"""12.3 -- ``TesseractEngine``: a read where Tesseract is, an absence where it is not.

The task asks that the availability test pass on a machine with and without
Tesseract, so neither branch is left to whichever machine runs the suite: the
two probes are injected -- where the binary is, and what stands in for the
``pytesseract`` binding -- and the one test that does touch the real machine
asserts the engine agrees with the machine rather than asserting it is there.
"""

import inspect
import shutil

import numpy

from app.pipeline.tier1 import ocr, tesseract_engine

TesseractEngine = tesseract_engine.TesseractEngine
NO_WORDS = ocr.NO_WORDS

#: Where a probe says Tesseract lives, and what it says when nothing is found.
A_PATH_TO_TESSERACT = "C:/Program Files/Tesseract-OCR/tesseract.exe"
NOT_INSTALLED = None


class Output:
    """The one corner of ``pytesseract``'s shape the engine reads."""

    DICT = "dict"


class FakeBinding:
    """A ``pytesseract`` that returns rows a test wrote down, and records calls."""

    Output = Output

    def __init__(self, data=None):
        self.data = {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []} if data is None else data
        self.calls = []

    def image_to_data(self, image, **options):
        self.calls.append((image, options))
        return self.data


def rows(*specs):
    """pytesseract's dict output for the given rows: text, conf, and a box."""
    data = {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}
    for spec in specs:
        row = {
            "text": spec.get("text", "PASSPORT"),
            "conf": spec.get("conf", "97.5"),
            "left": spec.get("left", 12),
            "top": spec.get("top", 30),
            "width": spec.get("width", 128),
            "height": spec.get("height", 18),
        }
        for key, value in row.items():
            data[key].append(value)
    return data


def found(_binary):
    """A locate probe that finds Tesseract."""
    return A_PATH_TO_TESSERACT


def not_found(_binary):
    """A locate probe for a machine where Tesseract was never installed."""
    return NOT_INSTALLED


def a_frame():
    """A three-channel BGR frame in the order Tier 0 hands one over."""
    frame = numpy.zeros((1, 3, 3), dtype=numpy.uint8)
    frame[0, 0] = (30, 20, 10)
    frame[0, 1] = (60, 50, 40)
    frame[0, 2] = (90, 80, 70)
    return frame


def an_engine_that_can_read(binding=None):
    """An engine with both probes answering yes -- the machine-with branch."""
    return TesseractEngine(locate=found, binding=FakeBinding() if binding is None else binding)


def an_engine_that_cannot_read():
    """An engine with both probes answering no -- the machine-without branch."""
    return TesseractEngine(locate=not_found, binding=None)


# --- it is an engine behind the seam, and the seam is not widened ---


def test_the_engine_is_an_ocr_engine():
    assert issubclass(TesseractEngine, ocr.OcrEngine)


def test_the_engine_can_be_built_and_asked():
    assert isinstance(an_engine_that_can_read(), ocr.OcrEngine)


def test_availability_is_a_concrete_method_and_not_a_second_requirement():
    """D82 left availability off the interface; 12.3 answers it as a method."""
    assert ocr.OcrEngine.__abstractmethods__ == frozenset({"read"})
    assert TesseractEngine.__abstractmethods__ == frozenset()
    assert callable(TesseractEngine.is_available)


def test_read_still_takes_exactly_one_frame_and_answers_a_result():
    """An engine cannot smuggle a dpi or a psm back onto the seam."""
    signature = inspect.signature(TesseractEngine.read)
    assert tuple(signature.parameters) == ("self", "image")
    assert signature.return_annotation is ocr.OcrResult


# --- the task's own verification: available here, unavailable there ---


def test_an_engine_whose_binary_is_missing_reports_itself_unavailable():
    assert an_engine_that_cannot_read().is_available() is False


def test_an_engine_with_the_binary_and_the_binding_reports_itself_available():
    assert an_engine_that_can_read().is_available() is True


def test_availability_is_always_a_bool_and_never_a_raise():
    """Asking the question is safe in every state, including both parts absent."""
    for engine in (an_engine_that_cannot_read(), an_engine_that_can_read(), TesseractEngine()):
        assert isinstance(engine.is_available(), bool)


def test_the_binary_alone_is_not_availability():
    """The binary cannot be driven without the binding that drives it."""
    assert TesseractEngine(locate=found, binding=None).is_available() is False


def test_the_binding_alone_is_not_availability():
    """The binding is useless without the executable it shells out to."""
    assert TesseractEngine(locate=not_found, binding=FakeBinding()).is_available() is False


def test_the_probe_is_asked_about_the_tesseract_binary_by_name():
    asked = []

    def recording_locate(binary):
        asked.append(binary)
        return A_PATH_TO_TESSERACT

    TesseractEngine(locate=recording_locate, binding=FakeBinding()).is_available()
    assert asked == ["tesseract"]


def test_this_machine_agrees_with_itself():
    """The one test that touches the real machine, and it asserts no verdict.

    It passes on a box with Tesseract and on a box without, because it compares
    the engine's answer to the two things it is built from rather than to a
    fixed expectation.
    """
    engine = TesseractEngine()
    expected = shutil.which("tesseract") is not None and tesseract_engine._import_pytesseract() is not None
    assert engine.is_available() is expected


def test_asking_a_missing_tesseract_never_imports_error():
    """A box with no pytesseract answers False instead of raising ImportError."""
    engine = TesseractEngine(locate=not_found)
    assert engine.is_available() is False


# --- reading on a machine without Tesseract ---


def test_reading_without_tesseract_is_the_empty_read_and_not_a_raise():
    assert an_engine_that_cannot_read().read(a_frame()) == NO_WORDS


def test_reading_without_tesseract_never_calls_the_binding():
    binding = FakeBinding()
    TesseractEngine(locate=not_found, binding=binding).read(a_frame())
    assert binding.calls == []


def test_reading_without_the_binding_never_calls_the_binary():
    asked = []

    def recording_locate(binary):
        asked.append(binary)
        return A_PATH_TO_TESSERACT

    TesseractEngine(locate=recording_locate, binding=None).read(a_frame())
    assert asked == []


# --- reading on a machine with Tesseract ---


def test_every_word_is_read_with_its_text_its_box_and_its_confidence():
    engine = an_engine_that_can_read(FakeBinding(rows({"text": "PASSPORT", "left": 12, "top": 30, "width": 128, "height": 18, "conf": "97.5"})))
    word = engine.read(a_frame()).words[0]
    assert word.text == "PASSPORT"
    assert word.bbox == (12, 30, 140, 48)
    assert word.confidence == 0.975


def test_the_read_asks_for_a_dict_of_words_and_full_page_segmentation():
    binding = FakeBinding(rows())
    an_engine_that_can_read(binding).read(a_frame())
    _, options = binding.calls[0]
    assert options == {"lang": "eng", "config": "--psm 3", "output_type": "dict"}


def test_a_block_row_is_not_a_word():
    """pytesseract scores its block, paragraph and line rows at -1."""
    data = rows({"text": "PASSPORT", "conf": "90.0"}, {"text": "", "conf": "-1"}, {"text": "NO", "conf": "-1"})
    result = an_engine_that_can_read(FakeBinding(data)).read(a_frame())
    assert [word.text for word in result.words] == ["PASSPORT"]


def test_a_row_of_only_spaces_is_not_a_word():
    data = rows({"text": "PASSPORT"}, {"text": "   "})
    assert len(an_engine_that_can_read(FakeBinding(data)).read(a_frame()).words) == 1


def test_a_confidence_that_is_not_a_number_is_not_a_word():
    data = rows({"text": "PASSPORT"}, {"text": "NO", "conf": "n/a"})
    assert [w.text for w in an_engine_that_can_read(FakeBinding(data)).read(a_frame()).words] == ["PASSPORT"]


def test_a_word_of_zero_confidence_is_still_a_word():
    """Only the -1 block score means "not a word"; 0 means Tesseract was unsure."""
    data = rows({"text": "PASSPORT", "conf": "0"})
    assert an_engine_that_can_read(FakeBinding(data)).read(a_frame()).words[0].confidence == 0.0


def test_a_full_score_does_not_exceed_one():
    data = rows({"text": "PASSPORT", "conf": "100"})
    assert an_engine_that_can_read(FakeBinding(data)).read(a_frame()).words[0].confidence == 1.0


def test_the_words_come_back_in_the_order_tesseract_reported_them():
    data = rows({"text": "PASSPORT"}, {"text": "NUMBER"}, {"text": "ERIKSSON"})
    result = an_engine_that_can_read(FakeBinding(data)).read(a_frame())
    assert [word.text for word in result.words] == ["PASSPORT", "NUMBER", "ERIKSSON"]


def test_the_mean_confidence_is_the_mean_of_the_words_that_were_read():
    data = rows({"text": "A", "conf": "80.0"}, {"text": "B", "conf": "60.0"}, {"text": "", "conf": "0.0"})
    result = an_engine_that_can_read(FakeBinding(data)).read(a_frame())
    assert result.mean_confidence == 0.7


def test_the_mean_confidence_ignores_a_row_that_is_not_a_word():
    """A dropped row must not drag the mean of the page toward its own score."""
    data = rows({"text": "A", "conf": "100.0"}, {"text": "", "conf": "-1"})
    assert an_engine_that_can_read(FakeBinding(data)).read(a_frame()).mean_confidence == 1.0


def test_a_page_holding_no_words_is_the_shared_empty_read():
    """The same value Tier 1 degrades to, not a second spelling of nothing."""
    assert an_engine_that_can_read(FakeBinding()).read(a_frame()) == NO_WORDS


def test_the_frame_is_handed_over_as_rgb():
    """Tier 0 works in BGR and pytesseract's PIL path reads the array as RGB."""
    binding = FakeBinding(rows())
    an_engine_that_can_read(binding).read(a_frame())
    handed_over = binding.calls[0][0]
    assert list(handed_over[0, 0]) == [10, 20, 30]


def test_the_frame_is_handed_over_as_a_readable_array():
    """A reversed view would leave PIL with a negative-stride buffer."""
    binding = FakeBinding(rows())
    an_engine_that_can_read(binding).read(a_frame())
    assert binding.calls[0][0].flags["C_CONTIGUOUS"] is True


def test_the_frame_handed_over_is_a_copy_and_not_the_frame_itself():
    binding = FakeBinding(rows())
    frame = a_frame()
    an_engine_that_can_read(binding).read(frame)
    assert binding.calls[0][0] is not frame


def test_reading_leaves_the_frame_it_was_handed_untouched():
    binding = FakeBinding(rows())
    frame = a_frame()
    before = frame.copy()
    an_engine_that_can_read(binding).read(frame)
    assert numpy.array_equal(frame, before)


# --- the names the module exports ---


def test_every_name_in_all_exists_in_the_module():
    for name in tesseract_engine.__all__:
        assert hasattr(tesseract_engine, name)