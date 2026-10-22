"""Tier 1's barcode seam: one way to read a 2D barcode off a page, or nothing.

:class:`BarcodeDecoder` is the seam, :class:`DecodedBarcode` is one barcode,
and :class:`ZxingBarcodeDecoder` is the engine behind it.  A missing ``zxingcpp``
is answered through ``is_available()`` and degrades the read to
:data:`NO_BARCODES`, on `D83`'s rule that an absence is a value and not a fault.
"""

import abc
import dataclasses
from functools import lru_cache

__all__ = [
    "BarcodeDecoder",
    "DecodedBarcode",
    "IMPORT",
    "NO_BARCODES",
    "ZXING_DECODER",
    "ZxingBarcodeDecoder",
    "import_zxingcpp",
]

#: Constructor default meaning "import zxingcpp when asked".  Passing
#: ``binding=None`` instead says the binding is definitely absent, which is a
#: different answer and the one a test needs to be the same on every machine.
IMPORT = object()

#: The four corners of a barcode, clockwise from the top left, which is the
#: order :class:`~app.risk.flags.EvidenceFlag` says a region is written in.
_CORNER_ORDER = ("top_left", "top_right", "bottom_right", "bottom_left")


@dataclasses.dataclass(frozen=True)
class DecodedBarcode:
    """One barcode read off a page: its payload, its symbology and its box.

    ``text`` is the decoded payload and the only copy of it this record keeps.
    ``region`` is the four corners the decoder found, whole pixels, clockwise
    from the top left.  Frozen, for the reason
    :class:`~app.pipeline.tier1.ocr.OcrResult` is.
    """

    text: str
    format: str
    region: tuple[tuple[int, int], ...]


class BarcodeDecoder(abc.ABC):
    """The one question Tier 1 asks a barcode decoder, and its answer's shape.

    Declares ``read`` alone, exactly as :class:`~app.pipeline.tier1.ocr.OcrEngine`
    does under `D82`: a decoder wired without it cannot be instantiated.
    """

    @abc.abstractmethod
    def read(self, image) -> tuple:
        """Return every 2D barcode ``image`` carries, as a tuple of records.

        ``image`` is the working frame Tier 0 takes: three-channel BGR.
        """
        raise NotImplementedError


#: The read Tier 1 degrades to when no decoder is installed.  One value here so
#: two callers cannot each spell "nothing found" in their own way.
NO_BARCODES = ()


@lru_cache(maxsize=1)
def import_zxingcpp():
    """Return the ``zxingcpp`` module, or ``None`` where it is not installed.

    The absence is cached as firmly as the presence, so a box without the
    binding asks once per process rather than once per document.
    """
    try:
        import zxingcpp
    except ImportError:
        return None
    return zxingcpp


def _region(position):
    """``position``'s four corners as whole pixels, clockwise from the top left."""
    return tuple(
        (int(getattr(position, name).x), int(getattr(position, name).y))
        for name in _CORNER_ORDER
    )


class ZxingBarcodeDecoder(BarcodeDecoder):
    """zxing-cpp behind the seam, reported absent rather than raised.

    ``binding`` stands in for an already-imported ``zxingcpp``, so a test can
    answer either way on a machine that has neither.
    """

    def __init__(self, *, binding=IMPORT):
        self._binding = binding

    def _zxingcpp(self):
        """The binding to read through: the one handed in, or zxingcpp itself."""
        if self._binding is not IMPORT:
            return self._binding
        return import_zxingcpp()

    def is_available(self) -> bool:
        """Whether a read could run, which is whether the binding imports.

        Every state answers a bool, the absent one included, so a caller asks
        the question without a handler wrapped around asking it.
        """
        return self._zxingcpp() is not None

    def read(self, image) -> tuple:
        """Every 2D barcode ``image`` carries, or :data:`NO_BARCODES` when absent.

        Every symbology the binding reports is returned rather than a chosen
        few, and each record names the one it was read in.
        """
        binding = self._zxingcpp()
        if binding is None:
            return NO_BARCODES
        return tuple(
            DecodedBarcode(
                text=found.text,
                format=str(found.format),
                region=_region(found.position),
            )
            for found in binding.read_barcodes(image)
        )


#: The decoder this process reads with, module-level so the binding is probed
#: once rather than per document, on the reason
#: :data:`app.pipeline.tier1.selection.DEFAULT_ENGINES` is module-level.
ZXING_DECODER = ZxingBarcodeDecoder()
