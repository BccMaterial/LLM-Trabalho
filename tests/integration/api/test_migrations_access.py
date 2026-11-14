from uuid import uuid4

import pytest

from api.app import create_app


@pytest.fixture
def access_context(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migration_access.db'}"
    monkeypatch.setenv("PASSWORD_PEPPER", "test-password-pepper")
    monkeypatch.setenv("CORPORATE_EMAIL_DOMAINS", "clinica.example")
    app = create_app(database_url=database_url)
    app.config["ADMIN_API_TOKEN"] = "test-admin-api-token"
    app.config["SESSION_COOKIE_SECURE"] = False

    admin_api_client = app.test_client()
    admin_api_client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
    migration_response = admin_api_client.post("/api/migrations")
    assert migration_response.status_code == 200

    yield app, admin_api_client
    app.extensions["database_connector"].dispose()


def _create_user(admin_api_client, user_type):
    username = f"migration-{user_type}"
    email = (
        f"{username}@clinica.example"
        if user_type != "patient"
        else f"{username}@example.test"
    )
    response = admin_api_client.post(
        "/api/users",
        json={
            "nome": "Usuário de teste",
            "username": username,
            "cpf": f"{uuid4().int % 10**11:011d}",
            "type": user_type,
            "email": email,
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    return response.get_json()


def _login(client, user):
    return client.post(
        "/api/sessions",
        json={"email": user["email"], "password": "senha-segura-123"},
    )


def test_migration_routes_reject_missing_and_invalid_authentication(access_context):
    app, admin_api_client = access_context
    unauthenticated_client = app.test_client()

    assert unauthenticated_client.get("/api/migrations").status_code == 401
    assert unauthenticated_client.post("/api/migrations").status_code == 401
    assert (
        unauthenticated_client.get(
            "/api/migrations",
            headers={"Authorization": "Bearer invalid-token"},
        ).status_code
        == 401
    )
    assert admin_api_client.get("/api/migrations").status_code == 200
    assert admin_api_client.post("/api/migrations").status_code == 200


@pytest.mark.parametrize(
    "user_type",
    ["patient", "manager", "secretary", "policy_approver"],
)
def test_migration_routes_reject_non_admin_sessions(access_context, user_type):
    app, admin_api_client = access_context
    user = _create_user(admin_api_client, user_type)
    session_client = app.test_client()
    assert _login(session_client, user).status_code == 200

    assert session_client.get("/api/migrations").status_code == 403
    assert session_client.post("/api/migrations").status_code == 403


def test_admin_session_can_access_migration_routes(access_context):
    app, admin_api_client = access_context
    admin = _create_user(admin_api_client, "admin")
    session_client = app.test_client()
    assert _login(session_client, admin).status_code == 200

    assert session_client.get("/api/migrations").status_code == 200
    assert session_client.post("/api/migrations").status_code == 200
