"""Copy-move detection: match a capture's keypoints against the capture itself.

A region pasted from elsewhere in the same document leaves two places carrying
the same keypoints one translation apart, so :func:`copy_move_heatmap` measures
where the capture agrees with itself and :func:`copy_move_regions` answers where
that agreement sits.

**A translation is believed only when enough keypoint pairs agree on it.**  A
single self-similar pair is repeated texture -- a document is full of it -- and
:data:`MIN_COPIES` pairs agreeing on one shift is what separates a copied
region from the page's own furniture.

**The map is normalised against a committed ceiling, not its own maximum**
(D117's rule), so two captures are read on one scale and neither is stretched
to fill it.

**Translation only.**  A scaled, rotated or mirrored duplicate is a different
measurement and is not attempted here.

**Repeated content is not tampering.**  A letterhead, a repeated table row and
a forged duplicate are the same finding to this measurement, so the module
ships labelled ``is_stub`` and its detail says so.  D119 holds the argument and
the measured constants.
"""

import dataclasses
import math
import typing

import cv2
import numpy as np

from app.pipeline.tier2 import base

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "BLOCK_SIZE",
    "HOT_LEVEL",
    "MAX_FEATURES",
    "MIN_COPIES",
    "MIN_FEATURES",
    "MIN_SHIFT",
    "MODEL_VERSION",
    "MODULE_NAME",
    "RATIO",
    "REGION_MERGE",
    "SATURATION",
    "SHIFT_TOLERANCE",
    "CopyCluster",
    "CopyMatch",
    "CopyMoveError",
    "CopyMoveModule",
    "copy_clusters",
    "copy_move_heatmap",
    "copy_move_regions",
    "detect",
    "normalise",
    "region_polygons",
    "self_matches",
    "to_gray",
    "translate_clusters",
    "vote_map",
]

#: The name this module answers under, and the one its flag is traced to.
MODULE_NAME = "tamper_copy_move"

#: What produced an answer: this rule's own version, to be bumped when it moves.
MODEL_VERSION = "copy-move-v0"

#: The keypoint budget a capture is searched with.  A ceiling rather than a
#: target: SIFT returns what the texture gives it, and a flat page returns few.
MAX_FEATURES = 6000

#: Below this many features there is nothing to match, so the capture is refused.
MIN_FEATURES = 2

#: The descriptor distance at which the nearest match is half as close as the
#: runner-up, which is what makes a self-match distinguishable from a guess.
RATIO = 0.6

#: The smallest translation, in pixels, a pair may carry and still count.  A
#: keypoint matched to its own immediate neighbourhood is the same structure
#: twice over, not a second copy of it.
MIN_SHIFT = 24.0

#: The pixel size of the bin two shifts must fall in to be called the same
#: translation, which absorbs a detector's localisation error.
SHIFT_TOLERANCE = 16.0

#: How many pairs must agree on one translation before it is called a copy.
#: Measured: an untouched synthetic page's largest agreeing group is 3, and the
#: same page with a 150x150 region pasted elsewhere reaches 121.
MIN_COPIES = 8

#: The block a match votes in.  The same side as ELA's and noise residual's, so
#: 15.6's fusion reads all three maps cell for cell.
BLOCK_SIZE = 8

#: The agreeing pairs in one block at which a cell reads fully hot.  Measured:
#: the most common block of a copied region carries 4 and none of an untouched
#: page carries any, so 4 separates them completely.
SATURATION = 4.0

#: The normalised value at or above which a block is called copied, and the line
#: :attr:`CopyMoveModule.run` counts above.  The same line the other two modules
#: use, so 15.6's fusion reads all three on one line.
HOT_LEVEL = 0.5

#: The distance within which two matched keypoints are taken to be part of the
#: same copied region.  Measured: the two lobes of a copy stay separate from 32
#: to 128 pixels, and 48 sits inside that plateau.
REGION_MERGE = 48.0


class CopyMoveError(ValueError):
    """Raised when a frame cannot be matched, or an argument is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps working.
    A capture carrying too little texture to match against itself is refused
    rather than answered as a page with no copy in it.
    """


def _check_positive(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number above zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CopyMoveError(f"{field} must be a real number")
    if not value > 0:
        raise CopyMoveError(f"{field} must be above zero")


def _check_whole(value: object, field: str, *, least: int) -> None:
    """Refuse ``value`` unless it is a whole number of at least ``least``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CopyMoveError(f"{field} must be a whole number")
    if value < least:
        raise CopyMoveError(f"{field} must be at least {least}")


def to_gray(image: object) -> np.ndarray:
    """Return ``image`` as the one gray plane copy-move measures.

    This repeats :func:`~app.pipeline.tier2.ela.to_gray` rather than sharing
    it, so that this module's refusals are :class:`CopyMoveError` and not
    ELA's: a caller catching one of the three cannot mistake a frame one of
    them can measure for a frame another cannot.

    :param image: a capture as a ``numpy`` array, one, three or four channels.
    :returns: the capture's gray plane as ``float64``.
    :raises CopyMoveError: unless it is a non-empty array of 8-bit pixels.
    """
    if not isinstance(image, np.ndarray):
        raise CopyMoveError("image must be a numpy array")
    if image.ndim not in (2, 3):
        raise CopyMoveError("image must be two or three dimensional")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise CopyMoveError("image must hold at least one pixel")
    if image.dtype != np.uint8:
        raise CopyMoveError("image must hold 8-bit pixels")
    if image.ndim == 3:
        channels = image.shape[2]
        if channels == 1:
            image = image[:, :, 0]
        elif channels in (3, 4):
            colour = cv2.COLOR_BGR2GRAY if channels == 3 else cv2.COLOR_BGRA2GRAY
            image = cv2.cvtColor(image, colour)
        else:
            raise CopyMoveError("image must hold one, three or four channels")
    return image.astype(np.float64)


@dataclasses.dataclass(frozen=True)
class CopyMatch:
    """One keypoint the capture matched to another of its own keypoints.

    ``source`` and ``copy`` are ``(x, y)`` positions in the capture's own
    pixels and ``shift`` is the translation from one to the other.
    """

    source: tuple[float, float]
    copy: tuple[float, float]
    shift: tuple[float, float]

    def __post_init__(self) -> None:
        for name in ("source", "copy", "shift"):
            pair = getattr(self, name)
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not all(
                    isinstance(part, (int, float)) and not isinstance(part, bool)
                    for part in pair
                )
            ):
                raise CopyMoveError(f"{name} must be a pair of real numbers")


@dataclasses.dataclass(frozen=True)
class CopyCluster:
    """The keypoint pairs that agreed on one translation: one copy-move.

    ``matches`` holds at least :data:`MIN_COPIES` pairs by construction, which
    is what separates a copied region from the page's own repeated furniture.
    """

    shift: tuple[float, float]
    matches: tuple[CopyMatch, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.matches, tuple) or len(self.matches) < 2:
            raise CopyMoveError("a cluster must hold at least two matches")
        if not all(isinstance(match, CopyMatch) for match in self.matches):
            raise CopyMoveError("a cluster must hold CopyMatch pairs")


def detect(
    image: object, *, max_features: int = MAX_FEATURES
) -> tuple[tuple[tuple[float, float], ...], np.ndarray]:
    """Return the capture's keypoint positions and their SIFT descriptors.

    :param image: the capture, as :func:`to_gray` accepts it.
    :param max_features: the keypoint budget the search runs under.
    :returns: positions as ``(x, y)`` floats in detector order, and the
        descriptor matrix those positions describe.
    :raises CopyMoveError: on a frame that cannot be measured, or one carrying
        fewer than :data:`MIN_FEATURES` features -- there is nothing there to
        match against itself.
    """
    _check_whole(max_features, "max_features", least=1)
    gray = to_gray(image)
    detector = cv2.SIFT_create(nfeatures=max_features)
    keypoints, descriptors = detector.detectAndCompute(gray.astype(np.uint8), None)
    if descriptors is None or len(keypoints) < MIN_FEATURES:
        raise CopyMoveError("the capture carries too little texture to match")
    points = tuple((float(k.pt[0]), float(k.pt[1])) for k in keypoints)
    return points, descriptors


def self_matches(
    points: object,
    descriptors: object,
    *,
    ratio: float = RATIO,
    min_shift: float = MIN_SHIFT,
) -> tuple[CopyMatch, ...]:
    """Return the pairs of the capture's own keypoints that match each other.

    Each keypoint is compared against every other one, its nearest rival and
    the runner-up excluded, and a pair stands only when the nearest is close
    enough relative to the runner-up and far enough away to be a second place
    rather than the same structure twice.

    :param points: positions as :func:`detect` returns them.
    :param descriptors: the matching descriptor matrix.
    :param ratio: the distance at which the nearest match is refused.
    :param min_shift: the smallest translation, in pixels, a pair may carry.
    :returns: every pair that stood, in detector order.
    :raises CopyMoveError: on arguments that cannot be measured, or a descriptor
        matrix that does not describe the positions handed over.
    """
    if not isinstance(points, tuple) or len(points) < MIN_FEATURES:
        raise CopyMoveError("points must hold at least two positions")
    if not isinstance(descriptors, np.ndarray) or len(descriptors) != len(points):
        raise CopyMoveError("descriptors must be one row per point")
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
        raise CopyMoveError("ratio must be a real number")
    if not 0.0 < float(ratio) < 1.0:
        raise CopyMoveError("ratio must sit strictly between 0 and 1")
    _check_positive(min_shift, "min_shift")

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    found: list[CopyMatch] = []
    for index, group in enumerate(matcher.knnMatch(descriptors, descriptors, k=3)):
        others = [m for m in group if m.trainIdx != index]
        if len(others) < 2:
            continue
        nearest, runner_up = others[0], others[1]
        if nearest.distance <= 0.0 or nearest.distance / runner_up.distance >= ratio:
            continue
        rival = int(nearest.trainIdx)
        shift = (points[rival][0] - points[index][0], points[rival][1] - points[index][1])
        if math.hypot(*shift) < min_shift:
            continue
        found.append(CopyMatch(points[index], points[rival], shift))
    return tuple(found)


def translate_clusters(
    matches: object,
    *,
    tolerance: float = SHIFT_TOLERANCE,
    min_copies: int = MIN_COPIES,
) -> tuple[CopyCluster, ...]:
    """Return the groups of matches that agree on one translation.

    :param matches: pairs as :func:`self_matches` returns them.
    :param tolerance: the pixel size of the bin two shifts share to be called
        the same translation.
    :param min_copies: the pairs a translation must carry to be kept.
    :returns: the surviving translations, largest group first, each with the
        mean shift its group agreed on.
    :raises CopyMoveError: on arguments that cannot be measured, or a minimum
        below two -- one pair is a coincidence, not a translation.
    """
    _check_positive(tolerance, "tolerance")
    _check_whole(min_copies, "min_copies", least=2)
    if not isinstance(matches, tuple):
        raise CopyMoveError("matches must be a tuple of pairs")
    if not all(isinstance(match, CopyMatch) for match in matches):
        raise CopyMoveError("matches must hold CopyMatch pairs")

    bins: dict[tuple[int, int], list[CopyMatch]] = {}
    for match in matches:
        key = (
            int(round(match.shift[0] / tolerance)),
            int(round(match.shift[1] / tolerance)),
        )
        bins.setdefault(key, []).append(match)
    clusters = []
    for group in bins.values():
        if len(group) < min_copies:
            continue
        shift = (
            float(np.mean([m.shift[0] for m in group])),
            float(np.mean([m.shift[1] for m in group])),
        )
        clusters.append(CopyCluster(shift=shift, matches=tuple(group)))
    clusters.sort(key=lambda cluster: (-len(cluster.matches), cluster.shift))
    return tuple(clusters)


def copy_clusters(
    image: object,
    *,
    max_features: int = MAX_FEATURES,
    ratio: float = RATIO,
    min_shift: float = MIN_SHIFT,
    tolerance: float = SHIFT_TOLERANCE,
    min_copies: int = MIN_COPIES,
) -> tuple[CopyCluster, ...]:
    """Return the capture's translations that enough keypoint pairs agree on.

    :param image: the capture, as :func:`to_gray` accepts it.
    :returns: the copy-moves the capture carries, largest first.
    :raises CopyMoveError: on a frame copy-move cannot measure.
    """
    points, descriptors = detect(image, max_features=max_features)
    matches = self_matches(points, descriptors, ratio=ratio, min_shift=min_shift)
    return translate_clusters(matches, tolerance=tolerance, min_copies=min_copies)


def vote_map(
    clusters: object, shape: tuple[int, int], *, block: int = BLOCK_SIZE
) -> np.ndarray:
    """Return how many matched keypoints land in each block of the capture.

    :param clusters: copy-moves as :func:`copy_clusters` returns them.
    :param shape: the capture's ``(height, width)`` in pixels.
    :param block: the block side in pixels, :data:`BLOCK_SIZE` by default.
    :returns: a ``rows x cols`` array counting both ends of every pair, where a
        partial block along an edge is dropped rather than half counted.
    :raises CopyMoveError: on a frame too small to hold even one whole block, or
        arguments that cannot be measured.
    """
    if not isinstance(shape, tuple) or len(shape) != 2:
        raise CopyMoveError("shape must be a (height, width) pair")
    if not all(isinstance(side, int) and not isinstance(side, bool) for side in shape):
        raise CopyMoveError("shape must hold whole pixel counts")
    if not all(side > 0 for side in shape):
        raise CopyMoveError("shape must hold a positive frame")
    _check_whole(block, "block", least=1)
    if not isinstance(clusters, tuple) or not all(
        isinstance(cluster, CopyCluster) for cluster in clusters
    ):
        raise CopyMoveError("clusters must be a tuple of CopyCluster")

    rows, cols = shape[0] // block, shape[1] // block
    if rows < 1 or cols < 1:
        raise CopyMoveError("the frame is smaller than one block")
    votes = np.zeros((rows, cols))
    for cluster in clusters:
        for match in cluster.matches:
            for point in (match.source, match.copy):
                row, col = int(point[1]) // block, int(point[0]) // block
                if 0 <= row < rows and 0 <= col < cols:
                    votes[row, col] += 1
    return votes


def normalise(votes: object, *, ceiling: float = SATURATION) -> np.ndarray:
    """Return each block's agreeing pairs as a fraction of the ceiling.

    :param votes: block counts as :func:`vote_map` returns them.
    :param ceiling: the agreeing pairs in one block at which it reads fully hot.
    :returns: the same grid clipped into ``[0, 1]``, rising with the count.
    :raises CopyMoveError: on a ceiling that is not a real number above zero,
        which would divide by nothing.
    """
    _check_positive(ceiling, "ceiling")
    if not isinstance(votes, np.ndarray):
        raise CopyMoveError("votes must be a numpy array")
    return np.clip(votes / float(ceiling), 0.0, 1.0)


def copy_move_heatmap(
    image: object,
    *,
    block: int = BLOCK_SIZE,
    ceiling: float = SATURATION,
    max_features: int = MAX_FEATURES,
    ratio: float = RATIO,
    min_shift: float = MIN_SHIFT,
    tolerance: float = SHIFT_TOLERANCE,
    min_copies: int = MIN_COPIES,
) -> tuple[tuple[float, ...], ...]:
    """Return the capture's copy-move map as normalised rows of numbers.

    :param image: the capture, as :func:`to_gray` accepts it.
    :returns: rows of ``float`` in ``[0, 1]``, top to bottom and left to right,
        one cell per whole block, counting how many matched keypoints the block
        carries.
    :raises CopyMoveError: on a frame copy-move cannot measure.
    """
    gray = to_gray(image)
    clusters = copy_clusters(
        image,
        max_features=max_features,
        ratio=ratio,
        min_shift=min_shift,
        tolerance=tolerance,
        min_copies=min_copies,
    )
    votes = vote_map(clusters, gray.shape, block=block)
    heatmap = normalise(votes, ceiling=ceiling)
    return tuple(tuple(round(float(cell), 4) for cell in row) for row in heatmap)


def region_polygons(
    clusters: object,
    shape: tuple[int, int],
    *,
    merge: float = REGION_MERGE,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return one box per group of matched keypoints, as whole-pixel polygons.

    Matched keypoints within :data:`REGION_MERGE` of one another are one copied
    region; the two ends of a copy are far enough apart to stay two boxes.
    Corners run clockwise from the top left with an exclusive far corner, the
    order :func:`~app.pipeline.tier0.mrz_region._box_polygon` promises, and are
    plain integers so a polygon cannot pick up a numpy scalar at a boundary.

    :param clusters: copy-moves as :func:`copy_clusters` returns them.
    :param shape: the capture's ``(height, width)`` in pixels.
    :param merge: the distance within which two matched keypoints join.
    :returns: the boxes, in the order the groups were first seen.
    :raises CopyMoveError: on arguments that cannot be measured.
    """
    _check_positive(merge, "merge")
    if not isinstance(shape, tuple) or len(shape) != 2:
        raise CopyMoveError("shape must be a (height, width) pair")
    if not all(isinstance(side, int) and not isinstance(side, bool) for side in shape):
        raise CopyMoveError("shape must hold whole pixel counts")
    if not all(side > 0 for side in shape):
        raise CopyMoveError("shape must hold a positive frame")
    if not isinstance(clusters, tuple) or not all(
        isinstance(cluster, CopyCluster) for cluster in clusters
    ):
        raise CopyMoveError("clusters must be a tuple of CopyCluster")

    height, width = shape
    points = [p for cluster in clusters for match in cluster.matches for p in (match.source, match.copy)]
    if not points:
        return ()

    parent = list(range(len(points)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    grid: dict[tuple[int, int], list[int]] = {}
    for index, point in enumerate(points):
        grid.setdefault((int(point[1] // merge), int(point[0] // merge)), []).append(index)
    for (row, col), members in grid.items():
        for index in members:
            for drow in (-1, 0, 1):
                for dcol in (-1, 0, 1):
                    for other in grid.get((row + drow, col + dcol), ()):
                        if other <= index:
                            continue
                        gap = math.hypot(
                            points[index][0] - points[other][0],
                            points[index][1] - points[other][1],
                        )
                        if gap <= merge:
                            parent[find(index)] = find(other)

    groups: dict[int, list[tuple[float, float]]] = {}
    for index, point in enumerate(points):
        groups.setdefault(find(index), []).append(point)

    polygons = []
    for members in groups.values():
        array = np.array(members, dtype=np.float64)
        left = max(0, int(np.floor(array[:, 0].min())))
        top = max(0, int(np.floor(array[:, 1].min())))
        right = min(width, int(np.ceil(array[:, 0].max())) + 1)
        bottom = min(height, int(np.ceil(array[:, 1].max())) + 1)
        polygons.append(((left, top), (right, top), (right, bottom), (left, bottom)))
    return tuple(polygons)


def copy_move_regions(
    image: object,
    *,
    merge: float = REGION_MERGE,
    max_features: int = MAX_FEATURES,
    ratio: float = RATIO,
    min_shift: float = MIN_SHIFT,
    tolerance: float = SHIFT_TOLERANCE,
    min_copies: int = MIN_COPIES,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return where the capture's copies sit, as whole-pixel polygons.

    :param image: the capture, as :func:`to_gray` accepts it.
    :returns: one box per copied region, empty when the capture carries none.
    :raises CopyMoveError: on a frame copy-move cannot measure.
    """
    gray = to_gray(image)
    clusters = copy_clusters(
        image,
        max_features=max_features,
        ratio=ratio,
        min_shift=min_shift,
        tolerance=tolerance,
        min_copies=min_copies,
    )
    return region_polygons(clusters, gray.shape, merge=merge)


class CopyMoveModule(base.DeepModule):
    """Copy-move behind the Tier 2 seam: where the capture agrees with itself.

    It reads the working frame off the context it is handed and answers one D116
    record whose heatmap counts matched keypoints per block and whose regions
    are the boxes those keypoints fall in.  Both come from the same matched
    pairs, so a highlighted box is where the copy is rather than where a pixel
    map went hot.
    """

    name = MODULE_NAME

    def run(self, context: "ScreeningContext") -> base.DeepResult:
        """Return this capture's copy-move record.

        :param context: the run's record; the working frame is on
            ``context.image``.
        :returns: one :class:`~app.pipeline.tier2.base.DeepResult` whose score
            is the busiest block on the map, whose heatmap is the map, and whose
            regions are the boxes the matched keypoints fall in.
        """
        gray = to_gray(context.image)
        clusters = copy_clusters(context.image)
        votes = vote_map(clusters, gray.shape)
        heatmap = normalise(votes)
        rows = tuple(tuple(round(float(cell), 4) for cell in row) for row in heatmap)
        regions = region_polygons(clusters, gray.shape)

        peak = float(heatmap.max())
        copied = sum(1 for row in rows for cell in row if cell >= HOT_LEVEL)
        pairs = sum(len(cluster.matches) for cluster in clusters)
        detail = (
            f"Copy-move matched {pairs} keypoint pairs onto themselves across "
            f"{len(clusters)} repeated translations, landing in {copied} of "
            f"{len(rows) * len(rows[0])} blocks at or above {HOT_LEVEL:.2f} "
            f"({peak:.2f} at the busiest); repeated content is not proof of "
            f"tampering."
        )
        return base.DeepResult(
            module=self.name,
            score=peak,
            is_stub=True,
            model_version=MODEL_VERSION,
            detail=detail,
            heatmap=rows,
            regions=regions,
        )
