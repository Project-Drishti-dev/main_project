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

Since 18.7 the same walk answers :class:`Verification`: the three answers
beside the root it reached, the length of the path it walked and the names
of the checks that completed, so 18.7's route can say what was checked
without walking the log twice.  :func:`verify_event` is that record's
``status``, and the walk itself is written once, here.
"""

import uuid
from dataclasses import dataclass
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
    "CHECKS",
    "CHECK_PROOF",
    "CHECK_RECORD",
    "CHECK_ROOT",
    "UNKNOWN",
    "VERIFICATION_STATUSES",
    "VERIFIED",
    "Verification",
    "VerifyError",
    "verification_of",
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

#: The anchored root was read out of the entry this event's batch
#: committed to, so there is a commitment to compare against.
CHECK_ROOT = "root"

#: The stored record was hashed again out of the row's own columns and
#: compared with the digest stored beside it.
CHECK_RECORD = "record"

#: The sibling path from this event's own leaf up to that root was
#: walked.
CHECK_PROOF = "proof"

#: The steps one walk can complete, in the order it makes them, so
#: "every check ran" is a claim held against the walk itself.
CHECKS = (CHECK_ROOT, CHECK_RECORD, CHECK_PROOF)


@dataclass(frozen=True)
class Verification:
    """What one walk of the log found, in more than the three answers.

    :param status: ``VERIFIED``, ``ALTERED`` or ``UNKNOWN``.
    :param batch_id: the batch the walk reached, or ``None`` while none
        has claimed this event.
    :param batch_root: the root as the log spells it (``D57``'s verbatim
        column), or ``None`` while no root has been read.
    :param proof_length: the steps the walked proof carried, or ``None``
        while the walk has not built one.
    :param checked: the steps that completed, in walk order -- a check
        that could not run is absent rather than reported as passed.
    """

    status: str
    batch_id: uuid.UUID | None = None
    batch_root: str | None = None
    proof_length: int | None = None
    checked: tuple[str, ...] = ()


class VerifyError(ValueError):
    """Raised when an event handed over is one no row can carry.

    A :class:`ValueError`, on :class:`~app.ledger.anchoring.AnchorError`'s
    reasoning: what is unusable is what the caller passed in, and an event
    that was never written has no id to look up -- not ``unknown``, which is
    the answer about a row that exists.
    """


def verification_of(
    event: AuditEvent,
    *,
    sessions: sessionmaker[Session],
    ledger: Ledger,
) -> Verification:
    """Walk one stored event to the root its batch was anchored under.

    :param event: the event to verify.  Only its ``id`` is read -- the
        record, the hash, the salt, the position and the batch id all come
        back out of the row.
    :param sessions: the factory the rows are reloaded through, on
        ``D62``'s reasoning: a required one, never the module-level factory.
    :param ledger: the log the anchored root is read back from.
    :returns: the three answers in :class:`Verification`, beside the root,
        the length of the walked proof and the checks this walk reached.
    :raises TypeError: when ``event`` is not an
        :class:`~app.storage.models.AuditEvent`.
    :raises VerifyError: when an event handed over was never written, so no
        row carries it.
    """
    event_id = _id_of(event, "event")
    batch_id: uuid.UUID | None = None
    batch_root: str | None = None
    checked: list[str] = []

    def answer(status: str, proof_length: int | None = None) -> Verification:
        return Verification(
            status=status,
            batch_id=batch_id,
            batch_root=batch_root,
            proof_length=proof_length,
            checked=tuple(checked),
        )

    stored = _reload(sessions, event_id)
    if stored is None:
        return answer(UNKNOWN)
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
        return answer(UNKNOWN)
    entry = ledger.read_batch(batch_id)
    if entry is None:
        return answer(UNKNOWN)
    anchored = _root_of(entry)
    if anchored is None:
        return answer(UNKNOWN)
    batch_root = entry.merkle_root
    checked.append(CHECK_ROOT)
    salt = _salt_of(record_salt)
    if salt is None:
        return answer(UNKNOWN)
    recomputed = _recomputed(
        event_record(event_type, screening_id, actor, payload), salt
    )
    if recomputed is None:
        return answer(UNKNOWN)
    checked.append(CHECK_RECORD)
    if recomputed != record_hash:
        return answer(ALTERED)
    batch = _batch_of(sessions, batch_id)
    if batch is None:
        return answer(UNKNOWN)
    order, digests = batch
    if event_id not in order:
        return answer(UNKNOWN)
    position = order.index(event_id)
    proof = build_tree(digests).proof_for(position)
    checked.append(CHECK_PROOF)
    return answer(
        VERIFIED
        if verify_proof(leaf_hash(digests[position]), proof, anchored)
        else ALTERED,
        len(proof),
    )


def verify_event(
    event: AuditEvent,
    *,
    sessions: sessionmaker[Session],
    ledger: Ledger,
) -> str:
    """Verify one stored event against the root its batch was anchored under.

    :param event: the event to verify.  Only its ``id`` is read.
    :param sessions: the factory the rows are reloaded through.
    :param ledger: the log the anchored root is read back from.
    :returns: :func:`verification_of`'s ``status`` -- ``VERIFIED``,
        ``ALTERED`` or ``UNKNOWN``.
    :raises TypeError: when ``event`` is not an ``AuditEvent``.
    :raises VerifyError: when an event handed over was never written, so no
        row carries it.
    """
    return verification_of(event, sessions=sessions, ledger=ledger).status


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
