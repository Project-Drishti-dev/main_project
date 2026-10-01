"""The one record an event is hashed over, spelled once and shared.

10.2's writer seals it and 9.17's verifier rebuilds it out of a stored row.
The two must agree exactly, because a record spelled two ways would make
``verified`` a claim about a value nobody hashed.  Rationale in
``docs/DECISIONS.md`` D66.
"""

import uuid
from typing import Any

__all__ = ["event_record"]


def event_record(
    event_type: str,
    screening_id: uuid.UUID,
    actor: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """The four columns that say what an event is, as one hashable record.

    ``screening_id`` is spelled as its ``str()``: ``D48`` has no UUID branch,
    so a raw UUID has no canonical JSON and the row could not be verified at
    all.  ``created_at`` and ``batch_id`` are left out on purpose -- the
    first is stamped after the digest is taken and reads back naive on
    SQLite, the second is ``None`` until 9.16 sweeps the row in.

    :param event_type: one of :data:`~app.audit.event_types.EVENT_TYPES`.
    :param screening_id: the screening the event happened to.
    :param actor: the station label the row carries.
    :param payload: what the event carries, carried by reference and not
        copied, so the writer seals exactly what it was handed.
    :returns: a fresh object over the four values, ready for
        :func:`~app.ledger.hashing.hash_record`.
    """
    return {
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
        "screening_id": str(screening_id),
    }
