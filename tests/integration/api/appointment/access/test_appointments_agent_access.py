def test_agent_only_gets_minimized_availability_not_appointment_records(
    client, create_appointment, create_user, login_as_user
):
    appointment = create_appointment()
    agent = create_user("agent")
    session_client = login_as_user(agent)

    assert session_client.get("/api/appointments").status_code == 403
    response = session_client.get(
        "/api/appointments/availability",
        query_string={
            "professional_id": appointment["professional_id"],
            "agenda_inicio": "2026-12-01T10:00:00+00:00",
            "agenda_fim": "2026-12-01T11:00:00+00:00",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {"disponibilidade": "indisponivel"}
    assert appointment["patient_id"] not in response.get_data(as_text=True)
    assert "suspeita_paciente" not in response.get_data(as_text=True)

    assert (
        session_client.patch(
            f"/api/appointments/{appointment['id']}",
            json={"status": "Concluído"},
        ).status_code
        == 403
    )
    assert (
        session_client.delete(f"/api/appointments/{appointment['id']}").status_code
        == 403
    )


def test_agent_cannot_create_appointments(
    client, create_appointment, create_user, login_as_user
):
    appointment = create_appointment()
    agent = create_user("agent")
    session_client = login_as_user(agent)

    response = session_client.post(
        "/api/appointments",
        json={
            "patient_id": appointment["patient_id"],
            "professional_id": appointment["professional_id"],
            "agenda_inicio": "2026-12-01T12:00:00+00:00",
            "agenda_fim": "2026-12-01T13:00:00+00:00",
            "suspeita_paciente": "Avaliação inicial",
        },
    )

    assert response.status_code == 403
