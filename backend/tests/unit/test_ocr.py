"""12.2 -- the ``OcrEngine`` interface, and a stub that satisfies it.

The task's claim is that a stub satisfies the interface, so the first group
below is that claim: a stub subclasses ``OcrEngine``, can be built and asked,
and a subclass that forgets ``read`` cannot be built at all.  The signature is
read from the source rather than called, because a method that happens to work
when called proves less than a signature -- a second argument carrying a DPI,
or one with a default, would leave every behavioural test here passing.
"""

import dataclasses
import inspect

import pytest

from app.pipeline.tier1 import ocr

OcrEngine = ocr.OcrEngine
OcrResult = ocr.OcrResult
OcrWord = ocr.OcrWord

#: One word in the shape an engine reports it, holding no identity data this
#: project can print: a label, its box, and a confidence.
A_WORD = OcrWord(text="PASSPORT", bbox=(12, 30, 140, 48), confidence=0.97)
ANOTHER_WORD = OcrWord(text="NO", bbox=(12, 52, 44, 70), confidence=0.81)

#: The mean of the two words above, kept as the arithmetic rather than a
#: literal so a test asserting it cannot drift from the records it is about.
THEIR_MEAN = (A_WORD.confidence + ANOTHER_WORD.confidence) / 2

#: An empty read: what Tier 1 degrades to when no engine could read the page.
NO_WORDS = OcrResult(words=(), mean_confidence=0.0)


class StubEngine(OcrEngine):
    """An engine that answers from a result it was handed, and never reads."""

    def __init__(self, result=None):
        self.result = NO_WORDS if result is None else result
        self.seen = []

    def read(self, image):
        self.seen.append(image)
        return self.result


class AStubThatForgetsRead(OcrEngine):
    """An engine that wired everything except the one method the task names."""

    def is_available(self):
        return True


# --- the task's own claim: a stub satisfies the interface ---


def test_a_stub_subclasses_the_interface():
    assert issubclass(StubEngine, OcrEngine)


def test_a_stub_can_be_instantiated_and_asked():
    assert StubEngine().read(object()) == NO_WORDS


def test_the_interface_itself_cannot_be_instantiated():
    with pytest.raises(TypeError):
        OcrEngine()


def test_a_stub_that_forgets_read_cannot_be_instantiated():
    """The abstract method is what makes the interface checkable."""
    with pytest.raises(TypeError):
        AStubThatForgetsRead()


def test_read_is_the_only_method_the_interface_requires():
    """Availability is 12.3's question, so nothing else is required here."""
    assert OcrEngine.__abstractmethods__ == frozenset({"read"})


def test_a_caller_can_hold_a_stub_as_the_interface():
    """The point of the seam: the caller is written against the interface."""
    assert isinstance(StubEngine(), OcrEngine)


# --- the signature, read from the source rather than from a call ---


def _read_signature():
    return inspect.signature(OcrEngine.read)


def test_read_takes_exactly_the_one_argument_the_task_names():
    assert tuple(_read_signature().parameters) == ("self", "image")


def test_the_image_argument_is_positional():
    kinds = {p.kind for p in _read_signature().parameters.values()}
    assert inspect.Parameter.POSITIONAL_OR_KEYWORD in kinds
    assert inspect.Parameter.VAR_POSITIONAL not in kinds
    assert inspect.Parameter.VAR_KEYWORD not in kinds


def test_no_argument_has_a_default():
    """An omitted image is a page nobody read, not a page read as empty."""
    assert [
        p.default
        for p in _read_signature().parameters.values()
        if p.default is not inspect.Parameter.empty
    ] == []


def test_read_answers_an_ocr_result():
    """A stub answering any other shape would leave the caller reading one."""
    assert _read_signature().return_annotation is OcrResult


def test_a_stub_is_handed_the_frame_it_was_asked_about():
    frame = object()
    stub = StubEngine()
    stub.read(frame)
    assert stub.seen == [frame]


# --- the two records the interface answers with ---


def test_a_word_carries_its_text_its_box_and_its_confidence():
    assert A_WORD.text == "PASSPORT"
    assert A_WORD.bbox == (12, 30, 140, 48)
    assert A_WORD.confidence == 0.97


def test_a_result_carries_its_words_and_their_mean_confidence():
    result = OcrResult(words=(A_WORD, ANOTHER_WORD), mean_confidence=THEIR_MEAN)
    assert result.words == (A_WORD, ANOTHER_WORD)
    assert result.mean_confidence == pytest.approx(0.89)


def test_a_page_of_no_words_is_an_empty_read_and_not_a_missing_one():
    assert NO_WORDS.words == ()
    assert NO_WORDS.mean_confidence == 0.0


def test_a_word_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        A_WORD.confidence = 0.5


def test_a_result_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        NO_WORDS.mean_confidence = 0.5


def test_every_name_in_all_exists_in_the_module():
    for name in ocr.__all__:
        assert hasattr(ocr, name)
