import pytest
from sqlalchemy import text

from api.database import DatabaseConnector


def test_session_commits_when_context_exits():
    connector = DatabaseConnector("sqlite+pysqlite:///:memory:")
    try:
        with connector.session() as session:
            session.execute(text("CREATE TABLE example (value INTEGER)"))
            session.execute(text("INSERT INTO example (value) VALUES (1)"))

        with connector.session() as session:
            value = session.execute(text("SELECT value FROM example")).scalar_one()

        assert value == 1
    finally:
        connector.dispose()


def test_session_rolls_back_when_context_raises():
    connector = DatabaseConnector("sqlite+pysqlite:///:memory:")
    try:
        with connector.session() as session:
            session.execute(text("CREATE TABLE example (value INTEGER)"))

        with pytest.raises(RuntimeError):
            with connector.session() as session:
                session.execute(text("INSERT INTO example (value) VALUES (1)"))
                raise RuntimeError("abort transaction")

        with connector.session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM example")).scalar_one()

        assert count == 0
    finally:
        connector.dispose()
