"""11.6: every line this service logs is one JSON object, timed and identified.

:mod:`app.logging_config` owns the format and
:mod:`app.api.request_logging` owns the one line per request, so this file
holds the format's guarantees rather than the middleware's: that a line
parses, that it names the id the answer carried, that it carries an elapsed
time, and that nothing a caller typed reaches it.  11.7 adds the content
ban -- no image bytes, no OCR text, no identity -- on top of these.
"""

import io
import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions, routes_screenings
from app.api.request_id import REQUEST_ID_HEADER
from app.api.request_logging import RequestLoggingMiddleware
from app.config import (
    DEFAULT_LOG_LEVEL,
    LOG_LEVEL_ENV_VAR,
    LOG_LEVELS,
    get_log_level,
)
from app.logging_config import (
    ALWAYS_PRESENT_FIELDS,
    APP_LOGGER_NAME,
    FIELDS_KEY,
    JsonFormatter,
    bind_request_id,
    configure_logging,
    current_request_id,
    log_event,
)
from app.main import app
from app.storage import db
from app.storage.models import Base


#: An id no row carries, so a read below reaches a refusal or a fault rather
#: than a stored screening.
MISSING = uuid.uuid4()

#: An id a caller may offer, adopted verbatim (11.5) and now logged.
OFFERED = "req-01HQ3K7M2N9P"


def _boom(*_args, **_kwargs):
    """Stand in for a fault no route caught."""
    raise RuntimeError("boom")


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
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def answering_client() -> Iterator[TestClient]:
    """A client that answers a crash with its 500 body instead of re-raising."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def logged() -> Iterator[Callable[[], list[dict]]]:
    """Drain every line the ``app`` logger has written, parsed as JSON."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
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


@pytest.fixture
def capturing() -> Iterator[io.StringIO]:
    """The raw text of the lines a body logged, for the not-parseable checks."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


def _requests(lines: list[dict]) -> list[dict]:
    """The per-request lines out of ``lines``, which is one per HTTP answer."""
    return [line for line in lines if line["message"] == "http_request"]


def _formatted(record: logging.LogRecord) -> dict:
    """:returns: ``record`` rendered the way the app's handler renders it."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.emit(record)
    return json.loads(stream.getvalue())


# --- the line parses ------------------------------------------------------


def test_a_log_line_parses_as_json(client, logged):
    """The task's own assertion: one line, one object, parsed and read."""
    client.get("/health")

    lines = logged()

    assert len(lines) == 1
    line = lines[0]
    assert isinstance(line, dict)
    assert line["message"] == "http_request"


def test_a_line_carries_the_five_keys_it_always_promises(client, logged):
    """A reader indexes these without a guard on each, so they are all there."""
    client.get("/health")

    line = logged()[0]

    assert set(ALWAYS_PRESENT_FIELDS) == {
        "timestamp",
        "level",
        "logger",
        "message",
        "request_id",
    }
    for key in ALWAYS_PRESENT_FIELDS:
        assert key in line, line


def test_the_timestamp_is_a_utc_iso_instant(client, logged):
    """Parsed back, so a reader can sort lines by the moment each one names."""
    client.get("/health")

    stamp = datetime.fromisoformat(_requests(logged())[0]["timestamp"])

    assert stamp.utcoffset() == timedelta(0)


def test_every_line_a_whole_flow_writes_parses_as_json(
    answering_client, logged, sessions, monkeypatch
):
    """A success, a refusal, a router miss and a crash -- one shape throughout."""
    monkeypatch.setattr(routes_screenings.ScreeningRepository, "get", _boom)

    answering_client.get("/health")
    answering_client.post("/api/screenings")
    answering_client.get("/api/nowhere")
    answering_client.get(f"/api/screenings/{MISSING}")

    lines = logged()

    assert all(isinstance(line, dict) for line in lines)
    assert sorted(line["message"] for line in lines) == [
        "http_request",
        "http_request",
        "http_request",
        "http_request",
        "unhandled_request_error",
    ]


def test_a_traceback_stays_on_the_one_line(answering_client, logged, sessions, monkeypatch):
    """A multi-line exception escaped by the encoder, or the line is lost."""
    monkeypatch.setattr(routes_screenings.ScreeningRepository, "get", _boom)

    answering_client.get(f"/api/screenings/{MISSING}")

    raw = [line for line in logged() if line["message"] == "unhandled_request_error"]

    assert len(raw) == 1
    assert "RuntimeError" in raw[0]["exception"]


def test_a_field_that_is_not_serialisable_does_not_break_the_line():
    """A handler that raises turns one bad field into a failed request."""
    record = logging.LogRecord("app.x", logging.INFO, "", 0, "an_event", (), None)
    setattr(record, FIELDS_KEY, {"when": object()})

    assert _formatted(record)["when"].startswith("<object object")


# --- the line names the request it belongs to -----------------------------


def test_the_line_carries_the_id_the_answer_carries(client, logged):
    """The whole point of an id: the header and the log are the same value."""
    response = client.get("/health", headers={REQUEST_ID_HEADER: OFFERED})

    assert logged()[0]["request_id"] == response.headers[REQUEST_ID_HEADER] == OFFERED


def test_two_requests_log_two_ids(client, logged):
    """So the id correlates rather than being a constant on every line."""
    client.get("/health")
    client.get("/health")

    first, second = _requests(logged())

    assert first["request_id"] != second["request_id"]


def test_a_refusal_is_timed_and_named_too(client, logged, sessions):
    """An envelope refusal is still an answer, and answers are logged."""
    response = client.post("/api/screenings")

    line = _requests(logged())[0]

    assert response.status_code == 422
    assert line["status"] == 422
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_a_crash_line_carries_the_id_the_crash_was_answered_with(
    answering_client, logged, sessions, monkeypatch
):
    """The fault handler and the request line agree on one id, not two."""
    monkeypatch.setattr(routes_screenings.ScreeningRepository, "get", _boom)

    response = answering_client.get(f"/api/screenings/{MISSING}")

    lines = logged()

    assert {line["request_id"] for line in lines} == {
        response.headers[REQUEST_ID_HEADER]
    }
    # The request line is written as the exception unwinds through the logging
    # middleware, so it comes first -- and it reports a 500, because no
    # ``http.response.start`` had been sent by the time it was written.
    assert [line["message"] for line in lines] == [
        "http_request",
        "unhandled_request_error",
    ]
    assert _requests(lines)[0]["status"] == 500


# --- the elapsed time -----------------------------------------------------


def test_the_line_carries_the_elapsed_time(client, logged):
    """11.6's second half: how long the request took, as a number."""
    client.get("/health")

    elapsed = _requests(logged())[0]["elapsed_ms"]

    assert isinstance(elapsed, float)
    assert elapsed >= 0.0


def test_the_elapsed_time_covers_the_request_not_only_the_response(logged):
    """A handler that takes its time shows up, so the field is not a constant."""
    probe = FastAPI()
    probe.add_middleware(RequestLoggingMiddleware)

    @probe.get("/slow")
    def slow() -> dict[str, bool]:
        time.sleep(0.05)
        return {"ok": True}

    TestClient(probe).get("/slow")

    line = _requests(logged())[0]

    assert line["elapsed_ms"] >= 50.0
    # Nothing stamped this request, and the middleware minted no id of its own.
    assert line["request_id"] is None


# --- what the line names, and what it must not ----------------------------


def test_a_line_names_the_handler_that_answered(client, logged, sessions):
    """Stable and chosen here, rather than a path the caller controls."""
    client.post("/api/screenings")

    handler = _requests(logged())[0]["handler"]

    assert handler == "app.api.routes_screenings.create_screening"


def test_a_router_miss_names_no_handler(client, logged):
    """Nothing matched, and the line says so rather than inventing one."""
    response = client.get("/api/nowhere")

    line = _requests(logged())[0]

    assert response.status_code == 404
    assert line["status"] == 404
    assert line["handler"] is None


def test_a_path_a_caller_typed_never_reaches_the_log(client, logged, sessions):
    """A path segment is caller text, and 11.5 refused reflecting that."""
    client.get("/api/screenings/not-a-uuid")

    assert "not-a-uuid" not in json.dumps(logged())


# --- the id is ambient -------------------------------------------------


def test_a_line_logged_inside_a_request_carries_its_id(capturing):
    """The binding, checked without an HTTP request in the way."""
    logger = logging.getLogger(APP_LOGGER_NAME)
    with bind_request_id(OFFERED):
        log_event(logger, "inside")
    log_event(logger, "outside")

    inside, outside = [
        json.loads(line) for line in capturing.getvalue().splitlines()
    ]

    assert inside["request_id"] == OFFERED
    assert outside["request_id"] is None


def test_the_binding_is_restored_when_the_block_ends():
    """A neighbouring request must not see this one's id."""
    with bind_request_id(OFFERED):
        assert current_request_id() == OFFERED
    with bind_request_id("second"):
        assert current_request_id() == "second"

    assert current_request_id() is None


def test_a_field_may_not_shadow_the_event_name():
    """``message`` is the event, so a field called that is dropped, not merged."""
    record = logging.LogRecord("app.x", logging.INFO, "", 0, "an_event", (), None)
    setattr(record, FIELDS_KEY, {"message": "something else"})

    assert _formatted(record)["message"] == "an_event"


# --- the handler is attached once ----------------------------------------


def test_configuring_the_log_twice_attaches_one_handler():
    """Idempotent, because ``app.main`` is imported by every session."""
    logger = logging.getLogger(APP_LOGGER_NAME)

    def configured() -> int:
        return sum(
            isinstance(handler.formatter, JsonFormatter)
            for handler in logger.handlers
        )

    before = configured()
    configure_logging()
    configure_logging()

    assert configured() == before


def test_the_configured_logger_does_not_propagate():
    """Otherwise uvicorn's own root handler renders the record a second time."""
    assert logging.getLogger(APP_LOGGER_NAME).propagate is False


# --- the level, read from the environment by app.config -------------------


def test_no_level_configured_is_the_default():
    assert get_log_level() == DEFAULT_LOG_LEVEL


@pytest.mark.parametrize("level", LOG_LEVELS)
def test_every_level_name_is_accepted(monkeypatch, level):
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, level)

    assert get_log_level() == level


def test_a_level_spelled_in_another_case_is_still_a_level(monkeypatch):
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, "  debug  ")

    assert get_log_level() == "DEBUG"


def test_a_blank_level_is_the_default(monkeypatch):
    """``.env.example`` ships it blank, and a blank value must still start."""
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, "   ")

    assert get_log_level() == DEFAULT_LOG_LEVEL


@pytest.mark.parametrize("configured", ("TRACE", "verbose", "10", "INFO;DEBUG"))
def test_a_level_that_is_not_one_is_refused_rather_than_ignored(monkeypatch, configured):
    """``Logger.setLevel`` answers an unknown name by doing nothing at all."""
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, configured)

    with pytest.raises(ValueError, match=LOG_LEVEL_ENV_VAR) as raised:
        get_log_level()

    assert configured in str(raised.value)