"""Tier 1's OCR seam: one way to read words off a page, and what a word is.

:class:`OcrWord` is one word an engine read -- its text, its box in the image
it was read from, and the engine's confidence.  :class:`OcrResult` is one
read of one page: its words and the mean of their confidences.

:class:`OcrEngine` is the seam those reads go through.  ``read`` takes one
frame and answers one :class:`OcrResult`, and carries no option: a crop for
12.8's re-read arrives as a frame of its own, so no caller can hand an engine
an argument only a different engine understands.
"""

import abc
import dataclasses

__all__ = ["NO_WORDS", "OcrEngine", "OcrResult", "OcrWord"]


@dataclasses.dataclass(frozen=True)
class OcrWord:
    """One word read off a page.

    ``bbox`` is ``(left, top, right, bottom)`` in pixels of the image
    ``text`` was read from, and ``confidence`` is the engine's own ``0.0``-
    ``1.0`` reading -- the number 12.9's gate compares, not a measure of
    whether the word is correct.
    """

    text: str
    bbox: tuple[int, int, int, int]
    confidence: float


@dataclasses.dataclass(frozen=True)
class OcrResult:
    """One read of one page: its words, and their mean confidence.

    ``mean_confidence`` is the mean of ``words`` as the engine reported them,
    and ``0.0`` for a page holding no words.  The words are the only copy of
    a page's text this record keeps.
    """

    words: tuple[OcrWord, ...]
    mean_confidence: float


class OcrEngine(abc.ABC):
    """The one question Tier 1 asks an OCR engine, and the shape of its answer.

    A subclass that omits ``read`` cannot be instantiated, so an engine wired
    wrongly fails at construction rather than at the first document.
    """

    @abc.abstractmethod
    def read(self, image) -> OcrResult:
        """Return every word ``image`` carries, as one :class:`OcrResult`.

        ``image`` is the working frame Tier 0 takes: three-channel BGR.

        Returns:
            One :class:`OcrResult` holding an :class:`OcrWord` per word read
            and the mean of their confidences.
        """
        raise NotImplementedError


#: The read Tier 1 degrades to when no engine could read a page: no words,
#: and no confidence to speak of.  It is one value here so 12.3 and 12.4 cannot
#: each answer "nothing found" in their own spelling.
NO_WORDS = OcrResult(words=(), mean_confidence=0.0)
