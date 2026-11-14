from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import MetaData, Table, select

from api.app import create_app


@pytest.fixture
def application(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'professionals.db'}"
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
def create_professional(client):
    def create(nome="Dra. Ana", email=None, cpf=None):
        unique_id = uuid4()
        payload = {
            "nome": nome,
            "email": email or f"{unique_id.hex}@example.test",
            "cpf": cpf or f"{unique_id.int % 10**11:011d}",
        }
        response = client.post("/api/professionals", json=payload)
        assert response.status_code == 201
        return response.get_json()

    return create


@pytest.fixture
def create_user(client):
    sequence = 0

    def create(**overrides):
        nonlocal sequence
        sequence += 1
        payload = {
            "nome": f"Usuário profissional {sequence}",
            "username": f"professional-user-{sequence}",
            "cpf": f"{sequence:011d}",
            "type": "patient",
            "email": f"professional-user-{sequence}@example.test",
            "password": "senha-segura-123",
        }
        payload.update(overrides)
        response = client.post("/api/users", json=payload)
        assert response.status_code == 201
        return response.get_json()

    return create


@pytest.fixture
def create_appointments_table(application):
    def create(professional_id: UUID):
        engine = application.extensions["database_connector"].engine
        metadata = MetaData()
        users = Table("users", metadata, autoload_with=engine)
        appointments = Table("appointments", metadata, autoload_with=engine)
        metadata.create_all(engine)

        patient_id = uuid4()
        with engine.begin() as connection:
            connection.execute(
                users.insert(),
                {
                    "id": patient_id.hex,
                    "nome": "Paciente de teste",
                    "username": f"appointment-patient-{patient_id.hex}",
                    "cpf": f"{patient_id.int % 10**11:011d}",
                    "type": "patient",
                    "email": f"{patient_id.hex}@example.test",
                    "password_hash": "test",
                },
            )
            connection.execute(
                appointments.insert(),
                [
                    {
                        "id": uuid4().hex,
                        "patient_id": patient_id.hex,
                        "professional_id": professional_id.hex,
                        "agenda_inicio": datetime(2026, 12, 1, 10, tzinfo=timezone.utc),
                        "agenda_fim": datetime(2026, 12, 1, 11, tzinfo=timezone.utc),
                        "suspeita_paciente": "Teste",
                        "status": "agendado",
                    },
                    {
                        "id": uuid4().hex,
                        "patient_id": patient_id.hex,
                        "professional_id": professional_id.hex,
                        "agenda_inicio": datetime(2026, 12, 1, 11, tzinfo=timezone.utc),
                        "agenda_fim": datetime(2026, 12, 1, 12, tzinfo=timezone.utc),
                        "suspeita_paciente": "Teste",
                        "status": "confirmado",
                    },
                ],
            )
        return appointments

    return create


@pytest.fixture
def appointment_statuses(application):
    def get(appointments: Table) -> list[str]:
        engine = application.extensions["database_connector"].engine
        with engine.connect() as connection:
            return list(
                connection.scalars(
                    select(appointments.c.status).order_by(appointments.c.id)
                )
            )

    return get
