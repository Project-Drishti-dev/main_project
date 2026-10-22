"""Part 14's cascade: one screening carried in one record.

``ScreeningContext`` holds what the caller brought -- the screening id, the
document claim, the frame, the injected day and the checkpoint's depth --
beside the flags found so far and the stage trace.  ``STAGES`` holds the
stage callables the cascade may run, by name, and ``resolve_stage`` answers
one or refuses the name no registry holds.  Stage 0 is 14.3's capture gate,
``app.pipeline.quality.run_quality``, the first stage to write flags.
Stage 1 is 14.5's Tier 1, the first to write a score, as ``context.r1``.
Escalation is 14.6's and the rest of its part: ``escalations`` holds why a run
was sent on, and ``escalated`` is read off that list rather than stored beside
it.  ``run_cascade`` runs the registry in order and stops at the first hard
fail, leaving one :class:`StageTrace` row per stage it ran on
`context.stage_trace` and returning them as a :class:`CascadeResponse`.  A
stage that raises is traced as failed and the cascade runs on, so one
broken check does not lose the screening.
"""

import dataclasses
import time
import types
import typing
import uuid

from app.pipeline import quality
from app.pipeline.tier0 import stage as tier0_stage
from app.pipeline.tier0.dates import ReferenceDate
from app.pipeline.tier1 import stage as tier1_stage
from app.risk.flags import EvidenceFlag

__all__ = [
    "DEPTH_MODES",
    "FULL_DEPTH",
    "STAGES",
    "STAGE_NAMES",
    "STANDARD",
    "CascadeResponse",
    "ContextValueError",
    "ScreeningContext",
    "Stage",
    "StageTrace",
    "UnknownStageError",
    "resolve_stage",
    "run_cascade",
]

#: The ordinary cascade: Tier 2 runs only when a trigger asks for it.
STANDARD = "standard"

#: The abstract's full-depth mode, where Tier 2 runs whatever else answers.
FULL_DEPTH = "full_depth"

#: Every depth a context may carry, in cascade order.
DEPTH_MODES = (STANDARD, FULL_DEPTH)


class ContextValueError(ValueError):
    """Raised when a field of a :class:`ScreeningContext` is not well formed.

    A ``ValueError``, so a caller already catching one around its own wiring
    keeps working.  Messages name the field and the type, never the value.
    """


def _check_screening_id(screening_id: object) -> None:
    """Refuse ``screening_id`` unless it is a :class:`uuid.UUID`."""
    if not isinstance(screening_id, uuid.UUID):
        raise ContextValueError(
            "screening_id must be a uuid.UUID, not "
            f"{type(screening_id).__name__}"
        )


def _check_depth_mode(depth_mode: object) -> None:
    """Refuse ``depth_mode`` unless it names one of :data:`DEPTH_MODES`."""
    if not isinstance(depth_mode, str) or depth_mode not in DEPTH_MODES:
        raise ContextValueError(
            "depth_mode must be one of " + ", ".join(DEPTH_MODES)
        )


@dataclasses.dataclass(frozen=True)
class StageTrace:
    """One line of the stage trace: what ran, when, what it cost, what it added.

    :param stage: the registry name that ran.
    :param started: the clock reading taken before the stage was handed the context.
    :param elapsed: seconds from that reading to the stage returning.
    :param flags_added: how many findings the stage left on `context.flags`.
    :param escalated: whether the run was escalated once the stage returned,
        read off the reasons rather than stored beside them (D109).
    :param failed: whether the stage raised instead of returning (D114).  A
        stage that raised did run, so it is in the trace and in `ran`; the
        words it failed with are not (D106's own rule, kept).
    """

    stage: str
    started: float
    elapsed: float
    flags_added: int
    escalated: bool
    failed: bool


@dataclasses.dataclass
class ScreeningContext:
    """One screening, mutable because every stage of the cascade writes to it.

    The five caller-stated fields -- id, document claim, frame, reference day
    and depth -- are required; ``flags`` and ``stage_trace`` start empty and
    grow, and an empty one says no stage has run yet rather than that a
    document is clean.  ``hard_fail_reason`` starts ``None`` and is the
    cascade's one stop signal.  ``r1`` starts ``None`` and Tier 1 alone writes
    it, because no other stage produces a score.  ``escalations`` starts empty
    and holds one sentence per trigger that fired.  ``issuing_state`` starts
    ``None``, the claim 14.7's profile reads and that nothing writes yet.
    """

    screening_id: uuid.UUID
    document_type: str | None
    #: The working frame, typed ``Any`` because no gate here judges a frame.
    image: typing.Any
    #: The injected day, or ``None`` for a caller who injected none.
    reference_date: ReferenceDate | None
    #: The checkpoint's depth, required so no context can assume ``STANDARD``.
    depth_mode: str
    #: The findings so far, in the order the stages produced them.
    flags: list[EvidenceFlag] = dataclasses.field(default_factory=list)
    #: Why the cascade stopped, or ``None`` while it may still run on.  **A
    #: reason is the hard fail**: there is no second field beside it, so the
    #: two cannot disagree the way a bool and a sentence could.
    hard_fail_reason: str | None = None
    #: Tier 1's partial score, or ``None`` while Tier 1 has not run.  **A Tier 1
    #: that ran and found nothing writes ``0.0``**, which is an answer rather
    #: than an absence, so ``None`` means only that the tier has not run.
    r1: float | None = None
    #: Why this run was sent on: one sentence per trigger, in the order they
    #: fired.  **The reasons are the whole answer**, so :attr:`escalated` is
    #: read off this list rather than stored beside it, and the two cannot
    #: disagree the way a bool and a sentence could.
    escalations: list[str] = dataclasses.field(default_factory=list)
    #: One :class:`StageTrace` per stage run, in the order the stages ran, so
    #: the trace reads as the cascade did.
    stage_trace: list[StageTrace] = dataclasses.field(default_factory=list)

    #: The issuing state the document claims, or ``None`` while no page has
    #: claimed one.  **``None`` is an absence and not a hit**: no MRZ reaches
    #: the context today, and 14.7's watchlist must not read the absence as
    #: a match.
    issuing_state: str | None = None

    def __post_init__(self) -> None:
        """Check the two fields no stage owns; assign nothing."""
        _check_screening_id(self.screening_id)
        _check_depth_mode(self.depth_mode)

    @property
    def escalated(self) -> bool:
        """Whether a trigger has fired; read off the reasons, never stored."""
        return bool(self.escalations)


#: What one stage of the cascade is: handed the context, and answering only
#: by what it writes onto it.
Stage = typing.Callable[[ScreeningContext], None]

#: The stages this cascade may run, by name and in cascade order, behind a
#: read-only proxy so no caller can edit the set the cascade draws from.
#: **Stage 0 is the capture gate**, the one stage that runs before tier 0 and
#: the only one whose findings are about the photograph rather than the page.
#: **Tier 0 runs after it**, and a hard fail Tier 0 writes ends the cascade.
#: **Tier 1 runs after that**, and is the only stage that writes a score.
STAGES: typing.Mapping[str, Stage] = types.MappingProxyType(
    {
        quality.STAGE_NAME: quality.run_quality,
        tier0_stage.STAGE_NAME: tier0_stage.run_tier0,
        tier1_stage.STAGE_NAME: tier1_stage.run_tier1,
    }
)

#: The names :data:`STAGES` holds, in the order it holds them in.
STAGE_NAMES = tuple(STAGES)


class UnknownStageError(ValueError):
    """Raised when a name asks for a stage the registry does not hold.

    A ``ValueError``, so a caller already catching one keeps working.  A
    wiring mistake and not an absence, so the message names the stages this
    call does know and echoes the name that was asked for.
    """


def resolve_stage(
    name: str, *, stages: typing.Mapping[str, Stage] | None = None
) -> Stage:
    """The stage ``name`` asks for, refusing a name no registry holds.

    :param name: one of :data:`STAGE_NAMES`, spelled exactly.
    :param stages: the registry to read; defaults to :data:`STAGES`.
    :returns: the callable ``stages`` holds under that name.
    :raises UnknownStageError: when ``name`` is not a string, or names no
        stage in ``stages``.
    """
    known = STAGES if stages is None else stages
    if isinstance(name, str) and name in known:
        return known[name]
    raise UnknownStageError(
        f"stage name must be one of {_known_names(known)}; {name!r} is not one."
    )


def _known_names(known: typing.Mapping[str, Stage]) -> str:
    """The names ``known`` holds in its own order, or a phrase naming none."""
    return ", ".join(known) or "(none registered)"


@dataclasses.dataclass(frozen=True)
class CascadeResponse:
    """What one cascade call answers: the stages that ran, and their trace.

    :param ran: the names that ran, in order; a stage a hard fail kept out is
        absent rather than recorded as skipped, and a stage that raised is
        present because it ran, marked on its own row.
    :param trace: those same stages as :class:`StageTrace` rows, in that order.
    """

    ran: tuple[str, ...]
    trace: tuple[StageTrace, ...]


def _run(stage: Stage, context: ScreeningContext) -> bool:
    """Run one stage, answering whether it returned rather than raising.

    The exception is swallowed and none of it is carried: a row records that
    the stage failed, never the words it failed with (D114).
    """
    try:
        stage(context)
    except Exception:
        return False
    return True


def run_cascade(
    context: ScreeningContext,
    *,
    stages: typing.Mapping[str, Stage] | None = None,
    clock: typing.Callable[[], float] = time.perf_counter,
) -> CascadeResponse:
    """Run the registered stages in cascade order, stopping at a hard fail.

    A stage that raises is recorded as failed and the next one still runs, so
    one broken check costs its own row rather than the whole screening.

    :param context: the run's record; every stage below writes onto it.
    :param stages: the registry to run, in the order it holds them; defaults
        to :data:`STAGES`.
    :param clock: a callable reading seconds; defaults to
        :func:`time.perf_counter`, which cannot run backwards, and no wall
        clock is kept beside it because the screening already carries a
        timestamp.
    :returns: a :class:`CascadeResponse` whose `ran` is the names that ran
        and whose `trace` is one row per stage, appended to
        `context.stage_trace` as each stage finishes.
    """
    known = STAGES if stages is None else stages
    ran: list[str] = []
    trace: list[StageTrace] = []
    for name, stage in known.items():
        started = clock()
        before = len(context.flags)
        failed = not _run(stage, context)
        row = StageTrace(
            stage=name,
            started=started,
            elapsed=clock() - started,
            flags_added=len(context.flags) - before,
            escalated=context.escalated,
            failed=failed,
        )
        ran.append(name)
        trace.append(row)
        context.stage_trace.append(row)
        if context.hard_fail_reason is not None:
            break
    return CascadeResponse(ran=tuple(ran), trace=tuple(trace))
