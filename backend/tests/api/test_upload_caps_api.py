"""11.9: the upload caps on ``POST /api/screenings``, held at their edges.

The caps are not new to this endpoint -- :func:`app.analysis.read_uploaded_image`
spells them once and both endpoints reach it -- so what is asserted here is not
that something large is refused, which other tests already hold, but that each
cap sits exactly where :mod:`app.config` says it does.  A file of exactly
``MAX_UPLOAD_BYTES`` and an image of exactly ``MAX_IMAGE_PIXELS`` are both
accepted; one byte and one pixel more are both refused.  A cap moved either
way, or written ``>=`` where it means ``>``, passes every test that only looks
at something comfortably over the line.

Every upload here is a real, decodable image, so a refusal is the cap's and not
a side effect of bytes that were never a PNG.
"""

import struct
import zlib
from collections.abc import Iterator

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.config import MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES
from app.main import app
from app.storage import db
from app.storage.models import Base, Screening


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One migrated in-memory database, bound in as the session dependency.

    Bound into the app rather than named by ``DATABASE_URL`` at import, so the
    rows these tests count are the ones the route wrote.
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


# --- the byte cap --------------------------------------------------------


def test_a_file_of_exactly_the_byte_cap_is_accepted(client, sessions):
    """The cap is a ceiling the whole cap reaches, not one short of it."""
    response = client.post(
        "/api/screenings",
        files={"image": ("page.png", _at_byte_cap(), "image/png")},
    )

    assert response.status_code == 200
    assert _screenings(sessions) == 1


def test_one_byte_over_the_byte_cap_is_refused(client, sessions):
    response = client.post(
        "/api/screenings",
        files={"image": ("page.png", _one_byte_over_byte_cap(), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"
    assert _screenings(sessions) == 0


def test_the_byte_cap_is_measured_before_the_upload_is_identified(client, sessions):
    """An upload over the cap is too large whatever it claims to be."""
    response = client.post(
        "/api/screenings",
        files={"image": ("notes.txt", _one_byte_over_byte_cap(), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"
    assert _screenings(sessions) == 0


# --- the pixel cap -------------------------------------------------------


def test_an_image_of_exactly_the_pixel_cap_is_accepted(client, sessions):
    response = client.post(
        "/api/screenings",
        files={"image": ("page.png", _at_pixel_cap(4000, 5000), "image/png")},
    )

    assert response.status_code == 200
    assert _screenings(sessions) == 1


def test_one_pixel_over_the_cap_is_refused(client, sessions):
    response = client.post(
        "/api/screenings",
        files={"image": ("page.png", _png(_blank(4000, 5001)), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"
    assert _screenings(sessions) == 0


def test_the_pixel_cap_counts_the_image_and_not_its_longer_side(client, sessions):
    """20,000 pixels wide is inside the cap; a cap written per side is not.

    The same 20,000,000 pixels as ``4000`` by ``5000``, with one side carried
    past any round per-side bound a reader might reach for instead.  The
    pipeline is asked about the area, so it answers the same.
    """
    response = client.post(
        "/api/screenings",
        files={"image": ("wide.png", _at_pixel_cap(20000, 1000), "image/png")},
    )

    assert response.status_code == 200
    assert _screenings(sessions) == 1


# --- both endpoints reach the same two caps ------------------------------


@pytest.mark.parametrize("path", ["/api/analyze", "/api/screenings"])
def test_the_byte_cap_is_the_same_refusal_on_both_endpoints(client, path):
    response = client.post(
        path,
        files={"image": ("page.png", _one_byte_over_byte_cap(), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"


@pytest.mark.parametrize("path", ["/api/analyze", "/api/screenings"])
def test_the_pixel_cap_is_the_same_refusal_on_both_endpoints(client, path):
    response = client.post(
        path,
        files={"image": ("page.png", _png(_blank(4000, 5001)), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"


# --- the uploads these tests upload --------------------------------------


def _blank(width: int, height: int) -> np.ndarray:
    """A uniform page of that shape: the cheapest image the decoders accept."""
    return np.full((height, width, 3), 245, dtype=np.uint8)


def _png(image: np.ndarray) -> bytes:
    """``image`` as the PNG bytes an upload would carry."""
    encoded, data = cv2.imencode(".png", image)
    assert encoded
    return data.tobytes()


def _carried_to(data: bytes, size: int) -> bytes:
    """``data`` with a text chunk added, so the file is exactly ``size`` bytes.

    A well-formed PNG rather than trailing rubbish, so the file stays one the
    decoders on the path accept: otherwise a cap test would be measuring
    whether the bytes are a PNG and not where the cap is.
    """
    body = b"x" * (size - len(data) - 12)
    kind = b"tEXt"
    carried = data + struct.pack(">I", len(body)) + kind + body + struct.pack(
        ">I", zlib.crc32(kind + body) & 0xFFFFFFFF
    )
    assert len(carried) == size
    return carried


def _at_byte_cap() -> bytes:
    return _carried_to(_png(_blank(640, 480)), MAX_UPLOAD_BYTES)


def _one_byte_over_byte_cap() -> bytes:
    return _carried_to(_png(_blank(640, 480)), MAX_UPLOAD_BYTES + 1)


def _at_pixel_cap(width: int, height: int) -> bytes:
    """A real image of exactly ``MAX_IMAGE_PIXELS`` pixels.

    The shape is checked here rather than assumed, so a change to the cap fails
    the test instead of quietly measuring a different area.
    """
    assert width * height == MAX_IMAGE_PIXELS
    return _png(_blank(width, height))


def _screenings(sessions: sessionmaker[Session]) -> int:
    """How many ``screenings`` rows the database holds."""
    with sessions() as session:
        return len(session.execute(select(Screening)).scalars().all())