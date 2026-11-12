from uuid import UUID


def test_delete_deactivates_and_cancels_appointments(
    client, create_professional, create_appointments_table, appointment_statuses
):
    professional = create_professional()
    professional_id = UUID(professional["id"])
    appointments = create_appointments_table(professional_id)

    response = client.delete(f"/api/professionals/{professional['id']}")

    assert response.status_code == 200
    assert response.get_json()["id"] == professional["id"]
    assert response.get_json()["status"] is False
    assert appointment_statuses(appointments) == ["cancelado", "cancelado"]

    persisted = client.get(f"/api/professionals/{professional['id']}")
    assert persisted.status_code == 200
    assert persisted.get_json()["status"] is False


def test_delete_succeeds_before_appointments_table_exists(client, create_professional):
    professional = create_professional()

    response = client.delete(f"/api/professionals/{professional['id']}")

    assert response.status_code == 200
    assert response.get_json()["status"] is False
