"""Face-verification error rates, per demographic group, or the reasons there are none.

The abstract's validation plan asks for two numbers -- "wrong-person-accepted
and right-person-rejected rates, tuned on held-out data and reported per
demographic group" -- and Section 11 asks for them per group precisely because
NISTIR 8280 found error rates differ between groups.  This module is where
those two numbers are read, and where the report says out loud that they were
not.

**The comparison is 13.15's, unchanged.**  An
:class:`~app.pipeline.tier1.face.Embedder` embeds the document photo and the
live capture, and :func:`~app.pipeline.tier1.face.match_score` decides them
against a threshold the caller supplies.  Nothing here re-implements a cosine,
re-thresholds a similarity, or holds a model.

**A trial nothing could be compared is left out of both rates and counted.**
An embedder that is absent answers ``None`` and a stub answers a labelled zero
vector, and 13.15 refuses the comparison either way.  Scoring a refusal as a
rejection would put a model that is not installed into the false-reject rate,
which is the one number a screening station would act on.

**A trial with no demographic label still counts, and is shown.**  Each
dimension carries an ``unlabelled`` slot, so the per-group rows are the same
trials the overall row is and none is quietly dropped for want of a label.
"""

from typing import NamedTuple

from app.pipeline.tier1.face import NO_MATCH, match_score
from app.pipeline.tier1.insightface_embedder import InsightFaceEmbedder
from tests.fixtures.evaluation import Rate

__all__ = [
    "AGE_BANDS",
    "ALL",
    "CONFIGURED_EMBEDDER",
    "CONFIGURED_THRESHOLD",
    "CONFIGURED_TRIALS",
    "DEMOGRAPHIC_GROUPS",
    "DIMENSIONS",
    "GENDER_LABELS",
    "Group",
    "GroupRates",
    "MEASURED",
    "NO_MODEL",
    "NO_THRESHOLD",
    "NO_TRIALS",
    "NOT_MEASURED",
    "REASONS",
    "Report",
    "Trial",
    "UNLABELLED",
    "evaluate",
    "main",
    "table",
]

#: The two dimensions NISTIR 8280 reports demographic effects over.  A label
#: naming no dimension here is refused, so a dataset cannot land in a row
#: nothing collects.
DIMENSIONS = ("age_band", "gender")

#: The age bands a checkpoint's travellers fall into.  ``under-18`` is here
#: because a fairness table without it measures fairness over adults only.
AGE_BANDS = ("under-18", "18-30", "31-50", "51-plus")

#: The gender labels the FRVT demographic-effects study reports on.
GENDER_LABELS = ("female", "male")

#: The slot a trial with no label in that dimension lands in.  It is a declared
#: slot and not an absence, so the overall rate and the per-group rows are
#: always over the same trials.
UNLABELLED = "unlabelled"

#: The row every per-group row is beside.
ALL = "all"

#: The rates were read over the trials given.
MEASURED = "measured"

#: No rate was read, and :attr:`Report.reasons` says which input was missing.
NOT_MEASURED = "not measured"

#: Nothing to read: no demographic-labelled face dataset is installed here.
NO_TRIALS = "no trials configured"

#: Nothing to compare against.  The abstract's 0.55 is the worked example's
#: illustrative figure, and a harness that adopted it would be reporting a
#: threshold no held-out data ever tuned.
NO_THRESHOLD = "no threshold configured"

#: Trials were offered and none of them could be embedded, so no comparison
#: was made -- insightface is not installed on this box.
NO_MODEL = "no face model configured"

#: What each reason means, printed under any table carrying one.
REASONS = {
    NO_TRIALS: (
        "no face trials configured: no demographic-labelled dataset is "
        "installed, so there is nothing to compare"
    ),
    NO_THRESHOLD: (
        "no threshold configured: the abstract's 0.55 is its worked "
        "example's illustrative figure, not a tuned one"
    ),
    NO_MODEL: (
        "no face model configured: every trial went unmeasured, so neither "
        "rate has a denominator"
    ),
}

#: The trials this box has: none.
CONFIGURED_TRIALS = ()

#: The embedder this box has: 13.13's real seam, which reports itself absent
#: rather than falling back to the stub.
CONFIGURED_EMBEDDER = InsightFaceEmbedder()

#: The threshold this box has tuned: none.
CONFIGURED_THRESHOLD = None

_COLUMNS = ("demographic", "FAR", "FRR", "scored")


class Group(NamedTuple):
    """One declared slot: a dimension and the label inside it."""

    dimension: str
    label: str

    def __str__(self):
        """The slot as the table names it, e.g. ``age_band=18-30``."""
        return f"{self.dimension}={self.label}"


#: Every slot the table carries a row for, each dimension in its declared
#: order and each ending in its ``unlabelled`` slot.
DEMOGRAPHIC_GROUPS = tuple(
    Group(dimension, label)
    for dimension, labels in (
        ("age_band", AGE_BANDS),
        ("gender", GENDER_LABELS),
    )
    for label in labels + (UNLABELLED,)
)


class Trial(NamedTuple):
    """One face comparison: a document photo, a live capture, and whose they are.

    ``genuine`` is whether the two crops are the same person -- the one
    distinction the two rates are counted over.  ``labels`` are the trial's
    demographic slots; a trial carrying none is still counted, and lands in
    each dimension's ``unlabelled`` slot.
    """

    document: object
    live: object
    genuine: bool
    labels: tuple = ()


class GroupRates(NamedTuple):
    """One slot's two rates, and how many of its trials went unmeasured."""

    far: Rate
    frr: Rate
    unmeasured: int


class Report(NamedTuple):
    """The two rates overall, the same two per slot, and what is missing.

    ``far`` counts impostor trials held to a match, ``frr`` genuine trials held
    to none.  ``reasons`` is empty only where a rate was read: it names every
    input the run was missing, so the table can be read without guessing.
    """

    far: Rate
    frr: Rate
    by_group: dict
    trials: int
    unmeasured: int
    threshold: float | None
    reasons: tuple = ()

    @property
    def source(self):
        """:data:`MEASURED` where a rate was read, else :data:`NOT_MEASURED`."""
        return NOT_MEASURED if self.reasons else MEASURED

    @property
    def scored(self):
        """How many trials produced a comparison."""
        return self.trials - self.unmeasured


class _Verdict(NamedTuple):
    """One trial's outcome, carrying the slots it lands in."""

    slots: dict
    genuine: bool
    matched: bool | None


def _slots(labels):
    """``labels`` as one slot per declared dimension, checked.

    :raises ValueError: for a label naming no declared dimension, for a label
        outside that dimension's declared bands, and for two labels in one
        dimension.  All three are wiring mistakes rather than a measurement of
        nothing: each would put a trial in no row or in two, and the table
        would quietly stop being over the same trials the overall row is.
    """
    declared_by_dimension = {
        dimension: tuple(
            entry.label for entry in DEMOGRAPHIC_GROUPS
            if entry.dimension == dimension
        )
        for dimension in DIMENSIONS
    }
    chosen = {}
    for group in labels:
        if group.dimension not in declared_by_dimension:
            raise ValueError(
                f"{group.dimension!r} is not a demographic dimension, "
                f"so {group!r} lands in no row."
            )
        if group.label not in declared_by_dimension[group.dimension]:
            raise ValueError(
                f"{group.label!r} is not one of the {group.dimension} slots."
            )
        if group.dimension in chosen:
            raise ValueError(
                f"a trial carries one {group.dimension} slot, not "
                f"{chosen[group.dimension]!r} and {group.label!r}."
            )
        chosen[group.dimension] = group.label
    return {
        dimension: chosen.get(dimension, UNLABELLED) for dimension in DIMENSIONS
    }


def _verdict(trial, slots, embedder, threshold):
    """One trial decided through 13.12's embedder and 13.15's comparison.

    Answers :data:`~app.pipeline.tier1.face.NO_MATCH` -- ``None`` -- where no
    vector was measured or none could be compared, so an absent model is never
    scored as a rejection.
    """
    document = embedder.embed(trial.document)
    live = embedder.embed(trial.live)
    if document is None or live is None:
        return _Verdict(slots, trial.genuine, NO_MATCH)
    score = match_score(document, live, threshold)
    if score is NO_MATCH:
        return _Verdict(slots, trial.genuine, NO_MATCH)
    return _Verdict(slots, trial.genuine, score.matches)


def _rates(verdicts):
    """The two rates over ``verdicts``, and how many of them went unmeasured.

    An unmeasured verdict enters neither denominator, which is what keeps the
    two sets disjoint: FAR is over impostor trials only and FRR over genuine
    ones, so neither can stand in for the other.
    """
    accepted = rejected = impostors = genuines = unmeasured = 0
    for verdict in verdicts:
        if verdict.matched is NO_MATCH:
            unmeasured += 1
        elif verdict.genuine:
            genuines += 1
            rejected += not verdict.matched
        else:
            impostors += 1
            accepted += verdict.matched
    return Rate(accepted, impostors), Rate(rejected, genuines), unmeasured


def _by_group(verdicts):
    """Every declared slot's two rates, over the verdicts that land in it."""
    by_group = {}
    for group in DEMOGRAPHIC_GROUPS:
        far, frr, unmeasured = _rates(
            verdict for verdict in verdicts
            if verdict.slots[group.dimension] == group.label
        )
        by_group[group] = GroupRates(far, frr, unmeasured)
    return by_group


def evaluate(trials=CONFIGURED_TRIALS, embedder=CONFIGURED_EMBEDDER,
             threshold=CONFIGURED_THRESHOLD):
    """Read FAR and FRR over ``trials``, overall and per declared slot.

    ``threshold`` is required and defaults to none rather than to a figure: the
    abstract tunes its own on held-out data, and ``D101`` refuses a threshold
    nobody supplied.  A run missing any of trials, threshold or a working model
    reports no rate at all and names what was missing -- it does not report a
    zero, which is a rate a model achieves rather than a rate never read.

    Every trial's slots are checked before the first crop is embedded, so a
    wiring mistake is refused before half a dataset has been measured.
    """
    trials = tuple(trials)
    slots = tuple(_slots(trial.labels) for trial in trials)
    reasons = []
    if not trials:
        reasons.append(NO_TRIALS)
    if threshold is None:
        reasons.append(NO_THRESHOLD)
    verdicts = ()
    if trials and threshold is not None:
        verdicts = tuple(
            _verdict(trial, slot, embedder, threshold)
            for trial, slot in zip(trials, slots)
        )
        if all(verdict.matched is NO_MATCH for verdict in verdicts):
            reasons.append(NO_MODEL)
    far, frr, unmeasured = _rates(verdicts)
    return Report(
        far=far,
        frr=frr,
        by_group=_by_group(verdicts),
        trials=len(trials),
        unmeasured=unmeasured,
        threshold=threshold,
        reasons=tuple(reasons),
    )


def _rate_cell(rate):
    """One rate as ``accepted/trials``, or ``--`` where nothing was counted."""
    return "--" if rate.denominator == 0 else str(rate)


def _cells(label, rates, scored):
    """One row's cells, in the order :func:`table` prints them."""
    return (label, _rate_cell(rates.far), _rate_cell(rates.frr), str(scored))


def table(report):
    """``report`` as one table: the two rates overall and per demographic slot."""
    body = [
        _COLUMNS,
        _cells(ALL, report, report.scored),
    ] + [
        _cells(str(group), rates, rates.far.denominator + rates.frr.denominator)
        for group, rates in report.by_group.items()
    ]
    widths = [
        max(len(line[column]) for line in body) for column in range(len(_COLUMNS))
    ]
    lines = [
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(line)).rstrip()
        for line in body
    ]
    if report.reasons:
        lines.append("")
        lines.append(f"no rate was measured ({report.source}). Why:")
        lines += [f"  - {REASONS[reason]}" for reason in report.reasons]
    return "\n".join(lines)


def main(stream=None):
    """Print the table over the trials, embedder and threshold this box has."""
    print(table(evaluate()), file=stream)