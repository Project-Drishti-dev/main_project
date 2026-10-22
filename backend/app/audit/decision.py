"""The officer's own choice beside the band it was shown, and the difference.

10.6's one claim: an officer who contradicts the band leaves an event of
their own, carrying both sides.  **The choice is written down, never
derived** -- the abstract's three choices are named here and no band names
any of them (7.10), so a disagreement is a comparison between two things
that exist apart from each other.
Since 18.3 the choice itself is an event too, written here rather than at the
route that received it.  Since 18.4 a second choice is answered rather than
overwriting the first: it is a new event naming the one it took over from, and
where a choice stands is read off the trail rather than kept beside it.
Rationale in ``docs/DECISIONS.md`` D70, D145 and D146.

**Invariants**

- :data:`OFFICER_ACTIONS` is the abstract's three choices, and this module is
  the only place the adverse one is spelled in the service.
- :func:`~override_required` asks :func:`contradicts_band` in the adverse
  direction only, so neither other choice is ever held to a flag and a row
  carrying no band is asked nothing.
- :data:`BAND_ORDER` and :data:`OFFICER_ACTIONS` are two independent
  orderings; nothing here pairs a band with an action.
- An override is a new event: nothing in this module writes to the screening
  row or to the event the automated result left.
- ``record_officer_decision`` writes the choice before the override and
  refuses a choice it cannot read before either, so the trail never carries
  half of a decision.
- :data:`SUPERSEDES_KEY` is written only where a choice was already recorded,
  and only into the *new* event: a first choice's payload is 18.3's three
  keys and nothing else, and no event here is ever amended.
- Where a choice stands is :func:`recorded_decisions`'s reading of the trail's
  order and is stored nowhere -- :data:`DECISION_STATUSES` is the only
  vocabulary of it in the service.
- Every event goes through :func:`~app.audit.emit.emit` with ``sessions=``
  passed explicitly, so no module-level factory is reachable from here.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.audit.emit import emit
from app.audit.event_types import DECISION_RECORDED, OVERRIDE_RECORDED
from app.risk.flags import WEIGHT_BANDS
from app.storage.models import AuditEvent

__all__ = [
    "ADVERSE_RANK",
    "ALLOW_ENTRY",
    "BAND_ORDER",
    "DECISION_CURRENT",
    "DECISION_STATUSES",
    "DECISION_SUPERSEDED",
    "FURTHER_INSPECTION",
    "OFFICER_ACTIONS",
    "OFFICER_ACTION_KEY",
    "OVERRIDE_KEY",
    "REJECT_ENTRY",
    "REMARK_KEY",
    "SUPERSEDES_KEY",
    "SYSTEM_BAND_KEY",
    "DecisionError",
    "DecisionState",
    "contradicts_band",
    "current_decision",
    "override_required",
    "record_officer_decision",
    "record_override",
    "recorded_decisions",
]

#: The three choices the abstract gives the officer, in its own order.  Plain
#: text, like every other vocabulary in this service, and never an enum.
ALLOW_ENTRY = "allow"
FURTHER_INSPECTION = "further_inspection"
REJECT_ENTRY = "reject"

#: The three, closed and in the order the abstract writes them, so "the
#: officer's three choices" is a claim a test can hold against a count.
OFFICER_ACTIONS = (ALLOW_ENTRY, FURTHER_INSPECTION, REJECT_ENTRY)

#: Where the adverse choice sits on :data:`OFFICER_ACTIONS`, read off the
#: tuple rather than counted, so the rule below is asked about the same
#: vocabulary it is written in.
ADVERSE_RANK = OFFICER_ACTIONS.index(REJECT_ENTRY)

#: The bands in the order the 0-100 scale puts them in, read off
#: :data:`app.risk.config.LOW_MAX` and :data:`~app.risk.config.REVIEW_MAX`
#: rather than out of the engine at runtime.  **No band names an outcome**: the
#: ordering is a position on a scale, and 7.10's walk over this module holds
#: that the two vocabularies are never written in one place.
BAND_ORDER = ("low", "review", "high")

#: The payload key the system's own band is written under, so a reader is
#: told which side of the disagreement this value came from.
SYSTEM_BAND_KEY = "system_band"

#: The payload key the officer's own choice is written under.
OFFICER_ACTION_KEY = "officer_action"

#: The payload key the officer's own sentence is written under, kept exactly
#: as it was written: the reason is theirs and no service rewrites one.
REMARK_KEY = "remark"

#: The payload key the officer's own claim is written under -- what the
#: caller sent, which is never what the band beside it implies.
OVERRIDE_KEY = "override"

#: The payload key naming the choice this one was taken over from, holding
#: that choice's event id as a string (``D48`` has no UUID branch).  **Written
#: only where a choice was already recorded**, and written into the *new*
#: event: an event is sealed when it is written (8.5), so the second choice
#: cannot be an edit of the first and the link is the only way one can name
#: the other.
SUPERSEDES_KEY = "supersedes"

#: Where a choice stands when nothing has been taken over from it -- the one
#: a reader acts on, and the state the endpoint's own answer reports.
DECISION_CURRENT = "current"

#: Where a choice stands once a later one has taken over from it.  **Derived
#: from the trail and written nowhere**: the first choice's own bytes cannot
#: change, so what a second choice changes is what the trail says about it.
DECISION_SUPERSEDED = "superseded"

#: The two standings a recorded choice can read, closed and in the order a
#: reader meets them: the last choice is current, every earlier one is
#: superseded.  A tuple, so "no duplicates" is a claim a test can hold.
DECISION_STATUSES = (DECISION_CURRENT, DECISION_SUPERSEDED)


class DecisionError(ValueError):
    """Raised when a band or a choice is not a name this project reads.

    A ``ValueError``, on :class:`~app.audit.emit.EmitError`'s reasoning: what
    is unusable is what the caller passed in, and it is refused before an
    event is written.
    """


@dataclass(frozen=True)
class DecisionState:
    """One recorded choice as the trail reads it, and where it stands.

    :param decision_id: the ``decision_recorded`` event's own id -- the record
        itself rather than a copy of it.
    :param officer_action: the choice that event carries, as it was written.
    :param remark: the officer's own sentence, as it was written.
    :param override: the officer's own claim, at the value they sent.
    :param status: :data:`DECISION_CURRENT` or :data:`DECISION_SUPERSEDED`.
    :param supersedes: the choice this one was taken over from, as the id
        string the payload carries (``D48`` has no UUID branch), or ``None``
        where this was the first.
    :param created_at: when the event was written, in UTC.
    """

    decision_id: uuid.UUID
    officer_action: str
    remark: str
    override: bool
    status: str
    supersedes: str | None
    created_at: datetime


def recorded_decisions(
    screening_id: uuid.UUID, *, sessions: sessionmaker[Session]
) -> tuple[DecisionState, ...]:
    """Every choice recorded on one screening, in the order they were taken.

    :param screening_id: the screening whose trail is being read.  A
        :class:`uuid.UUID`, not coerced from a string.
    :param sessions: the factory the rows are read through, required and
        never the module-level one (``D62``'s reasoning).
    :returns: one :class:`DecisionState` per ``decision_recorded`` event, in
        ``created_at`` then ``id`` order -- the same total order
        :mod:`app.storage.repository` reads rows in, because two choices can
        share an instant and a partial order would leave one on no page at
        all.  **The last is :data:`DECISION_CURRENT` and every earlier one
        :data:`DECISION_SUPERSEDED`**, which is the whole of 18.4: where a
        choice stands is read off the trail rather than stored beside it (8.4
        refuses a seventeenth column), so a second choice changes what the
        trail says about the first without touching a byte of the first.
    """
    with sessions() as session:
        events = tuple(
            session.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.screening_id == screening_id,
                    AuditEvent.event_type == DECISION_RECORDED,
                )
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
            .scalars()
            .all()
        )
    last = len(events) - 1
    return tuple(
        _state_of(event, DECISION_CURRENT if at == last else DECISION_SUPERSEDED)
        for at, event in enumerate(events)
    )


def current_decision(
    screening_id: uuid.UUID, *, sessions: sessionmaker[Session]
) -> DecisionState | None:
    """The one recorded choice that nothing has been taken over from.

    :param screening_id: the screening whose trail is being read.
    :param sessions: the factory the rows are read through, required and
        never the module-level one.
    :returns: the last of :func:`recorded_decisions` -- what a reader acts on
        -- or ``None`` where no choice has been recorded, which is an answer
        rather than a fault (``ScreeningRepository.get``'s reasoning).
    """
    recorded = recorded_decisions(screening_id, sessions=sessions)
    return recorded[-1] if recorded else None


def contradicts_band(system_band: Any, officer_action: Any) -> bool:
    """Whether the officer's choice disagrees with the band shown alongside it.

    :param system_band: the band 7.9 answered, or ``None``.
    :param officer_action: the officer's own choice, or ``None``.
    :returns: ``True`` when the two sit at different points on their own
        orderings.  The three pairs that agree are ``low`` with
        :data:`ALLOW_ENTRY`, ``review`` with :data:`FURTHER_INSPECTION` and
        ``high`` with :data:`REJECT_ENTRY`; every other pairing is recorded,
        in either direction, because an officer who released a document the
        system was more worried about is owed the same record as one who
        stopped a document the system was less worried about.
    :raises DecisionError: when either name is outside its vocabulary.
    """
    return _band_rank(system_band) != _action_rank(officer_action)


def override_required(system_band: Any, officer_action: Any) -> bool:
    """Whether the officer has to claim the choice as going against the band.

    :param system_band: the band the officer was shown, or ``None`` on a row
        nothing has scored -- and then none was shown to go against.
    :param officer_action: the officer's own choice.
    :returns: ``True`` for :data:`REJECT_ENTRY` on any band below it, so a
        ``low`` and a ``review`` row both need the flag, and ``False`` for the
        ``high`` row that choice agrees with, for either other choice, and for
        a row carrying no band.  Where the choice is the adverse one this is
        :func:`contradicts_band` asked in one direction.
    :raises DecisionError: when the choice is outside the officer three, or
        the band is not one of :data:`BAND_ORDER`.
    """
    rank = _action_rank(officer_action)
    if rank != ADVERSE_RANK or system_band is None:
        return False
    return contradicts_band(system_band, officer_action)


def record_officer_decision(
    screening_id: uuid.UUID,
    *,
    system_band: str | None,
    officer_action: str,
    remark: str,
    override: bool,
    sessions: sessionmaker[Session],
    ruleset_version: str | None = None,
    model_versions: dict[str, str] | None = None,
) -> tuple[AuditEvent, AuditEvent | None]:
    """Write the choice an officer made, and the override beside it.

    :param screening_id: the screening the choice was made on.  Looked up
        never, on ``record_override``'s reasoning: the id is a value the
        trail carries, and an event outlives the row it names.
    :param system_band: the band the officer was shown, or ``None`` on a row
        nothing has scored -- and then no band was shown to go against, so
        there is no override to record.
    :param officer_action: the officer's own choice.
    :param remark: the officer's own sentence, kept as it was written.
    :param override: the officer's own claim -- what the caller sent, which
        is never what the band beside it implies.
    :param sessions: the factory both events are written through, required
        and never the module-level one (``D62``'s reasoning).
    :param ruleset_version: the ruleset the choice was made under, or
        ``None``.
    :param model_versions: module name to version, or ``None``.
    :returns: the ``decision_recorded`` event, and the ``override_recorded``
        event beside it -- ``None`` where the choice agreed with the band, or
        where there was no band to agree or disagree with.  **Where a choice
        was already recorded, the returned event carries
        :data:`SUPERSEDES_KEY`** -- the id of the choice it was taken over
        from, so a second choice is a link beside the first rather than a
        rewrite of it (18.4, D146).
    :raises DecisionError: when the choice is outside the officer three.  It
        is read before either event is written, so a refused choice leaves no
        half-decision behind.
    """
    _action_rank(officer_action)
    payload: dict[str, Any] = {
        OFFICER_ACTION_KEY: officer_action,
        REMARK_KEY: remark,
        OVERRIDE_KEY: override,
    }
    superseded = current_decision(screening_id, sessions=sessions)
    if superseded is not None:
        payload[SUPERSEDES_KEY] = str(superseded.decision_id)
    recorded = emit(
        DECISION_RECORDED,
        screening_id,
        payload,
        sessions=sessions,
        ruleset_version=ruleset_version,
        model_versions=model_versions,
    )
    if system_band is None:
        return recorded, None
    return recorded, record_override(
        screening_id,
        system_band=system_band,
        officer_action=officer_action,
        sessions=sessions,
        ruleset_version=ruleset_version,
        model_versions=model_versions,
    )


def record_override(
    screening_id: uuid.UUID,
    *,
    system_band: str,
    officer_action: str,
    sessions: sessionmaker[Session],
    ruleset_version: str | None = None,
    model_versions: dict[str, str] | None = None,
) -> AuditEvent | None:
    """Record that an officer contradicted the band, as an event of its own.

    :param screening_id: the screening the choice was made on.  Looked up
        never: the id is a value the trail carries, and an event outlives the
        row it names.
    :param system_band: the band the officer was shown, handed over by the
        caller rather than read off a row, so a band is never recomputed here.
    :param officer_action: the officer's own choice.
    :param sessions: the factory the event is written through, required and
        never the module-level one (``D62``'s reasoning).
    :param ruleset_version: the ruleset the band was scored under, or
        ``None``.  Handed to :func:`~app.audit.emit.emit`, which attaches it
        to the payload as the other key beside it.
    :param model_versions: module name to version, or ``None``.
    :returns: the stored event, or ``None`` when the choice agreed with the
        band -- an agreeing choice is not a refusal and there is nothing to
        record, which is the answer rather than an exception.
    :raises DecisionError: when either name is outside its vocabulary, before
        anything is written.
    :raises CanonicalJsonError: from ``emit``, if a version is not a shape
        the record can be spelled in (``D48``).
    """
    if not contradicts_band(system_band, officer_action):
        return None
    return emit(
        OVERRIDE_RECORDED,
        screening_id,
        {
            SYSTEM_BAND_KEY: system_band,
            OFFICER_ACTION_KEY: officer_action,
        },
        sessions=sessions,
        ruleset_version=ruleset_version,
        model_versions=model_versions,
    )


def _state_of(event: AuditEvent, status: str) -> DecisionState:
    """One ``decision_recorded`` row read as a choice standing at ``status``.

    :param event: the stored event, read back over a session this module was
        handed.
    :param status: where the choice stands, which the row does not carry and
        :func:`recorded_decisions` decides from the order the trail holds.
    :returns: the choice as the event recorded it, beside the standing that
        order gives it.  A key the row does not carry reads as the empty
        value rather than raising: 8.5 holds ``{}`` to be a payload an event
        may carry, so a decision written without one of these keys is still a
        row this can describe.
    """
    payload = event.payload
    return DecisionState(
        decision_id=event.id,
        officer_action=payload.get(OFFICER_ACTION_KEY, ""),
        remark=payload.get(REMARK_KEY, ""),
        override=bool(payload.get(OVERRIDE_KEY, False)),
        status=status,
        supersedes=payload.get(SUPERSEDES_KEY),
        created_at=event.created_at,
    )


def _band_rank(system_band: Any) -> int:
    """``system_band``'s position in :data:`BAND_ORDER`.

    :raises DecisionError: naming the value, which is a spelling in the
        source, a request body or a stored row rather than identity data.
    """
    if not isinstance(system_band, str) or system_band not in BAND_ORDER:
        raise DecisionError(
            f"{system_band!r} is not a band this project reads: 7.9 bands a "
            f"score with one of {', '.join(sorted(WEIGHT_BANDS))}"
        )
    return BAND_ORDER.index(system_band)


def _action_rank(officer_action: Any) -> int:
    """``officer_action``'s position in :data:`OFFICER_ACTIONS`.

    :raises DecisionError: naming the value and not restating the three, so
        the choices are spelled once in this module and nowhere else.
    """
    if not isinstance(officer_action, str) or officer_action not in OFFICER_ACTIONS:
        raise DecisionError(
            f"{officer_action!r} is not a choice an officer makes: the "
            f"abstract's three are named by OFFICER_ACTIONS"
        )
    return OFFICER_ACTIONS.index(officer_action)
