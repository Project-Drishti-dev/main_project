"""11.11: ``/health`` is liveness, ``/ready`` is readiness, and they disagree.

The split is only worth anything if the two answers can differ, so most of
this file is about the state of the world the probes are asked in: a database
that cannot be opened, and a database that answers while its ledger table is
gone.  The first is the case the task names; the second is the one a probe
that only ran ``SELECT 1`` would pass.

Each fixture hands a session factory to the app and removes it afterwards, so
a probe here reads the database it was given and never the one ``DATABASE_URL``
named at import.  That is also what proves ``/ready`` reaches its database
through :func:`app.api.get_sessions`: a route that closed over the module-level
factory would read the default file instead and answer about that.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.api.rate_limit import RateLimiter
from app.main import app
from app.storage import db
from app.storage.models import Base, LEDGER_ENTRY_TABLE_NAME


@contextmanager
def _pointed_at(factory: sessionmaker[Session]) -> Iterator[None]:
    """Bind ``factory`` as the app's session dependency for one test."""
    app.dependency_overrides[get_sessions] = lambda: factory
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_sessions, None)


@pytest.fixture
def reachable() -> Iterator[AbstractContextManager[None]]:
    """One in-memory database with the migrated schema, bound into the app."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield _pointed_at(db.build_session_factory(engine))
    finally:
        engine.dispose()


@pytest.fixture
def no_ledger() -> Iterator[AbstractContextManager[None]]:
    """A database that answers, with the ledger table dropped out from under it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE {LEDGER_ENTRY_TABLE_NAME}"))
    try:
        yield _pointed_at(db.build_session_factory(engine))
    finally:
        engine.dispose()


@pytest.fixture
def unreachable(tmp_path) -> Iterator[AbstractContextManager[None]]:
    """A database that cannot be opened at all.

    The file sits in a directory that was never created, so SQLite refuses the
    connect rather than creating one -- the refusal a stopped, unmounted or
    misconfigured database gives, and the one the task's test needs.
    """
    engine = db.build_engine(f"sqlite:///{tmp_path / 'nowhere' / 'drishti.db'}")
    try:
        yield _pointed_at(db.build_session_factory(engine))
    finally:
        engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health_answers_while_the_database_is_unreachable(unreachable, client):
    """The split, stated as the one behaviour that makes it a split.

    Liveness asks whether the process answers, so an outage cannot make it
    stop answering: otherwise a supervisor restarts a process that is alive
    and well, and the outage lasts longer than it needed to.
    """
    with unreachable:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_answers_its_status_and_nothing_else(client):
    """One key, so a caller polling it parses one shape."""
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_reports_every_check_it_ran(reachable, client):
    """A 200 names what was verified, so it is not read as an assumption."""
    with reachable:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": ["database", "ledger"]}


def test_ready_fails_when_the_database_is_unreachable(unreachable, client):
    """The case the task names: no database, no readiness.

    The refusal is the one error envelope every endpoint answers in (``D74``)
    and it names the check that failed, so an operator reads which of the two
    broke without turning on a debugger.
    """
    with unreachable:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert "database" in response.json()["error"]["message"]


def test_ready_fails_when_the_ledger_cannot_be_read(no_ledger, client):
    """A database that answers and a ledger that does not is still not ready.

    A probe that ran one statement against no table would pass here, so this
    is the case that holds ``/ready`` to both checks rather than to the
    database alone.
    """
    with no_ledger:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert "ledger" in response.json()["error"]["message"]


def test_both_probes_spend_no_analysis_budget(reachable, client):
    """A supervisor polling under load is not refused by the analysis budget.

    ``conftest`` hands the shipped limiter back after every test, so the small
    one put in place here outlives neither this test nor its neighbours.
    """
    app.state.rate_limiter = RateLimiter(1)

    with reachable:
        assert client.post("/api/analyze").status_code == 422
        assert client.post("/api/analyze").status_code == 429
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/ready").status_code == 200