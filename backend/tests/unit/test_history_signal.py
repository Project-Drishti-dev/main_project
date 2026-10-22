"""What the verified outcomes are still worth, and the bound they cannot pass.

Task 7.13 asks for ``history_signal(prior_outcomes, reference_date, config)``
that sums only verified outcomes, applies decay and clamps to a configurable
maximum magnitude, with two claims named in it: an unverified outcome
contributes nothing, and one old verified pass cannot move the band.  The two
headline tests at the top are those two claims and nothing else.

**The claim about the band is made about the bound, not about 34 and 69.**
The band numbers are uncalibrated on top of being unexercised end to end, so
the widths are *read* off :mod:`app.risk.config` and :mod:`app.risk.hard_rules`
rather than typed here and the assertions are ones that have to keep holding
when they move.  What makes them hold is ``D29``: each ``_MAX`` is the **last**
score of its own band, so a term that only *reduces* a score standing on one
of the four edges lands back inside that band, and the bottom edge lands back
on itself because 7.7 clamps.  **A term that raises a score crosses two of
those same edges, and one test below asserts exactly that**, so the headline
is a statement about a bounded signed term rather than a claim that the band
machinery is inert.

**The decay and the clamp do different jobs and both are pinned.**  The clamp
is what holds the total however many outcomes arrive; the decay is what makes
one old outcome worth a fraction of itself, and the headline says the fraction
with ``==`` rather than a tolerance, on the same grounds 7.12's three points
are asserted exactly.  A sum with the decay removed and a sum with the clamp
removed each fail a different test.

**Nothing here reads a clock.**  Every reference is the fixed
:data:`REFERENCE`, and the walks over ``history.py``'s own source hold the
absence in the form 7.13 needs it: ``datetime`` is imported for the *type* two
ages are measured between, and no call is ever made on it.
"""

import ast
import collections
import pathlib
from datetime import date, datetime, timedelta

import pytest

from app.risk import history as history_module
from app.risk.bands import to_band
from app.risk.clamp import clamp_score
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import FlagValueError
from app.risk.hard_rules import MAX_SCORE, MIN_SCORE
from app.risk.history import (
    DEFAULT_HISTORY_CONFIG,
    HISTORY_HALF_LIFE_DAYS,
    HISTORY_MAX_MAGNITUDE,
    HistoryConfig,
    PriorOutcome,
    decay,
    history_signal,
)

#: The committed calibration numbers, read off the module rather than typed,
#: so a retune moves every claim below with it -- 7.1's, 7.5's, 7.6's, 7.8's
#: and 7.12's suites read their vocabulary the same way.
HALF_LIFE = HISTORY_HALF_LIFE_DAYS
BOUND = HISTORY_MAX_MAGNITUDE

#: A fixed day to measure against.  **Written out rather than read from a
#: clock**, which is the whole of ``D12``'s point: a screening's history term
#: is a function of the reference the caller injects, so a replay of a
#: screening is a replay of its history term.
REFERENCE = date(2026, 10, 1)

#: The signed points one outcome is worth: a verified pass lowers suspicion
#: and a verified fail raises it, on the unit ``D21`` already answers in.
#: **Both are inside the bound**, so a test using them is asking about the
#: curve and the gate rather than about the clamp.
PASS_POINTS = -8.0
FAIL_POINTS = 10.0

#: How old "old" is, written as a multiple of the half-life rather than as a
#: day count so the claim stays "four half-lives old" when the policy number
#: moves.  Four is far enough that the decayed term is a rounding error
#: beside the bound, which is what the headline needs.
OLD_HALF_LIVES = 4

#: The four edges a score can be standing on: the two ends of the scale and
#: the two committed thresholds, each read rather than retyped.  These are the
#: scores the band claim is asked of, because ``D29`` puts every ``_MAX`` at
#: the *top* of its own band.
BAND_EDGES = (MIN_SCORE, LOW_MAX, REVIEW_MAX, MAX_SCORE)

#: How wide each of the three bands on the scale is, off the same names.
BAND_WIDTHS = (
    LOW_MAX - MIN_SCORE,
    REVIEW_MAX - LOW_MAX,
    MAX_SCORE - REVIEW_MAX,
)

#: Every attribute call that could be a clock of any kind, the same table
#: ``test_tier0_timing.py`` walks the runner with.
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

#: The three fields a prior outcome carries, and the only ones read.
OUTCOME_FIELDS = {"outcome_date", "weight", "verified"}

#: The words this package will not let a number carry, from 7.10 and 7.12.
DECISION_VOCABULARY = {
    "reject",
    "rejected",
    "deny",
    "denied",
    "decline",
    "verdict",
    "outcome_kind",
    "low",
    "review",
    "high",
}


class _Row:
    """A record carrying whatever fields it was handed, and nothing more.

    **Not a dataclass and not a flag**, because the point of it is that
    :func:`~app.risk.history.history_signal` reads three named fields off
    whatever it is handed.  Part 8's ledger is the caller this is written for,
    and an outcome read back from a database row is a namedtuple or a row
    object rather than a record this module built.
    """

    def __init__(self, **fields):
        self.__dict__.update(fields)


def _outcome(days_old=0, weight=PASS_POINTS, verified=True):
    """A :class:`PriorOutcome` ``days_old`` days before :data:`REFERENCE`."""
    return PriorOutcome(
        outcome_date=REFERENCE - timedelta(days=days_old),
        weight=weight,
        verified=verified,
    )


def _aged(half_lives, weight=PASS_POINTS, verified=True):
    """A verified outcome ``half_lives`` half-lives old."""
    return _outcome(half_lives * HALF_LIFE, weight, verified)


def _band_of(score):
    """The band ``score`` reads as once it is on the scale, as 7.14 will be."""
    return to_band(clamp_score(score))


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


def _imports():
    """``app`` and standard-library module names, walked rather than grepped."""
    imported, standard = set(), set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            names = {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {node.module or ""}
        else:
            continue
        for name in names:
            (imported if name.split(".")[0] == "app" else standard).add(name)
    return imported, standard


# --- the two claims the task names -----------------------------------------


@pytest.mark.parametrize(
    "weight",
    [PASS_POINTS, FAIL_POINTS, 0.0],
    ids=["pass", "fail", "nothing"],
)
@pytest.mark.parametrize(
    "days_old", [0, 180, 3650], ids=["today", "recent", "old"]
)
def test_an_unverified_outcome_contributes_nothing(weight, days_old):
    """4.8's one gate: an unaudited outcome is worth exactly zero.

    **Swept over both directions and every age**, because the gate is a claim
    about *the record* rather than about a number: a signal written as
    ``sum(o.weight * decay(...) for o in outcomes)`` passes a test that only
    ever offered a weightless record, and an unaudited outcome is exactly the
    one a screening must not be moved by.
    """
    unaudited = _outcome(days_old, weight, verified=False)

    assert history_signal([unaudited], REFERENCE) == 0.0
    assert history_signal([unaudited], REFERENCE) == history_signal([], REFERENCE)


def test_an_unverified_outcome_is_invisible_beside_a_verified_one():
    """Not merely zero on its own: it changes no other outcome's term.

    **Compared against the very same list with it removed**, which is the form
    a signal that *zeroed* an unaudited record would fail inside a set whose
    other members cancel, and the form a signal that *filtered* would pass
    only by accident of the arithmetic.
    """
    verified = [_aged(1), _aged(2, weight=FAIL_POINTS), _aged(3)]
    with_unverified = [
        _outcome(0, FAIL_POINTS, verified=False),
        *verified,
        _outcome(3650, PASS_POINTS, verified=False),
    ]

    assert history_signal(with_unverified, REFERENCE) == history_signal(
        verified, REFERENCE
    )


def test_one_old_verified_pass_cannot_move_the_band():
    """The task's second claim, and it is a claim about the bound.

    **Stated at the two levels that make it true.**  One old verified pass is
    worth ``PASS_POINTS * 0.5 ** 4`` exactly -- inside the bound, so the decay
    and not the clamp is what holds it down -- and even the *largest* term the
    bound allows cannot move a score standing on a band edge out of its own
    band.  The second half is the half that a retune would break, and it holds
    because ``D29`` puts every ``_MAX`` at the top of its own band: reducing
    from an edge lands back inside it, and reducing from the bottom edge lands
    back on itself because 7.7 clamps.
    """
    old_pass = _aged(OLD_HALF_LIVES, weight=PASS_POINTS)
    signal = history_signal([old_pass], REFERENCE)

    # The decay, pinned exactly rather than to a tolerance.
    assert signal == PASS_POINTS * 0.5**OLD_HALF_LIVES
    assert abs(signal) < BOUND

    # The whole term the bound allows, applied to every edge on the scale.
    loudest_pass = history_signal(
        [_aged(0, weight=-BOUND)], REFERENCE
    )
    assert loudest_pass == -BOUND
    for term in (signal, loudest_pass):
        for edge in BAND_EDGES:
            assert _band_of(edge + term) == _band_of(edge), edge


def test_the_bound_sits_below_the_narrowest_band():
    """The committed number the claim above rests on, against the committed pair.

    **The widths are read rather than typed**, so this holds at whatever
    ``D28``'s two thresholds are set to; the assertion is what makes the
    headline a property of the committed pair rather than of a number
    somebody typed twice.
    """
    assert BOUND < min(BAND_WIDTHS)
    assert BOUND < max(BAND_WIDTHS)


def test_a_verified_fail_can_move_a_band_edge():
    """The control: the headline is not a claim that the band never moves.

    A term that *raises* a score crosses two of the four edges at the bound,
    which is 4.8's other half -- repeat cases get continuity, and a confirmed
    bad history is worth raising a score for.  Without this test the headline
    could be passing because :func:`~app.risk.bands.to_band` were being fed
    something constant, rather than because a bounded pass cannot move an edge.
    """
    signal = history_signal([_aged(0, weight=BOUND)], REFERENCE)

    moved = [
        edge
        for edge in BAND_EDGES
        if _band_of(edge + signal) != _band_of(edge)
    ]

    assert moved, BAND_EDGES
    assert MIN_SCORE not in moved, "the clamp holds the bottom edge"
    assert MAX_SCORE not in moved, "the scale holds the top edge"


# --- the decay is applied ---------------------------------------------------


@pytest.mark.parametrize(
    ("half_lives", "expected"),
    [(0, 1.0), (1, 0.5), (2, 0.25), (4, 0.0625), (8, 0.00390625)],
    ids=["today", "one", "two", "four", "eight"],
)
def test_an_outcome_is_worth_its_weight_scaled_by_what_is_left_of_it(
    half_lives, expected
):
    """The task's "applies decay", through the sum rather than around it.

    **Exact equality rather than a tolerance**, for 7.12's reason: these are
    the dyadic points, so a sum written on 7.12's curve answers them bit for
    bit.  A history term scaled by anything else -- a linear ramp, a step at
    some age, a weight rounded to one decimal place -- fails here.
    """
    outcome = _aged(half_lives, weight=PASS_POINTS)

    assert history_signal([outcome], REFERENCE) == PASS_POINTS * expected


def test_a_fresh_verified_outcome_is_worth_all_of_itself():
    """At zero days the curve is ``1.0``, so the term is the weight unchanged.

    A signal starting below ``1.0`` would shrink every outcome by a constant
    nobody asked about, and the *age* of a verified outcome would not be what
    decides its worth.  **Every weight here is inside the bound**, so what is
    being asked is the curve and not the clamp.
    """
    for weight in (PASS_POINTS, 0.0, 6.0, -0.5, BOUND - 0.1):
        assert history_signal([_aged(0, weight=weight)], REFERENCE) == weight


def test_the_age_is_measured_from_the_reference_the_caller_named():
    """``D12``'s dependency, held by three references rather than one.

    The same outcome is worth three different amounts under three references,
    which is only possible if the subtraction is the caller's: a signal reading
    ``today()`` would answer all three identically, and would answer them
    differently tomorrow.
    """
    outcome = _aged(2, weight=FAIL_POINTS)
    later = 2 * HALF_LIFE

    assert history_signal([outcome], REFERENCE) == FAIL_POINTS * 0.25
    assert history_signal(
        [outcome], REFERENCE + timedelta(days=later)
    ) == FAIL_POINTS * 0.0625
    assert history_signal(
        [outcome], REFERENCE + timedelta(days=10 * HALF_LIFE)
    ) < FAIL_POINTS * 0.005


def test_the_reference_moves_one_day_at_a_time():
    """A whole day is the unit an age is measured in.

    Yesterday and today are one day apart whatever hour either was written
    at, so the two answers differ by exactly one day's worth of decay and by
    nothing else.
    """
    yesterday = _outcome(1, weight=FAIL_POINTS)

    today = history_signal([yesterday], REFERENCE)
    the_day_before = history_signal([yesterday], REFERENCE - timedelta(days=1))

    assert today < the_day_before
    assert today / the_day_before == pytest.approx(decay(1, HALF_LIFE))


def test_the_half_life_the_config_names_is_the_one_that_is_used():
    """The first calibration parameter, and it is not the committed one.

    **A second rate on purpose**: a signal that ignored ``config`` and used
    :data:`HISTORY_HALF_LIFE_DAYS` throughout would satisfy every other test
    in this file.
    """
    fast = HistoryConfig(half_life_days=30.0)
    outcome = _outcome(30, weight=FAIL_POINTS)

    assert history_signal([outcome], REFERENCE, fast) == FAIL_POINTS * 0.5
    assert history_signal([outcome], REFERENCE) != FAIL_POINTS * 0.5


def test_a_slow_half_life_keeps_an_outcome_worth_more():
    """The rate is a policy number and it moves in the expected direction.

    A signal answering the same term for every half-life would make
    :attr:`HistoryConfig.half_life_days` -- and the retune ``D28``'s reason is
    about -- a number nothing reads.
    """
    outcome = _outcome(90, weight=FAIL_POINTS)
    answers = [
        history_signal([outcome], REFERENCE, HistoryConfig(half_life_days=rate))
        for rate in (180.0, 30.0, 10.0)
    ]

    assert answers[0] > answers[1] > answers[2]


# --- the bound --------------------------------------------------------------


@pytest.mark.parametrize(
    "weight", [BOUND, 65.0, MAX_SCORE], ids=["bound", "heavy", "the-scale"]
)
def test_the_bound_holds_however_many_outcomes_arrive(weight):
    """The task's "clamps to a configurable maximum magnitude", at the top.

    **Five hundred fresh verified fails**, each worth more than the bound on
    its own, so an unbounded sum answers 500 times the weight and a bounded
    one answers the bound.  A sum that stopped early, divided rather than
    clamped, or clamped to something else is caught by the ``==``.
    """
    outcomes = [_aged(0, weight=weight) for _ in range(500)]

    assert history_signal(outcomes, REFERENCE) == BOUND


def test_the_bound_is_symmetric_and_never_inverts_a_sign():
    """A verified pass is bounded below by the number it is bounded above by.

    Two mutants fail here and nowhere else: a clamp written as one comparison
    leaves a negative total unbounded, and one written as ``min(abs(total),
    bound)`` answers a large pile of verified passes with a *positive* number
    -- a history layer that raises a score because a traveller was confirmed
    genuine.
    """
    many_passes = [_aged(0, weight=-60.0) for _ in range(500)]
    many_fails = [_aged(0, weight=60.0) for _ in range(500)]

    assert history_signal(many_passes, REFERENCE) == -BOUND
    assert history_signal(many_fails, REFERENCE) == BOUND


def test_a_total_inside_the_bound_is_handed_back_to_the_last_bit():
    """A clamp and not a rescale, on 7.7's reason.

    Two verified outcomes whose terms cancel exactly answer ``0.0`` and not a
    rounding of it, and a total a thousandth inside the bound is not nudged up
    to it.
    """
    cancelling = [_aged(0, weight=FAIL_POINTS), _aged(0, weight=-FAIL_POINTS)]
    just_inside = [_aged(0, weight=BOUND - 0.001)]

    assert history_signal(cancelling, REFERENCE) == 0.0
    assert history_signal(just_inside, REFERENCE) == BOUND - 0.001


def test_the_bound_the_config_names_is_the_one_that_is_applied():
    """The second calibration parameter, and it is not the committed one.

    **The history is long enough to overflow either bound**, so a signal
    ignoring ``config`` would answer the committed number to both.
    """
    outcomes = [_aged(0, weight=FAIL_POINTS) for _ in range(5)]

    assert (
        history_signal(outcomes, REFERENCE, HistoryConfig(max_magnitude=1.0))
        == 1.0
    )
    assert (
        history_signal(
            outcomes, REFERENCE, HistoryConfig(max_magnitude=MAX_SCORE)
        )
        == 5 * FAIL_POINTS
    )
    assert history_signal(outcomes, REFERENCE) == BOUND


def test_the_committed_defaults_are_the_config_a_caller_gets_for_nothing():
    """``HISTORY_HALF_LIFE_DAYS`` and ``HISTORY_MAX_MAGNITUDE``, by identity.

    ``D28``'s reason: a bound or a rate a deployment could retune would let
    what an old outcome is worth change with nothing recording it, so neither
    is an environment variable and the default is one committed record.
    **Identity rather than equality** for the rate -- a module rebuilding the
    record per call would pass every arithmetic assertion above and still be a
    policy answer that moves under a running service.
    """
    assert DEFAULT_HISTORY_CONFIG is history_module.DEFAULT_HISTORY_CONFIG
    assert isinstance(DEFAULT_HISTORY_CONFIG, HistoryConfig)
    assert DEFAULT_HISTORY_CONFIG.half_life_days is HISTORY_HALF_LIFE_DAYS
    assert DEFAULT_HISTORY_CONFIG.max_magnitude == HISTORY_MAX_MAGNITUDE
    assert HistoryConfig() == DEFAULT_HISTORY_CONFIG


def test_the_config_is_taken_positionally_and_by_keyword_alike():
    """The signature is the task's, and ``config`` is not keyword-only.

    Written as an inspection rather than a call, because the claim is about
    what the three names *are*: a fourth argument is a dependency nothing has
    asked for, and ``D32``'s reason that the half-life is committed rather
    than injected argues against opening a hole here.
    """
    assert history_signal.__code__.co_varnames[
        : history_signal.__code__.co_argcount
    ] == ("prior_outcomes", "reference_date", "config")

    outcomes = [_aged(0, weight=FAIL_POINTS)]
    assert history_signal(
        outcomes, REFERENCE, HistoryConfig()
    ) == history_signal(outcomes, REFERENCE, config=HistoryConfig())


# --- the sum ----------------------------------------------------------------


def test_an_empty_history_is_zero_rather_than_a_missing_answer():
    """No prior outcomes is the empty sum, on 7.5's convention.

    **Not a refusal and not ``None``**: a first-time traveller is the common
    case rather than a fault, and 7.14 is what adds this ``0.0`` to a score.
    """
    assert history_signal([], REFERENCE) == 0.0
    assert history_signal((), REFERENCE) == 0.0
    assert history_signal(iter(()), REFERENCE) == 0.0
    assert isinstance(history_signal([], REFERENCE), float)


def test_a_verified_fail_and_a_verified_pass_move_opposite_ways():
    """One signed number per outcome, which is what makes the total one sum.

    Two outcomes of equal magnitude and equal age cancel exactly, and the
    answer is neither of them: a history term whose sign depended on which
    kind of outcome arrived last would not be a sum at all.
    """
    fail = _aged(1, weight=FAIL_POINTS)
    passed = _aged(1, weight=-FAIL_POINTS)

    assert history_signal([fail], REFERENCE) == -history_signal(
        [passed], REFERENCE
    )
    assert history_signal([fail, passed], REFERENCE) == 0.0
    assert history_signal([passed, fail], REFERENCE) == 0.0


def test_the_answer_does_not_depend_on_the_order_the_outcomes_arrived_in():
    """``math.fsum`` is the accumulator, for 7.5's reason.

    Twenty-four terms of mixed sign, weight and age, summed forwards, then
    backwards, then rotated: an accumulator that added in arrival order
    answers the three differently in the last bits, and a replay has to be a
    replay.
    """
    outcomes = [
        _aged(index % 5, weight=PASS_POINTS if index % 3 else FAIL_POINTS)
        for index in range(24)
    ]
    orders = (outcomes, outcomes[::-1], outcomes[7:] + outcomes[:7])

    assert len({history_signal(order, REFERENCE) for order in orders}) == 1


def test_a_generator_of_outcomes_is_consumed_once():
    """Any iterable will do, and is read once, on 7.6's convention.

    **The sequence is never asked whether it is truthy**, because a generator
    is truthy whether or not it yields anything.
    """
    outcomes = (_aged(2, weight=FAIL_POINTS) for _ in range(4))

    assert history_signal(outcomes, REFERENCE) == 4 * FAIL_POINTS * 0.25


def test_any_record_carrying_the_three_fields_is_summed():
    """The accessor is the seam, so a stored outcome is not rebuilt first."""
    row = _Row(
        outcome_date=REFERENCE, weight=FAIL_POINTS, verified=True
    )
    named = collections.namedtuple("Named", sorted(OUTCOME_FIELDS))

    assert history_signal([row], REFERENCE) == FAIL_POINTS
    assert (
        history_signal([named(**row.__dict__)], REFERENCE) == FAIL_POINTS
    )


def test_nothing_the_caller_handed_in_is_amended():
    """The record and the config come back exactly as they went in.

    **Frozen on both**, on ``D31``'s reason: a term an officer is shown must
    not be able to change after the total was computed from it.
    """
    outcome = _aged(1)
    config = HistoryConfig()

    history_signal([outcome], REFERENCE, config)

    assert (outcome, config) == (_aged(1), HistoryConfig())
    with pytest.raises(AttributeError):
        outcome.weight = 99.0
    with pytest.raises(AttributeError):
        config.max_magnitude = 99.0


def test_the_same_history_always_answers_the_same_signal():
    """Pure: no file, no randomness, no hidden state and no clock.

    **Compared for equality**, which is the whole of the claim for a computed
    float: a replay of a screening has to be a replay of its history term.
    """
    outcomes = [_aged(index % 4, weight=FAIL_POINTS) for index in range(6)]

    assert history_signal(outcomes, REFERENCE) == history_signal(
        outcomes, REFERENCE
    )
    assert history_signal(
        outcomes, REFERENCE, HistoryConfig()
    ) == history_signal(outcomes, REFERENCE, HistoryConfig())


def test_the_module_exports_the_layer_and_nothing_more():
    """``__all__`` is the whole surface: a curve, a bound, and what reads them.

    Nothing here computes a score out of a sum, holds a band or writes a
    result: 7.14's ``apply_history`` adds this module's own bounded term to a
    score and is the one name added by it, and 7.15 is what puts a score in a
    record.
    """
    assert history_module.__all__ == [
        "DEFAULT_HISTORY_CONFIG",
        "HISTORY_HALF_LIFE_DAYS",
        "HISTORY_MAX_MAGNITUDE",
        "HistoryConfig",
        "PriorOutcome",
        "apply_history",
        "decay",
        "history_signal",
    ]


# --- what it refuses, and what it may not reach -----------------------------


@pytest.mark.parametrize(
    "missing", sorted(OUTCOME_FIELDS), ids=sorted(OUTCOME_FIELDS)
)
def test_a_record_missing_one_of_the_three_fields_is_refused(missing):
    """A record that cannot answer the sum is refused, not skipped.

    On 7.6's rule that a record carrying no ``id`` is refused rather than
    passed over: a screening stops rather than being scored from a record that
    is missing half of what it needs.
    """
    partial = _Row(
        **{
            field: value
            for field, value in (
                ("outcome_date", REFERENCE),
                ("weight", FAIL_POINTS),
                ("verified", True),
            )
            if field != missing
        }
    )

    with pytest.raises(FlagValueError) as caught:
        history_signal([partial], REFERENCE)
    assert missing in str(caught.value)


@pytest.mark.parametrize(
    "not_verified",
    [None, 1, 0, "yes", "", "False", 1.0],
    ids=["none", "one", "zero", "yes", "empty", "false-str", "one-float"],
)
def test_verified_is_a_bool_and_not_a_truthy_value(not_verified):
    """The gate is a type, so ``1`` cannot stand in for an audited outcome.

    **Every truthy spelling is swept**, because ``verified=1`` is the mutant
    this claim exists to catch: a signal written as ``if outcome.verified:``
    admits it, and an unaudited outcome would then reach the sum in full.
    """
    with pytest.raises(FlagValueError):
        PriorOutcome(
            outcome_date=REFERENCE,
            weight=FAIL_POINTS,
            verified=not_verified,
        )

    with pytest.raises(FlagValueError) as caught:
        history_signal(
            [
                _Row(
                    outcome_date=REFERENCE,
                    weight=FAIL_POINTS,
                    verified=not_verified,
                )
            ],
            REFERENCE,
        )
    assert "verified" in str(caught.value)


@pytest.mark.parametrize(
    "bad_weight",
    [
        None,
        True,
        "8",
        float("nan"),
        float("inf"),
        float("-inf"),
        object(),
        MAX_SCORE + 0.5,
        -MAX_SCORE - 0.5,
        1e9,
    ],
    ids=[
        "none",
        "true",
        "string",
        "nan",
        "inf",
        "neg-inf",
        "object",
        "just-over",
        "just-under",
        "huge",
    ],
)
def test_a_weight_that_is_not_points_on_the_scale_is_refused(bad_weight):
    """A ``nan`` poisons an accumulator silently, so it is refused here.

    ``math.fsum`` answers ``nan`` for a total containing one and it compares
    false against every bound, so an unbounded signal would hand a ``nan``
    straight through the clamp.
    """
    with pytest.raises(FlagValueError) as caught:
        history_signal([_aged(0, weight=bad_weight)], REFERENCE)
    assert "weight" in str(caught.value)


@pytest.mark.parametrize(
    "bad_date",
    [None, "2026-10-01", 20261001, datetime(2026, 10, 1), timedelta(days=1)],
    ids=["none", "string", "int", "timestamp", "timedelta"],
)
def test_an_outcome_date_that_is_not_a_plain_date_is_refused(bad_date):
    """A ``datetime`` is a ``date`` by inheritance and still not one here.

    Subtracting one from a ``date`` raises ``TypeError``, which is not the
    ``ValueError`` a caller around the scoring is catching, and a string is a
    date somebody meant to write rather than one anybody holds.
    """
    with pytest.raises(FlagValueError) as caught:
        history_signal(
            [_Row(outcome_date=bad_date, weight=FAIL_POINTS, verified=True)],
            REFERENCE,
        )
    assert "outcome_date" in str(caught.value)


@pytest.mark.parametrize(
    "bad_reference",
    [None, "2026-10-01", 20261001, datetime(2026, 10, 1), timedelta(days=1)],
    ids=["none", "string", "int", "timestamp", "timedelta"],
)
def test_a_reference_that_is_not_a_plain_date_is_refused(bad_reference):
    """``D12``'s dependency is checked like every other argument.

    **A refused reference rather than a defaulted one**: a signal that reached
    for ``today()`` when the caller named nothing would make the answer
    depend on the day it ran, which is the absence the walks below hold.
    """
    with pytest.raises(FlagValueError) as caught:
        history_signal([_aged(0)], bad_reference)
    assert "reference_date" in str(caught.value)


def test_a_verified_outcome_dated_after_the_reference_is_refused():
    """A negative age is a caller's fault, from 7.12's own refusal.

    Answered rather than refused, the weight would come back above ``1.0`` and
    the term would be inflated by a record whose clock is wrong -- so the
    refusal propagates out of :func:`~app.risk.history.decay` unchanged.
    """
    dated_later = PriorOutcome(
        outcome_date=REFERENCE + timedelta(days=1),
        weight=FAIL_POINTS,
        verified=True,
    )

    with pytest.raises(FlagValueError):
        history_signal([dated_later], REFERENCE)


def test_an_unverified_outcome_dated_after_the_reference_is_not_refused():
    """The other side of the gate: a shape is checked and a number is not used.

    An unaudited record's date contributes nothing, so refusing a screening
    over one would be a caller being told about a number the sum never
    touches.  **The record is still checked for shape** -- it has to be a
    date, just not a usable one.
    """
    dated_later = PriorOutcome(
        outcome_date=REFERENCE + timedelta(days=1),
        weight=FAIL_POINTS,
        verified=False,
    )

    assert history_signal([dated_later], REFERENCE) == 0.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("half_life_days", 0.0),
        ("half_life_days", -30.0),
        ("half_life_days", float("nan")),
        ("half_life_days", None),
        ("half_life_days", "180"),
        ("max_magnitude", 0.0),
        ("max_magnitude", -1.0),
        ("max_magnitude", MAX_SCORE + 1.0),
        ("max_magnitude", float("nan")),
        ("max_magnitude", True),
    ],
    ids=[
        "zero-half-life",
        "negative-half-life",
        "nan-half-life",
        "none-half-life",
        "string-half-life",
        "zero-bound",
        "negative-bound",
        "bound-over-scale",
        "nan-bound",
        "bool-bound",
    ],
)
def test_both_calibration_parameters_are_checked_where_they_are_built(
    field, value
):
    """A rate that is not a rate and a bound that bounds nothing are refused.

    **At construction rather than at the first screening**, so a caller finds
    out where they wrote the number.  A zero bound would answer every
    screening ``0.0`` and read as a policy that had been switched off.
    """
    with pytest.raises(FlagValueError) as caught:
        HistoryConfig(**{field: value})
    assert field in str(caught.value)


@pytest.mark.parametrize(
    "bad_config",
    [
        None,
        {},
        {"half_life_days": 180.0, "max_magnitude": 12.0},
        (180.0, 12.0),
        "HistoryConfig()",
        12.0,
    ],
    ids=["none", "dict", "mapping", "tuple", "string", "float"],
)
def test_a_config_that_is_not_a_config_is_refused(bad_config):
    """A mapping is refused rather than read.

    **Which is what makes the two names a committed record** rather than a
    convention a caller can spell four ways: a retune is an edit to the
    dataclass and a ``RULESET_VERSION`` bump, on ``D28``'s reason.
    """
    with pytest.raises(FlagValueError) as caught:
        history_signal([_aged(0)], REFERENCE, bad_config)
    assert "config" in str(caught.value)


@pytest.mark.parametrize(
    "bad_history",
    [None, "verified", b"verified", 7],
    ids=["none", "str", "bytes", "int"],
)
def test_a_history_that_is_not_a_collection_of_records_is_refused(bad_history):
    """A bare string is refused rather than iterated, on 7.6's reason.

    ``"verified"`` iterated is nine characters, each of which is then refused
    a field at a time -- a ``TypeError``-shaped answer to a question with one
    right answer.
    """
    with pytest.raises(FlagValueError) as caught:
        history_signal(bad_history, REFERENCE)
    assert "prior_outcomes" in str(caught.value)


def test_a_refusal_names_the_field_and_never_the_value():
    """``D6``'s rule for a message: the field and the type, never the number.

    An outcome's date is derived from a document's own history, and a message
    carrying one would put identity data in a log line or an exception body.
    """
    with pytest.raises(FlagValueError) as caught:
        history_signal([_aged(0, weight=float("nan"))], REFERENCE)
    assert "weight" in str(caught.value)
    assert "nan" not in str(caught.value)


def test_the_module_reads_no_clock():
    """No calendar and no stopwatch, in any form, in this module's own source.

    **The walk is repeated from 7.12 rather than assumed**, for ``D12``'s
    reason: 7.13 is the function whose whole job is turning a date into an
    age, so it is the most likely place in the package to reach a clock.
    ``datetime`` is imported -- for the *type* two ages are measured between
    -- and the first assertion is what says no call is ever made on it.
    """
    tree = _tree()

    assert not [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        if node.func.attr in CLOCK_CALLS
    ]

    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported & {"time", "calendar", "zoneinfo"} == set()
    assert {"datetime", "math"} <= imported


def test_history_signal_reaches_no_clock_of_its_own():
    """Scoped to this task's function rather than to the whole module.

    **The narrower walk is the stronger one here**, because 7.12's module
    walk can no longer be module-wide: this file legitimately imports
    ``datetime`` for the type of an outcome's date, so the claim that has to
    be made is the one about the code that computes the age.
    """
    reached = {
        node.func.attr
        for node in ast.walk(_function("history_signal"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert reached <= {"pow", "fsum"}


def test_history_signal_reads_the_three_fields_and_nothing_else():
    """The accessor names are the whole of what a record contributes.

    Held over the *call sites* of ``_field`` rather than over the attributes
    reached, because ``_field`` reads a field whose name is a variable.  A
    signal that went on to read a fourth one -- an identity, a screening id --
    would be pulling identity data into a score, and it would be pulled one
    ``getattr`` at a time.
    """
    read = {
        node.args[1].value
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_field"
        and len(node.args) == 2
        and isinstance(node.args[1], ast.Constant)
    }

    assert read == OUTCOME_FIELDS


def test_decay_is_still_the_same_arithmetic_over_two_numbers():
    """7.12's narrow walk, kept narrow on purpose.

    ``decay`` reaches no attribute of any object but ``math.pow`` and reads no
    record; that claim was true of the module when the module held nothing
    else, and it is still true of the function now that it holds a signal.
    """
    reached = {
        node.func.attr
        for node in ast.walk(_function("decay"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert reached <= {"pow"}


def test_the_module_imports_the_package_and_nothing_from_the_pipeline():
    """The dependency set, walked rather than grepped.

    ``D6``'s one-way rule keeps a tier out of :mod:`app.risk`, and an
    outcome's date read off a tier's own readings would put one there.
    """
    imported, standard = _imports()

    assert imported == {"app.risk.flags", "app.risk.hard_rules"}
    assert standard == {"collections.abc", "dataclasses", "datetime", "math"}


def test_the_module_imports_the_scale_and_not_the_band_thresholds():
    """``MAX_SCORE`` is 7.6's; ``LOW_MAX`` and ``REVIEW_MAX`` are 7.8's.

    The bound is a magnitude on the scale, so it is held to the scale's own
    end.  **The band thresholds are not imported**, so this module holds no
    idea where a band begins -- that is 7.9's question, asked of a total.
    """
    imported = {
        alias.name
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
        and node.module == "app.risk.hard_rules"
        for alias in node.names
    }

    assert imported == {"MAX_SCORE", "_score"}


def test_the_signal_carries_no_band_and_no_decision_of_its_own():
    """``D31``'s split, one term along from the contribution.

    The history term is the first thing that can move a total away from the
    sum of the rows beside it, so the last thing this module should grow is a
    mapping from its own arithmetic onto what a score *means*.  The vocabulary
    is the one 7.12's suite already walks this module with, docstrings and all.
    """
    tree = _tree()
    vocabulary = {
        word.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for word in node.value.replace(".", " ").replace("-", " ").split()
    }
    vocabulary |= {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    vocabulary |= {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    vocabulary |= {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    vocabulary |= {
        node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)
    }
    vocabulary |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    vocabulary |= {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert not {
        word
        for word in vocabulary
        if word.lower().strip("_").isalpha()
    } & DECISION_VOCABULARY
