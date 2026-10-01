"""Half as much every half-life, and no clock anywhere in it.

Task 7.12 asks for ``decay(age_days, half_life_days) -> float`` with tests at
0 days, exactly one half-life and two half-lives, and the three headline tests
below are those three points at a half-life read off the module rather than
typed in here.  They are asserted with ``==`` and not with a tolerance, because
``0.5 ** 1`` and ``0.5 ** 2`` are ``0.5`` and ``0.25`` exactly in binary
floating point: a decay answering ``0.5 ** (1 + 1e-12)`` would be correct to
twelve places and wrong.

**The two half-lives are not redundant with the first two.**  4.8's own claim
is that an old outcome counts for *less*, which a linear falloff satisfies at
every age -- so the one point that separates a half-life curve from a straight
line, a ramp, or a single step at some threshold, is the third.  A decay that
halved once and then flattened would pass at 1 and fail at 2.

**An age goes in; a day does not come out.**  ``decay`` takes the difference
between two dates the caller already holds, which is why 7.13's
``history_signal`` takes a ``reference_date`` and this module reaches no clock
of its own.  A decay that read ``today()`` would make a screening's score
depend on the day it ran, so the walk below holds the absence over this
module's own source the way ``test_tier0_timing.py`` holds it over the
runner's, and ``test_review_never_rejects.py``'s walk over ``app/`` will hold
it again if a clock is ever added.

**Every number a caller passes is checked, and checked once.**  Both arguments
go through 7.6's ``_score``, the package's single validation of a number, so a
``nan`` -- which compares false against every bound and would pass a decay
written as two comparisons -- is refused instead of answering a weight.  A
non-positive half-life and a negative age are refused for the reasons their own
module gives: the first is a division by zero or an answer of ``1.0`` forever,
and the second is an outcome dated after the reference.
"""

import ast
import math
import pathlib

import pytest

from app.risk import history as history_module
from app.risk.flags import FlagValueError
from app.risk.history import HISTORY_HALF_LIFE_DAYS, decay

#: A half-life read off the module rather than written here, so a retune moves
#: the headline tests' own arithmetic with it -- 7.1's, 7.5's and 7.6's suites
#: read their vocabulary the same way.
HALF_LIFE = HISTORY_HALF_LIFE_DAYS

#: The three points the task names, as multiples of the half-life.  Written as
#: multiples rather than as day counts so the claim stays "zero, one, two" when
#: the policy number moves.
ZERO_DAYS = 0
ONE_HALF_LIFE = 1
TWO_HALF_LIVES = 2

#: The answer each of those three must give.  0.5 and 0.25 are dyadic, so the
#: decay at one and at two half-lives is exact and needs no tolerance.
AT_ZERO_DAYS = 1.0
AT_ONE_HALF_LIFE = 0.5
AT_TWO_HALF_LIVES = 0.25

#: A second half-life, for the claims that are about the *shape* of the answer
#: rather than its value at one rate: a decay that hard-codes one number would
#: pass the three headline tests and fail this one.
OTHER_HALF_LIFE = 30.0

#: Every attribute call that could be a clock of any kind.  The same table
#: ``test_tier0_timing.py`` walks the runner with, kept whole here rather than
#: narrowed: this module has no clock of any kind to allow, so the calendar
#: names and the stopwatch names are the same list.
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


def _names(tree: ast.AST) -> set[str]:
    """Every identifier and string the tree holds, docstrings included."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.alias):
            found.add(node.name.rsplit(".", 1)[-1])
            found.add(node.asname or "")
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.update(node.value.replace(".", " ").replace("-", " ").split())
    found.discard("")
    return found


# --- the three points the task names --------------------------------------


@pytest.mark.parametrize(
    ("half_life", "half_lives", "expected"),
    [
        pytest.param(HALF_LIFE, ZERO_DAYS, AT_ZERO_DAYS, id="zero-days"),
        pytest.param(HALF_LIFE, ONE_HALF_LIFE, AT_ONE_HALF_LIFE, id="one"),
        pytest.param(HALF_LIFE, TWO_HALF_LIVES, AT_TWO_HALF_LIVES, id="two"),
    ],
)
def test_the_three_points_the_task_names_are_answered_exactly(
    half_life, half_lives, expected
):
    """0 days is all of it, one half-life is half, two are a quarter.

    **Exact equality rather than a tolerance**, which is the whole claim:
    ``0.5 ** 1`` and ``0.5 ** 2`` are representable, so a decay built on this
    curve answers these three numbers bit for bit.  An exponential written
    ``exp(-ln(2) * t)`` answers ``0.49999999999999994`` for one half-life --
    correct to fifteen places, and a dashboard rendering ``0.4999999999999999``
    next to a half-life of 180 days.
    """
    assert decay(half_lives * half_life, half_life) == expected


def test_an_outcome_of_today_is_worth_all_of_itself():
    """The curve starts at 1.0, so decay multiplies rather than discounts.

    A history term that started below ``1.0`` would shrink every outcome by a
    constant nobody had asked about, and the age of a *verified* outcome would
    not be what decides its weight.
    """
    assert decay(0, HALF_LIFE) == AT_ZERO_DAYS
    assert decay(0.0, HALF_LIFE) == AT_ZERO_DAYS


def test_a_half_life_halves_and_two_halve_twice():
    """The task's second and third points, also held against a second rate.

    **The rate is varied on purpose.**  7.12 names one function of two
    arguments, so a decay that ignored ``half_life_days`` -- returning ``0.5``
    for every positive age, or ``0.25`` -- would satisfy the three headline
    tests at the committed rate alone.  Thirty days rather than the committed
    one is what makes the second argument load-bearing.
    """
    assert decay(OTHER_HALF_LIFE, OTHER_HALF_LIFE) == AT_ONE_HALF_LIFE
    assert decay(2 * OTHER_HALF_LIFE, OTHER_HALF_LIFE) == AT_TWO_HALF_LIVES
    assert decay(2 * HALF_LIFE, HALF_LIFE) == AT_TWO_HALF_LIVES


# --- the shape of the curve -------------------------------------------------


@pytest.mark.parametrize("age_in_half_lives", [0, 1, 2, 3, 4, 8, 16])
def test_the_curve_is_a_half_life_and_not_a_ramp(age_in_half_lives):
    """Each further half-life halves again, all the way down.

    Held as ``decay(n * h) == 0.5 ** n`` rather than as three named points:
    a linear falloff from 1.0 passes 0 days, one half-life and two half-lives
    only if it happens to be steep enough, and a single step fails at three.
    The exponent is what makes the sequence *geometric* -- ``0.5 ** 8`` is
    ``1/256`` and ``0.5 ** 16`` is ``1/65536``, so an outcome sixteen
    half-lives old counts for fifteen thousandths of itself.
    """
    assert decay(age_in_half_lives * HALF_LIFE, HALF_LIFE) == math.pow(
        0.5, age_in_half_lives
    )


def test_an_older_outcome_is_never_worth_more_than_a_fresher_one():
    """4.8's own sentence: an old outcome counts for less than a recent one.

    **Non-increasing, not strictly decreasing**, because the curve reaches
    ``0.0`` once an age is thousands of half-lives past and every older age is
    then equal to it rather than below it.  The strict claim is held over the
    range where the answer is not yet exhausted, below.
    """
    ages = [0, 1, 7, HALF_LIFE, 365, 1000, 5000, 36500]
    weights = [decay(age, HALF_LIFE) for age in ages]

    assert all(
        later <= earlier for earlier, later in zip(weights, weights[1:])
    ), dict(zip(ages, weights))


def test_the_curve_still_falls_before_it_reaches_zero():
    """Over the range a real outcome can occupy, every day costs something.

    The sweep above is allowed to flatten at ``0.0``; this one is not, because
    a decay that reached zero inside a year would make 7.13's signal vanish
    rather than fade, and "counts for less" is not the same claim as "counts
    for nothing".
    """
    ages = range(0, 366)
    weights = [decay(age, HALF_LIFE) for age in ages]

    assert all(later < earlier for earlier, later in zip(weights, weights[1:]))
    assert weights[-1] > 0.0


def test_a_longer_half_life_keeps_an_outcome_worth_more():
    """The rate is a policy number and it moves in the expected direction.

    A decay that answered the same weight for every half-life would make
    ``HISTORY_HALF_LIFE_DAYS`` -- and the retune ``D28``'s reasoning is about
    -- a number nothing reads.
    """
    assert decay(90, 180) > decay(90, 30)
    assert decay(90, 30) > decay(90, 10)


def test_the_two_arguments_are_the_only_ones():
    """The signature is the task's, and no third input could answer a day.

    Written as an inspection rather than a call, because the claim is about
    what *cannot* be passed: a ``reference_date`` here would be 7.13's
    dependency in the wrong module, and a default the caller never overrides
    is a policy number nobody chose.
    """
    assert decay.__code__.co_varnames[: decay.__code__.co_argcount] == (
        "age_days",
        "half_life_days",
    )


# --- what the answer is, and is not ----------------------------------------


def test_the_answer_is_a_float_whatever_integer_types_arrived():
    """A number, not a numpy integer or an ``int``, on every path.

    7.13 sums these and 7.14 adds the sum to a score, so a decay returning
    whatever integer type it was handed would put a second numeric type into
    the arithmetic 7.5 holds to ``float``.
    """
    for age, half_life in ((0, HALF_LIFE), (HALF_LIFE, HALF_LIFE), (365, 30)):
        for left, right in ((int(age), int(half_life)), (float(age), half_life)):
            answer = decay(left, right)
            assert type(answer) is float, (left, right, answer)


def test_the_answer_is_a_weight_between_zero_and_one():
    """In ``[0, 1]``, including at the extremes where it is exactly one of them.

    The interval is written out rather than imported, and deliberately so:
    this is a *fraction of an outcome*, not a flag's measured strength, so
    ``D24``'s ``[0, 1]`` is ``normalise_value``'s contract rather than one
    every number in the package happens to share.
    """
    for age in (0, 1, HALF_LIFE, 2 * HALF_LIFE, 365, 3650, 365000):
        weight = decay(age, HALF_LIFE)
        assert 0.0 <= weight <= 1.0, age

    assert decay(0, HALF_LIFE) == 1.0
    assert decay(365000, HALF_LIFE) == 0.0


def test_the_answer_is_a_ratio_and_not_a_score():
    """Nothing here clamps to the scale or crosses a band threshold.

    ``clamp_score(1.0)`` is ``1.0`` and ``clamp_score(0.5)`` is ``0.5``, so a
    clamp would pass every case in this file while adding the wrong
    dependency: 7.7's ends are the score scale's, and a decay factor is not a
    score.  The import walk below holds that nothing from the scale is reached.
    """
    from app.risk.clamp import MAX_SCORE, clamp_score

    assert MAX_SCORE == 100.0
    assert decay(0, HALF_LIFE) <= MAX_SCORE
    assert clamp_score(decay(2 * HALF_LIFE, HALF_LIFE)) == AT_TWO_HALF_LIVES


def test_the_same_two_numbers_always_answer_the_same_weight():
    """Pure: no file, no randomness, no clock, no hidden state.

    **Compared for equality, and the constant compared for identity.**  A
    weight is computed, so two calls returning an equal ``float`` is the whole
    of the purity claim -- a replay of a screening has to be a replay of its
    history term and not a number that moved between two reads of the same
    input.  Identity belongs on :data:`HISTORY_HALF_LIFE_DAYS` instead: that
    one is a constant rather than a reading, so a module that recomputed it
    per call could pass every decay assertion above and still be a policy
    number that moves under a running service.
    """
    for age in (0, 45, HALF_LIFE, 1234):
        assert decay(age, HALF_LIFE) == decay(age, HALF_LIFE)

    assert HISTORY_HALF_LIFE_DAYS is history_module.HISTORY_HALF_LIFE_DAYS


def test_the_committed_half_life_is_the_default_and_is_read_not_retyped():
    """One policy number, in this module, and no second copy of it.

    ``D28``'s reason: a decay rate a deployment could retune would let what an
    old outcome is worth change with nothing recording the change, so the
    default is a constant here, there is no environment variable for it, and
    every claim in this file that needs a half-life reads this name.
    """
    assert isinstance(HISTORY_HALF_LIFE_DAYS, float)
    assert HISTORY_HALF_LIFE_DAYS > 0.0
    assert decay(0) == decay(0, HISTORY_HALF_LIFE_DAYS)
    assert decay(HISTORY_HALF_LIFE_DAYS) == AT_ONE_HALF_LIFE

    source = pathlib.Path(history_module.__file__).read_text(encoding="utf-8")
    assert f"{HISTORY_HALF_LIFE_DAYS:g}" not in source.replace(
        "HISTORY_HALF_LIFE_DAYS = 180.0", ""
    )


def test_the_module_exports_the_decay_and_its_half_life():
    """The curve and its rate are exported, and read off ``__all__``.

    **The whole list is no longer two names**: 7.13 added ``history_signal``,
    the record it sums and the bound it clamps to, and
    ``test_history_signal.py`` holds the full list exactly.  What is asserted
    here is the narrower claim this file owns -- the decay and the rate it is
    read with are both named -- so a curve that lost its own export would fail
    the file that wrote it rather than only the one that followed.
    """
    assert {"HISTORY_HALF_LIFE_DAYS", "decay"} <= set(history_module.__all__)


# --- what it refuses, and what it may not reach ----------------------------


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param("180", id="string"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="inf"),
        pytest.param(-float("inf"), id="neg-inf"),
        pytest.param(object(), id="object"),
    ],
)
@pytest.mark.parametrize("position", ["age", "half_life"])
def test_a_malformed_number_is_refused_in_either_position(bad, position):
    """Neither argument can be something other than a finite real number.

    **Both positions are swept** because one of them divides: a ``nan``
    half-life would make every weight a ``nan``, and a ``nan`` age would
    answer ``nan`` without ever failing a comparison -- the same reason 7.9
    validates with 7.6's ``_score`` rather than by comparing against two
    edges.  A ``bool`` is refused for the same reason ``D6`` refuses one where
    a flag's strength belongs: ``True`` is ``1``.
    """
    args = {"age_days": 1, "half_life_days": HALF_LIFE}
    args["age_days" if position == "age" else "half_life_days"] = bad

    with pytest.raises(FlagValueError):
        decay(**args)


@pytest.mark.parametrize("bad_age", [-1, -0.5, -HALF_LIFE, -1e9])
def test_an_outcome_dated_after_the_reference_is_refused(bad_age):
    """A negative age is a caller's fault, not a very fresh outcome.

    Answered rather than refused, a negative age would return a weight above
    ``1.0`` -- an outcome counted for more than all of itself, by an amount
    growing with how far in the future it is dated -- so 7.13's term could be
    inflated by a record whose clock is wrong.
    """
    with pytest.raises(FlagValueError):
        decay(bad_age, HALF_LIFE)


@pytest.mark.parametrize("bad_half_life", [0, 0.0, -1, -HALF_LIFE, -1e9])
def test_a_half_life_that_is_not_a_rate_is_refused(bad_half_life):
    """Zero and negative half-lives are refused rather than divided by.

    A zero would be a ``ZeroDivisionError`` -- not the package's ``ValueError``
    a caller around the scoring is catching -- and a negative one would answer
    a weight above ``1.0`` for every age, which is a curve that grows old
    rather than decaying.
    """
    with pytest.raises(FlagValueError):
        decay(1, bad_half_life)


def test_a_refusal_names_the_field_and_never_the_value():
    """``D6``'s rule for a message: the field and the type, never the number.

    The age of an outcome is derived from a date a caller holds, and a message
    carrying it would put identity data in a log line or an exception body.
    """
    with pytest.raises(FlagValueError) as caught:
        decay(-12345, HALF_LIFE)
    assert "age_days" in str(caught.value)
    assert "12345" not in str(caught.value)

    with pytest.raises(FlagValueError) as caught:
        decay(1, 0)
    assert "half_life_days" in str(caught.value)


def test_the_module_reads_no_clock():
    """No calendar and no stopwatch, in any form, in this module's own source.

    **The walk is repeated rather than assumed** for ``D12``'s reason: this is
    the first module in the package whose whole job is a function of *time*,
    so the module where a clock would be reached is the one most likely to
    reach one.  A decay that read ``date.today()`` would make a screening's
    score depend on the day it ran, and a replay of a screening would no
    longer be a replay of its history term.

    **``datetime`` is on the allowed side of the import line since 7.13**, and
    the reason is narrow: an age is a difference between two
    :class:`datetime.date` values, so the *type* has to be named to check one.
    The first assertion is the claim that matters and it is unchanged -- no
    call is ever made on the module -- so a history layer that read
    ``date.today()`` still fails here.
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
    assert not imported & {"time", "calendar", "zoneinfo"}
    assert {"datetime", "math"} <= imported


def test_the_module_imports_the_one_validation_and_nothing_from_the_pipeline():
    """Walked rather than grepped, and the claim is the absence of an import.

    :mod:`math` is the one standard-library module and it is here for
    :func:`math.pow` rather than for ``**`` so the curve reads as the
    exponential it is, and 7.13 added :mod:`dataclasses` for its two frozen
    records, :mod:`datetime` for the type an age is measured between and
    :mod:`collections.abc` for the ``Iterable`` the sequence is checked
    against.  On the project side the module needs 7.6's ``_score``, the
    error type it raises and the scale's own end -- one validation of a
    number for the whole package, shared rather than written a second time
    for 7.3's and 7.5's reason.  ``app.pipeline`` must not appear: ``D6``'s
    package-wide rule keeps a tier out of ``app.risk``, and an age computed
    from a tier's readings would put one there.
    """
    tree = _tree()
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

    assert imported == {"app.risk.flags", "app.risk.hard_rules"}
    assert standard == {"collections.abc", "dataclasses", "datetime", "math"}


def test_the_module_holds_no_band_and_no_decision_vocabulary():
    """``D31``'s split, held over this module the way 7.10's walk holds it.

    The history term is the first thing that can move a total away from the
    sum of 7.11's contributions, so it is where a score stops being
    explainable by its flags alone -- which is why the decay beside it has to
    stay arithmetic.  A band, a verdict or a rejection word written into this
    module would be the first such mapping in the package, sitting inside the
    one term 7.13 sums and 7.14 bounds.
    """
    vocabulary = {
        word.lower()
        for word in _names(_tree())
        if word.lower().lstrip("_").isalpha()
    }

    assert not vocabulary & {
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


def test_the_module_reaches_no_attribute_of_any_object():
    """Arithmetic over two numbers, and nothing else to ask.

    The same walk 7.9's suite uses, widened: 7.9 reads a score and must touch
    no object at all, and a decay that read an outcome's ``weight`` or a
    flag's ``value`` would be reading a record it has not validated.  The one
    attribute call it needs is ``math.pow``'s, which the walk allows by name
    rather than by exemption list.

    **Scoped to ``decay`` since 7.13**, and the narrowing is what keeps the
    claim true rather than what weakens it: the module now holds a function
    that reads three fields off an outcome record on purpose, so the
    module-wide walk would have to exempt ``_field``'s ``getattr`` and would
    then be asserting a list of exemptions.  ``decay`` itself still reaches
    nothing but ``math.pow``.
    """
    reached = {
        node.func.attr
        for node in ast.walk(_function("decay"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert reached <= {"pow"}
