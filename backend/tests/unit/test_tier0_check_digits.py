"""6.2 -- a failing printed check digit, one flag, carrying its own box.

`tasks.md` asks for two things: one flag per failing field, and each of them
carrying that field's region from Part 4.  What is pinned here is the
mapping from a :class:`~app.pipeline.tier0.mrz.CheckDigitResult` to an
:class:`~app.risk.flags.EvidenceFlag`, the box each one lands on, and the two
things that are *not* findings.

**The arithmetic is Part 1's and is not redone here.**  The pages are drawn
with one character mutated and read back through
:func:`~tests.fixtures.mrz_images.read_zone`, so a test asks the seam a
question about a document rather than asserting digits this file typed.

**``passed is None`` is the case this whole task could get wrong.**  A TD1
prints filler where an unused optional data field's digit would be, so a
perfectly honest specimen hands the rules engine a ``None`` on one of its five
rows.  A rule that fired on the third answer would invent a mismatch on every
identity card this project reads, so there are tests that it does not.

**The box is 4.12's own, compared rather than asserted.**  Each region is held
against :func:`~app.pipeline.tier0.mrz_region.field_regions` and against the
cell the fixture drew, so a highlight that moved would fail here rather than
reach Part 23.

**This module and its name carry ``check_digit``; ``runner.py`` does not read
the clock**, and the last test walks the runner's AST rather than trusting
this paragraph.
"""

import ast
import datetime
import pathlib

import pytest

from app.pipeline.tier0 import document, mrz_region, runner, td1, td2, td3
from app.pipeline.tier0.mrz import MrzValueError
from app.risk import flag_ids
from tests.fixtures import mrz_images

run_tier0 = runner.run_tier0

#: The three layouts, by the name Part 3 dispatches on, so a field's position
#: is read out of the table rather than counted out longhand in this file.
LAYOUTS = {"TD1": td1.TD1, "TD2": td2.TD2, "TD3": td3.TD3}

#: The three formats, as ``(name, line count)`` pairs read out of Part 3's own
#: table rather than written down here.
FORMATS = sorted(document.MRZ_SHAPES.values())

#: The reference 5.8's own suite measures against.  No rule in tier 0 reads a
#: day; the value is here so the argument can be shown being passed through
#: unchanged beside a finding.
REFERENCE = datetime.date(2026, 9, 30)


def zone_with(name, line_number, position, character):
    """The specimen of ``name`` with one printed character replaced.

    ``line_number`` is 1-based because that is how the layouts key themselves,
    and ``position`` is 1-based within the line for the same reason.
    """
    zone = list(mrz_images.SPECIMENS[name])
    line = zone[line_number - 1]
    assert line[position - 1] != character, "the mutation must change something"
    zone[line_number - 1] = line[: position - 1] + character + line[position:]
    return tuple(zone)


def parsed_page(name, zone):
    """A drawn page, the parse the caller would hand over, and the detection.

    **The zone is read back off the pixels before it is parsed**, so the
    document under test is the one the frame holds rather than the one this
    file typed: :func:`~tests.fixtures.mrz_images.read_zone` is the fixture's
    own reader, and the assertion is what stops a test passing on a page that
    was never drawn the way it claims.
    """
    page = mrz_images.render_format(name, lines=zone)
    read = mrz_images.read_zone(page)
    assert read == tuple(zone)
    return page, document.parse_mrz(read)


def printed_at(name, field):
    """The ``(line number, position)`` of ``field`` in ``name``'s layout.

    **Read out of the layout rather than counted**, because a position typed
    longhand here is a second copy of the table the pipeline already holds: a
    TD1's composite digit is on its second line and not its last, which is
    exactly the kind of thing a copied position gets wrong.
    """
    for line_name, fields in LAYOUTS[name].items():
        if field in fields:
            return int(line_name.rsplit("_", 1)[1]), fields[field][0]
    raise KeyError(f"{name} prints no field called {field}")


def cell_of(page, name, field):
    """The fixture's own cell box for ``field`` in ``name``'s layout."""
    line_number, position = printed_at(name, field)
    return page.cells[line_number - 1][position - 1]


def holds(outer, inner):
    """Whether the half-open box ``outer`` encloses the box ``inner``."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


# --- the named behaviour: a mutated composite ------------------------------


@pytest.mark.parametrize("name", FORMATS)
def test_a_mutated_composite_names_the_failing_field_and_locates_it(name):
    """`tasks.md` 6.2's own verify, on each of the three formats.

    **The printed digit is what is mutated**, not one of the characters it
    covers, and that is the only way to fail the composite alone.  Every
    character inside a composite span also sits inside some other printed
    digit's field -- on a TD3 the spans are 1-10, 14-20 and 22-43, and those
    are exactly the document number, the date of birth and the expiry plus
    the personal number -- so changing a character would report the other
    digit as failing too.  The composite's own digit is at a position no other
    digit is computed over, which is what makes one flag here one flag.
    """
    line_number, digit = printed_at(name, "composite_check_digit")
    zone = zone_with(name, line_number, digit, "0")

    page, parsed = parsed_page(name, zone)
    result = run_tier0(page.image, parsed_document=parsed)

    assert [flag.id for flag in result.flags] == [
        flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH
    ]
    assert result.flags[0].field == "composite"
    assert result.flags[0].region is not None


@pytest.mark.parametrize("name", FORMATS)
def test_the_region_is_part_4_s_own_box_over_that_digit_s_own_cell(name):
    """4.12's value handed over, and the fixture's cell is inside it."""
    line_number, digit = printed_at(name, "composite_check_digit")
    zone = zone_with(name, line_number, digit, "0")

    page, parsed = parsed_page(name, zone)
    detection = mrz_region.detect_mrz(page.image)
    result = run_tier0(page.image, parsed_document=parsed)

    assert result.flags[0].region == mrz_region.field_regions(
        parsed, detection.lines
    )["composite_check_digit"]
    box = result.flags[0].region
    assert len(box) == 4
    assert holds(
        (box[0][0], box[0][1], box[2][0], box[2][1]),
        cell_of(page, name, "composite_check_digit"),
    )


def test_a_td2_name_change_fails_the_composite_and_nothing_else():
    """The composite covers a field no other printed digit does.

    A TD2's line 1 carries no check digit at all and its name is inside the
    composite span, so this is the one substitution that only the composite
    can catch -- 2.14's blind spot, with the digits rather than the claim.
    """
    zone = zone_with("TD2", 1, 6, "X")

    page, parsed = parsed_page("TD2", zone)
    result = run_tier0(page.image, parsed_document=parsed)

    assert [flag.field for flag in result.flags] == ["composite"]
    assert result.flags[0].region is not None


# --- one flag per failing field, each with its own id and its own box ------


def test_two_failing_fields_are_two_flags_and_not_one_merged_finding():
    """A personal-number character is under two printed digits."""
    zone = zone_with("TD3", 2, 29, "A")

    page, parsed = parsed_page("TD3", zone)
    result = run_tier0(page.image, parsed_document=parsed)

    assert [(flag.id, flag.field) for flag in result.flags] == [
        (flag_ids.MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH, "personal_number"),
        (flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH, "composite"),
    ]
    assert [flag.region for flag in result.flags] == [
        region
        for region in (
            mrz_region.field_regions(
                parsed, mrz_region.detect_mrz(page.image).lines
            )[name]
            for name in ("personal_number_check_digit", "composite_check_digit")
        )
    ]
    assert all(flag.region is not None for flag in result.flags)


@pytest.mark.parametrize("name", FORMATS)
def test_a_clean_specimen_reports_nothing(name):
    """Every row passing, or unreadable, is silence."""
    page, parsed = parsed_page(name, mrz_images.SPECIMENS[name])

    result = run_tier0(page.image, parsed_document=parsed)

    assert result.flags == ()
    assert result.hard_failed is False


def test_a_row_that_could_not_be_read_is_not_a_mismatch():
    """2.14's third answer, kept: a TD1's unused optional data is ``None``.

    **This is the case that would fire on every identity card** if the
    conversion treated "not checked" as "failed", and the specimen is a
    perfectly honest one, so the assertion is on a real parse rather than a
    hand-built record.
    """
    page, parsed = parsed_page("TD1", mrz_images.SPECIMENS["TD1"])

    unreadable = [
        result
        for result in parsed.check_digit_results
        if result.passed is None
    ]
    result = run_tier0(page.image, parsed_document=parsed)

    assert [entry.field for entry in unreadable] == ["optional_data_1"]
    assert unreadable[0].expected is None
    assert result.flags == ()


# --- what the flag carries -------------------------------------------------


def test_a_finding_carries_both_digits_and_the_field_it_is_about():
    """The abstract's "expected 4, found 7" shape, read off the parse."""
    zone = zone_with("TD3", 2, 44, "0")

    page, parsed = parsed_page("TD3", zone)
    verdict = next(
        entry for entry in parsed.check_digit_results if entry.field == "composite"
    )
    flag = run_tier0(page.image, parsed_document=parsed).flags[0]

    assert flag.expected == str(verdict.expected) == "0"
    assert flag.found == str(verdict.found) == "6"
    assert flag.reason == "expected 0, found 6"
    assert flag.field == "composite"


def test_a_finding_is_a_tier_zero_flag_with_a_name_and_a_band():
    """``id`` is a stable machine name, ``label`` is the officer's sentence."""
    page, parsed = parsed_page("TD3", zone_with("TD3", 2, 44, "0"))

    flag = run_tier0(page.image, parsed_document=parsed).flags[0]

    assert flag.id in flag_ids.FLAG_IDS
    assert flag.tier == 0
    assert flag.label == "The composite check digit does not match."
    assert flag.weight_band == "high"
    assert flag.value == 1.0
    assert flag.confidence == 1.0
    assert flag.source_module == "app.pipeline.tier0.mrz"


def test_the_flag_carries_a_name_a_rule_invented_and_not_a_value():
    """Nothing a document printed reaches the flag except two digits.

    ``expected`` and ``found`` are the two halves of the arithmetic and
    nothing else; the field is a name this project wrote.  A flag that carried
    the characters the digit was computed over would be one more place a
    passport number sat, which is what ``CheckDigitResult`` refuses to be.
    """
    zone = zone_with("TD3", 2, 29, "A")

    page, parsed = parsed_page("TD3", zone)
    flags = run_tier0(page.image, parsed_document=parsed).flags

    assert flags
    assert not any(
        len(value) > 1
        for flag in flags
        for value in (flag.expected, flag.found)
        if value is not None
    )


def test_a_reference_date_does_not_move_a_check_digit_finding():
    """6.2 reads no day: the same document answers the same way either way."""
    page, parsed = parsed_page("TD3", zone_with("TD3", 2, 44, "0"))

    without = run_tier0(page.image, parsed_document=parsed)
    with_day = run_tier0(page.image, None, REFERENCE, parsed)

    assert with_day.flags == without.flags


def test_a_finding_leaves_the_override_to_6_5_and_6_5_answers_yes():
    """6.2 still sets nothing; the flag it returns is what 6.5 reads.

    **The pair is held rather than the ``False`` alone**, because this file
    was written when a failed digit was worth nothing beyond its own weight
    and a test that only asserted ``hard_failed is False`` would now pass on
    a runner that never asked the question at all.  What 6.5 settled is that
    the abstract's broken checksum exits straight to High Risk, so the
    override is the flag's own sentence and 6.2 is not where that is decided.
    """
    page, parsed = parsed_page("TD3", zone_with("TD3", 2, 44, "0"))

    result = run_tier0(page.image, parsed_document=parsed)

    assert result.flags
    assert result.hard_failed is True
    assert result.hard_fail_reason == result.flags[0].label


# --- the table is held against the three layouts ---------------------------


def _check_digit_rows():
    """Every ``(label, field, printed field)`` the three layouts declare."""
    return [
        (name, label, digit_field)
        for name, table in (
            ("TD1", td1.TD1_CHECK_DIGIT_FIELDS),
            ("TD2", td2.TD2_CHECK_DIGIT_FIELDS),
            ("TD3", td3.TD3_CHECK_DIGIT_FIELDS),
        )
        for label, _field, digit_field in table
    ]


@pytest.mark.parametrize(
    ("name", "label", "digit_field"),
    _check_digit_rows(),
    ids=[f"{name}-{label}" for name, label, _ in _check_digit_rows()],
)
def test_every_printed_digit_a_layout_declares_has_a_flag(name, label, digit_field):
    """A layout naming a digit this table lacks is a loud failure, not silence."""
    flag_id, _sentence, printed = runner._check_digit_flag(label)

    assert flag_id in flag_ids.FLAG_IDS
    assert printed == digit_field
    assert digit_field in {name for _line in LAYOUTS[name].values() for name in _line}


def test_no_check_digit_label_is_left_out_of_the_table():
    """The table is exactly the labels the three layouts use, either way round."""
    labels = {label for _name, label, _digit in _check_digit_rows()}

    assert labels == set(runner._CHECK_DIGIT_FLAG)


def test_a_label_no_layout_declares_is_refused_rather_than_skipped():
    """1.9's rule: the package raises one error type and never a bare KeyError."""
    with pytest.raises(MrzValueError):
        runner._check_digit_flag("no_such_digit")


# --- the seam: which parse, and whose page ---------------------------------


def test_a_page_nobody_handed_a_parse_for_carries_no_check_digit_findings():
    """The measurement still stands, and **no parse is not a pass**.

    Nothing in Part 4 reads a character out of a cell, so a caller who has a
    parse hands it over and a caller who does not gets the format and the
    regions and nothing else.  The two are different statements and only the
    flag-bearing one says anything about a document.
    """
    page = mrz_images.render_format("TD3")

    without = run_tier0(page.image)
    with_parse = run_tier0(
        page.image, parsed_document=document.parse_mrz(page.lines)
    )

    assert without.flags == ()
    assert with_parse.flags == ()
    assert without.detected_format == with_parse.detected_format == "TD3"


@pytest.mark.parametrize(
    "name", [other for other in FORMATS if other != "TD3"], ids=lambda n: n
)
def test_a_parse_of_another_format_is_refused_at_the_seam(name):
    """A highlight drawn over the wrong words is worse than no highlight."""
    page = mrz_images.render_format("TD3")

    with pytest.raises(MrzValueError):
        run_tier0(
            page.image,
            parsed_document=document.parse_mrz(mrz_images.SPECIMENS[name]),
        )


def test_a_parse_against_a_page_with_no_zone_is_refused():
    """The page measured as ``None``, so no field name can match it."""
    blank = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))

    with pytest.raises(MrzValueError):
        run_tier0(
            blank.image,
            parsed_document=document.parse_mrz(mrz_images.SPECIMENS["TD3"]),
        )


@pytest.mark.parametrize(
    "not_a_document",
    [
        pytest.param(mrz_images.SPECIMENS["TD3"], id="a-zone"),
        pytest.param("TD3", id="a-format-name"),
        pytest.param(None, id="none"),
        pytest.param(3, id="an-int"),
    ],
)
def test_only_a_parsed_document_or_nothing_is_a_parsed_document(not_a_document):
    """The shape is checked, for 6.1's reason and the same one."""
    page = mrz_images.render_format("TD3")

    if not_a_document is None:
        assert run_tier0(page.image, parsed_document=None).flags == ()
        return
    with pytest.raises(MrzValueError):
        run_tier0(page.image, parsed_document=not_a_document)


def test_a_field_with_no_box_is_a_flag_with_no_region_and_not_a_dropped_one():
    """4.12 says a field no cell names is absent; 23.6 says still list it.

    **Lines are empty here on purpose**, which is the one way a caller reaches
    4.12 with no cells to name, and the seam below it never sees: the runner
    always hands over what 4.6 kept.  It is the honest extreme of a short line
    whose cells were merged away, and the finding has to survive it.
    """
    page, parsed = parsed_page("TD3", zone_with("TD3", 2, 44, "0"))
    assert mrz_region.field_regions(parsed, ()) == {}

    flags = runner._check_digit_flags(parsed, ())

    assert [flag.id for flag in flags] == [
        flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH
    ]
    assert flags[0].region is None
    assert flags[0].field == "composite"


# --- the runner does not redo what Part 1 already answered -----------------


def _called_names(module) -> set[str]:
    """Every bare function name ``module`` calls."""
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Name)
    }


def test_the_runner_recomputes_no_digit_of_its_own():
    """The arithmetic stays in Part 1, so two places cannot disagree."""
    called = _called_names(runner)

    assert not called & {
        "char_value",
        "check_digit",
        "check_digit_results",
        "verify_check_digit",
        "weights",
    }


def test_the_runner_reports_what_the_document_already_said():
    """The verdict is the parse's own record, read and not re-derived."""
    zone = zone_with("TD3", 2, 44, "0")

    page, parsed = parsed_page("TD3", zone)
    flags = run_tier0(page.image, parsed_document=parsed).flags

    assert [(flag.field, flag.expected, flag.found) for flag in flags] == [
        (entry.field, str(entry.expected), str(entry.found))
        for entry in parsed.check_digit_results
        if entry.passed is False
    ]


def test_nothing_in_the_runner_reached_the_clock_on_the_way():
    """6.2 read no day either, so 6.1's walk is repeated rather than assumed."""
    tree = ast.parse(pathlib.Path(runner.__file__).read_text(encoding="utf-8"))

    assert [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Attribute)
        if node.func.attr in {"now", "utcnow", "today", "fromtimestamp"}
    ] == []
