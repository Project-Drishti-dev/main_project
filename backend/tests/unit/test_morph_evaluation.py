"""27.11 -- missed attacks and wrongly flagged genuine photographs, or why not.

The abstract fixes this module pair of numbers: "attacks missed versus genuine
photographs wrongly flagged", following the NIST FATE MORPH approach.  This
box has none of what they are read over -- no morph or deepfake corpus, and no
set of genuine photographs -- so the first group of tests holds the default run
to saying so rather than printing a zero, which is a rate a detector achieves.

The second group is the part the task names twice: honesty about stubs.  The
only classifiers behind Part 15's two seams are heuristics carrying ``is_stub``,
so a run over them produces real fractions whose numbers are a heuristic's, and
the harness has to say which kind of number it is holding.

The rest is the arithmetic, driven through stand-in classifiers so the harness
is proved to compute both numbers rather than only to decline to.  The two
that matter most are the honesty pair: a region no classifier could read, and an
ensemble carrying one stand-in, since each would otherwise reach a table
reading as a real detector's measurement.
"""

import io

import pytest

from app.pipeline.tier2 import deepfake, morph
from tests.fixtures import morph_evaluation as me

#: The regions most tests hand their stand-ins.  Strings, because nothing here
#: measures a pixel.
CLEAN = "clean"
MORPHED = "morphed"
FAKED = "faked"
UNREADABLE = "unreadable"


class FixedMorph(morph.MorphClassifier):
    """A stand-in morph classifier scoring each named region a chosen level.

    ``suspect`` is read against :data:`~app.pipeline.tier2.morph.SUSPECT_LEVEL`
    exactly as Part 15's own stand-in does, so a test wanting a boundary case
    can ask for the level itself and mean it.
    """

    def __init__(self, levels=None, refuse=(), version="model-v1", stub=False):
        """Hold the levels, the regions to refuse, and what this claims to be."""
        self._levels = {} if levels is None else dict(levels)
        self._refuse = tuple(refuse)
        self.model_version = version
        self.is_stub = stub
        self.seen = []

    def classify(self, region):
        """Answer ``region``, recording that it was read, or refusing it."""
        self.seen.append(region)
        if region in self._refuse:
            raise morph.MorphError("region holds no portrait outline")
        score = self._levels.get(region, 0.0)
        return morph.MorphVerdict(
            score=score,
            frequency=score,
            boundary=score,
            suspect=score >= morph.SUSPECT_LEVEL,
        )


class FixedDeep(deepfake.DeepfakeClassifier):
    """A stand-in deepfake classifier scoring each named region a chosen level."""

    def __init__(self, levels=None, refuse=(), version="model-v1", stub=False):
        """Hold the levels, the regions to refuse, and what this claims to be."""
        self._levels = {} if levels is None else dict(levels)
        self._refuse = tuple(refuse)
        self.model_version = version
        self.is_stub = stub
        self.seen = []

    def classify(self, region):
        """Answer ``region``, recording that it was read, or refusing it."""
        self.seen.append(region)
        if region in self._refuse:
            raise deepfake.DeepfakeError("region carries no power to share")
        score = self._levels.get(region, 0.0)
        return deepfake.DeepfakeVerdict(
            score=score, flat=score, suspect=score >= deepfake.SUSPECT_LEVEL
        )


def same(levels=None, refuse=(), **labels):
    """One classifier per declared kind, scoring the same regions alike."""
    return (
        FixedMorph(levels, refuse=refuse, **labels),
        FixedDeep(levels, refuse=refuse, **labels),
    )


def measure(trials, *pair):
    """A report over ``trials``, with a stand-in classifier for each kind."""
    morph_, deep_ = pair if pair else (FixedMorph(), FixedDeep())
    return me.evaluate(trials, {"morph": morph_, "deepfake": deep_})


def rows(text):
    """The printed table as a dict keyed by its first column."""
    return {
        line.split()[0]: line.split()
        for line in text.splitlines()
        if line.split() and not line.startswith("  -") and line[0].isalpha()
    }


# --- The shape of the table, before any data arrives --------------------------------


def test_the_two_columns_are_the_two_the_abstract_names():
    heading = me.table(me.evaluate()).splitlines()[0]
    assert heading.split()[0:2] == ["attack", "missed"]
    assert "genuine flagged" in heading


def test_every_declared_attack_kind_has_a_row_before_any_trial_exists():
    """The kinds are the table's shape, so they print empty rather than absent."""
    assert me.ATTACK_KINDS == ("morph", "deepfake")
    printed = rows(me.table(me.evaluate()))
    for kind in me.ATTACK_KINDS:
        assert kind in printed
    assert me.ALL in printed


# --- Honest absence -----------------------------------------------------------------


def test_the_default_run_measures_no_rate_and_says_why():
    """The task's verify: the scaffolding runs and says so."""
    default = me.evaluate()
    assert default.source == me.NOT_MEASURED
    assert default.overall.missed.ratio is None
    assert default.overall.flagged.ratio is None


def test_a_missing_corpus_is_named():
    assert me.evaluate().reasons == (me.NO_TRIALS,)


def test_the_table_prints_every_reason_it_carries():
    printed = me.table(me.evaluate())
    assert "no rate was measured" in printed
    for reason in me.evaluate().reasons:
        assert me.REASONS[reason] in printed


def test_an_empty_rate_prints_as_a_dash_and_not_as_a_zero():
    """A zero is a rate a detector achieves; an empty cell must not read like one."""
    printed = rows(me.table(me.evaluate()))
    assert printed[me.ALL][1:3] == ["--", "--"]
    assert printed["morph"][1:3] == ["--", "--"]


def test_a_missing_dataset_is_not_reported_as_a_zero_rate():
    assert me.evaluate().overall.missed == me.Rate(0, 0)
    assert me.evaluate().overall.missed.ratio is None


def test_a_kind_with_no_classifier_is_named_and_contributes_no_number():
    """The classifier column is the second word for which kind is unwired."""
    measured = me.evaluate(
        (me.Trial(CLEAN),), {"morph": FixedMorph(), "deepfake": None}
    )
    assert me.NO_CLASSIFIER in measured.reasons
    assert measured.by_kind["deepfake"].missed == me.Rate(0, 0)
    assert measured.by_kind["deepfake"].scored == 0


# --- Honesty about stubs, which the task names twice --------------------------------


def test_the_classifiers_this_box_has_are_the_labelled_stand_ins():
    assert isinstance(me.CONFIGURED_CLASSIFIERS["morph"], morph.MorphClassifier)
    assert isinstance(
        me.CONFIGURED_CLASSIFIERS["deepfake"], deepfake.DeepfakeClassifier
    )
    assert all(c.is_stub for c in me.CONFIGURED_CLASSIFIERS.values())


def test_a_run_over_stand_ins_says_stub_and_not_measured():
    """A stand-in's fractions are real, and they are still a heuristic's numbers."""
    stubbed = measure((me.Trial(MORPHED, "morph"),), *same({MORPHED: 0.9}, stub=True))
    assert stubbed.source == me.STUBBED
    assert stubbed.overall.missed == me.Rate(0, 1)


def test_a_run_over_a_real_model_says_measured():
    assert measure(
        (me.Trial(MORPHED, "morph"),), *same({MORPHED: 0.9})
    ).source == me.MEASURED


def test_a_number_with_nothing_behind_it_is_not_measured():
    """The source describes the number shown, so an absent one is not stub."""
    empty = measure((me.Trial(MORPHED, "morph"),), *same(stub=True))
    assert empty.by_kind["deepfake"].source == me.NOT_MEASURED


def test_an_ensemble_carrying_one_stand_in_is_reported_as_stub():
    """A heuristic in an ensemble can only add flags, so it taints the whole rate."""
    mixed = measure(
        (me.Trial(MORPHED, "morph"),),
        me.MorphEnsemble(
            FixedMorph(version="arcface-morph-v1"),
            FixedMorph({MORPHED: 0.9}, version="heuristic-v0", stub=True),
        ),
        FixedDeep(),
    )
    assert mixed.by_kind["morph"].source == me.STUBBED
    assert mixed.by_kind["morph"].classifier == "arcface-morph-v1+heuristic-v0"


def test_an_ensemble_of_this_boxs_own_heuristics_is_a_stub():
    """Part 15's stand-in answers any ensemble it joins, without a pixel read."""
    assert me.MorphEnsemble(morph.HeuristicMorphClassifier()).is_stub
    assert me.DeepfakeEnsemble(
        deepfake.HeuristicDeepfakeClassifier()
    ).model_version == "heuristic-v0"

def test_an_ensemble_of_real_models_names_every_member_and_reads_measured():
    real = measure(
        (me.Trial(MORPHED, "morph"),),
        me.MorphEnsemble(FixedMorph(version="a-v1"), FixedMorph(version="b-v2")),
        FixedDeep(),
    )
    assert real.by_kind["morph"].source == me.MEASURED
    assert real.by_kind["morph"].classifier == "a-v1+b-v2"


def test_an_ensemble_answers_with_the_member_that_fires_hardest():
    """Adding a member must not weaken the ensemble."""
    ensemble = me.MorphEnsemble(
        FixedMorph({MORPHED: 0.0}, version="quiet-v1"),
        FixedMorph({MORPHED: 0.9}, version="loud-v1"),
    )
    measured = measure((me.Trial(MORPHED, "morph"),), ensemble, FixedDeep())
    assert measured.by_kind["morph"].missed == me.Rate(0, 1)


def test_an_ensemble_is_unreadable_when_any_member_cannot_read():
    """An ensemble applied to only some of its trials is a different detector."""
    ensemble = me.MorphEnsemble(
        FixedMorph(refuse=(UNREADABLE,)), FixedMorph(version="second-v1")
    )
    measured = measure((me.Trial(UNREADABLE, "morph"),), ensemble, FixedDeep())
    assert measured.by_kind["morph"].unmeasured == 1
    assert measured.by_kind["morph"].missed == me.Rate(0, 0)


def test_an_ensemble_with_no_members_is_refused():
    with pytest.raises(morph.MorphError):
        me.MorphEnsemble()
    with pytest.raises(deepfake.DeepfakeError):
        me.DeepfakeEnsemble()


def test_an_ensemble_refuses_a_member_of_the_wrong_type():
    with pytest.raises(morph.MorphError):
        me.MorphEnsemble(FixedDeep())
    with pytest.raises(deepfake.DeepfakeError):
        me.DeepfakeEnsemble(FixedMorph())


# --- The arithmetic ------------------------------------------------------------------


def test_an_attack_the_classifier_fires_on_is_not_a_miss():
    measured = measure((me.Trial(MORPHED, "morph"),), *same({MORPHED: 0.9}))
    assert measured.by_kind["morph"].missed == me.Rate(0, 1)


def test_an_attack_the_classifier_reads_nothing_found_is_a_miss():
    measured = measure((me.Trial(MORPHED, "morph"),), *same({MORPHED: 0.0}))
    assert measured.by_kind["morph"].missed == me.Rate(1, 1)


def test_a_genuine_photograph_the_classifier_fires_on_is_wrongly_flagged():
    measured = measure((me.Trial(CLEAN),), *same({CLEAN: 0.9}))
    assert measured.by_kind["morph"].flagged == me.Rate(1, 1)


def test_a_genuine_photograph_it_does_not_fire_on_is_not_wrongly_flagged():
    measured = measure((me.Trial(CLEAN),), *same({CLEAN: 0.0}))
    assert measured.by_kind["morph"].flagged == me.Rate(0, 1)


def test_the_two_numbers_are_counted_over_disjoint_sets():
    """Attacks missed and genuine flagged can never stand in for each other."""
    measured = measure(
        (me.Trial(MORPHED, "morph"), me.Trial(CLEAN)),
        *same({MORPHED: 0.0, CLEAN: 0.9}),
    )
    assert measured.by_kind["morph"].missed == me.Rate(1, 1)
    assert measured.by_kind["morph"].flagged == me.Rate(1, 1)


def test_a_number_over_nothing_counted_has_no_ratio():
    """Attacks only: the wrongly-flagged rate has no denominator to read."""
    measured = measure((me.Trial(MORPHED, "morph"),), *same({MORPHED: 0.9}))
    assert measured.by_kind["morph"].flagged.ratio is None


def test_the_kinds_share_the_genuine_photographs_and_separate_the_attacks():
    measured = measure(
        (me.Trial(MORPHED, "morph"), me.Trial(FAKED, "deepfake"), me.Trial(CLEAN)),
        *same({MORPHED: 0.9, FAKED: 0.9, CLEAN: 0.0}),
    )
    assert measured.by_kind["morph"].missed == me.Rate(0, 1)
    assert measured.by_kind["deepfake"].missed == me.Rate(0, 1)
    assert measured.by_kind["morph"].flagged == me.Rate(0, 1)
    assert measured.by_kind["deepfake"].flagged == me.Rate(0, 1)


# --- An unreadable region is an absence, not an answer --------------------------------


def test_a_region_the_classifier_refuses_enters_neither_denominator():
    """The load-bearing case: unreadable must not be scored as a miss."""
    rates = measure(
        (me.Trial(UNREADABLE, "morph"),), *same(refuse=(UNREADABLE,))
    ).by_kind["morph"]
    assert rates.missed == me.Rate(0, 0)
    assert rates.missed.ratio is None
    assert rates.unmeasured == 1
    assert rates.source == me.NOT_MEASURED


def test_an_unreadable_region_is_counted_and_the_rest_still_measured():
    rates = measure(
        (me.Trial(UNREADABLE, "morph"), me.Trial(MORPHED, "morph")),
        *same({MORPHED: 0.9}, refuse=(UNREADABLE,)),
    ).by_kind["morph"]
    assert rates.unmeasured == 1
    assert rates.missed == me.Rate(0, 1)


def test_an_unreadable_genuine_photograph_is_not_a_clean_pass():
    """Blank paper reads a flat share of 1.000, so silence is not a verdict."""
    measured = measure((me.Trial(UNREADABLE),), *same(refuse=(UNREADABLE,)))
    assert measured.overall.flagged == me.Rate(0, 0)
    assert measured.unmeasured == 1
    assert measured.scored == 0


# --- Wiring to Part 15 ----------------------------------------------------------------


def test_an_attack_goes_through_its_own_kind_classifier_only():
    """A blend is not evidence about synthetic generation."""
    morph_, deep_ = FixedMorph(), FixedDeep()
    me.evaluate(
        (me.Trial(MORPHED, "morph"),), {"morph": morph_, "deepfake": deep_}
    )
    assert morph_.seen == [MORPHED]
    assert deep_.seen == []


def test_a_genuine_photograph_goes_through_both_classifiers():
    morph_, deep_ = FixedMorph(), FixedDeep()
    me.evaluate((me.Trial(CLEAN),), {"morph": morph_, "deepfake": deep_})
    assert morph_.seen == [CLEAN] and deep_.seen == [CLEAN]


def test_the_decision_is_the_verdicts_own_suspect_and_not_a_threshold_here():
    """Part 15 reads its own line; this harness adds no bar of its own."""
    at = morph.SUSPECT_LEVEL
    measured = measure(
        (me.Trial("at", "morph"), me.Trial("below", "morph")),
        FixedMorph({"at": at, "below": at - 0.001}),
        FixedDeep(),
    )
    assert measured.by_kind["morph"].missed == me.Rate(1, 2)


def test_every_trial_is_counted_by_exactly_one_overall_denominator():
    measured = measure(
        (me.Trial(MORPHED, "morph"), me.Trial(FAKED, "deepfake"), me.Trial(CLEAN)),
        *same({MORPHED: 0.0, FAKED: 0.0, CLEAN: 0.9}),
    )
    assert measured.overall.missed.denominator == 2
    assert measured.overall.flagged.denominator == 1
    assert measured.scored == 3


# --- The overall row ------------------------------------------------------------------


def test_the_overall_row_counts_an_attack_of_either_kind():
    measured = measure(
        (me.Trial(MORPHED, "morph"), me.Trial(FAKED, "deepfake")),
        *same({MORPHED: 0.0, FAKED: 0.0}),
    )
    assert measured.overall.missed == me.Rate(2, 2)


def test_the_overall_row_flags_a_genuine_photograph_either_classifier_flagged():
    """One alert on a real traveller is one alert, whichever detector raised it."""
    measured = me.evaluate(
        (me.Trial(CLEAN),),
        {"morph": FixedMorph({CLEAN: 0.9}), "deepfake": FixedDeep()},
    )
    assert measured.overall.flagged == me.Rate(1, 1)
    assert measured.by_kind["deepfake"].flagged == me.Rate(0, 1)


def test_the_overall_row_flags_a_genuine_photograph_the_second_classifier_flagged():
    """Whichever detector raised it, the traveller is flagged once, not twice."""
    measured = me.evaluate(
        (me.Trial(CLEAN),),
        {"morph": FixedMorph(), "deepfake": FixedDeep({CLEAN: 0.9})},
    )
    assert measured.overall.flagged == me.Rate(1, 1)
    assert measured.by_kind["morph"].flagged == me.Rate(0, 1)


def test_the_overall_row_names_every_classifier_it_merged():
    """Two kinds, two versions, and no member repeated in the merged label."""
    measured = me.evaluate(
        (me.Trial(CLEAN),),
        {
            "morph": FixedMorph({CLEAN: 0.9}, version="morph-v1"),
            "deepfake": FixedDeep(version="deep-v1"),
        },
    )
    assert measured.overall.classifier == "deep-v1+morph-v1"

def test_a_genuine_photograph_one_classifier_could_not_read_still_counts():
    measured = me.evaluate(
        (me.Trial(CLEAN),),
        {"morph": FixedMorph({CLEAN: 0.9}), "deepfake": FixedDeep(refuse=(CLEAN,))},
    )
    assert measured.overall.flagged == me.Rate(1, 1)
    assert measured.by_kind["deepfake"].unmeasured == 1


# --- Refusals --------------------------------------------------------------------------


def test_an_undeclared_attack_kind_is_refused():
    with pytest.raises(ValueError, match="not a declared attack kind"):
        measure((me.Trial(CLEAN, "swap"),))


def test_an_undeclared_kind_is_refused_before_anything_is_classified():
    """A wiring mistake must not be found after half a corpus was measured."""
    morph_ = FixedMorph()
    with pytest.raises(ValueError):
        me.evaluate(
            (me.Trial(MORPHED, "morph"), me.Trial(CLEAN, "swap")),
            {"morph": morph_, "deepfake": FixedDeep()},
        )
    assert morph_.seen == []


# --- The entry point --------------------------------------------------------------------


def test_main_prints_the_table_and_the_reasons():
    out = io.StringIO()
    me.main(out)
    printed = out.getvalue()
    assert "genuine flagged" in printed
    assert me.REASONS[me.NO_TRIALS] in printed