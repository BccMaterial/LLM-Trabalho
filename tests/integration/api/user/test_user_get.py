def test_list_users_can_filter_by_username_and_get_user_by_id(client, create_user):
    created = create_user(username="ana")
    create_user(username="bruno")

    filtered = client.get("/api/users?username=ana")
    listed = client.get("/api/users")
    fetched = client.get(f"/api/users/{created['id']}")

    assert filtered.status_code == 200
    assert [user["username"] for user in filtered.get_json()["value"]] == ["ana"]
    assert listed.status_code == 200
    assert listed.get_json()["total_items"] == 2
    assert fetched.status_code == 200
    assert fetched.get_json()["id"] == created["id"]
    assert "password_hash" not in fetched.get_json()


def test_get_users_routes_require_authentication(
    unauthenticated_client, client, create_user
):
    created = create_user()

    assert unauthenticated_client.get("/api/users").status_code == 401
    assert unauthenticated_client.get(f"/api/users/{created['id']}").status_code == 401
