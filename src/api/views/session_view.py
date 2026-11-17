from datetime import datetime, timezone

from flask import jsonify

from ..models.user import User
from ..models.user_session import UserSession


def session_response(user: User, user_session: UserSession):
    return jsonify(
        {
            "user": user.to_dict(),
            "session_id": str(user_session.id),
            "created_at": _timestamp(user_session.created_at),
            "expires_at": _timestamp(user_session.expires_at),
        }
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
