"""12.11 -- the per-document-type anchor table, and what it reads off the page.

The claim is the task's: a printed label finds its field, and the text beside
that label is the field's value.  :func:`tests.fixtures.document_images`
prints four labelled rows, this file reads them back, and the first test says
all four come out as the fixture printed them.

**The engine below reports the words the fixture drew, from the fixture's own
boxes.**  Neither Tesseract nor EasyOCR is installed here, so this read is a
stub -- but it is a stub over ground truth rather than over a hand-written
answer: ``putText`` advances one glyph at a time with no kerning, so summing
the widths of a line's words and the spaces between them walks the x positions
the drawing used.  **Every box the stub reports is checked against the ink**,
so a word it claims to have read cannot be one nothing was printed in.

**A visa and a national ID are two more tables and no second mechanism.**  Their
pages are drawn from rows this file states, and each new table is held to its
own page by the same two tests 12.11 used: the anchor round-trip and the print
order.  A table a page cannot be read by is a claim about a document nobody has.

**A value is answered even when it matches no pattern.**  12.15 compares a
printed field against the MRZ field it must agree with, and a forged value is
often malformed; a table that dropped what it could not match would leave that
comparison with nothing to disagree with.  The tests below hold both halves of
that -- the pattern trims a row to the value, and a row the pattern cannot read
still answers whole.
"""

import ast
import dataclasses
import pathlib

import cv2
import pytest

from app.pipeline.tier0 import td3
from app.pipeline.tier1 import fields, ocr, runner
from app.risk.flags import EvidenceFlag, FlagValueError
from tests.fixtures import document_images

PAGE = document_images.render_document()
CONFIDENT = 0.95
GROUND_TRUTH = "ground_truth"

PASSPORT = fields.PASSPORT
VALUE_OF = {field.name: field.value for field in PAGE.fields}

#: Every anchor spelling the table lists, against the field it belongs to.  A
#: spelling nothing locates is a claim the table cannot keep, so each is read
#: back off a page printed with it.
ANCHOR_CASES = [
    (rule.field, anchor)
    for rule in fields.FIELD_TABLES[PASSPORT]
    for anchor in rule.anchors
]


def rule_of(field, document_type=PASSPORT):
    """The rule ``document_type``'s table holds for ``field``."""
    for rule in fields.FIELD_TABLES[document_type]:
        if rule.field == field:
            return rule
    raise KeyError(f"the {document_type} table names no field {field!r}")


def words_of(box, text, page=PAGE):
    """The words ``text`` was printed as in ``box``, each with the box it took."""
    left, top, _, bottom = box
    face = (page.font, page.font_scale, page.thickness)
    space = cv2.getTextSize(" ", *face)[0][0]
    parts = []
    cursor = left
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


def read_of(page=PAGE):
    """What 12.11 consumes: the words ``run_tier1`` hands back for ``page``."""
    return runner.run_tier1(page.image, engines={GROUND_TRUTH: GroundTruth(page)}).ocr


def extracted(page=PAGE, document_type=PASSPORT):
    return fields.extract_fields(read_of(page), document_type)


def values_of(page=PAGE, document_type=PASSPORT):
    return dict(extracted(page, document_type).values)


# --- the task: four labelled rows in, four printed values out ---


def test_all_four_fields_are_extracted_off_the_fixture_page():
    assert values_of() == VALUE_OF
    assert len(VALUE_OF) == 4


@pytest.mark.parametrize("field_name", sorted(VALUE_OF))
def test_each_field_is_found_by_the_label_the_fixture_printed_it_under(field_name):
    """One field at a time, so a table that found three names one of them."""
    assert values_of()[field_name] == VALUE_OF[field_name]


@pytest.mark.parametrize(
    "field_name,anchor", ANCHOR_CASES, ids=[f"{name} as {anchor!r}" for name, anchor in ANCHOR_CASES]
)
def test_every_anchor_the_table_lists_locates_its_own_field(field_name, anchor):
    """An anchor spelling nothing locates is a claim the table cannot keep."""
    page = document_images.draw_document(tuple(
        (field.name, anchor if field.name == field_name else field.label, field.value)
        for field in PAGE.fields
    ))
    assert values_of(page)[field_name] == VALUE_OF[field_name]


def test_the_table_names_exactly_the_fields_the_fixture_prints_in_print_order():
    """So a field added to the specimen without a table entry fails here."""
    assert [rule.field for rule in fields.FIELD_TABLES[PASSPORT]] == list(VALUE_OF)


# --- 12.12: a visa and a national ID, one table each and no second mechanism ---

#: The rows each of the two new tables is held to, as ``(name, label, value)``
#: triples in print order.  Drawn with
#: :func:`tests.fixtures.document_images.draw_document` rather than read off the
#: fixture's own specimen: that fixture prints one document, and 12.12 adds two
#: tables rather than a second specimen page.
NEW_ROWS = {
    fields.VISA: (
        ("name", "Name", "ERIKSSON ANNA MARIA"),
        ("visa_number", "Visa No", "V898902C"),
        ("date_of_birth", "Date of birth", "12 AUG 1974"),
        ("date_of_expiry", "Valid until", "15 APR 2012"),
    ),
    fields.NATIONAL_ID: (
        ("name", "Name", "ERIKSSON ANNA MARIA"),
        ("national_id_number", "ID No", "482901345612"),
        ("date_of_birth", "Date of birth", "12 AUG 1974"),
        ("date_of_expiry", "Date of expiry", "15 APR 2012"),
    ),
}

#: Every anchor the two new tables list, against the type and field it is for.
NEW_ANCHOR_CASES = [
    (document_type, rule.field, anchor)
    for document_type, rows in NEW_ROWS.items()
    for rule in fields.FIELD_TABLES[document_type]
    for anchor in rule.anchors
]


def new_page(document_type, anchors=()):
    """The document ``document_type`` printed with, one field under another anchor."""
    swapped = dict(anchors)
    return document_images.draw_document(tuple(
        (name, swapped.get(name, label), value)
        for name, label, value in NEW_ROWS[document_type]
    ))


def new_values(document_type):
    """What 12.11's own call answers for a visa or a national ID page."""
    return values_of(new_page(document_type), document_type)


def printed_of(document_type):
    """The values ``document_type``'s page was printed with."""
    return {name: value for name, _, value in NEW_ROWS[document_type]}


@pytest.mark.parametrize("document_type", sorted(NEW_ROWS))
def test_a_new_table_reads_back_every_field_its_page_prints(document_type):
    """12.12's claim, once per table: the same call over a different read."""
    assert new_values(document_type) == printed_of(document_type)
    assert len(printed_of(document_type)) == 4


@pytest.mark.parametrize(
    "document_type,field_name,anchor", NEW_ANCHOR_CASES,
    ids=[f"{one} {name} as {anchor!r}" for one, name, anchor in NEW_ANCHOR_CASES],
)
def test_every_anchor_a_new_table_lists_locates_its_own_field(
    document_type, field_name, anchor
):
    """A spelling nothing locates is a claim the new tables cannot keep either."""
    page = new_page(document_type, ((field_name, anchor),))
    assert values_of(page, document_type)[field_name] == printed_of(document_type)[field_name]


@pytest.mark.parametrize("document_type", sorted(NEW_ROWS))
def test_a_new_table_names_exactly_the_fields_its_page_prints_in_print_order(document_type):
    """The same hold 12.11 has on the passport, over the two pages added here."""
    assert [rule.field for rule in fields.FIELD_TABLES[document_type]] == [
        name for name, _, _ in NEW_ROWS[document_type]
    ]


def test_a_national_id_number_is_answered_whole_where_a_passport_band_would_cut_it():
    """So the wider band is load-bearing rather than a second copy of the first."""
    number = printed_of(fields.NATIONAL_ID)["national_id_number"]
    assert len(number) == 12
    wider = rule_of("national_id_number", fields.NATIONAL_ID).value
    assert wider.search(number).group(0) == number
    # The passport's own band cannot read a twelve-character number whole, so
    # this pattern of its own is what stops 12.15 comparing nine digits of it.
    assert rule_of("passport_number").value.search(number) is None


def test_a_number_longer_than_its_own_band_is_answered_whole_and_not_cut_to_the_band():
    """The band's upper edge, and the module's own rule: a pattern that cannot
    read the whole of a value answers all of it, so 12.15 is handed a number
    that was printed rather than fourteen characters of one that was not."""
    too_long = "48290134561278901234"
    pattern = rule_of("national_id_number", fields.NATIONAL_ID).value
    assert pattern.search(too_long) is None
    page = document_images.draw_document(tuple(
        (name, label, too_long if name == "national_id_number" else value)
        for name, label, value in NEW_ROWS[fields.NATIONAL_ID]
    ))
    assert values_of(page, fields.NATIONAL_ID)["national_id_number"] == too_long


def test_a_visa_number_longer_than_the_shared_band_is_answered_whole_too():
    """The same rule on the band 12.11 already had, now reachable from a visa."""
    too_long = "V898902C1234567890"
    pattern = rule_of("visa_number", fields.VISA).value
    assert pattern.search(too_long) is None
    page = document_images.draw_document(tuple(
        (name, label, too_long if name == "visa_number" else value)
        for name, label, value in NEW_ROWS[fields.VISA]
    ))
    assert values_of(page, fields.VISA)["visa_number"] == too_long


def test_the_three_tables_name_three_different_numbers():
    """Two more tables, and neither a copy of the passport's nor of the other's."""
    numbers = {
        rule.field
        for rules in fields.FIELD_TABLES.values()
        for rule in rules
        if rule.field.endswith("_number")
    }
    assert numbers == {"passport_number", "visa_number", "national_id_number"}


@pytest.mark.parametrize("document_type", [fields.VISA, fields.NATIONAL_ID])
def test_the_passport_table_reads_no_number_off_the_other_two_pages(document_type):
    """No fallback and no shared table, on the page a fallback would have to guess."""
    assert values_of(new_page(document_type), fields.PASSPORT)["passport_number"] is None


# --- the value is what sits beside the label, and the label is not part of it ---


def test_a_value_is_what_sits_beside_its_anchor_rather_than_the_whole_row():
    """Reading the row would answer "N" for the name, so this is the difference."""
    name = VALUE_OF["name"]
    assert rule_of("name").value.search(f"Name  {name}").group(0) != name
    assert values_of()["name"] == name


def test_no_field_carries_its_own_label_into_its_value():
    for field in PAGE.fields:
        assert field.label not in values_of()[field.name]


def test_the_pattern_picks_the_value_out_of_text_printed_beside_it():
    """A row carrying more than the value is trimmed to the value's own shape."""
    page = document_images.render_document(values={"date_of_birth": "12 AUG 1974 (COPY)"})
    assert values_of(page)["date_of_birth"] == "12 AUG 1974"


def test_a_value_matching_no_pattern_is_still_answered_rather_than_dropped():
    """12.15 needs something to disagree with, and a forgery is often malformed."""
    page = document_images.render_document(values={"date_of_birth": "NOT A DATE"})
    assert values_of(page)["date_of_birth"] == "NOT A DATE"


# --- absence is a value here too, and it is not an error ---


def test_a_field_the_page_never_printed_is_answered_none():
    page = document_images.draw_document(tuple(
        (field.name, field.label, field.value)
        for field in PAGE.fields if field.name != "passport_number"
    ))
    assert values_of(page)["passport_number"] is None


def test_a_label_printed_with_nothing_beside_it_is_answered_none():
    page = document_images.render_document(values={"date_of_expiry": ""})
    assert values_of(page)["date_of_expiry"] is None


def test_a_page_no_engine_could_read_answers_no_values_and_refuses_nothing():
    """12.6's degrade reaches 12.11 as four absent fields rather than an error."""
    unread = runner.run_tier1(PAGE.image, engines={}).ocr
    assert unread is ocr.NO_WORDS
    assert set(fields.extract_fields(unread, PASSPORT).values.values()) == {None}


@pytest.mark.parametrize("label", ["PASSPORT NO", "Passport  No.", "Passport No :"])
def test_a_label_read_in_another_case_or_spacing_still_locates_its_field(label):
    """So an engine's own spelling of a label is not a second label to fail on."""
    page = document_images.draw_document(tuple(
        (field.name, label if field.name == "passport_number" else field.label, field.value)
        for field in PAGE.fields
    ))
    assert values_of(page)["passport_number"] == VALUE_OF["passport_number"]


def test_a_label_whose_own_words_are_far_apart_is_not_read_as_the_anchor():
    """So the adjacency constant is doing work the printed page cannot show.

    Two words a form prints side by side, and the same three words spread across
    a row, are not one label -- and the spread pair is the only way to tell an
    adjacency rule from no rule at all on a page this project prints.
    """
    top, bottom, height = 60, 88, 400
    spread = tuple(
        ocr.OcrWord(text=text, bbox=(60 + height * index, top, 60 + height * index + 100, bottom),
                    confidence=CONFIDENT)
        for index, text in enumerate(("Date", "of", "birth"))
    )
    value = (ocr.OcrWord(text="12 AUG 1974", bbox=(60 + 3 * height, top, 60 + 4 * height, bottom),
                         confidence=CONFIDENT),)
    read = ocr.OcrResult(words=spread + value, mean_confidence=CONFIDENT)
    assert fields.extract_fields(read, PASSPORT).values["date_of_birth"] is None


# --- the read is rebuilt, not trusted ---


def test_words_are_regrouped_into_rows_rather_than_trusted_as_they_arrive():
    """Nothing in an OcrResult promises reading order, and one that did is a promise to keep."""
    read = read_of()
    shuffled = ocr.OcrResult(
        words=tuple(reversed(read.words)), mean_confidence=read.mean_confidence
    )
    assert dict(fields.extract_fields(shuffled, PASSPORT).values) == VALUE_OF


def test_a_value_printed_on_another_row_is_not_taken_as_this_field_s_value():
    """So that grouping words into rows is load-bearing and not decoration."""
    step = PAGE.fields[1].label_box[1] - PAGE.fields[0].label_box[1]
    printed = VALUE_OF["name"].split()
    moved = tuple(
        ocr.OcrWord(
            text=word.text,
            bbox=(word.bbox[0], word.bbox[1] + step, word.bbox[2], word.bbox[3] + step),
            confidence=word.confidence,
        )
        if word.text in printed else word
        for word in read_of().words
    )
    read = ocr.OcrResult(words=moved, mean_confidence=CONFIDENT)
    assert fields.extract_fields(read, PASSPORT).values["name"] is None


def _label_gaps(field):
    """The gaps between a printed label's own words, and the height it was printed at."""
    parts = words_of(field.label_box, field.label)
    gaps = [right[1][0] - left[1][2] for left, right in zip(parts, parts[1:])]
    return gaps, field.label_box[3] - field.label_box[1]


@pytest.mark.parametrize("field", PAGE.fields, ids=lambda one: one.name)
def test_a_printed_label_s_words_are_near_enough_to_be_one_anchor_run(field):
    """So the adjacency written down is not so tight that the page fails it."""
    gaps, height = _label_gaps(field)
    assert max(gaps, default=0) <= fields.ANCHOR_ADJACENCY * height


@pytest.mark.parametrize("field", PAGE.fields, ids=lambda one: one.name)
def test_the_value_column_is_far_enough_out_that_no_anchor_run_bridges_to_it(field):
    """The other half of the same constant: two printed blocks stay two blocks."""
    height = field.label_box[3] - field.label_box[1]
    assert field.value_box[0] - field.label_box[2] > fields.ANCHOR_ADJACENCY * height


# --- what this call refuses, and what it refuses loudly ---


def test_a_document_type_no_table_holds_is_a_refusal_not_four_absent_fields():
    with pytest.raises(fields.UnknownDocumentError) as refusal:
        fields.extract_fields(read_of(), "permit")
    assert isinstance(refusal.value, ValueError)
    assert PASSPORT in str(refusal.value)


@pytest.mark.parametrize("named", [None, 1, "", "Passport", b"passport", ["passport"]])
def test_a_name_that_is_not_one_of_the_tables_is_refused(named):
    """A misspelling answering None would degrade every screening and say nothing."""
    with pytest.raises(fields.UnknownDocumentError):
        fields.extract_fields(read_of(), named)


def test_a_read_that_is_not_an_ocr_result_is_refused():
    with pytest.raises(ValueError):
        fields.extract_fields(object(), PASSPORT)


# --- the tables themselves ---


def test_the_record_is_frozen_and_its_values_cannot_be_edited():
    got = extracted()
    with pytest.raises(dataclasses.FrozenInstanceError):
        got.document_type = "visa"
    with pytest.raises(TypeError):
        got.values["name"] = "SOMEBODY ELSE"


def test_a_caller_cannot_add_a_document_type_to_the_tables():
    with pytest.raises(TypeError):
        fields.FIELD_TABLES["permit"] = ()


def test_the_document_types_are_the_ones_the_tables_hold():
    assert fields.DOCUMENT_TYPES == tuple(fields.FIELD_TABLES)


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_no_document_type_names_a_field_twice(document_type):
    names = [rule.field for rule in fields.FIELD_TABLES[document_type]]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_every_rule_names_at_least_one_anchor(document_type):
    for rule in fields.FIELD_TABLES[document_type]:
        assert rule.anchors


# --- the read is a stub, so the stub is held to the pixels ---


@pytest.mark.parametrize("word", read_of().words, ids=lambda one: one.text)
def test_every_word_the_stub_reports_sits_on_ink_the_fixture_printed(word):
    """So the four values above are read off a page rather than invented."""
    left, top, right, bottom = word.bbox
    patch = PAGE.image[top:bottom, left:right]
    assert patch.size > 0
    assert int(patch.min()) == document_images.INK_LEVEL


# --- 12.13: one normaliser per value type, over the values 12.11 answers ---


def normalised(page=PAGE, document_type=PASSPORT):
    """12.13's step over 12.11's: the record with every value shaped as its type."""
    return fields.normalise_fields(extracted(page, document_type))


def normalised_values(page=PAGE, document_type=PASSPORT):
    return dict(normalised(page, document_type).values)


#: A date as a document prints it, against the ISO 12.13 answers.  A
#: single-digit day is in the list on purpose: a normaliser that padded or
#: trimmed the day fails on one of these rather than on the obvious one.
DATES = [
    ("12 AUG 1974", "1974-08-12"),
    ("1 JAN 2000", "2000-01-01"),
    ("31 DEC 1999", "1999-12-31"),
    ("09 FEB 1969", "1969-02-09"),
]

#: A name as a document prints it, against the shaped form — lower case, two
#: accents Unicode will not decompose, the sharp-s and a literal one, so the
#: map and the combining-mark rule are both load-bearing and not decoration.
NAMES = [
    ("MÜLLER ANNA MARIA", "MULLER ANNA MARIA"),
    ("Muller Anna Maria", "MULLER ANNA MARIA"),
    ("ØSTERGAARD", "OSTERGAARD"),
    ("STRAßE", "STRASSE"),
    ("ŁUKASZ", "LUKASZ"),
    ("ĐORĐE", "DORDE"),
]

#: A number as a document prints it in groups, against the joined form, per
#: table.  **Each printed value matches no band**, so 12.11's own rule answers
#: the whole of it and 12.13 is what turns the groups back into one number.
NUMBERS = [
    (fields.PASSPORT, "passport_number", "L898 902C", "L898902C"),
    (fields.VISA, "visa_number", "V898 902C", "V898902C"),
    (fields.NATIONAL_ID, "national_id_number", "4829 0134 5612", "482901345612"),
]


@pytest.mark.parametrize("printed,iso", DATES)
def test_a_date_is_answered_in_iso(printed, iso):
    """One type: the form the table's own pattern matched becomes ISO."""
    page = document_images.render_document(values={"date_of_birth": printed})
    assert values_of(page)["date_of_birth"] == printed
    assert normalised_values(page)["date_of_birth"] == iso


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
@pytest.mark.parametrize("printed,shaped", NAMES)
def test_a_name_is_upper_cased_and_transliterated(document_type, printed, shaped):
    """One type, over all three tables: the type is the field's, not the document's."""
    assert fields.normalise_value(rule_of("name", document_type), printed) == shaped


@pytest.mark.parametrize("document_type,field_name,printed,joined", NUMBERS)
def test_a_number_is_answered_without_its_spaces(document_type, field_name, printed, joined):
    """One type: a number printed in groups is one number, on every table."""
    rule = rule_of(field_name, document_type)
    assert rule.value.search(printed) is None
    assert fields.normalise_value(rule, printed) == joined
    assert fields.normalise_value(rule, joined) == joined


@pytest.mark.parametrize("document_type,field_name,printed,joined", NUMBERS)
def test_joining_a_number_removes_the_spaces_and_nothing_else(
    document_type, field_name, printed, joined
):
    """Every printed character survives, in order: the value is read, not rewritten."""
    shaped = fields.normalise_value(rule_of(field_name, document_type), printed)
    assert shaped == joined
    assert shaped.replace(" ", "") == printed.replace(" ", "")


def test_one_walk_normalises_a_whole_record_read_off_a_printed_page():
    """All three types over a page, and what was printed stays on hand beside it."""
    page = document_images.draw_document(tuple(
        (name, label, "V898 902C" if name == "visa_number" else value)
        for name, label, value in NEW_ROWS[fields.VISA]
    ))
    assert values_of(page, fields.VISA) == {
        "name": "ERIKSSON ANNA MARIA",
        "visa_number": "V898 902C",
        "date_of_birth": "12 AUG 1974",
        "date_of_expiry": "15 APR 2012",
    }
    assert normalised_values(page, fields.VISA) == {
        "name": "ERIKSSON ANNA MARIA",
        "visa_number": "V898902C",
        "date_of_birth": "1974-08-12",
        "date_of_expiry": "2012-04-15",
    }


def test_extract_fields_still_answers_what_the_page_printed():
    """12.13 is a separate call, and folding it into 12.11 would hide a forgery."""
    page = document_images.render_document(values={"date_of_birth": "12 AUG 1974"})
    fields.normalise_fields(extracted(page, PASSPORT))
    assert values_of(page)["date_of_birth"] == "12 AUG 1974"


# --- nothing is invented: a value read whole is handed back whole ---


@pytest.mark.parametrize(
    "printed",
    ["NOT A DATE", "31 FEB 1974", "12 XYZ 1974", "12/08/1974", "12 AUG 74"],
)
def test_a_date_that_cannot_be_read_is_carried_through_and_not_invented(printed):
    """12.15 needs something to disagree with, and a guess would be the forgery.

    An impossible day is not rolled over, an unknown month is not numbered, a
    two-digit year is not given a century, and a numeric date is not read
    day-first: each of those is a decision the page does not carry.
    """
    assert fields.normalise_value(rule_of("date_of_birth"), printed) == printed


@pytest.mark.parametrize("printed", ["4829 0134 5612 7890 1234", "4829-0134-5612"])
def test_a_number_whose_joined_form_misses_its_own_band_is_answered_whole(printed):
    """Too long, or carrying a character the band does not admit: it stays a value."""
    rule = rule_of("national_id_number", fields.NATIONAL_ID)
    assert fields.normalise_value(rule, printed) == printed


def test_a_number_the_band_admits_is_joined_even_where_the_page_printed_a_sentence():
    """**The band is the only judge, and that is the point.**  A normaliser that
    guessed at content would answer this one value two ways, and the guess is
    the thing 12.15 exists to catch."""
    rule = rule_of("national_id_number", fields.NATIONAL_ID)
    assert fields.normalise_value(rule, "NOT A NUMBER") == "NOTANUMBER"


def test_a_field_nobody_printed_is_still_absent_after_normalising():
    """12.6's degrade reaches 12.13 as an absent field, not an empty string."""
    page = document_images.draw_document(tuple(
        (field.name, field.label, field.value)
        for field in PAGE.fields if field.name != "passport_number"
    ))
    assert normalised_values(page)["passport_number"] is None
    assert fields.normalise_value(rule_of("passport_number"), None) is None


def test_normalising_a_record_twice_changes_nothing_the_second_time():
    """12.15 holds both sides of a comparison, and ISO is not fed back through."""
    once = normalised(new_page(fields.VISA), fields.VISA)
    assert dict(fields.normalise_fields(once).values) == dict(once.values)


# --- what this call refuses, and it refuses the way 12.11 does ---


def test_a_value_type_no_normaliser_holds_is_a_refusal_not_a_shrug():
    rule = dataclasses.replace(rule_of("name"), value_type="Date")
    with pytest.raises(fields.UnknownFieldTypeError) as refusal:
        fields.normalise_value(rule, "ERIKSSON ANNA MARIA")
    assert isinstance(refusal.value, ValueError)
    assert fields.DATE in str(refusal.value)


@pytest.mark.parametrize("named", [None, 1, "", "datee", b"date", ["date"]])
def test_a_value_type_that_is_not_one_of_three_is_refused(named):
    """A silent pass-through would hand 12.15 a value that looks compared."""
    rule = dataclasses.replace(rule_of("name"), value_type=named)
    with pytest.raises(fields.UnknownFieldTypeError):
        fields.normalise_value(rule, "ERIKSSON ANNA MARIA")


def test_a_rule_that_is_not_a_field_rule_is_refused():
    with pytest.raises(ValueError):
        fields.normalise_value(object(), "ERIKSSON ANNA MARIA")


@pytest.mark.parametrize("value", [1, 3.5, b"L898902C", ["L898902C"]])
def test_a_value_that_is_neither_a_string_nor_none_is_refused(value):
    with pytest.raises(ValueError):
        fields.normalise_value(rule_of("passport_number"), value)


def test_a_record_that_is_not_an_extracted_fields_is_refused():
    with pytest.raises(ValueError):
        fields.normalise_fields({"name": "ERIKSSON ANNA MARIA"})


def test_a_record_whose_document_type_no_table_holds_is_refused():
    """12.11's own refusal, so one misspelling is one error and not two paths."""
    stranded = fields.ExtractedFields(document_type="permit", values={}, regions={})
    with pytest.raises(fields.UnknownDocumentError):
        fields.normalise_fields(stranded)


# --- the types and the tables themselves ---


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_every_field_every_table_names_is_a_type_this_module_normalises(document_type):
    """So a field added to a table cannot reach 12.15 unnormalised."""
    for rule in fields.FIELD_TABLES[document_type]:
        assert rule.value_type in fields.NORMALISERS


def test_the_three_types_are_the_three_the_three_tables_use():
    used = {rule.value_type for rules in fields.FIELD_TABLES.values() for rule in rules}
    assert used == set(fields.FIELD_TYPES)
    assert fields.FIELD_TYPES == (fields.DATE, fields.NAME, fields.NUMBER)


def test_the_month_table_is_the_twelve_a_document_prints_and_nothing_else():
    """A lost month, or a locale that renamed one, would answer a date no
    document carries -- silently, because the value would still be a string."""
    assert len(fields.MONTH_NUMBERS) == 12
    assert sorted(fields.MONTH_NUMBERS.values()) == list(range(1, 13))
    assert fields.MONTH_NUMBERS["JAN"] == 1
    assert fields.MONTH_NUMBERS["DEC"] == 12


def test_a_caller_cannot_add_a_value_type_to_the_normalisers():
    with pytest.raises(TypeError):
        fields.NORMALISERS["place_of_birth"] = lambda rule, value: value


def test_the_normalised_record_is_frozen_like_the_one_it_was_answered_from():
    got = normalised()
    with pytest.raises(dataclasses.FrozenInstanceError):
        got.document_type = "visa"
    with pytest.raises(TypeError):
        got.values["name"] = "SOMEBODY ELSE"


def test_the_name_transliteration_borrows_tier_zero_s_map_rather_than_copying_it():
    """Two hundred accented letters remembered twice is a second place to be wrong."""
    source = pathlib.Path(fields.__file__).read_text(encoding="utf-8")
    assert "TRANSLITERATIONS" not in source
    assert "unicodedata" not in source
    assert fields.td3.TRANSLITERATIONS is td3.TRANSLITERATIONS


# --- 12.14: every field is answered with the region it was read from ---


def regions_of(page=PAGE, document_type=PASSPORT):
    """12.14's answer beside 12.11's: where each field was printed."""
    return dict(extracted(page, document_type).regions)


def corners_of(boxes):
    """The four corners the union of ``boxes`` is expected to be reported as."""
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    return ((left, top), (right, top), (right, bottom), (left, bottom))


def printed_boxes(field, text=None):
    """The boxes the words of ``text`` — or of the field's own value — took."""
    return [box for _, box in words_of(field.value_box, text or field.value, PAGE)]


def page_for(document_type):
    """The page ``document_type`` is printed on: the fixture's, or a new table's."""
    return PAGE if document_type == PASSPORT else new_page(document_type)


def flag_with(region):
    """A finding carrying ``region``, and everything else 12.15 will fill in."""
    return EvidenceFlag(
        id="flag-12-14",
        tier=1,
        label="printed field disagrees with the MRZ",
        weight_band="review",
        value=0.5,
        confidence=0.9,
        region=region,
        expected="1974-08-12",
        found="1975-08-12",
        reason="the printed date and the MRZ date disagree",
        source_module="app.pipeline.tier1.fields",
        field="date_of_birth",
    )


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_every_field_the_page_printed_is_answered_with_a_region(document_type):
    """The task's claim: nothing extracted arrives with nowhere to point.

    Over all three tables rather than the fixture's one, since a region is
    every table's to answer and a fourth table is not exempted from it.
    """
    got = regions_of(page_for(document_type), document_type)
    assert set(got) == {rule.field for rule in fields.FIELD_TABLES[document_type]}
    assert all(region is not None for region in got.values())
    assert all(len(region) == 4 for region in got.values())


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_each_field_s_region_is_the_union_of_the_words_its_own_value_was_read_from(
    document_type,
):
    """Measured off the fixture's boxes, so the region is not a plausible box."""
    page = page_for(document_type)
    got = regions_of(page, document_type)
    for field in page.fields:
        assert got[field.name] == corners_of(printed_boxes(field)), field.name


@pytest.mark.parametrize("field", PAGE.fields, ids=lambda one: one.name)
def test_a_region_lies_on_its_own_row_and_never_reaches_over_its_label(field):
    """A region covering the label would point an officer at the wrong ink.

    **Not inside the value's own box, and no claim that it is**: this stub lays
    each word out by its own width and adds the widths of the spaces, which
    overshoots the one number ``getTextSize`` measured the whole line with.  The
    region is the union of the words, and the words are what is being pointed
    at — so the row and the label are the two claims worth making.
    """
    region = regions_of()[field.name]
    left, top = region[0]
    _, bottom = region[2]
    assert field.value_box[1] <= top and bottom <= field.value_box[3]
    assert field.value_box[0] <= left
    assert left > field.label_box[2]


def test_a_value_the_pattern_trimmed_is_pointed_at_without_the_trailing_text():
    """The region follows the value, not the whole row it was printed beside."""
    page = document_images.render_document(values={"date_of_birth": "12 AUG 1974 (COPY)"})
    field = document_images.field_of(page, "date_of_birth")
    dropped = printed_boxes(field, field.value)[-1]
    got = regions_of(page)["date_of_birth"]
    assert got == corners_of(printed_boxes(field, "12 AUG 1974"))
    assert got[2][0] < dropped[0]


def test_a_value_matching_no_pattern_is_pointed_at_over_all_of_its_words():
    """12.11 hands a malformed value back whole, so 12.14 locates all of it."""
    page = document_images.render_document(values={"date_of_birth": "NOT A DATE"})
    field = document_images.field_of(page, "date_of_birth")
    assert regions_of(page)["date_of_birth"] == corners_of(printed_boxes(field))


def test_a_beside_token_carrying_no_ink_is_not_in_the_region():
    """The region covers the value's own words, and a stray space is not one.

    Engines differ on whether whitespace arrives inside a word's own text or as
    its own token; the second shifts every offset the value was matched at, and
    this pins that the shift is applied rather than assumed away.
    """
    field = document_images.field_of(PAGE, "passport_number")
    left = field.value_box[0]
    stray = ocr.OcrWord(
        text=" ",
        bbox=(left - 20, field.value_box[1], left - 10, field.value_box[3]),
        confidence=CONFIDENT,
    )
    read = ocr.OcrResult(words=read_of().words + (stray,), mean_confidence=CONFIDENT)
    got = fields.extract_fields(read, PASSPORT)
    assert got.values["passport_number"] == VALUE_OF["passport_number"]
    assert got.regions["passport_number"] == corners_of(printed_boxes(field))


# --- an absent region is a claim, on the flag's own reason ---


def test_a_field_the_page_never_printed_is_answered_no_value_and_no_region():
    page = document_images.draw_document(tuple(
        (field.name, field.label, field.value)
        for field in PAGE.fields if field.name != "passport_number"
    ))
    assert values_of(page)["passport_number"] is None
    assert regions_of(page)["passport_number"] is None


def test_a_label_printed_with_nothing_beside_it_is_answered_no_value_and_no_region():
    """A blank row is not an empty box — an empty box is not a place to point."""
    page = document_images.render_document(values={"date_of_expiry": ""})
    assert values_of(page)["date_of_expiry"] is None
    assert regions_of(page)["date_of_expiry"] is None


def test_a_page_no_engine_could_read_answers_no_value_and_no_region_for_every_field():
    """12.6's degrade reaches 12.14 as four absent fields rather than an error."""
    unread = runner.run_tier1(PAGE.image, engines={}).ocr
    got = fields.extract_fields(unread, PASSPORT)
    assert set(got.regions.values()) == {None}
    assert set(got.regions) == set(got.values)


def test_a_field_printed_on_two_rows_is_pointed_at_the_row_its_value_came_from():
    """A region beside the other row's value would be a misdirection, not a help."""
    page = document_images.draw_document(tuple(
        (field.name, field.label, field.value) for field in PAGE.fields
    ) + (("passport_no_again", "Passport No", "X0000000"),))
    first = document_images.field_of(page, "passport_number")
    again = document_images.field_of(page, "passport_no_again")
    assert values_of(page)["passport_number"] == VALUE_OF["passport_number"]
    assert regions_of(page)["passport_number"] == corners_of(printed_boxes(first))
    assert regions_of(page)["passport_number"][0][1] < again.value_box[1]


# --- the region is the page's frame, and never a crop's ---


@pytest.mark.parametrize("document_type", fields.DOCUMENT_TYPES)
def test_every_region_lies_inside_the_page_it_was_read_from(document_type):
    page = page_for(document_type)
    width, height = page.size
    for region in regions_of(page, document_type).values():
        for x, y in region:
            assert 0 <= x <= width and 0 <= y <= height


def test_this_module_cannot_answer_a_region_in_a_crop_s_frame():
    """12.8's re-read boxes are the crop's own, so the crop is not imported here."""
    tree = ast.parse(pathlib.Path(fields.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "reread" not in imported


# --- both sides of the value stay on hand, and the region travels with them ---


def test_normalising_carries_the_regions_and_leaves_what_the_page_printed_alone():
    """D91's cost: a region describes the page, so it goes with the printed form."""
    printed = extracted()
    shaped = fields.normalise_fields(printed)
    assert dict(shaped.regions) == dict(printed.regions)
    assert dict(printed.values) == VALUE_OF
    assert dict(shaped.values)["date_of_birth"] == "1974-08-12"


def test_a_record_carrying_no_region_for_a_field_answers_none_rather_than_raising():
    """23.6's shape for a field a record says nothing about: absent, not fatal."""
    got = extracted()
    stranded = dataclasses.replace(got, regions={"name": got.regions["name"]})
    assert dict(fields.normalise_fields(stranded).regions)["passport_number"] is None


def test_the_regions_cannot_be_edited_like_the_values_cannot():
    with pytest.raises(TypeError):
        extracted().regions["name"] = ((0, 0), (1, 0), (1, 1), (0, 1))


# --- the shape is the one a finding already carries, so 12.15 does not re-express it ---


def test_a_region_is_a_shape_a_finding_already_carries():
    region = regions_of()["date_of_birth"]
    assert flag_with(region).region == region


def test_the_finding_still_refuses_a_region_this_module_would_never_answer():
    """So the check above is the flag's own, and not a shape every value passes."""
    with pytest.raises(FlagValueError):
        flag_with("date_of_birth")


# --- what this layer is forbidden from becoming ---


def test_this_layer_holds_no_finding_vocabulary_and_so_cannot_raise_one():
    tree = ast.parse(pathlib.Path(fields.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "risk" not in imported
    built = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "EvidenceFlag"
    ]
    assert built == []


def test_this_layer_imports_no_logging_and_so_cannot_leak_a_printed_value():
    """D88's rule for the module above, and the one this module inherits."""
    tree = ast.parse(pathlib.Path(fields.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "logging" not in imported
