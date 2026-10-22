"""12.7 -- the document page every OCR test in Part 12 is drawn against.

The subject of this file is that the fixture is *ground truth*.  Part 4's
fixture drew a monospaced cell table so a zone could be read back out of it by
matching patterns; nothing here is read back that way, because an OCR engine
is what reads this page and neither engine is installed on this box.  So what
is pinned is the one claim every later test in Part 12 rests on: the text the
description states is the text the page was printed from, and the boxes the
description carries are the boxes the ink is inside.
"""

import dataclasses

import numpy as np
import pytest

from app.pipeline.tier0 import document
from tests.fixtures import document_images, mrz_images


#: The four fields 12.7 names, read out of the fixture's own table rather than
#: written down here, so a corrected specimen moves this file with it instead
#: of leaving it asserting a page nobody draws.
EXPECTED_FIELDS = {
    name: (label, value)
    for name, label, value in document_images.SPECIMENS["passport"]
}

FIELD_NAMES = list(EXPECTED_FIELDS)

#: The faces the size sweep draws at.  The smallest is 12.9's page: a field
#: printed small enough that its confidence is the gate's question.
FONT_SCALES = (0.6, 0.8, 1.0, 1.4)

#: The months a printed date spells, in order, so a test can say that 12 AUG
#: 1974 and the MRZ's 740812 are one day rather than trusting the fixture.
MONTHS = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)


def patch_of(frame, box):
    """The half-open ``box`` out of a frame or a mask, as an array."""
    return frame[box[1]:box[3], box[0]:box[2]]


def ink_of(page):
    """Where the page carries ink, read off the frame rather than off the boxes."""
    return page.image[:, :, 0] < document_images.PAPER_LEVEL


def boxes_of(page):
    """Every box the page's description carries, in printing order."""
    return [
        box for field in page.fields for box in (field.label_box, field.value_box)
    ]


def parsed_specimen():
    """The TD3 specimen, parsed the way Tier 0 parses one."""
    page = mrz_images.render_format("TD3")
    return document.parse_mrz(mrz_images.read_zone(page))


# --- the frame is the page that was asked for -----------------------------


@pytest.mark.parametrize(
    "size",
    [
        pytest.param(document_images.PAGE_SIZE, id="the-size-the-fixture-states"),
        pytest.param((1000, 320), id="a-short-page"),
        pytest.param((1600, 900), id="a-wide-page"),
    ],
)
def test_the_frame_is_the_size_that_was_asked_for_in_three_channels(size):
    # A frame that came out the wrong shape would put every field's box in the
    # wrong place, and the ink checks below would then be measuring a page
    # whose description is a lie -- which is the whole subject of this file.
    page = document_images.draw_document(
        document_images.SPECIMENS["passport"], size=size
    )

    assert page.image.shape == (size[1], size[0], 3)
    assert page.image.dtype == np.uint8
    assert page.size == size


def test_the_page_keeps_the_geometry_the_drawing_used():
    # 12.8's crop and 12.9's gate are both argued against a field's size, so a
    # test has to be able to say what it measured against rather than infer it
    # from the defaults it happened to get.
    page = document_images.render_document()

    assert page.font == document_images.FONT
    assert page.font_scale == document_images.FONT_SCALE
    assert page.thickness == document_images.THICKNESS
    assert page.margin == document_images.MARGIN
    assert page.label_gap == document_images.LABEL_GAP
    assert page.row_gap == document_images.ROW_GAP


# --- the description says what the page printed ---------------------------


@pytest.mark.parametrize("name", FIELD_NAMES)
def test_every_expected_field_is_present_with_its_label_and_its_value(name):
    # This is 12.7's own claim: the labels and values are known, so a test can
    # say what it expects to find on the page instead of reading the page and
    # agreeing with itself.
    label, value = EXPECTED_FIELDS[name]
    page = document_images.render_document()

    field = document_images.field_of(page, name)

    assert (field.label, field.value) == (label, value)


def test_the_page_prints_exactly_the_four_fields_12_7_names():
    # The four, in the specimen's own order.  A fifth field would be a field
    # 12.11 has no anchor for and 12.15 no MRZ value to compare against.
    page = document_images.render_document()

    assert [field.name for field in page.fields] == FIELD_NAMES
    assert set(FIELD_NAMES) == {
        "name", "passport_number", "date_of_birth", "date_of_expiry",
    }


def test_the_printed_document_number_is_the_one_its_mrz_carries():
    # 12.15 compares a printed field with the MRZ and expects a clean document
    # to agree; a fixture whose printed number was invented would hand that
    # test a mismatch on every clean page and blame the comparator.
    parsed = parsed_specimen()

    printed = document_images.field_of(
        document_images.render_document(), "passport_number"
    )

    # Tier 0 keeps a zone's field exactly as it printed it, filler and all, so
    # the printed page carries the same nine characters a visible field would.
    assert printed.value == parsed.document_number.strip("<")


@pytest.mark.parametrize(
    ("name", "printed"),
    [
        pytest.param("date_of_birth", "12 AUG 1974", id="date-of-birth"),
        pytest.param("date_of_expiry", "15 APR 2012", id="date-of-expiry"),
    ],
)
def test_each_printed_date_is_the_same_day_the_mrz_carries(name, printed):
    # The two forms are what 12.13 normalises between, and the printed form is
    # the one that is not ISO -- so the pair has to be one day, or the
    # normalisation is being tested on two different days.
    field = document_images.field_of(document_images.render_document(), name)

    day, month, year = printed.split()
    mrz_six = f"{year[2:]}{MONTHS.index(month) + 1:02d}{int(day):02d}"

    assert field.value == printed
    assert mrz_six in mrz_images.SPECIMENS["TD3"][1]


def test_the_printed_name_is_the_mrz_name_with_its_fillers_read_as_spaces():
    # The same person under both readings of the document, which is what makes
    # 12.15's name comparison and 12.16's diacritic tolerance about one case
    # rather than about two specimens that happen to sit in one fixture.
    zone_one = mrz_images.SPECIMENS["TD3"][0]
    printed = zone_one[zone_one.index("ERIKSSON"):]

    field = document_images.field_of(document_images.render_document(), "name")

    assert field.value == " ".join(printed.replace("<", " ").split())


# --- the description is a true account of the frame -----------------------


def test_every_box_the_description_carries_holds_ink_and_sits_inside_the_page():
    # A box with no ink in it is a region 12.8 would crop to nothing and 12.14
    # would report as the field's evidence, and a box outside the frame is a
    # crop NumPy silently shortens rather than one that fails.
    page = document_images.render_document()
    width, height = page.size

    for field in page.fields:
        for box in (field.label_box, field.value_box):
            assert 0 <= box[0] < box[2] <= width
            assert 0 <= box[1] < box[3] <= height
            patch = patch_of(page.image, box)
            assert int(patch.min()) == document_images.INK_LEVEL


def test_no_ink_is_printed_outside_the_boxes_the_description_names():
    # The half that makes the boxes evidence rather than decoration: a page
    # with ink the description cannot account for would put a word in a read
    # that no field owns, and 12.11 would have nowhere to extract it to.
    page = document_images.render_document()
    named = np.zeros(page.image.shape[:2], bool)
    for box in boxes_of(page):
        named[box[1]:box[3], box[0]:box[2]] = True

    assert not (ink_of(page) & ~named).any()


def test_no_two_printed_rows_share_a_row_of_the_page():
    # 12.11 finds a field by its anchor word and takes the text beside it, so
    # two rows sharing a row of the page would put one field's value inside
    # another field's box -- and the row pitch is measured off the face rather
    # than written down, so a page drawn at a scale nobody tested would be the
    # first to overlap.
    page = document_images.render_document()
    rows = [field.label_box for field in page.fields]

    for above, below in zip(rows, rows[1:]):
        assert above[3] <= below[1]

def test_a_fields_region_is_the_value_and_leaves_its_label_outside_it():
    # 12.8 crops to a field's region and re-reads it, so the region has to be
    # the value: a crop holding the label too would answer a re-read with two
    # words and put the anchor text into the field's value.
    page = document_images.render_document()

    for field in page.fields:
        assert field.value_box[0] >= field.label_box[2]


# --- an overridden value is printed, not only described -------------------


def test_an_overridden_value_is_the_text_the_page_was_printed_from():
    # 12.15 alters one printed date and expects exactly one mismatch, which
    # needs the alteration to reach the page: a description-only override would
    # report a field as wrong that the frame still prints correctly.
    altered = {"date_of_birth": "01 JAN 1970"}
    page = document_images.render_document(values=altered)

    printed = {field.name: field.value for field in page.fields}

    assert printed["date_of_birth"] == "01 JAN 1970"
    assert printed == {
        name: altered.get(name, value) for name, (_, value) in EXPECTED_FIELDS.items()
    }


def test_an_override_changes_the_ink_and_not_only_the_description():
    altered = {"date_of_birth": "01 JAN 1970"}
    default = document_images.render_document()
    page = document_images.render_document(values=altered)
    box = document_images.field_of(page, "date_of_birth").value_box

    assert not np.array_equal(
        patch_of(default.image, box), patch_of(page.image, box)
    )
    assert patch_of(ink_of(page), box).any()


def test_an_override_moves_no_other_fields_box():
    # The one field a test altered has to stay the one field that moved: a
    # value long enough to reflow the page would move every region below it,
    # and 12.14's report and 12.15's flag would then point at boxes that
    # belong to fields nobody altered.
    default = document_images.render_document()
    page = document_images.render_document(values={"name": "A MUCH LONGER PRINTED NAME"})

    assert [f.label_box for f in page.fields] == [f.label_box for f in default.fields]
    assert [f.value_box for f in page.fields[1:]] == [
        f.value_box for f in default.fields[1:]
    ]


# --- what the fixture refuses ---------------------------------------------


def test_a_page_with_no_fields_printed_on_it_is_refused():
    with pytest.raises(ValueError, match="at least one field"):
        document_images.draw_document(())


def test_two_fields_printed_under_one_name_are_refused():
    # A field is addressed by name -- 12.11 extracts into it and 12.15
    # overrides it -- so two rows under one name would have two answers and an
    # override would silently pick one of them.
    rows = document_images.SPECIMENS["passport"]
    doubled = rows + (("date_of_birth", "Born", "01 JAN 1970"),)

    with pytest.raises(ValueError, match="both named 'date_of_birth'"):
        document_images.draw_document(doubled)


def test_an_override_naming_no_printed_field_is_refused():
    # A misspelled override that printed nothing would leave a test asserting
    # that a page it thinks it altered is clean, and the mismatch it went to
    # look for would never exist.
    with pytest.raises(ValueError, match="prints no field named 'expiry'"):
        document_images.render_document(values={"expiry": "15 APR 2012"})


def test_a_document_this_fixture_does_not_print_is_refused():
    # 12.12 adds a visa and a national ID, and this is the answer it extends:
    # a caller cannot ask for a document whose printed fields are not stated.
    with pytest.raises(ValueError, match="not a document this fixture prints"):
        document_images.render_document("visa")


def test_a_block_that_does_not_fit_the_page_is_refused_rather_than_clipped():
    # Clipping would print part of a field, and a part-printed date reads back
    # as a date that was misread -- a pipeline test failing for a reason of the
    # fixture's making, which is the one failure mode a fixture exists to stop.
    with pytest.raises(ValueError, match="do not fit a page"):
        document_images.draw_document(
            document_images.SPECIMENS["passport"], size=(1000, 200)
        )


# --- the face, and the records --------------------------------------------


@pytest.mark.parametrize("font_scale", FONT_SCALES)
def test_a_face_prints_its_fields_at_the_size_it_was_asked_for(font_scale):
    # 12.9's gate and 12.8's re-read are both argued from a field being small,
    # so drawing at a named size and still printing every value is what makes
    # those two tasks able to ask for a page at all.
    page = document_images.render_document(font_scale=font_scale)

    assert page.font_scale == font_scale
    for field in page.fields:
        assert patch_of(ink_of(page), field.value_box).any()


def test_a_smaller_face_prints_smaller_text_than_a_larger_one():
    small = document_images.render_document(font_scale=0.6)
    large = document_images.render_document(font_scale=1.4)

    assert patch_of(small.image, document_images.field_of(small, "name").value_box).shape < patch_of(
        large.image, document_images.field_of(large, "name").value_box
    ).shape


def test_field_of_names_the_fields_a_page_prints_when_asked_for_another():
    page = document_images.render_document()

    with pytest.raises(KeyError, match=r"prints no field named 'nationality'"):
        document_images.field_of(page, "nationality")


def test_both_records_are_frozen_and_carry_no_public_method():
    # The same invariant OcrResult and MrzDocument are held to: a fixture's
    # description is evidence, so a test that could edit the ground truth it is
    # asserting against could make any page agree with any expectation.
    page = document_images.render_document()

    for record in (type(page), type(page.fields[0])):
        assert dataclasses.is_dataclass(record)
        assert record.__dataclass_params__.frozen
        assert not [name for name in vars(record) if not name.startswith("_")]

    with pytest.raises(dataclasses.FrozenInstanceError):
        page.size = (10, 10)
    with pytest.raises(dataclasses.FrozenInstanceError):
        page.fields[0].value = "ANYTHING ELSE"
