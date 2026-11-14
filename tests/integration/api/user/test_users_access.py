import pytest


def _login(client, user):
    return client.post(
        "/api/sessions",
        json={"email": user["email"], "password": "senha-segura-123"},
    )


@pytest.mark.parametrize(
    "user_type",
    ["patient", "manager", "secretary", "policy_approver"],
)
def test_non_admin_profiles_can_only_update_permitted_self_fields(
    client, create_user, user_type
):
    user = create_user(
        type=user_type,
        email=f"{user_type}@clinica.example",
    )
    other_user = create_user()
    session_client = client.application.test_client()
    assert _login(session_client, user).status_code == 200

    assert (
        session_client.post(
            "/api/users",
            json={
                "nome": "Novo usuário",
                "username": "blocked-user",
                "cpf": "12345678901",
                "type": "patient",
                "email": "blocked@example.test",
                "password": "senha-segura-123",
            },
        ).status_code
        == 403
    )
    assert session_client.get("/api/users").status_code == 403
    assert session_client.get(f"/api/users/{user['id']}").status_code == 403
    assert session_client.delete(f"/api/users/{user['id']}").status_code == 403
    assert session_client.delete(f"/api/users/{other_user['id']}").status_code == 403
    assert (
        session_client.patch(
            f"/api/users/{other_user['id']}",
            json={"nome": "Alteração indevida"},
        ).status_code
        == 403
    )

    assert (
        session_client.patch(
            f"/api/users/{user['id']}",
            json={"nome": "Nome próprio atualizado"},
        ).status_code
        == 200
    )
    assert (
        session_client.patch(
            f"/api/users/{user['id']}",
            json={"type": "admin"},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{user['id']}",
            json={"status": False},
        ).status_code
        == 403
    )


def test_admin_session_can_use_user_management_routes(client, create_user):
    admin = create_user(type="admin", email="admin@clinica.example")
    target = create_user()
    session_client = client.application.test_client()
    assert _login(session_client, admin).status_code == 200

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


def test_user_routes_reject_missing_and_invalid_authentication(
    client, unauthenticated_client
):
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
    assert client.get("/api/users").status_code == 200
