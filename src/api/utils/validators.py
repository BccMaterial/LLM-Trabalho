from collections.abc import Collection
from typing import TypeGuard
from uuid import UUID

from flask import request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest


def json_object() -> dict[str, object] | None:
    if not request.is_json:
        return None
    try:
        payload = request.get_json()
    except BadRequest:
        return None
    return payload if isinstance(payload, dict) else None


def is_valid_cpf(value: object) -> TypeGuard[str]:
    return (
        isinstance(value, str)
        and len(value) == 11
        and value.isascii()
        and value.isdecimal()
    )


def parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def is_identity_conflict(
    error: IntegrityError,
    constraint_names: Collection[str],
    table_name: str,
) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name in constraint_names:
        return True
    return str(error.orig).startswith(f"UNIQUE constraint failed: {table_name}.")
