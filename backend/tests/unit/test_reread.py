"""12.8 and 12.9 -- the crop that reads a field again, and the gate that asks for it.

Two claims, and they are told apart here.  **12.8 is about the frame**: a field
is cropped to its own box, blown up, re-thresholded, and read on its own.
**12.9 is about the decision**: a field read below
:data:`~app.pipeline.tier1.reread.OCR_CONFIDENCE_THRESHOLD` is re-read once,
then handed to a fallback engine, and only then reported as unsure.

The page is 12.7's and the boxes are its ground truth, so the region each of
these tests crops to is a box the fixture measured off the ink it printed and
not a rectangle a test typed in.  Neither engine here is real: 12.3 to 12.6 are
all answered by injected bindings, and a stub answering by the shape it was
handed is what lets these tests mean the same thing on a box with Tesseract
installed and on one without.
"""

import ast
import dataclasses
import inspect
import pathlib

import cv2
import numpy as np
import pytest

from app.pipeline.tier1 import ocr, reread
from tests.fixtures import document_images

NO_WORDS = ocr.NO_WORDS
re_read_field = reread.re_read_field
gate_field = reread.gate_field
OCR_UPSCALE = reread.OCR_UPSCALE
THRESHOLD = reread.OCR_CONFIDENCE_THRESHOLD

#: 12.7's page and one field of it, addressed by name as D87 makes a field be
#: addressed everywhere in this part.
PAGE = document_images.render_document()
DOB = document_images.field_of(PAGE, "date_of_birth")

MISREAD = "12 AUC 1974"
CONFIDENT = 0.96
UNSURE = 0.31


def read_of(text, confidence):
    """One word read at ``confidence``, as an engine would report it."""
    return ocr.OcrResult(
        words=(ocr.OcrWord(text=text, bbox=(0, 0, 10, 10), confidence=confidence),),
        mean_confidence=confidence,
    )


class RecordingEngine(ocr.OcrEngine):
    """An engine answering with whatever it was told, keeping every frame.

    The last result answers every read past the end of the list, so a test
    that expects one read and gets two sees the second rather than an
    ``IndexError`` that says nothing about which of the two is wrong.
    """

    def __init__(self, *results, available=True):
        self.results = list(results) or [NO_WORDS]
        self.available = available
        self.seen = []

    def is_available(self):
        return self.available

    def read(self, image):
        self.seen.append(image)
        return self.results[min(len(self.seen) - 1, len(self.results) - 1)]


class FaultingEngine(RecordingEngine):
    """An engine whose read faults: a broken install, not an absence."""

    def read(self, image):
        self.seen.append(image)
        raise RuntimeError("the reader cannot be built")


def crop_shape(box):
    """The frame ``box`` becomes: its size blown up by the module's factor."""
    left, top, right, bottom = box
    return ((bottom - top) * OCR_UPSCALE, (right - left) * OCR_UPSCALE)


# --- 12.8: the crop ---


def test_the_engine_is_handed_the_fields_own_box_enlarged():
    engine = RecordingEngine()
    re_read_field(PAGE.image, DOB.value_box, engine)
    height, width = crop_shape(DOB.value_box)
    assert engine.seen[0].shape == (height, width, 3)


def test_the_enlargement_is_the_modules_own_factor_and_not_a_caller_argument():
    """A per-call scale would make two fields read at two different sizes."""
    assert tuple(inspect.signature(re_read_field).parameters) == (
        "image",
        "region",
        "engine",
    )
    assert OCR_UPSCALE == 3


def test_the_crop_is_the_value_and_not_the_label_beside_it():
    """A union box would answer with the anchor word as well (D87)."""
    union = (DOB.label_box[0], DOB.label_box[1], DOB.value_box[2], DOB.value_box[3])
    value_engine, union_engine = RecordingEngine(), RecordingEngine()
    re_read_field(PAGE.image, DOB.value_box, value_engine)
    re_read_field(PAGE.image, union, union_engine)
    assert DOB.label_box[2] <= DOB.value_box[0]
    assert union_engine.seen[0].shape[1] > value_engine.seen[0].shape[1]


def test_the_crop_is_re_thresholded_and_not_only_enlarged():
    """Two levels in, because a cut was read off this crop's own histogram."""
    engine = RecordingEngine()
    re_read_field(PAGE.image, DOB.value_box, engine)
    assert set(np.unique(engine.seen[0]).tolist()).issubset({0, 255})


def test_thresholding_is_what_reduces_the_frame_and_not_the_page_being_binary():
    """Without this, a stub answering every frame with two levels would pass."""
    left, top, right, bottom = DOB.value_box
    assert len(np.unique(PAGE.image[top:bottom, left:right])) > 2


def test_the_engines_own_read_is_handed_back_untouched():
    """The module prepares a frame; it does not read, score or second-guess."""
    answer = read_of(DOB.value, CONFIDENT)
    assert re_read_field(PAGE.image, DOB.value_box, RecordingEngine(answer)) is answer


@pytest.mark.parametrize(
    "region",
    [
        None,
        "abcd",
        [10, 20, 30, 40],
        (10, 20, 30),
        (10, 20, 30, 40, 50),
        (10, 20, 10, 40),
        (10, 40, 30, 20),
        (-1, 20, 30, 40),
        (10, -1, 30, 40),
        (0, 0, PAGE.size[0] + 1, 40),
        (0, 0, 40, PAGE.size[1] + 1),
        (10.5, 20, 30, 40),
        (True, 20, 30, 40),
    ],
)
def test_a_region_that_is_not_four_whole_pixels_inside_the_frame_is_refused(region):
    """An empty crop answers no words, which reads as a field that is absent."""
    engine = RecordingEngine()
    with pytest.raises(ValueError):
        re_read_field(PAGE.image, region, engine)
    assert engine.seen == []


def test_a_frame_that_is_not_three_channels_is_refused():
    """12.2's seam states BGR, so this is its answer and not OpenCV's."""
    grey = cv2.cvtColor(PAGE.image, cv2.COLOR_BGR2GRAY)
    engine = RecordingEngine()
    with pytest.raises(ValueError):
        re_read_field(grey, DOB.value_box, engine)
    assert engine.seen == []


def test_a_frame_that_is_not_an_image_at_all_is_refused():
    with pytest.raises(ValueError):
        re_read_field(object(), DOB.value_box, RecordingEngine())


def test_a_numpy_pixel_is_a_pixel_and_not_a_refusal():
    """A box measured off the frame is numpy ints, and 12.7 hands those over."""
    left, top, right, bottom = (np.int32(side) for side in DOB.value_box)
    engine = RecordingEngine()
    re_read_field(PAGE.image, (left, top, right, bottom), engine)
    assert engine.seen[0].shape[:2] == crop_shape(DOB.value_box)


# --- 12.9: the gate ---


def test_a_field_read_confidently_is_kept_and_no_engine_is_asked_again():
    engine = RecordingEngine()
    confident = read_of(DOB.value, CONFIDENT)
    field = gate_field(PAGE.image, DOB.value_box, confident, engine)
    assert field.ocr is confident
    assert field.low_confidence is False
    assert field.steps == ()
    assert engine.seen == []


def test_a_read_landing_exactly_on_the_threshold_is_believed():
    """The gate compares ``>=``, so the threshold itself is not a re-read."""
    engine = RecordingEngine()
    at_threshold = read_of(DOB.value, THRESHOLD)
    assert gate_field(PAGE.image, DOB.value_box, at_threshold, engine).steps == ()
    assert engine.seen == []


def test_a_field_read_unsurely_is_re_read_once():
    """The page read is handed in, so the engine's only read here is the re-read."""
    engine = RecordingEngine(read_of(DOB.value, CONFIDENT))
    field = gate_field(PAGE.image, DOB.value_box, read_of(MISREAD, UNSURE), engine)
    assert field.steps == (reread.RE_READ,)
    assert len(engine.seen) == 1
    assert field.ocr.words[0].text == DOB.value
    assert field.low_confidence is False


def test_the_fallback_is_asked_only_after_the_re_read_was_still_unsure():
    engine = RecordingEngine(read_of(MISREAD, UNSURE), read_of(MISREAD, UNSURE))
    fallback = RecordingEngine(read_of(DOB.value, CONFIDENT))
    field = gate_field(
        PAGE.image, DOB.value_box, read_of(MISREAD, UNSURE),
        engine, fallback=fallback,
    )
    assert field.steps == (reread.RE_READ, reread.FALLBACK)
    assert fallback.seen


def test_the_fallback_reads_the_same_crop_the_re_read_did():
    """Handing it the whole page would undo the enlargement it was asked for."""
    engine = RecordingEngine(read_of(MISREAD, UNSURE), read_of(MISREAD, UNSURE))
    fallback = RecordingEngine(read_of(DOB.value, CONFIDENT))
    gate_field(
        PAGE.image, DOB.value_box, read_of(MISREAD, UNSURE),
        engine, fallback=fallback,
    )
    assert engine.seen[0].shape == fallback.seen[0].shape


def test_a_field_still_unsure_after_both_is_reported_unsure():
    engine = RecordingEngine(read_of(MISREAD, UNSURE), read_of(MISREAD, UNSURE))
    fallback = RecordingEngine(read_of(MISREAD, UNSURE))
    field = gate_field(
        PAGE.image, DOB.value_box, read_of(MISREAD, UNSURE),
        engine, fallback=fallback,
    )
    assert field.low_confidence is True
    assert field.steps == reread.GATE_STEPS


def test_no_fallback_means_no_fallback_step_and_the_reread_is_the_last_word():
    engine = RecordingEngine(read_of(MISREAD, UNSURE), read_of(MISREAD, UNSURE))
    field = gate_field(PAGE.image, DOB.value_box, read_of(MISREAD, UNSURE), engine)
    assert field.steps == (reread.RE_READ,)
    assert field.low_confidence is True
    assert reread.FALLBACK not in field.steps


def test_the_fallback_is_keyword_only_so_it_cannot_land_where_the_engine_belongs():
    kinds = {p.kind for p in inspect.signature(gate_field).parameters.values()}
    assert inspect.Parameter.KEYWORD_ONLY in kinds
    assert inspect.Parameter.VAR_POSITIONAL not in kinds
    assert inspect.Parameter.VAR_KEYWORD not in kinds


def test_a_read_that_is_not_an_ocr_result_is_refused():
    with pytest.raises(ValueError):
        gate_field(PAGE.image, DOB.value_box, object(), RecordingEngine())


# --- what stays loud, and what the module may not become ---


def test_a_read_that_faults_is_not_swallowed_into_a_field_nobody_could_read():
    """A broken install is not an absence, on 12.6's reasoning."""
    with pytest.raises(RuntimeError):
        gate_field(PAGE.image, DOB.value_box, read_of("x", UNSURE), FaultingEngine())


def test_the_gate_is_a_branch_on_a_confidence_and_not_a_catch_around_a_read():
    tree = ast.parse(pathlib.Path(reread.__file__).read_text(encoding="utf-8"))
    assert [node for node in ast.walk(tree) if isinstance(node, ast.Try)] == []


def test_the_gate_writes_no_log_line_and_so_no_ocr_text_can_reach_one():
    tree = ast.parse(pathlib.Path(reread.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported & {"logging", "print"} == set()


def test_the_record_holds_the_read_the_verdict_and_the_steps_and_nothing_else():
    assert tuple(f.name for f in dataclasses.fields(reread.FieldRead)) == (
        "ocr",
        "low_confidence",
        "steps",
    )


def test_the_record_is_frozen_and_carries_no_public_method():
    with pytest.raises(dataclasses.FrozenInstanceError):
        reread.FieldRead(ocr=NO_WORDS, low_confidence=False, steps=()).steps = ()
    assert [
        name
        for name in dir(reread.FieldRead)
        if not name.startswith("_") and callable(getattr(reread.FieldRead, name))
    ] == []


def test_every_name_in_all_exists_in_the_module():
    for name in reread.__all__:
        assert hasattr(reread, name)
