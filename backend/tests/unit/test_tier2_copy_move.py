"""15.5 -- a duplicated region inside the document is localised.

The claim pinned first is the verification the task names: a region copied
from one place in the document to another is found, and both of its ends are
named.  The rest pins that a translation needs agreement before it is called a
copy, that an untouched page carries none, that the map is measured against a
committed ceiling rather than its own maximum, and that the module ships
labelled -- D119.

The capture is synthetic on purpose: a textured page written once at quality
95, with one 150x150 region pasted elsewhere and the file written again, which
is what a forgery looks like.  Its texture is dense enough for a detector to
find something to match, and every constant in the module was measured against
it -- see D119.
"""

import math
import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, copy_move

SCREENING_ID = uuid.UUID("2f7b6d31-9c4a-4e15-9b72-1d4c8af60e35")
WIDTH, HEIGHT = 480, 360
#: The region copied, as (x, y, width, height), and where it was pasted.  The
#: paste overwrites the photo block, so the duplicate is visible on the page.
SOURCE_BOX = (32, 72, 150, 150)
PASTE_AT = (300, 190)
PAGE_QUALITY = 95
SEED = 20261005
#: The translation between the two ends, which is what the module should report.
EXPECTED_SHIFT = (PASTE_AT[0] - SOURCE_BOX[0], PASTE_AT[1] - SOURCE_BOX[1])


def _document():
    """A page carrying text, a photo block and a caption, so it has texture."""
    rng = np.random.default_rng(SEED)
    gray = np.full((HEIGHT, WIDTH), 236, np.uint8)
    gray[0:44, :] = np.linspace(202, 248, WIDTH, dtype=np.uint8)
    y = 70
    while y < 300:
        x = 30
        while x < 250:
            length = int(rng.integers(8, 34))
            cv2.line(gray, (x, y), (x + length, y), int(rng.integers(15, 90)),
                     int(rng.integers(1, 3)), cv2.LINE_AA)
            x += length + int(rng.integers(5, 11))
        y += 12
    for _ in range(160):
        centre = (int(rng.integers(284, 446)), int(rng.integers(74, 226)))
        cv2.circle(gray, centre, int(rng.integers(2, 14)), int(rng.integers(30, 230)), -1)
    photo = gray[70:230, 280:450].astype(np.int16)
    gray[70:230, 280:450] = np.clip(
        photo + rng.integers(-22, 23, (160, 170)), 0, 255).astype(np.uint8)
    cv2.rectangle(gray, (30, 310), (240, 340), 205, -1)
    cv2.circle(gray, (410, 320), 26, 90, 3)
    cv2.line(gray, (392, 320), (428, 320), 90, 3)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _written(frame):
    """Return ``frame`` as a codec wrote it and read it back."""
    encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), PAGE_QUALITY])
    assert encoded, "the test's own JPEG encoder refused its frame"
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _with_copy(page):
    """Return ``page`` with :data:`SOURCE_BOX` pasted over itself, then written."""
    x, y, width, height = SOURCE_BOX
    forged = page.copy()
    forged[PASTE_AT[1] : PASTE_AT[1] + height, PASTE_AT[0] : PASTE_AT[0] + width] = page[
        y : y + height, x : x + width
    ]
    return _written(forged)


#: A capture as it arrives, and the same capture with a region pasted elsewhere.
PAGE = _written(_document())
FORGED = _with_copy(PAGE)

#: The expensive half, measured once: what the module makes of each capture.
FORGED_CLUSTERS = copy_move.copy_clusters(FORGED)
FORGED_VOTES = copy_move.vote_map(FORGED_CLUSTERS, FORGED.shape[:2])
FORGED_HEATMAP = copy_move.copy_move_heatmap(FORGED)
FORGED_REGIONS = copy_move.copy_move_regions(FORGED)
CLEAN_CLUSTERS = copy_move.copy_clusters(PAGE)
CLEAN_HEATMAP = copy_move.copy_move_heatmap(PAGE)


def _context(image):
    """A context carrying the working frame the seam hands a module."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _box_of(polygon):
    """The ``(left, top, right, bottom)`` a clockwise-from-top-left box covers."""
    (left, top), (right, _), (_, bottom), _ = polygon
    return left, top, right, bottom


def _holds(box, polygon):
    """Whether ``polygon`` sits entirely inside ``box``, corners exclusive."""
    left, top, right, bottom = _box_of(polygon)
    x, y, width, height = box
    return left >= x and top >= y and right <= x + width and bottom <= y + height


def _overlaps(box, polygon):
    """Whether ``polygon`` shares any area at all with ``box``."""
    left, top, right, bottom = _box_of(polygon)
    x, y, width, height = box
    return left < x + width and right > x and top < y + height and bottom > y


def _cells_under(box, heatmap):
    """The heatmap cells covering ``box``, which the fixture keeps block-aligned."""
    x, y, width, height = box
    side = copy_move.BLOCK_SIZE
    rows = heatmap[y // side : (y + height) // side]
    return [cell for row in rows for cell in row[x // side : (x + width) // side]]


def _cells_outside(boxes, heatmap):
    """Every cell of the map not covered by ``boxes``."""
    side = copy_move.BLOCK_SIZE
    covered = set()
    for x, y, width, height in boxes:
        for row in range(y // side, (y + height) // side):
            for col in range(x // side, (x + width) // side):
                covered.add((row, col))
    return [
        cell
        for row, cells in enumerate(heatmap)
        for col, cell in enumerate(cells)
        if (row, col) not in covered
    ]


def _paste_box():
    """The box the region was pasted into, in the same terms as its source."""
    x, y, width, height = SOURCE_BOX
    return PASTE_AT[0], PASTE_AT[1], width, height


def _agreeing(count, shift):
    """``count`` matches that all carry the same ``shift``."""
    dx, dy = shift
    return tuple(
        copy_move.CopyMatch(
            source=(float(10 * n), float(4 * n)), copy=(float(10 * n + dx), float(4 * n + dy)),
            shift=(float(dx), float(dy)),
        )
        for n in range(count)
    )


def _scattered(count):
    """``count`` matches whose shifts all point somewhere different."""
    return tuple(
        copy_move.CopyMatch(
            source=(float(n), float(n)), copy=(float(n + 40 + 7 * n), float(n - 90)),
            shift=(float(40 + 7 * n), float(-90)),
        )
        for n in range(count)
    )


def test_a_duplicated_region_inside_the_document_is_localised():
    """The task's own verification: the copy is found and both its ends named."""
    assert FORGED_REGIONS, "a pasted region must be located"
    assert any(_holds(SOURCE_BOX, region) for region in FORGED_REGIONS)
    assert any(_holds(_paste_box(), region) for region in FORGED_REGIONS)


def test_both_ends_of_the_copy_are_located_not_just_the_paste():
    """A copy-move is two places, and naming one of them would localise nothing."""
    inside_source = [r for r in FORGED_REGIONS if _overlaps(SOURCE_BOX, r)]
    inside_paste = [r for r in FORGED_REGIONS if _overlaps(_paste_box(), r)]

    assert len(inside_source) == 1
    assert len(inside_paste) == 1
    assert inside_source[0] != inside_paste[0]


def test_the_heatmap_is_hot_only_where_the_copy_sits():
    """A map that lit up everywhere would localise nothing, so the rest is dark."""
    inside = _cells_under(SOURCE_BOX, FORGED_HEATMAP) + _cells_under(_paste_box(), FORGED_HEATMAP)
    outside = _cells_outside((SOURCE_BOX, _paste_box()), FORGED_HEATMAP)

    assert max(inside) >= copy_move.HOT_LEVEL
    assert max(outside) < copy_move.HOT_LEVEL


def test_an_untouched_capture_carries_no_copy():
    """The contrast is the copy's, so the same page before it must find nothing."""
    assert CLEAN_CLUSTERS == ()
    assert copy_move.copy_move_regions(PAGE) == ()
    assert max(max(row) for row in CLEAN_HEATMAP) == 0.0


def test_the_copy_is_named_by_the_translation_between_its_two_ends():
    """Both directions of the same copy are found, one per side."""
    shifts = {(round(abs(c.shift[0])), round(abs(c.shift[1]))) for c in FORGED_CLUSTERS}

    assert (round(abs(EXPECTED_SHIFT[0])), round(abs(EXPECTED_SHIFT[1]))) in shifts
    assert all(len(c.matches) >= copy_move.MIN_COPIES for c in FORGED_CLUSTERS)


def test_a_translation_needs_agreement_before_it_is_called_a_copy():
    """One pair is a coincidence, and repeated texture is not a copied region."""
    assert copy_move.translate_clusters(_agreeing(copy_move.MIN_COPIES - 1, (200, 50))) == ()
    assert copy_move.translate_clusters(_agreeing(copy_move.MIN_COPIES, (200, 50)))

    scattered = copy_move.translate_clusters(_scattered(400))
    assert scattered == ()


def test_pairs_that_all_agree_are_one_translation_not_many():
    """The point of the grouping: same shift, one copy-move however many pairs."""
    clusters = copy_move.translate_clusters(_agreeing(20, (200, 50)))

    assert len(clusters) == 1
    assert clusters[0].shift == pytest.approx((200.0, 50.0))
    assert len(clusters[0].matches) == 20


def test_every_match_is_far_enough_to_be_a_second_place():
    """The same structure twice over is not a copy, so a near match is refused."""
    points, descriptors = copy_move.detect(FORGED)
    matches = copy_move.self_matches(points, descriptors)

    assert matches, "the fixture must produce matches for this to be about"
    assert all(math.hypot(*m.shift) >= copy_move.MIN_SHIFT for m in matches)


def test_a_larger_minimum_shift_can_only_remove_matches():
    """The rule is a floor on the translation, so raising it narrows the set."""
    points, descriptors = copy_move.detect(FORGED)
    loose = copy_move.self_matches(points, descriptors, min_shift=1.0)
    strict = copy_move.self_matches(points, descriptors, min_shift=200.0)

    assert all(math.hypot(*m.shift) >= 200.0 for m in strict)
    assert {m.shift for m in strict} <= {m.shift for m in loose}


def test_a_frame_with_too_little_texture_to_match_is_refused():
    """A blank page carries nothing to match, and that is not a page with no copy."""
    with pytest.raises(copy_move.CopyMoveError):
        copy_move.copy_clusters(np.full((64, 64, 3), 128, np.uint8))


def test_the_map_is_one_cell_per_block():
    """A cell is the unit a match votes in, so a partial edge drops."""
    side = copy_move.BLOCK_SIZE

    assert (len(FORGED_HEATMAP), len(FORGED_HEATMAP[0])) == (HEIGHT // side, WIDTH // side)
    assert FORGED_VOTES.shape == (len(FORGED_HEATMAP), len(FORGED_HEATMAP[0]))


def test_a_frame_that_is_not_a_multiple_of_a_block_drops_its_remainder():
    """Rows of two different widths are refused by the record, so they cannot happen."""
    small = FORGED[:200, :200]
    heatmap = copy_move.copy_move_heatmap(small)
    side = copy_move.BLOCK_SIZE

    assert (len(heatmap), len(heatmap[0])) == (200 // side, 200 // side)


def test_every_cell_is_a_normalised_number():
    """The record holds numbers in [0, 1] and no pixels of the capture."""
    widths = {len(row) for row in FORGED_HEATMAP}
    cells = [cell for row in FORGED_HEATMAP for cell in row]

    assert widths == {len(FORGED_HEATMAP[0])}
    assert all(type(cell) is float for cell in cells)
    assert all(0.0 <= cell <= 1.0 for cell in cells)


def test_the_map_is_measured_against_a_committed_ceiling_not_its_own_maximum():
    """D117's rule: two captures are read on one scale and neither is stretched."""
    votes = np.array([[0.0, 2.0, 4.0]])

    assert copy_move.normalise(votes, ceiling=4.0)[0].tolist() == pytest.approx([0.0, 0.5, 1.0])
    assert copy_move.normalise(votes, ceiling=8.0)[0].tolist() == pytest.approx([0.0, 0.25, 0.5])


def test_a_block_reaches_the_heat_line_on_the_pairs_a_copy_produces():
    """The line is where the busiest block of a copy lands, not a chosen number."""
    busiest = int(FORGED_VOTES.max())
    hot = [c for c in _cells_under(_paste_box(), FORGED_HEATMAP) if c >= copy_move.HOT_LEVEL]

    assert busiest >= copy_move.SATURATION * copy_move.HOT_LEVEL
    assert hot, "the heat line must be reachable by what a copy actually produces"
    assert max(max(row) for row in FORGED_HEATMAP) == 1.0


def test_a_region_is_a_whole_pixel_polygon_readable_by_the_record():
    """Corner order, exclusivity and plain ints are all the record's terms."""
    for region in FORGED_REGIONS:
        left, top, right, bottom = _box_of(region)

        assert len(region) == 4
        assert all(type(coord) is int for corner in region for coord in corner)
        assert region == ((left, top), (right, top), (right, bottom), (left, bottom))
        assert right > left and bottom > top
        assert 0 <= left < right <= WIDTH
        assert 0 <= top < bottom <= HEIGHT


def test_a_region_is_clamped_to_the_frame_it_was_read_from():
    """A keypoint near an edge must not put a corner outside the capture."""
    frame = FORGED[:260, :260]
    regions = copy_move.copy_move_regions(frame)
    height, width = frame.shape[:2]

    assert all(
        0 <= corner[0] <= width and 0 <= corner[1] <= height
        for region in regions
        for corner in region
    )


def test_a_colour_capture_and_a_gray_one_answer_the_same_map():
    """One capture measured two ways is one measurement, not two to disagree."""
    gray = cv2.cvtColor(FORGED, cv2.COLOR_BGR2GRAY)

    assert copy_move.copy_move_heatmap(gray) == FORGED_HEATMAP
    assert copy_move.copy_move_regions(gray) == FORGED_REGIONS


def test_the_module_answers_a_record_that_names_itself():
    """D116's label fields are what stops a map reading as a finding."""
    result = copy_move.CopyMoveModule().run(_context(FORGED))

    assert result.module == copy_move.MODULE_NAME == "tamper_copy_move"
    assert result.is_stub is True
    assert result.model_version == "copy-move-v0"
    assert "tampering" in result.detail


def test_the_score_is_the_busiest_block_on_the_map():
    """One comparable scale, so 15.6's fusion reads this beside its neighbours."""
    result = copy_move.CopyMoveModule().run(_context(FORGED))

    assert result.score == max(max(row) for row in result.heatmap)
    assert result.score == pytest.approx(copy_move.HOT_LEVEL, abs=0.5)


def test_the_detail_says_repeated_content_is_not_tampering():
    """A letterhead and a forged duplicate are one finding to this measurement."""
    result = copy_move.CopyMoveModule().run(_context(FORGED))

    assert "not proof of tampering" in result.detail


def test_nothing_about_the_capture_reaches_the_record_but_numbers_and_boxes():
    """D117's rule: the record carries a map and whole pixels, never content."""
    result = copy_move.CopyMoveModule().run(_context(FORGED))
    numbers = [cell for row in result.heatmap for cell in row]

    assert all(type(cell) is float for cell in numbers)
    assert all(
        type(coord) is int for region in result.regions for corner in region for coord in corner
    )


def test_the_module_runs_through_the_registry_the_seam_holds():
    """The module constructs a D116 record behind 15.1's seam."""
    run = base.run_deep_modules(
        _context(FORGED), modules={copy_move.MODULE_NAME: copy_move.CopyMoveModule()}
    )

    assert run.ran == (copy_move.MODULE_NAME,)
    assert isinstance(run.results[0], base.DeepResult)


def test_the_module_is_shipped_and_still_not_registered():
    """15.6 is the task that fuses these, and a three-of-three registry would let
    ``ran`` claim the tier stood behind all of it before it does."""
    assert copy_move.MODULE_NAME not in base.MODULE_NAMES


@pytest.mark.parametrize(
    "argument",
    [0, -1, True, 0.0, -4.0, "8"],
)
def test_a_distance_that_is_not_a_real_number_above_zero_is_refused(argument):
    """A negative or non-numeric tolerance would bin shifts into nonsense."""
    points, descriptors = copy_move.detect(FORGED)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.self_matches(points, descriptors, min_shift=argument)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.translate_clusters(_agreeing(20, (200, 50)), tolerance=argument)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.normalise(FORGED_VOTES, ceiling=argument)


@pytest.mark.parametrize("ratio", [0.0, 1.0, -0.5, 1.5, True, "0.6"])
def test_a_ratio_outside_the_open_unit_interval_is_refused(ratio):
    """A ratio of one would keep every guess, and of zero would keep none."""
    points, descriptors = copy_move.detect(FORGED)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.self_matches(points, descriptors, ratio=ratio)


@pytest.mark.parametrize("min_copies", [0, 1, -8, True, 8.0])
def test_a_minimum_below_two_pairs_is_refused(min_copies):
    """One pair is a coincidence, and a translation needs agreement to exist."""
    with pytest.raises(copy_move.CopyMoveError):
        copy_move.translate_clusters(_agreeing(20, (200, 50)), min_copies=min_copies)


def test_a_maximum_feature_budget_that_is_not_a_whole_number_is_refused():
    """A budget of zero would search for nothing and answer it found no copy."""
    with pytest.raises(copy_move.CopyMoveError):
        copy_move.copy_clusters(FORGED, max_features=0)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.copy_clusters(FORGED, max_features=6000.0)


def test_a_frame_smaller_than_one_block_is_refused():
    """There is no whole block to vote in, and a partial one is not one."""
    small = np.zeros((4, 40, 3), np.uint8)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.vote_map(FORGED_CLUSTERS, small.shape[:2])


def test_a_frame_that_is_not_8_bit_pixels_is_refused():
    """Rescaling another dtype silently would be a measurement of another picture."""
    with pytest.raises(copy_move.CopyMoveError):
        copy_move.copy_move_heatmap(np.zeros((64, 64, 3), np.float32))

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.to_gray(None)


def test_descriptors_that_do_not_describe_the_points_are_refused():
    """A ragged matrix would index against the wrong keypoint."""
    points, descriptors = copy_move.detect(FORGED)

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.self_matches(points, descriptors[:-1])

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.self_matches(points, list(descriptors))


def test_a_cluster_of_one_pair_is_refused():
    """A cluster holds agreement, and a single pair is not it."""
    with pytest.raises(copy_move.CopyMoveError):
        copy_move.CopyCluster(shift=(200.0, 50.0), matches=_agreeing(1, (200, 50)))

    with pytest.raises(copy_move.CopyMoveError):
        copy_move.CopyMatch(source=(0.0,), copy=(1.0, 2.0), shift=(1.0, 2.0))
