"""Cross-document face: is the person whose papers these one person?

16.7.  :func:`face_consistent` reads the face each document's own photo shows
and answers whether the case holds one face or several.  Every face is found
and turned into a vector through Part 13's own seams --
:class:`~app.pipeline.tier1.face.FaceDetector`,
:func:`~app.pipeline.tier1.face_align.align_face` and
:class:`~app.pipeline.tier1.face.Embedder` -- and compared by
:func:`~app.pipeline.tier1.face.match_score`; nothing here holds a model, a
threshold or a comparison of its own.

**A box with no embedder answers ``not_configured`` rather than raising.**  D131.
"""

import collections.abc
import dataclasses

import numpy

from app.pipeline.crossdoc.documents import (
    CONSISTENT,
    INCONSISTENT,
    NOT_CONFIGURED,
    CaseConsistency,
    CaseDocument,
    _sequence_of,
)
from app.pipeline.tier0.td3 import MrzValueError
from app.pipeline.tier1.face import (
    Embedder,
    Embedding,
    FaceDetector,
    match_score,
)
from app.pipeline.tier1.face_align import NO_CROP, align_face
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

__all__ = ["CaseFace", "face_consistent"]

#: The tier every flag this module builds reports itself under, and the band
#: the weightset holds ``CROSSDOC_FACE_MISMATCH`` under -- read as a constant
#: so a band cannot drift from the row it mirrors.
TIER = "crossdoc"
WEIGHT_BAND = "high"
#: The sentence an officer reads, and the reason on the flag.  Both name the
#: rule and print no vector: a face embedding is biometric identity data, and
#: so is a photograph, so the two halves the comparison was made from are the
#: bar and the cosine rather than either face.
LABEL = (
    "The face on a document in this case is not the face on the other "
    "documents in this case."
)
REASON = "a face did not match the face this case was measured against"
#: The name this code invented for the field the finding is about, never a
#: value any document printed.
FIELD = "face"
SOURCE_MODULE = "app.pipeline.crossdoc.faces"


@dataclasses.dataclass(frozen=True)
class CaseFace:
    """One document in a case, and the frame its own photo was cut from.

    ``document`` is the same :class:`~app.pipeline.crossdoc.documents.CaseDocument`
    the other two rules read, and ``image`` is 13.14's crop of that document's
    photo field -- a frame a detector can be pointed at, which the shared
    record deliberately does not hold so that record stays a transcription.
    Frozen, on :class:`~app.pipeline.tier0.td3.MrzDocument`'s reason.
    """

    document: CaseDocument
    image: numpy.ndarray

    def __post_init__(self) -> None:
        """Check the document and the frame, assign nothing, return ``None``."""
        if not isinstance(self.document, CaseDocument):
            raise MrzValueError(
                "a case face carries a CaseDocument record, not "
                f"{type(self.document).__name__}"
            )
        if not isinstance(self.image, numpy.ndarray):
            raise MrzValueError(
                "a case face carries the frame its document's photo was cut "
                f"from, not {type(self.image).__name__}"
            )


def _as_threshold(value: object) -> float:
    """Return ``value`` as the bar 13.15 compares against, or refuse it.

    The check is 13.15's own -- a cosine runs from -1.0 to 1.0, so a bar
    outside ``(0.0, 1.0]`` is a wiring mistake -- but it is made here so the
    refusal is an :class:`~app.pipeline.tier0.td3.MrzValueError` like every
    other one this package raises, and a caller catching one around its
    cascade keeps working.  ``bool`` is an ``int`` here as everywhere else.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MrzValueError(
            f"the face match threshold must be a number, not "
            f"{type(value).__name__}"
        )
    if not 0.0 < value <= 1.0:
        raise MrzValueError(
            f"the face match threshold must be above 0.0 and no more than "
            f"1.0, not {value!r}"
        )
    return float(value)


def _faces_of(documents_in_case: object) -> tuple[CaseFace, ...]:
    """Return ``documents_in_case`` as a tuple of :class:`CaseFace`, or raise.

    The shape refusals are :func:`~app.pipeline.crossdoc.documents._sequence_of`'s
    rather than a second copy of them, so this rule cannot disagree with the
    other two about what a case is; the element refusal is this module's,
    because a face case holds a different record.
    """
    case = _sequence_of(documents_in_case)
    for record in case:
        if not isinstance(record, CaseFace):
            raise MrzValueError(
                "a face case holds CaseFace records, not "
                f"{type(record).__name__}"
            )
    return case


def _vector(
    record: CaseFace, detector: FaceDetector, embedder: Embedder
) -> Embedding | None:
    """Return the vector for ``record``'s face, or ``None`` where there is none.

    **The most confident face of the several a photo may hold.**  A portrait
    is one person, and where a detector offers more than one the question
    "whose face is this document's" is answered by the reading the detector
    itself gave rather than by the order it happened to return them in.

    A frame holding no face, and landmarks that describe no face, both answer
    ``None``: a measurement nobody could make, on D99's rule, and not a
    document that printed a wrong face.
    """
    found = detector.detect(record.image)
    if not found:
        return None
    face = max(found, key=lambda detected: detected.confidence)
    crop = align_face(record.image, face.landmarks)
    if crop is NO_CROP:
        return None
    return embedder.embed(crop)


def _flag(score) -> EvidenceFlag:
    """Return the one flag a face that did not match becomes.

    ``expected`` is the bar the pair was held to and ``found`` the cosine it
    reached, both ISO-free four-place decimals as 13.16 prints a similarity.
    Neither vector nor frame is carried: a face embedding is biometric
    identity data and a flag must not be a place it is stored.
    """
    return EvidenceFlag(
        id=flag_ids.CROSSDOC_FACE_MISMATCH,
        tier=TIER,
        label=LABEL,
        weight_band=WEIGHT_BAND,
        value=1.0,
        confidence=1.0,
        region=None,
        expected=f"{score.threshold:.4f}",
        found=f"{score.similarity:.4f}",
        reason=REASON,
        source_module=SOURCE_MODULE,
        field=FIELD,
    )


def face_consistent(
    documents_in_case: collections.abc.Iterable[CaseFace],
    detector: FaceDetector,
    embedder: Embedder,
    threshold: float,
) -> CaseConsistency:
    """Read every document's face against the first one the case can measure.

    **The reference face is the first document in the case that yields a
    vector**, and every other such document is compared against it, in the
    order the documents were given.  Which document is the primary one is the
    caller's to order rather than this rule's to guess from a role, and the
    pair order is fixed so a case cannot answer differently twice.

    One flag per document whose face did not match the reference.  Nothing is
    compared for a document holding no frame, a frame with no face in it, or
    a face the embedder declined to measure, and a pair 13.15 refuses to
    score -- a stub's labelled zero, or a vector with no direction -- is not
    compared and not counted either.  So a case with fewer than two measurable
    faces answers ``not_configured`` and never ``consistent``: silence is not
    a pass, on D121's rule.

    :param documents_in_case: the case's documents, each as a
        :class:`CaseFace` record.
    :param detector: where faces are found, by 13.12's seam.
    :param embedder: what a face becomes, by 13.13's seam.  It is asked
        :meth:`~app.pipeline.tier1.face.Embedder.is_available` once, and that
        answer is the whole degradation path.
    :param threshold: the bar the cosine is held to, required rather than
        defaulted on D98's reasoning.
    :returns: the status, the flags, and how many pairs were compared.
    :raises MrzValueError: if ``documents_in_case`` is not a sequence of
        :class:`CaseFace` records, or ``threshold`` is not a number in
        ``(0.0, 1.0]``.  Tier 0's error, so a caller catching one around its
        cascade keeps working.
    """
    bar = _as_threshold(threshold)
    case = _faces_of(documents_in_case)
    # One question, asked before anything is read: a box holding no face
    # model could not compare one pair either, and a rule that raised here
    # would take a whole case down over a capability it never needed to have.
    if not embedder.is_available():
        return CaseConsistency(status=NOT_CONFIGURED, flags=(), compared=0)
    reference = None
    flags = []
    compared = 0
    for record in case:
        vector = _vector(record, detector, embedder)
        if vector is None:
            continue
        if reference is None:
            reference = vector
            continue
        score = match_score(reference, vector, bar)
        if score is None:
            continue
        compared += 1
        if not score.matches:
            flags.append(_flag(score))
    status = INCONSISTENT if flags else (CONSISTENT if compared else NOT_CONFIGURED)
    return CaseConsistency(status=status, flags=tuple(flags), compared=compared)
