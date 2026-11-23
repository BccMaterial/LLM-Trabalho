def test_agent_can_only_read_minimized_active_professionals(
    create_user,
    create_professional,
    login_as_user,
):
    agent = create_user(type="agent", email="agent@clinica.example")
    professional = create_professional()
    session_client = login_as_user(agent)

    full_list = session_client.get("/api/professionals")
    minimized_list = session_client.get("/api/professionals/active")
    details = session_client.get(f"/api/professionals/{professional['id']}")

    assert full_list.status_code == 403
    assert minimized_list.status_code == 200
    assert minimized_list.get_json()["value"] == [
        {"id": professional["id"], "nome": professional["nome"]}
    ]
    assert details.status_code == 403
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
            json={"nome": "Profissional atualizado"},
        ).status_code
        == 403
    )
    assert (
        session_client.delete(f"/api/professionals/{professional['id']}").status_code
        == 403
    )
