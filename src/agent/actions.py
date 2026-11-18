import hashlib
import json
import re
import unicodedata
from typing import Any

from langgraph.types import interrupt

from .output_contract import insufficient_response
from .workflows.execution import (
    TerminationReason,
    deadline_expired,
    new_approval_deadline,
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

REQUIRED_BOOKING_FIELDS = {
    "professional_id",
    "agenda_inicio",
    "agenda_fim",
    "suspeita_paciente",
}


def parse_approval_response(message: str) -> bool | None:
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


def approved_action_key(
    conversation_id: str,
    tool_call: dict,
    authenticated_user: dict | None = None,
) -> str:
    arguments = json.loads(tool_call["function"]["arguments"])
    if authenticated_user and authenticated_user.get("id"):
        arguments["patient_id"] = authenticated_user["id"]
    canonical = json.dumps(
        {
            "conversation_id": conversation_id,
            "action": tool_call["function"]["name"],
            "arguments": arguments,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_approval_resume(resume: Any) -> dict:
    if isinstance(resume, str):
        parsed = parse_approval_response(resume)
        if parsed is True:
            return {"decision": "approve"}
        if parsed is False:
            return {"decision": "reject"}
        return {"decision": "invalid"}
    if not isinstance(resume, dict):
        return {"decision": "invalid"}
    return resume


def _validate_edited_booking(arguments: dict) -> str | None:
    if not REQUIRED_BOOKING_FIELDS.issubset(arguments):
        return "A edição não contém todos os dados obrigatórios."
    if not isinstance(arguments["agenda_inicio"], str):
        return "A edição contém argumentos inválidos."
    if not isinstance(arguments["agenda_fim"], str):
        return "A edição contém argumentos inválidos."
    if not isinstance(arguments["suspeita_paciente"], str):
        return "A edição contém argumentos inválidos."
    return None


def request_appointment_approval(state: dict) -> dict:
    pending_actions = state["pending_action"] or []
    confirmation_calls = [
        tool_call
        for tool_call in pending_actions
        if tool_call["function"]["name"] == "confirmar_agendamento"
    ]
    if len(confirmation_calls) != 1:
        raise ValueError("Só é possível solicitar confirmação de um horário por vez.")

    confirmation_call = confirmation_calls[0]
    arguments = json.loads(confirmation_call["function"]["arguments"])
    start = arguments.get("agenda_inicio")
    end = arguments.get("agenda_fim")
    professional_name = state.get("professional_name") or "profissional"
    if not start or not end:
        raise ValueError(
            "Não é possível pedir confirmação sem o início e o fim do horário."
        )

    resume = normalize_approval_resume(
        interrupt(
            {
                "type": "appointment_approval",
                "action": "confirmar_agendamento",
                "proposal_version": state["proposal_version"],
                "arguments": arguments,
                "professional_name": state.get("professional_name"),
                "expires_at": state.get("approval_expires_at"),
                "prompt": (
                    "Antes de registrar, confirme o profissional e o horário "
                    f"exatos: {professional_name} em {start} a {end}. "
                ),
                "accepted_responses": ["approve", "reject", "edit"],
            }
        )
    )

    if deadline_expired(state.get("approval_expires_at")):
        answer = (
            "A aprovação expirou. Nenhum agendamento foi criado; "
            "solicite uma nova proposta para continuar."
        )
        output = insufficient_response(answer, "aprovacao_expirada")
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
            "pending_action": None,
            "pending_message": None,
            "approval_result": False,
            "approval_decision": "expired",
            "approved_action_key": None,
            "approval_expires_at": None,
            "termination_reason": TerminationReason.APPROVAL_EXPIRED.value,
            "structured_response": output.model_dump(mode="json"),
            "answer": answer,
        }

    decision = resume.get("decision")
    if decision == "approve":
        approved_key = approved_action_key(
            state["conversation_id"],
            confirmation_call,
            state.get("authenticated_user"),
        )
        answer = f"O horário {start} a {end} foi aprovado explicitamente."
        output = insufficient_response(answer, "confirmacao_de_horario")
        return {
            "messages": state["messages"],
            "approval_result": True,
            "approval_decision": "approve",
            "approved_action_key": approved_key,
            "approval_expires_at": None,
            "termination_reason": None,
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
            "approval_expires_at": None,
            "termination_reason": TerminationReason.ACTION_REJECTED.value,
            "answer": answer,
        }

    if decision == "edit" and isinstance(resume.get("arguments"), dict):
        edited_arguments = resume["arguments"]
        invalid_reason = _validate_edited_booking(edited_arguments)
        if invalid_reason is None:
            edited_call = dict(confirmation_call)
            edited_call["function"] = dict(confirmation_call["function"])
            edited_call["function"]["arguments"] = json.dumps(
                edited_arguments,
                ensure_ascii=False,
            )
            return {
                "pending_action": [edited_call],
                "proposal_version": state["proposal_version"] + 1,
                "approval_result": None,
                "approval_decision": None,
                "approved_action_key": None,
                "approval_expires_at": new_approval_deadline(),
                "professional_name": None,
                "professional_validated": False,
                "termination_reason": None,
            }
        answer = invalid_reason
    else:
        answer = "Resposta inválida. Responda aprovar, rejeitar ou editar."

    output = insufficient_response(answer, "confirmacao_de_horario")
    return {
        "messages": state["messages"] + [{"role": "assistant", "content": answer}],
        "pending_action": pending_actions,
        "approval_result": None,
        "approval_decision": "invalid",
        "termination_reason": None,
        "structured_response": output.model_dump(mode="json"),
        "answer": answer,
    }
