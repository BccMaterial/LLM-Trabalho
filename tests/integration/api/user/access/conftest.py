import pytest


@pytest.fixture
def login_as_user(client):
    def login(user):
        session_client = client.application.test_client()
        response = session_client.post(
            "/api/sessions",
            json={"email": user["email"], "password": "senha-segura-123"},
        )
        assert response.status_code == 200
        return session_client

    return login


@pytest.fixture
def assert_non_admin_user_access(create_user, login_as_user):
    def assert_access(user_type):
        email = (
            f"{user_type}@clinica.example"
            if user_type != "patient"
            else f"{user_type}@example.test"
        )
        user = create_user(type=user_type, email=email)
        other_user = create_user()
        session_client = login_as_user(user)

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
        assert (
            session_client.delete(f"/api/users/{other_user['id']}").status_code == 403
        )
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

    return assert_access
