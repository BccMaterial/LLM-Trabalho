from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class SerializableEntity(Protocol):
    def to_dict(self) -> dict[str, object]: ...


Entity = TypeVar("Entity", bound=SerializableEntity)

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


class InvalidPageError(ValueError):
    pass


@dataclass(frozen=True)
class PaginationParameters:
    page: int
    page_size: int

    @classmethod
    def from_query_params(
        cls, query_params: Mapping[str, str]
    ) -> "PaginationParameters":
        raw_page = query_params.get("page")
        if raw_page is None:
            page = DEFAULT_PAGE
        else:
            if not raw_page.isascii() or not raw_page.isdecimal():
                raise InvalidPageError("page must be an integer")
            page = int(raw_page)
            if page < 1:
                raise InvalidPageError("page must be at least 1")

        raw_page_size = query_params.get("page_size")
        if (
            raw_page_size is None
            or not raw_page_size.isascii()
            or not raw_page_size.isdecimal()
        ):
            page_size = 0
        else:
            page_size = int(raw_page_size)
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            page_size = DEFAULT_PAGE_SIZE

        return cls(page=page, page_size=page_size)


@dataclass(frozen=True)
class PageResult[Entity]:
    page: int
    page_size: int
    next_link: str | None
    value: list[Entity]
    total_items: int

    def to_dict(self) -> dict[str, object]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "next_link": self.next_link,
            "value": [item.to_dict() for item in self.value],
            "total_items": self.total_items,
        }


class PaginationService:
    @staticmethod
    def paginate(
        session: Session,
        statement: Select[tuple[Entity]],
        parameters: PaginationParameters,
        request_url: str,
    ) -> PageResult[Entity]:
        count_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        total_items = session.scalar(count_statement) or 0
        offset = (parameters.page - 1) * parameters.page_size
        values = list(
            session.scalars(statement.offset(offset).limit(parameters.page_size))
        )
        next_link = None
        if offset + len(values) < total_items:
            next_link = PaginationService._next_link(request_url, parameters.page + 1)

        return PageResult(
            page=parameters.page,
            page_size=parameters.page_size,
            next_link=next_link,
            value=values,
            total_items=total_items,
        )

    @staticmethod
    def _next_link(request_url: str, next_page: int) -> str:
        parts = urlsplit(request_url)
        if not parts.scheme or not parts.netloc:
            raise ValueError("request_url must be an absolute URL")
        query_params = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "page"
        ]
        query_params.append(("page", str(next_page)))
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query_params),
                parts.fragment,
            )
        )
