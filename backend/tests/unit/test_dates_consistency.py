"""5.7 -- the issue-after-expiry rule, the one date rule that reads no date.

The first three rules ask what one printed date means *to the reader on the
reference day*.  This one asks whether a document contradicts **itself**: a
window that opens after it closes is a finding with no reference day in it at
all.  So the rule is handed the two records the other two produced and
compares the days they carry, and its signature is the proof -- two records,
no ``text`` and no ``reference``, so there is nothing here to re-read and no
third reading to invent.

Two things the tests below hold down hard, because each is a way this rule
could quietly become a different rule:

* **It compares the two days and not the other two rules' verdicts.**  An
  expired document and a window that has not opened are both consistent when
  their own dates run the right way round, so the boundary is one ``>`` and
  nothing about the reference.
* **The gap is the gap and is never inherited from the half that could be
  read.**  "An issue date nobody could read" is a different sentence from "an
  issue date after the expiry", and this rule says the first, which is the
  same :data:`dates.UNDETERMINED` the other three answer.

Nothing here names a flag id, a band, a weight or a region.  6.3 turns the
record into a ``DATE_ISSUE_AFTER_EXPIRY`` flag, and the two dates it already
holds are the two halves that flag needs for ``expected`` and ``found``.
"""

import dataclasses
import datetime
import inspect

import pytest

from app.pipeline.tier0 import dates, mrz
from app.risk import flag_ids

#: The reference every table below is measured against, and the one the rest
#: of the suite uses: 3.13's sweep read the same day.
REFERENCE = datetime.date(2026, 9, 30)


def _issue(day, status=dates.ISSUED, reference=REFERENCE):
    """An :class:`IssueResult` for ``day``, read against ``reference``."""
    return dates.IssueResult(status, day, reference)


def _expiry(day, status=dates.VALID, reference=REFERENCE):
    """An :class:`ExpiryResult` for ``day``, read against ``reference``."""
    return dates.ExpiryResult(status, day, reference)


# --- the two verdicts, asked of a document's own two dates -----------------


def test_a_document_issued_after_it_expired_contradicts_itself():
    """Expired in January 2024 and issued in January 2025: no such window."""
    expiry = dates.expiry_result("240101", REFERENCE)
    issue = dates.issue_result("250101", REFERENCE)

    result = dates.consistency_result(issue, expiry)

    assert expiry.status == dates.EXPIRED
    assert expiry.expiry == datetime.date(2024, 1, 1)
    assert issue.status == dates.ISSUED
    assert issue.issue == datetime.date(2025, 1, 1)
    assert result.status == dates.ISSUE_AFTER_EXPIRY
    assert result.issue == datetime.date(2025, 1, 1)
    assert result.expiry == datetime.date(2024, 1, 1)


def test_a_document_issued_before_it_expires_is_consistent_with_itself():
    """The ordinary document, and the answer it earns by being ordinary."""
    issue = dates.issue_result("240101", REFERENCE)
    expiry = dates.expiry_result("300101", REFERENCE)

    result = dates.consistency_result(issue, expiry)

    assert result.status == dates.CONSISTENT
    assert result.issue == datetime.date(2024, 1, 1)
    assert result.expiry == datetime.date(2030, 1, 1)


@pytest.mark.parametrize(
    "issue_day, expiry_day, status",
    [
        pytest.param(
            datetime.date(2012, 4, 15),
            datetime.date(2026, 9, 30),
            dates.CONSISTENT,
            id="issued-fourteen-years-ago",
        ),
        pytest.param(
            datetime.date(2026, 9, 30),
            datetime.date(2026, 9, 30),
            dates.CONSISTENT,
            id="issued-and-expiring-today",
        ),
        pytest.param(
            datetime.date(2026, 9, 30),
            datetime.date(2026, 10, 1),
            dates.CONSISTENT,
            id="expiring-tomorrow",
        ),
        pytest.param(
            datetime.date(2026, 10, 1),
            datetime.date(2026, 9, 30),
            dates.ISSUE_AFTER_EXPIRY,
            id="issued-tomorrow",
        ),
        pytest.param(
            datetime.date(2026, 9, 30),
            datetime.date(2026, 9, 29),
            dates.ISSUE_AFTER_EXPIRY,
            id="issued-the-day-after-it-expired",
        ),
        pytest.param(
            datetime.date(2099, 12, 31),
            datetime.date(2126, 1, 2),
            dates.CONSISTENT,
            id="a-window-whose-both-ends-read-a-century-ahead",
        ),
    ],
)
def test_one_day_moves_the_verdict(issue_day, expiry_day, status):
    """The table is the boundary: only the day after the expiry is in doubt."""
    result = dates.consistency_result(_issue(issue_day), _expiry(expiry_day))

    assert result.status == status
    assert result.issue == issue_day
    assert result.expiry == expiry_day


def test_the_day_itself_is_not_the_finding():
    """A document valid through the day it expires is valid on that day here too.

    The same reasoning as :data:`dates.EXPIRING_TODAY`: the boundary belongs
    inside, so a one-day window is consistent rather than a finding, and the
    day after is the first that is not.
    """
    today = dates.issue_result("260930", REFERENCE)
    expiring = dates.expiry_result("260930", REFERENCE)

    assert dates.consistency_result(today, expiring).status == dates.CONSISTENT
    assert (
        dates.consistency_result(
            dates.issue_result("261001", REFERENCE), expiring
        ).status
        == dates.ISSUE_AFTER_EXPIRY
    )


# --- it reads two records, and no date of its own --------------------------


def test_the_rule_takes_two_records_and_no_date_of_its_own():
    """There is no `text` to read again and no `reference` to inject."""
    signature = inspect.signature(dates.consistency_result)

    assert list(signature.parameters) == ["issue", "expiry"]
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )


def test_the_two_parameters_name_the_two_record_types():
    """A caller that swapped them is told rather than compared with itself."""
    hints = {
        name: parameter.annotation
        for name, parameter in inspect.signature(dates.consistency_result)
        .parameters.items()
    }

    assert hints == {
        "issue": dates.IssueResult,
        "expiry": dates.ExpiryResult,
    }


def test_the_rule_compares_the_two_days_and_not_the_other_rules_verdicts():
    """A document is compared with itself, so expiry and validity are beside
    the point -- an expired window and a window that has not opened are both
    consistent when their own two dates run the right way round."""
    expired_and_in_order = dates.consistency_result(
        _issue(datetime.date(2010, 1, 1)),
        _expiry(datetime.date(2012, 4, 15), status=dates.EXPIRED),
    )
    not_open_yet = dates.consistency_result(
        _issue(datetime.date(2099, 12, 31), status=dates.NOT_YET_VALID),
        _expiry(datetime.date(2126, 1, 2)),
    )

    assert expired_and_in_order.status == dates.CONSISTENT
    assert not_open_yet.status == dates.CONSISTENT


def test_the_readings_it_is_given_are_the_ones_the_two_other_rules_made():
    """The two known horizon gaps compose, and the composition is asserted.

    `991231` read in 2026 is a date of issue of 2099 (`D9`) and `120415` is an
    expiry that expired in 2012 (`D8`), so the two records the caller holds
    already contradict each other.  A rule that re-read the six characters
    would have to invent a third reading to reach the same answer, and the
    answer it reaches here is the one a caller can act on.
    """
    issue = dates.issue_result("991231", REFERENCE)
    expiry = dates.expiry_result("120415", REFERENCE)

    result = dates.consistency_result(issue, expiry)

    assert (issue.issue, expiry.expiry) == (
        datetime.date(2099, 12, 31),
        datetime.date(2012, 4, 15),
    )
    assert result.status == dates.ISSUE_AFTER_EXPIRY


# --- the gap is the gap ----------------------------------------------------


@pytest.mark.parametrize(
    "issue, expiry",
    [
        pytest.param(
            dates.issue_result("AAAAAA", REFERENCE),
            dates.expiry_result("300101", REFERENCE),
            id="an-issue-date-nobody-could-read",
        ),
        pytest.param(
            dates.issue_result("240101", REFERENCE),
            dates.expiry_result("AAAAAA", REFERENCE),
            id="an-expiry-nobody-could-read",
        ),
        pytest.param(
            dates.issue_result("993199", REFERENCE),
            dates.expiry_result("013200", REFERENCE),
            id="two-impossible-dates",
        ),
        pytest.param(
            dates.issue_result("AAAAAA", REFERENCE),
            dates.expiry_result("<<<<<<", REFERENCE),
            id="two-unreadable-dates",
        ),
    ],
)
def test_a_pair_with_a_gap_in_it_is_undetermined(issue, expiry):
    """One answer for unreadable, impossible and unplaceable alike."""
    result = dates.consistency_result(issue, expiry)

    assert result.status == dates.UNDETERMINED


def test_a_gap_carries_neither_day_rather_than_the_half_that_was_read():
    """A date nobody could read on one side is not half a comparison."""
    result = dates.consistency_result(
        dates.issue_result("AAAAAA", REFERENCE),
        dates.expiry_result("120415", REFERENCE),
    )

    assert result.issue is None
    assert result.expiry is None


def test_a_readable_half_does_not_lend_its_verdict_to_the_gap():
    """The other half here expired in 2012, so *every* issue date is after it.

    An answer of :data:`dates.CONSISTENT` would be a comparison this rule
    never made, and it would be true or false depending on a date nobody
    could read -- which is the difference between a finding and a gap.
    """
    result = dates.consistency_result(
        dates.issue_result("AAAAAA", REFERENCE),
        dates.expiry_result("120415", REFERENCE),
    )

    assert result.status != dates.CONSISTENT
    assert result.status == dates.UNDETERMINED


def test_the_gap_is_the_same_one_the_other_three_rules_answer():
    """A verdict belongs to the rule that judged it; the gap is the document's."""
    assert dates.CONSISTENCY_STATUSES & dates.EXPIRY_STATUSES == frozenset(
        {dates.UNDETERMINED}
    )
    assert dates.CONSISTENCY_STATUSES & dates.ISSUE_STATUSES == frozenset(
        {dates.UNDETERMINED}
    )
    assert dates.CONSISTENCY_STATUSES & dates.BIRTH_STATUSES == frozenset(
        {dates.UNDETERMINED}
    )


# --- the reference belongs to the two records ------------------------------


def test_the_reference_on_the_record_is_the_day_both_records_were_read_against():
    """It is carried, not asked for: this rule adds no third date."""
    result = dates.consistency_result(
        dates.issue_result("240101", REFERENCE),
        dates.expiry_result("300101", REFERENCE),
    )

    assert result.reference == REFERENCE


def test_two_results_read_on_different_days_are_refused():
    """Two days are two screenings rather than one document."""
    the_next_day = datetime.date(2026, 10, 1)

    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.consistency_result(
            dates.issue_result("240101", REFERENCE),
            dates.expiry_result("300101", the_next_day),
        )

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_timestamp_reference_is_a_legal_reference_on_either_record():
    """`datetime.datetime` is a `datetime.date`, so this is not that mistake."""
    stamp = datetime.datetime(2026, 9, 30, 23, 59, 59)
    result = dates.consistency_result(
        _issue(datetime.date(2024, 1, 1), reference=stamp),
        _expiry(datetime.date(2030, 1, 1), reference=stamp),
    )

    assert result.status == dates.CONSISTENT
    assert result.reference == REFERENCE
    assert type(result.reference) is datetime.date


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("2026-09-30", id="a-string"),
        pytest.param(None, id="none"),
        pytest.param(20260930, id="an-int"),
        pytest.param((2026, 9, 30), id="a-tuple"),
    ],
)
def test_a_reference_on_a_record_that_is_not_a_date_is_refused(reference):
    """A screening that went wrong must not read as a document nobody could read."""
    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.consistency_result(_issue(REFERENCE, reference=reference), _expiry(REFERENCE))

    assert type(excinfo.value) is mrz.MrzValueError


# --- the two arguments are two records --------------------------------------


@pytest.mark.parametrize(
    "issue, expiry",
    [
        pytest.param(
            dates.expiry_result("300101", REFERENCE),
            dates.expiry_result("300101", REFERENCE),
            id="the-expiry-result-handed-over-twice",
        ),
        pytest.param(
            dates.issue_result("240101", REFERENCE),
            dates.issue_result("240101", REFERENCE),
            id="the-issue-result-handed-over-twice",
        ),
        pytest.param(
            "240101", dates.expiry_result("300101", REFERENCE), id="a-string"
        ),
        pytest.param(None, dates.expiry_result("300101", REFERENCE), id="none"),
        pytest.param(
            dates.issue_result("240101", REFERENCE), "300101", id="a-string-expiry"
        ),
        pytest.param(
            dates.issue_result("240101", REFERENCE), None, id="no-expiry"
        ),
    ],
)
def test_an_argument_that_is_not_the_record_it_names_is_refused(issue, expiry):
    """A wrong order or a wrong type is a caller mistake, not a comparison."""
    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.consistency_result(issue, expiry)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the record -------------------------------------------------------------


def test_the_result_carries_the_two_days_and_the_reference_and_nothing_else():
    assert [f.name for f in dataclasses.fields(dates.ConsistencyResult)] == [
        "status",
        "issue",
        "expiry",
        "reference",
    ]


def test_a_result_cannot_be_edited():
    result = dates.consistency_result(
        dates.issue_result("250101", REFERENCE),
        dates.expiry_result("240101", REFERENCE),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = dates.CONSISTENT


def test_a_result_carries_no_public_method():
    """A second answer about the document would be a rule that agrees with itself."""
    public = [
        name
        for name in dir(dates.ConsistencyResult)
        if not name.startswith("_") and callable(getattr(dates.ConsistencyResult, name))
    ]

    assert public == []


def test_the_same_question_asked_twice_is_the_same_record():
    """Equal and hashable, so a re-run of the same screening compares cleanly."""
    first = dates.consistency_result(
        dates.issue_result("250101", REFERENCE),
        dates.expiry_result("240101", REFERENCE),
    )
    second = dates.consistency_result(
        dates.issue_result("250101", REFERENCE),
        dates.expiry_result("240101", REFERENCE),
    )

    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"status": "CONSISTENT"}, id="a-status-nobody-declared"),
        pytest.param({"status": 0}, id="a-status-that-is-not-a-string"),
        pytest.param({"status": None}, id="no-status"),
        pytest.param({"status": dates.ISSUED}, id="another_rule_s_own-status"),
        pytest.param({"status": dates.CONSISTENT, "issue": None}, id="consistent-with-no-issue"),
        pytest.param(
            {"status": dates.CONSISTENT, "expiry": None}, id="consistent-with-no-expiry"
        ),
        pytest.param(
            {"status": dates.ISSUE_AFTER_EXPIRY, "expiry": None},
            id="issue-after-expiry-with-no-expiry",
        ),
        pytest.param(
            {"status": dates.UNDETERMINED, "issue": REFERENCE},
            id="undetermined-with-an-issue-date",
        ),
        pytest.param(
            {"status": dates.UNDETERMINED, "expiry": REFERENCE},
            id="undetermined-with-an-expiry-date",
        ),
        pytest.param(
            {"status": dates.CONSISTENT, "issue": "2026-09-30"},
            id="an-issue-date-as-a-string",
        ),
        pytest.param(
            {"status": dates.CONSISTENT, "expiry": "2026-09-30"},
            id="an-expiry-date-as-a-string",
        ),
        pytest.param(
            {"status": dates.CONSISTENT, "reference": "2026-09-30"},
            id="a-reference-as-a-string",
        ),
        pytest.param({"status": dates.CONSISTENT, "reference": None}, id="no-reference"),
    ],
)
def test_a_malformed_result_is_refused_and_never_coerced(overrides):
    values = {
        "status": dates.CONSISTENT,
        "issue": REFERENCE,
        "expiry": REFERENCE,
        "reference": REFERENCE,
    }
    values.update(overrides)

    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.ConsistencyResult(**values)

    assert type(excinfo.value) is mrz.MrzValueError


# --- a rule decides nothing ------------------------------------------------


def test_the_result_names_no_flag_id_and_carries_no_weight_or_region():
    """`DATE_ISSUE_AFTER_EXPIRY` and a band are 6.3's to attach, not this rule's."""
    names = {field.name for field in dataclasses.fields(dates.ConsistencyResult)}

    assert names == {"status", "issue", "expiry", "reference"}
    assert (
        names
        & {
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
        }
        == set()
    )


def test_the_finding_carries_the_one_id_the_id_list_names_for_this_rule():
    """`flag_ids.py` says the rule is `DATE_ISSUE_AFTER_EXPIRY`, and no other."""
    assert flag_ids.DATE_ISSUE_AFTER_EXPIRY in flag_ids.FLAG_IDS
    assert dates.ISSUE_AFTER_EXPIRY == "issue_after_expiry"


def test_the_three_statuses_are_the_module_s_own_and_are_exported():
    assert dates.CONSISTENCY_STATUSES == frozenset(
        {dates.CONSISTENT, dates.ISSUE_AFTER_EXPIRY, dates.UNDETERMINED}
    )
    assert len(dates.CONSISTENCY_STATUSES) == 3
    assert {
        "CONSISTENCY_STATUSES",
        "CONSISTENT",
        "ISSUE_AFTER_EXPIRY",
        "ConsistencyResult",
        "consistency_result",
    } <= set(dates.__all__)


def test_this_rule_does_not_change_the_other_three_rules_answers():
    """Four rules beside each other in one module, and none rewrites another."""
    assert dates.expiry_result("260930", REFERENCE).status == dates.EXPIRING_TODAY
    assert dates.expiry_result("120415", REFERENCE).status == dates.EXPIRED
    assert dates.issue_result("261001", REFERENCE).status == dates.NOT_YET_VALID
    assert dates.issue_result("250101", REFERENCE).status == dates.ISSUED
    assert dates.dob_result("070930", REFERENCE).status == dates.PLAUSIBLE
    assert (
        dates.dob_result("261001", REFERENCE, 18).status == dates.IMPLAUSIBLE
    )
