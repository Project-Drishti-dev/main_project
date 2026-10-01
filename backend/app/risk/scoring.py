"""The weighted sum ``R = Σ(wᵢ · Fᵢ)``, and the terms it is made of.

Each term is the product of 7.3's
:func:`~app.risk.weightsets.lookup.weight_for`, which answers the ``w`` from
the weightset the caller holds, and 7.4's
:func:`~app.risk.values.normalise_value`, which answers the ``F``.  Both refuse
rather than substitute a default, so a term is a product of two numbers that
were both checked and this module re-checks neither.

**The terms are exposed, and the total is the sum of the terms shown.**
:func:`weighted_sum` answers the ``float`` 7.5 promised and
:func:`weighted_breakdown` answers the same number beside the per-flag rows it
was made from, so an officer can be shown why a document scored what it did.
There is **one** place the terms are multiplied and added:
:func:`weighted_sum` is defined as the ``total`` of
:func:`weighted_breakdown`, so the number and the explanation beside it cannot
drift apart, and the task's claim that the contributions sum to the
pre-history score holds by construction rather than by two implementations
agreeing.

**A contribution is arithmetic and carries no verdict.**  A
:class:`Contribution` is exactly the four fields the task names -- ``id``,
``weight``, ``value`` and their product -- and nothing else: no band, no
decision, no outcome.  7.10 holds that no band in the service may cause a
rejection, and a row an officer reads beside a band is exactly where such a
mapping would be written, so the split between what a number is and what it
means stays where 7.5 put it: the terms are here, and the band is 7.9's
question asked of the total.

**Invariants**

- The answer is a ``float``, whatever integer types the rows and the records
  hold.
- Weights are summed as they stand: nothing is renormalised over the flags
  that fired, and a flag at value ``1.0`` contributes its own whole weight.
- No flag is dropped, deduplicated or reordered.  A flag carrying an id another
  flag also carries is two findings and two terms.
- No flag is amended and the weightset is not written to.
- The sum is never clamped, never compared with a band threshold and never
  combined with a hard rule.
- **Every finding has exactly one row, in the order it arrived**, including
  a second finding carrying an id a first one already carries, and a finding
  whose measured value is ``0.0`` -- which is a row of nothing that is still
  shown, because a rule that fired and measured no strength is a reason the
  officer is owed.
- Both records are frozen, so a caller cannot amend a term after the fact and
  leave the total disagreeing with the rows shown.

**An empty sequence is ``0.0``.**  That is the empty sum rather than a missing
weight: no finding fired, so there is nothing to contribute.  The breakdown
over no findings is an empty tuple of contributions summing to ``0.0``, which
is a real answer rather than a missing one.

**A refusal from either gate propagates**, so a screening stops rather than
scoring a finding nobody weighted or nobody measured.

**A record carrying no ``id`` raises :exc:`FlagValueError` too**, and the sum
is the first place to see one: it is the first to read both fields of a term,
so it is the first that can see either missing.  The reader itself is
:func:`app.risk.flags._flag_id`, shared with 7.6's floor rather than written a
second time.  A raw ``AttributeError`` is not the ``ValueError`` a caller
around the scoring is catching.
"""

import dataclasses
import math
from collections.abc import Iterable

from app.risk.flags import FlagValueError, _flag_id
from app.risk.values import normalise_value
from app.risk.weightsets.loader import Weightset
from app.risk.weightsets.lookup import weight_for

__all__ = [
    "Contribution",
    "ScoreBreakdown",
    "contributions",
    "weighted_breakdown",
    "weighted_sum",
]


@dataclasses.dataclass(frozen=True)
class Contribution:
    """One finding's term in the sum, and the numbers it is made of.

    ``id`` is the finding the row is about, ``weight`` the ``w`` 7.3 answered
    for it, ``value`` the ``F`` 7.4 answered for it, and ``contribution``
    their product -- the number this row moved the score by.  **All four are
    ``float``** but for ``id``, so a dashboard renders them the same way
    whatever integer types the file and the record happened to hold.

    **The four fields are the whole of it.**  There is no band, no decision
    and no outcome here, and that is deliberate: 7.10 holds that no band in
    the service may cause a rejection of a traveller, and this is the record
    that sits directly beside a band on an officer's screen.  A contribution
    says what a finding was *worth*; what it *means* is 7.9's question asked
    of the total, and the officer's own decision is Part 8's.

    Frozen, like :class:`~app.risk.weightsets.loader.Weightset` and
    :class:`~app.pipeline.tier0.runner.TierResult`, so a caller cannot amend a
    term after the fact and leave the total disagreeing with the rows shown.
    """

    id: str
    weight: float
    value: float
    contribution: float


@dataclasses.dataclass(frozen=True)
class ScoreBreakdown:
    """The pre-history total, and the per-flag rows that add up to it.

    ``total`` is 7.5's ``R`` -- the score *before* 7.13's history term, 7.6's
    hard-rule floor and 7.7's clamp, which is what "pre-history" names.  It is
    the correctly rounded sum of ``contributions``, so the rows an officer is
    shown always add up to the number beside them.

    ``contributions`` is a tuple in the order the findings arrived: one row
    per finding, none dropped, deduplicated or reordered.  An empty tuple is
    a real answer -- a document on which nothing fired -- and sums to
    ``0.0`` rather than being a missing breakdown.
    """

    total: float
    contributions: tuple[Contribution, ...]


def _term(flag: object, weightset: Weightset) -> Contribution:
    """``flag``'s own term: 7.3's weight times 7.4's value.

    The one place a term is multiplied, shared by the sum and the breakdown
    so the two can never compute different products for the same finding.
    """
    flag_id = _flag_id(flag, "for its weight to be looked up")
    weight = weight_for(weightset, flag_id)
    value = normalise_value(flag)
    return Contribution(
        id=flag_id,
        weight=weight,
        value=value,
        contribution=weight * value,
    )


def contributions(
    flags: Iterable[object], weightset: Weightset
) -> tuple[Contribution, ...]:
    """One :class:`Contribution` per finding, in the order they arrived.

    The same terms :func:`weighted_sum` adds, exposed rather than discarded,
    so a caller can show an officer why a document scored what it did.  See
    :func:`weighted_breakdown` for the total that goes with them.
    """
    return tuple(_term(flag, weightset) for flag in flags)


def weighted_sum(flags: Iterable[object], weightset: Weightset) -> float:
    """``R`` for ``flags`` scored against ``weightset``, as a ``float``.

    :param flags: an iterable of records carrying an ``id`` and a ``value``, in
        any order.  :class:`~app.risk.flags.EvidenceFlag` is the record this is
        written for; the ``id`` is passed to
        :func:`~app.risk.weightsets.lookup.weight_for` and the ``value`` to
        :func:`~app.risk.values.normalise_value`.
    :param weightset: the loaded
        :class:`~app.risk.weightsets.loader.Weightset` the caller is already
        holding.  Nothing here opens the package.
    :returns: the sum of ``wᵢ · Fᵢ`` over the sequence, accumulated by
        :func:`math.fsum` so the answer is the correctly rounded exact sum of
        the terms and does not depend on the order they arrived in.
    :raises WeightsetError: when an id carries no usable weight in
        ``weightset``, from :func:`~app.risk.weightsets.lookup.weight_for`.
    :raises FlagValueError: when a flag carries no ``value``, a ``None``, a
        boolean, or a value that is not a real number in ``[0, 1]``, from
        :func:`~app.risk.values.normalise_value`; and when a record carries no
        ``id`` at all, from :func:`app.risk.flags._flag_id`.
    """
    return weighted_breakdown(flags, weightset).total


def weighted_breakdown(
    flags: Iterable[object], weightset: Weightset
) -> ScoreBreakdown:
    """``flags`` scored against ``weightset``: the total and its terms.

    The one call that answers both "what did this document score" and "which
    findings produced that number", so the two cannot be out of step.  The
    ``total`` is the correctly rounded sum of the ``contributions`` by
    construction, which is what makes the task's claim -- the contributions
    sum to the pre-history score -- true of every answer rather than of the
    cases a test happens to enumerate.

    :param flags: an iterable of records carrying an ``id`` and a ``value``,
        in any order.
    :param weightset: the loaded weightset the caller is already holding.
        Nothing here opens the package.
    :returns: a frozen :class:`ScoreBreakdown` whose ``total`` is 7.5's ``R``
        and whose ``contributions`` are one row per finding, in arrival
        order.  Nothing is clamped, banded or combined with a hard rule: this
        is the pre-history score.
    :raises WeightsetError: when an id carries no usable weight, from
        :func:`~app.risk.weightsets.lookup.weight_for`.
    :raises FlagValueError: when a flag carries no ``value`` or no ``id``, or
        carries a value that is not a real number in ``[0, 1]``.
    """
    terms = contributions(flags, weightset)
    return ScoreBreakdown(
        total=math.fsum(term.contribution for term in terms),
        contributions=terms,
    )
