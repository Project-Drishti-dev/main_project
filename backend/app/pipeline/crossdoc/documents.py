"""Cross-document passport reference: does a visa name a passport in its case?
16.5.  :func:`documents_consistent` reads the passport number each visa in a
case prints and answers whether the case holds that passport.  The status
vocabulary, the key, and why a flag carries no number are D129.
"""
import collections.abc
import dataclasses
import datetime
from app.pipeline.tier0.mrz import FILLER
from app.pipeline.tier0.td3 import MrzValueError
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag
__all__ = [
    "CONSISTENT",
    "INCONSISTENT",
    "NOT_CONFIGURED",
    "STATUSES",
    "CaseConsistency",
    "CaseDocument",
    "documents_consistent",
]
#: The tier every flag this module builds reports itself under.
TIER = "crossdoc"
#: The three roles a document may hold in a case.  A closed vocabulary, so a
#: role nobody wrote down is a refusal rather than a document compared as
#: something it might be.
PASSPORT = "passport"
VISA = "visa"
ID_DOCUMENT = "id"
DOCUMENT_ROLES = (PASSPORT, VISA, ID_DOCUMENT)
#: Three answers, and ``consistent`` is not reachable from an empty case.
CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"
NOT_CONFIGURED = "not_configured"
STATUSES = (CONSISTENT, INCONSISTENT, NOT_CONFIGURED)
#: The band the weightset carries ``CROSSDOC_UNKNOWN_PASSPORT_REFERENCE``
#: under, read as a constant so a band cannot drift from the row it mirrors.
WEIGHT_BAND = "review"
#: The sentence an officer reads, and the reason on the flag.  **Neither
#: carries a document number**: the number is the identity data this screening
#: is about, and every message in this project names a rule rather than its
#: value.  They are also identical, because the only datum that would tell two
#: offending visas apart is the number neither may print.
LABEL = (
    "A visa in this case references a passport number that no passport "
    "in this case prints."
)
REASON = "a visa's passport reference matched no passport in this case"
#: The layout's own name for the field a TD3 visa prints that number in.
FIELD = "personal_number"

def _check_number(value: object, name: str) -> None:
    """Refuse ``value`` unless it is a string.
    The type is the whole of the check, on D116's rule: a number that arrived
    as an ``int`` is a value this module did not read off a document, and
    coercing it would make a caller's bug look like a printed number.
    """
    if not isinstance(value, str):
        raise MrzValueError(
            f"a case document's {name} must be a string, not "
            f"{type(value).__name__}"
        )

def _check_window(
    valid_from: object, valid_until: object
) -> None:
    """Refuse a validity window that is half printed or not two dates.

    **Both ends or neither**: a window with one end is a document whose other
    end was not read, and this record is what the caller hands over rather
    than a measurement of a document, so a half window is a caller mistake
    and not a document that printed half a window.  A
    :class:`datetime.datetime` is refused rather than reduced, because this
    record is a transcription and the caller who holds a timestamp should
    name the day; :func:`~app.pipeline.crossdoc.validity._as_day` reduces one
    when the comparison is made.
    """
    for name, value in (
        ("valid_from", valid_from),
        ("valid_until", valid_until),
    ):
        if value is not None and not isinstance(value, datetime.date):
            raise MrzValueError(
                f"a case document's {name} must be a date, not "
                f"{type(value).__name__}"
            )
    if (valid_from is None) != (valid_until is None):
        raise MrzValueError(
            "a case document's validity window is printed from a day to a "
            "day, so neither end is set or both are"
        )

@dataclasses.dataclass(frozen=True)
class CaseDocument:
    """One document in a case: the role it plays, and what it prints.
    ``role`` is one of :data:`DOCUMENT_ROLES` and ``document_number`` is what
    the document itself prints.  ``referenced_passport_number`` is a visa's
    passport reference and ``None`` on every other role, which is refused
    rather than read: only a visa names a passport, so a passport carrying
    one is a caller that built a record the standard does not describe.
    ``valid_from`` and ``valid_until`` are the two days the document's own
    validity window prints, **both or neither**, and any role may carry one:
    every document prints a window and nothing in this package asks a
    passport not to.  The day the window is checked *against* is not a field
    here and never becomes one -- D130.
    Frozen, on :class:`~app.pipeline.tier0.td3.MrzDocument`'s reason: a
    document number that could be edited after the fact is a number nobody
    read off a document.
    """
    role: str
    document_number: str
    referenced_passport_number: str | None = None
    valid_from: datetime.date | None = None
    valid_until: datetime.date | None = None
    def __post_init__(self) -> None:
        """Check the role, the numbers and the window, assign nothing, return ``None``."""
        if not isinstance(self.role, str) or self.role not in DOCUMENT_ROLES:
            raise MrzValueError(
                "a case document's role must be one of "
                + ", ".join(DOCUMENT_ROLES)
            )
        _check_number(self.document_number, "document_number")
        _check_window(self.valid_from, self.valid_until)
        if self.role != VISA:
            if self.referenced_passport_number is not None:
                raise MrzValueError(
                    "only a visa references a passport number"
                )
            return
        if self.referenced_passport_number is not None:
            _check_number(
                self.referenced_passport_number, "referenced_passport_number"
            )

@dataclasses.dataclass(frozen=True)
class CaseConsistency:
    """What comparing one case's documents against each other found.
    ``status`` is one of :data:`STATUSES` and ``compared`` is how many
    cross-references were actually taken, which is what tells an empty case
    apart from a case whose visas all resolved.  ``flags`` is one flag per
    visa that referenced nothing in the case, so its length and
    ``status == INCONSISTENT`` are the same fact read twice.
    """
    status: str
    flags: tuple[EvidenceFlag, ...]
    compared: int
    def __post_init__(self) -> None:
        """Check the status and the flags, assign nothing, return ``None``."""
        if not isinstance(self.status, str) or self.status not in STATUSES:
            raise MrzValueError(
                "a case consistency status must be one of " + ", ".join(STATUSES)
            )
        if not isinstance(self.flags, tuple) or not all(
            isinstance(flag, EvidenceFlag) for flag in self.flags
        ):
            raise MrzValueError("flags must be a tuple of EvidenceFlag records")
        if isinstance(self.compared, bool) or not isinstance(self.compared, int):
            raise MrzValueError("compared must be a whole number of comparisons")

def _number_key(number: str) -> str:
    """Return ``number`` as the key two documents are matched on.
    Upper-cased, whitespace dropped and the MRZ filler removed, because the
    same passport number is printed into two fixed-width fields of two
    different documents and the widths need not agree.  **No digraph is
    folded**: D127 kept those for the name comparison and a number has none.
    """
    return "".join(number.upper().split()).replace(FILLER, "")

def _sequence_of(documents_in_case: object) -> tuple:
    """Return ``documents_in_case`` as a tuple, or raise.
    A bare string is refused before it is measured, on
    :func:`~app.pipeline.tier0.document._zone_of`'s reason: a string is a
    sequence of one-character documents, so iterating it would answer about
    every character in it and point at the wrong mistake entirely.  This is
    the shape half of :func:`_case_of` held apart, so a rule reading a
    different record can ask the same question of the same argument.
    """
    if isinstance(documents_in_case, (str, bytes)):
        raise MrzValueError(
            "a case is a sequence of documents, not one string of "
            f"{len(documents_in_case)} characters"
        )
    try:
        return tuple(documents_in_case)
    except TypeError:
        raise MrzValueError(
            "a case must be a sequence of documents, not "
            f"{type(documents_in_case).__name__}"
        ) from None

def _case_of(documents_in_case: object) -> tuple[CaseDocument, ...]:
    """Return ``documents_in_case`` as a tuple of documents, or raise.
    The shape refusals are :func:`_sequence_of`'s rather than a second copy
    of them, so the three rules cannot disagree about what a case is.
    """
    case = _sequence_of(documents_in_case)
    for document in case:
        if not isinstance(document, CaseDocument):
            raise MrzValueError(
                "a case holds CaseDocument records, not "
                f"{type(document).__name__}"
            )
    return case

def _flag() -> EvidenceFlag:
    """Return the one flag an unresolved passport reference becomes."""
    return EvidenceFlag(
        id=flag_ids.CROSSDOC_UNKNOWN_PASSPORT_REFERENCE,
        tier=TIER,
        label=LABEL,
        weight_band=WEIGHT_BAND,
        value=1.0,
        confidence=1.0,
        region=None,
        expected=None,
        found=None,
        reason=REASON,
        source_module="app.pipeline.crossdoc.documents",
        field=FIELD,
    )


def documents_consistent(
    documents_in_case: collections.abc.Iterable[CaseDocument],
) -> CaseConsistency:
    """Read every visa's passport reference against the case's passports.
    One flag per visa whose reference names no passport in the case, in the
    order the documents were given.  A visa that printed no reference is not
    compared and raises nothing, so a case of such visas answers
    ``not_configured`` rather than a clean bill.
    :param documents_in_case: the case's documents, as
        :class:`CaseDocument` records.
    :returns: the status, the flags, and how many references were compared.
    :raises MrzValueError: if ``documents_in_case`` is not a sequence of
        :class:`CaseDocument` records.  Tier 0's error, so a caller catching
        one around its cascade keeps working.
    """
    case = _case_of(documents_in_case)
    passports = {
        _number_key(document.document_number)
        for document in case
        if document.role == PASSPORT
    }
    flags = []
    compared = 0
    for document in case:
        if document.role != VISA:
            continue
        reference = _number_key(document.referenced_passport_number or "")
        if not reference:
            continue
        compared += 1
        if reference not in passports:
            flags.append(_flag())
    status = INCONSISTENT if flags else (CONSISTENT if compared else NOT_CONFIGURED)
    return CaseConsistency(
        status=status, flags=tuple(flags), compared=compared
    )
