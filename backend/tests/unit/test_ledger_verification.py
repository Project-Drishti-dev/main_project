"""9.17: ``verify_event`` -- reload, recompute, walk, and answer in one word.

The task's verify is "a test that mutates a stored payload flips the result
to ``altered``", so that is the first test here.  What the answer rests on is
pinned beside it, because each of those words is a separate claim:

- **the row is the record, not the object.**  Everything compared is read
  out of the database, so a payload changed on a detached event verifies and
  a row changed behind a pristine object does not.
- **the payload and the digest are checked separately, and neither check
  subsumes the other.**  A payload moved with its hash left stale is caught
  by the recomputation; a payload *and* its hash rewritten together walks to
  a root the log never signed, and only the walk answers for it.
- **siblings are cut from the rows**, so a row altered anywhere in the batch
  moves the proof this event walks.
- **the order is the row's.**  ``batch_index`` is where 9.16 cut the tree,
  so two rows stamped in one another's place do not walk to that root.
- **unknown is never a clearance.**  No row, no batch, no entry, no root, no
  leaf position, a payload no serialiser can spell, and a leaf set that
  cannot be rebuilt all answer it.
- **nothing but the event, the factory and the log is asked for**: the salt
  and the position come out of the row, so neither can be handed over by a
  caller that would have to be taken on trust.
- **the same row answers the same way twice.**  9.18: the digest is a
  function of the stored record and the row's own salt, so a repeat call
  recomputes one hash -- and another event's salt is another hash.
"""

import ast
import pathlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.audit.emit import emit
from app.audit.event_types import SCREENING_CREATED
from app.audit.record import event_record
from app.ledger import verification
from app.ledger.anchoring import (
    DEFAULT_BATCH_SIZE,
    anchor_batch,
    select_unanchored,
)
from app.ledger.hashing import hash_record
from app.ledger.salts import SaltedRecord, seal_record
from app.ledger.signing import Signer, load_signing_key
from app.ledger.store import Ledger, LedgerEntry as LedgerEntryRow, SqliteLedger
from app.ledger.verification import (
    ALTERED,
    UNKNOWN,
    VERIFICATION_STATUSES,
    VERIFIED,
    VerifyError,
    verify_event,
)
from app.storage import db
from app.storage.models import AuditEvent, LedgerEntry

#: The alembic configuration this service migrates with, derived from this
#: file for the reason ``test_ledger_store.py`` gives.
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"


def _url_for(database: pathlib.Path) -> str:
    """The URL naming ``database``, in the spelling 8.8's fixture uses."""
    return f"sqlite:///{database.as_posix()}"


@pytest.fixture(scope="module")
def migrated_databases(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[pathlib.Path, ...]:
    """Two migrated SQLite files: the one events are written to, and one that
    is not, for the claim about which database is read."""
    directory = tmp_path_factory.mktemp("ledger-verification")
    databases = (directory / "primary.db", directory / "other.db")
    for database in databases:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", _url_for(database))
            command.upgrade(Config(str(ALEMBIC_INI)), "head")
        assert database.exists()
    return databases


def _sessions_for(database: pathlib.Path) -> sessionmaker[Session]:
    """A session factory over ``database``, built the service's way."""
    return db.build_session_factory(db.build_engine(_url_for(database)))


@pytest.fixture
def sessions(
    migrated_databases: tuple[pathlib.Path, ...]
) -> sessionmaker[Session]:
    """A factory over the migrated file, emptied before the test ran.

    The migrated file is module-scoped, so it carries every event and every
    entry an earlier test left behind.  The empties are Core statements, so
    9.12's triggers and 8.6's mapper guards -- neither installed here --
    cannot refuse them.
    """
    factory = _sessions_for(migrated_databases[0])
    with factory() as session:
        session.execute(delete(AuditEvent))
        session.execute(delete(LedgerEntry))
        session.commit()
    return factory


@pytest.fixture
def other_sessions(
    migrated_databases: tuple[pathlib.Path, ...]
) -> sessionmaker[Session]:
    """A second factory, over a second migrated file no event is written to."""
    return _sessions_for(migrated_databases[1])


@pytest.fixture
def ledger(sessions: sessionmaker[Session]) -> SqliteLedger:
    """The log the events were anchored into."""
    return SqliteLedger(sessions)


@pytest.fixture
def signer() -> Signer:
    """A key loaded the way ``app.config`` hands one over."""
    return load_signing_key(None)


def _payload(index: int) -> dict[str, Any]:
    """A payload as 10.3 would attach one: an int and a label, and nothing
    ``D48`` refuses to spell."""
    return {"event": index, "station": "station-unset"}


def _sealed(index: int) -> tuple[uuid.UUID, SaltedRecord]:
    """One event's screening id beside the record 10.2 would have sealed."""
    screening_id = uuid.uuid4()
    sealed = seal_record(
        event_record(
            "screening_created", screening_id, "station-unset", _payload(index)
        )
    )
    return screening_id, sealed


def _store(
    sessions: sessionmaker[Session], how_many: int
) -> tuple[tuple[AuditEvent, ...], tuple[bytes, ...]]:
    """Write ``how_many`` unanchored events, oldest first, and answer them
    with the salts their digests were taken under.

    Each row carries the salt beside its digest, over 10.2's own record:
    this file's subject is 9.17, so the rows are built here rather than
    emitted, and the one test that emits really does so is named for it.
    """
    base = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    prepared = [_sealed(index) for index in range(how_many)]
    rows = tuple(
        AuditEvent(
            screening_id=screening_id,
            event_type="screening_created",
            actor="station-unset",
            payload=sealed.record["payload"],
            record_hash=sealed.digest,
            record_salt=sealed.salt_hex,
            created_at=base + timedelta(seconds=index),
        )
        for index, (screening_id, sealed) in enumerate(prepared)
    )
    with sessions() as session:
        session.add_all(rows)
        session.commit()
    events = tuple(select_unanchored(sessions))
    assert len(events) == how_many, "the run did not reach the database"
    return events, tuple(sealed.salt for _, sealed in prepared)


class _Run(NamedTuple):
    """One anchored batch, and the salts a caller needs to verify it."""

    events: tuple[AuditEvent, ...]
    salts: tuple[bytes, ...]
    entries: tuple[Any, ...]


def _anchored(
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
    how_many: int = DEFAULT_BATCH_SIZE,
) -> _Run:
    """Write ``how_many`` events, anchor them as 9.16 would, and answer both."""
    events, salts = _store(sessions, how_many)
    entries = anchor_batch(
        events, sessions=sessions, ledger=ledger, signer=signer
    )
    return _Run(events=events, salts=salts, entries=entries)


def _verify(
    run: _Run,
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    index: int = 0,
) -> str:
    """``verify_event`` with the two dependencies every test hands over, so
    each one can change only the thing it is about."""
    return verify_event(run.events[index], sessions=sessions, ledger=ledger)


class _Checked(NamedTuple):
    """One verification's answer beside the digest it recomputed."""

    status: str
    digest: str


def _check(
    run: _Run,
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    index: int,
) -> _Checked:
    """Verify one event, answering the status beside the digest 9.17
    recomputes over the row it read -- the two claims 9.18 pairs.
    """
    event = run.events[index]
    row = _row(sessions, event.id)
    assert row is not None, "the event did not reach the database"
    return _Checked(
        status=_verify(run, sessions, ledger, index),
        digest=hash_record(_record_of(sessions, event.id), run.salts[index]),
    )


def _rewrite(
    sessions: sessionmaker[Session], event_id: uuid.UUID, **columns: Any
) -> None:
    """Amend one row with a Core statement, so nothing of the ORM's identity
    map is in the way -- which is what a tamper is."""
    with sessions() as session:
        session.execute(
            update(AuditEvent)
            .where(AuditEvent.id == event_id)
            .values(**columns)
        )
        session.commit()


def _drop(sessions: sessionmaker[Session], *events: AuditEvent) -> None:
    """Remove rows with Core statements, the way a tamper would."""
    with sessions() as session:
        session.execute(
            delete(AuditEvent).where(
                AuditEvent.id.in_([event.id for event in events])
            )
        )
        session.commit()


def _row(
    sessions: sessionmaker[Session], event_id: uuid.UUID
) -> tuple[Any, ...] | None:
    """The payload, the digest and the batch id, straight off the row."""
    with sessions() as session:
        row = session.execute(
            select(
                AuditEvent.payload,
                AuditEvent.record_hash,
                AuditEvent.batch_id,
            ).where(AuditEvent.id == event_id)
        ).one_or_none()
    return None if row is None else (row[0], row[1], row[2])


def _record_of(
    sessions: sessionmaker[Session], event_id: uuid.UUID
) -> dict[str, Any]:
    """The record 10.2 hashed, rebuilt from the row as it reads back."""
    with sessions() as session:
        row = session.execute(
            select(
                AuditEvent.event_type,
                AuditEvent.screening_id,
                AuditEvent.actor,
                AuditEvent.payload,
            ).where(AuditEvent.id == event_id)
        ).one()
    return event_record(row[0], row[1], row[2], row[3])


def _created_at(
    sessions: sessionmaker[Session], event_id: uuid.UUID
) -> Any:
    """The row's ``created_at`` as SQLite hands it back."""
    with sessions() as session:
        return session.scalar(
            select(AuditEvent.created_at).where(AuditEvent.id == event_id)
        )


def _entries(
    sessions: sessionmaker[Session],
) -> tuple[tuple[Any, ...], ...]:
    """The log's rows as values, since two sessions never share an instance."""
    with sessions() as session:
        return tuple(
            (row.sequence, row.batch_id, row.merkle_root, row.signature)
            for row in session.scalars(
                select(LedgerEntry).order_by(LedgerEntry.sequence)
            )
        )


class _RecordingLedger(Ledger):
    """A log that answers ``None`` for every batch and records what it was
    asked for -- so a test can pin that a batch nobody named is never looked
    up at all, rather than looked up and found."""

    def __init__(self) -> None:
        self.asked: list[uuid.UUID] = []

    def append_batch(self, **kwargs: Any) -> LedgerEntryRow:
        raise AssertionError("verification appended to the log")

    def read_batch(self, batch_id: uuid.UUID) -> LedgerEntryRow | None:
        self.asked.append(batch_id)
        return None

    def iter_batches(self) -> Any:
        raise AssertionError("verification walked the log")


def test_a_verbatim_event_verifies(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The other end of the task's verify: nothing has moved, so every event
    in a default batch answers ``verified``.  The answers are listed one by
    one, so a sweep that walked nothing could not pass as this."""
    run = _anchored(sessions, ledger, signer)

    answers = [
        _verify(run, sessions, ledger, index) for index in range(len(run.events))
    ]

    assert answers == [VERIFIED] * DEFAULT_BATCH_SIZE


def test_a_verified_event_hashes_the_same_on_two_separate_calls(
    sessions: sessionmaker[Session],
    migrated_databases: tuple[pathlib.Path, ...],
    ledger: SqliteLedger,
    signer: Signer,
) -> None:
    """9.18.  The digest is a function of the stored payload and the event's
    own salt, so a second call recomputes the one the row was sealed under --
    ``verified`` twice over one hash.  The third call goes through a factory
    built fresh, so nothing carried over between them."""
    run = _anchored(sessions, ledger, signer, 3)

    first = _check(run, sessions, ledger, 1)
    second = _check(run, sessions, ledger, 1)
    third = _check(run, _sessions_for(migrated_databases[0]), ledger, 1)

    assert [first.status, second.status, third.status] == [VERIFIED] * 3
    assert first.digest == second.digest == third.digest
    assert first.digest == run.events[1].record_hash


def test_the_repeated_hash_is_the_one_this_salt_was_sealed_under(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Reproducible is not "the same under any salt": the same record under a
    neighbouring event's salt is another digest, and a row resealed under a
    salt it does not store is answered ``altered``.  So the repeat is a claim
    about a row and its own salt, never about a payload alone."""
    run = _anchored(sessions, ledger, signer, 3)
    stored = _row(sessions, run.events[1].id)
    assert stored is not None
    record = _record_of(sessions, run.events[1].id)

    assert hash_record(record, run.salts[1]) == stored[1]
    assert hash_record(record, run.salts[2]) != stored[1]
    assert _verify(run, sessions, ledger, 1) == VERIFIED

    _rewrite(sessions, run.events[1].id, record_salt=run.salts[2].hex())

    assert _verify(run, sessions, ledger, 1) == ALTERED


def test_the_repeated_hash_survives_the_round_trip_out_of_sqlite(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The row comes back through a JSON round trip and a naive
    ``created_at``, and neither moves the digest: the record read out of
    SQLite and the one the caller sealed hash identically.  The repeat is the
    database's spelling, not the anchoring's object."""
    run = _anchored(sessions, ledger, signer, 3)
    stored = _row(sessions, run.events[1].id)
    assert stored is not None
    held = run.events[1]

    assert _created_at(sessions, held.id).tzinfo is None
    assert (
        hash_record(_record_of(sessions, held.id), run.salts[1]) == stored[1]
    )
    assert (
        hash_record(
            event_record(
                held.event_type, held.screening_id, held.actor, held.payload
            ),
            run.salts[1],
        )
        == stored[1]
    )
    assert _verify(run, sessions, ledger, 1) == VERIFIED


def test_mutating_a_stored_payload_flips_the_answer_to_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The task's verify.  The payload in the database is rewritten and the
    hash beside it is left standing, so the pair no longer describes one
    record -- which is what a stale ``record_hash`` is for."""
    run = _anchored(sessions, ledger, signer)
    assert _verify(run, sessions, ledger, 3) == VERIFIED

    _rewrite(
        sessions,
        run.events[3].id,
        payload={"event": "tampered", "station": "station-unset"},
    )

    assert _verify(run, sessions, ledger, 3) == ALTERED
    assert _verify(run, sessions, ledger, 0) == VERIFIED


def test_a_payload_and_its_hash_rewritten_together_is_still_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The recomputation is made to pass -- the payload, the digest and the
    salt it was resealed under are all rewritten together -- so only the walk
    is left, and it answers because the anchored root committed to the
    digest this row used to carry."""
    run = _anchored(sessions, ledger, signer, 4)
    held = run.events[0]
    resealed = seal_record(
        event_record(
            held.event_type,
            held.screening_id,
            held.actor,
            {"event": "resealed"},
        )
    )
    _rewrite(
        sessions,
        held.id,
        payload=resealed.record["payload"],
        record_hash=resealed.digest,
        record_salt=resealed.salt_hex,
    )

    assert _verify(run, sessions, ledger, 0) == ALTERED
    # The batch is what the root commits to, so the events beside the
    # resealed one answer for the same root and are altered with it.
    assert _verify(run, sessions, ledger, 1) == ALTERED


def test_a_rewritten_digest_moves_the_whole_batch(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """One stored digest is one leaf, and the proof every other event walks is
    cut from the leaves beside it -- so a row whose digest moved takes the
    batch's answer with it, and only that event is tampered with."""
    run = _anchored(sessions, ledger, signer, 4)
    _rewrite(sessions, run.events[0].id, record_hash="cd" * 32)

    answers = [_verify(run, sessions, ledger, index) for index in range(4)]

    assert answers == [ALTERED] * 4


def test_a_stored_hash_changed_on_its_own_is_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The other half of the pair: the payload stands and the digest beside it
    is another row's, so neither half describes the other."""
    run = _anchored(sessions, ledger, signer, 4)
    _rewrite(sessions, run.events[1].id, record_hash=run.events[2].record_hash)

    assert _verify(run, sessions, ledger, 1) == ALTERED


def test_a_row_altered_elsewhere_in_the_batch_is_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The proof's siblings are cut from the rows, so a digest changed
    anywhere in the batch moves this event's walk even though its own two
    columns are untouched."""
    run = _anchored(sessions, ledger, signer, 5)
    _rewrite(sessions, run.events[4].id, record_hash="ab" * 32)

    assert _verify(run, sessions, ledger, 0) == ALTERED
    assert _verify(run, sessions, ledger, 4) == ALTERED


def test_a_batch_of_one_verifies_through_an_empty_proof(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """``D54``'s lone leaf is its own root, so the walk never moves and the
    answer is still ``verified`` rather than a failure to walk."""
    run = _anchored(sessions, ledger, signer, 1)

    assert _verify(run, sessions, ledger) == VERIFIED


def test_every_index_of_an_odd_batch_verifies(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Five leaves, so ``D53``'s promoted leaf sits in the middle of the sweep
    and its one-step-shorter path walks like every other."""
    run = _anchored(sessions, ledger, signer, 5)

    answers = [_verify(run, sessions, ledger, index) for index in range(5)]

    assert answers == [VERIFIED] * 5


def test_the_order_the_root_was_cut_in_is_what_verifies(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """``batch_index`` is the order the tree was cut in, so the rows read
    back in that order walk to the anchored root -- and two rows stamped in
    one another's place cut a different tree, which every event in the batch
    walks to and finds does not match."""
    run = _anchored(sessions, ledger, signer)
    assert _verify(run, sessions, ledger, 0) == VERIFIED

    _rewrite(sessions, run.events[0].id, batch_index=1)
    _rewrite(sessions, run.events[1].id, batch_index=0)

    answers = [_verify(run, sessions, ledger, index) for index in range(3)]

    assert answers == [ALTERED] * 3


def test_a_payload_changed_only_in_memory_verifies_anyway(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The row is the record: a detached object edited after it was read
    answers for nothing -- not its payload, not its digest, not the salt or
    the position beside them, and not even the anchoring's own stamp."""
    run = _anchored(sessions, ledger, signer, 3)
    run.events[1].payload = {"event": "never written"}
    run.events[1].record_hash = "cd" * 32
    run.events[1].record_salt = "ab" * 16
    run.events[1].batch_id = None
    run.events[1].batch_index = None

    assert _verify(run, sessions, ledger, 1) == VERIFIED


def test_a_row_changed_behind_a_pristine_object_is_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The same claim from the other side: the object still reads the payload
    that was written, and the answer follows the row rather than it."""
    run = _anchored(sessions, ledger, signer, 3)
    before = _row(sessions, run.events[2].id)
    _rewrite(sessions, run.events[2].id, payload={"event": "tampered"})

    assert _row(sessions, run.events[2].id) != before
    assert run.events[2].payload == _payload(2)
    assert _verify(run, sessions, ledger, 2) == ALTERED


def test_verification_writes_nothing_and_amends_nothing(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A reader that answered ``verified`` while amending a row would make its
    own answer worthless, so nothing is written and the log does not grow."""
    run = _anchored(sessions, ledger, signer, 3)
    entries = _entries(sessions)
    rows = tuple(_row(sessions, event.id) for event in run.events)

    assert _verify(run, sessions, ledger, 1) == VERIFIED

    assert _entries(sessions) == entries
    assert tuple(_row(sessions, event.id) for event in run.events) == rows


def test_it_reads_the_database_it_is_handed(
    sessions: sessionmaker[Session],
    other_sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
) -> None:
    """The factory is the dependency (``D62``): pointed at a file this event
    was never written to, the answer is ``unknown`` and never the row the
    other database holds."""
    run = _anchored(sessions, ledger, signer, 2)

    assert (
        verify_event(run.events[0], sessions=other_sessions, ledger=ledger)
        == UNKNOWN
    )


def test_an_event_nobody_anchored_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger
) -> None:
    """``batch_id IS NULL`` is a real state and not a zero batch: there is no
    root yet to walk a proof to."""
    events, _ = _store(sessions, 2)

    assert verify_event(events[0], sessions=sessions, ledger=ledger) == UNKNOWN


def test_an_unanchored_row_is_answered_without_asking_the_log(
    sessions: sessionmaker[Session],
) -> None:
    """``batch_id IS NULL`` is answered off the row.  There is no batch id to
    ask the log about, and the log answering ``None`` for the missing one is
    not the same claim -- so the query is not made at all."""
    events, _ = _store(sessions, 2)
    log = _RecordingLedger()

    assert verify_event(events[0], sessions=sessions, ledger=log) == UNKNOWN
    assert log.asked == []


def test_an_event_that_was_never_written_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """An id no row carries has nothing to read, which is a different answer
    from an event handed over with no id at all -- that one is refused."""
    run = _anchored(sessions, ledger, signer, 1)
    absent_salt = seal_record(_payload(99))
    absent = AuditEvent(
        screening_id=uuid.uuid4(),
        event_type="screening_created",
        actor="station-unset",
        payload=absent_salt.record,
        record_hash=absent_salt.digest,
        record_salt=absent_salt.salt_hex,
    )
    absent.id = uuid.uuid4()

    assert verify_event(absent, sessions=sessions, ledger=ledger) == UNKNOWN


def test_a_stamp_pointing_at_no_entry_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """``D62`` appends the entry before it stamps the rows, so a batch id can
    be carried by nothing: the answer is ``unknown``, never ``verified``."""
    run = _anchored(sessions, ledger, signer, 3)
    with sessions() as session:
        session.execute(delete(LedgerEntry))
        session.commit()

    assert _verify(run, sessions, ledger) == UNKNOWN


def test_an_entry_whose_root_is_not_a_digest_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger
) -> None:
    """``append_batch`` writes the root verbatim (``D57``), so prose in that
    column leaves no commitment to compare against rather than a record that
    moved."""
    events, _ = _store(sessions, 2)
    batch_id = uuid.uuid4()
    with sessions() as session:
        session.execute(
            update(AuditEvent)
            .where(AuditEvent.id.in_([event.id for event in events]))
            .values(batch_id=batch_id)
        )
        session.commit()
    ledger.append_batch(
        batch_id=batch_id, merkle_root="not a root", signature="00" * 64
    )

    assert verify_event(events[0], sessions=sessions, ledger=ledger) == UNKNOWN


def test_a_row_with_no_position_in_its_batch_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A batch is rebuilt from the rows in ``batch_index`` order, so one row
    carrying no position leaves no order to rebuild at all -- and no answer
    for the events beside it either."""
    run = _anchored(sessions, ledger, signer, 3)

    _rewrite(sessions, run.events[1].id, batch_index=None)

    assert _verify(run, sessions, ledger, 1) == UNKNOWN
    assert _verify(run, sessions, ledger, 0) == UNKNOWN


def test_a_batch_that_lost_a_row_is_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Every leaf is needed to rebuild the tree, so a batch short a row is
    rebuilt from what is left -- a different tree, which the walk answers
    ``altered`` rather than ``unknown``, because the order itself was still
    readable.  A missing *position* is the other answer; see above."""
    run = _anchored(sessions, ledger, signer, 3)
    _drop(sessions, run.events[2])

    assert _row(sessions, run.events[2].id) is None
    assert _verify(run, sessions, ledger, 0) == ALTERED


def test_a_sibling_hash_that_is_not_a_digest_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Whatever truncated another row's hash, this event's leaf can no longer
    be put beside it, and the answer says so instead of guessing."""
    run = _anchored(sessions, ledger, signer, 3)
    _rewrite(sessions, run.events[2].id, record_hash="9f86d081")

    assert _verify(run, sessions, ledger, 0) == UNKNOWN


def test_a_payload_the_serialiser_refuses_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """``D48`` bars a ``float`` from a hashed record, so a score stored as one
    has no digest to recompute: a question this cannot answer rather than one
    that came out wrong."""
    run = _anchored(sessions, ledger, signer, 2)
    _rewrite(sessions, run.events[1].id, payload={"score": 0.5})

    assert _verify(run, sessions, ledger, 1) == UNKNOWN


@pytest.mark.parametrize("where", ["event"])
def test_a_value_that_is_not_an_event_is_refused(
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
    where: str,
) -> None:
    """Only an ``AuditEvent`` carries an id to read, and a value that is not
    one is a caller at fault rather than a row to answer about."""
    run = _anchored(sessions, ledger, signer, 2)
    event: Any = "not an event" if where == "event" else run.events[0]

    with pytest.raises(TypeError):
        verify_event(event, sessions=sessions, ledger=ledger)


@pytest.mark.parametrize("where", ["event"])
def test_an_event_that_was_never_written_is_refused(
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
    where: str,
) -> None:
    """An event with no id was never written, so no row carries it and the
    question cannot be asked -- not ``unknown``, which is about a row that
    exists."""
    run = _anchored(sessions, ledger, signer, 2)
    transient = AuditEvent(
        screening_id=uuid.uuid4(),
        event_type="screening_created",
        actor="station-unset",
        payload=_payload(0),
        record_hash=run.events[0].record_hash,
        record_salt=run.events[0].record_salt,
    )
    assert transient.id is None
    event: Any = transient if where == "event" else run.events[0]

    with pytest.raises(VerifyError):
        verify_event(event, sessions=sessions, ledger=ledger)


def test_two_rows_claiming_one_position_is_unknown(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A position two rows hold would put two leaves where the anchor put
    one, so there is no tree to cut a proof from -- and no way to choose
    between them."""
    run = _anchored(sessions, ledger, signer, 2)

    _rewrite(sessions, run.events[1].id, batch_index=0)

    assert _verify(run, sessions, ledger, 0) == UNKNOWN


@pytest.mark.parametrize("stored", ["zz" * 16, "ab", None])
def test_a_stored_salt_that_cannot_be_read_is_unknown(
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
    stored: Any,
) -> None:
    """10.2 writes :data:`~app.ledger.salts.SALT_BYTES` bytes as hex beside
    the digest, and a row carrying anything else has no salt to recompute
    with.  That is ``unknown`` rather than a refusal: the salt is the row's
    own, not an argument a caller got wrong."""
    run = _anchored(sessions, ledger, signer, 2)

    _rewrite(sessions, run.events[0].id, record_salt=stored)

    assert _verify(run, sessions, ledger, 0) == UNKNOWN


def test_an_event_written_by_the_writer_verifies_against_its_root(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """10.2's writer and 9.17's reader with no hand-built hash between them:
    what the writer seals is what the reader rebuilds, or every event this
    project records would answer ``altered``."""
    event = emit(
        SCREENING_CREATED, uuid.uuid4(), {"event": 0}, sessions=sessions
    )

    (entry,) = anchor_batch(
        (event,), sessions=sessions, ledger=ledger, signer=signer
    )

    assert entry.batch_id == event.batch_id
    assert verify_event(event, sessions=sessions, ledger=ledger) == VERIFIED


def test_a_version_the_writer_attached_is_rewritable_only_as_altered(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """10.3's two keys are inside the record rather than beside it: the event
    verifies while the attached versions are the ones handed over, and
    rewriting one on the row answers ``altered`` rather than ``verified``."""
    event = emit(
        SCREENING_CREATED,
        uuid.uuid4(),
        {"event": 0},
        sessions=sessions,
        ruleset_version="0.1.0",
        model_versions={"tier2.forgery": "stub-1"},
    )
    anchor_batch((event,), sessions=sessions, ledger=ledger, signer=signer)

    assert verify_event(event, sessions=sessions, ledger=ledger) == VERIFIED

    _rewrite(
        sessions,
        event.id,
        payload={**event.payload, "ruleset_version": "9.9.9"},
    )

    assert verify_event(event, sessions=sessions, ledger=ledger) == ALTERED


def test_the_three_answers_are_the_ones_the_task_names() -> None:
    """A closed vocabulary, because a reader of an audit trail asks what the
    word means and three is the whole of it."""
    assert VERIFICATION_STATUSES == ("verified", "altered", "unknown")
    assert (VERIFIED, ALTERED, UNKNOWN) == VERIFICATION_STATUSES


def test_the_module_adds_no_serialiser_and_no_hash_of_its_own() -> None:
    """``D48``'s second serialiser and ``D51``'s second hash are both refused
    here, and so is ``D66``'s second record: the digest comes from
    ``hashing.hash_record``, the record from ``audit.record``, every leaf,
    node and walk from ``merkle``, and this module reads no clock of its
    own."""
    tree = ast.parse(
        pathlib.Path(verification.__file__).read_text(encoding="utf-8")
    )
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    named = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }

    assert "hashlib" not in imported
    assert "datetime" not in imported
    assert "canonical_json" not in named
    assert {"hash_record", "build_tree", "leaf_hash", "verify_proof"} <= named
    assert "event_record" in named, (
        "the record is spelled by the writer's own module, so a second "
        "spelling cannot make verified a claim about a value nobody hashed"
    )
    assert "read_digest" in named
