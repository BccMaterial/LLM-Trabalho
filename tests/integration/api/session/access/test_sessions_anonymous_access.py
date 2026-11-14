def test_session_route_rejects_anonymous_invalid_and_token_authentication(
    application,
    client,
):
    unauthenticated_client = application.test_client()

    assert unauthenticated_client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions").status_code == 401

    invalid_cookie_client = application.test_client()
    invalid_cookie_client.set_cookie("session_id", "not-a-session-token")
    assert invalid_cookie_client.get("/api/sessions").status_code == 401
