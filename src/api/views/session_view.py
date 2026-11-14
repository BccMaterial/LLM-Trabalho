from datetime import datetime, timezone

from flask import jsonify

from ..models.user import User


def session_response(user: User, expires_at: datetime):
    return jsonify(
        {
            "user": user.to_dict(),
            "expires_at": _timestamp(expires_at),
        }
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
