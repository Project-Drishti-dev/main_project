import struct
import zlib

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.analysis import MAX_UPLOAD_BYTES
from app.errors import APIError
from app import main as api
from app.main import app


client = TestClient(app)


def make_png_header(width: int, height: int) -> bytes:
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


def make_png() -> bytes:
    image = np.full((480, 640, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (100, 120), (540, 360), (30, 30, 30), 4)
    cv2.putText(
        image,
        "SAMPLE CARD",
        (170, 250),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (20, 20, 20),
        3,
    )
    encoded, data = cv2.imencode(".png", image)
    assert encoded
    return data.tobytes()


def test_analyze_requires_an_image():
    response = client.post("/api/analyze")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IMAGE_REQUIRED"


def test_analyze_rejects_unsupported_media_type():
    response = client.post(
        "/api/analyze",
        files={"image": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_analyze_rejects_files_over_the_upload_limit():
    response = client.post(
        "/api/analyze",
        files={
            "image": (
                "large.png",
                b"x" * (MAX_UPLOAD_BYTES + 1),
                "image/png",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_analyze_rejects_bytes_that_are_not_a_decodable_image():
    response = client.post(
        "/api/analyze",
        files={"image": ("broken.png", b"not a real png", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_analyze_rejects_a_declared_type_that_does_not_match_the_image():
    response = client.post(
        "/api/analyze",
        files={"image": ("sample.jpg", make_png(), "image/jpeg")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "MEDIA_TYPE_MISMATCH"


def test_analyze_rejects_images_over_the_decoded_pixel_limit():
    response = client.post(
        "/api/analyze",
        files={
            "image": (
                "huge.png",
                make_png_header(5000, 5000),
                "image/png",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"


def test_analyze_returns_all_nine_quality_checks():
    response = client.post(
        "/api/analyze",
        files={"image": ("sample.png", make_png(), "image/png")},
        data={"mode": "scan"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "scan"
    assert result["image"] == {"width": 640, "height": 480}
    assert isinstance(result["overall_pass"], bool)
    assert len(result["modules"]) == 9
    assert all(
        {
            "module",
            "label",
            "score",
            "unit",
            "passed",
            "rule",
            "reasons",
            "details",
            "mode",
        }
        <= module.keys()
        for module in result["modules"]
    )
    assert not any("_pts" in module or "_edges" in module for module in result["modules"])


def test_analyze_rejects_an_unknown_mode():
    response = client.post(
        "/api/analyze",
        files={"image": ("sample.png", make_png(), "image/png")},
        data={"mode": "guess"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_MODE"


def test_cors_does_not_allow_arbitrary_origins():
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_a_configured_local_origin():
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"


def test_unexpected_analysis_errors_return_a_generic_message(monkeypatch):
    def fail_analysis(*_args):
        raise RuntimeError("internal implementation detail")

    monkeypatch.setattr(api, "analyze_uploaded_image", fail_analysis)
    response = client.post(
        "/api/analyze",
        files={"image": ("sample.png", make_png(), "image/png")},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "ANALYSIS_FAILED",
            "message": "The image could not be analyzed. Please try again.",
        }
    }
