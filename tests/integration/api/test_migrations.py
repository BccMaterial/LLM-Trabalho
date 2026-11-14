from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from api.app import create_app

ALEMBIC_DIRECTORY = Path(__file__).resolve().parents[3] / "infra" / "alembic"
MIGRATIONS_DIRECTORY = ALEMBIC_DIRECTORY / "versions"
MIGRATION_COUNT = sum(
    1
    for migration_file in MIGRATIONS_DIRECTORY.glob("*.py")
    if migration_file.name != "__init__.py"
)


def test_migration_endpoints_list_and_apply_pending_migrations(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    app = create_app(database_url=database_url)
    app.config["ADMIN_API_TOKEN"] = "test-admin-api-token"
    app.config["SESSION_COOKIE_SECURE"] = False

    with app.test_client() as client:
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
        pending_response = client.get("/api/migrations")
        apply_response = client.post("/api/migrations")
        no_pending_response = client.get("/api/migrations")

    assert pending_response.status_code == 200
    pending = pending_response.get_json()["pending"]
    assert pending_response.get_json()["count"] == MIGRATION_COUNT
    assert {migration["revision"] for migration in pending} == {
        "20261106_01",
        "20261111_01",
        "20261112_01",
        "20261114_01",
    }
    assert apply_response.status_code == 200
    assert apply_response.get_json()["count"] == MIGRATION_COUNT
    assert set(apply_response.get_json()["applied"]) == {
        "20261106_01",
        "20261111_01",
        "20261112_01",
        "20261114_01",
    }
    assert no_pending_response.get_json() == {"pending": [], "count": 0}

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert inspector.has_table("migration_test")
        assert inspector.has_table("professionals")
        assert inspector.has_table("users")
        assert inspector.has_table("user_sessions")
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

        user_columns = {
            column["name"]: column for column in inspector.get_columns("users")
        }
        assert set(user_columns) == {
            "id",
            "nome",
            "username",
            "cpf",
            "type",
            "email",
            "password_hash",
            "status",
            "created_at",
            "updated_at",
        }
        user_unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("users")
        }
        assert ("username",) in user_unique_columns
        assert ("cpf",) in user_unique_columns
        assert ("email",) in user_unique_columns
        assert "gen_random_uuid()" in user_columns["id"]["default"]
        assert user_columns["status"]["default"] == "1"
        assert user_columns["created_at"]["default"] == "CURRENT_TIMESTAMP"
        assert user_columns["updated_at"]["default"] == "CURRENT_TIMESTAMP"

        session_columns = {
            column["name"]: column for column in inspector.get_columns("user_sessions")
        }
        assert set(session_columns) == {
            "token_hash",
            "user_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }
        assert session_columns["created_at"]["default"] == "CURRENT_TIMESTAMP"
        assert (
            inspector.get_foreign_keys("user_sessions")[0]["referred_table"] == "users"
        )
    finally:
        engine.dispose()


def test_professionals_migration_can_be_reversed_and_reapplied(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'reversible_migration.db'}"
    app = create_app(database_url=database_url)
    app.config["ADMIN_API_TOKEN"] = "test-admin-api-token"
    app.config["SESSION_COOKIE_SECURE"] = False

    with app.test_client() as client:
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
        response = client.post("/api/migrations")
    assert response.status_code == 200

    config = Config(str(ALEMBIC_DIRECTORY / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "20261106_01")

    engine = create_engine(database_url)
    try:
        assert not inspect(engine).has_table("professionals")
        assert not inspect(engine).has_table("users")
        assert not inspect(engine).has_table("user_sessions")
        assert inspect(engine).has_table("migration_test")
    finally:
        engine.dispose()

    command.upgrade(config, "heads")

    engine = create_engine(database_url)
    try:
        assert inspect(engine).has_table("professionals")
        assert inspect(engine).has_table("users")
        assert inspect(engine).has_table("user_sessions")
    finally:
        engine.dispose()
        app.extensions["database_connector"].dispose()
