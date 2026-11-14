import pytest


@pytest.fixture
def login_professional_user(application):
    def login(user):
        session_client = application.test_client()
        response = session_client.post(
            "/api/sessions",
            json={"email": user["email"], "password": "senha-segura-123"},
        )
        assert response.status_code == 200
        return session_client

    return login


@pytest.fixture
def assert_professional_role_access(
    create_user,
    create_professional,
    login_professional_user,
):
    def assert_access(user_type, allowed):
        email = (
            f"{user_type}@clinica.example"
            if user_type != "patient"
            else "patient@example.test"
        )
        actor = create_user(type=user_type, email=email)
        session_client = login_professional_user(actor)
        existing = create_professional()
        professional_id = existing["id"]
        expected_status = 200 if allowed else 403

        assert session_client.get("/api/professionals").status_code == expected_status
        assert (
            session_client.get(f"/api/professionals/{professional_id}").status_code
            == expected_status
        )
        assert session_client.post(
            "/api/professionals",
            json={
                "nome": "Novo profissional",
                "email": "new-professional@example.test",
                "cpf": "98765432109",
            },
        ).status_code == (201 if allowed else 403)
        assert (
            session_client.patch(
                f"/api/professionals/{professional_id}",
                json={"nome": "Profissional atualizado"},
            ).status_code
            == expected_status
        )
        assert (
            session_client.delete(f"/api/professionals/{professional_id}").status_code
            == expected_status
        )

    return assert_access
