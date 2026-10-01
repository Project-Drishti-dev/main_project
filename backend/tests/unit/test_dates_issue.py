"""5.5 -- the not-yet-valid rule, judged against an injected reference date.

The rule asks whether a document's validity window has opened: the date of
issue is the near end of the window and :data:`dates.NOT_YET_VALID` is the
answer when it is still in the future.  **Today belongs to the document**
here as it did on the expiry side -- a document is valid from the day it is
issued, so the day of issue itself is :data:`dates.ISSUED` and not a fourth
answer.

The direction of the reading is the whole of the rule, and it is the opposite
of `infer_expiry_year`'s: the date of issue is resolved in the reference's own
century and no other, because a reading taken a century back could never place
a document in the future and the rule could then never fire.  The two tests
named for that hold it, including the consequence it costs, which is asserted
rather than hoped for the same way `991231` is in `test_dates.py`.

The reference date is every test's own argument, and the module carries no
flag id, weight, region or confidence -- 6.3 turns a result into a
`DATE_NOT_YET_VALID` flag, so an id here would be the second opinion about a
finding that `EvidenceFlag` exists to hold once.
"""

import dataclasses
import datetime
import inspect

import pytest

from app.pipeline.tier0 import dates, mrz

#: The reference every table below is measured against, and the one the rest of
#: the suite uses: 3.13's sweep read the same day.
REFERENCE = datetime.date(2026, 9, 30)


# --- the three cases the rule names ----------------------------------------


def test_a_document_issued_tomorrow_is_not_yet_valid():
    result = dates.issue_result("261001", REFERENCE)

    assert result.status == dates.NOT_YET_VALID
    assert result.issue == datetime.date(2026, 10, 1)
    assert result.reference == REFERENCE


def test_a_document_issued_today_is_valid_from_today():
    """The window opens on the day of issue, so this is not "not yet valid"."""
    result = dates.issue_result("260930", REFERENCE)

    assert result.status == dates.ISSUED
    assert result.issue == REFERENCE


def test_a_document_issued_yesterday_is_issued():
    result = dates.issue_result("260929", REFERENCE)

    assert result.status == dates.ISSUED
    assert result.issue == datetime.date(2026, 9, 29)


@pytest.mark.parametrize(
    "text, reference, status, issue",
    [
        pytest.param(
            "260929",
            REFERENCE,
            dates.ISSUED,
            datetime.date(2026, 9, 29),
            id="yesterday",
        ),
        pytest.param(
            "260930", REFERENCE, dates.ISSUED, datetime.date(2026, 9, 30), id="today"
        ),
        pytest.param(
            "261001",
            REFERENCE,
            dates.NOT_YET_VALID,
            datetime.date(2026, 10, 1),
            id="tomorrow",
        ),
        pytest.param(
            "261001",
            datetime.date(2026, 10, 1),
            dates.ISSUED,
            datetime.date(2026, 10, 1),
            id="today-is-the-day-the-window-opened",
        ),
        pytest.param(
            "260930",
            datetime.date(2026, 10, 1),
            dates.ISSUED,
            datetime.date(2026, 9, 30),
            id="the-day-after-a-window-opened",
        ),
        pytest.param(
            "250930",
            REFERENCE,
            dates.ISSUED,
            datetime.date(2025, 9, 30),
            id="a-year-ago",
        ),
        pytest.param(
            "260101",
            REFERENCE,
            dates.ISSUED,
            datetime.date(2026, 1, 1),
            id="earlier-this-year",
        ),
        pytest.param(
            "261231",
            REFERENCE,
            dates.NOT_YET_VALID,
            datetime.date(2026, 12, 31),
            id="later-this-year",
        ),
        pytest.param(
            "300101",
            REFERENCE,
            dates.NOT_YET_VALID,
            datetime.date(2030, 1, 1),
            id="four-years-ahead",
        ),
    ],
)
def test_one_day_moves_the_verdict(text, reference, status, issue):
    """The table is the boundary: only the day after the issue date is in doubt."""
    result = dates.issue_result(text, reference)

    assert result.status == status
    assert result.issue == issue


def test_the_date_reported_is_the_day_the_window_opens_on():
    """A finding needs the day, and it is the one the verdict was made from."""
    result = dates.issue_result("261001", REFERENCE)

    assert result.issue == datetime.date(2026, 10, 1)


# --- the direction of the reading ------------------------------------------


def test_the_reading_is_the_reference_s_own_century_and_never_one_behind_it():
    """A century back is a reading no document could carry, and it cannot fire."""
    result = dates.issue_result("250101", REFERENCE)

    assert result.issue == datetime.date(2025, 1, 1)
    assert result.status == dates.ISSUED


def test_an_issue_date_does_not_reuse_the_forward_reading_an_expiry_takes():
    """`infer_expiry_year` answers 2125 here; this rule answers 2025, and must."""
    assert mrz.infer_expiry_year("250101", REFERENCE) == 2125

    result = dates.issue_result("250101", REFERENCE)

    assert result.issue == datetime.date(2025, 1, 1)
    assert result.status == dates.ISSUED


def test_two_printed_digits_a_century_ahead_are_read_a_century_ahead():
    """The mirror of the expiry rule's `991231`, asserted so it is read.

    Two digits repeat every century and this reading has no band to bound it,
    so a document issued in a year whose two digits sit ahead of the
    reference's own reads a century on.  That is the cost of the only reading
    under which the rule can fire, and it is recorded rather than wished away.
    """
    result = dates.issue_result("991231", REFERENCE)

    assert result.status == dates.NOT_YET_VALID
    assert result.issue == datetime.date(2099, 12, 31)


# --- the answers that are not a verdict ------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("<<<<<<", id="filler"),
        pytest.param("AAAAAA", id="letters"),
        pytest.param("74o812", id="a-letter-inside"),
        pytest.param("99 199", id="a-space-inside"),
        pytest.param("993199", id="a-month-of-99"),
        pytest.param("013200", id="a-day-of-32"),
    ],
)
def test_a_document_that_does_not_tell_us_is_undetermined(text):
    """One answer for unreadable, impossible and unplaceable alike."""
    result = dates.issue_result(text, REFERENCE)

    assert result.status == dates.UNDETERMINED
    assert result.issue is None


def test_an_undetermined_result_still_carries_the_reference_it_was_asked_against():
    """A gap is a fact about the document, not about the day it was read."""
    result = dates.issue_result("993199", REFERENCE)

    assert result.reference == REFERENCE


def test_a_29th_of_february_in_a_century_that_had_none_is_undetermined():
    """The gap is the century, not the six characters.

    2100 is not a leap century, so the nearest reading of `000229` names a day
    that never was and there is no other century this rule tries.
    """
    result = dates.issue_result("000229", datetime.date(2100, 6, 1))

    assert result.status == dates.UNDETERMINED
    assert result.issue is None


def test_the_same_29th_of_february_read_in_a_leap_century_is_a_real_day():
    """The same six characters are placed as soon as the century has the day."""
    result = dates.issue_result("000229", REFERENCE)

    assert result.issue == datetime.date(2000, 2, 29)
    assert result.status == dates.ISSUED


# --- the reference date is the caller's ------------------------------------


def test_the_reference_date_is_a_parameter_and_never_a_default():
    signature = inspect.signature(dates.issue_result)

    assert list(signature.parameters) == ["text", "reference"]
    assert signature.parameters["reference"].default is inspect.Parameter.empty


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("2026-09-30", id="a-string"),
        pytest.param(None, id="none"),
        pytest.param(20260930, id="an-int"),
        pytest.param((2026, 9, 30), id="a-tuple"),
    ],
)
def test_a_reference_that_is_not_a_date_is_refused(reference):
    """A screening that went wrong must not read as a document nobody could read."""
    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.issue_result("260930", reference)

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_timestamp_is_a_legal_reference_and_the_day_is_what_is_compared():
    """`datetime.datetime` is a `datetime.date`, so this is not that mistake."""
    stamp = datetime.datetime(2026, 9, 30, 23, 59, 59)
    result = dates.issue_result("260930", stamp)

    assert result.status == dates.ISSUED
    assert result.reference == REFERENCE
    assert type(result.reference) is datetime.date


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("26093", id="five-characters"),
        pytest.param("2609300", id="seven-characters"),
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
        pytest.param(260930, id="an-int"),
    ],
)
def test_a_field_that_is_not_a_date_field_is_a_caller_mistake_and_raises(text):
    """A wrong width is never a fact about a document, so it is not undetermined."""
    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.issue_result(text, REFERENCE)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the record -------------------------------------------------------------


def test_the_result_carries_three_fields_and_nothing_else():
    assert [f.name for f in dataclasses.fields(dates.IssueResult)] == [
        "status",
        "issue",
        "reference",
    ]


def test_a_result_cannot_be_edited():
    with pytest.raises(dataclasses.FrozenInstanceError):
        dates.issue_result("260930", REFERENCE).status = dates.NOT_YET_VALID


def test_a_result_carries_no_public_method():
    """A second answer about the document would be a rule that agrees with itself."""
    public = [
        name
        for name in dir(dates.IssueResult)
        if not name.startswith("_") and callable(getattr(dates.IssueResult, name))
    ]

    assert public == []


def test_the_same_question_asked_twice_is_the_same_record():
    """Equal and hashable, so a re-run of the same screening compares cleanly."""
    first = dates.issue_result("261001", REFERENCE)
    second = dates.issue_result("261001", REFERENCE)

    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"status": "ISSUED"}, id="a-status-nobody-declared"),
        pytest.param({"status": 0}, id="a-status-that-is-not-a-string"),
        pytest.param({"status": None}, id="no-status"),
        pytest.param({"status": dates.ISSUED, "issue": None}, id="issued-with-no-date"),
        pytest.param(
            {"status": dates.NOT_YET_VALID, "issue": None},
            id="not-yet-valid-with-no-date",
        ),
        pytest.param(
            {"status": dates.UNDETERMINED, "issue": REFERENCE},
            id="undetermined-with-a-date",
        ),
        pytest.param(
            {"status": dates.ISSUED, "issue": "2026-09-30"}, id="a-date-as-a-string"
        ),
        pytest.param(
            {"status": dates.ISSUED, "reference": "2026-09-30"},
            id="a-reference-as-a-string",
        ),
        pytest.param({"status": dates.ISSUED, "reference": None}, id="no-reference"),
    ],
)
def test_a_malformed_result_is_refused_and_never_coerced(overrides):
    values = {
        "status": dates.ISSUED,
        "issue": REFERENCE,
        "reference": REFERENCE,
    }
    values.update(overrides)

    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.IssueResult(**values)

    assert type(excinfo.value) is mrz.MrzValueError


# --- a rule decides nothing ------------------------------------------------


def test_the_result_names_no_flag_id_and_carries_no_weight_or_region():
    """`DATE_NOT_YET_VALID` and a band are 6.3's to attach, not this rule's."""
    names = {field.name for field in dataclasses.fields(dates.IssueResult)}

    assert names == {"status", "issue", "reference"}
    assert names & {
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
    } == set()


def test_the_two_rules_share_one_answer_and_it_is_the_gap():
    """A verdict belongs to the rule that judged it; "does not tell us" is the
    document's own answer, and both rules give it."""
    assert dates.ISSUE_STATUSES & dates.EXPIRY_STATUSES == frozenset(
        {dates.UNDETERMINED}
    )


def test_the_three_statuses_are_the_module_s_own_and_are_exported():
    assert dates.ISSUE_STATUSES == frozenset(
        {dates.ISSUED, dates.NOT_YET_VALID, dates.UNDETERMINED}
    )
    assert len(dates.ISSUE_STATUSES) == 3
    assert {
        "ISSUE_STATUSES",
        "ISSUED",
        "NOT_YET_VALID",
        "IssueResult",
        "issue_result",
    } <= set(dates.__all__)


def test_this_rule_does_not_change_the_expiry_rule_s_answers():
    """Two rules beside each other in one module, and neither reads the other."""
    assert dates.expiry_result("260930", REFERENCE).status == dates.EXPIRING_TODAY
    assert dates.expiry_result("120415", REFERENCE).status == dates.EXPIRED
    assert dates.expiry_result("261001", REFERENCE).status == dates.VALID
