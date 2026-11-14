def test_list_appointments_supports_patient_and_professional_filters(
    client, create_appointment
):
    appointment = create_appointment()

    assert client.get("/api/appointments").get_json()["total_items"] == 1
    assert (
        client.get(
            f"/api/appointments?patient_id={appointment['patient_id']}"
        ).get_json()["total_items"]
        == 1
    )
    assert (
        client.get(
            f"/api/appointments?professional_id={appointment['professional_id']}"
        ).get_json()["total_items"]
        == 1
    )
