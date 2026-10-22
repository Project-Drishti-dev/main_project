"""14.3: stage 0 -- the capture gate, run as a stage and read as flags.

:func:`run_quality` hands the context's frame to the existing quality gate and
appends one :class:`~app.risk.flags.EvidenceFlag` per check that did not pass,
every one of them tiered ``"quality"``.  :data:`STAGE_NAME` is the name the
cascade's registry holds the stage under, and :data:`CHECKS` is the one table
mapping each of the gate's own checks to the id its failure carries.

**Only ``passed is False`` reaches the stream.**  A check that passed and a
check that does not apply to this capture both write nothing: the gate reports
the second as ``None``, which is not a failure and is not an absence of one.
"""

import dataclasses
import types
import typing

from app.quality_checker import engine
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "CHECKS",
    "QUALITY_BAND",
    "QUALITY_TIER",
    "STAGE_NAME",
    "Check",
    "UnknownCheckError",
    "run_quality",
]

#: The name stage 0 is registered under in the cascade's registry.
STAGE_NAME = "quality"

#: The tier every finding this stage writes carries, which is the one name on
#: :class:`~app.risk.flags.EvidenceFlag` that is not a tier number.
QUALITY_TIER = "quality"

#: The severity band a failed check's finding sits in.  The weight itself is
#: the weightset's, and every one of the nine rows is banded ``low``.
QUALITY_BAND = "low"

#: What a check reports instead of a reason, when the gate refused it.
NO_REASON = "no_reason_reported"


@dataclasses.dataclass(frozen=True)
class Check:
    """One check of the gate: the id its failure carries and the officer's sentence."""

    flag_id: str
    label: str


#: The gate's own label to the finding that check's failure becomes, keyed on
#: the label :func:`app.quality_checker.engine.run_all` writes onto every
#: result.  **A tenth check is a tenth row here and a tenth id in
#: :mod:`app.risk.flag_ids`**, and a label this table does not hold is refused
#: by :func:`_flag` rather than dropped.
CHECKS: typing.Mapping[str, Check] = types.MappingProxyType(
    {
        "Sharpness": Check(
            flag_ids.QUALITY_BLUR,
            "The capture is too blurred to read.",
        ),
        "Noise": Check(
            flag_ids.QUALITY_NOISE,
            "The capture carries sensor noise above the ceiling.",
        ),
        "Exposure": Check(
            flag_ids.QUALITY_EXPOSURE,
            "The capture is under- or over-exposed.",
        ),
        "Lighting uniformity": Check(
            flag_ids.QUALITY_UNEVEN_LIGHTING,
            "The page is lit unevenly across its own surface.",
        ),
        "Glare": Check(
            flag_ids.QUALITY_GLARE,
            "A reflection covers the page.",
        ),
        "Resolution (PPI)": Check(
            flag_ids.QUALITY_LOW_RESOLUTION,
            "The capture resolves the page at too few pixels per inch.",
        ),
        "Skew / perspective": Check(
            flag_ids.QUALITY_SKEW,
            "The page is captured far off its own plane.",
        ),
        "Card coverage": Check(
            flag_ids.QUALITY_LOW_COVERAGE,
            "The document fills too little of the frame to read.",
        ),
        "Completeness (cut/crop)": Check(
            flag_ids.QUALITY_CROPPED,
            "An edge of the document is cut off by the frame.",
        ),
    }
)

#: Where each check measured what it measured, read off the gate's own module
#: table by its label rather than retyped beside :data:`CHECKS`.
_SOURCES: typing.Mapping[str, str] = types.MappingProxyType(
    {label: module.__name__ for module, label in engine.MODULES}
)


class UnknownCheckError(ValueError):
    """Raised when the gate reports a check this stage holds no finding for.

    A ``ValueError``, so a caller catching one around its cascade keeps
    working.  **A tenth check added without a tenth id is a wiring fault and
    not an absence**, and dropping the result instead would report a capture
    the gate could not clear as one it did.
    """


def run_quality(context: "ScreeningContext") -> None:
    """Run the capture gate over ``context`` and append a flag per failure.

    :param context: the run's record; only its ``flags`` list grows.
    :returns: ``None`` -- the stage answers by what it wrote.
    :raises UnknownCheckError: when the gate reports a check :data:`CHECKS`
        does not hold.
    """
    report = engine.analyze_image(context.image)
    context.flags.extend(_flags(report["modules"]))


def _flags(results: typing.Iterable[typing.Mapping]) -> list[EvidenceFlag]:
    """One flag per result the gate did not pass, in the gate's own order."""
    return [_flag(result) for result in results if result.get("passed") is False]


def _flag(result: typing.Mapping) -> EvidenceFlag:
    """``result`` as a finding, or a refusal naming the check it reports."""
    label = result.get("label")
    check = CHECKS.get(label)
    source = _SOURCES.get(label)
    if check is None or source is None:
        raise UnknownCheckError(
            f"the quality gate reported a check this stage holds no finding "
            f"for: {label!r}"
        )
    return EvidenceFlag(
        id=check.flag_id,
        tier=QUALITY_TIER,
        label=check.label,
        weight_band=QUALITY_BAND,
        value=1.0,
        confidence=1.0,
        region=None,
        expected=None,
        found=_found(result),
        reason=_reason(result),
        source_module=source,
        field=None,
    )


def _found(result: typing.Mapping) -> str | None:
    """The number the check measured, as it printed it, or ``None`` for nothing."""
    score = result.get("score")
    return None if score is None else str(score)


def _reason(result: typing.Mapping) -> str:
    """The check's own reasons joined, or the words for a check that named none."""
    reasons = result.get("reasons") or ()
    return ", ".join(str(one) for one in reasons) or NO_REASON
