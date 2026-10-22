"""11.1: ``POST /api/screenings`` over HTTP, and the two ids it answers.

The endpoint is reached through the real app with the real flow behind it and
one temporary database under it, so what is asserted is the shape a client
sees rather than a route's return value: both ids are UUIDs, both name rows
that exist, the audit id names the one ``analysis_completed`` event beside the
screening, and nothing about the upload reaches the response.  The refusals
asserted here are the ones a caller meets before any row is written.
"""

import uuid
from collections.abc import Iterator
import struct
import zlib

import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.analysis import MAX_UPLOAD_BYTES
from app.api import get_sessions
from app.api import routes_screenings
from app.audit.event_types import ANALYSIS_COMPLETED
from app.main import app
from app.storage import db
from app.storage.models import AuditEvent, Base, Screening
from tests.fixtures import mrz_images


def png_bytes(image) -> bytes:
    """``image`` encoded as the PNG bytes an upload would carry."""
    encoded, data = cv2.imencode(".png", image)
    assert encoded
    return data.tobytes()


#: A page with no machine-readable zone on it: Tier 0 measures it, finds
#: nothing to flag, and the cascade completes -- the shortest path from an
#: upload to a completed row.
BLANK = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema, and a factory over it.

    Bound into the app as the session dependency, so the route writes here
    rather than into the file ``DATABASE_URL`` named at import.
    """
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


def upload(data: dict | None = None) -> dict:
    """A multipart body carrying the shared upload shape."""
    return {
        "files": {"image": ("page.png", png_bytes(BLANK.image), "image/png")},
        "data": data or {},
    }


def png_header(width: int, height: int) -> bytes:
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


# --- the two ids ---------------------------------------------------------


def test_a_screening_answers_with_both_ids(client, sessions):
    response = client.post("/api/screenings", **upload())

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"screening_id", "audit_id"}
    assert uuid.UUID(body["screening_id"])
    assert uuid.UUID(body["audit_id"])


def test_both_ids_name_rows_that_exist(client, sessions):
    body = client.post("/api/screenings", **upload()).json()

    with sessions() as session:
        row = session.execute(
            select(Screening).where(Screening.id == uuid.UUID(body["screening_id"]))
        ).scalar_one()
        event = session.execute(
            select(AuditEvent).where(AuditEvent.id == uuid.UUID(body["audit_id"]))
        ).scalar_one()

    assert event.screening_id == row.id
    assert event.event_type == ANALYSIS_COMPLETED
    assert row.status == "completed"


def test_the_answered_ids_are_usable_addresses_of_the_screening(client, sessions):
    """The audit id is a row of this screening's trail and not a counter."""
    body = client.post("/api/screenings", **upload()).json()

    with sessions() as session:
        events = session.execute(
            select(AuditEvent).where(
                AuditEvent.screening_id == uuid.UUID(body["screening_id"])
            )
        ).scalars().all()

    assert uuid.UUID(body["audit_id"]) in {event.id for event in events}


def test_two_uploads_answer_with_two_trails(client, sessions):
    first = client.post("/api/screenings", **upload()).json()
    second = client.post("/api/screenings", **upload()).json()

    assert first["screening_id"] != second["screening_id"]
    assert first["audit_id"] != second["audit_id"]


# --- the upload the caller sent -----------------------------------------


def test_the_claim_and_the_name_are_stored_on_the_row(client, sessions):
    body = client.post(
        "/api/screenings",
        **upload({"document_type": "passport", "mode": "scan"}),
    ).json()

    with sessions() as session:
        row = session.execute(
            select(Screening).where(Screening.id == uuid.UUID(body["screening_id"]))
        ).scalar_one()

    assert row.document_type == "passport"
    assert row.filename == "page.png"
    assert (row.image_width, row.image_height) == (320, 90)


def test_a_claim_the_caller_never_made_is_spelled_as_its_absence(client, sessions):
    body = client.post("/api/screenings", **upload()).json()

    with sessions() as session:
        row = session.execute(
            select(Screening).where(Screening.id == uuid.UUID(body["screening_id"]))
        ).scalar_one()

    assert row.document_type == routes_screenings.DEFAULT_DOCUMENT_TYPE


def test_nothing_about_the_upload_reaches_the_answer(client, sessions):
    response = client.post("/api/screenings", **upload())

    assert "page.png" not in response.text
    assert "image" not in response.json()


def test_the_capture_claim_is_not_stored_as_the_gates_reading(client, sessions):
    """``mode`` is the quality gate's column, and 14.3 is what fills it."""
    body = client.post(
        "/api/screenings", **upload({"mode": "scan"})
    ).json()

    with sessions() as session:
        row = session.execute(
            select(Screening).where(Screening.id == uuid.UUID(body["screening_id"]))
        ).scalar_one()

    assert row.mode is None


# --- what is refused before a row is written -----------------------------


def test_a_request_without_an_image_is_refused(client, sessions):
    response = client.post("/api/screenings")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IMAGE_REQUIRED"
    assert _screenings(sessions) == 0


def test_a_blank_document_type_is_refused(client, sessions):
    response = client.post("/api/screenings", **upload({"document_type": "  "}))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DOCUMENT_TYPE"
    assert _screenings(sessions) == 0


def test_an_unknown_capture_claim_is_refused_with_the_shared_code(client, sessions):
    """The same vocabulary ``/api/analyze`` answers with, and no second one."""
    response = client.post("/api/screenings", **upload({"mode": "guess"}))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_MODE"
    assert _screenings(sessions) == 0


def test_an_undecodable_upload_is_refused_with_the_shared_code(client, sessions):
    response = client.post(
        "/api/screenings",
        files={"image": ("broken.png", b"not a real png", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert _screenings(sessions) == 0


def test_a_file_over_the_upload_limit_is_refused_with_the_shared_code(client, sessions):
    response = client.post(
        "/api/screenings",
        files={
            "image": ("large.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"
    assert _screenings(sessions) == 0


def test_an_image_over_the_pixel_cap_is_refused_with_the_shared_code(client, sessions):
    response = client.post(
        "/api/screenings",
        files={"image": ("huge.png", png_header(5000, 5000), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"
    assert _screenings(sessions) == 0


def test_a_fault_in_the_cascade_answers_a_generic_500(client, sessions, monkeypatch):
    def fail_cascade(**_kwargs):
        raise RuntimeError("internal implementation detail")

    monkeypatch.setattr(routes_screenings, "run_screening", fail_cascade)
    response = client.post("/api/screenings", **upload())

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "SCREENING_FAILED",
            "message": "The document could not be screened. Please try again.",
        }
    }
    assert "internal implementation detail" not in response.text


# --- the route is a route, and nothing else ------------------------------


def test_the_endpoint_declares_no_security_requirement():
    """No authentication: the contract asks for no credential and names none."""
    schema = app.openapi()

    assert "security" not in schema["paths"]["/api/screenings"]["post"]
    assert schema.get("components", {}).get("securitySchemes") is None


def test_both_endpoints_take_the_same_multipart_fields():
    """``image`` and ``mode`` are spelled once, so both accept the same body."""
    analyze = _multipart_fields("/api/analyze")
    screening = _multipart_fields("/api/screenings")

    for field in ("image", "mode"):
        assert screening[field] == analyze[field]


def test_the_claim_the_row_needs_is_the_only_field_the_shared_shape_lacks():
    screening = _multipart_fields("/api/screenings")
    analyze = _multipart_fields("/api/analyze")

    assert set(analyze) == {"image", "mode"}
    assert set(screening) - {"image", "mode"} == {"document_type"}


def _multipart_fields(path: str) -> dict:
    """The multipart body one endpoint accepts, as its fields are spelled."""
    schema = app.openapi()
    body = schema["paths"][path]["post"]["requestBody"]
    reference = body["content"]["multipart/form-data"]["schema"]["$ref"]
    return schema["components"]["schemas"][reference.rsplit("/", 1)[-1]]["properties"]


def _screenings(sessions: sessionmaker[Session]) -> int:
    """How many ``screenings`` rows the database holds."""
    with sessions() as session:
        return len(session.execute(select(Screening)).scalars().all())
