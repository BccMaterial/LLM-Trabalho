from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.orm import Session

from ..models.user import User
from ..services.authentication_middleware import SESSION_COOKIE_NAME
from ..services.user_password_service import (
    PasswordPepperNotConfiguredError,
    verify_password,
)
from ..services.user_service import UserService
from ..services.user_session_service import UserSessionService
from ..utils.normalizers import normalize_email
from ..utils.validators import json_object
from ..views import error_view, session_view

session_controller = Blueprint("session_controller", __name__)


@session_controller.post("/api/sessions")
def create_session():
    db_service = current_app.extensions["database_service"]
    payload = json_object()
    email = normalize_email(payload.get("email")) if payload is not None else None
    password = payload.get("password") if payload is not None else None
    if (
        payload is None
        or set(payload) != {"email", "password"}
        or email is None
        or not isinstance(password, str)
        or not password
    ):
        return error_view.error_response(
            "Invalid login data",
            400,
            "Provide a valid email address and password.",
        )

    pepper = current_app.config.get("PASSWORD_PEPPER")
    if not pepper:
        return error_view.error_response(
            "Authentication is not configured",
            503,
            "Set PASSWORD_PEPPER before enabling user login.",
        )

    lifetime = timedelta(seconds=current_app.config["SESSION_TTL_SECONDS"])

    def authenticate(session: Session) -> tuple[str, datetime, User] | None:
        user = UserService.get_by_email(session, email)
        if user is None or not user.status:
            return None
        if not verify_password(password, user.password_hash, pepper):
            return None
        token, expires_at = UserSessionService.create(session, user.id, lifetime)
        return token, expires_at, user

    try:
        result = db_service.run_with_session(authenticate)
    except PasswordPepperNotConfiguredError:
        return error_view.error_response(
            "Authentication is not configured",
            503,
            "Set PASSWORD_PEPPER before enabling user login.",
        )
    if result is None:
        return _invalid_credentials()

    token, expires_at, user = result
    response = session_view.session_response(user, expires_at)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        expires=expires_at,
        httponly=True,
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        samesite="Lax",
        path="/",
    )
    return response


@session_controller.get("/api/sessions")
def get_current_session():
    user = g.authenticated_user
    user_session = g.authenticated_session
    return session_view.session_response(user, user_session.expires_at)


@session_controller.delete("/api/sessions")
def delete_current_session():
    db_service = current_app.extensions["database_service"]
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        db_service.run_with_session(UserSessionService.revoke, token)

    response = jsonify({"message": "Session closed"})
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        httponly=True,
        samesite="Lax",
    )
    return response


def _invalid_credentials():
    return error_view.error_response(
        "Invalid credentials",
        401,
        "Check the email and password and try again.",
    )
