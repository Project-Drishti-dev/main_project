from io import BytesIO
from typing import Any, Final

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from .config import MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES
from .errors import APIError
from .quality_checker.engine import analyze_image


ALLOWED_IMAGE_TYPES: Final = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
ALLOWED_MODES: Final = {"auto", "photo", "scan"}


def analyze_uploaded_image(
    contents: bytes,
    content_type: str | None,
    requested_mode: str = "auto",
) -> dict[str, Any]:
    if len(contents) > MAX_UPLOAD_BYTES:
        raise APIError(413, "IMAGE_TOO_LARGE", "Choose an image that is 10 MB or smaller.")
    if not contents:
        raise APIError(422, "INVALID_IMAGE", "The uploaded file is empty or is not a supported image.")

    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    expected_format = ALLOWED_IMAGE_TYPES.get(media_type)
    if expected_format is None:
        raise APIError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Upload a JPEG, PNG, or WebP image.",
        )

    if requested_mode not in ALLOWED_MODES:
        raise APIError(
            422,
            "INVALID_MODE",
            "Mode must be one of: auto, photo, or scan.",
        )

    try:
        with Image.open(BytesIO(contents)) as probe:
            if probe.format != expected_format:
                raise APIError(
                    415,
                    "MEDIA_TYPE_MISMATCH",
                    "The file contents do not match the declared image type.",
                )
            width, height = probe.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise APIError(
                    413,
                    "IMAGE_DIMENSIONS_TOO_LARGE",
                    "The image dimensions exceed the supported limit.",
                )
            probe.verify()
    except APIError:
        raise
    except Image.DecompressionBombError:
        raise APIError(
            413,
            "IMAGE_DIMENSIONS_TOO_LARGE",
            "The image dimensions exceed the supported limit.",
        ) from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise APIError(
            422,
            "INVALID_IMAGE",
            "The uploaded file is empty or is not a supported image.",
        ) from None

    try:
        encoded = np.frombuffer(contents, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    except cv2.error:
        image = None
    if image is None:
        raise APIError(
            422,
            "INVALID_IMAGE",
            "The uploaded file is empty or is not a supported image.",
        )

    return analyze_image(image, requested_mode=requested_mode)
