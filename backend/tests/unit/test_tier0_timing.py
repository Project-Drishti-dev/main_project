"""6.6 -- what the run took: four named durations, measured and read-only.

`tasks.md` asks for per-stage timing on
:class:`~app.pipeline.tier0.runner.TierResult` so that a later task can show
"Tier 0 took 0.11 s" against the abstract's sub-0.3 s target, and its verify
is that a test asserts the timing keys exist and are non-negative.  That is
the first test below; the rest are the claims that make the number worth
anything.

**A duration is measured inside the run and not asked of the caller.**  A
caller timing the call from outside measures the HTTP boundary, the queue it
waited in and the response it has not written yet, so the figure on the
record and the figure against the abstract's target would be two different
numbers wearing one name.  The four keys are the three things the runner does
-- Part 4's chain, 6.2's digits, 6.4's lists -- and the total spanning them.

**The names are read out of the runner rather than typed here**, with one
deliberate exception: :func:`test_the_vocabulary_is_the_one_the_task_names`
pins :data:`~app.pipeline.tier0.runner.STAGE_NAMES` itself, because that
constant is the public contract every consumer of these numbers is written
against, and a renamed stage should be a failing test rather than a missing
key on a screen.
"""

import ast
import datetime
import inspect
import math
import numbers
import pathlib
import types

import numpy as np
import pytest

from app.pipeline.tier0 import document, runner
from app.pipeline.tier0.mrz import MrzValueError
from app.risk import watchlist as watchlist_seam
from tests.fixtures import mrz_images

run_tier0 = runner.run_tier0
TierResult = runner.TierResult
STAGE_NAMES = runner.STAGE_NAMES

#: The three stages, named as a consumer names them -- never by position.
STAGES = ("check_digits", "detection", "watchlist")

#: The one the abstract bounds, and the one a later task puts on a screen.
TOTAL = "total"

#: The reference 6.4 hands to 5.6 so a list is asked about a resolved day
#: rather than six printed characters.  6.6 reads no day; the value is here so
#: a run that asks a list can be timed as well as one that does not.
REFERENCE = datetime.date(2026, 9, 30)

#: A page carrying print that is not a machine-readable zone: one short line
#: of ordinary text, which is what a page with no MRZ on it looks like.
NO_ZONE_PAGE = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))


class SilentList(watchlist_seam.Watchlist):
    """A list that is asked and answers no hits.

    **A stub rather than 5.11's mock**, because 6.6 is about how long the
    watchlist stage took and not about what a list says -- 6.4's own file
    holds what a hit becomes.  What this does hold is that the stage really
    ran: a parse and a reference were handed in, so all three keys should
    have carried a value, and a runner that stopped asking would fail here
    rather than quietly time a stage it skipped.
    """

    def lookup(self, *, document_number, name, dob):
        """Answer no hits, having been asked about all three keys."""
        assert document_number and name and dob, (
            "a parse and a reference were handed in, so all three keys "
            "should have carried a value"
        )
        return []


def parsed_page(name="TD3"):
    """A drawn page and the parse a caller would hand in beside it.

    **The zone is read back off the pixels before it is parsed**, so the
    document under test is the one the frame holds rather than one this file
    typed -- the discipline 6.2's and 6.4's own suites follow.
    """
    page = mrz_images.render_format(name)
    read = mrz_images.read_zone(page)
    assert read == tuple(mrz_images.SPECIMENS[name])
    return page, document.parse_mrz(read)


# --- the named behaviour: keys that exist, and are not negative ------------


def test_the_timing_keys_exist_and_are_not_negative():
    """6.6's own verify, over a real page and a real chain behind it."""
    page, parsed = parsed_page()

    result = run_tier0(page.image, parsed_document=parsed)

    assert set(result.stage_timings) == set(STAGE_NAMES)
    for stage, seconds in result.stage_timings.items():
        assert isinstance(seconds, numbers.Real), stage
        assert seconds >= 0, f"the {stage} stage reported a negative duration"


def test_the_vocabulary_is_the_one_the_task_names():
    """The public contract, pinned so that renaming a stage fails here.

    **Every other name in this file is read out of the runner.**  This is the
    one place the four are written longhand, and it has to be: the task that
    shows "Tier 0 took 0.11 s" is written against these four words, so
    changing one of them has to break something rather than reach a screen as
    a key nobody holds.
    """
    assert set(STAGE_NAMES) == {
        "detection",
        "check_digits",
        "watchlist",
        "total",
    }
    assert isinstance(STAGE_NAMES, frozenset)
    assert "STAGE_NAMES" in runner.__all__


def test_the_key_set_does_not_move_with_the_page_or_with_what_was_wired_in():
    """Four arrivals, and the same four keys on every one of them.

    **A vocabulary that appeared and disappeared with the work would leave
    every consumer guarding its own lookup**, which is the one thing a fixed
    set exists to prevent.  A zone with a parse and a list wired exercises
    all three stages; the same page with neither skips two of them; a page of
    ordinary text measures ink and names no format; and the blank frame is
    the case 6.1 made a value rather than a refusal, so it is timed too.
    """
    page, parsed = parsed_page()

    runs = [
        run_tier0(
            page.image,
            parsed_document=parsed,
            watchlist=SilentList(),
            reference_date=REFERENCE,
        ),
        run_tier0(page.image),
        run_tier0(NO_ZONE_PAGE.image),
        run_tier0(np.full((120, 320, 3), 255, np.uint8)),
    ]

    for result in runs:
        assert set(result.stage_timings) == set(STAGE_NAMES)
        assert all(seconds >= 0 for seconds in result.stage_timings.values())


def test_a_stage_with_nothing_to_do_still_carries_its_key():
    """No parse means no digits were asked for, and the row is still there.

    **The number is not asserted to be zero, because it is not.**  The stage
    is a conditional that returns at once, and
    :func:`time.perf_counter` resolves to roughly a hundred nanoseconds on
    Windows, so the difference over an empty call is a small positive float
    on most runs and ``0.0`` on the ones where nothing was counted.  A test
    pinning ``0.0`` would be asserting the counter's granularity rather than
    this module's behaviour, and one pinning "small" would be asserting this
    machine's.  **What is worth holding is the key**: a stage that had no
    work is a row a consumer can draw, where a missing key is a lookup to
    guard before every read.

    **That the stage is timed at all rather than skipped** is the AST walk's
    claim in :func:`test_each_stage_is_timed_where_the_cascade_calls_it`:
    every write into the timings is a subtraction written in
    :func:`run_tier0` around the call, so there is no branch that could time
    a stage only when it had something to report.
    """
    page, parsed = parsed_page()

    bare = run_tier0(page.image)
    full = run_tier0(page.image, parsed_document=parsed)

    assert set(bare.stage_timings) == set(full.stage_timings) == set(STAGE_NAMES)
    assert bare.stage_timings["check_digits"] >= 0
    assert bare.stage_timings["watchlist"] >= 0
    # The one stage that always does work is timed on this page too, so the
    # two runs are not both reading zeros off a counter that was never
    # started.
    assert bare.stage_timings["detection"] > 0


def test_a_stage_that_did_work_reports_a_positive_number_of_seconds():
    """The other direction, and the reason the non-negative test is not enough.

    **A stopwatch wired to always answer ``0.0`` passes 6.6's verify.**  So
    the chain's own stage is held to being positive on a page with real ink
    in it: Part 4 runs a deskew, a cut and eight connected-component passes
    over a 912-pixel-wide frame, and no counter that reads twice could make
    that take nothing.  **The size is not asserted** -- a test saying "under
    0.3 s" would be a claim about this machine's OpenCV build rather than
    about the record, and the abstract's target is a later task's to measure.
    """
    page = mrz_images.render_format("TD3")

    result = run_tier0(page.image)

    assert result.stage_timings["detection"] > 0
    assert result.stage_timings[TOTAL] > 0


# --- the total is a measurement and not an addition ------------------------


def test_the_total_spans_every_stage_and_is_not_their_sum():
    """The abstract bounds the whole of Tier 0, so the whole is what is timed.

    **Two claims, and they are different.**  The total is at least each stage
    -- it was opened before the first and closed after the last, on a
    monotonic counter, so it cannot be less than anything inside it.  And it
    is *rather more* than the three added up, because the seam's refusals and
    the assembly sit outside the stages: a caller that summed the stages to
    draw the figure would under-report it, and under-reporting is the
    direction that lets a regression past the abstract's target look like a
    pass.
    """
    page, parsed = parsed_page()

    timings = run_tier0(
        page.image,
        parsed_document=parsed,
        watchlist=SilentList(),
        reference_date=REFERENCE,
    ).stage_timings

    assert all(timings[stage] <= timings[TOTAL] for stage in STAGES)
    assert sum(timings[stage] for stage in STAGES) <= timings[TOTAL]


def test_a_refused_run_produces_no_record_and_so_no_durations():
    """The seam refuses before any stage is measured, and nothing is handed back.

    **The claim is that there is nothing to read.**  A bad argument is
    refused inside the window the total is taken over, the exception carries
    no result, and a record claiming a duration for a run that produced none
    would be a number nobody measured.  This is the shape of every other
    refusal at this seam, and it is why the timing lives on the result rather
    than on a side channel that could outlive it.
    """
    page = mrz_images.render_format("TD3")

    with pytest.raises(MrzValueError) as raised:
        run_tier0(page.image, "")

    assert not hasattr(raised.value, "stage_timings")


# --- the numbers come off a stopwatch and not a calendar ------------------


#: Every attribute call in this module that could be a clock of some kind.
#: The four calendar names are 6.2's and 6.4's own ban; the rest are here
#: because 6.6 is the first task to let the runner read a clock at all.
CLOCK_CALLS = {
    "now",
    "utcnow",
    "today",
    "fromtimestamp",
    "time",
    "monotonic",
    "monotonic_ns",
    "perf_counter",
    "perf_counter_ns",
    "process_time",
}


def _runner_tree():
    """The runner's own syntax tree, parsed from its file."""
    return ast.parse(pathlib.Path(runner.__file__).read_text(encoding="utf-8"))


def _clock_calls():
    """Every clock-shaped attribute call in the runner's own source."""
    return [
        node.func.attr
        for node in ast.walk(_runner_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        if node.func.attr in CLOCK_CALLS
    ]


def test_the_only_clock_the_runner_reads_is_the_monotonic_one():
    """6.6 measures a duration and never resolves a day, and this says so.

    **The walk is repeated from 6.2's and 6.4's and widened**, because this
    task is the first to make the runner read a clock.  Those two walks ban
    the four calendar names and would pass just as happily over
    :func:`time.time`, which answers "how long since this instant" *and*
    moves when the host's clock is corrected.  So the claim here is the
    positive one: the only clock-shaped call in the module is
    :func:`time.perf_counter`, reached through
    :func:`~app.pipeline.tier0.runner._now`, and every other name in the
    table is absent from a module that imports both ``datetime`` and
    ``time`` and so could have read either.
    """
    assert set(_clock_calls()) == {"perf_counter"}

    imported = {
        alias.name
        for node in ast.walk(_runner_tree())
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert {"datetime", "time"} <= imported
    assert runner._now() > 0


def test_each_stage_is_timed_where_the_cascade_calls_it():
    """Four differences of :func:`_now` readings, and nothing in the way.

    **A wrapper taking a callable could only ever time the function it was
    handed**, so the order that decides what Tier 0 *is* would sit in a
    decorator rather than in :func:`run_tier0` where a reader can see which
    stage is which.  So every write into the timings is a subtraction of two
    readings taken around the call -- one per named stage, one for the total
    -- and a fifth stage would have to be written in this function to be
    timed at all.
    """
    body = next(
        node
        for node in _runner_tree().body
        if isinstance(node, ast.FunctionDef) and node.name == "run_tier0"
    )
    written = [
        node
        for node in ast.walk(body)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Subscript)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "timings"
    ]

    assert [node.targets[0].slice.value for node in written] == [
        "detection",
        "check_digits",
        "watchlist",
        "total",
    ]
    for node in written:
        assert isinstance(node.value, ast.BinOp)
        assert isinstance(node.value.op, ast.Sub)
        assert _reads_the_counter(node.value.left)
        # The stage closes its own window; the total closes a window opened
        # before the first stage, so its right-hand side is a reading held in
        # a name rather than a second call.
        assert _reads_the_counter(node.value.right) or isinstance(
            node.value.right, ast.Name
        )


def _reads_the_counter(node):
    """Whether ``node`` is a call of :func:`~app.pipeline.tier0.runner._now`."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_now"
    )


# --- the record keeps its own copy ----------------------------------------


def test_the_timings_cannot_be_changed_after_the_record_is_built():
    """A frozen dataclass stops a field being reassigned, not a dict emptied.

    **The caller keeps the dict it handed over**, and that is the whole
    hazard: a record built from a mapping its caller still holds can have
    its timings rewritten afterwards, which is the hole
    :func:`~app.pipeline.tier0.runner._check_regions` names for a list handed
    in where a tuple belongs.  It would put a number on a screening record
    that the run never measured, and this figure is what the abstract's
    target is checked against.
    """
    timings = {name: 0.0 for name in STAGE_NAMES}
    result = TierResult(stage_timings=timings)

    timings[TOTAL] = 99.0
    timings.clear()

    assert result.stage_timings[TOTAL] == 0.0
    assert set(result.stage_timings) == set(STAGE_NAMES)
    with pytest.raises(TypeError):
        result.stage_timings[TOTAL] = 1.0
    assert isinstance(result.stage_timings, types.MappingProxyType)


def test_a_consumer_names_the_stage_it_wants_and_cannot_read_it_by_position():
    """The mapping is the point: ``["total"]`` answers and ``[0]`` does not.

    **A tuple of pairs would have kept the record hashable**, and that is
    why it was not used: it would answer ``stage_timings[0]`` as readily as
    ``stage_timings["total"]``, and a positional read of a stage is the one
    thing a written-down vocabulary exists to stop -- 4.11's and 4.12's field
    names are the same rule for the same reason.
    """
    result = TierResult()

    assert result.stage_timings[TOTAL] == 0.0
    with pytest.raises(KeyError):
        result.stage_timings[0]


def test_the_empty_result_times_nothing_and_says_so_with_zeros():
    """Every field defaulted, so the empty result is still a complete one.

    **Zero and not absent.**  A default-constructed result is a page with
    nothing on it that nobody measured, and a stage that never ran says the
    same as a stage that ran instantly -- so the default carries all four
    keys rather than an empty mapping, and two default-constructed results
    still compare equal, which is the one-value comparison 6.1 set up.
    """
    result = TierResult()

    assert result.stage_timings == {name: 0.0 for name in STAGE_NAMES}
    assert result == TierResult(stage_timings={name: 0.0 for name in STAGE_NAMES})


@pytest.mark.parametrize(
    "timings",
    [
        pytest.param(None, id="none"),
        pytest.param((), id="an-empty-tuple"),
        pytest.param(
            [(name, 0.0) for name in STAGE_NAMES], id="pairs-not-a-mapping"
        ),
        pytest.param({name: 0.0 for name in STAGES}, id="no-total"),
        pytest.param(
            {**{name: 0.0 for name in STAGE_NAMES}, "screening": 0.0},
            id="an-unknown-stage",
        ),
        pytest.param(
            {**{name: 0.0 for name in STAGE_NAMES}, "total": "0.1"},
            id="a-string",
        ),
        pytest.param(
            {**{name: 0.0 for name in STAGE_NAMES}, "total": None},
            id="a-value-of-none",
        ),
        pytest.param(
            {**{name: 0.0 for name in STAGE_NAMES}, "total": True},
            id="a-bool",
        ),
        pytest.param(
            {**{name: 0.0 for name in STAGE_NAMES}, "total": -0.001},
            id="negative",
        ),
        pytest.param(
            {**{name: 0.0 for name in STAGE_NAMES}, "total": math.nan},
            id="nan",
        ),
    ],
)
def test_timings_that_could_not_have_been_measured_are_refused(timings):
    """A missing stage, an invented one, and a value that is not a duration.

    **A ``nan`` is the case worth naming.**  ``value < 0`` is false for it, so
    a naive check would let a number that compares false against everything
    through and onto a screen; the check is chained, ``0 <= value``, for the
    reason 5.2's own unit-interval check is.  **A ``bool`` is refused** where
    5.2's would have let it through as a real number, because ``True`` is one
    second and a truth value is not a measurement.  **A missing key is a
    refusal and not a default**, because a stage nobody timed and a stage
    that took no time are two different statements and only the second is
    reportable.
    """
    with pytest.raises(MrzValueError):
        TierResult(stage_timings=timings)


def test_a_numpy_duration_is_a_number_and_not_a_rejection():
    """A timer is a real number whichever library counted it, as 5.2 says."""
    result = TierResult(
        stage_timings={name: np.float64(0.25) for name in STAGE_NAMES}
    )

    assert result.stage_timings[TOTAL] == 0.25


def test_the_entry_point_takes_no_stopwatch_and_offers_no_switch():
    """Timing is not a parameter, and a caller cannot turn the numbers off.

    **There is nothing to inject and nothing to configure.**  A ``clock=``
    argument would let a caller hand the runner a callable that answered
    zeros, which is the one way these numbers could be wrong with nothing
    else broken.  6.1 already pins the signature, so what is held here is
    that 6.6 left it alone.
    """
    parameters = inspect.signature(run_tier0).parameters

    assert list(parameters) == [
        "image",
        "document_type",
        "reference_date",
        "parsed_document",
        "watchlist",
    ]
    assert not [name for name in parameters if "clock" in name or "time" in name]
