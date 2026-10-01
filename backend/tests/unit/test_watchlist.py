"""5.9 -- the ``Watchlist`` interface, and what a hit is allowed to carry.

The task's own claim is that **a stub satisfies the interface**, so the first
group below is that claim and everything else holds the seam the stub has to
be built against: the one abstract method, its three keyword-only arguments
with no defaults, and a record with no field a matched value could be written
into.

**The signature is read from the source rather than called**, because a method
that happens to work when called proves less than a signature: an argument
with a default, or a fourth argument carrying a reference date, would leave
every behavioural test in this file passing.

**The ``WATCHLIST_`` ids are read from** :mod:`app.risk.flag_ids`
**rather than written out here**, so the three kinds and the three ids are held
to each other by construction and a fourth kind added to one list fails the
other.
"""

import dataclasses
import datetime
import inspect

import pytest

from app.risk import flag_ids, watchlist

#: The short names, bound once so the tables below read as data rather than as
#: attribute paths, and so a name renamed in the module fails here rather than
#: quietly inside a string.
BLACKLIST = watchlist.BLACKLIST
STOLEN_DOCUMENT = watchlist.STOLEN_DOCUMENT
IDENTITY_SEEN = watchlist.IDENTITY_SEEN
DOCUMENT_NUMBER = watchlist.DOCUMENT_NUMBER
IDENTITY = watchlist.IDENTITY
Watchlist = watchlist.Watchlist
WatchlistHit = watchlist.WatchlistHit
WatchlistValueError = watchlist.WatchlistValueError

#: An entry id in the shape 5.10's seed will use: opaque, and not a value
#: anybody prints on a document.
AN_ENTRY = "WL-0001"
#: A second one, so a test that puts two entries in one list does not have to
#: invent the second by hand.
ANOTHER_ENTRY = "WL-0002"

#: A well-formed hit of each kind, with the ``matched_on`` that kind is found
#: by.  Every rejected case below is one of these with a single field replaced.
THE_WELL_FORMED_HITS = (
    (BLACKLIST, AN_ENTRY, DOCUMENT_NUMBER),
    (STOLEN_DOCUMENT, ANOTHER_ENTRY, DOCUMENT_NUMBER),
    (IDENTITY_SEEN, AN_ENTRY, IDENTITY),
)

#: The three arguments, in the order ``tasks.md`` 5.9 names them, each with a
#: value of its own type.  ``dob`` is a resolved day because that is what 5.6
#: hands on, not the six printed characters.
A_DOCUMENT_NUMBER = "X1234567"
A_NAME = "DOE<<JANE"
A_DOB = datetime.date(1988, 4, 12)


class StubWatchlist(Watchlist):
    """A connector that answers from a list it was handed, and nothing else."""

    def __init__(self, answers=()):
        self._answers = list(answers)
        self.calls = []

    def lookup(self, *, document_number, name, dob):
        self.calls.append((document_number, name, dob))
        return list(self._answers)


class AStubThatForgetsLookup(Watchlist):
    """A connector that never implemented the one method it must."""


# --- the task's own claim: a stub satisfies the interface ---


def test_a_stub_subclasses_the_interface():
    assert issubclass(StubWatchlist, Watchlist)


def test_a_stub_can_be_instantiated_and_asked():
    stub = StubWatchlist()
    assert stub.lookup(document_number=None, name=None, dob=None) == []


def test_the_interface_itself_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Watchlist()


def test_a_stub_that_forgets_lookup_cannot_be_instantiated():
    """The abstract method is what makes the interface checkable."""
    with pytest.raises(TypeError):
        AStubThatForgetsLookup()


def test_lookup_is_the_only_method_the_interface_requires():
    assert Watchlist.__abstractmethods__ == frozenset({"lookup"})


def test_a_stub_is_asked_the_three_arguments_and_gets_them_back():
    stub = StubWatchlist()
    stub.lookup(document_number=A_DOCUMENT_NUMBER, name=A_NAME, dob=A_DOB)
    assert stub.calls == [(A_DOCUMENT_NUMBER, A_NAME, A_DOB)]


# --- the signature, read from the source rather than from a call ---


def _lookup_signature():
    return inspect.signature(Watchlist.lookup)


def test_lookup_takes_exactly_the_three_arguments_the_task_names():
    assert tuple(_lookup_signature().parameters) == (
        "self",
        "document_number",
        "name",
        "dob",
    )


def test_the_three_arguments_are_keyword_only():
    """Two of them are strings, so a positional call could pair them wrongly
    and be answered with a clean miss rather than a failure."""
    kinds = {p.kind for p in _lookup_signature().parameters.values()}
    assert inspect.Parameter.KEYWORD_ONLY in kinds


def test_no_argument_has_a_default():
    """An omitted key is a question nobody asked, so every one is required."""
    defaults = [
        p.default
        for p in _lookup_signature().parameters.values()
        if p.default is not inspect.Parameter.empty
    ]
    assert defaults == []


def test_no_argument_is_a_reference_date():
    """A connector that filtered on "still listed today" would make a
    screening's outcome depend on when it ran."""
    assert "reference" not in _lookup_signature().parameters


def test_the_dob_argument_is_a_resolved_day():
    """Six printed characters carry no century, and resolving them here
    would give every connector a reference date of its own."""
    dob = _lookup_signature().parameters["dob"].annotation
    assert dob == datetime.date | None


def test_lookup_answers_a_list_of_hits():
    assert _lookup_signature().return_annotation == list[WatchlistHit]


def test_a_stub_returning_nothing_still_answers_a_list():
    assert StubWatchlist().lookup(
        document_number=A_DOCUMENT_NUMBER, name=None, dob=None
    ) == []


# --- the record: what a hit may carry ---


def test_a_hit_carries_three_fields_and_no_slot_for_a_matched_value():
    """This is the module's whole claim, so the field set is pinned: a fourth
    field is a place a document number or a name could be kept."""
    names = tuple(f.name for f in dataclasses.fields(WatchlistHit))
    assert names == ("kind", "entry_id", "matched_on")


@pytest.mark.parametrize(("kind", "entry_id", "matched_on"), THE_WELL_FORMED_HITS)
def test_each_of_the_three_kinds_is_accepted_with_its_own_key(kind, entry_id, matched_on):
    hit = WatchlistHit(kind, entry_id, matched_on)
    assert (hit.kind, hit.entry_id, hit.matched_on) == (kind, entry_id, matched_on)


def test_a_hit_is_frozen():
    hit = WatchlistHit(BLACKLIST, AN_ENTRY, DOCUMENT_NUMBER)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hit.kind = STOLEN_DOCUMENT


def test_a_hit_carries_no_public_method():
    """A method here would be a second answer about what matched."""
    public = [
        name
        for name in dir(WatchlistHit)
        if not name.startswith("_") and callable(getattr(WatchlistHit, name))
    ]
    assert public == []


def test_a_hit_is_not_an_exception():
    assert not issubclass(WatchlistHit, BaseException)


#: Each kind and the id 6.4 will give it, written out longhand so the pairing is
#: read rather than computed from a naming rule that happens to hold today.
THE_KIND_AND_ITS_ID = (
    (BLACKLIST, flag_ids.WATCHLIST_HIT),
    (STOLEN_DOCUMENT, flag_ids.WATCHLIST_STOLEN_DOCUMENT),
    (IDENTITY_SEEN, flag_ids.WATCHLIST_IDENTITY_SEEN),
)


def test_the_three_kinds_are_the_three_watchlist_ids_one_for_one():
    """The record's vocabulary and the flag ids cannot drift apart."""
    kinds = {kind for kind, _ in THE_KIND_AND_ITS_ID}
    assert kinds == set(watchlist.HIT_KINDS)
    ids = {flag_id for _, flag_id in THE_KIND_AND_ITS_ID}
    assert ids == {i for i in flag_ids.FLAG_IDS if i.startswith("WATCHLIST_")}


def test_the_error_is_a_value_error_so_existing_handlers_keep_working():
    assert issubclass(WatchlistValueError, ValueError)


def test_every_name_in_all_exists_in_the_module():
    """A typo in ``__all__`` breaks a star-import and nothing else, so it is
    read here rather than found later."""
    for name in watchlist.__all__:
        assert hasattr(watchlist, name), name


def test_the_two_vocabularies_are_frozen():
    """6.4 reads both, and a set a caller could add to would let a list answer
    with a kind nothing downstream has a weight for."""
    assert isinstance(watchlist.HIT_KINDS, frozenset)
    assert isinstance(watchlist.MATCHED_ON, frozenset)
    assert len(watchlist.HIT_KINDS) == 3
    assert len(watchlist.MATCHED_ON) == 2


# --- the record: what it refuses ---


@pytest.mark.parametrize("kind", ["", "BLACKLIST", "stolen", "unknown", None, 7, ["blacklist"]])
def test_a_kind_outside_the_three_is_refused(kind):
    with pytest.raises(WatchlistValueError):
        WatchlistHit(kind, AN_ENTRY, DOCUMENT_NUMBER)


@pytest.mark.parametrize(
    "matched_on", ["", "DOCUMENT_NUMBER", "name", "dob", None, 7, {"document_number"}]
)
def test_a_key_outside_the_two_is_refused(matched_on):
    with pytest.raises(WatchlistValueError):
        WatchlistHit(BLACKLIST, AN_ENTRY, matched_on)


@pytest.mark.parametrize(
    "entry_id",
    [
        "",
        " ",
        "DOE<<JANE",
        "MALHOTRA, ANJALI",
        "WL 0001",
        "WL-0001;drop",
        None,
        7,
    ],
)
def test_an_entry_id_that_is_not_a_token_is_refused(entry_id):
    with pytest.raises(WatchlistValueError):
        WatchlistHit(BLACKLIST, entry_id, DOCUMENT_NUMBER)


@pytest.mark.parametrize(
    "entry_id", ["WL-0001", "wl-0001", "ENTRY_2", "abc123", "0001", "a"]
)
def test_an_entry_id_written_as_a_token_is_accepted(entry_id):
    assert WatchlistHit(BLACKLIST, entry_id, DOCUMENT_NUMBER).entry_id == entry_id


@pytest.mark.parametrize("entry_id", ["1988-04-12", "MALHOTRA", "JANE"])
def test_the_entry_id_guard_is_a_guard_and_not_a_guarantee(entry_id):
    """A date and a single-token name are written in the characters an entry
    id allows, so the charset check passes them.  What keeps identity data
    out is that the record has three fields and none of them holds the value
    that matched -- a limit worth asserting rather than hoping away."""
    assert WatchlistHit(BLACKLIST, entry_id, DOCUMENT_NUMBER).entry_id == entry_id


@pytest.mark.parametrize(
    ("kind", "matched_on"),
    [
        (BLACKLIST, IDENTITY),
        (STOLEN_DOCUMENT, IDENTITY),
        (IDENTITY_SEEN, DOCUMENT_NUMBER),
    ],
)
def test_a_kind_matched_on_the_wrong_key_is_refused(kind, matched_on):
    """A blacklist entry is found by its number and an identity-seen entry by
    its name and date of birth, so a hit that disagrees with itself is
    refused rather than passed to 6.4."""
    with pytest.raises(WatchlistValueError):
        WatchlistHit(kind, AN_ENTRY, matched_on)


def test_a_refusal_names_the_field_and_never_repeats_the_value():
    """A name is the value most likely to arrive here, and a value quoted
    back is a value in a traceback and a log."""
    try:
        WatchlistHit("MALHOTRA ANJALI", AN_ENTRY, DOCUMENT_NUMBER)
    except WatchlistValueError as error:
        assert "kind" in str(error)
        assert "MALHOTRA" not in str(error)
    else:  # pragma: no cover - the call above must raise
        pytest.fail("a bad kind was accepted")
