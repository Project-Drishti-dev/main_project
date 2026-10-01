"""6.7 -- worked example A of `abstract.txt`, as a page and a set of flags.

Section 3 states the example in one sentence: a passport image passes the
quality gate, the MRZ is re-read at high confidence, **the date-of-birth check
digit is expected to be 4 but is found to be 7**, a hard rule for MRZ
integrity fires, the case exits to High Risk in under a second, and the
officer sees the date-of-birth field highlighted with the note "DOB check
digit mismatch".  Gate 6 is that sentence passing as a test, so this file
draws the document rather than describing it.

:data:`DOB` is the six characters the example's date of birth is printed as,
:data:`PRINTED_DIGIT` is the digit printed beside them, and every other
printed digit on the page agrees with its own characters -- so the
date-of-birth digit is the only disagreement and exactly one flag is owed.
:data:`REQUIRED` is what the standard makes of those six characters, read from
:func:`~app.pipeline.tier0.mrz.check_digit` at import rather than written
here, so the abstract's "4" is the library's answer and not this file's.

The zone is read back off the page's pixels before it is parsed, so the
document under test is the one the frame holds.  Nothing here drives the date
rules of 5.4 to 5.7, which 6.3 has not wired into the runner: worked example
A is a check-digit finding and the two halves of Tier 0 run independently.
"""

from app.pipeline.tier0 import document, mrz, mrz_region, runner, td3
from app.risk import flag_ids
from tests.fixtures import mrz_images

run_tier0 = runner.run_tier0

#: The six date-of-birth characters the page prints, chosen so that
#: :func:`~app.pipeline.tier0.mrz.check_digit` answers 4 over them -- which
#: ``test_the_standard_s_own_answer_over_those_six_characters_is_four`` reads
#: back from the library rather than from a literal here.
DOB = "740522"

#: The digit the page prints beside that date of birth, and the half of the
#: abstract's sentence that reads "found to be 7".
PRINTED_DIGIT = "7"

#: What the standard requires over :data:`DOB`, as one string: the shape
#: :class:`~app.risk.flags.EvidenceFlag` carries its two digits in.
REQUIRED = str(mrz.check_digit(DOB))


def _replacing(line, field, characters):
    """Return ``line`` with ``field``'s characters replaced, by the layout.

    **Every position is read out of
    :data:`~app.pipeline.tier0.td3.TD3_LINE_2` and none is counted here**, so
    the page is built from the table the pipeline reads rather than from a
    copy of it that could drift from it.
    """
    start, end = td3.TD3_LINE_2[field]
    return line[: start - 1] + characters + line[end:]


def zone_with(printed_digit=PRINTED_DIGIT):
    """The specimen with :data:`DOB` printed and ``printed_digit`` beside it.

    **The composite is recomputed over the line as printed**, so the composite
    agrees with the page and the date-of-birth digit is the only thing on it
    that does not -- which is the one note the abstract's example describes.
    A page whose composite failed as well is a real document and is not this
    one: it is the two-flag case 6.2's suite drives, and 2.14's blind spot is
    that a substitution inside a composite span is the composite's alone.
    """
    specimen = mrz_images.SPECIMENS["TD3"]
    line_2 = _replacing(specimen[1], "date_of_birth", DOB)
    line_2 = _replacing(line_2, "date_of_birth_check_digit", printed_digit)
    composite = str(mrz.check_digit(td3.td3_composite_input(line_2)))
    return (specimen[0], _replacing(line_2, "composite_check_digit", composite))


def drawn(printed_digit=PRINTED_DIGIT):
    """The drawn page, and the parse a caller who holds one would hand over.

    **The zone is read back off the pixels before it is parsed**, so the
    parse under test is the one the frame holds rather than the one this file
    typed, and the assertion is what stops the example passing on a page that
    was never drawn the way it claims.
    """
    zone = zone_with(printed_digit)
    page = mrz_images.render_format("TD3", lines=zone)
    read = mrz_images.read_zone(page)
    assert read == zone
    return page, document.parse_mrz(read)


def _holds(outer, inner):
    """Whether the half-open box ``outer`` encloses the box ``inner``."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _digit_cell(page):
    """The fixture's own box for the printed date-of-birth digit."""
    start, _end = td3.TD3_LINE_2["date_of_birth_check_digit"]
    return page.cells[1][start - 1]


# --- the example -----------------------------------------------------------


def test_the_standard_s_own_answer_over_those_six_characters_is_four():
    """The abstract's "expected 4", read off the library and not asserted here."""
    assert REQUIRED == "4"
    assert mrz.check_digit(DOB) == 4
    assert int(PRINTED_DIGIT) != mrz.check_digit(DOB)


def test_worked_example_a_reports_one_flag_naming_the_date_of_birth():
    """The four things the task's verify asks for, on the page the task names."""
    page, parsed = drawn()

    result = run_tier0(page.image, parsed_document=parsed)

    assert [flag.id for flag in result.flags] == [
        flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH
    ]
    flag = result.flags[0]
    assert flag.expected == "7" == PRINTED_DIGIT
    assert flag.found == "4" == REQUIRED
    assert flag.region is not None
    assert flag.field == "date_of_birth"
    assert flag.tier == 0
    assert flag.weight_band == "high"
    assert flag.label == "The date of birth's check digit does not match."


def test_the_flag_is_boxed_over_the_printed_digit_it_disagrees_with():
    """The abstract's "the date-of-birth field highlighted", at 4.12's box."""
    page, parsed = drawn()
    detection = mrz_region.detect_mrz(page.image)

    flag = run_tier0(page.image, parsed_document=parsed).flags[0]
    box = mrz_region.field_regions(parsed, detection.lines)[
        "date_of_birth_check_digit"
    ]

    assert flag.region == box
    assert _holds(
        (box[0][0], box[0][1], box[2][0], box[2][1]), _digit_cell(page)
    )


def test_the_date_of_birth_digit_is_the_only_row_that_disagrees():
    """The composite agrees, so this is one rule's finding and not two."""
    _page, parsed = drawn()

    verdicts = {
        verdict.field: verdict.passed for verdict in parsed.check_digit_results
    }

    assert verdicts["date_of_birth"] is False
    assert [field for field, passed in verdicts.items() if passed is False] == [
        "date_of_birth"
    ]
    assert not [field for field, passed in verdicts.items() if passed is None]


def test_the_case_exits_as_a_hard_fail_naming_that_finding_s_own_sentence():
    """6.5's override, and the reason it gives is the finding's own label."""
    page, parsed = drawn()

    result = run_tier0(page.image, parsed_document=parsed)

    assert result.hard_failed is True
    assert result.hard_fail_reason == result.flags[0].label
    assert "date of birth" in result.hard_fail_reason


def test_the_case_exits_within_the_second_the_abstract_states():
    """The example's own bound, not the sub-0.3 s design target above it.

    A target is not a threshold a shared test machine may be held to, and
    :attr:`~app.pipeline.tier0.runner.TierResult.stage_timings` is what 6.6
    measured, so the number is read off the record rather than timed here.
    """
    page, parsed = drawn()

    result = run_tier0(page.image, parsed_document=parsed)

    assert result.stage_timings["total"] < 1.0


def test_the_same_page_printing_the_digit_the_standard_requires_is_silent():
    """The printed digit is the whole difference, so the finding is owed to it."""
    page, parsed = drawn(printed_digit=REQUIRED)

    result = run_tier0(page.image, parsed_document=parsed)

    assert result.flags == ()
    assert result.hard_failed is False


def test_the_two_digits_are_carried_the_other_way_round_from_the_abstract():
    """Part 1's naming, pinned so the difference is a decision and not a drift.

    :attr:`~app.risk.flags.EvidenceFlag.expected` carries the digit the line
    prints and ``found`` the one its characters come to, which is the reverse
    of the abstract's "expected 4, found 7" -- so the reason an officer reads
    is "expected 7, found 4".  Part 1 wrote the names and 6.2's suite holds
    them, so this test names the difference instead of changing it; the
    question is recorded in ``HANDOVER.md``.
    """
    page, parsed = drawn()
    verdict = next(
        row
        for row in parsed.check_digit_results
        if row.field == "date_of_birth"
    )

    flag = run_tier0(page.image, parsed_document=parsed).flags[0]

    assert (flag.expected, flag.found) == (
        str(verdict.expected),
        str(verdict.found),
    ) == ("7", "4")
    assert flag.reason == "expected 7, found 4"
