"""15.4 -- an edited region shows anomalous noise, and the map says why it does.

The claim pinned first is the verification the task names: a region that was
edited carries a departure in its noise variance against the rest of its own
page, while a control region of the same size on the same page does not.  The
rest pins that the map is measured against the page rather than against an
absolute noise level, that the departure is symmetric in both directions, that
a page carrying no measurable noise is refused rather than answered as a clean
one, and that the module ships labelled -- D118.

The captures here are synthetic on purpose: a gradient page carrying its own
grain, with one region blurred so its noise collapses and another given extra
grain.  A real capture's text and edges carry their own noise structure, which
is why this asserts the contrast between two regions of one page rather than a
reading in the abstract.
"""

import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, noise_residual

SCREENING_ID = uuid.UUID("6c1f0b74-52ae-4d38-9f60-3ab5d7e24c18")
WIDTH, HEIGHT = 256, 192
#: The region blurred so its noise collapses, and a control region of the same
#: size on the other side of the page that is left untouched.
EDITED_BOX = (96, 56, 48, 48)
CONTROL_BOX = (16, 16, 48, 48)
#: The quality the page was written at, the strength of the blur applied to the
#: edited region, and the grain the page carries before it is written.
PAGE_QUALITY = 95
EDIT_BLUR = 5
GRAIN = 18
SEED = 20261002


def _jpeg(frame, quality):
    """Return ``frame`` as a codec wrote it and read it back."""
    encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert encoded, "the test's own JPEG encoder refused its frame"
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _grainy_page():
    """A gradient page carrying its own grain, so every block has a noise level."""
    across = np.linspace(30, 200, WIDTH, dtype=np.float64)
    down = np.linspace(30, 200, HEIGHT, dtype=np.float64)
    blue, green = np.meshgrid(across, down)
    ripple = np.cos(np.linspace(0, 3, HEIGHT)).reshape(-1, 1)
    red = 120.0 + 60.0 * np.sin(np.linspace(0, 3, WIDTH)) * ripple
    frame = np.clip(np.dstack([red, green, blue]), 0, 255).astype(np.uint8)
    rng = np.random.default_rng(SEED)
    grain = rng.integers(-GRAIN, GRAIN + 1, size=(HEIGHT, WIDTH, 1)).astype(np.int16)
    return np.clip(frame.astype(np.int16) + grain, 0, 255).astype(np.uint8)


#: A capture as it arrives: written once, at :data:`PAGE_QUALITY`.
PAGE = _jpeg(_grainy_page(), PAGE_QUALITY)


def _blurred_region(page):
    """Return ``page`` with :data:`EDITED_BOX` smoothed, as an edit would."""
    x, y, width, height = EDITED_BOX
    edited = page.copy()
    edited[y : y + height, x : x + width] = cv2.medianBlur(
        page[y : y + height, x : x + width], EDIT_BLUR
    )
    return edited


def _noisier_region(page, seed=7, amount=40):
    """Return ``page`` with :data:`EDITED_BOX` given grain it did not have."""
    x, y, width, height = EDITED_BOX
    edited = page.copy()
    rng = np.random.default_rng(seed)
    extra = rng.integers(-amount, amount + 1, size=(height, width, 1)).astype(np.int16)
    patch = page[y : y + height, x : x + width].astype(np.int16) + extra
    edited[y : y + height, x : x + width] = np.clip(patch, 0, 255).astype(np.uint8)
    return edited


EDITED = _blurred_region(PAGE)
NOISIER = _noisier_region(PAGE)


def _context(image):
    """A context carrying the working frame the seam hands a module."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _cells_under(box, heatmap):
    """The heatmap cells covering ``box``, which the test keeps block-aligned."""
    x, y, width, height = box
    side = noise_residual.VARIANCE_BLOCK
    rows = heatmap[y // side : (y + height) // side]
    return [cell for row in rows for cell in row[x // side : (x + width) // side]]


def _whole_map(heatmap):
    """Every cell of the map, in row order."""
    return [cell for row in heatmap for cell in row]


def test_an_edited_region_shows_anomalous_variance():
    """The task's own verification: the edited box departs from its own page."""
    inside = _cells_under(EDITED_BOX, noise_residual.noise_heatmap(EDITED))

    assert inside, "the edited box must cover whole blocks for this to measure anything"
    assert max(inside) >= noise_residual.HOT_LEVEL


def test_the_page_beside_the_edited_region_stays_ordinary():
    """A departure only localises if the rest of the same page did not depart."""
    heatmap = noise_residual.noise_heatmap(EDITED)
    inside = _cells_under(EDITED_BOX, heatmap)
    control = _cells_under(CONTROL_BOX, heatmap)

    assert max(control) < noise_residual.HOT_LEVEL
    assert max(inside) >= 4 * max(control)


def test_an_untouched_capture_departs_nowhere():
    """The same map on the page before the edit, so the contrast is the edit's."""
    heatmap = noise_residual.noise_heatmap(PAGE)

    assert max(_whole_map(heatmap)) < noise_residual.HOT_LEVEL


def test_a_region_made_noisier_also_reads_as_anomalous():
    """The departure is symmetric: too little noise departs as much as too much."""
    heatmap = noise_residual.noise_heatmap(NOISIER)
    inside = _cells_under(EDITED_BOX, heatmap)
    control = _cells_under(CONTROL_BOX, heatmap)

    assert max(inside) >= noise_residual.HOT_LEVEL
    assert max(control) < noise_residual.HOT_LEVEL


def test_the_map_is_measured_against_the_page_not_against_an_absolute_level():
    """A capture's absolute noise depends on its scanner and lighting, so the
    same departure must read the same on a capture that is quieter overall."""
    quieter = np.clip(PAGE.astype(np.float64) * 0.6, 0, 255).astype(np.uint8)
    quieter_edited = _blurred_region(quieter)
    heatmap = noise_residual.noise_heatmap(quieter_edited)

    assert max(_cells_under(EDITED_BOX, heatmap)) >= noise_residual.HOT_LEVEL
    assert max(_cells_under(CONTROL_BOX, heatmap)) < noise_residual.HOT_LEVEL


def test_the_map_is_one_cell_per_block():
    """A cell is the unit the variance is measured over, so a partial edge drops."""
    heatmap = noise_residual.noise_heatmap(PAGE)
    side = noise_residual.VARIANCE_BLOCK

    assert (len(heatmap), len(heatmap[0])) == (HEIGHT // side, WIDTH // side)
    assert (len(heatmap), len(heatmap[0])) == noise_residual.block_variance(
        noise_residual.high_pass(PAGE), side
    ).shape


def test_a_frame_that_is_not_a_multiple_of_a_block_drops_its_remainder():
    """Rows of two different widths are refused by the record, so they cannot happen."""
    small = np.random.default_rng(3).integers(0, 256, (20, 20, 3), dtype=np.uint8)
    heatmap = noise_residual.noise_heatmap(small)

    assert (len(heatmap), len(heatmap[0])) == (2, 2)


def test_every_cell_is_a_normalised_number():
    """The record holds numbers in [0, 1] and no pixels of the capture."""
    heatmap = noise_residual.noise_heatmap(EDITED)
    widths = {len(row) for row in heatmap}

    assert widths == {len(heatmap[0])}
    assert all(type(cell) is float for cell in _whole_map(heatmap))
    assert all(0.0 <= cell <= 1.0 for cell in _whole_map(heatmap))


def test_the_residual_is_the_capture_minus_a_median_of_itself():
    """The high-pass is one median subtraction, so the residual can be rebuilt."""
    gray = noise_residual.to_gray(EDITED)
    residual = noise_residual.high_pass(EDITED)

    assert np.allclose(residual, gray - cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float64))


def test_the_block_variance_is_measured_inside_each_block():
    """A cell is the variance of one block, so it is reproducible from the raw
    residual rather than trusted as a black box."""
    residual = noise_residual.high_pass(PAGE)
    side = noise_residual.VARIANCE_BLOCK
    rows, cols = HEIGHT // side, WIDTH // side
    whole = residual[: rows * side, : cols * side]

    assert np.allclose(
        noise_residual.block_variance(residual, side),
        whole.reshape(rows, side, cols, side).var(axis=(1, 3)),
    )


def test_a_departure_reads_full_at_the_factor_and_nothing_at_the_baseline():
    """The map is anchored at both ends: a block sitting at the page's own noise
    reads nothing, and one the factor away reads everything, in either
    direction, so the line is not arbitrary."""
    variances = np.array([[1.0, 8.0, 64.0]])
    normalised = noise_residual.normalise(variances, factor=8.0, baseline=8.0)

    assert normalised[0][1] == pytest.approx(0.0)
    assert normalised[0][0] == pytest.approx(1.0)
    assert normalised[0][2] == pytest.approx(1.0)


def test_a_page_with_no_measurable_noise_is_refused():
    """With every variance at zero there is nothing to depart from, and a ratio
    against zero is not a measurement."""
    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.noise_heatmap(np.full((64, 64, 3), 128, np.uint8))


def test_a_baseline_of_zero_is_refused_rather_than_dividing_by_it():
    """The refusal is the module's, not left to a nan that the record would reject."""
    variances = np.ones((2, 2))

    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.normalise(variances, baseline=0.0)


def test_a_factor_at_or_below_one_is_refused():
    """A factor of one would call every block with no variance fully hot."""
    variances = np.ones((2, 2))

    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.normalise(variances, factor=1.0)

    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.normalise(variances, factor=0.5)


@pytest.mark.parametrize("kernel", [0, 1, 2, 4, -3, True, 3.0])
def test_a_median_window_that_cannot_be_measured_is_refused(kernel):
    """An even or tiny window is not a median, and a float window is not a window."""
    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.high_pass(PAGE, kernel=kernel)


def test_a_median_window_wider_than_the_frame_is_refused():
    """A window past the frame's edge would answer the border rule, not the noise."""
    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.high_pass(np.full((8, 8, 3), 128, np.uint8), kernel=9)


@pytest.mark.parametrize("block", [0, -8, True, 8.0])
def test_a_block_that_is_not_a_whole_positive_number_is_refused(block):
    """A fractional block has no whole pixels to average over."""
    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.block_variance(noise_residual.high_pass(PAGE), block)


def test_a_frame_smaller_than_one_block_is_refused():
    """There is no whole block to measure, and a partial one is not one."""
    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.noise_heatmap(np.zeros((4, 4, 3), np.uint8))


def test_a_frame_that_is_not_8_bit_pixels_is_refused():
    """Rescaling another dtype silently would be a measurement of another picture."""
    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.noise_heatmap(np.zeros((16, 16, 3), np.float32))

    with pytest.raises(noise_residual.NoiseResidualError):
        noise_residual.to_gray(None)


def test_a_colour_capture_and_a_gray_one_answer_the_same_map():
    """One capture measured two ways is one measurement, not two to disagree."""
    gray = cv2.cvtColor(EDITED, cv2.COLOR_BGR2GRAY)

    assert noise_residual.noise_heatmap(gray) == noise_residual.noise_heatmap(EDITED)


def test_the_module_answers_a_record_that_names_itself():
    """D116's label fields are what stops a heatmap reading as a finding."""
    result = noise_residual.NoiseResidualModule().run(_context(EDITED))

    assert result.module == noise_residual.MODULE_NAME == "tamper_noise_residual"
    assert result.is_stub is True
    assert result.model_version
    assert "tampering" in result.detail


def test_the_score_is_the_worst_block_on_the_map():
    """One comparable scale, so 15.6's fusion reads this beside its neighbours."""
    result = noise_residual.NoiseResidualModule().run(_context(EDITED))

    assert result.score == max(_whole_map(result.heatmap))


def test_the_record_locates_nothing_yet():
    """15.13 is the task that turns a heatmap into polygons, and this is not it."""
    assert noise_residual.NoiseResidualModule().run(_context(EDITED)).regions == ()


def test_the_module_runs_through_the_registry_the_seam_holds():
    """The module constructs a D116 record behind 15.1's seam."""
    run = base.run_deep_modules(
        _context(EDITED), modules={noise_residual.MODULE_NAME: noise_residual.NoiseResidualModule()}
    )

    assert run.ran == (noise_residual.MODULE_NAME,)
    assert isinstance(run.results[0], base.DeepResult)


def test_the_module_is_shipped_and_still_not_registered():
    """15.6 is the task that fuses these, and a two-of-three registry would
    claim a deep tier ran when only two of its modules had."""
    assert noise_residual.MODULE_NAME not in base.MODULE_NAMES
