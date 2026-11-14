import pytest


def _login(client, user):
    return client.post(
        "/api/sessions",
        json={"email": user["email"], "password": "senha-segura-123"},
    )


@pytest.mark.parametrize(
    ("user_type", "allowed"),
    [
        ("admin", True),
        ("manager", True),
        ("patient", False),
        ("secretary", False),
        ("policy_approver", False),
    ],
)
def test_professional_routes_enforce_role_access(
    application, client, create_user, create_professional, user_type, allowed
):
    email = (
        f"{user_type}@clinica.example"
        if user_type != "patient"
        else "professional-patient@example.test"
    )
    actor = create_user(type=user_type, email=email)
    session_client = application.test_client()
    assert _login(session_client, actor).status_code == 200

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


def test_professional_routes_reject_missing_authentication(application, client):
    unauthenticated_client = application.test_client()

    assert unauthenticated_client.get("/api/professionals").status_code == 401
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
    assert client.get("/api/professionals").status_code == 200
    assert (
        client.post(
            "/api/professionals",
            json={
                "nome": "Via token",
                "email": "admin-token@example.test",
                "cpf": "98765432109",
            },
        ).status_code
        == 201
    )
