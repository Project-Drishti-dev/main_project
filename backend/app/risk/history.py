"""The history layer's two questions: how much of an old outcome is left, and
what is left once the verified ones have been added up.

The abstract's 4.8 says verified, audited prior outcomes are brought in as a
historical signal that "is bounded, so it can only move the score by a limited
amount, and it decays with time, so an old outcome counts for less than a
recent one".  **The decay is :func:`decay`, the bound is
:func:`history_signal`, and the term reaches a score through
:func:`apply_history`**, and the three are one sentence: each verified outcome
is worth its own signed number of points scaled by how much of it is left, the
total is held inside a magnitude no history can pass, and that total is what
gets added to the sum the findings produced.

**Only verified outcomes are summed, and the gate is a type rather than a
truthiness test.**  :attr:`PriorOutcome.verified` is a ``bool`` and anything
else is refused, so ``verified=1``, ``verified="yes"`` and ``verified=None``
cannot reach the sum as truthy records: 4.8's one gate on the layer is the one
gate a caller cannot widen by writing ``1``.  **A record is checked for shape
before that gate is asked of it**, on 7.6's rule that a record carrying no
``id`` is refused rather than passed over, so a malformed outcome is a fault
wherever in the sequence it sits rather than a silent zero.

**A pass is a negative number of points and a fail a positive one**, which is
:mod:`app.risk.weightsets.lookup`'s own unit on ``D21`` -- points, not shares
-- carrying the sign 4.8 asks for.  A verified pass gives a repeat case
continuity by *reducing* the score rather than by being a separate kind of
term; one signed number per outcome is what lets the total be one sum, and it
is why the bound below is symmetric.

**An age is supplied; a clock is never read.**  ``decay`` is handed how old an
outcome is rather than when it happened, so the caller owns the reference it
is measured against -- ``history_signal`` takes a ``reference_date`` and does
the subtraction (``D12``'s named dependency, and the same one-way rule the
watchlist seam keeps).  A decay that read ``today()`` would make a screening's
score depend on the day it ran, so a replay of a screening would not be a
replay of its history term, and ``test_tier0_timing.py``'s walk over the
runner's clock is the precedent for pinning that this module has none.
``datetime`` is imported here for the *type* two ages are measured between,
and the walk over this module's source holds that no call is ever made on it.

**A half-life is the whole curve, so the curve is written as a half-life.**
``decay(age, half_life) == 0.5 ** (age / half_life)``: at zero days an outcome
is worth all of itself, one half-life later exactly half, two later exactly a
quarter, and so on down.  The three points the task names are the three the
formula is pinned at, and they are exact in binary floating point --
``0.5 ** 1`` and ``0.5 ** 2`` are ``0.5`` and ``0.25`` -- so the suite asserts
them with ``==`` rather than a tolerance.  A linear falloff would pass "older
counts for less" at every age and would **not** pass at two half-lives, which
is why that point is in the task rather than only the first two.

**The half-life is committed policy, not a deployment setting**, on ``D28``'s
reason: the abstract calls the decay rate a calibration parameter, and a
parameter a deployment could retune would let what an old outcome is worth
change with nothing recording it.  :data:`HISTORY_HALF_LIFE_DAYS` is therefore
a constant in this module, there is no environment variable for it, and none
in ``.env.example``; a retune is a ``RULESET_VERSION`` bump like any other.

**This is a weight in ``[0, 1]`` and nothing else.**  It is not a score, so it
is never clamped to the 0-100 scale, never floored by 7.6 and never banded by
7.9; :func:`history_signal` multiplies it by an outcome's own signed weight
and :func:`apply_history` is what adds the resulting total to a score.
Like 7.11's :class:`~app.risk.scoring.Contribution`, it carries no band, no
decision and no outcome field -- ``D30``'s walk would catch the first one
written beside it -- because "half of a verified pass from four years ago" is
arithmetic, and what a score *means* is 7.9's question asked of the total.

**The term is added where the abstract's ``R = Sum(w_i * F_i) + hard rules``
puts it, which is under the floor rather than over it.**  4.8's signal sits
beneath the hard rules in that sentence, and the order is observable: a hard
fail lifts a score to a floor, and a term applied *above* that floor could pull
the reading back down off it, which is not what an override means.  So
:func:`apply_history` adds the bounded term to the sum 7.5 answered and stops
there -- it asks neither 7.6's question nor 7.7's, and holds no floor, no
table of overriding ids and no band.  7.15's ``compute_risk`` is what asks the
four questions in order.

**The bound is :func:`history_signal`'s and is not written a second time here.**
:func:`apply_history` adds the number that function already holds inside
``+/- config.max_magnitude``, so the adjustment it makes is the term itself
rounded by one addition, and a caller asking "by how much can history move
this score" gets the committed bound rather than one of this function's own.

**Invariants**

- The answer is a ``float`` in ``[0, 1]``, whatever integer types the ages
  arrived as.
- ``decay(0, h) == 1.0`` exactly, for every half-life.
- The answer never rises as the age rises, and never falls as the half-life
  rises: an older outcome is worth less and a slower decay is worth more.
- For ``decay``, the age and the half-life are the only two inputs.  No flag,
  no weightset, no outcome record and no band is read.
- Nothing is clamped, summed, rounded to a fixed precision or compared against
  a threshold.
- No file, no environment, no randomness and no clock, so the same two
  numbers always answer the same weight.

**A malformed number is refused rather than answered.**  Both arguments are
run through 7.6's :func:`~app.risk.hard_rules._score` -- the package's one
validation of a number -- so a ``bool``, a ``None``, a string, a ``nan`` or an
infinity raises :exc:`~app.risk.flags.FlagValueError` rather than producing a
weight.  **A non-positive half-life is refused and a negative age is refused**:
the first is a division that would answer ``1.0`` forever or raise on zero,
and the second is an outcome dated after the reference, which is a data fault
in the caller rather than a very fresh outcome to be scored at full strength.
"""

import dataclasses
import math
from collections.abc import Iterable
from datetime import date, datetime

from app.risk.flags import FlagValueError
from app.risk.hard_rules import MAX_SCORE, _score

__all__ = [
    "DEFAULT_HISTORY_CONFIG",
    "HISTORY_HALF_LIFE_DAYS",
    "HISTORY_MAX_MAGNITUDE",
    "HistoryConfig",
    "PriorOutcome",
    "apply_history",
    "decay",
    "history_signal",
]

#: How many days an outcome's weight is halved over, when a caller names no
#: other.  **A committed calibration parameter rather than a measurement**: the
#: abstract says the decay rate "is a calibration parameter, set during
#: validation", and no validation set exists here, so this is a documented
#: starting point chosen to be legible (roughly a season) rather than a tuned
#: number, and the honest reading of it is the one ``D28``'s thresholds get.
#: Read through this name rather than retyped, so a retune moves the claims
#: that lean on it at once.
HISTORY_HALF_LIFE_DAYS = 180.0

#: The most the whole history term may be worth, in points, when a caller names
#: no other.  **A committed calibration parameter rather than a measurement**,
#: on the same grounds as :data:`HISTORY_HALF_LIFE_DAYS`: 4.8 names "the exact
#: bound and decay rate" as the two parameters set during validation, so
#: neither is a deployment setting and neither is an environment variable.
#: **Twelve is chosen so the bound sits under the narrowest band on the
#: scale**, which is what lets a verified pass leave a score standing on a
#: band edge inside its own band; the width it is compared against is read off
#: :mod:`app.risk.config` by the suite rather than written here, so the claim
#: holds at whatever those numbers are set to.
HISTORY_MAX_MAGNITUDE = 12.0


def _age(age_days: object) -> float:
    """``age_days`` as a non-negative ``float``, or a refusal naming it."""
    age = _score("age_days", age_days)
    if age < 0.0:
        raise FlagValueError("age_days must not be negative")
    return age


def _half_life(half_life_days: object) -> float:
    """``half_life_days`` as a positive ``float``, or a refusal naming it."""
    half_life = _score("half_life_days", half_life_days)
    if half_life <= 0.0:
        raise FlagValueError("half_life_days must be greater than zero")
    return half_life


def decay(age_days: object, half_life_days: object = HISTORY_HALF_LIFE_DAYS) -> float:
    """How much of an outcome ``age_days`` old is still worth, as a ``float``.

    :param age_days: how old the outcome is, in days, as a difference between
        two dates the caller already holds.  **No clock is read here** -- the
        reference belongs to the caller, so the same two numbers answer the
        same weight on every run.
    :param half_life_days: how many days it takes for the outcome's weight to
        halve.  Optional, defaulting to
        :data:`HISTORY_HALF_LIFE_DAYS`; must be greater than zero.
    :returns: ``0.5 ** (age_days / half_life_days)``, so ``1.0`` at zero days,
        exactly ``0.5`` at one half-life and exactly ``0.25`` at two.  Always a
        ``float`` in ``[0, 1]``, and never clamped, banded or rounded.
    :raises ~app.risk.flags.FlagValueError: when either argument is not a
        finite real number -- a ``None``, a boolean, a string, a ``nan`` or an
        infinity -- from 7.6's :func:`~app.risk.hard_rules._score`; when
        ``age_days`` is negative, which is an outcome dated after the
        reference rather than a fresh one; or when ``half_life_days`` is zero
        or negative, which is not a rate at all.
    """
    return math.pow(
        0.5,
        _age(age_days) / _half_life(half_life_days),
    )


def _magnitude(max_magnitude: object) -> float:
    """``max_magnitude`` as a positive ``float``, or a refusal naming it."""
    bound = _score("max_magnitude", max_magnitude)
    if not 0.0 < bound <= MAX_SCORE:
        raise FlagValueError(
            f"max_magnitude must lie in (0, {MAX_SCORE:g}]"
        )
    return bound


def _points(weight: object) -> float:
    """``weight`` as signed points on the scale, or a refusal naming it."""
    value = _score("weight", weight)
    if abs(value) > MAX_SCORE:
        raise FlagValueError(f"weight must lie in [{-MAX_SCORE:g}, {MAX_SCORE:g}]")
    return value


def _verified(verified: object) -> bool:
    """``verified`` as a ``bool``, or a refusal naming it.

    **Membership rather than truthiness**, on ``D6``'s reason for refusing a
    boolean where a strength belongs: ``1`` and ``"yes"`` are both truthy and
    neither says an outcome was audited, and an unaudited outcome reaching the
    sum is the one thing 4.8 puts this layer's gate there to stop.
    """
    if not isinstance(verified, bool):
        raise FlagValueError(
            "verified must be True or False, not " f"{type(verified).__name__}"
        )
    return verified


def _calendar_date(field: str, value: object) -> date:
    """``value`` as a plain :class:`datetime.date`, or a refusal naming it.

    **A ``datetime`` is refused rather than accepted as a ``date``.**  It is a
    subclass, so an ``isinstance`` check alone lets one through, and
    subtracting a ``datetime`` from a ``date`` raises ``TypeError`` -- not the
    ``ValueError`` a caller around the scoring is catching.  A ``timedelta``
    and a string are refused for the same reason: an age is measured between
    two days, and anything else is a record that cannot answer one.
    """
    if not isinstance(value, date) or isinstance(value, datetime):
        raise FlagValueError(
            f"{field} must be a datetime.date, not {type(value).__name__}"
        )
    return value


def _field(record: object, name: str) -> object:
    """The field ``record`` carries, or a refusal naming the one it lacks."""
    try:
        return getattr(record, name)
    except AttributeError:
        raise FlagValueError(
            f"a prior outcome must carry a '{name}' for it to be summed"
        ) from None


def _outcomes(prior_outcomes: object) -> Iterable[object]:
    """``prior_outcomes`` as an iterable of records, or a refusal naming it.

    **A bare ``str`` or ``bytes`` is refused rather than iterated**, on 7.6's
    reason: one would be a sequence of characters, each of which is then
    refused a field at a time rather than the sequence itself being refused.
    """
    if isinstance(prior_outcomes, (str, bytes)) or not isinstance(
        prior_outcomes, Iterable
    ):
        raise FlagValueError(
            "prior_outcomes must be a collection of outcome records, not "
            f"{type(prior_outcomes).__name__}"
        )
    return prior_outcomes


def _config(config: object) -> "HistoryConfig":
    """``config`` as a :class:`HistoryConfig`, or a refusal naming it."""
    if not isinstance(config, HistoryConfig):
        raise FlagValueError(
            f"config must be a HistoryConfig, not {type(config).__name__}"
        )
    return config


def _bounded(total: float, max_magnitude: float) -> float:
    """``total`` held inside ``+/-max_magnitude``, symmetrically.

    **A clamp and not a rescale**, for 7.7's reason: a total of 900 is held to
    the bound rather than divided by anything, and a total inside it is
    handed back to the last bit.
    """
    if total > max_magnitude:
        return max_magnitude
    if total < -max_magnitude:
        return -max_magnitude
    return total


@dataclasses.dataclass(frozen=True)
class PriorOutcome:
    """One earlier screening of this document or identity, and what it is worth.

    :attr:`outcome_date` is the day the outcome was recorded, in the same
    scale of dates as the reference it is later measured against; it is a
    plain :class:`datetime.date` and never a timestamp, so an age is a whole
    number of days however the two are subtracted.

    :attr:`weight` is **signed points on the 0-100 scale**, the unit
    :func:`app.risk.weightsets.lookup.weight_for` already answers in and not a
    share of anything: negative for an outcome that lowers suspicion (a
    verified pass), positive for one that raises it (a verified fail).  **The
    sign is the caller's claim and is not inferred here**, because this record
    says what was worth what, not what it meant; what it means is 7.9's
    question asked of the total 7.14 assembles.

    :attr:`verified` says whether the outcome was verified and audited.  It
    is a ``bool`` and nothing else, and it is the field
    :func:`history_signal` gates the sum on: 4.8's "only verified outcomes are
    used" is one question asked of every record rather than a truthiness test
    applied to whatever arrived.

    **All three fields are checked as the record is built, and it is frozen.**
    Nothing is coerced and nothing is defaulted: a weight of ``None``, a date
    that is a string or a timestamp, and a ``verified`` of ``1`` are each a
    record that could not be summed, and a caller is told so where the record
    was built rather than where it was finally read.  The check assigns
    nothing, and there is no *public* method on the record for the reason
    :class:`~app.risk.flags.EvidenceFlag` has none: a method on it would be a
    second opinion about what happened.
    """

    outcome_date: date
    weight: float
    verified: bool

    def __post_init__(self) -> None:
        _calendar_date("outcome_date", self.outcome_date)
        _points(self.weight)
        _verified(self.verified)


@dataclasses.dataclass(frozen=True)
class HistoryConfig:
    """The two calibration parameters 4.8 names, and nothing else.

    :attr:`half_life_days` is how many days an outcome's weight is halved
    over, and is the same number :data:`HISTORY_HALF_LIFE_DAYS` holds, read
    rather than retyped so a retune moves the default with it.

    :attr:`max_magnitude` is the most the whole term may be worth in either
    direction, and is :data:`HISTORY_MAX_MAGNITUDE` by default.

    **Both are committed policy rather than deployment settings**, on ``D28``'s
    reason, which is why they are a record rather than two environment
    variables: a bound or a rate a deployment could retune would let what an
    old outcome is worth change with nothing recording the change, and a
    retune here is a ``RULESET_VERSION`` bump like any other.  **Neither
    number is a measurement** -- 4.8 says both are set during validation, and
    no validation set exists in this repo -- so the honest reading of each is
    the one 7.8's thresholds get.

    **Frozen, and both fields are checked as it is built.**  A half-life that
    is not a rate and a bound that is zero, negative or above the scale are
    refused here rather than at the first screening that used them.
    """

    half_life_days: float = HISTORY_HALF_LIFE_DAYS
    max_magnitude: float = HISTORY_MAX_MAGNITUDE

    def __post_init__(self) -> None:
        _half_life(self.half_life_days)
        _magnitude(self.max_magnitude)


#: The two committed defaults as one record, and the value
#: :func:`history_signal` answers with when a caller names no config.  A
#: module-level constant rather than a ``HistoryConfig()`` written in the
#: signature, so the committed answer is one object every caller shares and
#: compares for identity.
DEFAULT_HISTORY_CONFIG = HistoryConfig()


def _term(outcome: object, reference: date, config: "HistoryConfig") -> float:
    """One outcome's term in the sum: its weight times what is left of it.

    **Every field is read and checked before the verified gate is asked of
    it**, on 7.6's rule that a record is refused rather than passed over.  The
    age is computed only for a verified outcome, so an unaudited record dated
    after the reference contributes ``0.0`` rather than refusing a call over
    a number the sum never uses.
    """
    verified = _verified(_field(outcome, "verified"))
    outcome_date = _calendar_date("outcome_date", _field(outcome, "outcome_date"))
    weight = _points(_field(outcome, "weight"))

    if not verified:
        return 0.0

    age_days = (reference - outcome_date).days
    return weight * decay(age_days, config.half_life_days)


def history_signal(
    prior_outcomes: Iterable[object],
    reference_date: date,
    config: "HistoryConfig" = DEFAULT_HISTORY_CONFIG,
) -> float:
    """What ``prior_outcomes`` are still worth today, in signed points.

    :param prior_outcomes: the earlier outcomes of this document or identity,
        in any order and any number, including none.
        :class:`PriorOutcome` is the record this is written for; any record
        carrying ``outcome_date``, ``weight`` and ``verified`` will do, so an
        outcome read back from storage is summed without being rebuilt first.
        **An outcome that is not verified contributes nothing**, whatever its
        weight and however recent it is.
    :param reference_date: the day the ages are measured against --
        ``D12``'s named dependency, the same reference 5.8 injects into the
        three date rules.  **No clock is read here**, so the same outcomes and
        the same reference answer the same signal on every run and a replay of
        a screening is a replay of its history term.
    :param config: the two calibration parameters 4.8 names, keyword-defaulted
        to :data:`DEFAULT_HISTORY_CONFIG`.  Its ``half_life_days`` is what
        each outcome is decayed by and its ``max_magnitude`` is what the total
        is held to.
    :returns: the sum of ``weight * decay(age_days)`` over the **verified**
        outcomes, held inside ``+/-config.max_magnitude``, as a ``float``.
        Positive raises the score and negative lowers it; an empty sequence is
        ``0.0``.  Nothing is added to a score here and no band is consulted --
        :func:`apply_history` is what adds this term to a score, and 7.9's
        question is the one that reads the total.
    :raises ~app.risk.flags.FlagValueError: when ``prior_outcomes`` is not a
        collection of records, when a record carries no ``outcome_date``, no
        ``weight`` or no ``verified``, when ``verified`` is not a ``bool``,
        when ``weight`` is not a finite real number within the scale, when
        either date is not a plain :class:`datetime.date`, when
        ``reference_date`` is later than a verified outcome, or when ``config``
        is not a :class:`HistoryConfig`.
    """
    settings = _config(config)
    reference = _calendar_date("reference_date", reference_date)

    total = math.fsum(
        _term(outcome, reference, settings)
        for outcome in _outcomes(prior_outcomes)
    )
    return _bounded(total, settings.max_magnitude)


def apply_history(
    score: object,
    prior_outcomes: Iterable[object],
    reference_date: date,
    config: "HistoryConfig" = DEFAULT_HISTORY_CONFIG,
) -> float:
    """``score`` with this history added to it, as a ``float``.

    :param score: the pre-history score -- 7.5's
        :func:`~app.risk.scoring.weighted_sum`, in points on the 0-100 scale.
        **A score outside the scale is answered and not refused**, on 7.7's
        reason: 195 points is a real reading ``D21`` allows to run over the
        top, and 195 plus the term is still a sum waiting for 7.7 to hold.
    :param prior_outcomes: the earlier outcomes, as
        :func:`history_signal`'s own first argument -- any number and any
        order, including none.
    :param reference_date: the day the ages are measured against, as
        :func:`history_signal`'s own second argument.  **No clock is read
        here**, so the same score and the same outcomes answer the same
        number on every run.
    :param config: the two calibration parameters, as
        :func:`history_signal`'s own third argument and keyword-defaulted the
        same way.
    :returns: ``score + history_signal(prior_outcomes, reference_date,
        config)``.  **The adjustment is the term itself and no more**: the sum
        is :func:`history_signal`'s, already held inside
        ``+/-config.max_magnitude``, so history can move a score by at most the
        bound and by nothing else.  **Neither 7.6's floor nor 7.7's clamp is
        applied here** -- this is the fourth question, asked between 7.5's sum
        and both of those -- so an answer off the scale is off the scale
        still, and 7.15's ``compute_risk`` is what composes the four.
    :raises ~app.risk.flags.FlagValueError: when ``score`` is not a finite real
        number, from 7.6's :func:`~app.risk.hard_rules._score`, and for every
        reason :func:`history_signal` refuses its own three arguments -- a
        record that cannot be summed, a reference that is not a plain date, a
        config that is not a :class:`HistoryConfig`.  **The score is checked
        first**, so a call carrying two faults is told about the score rather
        than about whichever history happened to be read first.
    """
    total = _score("score", score)
    return total + history_signal(prior_outcomes, reference_date, config)
