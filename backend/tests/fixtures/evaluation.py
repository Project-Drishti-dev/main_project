"""Score a detector against the corpus's ground truth.

A detector is handed one :class:`Case` -- a drawn page with the manifest beside
it -- and answers with the fields it read and the alerts it raised, each naming
a kind and pointing at a region.  :func:`evaluate` scores those answers against
the manifest 27.4 declares, over four denominators that are deliberately not
each other: the fields read, the injections caught, the clean pages alarmed, and
the caught injections whose flagged region is measured.
"""

from typing import NamedTuple

from app.pipeline.tier0 import mrz_region
from app.pipeline.tier0.document import parse_mrz
from tests.fixtures import document_corpus, document_manifest

__all__ = [
    "Alert",
    "BAD_CHECK_DIGIT",
    "Case",
    "DEFAULT_SEEDS",
    "Mean",
    "NO_ZONE",
    "OVERLAP_THRESHOLD",
    "Rate",
    "Reading",
    "Report",
    "corpus",
    "evaluate",
    "iou",
    "read_zone",
    "summary",
]

#: The seeds the default corpus is drawn over.
DEFAULT_SEEDS = (0, 1, 2)

#: The IoU a flagged region must reach to count as having found the edit.  Half
#: is the convention of the detection literature, and 0.5 here separates a
#: detector pointing at the region from one naming its label only.
OVERLAP_THRESHOLD = 0.5

#: The two labels :func:`read_zone` raises.  A catch is keyed by the kind of
#: injection it names, so a label naming no injection catches nothing.
NO_ZONE = "zone_not_found"
BAD_CHECK_DIGIT = "check_digit"


class Alert(NamedTuple):
    """One thing a detector wants looked at, and the region it points at.

    ``box`` is a half-open box in the page's own pixels, or ``None`` where the
    detector says what is wrong without saying where.
    """

    label: str
    box: object = None


class Reading(NamedTuple):
    """What one detector made of one page: the fields it read, and its alerts."""

    fields: dict
    alerts: tuple = ()


class Rate(NamedTuple):
    """One count over one denominator.  No denominator is no number."""

    numerator: int
    denominator: int

    @property
    def ratio(self):
        """The share counted, or ``None`` where nothing was counted."""
        if not self.denominator:
            return None
        return self.numerator / self.denominator

    def __str__(self):
        return f"{self.numerator}/{self.denominator}"


class Mean(NamedTuple):
    """One mean over the values it averaged.  Nothing averaged is no number."""

    total: float
    count: int

    @property
    def value(self):
        """The mean, or ``None`` where nothing was averaged."""
        if not self.count:
            return None
        return self.total / self.count

    def __str__(self):
        if not self.count:
            return "nothing measured"
        return f"{self.value:.3f} over {self.count}"


class Case(NamedTuple):
    """One drawn page, the manifest that is its ground truth, and its injections.

    The page's own name is ``record["document_id"]``, which the generator gives
    by type and seed and so names a clean page and a tampered one alike.
    """

    record: dict
    document: object
    tampered: tuple


class Report(NamedTuple):
    """Three rates over three denominators, the mean IoU, and the catch rate
    per injection kind."""

    fields: Rate
    caught: Rate
    false_alerts: Rate
    overlap: Mean
    localized: Rate
    by_kind: dict


def corpus(seeds=DEFAULT_SEEDS, document_types=None):
    """One clean page and one page per injection, for each type and each seed."""
    types = tuple(document_types if document_types is not None
                  else document_corpus.DOCUMENT_TYPES)
    selections = ((), *((kind,) for kind in document_corpus.TAMPER_KINDS))
    drawn = []
    for document_type in types:
        for seed in seeds:
            for tampers in selections:
                document = document_corpus.generate(
                    seed, document_type=document_type, tampers=tampers
                )
                record = document_manifest.manifest(document)
                drawn.append(Case(
                    record,
                    document,
                    tuple(injection["kind"] for injection in record["tampering"]),
                ))
    return tuple(drawn)


def _area(box):
    """The pixels inside a half-open box."""
    return (box[2] - box[0]) * (box[3] - box[1])


def iou(one, other):
    """Intersection over union of two half-open boxes; ``0.0`` where either is
    absent, where they miss, or where the boxes enclose no pixel."""
    if one is None or other is None:
        return 0.0
    shared = (
        max(0, min(one[2], other[2]) - max(one[0], other[0]))
        * max(0, min(one[3], other[3]) - max(one[1], other[1]))
    )
    union = _area(one) + _area(other) - shared
    return shared / union if union else 0.0


def _fields(format_name, lines):
    """Every field of ``format_name``, cut out of the ``lines`` that were read."""
    layout = mrz_region.MRZ_LAYOUTS[format_name]
    return {
        name: lines[number - 1][first - 1:last]
        for number, spans in enumerate(layout.values(), start=1)
        for name, (first, last) in spans.items()
        if number <= len(lines)
    }


def read_zone(case):
    """The machine-readable zone read out of ``case``'s own pixels.

    :func:`~app.pipeline.tier0.mrz_region.detect_mrz` finds the zone without
    being told where it is, the characters come from the corpus fixture's own
    reader, and each printed check digit from
    :func:`~app.pipeline.tier0.document.parse_mrz`.  **The printed block is not
    read**: no OCR engine is installed here, and nothing in this repository
    reads a character out of a printed row.  Neither label it raises points at a
    region: the zone reader says which row failed, not where on the page.
    """
    detection = mrz_region.detect_mrz(case.document.image)
    if detection.format is None:
        return Reading({}, (Alert(NO_ZONE),))
    lines = document_corpus.read_mrz(case.document)
    verdicts = parse_mrz(lines).check_digit_results
    return Reading(
        _fields(detection.format, lines),
        tuple(Alert(BAD_CHECK_DIGIT) for verdict in verdicts
              if verdict.passed is False),
    )


def _best_overlap(alerts, kind, box):
    """The IoU of the alert naming ``kind`` that sits closest over ``box``.

    A detector may raise the same kind more than once at different places; the
    one nearest the edit is the one that found it.
    """
    return max(
        (iou(alert.box, box) for alert in alerts if alert.label == kind),
        default=0.0,
    )


def evaluate(cases, detector=read_zone):
    """Score ``detector`` over ``cases``, against the manifests they carry.

    An injection is caught when the reading carries an alert naming its kind,
    counted over the injections the corpus drew.  A page is a false alert when
    its reading carries any alert at all and it carries no injection.  The two
    are counted over disjoint pages, so neither can stand in for the other.
    ``overlap`` averages the IoU between each caught injection's edited region
    and the best alert naming it -- over the caught injections, so a detector
    that catches nothing is left with no number rather than a perfect zero.
    """
    correct = fields = caught = injected = clean = alarmed = 0
    overlap = 0.0
    localized = measured = 0
    per_kind = {kind: [0, 0] for kind in document_corpus.TAMPER_KINDS}
    for case in cases:
        reading = detector(case)
        for field in case.record["mrz"]:
            fields += 1
            correct += reading.fields.get(field["name"]) == field["value"]
        labels = {alert.label for alert in reading.alerts}
        for injection in case.record["tampering"]:
            kind = injection["kind"]
            injected += 1
            hit = kind in labels
            caught += hit
            per_kind[kind][0] += hit
            per_kind[kind][1] += 1
            if hit:
                best = _best_overlap(reading.alerts, kind, injection["box"])
                overlap += best
                measured += 1
                localized += best >= OVERLAP_THRESHOLD
        if not case.tampered:
            clean += 1
            alarmed += bool(labels)
    return Report(
        fields=Rate(correct, fields),
        caught=Rate(caught, injected),
        false_alerts=Rate(alarmed, clean),
        overlap=Mean(overlap, measured),
        localized=Rate(localized, measured),
        by_kind={kind: Rate(hit, total)
                 for kind, (hit, total) in per_kind.items()},
    )


def summary(report):
    """The rates and the mean IoU as text, one line each, with what is behind each."""
    lines = [
        f"field accuracy    {report.fields}",
        f"tamper catch rate {report.caught}",
        f"false-alert rate  {report.false_alerts}",
        f"region overlap    {report.overlap}",
        f"localized region  {report.localized}",
    ]
    lines += [f"  {kind:<24}{rate}"
              for kind, rate in sorted(report.by_kind.items())]
    return "\n".join(lines)