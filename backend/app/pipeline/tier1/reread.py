"""Reading one printed field a second time: the crop, and the gate that asks for it.

A printed field is small, and an engine reading a whole page spends one pixel
budget across every field on it.  :func:`re_read_field` is 12.8's answer to
that: crop to the one box the field was printed in, blow that crop up,
re-threshold it, and read only that.  :func:`gate_field` is 12.9's answer to
what to do when the first read came back unsure, and it is the one place in
Tier 1 where a second engine is tried on purpose — 12.5's rule that a
preference is never substituted holds for *choosing* a read, not for repairing
one.

**Both extra reads happen before anything is reported, and that ordering is
the claim the abstract makes.**  Section 4.1 says a field whose OCR confidence
is low "is re-read or a fallback engine is used before any flag is raised, so
that a misread character is not reported as a forgery", and section 8 lists
low-confidence OCR being re-read before flagging as this project's answer to
false alarms on genuine travellers.  :attr:`FieldRead.low_confidence` is the
only thing down this line that owes anyone a finding, so a field the gate
resolved reports false and owes nothing.

**This module holds no finding vocabulary at all.**  It does not import
:mod:`app.risk` and it builds no flag, because what a page means is 12.11 to
12.16's question and not a crop's.  12.10 is what pins that: a clean page
whose field was merely misread resolves here and produces no finding, and a
test asserts this module never gains the means to produce one.

**The threshold is a stated default and not a measured figure.**  The abstract
names no number, says thresholds are chosen against a target false-alert rate
and versioned so every policy change is recorded, and claims no accuracy
figures.  :data:`OCR_CONFIDENCE_THRESHOLD` is this project's starting value
and Part 27 is what earns a better one.
"""

import dataclasses
import numbers

import cv2

from app.pipeline.tier1.ocr import OcrResult

__all__ = [
    "FALLBACK",
    "FieldRead",
    "GATE_STEPS",
    "OCR_CONFIDENCE_THRESHOLD",
    "OCR_UPSCALE",
    "RE_READ",
    "gate_field",
    "re_read_field",
]

#: The two extra reads the gate may take, and the only two: the field's crop
#: re-read by the engine that read the page, then that same crop read by a
#: fallback engine.  Named constants rather than strings at the call sites, so
#: :attr:`FieldRead.steps` is a closed vocabulary a caller matches on without
#: depending on what this module happens to spell them as today.
RE_READ = "re_read"
FALLBACK = "fallback"
GATE_STEPS = (RE_READ, FALLBACK)

#: The factor a field's box is blown up by on both axes before it is read
#: again.  The page 12.7 prints carries its values at scale 1.0, so a value box
#: is tens of pixels tall and a whole-page read has little of a glyph to work
#: with; 3x puts one back in the range both engines are built for.  A module
#: constant and not a caller argument, on 12.2's reason that a read carries no
#: engine-specific option.
OCR_UPSCALE = 3

#: The mean confidence at or above which a field is believed without a second
#: look.  Written down here rather than left to each engine's own cutoff,
#: because 4.1's promise is that *this project* re-reads a low-confidence
#: field rather than reporting it, and an engine's default would make that a
#: silent decision taken twice and differently.
OCR_CONFIDENCE_THRESHOLD = 0.80


@dataclasses.dataclass(frozen=True)
class FieldRead:
    """One field's read after the gate has had its say about it.

    ``ocr`` is the read Tier 1 keeps: the first one the gate believed, or the
    last one taken when it believed none.  **Its words carry boxes in the frame
    they were read from**, so a box from a re-read is a box in the crop and not
    on the page; 12.14 reports the field's own region rather than this one, and
    that is why the two cannot be confused for one another.

    ``low_confidence`` is the gate's verdict and the only thing here that owes
    anyone a finding: ``False`` means 4.1's promise was kept for this field and
    nothing is owed.  ``steps`` names the extra reads that were taken, drawn
    from :data:`GATE_STEPS`, so a caller can see what the gate did without the
    gate writing a log line about it.

    Frozen, and carrying no public method, for the reason
    :class:`~app.risk.flags.EvidenceFlag` is: a second opinion about what was
    read would be a second answer, and the gate is the one thing here allowed
    to have one.
    """

    ocr: OcrResult
    low_confidence: bool
    steps: tuple[str, ...]


def _check_frame(image: object) -> None:
    """Refuse ``image`` unless it is a three-channel frame, as 12.2's seam states.

    Checked here rather than left to :func:`cv2.cvtColor`, so a caller handing
    a single-channel crop gets this module's one answer about what a frame is
    rather than an OpenCV error naming a conversion four lines below.
    """
    shape = getattr(image, "shape", None)
    if not isinstance(shape, tuple) or len(shape) != 3 or shape[2] != 3:
        raise ValueError("a frame must be a three-channel image, as 12.2's seam states")


def _check_region(region: object, shape: tuple) -> tuple[int, int, int, int]:
    """``region`` as four whole-pixel bounds inside a frame of ``shape``.

    The box is half-open on both axes, so it is ``(left, top, right, bottom)``
    exactly as a :class:`~tests.fixtures.document_images.PrintedField` carries
    it and exactly as :func:`cv2` slices an array.

    **A region that would slice to nothing is refused rather than read.**  An
    empty or inverted crop throws the field away and answers with no words,
    which a caller would read as a field that is genuinely absent -- and 4.1's
    promise is about misreads, not about one a bad box invented.
    """
    if not isinstance(region, tuple) or len(region) != 4:
        raise ValueError("region must be a (left, top, right, bottom) tuple")
    if not all(
        isinstance(side, numbers.Integral) and not isinstance(side, bool)
        for side in region
    ):
        raise ValueError("region must hold whole pixels")
    left, top, right, bottom = (int(side) for side in region)
    if right <= left or bottom <= top:
        raise ValueError("a region must enclose at least one pixel")
    height, width = shape[:2]
    if left < 0 or top < 0 or right > width or bottom > height:
        raise ValueError("region must lie inside the frame it crops")
    return left, top, right, bottom


def _prepared_crop(image, region: object):
    """The field's own box, blown up and re-thresholded, ready to be read.

    **Re-thresholded, and not merely enlarged**, because an upscaled crop is
    still a crop of whatever exposure the page was captured at, and a field
    that reads badly on a page often reads badly because of its contrast
    rather than its size.  Otsu is used rather than a fixed cut so the cut is
    read off this crop's own two levels and is not a second place a page's
    exposure is written down.

    **Handed back as three channels.**  :class:`~app.pipeline.tier1.ocr.OcrEngine`
    promises every frame it is handed is BGR, and EasyOCR is passed it
    untouched (``D84``), so a single-channel image leaving this module would
    break the one engine that cannot convert for itself.
    """
    left, top, right, bottom = _check_region(region, image.shape)
    crop = image[top:bottom, left:right]
    enlarged = cv2.resize(
        crop, None, fx=OCR_UPSCALE, fy=OCR_UPSCALE, interpolation=cv2.INTER_CUBIC
    )
    grey = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def re_read_field(image, region: object, engine):
    """Read ``region`` of ``image`` on its own, and answer what the engine read.

    :param image: the frame the field was printed on -- three-channel BGR, as
        12.2's seam states.
    :param region: the field's own box as ``(left, top, right, bottom)``, which
        is a :class:`~tests.fixtures.document_images.PrintedField`'s
        ``value_box`` and not its ``label_box``: a box over both would answer
        with the anchor word as well as the value (``D87``).
    :param engine: the engine to read the crop with, asked once.
    :returns: the engine's own :class:`~app.pipeline.tier1.ocr.OcrResult`,
        carried exactly as it reported it -- this function prepares a frame
        and does not read, score or second-guess the answer.
    :raises ValueError: if ``image`` is not a three-channel frame, or
        ``region`` is not four whole-pixel bounds inside it.
    """
    _check_frame(image)
    return engine.read(_prepared_crop(image, region))


def gate_field(image, region: object, read: OcrResult, engine, *, fallback=None):
    """Return the read Tier 1 keeps for one field, having re-read it if unsure.

    **The comparison is a branch and this module holds no handler**, on 12.6's
    reasoning: a read that faults is a broken install and stays loud rather
    than being answered as a field nobody could read.

    :param image: the frame the field was printed on, re-read against when the
        gate needs a second look.
    :param region: the field's own box, as :func:`re_read_field` takes it.
    :param read: what the page read already made of this field.
    :param engine: the engine that read the page, asked again on the crop.
    :param fallback: a second engine to try when the re-read is still unsure,
        or ``None`` for none.  It is read **the same crop the re-read was**,
        because handing a fallback the whole page would undo the enlargement
        it is being asked for.  Keyword-only, so a caller cannot pass one where
        the engine belongs.
    :returns: a :class:`FieldRead` holding the read to keep, whether the gate
        ended unsure, and which of :data:`GATE_STEPS` it took to get there.
    :raises ValueError: for anything :func:`re_read_field` refuses, and for a
        ``read`` that is not an :class:`~app.pipeline.tier1.ocr.OcrResult`.
    """
    if not isinstance(read, OcrResult):
        raise ValueError(f"read must be an OcrResult, not {type(read).__name__}")
    steps = ()
    kept = read
    if read.mean_confidence >= OCR_CONFIDENCE_THRESHOLD:
        return FieldRead(ocr=kept, low_confidence=False, steps=steps)

    steps += (RE_READ,)
    kept = re_read_field(image, region, engine)
    if kept.mean_confidence >= OCR_CONFIDENCE_THRESHOLD:
        return FieldRead(ocr=kept, low_confidence=False, steps=steps)

    if fallback is not None:
        steps += (FALLBACK,)
        kept = re_read_field(image, region, fallback)
    return FieldRead(
        ocr=kept,
        low_confidence=kept.mean_confidence < OCR_CONFIDENCE_THRESHOLD,
        steps=steps,
    )
