"""14.3 -- The capture gate runs as stage 0, and its failures are the flags.

The headline is the task's own verification: a blurred image produces a
quality flag.  The rest is what makes that one flag trustworthy -- a check that
passed and one that does not apply write nothing, one that failed writes one
finding and no merged summary, and a check that could not run is reported
rather than dropped.  Why the ids, the tier and the weight are what they are is
D106; why the registry is read-only is D105.
"""

import datetime
import uuid

import cv2
import pytest

from app.pipeline import orchestrator, quality
from app.quality_checker import engine
from app.risk import flag_ids
from app.risk.config import LOW_MAX
from app.risk.flags import EvidenceFlag
from app.risk.weightsets.loader import load_weightset
from app.risk.weightsets.lookup import weight_for
from tests.fixtures import document_images

SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")
REFERENCE_DATE = datetime.date(2026, 10, 2)

#: How far past its own floor the sharpness check is pushed by the blur below,
#: well past the variance a printed page scores.
BLUR_SIGMA = 9


def _page():
    """A printed page, the fixture's own specimen at its own size."""
    return document_images.render_document().image


def _blurred(sigma=BLUR_SIGMA):
    """:func:`_page` with the edges taken off it."""
    return cv2.GaussianBlur(_page(), (0, 0), sigma)


def _context(image):
    """A context carrying ``image`` and nothing else a stage has to be handed."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=REFERENCE_DATE,
        depth_mode=orchestrator.STANDARD,
    )


def _result(label, passed, score=None, reasons=()):
    """One result in the shape the gate writes, for a stand-in report."""
    return {
        "module": label.lower().split(" ")[0],
        "label": label,
        "score": score,
        "unit": "",
        "passed": passed,
        "mode": "photo",
        "rule": "",
        "reasons": list(reasons),
        "details": {},
    }


def _gate(monkeypatch, *results):
    """Stand the gate in for this test, answering with ``results`` and nothing else."""
    monkeypatch.setattr(
        engine,
        "analyze_image",
        lambda image, requested_mode="auto": {
            "mode": "photo",
            "image": {"width": 0, "height": 0},
            "trim_box": None,
            "overall_pass": all(r["passed"] is not False for r in results),
            "modules": list(results),
        },
    )


def _earlier_finding():
    """One tier-0 finding, so a test can ask what stage 0 did to what it found."""
    return EvidenceFlag(
        id=flag_ids.DATE_EXPIRED,
        tier=0,
        label="The document has expired.",
        weight_band="high",
        value=1.0,
        confidence=1.0,
        region=None,
        expected="2026-10-02",
        found="2012-04-15",
        reason="the document was valid until 2012-04-15",
        source_module="app.pipeline.tier0.dates",
        field="date_of_expiry",
    )


def _flag_ids(context):
    """The ids the context's flag stream holds, in the order they were written."""
    return [flag.id for flag in context.flags]


# --- the task's own verification, against the real gate and a real blur ---


def test_a_blurred_image_produces_a_quality_flag():
    context = _context(_blurred())

    quality.run_quality(context)

    assert flag_ids.QUALITY_BLUR in _flag_ids(context)
    assert context.flags[0].tier == quality.QUALITY_TIER


def test_the_same_page_sharp_produces_no_blur_flag():
    """The paired negative: the blur is what the finding is about."""
    context = _context(_page())

    quality.run_quality(context)

    assert flag_ids.QUALITY_BLUR not in _flag_ids(context)


def test_a_blurred_image_is_flagged_by_the_stage_the_registry_names():
    context = _context(_blurred())

    orchestrator.resolve_stage(quality.STAGE_NAME)(context)

    assert flag_ids.QUALITY_BLUR in _flag_ids(context)


# --- what reaches the stream, and what does not ---


@pytest.mark.parametrize(
    ("passed", "why"),
    [
        (True, "a check that passed"),
        (None, "a check that does not apply to this capture"),
    ],
    ids=["passed", "not-applicable"],
)
def test_only_a_failed_check_reaches_the_stream(monkeypatch, passed, why):
    _gate(monkeypatch, _result("Glare", passed, reasons=["glare_total_high"]))
    context = _context(_page())

    quality.run_quality(context)

    assert context.flags == []


def test_one_flag_is_written_per_failed_check_in_the_gate_own_order(monkeypatch):
    _gate(
        monkeypatch,
        _result("Sharpness", False, score=12.5, reasons=["blurry"]),
        _result("Exposure", True, score=180.0),
        _result("Card coverage", False, score=0.04, reasons=["card_too_small"]),
    )
    context = _context(_page())

    quality.run_quality(context)

    assert _flag_ids(context) == [
        flag_ids.QUALITY_BLUR,
        flag_ids.QUALITY_LOW_COVERAGE,
    ]


def test_the_stage_appends_to_the_flags_already_found(monkeypatch):
    """The context is the run's one record, so stage 0 joins what is there."""
    _gate(monkeypatch, _result("Sharpness", False, score=1.0, reasons=["blurry"]))
    context = _context(_page())
    context.flags.append(_earlier_finding())

    quality.run_quality(context)

    assert _flag_ids(context) == [flag_ids.DATE_EXPIRED, flag_ids.QUALITY_BLUR]


def test_the_stage_writes_nothing_but_the_flags(monkeypatch):
    _gate(monkeypatch, _result("Sharpness", False, score=1.0, reasons=["blurry"]))
    context = _context(_page())
    before = (context.screening_id, context.document_type, context.image)

    quality.run_quality(context)

    assert (context.screening_id, context.document_type, context.image) == before
    assert context.stage_trace == []


def test_the_stage_answers_nothing_and_takes_the_context(monkeypatch):
    _gate(monkeypatch, _result("Sharpness", False, reasons=["blurry"]))

    assert quality.run_quality(_context(_page())) is None


# --- what one flag says ---


@pytest.mark.parametrize(
    "label", sorted(quality.CHECKS), ids=sorted(quality.CHECKS)
)
def test_every_check_the_gate_runs_becomes_a_flag_of_its_own(monkeypatch, label):
    _gate(monkeypatch, _result(label, False, score=1.0, reasons=["failed"]))
    context = _context(_page())

    quality.run_quality(context)

    assert len(context.flags) == 1
    assert context.flags[0].id == quality.CHECKS[label].flag_id
    assert context.flags[0].label == quality.CHECKS[label].label


def test_a_flag_the_stage_writes_is_a_quality_finding(monkeypatch):
    _gate(monkeypatch, _result("Sharpness", False, score=1.0, reasons=["blurry"]))
    context = _context(_page())

    quality.run_quality(context)

    flag = context.flags[0]
    assert flag.tier == quality.QUALITY_TIER
    assert flag.weight_band == quality.QUALITY_BAND
    assert flag.value == 1.0
    assert flag.confidence == 1.0
    assert flag.field is None
    assert flag.region is None


def test_a_flag_names_the_module_that_measured_it(monkeypatch):
    _gate(monkeypatch, _result("Sharpness", False, score=1.0, reasons=["blurry"]))
    context = _context(_page())
    measured = {label: module.__name__ for module, label in engine.MODULES}

    quality.run_quality(context)

    assert context.flags[0].source_module == measured["Sharpness"]


def test_a_flag_carries_the_number_the_gate_printed(monkeypatch):
    _gate(monkeypatch, _result("Sharpness", False, score=12.5, reasons=["blurry"]))
    context = _context(_page())

    quality.run_quality(context)

    assert context.flags[0].found == "12.5"
    assert context.flags[0].reason == "blurry"


def test_a_check_that_measured_nothing_carries_no_number(monkeypatch):
    """The resolution check on a page it found no text on: a failure with no score."""
    _gate(
        monkeypatch,
        _result("Resolution (PPI)", False, score=None, reasons=["too_little_text_found"]),
    )
    context = _context(_page())

    quality.run_quality(context)

    assert context.flags[0].found is None
    assert context.flags[0].reason == "too_little_text_found"


def test_a_check_that_named_no_reason_says_so(monkeypatch):
    _gate(monkeypatch, _result("Sharpness", False, score=1.0, reasons=[]))
    context = _context(_page())

    quality.run_quality(context)

    assert context.flags[0].reason == quality.NO_REASON


def test_several_reasons_are_carried_as_the_check_printed_them(monkeypatch):
    _gate(
        monkeypatch,
        _result("Glare", False, score=0.4, reasons=["glare_total_high", "glare_blob_large"]),
    )
    context = _context(_page())

    quality.run_quality(context)

    assert context.flags[0].reason == "glare_total_high, glare_blob_large"


def test_a_check_that_raised_is_reported_and_not_dropped(monkeypatch):
    """A module that cannot answer is a check the gate did not clear, and says so."""

    class Broken:
        __name__ = "app.quality_checker.broken_check"

        @staticmethod
        def assess(_image, mode="photo"):
            raise RuntimeError("internal detail that must not reach a flag")

    monkeypatch.setattr(engine, "MODULES", ((Broken, "Sharpness"),))
    context = _context(_page())

    quality.run_quality(context)

    assert _flag_ids(context) == [flag_ids.QUALITY_BLUR]
    assert context.flags[0].reason == "module_error"
    assert context.flags[0].found is None


def test_a_check_this_stage_holds_no_finding_for_is_refused(monkeypatch):
    """A tenth check with no id would otherwise drop out of the record silently."""
    _gate(monkeypatch, _result("A check nobody wrote down", False, score=1.0))
    context = _context(_page())

    with pytest.raises(quality.UnknownCheckError) as refusal:
        quality.run_quality(context)

    assert "A check nobody wrote down" in str(refusal.value)
    assert context.flags == []


def test_the_refusal_is_a_value_error():
    assert issubclass(quality.UnknownCheckError, ValueError)


# --- the table, the registry, and the weightset ---


def test_the_table_holds_exactly_the_checks_the_gate_runs():
    """One check, one id: a tenth module fails here rather than in a screening."""
    assert set(quality.CHECKS) == {label for _, label in engine.MODULES}


def test_every_id_the_table_holds_is_in_the_vocabulary():
    """Nine checks, nine distinct ids -- and every one of them legal to emit."""
    held = {check.flag_id for check in quality.CHECKS.values()}

    assert len(held) == len(quality.CHECKS)
    assert held <= set(flag_ids.FLAG_IDS)
    assert all(flag_id.startswith("QUALITY_") for flag_id in held)


def test_every_id_the_table_holds_is_weighed_by_the_shipped_weightset():
    """7.1's completeness claim, for this tier: no id reaches the engine unweighted."""
    weightset = load_weightset()

    for check in quality.CHECKS.values():
        weight = weight_for(weightset, check.flag_id)
        assert 0 < weight <= LOW_MAX


def test_the_shipped_registry_holds_this_stage_under_its_own_name():
    assert orchestrator.resolve_stage(quality.STAGE_NAME) is quality.run_quality
    assert orchestrator.STAGE_NAMES[0] == quality.STAGE_NAME


def test_the_registry_still_reads_only_the_names_it_holds():
    with pytest.raises(orchestrator.UnknownStageError):
        orchestrator.resolve_stage("tier_2")
