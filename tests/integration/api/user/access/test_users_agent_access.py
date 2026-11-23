def test_agent_cannot_access_patient_user_records(
    create_user,
    login_as_user,
):
    agent = create_user(type="agent", email="agent@clinica.example")
    target = create_user()
    session_client = login_as_user(agent)

    assert session_client.get("/api/users").status_code == 403
    assert session_client.get(f"/api/users/{target['id']}").status_code == 403
    assert session_client.post("/api/users", json={}).status_code == 403
    assert (
        session_client.patch(
            f"/api/users/{agent['id']}",
            json={"nome": "Alteração indevida"},
        ).status_code
        == 403
    )
    assert session_client.delete(f"/api/users/{target['id']}").status_code == 403
