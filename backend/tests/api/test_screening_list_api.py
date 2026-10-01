"""11.3: ``GET /api/screenings`` answers one page of the three filters.

The endpoint is reached through the real app with a temporary database under
it, so what is asserted is the answer a client reads rather than a route's
return value: a page carries its rows, the number of rows that *matched*
rather than the number on the page, and the bounds it was taken with -- and
every filter narrows the rows and the count together.

**The rows are written with stamps the test chose.**  ``created_at`` is
stamped to the microsecond by the ORM, so a date range asserted against a
clock this test waited for would prove nothing; every row below carries one
of :data:`MARCH`, an hour apart on one chosen day, which is also what makes
the read order an assertion rather than an accident of insertion.
"""

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.api.routes_screenings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.main import app
from app.storage import db
from app.storage.models import Base, Screening
from app.storage.repository import ScreeningRepository


#: One row an hour, 00:00 to 05:00 UTC on 1 March 2026.
MARCH = tuple(
    datetime(2026, 3, 1, hour, 0, tzinfo=timezone.utc) for hour in range(6)
)

#: Every field a row in the list is required to carry.  Written out once and
#: read back against the body, so a field dropped from the contract fails
#: here rather than being noticed by a table that renders nothing.
THE_ITEM_FIELDS = (
    "screening_id",
    "status",
    "document_type",
    "created_at",
    "score",
    "band",
)

#: What each of the six rows below carries, in the order they are written.
#: The bands, the kinds and the stamps are all here so a test can ask for one
#: filter and be answered a set it chose rather than a set it counted.
THE_TABLE = (
    ("passport", "low", 10.0, "completed"),
    ("passport", "review", 55.0, "completed"),
    ("passport", "high", 91.0, "completed"),
    ("visa", "low", 20.0, "completed"),
    ("visa", "review", 60.0, "completed"),
    ("national-id", None, None, "pending"),
)


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema, and a factory over it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        factory = db.build_session_factory(engine)
        app.dependency_overrides[get_sessions] = lambda: factory
        yield factory
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def written(sessions: sessionmaker[Session]) -> list[Screening]:
    """The six rows of :data:`THE_TABLE`, stamped one hour apart."""
    with sessions() as session:
        rows = [
            Screening(
                document_type=doc_type,
                filename=f"a-name-that-must-not-travel-{index}.jpg",
                image_width=1240,
                image_height=1754,
                band=band,
                score=score,
                status=status,
                created_at=MARCH[index],
            )
            for index, (doc_type, band, score, status) in enumerate(THE_TABLE)
        ]
        session.add_all(rows)
        session.commit()
    return rows


def _page(client: TestClient, query: str = "") -> dict:
    """The answer 11.3's endpoint gives for ``query``."""
    response = client.get(f"/api/screenings{query}")
    assert response.status_code == 200, response.text
    return response.json()


def _ids(body: dict) -> list[str]:
    """The ids on a page, as the answer spells them."""
    return [item["screening_id"] for item in body["items"]]


def _at(hour: int) -> str:
    """``MARCH[hour]`` as a query-string instant, carrying its offset.

    ``Z`` rather than ``+00:00``: a query string decodes ``+`` as a space, so
    the offset-bearing spelling ISO gives would arrive as `` 00:00`` and be
    refused -- which is a trap in the spelling, not in the instant.
    """
    return MARCH[hour].isoformat().replace("+00:00", "Z")


# --- the page, and what a row in it is -------------------------------------


def test_a_page_carries_its_rows_its_total_and_the_bounds_it_was_taken_with(
    client, written
):
    """24.3's table needs the count beside the rows, not a second request."""
    body = _page(client)

    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (
        len(THE_TABLE),
        0,
        DEFAULT_PAGE_SIZE,
    )
    assert _ids(body) == [str(row.id) for row in written]


def test_a_row_in_the_list_is_the_row_s_own_columns(client, written):
    """A list reads the table; it does not score anything a second time."""
    body = _page(client)

    for item, row in zip(body["items"], written, strict=True):
        assert set(item) == set(THE_ITEM_FIELDS)
        assert item["screening_id"] == str(row.id)
        assert item["status"] == row.status
        assert item["document_type"] == row.document_type
        assert item["score"] == row.score
        assert item["band"] == row.band


def test_a_list_row_carries_no_findings_no_narrative_and_no_filename(
    client, written
):
    """The full read is 11.2's; a page stays the six fields a table shows."""
    response = client.get("/api/screenings")

    assert response.status_code == 200
    assert "a-name-that-must-not-travel" not in response.text
    for absent in ("flags", "contributions", "summary", "filename"):
        assert absent not in response.text


def test_a_row_nothing_has_scored_is_listed_with_nulls(client, written):
    """11.1 creates a row before any stage has run, and the list shows it."""
    pending = written[-1]

    item = next(
        item
        for item in _page(client)["items"]
        if item["screening_id"] == str(pending.id)
    )

    assert item["status"] == "pending"
    assert item["score"] is None
    assert item["band"] is None


# --- the band filter ------------------------------------------------------


def test_the_band_filter_answers_only_that_band_and_counts_what_matched(
    client, written
):
    """Every other band is in the table, so a filter answering all six fails."""
    body = _page(client, "?band=low")

    assert _ids(body) == [str(written[0].id), str(written[3].id)]
    assert body["total"] == 2
    assert body["total"] < len(THE_TABLE)


def test_a_band_no_row_carries_is_an_empty_page_rather_than_a_refusal(
    client, written
):
    """The repository holds no vocabulary, so a name is a filter, not a fault."""
    body = _page(client, "?band=a-band-this-service-has-never-written")

    assert written, "the table this is empty against must hold rows"
    assert body == {"items": [], "total": 0, "offset": 0, "limit": DEFAULT_PAGE_SIZE}


# --- the document-type filter ---------------------------------------------


def test_the_document_type_filter_answers_only_that_kind(client, written):
    body = _page(client, "?document_type=visa")

    assert _ids(body) == [str(written[3].id), str(written[4].id)]
    assert body["total"] == 2


def test_a_kind_no_row_carries_is_an_empty_page(client, written):
    body = _page(client, "?document_type=travel-permit")

    assert written, "the table this is empty against must hold rows"
    assert body["items"] == []
    assert body["total"] == 0


# --- the date range -------------------------------------------------------


def test_the_date_range_answers_only_the_rows_stamped_inside_it(client, written):
    """Both ends inclusive: the rows on the bounds are on the page."""
    body = _page(client, f"?created_after={_at(1)}&created_before={_at(4)}")

    assert _ids(body) == [str(row.id) for row in written[1:5]]
    assert body["total"] == 4


def test_an_open_end_of_the_range_reaches_the_edge_of_the_table(client, written):
    body = _page(client, f"?created_after={_at(4)}")

    assert _ids(body) == [str(written[4].id), str(written[5].id)]
    assert body["total"] == 2


# --- the three of them over one window ------------------------------------


def test_the_three_filters_are_one_window_and_one_count(client, written):
    """One filter at a time matches more, so dropping any of them shows."""
    alone = (
        _page(client, "?band=low")["total"],
        _page(client, "?document_type=visa")["total"],
        _page(client, f"?created_after={_at(2)}&created_before={_at(4)}")[
            "total"
        ],
    )

    body = _page(
        client,
        f"?band=low&document_type=visa&created_after={_at(2)}"
        f"&created_before={_at(4)}",
    )

    assert alone == (2, 2, 3)
    assert _ids(body) == [str(written[3].id)]
    assert body["total"] == 1


def test_a_filter_that_matches_nothing_is_an_empty_page_not_the_whole_table(
    client, written
):
    """A window no row falls inside must narrow rather than widen."""
    body = _page(client, f"?band=low&created_after={_at(5)}")

    assert body["items"] == []
    assert body["total"] == 0


# --- the page, over the matched rows --------------------------------------


def test_the_page_size_bounds_the_rows_and_not_the_total(client, written):
    first = _page(client, "?limit=2")
    second = _page(client, "?offset=2&limit=2")
    last = _page(client, "?offset=4&limit=2")

    assert _ids(first) == [str(row.id) for row in written[:2]]
    assert (first["total"], first["offset"], first["limit"]) == (6, 0, 2)
    assert _ids(second) == [str(row.id) for row in written[2:4]]
    assert (second["total"], second["offset"], second["limit"]) == (6, 2, 2)
    assert _ids(last) == [str(row.id) for row in written[4:]]
    assert last["total"] == 6


def test_a_page_is_taken_over_the_matched_rows_and_not_the_table(client, written):
    """A window over the whole table would shift the page under the filter."""
    body = _page(client, "?band=low&offset=1&limit=1")

    assert _ids(body) == [str(written[3].id)]
    assert body["total"] == 2


def test_a_page_past_the_last_row_is_empty_and_still_counts(client, written):
    body = _page(client, "?offset=99")

    assert body["items"] == []
    assert body["total"] == 6


def test_a_deleted_row_is_answered_by_no_page_and_counted_by_no_total(
    client, written, sessions
):
    """8.15's rule reaches this read through the repository's one filter."""
    ScreeningRepository(sessions).soft_delete(
        written[1].id, deleted_at=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
    )

    body = _page(client, "?band=review")

    assert _ids(body) == [str(written[4].id)]
    assert body["total"] == 1
    assert str(written[1].id) not in _ids(_page(client))
    assert _page(client)["total"] == 5


# --- what the request is refused for --------------------------------------


def test_a_bound_carrying_no_offset_is_refused_rather_than_guessed(client):
    """A naive bound would be two instants on two backends, so it is a 422."""
    response = client.get("/api/screenings?created_after=2026-03-01T01:00:00")

    assert response.status_code == 422
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


def test_a_range_whose_ends_are_inverted_is_refused(client):
    response = client.get(
        f"/api/screenings?created_after={_at(4)}&created_before={_at(1)}"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


def test_bounds_that_describe_no_page_are_refused_before_the_table_is_read(
    client, written
):
    """``ge``/``le`` on the parameters, so no query is ever emitted."""
    for query in ("?limit=0", "?offset=-1", f"?limit={MAX_PAGE_SIZE + 1}"):
        response = client.get(f"/api/screenings{query}")

        assert response.status_code == 422, query
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


# --- the contract the route declares --------------------------------------


def test_the_endpoint_declares_no_security_requirement():
    """No authentication: the contract asks for no credential and names none."""
    operation = app.openapi()["paths"]["/api/screenings"]["get"]

    assert "security" not in operation
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "band",
        "document_type",
        "created_after",
        "created_before",
        "offset",
        "limit",
    }
