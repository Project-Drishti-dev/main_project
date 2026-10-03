"""18.11: the polling document, and the claim that it is the stream's state.

The task names one assertion -- both routes report identical state -- and the
group below holds it against four rows rather than one: a run with findings,
a row nothing ran on, a row a further tier completed after it, and a row
whose findings name a tier nothing else does.  One comparison would pass on a
document that happened to agree once.

**The two sides are read by two different parsers on purpose.**  The polling
answer is read with response.json(); the stream is read by the frame reader
in tests.fixtures.progress_routes, which knows nothing about the document.
One parser used for both would read a change to either shape the same way on
both sides, and the comparison would agree with the change.

**The rows under the comparison are a real cascade's**, as in 18.10's file:
a blank upload produces no findings, so a document comparing equal to an
empty one would prove nothing about a step.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.emit import emit
from app.audit.event_types import TIER_COMPLETED
from app.main import app
from app.progress import UNKNOWN_TIER, UNIT_TIER
from app.screening import TIER_KEY
from app.storage import db
from app.storage.models import Base
from tests.fixtures.progress_routes import (
    DONE_KEYS,
    FRAME_KEYS,
    UPLOAD_NAME,
    done_frame,
    parse_frames,
    pending,
    progress_steps,
    screened,
    store_flags,
    stream_text,
)


#: The exact keys the polling document carries.  A fourth is a field a client
#: has to parse, and a missing one is a caller left reading an absent key.
DOCUMENT_KEYS = {"screening_id", "units", "events"}


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


def _polled(client: TestClient, screening_id: uuid.UUID) -> dict[str, Any]:
    """The polling answer, as the object the response carried.

    :param client: the app, reached the way 18.10's cases reach it.
    :param screening_id: the row being asked about.
    :returns: the parsed body.
    :raises AssertionError: for an answer that was not 200 JSON, which is
        what the route promises and what a client is written against.
    """
    response = client.get(f"/api/screenings/{screening_id}/progress")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    return response.json()


def _both(
    client: TestClient, screening_id: uuid.UUID
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """What each route says about one screening, side by side.

    :param client: the app, reached the way 18.10's cases reach it.
    :param screening_id: the row both routes are asked about.
    :returns: the polling document, the stream' progress steps, and the one
        frame the stream ends on -- in that order, so a case compares the
        two answers rather than re-deriving either of them.
    """
    document = _polled(client, screening_id)
    frames = parse_frames(stream_text(client, screening_id))
    return document, progress_steps(frames), done_frame(frames)


# --- the claim the task names ---------------------------------------------


def test_the_two_routes_report_the_same_steps_in_the_same_order(
    client, sessions
):
    """The same steps, in the same order, asked of a run that recorded some.

    A list equality rather than a set of names: a step that moved position,
    or one that appeared on one route only, is a difference a client would
    read as progress that had not happened.
    """
    row = screened(sessions)

    document, streamed, done = _both(client, row.id)

    assert streamed, "the fixture screened a page with no finding to report"
    assert document["events"] == streamed


def test_the_two_routes_agree_on_how_many_steps_there_were(client, sessions):
    """The step count is reported once, and reads the same on both routes."""
    row = screened(sessions)

    document, streamed, done = _both(client, row.id)

    assert set(done) == DONE_KEYS
    assert document["units"] == done["units"] == len(streamed)
    assert document["units"] == len(document["events"])


def test_the_two_routes_answer_about_the_same_screening(client, sessions):
    """Both name the row, and so does every step either of them reported."""
    row = screened(sessions)

    document, streamed, done = _both(client, row.id)

    assert document["screening_id"] == done["screening_id"] == str(row.id)
    assert {step["screening_id"] for step in streamed} == {str(row.id)}


def test_a_row_nothing_ran_on_agrees_across_both_routes(client, sessions):
    """No event and no finding is no step on either route, and no unit."""
    row = pending(sessions)

    document, streamed, done = _both(client, row.id)

    assert document["events"] == streamed == []
    assert document["units"] == done["units"] == 0


def test_the_two_routes_agree_after_a_further_tier_completed(
    client, sessions
):
    """The document is read each time it is asked for, not remembered.

    A second tier is written to the trail after the row was screened, so a
    document built at create time, or held across requests, would answer
    with the state from before it -- and would still be self-consistent.
    """
    row = screened(sessions)
    emit(TIER_COMPLETED, row.id, {TIER_KEY: "tier_1"}, sessions=sessions)

    document, streamed, done = _both(client, row.id)

    assert document["events"] == streamed
    assert [
        step["tier"] for step in streamed if step["unit"] == UNIT_TIER
    ] == ["tier_0", "tier_1"]


def test_the_two_routes_agree_on_a_finding_naming_the_unknown_tier(
    client, sessions
):
    """A damaged finding is read the same way by both, tier included."""
    row = screened(sessions)
    store_flags(
        sessions,
        row,
        [*row.flags, {"source_module": "a.module", "tier": None}],
    )

    document, streamed, done = _both(client, row.id)

    assert document["events"] == streamed
    assert [
        step["module"] for step in streamed if step["tier"] == UNKNOWN_TIER
    ] == ["a.module"]


# --- the document's own shape ---------------------------------------------


def test_the_document_is_three_keys_and_nothing_else(client, sessions):
    """The document is a public surface, so a fourth key fails this case."""
    row = screened(sessions)

    document, _, _ = _both(client, row.id)

    assert set(document) == DOCUMENT_KEYS


def test_a_step_carries_exactly_the_keys_a_frame_carries(client, sessions):
    """One step, five keys -- the same five whichever route spelled it."""
    row = screened(sessions)

    document, _, _ = _both(client, row.id)

    assert document["events"]
    assert all(set(step) == FRAME_KEYS for step in document["events"])


def test_polling_the_same_row_twice_answers_the_same_bytes(client, sessions):
    """A poller may ask twice, and the two answers must not drift.

    A read that differed between two calls on one row would be a progress
    state moving under a caller that has already read the whole of it.
    """
    row = screened(sessions)

    first = client.get(f"/api/screenings/{row.id}/progress")
    second = client.get(f"/api/screenings/{row.id}/progress")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content


def test_the_polling_answer_is_a_document_and_not_a_stream(client, sessions):
    """The fallback is the fallback: no event stream is left on the wire."""
    row = screened(sessions)

    response = client.get(f"/api/screenings/{row.id}/progress")

    assert response.headers["content-type"].startswith("application/json")
    assert "event:" not in response.text


# --- one refusal, made the same way by both ------------------------------


def test_an_id_no_row_carries_is_the_same_404_the_stream_answers(
    client, sessions
):
    """Both routes make one refusal, and it is the envelope's own."""
    missing = uuid.uuid4()

    polled = client.get(f"/api/screenings/{missing}/progress")
    streamed = client.get(f"/api/screenings/{missing}/progress/stream")

    assert polled.status_code == streamed.status_code == 404
    assert polled.json() == streamed.json()
    assert polled.json()["error"]["code"] == "SCREENING_NOT_FOUND"


def test_a_refused_poll_carries_no_progress(client, sessions):
    """A refusal is a refusal: no empty document wrapped around the refusal."""
    response = client.get(f"/api/screenings/{uuid.uuid4()}/progress")

    assert response.headers["content-type"].startswith("application/json")
    assert "events" not in response.text
    assert "event:" not in response.text


# --- what no document may carry ------------------------------------------


def test_the_document_carries_no_finding_a_value_or_the_upload_name(
    client, sessions
):
    """The document is filed beside a screen, so it carries what a frame
    carries: a name and a count, and nothing read off the document."""
    row = screened(sessions)

    body = client.get(f"/api/screenings/{row.id}/progress").text

    forbidden = {UPLOAD_NAME, str(row.score)}
    forbidden.update(
        flag["field"]
        for flag in row.flags
        if isinstance(flag.get("field"), str) and flag["field"]
    )
    forbidden.update(
        str(flag["expected"])
        for flag in row.flags
        if isinstance(flag.get("expected"), str) and len(flag["expected"]) > 3
    )
    assert forbidden, "the fixture produced nothing to keep out of a document"

    assert [name for name in forbidden if name in body] == []
