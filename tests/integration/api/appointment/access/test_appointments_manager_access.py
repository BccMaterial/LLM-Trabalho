def test_manager_can_read_and_write_appointments(
    client, create_appointment, create_user, login_as_user
):
    appointment = create_appointment()
    manager = create_user("manager")
    session_client = login_as_user(manager)

    assert session_client.get("/api/appointments").status_code == 200
    assert (
        session_client.delete(f"/api/appointments/{appointment['id']}").status_code
        == 200
    )
