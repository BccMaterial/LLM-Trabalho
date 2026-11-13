import os
import re
from collections.abc import Callable
from typing import TypedDict, TypeGuard, TypeVar
from uuid import UUID

from flask import Blueprint, current_app, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest

from ..models.user import User
from ..services.pagination_service import InvalidPageError, PaginationParameters
from ..services.user_password_service import (
    PasswordPepperNotConfiguredError,
    hash_password,
)
from ..services.user_service import UserChanges, UserService
from ..views import error_view, user_view

user_controller = Blueprint("user_controller", __name__)
Result = TypeVar("Result")

USER_TYPES = frozenset({"patient", "manager", "secretary", "policy_approver", "admin"})


class UserCreateFields(TypedDict):
    nome: str
    username: str
    cpf: str
    type: str
    email: str
    password: str
    status: bool


@user_controller.post("/api/users")
def create_user():
    payload = _json_object()
    fields = _validated_create_fields(payload)
    if fields is None:
        return error_view.error_response(
            "Invalid user data",
            400,
            "Provide a name, username, valid user type, email, unmasked 11-digit CPF, and password.",
        )
    if not _has_valid_corporate_domain(fields["type"], fields["email"]):
        return _invalid_corporate_email()

    try:
        password_hash = hash_password(
            fields["password"],
            current_app.config.get("PASSWORD_PEPPER"),
        )
    except PasswordPepperNotConfiguredError:
        return _password_configuration_error()

    try:
        user = _run_with_session(
            UserService.create,
            fields["nome"],
            fields["username"],
            fields["cpf"],
            fields["type"],
            fields["email"],
            password_hash,
            fields["status"],
        )
    except IntegrityError as error:
        if not _is_identity_conflict(error):
            raise
        return _identity_conflict()
    return user_view.user_response(user, 201)


@user_controller.get("/api/users")
def list_users():
    username = request.args.get("username")
    if username is not None:
        username = username.strip()
        if not username or len(username) > 100:
            return error_view.error_response(
                "Invalid username",
                400,
                "Provide a non-empty username of at most 100 characters.",
            )

    try:
        parameters = PaginationParameters.from_query_params(request.args)
    except InvalidPageError:
        return error_view.error_response(
            "Invalid page parameter",
            400,
            "Use an integer greater than or equal to 1.",
        )

    page = _run_with_session(
        UserService.list,
        parameters,
        request.url,
        username,
    )
    return user_view.users_response(page)


@user_controller.get("/api/users/<user_id>")
def get_user(user_id: str):
    parsed_id = _parse_id(user_id)
    if parsed_id is None:
        return _user_not_found()

    user = _run_with_session(UserService.get, parsed_id)
    if user is None:
        return _user_not_found()
    return user_view.user_response(user)


@user_controller.patch("/api/users/<user_id>")
def update_user(user_id: str):
    parsed_id = _parse_id(user_id)
    if parsed_id is None:
        return _user_not_found()

    payload = _json_object()
    fields = _validated_patch_fields(payload)
    if fields is None:
        return error_view.error_response(
            "Invalid user data",
            400,
            "Provide valid values for the supplied name, username, email, CPF, type, status, and password.",
        )

    user = _run_with_session(UserService.get, parsed_id)
    if user is None:
        return _user_not_found()

    effective_type = fields.get("type", user.type)
    effective_email = fields.get("email", user.email)
    if not _has_valid_corporate_domain(effective_type, effective_email):
        return _invalid_corporate_email()

    if "password" in fields:
        try:
            password_hash = hash_password(
                fields.pop("password"),
                current_app.config.get("PASSWORD_PEPPER"),
            )
        except PasswordPepperNotConfiguredError:
            return _password_configuration_error()
        fields["password_hash"] = password_hash

    def update(session: Session) -> User | None:
        current_user = UserService.get(session, parsed_id)
        if current_user is None:
            return None
        return UserService.update(session, current_user, fields)

    try:
        updated = _run_with_session(update)
    except IntegrityError as error:
        if not _is_identity_conflict(error):
            raise
        return _identity_conflict()
    if updated is None:
        return _user_not_found()
    return user_view.user_response(updated)


@user_controller.delete("/api/users/<user_id>")
def deactivate_user(user_id: str):
    parsed_id = _parse_id(user_id)
    if parsed_id is None:
        return _user_not_found()

    def deactivate(session: Session) -> User | None:
        user = UserService.get(session, parsed_id)
        if user is None:
            return None
        return UserService.deactivate(session, user)

    deactivated = _run_with_session(deactivate)
    if deactivated is None:
        return _user_not_found()
    return user_view.user_response(deactivated)


def _run_with_session(operation: Callable[..., Result], *args: object) -> Result:
    return current_app.extensions["database_service"].run_with_session(operation, *args)


def _user_not_found():
    return error_view.error_response(
        "User not found",
        404,
        "Verify the user ID and try again.",
    )


def _invalid_corporate_email():
    return error_view.error_response(
        "Invalid corporate email",
        400,
        "Non-patient users must use an email domain listed in CORPORATE_EMAIL_DOMAINS.",
    )


def _password_configuration_error():
    return error_view.error_response(
        "Password hashing is not configured",
        503,
        "Set PASSWORD_PEPPER before creating users or resetting passwords.",
    )


def _json_object() -> dict[str, object] | None:
    if not request.is_json:
        return None
    try:
        payload = request.get_json()
    except BadRequest:
        return None
    return payload if isinstance(payload, dict) else None


def _validated_create_fields(
    payload: dict[str, object] | None,
) -> UserCreateFields | None:
    if payload is None or set(payload) - {
        "nome",
        "username",
        "cpf",
        "type",
        "email",
        "password",
        "status",
    }:
        return None

    nome = payload.get("nome")
    username = _normalize_username(payload.get("username"))
    cpf = payload.get("cpf")
    user_type = payload.get("type")
    email = _normalize_email(payload.get("email"))
    password = payload.get("password")
    status = payload.get("status", True)
    if (
        not isinstance(nome, str)
        or not nome.strip()
        or len(nome.strip()) > 255
        or username is None
        or not _is_valid_cpf(cpf)
        or not isinstance(user_type, str)
        or user_type not in USER_TYPES
        or email is None
        or not isinstance(password, str)
        or not password
        or type(status) is not bool
    ):
        return None
    return {
        "nome": nome.strip(),
        "username": username,
        "cpf": cpf,
        "type": user_type,
        "email": email,
        "password": password,
        "status": status,
    }


def _validated_patch_fields(
    payload: dict[str, object] | None,
) -> UserChanges | None:
    valid_fields = {
        "nome",
        "username",
        "cpf",
        "type",
        "email",
        "password",
        "status",
    }
    if payload is None or not payload or set(payload) - valid_fields:
        return None

    fields: UserChanges = {}
    if "nome" in payload:
        nome = payload["nome"]
        if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > 255:
            return None
        fields["nome"] = nome.strip()
    if "username" in payload:
        username = _normalize_username(payload["username"])
        if username is None:
            return None
        fields["username"] = username
    if "cpf" in payload:
        cpf = payload["cpf"]
        if not _is_valid_cpf(cpf):
            return None
        fields["cpf"] = cpf
    if "type" in payload:
        user_type = payload["type"]
        if not isinstance(user_type, str) or user_type not in USER_TYPES:
            return None
        fields["type"] = user_type
    if "email" in payload:
        email = _normalize_email(payload["email"])
        if email is None:
            return None
        fields["email"] = email
    if "password" in payload:
        password = payload["password"]
        if not isinstance(password, str) or not password:
            return None
        fields["password"] = password
    if "status" in payload:
        status = payload["status"]
        if type(status) is not bool:
            return None
        fields["status"] = status
    return fields


def _normalize_username(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    username = value.strip()
    if not username or len(username) > 100:
        return None
    return username


def _normalize_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return None
    return email


def _is_valid_cpf(value: object) -> TypeGuard[str]:
    return (
        isinstance(value, str)
        and len(value) == 11
        and value.isascii()
        and value.isdecimal()
    )


def _has_valid_corporate_domain(user_type: str, email: str) -> bool:
    if user_type == "patient":
        return True
    configured_domains = current_app.config.get(
        "CORPORATE_EMAIL_DOMAINS",
        os.getenv("CORPORATE_EMAIL_DOMAINS", ""),
    )
    if not isinstance(configured_domains, str):
        return False
    domains = {
        domain.strip().lower()
        for domain in configured_domains.split(",")
        if domain.strip()
    }
    email_domain = email.rpartition("@")[2].lower()
    return bool(domains) and email_domain in domains


def _is_identity_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None), "constraint_name", None
    )
    if constraint_name in {
        "uq_users_username",
        "uq_users_cpf",
        "uq_users_email",
    }:
        return True
    return str(error.orig).startswith("UNIQUE constraint failed: users.")


def _identity_conflict():
    return error_view.error_response(
        "User username, CPF, or email already exists",
        409,
        "Use a username, CPF, and email not assigned to another user.",
    )


def _parse_id(user_id: str) -> UUID | None:
    try:
        return UUID(user_id)
    except ValueError:
        return None
