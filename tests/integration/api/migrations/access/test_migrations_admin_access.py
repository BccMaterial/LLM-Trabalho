def test_admin_session_and_api_token_can_access_migrations(
    migration_client,
    login_as_user,
):
    assert migration_client.post("/api/migrations").status_code == 200
    response = migration_client.post(
        "/api/users",
        json={
            "nome": "Administrador",
            "username": "migration-admin",
            "cpf": "12345678901",
            "type": "admin",
            "email": "migration-admin@clinica.example",
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    admin = response.get_json()
    session_client = login_as_user(admin)

    assert session_client.get("/api/migrations").status_code == 200
    assert session_client.post("/api/migrations").status_code == 200
    assert migration_client.get("/api/migrations").status_code == 200
    assert migration_client.post("/api/migrations").status_code == 200
