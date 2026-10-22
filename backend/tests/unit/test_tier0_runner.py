"""6.1 -- the runner and the one record Tier 0 hands back.

`tasks.md` names five things on :class:`~app.pipeline.tier0.runner.TierResult`
-- flags, a hard-failed bool, a hard-fail reason, a detected format and
detected regions -- and one entry point that runs a page through them.  What
is pinned here is the shape of that record, the seam's refusals, and the claim
this runner is *not* making yet.  **6.6 added a sixth field**, the per-stage
timings, and the two structural tests below carry it as an addition; what
the numbers mean and whether they can be trusted is `test_tier0_timing.py`'s
own file.

**The measurement is Part 4's own, handed over untouched.**  The format is
4.7's answer and the regions are 4.8's polygons, so the tests compare the
result against :func:`~app.pipeline.tier0.mrz_region.detect_mrz` rather than
against a second set of numbers written here: a runner that re-measured would
be the second opinion this project has spent four parts refusing to write.

**6.1's empty flag list was this task's claim and 6.2 broke it.**  6.2 wired
the check digits, so the test that asserted no rules were wired is gone and
`test_tier0_check_digits.py` holds what fired instead.  A page with a zone and
no parse still comes back with no flags, and that is a different statement
from a clean document's: it is in `test_tier0_check_digits.py` too, because
neither of them is a pass.

**The clock ban is walked, not grepped**, for the reason
:mod:`test_reference_date` gives: this docstring and the module's own name
`datetime.now()` in order to say it is not used.
"""

import ast
import dataclasses
import datetime
import inspect
import pathlib

import numpy as np
import pytest

from app.pipeline.tier0 import document, mrz_region, runner
from app.pipeline.tier0.mrz import MrzValueError
from app.risk.flags import EvidenceFlag, FlagValueError
from tests.fixtures import mrz_images

TierResult = runner.TierResult
run_tier0 = runner.run_tier0

#: The reference the injection tests use, and the day 5.8's own suite measures
#: against.  No rule in this module reads a day; the value is here so the
#: argument can be shown being accepted and being passed on.
REFERENCE = datetime.date(2026, 9, 30)

#: The three formats, as ``(name, line count)`` pairs read out of Part 3's own
#: table rather than written down here.
FORMATS = sorted(document.MRZ_SHAPES.items())

#: A page carrying print that is not a machine-readable zone: one short line of
#: ordinary text, which is what a page with no MRZ on it looks like.
NO_ZONE_PAGE = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))


def _tree(module) -> ast.Module:
    """The parsed source of ``module``."""
    return ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))


def _clock_calls(module) -> list[str]:
    """Every attribute call named after the calendar in ``module``'s source."""
    return [
        node.func.attr
        for node in ast.walk(_tree(module))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        if node.func.attr in {"now", "utcnow", "today", "fromtimestamp"}
    ]


def _blank_page():
    """A frame of paper with nothing on it at all."""
    return np.full((120, 320, 3), 255, np.uint8)


def box_of(polygon):
    """The half-open box a polygon names, read by position."""
    return (
        min(point[0] for point in polygon),
        min(point[1] for point in polygon),
        max(point[0] for point in polygon),
        max(point[1] for point in polygon),
    )


def holds(outer, inner):
    """Whether the half-open box ``outer`` encloses the box ``inner``."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def ink_box(page, number):
    """The half-open box the ink of one drawn line covers.

    **The cells and not the ink are what the generator knows, so the ink is
    read back off the frame.**  A cell is a fixed box the glyph is stamped
    into, and a character whose pattern leaves its last column empty prints
    ink a whole cell short of the cell's edge -- so a polygon that covered
    every cell would be a polygon a sixth of a line too wide, and 4.8's own
    note says it is one pixel inside the drawn extent rather than on it.
    """
    line = page.cells[number]
    left = min(cell[0] for cell in line)
    top = min(cell[1] for cell in line)
    right = max(cell[2] for cell in line)
    bottom = max(cell[3] for cell in line)
    patch = page.image[top:bottom, left:right, 0]
    ink = np.argwhere(patch < mrz_images.INK_LEVEL + 128)

    return (
        left + int(ink[:, 1].min()),
        top + int(ink[:, 0].min()),
        left + int(ink[:, 1].max()) + 1,
        top + int(ink[:, 0].max()) + 1,
    )


# --- the named behaviour: a page in, a TierResult out -----------------------


@pytest.mark.parametrize(
    ("shape", "name"), FORMATS, ids=[name for _, name in FORMATS]
)
def test_a_synthetic_mrz_page_comes_back_as_a_tier_result(shape, name):
    """`tasks.md` 6.1's own verify, on every format the project prints."""
    page = mrz_images.render_format(name)

    result = run_tier0(page.image)

    assert type(result) is TierResult
    assert result.detected_format == name == page.format
    assert len(result.detected_regions) == shape[0]


def test_the_empty_result_is_the_empty_result_and_not_a_gap():
    """Every field defaulted, so a caller compares against one value."""
    result = TierResult()

    assert result == TierResult(
        flags=(),
        hard_failed=False,
        hard_fail_reason=None,
        detected_format=None,
        detected_regions=(),
        stage_timings={name: 0.0 for name in runner.STAGE_NAMES},
    )
    assert result.flags == ()
    assert result.hard_failed is False
    assert result.detected_regions == ()


def test_the_result_carries_the_fields_the_task_names_and_nothing_else():
    """Six fields: 6.1's five in the task's order, then 6.6's timings.

    **The sixth is an addition and not a replacement**, so the order the task
    names them in still reads off the record in that order, and a consumer
    written against the first five keeps working.
    """
    assert [field.name for field in dataclasses.fields(TierResult)] == [
        "flags",
        "hard_failed",
        "hard_fail_reason",
        "detected_format",
        "detected_regions",
        "stage_timings",
    ]


def test_the_record_cannot_be_edited_and_carries_no_second_opinion():
    """Frozen, and no public method, for every other record's reason.

    **The names are read off an instance and not the class**, because 6.6's
    sixth field is built by a factory: a dataclass leaves no class attribute
    behind for one, so asking the class would quietly drop a field rather
    than catch a method added to it.
    """
    public = [
        name
        for name in dir(TierResult())
        if not name.startswith("_")
    ]

    with pytest.raises(dataclasses.FrozenInstanceError):
        TierResult().detected_format = "TD1"

    assert public == [
        "detected_format",
        "detected_regions",
        "flags",
        "hard_fail_reason",
        "hard_failed",
        "stage_timings",
    ]


# --- the measurement is Part 4's own, handed over --------------------------


def test_the_format_and_the_regions_are_the_chain_s_own_answer():
    """A re-measurement would be the second opinion 4.8's note warns about."""
    page = mrz_images.render_format("TD3")
    detection = mrz_region.detect_mrz(page.image)

    result = run_tier0(page.image)

    assert result.detected_format == detection.format
    assert result.detected_regions == detection.regions


@pytest.mark.parametrize(
    ("shape", "name"), FORMATS, ids=[name for _, name in FORMATS]
)
def test_every_line_the_chain_found_has_a_region_on_it(shape, name):
    """One polygon per line, and each one covers the ink it was drawn from."""
    page = mrz_images.render_format(name)

    regions = run_tier0(page.image).detected_regions

    assert len(regions) == shape[0]
    for number, region in enumerate(regions):
        assert holds(box_of(region), ink_box(page, number)), (
            f"line {number + 1} does not cover its own ink"
        )


# --- a page with no zone is a value and not a refusal -----------------------


@pytest.mark.parametrize(
    "page",
    [
        pytest.param(_blank_page(), id="paper"),
        pytest.param(NO_ZONE_PAGE.image, id="ordinary-text"),
        pytest.param(
            mrz_images.draw_page(("B" * 44,)).image,
            id="one-line-of-44",
        ),
    ],
)
def test_a_page_with_no_zone_this_project_reads_is_answered_not_refused(page):
    """Part 4's own rule, carried: the format is ``None`` and nothing raises."""
    result = run_tier0(page)

    assert type(result) is TierResult
    assert result.detected_format is None
    # The lines and their regions are still reported: 4.8 measures ink and a
    # line of print is ink, so the format being ``None`` is the only thing a
    # caller loses here.
    assert result.detected_regions == mrz_region.detect_mrz(page).regions
    assert result.flags == ()
    assert result.hard_failed is False


def test_a_turned_page_still_comes_back_as_a_result():
    """The chain's angle, not this module's: four degrees and a named format."""
    page = mrz_images.render_format("TD3", angle_deg=4.0)

    result = run_tier0(page.image)

    assert type(result) is TierResult
    assert result.detected_format == mrz_region.detect_mrz(page.image).format
    assert len(result.detected_regions) == len(page.cells)


# --- the hard fail and its reason are one thing ----------------------------


def _a_flag(**overrides):
    """A flag to put in a result, with the fields a test does not care about
    written once here rather than in every case that needs one."""
    fields = {
        "id": "MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH",
        "tier": 0,
        "label": "The composite check digit does not match.",
        "weight_band": "high",
        "value": 1.0,
        "confidence": 1.0,
        "region": ((0, 0), (10, 0), (10, 4), (0, 4)),
        "expected": "4",
        "found": "7",
        "reason": "expected 4, found 7",
        "source_module": "app.pipeline.tier0.mrz",
        "field": "composite",
    }
    return EvidenceFlag(**{**fields, **overrides})


def test_a_hard_fail_carries_its_reason_and_a_reason_is_a_hard_fail():
    """The abstract's exit records the reason, so the two fields are one."""
    with_reason = TierResult(
        hard_failed=True, hard_fail_reason="MRZ integrity failure"
    )
    with pytest.raises(MrzValueError):
        TierResult(hard_failed=True)
    with pytest.raises(MrzValueError):
        TierResult(hard_fail_reason="MRZ integrity failure")

    assert with_reason.hard_failed is True


@pytest.mark.parametrize(
    "hard_failed", [0, 1, "yes", None], ids=["zero", "one", "a-string", "none"]
)
def test_hard_failed_is_a_bool_and_not_something_truthy(hard_failed):
    """An engine branching on this field cannot compare a number to a bool."""
    with pytest.raises(MrzValueError):
        TierResult(hard_failed=hard_failed)


# --- the fields a caller can get wrong at the seam --------------------------


def test_flags_must_be_the_records_the_engine_reads():
    """A tuple holding anything else would be scored as though it were one."""
    flag = _a_flag()

    assert TierResult(flags=(flag,)).flags == (flag,)
    for bad in ([flag], (flag, "composite"), ({"id": "X"},), (None,)):
        with pytest.raises(MrzValueError):
            TierResult(flags=bad)


def test_the_container_fields_are_tuples_and_the_record_is_frozen():
    """A list in a frozen record is a hole in the frozenness.

    **6.6 took the record's hash with it**, and the trade went this way: a
    read-only mapping cannot be hashed, while a caller's own dict left in the
    field is the hole this test exists to catch.  The two tuple fields are
    still refused as lists, and the mapping's own immutability is held in
    `test_tier0_timing.py` against a dict the caller still holds.
    """
    with pytest.raises(MrzValueError):
        TierResult(detected_regions=[[(0, 0), (4, 0), (4, 4)]])

    assert hash(TierResult().detected_regions) == hash(())


def test_a_detected_format_is_a_name_the_project_reads():
    """Read out of Part 3's table, so a fourth format is one entry there."""
    for name in document.MRZ_SHAPES.values():
        assert TierResult(detected_format=name).detected_format == name
    with pytest.raises(MrzValueError):
        TierResult(detected_format="TD4")


@pytest.mark.parametrize(
    "document_type",
    [
        pytest.param("", id="empty"),
        pytest.param(0, id="an-int"),
        pytest.param(("passport",), id="a-tuple"),
    ],
)
def test_a_document_type_is_a_callers_word_or_nothing(document_type):
    """The shape is checked; no vocabulary is imposed on it."""
    with pytest.raises(MrzValueError):
        run_tier0(_blank_page(), document_type)


@pytest.mark.parametrize(
    "document_type",
    [
        pytest.param(None, id="none"),
        pytest.param("passport", id="passport"),
        pytest.param("national_id", id="national-id"),
        pytest.param("TD1", id="a-format-name"),
    ],
)
def test_a_document_type_never_chooses_the_format(document_type):
    """The shape decides, so a claim in front of a TD1 still gets the TD1."""
    page = mrz_images.render_format("TD3")

    assert run_tier0(page.image, document_type).detected_format == "TD3"


@pytest.mark.parametrize(
    "reference_date",
    [
        pytest.param("2026-09-30", id="a-string"),
        pytest.param(20260930, id="an-int"),
        pytest.param((2026, 9, 30), id="a-tuple"),
    ],
)
def test_a_reference_date_that_is_not_a_day_is_refused_at_the_seam(reference_date):
    """A bad reference is a caller mistake and is loud, on 5.8's reasoning."""
    with pytest.raises(MrzValueError):
        run_tier0(_blank_page(), None, reference_date)


@pytest.mark.parametrize(
    "reference_date",
    [
        pytest.param(None, id="none"),
        pytest.param(REFERENCE, id="a-day"),
        pytest.param(datetime.datetime(2026, 9, 30, 23, 59, 59), id="a-stamp"),
    ],
)
def test_a_reference_date_is_injected_and_never_read_from_the_clock(
    reference_date,
):
    """``None`` is the caller saying they injected no day, not a default."""
    page = mrz_images.render_format("TD3")

    assert run_tier0(page.image, None, reference_date).detected_format == "TD3"
    assert run_tier0(page.image, reference_date=reference_date) is not None


def test_the_entry_point_is_the_signature_the_task_names():
    """Four optional arguments and none of them is a day or a callable.

    **``parsed_document`` is 6.2's addition and it is not a rule or a
    callback**: it is the caller's own parse of the same page, handed over
    because nothing in Part 4 reads a character out of a cell.
    **``watchlist`` is 6.4's, and it is a connector rather than a rule or a
    callback too**: a caller wires a list and the runner never imports one.
    """
    signature = inspect.signature(run_tier0)

    assert list(signature.parameters) == [
        "image",
        "document_type",
        "reference_date",
        "parsed_document",
        "watchlist",
    ]
    assert signature.parameters["document_type"].default is None
    assert signature.parameters["reference_date"].default is None
    assert signature.parameters["parsed_document"].default is None
    assert signature.parameters["watchlist"].default is None
    assert not [
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is not inspect.Parameter.empty
        and (isinstance(parameter.default, datetime.date) or callable(
            parameter.default
        ))
    ]


def test_the_module_is_the_tier_s_whole_surface():
    """``__all__`` pins what a caller may reach for."""
    assert runner.__all__ == ["STAGE_NAMES", "TIER_NAME", "TierResult", "run_tier0"]
    assert {
        node.name for node in _tree(runner).body if isinstance(node, ast.ClassDef)
    } == {"TierResult"}
    assert {
        node.name
        for node in _tree(runner).body
        if isinstance(node, ast.FunctionDef)
        if not node.name.startswith("_")
    } == {"run_tier0"}


def test_nothing_in_the_runner_reads_the_clock():
    """`datetime.now()` inside check logic is banned by `tasks.md`."""
    assert _clock_calls(runner) == [], "runner.py reads the clock"

    # The walk only means something if the module holds `datetime` at all: a
    # module that could not have read the calendar would pass vacuously.
    imported = {
        alias.name
        for node in ast.walk(_tree(runner))
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "datetime" in imported


def test_a_flag_this_runner_would_carry_is_the_type_the_engine_reads():
    """The import is the dependency direction: rules emit, the runner collects."""
    assert TierResult(flags=(_a_flag(),)).flags[0].tier == 0
    with pytest.raises(FlagValueError):
        # A flag built wrongly is refused where it is built, not here.
        _a_flag(value=1.4)
