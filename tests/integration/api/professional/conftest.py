from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, Uuid, select

from api.app import create_app


@pytest.fixture
def application(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'professionals.db'}"
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
def create_appointments_table(application):
    def create(professional_id: UUID):
        engine = application.extensions["database_connector"].engine
        metadata = MetaData()
        Table(
            "professionals",
            metadata,
            Column("id", Uuid(as_uuid=True), primary_key=True),
        )
        appointments = Table(
            "appointments",
            metadata,
            Column("id", Uuid(as_uuid=True), primary_key=True),
            Column(
                "id_profissional",
                Uuid(as_uuid=True),
                ForeignKey("professionals.id"),
                nullable=False,
            ),
            Column("status", String, nullable=False),
        )
        metadata.create_all(engine)

        with engine.begin() as connection:
            connection.execute(
                appointments.insert(),
                [
                    {
                        "id": uuid4(),
                        "id_profissional": professional_id,
                        "status": "agendado",
                    },
                    {
                        "id": uuid4(),
                        "id_profissional": professional_id,
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
