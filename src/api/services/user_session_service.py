import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.user import User
from ..models.user_session import UserSession


class UserSessionService:
    @staticmethod
    def create(
        session: Session,
        user_id: UUID,
        lifetime: timedelta,
    ) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + lifetime
        session.add(
            UserSession(
                token_hash=_token_hash(token),
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                expires_at=expires_at,
            )
        )
        session.flush()
        return token, expires_at

    @staticmethod
    def get_for_token(
        session: Session,
        token: str,
    ) -> tuple[UserSession, User] | None:
        user_session = session.scalar(
            select(UserSession).where(
                UserSession.token_hash == _token_hash(token),
                UserSession.revoked_at.is_(None),
            )
        )
        if user_session is None or _as_utc(user_session.expires_at) <= datetime.now(
            timezone.utc
        ):
            return None
        user = session.get(User, user_session.user_id)
        if user is None or not user.status:
            return None
        return user_session, user

    @staticmethod
    def revoke(session: Session, token: str) -> None:
        user_session = session.get(UserSession, _token_hash(token))
        if user_session is not None and user_session.revoked_at is None:
            user_session.revoked_at = datetime.now(timezone.utc)
            session.flush()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
