"""Time each tier and print the abstract's targets beside what was measured.

The abstract bounds Tier 0 at under 0.3 s, Tier 1 at 0.5-1 s and Tier 2 at
1-2 s, and then says in its own terms that those figures "are design targets
and will be reported as measurements once evaluated".  A row here therefore
carries two kinds of number and says which is which: the median and p95 read
on this machine, and the designed target they are read against.

**A tier that nothing ran is designed, not measured.**  Tier 0 is read from
:func:`~app.pipeline.tier0.runner.run_tier0`'s own in-run ``total``, so the
figure is the tier's and not the caller's; Tier 1 and Tier 2 have no reader on
a box with no OCR engine and no configured deep modules, so their rows carry
the target alone and ``--`` in both measured columns.
"""

import math
from typing import NamedTuple

from app.pipeline.tier0 import runner
from tests.fixtures import document_corpus, evaluation

__all__ = [
    "DESIGNED",
    "MEASURED",
    "NOTE",
    "P95",
    "Row",
    "TARGETS",
    "TIER_NAMES",
    "Target",
    "benchmark",
    "designed",
    "main",
    "median",
    "p95",
    "read_tier0",
    "summarise",
    "table",
]

#: The three tiers the abstract bounds, in the order it bounds them.
TIER_NAMES = ("tier_0", "tier_1", "tier_2")

#: The percentile reported as the worst case.
P95 = 0.95

#: A row's numbers were read on this machine.
MEASURED = "measured"

#: A row is the abstract's target and nothing else.
DESIGNED = "designed"

#: What a designed row means, printed under any table holding one.
NOTE = (
    "Rows marked designed are the abstract's targets: nothing was measured "
    "for that tier on this machine."
)

_COLUMNS = (
    "tier",
    "median (measured)",
    "p95 (measured)",
    "target (designed)",
    "verdict",
    "source",
)


class Target(NamedTuple):
    """One tier's designed window in seconds, and the label the abstract gives it."""

    low: float
    high: float
    label: str

    def holds(self, seconds):
        """Whether ``seconds`` sits inside the designed window, bounds included."""
        return self.low <= seconds <= self.high


#: The abstract's three windows.  Tier 0's is one-sided, so its low bound is
#: zero: a Tier 0 that took no time at all is inside "under 0.3 s".
TARGETS = {
    "tier_0": Target(0.0, 0.3, "<0.3 s"),
    "tier_1": Target(0.5, 1.0, "0.5-1 s"),
    "tier_2": Target(1.0, 2.0, "1-2 s"),
}


class Row(NamedTuple):
    """One tier's row: where its numbers came from, and what they were.

    ``median_s`` and ``p95_s`` are seconds, or ``None`` where nothing was
    measured, and ``samples`` is how many runs the row summarises.
    """

    tier: str
    source: str
    samples: int
    median_s: float | None
    p95_s: float | None
    target: Target

    @property
    def within(self):
        """Whether both measured numbers sit inside the target, else ``None``."""
        if self.source == DESIGNED:
            return None
        return all(
            self.target.holds(value) for value in (self.median_s, self.p95_s)
        )


def median(samples):
    """The middle of ``samples``, or ``None`` where there are none.

    An even count averages its two middle values, as ``statistics.median``
    does and as a reader expects of a median.
    """
    if not samples:
        return None
    ordered = sorted(samples)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def p95(samples):
    """The nearest-rank 95th percentile of ``samples``, or ``None`` where empty.

    The smallest sample at or above that percentile's rank, and **nothing
    interpolated**: a tier is read over a handful of runs here, and a fraction
    between two of them would be a duration no run produced.
    """
    if not samples:
        return None
    ordered = sorted(samples)
    return ordered[max(math.ceil(P95 * len(ordered)), 1) - 1]


def read_tier0(document):
    """Tier 0's own in-run total, in seconds, over one drawn page."""
    return runner.run_tier0(document.image).stage_timings["total"]


def designed(tier):
    """The row for a tier nothing measured: its target and two absent columns."""
    return Row(tier, DESIGNED, 0, None, None, TARGETS[tier])


def summarise(tier, samples):
    """One measured row for ``tier`` over ``samples``, given in seconds.

    :raises ValueError: for a tier the abstract does not bound, and for no
        samples at all -- a measured row with nothing measured in it is the one
        row this module must never build.
    """
    if tier not in TARGETS:
        raise ValueError(f"the abstract bounds no tier named {tier!r}")
    if not samples:
        raise ValueError(f"nothing was measured for {tier}, so it is designed")
    return Row(
        tier, MEASURED, len(samples), median(samples), p95(samples), TARGETS[tier]
    )


def benchmark(pages=(), readers=None):
    """One row per tier in :data:`TIER_NAMES`, in that order.

    ``readers`` maps a tier to a callable taking one drawn page and returning
    that tier's duration in seconds; the default reads Tier 0 alone.  A tier
    with no reader, or a reader with no page to read, is reported as
    :data:`DESIGNED` -- a measured row with nothing in it would be the one lie
    this table is built not to tell.
    """
    chosen = {"tier_0": read_tier0} if readers is None else dict(readers)
    rows = []
    for tier in TIER_NAMES:
        reader_for_tier = chosen.get(tier)
        samples = (
            tuple(reader_for_tier(page) for page in pages)
            if reader_for_tier is not None
            else ()
        )
        rows.append(summarise(tier, samples) if samples else designed(tier))
    return tuple(rows)


def _seconds(value):
    """A duration in seconds for one table cell, or ``--`` where there is none."""
    return "--" if value is None else f"{value:.3f} s"


def _cells(row):
    """One row's cells, in the order :func:`table` prints them."""
    verdict = "--" if row.within is None else ("within" if row.within else "over")
    return (
        row.tier,
        _seconds(row.median_s),
        _seconds(row.p95_s),
        row.target.label,
        verdict,
        row.source,
    )


def table(rows):
    """``rows`` as one table: the two measured columns beside the designed target."""
    body = [_COLUMNS] + [_cells(row) for row in rows]
    widths = [
        max(len(line[column]) for line in body) for column in range(len(_COLUMNS))
    ]
    lines = [
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(line)).rstrip()
        for line in body
    ]
    if any(row.source == DESIGNED for row in rows):
        lines.append(NOTE)
    return "\n".join(lines)


def main(stream=None):
    """Print the table over one clean page per document type and seed."""
    pages = [
        document_corpus.generate(seed, document_type=document_type)
        for document_type in document_corpus.DOCUMENT_TYPES
        for seed in evaluation.DEFAULT_SEEDS
    ]
    print(table(benchmark(pages)), file=stream)