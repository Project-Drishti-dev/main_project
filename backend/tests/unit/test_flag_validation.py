"""What an :class:`EvidenceFlag` refuses: the three shape rules of 5.2.

5.1 built a record whose eleven fields could be constructed and read back and
checked nothing else, so every claim below is new rather than a tightening of
an old one.

**One test per rejected case**, parametrised with an ``id`` naming the case, so
a failure says which field and which value was accepted rather than that a
parametrised group failed.  The accepted side is pinned as hard as the refused
side: a check that refuses everything is not a check, and the boundary cases --
``0`` and ``1``, a triangle, a box, ``region=None`` -- are where a range or a
polygon rule goes wrong quietly.

**Every case is built through the constructor**, never by calling a private
check, because the claim is that a malformed flag cannot be built at all.
"""

import ast
import dataclasses
import numbers
import pathlib

import numpy as np
import pytest

from app.pipeline.tier0 import mrz
from app.risk import flags as flags_module
from app.risk.flags import (
    EvidenceFlag,
    FlagValueError,
    MIN_REGION_CORNERS,
    WEIGHT_BANDS,
)

#: A field-shaped box: two lines of pixels, clockwise from the top left, the
#: shape 4.12's `_box_polygon` writes and 6.2 hands over unchanged.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: The smallest legal polygon: three corners, and the case the floor exists for.
TRIANGLE = ((10, 20), (110, 20), (60, 90))


def a_flag(**overrides):
    """A well-formed flag, with ``overrides`` replacing any of its fields."""
    values = {
        "id": "MRZ_DOB_CHECK_DIGIT_MISMATCH",
        "tier": 0,
        "label": "Date-of-birth check digit does not match",
        "weight_band": "high",
        "value": 0.9,
        "confidence": 1.0,
        "region": FIELD_BOX,
        "expected": "4",
        "found": "7",
        "reason": "The digits printed over the date of birth read 7; the "
        "characters themselves compute to 4.",
        "source_module": "app.pipeline.tier0.runner",
        "field": "date_of_birth",
    }
    values.update(overrides)
    return EvidenceFlag(**values)


# --- value and confidence: real numbers in the closed unit interval ---------


@pytest.mark.parametrize("field", ["value", "confidence"])
@pytest.mark.parametrize(
    ("number", "label"),
    [
        (0, "zero-as-an-int"),
        (1, "one-as-an-int"),
        (0.0, "zero"),
        (1.0, "one"),
        (0.5, "midway"),
        (0.999999, "just-below-one"),
        (1e-9, "just-above-zero"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_a_number_inside_the_closed_range_is_accepted(field, number, label):
    """Both ends are inside `[0, 1]`; a range stated with a `<` would refuse them."""
    flag = a_flag(**{field: number})

    assert getattr(flag, field) == number


@pytest.mark.parametrize("field", ["value", "confidence"])
@pytest.mark.parametrize(
    "number",
    [1.4, -0.0001, 100, -1],
    ids=["just-above-one", "just-below-zero", "a-hundred", "minus-one"],
)
def test_a_number_outside_the_range_is_refused(field, number):
    """**Refused, not clipped.**  `value = 1.4` is a bug in the module that built
    the flag, so it raises rather than arriving at 7.5 as a contribution of 1.0
    for a finding that measured 1.4 -- a difference no score downstream could
    show.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(**{field: number})

    assert field in str(caught.value)
    assert "[0, 1]" in str(caught.value)


@pytest.mark.parametrize("field", ["value", "confidence"])
@pytest.mark.parametrize(
    "number",
    ["0.9", None, [0.9], {"value": 0.9}],
    ids=["a-string", "none", "a-list", "a-dict"],
)
def test_something_that_is_not_a_number_is_refused(field, number):
    with pytest.raises(FlagValueError) as caught:
        a_flag(**{field: number})

    assert field in str(caught.value)
    assert "real number" in str(caught.value)


@pytest.mark.parametrize("field", ["value", "confidence"])
@pytest.mark.parametrize(
    "number",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "infinity", "negative-infinity"],
)
def test_a_number_that_compares_with_nothing_is_refused(field, number):
    """`nan` is a real number and fails both halves of a two-sided range test.

    `number < 0 or number > 1` would let it through, so the range is chained and
    this case is the reason: a `nan` reaching 7.4's normalise would poison a
    weighted sum silently.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(**{field: number})

    assert "[0, 1]" in str(caught.value)


# --- weight_band: one of the three bands ------------------------------------


def test_the_allowed_bands_are_the_three_the_definitions_name():
    """`tasks.md` defines a band as `low` | `review` | `high`, and nothing else.

    `review` must never auto-reject is a property of the thresholds in 7.8, not
    of the name, so nothing here reads the set as an ordering.
    """
    assert set(WEIGHT_BANDS) == {"low", "review", "high"}
    assert isinstance(WEIGHT_BANDS, frozenset)


@pytest.mark.parametrize("band", ["low", "review", "high"])
def test_a_band_in_the_allowed_set_is_accepted(band):
    assert a_flag(weight_band=band).weight_band == band


@pytest.mark.parametrize(
    "band",
    ["critical", "High", "HIGH", "low ", " low", "", "medium", None, 1, ("low",)],
    ids=[
        "an-unknown-name",
        "capitalised",
        "shouted",
        "trailing-space",
        "leading-space",
        "empty",
        "another-unknown-name",
        "none",
        "an-int",
        "a-tuple",
    ],
)
def test_a_band_outside_the_allowed_set_is_refused(band):
    """The membership is exact: a near-miss is a different band, not a typo to fix.

    A tuple is in the list because membership on an unhashable value raises
    `TypeError`, and a flag built wrongly is refused with one error type.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(weight_band=band)

    assert "weight_band" in str(caught.value)
    assert "high" in str(caught.value)


# --- region: a polygon of whole-pixel corners, or None ----------------------


def test_a_polygon_and_no_region_are_both_legal():
    """`None` is 23.6's claim -- a finding with nowhere to point is still listed.

    So the polygon check is a check on the shape that is there and never a
    demand that something be there, and both of the legal shapes are built here
    rather than one being the default.
    """
    assert a_flag(region=None).region is None
    assert a_flag(region=FIELD_BOX).region == FIELD_BOX
    assert a_flag(region=TRIANGLE).region == TRIANGLE


def test_a_polygon_of_five_corners_is_accepted():
    """The floor is a floor: a shape above it is not refused for being unusual."""
    pentagon = ((10, 20), (60, 10), (110, 20), (100, 60), (20, 60))

    assert a_flag(region=pentagon).region == pentagon


def test_a_corner_of_any_integer_type_is_accepted():
    """`numbers.Integral` rather than `int`, so a detector's scalar is not a refusal.

    4.12 casts to plain `int` so a numpy scalar cannot reach Part 11's JSON; a
    flag handed one anyway holds the same pixel, and refusing it would push the
    cast into every future caller instead of leaving it in the one helper that
    already does it.

    A `bool` is in the same list for the same reason: `True` is pixel 1 in
    Python's own arithmetic, so it is a coordinate rather than a shape error.
    """
    numpy_region = (
        (np.int64(10), np.int64(20)),
        (np.int64(110), np.int64(20)),
        (np.int64(10), np.int64(40)),
    )
    boolean_region = ((10, True), (110, 20), (10, 40))

    numpy_flag = a_flag(region=numpy_region)
    boolean_flag = a_flag(region=boolean_region)

    assert all(
        isinstance(coord, numbers.Integral)
        for corner in numpy_flag.region
        for coord in corner
    )
    assert boolean_flag.region == ((10, 1), (110, 20), (10, 40))


@pytest.mark.parametrize("field", ["value", "confidence"])
def test_the_field_named_in_the_message_is_the_field_that_was_refused(field):
    """Two ranges, one message shape: the officer reading a traceback is told
    which of the two numbers was out of bounds, and a message that always said
    "value" would send the reader to the wrong field.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(**{field: 1.4})

    other = "confidence" if field == "value" else "value"
    assert f"{field} must lie" in str(caught.value)
    assert other not in str(caught.value)


@pytest.mark.parametrize(
    "region",
    [
        (),
        ((10, 20),),
        ((10, 20), (110, 20)),
        "date_of_birth",
        {"x": 10, "y": 20},
        [[10, 20], [110, 20], [10, 40]],
        42,
        False,
    ],
    ids=[
        "no-corners",
        "one-corner",
        "two-corners",
        "a-field-name",
        "a-box-as-a-dict",
        "a-list-of-lists",
        "an-int",
        "a-bool",
    ],
)
def test_a_region_that_is_not_a_polygon_is_refused(region):
    """`D5` forbids the string and the dict outright; the floor forbids the rest.

    Two corners are a segment and enclose no area, which is the only reason the
    floor is three rather than two. `False` is in the list because it is not
    `None` and `region is None` is the test, not `if not region` -- so an
    "empty" region fails as a shape rather than passing as an absent one.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(region=region)

    assert "region" in str(caught.value)
    assert str(MIN_REGION_CORNERS) in str(caught.value)


@pytest.mark.parametrize(
    ("region", "message"),
    [
        (((10, 20, 30), (110, 20), (10, 40)), "(x, y) pair"),
        (((10,), (110, 20), (10, 40)), "(x, y) pair"),
        ((10, 110, 10), "(x, y) pair"),
        ((10, 20, 30), "(x, y) pair"),
        ((None, None, None), "(x, y) pair"),
        (((10.5, 20), (110, 20), (10, 40)), "whole pixels"),
        (((10, None), (110, 20), (10, 40)), "whole pixels"),
        (("[10, 20]", (110, 20), (10, 40)), "(x, y) pair"),
        (((10, "20"), (110, 20), (10, 40)), "whole pixels"),
    ],
    ids=[
        "three-values",
        "one-value",
        "a-corner-of-bare-ints",
        "three-bare-ints",
        "three-nones",
        "a-fractional-pixel",
        "none-in-a-corner",
        "a-list-in-a-corner",
        "text-in-a-corner",
    ],
)
def test_a_corner_that_is_not_a_pair_of_whole_pixels_is_refused(region, message):
    with pytest.raises(FlagValueError) as caught:
        a_flag(region=region)

    assert "region corner" in str(caught.value)
    assert message in str(caught.value)


def test_the_offending_corner_is_named_and_the_bad_text_is_not():
    """A message may point at the corner it broke and quote nothing.

    A field name or a line of printed text is exactly what a wrong region
    carries, and `AGENTS.md` bans identity data in logs -- so the refusal names
    the rule and the index, and the value stays in the caller's own frame.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(region=((10, 20), (110, 20), ("SURNAME", "ERIKSSON")))

    assert "region corner 2" in str(caught.value)
    assert "ERIKSSON" not in str(caught.value)
    assert "SURNAME" not in str(caught.value)


def test_the_message_never_quotes_the_value_it_refused():
    """A band handed over as OCR text is refused without that text in the message."""
    with pytest.raises(FlagValueError) as caught:
        a_flag(weight_band="ERIKSSON<<ANNA MARIA")

    assert "weight_band" in str(caught.value)
    assert "ERIKSSON" not in str(caught.value)


# --- the shape of the checking itself ---------------------------------------


def test_a_valid_flag_survives_being_built_again():
    """`__post_init__` checks and assigns nothing, so a flag is legal input.

    `dataclasses.replace` is the only way a caller re-checks a flag, and 6.2
    copies flags while attaching a region; a check that rewrote a field would
    turn that copy into a second measurement.
    """
    flag = a_flag()

    assert dataclasses.replace(flag) == flag
    assert dataclasses.replace(flag, value=0.5).value == 0.5
    assert dataclasses.replace(flag, region=None).region is None


def test_the_error_is_the_risk_packages_own_and_is_a_value_error():
    """1.4's reasoning again: a subclass keeps an existing `except ValueError` working.

    `mrz.MrzValueError` is the MRZ package's one error type, and a flag is
    emitted by tiers 1 and 2 and by the crossdoc rules, none of which import the
    MRZ parser -- so reusing it here would make a face-match flag depend on
    tier0. `APIError` is the HTTP boundary's and is not a value error at all.
    """
    assert issubclass(FlagValueError, ValueError)
    assert not issubclass(EvidenceFlag, BaseException)
    assert not issubclass(FlagValueError, mrz.MrzValueError)


def test_the_flag_module_imports_nothing_from_the_pipeline():
    """Walked rather than grepped, and the point is the absence of an import.

    `app.risk` is the one type every tier emits, whatever produced it, so a
    dependency from it onto `app.pipeline.tier0` would invert the layering and
    put a package-wide AST ban at risk.
    """
    tree = ast.parse(
        pathlib.Path(flags_module.__file__).read_text(encoding="utf-8")
    )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    assert imported == {"dataclasses", "numbers"}


def test_the_record_offers_no_public_method():
    """The "a record is data, never a second opinion" rule, pinned on the new hook.

    `__post_init__` is a dunder that refuses a malformed field and assigns
    nothing; a public method would be the thing this guards against, and adding
    one should have to delete this test on purpose.
    """
    assert [name for name in dir(EvidenceFlag) if not name.startswith("_")] == []


def test_the_module_exports_the_four_names_the_decision_names():
    """A `__all__` that names a fifth thing is a change to D6 someone has to see."""
    assert flags_module.__all__ == [
        "EvidenceFlag",
        "FlagValueError",
        "MIN_REGION_CORNERS",
        "WEIGHT_BANDS",
    ]
