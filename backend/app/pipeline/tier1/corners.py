"""Where on a capture the document is: its four corners, in one order.

Tier 1 measures a printed field against the rectangle its template holds, and
13.7 on measures in template space -- so the first thing a capture needs is
where its own page is.  :func:`detect_corners` answers that and
:func:`order_corners` is the one order corners are written in.

**The search is :func:`app.quality_checker.m8_coverage.find_card`.**  That is
the detector this repository already runs on every capture, in five quality
checks, and a sixth copy of it would be a second answer to a question five
answers already give -- free to disagree on exactly the off-axis photographs
where the answer decides whether a layout can be measured at all.

**The corners are whole pixels, clockwise from the top left.**  That is the
order :attr:`app.risk.flags.EvidenceFlag.region` and
:attr:`~app.pipeline.tier1.templates.loader.FieldRect.corners` are both
written in, so a detected corner and a template rectangle are one shape.

**A capture holding no document is a value, not an exception.**  The answer is
:data:`NO_CORNERS`, on the reason ``mrz_region.detect_mrz`` reports a blank
page rather than raising: a page that is not a document is an ordinary outcome.

**An outline that was not a quadrilateral is not answered as one.**  Where
``find_card`` cannot simplify its outline to four corners it answers the
rectangle that best fits it, which is a guess about a page rather than a
measurement of one, and 13.7's homography would straighten a document nobody
has found.  That answer is :data:`NO_CORNERS` here.
"""

from app.quality_checker import m8_coverage

__all__ = [
    "CORNER_COUNT",
    "NO_CORNERS",
    "QUADRILATERAL",
    "detect_corners",
    "order_corners",
]

#: The read Tier 1 degrades to when the frame holds no document.  One empty
#: tuple here, as ``barcode.NO_BARCODES`` is for the barcode read, so a caller
#: and a test cannot each spell "nothing found" in their own way.
NO_CORNERS = ()

#: How many corners a document has, and so how many a capture is answered with.
CORNER_COUNT = 4

#: What ``find_card`` calls an outline it simplified to four corners, which is
#: the only one of its two answers that measured a quadrilateral rather than
#: fitted one.  Named here so the check reads as this module's own.
QUADRILATERAL = "quad"


def _whole_pixels(points):
    """``points`` as whole-pixel ``(x, y)`` pairs, each the nearest pixel to.

    Rounded rather than truncated: ``int`` truncates toward zero, so a corner
    left of the frame would come back a pixel short of where it was measured.
    """
    return tuple((int(round(float(x))), int(round(float(y)))) for x, y in points)


def order_corners(points):
    """``points`` as one document's corners, clockwise from the top left.

    Raises :exc:`ValueError` for anything but :data:`CORNER_COUNT` points: a
    corner set that is not four points is the caller's mistake, and the sort
    below would reshape it into four without ever saying so.
    """
    corners = tuple((float(x), float(y)) for x, y in points)
    if len(corners) != CORNER_COUNT:
        raise ValueError(
            f"a document has {CORNER_COUNT} corners, not {len(corners)}"
        )
    return _whole_pixels(m8_coverage.order_card_corners(corners))


def detect_corners(image):
    """The document's corners in ``image``'s own pixels, or :data:`NO_CORNERS`.

    ``image`` is the working frame Tier 1 takes: three-channel BGR, which is
    the frame ``find_card`` was measured on.
    """
    card = m8_coverage.find_card(image)
    if card is None or card["method"] != QUADRILATERAL:
        return NO_CORNERS
    return order_corners(card["pts"])
