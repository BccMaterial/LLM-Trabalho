from uuid import uuid4

import pytest

from api.app import create_app


@pytest.fixture
def application(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'appointments.db'}"
    monkeypatch.setenv("PASSWORD_PEPPER", "test-password-pepper")
    monkeypatch.setenv("CORPORATE_EMAIL_DOMAINS", "clinica.example")
    app = create_app(database_url=database_url)
    app.config["ADMIN_API_TOKEN"] = "test-admin-api-token"
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
def create_user(client):
    sequence = 0

    def create(user_type="patient"):
        nonlocal sequence
        sequence += 1
        response = client.post(
            "/api/users",
            json={
                "nome": f"Usuário {sequence}",
                "username": f"appointment-user-{sequence}",
                "cpf": f"{sequence:011d}",
                "type": user_type,
                "email": f"appointment-user-{sequence}@clinica.example",
                "password": "senha-segura-123",
            },
        )
        assert response.status_code == 201
        return response.get_json()

    return create


@pytest.fixture
def create_professional(client):
    def create():
        identifier = uuid4()
        response = client.post(
            "/api/professionals",
            json={
                "nome": "Dra. Ana",
                "email": f"{identifier.hex}@example.test",
                "cpf": f"{identifier.int % 10**11:011d}",
            },
        )
        assert response.status_code == 201
        return response.get_json()

    return create


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
def create_appointment(client, create_user, create_professional):
    def create(**overrides):
        patient = overrides.pop("patient", None) or create_user()
        professional = overrides.pop("professional", None) or create_professional()
        payload = {
            "patient_id": patient["id"],
            "professional_id": professional["id"],
            "agenda_inicio": "2026-12-01T10:00:00+00:00",
            "agenda_fim": "2026-12-01T11:00:00+00:00",
            "suspeita_paciente": "Avaliação inicial",
        }
        payload.update(overrides)
        response = client.post("/api/appointments", json=payload)
        assert response.status_code == 201
        return response.get_json()

    return create
