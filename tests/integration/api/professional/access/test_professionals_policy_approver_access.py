def test_policy_approver_cannot_use_professional_routes(
    create_user,
    create_professional,
    login_as_user,
):
    policy_approver = create_user(
        type="policy_approver",
        email="policy-approver@clinica.example",
    )
    professional = create_professional()
    session_client = login_as_user(policy_approver)

    assert session_client.get("/api/professionals").status_code == 403
    assert (
        session_client.get(f"/api/professionals/{professional['id']}").status_code
        == 403
    )
    assert (
        session_client.post(
            "/api/professionals",
            json={
                "nome": "Novo profissional",
                "email": "novo-profissional@example.test",
                "cpf": "98765432109",
            },
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/professionals/{professional['id']}",
            json={"nome": "Alteração indevida"},
        ).status_code
        == 403
    )
    assert (
        session_client.delete(f"/api/professionals/{professional['id']}").status_code
        == 403
    )
