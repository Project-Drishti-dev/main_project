"""14.5: Tier 1 as a stage of the cascade, and the partial score ``R1``.

:func:`run_tier1` hands the context's frame to
:func:`app.pipeline.tier1.runner.run_tier1`, extends ``context.flags`` with the
findings that came back, and writes their weighted sum to ``context.r1``.
"""

import typing

from app.pipeline.tier1 import runner
from app.risk import scoring
from app.risk.weightsets.loader import Weightset, load_weightset

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = ["STAGE_NAME", "run_tier1"]

#: The name the cascade's registry holds this stage under.
STAGE_NAME = "tier_1"


def run_tier1(
    context: "ScreeningContext",
    *,
    weightset: Weightset | None = None,
) -> None:
    """Run Tier 1 over ``context``, writing its findings and ``r1`` onto it.

    :param context: the run's record; only ``flags`` and ``r1`` grow.
    :param weightset: the weightset ``R1`` is scored against; defaults to the
        shipped one, read per call so a retuned file is the one scored.
    :returns: ``None`` -- the stage answers by what it wrote.
    :raises WeightsetError: from :func:`~app.risk.scoring.weighted_sum`, when a
        finding carries no weight in ``weightset``.
    """
    result = runner.run_tier1(context.image)
    context.flags.extend(result.flags)
    ruleset = load_weightset() if weightset is None else weightset
    context.r1 = scoring.weighted_sum(result.flags, ruleset)
