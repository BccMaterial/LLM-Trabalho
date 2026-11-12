from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .professional import Professional

__all__ = ["Base", "Professional"]
