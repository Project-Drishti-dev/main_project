"""The connector that answers from the seed file beside this module.

There is no stolen-document or blacklist service to ask yet, so
:class:`MockWatchlist` stands in for one: it holds no list of its own and reads
the rows of ``watchlist.json`` once, when it is built.  It lives here rather
than in :mod:`app.risk` because the seed is the whole of it -- when a live
connector arrives, this module and its JSON go and
:mod:`app.risk.watchlist` stays.

**A mock is a lookup table and not a matcher.**  A row is compared with the
values it carries, exactly as printed: no case folding, no filler stripping and
no tidying, because a rule this project has not written down is a rule no live
connector could be expected to share.  An identity row carries the holder's
name in two shapes -- the printed MRZ form and the tidied one -- and **either
hits**, so a caller holding one spelling and a caller holding the other are
answered alike rather than one of them being told the document is clear.

**A ``None`` argument is a key that was not read, so it cannot match.**  An
identity row needs a name *and* a date of birth, and asking about the name alone
is not a question about the identity.  The three arguments are keyword-only and
required, as :meth:`app.risk.watchlist.Watchlist.lookup` declares them.

**Nothing read out of the seed reaches the answer.**  Every row is turned into
a :class:`app.risk.watchlist.WatchlistHit`, which carries the entry's kind, id
and key and has no field a document number, a name or a date of birth could be
written into; a row that cannot be read that way is refused rather than passed
over, because a row passed over is an entry this list is unable to speak about
and an unanswered question reads as a cleared document.

**Nothing here reads the clock.**  ``dob`` arrives resolved, and the row's own
text is read as the day it names.
"""

import datetime
import importlib.resources
import json
from collections.abc import Mapping
from typing import Any

from app.risk.watchlist import (
    DOCUMENT_NUMBER,
    Watchlist,
    WatchlistHit,
    WatchlistValueError,
)

__all__ = ["NAME_KEYS", "SEED_PACKAGE", "SEED_RESOURCE", "MockWatchlist"]

#: The package the seed file is read through, so a path is never assembled out
#: of ``__file__`` and the read survives the file being packaged.
SEED_PACKAGE = "app.seed"
#: The one resource this connector answers from.
SEED_RESOURCE = "watchlist.json"
#: The keys an identity row carries its name under.  Both are tried, so the
#: spelling a caller holds is not a reason to answer "no entry matched".
NAME_KEYS = ("name", "name_tidied")


def _entries() -> tuple[Mapping[str, Any], ...]:
    """The rows of the seed file, read from the package resource."""
    text = (
        importlib.resources.files(SEED_PACKAGE)
        .joinpath(SEED_RESOURCE)
        .read_text(encoding="utf-8")
    )
    return tuple(json.loads(text)["entries"])


def _field(row: Mapping[str, Any], key: str) -> str:
    """Return the text ``row`` carries under ``key``.

    Refused rather than defaulted, and the message names the key and not the
    value for :class:`app.risk.watchlist.WatchlistValueError`'s reason: a value
    quoted back is a value in a traceback, and a seed row's value is the name of
    a person.
    """
    value = row.get(key)
    if not isinstance(value, str):
        raise WatchlistValueError(f"a seed row's {key} is missing or is not text")
    return value


def _day_of(row: Mapping[str, Any]) -> datetime.date:
    """The day the row's ``dob`` names, read the way 5.6 resolves one."""
    try:
        return datetime.date.fromisoformat(_field(row, "dob"))
    except ValueError:
        raise WatchlistValueError("a seed row's dob is not a date") from None


def _matches(
    row: Mapping[str, Any],
    matched_on: str,
    *,
    document_number: str | None,
    name: str | None,
    dob: datetime.date | None,
) -> bool:
    """Whether ``row`` is one of the entries these three values find."""
    if matched_on == DOCUMENT_NUMBER:
        if document_number is None:
            return False
        return _field(row, "document_number") == document_number
    if name is None or dob is None:
        return False
    if name not in tuple(_field(row, key) for key in NAME_KEYS):
        return False
    return _day_of(row) == dob


class MockWatchlist(Watchlist):
    """A connector that answers 5.9's one question from ``watchlist.json``.

    **The seed is read once, when the connector is built**, and every lookup
    after that answers from the rows read then: the file does not change while
    a run is going, so a read per document is work a screening pays for
    nothing.  The rows are the connector's and not the module's, so a second
    connector reads the seed again and a row edited in it is a row the next
    connector answers from.

    The seed is synthetic and belongs to this project rather than to a service,
    and nothing here carries a matched value past the seam.
    """

    def __init__(self) -> None:
        """Read the seed's rows once, and return ``None``."""
        self._rows = _entries()

    def lookup(
        self,
        *,
        document_number: str | None,
        name: str | None,
        dob: datetime.date | None,
    ) -> list[WatchlistHit]:
        """Return the seed entry each of the three values finds.

        A ``document_number`` row is found by its document number alone, and an
        identity row by its name in either printed shape together with its date
        of birth.  An argument passed as ``None`` is a key that was not read,
        so it matches nothing rather than matching everything.

        Returns:
            One :class:`~app.risk.watchlist.WatchlistHit` per entry found, in
            the order the seed lists them, and no order is promised to a caller.
        """
        hits = []
        for row in self._rows:
            hit = WatchlistHit(
                _field(row, "kind"),
                _field(row, "entry_id"),
                _field(row, "matched_on"),
            )
            if _matches(
                row,
                hit.matched_on,
                document_number=document_number,
                name=name,
                dob=dob,
            ):
                hits.append(hit)
        return hits
