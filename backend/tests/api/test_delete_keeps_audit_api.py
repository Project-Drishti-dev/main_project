"""18.6: a delete leaves the ledger entry and the audit events where they were.

The claim is a negative one -- deleting a screening must not erase the audit
trail -- so every case reads the trail and the log back after the delete and
compares them with what they said before.  Nothing is written here: 8.15's
stamp was already there, and this is the test of the clause 18.5 left open.

The anchor is the real 9.16 and the check is the real 9.17, because surviving
is only a claim about a trail that can still be walked: rows that outlive the
delete but no longer reach their root would satisfy a count.
"""

import contextlib
import uuid
from collections.abc import Iterator
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.decision import ALLOW_ENTRY, OFFICER_ACTION_KEY, REMARK_KEY
from app.audit.event_types import DECISION_RECORDED
from app.ledger.anchoring import anchor_batch, select_unanchored
from app.ledger.signing import load_signing_key
from app.ledger.store import SqliteLedger
from app.ledger.verification import VERIFIED, verify_event
from app.main import app
from app.pipeline.tier0 import document
from app.screening import run_screening
from app.storage import db
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    LEDGER_ENTRY_TABLE_NAME,
    SCREENING_TABLE_NAME,
    AuditEvent,
    Base,
    LedgerEntry,
    Screening,
)
from tests.fixtures import mrz_images

#: The path an officer's choice is taken at, as the contract spells it.
DECISION_PATH = "/api/screenings/{screening_id}/decision"

#: What the officer wrote beside the choice, padded so "kept as it was
#: written" compares against the request rather than against a copy of it.
A_REMARK = "  The face does not match the live capture.  "


class _Database(NamedTuple):
    """The one temporary database every case here runs on."""

    engine: Engine
    sessions: sessionmaker[Session]


@pytest.fixture
def database() -> Iterator[_Database]:
    """One in-memory database with the mapped schema, and a factory over it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        factory = db.build_session_factory(engine)
        app.dependency_overrides[get_sessions] = lambda: factory
        yield _Database(engine=engine, sessions=factory)
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        engine.dispose()


@pytest.fixture
def client(database: _Database) -> Iterator[TestClient]:
    """A client over the app the delete is served by, on the same database."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ledger(database: _Database) -> SqliteLedger:
    """The log 9.16 appends to and 9.17 reads back, over the same database."""
    return SqliteLedger(database.sessions)


@pytest.fixture
def signer():
    """A key for this case alone: two generated keys are never the same key."""
    return load_signing_key(None)


def _screened(sessions: sessionmaker[Session]) -> Screening:
    """One real screening, so its trail carries an analysis and not a stub."""
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


def _trail(
    sessions: sessionmaker[Session], screening_id: uuid.UUID
) -> list[AuditEvent]:
    """Every event one screening wrote, read back over a fresh session."""
    with sessions() as session:
        return list(
            session.scalars(
                select(AuditEvent)
                .where(AuditEvent.screening_id == screening_id)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            ).all()
        )


def _recorded(
    sessions: sessionmaker[Session], screening_id: uuid.UUID
) -> dict[uuid.UUID, tuple]:
    """Each stored event as the columns a delete must not move, keyed by id.

    The record's own columns rather than its count, so a row that was rewritten
    in place fails this rather than passing it.
    """
    with sessions() as session:
        rows = session.execute(
            select(
                AuditEvent.id,
                AuditEvent.event_type,
                AuditEvent.actor,
                AuditEvent.payload,
                AuditEvent.record_hash,
                AuditEvent.record_salt,
                AuditEvent.batch_id,
                AuditEvent.batch_index,
            ).where(AuditEvent.screening_id == screening_id)
        ).all()
    return {row[0]: tuple(row[1:]) for row in rows}


def _entry(ledger: SqliteLedger, batch_id: uuid.UUID) -> tuple | None:
    """One entry's five columns as the log holds them, or ``None``.

    Read back out of the database rather than off the object 9.16 answered
    with, so the comparison is the log's own and not a detached row's.
    """
    row = ledger.read_batch(batch_id)
    if row is None:
        return None
    return (
        row.sequence,
        row.batch_id,
        row.merkle_root,
        row.signature,
        row.anchored_at,
    )


def _anchored(
    database: _Database, ledger: SqliteLedger, signer
) -> tuple[LedgerEntry, ...]:
    """Sweep the unanchored run through 9.16 and answer the entries it wrote."""
    return anchor_batch(
        select_unanchored(database.sessions),
        sessions=database.sessions,
        ledger=ledger,
        signer=signer,
    )


def _deleted(client: TestClient, row: Screening) -> dict:
    """The delete 18.5's endpoint is asked for, and the answer it gives."""
    response = client.delete(f"/api/screenings/{row.id}")
    assert response.status_code == 200
    return response.json()


def _decided(client: TestClient, screening_id: uuid.UUID) -> None:
    """One officer choice, taken through the URL before any delete."""
    response = client.post(
        DECISION_PATH.format(screening_id=screening_id),
        json={"action": ALLOW_ENTRY, "remark": A_REMARK, "override": True},
    )
    assert response.status_code == 200


@contextlib.contextmanager
def _issued(engine: Engine) -> Iterator[list[str]]:
    """Every statement the engine issues inside this block."""
    statements: list[str] = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _statuses(database: _Database, ledger: SqliteLedger, screening_id):
    """9.17's answer for each event one screening wrote, in the trail's order."""
    return [
        verify_event(row, sessions=database.sessions, ledger=ledger)
        for row in _trail(database.sessions, screening_id)
    ]


# --- the task's own claim: the trail is untouched by the delete -----------


def test_the_audit_events_are_still_there_after_the_delete(
    client, database, ledger, signer
):
    """The verify line, through the real app: every event stands where it did."""
    row = _screened(database.sessions)
    _anchored(database, ledger, signer)
    before = _recorded(database.sessions, row.id)
    assert before

    _deleted(client, row)
    after = _recorded(database.sessions, row.id)

    assert set(before) <= set(after)
    for event_id, columns in before.items():
        assert after[event_id] == columns, event_id


def test_the_ledger_entry_is_still_in_the_log_after_the_delete(
    client, database, ledger, signer
):
    """The other half of the claim: the entry is neither removed nor amended."""
    row = _screened(database.sessions)
    (entry,) = _anchored(database, ledger, signer)
    before = _entry(ledger, entry.batch_id)
    assert before is not None

    _deleted(client, row)

    assert _entry(ledger, entry.batch_id) == before


def test_every_event_still_verifies_after_the_delete(client, database, ledger, signer):
    """9.17's answer is about the row, so a stamp elsewhere changes nothing."""
    row = _screened(database.sessions)
    _anchored(database, ledger, signer)
    assert _trail(database.sessions, row.id)

    _deleted(client, row)
    statuses = _statuses(database, ledger, row.id)

    assert statuses and set(statuses) == {VERIFIED}


def test_the_chain_still_walks_the_batch_the_deleted_screening_is_in(
    client, database, ledger, signer
):
    """The log is walked by position, and the delete moved no position."""
    row = _screened(database.sessions)
    entries = _anchored(database, ledger, signer)

    _deleted(client, row)
    chain = list(ledger.iter_batches())

    assert [held.sequence for held in chain] == [e.sequence for e in entries]


def test_the_screening_is_gone_from_reads_while_its_trail_is_not(
    client, database, ledger, signer
):
    """Both halves at once, which is the shape of the claim rather than a count."""
    row = _screened(database.sessions)
    (entry,) = _anchored(database, ledger, signer)

    _deleted(client, row)

    assert client.get(f"/api/screenings/{row.id}").status_code == 404
    assert _trail(database.sessions, row.id)
    assert ledger.read_batch(entry.batch_id) is not None


def test_the_officers_choice_survives_the_delete_too(
    client, database, ledger, signer
):
    """A recorded decision is the part of the trail most worth keeping."""
    row = _screened(database.sessions)
    _decided(client, row.id)
    _anchored(database, ledger, signer)
    (chosen,) = [
        held
        for held in _trail(database.sessions, row.id)
        if held.event_type == DECISION_RECORDED
    ]

    _deleted(client, row)

    assert verify_event(
        chosen, sessions=database.sessions, ledger=ledger
    ) == VERIFIED
    assert chosen.payload[OFFICER_ACTION_KEY] == ALLOW_ENTRY
    assert chosen.payload[REMARK_KEY] == A_REMARK


def test_the_events_still_name_the_id_the_delete_stamped(
    client, database, ledger, signer
):
    """24.8 reaches a trail by screening id, and a delete does not rename one."""
    row = _screened(database.sessions)
    _anchored(database, ledger, signer)

    _deleted(client, row)
    events = _trail(database.sessions, row.id)

    assert events
    assert {held.screening_id for held in events} == {row.id}


# --- what the delete is not allowed to reach ------------------------------


def test_a_delete_takes_no_other_screening_trail_with_it(
    client, database, ledger, signer
):
    """Two trails in one batch, one stamp: both batches still walk afterwards."""
    kept = _screened(database.sessions)
    removed = _screened(database.sessions)
    assert _anchored(database, ledger, signer)
    before = _recorded(database.sessions, kept.id)

    _deleted(client, removed)

    assert _recorded(database.sessions, kept.id) == before
    assert _statuses(database, ledger, kept.id) == [
        VERIFIED
    ] * len(_trail(database.sessions, kept.id))
    assert _statuses(database, ledger, removed.id) == [
        VERIFIED
    ] * len(_trail(database.sessions, removed.id))


def test_a_run_anchored_after_the_delete_still_verifies(
    client, database, ledger, signer
):
    """A sweep that reaches the trail after the stamp commits and still walks."""
    row = _screened(database.sessions)
    _deleted(client, row)

    entries = _anchored(database, ledger, signer)
    events = _trail(database.sessions, row.id)

    assert entries and events
    assert _statuses(database, ledger, row.id) == [VERIFIED] * len(events)


def test_the_delete_issues_nothing_that_removes_a_trail_row(
    client, database, ledger, signer
):
    """The stamp is a write on screenings; no trail statement is issued at all."""
    row = _screened(database.sessions)
    _anchored(database, ledger, signer)

    with _issued(database.engine) as statements:
        _deleted(client, row)

    against_the_trail = [
        statement
        for statement in statements
        if AUDIT_EVENT_TABLE_NAME in statement
        or LEDGER_ENTRY_TABLE_NAME in statement
    ]
    assert against_the_trail == []
    assert [s for s in statements if SCREENING_TABLE_NAME in s]


def test_no_foreign_key_carries_an_event_to_the_row_a_delete_stamps(database):
    """8.5's load-bearing claim, read off the schema rather than the prose."""
    assert AuditEvent.__table__.foreign_keys == frozenset()
    with database.sessions() as session:
        declared = session.execute(
            text(f"PRAGMA foreign_key_list({AUDIT_EVENT_TABLE_NAME})")
        ).all()

    assert declared == []
