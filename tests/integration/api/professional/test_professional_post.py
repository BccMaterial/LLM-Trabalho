from uuid import UUID

import pytest


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


def test_create_professional_rejects_duplicate_email_or_cpf(
    client, create_professional
):
    existing = create_professional()
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
