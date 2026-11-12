import pytest
from sqlalchemy import create_engine, text

from api.database import DatabaseConnector
from api.services.database_service import DatabaseService


def test_database_service_commits_successful_session_operations(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'database_service.db'}"
    connector = DatabaseConnector(database_url)
    service = DatabaseService(connector)
    with connector.engine.begin() as connection:
        connection.execute(text("CREATE TABLE records (value TEXT NOT NULL)"))

    result = service.run_with_session(
        lambda session, value: session.execute(
            text("INSERT INTO records (value) VALUES (:value)"),
            {"value": value},
        ).rowcount,
        "committed",
    )

    assert result == 1
    assert (
        service.run_with_session(
            lambda session: session.scalar(text("SELECT value FROM records"))
        )
        == "committed"
    )
    connector.dispose()


def test_database_service_rolls_back_failed_session_operations(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'database_rollback.db'}"
    connector = DatabaseConnector(database_url)
    service = DatabaseService(connector)
    with connector.engine.begin() as connection:
        connection.execute(text("CREATE TABLE records (value TEXT NOT NULL)"))

    def insert_then_fail(session):
        session.execute(text("INSERT INTO records (value) VALUES ('rolled back')"))
        raise RuntimeError("operation failed")

    with pytest.raises(RuntimeError, match="operation failed"):
        service.run_with_session(insert_then_fail)

    assert (
        service.run_with_session(
            lambda session: session.scalar(text("SELECT count(*) FROM records"))
        )
        == 0
    )
    connector.dispose()
