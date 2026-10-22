"""`visa_validity_consistent`: the visa's printed window must cover the day.

16.6 names one case -- a visa whose validity window does not cover the travel
date -- and the rest of the surface is pinned here so a later change to it is
a decision rather than a drift.  The travel date is an argument and never a
field, and the window is closed at both ends: D130.
"""

import dataclasses
import datetime

import pytest

from app.pipeline.crossdoc import validity as validity_module
from app.pipeline.crossdoc.documents import (
    CONSISTENT,
    INCONSISTENT,
    NOT_CONFIGURED,
    VISA,
    CaseDocument,
)
from app.pipeline.crossdoc.validity import visa_validity_consistent
from app.pipeline.tier0.td3 import MrzValueError
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag
from app.risk.weightsets import loader

TRAVEL = datetime.date(2026, 6, 15)


def day(text):
    return datetime.date(*(int(part) for part in text.split("-")))


def visa(number="V7654321", first="2026-01-01", last="2026-12-31"):
    return CaseDocument(
        role=VISA,
        document_number=number,
        referenced_passport_number="AB1234567",
        valid_from=day(first) if first else None,
        valid_until=day(last) if last else None,
    )


def passport(number="AB1234567", first="2020-01-01", last="2020-01-01"):
    return CaseDocument(
        role="passport",
        document_number=number,
        valid_from=day(first) if first else None,
        valid_until=day(last) if last else None,
    )


# --- the case tasks.md names -------------------------------------------------


def test_a_visa_whose_window_ended_before_the_travel_date_raises_a_flag():
    result = visa_validity_consistent(
        [visa(last="2026-06-14")], datetime.date(2026, 6, 15)
    )

    assert len(result.flags) == 1
    assert result.flags[0].id == flag_ids.CROSSDOC_VALIDITY_WINDOW_MISMATCH


def test_a_visa_whose_window_opens_after_the_travel_date_raises_a_flag():
    result = visa_validity_consistent(
        [visa(first="2026-06-16")], datetime.date(2026, 6, 15)
    )

    assert len(result.flags) == 1
    assert result.flags[0].id == flag_ids.CROSSDOC_VALIDITY_WINDOW_MISMATCH


def test_that_flag_is_the_one_the_vocabulary_holds():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].id in flag_ids.FLAG_IDS


def test_a_case_holding_no_visa_at_all_is_not_configured():
    result = visa_validity_consistent([passport()], TRAVEL)

    assert result.status == NOT_CONFIGURED
    assert result.compared == 0
    assert result.flags == ()


# --- the case that agrees ----------------------------------------------------


def test_a_visa_whose_window_covers_the_travel_date_raises_no_flag():
    result = visa_validity_consistent([visa()], TRAVEL)

    assert result.flags == ()
    assert result.status == CONSISTENT
    assert result.compared == 1


@pytest.mark.parametrize("travel", ["2026-01-01", "2026-06-15", "2026-12-31"])
def test_the_window_is_closed_at_both_ends(travel):
    """D130: valid *from* the first day and *until* the last day."""
    result = visa_validity_consistent([visa()], day(travel))

    assert result.flags == ()


@pytest.mark.parametrize("travel", ["2025-12-31", "2027-01-01"])
def test_one_day_outside_the_window_is_a_flag(travel):
    result = visa_validity_consistent([visa()], day(travel))

    assert len(result.flags) == 1


def test_a_window_that_is_one_day_wide_covers_that_one_day():
    result = visa_validity_consistent(
        [visa(first="2026-06-15", last="2026-06-15")], datetime.date(2026, 6, 15)
    )

    assert result.flags == ()
    assert result.compared == 1


# --- the travel date is injected (D130) -------------------------------------


def test_the_travel_date_is_an_argument_and_not_a_field_of_a_document():
    """A document must not carry the day it is checked against."""
    assert "travel" not in CaseDocument.__dataclass_fields__
    assert "travel_date" not in CaseDocument.__dataclass_fields__


def test_the_printed_window_is_a_field_of_the_document():
    assert CaseDocument.__dataclass_fields__["valid_from"].default is None
    assert CaseDocument.__dataclass_fields__["valid_until"].default is None


def test_a_timestamp_travel_date_is_reduced_to_its_day():
    stamped = datetime.datetime(2026, 6, 15, 23, 59, 59)

    result = visa_validity_consistent([visa(first="2026-06-16")], stamped)

    assert len(result.flags) == 1


def test_a_timestamp_is_compared_as_the_day_it_falls_on():
    """The window closes on 2026-06-15, and 23:59 on that day is still that day."""
    result = visa_validity_consistent(
        [visa(first="2026-01-01", last="2026-06-15")],
        datetime.datetime(2026, 6, 15, 23, 59, 59),
    )

    assert result.flags == ()


def test_the_same_travel_date_answers_the_same_every_time():
    case = [visa(last="2020-01-01")]

    first = visa_validity_consistent(case, TRAVEL)
    second = visa_validity_consistent(case, TRAVEL)

    assert first == second


# --- what was compared -------------------------------------------------------


def test_a_visa_printing_no_window_is_not_compared():
    result = visa_validity_consistent([visa(first=None, last=None)], TRAVEL)

    assert result.compared == 0
    assert result.flags == ()
    assert result.status == NOT_CONFIGURED


def test_a_case_of_visas_printing_no_window_is_not_configured():
    result = visa_validity_consistent(
        [visa("V1", None, None), visa("V2", None, None)], TRAVEL
    )

    assert result.status == NOT_CONFIGURED
    assert result.compared == 0


def test_an_empty_case_compares_nothing():
    result = visa_validity_consistent([], TRAVEL)

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_one_offending_visa_among_two_is_one_flag_and_two_comparisons():
    result = visa_validity_consistent(
        [visa(), visa("V1111111", last="2020-01-01")], TRAVEL
    )

    assert len(result.flags) == 1
    assert result.compared == 2


def test_two_visas_missing_the_travel_date_raise_two_flags():
    result = visa_validity_consistent(
        [visa("V1", last="2020-01-01"), visa("V2", first="2030-01-01")], TRAVEL
    )

    assert len(result.flags) == 2
    assert result.compared == 2


def test_a_passports_window_is_never_compared_by_this_rule():
    """16.6 is the visa's window against the travel date, and nothing else."""
    result = visa_validity_consistent([passport()], TRAVEL)

    assert result.compared == 0
    assert result.flags == ()


@pytest.mark.parametrize("role", ["id", "passport"])
def test_a_non_visa_is_never_a_window_finding(role):
    document = CaseDocument(
        role=role, document_number="X", valid_from=TRAVEL, valid_until=TRAVEL
    )

    result = visa_validity_consistent([document], TRAVEL)

    assert result.compared == 0


def test_a_window_running_backwards_covers_nothing_and_is_a_flag():
    """A visa contradicting itself is 16.5's sibling rule, not this one's."""
    result = visa_validity_consistent(
        [visa(first="2026-12-31", last="2026-01-01")], TRAVEL
    )

    assert len(result.flags) == 1


def test_the_flags_come_back_in_the_order_the_documents_were_given():
    "Two offending visas differ only in the window each one printed."
    case = [visa("V1", last="2020-01-01"), visa(), visa("V2", first="2030-01-01")]

    result = visa_validity_consistent(case, TRAVEL)

    assert [flag.expected for flag in result.flags] == [
        "2026-01-01/2020-01-01",
        "2030-01-01/2026-12-31",
    ]
    assert result.compared == 3


def test_the_answer_does_not_depend_on_whether_the_case_is_a_tuple():
    case = [visa()]

    assert visa_validity_consistent(case, TRAVEL) == visa_validity_consistent(
        tuple(case), TRAVEL
    )


def test_a_generator_is_measured_once_and_handed_on_whole():
    result = visa_validity_consistent(
        (document for document in [visa()]), TRAVEL
    )

    assert result.compared == 1


def test_a_passport_in_the_case_does_not_change_the_verdict():
    with_passport = visa_validity_consistent([passport(), visa()], TRAVEL)
    without = visa_validity_consistent([visa()], TRAVEL)

    assert with_passport == without


# --- the flag's own shape ----------------------------------------------------


def test_the_flag_reports_itself_under_the_crossdoc_tier():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].tier == "crossdoc"


def test_the_flag_carries_the_band_the_weightset_holds_it_under():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].weight_band == "review"


def test_the_band_on_the_flag_is_the_band_the_weightset_row_carries():
    """A band is read as a constant so it cannot drift from the row."""
    row = loader.load_weightset().flags[flag_ids.CROSSDOC_VALIDITY_WINDOW_MISMATCH]

    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].weight_band == row["band"]


def test_the_flag_names_the_window_the_finding_is_about():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].field == "validity_window"


def test_the_flag_points_at_nothing_on_any_one_document():
    """A window is about two pages, so neither frame locates it."""
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].region is None


def test_the_flag_carries_the_two_days_the_comparison_was_made_from():
    """A date is not identity data, so the halves are carried here."""
    result = visa_validity_consistent(
        [visa(first="2026-01-01", last="2026-06-14")], TRAVEL
    )
    flag = result.flags[0]

    assert flag.expected == "2026-01-01/2026-06-14"
    assert flag.found == "2026-06-15"


def test_the_days_on_the_flag_round_trip_back_to_the_days_compared():
    """``found`` and both ends of ``expected`` are ISO 8601 days, not prose."""
    result = visa_validity_consistent(
        [visa(first="2026-01-01", last="2026-06-14")], TRAVEL
    )
    flag = result.flags[0]

    assert datetime.date.fromisoformat(flag.found) == TRAVEL
    first, last = flag.expected.split("/")

    assert datetime.date.fromisoformat(first) == datetime.date(2026, 1, 1)
    assert datetime.date.fromisoformat(last) == datetime.date(2026, 6, 14)


def test_the_flag_reads_the_window_as_iso_days_and_nothing_else():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].expected.endswith("/2020-01-01")
    assert result.flags[0].found == "2026-06-15"


def test_the_flag_reports_itself_from_this_module():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.flags[0].source_module == "app.pipeline.crossdoc.validity"


def test_every_flag_is_an_evidence_flag():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert all(isinstance(flag, EvidenceFlag) for flag in result.flags)


def test_a_flag_carries_no_document_number_on_any_of_its_fields():
    """The one rule the whole project holds: a flag is never identity data."""
    result = visa_validity_consistent([visa(number="V9999999", last="2020-01-01")], TRAVEL)
    flag = result.flags[0]

    assert "V9999999" not in flag.label
    assert "V9999999" not in flag.reason
    assert "V9999999" not in flag.expected
    assert "V9999999" not in flag.found


def test_the_flag_carries_no_passport_reference_either():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)
    flag = result.flags[0]

    assert "AB1234567" not in flag.label
    assert "AB1234567" not in flag.reason


def test_the_message_names_the_rule_and_prints_neither_date():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)
    flag = result.flags[0]

    assert "2026-06-15" not in flag.label
    assert "2020-01-01" not in flag.label
    assert "window" in flag.reason


def test_the_windows_are_carried_as_a_count_and_not_as_a_list():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert result.compared == 1
    assert "V7654321" not in repr(result)


def test_a_consistency_record_cannot_be_edited_after_it_is_answered():
    answered = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    with pytest.raises(dataclasses.FrozenInstanceError):
        answered.status = CONSISTENT


def test_a_visas_window_cannot_be_edited_after_it_is_built():
    built = visa()

    with pytest.raises(dataclasses.FrozenInstanceError):
        built.valid_until = datetime.date(2030, 1, 1)


# --- refusals ---------------------------------------------------------------


@pytest.mark.parametrize("travel", [None, 42, "2026-06-15", ["2026-06-15"]])
def test_a_travel_date_that_is_not_a_date_is_refused(travel):
    with pytest.raises(MrzValueError):
        visa_validity_consistent([visa()], travel)


def test_a_refusal_names_the_type_it_was_given_and_not_the_value():
    with pytest.raises(MrzValueError) as caught:
        visa_validity_consistent([visa()], "2026-06-15")

    assert "str" in str(caught.value)


@pytest.mark.parametrize("not_a_date", [42, "2026-01-01", [2026, 1, 1], True])
def test_a_window_end_that_is_not_a_date_is_refused(not_a_date):
    with pytest.raises(MrzValueError):
        CaseDocument(role=VISA, document_number="V1", valid_from=not_a_date, valid_until=TRAVEL)

    with pytest.raises(MrzValueError):
        CaseDocument(role=VISA, document_number="V1", valid_from=TRAVEL, valid_until=not_a_date)


def test_a_window_with_only_one_end_is_refused():
    """Half a window is a caller mistake, not a document that printed half."""
    with pytest.raises(MrzValueError):
        CaseDocument(role=VISA, document_number="V1", valid_from=TRAVEL)

    with pytest.raises(MrzValueError):
        CaseDocument(role=VISA, document_number="V1", valid_until=TRAVEL)


def test_a_window_with_neither_end_is_accepted():
    built = CaseDocument(role=VISA, document_number="V1")

    assert built.valid_from is None
    assert built.valid_until is None


def test_a_refusal_on_the_window_names_the_end_it_was_holding():
    with pytest.raises(MrzValueError) as caught:
        CaseDocument(role=VISA, document_number="V1", valid_from="2026-01-01", valid_until=TRAVEL)

    assert "valid_from" in str(caught.value)


@pytest.mark.parametrize("case", [None, 42, {"visa": "V7654321"}])
def test_something_that_is_not_a_sequence_of_documents_is_refused(case):
    with pytest.raises(MrzValueError):
        visa_validity_consistent(case, TRAVEL)


def test_one_string_is_refused_as_a_case():
    with pytest.raises(MrzValueError):
        visa_validity_consistent("V7654321", TRAVEL)


@pytest.mark.parametrize("not_a_document", [None, 42, "visa", {"role": "visa"}])
def test_a_case_holding_something_that_is_not_a_document_is_refused(not_a_document):
    with pytest.raises(MrzValueError):
        visa_validity_consistent([visa(), not_a_document], TRAVEL)


def test_the_travel_date_is_refused_before_the_case_is_read():
    """A bad argument is named first, so a caller is told which of the two."""
    with pytest.raises(MrzValueError) as caught:
        visa_validity_consistent("V7654321", "2026-06-15")

    assert "travel date" in str(caught.value)


def test_a_refusal_is_a_value_error():
    assert issubclass(MrzValueError, ValueError)


def test_the_module_raises_only_the_tier0_error():
    assert validity_module.MrzValueError is MrzValueError


# --- the surface itself ------------------------------------------------------


def test_the_module_exports_exactly_its_own_names():
    assert validity_module.__all__ == ["visa_validity_consistent"]


def test_consistent_is_not_the_answer_for_a_case_that_compared_nothing():
    assert visa_validity_consistent([passport()], TRAVEL).status == NOT_CONFIGURED


def test_the_flag_count_and_the_status_are_the_same_fact_read_twice():
    result = visa_validity_consistent([visa(last="2020-01-01")], TRAVEL)

    assert bool(result.flags) == (result.status == INCONSISTENT)


def test_the_module_names_no_threshold_of_its_own():
    """The window is what the visa printed; no rule here widens or narrows it."""
    import inspect

    assert "tolerance" not in inspect.signature(visa_validity_consistent).parameters


def test_the_module_reads_no_clock_and_no_document_image():
    """The 3.12/3.13 rule: this module resolves no day and reads no frame."""
    import ast
    from pathlib import Path

    source = Path(validity_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in {"now", "today", "utcnow"}
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any("cv2" in (alias.name or "") or "numpy" in (alias.name or "") for alias in node.names)
        for node in ast.walk(tree)
    )


def test_the_travel_date_has_no_default():
    """A rule that defaulted its day would answer on the day it happened to run."""
    import inspect

    assert inspect.signature(visa_validity_consistent).parameters[
        "travel_date"
    ].default is inspect.Parameter.empty
