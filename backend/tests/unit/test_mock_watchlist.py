"""5.11 -- the mock connector, and the three questions the seed is asked.

`tasks.md` names the three: a number in the seed hits, an unknown number
misses, and a name with a date of birth hits.  Each is asked of
:class:`app.seed.mock_watchlist.MockWatchlist` and each names the entry the
seed lists, so a row renamed in the JSON fails here rather than answering with
no entry at all.

**Which name shape the mock looks up is this task's to pin**, because 5.10's row
carries both the printed MRZ form and the tidied one.  The mock matches either,
so a caller holding one spelling is answered the same as a caller holding the
other, and the tests say so rather than leaving a mock that happens to work on
one of them.

**The values are read from the seed, not copied into this file.**  A hand-typed
``X00000001`` beside a JSON row that no longer says so would leave the tests
green against a seed nothing matches.

**The read count is taken at the resource, not at ``_entries``.**  What 5.12
asks is that the file is opened once rather than once per document, so what is
counted is the read of the seed itself; counting this module's own function
would say that whatever the read was replaced with is still called once.
"""

import datetime
import json

import pytest

from app.risk import watchlist
from app.seed import mock_watchlist

MockWatchlist = mock_watchlist.MockWatchlist
WatchlistHit = watchlist.WatchlistHit
WatchlistValueError = watchlist.WatchlistValueError

#: The package and resource the seed lives in, read through the mock's own
#: constants so the test and the connector cannot disagree about them.
SEED_TEXT = (
    mock_watchlist.importlib.resources.files(mock_watchlist.SEED_PACKAGE)
    .joinpath(mock_watchlist.SEED_RESOURCE)
    .read_text(encoding="utf-8")
)
SEED = json.loads(SEED_TEXT)

#: The document-number rows, as ``(document number, entry id, kind)``.  Both
#: document-number kinds are in the seed, and the blacklist one is the seed's
#: only blacklisted number.
NUMBER_ROWS = tuple(
    (row["document_number"], row["entry_id"], row["kind"])
    for row in SEED["entries"]
    if row["matched_on"] == watchlist.DOCUMENT_NUMBER
)

#: The identity row, read rather than written out.
IDENTITY_ROW = next(
    row for row in SEED["entries"] if row["matched_on"] == watchlist.IDENTITY
)
IDENTITY_NAME = IDENTITY_ROW["name"]
IDENTITY_NAME_TIDIED = IDENTITY_ROW["name_tidied"]
IDENTITY_DOB = datetime.date.fromisoformat(IDENTITY_ROW["dob"])

#: A document number the seed does not carry, and a day it does not name.
A_NUMBER_NOT_ON_THE_LIST = "X9999999"
A_DAY_NOT_ON_THE_LIST = datetime.date(1990, 1, 2)


def ask(**arguments):
    """Ask a fresh mock the question, with the three arguments defaulting to None."""
    values = {
        "document_number": None,
        "name": None,
        "dob": None,
    }
    values.update(arguments)
    return MockWatchlist().lookup(**values)


def _count_seed_reads(monkeypatch):
    """Record the name of every resource read through the seed's own door.

    The read is counted where the file is opened rather than at ``_entries``,
    so the number is a fact about the seed and not about this module's own
    bookkeeping.
    """
    reads = []
    real_files = mock_watchlist.importlib.resources.files

    class _Counting:
        """A traversable that appends to ``reads`` for each text it hands over."""

        def __init__(self, wrapped, name=None):
            self._wrapped = wrapped
            self._name = name

        def joinpath(self, name):
            return _Counting(self._wrapped.joinpath(name), name)

        def read_text(self, encoding=None):
            reads.append(self._name)
            return self._wrapped.read_text(encoding=encoding)

    monkeypatch.setattr(
        mock_watchlist.importlib.resources,
        "files",
        lambda package: _Counting(real_files(package)),
    )
    return reads


def test_the_mock_is_a_watchlist():
    """A stand-in that is not the interface is a stand-in nothing can hold."""
    assert issubclass(MockWatchlist, watchlist.Watchlist)


def test_the_seed_holds_the_three_kinds_of_entry_the_seam_names():
    """Otherwise a kind the mock answers is a kind no test ever asks for."""
    assert {row["kind"] for row in SEED["entries"]} == set(watchlist.HIT_KINDS)


# --- the three questions tasks.md names ------------------------------------


@pytest.mark.parametrize(("document_number", "entry_id", "kind"), NUMBER_ROWS)
def test_a_number_in_the_seed_hits(document_number, entry_id, kind):
    hits = ask(document_number=document_number)
    assert hits == [WatchlistHit(kind, entry_id, watchlist.DOCUMENT_NUMBER)]


def test_an_unknown_number_misses():
    assert ask(document_number=A_NUMBER_NOT_ON_THE_LIST) == []


@pytest.mark.parametrize("name", [IDENTITY_NAME, IDENTITY_NAME_TIDIED])
def test_a_name_and_a_dob_in_the_seed_hit(name):
    hits = ask(name=name, dob=IDENTITY_DOB)
    assert hits == [
        WatchlistHit(
            watchlist.IDENTITY_SEEN,
            IDENTITY_ROW["entry_id"],
            watchlist.IDENTITY,
        )
    ]


# --- the name shape the mock looks up is either one ------------------------


def test_both_name_shapes_the_seed_carries_are_the_same_lookup():
    """The row carries a printed name and a tidied one, and the mock answers
    alike for each.  A mock matching only the printed form would tell a caller
    holding the tidied one that nothing was found."""
    assert IDENTITY_NAME != IDENTITY_NAME_TIDIED
    printed = ask(name=IDENTITY_NAME, dob=IDENTITY_DOB)
    tidied = ask(name=IDENTITY_NAME_TIDIED, dob=IDENTITY_DOB)
    assert printed == tidied


def test_a_name_in_the_seed_with_another_dob_misses():
    """An identity entry is a name *and* a day: either alone is a different
    person, and a lookup of one key alone is not a question about the identity."""
    assert ask(name=IDENTITY_NAME, dob=A_DAY_NOT_ON_THE_LIST) == []


# --- a key that was not read matches nothing -------------------------------


def test_three_none_values_find_nothing():
    """Nothing was asked, so nothing was found -- which is not a document
    cleared."""
    assert ask() == []


def test_a_name_without_a_day_finds_nothing():
    assert ask(name=IDENTITY_NAME) == []


def test_a_day_without_a_name_finds_nothing():
    assert ask(dob=IDENTITY_DOB) == []


def test_a_hit_from_the_seed_carries_no_matched_value():
    """`D13`'s limit held on the mock rather than left to the record: the
    numbers and names the seed matched against are in nothing a caller gets
    back."""
    hits = ask(
        document_number=NUMBER_ROWS[0][0],
        name=IDENTITY_NAME,
        dob=IDENTITY_DOB,
    )
    carried = {value for hit in hits for value in vars(hit).values()}
    for matched in (NUMBER_ROWS[0][0], IDENTITY_NAME, IDENTITY_NAME_TIDIED):
        assert matched not in carried


# --- what a row the seed cannot be read from does -------------------------


def test_a_row_the_mock_cannot_read_is_refused_and_not_passed_over(monkeypatch):
    """A row this connector cannot speak about is an entry the list is unable
    to answer for, and answering "nothing matched" would read as a cleared
    document."""
    monkeypatch.setattr(
        mock_watchlist,
        "_entries",
        lambda: ({"kind": watchlist.BLACKLIST, "entry_id": "WL-0001"},),
    )
    with pytest.raises(WatchlistValueError):
        ask(document_number=A_NUMBER_NOT_ON_THE_LIST)


def test_a_refusal_names_the_key_and_never_repeats_the_value(monkeypatch):
    """The seed's values are a person's name, and a value quoted back is a
    value in a traceback."""
    monkeypatch.setattr(
        mock_watchlist,
        "_entries",
        lambda: (
            {
                "kind": watchlist.IDENTITY_SEEN,
                "entry_id": "IDENTITY-0001",
                "matched_on": watchlist.IDENTITY,
                "name": IDENTITY_NAME,
                "name_tidied": IDENTITY_NAME_TIDIED,
                "dob": "not-a-date",
            },
        ),
    )
    with pytest.raises(WatchlistValueError) as excinfo:
        ask(name=IDENTITY_NAME, dob=IDENTITY_DOB)
    assert "dob" in str(excinfo.value)
    assert IDENTITY_NAME not in str(excinfo.value)


# --- what the mock must not do --------------------------------------------


def test_the_seed_is_read_once_when_the_connector_is_built_and_never_again(
    monkeypatch,
):
    """The file does not change while a run is going, so a screening that
    reopened it per document paid a read for an answer it already had."""
    reads = _count_seed_reads(monkeypatch)
    connector = MockWatchlist()
    assert reads == [mock_watchlist.SEED_RESOURCE]
    for _ in range(3):
        assert connector.lookup(
            document_number=NUMBER_ROWS[0][0],
            name=IDENTITY_NAME,
            dob=IDENTITY_DOB,
        )
    assert reads == [mock_watchlist.SEED_RESOURCE]


def test_the_rows_belong_to_the_connector_and_not_to_the_module(monkeypatch):
    """A cache held at module level would answer every connector in the
    process from the first one's read, and a row edited in the seed would be a
    row no later connector could find."""
    reads = _count_seed_reads(monkeypatch)
    MockWatchlist()
    MockWatchlist()
    assert reads == [mock_watchlist.SEED_RESOURCE] * 2


def test_the_mock_reads_the_seed_it_names_and_not_a_path_of_its_own():
    """A path assembled out of ``__file__`` breaks when the package is
    installed as a zip or a wheel, and the mock would answer from nothing."""
    assert mock_watchlist.SEED_PACKAGE == "app.seed"
    assert mock_watchlist.SEED_RESOURCE == "watchlist.json"


def test_every_name_in_all_exists_in_the_module():
    for name in mock_watchlist.__all__:
        assert hasattr(mock_watchlist, name), name
