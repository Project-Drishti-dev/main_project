"""Every number the results page shows is drawn beside its dataset.

27.12 asks for a view that pairs each measured metric with the dataset it came
from, and a test that says so.  This file holds the harness half of that claim:
the rows are refused here before the page ever sees them, and the committed
file the page loads is held against a fresh render so it cannot drift.
"""

import pytest

from tests.fixtures import results_view


DATASET_IDS = frozenset(
    dataset.id for dataset in results_view.DATASETS
)


def _metric(**overrides):
    """One measurable metric, with the fields a row always carries."""
    fields = {
        "id": "sample",
        "label": "Sample",
        "value": "1/2",
        "source": results_view.MEASURED,
        "dataset": results_view.DRAWN_CORPUS,
        "detector": "read_zone",
        "note": "",
    }
    fields.update(overrides)
    return results_view.Metric(**fields)


def test_every_metric_showing_a_number_names_a_dataset():
    for metric in results_view.metrics():
        if not metric.shows_a_number or metric.is_design_target:
            continue
        assert metric.dataset, (
            f"{metric.id} shows {metric.value} and names no dataset, so the "
            "page would draw a number with nothing behind it"
        )
        assert metric.dataset in DATASET_IDS, (
            f"{metric.id} names dataset {metric.dataset!r}, which is not one "
            "this module declares"
        )


def test_a_design_target_names_no_dataset():
    targets = [
        metric for metric in results_view.metrics() if metric.is_design_target
    ]

    assert targets, "the page shows the abstract's latency targets"
    for metric in targets:
        assert metric.dataset == "", f"{metric.id} is a target, not a reading"


def test_a_row_with_no_denominator_is_not_measured():
    """A rate with nothing counted is no number, and says so rather than 0."""
    for metric in results_view.metrics():
        if metric.shows_a_number:
            continue
        assert metric.source not in (
            results_view.MEASURED,
            results_view.STUBBED,
        ), f"{metric.id} shows {metric.value} and claims {metric.source}"


def test_the_face_and_morph_metrics_name_no_dataset():
    """No face or morph corpus is installed here, so none claims one."""
    metrics = [
        metric
        for metric in results_view.metrics()
        if metric.id.startswith(("face_", "morph_"))
    ]

    assert metrics, "the page shows what the face and morph harnesses report"
    for metric in metrics:
        assert metric.dataset == "", metric.id
        assert metric.source == results_view.NOT_MEASURED, metric.id


def test_a_number_with_no_dataset_is_refused():
    with pytest.raises(
        results_view.MetricWithoutDataset, match="names no dataset"
    ):
        results_view.checked(_metric(dataset=""))


def test_a_design_target_naming_a_dataset_is_refused():
    with pytest.raises(
        results_view.MetricWithoutDataset, match="must not name a dataset"
    ):
        results_view.checked(
            _metric(
                source=results_view.DESIGNED,
                value="<0.3 s",
                dataset=results_view.DRAWN_CORPUS,
            )
        )


def test_a_measured_row_with_no_number_is_refused():
    """A reading with nothing in it is the one row this module never builds."""
    with pytest.raises(
        results_view.MetricWithoutDataset, match="shows no number"
    ):
        results_view.checked(
            _metric(value=results_view.NO_NUMBER, source=results_view.MEASURED)
        )


def test_the_render_is_the_same_every_time():
    assert results_view.render() == results_view.render()


def test_the_committed_file_names_the_global_the_page_reads():
    text = results_view.METRIC_PATH.read_text(encoding="utf-8")

    assert text.startswith(results_view.HEADER), (
        "the file must say where it came from, so nobody edits it by hand"
    )
    assert "window.DRISHTI_RESULTS_METRICS" in text


def test_the_committed_file_matches_a_fresh_render():
    """The page cannot show a number the harnesses would not write today."""
    committed = results_view.METRIC_PATH.read_text(encoding="utf-8")

    assert committed == results_view.render(), (
        "frontend/results-metrics.js is stale: regenerate it with "
        "`python -m tests.fixtures.results_view`"
    )