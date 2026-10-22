"""19.7: how long a stored document is kept, and the one function that acts.

:func:`purge_expired_evidence` walks one store, deletes the blobs whose age is
past the window :func:`app.config.get_retention_days` answers for
:data:`~app.config.RECORD_CLASS_EVIDENCE`, and reports the digests it removed
in a :class:`PurgeResult`.

**A blob is aged by the file that holds it, because nothing else records the
instant.**  The store keeps no index (D157) and the column on the row holds an
address rather than a time, so the window is measured against the last write
of the file -- the one set when
:meth:`~app.storage.blob_store.EvidenceStore.put` moved the finished body
into place.  The consequence is recorded rather than hidden: copying a store
restamps every blob in it.

**Only a file named like a blob is touched.**  A half-written `.partial`, a
backup, or anything else beside the blobs in the root is not in
:meth:`~app.storage.blob_store.EvidenceStore.blob_paths`, so no expiry window
can reach it.

**The window is a boundary and not a moment.**  A blob written exactly
`retention_days` ago is kept and one written a second earlier is deleted; a
window of zero days is refused rather than read as delete everything now, on
:func:`app.config.get_rate_limit_per_minute` reasoning that a value only safe
when it is refused is refused.

**A purge answers digests, never a document.**  :class:`PurgeResult` carries
what is no longer on disk and how much was left, so a caller can report what
went without holding a path or a byte of what it went from.

**A sweep run twice names what it removed once.**  A digest is reported only
for a file that run removed, so a second sweep over one store answers nothing
deleted, and one document is named once however many sweeps walk the store.

**One sweep is one line in the log** (:data:`PURGE_LOG_EVENT`), carrying the
window enforced and every digest it removed, so the log itself says what went
and no caller has to keep it.  The message is the event name and the digests
travel as fields, so no digest is formatted into the text of a line.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import RECORD_CLASS_EVIDENCE, get_retention_days
from app.logging_config import log_event
from app.storage.blob_store import BLOB_SUFFIX, EvidenceStore

__all__ = ["PURGE_LOG_EVENT", "PurgeResult", "purge_expired_evidence"]

logger = logging.getLogger(__name__)

#: The event one sweep logs under.  A name rather than a sentence, on
#: :func:`app.logging_config.log_event` reasoning that nothing a sweep
#: removed reaches a line by being formatted into one.
PURGE_LOG_EVENT = "evidence_purge"


@dataclass(frozen=True, slots=True)
class PurgeResult:
    """What one purge removed, and how much it left.

    :param deleted: the digests of the blobs that are no longer on disk, in
        the order the store named them.  A digest and nothing else: no path,
        and no byte of any document.
    :param kept: how many blobs were still inside the window.
    :invariant: a sweep run twice over one store reports nothing deleted the
        second time, because a digest is reported only for a file that run
        removed.
    """

    deleted: tuple[str, ...]
    kept: int

    def __post_init__(self) -> None:
        """Refuse an answer that is not the shape a purge answers.

        :returns: nothing.
        :raises TypeError: naming the type of the field and no value.
        """
        if not isinstance(self.deleted, tuple) or not all(
            isinstance(digest, str) for digest in self.deleted
        ):
            raise TypeError(
                f"what a purge deleted is a {type(self.deleted).__name__}, and "
                f"only a tuple of digests may be reported: no value is shown"
            )
        if not isinstance(self.kept, int) or isinstance(self.kept, bool):
            raise TypeError(
                f"what a purge kept is a {type(self.kept).__name__}, and only a "
                f"whole number of blobs may be counted: no value is shown"
            )


def purge_expired_evidence(
    store: Any,
    *,
    retention_days: int | None = None,
    now: datetime | None = None,
) -> PurgeResult:
    """The blobs past their window, deleted, and the rest counted.

    :param store: the store to sweep, handed one rather than read from the
        environment on :mod:`app.config` reasoning that a key is not read
        where it is used.
    :param retention_days: the window to enforce.  `None` answers
        :func:`app.config.get_retention_days` for
        :data:`~app.config.RECORD_CLASS_EVIDENCE`, the only record class a
        purge removes; a whole number of days may be passed instead, which is
        how a case holds the window still.
    :param now: the instant the window is measured from.  The UTC clock when
        `None`, so a case that must be exact about the boundary passes the
        instant rather than sleeping for it.
    :returns: a :class:`PurgeResult` naming the digests removed and counting
        the blobs kept, beside one :data:`PURGE_LOG_EVENT` line logged for
        the sweep itself.
    :raises TypeError: naming the type of `store`, of a window that is not a
        whole number of days, and of an instant that is not a datetime, with
        no value.
    :raises ValueError: when the window is below one day, or when the instant
        carries no timezone -- one that cannot be compared with the UTC stamp
        of a file is not an instant to measure from.
    """
    checked_store = _checked_store(store)
    window = _checked_days(
        retention_days
        if retention_days is not None
        else get_retention_days()[RECORD_CLASS_EVIDENCE]
    )
    cutoff = _checked_moment(now) - timedelta(days=window)
    deleted: list[str] = []
    kept = 0
    for path in checked_store.blob_paths():
        # A file another sweep removed between the listing and here is
        # skipped rather than reported: the sweep that removed it already
        # named the digest, and this one has removed nothing.
        if not path.is_file():
            continue
        written_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if written_at < cutoff:
            path.unlink(missing_ok=True)
            deleted.append(path.name.removesuffix(BLOB_SUFFIX))
        else:
            kept += 1
    log_event(
        logger,
        PURGE_LOG_EVENT,
        retention_days=window,
        deleted=tuple(deleted),
        deleted_count=len(deleted),
        kept=kept,
    )
    return PurgeResult(deleted=tuple(deleted), kept=kept)


def _checked_store(value: Any) -> EvidenceStore:
    """`value` read as the store to sweep, or refused by type.

    :param value: what a caller handed to :func:`purge_expired_evidence`.
    :returns: the store, unchanged.
    :raises TypeError: naming the type and no value, so a directory cannot be
        swept by mistake.
    """
    if not isinstance(value, EvidenceStore):
        raise TypeError(
            f"the store to purge is a {type(value).__name__}, and only an "
            f"EvidenceStore holds blobs to expire: no value is shown"
        )
    return value


def _checked_days(value: Any) -> int:
    """`value` read as a window in whole days, or refused.

    :param value: a window, or what :func:`app.config.get_retention_days`
        answered for the evidence class.
    :returns: the window.
    :raises TypeError: naming the type and no value.  `bool` is refused with
        the rest, because it is an `int` and `True` is not one day.
    :raises ValueError: when the window is below one day, which expires a
        document the moment it is stored rather than after a window.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"a retention window is a {type(value).__name__}, and only a whole "
            f"number of days may expire a document: no value is shown"
        )
    if value < 1:
        raise ValueError(
            f"a retention window is {value} days, which expires a document "
            f"the moment it is stored rather than after a window"
        )
    return value


def _checked_moment(value: Any) -> datetime:
    """`value` read as the instant a window is measured from.

    :param value: `None`, or the instant a caller passed.
    :returns: that instant, or the UTC clock when none was passed.
    :raises TypeError: naming the type and no value.
    :raises ValueError: when the instant carries no timezone, so the
        comparison with the UTC stamp of a file would be arithmetic the
        reader has to invent.
    """
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, datetime):
        raise TypeError(
            f"the instant a window is measured from is a "
            f"{type(value).__name__}, and only a datetime may be one: no "
            f"value is shown"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "the instant a window is measured from carries no timezone, and "
            "an instant nobody can compare with the UTC stamp of a file is "
            "not one to measure from"
        )
    return value
