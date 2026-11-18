import json

from src.agent.actions import (
    approved_action_key,
    normalize_approval_resume,
    parse_approval_response,
)


def test_parse_approval_response_accepts_explicit_confirmation():
    assert parse_approval_response("Sim, confirmo.") is True
    assert parse_approval_response("não") is False
    assert parse_approval_response("Talvez") is None


def test_normalize_approval_resume_rejects_ambiguous_response():
    assert normalize_approval_resume("Sim, confirmo.") == {"decision": "approve"}
    assert normalize_approval_resume("Não.") == {"decision": "reject"}
    assert normalize_approval_resume("Talvez") == {"decision": "invalid"}


def test_approved_action_key_changes_when_arguments_change():
    tool_call = {
        "function": {
            "name": "confirmar_agendamento",
            "arguments": json.dumps(
                {
                    "professional_id": "professional-1",
                    "agenda_inicio": "2027-01-15T10:00:00-03:00",
                    "agenda_fim": "2027-01-15T11:00:00-03:00",
                }
            ),
        }
    }

    first = approved_action_key("conversation-1", tool_call)
    tool_call["function"]["arguments"] = json.dumps(
        {
            "professional_id": "professional-1",
            "agenda_inicio": "2027-01-15T14:00:00-03:00",
            "agenda_fim": "2027-01-15T15:00:00-03:00",
        }
    )
    second = approved_action_key("conversation-1", tool_call)

    assert first != second


def test_approved_action_key_uses_authenticated_patient_identity():
    call = {
        "function": {
            "name": "confirmar_agendamento",
            "arguments": json.dumps(
                {
                    "patient_id": "model-patient-1",
                    "professional_id": "professional-1",
                    "agenda_inicio": "2027-01-15T10:00:00-03:00",
                    "agenda_fim": "2027-01-15T11:00:00-03:00",
                }
            ),
        }
    }
    authenticated_user = {"id": "authenticated-patient"}
    first = approved_action_key("conversation-1", call, authenticated_user)
    call["function"]["arguments"] = json.dumps(
        {
            "patient_id": "model-patient-2",
            "professional_id": "professional-1",
            "agenda_inicio": "2027-01-15T10:00:00-03:00",
            "agenda_fim": "2027-01-15T11:00:00-03:00",
        }
    )

    second = approved_action_key("conversation-1", call, authenticated_user)

    assert first == second
