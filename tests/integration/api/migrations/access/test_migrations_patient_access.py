def test_patient_cannot_access_migrations(
    migration_client,
    login_as_user,
):
    assert migration_client.post("/api/migrations").status_code == 200
    response = migration_client.post(
        "/api/users",
        json={
            "nome": "Paciente",
            "username": "migration-patient",
            "cpf": "12345678901",
            "type": "patient",
            "email": "migration-patient@example.test",
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    patient = response.get_json()
    session_client = login_as_user(patient)

    assert session_client.get("/api/migrations").status_code == 403
    assert session_client.post("/api/migrations").status_code == 403
