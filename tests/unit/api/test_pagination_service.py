import pytest
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from api.services.pagination_service import (
    InvalidPageError,
    PaginationParameters,
    PaginationService,
)


class RecordBase(DeclarativeBase):
    pass


class Record(RecordBase):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String, nullable=False)

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "category": self.category}


def test_pagination_parameters_apply_defaults_and_page_size_fallback():
    defaults = PaginationParameters.from_query_params({})
    invalid_size = PaginationParameters.from_query_params(
        {"page": "2", "page_size": "501"}
    )
    malformed_size = PaginationParameters.from_query_params(
        {"page_size": "not-a-number"}
    )
    at_maximum = PaginationParameters.from_query_params({"page_size": "500"})

    assert defaults.page == 1
    assert defaults.page_size == 50
    assert invalid_size.page == 2
    assert invalid_size.page_size == 50
    assert malformed_size.page_size == 50
    assert at_maximum.page_size == 500


@pytest.mark.parametrize("page", ["", "0", "-1", "bad", "1_0"])
def test_pagination_parameters_reject_invalid_page(page):
    with pytest.raises(InvalidPageError):
        PaginationParameters.from_query_params({"page": page})


def test_pagination_service_builds_generic_page_and_next_link():
    engine = create_engine("sqlite:///:memory:")
    RecordBase.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            Record.__table__.insert(),
            [
                {"id": 1, "category": "a"},
                {"id": 2, "category": "a"},
                {"id": 3, "category": "b"},
            ],
        )

    with Session(engine) as session:
        page = PaginationService.paginate(
            session,
            select(Record).where(Record.category == "a").order_by(Record.id),
            PaginationParameters(page=1, page_size=1),
            "https://example.test/records?category=a&page_size=1",
        )
        out_of_range = PaginationService.paginate(
            session,
            select(Record).where(Record.category == "a").order_by(Record.id),
            PaginationParameters(page=5, page_size=1),
            "https://example.test/records?category=a&page=5&page_size=1",
        )

    engine.dispose()
    assert [record.id for record in page.value] == [1]
    assert page.total_items == 2
    assert page.to_dict() == {
        "page": 1,
        "page_size": 1,
        "next_link": "https://example.test/records?category=a&page_size=1&page=2",
        "value": [{"id": 1, "category": "a"}],
        "total_items": 2,
    }
    assert page.next_link == (
        "https://example.test/records?category=a&page_size=1&page=2"
    )
    assert out_of_range.value == []
    assert out_of_range.total_items == 2
    assert out_of_range.next_link is None
