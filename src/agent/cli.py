import getpass
from uuid import uuid4

from .integrations import llm
from .integrations.api import ApiClient
from .workflows.scheduling import (
    STOP_COMMANDS,
    SYSTEM_PROMPT,
    TERMINAL_HELP,
    SchedulingState,
    build_scheduling_graph,
)

DEMO_MESSAGE = "Quero agendar uma avaliação neuropsicológica para a manhã."


def run_scheduling_flow(
    user_message: str = DEMO_MESSAGE, interactive: bool = True
) -> str:
    """Executa a demonstração em turnos até o paciente encerrar."""
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
