def test_policy_approver_can_access_own_session(create_user, login_as_user):
    user = create_user(
        type="policy_approver",
        email="policy-approver@clinica.example",
    )
    client = login_as_user(user)

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == user["id"]
