"""27.3 -- four injected forgeries, each recording the region it changed.

The subject of this file is that an injected alteration is *measurable*: the
manifest holds one record per injection, every record carries a region, and that
region is where the injection actually put ink -- measured against the page the
same seed draws untampered rather than declared by the drawing code.  Three of
the four edit the printed block and leave the zone alone, so a tampered page is
a document whose two halves disagree while its zone still reads, which is what
27.6 will measure a detector against.  What is *not* claimed is that any of this
is caught: no detector has been run over these pages yet.
"""

import datetime

import numpy as np
import pytest

from app.pipeline.tier0 import document, mrz_region, td1, td2, td3
from tests.fixtures import document_corpus, document_images


#: The seeds the injections are swept over.  Two, because one seed's replaced
#: photo is one picture and says nothing about the next.
SEEDS = (0, 1)

#: Every document type the generator draws, paired with the format it carries,
#: so the cases below read as three document types and not three format names.
DOCUMENT_TYPES = tuple(document_corpus.DOCUMENT_TYPES.items())
TYPES = tuple(name for name, _ in DOCUMENT_TYPES)

#: How many printed check digits each format's own table holds, counted off the
#: module that states it rather than typed here.
CHECK_DIGIT_FIELDS = {
    "TD1": td1.TD1_CHECK_DIGIT_FIELDS,
    "TD2": td2.TD2_CHECK_DIGIT_FIELDS,
    "TD3": td3.TD3_CHECK_DIGIT_FIELDS,
}

#: Each tamper alone, then all four on one page.
PAIRS = tuple((kind,) for kind in document_corpus.TAMPER_KINDS) + (
    document_corpus.TAMPER_KINDS,
)
KINDS = tuple((kind,) for kind in document_corpus.TAMPER_KINDS)


def marked(drawn):
    """The pixels ``drawn`` and the untampered page of its seed disagree on."""
    plain = document_corpus.generate(
        drawn.seed, document_type=drawn.document_type, size=_size(drawn)
    )
    return np.any(drawn.image != plain.image, axis=2)


def _size(drawn):
    """The page size ``drawn`` was asked for, which is its own drawn size."""
    return drawn.size


def tight_box(mask):
    """The tight half-open box of a boolean mask."""
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    return (int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1)


def inside(outer, inner):
    """Whether the half-open box ``inner`` sits wholly inside ``outer``."""
    return (
        outer[0] <= inner[0] and outer[1] <= inner[1]
        and inner[2] <= outer[2] and inner[3] <= outer[3]
    )


def intersects(one, other):
    """Whether two half-open boxes overlap."""
    return (
        one[0] < other[2] and other[0] < one[2]
        and one[1] < other[3] and other[1] < one[3]
    )


def printed_date(text):
    """The day a printed date such as ``20 FEB 1968`` names."""
    return datetime.datetime.strptime(text, "%d %b %Y").date()


def zone_date(text):
    """The day a zone date such as ``680220`` names."""
    return datetime.datetime.strptime(text, "%y%m%d").date()


def patch(image, box):
    """The pixels of ``box`` in ``image``."""
    return image[box[1]:box[3], box[0]:box[2]]


# --- one record per injection, and a region that bounds real pixels --------


@pytest.mark.parametrize("tampers", PAIRS, ids=lambda kinds: "+".join(kinds))
@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_manifest_records_a_region_for_every_injection(tampers, document_type, seed):
    # 27.3's literal Verify.  One record per injection, each carrying a region
    # inside the page that bounds a pixel the injection really changed.  Both
    # halves are load-bearing: a region of zero area, or one bounding nothing,
    # would answer "a region for every injection" on the page's own paper.
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=tampers
    )
    differing = marked(drawn)

    assert [injection.kind for injection in drawn.tampering] == list(tampers)
    width, height = drawn.size
    for injection in drawn.tampering:
        left, top, right, bottom = injection.box
        assert 0 <= left < right <= width
        assert 0 <= top < bottom <= height
        assert differing[top:bottom, left:right].any()


@pytest.mark.parametrize("tampers", PAIRS, ids=lambda kinds: "+".join(kinds))
@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_region_is_the_box_of_the_pixels_that_one_injection_changed(
    tampers, document_type, seed
):
    # The region is measured off two draws rather than declared, so each record
    # is compared against the difference its own injection made -- the page with
    # the injections before it against the page with this one as well.
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=tampers
    )

    for index, injection in enumerate(drawn.tampering):
        before = document_corpus.generate(
            seed, document_type=document_type, tampers=tampers[:index]
        )
        after = document_corpus.generate(
            seed, document_type=document_type, tampers=tampers[:index + 1]
        )
        assert injection.box == tight_box(np.any(before.image != after.image, axis=2))


@pytest.mark.parametrize("tampers", KINDS, ids=lambda kinds: "+".join(kinds))
@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_an_injection_changes_nothing_outside_its_own_region(
    tampers, document_type, seed
):
    # An injection that repainted the page would make every region on it
    # equally true and none of them informative.  Everything the injection left
    # alone is byte for byte what the untampered page drew there.
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=tampers
    )
    differing = marked(drawn)
    covered = np.zeros(differing.shape, bool)

    for injection in drawn.tampering:
        left, top, right, bottom = injection.box
        covered[top:bottom, left:right] = True
    assert (differing <= covered).all()


# --- what each of the four is ----------------------------------------------


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_text_edit_prints_another_generated_number_over_an_untouched_zone(
    document_type, seed
):
    # The classic half of a forgery: the printed number is a different number
    # and the zone still carries the old one.  Both numbers come out of the
    # generator's own pool, so the corpus does not become a corpus of real ones.
    plain = document_corpus.generate(seed, document_type=document_type)
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=("text_edit",)
    )
    injection = document_corpus.tamper(drawn, "text_edit")
    printed = document_corpus.printed_field(drawn, "document_number")

    assert injection.field == "document_number"
    assert injection.original == document_corpus.printed_field(
        plain, "document_number"
    ).value
    assert injection.replacement == printed.value != injection.original
    assert printed.value.startswith(document_corpus.DOCUMENT_NUMBER_PREFIX)
    assert printed.value[len(document_corpus.DOCUMENT_NUMBER_PREFIX):].isdigit()
    assert printed.label == document_corpus.printed_field(
        plain, "document_number"
    ).label
    assert drawn.mrz_lines == plain.mrz_lines
    assert document_corpus.mrz_field(drawn, "document_number").value != printed.value
    assert inside(printed.value_box, injection.box)


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_birth_date_change_prints_another_day_in_the_stated_years(
    document_type, seed
):
    # A date is only a different date if it is still a day the generator draws:
    # a replacement outside the stated window would make a corpus whose forgery
    # is detectable because it is impossible rather than because it is false.
    plain = document_corpus.generate(seed, document_type=document_type)
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=("date_of_birth_change",)
    )
    injection = document_corpus.tamper(drawn, "date_of_birth_change")
    printed = document_corpus.printed_field(drawn, "date_of_birth")

    assert injection.field == "date_of_birth"
    assert injection.replacement == printed.value
    assert printed_date(injection.original) == printed_date(
        document_corpus.printed_field(plain, "date_of_birth").value
    )
    assert printed_date(injection.replacement) != printed_date(injection.original)
    assert printed_date(injection.replacement).year in document_corpus.BIRTH_YEARS
    assert printed_date(injection.replacement) != zone_date(
        document_corpus.mrz_field(drawn, "date_of_birth").value
    )


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_replaced_photo_covers_the_portrait_every_page_prints(
    document_type, seed
):
    # A replacement is only a replacement if there was something to replace, so
    # every page carries the same portrait and the injection's region lies
    # wholly inside it.  That the region can be smaller than the portrait is the
    # honest answer: the marks both pictures share are not part of the change.
    plain = document_corpus.generate(seed, document_type=document_type)
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=("photo_replacement",)
    )
    injection = document_corpus.tamper(drawn, "photo_replacement")
    box = plain.portrait

    assert drawn.portrait == box
    assert patch(plain.image, box).min() < document_images.PAPER_LEVEL
    assert np.array_equal(
        patch(plain.image, plain.portrait),
        patch(
            document_corpus.generate(seed + 9, document_type=document_type).image,
            document_corpus.generate(seed + 9, document_type=document_type).portrait,
        ),
    )
    assert not np.array_equal(patch(drawn.image, box), patch(plain.image, box))
    assert inside(box, injection.box)
    assert injection.field is None


@pytest.mark.parametrize("document_type", TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_stamp_is_inked_marks_and_no_text(document_type, seed):
    # A stamp carrying letters at a legible size would be measured as a line of
    # the zone beside it -- 4.4 measures a line by glyph height -- so a corpus
    # full of them would be a corpus whose stamps read as zones.
    plain = document_corpus.generate(seed, document_type=document_type)
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=("stamp_edit",)
    )
    injection = document_corpus.tamper(drawn, "stamp_edit")
    glyphs = mrz_region.to_gray(
        patch(drawn.image, injection.box)
    )

    assert injection.field is None
    assert patch(drawn.image, injection.box).min() < document_images.PAPER_LEVEL
    assert not np.array_equal(
        patch(drawn.image, injection.box), patch(plain.image, injection.box)
    )
    # Nothing in the stamp survives 4.4's glyph band, so it cannot be grouped
    # into a line of the zone beside it -- which is the whole reason it is inked
    # marks and no text.
    components = mrz_region.extract_components(mrz_region.binarize_inverted(glyphs))
    assert mrz_region.filter_glyphs(components) == ()


# --- the page a tampered document is still a document ----------------------


@pytest.mark.parametrize("document_type,format_name", DOCUMENT_TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_tampered_page_keeps_its_frame_and_loses_none_of_its_zone(
    document_type, format_name, seed
):
    # Four injections on one page must leave a readable document behind: same
    # frame, same cells, same zone, same passing check digits.  What changed is
    # ink inside the recorded regions and nothing else -- and the two printed
    # rows that were re-printed now disagree with the zone, which is the forgery
    # 27.6 will measure rather than a broken corpus.
    plain = document_corpus.generate(seed, document_type=document_type)
    drawn = document_corpus.generate(
        seed, document_type=document_type, tampers=document_corpus.TAMPER_KINDS
    )
    found = mrz_region.detect_mrz(drawn.image)
    parsed = document.parse_mrz(document_corpus.read_mrz(drawn))
    cells = [box for row in drawn.cells for box in row]

    assert drawn.size == plain.size
    assert drawn.cells == plain.cells
    assert drawn.portrait == plain.portrait
    assert found.format == format_name
    assert len(found.lines) == len(plain.mrz_lines)
    assert document_corpus.read_mrz(drawn) == drawn.mrz_lines
    assert [result.passed for result in parsed.check_digit_results] == [True] * len(
        CHECK_DIGIT_FIELDS[format_name]
    )
    for injection in drawn.tampering:
        assert not any(intersects(injection.box, cell) for cell in cells)
    assert (
        document_corpus.printed_field(drawn, "document_number").value
        != parsed.document_number
    )
    assert printed_date(
        document_corpus.printed_field(drawn, "date_of_birth").value
    ) != zone_date(parsed.date_of_birth)


# --- the same seed draws the same tampering -------------------------------


@pytest.mark.parametrize("document_type", TYPES)
def test_the_same_seed_injects_the_same_tampering_and_another_another(
    document_type
):
    first = document_corpus.generate(
        3, document_type=document_type, tampers=document_corpus.TAMPER_KINDS
    )
    again = document_corpus.generate(
        3, document_type=document_type, tampers=document_corpus.TAMPER_KINDS
    )
    other = document_corpus.generate(
        4, document_type=document_type, tampers=document_corpus.TAMPER_KINDS
    )

    assert first.tampering == again.tampering
    assert np.array_equal(first.image, again.image)
    assert [injection.kind for injection in other.tampering] == [
        injection.kind for injection in first.tampering
    ]


# --- what this generator refuses to do ------------------------------------


def test_a_tamper_this_generator_does_not_inject_is_refused_by_name():
    with pytest.raises(KeyError):
        document_corpus.generate(0, tampers=("signature_replacement",))


def test_the_same_tamper_asked_for_twice_is_refused():
    with pytest.raises(ValueError):
        document_corpus.generate(0, tampers=("stamp_edit", "stamp_edit"))


def test_an_injection_is_read_back_by_its_kind_and_refuses_one_it_does_not_carry():
    drawn = document_corpus.generate(0, tampers=("text_edit",))

    assert document_corpus.tamper(drawn, "text_edit").kind == "text_edit"
    with pytest.raises(KeyError):
        document_corpus.tamper(drawn, "stamp_edit")


def test_the_injections_are_the_four_this_task_names():
    # Pinned here as well as in the generator, for the reason 27.2 pinned its
    # value pools: a case that compares the manifest against the generator's own
    # table would follow the table if the table were widened.
    assert document_corpus.TAMPER_KINDS == (
        "photo_replacement",
        "text_edit",
        "date_of_birth_change",
        "stamp_edit",
    )
    assert document_corpus.TAMPER_FIELDS == {
        "text_edit": "document_number",
        "date_of_birth_change": "date_of_birth",
    }

    for kind in document_corpus.TAMPER_KINDS:
        drawn = document_corpus.generate(0, tampers=(kind,))
        injection = document_corpus.tamper(drawn, kind)
        if kind in document_corpus.TAMPER_FIELDS:
            assert injection.field == document_corpus.TAMPER_FIELDS[kind]
            assert injection.original != injection.replacement
            assert (
                document_corpus.printed_field(drawn, injection.field).value
                == injection.replacement
            )
        else:
            assert injection.field is None
            assert injection.original is None
            assert injection.replacement is None
