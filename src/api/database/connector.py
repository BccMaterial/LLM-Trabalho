from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseConnector:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("database_url must not be empty")

        self.engine: Engine = create_engine(database_url)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._session_factory.begin() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
