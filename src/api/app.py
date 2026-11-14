import os

from dotenv import load_dotenv
from flask import Flask

from .controllers.example_controller import example_controller
from .controllers.migration_controller import migration_controller
from .controllers.professional_controller import professional_controller
from .controllers.session_controller import session_controller
from .controllers.user_controller import user_controller
from .database import DatabaseConnector
from .services import DatabaseService, MigrationService
from .services.authentication_middleware import register_authentication_middleware

load_dotenv()


def create_app(database_url: str | None = None):
    app = Flask(__name__)
    app.config["PASSWORD_PEPPER"] = os.getenv("PASSWORD_PEPPER")
    app.config["CORPORATE_EMAIL_DOMAINS"] = os.getenv(
        "CORPORATE_EMAIL_DOMAINS",
        "",
    )
    app.config["ADMIN_API_TOKEN"] = os.getenv("ADMIN_API_TOKEN")
    try:
        session_ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    except ValueError as error:
        raise RuntimeError("SESSION_TTL_SECONDS must be a positive integer") from error
    if session_ttl_seconds <= 0:
        raise RuntimeError("SESSION_TTL_SECONDS must be a positive integer")
    app.config["SESSION_TTL_SECONDS"] = session_ttl_seconds
    app.config["SESSION_COOKIE_SECURE"] = os.getenv(
        "SESSION_COOKIE_SECURE",
        "true",
    ).lower() in {"1", "true", "yes", "on"}
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to start the API")

    database_connector = DatabaseConnector(database_url)
    app.extensions["database_connector"] = database_connector
    app.extensions["database_service"] = DatabaseService(database_connector)
    app.extensions["migration_service"] = MigrationService(database_url)
    app.register_blueprint(example_controller)
    app.register_blueprint(migration_controller)
    app.register_blueprint(professional_controller)
    app.register_blueprint(session_controller)
    app.register_blueprint(user_controller)
    register_authentication_middleware(app)
    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
