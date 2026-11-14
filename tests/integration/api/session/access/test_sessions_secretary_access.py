def test_secretary_can_access_own_session(create_user, login_as_user):
    user = create_user(type="secretary", email="secretary@clinica.example")
    client = login_as_user(user)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == user["id"]
