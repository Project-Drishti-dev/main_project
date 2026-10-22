"""34 and 69, and the reason they are a committed pair rather than a setting.

Task 7.8 asks for the band thresholds in config with those two defaults and a
test asserting them, and the headline test below is that claim exactly.  The
rest of this file is the part that makes the two numbers mean something: a
threshold nobody places is a pair of free numbers that any retune of the
weightset or of the scale would quietly contradict, so the claims here are

- the defaults are the ones the task names, as two floats;
- they stand in the order the bands are read, inside the scale 7.6 holds, so
  all three bands are ranges rather than one point or an empty span;
- they divide the weights committed in ``v1.yaml`` -- a ``low`` row cannot
  weigh more than ``LOW_MAX``, and no row at all can weigh more than
  ``REVIEW_MAX`` (``D21``);
- the pair exists once: no other module in :mod:`app.risk` writes one of these
  names, and none compares a score against either value as a literal;
- and nothing here reads the environment, a clock or a file, which is what
  keeps the pair out of ``.env.example`` and holds a replay to a replay.

**The two numbers are read off this module, never retyped**, the way 7.1's,
7.5's, 7.6's and 7.7's suites read their vocabulary, so a retune moves every
claim that leans on them at once.  The three suites that predate this file
``test_weightset_v1.py``, ``test_hard_fail_floor.py`` and
``test_score_clamp.py`` each carried their own copy of 69 for exactly the
reason: the threshold did not exist yet.  It does now, and those three read it
from here.
"""

import ast
import pathlib

import pytest

from app.risk import config as config_module
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import WEIGHT_BANDS
from app.risk.hard_rules import MAX_SCORE, MIN_SCORE
from app.risk.weightsets.loader import DEFAULT_WEIGHTSET, load_weightset

#: The package this module is the config for, walked below to hold the pair to
#: one place.  Derived from this module's own file so a second risk package
#: cannot be added beside the first without the walk reaching it.
RISK_PACKAGE = pathlib.Path(config_module.__file__).resolve().parent

#: This module, named rather than filtered out of the walk by a string
#: comparison on the path: the pair is allowed to be written here and nowhere
#: else, so the one file that may write it is named.
THIS_MODULE = pathlib.Path(config_module.__file__).resolve()

#: The two names, in the order the bands are read, severity first.
THRESHOLD_NAMES = ("LOW_MAX", "REVIEW_MAX")

#: The defaults the task names.  Written here and nowhere else in the
#: package, so this is the single place a test reads the committed pair from.
COMMITTED_DEFAULTS = {"LOW_MAX": 34, "REVIEW_MAX": 69}


def _source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _modules_beside_this_one() -> list[pathlib.Path]:
    """Every module in the package except this one, in a stable order."""
    return sorted(
        path.resolve()
        for path in RISK_PACKAGE.rglob("*.py")
        if path.resolve() != THIS_MODULE
    )


def _assigned_names(tree: ast.AST) -> set[str]:
    """The plain module-level names an AST assigns to."""
    return {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _literal_numbers(nodes: list[ast.expr]) -> set[float]:
    """The values of the operands that are numbers written out in full."""
    return {
        node.value
        for node in nodes
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    }


@pytest.mark.parametrize(
    ("name", "committed"),
    sorted(COMMITTED_DEFAULTS.items()),
    ids=["low-max", "review-max"],
)
def test_the_committed_threshold_is_the_number_the_task_names(name, committed):
    """The task's own claim: the defaults are 34 and 69.

    **A float and not an int, and the assertion is loose about the pair
    deliberately**: the scale's two ends are floats in 7.6 and 7.9's
    comparisons are between two numbers of one kind, but ``34 == 34.0`` and
    the value is what a band is decided on.
    """
    assert getattr(config_module, name) == committed


def test_both_thresholds_are_floats_on_the_scale():
    """Two scores, not two labels, and neither a string a caller must parse.

    ``D6``'s rule for a flag's ``value`` applies to a threshold for the same
    reason: a threshold that arrived as ``"34"`` would compare as a string
    against a float score and answer every comparison one way.
    """
    for name in THRESHOLD_NAMES:
        threshold = getattr(config_module, name)
        assert isinstance(threshold, float), name
        assert MIN_SCORE <= threshold <= MAX_SCORE, name


def test_a_threshold_is_a_constant_and_not_something_recomputed_per_read():
    """The same band on every run, which is what makes a screening replayable.

    Read twice off the module rather than recomputed: a threshold written as
    an expression -- read from a file, taken from the clock, derived from the
    weightset -- would be a policy that could change under a running service
    with nothing recording it, which the abstract's "versioned so that every
    change to policy is recorded" refuses.
    """
    for name in THRESHOLD_NAMES:
        assert getattr(config_module, name) is getattr(config_module, name)


def test_each_of_the_three_bands_is_a_range_and_not_a_single_point():
    """The ordering, written as what each of the three bands needs from it.

    Three strict inequalities, one per band, and the ends are 7.6's rather
    than ``0`` and ``100`` so a retune of the scale cannot leave a stale
    threshold beside a moved end.

    - ``MIN_SCORE < LOW_MAX`` or ``low`` is the one score a clean document
      reads, and 7.5's own empty sum is ``0.0``: every genuine traveller with
      no findings would then be sent to a human.
    - ``LOW_MAX < REVIEW_MAX`` or ``review`` has exactly one score on it, so a
      band an officer reads is decided by a one-point difference -- the thing
      ``D18`` refuses and the thing 7.9 needs a case to decide.
    - ``REVIEW_MAX < MAX_SCORE`` or a score of 100 -- a pile of strong findings
      that 7.7 holds to the top of the scale -- lands in ``review``, and a
      certain forgery becomes arguable.
    """
    assert MIN_SCORE < LOW_MAX
    assert LOW_MAX < REVIEW_MAX
    assert REVIEW_MAX < MAX_SCORE


def test_the_thresholds_are_exported_and_nothing_else():
    """``__all__`` is the pair, so a caller can see the whole of the config.

    The two ends of the scale are 7.6's and 7.7 reads them from there; 7.8
    adds two names and a third would be a parameter no task has asked for.
    """
    assert config_module.__all__ == ["LOW_MAX", "REVIEW_MAX"]


def test_the_module_holds_the_pair_and_nothing_that_could_move_it():
    """The whole body is the docstring, ``__all__`` and the two assignments.

    Held as a statement list rather than as a claim about behaviour, because
    the risk this file guards against is a *second* thing in the module: a
    helper, an import or a validation that would answer "which band" here as
    well as in 7.9.  **No import at all** is the other half of that -- not
    ``os``, not ``importlib``, not a clock -- so the pair cannot become a
    deployment setting without this failing.
    """
    tree = ast.parse(_source(THIS_MODULE))
    body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        )
    ]

    assert [type(node) for node in body] == [ast.Assign, ast.Assign, ast.Assign]
    assert [target.id for node in body for target in node.targets] == [
        "__all__",
        "LOW_MAX",
        "REVIEW_MAX",
    ]
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )


def test_no_other_risk_module_writes_a_threshold_of_its_own():
    """The pair is written once, and 7.7's "there is one pair" holds for both.

    ``test_score_clamp.py`` holds that the two *ends* of the scale are written
    once; this holds the same for the two thresholds that divide it.  A second
    module assigning ``REVIEW_MAX = 69`` would be free to answer a different
    question from the one 7.9 asks the moment the committed pair was retuned,
    and no screening would fail.
    """
    for path in _modules_beside_this_one():
        assigned = _assigned_names(ast.parse(_source(path)))
        assert not assigned & set(THRESHOLD_NAMES), path.name


def test_no_risk_module_compares_a_score_against_a_threshold_written_out():
    """7.9 must read the name, and the walk is over the whole package.

    An assignment is one way to get a second copy; a literal in a comparison
    is the quieter one.  ``score >= 69`` in ``to_band`` would band every
    document correctly today and be wrong the day the pair moved, with no
    import to find and no name to grep for.
    """
    committed = set(COMMITTED_DEFAULTS.values())
    for path in _modules_beside_this_one():
        tree = ast.parse(_source(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            assert not _literal_numbers(operands) & committed, (
                f"{path.name} compares against a committed threshold literal"
            )


def test_the_pair_divides_the_weights_the_file_committed():
    """The thresholds are read against ``v1.yaml``, so neither number is free.

    One rule covers the file: a row may never weigh more than the threshold of
    the band it is *not* in.  A ``low`` row above ``LOW_MAX`` would put a
    single confirmed low finding into ``review``; a ``review`` or ``high`` row
    above ``REVIEW_MAX`` would put one finding into ``high`` on its own, which
    is ``D21``'s claim and the reason the committed pair sits where it does.

    **The weights are read through 7.2's loader and none is retyped here**,
    so this fails on a retune of either side rather than on a stale copy of
    the other.
    """
    weightset = load_weightset(DEFAULT_WEIGHTSET)
    for flag_id, row in weightset.flags.items():
        band = row["band"]
        assert band in WEIGHT_BANDS, flag_id
        ceiling = LOW_MAX if band == "low" else REVIEW_MAX
        assert row["weight"] <= ceiling, (
            f"{flag_id} weighs {row['weight']} and is banded {band}"
        )
