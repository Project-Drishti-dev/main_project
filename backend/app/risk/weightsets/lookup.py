"""The one lookup from a flag id to the weight the engine scores it with.

7.2's loader parses a weightset and hands back a frozen
:class:`~app.risk.weightsets.loader.Weightset`; this module is what a caller
asks that record with.  **The lookup is a function over the record and never a
second reader of ``v1.yaml``**, so a caller is answered from the rows it is
already holding and the file is opened in exactly one place.

**An id the record carries no row for raises rather than answering zero.**  The
engine's sum is ``R = sum(w_i * F_i)``, so a finding with no weight is a
finding worth nothing: it reaches the officer's list of reasons having moved
no score at all, and a screening can be answered ``low`` on a finding the
weightset never mentioned.

**A row that carries no finite numeric weight raises for the same reason**, and
so does a row that is not a mapping at all.  A ``band`` with no ``weight`` read
with ``.get`` is ``0.0``; a boolean weight is inside ``[0, 1]`` in Python's own
arithmetic; and a ``nan`` is quieter still, because every comparison against it
is false and the band it lands in is decided by nothing.

**The refusals raise
:exc:`~app.risk.weightsets.loader.WeightsetError` rather than ``KeyError``.**
The exception is a ``ValueError``, so a caller already catching ``ValueError``
around the code that loads a weightset keeps catching it, and a ``KeyError``
reads like a bug in the caller rather than a flag with no weight.  **A message
names the id and the ruleset version**, both of which are rule names and
nothing read off a document.
"""

import math
from collections.abc import Mapping

from app.risk.weightsets.loader import Weightset, WeightsetError

__all__ = ["WEIGHT_KEY", "weight_for"]

#: The key a row carries its weight under.  Named rather than written inline so
#: the file's own spelling is the one the lookup reads.
WEIGHT_KEY = "weight"


def _is_scoreable(value: object) -> bool:
    """Whether ``value`` is a real number a score may be built from."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def weight_for(weightset: Weightset, flag_id: str) -> float:
    """The weight ``flag_id`` carries in ``weightset``, as a ``float``.

    Answers from the rows the record already holds, and refuses rather than
    defaulting to a number: an id with no row, a row that is not a mapping, and
    a row whose :data:`WEIGHT_KEY` is missing or is not a finite number all
    raise :exc:`~app.risk.weightsets.loader.WeightsetError`.

    The id is not checked against
    :data:`app.risk.flag_ids.FLAG_IDS` here: the vocabulary is what a rule may
    emit, and a weightset is what a screening is scored against, so an id the
    vocabulary has and the file does not is 7.1's completeness test's claim
    about the file rather than this module's to re-judge.
    """
    ruleset = weightset.ruleset_version

    if flag_id not in weightset.flags:
        raise WeightsetError(
            f"the {ruleset!r} weightset carries no row for {flag_id!r}"
        )

    row = weightset.flags[flag_id]
    if not isinstance(row, Mapping):
        raise WeightsetError(
            f"the row for {flag_id!r} in the {ruleset!r} weightset is not a mapping"
        )

    weight = row.get(WEIGHT_KEY)
    if not _is_scoreable(weight):
        raise WeightsetError(
            f"the row for {flag_id!r} in the {ruleset!r} weightset carries no "
            f"finite numeric {WEIGHT_KEY!r}"
        )

    return float(weight)
