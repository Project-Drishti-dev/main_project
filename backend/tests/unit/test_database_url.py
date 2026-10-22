"""8.3: a PostgreSQL URL is accepted without being connected to, and a
malformed one is refused.

The task's two claims are one question with two answers, and the first is only
worth having because of the second:

- **A ``postgresql://`` URL is accepted, and accepting it is not connecting to
  it.**  Measured in this environment: ``create_engine`` on a PostgreSQL URL
  raises ``ModuleNotFoundError: No module named 'psycopg'``, having parsed the
  URL and dialled nothing -- so a suite that tried to prove acceptance by
  building an engine would be proving the opposite.  Acceptance is asked of
  the config, and "without connecting" is held from two directions that fail
  separately: statically, that ``app/config.py`` imports the URL *parser* and
  nothing that can open a connection; and at run time, with ``socket.socket``
  poisoned while the config answers.
- **A malformed URL is refused here, where it was configured, and not passed
  on.**  The next place it would surface is 8.8's ``alembic upgrade head``,
  against a database file that may already hold rows.
- **Refusing is a ``ValueError`` naming the variable, and never quotes the
  value.**  A configured database URL carries a password and this refusal can
  reach a log, so the message is held against carrying any of it.
- **The refusal does not over-reach.**  A PostgreSQL URL may omit the host (a
  unix-socket connection is a real deployment), may name its driver
  (``postgresql+psycopg://``), and ``sqlite://`` -- the in-memory URL 8.4 may
  want -- is accepted; each of those would be a refusal that breaks a working
  configuration, which is the mistake a gate like this makes easily.
"""

import ast
import pathlib
import socket

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Dialect, make_url

from app import config
from app.storage import db


@pytest.fixture(autouse=True)
def _no_configured_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test here starts from the default, whatever the shell carries."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


def _refuse_any_socket(*_args: object, **_kwargs: object) -> None:
    """Stand in for :class:`socket.socket`, refusing to be constructed."""
    raise AssertionError("reading the configuration opened a connection")


def test_a_postgres_url_is_accepted_and_returned_as_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = "postgresql://officer:s3cr3t@db.internal:5432/drishti?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", configured)

    assert config.get_database_url() == configured


def test_an_accepted_postgres_url_still_parses_as_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance is read back off the parser rather than asserted as a
    string, so a gate that answered every URL would fail this."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://officer@db.internal:5432/drishti")

    parsed = make_url(config.get_database_url())

    assert parsed.drivername == "postgresql"
    assert parsed.username == "officer"
    assert parsed.host == "db.internal"
    assert parsed.port == 5432
    assert parsed.database == "drishti"


def test_a_postgres_url_is_accepted_without_opening_a_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task's "without connecting", measured rather than asserted: with
    the socket constructor refusing to build, the config still answers."""
    monkeypatch.setattr(socket, "socket", _refuse_any_socket)
    monkeypatch.setenv("DATABASE_URL", "postgresql://officer@db.internal:5432/drishti")

    assert config.get_database_url().startswith("postgresql://")


def test_the_config_parses_a_url_and_never_builds_an_engine() -> None:
    """The static half of the same claim, and the one that survives ``psycopg``
    being installed later.

    ``app/config.py`` may import the parser and the exception the parser
    raises, and nothing else out of SQLAlchemy: an engine, a session factory
    or a dialect is a connection with one more step, and it is
    :mod:`app.storage`'s job (``D36``).
    """
    source = ast.parse(pathlib.Path(config.__file__).read_text(encoding="utf-8"))
    sqlalchemy_imports = {
        alias.name
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("sqlalchemy")
        for alias in node.names
    }

    assert sqlalchemy_imports <= {"make_url", "ArgumentError"}


@pytest.mark.parametrize(
    "accepted",
    [
        "sqlite://",
        "sqlite:///drishti.db",
        "sqlite:////absolute/path.db",
        "sqlite:///D:/sih/main_project/backend/drishti.db",
        "postgresql://officer@db.internal:5432/drishti",
        "postgresql:///drishti",
        "postgresql+psycopg://officer@db.internal:5432/drishti",
    ],
)
def test_every_url_the_config_accepts_names_a_dialect_sqlalchemy_knows(
    accepted: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation and use cannot disagree about what a URL is, because the
    config parses with the same parser ``create_engine`` does, and resolving
    the dialect needs no DBAPI -- so this holds for the PostgreSQL rows in an
    environment where ``psycopg`` is not installed.  A URL the config waved
    through that SQLAlchemy cannot resolve raises here instead.
    """
    monkeypatch.setenv("DATABASE_URL", accepted)

    dialect = make_url(config.get_database_url()).get_dialect()

    assert isinstance(dialect, type) and issubclass(dialect, Dialect)


def test_the_accepted_url_reaches_an_engine_that_connects(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of "accepted without connecting", where connecting is
    possible: for SQLite the answer the config gives is the URL an engine is
    built from and connects on."""
    chosen = tmp_path / "chosen.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{chosen.as_posix()}")

    engine = db.build_engine(config.get_database_url())
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_the_default_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", config.DEFAULT_DATABASE_URL)

    assert (
        make_url(config.get_database_url()).drivername
        in config.SUPPORTED_DATABASE_SCHEMES
    )


@pytest.mark.parametrize(
    "malformed",
    [
        "not a url",
        "drishti.db",
        "://",
        "://officer@db.internal/drishti",
        "postgresql:/officer@db.internal/drishti",
        "postgresql://db.internal:not-a-port/drishti",
    ],
)
def test_a_malformed_url_is_refused(
    malformed: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", malformed)

    with pytest.raises(ValueError):
        config.get_database_url()


@pytest.mark.parametrize(
    "unsupported",
    [
        "postgres://officer@db.internal/drishti",
        "mysql://officer@db.internal/drishti",
        "mssql://officer@db.internal/drishti",
        "http://example.com",
    ],
)
def test_a_backend_this_service_does_not_ship_is_refused(
    unsupported: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLAlchemy reads ``postgres://`` and ``mysql://`` as URL-shaped strings
    and fails later, at a driver lookup.  ``postgres://`` in particular is the
    one typo here worth naming: it is the scheme Postgres' own older
    connection strings use, and SQLAlchemy has no dialect under that name.
    """
    monkeypatch.setenv("DATABASE_URL", unsupported)

    with pytest.raises(ValueError, match="postgresql"):
        config.get_database_url()


@pytest.mark.parametrize(
    "nameless", ["postgresql://", "postgresql://officer@db.internal/", "postgresql://officer@db.internal:5432/"]
)
def test_a_postgres_url_naming_no_database_is_refused(
    nameless: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PostgreSQL URL without a database is a connection to a name the
    deployment has to have, and refusing it here is the difference between a
    configuration error and a failed migration against a file holding rows."""
    monkeypatch.setenv("DATABASE_URL", nameless)

    with pytest.raises(ValueError):
        config.get_database_url()


def test_a_refusal_names_the_variable_and_quotes_none_of_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``DATABASE_URL`` carries a password, and this refusal can reach a log
    that someone attaches to a ticket, so the message names the variable and
    no part of what it was set to."""
    monkeypatch.setenv("DATABASE_URL", "mysql://officer:hunter2@db.internal/drishti")

    with pytest.raises(ValueError) as refusal:
        config.get_database_url()

    assert "DATABASE_URL" in str(refusal.value)
    assert "hunter2" not in str(refusal.value)
    assert "db.internal" not in str(refusal.value)


def test_a_malformed_url_is_refused_rather_than_defaulted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answering the local SQLite file instead would be the worse failure: a
    misconfigured deployment would come up, empty, against a file nobody
    meant to open."""
    monkeypatch.setenv("DATABASE_URL", "not a url")

    with pytest.raises(ValueError) as refusal:
        config.get_database_url()

    assert config.DEFAULT_DATABASE_URL not in str(refusal.value)


@pytest.mark.parametrize(
    "value",
    ["", " ", "\t", "  postgresql://officer@db.internal/drishti  "],
)
def test_whitespace_is_stripped_before_the_url_is_read(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first three are the blank ``.env.example`` ships, which 8.2 made an
    unset value; the last is a padded value from a shell or a compose file,
    which is a URL with whitespace around it.  ``make_url`` refuses the second
    outright -- a leading space is not a URL -- so the strip has to come first
    or a padded deployment value would be reported as malformed."""
    monkeypatch.setenv("DATABASE_URL", value)

    answer = config.get_database_url()

    if value.strip():
        assert answer == "postgresql://officer@db.internal/drishti"
    else:
        assert answer == config.DEFAULT_DATABASE_URL
