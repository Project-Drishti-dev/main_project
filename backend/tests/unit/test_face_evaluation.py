"""27.10 -- FAR and FRR per demographic group, and the reasons there are none.

The subject of this file is that the harness reports a rate **only** where one
was read.  The abstract asks for "wrong-person-accepted and right-person-
rejected rates, tuned on held-out data and reported per demographic group",
and this box has none of the three: no demographic-labelled face dataset, no
tuned threshold, and no insightface package.  So the first group of tests
holds the default run to that -- it prints no rate, and it names every input
that was missing rather than printing a zero, which would be a rate no model
achieved.

The rest are the arithmetic and the slots, driven through a stand-in embedder
so the harness is proved to compute a rate at all rather than only to decline
to.  The two that matter most are the honesty pair: a stub and an absent model
must leave a trial out of both rates rather than scoring it as a rejection,
because a false-reject rate is a number a screening station would act on.
"""

import io

import pytest

from app.pipeline.tier1.face import Embedder, Embedding, NullEmbedder
from app.pipeline.tier1.insightface_embedder import InsightFaceEmbedder
from tests.fixtures import face_evaluation as fe

#: The threshold most tests hold trials to.  Nothing tunes it -- see
#: ``NO_THRESHOLD`` -- it is a bar the harness is handed so the arithmetic has
#: a bar at all.
BAR = 0.55

#: Two-dimensional vectors whose cosines are exactly known: the unit axes are
#: 1.0 and 0.0 apart, and (0.6, 0.8) is 0.6 off the x axis.
VECTORS = {
    "a": (1.0, 0.0),
    "b": (0.0, 1.0),
    "sideways": (0.6, 0.8),
    "opposite": (-1.0, 0.0),
}


class FixedEmbedder(Embedder):
    """A stand-in for 13.13 that answers each named crop with a known vector.

    It records what it was handed, so a test can prove both halves of a trial
    went through the seam rather than one being reused.
    """

    def __init__(self, vectors=None, stub=False):
        self._vectors = VECTORS if vectors is None else vectors
        self._stub = stub
        self.seen = []

    def is_available(self):
        return True

    def embed(self, image):
        self.seen.append(image)
        if image is None:
            return None
        if self._stub:
            return Embedding(vector=(0.0, 0.0), is_stub=True)
        return Embedding(vector=self._vectors[image])


def trial(document, live, genuine, *labels):
    """One :class:`~tests.fixtures.face_evaluation.Trial` over two named crops."""
    return fe.Trial(document, live, genuine, tuple(labels))


def report(trials, embedder=None, threshold=BAR):
    """A report over ``trials``, with a bar supplied unless a test says not to."""
    return fe.evaluate(
        trials, FixedEmbedder() if embedder is None else embedder, threshold
    )


def rows(text):
    """The printed table as a dict keyed by the first column."""
    return {
        line.split()[0]: line.split()
        for line in text.splitlines()
        if line.split() and not line.startswith("  -") and line[0].isalpha()
    }


# --- The slots, declared before any data arrives ---------------------------------


def test_the_table_carries_a_FAR_column_and_an_FRR_column():
    heading = fe.table(fe.evaluate()).splitlines()[0]
    assert heading.split()[1:3] == ["FAR", "FRR"]


def test_every_declared_slot_has_a_row_before_any_trial_exists():
    """The slots are the table's shape, so they print empty rather than absent."""
    printed = rows(fe.table(fe.evaluate()))
    for group in fe.DEMOGRAPHIC_GROUPS:
        assert str(group) in printed


def test_each_dimension_declares_an_unlabelled_slot():
    """A trial with no label must land somewhere, or the rows stop adding up."""
    for dimension in fe.DIMENSIONS:
        labels = [g.label for g in fe.DEMOGRAPHIC_GROUPS if g.dimension == dimension]
        assert labels[-1] == fe.UNLABELLED


def test_the_two_dimensions_are_the_ones_nistir_8280_reports_over():
    assert fe.DIMENSIONS == ("age_band", "gender")
    assert fe.AGE_BANDS[0] == "under-18"
    assert fe.GENDER_LABELS == ("female", "male")


def test_every_trial_lands_in_exactly_one_slot_per_dimension():
    """The per-group rows and the overall row must be over the same trials."""
    trials = [
        trial("a", "a", True, fe.Group("age_band", "18-30"), fe.Group("gender", "male")),
        trial("a", "b", False, fe.Group("age_band", "51-plus")),
        trial("a", "b", False),
    ]
    scored = report(trials)
    for dimension in fe.DIMENSIONS:
        slots = [g for g in fe.DEMOGRAPHIC_GROUPS if g.dimension == dimension]
        counted = sum(
            rates.far.denominator + rates.frr.denominator + rates.unmeasured
            for group, rates in scored.by_group.items() if group in slots
        )
        assert counted == len(trials) == scored.scored


# --- Honest absence ---------------------------------------------------------------


def test_the_default_run_measures_no_rate_and_says_why():
    """The task's verify: the scaffolding runs and says so."""
    default = fe.evaluate()
    assert default.source == fe.NOT_MEASURED
    assert default.far.ratio is None and default.frr.ratio is None


def test_a_missing_dataset_and_a_missing_threshold_are_both_named():
    """Each missing input is its own reason, not one reason for "unconfigured"."""
    assert set(fe.evaluate().reasons) == {fe.NO_TRIALS, fe.NO_THRESHOLD}


def test_the_table_prints_every_reason_it_carries():
    printed = fe.table(fe.evaluate())
    assert "no rate was measured" in printed
    for reason in fe.evaluate().reasons:
        assert fe.REASONS[reason] in printed


def test_an_empty_rate_prints_as_a_dash_and_not_as_a_zero():
    """A zero is a rate a model achieved; an empty cell must not read like one."""
    printed = rows(fe.table(fe.evaluate()))
    assert printed[fe.ALL][1:3] == ["--", "--"]
    assert printed[str(fe.Group("gender", "female"))][1:3] == ["--", "--"]


def test_a_measured_rate_prints_as_its_own_fraction():
    """Every rate shown carries the denominator it was counted over."""
    printed = rows(fe.table(report([trial("a", "a", False)])))
    assert printed[fe.ALL][1:4] == ["1/1", "--", "1"]


def test_a_missing_dataset_is_not_reported_as_a_zero_rate():
    """A zero is a rate a model achieved; an empty run has no rate at all."""
    assert fe.evaluate().far == fe.Rate(0, 0)
    assert fe.evaluate().far.ratio is None


def test_the_threshold_is_never_invented():
    """The abstract's 0.55 is its worked example's figure, not a tuned one."""
    assert fe.CONFIGURED_THRESHOLD is None
    assert fe.NO_THRESHOLD in fe.evaluate(
        (trial("a", "a", True),), FixedEmbedder()
    ).reasons


def test_the_threshold_still_reaches_thirteen_fifteens_own_check():
    """A bar is supplied to the seam, so a None one cannot slip past it."""
    from app.pipeline.tier1.face import match_score

    vector = Embedding(vector=(1.0, 0.0))
    with pytest.raises(ValueError):
        match_score(vector, vector, None)


def test_an_absent_insightface_leaves_every_trial_unmeasured():
    """``binding=None`` says the package is definitely not there, on any box."""
    absent = InsightFaceEmbedder(binding=None)
    measured = report([trial("a", "a", True)], absent)
    assert measured.source == fe.NOT_MEASURED
    assert fe.NO_MODEL in measured.reasons
    assert measured.unmeasured == 1


def test_the_null_embedder_leaves_every_trial_unmeasured():
    measured = report([trial("a", "a", True)], NullEmbedder())
    assert fe.NO_MODEL in measured.reasons
    assert measured.scored == 0


def test_a_missing_live_capture_leaves_the_trial_unmeasured():
    """Both halves are read through the seam, so either half being absent counts."""
    measured = report([trial("a", None, False)], FixedEmbedder())
    assert measured.unmeasured == 1
    assert measured.far.denominator == 0


def test_a_stub_is_reported_as_no_model_not_as_a_rejection():
    """The load-bearing case: an absent model must not become an FRR."""
    stubbed = report([trial("a", "a", True)], FixedEmbedder(stub=True))
    assert stubbed.frr == fe.Rate(0, 0)
    assert stubbed.frr.ratio is None
    assert stubbed.unmeasured == 1


def test_a_trial_nothing_could_compare_enters_neither_denominator():
    partly = report(
        [trial(None, "a", True), trial("a", "a", True)], FixedEmbedder()
    )
    assert (partly.far, partly.frr) == (fe.Rate(0, 0), fe.Rate(0, 1))
    assert partly.unmeasured == 1
    assert partly.scored == 1
    assert fe.NO_MODEL not in partly.reasons


# --- The arithmetic ---------------------------------------------------------------


def test_a_genuine_pair_over_the_bar_is_not_a_false_reject():
    assert report([trial("a", "a", True)]).frr == fe.Rate(0, 1)


def test_a_genuine_pair_under_the_bar_is_a_false_reject():
    assert report([trial("a", "b", True)]).frr == fe.Rate(1, 1)


def test_an_impostor_pair_over_the_bar_is_a_false_accept():
    assert report([trial("a", "a", False)]).far == fe.Rate(1, 1)


def test_an_impostor_pair_under_the_bar_is_not_a_false_accept():
    assert report([trial("a", "b", False)]).far == fe.Rate(0, 1)


def test_the_two_rates_are_counted_over_disjoint_trials():
    """A wrong person accepted and a right person rejected are never each other."""
    measured = report(
        [trial("a", "a", True), trial("a", "a", False), trial("a", "b", True)]
    )
    assert measured.far == fe.Rate(1, 1)
    assert measured.frr == fe.Rate(1, 2)


def test_a_rate_over_nothing_counted_has_no_ratio():
    """Genuine trials only: the false-accept rate has no denominator to read."""
    assert report([trial("a", "a", True)]).far.ratio is None


# --- Per group --------------------------------------------------------------------


def test_a_trial_lands_in_its_own_age_band_and_its_own_gender_slot():
    measured = report(
        [trial("a", "a", False, fe.Group("age_band", "31-50"), fe.Group("gender", "female"))]
    )
    by_group = measured.by_group
    assert by_group[fe.Group("age_band", "31-50")].far == fe.Rate(1, 1)
    assert by_group[fe.Group("gender", "female")].far == fe.Rate(1, 1)
    assert by_group[fe.Group("age_band", "18-30")].far.denominator == 0


def test_a_trial_with_no_label_lands_in_both_unlabelled_slots():
    measured = report([trial("a", "a", False)])
    unlabelled = fe.Group("gender", fe.UNLABELLED)
    assert measured.by_group[unlabelled].far == fe.Rate(1, 1)
    assert measured.by_group[fe.Group("age_band", fe.UNLABELLED)].far == fe.Rate(1, 1)


def test_a_group_reports_its_own_rate_and_not_the_overall_one():
    """A group that matches nothing must not inherit the overall rate."""
    measured = report([
        trial("a", "a", False, fe.Group("gender", "male")),
        trial("a", "b", False, fe.Group("gender", "female")),
    ])
    assert measured.far == fe.Rate(1, 2)
    assert measured.by_group[fe.Group("gender", "male")].far == fe.Rate(1, 1)
    assert measured.by_group[fe.Group("gender", "female")].far == fe.Rate(0, 1)


def test_an_unmeasured_trial_is_counted_against_its_own_group():
    measured = report(
        [trial(None, "a", False, fe.Group("gender", "male"))], FixedEmbedder()
    )
    assert measured.by_group[fe.Group("gender", "male")].unmeasured == 1
    assert measured.by_group[fe.Group("gender", "male")].far.denominator == 0


# --- Wiring to Part 13 ------------------------------------------------------------


def test_both_halves_of_a_trial_go_through_the_embedder():
    """The document photo and the live capture are each read, not reused."""
    embedder = FixedEmbedder()
    report([trial("a", "b", False)], embedder)
    assert embedder.seen == ["a", "b"]


def test_the_rate_is_the_thresholds_own_decision():
    """13.15 holds the bar; this module supplies it and reads the answer."""
    trials = [trial("a", "sideways", False)]
    assert report(trials, threshold=0.5).far == fe.Rate(1, 1)
    assert report(trials, threshold=0.7).far == fe.Rate(0, 1)


def test_the_embedder_the_box_has_is_the_real_seam_not_the_stub():
    assert isinstance(fe.CONFIGURED_EMBEDDER, InsightFaceEmbedder)
    assert not isinstance(fe.CONFIGURED_EMBEDDER, NullEmbedder)


# --- Refusals ---------------------------------------------------------------------


def test_two_slots_in_one_dimension_are_refused():
    with pytest.raises(ValueError, match="one age_band slot"):
        report([trial("a", "a", True,
                      fe.Group("age_band", "18-30"), fe.Group("age_band", "51-plus"))])


def test_a_label_naming_no_declared_dimension_is_refused():
    with pytest.raises(ValueError, match="not a demographic dimension"):
        report([trial("a", "a", True, fe.Group("accent", "regional"))])


def test_a_label_outside_the_declared_bands_is_refused():
    with pytest.raises(ValueError, match="not one of the age_band slots"):
        report([trial("a", "a", True, fe.Group("age_band", "40-49"))])


def test_a_refused_trial_is_refused_before_anything_is_embedded():
    """A wiring mistake must not be found after half a dataset was measured."""
    embedder = FixedEmbedder()
    with pytest.raises(ValueError):
        report([trial("a", "a", True), trial("a", "a", True, fe.Group("age_band", "40-49"))],
               embedder)
    assert embedder.seen == []


# --- The entry point ---------------------------------------------------------------


def test_main_prints_the_table_and_the_reasons():
    out = io.StringIO()
    fe.main(out)
    printed = out.getvalue()
    assert "demographic" in printed and "FAR" in printed
    assert fe.REASONS[fe.NO_MODEL] or fe.REASONS[fe.NO_TRIALS] in printed
    assert fe.REASONS[fe.NO_TRIALS] in printed