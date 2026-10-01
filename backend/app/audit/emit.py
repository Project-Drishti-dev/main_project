"""The one function that writes an audit event.

Every event in the trail is made here or nowhere: the name is checked against
the vocabulary, the ruleset and model versions are attached to the payload,
the record is sealed with a salt of its own, the digest is taken before a row
exists, and the row is persisted and handed back.
Rationale in ``docs/DECISIONS.md`` D66 and D67.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.audit.event_types import EVENT_TYPES
from app.audit.record import event_record
from app.ledger.salts import seal_record
from app.storage.models import AuditEvent

__all__ = [
    "MODEL_VERSIONS_KEY",
    "PLACEHOLDER_ACTOR",
    "RULESET_VERSION_KEY",
    "VERSION_KEYS",
    "EmitError",
    "emit",
]


#: The payload key naming the ruleset the event happened under.  Spelled
#: once here, under the same two names ``Screening`` uses as columns.
RULESET_VERSION_KEY = "ruleset_version"

#: The payload key holding the module-name-to-version object, or ``None``
#: while no model has answered for the screening.
MODEL_VERSIONS_KEY = "model_versions"

#: The two keys 10.3 attaches to every payload, in the order they are
#: spelled into it.  A tuple, so "both, always" is a claim a test can hold.
VERSION_KEYS = (RULESET_VERSION_KEY, MODEL_VERSIONS_KEY)


#: The station every event is recorded under until 10.7 reads a configured
#: one from the environment.  A label, never a person, a session or a
#: credential.
PLACEHOLDER_ACTOR = "station-unset"


class EmitError(ValueError):
    """Raised when an event cannot be recorded as it stands.

    A ``ValueError``, on :class:`~app.ledger.anchoring.AnchorError`'s
    reasoning: what is unusable is what the caller passed in, and a name
    outside the vocabulary is refused before a row is written.
    """


def emit(
    event_type: str,
    screening_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    sessions: sessionmaker[Session],
    ruleset_version: str | None = None,
    model_versions: dict[str, str] | None = None,
) -> AuditEvent:
    """Hash one record, store one row, and answer the row that was stored.

    :param event_type: one of :data:`~app.audit.event_types.EVENT_TYPES`,
        which is where 10.1's vocabulary becomes load-bearing.
    :param screening_id: the screening it happened to.  No screening row is
        looked up: ``screening_id`` declares no foreign key, so an event
        outlives the row it names and this is a value the trail carries.
    :param payload: what the event carries, as an object; ``{}`` is 8.5's
        honest "nothing to add", never an absent value.  Carried by
        reference and never amended -- the two version keys are attached to
        a copy, so the caller's object comes back unchanged.
    :param sessions: the factory the row is written through, required and
        never the module-level factory (``D62``'s reasoning).
    :param ruleset_version: the ruleset the event happened under, or
        ``None``.  Never defaulted from :data:`app.version.RULESET_VERSION`,
        which would put a ruleset in the trail nothing answered under.
    :param model_versions: module name to version, or ``None`` while no
        model has answered for the screening.
    :returns: the stored row, still readable once this call's session has
        closed -- which is what ``expire_on_commit=False`` buys.
    :raises EmitError: when ``event_type`` is not one of the six names, or
        the payload already carries one of the two version keys.
    :raises TypeError: when ``screening_id`` is not a :class:`uuid.UUID`, or
        ``payload`` is not an object, or a version is not in the shape its
        column holds -- naming the type, never the value.
    :raises CanonicalJsonError: when the record has no canonical spelling,
        which is a ``float`` in a payload (``D48``).  Raised before the row
        is built, so a payload that cannot be hashed is never stored.
    """
    _event_type_of(event_type)
    _screening_of(screening_id)
    _versions_of(ruleset_version, model_versions)
    recorded = _with_versions(payload, ruleset_version, model_versions)
    sealed = seal_record(
        event_record(event_type, screening_id, PLACEHOLDER_ACTOR, recorded)
    )
    event = AuditEvent(
        screening_id=screening_id,
        event_type=event_type,
        actor=PLACEHOLDER_ACTOR,
        payload=recorded,
        record_hash=sealed.digest,
        record_salt=sealed.salt_hex,
    )
    with sessions() as session:
        session.add(event)
        session.commit()
    return event


def _event_type_of(event_type: Any) -> str:
    """``event_type`` if the vocabulary holds it, and nothing else.

    :raises EmitError: naming the value, which is a constant in the source
        that was misspelled -- never anything a screening carried.
    """
    if event_type not in EVENT_TYPES:
        raise EmitError(
            f"{event_type!r} is not one of the six names in "
            f"app.audit.event_types.EVENT_TYPES, and an audit trail is read "
            f"by those names"
        )
    return event_type


def _screening_of(screening_id: Any) -> uuid.UUID:
    """``screening_id`` if it is a UUID.

    :raises TypeError: naming the type and not the value.
    """
    if not isinstance(screening_id, uuid.UUID):
        raise TypeError(
            f"a screening_id is a {type(screening_id).__name__}, and only a "
            f"UUID may be recorded beside an event: no value is shown"
        )
    return screening_id


def _payload_of(payload: Any) -> dict[str, Any]:
    """``payload`` if it is an object, as the JSON column and 8.5 spell it.

    :raises TypeError: naming the type and not the value, so a payload
        holding identity data reaches no log.
    """
    if not isinstance(payload, dict):
        raise TypeError(
            f"a payload is a {type(payload).__name__}, and an event carries "
            f"an object: 8.5's empty one is {{}}, not an absent value: "
            f"no value is shown"
        )
    return payload


def _versions_of(ruleset_version: Any, model_versions: Any) -> None:
    """Both version values in the shapes their ``Screening`` columns hold.

    ``None`` is a shape: a ruleset nothing has scored under and a model
    nothing has asked are both honest, and both stay ``None`` rather than
    becoming a constant.

    :raises TypeError: naming the type and not the value, so nothing a
        screening carried reaches a log.
    """
    if ruleset_version is not None and not isinstance(ruleset_version, str):
        raise TypeError(
            f"a ruleset_version is a {type(ruleset_version).__name__}, and a "
            f"ruleset is named by text or by nothing at all: no value is shown"
        )
    if model_versions is not None and not isinstance(model_versions, dict):
        raise TypeError(
            f"model_versions is a {type(model_versions).__name__}, and the "
            f"column holds module name to version or nothing at all: no "
            f"value is shown"
        )


def _with_versions(
    payload: Any,
    ruleset_version: str | None,
    model_versions: dict[str, str] | None,
) -> dict[str, Any]:
    """``payload`` with both version keys attached, or refused.

    Both keys are attached whether or not a value was handed over, so a
    reader never has to tell "unknown" from "never asked about".  The result
    is a fresh object, and it is both what is hashed and what is stored
    (``D66``), so the versions land inside the record for free -- in this
    writer and in 9.17's rebuild together, with no change to the verifier.

    :raises TypeError: when ``payload`` is not an object.
    :raises EmitError: when the payload already carries one of the two keys,
        naming the key -- a constant in the source, never a value.
    """
    _payload_of(payload)
    for key in VERSION_KEYS:
        if key in payload:
            raise EmitError(
                f"the payload already carries {key!r}, and an event records "
                f"that value once: hand it over as the keyword argument "
                f"instead of writing it into the payload"
            )
    return {
        **payload,
        RULESET_VERSION_KEY: ruleset_version,
        MODEL_VERSIONS_KEY: model_versions,
    }
