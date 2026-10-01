"""5.8 -- the ``ReferenceDate`` dependency, and the ban on reading the clock.

The three rules that read a printed date already took the day they were asked
against as an argument, and :mod:`~app.pipeline.tier0.mrz` already walked its
own source to prove it never reads the calendar.  So this task adds the
*dependency*: one declared name for the day a rule is handed, so the cascade
(6.3 and what follows it) has a single thing to inject, a signature says what
it is asking for, and one test can hold every rule to it rather than one rule
at a time.

**The dependency is an alias and not a type of this project's own.**  A
subclass would make every ``isinstance`` in the module and every record a
caller already holds answer to two questions, and a wrapper would be a place a
clock could be read from -- which is the one thing ``tasks.md`` bans.  So
:data:`dates.ReferenceDate` *is* :class:`datetime.date`, and the test below
holds that identity rather than trusting the name.

The source is **walked, not grepped**, for the reason :mod:`test_mrz` gives:
this docstring and the module's own docstring name ``datetime.now()`` in order
to say it is not used, so a substring test would have to ban the sentence that
documents the rule.
"""

import ast
import dataclasses
import datetime
import inspect
import pathlib

import pytest

from app.pipeline.tier0 import dates, mrz

#: The reference the behavioural tables below are measured against, and the
#: one the rest of the suite uses: 3.13's sweep read the same day.
REFERENCE = datetime.date(2026, 9, 30)

#: A maximum configured tight enough that both halves of the birth rule are
#: reachable, so the *reference* is what moves that answer and not the band.
TIGHT = 18

#: The four names a call to the calendar can go by.  This is the set
#: :mod:`test_mrz` walks ``mrz.py`` with, and it is four rather than one
#: because ``datetime.now()`` is the sentence ``tasks.md`` uses and
#: ``date.today()`` is the same dependency written more quietly.
CLOCK_CALLS = frozenset({"now", "utcnow", "today", "fromtimestamp"})

#: The three rules that read a printed date, so each takes the dependency as
#: an argument.
THE_RULES_THAT_READ_A_DATE = (
    dates.expiry_result,
    dates.issue_result,
    dates.dob_result,
)
#: All four, and the fourth is in the list because it is the *exception*
#: rather than a fifth reading: it is handed the two records and carries the
#: reference off them (``D11``), so a test holding "every rule" has to say
#: what it holds about this one.
ALL_FOUR_RULES = (*THE_RULES_THAT_READ_A_DATE, dates.consistency_result)

#: The four records, one per rule, each carrying the day it was asked against.
THE_RECORDS = (
    dates.ExpiryResult,
    dates.IssueResult,
    dates.BirthResult,
    dates.ConsistencyResult,
)


def _ask(rule, text: str, reference, *rest):
    """Call ``rule`` on ``text`` and ``reference``, with the birth band if asked."""
    return rule(text, reference, *rest)


def _tree(module) -> ast.Module:
    """The parsed source of ``module``."""
    return ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))


def _clock_calls(module) -> list[str]:
    """Every attribute call named after the calendar in ``module``'s source."""
    return [
        node.func.attr
        for node in ast.walk(_tree(module))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        if node.func.attr in CLOCK_CALLS
    ]


def _declared_type(record, name: str):
    """The type ``record`` declares on its ``name`` field."""
    names = [field.name for field in dataclasses.fields(record)]
    return dataclasses.fields(record)[names.index(name)].type


# --- the dependency is one name for the day ---------------------------------


def test_the_dependency_is_the_plain_date_and_not_a_type_of_this_projects_own():
    """An alias is the whole of it: a second date type is what is forbidden."""
    assert dates.ReferenceDate is datetime.date
    assert issubclass(dates.ReferenceDate, datetime.date)
    assert "ReferenceDate" in dates.__all__

    # No class of this project's own stands in for a date: the module *defines*
    # four, and they are records.  A subclass or a wrapper would have to be
    # defined here to be handed to a rule, so the class list is the claim.
    assert {
        node.name for node in _tree(dates).body if isinstance(node, ast.ClassDef)
    } == {
        "ExpiryResult",
        "IssueResult",
        "BirthResult",
        "ConsistencyResult",
    }
    assert not dataclasses.is_dataclass(dates.ReferenceDate)


def test_naming_the_dependency_changes_no_rule_s_answer():
    """The alias is a declaration, not a new behaviour to reconcile later."""
    assert dates.expiry_result("260930", REFERENCE) == dates.ExpiryResult(
        dates.EXPIRING_TODAY, datetime.date(2026, 9, 30), REFERENCE
    )
    assert dates.issue_result("250101", REFERENCE) == dates.IssueResult(
        dates.ISSUED, datetime.date(2025, 1, 1), REFERENCE
    )
    assert dates.dob_result("161001", REFERENCE, TIGHT) == dates.BirthResult(
        dates.PLAUSIBLE, datetime.date(2016, 10, 1), REFERENCE
    )


def test_the_dependency_is_written_by_name_wherever_it_is_declared():
    """The alias and `datetime.date` are one object, so only the source says."""
    tree = _tree(dates)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }

    # The three rules that read a printed date declare it as a parameter.
    assert {
        name: [
            ast.unparse(arg.annotation)
            for arg in functions[name].args.args
            if arg.arg == "reference"
        ]
        for name in ("expiry_result", "issue_result", "dob_result")
    } == {
        "expiry_result": ["ReferenceDate"],
        "issue_result": ["ReferenceDate"],
        "dob_result": ["ReferenceDate"],
    }
    # And all four records declare it as the field they carry it in, the
    # fourth included: it is carried there rather than asked for.
    assert {
        name: [
            ast.unparse(node.annotation)
            for node in classes[name].body
            if isinstance(node, ast.AnnAssign)
            and node.target.id == "reference"
        ]
        for name in (
            "ExpiryResult",
            "IssueResult",
            "BirthResult",
            "ConsistencyResult",
        )
    } == {
        "ExpiryResult": ["ReferenceDate"],
        "IssueResult": ["ReferenceDate"],
        "BirthResult": ["ReferenceDate"],
        "ConsistencyResult": ["ReferenceDate"],
    }


# --- every rule asks for it and none of them defaults it --------------------


@pytest.mark.parametrize(
    ("rule", "parameters"),
    [
        pytest.param(dates.expiry_result, ["text", "reference"], id="expiry"),
        pytest.param(dates.issue_result, ["text", "reference"], id="issue"),
        pytest.param(
            dates.dob_result, ["text", "reference", "max_age"], id="birth"
        ),
    ],
)
def test_every_rule_that_reads_a_date_declares_the_dependency(rule, parameters):
    """The type on the signature is the injection point, and it is bare."""
    signature = inspect.signature(rule)

    assert list(signature.parameters) == parameters
    assert signature.parameters["reference"].annotation is dates.ReferenceDate
    assert signature.parameters["reference"].default is inspect.Parameter.empty


def test_no_rule_has_a_default_that_could_have_come_from_the_clock():
    """A ``date.today()`` default passes every behavioural test, and is the bug."""
    defaults = {
        name: parameter.default
        for rule in ALL_FOUR_RULES
        for name, parameter in inspect.signature(rule).parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }

    # The one default in the module is the caller's age band, and it is the
    # project's own figure rather than a day.  Anything callable here would be
    # a rule computing its own reference at the moment it was called.
    assert defaults == {"max_age": mrz.MAX_BIRTH_AGE}
    assert not [
        value
        for value in defaults.values()
        if isinstance(value, datetime.date) or callable(value)
    ]


@pytest.mark.parametrize("record", THE_RECORDS, ids=lambda record: record.__name__)
def test_every_record_carries_the_dependency_and_names_it_on_the_field(record):
    """The day a finding quotes is the day the question was asked against."""
    names = [field.name for field in dataclasses.fields(record)]

    assert "reference" in names
    assert _declared_type(record, "reference") is dates.ReferenceDate


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("2026-09-30", id="a-string"),
        pytest.param(None, id="none"),
        pytest.param(20260930, id="an-int"),
        pytest.param((2026, 9, 30), id="a-tuple"),
    ],
)
@pytest.mark.parametrize(
    "rule",
    THE_RULES_THAT_READ_A_DATE,
    ids=["expiry", "issue", "birth"],
)
def test_a_dependency_that_is_not_a_day_is_refused_at_the_seam(rule, reference):
    """A caller who has not injected a day has made a mistake, and it is loud."""
    band = (TIGHT,) if rule is dates.dob_result else ()

    with pytest.raises(mrz.MrzValueError) as excinfo:
        _ask(rule, "260930", reference, *band)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the injected day is what the answer turns on ---------------------------


def test_the_expiry_rule_answers_on_the_day_it_is_asked_about():
    """`300930` is valid now, the last day of its window, and over after it."""
    assert dates.expiry_result("300930", REFERENCE).status == dates.VALID
    assert dates.expiry_result("300930", datetime.date(2030, 9, 30)).status == (
        dates.EXPIRING_TODAY
    )
    assert dates.expiry_result("300930", datetime.date(2031, 1, 1)).status == (
        dates.EXPIRED
    )


def test_the_issue_rule_answers_on_the_day_it_is_asked_about():
    """`270101` opens a window that has not opened on the reference day."""
    assert dates.issue_result("270101", REFERENCE).status == dates.NOT_YET_VALID
    assert dates.issue_result("270101", datetime.date(2027, 1, 1)).status == (
        dates.ISSUED
    )


def test_the_birth_rule_answers_on_the_day_it_is_asked_about():
    """The same birth is implausible today and ordinary a year on."""
    assert dates.dob_result("261001", REFERENCE, TIGHT).status == dates.IMPLAUSIBLE
    assert dates.dob_result("261001", datetime.date(2027, 1, 1), TIGHT).status == (
        dates.PLAUSIBLE
    )


@pytest.mark.parametrize(
    "rule",
    THE_RULES_THAT_READ_A_DATE,
    ids=["expiry", "issue", "birth"],
)
def test_the_record_says_which_day_it_was_asked_against(rule):
    """A finding is only explainable if the record names the day behind it."""
    stamp = datetime.datetime(2026, 9, 30, 23, 59, 59)
    band = (TIGHT,) if rule is dates.dob_result else ()
    result = _ask(rule, "260930", stamp, *band)

    assert result.reference == REFERENCE
    # A timestamp is a legal injection and is reduced to its day, so the field
    # carries the dependency rather than the wider type that satisfies it.
    assert type(result.reference) is dates.ReferenceDate


def test_the_same_day_asked_twice_answers_the_same_thing():
    """What an injected day buys: the answer is a fact, not an artefact."""
    assert dates.expiry_result("260930", REFERENCE) == dates.expiry_result(
        "260930", REFERENCE
    )


# --- no module in the date rules reaches the calendar -----------------------


def test_no_module_in_the_date_rules_calls_the_clock():
    """`datetime.now()` inside check logic is banned by `tasks.md`."""
    for module in (dates, mrz):
        assert _clock_calls(module) == [], f"{module.__name__} reads the clock"

    # The walk only means something if these modules hold `datetime` at all: a
    # module that could not have read the calendar would pass vacuously.
    imported = {
        alias.name
        for module in (dates, mrz)
        for node in ast.walk(_tree(module))
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "datetime" in imported
    assert CLOCK_CALLS == {"now", "utcnow", "today", "fromtimestamp"}


def test_the_four_rules_are_the_module_s_whole_surface_for_the_dependency():
    """Every rule and its parameters in one table, so a fifth rule is a change."""
    assert {
        rule.__name__: list(inspect.signature(rule).parameters)
        for rule in ALL_FOUR_RULES
    } == {
        "expiry_result": ["text", "reference"],
        "issue_result": ["text", "reference"],
        "dob_result": ["text", "reference", "max_age"],
        "consistency_result": ["issue", "expiry"],
    }


# --- the fourth rule carries the dependency rather than taking it -----------


def test_the_fourth_rule_carries_the_dependency_and_does_not_take_it_again():
    """`D11`'s exception is pinned here, so it cannot drift into a fifth rule."""
    signature = inspect.signature(dates.consistency_result)

    assert list(signature.parameters) == ["issue", "expiry"]
    assert "reference" not in signature.parameters

    # It is not exempt from the dependency, only from being handed it twice:
    # both arguments are records that hold one, they must agree on it, and the
    # result carries the day they agree on.
    issue = dates.issue_result("250101", REFERENCE)
    expiry = dates.expiry_result("300930", REFERENCE)
    result = dates.consistency_result(issue, expiry)

    assert result.reference == REFERENCE
    assert _declared_type(dates.ConsistencyResult, "reference") is dates.ReferenceDate
