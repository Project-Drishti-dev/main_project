"""The flag-id list is the only place the set of legal ids is written down.

Task 5.3 asks for a module holding a constant for every flag id the system
uses, and for a test that it exposes no duplicates.  The rest of this file is
the rest of that claim: that each constant is named after the id it holds, that
the set the weightset is checked against holds every constant and nothing
else, that the named prefixes are the only families, and that no id collides
with a name the pipeline already uses -- ``MRZ_LAYOUTS`` and ``DATE_LENGTH``
are the two that would otherwise be one refactor away from a silent clash.

**The duplicate check is the headline and it is deliberately dull.**  A test
failing here means one id has two names, which is a typing mistake rather
than a design question, so it is a plain set comparison and nothing else.
"""

import ast
import inspect
from pathlib import Path

import pytest

from app.risk import flag_ids, flags

#: The nine families the module is required to hold, stated here rather than
#: read from ``PREFIXES`` so that widening the list is a deliberate act.  14.3
#: opened ``QUALITY``, the capture gate that runs as stage 0.
NAMED_PREFIXES = (
    "QUALITY",
    "MRZ",
    "DATE",
    "WATCHLIST",
    "OCR",
    "LAYOUT",
    "FACE",
    "TAMPER",
    "CROSSDOC",
)

TIER0_PACKAGE = Path(flags.__file__).parent.parent / "pipeline" / "tier0"


def id_constants():
    """The module's flag ids as ``{constant name: id}``.

    **Every module-level string is an id**, which is the rule the module
    documents: :data:`PREFIXES` is a tuple and :data:`FLAG_IDS` is a frozenset,
    so nothing else here is a string.  A helper that quietly skipped names it
    did not recognise would let a mistyped constant escape the checks below.
    """
    return {
        name: value
        for name, value in vars(flag_ids).items()
        if name.isupper() and isinstance(value, str)
    }


def uppercase_names(path):
    """The uppercase names a module assigns at module level, read without importing it.

    **Names, not values, because the collision is about the name.**  A flag id
    is a string and ``mrz_region.MRZ_LAYOUTS`` is a dict, and a weightset keyed
    on a name the pipeline already means by something else is the failure this
    looks for.  Read statically, so the check does not have to import OpenCV to
    see ``mrz_region``'s names.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name) and target.id.isupper()
    }


def test_the_module_exposes_no_duplicate_flag_ids():
    """The claim 5.3 is named for: one id, one name, across the whole module."""
    names = id_constants()
    seen = {}
    for name, value in names.items():
        assert value not in seen, (
            f"{name} and {seen[value]} both hold the flag id {value}"
        )
        seen[value] = name


def test_every_constant_is_named_after_the_id_it_holds():
    """A constant whose name differs from its value is one step from a duplicate."""
    misnamed = {
        name: value
        for name, value in id_constants().items()
        if name != value
    }

    assert misnamed == {}


def test_the_id_set_holds_every_constant_and_nothing_else():
    """`FLAG_IDS` is the weightset's list, so an id outside it is unscored."""
    constants = id_constants()

    assert flag_ids.FLAG_IDS == set(constants.values())
    assert set(flag_ids.ALL_FLAG_IDS) == set(constants.values())
    assert flag_ids.FLAG_IDS == frozenset(flag_ids.ALL_FLAG_IDS)


def test_every_id_is_listed_exactly_once_in_the_ordered_tuple():
    """`ALL_FLAG_IDS` is built by name, so a name left out is a silent omission."""
    constants = id_constants()

    assert len(flag_ids.ALL_FLAG_IDS) == len(constants)
    assert sorted(flag_ids.ALL_FLAG_IDS) == sorted(constants.values())


def test_the_public_names_are_the_ordered_tuple_and_the_three_tables():
    """`__all__` is derived from the ids, so it may not hold anything else."""
    constants = id_constants()

    assert flag_ids.__all__ == (
        "ALL_FLAG_IDS",
        "FLAG_IDS",
        "PREFIXES",
    ) + flag_ids.ALL_FLAG_IDS
    assert set(flag_ids.__all__) == {"ALL_FLAG_IDS", "FLAG_IDS", "PREFIXES"} | set(
        constants
    )


def test_the_named_prefixes_are_the_ones_the_module_holds():
    """A family is a decision about this list, not a string in a module."""
    assert tuple(flag_ids.PREFIXES) == NAMED_PREFIXES


@pytest.mark.parametrize("flag_id", flag_ids.ALL_FLAG_IDS, ids=flag_ids.ALL_FLAG_IDS)
def test_every_flag_id_carries_one_of_the_named_prefixes(flag_id):
    """A prefix nobody named is an id the frontend cannot group and 7.1 cannot find."""
    prefixes = tuple(f"{prefix}_" for prefix in flag_ids.PREFIXES)

    assert flag_id.startswith(prefixes)


@pytest.mark.parametrize("prefix", NAMED_PREFIXES)
def test_every_named_prefix_holds_at_least_one_flag_id(prefix):
    """An empty family is a prefix the list promises and no rule can emit."""
    assert any(value.startswith(f"{prefix}_") for value in flag_ids.FLAG_IDS)


def test_the_ordered_tuple_runs_the_families_in_cascade_order():
    """The order of `ALL_FLAG_IDS` is tier 0, tier 1, tier 2, then crossdoc."""
    prefixes = [value.split("_", 1)[0] for value in flag_ids.ALL_FLAG_IDS]
    expected = [
        prefix
        for prefix in NAMED_PREFIXES
        for _ in range(prefixes.count(prefix))
    ]

    assert prefixes == expected


def test_the_module_imports_nothing():
    """The weightset loader and the verifier read this list; neither should pull in OpenCV."""
    tree = ast.parse(inspect.getsource(flag_ids))
    imported = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert imported == []


def test_no_flag_id_collides_with_a_name_the_risk_package_already_uses():
    """`WEIGHT_BANDS` and `MIN_REGION_CORNERS` live beside the ids in one package."""
    package = Path(flags.__file__).parent

    others = set(flags.__all__)
    for module in sorted(package.glob("*.py")):
        if module.name == flag_ids.__name__.rsplit(".", 1)[-1] + ".py":
            continue
        others.update(uppercase_names(module))

    assert set(flag_ids.FLAG_IDS) & others == set()


def test_no_flag_id_collides_with_a_name_the_mrz_pipeline_already_uses():
    """`MRZ_LAYOUTS`, `MRZ_SHAPES` and `DATE_LENGTH` are the near misses.

    None of them is a flag id, and all three are one refactor away from a
    spelling that would make them one -- a weightset keyed on a name the
    pipeline already means by something else.
    """
    pipeline = set()
    for module in sorted(TIER0_PACKAGE.glob("*.py")):
        pipeline.update(uppercase_names(module))

    assert set(flag_ids.FLAG_IDS) & pipeline == set()


def test_the_ids_the_specifications_name_are_all_here():
    """Every id written in a source document is a constant, not a remembered string."""
    named_elsewhere = {
        "WATCHLIST_HIT",
        "OCR_MRZ_MISMATCH",
        "LAYOUT_DEVIATION",
        "FACE_MISMATCH",
        "FACE_LOW_SIMILARITY",
        "MRZ_DOB_CHECK_DIGIT_MISMATCH",
        "DATE_EXPIRED",
    }

    assert named_elsewhere <= set(flag_ids.FLAG_IDS)
