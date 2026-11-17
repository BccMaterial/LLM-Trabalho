def test_agent_can_read_and_manage_professionals(
    create_user,
    create_professional,
    login_as_user,
):
    agent = create_user(type="agent", email="agent@clinica.example")
    professional = create_professional()
    session_client = login_as_user(agent)

    assert session_client.get("/api/professionals").status_code == 200
    assert (
        session_client.get(f"/api/professionals/{professional['id']}").status_code
        == 200
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
        == 201
    )
    assert (
        session_client.patch(
            f"/api/professionals/{professional['id']}",
            json={"nome": "Profissional atualizado"},
        ).status_code
        == 200
    )
    assert (
        session_client.delete(f"/api/professionals/{professional['id']}").status_code
        == 200
    )
