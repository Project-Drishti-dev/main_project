"""Cutting a run of unanchored events into the batches 9.16 will anchor.

One function, one job: consecutive events in, consecutive batches out, in
the order the caller handed them over.  Nothing here sorts, stamps, queries
or builds a tree -- 9.16 owns what a batch becomes.
"""

from typing import Iterable, Tuple, TypeVar

__all__ = ["group_into_batches"]


#: Whatever an event is to the caller -- in this ledger an
#: :class:`~app.storage.models.AuditEvent` row, but the function never looks
#: inside one, so it stays generic.
EventT = TypeVar("EventT")


def group_into_batches(
    unanchored_events: Iterable[EventT], size: int
) -> Tuple[Tuple[EventT, ...], ...]:
    """The events cut into consecutive batches of at most ``size``.

    :param unanchored_events: the events to cut, in the order they should be
        anchored.  Any iterable, consumed once; each event is handed back by
        identity, never copied, so 9.16 stamps the row the caller holds.
    :param size: how many events one batch holds at most.  A positive
        ``int``.
    :returns: a tuple of tuples in the order given, every one of them
        non-empty.  Nothing to cut answers ``()`` rather than one empty
        batch, because :func:`app.ledger.merkle.build_tree` refuses a tree
        over no leaves (``D54``).
    :raises TypeError: when ``size`` is not an ``int`` -- a ``bool``
        included, as :meth:`~app.ledger.merkle.MerkleTree.proof_for` draws
        the line for an index.
    :raises ValueError: when ``size`` is not positive, which would be a batch
        of nothing or a step backwards.
    """
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError(
            f"size is a {type(size).__name__}, and a batch size is an int: "
            f"no value is shown"
        )
    if size < 1:
        raise ValueError(
            f"size is {size}, and a batch holds at least one event: "
            f"no value is shown"
        )
    events = tuple(unanchored_events)
    return tuple(
        events[start : start + size] for start in range(0, len(events), size)
    )
