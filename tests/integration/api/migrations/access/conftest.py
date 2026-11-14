from uuid import uuid4

import pytest

from api.app import create_app


@pytest.fixture
def migration_application(tmp_path, monkeypatch):
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

    yield app
    app.extensions["database_connector"].dispose()


@pytest.fixture
def migration_admin_client(migration_application):
    client = migration_application.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
    return client


@pytest.fixture
def migration_anonymous_client(migration_application):
    return migration_application.test_client()


@pytest.fixture
def create_migration_user(migration_admin_client):
    def create(user_type):
        username = f"migration-{user_type}"
        email = (
            f"{username}@clinica.example"
            if user_type != "patient"
            else f"{username}@example.test"
        )
        response = migration_admin_client.post(
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

    return create


@pytest.fixture
def login_migration_user(migration_application):
    def login(user):
        client = migration_application.test_client()
        response = client.post(
            "/api/sessions",
            json={"email": user["email"], "password": "senha-segura-123"},
        )
        assert response.status_code == 200
        return client

    return login


@pytest.fixture
def assert_non_admin_migration_access(
    create_migration_user,
    login_migration_user,
):
    def assert_access(user_type):
        user = create_migration_user(user_type)
        client = login_migration_user(user)
        assert client.get("/api/migrations").status_code == 403
        assert client.post("/api/migrations").status_code == 403

    return assert_access
