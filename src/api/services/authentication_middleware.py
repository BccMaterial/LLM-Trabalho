import hmac

from flask import Flask, current_app, g, request

from ..services.user_session_service import UserSessionService
from ..views import error_view

SESSION_COOKIE_NAME = "session_id"

_PUBLIC_ENDPOINTS = {
    "example_controller.example",
    "session_controller.create_session",
    "session_controller.delete_current_session",
}
_PROTECTED_ENDPOINTS = {
    "user_controller.create_user",
    "user_controller.list_users",
    "user_controller.get_user",
    "user_controller.update_user",
    "user_controller.deactivate_user",
    "professional_controller.create_professional",
    "professional_controller.list_professionals",
    "professional_controller.get_professional",
    "professional_controller.update_professional",
    "professional_controller.deactivate_professional",
    "migration_controller.list_pending_migrations",
    "migration_controller.apply_pending_migrations",
    "session_controller.get_current_session",
}
_PROFESSIONAL_ENDPOINTS = {
    "professional_controller.create_professional",
    "professional_controller.list_professionals",
    "professional_controller.get_professional",
    "professional_controller.update_professional",
    "professional_controller.deactivate_professional",
}
_ADMIN_ENDPOINTS = {
    "migration_controller.list_pending_migrations",
    "migration_controller.apply_pending_migrations",
}


def register_authentication_middleware(app: Flask) -> None:
    @app.before_request
    def authenticate_request():
        endpoint = request.endpoint
        if endpoint in _PUBLIC_ENDPOINTS or endpoint not in _PROTECTED_ENDPOINTS:
            return None

        if (
            endpoint != "session_controller.get_current_session"
            and _has_admin_api_token()
        ):
            g.admin_api_token = True
            return None

        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            return _authentication_required()

        db_service = current_app.extensions["database_service"]
        session_info = db_service.run_with_session(
            UserSessionService.get_for_token,
            token,
        )
        if session_info is None:
            return _authentication_required()

        user_session, user = session_info
        g.admin_api_token = False
        g.authenticated_user = user
        g.authenticated_session = user_session

        if endpoint in _ADMIN_ENDPOINTS and user.type != "admin":
            return _permission_denied()
        if endpoint in _PROFESSIONAL_ENDPOINTS and user.type not in {
            "admin",
            "manager",
        }:
            return _permission_denied()
        return None


def _has_admin_api_token() -> bool:
    configured_token = current_app.config.get("ADMIN_API_TOKEN")
    if not isinstance(configured_token, str) or not configured_token:
        return False
    scheme, separator, token = request.headers.get("Authorization", "").partition(" ")
    return bool(
        separator
        and scheme.lower() == "bearer"
        and token
        and hmac.compare_digest(token, configured_token)
    )


def _authentication_required():
    return error_view.error_response(
        "Authentication required",
        401,
        "Sign in with a valid account and try again.",
    )


def _permission_denied():
    return error_view.error_response(
        "Permission denied",
        403,
        "Your account is not authorized to perform this action.",
    )
