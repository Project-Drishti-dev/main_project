"""27.9 -- median and p95 per tier, against the abstract's targets, labelled.

The subject of this file is that the table carries **two kinds of number and
says which is which**.  The abstract bounds the three tiers and then calls
those figures design targets; a benchmark printing a measurement beside them
without the distinction would be claiming the abstract measured something it
did not.  So every row is either `measured` -- read on this machine -- or
`designed` -- the abstract's window and nothing else.

A tier with no reader on this box is therefore `designed`, with no median, no
p95 and no verdict: Tier 1 needs an OCR engine and Tier 2 a configured
deep-module registry, and neither is here, so a row for them cannot be inside
or outside a window it was never measured against.  That is the first group of
tests.  The rest are the arithmetic and the labels the table is built from.
"""

import io
import types

import pytest

from tests.fixtures import document_corpus, evaluation, latency_benchmark as bench

#: One clean page per seed, drawn once.  The default benchmark reads Tier 0
#: over these and reads nothing else.
PAGES = tuple(document_corpus.generate(seed) for seed in evaluation.DEFAULT_SEEDS)

ROWS = bench.benchmark(PAGES)


def rows_by_tier(rows=ROWS):
    """The rows keyed by the tier each one is about."""
    return {row.tier: row for row in rows}


def answering(*values):
    """A reader answering each page with the next of ``values``, last one repeated."""
    ordered = list(values)
    seen = []

    def reader(page):
        seen.append(page)
        return ordered[min(len(seen) - 1, len(ordered) - 1)]

    return reader


def test_the_table_carries_a_median_column_and_a_p95_column():
    """The task's verify: both columns are there, and each says whose it is."""
    heading = bench.table(ROWS).splitlines()[0]
    assert "median (measured)" in heading
    assert "p95 (measured)" in heading


def test_each_measured_number_sits_under_its_own_heading():
    """A table with both columns is not enough: the numbers must not swap."""
    row = bench.summarise("tier_0", (0.10, 0.16))
    heading, cells = bench.table([row]).splitlines()[:2]
    assert heading.split()[1:5] == ["median", "(measured)", "p95", "(measured)"]
    assert cells.split()[1:5] == ["0.130", "s", "0.160", "s"]


def test_the_designed_targets_are_the_abstracts_three_windows():
    assert bench.TIER_NAMES == ("tier_0", "tier_1", "tier_2")
    assert tuple(bench.TARGETS) == bench.TIER_NAMES
    assert [target.label for target in bench.TARGETS.values()] == [
        "<0.3 s",
        "0.5-1 s",
        "1-2 s",
    ]


@pytest.mark.parametrize(
    "tier, inside, outside",
    [
        ("tier_0", (0.0, 0.29), (0.31,)),
        ("tier_1", (0.5, 1.0), (0.4, 1.2)),
        ("tier_2", (1.0, 2.0), (0.9, 2.5)),
    ],
)
def test_a_window_holds_its_bounds_and_refuses_what_lies_outside(tier, inside, outside):
    target = bench.TARGETS[tier]
    assert all(target.holds(seconds) for seconds in inside)
    assert not any(target.holds(seconds) for seconds in outside)


def test_the_rows_come_out_in_the_order_the_abstract_bounds_the_tiers():
    assert tuple(row.tier for row in ROWS) == bench.TIER_NAMES


def test_the_default_benchmark_reads_tier_0_over_every_page():
    row = rows_by_tier()["tier_0"]
    assert row.source == bench.MEASURED
    assert row.samples == len(PAGES)
    assert row.median_s > 0 and row.p95_s >= row.median_s


def test_the_tier_0_figure_is_the_runs_own_total(monkeypatch):
    """The harness reads ``total`` off the record and times nothing itself.

    A caller timing the call from outside would measure its own overhead too,
    so the figure against the abstract's sub-0.3 s target would be a different
    number wearing the same name.
    """
    timings = {
        "detection": 0.01,
        "check_digits": 0.02,
        "watchlist": 0.03,
        "total": 0.42,
    }
    seen = []

    def fake_run(image, *args, **kwargs):
        seen.append(image)
        return types.SimpleNamespace(stage_timings=timings)

    monkeypatch.setattr(bench.runner, "run_tier0", fake_run)
    assert bench.read_tier0(PAGES[0]) == 0.42
    assert seen == [PAGES[0].image]


def test_a_reader_is_handed_the_drawn_page():
    seen = []

    def reader(page):
        seen.append(page)
        return 0.01

    bench.benchmark((PAGES[0],), readers={"tier_0": reader})
    assert seen == [PAGES[0]]


def test_a_measured_row_carries_the_median_and_the_p95_of_what_was_answered():
    row = rows_by_tier(bench.benchmark(
        PAGES, readers={"tier_0": answering(0.10, 0.12, 0.14)}
    ))["tier_0"]
    assert row.source == bench.MEASURED
    assert row.samples == 3
    assert row.median_s == pytest.approx(0.12)
    assert row.p95_s == 0.14


def test_a_tier_with_no_reader_is_designed_and_carries_no_numbers():
    for tier in ("tier_1", "tier_2"):
        row = rows_by_tier()[tier]
        assert row.source == bench.DESIGNED
        assert (row.samples, row.median_s, row.p95_s, row.within) == (0, None, None, None)


def test_the_table_prints_two_blanks_where_a_tier_was_not_measured():
    cells = {
        line.split()[0]: line for line in bench.table(ROWS).splitlines()[1:]
    }
    for tier in ("tier_1", "tier_2"):
        assert cells[tier].split()[1:3] == ["--", "--"]
    assert float(cells["tier_0"].split()[1]) > 0


def test_a_reader_with_no_page_to_read_is_still_designed():
    row = rows_by_tier(bench.benchmark(
        (), readers={"tier_0": answering(0.01)}
    ))["tier_0"]
    assert row.source == bench.DESIGNED


def test_the_median_is_the_middle_and_an_even_count_averages_its_two_middles():
    assert bench.median((0.3, 0.1, 0.2)) == 0.2
    assert bench.median((0.1, 0.2, 0.3, 0.4)) == pytest.approx(0.25)
    assert bench.median(()) is None


def test_the_p95_is_the_nearest_rank_and_interpolates_nothing():
    twenty = tuple(index / 100 for index in range(1, 21))
    assert bench.p95(twenty) == 0.19
    # Interpolating here would report 0.95, a duration no run produced.
    assert bench.p95((0.0, 1.0)) == 1.0
    assert bench.p95(()) is None


def test_a_measured_row_is_judged_against_the_window_it_was_read_against():
    inside = bench.summarise("tier_0", (0.10, 0.12))
    outside = bench.summarise("tier_0", (0.10, 0.31))
    assert inside.within is True
    assert outside.within is False


def test_summarise_refuses_a_tier_the_abstract_does_not_bound():
    with pytest.raises(ValueError):
        bench.summarise("tier_3", (0.1,))


def test_a_measured_row_is_never_built_from_no_samples_at_all():
    with pytest.raises(ValueError):
        bench.summarise("tier_0", ())


def test_the_table_labels_its_columns_measured_and_designed():
    text = bench.table(ROWS)
    assert "median (measured)" in text and "p95 (measured)" in text
    assert "target (designed)" in text
    assert bench.NOTE in text


def test_a_table_of_measured_rows_alone_carries_no_designed_note():
    measured = [bench.summarise("tier_0", (0.1, 0.12))]
    assert bench.NOTE not in bench.table(measured)


def test_running_the_benchmark_prints_the_table_it_produces():
    stream = io.StringIO()
    bench.main(stream=stream)
    lines = stream.getvalue().splitlines()
    assert "median (measured)" in lines[0]
    assert "p95 (measured)" in lines[0]
    assert lines[1].split()[0] == "tier_0"