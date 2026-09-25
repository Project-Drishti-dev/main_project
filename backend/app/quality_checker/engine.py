import inspect
import logging
from typing import Any

import cv2
import numpy as np

from . import (
    m1_sharpness,
    m2_noise,
    m3_exposure,
    m4_uniformity,
    m5_glare,
    m6_ppi,
    m7_skew,
    m8_coverage,
    m9_completeness,
)


logger = logging.getLogger(__name__)

MODULES = (
    (m1_sharpness, "Sharpness"),
    (m2_noise, "Noise"),
    (m3_exposure, "Exposure"),
    (m4_uniformity, "Lighting uniformity"),
    (m5_glare, "Glare"),
    (m6_ppi, "Resolution (PPI)"),
    (m7_skew, "Skew / perspective"),
    (m8_coverage, "Card coverage"),
    (m9_completeness, "Completeness (cut/crop)"),
)

TEXT_DENSITY_MAX = 0.10


def trim_padding(
    image: np.ndarray,
    tolerance: int = 1,
    flat_fraction: float = 0.995,
    minimum_gain: float = 0.05,
) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    height, width = image.shape[:2]
    corners = (
        image[0, 0],
        image[0, -1],
        image[-1, 0],
        image[-1, -1],
    )
    best_mask = None
    best_count = 0

    for corner in corners:
        if int(np.mean(corner)) >= 235:
            continue
        mask = (
            np.abs(image.astype(np.int16) - corner.astype(np.int16))
            .max(axis=2)
            <= tolerance
        )
        count = int(mask.sum())
        if count > best_count:
            best_mask = mask
            best_count = count

    if best_mask is None:
        return image, None

    rows = np.where(best_mask.mean(axis=1) < flat_fraction)[0]
    columns = np.where(best_mask.mean(axis=0) < flat_fraction)[0]
    if len(rows) == 0 or len(columns) == 0:
        return image, None

    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(columns[0]), int(columns[-1]) + 1
    kept_pixels = (y1 - y0) * (x1 - x0)
    if (
        kept_pixels > (1 - minimum_gain) * height * width
        or (y1 - y0) < 100
        or (x1 - x0) < 100
    ):
        return image, None

    return image[y0:y1, x0:x1], (x0, y0, x1, y1)


def _interior_ink_density(image: np.ndarray, points: np.ndarray) -> float:
    height, width = image.shape[:2]
    mask = np.zeros((height, width), np.uint8)
    cv2.fillConvexPoly(mask, points.astype(np.int32), 255)
    interior = mask > 0
    if interior.sum() == 0:
        return 0.0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    return float(binary[interior].astype(bool).mean())


def detect_mode(image: np.ndarray) -> str:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    thickness = max(2, int(0.03 * min(height, width)))
    sides = (
        gray[:thickness, :],
        gray[-thickness:, :],
        gray[:, :thickness],
        gray[:, -thickness:],
    )
    bright_sides = all((side >= 190).mean() >= 0.6 for side in sides)
    if not bright_sides:
        return "photo"

    try:
        card = m8_coverage.find_card(image)
    except Exception:
        logger.exception("Card detection failed while determining image mode")
        card = None

    if card is None or card["touches_border"] or card["area_frac"] > 0.85:
        return "scan"

    top_left, top_right, bottom_right, bottom_left = card["pts"]
    side_a = (
        np.linalg.norm(top_right - top_left)
        + np.linalg.norm(bottom_right - bottom_left)
    ) / 2.0
    side_b = (
        np.linalg.norm(bottom_left - top_left)
        + np.linalg.norm(bottom_right - top_right)
    ) / 2.0
    aspect = max(side_a, side_b) / max(min(side_a, side_b), 1e-6)
    expected_aspect = 85.6 / 54.0
    looks_like_card = (
        card["area_frac"] >= 0.15
        and abs(aspect - expected_aspect) / expected_aspect <= 0.25
    )
    if (
        looks_like_card
        and _interior_ink_density(image, card["pts"]) > TEXT_DENSITY_MAX
    ):
        looks_like_card = False
    return "photo" if looks_like_card else "scan"


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def run_all(
    image: np.ndarray,
    mode: str = "photo",
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    results = []
    for module, label in MODULES:
        try:
            assess = module.assess
            parameters = inspect.signature(assess).parameters
            kwargs = {
                key: value
                for key, value in (extra or {}).items()
                if key in parameters and value is not None
            }
            result = assess(image, mode=mode, **kwargs)
            result.pop("_pts", None)
            result.pop("_edges", None)
            result["label"] = label
            result["mode"] = mode
            results.append(_json_safe(result))
        except Exception:
            logger.exception("Quality-check module failed: %s", module.__name__)
            results.append(
                {
                    "module": module.__name__,
                    "label": label,
                    "score": None,
                    "unit": "",
                    "passed": False,
                    "mode": mode,
                    "rule": "",
                    "reasons": ["module_error"],
                    "details": {},
                }
            )
    return results


def analyze_image(image: np.ndarray, requested_mode: str = "auto") -> dict[str, Any]:
    original_height, original_width = image.shape[:2]
    trim_box = None

    trimmed, candidate_box = trim_padding(image)
    if candidate_box and requested_mode == "auto" and detect_mode(trimmed) == "photo":
        pass
    elif candidate_box:
        image = trimmed
        trim_box = candidate_box

    mode = detect_mode(image) if requested_mode == "auto" else requested_mode
    modules = run_all(image, mode, {"doc": "any"})
    overall_pass = all(result["passed"] is not False for result in modules)

    return {
        "mode": mode,
        "image": {"width": original_width, "height": original_height},
        "trim_box": trim_box,
        "overall_pass": overall_pass,
        "modules": modules,
    }
