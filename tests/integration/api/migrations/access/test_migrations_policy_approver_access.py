def test_policy_approver_cannot_access_migrations(
    migration_client,
    login_as_user,
):
    assert migration_client.post("/api/migrations").status_code == 200
    response = migration_client.post(
        "/api/users",
        json={
            "nome": "Aprovador de políticas",
            "username": "migration-policy-approver",
            "cpf": "12345678901",
            "type": "policy_approver",
            "email": "migration-policy-approver@clinica.example",
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    policy_approver = response.get_json()
    session_client = login_as_user(policy_approver)

    assert session_client.get("/api/migrations").status_code == 403
    assert session_client.post("/api/migrations").status_code == 403
