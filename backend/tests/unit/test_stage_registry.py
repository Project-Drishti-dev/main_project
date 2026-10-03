"""14.2 -- A stage name resolves to its callable, and a name none holds is refused.

The claim pinned here is the task's: the registry maps a stage name to the
callable that runs it, and a name it does not hold is a loud refusal naming
what is known rather than a silent ``None``.  Why the registry is read-only,
why the names are read off the registry, and why the shipped one holds the
capture gate alone are D105 and D106.
"""

import uuid

import pytest

from app.pipeline import orchestrator

STAGES = orchestrator.STAGES
STAGE_NAMES = orchestrator.STAGE_NAMES
UnknownStageError = orchestrator.UnknownStageError
resolve_stage = orchestrator.resolve_stage

#: The two names this test's own registry holds, in cascade order.
QUALITY = "quality"
TIER_0 = "tier_0"


def _quality_stage(context):
    """A stand-in for stage 0; what a stage does is not this task's claim."""
    context.stage_trace.append(QUALITY)


def _tier0_stage(context):
    """A second stand-in, so each name resolves to its own callable."""
    context.stage_trace.append(TIER_0)


def _registry():
    """A registry of the two stand-ins, in the order the cascade runs them."""
    return {QUALITY: _quality_stage, TIER_0: _tier0_stage}


def _context():
    """A context carrying what the stand-in stages need and nothing else."""
    return orchestrator.ScreeningContext(
        screening_id=uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f"),
        document_type="passport",
        image=object(),
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def test_a_registered_name_resolves_to_its_own_callable():
    stages = _registry()

    assert resolve_stage(QUALITY, stages=stages) is _quality_stage
    assert resolve_stage(TIER_0, stages=stages) is _tier0_stage


def test_a_caller_can_run_the_stage_the_name_names():
    context = _context()

    resolve_stage(TIER_0, stages=_registry())(context)

    assert context.stage_trace == [TIER_0]


def test_the_shipped_registry_is_the_one_a_bare_call_reads():
    """14.3 gave the shipped registry its first stage, 14.4 and 14.5 the rest.

    So a bare call answers for the name the shipped one holds -- with the real
    stage and not this file's stand-in -- and still refuses a name it does not.
    """
    assert resolve_stage(QUALITY) is not _quality_stage

    with pytest.raises(UnknownStageError):
        resolve_stage("tier_2")


@pytest.mark.parametrize(
    "name", ["tier_2", "quality_gate", "Tier_0", "tier_0 ", "tier-0", "", "  "]
)
def test_a_stage_name_nobody_wrote_is_refused(name):
    with pytest.raises(UnknownStageError):
        resolve_stage(name, stages=_registry())


@pytest.mark.parametrize("name", [None, 7, b"quality", ["quality"], object()])
def test_a_name_that_is_not_a_string_is_refused(name):
    with pytest.raises(UnknownStageError):
        resolve_stage(name, stages=_registry())


def test_the_refusal_names_the_stages_this_call_does_know():
    with pytest.raises(UnknownStageError) as refusal:
        resolve_stage("tier_2", stages=_registry())

    message = str(refusal.value)
    assert QUALITY in message
    assert TIER_0 in message


def test_the_refusal_echoes_the_name_it_refused():
    with pytest.raises(UnknownStageError) as refusal:
        resolve_stage("tier_2", stages=_registry())

    assert "tier_2" in str(refusal.value)


def test_a_registry_holding_no_stage_still_refuses_readably():
    with pytest.raises(UnknownStageError) as refusal:
        resolve_stage(QUALITY, stages={})

    assert "none registered" in str(refusal.value)


def test_the_refusal_is_a_value_error():
    assert issubclass(UnknownStageError, ValueError)


def test_the_shipped_registry_is_read_only():
    with pytest.raises(TypeError):
        STAGES[QUALITY] = _quality_stage


def test_every_registered_name_has_a_callable():
    assert all(callable(stage) for stage in STAGES.values())


def test_the_names_read_off_the_registry_are_the_ones_it_holds():
    assert STAGE_NAMES == tuple(STAGES)
