from flask import Blueprint, current_app

from ..views import migration_view

migration_controller = Blueprint("migration_controller", __name__)


@migration_controller.get("/api/migrations")
def list_pending_migrations():
    migrations = current_app.extensions["migration_service"].pending_migrations()
    return migration_view.pending_migrations_response(migrations)


@migration_controller.post("/api/migrations")
def apply_pending_migrations():
    applied = current_app.extensions["migration_service"].apply_pending_migrations()
    return migration_view.applied_migrations_response(applied)
