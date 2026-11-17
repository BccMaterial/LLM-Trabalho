def test_agent_can_read_session_context_and_close_own_session(
    create_user,
    login_as_user,
):
    target = create_user(email="target@clinica.example")
    agent = create_user(type="agent", email="agent@clinica.example")
    target_client = login_as_user(target)
    target_session_id = target_client.get("/api/sessions").get_json()["session_id"]
    agent_client = login_as_user(agent)

    response = agent_client.get(f"/api/sessions/{target_session_id}")

    assert response.status_code == 200
    assert response.get_json()["session_id"] == target_session_id
    assert response.get_json()["user"]["id"] == target["id"]
    assert response.get_json()["created_at"]
    assert response.get_json()["expires_at"]
    assert agent_client.get("/api/sessions").status_code == 200
    assert target_client.delete("/api/sessions").status_code == 200
    assert agent_client.get(f"/api/sessions/{target_session_id}").status_code == 404
    assert agent_client.delete("/api/sessions").status_code == 200
