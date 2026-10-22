"""The hard-rule floor: one hard fail lifts ``R`` to a level the sum never lowers.

The abstract writes ``R = Sum(w_i * F_i) + hard rules`` and says a hard rule
"overrides the weighted sum and forces High Risk".  That is a floor and not a
contribution: a broken printed checksum does not add sixty points, and
:func:`~app.risk.scoring.weighted_sum` has already added its terms by the time
this question is asked.  **The floor is applied above the sum and never inside
it**, so a screening's sum stays the sum its ruleset produced and the override
is one question asked afterwards.

**This module holds no table of which rules override.**  Whether a finding
overrides is 6.5's answer, and 6.5's answer is
:data:`app.pipeline.tier0.runner._HARD_FAIL_IDS` -- a union of each family's
own table, held beside each family's own labels.  :mod:`app.risk` imports
nothing from :mod:`app.pipeline` (`D6`'s one-way dependency: rules emit
records and the engine consumes them), so **the caller passes the ids in and
the engine is asked rather than told.**  ``test_hard_fail_floor.py`` reads that
table from the other side, the way 7.1's suite reads the watchlist bands, so
the two tables are held to each other by a test and not by a second copy in
production code.

**Invariants**

- The answer is the floor when a rule the caller named has fired and the floor
  is above the score, and the score itself otherwise.
- **A floor never lowers.**  A sum already at or above the floor is handed
  back unchanged, so a hard fail cannot make a heavier document read safer.
- **The overriding flag's own strength is not read.**  A finding carrying
  ``value=0.0`` -- a rule that fired without being able to quantify -- lifts
  the score exactly as one carrying ``1.0`` does.  The score arrives already
  summed and no value is re-read here.
- Every flag in the sequence is read, including the ones after an override
  already fired: a record carrying no ``id`` is refused rather than passed
  over, the same way :func:`~app.risk.scoring.weighted_sum` refuses rather
  than skipping a term.
- Nothing is summed, clamped, banded, deduplicated, sorted or amended, and
  neither a flag nor the table the caller passed is written to.
- **The ids are consumed and never tested for truthiness**, because a
  generator is truthy whether or not it yields anything.
- No clock, no randomness and no file.

**The floor is a point on the scale 7.7 clamps to**, so it is held to
``[MIN_SCORE, MAX_SCORE]`` and refused outside it: a floor above the top of
the scale is one no answer can reach, and one below the bottom is a no-op
that reads as a configured override.

**A malformed argument raises :exc:`~app.risk.flags.FlagValueError`** -- a
score, a floor, a table and a flag are not things a screening may be answered
from when one of them is wrong, and the type is a `ValueError` so a caller
already catching one around the scoring keeps catching it.  **A message names
the field and the type and never the value**, on `D6`'s grounds.
"""

import math
from collections.abc import Iterable

from app.risk.flags import FlagValueError, _flag_id

__all__ = [
    "DEFAULT_HARD_FAIL_FLOOR",
    "MAX_SCORE",
    "MIN_SCORE",
    "apply_hard_rules",
]

#: The level a hard fail lifts the score to when a caller names no other.
#: **Above the High threshold rather than at it**, so a hard fail reaches High
#: by the same arithmetic as any other score and 7.9's band thresholds are not
#: given a fourth case to special-case.
DEFAULT_HARD_FAIL_FLOOR = 90.0

#: The two ends of the score scale, named here rather than written as `0` and
#: `100` at each use, so 7.7's clamp is held to one pair of numbers.
MIN_SCORE = 0.0
MAX_SCORE = 100.0


def _score(field: str, number: object) -> float:
    """``number`` as the ``float`` a score may be, or a refusal naming it."""
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise FlagValueError(
            f"{field} must be a real number, not {type(number).__name__}"
        )
    if not math.isfinite(number):
        raise FlagValueError(f"{field} must be a finite number")
    return float(number)


def _floor(floor: object) -> float:
    """The floor as the ``float`` on the scale, or a refusal naming it."""
    level = _score("floor", floor)
    if not MIN_SCORE <= level <= MAX_SCORE:
        raise FlagValueError(
            f"floor must lie in [{MIN_SCORE:g}, {MAX_SCORE:g}]"
        )
    return level


def _overrides(flags: Iterable[object], hard_fail_ids: object) -> bool:
    """Whether a rule ``hard_fail_ids`` names has fired among ``flags``.

    **A bare ``str`` is refused rather than iterated.**  ``"WATCHLIST_HIT"``
    iterated is eleven characters that match no id, so the mistake would
    answer every screening with the sum it already had and never raise.

    **Every flag is read, not only those up to the first override**, so a
    record carrying no ``id`` is refused wherever in the sequence it sits --
    the same discipline :func:`~app.risk.scoring.weighted_sum` is held to for
    a term it cannot add.
    """
    if isinstance(hard_fail_ids, (str, bytes)) or not isinstance(
        hard_fail_ids, Iterable
    ):
        raise FlagValueError(
            "hard_fail_ids must be a collection of flag ids, not "
            f"{type(hard_fail_ids).__name__}"
        )
    table = frozenset(hard_fail_ids)
    fired = [
        _flag_id(flag, "for the hard-rule question to be asked of it")
        for flag in flags
    ]
    return any(flag_id in table for flag_id in fired)


def apply_hard_rules(
    score: object,
    flags: Iterable[object],
    hard_fail_ids: Iterable[str],
    *,
    floor: float = DEFAULT_HARD_FAIL_FLOOR,
) -> float:
    """``score`` lifted to ``floor`` when one of ``hard_fail_ids`` has fired.

    :param score: the sum :func:`~app.risk.scoring.weighted_sum` returned, in
        points on the 0-100 scale and possibly above it (``D21``).
    :param flags: the records that sum was computed from, in any order.
        :class:`~app.risk.flags.EvidenceFlag` is the record this is written
        for; the ``id`` is read by :func:`app.risk.flags._flag_id` and nothing
        else about a flag is touched.
    :param hard_fail_ids: the ids of the rules that override -- 6.5's answer,
        passed in rather than imported.  Any iterable of them will do, and a
        generator is consumed once.
    :param floor: the level to lift the score to, keyword-only and defaulted
        to :data:`DEFAULT_HARD_FAIL_FLOOR`.
    :returns: ``floor`` when an overriding rule fired and ``floor`` is above
        ``score``, and ``score`` unchanged otherwise.  Always a ``float``.
    :raises FlagValueError: when ``score`` is not a finite real number, when
        ``floor`` is not one inside ``[0, 100]``, when ``hard_fail_ids`` is
        ``None`` or a bare string rather than a collection of ids, or when a
        record in ``flags`` carries no ``id``.
    """
    total = _score("score", score)
    level = _floor(floor)

    if _overrides(flags, hard_fail_ids) and total < level:
        return level
    return total
