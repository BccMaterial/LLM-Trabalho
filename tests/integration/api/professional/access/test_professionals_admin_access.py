def test_admin_session_can_use_professional_routes(
    create_user,
    create_professional,
    login_as_user,
):
    admin = create_user(type="admin", email="admin@clinica.example")
    professional = create_professional()
    session_client = login_as_user(admin)

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


def test_admin_api_token_can_use_professional_routes(client):
    assert client.get("/api/professionals").status_code == 200
    response = client.post(
        "/api/professionals",
        json={
            "nome": "Profissional via token",
            "email": "admin-token@example.test",
            "cpf": "98765432109",
        },
    )
    assert response.status_code == 201
