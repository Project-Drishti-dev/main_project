"""17.13 -- every flag id the registry knows has a plain-language explanation.

The claim is a completeness claim, so it is held in both directions: every id in
:data:`app.risk.flag_ids.FLAG_IDS` has a sentence here, and no sentence is held
for an id the registry does not know.  The rest of the file is what makes a
sentence usable as a floor rather than as prose -- it carries no token the
verifier reads, it fills nothing out of the finding, two ids are never told apart
by the same sentence, and the line it completes is settled by its own flag's
data and by no other.
"""

import ast
import dataclasses
import inspect

import pytest

from app import explain
from app.explain import reasons, verifier
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag, FlagValueError

REASON_TEMPLATES = reasons.REASON_TEMPLATES
reason_for = reasons.reason_for

#: One finding as a rule hands it over, with only the id varying between cases.
FLAG_DATA = {
    "id": "DATE_EXPIRED",
    "tier": 0,
    "label": "Date of expiry is in the past",
    "weight_band": "high",
    "value": 0.87,
    "confidence": 0.91,
    "region": None,
    "expected": "2024-11-02",
    "found": "2023-11-02",
    "reason": "The printed expiry is before the reference date.",
    "source_module": "app.pipeline.tier0.dates",
    "field": "date_of_expiry",
}

#: Every id, in the registry's own order, so a case is named for the id it holds.
EVERY_ID = pytest.mark.parametrize(
    "flag_id", flag_ids.ALL_FLAG_IDS, ids=flag_ids.ALL_FLAG_IDS
)


def _flag(**overrides):
    """The flag :data:`FLAG_DATA` describes, as an :class:`EvidenceFlag`."""
    fields = dict(FLAG_DATA)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _line(flag):
    """The one line the fallback summary narrates ``flag`` on, template included."""
    return "- " + flag.id + ": " + reason_for(flag)


@EVERY_ID
def test_every_flag_id_the_registry_knows_has_a_reason_template(flag_id):
    """The claim 17.13 is named for: an id is never left with no explanation."""
    assert flag_id in REASON_TEMPLATES
    sentence = REASON_TEMPLATES[flag_id]
    assert isinstance(sentence, str)
    assert sentence == sentence.strip()
    assert sentence.endswith(".")


def test_the_table_holds_every_id_the_registry_knows_and_nothing_else():
    """A sentence for an id no rule can emit is prose about nothing."""
    assert set(REASON_TEMPLATES) == set(flag_ids.FLAG_IDS)
    assert len(REASON_TEMPLATES) == len(flag_ids.ALL_FLAG_IDS)


def test_the_table_runs_the_registry_in_cascade_order():
    """The order is the cascade, as it is in ``flag_ids`` and in the summary."""
    assert tuple(REASON_TEMPLATES) == flag_ids.ALL_FLAG_IDS


def test_no_flag_id_is_retyped_inside_the_table():
    """The key is the registry's own constant, so an id cannot be mistyped here."""
    tree = ast.parse(inspect.getsource(reasons))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert literals & set(flag_ids.FLAG_IDS) == set()


@EVERY_ID
def test_no_template_carries_a_token_the_verifier_reads(flag_id):
    """The floor cannot be refused whatever the flag data prints, because it names nothing."""
    sentence = REASON_TEMPLATES[flag_id]

    assert verifier.extract_numbers(sentence) == ()
    assert verifier.extract_dates(sentence) == ()
    assert verifier.extract_field_names(sentence) == ()


@EVERY_ID
def test_a_template_is_one_fixed_line_with_nothing_to_fill(flag_id):
    """A slot filled from the finding is a slot a document can write into."""
    sentence = REASON_TEMPLATES[flag_id]

    assert "`n" not in sentence
    assert "{" not in sentence and "}" not in sentence


def test_two_ids_are_never_told_apart_by_the_same_sentence():
    """One sentence per family would leave a rule's own finding unexplained."""
    assert len(set(REASON_TEMPLATES.values())) == len(REASON_TEMPLATES)


@EVERY_ID
def test_a_finding_is_explained_in_the_words_of_the_id_it_carries(flag_id):
    """The reader answers for the finding handed over, not for some other id."""
    assert reason_for(_flag(id=flag_id)) == REASON_TEMPLATES[flag_id]


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason": ""},
        {"reason": "A specific reason the rule wrote at the time."},
        {"expected": None, "found": None, "field": None},
        {"reason": "It expired on 2029-01-05 at 0.42 confidence."},
    ],
)
def test_the_sentence_is_the_same_whatever_the_finding_carries(overrides):
    """A fixed sentence cannot quote the document, so it cannot leak one either."""
    flag = _flag(id="WATCHLIST_HIT", **overrides)

    assert reason_for(flag) == REASON_TEMPLATES["WATCHLIST_HIT"]


@EVERY_ID
def test_a_finding_that_wrote_no_reason_is_still_explained(flag_id):
    """A blank reason is the gap this table exists to close."""
    flag = _flag(id=flag_id, reason="")

    assert reason_for(flag).strip() == REASON_TEMPLATES[flag_id]


@EVERY_ID
def test_the_floor_line_is_held_to_the_same_rule_as_the_summary(flag_id):
    """17.5's line is settled by the flag data beside it, template included."""
    flag = _flag(id=flag_id, reason="")

    assert verifier.verify_summary(_line(flag), dataclasses.asdict(flag)) == (True, ())


def test_the_floor_line_is_settled_by_its_own_flags_data_and_by_no_other():
    """The case above cannot pass from a line that carries nothing worth settling."""
    flag = _flag(id="QUALITY_GLARE", reason="")

    assert verifier.verify_summary(_line(flag), [dataclasses.asdict(_flag())]) == (
        False,
        ("QUALITY_GLARE",),
    )


def test_a_finding_missing_its_id_is_refused():
    """A finding with no id names no rule, so there is no sentence to give it."""

    class _Bare:
        """A finding carrying nothing at all."""

    with pytest.raises(FlagValueError):
        reason_for(_Bare())


@pytest.mark.parametrize("flag_id", [None, 7, b"DATE_EXPIRED", ["DATE_EXPIRED"]])
def test_an_id_that_is_not_text_is_refused(flag_id):
    """The id is a lookup key, and anything else is not one."""
    with pytest.raises(FlagValueError):
        reason_for(_flag(id=flag_id))


@pytest.mark.parametrize(
    "flag_id", ["", "   ", "date_expired", "DATE_EXPIRED_TYPO", "MRZ_DOB_CHECK_DIGIT"]
)
def test_an_id_the_registry_does_not_know_is_refused(flag_id):
    """An invented sentence would be a claim about a rule that does not exist."""
    with pytest.raises(FlagValueError) as refusal:
        reason_for(_flag(id=flag_id))

    assert "app.risk.flag_ids" in str(refusal.value)
    if flag_id.strip():
        assert flag_id not in str(refusal.value)


def test_the_table_is_read_only():
    """The table is the record, so nothing may amend it after it is imported."""
    with pytest.raises(TypeError):
        REASON_TEMPLATES["DATE_EXPIRED"] = "The officer was told something else."


def test_the_module_imports_only_the_registry_and_the_error():
    """An officer-facing sentence must not pull a detector in to be written."""
    tree = ast.parse(inspect.getsource(reasons))

    assert sorted(
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ) == [
        "from app.risk import flag_ids",
        "from app.risk.flags import FlagValueError",
        "from types import MappingProxyType",
    ]


def test_the_package_re_exports_nothing_so_a_sentence_is_reached_from_its_module():
    """A caller says which module it took the sentence from, as everywhere in this package."""
    assert not hasattr(explain, "reason_for")
