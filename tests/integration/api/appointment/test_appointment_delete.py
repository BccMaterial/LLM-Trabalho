def test_delete_appointment_is_logical(client, create_appointment):
    appointment = create_appointment()

    response = client.delete(f"/api/appointments/{appointment['id']}")

    assert response.status_code == 200
    assert response.get_json()["status"] == "Cancelado"
    assert client.get("/api/appointments").get_json()["total_items"] == 1
