import hashlib
import json
import re
import unicodedata
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ...prompts import load_prompt
from .. import tools
from ..integrations import llm
from ..output_contract import insufficient_response, validate_agent_output

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

AFFIRMATIVE_APPROVALS = {
    "confirmo",
    "confirmo esse horario",
    "confirmo o agendamento",
    "confirmo o horario",
    "pode agendar",
    "pode confirmar",
    "pode confirmar o agendamento",
    "sim",
    "sim confirmo",
}
NEGATIVE_APPROVALS = {
    "cancela",
    "cancele",
    "deixa para la",
    "deixa pra la",
    "nao",
    "nao confirmo",
    "nao quero",
    "nao quero agendar",
    "nao precisa",
    "prefiro nao",
}


def _approved_action_key(conversation_id: str, tool_call: dict) -> str:
    canonical = json.dumps(
        {
            "conversation_id": conversation_id,
            "action": tool_call["function"]["name"],
            "arguments": json.loads(tool_call["function"]["arguments"]),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _parse_approval_response(message: str) -> bool | None:
    normalized = unicodedata.normalize("NFKD", message.casefold())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = " ".join(normalized.split())
    if normalized in AFFIRMATIVE_APPROVALS:
        return True
    if normalized in NEGATIVE_APPROVALS:
        return False
    return None


def build_scheduling_graph(
    llm_client: llm.OpenAI,
    api_client: tools.ApiClient,
):
    def call_model(state: SchedulingState) -> dict:
        response = llm.request_with_retry(llm_client, state["messages"])
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        assistant_message = message.model_dump(exclude_none=True)
        pending_actions = [
            tool_call.model_dump(exclude_none=True) for tool_call in tool_calls
        ]
        structured_response = None
        answer = None
        if not tool_calls:
            output = validate_agent_output(
                message.content or "",
                state["tool_results"],
            )
            structured_response = output.model_dump(mode="json")
            answer = output.resultado.mensagem
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
        if approved_key and approved_key not in completed_action_keys:
            completed_action_keys.append(approved_key)
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
        pending_actions = state["pending_action"] or []
        confirmation_calls = [
            tool_call
            for tool_call in pending_actions
            if tool_call["function"]["name"] == "confirmar_agendamento"
        ]
        if len(confirmation_calls) != 1:
            raise ValueError(
                "Só é possível solicitar confirmação de um horário por vez."
            )

        confirmation_call = confirmation_calls[0]
        arguments = json.loads(confirmation_call["function"]["arguments"])
        start = arguments.get("agenda_inicio")
        end = arguments.get("agenda_fim")
        if not start or not end:
            raise ValueError(
                "Não é possível pedir confirmação sem o início e o fim do horário."
            )

        resume = interrupt(
            {
                "type": "appointment_approval",
                "action": "confirmar_agendamento",
                "proposal_version": state["proposal_version"],
                "arguments": arguments,
                "prompt": (
                    "Antes de registrar, confirme o horário exato: "
                    f"{start} a {end}. "
                ),
                "accepted_responses": ["approve", "reject", "edit"],
            }
        )

        if isinstance(resume, str):
            parsed = _parse_approval_response(resume)
            resume = (
                {"decision": "approve"}
                if parsed is True
                else (
                    {"decision": "reject"}
                    if parsed is False
                    else {"decision": "invalid"}
                )
            )
        if not isinstance(resume, dict):
            resume = {"decision": "invalid"}

        decision = resume.get("decision")
        if decision == "approve":
            approved_key = _approved_action_key(
                state["conversation_id"], confirmation_call
            )
            answer = f"O horário {start} a {end} foi aprovado explicitamente."
            output = insufficient_response(answer, "confirmacao_de_horario")
            return {
                "messages": state["messages"],
                "approval_result": True,
                "approval_decision": "approve",
                "approved_action_key": approved_key,
                "structured_response": output.model_dump(mode="json"),
                "answer": None,
            }
        if decision == "reject":
            answer = "O agendamento não foi criado porque o paciente recusou."
            messages = list(state["messages"])
            if state["pending_message"]:
                messages.append(state["pending_message"])
            for tool_call in pending_actions:
                result = {
                    "cancelled": True,
                    "reason": "O paciente não autorizou o agendamento.",
                }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            output = insufficient_response(answer, "confirmacao_de_horario")
            return {
                "messages": messages,
                "pending_action": None,
                "pending_message": None,
                "approval_result": False,
                "approval_decision": "reject",
                "structured_response": output.model_dump(mode="json"),
                "answer": answer,
            }
        if decision == "edit" and isinstance(resume.get("arguments"), dict):
            edited_arguments = resume["arguments"]
            required = {
                "professional_id",
                "agenda_inicio",
                "agenda_fim",
                "suspeita_paciente",
            }
            if not required.issubset(edited_arguments):
                answer = "A edição não contém todos os dados obrigatórios."
            else:
                try:
                    edited_start = edited_arguments["agenda_inicio"]
                    edited_end = edited_arguments["agenda_fim"]
                    if not isinstance(edited_start, str) or not isinstance(
                        edited_end, str
                    ):
                        raise ValueError
                    if not isinstance(edited_arguments["suspeita_paciente"], str):
                        raise ValueError
                except (KeyError, ValueError, TypeError):
                    answer = "A edição contém argumentos inválidos."
                else:
                    confirmation_call = dict(confirmation_call)
                    confirmation_call["function"] = dict(confirmation_call["function"])
                    confirmation_call["function"]["arguments"] = json.dumps(
                        edited_arguments,
                        ensure_ascii=False,
                    )
                    return {
                        "pending_action": [confirmation_call],
                        "proposal_version": state["proposal_version"] + 1,
                        "approval_result": None,
                        "approval_decision": None,
                        "approved_action_key": None,
                    }
        else:
            answer = "Resposta inválida. Responda aprovar, rejeitar ou editar."

        output = insufficient_response(answer, "confirmacao_de_horario")
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
            "pending_action": pending_actions,
            "approval_result": None,
            "approval_decision": "invalid",
            "structured_response": output.model_dump(mode="json"),
            "answer": answer,
        }

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
        {"call_model": "call_model", "limit_reached": "limit_reached"},
    )
    builder.add_edge("limit_reached", END)
    return builder.compile(checkpointer=MemorySaver())
