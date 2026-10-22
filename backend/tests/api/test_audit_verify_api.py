"""18.7: ``GET /api/audit/{audit_id}/verify`` answers in three words plus proof.

The endpoint reports what 9.17 walked and what it read on the way, so the
cases below hold three separate claims apart rather than one answer:

- **the word is 9.17's own.** The status is the three names that module
  answers with, the batch root is the log's own column and the proof length is
  the path the tree really cuts -- each read back out of the database rather
  than off the object the walk was handed.
- **only the checks that ran are named.** A clearance and an answer that
  stopped before it compared anything are both 200, so ``checked`` says which
  it was, and an event no batch has claimed names nothing at all.
- **nothing read off a document reaches the answer.** The sentences are fixed
  prose, and the payload that was hashed beside the digest is not echoed back.

The anchor is the real 9.16 and the walk is the real 9.17, because reporting a
proof is only a claim about a trail that can still be walked.  The two cases
that tamper do it through the same statements an attacker would, so the
answer they move is the endpoint's.
"""

import contextlib
import typing
import uuid
from collections.abc import Iterator
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.api.rate_limit import RateLimiter
from app.audit.emit import emit
from app.audit.event_types import SCREENING_CREATED
from app.audit.trail import completed_event_id
from app.audit.verify import CHECK_SENTENCES, ExplainError, explain
from app.ledger.anchoring import anchor_batch, select_unanchored
from app.ledger.merkle import build_tree, read_digest
from app.ledger.signing import load_signing_key
from app.ledger.store import SqliteLedger
from app.ledger.verification import (
    ALTERED,
    CHECK_PROOF,
    CHECK_RECORD,
    CHECK_ROOT,
    CHECKS,
    UNKNOWN,
    VERIFICATION_STATUSES,
    VERIFIED,
    Verification,
    verification_of,
)
from app.main import app
from app.pipeline.tier0 import document
from app.schemas import AuditVerificationResponse
from app.screening import run_screening
from app.storage import db
from app.storage.models import (
    LEDGER_ENTRY_TABLE_NAME,
    SCREENING_TABLE_NAME,
    AuditEvent,
    Base,
    LedgerEntry,
)
from tests.fixtures import mrz_images

#: The path 18.7 adds, spelled once so a case cannot drift from the contract.
VERIFY_PATH = "/api/audit/{audit_id}/verify"

#: A value that lives only in one payload, so an answer that echoed the record
#: back would carry it.
A_MARKER = "MRS-TESTCASE-4417"

#: A root that is a digest and is not the batch's own, for the case that moves
#: the commitment rather than the record.
ANOTHER_ROOT = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


class _Database(NamedTuple):
    """The one temporary database every case here runs on."""

    engine: Engine
    sessions: sessionmaker[Session]


@pytest.fixture
def database() -> Iterator[_Database]:
    """One in-memory database with the mapped schema, and a factory over it.

    The mapped schema and not a migrated file, because two cases here issue
    the statements an attacker would and 9.12's guards are exactly what a
    migrated file would refuse them with.
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
    sessions: sessionmaker[Session], how_many: int = 1
) -> tuple[AuditEvent, ...]:
    """``how_many`` events written by 10.2's own writer, in order.

    Emitted rather than hand-built, so what the walk reads back is what the
    writer sealed -- the one claim a rebuilt row could not make.
    """
    return tuple(
        emit(
            SCREENING_CREATED,
            uuid.uuid4(),
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


def _digests(
    sessions: sessionmaker[Session], batch_id: Any
) -> tuple[bytes, ...]:
    """A batch's stored digests in the order it was anchored."""
    with sessions() as session:
        rows = session.execute(
            select(AuditEvent.record_hash)
            .where(AuditEvent.batch_id == batch_id)
            .order_by(AuditEvent.batch_index, AuditEvent.id)
        ).all()
    return tuple(read_digest(row[0]) for row in rows)


def _rewrite(sessions: sessionmaker[Session], event_id: Any, **values: Any) -> None:
    """Write ``values`` onto one stored event, as a statement rather than an ORM.

    A Core ``UPDATE``, so 8.6's mapper guards -- which refuse an amendment from
    inside the service -- do not stand between the case and the row.
    """
    with sessions() as session:
        session.execute(
            update(AuditEvent).where(AuditEvent.id == event_id).values(**values)
        )
        session.commit()

def _rewrite_root(
    sessions: sessionmaker[Session], batch_id: Any, root: str
) -> None:
    """Write ``root`` onto one ledger entry, as a statement rather than an ORM.

    A Core ``UPDATE``, which is how a database that was never migrated answers
    9.12's refusal -- and it is the only way a root can move under a batch that
    was anchored while every leaf still hashes.
    """
    with sessions() as session:
        session.execute(
            update(LedgerEntry)
            .where(LedgerEntry.batch_id == batch_id)
            .values(merkle_root=root)
        )
        session.commit()


def _body(client: TestClient, audit_id: Any) -> dict:
    """The verify answer, once the endpoint has answered 200 for it."""
    response = client.get(VERIFY_PATH.format(audit_id=audit_id))
    assert response.status_code == 200, response.text
    return response.json()


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


# --- the answer a standing record gets -------------------------------------


def test_an_anchored_event_answers_verified_through_the_real_app(
    client, database, ledger, signer
):
    """The line 18.7's task states: a sound record walks, and this says so."""
    (event,) = _events(database.sessions)
    (entry,) = _anchored(database, ledger, signer)

    body = _body(client, event.id)

    assert body["status"] == VERIFIED
    assert body["batch_id"] == str(entry.batch_id)
    assert verification_of(event, sessions=database.sessions, ledger=ledger).status == (
        VERIFIED
    )


def test_the_word_answered_is_one_of_the_three_9_17_answers(
    client, database, ledger, signer
):
    """The status is read off that module's own vocabulary, not retyped here."""
    (event,) = _events(database.sessions)
    _anchored(database, ledger, signer)

    assert _body(client, event.id)["status"] in VERIFICATION_STATUSES


def test_the_batch_root_answered_is_the_column_the_log_holds(
    client, database, ledger, signer
):
    """D57's verbatim column is reported as it stands, not re-encoded."""
    (event,) = _events(database.sessions)
    (entry,) = _anchored(database, ledger, signer)

    root = _body(client, event.id)["batch_root"]

    assert root == entry.merkle_root
    assert read_digest(root).hex() == entry.merkle_root


def test_the_proof_length_answered_is_the_path_the_tree_really_cuts(
    client, database, ledger, signer
):
    """The number is the walk's own, rebuilt here from the stored digests."""
    events = _events(database.sessions, 4)
    (entry,) = _anchored(database, ledger, signer)
    walked = build_tree(_digests(database.sessions, entry.batch_id)).proof_for(2)

    body = _body(client, events[2].id)

    assert body["proof_length"] == len(walked)
    assert body["proof_length"] == 2


def test_two_records_in_one_batch_report_one_root_and_their_own_paths(
    client, database, ledger, signer
):
    """The root is the batch's, so it cannot be the record's own."""
    events = _events(database.sessions, 4)
    (entry,) = _anchored(database, ledger, signer)

    first = _body(client, events[0].id)
    last = _body(client, events[3].id)

    assert first["batch_id"] == last["batch_id"] == str(entry.batch_id)
    assert first["batch_root"] == last["batch_root"] == entry.merkle_root
    assert first["proof_length"] == last["proof_length"]


def test_the_id_the_create_endpoint_answered_with_is_the_one_verified(
    client, database, ledger, signer
):
    """The officer holds what 11.1 answered, so that is what this route reads."""
    row = _screened(database.sessions)
    _anchored(database, ledger, signer)
    audit_id = completed_event_id(row.id, sessions=database.sessions)
    assert audit_id is not None

    body = _body(client, audit_id)

    assert body["audit_id"] == str(audit_id)
    assert body["status"] == VERIFIED


# --- what was checked, and what was not ------------------------------------


def test_every_check_that_ran_is_named_in_plain_language(
    client, database, ledger, signer
):
    """One sentence per check, in the walk's order, from the module's own table."""
    (event,) = _events(database.sessions)
    _anchored(database, ledger, signer)
    walked = verification_of(event, sessions=database.sessions, ledger=ledger)

    checked = _body(client, event.id)["checked"]

    assert list(walked.checked) == list(CHECKS)
    assert checked == [CHECK_SENTENCES[check] for check in walked.checked]
    assert checked == list(explain(walked))
    assert all(sentence.endswith(".") for sentence in checked)


def test_every_check_9_17_can_complete_has_a_sentence():
    """A step added to the walk without a sentence here would be a silent gap."""
    assert set(CHECK_SENTENCES) == set(CHECKS)


def test_a_check_this_table_cannot_name_is_refused():
    """Not a KeyError out of a lookup: the step is named, the value is not."""
    with pytest.raises(ExplainError):
        explain(Verification(VERIFIED, checked=("a-check-nobody-named",)))


def test_an_event_no_batch_has_claimed_names_no_check_at_all(
    client, database
):
    """``unknown`` is an answer about nothing to compare, and says so."""
    (event,) = _events(database.sessions)

    body = _body(client, event.id)

    assert body["status"] == UNKNOWN
    assert body["checked"] == []
    assert body["batch_id"] is None
    assert body["batch_root"] is None
    assert body["proof_length"] is None


def test_a_salt_that_cannot_be_read_names_only_the_check_that_ran(
    client, database, ledger, signer
):
    """A check that could not run is absent rather than reported as passed."""
    (event,) = _events(database.sessions)
    (entry,) = _anchored(database, ledger, signer)
    _rewrite(database.sessions, event.id, record_salt="zz")

    body = _body(client, event.id)

    assert body["status"] == UNKNOWN
    assert body["checked"] == [CHECK_SENTENCES[CHECK_ROOT]]
    assert body["batch_root"] == entry.merkle_root
    assert body["proof_length"] is None


def test_an_id_no_row_carries_answers_unknown_rather_than_404(client, database):
    """The question was answerable, and the answer is that nothing is there."""
    body = _body(client, uuid.uuid4())

    assert body["status"] == UNKNOWN
    assert body["checked"] == []


def test_an_id_that_is_not_a_uuid_is_refused_in_the_envelope(client):
    """FastAPI answers before the route runs, in the one error shape."""
    response = client.get(VERIFY_PATH.format(audit_id="not-a-uuid"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_the_status_the_schema_allows_is_9_17s_own_three():
    """The response model pins the vocabulary, and it is that module's."""
    annotation = AuditVerificationResponse.model_fields["status"].annotation

    assert typing.get_args(annotation) == VERIFICATION_STATUSES


# --- a moved commitment, and a moved record --------------------------------


def test_a_root_that_moved_flips_the_answer_to_altered(
    client, database, ledger, signer
):
    """The record still hashes and the path no longer ends at the root.

    18.8's case is the other vector: this one moves the commitment the batch
    was anchored under, so the record check passes and the walk answers.
    """
    (event,) = _events(database.sessions)
    (entry,) = _anchored(database, ledger, signer)
    _rewrite_root(database.sessions, entry.batch_id, ANOTHER_ROOT)

    body = _body(client, event.id)

    assert body["status"] == ALTERED
    assert body["checked"] == [
        CHECK_SENTENCES[check] for check in (CHECK_ROOT, CHECK_RECORD, CHECK_PROOF)
    ]
    assert body["proof_length"] == 0


def test_the_same_record_verified_before_the_root_moved(
    client, database, ledger, signer
):
    """The comparison is one answer before and one after, or it proves nothing."""
    (event,) = _events(database.sessions)
    (entry,) = _anchored(database, ledger, signer)
    assert _body(client, event.id)["status"] == VERIFIED

    _rewrite_root(database.sessions, entry.batch_id, ANOTHER_ROOT)

    assert _body(client, event.id)["status"] == ALTERED


# --- what the read is not allowed to do ------------------------------------


def test_the_answer_holds_nothing_but_the_six_named_fields(
    client, database, ledger, signer
):
    """The whole body, read off one answer rather than counted."""
    (event,) = _events(database.sessions)
    _anchored(database, ledger, signer)

    body = _body(client, event.id)

    assert set(body) == {
        "audit_id",
        "status",
        "batch_id",
        "batch_root",
        "proof_length",
        "checked",
    }


def test_no_value_read_off_the_document_reaches_the_answer(
    client, database, ledger, signer
):
    """The payload is hashed, never echoed: the marker is in no field of it."""
    (event,) = _events(database.sessions)
    _anchored(database, ledger, signer)

    response = client.get(VERIFY_PATH.format(audit_id=event.id))

    assert A_MARKER not in response.text
    assert str(event.payload) not in response.text


def test_the_read_issues_no_write_statement(client, database, ledger, signer):
    """A verify that writes would be the alteration it reports."""
    (event,) = _events(database.sessions)
    _anchored(database, ledger, signer)

    with _issued(database.engine) as statements:
        assert _body(client, event.id)["status"] == VERIFIED

    written = [
        statement
        for statement in statements
        if statement.split(None, 1)[0].upper()
        in {"INSERT", "UPDATE", "DELETE"}
    ]
    assert written == []


def test_the_read_spends_no_analysis_budget(client, database, ledger, signer):
    """11.8's guard sits on the two analysis routes, and this is not one.

    The two refused calls are the control: with a one-request budget armed,
    the analyse route does spend and this one still answers.
    """
    (event,) = _events(database.sessions)
    _anchored(database, ledger, signer)
    shipped = app.state.rate_limiter
    app.state.rate_limiter = RateLimiter(1)
    try:
        assert client.post("/api/analyze").status_code == 422
        assert client.post("/api/analyze").status_code == 429

        assert _body(client, event.id)["status"] == VERIFIED
        assert _body(client, event.id)["status"] == VERIFIED
    finally:
        app.state.rate_limiter = shipped


def test_the_read_leaves_the_screening_row_untouched(
    client, database, ledger, signer
):
    """8.5's row is not this route's business, so no statement names it."""
    row = _screened(database.sessions)
    audit_id = completed_event_id(row.id, sessions=database.sessions)
    _anchored(database, ledger, signer)

    with _issued(database.engine) as statements:
        _body(client, audit_id)

    against_the_log = [
        s for s in statements
        if LEDGER_ENTRY_TABLE_NAME.upper() in s.upper()
    ]
    assert against_the_log
    assert all("SELECT" in s.upper() for s in against_the_log)
