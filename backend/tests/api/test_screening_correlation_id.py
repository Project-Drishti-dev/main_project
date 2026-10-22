"""26.8: the correlation id a screening was asked under is on the row.

The unit file holds the claim at the flow.  This one holds the hop the flow
cannot see: **the id the caller offered reaches the stored row through the
real route**, which is the half that could silently break -- the id is bound
in a middleware, the cascade runs in a threadpool, and a context variable
that did not cross either would leave every line null and the row empty.

- **the header, the answer, the lines and the row are one value.**  Asserted
  as a set over everything the run wrote, so an id that reached two of the
  four and not the others fails here rather than in a support ticket.
- **an id nobody offered is still one.**  The row carries the minted id the
  answer was stamped with, not ``None`` -- a stored screening a caller cannot
  correlate is the failure this column exists to prevent.
- **the 404 path stamps a row-free answer**, so a read that found nothing has
  nothing to correlate and says so with a 404 rather than a row.
"""

import io
import json
import logging
import uuid
from collections.abc import Callable, Iterator

import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.api.request_id import REQUEST_ID_HEADER
from app.logging_config import APP_LOGGER_NAME, JsonFormatter
from app.main import app
from app.storage import db
from app.storage.models import Base
from app.storage.repository import ScreeningRepository
from tests.fixtures import mrz_images

#: A page with no machine-readable zone on it: the cascade completes, so the
#: lines below are written on the ordinary path rather than on a fault.
BLANK = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))

#: The id a caller offered, adopted verbatim (11.5).
OFFERED = "req-01HQ3K7M2N9P"

#: An id no row carries, so a read reaches a refusal rather than a result.
MISSING = uuid.uuid4()


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database, bound in as the route's session dependency."""
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
def logged() -> Iterator[Callable[[], list[dict]]]:
    """Drain every line the ``app`` logger has written, parsed as JSON."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield lambda: [
            json.loads(line)
            for line in stream.getvalue().splitlines()
            if line.strip()
        ]
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


def _upload() -> dict:
    """The multipart body ``POST /api/screenings`` accepts."""
    encoded, data = cv2.imencode(".png", BLANK.image)
    assert encoded
    return {"files": {"image": ("page.png", data.tobytes(), "image/png")}}


def _stored(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> object:
    """The committed row, read back over a fresh session."""
    row = ScreeningRepository(sessions).get(screening_id)
    assert row is not None, "the route answered with a row it did not store"
    return row


def test_the_id_the_answer_carried_is_the_one_on_the_row(client, sessions, logged):
    """The header, the answer, every line and the row are one value."""
    response = client.post(
        "/api/screenings", headers={REQUEST_ID_HEADER: OFFERED}, **_upload()
    )
    answered = response.headers[REQUEST_ID_HEADER]
    row = _stored(sessions, uuid.UUID(response.json()["screening_id"]))

    assert response.status_code == 200
    assert answered == OFFERED
    assert row.request_id == OFFERED
    assert {line["request_id"] for line in logged()} == {OFFERED}


def test_a_caller_who_offered_none_still_gets_a_correlatable_row(
    client, sessions, logged
):
    """The minted id the answer was stamped with is the one stored, not ``None``."""
    response = client.post("/api/screenings", **_upload())
    answered = response.headers[REQUEST_ID_HEADER]
    row = _stored(sessions, uuid.UUID(response.json()["screening_id"]))

    assert row.request_id == answered
    assert answered is not None
    assert {line["request_id"] for line in logged()} == {answered}


def test_two_screenings_carry_two_ids(client, sessions, logged):
    """So the column correlates rather than being a constant on every row."""
    first = client.post("/api/screenings", **_upload())
    second = client.post("/api/screenings", **_upload())

    stored = {
        _stored(sessions, uuid.UUID(body.json()["screening_id"])).request_id
        for body in (first, second)
    }

    assert len(stored) == 2
    assert stored == {
        first.headers[REQUEST_ID_HEADER],
        second.headers[REQUEST_ID_HEADER],
    }


def test_a_read_that_found_no_row_is_answered_not_stored(client, sessions):
    """A refusal correlates through the header alone; there is no row to carry it."""
    response = client.get(f"/api/screenings/{MISSING}")

    assert response.status_code == 404
    assert response.headers[REQUEST_ID_HEADER]
    assert _missing(sessions) is None


def _missing(sessions: sessionmaker[Session]) -> object:
    """The row the refusal named, which must not exist."""
    return ScreeningRepository(sessions).get(MISSING)