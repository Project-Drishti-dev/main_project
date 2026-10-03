"""11.7: no log line ever carries image bytes, an OCR string or an embedding.

Two halves, because either alone would prove very little.  The runtime half
drives the real flows -- an upload that succeeds, a document carrying a
machine-readable zone, a quality module that faults, a request that crashes
-- and asserts none of the three payloads appears in any line they write.
The source half walks ``backend/app`` with :mod:`ast`, so the next call site
that hands one in turns this suite red rather than waiting for a leak to be
found in production.  A payload is also logged on purpose, which is what
proves the runtime assertion has teeth: without it a checker that never
matched anything would pass every flow below.

``D76`` left no free-text slot in a line, so a payload can only arrive as a
*value* passed to :func:`~app.logging_config.log_event`.  That is the door
:data:`ALLOWED_FIELDS` keeps shut, and it is why this file polices field
names rather than message text.
"""

import ast
import io
import json
import logging
import struct
import zlib
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions, routes_screenings
from app.logging_config import APP_LOGGER_NAME, JsonFormatter, log_event
from app.main import app
from app.quality_checker import engine
from app.storage import db
from app.storage.models import Base
from tests.fixtures import mrz_images


#: A marker carried inside the uploaded bytes as a PNG text chunk, so the
#: ban below is checked against the bytes themselves rather than a stand-in.
IMAGE_BYTES_MARKER = "DRISHTI-IMAGE-BYTES-3f9a1c"

#: What a TD3 page really prints, and the two substrings of it worth banning
#: by name: the holder's name and the document number.
OCR_NAME = "ERIKSSON<<ANNA<MARIA"
OCR_DOCUMENT_NUMBER = "L898902C<3"

#: An embedding, and the value in it distinctive enough to search for.  No
#: model answers in this build, so nothing produces one yet -- the ban is
#: held now rather than when the first model lands.
EMBEDDING = [0.0314, -0.6112507, 0.9482]
EMBEDDING_MARKER = "-0.6112507"

#: What a caller may type that is theirs and nobody else's: the name on the
#: page, sent as the upload's filename and as the document-type claim.
CALLER_IDENTITY = "ANNA MARIA ERIKSSON"

#: The banned payloads, each named by what it is, so a failure reads as
#: which one leaked.  ``caller_identity`` is here for the same reason as the
#: OCR string: a caller's own text is the payload a request most easily
#: carries into a log.
BANNED = {
    "image_bytes": (IMAGE_BYTES_MARKER,),
    "ocr_text": (OCR_NAME, OCR_DOCUMENT_NUMBER),
    "caller_identity": (CALLER_IDENTITY,),
    "embedding": (EMBEDDING_MARKER,),
}

#: The fields a call site may hand to ``log_event``.  Each is vocabulary
#: this repository chose -- a method, the handler that answered, a status, a
#: duration, a module's name, a row's id -- and none of them is data a caller
#: supplied or a document carried.  Adding one is a decision to make here;
#: adding a payload is not, and this set is where the two differ.
ALLOWED_FIELDS = frozenset(
    {"elapsed_ms", "handler", "method", "module", "screening_id", "status"}
)

#: ``log_event``'s own two options, which are not fields -- they steer the
#: record rather than joining it.
CALL_OPTIONS = frozenset({"exc_info", "level"})

#: The logger methods this service must not call.  ``log_event`` is the only
#: way a module writes a line, so reaching for one of these directly is a
#: second, unpoliced door into the log.
LOGGER_METHODS = frozenset(
    {
        "critical",
        "debug",
        "error",
        "exception",
        "fatal",
        "info",
        "log",
        "warn",
        "warning",
    }
)

#: The module that owns ``log_event``, and the one module allowed to call a
#: logger method: the ``logger.log`` inside it is the write every other call
#: site routes through.
THE_WRITER = "logging_config.py"

#: Every module under ``app``, read as source rather than imported.
APP_SOURCES = sorted((Path(__file__).resolve().parents[2] / "app").rglob("*.py"))

#: A page with a real machine-readable zone on it, so Tier 0 reads genuine
#: OCR text off it -- a name and a document number this service really parses.
PAGE = mrz_images.render_format("TD3")


def marked_png(image: np.ndarray, marker: str) -> bytes:
    """``image`` as PNG bytes whose raw bytes carry ``marker`` verbatim.

    A chunk spliced into a real encoding rather than a re-save, because what
    is under test is the bytes as they arrive.  ``tEXt`` is ancillary, so
    every decoder skips it and the marker is still there in what the service
    was handed.
    """

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    encoded, data = cv2.imencode(".png", image)
    assert encoded
    raw = data.tobytes()
    at = raw.rindex(b"IEND") - 4  # the length field ahead of the final chunk
    text = chunk(b"tEXt", b"Comment\x00" + marker.encode("ascii"))
    return raw[:at] + text + raw[at:]


def _carries(line: str) -> list[str]:
    """:returns: the names of the banned payloads ``line`` carries."""
    return [
        name for name, markers in BANNED.items() if any(m in line for m in markers)
    ]


def _carried_by(lines: list[dict]) -> list[str]:
    """:returns: every banned payload any of ``lines`` carries."""
    return [name for line in lines for name in _carries(json.dumps(line))]


def _tree(path: Path) -> ast.Module:
    """:returns: ``path`` parsed, so its logging calls can be read not run."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _nodes(path: Path, wanted: type) -> Iterator[ast.AST]:
    """:returns: every node of ``wanted`` kind in ``path``."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, wanted):
            yield node


def _log_event_calls(path: Path) -> Iterator[ast.Call]:
    """:returns: every ``log_event(...)`` call in ``path``."""
    for node in _nodes(path, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "log_event":
            yield node


def _logger_method_calls(path: Path) -> Iterator[ast.Call]:
    """:returns: every direct logger method call in ``path``, whatever holds it."""
    for node in _nodes(path, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in LOGGER_METHODS:
            yield node


def _string_constants(path: Path) -> set[str]:
    """:returns: the names ``path`` binds at module level to a string."""
    names = set()
    for node in _tree(path).body:
        if not (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        names.update(
            child.id for target in targets for child in ast.walk(target)
            if isinstance(child, ast.Name)
        )
    return names


def _names_an_event(call: ast.Call, constants: set[str]) -> bool:
    """:returns: whether ``call``'s message is a string constant.

    A literal, or the name of a module-level string constant -- how
    ``app.api.request_logging`` spells the one event it writes.
    """
    if len(call.args) < 2:
        return False
    message = call.args[1]
    if isinstance(message, ast.Constant):
        return isinstance(message.value, str)
    return isinstance(message, ast.Name) and message.id in constants


def _field_offenders(call: ast.Call) -> list[str]:
    """:returns: why ``call`` passes a field outside :data:`ALLOWED_FIELDS`."""
    reasons = []
    if any(isinstance(node, ast.Starred) for node in call.keywords):
        reasons.append("a ** splat, whose names nothing here has seen")
    for keyword in call.keywords:
        if keyword.arg is not None and keyword.arg not in ALLOWED_FIELDS | CALL_OPTIONS:
            reasons.append(f"{keyword.arg!r}")
    return reasons


def _boom(*_args, **_kwargs):
    """Stand in for a fault that a caller somewhere did not catch."""
    raise RuntimeError("boom")


def _upload(marker: str) -> dict:
    """The shared upload shape, carrying every payload this file bans."""
    return {
        "image": (
            f"{CALLER_IDENTITY}.png",
            marked_png(PAGE.image, marker),
            "image/png",
        )
    }


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema, and a factory over it."""
    database = db.build_engine("sqlite://")
    Base.metadata.create_all(database)
    try:
        factory = db.build_session_factory(database)
        app.dependency_overrides[get_sessions] = lambda: factory
        yield factory
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        database.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def answering_client() -> Iterator[TestClient]:
    """A client that answers a crash with its 500 body instead of re-raising."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _capture(stream: io.StringIO) -> logging.Handler:
    """``stream`` wired to the ``app`` logger, formatted as a line is."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logging.getLogger(APP_LOGGER_NAME).addHandler(handler)
    return handler


@pytest.fixture
def logged() -> Iterator[Iterator[list[dict]]]:
    """Every line the ``app`` logger writes, parsed as JSON."""
    stream = io.StringIO()
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    handler = _capture(stream)
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
    """The raw text of every line written, for the check on the line itself."""
    stream = io.StringIO()
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    handler = _capture(stream)
    logger.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


# --- the ban has teeth ----------------------------------------------------


def test_the_ban_catches_a_payload_deliberately_handed_in(capturing):
    """The mutation the ban exists for.

    Without this, every assertion below would pass against a checker that
    never matches anything -- the classic way a leak test earns its green.
    """
    log_event(
        logging.getLogger(APP_LOGGER_NAME),
        "a_payload_someone_handed_in",
        image_bytes=_upload(IMAGE_BYTES_MARKER)["image"][1],
        ocr_text=OCR_NAME,
        caller_name=CALLER_IDENTITY,
        embedding=EMBEDDING,
    )

    assert _carries(capturing.getvalue()) == [
        "image_bytes",
        "ocr_text",
        "caller_identity",
        "embedding",
    ]


# --- the real flows, which carry none of them -----------------------------


def test_an_upload_that_succeeded_carries_none_of_its_bytes(client, logged):
    """The bytes were decoded, measured and answered, and none of it was logged."""
    response = client.post("/api/analyze", files=_upload(IMAGE_BYTES_MARKER))

    lines = logged()

    assert response.status_code == 200
    # Named, so an empty capture cannot pass this as a clean bill of health.
    assert [line["message"] for line in lines] == ["http_request"]
    assert _carried_by(lines) == []


def test_a_screened_document_carries_none_of_its_ocr(client, logged, sessions):
    """A TD3 page read end to end: the zone is parsed and none of it is logged.

    The caller's own name rides in twice -- as the filename and as the
    document-type claim -- and ``run_screening`` stores both on the row
    without carrying either into an event.  The log is the third place they
    must not reach.
    """
    response = client.post(
        "/api/screenings",
        files=_upload(IMAGE_BYTES_MARKER),
        data={"document_type": CALLER_IDENTITY},
    )

    lines = logged()

    assert response.status_code == 200
    assert [line["message"] for line in lines] == ["http_request"]
    assert _carried_by(lines) == []


def test_a_quality_module_that_faulted_carries_none_of_the_frame(
    client, logged, monkeypatch
):
    """The fault line is written with its traceback, and the frame is not in it."""
    monkeypatch.setattr(engine.m1_sharpness, "assess", _boom, raising=True)

    response = client.post("/api/analyze", files=_upload(IMAGE_BYTES_MARKER))

    lines = logged()
    faulted = [
        line for line in lines if line["message"] == "quality_check_module_failed"
    ]

    assert response.status_code == 200
    assert len(faulted) == 1
    # Named, and carrying the traceback, so an empty capture cannot pass this
    # as a clean bill of health.
    assert "RuntimeError" in faulted[0]["exception"]
    assert _carried_by(lines) == []


def test_a_crashed_request_carries_none_of_the_request(
    answering_client, logged, sessions, monkeypatch
):
    """A fault no route caught, logged with its traceback, names no payload."""
    monkeypatch.setattr(routes_screenings.ScreeningRepository, "get", _boom)

    response = answering_client.get(
        "/api/screenings/6f1b1f2c-0000-4000-8000-000000000000"
    )

    lines = logged()

    assert response.status_code == 500
    assert sorted(line["message"] for line in lines) == [
        "http_request",
        "unhandled_request_error",
    ]
    assert _carried_by(lines) == []


# --- the source, so the next call site cannot open the door ---------------


def test_log_event_is_the_only_way_a_module_logs():
    """No ``logger.info``, no ``logger.exception``, no second spelling at all."""
    offenders = [
        f"{path.name}:{node.lineno} calls {node.func.attr}() directly"
        for path in APP_SOURCES
        if path.name != THE_WRITER
        for node in _logger_method_calls(path)
    ]

    assert offenders == []


def test_every_event_is_named_by_a_constant():
    """The message is the event name, so it is a constant and not prose.

    A call that built its message would be reintroducing the free-text slot
    ``D76`` removed, which is where a payload would enter.
    """
    offenders = [
        f"{path.name}:{call.lineno} names no constant event"
        for path in APP_SOURCES
        for call in _log_event_calls(path)
        if not _names_an_event(call, _string_constants(path))
    ]

    assert offenders == []


def test_no_call_site_hands_in_a_field_outside_the_allowed_set():
    """The door itself: a payload arrives as a value, so the values are policed.

    A ``**fields`` splat is refused for the same reason it is dangerous at run
    time -- it would smuggle in a name this set has never seen.
    """
    offenders = [
        f"{path.name}:{call.lineno} passes {reason}"
        for path in APP_SOURCES
        for call in _log_event_calls(path)
        for reason in _field_offenders(call)
    ]

    assert offenders == []


def test_every_allowed_field_is_one_a_call_site_really_passes():
    """The set cannot quietly grow: an unused name is a hole waiting to be used."""
    passed = {
        keyword.arg
        for path in APP_SOURCES
        for call in _log_event_calls(path)
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert ALLOWED_FIELDS <= passed