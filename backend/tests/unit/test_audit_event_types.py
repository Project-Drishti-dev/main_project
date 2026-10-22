"""10.1: the six event-type names, closed and free of duplicates.

Beyond the task's duplicate check this pins the exact six spellings, that
each constant stands for its own name as plain text rather than an enum
member, that the vocabulary has one home in ``app/``, and that this module
declares no behaviour -- refusing a name is 10.2's writer.
"""

import ast
from collections import Counter
from pathlib import Path

import pytest

from app.audit import event_types


#: The six names ``tasks.md`` 10.1 spells, in the order it spells them.
TASK_NAMES = (
    "screening_created",
    "analysis_completed",
    "tier_completed",
    "decision_recorded",
    "override_recorded",
    "screening_deleted",
)

#: The constant each of those names is expected to be stated as.
CONSTANT_NAMES = (
    "SCREENING_CREATED",
    "ANALYSIS_COMPLETED",
    "TIER_COMPLETED",
    "DECISION_RECORDED",
    "OVERRIDE_RECORDED",
    "SCREENING_DELETED",
)


def test_the_vocabulary_holds_no_duplicates():
    """A repeated name would make one trail mean two things."""
    vocabulary = event_types.EVENT_TYPES

    assert isinstance(vocabulary, tuple), (
        "a set cannot hold a duplicate, so the check below would be vacuous"
    )
    repeated = sorted(n for n, c in Counter(vocabulary).items() if c > 1)

    assert repeated == []


def test_the_vocabulary_is_exactly_the_six_names_the_task_spells():
    assert set(event_types.EVENT_TYPES) == set(TASK_NAMES)


@pytest.mark.parametrize("constant, value", list(zip(CONSTANT_NAMES, TASK_NAMES)))
def test_each_constant_stands_for_its_own_name(constant, value):
    assert getattr(event_types, constant) == value


def test_every_value_is_plain_text_rather_than_an_enum_member():
    for value in event_types.EVENT_TYPES:
        assert type(value) is str


def test_the_module_exports_the_six_constants_and_the_closed_tuple():
    assert set(event_types.__all__) == set(CONSTANT_NAMES) | {"EVENT_TYPES"}


def test_no_other_module_in_the_app_package_spells_one_of_the_six_names():
    """One vocabulary: every other module imports the constant."""
    package = Path(event_types.__file__).parent.parent
    offenders = []
    for module in sorted(package.rglob("*.py")):
        if module == Path(event_types.__file__):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in TASK_NAMES:
                offenders.append(f"{module.name}: {node.value!r}")

    assert offenders == []


def test_this_module_declares_no_callable():
    source = Path(event_types.__file__).read_text(encoding="utf-8")
    defined = [
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    assert defined == []
