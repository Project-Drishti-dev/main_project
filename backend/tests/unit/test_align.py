"""13.7 -- a capture is warped into template space, and lands on the template.

The claim is a comparison against the committed reference itself: the shipped
template's own page, laid down tilted on a dark surface and photographed, comes
back within a few grey levels of the file it was printed from.

**The page under test is the committed template.**  Warping the printed specimen
instead would measure the fixture against itself; laying the template down and
photographing it puts the one artefact 13.9 will measure against into the
capture, so "close to the template" is a comparison with that file and not with
a second drawing of it.

**The corners come from the detector, not from the layout.**  The page is laid
at :data:`LAID_AT` and photographed; the homography is built from what
:func:`~app.pipeline.tier1.corners.detect_corners` answers on that capture.

**The limits are contracts, and the numbers behind them are in ``D97``.**  They
reject a warp that leaves the page where it was, one built off a reversed
corner order, and one built off corners a few pixels off the page's own.
"""

import importlib.resources
import math

import numpy as np
import pytest
from PIL import Image

from app.pipeline.tier1 import align
from app.pipeline.tier1.corners import NO_CORNERS, detect_corners
from app.pipeline.tier1.templates import loader
from app.pipeline.tier1.templates.loader import load_template
from tests.fixtures import document_images

#: The committed layout, read through its own loader so the frame these tests
#: measure against is the one the pipeline measures against.
TEMPLATE = load_template("passport_td3")

#: The capture the template's page is photographed into, ``(width, height)``.
#: Large enough that a page tilted at :data:`TILTED_BY_DEGREES` clears the
#: frame on every side, which a contour clipped by the edge is not.
FRAME = (1300, 1000)

#: How far the page is turned, in degrees.  Not zero: a page laid square would
#: be answered correctly by a warp that never turned anything back.
TILTED_BY_DEGREES = 7.0

#: Where the page's own four corners were put, clockwise from the top left.  The
#: page rectangle rotated about its own centre and moved by
#: :data:`LAYED_AT_OFFSET`; pinned as a literal because these are the ground
#: truth the corners are measured against, and held to that rotation by
#: :func:`test_the_page_is_actually_tilted`.
LAYED_AT_OFFSET = (150, 90)
LAID_AT = ((196, 32), (1189, 154), (1104, 848), (111, 726))

#: The page rectangle's own centre, which :data:`LAID_AT` is turned about.
PAGE_CENTRE = (500, 350)

#: The largest mean difference from the template a warped capture may carry, in
#: grey levels of 0-255.  A capture left where it was, and one straightened off
#: a reversed corner order, are both an order of magnitude outside it.
CLOSE_MEAN_DIFFERENCE = 8

#: How near "near" is, in grey levels, and how much of the frame must be
#: within it.  Together these catch a warp that is dark rather than misaligned.
CLOSE_WITHIN = 40
CLOSE_FRACTION = 0.96

#: How far a found corner may sit from where the page was laid, in pixels.
#: This detector's own outline simplification and its downscaling set this, not
#: the fixture, and they are well inside the paper's edge.
CORNER_TOLERANCE_PX = 8


def rotated_quad(degrees, centre, offset):
    """The page rectangle turned ``degrees`` clockwise about ``centre``, then moved.

    ``(0, 0)`` through the page's own ``(width, height)``, in the clockwise-from-
    the-top-left order every corner in this repository is written in.
    """
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    cx, cy = centre
    width, height = TEMPLATE.reference_size
    return tuple(
        (
            int(round(cx + (x - cx) * cos - (y - cy) * sin + offset[0])),
            int(round(cy + (x - cx) * sin + (y - cy) * cos + offset[1])),
        )
        for x, y in ((0, 0), (width, 0), (width, height), (0, height))
    )


def reference_image():
    """The committed reference as the BGR frame :mod:`align` warps onto.

    Read as the package resource :mod:`loader` reads it as, so this follows the
    template file rather than a path written beside the test.
    """
    resource = importlib.resources.files(loader.TEMPLATES_PACKAGE).joinpath(
        TEMPLATE.reference_image
    )
    with resource.open("rb") as stream:
        with Image.open(stream) as image:
            return np.ascontiguousarray(np.array(image.convert("RGB"))[:, :, ::-1])


def capture():
    """The committed page laid at :data:`LAID_AT` and photographed on a dark frame."""
    return document_images.lay(
        reference_image(), TEMPLATE.reference_size, LAID_AT, FRAME
    )


def blank_frame():
    """A capture of :data:`FRAME` holding nothing a detector can call a page."""
    return np.full((FRAME[1], FRAME[0], 3), 128, np.uint8)


def warped():
    """The photographed page detected, then warped onto the template's frame."""
    photo = capture()
    return align.warp_to_template(photo, TEMPLATE, detect_corners(photo))


def project(matrix, point):
    """Where ``matrix`` -- the homography -- carries ``point``, in its own units."""
    x, y = float(point[0]), float(point[1])
    scale = matrix[2, 0] * x + matrix[2, 1] * y + matrix[2, 2]
    return (
        (matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2]) / scale,
        (matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2]) / scale,
    )


def test_the_page_is_actually_tilted():
    assert LAID_AT == rotated_quad(
        TILTED_BY_DEGREES, PAGE_CENTRE, LAYED_AT_OFFSET
    )


def test_template_space_is_the_reference_frames_own_four_corners():
    width, height = TEMPLATE.reference_size

    assert align.template_corners(TEMPLATE) == (
        (0, 0), (width, 0), (width, height), (0, height)
    )


def test_the_template_corners_are_clockwise_from_the_top_left():
    found = align.template_corners(TEMPLATE)

    by_sum = sorted(found, key=lambda corner: corner[0] + corner[1])
    by_difference = sorted(found, key=lambda corner: corner[1] - corner[0])
    assert found == (by_sum[0], by_difference[0], by_sum[-1], by_difference[-1])


def test_the_homography_carries_the_detected_corners_onto_the_templates_corners():
    photo = capture()
    found = detect_corners(photo)

    matrix = align.homography(found, TEMPLATE)

    carried = [project(matrix, corner) for corner in found]
    for got, want in zip(carried, align.template_corners(TEMPLATE)):
        assert abs(got[0] - want[0]) < 1e-3 and abs(got[1] - want[1]) < 1e-3, (
            f"{found} is carried to {carried}, not onto {align.template_corners(TEMPLATE)}"
        )


def test_the_warped_document_is_the_size_of_the_templates_own_frame():
    width, height = TEMPLATE.reference_size

    assert warped().shape == (height, width, 3)


def test_a_rotated_document_is_warped_close_to_the_template():
    difference = np.abs(warped().astype(int) - reference_image().astype(int))

    assert difference.mean() < CLOSE_MEAN_DIFFERENCE, (
        f"the warped page averages {difference.mean():.2f} grey levels from the template"
    )
    assert (difference.max(axis=2) <= CLOSE_WITHIN).mean() > CLOSE_FRACTION, (
        "too much of the warped page is nowhere near the template"
    )


def test_a_frame_holding_no_document_is_answered_and_not_raised():
    found = detect_corners(blank_frame())

    assert found == NO_CORNERS
    assert align.warp_to_template(blank_frame(), TEMPLATE, found) is align.NO_WARP


def test_a_quadrilateral_enclosing_no_area_is_not_straightened():
    # Four points in a line are four corners and no page, which is what a
    # detector hands back when its outline collapses.
    collinear = ((0, 0), (1, 1), (2, 2), (3, 3))

    assert align.homography(collinear, TEMPLATE) is align.NO_WARP
    assert align.warp_to_template(blank_frame(), TEMPLATE, collinear) is align.NO_WARP


@pytest.mark.parametrize(
    "points",
    [(), ((1, 1), (2, 2), (3, 3)), ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5))],
)
def test_the_homography_refuses_anything_that_is_not_four_points(points):
    with pytest.raises(ValueError) as refused:
        align.homography(points, TEMPLATE)

    # The count is named, so a caller who passed three points is told three
    # rather than being handed a reshape error from underneath.
    assert f"not {len(points)}" in str(refused.value)


def test_the_empty_answer_is_the_one_value_rather_than_a_fresh_one_each_call():
    assert align.NO_WARP is None
    assert align.warp_to_template(blank_frame(), TEMPLATE, NO_CORNERS) is align.NO_WARP
