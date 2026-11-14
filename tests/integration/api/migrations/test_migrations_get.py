def test_migrations_get_lists_pending_migrations(migration_client, migration_count):
    response = migration_client.get("/api/migrations")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == migration_count
    assert {migration["revision"] for migration in data["pending"]} == {
        "20261106_01",
        "20261111_01",
        "20261112_01",
        "20261114_01",
    }


def test_migrations_get_returns_empty_list_when_all_are_applied(
    migration_app,
    migration_client,
):
    migration_app.extensions["migration_service"].apply_pending_migrations()

    response = migration_client.get("/api/migrations")

    assert response.status_code == 200
    assert response.get_json() == {"pending": [], "count": 0}
