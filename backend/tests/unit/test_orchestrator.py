"""14.1 -- A context is constructible, and its two lists belong to one context.

The claim pinned here is the task's: the cascade's record can be built, and
what the caller stated comes back out of it unchanged.  What is checked at
construction, why the depth field is not called ``mode``, and what the trace
list does not yet promise are D104.
"""

import datetime
import uuid

import pytest

from app.pipeline import orchestrator
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag
from app.storage.models import SCREENING_MODES

ScreeningContext = orchestrator.ScreeningContext
DEPTH_MODES = orchestrator.DEPTH_MODES
STANDARD = orchestrator.STANDARD
FULL_DEPTH = orchestrator.FULL_DEPTH

#: The id the storage layer hands over, so the test builds one of those.
SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")

#: The injected day; no module in this task reads a clock for one.
REFERENCE_DATE = datetime.date(2026, 10, 2)

#: A frame standing in for the working one; nothing here reads its pixels.
PAGE = object()

#: One flag as a stage leaves it, so the append test moves a real one.
FLAG = EvidenceFlag(
    id=flag_ids.FACE_LOW_SIMILARITY,
    tier=1,
    label="The photograph and the live capture are below the threshold.",
    weight_band="high",
    value=1.0,
    confidence=0.9,
    region=None,
    expected="0.55",
    found="0.41",
    reason="the cosine between the two embeddings is 0.41",
    source_module="app.pipeline.tier1.face",
    field="photo",
)


def _context(**overrides):
    """A context carrying the constants above, with ``overrides`` applied."""
    stated = {
        "screening_id": SCREENING_ID,
        "document_type": "passport",
        "image": PAGE,
        "reference_date": REFERENCE_DATE,
        "depth_mode": STANDARD,
    }
    stated.update(overrides)
    return ScreeningContext(**stated)


def test_a_caller_can_construct_a_context():
    context = ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=PAGE,
        reference_date=REFERENCE_DATE,
        depth_mode=FULL_DEPTH,
    )

    assert context.screening_id == SCREENING_ID
    assert context.document_type == "passport"
    assert context.image is PAGE
    assert context.reference_date == REFERENCE_DATE
    assert context.depth_mode == FULL_DEPTH
    assert context.flags == []
    assert context.stage_trace == []


def test_a_stage_leaves_its_flag_on_the_context():
    context = _context()

    context.flags.append(FLAG)

    assert context.flags == [FLAG]


def test_two_contexts_do_not_share_one_list():
    first = _context()
    second = _context()

    first.flags.append(FLAG)
    first.stage_trace.append("tier_0")

    assert first.flags == [FLAG]
    assert first.stage_trace == ["tier_0"]
    assert second.flags == []
    assert second.stage_trace == []


def test_no_injected_day_is_a_legal_context():
    assert _context(reference_date=None).reference_date is None


def test_no_document_claim_is_a_legal_context():
    assert _context(document_type=None).document_type is None


@pytest.mark.parametrize(
    "screening_id", ["6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f", 7, None]
)
def test_a_screening_id_that_is_not_a_uuid_is_refused(screening_id):
    with pytest.raises(orchestrator.ContextValueError) as refusal:
        _context(screening_id=screening_id)

    assert "uuid.UUID" in str(refusal.value)


def test_the_refusal_names_the_type_and_not_the_id():
    written = "6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f"

    with pytest.raises(orchestrator.ContextValueError) as refusal:
        _context(screening_id=written)

    assert "str" in str(refusal.value)
    assert written not in str(refusal.value)


@pytest.mark.parametrize("depth_mode", ["deep", "full depth", "", None, 1])
def test_a_depth_mode_naming_nothing_known_is_refused(depth_mode):
    with pytest.raises(orchestrator.ContextValueError) as refusal:
        _context(depth_mode=depth_mode)

    assert "depth_mode" in str(refusal.value)


def test_a_refused_depth_mode_names_both_depths():
    with pytest.raises(orchestrator.ContextValueError) as refusal:
        _context(depth_mode="full depth")

    message = str(refusal.value)
    assert STANDARD in message
    assert FULL_DEPTH in message


def test_the_depths_are_the_two_named_and_not_the_capture_modes():
    assert DEPTH_MODES == (STANDARD, FULL_DEPTH)
    assert set(DEPTH_MODES) & set(SCREENING_MODES) == set()
