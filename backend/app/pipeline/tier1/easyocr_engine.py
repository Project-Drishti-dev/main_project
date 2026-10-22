"""EasyOCR behind the OCR seam: a word-level read, or an honest absence.

EasyOCR is one thing rather than two -- a Python package, not a package plus
an executable it shells out to -- so :meth:`EasyOcrEngine.is_available` asks one
question and answers a bool for every state.  The package is imported on first
use rather than at module scope, so importing this module on a box that has
never installed it costs nothing and fails nothing.
"""

from functools import lru_cache

import numpy

from app.pipeline.tier1.ocr import NO_WORDS, OcrEngine, OcrResult, OcrWord

__all__ = [
    "EASYOCR_DETAIL",
    "EASYOCR_LANGUAGES",
    "EASYOCR_OUTPUT_FORMAT",
    "EASYOCR_PARAGRAPH",
    "IMPORT",
    "EasyOcrEngine",
]

#: Constructor default meaning "import easyocr when asked".  Passing
#: ``binding=None`` instead says the package is definitely absent, which is a
#: different answer and the one a test needs to be the same on every machine.
IMPORT = object()

#: The languages a reader is built for, and the three reading options that
#: decide the shape of what comes back.  ``EASYOCR_DETAIL`` keeps the boxes and
#: confidences an ``OcrWord`` is made of, ``EASYOCR_PARAGRAPH`` off keeps one
#: row per detected box rather than one per paragraph of them, and
#: ``EASYOCR_OUTPUT_FORMAT`` pins the row layout to ``[box, text, confidence]``
#: rather than inheriting whatever EasyOCR's own default happens to be.
EASYOCR_LANGUAGES = ["en"]
EASYOCR_DETAIL = 1
EASYOCR_PARAGRAPH = False
EASYOCR_OUTPUT_FORMAT = "standard"


@lru_cache(maxsize=1)
def _import_easyocr():
    """Return the ``easyocr`` module, or ``None`` where it is not installed.

    The absence is cached as firmly as the presence: a box without the package
    asks once per process rather than once per document.
    """
    try:
        import easyocr
    except ImportError:
        return None
    return easyocr


def _as_confidence(raw):
    """EasyOCR's own score as this project's ``0.0..1.0``, or ``None``.

    EasyOCR already scores on our scale, so there is no block-row marker to
    recognise here; a score that is not a number at all is the only thing it
    cannot read, and a score outside the range is clamped rather than kept,
    because a confidence above one would lift 12.9's gate on a page it was
    unsure about.
    """
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return None
    return min(max(score, 0.0), 1.0)


def _as_bbox(quad):
    """EasyOCR's four-point box as ``(left, top, right, bottom)``.

    EasyOCR reports the corners of a quadrilateral rather than an origin and a
    size, and does not order those corners, so a box is read as the extent of
    its points rather than as the first two of them.
    """
    xs = [point[0] for point in quad]
    ys = [point[1] for point in quad]
    return (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))


def _words_from(rows):
    """Every word row of EasyOCR's output, in the order it reported them."""
    for quad, raw_text, raw_confidence in rows:
        text = raw_text.strip()
        confidence = _as_confidence(raw_confidence)
        if not text or confidence is None:
            continue
        yield OcrWord(text=text, bbox=_as_bbox(quad), confidence=confidence)


def _result(words):
    """One read of ``words``, carrying the mean confidence 12.9's gate reads."""
    if not words:
        return NO_WORDS
    mean = sum(word.confidence for word in words) / len(words)
    return OcrResult(words=tuple(words), mean_confidence=mean)


class EasyOcrEngine(OcrEngine):
    """EasyOCR's word-level read, reported absent rather than raised.

    ``binding`` stands in for an already-imported ``easyocr``, so a test can
    answer either way on a machine that has neither.  The reader built from it
    is held on the instance, because it carries the loaded models and building
    one per document would re-load them per document.
    """

    def __init__(self, *, binding=IMPORT):
        self._binding = binding
        self._reader = None

    def _easyocr(self):
        """The package to read through: the one handed in, or easyocr."""
        if self._binding is not IMPORT:
            return self._binding
        return _import_easyocr()

    def _reader_for(self, binding):
        """The reader to read through, built once and then kept."""
        if self._reader is None:
            self._reader = binding.Reader(lang_list=EASYOCR_LANGUAGES)
        return self._reader

    def is_available(self) -> bool:
        """Whether a read could run: the ``easyocr`` package imports.

        One question, because EasyOCR is a package and not a package plus an
        executable: there is no second half whose absence could be reported
        separately, and so no way for this answer to be half-true.
        """
        return self._easyocr() is not None

    def read(self, image) -> OcrResult:
        """Return every word ``image`` carries, or the empty read when absent.

        A missing EasyOCR is not an error here: the read degrades to
        :data:`~app.pipeline.tier1.ocr.NO_WORDS`, which is the result 12.6
        asserts keeps a screening alive instead of failing the document.

        Tier 0's frame is handed over in the order it arrives.  EasyOCR reads a
        three-channel array as BGR, which is the order Tier 0 already works
        in, so the reversal 12.3 performs for pytesseract is deliberately not
        performed here: it would swap the two channels EasyOCR greys and
        normalises, and every box and confidence would still look plausible.
        """
        binding = self._easyocr()
        if binding is None:
            return NO_WORDS
        reader = self._reader_for(binding)
        rows = reader.readtext(
            numpy.array(image, order="C", copy=True),
            detail=EASYOCR_DETAIL,
            paragraph=EASYOCR_PARAGRAPH,
            output_format=EASYOCR_OUTPUT_FORMAT,
        )
        return _result(tuple(_words_from(rows)))
