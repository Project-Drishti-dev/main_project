"""8.8: alembic is initialised, and ``upgrade head`` builds the models.

The task's verify is "``alembic upgrade head`` on a fresh file succeeds", so
this file runs exactly that -- through the same code path a deploy step
would, rather than by asserting on a script's text:

- **the migration, not the mapping.**  The schema is read back out of a
  migrated database with :func:`sqlalchemy.inspect`, because an
  ``op.create_table`` in a version file is a claim about a script and a
  reflected table is a claim about the database 11.1 will insert into.
- **one URL, and it is the service's.**  ``alembic/env.py`` asks
  :func:`app.config.get_database_url` rather than reading ``alembic.ini`` or
  the environment a second time, so a database that was migrated and a
  database that is served cannot be two different files.  Held from both
  sides: the migration follows ``DATABASE_URL`` when it is set, and
  ``alembic.ini`` names no URL of its own.
- **the default is the SQLite file, and it is a file.**  Not ``:memory:``,
  because 8.2's own reasoning is that the schema is migrated in one process
  and read in another; a suite that upgraded an in-memory database would
  prove nothing about the service.
- **the schema matches the models.**  ``alembic check`` re-runs
  autogenerate against the migrated database and must find nothing to do,
  which is the claim a hand-written migration most often stops making: that
  a column added to ``models.py`` later is a column the first migration
  never had.
- **and the migration comes back off.**  8.9's ``upgrade head`` then
  ``downgrade base`` then ``upgrade head`` runs at the bottom of this file,
  on the same temp file, so ``downgrade`` is measured rather than assumed:
  an index left behind by it is an index the second upgrade collides on.
"""

import configparser
import pathlib
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, func, inspect, select

from app import config
from app.storage import db
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    LEDGER_ENTRY_TABLE_NAME,
    NAMING_CONVENTION,
    SCREENING_TABLE_NAME,
    TRAVELER_CASE_TABLE_NAME,
    Base,
    Screening,
)


#: The alembic configuration this service migrates with, found beside the
#: tests rather than spelled as a relative path: the suite runs from the
#: repository root (``check-all.ps1``) and a ``cd backend`` here would be a
#: second answer to "where is alembic.ini" that the root run disagrees with.
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"

#: Where the version scripts live, so the tests can name one rather than
#: spelling ``backend/alembic/versions`` three more times.
VERSIONS_DIR = ALEMBIC_INI.parent / "alembic" / "versions"

#: The three tables 8.4 to 8.7 mapped, against the one alembic keeps of its
#: own, so "the schema is here" is a set rather than three remembered names.
APPLICATION_TABLES = frozenset(
    {
        SCREENING_TABLE_NAME,
        AUDIT_EVENT_TABLE_NAME,
        LEDGER_ENTRY_TABLE_NAME,
        TRAVELER_CASE_TABLE_NAME,
    }
)


@pytest.fixture
def fresh_database(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """A SQLite file that does not exist yet, configured as the database.

    ``tmp_path`` is outside the repository, so a failed run cannot leave a
    ``drishti.db`` beside the code -- and the file is *absent* to begin with,
    which is the "fresh file" the task's verify names.
    """
    database = tmp_path / "drishti.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    assert not database.exists()
    yield database


def _config() -> Config:
    """A fresh :class:`~alembic.config.Config` over the project's ini file."""
    return Config(str(ALEMBIC_INI))


def _head_revision() -> str:
    """The one revision ``head`` names, read from the scripts."""
    return ScriptDirectory.from_config(_config()).get_current_head()


def _the_migration() -> pathlib.Path:
    """The first version file: the one 8.5's schema was created in."""
    script = sorted(VERSIONS_DIR.glob("*.py"))[0]
    return script


def _schema_shape(
    database: pathlib.Path,
) -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """Every table's columns and indexes, as the database reports them.

    Read through :func:`sqlalchemy.inspect` rather than from
    ``Base.metadata``, so a table the migration forgot is visible here and
    two databases can be compared for equality.
    """
    engine = db.build_engine(f"sqlite:///{database.as_posix()}")
    try:
        inspector = inspect(engine)
        return {
            table: (
                frozenset(c["name"] for c in inspector.get_columns(table)),
                frozenset(i["name"] for i in inspector.get_indexes(table)),
            )
            for table in inspector.get_table_names()
        }
    finally:
        engine.dispose()


def _stamped_revision(database: pathlib.Path) -> str | None:
    """The revision ``alembic_version`` records, or ``None`` at base."""
    engine = db.build_engine(f"sqlite:///{database.as_posix()}")
    try:
        with engine.connect() as connection:
            return connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def _write_one_screening(database: pathlib.Path) -> None:
    """Write the one row 8.4 says this table holds before analysis runs."""
    engine = db.build_engine(f"sqlite:///{database.as_posix()}")
    factory = db.build_session_factory(engine)
    try:
        with factory() as session:
            session.add(
                Screening(
                    document_type="passport",
                    filename="specimen.png",
                    image_width=640,
                    image_height=480,
                )
            )
            session.commit()
    finally:
        engine.dispose()


def _count_screenings(database: pathlib.Path) -> int:
    """How many rows ``screenings`` holds, read back through the ORM."""
    engine = db.build_engine(f"sqlite:///{database.as_posix()}")
    factory = db.build_session_factory(engine)
    try:
        with factory() as session:
            return session.scalar(select(func.count()).select_from(Screening))
    finally:
        engine.dispose()


# --- the task's verify ----------------------------------------------


def test_upgrade_head_on_a_fresh_file_succeeds(fresh_database: pathlib.Path) -> None:
    """``alembic upgrade head`` on a file that does not exist yet.

    The whole claim: the file appears, and alembic stamped it ``head``.
    Asserted through the file rather than through alembic's exit status, so
    a run that created the database and then failed to record the revision
    fails here too.
    """
    command.upgrade(_config(), "head")

    assert fresh_database.exists()
    engine = db.build_engine(f"sqlite:///{fresh_database.as_posix()}")
    with engine.connect() as connection:
        stamped = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    engine.dispose()

    assert stamped == _head_revision()


def test_upgrade_head_is_idempotent(fresh_database: pathlib.Path) -> None:
    """Running it twice is still one revision, not a second ``CREATE TABLE``.

    A deploy step that runs ``upgrade head`` on every boot is the ordinary
    case, so "succeeds" has to mean on the second run as well as the first.
    """
    command.upgrade(_config(), "head")
    command.upgrade(_config(), "head")

    engine = db.build_engine(f"sqlite:///{fresh_database.as_posix()}")
    try:
        assert set(inspect(engine).get_table_names()) == {
            SCREENING_TABLE_NAME,
            AUDIT_EVENT_TABLE_NAME,
            LEDGER_ENTRY_TABLE_NAME,
            TRAVELER_CASE_TABLE_NAME,
            "alembic_version",
        }
    finally:
        engine.dispose()


# --- the schema is the models -------------------------------------


def test_the_migrated_schema_matches_the_models(
    fresh_database: pathlib.Path,
) -> None:
    """Autogenerate finds nothing to do against a migrated database.

    This is the claim "the first migration matching the models", held
    against a schema rather than against the version file: a column added
    to ``models.py`` and not to the migration shows up here as a diff,
    because the database was built from the migration and the comparison
    is against the mapping.
    """
    command.upgrade(_config(), "head")

    engine = db.build_engine(f"sqlite:///{fresh_database.as_posix()}")
    try:
        with engine.connect() as connection:
            diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    finally:
        engine.dispose()

    assert diffs == []


@pytest.mark.parametrize(
    ("table_name", "column_count"),
    [
        (SCREENING_TABLE_NAME, 16),
        (AUDIT_EVENT_TABLE_NAME, 10),
        (LEDGER_ENTRY_TABLE_NAME, 5),
        (TRAVELER_CASE_TABLE_NAME, 3),
    ],
)
def test_every_table_lands_with_the_columns_its_model_declares(
    table_name: str,
    column_count: int,
    fresh_database: pathlib.Path,
) -> None:
    """Reflected column count, against the count the model declares.

    Read from the database rather than from ``Base.metadata`` so a table
    the migration forgot, or one carrying an extra column, is visible here.
    """
    command.upgrade(_config(), "head")

    engine = db.build_engine(f"sqlite:///{fresh_database.as_posix()}")
    try:
        reported = {c["name"] for c in inspect(engine).get_columns(table_name)}
    finally:
        engine.dispose()

    assert reported == {c.name for c in Base.metadata.tables[table_name].columns}
    assert len(reported) == column_count


# --- 8.7's indexes, created by the migration ---------------------------


@pytest.mark.parametrize("column", ("created_at", "band"))
def test_the_migration_creates_the_indexes_under_the_names_8_7_fixed(
    column: str,
    fresh_database: pathlib.Path,
) -> None:
    """8.7's handover said the migration must create these by name.

    The name is recomputed from ``NAMING_CONVENTION`` rather than written
    out, so a rename of the convention or of the table moves the expectation
    with it -- which is what lets ``downgrade`` drop what ``upgrade``
    created.
    """
    command.upgrade(_config(), "head")

    wanted = NAMING_CONVENTION["ix"] % {
        "table_name": SCREENING_TABLE_NAME,
        "column_0_N_name": column,
    }
    engine = db.build_engine(f"sqlite:///{fresh_database.as_posix()}")
    try:
        reported = {
            index["name"]: index
            for index in inspect(engine).get_indexes(SCREENING_TABLE_NAME)
        }
    finally:
        engine.dispose()

    assert wanted in reported
    assert reported[wanted]["column_names"] == [column]
    assert not reported[wanted]["unique"]


def test_the_indexes_come_from_create_index_not_from_create_table() -> None:
    """``upgrade`` issues a ``CREATE INDEX`` of its own, beside the table.

    8.7 measured that SQLite keeps the two out of ``CREATE TABLE``; this
    reads the migration's own calls rather than re-measuring the dialect,
    because the thing 8.8 owes 8.7 is that this file calls
    ``op.create_index``.
    """
    source = _the_migration().read_text(encoding="utf-8")

    assert "create_index" in source
    for column in ("created_at", "band"):
        assert (
            NAMING_CONVENTION["ix"]
            % {
                "table_name": SCREENING_TABLE_NAME,
                "column_0_N_name": column,
            }
            in source
        )


# --- one URL -----------------------------------------------------------


def test_the_migration_follows_the_configured_url(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DATABASE_URL`` names the file the migration writes to.

    The deploy case is 26.5's PostgreSQL one; SQLite stands in for it here
    because it is the only backend with a driver installed, and the claim is
    about *which file* rather than about which backend.
    """
    elsewhere = tmp_path / "elsewhere.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{elsewhere.as_posix()}")

    command.upgrade(_config(), "head")

    assert elsewhere.exists()


def test_the_default_url_is_the_sqlite_file_alembic_writes_to() -> None:
    """With nothing configured, the URL is a SQLite *file*, not ``:memory:``.

    Read from ``env.py``'s own source rather than by upgrading: the default
    is a real path in the repository, and a suite must not create it.
    """
    env_source = (
        pathlib.Path(__file__).resolve().parents[2] / "alembic" / "env.py"
    ).read_text(encoding="utf-8")

    assert "get_database_url" in env_source
    assert config.DEFAULT_DATABASE_URL.startswith("sqlite:///")
    assert ":memory:" not in config.DEFAULT_DATABASE_URL
    assert config.DEFAULT_DATABASE_URL.endswith("/drishti.db")


def test_the_ini_names_no_url_of_its_own() -> None:
    """``alembic.ini`` carries no ``sqlalchemy.url``.

    A URL written here is a second spelling of ``DATABASE_URL``, and it is
    the one that would win on a deployment where someone set it months ago
    and forgot -- migrating a database the service never reads.

    Read through a parser, so a *comment* naming the key does not fail this
    and an active line setting it cannot hide behind one.
    """
    parser = configparser.ConfigParser()
    parser.read(ALEMBIC_INI, encoding="utf-8")

    assert "sqlalchemy.url" not in parser["alembic"]


def test_the_ini_resolves_its_paths_against_itself() -> None:
    """``script_location`` and ``prepend_sys_path`` are ``%(here)s``.

    Both resolve against this ini file rather than the working directory,
    so ``alembic upgrade head`` reaches ``app`` whether it is invoked from
    ``backend/`` or from the repository root.

    Read raw: ``%(here)s`` is alembic's own token, so a plain parser would
    try to interpolate it as a configparser reference and raise.
    """
    parser = configparser.ConfigParser()
    parser.read(ALEMBIC_INI, encoding="utf-8")

    assert (
        parser.get("alembic", "script_location", raw=True) == "%(here)s/alembic"
    )
    assert parser.get("alembic", "prepend_sys_path", raw=True) == "%(here)s"


def test_no_migration_leaves_a_database_file_behind(tmp_path: pathlib.Path) -> None:
    """Running the suite creates no ``backend/drishti.db``.

    Every test here points ``DATABASE_URL`` at ``tmp_path``.  This is the
    check on that: the repository's own default file is absent, *and* no
    ``drishti.db`` appeared where the process was started.

    Two places, because they fail separately.  A relative URL such as
    ``sqlite:///drishti.db`` resolves against the working directory, so a
    suite run from the repository root would leave its file in the root and
    leave ``backend/`` clean -- and 8.2's reason for an absolute default
    ("a different database per launch directory") is exactly that.
    """
    assert not config.DEFAULT_DATABASE_PATH.exists()
    assert not (pathlib.Path.cwd() / "drishti.db").exists()
    assert not (pathlib.Path.cwd() / config.DEFAULT_DATABASE_FILENAME).exists()


# --- offline mode ------------------------------------------------------


def test_offline_mode_emits_sql_without_touching_a_file(
    fresh_database: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--sql`` emits the DDL and creates no file.

    The offline path is the one a PostgreSQL review runs before a deploy,
    and it must answer without a driver and without a database.
    """
    command.upgrade(_config(), "head", sql=True)

    emitted = capsys.readouterr().out
    assert "CREATE TABLE screenings" in emitted
    assert "CREATE INDEX ix_screenings_band" in emitted
    assert not fresh_database.exists()


def test_every_migration_is_on_one_chain_from_base_to_head() -> None:
    """One chain, so ``head`` and ``base`` are the same pair of endpoints.

    10.2 added a second revision rather than amending 8.5's, because a
    column a database already holds rows without is a migration and not an
    edit to the file that created the table.  What has to hold is that every
    version file sits on that one chain, which is what 8.9's round trip below
    walks up and back down.
    """
    script = ScriptDirectory.from_config(_config())

    assert len(script.get_heads()) == 1, "a second head is a second chain"
    assert len(script.get_bases()) == 1, "a second base is a second chain"
    assert len(list(script.walk_revisions())) == len(
        list(VERSIONS_DIR.glob("*.py"))
    )


# --- 8.9: upgrade, downgrade, upgrade --------------------------------


def test_the_round_trip_leaves_the_schema_it_started_from(
    fresh_database: pathlib.Path,
) -> None:
    """``upgrade head``, ``downgrade base``, ``upgrade head``.

    The whole claim, and it is a comparison rather than a presence check:
    every table's columns and indexes after the second upgrade are the ones
    the first upgrade built. A ``downgrade`` that dropped a column it should
    have kept, or a table it should not have touched, shows up as a shape
    that differs.
    """
    command.upgrade(_config(), "head")
    first = _schema_shape(fresh_database)

    command.downgrade(_config(), "base")
    command.upgrade(_config(), "head")

    assert _schema_shape(fresh_database) == first
    assert set(_schema_shape(fresh_database)) == APPLICATION_TABLES | {
        "alembic_version"
    }
    assert _stamped_revision(fresh_database) == _head_revision()


def test_downgrade_base_leaves_the_database_at_base(
    fresh_database: pathlib.Path,
) -> None:
    """The middle step really is ``base``, not a half-applied head.

    The three tables are gone and ``alembic_version`` records no revision,
    so a rollback leaves a database the next ``upgrade head`` can build into
    rather than one stamped ``head`` over an empty schema.
    """
    command.upgrade(_config(), "head")

    command.downgrade(_config(), "base")

    assert set(_schema_shape(fresh_database)) == {"alembic_version"}
    assert _stamped_revision(fresh_database) is None


def test_the_indexes_come_back_after_a_downgrade(
    fresh_database: pathlib.Path,
) -> None:
    """``downgrade`` drops what ``upgrade`` created, by the same two names.

    An index the downgrade left behind is an index the second ``upgrade``
    collides on, so the round trip passing is itself the evidence; this
    asserts the two names are back rather than trusting the exit status.
    """
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "base")

    command.upgrade(_config(), "head")

    _, indexes = _schema_shape(fresh_database)[SCREENING_TABLE_NAME]
    assert indexes == {
        NAMING_CONVENTION["ix"]
        % {"table_name": SCREENING_TABLE_NAME, "column_0_N_name": column}
        for column in ("created_at", "band")
    }


def test_the_schema_rebuilt_by_the_round_trip_matches_the_models(
    fresh_database: pathlib.Path,
) -> None:
    """Autogenerate still finds nothing to do after a full round trip.

    8.8's claim held the *first* upgrade against the models; this holds the
    second, because a ``downgrade`` that dropped something and an ``upgrade``
    that did not put it back would still leave a stamped database.
    """
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "base")
    command.upgrade(_config(), "head")

    engine = db.build_engine(f"sqlite:///{fresh_database.as_posix()}")
    try:
        with engine.connect() as connection:
            diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    finally:
        engine.dispose()

    assert diffs == []


def test_the_round_trip_drops_the_data_and_the_schema_takes_a_row_again(
    fresh_database: pathlib.Path,
) -> None:
    """A downgrade removes the rows, and the rebuilt table is writable.

    Two claims in one run, because either alone would pass on a broken
    migration: a ``downgrade`` that kept the rows, and an ``upgrade`` that
    recreated the table's name without the columns 11.1 inserts into.
    """
    command.upgrade(_config(), "head")
    _write_one_screening(fresh_database)
    assert _count_screenings(fresh_database) == 1

    command.downgrade(_config(), "base")
    command.upgrade(_config(), "head")

    assert _count_screenings(fresh_database) == 0
    _write_one_screening(fresh_database)
    assert _count_screenings(fresh_database) == 1
