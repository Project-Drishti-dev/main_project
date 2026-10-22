"""8.2: the default is a local SQLite file, and ``DATABASE_URL`` is the only
thing that moves it.

The task's one claim is "defaulting to a local SQLite file, overridable by
``DATABASE_URL``", and these are the two halves of it plus the two properties
that make them usable by 8.4 to 8.9 rather than merely true today:

- **the default is SQLite, read off the engine and off the config, not typed
  into a test.**  A default that stopped being SQLite would still leave a
  passing suite if the assertions restated what the module says, so the
  dialect name is read from the engine SQLAlchemy built.
- **building is free of side effects.**  The file appears on the first
  connection and not before, which is why importing this module in a suite
  run leaves no database behind -- asserted against a path in ``tmp_path``
  rather than against the committed default, which cannot be un-created by a
  test that runs twice.
- **the caller's path is honoured**, because 8.9 upgrades and downgrades a
  temporary database and the module-level pair cannot be that.
- **the module-level pair is read once**, and a builder re-reads the
  environment on every call: the two claims together are what let a test move
  the database without reimporting the module.
"""

import pathlib

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import config
from app.storage import db


@pytest.fixture(autouse=True)
def _no_configured_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test here starts from the default, whatever the shell carries."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


def _sqlite_url(path: pathlib.Path) -> str:
    """A SQLite URL for ``path``, in the posix spelling :mod:`app.config` uses."""
    return f"sqlite:///{path.as_posix()}"


def _is_the_same_file(url_path: str, path: pathlib.Path) -> bool:
    """Whether a database path read back off a URL is ``path``.

    Compared as paths rather than as strings: SQLAlchemy normalises the
    separators of a URL and percent-escapes a Windows drive letter, so
    ``D:\\...\\drishti.db`` and ``D%3A/.../drishti.db`` are one file written two
    ways.
    """
    return pathlib.PurePath(url_path) == path


def test_the_configured_url_is_the_default_when_the_variable_is_unset() -> None:
    assert config.get_database_url() == config.DEFAULT_DATABASE_URL


@pytest.mark.parametrize("blank", ["", " ", "\t", "\n", "  \t "])
def test_a_blank_value_is_read_as_unset(
    blank: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``.env.example`` ships ``DATABASE_URL=`` empty, and copying it to
    ``.env`` must not turn the default into a URL nothing can parse."""
    monkeypatch.setenv("DATABASE_URL", blank)

    assert config.get_database_url() == config.DEFAULT_DATABASE_URL


def test_the_configured_url_is_returned_as_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The config does not re-serialise what it was given; whether the URL is
    acceptable at all is 8.3's question of the same answer, in
    ``test_database_url.py``."""
    configured = "postgresql://db.internal:5432/drishti"
    monkeypatch.setenv("DATABASE_URL", f"  {configured}  ")

    assert config.get_database_url() == configured


def test_the_default_is_a_sqlite_file() -> None:
    assert db.engine.dialect.name == "sqlite"
    assert _is_the_same_file(
        db.engine.url.database, config.DEFAULT_DATABASE_PATH
    )


def test_the_default_file_is_absolute_and_sits_beside_the_code() -> None:
    """A relative path would be a different database per launch directory."""
    assert pathlib.PurePath(db.engine.url.database).is_absolute()
    assert config.DEFAULT_DATABASE_PATH.parent == config.BACKEND_DIR
    assert config.DEFAULT_DATABASE_PATH.suffix == ".db"


def test_the_default_is_the_config_default_not_a_second_copy() -> None:
    assert db.engine.url == make_url(config.DEFAULT_DATABASE_URL)


def test_the_session_factory_is_bound_to_the_module_level_engine() -> None:
    with db.SessionLocal() as session:
        assert session.get_bind() is db.engine


def test_each_call_to_the_session_factory_is_a_new_session() -> None:
    with db.SessionLocal() as first, db.SessionLocal() as second:
        assert first is not second


def test_the_factory_commits_without_expiring(
) -> None:
    """A repository method returns the row it wrote and the session closes, so
    the object has to survive that; 8.10 is where the effect is exercised."""
    assert db.SessionLocal.kw["expire_on_commit"] is False


def test_database_url_overrides_the_default(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(tmp_path / "chosen.db"))

    chosen = db.build_engine()

    assert chosen is not db.engine
    assert _is_the_same_file(chosen.url.database, tmp_path / "chosen.db")


def test_an_explicit_url_overrides_the_configured_one(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The argument is how 8.9 reaches a temporary database without touching
    the environment of the process running the migrations."""
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(tmp_path / "environment.db"))

    explicit = db.build_engine(_sqlite_url(tmp_path / "explicit.db"))

    assert _is_the_same_file(explicit.url.database, tmp_path / "explicit.db")


def test_building_an_engine_creates_no_file(
    tmp_path: pathlib.Path,
) -> None:
    """SQLAlchemy parses a URL and allocates a pool; the file appears on the
    first connection, so importing this module in a suite run leaves nothing."""
    path = tmp_path / "lazy.db"
    engine = db.build_engine(_sqlite_url(path))
    try:
        assert not path.exists()

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        assert path.is_file()
    finally:
        engine.dispose()


def test_a_session_from_a_caller_built_factory_reads_its_own_database(
    tmp_path: pathlib.Path,
) -> None:
    """The whole shape 8.9 needs, exercised now: an engine and a factory over
    a path the caller chose, reaching a working database."""
    path = tmp_path / "temporary.db"
    sessions = db.build_session_factory(db.build_engine(_sqlite_url(path)))
    engine = sessions.kw["bind"]
    try:
        with sessions() as session:
            assert session.get_bind() is engine
            assert session.execute(text("SELECT 1")).scalar_one() == 1

        assert path.is_file()
    finally:
        engine.dispose()


def test_a_caller_built_pair_never_reaches_the_default_database(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "isolated.db"
    sessions = db.build_session_factory(db.build_engine(_sqlite_url(path)))
    engine = sessions.kw["bind"]
    try:
        with sessions() as session:
            session.execute(text("SELECT 1"))

        assert engine is not db.engine
        assert _is_the_same_file(engine.url.database, path)
        assert engine.url.database != db.engine.url.database
    finally:
        engine.dispose()
