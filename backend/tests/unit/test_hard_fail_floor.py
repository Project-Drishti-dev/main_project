"""One hard fail lifts the score to a floor the soft pile cannot argue with.

Task 7.6 asks for hard-rule handling -- any hard fail raises ``R`` to a
configurable floor, default 90, regardless of the sum -- and for a test
proving a hard fail cannot be outvoted by many soft flags.  The headline test
below is that second claim, and it is written as a sweep over the size and
strength of the soft pile rather than as one worked number, because "many" is
the part of the claim that a single example can understate.

**6.5's table is read here and nowhere in the package.**  Which rules override
is :data:`app.pipeline.tier0.runner._HARD_FAIL_IDS`, a union of each family's
own table held beside its own labels, and this file reads it from the other
side the way 7.1's suite reads the watchlist bands.  Two tables holding one
fact is how they drift apart; one table read twice is not.  So the ids come
from the runner, the weights come from the committed weightset, and neither is
retyped here.

**The floor is 90 because 7.8's ``REVIEW_MAX`` is 69.**  A hard fail has to
reach High to be an override at all, and the threshold is imported rather
than written out here, so the two numbers are held to each other by a retune
rather than by a copy.

**The rest of the file is what the floor must not do**: lower a heavier score,
read the overriding flag's own strength, answer for a table it was not given,
or turn a malformed argument into a number.
"""

import ast
import dataclasses
import pathlib

import pytest

from app.pipeline.tier0 import runner
from app.risk import flag_ids, hard_rules
from app.risk.config import REVIEW_MAX
from app.risk.flags import EvidenceFlag, FlagValueError
from app.risk.hard_rules import (
    DEFAULT_HARD_FAIL_FLOOR,
    MAX_SCORE,
    MIN_SCORE,
    apply_hard_rules,
)
from app.risk.scoring import weighted_sum
from app.risk.weightsets.loader import load_weightset

#: A field-shaped box: two lines of pixels, clockwise from the top left, the
#: shape 4.12's `_box_polygon` writes.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: 6.5's answer, read rather than restated.  A family joins it by editing the
#: table beside its own labels, and every id in it is one this engine's floor
#: is being asked about.
HARD_FAIL_IDS = frozenset(runner._HARD_FAIL_IDS)

#: Every id that does *not* override.  The soft pile is built from these, so a
#: sweep over it cannot accidentally put a second override in the pile and
#: prove the override with itself.
SOFT_FLAG_IDS = tuple(
    flag_id for flag_id in flag_ids.ALL_FLAG_IDS if flag_id not in HARD_FAIL_IDS
)

#: The soft pile's sizes and strengths.  100 findings is four passes over the
#: whole non-overriding vocabulary, and at `1.0` every one of them scores its
#: own whole weight -- a pile several times the top of the scale, which is the
#: situation in which a diluted override would show.
PILE_SIZES = (0, 1, 5, 25, 100)
PILE_VALUES = (0.0, 0.5, 1.0)

#: The strengths an overriding rule may report, swept because the override's
#: whole claim is that none of them changes the answer.
HARD_FAIL_VALUES = (0.0, 0.25, 0.5, 1.0)

#: The abstract's own named override, worked example A's date-of-birth check
#: digit, used wherever one overriding rule has to stand for the family.
OVERRIDING_FLAG = flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH


def a_flag(flag_id, value=1.0, **overrides):
    """A well-formed flag, with ``overrides`` replacing any of its fields."""
    fields = {
        "id": flag_id,
        "tier": 0,
        "label": "A finding worth explaining",
        "weight_band": "high",
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


def a_soft_pile(size, value):
    """``size`` soft findings cycling the whole non-overriding vocabulary."""
    return [
        a_flag(
            SOFT_FLAG_IDS[index % len(SOFT_FLAG_IDS)],
            value,
            weight_band="low",
        )
        for index in range(size)
    ]


def the_score(flags):
    """``R`` for ``flags``, read off the committed weightset."""
    return weighted_sum(flags, load_weightset())


def the_answer(flags, score=None, floor=None):
    """The end-to-end answer: 7.5's sum, then 7.6's floor over it."""
    total = the_score(flags) if score is None else score
    if floor is None:
        return apply_hard_rules(total, flags, HARD_FAIL_IDS)
    return apply_hard_rules(total, flags, HARD_FAIL_IDS, floor=floor)


@dataclasses.dataclass(frozen=True)
class DraftFinding:
    """A record carrying an ``id`` and nothing else this question asks about.

    Used for the two records a well-formed flag cannot be: one with no ``id``
    at all, and one whose id is carried as something that is not a string.
    """

    id: object = None


# --- the test the task names ------------------------------------------------


@pytest.mark.parametrize("size", PILE_SIZES)
@pytest.mark.parametrize("value", PILE_VALUES)
def test_a_hard_fail_cannot_be_outvoted_by_many_soft_flags(size, value):
    """The claim, swept over the soft pile rather than illustrated by one size.

    **The hard fail is measured at ``0.0``**, the weakest reading
    :class:`~app.risk.flags.EvidenceFlag` allows, so under any scheme that
    scores a finding as weight times strength it contributes nothing at all and
    the pile alone decides the answer.  **The soft pile is every id the runner
    does not call a hard fail, up to four passes over all of them at full
    strength** -- several times the top of the scale, so a sum that is
    renormalised, averaged or diluted by the pile shows up here as a lower
    number than the floor.

    Four claims, none of them a restatement of the implementation:

    1. **the hard fail's own move in the sum is 7.5's arithmetic and nothing
       else** -- ``weight * value``, which is nothing at all when the rule
       measured ``0.0`` -- so nothing about the override is hiding in it;
    2. **nothing the pile does puts the answer below the floor** -- the pile
       may be empty or a hundred full-strength findings, and a floor that
       were diluted, averaged or summed away fails here;
    3. **nor below the sum it was handed**, so the pile cannot buy a lighter
       answer by being larger; and
    4. **an empty pile reaches the floor exactly**, so the override is the
       whole of the answer there rather than a rounding of something else.

    The other half of "outvoted" -- that a rule's own uncertainty cannot buy
    its way out of the floor -- is
    :func:`test_the_answer_does_not_move_with_how_strongly_the_rule_measured`.
    """
    loaded = load_weightset()
    soft = a_soft_pile(size, value)
    screened = weighted_sum(soft, loaded)
    weight = loaded.flags[OVERRIDING_FLAG]["weight"]

    assert the_answer(soft, score=screened) == screened

    for hard_value in HARD_FAIL_VALUES:
        flags = soft + [a_flag(OVERRIDING_FLAG, hard_value)]
        with_hard_fail = weighted_sum(flags, loaded)

        assert with_hard_fail == screened + weight * hard_value

        answered = the_answer(flags, score=with_hard_fail)

        assert answered >= DEFAULT_HARD_FAIL_FLOOR
        assert answered >= with_hard_fail
        if with_hard_fail < DEFAULT_HARD_FAIL_FLOOR:
            assert answered == DEFAULT_HARD_FAIL_FLOOR


def test_the_answer_does_not_move_with_how_strongly_the_rule_measured():
    """The other half of "outvoted", at a pile that would otherwise decide it.

    A checksum that is *wrong* is a checksum that is wrong: the rule either
    recomputed it and disagreed, or it did not and said so.  A floor that
    weighted its override by how strongly the rule measured would let a rule
    reporting `0.0` be outvoted by the same pile that a rule reporting `1.0`
    overrides -- and 5.2 leaves `value` free precisely because a rule that
    cannot quantify a disagreement must still be able to report one.

    **The score is handed in fixed** across the sweep, because that is the
    shape the floor sees: 7.5 has already added the terms, including this
    flag's own, and 7.6 is asked one further question about them.
    """
    loaded = load_weightset()
    pile = a_soft_pile(100, 1.0)
    screened = weighted_sum(pile, loaded)

    assert screened > DEFAULT_HARD_FAIL_FLOOR
    assert {
        the_answer(
            pile + [a_flag(OVERRIDING_FLAG, value)],
            score=screened,
        )
        for value in HARD_FAIL_VALUES
    } == {screened}


def test_the_soft_pile_alone_reaches_further_than_the_floor():
    """The pile is measured, so the sweep above is a real contest and not a
    formality: a hundred full-strength soft findings carry the score past 90
    before the override is applied, which is where `D21` stops being a rule
    about one finding and becomes a fact about many.
    """
    loaded = load_weightset()
    pile = a_soft_pile(100, 1.0)

    assert weighted_sum(pile, loaded) > MAX_SCORE
    assert weighted_sum(pile, loaded) > DEFAULT_HARD_FAIL_FLOOR


def test_the_override_never_lowers_a_score_that_is_already_above_the_floor():
    """A floor that lowered would be a second way to fail a genuine traveller.

    The mistake this rules out is adding the floor to the score rather than
    taking the larger of the two.  A screening with a blacklist hit and
    corroborating findings is already past the floor, and an additive override
    would report 285 for a 0-100 scale -- which 7.7 would then clamp to 100
    and lose every point of margin above the threshold.
    """
    loaded = load_weightset()
    flags = [
        a_flag(flag_ids.WATCHLIST_HIT, 1.0),
        a_flag(flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH, 1.0),
        a_flag(flag_ids.CROSSDOC_FACE_MISMATCH, 1.0),
    ]
    screened = weighted_sum(flags, loaded)

    assert screened > DEFAULT_HARD_FAIL_FLOOR
    assert the_answer(flags, score=screened) == screened


def test_a_hard_fail_alone_reaches_the_floor_measured_at_nothing():
    """Worked example A's shape: a broken checksum and nothing else.

    6.7's test draws the document and reads it through the runner; this is the
    arithmetic under it.  A single failing printed digit with no other finding
    on the page is the abstract's "exits directly to High Risk", and the floor
    is the whole of what puts it there -- the flag's own weight is 60 and its
    own value is 0.0, so the sum has nothing to do with the answer.
    """
    hard_fail = a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 0.0)

    assert the_score([hard_fail]) == 0.0
    assert the_answer([hard_fail]) == DEFAULT_HARD_FAIL_FLOOR
    assert the_answer([hard_fail]) > REVIEW_MAX


def test_a_hard_fail_is_the_only_single_finding_that_reaches_high():
    """`D21`'s other half: corroboration reaches High, and a hard fail does not
    need any.

    The heaviest single weight in `v1.yaml` is 65 against a `REVIEW_MAX` of
    69, so **no one soft finding can send a document to High on its own**
    whatever its value.  Read here rather than asserted from 7.1's suite, so
    this file's claim about a hard fail and that file's claim about a weight
    are two sides of one number.
    """
    loaded = load_weightset()
    heaviest_soft = max(
        SOFT_FLAG_IDS, key=lambda flag_id: loaded.flags[flag_id]["weight"]
    )

    assert loaded.flags[heaviest_soft]["weight"] <= REVIEW_MAX
    assert the_answer([a_flag(heaviest_soft, 1.0)]) <= REVIEW_MAX
    assert the_answer([a_flag(flag_ids.WATCHLIST_HIT, 1.0)]) == (
        DEFAULT_HARD_FAIL_FLOOR
    )


def test_the_default_floor_is_ninety_and_sits_clear_of_the_high_threshold():
    """The task's number, and the reason it is above `REVIEW_MAX` rather than
    on it.

    A floor equal to the threshold would leave `to_band`'s comparison in
    charge of whether a hard fail is High, and 7.9 would have to know about
    hard rules at all.  Twenty-one points of daylight means the override lands
    in High under the same arithmetic as any other score.
    """
    assert DEFAULT_HARD_FAIL_FLOOR == 90.0
    assert DEFAULT_HARD_FAIL_FLOOR > REVIEW_MAX
    assert DEFAULT_HARD_FAIL_FLOOR <= MAX_SCORE


# --- the floor is asked of the ids, and not of anything else ----------------


@pytest.mark.parametrize("flag_id", sorted(HARD_FAIL_IDS))
def test_every_id_the_runner_calls_a_hard_fail_lifts_the_score(flag_id):
    """The whole of 6.5's table, held against the engine's own answer.

    The floor does not hold a copy of the table, so the claim that the two
    agree is this test rather than a comparison in production code.  It runs
    over the table rather than over two examples of it, on 6.5's reason: the
    claim is that the union holds, not that a representative of it does.
    """
    flag = a_flag(flag_id, 0.0)

    assert flag_id not in SOFT_FLAG_IDS
    assert the_answer([flag]) == DEFAULT_HARD_FAIL_FLOOR


@pytest.mark.parametrize("flag_id", SOFT_FLAG_IDS)
def test_no_id_the_runner_does_not_call_a_hard_fail_moves_the_score(flag_id):
    """The converse, over every remaining id in the vocabulary.

    A floor applied to a soft finding would be a stand-in heuristic rejecting a
    genuine traveller, which is the false alarm `D21` lists under the Review
    band's reason for existing.  Fifteen of the twenty-five are `high`, so
    this cannot be satisfied by a floor that asked about the band -- see
    :func:`test_the_override_is_not_the_weight_band`.
    """
    flag = a_flag(flag_id, 1.0)
    loaded = load_weightset()

    assert the_answer([flag]) == weighted_sum([flag], loaded)


def test_the_override_is_not_the_weight_band():
    """6.5's point, as arithmetic: two `high` bands, one override.

    A blacklist hit and a failed printed checksum are both `high` in
    `v1.yaml`, and so is a stolen-document hit -- which does not override.  A
    floor that asked about the band would have to give one answer for two
    different claims, and the only way to make it agree with the runner on the
    first two is to get the third wrong.
    """
    hard_fail = a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 1.0)
    heavy_soft = a_flag(flag_ids.WATCHLIST_STOLEN_DOCUMENT, 1.0)
    loaded = load_weightset()
    high_soft = [
        flag_id
        for flag_id in SOFT_FLAG_IDS
        if loaded.flags[flag_id]["band"] == "high"
    ]

    assert hard_fail.weight_band == heavy_soft.weight_band == "high"
    assert the_answer([hard_fail]) == DEFAULT_HARD_FAIL_FLOOR
    assert the_answer([heavy_soft]) < DEFAULT_HARD_FAIL_FLOOR
    assert high_soft, "D21 gave the high band fifteen ids, so this is not vacuous"
    assert [
        the_answer([a_flag(flag_id, 1.0)]) for flag_id in high_soft
    ] == [loaded.flags[flag_id]["weight"] for flag_id in high_soft]


def test_the_score_alone_decides_whether_a_finding_was_weighted():
    """Nothing about the floor reads a weight, so 7.3's refusal still reaches
    the caller rather than being side-stepped by the override.

    A hard fail id whose weight is missing from the weightset cannot be
    scored, and a screening that cannot be summed cannot be floored either:
    answering `90` from the override alone would be a score nobody could
    trace back to a weightset.
    """
    loaded = load_weightset()
    flags = [
        a_flag("NOT_A_REAL_FLAG_ID", 1.0),
        a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 0.0),
    ]

    with pytest.raises(ValueError):
        the_score(flags)
    with pytest.raises(ValueError):
        the_answer(flags)


def test_no_id_override_is_held_as_a_list_and_a_set_are_the_same_answer():
    """6.5's table is a `frozenset` and the union beside it a `frozenset`
    too; a caller holding a list, a tuple or a generator is answered the same
    way, so the engine is not holding a container type of its own.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]
    answers = {
        apply_hard_rules(0.0, flags, table)
        for table in (
            set(HARD_FAIL_IDS),
            sorted(HARD_FAIL_IDS),
            tuple(HARD_FAIL_IDS),
            iter(sorted(HARD_FAIL_IDS)),
        )
    }

    assert answers == {DEFAULT_HARD_FAIL_FLOOR}


# --- nothing else about the floor -------------------------------------------


def test_an_empty_iterator_of_ids_is_no_hard_fail_at_all():
    """A generator is truthy whether or not it yields, and reading it as one
    would floor every screening a caller passed one.
    """
    flags = [a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 0.0)]

    assert apply_hard_rules(0.0, flags, iter(())) == 0.0
    assert apply_hard_rules(0.0, flags, (i for i in ())) == 0.0


def test_an_empty_flag_list_is_answered_with_the_sum_it_carries():
    """No finding fired, so no rule overrode, whatever the score was."""
    assert apply_hard_rules(0.0, [], HARD_FAIL_IDS) == 0.0
    assert apply_hard_rules(51.25, [], HARD_FAIL_IDS) == 51.25


def test_the_floor_is_configurable_and_the_default_is_only_a_default():
    """A floor a deployment retunes is one argument, and the file's default is
    what a caller gets when it names none.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]

    assert apply_hard_rules(0.0, flags, HARD_FAIL_IDS, floor=70.0) == 70.0
    assert apply_hard_rules(0.0, flags, HARD_FAIL_IDS, floor=MAX_SCORE) == (
        MAX_SCORE
    )
    assert apply_hard_rules(80.0, flags, HARD_FAIL_IDS, floor=70.0) == 80.0


def test_a_floor_at_the_ends_of_the_scale_is_answered_rather_than_refused():
    """Both ends are levels, and one of them is a no-op that is still a level:
    a floor of `MIN_SCORE` cannot lower a score and must not be mistaken for a
    missing one.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]

    assert apply_hard_rules(41.0, flags, HARD_FAIL_IDS, floor=MIN_SCORE) == 41.0
    assert apply_hard_rules(0.0, flags, HARD_FAIL_IDS, floor=MIN_SCORE) == (
        MIN_SCORE
    )


def test_the_answer_is_a_float_and_the_flags_and_the_table_are_not_amended():
    """A flag is evidence and a table is 6.5's record of a decision."""
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]
    before = [dataclasses.replace(flag) for flag in flags]
    table = set(HARD_FAIL_IDS)
    table_before = set(table)

    answer = apply_hard_rules(0.0, flags, table)

    assert type(answer) is float
    assert flags == before
    assert table == table_before


# --- refusals reach the caller rather than becoming a number ----------------


@pytest.mark.parametrize(
    "score",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="boolean"),
        pytest.param("0.0", id="text"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
    ],
)
def test_a_score_that_is_not_a_number_stops_the_floor(score):
    """A `nan` is the quiet one: every comparison against it is false, so a
    floor written as a comparison would leave it exactly as it was.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]

    with pytest.raises(FlagValueError):
        apply_hard_rules(score, flags, HARD_FAIL_IDS)


@pytest.mark.parametrize(
    "floor",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="boolean"),
        pytest.param("90", id="text"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(-0.5, id="below-the-scale"),
        pytest.param(MAX_SCORE + 0.5, id="above-the-scale"),
    ],
)
def test_a_floor_off_the_scale_is_refused(floor):
    """A floor above the top of the scale is one no answer can reach, and one
    below the bottom is a no-op that reads as a configured override.  Either
    way the deployment believes it has said something it has not.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]

    with pytest.raises(FlagValueError) as raised:
        apply_hard_rules(0.0, flags, HARD_FAIL_IDS, floor=floor)

    assert "floor" in str(raised.value)


@pytest.mark.parametrize(
    "table",
    [
        pytest.param(None, id="none"),
        pytest.param(flag_ids.WATCHLIST_HIT, id="a-bare-string"),
        pytest.param(b"WATCHLIST_HIT", id="bytes"),
        pytest.param(7, id="not-a-collection"),
    ],
)
def test_a_table_that_is_not_a_collection_of_ids_is_refused(table):
    """A bare id string iterated is characters that match no id, so the mistake
    would answer every screening with the sum it already had and never raise.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0)]

    with pytest.raises(FlagValueError) as raised:
        apply_hard_rules(0.0, flags, table)

    assert "hard_fail_ids" in str(raised.value)


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(object(), id="no-attributes"),
        pytest.param(None, id="none"),
        pytest.param(DraftFinding, id="a-class-not-a-record"),
        pytest.param(DraftFinding(id=None), id="a-null-id"),
    ],
)
def test_a_flag_with_no_usable_id_is_refused_rather_than_passed_over(record):
    """Every flag in the list is read, so a broken one is refused even when an
    override has already been found: passing over it is the same
    skip-the-bad-flag fault 7.3 and 7.5 refuse.
    """
    flags = [a_flag(flag_ids.WATCHLIST_HIT, 0.0), record]

    with pytest.raises(FlagValueError) as raised:
        apply_hard_rules(0.0, flags, HARD_FAIL_IDS)

    assert "id" in str(raised.value)


def test_a_refusal_never_quotes_the_value_it_refused():
    """`D6`'s rule, held over a score and a floor: the message names the field
    and the type, because the value is where something off a document arrives.
    """
    with pytest.raises(FlagValueError) as raised:
        apply_hard_rules("FICTITIOUS<<JANE", [], HARD_FAIL_IDS)

    assert "FICTITIOUS" not in str(raised.value)
    assert "score" in str(raised.value)


# --- what the module may import --------------------------------------------


def test_the_module_reaches_no_further_than_the_error_and_the_id_reader():
    """Walked rather than grepped, and the claim is the absence of an import.

    **The load-bearing one is `app.pipeline`.**  Which rules override is 6.5's
    table in the runner, and this module is handed the ids rather than
    importing them: the pipeline depends on this package's records and a floor
    that reached back into it would make the engine depend on the tier that
    feeds it.  One standard-library module and one project module, both the
    refusal machinery and nothing else.
    """
    tree = ast.parse(
        pathlib.Path(hard_rules.__file__).read_text(encoding="utf-8")
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

    assert imported == {"app.risk.flags"}
    assert standard == {"math", "collections.abc"}


def test_the_module_exports_the_floor_the_bounds_and_the_one_function():
    """`math`, `Iterable` and the reader are used, not re-exported."""
    assert hard_rules.__all__ == [
        "DEFAULT_HARD_FAIL_FLOOR",
        "MAX_SCORE",
        "MIN_SCORE",
        "apply_hard_rules",
    ]


def test_the_module_reads_no_clock_and_no_randomness():
    """`D12`'s rule extends here: a score must not depend on when it ran, and
    a floor that depended on it would be a different screening tomorrow's."""
    tree = ast.parse(
        pathlib.Path(hard_rules.__file__).read_text(encoding="utf-8")
    )
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


def test_the_module_sums_nothing_and_reads_no_file():
    """7.5's sum is the only place the terms are added, and 7.2's loader is the
    only place a weightset is opened.
    """
    source = pathlib.Path(hard_rules.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert not called & {"sum", "fsum", "open", "max", "min"}
    assert "weightset" not in source.lower().replace("weightset the", "")
