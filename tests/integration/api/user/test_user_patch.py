from uuid import UUID

import pytest
from sqlalchemy import select

from api.models.user import User
from api.services.user_password_service import verify_password


def _stored_user(client, user_id):
    with client.application.extensions["database_connector"].session() as session:
        return session.scalar(select(User).where(User.id == UUID(user_id)))


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
    user = _stored_user(client, created["id"])
    assert user is not None
    existing_hash = user.password_hash
    client.application.config["PASSWORD_PEPPER"] = None

    response = client.patch(
        f"/api/users/{created['id']}",
        json={"password": "nova-senha-456"},
    )

    assert response.status_code == 503
    updated_user = _stored_user(client, created["id"])
    assert updated_user is not None
    assert updated_user.password_hash == existing_hash


@pytest.mark.parametrize("unique_field", ["username", "cpf", "email"])
def test_update_user_rejects_duplicate_identity(client, create_user, unique_field):
    existing = create_user()
    target = create_user()

    response = client.patch(
        f"/api/users/{target['id']}",
        json={unique_field: existing[unique_field]},
    )

    assert response.status_code == 409
