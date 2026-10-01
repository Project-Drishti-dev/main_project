"""5.4 -- the expiry rule, judged against an injected reference date.

The three cases the task names are here and in the table beside them: a
document that expired yesterday, one that expires today, and one with time
left on it.  **Today belongs to the document rather than to the officer** --
`infer_expiry_year` admits the day itself for exactly that reason, so
`EXPIRING_TODAY` is a distinct answer from `VALID` and not the same answer
twice.

What the rule does *not* do is settled by the tests at the bottom rather than
by the docstrings: it names no flag id, carries no weight and no region, and
imports nothing from `app.risk`.  A rule produces a result and 6.3 turns a
result into a flag, so a `DATE_EXPIRED` here would be the second opinion
about a finding that `EvidenceFlag` exists to hold once.

The reference date is every test's own argument.  Nothing below reads the
clock, and the signature pin holds that: a `date.today()` default would pass
every behavioural test in this file and still make a screening's answer
depend on when it ran.
"""

import ast
import dataclasses
import datetime
import inspect
import pathlib

import pytest

from app.pipeline.tier0 import dates, mrz

#: The reference every table below is measured against, and the one the rest
#: of the suite uses: 3.13's sweep read the same day.
REFERENCE = datetime.date(2026, 9, 30)

#: The specimen's own date of expiry, thirteen and a half years past on this
#: reference.  It is the expired case every other test here is a neighbour of.
SPECIMEN_EXPIRY = "120415"


# --- the three cases the task names ----------------------------------------


def test_a_document_that_expired_yesterday_is_expired():
    result = dates.expiry_result("260929", REFERENCE)

    assert result.status == dates.EXPIRED
    assert result.expiry == datetime.date(2026, 9, 29)
    assert result.reference == REFERENCE


def test_a_document_that_expires_today_is_still_valid_today():
    """The boundary is inclusive, so this is its own answer and not `EXPIRED`."""
    result = dates.expiry_result("260930", REFERENCE)

    assert result.status == dates.EXPIRING_TODAY
    assert result.expiry == REFERENCE


def test_a_document_that_expires_tomorrow_is_valid():
    result = dates.expiry_result("261001", REFERENCE)

    assert result.status == dates.VALID
    assert result.expiry == datetime.date(2026, 10, 1)


@pytest.mark.parametrize(
    "text, reference, status",
    [
        pytest.param("260929", REFERENCE, dates.EXPIRED, id="expired-yesterday"),
        pytest.param("260930", REFERENCE, dates.EXPIRING_TODAY, id="today"),
        pytest.param("261001", REFERENCE, dates.VALID, id="tomorrow"),
        pytest.param(
            "260930",
            datetime.date(2026, 10, 1),
            dates.EXPIRED,
            id="yesterday-was-the-day-it-expired",
        ),
        pytest.param(
            "261001",
            datetime.date(2026, 9, 29),
            dates.VALID,
            id="the-day-before-it-expires",
        ),
        pytest.param("250930", REFERENCE, dates.EXPIRED, id="expired-a-year-ago"),
        pytest.param("270930", REFERENCE, dates.VALID, id="valid-for-a-year-more"),
        pytest.param(
            "260101", REFERENCE, dates.EXPIRED, id="expired-earlier-this-year"
        ),
    ],
)
def test_one_day_moves_the_verdict(text, reference, status):
    """The table is the boundary: only the day the expiry falls on is in doubt."""
    assert dates.expiry_result(text, reference).status == status


@pytest.mark.parametrize(
    "text, status, expiry",
    [
        pytest.param(
            SPECIMEN_EXPIRY,
            dates.EXPIRED,
            datetime.date(2012, 4, 15),
            id="the-specimen-expired-in-2012",
        ),
        pytest.param(
            "260929",
            dates.EXPIRED,
            datetime.date(2026, 9, 29),
            id="this-century-yesterday",
        ),
        pytest.param(
            "260930",
            dates.EXPIRING_TODAY,
            datetime.date(2026, 9, 30),
            id="this-century-today",
        ),
        pytest.param(
            "261001",
            dates.VALID,
            datetime.date(2026, 10, 1),
            id="this-century-tomorrow",
        ),
        pytest.param(
            "270930", dates.VALID, datetime.date(2027, 9, 30), id="next-year"
        ),
        pytest.param(
            "740930",
            dates.VALID,
            datetime.date(2074, 9, 30),
            id="forty-eight-years-left",
        ),
        # The forward reading is `infer_expiry_year`'s and it has no band: two
        # digits repeat every century, so "991231" read in 2026 is 2099 and is
        # valid.  Asserted because it is a consequence an officer should read
        # rather than discover, not because it is welcome.
        pytest.param(
            "991231",
            dates.VALID,
            datetime.date(2099, 12, 31),
            id="a-century-off-is-still-valid",
        ),
    ],
)
def test_the_date_reported_is_the_day_the_verdict_is_about(text, status, expiry):
    """An expired document reports the day it expired on, not the century it was given."""
    result = dates.expiry_result(text, REFERENCE)

    assert result.status == status
    assert result.expiry == expiry


def test_the_specimen_reads_backwards_to_the_year_it_actually_expired():
    """`infer_expiry_year` answers 2112 for these six characters, and so must the rule."""
    assert mrz.infer_expiry_year(SPECIMEN_EXPIRY, REFERENCE) == 2112
    result = dates.expiry_result(SPECIMEN_EXPIRY, REFERENCE)

    assert result.status == dates.EXPIRED
    assert result.expiry == datetime.date(2012, 4, 15)


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
        pytest.param("000229", id="a-29th-of-february-no-century-had"),
    ],
)
def test_a_document_that_does_not_tell_us_is_undetermined(text):
    """One answer for unreadable, impossible and unplaceable alike."""
    result = dates.expiry_result(text, REFERENCE)

    assert result.status == dates.UNDETERMINED
    assert result.expiry is None


def test_an_undetermined_result_still_carries_the_reference_it_was_asked_against():
    """A gap is a fact about the document, not about the day it was read."""
    result = dates.expiry_result("993199", REFERENCE)

    assert result.reference == REFERENCE


def test_a_second_of_february_that_never_was_is_undetermined_rather_than_expired():
    """The one corner where the answer arrives a century on for another reason.

    1900 is not a leap century, so `000229` read in January 1900 skips
    1900-02-29 for the calendar rather than for the reference and lands on
    2000-02-29.  Un-rolling that gives a day that never was, and this answers
    "we cannot tell" rather than inventing one.
    """
    result = dates.expiry_result("000229", datetime.date(1900, 1, 15))

    assert result.status == dates.UNDETERMINED
    assert result.expiry is None


# --- the reference date is the caller's ------------------------------------


def test_the_reference_date_is_a_parameter_and_never_a_default():
    signature = inspect.signature(dates.expiry_result)

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
        dates.expiry_result("260930", reference)

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_timestamp_is_a_legal_reference_and_the_day_is_what_is_compared():
    """`datetime.datetime` is a `datetime.date`, so this is not that mistake."""
    stamp = datetime.datetime(2026, 9, 30, 23, 59, 59)
    result = dates.expiry_result("260930", stamp)

    assert result.status == dates.EXPIRING_TODAY
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
        dates.expiry_result(text, REFERENCE)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the record ------------------------------------------------------------


def test_the_result_carries_three_fields_and_nothing_else():
    assert [f.name for f in dataclasses.fields(dates.ExpiryResult)] == [
        "status",
        "expiry",
        "reference",
    ]


def test_a_result_cannot_be_edited():
    with pytest.raises(dataclasses.FrozenInstanceError):
        dates.expiry_result("260930", REFERENCE).status = dates.EXPIRED


def test_a_result_carries_no_public_method():
    """A second answer about the document would be a rule that agrees with itself."""
    public = [
        name
        for name in dir(dates.ExpiryResult)
        if not name.startswith("_") and callable(getattr(dates.ExpiryResult, name))
    ]

    assert public == []


def test_the_same_question_asked_twice_is_the_same_record():
    """Equal and hashable, so a re-run of the same screening compares cleanly."""
    first = dates.expiry_result(SPECIMEN_EXPIRY, REFERENCE)
    second = dates.expiry_result(SPECIMEN_EXPIRY, REFERENCE)

    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"status": "EXPIRED"}, id="a-status-nobody-declared"),
        pytest.param({"status": 0}, id="a-status-that-is-not-a-string"),
        pytest.param({"status": None}, id="no-status"),
        pytest.param({"status": dates.VALID, "expiry": None}, id="valid-with-no-date"),
        pytest.param(
            {"status": dates.EXPIRED, "expiry": None}, id="expired-with-no-date"
        ),
        pytest.param(
            {"status": dates.UNDETERMINED, "expiry": REFERENCE},
            id="undetermined-with-a-date",
        ),
        pytest.param(
            {"status": dates.VALID, "expiry": "2026-10-01"}, id="a-date-as-a-string"
        ),
        pytest.param(
            {"status": dates.VALID, "reference": "2026-09-30"},
            id="a-reference-as-a-string",
        ),
        pytest.param({"status": dates.VALID, "reference": None}, id="no-reference"),
    ],
)
def test_a_malformed_result_is_refused_and_never_coerced(overrides):
    values = {
        "status": dates.VALID,
        "expiry": REFERENCE,
        "reference": REFERENCE,
    }
    values.update(overrides)

    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.ExpiryResult(**values)

    assert type(excinfo.value) is mrz.MrzValueError


# --- a rule decides nothing ------------------------------------------------


def test_the_result_names_no_flag_id_and_carries_no_weight_or_region():
    """`DATE_EXPIRED` and a band are 6.3's to attach, not this rule's to choose."""
    names = {field.name for field in dataclasses.fields(dates.ExpiryResult)}

    assert names == {"status", "expiry", "reference"}
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


def test_the_module_imports_nothing_from_the_risk_package():
    """The dependency runs one way: a rule answers, and the risk package wraps it."""
    tree = ast.parse(pathlib.Path(dates.__file__).read_text(encoding="utf-8"))
    imported = [
        node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert [name for name in imported if "risk" in str(name)] == []


def test_the_module_defines_no_error_type_of_its_own():
    """1.9's single error type is the package's, and this module reuses it."""
    defined = {
        name
        for name, obj in vars(dates).items()
        if isinstance(obj, type) and issubclass(obj, BaseException)
    }

    assert defined == {"MrzValueError"}
    assert dates.MrzValueError is mrz.MrzValueError


def test_the_four_statuses_are_the_module_s_own_and_are_exported():
    assert dates.EXPIRY_STATUSES == frozenset(
        {dates.EXPIRED, dates.VALID, dates.EXPIRING_TODAY, dates.UNDETERMINED}
    )
    assert len(dates.EXPIRY_STATUSES) == 4
    assert set(dates.__all__) == {
        "BIRTH_STATUSES",
        "CONSISTENCY_STATUSES",
        "CONSISTENT",
        "EXPIRED",
        "EXPIRING_TODAY",
        "EXPIRY_STATUSES",
        "IMPLAUSIBLE",
        "ISSUE_AFTER_EXPIRY",
        "ISSUE_STATUSES",
        "ISSUED",
        "NOT_YET_VALID",
        "PLAUSIBLE",
        "ReferenceDate",
        "UNDETERMINED",
        "VALID",
        "BirthResult",
        "ConsistencyResult",
        "ExpiryResult",
        "IssueResult",
        "consistency_result",
        "dob_result",
        "expiry_result",
        "issue_result",
    }
