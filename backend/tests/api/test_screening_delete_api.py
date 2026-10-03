"""18.5: ``DELETE /api/screenings/{id}`` stamps a row and removes nothing.

Reached through the real app, the real flow behind it and one temporary
database under it, so what is asserted is what a client reads afterwards
rather than a route's return value.  The task's own claim is that the
screening disappears from reads, and 8.15 had already written that rule and
every read in the repository already carries it -- so what is proved here is
that the URL reaches the rule, and what a caller is told about the delete.

**The row is still there.**  A soft delete is a stamp, so the last groups of
cases read the table directly, past the reads the repository guards: a
deleted screening keeps its band, its findings and its score, and keeps the
stamp it was given rather than being given a second one.
"""

import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.main import app
from app.pipeline.tier0 import document
from app.screening import run_screening
from app.storage import db
from app.storage.models import Base, Screening
from app.storage.repository import ScreeningRepository
from tests.fixtures import mrz_images


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


def _screened(sessions: sessionmaker[Session]) -> Screening:
    """One real screening, so the delete is asked about a row with a result.

    The page is parsed back off its own pixels rather than handed over as
    text, and 6.2 boxes the failing digit, so the row carries a finding and a
    band for the delete to leave alone.
    """
    zone = list(mrz_images.SPECIMENS["TD3"])
    printed = zone[1][43]
    zone[1] = zone[1][:43] + ("0" if printed != "0" else "1") + zone[1][44:]
    page = mrz_images.render_format("TD3", lines=tuple(zone))
    return run_screening(
        sessions=sessions,
        image=page.image,
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        parsed_document=document.parse_mrz(mrz_images.read_zone(page)),
    )


def _pending(sessions: sessionmaker[Session]) -> Screening:
    """One row 11.1 wrote before any stage ran, carrying no result at all."""
    return ScreeningRepository(sessions).create(
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        image_width=320,
        image_height=90,
    )


def _stored(sessions: sessionmaker[Session], row: Screening) -> Screening | None:
    """The row read past every read the repository guards.

    A direct statement rather than the repository, because the repository's
    own answer for a deleted row is the absence this task is about.
    """
    with sessions() as session:
        return session.execute(
            select(Screening).where(Screening.id == row.id)
        ).scalar_one_or_none()


def _deleted(client: TestClient, row: Screening) -> dict:
    """The answer 18.5's endpoint gives for ``row``."""
    response = client.delete(f"/api/screenings/{row.id}")
    assert response.status_code == 200
    return response.json()


# --- the task's own claim: the screening is gone from reads ---------------


def test_the_screening_is_gone_from_the_item_read(client, sessions):
    """The verify line, through the real app: read it back and it is not there."""
    row = _screened(sessions)

    _deleted(client, row)
    response = client.get(f"/api/screenings/{row.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCREENING_NOT_FOUND"


def test_the_screening_is_gone_from_the_list_read(client, sessions):
    """11.3's page loses the row, and the count moves with the rows."""
    row = _screened(sessions)
    assert client.get("/api/screenings").json()["total"] == 1

    _deleted(client, row)
    body = client.get("/api/screenings").json()

    assert body["total"] == 0
    assert [item["screening_id"] for item in body["items"]] == []


def test_a_delete_takes_no_other_row_with_it(client, sessions):
    kept = _screened(sessions)
    removed = _screened(sessions)

    _deleted(client, removed)
    body = client.get("/api/screenings").json()

    assert [item["screening_id"] for item in body["items"]] == [str(kept.id)]
    assert client.get(f"/api/screenings/{kept.id}").status_code == 200


def test_a_deleted_screening_cannot_be_read_through_any_filter(client, sessions):
    """A filter that names nothing is an empty page, not a second copy."""
    row = _screened(sessions)
    _deleted(client, row)

    for query in (
        f"?band={row.band}",
        "?document_type=passport",
    ):
        body = client.get(f"/api/screenings{query}").json()

        assert body["total"] == 0, query
        assert body["items"] == [], query


# --- what the answer is, and what it refuses to carry ----------------------


def test_the_answer_names_the_row_and_nothing_else(client, sessions):
    row = _screened(sessions)

    body = _deleted(client, row)

    assert set(body) == {"screening_id", "deleted_at"}
    assert body["screening_id"] == str(row.id)
    assert body["deleted_at"] is not None


def test_the_stamp_is_the_instant_the_request_was_handled(client, sessions):
    """The repository is handed the instant rather than reading a clock."""
    row = _screened(sessions)

    before = datetime.now(timezone.utc)
    body = _deleted(client, row)
    after = datetime.now(timezone.utc)

    assert before <= datetime.fromisoformat(body["deleted_at"]) <= after


def test_nothing_read_off_the_document_reaches_the_answer(client, sessions):
    row = _screened(sessions)

    answer = _deleted(client, row)

    assert "a-name-that-must-not-travel" not in str(answer)
    assert set(answer) == {"screening_id", "deleted_at"}


# --- the row is stamped, not removed --------------------------------------


def test_the_row_is_still_in_the_table(client, sessions):
    """8.15's claim: the delete stamps the column and removes no row."""
    row = _screened(sessions)

    _deleted(client, row)
    stored = _stored(sessions, row)

    assert stored is not None
    assert stored.deleted_at is not None


def test_a_deleted_row_keeps_its_score_its_band_and_its_findings(client, sessions):
    row = _screened(sessions)
    assert row.band and row.flags

    _deleted(client, row)
    stored = _stored(sessions, row)

    assert stored.score == row.score
    assert stored.band == row.band
    assert stored.flags == json.loads(json.dumps(row.flags))
    assert stored.created_at.replace(tzinfo=timezone.utc) == row.created_at


def test_a_screening_nobody_scored_can_be_deleted(client, sessions):
    """11.1 writes the row before any stage runs, so a delete is not a stage."""
    created = _pending(sessions)

    _deleted(client, created)

    assert _stored(sessions, created).deleted_at is not None
    assert client.get(f"/api/screenings/{created.id}").status_code == 404


# --- deleting twice, and ids that name nothing ----------------------------


def test_a_second_delete_is_absence_and_leaves_the_first_stamp(client, sessions):
    """When it was deleted is a fact about the past, and is not restated."""
    row = _screened(sessions)
    first = _deleted(client, row)["deleted_at"]

    response = client.delete(f"/api/screenings/{row.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCREENING_NOT_FOUND"
    stored = _stored(sessions, row)
    assert stored.deleted_at.replace(tzinfo=timezone.utc) == datetime.fromisoformat(
        first
    )


def test_an_id_no_row_carries_is_a_404_in_the_shared_envelope(client, sessions):
    """11.4 is what holds this body to the shape every other refusal uses."""
    response = client.delete(f"/api/screenings/{uuid.uuid4()}")

    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "SCREENING_NOT_FOUND"


def test_an_id_that_is_not_one_is_refused_before_the_table_is_read(client, sessions):
    response = client.delete("/api/screenings/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


# --- a browser has to be allowed to send it -------------------------------


def test_the_preflight_lets_a_browser_send_the_delete(client):
    """24.5 deletes from a page served on another origin, so it must be allowed."""
    response = client.options(
        f"/api/screenings/{uuid.uuid4()}",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]
