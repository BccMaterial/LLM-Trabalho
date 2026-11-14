from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .appointment import Appointment
from .professional import Professional
from .user import User
from .user_session import UserSession

__all__ = ["Appointment", "Base", "Professional", "User", "UserSession"]
