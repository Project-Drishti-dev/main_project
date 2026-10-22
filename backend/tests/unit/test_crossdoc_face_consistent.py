"""`face_consistent`: one face across a case, or the box cannot measure one.

16.7 names one case -- a face that does not match across two documents in the
same case -- and the rest of the surface is pinned here so a later change to
it is a decision rather than a drift.  Both paths are held: a case measured
with a real embedder, and a box holding none, which answers `not_configured`
rather than raising.  D131.
"""

import ast
import dataclasses
import inspect
from pathlib import Path

import numpy
import pytest

from app.pipeline.crossdoc import faces as faces_module
from app.pipeline.crossdoc.documents import (
    CONSISTENT,
    INCONSISTENT,
    NOT_CONFIGURED,
    CaseDocument,
)
from app.pipeline.crossdoc.faces import CaseFace, face_consistent
from app.pipeline.tier0.td3 import MrzValueError
from app.pipeline.tier1.face import (
    Embedder,
    Embedding,
    FaceDetector,
    DetectedFace,
    NullEmbedder,
)
from app.pipeline.tier1.face_align import CANONICAL_LANDMARKS, align_face
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag
from app.risk.weightsets import loader

#: The bar every comparison in this file is held to, well above the cosine
#: between the two vectors below and well below their own.
THRESHOLD = 0.6
#: Two faces that are nothing like each other: 1.0 and 0.0 in different
#: directions, so their cosine is exactly 0.0.  A third, `SAME`, is ``UNIT``
#: scaled, which is the same direction and therefore a match -- 13.15's rule
#: that neither vector's length is part of the answer.
UNIT = (1.0, 0.0, 0.0)
OTHER = (0.0, 1.0, 0.0)
#: Five landmarks enclosing an area, so 13.14 can fit a similarity onto them,
#: and five lying on one line, which enclose none and fit nothing.
FACE_LANDMARKS = ((30, 40), (80, 40), (55, 65), (35, 85), (75, 85))
FLAT_LANDMARKS = ((10, 10), (20, 10), (30, 10), (40, 10), (50, 10))


def frame(fill=0):
    """A blank photo frame the same shape every time, distinguishable by fill."""
    return numpy.full((112, 112, 3), fill, dtype=numpy.uint8)


def face(landmarks=FACE_LANDMARKS, confidence=0.9):
    """One detected face, at one frame's own coordinates."""
    return DetectedFace(
        region=((10, 10), (90, 10), (90, 90), (10, 90)),
        confidence=confidence,
        landmarks=landmarks,
    )


def passport(number="AB1234567"):
    return CaseDocument(role="passport", document_number=number)


def visa(number="V7654321"):
    return CaseDocument(
        role="visa",
        document_number=number,
        referenced_passport_number="AB1234567",
    )


def record(document=None, fill=0):
    """One document in a face case, and the frame its photo was cut from."""
    return CaseFace(document=document or passport(), image=frame(fill))


class StubDetector(FaceDetector):
    """A detector that answers the faces it was built with, and records them.

    ``by_image`` maps the fill of a frame to the faces it holds, so a test
    naming two documents names two answers rather than one answer asked twice.
    """

    def __init__(self, faces_by_fill=None, default=()):
        self._by_fill = faces_by_fill or {}
        self._default = tuple(default)
        self.asked = []

    def detect(self, image):
        self.asked.append(image)
        return self._by_fill.get(int(image[0, 0, 0]), self._default)


class SequenceEmbedder(Embedder):
    """An embedder that answers each crop with the next vector it was given.

    Ordering rather than content, because a crop is a warp of the frame and
    nothing readable survives it: the rule asks in document order, so the
    vectors are written in document order too.  ``crops`` records what each
    answer was made from, which is how a test asks *which* face was embedded.
    """

    def __init__(self, vectors=(), available=True):
        self._vectors = [
            None if vector is None else Embedding(vector=tuple(vector))
            for vector in vectors
        ]
        self._available = available
        self.crops = []

    def is_available(self):
        return self._available

    def embed(self, image):
        self.crops.append(image)
        return self._vectors.pop(0)


def measured(*vectors, threshold=THRESHOLD, fills=None):
    """Answer ``face_consistent`` over a case of blank frames, as a real box would.

    Each frame is given its own fill and its own vector, so document order and
    vector order are the same order and a test can name one and mean the other.
    """
    fills = list(fills) if fills is not None else list(range(len(vectors)))
    case = [record(fill=fills[index]) for index in range(len(vectors))]
    return face_consistent(
        case,
        StubDetector(default=(face(),)),
        SequenceEmbedder(vectors),
        threshold,
    )


# --- the case tasks.md names, on a box holding an embedder -------------------


def test_two_documents_showing_the_same_face_raise_no_flag():
    result = measured(UNIT, UNIT)

    assert result.flags == ()
    assert result.status == CONSISTENT


def test_two_documents_showing_different_faces_raise_a_flag():
    result = measured(UNIT, OTHER)

    assert len(result.flags) == 1
    assert result.flags[0].id == flag_ids.CROSSDOC_FACE_MISMATCH


def test_that_flag_is_the_one_the_vocabulary_holds():
    result = measured(UNIT, OTHER)

    assert result.flags[0].id in flag_ids.FLAG_IDS


def test_a_pair_that_agrees_is_still_counted_as_compared():
    result = measured(UNIT, UNIT)

    assert result.compared == 1


def test_a_vector_scaled_is_the_same_face_and_does_not_raise_a_flag():
    """13.15: neither vector's length is part of the cosine."""
    result = measured(UNIT, (7.5, 0.0, 0.0))

    assert result.flags == ()
    assert result.status == CONSISTENT


# --- the same case on a box holding no embedder ------------------------------


def test_a_box_with_no_embedder_answers_not_configured():
    result = face_consistent(
        [record(fill=0), record(fill=1)],
        StubDetector(default=(face(),)),
        SequenceEmbedder([UNIT, OTHER], available=False),
        THRESHOLD,
    )

    assert result.status == NOT_CONFIGURED
    assert result.compared == 0
    assert result.flags == ()


def test_a_box_with_no_embedder_does_not_raise():
    face_consistent(
        [record(fill=0), record(fill=1)],
        StubDetector(default=(face(),)),
        SequenceEmbedder([], available=False),
        THRESHOLD,
    )


def test_a_box_with_no_embedder_reads_nothing_to_find_that_out():
    detector = StubDetector(default=(face(),))
    face_consistent(
        [record(fill=0), record(fill=1)],
        detector,
        SequenceEmbedder([], available=False),
        THRESHOLD,
    )

    assert detector.asked == []


def test_a_box_with_no_embedder_flags_nothing_even_when_the_faces_differ():
    """Degradation is not a quieter kind of finding; it is no finding."""
    result = face_consistent(
        [record(fill=0), record(fill=1)],
        StubDetector(default=(face(),)),
        SequenceEmbedder([UNIT, OTHER], available=False),
        THRESHOLD,
    )

    assert result.flags == ()


def test_the_two_paths_are_two_answers_and_not_one_answer_chosen():
    """The same case, measured and unmeasured, is read two different ways."""
    case = [record(fill=0), record(fill=1)]
    detector = StubDetector(default=(face(),))

    measured_result = face_consistent(
        case, detector, SequenceEmbedder([UNIT, OTHER]), THRESHOLD
    )
    unmeasured_result = face_consistent(
        case, detector, SequenceEmbedder([], available=False), THRESHOLD
    )

    assert measured_result.status == INCONSISTENT
    assert unmeasured_result.status == NOT_CONFIGURED


def test_the_stub_embedder_degrades_the_same_way_a_missing_one_does():
    """`NullEmbedder` answers, measures nothing, and is refused by 13.15."""
    result = face_consistent(
        [record(fill=0), record(fill=1)],
        StubDetector(default=(face(),)),
        NullEmbedder(),
        THRESHOLD,
    )

    assert result.status == NOT_CONFIGURED
    assert result.compared == 0
    assert result.flags == ()


# --- a document that cannot be measured at all -------------------------------


def test_a_document_with_no_face_in_it_is_not_compared():
    case = [record(fill=0), record(fill=1)]
    detector = StubDetector({0: (face(),), 1: ()})
    result = face_consistent(
        case, detector, SequenceEmbedder([UNIT]), THRESHOLD
    )

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_a_document_holding_no_frame_is_not_compared():
    case = [CaseFace(document=passport(), image=frame(0)), record(fill=1)]
    result = face_consistent(
        case,
        StubDetector({1: (face(),)}),
        SequenceEmbedder([UNIT]),
        THRESHOLD,
    )

    assert result.compared == 0
    assert result.flags == ()


def test_landmarks_that_describe_no_face_are_not_compared():
    """13.14's `NO_CROP`: five points on a line enclose no area."""
    case = [record(fill=0), record(fill=1)]
    detector = StubDetector({0: (face(),), 1: (face(FLAT_LANDMARKS),)})
    result = face_consistent(
        case, detector, SequenceEmbedder([UNIT]), THRESHOLD
    )

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_an_embedder_that_measures_nothing_is_not_compared():
    case = [record(fill=0), record(fill=1)]
    result = face_consistent(
        case,
        StubDetector(default=(face(),)),
        SequenceEmbedder([UNIT, None]),
        THRESHOLD,
    )

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_a_case_of_one_document_compares_nothing_and_is_not_configured():
    result = measured(UNIT)

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED
    assert result.flags == ()


def test_a_case_holding_no_documents_is_not_configured():
    result = face_consistent([], StubDetector(), SequenceEmbedder(), THRESHOLD)

    assert result.status == NOT_CONFIGURED
    assert result.compared == 0


# --- silence is never a pass -------------------------------------------------


@pytest.mark.parametrize(
    "vectors",
    [(), (UNIT,), (UNIT, UNIT), (UNIT, None), (UNIT, None, None)],
    ids=["empty", "one", "two-equal", "one-unmeasurable", "two-unmeasurable"],
)
def test_a_case_nothing_was_compared_in_is_never_answered_consistent(vectors):
    result = measured(*vectors)

    if result.compared:
        assert result.status == CONSISTENT
    else:
        assert result.status == NOT_CONFIGURED


# --- which face is the reference ---------------------------------------------


def test_the_first_measurable_document_is_the_reference():
    """A document that cannot be measured is skipped, not made the reference."""
    case = [record(fill=0), record(fill=1), record(fill=2)]
    detector = StubDetector({0: (), 1: (face(),), 2: (face(),)})
    result = face_consistent(
        case, detector, SequenceEmbedder([UNIT, OTHER]), THRESHOLD
    )

    assert len(result.flags) == 1
    assert result.compared == 1


def test_the_reference_face_is_never_compared_against_itself():
    result = measured(UNIT)

    assert result.compared == 0
    assert result.flags == ()


def test_every_face_is_compared_against_the_reference_and_not_each_other():
    """The second agrees with the reference, the third does not: one flag."""
    result = measured(UNIT, UNIT, OTHER)

    assert len(result.flags) == 1
    assert result.compared == 2


def test_three_documents_raise_a_flag_for_each_that_disagrees_with_the_reference():
    result = measured(UNIT, OTHER, (0.0, 0.0, 1.0))

    assert len(result.flags) == 2
    assert result.compared == 2


def test_a_face_a_photograph_shows_several_times_is_the_most_confident():
    """A portrait is one person; where several are offered, confidence decides.

    The confident face on the first document is the one that aligns to
    nothing, so the rule skipping that document is the whole of the proof:
    reading the other face would have measured it and compared the pair.
    """
    detector = StubDetector(
        {
            0: (
                face(FLAT_LANDMARKS, confidence=0.9),
                face(FACE_LANDMARKS, confidence=0.4),
            ),
            1: (face(FACE_LANDMARKS),),
        }
    )
    result = face_consistent(
        [record(fill=0), record(fill=1)],
        detector,
        SequenceEmbedder([UNIT, UNIT]),
        THRESHOLD,
    )

    assert result.compared == 0
    assert result.status == NOT_CONFIGURED


def test_the_crops_a_measured_face_was_made_from_are_the_aligned_ones():
    """13.14's crop is what reaches the embedder, and only that."""
    detector = StubDetector(default=(face(),))
    embedder = SequenceEmbedder([UNIT, UNIT])

    face_consistent([record(fill=0), record(fill=1)], detector, embedder, THRESHOLD)

    for asked, fill in zip(embedder.crops, (0, 1)):
        assert asked.shape == (112, 112, 3)
        assert asked is not frame(fill)


# --- the order the documents are read in -------------------------------------


def test_flags_come_out_in_the_order_the_documents_were_given():
    result = measured(UNIT, OTHER, (0.0, 0.0, 1.0), UNIT)

    assert len(result.flags) == 2


def test_the_same_case_answered_twice_answers_the_same_way():
    first = measured(UNIT, OTHER, (0.0, 0.0, 1.0))
    second = measured(UNIT, OTHER, (0.0, 0.0, 1.0))

    assert first.status == second.status
    assert first.compared == second.compared
    assert [flag.found for flag in first.flags] == [
        flag.found for flag in second.flags
    ]


def test_the_documents_are_given_in_the_order_the_caller_ordered_them():
    """Two documents, compared in the order the case lists them."""
    forwards = measured(UNIT, OTHER)
    backwards = measured(OTHER, UNIT)

    assert forwards.status == backwards.status == INCONSISTENT


def test_a_generator_is_read_once_and_answered():
    result = face_consistent(
        (record(fill=index) for index in range(2)),
        StubDetector(default=(face(),)),
        SequenceEmbedder([UNIT, OTHER]),
        THRESHOLD,
    )

    assert result.compared == 1
    assert len(result.flags) == 1


# --- what the flag carries ---------------------------------------------------


def test_the_flag_names_the_rule_and_prints_no_vector():
    result = measured(UNIT, OTHER)
    flag = result.flags[0]

    assert flag.id == flag_ids.CROSSDOC_FACE_MISMATCH
    assert flag.tier == "crossdoc"
    assert flag.source_module == "app.pipeline.crossdoc.faces"
    assert flag.field == "face"
    assert flag.reason == faces_module.REASON
    assert flag.label == faces_module.LABEL


def test_the_flag_carries_the_bar_and_the_cosine_and_nothing_else():
    result = measured(UNIT, OTHER)
    flag = result.flags[0]

    assert flag.expected == "0.6000"
    assert flag.found == "0.0000"


def test_the_flag_carries_the_cosine_that_was_measured():
    result = face_consistent(
        [record(fill=0), record(fill=1)],
        StubDetector(default=(face(),)),
        SequenceEmbedder([UNIT, (1.0, 2.0, 0.0)]),
        THRESHOLD,
    )

    assert result.flags[0].found == f"{1 / 5 ** 0.5:.4f}"


def test_the_flag_carries_the_bar_it_was_measured_against():
    result = measured(UNIT, OTHER, threshold=0.9)

    assert result.flags[0].expected == "0.9000"


def test_the_flag_carries_the_two_numbers_and_nothing_that_identifies_a_face():
    """D129 widened: a face embedding is biometric identity data, so a flag
    must not become a place either face is stored."""
    result = measured(UNIT, OTHER)
    flag = result.flags[0]

    assert (flag.expected, flag.found) == ("0.6000", "0.0000")
    assert flag.region is None
    for side in (flag.expected, flag.found, flag.label, flag.reason, flag.field):
        assert isinstance(side, str)
        assert "," not in side


def test_the_flag_locates_nothing():
    """Two documents' faces are on two frames, so neither can be pointed at."""
    result = measured(UNIT, OTHER)

    assert result.flags[0].region is None


def test_the_flag_carries_the_strongest_of_the_four_crossdoc_bands():
    result = measured(UNIT, OTHER)

    assert result.flags[0].weight_band == "high"


def test_the_band_on_the_flag_is_the_band_the_weightset_row_carries():
    row = loader.load_weightset().flags[flag_ids.CROSSDOC_FACE_MISMATCH]

    assert measured(UNIT, OTHER).flags[0].weight_band == row["band"]


def test_the_flag_is_an_evidence_flag():
    result = measured(UNIT, OTHER)

    assert isinstance(result.flags[0], EvidenceFlag)


def test_the_flag_is_frozen():
    result = measured(UNIT, OTHER)
    flag = result.flags[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        flag.id = flag_ids.CROSSDOC_NAME_MISMATCH


# --- what a case is ----------------------------------------------------------


def test_a_bare_string_is_refused_before_it_is_measured():
    with pytest.raises(MrzValueError):
        face_consistent(
            "AB1234567", StubDetector(), SequenceEmbedder(), THRESHOLD
        )


def test_bytes_are_refused_as_a_case():
    with pytest.raises(MrzValueError):
        face_consistent(
            b"AB1234567", StubDetector(), SequenceEmbedder(), THRESHOLD
        )


def test_something_that_is_not_a_sequence_is_refused():
    with pytest.raises(MrzValueError):
        face_consistent(7, StubDetector(), SequenceEmbedder(), THRESHOLD)


def test_a_case_of_plain_case_documents_is_refused():
    """The face case holds a different record, and says so."""
    with pytest.raises(MrzValueError):
        face_consistent(
            [passport(), visa()], StubDetector(), SequenceEmbedder(), THRESHOLD
        )


def test_a_case_holding_something_else_entirely_is_refused():
    with pytest.raises(MrzValueError):
        face_consistent(
            [record(), 7], StubDetector(), SequenceEmbedder(), THRESHOLD
        )


def test_the_refusal_says_what_the_case_was_given():
    with pytest.raises(MrzValueError) as caught:
        face_consistent([7], StubDetector(), SequenceEmbedder(), THRESHOLD)

    assert "int" in str(caught.value)


def test_a_case_face_carrying_no_document_is_refused():
    with pytest.raises(MrzValueError):
        CaseFace(document=passport().document_number, image=frame(0))


def test_a_case_face_carrying_no_frame_is_refused():
    with pytest.raises(MrzValueError):
        CaseFace(document=passport(), image="frame.png")


def test_a_case_face_carrying_a_list_of_pixels_is_refused():
    """A list is a frame-shaped thing that ``cv2`` would refuse later and less
    clearly; refusing it here names the mistake."""
    with pytest.raises(MrzValueError):
        CaseFace(document=passport(), image=[[0, 0, 0]])


def test_a_case_face_is_frozen():
    record_ = record()

    with pytest.raises(dataclasses.FrozenInstanceError):
        record_.image = frame(9)


def test_no_field_of_a_case_face_has_a_default():
    for field in dataclasses.fields(CaseFace):
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


# --- the bar the cosine is held to -------------------------------------------


@pytest.mark.parametrize(
    "threshold", [0, 0.0, -0.5, 1.01, 2.0, "0.6", None, True, False]
)
def test_a_bar_no_cosine_could_be_held_to_is_refused(threshold):
    with pytest.raises(MrzValueError):
        face_consistent(
            [record(fill=0), record(fill=1)],
            StubDetector(default=(face(),)),
            SequenceEmbedder([UNIT, OTHER]),
            threshold,
        )


def test_a_bar_at_the_ends_of_the_range_is_accepted():
    """``1.0`` is reachable by a perfect match and ``0.0`` is not a bar."""
    for threshold in (0.0001, 1.0):
        face_consistent(
            [record(fill=0), record(fill=1)],
            StubDetector(default=(face(),)),
            SequenceEmbedder([UNIT, UNIT]),
            threshold,
        )


def test_a_bar_of_one_is_reached_by_a_face_against_itself():
    result = measured(UNIT, UNIT, threshold=1.0)

    assert result.flags == ()


def test_the_bar_is_required_and_has_no_default():
    with pytest.raises(TypeError):
        face_consistent([record()], StubDetector(), SequenceEmbedder())


def test_the_rule_is_asked_for_a_case_two_seams_and_a_bar():
    """13.15's own signature, read the same way: four named arguments, none of
    them keyword-only and none of them starred."""
    assert tuple(inspect.signature(face_consistent).parameters) == (
        "documents_in_case",
        "detector",
        "embedder",
        "threshold",
    )
    assert {
        parameter.kind
        for parameter in inspect.signature(face_consistent).parameters.values()
    } == {inspect.Parameter.POSITIONAL_OR_KEYWORD}


# --- the record --------------------------------------------------------------


def test_the_shared_document_record_still_holds_no_frame():
    """D131: the transcription record stays a transcription, and the two
    earlier rules keep their own no-image guard."""
    source = Path(faces_module.__file__).read_text(encoding="utf-8")
    assert "numpy" in source

    from app.pipeline.crossdoc import documents, validity

    for module in (documents, validity):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(
                (alias.name or "").split(".")[0] in {"cv2", "numpy"}
                for alias in node.names
            )
            for node in ast.walk(tree)
        )


def test_the_module_resolves_no_clock():
    source = Path(faces_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in {"now", "today", "utcnow"}
        for node in ast.walk(tree)
    )


def test_the_module_holds_no_threshold_of_its_own():
    """13.15's threshold rides on the score; this module only carries it."""
    source = Path(faces_module.__file__).read_text(encoding="utf-8")

    assert "THRESHOLD" not in source.replace("threshold", "")


def test_the_module_names_no_model():
    source = Path(faces_module.__file__).read_text(encoding="utf-8")

    assert "InsightFace" not in source and "insightface" not in source


def test_the_answer_is_the_shared_consistency_record():
    result = measured(UNIT, OTHER)

    assert type(result) is __import__(
        "app.pipeline.crossdoc.documents", fromlist=["CaseConsistency"]
    ).CaseConsistency


def test_a_case_face_holds_the_document_the_other_rules_read():
    case = [record(document=visa())]

    assert case[0].document == visa()


def test_the_faces_record_is_exported_under_both_of_its_names():
    assert faces_module.__all__ == ["CaseFace", "face_consistent"]


def test_the_canonical_landmarks_are_the_five_this_rule_aligns():
    """13.14's order is five points, and this rule asks for five."""
    assert len(CANONICAL_LANDMARKS) == len(FACE_LANDMARKS) == 5
