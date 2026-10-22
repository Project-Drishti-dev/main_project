"""9.16: ``anchor_batch`` -- root, sign, append, stamp.

The task's verify is "1 ledger row for 25 events and every event carries the
batch id", so that is the first test here.  What the row rests on is pinned
beside it, because each of those words is a separate claim:

- **the root is over the *stored* digests, in the caller's order.**  9.15
  commits to the order the events were given in, and the digests come out
  of the database rather than off the objects, so a row whose in-memory
  hash has drifted cannot be rooted by what it used to say.
- **the signature is over the root, and the log is hex.**  Root and
  signature are widened on the way in and decode back to the bytes the
  signer signed, which is the spelling ``D62`` picks for the text columns.
- **the entry is appended before the stamp, and the stamp is conditional.**
  The write carries ``WHERE batch_id IS NULL`` so a row claimed in between
  is not taken from whoever claimed it -- held against the emitted
  statement, the way ``iter_batches``' order is.
- **an event is anchored once.**  Already-stamped rows are refused with the
  log untouched, which is what makes re-running the reader safe.
- **nothing to anchor is not an error.**  ``D54`` refuses a tree over no
  leaves, so a quiet window answers ``()`` and writes no entry.
- **the run is the reader's.**  ``select_unanchored`` is the first thing in
  Part 9 that chooses which events go together, and its order is the order
  the next anchor commits to.
- **a refused size or row touches nothing.**  The refusals come before the
  first write, so a bad run cannot leave a half-anchored batch behind.
"""

import contextlib
import inspect
import pathlib
import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, List, NamedTuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, delete, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.ledger.anchoring import (
    DEFAULT_BATCH_SIZE,
    AnchorError,
    anchor_batch,
    select_unanchored,
)
from app.ledger.merkle import build_tree
from app.ledger.salts import seal_record
from app.ledger.signing import Signer, load_signing_key, verify_signature
from app.ledger.store import SqliteLedger
from app.storage import db
from app.storage.models import AuditEvent, LedgerEntry

#: The alembic configuration this service migrates with, derived from this
#: file for the reason ``test_ledger_store.py`` gives.
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"


def _url_for(database: pathlib.Path) -> str:
    """The URL naming ``database``, in the spelling 8.8's fixture uses."""
    return f"sqlite:///{database.as_posix()}"


class _Databases(NamedTuple):
    """Two migrated SQLite files, for the claim about who owns the session."""

    primary: pathlib.Path
    other: pathlib.Path


@pytest.fixture(scope="module")
def migrated_databases(tmp_path_factory: pytest.TempPathFactory) -> _Databases:
    """Two ``tmp_path`` files migrated to head, and nothing else in them."""
    directory = tmp_path_factory.mktemp("ledger-anchoring")
    databases = _Databases(directory / "primary.db", directory / "other.db")
    for database in tuple(databases):
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", _url_for(database))
            command.upgrade(Config(str(ALEMBIC_INI)), "head")
        assert database.exists()
    return databases


def _sessions_for(database: pathlib.Path) -> sessionmaker[Session]:
    """A session factory over ``database``, built the service's way."""
    return db.build_session_factory(db.build_engine(_url_for(database)))


@pytest.fixture
def sessions(migrated_databases: _Databases) -> sessionmaker[Session]:
    """A factory over the migrated file, emptied before the test ran.

    The migrated file is module-scoped, so it carries every event and every
    entry an earlier test left behind, and several of the claims below are
    about a log holding nothing at all.  The empties are issued as Core
    statements, so 9.12's triggers and 8.6's mapper guards -- neither
    installed here -- cannot refuse them.
    """
    factory = _sessions_for(migrated_databases.primary)
    with factory() as session:
        session.execute(delete(AuditEvent))
        session.execute(delete(LedgerEntry))
        session.commit()
    return factory


@pytest.fixture
def other_sessions(migrated_databases: _Databases) -> sessionmaker[Session]:
    """A second factory, over a second migrated file."""
    return _sessions_for(migrated_databases.other)


@pytest.fixture
def ledger(sessions: sessionmaker[Session]) -> SqliteLedger:
    """The log the events are anchored into."""
    return SqliteLedger(sessions)


@pytest.fixture
def signer() -> Signer:
    """A key loaded the way ``app.config`` hands one over."""
    return load_signing_key(None)


def _a_digest(index: int) -> str:
    """A record hash as 10.2 would have written it, one per event."""
    return seal_record({"event": index}).digest


def _store(
    sessions: sessionmaker[Session], how_many: int
) -> tuple[AuditEvent, ...]:
    """Write ``how_many`` unanchored events, oldest first, and answer them."""
    base = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    rows = tuple(
        AuditEvent(
            screening_id=uuid.uuid4(),
            event_type="screening_created",
            actor="station-unset",
            payload={"event": index},
            record_hash=_a_digest(index),
            created_at=base + timedelta(seconds=index),
        )
        for index in range(how_many)
    )
    with sessions() as session:
        session.add_all(rows)
        session.commit()
    return tuple(select_unanchored(sessions))


def _stored_events(
    sessions: sessionmaker[Session],
) -> tuple[AuditEvent, ...]:
    """Every stored event, read back over a session that did not write it."""
    with sessions() as session:
        return tuple(
            session.scalars(select(AuditEvent).order_by(AuditEvent.created_at))
        )


def _entries(
    sessions: sessionmaker[Session],
) -> tuple[LedgerEntry, ...]:
    """Every row in the log, read back over a fresh session."""
    with sessions() as session:
        return tuple(
            session.scalars(select(LedgerEntry).order_by(LedgerEntry.sequence))
        )


def _digests(events: Sequence[AuditEvent]) -> tuple[bytes, ...]:
    """The stored digests of ``events``, unwidened and in their own order."""
    return tuple(bytes.fromhex(event.record_hash) for event in events)


def _as_utc(moment: datetime) -> datetime:
    """Read back a stamp SQLite returned with no ``tzinfo``, as UTC."""
    return moment.replace(tzinfo=timezone.utc)


def _anchor(
    events: Sequence[AuditEvent],
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
    **overrides: Any,
) -> tuple[Any, ...]:
    """``anchor_batch`` with the three dependencies every test hands over."""
    return anchor_batch(
        events,
        sessions=sessions,
        ledger=ledger,
        signer=signer,
        **overrides,
    )


@contextlib.contextmanager
def _emitted(sessions: sessionmaker[Session]) -> Iterator[List[str]]:
    """Collect every statement the engine issues inside the block."""
    engine: Engine = sessions.kw["bind"]
    seen: List[str] = []

    def _record(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _record)


# --- the task's claim -------------------------------------------------------


def test_twenty_five_events_give_one_ledger_row_and_every_event_is_stamped(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """9.16's verify, read back over a session that did not write it.

    One row rather than 25 is the whole claim: the log commits to a batch,
    not to each event in it, and the events reach that entry through the
    ``batch_id`` stamped on them.
    """
    events = _store(sessions, 25)

    entries = _anchor(events, sessions, ledger, signer)

    rows = _entries(sessions)
    assert len(rows) == 1
    assert len(entries) == 1
    assert entries[0].sequence == rows[0].sequence

    stored = _stored_events(sessions)
    assert len(stored) == 25
    assert {event.batch_id for event in stored} == {rows[0].batch_id}


def test_the_events_the_caller_still_holds_carry_the_batch_id(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """9.15 handed the rows over by identity so 9.16 could stamp them."""
    events = _store(sessions, 3)

    (entry,) = _anchor(events, sessions, ledger, signer)

    assert {event.batch_id for event in events} == {entry.batch_id}


def test_every_anchored_row_carries_its_own_position_in_the_batch(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """9.17 rebuilds the tree from the rows in ``batch_index`` order, so the
    order the root was cut in is stored rather than handed over by whoever
    anchored (``D66``)."""
    events = _store(sessions, 4)

    _anchor(events, sessions, ledger, signer)

    stored = _stored_events(sessions)
    assert sorted(event.batch_index for event in stored) == [0, 1, 2, 3]
    assert [event.batch_index for event in events] == [0, 1, 2, 3]


def test_the_reader_answers_nothing_once_the_run_is_anchored(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The reader picks the run, and the stamp is what retires it."""
    events = _store(sessions, 5)

    _anchor(events, sessions, ledger, signer)

    assert select_unanchored(sessions) == ()


def test_an_anchored_entry_can_be_read_back_by_its_batch_id(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """9.17 finds the entry a stamp points at; this is that lookup."""
    events = _store(sessions, 2)

    (entry,) = _anchor(events, sessions, ledger, signer)

    found = ledger.read_batch(events[0].batch_id)

    assert found is not None
    assert found.sequence == entry.sequence
    assert found.merkle_root == entry.merkle_root


# --- what the root commits to ----------------------------------------------


def test_the_root_is_the_tree_over_the_stored_digests_in_the_batch_order(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """9.15's order is the order the root commits to."""
    events = _store(sessions, 7)
    reversed_run = tuple(reversed(events))

    (entry,) = _anchor(reversed_run, sessions, ledger, signer)

    expected = build_tree(_digests(reversed_run)).root.hex()
    assert entry.merkle_root == expected


def test_the_digest_comes_from_the_database_not_the_object(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A row whose in-memory hash has drifted is rooted by what is stored.

    The caller holds the same object the reader answered, so drifting it
    stands for a caller that passed a hand-built row instead.  Rooting that
    hash would sign a root 9.17 could never recompute from the row.
    """
    (event,) = _store(sessions, 1)
    stored_hash = event.record_hash
    event.record_hash = _a_digest(99)

    (entry,) = _anchor((event,), sessions, ledger, signer)

    expected = build_tree((bytes.fromhex(stored_hash),)).root.hex()
    assert entry.merkle_root == expected


def test_the_signature_verifies_against_the_stored_root(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The log is hex, and it decodes back to what was signed."""
    events = _store(sessions, 4)

    (entry,) = _anchor(events, sessions, ledger, signer)

    root = bytes.fromhex(entry.merkle_root)
    signature = bytes.fromhex(entry.signature)
    assert len(entry.merkle_root) == 64
    assert len(entry.signature) == 128
    assert entry.merkle_root == entry.merkle_root.lower()
    assert verify_signature(signer.public_key, signature, root)
    assert not verify_signature(signer.public_key, signature, bytes(32))


def test_each_batch_gets_its_own_entry_and_its_own_id(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """100 events at the default size are four batches and four entries."""
    events = _store(sessions, 100)
    assert len(events) == 100

    entries = _anchor(events, sessions, ledger, signer)

    assert len(entries) == 4
    assert len({entry.batch_id for entry in entries}) == 4
    assert [entry.sequence for entry in entries] == sorted(
        entry.sequence for entry in entries
    )
    stamped = _stored_events(sessions)
    assert len(stamped) == 100
    for number, entry in enumerate(entries):
        window = stamped[
            number * DEFAULT_BATCH_SIZE : (number + 1) * DEFAULT_BATCH_SIZE
        ]
        assert {event.batch_id for event in window} == {entry.batch_id}
        assert entry.merkle_root == build_tree(_digests(window)).root.hex()


def test_a_short_last_batch_is_anchored_too(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A tail is a batch, not a remainder nobody commits to."""
    events = _store(sessions, 26)

    entries = _anchor(events, sessions, ledger, signer)

    assert len(entries) == 2
    tail = _stored_events(sessions)[-1:]
    assert {event.batch_id for event in tail} == {entries[1].batch_id}


def test_anchoring_nothing_appends_nothing(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """``D54`` refuses a tree over no leaves, so a quiet window is not an
    error -- it is ``()`` and no row."""
    assert select_unanchored(sessions) == ()

    entries = _anchor((), sessions, ledger, signer)

    assert entries == ()
    assert _entries(sessions) == ()


def test_an_explicit_stamp_reaches_the_entry(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """9.11's optional stamp is passed through, not read and dropped."""
    events = _store(sessions, 2)
    moment = datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)

    (entry,) = _anchor(events, sessions, ledger, signer, anchored_at=moment)

    stored = _entries(sessions)[0]
    assert _as_utc(stored.anchored_at) == moment
    assert stored.sequence == entry.sequence


# --- an event is anchored once ---------------------------------------------


def test_an_already_anchored_event_is_refused_with_the_log_untouched(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Re-anchoring would move the row off the entry that committed it."""
    events = _store(sessions, 2)
    (first,) = _anchor(events, sessions, ledger, signer)

    with pytest.raises(AnchorError):
        _anchor(events, sessions, ledger, signer)

    rows = _entries(sessions)
    assert len(rows) == 1
    assert rows[0].batch_id == first.batch_id
    stamped = _stored_events(sessions)
    assert {event.batch_id for event in stamped} == {first.batch_id}


def test_the_stamp_is_conditional_in_the_database(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The entry is appended before the stamp, and the stamp is conditional.

    Held against the emitted statement, the way ``iter_batches``' order is:
    a row claimed between the read and the write is not taken from whoever
    claimed it, and on SQLite the row count alone cannot show that.  There
    is one statement per event, because a position is that event's own
    value.  The order matters for the same reason: a stamp written first
    would point at an entry the log does not hold if the append then failed.
    """
    events = _store(sessions, 4)

    with _emitted(sessions) as statements:
        _anchor(events, sessions, ledger, signer)

    updates = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("UPDATE")
    ]
    inserts = [
        index
        for index, statement in enumerate(statements)
        if statement.lstrip().upper().startswith("INSERT INTO LEDGER_ENTRIES")
    ]
    assert len(updates) == len(events)
    assert all("batch_id IS NULL" in statement for statement in updates)
    assert min(
        statements.index(statement) for statement in updates
    ) > inserts[0]


# --- refusals --------------------------------------------------------------


def test_an_event_that_was_never_written_is_refused(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A transient row has no digest to root and no row to stamp."""
    transient = AuditEvent(record_hash=_a_digest(0))

    with pytest.raises(AnchorError):
        _anchor((transient,), sessions, ledger, signer)

    assert _entries(sessions) == ()


def test_an_element_that_is_not_an_event_is_refused_by_type(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """The message names the type and quotes no value."""
    with pytest.raises(TypeError) as refusal:
        _anchor(("not-an-event",), sessions, ledger, signer)

    assert "str" in str(refusal.value)
    assert "not-an-event" not in str(refusal.value)
    assert _entries(sessions) == ()


def test_one_event_in_a_batch_twice_is_refused(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Two leaves for one row would give 9.17 two positions for it."""
    (event,) = _store(sessions, 1)

    with pytest.raises(AnchorError):
        _anchor((event, event), sessions, ledger, signer)

    assert _entries(sessions) == ()
    assert _stored_events(sessions)[0].batch_id is None


def test_a_record_hash_that_is_not_a_digest_is_refused(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A leaf is 32 bytes; a truncated or unhashed column cannot be one."""
    events = _store(sessions, 1)
    with sessions() as session:
        row = session.get(AuditEvent, events[0].id)
        row.record_hash = "9f86d081"
        session.commit()

    with pytest.raises(AnchorError):
        _anchor(events, sessions, ledger, signer)

    assert _entries(sessions) == ()


def test_a_record_hash_that_is_not_hex_is_refused(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """Whatever put prose in that column, a leaf cannot be read from it."""
    events = _store(sessions, 1)
    with sessions() as session:
        row = session.get(AuditEvent, events[0].id)
        row.record_hash = "not a digest"
        session.commit()

    with pytest.raises(AnchorError):
        _anchor(events, sessions, ledger, signer)

    assert _entries(sessions) == ()


@pytest.mark.parametrize("size", [0, -1])
def test_a_size_that_cannot_cut_refuses_before_anything_is_read(
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
    size: int,
) -> None:
    """9.15's refusals come first, so no run is drained on the way out."""
    events = _store(sessions, 2)

    with pytest.raises(ValueError):
        _anchor(events, sessions, ledger, signer, size=size)

    assert _entries(sessions) == ()
    assert [event.id for event in select_unanchored(sessions)] == [
        event.id for event in events
    ]


def test_a_size_that_is_not_an_int_is_refused(
    sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
) -> None:
    """A ``bool`` is an ``int`` and would cut batches of one."""
    events = _store(sessions, 2)

    with pytest.raises(TypeError):
        _anchor(events, sessions, ledger, signer, size=True)

    assert _entries(sessions) == ()


# --- the run is the reader's -----------------------------------------------


def test_the_reader_answers_the_unanchored_rows_oldest_first(
    sessions: sessionmaker[Session],
) -> None:
    """The order here is the order the next anchor commits to."""
    events = _store(sessions, 4)

    answer = select_unanchored(sessions)

    assert [event.id for event in answer] == [
        event.id for event in events
    ]
    assert all(event.batch_id is None for event in answer)


def test_the_reader_leaves_out_rows_a_batch_already_claimed(
    sessions: sessionmaker[Session], ledger: SqliteLedger, signer: Signer
) -> None:
    """A sweep takes what is unanchored, not what exists."""
    events = _store(sessions, 5)
    _anchor(events[:2], sessions, ledger, signer)

    answer = select_unanchored(sessions)

    assert [event.id for event in answer] == [
        event.id for event in events[2:]
    ]


# --- who owns the session --------------------------------------------------


def test_the_rows_are_written_to_the_database_its_sessions_name(
    sessions: sessionmaker[Session],
    other_sessions: sessionmaker[Session],
    ledger: SqliteLedger,
    signer: Signer,
) -> None:
    """An anchoring that reached for ``SessionLocal`` passes every test above.

    The events are written through one factory and the log is over the same
    file, and a second, separately migrated database must come out empty on
    both tables.
    """
    events = _store(sessions, 3)

    _anchor(events, sessions, ledger, signer)

    assert select_unanchored(sessions) == ()
    with other_sessions() as session:
        assert session.scalars(select(AuditEvent)).all() == []
        assert session.scalars(select(LedgerEntry)).all() == []


# --- the shape of the verb -------------------------------------------------


def test_dependencies_are_keyword_only_and_there_are_four() -> None:
    """A ledger or a signer cannot be handed over positionally by accident."""
    parameters = inspect.signature(anchor_batch).parameters
    keyword_only = {
        name
        for name, parameter in parameters.items()
        if parameter.kind is parameter.KEYWORD_ONLY
    }

    assert list(parameters)[0] == "events"
    assert keyword_only == {
        "sessions",
        "ledger",
        "signer",
        "size",
        "anchored_at",
    }


def test_anchoring_never_reaches_for_the_module_level_session_factory() -> None:
    """9.16's caller owns the seam, as 9.11's and 8.10's callers do."""
    source = inspect.getsource(anchor_batch)

    assert "SessionLocal" not in source
    assert "build_session_factory" not in source


def test_the_default_batch_size_is_the_one_the_verify_states() -> None:
    """25, and a default rather than a rule."""
    assert DEFAULT_BATCH_SIZE == 25
