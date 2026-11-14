from flask import Blueprint, current_app

from ..policies.authorization_context import current_actor_type
from ..policies.migration_authorization_policy import MigrationAuthorizationPolicy
from ..views import error_view, migration_view

migration_controller = Blueprint("migration_controller", __name__)


@migration_controller.get("/api/migrations")
def list_pending_migrations():
    if not MigrationAuthorizationPolicy.can_list_migrations(current_actor_type()):
        return _permission_denied()
    migrations = current_app.extensions["migration_service"].pending_migrations()
    return migration_view.pending_migrations_response(migrations)


@migration_controller.post("/api/migrations")
def apply_pending_migrations():
    if not MigrationAuthorizationPolicy.can_apply_migrations(current_actor_type()):
        return _permission_denied()
    applied = current_app.extensions["migration_service"].apply_pending_migrations()
    return migration_view.applied_migrations_response(applied)


def _permission_denied():
    return error_view.error_response(
        "Permission denied",
        403,
        "Your account is not authorized to perform this action.",
    )
