"""11.4: every new endpoint answers a refusal in the one existing envelope.

``app.main`` holds one body -- ``{"error": {"code", "message"}}`` -- and this
file holds every refusal 11.1 to 11.3 can answer to it, plus the 404 the task
names and the faults none of the three routes catch.  A second spelling on a
new endpoint fails here rather than reaching a client that parses one shape.
"""

import re
import struct
import uuid
import zlib
from collections.abc import Iterator

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.analysis import MAX_UPLOAD_BYTES
from app.api import get_sessions, routes_screenings
from app.main import app
from app.risk.weightsets.loader import WeightsetError
from app.storage import db
from app.storage.models import Base
from app.storage.repository import ScreeningRepository


#: A code is the vocabulary a client branches on, so its spelling is held.
CODE = re.compile(r"[A-Z][A-Z0-9_]*")

#: An id no row carries, so the reads below reach a refusal and not a page.
MISSING = uuid.uuid4()

#: The three endpoints 11.1 to 11.3 added.
THE_NEW_ENDPOINTS = (
    "POST /api/screenings",
    "GET /api/screenings",
    "GET /api/screenings/{screening_id}",
)


def _png_header(width: int, height: int) -> bytes:
    """A PNG whose header claims ``width`` by ``height`` and carries no pixels."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", b"")
        + chunk(b"IEND", b"")
    )


def _png_bytes() -> bytes:
    """The smallest real PNG, for the refusal that needs decodable bytes."""
    encoded, data = cv2.imencode(".png", np.zeros((8, 8, 3), dtype=np.uint8))
    assert encoded
    return data.tobytes()


A_PNG = _png_bytes()


#: One row per refusal: endpoint, method, path, what is sent, status, code.
#: Every body is the smallest that reaches its refusal, and every one is
#: answered through the real app rather than by calling a handler directly.
THE_REFUSALS = (
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        None,
        422,
        "IMAGE_REQUIRED",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {
            "files": {"image": ("page.png", b"", "image/png")},
            "data": {"document_type": "  "},
        },
        422,
        "INVALID_DOCUMENT_TYPE",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {
            "files": {"image": ("page.png", A_PNG, "image/png")},
            "data": {"mode": "guess"},
        },
        422,
        "INVALID_MODE",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {"files": {"image": ("broken.png", b"not a real png", "image/png")}},
        422,
        "INVALID_IMAGE",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {"files": {"image": ("large.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")}},
        413,
        "IMAGE_TOO_LARGE",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {"files": {"image": ("huge.png", _png_header(5000, 5000), "image/png")}},
        413,
        "IMAGE_DIMENSIONS_TOO_LARGE",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {"files": {"image": ("notes.txt", b"not an image", "text/plain")}},
        415,
        "UNSUPPORTED_MEDIA_TYPE",
    ),
    (
        "POST /api/screenings",
        "post",
        "/api/screenings",
        {"files": {"image": ("page.jpg", A_PNG, "image/jpeg")}},
        415,
        "MEDIA_TYPE_MISMATCH",
    ),
    (
        "GET /api/screenings",
        "get",
        "/api/screenings?created_after=2026-03-01T01:00:00",
        None,
        422,
        "INVALID_DATE_RANGE",
    ),
    (
        "GET /api/screenings",
        "get",
        "/api/screenings"
        "?created_after=2026-03-01T04:00:00Z&created_before=2026-03-01T01:00:00Z",
        None,
        422,
        "INVALID_DATE_RANGE",
    ),
    (
        "GET /api/screenings",
        "get",
        "/api/screenings?limit=0",
        None,
        422,
        "INVALID_REQUEST",
    ),
    (
        "GET /api/screenings/{screening_id}",
        "get",
        f"/api/screenings/{MISSING}",
        None,
        404,
        "SCREENING_NOT_FOUND",
    ),
    (
        "GET /api/screenings/{screening_id}",
        "get",
        "/api/screenings/not-a-uuid",
        None,
        422,
        "INVALID_REQUEST",
    ),
)


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


def _assert_envelope(response, status_code: int, code: str) -> dict:
    """Assert the body every refusal is answered in, and hand it back.

    :returns: the ``error`` object, so a caller can read the message it
        checked alongside the shape.
    """
    assert response.status_code == status_code, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {"error"}, body
    detail = body["error"]
    assert set(detail) == {"code", "message"}, detail
    assert detail["code"] == code
    assert CODE.fullmatch(detail["code"]), detail["code"]
    assert detail["message"].strip(), detail
    return detail


# --- one shape, on every refusal the new endpoints answer ------------------


@pytest.mark.parametrize(
    ("endpoint", "method", "path", "sent", "status_code", "code"),
    THE_REFUSALS,
    ids=[f"{case[0]} {case[-1]}" for case in THE_REFUSALS],
)
def test_a_refusal_is_the_shared_envelope_and_nothing_else(
    client,
    sessions,
    endpoint,
    method,
    path,
    sent,
    status_code,
    code,
):
    """11.4's claim: one body, on every refusal, and nothing beside it."""
    response = getattr(client, method)(path, **(sent or {}))

    _assert_envelope(response, status_code, code)


def test_every_new_endpoint_is_refused_here_or_it_is_unchecked():
    """A fourth endpoint has no row here until someone writes one."""
    assert {case[0] for case in THE_REFUSALS} == set(THE_NEW_ENDPOINTS)


# --- the 404, in the shape the existing endpoint already uses --------------


def test_a_404_body_matches_the_envelope_the_existing_endpoint_uses(
    client, sessions
):
    """11.4's own verify: 404 in the shape ``/api/analyze`` already answers."""
    established = client.post("/api/analyze")

    missing = client.get(f"/api/screenings/{MISSING}")
    detail = _assert_envelope(missing, 404, "SCREENING_NOT_FOUND")

    assert established.status_code == 422
    assert set(established.json()) == set(missing.json()) == {"error"}
    assert set(established.json()["error"]) == set(missing.json()["error"]) == {
        "code",
        "message",
    }
    assert detail["message"] != established.json()["error"]["message"]


# --- the faults, which name no fault ---------------------------------------


def test_a_fault_in_the_cascade_is_a_generic_envelope(client, sessions, monkeypatch):
    """11.1's catch-all, in the one shape every other refusal is answered in."""

    def fail_cascade(**_kwargs):
        raise RuntimeError("internal implementation detail")

    monkeypatch.setattr(routes_screenings, "run_screening", fail_cascade)
    response = client.post(
        "/api/screenings",
        files={"image": ("page.png", A_PNG, "image/png")},
    )

    _assert_envelope(response, 500, "SCREENING_FAILED")
    assert "internal implementation detail" not in response.text


def test_a_result_that_cannot_be_rebuilt_is_a_generic_envelope(
    client, sessions, monkeypatch
):
    """11.2's catch-all, on the read that answers a whole stored screening."""
    created = ScreeningRepository(sessions).create(
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        image_width=320,
        image_height=90,
    )

    def fail_weightset(*_args, **_kwargs):
        raise WeightsetError("a ruleset this deployment does not ship")

    monkeypatch.setattr(routes_screenings, "load_weightset", fail_weightset)
    response = client.get(f"/api/screenings/{created.id}")

    _assert_envelope(response, 500, "SCREENING_UNREADABLE")
    assert "a ruleset this deployment does not ship" not in response.text


def test_a_fault_no_route_catches_is_the_envelope_not_a_crash_page(
    answering_client, sessions, monkeypatch
):
    """The reads carry no catch-all, so the app answers on their behalf."""

    def fail_read(_self, _screening_id):
        raise RuntimeError("internal implementation detail")

    monkeypatch.setattr(
        routes_screenings.ScreeningRepository, "get", fail_read
    )
    response = answering_client.get(f"/api/screenings/{MISSING}")

    _assert_envelope(response, 500, "INTERNAL_ERROR")
    assert "internal implementation detail" not in response.text


# --- the contract the routes declare --------------------------------------


def test_every_failure_the_new_endpoints_declare_is_the_envelope_model():
    """The document says the same thing the body does, or says nothing."""
    schema = app.openapi()

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if not path.startswith("/api/screenings"):
                continue
            for status, response in operation["responses"].items():
                if status.startswith("2"):
                    continue
                model = response["content"]["application/json"]["schema"]["$ref"]
                assert model == "#/components/schemas/ErrorResponse", (
                    f"{method.upper()} {path} {status} declares {model}"
                )

    detail = schema["components"]["schemas"]["ErrorDetail"]
    assert set(detail["properties"]) == {"code", "message"}
    assert set(detail["required"]) == {"code", "message"}


def test_no_second_error_schema_is_declared_anywhere_in_the_contract():
    """FastAPI's own validation model would be a second spelling of a 422."""
    schemas = app.openapi()["components"]["schemas"]

    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert {name for name in schemas if "Error" in name} == {
        "ErrorDetail",
        "ErrorResponse",
    }
