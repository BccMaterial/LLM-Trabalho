def test_admin_session_and_api_token_can_access_migrations(
    create_migration_user,
    login_migration_user,
    migration_admin_client,
):
    admin = create_migration_user("admin")
    session_client = login_migration_user(admin)

    assert session_client.get("/api/migrations").status_code == 200
    assert session_client.post("/api/migrations").status_code == 200
    assert migration_admin_client.get("/api/migrations").status_code == 200
    assert migration_admin_client.post("/api/migrations").status_code == 200
