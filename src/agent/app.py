import getpass
import json
import re
import unicodedata
from typing import Any, TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from src.prompts import load_prompt

from . import llm, tools
from .demo_data import populate_example_data

load_dotenv()

ATENDENTE_PROMPT = load_prompt("atendente_v1")
SYSTEM_PROMPT = ATENDENTE_PROMPT.content
DEMO_MESSAGE = "Quero agendar uma avaliação neuropsicológica para a manhã."
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


class SchedulingState(TypedDict):
    messages: list[dict]
    conversation_id: str
    round_count: int
    pending_action: list[dict] | None
    pending_message: dict | None
    approval_result: bool | None
    tool_results: list[dict[str, Any]]
    answer: str | None
    authenticated_user: dict[str, Any] | None


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
        return {
            "messages": (
                state["messages"]
                if tool_calls
                else state["messages"] + [assistant_message]
            ),
            "round_count": state["round_count"] + 1,
            "pending_action": [
                tool_call.model_dump(exclude_none=True) for tool_call in tool_calls
            ]
            or None,
            "pending_message": assistant_message if tool_calls else None,
            "answer": None if tool_calls else message.content or "",
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
        execute_tool_calls(
            state["pending_action"] or [],
            messages,
            tool_results,
            approval_result=state["approval_result"],
            authenticated_user=state.get("authenticated_user"),
        )
        return {
            "messages": messages,
            "pending_action": None,
            "pending_message": None,
            "tool_results": tool_results,
            "approval_result": None,
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

        answer = (
            "Antes de registrar, confirme o horário exato: "
            f"{start} a {end}. Responda “sim, confirmo” para autorizar "
            "ou “não” para cancelar."
        )
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
            "pending_action": pending_actions,
            "approval_result": None,
            "answer": answer,
        }

    def route_from_start(state: SchedulingState) -> str:
        if state["pending_action"] and state["approval_result"] is None:
            return "resolve_approval"
        return "call_model"

    def resolve_approval(state: SchedulingState) -> dict:
        patient_message = state["messages"][-1].get("content", "")
        approval = _parse_approval_response(patient_message)
        if approval is True:
            return {"approval_result": True}
        if approval is False:
            messages = list(state["messages"])
            if state["pending_message"]:
                messages.append(state["pending_message"])
            for tool_call in state["pending_action"] or []:
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
            return {
                "messages": messages,
                "pending_action": None,
                "pending_message": None,
                "approval_result": False,
            }

        answer = (
            "Não consegui identificar uma confirmação ou recusa. "
            "Responda “sim, confirmo” para autorizar esse horário ou “não” "
            "para cancelar."
        )
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
            "answer": answer,
        }

    def route_after_approval(state: SchedulingState) -> str:
        if state["approval_result"] is True:
            return "dispatch_tools"
        if state["approval_result"] is False:
            return "call_model"
        return "end"

    def route_after_tools(state: SchedulingState) -> str:
        return (
            "limit_reached" if state["round_count"] >= MAX_TOOL_ROUNDS else "call_model"
        )

    def limit_reached(_: SchedulingState) -> dict:
        return {
            "answer": (
                "Não foi possível concluir o atendimento dentro do limite "
                "da demonstração."
            )
        }

    builder = StateGraph(SchedulingState)
    builder.add_node("call_model", call_model)
    builder.add_node("dispatch_tools", dispatch_tools)
    builder.add_node("request_approval", request_approval)
    builder.add_node("resolve_approval", resolve_approval)
    builder.add_node("require_authentication", require_authentication)
    builder.add_node("limit_reached", limit_reached)
    builder.add_conditional_edges(
        START,
        route_from_start,
        {"call_model": "call_model", "resolve_approval": "resolve_approval"},
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
        lambda _: "end",
        {"end": END},
    )
    builder.add_conditional_edges(
        "resolve_approval",
        route_after_approval,
        {
            "dispatch_tools": "dispatch_tools",
            "call_model": "call_model",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "dispatch_tools",
        route_after_tools,
        {"call_model": "call_model", "limit_reached": "limit_reached"},
    )
    builder.add_edge("limit_reached", END)
    return builder.compile()


def run_scheduling_flow(
    user_message: str = DEMO_MESSAGE, interactive: bool = True
) -> str:
    """Executa a demonstração em turnos até o paciente encerrar."""
    api_client = tools.ApiClient()
    llm_client = llm.create_client()
    graph = build_scheduling_graph(llm_client, api_client)
    state: SchedulingState = {
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        "conversation_id": str(uuid4()),
        "round_count": 0,
        "pending_action": None,
        "pending_message": None,
        "approval_result": None,
        "tool_results": [],
        "answer": None,
        "authenticated_user": None,
    }

    if interactive:
        print("Modo convidado ativo. Use /login para autenticar ou /help.")

    while True:
        state["messages"].append({"role": "user", "content": user_message})
        state["round_count"] = 0
        if not state["pending_action"]:
            state["approval_result"] = None
        state = graph.invoke(state)
        answer = state["answer"] or ""
        print(f"Agente: {answer}")

        if not interactive:
            return answer

        try:
            user_message = input("\nPaciente (ou 'sair'): ").strip()
        except EOFError:
            print("\nAtendimento encerrado.")
            return answer
        command = user_message.casefold()
        if command == "/help":
            print(TERMINAL_HELP)
            continue
        if command == "/login":
            email = input("\nE-mail: ").strip()
            password = getpass.getpass("Senha: ")
            if not email or not password:
                print("Informe o e-mail e a senha.")
                continue
            try:
                state["authenticated_user"] = api_client.login_user(email, password)
                print("Login realizado.")
            except RuntimeError as error:
                print(f"Não foi possível fazer login: {error}")
            continue
        if command == "/sair" or command in STOP_COMMANDS:
            print("Atendimento encerrado.")
            return answer
        if not user_message:
            print("Digite uma mensagem para continuar o atendimento.")
            continue


if __name__ == "__main__":
    print("Executando demonstração de solicitação de agendamento...")
    populate_example_data()
    print(run_scheduling_flow())
