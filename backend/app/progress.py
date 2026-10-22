"""18.10: what one screening's run recorded, as a sequence of progress steps.

A screening is screened synchronously -- ``POST /api/screenings`` answers with
its two ids only after the cascade has finished -- so there is nothing here to
watch while a run is in flight.  What this module owns is the other half of
that fact: **the progress a finished run left behind**, read back off the row
and the trail beside it, and spelled as the server-sent events the stream
route carries and as the one document a polling caller asks for.

**Two units and two states, and they are not the same word.**  A tier is
``completed`` because the trail wrote a ``tier_completed`` event naming it, and
a module is ``reported`` because a stored finding names it as the module that
made it.  A module that ran and found nothing leaves no step at all, which is
why its state is not ``completed``: the sequence says what the trail recorded
and never claims a clean module did not run.

**18.12 is the same walk with the instants kept.**  `build_stage_trace` answers
where a run's time went, and it rides the screening's own answer rather than a
route of its own: a stage is a `tier_completed` event, its cost is the window
between it and the instant recorded before it, and the whole is read off the
run's first and last instants rather than summed from its windows.  A module is
not a stage and carries no timing, because a stored finding is not an event
with an instant on it.

**Nothing read off the document is in an event.**  No finding id, no expected
or found value, no region, no score and no filename -- a frame carries tier
names, module names and a count, which are this repository's own words.
Rationale in ``docs/DECISIONS.md`` D151, D152 and D153.
"""

import dataclasses
import json
import uuid
from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.audit.event_types import (
    ANALYSIS_COMPLETED,
    SCREENING_CREATED,
    TIER_COMPLETED,
)
from app.screening import TIER_KEY
from app.storage.models import AuditEvent, Screening

__all__ = [
    "DONE_EVENT",
    "PROGRESS_EVENT",
    "STATE_COMPLETED",
    "STATE_REPORTED",
    "UNKNOWN_TIER",
    "UNIT_MODULE",
    "UNIT_TIER",
    "ProgressEvent",
    "ProgressReport",
    "StageTiming",
    "StageTrace",
    "build_progress",
    "build_stage_trace",
]

#: The two units this reports on: a tier the cascade ran, and a module inside
#: one.  Plain text rather than an enum, because they cross the wire.
UNIT_TIER = "tier"
UNIT_MODULE = "module"

#: What each unit did.  **Not one word for both, and that is the point**: the
#: trail is the record of a tier completing, and a stored finding is the only
#: record of a module having spoken at all.
STATE_COMPLETED = "completed"
STATE_REPORTED = "reported"

#: The event names on the wire -- one per step, then the one that ends the
#: stream.  A client that reads only ``done`` still learns how far it got.
PROGRESS_EVENT = "progress"
DONE_EVENT = "done"

#: The tier a finding is filed under when it names none.  Every flag requires
#: a tier, so this is a defence against a row written by something other than
#: this cascade rather than a state the cascade produces.
UNKNOWN_TIER = "unknown"

#: The three event names a run writes for itself, and the only three a cost is
#: measured from: the instant before the cascade ran, one per tier that
#: returned, and the instant the run answered.  A decision is written by an
#: officer after the run and belongs to no stage, so reading the trail whole
#: would measure an officer's pause as a stage's work.
_RUN_EVENTS = (SCREENING_CREATED, TIER_COMPLETED, ANALYSIS_COMPLETED)

#: One run event as the read hands it on: what it was, what it carried and
#: when it was stamped -- plain values, so nothing outlives the session.
_RunEvent = tuple[str, dict[str, Any], datetime]


@dataclasses.dataclass(frozen=True)
class ProgressEvent:
    """One step of a run: what unit it was, which one, and what it did.

    :param unit: :data:`UNIT_TIER` or :data:`UNIT_MODULE`.
    :param state: what the unit did -- ``completed`` for a tier the trail
        recorded, ``reported`` for a module a stored finding names.
    :param tier: the tier this step belongs to; a tier event names its own.
    :param module: the module that reported, or ``None`` on a tier event.
    """

    unit: str
    state: str
    tier: str
    module: str | None

    def payload(self, screening_id: uuid.UUID) -> dict[str, Any]:
        """The step as the JSON object one frame's ``data:`` line carries.

        :param screening_id: the screening the stream is about, on every
            event rather than only the first, so a frame read back out of a
            log still says which screening it belongs to.
        :returns: those five keys, and nothing else.
        """
        return {
            "screening_id": str(screening_id),
            "unit": self.unit,
            "state": self.state,
            "tier": self.tier,
            "module": self.module,
        }


@dataclasses.dataclass(frozen=True)
class ProgressReport:
    """One screening's recorded progress, and the frames it streams as.

    :param screening_id: the screening every step below belongs to.
    :param events: the steps, in the order the run produced them -- each
        completed tier, then the modules that reported under it.
    """

    screening_id: uuid.UUID
    events: tuple[ProgressEvent, ...]

    def frames(self) -> Iterator[str]:
        """The whole stream as server-sent event frames, the last one ``done``.

        Yields one frame per recorded step and then exactly one ``done``
        frame, so a reader that stops there holds the whole sequence and the
        response ends on its own rather than waiting for a caller to hang up.
        """
        for event in self.events:
            yield _frame(PROGRESS_EVENT, event.payload(self.screening_id))
        yield _frame(
            DONE_EVENT,
            {"screening_id": str(self.screening_id), "units": len(self.events)},
        )

    def snapshot(self) -> dict[str, Any]:
        """The whole sequence as one JSON document, for a caller that polls.

        :returns: the screening's id, how many steps there are, and those
            steps as the same five keys each frame above carries, in the
            same order.  There is no second spelling for a poller to drift
            from: both this method and frames() read
            ProgressEvent.payload, and units is the count the done frame
            already reports.
        """
        return {
            "screening_id": str(self.screening_id),
            "units": len(self.events),
            "events": [
                event.payload(self.screening_id) for event in self.events
            ],
        }


@dataclasses.dataclass(frozen=True)
class StageTiming:
    """One stage's window: which stage, when it was recorded, what it cost.

    :param tier: the tier name that event's own payload carried.
    :param recorded_at: the instant it was stamped, which is where the stage
        ended -- a ``tier_completed`` event is written after the tier returned.
    :param elapsed_ms: whole milliseconds from the instant recorded before
        this one, or ``None`` when the run recorded nothing before it and so
        has no window to measure -- an absence, not a zero.
    """

    tier: str
    recorded_at: datetime
    elapsed_ms: int | None


@dataclasses.dataclass(frozen=True)
class StageTrace:
    """The stages one run recorded, and what the whole of that run cost.

    :param stages: one row per tier the trail recorded, in trail order.
    :param total_ms: whole milliseconds from the run's first event to the
        instant it answered, or ``None`` when either end was never recorded.
    """

    stages: tuple[StageTiming, ...]
    total_ms: int | None

    def document(self) -> dict[str, Any]:
        """The trace as the document a screening's own answer carries.

        :returns: ``total_ms`` and ``stages``, and nothing else.  Each stage
            names its tier, the instant it was recorded at and what the
            window before it cost; the screening is named by the answer
            this sits in, so nothing here repeats it.
        """
        return {
            "total_ms": self.total_ms,
            "stages": [
                {
                    "tier": stage.tier,
                    "recorded_at": stage.recorded_at,
                    "elapsed_ms": stage.elapsed_ms,
                }
                for stage in self.stages
            ],
        }


def build_progress(
    row: Screening, *, sessions: sessionmaker[Session]
) -> ProgressReport:
    """Read back what one screening's run recorded, as its progress steps.

    :param row: the screening, already read by the caller, so a row that is
        not there was refused before this was asked.
    :param sessions: the factory the trail is read through.
    :returns: a :class:`ProgressReport` holding each tier the trail recorded
        as completed, in the order it wrote them, followed by the modules
        whose stored findings named them.  A row with no event and no finding
        carries no step, and its stream is the ``done`` frame alone.
    """
    events = _run_events(row.id, sessions=sessions)
    completed = _completed_tiers(events)
    reported = _reporting_modules(row)
    return ProgressReport(
        screening_id=row.id, events=_steps(completed, reported)
    )


def build_stage_trace(
    row: Screening, *, sessions: sessionmaker[Session]
) -> StageTrace:
    """What one run's stages cost, read off the instants the trail recorded.

    **A window between two recorded instants, not a stopwatch around the
    stage.**  A stage is charged everything between its own event and the
    one before it, so what no stage is charged is the scoring and the store
    after the last tier -- which is why the whole is read off the run's own
    first and last instants rather than summed from its windows.

    :param row: the screening, already read by the caller.
    :param sessions: the factory the trail is read through.
    :returns: one row per tier the trail recorded, in trail order, and the
        run's whole cost.  A row nothing ran on carries neither, which is an
        absence rather than a zero.
    """
    return _trace(_run_events(row.id, sessions=sessions))


def _trace(events: tuple[_RunEvent, ...]) -> StageTrace:
    """The stages a run recorded, walked off its own events.

    A stage's window opens on the instant recorded before it -- the run's
    first event for the first stage, the stage before it after that -- so a
    decision written in between is never charged to a stage.

    :param events: the run's own events, in trail order.
    :returns: one row per recorded tier and the run's whole cost, each
        ``None`` rather than a zero where the trail recorded no instant to
        measure from.
    """
    created = _instants(events, SCREENING_CREATED)
    answered = _instants(events, ANALYSIS_COMPLETED)
    started = created[0] if created else None
    stages: list[StageTiming] = []
    previous = started
    for event_type, payload, recorded_at in events:
        if event_type != TIER_COMPLETED:
            continue
        tier = _tier_name(payload)
        if tier is None:
            continue
        stages.append(
            StageTiming(tier, recorded_at, _elapsed_ms(previous, recorded_at))
        )
        previous = recorded_at
    return StageTrace(
        tuple(stages),
        _elapsed_ms(started, answered[-1] if answered else None),
    )


def _run_events(
    screening_id: uuid.UUID, *, sessions: sessionmaker[Session]
) -> tuple[_RunEvent, ...]:
    """The events a run writes for itself, in the order it wrote them.

    :param screening_id: the screening the events belong to.
    :param sessions: the factory the events are read through.
    :returns: each event as its type, payload and instant, in the order
        :func:`_trail_order` puts them in rather than the order the rows
        landed in: the run's own first instant opens its timeline, the
        instant and then the id order each group, and an event stamped
        before that opening instant is walked last (D155).  Read as plain
        values inside the session, so none of it is touched after that
        session has closed.
    """
    with sessions() as session:
        stamped = [
            (event.event_type, event.payload or {}, event.created_at)
            for event in session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.screening_id == screening_id,
                    AuditEvent.event_type.in_(_RUN_EVENTS),
                )
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        ]
    return tuple(_trail_order(stamped))


def _trail_order(stamped: list[_RunEvent]) -> list[_RunEvent]:
    """The run's events in the order the run happened, not the clock's.

    A run opens at the instant its ``screening_created`` event carries -- the
    same instant ``_trace`` charges the first stage from -- so an event
    stamped before that instant cannot be placed on the run, whether a clock
    moved backwards or a writer backdated the row.  **Such an event is walked
    last, and each group keeps D151's order**, the instant and then the id,
    so a run whose clock never moved is in the order it was written in.  A
    run that opened with no event of its own has no instant to be behind, and
    is left as the trail holds it.

    :param stamped: the events as the trail holds them, oldest first.
    :returns: those events in the order both readers walk them.
    """
    opened_at = next(
        (
            recorded_at
            for event_type, _, recorded_at in stamped
            if event_type == SCREENING_CREATED
        ),
        None,
    )
    if opened_at is None:
        return list(stamped)
    return [event for event in stamped if event[2] >= opened_at] + [
        event for event in stamped if event[2] < opened_at
    ]


def _instants(
    events: tuple[_RunEvent, ...], event_type: str
) -> tuple[datetime, ...]:
    """Every instant one kind of event was stamped at, oldest first.

    :param events: the run's events, in trail order.
    :param event_type: the event name being asked about.
    :returns: those instants, or the empty tuple when it wrote none.
    """
    return tuple(
        recorded_at
        for kind, _, recorded_at in events
        if kind == event_type
    )


def _elapsed_ms(start: datetime | None, end: datetime | None) -> int | None:
    """Whole milliseconds from one recorded instant to another.

    :param start: where the window opens, or ``None`` for no window at all.
    :param end: where it closes, or ``None`` for the same reason.
    :returns: the width in whole milliseconds, and never below zero -- the
        stamps come from a wall clock, so a clock that moved backwards reads
        as no time rather than as a negative cost.
    """
    if start is None or end is None:
        return None
    return max(0, round((end - start).total_seconds() * 1000))


def _frame(name: str, payload: Mapping[str, Any]) -> str:
    """One server-sent event: a name line, one ``data:`` line, a blank line.

    :param name: the event name a client listens for.
    :param payload: the object the frame carries, sorted so the same step is
        the same bytes on every run.
    :returns: the frame as text, ended by the blank line that completes it.
    """
    return f"event: {name}\ndata: {json.dumps(payload, sort_keys=True)}\n\n"


def _completed_tiers(events: tuple[_RunEvent, ...]) -> list[str]:
    """The tiers the trail recorded as completed, in the order it wrote them.

    Read off ``_run_events``, which has already put them in the order the
    run happened: its own opening instant first, then each group's own
    instant and then its id (D155).  **A name twice is kept twice** --
    a tier that ran twice ran twice.

    :param events: the run's own events, in trail order.
    :returns: the tier names, in trail order, and none for an event naming
        no tier.
    """
    names: list[str] = []
    for event_type, payload, _ in events:
        if event_type != TIER_COMPLETED:
            continue
        name = _tier_name(payload)
        if name is not None:
            names.append(name)
    return names


def _tier_name(payload: Mapping[str, Any]) -> str | None:
    """The tier one ``tier_completed`` payload names, or ``None`` for no tier.

    The payload is the record, so a record carrying a non-text or an empty
    name names no stage and is skipped rather than filed under a
    placeholder that would read as one.

    :param payload: one stored event payload.
    :returns: the tier name it carries, or ``None``.
    """
    name = payload.get(TIER_KEY)
    return name if isinstance(name, str) and name else None


def _reporting_modules(row: Screening) -> dict[str, list[str]]:
    """The modules a stored finding names, per tier, in first-seen order.

    A flag carries the module that produced it, and that is the only record
    this repository keeps of a module having run.  A finding this cannot read
    as a mapping, or one naming no module, is skipped rather than filed under
    a placeholder name that would read as a module.

    :param row: the screening whose stored findings are read.
    :returns: tier name to the modules reported under it, each listed once.
    """
    groups: dict[str, list[str]] = {}
    for flag in row.flags or []:
        if not isinstance(flag, Mapping):
            continue
        module = flag.get("source_module")
        if not isinstance(module, str) or not module:
            continue
        reported = groups.setdefault(_tier_of(flag), [])
        if module not in reported:
            reported.append(module)
    return groups


def _tier_of(flag: Mapping[str, Any]) -> str:
    """The tier a stored finding belongs to, as text.

    A flag carries ``tier`` as ``0``, ``1``, ``2``, ``"quality"`` or
    ``"crossdoc"``, so the number is spelled rather than dropped: a stream
    saying ``"0"`` and a stream saying nothing about it would disagree about
    which tier a finding came from.

    :param flag: one stored finding.
    :returns: the tier it names, or :data:`UNKNOWN_TIER`.
    """
    raw = flag.get("tier")
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        return str(raw)
    return UNKNOWN_TIER


def _steps(
    completed: list[str], reported: Mapping[str, list[str]]
) -> tuple[ProgressEvent, ...]:
    """The steps, in cascade order: each completed tier, then its modules.

    A tier that only a finding names is still walked, and is walked after
    every tier the trail recorded -- the trail is the record of what ran, so
    a tier no event names is appended rather than ordered into the middle of
    the cascade on a finding's word alone.

    :param completed: the tiers the trail recorded, in trail order.
    :param reported: the modules each tier's findings named.
    :returns: the steps, tiers and their modules interleaved as above.
    """
    tiers = list(completed)
    for tier in reported:
        if tier not in tiers:
            tiers.append(tier)
    steps: list[ProgressEvent] = []
    for tier in tiers:
        if tier in completed:
            steps.append(
                ProgressEvent(UNIT_TIER, STATE_COMPLETED, tier, None)
            )
        for module in reported.get(tier, ()):
            steps.append(
                ProgressEvent(UNIT_MODULE, STATE_REPORTED, tier, module)
            )
    return tuple(steps)
