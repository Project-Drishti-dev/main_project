"""12.6 -- Tier 1 degrades to "ocr unavailable", and the document still gets a result.

The claim this file pins is the task's: an absent engine is answered by a
value, not by a refusal, so a missing OCR engine cannot fail a document.  What
stays loud instead, and why the degrade is a branch rather than a catch, is
D86; what the two 12.5 decisions already fixed is not re-argued here.

The engines are stubs answering availability as a test wrote it down, so every
case means the same thing on a station with Tesseract and on one without; the
one test that touches the real registry says so and skips rather than assume.
"""

import ast
import dataclasses
import inspect
import pathlib

import pytest

from app.pipeline.tier1 import ocr, runner, selection

Tier1Result = runner.Tier1Result
run_tier1 = runner.run_tier1
NO_WORDS = ocr.NO_WORDS

#: The two preference spellings, read off the selector rather than retyped.
TESSERACT = selection.TESSERACT
EASYOCR = selection.EASYOCR

#: A frame standing in for the one Tier 0 hands over.  Nothing here reads it,
#: so it is a marker rather than an image the engines would refuse.
PAGE = object()

#: One read of one page with a word in it, so "what the engine reported" and
#: "what Tier 1 carried" are two different objects a test can tell apart.
READ = ocr.OcrResult(
    words=(ocr.OcrWord(text="PASSPORT", bbox=(10, 20, 80, 40), confidence=0.91),),
    mean_confidence=0.91,
)


class StubEngine(ocr.OcrEngine):
    """An engine answering availability as it was told, and recording its reads."""

    def __init__(self, available, result=None):
        self.available = available
        self.asked = 0
        self.reads = []
        self.result = NO_WORDS if result is None else result

    def is_available(self):
        self.asked += 1
        return self.available

    def read(self, image):
        self.reads.append(image)
        return self.result


class FaultingRead(StubEngine):
    """An installed engine whose read faults: a broken install, not an absence."""

    def read(self, image):
        self.reads.append(image)
        raise RuntimeError("the reader cannot be built")


class FaultingProbe(StubEngine):
    """An installed engine whose own availability probe faults."""

    def is_available(self):
        self.asked += 1
        raise RuntimeError("the reader cannot be built")


def registry(*specs):
    """A registry of stub engines from ``(name, available[, result])`` specs."""
    return {spec[0]: StubEngine(*spec[1:]) for spec in specs}


# --- the degrade the task names: no engine, and a result anyway ---


def test_no_engine_installed_answers_a_result_rather_than_a_refusal():
    engines = registry((TESSERACT, False), (EASYOCR, False))
    result = run_tier1(PAGE, engines=engines)
    assert isinstance(result, Tier1Result)
    assert result.ocr_available is False


def test_the_degraded_read_is_the_shared_empty_read():
    """One spelling of nothing, not a second one written here."""
    engines = registry((TESSERACT, False))
    assert run_tier1(PAGE, engines=engines).ocr is NO_WORDS


def test_the_degraded_read_carries_no_words_and_no_confidence():
    engines = registry((TESSERACT, False))
    degraded = run_tier1(PAGE, engines=engines).ocr
    assert degraded.words == ()
    assert degraded.mean_confidence == 0.0


def test_nothing_is_read_when_no_engine_is_available():
    """A page with nothing to read it with is not read by an engine anyway."""
    engines = registry((TESSERACT, False), (EASYOCR, False))
    run_tier1(PAGE, engines=engines)
    assert [engine.reads for engine in engines.values()] == [[], []]


def test_a_registry_holding_no_engines_degrades_the_same_way():
    result = run_tier1(PAGE, engines={})
    assert result.ocr_available is False
    assert result.ocr is NO_WORDS


def test_an_unavailable_preference_degrades_and_asks_about_no_other_engine():
    """12.5's non-substitution reaches the document: no silent second read."""
    engines = registry((TESSERACT, True), (EASYOCR, False))
    result = run_tier1(PAGE, EASYOCR, engines=engines)
    assert result.ocr_available is False
    assert engines[TESSERACT].asked == 0


def test_a_box_with_no_engine_installed_degrades_through_the_default_registry():
    """Machine-agnostic: written to be skipped, not to be assumed either way."""
    if selection.select_engine() is not None:
        pytest.skip("this box has an engine installed, so its default registry can read")
    result = run_tier1(PAGE)
    assert result.ocr_available is False
    assert result.ocr is NO_WORDS


# --- an available engine reads exactly as it always did ---


def test_an_available_engine_is_handed_the_frame_it_was_given():
    engines = registry((TESSERACT, True, READ))
    run_tier1(PAGE, engines=engines)
    assert engines[TESSERACT].reads == [PAGE]


def test_an_available_engine_reports_ocr_available():
    engines = registry((TESSERACT, True, READ))
    assert run_tier1(PAGE, engines=engines).ocr_available is True


def test_the_read_is_carried_exactly_as_the_engine_reported_it():
    """No re-reading of the words, and no second mean beside the engine's."""
    engines = registry((TESSERACT, True, READ))
    assert run_tier1(PAGE, engines=engines).ocr is READ


def test_a_preference_naming_no_engine_still_answers_the_engine_held():
    engines = registry((TESSERACT, True, READ), (EASYOCR, False))
    assert run_tier1(PAGE, TESSERACT, engines=engines).ocr is READ


def test_a_blank_page_read_by_an_available_engine_is_not_ocr_unavailable():
    """The mirror of the degrade: the same empty read, and a different answer.

    Without this the availability flag would be unpinned -- a runner that
    reported it from the words would pass every test above.
    """
    engines = registry((TESSERACT, True))
    result = run_tier1(PAGE, engines=engines)
    assert result.ocr is NO_WORDS
    assert result.ocr_available is True


# --- what stays loud: a fault is not an absence ---


def test_a_read_that_faults_is_not_swallowed_into_the_degrade():
    """A broken install must not read to a caller as a page with no words."""
    engines = {TESSERACT: FaultingRead(True)}
    with pytest.raises(RuntimeError):
        run_tier1(PAGE, engines=engines)


def test_a_probe_that_faults_is_not_swallowed_either():
    engines = {TESSERACT: FaultingProbe(True)}
    with pytest.raises(RuntimeError):
        run_tier1(PAGE, engines=engines)


def test_a_preference_naming_no_engine_is_still_refused_and_not_degraded():
    """12.5's refusal stays a refusal: degrading it would hide a wiring mistake."""
    engines = registry((TESSERACT, True, READ))
    with pytest.raises(selection.UnknownEngineError):
        run_tier1(PAGE, "paddleocr", engines=engines)


# --- the seam's own shape ---


def test_the_runner_holds_no_handler_and_no_clock():
    """The degrade is a branch on a value, not a catch around a read (D86)."""
    tree = ast.parse(pathlib.Path(runner.__file__).read_text(encoding="utf-8"))
    assert [node for node in ast.walk(tree) if isinstance(node, ast.Try)] == []
    read_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert read_modules & {"datetime", "time"} == set()


def test_every_name_in_all_exists_in_the_module():
    for name in runner.__all__:
        assert hasattr(runner, name)


def test_the_result_holds_the_read_the_availability_and_nothing_else():
    """No reason, no cause, no clock: one absence is one state (D85, D108)."""
    assert tuple(f.name for f in dataclasses.fields(Tier1Result)) == (
        "ocr",
        "ocr_available",
        "flags",
    )


def test_the_result_is_frozen_and_carries_no_public_method():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Tier1Result(ocr=NO_WORDS, ocr_available=False).ocr_available = True
    assert [
        name
        for name in dir(Tier1Result)
        if not name.startswith("_") and callable(getattr(Tier1Result, name))
    ] == []


def test_the_signature_is_an_image_a_preference_and_a_registry():
    assert tuple(inspect.signature(run_tier1).parameters) == (
        "image",
        "preference",
        "engines",
    )


def test_the_registry_is_keyword_only_and_nothing_takes_a_varargs():
    kinds = {p.kind for p in inspect.signature(run_tier1).parameters.values()}
    assert inspect.Parameter.KEYWORD_ONLY in kinds
    assert inspect.Parameter.VAR_POSITIONAL not in kinds
    assert inspect.Parameter.VAR_KEYWORD not in kinds


def test_the_return_annotation_names_a_tier1_result():
    assert inspect.signature(run_tier1).return_annotation is Tier1Result
