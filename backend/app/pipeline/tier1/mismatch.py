"""Whether each printed field agrees with the field it must match.

:func:`compare_to_mrz` walks a document type's own field table and answers one
:class:`~app.risk.flags.EvidenceFlag` for every field whose printed value
disagrees with the machine-readable zone, each carrying that field's own region
and the two halves of the comparison.  :func:`compare_to_barcode` asks the same
question of a 2D barcode's payload.  ``D93`` and ``D94`` record what each decides.
"""

import re
from collections.abc import Mapping
from types import MappingProxyType

from app.pipeline.tier0 import td3
from app.pipeline.tier0.mrz import FILLER, MrzValueError
from app.pipeline.tier0.td3 import MrzDocument
from app.pipeline.tier1 import fields
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

__all__ = [
    "BARCODE_FIELDS",
    "BARCODE_MISMATCH_BAND",
    "MRZ_FIELDS",
    "MISMATCH_BAND",
    "SOURCE_MODULE",
    "compare_to_barcode",
    "compare_to_mrz",
]

#: The MRZ attributes each printed field must agree with, in the order the zone
#: prints them.  Every field of every table in :data:`fields.FIELD_TABLES` is
#: mapped, and one that is not is a refusal rather than a silent skip.
MRZ_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "name": ("surname", "given_names"),
    "passport_number": ("document_number",),
    "visa_number": ("document_number",),
    "national_id_number": ("document_number",),
    "date_of_birth": ("date_of_birth",),
    "date_of_expiry": ("date_of_expiry",),
})

#: The severity band this finding sits in.  Stated here because
#: :class:`~app.risk.flags.EvidenceFlag` asks for one and the weight that
#: belongs to it is data rather than code; a test holds this to ``v1.yaml``.
MISMATCH_BAND = "high"

#: The band 13.3's finding sits in, and deliberately the weaker of the two:
#: both of its readings come off one image, so either can be the wrong one.
BARCODE_MISMATCH_BAND = "review"

#: The printed fields a 2D barcode payload is expected to match, and the TD3
#: line-2 field each one is read from.  A table rather than a chain of tests,
#: so a document type is added by naming its number here.  ``name`` is absent
#: and that absence is the claim: a TD3 payload carries no name to disagree.
BARCODE_FIELDS: Mapping[str, str] = MappingProxyType({
    "passport_number": "document_number",
    "visa_number": "document_number",
    "national_id_number": "document_number",
    "date_of_birth": "date_of_birth",
    "date_of_expiry": "date_of_expiry",
})

#: The name every finding this module builds answers under.
SOURCE_MODULE = "app.pipeline.tier1.mismatch"

#: The three value types a rule may name, and which of them ``tolerance``
#: reaches.  A name is words a document spells inconsistently, so a count of
#: words is what a caller states; a date and a number are exact or are not.
_TOLERATED = fields.NAME

#: The other side of each comparison, named in the sentence a finding holds.
_ZONE_SOURCE = "the machine-readable zone"
_BARCODE_SOURCE = "the barcode"

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MRZ_DATE = re.compile(r"^(\d{2})(\d{2})(\d{2})$")


def _words(text):
    """``text`` as upper-case words, the filler the MRZ pads with set aside."""
    return tuple(text.upper().replace(FILLER, " ").split())


def _mrz_text(attributes, document):
    """The zone's own characters for one printed field, or ``None``.

    ``None`` where the record carries none of them: a TD1's name sits on a line
    this build does not read, which is an absence rather than a disagreement.
    """
    halves = []
    for name in attributes:
        half = getattr(document, name, None)
        if half is None:
            return None
        halves.append(half if isinstance(half, str) else " ".join(half))
    return " ".join(_words(" ".join(halves))) or None


def _token_distance(left, right):
    """The fewest words one sequence must lose or gain to become the other."""
    previous = list(range(len(right) + 1))
    for row, one in enumerate(left, start=1):
        current = [row]
        for column, two in enumerate(right, start=1):
            current.append(min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + (one != two),
            ))
        previous = current
    return previous[-1]


def _dates_agree(printed, printed_mrz):
    """Whether an ISO date and a six-character MRZ date name the same day.

    Only the two year digits the zone prints are compared, so no century is
    invented; ``mrz.infer_birth_year`` is what turns a printed ``YYMMDD`` into
    a year, and this comparator is not that function.
    """
    left, right = _ISO_DATE.match(printed), _MRZ_DATE.match(printed_mrz)
    if left is None or right is None:
        return False
    return (left.group(1)[2:], left.group(2), left.group(3)) == right.groups()


def _exact_agrees(rule, printed, other):
    """Whether two values of a type no tolerance reaches are one value.

    :returns: whether ``printed`` and ``other`` name the same value.
    :raises ValueError: when ``rule`` names a name, which has no exact form.
    """
    if rule.value_type == fields.DATE:
        return _dates_agree(printed, other)
    if rule.value_type == fields.NUMBER:
        return printed == other
    raise ValueError(
        f"value_type must be one of "
        f"{', '.join(sorted((fields.DATE, fields.NAME, fields.NUMBER)))}; "
        f"{rule.value_type!r} is not one."
    )


def _agrees(rule, printed, printed_mrz, tolerance, words):
    """Whether ``printed`` and the zone's own text are one field's value.

    :param words: the zone's text already split, which the name comparison needs.
    :returns: ``(agrees, agreed)``, where ``agreed`` is ``None`` for a value
        that is not a name and has no words to count.
    :raises ValueError: when ``rule`` names a value type this cannot compare.
    """
    if rule.value_type == _TOLERATED:
        agreed = len(words) - _token_distance(_words(printed), words)
        return agreed >= len(words) - tolerance, agreed
    return _exact_agrees(rule, printed, printed_mrz), None


def _expected(rule, printed_mrz, words):
    """The half the zone carried, as short as it can honestly be made."""
    if rule.value_type == _TOLERATED:
        return f"{len(words)} name words"
    return printed_mrz


def _found(rule, printed, agreed):
    """The half the page carried, in the terms :func:`_expected` used."""
    if rule.value_type == _TOLERATED:
        return f"{agreed} agree"
    return printed


def _label(rule, source=_ZONE_SOURCE):
    """The one sentence a finding's label holds, naming no printed text."""
    name = rule.field.replace("_", " ")
    return f"the printed {name} disagrees with {source}"


def _reason(rule, tolerance, agreed, total):
    """The one sentence a finding's reason holds, naming no printed text."""
    if rule.value_type == _TOLERATED:
        return (
            f"{agreed} of the {total} words the zone's name carries are on the "
            f"printed page, and the tolerance is {tolerance}"
        )
    if rule.value_type == fields.DATE:
        return "the printed date and the machine-readable date are not the same day"
    return "the printed number and the machine-readable number are not the same number"


def _barcode_reason(rule):
    """The sentence a barcode finding's reason holds, naming no printed text."""
    if rule.value_type == fields.DATE:
        return "the printed date and the date in the barcode are not the same day"
    return "the printed number and the number in the barcode are not the same number"


def compare_to_mrz(ocr_fields, mrz_document, tolerance):
    """One finding per printed field that disagrees with the zone beside it.

    :param ocr_fields: the record :func:`~app.pipeline.tier1.fields.normalise_fields`
        answered, so that both sides are shaped alike; a record no normaliser
        has shaped is compared exactly as the page printed it.
    :param mrz_document: the zone's :class:`~app.pipeline.tier0.td3.MrzDocument`.
    :param tolerance: how many name words may differ before a name disagrees,
        counted in words and not in characters.  Required and not defaulted, so
        every call states the policy it was given.
    :returns: a tuple of :class:`~app.risk.flags.EvidenceFlag` in the table's
        printed order, empty where every field agreed.
    :raises ValueError: for a record, a zone or a tolerance this cannot hold,
        and for a field no entry in :data:`MRZ_FIELDS` names.
    :raises fields.UnknownDocumentError: when the record names no table here.
    """
    if not isinstance(ocr_fields, fields.ExtractedFields):
        raise ValueError(
            f"ocr_fields must be an ExtractedFields, not {type(ocr_fields).__name__}"
        )
    if not isinstance(mrz_document, MrzDocument):
        raise ValueError(
            f"mrz_document must be a MrzDocument, not {type(mrz_document).__name__}"
        )
    if isinstance(tolerance, bool) or not isinstance(tolerance, int) or tolerance < 0:
        raise ValueError(f"tolerance must be a whole count of words, not {tolerance!r}")
    rules = fields.FIELD_TABLES.get(ocr_fields.document_type)
    if rules is None:
        raise fields.UnknownDocumentError(
            f"document_type must be one of {', '.join(fields.FIELD_TABLES)}; "
            f"{ocr_fields.document_type!r} is not one."
        )
    unmapped = sorted(rule.field for rule in rules if rule.field not in MRZ_FIELDS)
    if unmapped:
        raise ValueError(f"no MRZ field is mapped to the printed field {unmapped[0]!r}")

    flags = []
    for rule in rules:
        printed = ocr_fields.values[rule.field]
        if printed is None:
            continue
        printed_mrz = _mrz_text(MRZ_FIELDS[rule.field], mrz_document)
        if printed_mrz is None:
            continue
        words = tuple(printed_mrz.split())
        agrees, agreed = _agrees(rule, printed, printed_mrz, tolerance, words)
        if agrees:
            continue
        flags.append(EvidenceFlag(
            id=flag_ids.OCR_MRZ_MISMATCH,
            tier=1,
            label=_label(rule),
            weight_band=MISMATCH_BAND,
            value=1.0,
            confidence=1.0,
            region=ocr_fields.regions.get(rule.field),
            expected=_expected(rule, printed_mrz, words),
            found=_found(rule, printed, agreed),
            reason=_reason(rule, tolerance, agreed, len(words)),
            source_module=SOURCE_MODULE,
            field=rule.field,
        ))
    return tuple(flags)


def _payload_line(payload):
    """The line of a TD3-shaped payload a field is read from, or ``None``.

    ``None`` is a payload this cannot read at all, which is an absence and not
    a disagreement: to name what such a payload disagrees with would be
    inventing the other half of the comparison rather than reporting one.

    The payload's own edges are set aside before it is split into lines,
    because a scanner hands back a trailing newline and a zone that is
    merely padded is read rather than called unreadable.
    """
    try:
        return td3.validate_td3_lines(payload.strip().splitlines())[1]
    except MrzValueError:
        return None


def _payload_text(line_2, name):
    """The payload's own text for one TD3 line-2 field, its filler set aside."""
    return " ".join(_words(td3.td3_field(line_2, td3.TD3_LINE_2, name))) or None


def compare_to_barcode(ocr_fields, payload):
    """One finding per printed field the barcode payload disagrees with.

    :param ocr_fields: the record :func:`~app.pipeline.tier1.fields.normalise_fields`
        answered; shaped or as printed, this does not reshape it.
    :param payload: the decoded 2D barcode text, read as a TD3 zone.
    :returns: a tuple of :class:`~app.risk.flags.EvidenceFlag` in the table's
        printed order, empty where every field agreed or the payload could not
        be read as a TD3 zone at all.
    :raises ValueError: for a record or a payload that is not one of these.
    :raises fields.UnknownDocumentError: when the record names no table here.
    """
    if not isinstance(ocr_fields, fields.ExtractedFields):
        raise ValueError(
            f"ocr_fields must be an ExtractedFields, not {type(ocr_fields).__name__}"
        )
    if not isinstance(payload, str):
        raise ValueError(f"payload must be a str, not {type(payload).__name__}")
    rules = fields.FIELD_TABLES.get(ocr_fields.document_type)
    if rules is None:
        raise fields.UnknownDocumentError(
            f"document_type must be one of {', '.join(fields.FIELD_TABLES)}; "
            f"{ocr_fields.document_type!r} is not one."
        )
    line_2 = _payload_line(payload)
    if line_2 is None:
        return ()

    flags = []
    for rule in rules:
        name = BARCODE_FIELDS.get(rule.field)
        if name is None:
            continue
        printed = ocr_fields.values[rule.field]
        if printed is None:
            continue
        encoded = _payload_text(line_2, name)
        if encoded is None or _exact_agrees(rule, printed, encoded):
            continue
        flags.append(EvidenceFlag(
            id=flag_ids.OCR_BARCODE_MISMATCH,
            tier=1,
            label=_label(rule, _BARCODE_SOURCE),
            weight_band=BARCODE_MISMATCH_BAND,
            value=1.0,
            confidence=1.0,
            region=ocr_fields.regions.get(rule.field),
            expected=encoded,
            found=printed,
            reason=_barcode_reason(rule),
            source_module=SOURCE_MODULE,
            field=rule.field,
        ))
    return tuple(flags)
