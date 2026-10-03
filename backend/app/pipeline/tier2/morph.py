"""Face-morph detection at the photo region, behind a labelled stand-in.

A morph is one portrait averaged with another, so it carries two signs that a
genuine capture does not: averaging cancels the fine detail a real photograph
holds, and it leaves the silhouette with two outlines where one subject was.
:func:`frequency_cue` reads the first and :func:`boundary_cue` the second, and
:func:`morph_score` averages them because neither cue alone is evidence, and
**one of them has been measured to need that**: one clean portrait of the
fifteen drawn reached a shape factor of 1.194, past :data:`BOUNDARY_LEVEL`,
which on its own would have been a finding against a genuine traveller.  The
frequency cue separated every clean portrait from every blend; the boundary cue
did not, and it is kept because it catches what the frequency cue catches
least.

**Both cues are measured after the region is resampled onto one canonical
grid.**  Read on the capture as it was photographed, the frequency cue is not a
property of the portrait at all -- it fell from 0.0397 at 80px to 0.0039 at
240px across four sizes of the *same* artwork, so any constant sat against it
would be describing the scanner rather than the face.  D120's answer to that
problem was a canonical grid, and it is the same one.

:class:`MorphClassifier` is the seam a trained model goes through, and
:class:`HeuristicMorphClassifier` is the stand-in behind it.  **The stand-in is
labelled ``heuristic-v0`` and ``is_stub``, and it never sets either to anything
else**: D122 holds why the two are attributes of the interface rather than of
the module, so no later swap can leave a real model's answer reading as a
heuristic's or the reverse.

**These cues measure averaged and doubled structure, not faces, and this
repository cannot tell the two apart.**  Measured on purpose: a block of body
text read 0.500 and a checkerboard 0.445, both suspect, because both are dense
with detail and both have a ragged outline.  **Nothing here decides whether a
region holds a portrait** -- :func:`boundary_cue` refuses a region with no
closed outline at all, which is the only absence it can name.  A caller that
knows where the portrait is should say so through :func:`MorphModule`'s region
seam rather than let this module find one.  D122 holds the measured lines and
this limit.
"""

import abc
import dataclasses
import math
import typing

import cv2
import numpy as np

from app.pipeline.tier2 import base

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "BOUNDARY_LEVEL",
    "BOUNDARY_SPAN",
    "CANONICAL",
    "FREQUENCY_LEVEL",
    "FREQUENCY_RING",
    "FREQUENCY_SPAN",
    "MODEL_VERSION",
    "MODULE_NAME",
    "NO_FACE",
    "SUSPECT_LEVEL",
    "HeuristicMorphClassifier",
    "MorphClassifier",
    "MorphError",
    "MorphModule",
    "MorphVerdict",
    "boundary_cue",
    "frequency_cue",
    "morph_score",
    "silhouette",
    "to_gray",
    "whole_frame",
]

#: The name this module answers under; ``TAMPER_MORPH_SUSPECTED`` in the
#: shipped weightset carries its weight.
MODULE_NAME = "tamper_morph"

#: What produced an answer.  **This string says the work was a heuristic and
#: not a model**, so it is owned by the interface rather than by the module:
#: :class:`HeuristicMorphClassifier` sets it and a trained classifier sets its
#: own, and neither can answer without saying which it was.  D122.
MODEL_VERSION = "heuristic-v0"

#: The side the photo region is resampled to before either cue is read, so a
#: portrait photographed at 80px and one at 240px are measured on one grid.
#: D120's answer, held again rather than shared.
CANONICAL = 64

#: The share of the region's radius above which spectral power counts as
#: detail.  Measured: at 0.25 a clean synthetic portrait and a blend of two
#: differ by 0.006, at 0.35 by 0.002, and 0.30 is where the two separate
#: furthest on every size tried.  D122 records the probe.
FREQUENCY_RING = 0.30

#: The share at or below which a portrait is called low-detail, and the span
#: over which it reaches a full cue.  **The level is the midpoint of a measured
#: gap, not a round number**: across 24 clean synthetic portraits the lowest
#: share was 0.0352 and across 24 blends the highest was 0.0338, and nothing
#: observed falls between them.  The span is the distance from the level to the
#: most depleted blend measured (0.0253).  D122.
FREQUENCY_LEVEL = 0.0345
FREQUENCY_SPAN = 0.0092

#: The shape factor at or above which a silhouette is called doubled, and the
#: span over which it reaches a full cue.  The factor is ``perimeter^2 /
#: (4*pi*area)``, which is 1.0 for a circle and 1.13 for a plain head, and rises
#: when a second outline is drawn inside the first.  **The level is a measured
#: gap midpoint, and a weaker one than the frequency line's**: the 24 portraits
#: the probe drew to place it topped out at 1.146 and the blends bottomed at
#: 1.178, but on 30 portraits the probe had not been tuned on a clean one
#: reached 1.194 and crossed it.  **This line does not separate on its own**,
#: which is why the score is a mean and why a portrait over it still reads
#: below :data:`SUSPECT_LEVEL`.  The span reaches the most irregular blend
#: measured (1.287).  D122.
BOUNDARY_LEVEL = 1.162
BOUNDARY_SPAN = 0.125

#: The score at or above which the answer names a suspected morph.  Measured
#: the same way: on 30 clean portraits and 30 blends the probe had not been
#: tuned on, the cleanest portrait reached 0.128 and the weakest blend 0.314,
#: so the midpoint 0.221 sits in a gap nothing observed occupies.  **This is a
#: line between two synthetic groups and not a calibrated threshold**, and D122
#: records what it would take to move it.
SUSPECT_LEVEL = 0.221

#: What a region that holds no portrait answers.  ``None``, not ``0.0``: a
#: text block measured at 0.500 by the same cues that read a blend, so scoring
#: it would report a clean page as a suspected morph.
NO_FACE = None


class MorphError(ValueError):
    """Raised when a region cannot be measured, or an argument is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps
    working, as D115 requires of everything Tier 2 raises.
    """


def _check_positive(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number above zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MorphError(f"{field} must be a real number")
    if not value > 0:
        raise MorphError(f"{field} must be above zero")


def _check_unit(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number in the closed unit interval."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MorphError(f"{field} must be a real number")
    if not 0.0 <= float(value) <= 1.0:
        raise MorphError(f"{field} must sit in [0, 1]")


def to_gray(region: object) -> np.ndarray:
    """Return ``region`` as the one gray plane the cues measure.

    :param region: a photo region as a ``numpy`` array, one, three or four
        channels.
    :returns: the region's gray plane as ``float64``.
    :raises MorphError: unless it is a non-empty array of 8-bit pixels, since
        rescaling another dtype silently would measure another picture.
    """
    if not isinstance(region, np.ndarray):
        raise MorphError("region must be a numpy array")
    if region.ndim not in (2, 3):
        raise MorphError("region must be two or three dimensional")
    if region.shape[0] < 1 or region.shape[1] < 1:
        raise MorphError("region must hold at least one pixel")
    if region.dtype != np.uint8:
        raise MorphError("region must hold 8-bit pixels")
    if region.ndim == 3:
        channels = region.shape[2]
        if channels == 1:
            region = region[:, :, 0]
        elif channels in (3, 4):
            colour = cv2.COLOR_BGR2GRAY if channels == 3 else cv2.COLOR_BGRA2GRAY
            region = cv2.cvtColor(region, colour)
        else:
            raise MorphError("region must hold one, three or four channels")
    return region.astype(np.float64)


def canonical(region: object, *, size: int = CANONICAL) -> np.ndarray:
    """Return ``region`` resampled onto the one grid both cues are read on.

    :param region: a photo region as :func:`to_gray` accepts it.
    :param size: the square both sides are resampled to; ``INTER_AREA``, which
        averages when shrinking rather than dropping detail.
    :returns: the region as a ``size``-square ``uint8`` array.
    :raises MorphError: on a size that is not a whole number of pixels above
        zero, or on a region smaller than the grid it is resampled to.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise MorphError("size must be a whole number of pixels above zero")
    gray = to_gray(region)
    if gray.shape[0] < size or gray.shape[1] < size:
        raise MorphError(
            f"region of {gray.shape[1]}x{gray.shape[0]} is smaller than the "
            f"{size}x{size} grid it is measured on"
        )
    return cv2.resize(
        gray.astype(np.uint8), (size, size), interpolation=cv2.INTER_AREA
    )


def frequency_cue(region: object, *, ring: float = FREQUENCY_RING) -> float:
    """How far ``region``'s fine detail has been averaged away, in ``[0, 1]``.

    The share of spectral power sitting outside ``ring`` of the centre, on the
    canonical grid.  **It is a share of the region's own power and not of a
    committed level**, so a dark portrait and a bright one are read alike.

    :param region: a photo region as :func:`to_gray` accepts it.
    :param ring: the share of the radius above which power counts as detail.
    :returns: ``0.0`` when the region holds its detail or more and ``1.0`` when
        it is :data:`FREQUENCY_SPAN` or more below :data:`FREQUENCY_LEVEL`.
    :raises MorphError: on a ring outside ``(0, 1)``, or on a region whose power
        is zero, which measures nothing to share.
    """
    if isinstance(ring, bool) or not isinstance(ring, (int, float)):
        raise MorphError("ring must be a real number")
    if not 0.0 < float(ring) < 1.0:
        raise MorphError("ring must sit strictly inside (0, 1)")
    grid = canonical(region).astype(np.float64)
    grid = grid - grid.mean()
    power = np.abs(np.fft.fftshift(np.fft.fft2(grid))) ** 2
    total = float(power.sum())
    if total <= 0.0:
        raise MorphError("region carries no power to share; it is one flat value")
    rows, cols = power.shape
    ys, xs = np.ogrid[:rows, :cols]
    radius = np.sqrt((ys - rows / 2) ** 2 + (xs - cols / 2) ** 2)
    detail = power[radius > float(ring) * (min(rows, cols) / 2)].sum()
    share = float(detail) / total
    _check_positive(FREQUENCY_SPAN, "FREQUENCY_SPAN")
    return float(np.clip((FREQUENCY_LEVEL - share) / FREQUENCY_SPAN, 0.0, 1.0))


def silhouette(region: object) -> np.ndarray:
    """Return the portrait's own outline as a mask, thresholded by Otsu.

    **The level is the region's own**, so a pale portrait and a dark one are
    separated the same way without a committed level that only fits one of
    them.
    """
    grid = canonical(region)
    level = float(cv2.threshold(grid, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])
    mask = (grid < level).astype(np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))


def boundary_cue(region: object) -> float:
    """How far ``region``'s outline has been doubled, in ``[0, 1]``.

    The largest silhouette's shape factor, ``perimeter^2 / (4*pi*area)``: 1.0 is
    a circle, and averaging two faces leaves a second outline inside the first
    that pushes the ratio up.  A region holding no closed outline answers
    :data:`NO_FACE`, because there is no portrait there to have been morphed.

    :returns: ``0.0`` at or below :data:`BOUNDARY_LEVEL` and ``1.0`` at or
        :data:`BOUNDARY_SPAN` above it.
    :raises MorphError: on a region holding no measurable outline, so a caller
        cannot mistake a refusal for a measured zero.
    """
    mask = silhouette(region)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count < 2:
        raise MorphError("region holds no portrait outline; there is no face to read")
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    contours, _ = cv2.findContours(
        (labels == largest).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    outline = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(outline))
    if area <= 0.0:
        raise MorphError("region holds no portrait outline; there is no face to read")
    perimeter = float(cv2.arcLength(outline, True))
    factor = (perimeter * perimeter) / (4.0 * math.pi * area)
    _check_positive(BOUNDARY_SPAN, "BOUNDARY_SPAN")
    return float(np.clip((factor - BOUNDARY_LEVEL) / BOUNDARY_SPAN, 0.0, 1.0))


@dataclasses.dataclass(frozen=True)
class MorphVerdict:
    """One classifier's answer about one photo region, with its cues beside it.

    ``score`` is the mean of the two cues and ``suspect`` is that score read
    against :data:`SUSPECT_LEVEL`.  Both cues are kept so an officer can see
    which one fired, which matters because neither is evidence on its own.
    """

    #: How strongly this classifier believes its own finding, in ``[0, 1]``.
    score: float

    #: The detail-deficit cue, in ``[0, 1]``.
    frequency: float

    #: The doubled-outline cue, in ``[0, 1]``.
    boundary: float

    #: Whether ``score`` reached :data:`SUSPECT_LEVEL`.
    suspect: bool

    def __post_init__(self) -> None:
        """Refuse a verdict whose score and its cues disagree."""
        _check_unit(self.score, "score")
        _check_unit(self.frequency, "frequency")
        _check_unit(self.boundary, "boundary")
        if not isinstance(self.suspect, bool):
            raise MorphError("suspect must be a bool")
        if self.suspect != (self.score >= SUSPECT_LEVEL):
            raise MorphError("suspect must be whether score reached the suspect level")


def morph_score(region: object) -> MorphVerdict:
    """Return what both cues together say about ``region``.

    :param region: a photo region as :func:`to_gray` accepts it.
    :returns: one :class:`MorphVerdict` whose score is the **mean** of the two
        cues.  Averaged rather than maxed, on ELA's rule that a maximum
        promotes one cue to a finding the other would have contradicted, and
        averaging damps what one measurement does on its own.
    :raises MorphError: when the region holds no portrait outline, per
        :func:`boundary_cue`.
    """
    frequency = frequency_cue(region)
    boundary = boundary_cue(region)
    score = (frequency + boundary) / 2.0
    return MorphVerdict(
        score=score,
        frequency=frequency,
        boundary=boundary,
        suspect=score >= SUSPECT_LEVEL,
    )


class MorphClassifier(abc.ABC):
    """The one question a morph detector is asked, and the shape of its answer.

    **``model_version`` and ``is_stub`` belong to this interface and not to the
    module that wraps it**, so the label travels with whatever answered and a
    trained classifier cannot be shipped reading as a heuristic.  A subclass
    that omits ``classify`` cannot be instantiated, so a classifier wired
    wrongly fails at construction rather than on the first document.
    """

    #: What produced this classifier's answers, and whether it is a stand-in.
    model_version: str
    is_stub: bool

    @abc.abstractmethod
    def classify(self, region: object) -> MorphVerdict:
        """Return what this classifier makes of one photo region.

        :param region: the photo region cut from the aligned frame, not the
            whole page: a cue measured over a text block is a measurement of
            the text block.
        :returns: one :class:`MorphVerdict` carrying the score and both cues.
        """
        raise NotImplementedError


class HeuristicMorphClassifier(MorphClassifier):
    """The stand-in behind :class:`MorphClassifier`: two cues, no model.

    It answers :attr:`is_stub` ``True`` and :attr:`model_version`
    ``heuristic-v0`` and cannot answer otherwise, so a caller's record says a
    heuristic produced every number in it.  **The real classifier 15.10 leaves
    room for goes behind this same interface** and sets both to its own values.
    """

    model_version = MODEL_VERSION
    is_stub = True

    def classify(self, region: object) -> MorphVerdict:
        """Return :func:`morph_score` on ``region``.

        :raises MorphError: when ``region`` holds no portrait outline.
        """
        return morph_score(region)


def whole_frame(context: "ScreeningContext") -> object:
    """Return the working frame itself, which is what the seam hands over.

    **This is the default region and it is named rather than implied**: nothing
    on :class:`~app.pipeline.orchestrator.ScreeningContext` says where a
    document's portrait is, so a module that claimed to have read the photo
    region off the context would be claiming a measurement it did not make.  A
    caller holding an aligned frame and a template passes
    :func:`~app.pipeline.tier1.face_align.photo_region` in its place.
    """
    return context.image


def _summarise(verdict: MorphVerdict) -> str:
    """Return the clause an officer reads, naming the verdict and both cues.

    **A verdict with no cue above its line is reported as nothing found, not as
    a suspicion.**  The two readings are not stylistic: a score of 0.00 said
    "no morph here" and wording it "a suspected face morph" is the same defect
    15.9 fixed for a registry, one level up.  D121's rule holds.
    """
    if not verdict.suspect:
        return (
            f"nothing found: detail share reads at {verdict.frequency:.2f} and the "
            f"outline at {verdict.boundary:.2f}, neither above its line, for a "
            f"combined {verdict.score:.2f} against a suspect line of "
            f"{SUSPECT_LEVEL:.2f}. That is a measurement of two cues and not a "
            f"verdict that the portrait is genuine."
        )
    reading = (
        "both cues above their lines"
        if verdict.frequency > 0.0 and verdict.boundary > 0.0
        else "one cue above its line and the other not, which the mean damps"
    )
    return (
        f"a suspected face morph: detail share reads low at "
        f"{verdict.frequency:.2f} and the outline reads doubled at "
        f"{verdict.boundary:.2f}, {reading}, for a combined {verdict.score:.2f} "
        f"against a suspect line of {SUSPECT_LEVEL:.2f}."
    )


class MorphModule(base.DeepModule):
    """Face-morph detection behind the Tier 2 seam, labelled as heuristic.

    It answers one D116 record whose score is
    :class:`HeuristicMorphClassifier`'s, and whose ``is_stub`` and
    ``model_version`` are the classifier's rather than this module's.  The
    ``heatmap`` is left empty on purpose: both cues are one number for the
    whole region, so there is no map to draw, and 15.13 is the task that turns
    a heatmap into polygons.
    """

    name = MODULE_NAME

    def __init__(
        self,
        classifier: MorphClassifier | None = None,
        region_of: typing.Callable[["ScreeningContext"], object] | None = None,
    ) -> None:
        """Hold the classifier and the region, refusing both once, here.

        :param classifier: the classifier to answer with; defaults to this
            module's own :class:`HeuristicMorphClassifier`.  **It is refused at
            construction rather than once per document**, on 15.9's rule that a
            seam checked per call is a seam checked too late.
        :param region_of: what names the region this module measures, given the
            context it was handed; defaults to :func:`whole_frame`.  **It is a
            seam rather than a constant because the cue is only meaningful over
            a portrait**: a caller holding an aligned frame and a template hands
            :func:`~app.pipeline.tier1.face_align.photo_region` in instead, and
            the record then names a photo region this module really did read.
        :raises MorphError: unless both are what they claim to be, so a caller
            cannot wire a stand-in in unlabelled or a region in unwired.
        """
        chosen = HeuristicMorphClassifier() if classifier is None else classifier
        if not isinstance(chosen, MorphClassifier):
            raise MorphError("classifier must be a MorphClassifier")
        if not isinstance(chosen.model_version, str) or not chosen.model_version.strip():
            raise MorphError("a classifier must say what produced it")
        if not isinstance(chosen.is_stub, bool):
            raise MorphError("a classifier must say whether it is a stand-in")
        if region_of is None:
            region_of = whole_frame
        if not callable(region_of):
            raise MorphError("region_of must be callable")
        self.classifier = chosen
        self.region_of = region_of

    def run(self, context: "ScreeningContext") -> base.DeepResult:
        """Return this capture's morph record.

        :param context: the run's record; the working frame is on
            ``context.image``.
        :returns: one :class:`~app.pipeline.tier2.base.DeepResult` whose score
            and version are the classifier's, never this module's.
        :raises MorphError: when ``context.image`` holds no portrait outline,
            which is D115's rule: a region that cannot be read is refused, not
            answered as a page with no morph on it.
        """
        region = self.region_of(context)
        verdict = self.classifier.classify(region)
        detail = (
            "Face morph measured the region this instance was pointed at with two "
            "cues and no model: "
            + _summarise(verdict)
            + " The cues measure averaged and doubled structure rather than faces, "
            "so a region holding no portrait can read as a morph, and none of this "
            "has been run against a real morphing attack."
        )
        return base.DeepResult(
            module=self.name,
            score=verdict.score,
            is_stub=self.classifier.is_stub,
            model_version=self.classifier.model_version,
            detail=detail,
        )
