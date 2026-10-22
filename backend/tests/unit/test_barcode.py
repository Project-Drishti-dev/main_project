"""13.1 and 13.2 -- the barcode seam, and a payload that round-trips through it.

13.1's claim is that a missing binding is answered rather than raised, so the
test for it asks a decoder built with no binding at all.  13.2's claim is that a
payload drawn as a QR here comes back off a real read unchanged, which is the
only way 13.3 has anything to compare: a comparator fed a string nobody
decoded would prove nothing about a decoder.

**The frame is drawn by the library under test**, which is a real dependency
rather than a stand-in -- there is no barcode fixture to invent when OpenCV's
own QR writer exists in the binding this module already imports.
"""

import dataclasses

import numpy
import pytest

from app.pipeline.tier1 import barcode
from tests.fixtures import mrz_images

#: The payload the round trip carries: the TD3 specimen Part 4 already prints,
#: joined into the two lines a QR holds.  A real zone rather than "hello", so
#: 13.3 can decode this frame and compare what comes back with a printed page.
PAYLOAD = "\n".join(mrz_images.SPECIMENS["TD3"])

#: How many pixels each module of the QR is drawn at.  4 is the smallest this
#: box reads reliably, and the reason is a decoding failure rather than a rule.
SCALE = 4

#: The paper a blank page is filled with and the paper between two codes.
#: Written once because both frames are built from it, and a second copy
#: could differ from the first by one level and say nothing.
PAPER = 255
GAP = 40

#: The reason a test that needs the binding carries when the box has none.
NO_BINDING = "zxing-cpp is not installed"

#: The second payload the two-barcode frame carries: the specimen's number
#: moved and nothing else, so the two are told apart by one character rather
#: than by having nothing in common, and the frame stays the size a page is.
OTHER = PAYLOAD.replace("L898902C", "X999999X")

#: A payload wearing whitespace on both of its own edges, which survives the
#: round trip whole and so may not be trimmed on the way back out of it.
PADDED = "\nL898902C\t"

needs_binding = pytest.mark.skipif(
    barcode.import_zxingcpp() is None, reason=NO_BINDING
)


def a_frame(*payloads, scale=SCALE, gap=GAP):
    """A frame carrying one QR per payload in ``payloads``, side by side on paper.

    A page may carry more than one 2D barcode, so the fixture takes any
    number rather than the single one that would let a reader stop at the
    first and answer half a page.
    """
    binding = barcode.import_zxingcpp()
    codes = [
        numpy.asarray(binding.write_barcode_to_image(
            binding.create_barcode(payload, binding.QRCode), scale,
        ))
        for payload in payloads
    ]
    height = max(code.shape[0] for code in codes)
    width = sum(code.shape[1] for code in codes) + gap * (len(codes) - 1)
    frame = numpy.full((height, width), PAPER, numpy.uint8)
    left = 0
    for code in codes:
        frame[:code.shape[0], left:left + code.shape[1]] = code
        left += code.shape[1] + gap
    return numpy.ascontiguousarray(frame)


def a_qr(payload=PAYLOAD, scale=SCALE):
    """A frame carrying ``payload`` as a QR code, drawn by the binding itself."""
    return a_frame(payload, scale=scale)


# --- 13.1: the seam, and an absence that is an answer ---


def test_the_seam_declares_read_and_nothing_a_decoder_must_also_answer():
    """`D82`'s shape, and the reason a half-built decoder cannot be instantiated."""
    assert barcode.BarcodeDecoder.__abstractmethods__ == frozenset({"read"})
    with pytest.raises(TypeError):
        barcode.BarcodeDecoder()


def test_a_decoder_handed_the_binding_reports_itself_available():
    assert barcode.ZxingBarcodeDecoder(
        binding=barcode.import_zxingcpp()
    ).is_available() is True


def test_a_decoder_handed_no_binding_reports_itself_unavailable():
    """13.1's own claim: absence is a bool, never an exception."""
    assert barcode.ZxingBarcodeDecoder(binding=None).is_available() is False


def test_a_decoder_with_no_binding_reads_nothing_and_raises_nothing():
    """A screening on a box without the binding degrades rather than failing."""
    decoder = barcode.ZxingBarcodeDecoder(binding=None)
    blank = numpy.zeros((60, 60), numpy.uint8)

    assert decoder.read(blank) is barcode.NO_BARCODES


def test_the_binding_is_probed_once_and_the_probe_is_the_module_itself():
    """Cached absence, so a box without it asks once per process, not per page."""
    assert barcode.import_zxingcpp() is barcode.import_zxingcpp()


@needs_binding
def test_the_decoder_this_process_reads_with_reports_itself_available():
    assert isinstance(barcode.ZXING_DECODER, barcode.BarcodeDecoder)
    assert barcode.ZXING_DECODER.is_available() is True


# --- 13.2: a payload drawn here and read back there ---


@needs_binding
def test_a_qr_drawn_here_round_trips_through_a_real_read_unchanged():
    """13.2's own claim: encode here, decode there, and nothing is lost."""
    decoded = barcode.ZXING_DECODER.read(a_qr())

    assert len(decoded) == 1
    assert decoded[0].text == PAYLOAD


@needs_binding
def test_the_seam_keeps_the_payload_whole_and_altered_in_no_way():
    """Whitespace is part of what was encoded, and a seam may not tidy it."""
    decoded = barcode.ZXING_DECODER.read(a_qr(PADDED))[0]

    assert decoded.text == PADDED


@needs_binding
def test_each_record_names_the_symbology_it_was_read_in():
    assert barcode.ZXING_DECODER.read(a_qr())[0].format == "QR Code"


@needs_binding
def test_a_record_carries_the_four_whole_pixels_the_code_took():
    """Four corners clockwise from the top left, which is what a region is."""
    region = barcode.ZXING_DECODER.read(a_qr())[0].region

    assert len(region) == 4
    assert all(isinstance(coord, int) for corner in region for coord in corner)
    (left, top), (right, _), (_, bottom), _ = region
    assert left < right and top < bottom


@needs_binding
def test_a_page_carrying_no_barcode_reads_as_nothing_rather_than_failing():
    """The other half of 13.1: present and finding nothing are both answers."""
    blank = numpy.full((60, 60), PAPER, numpy.uint8)

    assert barcode.ZXING_DECODER.read(blank) == barcode.NO_BARCODES


@needs_binding
def test_every_barcode_on_the_page_is_returned_and_not_only_the_first():
    """A page may carry two, and stopping at one would be a silent half-answer."""
    decoded = barcode.ZXING_DECODER.read(a_frame(PAYLOAD, OTHER))

    assert len(decoded) == 2
    assert {one.text for one in decoded} == {PAYLOAD, OTHER}


@needs_binding
def test_the_record_is_frozen_because_a_payload_may_not_be_edited_after_it_is_read():
    decoded = barcode.ZXING_DECODER.read(a_qr())[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        decoded.text = "anything else"
