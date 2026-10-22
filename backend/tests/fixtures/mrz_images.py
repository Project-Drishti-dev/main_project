"""A synthetic MRZ page: one glyph per cell, at a size, an angle and a noise
level the caller names.

The input is the *text* of a zone, read from
:data:`~app.pipeline.tier0.document.MRZ_SHAPES` for its shape.  The output is
an :class:`MrzPage`: a BGR frame plus the ground truth the frame was drawn
from -- the characters, the half-open box of every character cell, and the
geometry the drawing used.

**The face is monospaced and the pitch is fixed.**  Every character is stamped
into a box of ``cell_px`` followed by ``gap`` columns of paper, so character
*k*'s ink is inside cell *k* and cannot touch character *k + 1*'s.  Every
character in the ICAO set is drawn from one 5x7 pattern table, so no character
is wider than another and no advance is a font metric.

**The ink is the only thing the page carries.**  Paper is
:data:`PAPER_LEVEL` in all three channels and ink is :data:`INK_LEVEL` in all
three, so the frame is neutral and a caller's own colour or shading step is
never fighting what was drawn.  The shading and the grain are applied *after*
the rotation, so a turned page's corners and its paper carry the same lighting
as the rest of the frame.

**The cell boxes are ground truth in the frame they were drawn into, which is
the upright one.**  A page drawn at a non-zero ``angle_deg`` is a page whose
zone the *chain* has to survive, not a page whose pixels a caller can index:
the boxes are where the glyphs were before the turn, and nothing here composes
the turn into them.  :func:`read_zone` therefore reads an upright page; the
angle is exercised by asking the chain a question instead.
"""

import dataclasses
import functools

import cv2
import numpy as np

from app.pipeline.tier0 import document


#: Paper, in every channel.  A neutral, so that nothing a caller does to the
#: colour of a page has to fight the fixture.
PAPER_LEVEL = 255

#: Ink, in every channel.
INK_LEVEL = 0

#: Columns of paper left between one cell and the next.  4.1 turns a leaned
#: page and 4.13 turns it back, and each :func:`cv2.warpAffine` spreads a hard
#: edge about a pixel either side, so a narrow gap is gone before 4.3 numbers
#: a component and 4.10 has nothing to cut on.  Measured on a page turned to
#: both signs of 4 degrees, on all three formats: a gap of 1 merges 44 glyphs
#: into 23 to 26 on every one, a gap of 2 is exact everywhere except a TD3
#: turned anticlockwise, which loses one glyph, and 3 is the first gap that is
#: exact on all three.  Four is what is drawn, so the sweep has a pixel of
#: margin over the measured minimum.
GAP_PX = 4

#: Paper around the zone when the caller does not name a page size, in pixels.
MARGIN = 40

#: Line-to-line advance, as a multiple of the cell height.  Twice the cell is
#: the ICAO line pitch, and it is the reason two lines of a zone do not share a
#: row with each other: 4.5 groups by vertical overlap, and 4.2's block size is
#: held to staying under the line pitch.
LINE_PITCH_FACTOR = 2

#: The face the generator draws in unless the caller names another: 15 pixels
#: wide by 21 high, which is inside 4.4's glyph height band (8 to 24).
DEFAULT_CELL_PX = (15, 21)

#: Cell sizes the tests sweep, ``(width, height)`` in pixels.  Both sides are
#: whole multiples of the 5x7 pattern, so every pattern pixel is the same size
#: and :func:`read_zone` can read any of the three back exactly.  The two
#: smaller are inside 4.4's height band; the largest is *above* its ceiling,
#: which makes it a control rather than a size to detect.
CELL_SIZES = ((10, 14), (15, 21), (20, 28))

#: Angles the tests sweep, in degrees.  Clockwise is positive, as it is for
#: :func:`cv2.getRotationMatrix2D` and therefore for 4.1.
ANGLE_DEGREES = (-4.0, -2.0, 0.0, 2.0, 4.0)

#: Sensor noise the tests sweep, in grey levels.  0 is a clean draw, 4 is
#: visible grain on a cheap capture, 10 is a bad one.
NOISE_SIGMA_LEVELS = (0.0, 4.0, 10.0)

#: Seed the grain is drawn from, so a failure repeats.
NOISE_SEED = 7

#: The three zones this project prints, as text.  One specimen per format,
#: each of the shape :data:`~app.pipeline.tier0.document.MRZ_SHAPES` names for
#: it, and each carrying a composite check digit this repository states rather
#: than reads from a specimen document.
SPECIMENS = {
    "TD1": (
        "I<UTOD231458907<<<<<<<<<<<<<<<",
        "7408122F1204159UTO<<<<<<<<<<<7",
        "ERIKSSON<<ANNA<MARIA" + "<" * 10,
    ),
    "TD2": (
        "V<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<",
        "L898902C<3UTO7408122F1204159ZE184283",
    ),
    "TD3": (
        "P<UTOERIKSSON<<ANNA<MARIA" + "<" * 19,
        "L898902C<3"          # 1-10  document number and its check digit
        "UTO"                 # 11-13 nationality
        "7408122"             # 14-20 date of birth and its check digit
        "F"                   # 21     sex
        "1204159"             # 22-28 date of expiry and its check digit
        "ZE184226B<<<<<1"     # 29-43 personal number and its check digit
        "6",                  # 44     composite check digit
    ),
}

#: The pattern table: one 5x7 bitmap per ICAO character, rows of five
#: characters separated by ``/``, ``#`` for ink.  Every entry is a different
#: pattern, which is what makes :func:`read_zone` able to name what was drawn.
_FONT = {
    "0": ".###./#...#/#..##/#.#.#/##..#/#...#/.###.",
    "1": "..#../.##../..#../..#../..#../..#../.###.",
    "2": ".###./#...#/....#/...#./..#../.#.../#####",
    "3": ".###./#...#/....#/..##./....#/#...#/.###.",
    "4": "...#./..##./.#.#./#..#./#####/...#./...#.",
    "5": "#####/#..../####./....#/....#/#...#/.###.",
    "6": "..##./.#.../#..../####./#...#/#...#/.###.",
    "7": "#####/....#/...#./..#../.#.../.#.../.#...",
    "8": ".###./#...#/#...#/.###./#...#/#...#/.###.",
    "9": ".###./#...#/#...#/.####/....#/...#./.##..",
    "A": ".###./#...#/#...#/#####/#...#/#...#/#...#",
    "B": "####./#...#/#...#/####./#...#/#...#/####.",
    "C": ".###./#...#/#..../#..../#..../#...#/.###.",
    "D": "###../#..#./#...#/#...#/#...#/#..#./###..",
    "E": "#####/#..../#..../####./#..../#..../#####",
    "F": "#####/#..../#..../####./#..../#..../#....",
    "G": ".###./#...#/#..../#.###/#...#/#...#/.####",
    "H": "#...#/#...#/#...#/#####/#...#/#...#/#...#",
    "I": "#####/..#../..#../..#../..#../..#../#####",
    "J": "..###/...#./...#./...#./...#./#..#./.##..",
    "K": "#...#/#..#./#.#../##.../#.#../#..#./#...#",
    "L": "#..../#..../#..../#..../#..../#..../#####",
    "M": "#...#/##.##/#.#.#/#.#.#/#...#/#...#/#...#",
    "N": "#...#/##..#/#.#.#/#.#.#/#..##/#...#/#...#",
    "O": ".###./#...#/#...#/#...#/#...#/#...#/.###.",
    "P": "####./#...#/#...#/####./#..../#..../#....",
    "Q": ".###./#...#/#...#/#...#/#.#.#/#..#./.##.#",
    "R": "####./#...#/#...#/####./#.#../#..#./#...#",
    "S": ".####/#..../#..../.###./....#/....#/####.",
    "T": "#####/..#../..#../..#../..#../..#../..#..",
    "U": "#...#/#...#/#...#/#...#/#...#/#...#/.###.",
    "V": "#...#/#...#/#...#/#...#/#...#/.#.#./..#..",
    "W": "#...#/#...#/#...#/#.#.#/#.#.#/##.##/#...#",
    "X": "#...#/#...#/.#.#./..#../.#.#./#...#/#...#",
    "Y": "#...#/#...#/.#.#./..#../..#../..#../..#..",
    "Z": "#####/....#/...#./..#../.#.../#..../#####",
    "<": "..#../.#.../#..../.#.../..#../..#../..#..",
}

#: Columns in a pattern, and rows in one.
FONT_WIDTH, FONT_HEIGHT = 5, 7

#: The pattern table with each row's marks read as booleans, in the order the
#: table writes them -- which is what makes a tie in :func:`_match` resolve
#: the same way on every run.
_GLYPHS = {
    character: tuple(
        tuple(mark == "#" for mark in row) for row in rows.split("/")
    )
    for character, rows in _FONT.items()
}


@dataclasses.dataclass(frozen=True)
class MrzPage:
    """One drawn page and the ground truth it was drawn from.

    ``image`` is a three-channel BGR ``uint8`` frame of ``size``.  ``lines``
    is the text that was drawn, ``cells`` is one half-open
    ``(left, top, right, bottom)`` box per drawn character in reading order --
    outer index the line from 1's zero, inner index the character from 0 --
    and ``format`` is the name
    :data:`~app.pipeline.tier0.document.MRZ_SHAPES` holds for that text's
    shape, or ``None`` for text that is not one of the three.  It is read from
    the first line's own width, because a fixture is asked to draw a page of
    print that is *not* a zone as readily as one that is.

    The remaining fields are the geometry the drawing used, kept so a test can
    say what it measured against.  Frozen, and carrying no method, for the
    reason :class:`~app.pipeline.tier0.mrz_region.MrzComponent` is.
    """

    image: np.ndarray
    lines: tuple
    cells: tuple
    format: str | None
    size: tuple
    cell_px: tuple
    gap: int
    pitch: int
    leading: int
    angle_deg: float
    gain: float
    noise_sigma: float
    shadow_floor: float | None


def _glyph(character):
    """The pattern for ``character``, or the filler's if it is not one.

    The filler is the answer rather than a raise: the page is a fixture, and a
    fixture that stopped drawing over a typo would fail a test about the
    *pipeline* with a message about the fixture.
    """
    return _GLYPHS.get(character, _GLYPHS["<"])


def _scale(pattern, width, height):
    """``pattern`` blown up to a ``(height, width)`` boolean block.

    Every pattern pixel becomes a whole block of the same size, and the block
    sizes are worked out by proportion rather than by division, so a cell that
    is not a multiple of :data:`FONT_WIDTH` by :data:`FONT_HEIGHT` still fills
    its box instead of leaving a bare column.
    """
    columns = (np.arange(width) * FONT_WIDTH) // width
    rows = (np.arange(height) * FONT_HEIGHT) // height
    return np.array(pattern, dtype=bool)[rows][:, columns]


def draw_page(
    lines,
    size=None,
    cell_px=DEFAULT_CELL_PX,
    gap=GAP_PX,
    angle_deg=0.0,
    gain=1.0,
    noise_sigma=0.0,
    shadow_floor=None,
    left=None,
    top=None,
    seed=NOISE_SEED,
):
    """Draw ``lines`` onto a page and say where every character went.

    ``size`` is ``(width, height)`` in pixels, and ``None`` means the page is
    exactly the zone plus :data:`MARGIN` of paper on every side.  ``cell_px``
    is the ``(width, height)`` of one character's box, drawn from
    :data:`DEFAULT_CELL_PX` when it is not given, and ``gap`` is the paper
    after it.  ``angle_deg`` turns the finished page about its centre,
    clockwise positive, and ``0.0`` skips the rotation so an upright page *is*
    the drawn page rather than a resample of it.  ``noise_sigma`` adds sensor
    grain in grey levels from ``seed``, ``gain`` dims the whole frame to that
    fraction of its brightness, and ``shadow_floor`` darkens the right-hand
    edge of the frame to that fraction of the left-hand brightness.  ``left``
    and ``top`` place the zone and default to :data:`MARGIN`.

    A zone that does not fit inside ``size`` is refused rather than clipped,
    because a half-drawn zone reads back as a zone with characters missing
    from it -- a page that would fail a pipeline test for a reason that has
    nothing to do with the pipeline.
    """
    lines = tuple(lines)
    if not lines:
        raise ValueError("a page needs at least one line to draw")

    cell_width, cell_height = cell_px
    pitch = cell_width + gap
    leading = LINE_PITCH_FACTOR * cell_height
    left = MARGIN if left is None else left
    top = MARGIN if top is None else top
    columns = max(len(line) for line in lines)
    if size is None:
        size = (
            left + pitch * (columns - 1) + cell_width + left,
            top + leading * (len(lines) - 1) + cell_height + top,
        )
    width, height = size
    zone = (
        left + pitch * (columns - 1) + cell_width,
        top + leading * (len(lines) - 1) + cell_height,
    )
    if zone[0] > width or zone[1] > height:
        raise ValueError(
            f"a {len(lines)}x{columns} zone needs {zone[0]}x{zone[1]} pixels "
            f"and does not fit a page of {width}x{height}"
        )

    page = np.full((height, width, 3), PAPER_LEVEL, np.uint8)
    cells = []
    for number, line in enumerate(lines):
        row = []
        for index, character in enumerate(line):
            x = left + pitch * index
            y = top + leading * number
            block = _scale(_glyph(character), cell_width, cell_height)
            page[y:y + cell_height, x:x + cell_width][block] = INK_LEVEL
            row.append((x, y, x + cell_width, y + cell_height))
        cells.append(tuple(row))

    if angle_deg:
        matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle_deg, 1.0)
        page = cv2.warpAffine(
            page, matrix, (width, height),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(PAPER_LEVEL, PAPER_LEVEL, PAPER_LEVEL),
        )
    if gain != 1.0:
        page = np.clip(page.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    if shadow_floor is not None:
        ramp = np.linspace(1.0, shadow_floor, width, dtype=np.float32)
        page = np.clip(
            page.astype(np.float32) * ramp[None, :, None], 0, 255
        ).astype(np.uint8)
    if noise_sigma:
        rng = np.random.default_rng(seed)
        page = np.clip(
            page.astype(np.float32)
            + rng.normal(0.0, noise_sigma, page.shape),
            0,
            255,
        ).astype(np.uint8)

    return MrzPage(
        image=page,
        lines=lines,
        cells=tuple(cells),
        format=_format_of(cells),
        size=size,
        cell_px=tuple(cell_px),
        gap=int(gap),
        pitch=pitch,
        leading=leading,
        angle_deg=float(angle_deg),
        gain=float(gain),
        noise_sigma=float(noise_sigma),
        shadow_floor=shadow_floor,
    )


def _format_of(cells):
    """The name in :data:`MRZ_SHAPES` that the drawn cells have the shape of."""
    shape = (len(cells), len(cells[0]))
    return next(
        (name for size, name in document.MRZ_SHAPES.items() if size == shape),
        None,
    )


def render_format(name, lines=None, **kwargs):
    """Draw the zone ``name`` prints, or ``lines`` if the caller brings its own.

    ``name`` is one of the three values
    :data:`~app.pipeline.tier0.document.MRZ_SHAPES` holds, and the shape it is
    checked against is that table's -- a generator that drew a 43-character
    TD3 and then let the detector be blamed for refusing it would be the exact
    mistake this replaces.
    """
    if name not in document.MRZ_SHAPES.values():
        raise ValueError(
            f"{name!r} is not a format this project reads: "
            f"{sorted(document.MRZ_SHAPES.values())}"
        )
    zone = SPECIMENS[name] if lines is None else tuple(lines)
    shape = next(
        shape for shape, value in document.MRZ_SHAPES.items() if value == name
    )
    if (len(zone), len(zone[0])) != shape:
        raise ValueError(
            f"{name} prints {shape[0]} lines of {shape[1]} characters; "
            f"got {len(zone)} of {len(zone[0])}"
        )
    return draw_page(zone, **kwargs)


@functools.lru_cache(maxsize=None)
def _match(pattern):
    """The character whose pattern is nearest ``pattern``.

    Ties go to whichever character :data:`_GLYPHS` reaches first, which is the
    order the table is written in, so the answer does not depend on dict
    iteration or on anything measured.
    """
    best, fewest = "<", None
    for character, glyph in _GLYPHS.items():
        wrong = sum(
            1
            for row in range(FONT_HEIGHT)
            for column in range(FONT_WIDTH)
            if pattern[row][column] is not glyph[row][column]
        )
        if fewest is None or wrong < fewest:
            best, fewest = character, wrong
    return best


def _read_cell(image, box):
    """The character in one cell box of ``image``, read by nearest pattern.

    The cell is resampled down to :data:`FONT_WIDTH` by :data:`FONT_HEIGHT` and
    thresholded halfway between the cell's own darkest and brightest levels, so
    the answer does not depend on how dark the paper is or how far the ink
    sits below it.  That is what lets a dimmed, a shaded and a clean page be
    read by the same function off the same ground truth.
    """
    left, top, right, bottom = box
    patch = image[top:bottom, left:right, 0]
    small = cv2.resize(
        patch, (FONT_WIDTH, FONT_HEIGHT), interpolation=cv2.INTER_AREA
    ).astype(np.float32)
    darkest, brightest = float(small.min()), float(small.max())
    ink = (brightest - small) / max(brightest - darkest, 1e-6)
    pattern = tuple(
        tuple(bool(ink[row, column] >= 0.5) for column in range(FONT_WIDTH))
        for row in range(FONT_HEIGHT)
    )
    return _match(pattern)


def read_zone(page):
    """The characters ``page`` was drawn from, read back out of its pixels.

    One string per drawn line, in the lines' own order, read off
    :attr:`MrzPage.cells`.  This is the *fixture's* reader and not the
    pipeline's: it exists so a test can close the loop from text to image to
    text, and it is deliberately the only place in Part 4 that names a
    character out of a blob.
    """
    return tuple(
        "".join(_read_cell(page.image, box) for box in line) for line in page.cells
    )
