import getpass
import json
from uuid import uuid4

from langgraph.types import Command

from .integrations import llm
from .integrations.api import ApiClient
from .workflows.scheduling import (
    STOP_COMMANDS,
    SYSTEM_PROMPT,
    TERMINAL_HELP,
    SchedulingState,
    build_scheduling_graph,
)


def run_scheduling_flow(
    user_message: str | None = None, interactive: bool = True
) -> str:
    """Executa o atendimento em turnos até o paciente encerrar."""
    if not interactive and user_message is None:
        raise ValueError("Informe user_message quando interactive for False.")

    api_client = ApiClient()
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
        "structured_response": None,
        "answer": None,
        "authenticated_user": None,
        "approval_decision": None,
        "proposal_version": 0,
        "approved_action_key": None,
        "completed_action_keys": [],
    }

    if interactive:
        print("Modo convidado ativo. Use /login para autenticar ou /help.")

    while True:
        if user_message is None:
            try:
                user_message = input("\nPaciente (ou 'sair'): ").strip()
            except EOFError:
                print("\nAtendimento encerrado.")
                return ""
            command = user_message.casefold()
            if command == "/help":
                print(TERMINAL_HELP)
                user_message = None
                continue
            if command == "/login":
                email = input("\nE-mail: ").strip()
                password = getpass.getpass("Senha: ")
                if not email or not password:
                    print("Informe o e-mail e a senha.")
                    user_message = None
                    continue
                try:
                    state["authenticated_user"] = api_client.login_user(email, password)
                    print("Login realizado.")
                except RuntimeError as error:
                    print(f"Não foi possível fazer login: {error}")
                user_message = None
                continue
            if command == "/sair" or command in STOP_COMMANDS:
                print("Atendimento encerrado.")
                return ""
            if not user_message:
                print("Digite uma mensagem para continuar o atendimento.")
                user_message = None
                continue

        state["messages"].append({"role": "user", "content": user_message})
        state["round_count"] = 0
        if not state["pending_action"]:
            state["approval_result"] = None
        config = {"configurable": {"thread_id": state["conversation_id"]}}
        result = graph.invoke(state, config)
        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        while interrupts:
            interrupt_value = interrupts[0].value
            if isinstance(interrupt_value, dict):
                arguments = interrupt_value.get("arguments", {})
                start = arguments.get("agenda_inicio", "")
                end = arguments.get("agenda_fim", "")
                print(
                    "Agente: "
                    f"Confirme o agendamento de {start} a {end}. "
                    "Responda aprovar, rejeitar ou editar."
                )
            if not interactive:
                return (
                    interrupt_value.get("prompt", "")
                    if isinstance(interrupt_value, dict)
                    else "A confirmação humana é necessária."
                )
            try:
                resume_text = input("Ação (aprovar/rejeitar/editar [JSON]): ").strip()
            except EOFError:
                print("\nAtendimento encerrado.")
                return ""
            normalized = resume_text.casefold()
            if normalized.startswith("aprovar"):
                resume = {"decision": "approve"}
            elif normalized.startswith("rejeitar"):
                resume = {"decision": "reject"}
            elif normalized.startswith("editar"):
                raw_arguments = resume_text.partition(" ")[2].strip()
                try:
                    edited_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    print("Informe os argumentos JSON da edição.")
                    continue
                resume = {
                    "decision": "edit",
                    "arguments": edited_arguments,
                }
            else:
                resume = {"decision": "invalid"}
            result = graph.invoke(Command(resume=resume), config)
            interrupts = (
                result.get("__interrupt__") if isinstance(result, dict) else None
            )
        state = result
        answer = state["answer"] or ""
        print(f"Agente: {answer}")

        if not interactive:
            return answer

        user_message = None
