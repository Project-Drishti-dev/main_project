"""18.8: a screening payload moved in the database answers altered, not cleared.

18.7 moved the commitment -- a ledger entry root -- while every leaf still
hashed, and named this vector as the one it left alone.  Here the other half
moves: the payload column of a stored audit event is rewritten by a statement
that never went through the writer, the digest stored beside the row is left
exactly as 10.2 sealed it, and the endpoint has to answer altered rather than
a clearance.

Three claims are held apart rather than folded into one answer:

- **the record is what moved.** The digest in the row is rebuilt here out of
  the columns 9.17 reads, over the payload as the writer left it, so the two
  halves disagree because a payload was rewritten and not because both were.
- **only the record asked about is condemned.** A moved payload answers
  altered while every event anchored beside it still answers verified under
  one root that did not move.
- **moved is not unreadable.** A payload that is still spellable answers
  altered; one that cannot be spelled answers unknown and names fewer checks.
  Neither answer carries the payload it is talking about.
"""

import uuid
from collections.abc import Iterator
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.emit import emit
from app.audit.event_types import SCREENING_CREATED
from app.audit.record import event_record
from app.audit.trail import completed_event_id
from app.audit.verify import CHECK_SENTENCES
from app.ledger.anchoring import anchor_batch, select_unanchored
from app.ledger.hashing import hash_record
from app.ledger.signing import load_signing_key
from app.ledger.store import SqliteLedger
from app.ledger.verification import (
    ALTERED,
    CHECK_PROOF,
    CHECK_RECORD,
    CHECK_ROOT,
    UNKNOWN,
    VERIFIED,
)
from app.main import app
from app.pipeline.tier0 import document
from app.screening import run_screening
from app.storage import db
from app.storage.models import AuditEvent, Base, LedgerEntry
from tests.fixtures import mrz_images

#: The path 18.8 exercises, spelled once so a case cannot drift from the route.
VERIFY_PATH = "/api/audit/{audit_id}/verify"

#: A value that lives only inside a payload, so an answer that echoed the
#: record back would carry it.
A_MARKER = "MRS-TESTCASE-4417"

#: The value written over it, which no writer ever sealed.
A_TAMPERED_MARKER = "MRS-TAMPERED-9021"

#: A key no writer put there, holding a value D48 refuses to spell.
A_FLOAT_KEY = "measured_share"

#: That value: a float, which canonical JSON has no canonical spelling for.
A_FLOAT = 0.42


class _Database(NamedTuple):
    """The one temporary database every case here runs on."""

    engine: Engine
    sessions: sessionmaker[Session]


@pytest.fixture
def database() -> Iterator[_Database]:
    """One in-memory database with the mapped schema, and a factory over it.

    The mapped schema and not a migrated file, because these cases issue the
    statement an attacker would and the 9.12 guards are exactly what a
    migrated file would refuse it with.
    """
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
    """A client over the app the verify is served by, on the same database."""
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


def _events(
    sessions: sessionmaker[Session], screening_id: uuid.UUID, how_many: int = 1
) -> tuple[AuditEvent, ...]:
    """how_many events of one screening, written by the writer itself.

    Emitted rather than hand-built, so what the walk reads back is what was
    sealed -- the one claim a rebuilt row could not make.
    """
    return tuple(
        emit(
            SCREENING_CREATED,
            screening_id,
            {"event": index, "note": A_MARKER},
            sessions=sessions,
        )
        for index in range(how_many)
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


def _screened(sessions: sessionmaker[Session]):
    """One real screening, so the id the create endpoint answers with exists."""
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


def _rewrite_payload(
    sessions: sessionmaker[Session], event_id: Any, payload: Any
) -> None:
    """Write payload onto one stored event, as a statement rather than an ORM.

    A Core UPDATE, so the 8.6 mapper guards -- which refuse an amendment from
    inside the service -- do not stand between the case and the row, and no
    column of the row other than the payload is named in the statement.
    """
    with sessions() as session:
        session.execute(
            update(AuditEvent)
            .where(AuditEvent.id == event_id)
            .values(payload=payload)
        )
        session.commit()


def _stored(sessions: sessionmaker[Session], event_id: Any) -> tuple | None:
    """The seven columns 9.17 reads, in that module own order, or None.

    Read through the same projection the walk uses, so a case can rebuild the
    digest that was sealed without asking the walk what it thinks it read.
    """
    with sessions() as session:
        row = session.execute(
            select(
                AuditEvent.batch_id,
                AuditEvent.record_hash,
                AuditEvent.record_salt,
                AuditEvent.event_type,
                AuditEvent.screening_id,
                AuditEvent.actor,
                AuditEvent.payload,
            ).where(AuditEvent.id == event_id)
        ).one_or_none()
    return None if row is None else tuple(row)


def _sealed_digest(row: tuple) -> str:
    """The digest the writer sealed for a stored row, rebuilt here.

    Spelled by the writers own record function (D66), so this is a second
    opinion about the row rather than a second copy of the walk.
    """
    (
        _batch_id,
        _record_hash,
        record_salt,
        event_type,
        screening_id,
        actor,
        payload,
    ) = row
    return hash_record(
        event_record(event_type, screening_id, actor, payload),
        bytes.fromhex(record_salt),
    )


def _with_note(payload: Any, note: str) -> dict:
    """The stored payload with one value overwritten and nothing else moved.

    Built as a fresh object, so the version keys 10.3 attached are still in
    it: a payload that kept its shape can still be spelled, which is the
    difference between a record that moved and one that cannot be read.
    """
    return {**payload, "note": note}


def _body(client: TestClient, audit_id: Any) -> dict:
    """The verify answer, once the endpoint has answered 200 for it."""
    response = client.get(VERIFY_PATH.format(audit_id=audit_id))
    assert response.status_code == 200, response.text
    return response.json()


# --- a record that moved ---------------------------------------------------


def test_a_moved_screening_payload_flips_the_answer_to_altered(
    client, database, ledger, signer
):
    """The line 18.8 states: a tampered payload is an altered record."""
    (event,) = _events(database.sessions, uuid.uuid4())
    (entry,) = _anchored(database, ledger, signer)
    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )

    body = _body(client, event.id)

    assert body["status"] == ALTERED
    assert body["batch_id"] == str(entry.batch_id)
    assert body["batch_root"] == entry.merkle_root


def test_the_same_record_answers_verified_before_its_payload_moved(
    client, database, ledger, signer
):
    """One answer before and one after, or the second of them proves nothing."""
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    assert _body(client, event.id)["status"] == VERIFIED

    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )

    assert _body(client, event.id)["status"] == ALTERED


# --- which of the two halves moved -----------------------------------------


def test_the_digest_the_row_carries_is_the_one_the_writer_sealed(
    client, database, ledger, signer
):
    """Only the payload column moved, so the stored digest is the old one.

    The digest is rebuilt here from the row as the writer left it.  If that
    still matches the column sitting beside the payload, then the halves
    disagree because a payload was rewritten and not because a digest was
    rewritten with it.
    """
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    sealed = _sealed_digest(_stored(database.sessions, event.id))

    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )
    row = _stored(database.sessions, event.id)

    assert row[1] == sealed
    assert _sealed_digest(row) != row[1]
    assert _body(client, event.id)["status"] == ALTERED


def test_every_column_beside_the_payload_is_as_the_writer_left_it(
    client, database, ledger, signer
):
    """The record is four columns, and this holds the other three of them."""
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    before = _stored(database.sessions, event.id)

    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )
    after = _stored(database.sessions, event.id)

    assert before[3:6] == after[3:6] == (
        SCREENING_CREATED,
        event.screening_id,
        event.actor,
    )
    assert after[6] != before[6]
    assert _body(client, event.id)["status"] == ALTERED


# --- what was checked ------------------------------------------------------


def test_the_walk_names_the_record_check_and_stops_there(
    client, database, ledger, signer
):
    """A comparison that came out wrong is named; a walk never taken is not.

    The proof is not walked once the record disagrees, so the answer carries
    no length rather than the length of nothing.
    """
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )

    body = _body(client, event.id)

    assert body["checked"] == [
        CHECK_SENTENCES[check] for check in (CHECK_ROOT, CHECK_RECORD)
    ]
    assert body["proof_length"] is None
    assert CHECK_SENTENCES[CHECK_PROOF] not in body["checked"]


# --- one record, and not the batch -----------------------------------------


def test_the_records_anchored_beside_it_still_answer_verified(
    client, database, ledger, signer
):
    """One moved payload does not condemn the batch it was anchored in."""
    events = _events(database.sessions, uuid.uuid4(), 3)
    (entry,) = _anchored(database, ledger, signer)
    _rewrite_payload(
        database.sessions,
        events[1].id,
        _with_note(events[1].payload, A_TAMPERED_MARKER),
    )

    moved = _body(client, events[1].id)
    beside = [_body(client, event.id) for event in (events[0], events[2])]

    assert moved["status"] == ALTERED
    assert [body["status"] for body in beside] == [VERIFIED, VERIFIED]
    assert all(body["batch_root"] == entry.merkle_root for body in beside)
    assert all(body["batch_id"] == moved["batch_id"] for body in beside)


def test_a_real_screening_answers_altered_once_its_payload_moves(
    client, database, ledger, signer
):
    """The vector on the event 11.1 answered with, not on a row built here."""
    row = _screened(database.sessions)
    audit_id = completed_event_id(row.id, sessions=database.sessions)
    assert audit_id is not None
    _anchored(database, ledger, signer)
    assert _body(client, audit_id)["status"] == VERIFIED

    _rewrite_payload(
        database.sessions,
        audit_id,
        _with_note(_stored(database.sessions, audit_id)[6], A_TAMPERED_MARKER),
    )

    assert _body(client, audit_id)["status"] == ALTERED


# --- moved is not unreadable -----------------------------------------------


def test_a_payload_that_cannot_be_spelled_answers_unknown_not_altered(
    client, database, ledger, signer
):
    """Moved and unreadable are two answers, and the checks say which.

    A float is D48 barred from canonical JSON, so the walk has no digest to
    compare against and stops one check earlier than a payload that merely
    moved.
    """
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    _rewrite_payload(
        database.sessions, event.id, {**event.payload, A_FLOAT_KEY: A_FLOAT}
    )

    body = _body(client, event.id)

    assert body["status"] == UNKNOWN
    assert body["checked"] == [CHECK_SENTENCES[CHECK_ROOT]]
    assert body["proof_length"] is None


def test_reading_the_moved_record_twice_answers_the_same_word(
    client, database, ledger, signer
):
    """A verify neither heals the row nor drifts away from what it found."""
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )

    first = _body(client, event.id)
    second = _body(client, event.id)

    assert first["status"] == second["status"] == ALTERED
    assert first["checked"] == second["checked"]


# --- what the answer is not allowed to do ----------------------------------


def test_the_answer_never_carries_the_tampered_value(
    client, database, ledger, signer
):
    """An officer is told the record moved, not what the row now says."""
    (event,) = _events(database.sessions, uuid.uuid4())
    _anchored(database, ledger, signer)
    _rewrite_payload(
        database.sessions, event.id, _with_note(event.payload, A_TAMPERED_MARKER)
    )

    response = client.get(VERIFY_PATH.format(audit_id=event.id))

    assert A_TAMPERED_MARKER not in response.text
    assert A_MARKER not in response.text
