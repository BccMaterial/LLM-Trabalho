from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from api.app import create_app


def test_migration_endpoints_list_and_apply_pending_migrations(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    app = create_app(database_url=database_url)

    with app.test_client() as client:
        pending_response = client.get("/api/migrations")
        apply_response = client.post("/api/migrations")
        no_pending_response = client.get("/api/migrations")

    assert pending_response.status_code == 200
    pending = pending_response.get_json()["pending"]
    assert pending_response.get_json()["count"] == 2
    assert {migration["revision"] for migration in pending} == {
        "20261106_01",
        "20261111_01",
    }
    assert apply_response.status_code == 200
    assert apply_response.get_json()["count"] == 2
    assert set(apply_response.get_json()["applied"]) == {
        "20261106_01",
        "20261111_01",
    }
    assert no_pending_response.get_json() == {"pending": [], "count": 0}

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert inspector.has_table("migration_test")
        assert inspector.has_table("professionals")
        professional_columns = {
            column["name"]: column for column in inspector.get_columns("professionals")
        }
        assert set(professional_columns) == {
            "id",
            "nome",
            "email",
            "cpf",
            "status",
            "created_at",
            "updated_at",
        }
        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("professionals")
        }
        assert ("email",) in unique_columns
        assert ("cpf",) in unique_columns
        assert "gen_random_uuid()" in professional_columns["id"]["default"]
        assert professional_columns["status"]["default"] == "1"
        assert professional_columns["created_at"]["default"] == "CURRENT_TIMESTAMP"
        assert professional_columns["updated_at"]["default"] == "CURRENT_TIMESTAMP"
        identifier = uuid4()
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "INSERT INTO professionals (id, nome, email, cpf) "
                    "VALUES (:id, 'Database default', 'db@example.test', '12345678901') "
                    "RETURNING id, status, created_at, updated_at"
                ),
                {"id": identifier.hex},
            ).one()
        assert UUID(row.id) == identifier
        assert row.status == 1
        assert row.created_at
        assert row.updated_at
    finally:
        engine.dispose()


def test_professionals_migration_can_be_reversed_and_reapplied(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'reversible_migration.db'}"
    app = create_app(database_url=database_url)

    with app.test_client() as client:
        response = client.post("/api/migrations")
    assert response.status_code == 200

    config = Config(
        str(Path(__file__).resolve().parents[3] / "infra" / "alembic" / "alembic.ini")
    )
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "20261106_01")

    engine = create_engine(database_url)
    try:
        assert not inspect(engine).has_table("professionals")
        assert inspect(engine).has_table("migration_test")
    finally:
        engine.dispose()

    command.upgrade(config, "heads")

    engine = create_engine(database_url)
    try:
        assert inspect(engine).has_table("professionals")
    finally:
        engine.dispose()
        app.extensions["database_connector"].dispose()
