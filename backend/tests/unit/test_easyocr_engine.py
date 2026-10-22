"""12.4 -- ``EasyOcrEngine``: a read where EasyOCR is, an absence where it is not.

The task asks for the same unavailable-rather-than-raising behaviour 12.3 gave
Tesseract, so this module asks the same two questions of it: does absence
answer as a value rather than a raise, and does the read degrade to the same
shared empty read.  What is not the same is the probe -- EasyOCR is one Python
package and not a package plus an executable -- and the channel order, which is
the reason this engine has its own tests rather than inheriting 12.3's.
"""

import inspect

import numpy
import pytest

from app.pipeline.tier1 import easyocr_engine, ocr, tesseract_engine

EasyOcrEngine = easyocr_engine.EasyOcrEngine
NO_WORDS = ocr.NO_WORDS

#: One word as EasyOCR reports it: a four-point box, the text, and a score
#: already on this project's 0.0-1.0 scale.  No identity data -- a label, its
#: box and a confidence.
A_BOX = [[12, 30], [140, 30], [140, 48], [12, 48]]
THE_BOX_AS_A_RECTANGLE = (12, 30, 140, 48)

#: The same four corners shuffled, which is the order EasyOCR actually emits a
#: rotated box in and the one a naive "first two points" reader gets wrong.
A_SHUFFLED_BOX = [[140, 48], [12, 30], [12, 48], [140, 30]]

NOT_INSTALLED = None


class FakeReader:
    """An EasyOCR reader that answers with rows a test wrote down."""

    def __init__(self, rows=None):
        self.rows = [] if rows is None else rows
        self.calls = []

    def readtext(self, image, **options):
        self.calls.append((image, options))
        return self.rows


class FakeBinding:
    """An ``easyocr`` module that builds a reader a test can inspect."""

    def __init__(self, rows=None):
        self.reader = FakeReader(rows)
        self.built = []

    def Reader(self, lang_list):  # noqa: N802 -- easyocr's own spelling
        self.built.append(list(lang_list))
        return self.reader


class ABindingWhoseReaderCannotBeBuilt:
    """An install that is present but cannot load its models."""

    def __init__(self):
        self.attempts = 0

    def Reader(self, lang_list):  # noqa: N802 -- easyocr's own spelling
        self.attempts += 1
        raise RuntimeError("model download failed")


def rows(*specs):
    """EasyOCR's ``[box, text, confidence]`` rows for the given specs.

    Called with no specs it is one default word, so a test about a box or a
    channel order can ask for a readable page without writing a word down;
    ``[]`` is the page holding none.
    """
    if not specs:
        specs = ({},)
    made = []
    for spec in specs:
        made.append([
            spec.get("box", A_BOX),
            spec.get("text", "PASSPORT"),
            spec.get("conf", 0.97),
        ])
    return made


def a_frame():
    """A three-channel BGR frame in the order Tier 0 hands one over."""
    frame = numpy.zeros((1, 3, 3), dtype=numpy.uint8)
    frame[0, 0] = (30, 20, 10)
    frame[0, 1] = (60, 50, 40)
    frame[0, 2] = (90, 80, 70)
    return frame


def an_engine_that_can_read(found_rows=None):
    """An engine whose probe answers yes -- the machine-with branch."""
    return EasyOcrEngine(binding=FakeBinding(found_rows))


def an_engine_that_cannot_read():
    """An engine whose probe answers no -- the machine-without branch."""
    return EasyOcrEngine(binding=NOT_INSTALLED)


# --- it is an engine behind the seam, and the seam is not widened ---


def test_the_engine_is_an_ocr_engine():
    assert issubclass(EasyOcrEngine, ocr.OcrEngine)


def test_the_engine_can_be_built_and_asked():
    assert isinstance(an_engine_that_can_read(), ocr.OcrEngine)


def test_availability_is_a_concrete_method_and_not_a_second_requirement():
    """D82 left availability off the interface; 12.4 answers it as a method."""
    assert ocr.OcrEngine.__abstractmethods__ == frozenset({"read"})
    assert EasyOcrEngine.__abstractmethods__ == frozenset()
    assert callable(EasyOcrEngine.is_available)


def test_read_still_takes_exactly_one_frame_and_answers_a_result():
    """An engine cannot smuggle a language or a decoder back onto the seam."""
    signature = inspect.signature(EasyOcrEngine.read)
    assert tuple(signature.parameters) == ("self", "image")
    assert signature.return_annotation is ocr.OcrResult


# --- the task's own verification: available here, unavailable there ---


def test_an_engine_without_easyocr_reports_itself_unavailable():
    assert an_engine_that_cannot_read().is_available() is False


def test_an_engine_with_easyocr_reports_itself_available():
    assert an_engine_that_can_read().is_available() is True


def test_availability_is_always_a_bool_and_never_a_raise():
    """Asking the question is safe in every state, including the absent one."""
    for engine in (an_engine_that_cannot_read(), an_engine_that_can_read(), EasyOcrEngine()):
        assert isinstance(engine.is_available(), bool)


def test_asking_a_missing_easyocr_never_raises_import_error():
    """A box with no easyocr answers False instead of raising ImportError."""
    assert EasyOcrEngine(binding=NOT_INSTALLED).is_available() is False


def test_availability_is_one_question_and_not_two():
    """EasyOCR is a package, not a package plus an executable to find.

    Tesseract's engine takes a second probe because it has a second half to be
    missing.  This one takes no such argument, so there is no way for the
    answer to be half-true -- and no second probe for a test to inject a lie
    through.
    """
    assert tuple(inspect.signature(EasyOcrEngine.__init__).parameters) == ("self", "binding")


def test_this_machine_agrees_with_itself():
    """The one test that touches the real machine, and it asserts no verdict.

    It passes on a box with EasyOCR and on a box without, because it compares
    the engine's answer to the thing it is built from rather than to a fixed
    expectation.
    """
    engine = EasyOcrEngine()
    assert engine.is_available() is (easyocr_engine._import_easyocr() is not None)


def test_easyocr_is_not_imported_at_module_scope():
    """A module-scope import would make this module an ``ImportError`` on

    every box that has not installed EasyOCR -- the exact failure the task
    asks 12.4 not to have.
    """
    assert "easyocr" not in vars(easyocr_engine)


# --- reading on a machine without EasyOCR ---


def test_reading_without_easyocr_is_the_empty_read_and_not_a_raise():
    assert an_engine_that_cannot_read().read(a_frame()) == NO_WORDS


def test_reading_without_easyocr_returns_the_shared_value_itself():
    """The same object Tier 1 degrades to, not an equal-looking copy."""
    assert an_engine_that_cannot_read().read(a_frame()) is NO_WORDS


def test_both_engines_degrade_to_the_same_shared_value():
    """D83's reason for one NO_WORDS, now that there are two engines to answer.

    Two spellings of "nothing found" would read later as two findings, which is
    the bug the shared value exists to prevent.
    """
    tesseract = tesseract_engine.TesseractEngine(locate=lambda _binary: None, binding=None)
    easy = EasyOcrEngine(binding=NOT_INSTALLED)
    assert tesseract.read(a_frame()) is easy.read(a_frame()) is NO_WORDS


def test_reading_without_easyocr_never_builds_a_reader():
    """No absent engine gets as far as constructing the thing that reads."""
    binding = FakeBinding(rows({"text": "PASSPORT"}))
    EasyOcrEngine(binding=NOT_INSTALLED).read(a_frame())
    assert binding.built == []


def test_a_reader_that_cannot_be_built_is_a_broken_install_and_raises():
    """A present package whose models cannot load is not an absent engine.

    D83 forbids read raising for a missing binary or a missing binding, and
    permits it for a broken install: swallowing this would report a blank page
    on a box whose EasyOCR is installed and merely unreachable.
    """
    with pytest.raises(RuntimeError):
        EasyOcrEngine(binding=ABindingWhoseReaderCannotBeBuilt()).read(a_frame())


# --- reading on a machine with EasyOCR ---


def test_every_word_is_read_with_its_text_its_box_and_its_confidence():
    word = an_engine_that_can_read(rows()).read(a_frame()).words[0]
    assert word.text == "PASSPORT"
    assert word.bbox == THE_BOX_AS_A_RECTANGLE
    assert word.confidence == 0.97


def test_a_box_is_read_as_the_extent_of_its_points_and_not_as_its_first_two():
    """EasyOCR reports four unordered corners, not an origin and a size."""
    word = an_engine_that_can_read(rows({"box": A_SHUFFLED_BOX})).read(a_frame()).words[0]
    assert word.bbox == THE_BOX_AS_A_RECTANGLE


def test_the_words_come_back_in_the_order_easyocr_reported_them():
    found = rows({"text": "PASSPORT"}, {"text": "NUMBER"}, {"text": "ERIKSSON"})
    result = an_engine_that_can_read(found).read(a_frame())
    assert [word.text for word in result.words] == ["PASSPORT", "NUMBER", "ERIKSSON"]


def test_a_region_of_only_spaces_is_not_a_word():
    found = rows({"text": "PASSPORT"}, {"text": "   "})
    result = an_engine_that_can_read(found).read(a_frame())
    assert [word.text for word in result.words] == ["PASSPORT"]


def test_a_confidence_that_is_not_a_number_is_not_a_word():
    found = rows({"text": "PASSPORT"}, {"text": "NO", "conf": "n/a"})
    result = an_engine_that_can_read(found).read(a_frame())
    assert [word.text for word in result.words] == ["PASSPORT"]


def test_a_confidence_above_one_is_clamped_to_one():
    """A score above the range would otherwise lift 12.9's gate on a bad read."""
    word = an_engine_that_can_read(rows({"conf": 1.4})).read(a_frame()).words[0]
    assert word.confidence == 1.0


def test_a_confidence_below_zero_is_clamped_to_zero():
    word = an_engine_that_can_read(rows({"conf": -0.5})).read(a_frame()).words[0]
    assert word.confidence == 0.0


def test_a_word_of_zero_confidence_is_still_a_word():
    """Zero means EasyOCR was unsure, which is 12.9's gate's problem, not ours."""
    word = an_engine_that_can_read(rows({"conf": 0.0})).read(a_frame()).words[0]
    assert word.confidence == 0.0


def test_the_mean_confidence_is_the_mean_of_the_words_that_were_read():
    found = rows({"text": "A", "conf": 0.8}, {"text": "B", "conf": 0.6}, {"text": "", "conf": 0.1})
    result = an_engine_that_can_read(found).read(a_frame())
    assert result.mean_confidence == pytest.approx(0.7)


def test_the_mean_confidence_ignores_a_row_that_is_not_a_word():
    """A dropped row must not drag the mean of the page toward its own score."""
    found = rows({"text": "A", "conf": 1.0}, {"text": "B", "conf": "n/a"})
    result = an_engine_that_can_read(found).read(a_frame())
    assert result.mean_confidence == 1.0


def test_a_page_holding_no_words_is_the_shared_empty_read():
    assert an_engine_that_can_read([]).read(a_frame()) is NO_WORDS


# --- the options that decide what comes back ---


def test_the_read_asks_for_detail_and_not_for_a_paragraph():
    """One row per box, not one per paragraph of boxes."""
    binding = FakeBinding(rows())
    EasyOcrEngine(binding=binding).read(a_frame())
    _, options = binding.reader.calls[0]
    assert options == {"detail": 1, "paragraph": False, "output_format": "standard"}


def test_the_reader_is_built_for_the_project_languages():
    """Languages are a module constant, never a caller argument."""
    binding = FakeBinding(rows())
    EasyOcrEngine(binding=binding).read(a_frame())
    assert binding.built == [["en"]]


def test_the_reader_is_built_once_and_kept_across_documents():
    """It carries the loaded models; rebuilding would re-load them per page."""
    binding = FakeBinding(rows())
    engine = EasyOcrEngine(binding=binding)
    engine.read(a_frame())
    engine.read(a_frame())
    assert binding.built == [["en"]]


# --- the frame, in the order EasyOCR actually reads it ---


def test_the_frame_is_handed_over_in_tier_0s_bgr_order():
    """EasyOCR reads a three-channel array as BGR and greys it as BGR.

    This is the one place this engine must differ from 12.3: reversing the
    frame the way pytesseract needs would swap the two channels EasyOCR
    normalises, and every box, text and confidence would still look plausible.
    """
    binding = FakeBinding(rows())
    EasyOcrEngine(binding=binding).read(a_frame())
    assert list(binding.reader.calls[0][0][0, 0]) == [30, 20, 10]


def test_the_frame_is_handed_over_as_a_readable_array():
    binding = FakeBinding(rows())
    EasyOcrEngine(binding=binding).read(a_frame())
    assert binding.reader.calls[0][0].flags["C_CONTIGUOUS"] is True


def test_the_frame_handed_over_is_a_copy_and_not_the_frame_itself():
    binding = FakeBinding(rows())
    frame = a_frame()
    EasyOcrEngine(binding=binding).read(frame)
    assert binding.reader.calls[0][0] is not frame


def test_reading_leaves_the_frame_it_was_handed_untouched():
    binding = FakeBinding(rows())
    frame = a_frame()
    before = frame.copy()
    EasyOcrEngine(binding=binding).read(frame)
    assert numpy.array_equal(frame, before)


# --- the names the module exports ---


def test_every_name_in_all_exists_in_the_module():
    for name in easyocr_engine.__all__:
        assert hasattr(easyocr_engine, name)
