"""Run the single-image Tier 0, Tier 1 and Tier 2 checks for the upload UI."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType, SimpleNamespace
from typing import Any, Callable

from app.pipeline.tier0 import runner as tier0
from app.pipeline.tier1 import runner as tier1
from app.pipeline.tier1 import selection
from app.pipeline.tier2 import anomaly, base, copy_move, deepfake, ela, flags, morph
from app.pipeline.tier2 import noise_residual, stamp

TESSERACT_PREFERENCE = selection.TESSERACT
TIER_NOTICE = (
    "These are prototypes, not proof. They may highlight patterns to review, "
    "but they cannot tell whether a document is genuine."
)
TIER2_DISPLAY_COPY: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        ela.MODULE_NAME: (
            "Compression patterns",
            "Looks for areas that change differently when the image is saved "
            "again. Normal compression can cause this too.",
        ),
        noise_residual.MODULE_NAME: (
            "Image texture",
            "Compares image texture across areas. Lighting, cameras, and "
            "printing can create differences.",
        ),
        copy_move.MODULE_NAME: (
            "Repeated image content",
            "Looks for similar content repeated in one image. Repeated patterns "
            "can be normal.",
        ),
        stamp.MODULE_NAME: (
            "Stamp similarity",
            "Compares marks with sample stamp shapes. A similar shape does not "
            "prove a stamp is genuine.",
        ),
        morph.MODULE_NAME: (
            "Face blending",
            "Looks for patterns that can appear when faces are blended. It "
            "cannot confirm a face was changed.",
        ),
        deepfake.MODULE_NAME: (
            "AI-image patterns",
            "Checks simple visual patterns; it is not trained to spot "
            "AI-generated images.",
        ),
        "tamper_anomaly": (
            "Unusual image patterns",
            "Compares the image with synthetic examples. The score is not the "
            "chance that the document is fake.",
        ),
    }
)
DEFAULT_ANOMALY_SCORER = anomaly.AnomalyScorer()

DEFAULT_TIER2_MODULES: Mapping[str, base.DeepModule] = MappingProxyType(
    {
        ela.MODULE_NAME: ela.ELAModule(),
        noise_residual.MODULE_NAME: noise_residual.NoiseResidualModule(),
        copy_move.MODULE_NAME: copy_move.CopyMoveModule(),
        stamp.MODULE_NAME: stamp.StampModule(),
        morph.MODULE_NAME: morph.MorphModule(),
        deepfake.MODULE_NAME: deepfake.DeepfakeModule(),
    }
)


@dataclasses.dataclass(frozen=True)
class TierCheck:
    """A safe check summary with optional prototype OCR text."""

    tier: int
    module: str
    label: str
    status: str
    value: float | None
    is_stub: bool
    model_version: str | None
    detail: str
    recognized_text: str | None = None

    def to_wire(self) -> dict[str, Any]:
        """Return the fields exposed by the analysis API."""
        return dataclasses.asdict(self)


def run_tier_checks(
    image: Any,
    *,
    document_type: str | None = None,
    reference_date=None,
    parsed_document=None,
    watchlist=None,
    tier0_runner: Callable[..., Any] | None = None,
    tier1_runner: Callable[..., Any] | None = None,
    tier2_modules: Mapping[str, base.DeepModule] | None = None,
    anomaly_scorer: anomaly.AnomalyScorer | None = DEFAULT_ANOMALY_SCORER,
) -> tuple[TierCheck, ...]:
    """Return the available single-image check summaries in tier order."""
    run_zero = tier0.run_tier0 if tier0_runner is None else tier0_runner
    run_one = tier1.run_tier1 if tier1_runner is None else tier1_runner
    modules = DEFAULT_TIER2_MODULES if tier2_modules is None else tier2_modules
    checks: list[TierCheck] = []

    try:
        zero = run_zero(
            image,
            document_type=document_type,
            reference_date=reference_date,
            parsed_document=parsed_document,
            watchlist=watchlist,
        )
    except Exception:
        checks.append(_failed(0, "mrz_detection", "MRZ format detection"))
        zero = None
    else:
        zero_detail = "; ".join(flag.label for flag in zero.flags)
        if not zero_detail:
            zero_detail = (
                f"Detected {zero.detected_format} MRZ format."
                if zero.detected_format
                else "No MRZ format detected."
            )
        checks.append(
            TierCheck(
                tier=0,
                module="mrz_detection",
                label="MRZ format detection",
                status="hard_fail" if zero.hard_failed else "completed",
                value=None,
                is_stub=False,
                model_version=None,
                detail=zero.hard_fail_reason or zero_detail,
            )
        )

    if zero is not None and zero.hard_failed:
        return tuple(checks)

    try:
        one = run_one(image, preference=TESSERACT_PREFERENCE)
    except Exception:
        checks.append(_failed(1, "ocr", "OCR engine"))
    else:
        recognized_text = (
            " ".join(word.text for word in one.ocr.words).strip()
            if one.ocr_available
            else ""
        ) or None
        checks.append(
            TierCheck(
                tier=1,
                module="ocr",
                label="OCR engine",
                status="completed" if one.ocr_available else "unavailable",
                value=None,
                is_stub=False,
                model_version=None,
                detail=(
                    "Tesseract ran; OCR text is shown below."
                    if recognized_text
                    else "Tesseract ran; no text was recognized."
                    if one.ocr_available
                    else "Tesseract is unavailable; OCR was not run."
                ),
                recognized_text=recognized_text,
            )
        )

    context = SimpleNamespace(image=image)
    labels = {rule.module: rule.label for rule in flags.RULES}
    for name, module in modules.items():
        display_label, display_detail = TIER2_DISPLAY_COPY.get(
            name, (labels.get(name, name), None)
        )
        try:
            result = module.run(context)
            if not isinstance(result, base.DeepResult) or result.module != name:
                raise TypeError("Tier 2 module returned an invalid result")
        except Exception:
            checks.append(_failed(2, name, display_label, is_stub=True))
            continue
        checks.append(
            TierCheck(
                tier=2,
                module=name,
                label=display_label,
                status="stub" if result.is_stub else "completed",
                value=result.score,
                is_stub=result.is_stub,
                model_version=result.model_version,
                detail=display_detail or result.detail,
            )
        )

    if anomaly_scorer is not None:
        anomaly_label, anomaly_detail = TIER2_DISPLAY_COPY["tamper_anomaly"]
        try:
            vector = anomaly.feature_vector(image)
            rank = anomaly_scorer.rank(vector)
        except Exception:
            checks.append(
                _failed(
                    2,
                    "tamper_anomaly",
                    anomaly_label,
                    is_stub=True,
                )
            )
        else:
            checks.append(
                TierCheck(
                    tier=2,
                    module="tamper_anomaly",
                    label=anomaly_label,
                    status="stub",
                    value=rank,
                    is_stub=True,
                    model_version=anomaly_scorer.model_version,
                    detail=anomaly_detail,
                )
            )
    return tuple(checks)


def _failed(
    tier: int, module: str, label: str, *, is_stub: bool = False
) -> TierCheck:
    """Return a generic failure without retaining an exception message."""
    return TierCheck(
        tier=tier,
        module=module,
        label=label,
        status="failed",
        value=None,
        is_stub=is_stub,
        model_version=None,
        detail="This check could not run.",
    )
