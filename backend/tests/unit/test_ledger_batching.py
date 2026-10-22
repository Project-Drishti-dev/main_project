"""9.15: cutting a run of unanchored events into the batches 9.16 anchors.

The task's verify is "100 events at batch size 25 gives 4 batches in stable
order", so that is the first test here.  What the count rests on is pinned
beside it, because each of those words is a separate claim:

- **the order is the caller's.**  Nothing sorts, so a run handed over
  out of order comes back out of order -- a function that sorted would give
  four batches just as easily.
- **the partition loses nothing and repeats nothing.**  Flattening the
  batches answers the input exactly, which is the property 9.16's
  "stamp every event" rests on.
- **events are handed back by identity.**  9.16 stamps a row, and a copy
  would leave the caller's row unstamped.
- **the last batch is short, never padded.**  26 events at 25 are two
  batches, the second holding one.
- **nothing to cut is no batches, not one empty one.**  ``D54`` refuses a
  tree over no leaves, so a zero-event batch must not exist to be rooted.
- **a refused size never touches the events.**  The check is first, so a
  size that cannot work cannot consume a stream on its way to failing.
- **the size is a positive ``int``.**  A ``bool`` is an ``int`` and would
  otherwise cut batches of one (``proof_for``'s rule), and zero would be a
  step backwards.
- **no event shape is assumed.**  The function never looks inside an event,
  so it is not coupled to a column it would then have to keep in step.
"""

from typing import Any, Iterator, List

import pytest

from app.ledger.batching import group_into_batches


# --- the task's claim -------------------------------------------------------


def test_one_hundred_events_at_twenty_five_give_four_batches_in_stable_order(
) -> None:
    """The task's own claim: a batch of 25 repeated four times is what 9.16
    roots four entries for."""
    events = [f"event-{index:03d}" for index in range(100)]

    batches = group_into_batches(events, 25)

    assert len(batches) == 4
    assert [len(batch) for batch in batches] == [25, 25, 25, 25]
    # Stable order: batch n holds events 25n .. 25n+24, in that order.
    for index, batch in enumerate(batches):
        assert list(batch) == events[index * 25 : index * 25 + 25]


# --- the order is the caller's ---------------------------------------------


def test_a_run_handed_over_out_of_order_comes_back_out_of_order() -> None:
    """A grouping that sorted would still give four batches; what 9.16
    commits to is the order the events were written in."""
    events = ["c", "a", "d", "b", "e"]

    batches = group_into_batches(events, 2)

    assert [list(batch) for batch in batches] == [["c", "a"], ["d", "b"], ["e"]]


def test_flattening_the_batches_answers_the_input_exactly() -> None:
    """The partition property: nothing dropped, nothing repeated, at any
    size -- which is what "stamp every event" in 9.16 stands on."""
    events = [f"event-{index}" for index in range(26)]

    for size in (1, 2, 5, 25, 26, 27, 100):
        flattened = [
            event for batch in group_into_batches(events, size) for event in batch
        ]
        assert flattened == events, size


def test_an_event_comes_back_as_the_object_the_caller_held() -> None:
    """9.16 stamps a row, so the batch must hold that row and not a copy of
    it -- a copy would leave the caller's event unstamped and unanchored."""
    events = [object(), object(), object()]

    batches = group_into_batches(events, 2)

    assert batches[0][0] is events[0]
    assert batches[1][0] is events[2]


# --- the ends of the run ---------------------------------------------------


def test_a_short_last_batch_is_not_padded() -> None:
    """26 events at 25 are two batches and the second holds one. Padding
    would invent an event, and refusing would drop the tail."""
    events = list(range(26))

    batches = group_into_batches(events, 25)

    assert [len(batch) for batch in batches] == [25, 1]
    assert batches[-1] == (25,)


@pytest.mark.parametrize("size", [26, 100])
def test_a_size_that_covers_the_run_gives_one_batch(size: int) -> None:
    """A size at or above the run length is one batch, not one plus an
    empty remainder -- the "every batch is non-empty" claim."""
    events = list(range(26))

    batches = group_into_batches(events, size)

    assert len(batches) == 1
    assert list(batches[0]) == events


@pytest.mark.parametrize("empty", [[], (), iter(())])
def test_nothing_to_cut_answers_no_batch_at_all(empty: Any) -> None:
    """``D54`` refuses a tree over no leaves, so a zero-event batch must
    never reach 9.16 to be rooted."""
    assert group_into_batches(empty, 25) == ()


def test_an_iterator_is_cut_and_consumed_once() -> None:
    """The caller may hand a stream rather than a list -- 9.16 reads events
    from the database -- and it is walked exactly once, not per batch."""
    events = [f"event-{index}" for index in range(10)]

    batches = group_into_batches(iter(events), 4)

    assert [list(batch) for batch in batches] == [
        events[0:4],
        events[4:8],
        events[8:10],
    ]


# --- the size is checked before anything is read ----------------------------


def test_a_refused_size_never_touches_the_events() -> None:
    """A size that cannot work must fail before a stream is consumed: a
    caller that catches the refusal and retries would otherwise find its
    events already drained."""
    consumed = False

    def events() -> Iterator[str]:
        nonlocal consumed
        consumed = True
        yield "event-0"

    with pytest.raises(ValueError):
        group_into_batches(events(), 0)

    assert consumed is False


@pytest.mark.parametrize("size", [0, -1, -25])
def test_a_size_that_is_not_positive_is_refused(size: int) -> None:
    """A batch of nothing, or a step backwards over the run."""
    with pytest.raises(ValueError):
        group_into_batches(["event-0"], size)


@pytest.mark.parametrize("size", [True, False, 25.0, "25", None])
def test_a_size_that_is_not_an_int_is_refused(size: Any) -> None:
    """``proof_for``'s rule: ``True`` is an ``int`` and would quietly cut
    batches of one, and ``25.0`` compares equal to a real size without
    being one."""
    with pytest.raises(TypeError):
        group_into_batches(["event-0"], size)


def test_the_refusal_is_raised_before_the_iterable_is_read() -> None:
    """The type fault and the value fault are both decided before any event
    is pulled, so neither refusal depends on what the caller handed over."""
    for bad in (True, "25", 0, -1):
        pulled: List[str] = []

        def events() -> Iterator[str]:
            for name in ("a", "b"):
                pulled.append(name)
                yield name

        with pytest.raises((TypeError, ValueError)):
            group_into_batches(events(), bad)
        assert pulled == [], bad


# --- the shape of the answer ------------------------------------------------


def test_the_batches_are_tuples_and_cannot_be_edited_after_the_fact() -> None:
    """What 9.16 roots is what this answered, so an answer a caller could
    append to between the cut and the tree would not be the batch it cut."""
    batches = group_into_batches(["a", "b", "c"], 2)

    assert isinstance(batches, tuple)
    assert all(isinstance(batch, tuple) for batch in batches)
    # Editing the answer in place would not be the batch that was cut, and
    # a tuple cannot be edited in place at all.
    with pytest.raises(AttributeError):
        batches.append(("c",))


def test_no_event_shape_is_assumed() -> None:
    """The function groups what it is handed and never looks inside it, so
    it is not coupled to a column 9.16 will stamp."""
    events = [None, 0, "", object()]

    batches = group_into_batches(events, 3)

    assert [len(batch) for batch in batches] == [3, 1]
