def test_manager_can_access_own_session(login_session_profile):
    client, user = login_session_profile("manager")

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == user["id"]
