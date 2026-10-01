"""The officer's own choice beside the band it was shown, and the difference.

10.6's one claim: an officer who contradicts the band leaves an event of
their own, carrying both sides.  **The choice is written down, never
derived** -- the abstract's three choices are named here and no band names
any of them (7.10), so a disagreement is a comparison between two things
that exist apart from each other.
Rationale in ``docs/DECISIONS.md`` D70.

**Invariants**

- :data:`OFFICER_ACTIONS` is the abstract's three choices, and this module is
  the only place the adverse one is spelled in the service.
- :data:`BAND_ORDER` and :data:`OFFICER_ACTIONS` are two independent
  orderings; nothing here pairs a band with an action.
- An override is a new event: nothing in this module writes to the screening
  row or to the event the automated result left.
- Every event goes through :func:`~app.audit.emit.emit` with ``sessions=``
  passed explicitly, so no module-level factory is reachable from here.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.audit.emit import emit
from app.audit.event_types import OVERRIDE_RECORDED
from app.risk.flags import WEIGHT_BANDS
from app.storage.models import AuditEvent

__all__ = [
    "ALLOW_ENTRY",
    "BAND_ORDER",
    "FURTHER_INSPECTION",
    "OFFICER_ACTIONS",
    "OFFICER_ACTION_KEY",
    "REJECT_ENTRY",
    "SYSTEM_BAND_KEY",
    "DecisionError",
    "contradicts_band",
    "record_override",
]

#: The three choices the abstract gives the officer, in its own order.  Plain
#: text, like every other vocabulary in this service, and never an enum.
ALLOW_ENTRY = "allow"
FURTHER_INSPECTION = "further_inspection"
REJECT_ENTRY = "reject"

#: The three, closed and in the order the abstract writes them, so "the
#: officer's three choices" is a claim a test can hold against a count.
OFFICER_ACTIONS = (ALLOW_ENTRY, FURTHER_INSPECTION, REJECT_ENTRY)

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


class DecisionError(ValueError):
    """Raised when a band or a choice is not a name this project reads.

    A ``ValueError``, on :class:`~app.audit.emit.EmitError`'s reasoning: what
    is unusable is what the caller passed in, and it is refused before an
    event is written.
    """


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
