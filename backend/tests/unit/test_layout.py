"""13.9 -- a field printed away from where the layout puts it is flagged.

The page under test is the committed reference, laid down tilted and
photographed exactly as 13.7 lays it down, so the alignment this module
measures in is the pipeline's own alignment and not a second drawing of it.

**13.10's font proxy is read off the type the page prints, which is the four
labels and not the five field rectangles.**  Those rectangles are blank paper
in the committed file, so a proxy measured inside them would have nothing to
measure, and the labels are printed in one place on every page of the
committed layout.

**The page under test is reprinted in a second face with one variable changed.**
The same four words, the same baselines, the same size: the face is all that
differs between the control and the finding, and the position half is asserted
unchanged beside it so the score cannot have moved for another reason.

**The shifted field is the one field the committed reference actually prints
anything inside.**  The four text rectangles are blank paper in that file, which
is what ``_scoreable`` refuses to measure against; a test that shifted one of
them would be measuring a drawn box rather than a printed field.  The photo
block fills its own rectangle, so its centre is where its ink is.

**13.11 unaligns one capture rather than printing a second page.**  The same
photograph is put into template space twice, once by the corners the detector
found and once by those corners turned about the capture's centre, so the page
and everything printed on it are identical and only the alignment differs.
"""

import importlib.resources

import cv2
import numpy as np
import pytest
from PIL import Image

from app.pipeline.tier1 import align, layout
from app.pipeline.tier1.corners import detect_corners
from app.pipeline.tier1.templates import loader
from app.pipeline.tier1.templates.loader import TemplateError, load_template
from app.risk import flag_ids
from app.risk.weightsets import loader as weightset_loader
from tests.fixtures import document_images

#: The committed layout, read through its own loader so the frame these tests
#: measure against is the one the pipeline measures against.
TEMPLATE = load_template("passport_td3")

#: The allowances, read out of that same file by the module under test.
TOLERANCES = layout.read_tolerances(TEMPLATE)

#: The capture the page is photographed into, and where it is laid, both taken
#: from 13.7 so the two tests warp the same photograph.
FRAME = (1300, 1000)
LAID_AT = ((196, 32), (1189, 154), (1104, 848), (111, 726))

#: How far the shifted field is moved, in whole pixels, up and to the right.
#: Chosen inside ``layout.MAX_DISPLACEMENT_PX`` so the field is still measured,
#: and clear of ``TOLERANCES`` so the move is unambiguously a deviation.
SHIFTED_BY = (30, -25)

#: How far the measured displacement may sit from the move actually made, in
#: pixels.  The warp's own round trip through the detector costs a couple of
#: pixels; this is a claim that the number means the displacement, not that it
#: is exact.
WITHIN_PIXELS = 6.0

#: The field whose rectangle the committed reference does print inside.
INKED_FIELD = "photo"

#: The four fields whose rectangles the committed reference leaves blank.
BLANK_FIELDS = ("name", "passport_number", "date_of_birth", "date_of_expiry")

#: The four lines the committed reference prints, and where it prints them.
#: Read off the committed asset and used to rebuild a page with its type set in
#: another face; a reprint in ``FONT_HERSHEY_SIMPLEX`` at this size reproduces
#: the committed page's own style numbers, which is what makes it the control.
LABELS = ("Name", "Passport No", "Date of birth", "Date of expiry")
LABEL_BASELINES = (87, 138, 189, 240)
LABEL_LEFT = 60

#: The face the committed reference prints in, and a second one of the same
#: size to set the same words in.
REFERENCE_FACE = cv2.FONT_HERSHEY_SIMPLEX
OTHER_FACE = cv2.FONT_HERSHEY_DUPLEX

#: How far the corners the pipeline uses are turned from the capture's own, in
#: degrees about the capture's centre, so the page reaches template space
#: unstraightened.  Four degrees carries the one measured field 24 pixels from
#: its rectangle -- twice its own 12-pixel tolerance, and inside the 64 pixels
#: this module still looks.
MISALIGNED_BY_DEGREES = 4.0


def reference_image():
    """The committed reference as the BGR frame a capture is laid down from."""
    resource = importlib.resources.files(loader.TEMPLATES_PACKAGE).joinpath(
        TEMPLATE.reference_image
    )
    with resource.open("rb") as stream:
        with Image.open(stream) as image:
            return np.ascontiguousarray(np.array(image.convert("RGB"))[:, :, ::-1])


def capture(page):
    """``page`` laid down and photographed, as 13.7 lays it down."""
    return document_images.lay(page, TEMPLATE.reference_size, LAID_AT, FRAME)


def aligned(page):
    """``page`` laid down, photographed, found, and warped onto the template."""
    photo = capture(page)
    return align.warp_to_template(photo, TEMPLATE, detect_corners(photo))


def misaligned(corners, degrees=MISALIGNED_BY_DEGREES):
    """``corners`` turned about the capture's own centre, as whole pixels.

    A capture put into template space by corners that are not its document's is
    an unaligned document, and nothing else about it changes: the photograph,
    the detector and the warp are all still the pipeline's own.
    """
    centre = np.array([FRAME[0] / 2, FRAME[1] / 2], float)
    turn = np.radians(degrees)
    rotation = np.array([
        [np.cos(turn), -np.sin(turn)],
        [np.sin(turn), np.cos(turn)],
    ])

    turned = []
    for point in corners:
        moved = rotation @ (np.array(point, float) - centre) + centre
        turned.append((int(round(float(moved[0]))), int(round(float(moved[1])))))
    return tuple(turned)


def shifted_page(dx, dy):
    """The committed page with the photo block wiped and reprinted ``(dx, dy)`` off.

    Wiping first is what makes this a moved field rather than a second block
    printed beside the first: the page carries one photo block, and it is not
    where the layout puts it.
    """
    page = reference_image()
    rect = TEMPLATE.fields[INKED_FIELD]
    cv2.rectangle(
        page, (rect.x, rect.y), (rect.x + rect.width, rect.y + rect.height),
        (255, 255, 255), -1,
    )
    cv2.rectangle(
        page,
        (rect.x + dx, rect.y + dy),
        (rect.x + dx + rect.width, rect.y + dy + rect.height),
        (205, 205, 205), -1,
    )
    return page


def reprinted(face, scale=1.0, thickness=2):
    """The committed page with its four labels wiped and set again in ``face``.

    Only the type is touched: the photo block is left exactly where the
    committed file puts it, so every field displacement is unchanged.
    """
    page = reference_image()
    for label, baseline in zip(LABELS, LABEL_BASELINES):
        cv2.rectangle(
            page, (LABEL_LEFT - 4, baseline - 32), (286, baseline + 12),
            (255, 255, 255), -1,
        )
        cv2.putText(
            page, label, (LABEL_LEFT, baseline), face, scale, (0, 0, 0),
            thickness, cv2.LINE_AA,
        )
    return page


def deviation_of(field):
    """The measured deviation for ``field``, or a failure naming what was measured."""
    found = layout.field_deviations(aligned(shifted_page(*SHIFTED_BY)), TEMPLATE)
    measured = {one.field: one for one in found}
    assert field in measured, f"nothing measured for {field!r}: {sorted(measured)}"
    return measured[field]


# --- the task's own claim: a deliberately shifted field is flagged ---


def test_a_field_shifted_past_its_tolerance_is_flagged():
    """A printed field moved off its rectangle is one LAYOUT_DEVIATION finding.

    The whole claim of 13.9 in one assertion: the move is deliberate, it is
    more than three times the tolerance, and the flag is emitted for it.
    """
    flags = layout.compare_layout(aligned(shifted_page(*SHIFTED_BY)), TEMPLATE)

    assert [flag.field for flag in flags] == [INKED_FIELD]
    assert [flag.id for flag in flags] == [flag_ids.LAYOUT_DEVIATION]


def test_the_finding_hangs_on_the_fields_own_region():
    """The region is that field's rectangle, so an officer is shown the field."""
    flag = layout.compare_layout(aligned(shifted_page(*SHIFTED_BY)), TEMPLATE)[0]

    assert flag.region == TEMPLATE.fields[INKED_FIELD].corners


def test_the_measurement_is_the_displacement_rather_than_a_constant():
    """The number is how far the field moved, within the warp's own error.

    Without this the flag would still fire for any field at all, and 13.11's
    "an unaligned page scores worse than an aligned one" would have nothing to
    stand on.
    """
    measured = deviation_of(INKED_FIELD)
    wanted = float(np.hypot(*SHIFTED_BY))

    assert measured.offset[0] == pytest.approx(SHIFTED_BY[0], abs=WITHIN_PIXELS)
    assert measured.offset[1] == pytest.approx(SHIFTED_BY[1], abs=WITHIN_PIXELS)
    assert measured.deviation == pytest.approx(wanted, abs=WITHIN_PIXELS)


def test_the_score_rises_with_the_displacement_and_stays_in_the_unit_interval():
    """A field twice its tolerance out scores 1.0, and no field can score past it."""
    measured = deviation_of(INKED_FIELD)
    at_tolerance = layout.FieldDeviation(
        field=measured.field, region=measured.region, offset=(0, 0),
        deviation=measured.tolerance, tolerance=measured.tolerance,
    )
    at_saturation = layout.FieldDeviation(
        field=measured.field, region=measured.region, offset=(0, 0),
        deviation=measured.tolerance * layout.VALUE_SATURATION,
        tolerance=measured.tolerance,
    )

    assert at_tolerance.score == 0.5
    assert at_saturation.score == 1.0
    assert at_tolerance.score < at_saturation.score
    assert 0.0 <= measured.score <= 1.0


# --- what is not a deviation ---


def test_a_field_inside_its_tolerance_is_not_flagged():
    """The committed page, photographed and warped, reads as where it belongs.

    This is the control the whole metric stands against: a genuine document
    must not be reported as a displaced one, which is what 13.8's position
    tolerance of 12 was chosen to prevent against a detector that lands 4 to 5
    pixels out.
    """
    measured = {one.field: one for one in layout.field_deviations(aligned(reference_image()), TEMPLATE)}

    assert measured[INKED_FIELD].deviation <= TOLERANCES[INKED_FIELD]
    assert layout.compare_layout(aligned(reference_image()), TEMPLATE) == ()


def test_a_rectangle_with_no_ink_in_the_reference_is_skipped_not_scored_as_zero():
    """The four blank rectangles are refused as unmeasurable, not read as in place.

    Their rectangles record where a value may go, not where the ink is, so a
    field measured against one is measured against a drawn box.  Scoring them
    as zero would be a claim this data cannot support.
    """
    found = {one.field for one in layout.field_deviations(aligned(reference_image()), TEMPLATE)}

    assert found == {INKED_FIELD}
    assert not set(BLANK_FIELDS) & found


def test_a_field_moved_out_of_reach_is_not_measured():
    """Past ``MAX_DISPLACEMENT_PX`` there is no measurement, and so no finding.

    Stated rather than left: a field moved further than this module looks is
    absent from its answer rather than reported as in place.
    """
    far = (0, int(layout.MAX_DISPLACEMENT_PX) + 100)

    assert layout.field_deviations(aligned(shifted_page(*far)), TEMPLATE) == ()


# --- the flag is one the rest of the system already knows ---


def test_the_id_and_the_band_emitted_are_the_ones_the_weightset_holds():
    """``LAYOUT_DEVIATION`` is declared, and ``low`` is the band it is given.

    The band is not this module's to choose: ``v1.yaml`` already calls template
    deviation the classic false alarm on a genuine document.
    """
    row = weightset_loader.load_weightset().flags[flag_ids.LAYOUT_DEVIATION]
    flag = layout.compare_layout(aligned(shifted_page(*SHIFTED_BY)), TEMPLATE)[0]

    assert flag.id in flag_ids.FLAG_IDS
    assert row["band"] == layout.DEVIATION_BAND == flag.weight_band
    assert 0.0 <= flag.value <= 1.0


def test_the_finding_names_no_printed_text():
    """``reason`` is numbers and the field's own name, never what the page printed."""
    flag = layout.compare_layout(aligned(shifted_page(*SHIFTED_BY)), TEMPLATE)[0]

    assert flag.expected is None and flag.found is None
    assert flag.source_module == layout.SOURCE_MODULE
    assert flag.tier == 1


# --- what is refused rather than guessed ---


@pytest.mark.parametrize("position", [None, 0, -3, True, "12", float("nan")])
def test_read_tolerances_refuses_a_position_that_is_not_a_positive_number(monkeypatch, position):
    """A tolerance no field could be measured against is refused, not defaulted."""
    document = {
        loader.FIELDS_KEY: {
            field: {loader.FIELDS_KEY: {}, layout.TOLERANCE_KEY: {layout.POSITION_KEY: position}}
            for field in TEMPLATE.fields
        }
    }
    monkeypatch.setattr(loader, "read_document", lambda name: document)

    with pytest.raises(TemplateError) as refused:
        layout.read_tolerances(TEMPLATE)

    assert layout.POSITION_KEY in str(refused.value)


def test_read_tolerances_refuses_a_field_carrying_no_tolerance_at_all(monkeypatch):
    """A row with no ``tolerance`` key is refused on the same ground as a bad one."""
    document = {
        loader.FIELDS_KEY: {field: {"x": 0, "y": 0, "width": 1, "height": 1} for field in TEMPLATE.fields}
    }
    monkeypatch.setattr(loader, "read_document", lambda name: document)

    with pytest.raises(TemplateError) as refused:
        layout.read_tolerances(TEMPLATE)

    assert layout.TOLERANCE_KEY in str(refused.value)


def test_a_field_with_no_tolerance_given_is_refused_rather_than_defaulted():
    """A caller passing half the allowances is told which field is missing."""
    partial = {field: 12 for field in list(TEMPLATE.fields)[:-1]}

    with pytest.raises(ValueError) as refused:
        layout.field_deviations(aligned(reference_image()), TEMPLATE, partial)

    assert list(TEMPLATE.fields)[-1] in str(refused.value)


@pytest.mark.parametrize("frame", [np.zeros((10, 10), np.uint8), "not a frame", None])
def test_a_frame_that_is_not_three_channels_is_refused(frame):
    """Template space is a three-channel frame, as ``align`` hands it over."""
    with pytest.raises(ValueError) as refused:
        layout.field_deviations(frame, TEMPLATE)

    assert "three-channel" in str(refused.value)


# --- 13.10: the font-style proxy, and the score it is read into ---


def test_the_style_numbers_are_read_off_the_type_the_page_prints():
    """Both numbers are measured on real glyphs, and the capture costs little of them.

    The reference's own type is compared with the same page photographed and
    warped, which is the only comparison the metric ever makes -- a page against
    its own reference, never a page against a constant.
    """
    found = layout.font_style(aligned(reference_image()))
    expected = layout.font_style(reference_image())

    assert found is not None and expected is not None
    assert found.glyphs > 0
    assert 0.0 < found.stroke_density < 1.0
    assert found.height_spread > 0.0
    assert found.stroke_density == pytest.approx(expected.stroke_density, rel=0.05)
    assert found.height_spread == pytest.approx(expected.height_spread, rel=0.05)


def test_a_page_printed_in_the_reference_own_face_is_not_called_another_one():
    """The committed words, wiped and set again in the committed face, read clean.

    The control the whole proxy stands against: this build's ``putText`` cannot
    go heavier than the committed page already is, so a same-face reprint is the
    nearest thing to a page that is certainly not a forgery.

    The departure is also spelled out, so that it is this page's ink share against
    the *reference's* ink share and not a number compared with itself.
    """
    found = layout.font_style(aligned(reprinted(REFERENCE_FACE)))
    expected = layout.font_style(reference_image())
    from_its_own_reference = (
        abs(found.stroke_density - expected.stroke_density) / layout.DENSITY_TOLERANCE
    )

    assert layout.font_deviation(aligned(reprinted(REFERENCE_FACE)), TEMPLATE) == pytest.approx(
        from_its_own_reference
    )
    assert from_its_own_reference < 0.25


def test_type_set_in_another_face_departs_from_the_reference_face():
    """The same words in another face move both style numbers the same way.

    ``DUPLEX`` fills more of each glyph than ``SIMPLEX`` at this size and sets it
    to the same heights, so this is a page whose weight alone is wrong.
    """
    same = layout.font_style(aligned(reprinted(REFERENCE_FACE)))
    other = layout.font_style(aligned(reprinted(OTHER_FACE)))

    assert other.stroke_density > same.stroke_density
    assert other.height_spread > same.height_spread
    # The heights are past the whole tolerance by more than twice, so the
    # departure is 1.0 whatever the ink share does: the worse of the two.
    assert layout.font_deviation(aligned(reprinted(OTHER_FACE)), TEMPLATE) == 1.0


def test_a_different_face_lowers_the_layout_score_and_the_positions_do_not_move():
    """The proxy is in the layout score, and the position half is untouched by it.

    The claim of 13.10 in one assertion: two pages with every field exactly where
    the layout puts it, differing only in the face their type is set in, score
    differently -- so the score is not 13.9's number wearing a new name.
    """
    control = aligned(reprinted(REFERENCE_FACE))
    finding = aligned(reprinted(OTHER_FACE))

    assert layout.field_deviations(finding, TEMPLATE) == layout.field_deviations(control, TEMPLATE)
    assert layout.layout_score(finding, TEMPLATE) < layout.layout_score(control, TEMPLATE)
    assert layout.layout_score(control, TEMPLATE) > 0.5


def test_a_page_that_prints_no_type_is_scored_on_nothing_rather_than_cleanly():
    """Blank paper carries no glyphs, so there is no style to say matches.

    ``D99``'s rule applied to the new metric: an absence of measurement is not a
    measurement of agreement.
    """
    blank = np.full_like(reference_image(), 255)

    assert layout.font_style(blank) is None
    assert layout.font_deviation(blank, TEMPLATE) is None
    assert layout.layout_score(blank, TEMPLATE) is None


# --- 13.11: the score answers to alignment, so it is not a constant ---


def test_an_unaligned_page_scores_lower_than_an_aligned_one():
    """The claim of 13.11: one capture, one number, two answers.

    The same photograph is put into template space twice -- once by the corners
    the detector found, and once by those corners turned by
    ``MISALIGNED_BY_DEGREES``.  Only the alignment differs, so the score cannot
    have moved for any other reason, and a metric that answered the same number
    twice would fail here.

    Both are checked to exist before they are compared: ``None`` is an absence
    of measurement rather than a low score, and comparing it would say nothing.
    """
    photo = capture(reference_image())
    found = detect_corners(photo)
    straight = layout.layout_score(
        align.warp_to_template(photo, TEMPLATE, found), TEMPLATE
    )
    turned = layout.layout_score(
        align.warp_to_template(photo, TEMPLATE, misaligned(found)), TEMPLATE
    )

    assert straight is not None and turned is not None
    assert straight > 0.5
    assert turned < straight


def test_the_lower_score_is_the_field_off_its_own_rectangle():
    """The drop is measured: the one measured field is no longer where the layout puts it.

    The support 13.9's own test promised 13.11.  The field sits inside its own
    tolerance once the capture is straightened and outside it once it is not,
    and 13.9's finding says the same thing per field -- so the document-level
    score and the field-level flag are one measurement read two ways.
    """
    photo = capture(reference_image())
    found = detect_corners(photo)
    straight = align.warp_to_template(photo, TEMPLATE, found)
    turned = align.warp_to_template(photo, TEMPLATE, misaligned(found))

    def deviation(frame):
        measured = {one.field: one for one in layout.field_deviations(frame, TEMPLATE)}
        assert INKED_FIELD in measured, f"nothing measured for {INKED_FIELD!r}"
        return measured[INKED_FIELD]

    assert deviation(straight).deviation <= TOLERANCES[INKED_FIELD]
    assert deviation(turned).deviation > TOLERANCES[INKED_FIELD]
    assert layout.compare_layout(turned, TEMPLATE) != ()
    assert layout.compare_layout(straight, TEMPLATE) == ()


@pytest.mark.parametrize("frame", [np.zeros((10, 10), np.uint8), "not a frame", None])
def test_font_style_refuses_a_frame_that_is_not_three_channels(frame):
    """Template space is a three-channel frame, as ``align`` hands it over."""
    with pytest.raises(ValueError) as refused:
        layout.font_style(frame)

    assert "three-channel" in str(refused.value)
