"""The clamp: the last question asked of a score, and the only one that edits it.

:func:`~app.risk.scoring.weighted_sum` answers ``R`` in points and is allowed
to run over the top of the scale (``D21``), and
:func:`~app.risk.hard_rules.apply_hard_rules` may lift it to a floor.  What an
officer reads is neither of those numbers: it is a point on a 0-100 scale, and
this module is what turns the first into the second.

**A clamp and not a rescale.**  195 points are held to 100 rather than being
divided by anything, and a score of 95 stays 95: the margin above a band
threshold is kept everywhere it exists and lost only where the scale ends.

**A score off the scale is answered rather than refused.**  ``D23`` and
``D24`` refuse a flag that cannot be scored, because there the answer would be
a number nobody can trace back to a weightset.  This is the other case:
corroborating findings *are* how a document reaches High, so 195 is a real
reading that happens to be larger than the scale can show, and refusing it
would fail a document instead of reporting it.  **What is refused is a score
that is not a finite real number at all** -- a ``nan`` passes no comparison, so
a clamp written as two comparisons would hand it back exactly as it was.

**The scale's ends are read, not retyped.**  :data:`MIN_SCORE` and
:data:`MAX_SCORE` are 7.6's and are imported rather than written as ``0`` and
``100`` at each use, so a retune of the scale is one edit and a stale ``100``
cannot sit beside a moved ``MAX_SCORE``.  7.6's ``_score`` is the one
validation of a score for the whole package and is shared rather than written a
second time, for 7.3's and 7.5's reason: two answers to one question is how
they drift apart.

**Invariants**

- The answer is a ``float`` in ``[MIN_SCORE, MAX_SCORE]`` for every score,
  whatever integer type the number arrived as.
- **A score inside the scale is handed back exactly**, and both ends are levels
  rather than the first number off them: :data:`MIN_SCORE` and
  :data:`MAX_SCORE` answer themselves.
- **Holding it twice is holding it once**, and the answer never depends on
  which number was offered first.
- Nothing is summed, scaled, banded, weighted or amended.  No band threshold
  is consulted -- :data:`~app.risk.hard_rules.MAX_SCORE` is the top of the
  scale and not 7.8's ``REVIEW_MAX``, and comparing against one is 7.9's
  question.
- No flag is read, no file is opened, and no clock or randomness is reached,
  so the same score always clamps to the same answer.
"""

from app.risk.hard_rules import MAX_SCORE, MIN_SCORE, _score

__all__ = ["clamp_score"]


def clamp_score(score: object) -> float:
    """``score`` held to ``[MIN_SCORE, MAX_SCORE]``, as a ``float``.

    :param score: the number to hold to the scale -- normally the answer of
        :func:`~app.risk.scoring.weighted_sum`, and possibly the answer of
        :func:`~app.risk.hard_rules.apply_hard_rules` over that.
    :returns: :data:`MIN_SCORE` when ``score`` is below the scale,
        :data:`MAX_SCORE` when it is above it, and ``score`` itself otherwise,
        unchanged and to the last bit.
    :raises ~app.risk.flags.FlagValueError: when ``score`` is not a finite real
        number -- a ``None``, a boolean, a string, a ``nan`` or an infinity --
        from 7.6's ``_score``.  A score that is merely *large* or *negative* is
        answered, not refused.
    """
    total = _score("score", score)
    return max(MIN_SCORE, min(total, MAX_SCORE))
