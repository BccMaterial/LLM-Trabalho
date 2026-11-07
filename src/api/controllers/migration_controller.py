import hmac

from flask import Blueprint, current_app, jsonify, request

from ..views import migration_view

migration_controller = Blueprint("migration_controller", __name__)


def _authorize_migrations():
    expected_token = current_app.config.get("MIGRATIONS_TOKEN")
    if not expected_token:
        return jsonify({"error": "Migration endpoint is not configured"}), 503

    authorization = request.headers.get("Authorization", "")
    scheme, _, supplied_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        supplied_token,
        expected_token,
    ):
        return jsonify({"error": "Unauthorized"}), 401

    return None


@migration_controller.get("/api/migrations")
def list_pending_migrations():
    authorization_error = _authorize_migrations()
    if authorization_error:
        return authorization_error

    migrations = current_app.extensions["migration_service"].pending_migrations()
    return migration_view.pending_migrations_response(migrations)


@migration_controller.post("/api/migrations")
def apply_pending_migrations():
    authorization_error = _authorize_migrations()
    if authorization_error:
        return authorization_error

    applied = current_app.extensions["migration_service"].apply_pending_migrations()
    return migration_view.applied_migrations_response(applied)
