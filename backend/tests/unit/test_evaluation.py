"""27.6 -- tamper catch rate and false-alert rate, reported as two numbers.

The subject of this file is that the two are counted over *different pages*:
the catch rate counts injections on pages the corpus tampered, the false-alert
rate counts alarmed pages the corpus left clean.  A detector raising everything
scores 1.0 on one and 1.0 on the other; one raising only where an injection was
injected scores 1.0 and 0.0.  So neither number can be recovered from the other,
which is what "reported separately" has to mean.
"""

import types

import numpy as np
import pytest

from tests.fixtures import document_corpus, document_manifest, evaluation, mrz_images

KINDS = document_corpus.TAMPER_KINDS
SEEDS = evaluation.DEFAULT_SEEDS
TYPES = tuple(document_corpus.DOCUMENT_TYPES)

#: The whole corpus, drawn once: a clean page and one page per injection for
#: each type and each seed.  Nothing here is detected -- the rates below are
#: driven by detectors a case hands the labels to raise.
CASES = evaluation.corpus()
CLEAN = tuple(case for case in CASES if not case.tampered)
INJECTED = sum(len(case.tampered) for case in CASES)

#: One seed, for the one case that runs the real zone reader over pixels.
READ = evaluation.corpus(seeds=(0,))


def ids(case):
    """A page's place in the corpus, readable in a failed case's name."""
    tampers = "+".join(case.tampered) or "clean"
    return f"{case.record['document_id']}-{tampers}"


def raising(labels):
    """A detector that reads nothing and raises the labels ``labels(case)`` names."""

    def detector(case):
        return evaluation.Reading(
            {}, tuple(evaluation.Alert(label) for label in labels(case))
        )

    return detector


def scores(detector):
    """The report over the whole corpus, for one detector."""
    return evaluation.evaluate(CASES, detector)


def test_the_catch_rate_and_the_false_alert_rate_are_two_numbers():
    exact = scores(raising(lambda case: case.tampered))
    trigger_happy = scores(raising(lambda case: KINDS))
    assert exact.caught.ratio == trigger_happy.caught.ratio == 1.0
    assert exact.false_alerts.ratio == 0.0
    assert trigger_happy.false_alerts.ratio == 1.0


def test_alarming_only_the_clean_pages_catches_nothing_and_alarms_all_of_them():
    report = scores(raising(lambda case: () if case.tampered else KINDS))
    assert report.caught.ratio == 0.0
    assert report.false_alerts.ratio == 1.0


def test_a_detector_that_raises_nothing_scores_zero_on_both():
    report = scores(raising(lambda case: ()))
    assert report.caught.ratio == 0.0
    assert report.false_alerts.ratio == 0.0


def test_an_alert_naming_no_injection_catches_nothing():
    report = scores(raising(lambda case: ("something_else",) if case.tampered else ()))
    assert report.caught.ratio == 0.0
    assert report.false_alerts.ratio == 0.0


def test_the_catch_rate_counts_injections_and_the_false_alert_rate_clean_pages():
    report = scores(raising(lambda case: KINDS))
    assert report.caught.denominator == INJECTED == len(CLEAN) * len(KINDS)
    assert report.false_alerts.denominator == len(CLEAN)


def test_the_corpus_draws_one_clean_page_and_one_page_per_injection():
    assert len(CLEAN) == len(TYPES) * len(SEEDS)
    assert INJECTED == len(CLEAN) * len(KINDS)


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_every_case_carries_a_manifest_that_validates(case):
    assert document_manifest.validate(case.record) == ()


@pytest.mark.parametrize("kind", KINDS)
def test_each_injection_kind_has_its_own_catch_rate(kind):
    report = scores(raising(lambda case: (kind,) if kind in case.tampered else ()))
    assert report.by_kind[kind].ratio == 1.0
    missed = [name for name in KINDS if name != kind]
    assert [report.by_kind[name].ratio for name in missed] == [0.0] * len(missed)
    assert report.caught.ratio == 1 / len(KINDS)


def test_the_per_kind_rates_are_the_catch_rate_cut_by_kind():
    one_label = raising(lambda case: ("photo_replacement",) if case.tampered else ())
    report = scores(one_label)
    assert report.caught.ratio == 1 / len(KINDS)
    assert sum(rate.numerator for rate in report.by_kind.values()) == report.caught.numerator
    assert {rate.denominator for rate in report.by_kind.values()} == {len(CLEAN)}

def test_a_detector_that_reads_nothing_scores_no_field_correct():
    report = scores(raising(lambda case: KINDS))
    assert report.fields.ratio == 0.0
    assert report.fields.denominator == sum(len(case.record["mrz"]) for case in CASES)


def test_a_field_read_wrong_costs_exactly_one_field_on_its_own_page():
    def detector(case):
        fields = {field["name"]: field["value"] for field in case.record["mrz"]}
        first = case.record["mrz"][0]
        fields[first["name"]] = "?" * len(first["value"])
        return evaluation.Reading(fields, ())

    report = scores(detector)
    assert report.fields.numerator == report.fields.denominator - len(CASES)
    assert report.caught.ratio == 0.0


def test_the_zone_reader_reads_every_field_and_raises_nothing_at_all():
    report = evaluation.evaluate(READ)
    assert report.fields.ratio == 1.0
    assert report.caught.ratio == 0.0
    assert report.false_alerts.ratio == 0.0


def test_a_page_with_no_zone_reads_no_field_and_says_so():
    blank = types.SimpleNamespace(
        image=np.full((400, 600, 3), mrz_images.PAPER_LEVEL, dtype=np.uint8)
    )
    reading = evaluation.read_zone(evaluation.Case({"mrz": []}, blank, ()))
    assert reading.fields == {}
    assert [alert.label for alert in reading.alerts] == [evaluation.NO_ZONE]

def test_a_rate_with_no_denominator_is_no_number():
    assert evaluation.Rate(0, 0).ratio is None
    assert str(evaluation.Rate(3, 0)) == "3/0"


def test_the_summary_reports_the_two_rates_on_their_own_lines():
    lines = evaluation.summary(scores(raising(lambda case: KINDS))).splitlines()
    assert lines[1].split() == ["tamper", "catch", "rate", f"{INJECTED}/{INJECTED}"]
    assert lines[2].split() == ["false-alert", "rate", f"{len(CLEAN)}/{len(CLEAN)}"]
