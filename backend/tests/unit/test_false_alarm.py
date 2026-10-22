"""12.10 -- the anti-false-alarm test the abstract's 4.1 sentence is about.

Section 4.1 says that where OCR confidence is low the field "is re-read or a
fallback engine is used before any flag is raised, so that a misread character
is not reported as a forgery", and section 8 lists low-confidence OCR being
re-read before flagging as this project's answer to false alarms on genuine
travellers.  **The page in this file is never altered.**  Every wrong reading
here is a misread of clean ink, which is the whole of the claim: a misread
field and an altered one look identical to whatever compares them, and only one
of them is a forgery.

**The engine below answers by the shape of the frame it is handed, not by how
many times it was asked.**  A stub answering by call count would let a gate
that skipped the crop, re-read the whole page and copied the misread through
pass every test in this file; answering by shape means the misread survives
unless the gate really cropped, really enlarged and really re-thresholded.

**"No flag" is asserted as two things this layer can be shown to be true of,
because 12.15 has not been written.**  The gate owes nothing when its verdict
is false and the value it keeps is what the page printed -- so neither id
:mod:`app.risk.flag_ids` holds for a Tier 1 read (:data:`OCR_MRZ_MISMATCH`,
:data:`OCR_LOW_CONFIDENCE`) has anything to fire on -- and the module is shown
structurally to hold no finding vocabulary at all.  A test that counted flags
would have to wait for 12.15, and would then be asserting about a comparator
rather than about the re-read that is what stops the false alarm.
"""

import ast
import pathlib

import pytest

from app.pipeline.tier0 import td3
from app.pipeline.tier1 import ocr, reread
from app.risk import flag_ids
from tests.fixtures import document_images, mrz_images

PAGE = document_images.render_document()
DOB = document_images.field_of(PAGE, "date_of_birth")

CONFIDENT = 0.96
UNSURE = 0.31

#: One plausible misread per printed field: ``G`` read as ``C``, ``0`` as
#: ``O``, ``1`` as ``I``.  Each differs from the truth by exactly one glyph,
#: which is what a real engine does and what makes the correction worth
#: testing -- a read that came back as noise would fail every rule at once and
#: would not be the near miss 4.1 is about.
MISREADS = {
    "name": "ERIKSSON ANNA MAR1A",
    "passport_number": "L8989O2C",
    "date_of_birth": "12 AUC 1974",
    "date_of_expiry": "15 APR 20I2",
}

MONTHS = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)


def read_of(text, confidence):
    """One word read at ``confidence``, as an engine would report it."""
    return ocr.OcrResult(
        words=(ocr.OcrWord(text=text, bbox=(0, 0, 10, 10), confidence=confidence),),
        mean_confidence=confidence,
    )


def crop_shape(box):
    """The frame ``box`` becomes once 12.8 has enlarged it."""
    left, top, right, bottom = box
    return ((bottom - top) * reread.OCR_UPSCALE, (right - left) * reread.OCR_UPSCALE)


class MisreadingEngine(ocr.OcrEngine):
    """An engine that misreads a field off the page and reads it off the crop.

    The document is never altered underneath it, so every wrong answer here is
    a misread of ink that is exactly as printed.  ``read`` decides by the
    frame's own size: the whole page is too small a share of the glyph for this
    engine, and the enlarged re-thresholded crop carries enough of it.
    """

    def __init__(self, truth, misread, crop_shape):
        self.truth = truth
        self.misread = misread
        self.crop_shape = crop_shape
        self.seen = []

    def read(self, image):
        self.seen.append(image.shape)
        if tuple(image.shape[:2]) == self.crop_shape:
            return read_of(self.truth, CONFIDENT)
        return read_of(self.misread, UNSURE)


def misreading(field_name):
    """An engine that misreads ``field_name`` off the page and reads it cropped."""
    field = document_images.field_of(PAGE, field_name)
    return MisreadingEngine(
        truth=field.value,
        misread=MISREADS[field_name],
        crop_shape=crop_shape(field.value_box),
    )


def gate(field_name, engine=None):
    """What the gate does with one misread field of the clean page."""
    field = document_images.field_of(PAGE, field_name)
    engine = misreading(field_name) if engine is None else engine
    page_read = engine.read(PAGE.image)
    return reread.gate_field(PAGE.image, field.value_box, page_read, engine)


# --- the claim 4.1 makes ---


def test_a_field_that_was_only_misread_is_re_read_correctly_and_owes_no_finding():
    field = gate("date_of_birth")
    assert [word.text for word in field.ocr.words] == [DOB.value]
    assert field.low_confidence is False


def test_the_misread_never_reaches_the_record_tier1_keeps():
    """A gate that kept the page read and appended the re-read would fail this."""
    field = gate("date_of_birth")
    assert MISREADS["date_of_birth"] not in [word.text for word in field.ocr.words]


def test_it_was_the_re_read_that_corrected_it_and_only_one_was_taken():
    engine = misreading("date_of_birth")
    field = gate("date_of_birth", engine)
    assert field.steps == (reread.RE_READ,)
    assert len(engine.seen) == 2


def test_the_re_read_was_of_the_fields_own_printed_box():
    """So that whatever is eventually pointed at is where the field was printed."""
    engine = misreading("date_of_birth")
    gate("date_of_birth", engine)
    assert tuple(engine.seen[1][:2]) == crop_shape(DOB.value_box)


def test_a_field_read_correctly_the_first_time_is_left_alone():
    """The mirror: a gate that re-read everything would owe nobody a misread."""
    field = document_images.field_of(PAGE, "date_of_birth")
    engine = misreading("date_of_birth")
    confident = read_of(field.value, CONFIDENT)
    gated = reread.gate_field(PAGE.image, field.value_box, confident, engine)
    assert gated.ocr is confident
    assert gated.steps == ()
    assert engine.seen == []


@pytest.mark.parametrize("field_name", sorted(MISREADS))
def test_no_field_of_a_clean_page_is_owed_a_finding_once_it_is_re_read(field_name):
    """The claim is about the page, not about the one field that happened to fail."""
    field = gate(field_name)
    printed = document_images.field_of(PAGE, field_name).value
    assert [word.text for word in field.ocr.words] == [printed]
    assert field.low_confidence is False


# --- what the gate prevented, and what it is forbidden from becoming ---


def test_the_page_read_believed_would_have_owed_the_low_confidence_finding():
    """The counterfactual that makes the tests above worth running."""
    page_read = misreading("date_of_birth").read(PAGE.image)
    assert page_read.mean_confidence < reread.OCR_CONFIDENCE_THRESHOLD
    assert flag_ids.OCR_LOW_CONFIDENCE in flag_ids.FLAG_IDS


def test_neither_tier_1_finding_has_anything_to_fire_on_for_a_resolved_field():
    """A comparison of the kept read against the MRZ finds nothing to disagree."""
    field = gate("date_of_birth")
    assert field.low_confidence is False
    assert field.ocr.words[0].text == DOB.value
    assert flag_ids.OCR_MRZ_MISMATCH in flag_ids.FLAG_IDS


def test_this_layer_holds_no_finding_vocabulary_and_so_cannot_raise_one():
    tree = ast.parse(pathlib.Path(reread.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "risk" not in imported
    built = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "EvidenceFlag"
    ]
    assert built == []


def test_the_page_was_never_altered_and_agrees_with_its_own_machine_readable_zone():
    """What makes the reads above misreads: the printed day is the MRZ's day.

    The MRZ carries ``YYMMDD`` and the page prints ``DD MON YYYY``, so the two
    are the same day stated twice -- and this test reads both out of the
    fixtures rather than asserting the constant, so a specimen that moved would
    fail here instead of quietly agreeing with itself.
    """
    day, month, year = DOB.value[:2], DOB.value[3:6], DOB.value[7:]
    assert month in MONTHS
    assert td3.parse_date_of_birth(mrz_images.SPECIMENS["TD3"][1]) == (
        year[2:] + f"{MONTHS.index(month) + 1:02d}" + day
    )
