def _login(client, user):
    return client.post(
        "/api/sessions",
        json={"email": user["email"], "password": "senha-segura-123"},
    )


def test_current_session_requires_a_valid_session_cookie(
    application, client, create_user, unauthenticated_client
):
    assert unauthenticated_client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions").status_code == 401

    invalid_cookie_client = application.test_client()
    invalid_cookie_client.set_cookie("session_id", "not-a-session-token")
    assert invalid_cookie_client.get("/api/sessions").status_code == 401

    user = create_user()
    session_client = application.test_client()
    assert _login(session_client, user).status_code == 200
    assert session_client.get("/api/sessions").status_code == 200
