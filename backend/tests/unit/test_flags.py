"""One structured finding: the record every rule answers with.

Task 5.1 asks for a model whose eleven fields can be constructed and read
back, and that is the whole claim here.  Nothing below says whether a value in
    ``[0, 1]`` is accepted or a band is one of the allowed ones -- that is the
next task, and a test written now against a range the model does not yet hold
would pass for a rule nobody wrote.  **6.2 made it twelve**, by adding
``field`` at the end; ``D17`` records why, and the field-order test below is
what says nothing shifted underneath the eleven.

**Every expected value below is written out longhand** rather than read back
from the record, so a flag that carried one field in another's slot produces a
mismatch rather than a match.  The field order is pinned as well, because it
is the order the fields are declared in and a rule that builds a flag
positionally would silently change meaning if a field were inserted.
"""

import dataclasses

import pytest

from app.risk.flags import EvidenceFlag

#: A field-shaped box: two lines of pixels, clockwise from the top left.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))


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


def test_every_field_reads_back():
    flag = a_flag()

    assert flag.id == "MRZ_DOB_CHECK_DIGIT_MISMATCH"
    assert flag.tier == 0
    assert flag.label == "Date-of-birth check digit does not match"
    assert flag.weight_band == "high"
    assert flag.value == 0.9
    assert flag.confidence == 1.0
    assert flag.region == ((10, 20), (110, 20), (110, 40), (10, 40))
    assert flag.expected == "4"
    assert flag.found == "7"
    assert flag.reason == (
        "The digits printed over the date of birth read 7; the characters "
        "themselves compute to 4."
    )
    assert flag.source_module == "app.pipeline.tier0.runner"
    assert flag.field == "date_of_birth"


def test_the_fields_are_the_twelve_the_task_names_in_order():
    """5.1 named eleven; 6.2 added ``field`` last, so nothing shifted.

    **The order is the claim, and the addition is at the end.**  A flag built
    positionally by a rule keeps the meaning it had, which is why the new
    field was not inserted next to the ones it belongs beside.
    """
    assert [f.name for f in dataclasses.fields(EvidenceFlag)] == [
        "id",
        "tier",
        "label",
        "weight_band",
        "value",
        "confidence",
        "region",
        "expected",
        "found",
        "reason",
        "source_module",
        "field",
    ]


def test_a_field_is_named_and_a_finding_with_no_field_says_none():
    """``D17``: where the finding is and what it is called are two questions."""
    assert a_flag().field == "date_of_birth"
    assert a_flag(field=None).field is None


def test_a_flag_with_no_region_carries_none():
    """A finding that cannot be located is a flag, not a missing one."""
    flag = a_flag(region=None)

    assert flag.region is None
    assert flag.id == "MRZ_DOB_CHECK_DIGIT_MISMATCH"


def test_a_flag_cannot_be_edited():
    """Evidence nobody may tidy: a changed field would read as a read one."""
    flag = a_flag()

    with pytest.raises(dataclasses.FrozenInstanceError):
        flag.value = 0.1
