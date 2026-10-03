"""Tesseract behind the OCR seam: a word-level read, or an honest absence.

Two things must be present before a read can run -- the ``pytesseract`` binding
and the ``tesseract`` binary -- and either one being missing is answered
through :meth:`TesseractEngine.is_available`, never raised.  The binding is
imported on first use rather than at module scope, so importing this module on
a box that has neither costs nothing and fails nothing.
"""

import shutil
from functools import lru_cache

import numpy

from app.pipeline.tier1.ocr import NO_WORDS, OcrEngine, OcrResult, OcrWord

__all__ = ["IMPORT", "TESSERACT_BINARY", "TESSERACT_CONFIG", "TESSERACT_LANGUAGE", "TesseractEngine"]

#: Constructor default meaning "import pytesseract when asked". Passing
#: ``binding=None`` instead says the binding is definitely absent, which is a
#: different answer and the one a test needs to be the same on every machine.
IMPORT = object()

#: The executable a read shells out to, and how it is asked to read the page:
#: 3 is "fully automatic" segmentation, spelled out rather than inherited so a
#: change to pytesseract's own default cannot silently move our boxes.
TESSERACT_BINARY = "tesseract"
TESSERACT_CONFIG = "--psm 3"
TESSERACT_LANGUAGE = "eng"

#: pytesseract reports its output as one row per block, paragraph, line and
#: word, and marks the first three with this score. A word is scored out of
#: :data:`_SCORE_SCALE`; ours is scored out of 1.
_BLOCK_ROW_SCORE = -1.0
_SCORE_SCALE = 100.0


@lru_cache(maxsize=1)
def _import_pytesseract():
    """Return the ``pytesseract`` module, or ``None`` where it is not installed.

    The absence is cached as firmly as the presence: a box without the binding
    asks once per process rather than once per document.
    """
    try:
        import pytesseract
    except ImportError:
        return None
    return pytesseract


def _as_rgb(image):
    """Hand pytesseract the frame in the channel order it reads.

    Tier 0 works in BGR and pytesseract builds a PIL image, which reads the
    array as RGB, so a frame passed on as it stands swaps two channels.
    """
    return numpy.ascontiguousarray(image[:, :, ::-1])


def _as_confidence(raw):
    """Tesseract's ``0..100`` score as this project's ``0.0..1.0``, or ``None``.

    ``None`` means the row is not a word: pytesseract scores its block,
    paragraph and line rows at -1, and a score that is not a number at all is
    not a word's confidence either.
    """
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return None
    if score <= _BLOCK_ROW_SCORE:
        return None
    return min(score / _SCORE_SCALE, 1.0)


def _words_from(data):
    """Every word row of pytesseract's dict output, in the order it reported."""
    for index, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        confidence = _as_confidence(data["conf"][index])
        if not text or confidence is None:
            continue
        left = int(data["left"][index])
        top = int(data["top"][index])
        yield OcrWord(
            text=text,
            bbox=(left, top, left + int(data["width"][index]), top + int(data["height"][index])),
            confidence=confidence,
        )


def _result(words):
    """One read of ``words``, carrying the mean confidence 12.9's gate reads."""
    if not words:
        return NO_WORDS
    mean = sum(word.confidence for word in words) / len(words)
    return OcrResult(words=tuple(words), mean_confidence=mean)


class TesseractEngine(OcrEngine):
    """Tesseract's word-level read, reported absent rather than raised.

    ``locate`` answers where the binary is -- ``None`` when it is not installed
    -- and ``binding`` stands in for an already-imported ``pytesseract``. Both
    are injected so a test can answer either way on a machine with neither.
    """

    def __init__(self, *, locate=None, binding=IMPORT):
        self._locate = shutil.which if locate is None else locate
        self._binding = binding

    def _pytesseract(self):
        """The binding to read through: the one handed in, or pytesseract."""
        if self._binding is not IMPORT:
            return self._binding
        return _import_pytesseract()

    def is_available(self) -> bool:
        """Whether a read could run: the binding imports and the binary is found.

        Every state answers a bool, both missing included, so 12.5's selector
        can ask the question without a handler wrapped around asking it.
        """
        if self._pytesseract() is None:
            return False
        return self._locate(TESSERACT_BINARY) is not None

    def read(self, image) -> OcrResult:
        """Return every word ``image`` carries, or the empty read when absent.

        A missing Tesseract is not an error here: the read degrades to
        :data:`~app.pipeline.tier1.ocr.NO_WORDS`, which is the result 12.6
        asserts keeps a screening alive instead of failing the document.
        """
        binding = self._pytesseract()
        if binding is None or self._locate(TESSERACT_BINARY) is None:
            return NO_WORDS
        data = binding.image_to_data(
            _as_rgb(image),
            lang=TESSERACT_LANGUAGE,
            config=TESSERACT_CONFIG,
            output_type=binding.Output.DICT,
        )
        return _result(tuple(_words_from(data)))