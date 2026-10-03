"""A synthetic passport data page: known labels and values at a known size.

Part 12's frame for OCR.  Each field is printed once from text this file
states, and every box handed back is where its own text was printed, so 12.8
can crop to a field and 12.14 can report where a field came from off ground
truth rather than off a guess.  The specimen is the person
:data:`~tests.fixtures.mrz_images.SPECIMENS` prints, on the same paper and the
same ink, because a printed field and the MRZ it has to agree with are one
document.
"""

import dataclasses

import cv2
import numpy as np

from tests.fixtures import mrz_images

__all__ = [
    "BACKGROUND_LEVEL",
    "DocumentPage",
    "INK_COLOUR",
    "INK_LEVEL",
    "PAGE_SIZE",
    "PAPER_LEVEL",
    "PrintedField",
    "SPECIMENS",
    "draw_document",
    "field_of",
    "lay",
    "photograph",
    "render_document",
]

#: Paper and ink, re-exported from Part 4's fixture rather than written down a
#: second time: one level for each, so nothing downstream has to ask which face
#: a frame was drawn on.
PAPER_LEVEL = mrz_images.PAPER_LEVEL
INK_LEVEL = mrz_images.INK_LEVEL

#: What a capture is filled with around the page, a shade under ink and
#: well under paper: a document lying on a dark surface, not the whole frame.
BACKGROUND_LEVEL = 40

#: The colour a field is printed in: ink in all three channels, so the page is
#: neutral before a caller does anything to its colour.
INK_COLOUR = (INK_LEVEL, INK_LEVEL, INK_LEVEL)

#: The page the fields are printed on, ``(width, height)`` in pixels.  A
#: landscape data page at a passport's proportions, with the printed block down
#: its left and the rest of the page left as paper.
PAGE_SIZE = (1000, 700)

#: The face the fields are printed in.  Hershey Simplex, and not Part 4's 5x7
#: cell table: an OCR engine is what has to read this page, and a table of
#: stamped cells has neither an advance nor a baseline, so neither a word's box
#: nor a form's row could be measured off it.
FONT = cv2.FONT_HERSHEY_SIMPLEX

#: The scale and the stroke that face is drawn at.  A caller wanting a page
#: too small to read well asks for a smaller ``font_scale``, and 12.9's
#: low-confidence field is one of those pages.
FONT_SCALE = 1.0
THICKNESS = 2

#: Paper around the printed block, between the widest label and the values, and
#: between one printed row and the next, in pixels.
MARGIN = 60
LABEL_GAP = 40
ROW_GAP = 24

#: The one document this fixture prints, as ``(name, label, value)`` triples in
#: the order it prints them.  Every value is the one the TD3 specimen carries,
#: and the two dates print as a passport prints them rather than as ISO, so
#: 12.13 has a printed form to normalise.
SPECIMENS = {
    "passport": (
        ("name", "Name", "ERIKSSON ANNA MARIA"),
        ("passport_number", "Passport No", "L898902C"),
        ("date_of_birth", "Date of birth", "12 AUG 1974"),
        ("date_of_expiry", "Date of expiry", "15 APR 2012"),
    ),
}


@dataclasses.dataclass(frozen=True)
class PrintedField:
    """One printed field: what it is, how it is labelled, and where both went.

    ``name`` is the key a caller overrides it by and 12.11's table extracts
    into, ``label`` the anchor text on the page and ``value`` the text beside
    it.  The two boxes are half-open, and are where each of those was printed.
    """

    name: str
    label: str
    value: str
    label_box: tuple
    value_box: tuple


@dataclasses.dataclass(frozen=True)
class DocumentPage:
    """One printed page and the ground truth it was printed from.

    ``image`` is a three-channel BGR ``uint8`` frame of ``size``, and ``fields``
    is one :class:`PrintedField` per printed row in the order they were
    printed.  The rest is the geometry the drawing used, kept so a test can say
    what it measured against.  Frozen, and carrying no public method, for the
    reason :class:`~app.pipeline.tier1.ocr.OcrResult` is.
    """

    image: np.ndarray
    fields: tuple
    size: tuple
    font: int
    font_scale: float
    thickness: int
    margin: int
    label_gap: int
    row_gap: int


def _metrics(text, font, font_scale, thickness):
    """``text``'s width, and its ascent above and descent below a baseline.

    All three are ``cv2.getTextSize``'s, because ``putText`` draws inside what
    it measures and a box worked out by hand would be a second answer.
    """
    (width, height), descent = cv2.getTextSize(text, font, font_scale, thickness)
    return int(width), int(height), int(descent)


def _print_line(page, text, left, baseline, font, font_scale, thickness):
    """Print one line with its baseline at ``baseline``; return the box it took.

    ``putText`` places text by its baseline, so the box is the ascent above
    that line and the descent below it, half-open as every box here is.
    """
    width, ascent, descent = _metrics(text, font, font_scale, thickness)
    cv2.putText(
        page, text, (left, baseline), font, font_scale, INK_COLOUR, thickness,
        cv2.LINE_8,
    )
    return (int(left), int(baseline - ascent), int(left + width), int(baseline + descent))


def draw_document(
    rows,
    size=PAGE_SIZE,
    font=FONT,
    font_scale=FONT_SCALE,
    thickness=THICKNESS,
    margin=MARGIN,
    label_gap=LABEL_GAP,
    row_gap=ROW_GAP,
):
    """Print ``rows`` on a page and say where every label and value went.

    ``rows`` is a non-empty sequence of ``(name, label, value)`` triples whose
    names are all different, because a field is addressed by its name.  The
    values share one column, placed by the widest label, so a printed value can
    be swapped without any other box moving.  A block that will not fit inside
    ``size`` is refused rather than clipped: half a value reads as a misread
    one, and would fail a pipeline test for a reason of the fixture's making.
    """
    rows = tuple((name, label, value) for name, label, value in rows)
    if not rows:
        raise ValueError("a page needs at least one field printed on it")
    names = [name for name, _, _ in rows]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"two printed fields are both named {repeated[0]!r}")

    def measured(text):
        return _metrics(text, font, font_scale, thickness)

    width, height = size
    column = margin + max(measured(label)[0] for _, label, _ in rows) + label_gap
    ascent = max(measured(label)[1] for _, label, _ in rows)
    descent = max(measured(label)[2] for _, label, _ in rows)
    block = (
        column + max(measured(value)[0] for _, _, value in rows),
        margin + ascent + (ascent + row_gap) * (len(rows) - 1) + descent + margin,
    )
    if block[0] > width or block[1] > height:
        raise ValueError(
            f"{len(rows)} printed fields need {block[0]}x{block[1]} pixels "
            f"and do not fit a page of {width}x{height}"
        )

    page = np.full((height, width, 3), PAPER_LEVEL, np.uint8)
    fields = []
    baseline = margin + ascent
    for name, label, value in rows:
        label_box = _print_line(
            page, label, margin, baseline, font, font_scale, thickness
        )
        value_box = _print_line(
            page, value, column, baseline, font, font_scale, thickness
        )
        fields.append(
            PrintedField(
                name=name, label=label, value=value,
                label_box=label_box, value_box=value_box,
            )
        )
        baseline += ascent + row_gap

    return DocumentPage(
        image=page,
        fields=tuple(fields),
        size=(int(width), int(height)),
        font=int(font),
        font_scale=float(font_scale),
        thickness=int(thickness),
        margin=int(margin),
        label_gap=int(label_gap),
        row_gap=int(row_gap),
    )


def render_document(name="passport", values=None, **kwargs):
    """Print the document ``name``, or ``values``' own text where it names one.

    ``values`` maps a field's name to the text to print for it -- 12.15 alters
    one printed date this way -- and a name the document prints no field under
    is refused rather than ignored, so a misspelled override cannot leave a
    page that looks printed and says nothing.  Every other field prints as the
    specimen states it.
    """
    if name not in SPECIMENS:
        raise ValueError(
            f"{name!r} is not a document this fixture prints: {sorted(SPECIMENS)}"
        )
    rows = SPECIMENS[name]
    if values:
        unknown = sorted(set(values) - {field for field, _, _ in rows})
        if unknown:
            raise ValueError(f"{name} prints no field named {unknown[0]!r}")
        rows = tuple(
            (field, label, values.get(field, value)) for field, label, value in rows
        )
    return draw_document(rows, **kwargs)


def field_of(page, name):
    """The field ``name``, read off the page's own description.

    Raises ``KeyError`` naming the fields the page does print, so a test asking
    for a field this page has not got fails on its own name rather than on the
    pipeline code it meant to exercise.
    """
    for field in page.fields:
        if field.name == name:
            return field
    printed = [field.name for field in page.fields]
    raise KeyError(f"this page prints no field named {name!r}: {printed}")


def lay(image, size, quad, frame_size, background=BACKGROUND_LEVEL):
    """``image`` laid into a capture of ``frame_size`` at ``quad``.

    ``image`` is a three-channel BGR frame of ``size``, ``(width, height)``, and
    ``quad`` the four ``(x, y)`` positions its own corners are put at,
    clockwise from the top left -- this project's one corner order -- so a test
    that lays a page at a known quadrilateral knows where its corners are and
    can measure a detector and an alignment against them.  13.7 lays the
    committed template's own reference this way, so the frame it warps back to
    is the one it started as.
    """
    width, height = frame_size
    capture = np.full((height, width, 3), background, np.uint8)
    laid_at = np.array(quad, np.float32).reshape(4, 2)
    printed_at = np.array(
        [
            [0, 0],
            [size[0], 0],
            [size[0], size[1]],
            [0, size[1]],
        ],
        np.float32,
    )
    matrix = cv2.getPerspectiveTransform(printed_at, laid_at)
    inside = np.zeros((height, width), np.uint8)
    cv2.fillConvexPoly(inside, laid_at.astype(np.int32), 255)
    laid = cv2.warpPerspective(image, matrix, frame_size)
    capture[inside > 0] = laid[inside > 0]
    return capture


def photograph(page, quad, frame_size, background=BACKGROUND_LEVEL):
    """``page`` laid into a capture of ``frame_size`` at ``quad``.

    :func:`lay`, given a printed page's own frame.
    """
    return lay(page.image, page.size, quad, frame_size, background)

