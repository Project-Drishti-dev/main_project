"""15.3 -- ELA lights up a region that was encoded again, and says what it read.

The claim pinned first is the verification the task names: a re-compressed
region reads hot on the map while the page beside it stays dark.  The rest
pins that the map is normalised against a committed ceiling rather than
against its own maximum, that it is one cell per JPEG block, that the frame
is re-encoded at every shipped quality, that a frame ELA cannot measure is
refused instead of answered as a clean page, and that the module ships
labelled -- D117.

The captures here are synthetic on purpose: a soft gradient page carrying no
detail for a codec to lose, with one region replaced by the output of a
second encoder.  A real capture's text and edges ring under every quality,
which is why this asserts the contrast between two regions of one page
rather than a reading in the abstract.
"""

import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, ela

SCREENING_ID = uuid.UUID("2f8a6d51-9b3c-4e07-8a1d-5c6e7f80912a")
WIDTH, HEIGHT = 256, 192
#: The region replaced by a second encoder, and a control region of the same
#: size on the other side of the page that is left untouched.
EDITED_BOX = (96, 56, 48, 48)
CONTROL_BOX = (16, 16, 48, 48)
#: The quality the page itself was saved at, and the one its edited region was
#: written at.  The gap between them is the double compression being looked for.
PAGE_QUALITY = 95
PATCH_QUALITY = 30
SEED = 20261002


def _jpeg(frame, quality):
    """Return ``frame`` as a codec wrote it and read it back."""
    encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert encoded, "the test's own JPEG encoder refused its frame"
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _smooth_page():
    """A page of nothing but a soft gradient, so a block has no detail to lose."""
    across = np.linspace(30, 200, WIDTH, dtype=np.float64)
    down = np.linspace(30, 200, HEIGHT, dtype=np.float64)
    blue, green = np.meshgrid(across, down)
    ripple = np.cos(np.linspace(0, 3, HEIGHT)).reshape(-1, 1)
    red = 120.0 + 60.0 * np.sin(np.linspace(0, 3, WIDTH)) * ripple
    return np.clip(np.dstack([red, green, blue]), 0, 255).astype(np.uint8)


def _printed_patch(height, width):
    """Fine detail with grain on it, which is what a second codec destroys."""
    rng = np.random.default_rng(SEED)
    patch = np.full((height, width, 3), 235, np.uint8)
    for row in range(height // 6 + 1):
        cv2.putText(
            patch, "MRZ", (2, 6 + row * 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (15, 15, 15), 1, cv2.LINE_AA,
        )
    grain = rng.integers(-30, 31, size=(height, width, 1)).astype(np.int16)
    return np.clip(patch.astype(np.int16) + grain, 0, 255).astype(np.uint8)


#: A capture as it arrives: written once, at :data:`PAGE_QUALITY`.
PAGE = _jpeg(_smooth_page(), PAGE_QUALITY)


def _region_encoded_again(page):
    """Return ``page`` with :data:`EDITED_BOX` replaced by a codec's output."""
    x, y, width, height = EDITED_BOX
    edited = page.copy()
    edited[y : y + height, x : x + width] = _jpeg(
        _printed_patch(height, width), PATCH_QUALITY
    )
    return edited


RECOMPRESSED = _region_encoded_again(PAGE)


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
    side = ela.BLOCK_SIZE
    rows = heatmap[y // side : (y + height) // side]
    return [cell for row in rows for cell in row[x // side : (x + width) // side]]


def _whole_map(heatmap):
    """Every cell of the map, in row order."""
    return [cell for row in heatmap for cell in row]


def test_a_re_compressed_region_lights_up():
    """The task's own verification: the region a second encoder wrote is hot."""
    inside = _cells_under(EDITED_BOX, ela.ela_heatmap(RECOMPRESSED))

    assert inside, "the edited box must cover whole blocks for this to measure anything"
    assert max(inside) >= ela.HOT_LEVEL


def test_the_page_beside_the_edited_region_stays_dark():
    """A lit region only localises if the rest of the same page did not light up."""
    heatmap = ela.ela_heatmap(RECOMPRESSED)
    inside = _cells_under(EDITED_BOX, heatmap)
    control = _cells_under(CONTROL_BOX, heatmap)

    assert max(control) < ela.HOT_LEVEL
    assert max(inside) >= 4 * max(control)


def test_an_untouched_capture_lights_up_nowhere():
    """The same map on the page before the edit, so the contrast is the edit's."""
    heatmap = ela.ela_heatmap(PAGE)

    assert max(_whole_map(heatmap)) < ela.HOT_LEVEL


def test_the_map_is_one_cell_per_jpeg_block():
    """A cell is the unit the codec coded, so a partial edge block is dropped."""
    heatmap = ela.ela_heatmap(PAGE)

    assert (len(heatmap), len(heatmap[0])) == (HEIGHT // ela.BLOCK_SIZE, WIDTH // ela.BLOCK_SIZE)
    assert (len(heatmap), len(heatmap[0])) == ela.block_means(
        ela.to_gray(PAGE), ela.BLOCK_SIZE
    ).shape


def test_a_frame_that_is_not_a_multiple_of_a_block_drops_its_remainder():
    """Rows of two different widths are refused by the record, so they cannot happen."""
    heatmap = ela.ela_heatmap(np.full((20, 20, 3), 128, np.uint8))

    assert (len(heatmap), len(heatmap[0])) == (2, 2)


def test_every_cell_is_a_normalised_number():
    """The record holds numbers in [0, 1] and no pixels of the capture."""
    heatmap = ela.ela_heatmap(RECOMPRESSED)
    widths = {len(row) for row in heatmap}

    assert widths == {len(heatmap[0])}
    assert all(type(cell) is float for cell in _whole_map(heatmap))
    assert all(0.0 <= cell <= 1.0 for cell in _whole_map(heatmap))


def test_the_frame_is_re_encoded_at_every_shipped_quality(monkeypatch):
    """The task says several qualities, and one quality would not be several."""
    seen = []
    real = ela.jpeg_round_trip

    def record(image, quality):
        seen.append(quality)
        return real(image, quality)

    monkeypatch.setattr(ela, "jpeg_round_trip", record)

    ela.ela_heatmap(PAGE)

    assert len(ela.QUALITIES) > 1
    assert tuple(seen) == ela.QUALITIES


def test_a_narrower_set_of_qualities_still_answers_a_map():
    """A caller may retune the qualities without being refused for narrowing."""
    heatmap = ela.ela_heatmap(PAGE, qualities=(95,))

    assert heatmap == ela.ela_heatmap(PAGE, qualities=(95,))


def test_no_quality_at_all_is_refused():
    """A round trip that never happened measures nothing and is not a clean page."""
    with pytest.raises(ela.ELAError):
        ela.ela_heatmap(PAGE, qualities=())


@pytest.mark.parametrize("quality", [0, 101, 75.0, True])
def test_a_quality_outside_the_jpeg_range_is_refused(quality):
    """OpenCV clamps rather than refuses, so a clamped quality would be a lie."""
    with pytest.raises(ela.ELAError):
        ela.ela_heatmap(PAGE, qualities=(quality,))


def test_a_frame_smaller_than_one_block_is_refused():
    """There is no whole block to measure, and a partial one is not one."""
    with pytest.raises(ela.ELAError):
        ela.ela_heatmap(np.zeros((4, 4, 3), np.uint8))


def test_a_frame_that_is_not_8_bit_pixels_is_refused():
    """Rescaling another dtype silently would be a measurement of another picture."""
    with pytest.raises(ela.ELAError):
        ela.ela_heatmap(np.zeros((16, 16, 3), np.float32))

    with pytest.raises(ela.ELAError):
        ela.to_gray(None)


def test_a_colour_capture_and_a_gray_one_answer_the_same_map():
    """One capture measured two ways is one measurement, not two to disagree."""
    gray = cv2.cvtColor(RECOMPRESSED, cv2.COLOR_BGR2GRAY)

    assert ela.ela_heatmap(gray) == ela.ela_heatmap(RECOMPRESSED)


def test_the_module_answers_a_record_that_names_itself():
    """D116's label fields are what stops a heatmap reading as a finding."""
    result = ela.ELAModule().run(_context(RECOMPRESSED))

    assert result.module == ela.MODULE_NAME == "tamper_ela"
    assert result.is_stub is True
    assert result.model_version
    assert "tampering" in result.detail


def test_the_score_is_the_worst_block_on_the_map():
    """One comparable scale, so 15.6's fusion reads this beside its neighbours."""
    result = ela.ELAModule().run(_context(RECOMPRESSED))

    assert result.score == max(_whole_map(result.heatmap))


def test_the_record_locates_nothing_yet():
    """15.13 is the task that turns a heatmap into polygons, and this is not it."""
    assert ela.ELAModule().run(_context(RECOMPRESSED)).regions == ()


def test_the_module_runs_through_the_registry_the_seam_holds():
    """The first module to construct a D116 record does it behind 15.1's seam."""
    run = base.run_deep_modules(
        _context(RECOMPRESSED), modules={ela.MODULE_NAME: ela.ELAModule()}
    )

    assert run.ran == (ela.MODULE_NAME,)
    assert isinstance(run.results[0], base.DeepResult)


def test_the_module_is_shipped_and_still_not_registered():
    """15.6 is the task that fuses these, and a half-filled registry would claim
    a deep tier ran when only one of its modules had."""
    assert ela.MODULE_NAME not in base.MODULE_NAMES
