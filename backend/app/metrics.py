"""26.8: what one screening cost, and how its cascade ended.

Two events and one closed vocabulary, so the flow decides *when* a cascade
is measured and never *how* the answer is spelled.  A metric is a log line
and nothing more: the service has one channel (D76), and a second one would
be a second thing to correlate by id.
"""

import logging
import uuid
from collections.abc import Sequence

from app.logging_config import log_event

__all__ = [
    "CASCADE_OUTCOMES",
    "CASCADE_OUTCOME_EVENT",
    "OUTCOME_COMPLETED",
    "OUTCOME_FAILED",
    "OUTCOME_HARD_FAILED",
    "TIER_LATENCY_EVENT",
    "emit_cascade_outcome",
    "emit_tier_latency",
]


#: One line per tier the cascade ran, naming what that tier cost.  Per *tier*
#: and not per stage: 6.6 already times a tier's own stages inside its
#: result, and this is the caller's half -- the tier as the cascade paid for
#: it.
TIER_LATENCY_EVENT = "cascade_tier_latency"

#: One line per cascade, naming how the whole of it ended.  Written even for
#: a cascade that raised, which is the outcome the other two cannot describe.
CASCADE_OUTCOME_EVENT = "cascade_outcome"

#: Every tier of the plan ran and none of them stopped it.
OUTCOME_COMPLETED = "completed"

#: A tier hard-failed, which is the cascade's one stop (6.5).
OUTCOME_HARD_FAILED = "hard_failed"

#: A tier raised, so the cascade answered nothing at all.
OUTCOME_FAILED = "failed"

#: The three ways a cascade can end, in that order.  Frozen because a reader
#: groups by this name, and a fourth way to end has to be added here rather
#: than discovered in a log.
CASCADE_OUTCOMES = (OUTCOME_COMPLETED, OUTCOME_HARD_FAILED, OUTCOME_FAILED)

logger = logging.getLogger(__name__)


def emit_tier_latency(
    *,
    screening_id: uuid.UUID,
    tier: str,
    elapsed_ms: float,
    flags_found: int,
    hard_failed: bool,
) -> None:
    """Write one tier's latency line, naming the row it belongs to.

    :invariant: every field is this repository's own vocabulary -- a row's
        opaque id, a tier's name, a duration, a count and a boolean -- so
        11.7's ban holds for this line as it does for every other.
    """
    log_event(
        logger,
        TIER_LATENCY_EVENT,
        screening_id=str(screening_id),
        tier=tier,
        elapsed_ms=elapsed_ms,
        flags_found=flags_found,
        hard_failed=hard_failed,
    )


def emit_cascade_outcome(
    *,
    screening_id: uuid.UUID,
    outcome: str,
    tiers_run: Sequence[str],
    elapsed_ms: float,
    flags_found: int,
) -> None:
    """Write one cascade's outcome line, including for a cascade that raised.

    :param tiers_run: the tiers that ran, in the order they ran.  A tier a
        hard fail kept out is absent rather than recorded as skipped, so the
        names are the trail's own answer rather than a second one.
    :invariant: ``outcome`` is one of :data:`CASCADE_OUTCOMES`, and the line
        is written exactly once per cascade.
    """
    log_event(
        logger,
        CASCADE_OUTCOME_EVENT,
        screening_id=str(screening_id),
        outcome=outcome,
        tiers_run=list(tiers_run),
        elapsed_ms=elapsed_ms,
        flags_found=flags_found,
    )