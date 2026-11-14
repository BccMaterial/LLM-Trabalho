def test_migration_routes_reject_missing_or_invalid_authentication(
    migration_anonymous_client,
):
    assert migration_anonymous_client.get("/api/migrations").status_code == 401
    assert migration_anonymous_client.post("/api/migrations").status_code == 401
    assert (
        migration_anonymous_client.get(
            "/api/migrations",
            headers={"Authorization": "Bearer invalid-token"},
        ).status_code
        == 401
    )
