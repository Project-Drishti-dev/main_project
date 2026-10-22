"""9.12: append-only, refused by the database rather than by the service.

``D39``'s mapper events already refuse an amendment and a removal from the
ORM's side, and 9.11's log never offers a way to make one.  The gap this
file closes is a statement that never reached the ORM: a raw ``UPDATE``, a
``DELETE`` from a script, a second service.  So every refusal below is
issued as driver-level SQL, which is the only place the triggers can be seen
at all.

- **both verbs raise, and say why.**  A trigger that fired on one of the two
  and stayed quiet on the other would satisfy a weaker test, so the two are
  separate tests and each reads the refusal's message.
- **the migrated log alone refuses nothing.**  Over a file that was upgraded
  to head and never installed, the same two statements *succeed*.  Without
  that, the refusals below would be a claim about SQLite rather than about
  :mod:`app.ledger.triggers`.
- **a refusal leaves the entry exactly as it was** -- same position, same
  root, same signature -- because a guard that half-applied the statement it
  refused would be worse than no guard.
- **the third verb still works.**  The refusals are the two the task names,
  not a table that answers nobody: an append lands after both.
- **the guards are ``BEFORE``/``FOR EACH ROW``/``ABORT``**, read back out of
  ``sqlite_master`` rather than taken from the module, and the table carries
  exactly the two exported names and no third.
- **installing twice is a no-op**, because a caller will ask on every start.
- **the two halves answer in their own words.**  The mapper guard raises
  ``LedgerAppendOnlyError`` *before any statement is sent*, which is why the
  trigger half was needed: the ORM's refusal cannot see raw SQL.
- **the package has no verb for removing the guards**, which is why the
  empty-log helper below drops them by name and installs them again.
- **the installer refuses a non-SQLite engine** by name rather than sending
  another dialect a ``RAISE`` it does not have.
- **and the one hole there is, is measured.**  ``INSERT OR REPLACE`` does not
  fire the delete trigger unless ``PRAGMA recursive_triggers`` is on, so both
  settings are pinned here rather than left to be discovered.
"""

import pathlib
import uuid
from collections.abc import Iterator
from typing import NamedTuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_mock_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.ledger import triggers
from app.ledger.store import SqliteLedger
from app.storage import db
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    LEDGER_ENTRY_TABLE_NAME,
    SCREENING_TABLE_NAME,
    LedgerAppendOnlyError,
    LedgerEntry,
)

#: The alembic configuration this service migrates with, derived from this
#: file for the reason ``test_ledger_store.py`` gives.
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"

#: A root and a signature in the spellings 9.16 will hand over.
A_ROOT = "7c9f" * 16
A_SIGNATURE = "3f" * 64

#: The two guards, as the package names them, so "the table carries exactly
#: these" is a set rather than a remembered count.
THE_GUARDS = (
    triggers.UPDATE_TRIGGER_NAME,
    triggers.DELETE_TRIGGER_NAME,
)

#: Overwriting a position that is already in the log, which is the statement
#: that walks past a delete trigger.
REPLACE_AT = (
    f"INSERT OR REPLACE INTO {LEDGER_ENTRY_TABLE_NAME} "
    "(sequence, batch_id, merkle_root, signature, anchored_at) "
    "VALUES (?, ?, 'forged', 'forged', ?)"
)


def _url_for(database: pathlib.Path) -> str:
    """The URL naming ``database``, in the spelling 8.8's fixture uses."""
    return f"sqlite:///{database.as_posix()}"


class _Databases(NamedTuple):
    """Two migrated files: one that gets the guards, one that never does."""

    guarded: pathlib.Path
    bare: pathlib.Path


@pytest.fixture(scope="module")
def migrated_databases(tmp_path_factory: pytest.TempPathFactory) -> _Databases:
    """Two ``tmp_path`` files migrated to head, and nothing else in them."""
    directory = tmp_path_factory.mktemp("ledger-append-only")
    databases = _Databases(directory / "guarded.db", directory / "bare.db")
    for database in databases:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", _url_for(database))
            command.upgrade(Config(str(ALEMBIC_INI)), "head")
        assert database.exists()
    return databases


class _Log(NamedTuple):
    """The engine, the sessions and the ledger over one guarded file."""

    engine: Engine
    sessions: sessionmaker[Session]
    ledger: SqliteLedger


def _open(database: pathlib.Path) -> _Log:
    """Build the service's engine, sessions and ledger over ``database``."""
    engine = db.build_engine(_url_for(database))
    sessions = db.build_session_factory(engine)
    return _Log(engine, sessions, SqliteLedger(sessions))


def _guard_names(connection: Connection, table: str) -> tuple[str, ...]:
    """The trigger names the database itself reports for ``table``."""
    rows = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' "
        "AND tbl_name = ? ORDER BY name",
        (table,),
    )
    return tuple(row[0] for row in rows)


def _empty(log: _Log) -> None:
    """Leave the log empty with the guards still in place.

    An installed log cannot be emptied -- that is this task's claim -- so
    the only way to hand the next test an empty one is to drop the two
    triggers by name, delete, and install again.  The drop lives here rather
    than in :mod:`app.ledger.triggers` because the package has no such verb.
    """
    with log.engine.begin() as connection:
        for name in THE_GUARDS:
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name}")
        connection.exec_driver_sql(f"DELETE FROM {LEDGER_ENTRY_TABLE_NAME}")
    triggers.install_append_only_triggers(log.engine)


@pytest.fixture
def log(migrated_databases: _Databases) -> Iterator[_Log]:
    """A guarded log, installed here and emptied again on the way out."""
    opened = _open(migrated_databases.guarded)
    triggers.install_append_only_triggers(opened.engine)
    _empty(opened)
    yield opened
    _empty(opened)
    opened.engine.dispose()


@pytest.fixture(scope="module")
def bare_log(migrated_databases: _Databases) -> Iterator[_Log]:
    """A migrated log the guards were never installed on."""
    opened = _open(migrated_databases.bare)
    yield opened
    opened.engine.dispose()


def _append(log: _Log) -> LedgerEntry:
    """Append one batch to ``log``, the way 9.16 will."""
    return log.ledger.append_batch(
        batch_id=uuid.uuid4(),
        merkle_root=A_ROOT,
        signature=A_SIGNATURE,
    )


def _raw(engine: Engine, statement: str, parameters: tuple = ()) -> None:
    """Run one statement with no ORM in the way, and commit or roll back."""
    with engine.begin() as connection:
        connection.exec_driver_sql(statement, parameters)


# --- the task's verify: both verbs raise ------------------------------


def test_an_update_through_raw_sql_is_refused(log: _Log) -> None:
    """An ``UPDATE`` naming no ORM raises, and names the refusal."""
    entry = _append(log)
    with pytest.raises(IntegrityError) as caught:
        _raw(
            log.engine,
            f"UPDATE {LEDGER_ENTRY_TABLE_NAME} SET merkle_root = 'amended' "
            f"WHERE sequence = {entry.sequence}",
        )
    assert triggers.APPEND_ONLY_MESSAGE in str(caught.value)


def test_a_delete_through_raw_sql_is_refused(log: _Log) -> None:
    """A ``DELETE`` naming no ORM raises, and names the refusal."""
    _append(log)
    with pytest.raises(IntegrityError) as caught:
        _raw(log.engine, f"DELETE FROM {LEDGER_ENTRY_TABLE_NAME}")
    assert triggers.APPEND_ONLY_MESSAGE in str(caught.value)


def test_the_refused_entry_is_untouched(log: _Log) -> None:
    """After both refusals the entry stands: same position, root, signature."""
    entry = _append(log)
    for statement in (
        f"UPDATE {LEDGER_ENTRY_TABLE_NAME} SET merkle_root = 'amended', "
        f"signature = 'amended' WHERE sequence = {entry.sequence}",
        f"DELETE FROM {LEDGER_ENTRY_TABLE_NAME} "
        f"WHERE sequence = {entry.sequence}",
    ):
        with pytest.raises(IntegrityError):
            _raw(log.engine, statement)
    survivors = tuple(log.ledger.iter_batches())
    assert len(survivors) == 1
    assert (survivors[0].sequence, survivors[0].merkle_root) == (
        entry.sequence,
        A_ROOT,
    )
    assert survivors[0].signature == A_SIGNATURE


def test_an_append_still_lands_after_a_refusal(log: _Log) -> None:
    """The guards refuse two verbs, not the log: the next append commits."""
    first = _append(log)
    with pytest.raises(IntegrityError):
        _raw(log.engine, f"DELETE FROM {LEDGER_ENTRY_TABLE_NAME}")
    second = _append(log)
    assert (first.sequence, second.sequence) == (1, 2)
    assert len(tuple(log.ledger.iter_batches())) == 2


def test_the_migrated_log_alone_refuses_nothing(bare_log: _Log) -> None:
    """Without the installer, the same two statements both succeed.

    The claim that makes the five tests above a claim about the triggers:
    a migrated ``ledger_entries`` is an ordinary table until 9.12 guards it.
    """
    entry = _append(bare_log)
    _raw(
        bare_log.engine,
        f"UPDATE {LEDGER_ENTRY_TABLE_NAME} SET merkle_root = 'amended' "
        f"WHERE sequence = {entry.sequence}",
    )
    assert bare_log.ledger.read_batch(entry.batch_id).merkle_root == "amended"
    _raw(bare_log.engine, f"DELETE FROM {LEDGER_ENTRY_TABLE_NAME}")
    assert tuple(bare_log.ledger.iter_batches()) == ()


# --- what was installed ----------------------------------------------


def test_the_table_carries_exactly_the_two_exported_guards(log: _Log) -> None:
    """Two trigger names, the package's own, and no third beside them."""
    with log.engine.connect() as connection:
        assert _guard_names(connection, LEDGER_ENTRY_TABLE_NAME) == tuple(
            sorted(THE_GUARDS)
        )
        for other in (SCREENING_TABLE_NAME, AUDIT_EVENT_TABLE_NAME):
            assert _guard_names(connection, other) == ()


@pytest.mark.parametrize(
    ("name", "verb"),
    [
        (triggers.UPDATE_TRIGGER_NAME, "UPDATE"),
        (triggers.DELETE_TRIGGER_NAME, "DELETE"),
    ],
)
def test_the_guard_is_a_before_row_trigger_that_aborts(
    log: _Log, name: str, verb: str
) -> None:
    """The stored DDL, read out of the database rather than the module."""
    with log.engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT tbl_name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name = ?",
            (name,),
        ).one()
    table, statement = row
    assert table == LEDGER_ENTRY_TABLE_NAME
    assert f"BEFORE {verb} ON {LEDGER_ENTRY_TABLE_NAME}" in statement
    assert "FOR EACH ROW" in statement
    assert f"RAISE(ABORT, '{triggers.APPEND_ONLY_MESSAGE}')" in statement


def test_installing_a_second_time_changes_nothing(log: _Log) -> None:
    """A second install is a no-op, because a caller asks on every start."""
    _append(log)
    with log.engine.connect() as connection:
        before = _guard_names(connection, LEDGER_ENTRY_TABLE_NAME)
    triggers.install_append_only_triggers(log.engine)
    triggers.install_append_only_triggers(log.engine)
    with log.engine.connect() as connection:
        assert _guard_names(connection, LEDGER_ENTRY_TABLE_NAME) == before
    with pytest.raises(IntegrityError):
        _raw(log.engine, f"DELETE FROM {LEDGER_ENTRY_TABLE_NAME}")


def test_the_package_exports_no_verb_that_removes_the_guards() -> None:
    """Nothing in :mod:`app.ledger.triggers` un-installs what it installs."""
    assert set(triggers.__all__) == {
        "APPEND_ONLY_MESSAGE",
        "DELETE_TRIGGER_NAME",
        "UPDATE_TRIGGER_NAME",
        "install_append_only_triggers",
    }
    assert not [
        name
        for name in dir(triggers)
        if "drop" in name.lower() or "remove" in name.lower()
    ]


def test_the_installer_refuses_an_engine_that_is_not_sqlite() -> None:
    """A non-SQLite engine is refused by name, with no statement sent."""
    sent: list[str] = []
    engine = create_mock_engine(
        "postgresql://", lambda sql, *a, **k: sent.append(sql)
    )
    with pytest.raises(ValueError, match="postgresql"):
        triggers.install_append_only_triggers(engine)
    assert sent == []


# --- the two halves, and the one hole there is ------------------------


def test_the_mapper_guard_answers_before_any_statement_is_sent(
    log: _Log,
) -> None:
    """The ORM's own refusal is a different type, raised earlier.

    Which is why the triggers exist: this half of the guarantee never sees
    a statement the ORM did not build, and the four tests above are the
    statements it cannot see.  ``delete`` alone refuses nothing -- the
    mapper events fire at the flush, and the flush is where it stops.
    """
    entry = _append(log)
    sent: list[str] = []

    def record(
        _conn, _cursor, statement, _parameters, _context, _many
    ) -> None:
        sent.append(statement)

    event.listen(log.engine, "before_cursor_execute", record)
    try:
        with log.sessions() as session:
            row = session.get(LedgerEntry, entry.sequence)
            with pytest.raises(LedgerAppendOnlyError) as caught:
                session.delete(row)
                session.flush()
    finally:
        event.remove(log.engine, "before_cursor_execute", record)
    assert not isinstance(caught.value, IntegrityError)
    assert not [
        statement
        for statement in sent
        if statement.lstrip().upper().startswith(("UPDATE ", "DELETE "))
    ]


def test_a_replace_walks_past_the_delete_trigger_unless_triggers_recurse(
    log: _Log,
) -> None:
    """The one statement the guards do not stop, and the pragma that does.

    ``INSERT OR REPLACE`` deletes the conflicting row without firing the
    delete trigger, so a caller can overwrite a position -- with the
    default pragma, silently.  Both settings are pinned here because the
    guarantee is the pair of them, not the first.
    """
    entry = _append(log)
    parameters = (
        entry.sequence,
        str(entry.batch_id),
        entry.anchored_at.isoformat(),
    )
    _raw(log.engine, REPLACE_AT, parameters)
    with log.sessions() as session:
        replaced = session.get(LedgerEntry, entry.sequence)
    assert (replaced.sequence, replaced.merkle_root) == (
        entry.sequence,
        "forged",
    )
    with log.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA recursive_triggers = ON")
        try:
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(REPLACE_AT, parameters)
        finally:
            connection.rollback()
            connection.exec_driver_sql("PRAGMA recursive_triggers = OFF")
