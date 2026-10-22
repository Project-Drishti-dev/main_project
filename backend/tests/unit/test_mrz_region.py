"""Part 4.1-4.2 -- the working image is rotated upright, then cut into ink.

The subject of this file is not OpenCV.  It is the claim that the angle comes
from :mod:`app.quality_checker.m7_skew` rather than from a second estimator
written here: two estimators for "how far round is this image" would agree on
a synthetic page and disagree on a held document, and only one of them would
be the one the quality gate already told the officer about.

4.2 adds the two steps after the rotation -- :func:`mrz_region.to_gray` and
:func:`mrz_region.binarize_inverted` -- and the subject there is equally not a
pair of OpenCV calls.  It is that the cut is *local*, because 4.1 deliberately
did not assume the paper was white, and that the ink comes out as the white,
because everything from 4.3 onwards reads ink as "the thing to look at".
"""

import ast
import dataclasses
import math
import pathlib
import statistics
import subprocess
import sys

import cv2
import numpy as np
import pytest

from app.pipeline.tier0 import document, mrz, mrz_region, td1, td2, td3
from app.quality_checker import m7_skew
from tests.fixtures import mrz_images


# --- the fixture ---------------------------------------------------------

# 4.14 builds the real generator for all three formats; this one is the
# smallest thing that has a *measurable* tilt, and it is deliberately written
# here rather than imported so that 4.1's test says what 4.1 does.  Width and
# height, because that is the order every OpenCV call in this file takes them
# in, and the one thing a fixture should not add is an order to remember.
PAGE_WIDTH, PAGE_HEIGHT = 600, 300
LINES = ("P<UTOERIKSSON<<ANNA<MARIA", "L898902C36UTO7408122F1204159")


def upright_mrz():
    """A white page with two lines of MRZ glyphs on it, in BGR."""
    height, width = PAGE_HEIGHT, PAGE_WIDTH
    image = np.full((height, width, 3), 255, np.uint8)
    for row, text in enumerate(LINES):
        cv2.putText(
            image, text, (40, 120 + 70 * row),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA,
        )
    return image


def rotated_mrz(angle):
    """The same page, turned by ``angle`` degrees about its centre.

    Filled with a per-channel white, for the reason ``_border_fill``'s
    docstring gives: a scalar ``borderValue`` would make these corners blue.
    """
    height, width = PAGE_HEIGHT, PAGE_WIDTH
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
    return cv2.warpAffine(
        upright_mrz(), matrix, (width, height),
        borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
    )


def measured_tilt(image):
    """The tilt of the ink in degrees, read by m7_skew's *other* estimator.

    Deliberately not the estimator ``deskew`` follows.  ``m7_skew.text_skew``
    in scan mode searches a row-projection profile; this is the photo-mode
    ``minAreaRect``, which shares no code with it and agrees with the angle the
    fixture was built with.  A test that measured the result with the same
    function that produced it would pass on a sign flip, because a sign flip
    makes the estimator confidently wrong rather than wrong-looking.
    """
    return m7_skew.text_skew(image, mode="photo")


def ink_pixels(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    return int(np.count_nonzero(binary))


# --- the task's test -----------------------------------------------------


def test_a_deliberately_rotated_image_comes_back_upright():
    # The test 4.1 asks for.  Both halves matter: the corrected page has to be
    # flat *and* the starting page has to be visibly tilted, or the assertion
    # below is one an identity function would also pass.
    tilted = rotated_mrz(5.0)
    corrected = mrz_region.deskew(tilted)

    assert abs(measured_tilt(tilted)) > 4.0, "the fixture is not actually tilted"
    assert abs(measured_tilt(corrected)) <= 0.5


# --- and the sign, which is the whole of it ------------------------------


@pytest.mark.parametrize(
    "angle",
    [
        pytest.param(1.0, id="one-degree-clockwise"),
        pytest.param(-2.5, id="two-and-a-half-degrees-anticlockwise"),
        pytest.param(5.0, id="five-degrees-clockwise"),
        pytest.param(-5.0, id="five-degrees-anticlockwise"),
        pytest.param(8.0, id="eight-degrees-clockwise"),
        pytest.param(-8.0, id="eight-degrees-anticlockwise"),
    ],
)
def test_every_angle_is_corrected_in_the_direction_that_undoes_it(angle):
    # Each rotation is paired with its mirror in this list on purpose.  An
    # estimator whose sign was taken the wrong way round would pass on the
    # first of a pair and fail on the second, and a helper that applied the
    # negation of the reading would leave ~2x the tilt on *both*.
    tilted = rotated_mrz(angle)
    corrected = mrz_region.deskew(tilted)

    assert abs(measured_tilt(tilted)) >= abs(angle) - 0.5
    assert abs(measured_tilt(corrected)) <= 0.5


def test_the_corrected_page_is_the_flat_page_and_not_a_blank_one():
    # Deskew rotates; it does not redraw.  An implementation that filled the
    # frame (rather than the corners) would satisfy the tilt assertion above
    # and hand 4.2 an empty image to threshold.
    corrected = mrz_region.deskew(rotated_mrz(5.0))

    assert ink_pixels(corrected) == pytest.approx(ink_pixels(upright_mrz()), rel=0.1)


# --- the frame does not move ---------------------------------------------


def test_the_frame_is_unchanged_so_a_region_means_the_same_pixel_afterwards():
    # 4.8 emits polygons and 4.12 returns field boxes, both in image pixels,
    # and 11.2 draws them on the image the officer is looking at.  A deskew
    # that enlarged the canvas would offset every one of them, and nothing
    # downstream carries an offset.
    corrected = mrz_region.deskew(rotated_mrz(6.0))

    assert corrected.shape == (PAGE_HEIGHT, PAGE_WIDTH, 3)
    assert corrected.dtype == np.uint8


def test_the_new_corners_take_the_images_own_median_colour():
    # The blue-corner trap: OpenCV reads a scalar borderValue as (v, 0, 0) on a
    # three-channel image, so a scalar white fill fills blue, which binarises
    # as ink and hands 4.3 a component spanning the whole page.
    corrected = mrz_region.deskew(rotated_mrz(6.0))
    corner = corrected[0, 0]

    assert int(corner[0]) == int(corner[1]) == int(corner[2])
    assert int(corner[0]) > 200


def test_a_page_that_is_already_upright_keeps_its_pixels():
    # Not an identity claim -- deskew still resamples, and the reading on an
    # upright page is a couple of 1e-16 rather than a true zero.  What is
    # claimed is the one an officer would care about: straightening a good
    # photograph does not touch a single pixel of it, so the glyphs 4.2 is
    # about to threshold are the glyphs that were captured.
    page = upright_mrz()

    assert np.array_equal(mrz_region.deskew(page), page)


# --- the reuse, which is the point ---------------------------------------


def test_the_angle_is_m7_skews_own_reading_and_not_a_second_measurement():
    tilted = rotated_mrz(4.0)

    assert mrz_region.skew_deg(tilted) == m7_skew.text_skew(tilted, mode="scan")
    assert mrz_region.skew_deg(tilted, mode="photo") == m7_skew.text_skew(
        tilted, mode="photo"
    )


def test_the_rotation_follows_m7_skews_reading_when_that_reading_changes(
    monkeypatch,
):
    # The strongest form of "reuses": stand a sentinel in m7_skew's place and
    # assert the image comes out rotated by exactly the sentinel.  A local
    # estimator would ignore the sentinel and this would still pass on a
    # fixture that happened to be tilted by the same amount.
    tilted = rotated_mrz(5.0)
    sentinel = 3.0
    monkeypatch.setattr(m7_skew, "text_skew", lambda image, mode="scan": sentinel)

    corrected = mrz_region.deskew(tilted)
    height, width = PAGE_HEIGHT, PAGE_WIDTH
    expected = cv2.warpAffine(
        tilted,
        cv2.getRotationMatrix2D((width / 2.0, height / 2.0), sentinel, 1.0),
        (width, height),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    assert np.array_equal(corrected, expected)


def test_the_largest_angle_deskew_will_act_on_is_the_quality_gates_own():
    # Not a restated number.  `MAX_SKEW_DEG` is where m7_skew's verdict is
    # already a failure, and a second constant would be a second definition of
    # "too rotated" that could drift from the one on the officer's screen.
    assert mrz_region.MAX_DESKEW_DEG == m7_skew.MAX_SKEW_DEG


@pytest.mark.parametrize("reading", [0.0, 1.0, -1.0])
def test_any_angle_inside_the_bound_is_rotated_by(reading, monkeypatch):
    image = upright_mrz()
    monkeypatch.setattr(mrz_region, "skew_deg", lambda image, mode="scan": reading)

    result = mrz_region.deskew(image)

    assert result is not image
    assert result.shape == image.shape


@pytest.mark.parametrize(
    "reading",
    [0.0, 3.0, -3.0, mrz_region.MAX_DESKEW_DEG, -mrz_region.MAX_DESKEW_DEG],
)
def test_the_bound_itself_is_applied_and_is_not_off_by_one(reading, monkeypatch):
    # `>` and not `>=`: a document at exactly the gate's threshold is one the
    # gate passes, so refusing to straighten it would make this helper
    # disagree with the verdict printed above it on the same screen.
    image = upright_mrz()
    monkeypatch.setattr(mrz_region, "skew_deg", lambda image, mode="scan": reading)

    assert mrz_region.deskew(image) is not image


@pytest.mark.parametrize(
    "reading",
    [
        pytest.param(mrz_region.MAX_DESKEW_DEG + 0.1, id="just-past-the-bound"),
        pytest.param(-mrz_region.MAX_DESKEW_DEG - 0.1, id="and-the-other-way"),
        pytest.param(14.9, id="where-m7-skews-search-runs-out"),
        pytest.param(None, id="and-no-text-to-measure"),
    ],
)
def test_a_rotation_the_gate_would_have_rejected_is_not_applied(reading, monkeypatch):
    # Past the bound, m7_skew's reading is the edge of its own search rather
    # than a measurement of the page, and rotating by it can leave the image
    # less upright than it was.  Returning the frame untouched is also what a
    # blank image needs: the scan estimator answers an empty page with the end
    # of its search range, which lands here too.
    image = upright_mrz()
    monkeypatch.setattr(mrz_region, "skew_deg", lambda image, mode="scan": reading)

    result = mrz_region.deskew(image)

    assert result is image


@pytest.mark.parametrize("mode", ["scan", "photo"])
def test_a_page_with_no_text_on_it_is_returned_unchanged(mode):
    blank = np.full((200, 400, 3), 255, np.uint8)

    assert mrz_region.deskew(blank, mode=mode) is blank


def test_deskew_never_returns_a_different_size_for_a_different_reason():
    # Two ways this could go wrong that the tilt test cannot see: a canvas
    # that silently changed size, and a fill that swallowed the glyphs.  Both
    # are checked above; this is the cheap total statement of "the page that
    # comes out is the page that went in, rotated".
    tilted = rotated_mrz(7.0)
    corrected = mrz_region.deskew(tilted)

    assert corrected.shape == tilted.shape
    assert not np.array_equal(corrected, tilted)


# =========================================================================
# 4.2 -- to_gray, then binarize_inverted
# =========================================================================

# The frames the two steps are handed.  All three are built *on top of*
# `upright_mrz` rather than beside it, because 4.14 replaces that one fixture
# for all three formats and a second generator would be a second thing to
# reconcile against it.

#: The dimmest a photographed page gets on the far side of the lamp.  A factor
#: rather than a grey level, so the fixture is a *shadow* and not a different
#: piece of paper: the glyphs stay 0 and the paper falls off across the page.
SHADOW_FLOOR = 0.5

#: Sigma of the sensor noise, in grey levels, for the grain case.  6 is
#: visible grain on a cheap capture rather than a camera fault.
GRAIN_SIGMA = 6.0

#: Distance between the two text baselines in `upright_mrz`, in pixels -- the
#: MRZ line pitch, which is one of the three rules the block size is held to.
LINE_PITCH = 70


def shadowed_mrz(floor=SHADOW_FLOOR):
    """The fixture as a photograph: a lamp at the left edge, shade at the right."""
    ramp = np.linspace(1.0, floor, PAGE_WIDTH, dtype=np.float32)[None, :, None]
    return np.clip(upright_mrz().astype(np.float32) * ramp, 0, 255).astype(np.uint8)


def dim_mrz(level=90):
    """The fixture photographed in low light: everything darker, nothing uneven."""
    return (upright_mrz().astype(np.float32) * (level / 255.0)).astype(np.uint8)


def grainy_mrz(sigma=GRAIN_SIGMA, seed=7):
    """The fixture with sensor grain on it.  Fixed seed, so a failure repeats."""
    rng = np.random.default_rng(seed)
    page = upright_mrz().astype(np.float32)
    return np.clip(page + rng.normal(0.0, sigma, page.shape), 0, 255).astype(np.uint8)


def glyph_mask(grow=1):
    """Where the fixture's ink is: the same two lines drawn without smoothing.

    `upright_mrz` draws with ``LINE_AA``, so the ink it puts down is a fringe
    of greys around a solid core, and a threshold is meant to find the fringe
    too.  This is the core, grown by ``grow`` pixels so the comparison allows
    for it -- the fixture is *drawn*, which is the one thing about it that
    makes a ground truth available at all.
    """
    mask = np.zeros((PAGE_HEIGHT, PAGE_WIDTH), np.uint8)
    for row, text in enumerate(LINES):
        cv2.putText(
            mask, text, (40, 120 + 70 * row),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2, cv2.LINE_8,
        )
    return cv2.dilate(mask, np.ones((2 * grow + 1, 2 * grow + 1), np.uint8))


def ink_fraction(binary):
    """The share of the page that is ink.  "Mostly binary" has to be measured."""
    return float(np.count_nonzero(binary)) / binary.size


def _widest_and_tallest(binary):
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        return 0, 0
    return (
        int(stats[1:, cv2.CC_STAT_WIDTH].max()),
        int(stats[1:, cv2.CC_STAT_HEIGHT].max()),
    )


def widest_component(binary):
    return _widest_and_tallest(binary)[0]


def tallest_component(binary):
    return _widest_and_tallest(binary)[1]


def row_bands(binary):
    """How many separate strips of rows carry any ink at all.

    Two lines of MRZ on a page are two bands.  A cut that has lost the page --
    a global threshold across a shadow, a polarity flip, a blank frame -- gives
    one, or none, and this is the cheapest way to say so.  Deliberately has no
    threshold in it: ``grainy_mrz`` is the frame this cannot answer for, and
    the tests below say what it can answer instead.
    """
    rows = np.flatnonzero(binary.any(axis=1))
    if rows.size == 0:
        return 0
    return 1 + int(np.count_nonzero(np.diff(rows) > 1))


def one_cut_for_the_whole_page(gray):
    """The alternative this task does not take: a single Otsu cut.

    Not a straw man -- it is the estimator ``m7_skew`` itself uses to find
    text to measure a skew on, and it is the right answer for a flat scan.
    It is written out longhand here because the two have to be compared on the
    same frame, and a test that only asserted what the local cut does could
    not tell a deliberate choice from a lucky fixture.
    """
    out = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return (np.asarray(out[-1]) > 0).astype(np.uint8) * 255


def cut_with(gray, block, offset):
    """``binarize_inverted`` with the module's constants stood aside."""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, block, offset,
    )


FRAMES = {
    "flat-scan": upright_mrz,
    "one-sided-shadow": shadowed_mrz,
    "low-light": dim_mrz,
}


# --- the task's own test -------------------------------------------------


def test_the_mrz_glyphs_come_back_white_on_black():
    # The test 4.2 asks for.  Polarity is the half that is easy to get
    # backwards: THRESH_BINARY is the flag most snippets reach for, and it
    # hands 4.3 one full-page component to reject before it has read a glyph.
    binary = mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz()))

    assert set(np.unique(binary)) == {0, 255}
    assert row_bands(binary) == 2


def test_the_white_is_the_glyphs_and_nothing_outside_them():
    # A polarity claim measured against the fixture's own drawing rather than
    # against a proxy.  Zero white outside the glyphs is the strong half: the
    # other way round puts ~174,000 pixels of paper outside it, so this fails
    # on a THRESH_BINARY swap and on a global cut alike, for different reasons.
    mask = glyph_mask() > 0
    white = mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz())) > 0

    assert int(np.count_nonzero(white & ~mask)) == 0
    assert int(white.sum()) > 0


def test_the_cut_finds_at_least_as_much_ink_as_a_hard_cut_does():
    # The other half of the same question.  An adaptive cut is a *lower* bar
    # than a fixed one in shadow and a *higher* one in light, so it can drop
    # the anti-aliased edge of a stroke as easily as it can add one.  This
    # says it is not quietly eating the fixture's glyphs: it finds every pixel
    # a 127 cut finds, and not many more.
    gray = mrz_region.to_gray(upright_mrz())
    hard = int(np.count_nonzero(cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)[1]))
    found = int(np.count_nonzero(mrz_region.binarize_inverted(gray)))

    assert hard <= found <= hard * 1.5


# --- single channel, which is the other half of the task's test ----------


@pytest.mark.parametrize("name", FRAMES)
def test_both_steps_hand_back_one_channel_at_the_size_they_were_given(name):
    # 4.1 spent a test on this and it is still true after 4.2: 4.8 emits
    # polygons and 4.12 returns field boxes in image pixels, and every one of
    # them is meaningless against a frame the pipeline quietly resized.
    image = FRAMES[name]()
    gray = mrz_region.to_gray(image)
    binary = mrz_region.binarize_inverted(gray)

    assert gray.shape == (PAGE_HEIGHT, PAGE_WIDTH)
    assert gray.dtype == np.uint8
    assert binary.shape == gray.shape
    assert binary.dtype == np.uint8


@pytest.mark.parametrize("name", FRAMES)
def test_the_output_is_two_values_and_not_a_greyscale(name):
    # "Binary" asserted as an exact set rather than as a proportion.  A helper
    # that returned the threshold's input, or a blurred page, would have a
    # plausible mean and fail here.
    binary = mrz_region.binarize_inverted(mrz_region.to_gray(FRAMES[name]()))

    assert set(np.unique(binary)) == {0, 255}


@pytest.mark.parametrize("name", FRAMES)
def test_the_output_is_mostly_paper(name):
    # The other reading of "mostly", and the one 4.3 depends on: if ink were
    # the majority then the component 4.3 is about to find is the page.  The
    # band is measured across all four frames rather than asserted: 2.6% on
    # the flat scan, 2.9% under the shadow, 2.8% in low light, 3.0% with grain.
    binary = mrz_region.binarize_inverted(mrz_region.to_gray(FRAMES[name]()))

    assert 0.01 < ink_fraction(binary) < 0.15


@pytest.mark.parametrize("name", FRAMES)
def test_the_white_falls_in_the_two_bands_the_lines_are_printed_in(name):
    # Where, not how much.  Two lines of MRZ are two row bands, and this is
    # the assertion that fails first on a polarity flip, on a blank frame, and
    # on a page whose shadow has been read as ink end to end.
    binary = mrz_region.binarize_inverted(mrz_region.to_gray(FRAMES[name]()))

    assert row_bands(binary) == 2


def test_to_gray_hands_back_a_frame_that_is_already_single_channel():
    # The opposite of `deskew`'s deliberate refusal, and for a stated reason:
    # here the conversion is the job, so a frame that has been converted is
    # already the answer.  The same object rather than a copy, as `deskew`
    # does, so a caller can tell "nothing to do" from "this made a copy".
    gray = mrz_region.to_gray(upright_mrz())

    assert mrz_region.to_gray(gray) is gray


def test_the_greyscale_is_weighted_luma_and_not_the_mean_of_three_channels():
    # The three primaries, filled in BGR, against the mean that a channel
    # average would give.  A mean says a saturated red and a saturated blue are
    # the same brightness, which is how blue ink or a red security tint ends up
    # sitting exactly where black belongs.  The values are the longhand ones,
    # not read back from the call, so a change of weights fails here.
    readings = {
        (0, 0, 255): 76,     # red
        (0, 255, 0): 150,   # green
        (255, 0, 0): 29,    # blue
        (128, 128, 128): 128,
    }

    for bgr, expected in readings.items():
        assert int(mrz_region.to_gray(np.full((1, 1, 3), bgr, np.uint8))[0, 0]) == expected
    assert sum((0, 0, 255)) // 3 == 85, "a channel mean would read 85 for all three"


# --- why the cut is local, which is the reason the task says adaptive -----


def test_one_cut_for_the_whole_page_would_read_the_shadowed_half_as_ink():
    # Both halves of the comparison on one frame, because a test asserting
    # only what the local cut does could not tell a decision from a fixture
    # that happened to be evenly lit.  4.1 is the reason this matters: it
    # filled the new corners with the image's own median precisely because the
    # paper cannot be assumed white, and a single cut inherits that assumption
    # straight back.  Measured on this fixture: 88% of the shadowed half
    # against 2.9% of the page.
    page = shadowed_mrz()
    shadowed_half = PAGE_WIDTH // 2
    gray = mrz_region.to_gray(page)
    local = mrz_region.binarize_inverted(gray)
    one_cut = one_cut_for_the_whole_page(gray)

    assert ink_fraction(local[:, shadowed_half:]) < 0.10
    assert ink_fraction(one_cut[:, shadowed_half:]) > 0.50
    assert widest_component(local) < 40
    assert widest_component(one_cut) > 200


def test_the_cut_travels_with_the_paper_so_a_shadowed_page_still_reads_the_same():
    # The claim underneath the one above, in the form 4.3 would experience it:
    # a shadowed page and a flat page of the same document come back with the
    # same amount of ink in the same two places.  A global cut does not manage
    # either -- it puts the shadowed page's bands together into one.
    flat = mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz()))
    shaded = mrz_region.binarize_inverted(mrz_region.to_gray(shadowed_mrz()))

    assert ink_fraction(shaded) == pytest.approx(ink_fraction(flat), rel=0.10)
    assert row_bands(shaded) == row_bands(flat) == 2
    assert row_bands(one_cut_for_the_whole_page(mrz_region.to_gray(shadowed_mrz()))) == 1


def test_low_light_alone_does_not_need_the_local_cut_and_this_does_not_claim_it():
    # The honest limit of the claim above, written down as a test so nobody
    # widens it later.  Dimming the whole page moves every pixel and the local
    # mean with it, so a single cut handles that fine; what defeats a single
    # cut is a page that is *uneven*, and only that is claimed.
    dim = mrz_region.binarize_inverted(mrz_region.to_gray(dim_mrz()))

    assert ink_fraction(dim) == pytest.approx(ink_fraction(
        mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz()))), rel=0.10)


# --- the order, which 4.1 fixed: deskew, to_gray, binarize_inverted ------


def test_the_whole_chain_still_lands_on_the_two_lines_of_a_tilted_page():
    # 4.1's handover fixes the order and 4.2 sits inside it.  Run end to end
    # from a deliberately tilted page: the frame is the one that went in, and
    # the ink is on the lines rather than on the corners the rotation opened.
    tilted = rotated_mrz(5.0)
    binary = mrz_region.binarize_inverted(
        mrz_region.to_gray(mrz_region.deskew(tilted))
    )

    assert binary.shape == (PAGE_HEIGHT, PAGE_WIDTH)
    assert row_bands(binary) == 2
    assert ink_fraction(binary) == pytest.approx(ink_fraction(
        mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz()))), rel=0.10)


# --- the two constants, and what each of them is for ----------------------


def test_an_offset_of_zero_reads_the_paper_as_ink_and_this_one_does_not():
    # Not a taste claim.  `THRESH_BINARY_INV` marks a pixel white when it is
    # at or below `local mean - C`, so at C = 0 a *uniform* page compares equal
    # to its own neighbourhood mean and every one of its pixels becomes ink:
    # 84% of the flat fixture is white there, against 2.9% here.  A helper
    # that stood the offset at zero would satisfy every other test here and
    # hand 4.3 one component the width of the page.
    gray = mrz_region.to_gray(upright_mrz())

    assert mrz_region.ADAPTIVE_C > 0
    assert ink_fraction(cut_with(gray, mrz_region.ADAPTIVE_BLOCK_SIZE, 0)) > 0.50
    assert ink_fraction(mrz_region.binarize_inverted(gray)) < 0.10


def test_sensor_grain_does_not_run_the_page_white():
    # The second job the offset does, and the reason it is not tuned down to
    # the last grey level.  Grain is the case where a local mean alone is not
    # enough, because a single dark speck is darker than its neighbourhood
    # whatever that neighbourhood is.
    gray = mrz_region.to_gray(grainy_mrz())
    clean = mrz_region.to_gray(upright_mrz())

    assert ink_fraction(mrz_region.binarize_inverted(gray)) == pytest.approx(
        ink_fraction(mrz_region.binarize_inverted(clean)), rel=0.50)
    assert ink_fraction(cut_with(gray, mrz_region.ADAPTIVE_BLOCK_SIZE, 0)) > 0.30


def test_grain_leaves_the_glyphs_the_size_the_rest_of_part_4_filters_on():
    # What the grain *is* allowed to do, said as a test rather than left to
    # 4.4: it makes isolated single pixels, and on this fixture it makes whole
    # rows of them, so no row-band claim survives it.  The claim that does
    # survive is the one 4.4 is about -- the largest and the tallest component
    # are the same glyph they are on a clean page, so the height band it is
    # about to write rejects the speckle and keeps the print.
    flat = mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz()))
    grain = mrz_region.binarize_inverted(mrz_region.to_gray(grainy_mrz()))

    assert _widest_and_tallest(grain) == _widest_and_tallest(flat) == (22, 15)


def test_the_block_size_obeys_the_three_rules_it_is_pinned_on():
    # Odd, because OpenCV refuses an even neighbourhood; at least twice a
    # glyph, or the window is small enough to measure the glyph's own level
    # and stops being a cut relative to the paper; and under a line pitch, or a
    # pixel in the gap between two MRZ lines takes both lines' ink into its
    # mean.  The two sizes are measured from the fixture rather than restated
    # here, so 4.14 replacing the generator cannot quietly invalidate the rule.
    binary = mrz_region.binarize_inverted(mrz_region.to_gray(upright_mrz()))
    glyph = tallest_component(binary)

    assert mrz_region.ADAPTIVE_BLOCK_SIZE % 2 == 1
    assert mrz_region.ADAPTIVE_BLOCK_SIZE >= 2 * glyph
    assert mrz_region.ADAPTIVE_BLOCK_SIZE < LINE_PITCH
    assert glyph == 15


def test_the_reading_does_not_depend_on_which_odd_block_is_used():
    # The measurement behind the test above being a *rule* rather than a tuned
    # optimum: every odd block from 11 to 61 gives the same reading on this
    # fixture.  So the constant is held to the three rules and not to a number
    # that happened to be tried first, and a later task that needs a different
    # block has to re-run this before it may claim the same answer.
    gray = mrz_region.to_gray(upright_mrz())
    readings = {
        block: cut_with(gray, block, mrz_region.ADAPTIVE_C) for block in range(11, 62, 2)
    }
    module_reading = mrz_region.binarize_inverted(gray)

    assert len(readings) == 26
    for block, binary in readings.items():
        assert ink_fraction(binary) == pytest.approx(
            ink_fraction(module_reading), rel=0.15
        ), f"block {block} reads differently"
        assert tallest_component(binary) == tallest_component(module_reading)


# --- the caller's mistake, left visible ----------------------------------


def test_a_colour_frame_handed_to_binarize_is_not_papered_over():
    # The same `cv2.error` 4.1 documents for `deskew`, and for a related
    # reason: this function reads a frame the caller already holds rather than
    # measuring one, so converting quietly would hide a mistake in the caller
    # behind an answer that looked fine.  The two functions are separate so
    # the channel question is settled in `to_gray`, where it is known.
    with pytest.raises(cv2.error):
        mrz_region.binarize_inverted(upright_mrz())


# --- 4.3: the ink, numbered and measured ----------------------------------

# 4.14 replaces `upright_mrz` with a generator for all three formats, so
# everything below reads the fixture through `LINES` rather than through a
# count written here.  A plausible component count is a property of what was
# drawn, and what was drawn is these two strings.

#: Every character the fixture prints, across both lines.  The ceiling on a
#: component count, because a blob holds at least one character's ink and a
#: component with nothing behind it is a cut that failed.
PRINTED_CHARACTERS = sum(len(line) for line in LINES)


def binary_of(frame):
    return mrz_region.binarize_inverted(mrz_region.to_gray(frame))


def components_of(frame):
    """The whole chain, so a test names the pipeline it is testing."""
    return mrz_region.extract_components(binary_of(frame))


def solid_frame(*blocks):
    """A binary frame with known rectangles on it, in ``(x, y, w, h)`` order."""
    height = max(y + h for _, y, _, h in blocks) + 4
    width = max(x + w for x, _, w, _ in blocks) + 4
    frame = np.zeros((height, width), np.uint8)
    for x, y, w, h in blocks:
        frame[y:y + h, x:x + w] = 255
    return frame


def drawn_extent():
    """The fixture's ink as the ``(top, bottom, left, right)`` it occupies.

    Measured off ``glyph_mask`` rather than written down, for the reason 4.2
    drew that mask at all: the fixture is *drawn*, which is the one thing
    about it that makes a ground truth available, and a box held as a literal
    here would be a second thing for 4.14 to invalidate.
    """
    rows, cols = np.nonzero(glyph_mask())
    return rows.min(), rows.max(), cols.min(), cols.max()


def test_a_two_line_page_comes_back_as_a_plausible_number_of_glyphs():
    # The test 4.3 asks for.  "Plausible" is four claims and not one, because
    # a bare count is satisfied by a page that went white and came back as a
    # single component just as comfortably as by two lines of print.
    binary = binary_of(upright_mrz())
    components = components_of(upright_mrz())

    # One blob per printed character at most, and no more than a quarter of
    # them merged into a neighbour.  Measured: 51, from 53.
    assert len(components) <= PRINTED_CHARACTERS
    assert len(components) >= 3 * PRINTED_CHARACTERS // 4

    # The list covers the ink exactly.  The areas partition the white pixels,
    # so this fails if a component is dropped, counted twice, or if the page
    # sneaks back in as a component of its own.
    assert sum(c.area for c in components) == int(np.count_nonzero(binary))

    # Every blob is a glyph and not a photograph, a frame edge, or a corner
    # 4.1 filled: all of them sit inside the ink the fixture drew.
    top, bottom, left, right = drawn_extent()
    for c in components:
        assert left <= c.left and c.bbox[2] <= right + 1
        assert top <= c.top and c.bbox[3] <= bottom + 1

    # And the extremes are 4.2's own numbers, read by 4.2's own helper rather
    # than by this task's.  4.4's height band is about to be written against
    # them, and the two tasks have to stay checkable against each other.
    assert max(c.width for c in components) == widest_component(binary)
    assert max(c.height for c in components) == tallest_component(binary)


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_the_count_is_the_same_on_every_clean_capture(name):
    # The three ways 4.2 photographs a page -- flat, one-sided shadow, low
    # light -- have to agree about how much ink there is, or 4.4's band is
    # being written against a fixture that flatters itself.  Measured: 51, 51
    # and 52, so the band is two wide rather than one.
    count = len(components_of(FRAMES[name]()))

    assert count <= PRINTED_CHARACTERS
    assert count >= PRINTED_CHARACTERS - 5


def test_a_grainy_capture_is_not_cleaned_up_here():
    # 4.3 numbers what the cut produced; 4.4 decides what a glyph is.  A
    # function that filtered here would be applying a band nobody wrote down,
    # and the handover's note about 4.4 possibly needing an area filter is
    # exactly the failure this exists to catch.  Measured: 313 components on
    # the grainy frame against 51 on the clean one, single-pixel areas among
    # them.
    clean = components_of(upright_mrz())
    grainy = components_of(grainy_mrz())

    assert len(grainy) > 3 * len(clean)
    assert min(c.area for c in grainy) < min(c.area for c in clean)

    # The claim 4.4 rests on, restated through this task's own output: the
    # speckle adds blobs and takes none of the print away.
    assert max(c.width for c in grainy) == max(c.width for c in clean)
    assert max(c.height for c in grainy) == max(c.height for c in clean)


def test_every_number_is_measured_against_the_frame_it_came_from():
    # The task's other half.  A count cannot tell a correct measurement from a
    # plausible one, so the box, the extent and the area are checked against
    # rectangles whose coordinates are written in the test.
    components = mrz_region.extract_components(
        solid_frame((10, 20, 5, 7), (40, 20, 3, 9), (40, 60, 30, 10))
    )

    assert [c.bbox for c in components] == [
        (10, 20, 15, 27), (40, 20, 43, 29), (40, 60, 70, 70),
    ]
    assert [c.width for c in components] == [5, 3, 30]
    assert [c.height for c in components] == [7, 9, 10]
    assert [c.area for c in components] == [35, 27, 300]


def test_the_centroid_is_the_mean_of_the_pixels_and_not_the_middle_of_the_box():
    # A staircase: solid, and nothing like its own box.  4.9 fits a line
    # through these to find the residual skew inside a line, so a box centre
    # would tilt that fit towards whichever glyph shape is in the group.
    staircase = np.zeros((20, 20), np.uint8)
    staircase[2:4, 2:12] = 255
    staircase[4:6, 4:12] = 255
    staircase[6:8, 6:12] = 255

    (component,) = mrz_region.extract_components(staircase)

    assert component.centroid == (component.cx, component.cy)
    assert component.cx == pytest.approx(7.333333, abs=1e-6)
    assert component.cy == pytest.approx(4.166667, abs=1e-6)
    # The reading it must not be confused with.
    assert component.cy != pytest.approx((component.bbox[1] + component.bbox[3]) / 2)
    assert (component.area, component.width, component.height) == (48, 10, 6)


def test_the_centroid_of_every_component_is_the_mean_of_its_own_pixels():
    # The staircase says the two readings differ; this says the one that was
    # chosen is right -- over every component of a real page rather than over
    # one hand-drawn shape.
    binary = binary_of(upright_mrz())
    _, labels, _, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=mrz_region.CONNECTIVITY
    )

    for component in mrz_region.extract_components(binary):
        # The box is tight, so the only label inside it is its own.
        window = labels[component.top:component.bbox[3],
                        component.left:component.bbox[2]]
        rows, cols = np.nonzero(window)

        assert component.cx == pytest.approx(component.left + cols.mean())
        assert component.cy == pytest.approx(component.top + rows.mean())
        assert component.left <= component.cx <= component.bbox[2]
        assert component.top <= component.cy <= component.bbox[3]


def test_the_box_is_half_open_and_says_which_one_it_is():
    # One pixel at (6, 4).  OpenCV's own cv::Rect counts the far edge in and
    # would call it (6, 4, 6, 4); the half-open form is what makes
    # `binary[top:top + height, left:left + width]` this component and nothing
    # else, which is the slice 4.8 and 4.12 are cut from.
    frame = np.zeros((10, 10), np.uint8)
    frame[4, 6] = 255

    (component,) = mrz_region.extract_components(frame)

    assert component.bbox == (6, 4, 7, 5)
    assert component.bbox != (6, 4, 6, 4)
    assert frame[component.top:component.bbox[3],
                 component.left:component.bbox[2]].sum() == 255


def test_the_numbers_are_plain_python_and_not_numpy_scalars():
    # 4.4 compares these against a band and 4.5 sorts them, and a record
    # carrying numpy.int32 is one that cannot go in a JSON body when 4.13's
    # empty result becomes a response.
    (component,) = mrz_region.extract_components(solid_frame((3, 4, 5, 6)))

    for value in (component.left, component.top, component.width,
                  component.height, component.area):
        assert type(value) is int
    for value in (component.cx, component.cy):
        assert type(value) is float


def test_the_record_is_frozen_and_compares_by_value():
    # 4.1's frame does not move, and neither does a measurement: a record that
    # could be edited would let a measured glyph become a convenient one.
    first = mrz_region.extract_components(solid_frame((3, 4, 5, 6)))[0]
    second = mrz_region.extract_components(solid_frame((3, 4, 5, 6)))[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        first.width = 99
    assert first == second
    assert hash(first) == hash(second)


def test_the_page_is_dropped_by_label_and_not_by_size():
    # The load-bearing half of 4.2's polarity decision, and the case it was
    # made for.  An all-ink frame is the page that went white: OpenCV numbers
    # the *empty* background anyway, so the first row of `stats` is the
    # sentinel [-1, 2147483647, 0, 0, 0] and the only real component is the
    # whole page.  Dropping the widest, the last or the largest-area row would
    # report a clean page here, and 4.4 would have nothing left to reject.
    components = mrz_region.extract_components(
        np.full((PAGE_HEIGHT, PAGE_WIDTH), 255, np.uint8)
    )

    assert len(components) == 1
    assert components[0].bbox == (0, 0, PAGE_WIDTH, PAGE_HEIGHT)
    assert components[0].area == PAGE_WIDTH * PAGE_HEIGHT

    # The same rule when the background is small rather than absent.  A page
    # that is all ink except a hole is still one component, so a reading that
    # dropped "the biggest blob" would return the hole instead.
    ring = np.full((40, 40), 255, np.uint8)
    ring[10:30, 10:30] = 0

    (component,) = mrz_region.extract_components(ring)

    assert component.bbox == (0, 0, 40, 40)
    assert component.area == 40 * 40 - 20 * 20


def test_a_page_with_no_ink_has_no_components():
    # 4.13 is where this becomes an empty result rather than a raise; the
    # input half is here so the two cannot drift apart.
    assert mrz_region.extract_components(
        np.zeros((PAGE_HEIGHT, PAGE_WIDTH), np.uint8)
    ) == ()


def test_two_glyphs_touching_diagonally_are_one_component():
    # What CONNECTIVITY is for, measured.  A diagonal pixel run is
    # 8-connected and not 4-connected, and MRZ strokes are diagonal -- the
    # leg of a 7, the crossbar of a 4.  Under 4-connectivity this
    # twelve-pixel stroke is twelve glyphs.
    stroke = np.zeros((20, 20), np.uint8)
    for step in range(12):
        stroke[2 + step, 2 + step] = 255

    assert mrz_region.CONNECTIVITY == 8
    assert len(mrz_region.extract_components(stroke)) == 1
    assert cv2.connectedComponentsWithStats(stroke, connectivity=4)[0] - 1 == 12


def test_the_connectivity_is_passed_by_keyword_and_not_positionally(monkeypatch):
    # OpenCV's signature is connectedComponentsWithStats(image[, labels[,
    # stats[, centroids[, connectivity[, ltype]]]]]) -- the second positional
    # parameter is the `labels` *output*, so a call written `(binary, 8)` binds
    # the 8 there and silently gets the default.  The default is 8, which is
    # why it cannot be noticed by looking at the answers; it shows up on a
    # diagonal stroke, where the positional form reports one component and
    # 4-connectivity reports twelve.
    stroke = np.zeros((20, 20), np.uint8)
    for step in range(12):
        stroke[2 + step, 2 + step] = 255

    assert cv2.connectedComponentsWithStats(stroke, 8)[0] == \
        cv2.connectedComponentsWithStats(stroke, 4)[0]
    assert cv2.connectedComponentsWithStats(
        stroke, connectivity=4
    )[0] - 1 == 12

    seen = {}
    original = cv2.connectedComponentsWithStats

    def record(image, *args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return original(image, connectivity=kwargs.get("connectivity", 8))

    monkeypatch.setattr(mrz_region.cv2, "connectedComponentsWithStats", record)
    mrz_region.extract_components(stroke)

    assert seen["args"] == ()
    assert seen["kwargs"] == {"connectivity": mrz_region.CONNECTIVITY}


def test_the_list_reads_down_the_page_and_then_across_it():
    # 4.5 groups by vertical overlap and 4.10 segments along x, so both want
    # this order and neither can want OpenCV's.  Asserting the sort is not
    # enough on its own: OpenCV numbers labels in raster-scan order, which is
    # already (top, left) on most frames, so the fixture is also checked for
    # being the frame where it is not.
    order = [(c.top, c.left) for c in components_of(upright_mrz())]

    assert order == sorted(order)
    assert len(set(order)) == len(order)

    count, _, stats, _ = cv2.connectedComponentsWithStats(
        binary_of(upright_mrz()), connectivity=mrz_region.CONNECTIVITY
    )
    as_labelled = [
        (int(stats[label, cv2.CC_STAT_TOP]), int(stats[label, cv2.CC_STAT_LEFT]))
        for label in range(1, count)
    ]
    assert as_labelled != sorted(as_labelled)


def test_a_colour_frame_handed_to_extract_components_is_not_papered_over():
    # 4.2's rule restated for this function: it reads a frame the caller
    # holds rather than measuring one, so a three-channel frame comes back as
    # a cv2.error rather than a quiet conversion.
    with pytest.raises(cv2.error):
        mrz_region.extract_components(upright_mrz())


def test_a_greyscale_frame_is_accepted_and_its_answer_is_the_page():
    # The other caller mistake, which is *not* caught, and saying so is the
    # point.  OpenCV reads every non-zero pixel as ink, so `to_gray`'s own
    # output handed straight in -- skipping `binarize_inverted` -- gives 24
    # components on this fixture and one of them spans the page.  That is the
    # page-turned-white failure reached by another route, and refusing it
    # would need a raise this module may not have.
    components = mrz_region.extract_components(
        mrz_region.to_gray(upright_mrz())
    )

    assert max(c.width for c in components) == PAGE_WIDTH
    assert len(components) < PRINTED_CHARACTERS


# =========================================================================
# 4.4 -- filter_glyphs: a height band and an aspect-ratio band
# =========================================================================

# The two blobs a document frame actually carries, added to the fixture on
# purpose rather than described.  Both are measured by the tests below before
# anything is claimed about them, because the whole point of the two cases the
# task names is *which half of the band* does the refusing, and that is only
# worth anything if each blob's own numbers are read off the frame.

#: The photo box, as ``(top, left, height, width)``.  Flat-toned on purpose:
#: a printed portrait is an even wash of tone, and -- the part worth knowing --
#: a *uniform* patch is not ink to a local cut at all, so what comes through
#: is the box's outline rather than its face.  It is still one blob of the
#: box's own size, which is the thing the height band has to refuse.
PHOTO_TOP, PHOTO_LEFT, PHOTO_HEIGHT, PHOTO_WIDTH, PHOTO_LEVEL = 40, 380, 120, 180, 60


def photo_page(level=PHOTO_LEVEL):
    """The fixture with a printed photo box on it, in the empty corner."""
    page = upright_mrz()
    page[PHOTO_TOP:PHOTO_TOP + PHOTO_HEIGHT, PHOTO_LEFT:PHOTO_LEFT + PHOTO_WIDTH] = level
    return page


def signature_page(amplitude=9, thickness=2):
    """The fixture with a signature's stroke on it -- one long thin curve.

    Amplitude 9 rather than the 18 a first attempt used, and that is the whole
    design of the case: the stroke has to come through the cut *inside* the
    height band, or the height half would refuse it and the aspect band would
    never be exercised at all.
    """
    page = upright_mrz()
    stroke = np.array(
        [[PHOTO_LEFT + i * 5, 230 - int(amplitude * np.sin(i / 2.2))] for i in range(30)],
        np.int32,
    )
    cv2.polylines(page, [stroke], False, (0, 0, 0), thickness, cv2.LINE_AA)
    return page


def component_at(components, left, top):
    """The one component whose box starts at ``(left, top)``, or None."""
    return next(
        (c for c in components if c.left == left and c.top == top), None
    )


def glyphs_of(frame):
    """The whole chain, filtered.  A test names the pipeline it is testing."""
    return mrz_region.filter_glyphs(components_of(frame))


def inside_drawn_glyphs(components):
    """Whether every blob sits inside the ink the fixture drew, 4.3's test."""
    top, bottom, left, right = drawn_extent()
    return all(
        left <= c.left and c.bbox[2] <= right + 1
        and top <= c.top and c.bbox[3] <= bottom + 1
        for c in components
    )


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_a_clean_page_keeps_every_glyph_it_printed(name):
    # The band has to be a filter and not a sieve.  All three ways 4.2
    # photographs a page -- flat, one-sided shadow, low light -- come through
    # 4.3 with a different count (51, 51, 52, because two pairs of neighbours
    # merge at different points on the cut), and the band has to be wide enough
    # for the widest of them and narrow enough to reject everything else.
    components = components_of(FRAMES[name]())
    glyphs = mrz_region.filter_glyphs(components)

    assert glyphs == components
    assert all(
        mrz_region.GLYPH_MIN_HEIGHT_PX <= c.height <= mrz_region.GLYPH_MAX_HEIGHT_PX
        and mrz_region.GLYPH_MIN_ASPECT
        <= c.width / c.height
        <= mrz_region.GLYPH_MAX_ASPECT
        for c in glyphs
    )


def test_a_large_photo_region_is_rejected():
    # The first case the task names, and the half of the band that has to do
    # it: a photo box is roughly as wide as it is tall, so its aspect ratio
    # sits inside the aspect band and only the height bound can refuse it.  If
    # the numbers below did not come out that way this test would be passing
    # for the wrong reason, so they are read off the frame first.
    components = components_of(photo_page())
    photo = component_at(components, PHOTO_LEFT, PHOTO_TOP)

    assert (photo.width, photo.height) == (PHOTO_WIDTH, PHOTO_HEIGHT)
    assert mrz_region.GLYPH_MIN_ASPECT <= photo.width / photo.height <= (
        mrz_region.GLYPH_MAX_ASPECT
    )

    glyphs = mrz_region.filter_glyphs(components)

    assert photo not in glyphs
    assert component_at(glyphs, PHOTO_LEFT, PHOTO_TOP) is None
    # And the box took nothing with it: the two lines of print are untouched,
    # and what is left is every survivor 4.3 measured on the bare fixture.
    assert len(glyphs) == len(components_of(upright_mrz()))
    assert inside_drawn_glyphs(glyphs)


def test_a_signature_blob_is_rejected():
    # The second case the task names, and the *other* half of the band: a
    # signature is a long horizontal scrawl whose own height is inside the
    # height band, so nothing but the aspect bound can refuse it.
    components = components_of(signature_page())
    signature = max(components, key=lambda c: c.width)

    assert mrz_region.GLYPH_MIN_HEIGHT_PX <= signature.height <= (
        mrz_region.GLYPH_MAX_HEIGHT_PX
    )
    assert signature.width / signature.height > mrz_region.GLYPH_MAX_ASPECT

    glyphs = mrz_region.filter_glyphs(components)

    assert signature not in glyphs
    assert len(glyphs) == len(components_of(upright_mrz()))
    assert inside_drawn_glyphs(glyphs)


def test_the_grain_falls_away_and_both_lines_stay():
    # 4.3's handover note said the band would be asked to do this, and this is
    # the claim it was resting on: the speckle a sigma-6 capture leaves behind
    # is one and two pixels tall, so the height floor removes every one of
    # 4.3's 313 components except the print -- and the print it keeps is the
    # print, not a handful of the blobs that happened to be big enough.
    components = components_of(grainy_mrz())
    glyphs = mrz_region.filter_glyphs(components)

    assert len(components) > 3 * len(components_of(upright_mrz()))
    assert len(glyphs) == len(components_of(upright_mrz()))
    assert inside_drawn_glyphs(glyphs)


def test_a_page_whose_cut_went_white_has_no_glyphs_to_group():
    # The failure 4.3 deliberately left in the list for this task: when 4.2's
    # cut loses the page the frame is entirely ink, and OpenCV leaves 4.3 a
    # single component 600 by 300.  Reporting that as a glyph would give 4.5 a
    # line of one and 4.7 a document type, so the ceiling is above every glyph
    # on this fixture and below a page.
    components = mrz_region.extract_components(np.full((PAGE_HEIGHT, PAGE_WIDTH), 255, np.uint8))

    assert [(c.width, c.height) for c in components] == [(PAGE_WIDTH, PAGE_HEIGHT)]
    assert mrz_region.filter_glyphs(components) == ()


def test_a_greyscale_frame_is_only_partly_cured_and_the_number_is_written_down():
    # 4.3's other open exposure, and the handover was explicit that this is
    # where it starts to hurt: skipping `binarize_inverted` gives 24
    # components with the page among them, and the band removes the page and
    # most of the rest but not all of it.  A caller gets a partial answer
    # rather than a loud failure, which is the worse of the two, so the number
    # is asserted here rather than left to be discovered in the field.
    components = mrz_region.extract_components(mrz_region.to_gray(upright_mrz()))
    glyphs = mrz_region.filter_glyphs(components)

    assert len(components) == 24
    assert max(c.width for c in components) == PAGE_WIDTH
    assert len(glyphs) == 6
    # Every survivor is a speck of *paper* rather than of print: a row band of
    # it that is 10 pixels tall -- inside the height band, unavoidably -- but
    # shorter than the shortest glyph the fixture drew, which is exactly the
    # shape a band cannot separate and the reason this stays a known limit.
    assert all(c.width < mrz_region.GLYPH_MIN_HEIGHT_PX for c in glyphs)
    assert max(c.height for c in glyphs) < min(
        c.height for c in components_of(upright_mrz())
    )


def test_the_band_is_held_to_the_rules_it_is_pinned_on():
    # The four constants are this project's own numbers and 4.14 replaces the
    # fixture they were measured on, so what is pinned here is the *rules*
    # rather than the readings: each bound is measured against the frame and
    # each rule is stated where it can be checked.
    binaries = {
        name: binary_of(FRAMES[name]()) for name in sorted(FRAMES)
    }
    heights = [
        c.height for binary in binaries.values()
        for c in mrz_region.extract_components(binary)
    ]
    aspects = [
        c.width / c.height for binary in binaries.values()
        for c in mrz_region.extract_components(binary)
    ]

    # Every glyph on the fixture is inside the band, at both ends.
    assert min(heights) > mrz_region.GLYPH_MIN_HEIGHT_PX
    assert max(heights) <= mrz_region.GLYPH_MAX_HEIGHT_PX
    assert min(aspects) > mrz_region.GLYPH_MIN_ASPECT
    assert max(aspects) < mrz_region.GLYPH_MAX_ASPECT

    # The floor is at least half the tallest glyph -- half is where a mark
    # stops being one -- and the ceiling is under half the line pitch, or a
    # glyph could be taller than the gap to the line above it.
    assert mrz_region.GLYPH_MIN_HEIGHT_PX * 2 >= max(heights)
    assert mrz_region.GLYPH_MAX_HEIGHT_PX <= LINE_PITCH // 2
    # An MRZ character cell is about square, so even a merged pair is nearer
    # 2:1; three is the generous end of what a character can be.
    assert mrz_region.GLYPH_MAX_ASPECT <= 3.0

    # And the band is two ordered bands, not four loose numbers.
    assert (
        0 < mrz_region.GLYPH_MIN_HEIGHT_PX < mrz_region.GLYPH_MAX_HEIGHT_PX
        and 0 < mrz_region.GLYPH_MIN_ASPECT < mrz_region.GLYPH_MAX_ASPECT
    )


@pytest.mark.parametrize(
    "width, height, kept",
    [
        # Exactly on each of the four bounds, and exactly a step outside it.
        # Off-by-one either way fails: the bounds are half-open nowhere.
        (5, mrz_region.GLYPH_MIN_HEIGHT_PX, True),
        (5, mrz_region.GLYPH_MIN_HEIGHT_PX - 1, False),
        (20, mrz_region.GLYPH_MAX_HEIGHT_PX, True),
        (20, mrz_region.GLYPH_MAX_HEIGHT_PX + 1, False),
        (2, 10, True),
        (1, 10, False),
        (20, 8, True),
        (21, 8, False),
    ],
)
def test_each_edge_of_the_band_is_inside_it(width, height, kept):
    # 2/10 is 0.2 and 20/8 is 2.5, so these are the bounds themselves rather
    # than numbers near them; the four that fail are one step outside on the
    # side that has to be strict.
    record = mrz_region.MrzComponent(
        left=0, top=0, width=width, height=height, area=width * height,
        cx=0.0, cy=0.0,
    )

    assert (mrz_region.filter_glyphs((record,)) == (record,)) is kept


def test_area_is_not_what_decides():
    # The handover's standing note, made non-vacuous: `area` is carried on the
    # record and nothing reads it.  These two blobs have the *same* area and
    # opposite verdicts, so no filter on area could produce both answers,
    # whichever direction it were written.
    hairline, rule = mrz_region.extract_components(
        solid_frame((10, 10, 3, 13), (40, 10, 1, 39))
    )

    assert hairline.area == rule.area == 39
    assert mrz_region.filter_glyphs((hairline,)) == (hairline,)
    assert mrz_region.filter_glyphs((rule,)) == ()


def test_the_records_that_survive_are_the_ones_that_came_in():
    # 4.5 groups them and 4.9 fits a line through their centroids, so a
    # rebuilt record would be a second measurement of the same blob.  The
    # order 4.3 chose is kept for the same reason it was chosen.
    components = components_of(grainy_mrz())
    glyphs = mrz_region.filter_glyphs(components)

    assert isinstance(glyphs, tuple)
    assert len({id(c) for c in glyphs}) == len(glyphs)
    assert all(any(c is kept for kept in glyphs) for c in glyphs)
    assert len(glyphs) < len(components)
    assert [(c.top, c.left) for c in glyphs] == sorted(
        (c.top, c.left) for c in glyphs
    )
    # Filtering is a projection, so filtering twice is filtering once, and an
    # empty page of blobs is not an error.
    assert mrz_region.filter_glyphs(glyphs) == glyphs
    assert mrz_region.filter_glyphs(()) == ()


def test_a_record_of_no_height_is_refused_rather_than_divided_by():
    # `connectedComponentsWithStats` cannot produce one -- every component has
    # at least one pixel -- but a caller can hand a record over, and the
    # aspect bound is a division.  The height bound is tested first, so this
    # is a filtered blob rather than a `ZeroDivisionError`.
    flat = mrz_region.MrzComponent(
        left=0, top=0, width=0, height=0, area=0, cx=0.0, cy=0.0
    )

    assert mrz_region.filter_glyphs((flat,)) == ()


# --- 4.5: the survivors, grouped into lines by vertical overlap ----------


def drawn_bands():
    """The rows the fixture's ink occupies, one ``(first, last)`` per line.

    Measured off ``glyph_mask`` rather than written down, for 4.2's reason:
    the fixture is *drawn*, which is the one thing about it that makes a
    ground truth available at all, and a pair of literals here would be a
    second thing for 4.14 to invalidate.
    """
    rows = np.flatnonzero((glyph_mask() > 0).any(axis=1))
    bands = []
    for row in rows:
        if bands and int(row) == bands[-1][1] + 1:
            bands[-1][1] = int(row)
        else:
            bands.append([int(row), int(row)])
    return tuple((first, last) for first, last in bands)


def lines_of(frame):
    """The whole chain, grouped.  A test names the pipeline it is testing."""
    return mrz_region.group_lines(glyphs_of(frame))


def component_record(left, top, width=10, height=10):
    """A glyph-sized record at a written-in box, for the hand-made cases."""
    return mrz_region.MrzComponent(
        left=left, top=top, width=width, height=height, area=width * height,
        cx=left + width / 2, cy=top + height / 2,
    )


def line_rows(line):
    """A line's own vertical extent, half-open like the boxes it came from."""
    return min(c.top for c in line), max(c.bbox[3] for c in line)


@pytest.mark.parametrize("name", sorted(FRAMES) + ["grainy"])
def test_a_two_line_page_comes_back_as_exactly_two_lines(name):
    # The test 4.5 asks for, and the count on its own is a weak claim: one
    # group holding both lines answers "2" just as comfortably as two groups
    # holding one line each.  So the count is checked against what was drawn
    # -- each line sits inside one of the fixture's own row bands, and the
    # bands are used one apiece -- and against the fact that the grouping is
    # a *partition* of what 4.4 kept rather than a summary of it.
    #
    # The grainy capture is in the list because 4.4's band is what makes it
    # answerable at all: without it this counts 313 blobs, and a grouping
    # that had to survive speckle would be 4.4's band written a second time.
    frame = grainy_mrz() if name == "grainy" else FRAMES[name]()
    glyphs = glyphs_of(frame)
    lines = mrz_region.group_lines(glyphs)
    bands = drawn_bands()

    assert len(lines) == 2
    assert len(bands) == 2
    for line, (first, last) in zip(lines, bands):
        assert line, "a drawn line of print came back empty"
        assert all(first <= c.top and c.bbox[3] <= last for c in line)

    # Two lines, not one read twice: their rows are disjoint and the gap
    # between them is larger than the tallest glyph on the page -- which is
    # 4.4's own reason for putting its ceiling under half the line pitch.
    assert line_rows(lines[0])[1] < line_rows(lines[1])[0]
    assert (line_rows(lines[1])[0] - line_rows(lines[0])[1]) > max(
        c.height for c in glyphs
    )

    # Every survivor arrives exactly once, and it arrives as the record 4.3
    # measured rather than as a copy of it.
    assert sum(len(line) for line in lines) == len(glyphs)
    assert {id(c) for line in lines for c in line} == {id(c) for c in glyphs}


def test_a_blob_joins_a_line_only_while_it_shares_a_row_with_it():
    # The rule itself, on boxes whose coordinates are written down rather
    # than measured off a cut, so the boundary is visible: rows 10-20,
    # 15-25 and 20-30.  The first two share row 19 and the third starts
    # exactly where the second ends -- sharing no row with it -- and opens a
    # line of its own.  Half-open at both ends, and neither reading is a
    # preference: an inclusive edge merges two adjacent lines at a printed
    # baseline, a strict one splits a line whose glyphs merely touch.
    first, second, third, fourth = (
        component_record(0, 10),
        component_record(30, 15),
        component_record(60, 20),
        component_record(90, 30),
    )

    lines = mrz_region.group_lines((first, second, third, fourth))

    assert lines == ((first, second, third), (fourth,))
    assert line_rows(lines[0]) == (10, 30)
    assert line_rows(lines[1]) == (30, 40)


def test_a_line_is_closed_by_its_deepest_member_and_not_by_its_last_one():
    # The other half of the same rule, and the one the first test above
    # cannot see: comparing each blob against the *previous* one is enough to
    # pass it, because there every blob reaches lower than the one before it.
    # Rows 10-31, 15-17 and 30-32: the middle blob stops 14 rows short of
    # where it started, so a rule that adopted its bottom as the new edge
    # would put the third blob somewhere else entirely -- and a rule that
    # lost a row off the edge while it did so would lose this one too.
    deep, shallow, later = (
        component_record(0, 10, width=11, height=21),
        component_record(30, 15, width=11, height=2),
        component_record(60, 30, width=11, height=2),
    )

    lines = mrz_region.group_lines((deep, shallow, later))

    assert lines == ((deep, shallow, later),)
    assert line_rows(lines[0]) == (10, 32)
    # The shape that makes it load-bearing: the middle blob ends well above
    # the third, and the first and the third share row 30.
    assert shallow.bbox[3] < later.top
    assert deep.top < shallow.top < later.top < deep.bbox[3]

    # And the transitivity the module docstring claims, in the direction the
    # other test reads it: a blob that shares no row with the *first* member
    # is still on that member's line when something between them bridges.
    bridged, bridge, hanging = (
        component_record(0, 10),
        component_record(30, 15),
        component_record(60, 20),
    )

    assert mrz_region.group_lines((bridged, bridge, hanging)) == (
        (bridged, bridge, hanging),
    )
    assert bridged.bbox[3] == hanging.top  # they share no row at all


def test_a_blob_holding_two_characters_is_still_one_line():
    # 4.3's note that this has to survive, and it is about the blob count
    # rather than about the grouping: two pairs of neighbours touch at this
    # cut, so each line comes back with fewer blobs than it has printed
    # characters and one of them is roughly twice as wide as its neighbours.
    # Written longhand rather than waited for on the fixture, because which
    # pairs merge is a property of the cut and 4.14 replaces it.
    merged, plain, below = (
        component_record(30, 10, width=22, height=14),
        component_record(0, 10, width=11, height=14),
        component_record(0, 60, width=11, height=14),
    )

    lines = mrz_region.group_lines((below, merged, plain))

    assert lines == ((plain, merged), (below,))
    # The wide blob did not become a second group, and it did not drag the
    # line below it up with it either.
    assert len(lines) == 2
    assert line_rows(lines[0])[1] <= line_rows(lines[1])[0]


def test_each_line_holds_the_characters_of_one_baseline_and_nothing_else():
    # The per-line half of "two lines", measured against what was printed:
    # one blob per character at most, and never so few that characters went
    # missing rather than merged.  Measured on this fixture: 24 and 27
    # against 25 and 28 on a flat scan, 25 and 27 in low light.
    lines = lines_of(upright_mrz())

    assert len(lines) == len(LINES)
    for line, text in zip(lines, LINES):
        assert 3 * len(text) // 4 <= len(line) <= len(text)
        # And the merge is inside a line rather than between two: the line
        # is as wide as the print is, and a blob that had leaked into its
        # neighbour would push it past the drawn extent.
        _, _, left, right = drawn_extent()
        assert left <= min(c.left for c in line)
        assert max(c.bbox[2] for c in line) <= right + 1


def test_the_lines_read_down_the_page_and_the_glyphs_read_across_it():
    # Neither order is the one 4.3 chose, and that is the point of the
    # re-sort.  Groups run top to bottom because 4.7 counts them and 4.11
    # maps a cell index to a field offset; glyphs run left to right because
    # 4.10 segments along x and its cell 0 has to be the leftmost character.
    glyphs = glyphs_of(upright_mrz())
    lines = mrz_region.group_lines(glyphs)

    assert [line[0].top for line in lines] == sorted(line[0].top for line in lines)
    for line in lines:
        assert [c.left for c in line] == sorted(c.left for c in line)

    # Not vacuous: 4.3's order is the raster-scan order of OpenCV's
    # labelling, and this fixture's first line is where the two come apart.
    first_line_as_43_ordered_it = glyphs[: len(lines[0])]
    assert [c.left for c in first_line_as_43_ordered_it] != sorted(
        c.left for c in first_line_as_43_ordered_it
    )


def test_the_groups_do_not_depend_on_the_order_the_blobs_arrive_in():
    # 4.4 keeps 4.3's order rather than rebuilding it, so the order this is
    # handed is not this step's to trust.  Three different arrivals of the
    # same 51 records have to come back as the same two lines.
    glyphs = glyphs_of(upright_mrz())
    expected = mrz_region.group_lines(glyphs)

    assert mrz_region.group_lines(tuple(reversed(glyphs))) == expected
    assert mrz_region.group_lines(glyphs[27:] + glyphs[:27]) == expected
    # And what comes back is made of the records that went in, not copies.
    assert all(
        any(c is kept for line in expected for kept in line) for c in glyphs
    )


def test_the_height_band_is_not_applied_a_second_time():
    # The handover's standing instruction to this task, made checkable: 4.4
    # wrote the band and re-applying it here would be one rule in two places.
    # The record that shows it is the signature 4.4 refuses -- 150 by 20, an
    # aspect ratio of 7.5 -- handed straight over instead of through the
    # filter.  Grouping it is 4.5's whole remit: which blobs share rows.
    signature = component_record(10, 40, width=150, height=20)

    assert mrz_region.filter_glyphs((signature,)) == ()
    assert mrz_region.group_lines((signature,)) == ((signature,),)


def test_nothing_is_discarded_here_because_that_is_46s_call():
    # "Is this line plausible" is 4.6's question -- height consistency and
    # inter-line spacing -- and answering it here would be a threshold
    # 4.4 did not write down.  So a group of one comes back as a group of one,
    # and the handover's open exposure is measured rather than promised: the
    # six specks of *paper* a greyscale frame leaves behind survive 4.4, and
    # this groups them onto the same two baselines the print uses.
    (stray,) = mrz_region.filter_glyphs(
        mrz_region.extract_components(solid_frame((10, 10, 5, 8)))
    )
    specks = mrz_region.filter_glyphs(
        mrz_region.extract_components(mrz_region.to_gray(upright_mrz()))
    )
    lines = mrz_region.group_lines(specks)

    assert mrz_region.group_lines((stray,)) == ((stray,),)
    assert len(specks) == 6
    assert [len(line) for line in lines] == [2, 4]
    for line, (first, last) in zip(lines, drawn_bands()):
        assert first <= line_rows(line)[0] and line_rows(line)[1] <= last


def test_a_frame_with_nothing_on_it_comes_back_with_no_lines():
    # 4.13's empty result begins here, and the two ways a frame arrives
    # empty are both ordinary rather than exceptional: a page whose cut went
    # white is refused by 4.4's height ceiling, and a frame with no ink has
    # no component to begin with.  Neither raises, because the package has
    # exactly one error type and "there is no MRZ here" is not one of them.
    blank = mrz_region.extract_components(
        np.zeros((PAGE_HEIGHT, PAGE_WIDTH), np.uint8)
    )
    white = mrz_region.filter_glyphs(
        mrz_region.extract_components(np.full((PAGE_HEIGHT, PAGE_WIDTH), 255, np.uint8))
    )

    assert blank == ()
    assert mrz_region.group_lines(blank) == ()
    assert white == ()
    assert mrz_region.group_lines(white) == ()
    assert mrz_region.group_lines(()) == ()


def test_a_record_of_no_height_is_a_line_of_its_own_and_not_an_error():
    # `extract_components` cannot produce one -- every blob has at least one
    # pixel -- but a caller can hand a record over, and an empty vertical
    # extent has no row to share.  Sorted by top it can only ever be a line
    # of one: nothing that follows it starts higher.
    flat = mrz_region.MrzComponent(
        left=0, top=10, width=0, height=0, area=0, cx=0.0, cy=10.0
    )

    assert mrz_region.group_lines((flat,)) == ((flat,),)


# --- 4.6: the line groups, scored on height and on spacing ---------------

#: The stray line, and the number that places it.  A *name* in the
#: fixture's own font, at the fixture's own size and thickness, above the
#: MRZ: 4.4 cannot refuse it, its own glyphs are the MRZ's own glyphs, and
#: the only thing wrong with it is where it sits.  Drawn smaller, or in
#: another face, it would be discardable on height as well, and the task's
#: test would then be showing that either score refuses it rather than that
#: this one does.
STRAY_TEXT = "ERIKSSON<<ANNA<MARIA"
STRAY_BASELINE = 20


def stray_line_page(baseline=STRAY_BASELINE, text=STRAY_TEXT, scale=0.7):
    """The fixture with a line of ordinary type above the MRZ.

    Written onto the page rather than drawn by a second generator, for 4.4's
    reason: the blob has to be one 4.4 would otherwise have kept, and the
    two MRZ lines underneath have to be untouched, so that what comes back
    can be compared with the page that never had the stray on it.
    """
    page = upright_mrz()
    cv2.putText(
        page, text, (40, baseline),
        cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2, cv2.LINE_AA,
    )
    return page


def line_top(line):
    """A line's own first row, which is 4.5's reading order made a number."""
    return min(component.top for component in line)


def heights_spread(line):
    """The height score, measured here rather than read off the function."""
    heights = sorted(component.height for component in line)
    return (heights[-1] - heights[0]) / statistics.median(heights)


def pitches_of(lines):
    """The spacing from each line down to the one below it."""
    tops = [line_top(line) for line in lines]
    return [below - above for above, below in zip(tops, tops[1:])]


@pytest.mark.parametrize("name", sorted(FRAMES) + ["grainy"])
def test_the_two_printed_lines_of_every_capture_survive_the_scoring(name):
    # The filter has to be a filter and not a sieve, and it is checked on all
    # four captures for the reason 4.4 checks its band on all four: the
    # grainy page is 313 blobs before 4.4 and 51 after it, so a score that
    # needed a clean page would be 4.4's band written a second time.
    frame = grainy_mrz() if name == "grainy" else FRAMES[name]()
    glyphs = glyphs_of(frame)
    lines = mrz_region.group_lines(glyphs)

    scored = mrz_region.filter_lines(lines)

    assert scored == lines
    # Neither score is being handed nothing: this fixture's own lines do
    # differ in height, so the height score has a real spread to judge, and
    # the leading is the same on all four captures, so there is a real
    # reading behind the spacing band rather than an accident.
    assert max(heights_spread(line) for line in lines) > 0.0
    assert max(heights_spread(line) for line in lines) <= (
        mrz_region.LINE_MAX_HEIGHT_SPREAD
    )
    assert pitches_of(lines) == [LINE_PITCH]
    # And what comes back is a partition of the records that went in, made of
    # those records rather than of copies.
    assert sum(len(line) for line in scored) == len(glyphs)
    assert {id(c) for line in scored for c in line} == {id(c) for c in glyphs}


def test_a_line_whose_glyphs_disagree_about_height_is_discarded():
    # The first of the two scores, written longhand so both halves of the
    # rule are visible at once: two marks on one baseline whose heights
    # cannot both be the body size of the line, beside a line whose single
    # mark is an ordinary glyph.  4.4 keeps all three -- a 10 by 10 and a
    # 24 by 24 are both inside its band -- which is the whole reason this
    # score exists at all.
    short, tall, partner = (
        component_record(0, 10, width=10, height=10),
        component_record(30, 10, width=24, height=24),
        component_record(0, 80, width=11, height=14),
    )
    lines = mrz_region.group_lines((tall, partner, short))

    assert mrz_region.filter_glyphs((short, tall, partner)) == (
        short, tall, partner,
    )

    scored = mrz_region.filter_lines(lines)

    assert scored == ((partner,),)
    # The height score is what refused it, measured rather than asserted: the
    # discarded group's spacing is exactly the leading, so the other score
    # has nothing to say about it.
    assert heights_spread((short, tall)) > mrz_region.LINE_MAX_HEIGHT_SPREAD
    assert pitches_of(lines) == [LINE_PITCH]
    # And the line goes *with* the mark rather than instead of it -- 4.10
    # would otherwise be handed a cell for a mark the cut invented.
    assert not any(
        member is kept for line in scored for kept in line for member in (short, tall)
    )


def test_a_line_that_is_not_on_the_leading_the_set_shows_is_discarded():
    # The second score, and the one the task's own test needs.  Three groups
    # of one mark each: two of them a leading apart, and a third 30 rows
    # further off the second, which is 0.43 of the leading -- a departure a
    # printed block does not make and a quarter of the leading refuses.
    first, second, stray = (
        component_record(0, 10, width=11, height=14),
        component_record(0, 80, width=11, height=14),
        component_record(0, 180, width=11, height=14),
    )
    lines = mrz_region.group_lines((stray, first, second))

    assert mrz_region.filter_lines(lines) == ((first,), (second,))
    # The other score would have kept it: one mark, one height, nothing to
    # disagree with.
    assert heights_spread((stray,)) == 0.0
    # And the same two groups *without* the MRZ line above them both survive,
    # which is the arithmetic behind the task's third line: two groups have
    # one spacing between them, and one spacing cannot be inconsistent.
    assert mrz_region.filter_lines(((second,), (stray,))) == ((second,), (stray,))


def test_a_third_stray_line_printed_on_the_page_is_discarded():
    # The test 4.6 asks for, and both halves of it.  A line of ordinary type
    # is drawn on the fixture page above the MRZ: it has to *arrive* as a
    # third group -- 4.5 reports the grouping it is handed and refuses to
    # pre-judge it -- and this step has to throw it away while leaving the
    # two printed lines exactly as they come back from the page that never
    # had the stray on it.
    glyphs = glyphs_of(stray_line_page())
    lines = mrz_region.group_lines(glyphs)
    plain = mrz_region.group_lines(glyphs_of(upright_mrz()))

    # It arrives: above both printed lines and clear of the first band the
    # fixture drew, and glyph-plausible all the way through 4.4 -- which is
    # what makes this a test of 4.6's scores and not of 4.4's band.
    assert len(lines) == 3
    assert [line_top(line) for line in lines] == sorted(line_top(l) for l in lines)
    assert lines[0][-1].bbox[3] <= drawn_bands()[0][0]
    assert lines[1:] == plain

    # It is the spacing that refuses it, and the test is that one score
    # rather than two: measured, the stray's own glyphs are the MRZ's own
    # glyphs and its spread is inside the height band, while its spacing is
    # 30 rows further out than a quarter of the leading allows.
    assert heights_spread(lines[0]) <= mrz_region.LINE_MAX_HEIGHT_SPREAD
    lead = min(pitches_of(lines))
    stray_pitch = line_top(lines[1]) - line_top(lines[0])
    assert lead == LINE_PITCH
    assert (stray_pitch - lead) / lead > mrz_region.LINE_MAX_SPACING_SPREAD

    scored = mrz_region.filter_lines(lines)

    assert scored == plain
    assert sum(len(line) for line in scored) == sum(len(line) for line in plain)
    # The two lines that survive are the very groups 4.5 produced, in order.
    assert scored[0] is lines[1]
    assert scored[1] is lines[2]


def test_a_stray_line_printed_near_the_leading_is_not_what_these_scores_catch():
    # The limit, measured rather than promised.  The same line of type drawn
    # 20 rows lower lands 0.14 of the leading from the MRZ -- the same
    # proportion as the height spread the two printed lines have between
    # them, and comfortably inside the band -- so it is consistent with the
    # set and survives.  What catches a page with three lines on it is 4.7's
    # line count and 4.10's cell count: a consistency score is not a
    # document reader, and this is where that stops being a caveat.
    lines = mrz_region.group_lines(glyphs_of(stray_line_page(baseline=40)))
    lead = min(pitches_of(lines))
    stray_pitch = line_top(lines[1]) - line_top(lines[0])

    assert len(lines) == 3
    assert 0.0 < (stray_pitch - lead) / lead <= mrz_region.LINE_MAX_SPACING_SPREAD
    assert mrz_region.filter_lines(lines) == lines


def test_the_height_score_is_measured_against_the_lines_own_median():
    # Which statistic the reference is, is a decision like any other, and it
    # is the median and not the middle of the sorted heights: two marks of 19
    # and 28 rows give a true median of 23.5 and a spread of 0.38, where the
    # upper of the two would say 0.32 and keep the line.  A caller may hand
    # over marks 4.4 would have refused -- 4.5's own signature case is the
    # precedent -- so the reference cannot be a size 4.4 chose.
    low, high, partner = (
        component_record(0, 10, width=19, height=19),
        component_record(40, 10, width=28, height=28),
        component_record(0, 80, width=11, height=14),
    )
    lines = mrz_region.group_lines((low, high, partner))

    assert (28 - 19) / ((19 + 28) / 2) > mrz_region.LINE_MAX_HEIGHT_SPREAD
    assert (28 - 19) / 28 <= mrz_region.LINE_MAX_HEIGHT_SPREAD
    assert mrz_region.filter_lines(lines) == ((partner,),)

    # And the median rather than the mean, which can only be told apart at the
    # edge: four marks of 8, 12, 12 and 12 rows give a median of 12 -- a
    # spread of exactly a third, kept because the edge is inside the band --
    # and a mean of 11, which is 0.36 and discarded.  A rule with either of
    # those two numbers in it is a different rule, and this is the only case
    # here that sees which one is in force.
    edge = tuple(
        component_record(index * 20, 10, width=10, height=height)
        for index, height in enumerate((8, 12, 12, 12))
    )
    assert heights_spread(edge) == mrz_region.LINE_MAX_HEIGHT_SPREAD
    assert 4 / statistics.mean([8, 12, 12, 12]) > mrz_region.LINE_MAX_HEIGHT_SPREAD
    assert mrz_region.filter_lines((edge,)) == (edge,)


def test_a_line_with_no_height_is_discarded_rather_than_divided_by():
    # `extract_components` cannot produce a record of zero height, but a
    # caller can hand one over, and 4.4 refused that record for exactly this
    # reason: the aspect ratio divides by it.  Here the median does, and a
    # group of nothing but zero-height records has no body size to be
    # consistent with, so it goes rather than raising.
    flat = mrz_region.MrzComponent(
        left=0, top=10, width=0, height=0, area=0, cx=0.0, cy=10.0
    )
    partner = component_record(0, 80, width=11, height=14)
    lines = (
        (partner,),
        (flat, component_record(40, 10, width=11, height=14)),
    )

    assert mrz_region.filter_lines(((flat,),)) == ()
    assert mrz_region.filter_lines(lines) == ((partner,),)


@pytest.mark.parametrize("heights,kept", [
    ((5, 7), True),        # exactly a third: the edge is *inside* the band
    ((5, 5, 7), False),    # two fifths, and the case above plus one short mark
    ((13, 15), True),      # the spread this fixture's own lines have
    ((10, 24), False),     # a factor 4.4's own band keeps, both of them
])
def test_each_edge_of_the_height_band_is_inside_it(heights, kept):
    # The comparison has to be decidable at the edge, and which way it goes is
    # a decision rather than an accident: a mark exactly a third off the
    # line's median is still a glyph of that line, and the band is written
    # to say so.  The last case is the one 4.4 cannot refuse -- a 10 by 10
    # and a 24 by 24 are both inside its band -- so it is the only row here
    # that says anything about 4.6 existing.
    line = tuple(
        component_record(index * 20, 10, width=10, height=height)
        for index, height in enumerate(heights)
    )

    assert (mrz_region.filter_lines((line,)) == (line,)) is kept


@pytest.mark.parametrize("pitch,kept", [
    (89, True),   # a quarter of 72 is exactly 18, so these three straddle it
    (90, True),   # and the middle one *is* the edge, which is inside
    (91, False),  # and this is the first row outside it
])
def test_each_edge_of_the_spacing_band_is_inside_it(pitch, kept):
    # The same decidability on the second score, and it is measured against
    # the leading rather than written down, so nothing here depends on the
    # stray line's own placement staying where it is.  The leading is 72 and
    # not the fixture's 70 for one reason: rows are whole numbers, a quarter
    # of 70 is 17.5, and a comparison whose two sides cannot land on the same
    # row is not a comparison this test could pin.
    lead = 72
    first = component_record(0, 10, width=11, height=14)
    second = component_record(0, 10 + lead, width=11, height=14)
    stray = component_record(0, 10 + lead + pitch, width=11, height=14)
    lines = mrz_region.group_lines((first, second, stray))

    scored = mrz_region.filter_lines(lines)

    # Whether the *stray* survives is what the band decides; the two lines
    # on the leading come through either way, by identity and in order.
    assert any(stray is member for line in scored for member in line) is kept
    assert scored[0] is lines[0]
    assert scored[1] is lines[1]


def test_the_greyscale_specks_are_not_what_these_two_scores_discard():
    # 4.5's own note said 4.6 is what throws the specks a greyscale frame
    # leaves behind away.  Measured, it is not: the two groups of 2 and 4 are
    # all ten rows tall like each other and a leading apart like each other,
    # which is all a consistency score can see -- it cannot tell a line of
    # two blobs from a line of forty.  Correcting that sentence is the point
    # of this test.  What a two-blob line is caught by is 4.7's cell count,
    # and what a caller that produced it has to fix is 4.2's cut.
    specks = mrz_region.filter_glyphs(
        mrz_region.extract_components(mrz_region.to_gray(upright_mrz()))
    )
    lines = mrz_region.group_lines(specks)

    assert [len(line) for line in lines] == [2, 4]
    assert all(heights_spread(line) == 0.0 for line in lines)
    assert pitches_of(lines) == [LINE_PITCH]
    assert mrz_region.filter_lines(lines) == lines


def test_the_two_bands_are_held_to_the_rules_they_are_pinned_on():
    lines = mrz_region.group_lines(glyphs_of(upright_mrz()))
    spreads = [heights_spread(line) for line in lines]
    glyphs = [c for line in lines for c in line]

    # Height: at least twice the worst spread this fixture shows, so a line
    # printed with a little more variation than its neighbour is not a line
    # that loses them.  4.14's generator has to keep that true.
    assert mrz_region.LINE_MAX_HEIGHT_SPREAD >= 2 * max(spreads)
    # And narrower than the spread 4.4's own band admits for a line of these
    # glyphs, which is the whole reason this score exists: 4.4 judges each
    # blob on its own, this judges the line they share a baseline with.
    assert mrz_region.LINE_MAX_HEIGHT_SPREAD < (
        mrz_region.GLYPH_MAX_HEIGHT_PX - mrz_region.GLYPH_MIN_HEIGHT_PX
    ) / statistics.median([c.height for c in glyphs])

    # Spacing: the band sits above a whole glyph, because a departure
    # smaller than a glyph cannot be told from a printing or a scanning
    # artefact; and it is a fraction and not a pixel count, or a page at
    # another scale would be a different answer.
    assert mrz_region.LINE_MAX_SPACING_SPREAD * LINE_PITCH > max(
        c.height for c in glyphs
    )
    assert 0.0 < mrz_region.LINE_MAX_SPACING_SPREAD < 1.0
    # And the honest limit of that rule: this fixture has one spacing to
    # measure, so the band is held to its rule and to the one reading there
    # is -- the same leading on all three of 4.2's clean captures.
    for name in sorted(FRAMES):
        tops = [
            line_top(line)
            for line in mrz_region.group_lines(glyphs_of(FRAMES[name]()))
        ]
        assert [below - above for above, below in zip(tops, tops[1:])] == [LINE_PITCH]


def test_the_groups_that_survive_are_the_ones_that_went_in():
    # A filter that rebuilt its groups would be a second measurement of the
    # same blobs, for 4.4's reason, and 4.9 fits lines through their
    # centroids.  The order the groups arrive in is 4.5's to have chosen, so
    # the spacing is read between them sorted by their own tops: the same
    # groups handed over backwards give the same answer rather than a set of
    # negative spacings.
    glyphs = glyphs_of(upright_mrz())
    lines = mrz_region.group_lines(glyphs)
    scored = mrz_region.filter_lines(lines)

    assert scored == lines
    assert {id(c) for line in scored for c in line} == {id(c) for c in glyphs}
    assert mrz_region.filter_lines(tuple(reversed(lines))) == tuple(reversed(scored))
    # And nothing at all is still nothing at all, as everywhere else here.
    assert mrz_region.filter_lines(()) == ()


# --- 4.8: each surviving line, as four points on the page ----------------


def band_drawn_extent(band):
    """The ink the fixture drew for one of its own line bands.

    Measured off ``glyph_mask`` and restricted to ``band`` -- one of
    ``drawn_bands``' own pairs -- rather than off a literal, for 4.2's
    reason: the fixture is *drawn*, which is the one thing about it that
    makes a ground truth available at all.  4.8's polygon is measured against
    one band per line rather than against the whole page, because a polygon
    that enclosed the page would pass a test written the other way.
    """
    first, last = band
    rows = np.flatnonzero((glyph_mask()[first:last + 1] > 0).any(axis=1))
    cols = np.flatnonzero((glyph_mask()[first:last + 1] > 0).any(axis=0))
    return (
        int(cols.min()),
        first + int(rows.min()),
        int(cols.max()),
        first + int(rows.max()),
    )


def polygons_of(frame):
    """The whole chain, located.  A test names the pipeline it is testing."""
    return mrz_region.line_polygons(
        mrz_region.filter_lines(lines_of(frame))
    )


def holds(polygon, extent):
    """Whether the four corners, read in 4.8's order, hold a half-open box.

    The corners are read *by position* -- top left, top right, bottom right,
    bottom left -- and not by their own minimum and maximum, because a quad
    whose corners were in the wrong order has the same minimum and maximum as
    one in the right order and would satisfy a test written the other way.
    The level and plumb assertions are the same claim: this is a rectangle,
    and 4.8's four points are the four corners of one.
    """
    top_left, top_right, bottom_right, bottom_left = polygon
    left, top, right, bottom = extent
    return (
        top_left[1] == top_right[1]
        and bottom_left[1] == bottom_right[1]
        and top_left[0] == bottom_left[0]
        and top_right[0] == bottom_right[0]
        and top_left[0] <= left
        and top_right[0] >= right
        and top_left[1] <= top
        and bottom_left[1] >= bottom
    )


def test_the_four_points_are_the_lines_own_box_read_clockwise_from_the_top_left():
    # The test 4.8 asks for, written longhand so the point order is a
    # statement rather than something a reader has to infer: two records with
    # written-in boxes, and the polygon they must come back as.  The far edge
    # is 36 and 34 rather than 35 and 33 -- `bbox` is half-open, and that is
    # the corner `binary[top:bottom, left:right]` is cut from.
    line = (
        component_record(10, 20, width=8, height=12),
        component_record(30, 24, width=6, height=10),
    )

    assert mrz_region.line_polygons((line,)) == (
        ((10, 20), (36, 20), (36, 34), (10, 34)),
    )


@pytest.mark.parametrize("name", sorted(FRAMES) + ["grainy"])
def test_the_polygon_encloses_the_glyphs_that_were_drawn(name):
    # The other half of the test 4.8 asks for.  Each polygon is checked
    # against the ink the fixture drew for that line's own baseline, and
    # "encloses" is bounded in both directions, because on its own it is
    # satisfied by the page: the polygon must reach every blob the cut found
    # and must stay inside the drawn ink.
    #
    # **The polygon sits inside the drawn extent rather than round it, and by
    # exactly one pixel on every edge of both lines.**  That is a difference
    # between two renderings of one character, not slack in the polygon:
    # `upright_mrz` draws with LINE_AA and the cut keeps the solid core of
    # that fringe, where `glyph_mask` draws the same text with LINE_8 and
    # dilates it by a pixel, so the ground truth is a pixel fatter than the
    # ink the cut can honestly claim.  `inside_drawn_glyphs` reads the same
    # difference from the other end.  So the lower bound is zero -- a
    # polygon reaching outside the drawn ink would be padding, and this is
    # where 4.12's field boxes would inherit it -- and the upper bound is
    # that one pixel, which a polygon cut from anything coarser than this
    # cut would fail.
    frame = grainy_mrz() if name == "grainy" else FRAMES[name]()
    lines = mrz_region.filter_lines(lines_of(frame))
    bands = drawn_bands()

    polygons = mrz_region.line_polygons(lines)

    assert len(polygons) == len(lines) == len(bands) == 2
    for polygon, line, band in zip(polygons, lines, bands):
        left, top, right, bottom = band_drawn_extent(band)
        top_left, top_right, bottom_right, bottom_left = polygon

        # The exact claim, with no pixel of slack in it: every blob the cut
        # found for this line is inside the polygon it is handed, corner for
        # corner, on the half-open convention the two of them already share.
        assert all(holds(polygon, component.bbox) for component in line)
        assert (
            0 <= top_left[0] - left <= 1
            and 0 <= top_left[1] - top <= 1
            and 0 <= right - bottom_right[0] <= 1
            and 0 <= bottom - bottom_left[1] <= 1
        ), "the polygon is not inside the drawn extent, or is more than a pixel inside it"


def test_every_line_gets_one_polygon_and_they_read_down_the_page():
    # One in, one out, in the order the lines arrived -- 4.5 owns that order
    # and 4.8 has no opinion about it.  And the two are told apart by which
    # band of the fixture they land in, so a function that answered with the
    # page's own box twice, or with both lines merged into one, is caught.
    polygons = polygons_of(upright_mrz())

    assert len(polygons) == 2
    for polygon, band in zip(polygons, drawn_bands()):
        first, last = band
        top_left, _, _, bottom_left = polygon
        assert first <= top_left[1] <= bottom_left[1] <= last


def test_each_edge_of_the_polygon_is_touched_by_a_glyph_of_that_line():
    # "Encloses" on its own is satisfied by the page.  Every edge is the
    # extreme of some blob, so the rectangle is the smallest one holding the
    # line -- a margin added here for a highlight to be visible would be a
    # number 4.12's field boxes would then have to carry as well.
    line = mrz_region.filter_lines(lines_of(upright_mrz()))[0]

    polygon = mrz_region.line_polygons((line,))[0]

    lefts = {component.bbox[0] for component in line}
    tops = {component.bbox[1] for component in line}
    rights = {component.bbox[2] for component in line}
    bottoms = {component.bbox[3] for component in line}
    assert polygon[0][0] in lefts and polygon[0][1] in tops
    assert polygon[1][0] in rights
    assert polygon[2][1] in bottoms
    assert polygon[2][0] == max(rights) and polygon[3][1] == max(bottoms)


def test_the_coordinates_are_plain_python_ints():
    # 4.3's rule, carried: 4.13's empty result becomes a JSON body, and a
    # numpy integer in a polygon is an object no response encoder will take.
    polygons = polygons_of(upright_mrz())

    for polygon in polygons:
        for point in polygon:
            assert type(point) is tuple and len(point) == 2
            assert all(type(value) is int for value in point)


def test_a_line_of_no_glyphs_is_not_a_rectangle_at_the_origin():
    # There is no corner to report for a line with no members, and a
    # rectangle at (0, 0) would be a place on the page no MRZ is.  A line of
    # zero-height records *is* reportable, and comes back as a rectangle with
    # no height rather than being dropped: that record is one 4.3 cannot
    # produce and a caller can, and a degenerate answer about a real record
    # beats no answer.
    flat = component_record(5, 7, width=0, height=0)

    assert mrz_region.line_polygons(((flat,),)) == (
        ((5, 7), (5, 7), (5, 7), (5, 7)),
    )
    assert mrz_region.line_polygons(((),)) == ()
    assert mrz_region.line_polygons(()) == ()


def test_two_lines_that_touch_stay_two_polygons():
    # Nothing is merged and nothing is re-judged here: 4.5 decided what a line
    # is and 4.6 decided which are worth reading, so a caller handing over two
    # groups on overlapping rows gets two rectangles, one per group, however
    # much of each other they cover.
    above = (component_record(10, 20, width=8, height=12),)
    below = (component_record(40, 26, width=8, height=12),)

    polygons = mrz_region.line_polygons((above, below))

    assert len(polygons) == 2
    assert polygons[0][0][1] == 20 and polygons[1][0][1] == 26
    assert polygons[0][2][1] == 32 and polygons[1][2][1] == 38


# --- 4.9: the lean inside one line, read off its own glyph centroids -----


def tilted_pair_mrz(angles, scale=0.7, thickness=2):
    """The fixture, with each line turned by its own amount.

    The one capture in this file 4.1's page reading cannot answer for.  Each
    line is drawn on its own layer and turned about its own baseline, so the
    two lines disagree -- which is the ordinary case of a document bowed
    along its binding, and the reason 4.9 measures a line rather than a page.
    Written here rather than imported, like every other fixture in this file:
    4.14 is the task that replaces them.
    """
    page = np.full((PAGE_HEIGHT, PAGE_WIDTH, 3), 255, np.uint8)
    for row, (text, angle) in enumerate(zip(LINES, angles)):
        baseline = 120 + 70 * row
        layer = np.full((PAGE_HEIGHT, PAGE_WIDTH, 3), 255, np.uint8)
        cv2.putText(
            layer, text, (40, baseline),
            cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness, cv2.LINE_AA,
        )
        if angle:
            matrix = cv2.getRotationMatrix2D(
                (PAGE_WIDTH / 2.0, baseline), angle, 1.0
            )
            layer = cv2.warpAffine(
                layer, matrix, (PAGE_WIDTH, PAGE_HEIGHT),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
            )
        page = cv2.bitwise_and(page, layer)
    return page


def readings_of(frame):
    """One residual reading per surviving line, in the lines' own order."""
    return tuple(
        mrz_region.residual_skew_deg(line)
        for line in mrz_region.filter_lines(lines_of(frame))
    )


def turned_of(frame):
    """Every surviving line turned level, in the lines' own order."""
    return tuple(
        mrz_region.deskew_line(line)
        for line in mrz_region.filter_lines(lines_of(frame))
    )


def spread(line, attr):
    """A line's own extent along one axis, in that axis' own pixels."""
    return (
        max(getattr(c, attr) for c in line)
        - min(getattr(c, attr) for c in line)
    )


def test_a_slightly_rotated_page_reads_its_own_tilt_off_its_glyph_centroids():
    # The test 4.9 asks for, and both halves of it are load-bearing.  A page
    # turned a *couple* of degrees is the case: 4.1 has already run, and what
    # is left is the part it left -- or, on a page handed straight to 4.9, the
    # part a page-level reading cannot see line by line.  The flat half is
    # what stops a function returning 0.0 from passing, which is the one wrong
    # answer that satisfies the first half on its own.
    tilted = rotated_mrz(2.0)

    readings = readings_of(tilted)

    assert len(readings) == 2
    assert all(abs(reading + 2.0) < 0.25 for reading in readings), readings
    # The same two lines on the page that was not turned at all, measured the
    # same way: under a fifth of a degree on every clean capture, which is
    # the glyphs' own shapes and not a lean.
    assert all(abs(reading) < 0.3 for reading in readings_of(upright_mrz()))


@pytest.mark.parametrize("turned", [1.0, 2.0, 3.0, -2.0])
def test_the_reading_is_the_pages_own_lean_and_not_a_second_opinion_on_it(turned):
    # 4.1 answers for the whole page and 4.9 for one line, so the two have to
    # agree in sign and in size or 4.9 is a second estimator for a question
    # 4.1 already settled.  The sign is the half that is easy to get wrong and
    # the half that would leave a page rotated twice the wrong way: a page
    # turned +2.0 reads -2.0 here, exactly as `skew_deg` reads it, and the
    # correction is applied as the reading comes.
    page = rotated_mrz(turned)

    page_reading = mrz_region.skew_deg(page)
    readings = readings_of(page)

    assert all(
        abs(reading - page_reading) < 0.25 for reading in readings
    ), f"page {page_reading:+.3f} against lines {readings}"
    # Applied as it comes levels the line; applied the other way round doubles
    # the lean, so the sign is settled from both ends rather than from one.
    line = mrz_region.filter_lines(lines_of(page))[0]
    assert abs(mrz_region.residual_skew_deg(mrz_region.deskew_line(line))) < 0.01
    assert abs(
        mrz_region.residual_skew_deg(
            mrz_region.deskew_line(line)
        )
    ) < abs(mrz_region.residual_skew_deg(line))


def test_the_two_lines_of_one_page_are_measured_separately():
    # The claim the module docstring makes about 4.9 not being 4.1 a second
    # time, measured rather than argued.  A page whose two lines are turned
    # by different amounts has one page reading and two line readings.  On
    # this capture the page answers **+1.40** and the lines answer **-1.86**
    # and **+1.54**: the page's own answer is **3.26 degrees out** for the
    # upper line, so no single rotation of the frame could level both, which
    # is the whole reason 4.10 is handed one group at a time.
    page = tilted_pair_mrz((2.0, -1.5))
    lines = mrz_region.filter_lines(lines_of(page))

    assert len(lines) == 2
    above, below = (mrz_region.residual_skew_deg(line) for line in lines)
    page_reading = mrz_region.skew_deg(page)

    assert abs(above + 2.0) < 0.25 and abs(below - 1.5) < 0.25
    assert (above < 0) != (below < 0), "the two lines do not disagree"
    assert abs(above - below) > 3.0
    assert abs(page_reading - above) > 1.0
    # And each is levelled by its own reading rather than by the page's.
    assert abs(mrz_region.residual_skew_deg(mrz_region.deskew_line(lines[0]))) < 0.01
    assert abs(mrz_region.residual_skew_deg(mrz_region.deskew_line(lines[1]))) < 0.01


def test_a_group_is_turned_level_rather_than_left_tilted():
    # What "rotate the group" has to mean, measured in the pixels rather than
    # in the number that came out of the estimator.  A line leaning 2 degrees
    # has its glyphs' centroids scattered over **10 to 14 rows**; turned, they
    # are over **2 to 3**, which is the scatter a *flat* page's own line shows
    # (2.35 and 2.54) and is therefore the glyphs' shapes rather than a lean.
    # An implementation that reported the angle and left the group alone would
    # satisfy the residual assertion below and fail this one.
    tilted, level = turned_of(rotated_mrz(2.0))
    before = mrz_region.filter_lines(lines_of(rotated_mrz(2.0)))

    for line, turned in zip(before, (tilted, level)):
        assert abs(mrz_region.residual_skew_deg(turned)) < 0.01
        assert spread(line, "cy") > 9.0
        assert spread(turned, "cy") < 3.5


def test_the_turn_is_about_the_lines_own_centre_of_mass_and_moves_nothing():
    # 4.1's promise, at one line's scale: a region means the same pixel before
    # and after the correction, or every polygon 4.8 emits and every field box
    # 4.12 returns is offset from the frame the officer is looking at.  The
    # least-squares line passes through the mean centroid, so rotating about
    # that mean is what holds the group still -- and the residual drift is
    # float error, measured at the eighth decimal.
    page = rotated_mrz(2.0)
    for line, turned in zip(
        mrz_region.filter_lines(lines_of(page)), turned_of(page)
    ):
        for attr in ("cx", "cy"):
            before = statistics.fmean(getattr(c, attr) for c in line)
            after = statistics.fmean(getattr(c, attr) for c in turned)
            assert abs(after - before) < 1e-6, attr
        assert spread(turned, "cx") > 0.9 * spread(line, "cx")
        assert max(c.bbox[2] for c in turned) <= PAGE_WIDTH
        assert max(c.bbox[3] for c in turned) <= PAGE_HEIGHT


def test_a_line_with_no_lean_is_handed_straight_back_records_and_all():
    # The identity case, and the one reading where a negated sign and a
    # correct implementation are indistinguishable from the outside -- so it is
    # the case that has to be asserted rather than assumed.  A rebuilt record
    # would be a second measurement of blobs nobody moved, which is
    # `filter_glyphs`' own reason for handing back the records it was given.
    level = tuple(
        component_record(left=10 + 20 * i, top=50, width=8, height=12)
        for i in range(6)
    )
    # `component_record` puts the centroid at the middle of the box, and this
    # line is level, so the fit is exactly zero and not merely small.
    assert mrz_region.residual_skew_deg(level) == 0.0

    turned = mrz_region.deskew_line(level)

    assert turned == level
    assert all(was is now for was, now in zip(level, turned))


@pytest.mark.parametrize(
    "name,group",
    [
        ("no glyphs", ()),
        (
            "one glyph",
            (component_record(left=3, top=4, width=8, height=10),),
        ),
        (
            "two glyphs at the same cx",
            (
                component_record(left=3, top=4, width=8, height=10),
                component_record(left=3, top=20, width=8, height=10),
            ),
        ),
        (
            "one glyph with no box",
            (component_record(left=4, top=6, width=0, height=0),),
        ),
    ],
)
def test_a_line_that_cannot_be_fitted_reads_zero_rather_than_dividing(name, group):
    # A group of one is not a contrivance: 4.5 does not discard it, so a stray
    # mark 4.6 kept arrives on its own.  Two glyphs at the same `cx` are the
    # other way in, and both are decided by arithmetic rather than by a rule:
    # a group whose `cx` are all the same has every `(cx - mean)` at zero, so
    # the lean is zero with them and there is no direction to lean in.  The
    # zero-spread check says so where the reading is made, and the reading
    # stays 0.0 either way -- `math.atan2(0.0, 0.0)` is 0.0 -- so what the
    # test holds is the *answer*, not a guard against a `ZeroDivisionError`
    # this implementation never had.
    assert mrz_region.residual_skew_deg(group) == 0.0, name

    turned = mrz_region.deskew_line(group)

    assert turned == group
    assert all(was is now for was, now in zip(group, turned))


def test_the_fit_is_through_the_centroids_and_not_the_middle_of_the_boxes():
    # 4.3's own distinction, applied.  A glyph is strokes rather than a solid,
    # so its centroid sits where its ink is and the middle of its box sits
    # where its extent is.  These two records lean because their *ink* leans:
    # one blob in the top-left corner of its box, one in the bottom-right
    # corner of another.  **The centroid fit reads 4.24 degrees and the
    # box-centre fit reads 0.0** -- so a box-centre implementation would call
    # this tilted line level, and would go on calling this fixture's level
    # lines level as well, which is what makes the discrimination necessary
    # rather than decorative.
    leaning = (
        mrz_region.MrzComponent(
            left=0, top=0, width=10, height=10, area=40, cx=1.0, cy=1.0
        ),
        mrz_region.MrzComponent(
            left=100, top=0, width=10, height=10, area=40, cx=109.0, cy=9.0
        ),
    )
    middles = tuple(
        dataclasses.replace(
            component, cx=component.left + component.width / 2,
            cy=component.top + component.height / 2,
        )
        for component in leaning
    )

    assert abs(mrz_region.residual_skew_deg(leaning) - 4.24) < 0.01
    assert mrz_region.residual_skew_deg(middles) == 0.0


def test_the_ink_is_carried_across_rather_than_counted_again():
    # Three claims in one place because they are three readings of the same
    # rule -- a rotation moves a record's numbers, it does not re-measure the
    # blob.  `area` is a pixel count and passes through untouched; the
    # **centroid is the rotated centroid and not the middle of the new box**,
    # so 4.3's distinction survives the rotation (measured: all 24 glyphs of
    # the line are off the middle, where before the turn they were not); and
    # no centroid is left outside the box it is reported with, which is the
    # invariant a rounded box could have broken and does not.
    page = rotated_mrz(2.0)
    for line, turned in zip(
        mrz_region.filter_lines(lines_of(page)), turned_of(page)
    ):
        assert len(turned) == len(line)
        for was, now in zip(line, turned):
            assert now.area == was.area
            assert now.left <= now.cx <= now.bbox[2]
            assert now.top <= now.cy <= now.bbox[3]
            assert (
                abs((now.cx - now.left) - now.width / 2) > 0.001
                or abs((now.cy - now.top) - now.height / 2) > 0.001
            )


def test_a_turned_box_is_the_turned_corners_and_not_a_moved_one():
    # A box turned by an angle is not the same box with a different top-left,
    # and this is where the difference shows.  **On a 2-degree page a box's
    # width never changes and its height grows by one pixel** -- the
    # `height * sin(angle)` an axis-aligned box cannot avoid once it is no
    # longer square to the ink -- and the far corners are the exact diagonal,
    # so a 45-degree turn of a 10-by-10 box is 14 by 14.  The consequence is
    # written down rather than discovered later: **a turned box is no longer
    # a slice of the cut**, so nothing downstream may cut one out.
    page = rotated_mrz(2.0)
    for line, turned in zip(
        mrz_region.filter_lines(lines_of(page)), turned_of(page)
    ):
        for was, now in zip(line, turned):
            assert 0 <= now.height - was.height <= 1
            assert now.width == was.width

    steep = (
        mrz_region.MrzComponent(
            left=0, top=0, width=10, height=10, area=40, cx=5.0, cy=5.0
        ),
        mrz_region.MrzComponent(
            left=90, top=90, width=10, height=10, area=40, cx=95.0, cy=95.0
        ),
    )
    diagonal = round(10 * 2 ** 0.5)

    assert mrz_region.residual_skew_deg(steep) == 45.0
    for turned in mrz_region.deskew_line(steep):
        assert turned.width == turned.height == diagonal
    # And the two boxes land on one level, which is the 45 degrees gone.
    turned = mrz_region.deskew_line(steep)
    assert {c.top for c in turned} == {43} and {c.bbox[3] for c in turned} == {57}


def test_a_steep_line_is_leveled_rather_than_refused():
    # There is no bound on a residual here, the way there is one at
    # `MAX_DESKEW_DEG`, and that is a decision rather than an omission: the
    # answer to a tilted line is to level it.  A future bound would be a
    # deliberate decision, so the test is here to make it fail on the day it
    # is written -- which is the same argument 4.1's own bound carries.
    steep = tuple(
        component_record(left=10 * i, top=9 * i, width=6, height=6)
        for i in range(5)
    )

    assert mrz_region.residual_skew_deg(steep) > 40.0
    assert abs(mrz_region.residual_skew_deg(mrz_region.deskew_line(steep))) < 0.01


def test_the_group_is_still_one_group_reading_left_to_right_after_the_turn():
    # 4.10's requirements, held on the group this hands over rather than on
    # the one it was given: 4.5 owns "a line" and 4.10 segments along x, so a
    # turn that split the group or reversed it would break the cell order
    # that 4.11 maps to field offsets.
    for turned in turned_of(rotated_mrz(2.0)):
        assert [c.cx for c in turned] == sorted(c.cx for c in turned)
        assert [len(group) for group in mrz_region.group_lines(turned)] == [
            len(turned)
        ]


def test_the_numbers_are_plain_python_and_not_numpy_scalars():
    # 4.3's rule, carried through the rotation.  OpenCV's matrix is a numpy
    # array and every number below came out of it, so this is where a
    # `numpy.float64` would enter the record -- and 4.13's empty result
    # becomes a JSON body, which no encoder will take one of.
    for turned in turned_of(rotated_mrz(2.0)):
        for component in turned:
            assert type(component.left) is int
            assert type(component.top) is int
            assert type(component.width) is int
            assert type(component.height) is int
            assert type(component.area) is int
            assert type(component.cx) is float
            assert type(component.cy) is float
    assert type(readings_of(upright_mrz())[0]) is float


def test_four_one_corrected_the_page_already_and_this_does_not_correct_it_twice():
    # The word in the task is *residual*, and this is what pins it.  After
    # 4.1 has run, the two lines read **+0.17 and +0.02** -- the same as a
    # page that was never turned at all, and nothing like the 2 degrees the
    # page was handed.  A 4.9 that re-measured the page instead of the line
    # would answer 2.0 here and turn the line twice.
    for turned in (2.0, 5.0):
        page = mrz_region.deskew(rotated_mrz(turned))
        readings = readings_of(page)

        assert all(abs(reading) < 0.3 for reading in readings), readings
        assert all(
            abs(mrz_region.residual_skew_deg(line)) < 0.3
            for line in turned_of(page)
        )


# --- 4.10: the line's ink, as one cell per run of columns -----------------


#: What the fixture *drew*, one entry per line, as opposed to
#: PRINTED_CHARACTERS' total.  4.10's shortfall is a per-line claim and needs
#: the per-line number to be made against.
DRAWN_PER_LINE = tuple(len(text) for text in LINES)


def cells_of(frame, turn=False):
    """One tuple of cells per surviving line, in the lines' own order.

    A cell is read off the line 4.6 kept, which is the module docstring's
    claim; the ``turn`` switch exists only for the one test that measures what
    4.9's turn costs, and is off by default because it is worse input.
    """
    return tuple(
        mrz_region.segment_cells(mrz_region.deskew_line(line) if turn else line)
        for line in mrz_region.filter_lines(lines_of(frame))
    )


def zone_of(line_count, line_length, pitch=12, left=10, top=20, leading=40):
    """One longhand zone: `line_count` lines of `line_length` glyph records.

    Written here rather than drawn, for the reason 4.14 is the task that draws
    it: the point of this test is the *count*, and a drawn line whose glyphs
    merge cannot answer a count question at all.
    """
    return tuple(
        tuple(
            component_record(left=left + pitch * i, top=top + leading * row)
            for i in range(line_length)
        )
        for row in range(line_count)
    )


def line_length_of(name):
    """The characters `name` prints per line, out of Part 3's own table."""
    return next(
        length for (_, length), shape in document.MRZ_SHAPES.items() if shape == name
    )


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_the_cell_count_is_the_length_of_the_format_the_zone_was_inferred_to_be(
    shape, name
):
    # The test 4.10 asks for, and both of its halves are the point: a line that
    # segments into some number of cells says nothing unless that number is
    # the one its *format* prints, and a format inferred from the zone says
    # nothing unless the cells come back at that length.  Asserting either
    # alone would pass on a function returning one cell per record.
    #
    # The length is read out of MRZ_SHAPES -- the same table `infer_format`
    # reads, and Part 3's own statement of the three shapes -- rather than
    # written into this test, so a fourth format is one row and not a fourth
    # thing to type here.  The zone is longhand for the reason the handover
    # gives 4.7: a hand-made zone can carry a format's exact width, and this
    # fixture cannot (see the shortfall test below).
    line_count, line_length = shape
    zone = zone_of(line_count, line_length)

    inferred = mrz_region.infer_format(zone)
    cells = tuple(mrz_region.segment_cells(line) for line in zone)

    assert inferred == name
    assert line_length_of(inferred) == line_length
    assert len(zone) == line_count
    assert {len(line) for line in cells} == {line_length}
    # And the two halves stay independent: the count is read off the ink, not
    # off the table, which is what would make the assertion above a
    # restatement.  A line one character short of its format still comes back
    # one cell short of it, with nothing padding it to the shape.
    short = zone_of(line_count, line_length - 1)
    assert len(mrz_region.segment_cells(short[0])) == line_length - 1


@pytest.mark.parametrize("turned", [0.0, 2.0, 5.0])
def test_the_profile_is_the_cuts_own_projection_and_no_frame_is_cut(turned):
    # 4.9's promise, held at the step it was made for: everything downstream
    # of a turned group reads positions, because a turned box is no longer a
    # slice of the cut.  So the profile this step segments along must be the
    # same projection the *frame* gives -- not an approximation of it, and not
    # a slice of anything.  Measured over this fixture's two lines at each
    # angle, the columns the records claim and the columns `binary` holds agree
    # one for one, and that is arithmetic rather than luck: a connected
    # component's box is the exact projection of its pixels on each axis.
    #
    # The tilted captures are the half that matters: a page bowed along its
    # binding is the ordinary case, so a box that is "a rectangle around
    # slanted ink" would be expected to claim columns the frame does not have.
    # It does not, and that is why 4.10 segments the line 4.6 kept.
    frame = upright_mrz() if not turned else rotated_mrz(turned)
    binary = binary_of(frame)
    for line, cells in zip(mrz_region.filter_lines(lines_of(frame)), cells_of(frame)):
        left = min(component.bbox[0] for component in line)
        top = min(component.bbox[1] for component in line)
        right = max(component.bbox[2] for component in line)
        bottom = max(component.bbox[3] for component in line)
        from_the_frame = (binary[top:bottom, left:right] > 0).any(axis=0)
        from_the_records = np.zeros(right - left, bool)
        for component in line:
            from_the_records[
                component.bbox[0] - left: component.bbox[2] - left
            ] = True

        assert from_the_records.shape == from_the_frame.shape
        assert (from_the_records == from_the_frame).all()
        assert not (from_the_records & ~from_the_frame).any()
        # The cells are the runs of that profile and nothing is sliced to get
        # them: one per stretch of occupied columns, which is one plus the
        # number of times a stretch ends.  Counted off the *frame*, so the
        # frame decides the number and the function is only asked to agree.
        run_ends = from_the_records[:-1] & ~from_the_records[1:]
        assert len(cells) == 1 + int(run_ends.sum())


@pytest.mark.parametrize("gap,cells", [(0, 1), (1, 2), (2, 2)])
def test_a_cell_is_a_run_of_ink_and_sharing_a_column_is_what_makes_one(gap, cells):
    # What a gap *is*, held at the edges rather than described: a column either
    # holds ink or it does not, so two records whose boxes abut share a
    # column and are one cell, and one blank column between them is already
    # two.  There is no threshold here to be off by one -- a gap of zero and a
    # gap of one are the whole of the decision.
    line = (
        component_record(left=10, top=40, width=10, height=12),
        component_record(left=20 + gap, top=40, width=10, height=12),
    )

    segmented = mrz_region.segment_cells(line)

    assert len(segmented) == cells
    assert sum(len(cell) for cell in segmented) == 2


def test_every_record_handed_in_lands_in_exactly_one_cell_and_is_that_record():
    # The records come back rather than copies of them, for
    # `filter_glyphs`'s reason: 4.9 fits lines through these centroids and
    # 4.12 cuts its boxes out of these boxes, so a rebuilt record would be a
    # second measurement of a blob nobody moved.  And every one of them lands
    # exactly once -- a cell index that skipped a record would put 4.11's
    # field offsets out by one with nothing to show for it.
    line = tuple(
        component_record(left=10 + 12 * i, top=40, width=8, height=12)
        for i in range(6)
    ) + (component_record(left=82, top=40, width=8, height=12),)

    segmented = mrz_region.segment_cells(line)
    returned = [component for cell in segmented for component in cell]

    assert len(returned) == len(line)
    assert {id(component) for component in returned} == {
        id(component) for component in line
    }
    # One cell per record here, and the touching pair is the seventh.
    assert [len(cell) for cell in segmented] == [1, 1, 1, 1, 1, 1, 1]


def test_the_cells_read_left_to_right_whatever_order_the_line_arrives_in():
    # 4.5 sorts a line left to right and 4.11 indexes the cells, so cell 0
    # being the leftmost character is the claim 4.10 exists to hold -- and it
    # is held by *reading the profile*, not by trusting the order the records
    # arrived in, which is why handing the same line over backwards has to
    # give the same cells.
    line = tuple(
        component_record(left=10 + 20 * i, top=40, width=8, height=12)
        for i in range(4)
    )

    assert mrz_region.segment_cells(line[::-1]) == mrz_region.segment_cells(line)
    assert [
        cell[0].left for cell in mrz_region.segment_cells(line[::-1])
    ] == sorted(component.left for component in line)


def test_a_line_of_no_glyphs_has_no_cells_and_a_line_of_one_glyph_has_one():
    # Both are arithmetic rather than judgements.  4.13 has to be able to say
    # "no MRZ here" without an exception, so the empty line cannot raise and
    # cannot come back with a cell at the origin -- which is the same reason
    # 4.8 declines to give an empty line a polygon.
    assert mrz_region.segment_cells(()) == ()

    one = (component_record(left=7, top=40, width=8, height=12),)

    assert mrz_region.segment_cells(one) == (one,)


def test_a_record_of_no_width_is_not_lost_and_is_a_column_of_its_own():
    # `extract_components` cannot produce one, though a caller can hand one
    # over, and 4.4, 4.5 and 4.8 each decided what to do with a degenerate
    # record rather than let it disappear.  A box of no width still stands on
    # the column its own `left` names, so it is given that column: two of them
    # on their own are two cells, and one between two records joins the run
    # beside it -- never a cell counted from nothing.
    two_empty = (
        component_record(left=10, top=40, width=0, height=12),
        component_record(left=40, top=40, width=0, height=12),
    )
    assert len(mrz_region.segment_cells(two_empty)) == 2
    assert all(
        len(cell) == 1 for cell in mrz_region.segment_cells(two_empty)
    )

    between = (
        component_record(left=10, top=40, width=10, height=12),
        component_record(left=20, top=40, width=0, height=12),
        component_record(left=30, top=40, width=10, height=12),
    )
    segmented = mrz_region.segment_cells(between)

    assert [len(cell) for cell in segmented] == [2, 1]
    assert sum(len(cell) for cell in segmented) == 3


@pytest.mark.parametrize(
    "turned,expected", [(2.0, (22, 26)), (3.0, (10, 20)), (5.0, (1, 4))]
)
def test_the_turns_own_boxes_are_what_would_close_the_gaps_and_this_does_not(
    turned, expected
):
    # 4.9 was written on the premise that a leaning line has to be levelled
    # before it can be segmented along x, and **that premise is measured false
    # here**: a blob's box is its ink's own projection at any tilt, so the
    # leaning line segments into exactly the ink's runs (the test above holds
    # it against the frame's own pixels).  What does cost cells is 4.9's
    # *output*, because rotating a box's four corners and taking the rounded
    # bounds is the bounds of a rotated rectangle rather than of the ink in it
    # -- wider by `height * sin(angle)`, which is 0.6 pixels at 2 degrees and
    # 1.3 at 5 on this fixture's 15-row glyphs, against gaps of 1 and 2.
    #
    # So the turned copy never gains a cell and, from 3 degrees on, loses
    # several; at 5 degrees it hands over *one* cell for the whole line, which
    # is the number a future bound on 4.9 would have to beat.  4.9's own
    # sentence is right that a turn can cost cells and wrong about the size:
    # it is `height * sin(angle)`, not the width of a glyph.
    page = rotated_mrz(turned)

    level_cells = cells_of(page, turn=False)
    turned_cells = cells_of(page, turn=True)

    assert all(
        len(after) <= len(before)
        for before, after in zip(level_cells, turned_cells)
    )
    assert tuple(len(line) for line in turned_cells) == expected
    if turned > 2.0:
        assert all(
            len(after) < len(before)
            for before, after in zip(level_cells, turned_cells)
        )
    else:
        assert [len(line) for line in level_cells] == list(expected)
    # And the residual is the page's own lean, so the collapse is attributable
    # to the rotation rather than to the page having cut differently.
    readings = readings_of(page)
    assert all(abs(reading + turned) < 0.25 for reading in readings), readings


def test_the_count_is_a_lower_bound_because_a_merged_pair_is_one_cell():
    # The honest limit of the step, measured on this fixture's own page rather
    # than left to be discovered by 4.11.  The two lines print **25 and 28**
    # characters and segment into **23 and 27** cells, and every missing cell
    # is accounted for: this cut merges a pair of characters into one blob
    # (8-connectivity joins corners that touch), and one line also has two
    # records whose boxes share a column.  A merged pair is one run of ink with
    # no gap in it, so no gap profile can split it -- which is why a cell count
    # is a *lower* bound and 4.11's index-to-field mapping is exact only up to
    # the first merge.  4.14's generator, in a monospaced face, is what
    # re-measures this.
    lines = mrz_region.filter_lines(lines_of(upright_mrz()))

    assert len(lines) == len(DRAWN_PER_LINE)
    for line, printed in zip(lines, DRAWN_PER_LINE):
        # Segmented from the line as it was handed over, so `is` below is the
        # identity of the record `filter_lines` passed on rather than a value
        # match against 4.9's rebuilt copy.
        cells = mrz_region.segment_cells(line)
        median = statistics.median(component.width for component in line)
        merged = [
            component for component in line if component.width > 1.5 * median
        ]
        shared = [cell for cell in cells if len(cell) > 1]

        assert len(merged) == 1, "one pair merged on this line"
        assert printed == len(line) + len(merged)
        assert len(cells) == len(line) - len(shared)
        assert len(cells) < printed
        # And the merged blob is one cell holding one record: a cell is a run
        # of ink, not a count of characters the run cannot be shown to hold.
        widest = max(line, key=lambda component: component.width)
        assert widest in merged
        assert [
            len(cell) for cell in cells if any(c is widest for c in cell)
        ] == [1]
    assert tuple(len(cells) for cells in cells_of(upright_mrz())) == (23, 27)


# --- 4.11: a cell index to a field, read out of the layout ---------------


def cells_named(name, line_count, line_length):
    """The field each cell of a longhand zone names, cell by cell."""
    return [
        mrz_region.cell_field(name, number, index)
        for number, line in enumerate(zone_of(line_count, line_length), start=1)
        for index in range(len(mrz_region.segment_cells(line)))
    ]


def printed_fields(name):
    """The layout's field names, one per position they print, in order."""
    return [
        field
        for spans in mrz_region.MRZ_LAYOUTS[name].values()
        for field, (start, stop) in spans.items()
        for _ in range(stop - start + 1)
    ]


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_every_cell_of_every_line_names_the_field_that_prints_it(shape, name):
    # The task 4.11 asks for, and the whole of it: a cell index in, the field
    # printed at that position out.  Three claims in one test because any one
    # of them alone passes on a function returning something plausible.
    #
    # No position is typed here -- the span each answer is checked against
    # comes out of the same table the module reads, so a layout corrected in
    # one place can neither fail this test nor pass it on a stale number.  The
    # zone is longhand, `zone_of`, for 4.10's reason: a drawn line whose
    # glyphs merge cannot answer a cell question, and this fixture's own
    # lines infer as `None`.
    line_count, line_length = shape
    named = cells_named(name, line_count, line_length)

    # Every cell is inside the line's own width, so every cell is named.
    assert len(named) == line_count * line_length
    assert all(answer is not None for answer in named)
    # Each answer is the span holding this cell, and the offset counts from
    # that field's own first position -- so right names with wrong offsets
    # fail here rather than passing.
    for line_number, spans in enumerate(
        mrz_region.MRZ_LAYOUTS[name].values(), start=1
    ):
        start = (line_number - 1) * line_length
        for index, (field, offset) in enumerate(named[start:start + line_length]):
            first, last = spans[field]
            assert first <= index + 1 <= last
            assert offset == index + 1 - first
    # And the cells tile the line: the fields come back in the layout's own
    # order, each one once, with nothing between them and nothing after the
    # last.  This is the property 4.12 cuts its field boxes out of.
    assert [field for field, _ in named] == printed_fields(name)


def test_the_cell_holding_the_passport_number_check_digit_names_that_digit():
    # The task 4.11 names as its test: the passport-number check digit on a
    # TD3 line 2 is a field of `td3.TD3_LINE_2` in its own right, so the cell
    # printed at its position names it -- and nothing else, because a printed
    # digit is one position wide.
    #
    # The index comes out of the layout and the cells out of 4.10 over the
    # longhand zone, so this asserts the two halves agree rather than restating
    # either.  A mapping off by one in either direction puts the digit on a
    # neighbouring cell and fails the neighbour assertions below.
    named = [field for field, _ in cells_named("TD3", 2, 44)][44:]
    first, last = mrz_region.MRZ_LAYOUTS["TD3"]["line_2"][
        "document_number_check_digit"
    ]

    assert first == last
    assert named.count("document_number_check_digit") == 1
    assert named.index("document_number_check_digit") == first - 1
    assert mrz_region.cell_field("TD3", 2, first - 1) == (
        "document_number_check_digit",
        0,
    )
    # The neighbours are the document number's last character and the
    # nationality, so a shift of one cell either way is caught rather than
    # absorbed by a field that happens to be wide.
    assert named[first - 2] == "document_number"
    assert named[first] == "nationality"


def test_cell_thirteen_is_the_date_of_birth_and_not_a_check_digit():
    # tasks.md 4.11 asks for "a test asserting cell 13 on TD3 line 2 maps to
    # the passport-number check digit".  It does not, and cannot: the layout
    # prints that check digit at position 10, so it is **cell 9**, while cell
    # 13 is printed at position 14 -- the first position of the date of birth.
    # This test says which of the task's two clauses this step implements.
    #
    # The first clause is the one implemented: the mapping reuses the Part 2/3
    # layout constants so there is exactly one source of truth.  Satisfying the
    # example would need a span this repository's own table does not contain,
    # and a second table of positions is the drift that clause exists to
    # prevent -- with nothing to check it against, since there is no copy of
    # Doc 9303 here.  The same shape as 2.4's `IND`: the rule the sentence
    # states, not the example it illustrates.
    assert mrz_region.cell_field("TD3", 2, 9) == (
        "document_number_check_digit",
        0,
    )
    assert mrz_region.cell_field("TD3", 2, 13) == ("date_of_birth", 0)
    assert mrz_region.cell_field("TD3", 2, 13) != mrz_region.cell_field("TD3", 2, 9)


def test_a_line_is_numbered_from_one_and_a_cell_from_zero():
    # The two conventions, pinned separately, because they are two different
    # numbers about two different things and only one of them is an index.  A
    # line is what the standard numbers and what the layouts key themselves
    # (`line_1`, `line_2`, `line_3`); a cell is a member of the tuple 4.10
    # returns, whose first element is cell 0.  So cell 0 is position 1, and
    # line 0 is not a line at all.
    assert mrz_region.cell_field("TD3", 1, 0) == ("document_code", 0)
    assert mrz_region.cell_field("TD3", 2, 0) == ("document_number", 0)
    assert td3.TD3_LINE_1["document_code"] == (1, 2)
    assert td3.TD3_LINE_2["document_number"] == (1, 9)
    assert mrz_region.cell_field("TD3", 0, 0) is None


def test_a_format_line_or_cell_that_is_not_there_maps_to_nothing():
    # Three refusals, all reachable rather than decorative.  An unknown format
    # name is what a caller holding something other than 4.7's answer would
    # pass; line 3 is a TD1 line a TD3 does not print; and a cell past the end
    # of the line is a real reading of a real cut, because a broken stroke
    # splits a glyph -- 4.10's count is a lower bound in one direction and
    # nothing at all in the other.
    assert mrz_region.cell_field("TD4", 1, 0) is None
    assert mrz_region.cell_field("", 1, 0) is None
    assert mrz_region.cell_field(None, 1, 0) is None
    assert mrz_region.cell_field("TD1", 4, 0) is None
    assert mrz_region.cell_field("TD3", 3, 0) is None
    assert mrz_region.cell_field("TD3", 2, -1) is None
    assert mrz_region.cell_field("TD3", 2, 44) is None
    assert mrz_region.cell_field("TD3", 2, 10_000) is None


def test_the_layout_table_is_the_formats_own_and_not_a_second_copy():
    # The "exactly one source of truth" half of the task, held by identity
    # rather than by equality: `MRZ_LAYOUTS` must *be* the dicts Parts 2 and 3
    # built, so a position corrected in `td3` reaches 4.11 and 4.12 without
    # being typed again.  A copy that compared equal would pass an equality
    # assertion and drift the moment either table was edited.
    assert mrz_region.MRZ_LAYOUTS["TD1"] is td1.TD1
    assert mrz_region.MRZ_LAYOUTS["TD2"] is td2.TD2
    assert mrz_region.MRZ_LAYOUTS["TD3"] is td3.TD3
    assert set(mrz_region.MRZ_LAYOUTS) == set(document.MRZ_SHAPES.values())


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_a_whole_zone_of_a_format_names_every_field_it_prints(shape, name):
    # 4.11 end to end, and the shape 4.12 will consume: infer the format from
    # the zone, segment each line, read the fields out of the cells.  Every
    # field the format prints is named, in the layout's order, which is what
    # makes a per-field box meaningful rather than a box per line.
    line_count, line_length = shape
    zone = zone_of(line_count, line_length)
    named = [field for field, _ in cells_named(name, line_count, line_length)]

    assert mrz_region.infer_format(zone) == name
    assert named == printed_fields(name)
    # And the printed composite digit sits where the layout puts it, on the
    # line the layout puts it: the last cell of TD3's and TD2's line 2, and
    # of TD1's line 2 as well -- a TD1's line 3 is the name, which is what
    # makes a TD1 three lines where a TD3 is two.
    for number, spans in enumerate(
        mrz_region.MRZ_LAYOUTS[name].values(), start=1
    ):
        if "composite_check_digit" not in spans:
            continue
        position = spans["composite_check_digit"][0]
        assert named[(number - 1) * line_length + position - 1] == (
            "composite_check_digit"
        )
        break


# --- 4.12: one box per field, cut from the line 4.6 kept -----------------


#: The three zones, one per format, each parsed rather than constructed --
#: `field_regions` reads `.format` off a document and nothing else, so what
#: matters is that the record is a real one a real parser built.  The
#: characters are the generator's own specimens, which are the characters
#: test_document.py prints, so the repository holds one specimen per format
#: and not one per test file: 4.14's generator draws these and this file
#: parses them, and a correction to either would have to be made twice if the
#: text were written out again here.
ZONES = {name: list(lines) for name, lines in mrz_images.SPECIMENS.items()}


def parsed_of(name, zone=None):
    """A real `MrzDocument` of ``name``, parsed rather than constructed."""
    return document.parse_mrz(ZONES[name] if zone is None else zone)


def edited(zone, line_number, first, text):
    """The same zone with ``text`` printed at position ``first`` of a line."""
    rows = list(zone)
    row = rows[line_number - 1]
    rows[line_number - 1] = row[: first - 1] + text + row[first - 1 + len(text):]
    return rows


def box_of(polygon):
    """The half-open box 4.8's four corners name, read *by position*.

    The two corners used are the top left and the bottom right, which is only
    a box if the polygon is one -- 4.8's `holds` is what says it is, reading
    all four corners by position so a quad in the wrong order fails there
    rather than passing here.
    """
    (top_left, _, bottom_right, _) = polygon
    return (top_left[0], top_left[1], bottom_right[0], bottom_right[1])


def extent_of(records):
    """The half-open box a run of records' own boxes occupies."""
    return (
        min(component.bbox[0] for component in records),
        min(component.bbox[1] for component in records),
        max(component.bbox[2] for component in records),
        max(component.bbox[3] for component in records),
    )


def enclosing(outer, inner):
    """Whether ``inner``'s half-open box sits inside ``outer``'s."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def printed_names(name):
    """The layout's field names, one per field, in printed order."""
    return [
        field
        for spans in mrz_region.MRZ_LAYOUTS[name].values()
        for field in spans
    ]


def regions_of(name):
    """The longhand zone of ``name`` and the regions cut out of it.

    ``zone_of`` rather than a drawn page, for 4.10's reason: the point of
    these tests is which *characters* a box covers, and a drawn line whose
    glyphs merge cannot answer that.  The zone is what `filter_lines` would
    hand over: uniform glyphs on a uniform pitch.
    """
    line_count, line_length = next(
        shape for shape, value in document.MRZ_SHAPES.items() if value == name
    )
    zone = zone_of(line_count, line_length)
    return zone, mrz_region.field_regions(parsed_of(name), zone)


def test_the_date_of_birth_box_covers_the_date_of_birth_and_not_the_expiry():
    # The test 4.12 asks for, and both of its halves are the point.  A box
    # that covered the whole line would satisfy the first half and pass
    # nothing, so the ground truth is what the *zone drew* at the positions
    # the layout prints -- read out of the layout rather than typed, so a
    # span corrected in a format module moves this test with it and a box
    # cut from the wrong cells fails on a value rather than on a name.
    zone, regions = regions_of("TD3")
    spans = mrz_region.MRZ_LAYOUTS["TD3"]["line_2"]
    first, last = spans["date_of_birth"]
    expiry_first, expiry_last = spans["date_of_expiry"]
    birth_characters = zone[1][first - 1:last]
    expiry_characters = zone[1][expiry_first - 1:expiry_last]

    assert "date_of_birth" in regions and "date_of_expiry" in regions
    # Covers the six printed characters, and is level and plumb: 4.8's own
    # `holds`, which reads all four corners by position.
    assert holds(regions["date_of_birth"], extent_of(birth_characters))
    # ... and covers *only* them: the box is the characters' own extent, so
    # the equality is what makes the negative half below true rather than
    # merely likely.
    assert box_of(regions["date_of_birth"]) == extent_of(birth_characters)
    assert not any(
        enclosing(box_of(regions["date_of_birth"]), component.bbox)
        for component in expiry_characters
    )
    # The two dates are neighbours in the layout with the sex marker and two
    # check digits between them, so neither box can reach the other even by
    # one cell of slack -- and a box cut a cell either way fails here.
    assert box_of(regions["date_of_expiry"]) == extent_of(expiry_characters)
    assert box_of(regions["date_of_birth"])[2] <= expiry_characters[0].bbox[0]
    # Plain ints, so a caller can serialise the polygon without a numpy
    # scalar turning up at the JSON boundary in Part 11.
    assert all(
        isinstance(value, int)
        for point in regions["date_of_birth"]
        for value in point
    )


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_every_field_the_document_extracted_has_one_box_in_printed_order(
    shape, name
):
    # The shape 6.2 needs -- a region per field, named as the document names
    # its fields -- on all three formats rather than on the one 4.12's own
    # example names, because a table read for a TD3 is a table that can be
    # wrong for a TD1 and pass everything else here.
    zone, regions = regions_of(name)
    line_polygons = mrz_region.line_polygons(zone)

    assert parsed_of(name).format == name
    assert list(regions) == printed_names(name)
    # The keys are the document's own field names, read rather than
    # translated: `sources` is what a parse recorded, and a name here that is
    # not in it would be a region nothing downstream could label.
    assert set(regions) == set(parsed_of(name).sources)
    # Every field prints on exactly one line of its format, so each box is
    # cut from the line its layout puts the field on -- and is inside 4.8's
    # polygon for that line, which is 4.8's own answer rather than a margin
    # this step could have invented.
    for number, spans in enumerate(
        mrz_region.MRZ_LAYOUTS[name].values(), start=1
    ):
        line_box = box_of(line_polygons[number - 1])
        for field in spans:
            assert enclosing(line_box, box_of(regions[field]))
    # A box per field is not a box per line: there is one box for every
    # field the layout prints, and they are not the three (or two) line
    # polygons with the same name twice.
    assert len(regions) == len(printed_names(name)) > len(line_polygons)


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_every_field_box_is_the_box_of_the_characters_its_span_prints(
    shape, name
):
    # What a union of cells must be and what a box cut from the wrong cells
    # is not: the fields *partition* a line (2.1 gives every position to
    # exactly one field), so each box is the extent of the characters its own
    # span prints, their boxes are disjoint and read left to right in the
    # layout's own order, and every character of the line sits inside exactly
    # one of them.  A box cut from the whole line passes "covers its
    # characters" and fails every line here.
    zone, regions = regions_of(name)
    line_polygons = mrz_region.line_polygons(zone)

    for number, spans in enumerate(
        mrz_region.MRZ_LAYOUTS[name].values(), start=1
    ):
        line_box = box_of(line_polygons[number - 1])
        boxes = []
        for field in spans:
            first, last = spans[field]
            drawn = extent_of(zone[number - 1][first - 1:last])
            assert box_of(regions[field]) == drawn
            assert enclosing(line_box, drawn)
            boxes.append(drawn)

        assert boxes[0][0] == line_box[0], "the first field starts the line"
        assert boxes[-1][2] == line_box[2], "the last field ends the line"
        assert all(
            before[2] < after[0] for before, after in zip(boxes, boxes[1:])
        ), "the fields are disjoint, and in the layout's own order"
        assert all(
            sum(
                enclosing(box, component.bbox) for box in boxes
            ) == 1
            for component in zone[number - 1]
        ), "every character of the line is in exactly one field's box"


def test_a_field_no_cell_names_is_absent_rather_than_present_and_null():
    # 4.10's lower bound carried one step on.  A line whose last few
    # characters were never cut has no ink for those fields to be made of,
    # and the answer says so by leaving them out rather than by reporting a
    # `None`: "looked, found nothing" is a different statement, and one a
    # caller could act on as though it had been measured.
    zone = zone_of(2, 44)
    short = zone[:1] + (zone[1][:30],)
    regions = mrz_region.field_regions(parsed_of("TD3"), short)

    assert len(mrz_region.segment_cells(short[1])) == 30
    assert "nationality" in regions
    # A field that *straddles* the shortfall keeps the half that was cut:
    # positions 29-30 of 29-42 were printed and are reported, and only the
    # fields entirely past the cut are missing.
    assert "personal_number" in regions
    assert "personal_number_check_digit" not in regions
    assert "composite_check_digit" not in regions
    assert None not in regions.values()
    assert list(regions)[-1] == "personal_number"


def test_a_document_this_project_does_not_parse_is_an_empty_answer():
    # 4.13 is built on this: "no MRZ here" is a value this module returns
    # rather than an exception it raises, and the three refusals
    # `cell_field` makes all arrive here the same way -- a field that is not
    # in the answer.
    zone = zone_of(2, 44)
    elsewhere = dataclasses.replace(parsed_of("TD3"), format="TD4")

    assert mrz_region.field_regions(elsewhere, zone) == {}
    assert mrz_region.field_regions(parsed_of("TD3"), ()) == {}
    # A zone with a line the format does not have is the other direction:
    # line 1's fields are cut and line 2's are simply not there.
    assert set(mrz_region.field_regions(parsed_of("TD3"), zone[:1])) == set(
        mrz_region.MRZ_LAYOUTS["TD3"]["line_1"]
    )


def test_the_boxes_are_cut_from_the_unturned_line_and_not_from_4_9_s_copy():
    # 4.8's note and 4.9's measurement, held at the step that depends on
    # them.  A line leaning 8 degrees still segments into its own cells
    # without a turn -- a blob's box is its ink's projection at any tilt --
    # while `deskew_line`'s copy inflates every box by `height * sin(angle)`,
    # which at 8 degrees on glyphs 10 wide is 1.4 pixels against a one-pixel
    # gap, closing every gap on the line.  So this pins both halves at once:
    # the counterfactual is measured here rather than assumed, and the boxes
    # still tile the line exactly as they do on a level one.
    degree = 8
    pitch, left, top, leading = 11, 10, 20, 200
    rise = math.tan(math.radians(degree)) * pitch
    zone = tuple(
        tuple(
            component_record(
                left=left + pitch * index,
                top=round(
                    top + leading * row + rise * (index - (44 - 1) / 2)
                ),
            )
            for index in range(44)
        )
        for row in range(2)
    )
    regions = mrz_region.field_regions(parsed_of("TD3"), zone)

    assert all(
        abs(reading - degree) < 1.0
        for reading in (
            mrz_region.residual_skew_deg(line) for line in zone
        )
    ), "the fixture leans, and leans by what it says"
    # The turned copy is measurably worse input -- at this angle it hands
    # over fewer cells than it was given, which is the whole of 4.9's cost.
    assert all(
        len(mrz_region.segment_cells(mrz_region.deskew_line(line)))
        < len(mrz_region.segment_cells(line))
        for line in zone
    )
    # And the unturned cut is still exact: every field of the layout has a
    # box, and the boxes tile line 2 with nothing overlapped or missing.
    assert list(regions) == printed_names("TD3")
    spans = mrz_region.MRZ_LAYOUTS["TD3"]["line_2"]
    placed = sorted(box_of(regions[field]) for field in spans)
    line_box = box_of(mrz_region.line_polygons(zone)[1])
    assert placed[0][0] == line_box[0] and placed[-1][2] == line_box[2]
    assert all(
        before[2] < after[0] for before, after in zip(placed, placed[1:])
    )
    assert all(
        sum(enclosing(box, component.bbox) for box in placed) == 1
        for component in zone[1]
    ), "every character of line 2 is in exactly one field's box"


def test_what_the_parse_read_cannot_move_a_box():
    # The claim 4.12 makes about its document argument, held rather than
    # asserted in prose: the same zone drawn the same way gives the same
    # boxes whichever six characters its line 2 prints at the date of birth,
    # because the format names the layout and the cells name the fields, and
    # no character is read here.  A step that read `document.date_of_birth`,
    # or one that cut its boxes out of the parsed text rather than the ink,
    # would move them.
    _, regions = regions_of("TD3")
    elsewhere = edited(ZONES["TD3"], 2, 14, "121231")
    printed = mrz_region.field_regions(
        parsed_of("TD3", elsewhere), zone_of(2, 44)
    )

    assert parsed_of("TD3", elsewhere).date_of_birth == "121231"
    assert printed == regions


# --- the boundary this module must not move -------------------------------


def test_the_character_readers_still_import_without_opencv():
    # Parts 1-3 are pure arithmetic over characters and load neither cv2 nor
    # numpy, so a caller can parse a stored zone with no OpenCV in the process.
    # This module is the first file in the package to import cv2, which makes
    # that property one careless `from .mrz_region import deskew` away from
    # being untrue -- and nothing else in the suite would notice.
    backend_root = pathlib.Path(mrz.__file__).parents[3]
    probe = (
        "import sys;"
        "import app.pipeline.tier0.document, app.pipeline.tier0.td1,"
        " app.pipeline.tier0.td2, app.pipeline.tier0.td3;"
        "print('cv2' in sys.modules, 'numpy' in sys.modules)"
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=backend_root, capture_output=True, text=True, check=True,
    )

    assert result.stdout.strip() == "False False"


def test_the_module_raises_nothing_of_its_own():
    # 1.9's rule, from this module's side: MrzValueError is the package's one
    # error type, and a detector that raised a second one would put an
    # OpenCV failure and a "no MRZ here" into different except clauses at every
    # call site in 4.13.
    #
    # Walked rather than grepped, and that is 3.14's move applied here.  The
    # two substrings this replaces would have banned the *sentences* in the
    # module docstring that explain the rule -- 4.3's own prose says what a
    # raise would cost -- and a class statement is not an error type, which
    # is what the rule is about.  4.3 adds the first record in this module, so
    # the check now says what it meant: no `raise` anywhere, and no class that
    # is an exception.
    tree = ast.parse(
        pathlib.Path(mrz_region.__file__).read_text(encoding="utf-8")
    )

    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Raise)]
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id.endswith("Error")
            or isinstance(base, ast.Attribute) and base.attr.endswith("Error")
            or isinstance(base, ast.Name) and base.id in {"Exception", "BaseException"}
            for base in node.bases
        )
    ]
    assert not issubclass(mrz_region.MrzComponent, BaseException)

    assert mrz_region.__all__ == [
        "MAX_DESKEW_DEG",
        "MRZ_LAYOUTS",
        "MrzComponent",
        "MrzDetection",
        "binarize_inverted",
        "cell_field",
        "detect_mrz",
        "deskew",
        "deskew_line",
        "extract_components",
        "field_regions",
        "filter_glyphs",
        "filter_lines",
        "group_lines",
        "infer_format",
        "line_polygons",
        "residual_skew_deg",
        "segment_cells",
        "skew_deg",
        "to_gray",
    ]


def test_the_record_is_data_and_nothing_else():
    # The other half of what "no class" used to mean here.  MrzComponent
    # carries seven numbers and two derived views of them; a method on it
    # would be behaviour, and behaviour is where a second judgement about
    # what a glyph is would grow -- 4.4's band, not this record's.
    fields = [field.name for field in dataclasses.fields(mrz_region.MrzComponent)]
    public = {
        name
        for name in vars(mrz_region.MrzComponent)
        if not name.startswith("_")
    } - set(fields)

    assert fields == ["left", "top", "width", "height", "area", "cx", "cy"]
    assert public == {"bbox", "centroid"}


# --- 4.13: the detector, and the page with no MRZ on it -------------------

#: The block a hand-made zone's character is drawn as, and the advance it is
#: drawn at -- a two-pixel gap, so nothing here depends on 4.10's cells
#: finding a break.  The same numbers `zone_of` uses, for 4.10's reason.
ZONE_GLYPH_PX, ZONE_PITCH_PX = 10, 12
ZONE_LEFT, ZONE_TOP, ZONE_LEADING_PX = 10, 20, 40


def blank_page(level=255):
    """A page with nothing on it, at the size every other fixture is drawn at."""
    return np.full((PAGE_HEIGHT, PAGE_WIDTH, 3), level, np.uint8)


def zone_page(
    line_count, line_length, glyph=ZONE_GLYPH_PX, pitch=ZONE_PITCH_PX,
    left=ZONE_LEFT, top=ZONE_TOP, leading=ZONE_LEADING_PX, margin=60,
):
    """A white page carrying a hand-made zone, *drawn* rather than longhand.

    ``zone_of`` is longhand because a count is the question there; this is
    drawn because 4.13's question is whether a page comes back *named*, and
    only a page can answer that.  Blocks rather than letters, for the same
    reason: the drawn text fixture merges its own glyphs -- measured, 24 and
    27 blobs for two 44-character lines -- so it is a page of print rather
    than a zone, and 4.14's generator is the task that draws one properly.
    """
    height = top + leading * (line_count - 1) + glyph + margin
    width = left + pitch * (line_length - 1) + glyph + margin
    page = np.full((height, width, 3), 255, np.uint8)
    for row in range(line_count):
        for index in range(line_length):
            x, y = left + pitch * index, top + leading * row
            page[y:y + glyph, x:x + glyph] = (0, 0, 0)
    return page


def zone_shape(name):
    """The shape ``name`` prints, read out of Part 3's own table."""
    return next(
        shape for shape, value in document.MRZ_SHAPES.items() if value == name
    )


def zone_extent(
    row, line_length, glyph=ZONE_GLYPH_PX, pitch=ZONE_PITCH_PX,
    left=ZONE_LEFT, top=ZONE_TOP, leading=ZONE_LEADING_PX,
):
    """The half-open box ``zone_page`` drew line ``row`` into."""
    y = top + leading * row
    return (left, y, left + pitch * (line_length - 1) + glyph, y + glyph)


def zone_page_turned(angle, line_count=2, line_length=44):
    """The hand-made zone page, turned by ``angle`` degrees about its centre.

    A per-channel white for the corners, for the reason ``_border_fill``'s
    docstring gives and ``rotated_mrz`` repeats.
    """
    page = zone_page(line_count, line_length)
    height, width = page.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
    return cv2.warpAffine(
        page, matrix, (width, height),
        borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
    )


def detected(name):
    """What the detector makes of a drawn page carrying a zone of ``name``."""
    return mrz_region.detect_mrz(zone_page(*zone_shape(name)))


def test_a_blank_page_answers_no_mrz_rather_than_raising():
    # The test 4.13 asks for, and "rather than raising" is the claim the whole
    # call is inside: a detector that refused a page it could not read would
    # raise out of `m7_skew`, out of OpenCV, or out of this module's own code,
    # and a caller would then need an `except` around every frame it is handed
    # rather than around the one it cannot read.
    found = mrz_region.detect_mrz(blank_page())

    assert found == mrz_region.MrzDetection()
    assert found.format is None
    assert found.lines == ()
    assert found.regions == ()


@pytest.mark.parametrize(
    "level",
    [pytest.param(255, id="white-paper"), pytest.param(0, id="all-ink-page")],
)
def test_both_ways_a_blank_page_arrives_answer_the_same_empty_value(level):
    # 4.3 pins the two ways an *empty* frame reads at its own step: a page
    # whose cut went white is refused by 4.4's height ceiling, and a frame
    # with no ink has no component to begin with.  A uniform page arrives at
    # the detector in the second state whichever way round it is -- the local
    # cut reads a page as one or as the other, never as print -- so both are
    # held to the same empty value, and a detector that only understood the
    # white one would still pass a blank-page test.
    assert mrz_region.detect_mrz(blank_page(level)) == mrz_region.MrzDetection()


def test_two_lines_of_print_that_are_not_a_zone_name_no_format():
    # The page that looks like a TD3 and is not one, and the case that keeps
    # 4.7's refusal load-bearing at the top of the chain: `upright_mrz` draws
    # two 44-character lines, and the cut merges them to 24 and 27 blobs, so
    # the median of 25.5 is outside every shape's band.  A detector that named
    # the nearest of the three would name a format for a page this repository
    # drew itself, and a visa read as a passport shifts every field after it.
    found = mrz_region.detect_mrz(upright_mrz())
    median = statistics.median(len(line) for line in found.lines)

    assert found.format is None
    assert all(
        abs(median - length) > mrz_region.LINE_LENGTH_TOLERANCE
        for _, length in document.MRZ_SHAPES
    )
    # The ink is still reported.  4.8's answer is a measurement, and dropping
    # it because the *shape* was refused would throw away the one thing a
    # caller can draw to say there was something here to find.
    assert len(found.regions) == len(found.lines) == 2


@pytest.mark.parametrize(
    "angle",
    [
        pytest.param(2.0, id="two-degrees-clockwise"),
        pytest.param(-3.0, id="three-degrees-anticlockwise"),
        pytest.param(4.0, id="four-degrees-clockwise"),
    ],
)
def test_a_zone_on_a_tilted_page_is_still_found(angle):
    # 4.13's one claim about 4.1: the chain starts at the rotation, so a page
    # that arrives leaning is still a page whose zone gets named.  The first
    # assertion is the guard 4.1's own test uses -- without it this would be
    # passed by a detector that ignored the tilt entirely, since a zone drawn
    # upright is a zone found upright.  `measured_tilt` rather than
    # `skew_deg`, for the reason its own docstring gives: it shares no code
    # with the reading the detector follows, so a sign flip cannot make the
    # two agree.
    #
    # The glyph counts are exact at these angles and are *not* exact at 6,
    # where the turn costs one blob.  That is 4.10's "a cell count is a
    # lower bound", and a median of 43.5 and 44 is a TD3 either way.
    tilted = zone_page_turned(angle)
    found = mrz_region.detect_mrz(tilted)

    assert abs(measured_tilt(tilted)) > 1.5, "the fixture is not actually tilted"
    assert found.format == "TD3"
    assert [len(line) for line in found.lines] == [44, 44]


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_a_zone_drawn_on_a_page_is_named_and_located(shape, name):
    # The other half of the blank-page test, without which it proves nothing:
    # a detector that answered "no MRZ" to every page would pass it.  All
    # three formats rather than one, because a chain that reads a TD3 can be
    # a chain that was measured on a TD3.
    found = detected(name)

    assert found.format == name
    assert found.format in document.MRZ_SHAPES.values()
    assert len(found.lines) == len(found.regions) == shape[0]


def test_the_regions_are_the_lines_own_polygons_and_the_lines_come_with_them():
    # Two claims in one, because they are one answer split in two: the
    # polygons are 4.8's own boxes of the lines 4.6 kept -- read off the
    # blocks the page drew, not off a literal -- and the line groups are on the
    # record beside them.  Without the second half 4.10 and 4.12 would have
    # nothing to take, and a caller would have to run the whole chain a second
    # time to get a zone it had already measured.
    line_count, line_length = zone_shape("TD3")
    found = detected("TD3")

    assert found.regions == mrz_region.line_polygons(found.lines)
    assert all(
        holds(polygon, zone_extent(row, line_length))
        for row, polygon in enumerate(found.regions)
    )
    assert all(
        len(line) == line_length and line_count == len(found.lines)
        for line in found.lines
    )


@pytest.mark.parametrize(
    "shape,name", sorted(document.MRZ_SHAPES.items())
)
def test_the_field_boxes_are_still_cuttable_from_a_detected_page(shape, name):
    # What makes the record a detector's answer rather than a summary: 4.12
    # takes a parsed document and a zone, and until this task nothing turned a
    # page into either.  One box per field the layout prints, on all three
    # formats, from the lines the page was detected with.
    found = detected(name)
    regions = mrz_region.field_regions(parsed_of(name), found.lines)

    assert list(regions) == printed_names(name)
    assert set(regions) == set(parsed_of(name).sources)


def test_the_detection_is_data_and_nothing_else():
    # `MrzComponent`'s rule, applied to the record that answers for the whole
    # chain.  A method on it would be behaviour, and behaviour is where a
    # second judgement about what a page holds would grow: whether these
    # lines are a zone is 4.7's answer, already read into `format`, and a
    # method that re-derived it would be able to disagree with the field.
    fields = [field.name for field in dataclasses.fields(mrz_region.MrzDetection)]
    public = {
        name
        for name in vars(mrz_region.MrzDetection)
        if not name.startswith("_")
    } - set(fields)

    assert fields == ["format", "lines", "regions"]
    assert public == set()
    assert not issubclass(mrz_region.MrzDetection, BaseException)
