import pytest


@pytest.fixture
def login_session_profile(application, create_user):
    def login(user_type):
        email = (
            f"{user_type}@clinica.example"
            if user_type != "patient"
            else "patient@example.test"
        )
        user = create_user(type=user_type, email=email)
        client = application.test_client()
        response = client.post(
            "/api/sessions",
            json={"email": user["email"], "password": "senha-segura-123"},
        )
        assert response.status_code == 200
        return client, user

    return login
