from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .professional import Professional
from .user import User
from .user_session import UserSession

__all__ = ["Base", "Professional", "User", "UserSession"]
