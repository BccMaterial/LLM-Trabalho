def test_admin_session_can_manage_users(client, create_user, login_as_user):
    admin = create_user(type="admin", email="admin@clinica.example")
    target = create_user()
    session_client = login_as_user(admin)

    created_response = session_client.post(
        "/api/users",
        json={
            "nome": "Usuária gerenciada",
            "username": "managed-user",
            "cpf": "12345678901",
            "type": "patient",
            "email": "managed@example.test",
            "password": "senha-segura-123",
        },
    )
    assert created_response.status_code == 201
    created_user_id = created_response.get_json()["id"]
    assert session_client.get("/api/users").status_code == 200
    assert session_client.get(f"/api/users/{target['id']}").status_code == 200
    assert (
        session_client.patch(
            f"/api/users/{created_user_id}",
            json={
                "type": "manager",
                "email": "managed-manager@clinica.example",
                "status": False,
            },
        ).status_code
        == 200
    )
    assert session_client.delete(f"/api/users/{created_user_id}").status_code == 200


def test_admin_api_token_can_use_user_routes(client):
    payload = {
        "nome": "Usuário via token",
        "username": "token-user",
        "cpf": "12345678901",
        "type": "patient",
        "email": "token-user@example.test",
        "password": "senha-segura-123",
    }

    assert client.get("/api/users").status_code == 200
    assert client.post("/api/users", json=payload).status_code == 201
