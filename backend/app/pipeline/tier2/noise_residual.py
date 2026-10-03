"""Noise-residual analysis: high-pass the capture and read where its noise departs.

A spliced or re-encoded region carries the noise of the source it came from
rather than the noise of the page it was pasted onto.  :func:`high_pass` answers
the capture minus a median of itself, :func:`block_variance` reduces that
residual to one variance per block, and :func:`noise_heatmap` reports each
block's distance from the page's own median noise as normalised rows.

**The map is measured against the page's own median, never against its own
maximum and never against an absolute noise level.**  A capture's absolute noise
is set by its scanner, lighting and encoder, none of which this repository can
calibrate, so the only comparison available offline is each block against the
rest of the same capture.  The departure is symmetric, because a denoised
splice is as inconsistent with its neighbours as a noisier one.

**A page carrying no measurable noise is refused rather than answered as a
clean one.**  With every block's variance at zero there is nothing to depart
from, and a ratio against zero is not a measurement.

This module says where a capture's noise is inconsistent and not why, so it
ships labelled ``is_stub``.  D118 holds the argument and the measured ceiling.
"""

import math
import typing

import cv2
import numpy as np

from app.pipeline.tier2 import base

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "ANOMALY_FACTOR",
    "HOT_LEVEL",
    "MODEL_VERSION",
    "MODULE_NAME",
    "RESIDUAL_KERNEL",
    "VARIANCE_BLOCK",
    "NoiseResidualError",
    "NoiseResidualModule",
    "block_variance",
    "high_pass",
    "noise_heatmap",
    "normalise",
    "to_gray",
]

#: The name this module answers under, and the one its flag is traced to.
MODULE_NAME = "tamper_noise_residual"

#: What produced an answer: this rule's own version, to be bumped when it
#: moves rather than read off the file's date.
MODEL_VERSION = "noise-residual-v0"

#: The median window's side in pixels.  A median rather than a mean, because a
#: document is full of edges and a mean high-pass answers those edges rather
#: than the noise underneath them.
RESIDUAL_KERNEL = 3

#: The block a variance is measured over.  The same side as ELA's, so the two
#: maps overlay cell for cell when 15.6 fuses them.
VARIANCE_BLOCK = 8

#: The ratio at which a block reads fully hot, in either direction from the
#: page's own median noise.  Measured, not chosen: on an untouched synthetic
#: page the worst block sits 2.0x the median, which reads 0.28, so 8x is four
#: times past what a capture's own noise produces.  D118 records the probe.
ANOMALY_FACTOR = 8.0

#: The normalised departure at or above which a block is called anomalous, and
#: the line :attr:`NoiseResidualModule.run` counts above.  The same line ELA
#: uses, so 15.6's fusion reads both modules on one scale.
HOT_LEVEL = 0.5


class NoiseResidualError(ValueError):
    """Raised when a frame cannot be measured, or an argument is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps
    working.  A frame noise residual cannot measure is refused rather than
    answered as a clean page, and D115's rule says the caller decides what to
    do with that.
    """


def _check_positive(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number above zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NoiseResidualError(f"{field} must be a real number")
    if not value > 0:
        raise NoiseResidualError(f"{field} must be above zero")


def to_gray(image: object) -> np.ndarray:
    """Return ``image`` as the one gray plane noise residual measures.

    This repeats :func:`~app.pipeline.tier2.ela.to_gray` rather than sharing
    it, so that this module's refusals are :class:`NoiseResidualError` and not
    ELA's: a caller catching one of the two cannot mistake a frame one of them
    can measure for a frame the other cannot.

    :param image: a capture as a ``numpy`` array, one, three or four channels.
    :returns: the capture's gray plane as ``float64``.
    :raises NoiseResidualError: unless it is a non-empty array of 8-bit pixels,
        since rescaling another dtype silently would measure another picture.
    """
    if not isinstance(image, np.ndarray):
        raise NoiseResidualError("image must be a numpy array")
    if image.ndim not in (2, 3):
        raise NoiseResidualError("image must be two or three dimensional")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise NoiseResidualError("image must hold at least one pixel")
    if image.dtype != np.uint8:
        raise NoiseResidualError("image must hold 8-bit pixels")
    if image.ndim == 3:
        channels = image.shape[2]
        if channels == 1:
            image = image[:, :, 0]
        elif channels in (3, 4):
            colour = cv2.COLOR_BGR2GRAY if channels == 3 else cv2.COLOR_BGRA2GRAY
            image = cv2.cvtColor(image, colour)
        else:
            raise NoiseResidualError("image must hold one, three or four channels")
    return image.astype(np.float64)


def high_pass(image: object, *, kernel: int = RESIDUAL_KERNEL) -> np.ndarray:
    """Return ``image`` minus a median of itself, one value per pixel.

    :param image: a gray plane or colour frame as :func:`to_gray` accepts it.
    :param kernel: the median window's side in pixels, an odd number.
    :returns: the residual in the frame's own order, as ``float64``.
    :raises NoiseResidualError: on an even, tiny or non-whole window, or a
        window wider than the frame, where the residual would answer the
        border rule rather than the capture.
    """
    if isinstance(kernel, bool) or not isinstance(kernel, int):
        raise NoiseResidualError("kernel must be a whole number of pixels")
    if kernel < 3 or kernel % 2 == 0:
        raise NoiseResidualError("kernel must be an odd number of at least 3")
    gray = to_gray(image)
    height, width = gray.shape
    if kernel > min(height, width):
        raise NoiseResidualError("kernel is wider than the frame")
    smoothed = cv2.medianBlur(gray.astype(np.uint8), kernel)
    return gray - smoothed.astype(np.float64)


def block_variance(values: np.ndarray, block: int = VARIANCE_BLOCK) -> np.ndarray:
    """Return the variance of ``values`` in each whole ``block``-sized block.

    :param values: a two-dimensional array to reduce.
    :param block: the block side in pixels, :data:`VARIANCE_BLOCK` by default.
    :returns: a ``rows x cols`` array, one variance per whole block, where a
        partial block along an edge is dropped rather than averaged over fewer
        pixels than its neighbours.
    :raises NoiseResidualError: on a block side that is not a whole positive
        number of pixels, or a frame too small to hold even one whole block.
    """
    if isinstance(block, bool) or not isinstance(block, int):
        raise NoiseResidualError("block must be a whole number of pixels")
    _check_positive(block, "block")
    height, width = values.shape
    rows, cols = height // block, width // block
    if rows < 1 or cols < 1:
        raise NoiseResidualError("the frame is smaller than one block")
    whole = values[: rows * block, : cols * block]
    return whole.reshape(rows, block, cols, block).var(axis=(1, 3))


def normalise(
    variances: np.ndarray,
    *,
    factor: float = ANOMALY_FACTOR,
    baseline: float | None = None,
) -> np.ndarray:
    """Return how far each block sits from the page's own median noise.

    :param variances: block variances as :func:`block_variance` returns them.
    :param factor: the ratio at which a block reads fully hot.
    :param baseline: the variance every block is compared against; defaults to
        the median of ``variances``.
    :returns: the same grid in ``[0, 1]``, rising with the log-ratio and so
        symmetric in both directions.
    :raises NoiseResidualError: on a factor that is not a real number above one,
        or a baseline at or below zero -- a page carrying no noise has nothing
        for a block to depart from, and answering it would be a clean page.
    """
    _check_positive(factor, "factor")
    if factor <= 1.0:
        raise NoiseResidualError("factor must be above 1")
    if baseline is None:
        measured = float(np.median(variances))
    elif isinstance(baseline, bool) or not isinstance(baseline, (int, float)):
        raise NoiseResidualError("baseline must be a real number")
    else:
        measured = float(baseline)
    if not measured > 0.0:
        raise NoiseResidualError("the page carries no noise to measure a departure from")
    # A block with no variance at all where the page has some is as anomalous as
    # any departure, so log2's divide-by-zero is left to clip at 1.0.
    with np.errstate(divide="ignore"):
        departure = np.abs(np.log2(variances / measured))
    return np.clip(departure / math.log2(factor), 0.0, 1.0)


def noise_heatmap(
    image: object,
    *,
    block: int = VARIANCE_BLOCK,
    kernel: int = RESIDUAL_KERNEL,
    factor: float = ANOMALY_FACTOR,
) -> tuple[tuple[float, ...], ...]:
    """Return the capture's noise-residual map as normalised rows of numbers.

    :param image: the capture, as :func:`to_gray` accepts it.
    :param block: the block a variance is measured over.
    :param kernel: the median window's side in pixels.
    :param factor: the ratio at which a block reads fully hot.
    :returns: rows of ``float`` in ``[0, 1]``, top to bottom and left to right,
        one cell per whole block of the frame.
    :raises NoiseResidualError: on a frame noise residual cannot measure.
    """
    variances = block_variance(high_pass(image, kernel=kernel), block=block)
    heatmap = normalise(variances, factor=factor)
    return tuple(tuple(round(float(cell), 4) for cell in row) for row in heatmap)


class NoiseResidualModule(base.DeepModule):
    """Noise residual behind the Tier 2 seam: a departure map, labelled as heuristic.

    It reads the working frame off the context it is handed and answers one D116
    record whose heatmap is :func:`noise_heatmap`.  ``regions`` is left empty on
    purpose: 15.13 turns a heatmap into polygons, and a region derived here
    would be a second answer to that question.
    """

    name = MODULE_NAME

    def run(self, context: "ScreeningContext") -> base.DeepResult:
        """Return this capture's noise-residual record.

        :param context: the run's record; the working frame is on
            ``context.image``.
        :returns: one :class:`~app.pipeline.tier2.base.DeepResult` whose score
            is the worst block on the map and whose heatmap is the map.
        """
        heatmap = noise_heatmap(context.image)
        rows, cols = len(heatmap), len(heatmap[0])
        peak = max(max(row) for row in heatmap)
        anomalous = sum(1 for row in heatmap for cell in row if cell >= HOT_LEVEL)
        share = anomalous / (rows * cols)
        detail = (
            f"Noise residual high-passed the capture with a {RESIDUAL_KERNEL}px median "
            f"and read {cols}x{rows} blocks against the page's own median noise: the "
            f"worst sits {peak:.2f} away from it, {share:.0%} of blocks sit at or above "
            f"{HOT_LEVEL:.2f}, and this is local inconsistency rather than tampering."
        )
        return base.DeepResult(
            module=self.name,
            score=peak,
            is_stub=True,
            model_version=MODEL_VERSION,
            detail=detail,
            heatmap=heatmap,
        )
