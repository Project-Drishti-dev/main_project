"""A flag's value mapped into the engine's range, or a refusal.

Task 7.4 asks for ``normalise_value(flag)`` and names three cases: a normal
flag, a ``None`` value, and a boolean-style flag.  **The map is the identity**
-- a flag's ``value`` is already inside ``[0, 1]`` (``D6``), which is the
range the engine sums in -- so what is held here is the decision about whether
a value may be summed at all, and the ``float`` the answer always is.

**Two of the three named cases disagree with ``D6``, and neither is softened
to make one reachable.**  ``D6`` holds ``value`` to the closed unit interval
and refuses ``None``, so a ``None`` value cannot be built as an
``EvidenceFlag`` at all.  A boolean *is* buildable -- a boolean is inside
``[0, 1]`` in Python's own arithmetic -- and the gate refuses it where the
record's own check accepts it, because a boolean says a rule fired rather than
how strongly.  :class:`DraftFinding` is the other shape the gate exists for: a
rule's own finding before it became a flag, and, in Part 8, a flag read back
from storage where ``null`` is a legal value.  ``D24`` records the
reconciliation and 7.4's own premise.

**Every refusal is claimed as a failure, not as an absence of an exception**,
and the text a value might carry is asserted absent from the message that
refused it.
"""

import ast
import dataclasses
import pathlib

import numpy as np
import pytest

from app.risk import values as values_module
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.values import normalise_value
from app.risk.weightsets.loader import load_weightset
from app.risk.weightsets.lookup import weight_for

#: A field-shaped box: two lines of pixels, clockwise from the top left, the
#: shape 4.12's `_box_polygon` writes and 6.2 hands over unchanged.
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


@dataclasses.dataclass(frozen=True)
class DraftFinding:
    """A record carrying a ``value`` that a well-formed flag cannot.

    ``D6``'s constructor check is why the refusals are written against this
    rather than against a flag: a ``None``, a string or a ``1.4`` cannot be
    built into one.  A rule's own result has this shape before it becomes a
    flag, and Part 8 reads flags back out of storage, where ``null`` is a legal
    value and a number written by an older ruleset is not a promise.
    """

    value: object


# --- the map itself --------------------------------------------------------


def test_a_normal_flag_normalises_to_its_own_value():
    """The case the task names first, and the whole of the claim: ``0.9`` is
    ``0.9``.
    """
    flag = a_flag(value=0.9)

    assert normalise_value(flag) == 0.9


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(0.0, id="zero"),
        pytest.param(1.0, id="one"),
        pytest.param(0.5, id="midway"),
        pytest.param(0.9, id="strong"),
        pytest.param(0.999999, id="just-below-one"),
        pytest.param(1e-9, id="just-above-zero"),
        pytest.param(0, id="zero-as-an-int"),
        pytest.param(1, id="one-as-an-int"),
        pytest.param(np.float64(0.5), id="a-numpy-float"),
        pytest.param(np.float32(0.5), id="a-numpy-float32"),
    ],
)
def test_a_value_inside_the_range_is_its_own_normalised_form(value):
    """The identity is pinned over the whole interval, both ends included.

    ``0`` and ``1`` are inside a *closed* interval, so a normalise written
    with a strict comparison would refuse them.  The answer is a ``float``
    wherever the record holds an ``int`` or a numpy scalar, because 7.5
    multiplies whatever this returns.
    """
    normalised = normalise_value(a_flag(value=value))

    assert normalised == value
    assert type(normalised) is float


def test_the_value_is_not_rescaled_rounded_or_clipped():
    """A value in range is a number of its own, not a share of the maximum.

    The engine's range is the flag's own range, so there is no divisor, no
    rounding step and no ceiling: ``0.9`` stays ``0.9`` and ``0.1`` stays
    ``0.1``, and neither is nudged towards the middle of the interval.
    """
    values = [0.1, 0.25, 0.5, 0.75, 0.9]

    assert [normalise_value(a_flag(value=v)) for v in values] == values


def test_normalising_a_flag_does_not_amend_it():
    """A flag is evidence, so reading its value is not a write to it.

    The record is frozen, so the only way a value could change is a coerced
    one held somewhere else; a screening replayed from its recorded flags has
    to read the numbers the rules wrote down.
    """
    flag = a_flag(value=0.9)

    before = dataclasses.replace(flag)
    normalise_value(flag)

    assert flag == before
    assert flag.value == 0.9


# --- the two cases `D6` and this task disagree on ---------------------------


def test_a_none_value_is_refused_rather_than_scored_as_zero():
    """The case the task names, and the one ``D6`` makes unreachable.

    A rule that measured nothing is silence, and silence is not a finding of no
    strength: ``F = 0`` would put the rule's term in 7.5's sum as a real
    contribution of nothing, and an unanswered question reads as a cleared
    document.  ``DraftFinding`` is the shape such a record has, and
    ``D6``'s own check is below.
    """
    with pytest.raises(FlagValueError) as caught:
        normalise_value(DraftFinding(value=None))

    assert "value" in str(caught.value)
    assert "None" in str(caught.value)


def test_the_none_case_is_not_reachable_through_the_record_itself():
    """So the test above is a real gate rather than a fiction.

    ``D6`` refuses a ``None`` at construction, so the flag the engine is
    handed can never carry one; the refusal here is about the records the
    engine is *not* handed by a rule, and pinning that is what says which of
    the two the guard is for.
    """
    with pytest.raises(FlagValueError) as caught:
        a_flag(value=None)

    assert "value" in str(caught.value)


@pytest.mark.parametrize("fired", [True, False], ids=["true", "false"])
def test_a_boolean_flag_is_refused_rather_than_read_as_one_or_zero(fired):
    """The third named case, and the one ``D6``'s closed interval lets build.

    A boolean is inside ``[0, 1]`` in Python's own arithmetic, so the record
    accepts it and the flag below is real.  The gate refuses it: ``True``
    scored as ``1.0`` would make every rule that fired a maximum-strength
    finding, and ``False`` scored as ``0.0`` would put "this rule did not fire"
    into the sum as a contribution of nothing -- the same silent zero 7.3
    refuses an unweighted id for.
    """
    flag = a_flag(value=fired)

    with pytest.raises(FlagValueError) as caught:
        normalise_value(flag)

    assert "value" in str(caught.value)
    assert "boolean" in str(caught.value)


# --- everything else that is not a number the sum may carry -----------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0.9", id="text"),
        pytest.param([0.9], id="a-list"),
        pytest.param({"value": 0.9}, id="a-dict"),
        pytest.param(1.4, id="just-above-one"),
        pytest.param(-0.0001, id="just-below-zero"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param(np.bool_(True), id="a-numpy-boolean"),
    ],
)
def test_a_value_that_is_not_a_score_is_refused(value):
    """The rest of the routes to a number the file did not measure.

    A ``nan`` is the quietest of them: every comparison against it is false,
    so a ``nan`` reaching 7.5 poisons the sum with no error anywhere and the
    band it lands in is decided by nothing.  ``1.4`` and ``-0.0001`` are the
    5.2 clipping argument again -- a contribution of ``1.0`` for a finding
    that measured ``1.4`` is a difference no score downstream could show.
    """
    with pytest.raises(FlagValueError) as caught:
        normalise_value(DraftFinding(value=value))

    assert "value" in str(caught.value)


@pytest.mark.parametrize(
    "flag",
    [
        pytest.param(object(), id="a-record-with-no-value"),
        pytest.param(None, id="none"),
        pytest.param("MRZ_EXPIRED", id="a-flag-id"),
        pytest.param(0.9, id="a-number-that-is-not-a-flag"),
    ],
)
def test_something_that_is_not_a_record_carrying_a_value_is_refused(flag):
    """A flag id, or a bare number, is a caller bug rather than a refusal of
    value: the answer would be an ``AttributeError``, which is not the
    ``ValueError`` a caller around the scoring is catching.
    """
    with pytest.raises(FlagValueError) as caught:
        normalise_value(flag)

    assert "value" in str(caught.value)


def test_the_refusal_is_a_flag_value_error_and_a_value_error():
    """``D6``'s error type, so an ``except ValueError`` around the scoring keeps
    working and a message says a bad value rather than a bad caller.
    """
    with pytest.raises(ValueError) as caught:
        normalise_value(DraftFinding(value=1.4))

    assert isinstance(caught.value, FlagValueError)
    assert not isinstance(caught.value, (TypeError, AttributeError))


def test_the_message_never_quotes_the_value_it_refused():
    """A value is exactly where printed text arrives, and ``AGENTS.md`` bans
    identity data in logs -- so the refusal names the field and the type and
    leaves the value in the caller's own frame.
    """
    with pytest.raises(FlagValueError) as caught:
        normalise_value(DraftFinding(value="ERIKSSON<<ANNA MARIA"))

    assert "value" in str(caught.value)
    assert "ERIKSSON" not in str(caught.value)


# --- the seam 7.5 is written against ---------------------------------------


def test_the_two_halves_of_a_term_pair_up_over_one_flag():
    """7.3 answers the ``w`` and this answers the ``F``, and both are floats.

    The product is one term of ``R = sum(w_i * F_i)``, and it is checked here
    rather than in 7.5 because a term that cannot be multiplied is this
    module's to prevent.
    """
    flag = a_flag(value=0.5)
    loaded = load_weightset()

    term = weight_for(loaded, flag.id) * normalise_value(flag)

    assert term == weight_for(loaded, flag.id) * 0.5
    assert isinstance(term, float)


def test_the_module_imports_the_flag_record_and_nothing_else():
    """Walked rather than grepped, and the point is the absence of an import.

    ``app.risk`` must not import ``app.pipeline.tier0``, and the engine's gate
    is the last place in the package where that could happen: a weightset and
    a value both arrive from the tiers, and a gate that reached back into one
    would put a tier0 import under ``D6``'s package-wide rule.
    """
    tree = ast.parse(
        pathlib.Path(values_module.__file__).read_text(encoding="utf-8")
    )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    assert imported == {"app.risk.flags"}


def test_the_module_exports_the_one_name_the_task_names():
    """The range is 5.2's and the refusal is ``D6``'s; this module adds a gate
    and no vocabulary of its own.
    """
    assert values_module.__all__ == ["normalise_value"]
