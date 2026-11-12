from collections.abc import Callable
from typing import TypeVar

from ..database import DatabaseConnector

Result = TypeVar("Result")


class DatabaseService:
    def __init__(self, connector: DatabaseConnector):
        self._connector = connector

    def run_with_session(
        self,
        operation: Callable[..., Result],
        *args: object,
    ) -> Result:
        with self._connector.session() as session:
            return operation(session, *args)
