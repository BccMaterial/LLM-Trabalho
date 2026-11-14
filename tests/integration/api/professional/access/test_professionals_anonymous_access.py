def test_professional_routes_reject_missing_or_invalid_authentication(
    application,
):
    unauthenticated_client = application.test_client()

    assert unauthenticated_client.get("/api/professionals").status_code == 401
    assert (
        unauthenticated_client.get(
            "/api/professionals",
            headers={"Authorization": "Bearer invalid-token"},
        ).status_code
        == 401
    )
    assert (
        unauthenticated_client.post(
            "/api/professionals",
            json={
                "nome": "Sem autenticação",
                "email": "unauthenticated@example.test",
                "cpf": "12345678901",
            },
        ).status_code
        == 401
    )
