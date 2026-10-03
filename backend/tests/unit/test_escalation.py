"""14.6 -- ``R1`` inside the ambiguity band escalates; at each edge or outside it does not.

The headline is the task's own verification, and the sweep beside it is the
other half of the task: inside, at each of the two edges, and outside.  The
rest hold the band's shape -- closed at its own top, open at its bottom, the
way 7.9 draws every band -- show the caller's band and not a constant here
decides, keep ``None`` a tier that has not run rather than a score of zero,
and hold that an escalation is a sentence on the context rather than a bool
that could disagree with one.  D109 has the reasoning.

14.7's tests follow beside them: a document type or an issuing state on a
configurable watchlist escalates, an unclaimed value is not a hit, and the
two ends of the watchlist do not read one another.  D110 has the reasoning.

14.8's follow after those: one id draws the same way every time it is asked,
and over ten thousand ids the share drawn is the rate the draw was built
with.  D111 has the reasoning.

14.9 follow those: a checkpoint running at full depth escalates every
screening it is handed, and every other depth escalates none.  D112 has
the reasoning.
"""

#: The modules that would let a check draw a number or tell the time.  No
#: trigger may reach one, so one screen sees all three of them.
NO_CLOCK_OR_DRAWS = frozenset(
    {
        "calendar",
        "datetime",
        "json",
        "os",
        "pathlib",
        "random",
        "secrets",
        "time",
        "tomllib",
        "yaml",
    }
)

import ast
import dataclasses
import datetime
import inspect
import math
import pathlib
import uuid

import pytest

from app.pipeline import escalation, orchestrator
from app.risk.bands import to_band
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import FlagValueError

AmbiguityBand = escalation.AmbiguityBand
DeepAuditDraw = escalation.DeepAuditDraw
HighRiskProfile = escalation.HighRiskProfile
check_ambiguity = escalation.check_ambiguity
check_deep_audit = escalation.check_deep_audit
check_full_depth = escalation.check_full_depth
check_high_risk_profile = escalation.check_high_risk_profile
default_band = escalation.default_band
default_draw = escalation.default_draw
default_profile = escalation.default_profile

SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")
REFERENCE_DATE = datetime.date(2026, 10, 2)

#: A frame standing in for the working one; nothing here reads its pixels.
PAGE = object()

#: A score plainly between the two committed edges, not derived from either.
INSIDE = 45.0

#: The sum an empty Tier 1 writes, which 14.5 makes an answer rather than an
#: absence -- and which sits below the band rather than inside it.
NO_TRIGGER = 0.0

#: Two secrets no deployment has, so a test can show the first is in the draw.
SECRET = b"14.8-drishti-test-secret"
OTHER_SECRET = b"14.8-drishti-other-secret"

#: The rate the corpus is measured at, and the size of the corpus.
MEASURED_RATE = 0.05
CORPUS = 10_000

#: The draw the 14.8 tests measure, built from the two above.
MEASURED = DeepAuditDraw(MEASURED_RATE, SECRET)


def _imported_modules():
    """The top-level modules :mod:`escalation` imports, for a scan to read."""
    tree = ast.parse(pathlib.Path(escalation.__file__).read_text(encoding="utf-8"))
    modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    return modules | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def _first_drawn(rate=MEASURED_RATE, secret=SECRET):
    """The first id of the corpus a draw at ``rate`` escalates.

    Found with the draw itself, so this only locates an id for a test about
    what an escalation *writes*; whether the draw is right is
    ``test_the_draw_rate_is_the_share_of_a_corpus_it_escalates``'s claim.
    """
    draw = DeepAuditDraw(rate, secret)
    for index in range(CORPUS):
        screening_id = uuid.UUID(int=index)
        if draw.draws(screening_id):
            return screening_id
    raise AssertionError(f"no id of the corpus drew at {rate:g}")


def _first_undrawn(rate=MEASURED_RATE, secret=SECRET):
    """The first id of the corpus a draw at ``rate`` leaves alone."""
    draw = DeepAuditDraw(rate, secret)
    for index in range(CORPUS):
        screening_id = uuid.UUID(int=index)
        if not draw.draws(screening_id):
            return screening_id
    raise AssertionError(f"every id of the corpus drew at {rate:g}")


def _context(**overrides):
    """A context carrying the constants above, with ``overrides`` applied."""
    stated = {
        "screening_id": SCREENING_ID,
        "document_type": "passport",
        "image": PAGE,
        "reference_date": REFERENCE_DATE,
        "depth_mode": orchestrator.STANDARD,
    }
    stated.update(overrides)
    return orchestrator.ScreeningContext(**stated)


def test_an_r1_inside_the_band_escalates():
    """The task's own verification, on the shipped band."""
    context = _context(r1=INSIDE)

    assert check_ambiguity(context) is True
    assert context.escalated is True
    assert len(context.escalations) == 1


@pytest.mark.parametrize(
    ("r1", "escalates"),
    [
        pytest.param(LOW_MAX - 1.0, False, id="below-the-band"),
        pytest.param(LOW_MAX, False, id="at-the-lower-edge"),
        pytest.param(LOW_MAX + 0.5, True, id="just-inside-the-lower-edge"),
        pytest.param(INSIDE, True, id="inside"),
        pytest.param(REVIEW_MAX, True, id="at-the-upper-edge"),
        pytest.param(REVIEW_MAX + 1.0, False, id="above-the-band"),
    ],
)
def test_the_band_is_closed_at_its_top_and_open_at_its_bottom(r1, escalates):
    """Each edge is the top of its own band, which is what ``_max`` says.

    ``D28``'s pair is uncalibrated, so every score here is read off it: a
    ``34`` or a ``69`` written into this file would place the edges correctly
    today and be wrong the day the pair was retuned, with no name to grep for.
    """
    context = _context(r1=r1)

    assert check_ambiguity(context) is escalates
    assert context.escalated is escalates
    assert len(context.escalations) == (1 if escalates else 0)


def test_an_r1_outside_the_band_escalates_nothing():
    """Outside is an answer, and it is written the same way ``None`` is."""
    context = _context(r1=REVIEW_MAX + 20.0)

    assert check_ambiguity(context) is False
    assert context.escalations == []
    assert context.escalated is False


def test_a_tier_1_that_ran_and_found_nothing_is_not_ambiguous():
    """``0.0`` is a score below the band, not the missing score of a tier."""
    context = _context(r1=NO_TRIGGER)

    assert check_ambiguity(context) is False
    assert context.escalations == []


def test_a_tier_1_that_has_not_run_is_not_a_score_to_read():
    """``None`` is an absence, so there is nothing for a band to answer about."""
    context = _context()

    assert context.r1 is None
    assert check_ambiguity(context) is False
    assert context.escalations == []


def test_the_band_the_caller_hands_over_is_the_one_that_decides():
    """The record decides, so a retuned band moves both edges at once."""
    context = _context(r1=INSIDE)

    assert check_ambiguity(context, band=AmbiguityBand(10.0, 20.0)) is False
    assert context.escalations == []
    assert check_ambiguity(context, band=AmbiguityBand(0.0, INSIDE)) is True
    assert len(context.escalations) == 1


def test_the_default_band_is_read_off_the_committed_thresholds_per_call():
    """No number of the band's is written here, and none is frozen at import."""
    assert default_band() == AmbiguityBand(LOW_MAX, REVIEW_MAX)
    context = _context(r1=INSIDE)

    check_ambiguity(context)

    assert f"{LOW_MAX:g}" in context.escalations[0]
    assert f"{REVIEW_MAX:g}" in context.escalations[0]


@pytest.mark.parametrize(
    "score", [0.0, LOW_MAX, LOW_MAX + 0.5, REVIEW_MAX, REVIEW_MAX + 0.5, 100.0]
)
def test_the_default_band_reads_the_scores_7_9_reads_as_review(score):
    """The escalation band and 7.9's middle band are one answer, not two.

    They are not the same question -- one is a configurable range on an
    unclamped partial score, the other is what an officer reads off a total --
    so the suite holds them together rather than deriving one from the other.
    """
    assert default_band().contains(score) == (to_band(score) == "review")


def test_the_escalation_is_a_reason_and_not_a_bool_a_caller_can_disagree_with():
    """``escalated`` is read off the reasons, so a second trigger cannot be lost."""
    context = _context(r1=INSIDE)

    check_ambiguity(context)
    context.escalations.append("the issuing state is on the profile watchlist")

    assert len(context.escalations) == 2
    assert context.escalated is True
    assert all(isinstance(reason, str) for reason in context.escalations)


def test_an_escalation_hard_fails_nothing_and_changes_no_score():
    """It is a routing decision, not 14.4's stop and not 7.5's arithmetic."""
    context = _context(r1=INSIDE)

    check_ambiguity(context)

    assert context.hard_fail_reason is None
    assert context.r1 == INSIDE
    assert context.flags == []


def test_a_context_starts_with_no_escalation_and_holds_its_own_list():
    """``D104``'s per-instance accumulator, on the third list the record grew."""
    first = _context(r1=INSIDE)
    second = _context()

    check_ambiguity(first)

    assert first.escalated is True
    assert second.escalated is False
    assert second.escalations == []


@pytest.mark.parametrize(
    "edges",
    [
        pytest.param((34.0, 34.0), id="a-band-one-point-wide-is-no-band"),
        pytest.param((69.0, 34.0), id="the-edges-the-wrong-way-round"),
        pytest.param((0.0, True), id="a-bool-for-the-top"),
        pytest.param((0.0, "69"), id="a-string-for-the-top"),
        pytest.param((0.0, float("nan")), id="a-nan-for-the-top"),
        pytest.param((0.0, float("inf")), id="an-infinity-for-the-top"),
    ],
)
def test_a_band_that_could_not_be_read_as_a_range_is_refused(edges):
    with pytest.raises(FlagValueError):
        AmbiguityBand(*edges)


@pytest.mark.parametrize(
    "r1",
    [
        pytest.param(True, id="a-bool"),
        pytest.param("45", id="a-string"),
        pytest.param(float("nan"), id="a-nan"),
        pytest.param(float("inf"), id="an-infinity"),
        pytest.param(object(), id="an-object"),
    ],
)
def test_an_r1_no_band_can_be_read_against_is_refused(r1):
    """A ``nan`` compares false against both edges, so a band written as two
    comparisons would answer ``False`` and quietly call it a clean page."""
    with pytest.raises(FlagValueError):
        check_ambiguity(_context(r1=r1))


def test_the_refusal_names_the_field_and_never_the_score():
    with pytest.raises(FlagValueError) as refusal:
        check_ambiguity(_context(r1="45"))

    assert "r1" in str(refusal.value)


def test_a_band_that_is_not_the_record_is_refused():
    """A pair written where the record is wanted is a wiring mistake."""
    with pytest.raises(FlagValueError) as refusal:
        check_ambiguity(_context(r1=INSIDE), band=(LOW_MAX, REVIEW_MAX))

    assert "AmbiguityBand" in str(refusal.value)
    assert "tuple" in str(refusal.value)


def test_the_check_reaches_no_clock_and_no_randomness():
    """The same page escalates the same way on every run, so nothing is drawn."""
    tree = ast.parse(pathlib.Path(escalation.__file__).read_text(encoding="utf-8"))
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

    assert not modules & {"time", "random", "secrets", "datetime", "calendar"}


def test_the_check_is_named_beside_the_three_triggers_still_to_come():
    """14.7 to 14.9 add their own beside this one rather than renaming it."""
    assert escalation.CHECK_NAME == "ambiguity"

# --- 14.7: the high-risk profile ------------------------------------------------

#: The profile 14.7's tests read: one document type and one issuing state.
WATCHED = HighRiskProfile(document_types={"visa"}, issuing_states={"ind"})

#: The claims of an ordinary passport, which this profile does not list.
GENUINE = {"document_type": "passport", "issuing_state": "usa"}


def test_a_document_type_on_the_profile_escalates():
    """The task's own verification, on the document-type half of the watchlist."""
    context = _context(document_type="visa", issuing_state="usa")

    assert check_high_risk_profile(context, profile=WATCHED) is True
    assert context.escalated is True
    assert len(context.escalations) == 1
    assert "visa" in context.escalations[0]


def test_an_issuing_state_on_the_profile_escalates():
    """The state half alone escalates, on the code the document printed."""
    context = _context(document_type="passport", issuing_state="IND")

    assert check_high_risk_profile(context, profile=WATCHED) is True
    assert len(context.escalations) == 1
    assert "IND" in context.escalations[0]


def test_a_document_matching_both_ends_escalates_once():
    """One trigger writes one reason: the type is named and the state is not."""
    context = _context(document_type="visa", issuing_state="IND")

    assert check_high_risk_profile(context, profile=WATCHED) is True
    assert len(context.escalations) == 1
    assert "visa" in context.escalations[0]
    assert "IND" not in context.escalations[0]


def test_a_document_off_both_ends_escalates_nothing():
    """Off the lists is an answer, and it is written the way ``None`` is."""
    context = _context(**GENUINE)

    assert check_high_risk_profile(context, profile=WATCHED) is False
    assert context.escalations == []
    assert context.escalated is False


@pytest.mark.parametrize(
    "claimed",
    [
        pytest.param(
            {"document_type": None, "issuing_state": None}, id="nothing-claimed"
        ),
        pytest.param(
            {"document_type": "passport", "issuing_state": None},
            id="no-state-claimed",
        ),
        pytest.param(
            {"document_type": None, "issuing_state": "usa"}, id="no-type-claimed"
        ),
        pytest.param(
            {"document_type": "passport", "issuing_state": "usa"},
            id="both-claimed-and-neither-listed",
        ),
    ],
)
def test_an_unclaimed_value_is_not_a_hit(claimed):
    """``None`` is an absence, and this watchlist reads type OR state."""
    context = _context(**claimed)

    assert check_high_risk_profile(context, profile=WATCHED) is False
    assert context.escalations == []


@pytest.mark.parametrize(
    ("profile", "claimed", "escalates"),
    [
        pytest.param(
            HighRiskProfile(document_types={"visa"}),
            {"issuing_state": "ind"},
            False,
            id="a-type-list-does-not-watch-states",
        ),
        pytest.param(
            HighRiskProfile(issuing_states={"ind"}),
            {"document_type": "visa"},
            False,
            id="a-state-list-does-not-watch-types",
        ),
        pytest.param(
            HighRiskProfile(issuing_states={"ind"}),
            {"issuing_state": "ind"},
            True,
            id="the-state-list-alone-still-escalates",
        ),
    ],
)
def test_the_two_ends_of_the_watchlist_are_independent(profile, claimed, escalates):
    """A document type is not an issuing state, so neither list reads the other."""
    context = _context(**{"document_type": "passport", "issuing_state": "usa", **claimed})

    assert check_high_risk_profile(context, profile=profile) is escalates
    assert len(context.escalations) == (1 if escalates else 0)


def test_the_callers_profile_is_the_one_that_decides():
    """The record decides, so a retuned watchlist moves both ends at once."""
    context = _context(document_type="visa", issuing_state="usa")

    assert check_high_risk_profile(context, profile=HighRiskProfile()) is False
    assert context.escalations == []
    assert check_high_risk_profile(context, profile=WATCHED) is True
    assert len(context.escalations) == 1


@pytest.mark.parametrize(
    ("claimed", "listed", "matches"),
    [
        pytest.param("IND", {"ind"}, True, id="an-mrz-code-prints-itself-in-caps"),
        pytest.param("ind", {"IND"}, True, id="a-listed-entry-need-not-be-in-caps"),
        pytest.param("Passport", {"passport"}, True, id="a-type-in-either-case"),
        pytest.param(" ind ", {"ind"}, True, id="a-claim-padded-by-a-reader"),
        pytest.param("USA", {"ind"}, False, id="another-state-is-not-this-one"),
    ],
)
def test_the_watchlist_reads_a_claim_the_way_a_document_prints_it(
    claimed, listed, matches
):
    """Both ends compare case-folded and trimmed, so one spelling is compared."""
    profile = HighRiskProfile(issuing_states=listed)

    assert profile.matches(None, claimed) is matches


def test_the_entries_are_folded_to_one_spelling_and_held_frozen():
    """What a caller lists and what the record holds cannot disagree later."""
    profile = HighRiskProfile(document_types={" Visa ", "Passport"})

    assert profile.document_types == frozenset({"visa", "passport"})
    assert isinstance(profile.document_types, frozenset)


def test_a_built_profile_cannot_be_edited_after_it_is_built():
    """A watchlist a later stage could edit would be a second answer per run."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        WATCHED.document_types = frozenset({"passport"})


def test_the_shipped_profile_names_nothing_and_escalates_nothing():
    """The abstract names the trigger but never the list, so none is shipped."""
    assert escalation.SHIPPED_DOCUMENT_TYPES == frozenset()
    assert escalation.SHIPPED_ISSUING_STATES == frozenset()
    assert default_profile() == HighRiskProfile()
    context = _context(document_type="visa", issuing_state="ind")

    assert check_high_risk_profile(context) is False
    assert context.escalations == []


def test_the_shipped_profile_is_built_per_call_from_the_committed_lists():
    """No file and no environment, so a deployment cannot retune it quietly."""
    assert default_profile() is not default_profile()
    assert default_profile() == HighRiskProfile(
        escalation.SHIPPED_DOCUMENT_TYPES, escalation.SHIPPED_ISSUING_STATES
    )


def test_a_profile_escalation_appends_beside_the_ambiguity_reason():
    """D109's two triggers keep their own sentences and neither is lost."""
    context = _context(document_type="visa", issuing_state="usa", r1=INSIDE)

    check_ambiguity(context)
    check_high_risk_profile(context, profile=WATCHED)

    assert len(context.escalations) == 2
    assert context.escalated is True


def test_a_profile_escalation_hard_fails_nothing_and_changes_no_score():
    """It is a routing decision, not 14.4's stop and not 7.5's arithmetic."""
    context = _context(document_type="visa", issuing_state="usa", r1=NO_TRIGGER)

    check_high_risk_profile(context, profile=WATCHED)

    assert context.hard_fail_reason is None
    assert context.r1 == NO_TRIGGER
    assert context.flags == []


def test_a_profile_that_is_not_the_record_is_refused():
    """A bare set of values is a wiring mistake, not a watchlist."""
    with pytest.raises(FlagValueError) as refusal:
        check_high_risk_profile(
            _context(document_type="visa"), profile=frozenset({"visa"})
        )

    assert "HighRiskProfile" in str(refusal.value)
    assert "frozenset" in str(refusal.value)


@pytest.mark.parametrize(
    ("claimed", "field"),
    [
        pytest.param({"document_type": 7}, "document_type", id="a-number-for-the-type"),
        pytest.param(
            {"issuing_state": object()}, "issuing_state", id="an-object-for-the-state"
        ),
    ],
)
def test_a_claim_no_watchlist_can_be_read_against_is_refused(claimed, field):
    """A claim that is neither ``None`` nor a string is refused, not compared."""
    with pytest.raises(FlagValueError) as refusal:
        check_high_risk_profile(_context(**claimed), profile=WATCHED)

    assert field in str(refusal.value)


@pytest.mark.parametrize(
    ("entries", "field"),
    [
        pytest.param(
            {"document_types": {7}}, "document_types", id="a-number-for-a-type"
        ),
        pytest.param(
            {"issuing_states": {None}}, "issuing_states", id="none-for-a-state"
        ),
        pytest.param(
            {"issuing_states": {" "}}, "issuing_states", id="a-blank-for-a-state"
        ),
    ],
)
def test_an_entry_no_watchlist_can_hold_is_refused(entries, field):
    """An entry that could not be compared is refused when the list is built."""
    with pytest.raises(FlagValueError) as refusal:
        HighRiskProfile(**entries)

    assert field in str(refusal.value)


def test_the_three_checks_are_named_apart():
    """14.8 has followed 14.7's prefixed shape rather than renaming these."""
    assert escalation.CHECK_NAME == "ambiguity"
    assert escalation.HIGH_RISK_PROFILE_CHECK_NAME == "high_risk_profile"
    assert escalation.DEEP_AUDIT_CHECK_NAME == "deep_audit"


def test_the_profile_check_reaches_no_file_no_clock_and_no_randomness():
    """A watchlist read from disk could be retuned with nothing recording it.

    14.6's own test holds the modules that would draw or tell the time; this
    one adds the two a configured watchlist would have to be read through.
    """
    assert not _imported_modules() & NO_CLOCK_OR_DRAWS


def test_the_draw_is_an_hmac_and_reaches_neither_a_clock_nor_a_file():
    """HMAC is what makes the draw unpredictable, and nothing else is asked.

    A ``random`` here would answer a different way the second time, which is
    the one property the draw has to have and the one it loses first.  The
    scan reads the whole module, because all three triggers share the file.
    """
    modules = _imported_modules()

    assert {"hashlib", "hmac"} <= modules
    assert not modules & NO_CLOCK_OR_DRAWS


def test_a_drawn_screening_escalates():
    """The task's own trigger, on a draw that names a real rate."""
    context = _context(screening_id=_first_drawn())

    assert check_deep_audit(context, draw=MEASURED) is True
    assert context.escalated is True
    assert len(context.escalations) == 1


def test_an_undrawn_screening_escalates_nothing():
    """A case the draw leaves alone is written the way ``None`` is."""
    context = _context(screening_id=_first_undrawn())

    assert check_deep_audit(context, draw=MEASURED) is False
    assert context.escalations == []
    assert context.escalated is False


def test_the_same_screening_id_always_draws_the_same_outcome():
    """The task's own first claim: asked twice, a case is drawn or it is not.

    Both sides of 200 ids are seen in this one run first, so a draw that
    answered the same way every time cannot pass it by drawing nobody.
    """
    ids = [uuid.UUID(int=index) for index in range(200)]
    first = {screening_id: MEASURED.draws(screening_id) for screening_id in ids}

    assert set(first.values()) == {True, False}
    for screening_id, drawn in first.items():
        assert MEASURED.draws(screening_id) is drawn
        assert DeepAuditDraw(MEASURED_RATE, SECRET).draws(screening_id) is drawn


@pytest.mark.parametrize("rate", [0.05, 0.02])
def test_the_draw_rate_is_the_share_of_a_corpus_it_escalates(rate):
    """The task's own second claim: the distribution over 10 000 ids.

    A Bernoulli share of ``n`` ids sits ``sqrt(n * p * (1 - p))`` from its
    mean, so the band is five of those rather than a count this one secret
    happens to produce today.
    """
    draw = DeepAuditDraw(rate, SECRET)

    drawn = sum(draw.draws(uuid.UUID(int=index)) for index in range(CORPUS))
    sigma = math.sqrt(CORPUS * rate * (1.0 - rate))

    assert abs(drawn - rate * CORPUS) <= 5.0 * sigma


@pytest.mark.parametrize("rate", [0.0, 1.0])
def test_the_edges_of_a_rate_are_exact_and_need_no_corpus(rate):
    """Zero draws nobody and one draws everybody, so neither needs a sample."""
    draw = DeepAuditDraw(rate, SECRET)
    outcomes = [draw.draws(uuid.UUID(int=index)) for index in range(200)]

    assert all(outcomes) is (rate == 1.0)
    assert any(outcomes) is (rate == 1.0)


def test_a_second_secret_draws_the_same_corpus_differently():
    """The secret is in the draw, which is what an adversary cannot guess."""
    mine = DeepAuditDraw(0.5, SECRET)
    theirs = DeepAuditDraw(0.5, OTHER_SECRET)

    outcomes = {
        (mine.draws(uuid.UUID(int=index)), theirs.draws(uuid.UUID(int=index)))
        for index in range(200)
    }

    assert len(outcomes) == 4


def test_the_draw_asks_for_nothing_the_cascade_has_not_produced():
    """The id alone decides it, where 14.6 needs ``R1`` and 14.7 a claim."""
    context = _context(screening_id=_first_drawn())

    assert context.r1 is None
    assert context.issuing_state is None
    assert check_deep_audit(context, draw=MEASURED) is True
    assert context.r1 is None


def test_a_deep_audit_escalation_hard_fails_nothing_and_changes_no_score():
    """It is a routing decision, like the two triggers before it."""
    context = _context(screening_id=_first_drawn(), r1=NO_TRIGGER)

    check_deep_audit(context, draw=MEASURED)

    assert context.hard_fail_reason is None
    assert context.r1 == NO_TRIGGER
    assert context.flags == []


def test_all_three_triggers_keep_their_own_sentences():
    """D109's one-sentence-per-trigger rule holds for the third as well."""
    context = _context(
        screening_id=_first_drawn(),
        r1=INSIDE,
        document_type="visa",
        issuing_state="usa",
    )

    check_ambiguity(context)
    check_high_risk_profile(context, profile=WATCHED)
    check_deep_audit(context, draw=MEASURED)

    assert len(context.escalations) == 3
    assert context.escalated is True


def test_the_reason_names_the_rate_and_quotes_neither_the_id_nor_the_secret():
    """The rate is the policy an officer reads; the secret is not theirs."""
    drawn = _first_drawn()
    context = _context(screening_id=drawn)

    check_deep_audit(context, draw=MEASURED)

    (reason,) = context.escalations
    assert f"{MEASURED_RATE:g}" in reason
    assert str(drawn) not in reason
    assert SECRET.decode() not in reason


def test_the_shipped_rate_is_zero_and_draws_nobody():
    """The abstract names the trigger and never the rate, so none is shipped."""
    assert escalation.SHIPPED_DEEP_AUDIT_RATE == 0.0
    assert default_draw(SECRET) == DeepAuditDraw(0.0, SECRET)
    context = _context()

    assert check_deep_audit(context, draw=default_draw(SECRET)) is False
    assert context.escalations == []


def test_the_shipped_draw_is_built_per_call_from_the_committed_rate():
    """No file and no environment, so a deployment cannot retune it quietly."""
    assert default_draw(SECRET) is not default_draw(SECRET)


def test_a_built_draw_cannot_be_edited_after_it_is_built():
    """A rate a later stage could edit would be a second answer per run."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        MEASURED.rate = 1.0


def test_a_draw_that_is_not_the_record_is_refused():
    """A bare pair of rate and secret is a wiring mistake, not a draw."""
    with pytest.raises(FlagValueError) as refusal:
        check_deep_audit(_context(), draw=(MEASURED_RATE, SECRET))

    assert "DeepAuditDraw" in str(refusal.value)
    assert "tuple" in str(refusal.value)


@pytest.mark.parametrize(
    "rate",
    [
        pytest.param(-0.01, id="below-zero"),
        pytest.param(1.01, id="above-one"),
        pytest.param("0.5", id="a-string"),
        pytest.param(None, id="nothing"),
        pytest.param(True, id="a-bool"),
    ],
)
def test_a_rate_no_draw_can_be_read_as_is_refused(rate):
    """A rate that is not a probability is refused when the draw is built."""
    with pytest.raises(FlagValueError) as refusal:
        DeepAuditDraw(rate, SECRET)

    assert "rate" in str(refusal.value)


@pytest.mark.parametrize(
    "secret",
    [
        pytest.param("", id="an-empty-string"),
        pytest.param("a-string-not-bytes", id="a-string"),
        pytest.param(None, id="nothing"),
        pytest.param(7, id="a-number"),
    ],
)
def test_a_secret_no_draw_can_be_keyed_by_is_refused(secret):
    """A key that is not bytes is refused rather than coerced into some."""
    with pytest.raises(FlagValueError) as refusal:
        DeepAuditDraw(MEASURED_RATE, secret)

    assert "secret" in str(refusal.value)


def test_a_bytearray_secret_is_folded_to_the_bytes_it_holds():
    """The one container a caller hands over is read, not refused."""
    draw = DeepAuditDraw(MEASURED_RATE, bytearray(SECRET))

    assert draw.secret == SECRET


@pytest.mark.parametrize(
    "screening_id",
    [
        pytest.param("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f", id="a-printed-id"),
        pytest.param(7, id="a-number"),
        pytest.param(None, id="nothing"),
    ],
)
def test_a_screening_id_no_draw_can_be_read_is_refused(screening_id):
    """The context refuses one already; a direct caller gets the same answer."""
    with pytest.raises(FlagValueError) as refusal:
        MEASURED.draws(screening_id)

    assert "screening_id" in str(refusal.value)


# --- 14.9: the full-depth mode flag---------------------------------------

#: The depth that escalates every screening, and the one that never does.
FULL = orchestrator.FULL_DEPTH
ORDINARY = orchestrator.STANDARD

#: What a screening row records about the photograph instead, which this
#: trigger must never read: D104 holds the two vocabularies apart.
CAPTURE_MODES = frozenset({"photo", "scan"})


def test_a_full_depth_screening_always_escalates():
    """The task own verification: full depth escalates whatever it holds."""
    context = _context(depth_mode=FULL)

    assert check_full_depth(context) is True
    assert len(context.escalations) == 1


def test_full_depth_escalates_a_screening_nothing_else_would():
    """The point of the trigger: a clean, undrawn, unclaimed case still goes."""
    context = _context(
        depth_mode=FULL,
        screening_id=_first_undrawn(),
        r1=NO_TRIGGER,
        document_type="passport",
        issuing_state="usa",
    )

    assert check_ambiguity(context) is False
    assert check_high_risk_profile(context, profile=WATCHED) is False
    assert check_deep_audit(context, draw=MEASURED) is False
    assert context.escalations == []

    assert check_full_depth(context) is True
    assert len(context.escalations) == 1


@pytest.mark.parametrize(
    "r1",
    [
        pytest.param(None, id="before-tier-1"),
        pytest.param(NO_TRIGGER, id="a-clean-tier-1"),
        pytest.param(INSIDE, id="inside-the-band"),
        pytest.param(100.0, id="the-worst-score-there-is"),
    ],
)
def test_full_depth_escalates_whatever_r1_holds(r1):
    """A score is a reason, and this one is a reason that does not read it."""
    context = _context(depth_mode=FULL, r1=r1)

    assert check_full_depth(context) is True


@pytest.mark.parametrize(
    "claimed",
    [
        pytest.param(
            {"document_type": "visa", "issuing_state": "ind"}, id="watched"
        ),
        pytest.param(
            {"document_type": None, "issuing_state": None}, id="unclaimed"
        ),
    ],
)
def test_full_depth_escalates_whatever_the_document_claims(claimed):
    """The other triggers claims do not decide this one either."""
    context = _context(depth_mode=FULL, **claimed)

    assert check_full_depth(context) is True


def test_full_depth_escalates_every_id_of_the_corpus():
    """Always is a claim about every screening, not about this one."""
    context = _context(depth_mode=FULL)

    for index in range(200):
        context.screening_id = uuid.UUID(int=index)
        assert check_full_depth(context) is True

    assert len(context.escalations) == 200


def test_a_standard_screening_is_never_escalated_by_the_mode():
    """Ordinary depth escalates nothing even when the other three all fire."""
    context = _context(
        depth_mode=ORDINARY,
        screening_id=_first_drawn(),
        r1=INSIDE,
        document_type="visa",
        issuing_state="ind",
    )

    check_ambiguity(context)
    check_high_risk_profile(context, profile=WATCHED)
    check_deep_audit(context, draw=MEASURED)

    assert check_full_depth(context) is False
    assert len(context.escalations) == 3


@pytest.mark.parametrize("depth_mode", orchestrator.DEPTH_MODES)
def test_the_trigger_escalates_for_full_depth_and_no_other_depth(depth_mode):
    """A third depth must not read as standard, nor standard as nothing."""
    context = _context(depth_mode=depth_mode)

    assert check_full_depth(context) is (depth_mode == FULL)


def test_the_mode_is_read_off_the_context_and_is_not_a_parameter():
    """A mode handed in could answer for a screening that is not this one."""
    assert list(inspect.signature(check_full_depth).parameters) == ["context"]


def test_a_mode_nothing_recognises_is_refused_by_the_context_already():
    """The record owns the vocabulary; a second refusal is a second opinion."""
    with pytest.raises(orchestrator.ContextValueError) as refusal:
        _context(depth_mode="deep")

    assert "depth_mode" in str(refusal.value)


def test_the_full_depth_trigger_needs_nothing_the_cascade_has_produced():
    """Like the draw, it is answerable before any stage has run."""
    context = _context(depth_mode=FULL)

    assert context.r1 is None
    assert context.flags == []
    assert check_full_depth(context) is True


def test_a_full_depth_escalation_hard_fails_nothing_and_changes_no_score():
    """D108 rule holds for the fourth trigger as for the first three."""
    context = _context(depth_mode=FULL, r1=NO_TRIGGER)

    assert check_full_depth(context) is True

    assert context.hard_fail_reason is None
    assert context.r1 == NO_TRIGGER
    assert context.flags == []


def test_the_reason_names_the_mode_and_quotes_nothing_else():
    """The mode is the whole reason; a claim or an id belongs in no such line."""
    context = _context(
        depth_mode=FULL,
        document_type="passport",
        issuing_state="usa",
        screening_id=_first_drawn(),
    )

    check_full_depth(context)

    (reason,) = context.escalations
    assert "full-depth" in reason
    assert "passport" not in reason
    assert "usa" not in reason
    assert str(context.screening_id) not in reason


def test_the_mode_answers_the_same_way_every_time_it_is_asked():
    """Asked twice it says yes twice; the gate is where once belongs."""
    context = _context(depth_mode=FULL)

    assert check_full_depth(context) is True
    assert check_full_depth(context) is True
    assert len(context.escalations) == 2


def test_the_fourth_trigger_is_named_beside_the_first_three():
    """14.9 prefixed its own as 14.7 and 14.8 did, and renamed none of them."""
    names = (
        escalation.CHECK_NAME,
        escalation.HIGH_RISK_PROFILE_CHECK_NAME,
        escalation.DEEP_AUDIT_CHECK_NAME,
        escalation.FULL_DEPTH_CHECK_NAME,
    )

    assert names == (
        "ambiguity",
        "high_risk_profile",
        "deep_audit",
        "full_depth",
    )
    assert len(set(names)) == len(names)


def test_the_fourth_trigger_is_exported_under_its_own_name():
    """A trigger nothing can reach is one nobody has wired to the gate."""
    assert "FULL_DEPTH_CHECK_NAME" in escalation.__all__
    assert "check_full_depth" in escalation.__all__
    assert escalation.check_full_depth is check_full_depth


def test_the_fourth_trigger_never_reads_a_capture_mode():
    """D104 two vocabularies stay disjoint where the trigger reads one."""
    assert CAPTURE_MODES & {
        escalation.CHECK_NAME,
        escalation.HIGH_RISK_PROFILE_CHECK_NAME,
        escalation.DEEP_AUDIT_CHECK_NAME,
        escalation.FULL_DEPTH_CHECK_NAME,
    } == set()
    assert CAPTURE_MODES & set(orchestrator.DEPTH_MODES) == set()


def test_the_fourth_trigger_reaches_no_clock_no_draw_and_no_file():
    """The mode is read off the record, so nothing could retune it here."""
    assert not _imported_modules() & NO_CLOCK_OR_DRAWS


def test_all_four_triggers_keep_their_own_sentences():
    """D109 one sentence per trigger holds for the fourth as well."""
    context = _context(
        depth_mode=FULL,
        screening_id=_first_drawn(),
        r1=INSIDE,
        document_type="visa",
        issuing_state="usa",
    )

    check_ambiguity(context)
    check_high_risk_profile(context, profile=WATCHED)
    check_deep_audit(context, draw=MEASURED)
    check_full_depth(context)

    assert len(context.escalations) == 4
    assert len(set(context.escalations)) == 4
    assert context.escalated is True
