"""`documents_consistent`: a visa must name a passport the case holds.

16.5 names one case -- a visa referencing an unknown passport -- and the rest
of the surface is pinned here so a later change to it is a decision rather
than a drift.  D129.
"""

import dataclasses

import pytest

from app.pipeline.crossdoc import documents as documents_module
from app.pipeline.crossdoc.documents import (
    CONSISTENT,
    INCONSISTENT,
    NOT_CONFIGURED,
    STATUSES,
    CaseConsistency,
    CaseDocument,
    documents_consistent,
)
from app.pipeline.tier0.mrz import FILLER
from app.pipeline.tier0.td3 import MrzValueError
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag


def passport(number="AB1234567"):
    return CaseDocument(role="passport", document_number=number)


def visa(number="V7654321", reference="AB1234567"):
    return CaseDocument(
        role="visa",
        document_number=number,
        referenced_passport_number=reference,
    )


# --- the case tasks.md names -------------------------------------------------


def test_a_visa_referencing_an_unknown_passport_raises_a_flag():
    result = documents_consistent([passport("AB0000000"), visa(reference="ZZ9999999")])

    assert len(result.flags) == 1
    assert result.flags[0].id == flag_ids.CROSSDOC_UNKNOWN_PASSPORT_REFERENCE


def test_that_flag_is_the_one_the_vocabulary_holds():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.flags[0].id in flag_ids.FLAG_IDS


def test_a_case_holding_no_passport_at_all_is_inconsistent():
    result = documents_consistent([visa(reference="AB1234567")])

    assert result.status == INCONSISTENT
    assert len(result.flags) == 1


# --- the case that agrees ----------------------------------------------------


def test_a_visa_referencing_a_passport_in_the_case_raises_no_flag():
    result = documents_consistent([passport(), visa()])

    assert result.flags == ()
    assert result.status == CONSISTENT
    assert result.compared == 1


@pytest.mark.parametrize(
    ("printed", "referenced"),
    [
        ("AB1234567", "ab1234567"),
        ("AB1234567", " AB1234567 "),
        ("AB1234567", "AB1234567" + FILLER),
        ("AB1234567" + FILLER, "AB1234567"),
    ],
)
def test_the_same_number_printed_differently_is_one_number(printed, referenced):
    result = documents_consistent([passport(printed), visa(reference=referenced)])

    assert result.flags == ()


# --- the key is not a name key (D127) ---------------------------------------


def test_a_digraph_in_a_number_is_not_folded():
    result = documents_consistent(
        [passport("MUELLER1"), visa(reference="MULLER1")]
    )

    assert len(result.flags) == 1


# --- what was compared -------------------------------------------------------


def test_a_case_with_no_visa_compares_nothing():
    result = documents_consistent([passport(), passport("CD7654321")])

    assert result.compared == 0
    assert result.flags == ()
    assert result.status == NOT_CONFIGURED


def test_an_empty_case_compares_nothing():
    result = documents_consistent([])

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_a_visa_printing_no_reference_is_not_compared():
    result = documents_consistent([passport(), visa(reference=None)])

    assert result.compared == 0
    assert result.flags == ()
    assert result.status == NOT_CONFIGURED


def test_an_all_filler_reference_is_not_compared():
    result = documents_consistent([passport(), visa(reference=FILLER * 9)])

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_an_unreadable_reference_is_not_read_as_a_mismatch():
    """D115: a measurement that could not be taken is not a finding."""
    result = documents_consistent([passport(), visa(reference=None)])

    assert result.status != INCONSISTENT


def test_a_passport_printing_nothing_cannot_satisfy_a_reference():
    result = documents_consistent([passport(FILLER * 9), visa()])

    assert len(result.flags) == 1


def test_two_visas_naming_one_passport_compare_twice():
    result = documents_consistent([passport(), visa(), visa("V1111111")])

    assert result.compared == 2
    assert result.flags == ()


def test_two_visas_naming_nothing_raise_two_flags():
    result = documents_consistent([visa(reference="ZZ0000001"), visa(reference="ZZ0000002")])

    assert len(result.flags) == 2
    assert result.compared == 2


def test_one_flag_per_offending_visa_and_none_for_the_rest():
    result = documents_consistent(
        [passport(), visa(), visa("V1111111", reference="ZZ0000001")]
    )

    assert len(result.flags) == 1
    assert result.compared == 2


@pytest.mark.parametrize("role", ["id", "passport"])
def test_an_id_and_a_passport_are_never_a_reference(role):
    result = documents_consistent([passport(), CaseDocument(role=role, document_number="X")])

    assert result.compared == 0


def test_the_flags_come_back_in_the_order_the_documents_were_given():
    case = [visa("V1", reference="ZZ0000001"), passport(), visa("V2", reference="ZZ0000002")]

    first = documents_consistent(case)
    second = documents_consistent(list(reversed(case)))

    assert first.flags == second.flags
    assert first.compared == second.compared == 2


def test_the_answer_does_not_depend_on_whether_the_case_is_a_tuple():
    case = [passport(), visa()]

    assert documents_consistent(case) == documents_consistent(tuple(case))


def test_a_generator_is_measured_once_and_handed_on_whole():
    result = documents_consistent(document for document in [passport(), visa()])

    assert result.compared == 1


# --- the flag's own shape ----------------------------------------------------


def test_the_flag_reports_itself_under_the_crossdoc_tier():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.flags[0].tier == "crossdoc"


def test_the_flag_carries_the_band_the_weightset_holds_it_under():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.flags[0].weight_band == "review"


def test_the_flag_names_the_field_a_visa_prints_the_number_in():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.flags[0].field == "personal_number"


def test_the_flag_points_at_nothing_on_any_one_document():
    """A cross-document finding is about two pages, so neither frame locates it."""
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.flags[0].region is None


def test_the_flag_carries_no_passport_number_on_any_of_its_fields():
    """The one rule the whole project holds: a flag is never identity data."""
    result = documents_consistent([visa(reference="ZZ9999999")])
    flag = result.flags[0]

    assert "ZZ9999999" not in flag.label
    assert "ZZ9999999" not in flag.reason
    assert flag.expected is None
    assert flag.found is None


def test_the_flag_reports_itself_from_this_module():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.flags[0].source_module == "app.pipeline.crossdoc.documents"


def test_every_flag_is_an_evidence_flag():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert all(isinstance(flag, EvidenceFlag) for flag in result.flags)


def test_the_flags_carry_the_reference_count_only_as_a_count():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert result.compared == 1
    assert "ZZ9999999" not in repr(result)


def test_a_consistency_record_cannot_be_edited_after_it_is_answered():
    answered = documents_consistent([visa(reference="ZZ9999999")])

    with pytest.raises(dataclasses.FrozenInstanceError):
        answered.status = CONSISTENT


def test_a_document_record_cannot_be_edited_after_it_is_built():
    built = passport()

    with pytest.raises(dataclasses.FrozenInstanceError):
        built.document_number = "ZZ9999999"


# --- refusals ---------------------------------------------------------------


def test_a_role_outside_the_vocabulary_is_refused():
    with pytest.raises(MrzValueError):
        CaseDocument(role="residence_permit", document_number="AB1234567")


@pytest.mark.parametrize("role", [None, 42, ["passport"]])
def test_a_role_that_is_not_one_of_three_strings_is_refused(role):
    with pytest.raises(MrzValueError):
        CaseDocument(role=role, document_number="AB1234567")


def test_a_document_number_that_is_not_a_string_is_refused():
    with pytest.raises(MrzValueError):
        CaseDocument(role="passport", document_number=1234567)


def test_a_reference_that_is_not_a_string_is_refused():
    with pytest.raises(MrzValueError):
        CaseDocument(role="visa", document_number="V1", referenced_passport_number=1234)


@pytest.mark.parametrize("role", ["passport", "id"])
def test_a_non_visa_carrying_a_reference_is_refused(role):
    with pytest.raises(MrzValueError):
        CaseDocument(
            role=role, document_number="AB1234567", referenced_passport_number="AB1234567"
        )


def test_a_visa_with_no_reference_at_all_is_accepted():
    built = CaseDocument(role="visa", document_number="V1")

    assert built.referenced_passport_number is None


@pytest.mark.parametrize("case", [None, 42, {"passport": "AB1234567"}])
def test_something_that_is_not_a_sequence_of_documents_is_refused(case):
    with pytest.raises(MrzValueError):
        documents_consistent(case)


def test_one_string_is_refused_as_a_case():
    with pytest.raises(MrzValueError):
        documents_consistent("AB1234567")


def test_a_string_is_refused_before_it_is_measured_into_documents():
    """A string is a sequence of characters, so the mistake is named first."""
    with pytest.raises(MrzValueError) as caught:
        documents_consistent("AB1234567")

    assert "sequence of documents" in str(caught.value)
    assert "CaseDocument" not in str(caught.value)


@pytest.mark.parametrize("not_a_document", [None, 42, "passport", {"role": "visa"}])
def test_a_case_holding_something_that_is_not_a_document_is_refused(not_a_document):
    with pytest.raises(MrzValueError):
        documents_consistent([passport(), not_a_document])


def test_a_refusal_names_the_type_it_was_given_and_not_the_number():
    with pytest.raises(MrzValueError) as caught:
        documents_consistent([CaseDocument(role="visa", document_number="V1", referenced_passport_number=1234)])

    assert "int" in str(caught.value)
    assert "1234" not in str(caught.value)


def test_a_refusal_never_prints_the_document_number_it_was_holding():
    with pytest.raises(MrzValueError) as caught:
        documents_consistent("AB1234567")

    assert "AB1234567" not in str(caught.value)


def test_a_refusal_is_a_value_error():
    assert issubclass(MrzValueError, ValueError)


def test_a_status_outside_the_vocabulary_is_refused():
    with pytest.raises(MrzValueError):
        CaseConsistency(status="clean", flags=(), compared=1)


def test_a_consistency_record_holding_something_that_is_not_a_flag_is_refused():
    with pytest.raises(MrzValueError):
        CaseConsistency(status=CONSISTENT, flags=("a flag",), compared=1)


def test_a_comparison_count_that_is_not_a_whole_number_is_refused():
    with pytest.raises(MrzValueError):
        CaseConsistency(status=CONSISTENT, flags=(), compared=1.0)


# --- the surface itself ------------------------------------------------------


def test_the_module_exports_exactly_its_own_names():
    assert documents_module.__all__ == [
        "CONSISTENT",
        "INCONSISTENT",
        "NOT_CONFIGURED",
        "STATUSES",
        "CaseConsistency",
        "CaseDocument",
        "documents_consistent",
    ]


def test_the_three_statuses_are_the_only_ones_there_are():
    assert STATUSES == (CONSISTENT, INCONSISTENT, NOT_CONFIGURED)


def test_consistent_is_not_the_answer_for_a_case_that_compared_nothing():
    assert documents_consistent([passport()]).status == NOT_CONFIGURED


def test_the_flag_count_and_the_status_are_the_same_fact_read_twice():
    result = documents_consistent([visa(reference="ZZ9999999")])

    assert bool(result.flags) == (result.status == INCONSISTENT)


def test_the_module_raises_only_the_tier0_error():
    assert documents_module.MrzValueError is MrzValueError


def test_the_module_reads_no_clock_and_no_document_image():
    """The 3.12/3.13 rule: this module resolves no day and reads no frame.

    16.6 widened ``CaseDocument`` with the two days a window prints, so the
    check is what the rule always meant: **no call reaches a clock**, and no
    image library is imported.  Asserting the word ``datetime`` is absent would
    now fail on a type annotation rather than on a rule that resolves a day.
    """
    import ast
    from pathlib import Path

    source = Path(documents_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in {"now", "today", "utcnow"}
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            (alias.name or "").split(".")[0] in {"cv2", "numpy"}
            for alias in node.names
        )
        for node in ast.walk(tree)
    )


def test_the_module_names_no_rule_of_its_own():
    """A cross-reference is an exact match or it is not; no threshold here."""
    import inspect

    assert "tolerance" not in inspect.signature(documents_consistent).parameters
