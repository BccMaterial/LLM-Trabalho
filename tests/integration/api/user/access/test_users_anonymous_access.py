def test_user_routes_reject_missing_or_invalid_authentication(
    client,
):
    unauthenticated_client = client.application.test_client()

    assert unauthenticated_client.get("/api/users").status_code == 401
    assert (
        unauthenticated_client.get(
            "/api/users/00000000-0000-0000-0000-000000000000"
        ).status_code
        == 401
    )
    assert (
        unauthenticated_client.get(
            "/api/users",
            headers={"Authorization": "Bearer invalid-token"},
        ).status_code
        == 401
    )
    assert unauthenticated_client.post("/api/users", json={}).status_code == 401
