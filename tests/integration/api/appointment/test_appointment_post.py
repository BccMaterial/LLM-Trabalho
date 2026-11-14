def test_create_appointment_defaults_to_pending(client, create_appointment):
    appointment = create_appointment()

    assert appointment["status"] == "Pendente"


def test_pending_appointment_conflicts_by_professional_or_patient(
    client, create_appointment, create_user, create_professional
):
    patient = create_user()
    professional = create_professional()
    create_appointment(patient=patient, professional=professional)

    same_professional = client.post(
        "/api/appointments",
        json={
            "patient_id": create_user()["id"],
            "professional_id": professional["id"],
            "agenda_inicio": "2026-12-01T10:30:00+00:00",
            "agenda_fim": "2026-12-01T11:30:00+00:00",
            "suspeita_paciente": "Conflito",
        },
    )
    same_patient = client.post(
        "/api/appointments",
        json={
            "patient_id": patient["id"],
            "professional_id": create_professional()["id"],
            "agenda_inicio": "2026-12-01T10:30:00+00:00",
            "agenda_fim": "2026-12-01T11:30:00+00:00",
            "suspeita_paciente": "Conflito",
        },
    )

    assert same_professional.status_code == 409
    assert same_patient.status_code == 409


def test_non_pending_appointment_does_not_conflict(client, create_appointment):
    appointment = create_appointment(status="Concluído")
    response = client.post(
        "/api/appointments",
        json={
            "patient_id": appointment["patient_id"],
            "professional_id": appointment["professional_id"],
            "agenda_inicio": "2026-12-01T10:30:00+00:00",
            "agenda_fim": "2026-12-01T11:30:00+00:00",
            "suspeita_paciente": "Novo horário",
        },
    )

    assert response.status_code == 201
