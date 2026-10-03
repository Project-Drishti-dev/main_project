"""12.15 -- one finding per printed field that disagrees with the machine-readable zone.

The claim is the task's: alter one printed date and exactly one finding comes
back, pointing at that field.  :func:`tests.fixtures.document_images` prints
the TD3 specimen, :func:`app.pipeline.tier0.td3.parse_td3` reads the zone beside
it, and this file compares the two and holds the answer to the task's line.

**The engine below is a stub over ground truth, as 12.11's is.**  ``putText``
advances one glyph at a time with no kerning, so summing a row's word widths and
the spaces between them walks the x positions the drawing used.  Neither engine
is installed on this box, so nothing here has read real ink, and every finding
below is a disagreement between two readings of a page this file drew.

**The comparator is handed the shaped record and is not reshaped inside.**  12.13
is a separate call and stays one, so what the page printed stays on hand beside
what it was shaped into; a test says the two forms do not compare alike rather
than leaving the difference to be assumed away.
"""

import ast
import contextlib
import dataclasses
import pathlib
from types import MappingProxyType

import cv2
import numpy
import pytest

from app.pipeline.tier0 import mrz, td3
from app.pipeline.tier1 import barcode, fields, mismatch, ocr, runner
from app.risk import flag_ids
from app.risk.weightsets import loader
from tests.fixtures import document_images, mrz_images

PAGE = document_images.render_document()
CONFIDENT = 0.95
GROUND_TRUTH = "ground_truth"

#: The words that may differ between two names before they disagree.  Zero, so
#: that the tests below say what a name disagreement is rather than absorbing it.
TOLERANCE = 0

#: The zone the fixture's page belongs to, read by Tier 0's own parser.
MRZ = td3.parse_td3(mrz_images.SPECIMENS["TD3"])

#: The one printed value each of the four passport fields is altered to.  Each
#: differs from what the fixture prints in exactly one thing, so a comparator
#: that flags more than the field it was altered on is over-reaching.
ALTERED = {
    "name": "ERIKSSON ANNA MARIE",
    "passport_number": "L8989O2C",
    "date_of_birth": "13 AUG 1974",
    "date_of_expiry": "15 APR 2013",
}

#: The zone's own name as a page would print it, read off the parsed zone
#: rather than typed in beside it, so a change to the specimen cannot leave
#: 12.16's cases quietly agreeing with each other and nothing else.
ZONE_NAME = " ".join((MRZ.surname, *MRZ.given_names))

#: The same three words with a run of spaces between each pair instead of one.
#: How far apart a document prints its name is what varies and is never a
#: disagreement.
SPACED_NAME = "  ".join((MRZ.surname, *MRZ.given_names))

#: The same three words with an accent on one letter of each, written as
#: escapes: a source file's encoding is not this test's claim, and 12.16's own
#: diacritic test below says why the ink cannot carry these.
ACCENTED_NAME = "\u00c9RIKSSON \u00c1NNA MAR\u00cdA"

#: Each of the two above with its last word changed as well, which is what lets
#: the third test measure the differences rather than only watch them produce
#: nothing: a finding has to exist for its own count of agreeing words to be
#: read at all.
SPACED_AND_ONE_WORD_OFF = "  ".join((MRZ.surname, *MRZ.given_names[:-1], "MARIE"))
ACCENTED_AND_ONE_WORD_OFF = "\u00c9RIKSSON \u00c1NNA MARIE"


def words_of(box, text, page):
    """The words ``text`` was printed as in ``box``, each with the box it took."""
    left, top, _, bottom = box
    face = (page.font, page.font_scale, page.thickness)
    space = cv2.getTextSize(" ", *face)[0][0]
    parts, cursor = [], left
    for index, word in enumerate(text.split()):
        if index:
            cursor += space
        width = cv2.getTextSize(word, *face)[0][0]
        parts.append((word, (int(cursor), int(top), int(cursor + width), int(bottom))))
        cursor += width
    return parts


class GroundTruth(ocr.OcrEngine):
    """An engine reporting the words ``document_images`` printed, as it printed them."""

    def __init__(self, page):
        self.page = page

    def is_available(self):
        return True

    def read(self, image):
        words = []
        for field in self.page.fields:
            for text, box in words_of(field.label_box, field.label, self.page):
                words.append(ocr.OcrWord(text=text, bbox=box, confidence=CONFIDENT))
            for text, box in words_of(field.value_box, field.value, self.page):
                words.append(ocr.OcrWord(text=text, bbox=box, confidence=CONFIDENT))
        return ocr.OcrResult(words=tuple(words), mean_confidence=CONFIDENT)


def printed_of(page=PAGE):
    """The record 12.11 answered off ``page``, as the page printed it."""
    read = runner.run_tier1(page.image, engines={GROUND_TRUTH: GroundTruth(page)}).ocr
    return fields.extract_fields(read, fields.PASSPORT)


def shaped_of(page=PAGE, document_type=fields.PASSPORT):
    """The record 12.13 answered, which is the one 12.15 compares."""
    return fields.normalise_fields(printed_of(page))


def flagged(record, tolerance=TOLERANCE, mrz=MRZ):
    """What 12.15 answers for ``record`` against the zone ``mrz`` carries."""
    return mismatch.compare_to_mrz(record, mrz, tolerance)


def a_page(**values):
    """The fixture's page with ``values``' own printed text swapped in."""
    return document_images.render_document(values=values)


@contextlib.contextmanager
def _table_replaced(rule):
    """The passport table with ``rule`` added, and the real one put back after."""
    original = fields.FIELD_TABLES
    fields.FIELD_TABLES = MappingProxyType({
        **original,
        fields.PASSPORT: (rule, *original[fields.PASSPORT]),
    })
    try:
        yield
    finally:
        fields.FIELD_TABLES = original


@contextlib.contextmanager
def _rule_retyped(field_name, value_type):
    """The passport table with one field's rule carrying a different type."""
    original = fields.FIELD_TABLES
    fields.FIELD_TABLES = MappingProxyType({
        **original,
        fields.PASSPORT: tuple(
            fields.FieldRule(
                field=rule.field, anchors=rule.anchors, value=rule.value,
                value_type=value_type,
            ) if rule.field == field_name else rule
            for rule in original[fields.PASSPORT]
        ),
    })
    try:
        yield
    finally:
        fields.FIELD_TABLES = original


def a_record(**values):
    """A shaped record whose printed values are ``values``, the rest unaltered."""
    return fields.ExtractedFields(
        document_type=fields.PASSPORT,
        values=MappingProxyType({
            rule.field: values.get(rule.field, shaped_of().values[rule.field])
            for rule in fields.FIELD_TABLES[fields.PASSPORT]
        }),
        regions=shaped_of().regions,
    )


def printed_as(**values):
    """The record 12.13 answers for a page that printed ``values`` as printed.

    **Through the normaliser rather than around it**, which is the whole
    reason this is not :func:`a_record`: that helper hands over values already
    shaped, so a name still carrying its accents would reach 12.15 as it was
    written and be counted a differing word.  The unaltered fields come off the
    real page, so a record built here differs from the fixture in one field and
    agrees with it everywhere else.
    """
    return fields.normalise_fields(fields.ExtractedFields(
        document_type=fields.PASSPORT,
        values=MappingProxyType({
            rule.field: values.get(rule.field, printed_of().values[rule.field])
            for rule in fields.FIELD_TABLES[fields.PASSPORT]
        }),
        regions=printed_of().regions,
    ))


# --- the task: one printed field altered, exactly one finding ---


def test_altering_the_printed_date_of_birth_yields_exactly_one_mismatch_flag():
    """The task's own verification line, with the finding's whole claim on it."""
    page = a_page(date_of_birth=ALTERED["date_of_birth"])
    flags = flagged(shaped_of(page))

    assert len(flags) == 1
    assert flags[0].id == flag_ids.OCR_MRZ_MISMATCH
    assert flags[0].field == "date_of_birth"
    assert flags[0].tier == 1
    assert flags[0].expected == "740812"
    assert flags[0].found == "1974-08-13"


def test_the_finding_points_at_the_words_the_altered_value_was_read_from():
    """12.14's corners and no geometry of its own, on the field as printed."""
    page = a_page(date_of_birth=ALTERED["date_of_birth"])
    record = shaped_of(page)
    flag = flagged(record)[0]

    assert flag.region == record.regions["date_of_birth"]
    assert flag.region == shapes_of_words(page, "date_of_birth")
    assert flag.region != record.regions["name"]


def shapes_of_words(page, field_name):
    """The four corners the words of ``field_name``'s printed value took."""
    field = document_images.field_of(page, field_name)
    boxes = [box for _, box in words_of(field.value_box, field.value, page)]
    left, top = min(box[0] for box in boxes), min(box[1] for box in boxes)
    right, bottom = max(box[2] for box in boxes), max(box[3] for box in boxes)
    return ((left, top), (right, top), (right, bottom), (left, bottom))


def test_a_page_printed_exactly_as_the_zone_reads_it_owes_nobody_a_finding():
    assert flagged(shaped_of()) == ()


@pytest.mark.parametrize("field_name", sorted(ALTERED))
def test_altering_any_one_printed_field_yields_exactly_one_finding(field_name):
    """One field at a time, so a comparator that flagged two of them would fail."""
    page = a_page(**{field_name: ALTERED[field_name]})
    flags = flagged(shaped_of(page))

    assert [one.field for one in flags] == [field_name]


def test_altering_every_printed_field_at_once_yields_one_finding_for_each():
    """Four altered fields are four findings, and four and not five."""
    page = a_page(**ALTERED)
    flags = flagged(shaped_of(page))

    assert [one.field for one in flags] == [
        rule.field for rule in fields.FIELD_TABLES[fields.PASSPORT]
    ]


# --- both sides are shaped, and the zone's own filler is not part of a value ---


def test_the_record_compared_is_the_one_handed_over_and_not_reshaped_inside():
    """12.13 stays a separate call, so the printed form is what compares as printed."""
    assert [one.field for one in flagged(printed_of())] == [
        "date_of_birth", "date_of_expiry",
    ]
    assert flagged(shaped_of()) == ()


def test_a_number_the_zone_padded_with_filler_still_agrees_with_the_printed_one():
    """A TD3 prints its document number to nine places and the page to eight."""
    assert MRZ.document_number == "L898902C<"
    assert shaped_of().values["passport_number"] == "L898902C"
    assert flagged(shaped_of()) == ()


def test_the_zone_is_the_side_held_to_its_own_filler_on_every_field():
    """Filler is padding, so removing it is the only edit this module makes."""
    for rule in fields.FIELD_TABLES[fields.PASSPORT]:
        assert rule.field in mismatch.MRZ_FIELDS


# --- a name, and the transliteration tolerance that reaches only a name ---


def test_a_name_differing_in_one_word_disagrees_at_no_tolerance():
    flags = flagged(a_record(name=ALTERED["name"]))
    assert [one.field for one in flags] == ["name"]
    assert flags[0].found == "2 agree"


def test_one_differing_word_is_within_a_tolerance_of_one():
    assert flagged(a_record(name=ALTERED["name"]), tolerance=1) == ()


def test_a_name_differing_in_a_second_word_is_outside_a_tolerance_of_one():
    flags = flagged(a_record(name="ERIKSSON ANNA MARIE ERIKSSON"), tolerance=1)
    assert [one.field for one in flags] == ["name"]


# --- 12.16: spacing and diacritics are the page's, not a disagreement ---


def test_a_name_printed_with_its_spacing_altered_owes_nobody_a_finding():
    """The words are what the zone is compared with, and the spacing is not a word.

    **Drawn rather than built**, and this is the one of the two differences
    ``cv2.putText`` can actually put on paper: spaces are in the Hershey face,
    so the page below carries the run of spaces it says it does and the value
    reaches 12.15 read off real ink.  12.13 does nothing to the spacing here
    — transliteration is not what is being relied on.
    """
    page = a_page(name=SPACED_NAME)
    assert "  " in document_images.field_of(page, "name").value
    record = shaped_of(page)
    assert record.values["name"] == ZONE_NAME
    assert flagged(record) == ()


def test_a_name_printed_with_diacritics_owes_nobody_a_finding():
    """An accented spelling of a name is the name the zone spells without accents.

    **Built as a record and not drawn, and the reason is the ink**: the Hershey
    face has no glyph for an accented letter and ``putText`` prints a question
    mark in its place, so a page claiming to carry this name would be a page
    whose image says something other than the words the engine reports off it.
    Going through :func:`printed_as` is what makes the claim one about the
    whole path: 12.13 removes the accent, and 12.15 is handed the words the
    zone already carries.
    """
    record = printed_as(name=ACCENTED_NAME)
    assert record.values["name"] == ZONE_NAME
    assert flagged(record) == ()


def test_neither_difference_costs_a_word():
    """Both are spent before the words are counted, so no tolerance agrees them.

    **The count on a finding is what this holds, and not an absence of
    findings**: with one real word changed as well, a name carrying a run of
    spaces or an accent still loses exactly one word, so the finding reads
    ``2 agree`` and a tolerance of one covers it where a tolerance of none does
    not.  An absence of findings on its own would be satisfied by a comparator
    that never flagged anything, and would not notice a tolerance that had
    stopped reaching a name altogether.
    """
    for printed in (SPACED_AND_ONE_WORD_OFF, ACCENTED_AND_ONE_WORD_OFF):
        record = printed_as(name=printed)
        assert [one.field for one in flagged(record)] == ["name"]
        assert flagged(record)[0].found == "2 agree"
        assert flagged(record, tolerance=1) == ()


def test_the_tolerance_reaches_a_name_and_nothing_else():
    """A digit is a digit: no tolerance buys a date that is one day out."""
    page = a_page(date_of_birth=ALTERED["date_of_birth"])
    assert [one.field for one in flagged(shaped_of(page), tolerance=3)] == [
        "date_of_birth"
    ]


def test_a_name_carrying_neither_side_as_words_is_a_disagreement_and_not_a_crash():
    assert [one.field for one in flagged(a_record(name="<>"))] == ["name"]


# --- a value nothing could read is the one most worth comparing ---


@pytest.mark.parametrize("printed", ("12 AUC 1974", "12 AUG.", "not a date"))
def test_a_date_no_pattern_could_read_still_disagrees_rather_than_being_dropped(printed):
    """D89's rule, paid here: the malformed value is what a forgery leaves behind."""
    flags = flagged(a_record(date_of_birth=printed))

    assert [one.field for one in flags] == ["date_of_birth"]
    assert flags[0].found == printed


# --- what a finding carries, and what it may never carry ---


def test_a_finding_carries_no_part_of_the_holders_name():
    """D6's rule: a flag is not a place identity data is stored."""
    flag = flagged(a_record(name="ERIKSSON ANNA MARIE"))[0]

    for half in (flag.expected, flag.found, flag.label, flag.reason):
        assert "ERIKSSON" not in half
        assert "ANNA" not in half
        assert "MARIE" not in half


def test_a_names_two_halves_are_counts_of_words_and_not_the_words_themselves():
    flag = flagged(a_record(name=ALTERED["name"]))[0]

    assert flag.expected == "3 name words"
    assert flag.found == "2 agree"


def test_a_date_and_a_number_carry_the_two_values_that_were_compared():
    """Short values, which is what ``expected`` and ``found`` are for."""
    found = {
        one.field: (one.expected, one.found) for one in flagged(a_record(
            date_of_birth="1974-08-13", passport_number="L8989O2C",
        ))
    }

    assert found["date_of_birth"] == ("740812", "1974-08-13")
    assert found["passport_number"] == ("L898902C", "L8989O2C")


def test_every_finding_is_certain_because_both_sides_were_read_and_not_inferred():
    flag = flagged(a_record(date_of_birth=ALTERED["date_of_birth"]))[0]

    assert (flag.value, flag.confidence) == (1.0, 1.0)


def test_every_finding_names_the_module_that_produced_it_and_the_field_it_is_about():
    flag = flagged(a_record(date_of_birth=ALTERED["date_of_birth"]))[0]

    assert mismatch.SOURCE_MODULE == flag.source_module == (
        "app.pipeline.tier1.mismatch"
    )
    assert flag.field == "date_of_birth"
    assert "date of birth" in flag.label


def test_the_id_emitted_is_one_the_flag_ids_and_the_weightset_both_hold():
    flag = flagged(a_record(date_of_birth=ALTERED["date_of_birth"]))[0]

    assert flag.id in flag_ids.FLAG_IDS
    assert flag.id in loader.load_weightset().flags


def test_the_band_this_module_states_is_the_one_the_weightset_holds():
    row = loader.load_weightset().flags[flag_ids.OCR_MRZ_MISMATCH]
    flag = flagged(a_record(date_of_birth=ALTERED["date_of_birth"]))[0]

    assert row["band"] == mismatch.MISMATCH_BAND == flag.weight_band


# --- what is not a disagreement ---


def test_a_field_the_page_never_printed_is_absent_and_not_a_finding():
    """An unreadable field has nothing to disagree with; 12.10 owes a different id."""
    record = fields.ExtractedFields(
        document_type=fields.PASSPORT,
        values=MappingProxyType({
            **shaped_of().values, "passport_number": None,
        }),
        regions=shaped_of().regions,
    )
    assert flagged(record) == ()


def test_a_zone_carrying_no_name_is_an_absence_and_not_a_disagreement():
    """A TD1's name sits on line 3, which 3.7 has not read yet; that is not a forgery."""
    unread_name = dataclasses.replace(MRZ, surname=None, given_names=())

    assert [one.field for one in flagged(
        a_record(name="ERIKSSON ANNA MARIE"), mrz=unread_name,
    )] == []
    assert [one.field for one in flagged(
        a_record(date_of_birth=ALTERED["date_of_birth"]), mrz=unread_name,
    )] == ["date_of_birth"]


def test_only_the_two_year_digits_the_zone_prints_are_compared_and_no_century_invented():
    """3.12 left the century open and infer_birth_year is what closes it."""
    assert flagged(a_record(date_of_birth="1874-08-12")) == ()
    assert [one.field for one in flagged(a_record(date_of_birth="1904-08-12"))] == [
        "date_of_birth"
    ]


# --- the table this walks, and the refusals ---


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_every_field_every_table_names_has_a_mrz_field_to_agree_with(document_type):
    """A field with no mapping is a claim no caller downstream could keep."""
    named = {rule.field for rule in fields.FIELD_TABLES[document_type]}
    assert named <= set(mismatch.MRZ_FIELDS)


def test_a_caller_cannot_add_a_mrz_field_to_the_mapping():
    with pytest.raises(TypeError):
        mismatch.MRZ_FIELDS["sex"] = ("sex",)


@pytest.mark.parametrize(
    "record", (None, "L898902C", {}, 7), ids=lambda one: type(one).__name__
)
def test_a_record_that_is_not_an_extracted_fields_is_refused(record):
    with pytest.raises(ValueError):
        flagged(record)


@pytest.mark.parametrize(
    "zone", (None, ("P<UTOERIKSSON", "L898902C"), "P<UTO"), ids=lambda one: type(one).__name__
)
def test_a_zone_that_is_not_a_mrz_document_is_refused(zone):
    with pytest.raises(ValueError):
        mismatch.compare_to_mrz(shaped_of(), zone, TOLERANCE)


@pytest.mark.parametrize("tolerance", (-1, 0.5, "1", None, True), ids=repr)
def test_a_tolerance_that_is_not_a_whole_count_is_refused(tolerance):
    with pytest.raises(ValueError):
        mismatch.compare_to_mrz(shaped_of(), MRZ, tolerance)


def test_a_record_whose_document_type_no_table_holds_is_refused():
    record = fields.ExtractedFields(
        document_type="driving licence",
        values=shaped_of().values,
        regions=shaped_of().regions,
    )
    with pytest.raises(fields.UnknownDocumentError):
        flagged(record)


def test_a_value_type_no_comparison_here_holds_is_a_refusal_and_not_a_agreement():
    """A type 12.13 refuses is refused here too, rather than passing as agreed."""
    rule = fields.FIELD_TABLES[fields.PASSPORT][0]
    with _table_replaced(fields.FieldRule(
        field=rule.field,
        anchors=rule.anchors,
        value=rule.value,
        value_type="height",
    )):
        record = fields.ExtractedFields(
            document_type=fields.PASSPORT,
            values=MappingProxyType({rule.field: "TALL"}),
            regions=MappingProxyType({rule.field: None}),
        )
        with pytest.raises(ValueError, match="height"):
            flagged(record)


def test_a_field_no_mrz_mapping_names_is_a_refusal_and_not_a_silent_skip():
    """Checked before anything is emitted, so a partial answer is never returned."""
    rule = fields.FIELD_TABLES[fields.PASSPORT][0]
    with _table_replaced(fields.FieldRule(
        field="issue_place",
        anchors=rule.anchors,
        value=rule.value,
        value_type=rule.value_type,
    )):
        record = fields.ExtractedFields(
            document_type=fields.PASSPORT,
            values=MappingProxyType({"issue_place": "DELHI"}),
            regions=MappingProxyType({"issue_place": None}),
        )
        with pytest.raises(ValueError, match="issue_place"):
            flagged(record)


# --- what this module is allowed to reach for ---


def _tree():
    """This module's own syntax tree, walked rather than its text matched."""
    return ast.parse(pathlib.Path(mismatch.__file__).read_text(encoding="utf-8"))


def test_this_module_is_where_tier_one_first_holds_finding_vocabulary():
    """The two modules above it hold none, and this one is the first to import it."""
    imported = {
        node.module for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name for node in ast.walk(_tree())
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert {"app.risk", "app.risk.flags"} <= imported
    assert not any(one.split(".")[0] == "logging" for one in imported)


def test_this_module_holds_no_geometry_and_hands_the_record_s_own_region_over():
    source = pathlib.Path(mismatch.__file__).read_text(encoding="utf-8")
    assert "cv2" not in source
    assert "bbox" not in source
    assert "region=ocr_fields.regions" in source


def test_the_field_mapping_is_read_only_and_named_outside_the_comparison():
    assert mismatch.MRZ_FIELDS["name"] == ("surname", "given_names")
    assert mismatch.MRZ_FIELDS["passport_number"] == ("document_number",)
    with pytest.raises(TypeError):
        del mismatch.MRZ_FIELDS["name"]


# --- 13.3: the barcode payload against the field printed beside it ---

#: The zone's own two lines, so a payload is the same zone with a field moved
#: rather than a string written out beside it.
ZONE_LINE_1, ZONE_LINE_2 = mrz_images.SPECIMENS["TD3"]

#: Where in line 2 each field a barcode carries sits, zero-indexed and
#: half-open, and where the digit printed over it sits.  **Splicing is not
#: reading**: these are the fixture's own numbers, so a change to the specimen
#: cannot leave a payload quietly agreeing with the page it was built to differ
#: from, which is 12.16's lesson held a second time.
BARCODE_SPANS = {
    "passport_number": (0, 9),
    "date_of_birth": (13, 19),
    "date_of_expiry": (21, 27),
}
BARCODE_DIGITS = {"passport_number": 9, "date_of_birth": 19, "date_of_expiry": 27}

#: The one value each field a barcode carries is moved to inside the payload.
#: Each differs from the specimen's in every digit, so a payload agreeing on two
#: of the three fields would say which one was compared.
MOVED_IN_QR = {
    "passport_number": "X999999X",
    "date_of_birth": "130819",
    "date_of_expiry": "150420",
}

#: How many pixels each module of a QR is drawn at, for the two tests that read
#: one off a frame rather than naming its payload.
QR_SCALE = 4

needs_binding = pytest.mark.skipif(
    barcode.import_zxingcpp() is None, reason="zxing-cpp is not installed"
)


def _composite_span(line_2):
    """The characters a TD3 composite digit is computed over."""
    return line_2[0:10] + line_2[13:20] + line_2[21:43]


def a_payload(**swapped):
    """A TD3 payload over the zone's own characters, with ``swapped`` moved.

    Every printed digit that covers a moved field is recomputed, and so is the
    composite, so the payload is a zone Tier 0 would accept rather than a
    string shaped like one.  :func:`test_every_payload_this_builds_is_a_zone_
    tier_zero_would_accept` holds the fixture to that.
    """
    line_2 = ZONE_LINE_2
    for field, value in swapped.items():
        start, end = BARCODE_SPANS[field]
        line_2 = line_2[:start] + value.ljust(end - start, mrz.FILLER) + line_2[end:]
        digit = BARCODE_DIGITS[field]
        line_2 = line_2[:digit] + str(mrz.check_digit(line_2[start:digit])) + line_2[digit + 1:]
    composite = mrz.check_digit(_composite_span(line_2))
    return f"{ZONE_LINE_1}\n{line_2[:43]}{composite}{line_2[44:]}"


def decoded_from(payload):
    """What 13.1's decoder reads off a QR carrying ``payload``."""
    binding = barcode.import_zxingcpp()
    frame = numpy.ascontiguousarray(numpy.asarray(
        binding.write_barcode_to_image(
            binding.create_barcode(payload, binding.QRCode), QR_SCALE,
        )
    ))
    found = barcode.ZXING_DECODER.read(frame)
    assert len(found) == 1, "the fixture drew one barcode and read another number"
    return found[0].text


def barred(record, payload):
    """What 13.3 answers for ``record`` against the barcode carrying ``payload``."""
    return mismatch.compare_to_barcode(record, payload)


@needs_binding
def test_a_qr_carrying_another_number_yields_exactly_one_barcode_flag():
    """13.3's own verification line, with the finding's whole claim on it."""
    record = a_record()
    moved = MOVED_IN_QR["passport_number"]
    flags = barred(record, decoded_from(a_payload(passport_number=moved)))

    assert len(flags) == 1
    assert flags[0].id == flag_ids.OCR_BARCODE_MISMATCH
    assert flags[0].field == "passport_number"
    assert flags[0].tier == 1
    assert flags[0].expected == moved
    assert flags[0].found == record.values["passport_number"]


@needs_binding
def test_a_qr_carrying_what_the_page_prints_owes_nobody_a_finding():
    """The agreeing half of the round trip, so the test above is a disagreement."""
    assert barred(shaped_of(), decoded_from(a_payload())) == ()


def test_a_payload_that_agrees_with_the_page_and_not_the_zone_owes_nobody_a_finding():
    """12.15 and 13.3 can disagree, which is the only way either is worth running."""
    moved = MOVED_IN_QR["passport_number"]
    record = a_record()
    zone = dataclasses.replace(MRZ, document_number=moved)

    assert barred(record, a_payload()) == ()
    assert [one.field for one in flagged(record, mrz=zone)] == ["passport_number"]


def test_the_finding_points_at_the_words_the_mismatched_value_was_read_from():
    """13.14's corners and no geometry of its own, on the field as printed."""
    record = shaped_of()
    flags = barred(record, a_payload(passport_number=MOVED_IN_QR["passport_number"]))

    assert flags[0].region == record.regions["passport_number"]
    assert flags[0].region != record.regions["name"]


@pytest.mark.parametrize("field_name", sorted(MOVED_IN_QR))
def test_moving_any_one_field_inside_the_payload_yields_exactly_one_finding(field_name):
    """One field at a time, so a comparator reading two of them would fail."""
    flags = barred(
        shaped_of(), a_payload(**{field_name: MOVED_IN_QR[field_name]})
    )

    assert [one.field for one in flags] == [field_name]


def test_moving_every_carried_field_at_once_yields_one_finding_for_each():
    """Three fields are three findings, and three and not four: a name is not one."""
    flags = barred(shaped_of(), a_payload(**MOVED_IN_QR))

    assert [one.field for one in flags] == sorted(MOVED_IN_QR, key=list(
        rule.field for rule in fields.FIELD_TABLES[fields.PASSPORT]
    ).index)


def test_the_record_compared_is_the_one_handed_over_and_not_reshaped_inside():
    """12.13 stays one call, so a record read as printed reaches this as printed."""
    payload = a_payload()

    assert [one.field for one in barred(printed_of(), payload)] == [
        "date_of_birth", "date_of_expiry",
    ]
    assert barred(shaped_of(), payload) == ()


def test_a_payload_wearing_its_own_edges_is_still_read_rather_than_called_unreadable():
    """A scanner hands back a trailing newline, and that is not a bad zone."""
    padded = f"\n{a_payload()}\n"
    moved = f"\n{a_payload(passport_number=MOVED_IN_QR['passport_number'])}\n"

    assert barred(shaped_of(), padded) == ()
    assert [one.field for one in barred(shaped_of(), moved)] == ["passport_number"]


def test_only_the_two_year_digits_the_payload_prints_are_compared_and_no_century_invented():
    payload = a_payload()

    assert barred(a_record(date_of_birth="1874-08-12"), payload) == ()
    assert [one.field for one in barred(
        a_record(date_of_birth="1904-08-12"), payload,
    )] == ["date_of_birth"]


# --- what a barcode finding carries, and what it may never carry ---


def test_the_id_and_the_band_emitted_are_the_ones_flag_ids_and_the_weightset_hold():
    row = loader.load_weightset().flags[flag_ids.OCR_BARCODE_MISMATCH]
    flag = barred(
        a_record(), a_payload(passport_number=MOVED_IN_QR["passport_number"])
    )[0]

    assert flag.id in flag_ids.FLAG_IDS
    assert row["band"] == mismatch.BARCODE_MISMATCH_BAND == flag.weight_band


def test_a_barcode_finding_names_the_module_that_produced_it_and_not_the_zone():
    flag = barred(
        a_record(), a_payload(passport_number=MOVED_IN_QR["passport_number"])
    )[0]

    assert flag.source_module == mismatch.SOURCE_MODULE
    assert "barcode" in flag.label
    assert "machine-readable zone" not in flag.label
    assert "barcode" in flag.reason


def test_a_barcode_finding_carries_no_part_of_the_holders_name():
    """`D6` again, and here it is load-bearing: line 1 of the payload carries it."""
    flag = barred(
        a_record(), a_payload(passport_number=MOVED_IN_QR["passport_number"])
    )[0]

    for half in (flag.expected, flag.found, flag.label, flag.reason):
        for word in ZONE_NAME.split():
            assert word not in half


def test_a_barcode_finding_is_certain_because_both_sides_were_read():
    flag = barred(
        a_record(), a_payload(passport_number=MOVED_IN_QR["passport_number"])
    )[0]

    assert (flag.value, flag.confidence) == (1.0, 1.0)


# --- what is not a disagreement ---


@pytest.mark.parametrize(
    "payload", ("", "hello", "L898902C", "x" * 88), ids=("", "word", "line", "one-line")
)
def test_a_payload_this_cannot_read_as_a_zone_is_an_absence_and_not_a_disagreement(payload):
    """Naming what an unreadable payload disagrees with would invent the half."""
    assert barred(a_record(), payload) == ()


def test_a_field_the_page_never_printed_is_absence_and_not_a_finding():
    """Nothing was printed, so nothing disagrees; 12.10 owes a different id."""
    record = fields.ExtractedFields(
        document_type=fields.PASSPORT,
        values=MappingProxyType({**shaped_of().values, "passport_number": None}),
        regions=shaped_of().regions,
    )

    assert barred(record, a_payload(passport_number=MOVED_IN_QR["passport_number"])) == ()


def test_every_payload_this_builds_is_a_zone_tier_zero_would_accept():
    """The fixture splices a zone, so its own printed digits have to hold."""
    for swapped in ({}, *({field: moved} for field, moved in MOVED_IN_QR.items())):
        line_2 = a_payload(**swapped).splitlines()[1]

        for field, (start, _) in BARCODE_SPANS.items():
            digit = BARCODE_DIGITS[field]
            assert mrz.verify_check_digit(line_2[start:digit], line_2[digit])
        assert mrz.verify_check_digit(_composite_span(line_2), line_2[43])


# --- the table this reads, and the refusals ---


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_every_number_field_every_table_names_is_one_the_payload_carries(document_type):
    named = {rule.field for rule in fields.FIELD_TABLES[document_type]}
    assert {one for one in named if one.endswith("number")} <= set(mismatch.BARCODE_FIELDS)


def test_the_barcode_mapping_is_read_only_and_names_no_field_a_payload_cannot_carry():
    assert mismatch.BARCODE_FIELDS["passport_number"] == "document_number"
    assert "name" not in mismatch.BARCODE_FIELDS
    with pytest.raises(TypeError):
        mismatch.BARCODE_FIELDS["name"] = "name"


@pytest.mark.parametrize(
    "record", (None, "L898902C", {}, 7), ids=lambda one: type(one).__name__
)
def test_a_record_that_is_not_an_extracted_fields_is_refused(record):
    with pytest.raises(ValueError):
        barred(record, a_payload())


@pytest.mark.parametrize(
    "payload", (None, 7, ["a"], b"L898902C"), ids=lambda one: type(one).__name__
)
def test_a_payload_that_is_not_text_is_refused(payload):
    with pytest.raises(ValueError):
        barred(a_record(), payload)


def test_a_record_whose_document_type_no_table_holds_is_refused():
    record = fields.ExtractedFields(
        document_type="boarding_pass",
        values=shaped_of().values,
        regions=shaped_of().regions,
    )
    with pytest.raises(fields.UnknownDocumentError):
        barred(record, a_payload())


def test_a_value_type_no_exact_comparison_holds_is_a_refusal_and_not_an_agreement():
    """A type 13.3 refuses is refused rather than passing as an agreement."""
    with _rule_retyped("passport_number", "height"):
        with pytest.raises(ValueError, match="height"):
            barred(a_record(), a_payload())
