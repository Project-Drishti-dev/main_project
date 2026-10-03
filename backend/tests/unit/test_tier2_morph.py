"""15.10 -- a morph classifier is an interface, and its stand-in says it is one.

The claim pinned first is the verification the task names: the record this
module answers carries ``is_stub`` and the version string ``heuristic-v0``, so
nothing built on the cues can be read as a trained model's work.  The rest
holds that the label belongs to the classifier rather than to the module, that
a region with no portrait is refused rather than scored, and that both cue lines
sit in a gap the probe measured rather than where a textbook would put them --
D122.

Every figure here came from the shipped functions, and the fixture resizes the
artwork it already has rather than redrawing it, so no number asserts something
a probe never produced.
"""

import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import morph

SCREENING_ID = uuid.UUID("7c2b1d4e-5a6f-4b7c-8d9e-0f1a2b3c4d5e")
FACE_SIDE = 200
PAGE_W, PAGE_H = 900, 700
PHOTO_AT = (640, 380)


def _head(side=FACE_SIDE, oval=(52, 66), dx=0, eye=20, seed=7, noise=9):
    """Return one synthetic head at ``side`` pixels square.

    Drawn here rather than committed, so a test that needs a portrait at
    another size rescales this one instead of authoring a second face that
    would differ in more ways than the one under test.
    """
    image = np.full((side, side), 220, np.uint8)
    cv2.ellipse(image, (side // 2 + dx, side // 2), oval, 0, 0, 360, 150, -1)
    cv2.circle(image, (side // 2 + dx - eye, side // 2 - 20), 9, 40, -1)
    cv2.circle(image, (side // 2 + dx + eye, side // 2 - 20), 9, 40, -1)
    cv2.ellipse(image, (side // 2 + dx, side // 2 + 40), (26, 10), 0, 0, 180, 60, 2)
    rng = np.random.default_rng(seed)
    noise_added = rng.normal(0, noise, image.shape)
    return cv2.GaussianBlur(
        np.clip(image.astype(np.int16) + noise_added, 0, 255).astype(np.uint8), (3, 3), 0
    )


def _blend(left, right):
    """Return the mean of two portraits, which is what a morph is."""
    return np.clip(
        (left.astype(np.float64) + right.astype(np.float64)) / 2, 0, 255
    ).astype(np.uint8)


ONE = _head()
OTHER = _head(oval=(44, 62), dx=10, eye=26)
MORPHED = _blend(ONE, OTHER)


def _page(photo=None):
    """Return a 900x700 text page carrying ``photo`` at :data:`PHOTO_AT`."""
    page = np.full((PAGE_H, PAGE_W), 236, np.uint8)
    for row in range(40, 300, 16):
        for column in range(40, 560, 18):
            cv2.line(page, (column, row), (column + 12, row), 70, 2, cv2.LINE_AA)
    if photo is not None:
        x, y = PHOTO_AT
        page[y : y + photo.shape[0], x : x + photo.shape[1]] = photo
    return page


def _context(image):
    """Return a context carrying the working frame the seam hands a module."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _photo_of(context):
    """Cut the portrait out of the page, standing in for a real locator."""
    x, y = PHOTO_AT
    return context.image[y : y + FACE_SIDE, x : x + FACE_SIDE]


def _at_photo(classifier=None):
    """A module pointed at the portrait rather than at the whole page."""
    return morph.MorphModule(classifier=classifier, region_of=_photo_of)


class _Labelled(morph.MorphClassifier):
    """A classifier reporting itself as a real model, so the swap can be read."""

    model_version = "arcface-morph-v3"
    is_stub = False

    def classify(self, region):
        return morph.morph_score(region)


# --- the task's own verification -----------------------------------------


def test_the_record_says_a_heuristic_produced_it():
    """The task's own verification: ``is_stub`` and ``heuristic-v0`` on the record."""
    result = _at_photo().run(_context(_page(MORPHED)))

    assert result.is_stub is True
    assert result.model_version == "heuristic-v0"


def test_the_module_answers_under_the_name_its_flag_is_traced_to():
    """``TAMPER_MORPH_SUSPECTED`` carries the weight; the record names the module."""
    assert morph.MODULE_NAME == "tamper_morph"
    assert morph.MODEL_VERSION == "heuristic-v0"
    assert _at_photo().run(_context(_page(MORPHED))).module == "tamper_morph"


# --- the label belongs to the classifier, not to the module --------------


def test_the_stand_in_labelled_itself_cannot_answer_otherwise():
    """Both attributes are fixed on the stand-in, so a module cannot relabel it."""
    stand_in = morph.HeuristicMorphClassifier()

    assert stand_in.is_stub is True
    assert stand_in.model_version == "heuristic-v0"


def test_the_record_carries_the_classifier_label_not_the_module_one():
    """A real classifier's own version and stub flag are what reach the record."""
    result = _at_photo(classifier=_Labelled()).run(_context(_page(MORPHED)))

    assert result.is_stub is False
    assert result.model_version == "arcface-morph-v3"


def test_a_module_is_refused_a_classifier_that_cannot_say_what_it_is():
    """Wired wrongly fails at construction, not on the first document."""
    with pytest.raises(morph.MorphError):
        morph.MorphModule(classifier=object())


def test_a_classifier_without_run_cannot_be_built():
    """A subclass that never wrote ``classify`` fails the same way."""
    with pytest.raises(TypeError):
        type("_NoClassify", (morph.MorphClassifier,), {"model_version": "x", "is_stub": True})()


# --- the cues, and the lines they are read against ----------------------


def test_a_clean_portrait_reads_near_nothing_and_a_blend_reads_suspect():
    """The whole claim: averaging two faces moves both cues, and the gap holds."""
    clean = morph.morph_score(ONE)
    blended = morph.morph_score(MORPHED)

    assert clean.score == 0.0
    assert clean.suspect is False
    assert blended.score > morph.SUSPECT_LEVEL
    assert blended.suspect is True


def test_the_two_cues_move_in_opposite_directions_on_a_blend():
    """A blend loses detail and doubles the outline, which is why both are read."""
    clean = morph.morph_score(ONE)
    blended = morph.morph_score(MORPHED)

    assert clean.frequency == 0.0 and clean.boundary == 0.0
    assert blended.frequency > 0.0 and blended.boundary > 0.0


def test_the_score_is_the_mean_of_the_two_cues():
    """Averaged, not maxed: ELA's rule that one cue must not speak for both."""
    verdict = morph.morph_score(MORPHED)

    assert verdict.score == pytest.approx((verdict.frequency + verdict.boundary) / 2)


def test_the_frequency_line_sits_in_a_gap_the_probe_measured():
    """Every clean portrait leaves it 0 and every blend pushes past it.

    This is the cue that carries the separation on its own, and the one the
    canonical grid rescued: read raw, its share moved with capture size.
    """
    for oval, dx, eye, seed, noise in (
        ((46, 58), 3, 17, 11, 5),
        ((56, 72), -6, 28, 99, 12),
        ((44, 62), 8, 22, 41, 7),
        ((52, 64), -2, 19, 63, 15),
        ((50, 70), 5, 25, 77, 6),
    ):
        for side in (140, 180, 220):
            clean = _head(side, oval, dx, eye, seed, noise)
            other = _head(side, (oval[0] - 7, oval[1] - 5), dx + 12, eye + 5, seed + 1000, noise)

            assert morph.frequency_cue(clean) == 0.0
            assert morph.frequency_cue(_blend(clean, other)) > 0.0


def test_the_boundary_line_does_not_separate_on_its_own_and_the_mean_saves_it():
    """A clean portrait crosses :data:`BOUNDARY_LEVEL`; the score still holds.

    This is the honest limit of the second cue and it is why the score is a
    mean rather than a maximum: one clean portrait of the twenty measured
    reached a shape factor of 1.194, past the 1.162 line, which alone would
    have been a finding against a genuine traveller.  D122 records it.
    """
    over_line = []
    for oval, dx, eye, seed, noise in (
        ((46, 58), 3, 17, 11, 5),
        ((56, 72), -6, 28, 99, 12),
        ((44, 62), 8, 22, 41, 7),
        ((52, 64), -2, 19, 63, 15),
        ((50, 70), 5, 25, 77, 6),
    ):
        for side in (140, 180, 220):
            clean = _head(side, oval, dx, eye, seed, noise)
            verdict = morph.morph_score(clean)
            if morph.boundary_cue(clean) > 0.0:
                over_line.append(verdict.score)

    assert over_line, "no clean portrait crossed the boundary line, so this pins nothing"
    assert max(over_line) < morph.SUSPECT_LEVEL


def test_no_clean_portrait_reaches_the_line_and_no_blend_falls_below_it():
    """The suspect line sits in the gap the same sweep leaves, held both ways."""
    clean_scores, blend_scores = [], []
    for oval, dx, eye, seed, noise in (
        ((46, 58), 3, 17, 11, 5),
        ((56, 72), -6, 28, 99, 12),
    ):
        for side in (140, 180, 220):
            clean = _head(side, oval, dx, eye, seed, noise)
            other = _head(side, (oval[0] - 7, oval[1] - 5), dx + 12, eye + 5, seed + 1000, noise)
            blend = _blend(clean, other)
            clean_scores.append(morph.morph_score(clean).score)
            blend_scores.append(morph.morph_score(_jpeg(blend, 80)).score)

    assert max(clean_scores) < morph.SUSPECT_LEVEL
    assert min(blend_scores) > morph.SUSPECT_LEVEL


def test_jpeg_quality_does_not_move_either_line():
    """A real capture is encoded, so the gap has to survive being re-encoded."""
    for quality in (95, 75, 60):
        assert morph.morph_score(_jpeg(ONE, quality)).suspect is False
        assert morph.morph_score(_jpeg(MORPHED, quality)).suspect is True


def _jpeg(region, quality):
    """Return ``region`` through a JPEG round trip at ``quality``."""
    encoded, buffer = cv2.imencode(
        ".jpg", region, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    assert encoded, "the test's own JPEG encoder refused its region"
    return cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)


# --- a portrait photographed at another size reads the same -------------
# Rescaled, never redrawn: redrawing changes relative stroke widths, so a
# method that could not survive a redraw would look stable here for the wrong
# reason.


def test_the_cue_survives_the_portrait_being_photographed_at_another_size():
    """Canonicalisation is why: read raw, the share moves with capture size."""
    for side in (80, 120, 240):
        rescaled = cv2.resize(ONE, (side, side), interpolation=cv2.INTER_AREA)
        assert morph.morph_score(rescaled).suspect is False

        rescaled_blend = cv2.resize(MORPHED, (side, side), interpolation=cv2.INTER_AREA)
        assert morph.morph_score(rescaled_blend).suspect is True


def test_the_canonical_grid_is_what_makes_it_size_independent():
    """Un-canonicalised, the same artwork's share moves across four sizes."""
    shares = set()
    for side in (80, 120, 160, 240):
        rescaled = cv2.resize(ONE, (side, side), interpolation=cv2.INTER_AREA)
        shares.add(round(morph.frequency_cue(rescaled), 3))

    assert len(shares) > 1


# --- an absence is refused, never scored --------------------------------


def test_a_region_holding_no_portrait_is_refused_rather_than_scored():
    """Flat paper has no face to have been morphed, so there is nothing to read."""
    with pytest.raises(morph.MorphError):
        morph.morph_score(np.full((FACE_SIDE, FACE_SIDE), 200, np.uint8))


def test_a_region_too_small_to_read_on_the_grid_is_refused():
    """A crop smaller than the canonical grid would be upsampled, not measured."""
    with pytest.raises(morph.MorphError):
        morph.morph_score(np.zeros((10, 10), np.uint8))


def test_the_absence_is_a_named_answer_rather_than_a_zero():
    """``NO_FACE`` exists so a caller can test for it without inventing one."""
    assert morph.NO_FACE is None


# --- the record an officer reads ---------------------------------------


def test_a_record_below_the_line_says_nothing_found():
    """D121 one level up: a score of 0.00 is never worded as a suspicion."""
    detail = _at_photo().run(_context(_page(ONE))).detail

    assert "nothing found" in detail
    assert "a suspected face morph" not in detail


def test_a_record_above_the_line_says_a_suspected_morph():
    """The same sentence must name a finding when there is one."""
    detail = _at_photo().run(_context(_page(MORPHED))).detail

    assert "a suspected face morph" in detail


def test_every_record_says_the_cues_are_not_faces():
    """The known limit is in the sentence, not only in this test file."""
    detail = _at_photo().run(_context(_page(ONE))).detail

    assert "rather than faces" in detail


def test_a_record_reports_no_heatmap_and_no_region():
    """One number for the whole region, so there is no map and no box to draw."""
    result = _at_photo().run(_context(_page(MORPHED)))

    assert result.heatmap == ()
    assert result.regions == ()


# --- which region was measured ----------------------------------------


def test_the_module_measures_the_whole_frame_when_nothing_else_is_named():
    """The seam hands over a frame and nothing says where the portrait is."""
    assert morph.MorphModule().region_of is morph.whole_frame


def test_a_region_seam_is_answered_with_the_frame_it_was_handed():
    """``whole_frame`` reads the working frame and no other source."""
    frame = object()

    assert morph.whole_frame(_context(frame)) is frame


def test_a_region_seam_is_refused_when_it_is_not_callable():
    """Wired wrongly fails at construction, like the classifier."""
    with pytest.raises(morph.MorphError):
        morph.MorphModule(region_of="the photo box")


def test_the_record_names_the_region_it_was_pointed_at_not_the_page():
    """A module reading a portrait must not claim to have read the page."""
    detail = _at_photo().run(_context(_page(MORPHED))).detail

    assert "the region this instance was pointed at" in detail


# --- the seam's own rules still hold -----------------------------------


def test_the_shipped_registry_still_holds_no_module():
    """15.1 pinned an empty registry and 15.3-15.5, 15.8-15.9 did not fill it."""
    from app.pipeline.tier2 import base

    assert base.MODULE_NAMES == ()


def test_the_verdict_refuses_a_suspect_flag_that_contradicts_its_score():
    """The record cannot say "suspected" while carrying a score below the line."""
    with pytest.raises(morph.MorphError):
        morph.MorphVerdict(score=0.0, frequency=0.0, boundary=0.0, suspect=True)
