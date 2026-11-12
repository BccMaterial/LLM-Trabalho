from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, Uuid, select

from api.app import create_app


@pytest.fixture
def application(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'professionals.db'}"
    app = create_app(database_url=database_url)

    with app.test_client() as client:
        response = client.post("/api/migrations")
    assert response.status_code == 200

    yield app
    app.extensions["database_connector"].dispose()


@pytest.fixture
def client(application):
    return application.test_client()


def create_professional(client, nome="Dra. Ana", email=None, cpf=None):
    unique_id = uuid4()
    payload = {
        "nome": nome,
        "email": email or f"{unique_id.hex}@example.test",
        "cpf": cpf or f"{unique_id.int % 10**11:011d}",
    }
    response = client.post("/api/professionals", json=payload)
    assert response.status_code == 201
    return response.get_json()


def test_create_professional_defaults_to_active_with_uuid_and_timestamps(client):
    response = client.post(
        "/api/professionals",
        json={
            "nome": "Dra. Ana",
            "email": "  ANA@EXAMPLE.TEST ",
            "cpf": "12345678901",
        },
    )

    assert response.status_code == 201
    professional = response.get_json()
    assert UUID(professional["id"]).version == 4
    assert professional["nome"] == "Dra. Ana"
    assert professional["email"] == "ana@example.test"
    assert professional["cpf"] == "12345678901"
    assert professional["status"] is True
    assert professional["created_at"].endswith("+00:00")
    assert professional["updated_at"].endswith("+00:00")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"nome": "Dra. Ana"},
        {"nome": "  ", "email": "ana@example.test", "cpf": "12345678901"},
        {"nome": "Dra. Ana", "email": "invalid", "cpf": "12345678901"},
        {
            "nome": "Dra. Ana",
            "email": "ana@example.test",
            "cpf": "123.456.789-01",
        },
        {"nome": "Dra. Ana", "email": "ana@example.test", "cpf": 12345678901},
        {
            "nome": "Dra. Ana",
            "email": "ana@example.test",
            "cpf": "12345678901",
            "status": False,
        },
        {
            "nome": "Dra. Ana",
            "email": "ana@example.test",
            "cpf": "12345678901",
            "unknown": "value",
        },
    ],
)
def test_create_professional_rejects_invalid_data(client, payload):
    response = client.post("/api/professionals", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Invalid professional data",
        "status_code": 400,
        "action": "Provide a name, a valid email address, and an unmasked 11-digit CPF.",
    }


def test_create_professional_rejects_duplicate_email_or_cpf(client):
    existing = create_professional(client)
    duplicate_email = client.post(
        "/api/professionals",
        json={
            "nome": "Dr. Bruno",
            "email": existing["email"].upper(),
            "cpf": "98765432100",
        },
    )
    duplicate_cpf = client.post(
        "/api/professionals",
        json={
            "nome": "Dra. Bia",
            "email": "bia@example.test",
            "cpf": existing["cpf"],
        },
    )

    assert duplicate_email.status_code == 409
    assert duplicate_cpf.status_code == 409
    assert duplicate_email.get_json()["status_code"] == 409


def test_get_professional_and_missing_professional(client):
    professional = create_professional(client)

    response = client.get(f"/api/professionals/{professional['id']}")
    missing_response = client.get(f"/api/professionals/{uuid4()}")
    invalid_id_response = client.get("/api/professionals/not-a-uuid")

    assert response.status_code == 200
    assert response.get_json()["id"] == professional["id"]
    assert missing_response.status_code == 404
    assert invalid_id_response.status_code == 404


def test_list_professionals_is_paginated_and_preserves_query_params(client):
    create_professional(client, "Dra. Ana")
    create_professional(client, "Dr. Bruno")

    first_page = client.get("/api/professionals?page_size=1&department=neuro")
    first_page_data = first_page.get_json()
    next_link = first_page_data["next_link"]

    assert first_page.status_code == 200
    assert set(first_page_data) == {
        "page",
        "page_size",
        "next_link",
        "value",
        "total_items",
    }
    assert first_page_data["page"] == 1
    assert first_page_data["page_size"] == 1
    assert first_page_data["total_items"] == 2
    assert len(first_page_data["value"]) == 1
    assert next_link.startswith("http://")
    assert "page=2" in next_link
    assert "page_size=1" in next_link
    assert "department=neuro" in next_link

    next_page_url = next_link.removeprefix("http://localhost")
    second_page = client.get(next_page_url)
    second_page_data = second_page.get_json()

    assert second_page.status_code == 200
    assert second_page_data["page"] == 2
    assert second_page_data["value"][0]["nome"] == "Dr. Bruno"
    assert second_page_data["next_link"] is None


def test_list_professionals_includes_inactive_and_empty_out_of_range_page(client):
    professional = create_professional(client)
    deactivation = client.delete(f"/api/professionals/{professional['id']}")

    response = client.get("/api/professionals?page=5&page_size=1")
    page_data = response.get_json()

    assert deactivation.status_code == 200
    assert deactivation.get_json()["status"] is False
    assert response.status_code == 200
    assert page_data["total_items"] == 1
    assert page_data["value"] == []
    assert page_data["next_link"] is None


@pytest.mark.parametrize("page", ["0", "-1", "invalid"])
def test_list_professionals_rejects_invalid_page(client, page):
    response = client.get(f"/api/professionals?page={page}")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Invalid page parameter",
        "status_code": 400,
        "action": "Use an integer greater than or equal to 1.",
    }


@pytest.mark.parametrize("page_size", ["0", "-1", "invalid", "501"])
def test_list_professionals_uses_default_for_invalid_page_size(client, page_size):
    response = client.get(f"/api/professionals?page_size={page_size}")

    assert response.status_code == 200
    assert response.get_json()["page_size"] == 50


def test_patch_updates_name_and_deactivation_cancels_appointments(client, application):
    professional = create_professional(client)
    professional_id = UUID(professional["id"])
    appointments = _create_appointments_table(application, professional_id)

    response = client.patch(
        f"/api/professionals/{professional['id']}",
        json={
            "nome": "Dra. Beatriz",
            "email": "BEATRIZ@EXAMPLE.TEST",
            "cpf": "98765432100",
            "status": False,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["nome"] == "Dra. Beatriz"
    assert response.get_json()["email"] == "beatriz@example.test"
    assert response.get_json()["cpf"] == "98765432100"
    assert response.get_json()["status"] is False
    assert _appointment_statuses(application, appointments) == [
        "cancelado",
        "cancelado",
    ]

    reactivation = client.patch(
        f"/api/professionals/{professional['id']}",
        json={"status": True},
    )
    assert reactivation.status_code == 200
    assert reactivation.get_json()["status"] is True


def test_delete_deactivates_and_cancels_appointments(client, application):
    professional = create_professional(client)
    professional_id = UUID(professional["id"])
    appointments = _create_appointments_table(application, professional_id)

    response = client.delete(f"/api/professionals/{professional['id']}")

    assert response.status_code == 200
    assert response.get_json()["id"] == professional["id"]
    assert response.get_json()["status"] is False
    assert _appointment_statuses(application, appointments) == [
        "cancelado",
        "cancelado",
    ]

    persisted = client.get(f"/api/professionals/{professional['id']}")
    assert persisted.status_code == 200
    assert persisted.get_json()["status"] is False


def test_delete_succeeds_before_appointments_table_exists(client):
    professional = create_professional(client)

    response = client.delete(f"/api/professionals/{professional['id']}")

    assert response.status_code == 200
    assert response.get_json()["status"] is False


def test_patch_rejects_invalid_data_and_missing_professional(client):
    professional = create_professional(client)

    invalid_response = client.patch(
        f"/api/professionals/{professional['id']}",
        json={"status": "inactive"},
    )
    missing_response = client.patch(
        f"/api/professionals/{uuid4()}",
        json={"nome": "Dra. Bia"},
    )

    assert invalid_response.status_code == 400
    assert missing_response.status_code == 404


@pytest.mark.parametrize("field", ["email", "cpf"])
def test_patch_rejects_duplicate_professional_identity(client, field):
    first = create_professional(client)
    second = create_professional(client)

    response = client.patch(
        f"/api/professionals/{second['id']}",
        json={field: first[field]},
    )

    assert response.status_code == 409
    persisted = client.get(f"/api/professionals/{second['id']}")
    assert persisted.get_json()[field] == second[field]


def _create_appointments_table(application, professional_id: UUID):
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


def _appointment_statuses(application, appointments: Table) -> list[str]:
    engine = application.extensions["database_connector"].engine
    with engine.connect() as connection:
        return list(
            connection.scalars(
                select(appointments.c.status).order_by(appointments.c.id)
            )
        )
