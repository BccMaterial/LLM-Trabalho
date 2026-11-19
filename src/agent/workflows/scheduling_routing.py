from typing import Any


def route_after_model(state: dict[str, Any]) -> str:
    if state.get("termination_reason"):
        return "end"
    if not state["pending_action"]:
        return "end"
    if any(
        tool_call["function"]["name"] == "confirmar_agendamento"
        for tool_call in state["pending_action"]
    ):
        if not state.get("authenticated_user"):
            return "require_authentication"
        return "validate_professional"
    return "dispatch_tools"


def route_from_start(state: dict[str, Any]) -> str:
    if state["pending_action"] and state["approval_result"] is None:
        return (
            "request_approval"
            if state.get("professional_validated")
            else "validate_professional"
        )
    return "call_model"


def route_after_professional_validation(state: dict[str, Any]) -> str:
    return "end" if state.get("termination_reason") else "request_approval"


def route_after_approval(state: dict[str, Any]) -> str:
    if state.get("termination_reason"):
        return "end"
    if state["approval_result"] is True:
        return "revalidate_availability"
    if state["approval_result"] is None and state["approval_decision"] is None:
        return (
            "request_approval"
            if state.get("professional_validated")
            else "validate_professional"
        )
    return "end"


def route_after_tools(state: dict[str, Any]) -> str:
    if state.get("termination_reason"):
        return "end"
    final_status = (
        (state.get("structured_response") or {}).get("resultado", {}).get("status")
    )
    if final_status in {"agendamento_confirmado", "agendamento_nao_confirmado"}:
        return "end"
    return "call_model"
