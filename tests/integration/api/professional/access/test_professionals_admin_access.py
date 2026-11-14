def test_admin_session_can_use_professional_routes(assert_professional_role_access):
    assert_professional_role_access("admin", allowed=True)


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
