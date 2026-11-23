def test_patient_can_only_read_own_appointments(
    client, create_appointment, create_user, login_as_user
):
    patient = create_user()
    other_patient = create_user()
    own = create_appointment(patient=patient)
    other = create_appointment(patient=other_patient)
    session_client = login_as_user(patient)

    own_response = session_client.get(f"/api/appointments?patient_id={patient['id']}")
    other_response = session_client.get(
        f"/api/appointments?patient_id={other['patient_id']}"
    )

    assert own_response.status_code == 200
    assert [item["id"] for item in own_response.get_json()["value"]] == [own["id"]]
    assert other_response.status_code == 403
    assert (
        session_client.get(
            "/api/appointments/availability",
            query_string={
                "professional_id": own["professional_id"],
                "agenda_inicio": own["agenda_inicio"],
                "agenda_fim": own["agenda_fim"],
            },
        ).status_code
        == 403
    )
    own_booking = session_client.post(
        "/api/appointments",
        json={
            "patient_id": patient["id"],
            "professional_id": own["professional_id"],
            "agenda_inicio": "2026-12-01T12:00:00+00:00",
            "agenda_fim": "2026-12-01T13:00:00+00:00",
            "suspeita_paciente": "Avaliação inicial",
        },
    )
    other_booking = session_client.post(
        "/api/appointments",
        json={
            "patient_id": other_patient["id"],
            "professional_id": own["professional_id"],
            "agenda_inicio": "2026-12-01T13:00:00+00:00",
            "agenda_fim": "2026-12-01T14:00:00+00:00",
            "suspeita_paciente": "Avaliação inicial",
        },
    )
    assert own_booking.status_code == 201
    assert other_booking.status_code == 403
