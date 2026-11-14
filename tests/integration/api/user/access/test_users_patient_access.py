def test_patient_cannot_manage_users_and_can_update_permitted_self_fields(
    create_user,
    login_as_user,
):
    patient = create_user(email="patient@example.test", type="patient")
    other_user = create_user()
    session_client = login_as_user(patient)

    assert session_client.post("/api/users", json={}).status_code == 403
    assert session_client.get("/api/users").status_code == 403
    assert session_client.get(f"/api/users/{patient['id']}").status_code == 403
    assert session_client.delete(f"/api/users/{patient['id']}").status_code == 403
    assert session_client.delete(f"/api/users/{other_user['id']}").status_code == 403
    assert (
        session_client.patch(
            f"/api/users/{other_user['id']}",
            json={"nome": "Alteração indevida"},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{patient['id']}",
            json={"nome": "Nome atualizado"},
        ).status_code
        == 200
    )
    assert (
        session_client.patch(
            f"/api/users/{patient['id']}",
            json={"type": "admin"},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{patient['id']}",
            json={"status": False},
        ).status_code
        == 403
    )
