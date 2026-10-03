"""Error-level analysis: re-encode the frame and read where it disagrees with itself.

A JPEG block that has been through a second encoder still carries the first
encoder's artefacts, so re-encoding a capture and measuring the discrepancy
localises re-compression.  :func:`ela_heatmap` answers that measurement as a
normalised map, one cell per :data:`BLOCK_SIZE` block, and :class:`ELAModule`
wraps the map in the record D116 froze.

**The map is normalised against a committed ceiling, not against its own
maximum.**  Dividing by the largest block on the page would paint that page's
own noise across the whole scale, and a cell that reads fully hot because the
map was stretched to fit it is the one claim an overlay must not make.  A
block whose mean discrepancy reaches :data:`SATURATION` reads fully hot
instead, so two captures are read on one scale and neither is stretched to
fill it.

**The several qualities are averaged rather than maxed.**  Ringing around an
edge is present at every quality and is not evidence of anything, and a
maximum would promote it to a finding the moment one quality happened to
ring hardest; averaging damps what every codec does and leaves behind the
blocks that disagree for a reason.

**ELA measures re-compression, not tampering.**  The qualities, the
amplification and the ceiling are this repository's choices and nothing here
is calibrated against ground truth, so the module ships labelled ``is_stub``
and its ``detail`` says what was measured.  D117 holds the argument.
"""

import typing

import cv2
import numpy as np

from app.pipeline.tier2 import base

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "AMPLIFY",
    "BLOCK_SIZE",
    "ELAModule",
    "ELAError",
    "HOT_LEVEL",
    "MODEL_VERSION",
    "MODULE_NAME",
    "QUALITIES",
    "QUALITY_RANGE",
    "SATURATION",
    "block_means",
    "ela_heatmap",
    "error_map",
    "jpeg_round_trip",
    "normalise",
    "to_gray",
]

#: The name this module answers under, and the one its flag is traced to;
#: ``TAMPER_ELA_ANOMALY`` in the shipped weightset carries its weight.
MODULE_NAME = "tamper_ela"

#: What produced an answer: this rule's own version, to be bumped when it
#: moves rather than read off the file's date.
MODEL_VERSION = "ela-v0"

#: The JPEG qualities the frame is re-encoded at.  Several, because one
#: quality measures that one coder's mood: a block that disagrees at every
#: setting is doing something a block that disagrees at one is not.
QUALITIES = (75, 85, 95)

#: The range a quality must sit inside.  OpenCV clamps rather than refuses,
#: so a quality of 500 would quietly measure quality 100.
QUALITY_RANGE = (1, 100)

#: One JPEG block, so one heatmap cell is the unit the codec actually coded
#: rather than a window chosen for convenience.
BLOCK_SIZE = 8

#: How far the raw discrepancy is stretched before it is blocked.  A raw
#: per-pixel JPEG error is a handful of gray levels and reads as noise on a
#: map; the stretch is what makes it legible, and it is undone by
#: :data:`SATURATION`.
AMPLIFY = 20.0

#: The amplified mean discrepancy at which a block reads fully hot, which is
#: :data:`AMPLIFY` times three gray levels.  An untouched capture re-encodes
#: to well under one gray level of block mean, so three is past what the
#: capture's own noise and the codec's own quantisation produce.
SATURATION = 60.0

#: The normalised discrepancy at or above which a block is called hot, and
#: the line :attr:`ELAModule.run` counts above when it writes its sentence.
HOT_LEVEL = 0.5


class ELAError(ValueError):
    """Raised when a frame cannot be measured, or an argument is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps
    working.  A frame ELA cannot measure is refused rather than answered as a
    clean page, and D115's rule says the caller decides what to do with that.
    """


def _check_quality(quality: object) -> None:
    """Refuse ``quality`` unless it is a whole number inside :data:`QUALITY_RANGE`."""
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise ELAError("quality must be a whole number")
    low, high = QUALITY_RANGE
    if not low <= quality <= high:
        raise ELAError(f"quality must sit in [{low}, {high}]")


def _check_positive(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number above zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ELAError(f"{field} must be a real number")
    if not value > 0:
        raise ELAError(f"{field} must be above zero")


def to_gray(image: object) -> np.ndarray:
    """Return ``image`` as the one gray plane ELA measures.

    :param image: a capture as a ``numpy`` array, one, three or four channels.
    :returns: the capture's gray plane as ``float64``.
    :raises ELAError: unless it is a non-empty array of 8-bit pixels, since
        ELA reads gray levels and rescaling another dtype silently would be
        a measurement of a different picture.
    """
    if not isinstance(image, np.ndarray):
        raise ELAError("image must be a numpy array")
    if image.ndim not in (2, 3):
        raise ELAError("image must be two or three dimensional")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise ELAError("image must hold at least one pixel")
    if image.dtype != np.uint8:
        raise ELAError("image must hold 8-bit pixels")
    if image.ndim == 3:
        channels = image.shape[2]
        if channels == 1:
            image = image[:, :, 0]
        elif channels in (3, 4):
            colour = cv2.COLOR_BGR2GRAY if channels == 3 else cv2.COLOR_BGRA2GRAY
            image = cv2.cvtColor(image, colour)
        else:
            raise ELAError("image must hold one, three or four channels")
    return image.astype(np.float64)


def jpeg_round_trip(image: np.ndarray, quality: int) -> np.ndarray:
    """Return ``image`` re-encoded as JPEG at ``quality`` and decoded back.

    :param image: a gray plane or colour frame as :func:`to_gray` accepts it.
    :param quality: the JPEG quality to re-encode at, inside
        :data:`QUALITY_RANGE`.
    :returns: the decoded re-encode, in the frame's own channel count.
    :raises ELAError: on a quality outside the range, or an encoder that
        refused the frame or returned one it cannot decode.
    """
    _check_quality(quality)
    try:
        encoded, buffer = cv2.imencode(
            ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        )
    except cv2.error:
        raise ELAError("the JPEG encoder refused the frame") from None
    if not encoded:
        raise ELAError("the JPEG encoder refused the frame")
    decoded = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise ELAError("the JPEG encoder returned a frame it could not read back")
    return decoded


def error_map(gray: np.ndarray, quality: int, *, amplify: float = AMPLIFY) -> np.ndarray:
    """Return ``gray``'s amplified discrepancy against itself re-encoded.

    :param gray: one gray plane as :func:`to_gray` returns it.
    :param quality: the JPEG quality to re-encode at.
    :param amplify: how far the raw discrepancy is stretched, undone later by
        :data:`SATURATION`.
    :returns: one non-negative ``float64`` per pixel, in the frame's order.
    """
    _check_positive(amplify, "amplify")
    again = jpeg_round_trip(gray.astype(np.uint8), quality)
    return np.abs(gray - again.astype(np.float64)) * float(amplify)


def block_means(values: np.ndarray, block: int = BLOCK_SIZE) -> np.ndarray:
    """Return ``values`` averaged into whole ``block``-sized blocks.

    :param values: a two-dimensional array to reduce.
    :param block: the block side in pixels, :data:`BLOCK_SIZE` by default.
    :returns: a ``rows x cols`` array, one mean per whole block, where a
        partial block along an edge is dropped rather than averaged over
        fewer pixels than its neighbours.
    :raises ELAError: on a block side that is not a positive integer, or a
        frame too small to hold even one whole block.
    """
    if isinstance(block, bool) or not isinstance(block, int):
        raise ELAError("block must be a whole number of pixels")
    _check_positive(block, "block")
    height, width = values.shape
    rows, cols = height // block, width // block
    if rows < 1 or cols < 1:
        raise ELAError("the frame is smaller than one block")
    whole = values[: rows * block, : cols * block]
    return whole.reshape(rows, block, cols, block).mean(axis=(1, 3))


def normalise(blocks: np.ndarray, *, saturation: float = SATURATION) -> np.ndarray:
    """Return ``blocks`` clipped into ``[0, 1]`` against a committed ceiling.

    :param blocks: block means as :func:`block_means` returns them.
    :param saturation: the amplified discrepancy that reads fully hot.
    :returns: the same grid scaled so that ``saturation`` is 1.0.
    :raises ELAError: on a saturation that is not a real number above zero.
    """
    _check_positive(saturation, "saturation")
    return np.clip(blocks / float(saturation), 0.0, 1.0)


def ela_heatmap(
    image: object,
    *,
    qualities: typing.Sequence[int] = QUALITIES,
    block: int = BLOCK_SIZE,
    amplify: float = AMPLIFY,
    saturation: float = SATURATION,
) -> tuple[tuple[float, ...], ...]:
    """Return the capture's error-level map as normalised rows of numbers.

    :param image: the capture, as :func:`to_gray` accepts it.
    :param qualities: the JPEG qualities to re-encode at, more than one
        being the point; their block maps are averaged.
    :param block: the block side in pixels.
    :param amplify: how far each quality's discrepancy is stretched.
    :param saturation: the amplified discrepancy that reads fully hot.
    :returns: rows of ``float`` in ``[0, 1]``, top to bottom and left to
        right, one cell per whole block of the frame.
    :raises ELAError: on no quality at all, or a frame ELA cannot measure.
    """
    if not qualities:
        raise ELAError("qualities must name at least one JPEG quality")
    gray = to_gray(image)
    per_quality = [block_means(error_map(gray, quality, amplify=amplify), block) for quality in qualities]
    heatmap = normalise(np.mean(per_quality, axis=0), saturation=saturation)
    return tuple(tuple(round(float(cell), 4) for cell in row) for row in heatmap)


class ELAModule(base.DeepModule):
    """ELA behind the Tier 2 seam: a re-compression map, labelled as heuristic.

    It reads the working frame off the context it is handed and answers one
    D116 record whose heatmap is :func:`ela_heatmap`.  ``regions`` is left
    empty on purpose: 15.13 is the task that turns a heatmap into polygons,
    and a region derived here would be a second answer to that question.
    """

    name = MODULE_NAME

    def run(self, context: "ScreeningContext") -> base.DeepResult:
        """Return this capture's ELA record.

        :param context: the run's record; the working frame is on
            ``context.image``.
        :returns: one :class:`~app.pipeline.tier2.base.DeepResult` whose
            score is the worst block on the map and whose heatmap is the map.
        """
        heatmap = ela_heatmap(context.image)
        rows, cols = len(heatmap), len(heatmap[0])
        peak = max(max(row) for row in heatmap)
        hot = sum(1 for row in heatmap for cell in row if cell >= HOT_LEVEL)
        share = hot / (rows * cols)
        detail = (
            f"ELA re-encoded the capture at JPEG qualities "
            f"{', '.join(str(quality) for quality in QUALITIES)} and read {cols}x{rows} "
            f"blocks: the worst reads {peak:.2f}, {share:.0%} of blocks read at or "
            f"above {HOT_LEVEL:.2f}, and this is re-compression rather than tampering."
        )
        return base.DeepResult(
            module=self.name,
            score=peak,
            is_stub=True,
            model_version=MODEL_VERSION,
            detail=detail,
            heatmap=heatmap,
        )
