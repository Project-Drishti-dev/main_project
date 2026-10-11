"""26.9: the public demo answers with a synthetic-image-only notice.

The demo is unauthenticated by decision, so the one thing a visitor must not
walk away believing is that these checks say who a document belongs to. The
notice travels in the response beside the findings, and the cases below hold
it to the endpoint, the contract, and its own wording.
"""

import cv2
from fastapi.testclient import TestClient

from app.analysis import SYNTHETIC_IMAGE_NOTICE
from app.main import app
from tests.fixtures import mrz_images


#: A page with a real machine-readable zone on it, so the analyses answered
#: below are real ones rather than a stand-in for one.
PAGE = mrz_images.render_format("TD3")


client = TestClient(app)


def _upload() -> dict:
    """One real upload, as the endpoint's multipart form carries it."""
    encoded, data = cv2.imencode(".png", PAGE.image)
    assert encoded
    return {"image": ("page.png", data.tobytes(), "image/png")}


def test_an_analysis_answers_with_the_notice():
    """The 200 body carries the notice, spelled as the module spells it."""
    response = client.post("/api/analyze", files=_upload())

    assert response.status_code == 200
    assert response.json()["notice"] == SYNTHETIC_IMAGE_NOTICE


def test_every_analysis_carries_the_notice_and_not_only_the_first():
    """The notice is part of an answer, not something a first call sets up."""
    first = client.post("/api/analyze", files=_upload())
    second = client.post("/api/analyze", files=_upload())

    assert first.json()["notice"] == second.json()["notice"]


def test_the_notice_says_what_these_checks_are_not():
    """A rewording that drops either half of the meaning fails here."""
    notice = SYNTHETIC_IMAGE_NOTICE.lower()

    assert "synthetic" in notice
    assert "identity" in notice


def test_a_refused_upload_answers_with_the_envelope_and_no_notice():
    """The notice is a result field; a refusal carries the envelope alone."""
    response = client.post(
        "/api/analyze",
        files={"image": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert "notice" not in response.json()


def test_the_documented_response_carries_the_notice():
    """A client reading the contract finds the field the answers carry."""
    properties = app.openapi()["components"]["schemas"]["AnalysisResponse"][
        "properties"
    ]

    assert properties["notice"]["type"] == "string"