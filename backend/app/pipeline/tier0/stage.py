"""14.4: Tier 0 as a stage of the cascade.

:func:`run_tier0` hands the context's frame, claim and injected day to
:func:`app.pipeline.tier0.runner.run_tier0` and writes what came back onto the
context.  A hard fail is written as its reason and nothing else, and
:func:`app.pipeline.orchestrator.run_cascade` reads that one field to stop.
"""

import typing

from app.pipeline.tier0 import runner

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = ["STAGE_NAME", "run_tier0"]

#: The name the cascade's registry holds this stage under, read off the
#: runner's own so the two cannot spell the tier differently.
STAGE_NAME = runner.TIER_NAME


def run_tier0(context: "ScreeningContext") -> None:
    """Run Tier 0 over ``context``, writing its findings and hard fail onto it.

    :param context: the run's record; only ``flags`` and ``hard_fail_reason``
        grow, and neither a parse nor a watchlist is asked because the context
        carries neither to hand over.
    :returns: ``None`` -- the stage answers by what it wrote.
    """
    result = runner.run_tier0(
        context.image,
        document_type=context.document_type,
        reference_date=context.reference_date,
    )
    context.flags.extend(result.flags)
    if result.hard_failed:
        context.hard_fail_reason = result.hard_fail_reason
