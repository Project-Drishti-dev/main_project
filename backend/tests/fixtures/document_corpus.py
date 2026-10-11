"""A synthetic identity document: printed rows, a correct MRZ, and a field manifest.

:func:`generate` is seeded, never reads the clock, and draws every value from a
pool this module states, so no real identity data can enter the corpus.  The
three document types are the three MRZ formats the project reads -- a passport
is a TD3, a visa a TD2, a national ID a TD1 -- and every line, position and
printed check digit is composed out of the format module that owns it.  Asked
for, it injects the four alterations in :data:`TAMPER_KINDS`, each of which
records the region it changed as ground truth.
"""

import dataclasses
import datetime
import random

import cv2
import numpy as np

from app.pipeline.tier0 import mrz, mrz_region, td1, td2, td3
from tests.fixtures import document_images, mrz_images

__all__ = [
    "BIRTH_YEARS",
    "DEFAULT_SEED",
    "DOCUMENT_NUMBER_DIGITS",
    "DOCUMENT_NUMBER_PREFIX",
    "DOCUMENT_TYPES",
    "EXPIRY_YEARS",
    "GIVEN_NAMES",
    "ISSUING_STATES",
    "MrzField",
    "NATIONALITIES",
    "PORTRAIT_SIZE",
    "ROW_GAP",
    "SEXES",
    "STAMP_SIZE",
    "SURNAMES",
    "SyntheticDocument",
    "TAMPER_KINDS",
    "Tamper",
    "generate",
    "mrz_field",
    "printed_field",
    "read_mrz",
    "tamper",
]

#: The seed :func:`generate` uses when the caller names none.
DEFAULT_SEED = 0

#: Invented surnames, and invented given names.  Nobody bears these; they are
#: tokens that exercise the name field's filler and its ``<<`` separator.
SURNAMES = (
    "TESTHOLDER",
    "SYNTHETIC",
    "SPECIMEN",
    "GROUNDTRUTH",
    "VECTORROW",
)
GIVEN_NAMES = ("ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON")

#: Nationality and issuing-state codes.  ``UTO`` is the code ICAO's own
#: examples print for an unknown state, so it names no country and no person.
NATIONALITIES = ("UTO",)
ISSUING_STATES = ("UTO",)

#: The three sex markers a document of any of these types may print.  The
#: filler is not one of them: a generator that drew it would be printing a
#: field no document in this corpus fills in.
SEXES = ("F", "M", "X")

#: The prefix every generated document number carries, so a generated number
#: is recognisable as generated rather than mistaken for an issued one.  With
#: :data:`DOCUMENT_NUMBER_DIGITS` it fills the nine positions all three formats
#: give a document number exactly.
DOCUMENT_NUMBER_PREFIX = "SYN"
DOCUMENT_NUMBER_DIGITS = 6

#: The years a generated date of birth and date of expiry may fall in.  Both
#: are whole four-digit years, so neither needs a century invented for it.
BIRTH_YEARS = tuple(range(1960, 2001))
EXPIRY_YEARS = tuple(range(2015, 2036))

#: The months as a document prints them, in order.
MONTH_NAMES = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)

#: The paper between one printed row and the next, in pixels.  **This is a
#: detection requirement rather than a look**: the MRZ strip's own line pitch
#: is 42 pixels and ``filter_lines`` keeps any line whose spacing is within a
#: quarter of the tightest spacing on the page, so rows printed closer together
#: than that survive beside the zone and the page then measures as more lines
#: than the format prints.
ROW_GAP = 60

#: The paper between the printed block and the MRZ strip, and the paper around
#: the strip, in pixels.  The strip is placed strictly below the lowest printed
#: row, so it can never cover a field.
MRZ_GAP = 30
MRZ_MARGIN = 40

#: The alterations :func:`generate` injects, in the order it injects them.  Not
#: one of them touches the zone, which is what leaves it the untouched half a
#: forged page disagrees with.
TAMPER_KINDS = (
    "photo_replacement",
    "text_edit",
    "date_of_birth_change",
    "stamp_edit",
)

#: The printed rows an injection edits, keyed by the kind that edits them.  The
#: two kinds absent from this table paste a picture and a stamp rather than
#: editing text, so they have no row to name.
TAMPER_FIELDS = {
    "text_edit": "document_number",
    "date_of_birth_change": "date_of_birth",
}

#: The portrait every generated page carries and an inked stamp, as
#: ``(width, height)`` in pixels, and the paper between the printed block and
#: both.  Both are drawn beside the block and above the strip, so an injection
#: into either can neither cover a printed row nor move what the zone reads.
PORTRAIT_SIZE = (160, 200)
STAMP_SIZE = (180, 90)
PORTRAIT_GAP = 60

#: How far a replacement portrait's head may move from :data:`PORTRAIT`'s, as a
#: fraction of the portrait's width, and how much darker its paper may be.
PORTRAIT_SHIFT = 0.18
PORTRAIT_TONES = (25, 50)

#: What a stamp is drawn in, in grey levels, and how thick its ring is.
#: **A stamp is inked marks and no text**: 4.4 measures a line by glyph height,
#: so a stamp carrying letters at a legible size would be measured as a line of
#: the zone beside it.
STAMP_INK_LEVEL = 60
STAMP_THICKNESS = 3

#: The angles a stamp is pasted at, in degrees, clockwise as ``cv2`` counts.
STAMP_ANGLES = (0, 8, -8, 16, -16)


@dataclasses.dataclass(frozen=True)
class MrzField:
    """One MRZ field: its name, its characters, and the box they are printed in.

    ``line_number`` is the number the standard gives the line, and ``box`` is
    the union of that field's own cells in page coordinates, half-open.
    """

    name: str
    value: str
    line_number: int
    box: tuple


@dataclasses.dataclass(frozen=True)
class Tamper:
    """One injected alteration: its kind, the row it edited, and its region.

    ``box`` is the tight half-open box of the pixels the injection changed,
    measured off the two draws.  ``original`` and ``replacement`` are the text
    before and after, ``None`` where an injection pastes a picture or a stamp
    instead of editing text, and so is ``field``.
    """

    kind: str
    field: str | None
    box: tuple
    original: str | None
    replacement: str | None


@dataclasses.dataclass(frozen=True)
class SyntheticDocument:
    """One drawn document page and the ground truth it was drawn from.

    ``image`` is a three-channel BGR ``uint8`` frame of ``size``, ``printed``
    is one :class:`~tests.fixtures.document_images.PrintedField` per printed
    row, ``mrz`` is one :class:`MrzField` per MRZ field in printed order,
    ``mrz_lines`` is the text the zone prints and ``cells`` is every drawn
    character cell in page coordinates.  ``portrait`` is where the page's photo
    was printed and ``tampering`` is one :class:`Tamper` per injection, in the
    order they were injected.  Frozen, like the records it is built from.
    """

    image: np.ndarray
    size: tuple
    printed: tuple
    mrz: tuple
    mrz_lines: tuple
    cells: tuple
    seed: int
    format: str
    document_type: str
    portrait: tuple
    tampering: tuple


@dataclasses.dataclass(frozen=True)
class _Portrait:
    """One drawn portrait: its own paper, a head and shoulders.

    ``centre`` and ``radius`` are fractions of the portrait's own width and
    height, and the three levels are the paper, the head and the shoulders.
    """

    centre: tuple
    radius: float
    photo_level: int
    head_level: int
    shoulder_level: int


#: The portrait every generated page carries.  Every page carries this one at
#: these levels, so a replaced photo is provably a different picture rather than
#: a second draw of the same one.
PORTRAIT = _Portrait(
    centre=(0.5, 0.42), radius=0.26, photo_level=205, head_level=150, shoulder_level=90
)


@dataclasses.dataclass(frozen=True)
class _Identity:
    """The one holder :func:`generate` invents, before anything is drawn."""

    surname: str
    given_names: tuple
    document_number: str
    nationality: str
    issuing_state: str
    sex: str
    date_of_birth: datetime.date
    date_of_expiry: datetime.date


@dataclasses.dataclass(frozen=True)
class _Carrier:
    """What :func:`read_mrz` hands ``mrz_images.read_zone``: an image and cells."""

    image: np.ndarray
    cells: tuple


@dataclasses.dataclass(frozen=True)
class _Format:
    """One document type: the MRZ format it carries and the rows its page prints.

    ``layout`` is the format module's own per-line table and every position is
    read out of it, so a position corrected there is corrected here.
    ``check_digit_fields`` is that module's own printed-digit table and
    ``field`` its own field reader, resolved at import rather than reached by
    string.  ``document_code`` is the only claim here that no table in the
    project makes, because what a document *is* is not a position.
    """

    name: str
    layout: dict
    document_code: str
    field: object
    check_digit_fields: tuple
    composite: object
    rows: object

    @property
    def line_count(self):
        """How many lines the format prints, read out of its own layout."""
        return len(self.layout)

    @property
    def line_length(self):
        """How wide a line is, read out of its own layout's last position."""
        return max(last for spans in self.layout.values() for _, last in spans.values())

    def span(self, name):
        """The line number and that line's layout printing ``name``, or raise."""
        for number, spans in enumerate(self.layout.values(), start=1):
            if name in spans:
                return number, spans
        printed = [field for spans in self.layout.values() for field in spans]
        raise KeyError(f"{self.name} prints no field named {name!r}: {printed}")


def _td1_composite(zone):
    """The 51 characters a TD1's printed composite digit is computed over."""
    return td1.td1_composite_input(zone[0], zone[1])


def _td2_composite(zone):
    """The 62 characters a TD2's printed composite digit is computed over."""
    return td2.td2_composite_input(zone[0], zone[1])


def _td3_composite(zone):
    """A TD3's printed composite digit is computed over its line 2 alone."""
    return td3.td3_composite_input(zone[1])


def _passport_rows(identity):
    """The rows a passport data page prints, in printed order."""
    return (
        ("surname", "Surname", identity.surname),
        ("given_names", "Given names", " ".join(identity.given_names)),
        ("document_number", "Passport No", identity.document_number),
        ("nationality", "Nationality", identity.nationality),
        ("date_of_birth", "Date of birth", _printed_date(identity.date_of_birth)),
        ("sex", "Sex", identity.sex),
        ("date_of_expiry", "Date of expiry", _printed_date(identity.date_of_expiry)),
    )


def _visa_rows(identity):
    """The rows a visa page prints: a passport's rows, numbered as a visa."""
    return tuple(
        (name, "Visa No" if name == "document_number" else label, value)
        for name, label, value in _passport_rows(identity)
    )


def _national_id_rows(identity):
    """The rows a national ID prints: a passport's rows, numbered as an ID."""
    return tuple(
        (name, "ID No" if name == "document_number" else label, value)
        for name, label, value in _passport_rows(identity)
    )


#: Every document type this generator draws, keyed by the name a caller asks
#: for and holding the MRZ format that type carries.  The values are the three
#: keys :data:`~app.pipeline.tier0.mrz_region.MRZ_LAYOUTS` is keyed by, so a
#: fourth format added there is a fourth row here rather than a silent absence.
DOCUMENT_TYPES = {
    "passport": "TD3",
    "visa": "TD2",
    "national_id": "TD1",
}

_FORMATS = {
    "passport": _Format(
        name="TD3",
        layout=td3.TD3,
        document_code="P<",
        field=td3.td3_field,
        check_digit_fields=td3.TD3_CHECK_DIGIT_FIELDS,
        composite=_td3_composite,
        rows=_passport_rows,
    ),
    "visa": _Format(
        name="TD2",
        layout=td2.TD2,
        document_code="V<",
        field=td2.td2_field,
        check_digit_fields=td2.TD2_CHECK_DIGIT_FIELDS,
        composite=_td2_composite,
        rows=_visa_rows,
    ),
    "national_id": _Format(
        name="TD1",
        layout=td1.TD1,
        document_code="I<",
        field=td1.td1_field,
        check_digit_fields=td1.TD1_CHECK_DIGIT_FIELDS,
        composite=_td1_composite,
        rows=_national_id_rows,
    ),
}


def _union(boxes):
    """The half-open box enclosing ``boxes``."""
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _printed_date(day):
    """``day`` as a document prints it, as ``12 AUG 1974``."""
    return f"{day.day:02d} {MONTH_NAMES[day.month - 1]} {day.year}"


def _printed_day(text):
    """The day ``text`` prints, read back through this module's own months."""
    day, month, year = text.split()
    return datetime.date(int(year), MONTH_NAMES.index(month) + 1, int(day))


def _day(rng, years):
    """A day in one of ``years``.  The day is never above 28, so printing it
    needs no month length and no leap year."""
    return datetime.date(rng.choice(years), rng.randint(1, 12), rng.randint(1, 28))


def _number(rng):
    """A document number: the prefix that marks it generated, then the digits."""
    return DOCUMENT_NUMBER_PREFIX + "".join(
        str(rng.randrange(10)) for _ in range(DOCUMENT_NUMBER_DIGITS)
    )


def _another_number(rng, number):
    """A generated number that is not ``number``.

    Drawn from the same pool, and a draw equal to ``number`` has its last digit
    stepped, so the answer is never the number printed and the loop cannot spin.
    """
    other = _number(rng)
    if other != number:
        return other
    return other[:-1] + str((int(other[-1]) + 1) % 10)


def _another_day(rng, day, years):
    """A day in ``years`` whose year is not ``day``'s, so it is never ``day``."""
    others = tuple(year for year in years if year != day.year)
    if not others:
        raise ValueError(f"{day.year} is the only year this window allows")
    return datetime.date(rng.choice(others), rng.randint(1, 12), rng.randint(1, 28))


def _identity(seed):
    """Invent one holder from ``seed``.  The only place randomness enters."""
    rng = random.Random(seed)
    return _Identity(
        surname=rng.choice(SURNAMES),
        given_names=tuple(rng.sample(GIVEN_NAMES, rng.choice((1, 2)))),
        document_number=_number(rng),
        nationality=rng.choice(NATIONALITIES),
        issuing_state=rng.choice(ISSUING_STATES),
        sex=rng.choice(SEXES),
        date_of_birth=_day(rng, BIRTH_YEARS),
        date_of_expiry=_day(rng, EXPIRY_YEARS),
    )


def _format_of(document_type):
    """The format record ``document_type`` is drawn with, or raise."""
    if document_type not in _FORMATS:
        raise KeyError(
            f"{document_type!r} is not a document this generator draws: "
            f"{sorted(_FORMATS)}"
        )
    return _FORMATS[document_type]


def _place(buffer, layout, name, value):
    """Write ``value`` into ``buffer`` at ``name``'s span in ``layout``.

    The span is read from ``layout`` and the buffer starts as filler, so a value
    shorter than its field is padded by the buffer and by nothing else.  A value
    too long is refused rather than truncated: half a field is a misread field.
    """
    first, last = layout[name]
    if len(value) > last - first + 1:
        raise ValueError(
            f"{name} needs {len(value)} characters and the field is "
            f"{last - first + 1} wide"
        )
    for offset, character in enumerate(value):
        buffer[first - 1 + offset] = character


def _placed(form, identity):
    """The values ``form`` prints besides its check digits, as line and name.

    The eight fields the three layouts hold between them, each placed on the
    line its own layout gives it -- which is why a TD1's name lands on its line
    3 without this function naming a line.  A field a format does not print,
    and the optional data a format prints where this generator prints nothing,
    is left as the filler the buffer started as.
    """
    printed = {field for spans in form.layout.values() for field in spans}
    values = (
        ("document_code", form.document_code),
        ("issuing_state", identity.issuing_state),
        ("name", identity.surname + "<<" + mrz.FILLER.join(identity.given_names)),
        ("document_number", identity.document_number),
        ("nationality", identity.nationality),
        ("date_of_birth", identity.date_of_birth.strftime("%y%m%d")),
        ("sex", identity.sex),
        ("date_of_expiry", identity.date_of_expiry.strftime("%y%m%d")),
    )
    return tuple(
        (form.span(name)[0], name, value)
        for name, value in values
        if name in printed
    )


def _zone(form, identity):
    """The lines ``form`` prints for ``identity``, in printed order.

    Every printed check digit is placed by name from the format module's own
    table, and the characters it is computed over are read back out of the
    buffers through the layout, so no position and no pairing is stated here.
    The composite is placed last because the standard's own table lists it
    last: its characters are the four digits printed before it.
    """
    buffers = [[mrz.FILLER] * form.line_length for _ in range(form.line_count)]
    for number, name, value in _placed(form, identity):
        _place(buffers[number - 1], form.layout[f"line_{number}"], name, value)
    for label, source, digit_field in form.check_digit_fields:
        zone = tuple("".join(buffer) for buffer in buffers)
        if source is None:
            characters = form.composite(zone)
        else:
            number, layout = form.span(source)
            characters = form.field(zone[number - 1], layout, source)
        number, layout = form.span(digit_field)
        _place(
            buffers[number - 1],
            layout,
            digit_field,
            str(mrz.check_digit(characters)),
        )
    return tuple("".join(buffer) for buffer in buffers)


def _mrz_fields(form, lines, cells):
    """One :class:`MrzField` per MRZ field, in printed order, off the drawn cells.

    Which field a cell prints is asked of
    :func:`~app.pipeline.tier0.mrz_region.cell_field`, so the manifest cannot
    name a field the layout does not print, and a cell that prints no field is
    refused rather than dropped -- a cell nobody can account for is a manifest
    short by one field.
    """
    found = {}
    for number, (line, row) in enumerate(zip(lines, cells), start=1):
        layout = form.layout[f"line_{number}"]
        for index, box in enumerate(row):
            owner = mrz_region.cell_field(form.name, number, index)
            if owner is None:
                raise ValueError(f"cell {index} of MRZ line {number} prints no field")
            name = owner[0]
            if name not in found:
                found[name] = (form.field(line, layout, name), number, [])
            found[name][2].append(box)
    return tuple(
        MrzField(name, value, number, _union(boxes))
        for name, (value, number, boxes) in found.items()
    )


def _box(left, top, size):
    """The half-open box of ``size`` -- ``(width, height)`` -- at ``(left, top)``."""
    return (int(left), int(top), int(left + size[0]), int(top + size[1]))


def _grey(level):
    """``level`` in all three channels, so a mark leaves a frame greyscale."""
    return (level, level, level)


def _band(fields):
    """The top, right and bottom of the block ``fields`` were printed in."""
    boxes = [box for field in fields for box in (field.label_box, field.value_box)]
    return (
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _changed(before, after):
    """The tight half-open box of the pixels ``before`` and ``after`` disagree on.

    Measured off the two draws, so a recorded region is where an injection put
    ink rather than where it meant to.  An injection that changed nothing is
    refused, because a region bounding no pixel would satisfy "a region for
    every injection" vacuously.
    """
    marked = np.any(before != after, axis=2)
    if not marked.any():
        raise ValueError("this injection changed no pixel")
    rows = np.flatnonzero(marked.any(axis=1))
    columns = np.flatnonzero(marked.any(axis=0))
    return (int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1)


def _free_boxes(fields):
    """The portrait's box and the stamp's box, both beside the printed block.

    The portrait stands at the block's head and the stamp at its foot, both to
    the right of the widest printed box and both above the strip -- which is
    placed below the lowest printed row -- so neither can cover a printed row
    and neither can change what the zone reads.
    """
    top, right, bottom = _band(fields)
    return (
        _box(right + PORTRAIT_GAP, top, PORTRAIT_SIZE),
        _box(right + PORTRAIT_GAP, bottom - STAMP_SIZE[1], STAMP_SIZE),
    )


def _draw_portrait(image, box, portrait):
    """Draw ``portrait`` in its own frame of ``box``'s size and paste that in.

    The frame is the box's own size and the box is filled before anything is
    drawn in it, so a replacement covers the photo it replaces and neither can
    paint outside the region the manifest records.
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    frame = np.full((height, width, 3), portrait.photo_level, np.uint8)
    cv2.ellipse(
        frame, (width // 2, height), (int(0.62 * width), int(0.55 * height)),
        0, 0, 360, _grey(portrait.shoulder_level), -1, cv2.LINE_8,
    )
    cv2.circle(
        frame,
        (int(portrait.centre[0] * width), int(portrait.centre[1] * height)),
        int(portrait.radius * width), _grey(portrait.head_level), -1, cv2.LINE_8,
    )
    image[top:bottom, left:right] = frame


def _draw_stamp(image, box, angle_deg):
    """An inked ring and its boss, turned ``angle_deg``, pasted over ``box``.

    The box's own pixels are the frame's paper, so whatever the stamp is pasted
    over stays where it was and only the ink is new.
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    frame = image[top:bottom, left:right].copy()
    for scale in (0.46, 0.24):
        cv2.ellipse(
            frame, (width // 2, height // 2), (int(scale * width), int(scale * height)),
            angle_deg, 0, 360, _grey(STAMP_INK_LEVEL), STAMP_THICKNESS, cv2.LINE_8,
        )
    image[top:bottom, left:right] = frame


def _compose(form, lines, page, strip, seed, document_type):
    """The printed block, the zone and the portrait on one frame, and its manifest.

    The portrait's and the stamp's boxes are reserved whether or not either is
    drawn, so injecting either adds ink inside a frame whose geometry an
    untampered document of the same seed already has.
    """
    portrait, stamp = _free_boxes(page.fields)
    bottom = max(box[3] for field in page.fields for box in (field.label_box, field.value_box))
    top = bottom + MRZ_GAP
    margin = document_images.MARGIN
    width = max(
        page.size[0],
        strip.size[0] + 2 * MRZ_MARGIN,
        portrait[2] + margin,
        stamp[2] + margin,
    )
    height = max(
        page.size[1],
        top + strip.size[1] + MRZ_MARGIN,
        portrait[3] + margin,
        stamp[3] + margin,
    )
    left = (width - strip.size[0]) // 2

    image = np.full((height, width, 3), document_images.PAPER_LEVEL, np.uint8)
    image[:page.size[1], :page.size[0]] = page.image
    image[top:top + strip.size[1], left:left + strip.size[0]] = strip.image
    cells = tuple(
        tuple(
            (x + left, y + top, right + left, bottom + top)
            for x, y, right, bottom in row
        )
        for row in strip.cells
    )
    _draw_portrait(image, portrait, PORTRAIT)

    return SyntheticDocument(
        image=image,
        size=(width, height),
        printed=page.fields,
        mrz=_mrz_fields(form, lines, cells),
        mrz_lines=lines,
        cells=cells,
        seed=seed,
        format=form.name,
        document_type=document_type,
        portrait=portrait,
        tampering=(),
    )


def _injected(document, image, injection):
    """``document`` drawn as ``image``, with ``injection`` appended to its manifest."""
    return dataclasses.replace(
        document, image=image, tampering=document.tampering + (injection,)
    )


def _requested(tampers):
    """The kinds ``tampers`` names, each known and named at most once.

    A kind named twice is refused rather than injected twice: one page carries
    one photo and one stamp, and two records for the same region would make
    "a region for every injection" true of an injection that did not happen.
    """
    kinds = tuple(tampers)
    unknown = [kind for kind in kinds if kind not in TAMPER_KINDS]
    if unknown:
        raise KeyError(
            f"{unknown[0]!r} is not a tamper this generator injects: "
            f"{list(TAMPER_KINDS)}"
        )
    repeated = sorted({kind for kind in kinds if kinds.count(kind) > 1})
    if repeated:
        raise ValueError(
            f"{repeated[0]!r} was asked for twice; a page carries one of each"
        )
    return kinds


def _rng(seed, kind):
    """The generator ``kind``'s own randomness is drawn from.

    Seeded by an integer, because a string seed of :class:`random.Random` is
    hashed in a way that differs between interpreter versions and a corpus whose
    tampering moved with the interpreter is not a corpus.
    """
    return random.Random((seed + 1) * len(TAMPER_KINDS) + TAMPER_KINDS.index(kind))


def _another_portrait(rng):
    """A portrait other than :data:`PORTRAIT`: its head moved, its paper darker."""
    return _Portrait(
        centre=tuple(
            value + rng.choice((-PORTRAIT_SHIFT, PORTRAIT_SHIFT))
            for value in PORTRAIT.centre
        ),
        radius=PORTRAIT.radius,
        photo_level=PORTRAIT.photo_level - rng.choice(PORTRAIT_TONES),
        head_level=PORTRAIT.head_level,
        shoulder_level=PORTRAIT.shoulder_level,
    )


def _replace_photo(document, rng):
    """A second portrait pasted over the portrait the page printed."""
    image = document.image.copy()
    _draw_portrait(image, document.portrait, _another_portrait(rng))

    return _injected(
        document,
        image,
        Tamper(
            "photo_replacement", None, _changed(document.image, image), None, None
        ),
    )


def _reprinted(document, kind, name, value):
    """The document with printed row ``name`` printed again as ``value``.

    The printed block is drawn again rather than painted over, because the
    drawing is what says where the new text went: the manifest then describes
    the pixels instead of an intention.  The rows come from the document's own
    printed values rather than from the holder, so a second injection composes
    with the first instead of undoing it.  The band repainted encloses the old
    and the new boxes both, so no ink of the text being replaced is left behind.
    """
    rows = tuple(
        (field.name, field.label, value if field.name == name else field.value)
        for field in document.printed
    )
    page = document_images.draw_document(rows, size=document.size, row_gap=ROW_GAP)
    old, new = _band(document.printed), _band(page.fields)
    top, right, bottom = min(old[0], new[0]), max(old[1], new[1]), max(old[2], new[2])
    image = document.image.copy()
    image[top:bottom, :right] = page.image[top:bottom, :right]

    box = document_images.field_of(page, name).value_box
    printed = tuple(
        dataclasses.replace(field, value=value, value_box=box)
        if field.name == name
        else field
        for field in document.printed
    )
    injection = Tamper(
        kind, name, _changed(document.image, image),
        printed_field(document, name).value, value,
    )
    return _injected(dataclasses.replace(document, printed=printed), image, injection)


def _edit_text(document, rng):
    """The document number printed again, as another generated number."""
    name = TAMPER_FIELDS["text_edit"]
    return _reprinted(
        document, "text_edit", name,
        _another_number(rng, printed_field(document, name).value),
    )


def _change_birth_date(document, rng):
    """The date of birth printed again, as another day in the stated years."""
    name = TAMPER_FIELDS["date_of_birth_change"]
    printed = printed_field(document, name).value
    return _reprinted(
        document, "date_of_birth_change", name,
        _printed_date(_another_day(rng, _printed_day(printed), BIRTH_YEARS)),
    )


def _edit_stamp(document, rng):
    """An inked stamp pasted on the paper beside the printed block."""
    image = document.image.copy()
    _draw_stamp(image, _free_boxes(document.printed)[1], rng.choice(STAMP_ANGLES))

    return _injected(
        document, image, Tamper("stamp_edit", None, _changed(document.image, image), None, None)
    )


#: The function injecting each kind, keyed by the kind's own name, so a caller
#: naming a kind this module does not hold is refused rather than quietly given
#: whichever function is written last here.
_INJECTORS = {
    "photo_replacement": _replace_photo,
    "text_edit": _edit_text,
    "date_of_birth_change": _change_birth_date,
    "stamp_edit": _edit_stamp,
}


def generate(
    seed=DEFAULT_SEED,
    document_type="passport",
    size=document_images.PAGE_SIZE,
    tampers=(),
):
    """Draw one synthetic document, tampered as asked, with its field manifest.

    ``seed`` picks the document and the same seed always draws the same one;
    ``document_type`` is one key of :data:`DOCUMENT_TYPES`; ``size`` is the
    ``(width, height)`` asked for, and the page grows when the printed block,
    the portrait and the strip do not all fit it, so nothing is clipped.
    ``tampers`` names alterations out of :data:`TAMPER_KINDS`, injected in that
    order once the page is drawn; neither the page's size nor its zone depends
    on what was injected.

    Raises:
        KeyError: for a document type or a tamper this generator does not draw.
        ValueError: if the printed rows do not fit ``size``, which
            :func:`~tests.fixtures.document_images.draw_document` refuses, if a
            kind is named twice, or an injection changed no pixel.
    """
    form = _format_of(document_type)
    identity = _identity(seed)
    lines = _zone(form, identity)
    page = document_images.draw_document(form.rows(identity), size=size, row_gap=ROW_GAP)
    strip = mrz_images.draw_page(lines, left=0, top=0)
    document = _compose(form, lines, page, strip, seed, document_type)

    for kind in _requested(tampers):
        document = _INJECTORS[kind](document, _rng(seed, kind))
    return document


def read_mrz(document):
    """The MRZ lines, read out of ``document``'s own pixels.

    The characters come from the frame and the boxes are this module's ground
    truth, which is how Part 4's fixture closes a loop from text to image to
    text; :func:`~app.pipeline.tier0.mrz_region.detect_mrz` is what proves the
    zone is in those pixels at all, and nothing else in this project reads a
    character out of a cell.
    """
    return mrz_images.read_zone(_Carrier(document.image, document.cells))


def printed_field(document, name):
    """The printed row ``name``, read off the page's own description."""
    for field in document.printed:
        if field.name == name:
            return field
    printed = [field.name for field in document.printed]
    raise KeyError(f"this page prints no field named {name!r}: {printed}")


def tamper(document, kind):
    """The injection of ``kind`` this document carries, or raise.

    ``KeyError`` names the kinds the manifest does hold, which is a different
    list from :data:`TAMPER_KINDS`: what a document was tampered with is a fact
    about that document.
    """
    for injection in document.tampering:
        if injection.kind == kind:
            return injection
    carried = [injection.kind for injection in document.tampering]
    raise KeyError(f"this document carries no {kind!r} injection: {carried}")


def mrz_field(document, name):
    """The MRZ field ``name``, read off the manifest's own description."""
    for field in document.mrz:
        if field.name == name:
            return field
    printed = [field.name for field in document.mrz]
    raise KeyError(f"this document's MRZ prints no field named {name!r}: {printed}")
