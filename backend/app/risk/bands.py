"""Which band a score reads as: the one question asked of the finished number.

The abstract has the risk engine "combine all flags into a score R and a band
(Low Risk, Review or High Risk)", and 7.5 to 7.7 are the three answers that
come before this one -- a sum, a floor, and a number on the scale.  What an
officer reads is none of those numbers.  It is one of three bands, and this
module is the one place in the package that decides which.

**Each threshold belongs to the band below it, and the names say so.**  34 is
:data:`~app.risk.config.LOW_MAX` and not the first ``review`` score: it is the
last ``low`` one.  69 is :data:`~app.risk.config.REVIEW_MAX` and not the first
``high`` one: it is the last ``review`` one.  So on the scale the three bands
are ``[MIN_SCORE, LOW_MAX]``, ``(LOW_MAX, REVIEW_MAX]`` and
``(REVIEW_MAX, MAX_SCORE]`` -- every band closed at its own top and open at the
bottom, which is what makes a boundary one score wide rather than a
contested point.  **The edges are read, never written out**; a ``34`` or a
``69`` compared here would band every document correctly today and be wrong
the day ``D28``'s pair was retuned, with no import to find and no name to
grep for.

**A row's band and a document's band are two different questions.**  The
``band`` in ``weightsets/v1.yaml`` is the severity class a *weight* sits in --
what one finding is worth -- and this answers for a *sum*.  The committed file
already shows them apart: two 30-point rows are banded ``review`` there, and
30 points on a document reads ``low``, because a clean document carrying one
dating irregularity is a document with a question on it rather than a case for
a second officer.  Nothing here reads the weightset, and a band is never
derived from a weight.

**A score that is not a number is refused, and a ``nan`` is why.**  The
validation is 7.6's :func:`~app.risk.hard_rules._score`, shared rather than
written a second time for 7.3's and 7.5's reason.  A ``nan`` compares false
against both thresholds, so a band written as two comparisons falls through
them and answers ``high`` -- the one answer a number that is not a number must
never produce, on a document no officer can then act on.  A ``bool`` is
refused for the same kind of reason: ``True`` is ``1`` and would read ``low``.

**Nothing is clamped and nothing off the scale is refused.**  7.7's
:func:`~app.risk.clamp_score` is what puts a score on the scale, and a caller
that skipped it has been handed the wrong number rather than a new case to
handle.  This module reads its argument and decides; it does not edit it, and
the two questions compose rather than merge (``D27``'s reason, and the reason
7.6 and 7.7 kept answering in either order).

**Invariants**

- The answer is one of ``flags.WEIGHT_BANDS`` -- the three names
  :attr:`~app.risk.flags.EvidenceFlag.weight_band` is checked against -- and
  ``tasks.md``'s lowercase spelling of them.  "Low Risk" and "High Risk" are
  the officer-facing spelling and 23.5's to render, not a second vocabulary
  to band in.
- **Every score has exactly one band.**  The three ranges are disjoint and
  together cover the scale, so no score is unbanded and none is in two.
- **Raising a score never lowers its band** and never leaves it where it was,
  so the reading moves at the two thresholds and nowhere else.
- A score is compared against the two thresholds and nothing else: no third
  edge, no default, no band of a band.
- No flag is read, no weightset is opened, no file is read, and no clock or
  randomness is reached, so the same score bands the same way on every run and
  a replay of a screening is a replay of its band.
- ``app.pipeline`` is not imported, on ``D6``'s one-way dependency: rules
  emit records and the engine consumes them, never the other way round.
"""

from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.hard_rules import _score

__all__ = ["to_band"]


def to_band(score: object) -> str:
    """``score`` as the band an officer reads: ``low``, ``review`` or ``high``.

    :param score: the finished number to read -- normally 7.7's
        :func:`~app.risk.clamp_score` over 7.6's
        :func:`~app.risk.hard_rules.apply_hard_rules` over 7.5's
        :func:`~app.risk.scoring.weighted_sum`, and therefore already inside
        ``[MIN_SCORE, MAX_SCORE]``.
    :returns: ``"low"`` when ``score`` is at or below
        :data:`~app.risk.config.LOW_MAX`, ``"review"`` when it is above that
        and at or below :data:`~app.risk.config.REVIEW_MAX`, and ``"high"``
        above that.  Both comparisons include the threshold they read, which
        is what the ``_MAX`` in each name says.
    :raises ~app.risk.flags.FlagValueError: when ``score`` is not a finite real
        number -- a ``None``, a boolean, a string, an object, a ``nan`` or an
        infinity -- from 7.6's :func:`~app.risk.hard_rules._score`.  A score
        that is merely *below* or *above* the scale is banded, not refused.
    """
    total = _score("score", score)
    if total <= LOW_MAX:
        return "low"
    if total <= REVIEW_MAX:
        return "review"
    return "high"
