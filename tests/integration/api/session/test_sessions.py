import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from api.models.user_session import UserSession


def _login(client, user):
    return client.post(
        "/api/sessions",
        json={"email": user["email"], "password": "senha-segura-123"},
    )


def test_login_current_session_and_logout(application, create_user):
    user = create_user()
    client = application.test_client()

    login_response = _login(client, user)
    cookie = client.get_cookie("session_id")

    assert login_response.status_code == 200
    assert login_response.get_json()["user"]["id"] == user["id"]
    assert "session_id" not in login_response.get_json()
    assert cookie is not None
    assert "HttpOnly" in login_response.headers["Set-Cookie"]
    assert "SameSite=Lax" in login_response.headers["Set-Cookie"]
    assert "expires=" in login_response.headers["Set-Cookie"].lower()
    remaining = datetime.fromisoformat(
        login_response.get_json()["expires_at"]
    ) - datetime.now(timezone.utc)
    assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)
    assert cookie.value not in login_response.get_data(as_text=True)
    assert cookie.value is not None

    current_response = client.get("/api/sessions")
    assert current_response.status_code == 200
    assert current_response.get_json()["user"]["id"] == user["id"]
    assert current_response.get_json()["expires_at"]

    logout_response = client.delete("/api/sessions")
    assert logout_response.status_code == 200
    assert client.get_cookie("session_id") is None
    client.set_cookie("session_id", cookie.value)
    assert client.get("/api/sessions").status_code == 401
    revoked_session = application.extensions["database_service"].run_with_session(
        lambda session: session.get(
            UserSession,
            hashlib.sha256(cookie.value.encode()).hexdigest(),
        )
    )
    assert revoked_session is not None
    assert revoked_session.revoked_at is not None


def test_login_rejects_malformed_credentials(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/sessions",
        json={"email": "not-an-email", "password": "secret"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid login data"


def test_login_configuration_error_does_not_depend_on_email(application, create_user):
    user = create_user()
    application.config["PASSWORD_PEPPER"] = None
    client = application.test_client()

    existing_email = client.post(
        "/api/sessions",
        json={"email": user["email"], "password": "senha-segura-123"},
    )
    unknown_email = client.post(
        "/api/sessions",
        json={"email": "unknown@example.test", "password": "senha-segura-123"},
    )

    assert existing_email.status_code == 503
    assert existing_email.get_json() == unknown_email.get_json()


def test_login_rejects_invalid_credentials_and_disabled_users(application, create_user):
    active_user = create_user()
    disabled_user = create_user(status=False)
    client = application.test_client()

    wrong_password = client.post(
        "/api/sessions",
        json={"email": active_user["email"], "password": "senha-errada"},
    )
    unknown_email = client.post(
        "/api/sessions",
        json={"email": "unknown@example.test", "password": "senha-errada"},
    )
    disabled_login = _login(client, disabled_user)

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.get_json() == unknown_email.get_json()
    assert disabled_login.status_code == 401
    assert client.get_cookie("session_id") is None


def test_expired_sessions_are_rejected(application, create_user):
    user = create_user()
    client = application.test_client()
    assert _login(client, user).status_code == 200
    token = client.get_cookie("session_id").value
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    db_service = application.extensions["database_service"]

    def expire(session):
        user_session = session.get(UserSession, token_hash)
        user_session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    db_service.run_with_session(expire)
    assert client.get("/api/sessions").status_code == 401

    expired_session = db_service.run_with_session(
        lambda session: session.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
    )
    assert expired_session is not None
    assert expired_session.revoked_at is None


def test_admin_api_token_protects_admin_routes(unauthenticated_client, client):
    assert unauthenticated_client.get("/api/users").status_code == 401
    assert unauthenticated_client.get("/api/migrations").status_code == 401
    invalid_token_response = unauthenticated_client.get(
        "/api/users",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert invalid_token_response.status_code == 401
    assert client.get("/api/users").status_code == 200
    assert client.get("/api/migrations").status_code == 200
    assert client.get("/api/sessions").status_code == 401
    assert client.post("/api/migrations").status_code == 200


@pytest.mark.parametrize(
    "user_type",
    ["patient", "manager", "secretary", "policy_approver"],
)
def test_non_admin_profiles_are_limited_to_self_update(
    application, create_user, user_type
):
    user = create_user(
        type=user_type,
        email=f"{user_type}@clinica.example",
    )
    other_user = create_user()
    session_client = application.test_client()
    assert _login(session_client, user).status_code == 200

    assert session_client.post("/api/users", json={}).status_code == 403
    assert session_client.get("/api/users").status_code == 403
    assert session_client.get(f"/api/users/{user['id']}").status_code == 403
    assert session_client.get("/api/migrations").status_code == 403
    assert session_client.post("/api/migrations").status_code == 403
    assert session_client.delete(f"/api/users/{user['id']}").status_code == 403

    assert (
        session_client.patch(
            f"/api/users/{user['id']}",
            json={"nome": "Nome próprio atualizado"},
        ).status_code
        == 200
    )
    assert (
        session_client.patch(
            f"/api/users/{user['id']}",
            json={"type": "admin"},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{user['id']}",
            json={"status": False},
        ).status_code
        == 403
    )
    assert (
        session_client.patch(
            f"/api/users/{other_user['id']}",
            json={"nome": "Alteração indevida"},
        ).status_code
        == 403
    )


def test_admin_session_can_manage_users_and_migrations(application, create_user):
    admin = create_user(type="admin", email="admin@clinica.example")
    target = create_user()
    session_client = application.test_client()
    assert _login(session_client, admin).status_code == 200

    created_response = session_client.post(
        "/api/users",
        json={
            "nome": "Usuária gerenciada",
            "username": "managed-user",
            "cpf": "12345678901",
            "type": "patient",
            "email": "managed@example.test",
            "password": "senha-segura-123",
        },
    )
    assert created_response.status_code == 201
    created_user_id = created_response.get_json()["id"]
    assert session_client.get("/api/users").status_code == 200
    assert session_client.get(f"/api/users/{target['id']}").status_code == 200
    assert (
        session_client.patch(
            f"/api/users/{created_user_id}",
            json={
                "type": "manager",
                "email": "managed-manager@clinica.example",
                "status": False,
            },
        ).status_code
        == 200
    )
    assert session_client.delete(f"/api/users/{created_user_id}").status_code == 200
    assert session_client.get("/api/migrations").status_code == 200
    assert session_client.post("/api/migrations").status_code == 200


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
    application, create_user, client, user_type, allowed
):
    actor_email = (
        f"{user_type}@clinica.example"
        if user_type != "patient"
        else "professional-patient@example.test"
    )
    actor = create_user(type=user_type, email=actor_email)
    session_client = application.test_client()
    assert _login(session_client, actor).status_code == 200

    existing = client.post(
        "/api/professionals",
        json={
            "nome": "Profissional existente",
            "email": "existing-professional@example.test",
            "cpf": "12345678901",
        },
    )
    assert existing.status_code == 201
    professional_id = existing.get_json()["id"]

    expected_read_status = 200 if allowed else 403
    assert session_client.get("/api/professionals").status_code == expected_read_status
    assert (
        session_client.get(f"/api/professionals/{professional_id}").status_code
        == expected_read_status
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
        == expected_read_status
    )
    assert (
        session_client.delete(f"/api/professionals/{professional_id}").status_code
        == expected_read_status
    )


def test_secure_cookie_flag_can_be_enabled(application, create_user):
    application.config["SESSION_COOKIE_SECURE"] = True
    user = create_user()
    response = _login(application.test_client(), user)

    assert response.status_code == 200
    assert "Secure" in response.headers["Set-Cookie"]
