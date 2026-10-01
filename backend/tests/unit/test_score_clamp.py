"""The score an officer reads is on the scale, and 195 becomes 100.

Task 7.7 asks for the final score clamped to ``[0, 100]`` with tests at both
extremes, and the two headline tests below are those extremes reached the
whole way rather than typed in: the top is 7.5's own unclamped sum of three
``high`` findings at full strength (195 points, measured off the committed
file), and the bottom is 7.5's own empty sum (a clean document, ``0.0``).
Both are swept rather than illustrated, because "off the scale" is the part of
the claim that one example can understate.

**The other half is what the clamp must not do**: rescale, band, replace 7.6's
floor, lower a heavier score, or refuse a score that is merely large.  A
refusal there would fail a document instead of reporting it, which is the
opposite of the refusal ``D23`` and ``D24`` make.

**Every weight is read off ``v1.yaml`` and none is retyped here**, the way
7.5's and 7.6's suites do.  **And the ``REVIEW_MAX`` below is 7.8's, imported
rather than written out**: it was a local copy while the threshold did not
exist, on 7.6's suite's reason, so a retune of the pair now moves this file's
claims with it.
"""

import ast
import pathlib

import pytest

from app.risk import clamp as clamp_module
from app.risk import flag_ids
from app.risk.config import REVIEW_MAX
from app.risk.clamp import clamp_score
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.hard_rules import (
    DEFAULT_HARD_FAIL_FLOOR,
    MAX_SCORE,
    MIN_SCORE,
    apply_hard_rules,
)
from app.risk.scoring import weighted_sum
from app.risk.weightsets.loader import load_weightset

#: A field-shaped box: two lines of pixels, clockwise from the top left, the
#: shape 4.12's `_box_polygon` writes.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: The three ``high`` findings 7.5's own suite sums to 195.  Their weights are
#: read off the file, never restated, so a retune moves both sides of this.
HIGH_PILE = (
    flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH,
    flag_ids.WATCHLIST_HIT,
    flag_ids.CROSSDOC_FACE_MISMATCH,
)

#: Worked example A's own override, used where one overriding rule has to
#: stand for the family.  The table is passed in rather than imported: which
#: rules override is 6.5's answer and ``D26``'s decision is that ``app.risk``
#: is asked rather than told.
HARD_FAIL_IDS = frozenset({flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH})

#: How many soft findings, and how strongly each reports.  100 is four passes
#: over the vocabulary at full strength -- several times the top of the scale,
#: which is the situation in which a rescale would show rather than a clamp.
PILE_SIZES = (0, 1, 3, 25, 100)
PILE_VALUES = (0.0, 0.5, 1.0)


def a_flag(flag_id, value=1.0, **overrides):
    """A well-formed flag, with ``overrides`` replacing any of its fields."""
    fields = {
        "id": flag_id,
        "tier": 0,
        "label": "A finding worth explaining",
        "weight_band": "high",
        "value": value,
        "confidence": 1.0,
        "region": FIELD_BOX,
        "expected": None,
        "found": None,
        "reason": "The printed characters disagree with the computed check.",
        "source_module": "app.pipeline.tier0.runner",
        "field": None,
    }
    fields.update(overrides)
    return EvidenceFlag(**fields)


def a_soft_pile(size, value):
    """``size`` full-strength findings from the pile above, cycling it."""
    return [
        a_flag(HIGH_PILE[index % len(HIGH_PILE)], value) for index in range(size)
    ]


def the_score(flags):
    """7.5's sum, read off the committed weightset."""
    return weighted_sum(flags, load_weightset())


def the_answer(flags):
    """The end-to-end reading: 7.5's sum, 7.6's floor, then 7.7's clamp."""
    total = the_score(flags)
    return clamp_score(apply_hard_rules(total, flags, HARD_FAIL_IDS))


# --- the two extremes the task names ---------------------------------------


@pytest.mark.parametrize("size", PILE_SIZES)
@pytest.mark.parametrize("value", PILE_VALUES)
def test_a_score_above_the_top_of_the_scale_is_held_to_the_top(size, value):
    """The upper extreme, reached the whole way and answered rather than
    refused.

    **The sum is 7.5's own and is not clamped inside it.** Three ``high``
    findings at full strength are 195 points under ``D21``, and a module that
    held the sum would have made 7.5's own
    ``test_the_sum_is_not_clamped_and_may_exceed_a_hundred`` true by
    accident. So the two are asked of each other: the sum is over the top, and
    the clamp is the top.

    **A score off the scale is answered, not refused.** The pile is swept from
    one finding to a hundred so that the sizes which reach the top for real are
    here, and a clamp that raised above ``MAX_SCORE`` for the larger ones
    fails here rather than passing on the small end.  Reporting a document
    heavier than the scale allows is the point; failing it would not be.
    """
    flags = a_soft_pile(size, value)
    screened = the_score(flags)

    if screened > MAX_SCORE:
        assert the_answer(flags) == MAX_SCORE
    assert clamp_score(screened) == min(screened, MAX_SCORE)
    assert clamp_score(screened) <= MAX_SCORE


def test_three_high_findings_are_a_hundred_and_not_a_hundred_and_eighty():
    """The upper extreme as one number an officer can be shown.

    7.5's own worked example for the no-clamp case is three ``high`` weights at
    full strength, and the weights are read here rather than retyped so the two
    suites agree by construction. ``195`` is checked as a measured fact of this
    weightset rather than assumed: a ruleset whose three heaviest findings came
    to less would leave this test measuring nothing.
    """
    loaded = load_weightset()
    flags = a_soft_pile(3, 1.0)
    screened = weighted_sum(flags, loaded)

    assert [loaded.flags[flag_id]["weight"] for flag_id in HIGH_PILE] == [65, 65, 65]
    assert screened == 195.0
    assert screened > MAX_SCORE
    assert the_answer(flags) == MAX_SCORE


@pytest.mark.parametrize(
    "score",
    [
        pytest.param(-0.5, id="just-below"),
        pytest.param(-12.5, id="below-the-hard-fail-floor"),
        pytest.param(-1e9, id="far-below"),
    ],
)
def test_a_score_below_the_bottom_of_the_scale_is_held_to_the_bottom(score):
    """The lower extreme, held for the number that can reach it.

    **Nothing in this engine reaches below zero today**: every committed
    weight is positive and every value is in ``[0, 1]``, so the sum is a sum of
    non-negative terms.  That is why the bound is held rather than proved
    unreachable -- **7.14's history term is the first thing that can move a
    score down**, and a screening's score must not read below zero because a
    traveller has a verified history.  The numbers are offered directly for
    that reason; the sweep below covers the half an officer can reach today.
    """
    assert score < MIN_SCORE
    assert clamp_score(score) == MIN_SCORE
    assert clamp_score(score) >= MIN_SCORE


@pytest.mark.parametrize("size", PILE_SIZES)
@pytest.mark.parametrize("value", PILE_VALUES)
def test_the_lower_half_of_the_scale_is_never_lifted_off_it(size, value):
    """The honest lower extreme: no finding fired, or few, and the reading is
    the sum itself.

    The empty sum is ``0.0`` and not a refusal, so a clean document reads zero
    rather than being lifted off the bottom of the scale by anything -- least of
    all by a floor, which needs an overriding rule to fire and this pile holds
    none, so the floor is a no-op here.

    **"Never lifted" is the whole claim and it is signed**: a clamp that added
    anything, or that nudged a score up to a round number, would raise a
    reading here while every pile past the top would look identical.
    """
    flags = a_soft_pile(size, value)
    screened = the_score(flags)

    assert screened >= MIN_SCORE
    assert clamp_score(screened) == min(screened, MAX_SCORE)
    assert clamp_score(screened) <= screened
    assert MIN_SCORE <= clamp_score(screened)
    assert the_answer(flags) == clamp_score(screened)
    assert the_answer([]) == MIN_SCORE


# --- the two ends are levels, not the first number off them -----------------


def test_both_ends_are_answered_as_the_scale_and_the_scale_is_the_tasks_scale():
    """``[0, 100]``, held as a pair rather than retyped at each end.

    7.6's suite already reads these two names, so a clamp that wrote ``0`` and
    ``100`` itself would be free to disagree with a retune of either. The
    numbers are also written here as the task states them, because a scale
    that moved without ``MAX_SCORE`` moving with it would answer a different
    question from the one the abstract asks.
    """
    assert (MIN_SCORE, MAX_SCORE) == (0.0, 100.0)
    assert clamp_score(MIN_SCORE) == MIN_SCORE
    assert clamp_score(MAX_SCORE) == MAX_SCORE


def test_a_score_inside_the_scale_is_handed_back_untouched():
    """No rounding, no rescaling, no flooring of a decimal place.

    The values are written as the arithmetic rather than the literals, so the
    expectation and the input cannot drift apart, and a clamp that rounded or
    truncated would move a score an officer is shown a reason for.
    """
    for score in (
        0.0 + 0.0,
        30.0 + 10.0 + 11.25,
        MIN_SCORE + 0.5,
        69.0 + 0.5,
        MAX_SCORE - 1e-9,
        MAX_SCORE,
    ):
        assert clamp_score(score) == score
        assert type(clamp_score(score)) is float


def test_the_clamp_is_not_a_rescale_and_loses_no_margin_it_can_keep():
    """Everything above the top is the same number, and 95 is still 95.

    The mistake this rules out is dividing by the total, or subtracting the
    overflow: ``195`` would become 65 under a share-of-the-top reading and 100
    minus the overflow would be a different number per document.  The margin
    above ``REVIEW_MAX`` is what 7.9 reads, so it has to survive wherever the
    scale has room for it.
    """
    assert clamp_score(MAX_SCORE + 0.5) == clamp_score(MAX_SCORE * 10) == MAX_SCORE
    assert clamp_score(95.0) == 95.0
    assert clamp_score(95.0) > REVIEW_MAX
    assert clamp_score(REVIEW_MAX) == REVIEW_MAX


def test_the_clamp_is_not_the_band_threshold():
    """It stops at the top of the scale and at nothing else.

    7.8's ``LOW_MAX`` and ``REVIEW_MAX`` are the boundaries of a *band*, and a
    clamp that stopped at one would answer two documents in the same band with
    the same score.  Read here as 7.6's suite reads it, so this file's claim
    and that file's claim about the floor are two sides of one number.
    """
    assert MAX_SCORE > REVIEW_MAX
    assert clamp_score(REVIEW_MAX + 0.5) != REVIEW_MAX
    assert clamp_score(REVIEW_MAX + 0.5) == REVIEW_MAX + 0.5


# --- what the clamp is composed with ---------------------------------------


def test_a_hard_fail_is_still_the_floor_and_not_a_hundred():
    """7.7 does not swallow 7.6, and this is the test that says so.

    Worked example A's shape: one broken printed digit, measured at ``0.0``,
    and nothing else on the page.  The sum is ``0.0``, the floor is ``90.0``,
    and the answer has to be ``90.0`` -- a clamp that reported the top of the
    scale would make every override indistinguishable from every pile of
    strong soft findings, which is exactly what 7.6's floor exists to prevent.
    """
    hard_fail = [a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 0.0)]

    assert the_score(hard_fail) == 0.0
    assert the_answer(hard_fail) == DEFAULT_HARD_FAIL_FLOOR
    assert the_answer(hard_fail) < MAX_SCORE


@pytest.mark.parametrize(
    ("size", "value"),
    [
        pytest.param(0, 0.5, id="a-hard-fail-alone-below-the-floor"),
        pytest.param(1, 0.5, id="below-the-floor"),
        pytest.param(3, 0.5, id="above-the-floor-below-the-top"),
        pytest.param(3, 1.0, id="past-the-top"),
    ],
)
def test_the_clamp_and_the_floor_answer_the_same_either_way_round(size, value):
    """Order is not a scoring input, and here it cannot be observed.

    7.6 holds a floor inside ``[MIN_SCORE, MAX_SCORE]`` and refuses one outside
    it, which is what makes this hold: a floor above the top would be
    unreachable and one below the bottom a no-op, so composing the two in
    either order lands on the same number.  **An overriding rule is in every
    one of the four cases**, or the floor is a no-op and the claim is
    vacuous, and they sit below the floor, above it, and past the top of the
    scale -- the only places the two orders could differ.
    """
    loaded = load_weightset()
    flags = a_soft_pile(size, value) + [
        a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 0.0)
    ]
    screened = weighted_sum(flags, loaded)

    floored_then_clamped = clamp_score(
        apply_hard_rules(screened, flags, HARD_FAIL_IDS)
    )
    clamped_then_floored = apply_hard_rules(
        clamp_score(screened), flags, HARD_FAIL_IDS
    )

    assert floored_then_clamped == clamped_then_floored
    assert floored_then_clamped == min(
        max(screened, DEFAULT_HARD_FAIL_FLOOR), MAX_SCORE
    )
    assert MIN_SCORE <= floored_then_clamped <= MAX_SCORE


@pytest.mark.parametrize("size", PILE_SIZES)
@pytest.mark.parametrize("value", PILE_VALUES)
def test_appending_evidence_never_lowers_the_score_an_officer_reads(size, value):
    """More findings never read safer, at either end of the scale.

    ``D21`` makes every weight positive, so a bigger pile is a larger sum and
    the clamp is not what makes this true -- but the clamp is where it would
    stop being observable, since past the top every pile reads 100.  A clamp
    that rescaled rather than held would break the bottom half of this sweep,
    which is why the empty pile is in it.
    """
    answers = [
        the_answer(a_soft_pile(index, value)) for index in range(size + 1)
    ]

    assert answers == sorted(answers)
    assert answers[-1] >= answers[0]
    assert all(MIN_SCORE <= answer <= MAX_SCORE for answer in answers)


def test_holding_the_answer_twice_is_holding_it_once():
    """A clamp applied to its own output is not a second opinion."""
    for score in (-12.5, 0.0, 51.25, 90.0, 195.0):
        once = clamp_score(score)

        assert clamp_score(once) == once


# --- refusals reach the caller rather than becoming a number ---------------


@pytest.mark.parametrize(
    "score",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="boolean"),
        pytest.param("100", id="text"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_a_score_that_is_not_a_finite_number_is_refused(score):
    """A ``nan`` is the quiet one: every comparison against it is false, so a
    clamp written as two comparisons would hand it straight back.
    """
    with pytest.raises(FlagValueError):
        clamp_score(score)


def test_a_refusal_never_quotes_the_value_it_refused():
    """``D6``'s rule, held over a score: the message names the field and the
    type, because the value is where something off a document arrives.
    """
    with pytest.raises(FlagValueError) as raised:
        clamp_score("FICTITIOUS<<JANE")

    assert "FICTITIOUS" not in str(raised.value)
    assert "score" in str(raised.value)


def test_an_int_score_is_answered_as_the_float_the_scale_is_written_in():
    """The weights in ``v1.yaml`` are YAML integers and the scale is floats."""

    assert clamp_score(MAX_SCORE) == MAX_SCORE
    assert clamp_score(195) == MAX_SCORE
    assert type(clamp_score(195)) is float


def test_the_answer_is_never_a_negative_zero():
    """An officer reads a number, and ``-0.0`` prints as one.

    Both ends of the scale are zero in different directions: ``MIN_SCORE`` is
    ``0.0`` and a score of ``-0.0`` is equal to it. A clamp written
    ``min(max(score, MIN), MAX)`` returns whichever zero it was handed, so the
    spelling is held rather than assumed to be free.
    """
    clamped = clamp_score(-0.0)

    assert clamped == MIN_SCORE
    assert str(clamped) == "0.0"


# --- what the module may import --------------------------------------------


def test_the_module_reaches_only_the_scale_it_is_held_to():
    """Walked rather than grepped, and the claim is the absence of an import.

    The scale's two ends and the one validation of a score are 7.6's, and this
    module reads them rather than retyping them -- which is also why
    ``app.pipeline`` must not appear: ``D6``'s one-way dependency keeps the
    tier out of ``app.risk``, and a clamp that reached back into one would put
    it there.  **One import is the whole of the reach**, and the error type is
    named in the docstring rather than imported and left unused.
    """
    tree = ast.parse(
        pathlib.Path(clamp_module.__file__).read_text(encoding="utf-8")
    )
    imported = set()
    standard = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {node.module or ""}
        else:
            continue
        for name in names:
            if name.split(".")[0] == "app":
                imported.add(name)
            else:
                standard.add(name)

    assert imported == {"app.risk.hard_rules"}
    assert standard == set()


def test_the_module_defines_neither_end_of_the_scale():
    """The pair of numbers is 7.6's, and there is one pair.

    7.6 wrote ``MIN_SCORE`` and ``MAX_SCORE`` for exactly this, and its own
    suite already reads both names.  A module that assigned them again would
    be free to answer a different question from the one the abstract asks the
    moment either was retuned, and nothing would fail until a screening.
    """
    source = pathlib.Path(clamp_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert not assigned & {"MIN_SCORE", "MAX_SCORE"}


def test_the_module_exports_the_one_name_the_task_names():
    """``MIN_SCORE``, ``MAX_SCORE`` and the validator are used, not
    re-exported: they are 7.6's and are read from there."""
    assert clamp_module.__all__ == ["clamp_score"]


def test_the_module_reads_no_clock_no_randomness_and_opens_no_file():
    """``D12``'s rule extends here, and a clamp that depended on when it ran
    would be a screening nobody could replay."""
    source = pathlib.Path(clamp_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)

    assert not called & {
        "now",
        "today",
        "time",
        "perf_counter",
        "random",
        "uniform",
        "randint",
        "sum",
        "fsum",
        "open",
    }
