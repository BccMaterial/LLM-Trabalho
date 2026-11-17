def test_agent_cannot_access_migrations(
    migration_client,
    login_as_user,
):
    assert migration_client.post("/api/migrations").status_code == 200
    response = migration_client.post(
        "/api/users",
        json={
            "nome": "Agente",
            "username": "migration-agent",
            "cpf": "12345678901",
            "type": "agent",
            "email": "migration-agent@clinica.example",
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    agent = response.get_json()
    session_client = login_as_user(agent)

    assert session_client.get("/api/migrations").status_code == 403
    assert session_client.post("/api/migrations").status_code == 403
