"""16.1: a ``TravelerCase`` row survives a write and a read, and a migration.

The task's verify is "a test round-tripping a case", so that is the first
test here and the rest are the claims a round trip alone would not catch:

- **the migrated database, not only the mapping.**  The round trip is run
  twice: once against a schema ``create_all`` built, and once against a
  schema ``alembic upgrade head`` built, because a table the migration
  forgot still round-trips through the ORM.
- **the ORM stamps ``id`` and ``created_at``.**  A caller that supplied
  neither is the only evidence that the defaults are declared here, so the
  test writes the label alone.
- **``label`` is required.**  A nullable label round-trips as ``None`` and
  reads back as a case with nothing to be found by, which is the state
  16.1's own column list is written to refuse.
- **a downgrade takes the rows with it and the rebuilt table takes one
  again.**  8.9's round trip holds this for ``screenings``; a table added
  by a later revision has to earn it separately.
"""

import pathlib
from collections.abc import Iterator
from datetime import timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.storage import db
from app.storage.models import (
    TRAVELER_CASE_TABLE_NAME,
    Base,
    TravelerCase,
)


#: The columns 16.1 names, in the order it names them.
EXPECTED_COLUMNS = ("id", "created_at", "label")

#: The alembic configuration this service migrates with, found beside the
#: tests rather than spelled as a relative path: the suite runs from the
#: repository root (``check-all.ps1``).
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture
def created_schema() -> Iterator[Engine]:
    """One in-memory database with the schema ``create_all`` built in it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def sessions(created_schema: Engine) -> sessionmaker[Session]:
    """A session factory over :func:`created_schema`."""
    return db.build_session_factory(created_schema)


@pytest.fixture
def migrated_database(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """A SQLite file upgraded to head, configured as the database."""
    database = tmp_path / "drishti.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    yield database


def _factory_for(database: pathlib.Path) -> sessionmaker[Session]:
    """A session factory over the migrated ``database``."""
    return db.build_session_factory(db.build_engine(f"sqlite:///{database.as_posix()}"))


def _open_one(sessions: sessionmaker[Session]) -> TravelerCase:
    """Write one case carrying a label and nothing else, and return it."""
    case = TravelerCase(label="Ravi Kulkarni -- arrival 14 Oct")
    with sessions() as session:
        session.add(case)
        session.commit()
    return case


def _count_cases(sessions: sessionmaker[Session]) -> int:
    """How many rows ``traveler_cases`` holds, read back through the ORM."""
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(TravelerCase))


def _the_one_case(sessions: sessionmaker[Session]) -> TravelerCase:
    """The single row ``traveler_cases`` holds, read back through the ORM."""
    with sessions() as session:
        return session.execute(select(TravelerCase)).scalars().one()


# --- the task's verify ------------------------------------------------


def test_a_case_round_trips(sessions: sessionmaker[Session]) -> None:
    """Write a case, close the session, read it back in another one.

    The label is what the caller handed over and the other two columns are
    what the ORM stamped, so all three are asserted against a row fetched
    by a session that never saw the insert.

    The stamp is compared after re-attaching UTC: SQLite stores no zone, so
    the ORM's value comes back naive and the instant is the same one.  This
    is the same round trip :attr:`Screening.created_at` has.
    """
    written = _open_one(sessions)

    read_back = _the_one_case(sessions)

    assert read_back.id == written.id
    assert read_back.label == "Ravi Kulkarni -- arrival 14 Oct"
    assert read_back.created_at.replace(tzinfo=timezone.utc) == written.created_at


def test_a_case_round_trips_through_a_migrated_database(
    migrated_database: pathlib.Path,
) -> None:
    """The same round trip against a schema the migration built.

    ``create_all`` builds the schema from the mapping, so it would round
    trip a table 16.1's migration never created.  This is the half that
    holds the migration to the model.
    """
    written = _open_one(_factory_for(migrated_database))

    read_back = _the_one_case(_factory_for(migrated_database))

    assert (read_back.id, read_back.label) == (
        written.id,
        "Ravi Kulkarni -- arrival 14 Oct",
    )


# --- the two columns this module stamps -------------------------------


def test_the_caller_supplies_only_the_label(sessions: sessionmaker[Session]) -> None:
    """``id`` and ``created_at`` are filled in without being handed over.

    A default that the caller could equally supply would not be a default,
    so neither appears in the row that was written.
    """
    _open_one(sessions)

    row = _the_one_case(sessions)

    assert row.id is not None
    assert row.created_at is not None


def test_two_cases_get_different_ids_and_stamps(
    sessions: sessionmaker[Session],
) -> None:
    """Each case is its own row: nothing about the label makes it shared."""
    with sessions() as session:
        session.add_all(
            [TravelerCase(label="case one"), TravelerCase(label="case one")]
        )
        session.commit()

    with sessions() as session:
        rows = session.execute(select(TravelerCase)).scalars().all()

    assert len(rows) == 2
    assert len({row.id for row in rows}) == 2


# --- the three columns, and no fourth ---------------------------------


def test_the_table_carries_exactly_the_three_columns_named(
    created_schema: Engine,
) -> None:
    """Reflected column names, in the order the task names them.

    Read from the created schema rather than from ``Base.metadata``, so a
    column a later task adds is visible here as a fourth.
    """
    columns = inspect(created_schema).get_columns(TRAVELER_CASE_TABLE_NAME)

    assert [c["name"] for c in columns] == list(EXPECTED_COLUMNS)


def test_the_migrated_table_carries_the_same_three(
    migrated_database: pathlib.Path,
) -> None:
    """The same three, in the same order, out of the migrated database."""
    engine = db.build_engine(f"sqlite:///{migrated_database.as_posix()}")
    try:
        columns = inspect(engine).get_columns(TRAVELER_CASE_TABLE_NAME)
    finally:
        engine.dispose()

    assert [c["name"] for c in columns] == list(EXPECTED_COLUMNS)


def test_a_case_with_no_label_is_refused(
    sessions: sessionmaker[Session],
) -> None:
    """``label`` is required, so the row cannot be written without one.

    The refusal is the database's, not a check in this module: a
    ``nullable=True`` column would accept the row and read it back as a
    case with nothing to be found by.
    """
    with pytest.raises(IntegrityError):
        with sessions() as session:
            session.add(TravelerCase())
            session.commit()


# --- 16.1's migration, round tripped ----------------------------------


def test_the_round_trip_drops_the_case_and_the_rebuilt_table_takes_one(
    migrated_database: pathlib.Path,
) -> None:
    """``downgrade base`` then ``upgrade head`` on a file holding a case.

    Both halves fail separately, so both are asserted: a downgrade that
    kept the row, and an upgrade that recreated the table's name without
    the columns the insert names.
    """
    config = Config(str(ALEMBIC_INI))
    _open_one(_factory_for(migrated_database))

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    assert _count_cases(_factory_for(migrated_database)) == 0

    _open_one(_factory_for(migrated_database))

    assert _count_cases(_factory_for(migrated_database)) == 1


def test_no_database_file_is_left_in_the_repository() -> None:
    """Running this file creates no ``backend/drishti.db``.

    Every test here points ``DATABASE_URL`` at ``tmp_path``; this is the
    check on that, because a relative URL would put its file in whichever
    directory the suite was started from.
    """
    backend = ALEMBIC_INI.parent
    assert not (backend / "drishti.db").exists()
    assert not (pathlib.Path.cwd() / "drishti.db").exists()
