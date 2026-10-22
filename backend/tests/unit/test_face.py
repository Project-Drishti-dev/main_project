"""13.12 -- the two face seams, and a stub that says it is a stub.

The task's claim is that ``NullEmbedder`` returns a deterministic zero vector
and reports ``is_stub: true``, so the first group below is that claim.  The
rest holds both interfaces abstract and checkable the way ``test_ocr.py`` holds
``OcrEngine``: signatures read from the source rather than from a call, since a
method that happens to work proves less than a signature with one argument too
many or a default the caller could omit.
"""

import dataclasses
import inspect

import pytest

from app.pipeline.tier1 import face

DetectedFace = face.DetectedFace
Embedder = face.Embedder
Embedding = face.Embedding
FaceDetector = face.FaceDetector
NullEmbedder = face.NullEmbedder

#: One face in the shape a detector reports it: four whole-pixel corners in
#: the order ``EvidenceFlag.region`` uses, and the detector's own confidence.
#: It carries no identity data this project could print.
A_FACE = DetectedFace(
    region=((120, 40), (280, 40), (280, 220), (120, 220)),
    confidence=0.94,
    landmarks=(
        (157.78, 175.75),
        (212.31, 190.04),
        (176.88, 214.07),
        (145.96, 239.96),
        (191.13, 251.79),
    ),
)

#: The frame a stub is handed.  A stub never reads it, and using one object
#: keeps the test from standing in for an image it does not build.
A_FRAME = object()

#: Each seam with the one method the task names, for the signature tests.
SEAMS = ((FaceDetector, "detect"), (Embedder, "embed"))


class StubDetector(FaceDetector):
    """A detector that answers from a tuple it was handed, and never looks."""

    def __init__(self, found=()):
        self.found = tuple(found)
        self.seen = []

    def detect(self, image):
        self.seen.append(image)
        return self.found


class ADetectorThatForgetsDetect(FaceDetector):
    """A detector that wired everything except the one method the task names."""

    def is_available(self):
        return True


class AnEmbedderThatForgetsEmbed(Embedder):
    """An embedder that wired everything except the one method the task names."""

    def is_available(self):
        return True


# --- the task's own claim: labelled a stub, and a vector of zeros ---


def test_the_null_embedder_is_labelled_as_a_stub():
    """13.12's own claim, and the one 13.15 needs in order to refuse it."""
    assert NullEmbedder().embed(A_FRAME).is_stub is True


def test_the_null_embedder_returns_a_vector_of_zeros():
    vector = NullEmbedder().embed(A_FRAME).vector
    assert set(vector) == {0.0}
    assert len(vector) == face.NULL_EMBEDDING_DIM


def test_the_zero_vector_is_the_same_on_every_call():
    embedder = NullEmbedder()
    assert embedder.embed(A_FRAME) == embedder.embed(object())


def test_the_zero_vector_is_the_same_for_every_instance():
    assert NullEmbedder().embed(A_FRAME) == NullEmbedder().embed(A_FRAME)


def test_the_vector_is_as_long_as_the_dimension_asked_for():
    assert len(NullEmbedder(dim=8).embed(A_FRAME).vector) == 8


def test_a_vector_that_is_not_a_stub_says_so_by_defaulting():
    """Otherwise the flag could only ever be set and never cleared."""
    assert Embedding(vector=(0.1, 0.2)).is_stub is False


def test_the_null_embedder_is_available_because_it_can_always_answer():
    assert NullEmbedder().is_available() is True


def test_the_null_embedder_refuses_no_image():
    assert NullEmbedder().embed(object()) is not None


# --- the dimension is asked for, and a bad one raises rather than defaults ---


@pytest.mark.parametrize("dim", [0, -1, -512])
def test_a_dimension_that_is_not_positive_is_refused(dim):
    with pytest.raises(ValueError):
        NullEmbedder(dim=dim)


@pytest.mark.parametrize("dim", [1.5, "512", None, True])
def test_a_dimension_that_is_not_an_integer_is_refused(dim):
    with pytest.raises(ValueError):
        NullEmbedder(dim=dim)


# --- both seams are abstract, and each names one method ---


def test_the_detector_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        FaceDetector()


def test_the_embedder_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Embedder()


def test_a_detector_that_forgets_detect_cannot_be_instantiated():
    """The abstract method is what makes the interface checkable."""
    with pytest.raises(TypeError):
        ADetectorThatForgetsDetect()


def test_an_embedder_that_forgets_embed_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AnEmbedderThatForgetsEmbed()


def test_detect_is_the_only_method_the_detector_requires():
    """Availability is 13.13's question, so nothing else is required here."""
    assert FaceDetector.__abstractmethods__ == frozenset({"detect"})


def test_embed_is_the_only_method_the_embedder_requires():
    assert Embedder.__abstractmethods__ == frozenset({"embed"})


def test_the_null_embedder_subclasses_the_interface():
    assert issubclass(NullEmbedder, Embedder)


def test_a_caller_can_hold_a_stub_as_the_interface():
    """The point of the seam: the caller is written against the interface."""
    assert isinstance(NullEmbedder(), Embedder)


# --- the signatures, read from the source rather than from a call ---


def _signature(interface, method):
    return inspect.signature(getattr(interface, method))


def _defaults(signature):
    return [
        parameter.default
        for parameter in signature.parameters.values()
        if parameter.default is not inspect.Parameter.empty
    ]


@pytest.mark.parametrize("interface,method", SEAMS)
def test_a_seam_takes_exactly_one_argument_besides_self(interface, method):
    assert tuple(_signature(interface, method).parameters) == ("self", "image")


@pytest.mark.parametrize("interface,method", SEAMS)
def test_no_argument_has_a_default(interface, method):
    """An omitted image is a face nobody embedded, not an empty embedding."""
    assert _defaults(_signature(interface, method)) == []


@pytest.mark.parametrize("interface,method", SEAMS)
def test_a_seam_takes_no_keyword_or_star_argument(interface, method):
    kinds = {
        parameter.kind
        for parameter in _signature(interface, method).parameters.values()
    }
    assert kinds == {inspect.Parameter.POSITIONAL_OR_KEYWORD}


def test_detect_answers_a_tuple_of_detected_faces():
    """A detector answering a single face would leave the caller guessing."""
    assert _signature(FaceDetector, "detect").return_annotation == tuple[
        DetectedFace, ...
    ]


def test_embed_answers_an_embedding_or_nothing():
    assert _signature(Embedder, "embed").return_annotation == Embedding | None


def test_the_null_embedder_does_not_widen_the_seam_it_implements():
    """A second argument on the stub is the per-engine option ``D82`` refuses.

    Python does not hold an override to its abstract method's signature, so
    the tests above read the seam while a caller reads the object it holds.
    Without this one a stub could take an argument only it understands and
    every other embedder would fail against it at the first document.
    """
    stub = _signature(NullEmbedder, "embed")
    seam = _signature(Embedder, "embed")
    assert tuple(stub.parameters) == tuple(seam.parameters)
    assert _defaults(stub) == _defaults(seam) == []


# --- the records, and the two absences that are values ---


def test_a_detected_face_carries_its_region_its_confidence_and_its_landmarks():
    assert A_FACE.region == ((120, 40), (280, 40), (280, 220), (120, 220))
    assert A_FACE.confidence == 0.94
    assert len(A_FACE.landmarks) == 5


def test_a_frame_with_no_face_is_an_empty_tuple_and_not_a_missing_one():
    assert StubDetector().detect(A_FRAME) == ()


def test_a_detector_is_handed_the_frame_it_was_asked_about():
    detector = StubDetector(found=(A_FACE,))
    assert detector.detect(A_FRAME) == (A_FACE,)
    assert detector.seen == [A_FRAME]


@pytest.mark.parametrize("field", ["region", "confidence", "landmarks"])
def test_no_field_of_a_detected_face_has_a_default(field):
    """A defaulted confidence is a face measured at a clean zero.

    ``D99``'s rule, held on the record: where there is nothing to measure the
    answer is ``None`` or the face is absent, never a zero that reads like a
    real reading.
    """
    assert face.DetectedFace.__dataclass_fields__[field].default is dataclasses.MISSING


def test_a_vector_has_no_default():
    """An embedding carrying no vector at all is not a measurement of none."""
    assert face.Embedding.__dataclass_fields__["vector"].default is dataclasses.MISSING


def test_a_detected_face_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        A_FACE.confidence = 0.5


def test_an_embedding_is_frozen():
    """A stub that could be relabelled after the fact would be no stub."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        Embedding(vector=(0.0,)).is_stub = True


def test_every_name_in_all_exists_in_the_module():
    for name in face.__all__:
        assert hasattr(face, name)
