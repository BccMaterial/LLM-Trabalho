def test_agent_can_read_and_close_own_session(create_user, login_as_user):
    agent = create_user(type="agent", email="agent@clinica.example")
    session_client = login_as_user(agent)

    response = session_client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == agent["id"]
    assert session_client.delete("/api/sessions").status_code == 200
