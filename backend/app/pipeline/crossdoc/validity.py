"""Cross-document validity window: does the visa cover the travel date?

16.6.  :func:`visa_validity_consistent` reads the validity window every visa
in a case prints and answers whether one injected travel date falls inside it.
The record it reads is :class:`~app.pipeline.crossdoc.documents.CaseDocument`,
the travel date arrives as an argument rather than as a field, and the window
is closed at both ends: D130.
"""
import collections.abc
import datetime

from app.pipeline.crossdoc.documents import (
    CONSISTENT,
    INCONSISTENT,
    NOT_CONFIGURED,
    VISA,
    CaseConsistency,
    CaseDocument,
    _case_of,
)
from app.pipeline.tier0.td3 import MrzValueError
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

__all__ = ["visa_validity_consistent"]

#: The tier every flag this module builds reports itself under, and the band
#: the weightset holds ``CROSSDOC_VALIDITY_WINDOW_MISMATCH`` under -- read as a
#: constant so a band cannot drift from the row it mirrors.
TIER = "crossdoc"
WEIGHT_BAND = "review"
#: The sentence an officer reads, and the reason on the flag.  Both name the
#: rule and print neither date; the two days the comparison was made from are
#: on ``expected`` and ``found``, which is where a flag carries them.
LABEL = (
    "A visa in this case does not cover the travel date with its own printed "
    "validity window."
)
REASON = "a visa's validity window does not include the travel date"
#: The name this code invented for the window the finding is about, never a
#: value the visa printed.
FIELD = "validity_window"
SOURCE_MODULE = "app.pipeline.crossdoc.validity"


def _as_day(value: object, name: str) -> datetime.date:
    """Return ``value`` as a plain :class:`datetime.date`, or refuse it.

    A :class:`datetime.datetime` is legal and is reduced to its day, on
    :func:`~app.pipeline.tier0.dates.expiry_result`'s reason: a caller holding
    a timestamp is not a caller making that mistake, and a window printed to
    the day compared against a time of day would answer in units nobody
    printed.  Anything else raises, because a travel date is never a fact
    about a document -- a caller who has not injected one has made a mistake
    rather than handed over a visa that cannot be read.
    """
    if not isinstance(value, datetime.date):
        raise MrzValueError(
            f"{name} must be a date, not {type(value).__name__}"
        )
    return datetime.date(value.year, value.month, value.day)


def _window(document: CaseDocument) -> tuple[datetime.date, datetime.date] | None:
    """Return the visa's window as two plain days, or ``None`` if it printed none.

    ``None`` is a visa that printed no window at all, which is not compared
    rather than flagged: it has not said its window is too short.  A window
    that prints only one end was refused when the record was built, so the two
    are either both there or both absent here.
    """
    if document.valid_from is None or document.valid_until is None:
        return None
    return _as_day(document.valid_from, "valid_from"), _as_day(
        document.valid_until, "valid_until"
    )


def _flag(window: tuple[datetime.date, datetime.date], travel: datetime.date) -> EvidenceFlag:
    """Return the one flag a window that misses the travel date becomes.

    ``expected`` is the window the visa printed as ``from/until`` and ``found``
    is the travel date, both as ISO 8601 days.  **A date is not identity
    data**, so unlike the passport reference of 16.5 these two halves are
    carried: an officer cannot act on "the visa does not cover the travel
    date" without the two days it was made from.
    """
    return EvidenceFlag(
        id=flag_ids.CROSSDOC_VALIDITY_WINDOW_MISMATCH,
        tier=TIER,
        label=LABEL,
        weight_band=WEIGHT_BAND,
        value=1.0,
        confidence=1.0,
        region=None,
        expected=f"{window[0].isoformat()}/{window[1].isoformat()}",
        found=travel.isoformat(),
        reason=REASON,
        source_module=SOURCE_MODULE,
        field=FIELD,
    )


def visa_validity_consistent(
    documents_in_case: collections.abc.Iterable[CaseDocument],
    travel_date: datetime.date,
) -> CaseConsistency:
    """Read every visa's printed validity window against one travel date.
    One flag per visa whose window does not include ``travel_date``, in the
    order the documents were given.  **The window is closed at both ends**: a
    visa valid *from* its first day is valid on it and one valid *until* its
    last day is valid on it, which is
    :func:`~app.pipeline.tier0.dates.expiry_result`'s own position that a
    document is valid through the day it expires.  A visa printing no window
    is not compared and raises nothing, so a case of such visas answers
    ``not_configured`` rather than a clean bill.
    :param documents_in_case: the case's documents, as
        :class:`~app.pipeline.crossdoc.documents.CaseDocument` records.
    :param travel_date: the day the journey happens, injected rather than read
        from a clock.
    :returns: the status, the flags, and how many windows were compared.
    :raises MrzValueError: if ``travel_date`` is not a date, or if
        ``documents_in_case`` is not a sequence of
        :class:`~app.pipeline.crossdoc.documents.CaseDocument` records.  Tier
        0's error, so a caller catching one around its cascade keeps working.
    """
    travel = _as_day(travel_date, "a travel date")
    # The sibling rule's own gate rather than a second copy of it: both rules
    # read the same record type, so the refusal for a case that is not one is
    # the same refusal.
    case = _case_of(documents_in_case)
    flags = []
    compared = 0
    for document in case:
        if document.role != VISA:
            continue
        window = _window(document)
        if window is None:
            continue
        compared += 1
        if not window[0] <= travel <= window[1]:
            flags.append(_flag(window, travel))
    status = INCONSISTENT if flags else (CONSISTENT if compared else NOT_CONFIGURED)
    return CaseConsistency(status=status, flags=tuple(flags), compared=compared)
