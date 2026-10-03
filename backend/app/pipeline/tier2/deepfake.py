"""Synthetic-portrait detection at the photo region, behind a labelled stand-in.

A deepfake is a portrait no camera ever saw, so unlike a morph -- which is two
real captures averaged and therefore keeps a real sensor's grain -- it carries
none. :func:`flat_cue` reads that absence as the share of adjacent-pixel
gradients that are exactly zero, which a capture's own noise fills in and a
low-frequency reconstruction does not.

**This cue reads flatness, not provenance, and nothing here has been run
against a real deepfake.**  A block of body text measured 0.506 on it and a
checkerboard 0.000, so a text region reads as a suspected synthetic portrait and
a hard-edged pattern reads as clean.  A region flat enough to carry no power at
all is refused rather than scored (:func:`flat_share`), which is the only
absence this module can name.  **The cue is a share and so is far steadier across
capture sizes than an absolute level would be, but it is not size-invariant**:
added grain survives the canonical grid less well from a small source, so a
120px portrait re-grained past about 5.0 reads clean where a 320px one still
fires at 6.0.  D123 holds the sweep.

:class:`DeepfakeClassifier` is the seam a trained model goes through, and
:class:`HeuristicDeepfakeClassifier` is the stand-in behind it.  The stand-in is
labelled ``heuristic-v0`` and ``is_stub`` and never answers otherwise, so no
later swap can leave a real model's answer reading as a heuristic's.  D123 holds
the measured lines, the rejected second cue and this limit.
"""

import abc
import dataclasses
import typing

import cv2
import numpy as np

from app.pipeline.tier2 import base

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "CANONICAL",
    "GRADIENT_LEVEL",
    "GRADIENT_SPAN",
    "MODEL_VERSION",
    "MODULE_NAME",
    "NO_SIGNAL",
    "SUSPECT_LEVEL",
    "DeepfakeClassifier",
    "DeepfakeError",
    "DeepfakeModule",
    "DeepfakeVerdict",
    "HeuristicDeepfakeClassifier",
    "canonical",
    "deepfake_score",
    "flat_cue",
    "flat_share",
    "to_gray",
    "whole_frame",
]

#: The name this module answers under; ``TAMPER_DEEPFAKE_SUSPECTED`` in the
#: shipped weightset carries its weight.
MODULE_NAME = "tamper_deepfake"

#: What produced an answer, owned by the classifier rather than by this module.
#: The same string 15.10's morph stand-in uses: both are a heuristic at version
#: zero, and ``module`` on the record is what tells the two apart.  D122, held.
MODEL_VERSION = "heuristic-v0"

#: The side the photo region is resampled to before the cue is read, so a
#: portrait photographed at 120px and one at 320px are measured on one grid.
#: D120's answer, held again rather than shared on D38's rule.
CANONICAL = 64

#: The flat share at or above which a region is called reconstructed, and the
#: span over which it reaches a full cue.  **Both are measured, not chosen.**
#: The level is the midpoint of a gap the probe left across 840 clean captures
#: and 700 reconstructed ones: no clean capture rose above 0.1482 and none fell
#: below 0.1931.  The span is the distance from the level to the most extreme
#: reconstructed share measured, 0.9418.  D123.
GRADIENT_LEVEL = 0.1706
GRADIENT_SPAN = 0.7712

#: The score at or above which the answer names a suspected synthetic portrait.
#: **This line is very low and the measurement is why.**  The reconstructed group
#: spreads 0.029 to 1.00 once normalised, so the weakest one the probe drew
#: reads 0.023 against every clean capture's 0.000, and the midpoint of that gap
#: is 0.0116.  A line this low is a false-alarm risk on anything this repository
#: has not drawn, which D21 already raises about a stand-in reaching High on its
#: own.  D123 records it as unresolved rather than moving it to a rounder,
#  safer-sounding number the probe never produced.
SUSPECT_LEVEL = 0.0116

#: What a region too flat to measure answers.  ``None``, not ``0.0``: blank
#: paper reads a flat share of 1.000, which would report an empty region as the
#: strongest possible finding.
NO_SIGNAL = None


class DeepfakeError(ValueError):
    """Raised when a region cannot be measured, or an argument is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps working,
    as D115 requires of everything Tier 2 raises.
    """


def _check_positive(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number above zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DeepfakeError(f"{field} must be a real number")
    if not value > 0:
        raise DeepfakeError(f"{field} must be above zero")


def _check_unit(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number in the closed unit interval."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DeepfakeError(f"{field} must be a real number")
    if not 0.0 <= float(value) <= 1.0:
        raise DeepfakeError(f"{field} must sit in [0, 1]")


def to_gray(region: object) -> np.ndarray:
    """Return ``region`` as the one gray plane the cue measures.

    :param region: a photo region as a ``numpy`` array, one, three or four
        channels.
    :returns: the region's gray plane as ``float64``.
    :raises DeepfakeError: unless it is a non-empty array of 8-bit pixels, since
        rescaling another dtype silently would measure another picture.
    """
    if not isinstance(region, np.ndarray):
        raise DeepfakeError("region must be a numpy array")
    if region.ndim not in (2, 3):
        raise DeepfakeError("region must be two or three dimensional")
    if region.shape[0] < 1 or region.shape[1] < 1:
        raise DeepfakeError("region must hold at least one pixel")
    if region.dtype != np.uint8:
        raise DeepfakeError("region must hold 8-bit pixels")
    if region.ndim == 3:
        channels = region.shape[2]
        if channels == 1:
            region = region[:, :, 0]
        elif channels in (3, 4):
            colour = cv2.COLOR_BGR2GRAY if channels == 3 else cv2.COLOR_BGRA2GRAY
            region = cv2.cvtColor(region, colour)
        else:
            raise DeepfakeError("region must hold one, three or four channels")
    return region.astype(np.float64)


def canonical(region: object, *, size: int = CANONICAL) -> np.ndarray:
    """Return ``region`` resampled onto the one grid the cue is read on.

    :param region: a photo region as :func:`to_gray` accepts it.
    :param size: the square both sides are resampled to; ``INTER_AREA``, which
        averages when shrinking rather than dropping detail.
    :returns: the region as a ``size``-square ``uint8`` array.
    :raises DeepfakeError: on a size that is not a whole number of pixels above
        zero, or on a region smaller than the grid it is resampled to.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise DeepfakeError("size must be a whole number of pixels above zero")
    gray = to_gray(region)
    if gray.shape[0] < size or gray.shape[1] < size:
        raise DeepfakeError(
            f"region of {gray.shape[1]}x{gray.shape[0]} is smaller than the "
            f"{size}x{size} grid it is measured on"
        )
    return cv2.resize(
        gray.astype(np.uint8), (size, size), interpolation=cv2.INTER_AREA
    )


def flat_share(region: object) -> float:
    """The share of ``region``'s adjacent-pixel gradients that are exactly zero.

    A capture's own noise makes almost none of them zero; a reconstruction from
    a low-frequency basis leaves large stretches perfectly flat.

    :param region: a photo region as :func:`to_gray` accepts it.
    :returns: a share in ``[0, 1]``.
    :raises DeepfakeError: on a region carrying no power to share, which is
        :data:`NO_SIGNAL` rather than a measurement of 1.0.
    """
    grid = canonical(region).astype(np.float64)
    if float(grid.var()) <= 0.0:
        raise DeepfakeError("region carries no power to share; it is one flat value")
    horizontal = np.abs(np.diff(grid, axis=1)).ravel()
    vertical = np.abs(np.diff(grid, axis=0)).ravel()
    gradients = np.concatenate((horizontal, vertical))
    return float((gradients == 0.0).mean())


def flat_cue(region: object) -> float:
    """How far ``region``'s flatness has gone, in ``[0, 1]``.

    :param region: a photo region as :func:`to_gray` accepts it.
    :returns: ``0.0`` at or below :data:`GRADIENT_LEVEL` and ``1.0`` at or
        :data:`GRADIENT_SPAN` above it.
    :raises DeepfakeError: on a region carrying no power to share.
    """
    share = flat_share(region)
    _check_positive(GRADIENT_SPAN, "GRADIENT_SPAN")
    return float(np.clip((share - GRADIENT_LEVEL) / GRADIENT_SPAN, 0.0, 1.0))


@dataclasses.dataclass(frozen=True)
class DeepfakeVerdict:
    """One classifier's answer about one photo region, with its cue beside it.

    ``score`` is the cue and ``suspect`` is that score read against
    :data:`SUSPECT_LEVEL`.  The cue is kept so an officer can see what fired,
    which matters because there is only one of them and no second reading to
    corroborate it.
    """

    #: How strongly this classifier believes its own finding, in ``[0, 1]``.
    score: float

    #: The flat-share cue, in ``[0, 1]``.
    flat: float

    #: Whether ``score`` reached :data:`SUSPECT_LEVEL`.
    suspect: bool

    def __post_init__(self) -> None:
        """Refuse a verdict whose score and its suspect flag disagree."""
        _check_unit(self.score, "score")
        _check_unit(self.flat, "flat")
        if not isinstance(self.suspect, bool):
            raise DeepfakeError("suspect must be a bool")
        if self.suspect != (self.score >= SUSPECT_LEVEL):
            raise DeepfakeError("suspect must be whether score reached the suspect level")


def deepfake_score(region: object) -> DeepfakeVerdict:
    """Return what the cue says about ``region``.

    :param region: a photo region as :func:`to_gray` accepts it.
    :returns: one :class:`DeepfakeVerdict`.  **The score is the cue itself, with
        no mean over a second reading**, because a second candidate was probed
        and rejected: a chroma noise-floor cue collapsed to 0.000 on
        reconstructed content re-grained past 2.5 while clean captures reached
        0.250, so averaging it in would have hidden detections rather than
        damping them.  D123 records the numbers.
    :raises DeepfakeError: when the region carries no power to share.
    """
    cue = flat_cue(region)
    return DeepfakeVerdict(score=cue, flat=cue, suspect=cue >= SUSPECT_LEVEL)


class DeepfakeClassifier(abc.ABC):
    """The one question a deepfake detector is asked, and the shape of its answer.

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
    def classify(self, region: object) -> DeepfakeVerdict:
        """Return what this classifier makes of one photo region.

        :param region: the photo region cut from the aligned frame, not the
            whole page: a cue measured over a text block is a measurement of
            the text block.
        :returns: one :class:`DeepfakeVerdict` carrying the score and its cue.
        """
        raise NotImplementedError


class HeuristicDeepfakeClassifier(DeepfakeClassifier):
    """The stand-in behind :class:`DeepfakeClassifier`: one cue, no model.

    It answers :attr:`is_stub` ``True`` and :attr:`model_version``
    ``heuristic-v0`` and cannot answer otherwise, so a caller's record says a
    heuristic produced every number in it.
    """

    model_version = MODEL_VERSION
    is_stub = True

    def classify(self, region: object) -> DeepfakeVerdict:
        """Return :func:`deepfake_score` on ``region``.

        :raises DeepfakeError: when ``region`` carries no power to share.
        """
        return deepfake_score(region)


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


def _summarise(verdict: DeepfakeVerdict) -> str:
    """Return the clause an officer reads, naming the verdict and its cue.

    **A verdict below the line is reported as nothing found, not as a
    suspicion.**  The two readings are not stylistic: a score of 0.00 worded
    "a suspected synthetic portrait" is the defect 15.9 fixed for a registry and
    15.10 for a morph, one level up.  D121's rule holds.
    """
    if not verdict.suspect:
        return (
            f"nothing found: the flat share reads at {verdict.flat:.3f}, at or "
            f"below its line of {GRADIENT_LEVEL:.3f}. That is a measurement of "
            f"one cue and not a verdict that the portrait is genuine."
        )
    return (
        f"a suspected synthetic portrait: the flat share reads at "
        f"{verdict.flat:.3f} against a line of {GRADIENT_LEVEL:.3f}, for a "
        f"combined {verdict.score:.3f} against a suspect line of "
        f"{SUSPECT_LEVEL:.3f}."
    )


class DeepfakeModule(base.DeepModule):
    """Synthetic-portrait detection behind the Tier 2 seam, labelled heuristic.

    It answers one D116 record whose score is
    :class:`HeuristicDeepfakeClassifier`'s, and whose ``is_stub`` and
    ``model_version`` are the classifier's rather than this module's.  The
    ``heatmap`` is left empty on purpose: the cue is one number for the whole
    region, so there is no map to draw.
    """

    name = MODULE_NAME

    def __init__(
        self,
        classifier: DeepfakeClassifier | None = None,
        region_of: typing.Callable[["ScreeningContext"], object] | None = None,
    ) -> None:
        """Hold the classifier and the region, refusing both once, here.

        :param classifier: the classifier to answer with; defaults to this
            module's own :class:`HeuristicDeepfakeClassifier`.  **It is refused
            at construction rather than once per document**, on 15.9's rule that
            a seam checked per call is a seam checked too late.
        :param region_of: what names the region this module measures, given the
            context it was handed; defaults to :func:`whole_frame`.  **It is a
            seam because the cue is only meaningful over a portrait**: a caller
            holding an aligned frame and a template hands
            :func:`~app.pipeline.tier1.face_align.photo_region` in instead.
        :raises DeepfakeError: unless both are what they claim to be, so a caller
            cannot wire a stand-in in unlabelled or a region in unwired.
        """
        chosen = (
            HeuristicDeepfakeClassifier() if classifier is None else classifier
        )
        if not isinstance(chosen, DeepfakeClassifier):
            raise DeepfakeError("classifier must be a DeepfakeClassifier")
        if not isinstance(chosen.model_version, str) or not chosen.model_version.strip():
            raise DeepfakeError("a classifier must say what produced it")
        if not isinstance(chosen.is_stub, bool):
            raise DeepfakeError("a classifier must say whether it is a stand-in")
        if region_of is None:
            region_of = whole_frame
        if not callable(region_of):
            raise DeepfakeError("region_of must be callable")
        self.classifier = chosen
        self.region_of = region_of

    def run(self, context: "ScreeningContext") -> base.DeepResult:
        """Return this capture's deepfake record.

        :param context: the run's record; the working frame is on
            ``context.image``.
        :returns: one :class:`~app.pipeline.tier2.base.DeepResult` whose score
            and version are the classifier's, never this module's.
        :raises DeepfakeError: when ``context.image`` carries no power to
            share, which is D115's rule: a region that cannot be read is
            refused, not answered as a page with nothing synthetic on it.
        """
        region = self.region_of(context)
        verdict = self.classifier.classify(region)
        detail = (
            "Deepfake measured the region this instance was pointed at with one "
            "cue and no model: "
            + _summarise(verdict)
            + " The cue reads how much of the region is piecewise flat rather than "
            "whether anything generated it, so a text block reads as suspected and "
            "a hard-edged pattern reads as clean, and no real deepfake has ever "
            "been scored against it."
        )
        return base.DeepResult(
            module=self.name,
            score=verdict.score,
            is_stub=self.classifier.is_stub,
            model_version=self.classifier.model_version,
            detail=detail,
        )
