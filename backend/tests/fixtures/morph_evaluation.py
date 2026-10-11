"""Morph and deepfake detection read the NIST FATE MORPH way, or say why not.

The abstract fixes the two numbers: "attacks missed versus genuine
photographs wrongly flagged".  This module is where they would be read, and
where a run says out loud that they were not.  ``D229`` holds the design.
"""

from typing import NamedTuple

from app.pipeline.tier2 import deepfake, morph
from tests.fixtures.evaluation import Rate

__all__ = [
    "ALL",
    "ATTACK_KINDS",
    "BONAFIDE",
    "CONFIGURED_CLASSIFIERS",
    "CONFIGURED_TRIALS",
    "DeepfakeEnsemble",
    "KindRates",
    "MEASURED",
    "MorphEnsemble",
    "NO_CLASSIFIER",
    "NO_TRIALS",
    "NOT_MEASURED",
    "REASONS",
    "Report",
    "STUBBED",
    "Trial",
    "evaluate",
    "main",
    "table",
]

#: The two attacks Tier 2's seams are measured over, in the abstract's order.
ATTACK_KINDS = ("morph", "deepfake")

#: A genuine photograph, carrying no declared attack.  ``None`` and not a
#: label, so an attack kind and a trial's ground truth cannot be confused.
BONAFIDE = None

#: The row both numbers are also reported over, across the two kinds.
ALL = "all"

#: A real model read the numbers.
MEASURED = "measured"

#: Only stand-ins produced the answers behind them.
STUBBED = "stub"

#: Nothing was counted; :attr:`Report.reasons` names the missing input.
NOT_MEASURED = "not measured"

#: Nothing to read: no morph or deepfake corpus and no set of genuine
#: photographs is installed here.
NO_TRIALS = "no trials configured"

#: A kind has no classifier behind its seam, so its numbers have no detector
#: to be rates of.
NO_CLASSIFIER = "no classifier configured"

#: What each reason means, printed under any table carrying one.
REASONS = {
    NO_TRIALS: (
        "no trials configured: no morph or deepfake corpus and no set of "
        "genuine photographs is installed, so there is nothing to miss and "
        "nothing to flag wrongly"
    ),
    NO_CLASSIFIER: (
        "no classifier configured: this kind has no classifier behind its "
        "seam, so its two numbers have no detector to be rates of"
    ),
}

#: The trials this box has: none.
CONFIGURED_TRIALS = ()

#: The classifiers this box has: Part 15's two labelled stand-ins, which are
#: heuristics and say so through ``is_stub``.
CONFIGURED_CLASSIFIERS = {
    "morph": morph.HeuristicMorphClassifier(),
    "deepfake": deepfake.HeuristicDeepfakeClassifier(),
}

_COLUMNS = (
    "attack",
    "missed",
    "genuine flagged",
    "scored",
    "classifier",
    "source",
)

#: What the ``classifier`` column prints where a kind has no classifier.
NO_CLASSIFIER_LABEL = "none"


class Trial(NamedTuple):
    """One portrait region and whether it is genuine or carries one attack.

    ``attack`` is :data:`BONAFIDE` or one declared kind.  A region is measured
    by its own kind's classifier and by nothing else; a genuine photograph is
    measured by both, because either one flagging it is an officer seeing an
    alert on a real traveller.
    """

    region: object
    attack: str | None = BONAFIDE


class KindRates(NamedTuple):
    """One kind's two numbers, over disjoint sets, and who produced them.

    ``missed`` counts attacks of this kind its classifier did not flag, over
    the attacks of this kind; ``flagged`` counts genuine photographs it
    flagged, over the genuine photographs.  ``stub`` is whether every answer
    behind both numbers came from a stand-in, and ``classifier`` names what
    produced them.
    """

    missed: Rate
    flagged: Rate
    unmeasured: int
    stub: bool
    classifier: str

    @property
    def source(self):
        """Where the numbers came from, or absent where nothing was counted."""
        if not self.scored:
            return NOT_MEASURED
        return STUBBED if self.stub else MEASURED

    @property
    def scored(self):
        """How many trials this kind's classifier produced a reading for."""
        return self.missed.denominator + self.flagged.denominator


class Report(NamedTuple):
    """The two numbers overall, the same two per kind, and what is missing.

    ``overall`` combines the kinds: an attack of either kind missed by its own
    classifier, and a genuine photograph flagged by either one.  ``reasons`` is
    empty only where a number was read, and names every missing input.
    """

    overall: KindRates
    by_kind: dict
    trials: int
    reasons: tuple = ()

    @property
    def source(self):
        """Not measured where an input is missing, else the overall row's."""
        if self.reasons:
            return NOT_MEASURED
        return self.overall.source

    @property
    def unmeasured(self):
        """How many trials no classifier could read."""
        return self.overall.unmeasured

    @property
    def scored(self):
        """How many trials produced a reading."""
        return self.trials - self.unmeasured


class _Either(NamedTuple):
    """One genuine trial read by both classifiers together: any one firing."""

    suspect: bool


class MorphEnsemble(morph.MorphClassifier):
    """Several morph classifiers behind one seam, answering on the strongest.

    ``is_stub`` is true when *any* member stands in, and ``model_version`` is
    the members' versions joined, so a record cannot read as a real model's
    while part of it is a heuristic's.
    """

    def __init__(self, *members):
        """Hold ``members``, refusing an empty or wrongly typed ensemble."""
        chosen = tuple(members)
        if not chosen:
            raise morph.MorphError("an ensemble needs at least one member")
        for member in chosen:
            if not isinstance(member, morph.MorphClassifier):
                raise morph.MorphError("every member must be a MorphClassifier")
        self.members = chosen
        self.model_version = "+".join(
            sorted({member.model_version for member in chosen})
        )
        self.is_stub = any(member.is_stub for member in chosen)

    def classify(self, region):
        """The member's verdict that fires hardest, so no member can be ignored.

        :raises MorphError: when any member cannot read ``region``, since an
            ensemble applied to only some of its trials is another detector.
        """
        return max(
            (member.classify(region) for member in self.members),
            key=lambda verdict: (verdict.suspect, verdict.score),
        )


class DeepfakeEnsemble(deepfake.DeepfakeClassifier):
    """Several deepfake classifiers behind one seam, as :class:`MorphEnsemble`."""

    def __init__(self, *members):
        """Hold ``members``, refusing an empty or wrongly typed ensemble."""
        chosen = tuple(members)
        if not chosen:
            raise deepfake.DeepfakeError("an ensemble needs at least one member")
        for member in chosen:
            if not isinstance(member, deepfake.DeepfakeClassifier):
                raise deepfake.DeepfakeError(
                    "every member must be a DeepfakeClassifier"
                )
        self.members = chosen
        self.model_version = "+".join(
            sorted({member.model_version for member in chosen})
        )
        self.is_stub = any(member.is_stub for member in chosen)

    def classify(self, region):
        """The member's verdict that fires hardest, as the morph ensemble's."""
        return max(
            (member.classify(region) for member in self.members),
            key=lambda verdict: (verdict.suspect, verdict.score),
        )


def _label(classifier):
    """What produced ``classifier``'s answers, for the table to name."""
    version = getattr(classifier, "model_version", None)
    return version if isinstance(version, str) and version else NO_CLASSIFIER_LABEL


def _version(labels):
    """The distinct versions ``labels`` names, joined into one label."""
    named = sorted({label for label in labels if label != NO_CLASSIFIER_LABEL})
    return "+".join(named) if named else NO_CLASSIFIER_LABEL


def _read(trial, classifier):
    """One trial read by ``classifier``, or ``None`` where it could not be read.

    A refusal is an unreadable region rather than a clean one, on D228's rule:
    blank paper and body text are the cases Part 15 measured its cues against,
    and scoring either as a miss would put a stand-in's limit into the rate.
    """
    if classifier is None:
        return None
    try:
        return classifier.classify(trial.region)
    except (morph.MorphError, deepfake.DeepfakeError):
        return None


def _either(verdicts):
    """One genuine trial read by both classifiers together, or ``None``.

    Either detector flagging the portrait is one alert on a real traveller, so
    the two are combined rather than reported as two rows.  A trial neither
    could read is unreadable, not clean.
    """
    read = [verdict for verdict in verdicts.values() if verdict is not None]
    if not read:
        return None
    return _Either(any(verdict.suspect for verdict in read))


def _counts(pairs):
    """Missed attacks and wrongly flagged genuine photographs, over ``pairs``.

    ``pairs`` is ``(is_attack, verdict)``, with ``verdict`` ``None`` where the
    classifier could not read the region.  The two sets are disjoint, so
    neither number can stand in for the other, and an unreadable trial enters
    neither denominator and is counted.
    """
    missed = flagged = attacks = genuine = unmeasured = 0
    for is_attack, verdict in pairs:
        if verdict is None:
            unmeasured += 1
        elif is_attack:
            attacks += 1
            missed += not verdict.suspect
        else:
            genuine += 1
            flagged += verdict.suspect
    return Rate(missed, attacks), Rate(flagged, genuine), unmeasured


def _check_attacks(trials):
    """Refuse any trial naming an attack kind outside :data:`ATTACK_KINDS`.

    :raises ValueError: for a kind nothing collects, which would leave the
        trial measured by no classifier and counted in no row.
    """
    for trial in trials:
        if trial.attack is not BONAFIDE and trial.attack not in ATTACK_KINDS:
            raise ValueError(
                f"{trial.attack!r} is not a declared attack kind, so the trial "
                "is measured by nothing and lands in no row."
            )


def evaluate(trials=CONFIGURED_TRIALS, classifiers=CONFIGURED_CLASSIFIERS):
    """Read missed attacks and wrongly flagged genuine photographs.

    ``classifiers`` maps each declared kind to the classifier behind its seam.
    A kind with none is named in ``reasons`` and contributes no number.  A run
    missing trials or a classifier reports no rate at all and says which
    input was absent; it never reports a zero, which is a rate a detector
    achieves rather than one never read.
    """
    trials = tuple(trials)
    _check_attacks(trials)
    reasons = []
    if not trials:
        reasons.append(NO_TRIALS)
    wired = {
        kind: (classifiers or {}).get(kind) for kind in ATTACK_KINDS
    }
    if any(wired[kind] is None for kind in ATTACK_KINDS):
        reasons.append(NO_CLASSIFIER)

    readings = [
        (
            trial,
            {
                kind: _read(trial, wired[kind])
                for kind in ATTACK_KINDS
                if trial.attack is BONAFIDE or trial.attack == kind
            },
        )
        for trial in trials
    ]


    def per_kind(kind):
        """The two numbers for ``kind``, over the trials that kind is read on."""
        missed, flagged, unmeasured = _counts([
            (trial.attack is not BONAFIDE, verdicts[kind])
            for trial, verdicts in readings
            if kind in verdicts
        ])
        return KindRates(
            missed,
            flagged,
            unmeasured,
            bool(getattr(wired[kind], "is_stub", False)),
            _label(wired[kind]),
        )

    by_kind = {kind: per_kind(kind) for kind in ATTACK_KINDS}
    overall = KindRates(
        *_counts(
            [
                (True, verdicts[trial.attack])
                for trial, verdicts in readings
                if trial.attack is not BONAFIDE
            ]
            + [
                (False, _either(verdicts))
                for trial, verdicts in readings
                if trial.attack is BONAFIDE
            ]
        ),
        any(getattr(wired[kind], "is_stub", False) for kind in ATTACK_KINDS),
        _version(rates.classifier for rates in by_kind.values()),
    )
    return Report(overall, by_kind, len(trials), tuple(reasons))


def _rate_cell(rate):
    """One rate as ``count/trials``, or ``--`` where nothing was counted."""
    return "--" if rate.denominator == 0 else str(rate)


def _cells(label, rates):
    """One row's cells, in the order :func:`table` prints them."""
    return (
        label,
        _rate_cell(rates.missed),
        _rate_cell(rates.flagged),
        str(rates.scored),
        rates.classifier,
        rates.source,
    )


def table(report):
    """``report`` as one table: the two numbers overall and per attack kind."""
    body = [_COLUMNS, _cells(ALL, report.overall)] + [
        _cells(kind, report.by_kind[kind]) for kind in ATTACK_KINDS
    ]
    widths = [
        max(len(line[column]) for line in body) for column in range(len(_COLUMNS))
    ]
    lines = [
        "  ".join(
            cell.ljust(widths[index]) for index, cell in enumerate(line)
        ).rstrip()
        for line in body
    ]
    if report.reasons:
        lines.append("")
        lines.append(f"no rate was measured ({report.source}). Why:")
        lines += [f"  - {REASONS[reason]}" for reason in report.reasons]
    return "\n".join(lines)


def main(stream=None):
    """Print the table over the trials and classifiers this box has."""
    print(table(evaluate()), file=stream)