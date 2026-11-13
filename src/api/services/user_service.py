from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.user import User
from .pagination_service import PageResult, PaginationParameters, PaginationService


class UserChanges(TypedDict, total=False):
    nome: str
    username: str
    cpf: str
    type: str
    email: str
    password: str
    password_hash: str
    status: bool


class UserService:
    @staticmethod
    def create(
        session: Session,
        nome: str,
        username: str,
        cpf: str,
        user_type: str,
        email: str,
        password_hash: str,
        status: bool,
    ) -> User:
        user = User(
            nome=nome,
            username=username,
            cpf=cpf,
            type=user_type,
            email=email,
            password_hash=password_hash,
            status=status,
        )
        session.add(user)
        session.flush()
        return user

    @staticmethod
    def list(
        session: Session,
        parameters: PaginationParameters,
        request_url: str,
        username: str | None = None,
    ) -> PageResult[User]:
        statement = select(User).order_by(User.created_at, User.id)
        if username is not None:
            statement = statement.where(User.username == username)
        return PaginationService.paginate(
            session,
            statement,
            parameters,
            request_url,
        )

    @staticmethod
    def get(session: Session, user_id: UUID) -> User | None:
        return session.get(User, user_id)

    @staticmethod
    def update(
        session: Session,
        user: User,
        fields: UserChanges,
    ) -> User:
        for field in ("nome", "username", "cpf", "type", "email", "status"):
            if field in fields:
                setattr(user, field, fields[field])
        if "password_hash" in fields:
            user.password_hash = fields["password_hash"]
        session.flush()
        return user

    @staticmethod
    def deactivate(session: Session, user: User) -> User:
        user.status = False
        session.flush()
        return user
