"""14.4 -- Tier 0 runs as a stage, and a hard fail ends the cascade.

The headline is the task's own verification: a hard fail in Tier 0 leaves
Tier 1 and Tier 2 unrun.  The rest pins what the stage writes onto the context
and that a clean page lets the later stages run, so what stops the cascade is
the hard fail and not a registry that happens to hold one stage.
"""

import datetime
import uuid

from app.pipeline import orchestrator, quality
from app.pipeline.tier0 import runner
from app.pipeline.tier0 import stage as tier0_stage
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")
REFERENCE_DATE = datetime.date(2026, 10, 2)

#: A frame standing in for the working one; the runner is stood in for here,
#: so nothing in this file reads its pixels.
PAGE = object()

#: The two stages a hard fail has to keep out, named as the tiers they are.
TIER_1 = "tier_1"
TIER_2 = "tier_2"

#: The sentence a composite check-digit failure is reported under, which is
#: the reason the runner hands back beside the flag it writes.
COMPOSITE_LABEL = "The MRZ composite check digit does not match."

STOLEN_LABEL = "The document number is recorded as a stolen document."


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


def _flag(flag_id, label):
    """One Tier 0 finding, in the shape the runner hands the cascade."""
    return EvidenceFlag(
        id=flag_id,
        tier=0,
        label=label,
        weight_band="high",
        value=1.0,
        confidence=1.0,
        region=None,
        expected=None,
        found="9",
        reason="the printed digit disagrees with the check digit beside it",
        source_module="app.pipeline.tier0.runner",
        field=None,
    )


def _tier0(monkeypatch, result):
    """Stand the Tier 0 runner in for this test, answering with ``result``."""
    monkeypatch.setattr(
        tier0_stage.runner, "run_tier0", lambda *args, **kwargs: result
    )


def _gate(monkeypatch):
    """Stand the capture gate in for this test, reporting a clean capture."""
    monkeypatch.setattr(
        quality.engine,
        "analyze_image",
        lambda image, requested_mode="auto": {"modules": []},
    )


def _spy(ran, name):
    """A stage that records having run under ``name`` and writes nothing."""

    def stage(context):
        ran.append(name)

    return stage


def _registry(ran):
    """The shipped cascade order, with stand-ins for the stages after tier 0."""
    return {
        quality.STAGE_NAME: quality.run_quality,
        tier0_stage.STAGE_NAME: tier0_stage.run_tier0,
        TIER_1: _spy(ran, TIER_1),
        TIER_2: _spy(ran, TIER_2),
    }


def _hard_fail_result():
    """The result a document with a broken composite digit comes back as."""
    flag = _flag(flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH, COMPOSITE_LABEL)
    return runner.TierResult(
        flags=(flag,), hard_failed=True, hard_fail_reason=COMPOSITE_LABEL
    )


def test_a_hard_fail_stops_the_cascade_and_tier_1_and_tier_2_never_ran(monkeypatch):
    _gate(monkeypatch)
    _tier0(monkeypatch, _hard_fail_result())
    ran: list[str] = []
    context = _context()

    response = orchestrator.run_cascade(context, stages=_registry(ran))

    assert ran == []
    assert response.ran == (quality.STAGE_NAME, tier0_stage.STAGE_NAME)
    assert context.hard_fail_reason == COMPOSITE_LABEL


def test_a_clean_tier_0_lets_tier_1_and_tier_2_run(monkeypatch):
    _gate(monkeypatch)
    _tier0(monkeypatch, runner.TierResult())
    ran: list[str] = []
    context = _context()

    response = orchestrator.run_cascade(context, stages=_registry(ran))

    assert ran == [TIER_1, TIER_2]
    assert response.ran == (
        quality.STAGE_NAME,
        tier0_stage.STAGE_NAME,
        TIER_1,
        TIER_2,
    )
    assert context.hard_fail_reason is None
    assert context.flags == []


def test_a_heavy_finding_that_is_not_a_hard_fail_does_not_stop_the_cascade(monkeypatch):
    _gate(monkeypatch)
    stolen = _flag(flag_ids.WATCHLIST_STOLEN_DOCUMENT, STOLEN_LABEL)
    _tier0(monkeypatch, runner.TierResult(flags=(stolen,)))
    ran: list[str] = []
    context = _context()

    orchestrator.run_cascade(context, stages=_registry(ran))

    assert ran == [TIER_1, TIER_2]
    assert context.hard_fail_reason is None
    assert context.flags == [stolen]


def test_tier_0_findings_land_on_the_context_in_the_runners_own_order(monkeypatch):
    _gate(monkeypatch)
    first = _flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, STOLEN_LABEL)
    second = _flag(flag_ids.MRZ_EXPIRY_CHECK_DIGIT_MISMATCH, COMPOSITE_LABEL)
    _tier0(monkeypatch, runner.TierResult(flags=(first, second)))
    context = _context()

    tier0_stage.run_tier0(context)

    assert context.flags == [first, second]


def test_the_shipped_registry_runs_the_capture_gate_then_tier_0_and_stops(monkeypatch):
    _gate(monkeypatch)
    _tier0(monkeypatch, _hard_fail_result())
    context = _context()

    response = orchestrator.run_cascade(context)

    assert response.ran == (quality.STAGE_NAME, tier0_stage.STAGE_NAME)
    assert context.hard_fail_reason == COMPOSITE_LABEL


def test_the_registry_holds_tier_0_and_the_capture_gate_runs_before_it():
    names = orchestrator.STAGE_NAMES

    assert tier0_stage.STAGE_NAME in names
    assert names.index(quality.STAGE_NAME) < names.index(tier0_stage.STAGE_NAME)
    assert (
        orchestrator.resolve_stage(tier0_stage.STAGE_NAME) is tier0_stage.run_tier0
    )


def test_tier_0_is_handed_the_contexts_frame_claim_and_injected_day(monkeypatch):
    asked: dict = {}

    def fake_run_tier0(image, **kwargs):
        asked["image"] = image
        asked.update(kwargs)
        return runner.TierResult()

    monkeypatch.setattr(tier0_stage.runner, "run_tier0", fake_run_tier0)
    context = _context()

    tier0_stage.run_tier0(context)

    assert asked["image"] is context.image
    assert asked["document_type"] == "passport"
    assert asked["reference_date"] == REFERENCE_DATE


def test_no_parse_and_no_watchlist_are_asked_because_the_context_carries_neither(monkeypatch):
    asked: dict = {}

    def fake_run_tier0(image, **kwargs):
        asked.update(kwargs)
        return runner.TierResult()

    monkeypatch.setattr(tier0_stage.runner, "run_tier0", fake_run_tier0)

    tier0_stage.run_tier0(_context())

    assert "parsed_document" not in asked
    assert "watchlist" not in asked


def test_a_context_starts_with_no_hard_fail():
    assert _context().hard_fail_reason is None


def test_a_registry_holding_no_stage_runs_nothing_and_answers_nothing():
    assert orchestrator.run_cascade(_context(), stages={}).ran == ()
