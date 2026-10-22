"""27.7 -- region overlap (IoU) between the flagged area and the edited area.

The subject of this file is that the overlap is a number of its own, over its
own denominator.  A detector naming every injection at the region the generator
edited scores 1.0 on both the catch rate and the overlap; one naming every
injection at the whole page catches exactly as many and overlaps far less; one
naming them with no region at all catches exactly as many again and overlaps
nothing.  So the IoU cannot be read off the catch rate, and a detector that
catches nothing is left with no number rather than a zero that would read as
"pointed at the wrong place".
"""

import pytest

from tests.fixtures import document_corpus, evaluation

KINDS = document_corpus.TAMPER_KINDS
THRESHOLD = evaluation.OVERLAP_THRESHOLD

#: The whole corpus, drawn once: a clean page and one page per injection for
#: each type and each seed.  Nothing is detected here -- the numbers below are
#: driven by detectors a case hands the regions to point at.
CASES = evaluation.corpus()
CLEAN = tuple(case for case in CASES if not case.tampered)
INJECTED = sum(len(case.tampered) for case in CASES)


def ids(case):
    """A page's place in the corpus, readable in a failed case's name."""
    tampers = "+".join(case.tampered) or "clean"
    return f"{case.record['document_id']}-{tampers}"


def pointing(where):
    """A detector naming every injection's kind, at whatever ``where`` says.

    ``where`` is handed the page and the injection's edited box, and answers the
    box to point at: the box itself, the whole page, half of it, or ``None``.
    """

    def detector(case):
        alerts = tuple(
            evaluation.Alert(injection["kind"], where(case.record, injection["box"]))
            for injection in case.record["tampering"]
        )
        return evaluation.Reading({}, alerts)

    return detector


def scores(detector):
    """The report over the whole corpus, for one detector."""
    return evaluation.evaluate(CASES, detector)


EXACT = pointing(lambda record, box: box)
WHOLE_PAGE = pointing(lambda record, box: [0, 0, *record["size"]])
#: The edit grown by a tenth on every side: it overlaps itself entirely, and
#: the union it is measured against is its own -- so 1 / 1.21 wherever the
#: margin is measured on both axes.
MARGIN = 0.1
PADDED = pointing(lambda record, box: [
    box[0] - round((box[2] - box[0]) * MARGIN),
    box[1] - round((box[3] - box[1]) * MARGIN),
    box[2] + round((box[2] - box[0]) * MARGIN),
    box[3] + round((box[3] - box[1]) * MARGIN),
])
#: The left quarter of the edit: a quarter of the region, over the whole of it.
QUARTER = pointing(lambda record, box: [
    box[0], box[1],
    box[0] + (box[2] - box[0]) // 4, box[3],
])
NOWHERE = pointing(lambda record, box: None)


def test_a_detector_pointing_at_the_edited_region_overlaps_it_entirely():
    report = scores(EXACT)
    assert report.caught.ratio == 1.0
    assert report.overlap.value == 1.0
    assert report.localized.ratio == 1.0


def test_the_catch_rate_and_the_overlap_are_not_the_same_number():
    exact = scores(EXACT)
    sloppy = scores(WHOLE_PAGE)
    unpointed = scores(NOWHERE)
    assert (sloppy.caught.ratio, unpointed.caught.ratio) == (1.0, 1.0)
    assert exact.overlap.value > sloppy.overlap.value > unpointed.overlap.value
    assert 0.0 < sloppy.overlap.value < 1.0
    assert unpointed.overlap.value == 0.0


def test_a_region_covering_the_edit_and_a_margin_still_reaches_the_threshold():
    report = scores(PADDED)
    assert report.caught.ratio == 1.0
    assert THRESHOLD <= report.overlap.value < 1.0
    assert report.localized.ratio == 1.0


def test_a_region_covering_a_quarter_of_the_edit_misses_the_threshold():
    report = scores(QUARTER)
    assert report.caught.ratio == 1.0
    assert 0.0 < report.overlap.value < THRESHOLD
    assert report.localized.ratio == 0.0


def test_only_the_exact_region_scores_one():
    assert scores(EXACT).overlap.value == 1.0
    assert scores(PADDED).overlap.value < 1.0


def test_the_overlap_is_measured_only_where_something_was_caught():
    report = scores(lambda case: evaluation.Reading({}, ()))
    assert report.caught.ratio == 0.0
    assert report.overlap.value is None
    assert report.overlap.count == 0
    assert report.localized.ratio is None


def test_catching_one_kind_measures_the_overlap_over_that_kind_only():
    def one_kind(case):
        return evaluation.Reading({}, tuple(
            evaluation.Alert(injection["kind"], injection["box"])
            for injection in case.record["tampering"]
            if injection["kind"] == "photo_replacement"
        ))

    report = scores(one_kind)
    assert report.caught.denominator == INJECTED
    assert report.overlap.count == report.caught.numerator == len(CLEAN)
    assert report.overlap.value == 1.0
    assert report.localized.denominator == len(CLEAN)


def test_the_best_of_several_alerts_naming_one_kind_is_the_one_scored():
    def spraying(case):
        whole = [0, 0, *case.record["size"]]
        return evaluation.Reading({}, tuple(
            evaluation.Alert(injection["kind"], box)
            for injection in case.record["tampering"]
            for box in (whole, injection["box"])
        ))

    report = scores(spraying)
    assert report.caught.ratio == 1.0
    assert report.overlap.value == 1.0


def test_a_region_naming_no_injection_is_never_measured_against_one():
    def pointing_elsewhere(case):
        page = [0, 0, *case.record["size"]]
        return evaluation.Reading({}, tuple(
            evaluation.Alert("something_else", page) for _ in case.record["tampering"]
        ))

    report = scores(pointing_elsewhere)
    assert report.caught.ratio == 0.0
    assert report.overlap.value is None


def test_the_mean_iou_is_the_mean_of_the_per_injection_overlaps():
    report = scores(WHOLE_PAGE)
    total = sum(
        evaluation.iou([0, 0, *case.record["size"]], injection["box"])
        for case in CASES for injection in case.record["tampering"]
    )
    assert report.overlap.total == pytest.approx(total)
    assert report.overlap.value == pytest.approx(total / INJECTED)


def test_iou_of_two_boxes_is_their_overlap_over_their_union():
    assert evaluation.iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert evaluation.iou([0, 0, 10, 10], [10, 10, 20, 20]) == 0.0
    assert evaluation.iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert evaluation.iou([0, 0, 10, 10], [0, 0, 10, 5]) == pytest.approx(0.5)
    assert evaluation.iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(1 / 3)
    assert evaluation.iou([0, 0, 10, 10], [10, 0, 20, 10]) == 0.0


def test_a_box_that_is_not_there_overlaps_nothing():
    assert evaluation.iou(None, [0, 0, 10, 10]) == 0.0
    assert evaluation.iou([0, 0, 10, 10], None) == 0.0
    assert evaluation.iou(None, None) == 0.0
    assert evaluation.iou([5, 5, 5, 5], [0, 0, 10, 10]) == 0.0


def test_a_mean_of_nothing_is_no_number():
    assert evaluation.Mean(0.0, 0).value is None
    assert str(evaluation.Mean(0.0, 0)) == "nothing measured"
    assert evaluation.Mean(1.5, 3).value == 0.5
    assert str(evaluation.Mean(1.5, 3)) == "0.500 over 3"


def test_the_summary_reports_the_overlap_under_its_own_name():
    lines = evaluation.summary(scores(EXACT)).splitlines()
    assert lines[3].split() == ["region", "overlap", "1.000", "over", str(INJECTED)]
    assert lines[4].split() == ["localized", "region", f"{INJECTED}/{INJECTED}"]


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_every_injection_is_overlapped_entirely_by_its_own_region(case):
    """The ground truth the overlap is measured against is the injection's box."""
    report = evaluation.evaluate((case,), EXACT)
    if not case.tampered:
        assert report.overlap.count == 0
    else:
        assert report.overlap.value == 1.0
        assert report.overlap.count == report.localized.numerator == len(case.tampered)