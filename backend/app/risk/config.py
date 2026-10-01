"""The two thresholds a score is read against: where ``low`` ends, and where
``review`` does.

The engine answers a score in points and an officer reads a band.  This module
holds the pair of numbers that separate the three bands, so "which band is
this score" has one answer in the package and not one per caller.  Deciding a
band is 7.9's ``to_band``; this module compares nothing, because a boundary
written here as well as there is a boundary that can disagree with itself.

**The thresholds are committed policy, not a deployment setting.**  The
abstract says thresholds are chosen against a target false-alert rate and a
target catch rate and are *versioned so that every change to policy is
recorded*, and 7.8's pair is the first half of that: they are part of the
ruleset, they are read from one place, and changing them is a change to
``RULESET_VERSION`` in the same commit (``D22``).  So there is no environment
variable here and none in ``.env.example`` -- a threshold a deployment could
retune would let it change what a score means with nothing recording the
change, and ``D21``'s claim that no single finding reaches High would then
hold only for the deployment that never touched it.

**Neither number is free.**  Both are read against the committed weightset by
``test_band_thresholds.py``: every ``low`` row must weigh no more than
:data:`LOW_MAX` and every other row no more than :data:`REVIEW_MAX`, so a
threshold and the weights it divides are held to each other rather than
restated beside one another.

**Invariants**

- ``MIN_SCORE <= LOW_MAX < REVIEW_MAX < MAX_SCORE``, where the two ends are
  7.6's.  Read in the direction a score is read: a clean document's 0 must be
  able to land in ``low``, a score of 100 must be able to land in ``high``,
  and the band between the two must be a range rather than a single point.
- Both are ``float``, like the ends of the scale they divide, so 7.9's
  comparisons are between two numbers of one kind.
- No clock, no randomness, no file and no environment: the same score reads as
  the same band on every run and on every deployment, or a replay of a
  screening is not a replay of anything.
- Nothing here is clamped, weighted or validated at import.  A constant that
  raised on the way in would fail an import rather than a screening, and
  ``-O`` strips an ``assert``; the suite holds the ordering above instead.
"""

__all__ = ["LOW_MAX", "REVIEW_MAX"]

#: The highest score still in ``low``.  A score above it is ``review`` or
#: ``high``, and 7.9 is what draws that line.  **Above any pile of the two
#: ``low`` rows the vocabulary has** -- they weigh 15 each, so two confirmed
#: low findings at full strength are 30 and stay low, and a third crosses.
#: A ``low`` row may therefore never weigh more than this, which is the rule
#: the test file holds against ``v1.yaml``.
LOW_MAX = 34.0

#: The highest score still in ``review``.  **One point clear of the heaviest
#: weight in the committed file**, which is 65, and that is ``D21``'s
#: arithmetic rather than a round number: High is reached by corroborating
#: findings or by 7.6's hard-fail floor of 90, never by one flag on its own.
REVIEW_MAX = 69.0
