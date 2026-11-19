from types import SimpleNamespace

import cases


def test_sanitize_redacts_sensitive_fields():
    value = {
        "password": "secret",
        "Cookie": "session=secret",
        "patient_id": "patient-id",
        "answer": "ok",
        "nested": {"token": "secret", "id_paciente": "patient-id"},
    }

    assert cases._sanitize(value) == {
        "password": "<redacted>",
        "Cookie": "<redacted>",
        "patient_id": "<redacted>",
        "answer": "ok",
        "nested": {"token": "<redacted>", "id_paciente": "<redacted>"},
    }


def test_worktree_dirty_status_is_recorded(monkeypatch):
    monkeypatch.setattr(
        cases.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=" M src/agent/cli.py\n"),
    )

    assert cases._git_worktree_dirty() is True


def test_case_passed_requires_authenticated_booking():
    result = {
        "tool_results": [
            {
                "name": "confirmar_agendamento",
                "result": {"id": "appointment-1"},
            }
        ],
        "structured_response": {"resultado": {"status": "agendamento_confirmado"}},
    }

    assert cases._case_passed(1, result)


def test_case_passed_requires_no_booking_without_login():
    assert cases._case_passed(
        4,
        {
            "tool_results": [],
            "answer": "O agendamento exige login.",
            "completed_actions": {},
        },
    )


def test_case_passed_requires_missing_patient_tool_result():
    assert cases._case_passed(
        2,
        {
            "tool_results": [
                {
                    "name": "consultar_disponibilidade",
                    "result": {"erro": "Paciente não encontrado na API."},
                }
            ],
            "structured_response": {
                "resultado": {"status": "consulta_indisponivel"},
                "suficiencia": "insuficiente",
            },
            "error_class": None,
        },
    )
    assert not cases._case_passed(
        2,
        {
            "tool_results": [],
            "structured_response": {
                "resultado": {"status": "informacao_insuficiente"},
                "suficiencia": "insuficiente",
            },
        },
    )


def test_case_passed_requires_edited_approval_and_idempotent_retry():
    assert not cases._case_passed(
        6,
        {"completed_actions": {"action-key": {"id": "appointment-1"}}},
    )
    assert cases._case_passed(
        6,
        {
            "completed_actions": {"action-key": {"id": "appointment-1"}},
            "interrupts": [
                {"arguments": {"agenda_inicio": "2027-01-15T10:00:00"}},
                {"arguments": {"agenda_inicio": "2027-01-16T10:00:00"}},
                {"arguments": {"agenda_inicio": "2027-01-16T10:00:00"}},
                {"arguments": {"agenda_inicio": "2027-01-16T10:00:00"}},
            ],
            "tool_results": [
                {
                    "name": "confirmar_agendamento",
                    "result": {"id": "appointment-1"},
                },
                {
                    "name": "confirmar_agendamento",
                    "result": {"id": "appointment-1", "idempotent": True},
                },
            ],
        },
    )


def test_case_passed_requires_conflicting_slot_and_no_second_booking():
    assert cases._case_passed(
        9,
        {
            "setup_booking": {
                "id": "appointment-1",
                "professional_id": "professional-1",
                "agenda_inicio": "2097-10-02T14:00:00-03:00",
                "agenda_fim": "2097-10-02T15:00:00-03:00",
            },
            "tool_results": [
                {
                    "name": "consultar_disponibilidade",
                    "arguments": {
                        "professional_id": "professional-1",
                        "agenda_inicio": "2097-10-02T14:00:00-03:00",
                        "agenda_fim": "2097-10-02T15:00:00-03:00",
                    },
                    "result": {"disponibilidade": "indisponivel"},
                }
            ],
            "structured_response": {
                "resultado": {"status": "informacao_insuficiente"},
            },
            "error_class": None,
        },
    )
    assert not cases._case_passed(
        9,
        {
            "setup_booking": {
                "id": "appointment-1",
                "professional_id": "professional-1",
                "agenda_inicio": "2097-10-02T14:00:00-03:00",
                "agenda_fim": "2097-10-02T15:00:00-03:00",
            },
            "tool_results": [
                {
                    "name": "consultar_disponibilidade",
                    "arguments": {
                        "professional_id": "professional-1",
                        "agenda_inicio": "2097-10-02T14:00:00-03:00",
                        "agenda_fim": "2097-10-02T15:00:00-03:00",
                    },
                    "result": {"disponibilidade": "indisponivel"},
                },
                {
                    "name": "confirmar_agendamento",
                    "result": {"id": "appointment-2"},
                },
            ],
            "structured_response": {
                "resultado": {"status": "informacao_insuficiente"},
            },
            "error_class": None,
        },
    )
