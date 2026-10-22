"""18.4: a second choice is answered, and overwrites nothing.

Reached through the real app over one temporary database, as 18.1's, 18.2's
and 18.3's files are.  **The claim to hold is that a second choice changes
what the first stands for rather than what it holds**: two ``decision_recorded``
events are on the trail, the second names the first under ``supersedes``, and
the first's own id, payload, digest and salt are byte-for-byte what they were
before the second arrived -- 9.17 still rebuilds it.

Where a choice stands is a *reading* of the trail rather than a column,
because 8.4 holds ``screenings`` to sixteen columns and none of them is a
decision.  So ``current`` and ``superseded`` are read off the order the trail
holds, and the two statuses are read off app.audit.decision rather than typed,
as is every payload key and every name the trail is asked about.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.decision import (
    BAND_ORDER,
    DECISION_CURRENT,
    DECISION_STATUSES,
    DECISION_SUPERSEDED,
    OFFICER_ACTIONS,
    OFFICER_ACTION_KEY,
    OVERRIDE_KEY,
    REJECT_ENTRY,
    REMARK_KEY,
    SUPERSEDES_KEY,
    current_decision,
    record_officer_decision,
    recorded_decisions,
)
from app.audit.emit import MODEL_VERSIONS_KEY, RULESET_VERSION_KEY
from app.audit.event_types import DECISION_RECORDED, OVERRIDE_RECORDED
from app.audit.record import event_record
from app.ledger.hashing import hash_record
from app.main import app
from app.storage import db
from app.storage.models import AuditEvent, Base, Screening

#: The path this rule is served at, as the contract spells it.
DECISION_PATH = "/api/screenings/{screening_id}/decision"

#: The band the adverse choice goes against and the one it agrees with, read
#: off the ordering rather than typed.
LOW = BAND_ORDER[0]
AGREEING = BAND_ORDER[-1]

#: The two choices this file takes in turn, both read off the vocabulary.  The
#: adverse one is sent claimed, so the pair is about supersession rather than
#: about 18.2's guard.
FIRST = OFFICER_ACTIONS[0]
SECOND = REJECT_ENTRY

#: What each officer wrote with their choice, distinct so a reader can tell
#: which sentence the trail is carrying.
FIRST_REMARK = "the face matches the live capture"
SECOND_REMARK = "the visa is a fortnight out of date"

#: 18.1's four, which 18.4 adds to rather than replaces (D143's revisit).
THE_OFFICER_FIELDS = ("screening_id", "action", "remark", "override")

#: The three this task adds beside them.
THE_RECORD_FIELDS = ("decision_id", "status", "supersedes")


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


def _screening(sessions: sessionmaker[Session], band: str | None) -> uuid.UUID:
    """One stored screening, carrying the band a stage left on it."""
    with sessions() as session:
        row = Screening(
            document_type="passport",
            filename="a-name-that-must-not-travel.jpg",
            image_width=1240,
            image_height=1754,
            band=band,
        )
        session.add(row)
        session.commit()
        return row.id


def _decide(client: TestClient, screening_id: uuid.UUID, **body):
    """The decision this endpoint is given, as a request."""
    return client.post(DECISION_PATH.format(screening_id=screening_id), json=body)


def _take(client: TestClient, screening_id: uuid.UUID, **body) -> dict:
    """One taken choice, asserted to have been accepted."""
    response = _decide(client, screening_id, **body)
    assert response.status_code == 200, response.text
    return response.json()


def _two_choices(client: TestClient, screening_id: uuid.UUID) -> tuple[dict, dict]:
    """A first choice and a second one on the same screening."""
    first = _take(client, screening_id, action=FIRST, remark=FIRST_REMARK)
    second = _take(client, screening_id, action=SECOND, remark=SECOND_REMARK)
    return first, second


def _trail(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> list[AuditEvent]:
    """The events one screening wrote, read back over a fresh session."""
    with sessions() as session:
        return list(
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.screening_id == screening_id)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
            .scalars()
            .all()
        )


def _decisions_on(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> list[AuditEvent]:
    """Every decision event on one trail, in the order the trail holds them."""
    return [
        event
        for event in _trail(sessions, screening_id)
        if event.event_type == DECISION_RECORDED
    ]


def _sealed(event: AuditEvent) -> tuple:
    """The four values 9.17 rebuilds a row from, as one comparable."""
    return (event.id, event.payload, event.record_hash, event.record_salt)


def _rebuilds(event: AuditEvent) -> bool:
    """Whether the stored digest is the one this record hashes to."""
    return event.record_hash == hash_record(
        event_record(event.event_type, event.screening_id, event.actor, event.payload),
        bytes.fromhex(event.record_salt),
    )


# --- the task's claim ------------------------------------------------------


def test_a_second_choice_changes_the_standing_of_the_first(client, sessions):
    """18.4's one case: the first choice reads superseded and the second
    current, off the trail rather than off a rewritten row."""
    screening_id = _screening(sessions, band=AGREEING)

    _two_choices(client, screening_id)

    states = recorded_decisions(screening_id, sessions=sessions)
    assert [state.status for state in states] == [
        DECISION_SUPERSEDED,
        DECISION_CURRENT,
    ]


def test_a_second_choice_emits_a_new_event_and_overwrites_neither(client, sessions):
    """Two events rather than one amended, and the first is still the row
    that was written -- 9.17 rebuilds it with no change at all."""
    screening_id = _screening(sessions, band=AGREEING)

    _take(client, screening_id, action=FIRST, remark=FIRST_REMARK)
    before = _decisions_on(sessions, screening_id)
    _take(client, screening_id, action=SECOND, remark=SECOND_REMARK)

    after = _decisions_on(sessions, screening_id)
    assert len(before) == 1 and len(after) == 2
    assert _sealed(after[0]) == _sealed(before[0])
    assert all(_rebuilds(event) for event in after)
    assert len({event.record_hash for event in after}) == 2
    assert len({event.record_salt for event in after}) == 2


def test_the_second_names_the_first_it_took_over_from(client, sessions):
    """The link is what makes the trail readable without a rewrite: it is
    written into the new event, and the first carries no key at all."""
    screening_id = _screening(sessions, band=AGREEING)

    _two_choices(client, screening_id)

    first, second = _decisions_on(sessions, screening_id)
    assert SUPERSEDES_KEY not in first.payload
    assert second.payload[SUPERSEDES_KEY] == str(first.id)


# --- where one choice stands -----------------------------------------------


@pytest.mark.parametrize("action", OFFICER_ACTIONS)
def test_a_choice_nothing_has_replaced_reads_current(sessions, client, action):
    """One choice is the current one whatever it says, on any band."""
    screening_id = _screening(sessions, band=AGREEING)

    _take(client, screening_id, action=action)

    states = recorded_decisions(screening_id, sessions=sessions)
    assert [state.status for state in states] == [DECISION_CURRENT]


def test_no_choice_recorded_reads_no_current_one(sessions):
    """Absence is an answer: a screening nothing has been decided on has no
    current choice rather than an error."""
    screening_id = _screening(sessions, band=LOW)

    assert current_decision(screening_id, sessions=sessions) is None
    assert recorded_decisions(screening_id, sessions=sessions) == ()


def test_a_third_choice_supersedes_the_second_and_not_the_first(client, sessions):
    """A chain rather than a pile: each choice names the one before it, and
    every earlier one keeps its own standing."""
    screening_id = _screening(sessions, band=AGREEING)

    _take(client, screening_id, action=FIRST, remark="one")
    _take(client, screening_id, action=SECOND, remark="two")
    _take(client, screening_id, action=FIRST, remark="three")

    first, second, third = _decisions_on(sessions, screening_id)
    assert third.payload[SUPERSEDES_KEY] == str(second.id)
    assert second.payload[SUPERSEDES_KEY] == str(first.id)
    assert [state.status for state in recorded_decisions(screening_id, sessions=sessions)] == [
        DECISION_SUPERSEDED,
        DECISION_SUPERSEDED,
        DECISION_CURRENT,
    ]


def test_the_standing_is_read_off_the_officers_own_words(client, sessions):
    """Every choice keeps what its officer sent, superseded or not: a
    standing says which one is acted on, never what any of them said."""
    screening_id = _screening(sessions, band=AGREEING)

    _two_choices(client, screening_id)

    states = recorded_decisions(screening_id, sessions=sessions)
    assert [(state.remark, state.status) for state in states] == [
        (FIRST_REMARK, DECISION_SUPERSEDED),
        (SECOND_REMARK, DECISION_CURRENT),
    ]
    assert all(state.officer_action in OFFICER_ACTIONS for state in states)
    assert [state.override for state in states] == [False, False]


def test_the_superseded_choice_is_still_the_officers_own_claim(client, sessions):
    """Superseding a choice does not retract the override beside it: the
    flag is what that officer sent, and a later choice is not that officer."""
    screening_id = _screening(sessions, band=LOW)

    _take(client, screening_id, action=REJECT_ENTRY, override=True, remark="claimed")
    _take(client, screening_id, action=FIRST, override=False, remark="released")

    states = recorded_decisions(screening_id, sessions=sessions)
    assert [(state.override, state.status) for state in states] == [
        (True, DECISION_SUPERSEDED),
        (False, DECISION_CURRENT),
    ]
    trail = _trail(sessions, screening_id)
    assert [event.event_type for event in trail] == [
        DECISION_RECORDED,
        OVERRIDE_RECORDED,
        DECISION_RECORDED,
    ]


def test_a_choice_on_another_screening_is_not_in_this_chain(sessions):
    """The chain is one screening's, read off its own trail, so a decision
    taken elsewhere cannot supersede this one."""
    this_one = _screening(sessions, band=AGREEING)
    that_one = _screening(sessions, band=AGREEING)
    for screening_id, remark in (
        (that_one, "elsewhere"),
        (this_one, "here"),
        (this_one, "here again"),
    ):
        record_officer_decision(
            screening_id,
            system_band=AGREEING,
            officer_action=FIRST,
            remark=remark,
            override=False,
            sessions=sessions,
        )

    states = recorded_decisions(this_one, sessions=sessions)
    assert [(state.remark, state.status) for state in states] == [
        ("here", DECISION_SUPERSEDED),
        ("here again", DECISION_CURRENT),
    ]
    elsewhere = recorded_decisions(that_one, sessions=sessions)
    assert [state.status for state in elsewhere] == [DECISION_CURRENT]
    assert elsewhere[0].decision_id != states[0].decision_id


def test_a_refused_second_choice_supersedes_nothing(client, sessions):
    """18.2's guard still comes before the write, so a choice nobody may take
    leaves the one already taken standing."""
    screening_id = _screening(sessions, band=LOW)

    _take(client, screening_id, action=FIRST, remark="released")
    assert _decide(client, screening_id, action=REJECT_ENTRY).status_code == 422

    states = recorded_decisions(screening_id, sessions=sessions)
    assert len(states) == 1
    assert states[0].status == DECISION_CURRENT
    assert states[0].remark == "released"


# --- what the answer says -------------------------------------------------


def test_the_answer_names_the_record_and_where_it_stands(client, sessions):
    """The three fields 18.4 adds: the event written, the standing it was
    read to carry, and no predecessor where there was none."""
    screening_id = _screening(sessions, band=AGREEING)

    body = _take(client, screening_id, action=FIRST, remark=FIRST_REMARK)

    assert set(body) == set(THE_OFFICER_FIELDS) | set(THE_RECORD_FIELDS)
    event = _decisions_on(sessions, screening_id)[0]
    assert body["decision_id"] == str(event.id)
    assert body["status"] == DECISION_CURRENT
    assert body["supersedes"] is None


def test_the_second_answer_names_the_choice_it_took_over_from(client, sessions):
    """A client holding the first decision's id can tell from the second
    answer alone that its own decision no longer stands."""
    screening_id = _screening(sessions, band=AGREEING)

    first, second = _two_choices(client, screening_id)

    assert first["supersedes"] is None
    assert second["supersedes"] == first["decision_id"]
    assert second["decision_id"] != first["decision_id"]


def test_the_answer_reports_the_standing_the_trail_reads(client, sessions):
    """``current`` is not a constant the route invented: it is what
    recorded_decisions reads back for the very record the answer names."""
    screening_id = _screening(sessions, band=AGREEING)

    body = _take(client, screening_id, action=FIRST)

    state = current_decision(screening_id, sessions=sessions)
    assert state is not None
    assert body["status"] == state.status
    assert body["decision_id"] == str(state.decision_id)
    assert body["supersedes"] == state.supersedes


def test_the_same_request_taken_twice_answers_the_same_standing(client, sessions):
    """The idempotency claim: a retry is answered with the same choice, the
    same remark and a current standing, and nothing the first wrote is lost."""
    screening_id = _screening(sessions, band=AGREEING)
    request = {"action": FIRST, "remark": FIRST_REMARK}

    first = _take(client, screening_id, **request)
    second = _take(client, screening_id, **request)

    assert {key: second[key] for key in THE_OFFICER_FIELDS} == {
        key: first[key] for key in THE_OFFICER_FIELDS
    }
    assert first["status"] == second["status"] == DECISION_CURRENT
    assert second["decision_id"] != first["decision_id"]
    states = recorded_decisions(screening_id, sessions=sessions)
    assert [state.status for state in states] == [
        DECISION_SUPERSEDED,
        DECISION_CURRENT,
    ]
    assert len(_decisions_on(sessions, screening_id)) == 2


def test_a_refusal_still_answers_only_the_error_envelope(client, sessions):
    """Nothing was recorded, so nothing is reported: no decision_id and no
    standing beside a 422."""
    screening_id = _screening(sessions, band=LOW)

    body = _decide(client, screening_id, action=REJECT_ENTRY).json()

    assert set(body) == {"error"}
    assert not set(THE_RECORD_FIELDS) & set(body["error"])


# --- nothing lands on the row ---------------------------------------------


def test_the_row_both_choices_were_made_on_is_untouched(client, sessions):
    """8.4's sixteen columns, none of which is a decision: a second choice
    writes a second event and nothing else."""
    screening_id = _screening(sessions, band=LOW)
    _take(client, screening_id, action=REJECT_ENTRY, override=True, remark="one")
    with sessions() as session:
        before = tuple(
            getattr(session.get(Screening, screening_id), name)
            for name in ("id", "status", "score", "band", "deleted_at")
        )

    _take(client, screening_id, action=FIRST, remark="two")

    with sessions() as session:
        after = tuple(
            getattr(session.get(Screening, screening_id), name)
            for name in ("id", "status", "score", "band", "deleted_at")
        )
    assert after == before


# --- the vocabulary, read rather than typed -------------------------------


def test_the_two_standings_are_named_in_one_place():
    """Closed, both spelled, and no duplicates -- so 'current' and
    'superseded' cannot both be absent or one of them a duplicate."""
    assert DECISION_STATUSES == (DECISION_CURRENT, DECISION_SUPERSEDED)
    assert len(set(DECISION_STATUSES)) == 2
    assert all(status.islower() and status.isascii() for status in DECISION_STATUSES)


def test_no_payload_carries_a_standing(client, sessions):
    """The standing is the trail's order and never a key of an event: a
    payload carrying one would be a claim that has to be rewritten when a
    later choice lands, and an event cannot be rewritten (8.5)."""
    screening_id = _screening(sessions, band=AGREEING)

    _two_choices(client, screening_id)

    for event in _trail(sessions, screening_id):
        assert not set(DECISION_STATUSES) & set(event.payload)
    for event in _decisions_on(sessions, screening_id):
        assert event.payload[OFFICER_ACTION_KEY] in OFFICER_ACTIONS
        assert isinstance(event.payload[OVERRIDE_KEY], bool)


def test_the_first_choice_still_carries_exactly_the_three_keys_it_did(client, sessions):
    """18.3's payload, byte for byte: the link is added to the second choice
    and never to the first, so a screening decided once hashes as it did."""
    screening_id = _screening(sessions, band=AGREEING)

    _two_choices(client, screening_id)

    first = _decisions_on(sessions, screening_id)[0]
    assert set(first.payload) == {
        OFFICER_ACTION_KEY,
        REMARK_KEY,
        OVERRIDE_KEY,
        RULESET_VERSION_KEY,
        MODEL_VERSIONS_KEY,
    }
