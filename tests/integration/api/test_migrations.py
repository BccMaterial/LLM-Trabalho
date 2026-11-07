from sqlalchemy import create_engine, inspect

from api.app import create_app


def test_migration_endpoints_list_and_apply_pending_migrations(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    app = create_app(database_url=database_url, migrations_token="test-token")
    headers = {"Authorization": "Bearer test-token"}

    with app.test_client() as client:
        pending_response = client.get("/api/migrations", headers=headers)
        apply_response = client.post("/api/migrations", headers=headers)
        no_pending_response = client.get("/api/migrations", headers=headers)

    assert pending_response.status_code == 200
    assert pending_response.get_json()["count"] == 1
    assert pending_response.get_json()["pending"][0]["revision"] == "20261106_01"
    assert apply_response.status_code == 200
    assert apply_response.get_json() == {
        "applied": ["20261106_01"],
        "count": 1,
    }
    assert no_pending_response.get_json() == {"pending": [], "count": 0}

    engine = create_engine(database_url)
    try:
        assert inspect(engine).has_table("migration_test")
    finally:
        engine.dispose()


def test_migration_endpoints_require_bearer_token():
    app = create_app(
        database_url="sqlite:///:memory:",
        migrations_token="test-token",
    )

    with app.test_client() as client:
        response = client.get("/api/migrations")

    assert response.status_code == 401
