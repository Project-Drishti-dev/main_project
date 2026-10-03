"""14.10 -- Every stage that ran leaves one trace row, and the call returns it.

The claim pinned here is the verification the task names: a run that reached the
deep analysis tier traces Tier 0, then Tier 1, then Tier 2, in that order and
in no other.  The rest pins what a row holds, that the rows on the context are
the ones returned, and that the clock defaults to the monotonic one; why the
row is frozen and why the answer carries the names as well as the rows is
D113.  The last block is 14.11: a stage that raises is traced as failed and
the stages after it still run, which is D114.
"""

import dataclasses
import inspect
import time
import uuid

import pytest

from app.pipeline import orchestrator
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

StageTrace = orchestrator.StageTrace
CascadeResponse = orchestrator.CascadeResponse
STAGE_NAMES = orchestrator.STAGE_NAMES

SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")

#: The three tiers the abstract runs in cascade order, spelled as the registry
#: spells the two of them 14.4 and 14.5 already hold.
TIER_0 = "tier_0"
TIER_1 = "tier_1"
TIER_2 = "tier_2"

#: The sentence 14.8 appends, stood in for by a stage here.
ESCALATION = "Drawn for a random deep audit at a rate of 0.1."

#: The sentence a stand-in stage writes as the cascade stop signal.
STOP = "The MRZ composite check digit does not match."

#: What a broken stage raises, standing in for a module that cannot answer.
BROKEN = "the encoder returned no direction"


def _context():
    """A context carrying what the stand-in stages need and nothing else."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=object(),
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _flag(flag_id, tier=1):
    """One finding, so a stage under test leaves a real one on the context."""
    return EvidenceFlag(
        id=flag_id,
        tier=tier,
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


def _stage(*, flags=(), escalation=None, stop=None):
    """A stand-in stage leaving findings, a reason, or the stop signal."""

    def stage(context):
        context.flags.extend(flags)
        if escalation is not None:
            context.escalations.append(escalation)
        if stop is not None:
            context.hard_fail_reason = stop

    return stage


def _broken(*, flags=()):
    """A stand-in stage that leaves what it can and then raises."""

    def stage(context):
        context.flags.extend(flags)
        raise RuntimeError(BROKEN)

    return stage


def _stages(order):
    """A registry holding one empty stand-in per name, in the order given."""
    return {name: _stage() for name in order}


def _clock(step=0.5):
    """A clock reading zero first and rising by `step` on every call."""
    state = {"now": 0.0}

    def read():
        value = state["now"]
        state["now"] += step
        return value

    return read


def test_the_trace_reads_tier_0_then_tier_1_then_tier_2():
    """The verification the task names: the three tiers, in cascade order."""
    context = _context()

    orchestrator.run_cascade(context, stages=_stages([TIER_0, TIER_1, TIER_2]))

    assert [row.stage for row in context.stage_trace] == [
        TIER_0,
        TIER_1,
        TIER_2,
    ]


def test_the_answer_carries_the_same_three_stages_in_the_same_order():
    context = _context()

    response = orchestrator.run_cascade(
        context, stages=_stages([TIER_0, TIER_1, TIER_2])
    )

    assert response.ran == (TIER_0, TIER_1, TIER_2)
    assert tuple(row.stage for row in response.trace) == response.ran


def test_the_rows_on_the_context_are_the_ones_returned():
    context = _context()

    response = orchestrator.run_cascade(context, stages=_stages([TIER_0, TIER_1]))

    assert tuple(context.stage_trace) == response.trace
    assert all(
        row is context.stage_trace[index]
        for index, row in enumerate(response.trace)
    )


def test_the_shipped_cascade_traces_the_gate_before_tier_0_and_tier_1():
    context = _context()

    response = orchestrator.run_cascade(context, stages=_stages(STAGE_NAMES))

    assert tuple(row.stage for row in context.stage_trace) == STAGE_NAMES
    assert response.ran == STAGE_NAMES
    assert STAGE_NAMES.index("quality") < STAGE_NAMES.index(TIER_0)
    assert STAGE_NAMES.index(TIER_0) < STAGE_NAMES.index(TIER_1)


def test_a_stage_is_named_by_the_registry_and_not_by_its_callable():
    context = _context()

    response = orchestrator.run_cascade(context, stages={"renamed": _stage()})

    assert response.trace[0].stage == "renamed"


def test_a_row_holds_the_six_fields_the_task_names():
    fields = tuple(field.name for field in dataclasses.fields(StageTrace))

    assert fields == (
        "stage",
        "started",
        "elapsed",
        "flags_added",
        "escalated",
        "failed",
    )


def test_a_stage_that_finds_nothing_records_no_flags():
    context = _context()

    orchestrator.run_cascade(context, stages=_stages([TIER_0]))

    assert context.stage_trace[0].flags_added == 0
    assert context.flags == []


def test_each_stage_counts_only_the_findings_it_left_itself():
    first = _flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, tier=0)
    second = _flag(flag_ids.WATCHLIST_STOLEN_DOCUMENT, tier=0)
    third = _flag(flag_ids.OCR_MRZ_MISMATCH)
    context = _context()

    orchestrator.run_cascade(
        context,
        stages={
            TIER_0: _stage(flags=(first, second)),
            TIER_1: _stage(flags=(third,)),
            TIER_2: _stage(),
        },
    )

    assert [row.flags_added for row in context.stage_trace] == [2, 1, 0]
    assert len(context.flags) == 3


def test_a_stage_is_timed_from_the_reading_taken_before_it_ran():
    context = _context()

    orchestrator.run_cascade(
        context, stages=_stages([TIER_0, TIER_1, TIER_2]), clock=_clock(0.5)
    )

    assert [row.started for row in context.stage_trace] == [0.0, 1.0, 2.0]
    assert [row.elapsed for row in context.stage_trace] == [0.5, 0.5, 0.5]


def test_elapsed_is_never_negative_under_the_shipped_clock():
    context = _context()

    response = orchestrator.run_cascade(
        context, stages=_stages([TIER_0, TIER_1, TIER_2])
    )

    assert [row.elapsed >= 0.0 for row in response.trace] == [True, True, True]


def test_started_reads_forward_along_the_trace():
    context = _context()

    orchestrator.run_cascade(context, stages=_stages([TIER_0, TIER_1, TIER_2]))

    starts = [row.started for row in context.stage_trace]
    assert starts == sorted(starts)
    assert len(set(starts)) == 3


def test_the_clock_defaults_to_the_monotonic_perf_counter():
    parameter = inspect.signature(orchestrator.run_cascade).parameters["clock"]

    assert parameter.default is time.perf_counter


def test_escalated_is_read_off_the_reasons_when_the_row_is_written():
    context = _context()

    orchestrator.run_cascade(
        context,
        stages={
            TIER_0: _stage(),
            TIER_1: _stage(escalation=ESCALATION),
            TIER_2: _stage(),
        },
    )

    assert [row.escalated for row in context.stage_trace] == [False, True, True]
    assert context.escalated is True


def test_a_run_that_escalated_nothing_records_false_on_every_row():
    context = _context()

    orchestrator.run_cascade(context, stages=_stages([TIER_0, TIER_1]))

    assert [row.escalated for row in context.stage_trace] == [False, False]


def test_a_hard_fail_leaves_the_trace_short():
    context = _context()

    response = orchestrator.run_cascade(
        context,
        stages={TIER_0: _stage(stop=STOP), TIER_1: _stage(), TIER_2: _stage()},
    )

    assert tuple(row.stage for row in context.stage_trace) == (TIER_0,)
    assert response.ran == (TIER_0,)


def test_the_stage_that_stopped_the_cascade_is_traced_with_what_it_found():
    found = _flag(flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH, tier=0)
    context = _context()

    response = orchestrator.run_cascade(
        context, stages={TIER_0: _stage(flags=(found,), stop=STOP)}
    )

    assert response.trace[0].stage == TIER_0
    assert response.trace[0].flags_added == 1
    assert context.hard_fail_reason == STOP


def test_an_empty_registry_answers_an_empty_trace():
    context = _context()

    response = orchestrator.run_cascade(context, stages={})

    assert response.ran == ()
    assert response.trace == ()
    assert context.stage_trace == []


def test_a_row_is_frozen():
    row = StageTrace(TIER_0, 0.0, 0.0, 0, False, False)

    with pytest.raises(dataclasses.FrozenInstanceError):
        row.stage = TIER_1


def test_the_answer_is_frozen():
    response = CascadeResponse((), ())

    with pytest.raises(dataclasses.FrozenInstanceError):
        response.ran = (TIER_0,)


# --- 14.11 -- one broken stage costs its own row and nothing else ---


def test_a_stage_that_raised_is_traced_as_failed():
    """The verification the task names: the broken row says failed."""
    context = _context()

    orchestrator.run_cascade(context, stages={TIER_0: _broken()})

    assert context.stage_trace[0].stage == TIER_0
    assert context.stage_trace[0].failed is True


def test_a_stage_that_raised_does_not_abort_the_stages_after_it():
    """The other half of the claim: the remaining modules still run."""
    context = _context()

    response = orchestrator.run_cascade(
        context, stages={TIER_0: _stage(), TIER_1: _broken(), TIER_2: _stage()}
    )

    assert response.ran == (TIER_0, TIER_1, TIER_2)
    assert [row.stage for row in context.stage_trace] == [TIER_0, TIER_1, TIER_2]


def test_a_broken_stage_leaves_only_its_own_row_marked():
    context = _context()

    orchestrator.run_cascade(
        context, stages={TIER_0: _broken(), TIER_1: _stage(), TIER_2: _stage()}
    )

    assert [row.failed for row in context.stage_trace] == [True, False, False]


def test_a_stage_that_ran_records_no_failure():
    context = _context()

    orchestrator.run_cascade(context, stages=_stages([TIER_0, TIER_1]))

    assert [row.failed for row in context.stage_trace] == [False, False]


def test_a_broken_stage_is_still_named_by_the_registry_and_not_its_callable():
    context = _context()

    response = orchestrator.run_cascade(context, stages={"renamed": _broken()})

    assert response.trace[0].stage == "renamed"
    assert response.ran == ("renamed",)


def test_the_cascade_does_not_raise_the_broken_stages_exception():
    """The caller hears nothing: a broken check is a row, not a crash."""
    context = _context()

    response = orchestrator.run_cascade(
        context, stages={TIER_0: _broken(), TIER_1: _stage()}
    )

    assert tuple(row.stage for row in response.trace) == (TIER_0, TIER_1)


def test_the_trace_records_that_a_stage_failed_and_not_the_words_it_failed_with():
    context = _context()

    orchestrator.run_cascade(context, stages={TIER_0: _broken()})

    assert BROKEN not in repr(context.stage_trace)


def test_what_a_broken_stage_managed_to_leave_before_it_broke_still_counts():
    """A finding written before the raise is a finding, not a casualty."""
    found = _flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, tier=0)
    context = _context()

    orchestrator.run_cascade(
        context, stages={TIER_0: _broken(flags=(found,)), TIER_1: _stage()}
    )

    assert context.stage_trace[0].flags_added == 1
    assert context.flags == [found]


def test_a_broken_stage_is_still_timed_to_the_moment_it_broke():
    context = _context()

    orchestrator.run_cascade(
        context,
        stages={TIER_0: _broken(), TIER_1: _stage(), TIER_2: _stage()},
        clock=_clock(0.5),
    )

    assert [row.elapsed for row in context.stage_trace] == [0.5, 0.5, 0.5]


def test_a_stage_that_raised_and_stopped_the_cascade_is_traced_as_both():
    """A hard fail is the one stop (D107) and isolation does not override it."""

    def stops_then_breaks(context):
        context.hard_fail_reason = STOP
        raise RuntimeError(BROKEN)

    context = _context()

    response = orchestrator.run_cascade(
        context, stages={TIER_0: stops_then_breaks, TIER_1: _stage()}
    )

    assert response.ran == (TIER_0,)
    assert context.stage_trace[0].failed is True
    assert context.hard_fail_reason == STOP


def test_two_broken_stages_are_both_traced_and_the_last_still_runs():
    context = _context()

    response = orchestrator.run_cascade(
        context,
        stages={TIER_0: _broken(), TIER_1: _broken(), TIER_2: _stage()},
    )

    assert [row.failed for row in response.trace] == [True, True, False]
    assert response.ran == (TIER_0, TIER_1, TIER_2)


def test_a_broken_stage_does_not_stop_a_stage_that_escalates_after_it():
    context = _context()

    orchestrator.run_cascade(
        context,
        stages={TIER_0: _broken(), TIER_1: _stage(escalation=ESCALATION)},
    )

    assert [row.escalated for row in context.stage_trace] == [False, True]


def test_the_last_stage_raising_does_not_cost_the_rows_before_it():
    context = _context()

    response = orchestrator.run_cascade(
        context, stages={TIER_0: _stage(), TIER_1: _stage(), TIER_2: _broken()}
    )

    assert [row.failed for row in response.trace] == [False, False, True]


def test_a_registry_of_nothing_but_broken_stages_runs_every_one_of_them():
    context = _context()

    response = orchestrator.run_cascade(
        context, stages={TIER_0: _broken(), TIER_1: _broken()}
    )

    assert response.ran == (TIER_0, TIER_1)
    assert all(row.failed for row in response.trace)


def test_a_shipped_stage_name_can_be_registered_broken_and_the_cascade_goes_on():
    """The isolation is the shipped cascade, not only a stand-in registry."""

    def broken(context):
        raise RuntimeError(BROKEN)

    names = list(STAGE_NAMES)
    registry = {name: _stage() for name in names}
    registry[names[-1]] = broken
    context = _context()

    response = orchestrator.run_cascade(context, stages=registry)

    assert response.ran == tuple(names)
    assert response.trace[-1].failed is True


def test_two_contexts_do_not_share_one_trace():
    first = _context()
    second = _context()

    orchestrator.run_cascade(first, stages=_stages([TIER_0]))

    assert len(first.stage_trace) == 1
    assert second.stage_trace == []
