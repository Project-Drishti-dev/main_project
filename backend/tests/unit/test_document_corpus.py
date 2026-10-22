"""27.2 -- a visa and a national ID, and the loop from each page to a parse.

The subject of this file is that the three document types the generator draws
are three documents rather than one document under three labels: the detector
names each format from the pixels, the characters read back out of those pixels
are the characters the manifest holds, the parse agrees with the manifest field
by field, and every printed check digit the format prints passes.  One case runs
per document type, so a visa that stopped being a TD2 or a national ID that
stopped being three lines of thirty fails here rather than in whatever the
corpus is later measured by.  What is *not* pinned is that the generator invents
nobody: the "no real identity data" claim is a closed vocabulary, and one case
holds every value the generator can produce against the pools it draws from.
"""

import ast
import datetime
import pathlib

import numpy as np
import pytest

from app.pipeline.tier0 import document, mrz_region, td1, td2, td3
from tests.fixtures import document_corpus, document_images, mrz_images


#: The seeds the round trip is swept over.  Three, because a seed that drew one
#: document says nothing about the next, and three because every one of them
#: draws a different name, a different number and different dates.
SEEDS = (0, 1, 2)

#: Every document type the generator draws, paired with the MRZ format it
#: carries, so the cases below read as three document types rather than three
#: format names.
DOCUMENT_TYPES = tuple(document_corpus.DOCUMENT_TYPES.items())
TYPES = tuple(name for name, _ in DOCUMENT_TYPES)

#: The format modules' own printed-check-digit tables and document-code sets,
#: read out rather than restated: a format that printed a sixth digit or a
#: fourth code would change these and the cases below would follow.
CHECK_DIGIT_FIELDS = {
    "TD1": td1.TD1_CHECK_DIGIT_FIELDS,
    "TD2": td2.TD2_CHECK_DIGIT_FIELDS,
    "TD3": td3.TD3_CHECK_DIGIT_FIELDS,
}
DOCUMENT_CODES = {
    "TD1": td1.TD1_DOCUMENT_CODES,
    "TD2": td2.TD2_DOCUMENT_CODES,
    "TD3": td3.TD3_DOCUMENT_CODES,
}

#: The shape each format prints, ``(lines, characters)``, held by the table the
#: detector itself measures a zone against.
SHAPES = {name: shape for shape, name in document.MRZ_SHAPES.items()}


def shape_of(document_type):
    """The shape the detector holds for ``document_type``'s format."""
    return SHAPES[document_corpus.DOCUMENT_TYPES[document_type]]


def ink(page, box):
    """Whether ``box`` of ``page`` carries any ink at all."""
    return bool(page.image[box[1]:box[3], box[0]:box[2]].min() < document_images.PAPER_LEVEL)


def union_of(boxes):
    """The half-open box enclosing ``boxes``."""
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def cells_of(drawn):
    """One cell count per drawn line, in the lines' own order."""
    return [len(row) for row in drawn.cells]


def assigned_cells(drawn):
    """Which cells the layout says each manifest field prints, read independently."""
    assigned = {}
    for number, row in enumerate(drawn.cells, start=1):
        for index, box in enumerate(row):
            owner = mrz_region.cell_field(drawn.format, number, index)
            assert owner is not None
            assigned.setdefault(owner[0], []).append(box)
    return assigned


def lines_from_manifest(drawn):
    """The zone lines rebuilt by concatenating the manifest in printed order."""
    lines = [""] * len(drawn.cells)
    for field in drawn.mrz:
        assert 1 <= field.line_number <= len(lines)
        lines[field.line_number - 1] += field.value
    return tuple(lines)


def printed_date(text):
    """The day a printed date such as ``20 FEB 1968`` names."""
    return datetime.datetime.strptime(text, "%d %b %Y").date()


def name_of(parsed):
    """The surname and given names this project's parsers read off a record.

    A TD2 and a TD3 have their names read by their own parser; a TD1 carries its
    name on a third line that 3.6 states nothing reads yet, so the raw
    characters are read here instead.  Both spellings have to name the holder
    the printed rows do, which is what the one-document case below holds.
    """
    if parsed.surname is not None:
        return parsed.surname, list(parsed.given_names)
    surname, _, given = parsed.sources["name"].partition("<<")
    return surname, [part for part in given.split("<") if part]


def module_source():
    """The generator's own source, for the case that reads it."""
    return pathlib.Path(document_corpus.__file__).read_text(encoding="utf-8")


# --- one case per document type, and each is its own format ---------------


@pytest.mark.parametrize("document_type,format_name", DOCUMENT_TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_generated_page_round_trips_to_the_mrz_it_was_printed_from(
    document_type, format_name, seed
):
    # 27.2's literal Verify, once per document type.  Image first: the zone is
    # located in the pixels, the characters are read out of those pixels, and
    # the parse is made from the characters -- so the only thing that can make
    # this pass is a page that carries the zone its manifest describes.
    drawn = document_corpus.generate(seed, document_type=document_type)

    found = mrz_region.detect_mrz(drawn.image)

    assert drawn.format == format_name
    assert found.format == format_name
    lines, length = shape_of(document_type)
    assert len(found.lines) == lines
    assert [len(mrz_region.segment_cells(line)) for line in found.lines] == [
        length
    ] * lines
    assert document_corpus.read_mrz(drawn) == drawn.mrz_lines

    parsed = document.parse_mrz(document_corpus.read_mrz(drawn))

    assert parsed.format == format_name
    for name in ("document_number", "nationality", "date_of_birth", "sex",
                 "date_of_expiry", "issuing_state"):
        assert getattr(parsed, name) == document_corpus.mrz_field(drawn, name).value


@pytest.mark.parametrize("document_type,format_name", DOCUMENT_TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_every_check_digit_the_zone_prints_passes(document_type, format_name, seed):
    # "A correct MRZ" is not a shape: it is the printed digits agreeing with the
    # characters beside them, which is what the parse answers and what the
    # generator has to have got right for the corpus to mean anything.  The
    # count is the format module's own, so a TD1 is proved to print five digits
    # rather than to print the two fewer a TD2 prints.
    drawn = document_corpus.generate(seed, document_type=document_type)

    parsed = document.parse_mrz(document_corpus.read_mrz(drawn))

    table = CHECK_DIGIT_FIELDS[format_name]
    assert [result.field for result in parsed.check_digit_results] == [
        label for label, _, _ in table
    ]
    assert [result.passed for result in parsed.check_digit_results] == [True] * len(table)


# --- the manifest is two collections held against each other ---------------


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_manifest_rebuilds_the_zone_and_owes_it_a_cell_for_every_character(
    document_type, seed
):
    # The manifest is complete and non-overlapping: concatenated in printed
    # order it is the zone character for character, and the layout hands every
    # cell to exactly one field.
    drawn = document_corpus.generate(seed, document_type=document_type)
    lines, length = shape_of(document_type)

    assert lines_from_manifest(drawn) == drawn.mrz_lines

    assigned = assigned_cells(drawn)
    assert sorted(assigned) == sorted(field.name for field in drawn.mrz)
    assert sum(len(boxes) for boxes in assigned.values()) == lines * length
    for field in drawn.mrz:
        assert field.box == union_of(assigned[field.name])


@pytest.mark.parametrize("document_type", TYPES)
def test_the_manifest_names_only_fields_the_layout_prints(document_type):
    drawn = document_corpus.generate(0, document_type=document_type)
    printed = set()
    for layout in mrz_region.MRZ_LAYOUTS[drawn.format].values():
        printed |= set(layout)

    assert {field.name for field in drawn.mrz} == printed


@pytest.mark.parametrize("document_type", TYPES)
def test_the_zone_is_not_the_specimen_the_other_fixtures_print(document_type):
    # The corpus must not be the ICAO example document under another name, or a
    # number measured over it would be a number measured over one document.
    specimen = tuple(mrz_images.SPECIMENS[document_corpus.DOCUMENT_TYPES[document_type]])

    for seed in SEEDS:
        assert document_corpus.generate(
            seed, document_type=document_type
        ).mrz_lines != specimen


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_every_manifest_box_sits_inside_the_page_it_was_drawn_on(document_type, seed):
    drawn = document_corpus.generate(seed, document_type=document_type)

    width, height = drawn.size
    for field in drawn.mrz:
        left, top, right, bottom = field.box
        assert 0 <= left < right <= width
        assert 0 <= top < bottom <= height
    for field in drawn.printed:
        for box in (field.label_box, field.value_box):
            left, top, right, bottom = box
            assert 0 <= left < right <= width
            assert 0 <= top < bottom <= height


# --- the printed block and the zone are one document -----------------------


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_printed_rows_and_the_zone_are_one_document(document_type, seed):
    # 27.2's manifest is ground truth for both halves of the page, so the two
    # halves have to agree: a corpus whose printed number and MRZ number disagree
    # would be a corpus of forged documents by accident.
    drawn = document_corpus.generate(seed, document_type=document_type)
    parsed = document.parse_mrz(document_corpus.read_mrz(drawn))
    surname, given = name_of(parsed)

    assert surname == document_corpus.printed_field(drawn, "surname").value
    assert given == document_corpus.printed_field(drawn, "given_names").value.split()
    assert (
        document_corpus.printed_field(drawn, "document_number").value
        == parsed.document_number
    )
    assert (
        document_corpus.printed_field(drawn, "nationality").value
        == parsed.nationality
    )
    assert document_corpus.printed_field(drawn, "sex").value == parsed.sex
    assert printed_date(
        document_corpus.printed_field(drawn, "date_of_birth").value
    ).strftime("%y%m%d") == parsed.date_of_birth
    assert printed_date(
        document_corpus.printed_field(drawn, "date_of_expiry").value
    ).strftime("%y%m%d") == parsed.date_of_expiry


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_every_printed_row_carries_its_own_ink(document_type, seed):
    drawn = document_corpus.generate(seed, document_type=document_type)

    for field in drawn.printed:
        assert ink(drawn, field.label_box)
        assert ink(drawn, field.value_box)


# --- nothing here is anybody -----------------------------------------------


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_no_value_this_generator_draws_comes_from_outside_its_own_pools(
    document_type, seed
):
    # "No real identity data" is checkable only as a closed vocabulary: every
    # name a document can carry is one this module states, every number carries
    # the prefix that marks it generated, and every date is inside a declared
    # window.  A value from anywhere else would fail here.
    drawn = document_corpus.generate(seed, document_type=document_type)
    parsed = document.parse_mrz(document_corpus.read_mrz(drawn))
    surname, given = name_of(parsed)

    assert surname in document_corpus.SURNAMES
    for name in given:
        assert name in document_corpus.GIVEN_NAMES
    assert parsed.nationality in document_corpus.NATIONALITIES
    assert parsed.issuing_state in document_corpus.ISSUING_STATES
    assert parsed.sex in document_corpus.SEXES
    assert parsed.document_number.startswith(document_corpus.DOCUMENT_NUMBER_PREFIX)
    assert parsed.document_number[
        len(document_corpus.DOCUMENT_NUMBER_PREFIX):
    ].isdigit()
    assert len(parsed.document_number) == (
        len(document_corpus.DOCUMENT_NUMBER_PREFIX)
        + document_corpus.DOCUMENT_NUMBER_DIGITS
    )
    birth = printed_date(
        document_corpus.printed_field(drawn, "date_of_birth").value
    )
    expiry = printed_date(
        document_corpus.printed_field(drawn, "date_of_expiry").value
    )
    assert birth.year in document_corpus.BIRTH_YEARS
    assert expiry.year in document_corpus.EXPIRY_YEARS


def test_the_pools_the_generator_draws_from_are_the_ones_this_file_states():
    # The closed-vocabulary cases above compare every drawn value against the
    # pools the generator declares, so widening a pool in the generator would
    # widen the check with it and nobody would notice.  The pools are therefore
    # pinned here as well: every name, code and marker is one this file lists,
    # and a value added to any of them to make a case pass fails here first.
    assert document_corpus.SURNAMES == (
        "TESTHOLDER",
        "SYNTHETIC",
        "SPECIMEN",
        "GROUNDTRUTH",
        "VECTORROW",
    )
    assert document_corpus.GIVEN_NAMES == ("ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON")
    assert document_corpus.NATIONALITIES == ("UTO",)
    assert document_corpus.ISSUING_STATES == ("UTO",)
    assert document_corpus.SEXES == ("F", "M", "X")
    assert document_corpus.DOCUMENT_NUMBER_PREFIX == "SYN"
    assert document_corpus.DOCUMENT_NUMBER_DIGITS == 6


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


# --- the page is the size that was asked for, or a larger one --------------


@pytest.mark.parametrize("document_type", TYPES)
def test_the_same_seed_draws_the_same_document_and_another_seed_another(
    document_type
):
    first = document_corpus.generate(4, document_type=document_type)
    again = document_corpus.generate(4, document_type=document_type)
    other = document_corpus.generate(5, document_type=document_type)

    assert first.mrz_lines == again.mrz_lines
    assert first.printed == again.printed
    assert np.array_equal(first.image, again.image)
    assert first.mrz_lines != other.mrz_lines


@pytest.mark.parametrize("document_type", TYPES)
def test_a_page_too_small_for_the_printed_rows_is_refused_rather_than_clipped(
    document_type
):
    with pytest.raises(ValueError):
        document_corpus.generate(0, document_type=document_type, size=(200, 120))


@pytest.mark.parametrize("document_type", TYPES)
def test_the_page_grows_to_hold_the_strip_rather_than_clipping_it(document_type):
    # The requested page cannot hold the seven rows and the strip, so it grows
    # and the zone is still findable -- a clipped strip would be a corpus whose
    # documents cannot be read at all.
    drawn = document_corpus.generate(0, document_type=document_type, size=(700, 700))
    lines, length = shape_of(document_type)

    # Whichever axis the strip overflows, the page is never smaller than the one
    # asked for and the zone is drawn whole.  A TD1's strip is three short lines
    # and is narrower than this page, so only the height has to grow -- which is
    # why the claim is "grew on at least one axis" rather than "grew on both".
    assert drawn.size[0] >= 700
    assert drawn.size[1] >= 700
    assert max(drawn.size) > 700
    assert cells_of(drawn) == [length] * lines
    assert mrz_region.detect_mrz(drawn.image).format == drawn.format


@pytest.mark.parametrize("document_type", TYPES)
def test_a_field_the_page_does_not_print_is_refused_by_name(document_type):
    drawn = document_corpus.generate(0, document_type=document_type)

    with pytest.raises(KeyError):
        document_corpus.printed_field(drawn, "portrait")
    with pytest.raises(KeyError):
        document_corpus.mrz_field(drawn, "portrait")


def test_a_document_type_this_generator_does_not_draw_is_refused_by_name():
    with pytest.raises(KeyError):
        document_corpus.generate(0, document_type="residence_permit")


# --- three types, three formats, and no two of them the same document ------


def test_the_three_document_types_carry_three_different_formats():
    # "Extend the generator to visas and to national IDs" is only true if the
    # two new types are documents of their own shapes: a TD2 is two lines of 36
    # and a TD1 is three of 30, and a TD3 is two of 44.  The shapes are read
    # out of the detector's own table rather than restated here.
    assert document_corpus.DOCUMENT_TYPES == {
        "passport": "TD3",
        "visa": "TD2",
        "national_id": "TD1",
    }
    shapes = [shape_of(name) for name in TYPES]
    assert len(set(shapes)) == 3
    assert shapes == [(2, 44), (2, 36), (3, 30)]


@pytest.mark.parametrize("document_type,format_name", DOCUMENT_TYPES)
def test_each_document_prints_the_code_its_own_format_accepts(
    document_type, format_name
):
    # A visa that printed ``P<`` would be refused by its own format's reader, so
    # the code is held against the closed set the format module states rather
    # than against a string written here.
    drawn = document_corpus.generate(0, document_type=document_type)

    code = document_corpus.mrz_field(drawn, "document_code").value

    assert code in DOCUMENT_CODES[format_name]
    assert document.parse_mrz(document_corpus.read_mrz(drawn)).document_code == code


@pytest.mark.parametrize("document_type", TYPES)
def test_each_document_type_prints_its_own_number_label(document_type):
    # The three types differ on the page and not only in the zone: a passport
    # reads "Passport No", a visa "Visa No" and a national ID "ID No" over the
    # same field name, so a corpus that quietly drew three passports under
    # three names would fail here.
    drawn = document_corpus.generate(0, document_type=document_type)

    assert document_corpus.printed_field(
        drawn, "document_number"
    ).label == {
        "passport": "Passport No",
        "visa": "Visa No",
        "national_id": "ID No",
    }[document_type]
