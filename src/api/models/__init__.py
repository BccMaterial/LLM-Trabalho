from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .professional import Professional
from .user import User

__all__ = ["Base", "Professional", "User"]
