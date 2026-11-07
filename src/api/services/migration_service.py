from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

ALEMBIC_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "infra" / "alembic" / "alembic.ini"
)


class MigrationService:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("database_url must not be empty")

        self.database_url = database_url

    def pending_migrations(self) -> list[dict[str, str]]:
        config = self._config()
        script_directory = ScriptDirectory.from_config(config)
        engine = create_engine(self.database_url)

        try:
            with engine.connect() as connection:
                current_heads = MigrationContext.configure(
                    connection
                ).get_current_heads()

            pending = script_directory.iterate_revisions(
                "heads",
                current_heads or "base",
            )
            return [
                {
                    "revision": revision.revision,
                    "description": revision.doc or "",
                }
                for revision in pending
            ]
        finally:
            engine.dispose()

    def apply_pending_migrations(self) -> list[str]:
        pending = self.pending_migrations()
        if not pending:
            return []

        command.upgrade(self._config(), "heads")
        return [migration["revision"] for migration in pending]

    def _config(self) -> Config:
        config = Config(str(ALEMBIC_CONFIG_PATH))
        config.set_main_option(
            "sqlalchemy.url",
            self.database_url.replace("%", "%%"),
        )
        return config
