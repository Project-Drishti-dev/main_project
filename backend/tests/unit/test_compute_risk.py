"""7.15 -- the five questions asked in one order, and worked example B.

7.5 to 7.7 and 7.9 to 7.14 each answer one question in its own module, and
none of them was wired to another: a band was a designed reading no screening
could reach.  :func:`~app.risk.engine.compute_risk` is the composition the
abstract describes -- "The risk engine combines all flags into a score R and a
band (Low Risk, Review or High Risk)" -- and this file is both its suite and
the second of Gate 7's two worked examples.

**Worked example B is the headline, in the abstract's own order.**  Section 3:
the checksums are valid, the dates are plausible and there is no watchlist
hit, so Tier 0 is clean; at Tier 1 the OCR matches the MRZ and the layout is
within tolerance, "but the face similarity to the live capture is 0.41
against a match threshold of 0.55", and "R1 falls in the ambiguous band and
the case is routed to Tier 2"; there the tamper heat-map concentrates on the
photo region and the morph score is high, so "the total R exceeds the high
threshold, and the officer sees the photo region highlighted with three stated
reasons".

**What the engine is and is not asked about the example.**  The engine
answers the two scores -- ``R1`` is the same call over the Tier 1 findings
alone, and the total is the same call over all three -- and it is 7.9's
middle band that is the abstract's "ambiguous band", read off
:data:`~app.risk.config.LOW_MAX` and :data:`~app.risk.config.REVIEW_MAX`
rather than written out.  **The routing decision is not this task's**: which
tiers ran is a flag's own ``tier`` and Part 13's escalation rule, and the
three reasons and the highlight over the photo region are a flag's ``id`` and
``region`` as 23.5 renders them.  What 7.15 owns is that one call turns those
findings into a number and a band.

**Every number is read, none retyped.**  Each weight comes from the committed
weightset through 7.3's lookup, both band thresholds from
:mod:`app.risk.config`, the floor from :mod:`app.risk.hard_rules` and the
history bound from :mod:`app.risk.history`, so a retune of the ruleset moves
this file's claims with it.  **6.5's hard-fail table is read from the runner
from the other side of the package**, as 7.1's and 7.6's suites already do,
because :mod:`app.risk` may not import :mod:`app.pipeline` to find it.

**The abstract says its similarity and threshold values are illustrative**,
and so are the weights they are scored against: nothing here is a measurement
and the bands below are a designed reading on uncalibrated thresholds.  What
is not illustrative is the composition -- the order, the refusals and the
arithmetic the record reports.
"""

import ast
import dataclasses
import math
import pathlib
from datetime import date, datetime, timedelta

import pytest

from app.pipeline.tier0 import runner
from app.risk import engine, flag_ids
from app.risk.bands import to_band
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.engine import RiskResult, ScreeningHistory, compute_risk
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.hard_rules import DEFAULT_HARD_FAIL_FLOOR, MAX_SCORE, MIN_SCORE
from app.risk.history import (
    DEFAULT_HISTORY_CONFIG,
    HISTORY_HALF_LIFE_DAYS,
    HISTORY_MAX_MAGNITUDE,
    HistoryConfig,
    PriorOutcome,
)
from app.risk.scoring import weighted_breakdown, weighted_sum
from app.risk.weightsets.loader import WeightsetError, load_weightset
from app.risk.weightsets.lookup import weight_for

#: The committed weightset, loaded once and read through 7.3's lookup.
WEIGHTSET = load_weightset()

#: 6.5's answer, read rather than restated.  The engine is handed this table
#: from the outside because ``app.risk`` may not import the runner to find it.
HARD_FAIL_IDS = frozenset(runner._HARD_FAIL_IDS)

#: The abstract's own two numbers, in the order it states them: the similarity
#: the comparison measured, and the match threshold it measured it against.
SIMILARITY = 0.41
MATCH_THRESHOLD = 0.55

#: The photo region all three reasons point at, as a four-corner box of whole
#: pixels -- the shape 4.12's ``_box_polygon`` writes.
PHOTO_REGION = ((320, 180), (520, 180), (520, 400), (320, 400))

#: The day history ages are measured against, ``D12``'s injected reference.
#: A constant rather than a call, because no engine answer may depend on the
#: day it happened to be asked on.
REFERENCE = date(2026, 10, 1)


def _weight(flag_id: str) -> float:
    """What ``flag_id`` is worth in the committed weightset."""
    return weight_for(WEIGHTSET, flag_id)


def _flag(flag_id, *, value=1.0, tier=1, region=PHOTO_REGION, **fields):
    """One :class:`EvidenceFlag` of this project's own shape.

    The band on the record is the one the committed file gives the id, read
    out of its row rather than written here, so a flag in a suite cannot
    disagree with the weightset about what it is worth.
    """
    return EvidenceFlag(
        id=flag_id,
        tier=tier,
        label=fields.pop("label", flag_id.replace("_", " ").lower()),
        weight_band=WEIGHTSET.flags[flag_id]["band"],
        value=value,
        confidence=1.0,
        region=region,
        expected=fields.pop("expected", None),
        found=fields.pop("found", None),
        reason=fields.pop("reason", "the rule fired"),
        source_module=fields.pop("source_module", "the rule under test"),
        field=fields.pop("field", None),
    )


def _passes(weight=-100.0, days=0, count=500, verified=True):
    """``count`` outcomes of one kind, ``days`` before the reference."""
    return tuple(
        PriorOutcome(
            outcome_date=REFERENCE - timedelta(days=days),
            weight=weight,
            verified=verified,
        )
        for _ in range(count)
    )


def _history_of(*outcomes, config=DEFAULT_HISTORY_CONFIG):
    """A :class:`ScreeningHistory` carrying ``outcomes`` against the reference."""
    return ScreeningHistory(
        prior_outcomes=outcomes, reference_date=REFERENCE, config=config
    )


def _example(flags=(), *, history=None, hard_fail_ids=HARD_FAIL_IDS, **kwargs):
    """A case scored the way a screening scores one."""
    return compute_risk(
        flags,
        WEIGHTSET,
        history,
        hard_fail_ids=hard_fail_ids,
        **kwargs,
    )
    return compute_risk(
        flags,
        WEIGHTSET,
        history,
        hard_fail_ids=hard_fail_ids,
        **kwargs,
    )


# --- the abstract's worked example B, finding by finding -------------------

#: Tier 1's one finding: the document photograph and the live capture scored
#: 0.41 against a match threshold of 0.55.  **The strength is 1.0 because the
#: rule fired**, which is how 6.2 and 6.4 report every threshold rule of their
#: own, and **the two numbers the rule compared are the flag's own**
#: ``expected`` and ``found`` rather than a share of its weight.
#: ``FACE_LOW_SIMILARITY`` is 7.1's own choice for this case, and 5.3's
#: recorded gap is that the line to ``FACE_MISMATCH`` is 13.16's to draw: the
#: abstract puts 0.41-against-0.55 in the band that escalates, not in a
#: verdict.
FACE = _flag(
    flag_ids.FACE_LOW_SIMILARITY,
    expected=f"{MATCH_THRESHOLD:.2f}",
    found=f"{SIMILARITY:.2f}",
    label="face similarity is below the match threshold",
    reason=(
        f"The document photograph and the live capture scored {SIMILARITY:.2f} "
        f"against a match threshold of {MATCH_THRESHOLD:.2f}."
    ),
    source_module="app.pipeline.tier1.face",
)

#: Tier 2's two: the tamper heat-map concentrating on the photo region, which
#: 15.6 fuses into one finding, and the morph classifier's high score.  Both
#: carry the face finding's own region, which is what "the photo region
#: highlighted" means before 23.5 draws it.
HEAT_MAP = _flag(
    flag_ids.TAMPER_FUSION_ANOMALY,
    tier=2,
    label="the tamper heat-map concentrates on the photo region",
    reason="The fused forensic score localises its concentration on the photo.",
    source_module="app.pipeline.tier2.tamper",
)

MORPH = _flag(
    flag_ids.TAMPER_MORPH_SUSPECTED,
    tier=2,
    label="the morph classifier scores the photograph as morphed",
    reason="The morph classifier's stand-in scores this photograph as morphed.",
    source_module="app.pipeline.tier2.morph",
)

#: The case, in the order the tiers produced it: Tier 1's finding, then Tier
#: 2's two.  **Tier 0 contributes nothing** -- the checksums are valid, the
#: dates are plausible and there is no watchlist hit, which is the abstract's
#: sentence and is asserted below rather than left to the reader.
TIER1_FLAGS = (FACE,)
CASE_FLAGS = (FACE, HEAT_MAP, MORPH)

#: The three reasons the abstract says the officer is shown, in that order.
EXAMPLE_REASONS = (
    flag_ids.FACE_LOW_SIMILARITY,
    flag_ids.TAMPER_FUSION_ANOMALY,
    flag_ids.TAMPER_MORPH_SUSPECTED,
)


# --- Gate 7, the second worked example -------------------------------------


def test_the_face_finding_alone_is_the_partial_score_the_abstract_routes_on():
    """``R1`` falls in the ambiguous band, which is what sends the case on.

    The escalation rule is stated on ``R1``, so ``R1`` is the same call over
    Tier 1's findings alone.  **Nothing in the engine distinguishes a partial
    score from a final one**, and nothing forces a tier boundary into a number.
    """
    partial = _example(TIER1_FLAGS)

    assert partial.score == _weight(flag_ids.FACE_LOW_SIMILARITY)
    assert partial.band == "review"
    assert LOW_MAX < partial.score <= REVIEW_MAX


def test_the_ambiguous_band_is_read_off_the_committed_thresholds():
    """The band ``R1`` lands in is the committed one, not a literal here.

    ``D28``'s pair is uncalibrated, so a ``34`` or a ``69`` written into this
    file would band the example correctly today and be wrong the day the pair
    was retuned.  **Each edge is the top of its own band and not the first of
    the one above it**, which is what the ``_MAX`` in each name says: 34 reads
    as the lowest band and 34.5 does not.
    """
    partial = _example(TIER1_FLAGS)

    assert partial.band == to_band(partial.score)
    assert to_band(LOW_MAX) == "low"
    assert to_band(REVIEW_MAX) == "review"
    assert MIN_SCORE < LOW_MAX < REVIEW_MAX < MAX_SCORE


def test_a_fired_threshold_rule_reports_its_full_strength_and_not_the_gap():
    """Why the face finding's ``value`` is 1.0, held against the other reading.

    :attr:`~app.risk.flags.EvidenceFlag.value` is "how strongly the finding
    itself speaks", and 6.2 and 6.4 write ``value=1.0`` for every threshold
    rule of their own.  The competing reading -- that a finding's strength is
    *how far below* the threshold it fell, ``1 - 0.41`` -- is measured here
    rather than argued about, and **it is the reading the abstract's own
    sentence rules out**: it puts ``R1`` in the lowest band, and a lowest-band
    ``R1`` is the case the escalation rule does not send on.  The similarity
    and the threshold stay on the flag as the two halves of the comparison
    the rule made, which is what ``expected`` and ``found`` are for.
    """
    gap = _flag(flag_ids.FACE_LOW_SIMILARITY, value=round(1.0 - SIMILARITY, 2))

    assert _example((gap,)).band == "low"
    assert FACE.value == 1.0
    assert (FACE.expected, FACE.found) == ("0.55", "0.41")


def test_tier_zero_is_clean_on_this_case():
    """The abstract's first clause: nothing at Tier 0 fired.

    ``R1`` is Tier 1's partial score, so a case carrying a Tier 0 finding
    would already have been stopped by a different clause of the escalation
    rule.  **Asserted from the flags' own ``tier`` field** rather than from
    the ids, because a tier is what the runner recorded and the id is only
    what the weightset weighs.
    """
    assert {flag.tier for flag in CASE_FLAGS} == {1, 2}
    assert all(flag.tier != 0 for flag in CASE_FLAGS)


def test_the_total_exceeds_the_high_threshold_before_the_clamp():
    """"The total R exceeds the high threshold" is a claim about the sum.

    The three findings weigh the sum of their own committed weights, over the
    top of the scale by design -- ``D21``'s rule that corroborating flags may
    exceed 100, and 7.7's clamp that holds the reading rather than rescaling
    it.  **The excess is asserted on the rows and not on the record's score**,
    so the abstract's sentence is a property of the arithmetic rather than of
    where the clamp happened to land.
    """
    total = math.fsum(_weight(flag_id) for flag_id in EXAMPLE_REASONS)
    result = _example(CASE_FLAGS)

    assert total > REVIEW_MAX
    assert total > MAX_SCORE
    assert math.fsum(row.contribution for row in result.contributions) == total
    assert result.score == MAX_SCORE


def test_the_case_reads_a_high_band():
    """The band the officer is shown, and it is the top of the scale."""
    result = _example(CASE_FLAGS)

    assert result.band == "high"
    assert result.score > REVIEW_MAX


def test_the_officer_is_shown_three_reasons_and_they_all_point_at_the_photo():
    """The abstract's three stated reasons, in the order the tiers made them.

    **One row per finding, none merged and none reordered**, which is 7.11's
    claim and the reason a heat-map finding and a morph finding are two rows
    rather than one "forensic" row.  The photo region is a flag's own field
    and not a contribution's, so what is asserted here is that the three
    findings share one region; drawing it over the image is 23.5's.
    """
    result = _example(CASE_FLAGS)

    assert tuple(row.id for row in result.contributions) == EXAMPLE_REASONS
    assert len(result.contributions) == 3
    assert {flag.region for flag in CASE_FLAGS} == {PHOTO_REGION}


def test_every_row_is_its_own_weight_times_its_own_value():
    """Each row shows the two numbers it was multiplied from, side by side.

    An officer reading a row has to be able to check it, which needs both
    operands on the row rather than only their product.  **The weights are
    read off the committed file**, so a retune moves the claim with it.
    """
    for row in _example(CASE_FLAGS).contributions:
        assert row.weight == _weight(row.id)
        assert row.value == 1.0
        assert row.contribution == row.weight * row.value
        assert row.contribution == row.weight * row.value


# --- the record, and what it is held to ------------------------------------


def test_the_ruleset_version_is_the_weightset_the_caller_held():
    """A score is quoted against the ruleset that produced it.

    Read off the record the caller passed rather than off
    :data:`app.version.RULESET_VERSION`, so a screening scored against a
    weightset that is not the one the service ships reports *that* ruleset's
    version.  **A version the service does not ship is therefore
    expressible**, which is the whole reason the field is on the record.
    """
    elsewhere = dataclasses.replace(WEIGHTSET, ruleset_version="9.9.9")

    assert _example(CASE_FLAGS).ruleset_version == WEIGHTSET.ruleset_version
    assert compute_risk(
        CASE_FLAGS, elsewhere, hard_fail_ids=HARD_FAIL_IDS
    ).ruleset_version == "9.9.9"


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param((), id="nothing-fired"),
        pytest.param(TIER1_FLAGS, id="one-finding"),
        pytest.param(CASE_FLAGS, id="the-example"),
        pytest.param(
            (_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, tier=0),), id="a-hard-fail"
        ),
        pytest.param(
            tuple(_flag(flag_ids.OCR_LOW_CONFIDENCE, value=0.1) for _ in range(4)),
            id="a-soft-pile",
        ),
    ],
)
def test_the_band_is_read_off_the_score_this_record_carries(flags):
    """The two cannot disagree, because there is only one number.

    Every answer is inside the scale and its band is 7.9's answer for that
    same number -- including the answers where the sum, the history term and
    the floor all moved the number on the way there.
    """
    result = _example(flags)

    assert isinstance(result, RiskResult)
    assert MIN_SCORE <= result.score <= MAX_SCORE
    assert result.band == to_band(result.score)
    assert result.band in {"low", "review", "high"}


def test_a_document_with_nothing_fired_is_a_real_answer():
    """The empty case, answered rather than refused.

    A tier that found nothing produced no flags, and that is a screening that
    reached the engine: 7.5's empty sum is ``0.0`` and this is where that
    ``0.0`` becomes a reading on the scale and a band an officer can see.
    """
    result = _example(())

    assert result.score == 0.0
    assert result.band == "low"
    assert result.contributions == ()
    assert result.ruleset_version == WEIGHTSET.ruleset_version


def test_the_rows_add_up_to_the_pre_history_total_and_not_to_the_score():
    """The honest gap, asserted rather than left to be discovered.

    4.8's term, 7.6's floor and 7.7's clamp all sit between the rows and the
    score, so on a case with any of them the rows do not add up to the number
    beside them.  **That is what 7.11's "pre-history" names**, and the number
    the rows *are* the sum of is the one 7.5 already returns.  A record whose
    rows silently tracked the score would be claiming the officer could add
    the column up and get the band, and on a hard fail they could not.
    """
    flags = (
        _flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, tier=0, value=0.0),
        FACE,
    )
    result = _example(flags)
    rows = math.fsum(row.contribution for row in result.contributions)

    assert rows == weighted_breakdown(flags, WEIGHTSET).total
    assert result.contributions[0].contribution == 0.0
    assert result.contributions[-1].contribution == pytest.approx(
        _weight(flag_ids.FACE_LOW_SIMILARITY)
    )
    assert result.score == DEFAULT_HARD_FAIL_FLOOR
    assert rows < result.score


def test_the_rows_are_the_ones_the_sum_was_made_of():
    """The record's rows and 7.5's own breakdown are the same rows.

    Held by equality rather than by re-deriving the products, so a record
    that recomputed or rounded its own rows would be caught here.
    """
    breakdown = weighted_breakdown(CASE_FLAGS, WEIGHTSET)

    assert _example(CASE_FLAGS).contributions == breakdown.contributions
    assert math.fsum(row.contribution for row in breakdown.contributions) == (
        breakdown.total
    )
    assert breakdown.total == weighted_sum(CASE_FLAGS, WEIGHTSET)


def test_one_finding_is_one_row_even_when_two_findings_carry_one_id():
    """7.11's claim, held at the record: nothing is merged or deduplicated.

    Two face findings are two measurements that happened to fire the same
    rule, and an officer is owed both of them.
    """
    result = _example((FACE, FACE))

    assert len(result.contributions) == 2
    assert result.score == pytest.approx(2 * _weight(flag_ids.FACE_LOW_SIMILARITY))


def test_the_record_is_frozen():
    """A caller cannot amend the score and leave the band reading another."""
    result = _example(CASE_FLAGS)

    for field, value in (
        ("score", 0.0),
        ("band", "low"),
        ("contributions", ()),
        ("ruleset_version", "9.9.9"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, field, value)


# --- the order, held by the source rather than by this docstring -----------

#: The five questions, in the order this file and the module both name.
ENGINE_QUESTIONS = (
    "weighted_breakdown",
    "apply_history",
    "apply_hard_rules",
    "clamp_score",
    "to_band",
)

#: What :func:`~app.risk.engine.compute_risk` may call beside them: the three
#: argument checks and the record it builds.  Nothing here writes arithmetic,
#: so a second sum, a second floor or a hand-rolled band would have to appear
#: in this set to be allowed at all.
ENGINE_HELPERS = ("_findings", "_weights", "_history", "RiskResult")

ENGINE_SOURCE = pathlib.Path(engine.__file__).read_text(encoding="utf-8")


def _engine_tree() -> ast.Module:
    return ast.parse(ENGINE_SOURCE)


def _engine_function(name: str) -> ast.FunctionDef:
    """``name``'s own definition, read out of the module's source."""
    for node in ast.walk(_engine_tree()):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined in {engine.__file__}")


def _calls_in(function: ast.AST) -> list[ast.Call]:
    return [node for node in ast.walk(function) if isinstance(node, ast.Call)]


def test_the_five_questions_are_asked_once_each_and_in_the_order_named():
    """The order is the design, and a docstring cannot hold it.

    ``D34``'s counterfactual is the reason: 500 verified passes take a hard
    failure's ``0.0`` to ``-12.0`` and the reading is still the floor where
    the other order answers ``78.0``.  **A test that reads the five calls out
    of the source is the only one that fails** when the next edit moves the
    term above the floor, which would otherwise be an edit that changed no
    assertion in this file.
    """
    asked = sorted(
        (call.lineno, call.func.id)
        for call in _calls_in(_engine_function("compute_risk"))
        if isinstance(call.func, ast.Name) and call.func.id in ENGINE_QUESTIONS
    )

    assert tuple(name for _, name in asked) == ENGINE_QUESTIONS


def test_compute_risk_calls_nothing_but_those_five_and_its_own_helpers():
    """No arithmetic of its own, and no second answer to any one question.

    The call set is the whole composition: a second sum, a second floor, a
    hand-written band or a sixth helper would be in this set and would fail
    this.  **No binary operator appears in the function either**, which is the
    sharper half -- the engine adds, floors, clamps and bands nothing; it asks
    four modules that each do one of those.
    """
    function = _engine_function("compute_risk")
    called = {
        call.func.id
        for call in _calls_in(function)
        if isinstance(call.func, ast.Name)
    }

    assert called == set(ENGINE_QUESTIONS) | set(ENGINE_HELPERS)
    assert not [node for node in ast.walk(function) if isinstance(node, ast.BinOp)]


def test_the_engine_never_imports_the_pipeline():
    """``D6``'s one-way dependency, read off the imports.

    Which rules override is 6.5's answer and it lives in the runner, so the
    engine is handed the table rather than reaching for it: a rule can be
    handed a weightset and the engine can be handed a table, and neither
    package has to know about the other.
    """
    imported = {
        node.module or ""
        for node in ast.walk(_engine_tree())
        if isinstance(node, ast.ImportFrom)
    }
    imported |= {
        alias.name
        for node in ast.walk(_engine_tree())
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert not [name for name in imported if name.startswith("app.pipeline")]


def test_no_clock_is_reached_anywhere_in_the_engine():
    """A screening's band is the same on every run, so nothing reads today.

    ``D12``'s named dependency is handed in on
    :attr:`ScreeningHistory.reference_date`; a clock reached here would make a
    replay of a screening a replay of nothing at all.
    """
    tree = _engine_tree()
    modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    modules |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    clocks = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } & {"now", "today", "utcnow", "time", "monotonic", "perf_counter"}

    assert not [
        name for name in modules if name in {"time", "calendar", "zoneinfo"}
    ]
    assert clocks == set()


def test_the_hard_fail_table_is_required_and_is_not_defaulted():
    """No default on purpose, and a call without one is a ``TypeError``.

    A defaulted table would be a second copy of 6.5's answer somewhere it can
    drift, and an empty one would let a broken checksum be scored at 60 and
    read as a document with a question on it -- the opposite of what
    "override" means.  **The refusal is Python's own**, so it happens before
    any argument is read and cannot be caught and answered around.
    """
    with pytest.raises(TypeError):
        compute_risk(CASE_FLAGS, WEIGHTSET)


def test_the_findings_are_read_once_and_the_hard_rule_question_sees_them():
    """A generator is a legal argument, which it would not be read twice.

    7.6's floor asks its own question of the same findings the sum was
    computed from, so a generator consumed by the sum would arrive empty
    there and answer the sum it already had.  **Read once into a tuple**, so
    the override is asked of exactly what was scored.
    """
    hard = _flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, tier=0)

    assert _example(flag for flag in (hard,)).score == DEFAULT_HARD_FAIL_FLOOR
    assert _example(iter(CASE_FLAGS)) == _example(CASE_FLAGS)
    assert _example(flag for flag in (hard,)).score == DEFAULT_HARD_FAIL_FLOOR
    assert _example(iter(CASE_FLAGS)) == _example(CASE_FLAGS)


# --- hard rules, composed --------------------------------------------------


@pytest.mark.parametrize("size", [1, 5, 25, 100])
def test_a_hard_fail_cannot_be_outvoted_by_many_soft_flags(size):
    """7.6's claim, at the record: the pile is real and the floor holds.

    The soft pile is built from ids the runner's own table does **not** call
    hard fails, read from the other side of the package, so the sweep cannot
    prove the override with itself.  At ``1.0`` every one of them scores its
    own whole weight, so 100 of them is a pile several times the top of the
    scale.  **The pile repeats its vocabulary** rather than truncating it, so
    the largest size is genuinely 100 findings.

    **The floor is a floor and not a ceiling**: 7.6's question is whether the
    pile can hold a hard fail *down*, and the answer is that it cannot, so the
    assertion is that the reading never falls below the floor rather than that
    it equals it.  A pile heavier than 90 reads heavier -- "a hard fail cannot
    make a heavier document read safer" -- and one answer is the clamp's, not
    the floor's.

    **The expected number is the engine's own composition rather than a second
    rule** -- ``min(MAX, max(floor, sum))``, with the overriding flag's own
    weight inside the sum.  7.6 is a ``max`` applied above the sum, so a pile
    too light to reach the floor reads the floor and nothing more.  14.3 put
    nine five-point rows at the head of the vocabulary, which is what made a
    light pile reachable here at all; the formula this replaces read as
    ``min(MAX, floor + pile)``, agreed with it only because every size it was
    given clamped to 100 (D106).
    """
    soft = [
        flag_id
        for flag_id in flag_ids.ALL_FLAG_IDS
        if flag_id not in HARD_FAIL_IDS
    ]
    pile = tuple(_flag(soft[index % len(soft)]) for index in range(size))
    result = _example((_flag(flag_ids.WATCHLIST_HIT, tier=0), *pile))

    assert result.score >= DEFAULT_HARD_FAIL_FLOOR
    assert result.band == "high"
    assert len(result.contributions) == size + 1
    assert result.score == min(
        MAX_SCORE,
        max(
            DEFAULT_HARD_FAIL_FLOOR,
            _weight(flag_ids.WATCHLIST_HIT)
            + math.fsum(_weight(soft[i % len(soft)]) for i in range(size)),
        ),
    )


def test_the_floor_is_configurable_through_the_engine():
    """7.6's configurable floor is the engine's floor, not only its own."""
    hard = _flag(flag_ids.WATCHLIST_HIT, tier=0)

    assert compute_risk(
        (hard,), WEIGHTSET, hard_fail_ids=HARD_FAIL_IDS, floor=75.0
    ).score == 75.0
    with pytest.raises(FlagValueError):
        compute_risk((hard,), WEIGHTSET, hard_fail_ids=HARD_FAIL_IDS, floor=101.0)


def test_a_soft_pile_is_held_at_the_top_and_the_rows_are_not_rewritten():
    """The clamp holds the reading and does not touch the rows.

    Three ``high`` findings at full strength is 195 points, ``D21``'s reason
    weights are points rather than shares.  **The rows still show 195**,
    because 7.7 clamps the number and not the explanation, and an officer
    shown a column summing to 100 against a weightset whose rows say 65 each
    is being shown an answer nobody can check.
    """
    pile = (
        _flag(flag_ids.CROSSDOC_FACE_MISMATCH),
        _flag(flag_ids.TAMPER_MORPH_SUSPECTED),
        _flag(flag_ids.MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH),
    )
    result = _example(pile, hard_fail_ids=frozenset())

    assert math.fsum(row.contribution for row in result.contributions) == 195.0
    assert result.score == MAX_SCORE
    assert result.band == "high"


def test_a_score_driven_below_the_scale_is_held_at_the_bottom():
    """The other end of the clamp, asked through the whole chain."""
    weak = (_flag(flag_ids.OCR_LOW_CONFIDENCE, value=0.1),)
    result = _example(weak, history=_history_of(*_passes()))

    assert weighted_sum(weak, WEIGHTSET) - HISTORY_MAX_MAGNITUDE < MIN_SCORE
    assert result.score == MIN_SCORE
    assert result.band == "low"


# --- history, composed -----------------------------------------------------


def test_no_history_is_a_term_of_nothing_and_says_so():
    """``history=None`` and an empty history are the same reading.

    A first sighting is not a screening with a history of zero: the two are
    the same answer here, and 7.14's call is not made at all for the first,
    which is why the two records compare equal rather than merely agreeing.
    """
    assert _example(CASE_FLAGS) == compute_risk(
        CASE_FLAGS, WEIGHTSET, _history_of(), hard_fail_ids=HARD_FAIL_IDS
    )


def test_a_verified_pass_lowers_the_score_the_record_reports():
    """4.8's continuity, at the record: a pass is a negative term.

    **The rows are the pre-history ones and the score is the lower number**,
    and both are on the record, which is the honest shape of a case whose
    history moved it.
    """
    plain = _example(TIER1_FLAGS)
    result = _example(
        TIER1_FLAGS, history=_history_of(*_passes(weight=-10.0, count=1))
    )

    assert result.score < plain.score
    assert result.score == pytest.approx(plain.score - 10.0)
    assert math.fsum(row.contribution for row in result.contributions) == plain.score


def test_an_unverified_outcome_contributes_nothing_to_the_record():
    """4.8's "only verified outcomes are used", held at the record."""
    unverified = _example(
        TIER1_FLAGS,
        history=_history_of(*_passes(weight=-100.0, verified=False)),
    )

    assert unverified == _example(TIER1_FLAGS)


def test_an_old_verified_pass_cannot_move_the_band():
    """The bound is the claim, and it is 7.13's rather than this file's.

    Four 15-point findings read the middle band with a margin wider than the
    history bound, so **even the whole pile of 500 verified passes at full
    strength leaves the band where it was**.  The bound and the band width are
    read off :mod:`app.risk.history` and :mod:`app.risk.config` rather than
    written here, so the claim survives a retune of either -- and fails one,
    which is the point: a bound wider than the narrowest band would stop being
    a bound.
    """
    findings = tuple(_flag(flag_ids.OCR_LOW_CONFIDENCE) for _ in range(4))
    plain = _example(findings)
    aged = _example(findings, history=_history_of(*_passes()))

    assert plain.band == "review"
    assert HISTORY_MAX_MAGNITUDE < REVIEW_MAX - LOW_MAX
    assert aged.band == "review"
    assert aged.score == plain.score - HISTORY_MAX_MAGNITUDE


def test_the_history_term_sits_under_the_floor_not_above_it():
    """``D34``'s order, held end to end for the first time.

    A hard failure and 500 verified passes: history is added to the sum, the
    floor is a ``max`` above it, and the reading is the floor.  **The other
    order answers the term itself**, so this is the assertion that would fail
    first if the composition were rearranged.
    """
    hard = (_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, tier=0),)
    result = _example(hard, history=_history_of(*_passes()))

    assert result.score == DEFAULT_HARD_FAIL_FLOOR
    assert result.band == "high"
    assert result.score > weighted_sum(hard, WEIGHTSET) + HISTORY_MAX_MAGNITUDE


def test_an_aged_pass_is_worth_less_than_a_fresh_one_at_the_record():
    """The decay, at the record: one case, two histories, two readings."""
    fresh = _example(
        TIER1_FLAGS, history=_history_of(*_passes(weight=-10.0, count=1))
    )
    two_half_lives = _example(
        TIER1_FLAGS,
        history=_history_of(
            *_passes(
                weight=-10.0, days=2 * int(HISTORY_HALF_LIFE_DAYS), count=1
            )
        ),
    )

    assert two_half_lives.score > fresh.score
    assert two_half_lives.score == pytest.approx(
        _weight(flag_ids.FACE_LOW_SIMILARITY) - 2.5
    )


def test_a_calibration_the_caller_names_is_the_one_that_is_used():
    """``config`` is a parameter, not a constant this module re-reads."""
    narrow = HistoryConfig(half_life_days=HISTORY_HALF_LIFE_DAYS, max_magnitude=1.0)
    result = _example(TIER1_FLAGS, history=_history_of(*_passes(), config=narrow))

    assert result.score == pytest.approx(_weight(flag_ids.FACE_LOW_SIMILARITY) - 1.0)


# --- the record's own refusals --------------------------------------------


@pytest.mark.parametrize(
    ("argument", "build"),
    [
        pytest.param("flags", lambda: "FACE_LOW_SIMILARITY", id="flags-as-a-string"),
        pytest.param("flags", lambda: 7, id="flags-as-an-int"),
        pytest.param(
            "flags",
            lambda: (dataclasses.replace(FACE, id=None),),
            id="a-flag-with-no-id",
        ),
        pytest.param(
            "flags",
            lambda: (dataclasses.replace(FACE, id=7),),
            id="a-flag-id-of-the-wrong-type",
        ),
        pytest.param(
            "flags",
            lambda: (dataclasses.replace(FACE, id="NOT_A_FLAG_ID"),),
            id="an-id-the-weightset-cannot-weigh",
        ),
        pytest.param("weights", lambda: "v1", id="a-weightset-named-not-loaded"),
        pytest.param(
            "weights", lambda: {"flags": {}}, id="a-weightset-as-a-mapping"
        ),
        pytest.param("history", lambda: [], id="history-as-a-list"),
        pytest.param("history", lambda: _passes(count=1), id="history-as-outcomes"),
        pytest.param("history", lambda: "PASS", id="history-as-a-string"),
    ],
)
def test_a_malformed_argument_is_refused_rather_than_answered(argument, build):
    """Every gate still gates, once the engine composes them.

    These are the arguments whose **type** is wrong at the seam; the
    field-level faults are each module's own and are held in their own
    suites.  Nothing is coerced, defaulted or answered around: a screening
    stops rather than producing a record of half its findings.
    """
    arguments = {"flags": (), "weights": WEIGHTSET, "history": None}

    with pytest.raises(ValueError):
        arguments[argument] = build()
        compute_risk(**arguments, hard_fail_ids=HARD_FAIL_IDS)


@pytest.mark.parametrize(
    "value", [None, True, 1.4, -0.1], ids=["none", "true", "above-one", "below-zero"]
)
def test_a_value_the_engine_would_refuse_never_reaches_a_record(value):
    """7.4's gate, at the record: an unmeasured value stops the screening."""
    with pytest.raises(FlagValueError):
        _example((_flag(flag_ids.FACE_LOW_SIMILARITY, value=value),))


def test_a_bare_string_of_ids_is_not_a_table_of_hard_fails():
    """7.6's refusal, held at the record: the table is a collection.

    Iterated, ``"WATCHLIST_HIT"`` is eleven characters that match no id, so
    the mistake would answer every screening with the sum it already had and
    never raise.
    """
    with pytest.raises(FlagValueError):
        _example(CASE_FLAGS, hard_fail_ids="WATCHLIST_HIT")


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(
            lambda: {"prior_outcomes": "PASS", "reference_date": REFERENCE},
            id="outcomes-as-a-string",
        ),
        pytest.param(
            lambda: {
                "prior_outcomes": (),
                "reference_date": datetime(2026, 10, 1, 9, 30),
            },
            id="a-timestamp-for-the-reference",
        ),
        pytest.param(
            lambda: {"prior_outcomes": (), "reference_date": "2026-10-01"},
            id="a-string-for-the-reference",
        ),
        pytest.param(
            lambda: {
                "prior_outcomes": (),
                "reference_date": REFERENCE,
                "config": 180.0,
            },
            id="a-config-that-is-not-a-record",
        ),
        pytest.param(
            lambda: {
                "prior_outcomes": (
                    dataclasses.replace(_passes(count=1)[0], verified=1),
                ),
                "reference_date": REFERENCE,
            },
            id="an-outcome-verified-by-truthiness",
        ),
    ],
)
def test_a_screening_history_is_checked_where_it_is_built(build):
    """``D12``'s reference and 7.13's gate, refused at the record.

    **The checks are 7.13's own** rather than second copies of them, so a
    day that is a timestamp and an outcome "verified" by ``1`` are refused in
    the same words and for the same reason whichever record is built.
    """
    with pytest.raises(FlagValueError):
        ScreeningHistory(**build())


def test_the_sum_is_asked_first_so_a_call_with_two_faults_names_the_findings():
    """A screening stops at the first fault rather than answering around one."""
    with pytest.raises(FlagValueError) as caught:
        compute_risk("FACE_LOW_SIMILARITY", "v1", hard_fail_ids=HARD_FAIL_IDS)

    assert "flags" in str(caught.value)


def test_a_weightset_error_stays_a_weightset_error_at_the_record():
    """7.2's and 7.3's type is the one a caller around the engine catches."""
    with pytest.raises(WeightsetError):
        _example((dataclasses.replace(FACE, id="NOT_A_FLAG_ID"),))
