"""15.11 -- a deepfake classifier is an interface, and its stand-in says it is one.

The claim pinned first is the verification the task names: the record this
module answers carries ``is_stub`` and the version string ``heuristic-v0``, so
nothing built on the cue can be read as a trained model's work.  The rest holds
that the label belongs to the classifier rather than to the module, that a
region too flat to measure is refused rather than scored, and that the cue line
sits in a gap measured on synthetic pairs -- D123.

The limits are pinned as carefully as the claim, because they are what makes it
honest: a text block reads as suspected, a checkerboard reads clean, and a
reconstruction re-grained hard enough stops firing altogether.  Every figure
here came from the shipped functions, and the fixture resizes the artwork it
already has rather than redrawing it.
"""

import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, deepfake

SCREENING_ID = uuid.UUID("7c2b1d4e-5a6f-4b7c-8d9e-0f1a2b3c4d5e")
FACE_SIDE = 200
PAGE_W, PAGE_H = 900, 700
PHOTO_AT = (640, 380)

#: The variants the size sweep rescales, and the seeds it photographs them at.
VARIANTS = (((46, 58), 17, 0), ((56, 72), 28, 6), ((52, 64), 19, 2), ((60, 60), 15, -8))
SIZES = (120, 200, 320)


def _head(side=FACE_SIDE, oval=(52, 66), eye=20, dx=0):
    """Return one synthetic head at ``side`` pixels square, in colour."""
    dx, eye = int(dx), int(eye)
    oval = (int(oval[0]), int(oval[1]))
    image = np.full((side, side, 3), 205, np.uint8)
    image[:, :] = (205, 190, 165)
    cv2.ellipse(image, (side // 2 + dx, side // 2), oval, 0, 0, 360, (150, 165, 175), -1)
    cv2.circle(image, (side // 2 + dx - eye, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.circle(image, (side // 2 + dx + eye, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.ellipse(image, (side // 2 + dx, side // 2 + 40), (26, 10), 0, 0, 180, (60, 65, 70), 2)
    return image


def _capture(art, seed=3, photons=0.9):
    """Return ``art`` as a capture: shot noise, whose variance follows light."""
    rng = np.random.default_rng(seed)
    lit = rng.poisson(np.clip(art.astype(np.float64) * photons, 0, None)) / photons
    read = rng.normal(0, 1.6, art.shape[:2] + (1,))
    return np.clip(lit + read, 0, 255).astype(np.uint8)


def _reconstructed(art, smooth=9, regrain=0.0, seed=4):
    """Return ``art`` rebuilt from a low-frequency basis, the way a model would.

    The strongest structure is put back so the result is not flat paper, and
    ``regrain`` adds uniform noise back, which is what a generated portrait
    that has been through a camera pipeline would carry.
    """
    image = art.astype(np.float64)
    low = cv2.GaussianBlur(image, (smooth, smooth), 0)
    edge = np.abs(cv2.Laplacian(cv2.cvtColor(art, cv2.COLOR_BGR2GRAY), cv2.CV_64F))
    out = low + (np.clip(edge / (edge.max() or 1.0), 0, 1) * 12.0)[:, :, None]
    if regrain:
        out = out + np.random.default_rng(seed).normal(0, regrain, image.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def _jpeg(region, quality):
    """Return ``region`` through a JPEG round trip at ``quality``."""
    encoded, buffer = cv2.imencode(
        ".jpg", region, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    assert encoded, "the test's own JPEG encoder refused its region"
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


ONE = _head()
CLEAN = _jpeg(_capture(ONE, seed=3), 75)
FAKE = _reconstructed(ONE, regrain=0.8, seed=3)


def _page(photo=None):
    """Return a 900x700 text page carrying ``photo`` at :data:`PHOTO_AT`."""
    page = np.full((PAGE_H, PAGE_W, 3), 236, np.uint8)
    for row in range(40, 300, 16):
        for column in range(40, 560, 18):
            cv2.line(page, (column, row), (column + 12, row), (70, 70, 70), 2, cv2.LINE_AA)
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
    return deepfake.DeepfakeModule(classifier=classifier, region_of=_photo_of)


class _Labelled(deepfake.DeepfakeClassifier):
    """A classifier reporting itself as a real model, so the swap can be read."""

    model_version = "arcface-deepfake-v3"
    is_stub = False

    def classify(self, region):
        return deepfake.deepfake_score(region)


# --- the task's own verification -----------------------------------------


def test_the_record_says_a_heuristic_produced_it():
    """The task's own verification: ``is_stub`` and ``heuristic-v0`` on the record."""
    result = _at_photo().run(_context(_page(FAKE)))

    assert result.is_stub is True
    assert result.model_version == "heuristic-v0"


def test_the_module_answers_under_the_name_its_flag_is_traced_to():
    """``TAMPER_DEEPFAKE_SUSPECTED`` carries the weight; the record names the module."""
    assert deepfake.MODULE_NAME == "tamper_deepfake"
    assert deepfake.MODEL_VERSION == "heuristic-v0"
    assert _at_photo().run(_context(_page(FAKE))).module == "tamper_deepfake"


# --- the label belongs to the classifier, not to the module --------------


def test_the_stand_in_labelled_itself_cannot_answer_otherwise():
    """Both attributes are fixed on the stand-in, so a module cannot relabel it."""
    stand_in = deepfake.HeuristicDeepfakeClassifier()

    assert stand_in.is_stub is True
    assert stand_in.model_version == "heuristic-v0"


def test_the_record_carries_the_classifier_label_not_the_module_one():
    """A real classifier's own version and stub flag are what reach the record."""
    result = _at_photo(classifier=_Labelled()).run(_context(_page(FAKE)))

    assert result.is_stub is False
    assert result.model_version == "arcface-deepfake-v3"


def test_a_module_is_refused_a_classifier_that_cannot_say_what_it_is():
    """Wired wrongly fails at construction, not on the first document."""
    with pytest.raises(deepfake.DeepfakeError):
        deepfake.DeepfakeModule(classifier=object())


def test_a_classifier_without_classify_cannot_be_built():
    """A subclass that never wrote ``classify`` fails the same way."""
    with pytest.raises(TypeError):
        type("_NoClassify", (deepfake.DeepfakeClassifier,), {"model_version": "x", "is_stub": True})()


# --- the cue, and the line it is read against ----------------------------


def test_a_clean_capture_reads_nothing_and_a_reconstruction_reads_suspect():
    """The whole claim: a capture's own noise fills the gradients a rebuild leaves."""
    clean = deepfake.deepfake_score(CLEAN)
    rebuilt = deepfake.deepfake_score(FAKE)

    assert clean.score == 0.0
    assert clean.suspect is False
    assert rebuilt.score > deepfake.SUSPECT_LEVEL
    assert rebuilt.suspect is True


def test_the_score_is_the_cue_itself_with_no_second_reading_averaged_in():
    """A rejected cue must not come back as half the score; D123 records why."""
    verdict = deepfake.deepfake_score(FAKE)

    assert verdict.score == verdict.flat
    assert verdict.flat == deepfake.flat_cue(FAKE)


def test_the_level_sits_in_a_gap_the_probe_measured():
    """Every clean capture falls below the line and every reconstruction above it.

    The two groups are read live rather than against pinned figures, so this
    holds the constant to being a midpoint of a gap these fixtures leave rather
    than to being the number the probe once printed.
    """
    clean_shares, rebuilt_shares = [], []
    for side in SIZES:
        for oval, eye, dx in VARIANTS:
            art = _head(side, oval, eye, dx)
            for seed in (3, 8):
                for quality in (95, 75, 60):
                    clean_shares.append(deepfake.flat_share(_jpeg(_capture(art, seed=seed), quality)))
                for regrain in (0.0, 0.8, 1.6, 2.5, 4.0):
                    rebuilt_shares.append(deepfake.flat_share(_reconstructed(art, regrain=regrain, seed=seed)))

    assert clean_shares and rebuilt_shares
    assert max(clean_shares) < deepfake.GRADIENT_LEVEL < min(rebuilt_shares)
    assert all(deepfake.flat_cue(_jpeg(_capture(_head(s, o, e, d), seed=k), 75)) == 0.0
               for s in (200,) for (o, e, d) in VARIANTS for k in (3, 8))


# Rescaled, never redrawn: redrawing changes relative stroke widths, so a method
# that could not survive a redraw would look stable here for the wrong reason.


def test_the_cue_survives_the_portrait_being_photographed_at_another_size():
    """Canonicalisation is why the share is a property of the portrait."""
    for side in (120, 160, 240, 320):
        rescaled = cv2.resize(CLEAN, (side, side), interpolation=cv2.INTER_AREA)
        assert deepfake.deepfake_score(rescaled).suspect is False

        rebuilt = cv2.resize(FAKE, (side, side), interpolation=cv2.INTER_AREA)
        assert deepfake.deepfake_score(rebuilt).suspect is True


def test_jpeg_quality_does_not_move_the_line():
    """A real capture is encoded, so the gap has to survive being re-encoded."""
    for quality in (95, 85, 75, 60, 50, 40):
        assert deepfake.deepfake_score(_jpeg(CLEAN, quality)).suspect is False
        assert deepfake.deepfake_score(_jpeg(FAKE, quality)).suspect is True


def test_a_reconstruction_re_grained_hard_enough_stops_being_flagged():
    """The honest limit, and it is size-dependent: grain puts flatness back.

    Measured across seven variants: at side 200 and above a reconstruction still
    fires after 6.0 of added noise, while at side 120 it stops firing between
    4.0 and 5.0, and every one of the fourteen misses was a 120px or 160px
    source.  The smaller the portrait, the more of that grain ``INTER_AREA``
    averages away on the way to the 64px grid, so a small one is the easier to
    hide.  This test exists so the limit is stated rather than found later.
    """
    small = deepfake.deepfake_score(_reconstructed(_head(120, (46, 58), 17, 0), regrain=5.0, seed=77))

    assert small.suspect is False, "a small reconstruction re-grained 5.0 no longer reads clean"
    for side in (200, 260, 320):
        large = deepfake.deepfake_score(_reconstructed(_head(side, (46, 58), 17, 0), regrain=6.0, seed=77))
        assert large.suspect is True, f"side {side} no longer survives 6.0 of re-grain"


# --- an absence is refused, never scored --------------------------------


def test_a_region_with_no_power_to_share_is_refused_rather_than_scored():
    """Blank paper reads a flat share of 1.000, the strongest possible answer."""
    with pytest.raises(deepfake.DeepfakeError):
        deepfake.deepfake_score(np.full((FACE_SIDE, FACE_SIDE, 3), 236, np.uint8))


def test_a_region_too_small_to_read_on_the_grid_is_refused():
    """A crop smaller than the canonical grid would be upsampled, not measured."""
    with pytest.raises(deepfake.DeepfakeError):
        deepfake.deepfake_score(np.zeros((10, 10, 3), np.uint8))


def test_the_absence_is_a_named_answer_rather_than_a_zero():
    """``NO_SIGNAL`` exists so a caller can test for it without inventing one."""
    assert deepfake.NO_SIGNAL is None


# --- the limits, pinned so they cannot quietly change --------------------


def test_a_text_block_reads_as_suspected_and_a_checkerboard_reads_clean():
    """The cue reads flatness and not provenance; measured, and not a small effect.

    A body-text block reads 0.506 and a checkerboard 0.000, so the cue is not
    wrong by a hair here -- it points the other way on both.  D123 holds this as
    the limit that a face detector would close.
    """
    text = np.full((FACE_SIDE, FACE_SIDE, 3), 200, np.uint8)
    for row in range(20, FACE_SIDE, 16):
        for column in range(20, FACE_SIDE, 18):
            cv2.line(text, (column, row), (column + 12, row), (70, 70, 70), 2, cv2.LINE_AA)
    checker = np.repeat(
        np.where((np.indices((FACE_SIDE, FACE_SIDE)).sum(axis=0) % 16 < 8)[:, :, None], 255, 0).astype(np.uint8),
        3,
        axis=2,
    )

    assert deepfake.deepfake_score(text).suspect is True
    assert deepfake.deepfake_score(checker).suspect is False


# --- the record an officer reads ---------------------------------------


def test_a_record_below_the_line_says_nothing_found():
    """D121 one level up: a score of 0.00 is never worded as a suspicion."""
    detail = _at_photo().run(_context(_page(CLEAN))).detail

    assert "nothing found" in detail
    assert "a suspected synthetic portrait" not in detail


def test_a_record_above_the_line_says_a_suspected_synthetic_portrait():
    """The same sentence must name a finding when there is one."""
    assert "a suspected synthetic portrait" in _at_photo().run(_context(_page(FAKE))).detail


def test_every_record_says_the_cue_is_not_provenance():
    """The known limit is in the sentence, not only in this test file."""
    detail = _at_photo().run(_context(_page(CLEAN))).detail

    assert "rather than whether anything generated it" in detail
    assert "no real deepfake has ever been scored" in detail


def test_a_record_reports_no_heatmap_and_no_region():
    """One number for the whole region, so there is no map and no box to draw."""
    result = _at_photo().run(_context(_page(FAKE)))

    assert result.heatmap == ()
    assert result.regions == ()


# --- which region was measured ----------------------------------------


def test_the_module_measures_the_whole_frame_when_nothing_else_is_named():
    """The seam hands over a frame and nothing says where the portrait is."""
    assert deepfake.DeepfakeModule().region_of is deepfake.whole_frame


def test_a_region_seam_is_answered_with_the_frame_it_was_handed():
    """``whole_frame`` reads the working frame and no other source."""
    frame = object()

    assert deepfake.whole_frame(_context(frame)) is frame


def test_a_region_seam_is_refused_when_it_is_not_callable():
    """Wired wrongly fails at construction, like the classifier."""
    with pytest.raises(deepfake.DeepfakeError):
        deepfake.DeepfakeModule(region_of="the photo box")


def test_the_record_names_the_region_it_was_pointed_at_not_the_page():
    """A module reading a portrait must not claim to have read the page."""
    assert "the region this instance was pointed at" in _at_photo().run(_context(_page(FAKE))).detail


# --- the seam's own rules still hold -----------------------------------


def test_the_shipped_registry_still_holds_no_module():
    """15.1 pinned an empty registry and 15.3-15.5, 15.8-15.10 did not fill it."""
    assert base.MODULE_NAMES == ()


def test_the_verdict_refuses_a_suspect_flag_that_contradicts_its_score():
    """The record cannot say "suspected" while carrying a score below the line."""
    with pytest.raises(deepfake.DeepfakeError):
        deepfake.DeepfakeVerdict(score=0.0, flat=0.0, suspect=True)
