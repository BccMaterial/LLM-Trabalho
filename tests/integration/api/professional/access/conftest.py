import pytest


@pytest.fixture
def login_as_user(client):
    def login(user):
        session_client = client.application.test_client()
        response = session_client.post(
            "/api/sessions",
            json={"email": user["email"], "password": "senha-segura-123"},
        )
        assert response.status_code == 200
        return session_client

    return login
