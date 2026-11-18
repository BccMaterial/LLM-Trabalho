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

ATENDENTE_PROMPT = load_prompt("atendente_v1")
SYSTEM_PROMPT = ATENDENTE_PROMPT.content
MAX_TOOL_ROUNDS = 5
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
    completed_action_keys: list[str]


def build_scheduling_graph(
    llm_client: llm.OpenAI,
    api_client: tools.ApiClient,
):
    def call_model(state: SchedulingState) -> dict:
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

        response = llm.request_with_retry(llm_client, messages)
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        assistant_message = message.model_dump(exclude_none=True)
        pending_actions = [
            tool_call.model_dump(exclude_none=True) for tool_call in tool_calls
        ]
        structured_response = None
        answer = None
        if not tool_calls:
            try:
                output = validate_agent_output(
                    message.content or "",
                    state["tool_results"],
                )
            except InvalidAgentOutputError:
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
        return {
            "messages": (
                state["messages"]
                if tool_calls
                else state["messages"] + [assistant_message]
            ),
            "round_count": state["round_count"] + 1,
            "pending_action": pending_actions or None,
            "pending_message": assistant_message if tool_calls else None,
            "structured_response": structured_response,
            "answer": answer,
            "proposal_version": (
                state.get("proposal_version", 0) + 1
                if any(
                    tool_call["function"]["name"] == "confirmar_agendamento"
                    for tool_call in pending_actions
                )
                else state.get("proposal_version", 0)
            ),
            "approval_decision": None,
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
                raise RuntimeError(
                    "O agendamento não pode ser executado sem aprovação explícita."
                )
            arguments = json.loads(tool_call["function"]["arguments"])
            result = tools.execute_tool(
                api_client,
                name,
                arguments,
                authenticated_user=authenticated_user,
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

    def route_after_model(state: SchedulingState) -> str:
        if not state["pending_action"]:
            return "end"
        if any(
            tool_call["function"]["name"] == "confirmar_agendamento"
            for tool_call in state["pending_action"]
        ):
            if not state.get("authenticated_user"):
                return "require_authentication"
            return "request_approval"
        return "dispatch_tools"

    def require_authentication(state: SchedulingState) -> dict:
        answer = "Para agendar, faça login com o comando /login."
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
            "pending_action": None,
            "pending_message": None,
            "answer": answer,
        }

    def dispatch_tools(state: SchedulingState) -> dict:
        messages = list(state["messages"])
        if state["pending_message"]:
            messages.append(state["pending_message"])
        tool_results = list(state["tool_results"])
        approved_key = state.get("approved_action_key")
        completed_action_keys = list(state.get("completed_action_keys") or [])
        if approved_key and approved_key in completed_action_keys:
            result = {
                "idempotent": True,
                "mensagem": "Esta ação aprovada já foi executada.",
            }
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
            return {
                "messages": messages,
                "pending_action": None,
                "pending_message": None,
                "tool_results": tool_results,
                "approval_result": None,
                "approval_decision": None,
                "approved_action_key": None,
            }
        execute_tool_calls(
            state["pending_action"] or [],
            messages,
            tool_results,
            approval_result=state["approval_result"],
            authenticated_user=state.get("authenticated_user"),
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
            and approved_key not in completed_action_keys
            and isinstance(booking_result, dict)
            and booking_result.get("id")
        ):
            completed_action_keys.append(approved_key)

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
                "completed_action_keys": completed_action_keys,
                "structured_response": structured_response,
                "answer": answer,
            }

        return {
            "messages": messages,
            "pending_action": None,
            "pending_message": None,
            "tool_results": tool_results,
            "approval_result": None,
            "approval_decision": None,
            "approved_action_key": None,
            "completed_action_keys": completed_action_keys,
        }

    def request_approval(state: SchedulingState) -> dict:
        list_professionals = getattr(api_client, "listar_profissionais", None)
        if not callable(list_professionals):
            return actions.request_appointment_approval(dict(state))

        confirmation_call = next(
            (
                tool_call
                for tool_call in state["pending_action"] or []
                if tool_call["function"]["name"] == "confirmar_agendamento"
            ),
            None,
        )
        arguments = (
            json.loads(confirmation_call["function"]["arguments"])
            if confirmation_call
            else {}
        )
        try:
            professionals = list_professionals()
        except RuntimeError:
            answer = (
                "Não consegui validar o profissional na API agora. "
                "Nenhum agendamento foi criado; tente novamente mais tarde."
            )
            output = insufficient_response(answer, "validacao_de_profissional")
            return {
                "messages": state["messages"]
                + [{"role": "assistant", "content": answer}],
                "pending_action": None,
                "pending_message": None,
                "approval_result": None,
                "approval_decision": "professional_lookup_failed",
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
            }

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
            output = insufficient_response(answer, "escolha_de_profissional")
            return {
                "messages": state["messages"]
                + [{"role": "assistant", "content": answer}],
                "pending_action": None,
                "pending_message": None,
                "approval_result": None,
                "approval_decision": "invalid_professional",
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
            }

        approval_state = dict(state)
        approval_state["professional_name"] = professional["nome"]
        return actions.request_appointment_approval(approval_state)

    def route_from_start(state: SchedulingState) -> str:
        if state["pending_action"] and state["approval_result"] is None:
            return "request_approval"
        return "call_model"

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
            return {
                "pending_action": None,
                "approval_result": None,
                "approval_decision": None,
                "answer": "Não há uma proposta válida para revalidar.",
            }
        arguments = json.loads(confirmation_call["function"]["arguments"])
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
        except RuntimeError:
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
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
            }
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
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
            }
        return {"pending_action": state["pending_action"]}

    def route_after_tools(state: SchedulingState) -> str:
        final_status = (
            (state.get("structured_response") or {}).get("resultado", {}).get("status")
        )
        if final_status in {"agendamento_confirmado", "agendamento_nao_confirmado"}:
            return "end"
        return (
            "limit_reached" if state["round_count"] >= MAX_TOOL_ROUNDS else "call_model"
        )

    def limit_reached(_: SchedulingState) -> dict:
        output = insufficient_response(
            "Não foi possível concluir o atendimento dentro do limite da demonstração.",
            "limite_de_rodadas",
        )
        return {
            "structured_response": output.model_dump(mode="json"),
            "answer": output.resultado.mensagem,
        }

    builder = StateGraph(SchedulingState)
    builder.add_node("call_model", call_model)
    builder.add_node("dispatch_tools", dispatch_tools)
    builder.add_node("request_approval", request_approval)
    builder.add_node("revalidate_availability", revalidate_availability)
    builder.add_node("require_authentication", require_authentication)
    builder.add_node("limit_reached", limit_reached)
    builder.add_conditional_edges(
        START,
        route_from_start,
        {
            "call_model": "call_model",
            "request_approval": "request_approval",
        },
    )
    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "dispatch_tools": "dispatch_tools",
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
        "request_approval",
        lambda state: (
            "revalidate_availability"
            if state["approval_result"] is True
            else (
                "request_approval"
                if state["approval_result"] is None
                and state["approval_decision"] is None
                else "end"
            )
        ),
        {
            "revalidate_availability": "revalidate_availability",
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
            "limit_reached": "limit_reached",
            "end": END,
        },
    )
    builder.add_edge("limit_reached", END)
    return builder.compile(checkpointer=MemorySaver())
