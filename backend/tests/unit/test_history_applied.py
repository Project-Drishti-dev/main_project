"""The history term added to a score, and the bound the adjustment cannot pass.

Task 7.14 asks for the history signal combined into the final score as a
bounded additive term, with a test asserting the adjustment never exceeds the
bound.  **The headline below is that assertion, swept rather than
illustrated**: scores from below the scale to well past the top of it,
histories long enough to overflow any bound by three orders of magnitude in
both directions, and three committed bounds including the widest
:class:`~app.risk.history.HistoryConfig` will take.

**The bound is 7.13's and is not written a second time.**  The term arrives
already inside ``+/- config.max_magnitude``, so what this task has to hold is
that *adding* it does not move a score further than the term does -- which is
the claim about the composition, and the reason the allowance in
:func:`_rounding` is one ulp of the arithmetic rather than a number typed
here.  A second clamp written in this task's own module would pass the
headline while answering a different question.

**The order of the four questions is part of the claim.**  The abstract's
``R = Sum(w_i * F_i) + hard rules`` puts the history term *under* the hard
rules, and the difference is observable: a term applied above 7.6's floor
could pull a hard fail's reading back down off it, which is not what an
override means.  So :func:`~app.risk.history.apply_history` adds the term and
stops, and the sweeps below ask of the composition -- sum, term, floor, clamp
-- that the floor and the clamp can only shrink the adjustment.
"""

import ast
import math
import pathlib
from datetime import date, timedelta

import pytest

from app.risk import flag_ids
from app.risk import history as history_module
from app.risk.clamp import clamp_score
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.hard_rules import (
    DEFAULT_HARD_FAIL_FLOOR,
    MAX_SCORE,
    MIN_SCORE,
    apply_hard_rules,
)
from app.risk.history import (
    DEFAULT_HISTORY_CONFIG,
    HISTORY_HALF_LIFE_DAYS,
    HISTORY_MAX_MAGNITUDE,
    HistoryConfig,
    PriorOutcome,
    apply_history,
    history_signal,
)
from app.risk.scoring import weighted_sum
from app.risk.weightsets.loader import load_weightset

#: The committed numbers, read off the module rather than typed, so a retune
#: moves every claim in this file with it.
HALF_LIFE = HISTORY_HALF_LIFE_DAYS
BOUND = HISTORY_MAX_MAGNITUDE

#: A fixed day to measure against, on ``D12``'s reason: the reference is the
#: caller's and no clock is read here either.
REFERENCE = date(2026, 10, 1)

#: The signed points one outcome is worth, on the unit 7.13 answers in.
PASS_POINTS = -8.0
FAIL_POINTS = 10.0

#: How old "old" is, as a multiple of the half-life rather than a day count.
OLD_HALF_LIVES = 4

#: A field-shaped box for the flags below: 4.12's ``_box_polygon`` shape.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: The three findings 7.5's own suite sums to 195 at full strength.  Read off
#: the vocabulary rather than restated, and used only through ``weighted_sum``.
HIGH_PILE = (
    flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH,
    flag_ids.WATCHLIST_HIT,
    flag_ids.CROSSDOC_FACE_MISMATCH,
)

#: Worked example A's own override.  Which rules override is 6.5's answer and
#: ``D26``'s decision is that ``app.risk`` is asked rather than told, so the
#: table is passed in rather than imported.
HARD_FAIL_ID = flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH
HARD_FAIL_IDS = frozenset({flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH})

#: How many outcomes a loud history holds.  Each is worth the whole scale, so
#: the sum is 50 000 points: three orders of magnitude past the widest bound
#: the config will take, which is what makes the clamp the only thing standing
#: between a long history and the headline.
LOUD = 500


def a_flag(flag_id, value=1.0):
    """A well-formed flag carrying one finding, with the 12 fields it needs."""
    return EvidenceFlag(
        id=flag_id,
        tier=0,
        label="A finding worth explaining",
        weight_band="high",
        value=value,
        confidence=1.0,
        region=FIELD_BOX,
        expected=None,
        found=None,
        reason="The printed characters disagree with the computed check.",
        source_module="app.pipeline.tier0.runner",
        field=None,
    )


def a_soft_pile(size, value):
    """``size`` full-strength findings from the pile above, cycling it."""
    return [
        a_flag(HIGH_PILE[index % len(HIGH_PILE)], value) for index in range(size)
    ]


def _outcome(days_old=0, weight=PASS_POINTS, verified=True):
    """A :class:`PriorOutcome` ``days_old`` days before :data:`REFERENCE`."""
    return PriorOutcome(
        outcome_date=REFERENCE - timedelta(days=days_old),
        weight=weight,
        verified=verified,
    )


class _Row:
    """A record carrying whatever fields it was handed, and nothing more.

    **Not a flag and not a dataclass**, because the point of it is that the
    refusals below are the signal's own: a row read back from storage in Part
    8 carries named fields rather than being rebuilt as a
    :class:`~app.risk.history.PriorOutcome` first.
    """

    def __init__(self, **fields):
        self.__dict__.update(fields)


def _loud(weight, count=LOUD, days_old=0, verified=True):
    """``count`` fresh (or ``days_old``) outcomes worth ``weight`` each."""
    return [
        _outcome(days_old, weight, verified) for _ in range(count)
    ]


#: A pile of passes worth 50 000 points, a pile of fails worth the same, a
#: long mixed history whose fresher half dominates, and a history in which
#: nothing was ever audited.
LOUD_PASSES = _loud(-MAX_SCORE)
LOUD_FAILS = _loud(MAX_SCORE)
LOUD_MIXED = [*_loud(MAX_SCORE, 300), *_loud(-MAX_SCORE, 300, 4 * HALF_LIFE)]
LOUD_UNAUDITED = _loud(MAX_SCORE, verified=False)

PILES = (LOUD_PASSES, LOUD_FAILS, LOUD_MIXED, LOUD_UNAUDITED)
PILE_IDS = ("passes", "fails", "mixed", "nothing-audited")

#: The three bounds the sweep is run at: the committed one, one tighter than
#: anything else in the file, and the widest :class:`HistoryConfig` accepts.
CONFIGS = (
    DEFAULT_HISTORY_CONFIG,
    HistoryConfig(max_magnitude=1.0),
    HistoryConfig(max_magnitude=MAX_SCORE),
)
CONFIG_IDS = ("committed", "tighter", "widest")

#: The scores the term is added to: outside the scale at both ends, an
#: awkward decimal, and every level the two committed thresholds sit at.
SCORES = (-40.0, MIN_SCORE, 3.7, LOW_MAX, REVIEW_MAX, MAX_SCORE, 195.0)
SCORE_IDS = (
    "below-the-scale",
    "the-bottom",
    "an-awkward-decimal",
    "the-first-threshold",
    "the-second-threshold",
    "the-top",
    "past-the-top",
)

#: Five screenings covering the places the two questions after this one could
#: differ: nothing fired, an override on its own, an override beside soft
#: evidence, soft evidence alone, and soft evidence already past the top.
SCREENINGS = {
    "nothing-fired": (),
    "one-hard-fail-alone": (a_flag(HARD_FAIL_ID, 0.0),),
    "a-hard-fail-beside-evidence": (
        a_flag(HARD_FAIL_ID, 0.0),
        *a_soft_pile(3, 0.5),
    ),
    "evidence-alone": tuple(a_soft_pile(3, 0.5)),
    "evidence-past-the-top": tuple(a_soft_pile(9, 1.0)),
}
SCREENING_IDS = sorted(SCREENINGS)


def _rounding(*numbers):
    """The most this arithmetic can be wrong, as a ``float``.

    **The adjustment is a difference, not the term that was added.**  The sum
    is rounded once on the way in and the difference rounded again on the way
    out, each within half a ulp of the larger magnitude, so one ulp is the
    whole allowance.  It is read off the numbers themselves rather than
    written here, which is what keeps the headline a claim about the bound
    rather than a claim about a tolerance somebody liked -- and is why a
    second clamp in the production module is *not* what makes the bound hold.
    """
    return max(math.ulp(abs(number)) for number in numbers)


def _tree():
    """This module's own syntax tree, parsed from its own file."""
    return ast.parse(
        pathlib.Path(history_module.__file__).read_text(encoding="utf-8")
    )


def _function(name):
    """The one function definition called ``name``, for a walk scoped to it."""
    found = [
        node
        for node in ast.walk(_tree())
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(found) == 1, name
    return found[0]


def the_score(flags):
    """7.5's sum, read off the committed weightset."""
    return weighted_sum(flags, load_weightset())


def the_reading(score, flags):
    """The two questions after this one: 7.6's floor, then 7.7's clamp."""
    return clamp_score(apply_hard_rules(score, flags, HARD_FAIL_IDS))


# --- the claim the task names ----------------------------------------------


@pytest.mark.parametrize("score", SCORES, ids=SCORE_IDS)
@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("pile", PILES, ids=PILE_IDS)
def test_the_adjustment_never_exceeds_the_bound(score, config, pile):
    """7.14's own sentence: bounded, so it can only move the score so much.

    **Swept over both directions, both ends of the scale and three bounds.**
    Every pile here overflows the bound by three orders of magnitude, so a term
    that were merely *nearly* bounded would answer the bound at these cases and
    the headline would be about the sweep rather than about the bound.  The
    scores are read off ``D29``'s two thresholds and 7.6's two ends, so this
    holds at whatever they are set to.
    """
    answer = apply_history(score, pile, REFERENCE, config)

    assert isinstance(answer, float)
    assert (
        abs(answer - score)
        <= config.max_magnitude + _rounding(score, answer)
    )


def test_the_term_that_is_added_is_the_bounded_signal_itself():
    """The adjustment is the term, not a version of it.

    **Exact equality, and no tolerance.**  This is the half the bound cannot
    see: a term halved or doubled still answers inside the bound at the widest
    config, and only the identity catches it.  The bound on the signal is
    asserted exactly here too, which is what the allowance in
    :func:`_rounding` above is *not* applied to.
    """
    for pile in PILES:
        for config in CONFIGS:
            signal = history_signal(pile, REFERENCE, config)

            assert abs(signal) <= config.max_magnitude
            assert apply_history(37.5, pile, REFERENCE, config) == (
                37.5 + signal
            )


def test_a_verified_pass_takes_points_off_and_a_verified_fail_puts_them_on():
    """The sign survives the addition, on 7.13's own unit.

    A term written ``abs(signal)`` would answer the bound above and still be a
    history layer that raises a traveller's score because a traveller was
    confirmed genuine, so the direction is asserted rather than the magnitude.
    """
    base = 40.0

    assert apply_history(base, LOUD_PASSES, REFERENCE) == base - BOUND
    assert apply_history(base, LOUD_FAILS, REFERENCE) == base + BOUND


def test_an_old_verified_pass_takes_off_less_than_a_recent_one():
    """4.8's decay, asked of the score rather than of the signal.

    **Both adjustments are exact**, so the headline above is not passing
    because the term is a flat 12 whatever the history says: a fresh pass
    takes its own points off and a four-half-life one takes a sixteenth.
    """
    base = 40.0
    recent = apply_history(base, [_outcome(0, PASS_POINTS)], REFERENCE)
    old = apply_history(
        base, [_outcome(OLD_HALF_LIVES * HALF_LIFE, PASS_POINTS)], REFERENCE
    )

    assert base - recent == -PASS_POINTS
    assert base - old == -PASS_POINTS * 0.5**OLD_HALF_LIVES
    assert base - recent > base - old > 0.0


def test_an_empty_history_leaves_the_score_exactly_as_it_was():
    """A first-time traveller is the common case, not a fault.

    **The empty sum is added rather than skipped**, and it is ``0.0`` added to
    a score rather than the score handed back untouched, so the answer is a
    ``float`` whatever the score arrived as.
    """
    for score in (0.0, 17.5, MIN_SCORE, MAX_SCORE, 195.0, -40.0):
        assert apply_history(score, [], REFERENCE) == score

    assert isinstance(apply_history(17, [], REFERENCE), float)


# --- where the term sits among the four questions --------------------------


@pytest.mark.parametrize("screen", SCREENING_IDS)
@pytest.mark.parametrize("pile", PILES, ids=PILE_IDS)
def test_the_floor_and_the_clamp_can_only_shrink_the_adjustment(screen, pile):
    """The two readings an officer compares differ by at most the term.

    The abstract writes ``R = Sum(w_i * F_i) + hard rules`` with the history
    term added to the sum and the hard rules above it, and **the difference
    between the reading taken with the term and the reading taken without it
    is what "only move the score by a limited amount" means at the end of the
    chain.**  Both later questions are 1-Lipschitz -- a floor raises and a
    clamp holds, and neither can add to a difference -- so composing them
    after the term can only hold that difference inside the term's own
    magnitude.  The five screenings are the places where they could differ:
    a floor that swallowed the term whole, and a clamp that swallowed it the
    other way.
    """
    flags = SCREENINGS[screen]
    screened = the_score(flags)
    with_history = apply_history(screened, pile, REFERENCE)
    final = the_reading(with_history, flags)
    without_history = the_reading(screened, flags)

    assert abs(with_history - screened) <= BOUND + _rounding(
        screened, with_history
    )
    assert abs(final - without_history) <= abs(
        with_history - screened
    ) + _rounding(screened, final)
    assert abs(final - without_history) <= BOUND + _rounding(screened, final)


def test_a_hard_fail_still_reads_the_floor_over_a_loud_history():
    """Worked example A's shape, with the history term under the floor.

    The sum is ``0.0``, the term is the whole ``-BOUND`` -- a history loud
    enough to take the score below the bottom of the scale -- and the reading
    has to be the floor.  **A term added above the floor answers 78.0**, which
    is the order this test exists to pin.
    """
    flags = SCREENINGS["one-hard-fail-alone"]
    screened = the_score(flags)
    with_history = apply_history(screened, LOUD_PASSES, REFERENCE)

    assert screened == 0.0
    assert with_history == -BOUND
    assert the_reading(with_history, flags) == DEFAULT_HARD_FAIL_FLOOR
    assert the_reading(with_history, flags) < DEFAULT_HARD_FAIL_FLOOR + BOUND


def test_a_loud_history_alone_reads_the_bottom_of_the_scale():
    """The control: the floor is above the term, not inside it.

    The same history with no override reads ``0.0`` -- held by 7.7 rather than
    lifted by 7.6 -- which is the other half of the order claim: neither of
    the two later questions is applied by :func:`apply_history` itself.
    """
    flags = ()
    screened = the_score(flags)
    with_history = apply_history(screened, LOUD_PASSES, REFERENCE)

    assert with_history == -BOUND
    assert the_reading(with_history, flags) == MIN_SCORE
    assert the_reading(with_history, flags) < DEFAULT_HARD_FAIL_FLOOR


@pytest.mark.parametrize(
    "score",
    [195.0, 500.0, -40.0, -500.0],
    ids=["past-the-top", "far-past", "below-the-scale", "far-below"],
)
def test_a_score_off_the_scale_is_answered_off_the_scale(score):
    """Nothing is held here: that is 7.7's question and it is asked after.

    On 7.7's reason that an off-scale score is a real reading rather than a
    fault.  **A term that clamped on the way through would make this task's
    answer depend on where the score stood**, and 195 plus the term is a sum
    the clamp is there to receive.
    """
    assert apply_history(score, LOUD_FAILS, REFERENCE) == score + BOUND
    assert apply_history(score, LOUD_PASSES, REFERENCE) == score - BOUND


# --- what the term is, structurally ----------------------------------------


def test_the_function_adds_the_signal_and_asks_nothing_else():
    """Two calls: the package's one validation of a number, and the signal.

    **A walk over this function's own subtree**, as 7.12's and 7.13's narrow
    walks are, and it is what holds that neither 7.6's floor nor 7.7's clamp
    nor 7.9's band is reached from here.  It also catches a term rescaled
    through any other name, and a second clamp written here instead of in
    :func:`history_signal`.
    """
    names, attributes = set(), set()
    for node in ast.walk(_function("apply_history")):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            attributes.add(node.func.attr)

    assert names == {"_score", "history_signal"}
    assert attributes == set()


def test_the_function_compares_nothing_and_defines_no_bound():
    """The bound is 7.13's, and there is one of it.

    **Held over the function's own subtree** rather than over the module: a
    second bound written here would be a policy number stated twice, free to
    disagree with a retune of :data:`HISTORY_MAX_MAGNITUDE` in a way nothing
    else in the package would notice.  **No number is written and nothing is
    compared**, which is the whole of the shape a two-call function has.
    """
    function = _function("apply_history")

    assert not [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ]
    assert not [
        node for node in ast.walk(function) if isinstance(node, ast.Compare)
    ]


def test_the_signature_is_the_task_s_and_config_is_not_keyword_only():
    """``score`` first, then the three :func:`history_signal` already takes.

    **Written as an inspection rather than a call**, because the claim is
    about what the four names *are*: a fifth argument is a dependency nothing
    has asked for, and making ``config`` keyword-only would break the
    positional spelling 7.13's own suite pins beside it.
    """
    assert apply_history.__code__.co_varnames[
        : apply_history.__code__.co_argcount
    ] == ("score", "prior_outcomes", "reference_date", "config")

    pile = [_outcome(0, FAIL_POINTS)]
    assert apply_history(
        10.0, pile, REFERENCE, HistoryConfig()
    ) == apply_history(10.0, pile, REFERENCE, config=HistoryConfig())


def test_the_term_is_exported_and_the_layer_is_otherwise_unchanged():
    """One name added to the surface, and it is the one this task names."""
    assert "apply_history" in history_module.__all__
    assert set(history_module.__all__) == {
        "DEFAULT_HISTORY_CONFIG",
        "HISTORY_HALF_LIFE_DAYS",
        "HISTORY_MAX_MAGNITUDE",
        "HistoryConfig",
        "PriorOutcome",
        "apply_history",
        "decay",
        "history_signal",
    }


def test_the_same_score_and_history_always_answer_the_same_score():
    """Pure: no file, no randomness, no hidden state and no clock.

    **Two separately built but equal histories**, because comparing one object
    with itself answers only that the function is a function: a term that
    read a clock, drew a random weight or cached the last answer would answer
    two equal histories identically in the first case and differ here.
    """
    one = [_outcome(index % 3, FAIL_POINTS) for index in range(20)]
    the_other = [_outcome(index % 3, FAIL_POINTS) for index in range(20)]

    assert one == the_other
    assert apply_history(48.0, one, REFERENCE) == apply_history(
        48.0, the_other, REFERENCE
    )


def test_nothing_the_caller_handed_in_is_amended():
    """The records and the config come back exactly as they went in."""
    outcomes = [_outcome(1, FAIL_POINTS)]
    config = HistoryConfig()

    apply_history(50.0, outcomes, REFERENCE, config)

    assert (outcomes, config) == ([_outcome(1, FAIL_POINTS)], HistoryConfig())


# --- what it refuses --------------------------------------------------------


@pytest.mark.parametrize(
    "bad_score",
    [
        None,
        True,
        False,
        "80",
        object(),
        float("nan"),
        float("inf"),
        -float("inf"),
    ],
    ids=[
        "none",
        "true",
        "false",
        "string",
        "object",
        "nan",
        "inf",
        "neg-inf",
    ],
)
def test_a_score_that_is_not_a_number_is_refused(bad_score):
    """7.6's one validation of a number, asked of the score this task adds to.

    **A ``nan`` is the case that matters**: it poisons a sum silently, passes
    every comparison against a bound and would be handed straight back as an
    answer an officer reads.
    """
    with pytest.raises(FlagValueError) as caught:
        apply_history(bad_score, LOUD_FAILS, REFERENCE)
    assert "score" in str(caught.value)


def test_the_score_is_checked_before_the_history_is_read():
    """A call with two faults is told about the score.

    The score is the argument that arrived first and it is the one every
    caller has, so a record that cannot be summed must not be the message a
    caller is given for a score that was not a number to begin with.
    """
    with pytest.raises(FlagValueError) as caught:
        apply_history(None, [object()], REFERENCE)
    assert "score" in str(caught.value)


@pytest.mark.parametrize(
    ("outcomes", "reference", "config", "named"),
    [
        (None, REFERENCE, DEFAULT_HISTORY_CONFIG, "prior_outcomes"),
        (
            [_Row(weight=FAIL_POINTS, verified=True)],
            REFERENCE,
            DEFAULT_HISTORY_CONFIG,
            "outcome_date",
        ),
        ([], "2026-10-01", DEFAULT_HISTORY_CONFIG, "reference_date"),
        ([], REFERENCE, 12.0, "config"),
        (
            [
                _Row(
                    outcome_date=REFERENCE,
                    weight=FAIL_POINTS,
                    verified="yes",
                )
            ],
            REFERENCE,
            DEFAULT_HISTORY_CONFIG,
            "verified",
        ),
    ],
    ids=["history", "record", "reference", "config", "the-gate"],
)
def test_every_refusal_the_signal_makes_reaches_the_caller(
    outcomes, reference, config, named
):
    """7.13's refusals are not swallowed by being composed with.

    **The name in the message is the one the failing argument has**, so a
    caller is told which of the three it got wrong rather than that the term
    could not be produced.
    """
    with pytest.raises(FlagValueError) as caught:
        apply_history(50.0, outcomes, reference, config)
    assert named in str(caught.value)
