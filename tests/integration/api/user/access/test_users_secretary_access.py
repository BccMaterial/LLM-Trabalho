def test_secretary_cannot_manage_users_and_can_update_permitted_self_fields(
    create_user,
    login_as_user,
):
    secretary = create_user(
        type="secretary",
        email="secretary@clinica.example",
    )
    other_user = create_user()
    session_client = login_as_user(secretary)

    assert session_client.post("/api/users", json={}).status_code == 403
    assert session_client.get("/api/users").status_code == 403
    assert session_client.get(f"/api/users/{secretary['id']}").status_code == 403
    assert session_client.delete(f"/api/users/{secretary['id']}").status_code == 403
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
            f"/api/users/{secretary['id']}",
            json={"nome": "Nome atualizado"},
        ).status_code
        == 200
    )
    assert (
        session_client.patch(
            f"/api/users/{secretary['id']}",
            json={"type": "admin"},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{secretary['id']}",
            json={"status": False},
        ).status_code
        == 403
    )
