"""18.3: a taken choice reaches the trail, with the override beside it.

Reached through the real app over one temporary database, as 18.1's and
18.2's files are: what is asserted is what a client reads rather than what a
handler returns.  **The claim to hold is that both names appear** -- one
decision_recorded for every choice taken, and an override_recorded beside it
where the choice went against the band shown -- so every count is read off
the trail rather than off a return value.

Both names are read off app.audit.event_types and both payloads are keyed off
app.audit.decision, so a respelling fails a case here rather than passing
quietly.  The band is always the stored one: a request cannot name the band
its choice is made against.  Where a second choice stands, and what the
endpoint answers about it, is 18.4 and its own file.
"""

import inspect
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.decision import (
    BAND_ORDER,
    OFFICER_ACTIONS,
    OFFICER_ACTION_KEY,
    OVERRIDE_KEY,
    REJECT_ENTRY,
    REMARK_KEY,
    SYSTEM_BAND_KEY,
    DecisionError,
    record_officer_decision,
)
from app.audit.emit import MODEL_VERSIONS_KEY, RULESET_VERSION_KEY, emit
from app.audit.event_types import (
    ANALYSIS_COMPLETED,
    DECISION_RECORDED,
    OVERRIDE_RECORDED,
)
from app.audit.record import event_record
from app.ledger.hashing import hash_record
from app.main import app
from app.storage import db
from app.storage.models import AuditEvent, Base, Screening

#: The path this rule is served at, as the contract spells it.
DECISION_PATH = "/api/screenings/{screening_id}/decision"

#: The band the adverse choice goes against, and the one it agrees with, both
#: read off the ordering rather than typed so a retune of it moves this file.
LOW = BAND_ORDER[0]
AGREEING = BAND_ORDER[-1]

#: A choice the adverse band is held to no flag for, and the adverse choice
#: itself, both read off the vocabulary rather than typed.
A_CHOICE = OFFICER_ACTIONS[0]

#: What the officer wrote with the choice.  Padded, so "kept exactly as it
#: was written" is a comparison against the request rather than a copy of it.
A_REMARK = "  The face does not match the live capture.  "

#: Every field the answer carries: 18.1's four, untouched since, and the
#: three 18.4 added beside them (D143's revisit clause, taken in D146).
THE_ANSWER_FIELDS = (
    "screening_id",
    "action",
    "remark",
    "override",
    "decision_id",
    "status",
    "supersedes",
)

#: A choice this project does not read, for the vocabulary refusal.
NOT_A_CHOICE = "escalate"

#: An id no row carries, so a decision on it is a refusal and not a page.
MISSING = uuid.uuid4()

#: The ruleset and the model version a stored row can carry, neither of them
#: a constant this service defaults to.
A_RULESET = "drishti-ruleset-18.3"
A_MODEL_VERSIONS = {"tier2.forgery": "0.1.0"}


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


def _screening(sessions: sessionmaker[Session], band: str | None, **stored) -> uuid.UUID:
    """One stored screening, carrying the band a stage left on it."""
    arguments: dict = {
        "document_type": "passport",
        "filename": "a-name-that-must-not-travel.jpg",
        "image_width": 1240,
        "image_height": 1754,
        "band": band,
    }
    arguments.update(stored)
    with sessions() as session:
        row = Screening(**arguments)
        session.add(row)
        session.commit()
        return row.id


def _decide(client: TestClient, screening_id: uuid.UUID, **body):
    """The decision this endpoint is given, as a request."""
    return client.post(DECISION_PATH.format(screening_id=screening_id), json=body)


def _row(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> tuple:
    """The four stored columns a choice is not allowed to move."""
    with sessions() as session:
        found = session.get(Screening, screening_id)
        return (found.score, found.band, found.status, found.ruleset_version)


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


def _of_type(events: list[AuditEvent], event_type: str) -> list[AuditEvent]:
    """Every event of that name, so a count can be asserted on its own."""
    return [event for event in events if event.event_type == event_type]


def _one_of(events: list[AuditEvent], event_type: str) -> AuditEvent:
    """The single event of that name, failing loudly on zero or two."""
    found = _of_type(events, event_type)
    assert len(found) == 1, f"expected one {event_type}, got {len(found)}"
    return found[0]


def _rebuilds(event: AuditEvent) -> bool:
    """Whether the stored digest is the one this record hashes to."""
    return event.record_hash == hash_record(
        event_record(event.event_type, event.screening_id, event.actor, event.payload),
        bytes.fromhex(event.record_salt),
    )


def _leaves(value) -> Iterator:
    """Every leaf of a payload, so a float can be looked for anywhere."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item)
    else:
        yield value


# --- the task's claim ------------------------------------------------------


def test_a_claimed_choice_against_the_band_leaves_both_events(client, sessions):
    """18.3's one case: both names on one trail, read back off the row."""
    screening_id = _screening(sessions, band=LOW)

    response = _decide(
        client, screening_id, action=REJECT_ENTRY, remark=A_REMARK, override=True
    )

    assert response.status_code == 200, response.text
    events = _trail(sessions, screening_id)
    assert _of_type(events, DECISION_RECORDED) != []
    assert _of_type(events, OVERRIDE_RECORDED) != []


# --- which choice writes what ---------------------------------------------


@pytest.mark.parametrize("action", OFFICER_ACTIONS)
def test_every_choice_leaves_exactly_one_decision_event(client, sessions, action):
    """No band was shown to any of them, so each is the choice alone."""
    screening_id = _screening(sessions, band=None)

    assert _decide(client, screening_id, action=action).status_code == 200

    events = _trail(sessions, screening_id)
    assert len(_of_type(events, DECISION_RECORDED)) == 1
    assert _of_type(events, OVERRIDE_RECORDED) == []


def test_a_choice_that_agrees_with_the_band_records_no_override(client, sessions):
    """The agreement is 10.6's answer, and it is unchanged by a URL."""
    screening_id = _screening(sessions, band=AGREEING)

    assert _decide(client, screening_id, action=REJECT_ENTRY).status_code == 200

    events = _trail(sessions, screening_id)
    assert len(_of_type(events, DECISION_RECORDED)) == 1
    assert _of_type(events, OVERRIDE_RECORDED) == []


def test_the_other_way_against_the_band_is_an_override_without_the_flag(client, sessions):
    """10.6's other direction: releasing what the system was most worried
    about is a disagreement too, and 18.2 holds it to no flag."""
    screening_id = _screening(sessions, band=AGREEING)

    assert _decide(client, screening_id, action=A_CHOICE).status_code == 200

    events = _trail(sessions, screening_id)
    assert len(_of_type(events, DECISION_RECORDED)) == 1
    assert len(_of_type(events, OVERRIDE_RECORDED)) == 1


def test_a_flag_naming_no_disagreement_records_no_override(client, sessions):
    """18.1 keeps the flag the caller's own claim, and the trail follows the
    band rather than the claim: both are recorded, and only one is a
    disagreement (D144's revisit, taken in D145)."""
    screening_id = _screening(sessions, band=AGREEING)

    assert _decide(client, screening_id, action=REJECT_ENTRY, override=True).status_code == 200

    events = _trail(sessions, screening_id)
    assert _of_type(events, OVERRIDE_RECORDED) == []
    assert _one_of(events, DECISION_RECORDED).payload[OVERRIDE_KEY] is True


# --- what each event carries -----------------------------------------------


def test_the_decision_event_carries_what_the_officer_sent(client, sessions):
    """Three keys of the officer's own, and the two versions beside them."""
    screening_id = _screening(sessions, band=AGREEING)

    response = _decide(
        client, screening_id, action=REJECT_ENTRY, remark=A_REMARK, override=True
    )

    assert response.status_code == 200, response.text
    payload = _one_of(_trail(sessions, screening_id), DECISION_RECORDED).payload
    assert set(payload) == {
        OFFICER_ACTION_KEY,
        REMARK_KEY,
        OVERRIDE_KEY,
        RULESET_VERSION_KEY,
        MODEL_VERSIONS_KEY,
    }
    assert payload[OFFICER_ACTION_KEY] == REJECT_ENTRY
    assert payload[REMARK_KEY] == A_REMARK
    assert payload[OVERRIDE_KEY] is True


def test_the_flag_is_recorded_at_the_value_the_caller_sent(client, sessions):
    """Including false: a claim that was not made is as much a record."""
    screening_id = _screening(sessions, band=AGREEING)

    assert _decide(client, screening_id, action=A_CHOICE).status_code == 200

    payload = _one_of(_trail(sessions, screening_id), DECISION_RECORDED).payload
    assert payload[OVERRIDE_KEY] is False


def test_the_override_event_carries_both_sides_and_nothing_else(client, sessions):
    """10.6's payload, unchanged: the remark is the decision's, not this one."""
    screening_id = _screening(sessions, band=LOW)

    assert _decide(client, screening_id, action=REJECT_ENTRY, remark=A_REMARK, override=True).status_code == 200

    payload = _one_of(_trail(sessions, screening_id), OVERRIDE_RECORDED).payload
    assert set(payload) == {
        SYSTEM_BAND_KEY,
        OFFICER_ACTION_KEY,
        RULESET_VERSION_KEY,
        MODEL_VERSIONS_KEY,
    }
    assert payload[SYSTEM_BAND_KEY] == LOW
    assert payload[OFFICER_ACTION_KEY] == REJECT_ENTRY


def test_the_versions_beside_a_choice_are_the_rows_own(client, sessions):
    """Never a constant: a row scored under nothing answers None."""
    screening_id = _screening(
        sessions,
        band=LOW,
        ruleset_version=A_RULESET,
        model_versions=A_MODEL_VERSIONS,
    )

    assert _decide(client, screening_id, action=REJECT_ENTRY, override=True).status_code == 200

    events = _trail(sessions, screening_id)
    for event_type in (DECISION_RECORDED, OVERRIDE_RECORDED):
        payload = _one_of(events, event_type).payload
        assert payload[RULESET_VERSION_KEY] == A_RULESET
        assert payload[MODEL_VERSIONS_KEY] == A_MODEL_VERSIONS


def test_a_row_nothing_scored_leaves_the_versions_it_carries(client, sessions):
    """The absence is written down rather than filled in."""
    screening_id = _screening(sessions, band=None)

    assert _decide(client, screening_id, action=A_CHOICE).status_code == 200

    payload = _one_of(_trail(sessions, screening_id), DECISION_RECORDED).payload
    assert payload[RULESET_VERSION_KEY] is None
    assert payload[MODEL_VERSIONS_KEY] is None


def test_no_event_carries_anything_read_off_the_document(client, sessions):
    """A choice records the officer, never the upload beside it."""
    screening_id = _screening(sessions, band=LOW)

    assert _decide(client, screening_id, action=REJECT_ENTRY, remark=A_REMARK, override=True).status_code == 200

    for event in _trail(sessions, screening_id):
        assert "a-name-that-must-not-travel" not in repr(event.payload)
        assert "passport" not in repr(event.payload)
        assert "document_type" not in event.payload
        assert "filename" not in event.payload
        assert not any(isinstance(leaf, float) for leaf in _leaves(event.payload))


# --- the two are records of their own --------------------------------------


def test_both_events_are_sealed_records_of_their_own(client, sessions):
    """One row each, and 9.17 rebuilds each with no change at all."""
    screening_id = _screening(sessions, band=LOW)

    assert _decide(client, screening_id, action=REJECT_ENTRY, override=True).status_code == 200

    events = _trail(sessions, screening_id)
    assert len(events) == 2
    assert all(event.screening_id == screening_id for event in events)
    assert all(_rebuilds(event) for event in events)
    assert len({event.record_hash for event in events}) == 2
    assert len({event.record_salt for event in events}) == 2


def test_the_automated_result_beside_the_choice_is_untouched(client, sessions):
    """A new event beside the result, and the result not rewritten by it."""
    screening_id = _screening(sessions, band=LOW, ruleset_version=A_RULESET)
    before = emit(
        ANALYSIS_COMPLETED,
        screening_id,
        {"band": LOW},
        sessions=sessions,
        ruleset_version=A_RULESET,
    )
    before_row = _row(sessions, screening_id)

    assert _decide(client, screening_id, action=REJECT_ENTRY, override=True).status_code == 200

    events = _trail(sessions, screening_id)
    after = _one_of(events, ANALYSIS_COMPLETED)
    assert (after.id, after.payload, after.record_hash, after.record_salt) == (
        before.id,
        before.payload,
        before.record_hash,
        before.record_salt,
    )
    assert len(_of_type(events, DECISION_RECORDED)) == 1
    assert len(_of_type(events, OVERRIDE_RECORDED)) == 1
    assert _row(sessions, screening_id) == before_row


# --- what a refusal writes ------------------------------------------------


def test_the_band_that_refuses_a_choice_writes_nothing(client, sessions):
    """18.2's 422 is a validation error, and 18.3 does not make it an event."""
    screening_id = _screening(sessions, band=LOW)

    assert _decide(client, screening_id, action=REJECT_ENTRY).status_code == 422

    assert _trail(sessions, screening_id) == []


def test_a_choice_this_project_cannot_read_writes_nothing(client, sessions):
    screening_id = _screening(sessions, band=LOW)

    assert _decide(client, screening_id, action=NOT_A_CHOICE).status_code == 422

    assert _trail(sessions, screening_id) == []


def test_a_decision_on_an_id_no_row_carries_writes_nothing(client, sessions):
    assert _decide(client, MISSING, action=A_CHOICE).status_code == 404

    assert _trail(sessions, MISSING) == []


# --- the answer, and the trail beside it -----------------------------------


def test_the_answer_still_carries_the_four_values_d143_pinned(client, sessions):
    """D143's revisit clause -- an event id beside the choice -- is taken by
    18.4, and it was taken by growing the answer: none of these four is
    replaced and the two events are still the only thing written (D146)."""
    screening_id = _screening(sessions, band=LOW)

    body = _decide(client, screening_id, action=REJECT_ENTRY, override=True).json()

    assert set(body) == set(THE_ANSWER_FIELDS)
    assert body["action"] == REJECT_ENTRY
    assert body["override"] is True
    assert len(_trail(sessions, screening_id)) == 2


def test_a_second_choice_leaves_its_own_events_and_overwrites_neither(client, sessions):
    """18.3 held the trail append-only; 18.4 is where a second choice is
    answered as well -- the first is still readable beside the second, which
    names it rather than replacing it."""
    screening_id = _screening(sessions, band=AGREEING)

    first = _decide(client, screening_id, action=A_CHOICE, remark="first")
    second = _decide(client, screening_id, action=REJECT_ENTRY, remark="second")

    assert first.status_code == second.status_code == 200
    decisions = _of_type(_trail(sessions, screening_id), DECISION_RECORDED)
    assert len(decisions) == 2
    assert {event.payload[REMARK_KEY] for event in decisions} == {"first", "second"}
    assert all(_rebuilds(event) for event in decisions)


# --- the writer, asked directly --------------------------------------------


def test_the_writer_answers_both_events_and_where_there_is_none(sessions):
    """The return value is the whole story, so a caller need not read back."""
    screening_id = _screening(sessions, band=LOW)

    decision, override = record_officer_decision(
        screening_id,
        system_band=LOW,
        officer_action=REJECT_ENTRY,
        remark=A_REMARK,
        override=True,
        sessions=sessions,
    )

    assert decision.event_type == DECISION_RECORDED
    assert override is not None
    assert override.event_type == OVERRIDE_RECORDED

    agreeing_id = _screening(sessions, band=AGREEING)
    decision, override = record_officer_decision(
        agreeing_id,
        system_band=AGREEING,
        officer_action=REJECT_ENTRY,
        remark="",
        override=False,
        sessions=sessions,
    )

    assert decision.event_type == DECISION_RECORDED
    assert override is None


def test_the_writer_records_no_override_for_a_row_nothing_scored(sessions):
    """No band was shown, so there is nothing the choice went against."""
    screening_id = _screening(sessions, band=None)

    _, override = record_officer_decision(
        screening_id,
        system_band=None,
        officer_action=REJECT_ENTRY,
        remark="",
        override=False,
        sessions=sessions,
    )

    assert override is None
    assert _of_type(_trail(sessions, screening_id), OVERRIDE_RECORDED) == []


def test_a_choice_the_writer_cannot_read_leaves_no_half_decision(sessions):
    """The name is read before either event, so nothing at all is written."""
    screening_id = _screening(sessions, band=LOW)

    with pytest.raises(DecisionError):
        record_officer_decision(
            screening_id,
            system_band=LOW,
            officer_action=NOT_A_CHOICE,
            remark="",
            override=False,
            sessions=sessions,
        )

    assert _trail(sessions, screening_id) == []


def test_the_writer_takes_the_factory_as_a_required_keyword():
    """D62's seam: no module-level session is reachable from here."""
    signature = inspect.signature(record_officer_decision)

    assert list(signature.parameters) == [
        "screening_id",
        "system_band",
        "officer_action",
        "remark",
        "override",
        "sessions",
        "ruleset_version",
        "model_versions",
    ]
    for name in (
        "system_band",
        "officer_action",
        "remark",
        "override",
        "sessions",
        "ruleset_version",
        "model_versions",
    ):
        assert signature.parameters[name].kind.name == "KEYWORD_ONLY"
    assert signature.parameters["sessions"].default is inspect.Parameter.empty
    assert signature.parameters["ruleset_version"].default is None
    assert signature.parameters["model_versions"].default is None
