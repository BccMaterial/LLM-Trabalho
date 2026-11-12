from uuid import UUID, uuid4

import pytest


def test_patch_updates_name_and_deactivation_cancels_appointments(
    client, create_professional, create_appointments_table, appointment_statuses
):
    professional = create_professional()
    professional_id = UUID(professional["id"])
    appointments = create_appointments_table(professional_id)

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
    assert appointment_statuses(appointments) == ["cancelado", "cancelado"]

    reactivation = client.patch(
        f"/api/professionals/{professional['id']}",
        json={"status": True},
    )
    assert reactivation.status_code == 200
    assert reactivation.get_json()["status"] is True


def test_patch_rejects_invalid_data_and_missing_professional(
    client, create_professional
):
    professional = create_professional()

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
def test_patch_rejects_duplicate_professional_identity(
    client, create_professional, field
):
    first = create_professional()
    second = create_professional()

    response = client.patch(
        f"/api/professionals/{second['id']}",
        json={field: first[field]},
    )

    assert response.status_code == 409
    persisted = client.get(f"/api/professionals/{second['id']}")
    assert persisted.get_json()[field] == second[field]
