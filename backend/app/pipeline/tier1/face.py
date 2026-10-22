"""Tier 1's face seam: where a face is, and what a face becomes.

:class:`DetectedFace` is one face a detector found -- its region in the frame
it was read from, and that detector's confidence.  :class:`Embedding` is one
face turned into a vector, carrying whether a real model produced it.  The two
seams are :class:`FaceDetector` and :class:`Embedder`; neither holds a
threshold, a model or a comparison.

:func:`match_score` is that comparison: the cosine between two embeddings,
beside the threshold they were held to.  It answers :data:`NO_MATCH` where a
vector has no direction to compare, and never a score of zero for one that has.
"""

import abc
import dataclasses
import math

__all__ = [
    "NO_MATCH",
    "NULL_EMBEDDING_DIM",
    "DetectedFace",
    "Embedder",
    "Embedding",
    "FaceDetector",
    "MatchScore",
    "NullEmbedder",
    "match_score",
]

#: The length of the vector :class:`NullEmbedder` returns, and ArcFace's own
#: embedding width.  Chosen so a stub's vector has the shape a real embedder
#: would hand back; it is not measured here, as no face model is installed here.
NULL_EMBEDDING_DIM = 512


#: What :func:`match_score` answers where two faces cannot be compared at all.
#: ``None`` and not ``0.0``, on ``D99``'s rule: a stub's zero vector has no
#: direction, so its cosine is ``0 / 0`` -- undefined rather than merely low.
NO_MATCH = None


@dataclasses.dataclass(frozen=True)
class DetectedFace:
    """One face a detector found, and how sure of it that detector was.

    ``region`` is a polygon of whole-pixel corners in the frame the face was
    read from, ordered as :attr:`~app.risk.flags.EvidenceFlag.region` orders
    its own.  ``confidence`` is the detector's own ``0.0``-``1.0`` reading.
    ``landmarks`` are the face's five points in the order
    :data:`~app.pipeline.tier1.face_align.LANDMARK_ORDER` names, and 13.14 is
    what earns that order being named on this record.
    """

    region: tuple[tuple[int, int], ...]
    confidence: float
    landmarks: tuple[tuple[float, float], ...]


@dataclasses.dataclass(frozen=True)
class Embedding:
    """One face turned into a vector, and whether a real model produced it.

    ``is_stub`` rides on the record rather than on the embedder, because a
    caller holding two embeddings cannot ask which embedder made either of
    them.  It defaults to ``False``: a vector is a measurement unless it says
    otherwise.
    """

    vector: tuple[float, ...]
    is_stub: bool = False


@dataclasses.dataclass(frozen=True)
class MatchScore:
    """Two faces compared: how alike they are, and the bar they were held to.

    The threshold rides on the record rather than living in the module as a
    constant, because 13.16's flag carries both numbers and a score whose
    threshold is one the caller has to remember is one place for the two to
    drift apart.  Neither field defaults: a similarity or a threshold nobody
    supplied is not a measurement (``D101``).
    """

    similarity: float
    threshold: float

    @property
    def matches(self) -> bool:
        """Whether the similarity reached the threshold; equal reaches it.

        Derived rather than stored, so it cannot disagree with the two numbers
        printed beside it.
        """
        return self.similarity >= self.threshold


class FaceDetector(abc.ABC):
    """The one question Tier 1 asks about faces: where are they.

    A subclass that omits ``detect`` cannot be instantiated, so a detector
    wired wrongly fails at construction rather than at the first document.
    ``is_available`` is left to each implementation, on ``D83``'s reasoning.
    """

    @abc.abstractmethod
    def detect(self, image) -> tuple[DetectedFace, ...]:
        """Return every face ``image`` holds, as a tuple.

        ``image`` is the working frame Tier 0 takes: three-channel BGR.  A
        frame holding no face is ``()``, which is a measurement of nothing
        rather than a failure to measure.
        """
        raise NotImplementedError


class Embedder(abc.ABC):
    """The one question Tier 1 asks about a face it has already found.

    A subclass that omits ``embed`` cannot be instantiated, so an embedder
    wired wrongly fails at construction rather than at the first document.
    ``is_available`` is left to each implementation, on ``D83``'s reasoning.
    """

    @abc.abstractmethod
    def embed(self, image) -> Embedding | None:
        """Return the vector for the face in ``image``, or ``None``.

        ``image`` is one face's crop, already aligned if 13.14 aligned it.
        ``None`` is where no vector was measured at all (``D99``'s rule), and
        is a different statement from a stub's labelled zero.
        """
        raise NotImplementedError


class NullEmbedder(Embedder):
    """The embedder that is always here and never measures anything.

    Every image answers with the same zero vector, carrying ``is_stub``.  A
    zero vector has no direction, so the cosine 13.15 compares is undefined
    against it; the label is what lets a caller refuse the comparison rather
    than divide by zero and call it a score.
    """

    def __init__(self, *, dim: int = NULL_EMBEDDING_DIM):
        """Build a stub whose vector is ``dim`` zeros long.

        A ``dim`` that is not a positive ``int`` raises rather than defaulting,
        on ``D98``'s reasoning: a vector of no dimensions is a stub that
        cannot be compared to anything, and that is a wiring mistake.
        """
        if isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0:
            raise ValueError(
                f"dim must be a positive int, not {type(dim).__name__}."
            )
        self._dim = dim

    def is_available(self) -> bool:
        """Always ``True``: this embedder can answer, and never measures."""
        return True

    def embed(self, image) -> Embedding | None:
        """Return the labelled zero vector; no image is ever refused."""
        return Embedding(vector=(0.0,) * self._dim, is_stub=True)


def _numbers(vector, side) -> list[float]:
    """``vector`` as a list of finite real floats, raising on anything else.

    Every element is checked rather than coerced: ``float("0.5")`` would take a
    string, and a vector that parsed its way into shape looks measured.  A
    non-finite value raises for the same reason a ``nan`` landmark does -- it
    reaches the cosine as itself and every number after it is a quiet ``nan``.
    """
    values = list(vector)
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{side} must hold real numbers, not {value!r}.")
        if not math.isfinite(value):
            raise ValueError(f"{side} must hold finite numbers, not {value!r}.")
    return [float(value) for value in values]


def _unit(values) -> list[float] | None:
    """``values`` at unit length, or :data:`NO_MATCH` where it has no length."""
    norm = math.sqrt(math.fsum(value * value for value in values))
    if norm == 0.0:
        return NO_MATCH
    return [value / norm for value in values]


def _is_threshold(value) -> bool:
    """Whether ``value`` is a bar a cosine could actually be held to.

    A cosine runs from ``-1.0`` to ``1.0``, so a threshold above one is a bar
    no pair of vectors can reach and is a wiring mistake rather than a strict
    one; zero and below are the same mistake the other way round.  ``bool`` is
    an ``int`` here as everywhere else in this project.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0.0 < value <= 1.0


def match_score(embedding_a, embedding_b, threshold) -> MatchScore | None:
    """Two embeddings compared against ``threshold``, or :data:`NO_MATCH`.

    The similarity is the cosine, so neither vector's length is part of the
    answer and scaling one does not move the score.  ``threshold`` is required
    and is checked before anything else, on ``D98``'s reasoning: it is part of
    the answer rather than a default standing behind it.

    A stub on either side, and any vector with no length, answer
    :data:`NO_MATCH` -- ``D101``'s refusal, and what lets a box with no face
    model degrade rather than raise.  Two vectors of different widths, or one
    holding something that is not a finite number, raise instead: those are
    wiring mistakes, which is not the same statement as measuring nothing.
    """
    if not _is_threshold(threshold):
        raise ValueError(
            f"threshold must be above 0.0 and no more than 1.0, not {threshold!r}."
        )
    if embedding_a.is_stub or embedding_b.is_stub:
        return NO_MATCH
    left = _numbers(embedding_a.vector, "embedding_a")
    right = _numbers(embedding_b.vector, "embedding_b")
    if len(left) != len(right):
        raise ValueError(
            f"two faces are compared as vectors of one width, "
            f"not {len(left)} and {len(right)}."
        )
    left, right = _unit(left), _unit(right)
    if left is NO_MATCH or right is NO_MATCH:
        return NO_MATCH
    similarity = math.fsum(one * other for one, other in zip(left, right))
    # A cosine cannot leave [-1.0, 1.0]; rounding can push it out.  A 5-12-13
    # vector against itself reads 1.0000000000000002 without this, which is a
    # similarity above a perfect match.
    return MatchScore(
        similarity=min(1.0, max(-1.0, similarity)), threshold=float(threshold)
    )
