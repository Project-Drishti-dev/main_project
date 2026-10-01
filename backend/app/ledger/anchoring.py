"""Sweeping unanchored events into batches: root each, sign, append, stamp.

9.15 cut the run and 9.17 will check it; this is what sits between the two,
and it is the first caller of :func:`~app.ledger.batching.group_into_batches`,
:func:`~app.ledger.merkle.build_tree` and
:meth:`~app.ledger.store.Ledger.append_batch`.  One verb anchors everything
it is handed -- 100 events at the default size are four batches and four
entries -- and :func:`select_unanchored` is the reader that hands it a run.

**The root commits to what the database holds, not to what a caller is
carrying.**  The digests are read from ``audit_events`` rather than taken
off the passed objects, so a stale or hand-built row cannot bake a hash
into a root 9.17 could never recompute.  An event that is not stored, or
whose stored ``record_hash`` is not a digest, is refused before the log is
touched.

**An event is anchored once.**  :func:`select_unanchored` selects
``batch_id IS NULL`` and the stamp is written ``WHERE batch_id IS NULL``,
so re-anchoring a row is refused by the database rather than by a check
that could be raced past.

**The stamp carries the position as well as the batch.**  ``batch_index`` is
the order the tree was cut in, counted from zero within its own batch, so
9.17 can rebuild that tree out of the rows instead of being handed the order
by whoever anchored (``D66``).

**The entry is appended before the events are stamped.**  The stamp is a
pointer into the log, so it must never point at an entry the log does not
hold; a failure between the two leaves the events unanchored and
re-anchorable rather than stamped toward nothing.  The cost is recorded in
``D62``.

**Text columns are hex, and this module decides the spelling.**  A root is
32 raw bytes and a signature 64, and both are widened to lowercase hex on
the way in -- the spelling :func:`~app.ledger.hashing.hash_record` writes
and the one :func:`~app.ledger.signing.verify_signature` is handed on the
way back.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Dict, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.ledger.batching import group_into_batches
from app.ledger.merkle import MerkleError, build_tree, read_digest
from app.ledger.signing import Signer
from app.ledger.store import Ledger
from app.storage.models import AuditEvent, LedgerEntry

__all__ = [
    "AnchorError",
    "DEFAULT_BATCH_SIZE",
    "anchor_batch",
    "select_unanchored",
]


#: How many events one batch holds unless a caller asks otherwise.  25, and
#: a default rather than a rule: a caller anchoring one screen's events may
#: pass another number, and this task's verify is stated at this size.
DEFAULT_BATCH_SIZE = 25


class AnchorError(ValueError):
    """Raised when an event cannot be anchored as it stands.

    A ``ValueError``, on :class:`~app.ledger.signing.SigningKeyError`'s
    reasoning: what is unusable is the row itself, and it is refused before
    the log is written rather than leaving a half-anchored batch.
    """


def select_unanchored(
    sessions: sessionmaker[Session],
) -> Tuple[AuditEvent, ...]:
    """Every event no batch has claimed, oldest first.

    :param sessions: the factory every session this reader opens is bound
        to, as :class:`~app.ledger.store.SqliteLedger` is handed.
    :returns: the rows whose ``batch_id`` is ``None``, detached and
        readable once this call's session has closed, ordered by
        ``created_at`` and then by ``id``.  Nothing to sweep answers ``()``.
    """
    with sessions() as session:
        return tuple(
            session.scalars(
                select(AuditEvent)
                .where(AuditEvent.batch_id.is_(None))
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        )


def anchor_batch(
    events: Iterable[AuditEvent],
    *,
    sessions: sessionmaker[Session],
    ledger: Ledger,
    signer: Signer,
    size: int = DEFAULT_BATCH_SIZE,
    anchored_at: datetime | None = None,
) -> Tuple[LedgerEntry, ...]:
    """Anchor ``events`` -- root, sign, append, stamp -- and answer the
    entries.

    :param events: the events to anchor, in the order they should be
        committed.  Any iterable, read once and cut by 9.15's verb, so the
        order here is the order a root commits to.
    :param sessions: the factory the rows are read and stamped through, on
        :class:`~app.storage.repository.ScreeningRepository`'s reasoning --
        required, and never defaulted to the module-level factory.
    :param ledger: the log to append through.  The seam, so anchoring can be
        held against something other than a real log.
    :param signer: the key the root is signed under, already loaded by
        :func:`~app.ledger.signing.load_signing_key`.  The root is the raw
        32 bytes; the text column takes the hex.
    :param size: how many events one batch holds, passed to 9.15's verb and
        refusing on its terms before a single row is read.
    :param anchored_at: when the batches were anchored, or ``None`` for the
        row's own stamp.  Passed through to ``append_batch``, so a naive
        value is refused there.
    :returns: one entry per batch, in the batches' order, and ``()`` for
        nothing to anchor -- no empty batch exists to be rooted (``D54``).
    :raises AnchorError: when an event is not stored, is repeated in one
        batch, carries a ``record_hash`` that is not a digest, or is
        already anchored.
    :raises TypeError: when an element of ``events`` is not an event, or
        from 9.15's verb for a ``size`` that is not an ``int``.
    :raises ValueError: from 9.15's verb, for a ``size`` that is not
        positive.
    """
    return tuple(
        _anchor_one(
            batch,
            sessions=sessions,
            ledger=ledger,
            signer=signer,
            anchored_at=anchored_at,
        )
        for batch in group_into_batches(events, size)
    )


def _anchor_one(
    batch: Tuple[AuditEvent, ...],
    *,
    sessions: sessionmaker[Session],
    ledger: Ledger,
    signer: Signer,
    anchored_at: datetime | None,
) -> LedgerEntry:
    """Anchor one non-empty batch, and answer the entry that committed it."""
    event_ids = _ids_of(batch)
    root = build_tree(_digests_of(sessions, event_ids)).root
    batch_id = uuid.uuid4()
    entry = ledger.append_batch(
        batch_id=batch_id,
        merkle_root=root.hex(),
        signature=signer.sign(root).hex(),
        anchored_at=anchored_at,
    )
    _stamp(sessions, event_ids, batch_id)
    # The caller's own objects, so the rows it still holds read back as
    # anchored: 9.15 handed them over by identity for this reason.
    for position, event in enumerate(batch):
        event.batch_id = batch_id
        event.batch_index = position
    return entry


def _ids_of(batch: Tuple[AuditEvent, ...]) -> Tuple[uuid.UUID, ...]:
    """The batch's event ids, refusing a row that cannot carry one.

    :raises TypeError: when an element is not an :class:`AuditEvent`; the
        message names the type alone.
    :raises AnchorError: when an event has no id -- it was never written,
        so there is no row to read a digest from or to stamp -- or when one
        id is repeated, which would put one leaf in the tree twice and give
        9.17 two positions for the same event.
    """
    event_ids: list[uuid.UUID] = []
    for position, event in enumerate(batch):
        if not isinstance(event, AuditEvent):
            raise TypeError(
                f"element {position} is a {type(event).__name__}, and only "
                f"an AuditEvent is anchored here: no value is shown"
            )
        if event.id is None:
            raise AnchorError(
                f"element {position} has no id, and an event that was "
                f"never written has no row to anchor: no value is shown"
            )
        if event.id in event_ids:
            raise AnchorError(
                f"event {event.id} is in this batch twice, and a batch "
                f"holds one leaf per event: no value is shown"
            )
        event_ids.append(event.id)
    return tuple(event_ids)


def _digests_of(
    sessions: sessionmaker[Session], event_ids: Tuple[uuid.UUID, ...]
) -> Tuple[bytes, ...]:
    """The stored digests for ``event_ids``, in the batch's own order.

    Read in a session that closes before anything is written, so the ledger
    append is not holding a read open against the writer that follows it.

    :raises AnchorError: when a row is gone, is already anchored, or carries
        a ``record_hash`` that is not a ``DIGEST_BYTES`` digest in hex.
    """
    with sessions() as session:
        rows = session.execute(
            select(AuditEvent.id, AuditEvent.batch_id, AuditEvent.record_hash)
            .where(AuditEvent.id.in_(event_ids))
        ).all()
    stored: Dict[uuid.UUID, Tuple[uuid.UUID | None, str]] = {
        row[0]: (row[1], row[2]) for row in rows
    }
    digests: list[bytes] = []
    for event_id in event_ids:
        row = stored.get(event_id)
        if row is None:
            raise AnchorError(
                f"event {event_id} is not stored, and a root cannot commit "
                f"to an event no row carries: no value is shown"
            )
        already, record_hash = row
        if already is not None:
            raise AnchorError(
                f"event {event_id} is already anchored in batch {already}, "
                f"and an event is anchored once: no value is shown"
            )
        digests.append(_digest_of(event_id, record_hash))
    return tuple(digests)


def _digest_of(event_id: uuid.UUID, record_hash: str) -> bytes:
    """One stored ``record_hash`` unwidened to the 32 bytes a leaf is.

    :raises AnchorError: when the column holds something that is not hex
        text, or hex text that is not one digest.  9.7's reader makes the
        judgement; this names the row it was made about.
    """
    try:
        return read_digest(record_hash)
    except (MerkleError, TypeError) as error:
        raise AnchorError(
            f"event {event_id} carries a record_hash that is not hex text, "
            f"and a leaf cannot be read from it: no value is shown"
        ) from error


def _stamp(
    sessions: sessionmaker[Session],
    event_ids: Tuple[uuid.UUID, ...],
    batch_id: uuid.UUID,
) -> None:
    """Write ``batch_id`` and each row's position onto every row of the batch.

    One statement per event, because a position is that event's own value and
    not one column's.  The ``batch_id IS NULL`` condition sits in each
    statement rather than in a check above them, so the write is conditional
    in the database: a row some other writer claimed in between is not taken
    from it.

    :raises AnchorError: when fewer rows were stamped than the batch held.
    """
    with sessions() as session:
        stamped = sum(
            session.execute(
                update(AuditEvent)
                .where(
                    AuditEvent.id == event_id,
                    AuditEvent.batch_id.is_(None),
                )
                .values(batch_id=batch_id, batch_index=position)
                .execution_options(synchronize_session=False)
            ).rowcount
            for position, event_id in enumerate(event_ids)
        )
        session.commit()
    if stamped != len(event_ids):
        raise AnchorError(
            f"{len(event_ids) - stamped} of {len(event_ids)} events were "
            f"claimed by another batch before this one was stamped: "
            f"no value is shown"
        )
