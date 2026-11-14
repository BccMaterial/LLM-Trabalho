def test_patient_can_access_own_session(create_user, login_as_user):
    user = create_user(type="patient", email="patient@example.test")
    client = login_as_user(user)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == user["id"]
