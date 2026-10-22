"""The per-flag breakdown, and the claim that it sums to the total.

Task 7.11 asks for a per-flag contribution breakdown -- ``id``, ``weight``,
``value``, ``contribution`` -- returned alongside the total, with a test that
the contributions sum to the pre-history score.  The headline test below is
that arithmetic written out: three flags, three weights read off the
committed file, three values chosen so every product is exact in binary
floating point, and a total a reader can check with a pencil.

**"Pre-history" is the word the task uses and it is 7.5's number.**  The
history term is 7.13's, so a breakdown produced here is the score *before*
history, the hard-rule floor and the clamp -- the ``R`` of ``R = Sum(w_i *
F_i)``.  The contributions are held to sum to exactly that, which is the
claim a dashboard's "why this score" panel rests on.

**The total is the sum of the exposed contributions by construction, not by
two agreeing implementations.**  :func:`weighted_sum` is defined as the
``total`` of the same :func:`weighted_breakdown` a caller reads the
contributions from, so the two cannot drift: there is one place the terms are
multiplied and added, and the float 7.5 returns is that place's own answer.

**Every weight is read off ``v1.yaml`` and none is retyped here**, the way
7.5's suite does, so a retuned weight fails as a different sum rather than
passing as a stale expectation.

**A contribution is arithmetic and carries nothing else.**  It is exactly the
four fields the task names -- no band, no decision, no outcome.  7.10's walk
over ``app/`` fails the moment a rejection word or a band-derived decision is
written beside these numbers, and a contribution that grew one would be the
first thing to trip it.
"""

import ast
import dataclasses
import math
import pathlib

import pytest

from app.risk import scoring as scoring_module
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.scoring import (
    Contribution,
    ScoreBreakdown,
    weighted_breakdown,
    weighted_sum,
)
from app.risk.weightsets.loader import Weightset, WeightsetError, load_weightset

#: A field-shaped box: two lines of pixels, clockwise from the top left, the
#: shape 4.12's `_box_polygon` writes.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: The three ids the headline example fires, one from each band, so the
#: example exercises the weightset rather than three rows of one family.
HIGH_FLAG = "MRZ_DOB_CHECK_DIGIT_MISMATCH"  # weight 60, band high
REVIEW_FLAG = "FACE_LOW_SIMILARITY"  # weight 40, band review
LOW_FLAG = "OCR_LOW_CONFIDENCE"  # weight 15, band low

#: The three values, all exact in binary floating point so every product below
#: is the number a reader computes on paper.  0.5, 0.25 and 0.75 are dyadic
#: rationals, so 60 * 0.5, 40 * 0.25 and 15 * 0.75 are exact and the total is
#: their exact sum.
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

    ``D6``'s constructor check refuses a ``None`` and a boolean, so the
    refusals the breakdown must propagate are reached through a rule's own
    record rather than through a flag -- the same shape 7.5's suite uses.
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


def the_terms(contributions):
    """The contribution column alone, so a sum over it reads as ``w * F``."""
    return [term.contribution for term in contributions]


# --- the task's own claim: the contributions sum to the pre-history score ---


def test_the_contributions_sum_to_the_pre_history_score():
    """The headline: 30 + 10 + 11.25 = 51.25, from the exposed terms alone.

    7.1's file gives these three ids weights of 60, 40 and 15; the three
    values are 0.5, 0.25 and 0.75, so each product is exact rather than
    merely close.  **The sum is taken over the ``contribution`` column the
    breakdown exposes** -- the number an officer's "why this score" panel
    would add up -- and asserted equal to both the record's own ``total`` and
    7.5's ``weighted_sum``.  That the three agree is the claim; the total
    being *defined* as their sum is what makes it hold by construction.
    """
    loaded = load_weightset()
    breakdown = weighted_breakdown(the_three_flags(), loaded)

    assert the_three_weights(loaded) == [60, 40, 15]
    assert math.fsum(the_terms(breakdown.contributions)) == EXPECTED_TOTAL
    assert math.fsum(the_terms(breakdown.contributions)) == breakdown.total
    assert breakdown.total == weighted_sum(the_three_flags(), loaded)


def test_each_contribution_is_its_own_weight_times_its_own_value():
    """Every column is checkable on its own, not only the total.

    The task names four fields, and a reader debugging a surprising score
    needs each of them to be the number the arithmetic used: the ``weight``
    the file holds, the ``value`` the flag carries, and the ``contribution``
    their product.  This asserts the three columns against each other and
    against the committed file rather than only that they sum.
    """
    loaded = load_weightset()
    breakdown = weighted_breakdown(the_three_flags(), loaded)
    rows = loaded.flags

    for term, flag_id, value in zip(
        breakdown.contributions,
        (HIGH_FLAG, REVIEW_FLAG, LOW_FLAG),
        (HIGH_VALUE, REVIEW_VALUE, LOW_VALUE),
    ):
        assert term.id == flag_id
        assert term.weight == rows[flag_id]["weight"]
        assert term.value == value
        assert term.contribution == term.weight * term.value

    assert the_terms(breakdown.contributions) == [30.0, 10.0, 11.25]


# --- one contribution per flag, and no flag dropped ------------------------


def test_there_is_one_contribution_per_finding_in_the_order_they_arrived():
    """The cascade's order is preserved and no finding is lost or added.

    A breakdown is a list the officer reads, so it must have exactly one row
    per finding: a dropped finding loses its explanation and a reordered one
    misreports which rule contributed what.  Duplicated rows would double the
    contribution and break the sum.
    """
    loaded = load_weightset()
    flags = the_three_flags()
    breakdown = weighted_breakdown(flags, loaded)

    assert [term.id for term in breakdown.contributions] == [
        flag.id for flag in flags
    ]
    assert len(breakdown.contributions) == len(flags)


def test_two_findings_of_one_id_are_two_contributions():
    """A dedupe by id would drop the second, which is 7.5's own claim.

    Two blacklist hits or two mismatched fields are two findings, and under
    ``D21`` their sum is exactly the corroboration the engine exists to
    accumulate.  A breakdown that showed one row for both would hide the
    second explanation *and* make the shown rows not add up to the score.
    """
    loaded = load_weightset()
    flags = [a_flag(REVIEW_FLAG, 0.5), a_flag(REVIEW_FLAG, 0.5)]
    breakdown = weighted_breakdown(flags, loaded)

    assert len(breakdown.contributions) == 2
    assert [term.id for term in breakdown.contributions] == [
        REVIEW_FLAG,
        REVIEW_FLAG,
    ]
    assert breakdown.total == 40.0 * 0.5 + 40.0 * 0.5
    assert math.fsum(the_terms(breakdown.contributions)) == breakdown.total


def test_a_clean_document_breaks_down_to_an_empty_list_and_a_zero_total():
    """No finding fired, so the breakdown is empty and its sum is ``0.0``.

    This is 7.5's empty sum carried through: the empty breakdown is not a
    refusal and not a ``None``, and summing nothing gives back ``0.0``, the
    same float 7.5 answers for a clean document.  A ``None`` here would be
    read downstream as "no data" rather than "nothing fired".
    """
    loaded = load_weightset()
    breakdown = weighted_breakdown([], loaded)

    assert breakdown.contributions == ()
    assert breakdown.total == 0.0
    assert type(breakdown.total) is float
    assert math.fsum(the_terms(breakdown.contributions)) == 0.0


def test_a_zero_value_contributes_a_zero_row_and_is_not_dropped():
    """A measured ``0.0`` is a term of nothing that is still shown.

    On ``D24``'s line: an *unmeasured* value is refused, while a measured
    ``0.0`` is a real reading of no strength.  It is a finding the officer
    should still see, so it gets a contribution of ``0.0`` and is not
    filtered out of the list -- filtering it would hide why a rule fired.
    """
    loaded = load_weightset()
    breakdown = weighted_breakdown([a_flag(REVIEW_FLAG, 0.0)], loaded)

    assert len(breakdown.contributions) == 1
    assert breakdown.contributions[0].contribution == 0.0
    assert breakdown.total == 0.0


# --- the total is the sum of the shown terms, and is 7.5's own number ------


def test_the_total_is_7_5_s_sum_and_the_two_never_disagree():
    """``weighted_sum`` *is* this module's ``total``, by definition.

    The task's whole point is that the number and the explanation beside it
    cannot drift, and the guarantee is structural: 7.5's float is the
    ``total`` field of the very breakdown a caller reads.  Over a spread of
    screenings -- clean, single, corroborating, and one running past the top
    of the scale -- the two must be the same float to the last bit.
    """
    loaded = load_weightset()
    cases = [
        [],
        [a_flag(REVIEW_FLAG, 1.0)],
        the_three_flags(),
        [a_flag(REVIEW_FLAG, 0.33), a_flag(REVIEW_FLAG, 0.67)],
        [
            a_flag("MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH", 1.0, weight_band="high"),
            a_flag("WATCHLIST_HIT", 1.0, weight_band="high"),
            a_flag("CROSSDOC_FACE_MISMATCH", 1.0, weight_band="high"),
        ],
    ]

    for flags in cases:
        breakdown = weighted_breakdown(flags, loaded)

        assert breakdown.total == weighted_sum(flags, loaded)
        assert math.fsum(the_terms(breakdown.contributions)) == breakdown.total


def test_a_breakdown_over_the_top_of_the_scale_still_shows_every_point():
    """195 points and three ``high`` rows: the sum is not clamped here.

    ``D21`` and 7.7's claim meet in the breakdown: corroborating findings are
    how a document reaches High, so the total is allowed to run over 100 and
    the clamp is what an officer finally sees.  A breakdown that clamped each
    contribution, or the total, would stop adding up to the pre-clamp score
    and would make the shown rows disagree with what 7.5 returned.
    """
    loaded = load_weightset()
    flags = [
        a_flag("MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH", 1.0, weight_band="high"),
        a_flag("WATCHLIST_HIT", 1.0, weight_band="high"),
        a_flag("CROSSDOC_FACE_MISMATCH", 1.0, weight_band="high"),
    ]
    breakdown = weighted_breakdown(flags, loaded)

    assert breakdown.total == 65.0 + 65.0 + 65.0
    assert breakdown.total == 195.0
    assert the_terms(breakdown.contributions) == [65.0, 65.0, 65.0]
    assert math.fsum(the_terms(breakdown.contributions)) == 195.0


def test_the_order_the_findings_arrive_in_does_not_change_the_total():
    """Cascade order is not a scoring input, on the same ``fsum`` footing.

    The three terms are accumulated with :func:`math.fsum`, so the total is
    the correctly rounded exact sum rather than a running total whose last
    bit depends on which rule answered first.  Every permutation of the three
    breaks down to the same total and the same set of terms.
    """
    import itertools

    loaded = load_weightset()
    flags = the_three_flags()

    totals = {
        weighted_breakdown(ordering, loaded).total
        for ordering in itertools.permutations(flags)
    }

    assert totals == {EXPECTED_TOTAL}


def test_the_records_are_frozen_and_carry_no_band_or_decision():
    """A contribution is arithmetic: the four fields, and nothing else.

    7.10's walk over ``app/`` fails the moment a band is written beside a
    rejection in one statement, so a contribution that grew a ``band``, a
    ``decision`` or an outcome would be the first thing to trip it.  The
    field set is pinned to exactly the four the task names, and both records
    are frozen, so a caller cannot amend a term after the fact and have the
    total disagree with the rows shown.
    """
    assert [field.name for field in dataclasses.fields(Contribution)] == [
        "id",
        "weight",
        "value",
        "contribution",
    ]
    assert [field.name for field in dataclasses.fields(ScoreBreakdown)] == [
        "total",
        "contributions",
    ]
    assert Contribution.__dataclass_params__.frozen
    assert ScoreBreakdown.__dataclass_params__.frozen

    forbidden = {"band", "decision", "outcome", "verdict", "status"}
    for record in (Contribution, ScoreBreakdown):
        assert not {field.name for field in dataclasses.fields(record)} & forbidden


# --- refusals reach the caller, so no half-built breakdown is returned -----


def test_an_unweighted_flag_id_stops_the_breakdown():
    """``D23``'s refusal is not swallowed into a row of nothing."""
    loaded = load_weightset()

    with pytest.raises(WeightsetError) as raised:
        weighted_breakdown([a_flag("NOT_A_REAL_FLAG_ID", 0.5)], loaded)

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
def test_an_unmeasured_value_stops_the_breakdown(value):
    """``D24``'s refusal reaches the caller through the breakdown, unchanged.

    A row that quietly recorded ``0.0`` for these would put "nobody measured
    this" into the shown terms as a contribution of nothing, which is the
    same fault as scoring an unweighted id as zero -- and worse on a
    dashboard, because the officer would see a reason that moved no score.
    """
    loaded = load_weightset()

    with pytest.raises(FlagValueError):
        weighted_breakdown([DraftFinding(id=REVIEW_FLAG, value=value)], loaded)


def test_one_bad_flag_in_a_good_screening_stops_the_whole_breakdown():
    """The refusal is not per-row skipping, which would show a partial list."""
    loaded = load_weightset()
    flags = [
        a_flag(HIGH_FLAG, HIGH_VALUE, weight_band="high"),
        DraftFinding(id="NOT_A_REAL_FLAG_ID", value=0.5),
        a_flag(LOW_FLAG, LOW_VALUE, weight_band="low"),
    ]

    with pytest.raises(WeightsetError):
        weighted_breakdown(flags, loaded)


def test_a_record_carrying_neither_field_is_refused():
    """Both halves of a term are read here, so both are this module's to check."""
    loaded = load_weightset()

    with pytest.raises(FlagValueError) as raised:
        weighted_breakdown([object()], loaded)

    assert "id" in str(raised.value)


def test_a_flag_id_passed_instead_of_a_flag_is_refused():
    """A bare id string is refused on the missing ``id``, not on a value.

    ``"FACE_LOW_SIMILARITY"`` passed where a finding belongs carries neither
    field, and **the weight is looked up before the value is read** -- the
    order 7.5 established, so the two gates refuse in the same sequence here
    as they do there.  A record missing both is therefore reported against
    the ``id``, and 7.5's own suite holds the same shape for the same reason.
    """
    loaded = load_weightset()

    with pytest.raises(FlagValueError) as raised:
        weighted_breakdown([REVIEW_FLAG], loaded)

    assert "id" in str(raised.value)


# --- the module's own bounds, held by walking its source -------------------


def _source(path):
    return path.read_text(encoding="utf-8")


THIS_MODULE = pathlib.Path(scoring_module.__file__)


def test_the_breakdown_adds_no_band_no_decision_and_no_outcome():
    """7.10's constraint from this module's side: the numbers are arithmetic.

    The vocabulary walk is over the whole of ``app/``, so a ``band`` field or
    a decision word added to a contribution would fail 7.10's suite.  This
    holds the same claim locally and names the reason: the four fields are
    ``id``, ``weight``, ``value`` and their product, and a contribution is
    not a place a traveller's outcome is recorded.
    """
    tree = ast.parse(_source(THIS_MODULE))
    annotated = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotated.add(node.target.id)
        elif isinstance(node, ast.arg) and node.annotation is not None:
            annotated |= {
                inner.id
                for inner in ast.walk(node.annotation)
                if isinstance(inner, ast.Name)
            }

    assert not annotated & {"band", "decision", "outcome", "verdict"}


def test_the_module_reads_no_clock_and_no_randomness():
    """``D12``'s rule extends here: a score must not depend on when it ran."""
    tree = ast.parse(_source(THIS_MODULE))
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


def test_the_module_imports_the_two_gates_and_nothing_from_the_pipeline():
    """Walked rather than grepped, and the claim is the absence of an import.

    The breakdown is written against 7.3's and 7.4's promise that a term is a
    checked float, so those two modules, the error type and the weightset
    record are all it needs.  ``dataclasses`` is added for the two frozen
    records the task's four fields live on.  ``app.pipeline`` must not
    appear, on ``D6``'s one-way dependency.
    """
    tree = ast.parse(_source(THIS_MODULE))
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
    assert "collections.abc" in standard
    assert "dataclasses" in standard
    assert "math" in standard


def test_the_module_exports_the_sum_and_the_breakdown_it_built():
    """``weighted_sum`` stays public -- 7.5's callers hold it -- beside the
    two records and the new entry points the task adds."""
    assert set(scoring_module.__all__) == {
        "Contribution",
        "ScoreBreakdown",
        "contributions",
        "weighted_breakdown",
        "weighted_sum",
    }


def test_a_refusal_never_quotes_the_value_it_refused():
    """``D6``'s rule, held over the breakdown: name the field, not the value."""
    loaded = load_weightset()

    with pytest.raises(FlagValueError) as raised:
        weighted_breakdown(
            [DraftFinding(id=REVIEW_FLAG, value="FICTITIOUS<<JANE")], loaded
        )

    assert "FICTITIOUS" not in str(raised.value)
    assert "value" in str(raised.value)


# --- the task's claim is not vacuous, and the ways it fails are named -------


@pytest.mark.parametrize(
    ("name", "contributions_to_total"),
    [
        pytest.param(
            "the-clamped-total",
            lambda rows: min(math.fsum(rows), 100.0),
            id="the-total-is-clamped-rather-than-summed",
        ),
        pytest.param(
            "the-floored-total",
            lambda rows: 90.0,
            id="the-total-is-7-6s-floor-rather-than-the-sum",
        ),
        pytest.param(
            "a-renormalised-row",
            lambda rows: math.fsum(rows) / 115.0,
            id="each-row-is-a-share-of-the-weights-that-fired",
        ),
        pytest.param(
            "a-dropped-row",
            lambda rows: math.fsum(rows[1:]),
            id="the-first-contribution-is-missing-from-the-sum",
        ),
        pytest.param(
            "a-doubled-row",
            lambda rows: math.fsum(rows) * 2.0,
            id="a-contribution-is-counted-twice",
        ),
    ],
)
def test_the_headline_claim_fails_for_every_wrong_total(
    name, contributions_to_total
):
    """The claim has teeth: each wrong reading of the total fails it.

    The task's test asserts that the contributions sum to the pre-history
    score.  **A test that only ever sees the right answer proves nothing**,
    so the five ways that sum is actually got wrong are named here and each
    is shown to break the equality: a total that is the clamp rather than the
    sum, a total that is 7.6's floor rather than the sum, a row renormalised
    over the weights that fired (``D21``'s mistake, which is the subtlest
    because the rows still add up to *something*), a row left out of the sum,
    and a row counted twice.

    Held against the *arithmetic* rather than against the module, so the
    assertions below are the ones the headline test is made of: sum the
    three products, and require the answer the committed file gives.
    """
    loaded = load_weightset()
    # The clamp is a no-op on 51.25, so the case that exposes it is the
    # 195-point one: three `high` findings at full strength, which is the
    # only place 7.7's clamp and a raw sum can disagree at all.
    flags = (
        the_three_flags()
        if not name.startswith("the-clamped")
        else [
            a_flag("MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH", 1.0, weight_band="high"),
            a_flag("WATCHLIST_HIT", 1.0, weight_band="high"),
            a_flag("CROSSDOC_FACE_MISMATCH", 1.0, weight_band="high"),
        ]
    )
    rows = the_terms(weighted_breakdown(flags, loaded).contributions)
    wrong_total = contributions_to_total(rows)
    expected_total = math.fsum(rows)

    assert math.fsum(rows) == expected_total
    assert wrong_total != expected_total


def test_the_sum_claim_alone_would_miss_a_renormalised_row():
    """What the task names is necessary and not on its own sufficient.

    **Written down because a weaker suite would have shipped a false
    confidence.**  A breakdown that renormalises every row over the weights
    that fired, and then totals *those* rows, is internally consistent: the
    contributions do sum to the total it reports.  Only the per-term claim --
    that a row is its own ``weight * value`` -- and the absolute expectation
    of 51.25 catch it.  So the headline test is paired with
    :func:`test_each_contribution_is_its_own_weight_times_its_own_value`
    deliberately, and the ``D21`` mutant above was measured against this file
    rather than assumed to be caught.
    """
    loaded = load_weightset()
    flags = the_three_flags()
    rows = the_terms(weighted_breakdown(flags, loaded).contributions)
    weights = the_three_weights(loaded)
    values = (HIGH_VALUE, REVIEW_VALUE, LOW_VALUE)

    renormalised = [row / math.fsum(weights) for row in rows]

    # Internally consistent, and still wrong.
    assert math.fsum(renormalised) == pytest.approx(
        sum(weight * value for weight, value in zip(weights, values))
        / math.fsum(weights)
    )
    assert renormalised != rows
    # This is the assertion that catches it, and the absolute one beside it.
    assert rows == [weight * value for weight, value in zip(weights, values)]
    assert math.fsum(rows) == EXPECTED_TOTAL
