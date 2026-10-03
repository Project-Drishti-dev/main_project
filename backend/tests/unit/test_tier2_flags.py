"""15.13 -- a Tier 2 result becomes a flag, and the flag says where.

The claim pinned first is the verification the task names: a flag built from a
page with one region re-encoded by a second codec carries a non-null region,
and that region is the re-encoded one rather than the page beside it.  The rest
holds that a region a module located itself beats a box derived from its own
map, that a result which is one number for the whole page still becomes a flag
with no region rather than being dropped, and that a frame too small to have
been drawn on is refused rather than answered as a clean page.

**The level a region is drawn at is each module own constant, not a number
chosen here.**  The tests below read those levels back out of the modules, so a
module retuning its own line cannot leave this table answering for it.

**Nothing here decides that a result is a finding**, and D125 records why that
question is not this task: measured against a clean printed page written at
JPEG 95, ELA reads 1.0000 with 53.9% of blocks at or above its own line, and
100% of them once grain was added, so a gate at the module own level fires on
an ordinary clean page.
"""

import dataclasses
import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, copy_move, ela, flags, noise_residual
from app.risk import flag_ids
from app.risk.flags import MIN_REGION_CORNERS, WEIGHT_BANDS

SCREENING_ID = uuid.UUID("5b7c9d21-0f4a-4e6b-8a3d-2c1f0e9d8b7a")
WIDTH, HEIGHT = 256, 192
#: The one region a second codec rewrote, and the quality it was written at
#: against the 95 the page itself was saved at.  The gap between them is the
#: double compression being looked for.
EDITED_BOX = (96, 56, 48, 48)
PAGE_QUALITY = 95
PATCH_QUALITY = 30
BOX = ((10, 20), (60, 20), (60, 70), (10, 70))


def _jpeg(frame, quality):
    """Return `frame` as a codec wrote it and read it back."""
    encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert encoded, "the test own JPEG encoder refused its frame"
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
    rng = np.random.default_rng(20261002)
    patch = np.full((height, width, 3), 235, np.uint8)
    for row in range(height // 6 + 1):
        cv2.putText(
            patch, "MRZ", (2, 6 + row * 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (15, 15, 15), 1, cv2.LINE_AA,
        )
    grain = rng.integers(-30, 31, size=(height, width, 1)).astype(np.int16)
    return np.clip(patch.astype(np.int16) + grain, 0, 255).astype(np.uint8)


def _capture():
    """A page carrying one region a second codec rewrote, and nothing else."""
    page = _smooth_page()
    left, top, width, height = EDITED_BOX
    page[top : top + height, left : left + width] = _jpeg(
        _printed_patch(height, width), PATCH_QUALITY
    )
    return _jpeg(page, PAGE_QUALITY)


def _context(image):
    """A context carrying what the seam hands a module and nothing else."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _heatmap(rows):
    """Return `rows` as the map a module would hand over."""
    return tuple(tuple(float(cell) for cell in row) for row in rows)


def _hot_at(row, column, rows=3, columns=5):
    """Return a map whose only hot cell sits at `row`, `column`."""
    cells = [[0.0] * columns for _ in range(rows)]
    cells[row][column] = 1.0
    return _heatmap(cells)


def _ela_result(**changes):
    """Return an ELA record, so a test changes one field and reads one answer."""
    defaults = dict(
        module=ela.MODULE_NAME,
        score=1.0,
        is_stub=True,
        model_version=ela.MODEL_VERSION,
        detail="ELA read the capture and this is re-compression, not tampering.",
        heatmap=_hot_at(1, 2),
    )
    defaults.update(changes)
    return base.DeepResult(**defaults)


def _box_holds(outer, inner):
    """Whether every corner of `inner` sits inside `outer` pixel to pixel."""
    left, top, width, height = outer
    right, bottom = left + width, top + height
    return all(
        left <= x <= right and top <= y <= bottom for x, y in inner
    )


def _share_of_page(box, shape):
    """The share of the whole frame `box` covers, as a fraction."""
    height, width = shape
    left, top = box[0]
    return ((box[2][0] - left) * (box[2][1] - top)) / float(width * height)


class TestTheTaskVerification:
    """A tampered region, and the flag that has to point at it."""

    def test_a_tampered_region_flag_carries_a_non_null_region(self):
        """The claim this task names: a region and a place to look at it."""
        page = _capture()

        flag = flags.flag_from_result(
            ela.ELAModule().run(_context(page)), shape=page.shape[:2]
        )

        assert flag.region is not None

    def test_that_region_is_the_region_that_was_rewritten(self):
        """A box over the whole page would satisfy the claim and be useless.

        Measured on this capture, the group of hot blocks holding the peak is
        the two leftmost block columns of the rewritten patch, so the box is
        16px of a 48px one and sits wholly inside it.  **The claim is
        containment and locality, not half the patch**: the map reads hottest
        where the second codec rewrote the most, and a weaker half-overlap
        threshold here would be a number this fixture never produced.
        """
        page = _capture()

        flag = flags.flag_from_result(
            ela.ELAModule().run(_context(page)), shape=page.shape[:2]
        )

        assert _box_holds(EDITED_BOX, flag.region)
        assert _share_of_page(flag.region, page.shape[:2]) < 0.25

    def test_that_region_is_a_polygon_of_plain_whole_pixels(self):
        """The shape an officer highlight is drawn over, and JSON carries."""
        page = _capture()

        flag = flags.flag_from_result(
            ela.ELAModule().run(_context(page)), shape=page.shape[:2]
        )

        assert len(flag.region) >= MIN_REGION_CORNERS
        assert all(type(value) is int for corner in flag.region for value in corner)

    def test_that_region_is_inside_the_frame_it_was_handed(self):
        """A box past the edge would be drawn over nothing at all."""
        page = _capture()

        flag = flags.flag_from_result(
            ela.ELAModule().run(_context(page)), shape=page.shape[:2]
        )

        height, width = page.shape[:2]
        assert all(0 <= x <= width for x, _ in flag.region)
        assert all(0 <= y <= height for _, y in flag.region)

    def test_the_same_capture_answers_the_same_region_twice_over(self):
        """A tie on the map must not make the highlight jump between runs."""
        page = _capture()
        module = ela.ELAModule()

        first = flags.flag_from_result(module.run(_context(page)), shape=page.shape[:2])
        second = flags.flag_from_result(module.run(_context(page)), shape=page.shape[:2])

        assert first.region == second.region


class TestTheFlagCarriesTheModuleAnswer:
    """What the module said travels across, and nothing is re-decided here."""

    def test_the_id_is_the_one_the_module_is_registered_under(self):
        """A flag reported under another module own id cannot be traced back."""
        flag = flags.flag_from_result(_ela_result(), shape=(HEIGHT, WIDTH))

        assert flag.id == flag_ids.TAMPER_ELA_ANOMALY

    def test_the_score_is_carried_as_both_of_the_numbers(self):
        """One module measured one number, so neither column estimates a second."""
        flag = flags.flag_from_result(_ela_result(score=0.75), shape=(HEIGHT, WIDTH))

        assert flag.value == 0.75
        assert flag.confidence == 0.75

    def test_the_modules_own_sentence_is_the_reason(self):
        """It is where the stand-in label travels, as there is no field for it."""
        result = _ela_result(is_stub=True)

        flag = flags.flag_from_result(result, shape=(HEIGHT, WIDTH))

        assert flag.reason == result.detail
        assert flag.source_module == "app.pipeline.tier2.ela"

    def test_the_flag_reports_tier_two_and_no_field(self):
        """A Tier 2 finding is about the capture, never about one printed field."""
        flag = flags.flag_from_result(_ela_result(), shape=(HEIGHT, WIDTH))

        assert flag.tier == 2
        assert flag.field is None
        assert flag.expected is None
        assert flag.found is None

    def test_every_rule_names_an_id_the_registry_holds(self):
        """15.14 asks a run to be checked; this is what it will be checked against."""
        assert flags.RULES
        assert all(rule.flag_id in flag_ids.FLAG_IDS for rule in flags.RULES)
        assert all(rule.weight_band in WEIGHT_BANDS for rule in flags.RULES)
        assert all(rule.label.strip() and rule.source_module.strip() for rule in flags.RULES)

    def test_every_rule_is_reachable_under_the_name_a_result_carries(self):
        """A module with no rule has nowhere to report and is refused instead."""
        assert set(flags.RULE_BY_MODULE) == {rule.module for rule in flags.RULES}

    def test_the_registry_cannot_be_widened_after_import(self):
        """A caller that added a rule would report under an id no weightset holds."""
        with pytest.raises(TypeError):
            flags.RULE_BY_MODULE["tamper_anything"] = flags.RULES[0]

    def test_a_result_from_a_module_with_no_rule_is_refused(self):
        """Silently dropping it would read as a module that found nothing."""
        result = dataclasses.replace(_ela_result(), module="tamper_anything")

        with pytest.raises(flags.Tier2FlagError):
            flags.flag_from_result(result, shape=(HEIGHT, WIDTH))


class TestWhereTheRegionComesFrom:
    """Five shapes, one rule: the strongest place the record can name."""

    def test_a_box_the_module_located_beats_one_derived_from_its_map(self):
        """It measured the place; the map only knows which block went hot."""
        result = _ela_result(regions=(BOX,), heatmap=_hot_at(0, 0))

        assert flags.region_from_result(result, (HEIGHT, WIDTH)) == BOX

    def test_the_first_of_several_boxes_is_the_one_reported(self):
        """The modules that carry both order their groups as they found them."""
        second = ((0, 0), (8, 0), (8, 8), (0, 8))
        result = _ela_result(regions=(BOX, second), heatmap=_hot_at(0, 0))

        assert flags.region_from_result(result, (HEIGHT, WIDTH)) == BOX

    def test_a_result_with_neither_a_map_nor_a_box_locates_nothing(self):
        """One number for the whole page is a finding with nowhere to point."""
        result = _ela_result(heatmap=())

        assert flags.region_from_result(result, (HEIGHT, WIDTH)) is None

    def test_such_a_result_is_still_a_flag_and_not_a_dropped_one(self):
        """The same rule 4.12 gave Tier 0: no box is not no finding."""
        flag = flags.flag_from_result(_ela_result(heatmap=()), shape=(HEIGHT, WIDTH))

        assert flag.region is None
        assert flag.id == flag_ids.TAMPER_ELA_ANOMALY

    def test_the_box_is_the_group_of_hot_cells_holding_the_map_peak(self):
        """One tampered area is one box, rather than one box per block of it."""
        cells = [[0.0] * 5 for _ in range(3)]
        for column in (1, 2, 3):
            cells[1][column] = 1.0
        result = _ela_result(heatmap=_heatmap(cells))

        box = flags.region_from_result(result, (30, 50))

        assert box == ((10, 10), (40, 10), (40, 20), (10, 20))

    def test_a_cold_map_locates_nothing_rather_than_the_whole_frame(self):
        """A box over every pixel would claim a measurement nobody made."""
        result = _ela_result(heatmap=_heatmap([[0.0] * 8 for _ in range(6)]))

        assert flags.region_from_result(result, (HEIGHT, WIDTH)) is None

    def test_a_map_with_one_hot_cell_still_locates_that_cell(self):
        """A single hot block is a place, and the map is not all-or-nothing."""
        result = _ela_result(heatmap=_hot_at(1, 2, rows=6, columns=8))

        assert flags.region_from_result(result, (HEIGHT, WIDTH)) == (
            (64, 32),
            (96, 32),
            (96, 64),
            (64, 64),
        )

    def test_a_callers_own_registry_draws_the_box_at_its_own_line(self):
        """The rule table is a seam, not a line copied into a test."""
        cells = [[0.0] * 3 for _ in range(2)]
        cells[1][1] = 1.0
        cells[1][2] = 0.4
        result = _ela_result(heatmap=_heatmap(cells))
        doctored = dict(flags.RULE_BY_MODULE)
        doctored[ela.MODULE_NAME] = dataclasses.replace(
            flags.RULE_BY_MODULE[ela.MODULE_NAME], level=0.3
        )

        shipped = flags.region_from_result(result, (20, 30))
        lowered = flags.region_from_result(result, (20, 30), registry=doctored)

        assert shipped == ((10, 10), (20, 10), (20, 20), (10, 20))
        assert lowered == ((10, 10), (30, 10), (30, 20), (10, 20))

    def test_a_tie_on_the_map_keeps_the_first_cell_in_image_order(self):
        """Two peaks equal must still draw one highlight in one place."""
        cells = [[0.0] * 3 for _ in range(2)]
        cells[0][0] = 1.0
        cells[1][2] = 1.0
        result = _ela_result(heatmap=_heatmap(cells))

        box = flags.region_from_result(result, (20, 30))

        assert box == ((0, 0), (10, 0), (10, 10), (0, 10))

    def test_a_frame_that_is_not_a_whole_number_of_blocks_still_answers(self):
        """Maps are cropped to whole blocks, so the grid need not divide the frame."""
        result = _ela_result(heatmap=_hot_at(1, 2))

        for frame in ((16, 16), (17, 19), (23, 41)):
            height, width = frame
            box = flags.region_from_result(result, frame)

            assert all(0 <= x <= width for x, _ in box)
            assert all(0 <= y <= height for _, y in box)

    def test_a_map_is_stretched_across_the_whole_frame_it_was_handed(self):
        """A box that stopped at the last whole block would leave the edge out."""
        result = _ela_result(heatmap=_hot_at(0, 4))

        box = flags.region_from_result(result, (10, 10))

        assert box[1][0] == 10


class TestWhatIsRefused:
    """A record or a frame that cannot be measured is not answered at all."""

    def test_a_record_that_is_not_a_deep_result_is_refused(self):
        """Duck-typed answers would skip every check the seam makes."""
        with pytest.raises(flags.Tier2FlagError):
            flags.flag_from_result(object(), shape=(HEIGHT, WIDTH))

        with pytest.raises(flags.Tier2FlagError):
            flags.region_from_result(object(), (HEIGHT, WIDTH))

    def test_a_run_that_is_not_a_deep_run_is_refused(self):
        """An empty answer and an absent run are two different things."""
        with pytest.raises(flags.Tier2FlagError):
            flags.flags_from_run((), shape=(HEIGHT, WIDTH))

    def test_a_frame_that_is_not_a_height_and_width_pair_is_refused(self):
        """The map cannot be stretched across a shape it was never handed."""
        for shape in ((HEIGHT,), (HEIGHT, WIDTH, 3), "256x192", (HEIGHT, float(WIDTH))):
            with pytest.raises(flags.Tier2FlagError):
                flags.region_from_result(_ela_result(), shape)

    def test_a_frame_holding_no_pixels_is_refused(self):
        """A zero-wide frame has no box in it to point at."""
        for shape in ((0, WIDTH), (HEIGHT, 0), (-1, WIDTH)):
            with pytest.raises(flags.Tier2FlagError):
                flags.region_from_result(_ela_result(), shape)

    def test_a_level_outside_the_unit_interval_is_refused(self):
        """A line above every cell would report the map as carrying nothing."""
        doctored = dict(flags.RULE_BY_MODULE)
        doctored[ela.MODULE_NAME] = dataclasses.replace(
            flags.RULE_BY_MODULE[ela.MODULE_NAME], level=1.4
        )
        result = _ela_result(heatmap=_hot_at(1, 2))

        with pytest.raises(flags.Tier2FlagError):
            flags.region_from_result(result, (HEIGHT, WIDTH), registry=doctored)


class TestARunOfResults:
    """What a whole Tier 2 run becomes, in the order it answered."""

    def test_every_result_becomes_one_flag_in_the_order_they_arrived(self):
        """A run reports what ran, and a caller reads a row beside its name."""
        page = _capture()
        modules = (ela.ELAModule(), noise_residual.NoiseResidualModule())
        run = base.DeepRun(
            ran=tuple(module.name for module in modules),
            results=tuple(module.run(_context(page)) for module in modules),
        )

        built = flags.flags_from_run(run, shape=page.shape[:2])

        assert len(built) == len(run.results)
        assert [flag.id for flag in built] == [
            flag_ids.TAMPER_ELA_ANOMALY,
            flag_ids.TAMPER_NOISE_RESIDUAL_ANOMALY,
        ]

    def test_a_result_that_located_nothing_still_takes_its_row(self):
        """Dropping it would make a module that found nothing read as absent."""
        run = base.DeepRun(
            ran=(ela.MODULE_NAME,),
            results=(_ela_result(heatmap=()),),
        )

        built = flags.flags_from_run(run, shape=(HEIGHT, WIDTH))

        assert len(built) == 1
        assert built[0].region is None

    def test_an_empty_run_answers_an_empty_tuple(self):
        """No deep module configured is a visible absence, not a clean page."""
        assert flags.flags_from_run(base.DeepRun(ran=(), results=()), shape=(HEIGHT, WIDTH)) == ()

    def test_a_run_answered_by_the_registry_converts_the_same_way(self):
        """The seam own runner is what a caller reaches for first."""
        page = _capture()
        modules = {ela.MODULE_NAME: ela.ELAModule()}

        run = base.run_deep_modules(_context(page), modules=modules)
        built = flags.flags_from_run(run, shape=page.shape[:2])

        assert len(built) == len(run.results)
        assert built[0].region is not None


class TestTheModulesOwnLevels:
    """The line a region is drawn at is read, not chosen."""

    def test_each_rule_reads_its_own_module_level(self):
        """A table holding its own copy of a level can drift from the module."""
        assert flags.RULE_BY_MODULE[ela.MODULE_NAME].level == ela.HOT_LEVEL
        assert (
            flags.RULE_BY_MODULE[noise_residual.MODULE_NAME].level
            == noise_residual.HOT_LEVEL
        )
        assert (
            flags.RULE_BY_MODULE[copy_move.MODULE_NAME].level == copy_move.HOT_LEVEL
        )
