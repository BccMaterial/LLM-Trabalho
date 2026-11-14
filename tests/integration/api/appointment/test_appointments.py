def test_create_appointment_defaults_to_pending_and_lists_by_filters(
    client, create_appointment
):
    appointment = create_appointment()

    assert appointment["status"] == "Pendente"
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


def test_completed_appointment_does_not_conflict_and_delete_is_logical(
    client, create_appointment
):
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

    deleted = client.delete(f"/api/appointments/{appointment['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["status"] == "Cancelado"
    assert client.get("/api/appointments").get_json()["total_items"] == 2


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
    assert session_client.post("/api/appointments", json={}).status_code == 403


def test_policy_approver_can_read_all_but_cannot_write(
    client, create_appointment, create_user, login_as_user
):
    create_appointment()
    approver = create_user("policy_approver")
    session_client = login_as_user(approver)

    assert session_client.get("/api/appointments").status_code == 200
    assert session_client.post("/api/appointments", json={}).status_code == 403
