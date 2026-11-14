import pytest

from api.app import create_app


@pytest.fixture
def application(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'sessions.db'}"
    monkeypatch.setenv("PASSWORD_PEPPER", "test-password-pepper")
    monkeypatch.setenv("CORPORATE_EMAIL_DOMAINS", "clinica.example")
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-api-token")
    app = create_app(database_url=database_url)
    app.config["SESSION_COOKIE_SECURE"] = False

    with app.test_client() as client:
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
        response = client.post("/api/migrations")
    assert response.status_code == 200

    yield app
    app.extensions["database_connector"].dispose()


@pytest.fixture
def client(application):
    test_client = application.test_client()
    test_client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
    return test_client


@pytest.fixture
def unauthenticated_client(application):
    return application.test_client()


@pytest.fixture
def create_user(client):
    sequence = 0

    def create(**overrides):
        nonlocal sequence
        sequence += 1
        payload = {
            "nome": f"Usuário {sequence}",
            "username": f"session-user-{sequence}",
            "cpf": f"{sequence:011d}",
            "type": "patient",
            "email": f"session-user-{sequence}@example.test",
            "password": "senha-segura-123",
        }
        payload.update(overrides)
        response = client.post("/api/users", json=payload)
        assert response.status_code == 201
        return response.get_json()

    return create
