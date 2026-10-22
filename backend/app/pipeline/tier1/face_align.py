"""One face turned into the crop ArcFace reads: landmarks in, square out.

:func:`align_face` is 13.14 in full -- five landmarks and the frame they were
found in come in, and the canonical square ArcFace was trained on comes out.
The transform between the two is a *similarity* (rotation, one uniform scale,
translation) rather than a full affine, so a face photographed at another angle
or another distance still lands on the pose the model expects, while the shear
a full affine would fit is not invited to distort it.

**Where the transform cannot be estimated the answer is ``None``, never a zero
crop.**  Landmarks stacked on one point, or on one line, describe no face, and
a 112-square of black would read like a face measured and found empty -- the
answer ``D99`` refuses everywhere else in this project.

:func:`photo_region` is where a detector is pointed: the template's own
``photo`` field cut out of the aligned frame, so a face is looked for where the
document says the face is rather than anywhere on the page.  It answers
``None`` for a template that places no photo field, which is the same absence
:func:`align_face` reports and not an empty crop.
"""

import cv2
import numpy as np

from app.pipeline.tier1.templates.loader import Template

__all__ = [
    "CANONICAL_LANDMARKS",
    "CANONICAL_SIZE",
    "LANDMARK_COUNT",
    "LANDMARK_ORDER",
    "NO_CROP",
    "PHOTO_FIELD",
    "align_face",
    "aligned_crops",
    "photo_region",
    "similarity_transform",
]

#: The template field a face is looked for in, and the only one this module reads.
PHOTO_FIELD = "photo"

#: The square ArcFace reads, and so the square this module produces.
CANONICAL_SIZE = 112

#: How many landmarks a face is described by: two eyes, a nose, two mouth corners.
LANDMARK_COUNT = 5

#: Which of the five is which, in the order every landmark tuple in this project
#: is written.  Named here rather than left to a reader, because a similarity
#: transform fitted to the same five points in a different order is a different
#: transform, and nothing downstream would say so.
LANDMARK_ORDER = ("left_eye", "right_eye", "nose", "left_mouth", "right_mouth")

#: Where those five points sit in the canonical crop -- ArcFace's own reference
#: positions for a 112-square, which are the model's input contract rather than
#: a measurement taken here.  Fitting to these is what "aligned" means.
CANONICAL_LANDMARKS = (
    (38.2946, 51.6963),
    (73.5318, 51.5014),
    (56.0252, 71.7366),
    (41.5493, 92.3655),
    (70.7299, 92.2041),
)

#: What both answers are where there is nothing to align to or nothing found.
NO_CROP = None


def _points(landmarks, count=LANDMARK_COUNT):
    """``landmarks`` as a ``(count, 2)`` float array, or :data:`NO_CROP` if it cannot be.

    A wrong number of points is a wiring mistake rather than a measurement of
    nothing, so it raises; points that are not finite are refused the same way,
    because a ``nan`` silently poisons the whole fitted transform.
    """
    points = np.asarray(tuple(landmarks), dtype=np.float64)
    if points.shape != (count, 2):
        raise ValueError(
            f"a face is {count} landmarks of (x, y), not {points.shape}."
        )
    if not np.isfinite(points).all():
        raise ValueError("landmarks must be finite numbers.")
    return points


def photo_region(frame, template: Template):
    """The template's own ``photo`` field cut out of ``frame``, or :data:`NO_CROP`.

    ``frame`` is the aligned page :mod:`app.pipeline.tier1.align` produced and
    ``template`` the layout it was aligned onto, so the rectangle is read in
    the same space it was written in.  A template placing no ``photo`` field
    answers :data:`NO_CROP`, and so does a frame too small to hold the rectangle
    it names: there is no region a face could have been in, which is not the
    same as a region that was searched and found empty.  The second case is
    answered rather than clipped, because a slice past the edge of a frame
    returns a shorter one -- a partial photo that would still be searched and
    reported as though it were the whole.
    """
    rect = template.fields.get(PHOTO_FIELD)
    if rect is None:
        return NO_CROP
    height, width = frame.shape[:2]
    if rect.x < 0 or rect.y < 0 or rect.x + rect.width > width or rect.y + rect.height > height:
        return NO_CROP
    return frame[rect.y : rect.y + rect.height, rect.x : rect.x + rect.width]


def similarity_transform(source, target=CANONICAL_LANDMARKS):
    """The 2x3 matrix carrying ``source`` onto ``target``, or :data:`NO_CROP`.

    The fit is partial rather than full: rotation, one uniform scale and
    translation, with no shear term.  Degenerate input -- every landmark on one
    point, or all five on one line -- encloses no area and cannot carry a
    similarity, and answers :data:`NO_CROP` rather than a matrix OpenCV fitted
    anyway and marked half its points outliers.
    """
    found = _points(source)
    wanted = _points(target)
    if cv2.contourArea(found.astype(np.float32)) <= 0.0:
        return NO_CROP
    matrix = cv2.estimateAffinePartial2D(found.astype(np.float32), wanted.astype(np.float32))[0]
    if matrix is None:
        return NO_CROP
    return matrix


def align_face(image, landmarks):
    """``image``'s face on the canonical crop, or :data:`NO_CROP`.

    ``landmarks`` are in the frame ``image`` was read from.  The warp is
    ``INTER_LINEAR``, named rather than left to a default that changes, so a
    caller comparing two aligned crops reads one filter rather than whichever
    ``cv2`` defaults to this month.
    """
    matrix = similarity_transform(landmarks)
    if matrix is NO_CROP:
        return NO_CROP
    return cv2.warpAffine(
        image, matrix, (CANONICAL_SIZE, CANONICAL_SIZE), flags=cv2.INTER_LINEAR
    )


def aligned_crops(frame, template: Template, detector):
    """Every face ``detector`` finds in the photo region, each aligned: a tuple.

    The tuple is empty for a page holding no face and for a template placing no
    photo field alike -- ``D101``'s ``()`` for "a measurement of nothing" --
    and both answer the same because a caller asking "what faces did this page's
    photo show" cannot tell a portrait-free page from a layout with no portrait.
    """
    region = photo_region(frame, template)
    if region is NO_CROP:
        return ()
    return tuple(
        crop
        for crop in (align_face(region, face.landmarks) for face in detector.detect(region))
        if crop is not NO_CROP
    )
