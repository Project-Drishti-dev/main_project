"""27.1 -- the synthetic passport, and the loop from its own page to a parse.

The subject of this file is that the page says what the manifest says.  The
characters are read out of the drawn pixels rather than out of the text the
generator started from, and the zone is first located by the project's own
detector, so a manifest that disagreed with its own image -- or an MRZ that no
detector could find -- fails here rather than in whatever the corpus is later
measured by.  What is *not* pinned is that the generator invents nobody: the
"no real identity data" claim is a closed vocabulary, and one case holds every
value this generator can produce against the pools it draws from.
"""

import ast
import datetime
import pathlib

import numpy as np
import pytest

from app.pipeline.tier0 import document, mrz_region, td3
from tests.fixtures import document_corpus, document_images, mrz_images, passport_corpus


#: The seeds the round trip is swept over.  Three, because a seed that drew one
#: document says nothing about the next, and three because every one of them
#: draws a different name, a different number and different dates.
SEEDS = (0, 1, 2)

#: The two shapes a passport's manifest and its zone have to agree on, read out
#: of the format modules rather than written down here.
SHAPE = (td3.TD3_LINE_COUNT, td3.TD3_LINE_LENGTH)

#: Every character cell one passport's zone prints.
CELLS_PER_PAGE = SHAPE[0] * SHAPE[1]


def ink(page, box):
    """Whether ``box`` of ``page`` carries any ink at all."""
    return bool(page.image[box[1]:box[3], box[0]:box[2]].min() < document_images.PAPER_LEVEL)


def inside(outer, inner):
    """Whether the half-open box ``outer`` encloses the half-open box ``inner``."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def union_of(boxes):
    """The half-open box enclosing ``boxes``."""
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def cells_of(passport):
    """One cell count per drawn line, in the lines' own order."""
    return [len(row) for row in passport.cells]


def assigned_cells(passport):
    """Which cells the layout says each manifest field prints, read independently."""
    assigned = {}
    for number, row in enumerate(passport.cells, start=1):
        for index, box in enumerate(row):
            owner = mrz_region.cell_field(passport.format, number, index)
            assert owner is not None
            assigned.setdefault(owner[0], []).append(box)
    return assigned


def lines_from_manifest(passport):
    """The two zone lines rebuilt by concatenating the manifest in printed order."""
    lines = [""] * SHAPE[0]
    for field in passport.mrz:
        assert 1 <= field.line_number <= SHAPE[0]
        lines[field.line_number - 1] += field.value
    return tuple(lines)


def printed_date(text):
    """The day a printed date such as ``20 FEB 1968`` names."""
    return datetime.datetime.strptime(text, "%d %b %Y").date()


def module_source():
    """The drawing code's own source, for the case that reads it.

    **Not :mod:`~tests.fixtures.passport_corpus` any more, and deliberately so.**
    27.2 moved the drawing into
    :mod:`~tests.fixtures.document_corpus` so that a visa and a national ID come
    out of one generator rather than three; the passport module is now the entry
    point onto it and reads no clock and draws no randomness itself, so walking
    *its* source would pass whatever the generator underneath did.
    """
    return pathlib.Path(document_corpus.__file__).read_text(encoding="utf-8")


# --- the page is the zone the manifest says it is -------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_the_generated_page_round_trips_to_the_mrz_it_was_printed_from(seed):
    # 27.1's literal Verify.  Image first: the zone is located by 4.13 in the
    # pixels, the characters are read out of those pixels, and the parse is
    # made from the characters -- so the only thing that can make this pass is
    # a page that carries the zone its manifest describes.
    passport = passport_corpus.generate(seed)

    found = mrz_region.detect_mrz(passport.image)

    assert found.format == passport.format
    assert len(found.lines) == SHAPE[0]
    assert [len(mrz_region.segment_cells(line)) for line in found.lines] == [
        SHAPE[1]
    ] * SHAPE[0]
    assert passport_corpus.read_mrz(passport) == passport.mrz_lines

    parsed = document.parse_mrz(passport_corpus.read_mrz(passport))

    for name in ("document_number", "nationality", "date_of_birth", "sex",
                 "date_of_expiry", "issuing_state"):
        assert getattr(parsed, name) == passport_corpus.mrz_field(passport, name).value
    assert parsed.surname == passport_corpus.printed_field(passport, "surname").value


@pytest.mark.parametrize("seed", SEEDS)
def test_every_check_digit_the_zone_prints_passes(seed):
    # "A correct MRZ" is not a shape: it is the five printed digits agreeing
    # with the characters beside them, which is what the parse answers and what
    # the generator has to have got right for the corpus to mean anything.
    passport = passport_corpus.generate(seed)

    parsed = document.parse_mrz(passport_corpus.read_mrz(passport))

    assert [result.field for result in parsed.check_digit_results] == [
        field for field, _, _ in td3.TD3_CHECK_DIGIT_FIELDS
    ]
    assert [result.passed for result in parsed.check_digit_results] == [True] * 5


@pytest.mark.parametrize("seed", SEEDS)
def test_the_manifest_rebuilds_the_zone_and_owes_it_a_cell_for_every_character(seed):
    # The manifest is complete and non-overlapping: concatenated in printed
    # order it is the zone character for character, and the layout hands every
    # cell to exactly one field.
    passport = passport_corpus.generate(seed)

    assert lines_from_manifest(passport) == passport.mrz_lines

    assigned = assigned_cells(passport)
    assert sorted(assigned) == sorted(field.name for field in passport.mrz)
    assert sum(len(boxes) for boxes in assigned.values()) == CELLS_PER_PAGE
    for field in passport.mrz:
        assert field.box == union_of(assigned[field.name])


@pytest.mark.parametrize("seed", SEEDS)
def test_every_manifest_box_sits_inside_the_page_it_was_drawn_on(seed):
    passport = passport_corpus.generate(seed)

    width, height = passport.size
    for field in passport.mrz:
        left, top, right, bottom = field.box
        assert 0 <= left < right <= width
        assert 0 <= top < bottom <= height
    for field in passport.printed:
        for box in (field.label_box, field.value_box):
            left, top, right, bottom = box
            assert 0 <= left < right <= width
            assert 0 <= top < bottom <= height


def test_the_manifest_names_only_fields_the_layout_prints():
    passport = passport_corpus.generate(0)
    printed = set()
    for layout in td3.TD3.values():
        printed |= set(layout)

    assert {field.name for field in passport.mrz} == printed


def test_the_zone_is_not_the_specimen_the_other_fixtures_print():
    # The corpus must not be the ICAO example document under another name, or a
    # number measured over it would be a number measured over one document.
    specimen = tuple(mrz_images.SPECIMENS[passport_corpus.FORM])

    for seed in SEEDS:
        assert passport_corpus.generate(seed).mrz_lines != specimen


# --- the printed block and the zone are one document -----------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_the_printed_rows_and_the_zone_are_one_document(seed):
    # 27.1's manifest is ground truth for both halves of the page, so the two
    # halves have to agree: a corpus whose printed name and MRZ name disagree
    # would be a corpus of forged documents by accident.
    passport = passport_corpus.generate(seed)
    parsed = document.parse_mrz(passport_corpus.read_mrz(passport))

    assert passport_corpus.printed_field(passport, "surname").value == parsed.surname
    assert (
        passport_corpus.printed_field(passport, "given_names").value.split()
        == list(parsed.given_names)
    )
    assert (
        passport_corpus.printed_field(passport, "document_number").value
        == parsed.document_number
    )
    assert (
        passport_corpus.printed_field(passport, "nationality").value
        == parsed.nationality
    )
    assert passport_corpus.printed_field(passport, "sex").value == parsed.sex
    assert printed_date(
        passport_corpus.printed_field(passport, "date_of_birth").value
    ).strftime("%y%m%d") == parsed.date_of_birth
    assert printed_date(
        passport_corpus.printed_field(passport, "date_of_expiry").value
    ).strftime("%y%m%d") == parsed.date_of_expiry


@pytest.mark.parametrize("seed", SEEDS)
def test_every_printed_row_carries_its_own_ink(seed):
    passport = passport_corpus.generate(seed)

    for field in passport.printed:
        assert ink(passport, field.label_box)
        assert ink(passport, field.value_box)


# --- nothing here is anybody -----------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_no_value_this_generator_draws_comes_from_outside_its_own_pools(seed):
    # "No real identity data" is checkable only as a closed vocabulary: every
    # name a document can carry is one this module states, every number carries
    # the prefix that marks it generated, and every date is inside a declared
    # window.  A value from anywhere else would fail here.
    passport = passport_corpus.generate(seed)
    parsed = document.parse_mrz(passport_corpus.read_mrz(passport))

    assert parsed.surname in passport_corpus.SURNAMES
    for given in parsed.given_names:
        assert given in passport_corpus.GIVEN_NAMES
    assert parsed.nationality in passport_corpus.NATIONALITIES
    assert parsed.issuing_state in passport_corpus.ISSUING_STATES
    assert parsed.sex in passport_corpus.SEXES
    assert parsed.document_number.startswith(passport_corpus.DOCUMENT_NUMBER_PREFIX)
    assert parsed.document_number[len(passport_corpus.DOCUMENT_NUMBER_PREFIX):].isdigit()
    assert len(parsed.document_number) == (
        len(passport_corpus.DOCUMENT_NUMBER_PREFIX)
        + passport_corpus.DOCUMENT_NUMBER_DIGITS
    )
    birth = printed_date(
        passport_corpus.printed_field(passport, "date_of_birth").value
    )
    expiry = printed_date(
        passport_corpus.printed_field(passport, "date_of_expiry").value
    )
    assert birth.year in passport_corpus.BIRTH_YEARS
    assert expiry.year in passport_corpus.EXPIRY_YEARS


def test_the_generator_never_reads_the_clock():
    # A corpus whose dates move with the wall clock is a corpus that cannot be
    # reproduced, and reproducibility is the whole reason a seed is taken.  The
    # clock is banned by walking the module's own source, which is the only way
    # to catch a call made through an alias.
    tree = ast.parse(module_source())

    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert attributes.isdisjoint({"now", "today", "utcnow", "fromtimestamp"})
    randomness = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "random"
    }
    assert randomness == {"Random"}


# --- the page is the size that was asked for, or a larger one ---------------


def test_the_same_seed_draws_the_same_passport_and_a_different_one_draws_another():
    first = passport_corpus.generate(4)
    again = passport_corpus.generate(4)
    other = passport_corpus.generate(5)

    assert first.mrz_lines == again.mrz_lines
    assert first.printed == again.printed
    assert np.array_equal(first.image, again.image)
    assert first.mrz_lines != other.mrz_lines


def test_a_page_too_small_for_the_printed_rows_is_refused_rather_than_clipped():
    with pytest.raises(ValueError):
        passport_corpus.generate(0, size=(200, 120))


def test_the_page_grows_to_hold_the_strip_rather_than_clipping_it():
    # The requested page cannot hold the seven rows and the strip, so it grows
    # and the zone is still findable -- a clipped strip would be a corpus whose
    # documents cannot be read at all.
    passport = passport_corpus.generate(0, size=(700, 700))

    assert passport.size[0] > 700
    assert passport.size[1] > 700
    assert cells_of(passport) == [SHAPE[1]] * SHAPE[0]
    assert mrz_region.detect_mrz(passport.image).format == passport.format


def test_a_field_the_page_does_not_print_is_refused_by_name():
    passport = passport_corpus.generate(0)

    with pytest.raises(KeyError):
        passport_corpus.printed_field(passport, "portrait")
    with pytest.raises(KeyError):
        passport_corpus.mrz_field(passport, "portrait")