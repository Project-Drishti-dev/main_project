"""9.11: the ``Ledger`` interface and the ``SqliteLedger`` behind it.

The task's verify is "a test round-trips a batch", so that is the first
test here, and it reads back over a *new* engine rather than off the return
value -- an append that never committed, or a read that answered from the
session that wrote the row, would otherwise pass.  What the round trip rests
on is pinned beside it:

- **the entry is in the migrated table.**  The fixture runs ``alembic
  upgrade head`` on a temporary file rather than ``create_all``, because
  this is the first thing in Part 9 that writes to ``ledger_entries`` and a
  write against a table the migration never made would pass here.
- **the returned entry is readable once its session has closed.**
  ``append_batch`` opens, writes, commits and closes inside the call, so the
  instance handed back is detached on return; ``expire_on_commit=False``
  (``D36``) is the only reason reading it does not raise, and *every*
  column is read so a column added later cannot become a new way to fail.
- **a position is the database's to give.**  Two appends take two distinct,
  increasing ``sequence`` values and no argument writes one, because an
  entry's identity *is* its position.
- **a batch is appended once.**  A second append of the same ``batch_id``
  is refused and the log still carries one entry, since two entries for one
  batch would leave ``read_batch`` with two answers to one question.
- **a stored spelling is 9.16's decision.**  A root and a signature that
  are *not* 64 or 128 hex characters travel verbatim, because
  :mod:`app.ledger.merkle` holds a root as 32 raw bytes and the spelling
  that reaches the column is that task's business.
- **an explicit stamp is an instant, not a wall time.**  A stamp given in
  another offset is stored as UTC and reads back as the same instant, and a
  naive one is refused with the log untouched, on ``D47``'s reasoning.
- **the ledger reads the database its sessions name.**  Held against two
  migrated databases at once, because a ledger that reached for
  :data:`app.storage.db.SessionLocal` would satisfy every test above it.
- **the interface is an interface.**  ``SqliteLedger`` is a ``Ledger``,
  ``Ledger`` itself cannot be built, and a subclass missing one of the three
  methods cannot be instantiated either.
- **nothing but hashes and stamps can be appended.**  The interface takes
  exactly four keywords, which is as much of the abstract's "only hashes
  reach the ledger" as this module can express.
"""

import inspect
import pathlib
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, delete, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.ledger.store import DuplicateBatchError, Ledger, SqliteLedger
from app.storage import db
from app.storage.models import LedgerEntry

#: The alembic configuration this service migrates with, derived from this
#: file for the reason ``test_screening_repository.py`` gives.
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"

#: Every column the model declares, so "a column added later is also a
#: column the append must fill" needs no edit here.
ALL_COLUMNS = frozenset(column.name for column in LedgerEntry.__table__.columns)

#: A root and a signature in the spellings a Merkle digest and an Ed25519
#: signature travel in, so the round trip is over values shaped like the
#: ones 9.16 will hand over.
A_ROOT = "7c9f" * 16
A_SIGNATURE = "3f" * 64

#: The keywords ``append_batch`` accepts.  Written out rather than read off
#: the implementation, so a fourth value reaching the log fails here first.
APPEND_KEYWORDS = {"batch_id", "merkle_root", "signature", "anchored_at"}


def _url_for(database: pathlib.Path) -> str:
    """The URL naming ``database``, in the spelling 8.8's fixture uses."""
    return f"sqlite:///{database.as_posix()}"


class _Databases(NamedTuple):
    """Two migrated SQLite files, for the claim about who owns the session."""

    primary: pathlib.Path
    other: pathlib.Path


def _migrate(databases: tuple[pathlib.Path, ...]) -> None:
    """Run ``upgrade head`` against each of ``databases``, in turn."""
    for database in databases:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", _url_for(database))
            command.upgrade(Config(str(ALEMBIC_INI)), "head")
        assert database.exists()


@pytest.fixture(scope="module")
def migrated_databases(tmp_path_factory: pytest.TempPathFactory) -> _Databases:
    """Two ``tmp_path`` files migrated to head, and nothing else in them."""
    directory = tmp_path_factory.mktemp("ledger-store")
    databases = _Databases(directory / "primary.db", directory / "other.db")
    _migrate(tuple(databases))
    return databases


def _sessions_for(database: pathlib.Path) -> sessionmaker[Session]:
    """A session factory over ``database``, built the service's way.

    Called twice over the same file it builds two engines, which is the
    point: a row found through the second one was serialised rather than
    still sitting in the identity map of the session that wrote it.
    """
    return db.build_session_factory(db.build_engine(_url_for(database)))


@pytest.fixture
def sessions(migrated_databases: _Databases) -> sessionmaker[Session]:
    """A session factory over the migrated file, built the service's way."""
    return _sessions_for(migrated_databases.primary)


@pytest.fixture
def ledger(sessions: sessionmaker[Session]) -> SqliteLedger:
    """The ledger under test, over the sessions the test handed it."""
    return SqliteLedger(sessions)


@pytest.fixture
def clean_sessions(sessions: sessionmaker[Session]) -> sessionmaker[Session]:
    """The same factory, over a log emptied before the test ran.

    The migrated file is module-scoped, so it carries every entry an
    earlier test appended.  A walk or a count taken against a log this test
    did not empty could only be a delta, so the delete happens here, once,
    and every count below it is an absolute number.
    """
    with sessions() as session:
        session.execute(delete(LedgerEntry))
        session.commit()
    return sessions


@pytest.fixture
def clean_ledger(clean_sessions: sessionmaker[Session]) -> SqliteLedger:
    """The ledger under test, over a log emptied before the test ran."""
    return SqliteLedger(clean_sessions)


def _append(ledger: SqliteLedger, **overrides: object) -> LedgerEntry:
    """Append one batch, with every value spelled unless overridden."""
    arguments: dict[str, object] = {
        "batch_id": uuid.uuid4(),
        "merkle_root": A_ROOT,
        "signature": A_SIGNATURE,
    }
    arguments.update(overrides)
    return ledger.append_batch(**arguments)  # type: ignore[arg-type]


def _as_utc(moment: datetime) -> datetime:
    """Read back a stamp SQLite returned with no ``tzinfo``, as UTC."""
    return moment.replace(tzinfo=timezone.utc)


def _write_at(
    sessions: sessionmaker[Session], positions: Sequence[int]
) -> tuple[LedgerEntry, ...]:
    """Write entries at the positions given, in the order given.

    Written through a session rather than appended, because a log appended
    to in order hands out positions in that same order -- which is the one
    order an ``ORDER BY`` on ``sequence`` and no ``ORDER BY`` at all would
    agree on.
    """
    with sessions() as session:
        written = tuple(
            LedgerEntry(
                sequence=position,
                batch_id=uuid.uuid4(),
                merkle_root=A_ROOT,
                signature=A_SIGNATURE,
            )
            for position in positions
        )
        session.add_all(written)
        session.commit()
    return written


# --- the task's assertion, and what it rests on -----------------------------


def test_a_batch_round_trips_through_the_ledger(
    clean_ledger: SqliteLedger, migrated_databases: _Databases
) -> None:
    """9.11's verify: append a batch, read it back, and it is the same one.

    Read over a *new* engine on the same file, so an append that never
    committed -- or a read answered out of the session that wrote the row --
    fails here rather than agreeing with itself.
    """
    batch_id = uuid.uuid4()

    appended = clean_ledger.append_batch(
        batch_id=batch_id, merkle_root=A_ROOT, signature=A_SIGNATURE
    )

    with _sessions_for(migrated_databases.primary)() as session:
        stored = session.execute(
            select(LedgerEntry).where(LedgerEntry.batch_id == batch_id)
        ).scalar_one()

    assert stored.batch_id == batch_id == appended.batch_id
    assert stored.merkle_root == A_ROOT
    assert stored.signature == A_SIGNATURE
    assert isinstance(stored.sequence, int)
    assert stored.sequence == appended.sequence
    assert stored.anchored_at is not None


def test_read_batch_answers_the_entry_that_was_appended(
    clean_ledger: SqliteLedger,
) -> None:
    """``read_batch`` reaches the same row the round trip above found."""
    batch_id = uuid.uuid4()
    appended = _append(clean_ledger, batch_id=batch_id)

    found = clean_ledger.read_batch(batch_id)

    assert found is not None
    assert (found.sequence, found.merkle_root, found.signature) == (
        appended.sequence,
        A_ROOT,
        A_SIGNATURE,
    )


def test_the_entry_is_in_the_migrated_table_not_merely_returned(
    clean_ledger: SqliteLedger, migrated_databases: _Databases
) -> None:
    """The row survives the session that wrote it, in a file of its own.

    Counted over a fresh engine on the migrated file, because a log that
    answered from its own session -- or rolled the append back -- would hold
    no row for this to find.
    """
    _append(clean_ledger)

    with _sessions_for(migrated_databases.primary)() as session:
        found = session.execute(select(LedgerEntry)).scalars().all()

    assert len(found) == 1


def test_the_returned_entry_is_readable_once_its_session_is_closed(
    clean_ledger: SqliteLedger,
) -> None:
    """``expire_on_commit=False`` (``D36``), measured by reading every column.

    ``append_batch`` opens, writes, commits and closes inside the call, so
    the entry handed back is detached.  Reading one attribute of it is enough
    to fail if the factory ever expires on commit, and *every* column is read
    because a column added later must not become a new way for this to raise.
    """
    appended = _append(clean_ledger)

    assert {name: getattr(appended, name) for name in sorted(ALL_COLUMNS)} == {
        "anchored_at": appended.anchored_at,
        "batch_id": appended.batch_id,
        "merkle_root": A_ROOT,
        "sequence": appended.sequence,
        "signature": A_SIGNATURE,
    }


def test_read_batch_answers_none_for_a_batch_the_log_does_not_carry(
    clean_ledger: SqliteLedger,
) -> None:
    """Absence is an answer: an id no entry carries is ``None``, not a raise.

    Asked against a log holding one entry, so a ``read_batch`` that ignored
    its argument and answered the first row -- the shape a query without a
    ``WHERE`` takes -- fails here rather than agreeing by luck.
    """
    _append(clean_ledger)

    assert clean_ledger.read_batch(uuid.uuid4()) is None


def test_a_position_is_the_databases_to_give(
    clean_ledger: SqliteLedger,
) -> None:
    """Two appends take two positions, and no caller can name one.

    Asserted as strictly increasing rather than as 1 and 2, because the log
    is module-scoped across the file and the numbers are the database's to
    hand out.  The signature is read as well: an argument that wrote a
    position would let an entry claim one already used.
    """
    first = _append(clean_ledger)
    second = _append(clean_ledger)

    assert second.sequence > first.sequence
    assert "sequence" not in inspect.signature(
        SqliteLedger.append_batch
    ).parameters


def test_a_batch_is_appended_once_and_the_refusal_writes_nothing(
    clean_ledger: SqliteLedger, sessions: sessionmaker[Session]
) -> None:
    """A second append of one batch is refused, and the log keeps one entry.

    Counted over a session rather than trusted from the raise, because a
    refusal that had already added the row would leave two entries and leave
    ``read_batch`` with two answers to one question.
    """
    batch_id = uuid.uuid4()
    _append(clean_ledger, batch_id=batch_id)

    with pytest.raises(DuplicateBatchError):
        _append(clean_ledger, batch_id=batch_id)

    with sessions() as session:
        stored = session.execute(
            select(LedgerEntry).where(LedgerEntry.batch_id == batch_id)
        ).scalars().all()
    assert len(stored) == 1


def test_a_second_append_of_another_batch_is_not_a_duplicate(
    clean_ledger: SqliteLedger,
) -> None:
    """The refusal is about the batch, not about the log holding anything.

    Without this a ``read_batch`` that answered the *first* row it found
    would pass the refusal test above on a log holding two batches.
    """
    first = _append(clean_ledger)
    second = _append(clean_ledger)

    assert second.sequence > first.sequence
    assert clean_ledger.read_batch(second.batch_id) is not None


def test_iter_batches_walks_the_log_in_sequence_order(
    clean_ledger: SqliteLedger,
) -> None:
    """The walk is the chain's own order, and it reaches every entry.

    The expected order is spelled out as three values rather than folded into
    ``all(...)``, so a walk over an empty range cannot pass, and each
    expected batch id is compared rather than each position, so a walk in
    insertion order would have to coincide with the chain's order to pass.
    """
    written = [_append(clean_ledger) for _ in range(3)]

    walked = list(clean_ledger.iter_batches())

    assert [entry.batch_id for entry in walked] == [
        entry.batch_id for entry in written
    ]
    assert [entry.sequence for entry in walked] == sorted(
        entry.sequence for entry in written
    )


def test_iter_batches_walks_the_chain_and_not_the_order_the_rows_arrived_in(
    clean_sessions: sessionmaker[Session],
) -> None:
    """The order is the chain's, over a log whose rows are in that order.

    Three entries written out of order at positions 40, 10 and 25, so the
    walk is asked for a chain rather than for a file.  On this backend the
    rows come back in that order whichever way the statement is written,
    which is why the next test checks the statement instead.
    """
    _write_at(clean_sessions, (40, 10, 25))

    walked = SqliteLedger(clean_sessions).iter_batches()

    assert [entry.sequence for entry in walked] == [10, 25, 40]


def test_the_walk_carries_its_own_ordering(
    clean_sessions: sessionmaker[Session],
) -> None:
    """``iter_batches`` orders by ``sequence`` rather than borrowing SQLite's.

    ``sequence`` is this table's ``INTEGER PRIMARY KEY``, so an unordered
    ``SELECT`` scans the rowid index -- which *is* sequence order here, and
    would go on passing after the ordering clause was dropped.  The rows
    therefore cannot carry this claim on their own, and the statement the
    walk emits is checked instead: one ``SELECT``, ordering on the
    sequence column.
    """
    engine = clean_sessions.kw["bind"]
    assert isinstance(engine, Engine)
    emitted: list[str] = []

    def record(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        emitted.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        list(SqliteLedger(clean_sessions).iter_batches())
    finally:
        event.remove(engine, "before_cursor_execute", record)

    selects = [one for one in emitted if "SELECT" in one.upper()]
    assert len(selects) == 1
    assert "ORDER BY ledger_entries.sequence" in selects[0]


def test_iter_batches_over_an_empty_log_walks_nothing(
    clean_ledger: SqliteLedger,
) -> None:
    """A log nobody has appended to answers no entries, not one blank."""
    assert list(clean_ledger.iter_batches()) == []


def test_the_root_and_signature_travel_verbatim(
    clean_ledger: SqliteLedger,
) -> None:
    """9.16 owns the stored spelling, so this module encodes nothing.

    Both values are written in a shape no digest or signature has, and
    answered back unchanged: :mod:`app.ledger.merkle` holds a root as 32
    raw bytes while the column is text, and a module that validated the
    spelling here would be a second answer to a question 9.16 has not
    asked yet -- and one that would refuse 9.16's first choice.
    """
    root, signature = "root-as-it-was-handed-over", "signature-uninterpreted"

    appended = _append(clean_ledger, merkle_root=root, signature=signature)
    found = clean_ledger.read_batch(appended.batch_id)

    assert found is not None
    assert (found.merkle_root, found.signature) == (root, signature)


def test_an_explicit_stamp_is_stored_as_the_instant_it_names(
    clean_ledger: SqliteLedger,
) -> None:
    """A stamp given in another offset is stored in UTC, as ``D47`` does.

    Read back with the same helper the repository's tests use, because
    SQLite's ``DATETIME`` drops the offset: a value stored as written would
    name a different instant, and 9.17's re-computation reads a naive stamp.
    """
    plus_five = timezone(timedelta(hours=5, minutes=30))
    moment = datetime(2026, 3, 1, 14, 30, tzinfo=plus_five)

    appended = _append(clean_ledger, anchored_at=moment)

    assert appended.anchored_at is not None
    assert _as_utc(appended.anchored_at) == moment


def test_an_omitted_stamp_is_the_rows_own_clock(
    clean_ledger: SqliteLedger,
) -> None:
    """``anchored_at`` left out is stamped by the row, not by this module.

    Bracketed by clock reads either side of the call, so a ledger stamping a
    constant -- or nothing at all -- fails rather than happening to hold a
    plausible instant.
    """
    before = datetime.now(timezone.utc)
    appended = _append(clean_ledger)
    after = datetime.now(timezone.utc)

    assert appended.anchored_at is not None
    assert before <= _as_utc(appended.anchored_at) <= after


def test_a_naive_stamp_is_refused_and_the_log_is_untouched(
    clean_ledger: SqliteLedger, sessions: sessionmaker[Session]
) -> None:
    """A stamp with no zone names no instant, so nothing is written.

    Counted after the refusal, because a refusal that had already added the
    row would leave an entry whose stamp no caller can name.
    """
    with pytest.raises(ValueError):
        _append(clean_ledger, anchored_at=datetime(2026, 3, 1, 14, 30))

    with sessions() as session:
        assert session.execute(select(LedgerEntry)).scalars().all() == []


def test_the_ledger_reads_the_database_its_sessions_name(
    clean_ledger: SqliteLedger, migrated_databases: _Databases
) -> None:
    """The ledger writes only where its sessions point.

    Two migrated files at once, because a ledger that reached for
    :data:`app.storage.db.SessionLocal` would satisfy every test above it and
    be pinned to the process's start-up configuration.
    """
    appended = _append(clean_ledger)

    with _sessions_for(migrated_databases.other)() as session:
        elsewhere = session.execute(select(LedgerEntry)).scalars().all()

    assert elsewhere == []
    assert clean_ledger.read_batch(appended.batch_id) is not None


def test_the_ledger_implements_the_interface_and_the_interface_is_abstract(
    sessions: sessionmaker[Session],
) -> None:
    """``SqliteLedger`` is a ``Ledger``, and ``Ledger`` cannot be built.

    A 9.16 caller holding a :class:`Ledger` gets the three methods, and the
    abstract base is what makes a missing one a failure at construction
    rather than an ``AttributeError`` at the call that needed it.
    """
    assert issubclass(SqliteLedger, Ledger)
    assert isinstance(SqliteLedger(sessions), Ledger)

    with pytest.raises(TypeError):
        Ledger()  # type: ignore[abstract]


def test_a_ledger_missing_a_method_cannot_be_instantiated() -> None:
    """One method short of the three is not a ``Ledger``.

    Spelled as a subclass rather than checked on the abstract base, because
    the base's own refusal is the thing :func:`issubclass` cannot show: a
    class that inherits the interface and forgets a method is the shape a
    future implementation would arrive in.
    """

    class _OneShort(Ledger):
        def append_batch(self, **kwargs: object) -> LedgerEntry:
            raise NotImplementedError

        def read_batch(self, batch_id: uuid.UUID) -> LedgerEntry | None:
            raise NotImplementedError

    with pytest.raises(TypeError):
        _OneShort()  # type: ignore[abstract]


def test_the_interface_takes_a_root_a_signature_and_two_stamps(
    sessions: sessionmaker[Session],
) -> None:
    """``append_batch`` has four keywords, and no fifth can reach the log.

    This is the abstract's "only hashes reach the ledger" as far as the
    signature can express it: an entry has a root, a signature, a batch id
    and two stamps, and there is no argument through which a payload, a
    filename or a person could be written.  Read off the abstract base as
    well as the implementation, so the two cannot drift apart.
    """
    for method in (Ledger.append_batch, SqliteLedger.append_batch):
        parameters = inspect.signature(method).parameters
        keyword_only = {
            name
            for name, parameter in parameters.items()
            if parameter.kind is inspect.Parameter.KEYWORD_ONLY
        }
        assert keyword_only == APPEND_KEYWORDS
        assert not any(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for name, parameter in parameters.items()
            if name != "self"
        )

    ledger = SqliteLedger(sessions)
    with pytest.raises(TypeError):
        ledger.append_batch(  # type: ignore[call-arg]
            batch_id=uuid.uuid4(),
            merkle_root=A_ROOT,
            signature=A_SIGNATURE,
            screening_id=uuid.uuid4(),
        )
