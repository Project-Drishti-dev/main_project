"""5.6 -- the implausible-date-of-birth rule, and the two boundaries it turns on.

The task states the rule in one sentence with two halves -- a date of birth in
the future, or one implying an age over a *configurable* maximum -- and the
second word is the whole of the design.  **A date of birth is read backwards**,
the way :func:`~app.pipeline.tier0.mrz.infer_birth_year` reads it, because two
printed digits repeat every hundred years: read in the reference's own century,
the birth of anybody alive in 2026 comes out as a date in the future.  The
tests below hold that reading down hard, and the second half of the rule only
becomes observable because the band the caller configures is what decides how
far back a reading may reach.

The default is :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE`, and **at that
default neither half can fire**: a two-century reading implies an age of at
most 99, and a finding that can never be made is asserted rather than left as
an intention.  That is why ``TIGHT`` below exists -- it is a maximum
configured low enough for both halves to be reachable, not a figure the module
holds.

Nothing here names a flag id, a band, a weight or a region.  6.3 turns a
result into a ``DATE_IMPLAUSIBLE_DOB`` flag, and the id list already says the
two halves share one id, so one status covers both and the record's own two
dates say which half it was.
"""

import ast
import dataclasses
import datetime
import inspect
import pathlib

import pytest

from app.pipeline.tier0 import dates, mrz
from app.risk import flag_ids

#: The reference every table below is measured against, and the one the rest
#: of the suite uses: 3.13's sweep read the same day.
REFERENCE = datetime.date(2026, 9, 30)

#: A maximum configured tight enough that both halves of the rule are
#: reachable.  **This is a test's figure and not the module's**: at
#: :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE` the band spans more than a
#: century, every real reading falls inside it, and neither implausible answer
#: is available.
TIGHT = 18


# --- the two halves the task names ----------------------------------------


def test_a_birth_that_has_not_happened_is_implausible():
    """The nearest reading of "30" in 2026 is October, and October is ahead."""
    result = dates.dob_result("261001", REFERENCE, TIGHT)

    assert result.status == dates.IMPLAUSIBLE
    assert result.birth == datetime.date(2026, 10, 1)
    assert result.reference == REFERENCE


def test_a_birth_today_has_happened_and_is_the_boundary():
    """The comparison is on the whole day, so today is not a future birth."""
    result = dates.dob_result("260930", REFERENCE, TIGHT)

    assert result.status == dates.PLAUSIBLE
    assert result.birth == REFERENCE


def test_a_birth_older_than_the_maximum_is_implausible():
    result = dates.dob_result("070930", REFERENCE, TIGHT)

    assert result.status == dates.IMPLAUSIBLE
    assert result.birth == datetime.date(2007, 9, 30)


@pytest.mark.parametrize(
    "text, reference, max_age, status, birth",
    [
        pytest.param(
            "261001",
            REFERENCE,
            TIGHT,
            dates.IMPLAUSIBLE,
            datetime.date(2026, 10, 1),
            id="tomorrow-has-not-happened",
        ),
        pytest.param(
            "260930",
            REFERENCE,
            TIGHT,
            dates.PLAUSIBLE,
            REFERENCE,
            id="today-has",
        ),
        pytest.param(
            "080930",
            REFERENCE,
            TIGHT,
            dates.PLAUSIBLE,
            datetime.date(2008, 9, 30),
            id="exactly-the-maximum-age",
        ),
        pytest.param(
            "080929",
            REFERENCE,
            TIGHT,
            dates.PLAUSIBLE,
            datetime.date(2008, 9, 29),
            id="a-day-before-the-maximum-birthday",
        ),
        pytest.param(
            "070930",
            REFERENCE,
            TIGHT,
            dates.IMPLAUSIBLE,
            datetime.date(2007, 9, 30),
            id="one-day-older-than-the-maximum",
        ),
        pytest.param(
            "070930",
            datetime.date(2026, 9, 29),
            TIGHT,
            dates.PLAUSIBLE,
            datetime.date(2007, 9, 30),
            id="the-same-digits-a-day-before-the-nineteenth-birthday",
        ),
        pytest.param(
            "070930",
            REFERENCE,
            TIGHT + 1,
            dates.PLAUSIBLE,
            datetime.date(2007, 9, 30),
            id="one-more-year-of-maximum-makes-it-plausible",
        ),
        pytest.param(
            "260929",
            REFERENCE,
            0,
            dates.IMPLAUSIBLE,
            datetime.date(2026, 9, 29),
            id="yesterday-is-over-a-maximum-of-zero",
        ),
        pytest.param(
            "260930",
            REFERENCE,
            0,
            dates.PLAUSIBLE,
            REFERENCE,
            id="today-is-not-over-a-maximum-of-zero",
        ),
        pytest.param(
            "260101",
            REFERENCE,
            TIGHT,
            dates.PLAUSIBLE,
            datetime.date(2026, 1, 1),
            id="a-nine-month-old",
        ),
        pytest.param(
            "000229",
            REFERENCE,
            mrz.MAX_BIRTH_AGE,
            dates.PLAUSIBLE,
            datetime.date(2000, 2, 29),
            id="a-29th-of-february-the-century-has",
        ),
    ],
)
def test_the_boundary_is_one_day_and_it_is_the_same_from_both_sides(
    text, reference, max_age, status, birth
):
    """Every row is a neighbour of the one above it: the maximum is inclusive."""
    result = dates.dob_result(text, reference, max_age)

    assert result.status == status
    assert result.birth == birth


def test_the_maximum_is_configurable_and_the_verdict_moves_with_it():
    """Sixteen is inside the band and fifteen is not, on the same characters."""
    assert dates.dob_result("100101", REFERENCE, 16).status == dates.PLAUSIBLE
    assert dates.dob_result("100101", REFERENCE, 15).status == dates.IMPLAUSIBLE


@pytest.mark.parametrize(
    "text, max_age, ahead",
    [
        pytest.param("261001", TIGHT, True, id="the-future-half"),
        pytest.param("070930", TIGHT, False, id="the-too-old-half"),
    ],
)
def test_which_half_fired_is_readable_off_the_record_alone(
    text, max_age, ahead
):
    """One status for both halves, so the record's own two dates must say which.

    This is what the shared id buys: `DATE_IMPLAUSIBLE_DOB` names one rule and
    6.3 still writes a reason, because a birth after the reference and a birth
    before it are different sentences and neither needs a second status.
    """
    result = dates.dob_result(text, REFERENCE, max_age)

    assert (result.birth > result.reference) is ahead


# --- the direction of the reading ------------------------------------------


def test_a_birth_whose_digits_sit_ahead_of_the_reference_reads_a_century_back():
    """The finding a forward reading would make on nearly every holder.

    Read in the reference's own century, "99" is 2099 and three quarters of
    every date of birth in the country is a birth that has not happened.  The
    band is what saves the rule: a century back is inside it, so the holder is
    read as the 26-year-old the document means and the rule stays silent.
    """
    result = dates.dob_result("991231", REFERENCE)

    assert result.status == dates.PLAUSIBLE
    assert result.birth == datetime.date(1999, 12, 31)


def test_the_future_half_is_exactly_what_the_century_function_threw_away():
    """`infer_birth_year` skips a candidate that has not happened and reads on.

    That is right for it -- a function whose job is to name a birth cannot
    answer with a future one -- and it is why this rule cannot be built on it:
    the reading that rule discarded is the finding this rule exists to report.
    """
    assert mrz.infer_birth_year("261231", REFERENCE) == 1926

    result = dates.dob_result("261231", REFERENCE, TIGHT)

    assert result.status == dates.IMPLAUSIBLE
    assert result.birth == datetime.date(2026, 12, 31)


def test_the_birth_rule_reads_backwards_where_the_issue_rule_reads_straight_on():
    """Two rules beside each other in one module, reading opposite ways."""
    assert dates.issue_result("991231", REFERENCE).issue == datetime.date(
        2099, 12, 31
    )
    assert dates.dob_result("991231", REFERENCE).birth == datetime.date(
        1999, 12, 31
    )


@pytest.mark.parametrize(
    "text, reference",
    [
        pytest.param("800101", REFERENCE, id="1980"),
        pytest.param("000101", REFERENCE, id="2000"),
        pytest.param("260930", REFERENCE, id="today"),
        pytest.param("991231", REFERENCE, id="a-century-ahead-on-print"),
        pytest.param("261231", REFERENCE, id="a-century-ahead-on-the-clock"),
        pytest.param("000229", datetime.date(2100, 6, 1), id="a-leap-century-has-it"),
        pytest.param("990229", datetime.date(2100, 6, 1), id="neither-century-has-it"),
        pytest.param("AAAAAA", REFERENCE, id="unreadable"),
        pytest.param("993199", REFERENCE, id="a-month-of-99"),
        pytest.param("013200", REFERENCE, id="a-day-of-32"),
    ],
)
def test_at_the_default_maximum_this_rule_is_the_century_function_made_a_day(
    text, reference
):
    """One reading and one band, so the two agree wherever the band is silent.

    `MAX_BIRTH_AGE` is wider than the two centuries the reading reaches, so at
    the default a real past birth is always inside the band: the two rules can
    then disagree about nothing at all, and a disagreement is a signal that
    one of them has been changed.
    """
    year = mrz.infer_birth_year(text, reference)
    result = dates.dob_result(text, reference)

    assert result.status == (
        dates.PLAUSIBLE if year is not None else dates.UNDETERMINED
    )
    assert result.birth == (
        None
        if year is None
        else datetime.date(year, int(text[2:4]), int(text[4:6]))
    )


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("800101", id="a-holder-in-the-1980s"),
        pytest.param("000101", id="a-holder-in-2000"),
        pytest.param("260930", id="a-birth-today"),
        pytest.param("991231", id="digits-ahead-of-the-clock"),
    ],
)
def test_at_the_default_maximum_neither_half_can_fire(text):
    """A finding this project cannot make is asserted rather than promised.

    A reading that spans at most two centuries implies an age of at most 99,
    and `MAX_BIRTH_AGE` is 120, so the band admits every real reading and the
    two implausible answers are unreachable.  That is what the task's
    "configurable" is for: only a tightened maximum makes this rule able to
    report anything.
    """
    assert dates.dob_result(text, REFERENCE).status == dates.PLAUSIBLE


# --- the answers that are not a verdict ------------------------------------


@pytest.mark.parametrize(
    "text, reference",
    [
        pytest.param("<<<<<<", REFERENCE, id="filler"),
        pytest.param("AAAAAA", REFERENCE, id="letters"),
        pytest.param("74o812", REFERENCE, id="a-letter-inside"),
        pytest.param("99 199", REFERENCE, id="a-space-inside"),
        pytest.param("993199", REFERENCE, id="a-month-of-99"),
        pytest.param("013200", REFERENCE, id="a-day-of-32"),
        pytest.param(
            "990229",
            datetime.date(2100, 6, 1),
            id="a-29th-of-february-neither-century-had",
        ),
    ],
)
def test_a_document_that_does_not_tell_us_is_undetermined(text, reference):
    """One answer for unreadable, impossible and unplaceable alike."""
    result = dates.dob_result(text, reference)

    assert result.status == dates.UNDETERMINED
    assert result.birth is None


def test_an_undetermined_result_still_carries_the_reference_it_was_asked_against():
    """A gap is a fact about the document, not about the day it was read."""
    result = dates.dob_result("993199", REFERENCE)

    assert result.reference == REFERENCE


def test_a_29th_of_february_a_century_back_is_a_birth_and_not_a_gap():
    """The mirror of the expiry rule's corner, and it lands the other way.

    A date of issue is read in one century, so `000229` in a century without a
    29th of February is the end of the road.  A birth is read in two, and
    2000-02-29 is a real day a century behind the reference -- which is what
    `infer_birth_year` has always done with these six characters.
    """
    reference = datetime.date(2100, 6, 1)

    assert dates.issue_result("000229", reference).status == dates.UNDETERMINED
    assert dates.dob_result("000229", reference).birth == datetime.date(
        2000, 2, 29
    )


def test_the_age_turns_on_the_day_a_birthday_falls_and_not_on_the_year():
    """Whole years elapsed, so the same six characters change verdict in a day.

    Born on the 30th of September 2007, the difference between the two *years*
    is 19 on the 29th of September 2026 and on the 30th alike, while the age is
    18 and then 19.  A maximum of 18 admits the first and refuses the second,
    which is the only reading of "an age" that means what it says.
    """
    the_day_before = datetime.date(2026, 9, 29)

    assert (
        dates.dob_result("070930", the_day_before, TIGHT).status
        == dates.PLAUSIBLE
    )
    assert (
        dates.dob_result("070930", REFERENCE, TIGHT).status
        == dates.IMPLAUSIBLE
    )


def test_the_project_s_own_figure_does_not_bound_the_century_function_either():
    """`MAX_BIRTH_AGE` is wider than any reading `infer_birth_year` reaches.

    Its search only falls back to a century back when the printed digits are
    ahead of the reference's own year, and then that fallback is under a
    hundred years old -- so the band inside `mrz.py` excludes nothing at all.
    The band in this rule is what excludes, which is the whole reason the
    task's maximum has to be configurable to be worth configuring.
    """
    text = "000101"

    assert mrz.infer_birth_year(text, REFERENCE) == 2000
    assert dates.dob_result(text, REFERENCE).status == dates.PLAUSIBLE
    assert dates.dob_result(text, REFERENCE, 0).status == dates.IMPLAUSIBLE


# --- the maximum is the caller's -------------------------------------------


def test_the_default_maximum_is_the_project_s_own_figure_and_no_second_one():
    """One number bounds a birth, and it is the one `mrz.py` already holds."""
    signature = inspect.signature(dates.dob_result)

    assert signature.parameters["max_age"].default == mrz.MAX_BIRTH_AGE

    figures = {
        name
        for name in dir(dates)
        if not name.startswith("_")
        and isinstance(getattr(dates, name), int)
        and not isinstance(getattr(dates, name), bool)
    }

    assert figures == {"MAX_BIRTH_AGE"}
    assert dates.MAX_BIRTH_AGE is mrz.MAX_BIRTH_AGE

    tree = ast.parse(pathlib.Path(dates.__file__).read_text(encoding="utf-8"))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    }

    assert literals == {
        0,
        1,
        100,
    }, "0 is a band's floor, 1 the expiry century step and 100 the century"


@pytest.mark.parametrize(
    "max_age",
    [
        pytest.param(-1, id="a-negative-maximum"),
        pytest.param(mrz.MAX_BIRTH_AGE + 1, id="over-the-projects-own-figure"),
        pytest.param("18", id="a-string"),
        pytest.param(18.0, id="a-float"),
        pytest.param(None, id="none"),
        pytest.param([18], id="a-list"),
        pytest.param(True, id="a-bool"),
    ],
)
def test_a_maximum_that_is_not_a_number_of_years_is_refused(max_age):
    """A bound that has been typed wrong is a caller mistake, not a wide band."""
    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.dob_result("260930", REFERENCE, max_age)

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_maximum_at_the_project_s_own_figure_is_accepted():
    """The bound is the ceiling of what may be configured, and it is legal."""
    assert (
        dates.dob_result("260930", REFERENCE, mrz.MAX_BIRTH_AGE).status
        == dates.PLAUSIBLE
    )


def test_the_reference_date_is_a_parameter_and_never_a_default():
    signature = inspect.signature(dates.dob_result)

    assert list(signature.parameters) == ["text", "reference", "max_age"]
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
        dates.dob_result("260930", reference)

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_timestamp_is_a_legal_reference_and_the_day_is_what_is_compared():
    """`datetime.datetime` is a `datetime.date`, so this is not that mistake."""
    stamp = datetime.datetime(2026, 9, 30, 23, 59, 59)
    result = dates.dob_result("260930", stamp, TIGHT)

    assert result.status == dates.PLAUSIBLE
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
        dates.dob_result(text, REFERENCE)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the record -------------------------------------------------------------


def test_the_result_carries_three_fields_and_nothing_else():
    assert [f.name for f in dataclasses.fields(dates.BirthResult)] == [
        "status",
        "birth",
        "reference",
    ]


def test_a_result_cannot_be_edited():
    with pytest.raises(dataclasses.FrozenInstanceError):
        dates.dob_result("070930", REFERENCE, TIGHT).status = dates.PLAUSIBLE


def test_a_result_carries_no_public_method():
    """A second answer about the document would be a rule that agrees with itself."""
    public = [
        name
        for name in dir(dates.BirthResult)
        if not name.startswith("_") and callable(getattr(dates.BirthResult, name))
    ]

    assert public == []


def test_the_same_question_asked_twice_is_the_same_record():
    """Equal and hashable, so a re-run of the same screening compares cleanly."""
    first = dates.dob_result("070930", REFERENCE, TIGHT)
    second = dates.dob_result("070930", REFERENCE, TIGHT)

    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"status": "IMPLAUSIBLE"}, id="a-status-nobody-declared"),
        pytest.param({"status": 0}, id="a-status-that-is-not-a-string"),
        pytest.param({"status": None}, id="no-status"),
        pytest.param(
            {"status": dates.PLAUSIBLE, "birth": None}, id="plausible-with-no-date"
        ),
        pytest.param(
            {"status": dates.IMPLAUSIBLE, "birth": None},
            id="implausible-with-no-date",
        ),
        pytest.param(
            {"status": dates.UNDETERMINED, "birth": REFERENCE},
            id="undetermined-with-a-date",
        ),
        pytest.param(
            {"status": dates.PLAUSIBLE, "birth": "2026-09-30"}, id="a-date-as-a-string"
        ),
        pytest.param(
            {"status": dates.PLAUSIBLE, "reference": "2026-09-30"},
            id="a-reference-as-a-string",
        ),
        pytest.param(
            {"status": dates.PLAUSIBLE, "reference": None}, id="no-reference"
        ),
    ],
)
def test_a_malformed_result_is_refused_and_never_coerced(overrides):
    values = {
        "status": dates.PLAUSIBLE,
        "birth": REFERENCE,
        "reference": REFERENCE,
    }
    values.update(overrides)

    with pytest.raises(mrz.MrzValueError) as excinfo:
        dates.BirthResult(**values)

    assert type(excinfo.value) is mrz.MrzValueError


# --- a rule decides nothing ------------------------------------------------


def test_the_result_names_no_flag_id_and_carries_no_weight_or_region():
    """`DATE_IMPLAUSIBLE_DOB` and a band are 6.3's to attach, not this rule's."""
    names = {field.name for field in dataclasses.fields(dates.BirthResult)}

    assert names == {"status", "birth", "reference"}
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


def test_both_halves_carry_the_one_id_the_id_list_names_for_them():
    """`flag_ids.py` says both conditions are one rule, and this holds it to it."""
    assert flag_ids.DATE_IMPLAUSIBLE_DOB in flag_ids.FLAG_IDS
    assert dates.IMPLAUSIBLE == "implausible"
    assert dates.PLAUSIBLE == "plausible"


def test_the_three_status_sets_share_exactly_the_gap():
    """A verdict belongs to the rule that judged it; the gap is the document's."""
    assert dates.BIRTH_STATUSES & dates.EXPIRY_STATUSES == frozenset(
        {dates.UNDETERMINED}
    )
    assert dates.BIRTH_STATUSES & dates.ISSUE_STATUSES == frozenset(
        {dates.UNDETERMINED}
    )


def test_the_three_statuses_are_the_module_s_own_and_are_exported():
    assert dates.BIRTH_STATUSES == frozenset(
        {dates.PLAUSIBLE, dates.IMPLAUSIBLE, dates.UNDETERMINED}
    )
    assert len(dates.BIRTH_STATUSES) == 3
    assert {
        "BIRTH_STATUSES",
        "PLAUSIBLE",
        "IMPLAUSIBLE",
        "BirthResult",
        "dob_result",
    } <= set(dates.__all__)


def test_this_rule_does_not_change_the_other_two_rules_s_answers():
    """Three rules beside each other in one module, and none reads another."""
    assert dates.expiry_result("260930", REFERENCE).status == dates.EXPIRING_TODAY
    assert dates.expiry_result("120415", REFERENCE).status == dates.EXPIRED
    assert dates.issue_result("261001", REFERENCE).status == dates.NOT_YET_VALID
    assert dates.issue_result("250101", REFERENCE).status == dates.ISSUED
