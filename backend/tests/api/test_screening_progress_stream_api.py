"""18.10: progress as a server-sent stream, and what each event may carry.

Reached through the real app, the real flow behind it and one temporary
database under it, so what is asserted is the bytes a caller reads off the
socket rather than a generator's return value.  The task names two things --
the shape of an event, and a clean disconnect -- and the group below holds
both, beside the two claims the stream makes about progress: a tier is
``completed`` because the trail wrote it, and a module is ``reported``
because a stored finding names it.

**The findings under the stream are a real cascade's.**  A page with no
machine-readable zone produces none, so a blank upload could only prove that
an empty table reads.  A drawn TD3 whose printed composite digit is wrong is
screened through app.screening.run_screening with its own parse, which is how
a rule gets its characters, and 6.2 then boxes the failing digit on the page
-- so the row carries findings, and the modules that made them are the ones
the stream goes on to report.

**The last group of cases is what no frame may carry**, on the ground 11.2's
read is held to: a filename is caller-supplied text and a field value is
read off the document, and a stream an officer watches is filed beside neither.

**One case holds the two spellings of a tier apart on purpose.**  The trail
names a tier ``tier_0`` and a finding names the same tier ``0``, and this
module does not invent the crosswalk between them: a frame says what the
record it was read from said, so a client sees both rather than a merge
nobody checked.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.emit import emit
from app.audit.event_types import TIER_COMPLETED
from app.main import app
from app.progress import (
    DONE_EVENT,
    PROGRESS_EVENT,
    UNKNOWN_TIER,
    STATE_COMPLETED,
    STATE_REPORTED,
    UNIT_MODULE,
    UNIT_TIER,
)
from app.screening import TIER_KEY
from app.storage import db
from app.storage.models import AuditEvent, Base
from tests.fixtures.progress_routes import (
    DONE_KEYS,
    FRAME_KEYS,
    UPLOAD_NAME,
    parse_frames,
    pending,
    progress_steps,
    screened,
    store_flags,
    stream_text,
)


#: The vocabulary the frames cross the socket in, written out rather than
#: only compared through the constants.  A constant renamed on both sides of
#: a comparison cannot fail a case, so the spellings a client parses are held
#: here as literals.
WIRE_VOCABULARY = (
    ("unit of a tier step", UNIT_TIER, "tier"),
    ("unit of a module step", UNIT_MODULE, "module"),
    ("state of a completed tier", STATE_COMPLETED, "completed"),
    ("state of a reporting module", STATE_REPORTED, "reported"),
    ("name of a step", PROGRESS_EVENT, "progress"),
    ("name of the last frame", DONE_EVENT, "done"),
)

#: The key a ``tier_completed`` event names its tier under, as the wire and
#: not as the constant, for the same reason as the vocabulary above.
WIRE_TIER_KEY = "tier"

#: Two instants a hand-written event is stamped with, given to the later tier
#: the earlier one so the reader cannot answer in insertion order.
EARLY = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 10, 3, 9, 5, tzinfo=timezone.utc)


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


# --- the event shape ------------------------------------------------------


def test_every_frame_is_a_named_event_carrying_one_json_object(
    client, sessions
):
    """The shape the task names: a named event per step, then one ``done``."""
    row = screened(sessions)

    frames = parse_frames(stream_text(client, row.id))

    assert frames, "a run with findings streamed nothing at all"
    assert all(name in (PROGRESS_EVENT, DONE_EVENT) for name, _ in frames)
    assert all(
        set(data) == FRAME_KEYS
        for name, data in frames[:-1]
        if name == PROGRESS_EVENT
    )
    assert set(frames[-1][1]) == DONE_KEYS
    assert [name for name, _ in frames].count(DONE_EVENT) == 1


def test_the_last_frame_is_the_done_event_and_the_stream_ends_there(
    client, sessions
):
    """A reader that stops at ``done`` holds the whole sequence.

    Reading to the end at all is half the claim: a generator that waited on
    a caller would make this case hang rather than fail.
    """
    row = screened(sessions)

    stream = stream_text(client, row.id)
    frames = parse_frames(stream)

    assert stream.endswith("\n\n")
    assert frames[-1][0] == DONE_EVENT
    assert frames[-1][1]["screening_id"] == str(row.id)
    assert frames[-1][1]["units"] == len(progress_steps(frames))


def test_a_caller_that_hangs_up_part_way_through_disconnects_cleanly(
    client, sessions
):
    """A reader that goes away mid-stream leaves nothing running behind it.

    The read below stops one frame in and closes, which is what a browser
    tab a user navigated away from does.  The claim is that nothing escapes
    and the response reports itself closed.
    """
    row = screened(sessions)

    with client.stream(
        "GET", f"/api/screenings/{row.id}/progress/stream"
    ) as response:
        assert response.status_code == 200
        chunks = response.iter_text()
        assert next(chunks).startswith("event: ")
        response.close()

    assert response.is_closed


# --- the vocabulary itself ------------------------------------------------


@pytest.mark.parametrize(
    ("what", "constant", "literal"), WIRE_VOCABULARY, ids=[w for w, _, _ in WIRE_VOCABULARY]
)
def test_the_wire_vocabulary_is_spelled_as_it_is_here(what, constant, literal):
    """A constant renamed on both sides of a comparison fails nothing."""
    assert constant == literal


def test_the_tier_key_is_the_payload_key_the_trail_writes(
    client, sessions
):
    """The key is spelled on the wire, not only through the constant.

    ``emit`` and the reader both reaching for :data:`app.screening.TIER_KEY`
    would agree whatever that constant said, so the case asks what was
    actually stored rather than what the module reads back.
    """
    row = screened(sessions)

    with sessions() as session:
        stored = list(
            session.query(AuditEvent.payload)
            .filter(AuditEvent.screening_id == row.id)
            .all()
        )
    tiers = [
        payload for (payload,) in stored if payload.get(WIRE_TIER_KEY) == "tier_0"
    ]
    assert len(tiers) == 1


def test_a_frame_is_exactly_its_bytes(client, sessions):
    """The frame is one name line and one sorted object, not merely parseable.

    Byte for byte, because a client reading a stream with a hand-written
    parser is reading the bytes rather than a dict, and a key order that
    moves is a change to them.
    """
    row = screened(sessions)

    stream = stream_text(client, row.id)

    assert stream.startswith(
        "event: progress\n"
        'data: {"module": null, "screening_id": "'
        + str(row.id)
        + '", "state": "completed", "tier": "tier_0", "unit": "tier"}\n\n'
    )


# --- what each step reports -----------------------------------------------


def test_a_tier_the_trail_recorded_is_reported_as_completed(client, sessions):
    """The per-tier half: the trail is the record of a tier having run."""
    row = screened(sessions)

    frames = parse_frames(stream_text(client, row.id))

    tiers = [
        step
        for step in progress_steps(frames)
        if step["unit"] == UNIT_TIER and step["tier"] == "tier_0"
    ]
    assert tiers == [
        {
            "screening_id": str(row.id),
            "unit": UNIT_TIER,
            "state": STATE_COMPLETED,
            "tier": "tier_0",
            "module": None,
        }
    ]


def test_a_module_a_stored_finding_names_is_reported_as_reported(
    client, sessions
):
    """The per-module half, and it is the findings that supply it."""
    row = screened(sessions)
    named = {
        flag["source_module"]
        for flag in row.flags
        if isinstance(flag.get("source_module"), str)
    }
    assert named, "the fixture screened a page with no finding to report"

    frames = parse_frames(stream_text(client, row.id))

    modules = [
        step for step in progress_steps(frames) if step["unit"] == UNIT_MODULE
    ]
    assert {step["module"] for step in modules} == named
    assert all(step["state"] == STATE_REPORTED for step in modules)
    assert all(step["module"] is not None for step in modules)


def test_a_tier_and_a_finding_spelling_it_differently_are_both_reported(
    client, sessions
):
    """The two records spell one tier two ways, and neither is corrected.

    The trail writes ``tier_0`` and a finding writes ``0``.  Reconciling them
    here would be a crosswalk this task did not design, so a frame carries
    what the record it was read from said -- and this case holds the two
    apart, so a later task that does join them has to change this one.
    """
    row = screened(sessions)
    finding_tiers = {str(flag["tier"]) for flag in row.flags}
    assert finding_tiers == {"0"}

    frames = parse_frames(stream_text(client, row.id))

    completed = {
        step["tier"]
        for step in progress_steps(frames)
        if step["unit"] == UNIT_TIER and step["state"] == STATE_COMPLETED
    }
    reported = {
        step["tier"]
        for step in progress_steps(frames)
        if step["unit"] == UNIT_MODULE
    }
    assert completed == {"tier_0"}
    assert reported == {"0"}


def test_tiers_are_reported_in_the_order_the_trail_wrote_them(
    client, sessions
):
    """Cascade order comes from the trail, not from a module-level guess."""
    row = screened(sessions)
    emit(TIER_COMPLETED, row.id, {TIER_KEY: "tier_1"}, sessions=sessions)

    frames = parse_frames(stream_text(client, row.id))

    tiers = [
        step["tier"]
        for step in progress_steps(frames)
        if step["unit"] == UNIT_TIER
    ]
    assert tiers == ["tier_0", "tier_1"]


def test_tiers_come_out_ordered_by_the_instant_they_were_stamped(
    client, sessions
):
    """Trail order is the stamped instant, not the order the rows landed.

    The two events here are written in the opposite order to the instants
    they carry, so a reader that answered in insertion order fails.  They are
    written straight to the table rather than through ``emit`` because
    ``emit`` stamps its own instant and this case is about the reader
    choosing between two the writer did not.
    """
    row = screened(sessions)
    with sessions() as session:
        for tier, moment in (("tier_late", LATE), ("tier_early", EARLY)):
            session.add(
                AuditEvent(
                    screening_id=row.id,
                    event_type=TIER_COMPLETED,
                    actor="station-unset",
                    payload={WIRE_TIER_KEY: tier},
                    record_hash="0" * 64,
                    created_at=moment,
                )
            )
        session.commit()

    frames = parse_frames(stream_text(client, row.id))

    tiers = [
        step["tier"] for step in progress_steps(frames) if step["unit"] == UNIT_TIER
    ]
    assert tiers == ["tier_0", "tier_early", "tier_late"]


def test_a_finding_naming_no_readable_tier_is_filed_under_the_unknown_one(
    client, sessions
):
    """A stored finding with no tier is named, not dropped and not guessed."""
    row = screened(sessions)
    store_flags(
        sessions, row, [*row.flags, {"source_module": "a.module", "tier": None}]
    )

    frames = parse_frames(stream_text(client, row.id))

    unknown = [
        step for step in progress_steps(frames) if step["tier"] == UNKNOWN_TIER
    ]
    assert [step["unit"] for step in unknown] == [UNIT_MODULE]
    assert unknown[0]["module"] == "a.module"
    assert unknown[0]["state"] == STATE_REPORTED


def test_a_finding_naming_its_tier_as_a_name_keeps_that_name(
    client, sessions
):
    """A tier is ``0`` or ``"quality"``, and a name is not spelled as a number.

    Both spellings are real: 14.3's gate files its findings under
    ``"quality"`` and Tier 0 files its own under ``0``.  Reading the second as
    the first would put a capture-gate module inside the cascade's own tier.
    """
    row = screened(sessions)
    store_flags(
        sessions,
        row,
        [*row.flags, {"source_module": "a.module", "tier": "quality"}],
    )

    frames = parse_frames(stream_text(client, row.id))

    quality = [step for step in progress_steps(frames) if step["tier"] == "quality"]
    assert [step["unit"] for step in quality] == [UNIT_MODULE]
    assert quality[0]["module"] == "a.module"
    assert quality[0]["state"] == STATE_REPORTED


def test_a_finding_naming_a_boolean_tier_is_not_read_as_a_number(
    client, sessions
):
    """``True`` is an ``int`` in Python, and a flag's tier is never a boolean.

    Read as one it would become tier ``1``, putting a module inside Tier 1 on
    the strength of a JSON ``true`` nobody meant as a tier at all.
    """
    row = screened(sessions)
    store_flags(
        sessions,
        row,
        [*row.flags, {"source_module": "a.module", "tier": True}],
    )

    frames = parse_frames(stream_text(client, row.id))

    steps = progress_steps(frames)
    assert all(step["tier"] != "1" for step in steps)
    unknown = [step for step in steps if step["tier"] == UNKNOWN_TIER]
    assert [step["module"] for step in unknown] == ["a.module"]


def test_a_stored_finding_that_is_not_an_object_is_skipped_not_read(
    client, sessions
):
    """The JSON column can hold anything, and the reader reads what it can.

    A row whose ``flags`` holds a string where a finding should be is a row
    this repository does not write, and the reader must not answer
    ``a.module``'s absence by inventing a name for it.
    """
    row = screened(sessions)
    named = {flag["source_module"] for flag in row.flags}
    assert named
    damaged = [*row.flags, "not-a-finding", {"tier": 0, "source_module": ""}]
    store_flags(sessions, row, damaged)

    frames = parse_frames(stream_text(client, row.id))

    modules = {
        step["module"] for step in progress_steps(frames) if step["unit"] == UNIT_MODULE
    }
    assert modules == named
    assert "not-a-finding" not in stream_text(client, row.id)


def test_an_event_naming_no_tier_is_skipped_rather_than_reported(
    client, sessions
):
    """The payload is the record, and a record carrying no name names no tier."""
    row = screened(sessions)
    emit(TIER_COMPLETED, row.id, {}, sessions=sessions)

    frames = parse_frames(stream_text(client, row.id))

    tiers = [
        step["tier"] for step in progress_steps(frames) if step["unit"] == UNIT_TIER
    ]
    assert tiers == ["tier_0"]


def test_a_row_nothing_has_run_on_streams_the_done_frame_alone(
    client, sessions
):
    """No event and no finding is no step -- and the stream still ends."""
    row = pending(sessions)

    frames = parse_frames(stream_text(client, row.id))

    assert [name for name, _ in frames] == [DONE_EVENT]
    assert frames[0][1] == {"screening_id": str(row.id), "units": 0}


def test_an_id_no_row_carries_is_a_404_and_not_a_stream(client, sessions):
    """The read finishes before the first byte, so the refusal is a 404."""
    response = client.get(
        f"/api/screenings/{uuid.uuid4()}/progress/stream"
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "SCREENING_NOT_FOUND"
    assert "event:" not in response.text


# --- what no frame may carry ----------------------------------------------


def test_no_frame_carries_a_finding_a_value_or_the_upload_name(
    client, sessions
):
    """The stream carries progress and nothing read off the document."""
    row = screened(sessions)
    stream = stream_text(client, row.id)

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
    assert forbidden, "the fixture produced nothing to keep out of a frame"

    assert [name for name in forbidden if name in stream] == []
