def test_manager_can_use_professional_routes(
    create_user,
    create_professional,
    login_as_user,
):
    manager = create_user(type="manager", email="manager@clinica.example")
    professional = create_professional()
    session_client = login_as_user(manager)

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
