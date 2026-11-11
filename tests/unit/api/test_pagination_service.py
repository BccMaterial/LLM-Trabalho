import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session

from api.services.pagination_service import (
    InvalidPageError,
    PaginationParameters,
    PaginationService,
)


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
    metadata = MetaData()
    records = Table(
        "records",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("category", String, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            records.insert(),
            [
                {"id": 1, "category": "a"},
                {"id": 2, "category": "a"},
                {"id": 3, "category": "b"},
            ],
        )

    with Session(engine) as session:
        page = PaginationService.paginate(
            session,
            select(records.c.id)
            .where(records.c.category == "a")
            .order_by(records.c.id),
            PaginationParameters(page=1, page_size=1),
            "https://example.test/records?category=a&page_size=1",
        )
        out_of_range = PaginationService.paginate(
            session,
            select(records.c.id)
            .where(records.c.category == "a")
            .order_by(records.c.id),
            PaginationParameters(page=5, page_size=1),
            "https://example.test/records?category=a&page=5&page_size=1",
        )

    engine.dispose()
    assert page.value == [1]
    assert page.total_items == 2
    assert page.next_link == (
        "https://example.test/records?category=a&page_size=1&page=2"
    )
    assert out_of_range.value == []
    assert out_of_range.total_items == 2
    assert out_of_range.next_link is None
