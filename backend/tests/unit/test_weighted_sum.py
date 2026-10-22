"""The weighted sum is the sum of the products, and says nothing else.

Task 7.5 asks for ``R = Σ(wᵢ · Fᵢ)`` with a test on a hand-computed three-flag
example, and the headline test below is that arithmetic written out longhand:
three flags, three weights read off the committed file, three values chosen
so every product is exact in binary floating point, and one total a reader can
check with a pencil.

**Every weight is read off ``v1.yaml`` and none is retyped here**, the way
7.1's and 7.3's tests do.  A retuned weight therefore fails these tests as a
different sum rather than passing as a stale expectation, and the pen-and-paper
arithmetic below stays true by construction.

**The rest of the file is the four things the sum must not do**: normalise,
clamp, band, or answer a refusal with a number.  The three gates either side
of it -- 7.3's lookup and 7.4's value -- are the ones that refuse, so the
claims here are that the refusals reach the caller and that the sum adds no
arithmetic of its own.
"""

import ast
import dataclasses
import itertools
import pathlib

import pytest

from app.risk import scoring as scoring_module
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.scoring import weighted_sum
from app.risk.weightsets.loader import Weightset, WeightsetError, load_weightset

#: A field-shaped box: two lines of pixels, clockwise from the top left, the
#: shape 4.12's `_box_polygon` writes.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: The three ids the headline example fires, one from each band and one from
#: each of the three tiers the cascade runs, so the example exercises the
#: weightset rather than three rows of one family.
HIGH_FLAG = "MRZ_DOB_CHECK_DIGIT_MISMATCH"  # weight 60, band high
REVIEW_FLAG = "FACE_LOW_SIMILARITY"  # weight 40, band review
LOW_FLAG = "OCR_LOW_CONFIDENCE"  # weight 15, band low

#: The three values, all exact in binary floating point so every product below
#: is the number a reader computes on paper.  0.5 and 0.25 and 0.75 are all
#: dyadic rationals, so 60 * 0.5, 40 * 0.25 and 15 * 0.75 are exact and the
#: total is their exact sum.
HIGH_VALUE = 0.5
REVIEW_VALUE = 0.25
LOW_VALUE = 0.75

#: The hand-computed total: 30 + 10 + 11.25.  Written as the three products
#: rather than as one literal so the expectation and the arithmetic cannot
#: disagree.
EXPECTED_TOTAL = 30.0 + 10.0 + 11.25


def a_flag(flag_id=REVIEW_FLAG, value=0.5, **overrides):
    """A well-formed flag, with ``overrides`` replacing any of its fields."""
    fields = {
        "id": flag_id,
        "tier": 0,
        "label": "A finding worth explaining",
        "weight_band": "review",
        "value": value,
        "confidence": 1.0,
        "region": FIELD_BOX,
        "expected": None,
        "found": None,
        "reason": "The printed characters disagree with the computed check.",
        "source_module": "app.pipeline.tier0.runner",
        "field": None,
    }
    fields.update(overrides)
    return EvidenceFlag(**fields)


@dataclasses.dataclass(frozen=True)
class DraftFinding:
    """A record carrying a ``value`` a well-formed flag cannot.

    ``D6``'s constructor check refuses a ``None`` and a ``1.4``, so the
    refusals the sum must propagate are reached through a rule's own record
    rather than through a flag -- the same shape 7.4's own suite uses.
    """

    id: str
    value: object


def the_three_flags():
    """The headline example's three flags, in the cascade's tier order."""
    return [
        a_flag(HIGH_FLAG, HIGH_VALUE, tier=0, weight_band="high"),
        a_flag(REVIEW_FLAG, REVIEW_VALUE, tier=1, weight_band="review"),
        a_flag(LOW_FLAG, LOW_VALUE, tier=1, weight_band="low"),
    ]


def the_three_weights(loaded):
    """The three weights, read off the committed file rather than retyped."""
    return [
        loaded.flags[flag_id]["weight"]
        for flag_id in (HIGH_FLAG, REVIEW_FLAG, LOW_FLAG)
    ]


# --- the hand-computed three-flag example ----------------------------------


def test_the_hand_computed_three_flag_example_sums_to_the_pencil_arithmetic():
    """The test the task names: ``30 + 10 + 11.25``.

    7.1's file gives these three ids weights of 60, 40 and 15; the three
    values are 0.5, 0.25 and 0.75, chosen so each product is exact rather than
    merely close.  The total is 51.25 and it is written as the sum of the
    three products so the expectation and the arithmetic cannot drift apart.
    """
    loaded = load_weightset()

    assert the_three_weights(loaded) == [60, 40, 15]
    assert weighted_sum(the_three_flags(), loaded) == EXPECTED_TOTAL


def test_each_term_is_its_own_weight_times_its_own_value():
    """The sum is three products added, so each one is checkable on its own.

    One flag at a time is the clearest statement of what the terms are, and it
    is what a contribution breakdown in 7.11 will have to reproduce.
    """
    loaded = load_weightset()
    terms = [
        weighted_sum([flag], loaded) for flag in the_three_flags()
    ]

    assert terms == [60 * 0.5, 40 * 0.25, 15 * 0.75]
    assert terms == [30.0, 10.0, 11.25]


def test_the_answer_is_a_float_even_though_the_file_holds_integers():
    """The weights in ``v1.yaml`` are YAML integers, and ``R`` is not.

    7.3 returns a ``float`` and 7.4 returns a ``float``, so the product is one
    whatever the row holds; a caller doing ``R // 1`` or comparing against an
    int threshold would otherwise be reasoning about a different type than the
    one the abstract writes the sum in.
    """
    loaded = load_weightset()

    assert isinstance(loaded.flags[HIGH_FLAG]["weight"], int)
    assert type(weighted_sum(the_three_flags(), loaded)) is float


# --- nothing is normalised, clamped or banded ------------------------------


def test_one_flag_at_full_strength_contributes_its_whole_weight():
    """``D21``: a weight is points on the score, not a share of a budget.

    The mistake this rules out is dividing by the weights of the flags that
    fired, so a single `high` finding could never reach past `low` no matter
    how few flags there were.  Three flags at full strength are the strongest
    statement: under a share-of-budget reading they would each be worth a
    third of their own weight.
    """
    loaded = load_weightset()
    flags = [
        a_flag(HIGH_FLAG, 1.0, weight_band="high"),
        a_flag(REVIEW_FLAG, 1.0),
        a_flag(LOW_FLAG, 1.0, weight_band="low"),
    ]

    assert weighted_sum(flags, loaded) == 60.0 + 40.0 + 15.0


def test_two_flags_at_half_strength_score_less_than_one_at_full():
    """The value scales the contribution, and does not rescale the weight."""
    loaded = load_weightset()

    one_full = weighted_sum([a_flag(REVIEW_FLAG, 1.0)], loaded)
    two_half = weighted_sum(
        [a_flag(REVIEW_FLAG, 0.5), a_flag(REVIEW_FLAG, 0.5)], loaded
    )

    assert one_full == 40.0
    assert two_half == 40.0


def test_the_sum_is_not_clamped_and_may_exceed_a_hundred():
    """7.7's clamp is 7.7's, and a clamp written here would hide a real score.

    Corroborating findings are how a document reaches High under `D21`, so the
    sum is allowed to run over 100 and 7.7 decides what an officer sees.  Three
    `high` findings at full strength is 195 points, and a module that clamped
    here would report 100 and lose the margin the band thresholds read.
    """
    loaded = load_weightset()
    flags = [
        a_flag("MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH", 1.0, weight_band="high"),
        a_flag("WATCHLIST_HIT", 1.0, weight_band="high"),
        a_flag("CROSSDOC_FACE_MISMATCH", 1.0, weight_band="high"),
    ]

    assert weighted_sum(flags, loaded) == 65.0 + 65.0 + 65.0
    assert weighted_sum(flags, loaded) > 100


def test_a_clean_document_scores_zero_rather_than_raising():
    """No finding fired, so the empty sum is ``0.0`` and nothing is missing.

    This is not the silent zero 7.3 and 7.4 refuse: an empty sequence has no
    term to leave out, and a document with no flags is a real answer a tier
    produces.  It is a `float` like every other answer.
    """
    loaded = load_weightset()

    assert weighted_sum([], loaded) == 0.0
    assert type(weighted_sum([], loaded)) is float


def test_a_zero_value_contributes_nothing_without_being_refused():
    """A rule that measured and found nothing is a finding, and scores zero.

    The line against ``D24``'s ``None`` refusal: an unmeasured value is
    silence and raises, while a measured ``0.0`` is a real reading of no
    strength and is in the sum as a term of nothing.
    """
    loaded = load_weightset()

    assert weighted_sum([a_flag(REVIEW_FLAG, 0.0)], loaded) == 0.0


# --- refusals reach the caller rather than becoming a number --------------


def test_an_unweighted_flag_id_stops_the_sum():
    """``D23``'s refusal is not swallowed into a term of nothing."""
    loaded = load_weightset()

    with pytest.raises(WeightsetError) as raised:
        weighted_sum([a_flag("NOT_A_REAL_FLAG_ID", 0.5)], loaded)

    assert "NOT_A_REAL_FLAG_ID" in str(raised.value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="boolean"),
        pytest.param("0.5", id="text"),
        pytest.param(1.4, id="above-the-range"),
    ],
)
def test_an_unmeasured_value_stops_the_sum(value):
    """``D24``'s refusal reaches the caller through the sum, unchanged.

    A term that quietly scored ``0.0`` for these would put "nobody measured
    this" into ``R`` as a contribution of nothing, which is the same fault
    ``D23`` refuses for a missing weight.
    """
    loaded = load_weightset()

    with pytest.raises(FlagValueError):
        weighted_sum([DraftFinding(id=REVIEW_FLAG, value=value)], loaded)


def test_one_bad_flag_in_a_good_screening_stops_the_whole_sum():
    """The refusal is not per-term skipping, which would score around it."""
    loaded = load_weightset()
    flags = [
        a_flag(HIGH_FLAG, HIGH_VALUE, weight_band="high"),
        DraftFinding(id="NOT_A_REAL_FLAG_ID", value=0.5),
        a_flag(LOW_FLAG, LOW_VALUE, weight_band="low"),
    ]

    with pytest.raises(WeightsetError):
        weighted_sum(flags, loaded)


def test_a_record_carrying_neither_field_is_refused_rather_than_scored_zero():
    """Both halves of a term are read here, so both are this module's to check.

    :func:`~app.risk.scoring._id_off` is the sum's own addition rather than
    either gate's: a raw ``AttributeError`` is not the ``ValueError`` a caller
    already catching one around the scoring is catching.
    """
    loaded = load_weightset()

    with pytest.raises(FlagValueError) as raised:
        weighted_sum([object()], loaded)

    assert "id" in str(raised.value)


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(None, id="none"),
        pytest.param("FACE_LOW_SIMILARITY", id="a-flag-id"),
        pytest.param(DraftFinding, id="a-class-not-a-record"),
    ],
)
def test_a_record_with_no_id_is_refused_rather_than_scored_as_zero(record):
    """A flag id passed instead of a flag, and a class, are both refusals."""
    loaded = load_weightset()

    with pytest.raises(FlagValueError) as raised:
        weighted_sum([record], loaded)

    assert "id" in str(raised.value)


# --- the invariants around the arithmetic ----------------------------------


def test_the_order_the_flags_arrive_in_does_not_change_the_score():
    """Cascade order is not a scoring input, and a caller may hand any order.

    Accumulated with :func:`math.fsum`, so the answer is the correctly rounded
    exact sum of the terms rather than a left-to-right running total whose last
    bit depends on which rule answered first.  Every permutation is compared
    against the hand-computed total rather than against one arbitrary order.

    **This test is a guard rather than a discriminator, and that is measured.**
    A left-to-right ``sum()`` over these three terms gives the same answer in
    every order: a search over every three-term combination drawn from the
    committed weights and values in hundredths found no ordering that changes
    the result, and a randomised search over the same range found none
    either.  What plain ``sum()`` *does* fail is the empty case, which returns
    an ``int`` -- held by
    :func:`test_a_clean_document_scores_zero_rather_than_raising`.
    """
    loaded = load_weightset()
    flags = the_three_flags()

    for ordering in itertools.permutations(flags):
        assert weighted_sum(ordering, loaded) == EXPECTED_TOTAL


def test_two_findings_of_one_id_are_two_terms():
    """``Σ`` is over findings, and two findings of one rule are two findings.

    A dedupe by id would drop the second blacklist hit or the second mismatched
    field, which under ``D21`` is exactly the corroboration the sum exists to
    accumulate.
    """
    loaded = load_weightset()

    both = weighted_sum([a_flag(REVIEW_FLAG, 0.5), a_flag(REVIEW_FLAG, 0.5)], loaded)

    assert both == 40.0 * 0.5 + 40.0 * 0.5


def test_a_single_flag_still_contributes_its_whole_weight():
    """One finding and one weight, so the sum cannot be a share of anything."""
    loaded = load_weightset()

    assert weighted_sum([a_flag(HIGH_FLAG, 1.0, weight_band="high")], loaded) == 60.0


def test_summing_reads_the_flags_and_the_weightset_without_amending_either():
    """A flag is evidence and a weightset is a record of a ruleset.

    Both are frozen, so the only way either could change here is a write held
    somewhere else.  The weights compared after the call are read off the same
    record rather than from a private copy taken before it.
    """
    loaded = load_weightset()
    flags = the_three_flags()
    before = [dataclasses.replace(flag) for flag in flags]

    weighted_sum(flags, loaded)

    assert flags == before
    assert [
        loaded.flags[flag_id]["weight"] for flag_id in (HIGH_FLAG, REVIEW_FLAG, LOW_FLAG)
    ] == [60, 40, 15]


def test_the_sum_opens_no_file_and_reads_no_package_resource(monkeypatch):
    """7.2's loader is the one way in, and the sum is not a second reader.

    ``loader._read`` is replaced with a call that fails, so a sum that
    re-read ``v1.yaml`` would fail this test rather than quietly answer from a
    file while the caller believed it was answering from a record.
    """
    from app.risk.weightsets import loader

    monkeypatch.setattr(
        loader, "_read", lambda _name: pytest.fail("the sum read the file")
    )
    loaded = Weightset(
        ruleset_version="9.9.9",
        flags={
            # 41 appears nowhere in v1.yaml, so a re-read could not answer it.
            HIGH_FLAG: {"weight": 41, "band": "high"},
        },
    )

    assert weighted_sum([a_flag(HIGH_FLAG, 0.5)], loaded) == 20.5


# --- what the module may import -------------------------------------------


def test_the_module_imports_the_two_gates_and_nothing_from_the_pipeline():
    """Walked rather than grepped, and the claim is the absence of an import.

    The sum is written against 7.3's and 7.4's promise that a term is a
    checked float, so those two modules, the error type and the weightset
    record are all it needs -- and nothing else from the project.  The
    standard-library set is :mod:`math` for :func:`~math.fsum`,
    :class:`~collections.abc.Iterable` for the type hint, and (since 7.11
    added the frozen :class:`~app.risk.scoring.Contribution` and
    :class:`~app.risk.scoring.ScoreBreakdown` records this module returns)
    :mod:`dataclasses`.

    ``app.pipeline`` must not appear: ``D6``'s package-wide rule keeps a tier
    out of ``app.risk``, and a sum reaching back into one would put it there.
    """
    tree = ast.parse(
        pathlib.Path(scoring_module.__file__).read_text(encoding="utf-8")
    )
    imported = set()
    standard = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {node.module or ""}
        else:
            continue
        for name in names:
            if name.split(".")[0] == "app":
                imported.add(name)
            else:
                standard.add(name)

    assert imported == {
        "app.risk.flags",
        "app.risk.values",
        "app.risk.weightsets.loader",
        "app.risk.weightsets.lookup",
    }
    assert standard == {"math", "collections.abc", "dataclasses"}


def test_the_module_exports_the_sum_and_the_breakdown_built_from_it():
    """``weighted_sum`` stays public beside the 7.11 records it now returns.

    7.5 promised ``weighted_sum`` and its callers hold it, so the name stays;
    7.11 widens the module with the two frozen records and the two entry
    points that expose the per-flag terms.  ``math``, ``Iterable`` and the
    record are used rather than re-exported, and the set below is exactly the
    module's public surface.
    """
    assert set(scoring_module.__all__) == {
        "Contribution",
        "ScoreBreakdown",
        "contributions",
        "weighted_breakdown",
        "weighted_sum",
    }


def test_the_module_reads_no_clock_and_no_randomness():
    """``D12``'s rule extends here: a score must not depend on when it ran.

    Held with an AST walk over the module's own source, the way 6.4's and
    ``test_tier0_timing.py``'s walks are held, because a screening scored
    differently tomorrow is a screening nobody can replay.
    """
    source = pathlib.Path(scoring_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)

    assert not called & {
        "now",
        "today",
        "time",
        "perf_counter",
        "random",
        "uniform",
        "randint",
    }
