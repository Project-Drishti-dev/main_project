"""13.6 -- a capture's document corners are found, and they come back in one order.

The claim is small and exact: a photograph of a page on a dark surface is
answered with the four corners the page was laid at, clockwise from the top
left, as whole pixels -- and a frame holding no document is answered
:data:`~app.pipeline.tier1.corners.NO_CORNERS` rather than raised.

**The page is a synthetic one because the corners have to be known.**  The
printed specimen is laid at :data:`LAID_AT` and photographed on a background
below its paper, so the four corners it was laid at are ground truth rather
than a re-reading of whatever the detector happened to produce.

**The search is not this module's, and a sentinel holds it there.**  A stub
replaces ``find_card`` with an outline of its own and is handed a string in
place of an image, so the corners must follow the stub and nothing else; a
second detector written beside the five this repository already ships would
fail that test rather than quietly agree with them.
"""

import numpy as np
import pytest

from app.pipeline.tier1 import corners
from app.pipeline.tier1.corners import NO_CORNERS, detect_corners, order_corners
from app.quality_checker import m8_coverage
from app.risk.flags import EvidenceFlag
from tests.fixtures import document_images

#: The capture the page is photographed into, ``(width, height)``.
FRAME = (1200, 900)

#: Where the page's own corners were put, clockwise from the top left.  A
#: quadrilateral and not a rectangle: a rectangle would leave the ordering
#: with nothing to decide, and every corner would sit on two ties.
LAID_AT = ((180, 120), (1020, 200), (960, 780), (140, 700))

#: How far a found corner may sit from where the page was laid, in pixels.
#: The detector's own outline simplification sets this, not the fixture, and it
#: is well inside the paper's edge on a capture this size.
CORNER_TOLERANCE_PX = 6

#: Not an image: a stand-in proving Tier 1 hands the frame to ``find_card``
#: unopened and reads nothing off it itself.
NOT_AN_IMAGE = "this is not an image"


def photograph():
    """The printed page laid at :data:`LAID_AT` and photographed on a dark frame."""
    return document_images.photograph(
        document_images.render_document("passport"), LAID_AT, FRAME
    )


def blank_frame():
    """A capture of :data:`FRAME` holding nothing a detector can call a page."""
    return np.full((FRAME[1], FRAME[0], 3), 128, np.uint8)


def an_outline(points, method="quad"):
    """The record ``find_card`` answers: an outline and the way it was got."""

    def search(_image):
        return {
            "pts": np.array(points, np.float32).reshape(4, 2),
            "method": method,
            "area_frac": 0.45,
            "touches_border": False,
        }

    return search


def a_flag(region):
    """A well-formed flag over ``region``, or the refusal building it makes."""
    return EvidenceFlag(
        id="LAYOUT_DEVIATION",
        tier=1,
        label="Layout",
        weight_band="low",
        value=0.5,
        confidence=1.0,
        region=region,
        expected=None,
        found=None,
        reason="A field sat away from where the template puts it.",
        source_module="app.pipeline.tier1.corners",
        field=None,
    )


def test_the_four_corners_are_the_four_the_page_was_laid_at():
    found = detect_corners(photograph())

    assert len(found) == 4
    for pixel, laid in zip(found, LAID_AT):
        assert all(
            abs(got - want) <= CORNER_TOLERANCE_PX for got, want in zip(pixel, laid)
        ), f"{pixel} is not the corner the page was laid at {laid}"


def test_the_corners_come_back_clockwise_from_the_top_left():
    found = detect_corners(photograph())

    by_sum = sorted(found, key=lambda corner: corner[0] + corner[1])
    by_difference = sorted(found, key=lambda corner: corner[1] - corner[0])
    assert found == (
        by_sum[0],
        by_difference[0],
        by_sum[-1],
        by_difference[-1],
    )


def test_the_corners_are_whole_pixels_a_findings_region_will_accept():
    found = detect_corners(photograph())

    assert all(
        isinstance(corner, tuple)
        and all(isinstance(pixel, int) for pixel in corner)
        for corner in found
    )
    assert a_flag(found).region == found


def test_a_frame_holding_no_document_is_answered_and_not_raised():
    assert detect_corners(blank_frame()) == NO_CORNERS


def test_the_search_is_the_quality_checkers_and_not_a_second_one(monkeypatch):
    laid = ((9, 9), (90, 12), (88, 78), (8, 76))
    seen = []

    def search(image):
        seen.append(image)
        return an_outline(laid)(image)

    monkeypatch.setattr(m8_coverage, "find_card", search)

    assert detect_corners(NOT_AN_IMAGE) == laid
    assert seen == [NOT_AN_IMAGE]


def test_an_outline_that_is_not_a_quadrilateral_is_not_answered_as_one(monkeypatch):
    monkeypatch.setattr(
        m8_coverage,
        "find_card",
        an_outline(((10, 10), (90, 10), (90, 60), (10, 60)), method="rect"),
    )

    assert detect_corners(NOT_AN_IMAGE) == NO_CORNERS


def test_the_ordering_is_the_quality_checkers_own(monkeypatch):
    seen = []

    def order(points):
        seen.append(tuple(points))
        return [(2, 2), (1, 1), (3, 3), (4, 4)]

    monkeypatch.setattr(m8_coverage, "order_card_corners", order)

    unordered = [(4, 4), (3, 3), (1, 1), (2, 2)]
    assert order_corners(unordered) == ((2, 2), (1, 1), (3, 3), (4, 4))
    assert seen == [((4.0, 4.0), (3.0, 3.0), (1.0, 1.0), (2.0, 2.0))]


def test_a_corner_is_the_nearest_pixel_and_not_the_one_truncated_towards_zero():
    # The left-hand corners sit off the frame, which is where rounding and
    # truncating part company: int() alone answers -9, 70 and 68 for these.
    unordered = ((88.2, 70.7), (7.4, 68.6), (-9.6, 2.7), (90.4, 6.3))

    assert order_corners(unordered) == ((-10, 3), (90, 6), (88, 71), (7, 69))


@pytest.mark.parametrize(
    "points",
    [(), ((1, 1), (2, 2), (3, 3)), ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5))],
)
def test_ordering_refuses_anything_that_is_not_four_points(points):
    with pytest.raises(ValueError):
        order_corners(points)


def test_the_empty_answer_is_one_value_rather_than_a_fresh_one_each_call():
    assert detect_corners(blank_frame()) is NO_CORNERS
    assert corners.NO_CORNERS == ()
