"""The weight lookup answers a flag id with a number, or it raises.

Task 7.3 is the first thing written against 7.2's loader rather than against
the file 7.1 wrote, and the one claim it exists to hold is the failure the
engine's sum cannot survive: **an id the weightset carries no row for raises
rather than scoring zero.**  ``R = sum(w_i * F_i)`` treats a missing weight as
a finding worth nothing, so the flag reaches the officer's list of reasons
having moved nothing, and a screening can be answered ``low`` on a finding the
weightset simply did not mention.

**The lookup is a function over the loaded record**, not a second reader of
``v1.yaml``, so a caller is answered from the rows it is already holding.

**The tests are written against ``flag_ids.FLAG_IDS``**: every id in the
vocabulary resolves, and an id outside it is how the raise is reached, since
7.1's completeness test means the committed file cannot raise.  An id the
vocabulary has and the file does not is a weightset fault, held by 7.1, not
here.
"""

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from app.risk import flag_ids
from app.risk.weightsets import loader
from app.risk.weightsets.loader import Weightset, WeightsetError, load_weightset
from app.risk.weightsets.lookup import WEIGHT_KEY, weight_for


def row(**fields):
    """A weightset row as the loader hands rows back: a read-only mapping."""
    return MappingProxyType(fields)


@pytest.mark.parametrize("flag_id", flag_ids.FLAG_IDS)
def test_every_id_in_the_vocabulary_resolves_to_the_weight_the_file_names(flag_id):
    """The whole vocabulary is answerable, and answered with the file's number.

    Written over :data:`flag_ids.FLAG_IDS` rather than over a hand-picked id,
    so an id added to the vocabulary is answered without this file being
    edited, and the weight compared is the one the row carries rather than a
    number retyped here.
    """
    loaded = load_weightset()

    weight = weight_for(loaded, flag_id)

    assert weight == loaded.flags[flag_id][WEIGHT_KEY]
    assert isinstance(weight, float)
    assert weight > 0


@pytest.mark.parametrize(
    "flag_id",
    [
        pytest.param("MRZ_DOB_CHECK_DIGIT_MISMATCH_COMPOSITE", id="typo_of_a_real_id"),
        pytest.param("QUALITY_GATE_LOW_RESOLUTION", id="unknown_family"),
        pytest.param("", id="empty"),
    ],
)
def test_an_id_the_vocabulary_does_not_have_raises(flag_id):
    """The refusal the task is named for, and the id is named in it.

    The id is a rule name and nothing printed off a document, so the message
    may carry it: a refusal nobody can locate is one nobody can fix.
    """
    loaded = load_weightset()

    with pytest.raises(WeightsetError) as raised:
        weight_for(loaded, flag_id)

    assert flag_id in str(raised.value)


def test_the_refusal_is_a_valueerror_and_not_a_keyerror():
    """``D23``'s decision, held rather than remembered.

    A ``KeyError`` reads like a bug in the caller rather than a flag the
    weightset has no weight for, and it is not a ``ValueError``, so a caller
    already catching ``ValueError`` around the code that loads a weightset
    does not catch this.
    """
    with pytest.raises(ValueError) as raised:
        weight_for(
            Weightset(ruleset_version="0.1.0", flags=MappingProxyType({})),
            "MRZ_EXPIRED",
        )

    assert not isinstance(raised.value, KeyError)


def test_a_weightset_with_no_rows_at_all_raises_rather_than_answering_zero():
    """The whole failure 7.2 refused an absent file over, reached from a record.

    An empty weightset is exactly what a caller holding a failed load looks
    like if the refusal is passed over, so the answer has to be a refusal too
    rather than ``0.0``.
    """
    empty = Weightset(ruleset_version="0.1.0", flags=MappingProxyType({}))

    with pytest.raises(WeightsetError, match="MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH"):
        weight_for(empty, "MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH")


def test_a_row_with_no_weight_raises_rather_than_answering_zero():
    """A row can be present and still be worth nothing to the engine.

    ``band`` alone is a legal-looking row and a weight read from it with
    ``.get`` is ``0.0``, which is the silent score 7.3 exists to remove.
    """
    partial = Weightset(
        ruleset_version="0.1.0",
        flags=MappingProxyType({"MRZ_EXPIRED": row(band="high")}),
    )

    with pytest.raises(WeightsetError, match=WEIGHT_KEY):
        weight_for(partial, "MRZ_EXPIRED")


@pytest.mark.parametrize(
    "weight",
    [
        pytest.param("60", id="text"),
        pytest.param(None, id="none"),
        pytest.param(True, id="boolean"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
    ],
)
def test_a_weight_that_is_not_a_real_number_is_refused(weight):
    """Four ways a row becomes a number that is not one, and none is a score.

    A boolean is inside ``[0, 1]`` in Python's own arithmetic and a string
    raises three modules later inside 7.5's multiply; ``nan`` is the quieter
    one, because every comparison against it is false and the band a ``nan``
    score lands in is decided by nothing at all.
    """
    broken = Weightset(
        ruleset_version="0.1.0",
        flags=MappingProxyType({"MRZ_EXPIRED": row(weight=weight, band="high")}),
    )

    with pytest.raises(WeightsetError, match=WEIGHT_KEY):
        weight_for(broken, "MRZ_EXPIRED")


def test_a_row_that_is_not_a_mapping_is_refused():
    """7.2 passes a non-mapping row through, so the lookup has to refuse one.

    The loader's claim is that a row's *shape* is 7.1's to judge, and this is
    where a shape that never reached the file's test is refused.
    """
    not_a_row = Weightset(
        ruleset_version="0.1.0", flags=MappingProxyType({"MRZ_EXPIRED": 60})
    )

    with pytest.raises(WeightsetError, match="MRZ_EXPIRED"):
        weight_for(not_a_row, "MRZ_EXPIRED")


def test_the_lookup_answers_from_the_record_it_is_handed_and_not_from_the_file(monkeypatch):
    """A second reader of ``v1.yaml`` would answer from a file, not a record.

    The record handed in carries a weight no committed file has -- 41 appears
    nowhere in ``v1.yaml`` -- so a lookup that re-read the file could not
    answer it.  :func:`loader._read` is replaced with a call that fails, so a
    lookup opening the package would fail the test rather than quietly pass.
    """
    monkeypatch.setattr(
        loader, "_read", lambda _name: pytest.fail("the lookup read the file")
    )
    handed = Weightset(
        ruleset_version="9.9.9",
        flags=MappingProxyType({"MRZ_EXPIRED": MappingProxyType({"weight": 41})}),
    )

    assert weight_for(handed, "MRZ_EXPIRED") == 41.0


def test_a_row_is_a_mapping_and_the_lookup_does_not_write_to_it():
    """The record stays frozen through the lookup: reading a weight is not a write.

    Held because the lookup is the first production code to read a row, and a
    row it could amend is a weight the version it quotes no longer describes.
    """
    loaded = load_weightset()

    weight_for(loaded, flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH)

    assert isinstance(loaded.flags[flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH], Mapping)
    with pytest.raises(TypeError):
        loaded.flags[flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH]["weight"] = 1
