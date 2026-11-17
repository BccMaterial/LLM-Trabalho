def test_admin_can_access_session_context(create_user, login_as_user):
    target = create_user(email="target@clinica.example")
    admin = create_user(type="admin", email="admin@clinica.example")
    target_client = login_as_user(target)
    target_session_id = target_client.get("/api/sessions").get_json()["session_id"]
    client = login_as_user(admin)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == admin["id"]
    context_response = client.get(f"/api/sessions/{target_session_id}")
    assert context_response.status_code == 200
    assert context_response.get_json()["user"]["id"] == target["id"]
