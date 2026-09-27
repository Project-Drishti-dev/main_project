"""
Stage A — get raw MRZ text out of a document photo.

Pipeline:
  1. Locate the MRZ strip (it's always along the bottom of the document).
  2. Deskew + crop tightly to just that strip.
  3. Clean up contrast / binarize so OCR has an easy time.
  4. Run tesseract, restricted to the MRZ alphabet (A-Z, 0-9, '<').

This stage only has to be "good enough" — Stage B's check-digit math is
what actually catches whether the text it produced is trustworthy. A
garbled OCR read will simply fail its checksum, which is the correct
outcome (we don't want to silently guess).
"""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
import pytesseract

from .models import ExtractionResult
from .mrz_parse import parse, MRZParseError

_MRZ_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
_TESSERACT_CONFIG = (
    f'--psm 6 --oem 3 -c tessedit_char_whitelist="{_MRZ_WHITELIST}"'
)


def _load_image(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")
    return img


def _deskew(gray: np.ndarray) -> np.ndarray:
    """
    Straighten small rotations using the orientation of dark (text/ink)
    pixels. Cheap and good enough for phone-photo-level skew; not meant to
    correct extreme perspective distortion.
    """
    # Threshold to find "ink" pixels (text is dark on a light background).
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thresh)
    if coords is None or len(coords) < 50:
        return gray  # not enough signal to safely deskew

    angle = cv2.minAreaRect(coords)[-1]
    # cv2.minAreaRect returns angle in [-90, 0); normalize to a small
    # correction rather than accidentally rotating 90 degrees.
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5 or abs(angle) > 20:
        return gray  # ignore noise / refuse implausibly large corrections

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _locate_mrz_band(gray: np.ndarray) -> np.ndarray:
    """
    Find the tight vertical band containing the MRZ inside the bottom
    portion of the document image, using row-wise dark-pixel density
    (the MRZ is dense, evenly spaced monospaced text — it stands out
    from surrounding photo/background rows).
    """
    h, w = gray.shape[:2]
    bottom_start = int(h * 0.55)  # MRZ is always in roughly the bottom half
    band = gray[bottom_start:h, :]

    thresh = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    row_density = thresh.sum(axis=1) / 255.0  # dark-pixel count per row
    row_frac = row_density / max(w, 1)

    # Text rows have moderate-to-high density; near-blank rows between
    # lines / margins have very low density. Use a permissive threshold
    # since font weight and phone-camera exposure vary a lot.
    text_rows = np.where(row_frac > 0.12)[0]
    if len(text_rows) == 0:
        # Fall back to the whole bottom band if density detection fails —
        # OCR + checksum will reject garbage downstream.
        return band

    top = max(text_rows[0] - 8, 0)
    bottom = min(text_rows[-1] + 8, band.shape[0])
    return band[top:bottom, :]


def _preprocess_for_ocr(strip: np.ndarray) -> np.ndarray:
    """Upscale + binarize the isolated MRZ strip so tesseract reads it cleanly."""
    # Upscaling small crops noticeably improves tesseract accuracy.
    scale = 3
    resized = cv2.resize(
        strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
    )
    resized = cv2.fastNlMeansDenoising(resized, h=10)
    # Otsu binarization gives crisp black-on-white text for OCR.
    _, binarized = cv2.threshold(
        resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return binarized


def extract_mrz_text(image_path: str) -> ExtractionResult:
    """
    Full Stage A: image path -> ExtractionResult carrying raw OCR text and
    (if parsing succeeded) structured MRZFields.
    """
    try:
        img = _load_image(image_path)
    except FileNotFoundError as e:
        return ExtractionResult(success=False, error=str(e))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = _deskew(gray)
    strip = _locate_mrz_band(gray)

    if strip.size == 0 or strip.shape[0] < 5:
        return ExtractionResult(success=False, error="MRZ strip not found in image")

    processed = _preprocess_for_ocr(strip)

    raw_text = pytesseract.image_to_string(processed, config=_TESSERACT_CONFIG)

    confidence: Optional[float] = None
    try:
        data = pytesseract.image_to_data(
            processed, config=_TESSERACT_CONFIG, output_type=pytesseract.Output.DICT
        )
        confs = [float(c) for c in data.get("conf", []) if str(c) not in ("-1", "")]
        if confs:
            confidence = sum(confs) / len(confs)
    except Exception:
        pass  # confidence is a nice-to-have, not required for the pipeline

    if not raw_text or not raw_text.strip():
        return ExtractionResult(
            success=False, error="OCR produced no text from the MRZ region",
            ocr_confidence=confidence,
        )

    try:
        fields = parse(raw_text)
    except MRZParseError as e:
        return ExtractionResult(
            success=False,
            raw_text=raw_text,
            error=f"MRZ text found but could not be parsed: {e}",
            ocr_confidence=confidence,
        )

    return ExtractionResult(
        success=True, raw_text=raw_text, mrz_fields=fields, ocr_confidence=confidence
    )
