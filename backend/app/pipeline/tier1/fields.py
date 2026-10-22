"""Which printed field a read found, and what sits beside the field's label.

:func:`extract_fields` takes the words one page read produced and answers a
value per field its document type is known to print.  It finds a field by the
anchor words its label was printed as, and takes what sits to the right of them
on the same row, so a document type is one table rather than code.

**A value is what was printed, even when it matches no pattern.**  A rule's
pattern says which part of the text beside the label is the value; a field
whose text matches none of it still answers with all of it.  12.15 compares a
printed field against the MRZ field it must agree with, and a forged value is
often malformed -- dropping it here would leave that comparison with nothing to
disagree with, which is the one outcome this project exists to avoid.

**Rows are rebuilt from the boxes, because engines do not answer in reading
order**, and an anchor run may not bridge two printed blocks:
:data:`ANCHOR_ADJACENCY` is how near two words must be, as a multiple of their
own height, to count as printed side by side.

**A value is answered as printed, and normalised on request.**  12.13 is a
separate call and not a step inside :func:`extract_fields`, so what the page
printed stays on hand beside what it was shaped into — 12.15 compares the
second, and a value no pattern could read is the one most worth comparing.
**Normalising removes what a document prints inconsistently and adds nothing**,
so a value its normaliser cannot read is handed back exactly as it arrived.

**Every field is answered with the region it was read from**, or with ``None``
for one that could not be located.  A region is the four corners of the very
words its value was read from — the shape
:attr:`~app.risk.flags.EvidenceFlag.region` already carries — so 12.15 hangs
a finding on it without re-expressing it.  **It is the page's frame and not a
crop's**: a box out of a re-read is in that crop's own coordinates, and 12.8's
gate keeps the frame it read in ``FieldRead``.  An absent region is a claim and
not a gap, on the reason the flag's own ``region`` gives: a field nobody
printed is answered with no region rather than dropped.

**The tables sit behind a mapping proxy and a rule is frozen**, on 12.5's
reason that a caller may not edit the set a choice is made from.  **This module
holds no finding vocabulary**: what a disagreement means is 12.15's question,
and a field nothing could read is ``None`` rather than a finding.
"""

import calendar
import dataclasses
import datetime
import re
from collections.abc import Callable, Mapping
from types import MappingProxyType

from app.pipeline.tier0 import td3
from app.pipeline.tier1.ocr import OcrResult, OcrWord

__all__ = [
    "ANCHOR_ADJACENCY",
    "DATE",
    "DOCUMENT_TYPES",
    "ExtractedFields",
    "FIELD_TABLES",
    "FIELD_TYPES",
    "FieldRule",
    "MONTH_NUMBERS",
    "NAME",
    "NORMALISERS",
    "NATIONAL_ID",
    "NATIONAL_ID_FIELDS",
    "NUMBER",
    "PASSPORT",
    "PASSPORT_FIELDS",
    "UnknownDocumentError",
    "UnknownFieldTypeError",
    "VISA",
    "VISA_FIELDS",
    "extract_fields",
    "normalise_fields",
    "normalise_value",
]

#: The spelling of the document type this module opens with, and the first of
#: three: 12.12 added two names beside it rather than a second mechanism.
PASSPORT = "passport"

#: A visa and a national identity card, spelled the way the abstract and the
#: problem statement name them, so a caller holding one of those words and
#: nothing else finds a table.
VISA = "visa"
NATIONAL_ID = "national_id"

#: Every document type a table exists for, in the order they are held.  Spelled
#: out beside the registry rather than read off its keys, so the order is one
#: value a test can hold :data:`FIELD_TABLES` against.
DOCUMENT_TYPES = (PASSPORT, VISA, NATIONAL_ID)

#: The three value types a rule may name, spelled out beside the registry
#: rather than read off its keys.  **The type is a property of the field and
#: not of the document type**: a name is a name on all three tables, so keying
#: on the document would make a fourth table a fourth normaliser and put a
#: question about which table is in play ahead of a question about the value.
DATE = "date"
NAME = "name"
NUMBER = "number"
FIELD_TYPES = (DATE, NAME, NUMBER)

#: How near two words must be, as a multiple of their own height, to count as
#: printed side by side rather than as two blocks sharing a row.  A label is
#: printed as one run of words separated by a space's width, well under one line
#: of text at any scale an engine reads, while the value column is a form's own
#: gap away -- so the two are told apart by geometry and not by a gap in pixels
#: that a page of another size would move.  A constant and not a caller
#: argument, on ``D88``'s reason that one read carries no option.
ANCHOR_ADJACENCY = 1.0

#: A name as a passport prints one: capital letters in words, with a hyphen or
#: an apostrophe inside a word.  **Deliberately not a wordlist** -- a name this
#: project has never seen is still a name, and refusing one here would drop the
#: very value 12.15 has to compare.
_NAME = re.compile(r"[A-Z][A-Z]*(?:[ '-][A-Z][A-Z]*)*")

#: A document number as one whole printed run of letters and digits, from the
#: six a shorter number may be to the nine a passport number is allowed.  **Both
#: word boundaries are the band's edges**, so a run of the same characters that
#: is longer than the band matches nothing at all: it is not this field's number
#: cut short, and a pattern that cannot read the whole of a value leaves the
#: module to answer all of it rather than invent nine digits of it.
_DOCUMENT_NUMBER = re.compile(r"\b[A-Z0-9]{6,9}\b")

#: A national ID number as one whole run of letters and digits, on a **wider
#: band than a passport's and deliberately a pattern of its own**: ICAO bounds
#: a travel document's number at nine characters and an identity card's number
#: is not bound by that standard at all, so answering one through the passport's
#: pattern would hand 12.15 nine digits of a twelve.  **Both word boundaries
#: are the band's edges holding**, on :data:`_DOCUMENT_NUMBER`'s reason: a run
#: longer than the band is not this field's number cut short, it is a value the
#: pattern cannot read, and the module's rule answers that whole.
_NATIONAL_ID_NUMBER = re.compile(r"\b[A-Z0-9]{6,14}\b")

#: A date as a document prints one: ``12 AUG 1974``, day, three-letter month,
#: four-digit year.  12.13 is what turns it into ISO, so nothing here asks for
#: a year written as the two digits the MRZ carries.
_DAY_MONTH_YEAR = re.compile(r"(\d{1,2})\s+([A-Z]{3})\s+(\d{4})")

#: The three-letter month a document prints, against the number it stands for.
#: **Read out of the standard library's own month table** rather than typed in
#: as twelve remembered values, on 1.6's rule -- and upper-cased here because a
#: document prints its month in capitals and ``calendar`` does not.
MONTH_NUMBERS: Mapping[str, int] = MappingProxyType({
    spelling.upper(): number
    for number, spelling in enumerate(calendar.month_abbr)
    if spelling
})


@dataclasses.dataclass(frozen=True)
class FieldRule:
    """One printed field: the anchor words that find it, and its value's shape.

    ``anchors`` are the label spellings the document type is known to print,
    compared with case, spacing and edge punctuation set aside; ``value``
    matches the text beside whichever anchor was printed; ``value_type`` is the
    one of :data:`FIELD_TYPES` 12.13 normalises the answer as, and it is
    **required rather than defaulted**, so a field added to a table cannot reach
    12.15 unnormalised by leaving it out.  Frozen, for the reason
    :class:`~app.pipeline.tier1.ocr.OcrResult` is.
    """

    field: str
    anchors: tuple[str, ...]
    value: re.Pattern
    value_type: str


#: The fields a passport data page is printed with.  ``field`` names match
#: :attr:`FieldRule.field`, and ``tests.fixtures.document_images`` prints exactly
#: these four -- so a page the fixture draws and a table that can read it are
#: one thing a test can state.
PASSPORT_FIELDS = (
    FieldRule(field="name", anchors=("Name", "Full Name"), value=_NAME, value_type=NAME),
    FieldRule(
        field="passport_number",
        anchors=("Passport No", "Passport Number"),
        value=_DOCUMENT_NUMBER,
        value_type=NUMBER,
    ),
    FieldRule(
        field="date_of_birth",
        anchors=("Date of birth", "Birth date"),
        value=_DAY_MONTH_YEAR,
        value_type=DATE,
    ),
    FieldRule(
        field="date_of_expiry",
        anchors=("Date of expiry", "Expiry date", "Date of expiration"),
        value=_DAY_MONTH_YEAR,
        value_type=DATE,
    ),
)

#: The fields a visa is printed with, in the order a visa page prints them.
#: **The four the passport table names and no others**: a visa's MRZ is a TD2
#: and a passport's is a TD3, and 12.15 compares each printed field with the MRZ
#: field it must agree with, so a field no MRZ carries has nothing to be
#: compared against here.  ``tests.unit.test_fields`` prints these rows and
#: holds this table to them.
VISA_FIELDS = (
    FieldRule(field="name", anchors=("Name", "Full Name"), value=_NAME, value_type=NAME),
    FieldRule(
        field="visa_number",
        anchors=("Visa No", "Visa Number"),
        value=_DOCUMENT_NUMBER,
        value_type=NUMBER,
    ),
    FieldRule(
        field="date_of_birth",
        anchors=("Date of birth", "Birth date"),
        value=_DAY_MONTH_YEAR,
        value_type=DATE,
    ),
    FieldRule(
        field="date_of_expiry",
        anchors=("Date of expiry", "Valid until", "Expiry date"),
        value=_DAY_MONTH_YEAR,
        value_type=DATE,
    ),
)

#: The fields a national identity card is printed with, in the order the card
#: prints them: the passport table's four fields over a number band of its own,
#: because a TD1's document number is an identity card's number and not a
#: travel document's.
NATIONAL_ID_FIELDS = (
    FieldRule(field="name", anchors=("Name", "Full Name"), value=_NAME, value_type=NAME),
    FieldRule(
        field="national_id_number",
        anchors=("ID No", "ID Number", "National ID No"),
        value=_NATIONAL_ID_NUMBER,
        value_type=NUMBER,
    ),
    FieldRule(
        field="date_of_birth",
        anchors=("Date of birth", "Birth date"),
        value=_DAY_MONTH_YEAR,
        value_type=DATE,
    ),
    FieldRule(
        field="date_of_expiry",
        anchors=("Date of expiry", "Valid until", "Expiry date"),
        value=_DAY_MONTH_YEAR,
        value_type=DATE,
    ),
)

#: The table per document type, behind a mapping proxy so no caller can add a
#: document type this module would then have to answer for.
FIELD_TABLES: Mapping[str, tuple[FieldRule, ...]] = MappingProxyType(
    {
        PASSPORT: PASSPORT_FIELDS,
        VISA: VISA_FIELDS,
        NATIONAL_ID: NATIONAL_ID_FIELDS,
    }
)


class UnknownDocumentError(ValueError):
    """Raised when a caller names a document type no table here holds.

    A ``ValueError``, so a caller already catching one around this choice keeps
    working.  This is a wiring mistake and not an absence: every name in
    :data:`DOCUMENT_TYPES` has a table, and answering ``None`` for a misspelling
    would hand 12.15 four absent fields on every document and say nothing about
    which type was asked for.
    """


class UnknownFieldTypeError(ValueError):
    """Raised when a rule names a value type no normaliser here holds.

    A ``ValueError`` for :class:`UnknownDocumentError`'s reason: every name in
    :data:`FIELD_TYPES` has a normaliser, so a name outside them is a wiring
    mistake, and answering such a value as it was printed would hand 12.15
    something that looks compared and was not.
    """


def _normalise_date(rule: FieldRule, value: str) -> str:
    """``value`` as ISO ``YYYY-MM-DD``, or unchanged where it is not a date.

    The three components are read off ``rule``'s own pattern, so the shape the
    table matched a date on is the shape it is read back from.  **An unknown
    month and an impossible day both answer as they were printed**: a 31st of
    February is carried through rather than rolled into March, because a date
    the page never carried is a disagreement 12.15 can see, and a silent
    correction is one it cannot.
    """
    found = rule.value.search(value)
    if found is None:
        return value
    month = MONTH_NUMBERS.get(found.group(2))
    if month is None:
        return value
    try:
        printed = datetime.date(int(found.group(3)), month, int(found.group(1)))
    except ValueError:
        return value
    return printed.isoformat()


def _normalise_name(rule: FieldRule, value: str) -> str:
    """``value`` upper-cased, with every diacritic Tier 0 would take off.

    The printed name is one run and is not split — 2.8's rule that a space
    is not a separator — so it is handed to Tier 0 as a surname and no given
    names are invented beside it.  **Tier 0's own map and its own
    combining-mark rule do the work**, on the argument :func:`~app.pipeline.tier0.mrz.check_digit`
    gives: the same two hundred accented letters remembered a second time is a
    second place for them to be wrong.
    """
    return td3.transliterate_names(value.upper(), ())[0]


def _normalise_number(rule: FieldRule, value: str) -> str:
    """``value`` with its spaces removed, where what is left is still a number.

    A document prints a long number in groups, and the groups are the value.
    **What goes is whitespace and nothing else**, and ``rule``'s own band
    decides whether what is left is a number at all — so a run the band
    cannot hold is answered whole, on 12.11's rule that a value it cannot read
    is still a value, and a hyphen the band does not admit is not swapped for
    nothing the way a space is.
    """
    joined = re.sub(r"\s+", "", value)
    return joined if rule.value.search(joined) is not None else value


NORMALISERS: Mapping[str, Callable[[FieldRule, str], str]] = MappingProxyType({
    DATE: _normalise_date,
    NAME: _normalise_name,
    NUMBER: _normalise_number,
})


@dataclasses.dataclass(frozen=True)
class ExtractedFields:
    """What one page's read held for one document type: a value per field.

    ``values`` carries an entry for every field the table names, holding
    ``None`` where the page printed no anchor for it -- absence, not an empty
    string, so a caller can tell a field nobody printed from one printed blank.

    ``regions`` carries an entry for the same fields, holding the four corners
    of the words that field's value was read from, or ``None`` where there is no
    value to point at.  **Required and not defaulted**, on 12.13's reason: a
    field whose region a record does not carry is a field 12.15 has nowhere to
    point, and the slot left out is the same gap.

    Read-only, because a caller editing either would leave the table and the
    record disagreeing about what the document was asked for.
    """

    document_type: str
    values: Mapping[str, str | None]
    regions: Mapping[str, tuple[tuple[int, int], ...] | None]


def _fold(text: str) -> str:
    """``text`` as a label spelling is compared: spacing and edges aside."""
    return " ".join(text.split()).strip(" .:,").casefold()


def _shares_row(line: list, word: OcrWord) -> bool:
    """Whether ``word``'s vertical span meets the row ``line`` was printed on.

    The span, not the baseline: an engine's box is all this module is given,
    and a word set in a different face is a shorter box on the same row.
    """
    top = min(one.bbox[1] for one in line)
    bottom = max(one.bbox[3] for one in line)
    return word.bbox[1] < bottom and word.bbox[3] > top


def _rows(words: tuple) -> list:
    """``words`` grouped into the rows they were printed on, each left to right.

    Sorted before grouping so the answer does not depend on the order an engine
    happened to report its words in -- nothing in :class:`OcrResult` promises
    reading order, and one that did would be a second promise to keep.
    """
    ordered = sorted(words, key=lambda one: (one.bbox[1], one.bbox[0]))
    grouped: list[list] = []
    for word in ordered:
        for line in grouped:
            if _shares_row(line, word):
                line.append(word)
                break
        else:
            grouped.append([word])
    return [sorted(line, key=lambda one: one.bbox[0]) for line in grouped]


def _side_by_side(left: OcrWord, right: OcrWord) -> bool:
    """Whether two words were printed beside each other or in separate blocks."""
    height = min(left.bbox[3] - left.bbox[1], right.bbox[3] - right.bbox[1])
    if height <= 0:
        return False
    return right.bbox[0] - left.bbox[2] <= ANCHOR_ADJACENCY * height


def _anchor_end(line: list, rule: FieldRule):
    """The index one past ``rule``'s anchor words on ``line``, or ``None``.

    The leftmost run wins, so a label carrying one of a field's anchor spellings
    inside a longer phrase is not read as that field's label.
    """
    for start in range(len(line)):
        for anchor in rule.anchors:
            span = len(anchor.split())
            run = line[start:start + span]
            if len(run) != span:
                continue
            if not all(_side_by_side(one, two) for one, two in zip(run, run[1:])):
                continue
            if _fold(" ".join(one.text for one in run)) == _fold(anchor):
                return start + span
    return None


def _printed_words(line: list, rule: FieldRule, start: int):
    """The value printed beside an anchor, and the words it was read from.

    **The whole of the text when the pattern matches none of it**, so a value
    printed malformed is still a value, and the match is trimmed to its own
    extent, so trailing text another field printed on the same row is not read
    as part of it.  The words answered are the value's own, which is what makes
    a region and a value describe the same ink.  ``None`` beside a bare anchor.
    """
    taken = line[start:]
    spans, cursor = [], 0
    for word in taken:
        spans.append((cursor, cursor + len(word.text)))
        cursor += len(word.text) + 1
    raw = " ".join(word.text for word in taken)
    text = raw.strip()
    if not text:
        return None
    found = rule.value.search(text)
    if found is None:
        return text, taken
    # The match sits in the stripped row and the spans in the raw one.
    lead = len(raw) - len(raw.lstrip())
    first, last = found.start() + lead, found.end() + lead
    covered = tuple(
        word for word, (begin, end) in zip(taken, spans) if begin < last and end > first
    )
    return found.group(0), covered or taken


def _region(words: tuple):
    """``words``' own boxes as four corners, clockwise from the top left.

    **The union of the boxes the value was read from and nothing else**, so a
    region points at the value rather than at the label beside it.  Four
    corners rather than a box, because that is the shape a flag's ``region``
    already carries.  **Plain ``int``**, as ``MrzComponent`` converts to, so a
    region can go into a JSON body.
    """
    boxes = [word.bbox for word in words]
    left = int(min(box[0] for box in boxes))
    top = int(min(box[1] for box in boxes))
    right = int(max(box[2] for box in boxes))
    bottom = int(max(box[3] for box in boxes))
    return ((left, top), (right, top), (right, bottom), (left, bottom))


def _table_named(document_type: object) -> tuple:
    """The table ``document_type`` names, refusing a name this call cannot hold."""
    if isinstance(document_type, str) and document_type in FIELD_TABLES:
        return FIELD_TABLES[document_type]
    raise UnknownDocumentError(
        f"document_type must be one of {', '.join(FIELD_TABLES)}; "
        f"{document_type!r} is not one."
    )


def extract_fields(read: OcrResult, document_type: str) -> ExtractedFields:
    """Answer one value per field ``document_type`` is printed with.

    :param read: what the page read produced -- the words
        :func:`~app.pipeline.tier1.runner.run_tier1` returns, and
        :data:`~app.pipeline.tier1.ocr.NO_WORDS` when no engine could read the
        page.
    :param document_type: one of :data:`DOCUMENT_TYPES`, spelled exactly.
    :returns: an :class:`ExtractedFields` carrying an entry for every field
        that table names, each holding the text printed beside that field's
        anchor with the corners of the words it was read from, or ``None`` for
        both where the page printed none.
    :raises ValueError: when ``read`` is not an :class:`~app.pipeline.tier1.ocr.OcrResult`.
    :raises UnknownDocumentError: when ``document_type`` names no table here.
    """
    if not isinstance(read, OcrResult):
        raise ValueError(f"read must be an OcrResult, not {type(read).__name__}")
    rules = _table_named(document_type)
    rows = _rows(read.words)
    values, regions = {}, {}
    for rule in rules:
        found = None
        for row in rows:
            end = _anchor_end(row, rule)
            if end is not None:
                found = _printed_words(row, rule, end)
                break
        values[rule.field] = None if found is None else found[0]
        regions[rule.field] = None if found is None else _region(found[1])
    return ExtractedFields(
        document_type=document_type,
        values=MappingProxyType(values),
        regions=MappingProxyType(regions),
    )


def normalise_value(rule: FieldRule, value: str | None) -> str | None:
    """``value`` shaped as ``rule``'s own value type; ``None`` answers ``None``.

    :param rule: the rule the value was read through, which is what says both
        the type and — for a number — the band to hold it to.
    :param value: what was printed, or ``None`` for a field nobody printed.
    :returns: the normalised value, or ``value`` itself where the normaliser
        cannot read it, so nothing this call is handed is ever lost.
    :raises ValueError: when ``rule`` is not a :class:`FieldRule`, or ``value``
        is neither a string nor ``None``.
    :raises UnknownFieldTypeError: when ``rule`` names no type in
        :data:`NORMALISERS` — including a name that is not a string at all.
    """
    if not isinstance(rule, FieldRule):
        raise ValueError(f"rule must be a FieldRule, not {type(rule).__name__}")
    if not isinstance(rule.value_type, str) or rule.value_type not in NORMALISERS:
        raise UnknownFieldTypeError(
            f"value_type must be one of {', '.join(NORMALISERS)}; "
            f"{rule.value_type!r} is not one."
        )
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"value must be a string or None, not {type(value).__name__}")
    return NORMALISERS[rule.value_type](rule, value)


def normalise_fields(extracted: ExtractedFields) -> ExtractedFields:
    """``extracted`` with every value shaped as the type its own rule names.

    The rules are the document type's own table, so all three document types
    are covered by this one walk and neither by a second code path nor by a
    field list — the argument :data:`FIELD_TABLES` already carries.

    :param extracted: what :func:`extract_fields` answered.
    :returns: a new frozen :class:`ExtractedFields`, carrying the regions of
        the record it was given.  That record is not edited, so what the page
        printed stays on hand beside what it was shaped into.
    :raises ValueError: when ``extracted`` is not an :class:`ExtractedFields`.
    :raises UnknownDocumentError: when its document type names no table here.
    """
    if not isinstance(extracted, ExtractedFields):
        raise ValueError(
            f"extracted must be an ExtractedFields, not {type(extracted).__name__}"
        )
    rules = _table_named(extracted.document_type)
    return ExtractedFields(
        document_type=extracted.document_type,
        values=MappingProxyType({
            rule.field: normalise_value(rule, extracted.values[rule.field])
            for rule in rules
        }),
        regions=MappingProxyType({
            rule.field: extracted.regions.get(rule.field) for rule in rules
        }),
    )
