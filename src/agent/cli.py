import getpass
import json
from uuid import uuid4

from langgraph.types import Command

from .integrations import llm
from .integrations.api import ApiClient
from .observability import (
    EvaluationTraceContext,
    configure_tracing,
    invoke_agent,
)
from .policy_retrieval import create_policy_retriever
from .workflows.execution import (
    LANGGRAPH_RECURSION_LIMIT,
    TerminationReason,
    new_execution_deadline,
)
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

    configure_tracing()
    api_client = ApiClient()
    llm_client = llm.create_client()
    graph = build_scheduling_graph(
        llm_client,
        api_client,
        create_policy_retriever(),
    )
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
        "approval_events": [],
        "proposal_version": 0,
        "approved_action_key": None,
        "completed_actions": {},
        "approval_expires_at": None,
        "professional_name": None,
        "professional_validated": False,
        "execution_deadline": None,
        "workflow_step_count": 0,
        "external_call_count": 0,
        "total_model_tokens": 0,
        "tool_call_counts": {},
        "termination_reason": None,
        "error_class": None,
        "error_kind": None,
    }

    if interactive:
        print("Modo convidado ativo. Use /login para autenticar ou /help.")

    turn_index = 0
    while True:
        if user_message is None:
            try:
                user_message = input("\nPaciente (ou 'sair'): ").strip()
            except EOFError:
                print("\nAtendimento encerrado.")
                state["termination_reason"] = TerminationReason.USER_EXIT.value
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
                state["termination_reason"] = TerminationReason.USER_EXIT.value
                return ""
            if not user_message:
                print("Digite uma mensagem para continuar o atendimento.")
                user_message = None
                continue

        state["messages"].append({"role": "user", "content": user_message})
        turn_index += 1
        state["round_count"] = 0
        state["tool_results"] = []
        state["workflow_step_count"] = 0
        state["external_call_count"] = 0
        state["total_model_tokens"] = 0
        state["tool_call_counts"] = {}
        state["termination_reason"] = None
        state["error_class"] = None
        state["error_kind"] = None
        state["execution_deadline"] = new_execution_deadline()
        api_client.set_execution_deadline(state["execution_deadline"])
        if not state["pending_action"]:
            state["approval_result"] = None
        config = {
            "configurable": {"thread_id": state["conversation_id"]},
            "recursion_limit": LANGGRAPH_RECURSION_LIMIT,
        }
        result = invoke_agent(
            graph,
            state,
            config,
            mode="interactive",
            turn_index=turn_index,
        )
        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        while interrupts:
            interrupt_value = interrupts[0].value
            if isinstance(interrupt_value, dict):
                arguments = interrupt_value.get("arguments", {})
                start = arguments.get("agenda_inicio", "")
                end = arguments.get("agenda_fim", "")
                professional_name = interrupt_value.get("professional_name")
                professional = f" com {professional_name}" if professional_name else ""
                print(
                    "Agente: "
                    f"Confirme o agendamento{professional} de {start} a {end}. "
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
                state["termination_reason"] = TerminationReason.USER_EXIT.value
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
            result = invoke_agent(
                graph,
                Command(resume=resume),
                config,
                mode="interactive",
                turn_index=turn_index,
                approval_decision=resume.get("decision"),
            )
            interrupts = (
                result.get("__interrupt__") if isinstance(result, dict) else None
            )
        state = result
        answer = state["answer"] or ""
        print(f"Agente: {answer}")

        if not interactive:
            return answer

        user_message = None


def run_scheduling_case(
    user_messages: list[str],
    *,
    login: tuple[str, str] | None = None,
    approval_decisions: list[dict] | None = None,
    evaluation_context: EvaluationTraceContext | None = None,
) -> dict:
    """Executa turnos do agente sem input humano e retorna estado exportável."""
    configure_tracing()
    api_client = ApiClient()
    llm_client = llm.create_client()
    graph = build_scheduling_graph(
        llm_client,
        api_client,
        create_policy_retriever(),
    )
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
        "approval_events": [],
        "proposal_version": 0,
        "approved_action_key": None,
        "completed_actions": {},
        "approval_expires_at": None,
        "professional_name": None,
        "professional_validated": False,
        "execution_deadline": None,
        "workflow_step_count": 0,
        "external_call_count": 0,
        "total_model_tokens": 0,
        "tool_call_counts": {},
        "termination_reason": None,
        "error_class": None,
        "error_kind": None,
    }

    authenticated_user = None
    if login is not None:
        authenticated_user = api_client.login_user(*login)
        state["authenticated_user"] = authenticated_user

    decisions = list(approval_decisions or [])
    interrupt_events: list[dict] = []
    turn_events: list[dict] = []
    all_tool_results: list[dict] = []
    for turn_index, user_message in enumerate(user_messages, start=1):
        state["messages"].append({"role": "user", "content": user_message})
        state["round_count"] = 0
        state["tool_results"] = []
        state["workflow_step_count"] = 0
        state["external_call_count"] = 0
        state["total_model_tokens"] = 0
        state["tool_call_counts"] = {}
        state["termination_reason"] = None
        state["error_class"] = None
        state["error_kind"] = None
        state["execution_deadline"] = new_execution_deadline()
        api_client.set_execution_deadline(state["execution_deadline"])
        if not state["pending_action"]:
            state["approval_result"] = None

        config = {
            "configurable": {"thread_id": state["conversation_id"]},
            "recursion_limit": LANGGRAPH_RECURSION_LIMIT,
        }
        result = invoke_agent(
            graph,
            state,
            config,
            mode="case",
            turn_index=turn_index,
            evaluation_context=evaluation_context,
        )
        turn_interrupts: list[dict] = []
        while isinstance(result, dict) and result.get("__interrupt__"):
            interrupt_value = result["__interrupt__"][0].value
            interrupt_event = (
                interrupt_value if isinstance(interrupt_value, dict) else {}
            )
            interrupt_events.append(interrupt_event)
            turn_interrupts.append(interrupt_event)
            resume = decisions.pop(0) if decisions else {"decision": "reject"}
            result = invoke_agent(
                graph,
                Command(resume=resume),
                config,
                mode="case",
                turn_index=turn_index,
                approval_decision=resume.get("decision"),
                evaluation_context=evaluation_context,
            )
        state = result
        turn_tool_results = state.get("tool_results") or []
        all_tool_results.extend(turn_tool_results)
        turn_events.append(
            {
                "input": user_message,
                "interrupts": turn_interrupts,
                "tool_results": turn_tool_results,
                "answer": state.get("answer"),
                "structured_response": state.get("structured_response"),
                "termination_reason": state.get("termination_reason"),
                "error_class": state.get("error_class"),
                "error_kind": state.get("error_kind"),
            }
        )

    return {
        "conversation_id": state["conversation_id"],
        "authenticated_user": authenticated_user,
        "interrupts": interrupt_events,
        "turns": turn_events,
        "answer": state.get("answer"),
        "structured_response": state.get("structured_response"),
        "tool_results": all_tool_results,
        "tool_call_counts": state.get("tool_call_counts") or {},
        "termination_reason": state.get("termination_reason"),
        "error_class": state.get("error_class"),
        "error_kind": state.get("error_kind"),
        "approval_decision": state.get("approval_decision"),
        "completed_actions": state.get("completed_actions") or {},
    }
