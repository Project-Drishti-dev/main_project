"""How far each printed field sits from where its own template rectangle puts it.

13.9's question, asked of the frame :mod:`app.pipeline.tier1.align` straightened
onto the template: for every field the template places, how far has that field's
ink moved, and is the move further than the ``position`` tolerance in its row?

**A displacement is a whole-pixel distance in template space, and it is measured
only where the reference says where the field's ink is.**  ``D99`` records why
the second half of that is a limit of the data rather than an oversight, and
``D98`` is what put the number being compared against into each field's own row.

13.10 asks about the other half of the abstract's "layout, fonts and text
positions": :func:`font_style` measures the type a page prints -- how full its
glyphs are and how even their heights -- and :func:`layout_score` is the one
number 13.9's displacements and that proxy are both read into.
"""

import dataclasses
import importlib.resources
import math
from collections.abc import Mapping
from types import MappingProxyType

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.pipeline.tier1.templates import loader
from app.pipeline.tier1.templates.loader import Template, TemplateError
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

__all__ = [
    "BLOB_BRIDGE_PX",
    "BORDER_MARGIN_PX",
    "DENSITY_TOLERANCE",
    "DEVIATION_BAND",
    "FieldDeviation",
    "FontStyle",
    "GLYPH_MAX_HEIGHT_PX",
    "GLYPH_MIN_AREA_PX",
    "GLYPH_MIN_HEIGHT_PX",
    "INK_CONTRAST_LEVELS",
    "MAX_DISPLACEMENT_PX",
    "MIN_REFERENCE_INK",
    "PAPER_PERCENTILE",
    "POSITION_KEY",
    "SOURCE_MODULE",
    "SPREAD_TOLERANCE",
    "TOLERANCE_KEY",
    "VALUE_SATURATION",
    "compare_layout",
    "field_deviations",
    "font_deviation",
    "font_style",
    "layout_score",
    "read_tolerances",
]

#: The key a field's row carries its allowances under, as 13.8 wrote it.
TOLERANCE_KEY = "tolerance"

#: The one of the three allowances 13.9 measures against.
POSITION_KEY = "position"

#: The severity band this finding sits in, held to ``v1.yaml`` by a test.
DEVIATION_BAND = "low"

#: The name every finding this module builds answers under.
SOURCE_MODULE = "app.pipeline.tier1.layout"

#: Which percentile of a frame is that frame's own paper.
PAPER_PERCENTILE = 95

#: How far below paper a pixel must be before it is ink rather than shading.
INK_CONTRAST_LEVELS = 40

#: The aligned frame's outer band, set aside before any ink is taken.
BORDER_MARGIN_PX = 8

#: How far apart two blobs of one field's ink may be and still be its ink.
BLOB_BRIDGE_PX = 8

#: How far from its own rectangle a field's ink is looked for, in pixels.
MAX_DISPLACEMENT_PX = 64.0

#: The share of a rectangle that must be inked in the reference to be scored.
MIN_REFERENCE_INK = 0.02

#: The displacement, as a multiple of the tolerance, at which value reaches 1.0.
VALUE_SATURATION = 2.0

#: How far a page's ink share may sit from the reference's own, as an absolute
#: share of the glyph boxes.  The lay-down/photograph/warp round trip costs
#: 0.010 of one, and D100 records where that number came from.
DENSITY_TOLERANCE = 0.15

#: How far a page's glyph heights may spread from the reference's own, in the
#: same units the spread itself is measured in.  The same round trip costs
#: 0.001 of one.
SPREAD_TOLERANCE = 0.03

#: The least and the most rows a mark may be and still be read as type.  The
#: committed reference prints glyphs 15 to 22 rows tall and carries a photo
#: block of 360, so the band is an order of magnitude either side of the
#: tallest type on the page that ships -- this layout's band, not a rule.
GLYPH_MIN_HEIGHT_PX = 6
GLYPH_MAX_HEIGHT_PX = 60

#: The least ink a mark may carry and still be a glyph rather than a speck.
GLYPH_MIN_AREA_PX = 8


def _positive_number(value) -> bool:
    """Whether ``value`` is a real, finite, strictly positive number.

    ``bool`` is an ``int``, so ``True`` would otherwise read as a tolerance of
    one pixel, and ``nan`` fails both halves of the comparison below.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0 < value < math.inf


def read_tolerances(template: Template) -> Mapping[str, float]:
    """The ``position`` allowance each field of ``template``'s own file records.

    Read out of the one parse :func:`load_template` already made, on ``D98``'s
    ground that the loader holds no tolerance and this is the module that knows
    what the number is for.

    :raises TemplateError: for a field whose row carries no positive
        ``position``, which is refused rather than defaulted -- a field measured
        against a tolerance nobody wrote is a field measured against nothing.
    """
    document = loader.read_document(template.name)
    rows = document.get(loader.FIELDS_KEY)

    tolerances = {}
    for field in template.fields:
        row = rows.get(field) if isinstance(rows, Mapping) else None
        tolerance = row.get(TOLERANCE_KEY) if isinstance(row, Mapping) else None
        position = (
            tolerance.get(POSITION_KEY) if isinstance(tolerance, Mapping) else None
        )
        if not _positive_number(position):
            raise TemplateError(
                f"the {field!r} field of the {template.name!r} template carries no "
                f"positive {TOLERANCE_KEY!r} {POSITION_KEY!r} to measure it against"
            )
        tolerances[field] = float(position)
    return MappingProxyType(tolerances)


def reference_gray(template: Template) -> np.ndarray:
    """The template's reference image as one-channel grey, read as a resource.

    Read through :func:`importlib.resources` on ``loader``'s reason: a path
    assembled from ``__file__`` stops resolving once the package is installed.
    """
    resource = importlib.resources.files(loader.TEMPLATES_PACKAGE).joinpath(
        template.reference_image
    )
    try:
        with resource.open("rb") as stream:
            with Image.open(stream) as image:
                return np.ascontiguousarray(np.array(image.convert("L")))
    except (UnidentifiedImageError, OSError):
        raise TemplateError(
            f"the {template.reference_image!r} reference cannot be read as an image"
        ) from None


def _paper_level(grey: np.ndarray) -> float:
    """The frame's own paper level, a percentile rather than its brightest pixel."""
    return float(np.percentile(grey, PAPER_PERCENTILE))


def _ink(grey: np.ndarray, paper: float) -> np.ndarray:
    """``grey``'s ink, with the aligned frame's outer band set aside.

    **The band is not the page.**  The corners 13.6 hands 13.7 are the
    detector's and land a few pixels off the page's own, so a warp built on them
    samples the capture's background into the frame's outermost pixels.  That is
    ink belonging to no field, and it drags a centroid toward the middle.
    """
    mask = grey < (paper - INK_CONTRAST_LEVELS)
    margin = BORDER_MARGIN_PX
    mask[:margin, :] = False
    mask[-margin:, :] = False
    mask[:, :margin] = False
    mask[:, -margin:] = False
    return mask


def _grey(frame: np.ndarray) -> np.ndarray:
    """Template space as one-channel grey.

    :raises ValueError: for a frame that is not three-channel, which is the
        only shape :func:`~app.pipeline.tier1.align.warp_to_template` answers.
    """
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(
            "aligned must be a three-channel frame, not "
            f"{getattr(frame, 'shape', type(frame).__name__)}"
        )
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _centres(template: Template) -> Mapping[str, tuple[float, float]]:
    """Where each field's own rectangle puts the middle of its ink."""
    return MappingProxyType({
        field: (rect.x + rect.width / 2, rect.y + rect.height / 2)
        for field, rect in template.fields.items()
    })


def _scoreable(reference: np.ndarray, rect) -> bool:
    """Whether the reference carries enough ink inside ``rect`` to measure against.

    **A rectangle with nothing printed in it records where a value may go, not
    where the ink is.**  Its centre is a drawn box, and scoring a field against
    one measures the box: on the committed layout a correctly printed value
    reads 7.6 pixels off its own rectangle, against a tolerance of 12.  A field
    like that is skipped, never scored as a displacement of zero.
    """
    patch = reference[rect.y:rect.y + rect.height, rect.x:rect.x + rect.width]
    inked = float((patch < (_paper_level(reference) - INK_CONTRAST_LEVELS)).sum())
    return inked > MIN_REFERENCE_INK * patch.size


def _claimed(mask, centres):
    """Each ink blob's centroid, given to the nearest field centre within reach.

    **Nearest, and not "inside its own rectangle".**  A field printed more than
    half a row from where the layout puts it lands inside its neighbour's
    rectangle, and a box test hands the ink to the neighbour -- a confidently
    wrong finding about the wrong field, which is what a shifted field produces
    on exactly the page this module exists to look at.  Nearest-centre keeps a
    moved field with its own ink, and ``MAX_DISPLACEMENT_PX`` stops a label on
    the far side of the page being claimed by the field nearest to it.
    """
    bridge = np.ones((2 * BLOB_BRIDGE_PX + 1,) * 2, np.uint8)
    count, labels = cv2.connectedComponents(cv2.dilate(mask.astype(np.uint8), bridge))

    claimed = {field: [] for field in centres}
    for label in range(1, count):
        rows, columns = np.nonzero((labels == label) & mask)
        if not columns.size:
            continue
        x, y = float(columns.mean()), float(rows.mean())
        field = min(
            centres,
            key=lambda name: (x - centres[name][0]) ** 2 + (y - centres[name][1]) ** 2,
        )
        if math.hypot(x - centres[field][0], y - centres[field][1]) <= MAX_DISPLACEMENT_PX:
            claimed[field].append((x, y))
    return claimed


@dataclasses.dataclass(frozen=True)
class FieldDeviation:
    """One field's measured displacement, and the allowance it is measured against.

    ``offset`` is whole pixels of template space from the rectangle's centre to
    the field's own ink, ``deviation`` that offset's length, and ``tolerance``
    the ``position`` allowance of that field's own row.  ``region`` is the
    rectangle's corners, which is the frame the finding is reported in.
    """

    field: str
    region: tuple
    offset: tuple
    deviation: float
    tolerance: float

    @property
    def score(self) -> float:
        """How far past its tolerance the field sits, in ``[0, 1]``."""
        return min(1.0, self.deviation / (VALUE_SATURATION * self.tolerance))

    @property
    def deviates(self) -> bool:
        """Whether the field sits further out than its own row allows."""
        return self.deviation > self.tolerance


def field_deviations(aligned, template, tolerances=None):
    """One :class:`FieldDeviation` per field that can be measured, in template order.

    :param aligned: the BGR frame :func:`~app.pipeline.tier1.align.warp_to_template`
        answered, already on the template's own frame.
    :param template: the loaded template that frame was warped onto.
    :param tolerances: the allowances :func:`read_tolerances` answers; read off
        the template's own file when not given.
    :returns: a tuple of deviations, empty where no field could be measured --
        which is an absence of ink, not a page where nothing moved.
    :raises ValueError: for a frame that is not three-channel, or for
        tolerances carrying no entry for a field the template places.
    """
    grey = _grey(aligned)
    if tolerances is None:
        tolerances = read_tolerances(template)
    missing = sorted(set(template.fields) - set(tolerances))
    if missing:
        raise ValueError(f"no tolerance is given for the field {missing[0]!r}")

    centres = _centres(template)
    claimed = _claimed(_ink(grey, _paper_level(grey)), centres)
    reference = reference_gray(template)

    measured = []
    for field, rect in template.fields.items():
        points = claimed[field]
        if not points or not _scoreable(reference, rect):
            continue
        column = sum(x for x, _ in points) / len(points)
        row = sum(y for _, y in points) / len(points)
        offset = (
            int(round(column - centres[field][0])),
            int(round(row - centres[field][1])),
        )
        measured.append(FieldDeviation(
            field=field,
            region=rect.corners,
            offset=offset,
            deviation=math.hypot(*offset),
            tolerance=float(tolerances[field]),
        ))
    return tuple(measured)


def compare_layout(aligned, template, tolerances=None):
    """One ``LAYOUT_DEVIATION`` finding per field sitting further out than its row allows.

    :returns: a tuple of :class:`~app.risk.flags.EvidenceFlag` in the template's
        own field order, empty where every measured field sat within tolerance.
    """
    return tuple(
        EvidenceFlag(
            id=flag_ids.LAYOUT_DEVIATION,
            tier=1,
            label=(
                f"the printed {measured.field.replace('_', ' ')} sits away from "
                "where the layout puts it"
            ),
            weight_band=DEVIATION_BAND,
            value=measured.score,
            confidence=1.0,
            region=measured.region,
            expected=None,
            found=None,
            reason=(
                f"the field's ink sits {measured.deviation:.0f} pixels from the "
                f"rectangle the layout gives it and the tolerance is "
                f"{measured.tolerance:g} pixels"
            ),
            source_module=SOURCE_MODULE,
            field=measured.field,
        )
        for measured in field_deviations(aligned, template, tolerances)
        if measured.deviates
    )


@dataclasses.dataclass(frozen=True)
class FontStyle:
    """The type a page prints, as the two numbers a font-style proxy is made of.

    ``stroke_density`` is the share of the glyphs' own boxes that carries ink --
    how much of a glyph is drawn on -- and ``height_spread`` is the standard
    deviation of their heights over their mean.  ``glyphs`` is how many marks the
    band admitted, which is why it is carried rather than implied.
    """

    glyphs: int
    stroke_density: float
    height_spread: float


def _style_of(grey: np.ndarray):
    """The type ``grey`` prints, or ``None`` where it prints none.

    **The photo block is not type, and the height band is what leaves it out.**
    360 rows is not a glyph at any weight, and naming the one block this layout
    happens to carry would be a rule about the layout rather than about type.
    """
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        _ink(grey, _paper_level(grey)).astype(np.uint8)
    )

    heights = []
    inked = boxed = 0
    for label in range(1, count):
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if GLYPH_MIN_HEIGHT_PX <= height <= GLYPH_MAX_HEIGHT_PX and area >= GLYPH_MIN_AREA_PX:
            heights.append(height)
            inked += area
            boxed += width * height
    if not heights:
        return None

    mean = sum(heights) / len(heights)
    spread = math.sqrt(sum((h - mean) ** 2 for h in heights) / len(heights)) / mean
    return FontStyle(
        glyphs=len(heights),
        stroke_density=float(inked / boxed),
        height_spread=float(spread),
    )


def font_style(frame: np.ndarray):
    """The font-style proxy of the type ``frame`` prints, or ``None`` where it prints none.

    :param frame: the BGR frame :func:`~app.pipeline.tier1.align.warp_to_template`
        answered, already on the template's own frame.
    :returns: a :class:`FontStyle`, or ``None`` where nothing on the page is a
        glyph the band admits -- an absence of type, not a page whose type matches.
    :raises ValueError: for a frame that is not three-channel.
    """
    return _style_of(_grey(frame))


def _departure(found: float, expected: float, tolerance: float) -> float:
    """How far ``found`` sits from ``expected``, as a share of ``tolerance``."""
    return float(min(1.0, abs(found - expected) / tolerance))


def font_deviation(aligned, template):
    """How far this page's type sits from the face its own reference prints, in ``[0, 1]``.

    **The worse of the two style numbers**, so a face that differs in weight but
    not in size is still read as a face that differs.  ``None`` where the page or
    the reference prints no type at all: half of a comparison that cannot be made
    is not a clean half, and ``D99`` is the precedent.

    :raises ValueError: for a frame that is not three-channel.
    """
    found = font_style(aligned)
    expected = _style_of(reference_gray(template))
    if found is None or expected is None:
        return None
    return max(
        _departure(found.stroke_density, expected.stroke_density, DENSITY_TOLERANCE),
        _departure(found.height_spread, expected.height_spread, SPREAD_TOLERANCE),
    )


def layout_score(aligned, template, tolerances=None):
    """How much of its own layout this page reproduces, in ``[0, 1]``.

    The mean of the position agreement 13.9 measures and the font agreement 13.10
    measures, so a page printed in another face scores below a page printed in
    this one even where every field sits exactly where the layout puts it.

    :returns: ``None`` where either half could not be measured at all -- a page
        this module says nothing about rather than one it calls a match.
    :raises ValueError: for a frame that is not three-channel, or for tolerances
        carrying no entry for a field the template places.
    """
    deviations = field_deviations(aligned, template, tolerances)
    style = font_deviation(aligned, template)
    if not deviations or style is None:
        return None

    position = sum(1.0 - one.score for one in deviations) / len(deviations)
    return (position + (1.0 - style)) / 2.0
