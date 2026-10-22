"""14.5 -- Tier 1 runs as a stage and leaves R1 on the context.

The headline is the task's own verification: ``R1`` is present in the context
after Tier 1 has run.  The rest pin what ``R1`` is -- the weighted sum of Tier
1's own findings, against the weightset the caller hands over, and not of every
flag the cascade has collected -- and that a Tier 1 which found nothing writes
``0.0`` rather than leaving the score absent.
"""

import datetime
import uuid

from app.pipeline import orchestrator, quality
from app.pipeline.tier0 import runner as tier0_runner
from app.pipeline.tier0 import stage as tier0_stage
from app.pipeline.tier1 import runner
from app.pipeline.tier1.ocr import NO_WORDS
from app.pipeline.tier1 import stage as tier1_stage
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag
from app.risk.weightsets.loader import load_weightset
from app.risk.weightsets.lookup import weight_for

SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")
REFERENCE_DATE = datetime.date(2026, 10, 2)

#: A frame standing in for the working one; nothing here reads its pixels.
PAGE = object()

#: The tier every finding this file builds carries.
TIER_1 = 1


def _context(**overrides):
    """A context carrying the constants above, with ``overrides`` applied."""
    stated = {
        "screening_id": SCREENING_ID,
        "document_type": "passport",
        "image": PAGE,
        "reference_date": REFERENCE_DATE,
        "depth_mode": orchestrator.STANDARD,
    }
    stated.update(overrides)
    return orchestrator.ScreeningContext(**stated)


def _weight(flag_id):
    """What the shipped weightset gives ``flag_id``."""
    return weight_for(load_weightset(), flag_id)


def _result(*flags):
    """A page that could be read, carrying ``flags`` as the findings it gave."""
    return runner.Tier1Result(
        ocr=NO_WORDS, ocr_available=True, flags=tuple(flags)
    )


def _tier1_flag(flag_id, band):
    """One Tier 1 finding, in the shape the runner hands the cascade."""
    return EvidenceFlag(
        id=flag_id,
        tier=TIER_1,
        label="The printed field disagrees with the zone beside it.",
        weight_band=band,
        value=1.0,
        confidence=1.0,
        region=None,
        expected="1990-01-01",
        found="1990-01-02",
        reason="the printed value disagrees with the machine-readable zone",
        source_module="app.pipeline.tier1.mismatch",
        field="date_of_birth",
    )


def _quality_flag():
    """One stage-0 finding, to show R1 is not the whole flag stream."""
    return EvidenceFlag(
        id=flag_ids.QUALITY_BLUR,
        tier=quality.QUALITY_TIER,
        label="The capture is too blurred to read.",
        weight_band=quality.QUALITY_BAND,
        value=1.0,
        confidence=1.0,
        region=None,
        expected=None,
        found="12.0",
        reason="the sharpness module's own floor",
        source_module="app.quality_checker.engine",
        field=None,
    )


def _tier1(monkeypatch, result):
    """Stand the Tier 1 runner in for this test, answering with ``result``."""
    monkeypatch.setattr(
        tier1_stage.runner, "run_tier1", lambda *args, **kwargs: result
    )


def _gate(monkeypatch):
    """Stand the capture gate in for this test, reporting a clean capture."""
    monkeypatch.setattr(
        quality.engine,
        "analyze_image",
        lambda image, requested_mode="auto": {"modules": []},
    )


def _tier0(monkeypatch, result):
    """Stand the Tier 0 runner in for this test, answering with ``result``."""
    monkeypatch.setattr(
        tier0_stage.runner, "run_tier0", lambda *args, **kwargs: result
    )


def test_r1_is_present_in_the_context_after_tier_1(monkeypatch):
    """The task's own verification, against a Tier 1 that found something."""
    _tier1(
        monkeypatch,
        _result(_tier1_flag(flag_ids.OCR_LOW_CONFIDENCE, "low")),
    )
    context = _context()

    tier1_stage.run_tier1(context)

    assert context.r1 == _weight(flag_ids.OCR_LOW_CONFIDENCE)
    assert [flag.id for flag in context.flags] == [flag_ids.OCR_LOW_CONFIDENCE]


def test_a_tier_1_that_found_nothing_writes_zero_not_none(monkeypatch):
    """An empty sum is 0.0, which is an answer rather than a missing one."""
    _tier1(monkeypatch, _result())
    context = _context()

    tier1_stage.run_tier1(context)

    assert context.r1 == 0.0


def test_a_context_starts_with_no_r1():
    assert _context().r1 is None


def test_r1_is_the_sum_of_tier_1s_own_flags_and_not_of_the_whole_stream(monkeypatch):
    """A capture that failed stage 0 moves the eventual R, never R1."""
    _tier1(monkeypatch, _result())
    context = _context(flags=[_quality_flag()])

    tier1_stage.run_tier1(context)

    assert context.r1 == 0.0
    assert [flag.id for flag in context.flags] == [flag_ids.QUALITY_BLUR]


def test_r1_is_scored_against_the_weightset_the_caller_hands_over(monkeypatch):
    """The stage sums the table; it does not hold a number of its own."""
    heavy = _tier1_flag(flag_ids.OCR_MRZ_MISMATCH, "high")
    _tier1(monkeypatch, _result(heavy))
    weightset = load_weightset()
    context = _context()

    tier1_stage.run_tier1(context, weightset=weightset)

    assert context.r1 == _weight(flag_ids.OCR_MRZ_MISMATCH)


def test_a_page_no_engine_could_read_is_the_one_finding_this_runner_makes(monkeypatch):
    """D86's degraded read reaches the score rather than only the officer."""
    real_run = runner.run_tier1
    monkeypatch.setattr(
        tier1_stage.runner,
        "run_tier1",
        lambda image: real_run(image, engines={}),
    )
    context = _context()

    tier1_stage.run_tier1(context)

    assert [flag.id for flag in context.flags] == [flag_ids.OCR_LOW_CONFIDENCE]
    assert context.r1 == _weight(flag_ids.OCR_LOW_CONFIDENCE)


def test_tier_1_is_handed_the_contexts_frame(monkeypatch):
    asked: dict = {}

    def fake_run_tier1(image, **kwargs):
        asked["image"] = image
        asked.update(kwargs)
        return _result()

    monkeypatch.setattr(tier1_stage.runner, "run_tier1", fake_run_tier1)
    context = _context()

    tier1_stage.run_tier1(context)

    assert asked["image"] is context.image


def test_a_heavy_tier_1_finding_moves_the_score_and_stops_nothing(monkeypatch):
    """R1 is arithmetic: a high band is a weight, never an override."""
    heavy = _tier1_flag(flag_ids.OCR_MRZ_MISMATCH, "high")
    _tier1(monkeypatch, _result(heavy))
    context = _context()

    tier1_stage.run_tier1(context)

    assert context.r1 == _weight(flag_ids.OCR_MRZ_MISMATCH)
    assert context.hard_fail_reason is None


def test_the_shipped_registry_runs_the_capture_gate_then_tier_0_then_tier_1(
    monkeypatch,
):
    _gate(monkeypatch)
    _tier0(monkeypatch, tier0_runner.TierResult())
    _tier1(monkeypatch, _result())
    context = _context()

    response = orchestrator.run_cascade(context)

    assert response.ran == (
        quality.STAGE_NAME,
        tier0_stage.STAGE_NAME,
        tier1_stage.STAGE_NAME,
    )
    assert context.r1 == 0.0


def test_the_registry_holds_tier_1_under_the_name_the_stage_spells():
    assert tier1_stage.STAGE_NAME in orchestrator.STAGE_NAMES
    assert (
        orchestrator.resolve_stage(tier1_stage.STAGE_NAME)
        is tier1_stage.run_tier1
    )
