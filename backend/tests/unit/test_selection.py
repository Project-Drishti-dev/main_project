"""12.5 -- ``select_engine``: a preference, an order, or no engine at all.

The task names three cases, and the first three groups below are those: an
explicit preference, the first available engine, and none available.  What
follows is what those three cannot check on their own -- the order is the
policy and is pinned, a preference is asked about alone, an unavailable
preference is not quietly answered with another engine, and the seam this
module reads does not declare the question it asks.

The engines are stubs answering ``is_available()`` as a test wrote it down, so
every case here means the same thing on a station with Tesseract and on one
without; the two tests at the end are the only ones that touch the real
registry, and they hold the answer to "one of ours or none" rather than to any
particular machine's answer.
"""

import inspect

import pytest

from app.pipeline.tier1 import ocr, selection
from app.pipeline.tier1.easyocr_engine import EasyOcrEngine
from app.pipeline.tier1.tesseract_engine import TesseractEngine

OcrEngine = ocr.OcrEngine
NO_WORDS = ocr.NO_WORDS

#: The two preference spellings, read off the module rather than retyped here,
#: so a renamed constant fails this file instead of passing against a
#: hard-coded string that no longer names anything.
TESSERACT = selection.TESSERACT
EASYOCR = selection.EASYOCR


class StubEngine(OcrEngine):
    """An engine that answers availability as it was told, and counts the asks.

    The count is what proves a question was not asked, and ``reads`` is what
    proves selecting an engine did not read a page to find out it could.
    """

    def __init__(self, available):
        self.available = available
        self.asked = 0
        self.reads = []

    def is_available(self):
        self.asked += 1
        return self.available

    def read(self, image):
        self.reads.append(image)
        return NO_WORDS


class BrokenEngine(StubEngine):
    """An installed engine whose probe itself faults."""

    def is_available(self):
        self.asked += 1
        raise RuntimeError("the reader cannot be built")


def registry(*specs):
    """A registry of stub engines from ``(name, available)`` specs, in order."""
    return {name: StubEngine(available) for name, available in specs}


# --- the three cases the task names ---


def test_no_preference_answers_the_first_available_engine():
    engines = registry((TESSERACT, True), (EASYOCR, True))
    assert selection.select_engine(engines=engines) is engines[TESSERACT]


def test_no_preference_answers_the_first_engine_that_is_available():
    """Tesseract unavailable, so the walk reaches the engine after it."""
    engines = registry((TESSERACT, False), (EASYOCR, True))
    assert selection.select_engine(engines=engines) is engines[EASYOCR]


def test_an_explicit_preference_is_answered_in_preference_of_the_order():
    engines = registry((TESSERACT, True), (EASYOCR, True))
    assert selection.select_engine(EASYOCR, engines=engines) is engines[EASYOCR]


def test_an_explicit_preference_that_is_not_available_answers_none():
    """The case the task names, and the one a fallback chain would get wrong."""
    engines = registry((TESSERACT, True), (EASYOCR, False))
    assert selection.select_engine(EASYOCR, engines=engines) is None


def test_an_unavailable_preference_is_not_answered_with_another_engine():
    """A preference is a choice: no substitution, even for an available engine."""
    engines = registry((TESSERACT, True), (EASYOCR, False))
    selection.select_engine(EASYOCR, engines=engines)
    assert engines[TESSERACT].asked == 0


def test_no_available_engine_answers_none():
    engines = registry((TESSERACT, False), (EASYOCR, False))
    assert selection.select_engine(engines=engines) is None


def test_a_registry_holding_no_engines_answers_none():
    assert selection.select_engine(engines={}) is None


def test_a_preference_is_answered_from_a_registry_of_one():
    engines = registry((EASYOCR, True))
    assert selection.select_engine(EASYOCR, engines=engines) is engines[EASYOCR]


def test_a_preference_naming_the_only_engine_is_answered_when_it_is_available():
    engines = registry((TESSERACT, True))
    assert selection.select_engine(TESSERACT, engines=engines) is engines[TESSERACT]


def test_a_preference_naming_the_only_engine_answers_none_when_it_is_unavailable():
    engines = registry((TESSERACT, False))
    assert selection.select_engine(TESSERACT, engines=engines) is None


# --- the order, which is the policy and not the alphabet ---


def test_the_order_walked_is_the_registrys_own_and_not_alphabetical():
    """The mirror of the walk reaching the second engine, pinning both ways."""
    engines = registry((EASYOCR, True), (TESSERACT, False))
    assert selection.select_engine(engines=engines) is engines[EASYOCR]


def test_an_engine_after_the_one_chosen_is_never_asked():
    engines = registry((TESSERACT, True), (EASYOCR, True))
    selection.select_engine(engines=engines)
    assert engines[EASYOCR].asked == 0


def test_naming_an_engine_asks_about_that_engine_only():
    engines = registry((TESSERACT, False), (EASYOCR, True))
    selection.select_engine(EASYOCR, engines=engines)
    assert engines[TESSERACT].asked == 0
    assert engines[EASYOCR].asked == 1


def test_the_engine_chosen_is_the_object_the_registry_holds():
    engines = registry((TESSERACT, False), (EASYOCR, True))
    chosen = selection.select_engine(engines=engines)
    assert chosen is engines[EASYOCR]


def test_selecting_an_engine_never_reads_a_page():
    """Choosing must not be the thing that does a read's work (``D84``)."""
    engines = registry((TESSERACT, True), (EASYOCR, True))
    selection.select_engine(engines=engines)
    selection.select_engine(EASYOCR, engines=engines)
    assert [engine.reads for engine in engines.values()] == [[], []]


def test_a_probe_that_faults_is_not_swallowed_by_the_selector():
    """``D83`` made absence a bool, so choosing is not a handler (``D74``)."""
    broken = BrokenEngine(True)
    with pytest.raises(RuntimeError):
        selection.select_engine(engines={TESSERACT: broken})
    assert broken.asked == 1


# --- a preference that names no engine is a refusal, not an absence ---


@pytest.mark.parametrize(
    "preference",
    ["tesseract ", " TESSERACT", "Tesseract", "paddleocr", "", "tesseract\n"],
)
def test_a_preference_naming_no_engine_is_refused(preference):
    with pytest.raises(selection.UnknownEngineError):
        selection.select_engine(preference, engines=registry((TESSERACT, True)))


@pytest.mark.parametrize("preference", [True, 0, 1, b"tesseract", ("tesseract",)])
def test_a_preference_that_is_not_a_string_is_refused(preference):
    with pytest.raises(selection.UnknownEngineError):
        selection.select_engine(preference, engines=registry((TESSERACT, True)))


def test_the_refusal_is_a_value_error():
    with pytest.raises(ValueError):
        selection.select_engine("paddleocr", engines=registry((TESSERACT, True)))


def test_the_refusal_names_the_engines_it_knows_and_the_one_asked_for():
    engines = registry((TESSERACT, True), (EASYOCR, True))
    with pytest.raises(selection.UnknownEngineError) as refusal:
        selection.select_engine("paddleocr", engines=engines)
    message = str(refusal.value)
    assert TESSERACT in message
    assert EASYOCR in message
    assert "paddleocr" in message


def test_a_preference_the_registrys_order_does_not_hold_is_still_refused():
    """Order is not permission: a name outside the registry is a refusal."""
    with pytest.raises(selection.UnknownEngineError):
        selection.select_engine(EASYOCR, engines=registry((TESSERACT, True)))


# --- the registry the default choice is made from ---


def test_every_name_in_all_exists_in_the_module():
    for name in selection.__all__:
        assert hasattr(selection, name)


def test_engine_names_is_the_order_the_default_registry_holds():
    assert tuple(selection.DEFAULT_ENGINES) == selection.ENGINE_NAMES


def test_the_default_registry_holds_one_engine_of_each_project_kind():
    assert isinstance(selection.DEFAULT_ENGINES[TESSERACT], TesseractEngine)
    assert isinstance(selection.DEFAULT_ENGINES[EASYOCR], EasyOcrEngine)


def test_the_default_registry_holds_the_module_engines_rather_than_new_ones():
    """One engine each, so EasyOCR's reader is not rebuilt per document."""
    assert selection.DEFAULT_ENGINES[TESSERACT] is selection.TESSERACT_ENGINE
    assert selection.DEFAULT_ENGINES[EASYOCR] is selection.EASYOCR_ENGINE


def test_the_default_registry_cannot_be_changed_by_a_caller():
    with pytest.raises(TypeError):
        selection.DEFAULT_ENGINES["paddleocr"] = StubEngine(True)


def test_selecting_from_the_default_registry_answers_ours_or_none():
    """Machine-agnostic: this box has neither engine and that is a valid answer."""
    chosen = selection.select_engine()
    assert chosen in (None, selection.TESSERACT_ENGINE, selection.EASYOCR_ENGINE)


def test_selecting_from_the_default_registry_honours_a_preference_ours():
    chosen = selection.select_engine(EASYOCR)
    assert chosen in (None, selection.EASYOCR_ENGINE)


# --- the signature, read from the source rather than from a call ---


def _select_signature():
    return inspect.signature(selection.select_engine)


def test_the_signature_is_a_preference_and_a_registry():
    assert tuple(_select_signature().parameters) == ("preference", "engines")


def test_the_registry_is_keyword_only():
    """Two registries in a row, and a second positional would be read as a name."""
    kinds = {p.kind for p in _select_signature().parameters.values()}
    assert inspect.Parameter.KEYWORD_ONLY in kinds
    assert inspect.Parameter.VAR_POSITIONAL not in kinds
    assert inspect.Parameter.VAR_KEYWORD not in kinds


def test_no_argument_takes_a_varargs_or_a_kwargs():
    parameters = _select_signature().parameters.values()
    assert [p.name for p in parameters if p.kind is inspect.Parameter.VAR_POSITIONAL] == []
    assert [p.name for p in parameters if p.kind is inspect.Parameter.VAR_KEYWORD] == []


def test_the_return_annotation_names_an_engine_or_nothing():
    """``None`` is half of what this function answers, and it is in the type."""
    assert _select_signature().return_annotation == (OcrEngine | None)