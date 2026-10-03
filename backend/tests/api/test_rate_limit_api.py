"""11.8: one budget per address on the endpoints that analyse an image.

The task's own verify is the N+1th request in a window -- the first N are
answered, and the one after is refused in the envelope :mod:`app.main`
already builds (``D74``).  Around it sit the properties that give that N a
meaning: another address has a budget of its own, the budget returns when the
window rolls, a request that was going to be refused anyway still spends it,
and neither the refusal nor the log says which address was over.

Every limit below is written to ``app.state.rate_limiter`` rather than to the
guard, so the guard under test is the one the service runs, and the clock
under it is a test's -- so "in a window" is a fact about the code rather than
a wait.
"""

import contextlib
import inspect
import io
import json
import logging
import re
import uuid
from collections.abc import Iterator

import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app import main as api
from app.api import get_sessions, routes_screenings
from app.api.rate_limit import (
    RATE_LIMIT_CODE,
    WINDOW_SECONDS,
    RateLimiter,
    enforce_analysis_rate_limit,
)
from app.api.request_id import REQUEST_ID_HEADER
from app.logging_config import APP_LOGGER_NAME, JsonFormatter
from app.main import app
from app.storage import db
from app.storage.models import Base
from tests.fixtures import mrz_images


#: The limit these tests run at -- small enough to count by hand.
N = 3

#: Two addresses from the documentation range, so neither can be a real
#: caller.  They are spelled out because one of the assertions is that
#: neither of them reaches the answer or the log.
AN_ADDRESS = "198.51.100.7"
ANOTHER_ADDRESS = "198.51.100.8"

#: A code is the vocabulary a client branches on, so its spelling is held.
CODE = re.compile(r"[A-Z][A-Z0-9_]*")

#: An id no row carries, so the read below reaches a 404 rather than a page.
MISSING = uuid.uuid4()

#: A page with a real machine-readable zone on it, so the analyses that are
#: answered are real ones rather than a stand-in for one.
PAGE = mrz_images.render_format("TD3")


def _page_png() -> bytes:
    encoded, data = cv2.imencode(".png", PAGE.image)
    assert encoded
    return data.tobytes()


A_PNG = _page_png()
UPLOAD = {"image": ("page.png", A_PNG, "image/png")}

#: A request with no body is refused by the route for its own sake.  It is
#: the cheap shape the tests below use where the counter is the point: it
#: spends the budget the same way an analysis does, and costs nothing to
#: make.


class Clock:
    """A clock a test moves by hand, so a window rolls without a wait."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _at(clock: Clock, limit: int = N) -> RateLimiter:
    """Put a limiter reading ``clock`` in the app, holding the next budget."""
    limiter = RateLimiter(limit, clock=clock)
    app.state.rate_limiter = limiter
    return limiter


@contextlib.contextmanager
def _caller(address: str) -> Iterator[TestClient]:
    """A client whose requests arrive from ``address``."""
    with TestClient(app, client=(address, 50000)) as client:
        yield client


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema, and a factory over it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        factory = db.build_session_factory(engine)
        app.dependency_overrides[get_sessions] = lambda: factory
        yield factory
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        engine.dispose()


@pytest.fixture
def logged() -> Iterator[Iterator[list[dict]]]:
    """Every line the ``app`` logger writes, parsed as JSON."""
    stream = io.StringIO()
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield lambda: [
            json.loads(line)
            for line in stream.getvalue().splitlines()
            if line.strip()
        ]
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


# --- the N+1th request, which is the task ----------------------------------


def test_the_n_plus_first_request_in_a_window_is_the_standard_envelope():
    """11.8's own verify: N analyses are answered, and the next is refused.

    The body is the one ``app.main`` builds for every refusal, reached
    through the real app rather than by calling the guard directly, and
    stamped with a request id like every other answer (``D75``).
    """
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        answered = [client.post("/api/analyze", files=UPLOAD) for _ in range(N)]
        refused = client.post("/api/analyze", files=UPLOAD)

    assert [response.status_code for response in answered] == [200] * N
    assert refused.status_code == 429, refused.text
    assert refused.headers["content-type"].startswith("application/json")
    assert refused.headers[REQUEST_ID_HEADER]
    body = refused.json()
    assert set(body) == {"error"}, body
    detail = body["error"]
    assert set(detail) == {"code", "message"}, detail
    assert detail["code"] == RATE_LIMIT_CODE
    assert CODE.fullmatch(detail["code"]), detail["code"]
    assert detail["message"].strip(), detail


def test_one_request_past_the_budget_is_still_answered():
    """The refusal above lands on the N+1th request and on no other.

    Without this it would pass against a limiter that refuses everything --
    the classic way a rate limit test earns its green.
    """
    _at(Clock(), limit=N + 1)

    with _caller(AN_ADDRESS) as client:
        statuses = [
            client.post("/api/analyze", files=UPLOAD).status_code
            for _ in range(N + 1)
        ]

    assert statuses == [200] * (N + 1)


def test_a_refused_request_never_reaches_the_analysis(monkeypatch):
    """The guard is ahead of the route, so a refusal costs nothing."""
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        for _ in range(N):
            assert client.post("/api/analyze").status_code == 422

        def fail(*_args, **_kwargs):
            raise AssertionError("the route ran after the budget was spent")

        monkeypatch.setattr(api, "analyze_uploaded_image", fail)

        assert client.post("/api/analyze", files=UPLOAD).status_code == 429


# --- what "per address", and "in a window", have to mean -------------------


def test_another_address_has_a_budget_of_its_own():
    _at(Clock())

    with _caller(AN_ADDRESS) as mine, _caller(ANOTHER_ADDRESS) as theirs:
        for _ in range(N):
            assert mine.post("/api/analyze").status_code == 422
        assert mine.post("/api/analyze").status_code == 429
        assert theirs.post("/api/analyze").status_code == 422


def test_the_budget_returns_when_the_window_rolls():
    clock = Clock()
    _at(clock)

    with _caller(AN_ADDRESS) as client:
        for _ in range(N):
            assert client.post("/api/analyze").status_code == 422
        assert client.post("/api/analyze").status_code == 429

        clock.advance(WINDOW_SECONDS)

        assert client.post("/api/analyze", files=UPLOAD).status_code == 200


def test_a_forwarded_address_does_not_buy_a_fresh_budget():
    """``X-Forwarded-For`` is the caller's own text, so it is never the key.

    Keyed on the header, the limit would be no limit at all: a caller that
    invented an address per request would never be refused.
    """
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        statuses = [
            client.post(
                "/api/analyze",
                headers={"X-Forwarded-For": f"203.0.113.{offered}"},
            ).status_code
            for offered in range(N)
        ]
        refused = client.post(
            "/api/analyze", files=UPLOAD, headers={"X-Forwarded-For": "203.0.113.99"}
        )

    assert statuses == [422] * N
    assert refused.status_code == 429


# --- which endpoints spend it ---------------------------------------------


def test_both_analysis_endpoints_spend_one_budget():
    """One budget on analysis, not one per route.

    A budget per route would be a budget of twice the size for any caller
    who alternated between the two, which is exactly the shape a scripted
    caller sends.
    """
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        assert client.post("/api/analyze").status_code == 422
        assert client.post("/api/screenings").status_code == 422
        assert client.post("/api/screenings").status_code == 422
        exhausted = client.post("/api/analyze")

    assert exhausted.status_code == 429


def test_the_reads_spend_no_budget(sessions):
    """11.8 limits what an image costs, not what reading a row costs."""
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        for _ in range(N + 1):
            assert client.post("/api/analyze").status_code in (422, 429)
        for path in ("/health", "/api/screenings", f"/api/screenings/{MISSING}"):
            assert client.get(path).status_code != 429, path


def test_a_request_refused_for_its_own_sake_still_spends_the_budget():
    """The guard is ahead of the route, so a bad upload is not free either."""
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        statuses = [
            client.post("/api/analyze").status_code for _ in range(N)
        ]
        refused = client.post("/api/analyze", files=UPLOAD)

    assert statuses == [422] * N
    assert refused.status_code == 429


# --- what the refusal and the line are allowed to say ----------------------


def test_the_address_reaches_neither_the_refusal_nor_the_log(logged):
    """The first thing keyed on something a caller controls (``D78``).

    A rejected request is exactly where a peer address would otherwise be
    echoed back, so the counter is the only place it is ever read.
    """
    _at(Clock())

    with _caller(AN_ADDRESS) as client:
        for _ in range(N + 1):
            response = client.post("/api/analyze")

    lines = logged()

    assert response.status_code == 429
    assert AN_ADDRESS not in response.text
    # The existing one line per request, and no second event for the refusal.
    assert [line["message"] for line in lines] == ["http_request"] * (N + 1)
    assert lines[-1]["status"] == 429
    assert AN_ADDRESS not in json.dumps(lines)


def test_the_guard_and_both_analysis_routes_run_on_the_event_loop():
    """What lets the counter hold no lock (``RateLimiter``'s invariant)."""
    assert inspect.iscoroutinefunction(enforce_analysis_rate_limit)
    for handler in (api.analyze, routes_screenings.create_screening):
        assert inspect.iscoroutinefunction(handler), handler.__name__


# --- the contract the endpoints declare ------------------------------------


def test_both_analysis_endpoints_declare_the_refusal_they_answer():
    """The document says the same thing the body does, or says nothing."""
    schema = app.openapi()

    for path in ("/api/analyze", "/api/screenings"):
        responses = schema["paths"][path]["post"]["responses"]
        model = responses["429"]["content"]["application/json"]["schema"]["$ref"]
        assert model == "#/components/schemas/ErrorResponse", path
