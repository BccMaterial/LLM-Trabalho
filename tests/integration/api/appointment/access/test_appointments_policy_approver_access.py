def test_policy_approver_can_read_all_but_cannot_write(
    client, create_appointment, create_user, login_as_user
):
    create_appointment()
    approver = create_user("policy_approver")
    session_client = login_as_user(approver)

    assert session_client.get("/api/appointments").status_code == 200
    assert session_client.post("/api/appointments", json={}).status_code == 403
