import os

from dotenv import load_dotenv
from flask import Flask

from .controllers.example_controller import example_controller
from .controllers.migration_controller import migration_controller
from .controllers.professional_controller import professional_controller
from .database import DatabaseConnector
from .services import MigrationService

load_dotenv()


def create_app(database_url: str | None = None):
    app = Flask(__name__)
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to start the API")

    app.extensions["database_connector"] = DatabaseConnector(database_url)
    app.extensions["migration_service"] = MigrationService(database_url)
    app.register_blueprint(example_controller)
    app.register_blueprint(migration_controller)
    app.register_blueprint(professional_controller)
    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
