"""4.14 -- the generator every test in Part 4 is meant to be drawn against.

The subject of this file is not the drawing.  It is that the fixture is
*ground truth*: text goes in as a page and the same text comes back out of it.
Everything else in Part 4 has been measured against a page drawn in OpenCV's
proportional Hershey face, where the advances come out 12.4 and 13.0 pixels on
the two lines of one zone and the glyphs merge into 24 and 27 blobs -- so no
test on it can reach a named format, and no pitch read off it is the
standard's.  That fixture is what this one replaces.

The face is monospaced, every character is stamped into a cell of its own with
a fixed gap after it, and the generator hands back the box of every cell it
drew.  That is the whole of it, and it is what makes "every field has a pixel
region" checkable rather than aspirational: a box can be compared with the
characters it is supposed to cover, because the characters' own boxes are
known.
"""

import dataclasses

import numpy as np
import pytest

from app.pipeline.tier0 import document, mrz, mrz_region
from tests.fixtures import mrz_images


#: The three formats as ``(shape, name)`` pairs read out of Part 3's own table
#: rather than written down, so a shape corrected in ``document.py`` moves this
#: file with it.
FORMATS = sorted(document.MRZ_SHAPES.items())

NAMES = [name for _, name in FORMATS]

#: The whole alphabet an MRZ can print, taken from ``mrz``'s own character
#: table, so a round trip over it covers the characters the three specimens
#: between them never use.
ALPHABET = "".join(mrz.CHAR_VALUES)

#: Exposures the tests sweep, as a fraction of the page's own brightness.
GAINS = (1.0, 0.7, 0.5, 0.35)

#: One-sided shadows the tests sweep, as the fraction of the left-hand
#: brightness the right-hand edge of the frame falls to.
SHADOW_FLOORS = (1.0, 0.8, 0.6)

#: A cell above 4.4's height ceiling, which is the control the size sweep
#: needs: a page drawn too large has to come back as a page with no zone on it
#: rather than as a zone somebody happened to keep.
OVERSIZED_CELL_PX = (20, 28)


def box_of(polygon):
    """The half-open box a four-point polygon names, read by position."""
    return (
        min(point[0] for point in polygon),
        min(point[1] for point in polygon),
        max(point[0] for point in polygon),
        max(point[1] for point in polygon),
    )


def union_of(cells):
    """The half-open box several cell boxes share, read off those cells."""
    return (
        min(cell[0] for cell in cells),
        min(cell[1] for cell in cells),
        max(cell[2] for cell in cells),
        max(cell[3] for cell in cells),
    )


def holds(outer, inner):
    """Whether the half-open box ``outer`` encloses the box ``inner``."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def drawn_mask(page):
    """Where the page carries ink, read off the cells rather than the pixels."""
    mask = np.zeros(page.image.shape[:2], bool)
    for line in page.cells:
        for left, top, right, bottom in line:
            mask[top:bottom, left:right] = True
    return mask


def cells_of(found):
    """One cell count per surviving line, in the lines' own order."""
    return [len(mrz_region.segment_cells(line)) for line in found.lines]


# --- the page is what the generator said it drew -------------------------


@pytest.mark.parametrize(
    "size",
    [
        pytest.param((660, 190), id="the-zone-plus-a-little-paper"),
        pytest.param((700, 400), id="a-tall-page"),
        pytest.param((1200, 190), id="a-wide-page"),
    ],
)
def test_the_frame_is_the_size_that_was_asked_for_in_three_channels(size):
    # A generator whose frame came out the wrong shape would put every cell in
    # the wrong place, and the round trip below would then fail for a reason
    # that reads as a pipeline failure.  4.1's own claim that the frame does
    # not move also depends on a size being an input rather than an accident.
    page = mrz_images.draw_page(mrz_images.SPECIMENS["TD1"], size=size)

    assert page.image.shape == (size[1], size[0], 3)
    assert page.image.dtype == np.uint8
    assert page.size == size


@pytest.mark.parametrize("name", NAMES)
def test_every_character_gets_one_cell_and_the_cells_read_left_to_right(name):
    # The count is the half that is easy to get wrong by one: a cell per
    # character rather than per *ink run* is right for a monospaced face and
    # wrong for a proportional one, which is the whole correction.  The order
    # is the other half, and it is what 4.10's and 4.11's left-to-right claims
    # are made against.
    page = mrz_images.render_format(name)
    line_count, line_length = next(
        shape for shape, value in document.MRZ_SHAPES.items() if value == name
    )

    assert len(page.cells) == line_count
    assert all(len(line) == line_length for line in page.cells)
    assert all(len(line) == line_length for line in page.lines)
    assert all(
        cell[0] > previous[0]
        for line in page.cells
        for previous, cell in zip(line, line[1:])
    )


@pytest.mark.parametrize("name", NAMES)
def test_no_ink_falls_outside_the_cells_the_page_reports(name):
    # The claim that makes the rest of Part 4 checkable: no pixel outside a
    # reported cell carries ink.  A glyph that overflowed its box, a cell list
    # one character long, or a cell list one character short would each break
    # it, and none of them would be visible in a comparison of two page
    # images.  It is one direction only -- a cell's own padding is paper, so
    # the ink fills rather than equals the cell, and the other direction is
    # the next test's.
    page = mrz_images.render_format(name)
    ink = page.image[:, :, 0] < mrz_images.PAPER_LEVEL

    assert not (ink & ~drawn_mask(page)).any()
    assert ink.sum() == sum(
        int(
            (page.image[top:bottom, left:right, 0] < mrz_images.PAPER_LEVEL).sum()
        )
        for line in page.cells
        for left, top, right, bottom in line
    )


@pytest.mark.parametrize("name", NAMES)
def test_every_cell_carries_ink_and_the_gap_after_it_is_paper(name):
    # The other half of the same equality, said separately because it is the
    # property 4.10 cuts on: a cell of blank paper is a cell the x-projection
    # has no break to find, and 4.10's "a cell count is a lower bound" would
    # then be a statement about the fixture rather than about the cut.
    page = mrz_images.render_format(name)

    for line in page.cells:
        for left, top, right, bottom in line:
            cell = page.image[top:bottom, left:right, 0]
            gap = page.image[top:bottom, right:right + page.gap, 0]
            assert int(cell.min()) < mrz_images.PAPER_LEVEL
            assert int(gap.min()) == mrz_images.PAPER_LEVEL


@pytest.mark.parametrize("name", NAMES)
def test_each_specimen_is_the_shape_the_project_names_for_it(name):
    # The generator must not hold a second shape table.  It reads
    # ``MRZ_SHAPES`` for the shape it draws, and this asserts that against
    # Part 3's own discriminator: if a shape were corrected in one place and
    # not the other, the fixture would be drawing a zone the parser has stopped
    # reading and every test on it would be measuring a fiction.
    lines = mrz_images.SPECIMENS[name]
    page = mrz_images.render_format(name)

    assert page.format == name
    assert page.format == document.detect_mrz_format(lines)
    assert (len(lines), len(lines[0])) == next(
        shape for shape, value in document.MRZ_SHAPES.items() if value == name
    )


@pytest.mark.parametrize("name", NAMES)
def test_a_zone_that_is_not_the_shape_it_was_asked_for_is_refused(name):
    # A generator that drew 43 characters and then let the detector be blamed
    # for refusing the page is the exact mistake this replaces, so the shape
    # is checked at the door rather than left for a pipeline test to find.  A
    # plain ``ValueError`` and not ``MrzValueError``: this is a fixture handed
    # a page that is not a zone, which is not a parse failing.
    line_count, line_length = next(
        shape for shape, value in document.MRZ_SHAPES.items() if value == name
    )
    short = tuple("<" * (line_length - 1) for _ in range(line_count))

    with pytest.raises(ValueError, match="characters; got"):
        mrz_images.render_format(name, lines=short)


def test_a_format_this_project_does_not_read_is_refused_by_name():
    # The other half of the same door, and the one that would otherwise be a
    # ``StopIteration`` from a ``next()`` over three shapes: a caller naming a
    # format Part 3 has never heard of has made a mistake in the *fixture*,
    # and the message should say so.
    with pytest.raises(ValueError, match="not a format this project reads"):
        mrz_images.render_format("TD4")


def test_print_that_is_not_a_zone_is_still_drawn_and_is_named_nothing():
    # 4.13's negative control is a page of two lines of print that is *not* a
    # zone, and it has to be drawable for the generator to be usable for it.
    # ``None`` rather than a raise is what makes that possible: refusing here
    # would leave the one page the pipeline must refuse as the one page the
    # fixture cannot draw.
    page = mrz_images.draw_page(("HELLO WORLD", "NOT A ZONE AT ALL"))

    assert page.format is None
    assert len(page.cells) == 2
    assert [len(line) for line in page.cells] == [11, 17]


def test_a_zone_too_big_for_the_page_is_refused_rather_than_clipped():
    # A page that clipped its zone would read back as a zone with characters
    # missing from the end of a line, which is precisely the shape 4.7 has to
    # refuse -- so a clipped fixture would fail a pipeline test for a reason
    # that has nothing to do with the pipeline.  4.13 needs a zone that is the
    # *wrong* length, and it draws that one on purpose rather than by running
    # out of room.
    with pytest.raises(ValueError, match="does not fit a page of"):
        mrz_images.draw_page(mrz_images.SPECIMENS["TD3"], size=(400, 100))


def test_a_page_with_no_lines_on_it_is_refused_rather_than_drawn():
    # ``max()`` over nothing raises inside the size arithmetic, which would be
    # an error about a tuple rather than about the page.  The fixture is asked
    # for a page, so a page with nothing on it is a caller's mistake and says
    # so.
    with pytest.raises(ValueError, match="at least one line"):
        mrz_images.draw_page(())


def test_the_record_is_data_and_nothing_else():
    # ``MrzComponent``'s and ``MrzDetection``'s rule, applied to the fixture's
    # own record.  A method on it would be a second way of asking where a
    # character went, and it would be a way that could disagree with the
    # ``cells`` the caller is already holding.
    fields = {field.name for field in dataclasses.fields(mrz_images.MrzPage)}
    public = {
        name for name in vars(mrz_images.MrzPage) if not name.startswith("_")
    } - fields

    assert fields == {
        "image",
        "lines",
        "cells",
        "format",
        "size",
        "cell_px",
        "gap",
        "pitch",
        "leading",
        "angle_deg",
        "gain",
        "noise_sigma",
        "shadow_floor",
    }
    assert public == set()
    assert not issubclass(mrz_images.MrzPage, BaseException)
    with pytest.raises(dataclasses.FrozenInstanceError):
        mrz_images.render_format("TD3").format = "TD1"


# --- the round trip, which is the task's own verify -----------------------


@pytest.mark.parametrize("name", NAMES)
def test_the_characters_come_back_off_the_page_exactly(name):
    # The round trip: text in, image, text out.  A reader that answered the
    # right characters for the wrong reasons -- by counting cells and looking
    # them up in ``page.lines``, say -- would pass this and nothing else, so
    # the reader is given the image and the boxes the drawing reported and
    # nothing else.
    page = mrz_images.render_format(name)

    assert mrz_images.read_zone(page) == page.lines


def test_every_character_the_mrz_can_print_is_read_back_from_its_own_cell():
    # The three specimens between them use twenty-odd of the thirty-seven
    # characters an MRZ can print, so a round trip over them leaves most of the
    # alphabet untested.  This draws one line of all of it and reads it back,
    # which is the claim that the pattern table is injective: two characters
    # whose bitmaps were alike would both come back as whichever came first,
    # and only a page carrying both would say so.
    page = mrz_images.draw_page((ALPHABET,))

    assert mrz_images.read_zone(page) == (ALPHABET,)
    assert set(ALPHABET) == set(mrz.CHAR_VALUES)


@pytest.mark.parametrize("name", NAMES)
def test_the_text_that_comes_back_parses_to_the_document_the_text_was(name):
    # The round trip closed rather than reopened.  Parts 1 to 3 turn characters
    # into a document and know nothing about pixels, so this is where the two
    # halves of the project meet: a document read off a *page* has to be the
    # document the same characters parse to when they are handed over as a
    # string.  ``==`` rather than a field-by-field walk, so a field that moved
    # is a failure here and not a surprise in Part 5.
    lines = mrz_images.SPECIMENS[name]
    page = mrz_images.render_format(name)

    assert document.parse_mrz(mrz_images.read_zone(page)) == document.parse_mrz(
        lines
    )


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("cell_px", mrz_images.CELL_SIZES)
def test_the_round_trip_holds_at_every_cell_size(name, cell_px):
    # "A given size" is the first of the three knobs the task names.  Every
    # size in the sweep is a whole multiple of the 5x7 pattern in both
    # directions, so every pattern pixel is the same size and the reader's
    # resample loses nothing -- which is what makes the three sizes a sweep
    # over one face rather than three separate fixtures.
    page = mrz_images.render_format(name, cell_px=cell_px)

    assert mrz_images.read_zone(page) == page.lines


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("sigma", mrz_images.NOISE_SIGMA_LEVELS)
def test_the_round_trip_holds_at_every_noise_level(name, sigma):
    # "A noise level" is the second knob, and the answer must not depend on
    # the paper being clean: the reader thresholds halfway between a cell's
    # own darkest and brightest levels, so grain moves both ends and the
    # character is still the nearest pattern.  Ten is past what a capture
    # does -- it is sigma-10 uniform noise on every channel.
    page = mrz_images.render_format(name, noise_sigma=sigma)

    assert mrz_images.read_zone(page) == page.lines


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("gain", GAINS)
def test_the_round_trip_holds_at_every_exposure(name, gain):
    # A page photographed in low light is the same page rather than a
    # different specimen, and this is the claim that the reader reads
    # contrast and not a grey level: 0.35 puts the paper at 89 and leaves the
    # ink at 0, and the same characters come back.
    page = mrz_images.render_format(name, gain=gain)

    assert mrz_images.read_zone(page) == page.lines


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("floor", SHADOW_FLOORS)
def test_the_round_trip_holds_under_a_one_sided_shadow(name, floor):
    # The uneven case, which is the one 4.2's local cut exists for: the ink
    # stays at 0 across the whole width and the paper falls away to the right,
    # so a reader thresholding on an absolute level would lose every character
    # on the dark half.  A cell's own brightest and darkest levels are both
    # inside one cell, so a ramp across the page is invisible to it.
    page = mrz_images.render_format(name, shadow_floor=floor)

    assert mrz_images.read_zone(page) == page.lines


def test_the_grain_is_really_drawn_and_does_not_change_the_answer():
    # Both halves of a noise knob, because a sweep that only asserted the
    # answer would pass a generator that ignored the argument.  Two seeds are
    # two different images and the characters are the same off both, which is
    # the property 4.2's offset exists to buy.
    clean = mrz_images.render_format("TD3", noise_sigma=0.0)
    first = mrz_images.render_format("TD3", noise_sigma=6.0, seed=1)
    second = mrz_images.render_format("TD3", noise_sigma=6.0, seed=2)

    assert not np.array_equal(first.image, second.image)
    assert not np.array_equal(first.image, clean.image)
    assert first.lines == second.lines == clean.lines
    assert mrz_images.read_zone(first) == clean.lines
    assert mrz_images.read_zone(second) == clean.lines


# --- the chain, on a page that really is a zone --------------------------


@pytest.mark.parametrize("shape,name", FORMATS)
def test_a_generated_zone_is_named_and_has_one_cell_per_character(shape, name):
    # The claim the drawn text fixture could not make, and the one 4.13's
    # "two lines of print that are not a zone" test is written around: a
    # monospaced page of a known shape comes back named, and every one of its
    # characters comes back as a cell.  4.10's count is a lower bound because
    # a merged pair is one cell, and on a page drawn one character per cell
    # there is nothing to merge, so here the bound is met exactly.
    page = mrz_images.render_format(name)
    found = mrz_region.detect_mrz(page.image)

    assert found.format == name
    assert len(found.lines) == shape[0]
    assert cells_of(found) == [shape[1]] * shape[0]


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("angle", mrz_images.ANGLE_DEGREES)
def test_a_generated_zone_on_a_tilted_page_is_still_named(name, angle):
    # "An angle" is the third knob, and it is the one the chain is asked about
    # rather than the reader: 4.1 turns the page and 4.13 turns it back, so
    # the pixels a turned page's ground truth names are no longer the pixels
    # the chain sees.  The cell counts are the claim -- one per printed
    # character, at both signs of four degrees, on all three formats.  A page
    # that was not actually tilted would pass this with the chain doing
    # nothing, so the fixture is checked for its tilt as well.
    page = mrz_images.render_format(name, angle_deg=angle)
    found = mrz_region.detect_mrz(page.image)

    assert abs(mrz_region.skew_deg(page.image)) > abs(angle) - 0.5
    assert found.format == name
    assert cells_of(found) == [len(line) for line in page.lines]


@pytest.mark.parametrize("name", NAMES)
def test_every_field_of_a_generated_zone_has_a_box_over_its_own_characters(
    name,
):
    # Gate 4's claim, and the one a proportional face could never make: a box
    # per field, each one inside the cells that field prints and touching those
    # cells and no others.  The spans come from the layout and the cells from
    # the drawing, so this compares two independent statements about the same
    # page rather than re-deriving one from the other.
    page = mrz_images.render_format(name)
    found = mrz_region.detect_mrz(page.image)
    regions = mrz_region.field_regions(
        document.parse_mrz(mrz_images.read_zone(page)), found.lines
    )
    printed = [
        field
        for spans in mrz_region.MRZ_LAYOUTS[name].values()
        for field in spans
    ]

    assert list(regions) == printed
    for line_name, spans in mrz_region.MRZ_LAYOUTS[name].items():
        cells = page.cells[int(line_name.rsplit("_", 1)[1]) - 1]
        for field, (start, stop) in spans.items():
            box = box_of(regions[field])
            touched = [
                index
                for index, cell in enumerate(cells)
                if box[0] < cell[2] and box[2] > cell[0]
            ]
            assert holds(union_of(cells[start - 1:stop]), box)
            assert touched == list(range(start - 1, stop))


@pytest.mark.parametrize("name", NAMES)
def test_a_cell_taller_than_the_band_is_a_page_with_no_zone_on_it(name):
    # The control the size sweep needs, in both of its halves.  A page drawn
    # too large has to come back as the empty value -- a name of ``None`` with
    # no lines and no polygons -- rather than as a zone somebody happened to
    # keep, because a size sweep in which every size is accepted measures
    # nothing about the band.  And the refusal is arithmetic rather than a
    # threshold this file guessed: every character in the pattern table draws
    # the full height of its cell, so 4.4 sees 28 where its ceiling is 24.
    page = mrz_images.render_format(name, cell_px=OVERSIZED_CELL_PX)
    found = mrz_region.detect_mrz(page.image)

    assert page.cell_px[1] > mrz_region.GLYPH_MAX_HEIGHT_PX
    assert found == mrz_region.MrzDetection()
    assert found.format is None
    assert found.lines == ()
    assert found.regions == ()


def test_every_character_draws_the_whole_height_of_its_cell():
    # What makes the control above an arithmetic claim rather than a
    # measurement: 4.4's height band is written against a pixel height, and
    # the only pixel height this face has is the cell's own.  A glyph sitting
    # in the top two thirds of its cell would make the band see a different
    # number at every cell size, and the size sweep would then be comparing
    # three fixtures rather than three sizes of one face.
    heights = set()
    aspects = []
    for character in ALPHABET:
        page = mrz_images.draw_page(
            (character,), cell_px=mrz_images.DEFAULT_CELL_PX
        )
        components = mrz_region.extract_components(
            mrz_region.binarize_inverted(mrz_region.to_gray(page.image))
        )

        assert len(components) == 1
        heights.add(components[0].height)
        aspects.append(components[0].width / components[0].height)

    assert heights == {mrz_images.DEFAULT_CELL_PX[1]}
    assert min(aspects) >= mrz_region.GLYPH_MIN_ASPECT
    assert max(aspects) <= mrz_region.GLYPH_MAX_ASPECT


def test_the_line_polygons_sit_inside_the_cells_they_were_cut_from():
    # One measurement that keeps the ground truth and the pixels together, and
    # it is what the field-box test leans on: 4.8's polygon is a box of the
    # ink, so it must sit inside the cells that line printed and must reach
    # both ends of them.  Without the second half a box drawn in the wrong
    # place inside the zone would pass.
    page = mrz_images.render_format("TD3")
    found = mrz_region.detect_mrz(page.image)

    assert len(found.regions) == len(page.lines)
    for number, polygon in enumerate(found.regions):
        cells = page.cells[number]
        box = box_of(polygon)

        assert holds(union_of(cells), box)
        assert box[0] < cells[0][2]
        assert box[2] > cells[-1][0]


# --- what the generator is here to measure for the rest of the part ------


@pytest.mark.parametrize("name", NAMES)
def test_the_gap_between_cells_is_what_survives_a_turn(name):
    # 4.10 cuts on a break in the x-projection, and a turned page is
    # resampled twice -- once to lean it and once to bring it back -- so the
    # gap is the fixture's own claim about how much paper 4.10 needs.  This is
    # the sweep behind :data:`mrz_images.GAP_PX`, and the interesting number
    # is where it stops working rather than a threshold: a gap of 1 merges a
    # zone into a fifth to a half as many blobs, 2 is exact on TD1 and TD2 and
    # loses one glyph on a TD3 turned anticlockwise, and 3 is the first gap
    # exact on all three at both signs of 4 degrees.
    line_length = len(mrz_images.SPECIMENS[name][0])
    measured = {
        gap: [
            mrz_region.detect_mrz(
                mrz_images.render_format(name, gap=gap, angle_deg=angle).image
            )
            for angle in (4.0, -4.0)
        ]
        for gap in (1, 2, 3, 4)
    }

    assert measured[1][0].format is None, "a one-pixel gap is not a page of cells"
    for gap in (3, 4):
        for found in measured[gap]:
            assert found.format == name
            assert cells_of(found) == [line_length] * len(found.lines)


@pytest.mark.parametrize("name", NAMES)
def test_a_zone_under_a_shadow_the_quality_gate_still_finds_is_named(name):
    # The uneven-page case measured rather than preferred.  Its boundary is
    # below :data:`SHADOW_FLOORS`: at a floor of 0.5 the paper on the right of
    # the frame is at 128, and on a page this wide ``m7_skew``'s scan
    # estimator no longer finds the text rows, so 4.1 is handed an angle that
    # is an artefact of its own search rather than a measurement of the page.
    # That limit belongs to ``m7_skew`` and not to the generator, so it is
    # written down in the handover rather than pinned here, and this is the
    # range the generator guarantees.
    for floor in SHADOW_FLOORS:
        page = mrz_images.render_format(name, shadow_floor=floor)
        found = mrz_region.detect_mrz(page.image)

        assert found.format == name
        assert cells_of(found) == [len(line) for line in page.lines]
