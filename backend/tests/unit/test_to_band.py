"""34 is the last ``low`` score, 69 is the last ``review`` one, and 0 and 100
are where an officer expects them to be.

Task 7.9 asks for ``to_band(score) -> "low" | "review" | "high"`` with the six
boundary values tested explicitly, and the table below is that claim as
written: 0, 34, 35, 69, 70 and 100.  **The task's six numbers cannot tell an
inclusive boundary from an exclusive one** -- 34 is ``low`` under ``<=`` and
under ``<`` is 33 that ends ``low`` -- so the table is held here as the floor
of the claim and the rest of this file is what pins the two edges exactly:

- the switches sit at :data:`~app.risk.config.LOW_MAX` and
  :data:`~app.risk.config.REVIEW_MAX` and nowhere else, checked at a
  ten-billionth either side of each so a ``<`` and a ``<=`` cannot both pass;
- the three bands are three contiguous ranges of the scale, disjoint, total,
  and never lowering as the score rises;
- every answer is one of ``flags.WEIGHT_BANDS`` and the module returns no
  fourth name -- held by a walk over its own ``return`` statements;
- a score that is not a number is refused, and the ``nan`` is the case that
  makes that load-bearing rather than tidy;
- a *row's* band in ``v1.yaml`` and the band a *score* reads are two
  questions, and the committed file already answers them differently;
- and the pipeline's own arithmetic reaches all three bands, so this is the
  question 7.5, 7.6 and 7.7 are composing into rather than a table of six
  numbers nothing produces.

**Both thresholds are read off ``app.risk.config`` and neither is retyped**
into an expectation, the way every other Part 7 suite does.  The task's own
digits appear once, in the table, and the two tests that follow hold them to
the committed pair so the table cannot drift from ``D28``.
"""

import ast
import pathlib

import pytest

from app.risk import bands as bands_module
from app.risk import flag_ids
from app.risk.bands import to_band
from app.risk.clamp import clamp_score
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import EvidenceFlag, FlagValueError, WEIGHT_BANDS
from app.risk.hard_rules import (
    DEFAULT_HARD_FAIL_FLOOR,
    MAX_SCORE,
    MIN_SCORE,
    apply_hard_rules,
)
from app.risk.scoring import weighted_sum
from app.risk.weightsets.loader import load_weightset

#: The package this module lives in, walked twice below: the three band names
#: are written in this one file, and nowhere else in the package.
RISK_PACKAGE = pathlib.Path(bands_module.__file__).resolve().parent

#: The one file allowed to answer a band, named rather than filtered out by a
#: string comparison on the path.
THIS_MODULE = pathlib.Path(bands_module.__file__).resolve()

#: The three bands in the order a score reads them, which is the order
#: ``tasks.md`` and the abstract name them.  Held to ``WEIGHT_BANDS`` below
#: rather than assumed, so a fourth name fails here as well.
SEVERITY_ORDER = ("low", "review", "high")

#: The task's own table.  **The two thresholds are the task's whole numbers
#: written out once, here**, and the test under it holds them to the committed
#: pair: everywhere else in this file the thresholds are read off
#: ``app.risk.config`` so a retune of ``D28``'s pair moves these claims with
#: it.  A ``<=`` boundary puts 34 in ``low`` and 35 in ``review`` because 34
#: is ``LOW_MAX`` -- the *maximum* of ``low`` -- and not the minimum of the
#: band above it.
TASK_BOUNDARY_TABLE = (
    pytest.param(0, "low", id="zero-the-bottom-of-the-scale"),
    pytest.param(34, "low", id="thirty-four-the-top-of-low"),
    pytest.param(35, "review", id="thirty-five-the-first-review"),
    pytest.param(69, "review", id="sixty-nine-the-top-of-review"),
    pytest.param(70, "high", id="seventy-the-first-high"),
    pytest.param(100, "high", id="a-hundred-the-top-of-the-scale"),
)

#: The grid the sweep below reads.  A quarter of a point puts both thresholds
#: exactly on grid lines -- 34 is index 136, 69 is index 276 -- and a step
#: that is a power of two keeps every line exact, so the highest score reading
#: ``low`` is ``LOW_MAX`` itself rather than 33.999999999999996.
SWEEP_STEP = 0.25

#: How far either side of a threshold the inclusive comparison is measured.
#: Comfortably above the ulp of both numbers -- about 7e-15 at 34 -- and
#: small enough that the three points are the same reading to an officer.
EPSILON = 1e-9

#: A field-shaped box: two lines of pixels, clockwise from the top left.
FIELD_BOX = ((10, 20), (110, 20), (110, 40), (10, 40))

#: The two ``low`` rows in ``v1.yaml``, 15 points each.  Two of them at full
#: strength are 30 and stay ``low``; three are 45 and cross, which is the
#: arithmetic ``D28`` gives for placing ``LOW_MAX`` at 34.
LOW_PILE = (flag_ids.OCR_LOW_CONFIDENCE, flag_ids.LAYOUT_DEVIATION)

#: The heaviest rows in the file, 65 points each.  One of them is 7.6's floor
#: shape and none is a hard fail in this suite: ``HARD_FAIL_IDS`` below names
#: only the date-of-birth digit, the way 7.7's suite stands in for the family.
HIGH_PILE = (
    flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH,
    flag_ids.WATCHLIST_HIT,
)

#: A 30-point row the file bands ``review``, which is the committed example
#: of a row's band and a score's band being two questions.
REVIEW_ROW = flag_ids.DATE_NOT_YET_VALID

#: Which rules override, passed in rather than imported: that is 6.5's answer
#: and ``D26``'s decision is that ``app.risk`` is asked rather than told.
HARD_FAIL_IDS = frozenset({flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH})


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


def a_pile(flag_ids_in_order, count, value=1.0):
    """``count`` full-strength findings, cycling the ids it is given."""
    return [
        a_flag(flag_ids_in_order[index % len(flag_ids_in_order)], value)
        for index in range(count)
    ]


def the_score(flags):
    """7.5's sum, read off the committed weightset."""
    return weighted_sum(flags, load_weightset())


def the_band(flags):
    """The end-to-end reading: 7.5's sum, 7.6's floor, 7.7's clamp, then this."""
    total = apply_hard_rules(the_score(flags), flags, HARD_FAIL_IDS)
    return to_band(clamp_score(total))


def the_scale(step=SWEEP_STEP):
    """Every grid point on ``[MIN_SCORE, MAX_SCORE]``, bottom to top."""
    steps = round((MAX_SCORE - MIN_SCORE) / step)
    return [MIN_SCORE + index * step for index in range(steps + 1)]


def _source(path):
    return path.read_text(encoding="utf-8")


def _modules_beside_this_one():
    """Every module in the package except this one, in a stable order."""
    return sorted(
        path.resolve()
        for path in RISK_PACKAGE.rglob("*.py")
        if path.resolve() != THIS_MODULE
    )


def _band_names_returned_by_this_module():
    """The band names ``to_band`` can answer with, read off its own returns."""
    tree = ast.parse(_source(THIS_MODULE))
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        for inner in ast.walk(node.value):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                names.add(inner.value)
    return names


# --- the task's own table, tested as written ------------------------------


@pytest.mark.parametrize(("score", "band"), TASK_BOUNDARY_TABLE)
def test_the_task_names_every_boundary_and_this_is_what_each_one_reads(
    score, band
):
    """The headline claim: 0, 34, 35, 69, 70 and 100, band by band.

    **The first and last are the ends of the scale and not chosen numbers.**
    0 is 7.5's empty sum, the reading of every genuine traveller on whom
    nothing fired, and 100 is the top 7.7 holds a pile of strong findings to;
    both are asserted against the scale's own ends below so a retune of the
    scale cannot leave a stale 0 and 100 answering in its place.
    """
    assert to_band(score) == band


def test_the_two_numbers_in_the_table_are_the_committed_pair():
    """The table's digits are ``LOW_MAX`` and ``REVIEW_MAX``, and held to them.

    This is what stops the six numbers above from becoming a second copy of
    the pair: they are written as whole numbers because the task names them
    as such, and this asserts they are the same two values the rest of the
    file bands against.  A retune of ``D28``'s pair moves every other claim
    in this suite and fails this one, rather than leaving the task's table
    answering about a pair nobody ships.
    """
    assert LOW_MAX == 34
    assert REVIEW_MAX == 69
    assert to_band(LOW_MAX) == to_band(34) == "low"
    assert to_band(REVIEW_MAX) == to_band(69) == "review"


def test_the_ends_of_the_scale_are_where_the_task_says_they_are():
    """0 and 100, read off 7.6 rather than typed, and neither is a no-op.

    7.8's suite already holds ``MIN_SCORE < LOW_MAX < REVIEW_MAX < MAX_SCORE``;
    this is that ordering made observable, because a pair that left the bottom
    of the scale above the first threshold would send every clean document to
    a second officer, and one that left the top of the scale below the second
    would make a certain forgery arguable.
    """
    assert (MIN_SCORE, MAX_SCORE) == (0.0, 100.0)
    assert MIN_SCORE < LOW_MAX < REVIEW_MAX < MAX_SCORE
    assert to_band(MIN_SCORE) == "low"
    assert to_band(MAX_SCORE) == "high"


# --- where the two switches actually are -----------------------------------


@pytest.mark.parametrize(
    ("edge", "at_or_below", "above"),
    [
        pytest.param(LOW_MAX, "low", "review", id="the-low-boundary"),
        pytest.param(REVIEW_MAX, "review", "high", id="the-review-boundary"),
    ],
)
def test_each_threshold_is_the_last_score_of_its_own_band(
    edge, at_or_below, above
):
    """Inclusive below, exclusive above, measured a ten-billionth out.

    **This is the assertion the task's six numbers cannot make.**  The table
    above passes identically under ``<`` and ``<=``, under ``>`` and ``>=``,
    and under a table that switched at 33 and 70 instead -- which is what
    ``D28``'s names refuse and what would move 34 into ``review`` and send a
    score an officer has been shown a reason for into a different queue.

    Three points per edge rather than two, because a boundary drawn *between*
    two representable floats would be invisible to a test that only asked
    about the threshold itself.
    """
    assert to_band(edge - EPSILON) == at_or_below
    assert to_band(edge) == at_or_below
    assert to_band(edge + EPSILON) == above


def test_the_three_bands_are_three_contiguous_ranges_of_the_scale():
    """A partition, not three overlapping intervals: total, exclusive, ordered.

    Read off the sweep rather than asserted case by case, and the three
    properties are the ones an officer's reading depends on:

    - **total** -- every score on the scale answers, and answers with one of
      the three legal names, so no screening is left unbanded;
    - **ordered** -- the answers never fall in severity as the score rises,
      so appending evidence cannot make a document read safer, which is 7.7's
      claim one step further on;
    - **contiguous** -- the answers in score order are a run of ``low``, then
      a run of ``review``, then a run of ``high``, with each run ending at a
      threshold.  Three interleaved ranges would satisfy total and ordered
      while banding a document differently from one a point heavier.
    """
    assert set(SEVERITY_ORDER) == set(WEIGHT_BANDS)
    answers = [(score, to_band(score)) for score in the_scale()]
    severity = {band: index for index, band in enumerate(SEVERITY_ORDER)}

    assert all(band in WEIGHT_BANDS for _, band in answers)

    readings = [severity[band] for _, band in answers]
    assert readings == sorted(readings)
    assert readings[0] == severity["low"]
    assert readings[-1] == severity["high"]

    assert min(
        score for score, answer in answers if answer == "review"
    ) <= LOW_MAX + SWEEP_STEP
    assert max(
        score for score, answer in answers if answer == "low"
    ) == LOW_MAX
    assert max(
        score for score, answer in answers if answer == "review"
    ) == REVIEW_MAX

    switches = [
        current_score
        for (_, previous_band), (current_score, current_band) in zip(
            answers, answers[1:]
        )
        if previous_band != current_band
    ]
    assert len(switches) == 2
    assert switches == [LOW_MAX + SWEEP_STEP, REVIEW_MAX + SWEEP_STEP]


def test_the_answer_is_a_name_and_never_a_number_or_a_label_of_another_shape():
    """A ``str`` from the committed vocabulary, whatever integer it was given.

    ``WEIGHT_BANDS`` is a frozenset, so membership needs a hashable value, and
    the band is compared against strings on a dashboard, in a response body
    and in 7.10's assertion about ``review``.  The weights in ``v1.yaml`` are
    YAML integers while the thresholds are floats, so a score reaching this
    as an ``int`` is the ordinary case rather than an edge.
    """
    for score in (0, 34, 35, 69, 70, 100, 35.0, 70.0, -0.0):
        answer = to_band(score)

        assert answer in WEIGHT_BANDS
        assert type(answer) is str


def test_asking_twice_is_asking_once():
    """No state, no clock, no file: the same score bands the same way."""
    for score in (0.0, 12.5, LOW_MAX, REVIEW_MAX, 99.9, 195.0):
        once = to_band(score)

        assert to_band(score) == to_band(score)
        assert to_band(score) == once


# --- a row's band and a score's band are two questions ----------------------


def test_no_single_finding_reads_as_high_on_its_own():
    """``D21`` read through this module rather than as arithmetic.

    ``D21``'s claim is that the heaviest weight in the file is 65, so no one
    finding can reach High and High means corroboration or 7.6's floor.  Held
    here by asking the question the claim is about, against every row in
    ``v1.yaml``, so a retune that made one flag decisive fails rather than
    leaving the claim true only in a comment.
    """
    weightset = load_weightset()

    for flag_id, row in weightset.flags.items():
        assert to_band(row["weight"]) != "high", flag_id


def test_a_rows_own_band_is_never_softer_than_the_band_its_weight_reads_as():
    """The two bands are different questions, and the gap has a direction.

    A row's ``band`` is the severity class a *weight* sits in -- what one
    finding is worth saying on its own -- and this answers for a *sum*.
    **The committed file already shows them apart, and only in one
    direction**: a row's band is never softer than the band its own weight
    reads as, and it is often harder.  A 30-point row is banded ``review``
    there, because a dated irregularity is worth a human's attention by
    itself, while 30 points *on a document* reads ``low``, because the same
    points beside a clean document are a document with one question on it.

    The direction is the whole discipline.  A module that derived the answer
    from the weightset would have to pick one of the two questions and would
    be wrong about the other -- and a weightset that read the other way round
    would be a ruleset calling its own heaviest findings ``low``.
    """
    weightset = load_weightset()
    severity = {band: index for index, band in enumerate(SEVERITY_ORDER)}
    stricter = {
        flag_id: (row["weight"], row["band"], to_band(row["weight"]))
        for flag_id, row in weightset.flags.items()
        if severity[row["band"]] > severity[to_band(row["weight"])]
    }

    for flag_id, row in weightset.flags.items():
        assert severity[row["band"]] >= severity[to_band(row["weight"])], flag_id

    assert stricter
    assert weightset.flags[REVIEW_ROW]["band"] == "review"
    assert to_band(weightset.flags[REVIEW_ROW]["weight"]) == "low"
    assert stricter[REVIEW_ROW] == (30, "review", "low")


# --- the bands the pipeline actually reaches -------------------------------


@pytest.mark.parametrize(
    ("flags", "expected_score", "expected_band"),
    [
        pytest.param((), 0.0, "low", id="a-clean-document"),
        pytest.param(a_pile(LOW_PILE, 2), 30.0, "low", id="two-low-findings"),
        pytest.param(a_pile(LOW_PILE, 3), 45.0, "review", id="three-low-findings"),
        pytest.param(
            a_pile((REVIEW_ROW,), 1), 30.0, "low", id="a-review-row-at-thirty"
        ),
        pytest.param(
            a_pile((flag_ids.DATE_ISSUE_AFTER_EXPIRY,), 1),
            40.0,
            "review",
            id="one-review-row",
        ),
        pytest.param(a_pile(HIGH_PILE, 1), 65.0, "review", id="one-high-row"),
        pytest.param(
            a_pile(HIGH_PILE, 2), 130.0, "high", id="two-high-rows-past-the-top"
        ),
    ],
)
def test_the_engine_asks_this_question_of_its_own_arithmetic(
    flags, expected_score, expected_band
):
    """All three bands are reached by 7.5 to 7.7 together, not only by hand.

    **The scores are asserted as measured facts of the committed file** before
    the band is, so a retune of a weight fails here saying which sum moved
    rather than reporting a band for a sum this file no longer produces.  The
    three cases that carry the claim are the clean document at 0, the heaviest
    single finding at 65 reading ``review`` (``D21``), and two of them
    summing to 130, held to the top of the scale by 7.7 and reading ``high``.

    No flag in this table is in ``HARD_FAIL_IDS``, so 7.6's floor is a no-op
    here and the band is the sum's own.
    """
    rows = load_weightset().flags
    weights = [rows[flag.id]["weight"] for flag in flags]

    assert sum(weights) == expected_score
    assert the_score(flags) == expected_score
    assert the_band(flags) == expected_band


def test_a_hard_fail_exits_to_high_and_never_to_review():
    """Worked example A, and the abstract's "exits directly to High Risk".

    One broken printed digit, measured at ``0.0`` so it carries no strength
    of its own: the sum is ``0.0``, 7.6's floor lifts it, 7.7 holds it, and
    the answer is ``high``.  **The floor is what decides this and not the
    sum**, which is the reason the floor is a floor -- a band computed from the
    sum alone would read a certain MRZ integrity failure as ``low``.
    """
    hard_fail = [a_flag(flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH, 0.0)]

    assert the_score(hard_fail) == 0.0
    assert to_band(the_score(hard_fail)) == "low"
    assert DEFAULT_HARD_FAIL_FLOOR > REVIEW_MAX
    assert the_band(hard_fail) == "high"


# --- refusals reach the caller rather than becoming a band -----------------


@pytest.mark.parametrize(
    "score",
    [
        pytest.param(None, id="none"),
        pytest.param(True, id="boolean-true-is-one"),
        pytest.param(False, id="boolean-false-is-zero"),
        pytest.param("100", id="text"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param(object(), id="an-object"),
    ],
)
def test_a_score_that_is_not_a_finite_number_is_refused(score):
    """A ``nan`` is the one that matters, and the reason is arithmetic.

    Every comparison against a ``nan`` is false, so a band written as two
    comparisons falls through both of them and answers ``high`` -- asserted
    here rather than described, because it is the whole reason 7.6's
    validation is shared into this module instead of a number being asked
    whether it is a number.  A ``bool`` is refused for the neighbouring
    reason: ``True`` is ``1``, which is a real score reading ``low``.
    """
    if isinstance(score, float) and score != score:
        assert not score <= LOW_MAX
        assert not score <= REVIEW_MAX

    with pytest.raises(FlagValueError):
        to_band(score)


def test_a_refusal_never_quotes_the_value_it_refused():
    """``D6``'s rule, held over a score: the message names the field and the
    type, because the value is where something off a document arrives."""
    with pytest.raises(FlagValueError) as raised:
        to_band("FICTITIOUS<<JANE")

    assert "FICTITIOUS" not in str(raised.value)
    assert "score" in str(raised.value)


def test_a_score_off_the_scale_is_banded_and_the_clamp_is_who_puts_it_there():
    """Nothing is clamped here and nothing is refused for being far out.

    7.7's clamp is what holds a score to the scale, and a caller that skipped
    it has been handed the wrong number rather than a new case to handle.  The
    claim is that skipping it changes nothing an officer reads: a score below
    the scale reads ``low`` either way and a score above it reads ``high``
    either way, so the two questions compose without merging -- the reason
    7.6 and 7.7 kept answering in either order.

    The two scores are real ones: 195 is three ``high`` findings at full
    strength, and a negative score is not reachable today but 7.14's bounded
    history term is the first thing that can produce one.
    """
    for score in (195.0, 1000.0, -12.5, -1e9):
        assert to_band(score) == to_band(clamp_score(score))

    assert to_band(195.0) == "high"
    assert to_band(-12.5) == "low"
    assert isinstance(to_band(195.0), str)


# --- what the module may read and return -----------------------------------


def test_the_three_names_it_answers_with_are_the_committed_vocabulary():
    """Walked over this module's own ``return`` statements, not over a list.

    ``flags.WEIGHT_BANDS`` is where a flag's ``weight_band`` is checked, and
    this is where a document's band is decided, so the three names are one
    vocabulary written in two places and held to each other.  The walk reads
    every string this module can hand back: a fourth name, a renamed band or a
    label like ``"Low Risk"`` -- 23.5's spelling to render rather than one to
    band in -- fails here rather than at a dashboard.
    """
    assert _band_names_returned_by_this_module() == set(WEIGHT_BANDS)


def test_no_other_risk_module_answers_a_band_from_a_score():
    """One question, one module, the way 7.5, 7.6 and 7.7 are held.

    A second module returning one of these three names would be free to answer
    a different question from the same vocabulary the moment ``D28``'s pair
    was retuned, and a screening would be banded by whichever it reached
    first.  The walk is over every module in the package but this one.
    """
    for path in _modules_beside_this_one():
        tree = ast.parse(_source(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            for inner in ast.walk(node.value):
                if (
                    isinstance(inner, ast.Constant)
                    and isinstance(inner.value, str)
                    and inner.value in WEIGHT_BANDS
                ):
                    raise AssertionError(
                        f"{path.name} answers a band of its own"
                    )


def test_the_function_asks_about_a_score_and_nothing_else():
    """One argument, named, with no default and nothing else to pass in.

    The shape is the claim: a ``to_band(score, weightset)`` would be banding
    a document against a ruleset rather than reading a finished number, and a
    ``band=`` default would let a caller be told the answer rather than ask
    for it.  ``D6``'s one-way dependency is held by the import walk below;
    this holds that nothing reaches the engine's own state.
    """
    tree = ast.parse(_source(THIS_MODULE))
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef)
    ]

    assert [function.name for function in functions] == ["to_band"]
    arguments = functions[0].args
    assert [argument.arg for argument in arguments.args] == ["score"]
    assert arguments.posonlyargs == []
    assert arguments.defaults == []
    assert arguments.kwonlyargs == []
    assert arguments.vararg is None
    assert arguments.kwarg is None


def test_both_edges_are_read_by_name_and_nothing_is_compared_against_a_literal():
    """The two thresholds and the two thresholds only.

    ``test_band_thresholds.py`` walks the whole package and fails on ``34`` or
    ``69`` written into a comparison; this is the other side of that walk, on
    the one module that has to compare against them: every comparison here
    reads a ``Name``, the names are the committed pair and the score, and no
    number is written out.  **A third edge is the quieter failure** -- a
    comparison against ``MAX_SCORE`` or a ``0`` would re-derive a boundary
    this package already owns, so the set of names is held exactly.
    """
    tree = ast.parse(_source(THIS_MODULE))
    comparisons = [node for node in ast.walk(tree) if isinstance(node, ast.Compare)]

    assert comparisons
    for node in comparisons:
        for operand in [node.left, *node.comparators]:
            assert isinstance(operand, ast.Name), ast.dump(operand)

    compared = {
        operand.id
        for node in comparisons
        for operand in [node.left, *node.comparators]
    }
    assert compared == {"total", "LOW_MAX", "REVIEW_MAX"}


def test_the_module_writes_neither_threshold_of_its_own():
    """``D28``'s pair is 7.8's and is read, on the reason 7.5 and 7.6 give."""
    tree = ast.parse(_source(THIS_MODULE))
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert not assigned & {"LOW_MAX", "REVIEW_MAX"}


def test_the_module_reaches_only_the_thresholds_and_the_one_score_validator():
    """Walked rather than grepped, and the claim is the reach itself.

    Two imports are the whole of it: 7.8's pair and 7.6's ``_score``, which
    is 7.7's precedent -- one validation of a score for the package, shared
    rather than written a second time, because two answers to one question is
    how they drift apart.  No standard library is reached, and
    ``app.pipeline`` is absent on ``D6``'s one-way dependency: a band
    computed by asking a rule which tier it came from would be a band that
    moved with the cascade.
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

    assert imported == {"app.risk.config", "app.risk.hard_rules"}
    assert standard == set()


def test_the_module_exports_the_one_name_the_task_names():
    """``to_band`` and nothing else: the two thresholds are 7.8's and the
    validator is 7.6's, and both are read from where they live."""
    assert bands_module.__all__ == ["to_band"]


def test_the_module_reads_no_clock_no_randomness_and_opens_no_file():
    """``D12``'s rule extends here: a band that depended on when it ran would
    be a screening nobody could replay, and one that read a file could change
    under a running service with nothing recording it."""
    tree = ast.parse(_source(THIS_MODULE))
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)

    # The only call in the module is 7.6's shared validator: no clock, no
    # randomness, no file, and nothing that could be added here without this
    # failing rather than arriving silently in a screening.
    assert called == {"_score"}


def test_the_module_reaches_no_attribute_and_so_reads_no_flag_or_weightset():
    """A score in and a name out: no record, no ruleset, no object at all.

    7.3 refuses an id with no weight rather than scoring it as zero, and 7.4
    refuses an unmeasured value, so a band that read a flag would be a second
    place the two gates could be asked.  ``to_band`` is asked about the
    finished number and the number is all it sees: the walk holds that not one
    attribute of any object is read here, so ``weightset.flags`` and
    ``flag.value`` cannot be added without this failing.
    """
    tree = ast.parse(_source(THIS_MODULE))
    attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }

    assert attributes == set()
