def test_update_appointment_changes_status(client, create_appointment):
    appointment = create_appointment()

    response = client.patch(
        f"/api/appointments/{appointment['id']}",
        json={"status": "Concluído"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "Concluído"
