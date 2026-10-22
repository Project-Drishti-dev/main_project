"""The append-only log: one interface, and the SQLite implementation of it.

:class:`Ledger` is what 9.16 appends through and what 9.17 reads back;
:class:`SqliteLedger` is the only implementation, and it is named for the
backend 9.12's triggers are written against rather than for the only URL it
will ever see -- the statements it issues are the ones the migrated
PostgreSQL schema takes as well, which nothing here measures.

**Neither the interface nor the implementation owns a session.**  Both are
handed a ``sessionmaker[Session]``, on
:class:`~app.storage.repository.ScreeningRepository`'s reasoning (``D42``):
the module-level factory is bound to the process's start-up configuration,
so a ledger that reached for it could not be pointed at a migrated file in a
test.  Nothing here builds an engine, declares a table or reads a clock --
:mod:`app.storage.models` owns the row, including the mapper events that
refuse an amendment, and 9.12 owns the database's half of the same refusal.

**A batch is appended once.**  :meth:`Ledger.append_batch` writes one
entry and refuses a ``batch_id`` the log already carries, because two
entries for one batch would leave :meth:`Ledger.read_batch` with two
answers to one question.  That refusal is this module's own rule: nothing
in the migration makes ``batch_id`` unique, so it is the application
speaking rather than the schema.

**The entry carries a root, a signature and two stamps, and nothing else.**
The four values ``append_batch`` takes are the whole vocabulary the log has,
which is as much of the abstract's "only hashes reach the ledger" as this
module can express; there is no argument here through which a payload, a
filename or a person could be written.

**A stored spelling is 9.16's decision, not this module's.**  The root and
the signature are written and answered back verbatim: :mod:`app.ledger.
merkle` holds a root as 32 raw bytes while the column is text, and how that
digest and a signature are spelled when they travel is 9.16's business, so
nothing here re-encodes a value or refuses one for its shape.
"""

import abc
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import LedgerEntry

__all__ = ["DuplicateBatchError", "Ledger", "SqliteLedger"]


#: How many rows :meth:`SqliteLedger.iter_batches` fetches at a time, so a
#: walk of a long chain does not buffer all of it before answering the first
#: entry.
_STREAM_CHUNK = 100


class DuplicateBatchError(RuntimeError):
    """Raised when a batch already in the log is appended a second time.

    A :class:`RuntimeError`, like
    :class:`~app.storage.models.LedgerAppendOnlyError` beside it: both are
    the service's own rule rather than a constraint the migration carries,
    and 9.12's triggers refuse the other two operations from the database's
    side.
    """


def _as_utc(name: str, moment: datetime) -> datetime:
    """Return ``moment`` as a UTC instant, refusing a naive stamp.

    :param name: the argument's name, for the message.
    :param moment: the instant the caller handed over.
    :returns: ``moment`` converted to UTC, so a stamp carrying an offset
        reaches the database as the instant it names.
    :raises ValueError: when ``moment`` carries no timezone, so nothing is
        queried and nothing is written.
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(
            f"{name} must carry a timezone, got naive {moment.isoformat()}"
        )
    return moment.astimezone(timezone.utc)


class Ledger(abc.ABC):
    """The three things the audit layer asks of a log.

    The interface rather than a concrete class, so 9.16's caller holds a
    :class:`Ledger` and the implementation is the one thing a test can
    swap; nothing in Part 9 needs a second implementation, and the deferred
    Fabric work is the reason the seam exists rather than a caller.
    """

    @abc.abstractmethod
    def append_batch(
        self,
        *,
        batch_id: uuid.UUID,
        merkle_root: str,
        signature: str,
        anchored_at: datetime | None = None,
    ) -> LedgerEntry:
        """Append one entry committing ``batch_id``, and answer the row.

        :param batch_id: the :class:`uuid.UUID` 9.16 stamps on each event
            in the batch.  Not coerced from a string.
        :param merkle_root: the batch's root, spelled as text.
        :param signature: the signature over that root, spelled as text.
        :param anchored_at: when the batch was anchored, keyword-only and
            optional.  ``None`` leaves the row's ORM default to stamp it; a
            given stamp must carry a timezone and is converted to UTC.
        :returns: the committed entry, carrying the position the database
            gave it, detached and readable.
        :raises DuplicateBatchError: when the log already carries this
            batch.  :raises ValueError: on a naive ``anchored_at``.
        """

    @abc.abstractmethod
    def read_batch(self, batch_id: uuid.UUID) -> LedgerEntry | None:
        """Return the entry committing ``batch_id``, or ``None`` if none does.

        :param batch_id: the :class:`uuid.UUID` the column holds.  Not
            coerced from a string.
        :returns: the stored entry, detached and readable, or ``None`` when
            no row carries that batch id -- an answer rather than a fault,
            on :meth:`ScreeningRepository.get`'s reasoning.
        """

    @abc.abstractmethod
    def iter_batches(self) -> Iterator[LedgerEntry]:
        """Walk every entry the log holds, in ``sequence`` order.

        :returns: an iterator over the entries, the order being the chain's
            own rather than the order anything was written in.
        """


class SqliteLedger(Ledger):
    """A :class:`Ledger` over the sessions the caller owns.

    :param sessions: the factory every session this ledger opens is bound
        to, as returned by :func:`app.storage.db.build_session_factory`.
        Required, and not defaulted to the module-level
        :data:`app.storage.db.SessionLocal`: see the module docstring.
    """

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def append_batch(
        self,
        *,
        batch_id: uuid.UUID,
        merkle_root: str,
        signature: str,
        anchored_at: datetime | None = None,
    ) -> LedgerEntry:
        """Append one entry committing ``batch_id``, and answer the row.

        :param batch_id: the batch this entry commits.  The same
            :class:`uuid.UUID` 9.16 stamps on each of its events.
        :param merkle_root: the batch's root, stored as it was handed over:
            see the module docstring.
        :param signature: the signature over that root, stored as handed.
        :param anchored_at: when the batch was anchored, or ``None`` for
            the row's ORM default.  Keyword-only, must carry a timezone and
            is converted to UTC.
        :returns: the committed entry, carrying the ``sequence`` the
            database assigned -- no argument writes one.
        :raises DuplicateBatchError: when the log already carries this
            batch, with nothing written.
        :raises ValueError: when ``anchored_at`` carries no timezone.
            Nothing is queried, so the log is neither read nor written.
        """
        stamp = (
            None if anchored_at is None else _as_utc("anchored_at", anchored_at)
        )
        row = LedgerEntry(
            batch_id=batch_id,
            merkle_root=merkle_root,
            signature=signature,
        )
        if stamp is not None:
            row.anchored_at = stamp
        with self._sessions() as session:
            already_there = session.execute(
                select(LedgerEntry.sequence).where(
                    LedgerEntry.batch_id == batch_id
                )
            ).first()
            if already_there is not None:
                raise DuplicateBatchError(
                    f"batch {batch_id} is already in the ledger at position "
                    f"{already_there[0]}: a batch is appended once and is "
                    f"never amended"
                )
            session.add(row)
            session.commit()
        return row

    def read_batch(self, batch_id: uuid.UUID) -> LedgerEntry | None:
        """Return the entry committing ``batch_id``, or ``None`` if none does.

        :param batch_id: the :class:`uuid.UUID` the column holds.  Not
            coerced from a string.
        :returns: the stored entry, detached and readable once this call's
            session has closed, or ``None`` when no row carries that batch.
        :raises sqlalchemy.exc.MultipleResultsFound: if the log ever held
            two entries for one batch, which :meth:`append_batch` refuses
            and nothing else in the schema prevents.
        """
        with self._sessions() as session:
            return session.execute(
                select(LedgerEntry).where(LedgerEntry.batch_id == batch_id)
            ).scalar_one_or_none()

    def iter_batches(self) -> Iterator[LedgerEntry]:
        """Walk every entry the log holds, in ``sequence`` order.

        :returns: an iterator over the entries.  The session it reads
            through stays open for as long as the caller keeps walking, so a
            caller that abandons the iterator part-way should close it.
        """
        with self._sessions() as session:
            yield from session.scalars(
                select(LedgerEntry)
                .order_by(LedgerEntry.sequence)
                .execution_options(yield_per=_STREAM_CHUNK)
            )
