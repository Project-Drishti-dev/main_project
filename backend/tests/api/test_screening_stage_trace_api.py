"""18.12: where a run's time went, on the screening's own answer.

The task asks for the stage trace and the per-stage timings on the response an
officer's screen is built from, so every case reads the real route against a
real cascade -- a page with no finding would prove only that an empty list is
answered.

**The timings are read back, not measured here.**  The trail stamps an event
when it is written, so a stage's cost is the window between its own event and
the one before it, and what that leaves out -- the scoring after the last tier
-- is why the whole is read off the run's first and last instants and is more
than its stages add up to.  The cases hold both against the trail's own
stamps, read here with sqlalchemy rather than through the module under test:
asking app.progress where its answer came from would make every comparison
agree with it.

**Two reads of one row must answer the same trace**, because these numbers come
off stored instants rather than off a clock: a trace that moved under a caller
who had already read the whole of it is a different answer each time.
"""

import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.emit import emit
from app.audit.event_types import (
    ANALYSIS_COMPLETED,
    DECISION_RECORDED,
    SCREENING_CREATED,
    TIER_COMPLETED,
)
from app.main import app
from app.progress import UNIT_TIER
from app.screening import TIER_KEY
from app.storage import db
from app.storage.models import AuditEvent, Base
from tests.fixtures.progress_routes import (
    UPLOAD_NAME,
    parse_frames,
    pending,
    progress_steps,
    screened,
    stream_text,
)


#: The exact keys the trace carries, and the exact keys one stage carries.
#: Sets, so an added key fails a case rather than being read past: both are
#: public surfaces, and a fourth field is a field a client has to parse.
TRACE_KEYS = {"total_ms", "stages"}
STAGE_KEYS = {"tier", "recorded_at", "elapsed_ms"}

#: How far the stages may sit either side of the whole, in milliseconds.
#: Each window is rounded on its own and the whole is rounded from the run's
#: own span, so the parts may differ from that sum by half a millisecond each.
ROUNDING = 1


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


def _trace(client: TestClient, screening_id: uuid.UUID) -> dict[str, Any]:
    """The stage trace the answer for one screening carries.

    :param client: the app, reached the way every case reaches it.
    :param screening_id: the row being asked about.
    :returns: the ``stage_trace`` object as the response carried it.
    :raises AssertionError: for an answer that was not 200, which is what the
        route promises for a row it carries.
    """
    response = client.get(f"/api/screenings/{screening_id}")
    assert response.status_code == 200
    return response.json()["stage_trace"]


def _trail(
    sessions: sessionmaker[Session], screening_id: uuid.UUID
) -> list[tuple[str, dict[str, Any], datetime]]:
    """One row's run events, read here rather than through app.progress.

    :param sessions: the factory the trail is read through.
    :param screening_id: the row whose trail is being read.
    :returns: each run event as its type, payload and instant, in the order
        the trail wrote them.
    """
    with sessions() as session:
        events = list(
            session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.screening_id == screening_id,
                    AuditEvent.event_type.in_(
                        (SCREENING_CREATED, TIER_COMPLETED, ANALYSIS_COMPLETED)
                    ),
                )
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        )
    return [
        (event.event_type, event.payload or {}, event.created_at)
        for event in events
    ]


def _naive(moment: datetime) -> datetime:
    """One instant with no zone on it, whichever side of a comparison has."""
    return moment.replace(tzinfo=None) if moment.tzinfo else moment


def _restamp(
    sessions: sessionmaker[Session],
    screening_id: uuid.UUID,
    event_type: str,
    moment: datetime,
) -> None:
    """Move the last instant recorded for one kind of event.

    :param sessions: the factory the trail is written through.
    :param screening_id: the row whose trail is being rewritten.
    :param event_type: the kind of event to move.
    :param moment: the instant it will carry afterwards.
    The column is stamped from a wall clock, so a clock that steps is the only
    way a window comes out backwards.  The record hash covers the type, the
    screening, the actor and the payload, and none of those moves here.
    """
    with sessions() as session:
        event = (
            session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.screening_id == screening_id,
                    AuditEvent.event_type == event_type,
                )
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
            )
            .first()
        )
        assert event is not None, f"no {event_type} was recorded"
        event.created_at = moment
        session.commit()


# --- the trace the task names ---------------------------------------------


def test_the_answer_carries_every_stage_the_run_recorded(client, sessions):
    """The trace names the run's stages, in the order the trail wrote them."""
    row = screened(sessions)

    stages = _trace(client, row.id)["stages"]

    assert stages, "the fixture ran a cascade that recorded no stage"
    assert [stage["tier"] for stage in stages] == [
        payload[TIER_KEY]
        for kind, payload, _ in _trail(sessions, row.id)
        if kind == TIER_COMPLETED
    ]


def test_a_stage_is_recorded_at_the_instant_the_trail_stamped(
    client, sessions
):
    """The instant beside a stage is the trail's own, not a reading of one."""
    row = screened(sessions)

    stages = _trace(client, row.id)["stages"]

    assert [
        _naive(datetime.fromisoformat(stage["recorded_at"]))
        for stage in stages
    ] == [
        _naive(recorded_at)
        for kind, _, recorded_at in _trail(sessions, row.id)
        if kind == TIER_COMPLETED
    ]


def test_a_stage_reports_a_whole_number_of_milliseconds(client, sessions):
    """A cost is whole milliseconds, and never a negative one."""
    row = screened(sessions)

    stages = _trace(client, row.id)["stages"]

    assert stages and all(
        isinstance(stage["elapsed_ms"], int)
        and not isinstance(stage["elapsed_ms"], bool)
        and stage["elapsed_ms"] >= 0
        for stage in stages
    )


def test_a_stage_is_charged_from_the_stage_before_it(client, sessions):
    """A later stage's window opens on the stage before it, not on the run.

    Two stages recorded over one run, and the second is charged the gap from
    the first rather than the gap from the start -- otherwise every stage
    would be billed for everything before it and a trace would say nothing
    about where the time actually went.
    """
    row = screened(sessions)
    emit(TIER_COMPLETED, row.id, {TIER_KEY: "tier_1"}, sessions=sessions)
    stamps = [
        _naive(recorded_at)
        for kind, _, recorded_at in _trail(sessions, row.id)
        if kind == TIER_COMPLETED
    ]

    elapsed = [
        stage["elapsed_ms"] for stage in _trace(client, row.id)["stages"]
    ]

    assert elapsed[0] != elapsed[1], "one run, two windows, two costs"
    assert elapsed[1] == max(
        0, round((stamps[1] - stamps[0]).total_seconds() * 1000)
    )


def test_the_whole_run_costs_at_least_its_stages(client, sessions):
    """The parts fit inside the whole, and the whole is not nothing."""
    row = screened(sessions)

    trace = _trace(client, row.id)

    assert trace["total_ms"] is not None and trace["total_ms"] > 0
    assert sum(stage["elapsed_ms"] for stage in trace["stages"]) <= (
        trace["total_ms"] + ROUNDING
    )


def test_the_total_is_the_span_the_run_recorded(client, sessions):
    """The whole is measured between the run's first and last stamps.

    The trail is read here to say which stamps those are: the first is
    ``screening_created`` and the last is ``analysis_completed``, and the
    span between them is the run including the scoring no stage is charged.
    """
    row = screened(sessions)
    stamps = _trail(sessions, row.id)

    total = _trace(client, row.id)["total_ms"]

    assert stamps[0][0] == SCREENING_CREATED
    assert stamps[-1][0] == ANALYSIS_COMPLETED
    span = _naive(stamps[-1][2]) - _naive(stamps[0][2])

    assert total == max(0, round(span.total_seconds() * 1000))


def test_the_trace_and_the_stream_count_the_same_stages(client, sessions):
    """One walk of the trail, so the two routes cannot disagree about it."""
    row = screened(sessions)

    streamed = [
        step["tier"]
        for step in progress_steps(parse_frames(stream_text(client, row.id)))
        if step["unit"] == UNIT_TIER
    ]

    assert [stage["tier"] for stage in _trace(client, row.id)["stages"]] == (
        streamed
    )


# --- the document's own shape ---------------------------------------------


def test_the_trace_is_two_keys_and_nothing_else(client, sessions):
    """The trace is a public surface, so a third key fails this case."""
    row = screened(sessions)

    assert set(_trace(client, row.id)) == TRACE_KEYS


def test_a_stage_carries_exactly_its_three_keys(client, sessions):
    """One stage, three keys -- a fourth is a field a client has to parse."""
    row = screened(sessions)

    stages = _trace(client, row.id)["stages"]

    assert stages and all(set(stage) == STAGE_KEYS for stage in stages)


def test_reading_one_row_twice_answers_the_same_trace(client, sessions):
    """The numbers come off stored instants, so two reads cannot disagree."""
    row = screened(sessions)

    first = client.get(f"/api/screenings/{row.id}")
    second = client.get(f"/api/screenings/{row.id}")

    assert first.status_code == second.status_code == 200
    assert first.json()["stage_trace"] == second.json()["stage_trace"]


# --- a row that recorded less --------------------------------------------


def test_a_row_nothing_ran_on_carries_no_stage_and_no_total(client, sessions):
    """No event at all is an absent trace, not a run that took no time."""
    row = pending(sessions)

    assert _trace(client, row.id) == {"total_ms": None, "stages": []}


def test_a_stage_with_nothing_before_it_reports_no_cost(client, sessions):
    """A tier event with no run before it has no window, and says so."""
    row = pending(sessions)
    emit(TIER_COMPLETED, row.id, {TIER_KEY: "tier_0"}, sessions=sessions)

    stages = _trace(client, row.id)["stages"]

    assert [stage["tier"] for stage in stages] == ["tier_0"]
    assert [stage["elapsed_ms"] for stage in stages] == [None]


def test_an_event_naming_no_tier_is_no_stage_on_either_route(client, sessions):
    """One rule for a nameless payload, held by both routes at once."""
    row = pending(sessions)
    emit(
        SCREENING_CREATED,
        row.id,
        {"document_type": "passport"},
        sessions=sessions,
    )
    emit(TIER_COMPLETED, row.id, {}, sessions=sessions)
    emit(TIER_COMPLETED, row.id, {TIER_KEY: ""}, sessions=sessions)

    streamed = [
        step
        for step in progress_steps(parse_frames(stream_text(client, row.id)))
        if step["unit"] == UNIT_TIER
    ]

    assert _trace(client, row.id)["stages"] == []
    assert streamed == []


def test_the_trace_is_read_again_rather_than_remembered(client, sessions):
    """A stage recorded later is in the next answer, not in a held one."""
    row = screened(sessions)
    emit(TIER_COMPLETED, row.id, {TIER_KEY: "tier_1"}, sessions=sessions)

    stages = _trace(client, row.id)["stages"]

    assert [stage["tier"] for stage in stages] == ["tier_0", "tier_1"]


def test_an_officers_decision_is_not_a_stage_and_costs_nothing(
    client, sessions
):
    """A choice written after the run is neither a stage nor time in one."""
    row = screened(sessions)
    before = _trace(client, row.id)

    emit(DECISION_RECORDED, row.id, {"action": "allow"}, sessions=sessions)
    after = _trace(client, row.id)

    assert after == before


def test_a_clock_that_stepped_back_reads_as_no_time(client, sessions):
    """A window a wall clock moved backwards over is zero, not negative."""
    row = screened(sessions)
    started = _trail(sessions, row.id)[0][2]
    earlier = _naive(started) - timedelta(seconds=5)
    _restamp(sessions, row.id, TIER_COMPLETED, earlier)

    stages = _trace(client, row.id)["stages"]

    assert [stage["elapsed_ms"] for stage in stages] == [0]


# --- what the trace may not carry ----------------------------------------


def test_the_trace_carries_no_finding_a_value_or_the_upload_name(
    client, sessions
):
    """A duration is a cost; nothing measured off the page rides with it."""
    row = screened(sessions)

    body = json.dumps(_trace(client, row.id))
    forbidden = {UPLOAD_NAME}
    forbidden.update(flag["id"] for flag in row.flags)
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
    assert forbidden, "the fixture produced nothing to keep out of an answer"

    assert [name for name in forbidden if name in body] == []