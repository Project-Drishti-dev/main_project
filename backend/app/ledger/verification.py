"""Whether one stored event is still the record the log committed to.

9.17 reloads the row, recomputes its digest over the stored record and walks
a proof from that digest to the root 9.16 anchored, answering ``verified``,
``altered`` or ``unknown`` -- one string, three states.

Nothing but the event, the session factory and the log is asked for.  The
salt and the position within the batch are read out of the row, on ``D62``'s
reasoning: the row is what gets verified, so a fact about it a caller could
hand over is a fact this would have to take on trust.

The recomputation spells the record with
:func:`~app.audit.record.event_record` -- the writer's own spelling, so two
shapes cannot make ``verified`` a claim about a value nobody hashed
(``D66``).
"""

import uuid
from typing import Any, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.audit.record import event_record
from app.ledger.canonical import CanonicalJsonError
from app.ledger.hashing import hash_record
from app.ledger.merkle import (
    MerkleError,
    build_tree,
    leaf_hash,
    read_digest,
    verify_proof,
)
from app.ledger.salts import SALT_BYTES
from app.ledger.store import Ledger
from app.storage.models import AuditEvent, LedgerEntry

__all__ = [
    "ALTERED",
    "UNKNOWN",
    "VERIFICATION_STATUSES",
    "VERIFIED",
    "VerifyError",
    "verify_event",
]


#: The row still hashes and still carries the digest the anchored root
#: committed to.
VERIFIED = "verified"

#: Everything needed to ask was there, and the two halves disagree.
ALTERED = "altered"

#: One of the halves is not there to compare: no row, no batch, no entry, no
#: root a proof could be walked to, or no leaf position for this event.
UNKNOWN = "unknown"

#: The three answers, in the order a reader meets them.
VERIFICATION_STATUSES = (VERIFIED, ALTERED, UNKNOWN)


class VerifyError(ValueError):
    """Raised when an event handed over is one no row can carry.

    A :class:`ValueError`, on :class:`~app.ledger.anchoring.AnchorError`'s
    reasoning: what is unusable is what the caller passed in, and an event
    that was never written has no id to look up -- not ``unknown``, which is
    the answer about a row that exists.
    """


def verify_event(
    event: AuditEvent,
    *,
    sessions: sessionmaker[Session],
    ledger: Ledger,
) -> str:
    """Verify one stored event against the root its batch was anchored under.

    :param event: the event to verify.  Only its ``id`` is read -- the
        record, the hash, the salt, the position and the batch id all come
        back out of the row.
    :param sessions: the factory the rows are reloaded through, on
        ``D62``'s reasoning: a required one, never the module-level factory.
    :param ledger: the log the anchored root is read back from.
    :returns: ``VERIFIED``, ``ALTERED`` or ``UNKNOWN``.
    :raises TypeError: when ``event`` is not an
        :class:`~app.storage.models.AuditEvent`.
    :raises VerifyError: when an event handed over was never written, so no
        row carries it.
    """
    event_id = _id_of(event, "event")
    stored = _reload(sessions, event_id)
    if stored is None:
        return UNKNOWN
    (
        batch_id,
        record_hash,
        record_salt,
        event_type,
        screening_id,
        actor,
        payload,
    ) = stored
    if batch_id is None:
        return UNKNOWN
    entry = ledger.read_batch(batch_id)
    if entry is None:
        return UNKNOWN
    root = _root_of(entry)
    if root is None:
        return UNKNOWN
    salt = _salt_of(record_salt)
    if salt is None:
        return UNKNOWN
    recomputed = _recomputed(
        event_record(event_type, screening_id, actor, payload), salt
    )
    if recomputed is None:
        return UNKNOWN
    if recomputed != record_hash:
        return ALTERED
    batch = _batch_of(sessions, batch_id)
    if batch is None:
        return UNKNOWN
    order, digests = batch
    if event_id not in order:
        return UNKNOWN
    position = order.index(event_id)
    proof = build_tree(digests).proof_for(position)
    return (
        VERIFIED
        if verify_proof(leaf_hash(digests[position]), proof, root)
        else ALTERED
    )


def _id_of(event: Any, what: str) -> uuid.UUID:
    """``event``'s id, refusing a value that is not a row at all.

    :param event: the value handed over.
    :param what: how to name it in a message, without its value.
    :returns: the event's id.
    :raises TypeError: when it is not an :class:`AuditEvent`.
    :raises VerifyError: when it carries no id, so no row can hold it.
    """
    if not isinstance(event, AuditEvent):
        raise TypeError(
            f"{what} is a {type(event).__name__}, and only an AuditEvent is "
            f"verified here: no value is shown"
        )
    if event.id is None:
        raise VerifyError(
            f"a {what} with no id was never written, so no row carries it: "
            f"no value is shown"
        )
    return event.id


def _reload(
    sessions: sessionmaker[Session], event_id: uuid.UUID
) -> Tuple[uuid.UUID | None, str, Any, str, uuid.UUID, str, Any] | None:
    """The row's seven columns this compares, or ``None`` if no row carries it.

    Read in a session that closes before anything else is touched, so the
    answer is the database's and never the caller's identity map.
    """
    with sessions() as session:
        row = session.execute(
            select(
                AuditEvent.batch_id,
                AuditEvent.record_hash,
                AuditEvent.record_salt,
                AuditEvent.event_type,
                AuditEvent.screening_id,
                AuditEvent.actor,
                AuditEvent.payload,
            ).where(AuditEvent.id == event_id)
        ).one_or_none()
    return None if row is None else tuple(row)


def _salt_of(record_salt: Any) -> bytes | None:
    """The row's stored salt as bytes, or ``None`` if it is not one.

    10.2 writes :attr:`~app.ledger.salts.SaltedRecord.salt_hex`, and only
    that width is accepted: a salt this module cannot unwiden is a digest it
    cannot recompute, which is ``unknown`` rather than an answer.
    """
    if not isinstance(record_salt, str):
        return None
    try:
        salt = bytes.fromhex(record_salt)
    except ValueError:
        return None
    return salt if len(salt) == SALT_BYTES else None


def _root_of(entry: LedgerEntry) -> bytes | None:
    """The entry's anchored root as raw bytes, or ``None`` if it is not one.

    A log entry is written verbatim (``D57``), so this is where a root of
    another width -- or of prose -- is refused, and refusing it means there
    is no commitment to compare against rather than a record that moved.
    """
    try:
        return read_digest(entry.merkle_root)
    except (MerkleError, TypeError):
        return None


def _recomputed(record: Any, salt: bytes) -> str | None:
    """The digest the stored record hashes to, or ``None`` if it cannot be.

    A record 9.2's serialiser refuses -- a ``float``, which ``D48`` bars --
    has no digest to compare, and a row that cannot be spelled is a question
    this cannot answer rather than one that came out wrong.  10.2's writer
    refuses the same record before it stores it, so this is the answer for a
    row written by something else.
    """
    try:
        return hash_record(record, salt)
    except CanonicalJsonError:
        return None


def _batch_of(
    sessions: sessionmaker[Session], batch_id: uuid.UUID
) -> Tuple[Tuple[uuid.UUID, ...], Tuple[bytes, ...]] | None:
    """The batch's ids and stored hashes in the order it was anchored.

    ``batch_index`` is that order, counted from zero within the batch, and
    9.16 writes it beside the batch id.  ``None`` when the order cannot be
    read: a row carrying no position, two rows claiming one, a position the
    batch does not reach contiguously, a row gone, or a hash that is not a
    digest.  The tree cannot be rebuilt without every leaf in its place, so
    this answers ``unknown`` -- never a clearance.
    """
    with sessions() as session:
        rows = session.execute(
            select(
                AuditEvent.id, AuditEvent.record_hash, AuditEvent.batch_index
            )
            .where(AuditEvent.batch_id == batch_id)
            .order_by(AuditEvent.batch_index, AuditEvent.id)
        ).all()
    if [row[2] for row in rows] != list(range(len(rows))):
        return None
    order: list[uuid.UUID] = []
    digests: list[bytes] = []
    for row in rows:
        try:
            digests.append(read_digest(row[1]))
        except (MerkleError, TypeError):
            return None
        order.append(row[0])
    return tuple(order), tuple(digests)
