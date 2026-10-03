"""A per-document feature vector, and an IsolationForest fitted on a committed fixture.

Every Tier 2 module so far reads its own thing -- a map, a mark, two cues, one
number -- so nothing has ever put two documents on one scale.  This is that
scale.  :func:`feature_vector` measures one document as the fifteen numbers in
:data:`FEATURE_NAMES`, drawn from five families: error-level analysis, noise
residual, histogram, edge density and field geometry.  :class:`AnomalyScorer`
fits a scikit-learn :class:`~sklearn.ensemble.IsolationForest` on rows measured
from clean synthetic pages and answers how unlike anything in that fixture a
document is.

**The score is a rank against the committed fixture, not a probability that a
document is forged.**  :meth:`AnomalyScorer.rank` returns the share of fixture
rows that are *less* anomalous than the one measured, so it is in ``[0, 1]``,
rises with the forest's own raw score, and needs no threshold chosen by hand:
the forest's :meth:`~sklearn.ensemble.IsolationForest.predict` supplies the
line, and :meth:`AnomalyScorer.outlier` reports it.

**Nothing here has met a real document.**  The fixture is synthetic artwork
this repository drew, on the same footing as every other Tier 2 constant, so
:class:`AnomalyScorer` is labelled ``is_stub`` and ``isolation-forest-v0`` even
though a forest really was fitted on it.  A real fit on real captures is the
thing that would change that label, and the vector, not the scorer, is the part
that survives the swap.  D124 holds the measured limits.

**A frame shorter than the grid is refused rather than upsampled.**  The vector
is measured on one canonical frame, :data:`CANONICAL` pixels on its long side and
whole :data:`~app.pipeline.tier2.ela.BLOCK_SIZE`-pixel blocks, so a page
photographed at 120px and one at 3200px are read on one grid.  Interpolating up
would measure pixels the capture never held, which is D115's rule applied to
resolution instead of content.
"""

import dataclasses
import json
import math
import numbers
import pathlib
import typing

import cv2
import numpy as np
from sklearn.ensemble import IsolationForest

from app.pipeline.tier2 import ela, noise_residual

__all__ = [
    "CANONICAL",
    "CONTAMINATION",
    "FEATURE_NAMES",
    "FIXTURE_PATH",
    "INK_LEVEL",
    "MODEL_VERSION",
    "N_ESTIMATORS",
    "RANDOM_STATE",
    "RULE_SHARE",
    "AnomalyError",
    "AnomalyScorer",
    "AnomalyVerdict",
    "FeatureVector",
    "canonical",
    "edge_stats",
    "ela_stats",
    "feature_vector",
    "field_stats",
    "histogram_stats",
    "load_fixture",
    "noise_stats",
]

#: The committed fixture this module fits on: rows measured by
#: :func:`feature_vector` from clean synthetic pages this repository drew.  It
#: ships in the package rather than beside the tests, because the scorer that
#: reads it is production code and a fixture only a test can see is a fixture
#: the scorer cannot load.  The generator that produced it is
#: ``test_tier2_anomaly.py``'s ``_clean_page``, recorded in the file itself.
FIXTURE_PATH = pathlib.Path(__file__).with_name("fixtures") / "clean_features_v1.json"

#: What produced an answer, and whether a stand-in produced it.  The forest is
#: really fitted, but on synthetic artwork, so the label says what it says for
#: every other Tier 2 module: this is not calibrated on documents.  A fit on
#: real captures takes a different version string, not a cleared flag.
MODEL_VERSION = "isolation-forest-v0"

#: The side the document is resampled to before any of the five families is
#: read, so a page photographed small and one photographed large are measured
#: on one grid.  D120's rule, held again on a different measurement.
CANONICAL = 256

#: The Canny pair edge density is read at, on a 0-255 gray plane.  Fixed
#: rather than median-relative so the number means the same thing on every
#: document and a shift in it is a shift in the document.
CANNY_LOW = 100
CANNY_HIGH = 200

#: Where the histogram puts its ink cut, and how many bins its entropy is read
#: over.  A scanned page is light paper with dark marks on it, so one cut
#: separates the two families without a classifier.
INK_LEVEL = 200
HIST_BINS = 16

#: The share of the frame's width (or height) a straight run of ink must reach
#: before the line is read as a form field rather than as a character stroke.
RULE_SHARE = 0.25

#: The forest's own shape: fixed and seeded, so fitting the same committed
#: fixture twice answers the same number.  **No per-feature scaling is applied,
#: and that is measured rather than assumed**: a forest draws each tree's
#: threshold uniformly inside one feature's own range, so dividing every column
#: by its spread across the fixture left the probe's clean and out-of-
#: distribution scores identical to four decimal places.
N_ESTIMATORS = 200
RANDOM_STATE = 0

#: The share of the committed fixture the forest may call outlier, which is
#: where :meth:`AnomalyScorer.outlier` reads its line: the fixture's own 95th
#: percentile.  **Not scikit-learn's ``"auto"``, which was measured here and
#: rejected.**  At ``"auto"`` the line sits at a raw score of 0.500, which is
#: the middle of the clean band rather than above it: it called 41 of the 120
#: committed rows and 6 of 12 freshly drawn clean pages outliers.  At 0.05 it
#: calls 6 of 120 and 1 of 12, and all four measured out-of-distribution
#: candidates stay above it.  D124 holds the numbers.
CONTAMINATION = 0.05

#: The vector's fifteen numbers, in the order they are fitted and scored.  The
#: fixture's header is checked against this list, so a fixture whose columns
#: were reordered is refused rather than read as another document.
FEATURE_NAMES = (
    "ela_mean",
    "ela_p95",
    "ela_max",
    "noise_median",
    "noise_p95",
    "noise_ratio",
    "hist_mean",
    "hist_std",
    "ink_share",
    "hist_entropy",
    "edge_density",
    "edge_strength",
    "rule_rows",
    "rule_cols",
    "row_fill",
)


class AnomalyError(ValueError):
    """Raised when a document cannot be measured, or an argument is malformed.

    A ``ValueError``, so a caller catching one around its cascade keeps working
    as D115 requires of everything Tier 2 raises.  A frame this module cannot
    measure is refused rather than answered as a typical document.
    """


def _gray(image: object) -> np.ndarray:
    """Return ``image`` as the one gray plane every family measures."""
    try:
        return ela.to_gray(image)
    except ela.ELAError as error:
        raise AnomalyError(str(error)) from error


def canonical(image: object, *, size: int = CANONICAL) -> np.ndarray:
    """Return ``image`` resampled onto the one grid the vector is read on.

    :param image: a document as :func:`~app.pipeline.tier2.ela.to_gray` takes
        it, one, three or four channels of 8-bit pixels.
    :param size: the long side the frame is resampled to.
    :returns: the frame as ``uint8``, cropped to whole
        :data:`~app.pipeline.tier2.ela.BLOCK_SIZE`-pixel blocks so every
        block-wise family below divides evenly, and kept 8-bit because a
        family that refuses another dtype would otherwise measure an
        interpolated picture instead of the capture's own levels.
    :raises AnomalyError: on a frame whose long side is under ``size``, which
        would have to be interpolated up, or a side that is not a whole number
        of pixels above zero.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise AnomalyError("size must be a whole number of pixels above zero")
    block = ela.BLOCK_SIZE
    gray = _gray(image)
    height, width = gray.shape
    longest = max(height, width)
    if longest < size:
        raise AnomalyError(
            f"document of {width}x{height} is smaller than the {size}px grid it "
            "is measured on; it would have to be interpolated up"
        )
    scale = size / longest
    whole_h = max(block, int(round(height * scale)) // block * block)
    whole_w = max(block, int(round(width * scale)) // block * block)
    return cv2.resize(
        gray.astype(np.uint8), (whole_w, whole_h), interpolation=cv2.INTER_AREA
    )


def ela_stats(gray: np.ndarray) -> tuple[float, float, float]:
    """Return the document's error-level statistics over every JPEG quality.

    :param gray: the canonical frame as :func:`canonical` returns it.
    :returns: the mean, the 95th percentile and the largest of the block means
        :func:`~app.pipeline.tier2.ela.error_map` gives at each of
        :data:`~app.pipeline.tier2.ela.QUALITIES`, pooled over blocks and
        qualities so one quality's mood cannot decide the answer.
    :raises AnomalyError: on a frame ELA cannot measure.
    """
    plane = gray.astype(np.float64)
    try:
        pooled = np.concatenate(
            [
                ela.block_means(ela.error_map(plane, quality)).ravel()
                for quality in ela.QUALITIES
            ]
        )
    except ela.ELAError as error:
        raise AnomalyError(str(error)) from error
    return (
        float(pooled.mean()),
        float(np.percentile(pooled, 95)),
        float(pooled.max()),
    )


def noise_stats(gray: np.ndarray) -> tuple[float, float, float]:
    """Return the document's noise-floor statistics, block by block.

    :param gray: the canonical frame as :func:`canonical` returns it.
    :returns: the median block residual variance, its 95th percentile, and
        their ratio in octaves.
    :raises AnomalyError: on a frame carrying no noise at all, which is
        :func:`~app.pipeline.tier2.noise_residual.normalise`'s refusal rather
        than a document whose noise happens to be zero.
    """
    try:
        variances = noise_residual.block_variance(noise_residual.high_pass(gray))
    except noise_residual.NoiseResidualError as error:
        raise AnomalyError(str(error)) from error
    median = float(np.median(variances))
    if not median > 0.0:
        raise AnomalyError("the document carries no noise to measure a departure from")
    p95 = float(np.percentile(variances, 95))
    return median, p95, float(math.log2(p95 / median))


def histogram_stats(gray: np.ndarray) -> tuple[float, float, float, float]:
    """Return the document's tonal statistics read off its own histogram.

    :param gray: the canonical frame as :func:`canonical` returns it.
    :returns: the mean and standard deviation of the 256-bin histogram, the
        share of pixels darker than :data:`INK_LEVEL`, and the entropy of the
        :data:`HIST_BINS`-bin histogram normalised into ``[0, 1]``.
    """
    counts = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    share = counts / counts.sum()
    levels = np.arange(256, dtype=np.float64)
    mean = float((levels * share).sum())
    std = float(math.sqrt(max(0.0, float(((levels - mean) ** 2 * share).sum()))))
    ink = float(share[:INK_LEVEL].sum())
    bins = share.reshape(HIST_BINS, 256 // HIST_BINS).sum(axis=1)
    present = bins[bins > 0.0]
    entropy = float(-(present * np.log2(present)).sum() / math.log2(HIST_BINS))
    return mean, std, ink, entropy


def edge_stats(gray: np.ndarray) -> tuple[float, float]:
    """Return how much of the document is edge, and how hard those edges are.

    :param gray: the canonical frame as :func:`canonical` returns it.
    :returns: the share of pixels :func:`cv2.Canny` calls edges at
        :data:`CANNY_LOW`/:data:`CANNY_HIGH`, and the mean Sobel gradient
        magnitude divided by 255.
    """
    edges = cv2.Canny(gray, CANNY_LOW, CANNY_HIGH)
    plane = gray.astype(np.float64)
    horizontal = cv2.Sobel(plane, cv2.CV_64F, 1, 0, ksize=3)
    vertical = cv2.Sobel(plane, cv2.CV_64F, 0, 1, ksize=3)
    strength = float((np.hypot(horizontal, vertical) / 255.0).mean())
    return float((edges > 0).mean()), strength


def _longest_run(mask: np.ndarray, axis: int) -> np.ndarray:
    """Return each line's longest unbroken run of ``True`` along ``axis``."""
    lines = mask if axis == 1 else mask.T
    padded = np.zeros((lines.shape[0], lines.shape[1] + 1), np.int32)
    padded[:, 1:] = np.cumsum(lines, axis=1, dtype=np.int32)
    longest = np.zeros(lines.shape[0], np.int32)
    for length in range(1, lines.shape[1] + 1):
        windows = padded[:, length:] - padded[:, :-length]
        longest = np.maximum(longest, windows.max(axis=1))
    return longest


def field_stats(gray: np.ndarray) -> tuple[float, float, float]:
    """Return the geometry of the form's printed fields.

    :param gray: the canonical frame as :func:`canonical` returns it.
    :returns: the share of rows holding a straight ink run at least
        :data:`RULE_SHARE` of the frame wide, the share of columns holding one
        at least that tall, and the share of rows carrying any ink at all.
    """
    ink = gray < INK_LEVEL
    rows = _longest_run(ink, 1)
    columns = _longest_run(ink, 0)
    rule_rows = float((rows >= max(1, round(RULE_SHARE * ink.shape[1]))).mean())
    rule_cols = float((columns >= max(1, round(RULE_SHARE * ink.shape[0]))).mean())
    return rule_rows, rule_cols, float(ink.any(axis=1).mean())


@dataclasses.dataclass(frozen=True)
class FeatureVector:
    """One document measured on :data:`FEATURE_NAMES`, in that order.

    Frozen, so a fitted forest cannot be shown a vector that changed under it.
    """

    ela_mean: float
    ela_p95: float
    ela_max: float
    noise_median: float
    noise_p95: float
    noise_ratio: float
    hist_mean: float
    hist_std: float
    ink_share: float
    hist_entropy: float
    edge_density: float
    edge_strength: float
    rule_rows: float
    rule_cols: float
    row_fill: float

    def __post_init__(self) -> None:
        """Refuse a vector carrying a value the forest cannot be shown."""
        for name in FEATURE_NAMES:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, numbers.Real):
                raise AnomalyError(f"{name} must be a real number")
            if not math.isfinite(float(value)):
                raise AnomalyError(f"{name} must be a finite number")

    def as_array(self) -> np.ndarray:
        """Return the vector as one row in :data:`FEATURE_NAMES` order."""
        return np.asarray([float(getattr(self, name)) for name in FEATURE_NAMES])


def feature_vector(image: object) -> FeatureVector:
    """Return ``image`` as the fifteen numbers a forest is fitted and scored on.

    :param image: a document as :func:`canonical` takes it.
    :returns: one :class:`FeatureVector` holding all five families.
    :raises AnomalyError: on a document no family can measure, which is D115's
        rule: a refusal, never a vector of zeros that would score as average.
    """
    gray = canonical(image)
    ela_mean, ela_p95, ela_max = ela_stats(gray)
    noise_median, noise_p95, noise_ratio = noise_stats(gray)
    hist_mean, hist_std, ink_share, hist_entropy = histogram_stats(gray)
    edge_density, edge_strength = edge_stats(gray)
    rule_rows, rule_cols, row_fill = field_stats(gray)
    return FeatureVector(
        ela_mean=ela_mean,
        ela_p95=ela_p95,
        ela_max=ela_max,
        noise_median=noise_median,
        noise_p95=noise_p95,
        noise_ratio=noise_ratio,
        hist_mean=hist_mean,
        hist_std=hist_std,
        ink_share=ink_share,
        hist_entropy=hist_entropy,
        edge_density=edge_density,
        edge_strength=edge_strength,
        rule_rows=rule_rows,
        rule_cols=rule_cols,
        row_fill=row_fill,
    )


def _check_row(row: object) -> tuple[float, ...]:
    """Refuse ``row`` unless it is one finite number per named feature."""
    if isinstance(row, (str, bytes)) or not isinstance(row, (list, tuple)):
        raise AnomalyError("a fixture row must be a sequence of numbers")
    if len(row) != len(FEATURE_NAMES):
        raise AnomalyError(
            f"a fixture row holds {len(row)} numbers and the vector names "
            f"{len(FEATURE_NAMES)}"
        )
    out = []
    for name, value in zip(FEATURE_NAMES, row):
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise AnomalyError(f"{name} must be a real number")
        number = float(value)
        if not math.isfinite(number):
            raise AnomalyError(f"{name} must be a finite number")
        out.append(number)
    return tuple(out)


def load_fixture(path: object = None) -> tuple[tuple[float, ...], ...]:
    """Return the committed clean-document rows the forest is fitted on.

    :param path: the fixture to read; :data:`FIXTURE_PATH` by default.
    :returns: one row of fifteen finite numbers per clean document.
    :raises AnomalyError: on a fixture that cannot be read, holds no rows, or
        whose header is not exactly :data:`FEATURE_NAMES` -- a reordered
        fixture is a silent wrong answer, not a rounding difference.
    """
    location = FIXTURE_PATH if path is None else pathlib.Path(path)
    try:
        payload = json.loads(location.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AnomalyError(
            f"the committed feature fixture is unreadable: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise AnomalyError("the committed feature fixture must hold an object")
    if tuple(payload.get("features", ())) != FEATURE_NAMES:
        raise AnomalyError("the fixture's feature header is not this vector's")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise AnomalyError("the committed feature fixture holds no rows")
    return tuple(_check_row(row) for row in rows)


@dataclasses.dataclass(frozen=True)
class AnomalyVerdict:
    """One document's answer: where it ranks, and how far out it reads.

    ``score`` is the rank against the committed fixture and is what a caller
    reads; ``raw`` is the forest's own unbounded anomaly score, kept because a
    rank that saturates at 1.0 hides how far past the fixture a document sits.
    ``outlier`` is the forest's own prediction, so the line is one scikit-learn
    fixed and not a threshold chosen here.
    """

    #: The share of fixture rows less anomalous than this document, in [0, 1].
    score: float

    #: The forest's own anomaly score: higher is more anomalous, unbounded.
    raw: float

    #: Whether the forest predicts this document as an outlier.
    outlier: bool

    #: The vector the answer was read from, so the numbers can be shown.
    features: FeatureVector

    def __post_init__(self) -> None:
        """Refuse a verdict whose score, raw reading or flag is malformed."""
        if isinstance(self.score, bool) or not isinstance(self.score, numbers.Real):
            raise AnomalyError("score must be a real number")
        if not 0.0 <= float(self.score) <= 1.0:
            raise AnomalyError("score must sit in [0, 1]")
        if isinstance(self.raw, bool) or not isinstance(self.raw, numbers.Real):
            raise AnomalyError("raw must be a real number")
        if not math.isfinite(float(self.raw)):
            raise AnomalyError("raw must be a finite number")
        if not isinstance(self.outlier, bool):
            raise AnomalyError("outlier must be a bool")
        if not isinstance(self.features, FeatureVector):
            raise AnomalyError("features must be a FeatureVector")


class AnomalyScorer:
    """An IsolationForest fitted on the committed fixture, scoring documents.

    The forest is fitted at construction on rows read by :func:`load_fixture`,
    seeded by :data:`RANDOM_STATE`, so two scorers built from the same fixture
    answer the same number for the same document.  It answers ``is_stub``
    ``True`` and :data:`MODEL_VERSION` and cannot answer otherwise: the fit is
    real, the documents behind it are not.
    """

    model_version = MODEL_VERSION
    is_stub = True

    def __init__(
        self,
        *,
        rows: typing.Sequence[typing.Sequence[float]] | None = None,
        n_estimators: int = N_ESTIMATORS,
        random_state: int = RANDOM_STATE,
        contamination: object = CONTAMINATION,
    ) -> None:
        """Fit the forest on ``rows``, or on the committed fixture.

        :param rows: the clean rows to fit on; :func:`load_fixture` by default.
        :param n_estimators: trees in the forest.
        :param random_state: the seed, so a fit is repeatable.
        :param contamination: the fraction the forest may call outlier, or
            ``"auto"`` for the threshold the original paper fixed.
        :raises AnomalyError: on rows that are not fifteen finite numbers each,
            too few to fit on, or a forest shape that is not one.
        """
        if isinstance(n_estimators, bool) or not isinstance(n_estimators, int):
            raise AnomalyError("n_estimators must be a whole number of trees")
        if n_estimators < 1:
            raise AnomalyError("n_estimators must be at least one tree")
        if isinstance(random_state, bool) or not isinstance(random_state, int):
            raise AnomalyError("random_state must be a whole number")
        if random_state < 0:
            raise AnomalyError("random_state must not be negative")
        if contamination != "auto" and not isinstance(contamination, numbers.Real):
            raise AnomalyError('contamination must be "auto" or a share in (0, 0.5]')
        fitted = load_fixture() if rows is None else tuple(_check_row(r) for r in rows)
        if len(fitted) < 2:
            raise AnomalyError("a forest cannot be fitted on fewer than two rows")
        self.rows = fitted
        self.forest = IsolationForest(
            n_estimators=n_estimators,
            random_state=random_state,
            contamination=contamination,
        )
        self.forest.fit(np.asarray(fitted, dtype=np.float64))
        self._raw = np.sort(self._raw_of(fitted))

    def _raw_of(self, vectors: typing.Sequence[object]) -> np.ndarray:
        """Return the forest's anomaly score for each row, higher is worse."""
        return -self.forest.score_samples(np.asarray(vectors, dtype=np.float64))

    def raw_score(self, features: FeatureVector) -> float:
        """Return the forest's own anomaly score for ``features``.

        :param features: one document's vector.
        :returns: a finite number, higher meaning more anomalous than the
            fixture and not bounded above.
        :raises AnomalyError: on anything that is not a :class:`FeatureVector`.
        """
        if not isinstance(features, FeatureVector):
            raise AnomalyError("features must be a FeatureVector")
        return float(self._raw_of([features.as_array()])[0])

    def rank(self, features: FeatureVector) -> float:
        """Return where ``features`` sits among the rows the forest was fitted on.

        :param features: one document's vector.
        :returns: the share of fixture rows less anomalous than this one, in
            ``[0, 1]``.  **A rank, not a probability**: it says how unlike the
            fixture a document is and nothing about whether it was tampered
            with.  A document past every row reads 1.0 and no further.
        :raises AnomalyError: on anything that is not a :class:`FeatureVector`.
        """
        raw = self.raw_score(features)
        return float((self._raw < raw).mean())

    def outlier(self, features: FeatureVector) -> bool:
        """Return whether the forest itself calls ``features`` an outlier.

        :param features: one document's vector.
        :returns: the forest's own prediction, at the threshold scikit-learn
            fixed rather than one chosen here.
        :raises AnomalyError: on anything that is not a :class:`FeatureVector`.
        """
        if not isinstance(features, FeatureVector):
            raise AnomalyError("features must be a FeatureVector")
        prediction = self.forest.predict(np.asarray([features.as_array()]))[0]
        return bool(prediction == -1)

    def verdict(self, image: object) -> AnomalyVerdict:
        """Return what the fitted forest makes of one document.

        :param image: a document as :func:`feature_vector` takes it.
        :returns: one :class:`AnomalyVerdict` carrying the rank, the forest's
            raw score, its own outlier call and the vector behind them.
        :raises AnomalyError: on a document no family can measure.
        """
        features = feature_vector(image)
        return AnomalyVerdict(
            score=self.rank(features),
            raw=self.raw_score(features),
            outlier=self.outlier(features),
            features=features,
        )
