from pathlib import Path

import pytest

from api.app import create_app

ALEMBIC_DIRECTORY = Path(__file__).resolve().parents[4] / "infra" / "alembic"
MIGRATIONS_DIRECTORY = ALEMBIC_DIRECTORY / "versions"


@pytest.fixture
def migration_database_url(tmp_path):
    return f"sqlite:///{tmp_path / 'migrations.db'}"


@pytest.fixture
def migration_count():
    return sum(
        1
        for migration_file in MIGRATIONS_DIRECTORY.glob("*.py")
        if migration_file.name != "__init__.py"
    )


@pytest.fixture
def migration_alembic_directory():
    return ALEMBIC_DIRECTORY


@pytest.fixture
def migration_app(migration_database_url):
    app = create_app(database_url=migration_database_url)
    app.config["ADMIN_API_TOKEN"] = "test-admin-api-token"
    app.config["SESSION_COOKIE_SECURE"] = False

    yield app
    app.extensions["database_connector"].dispose()


@pytest.fixture
def migration_client(migration_app):
    client = migration_app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-admin-api-token"
    return client
