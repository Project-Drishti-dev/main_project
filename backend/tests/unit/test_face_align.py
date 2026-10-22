"""13.14 -- five landmarks in, the canonical crop ArcFace reads out.

The claim under test is a round trip rather than a shape: a face-like figure is
drawn **already canonical**, turned into a larger frame by a known similarity,
and the alignment has to put it back where it started.  The band it has to land
in was measured, not chosen -- this fixture aligns to 1.33 grey levels of
0-255, while the same region left unaligned sits at 48.75, so the threshold
below has roughly a 35x margin over the fixture's own noise and still cannot be
passed by a transform that did nothing.

**A real face is never needed, and drawing one is the point.**  InsightFace is
not installed on this box and no face model is downloaded to test against
(``D84``), so the landmark positions are the fixture's own ground truth and the
test measures the geometry rather than a detector's accuracy.

**Two fixtures, because there are two frames.**  :func:`placed_face` is the
bare geometry, for the transform itself.  :func:`page_with_a_face` pastes that
same face into the committed template's own ``photo`` rectangle on a
page-sized frame, because a photo region only exists where the page is at
least as large as the rectangle naming it.
"""

import cv2
import numpy as np
import pytest

from app.pipeline.tier1 import face, face_align
from app.pipeline.tier1.face_align import (
    CANONICAL_LANDMARKS,
    CANONICAL_SIZE,
    LANDMARK_COUNT,
    LANDMARK_ORDER,
    NO_CROP,
    align_face,
    aligned_crops,
    photo_region,
    similarity_transform,
)
from app.pipeline.tier1.templates.loader import load_template

#: The committed layout, so ``photo_region`` is read against a real rectangle
#: rather than a stand-in this file invented, and its own page size is what the
#: page fixture is cut to.
TEMPLATE = load_template("passport_td3")
PHOTO_RECT = TEMPLATE.fields["photo"]

#: The page the face is pasted onto, as ``cv2`` counts a frame: width then
#: height, which is the reference size's own order.
PAGE_FRAME = TEMPLATE.reference_size

#: The transform the fixture applies on the way out, and the one alignment has
#: to recover: a scale, a turn about the origin, then a move.  Pinned as a
#: literal because these are the ground truth the landmarks are measured
#: against; :func:`test_the_fixture_is_actually_turned_and_scaled` holds them
#: to what the drawing really did.
PLACE_SCALE = 1.6
PLACE_DEGREES = 15.0

#: Where the bare geometry fixture is drawn, and where the page fixture puts the
#: same face -- inside the photo rectangle, which is what "in the photo region"
#: has to mean for the crop to be one a detector could ever have been handed.
PLACE_AT = (120.0, 80.0)
PLACE_FRAME = (460, 400)
PAGE_AT = (720.0, 100.0)

#: How close an aligned face must come back to the canonical drawing, in grey
#: levels of 0-255.  The fixture measures 1.33 and an unaligned crop of the
#: same region measures 48.75, so this band rejects a transform that did
#: nothing while tolerating the resampling a 1.6x turn cannot avoid.
ALIGNED_MEAN_DIFFERENCE = 8.0

#: The same comparison without aligning, which must stay far outside the band
#: above -- otherwise the test could pass on a fixture too small to notice.
UNALIGNED_MEAN_DIFFERENCE = 20.0


def canonical_face():
    """A face-like figure with its features drawn on the canonical landmarks.

    Ellipse for a head, a dot at each eye and the nose, a line for the mouth.
    Face-like is the honest word: nothing here was trained on or classified as
    anything, and the drawing only has to move rigidly for the transform to be
    checkable.
    """
    image = np.full((CANONICAL_SIZE, CANONICAL_SIZE, 3), 210, np.uint8)
    cv2.ellipse(image, (56, 68), (34, 44), 0, 0, 360, (150, 150, 170), -1)
    for eye in CANONICAL_LANDMARKS[:2]:
        cv2.circle(image, (int(eye[0]), int(eye[1])), 5, (40, 40, 40), -1)
    nose = CANONICAL_LANDMARKS[2]
    cv2.circle(image, (int(nose[0]), int(nose[1])), 4, (90, 90, 90), -1)
    left, right = CANONICAL_LANDMARKS[3], CANONICAL_LANDMARKS[4]
    cv2.line(image, (int(left[0]), int(left[1])), (int(right[0]), int(right[1])), (60, 60, 60), 3)
    return image


def draw_placed(frame_size, at):
    """The canonical face turned into ``frame_size`` at ``at``, and its landmarks.

    Returns the frame and the five positions in that frame -- what a detector
    handed the frame would report back.
    """
    radians = np.deg2rad(PLACE_DEGREES)
    rotation = np.array(
        [
            [np.cos(radians), -np.sin(radians)],
            [np.sin(radians), np.cos(radians)],
        ],
        np.float32,
    )
    linear = (rotation * PLACE_SCALE).astype(np.float32)
    forward = np.zeros((2, 3), np.float32)
    forward[:, :2] = linear
    forward[:, 2] = at

    frame = cv2.warpAffine(
        canonical_face(), forward, frame_size, flags=cv2.INTER_LINEAR
    )
    landmarks = (
        np.array(CANONICAL_LANDMARKS, np.float32) @ linear.T + np.array(at, np.float32)
    )
    return frame, landmarks


def placed_face():
    """The bare geometry fixture: a turned face on a plain frame, and its landmarks."""
    return draw_placed(PLACE_FRAME, PLACE_AT)


def page_with_a_face():
    """A page-sized frame holding the turned face inside the photo rectangle.

    Returns the page, and the same five landmarks **in the photo region's own
    coordinates**, which is what a detector handed that region would report and
    therefore what :func:`aligned_crops` aligns.
    """
    region_frame, region_landmarks = draw_placed(
        (PHOTO_RECT.width, PHOTO_RECT.height),
        (PAGE_AT[0] - PHOTO_RECT.x, PAGE_AT[1] - PHOTO_RECT.y),
    )
    page = np.full((PAGE_FRAME[1], PAGE_FRAME[0], 3), 255, np.uint8)
    page[
        PHOTO_RECT.y : PHOTO_RECT.y + PHOTO_RECT.height,
        PHOTO_RECT.x : PHOTO_RECT.x + PHOTO_RECT.width,
    ] = region_frame
    return page, region_landmarks


def a_detector_that_finds(*faces):
    """A detector answering ``faces`` whatever it is handed, and recording the frames."""

    class _Detector:
        def __init__(self):
            self.seen = []

        def detect(self, image):
            self.seen.append(image)
            return faces

    return _Detector()


def a_face_at(landmarks, confidence=0.9):
    """One :class:`~app.pipeline.tier1.face.DetectedFace` at ``landmarks``."""
    return face.DetectedFace(
        region=((0, 0), (1, 0), (1, 1), (0, 1)),
        confidence=confidence,
        landmarks=tuple((float(x), float(y)) for x, y in landmarks),
    )


def mean_difference(left, right):
    """The mean absolute grey-level difference between two frames, as a float."""
    return float(np.mean(np.abs(left.astype(np.int16) - right.astype(np.int16))))


# --- the task's own claim: landmarks in, the canonical crop out ---


def test_a_face_turned_in_a_frame_comes_back_to_the_canonical_crop():
    """13.14's claim, and the whole reason a similarity transform is fitted."""
    frame, landmarks = placed_face()
    aligned = align_face(frame, landmarks)

    assert mean_difference(aligned, canonical_face()) < ALIGNED_MEAN_DIFFERENCE


def test_the_same_region_left_unaligned_is_far_outside_that_band():
    """The control: without this the band above could pass on a weak fixture.

    Cut, not warped -- the identical pixels alignment was handed, resized
    rather than transformed.  If this ever falls inside the band the fixture
    has stopped being able to tell the two apart.
    """
    frame, _ = placed_face()
    x, y = (int(value) for value in PLACE_AT)
    unaligned = cv2.resize(
        frame[y : y + CANONICAL_SIZE, x : x + CANONICAL_SIZE],
        (CANONICAL_SIZE, CANONICAL_SIZE),
    )

    assert mean_difference(unaligned, canonical_face()) > UNALIGNED_MEAN_DIFFERENCE


def test_the_aligned_crop_is_the_square_the_recogniser_reads():
    frame, landmarks = placed_face()
    aligned = align_face(frame, landmarks)

    assert aligned.shape == (CANONICAL_SIZE, CANONICAL_SIZE, 3)
    assert aligned.dtype == np.uint8


def test_the_fixture_is_actually_turned_and_scaled():
    """The band is only worth reading if the fixture really moved.

    Held here rather than trusted: a fixture that silently stopped applying
    :data:`PLACE_DEGREES` would align perfectly and prove nothing.
    """
    frame, landmarks = placed_face()
    canonical = np.array(CANONICAL_LANDMARKS, np.float32)

    assert not np.allclose(landmarks, canonical)
    # A rotation and a scale, so the eye-to-eye span is PLACE_SCALE of the original.
    span_before = np.linalg.norm(canonical[1] - canonical[0])
    span_after = np.linalg.norm(landmarks[1] - landmarks[0])
    assert span_after == pytest.approx(span_before * PLACE_SCALE, rel=0.01)
    assert frame.shape[:2] == PLACE_FRAME[::-1]


def test_a_face_found_on_the_page_aligns_from_the_photo_region_it_was_found_in():
    """The task's "in the photo region", end to end and in the page's own space."""
    page, landmarks = page_with_a_face()
    detector = a_detector_that_finds(a_face_at(landmarks))

    crops = aligned_crops(page, TEMPLATE, detector)

    assert len(crops) == 1
    assert mean_difference(crops[0], canonical_face()) < ALIGNED_MEAN_DIFFERENCE


def test_the_detector_is_handed_the_photo_region_and_not_the_whole_page():
    page, landmarks = page_with_a_face()
    detector = a_detector_that_finds(a_face_at(landmarks))

    aligned_crops(page, TEMPLATE, detector)

    assert len(detector.seen) == 1
    assert detector.seen[0].shape == photo_region(page, TEMPLATE).shape
    assert np.array_equal(detector.seen[0], photo_region(page, TEMPLATE))


# --- the transform itself, and what it refuses ---


def test_the_transform_carries_the_landmarks_onto_the_canonical_ones():
    frame, landmarks = placed_face()
    matrix = similarity_transform(landmarks)

    moved = np.array(landmarks) @ matrix[:, :2].T + matrix[:, 2]
    assert np.allclose(moved, CANONICAL_LANDMARKS, atol=1e-3)


#: How far the mouth corners are dragged off the fitted pose, and in which
#: direction: the two are moved unequally, so the five points stop being the
#: image of any similarity at all.  Measured, not chosen -- these offsets put
#: 0.36 of shear on a *full* affine fit and leave a partial one at 0.0, which
#: is what makes the test below able to tell the two apart.
MOUTH_DRAG = ((-25.0, 14.0), (22.0, -12.0))


def shear_of(matrix):
    """How far a matrix is from being a similarity: 0.0 when it is one."""
    return max(abs(matrix[1, 0] + matrix[0, 1]), abs(matrix[1, 1] - matrix[0, 0]))


def test_the_transform_carries_rotation_and_one_uniform_scale_and_no_shear():
    """Why partial and not full affine: a similarity keeps the two axes equal."""
    frame, landmarks = placed_face()
    matrix = similarity_transform(landmarks)

    assert shear_of(matrix) == pytest.approx(0.0, abs=1e-6)


def test_landmarks_that_are_not_the_image_of_any_similarity_still_align_without_shear():
    """The claim above, on the landmarks that could have caught a full affine.

    Five points that *are* a similarity determine it uniquely, so a full affine
    and a partial one fit them identically and the test cannot tell which ran.
    Dragging the mouth corners off the pose breaks that: a full affine would
    answer with a shear, and this asserts the fit still has none.
    """
    frame, landmarks = placed_face()
    dragged = np.array(landmarks, np.float64).copy()
    dragged[3] += MOUTH_DRAG[0]
    dragged[4] += MOUTH_DRAG[1]

    matrix = similarity_transform(dragged)

    assert shear_of(matrix) == pytest.approx(0.0, abs=1e-6)


def test_a_full_affine_would_have_sheared_those_landmarks():
    """The control for the test above: this fixture can tell the two apart.

    Without it, a module that fitted a full affine would satisfy both tests
    above, because five points that are a similarity fit either way.
    """
    _, landmarks = placed_face()
    dragged = np.array(landmarks, np.float64).copy()
    dragged[3] += MOUTH_DRAG[0]
    dragged[4] += MOUTH_DRAG[1]

    full = cv2.estimateAffine2D(dragged.astype(np.float32), np.array(CANONICAL_LANDMARKS, np.float32))[0]

    assert shear_of(full) > 0.1


def test_landmarks_stacked_on_one_point_align_to_nothing_rather_than_to_black():
    """``D99``'s rule on geometry: degenerate landmarks are an absence."""
    frame, _ = placed_face()

    assert align_face(frame, [(100.0, 100.0)] * LANDMARK_COUNT) is NO_CROP


def test_landmarks_on_one_line_align_to_nothing_rather_than_to_a_stretched_face():
    frame, _ = placed_face()

    assert align_face(frame, [(10.0 + i, 10.0 + i) for i in range(LANDMARK_COUNT)]) is NO_CROP


@pytest.mark.parametrize(
    "landmarks",
    [
        pytest.param(((1.0, 2.0), (3.0, 4.0)), id="too_few"),
        pytest.param(tuple((float(i), float(i * i)) for i in range(6)), id="too_many"),
        pytest.param(((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0), (9.0,)), id="ragged"),
        pytest.param(
            ((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0), (float("nan"), 9.0)),
            id="not_finite",
        ),
    ],
)
def test_landmarks_that_are_not_five_finite_points_are_refused(landmarks):
    """A wiring mistake raises rather than defaulting, on ``D98``'s reasoning.

    Five points that are not five points would otherwise be quietly padded or
    trimmed into a transform that looked measured and was not.
    """
    frame, _ = placed_face()

    with pytest.raises(ValueError):
        align_face(frame, landmarks)


# --- the photo region, which is where a detector is pointed ---


def test_the_photo_region_is_the_template_own_photo_field_cut_out_of_the_frame():
    page, _ = page_with_a_face()

    region = photo_region(page, TEMPLATE)

    assert region.shape[:2] == (PHOTO_RECT.height, PHOTO_RECT.width)
    assert np.array_equal(
        region,
        page[
            PHOTO_RECT.y : PHOTO_RECT.y + PHOTO_RECT.height,
            PHOTO_RECT.x : PHOTO_RECT.x + PHOTO_RECT.width,
        ],
    )


def test_a_template_placing_no_photo_field_has_no_region_rather_than_an_empty_one():
    """An absent region is not a searched-and-empty one, on ``D99``'s rule."""
    page, _ = page_with_a_face()

    class _NoPhoto:
        fields = {"name": object()}

    assert photo_region(page, _NoPhoto()) is NO_CROP


def test_a_page_too_small_to_hold_the_photo_rectangle_has_no_region_rather_than_a_short_one():
    """A slice past the frame edge returns a shorter frame, which is not the region.

    Clipping would hand a detector a partial photo and report whatever it found
    there as though the whole portrait had been searched.
    """
    frame, _ = placed_face()

    assert photo_region(frame, TEMPLATE) is NO_CROP


def test_a_page_with_no_face_yields_no_crops_rather_than_a_refusal():
    page, _ = page_with_a_face()

    assert aligned_crops(page, TEMPLATE, a_detector_that_finds()) == ()


def test_a_template_with_no_photo_field_yields_no_crops_and_asks_the_detector_nothing():
    """A region that does not exist cannot be searched, so nothing is asked."""
    page, _ = page_with_a_face()
    detector = a_detector_that_finds()

    class _NoPhoto:
        fields = {"name": object()}

    assert aligned_crops(page, _NoPhoto(), detector) == ()
    assert detector.seen == []


def test_a_face_whose_landmarks_are_degenerate_is_dropped_rather_than_added_as_black():
    """One unusable face does not stop a good one being reported alongside it."""
    page, landmarks = page_with_a_face()
    detector = a_detector_that_finds(
        a_face_at([(9.0, 9.0)] * LANDMARK_COUNT, confidence=0.95),
        a_face_at(landmarks, confidence=0.8),
    )

    crops = aligned_crops(page, TEMPLATE, detector)

    assert len(crops) == 1
    assert mean_difference(crops[0], canonical_face()) < ALIGNED_MEAN_DIFFERENCE


# --- the constants, held to what this project relies on ---


def test_the_canonical_crop_is_the_square_the_embedder_reads():
    """13.13 resizes to 112 and 13.14 produces 112; one test holds them together."""
    from app.pipeline.tier1.insightface_embedder import MODEL_INPUT_SIZE

    assert CANONICAL_SIZE == MODEL_INPUT_SIZE


def test_there_are_five_landmarks_and_five_names_for_them():
    assert len(LANDMARK_ORDER) == LANDMARK_COUNT
    assert len(set(LANDMARK_ORDER)) == LANDMARK_COUNT


def test_the_canonical_landmarks_are_five_points_inside_the_canonical_square():
    points = np.array(CANONICAL_LANDMARKS)

    assert points.shape == (LANDMARK_COUNT, 2)
    assert ((points >= 0) & (points < CANONICAL_SIZE)).all()


def test_every_name_in_all_exists_in_the_module():
    for name in face_align.__all__:
        assert hasattr(face_align, name)
