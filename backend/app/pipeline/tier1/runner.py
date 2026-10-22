"""Tier 1 as one call: a page in, a record of what could be read off it.

A page no engine could read is answered by a result rather than a refusal, so
an absent OCR engine never fails a document.  The reasoning, and what stays
loud instead, is D86.  14.5's ``flags`` carries the findings its ``R1`` is
summed from, and there is exactly one of them today.
"""

import dataclasses
from collections.abc import Mapping

from app.pipeline.tier1 import selection
from app.pipeline.tier1.ocr import NO_WORDS, OcrEngine, OcrResult
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

__all__ = [
    "SOURCE_MODULE",
    "UNREADABLE_BAND",
    "UNREADABLE_LABEL",
    "Tier1Result",
    "run_tier1",
]

#: The tier every finding this runner writes carries.
_TIER = 1

#: The band an unreadable page's finding sits in, which is the band v1
#: carries under the id below.
UNREADABLE_BAND = "low"

#: The officer's sentence for a page no engine could read.
UNREADABLE_LABEL = "No engine could read the printed page."

#: The module a finding from this runner is traced to.
SOURCE_MODULE = "app.pipeline.tier1.runner"


@dataclasses.dataclass(frozen=True)
class Tier1Result:
    """What one page was read as: the read, and whether an engine could read.

    ``ocr`` is the chosen engine's own :class:`OcrResult`, or the shared empty
    read when there was no engine to read with.  ``ocr_available`` says which
    of the two it is, because a blank page and an unread one both carry no
    words and nothing else in the read would tell them apart.

    ``flags`` holds the findings this read produced, in the order they were
    made, and is empty when the page said nothing against itself.
    """

    ocr: OcrResult
    ocr_available: bool
    #: The findings 14.5's ``R1`` is summed from; empty is a real answer.
    flags: tuple[EvidenceFlag, ...] = ()


def run_tier1(
    image,
    preference: str | None = None,
    *,
    engines: Mapping[str, OcrEngine] | None = None,
) -> Tier1Result:
    """Read ``image`` with the chosen engine, or degrade to no words.

    :param image: the frame handed to the engine 12.5 chose, read through
        :func:`~app.pipeline.tier1.selection.select_engine`.
    :param preference: one of :data:`~app.pipeline.tier1.selection.ENGINE_NAMES`,
        or ``None`` for no preference.
    :param engines: the registry to choose from, defaulting to the default one.
    :returns: a :class:`Tier1Result` holding the engine's own read, or the
        shared empty read with ``ocr_available`` false when no engine was
        available -- one answer for an uninstalled engine, an unavailable
        preference and an empty registry alike.  A page no engine could read
        carries one :data:`UNREADABLE_LABEL` finding; a page one could read
        and which found nothing against itself carries none.
    :raises selection.UnknownEngineError: when ``preference`` names no engine.
    """
    engine = selection.select_engine(preference, engines=engines)
    if engine is None:
        return Tier1Result(
            ocr=NO_WORDS, ocr_available=False, flags=(_unreadable(),)
        )
    return Tier1Result(ocr=engine.read(image), ocr_available=True)


def _unreadable() -> EvidenceFlag:
    """The one finding a page no engine could read produces, at full strength."""
    return EvidenceFlag(
        id=flag_ids.OCR_LOW_CONFIDENCE,
        tier=_TIER,
        label=UNREADABLE_LABEL,
        weight_band=UNREADABLE_BAND,
        value=1.0,
        confidence=1.0,
        region=None,
        expected=None,
        found=None,
        reason="no OCR engine was available to read the page",
        source_module=SOURCE_MODULE,
        field=None,
    )
