"""Warp a capture into template space: the frame a template's rectangles sit on.

:func:`warp_to_template` takes the corners :mod:`app.pipeline.tier1.corners`
found on a capture and answers that document on the template's own reference
frame.  :func:`homography` is that matrix, exposed so a box measured in
template space can be carried back to capture pixels for an evidence region.
Template space is the reference frame's own four corners, clockwise from the
top left.  A capture holding no page is answered :data:`NO_WARP`.
"""

import cv2
import numpy as np

from app.pipeline.tier1.corners import CORNER_COUNT, NO_CORNERS

__all__ = [
    "NO_WARP",
    "homography",
    "template_corners",
    "warp_to_template",
]

#: What both answers are when there is no page to straighten: a frame that holds
#: no document, and four points enclosing no area.  ``None``, not an empty
#: frame, because an image of nothing would be a picture and not a refusal.
NO_WARP = None

#: The filter the warp resamples with, named so a caller comparing a warped
#: capture with the frame it was photographed from reads one filter rather than
#: whichever ``cv2`` defaults to this month.
INTERPOLATION = cv2.INTER_LINEAR


def template_corners(template):
    """The template's reference frame as four corners, clockwise from the top left.

    ``(0, 0)`` through ``(width, height)``, the frame every rectangle in
    ``template`` was measured on.  Never raises: a loaded template has one.
    """
    width, height = template.reference_size
    return ((0, 0), (width, 0), (width, height), (0, height))


def homography(corners, template):
    """The 3x3 matrix taking ``corners`` onto the template's corners, or :data:`NO_WARP`.

    ``corners`` is four points in the clockwise-from-the-top-left order
    :func:`~app.pipeline.tier1.corners.order_corners` writes.  Raises
    :exc:`ValueError` for any other count, and answers :data:`NO_WARP` for four
    points enclosing no area, which is not a page.
    """
    points = tuple(corners)
    if len(points) != CORNER_COUNT:
        raise ValueError(f"a document has {CORNER_COUNT} corners, not {len(points)}")

    found = np.array(points, np.float32).reshape(CORNER_COUNT, 2)
    if cv2.contourArea(found) <= 0.0:
        return NO_WARP
    return cv2.getPerspectiveTransform(found, np.array(template_corners(template), np.float32))


def warp_to_template(image, template, corners):
    """``image``'s document on the template's frame, or :data:`NO_WARP`.

    ``image`` is the BGR frame
    :func:`~app.pipeline.tier1.corners.detect_corners` was given and ``corners``
    what it answered.  Answers :data:`NO_WARP` on no corners and on a
    quadrilateral enclosing no area; otherwise a ``uint8`` BGR frame of the
    template's ``reference_size``.
    """
    if len(tuple(corners)) == len(NO_CORNERS):
        return NO_WARP

    matrix = homography(corners, template)
    if matrix is NO_WARP:
        return NO_WARP

    width, height = template.reference_size
    return cv2.warpPerspective(image, matrix, (width, height), flags=INTERPOLATION)
