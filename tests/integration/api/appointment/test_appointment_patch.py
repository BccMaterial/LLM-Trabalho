def test_update_appointment_changes_status(client, create_appointment):
    appointment = create_appointment()

    response = client.patch(
        f"/api/appointments/{appointment['id']}",
        json={"status": "Concluído"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "Concluído"


def test_update_pending_appointment_conflicts_by_professional(
    client, create_appointment
):
    existing = create_appointment()
    updated = create_appointment()

    response = client.patch(
        f"/api/appointments/{updated['id']}",
        json={
            "professional_id": existing["professional_id"],
            "agenda_inicio": "2026-12-01T10:30:00+00:00",
            "agenda_fim": "2026-12-01T11:30:00+00:00",
        },
    )

    assert response.status_code == 409


def test_update_pending_appointment_conflicts_by_patient(client, create_appointment):
    existing = create_appointment()
    updated = create_appointment()

    response = client.patch(
        f"/api/appointments/{updated['id']}",
        json={
            "patient_id": existing["patient_id"],
            "agenda_inicio": "2026-12-01T10:30:00+00:00",
            "agenda_fim": "2026-12-01T11:30:00+00:00",
        },
    )

    assert response.status_code == 409


def test_update_to_non_pending_status_does_not_conflict(client, create_appointment):
    existing = create_appointment()
    updated = create_appointment()

    response = client.patch(
        f"/api/appointments/{updated['id']}",
        json={
            "professional_id": existing["professional_id"],
            "patient_id": existing["patient_id"],
            "agenda_inicio": "2026-12-01T10:30:00+00:00",
            "agenda_fim": "2026-12-01T11:30:00+00:00",
            "status": "Concluído",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "Concluído"


def test_update_to_adjacent_pending_interval_does_not_conflict(
    client, create_appointment
):
    existing = create_appointment()
    updated = create_appointment()

    response = client.patch(
        f"/api/appointments/{updated['id']}",
        json={
            "professional_id": existing["professional_id"],
            "patient_id": existing["patient_id"],
            "agenda_inicio": "2026-12-01T11:00:00+00:00",
            "agenda_fim": "2026-12-01T12:00:00+00:00",
        },
    )

    assert response.status_code == 200
