"""The composition: five questions asked in one order, and one record at the end.

7.5 to 7.7 and 7.9 to 7.14 each answer one question, in its own module with
its own suite and its own refusals, and **none of them is wired to another**.
Before this module the whole chain was composed by nobody: a band was a
designed reading that no screening could reach, and 4.8's bounded term
reached a score nothing produced.  :func:`compute_risk` is the abstract's own
sentence -- "The risk engine combines all flags into a score R and a band
(Low Risk, Review or High Risk)" -- turned into a call, and
:class:`RiskResult` is what it hands back.

**The order is the design, and it is the order the abstract writes.**  ``R =
Sum(w_i * F_i)``, with 4.8's bounded term added to the sum, then a hard rule
overriding it, then a number on the 0-100 scale, then a band:

1. :func:`~app.risk.scoring.weighted_breakdown` (7.5, 7.11) -- the sum and the
   rows it was made of;
2. :func:`~app.risk.history.apply_history` (7.14) -- 4.8's term, added to the
   sum and to nothing else;
3. :func:`~app.risk.hard_rules.apply_hard_rules` (7.6) -- the floor, a ``max``
   and not an addition;
4. :func:`~app.risk.clamp_score` (7.7) -- the last question asked of a number;
5. :func:`~app.risk.bands.to_band` (7.9) -- the reading an officer sees.

**Any two of them swapped answer a different question.**  A term applied
above the floor is 7.14's own counterfactual: 500 verified passes take a hard
failure's ``0.0`` to ``-12.0`` and the reading is still ``90.0`` where the
other order answers ``78.0``.  A band read before the clamp is a band of a
number no officer will ever be shown.  **The order is therefore held by a
test that reads these five calls out of this file** -- a docstring cannot
fail, and an order that is only described is an order the next edit can move.

**The hard-fail table is asked for and never imported.**  Which rules
override is 6.5's answer, and it is a union of each family's own table held
beside each family's own labels; ``app.risk`` imports nothing from
``app.pipeline`` (``D6``'s one-way dependency: rules emit records and the
engine consumes them), so :func:`compute_risk` **requires** ``hard_fail_ids``
as a keyword rather than defaulting it.  A default would be a table written
somewhere it can drift, or an empty one that lets a broken checksum be scored
as a document with a question on it.

**No clock and no randomness**, so the same findings, the same weightset and
the same history answer the same record on every run and a replay of a
screening is a replay of its band.  The day history ages are measured against
is :attr:`ScreeningHistory.reference_date`, handed in by the caller on
``D12``'s terms.

**Invariants**

- :attr:`RiskResult.score` is inside ``[MIN_SCORE, MAX_SCORE]`` for every
  answer, and :attr:`RiskResult.band` is 7.9's answer read off *that* number.
  There is no second score to band and no band held beside a different one.
- :attr:`RiskResult.contributions` is 7.11's breakdown: one row per finding,
  in arrival order, none dropped, deduplicated or reordered.  **The rows add
  up to the pre-history total and not to the score**, and that is stated on
  the record rather than left to be discovered: 4.8's term, 7.6's floor and
  7.7's clamp all sit between the rows and the score.
- :attr:`RiskResult.ruleset_version` is read off the weightset the caller
  passed, so a score is quoted against the ruleset that produced it.
- The findings are read **once**, into a tuple, and all five questions are
  asked of that one sequence: 7.6's floor reads the flags a second time, and
  a generator handed to both would arrive empty there.
- Every question is asked exactly once and in the order above.  Nothing here
  normalises, clamps, bands, floors, dedupes, amends a flag, opens a file or
  writes anything down.
- **A refusal from any of the five propagates**, so a screening stops rather
  than answering a partial record: a missing weight, an unmeasured value and a
  missing id are all the ``ValueError`` a caller around the engine is already
  catching.
- **No field says what an officer should do.**  7.10 holds that no band in
  the service may cause a rejection of a traveller, and this is the record a
  band and a set of rows share.
"""

import dataclasses
from collections.abc import Iterable
from datetime import date

from app.risk.bands import to_band
from app.risk.clamp import clamp_score
from app.risk.flags import FlagValueError
from app.risk.hard_rules import (
    DEFAULT_HARD_FAIL_FLOOR,
    MAX_SCORE,
    MIN_SCORE,
    apply_hard_rules,
)
from app.risk.history import (
    DEFAULT_HISTORY_CONFIG,
    HistoryConfig,
    _calendar_date,
    _config,
    _outcomes,
    apply_history,
)
from app.risk.scoring import Contribution, weighted_breakdown
from app.risk.weightsets.loader import Weightset, WeightsetError

__all__ = [
    "RiskResult",
    "ScreeningHistory",
    "compute_risk",
]


def _findings(flags: object) -> tuple[object, ...]:
    """``flags`` read once, as the tuple every question below is asked of.

    **One read rather than two**, because the hard-rule question reads the
    findings again and a generator handed to both would be exhausted by the
    sum.  A sequence is copied rather than kept, so a caller cannot amend the
    findings midway through the composition.

    **A bare ``str`` or ``bytes`` is refused rather than iterated**, on 7.6's
    and 7.13's reason: it would be a sequence of characters, each of which is
    then refused a field at a time rather than the sequence itself being
    refused.
    """
    if isinstance(flags, (str, bytes)) or not isinstance(flags, Iterable):
        raise FlagValueError(
            f"flags must be a collection of findings, not {type(flags).__name__}"
        )
    return tuple(flags)


def _weights(weights: object) -> Weightset:
    """``weights`` as a :class:`Weightset`, or a refusal naming the type.

    7.3's lookup reads ``weightset.ruleset_version`` before it reads any row,
    so a plain mapping or a name would answer an ``AttributeError`` -- not the
    ``ValueError`` a caller around the engine is already catching.  The
    refusal is the loader's own type, because a weightset that is not one is
    7.2's fault rather than a new kind of argument.
    """
    if not isinstance(weights, Weightset):
        raise WeightsetError(
            f"weights must be a Weightset, not {type(weights).__name__}"
        )
    return weights


def _history(history: object) -> "ScreeningHistory":
    """``history`` as a :class:`ScreeningHistory`, or a refusal naming it.

    **``None`` is the one value that is not refused**, and it is refused
    earlier than here: it is the signature's default, so ``compute_risk``
    never asks this question about it.  A sequence of outcomes handed where a
    record is expected is refused rather than wrapped, because wrapping it
    would have to invent the reference date that is the record's whole reason
    for existing.
    """
    if not isinstance(history, ScreeningHistory):
        raise FlagValueError(
            f"history must be a ScreeningHistory, not {type(history).__name__}"
        )
    return history


@dataclasses.dataclass(frozen=True)
class ScreeningHistory:
    """The earlier outcomes of this case, and the day they are read against.

    :attr:`prior_outcomes` is 4.8's "verified and audited outcomes" as
    :class:`~app.risk.history.PriorOutcome` records, in any order and any
    number including none.  **It is held as a tuple, read once as this record
    is built**, so a generator cannot be exhausted by the first screening and
    answer an empty history to the second.

    :attr:`reference_date` is ``D12``'s named dependency, and the reason this
    is one record rather than three arguments: an age is a difference between
    two days, so the outcomes and the day they are measured against cannot be
    told apart.  **It has no default and no clock is read to fill it in**, so
    a call that has history must say which day it means and a screening is
    replayable from the record alone.

    :attr:`config` is 7.13's two calibration parameters, defaulted to the
    committed :data:`~app.risk.history.DEFAULT_HISTORY_CONFIG` on ``D28``'s
    grounds: a bound or a decay rate a caller could retune per screening would
    let what an old outcome is worth change with nothing recording it, so a
    retune is a ``RULESET_VERSION`` bump like any other.

    **All three are checked as the record is built, and it is frozen.**
    Nothing is coerced and nothing is defaulted: a ``prior_outcomes`` that is
    a bare string, a ``reference_date`` that is a timestamp rather than a
    plain day, and a ``config`` that is not a
    :class:`~app.risk.history.HistoryConfig` are each a record that could not
    be asked of, and a caller is told so where the record was built rather
    than where it was finally read.  The checks are 7.13's own rather than
    second copies of them.
    """

    prior_outcomes: tuple[object, ...]
    reference_date: date
    config: HistoryConfig = DEFAULT_HISTORY_CONFIG

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "prior_outcomes", tuple(_outcomes(self.prior_outcomes))
        )
        _calendar_date("reference_date", self.reference_date)
        _config(self.config)


@dataclasses.dataclass(frozen=True)
class RiskResult:
    """One screening's score, band, rows and ruleset version, and nothing else.

    :attr:`score` is the number an officer reads: on the 0-100 scale, after
    4.8's term, 7.6's floor and 7.7's clamp, and therefore always inside
    ``[MIN_SCORE, MAX_SCORE]``.

    :attr:`band` is 7.9's answer read off *that* number, so the two cannot
    disagree -- there is no second score to band and no band held beside a
    different one.

    :attr:`contributions` is 7.11's breakdown: one row per finding, in
    arrival order, none dropped, deduplicated or reordered.  **The rows add
    up to the pre-history total and not to :attr:`score`**, which is the
    honest reading rather than a defect to be tidied away: 4.8's term, 7.6's
    floor and 7.7's clamp all sit between the rows and the score, so a
    document with a history or a hard fail shows a score its rows do not add
    to.  The number the rows are the sum of is the ``total`` of
    :func:`~app.risk.scoring.weighted_breakdown`, which is where 7.11's own
    name for it -- "pre-history" -- belongs.

    :attr:`ruleset_version` is the string the weightset the caller passed
    carries, read off that record rather than off
    :data:`app.version.RULESET_VERSION`: a score is only comparable against
    the ruleset that produced it, and the two differ from the moment a
    screening is scored against a weightset that is not the one the service
    ships.

    **The four fields are the four the task names, and there is no fifth.**
    There is no decision, no outcome and no officer's action here: 7.10 holds
    that no band in the service may cause a rejection of a traveller, and this
    is the record where a band and a set of rows sit side by side.  Frozen, so
    a caller cannot amend the score and leave the band reading a number
    nobody is shown.
    """

    score: float
    band: str
    contributions: tuple[Contribution, ...]
    ruleset_version: str


def compute_risk(
    flags: Iterable[object],
    weights: Weightset,
    history: "ScreeningHistory | None" = None,
    *,
    hard_fail_ids: Iterable[str],
    floor: float = DEFAULT_HARD_FAIL_FLOOR,
) -> RiskResult:
    """``flags`` scored against ``weights``: a score, a band and the rows.

    :param flags: the findings the tiers produced, in any order and any
        number.  :class:`~app.risk.flags.EvidenceFlag` is the record this is
        written for; any record carrying an ``id`` and a ``value`` will do, so
        flags read back from storage are scored without being rebuilt.  **The
        sequence is read once** and all five questions are asked of that one
        tuple, so a generator is a legal argument and one finding is one row
        and one term.
    :param weights: the loaded
        :class:`~app.risk.weightsets.loader.Weightset` the caller is already
        holding.  Nothing here opens the package, and the version reported
        back is this record's own.
    :param history: the earlier outcomes of this case, or ``None`` for a
        first sighting.  A :class:`ScreeningHistory` rather than a bare
        sequence, because an age cannot be measured without the day it is
        measured against.  **``None`` means no history at all**: 4.8's term
        is then exactly ``0.0`` and 7.14's call is not made, rather than a
        term of nothing being added.
    :param hard_fail_ids: the ids of the rules that override -- 6.5's answer,
        required and passed in rather than imported, on ``D6``'s one-way
        dependency.  **There is no default on purpose**: a screening that
        forgot its table would score a broken checksum at 60 and read as a
        document with a question on it.  Any iterable will do and a generator
        is consumed once.
    :param floor: the level a hard failure lifts the score to, keyword-only
        and defaulted to :data:`~app.risk.hard_rules.DEFAULT_HARD_FAIL_FLOOR`.
    :returns: a frozen :class:`RiskResult` whose ``score`` is inside
        ``[MIN_SCORE, MAX_SCORE]``, whose ``band`` is
        :func:`~app.risk.bands.to_band` read off that score, whose
        ``contributions`` are 7.11's rows, and whose ``ruleset_version`` is
        the one ``weights`` carries.  The questions are asked in the order
        this module's own docstring names, once each.
    :raises ~app.risk.weightsets.loader.WeightsetError: when ``weights`` is
        not a :class:`~app.risk.weightsets.loader.Weightset`, and when a
        finding carries an id the weightset weighs no row for, from
        :func:`~app.risk.weightsets.lookup.weight_for`.
    :raises ~app.risk.flags.FlagValueError: when ``flags`` is not a
        collection, when a finding carries no ``id`` or no ``value``, when a
        value is a boolean or a number outside ``[0, 1]``, when ``history`` is
        not a :class:`ScreeningHistory` or any of its own fields is refused,
        when ``hard_fail_ids`` is a bare string, and for every reason
        :func:`~app.risk.history.apply_history`,
        :func:`~app.risk.hard_rules.apply_hard_rules` and
        :func:`~app.risk.clamp_score` refuse their own arguments.  **The
        sum is asked first**, so a call carrying two faults is told about the
        findings rather than about whichever question happened to run first.
    """
    findings = _findings(flags)
    ruleset = _weights(weights)

    breakdown = weighted_breakdown(findings, ruleset)
    score = breakdown.total

    if history is not None:
        record = _history(history)
        score = apply_history(
            score,
            record.prior_outcomes,
            record.reference_date,
            record.config,
        )

    score = apply_hard_rules(score, findings, hard_fail_ids, floor=floor)
    score = clamp_score(score)

    return RiskResult(
        score=score,
        band=to_band(score),
        contributions=breakdown.contributions,
        ruleset_version=ruleset.ruleset_version,
    )
