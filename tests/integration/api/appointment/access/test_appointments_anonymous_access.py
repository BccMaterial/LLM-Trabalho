def test_anonymous_user_cannot_access_appointments(client):
    anonymous_client = client.application.test_client()

    assert anonymous_client.get("/api/appointments").status_code == 401
    assert anonymous_client.post("/api/appointments", json={}).status_code == 401
