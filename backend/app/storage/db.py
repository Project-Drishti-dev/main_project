"""The engine and the session factory, and nothing else: no table, no query.

Task 8.2 asks for one engine and one session factory, defaulting to a local
SQLite file and overridable by ``DATABASE_URL``.  This module is that pair and
the two builders that make them, so the rest of Part 8 never spells a URL.

**The URL is configuration, and it is read from :mod:`app.config`.**  Not from
an ``os.environ`` call here: ``app/config.py`` is the one module that reads
the environment (``D28``'s note that it stays the deployment and HTTP-boundary
config), so ``app/storage`` asks
:func:`~app.config.get_database_url` for the answer rather than taking a
second reading of the same variable and disagreeing with the first.

**The default is a file, and it is absolute.**  ``:memory:`` would give every
connection its own empty database, so the tables alembic migrates in one
process (8.8) would be invisible to the service in another; and a path relative
to the current working directory would be a different database per launch
directory.  The file lives beside the code that uses it and is covered by
``.gitignore``'s ``*.db``.

**Building an engine opens no connection, and this module therefore has no
side effect at import.**  ``create_engine`` parses a URL and allocates a pool;
the file appears on the first connect.  So importing ``app.storage.db`` in a
test run does not leave a database behind, and a configuration error surfaces
where the connection is actually wanted rather than at import of an unrelated
module.

**An in-memory SQLite URL is given a ``StaticPool``, because the dialect's own
pool for one gives every thread its own empty database.**  ``sqlite://`` is a
URL ``D37`` accepts on purpose, and SQLAlchemy answers it with a
``SingletonThreadPool``: one connection per thread, each opening its own
private in-memory database.  Measured with SQLAlchemy 2.1.1, a second thread
reading a row the first had written gets ``no such table``.  A service
running synchronous endpoints in a thread pool is several threads, so the
one-connection pool and ``check_same_thread`` off are what make that URL mean
"one database" rather than "one database per thread".  Every other URL is
left to the dialect's own pool.

**The two builders are separate questions, so a caller can hold the engine it
is using.**  :func:`build_engine` answers "which engine", and
:func:`build_session_factory` answers "which sessions", taking the engine it
was given.  Wiring them the other way -- a session factory that builds its own
engine from a URL -- would mean the module-level ``SessionLocal`` held an
engine no name referred to, and a caller asking for a second database would
get a second pool against the same file rather than the engine it asked for.
8.9 upgrades and downgrades a temporary database, which is the caller this
split exists for:
``build_session_factory(build_engine(f"sqlite:///{path}"))``.

**The module-level pair is read at import time, and a test that changes the
environment afterwards must call the builder again.**  ``engine`` and
``SessionLocal`` are the wiring the service uses; they are bound to whatever
``DATABASE_URL`` said when the module was first imported, which is what "the
service reads its configuration once at start-up" means.  ``build_engine()``
reads it on every call, so an override is testable without reimporting.

**A committed session leaves its objects usable.**  ``expire_on_commit=False``
is set on the factory, because a repository method (8.10) returns the object
it wrote and the caller reads it after the session has closed; with the
default, every attribute of that object would raise
``DetachedInstanceError`` on the next read.

**Invariants**

- :func:`build_engine` opens no connection and creates no file, whatever the
  URL is.
- :func:`build_engine` changes the pool only for an in-memory SQLite URL: a
  file or a PostgreSQL URL gets whatever its dialect ships.
- The two builders share nothing: a session factory is bound to exactly the
  engine it was handed, and the module-level ``SessionLocal`` to exactly the
  module-level ``engine``.
- No SQLAlchemy object is created, mutated or closed here -- no ``MetaData``,
  no ``Base``, no mapper.  8.4 owns the models.
- Nothing here reaches a clock or the network, and nothing here reads a
  document, so an import is as cheap as the module that calls it.
"""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_database_url

__all__ = [
    "SessionLocal",
    "build_engine",
    "build_session_factory",
    "engine",
]


def build_engine(url: str | None = None) -> Engine:
    """An engine for ``url``, or for the configured default.

    :param url: a SQLAlchemy URL.  ``None`` -- the default -- asks
        :func:`~app.config.get_database_url`, which is
        ``DATABASE_URL`` when it is set and a local SQLite file when it is not.
    :returns: an :class:`~sqlalchemy.Engine` that has opened no connection and
        created no file.
    :raises ~sqlalchemy.exc.ArgumentError: when ``url`` cannot be parsed at all.
    :raises ModuleNotFoundError: when ``url`` names a scheme whose driver is
        not installed.  Measured in this environment: ``postgresql://`` raises
        ``No module named 'psycopg'`` here, with no connection attempted --
        SQLAlchemy imports the DBAPI to build the dialect.  Which is why
        :func:`~app.config.get_database_url` asks whether a URL is acceptable
        before a builder is ever handed one, so a malformed value is refused
        where it was configured rather than here, where the driver lookup
        would answer for it instead.
    """
    resolved = get_database_url() if url is None else url
    if _is_in_memory_sqlite(resolved):
        return create_engine(
            resolved,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    return create_engine(resolved)


def _is_in_memory_sqlite(url: str) -> bool:
    """Whether ``url`` names an in-memory SQLite database.

    :param url: a SQLAlchemy URL.
    :returns: whether the backend is SQLite and the URL names no file.
        Measured with SQLAlchemy 2.1.1: ``sqlite://`` parses to a
        ``database`` of ``None`` and ``sqlite:///:memory:`` to the string
        ``":memory:"``, while ``sqlite:///drishti.db`` names its file.

    **Read off the parsed URL with the parser ``create_engine`` parses with**,
    on ``D37``'s reason that two spellings of a URL cannot be allowed to
    disagree about which database they name.
    """
    parsed = make_url(url)
    return parsed.get_backend_name() == "sqlite" and parsed.database in (
        None,
        "",
        ":memory:",
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """The session factory for ``engine``.

    :param engine: the engine every session opened from this factory is bound
        to, and the only engine any of them can reach.
    :returns: a :class:`~sqlalchemy.orm.sessionmaker` whose ``expire_on_commit``
        is ``False``, so an object written inside the caller's ``with`` block
        is still readable after it closes.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


#: The engine the service uses, built from the configured URL when this module
#: was first imported.
engine: Engine = build_engine()

#: The session factory the service uses, bound to :data:`engine` and to nothing
#: else.
SessionLocal: sessionmaker[Session] = build_session_factory(engine)
