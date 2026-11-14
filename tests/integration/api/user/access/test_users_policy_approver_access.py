def test_policy_approver_cannot_manage_users_and_can_update_permitted_self_fields(
    create_user,
    login_as_user,
):
    policy_approver = create_user(
        type="policy_approver",
        email="policy-approver@clinica.example",
    )
    other_user = create_user()
    session_client = login_as_user(policy_approver)

    assert session_client.post("/api/users", json={}).status_code == 403
    assert session_client.get("/api/users").status_code == 403
    assert session_client.get(f"/api/users/{policy_approver['id']}").status_code == 403
    assert (
        session_client.delete(f"/api/users/{policy_approver['id']}").status_code == 403
    )
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
            f"/api/users/{policy_approver['id']}",
            json={"nome": "Nome atualizado"},
        ).status_code
        == 200
    )
    assert (
        session_client.patch(
            f"/api/users/{policy_approver['id']}",
            json={"type": "admin"},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{policy_approver['id']}",
            json={"status": False},
        ).status_code
        == 403
    )
