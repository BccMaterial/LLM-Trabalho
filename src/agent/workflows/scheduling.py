import hashlib
import json
from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ...prompts import load_prompt
from .. import actions, tools
from ..integrations import llm
from ..output_contract import (
    InvalidAgentOutputError,
    booking_result_response,
    insufficient_response,
    validate_agent_output,
)
from ..policy_retrieval import PolicyRetriever
from .execution import (
    MAX_COMPLETION_TOKENS_PER_CALL,
    MAX_EXTERNAL_CALLS,
    MAX_IDENTICAL_TOOL_CALLS,
    MAX_MODEL_TOKENS,
    MAX_WORKFLOW_STEPS,
    ErrorClass,
    FatalExecutionError,
    TerminationReason,
    classify_execution_error,
    deadline_expired,
    new_approval_deadline,
    remaining_seconds,
)
from .scheduling_routing import (
    route_after_approval,
    route_after_model,
    route_after_professional_validation,
    route_after_tools,
    route_from_start,
)

ATENDENTE_PROMPT = load_prompt("atendente_v1")
SYSTEM_PROMPT = ATENDENTE_PROMPT.content
STOP_COMMANDS = {"sair", "encerrar", "fim", "quit", "exit"}
TERMINAL_HELP = (
    "Comandos disponíveis:\n"
    "/login - autenticar sua conta\n"
    "/help - mostrar esta ajuda\n"
    "/sair - encerrar o atendimento"
)


class SchedulingState(TypedDict):
    messages: list[dict]
    conversation_id: str
    round_count: int
    pending_action: list[dict] | None
    pending_message: dict | None
    approval_result: bool | None
    tool_results: list[dict[str, Any]]
    structured_response: dict | None
    answer: str | None
    authenticated_user: dict[str, Any] | None
    approval_decision: str | None
    proposal_version: int
    approved_action_key: str | None
    completed_actions: dict[str, dict[str, Any]]
    approval_expires_at: str | None
    professional_name: str | None
    professional_validated: bool
    execution_deadline: str | None
    workflow_step_count: int
    external_call_count: int
    total_model_tokens: int
    tool_call_counts: dict[str, int]
    termination_reason: str | None
    error_class: str | None


def _tool_call_fingerprint(tool_call: dict) -> str:
    canonical = json.dumps(
        {
            "name": tool_call["function"]["name"],
            "arguments": json.loads(tool_call["function"]["arguments"]),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _response_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens", 0)
    else:
        total_tokens = getattr(usage, "total_tokens", 0)
    return total_tokens if isinstance(total_tokens, int) and total_tokens > 0 else 0


def _limit_reason(state: SchedulingState) -> TerminationReason | None:
    if state.get("workflow_step_count", 0) >= MAX_WORKFLOW_STEPS:
        return TerminationReason.LIMIT_REACHED
    if state.get("external_call_count", 0) >= MAX_EXTERNAL_CALLS:
        return TerminationReason.LIMIT_REACHED
    if state.get("total_model_tokens", 0) >= MAX_MODEL_TOKENS:
        return TerminationReason.LIMIT_REACHED
    if deadline_expired(state.get("execution_deadline")):
        return TerminationReason.LIMIT_REACHED
    return None


def _terminal_update(
    message: str,
    reason: TerminationReason,
    error_class: ErrorClass | None = None,
    *,
    state: SchedulingState | None = None,
    workflow_steps: int | None = None,
    external_calls: int | None = None,
    model_tokens: int | None = None,
) -> dict:
    output = insufficient_response(message, reason.value)
    update = {
        "pending_action": None,
        "pending_message": None,
        "approval_result": None,
        "structured_response": output.model_dump(mode="json"),
        "answer": message,
        "termination_reason": reason.value,
        "error_class": error_class.value if error_class else None,
    }
    if state is not None:
        update.update(
            _budget_update(
                state,
                workflow_steps=workflow_steps,
                external_calls=external_calls,
                model_tokens=model_tokens,
            )
        )
    return update


def _budget_update(
    state: SchedulingState,
    *,
    workflow_steps: int | None = None,
    external_calls: int | None = None,
    model_tokens: int | None = None,
) -> dict:
    update = {}
    if workflow_steps is not None:
        update["workflow_step_count"] = (
            state.get("workflow_step_count", 0) + workflow_steps
        )
    if external_calls is not None:
        update["external_call_count"] = (
            state.get("external_call_count", 0) + external_calls
        )
    if model_tokens is not None:
        update["total_model_tokens"] = model_tokens
    return update


def _error_update(
    error: Exception,
    state: SchedulingState,
    external_calls: int = 1,
) -> dict:
    error_class = classify_execution_error(error)
    reason = (
        TerminationReason.RECOVERABLE_ERROR
        if error_class == ErrorClass.RECOVERABLE
        else TerminationReason.FATAL_ERROR
    )
    message = (
        "O atendimento foi interrompido por uma falha temporária. "
        "Tente novamente mais tarde."
        if error_class == ErrorClass.RECOVERABLE
        else "O atendimento foi interrompido por uma falha interna. "
        "Nenhuma ação pendente foi executada."
    )
    return _terminal_update(
        message,
        reason,
        error_class,
        state=state,
        workflow_steps=1,
        external_calls=external_calls,
    )


def build_scheduling_graph(
    llm_client: llm.OpenAI,
    api_client: tools.ApiClient,
    policy_retriever: PolicyRetriever | None = None,
):
    def call_model(state: SchedulingState) -> dict:
        limit_reason = _limit_reason(state)
        if limit_reason:
            return _terminal_update(
                "O atendimento atingiu um limite seguro de execução. "
                "Nenhuma ação adicional foi executada.",
                limit_reason,
            )

        messages = list(state["messages"])
        if messages and messages[0].get("role") == "system":
            system_message = dict(messages[0])
            current_datetime = datetime.now(ZoneInfo("America/Sao_Paulo"))
            if state.get("authenticated_user"):
                authentication_context = (
                    "O paciente já está autenticado. A identidade dele vem da "
                    "sessão da API; nunca peça nome ou ID do paciente para "
                    "agendar."
                )
            else:
                authentication_context = (
                    "O paciente não está autenticado. Para agendar, oriente-o "
                    "a usar /login; não peça nome ou ID como substituto do login."
                )
            system_message["content"] = (
                f"{system_message['content']}\n\n"
                "Contexto de data e hora: considere a data atual como "
                f"{current_datetime:%Y-%m-%d}, no fuso America/Sao_Paulo. "
                "Use essa data como referência para interpretar expressões "
                "como hoje e amanhã; não deduza a data com base no treinamento.\n"
                f"Contexto de autenticação: {authentication_context}"
            )
            messages[0] = system_message

        try:
            remaining_tokens = MAX_MODEL_TOKENS - state.get("total_model_tokens", 0)
            timeout_seconds = remaining_seconds(state.get("execution_deadline"))
            if timeout_seconds <= 0:
                return _terminal_update(
                    "O atendimento excedeu o tempo máximo de execução.",
                    TerminationReason.LIMIT_REACHED,
                )
            response = llm.request_with_retry(
                llm_client,
                messages,
                max_tokens=min(MAX_COMPLETION_TOKENS_PER_CALL, remaining_tokens),
                timeout_seconds=timeout_seconds,
                tool_definitions=tools.get_tool_definitions(
                    include_policy_retrieval=policy_retriever is not None
                ),
            )
        except (RuntimeError, TimeoutError, ConnectionError) as error:
            return _error_update(error, state)
        except (ValueError, TypeError, KeyError) as error:
            return _error_update(error, state)

        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        assistant_message = message.model_dump(exclude_none=True)
        pending_actions = [
            tool_call.model_dump(exclude_none=True) for tool_call in tool_calls
        ]
        has_booking_action = any(
            tool_call["function"]["name"] == "confirmar_agendamento"
            for tool_call in pending_actions
        )
        structured_response = None
        answer = None
        termination_reason = None
        error_class = None
        if not tool_calls:
            termination_reason = TerminationReason.NORMAL_COMPLETION.value
        if not tool_calls:
            try:
                output = validate_agent_output(
                    message.content or "",
                    state["tool_results"],
                )
            except InvalidAgentOutputError:
                termination_reason = TerminationReason.RECOVERABLE_ERROR.value
                error_class = ErrorClass.RECOVERABLE.value
                output = insufficient_response(
                    "Não consegui processar esta resposta com segurança. "
                    "Pode reformular sua pergunta?",
                    "resposta_invalida_do_agente",
                )
            structured_response = output.model_dump(mode="json")
            answer = output.resultado.mensagem
            assistant_message = {
                "role": "assistant",
                "content": json.dumps(structured_response, ensure_ascii=False),
            }
        tool_call_counts = dict(state.get("tool_call_counts") or {})
        for tool_call in pending_actions:
            if tool_call["function"]["name"] == "confirmar_agendamento":
                continue
            try:
                fingerprint = _tool_call_fingerprint(tool_call)
            except (ValueError, TypeError, KeyError) as error:
                return _error_update(error, state)
            tool_call_counts[fingerprint] = tool_call_counts.get(fingerprint, 0) + 1
            if tool_call_counts[fingerprint] > MAX_IDENTICAL_TOOL_CALLS:
                return _terminal_update(
                    "O atendimento foi encerrado porque repetiu uma consulta "
                    "sem progresso. Reformule o pedido para continuar.",
                    TerminationReason.UNPRODUCTIVE_LOOP,
                    state=state,
                    workflow_steps=1,
                    external_calls=1,
                    model_tokens=state.get("total_model_tokens", 0)
                    + _response_tokens(response),
                )
        total_model_tokens = state.get("total_model_tokens", 0) + _response_tokens(
            response
        )
        if total_model_tokens > MAX_MODEL_TOKENS:
            return _terminal_update(
                "O atendimento atingiu o limite de tokens permitido. "
                "Nenhuma ação adicional foi executada.",
                TerminationReason.LIMIT_REACHED,
                state=state,
                workflow_steps=1,
                external_calls=1,
                model_tokens=total_model_tokens,
            )
        return {
            "messages": (
                state["messages"]
                if tool_calls
                else state["messages"] + [assistant_message]
            ),
            "round_count": state["round_count"] + 1,
            **_budget_update(state, workflow_steps=1, external_calls=1),
            "pending_action": pending_actions or None,
            "pending_message": assistant_message if tool_calls else None,
            "structured_response": structured_response,
            "answer": answer,
            "total_model_tokens": total_model_tokens,
            "tool_call_counts": tool_call_counts,
            "termination_reason": termination_reason,
            "error_class": error_class,
            "proposal_version": (
                state.get("proposal_version", 0) + 1
                if has_booking_action
                else state.get("proposal_version", 0)
            ),
            "approval_decision": None,
            "approval_expires_at": (
                new_approval_deadline()
                if has_booking_action
                else state.get("approval_expires_at")
            ),
            "professional_name": (
                None if has_booking_action else state.get("professional_name")
            ),
            "professional_validated": (
                False
                if has_booking_action
                else bool(state.get("professional_validated"))
            ),
        }

    def execute_tool_calls(
        tool_calls: list[dict],
        messages: list[dict],
        tool_results: list[dict[str, Any]],
        approval_result: bool | None = None,
        authenticated_user: dict[str, Any] | None = None,
    ) -> None:
        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            if name == "confirmar_agendamento" and approval_result is not True:
                raise FatalExecutionError(
                    "O agendamento não pode ser executado sem aprovação explícita."
                )
            arguments = json.loads(tool_call["function"]["arguments"])
            result = tools.execute_tool(
                api_client,
                name,
                arguments,
                authenticated_user=authenticated_user,
                policy_retriever=policy_retriever,
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
            tool_results.append({"name": name, "result": result})

    def require_authentication(state: SchedulingState) -> dict:
        answer = "Para agendar, faça login com o comando /login."
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
            "pending_action": None,
            "pending_message": None,
            "answer": answer,
            "termination_reason": TerminationReason.NORMAL_COMPLETION.value,
        }

    def dispatch_tools(state: SchedulingState) -> dict:
        messages = list(state["messages"])
        if state["pending_message"]:
            messages.append(state["pending_message"])
        tool_results = list(state["tool_results"])
        approved_key = state.get("approved_action_key")
        completed_actions = dict(state.get("completed_actions") or {})
        if approved_key and approved_key in completed_actions:
            result = dict(completed_actions[approved_key])
            result["idempotent"] = True
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": (state["pending_action"] or [{}])[0].get(
                        "id", "approved-action"
                    ),
                    "name": "confirmar_agendamento",
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
            tool_results.append({"name": "confirmar_agendamento", "result": result})
            budget_update = _budget_update(state, workflow_steps=1, external_calls=0)
        else:
            limit_reason = _limit_reason(state)
            attempted_tool_calls = len(state["pending_action"] or [])
            if limit_reason or (
                state.get("external_call_count", 0) + attempted_tool_calls
                > MAX_EXTERNAL_CALLS
            ):
                return _terminal_update(
                    "O atendimento atingiu um limite seguro de execução. "
                    "Nenhuma ação adicional foi executada.",
                    limit_reason or TerminationReason.LIMIT_REACHED,
                )
            try:
                execute_tool_calls(
                    state["pending_action"] or [],
                    messages,
                    tool_results,
                    approval_result=state["approval_result"],
                    authenticated_user=state.get("authenticated_user"),
                )
            except (RuntimeError, TimeoutError, ConnectionError) as error:
                return _error_update(error, state, attempted_tool_calls)
            except (FatalExecutionError, ValueError, TypeError, KeyError) as error:
                return _error_update(error, state, attempted_tool_calls)
            budget_update = _budget_update(
                state,
                workflow_steps=1,
                external_calls=attempted_tool_calls,
            )

        booking_result = next(
            (
                tool_result["result"]
                for tool_result in reversed(tool_results)
                if tool_result["name"] == "confirmar_agendamento"
            ),
            None,
        )
        if (
            approved_key
            and isinstance(booking_result, dict)
            and booking_result.get("id")
        ):
            completed_actions[approved_key] = {
                key: booking_result[key]
                for key in ("id", "agenda_inicio", "agenda_fim")
                if key in booking_result
            }

        booking_output = booking_result_response(tool_results)
        if booking_output is not None:
            structured_response = booking_output.model_dump(mode="json")
            answer = booking_output.resultado.mensagem
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(structured_response, ensure_ascii=False),
                }
            )
            return {
                "messages": messages,
                "pending_action": None,
                "pending_message": None,
                "tool_results": tool_results,
                "approval_result": None,
                "approval_decision": None,
                "approved_action_key": None,
                "completed_actions": completed_actions,
                "structured_response": structured_response,
                "answer": answer,
                **budget_update,
                "termination_reason": TerminationReason.NORMAL_COMPLETION.value,
                "error_class": None,
            }

        pending_tool_calls = state["pending_action"] or []
        if pending_tool_calls and all(
            call["function"]["name"] == "consultar_politica"
            for call in pending_tool_calls
        ):
            policy_results = [
                item["result"]
                for item in tool_results
                if item["name"] == "consultar_politica"
            ]
            if policy_results and all(
                isinstance(result, dict)
                and result.get("suficiencia") == "insuficiente"
                and not result.get("resultados")
                for result in policy_results
            ):
                answer = (
                    "Não encontrei uma política aprovada e vigente que "
                    "sustente essa resposta. Posso ajudar com outra dúvida "
                    "administrativa ou encaminhar a pergunta para a equipe."
                )
                output = insufficient_response(answer, "politica_nao_encontrada")
                structured_response = output.model_dump(mode="json")
                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(structured_response, ensure_ascii=False),
                    }
                )
                return {
                    "messages": messages,
                    "pending_action": None,
                    "pending_message": None,
                    "tool_results": tool_results,
                    "approval_result": None,
                    "approval_decision": None,
                    "approved_action_key": None,
                    "completed_actions": completed_actions,
                    "structured_response": structured_response,
                    "answer": answer,
                    **budget_update,
                    "termination_reason": TerminationReason.NORMAL_COMPLETION.value,
                    "error_class": None,
                }

        return {
            "messages": messages,
            "pending_action": None,
            "pending_message": None,
            "tool_results": tool_results,
            "approval_result": None,
            "approval_decision": None,
            "approved_action_key": None,
            "completed_actions": completed_actions,
            **budget_update,
            "termination_reason": None,
        }

    def validate_professional(state: SchedulingState) -> dict:
        list_professionals = getattr(api_client, "listar_profissionais", None)
        if not callable(list_professionals):
            return {
                "professional_validated": True,
                "professional_name": None,
                **_budget_update(state, workflow_steps=1),
            }

        limit_reason = _limit_reason(state)
        if limit_reason:
            return _terminal_update(
                "O atendimento atingiu um limite seguro de execução. "
                "Nenhuma ação adicional foi executada.",
                limit_reason,
            )

        confirmation_call = next(
            (
                tool_call
                for tool_call in state["pending_action"] or []
                if tool_call["function"]["name"] == "confirmar_agendamento"
            ),
            None,
        )
        if confirmation_call is None:
            return _terminal_update(
                "Não há uma proposta válida para validar.",
                TerminationReason.FATAL_ERROR,
                ErrorClass.FATAL,
            )
        try:
            arguments = json.loads(confirmation_call["function"]["arguments"])
        except (ValueError, TypeError, KeyError) as error:
            return _error_update(error, state, external_calls=0)

        try:
            professionals = list_professionals()
        except (RuntimeError, TimeoutError, ConnectionError) as error:
            answer = (
                "Não consegui validar o profissional na API agora. "
                "Nenhum agendamento foi criado; tente novamente mais tarde."
            )
            update = _error_update(error, state)
            update["answer"] = answer
            update["structured_response"] = insufficient_response(
                answer, "validacao_de_profissional"
            ).model_dump(mode="json")
            return update
        except (ValueError, TypeError, KeyError) as error:
            return _error_update(error, state)

        professional_id = arguments.get("professional_id")
        try:
            normalized_professional_id = str(UUID(professional_id))
        except (AttributeError, TypeError, ValueError):
            normalized_professional_id = ""
        professional = next(
            (
                item
                for item in professionals
                if item.get("id") == normalized_professional_id
            ),
            None,
        )
        if professional is None:
            names = [item["nome"] for item in professionals if item.get("nome")]
            if names:
                available_names = ", ".join(names)
                answer = (
                    "Não consegui validar o profissional desta proposta. "
                    "Nenhum agendamento foi criado. Escolha um profissional "
                    f"ativo para continuar: {available_names}."
                )
            else:
                answer = (
                    "Não há profissionais ativos cadastrados para este "
                    "agendamento. Nenhum agendamento foi criado."
                )
            update = _terminal_update(
                answer,
                TerminationReason.FATAL_ERROR,
                ErrorClass.FATAL,
            )
            update["messages"] = state["messages"] + [
                {"role": "assistant", "content": answer}
            ]
            update.update(_budget_update(state, workflow_steps=1, external_calls=1))
            update["structured_response"] = insufficient_response(
                answer, "escolha_de_profissional"
            ).model_dump(mode="json")
            return update
        return {
            "professional_name": professional["nome"],
            "professional_validated": True,
            **_budget_update(state, workflow_steps=1, external_calls=1),
        }

    def request_approval(state: SchedulingState) -> dict:
        limit_reason = _limit_reason(state)
        if limit_reason:
            return _terminal_update(
                "O atendimento atingiu um limite seguro de execução. "
                "Nenhuma ação adicional foi executada.",
                limit_reason,
            )

        approval_state = dict(state)
        try:
            update = actions.request_appointment_approval(approval_state)
        except (FatalExecutionError, ValueError, TypeError, KeyError) as error:
            return _error_update(error, state, external_calls=0)
        return update

    def revalidate_availability(state: SchedulingState) -> dict:
        confirmation_call = next(
            (
                tool_call
                for tool_call in state["pending_action"] or []
                if tool_call["function"]["name"] == "confirmar_agendamento"
            ),
            None,
        )
        if confirmation_call is None:
            return _terminal_update(
                "Não há uma proposta válida para revalidar.",
                TerminationReason.FATAL_ERROR,
                ErrorClass.FATAL,
            ) | {
                "pending_action": None,
                "approval_result": None,
                "approval_decision": None,
            }
        limit_reason = _limit_reason(state)
        if limit_reason:
            return _terminal_update(
                "O atendimento atingiu um limite seguro de execução. "
                "Nenhuma ação adicional foi executada.",
                limit_reason,
            )
        approved_key = state.get("approved_action_key")
        completed_actions = state.get("completed_actions") or {}
        if approved_key and approved_key in completed_actions:
            # A repeated approval for an action already applied in this
            # checkpoint must reach dispatch_tools' idempotency guard. A new
            # availability check would incorrectly turn a safe retry into a
            # conflict because the first write occupied that slot.
            return {
                "pending_action": state["pending_action"],
                **_budget_update(state, workflow_steps=1, external_calls=0),
            }
        try:
            arguments = json.loads(confirmation_call["function"]["arguments"])
        except (ValueError, TypeError, KeyError) as error:
            return _error_update(error, state)
        try:
            availability = tools.execute_tool(
                api_client,
                "consultar_disponibilidade",
                {
                    "professional_id": arguments.get("professional_id"),
                    "agenda_inicio": arguments.get("agenda_inicio"),
                    "agenda_fim": arguments.get("agenda_fim"),
                },
                authenticated_user=state.get("authenticated_user"),
            )
        except (RuntimeError, TimeoutError, ConnectionError):
            answer = (
                "Não consegui revalidar o profissional e o horário na API. "
                "Nenhum agendamento foi criado. Escolha um profissional e "
                "um horário disponíveis para tentar novamente."
            )
            output = insufficient_response(answer, "revalidacao_de_horario")
            return {
                "messages": state["messages"]
                + [{"role": "assistant", "content": answer}],
                "pending_action": None,
                "pending_message": None,
                "approval_result": None,
                "approval_decision": "revalidation_failed",
                "approved_action_key": None,
                **_budget_update(state, workflow_steps=1, external_calls=1),
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
                "termination_reason": TerminationReason.RECOVERABLE_ERROR.value,
                "error_class": ErrorClass.RECOVERABLE.value,
            }
        except (ValueError, TypeError, KeyError) as error:
            return _error_update(error, state)
        if availability.get("disponibilidade") != "disponivel":
            answer = (
                "O horário deixou de estar disponível. "
                "Nenhum agendamento foi criado."
            )
            output = insufficient_response(answer, "confirmacao_de_horario")
            return {
                "pending_action": None,
                "pending_message": None,
                "approval_result": None,
                "approval_decision": None,
                "approved_action_key": None,
                **_budget_update(state, workflow_steps=1, external_calls=1),
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
                "termination_reason": TerminationReason.NORMAL_COMPLETION.value,
            }
        return {
            "pending_action": state["pending_action"],
            **_budget_update(state, workflow_steps=1, external_calls=1),
        }

    builder = StateGraph(SchedulingState)
    builder.add_node("call_model", call_model)
    builder.add_node("dispatch_tools", dispatch_tools)
    builder.add_node("validate_professional", validate_professional)
    builder.add_node("request_approval", request_approval)
    builder.add_node("revalidate_availability", revalidate_availability)
    builder.add_node("require_authentication", require_authentication)
    builder.add_conditional_edges(
        START,
        route_from_start,
        {
            "call_model": "call_model",
            "validate_professional": "validate_professional",
            "request_approval": "request_approval",
        },
    )
    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "dispatch_tools": "dispatch_tools",
            "validate_professional": "validate_professional",
            "request_approval": "request_approval",
            "require_authentication": "require_authentication",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "require_authentication",
        lambda _: "end",
        {"end": END},
    )
    builder.add_conditional_edges(
        "validate_professional",
        route_after_professional_validation,
        {"request_approval": "request_approval", "end": END},
    )
    builder.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "revalidate_availability": "revalidate_availability",
            "validate_professional": "validate_professional",
            "request_approval": "request_approval",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "revalidate_availability",
        lambda state: (
            "dispatch_tools" if state["pending_action"] is not None else "end"
        ),
        {"dispatch_tools": "dispatch_tools", "end": END},
    )
    builder.add_conditional_edges(
        "dispatch_tools",
        route_after_tools,
        {
            "call_model": "call_model",
            "end": END,
        },
    )
    return builder.compile(checkpointer=MemorySaver())
