from uuid import UUID

import pytest
from sqlalchemy import select

from api.models.user import User
from api.services.user_password_service import verify_password


def _stored_user(client, user_id):
    with client.application.extensions["database_connector"].session() as session:
        return session.scalar(select(User).where(User.id == UUID(user_id)))


def test_create_user_defaults_to_active_and_never_exposes_password_or_hash(client):
    response = client.post(
        "/api/users",
        json={
            "nome": " Ana ",
            "username": " ana ",
            "cpf": "12345678901",
            "type": "patient",
            "email": " ANA@EXAMPLE.TEST ",
            "password": "senha-segura-123",
        },
    )

    assert response.status_code == 201
    data = response.get_json()
    assert UUID(data["id"]).version == 4
    assert data["nome"] == "Ana"
    assert data["username"] == "ana"
    assert data["email"] == "ana@example.test"
    assert data["status"] is True
    assert data["created_at"].endswith("+00:00")
    assert data["updated_at"].endswith("+00:00")
    assert "password" not in data
    assert "password_hash" not in data

    user = _stored_user(client, data["id"])
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(
        "senha-segura-123",
        user.password_hash,
        client.application.config["PASSWORD_PEPPER"],
    )
    assert not verify_password(
        "senha-incorreta",
        user.password_hash,
        client.application.config["PASSWORD_PEPPER"],
    )
    assert not verify_password(
        "senha-segura-123",
        user.password_hash,
        "a-different-pepper",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"nome": " ", "username": "ana"},
        {"nome": "Ana", "username": " "},
        {"nome": "Ana", "username": "ana", "cpf": "123.456.789-01"},
        {"nome": "Ana", "username": "ana", "type": "unknown"},
        {"nome": "Ana", "username": "ana", "password": ""},
        {"nome": "Ana", "username": "ana", "unknown": "value"},
    ],
)
def test_create_user_rejects_invalid_data(client, payload):
    response = client.post("/api/users", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid user data"


def test_password_operations_require_configured_pepper(client):
    client.application.config["PASSWORD_PEPPER"] = None

    response = client.post(
        "/api/users",
        json={
            "nome": "Ana",
            "username": "ana",
            "cpf": "12345678901",
            "type": "patient",
            "email": "ana@example.test",
            "password": "senha-segura-123",
        },
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "Password hashing is not configured"


def test_password_hashes_use_distinct_argon2_salts(client, create_user):
    first = create_user(password="senha-identica")
    second = create_user(password="senha-identica")

    first_user = _stored_user(client, first["id"])
    second_user = _stored_user(client, second["id"])

    assert first_user is not None
    assert second_user is not None
    assert first_user.password_hash.startswith("$argon2id$")
    assert second_user.password_hash.startswith("$argon2id$")
    assert first_user.password_hash != second_user.password_hash


def test_create_non_patient_requires_an_exact_configured_corporate_domain(client):
    accepted = client.post(
        "/api/users",
        json={
            "nome": "Gestora",
            "username": "gestora",
            "cpf": "12345678901",
            "type": "manager",
            "email": "GESTORA@CLINICA.EXAMPLE",
            "password": "senha-segura-123",
        },
    )
    rejected = client.post(
        "/api/users",
        json={
            "nome": "Outra gestora",
            "username": "outra-gestora",
            "cpf": "12345678902",
            "type": "manager",
            "email": "gestora@clinica.example.attacker.test",
            "password": "senha-segura-123",
        },
    )

    assert accepted.status_code == 201
    assert accepted.get_json()["email"] == "gestora@clinica.example"
    assert rejected.status_code == 400
    assert rejected.get_json()["error"] == "Invalid corporate email"


def test_non_patient_requires_domains_to_be_configured(client):
    client.application.config["CORPORATE_EMAIL_DOMAINS"] = ""
    response = client.post(
        "/api/users",
        json={
            "nome": "Gestora",
            "username": "gestora",
            "cpf": "12345678901",
            "type": "manager",
            "email": "gestora@clinica.example",
            "password": "senha-segura-123",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid corporate email"


def test_list_users_can_filter_by_username_and_get_user_by_id(client, create_user):
    created = create_user(username="ana")
    create_user(username="bruno")

    filtered = client.get("/api/users?username=ana")
    listed = client.get("/api/users")
    fetched = client.get(f"/api/users/{created['id']}")

    assert filtered.status_code == 200
    assert [user["username"] for user in filtered.get_json()["value"]] == ["ana"]
    assert listed.status_code == 200
    assert listed.get_json()["total_items"] == 2
    assert fetched.status_code == 200
    assert fetched.get_json()["id"] == created["id"]
    assert "password_hash" not in fetched.get_json()


def test_update_user_changes_fields_and_resets_password(client, create_user):
    created = create_user()

    response = client.patch(
        f"/api/users/{created['id']}",
        json={
            "nome": "Nome atualizado",
            "type": "manager",
            "email": "manager@grupo.example",
            "status": False,
            "password": "nova-senha-456",
        },
    )

    assert response.status_code == 200
    updated = response.get_json()
    assert updated["nome"] == "Nome atualizado"
    assert updated["type"] == "manager"
    assert updated["email"] == "manager@grupo.example"
    assert updated["status"] is False
    assert "password" not in updated
    assert "password_hash" not in updated

    user = _stored_user(client, created["id"])
    assert user is not None
    assert verify_password(
        "nova-senha-456",
        user.password_hash,
        client.application.config["PASSWORD_PEPPER"],
    )
    assert not verify_password(
        "senha-segura-123",
        user.password_hash,
        client.application.config["PASSWORD_PEPPER"],
    )


def test_update_non_patient_requires_valid_effective_domain(client, create_user):
    created = create_user()

    response = client.patch(
        f"/api/users/{created['id']}",
        json={"type": "secretary"},
    )

    assert response.status_code == 400
    assert client.get(f"/api/users/{created['id']}").get_json()["type"] == "patient"


def test_password_reset_requires_configured_pepper(client, create_user):
    created = create_user()
    existing_hash = _stored_user(client, created["id"]).password_hash
    client.application.config["PASSWORD_PEPPER"] = None

    response = client.patch(
        f"/api/users/{created['id']}",
        json={"password": "nova-senha-456"},
    )

    assert response.status_code == 503
    assert _stored_user(client, created["id"]).password_hash == existing_hash


@pytest.mark.parametrize("unique_field", ["username", "cpf", "email"])
def test_create_user_rejects_duplicate_identity(client, create_user, unique_field):
    existing = create_user()
    duplicate = {
        "nome": "Duplicado",
        "username": "new-username",
        "cpf": "98765432100",
        "type": "patient",
        "email": "new@example.test",
        "password": "senha-segura-123",
    }
    duplicate[unique_field] = existing[unique_field]

    response = client.post("/api/users", json=duplicate)

    assert response.status_code == 409


@pytest.mark.parametrize("unique_field", ["username", "cpf", "email"])
def test_update_user_rejects_duplicate_identity(client, create_user, unique_field):
    existing = create_user()
    target = create_user()

    response = client.patch(
        f"/api/users/{target['id']}",
        json={unique_field: existing[unique_field]},
    )

    assert response.status_code == 409


def test_delete_deactivates_user_without_removing_it(client, create_user):
    created = create_user()

    response = client.delete(f"/api/users/{created['id']}")
    fetched = client.get(f"/api/users/{created['id']}")

    assert response.status_code == 200
    assert response.get_json()["status"] is False
    assert fetched.status_code == 200
    assert fetched.get_json()["status"] is False


def test_users_routes_are_callable_without_authentication(client, create_user):
    created = create_user()

    assert client.get("/api/users").status_code == 200
    assert client.get(f"/api/users/{created['id']}").status_code == 200
