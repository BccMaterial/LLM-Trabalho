def test_agent_can_read_and_write_appointments(
    client, create_appointment, create_user, login_as_user
):
    appointment = create_appointment()
    agent = create_user("agent")
    session_client = login_as_user(agent)

    assert session_client.get("/api/appointments").status_code == 200
    assert (
        session_client.patch(
            f"/api/appointments/{appointment['id']}",
            json={"status": "Concluído"},
        ).status_code
        == 200
    )
    assert (
        session_client.delete(f"/api/appointments/{appointment['id']}").status_code
        == 200
    )
