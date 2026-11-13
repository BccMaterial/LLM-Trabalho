def test_delete_deactivates_user_without_removing_it(client, create_user):
    created = create_user()

    response = client.delete(f"/api/users/{created['id']}")
    fetched = client.get(f"/api/users/{created['id']}")

    assert response.status_code == 200
    assert response.get_json()["status"] is False
    assert fetched.status_code == 200
    assert fetched.get_json()["status"] is False
