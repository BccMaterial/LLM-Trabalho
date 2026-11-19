import cases


def test_sanitize_redacts_sensitive_fields():
    value = {
        "password": "secret",
        "Cookie": "session=secret",
        "answer": "ok",
        "nested": {"token": "secret"},
    }

    assert cases._sanitize(value) == {
        "password": "<redacted>",
        "Cookie": "<redacted>",
        "answer": "ok",
        "nested": {"token": "<redacted>"},
    }


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


def test_case_passed_requires_a_single_completed_action_for_retry():
    assert cases._case_passed(
        6,
        {"completed_actions": {"action-key": {"id": "appointment-1"}}},
    )
