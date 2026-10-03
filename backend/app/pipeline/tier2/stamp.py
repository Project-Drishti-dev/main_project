"""Stamp detection and template matching: find the ink, then say which mark it is.

:func:`find_stamps` proposes where chromatic ink sits on a capture, and
:func:`detect_stamps` names each proposal by comparing it against the committed
templates on one canonical grid, so a stamp printed at any size is read the
same way.  **Every template this repository ships is drawn by this
repository**; no authority's mark is committed, so this names its own artwork
and nothing else.  D120 holds the argument and the measured constants.

A registry holding no template answers :data:`NOT_CONFIGURED` rather than an
empty match list, so an absent capability is never read as a page with nothing
on it.  D121 holds that answer.
"""

import dataclasses
import numbers
import types
import typing

import cv2
import numpy as np

from app.pipeline.tier2 import base

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "CANONICAL",
    "CHROMA_LEVEL",
    "CLOSE",
    "MATCHED",
    "MATCH_LEVEL",
    "MIN_INK",
    "MIN_SIDE",
    "MODEL_VERSION",
    "MODULE_NAME",
    "NO_MATCH",
    "NOT_CONFIGURED",
    "QUALITY",
    "STAMP_TEMPLATES",
    "STATUSES",
    "TEMPLATE_NAMES",
    "StampCandidate",
    "StampDetection",
    "StampError",
    "StampMatch",
    "StampModule",
    "StampTemplate",
    "chroma",
    "detect_stamps",
    "find_stamps",
    "ink_extent",
    "ink_mask",
    "make_template",
    "match_score",
    "region_polygons",
    "to_color",
]

#: The name this module answers under, and the one its flag is traced to;
#: ``TAMPER_STAMP_ANOMALY`` in the shipped weightset carries its weight.
MODULE_NAME = "tamper_stamp"

#: What produced an answer: this rule's own version, to be bumped when it moves.
MODEL_VERSION = "stamp-v0"

#: The quality the shipped templates are authored at, so a committed template
#: carries codec artefacts the way any reprinted mark does.  D120.
QUALITY = 95

#: The chroma a pixel needs before it is called ink.  Measured: a colour
#: photograph reaches 94 and a grayscale page reaches none, and this line sits
#: above the photograph and well below the stamp ink's 148.  D120.
CHROMA_LEVEL = 55

#: The side of the elliptical kernel that closes the ink mask, joining a ring,
#: a star and its lettering into one component instead of three.  D120.
CLOSE = 15

#: The ink a component needs before it is offered as a stamp.  Measured, D120.
MIN_INK = 1000

#: The shorter side a component needs before it is offered.  A candidate
#: narrower than this has too few pixels for the canonical grid to mean
#: anything, so it is not proposed rather than proposed and refused.
MIN_SIDE = 40

#: The side both the candidate and the template are resampled to, which is what
#: makes the comparison independent of the size the stamp was printed at.
CANONICAL = 64

#: The correlation at or above which a proposal is called the template it best
#: matches.  Measured, D120.
MATCH_LEVEL = 0.75

#: At least one proposal was explained by a committed template.
MATCHED = "matched"

#: Every proposal was compared and none was explained.  A measurement of this
#: comparison and not a verdict on the document.  D121.
NO_MATCH = "no_match"

#: The registry held no template, so **nothing was compared at all**.  An
#: absent capability rather than a quiet result, and reported as its own answer
#: so it cannot be read as :data:`NO_MATCH`.  D121.
NOT_CONFIGURED = "not_configured"

#: Every status a :class:`StampDetection` may carry.  **There is deliberately
#: no ``clean`` among them**, since this module's silence is a measurement of
#: its own registry and not a statement about the page.  D121.
STATUSES = (MATCHED, NO_MATCH, NOT_CONFIGURED)


class StampError(ValueError):
    """Raised when a frame cannot be measured, or an argument is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps
    working.  A frame stamp matching cannot read is refused rather than
    answered as a page with no stamp on it, per D115's rule.
    """


def _check_positive(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a real number above zero."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise StampError(f"{field} must be a real number")
    if not float(value) > 0:
        raise StampError(f"{field} must be above zero")


def _check_whole(value: object, field: str) -> None:
    """Refuse ``value`` unless it is a positive whole number of pixels."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise StampError(f"{field} must be a whole number of pixels")
    if value < 1:
        raise StampError(f"{field} must be at least one pixel")


def to_color(image: object) -> np.ndarray:
    """Return ``image`` as the colour plane stamp matching measures.

    :returns: a three-channel 8-bit ``numpy`` array, alpha dropped.
    :raises StampError: unless the frame is a non-empty 8-bit colour array,
        since this module reads chromatic ink and a grayscale frame carries
        none to read.
    """
    if not isinstance(image, np.ndarray):
        raise StampError("image must be a numpy array")
    if image.dtype != np.uint8:
        raise StampError("image must hold 8-bit pixels")
    if image.ndim != 3:
        raise StampError("image must be three dimensional: stamp matching reads colour")
    channels = image.shape[2]
    if channels not in (3, 4):
        raise StampError("image must hold three or four channels")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise StampError("image must hold at least one pixel")
    return image[:, :, :3] if channels == 3 else image[:, :, :3].copy()


def chroma(image: object) -> np.ndarray:
    """Return ``image``'s per-pixel spread across the colour channels.

    :returns: one non-negative ``float64`` per pixel, in the frame's order.
    :raises StampError: on a frame :func:`to_color` refuses.
    """
    picture = to_color(image)
    planes = [picture[:, :, index].astype(np.float64) for index in range(3)]
    highest = np.maximum(np.maximum(planes[0], planes[1]), planes[2])
    lowest = np.minimum(np.minimum(planes[0], planes[1]), planes[2])
    return highest - lowest


def ink_mask(image: object, *, level: float = CHROMA_LEVEL, close: int = CLOSE) -> np.ndarray:
    """Return the frame's ink as a binary mask, one byte per pixel.

    :param level: the chroma at which a pixel is called ink.
    :param close: the side of the elliptical kernel that closes the mask.
    :returns: a ``uint8`` mask holding 1 for ink and 0 for paper.
    :raises StampError: on a level outside ``[0, 255]``, a close that is not a
        positive odd number of pixels, or a frame :func:`to_color` refuses.
    """
    if isinstance(level, bool) or not isinstance(level, numbers.Real):
        raise StampError("level must be a real number")
    if not 0.0 <= float(level) <= 255.0:
        raise StampError("level must sit in [0, 255]")
    if isinstance(close, bool) or not isinstance(close, int):
        raise StampError("close must be a whole number of pixels")
    if close < 1 or close % 2 == 0:
        raise StampError("close must be an odd number of at least one pixel")
    mask = (chroma(image) >= float(level)).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _canonical(patch: np.ndarray) -> np.ndarray:
    """Return ``patch`` resampled onto the one grid every comparison is made on."""
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.resize(
        gray, (CANONICAL, CANONICAL), interpolation=cv2.INTER_AREA
    ).astype(np.float32)


@dataclasses.dataclass(frozen=True)
class StampTemplate:
    """One committed mark: the image, and the one grid it is compared on.

    ``image`` is cropped to the ink on it and held read-only, so a template is
    the mark rather than the sheet it was drawn on.  ``canonical`` is derived
    once at construction rather than per comparison, and both arrays are frozen
    because a registry nobody may edit is the whole of a registry.
    """

    #: The name a match is reported under and a caller looks the template up by.
    name: str

    #: The mark itself: a read-only colour array cropped to its own ink.
    image: np.ndarray

    #: The mark resampled to :data:`CANONICAL` squared, derived at construction.
    canonical: np.ndarray = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Refuse a template that is not a named mark carrying findable ink."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise StampError("a template needs a name")
        picture = to_color(self.image)
        _check_whole(int(picture.shape[0]), "template height")
        _check_whole(int(picture.shape[1]), "template width")
        if not float(chroma(picture).max()) >= CHROMA_LEVEL:
            raise StampError("a template carries no ink this module could find")
        picture = picture.copy()
        picture.flags.writeable = False
        object.__setattr__(self, "image", picture)
        canonical = _canonical(picture)
        canonical.flags.writeable = False
        object.__setattr__(self, "canonical", canonical)

    @property
    def size(self) -> tuple[int, int]:
        """The template's own ``(width, height)`` in pixels, as whole numbers."""
        return (int(self.image.shape[1]), int(self.image.shape[0]))


def ink_extent(image: object, *, level: float = CHROMA_LEVEL) -> tuple[int, int, int, int]:
    """Return the ``(x, y, width, height)`` box of ``image``'s own ink.

    The extent is read off the raw ink and not off :func:`ink_mask`, because
    the mask closes the ink and a candidate is measured on what closed.  A
    template cropped to a closed mask would carry a border the candidate it is
    compared against does not, and the two would sit on the grid differently.

    :raises StampError: on a level outside ``[0, 255]``, a frame with no ink
        at that level, or one :func:`to_color` refuses.
    """
    if isinstance(level, bool) or not isinstance(level, numbers.Real):
        raise StampError("level must be a real number")
    if not 0.0 <= float(level) <= 255.0:
        raise StampError("level must sit in [0, 255]")
    rows, columns = np.nonzero(chroma(image) >= float(level))
    if not len(columns):
        raise StampError("the image carries no ink at that level")
    left, right = int(columns.min()), int(columns.max())
    top, bottom = int(rows.min()), int(rows.max())
    return (left, top, right - left + 1, bottom - top + 1)


def make_template(name: str, image: object) -> StampTemplate:
    """Return the mark on ``image``, cropped to its ink, under ``name``.

    :raises StampError: on an unnamed template, or one carrying no ink at or
        above :data:`CHROMA_LEVEL`, which would match nothing by construction.
    """
    picture = to_color(image)
    x, y, width, height = ink_extent(picture)
    return StampTemplate(name=name, image=picture[y : y + height, x : x + width])


@dataclasses.dataclass(frozen=True)
class StampCandidate:
    """Where the detector proposed ink: a whole-pixel box and the ink in it.

    ``box`` is ``(x, y, width, height)`` in the frame's own pixels and is the
    closed component's box, so it can be a little wider than the ink that
    produced it.  A candidate is a proposal and not a finding: nothing has
    compared it to a template yet.
    """

    box: tuple[int, int, int, int]
    ink: int

    def __post_init__(self) -> None:
        """Refuse a candidate that is not a whole-pixel box with ink in it."""
        box = self.box
        if not isinstance(box, tuple) or len(box) != 4:
            raise StampError("a candidate box must be an (x, y, width, height) tuple")
        if not all(isinstance(part, int) and not isinstance(part, bool) for part in box):
            raise StampError("a candidate box must hold whole pixels")
        if box[2] < 1 or box[3] < 1 or box[0] < 0 or box[1] < 0:
            raise StampError("a candidate box must hold a positive area on the page")
        if isinstance(self.ink, bool) or not isinstance(self.ink, int) or self.ink < 0:
            raise StampError("ink must be a whole number of pixels")


@dataclasses.dataclass(frozen=True)
class StampMatch:
    """One proposal that cleared :data:`MATCH_LEVEL` against one template.

    ``score`` is the correlation and not a probability the mark is genuine, and
    ``template`` names which committed template won rather than that anything
    is authentic.  Only a caller holding a registry of real marks can say the
    second, and none is committed here.
    """

    #: The name of the committed template this proposal matched.
    template: str

    #: The correlation at which it matched, in ``[0, 1]``.
    score: float

    #: The whole-pixel box the proposal was made on.
    box: tuple[int, int, int, int]

    def __post_init__(self) -> None:
        """Refuse a match that is not a named template at a real correlation."""
        if not isinstance(self.template, str) or not self.template.strip():
            raise StampError("a match must name its template")
        if isinstance(self.score, bool) or not isinstance(self.score, numbers.Real):
            raise StampError("score must be a real number")
        if not 0.0 <= float(self.score) <= 1.0:
            raise StampError("score must sit in [0, 1]")
        StampCandidate(box=self.box, ink=0)


@dataclasses.dataclass(frozen=True)
class StampDetection:
    """What one pass over a page answered: a status, and what it named.

    ``status`` is the whole point: an empty ``matches`` is this module's own
    measurement under :data:`NO_MATCH` and an absent capability under
    :data:`NOT_CONFIGURED`, and a bare match list cannot tell them apart.
    ``proposed`` carries the candidates the detector offered either way, so an
    unconfigured answer still shows the ink it had no template for.
    """

    #: Which of :data:`STATUSES` this answer is.
    status: str

    #: The proposals a template explained, in page order; two statuses hold none.
    matches: tuple[StampMatch, ...] = ()

    #: How many candidates were proposed, whether or not any could be compared.
    proposed: int = 0

    def __post_init__(self) -> None:
        """Refuse an answer whose status, matches and count disagree."""
        if self.status not in STATUSES:
            raise StampError(f"status must be one of {', '.join(STATUSES)}")
        if not isinstance(self.matches, tuple) or not all(
            isinstance(match, StampMatch) for match in self.matches
        ):
            raise StampError("matches must be a tuple of StampMatch")
        if isinstance(self.proposed, bool) or not isinstance(self.proposed, int):
            raise StampError("proposed must be a whole number of candidates")
        if self.proposed < len(self.matches):
            raise StampError("every match is one proposal, so there cannot be more")
        if self.status == MATCHED and not self.matches:
            raise StampError("a matched answer must name at least one mark")
        if self.status != MATCHED and self.matches:
            raise StampError(f"a {self.status} answer may not carry a match")


def _box_polygon(box: tuple[int, int, int, int]) -> tuple[tuple[int, int], ...]:
    """The four corners of a half-open box, clockwise from the top left.

    The corner order D119 promised for copy-move's boxes, held again rather
    than shared, on D38's rule that one application package holds no constant
    of another's.
    """
    left, top, width, height = box
    right, bottom = left + width, top + height
    return ((left, top), (right, top), (right, bottom), (left, bottom))


def region_polygons(matches: object) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return one box per match as whole-pixel polygons, in the order matched.

    :raises StampError: unless ``matches`` is a tuple of :class:`StampMatch`.
    """
    if not isinstance(matches, tuple) or not all(
        isinstance(match, StampMatch) for match in matches
    ):
        raise StampError("matches must be a tuple of StampMatch")
    return tuple(_box_polygon(match.box) for match in matches)


def find_stamps(
    image: object,
    *,
    level: float = CHROMA_LEVEL,
    close: int = CLOSE,
    min_ink: int = MIN_INK,
    min_side: int = MIN_SIDE,
) -> tuple[StampCandidate, ...]:
    """Return where the frame holds ink this module could call a stamp.

    :returns: the proposals in page order, top to bottom then left to right.
    :raises StampError: on arguments that are not whole-pixel thresholds, or a
        frame :func:`to_color` refuses.
    """
    _check_whole(min_ink, "min_ink")
    _check_whole(min_side, "min_side")
    picture = to_color(image)
    mask = ink_mask(picture, level=level, close=close)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    found = []
    for index in range(1, count):
        x, y, width, height, area = (int(stats[index, column]) for column in range(5))
        if area < min_ink or width < min_side or height < min_side:
            continue
        found.append(StampCandidate(box=(x, y, width, height), ink=area))
    return tuple(sorted(found, key=lambda candidate: (candidate.box[1], candidate.box[0])))


def match_score(image: object, candidate: StampCandidate, template: StampTemplate) -> float:
    """Return how well ``candidate`` correlates with ``template``.

    Both sides are resampled to :data:`CANONICAL` first, which is what makes
    the answer independent of the size the stamp was printed at; the returned
    value is the best single position on the two grids.

    :raises StampError: on a candidate or template that is not a record.
    """
    if not isinstance(candidate, StampCandidate):
        raise StampError("candidate must be a StampCandidate")
    if not isinstance(template, StampTemplate):
        raise StampError("template must be a StampTemplate")
    picture = to_color(image)
    x, y, width, height = candidate.box
    patch = picture[y : y + height, x : x + width]
    return float(
        cv2.matchTemplate(_canonical(patch), template.canonical, cv2.TM_CCOEFF_NORMED).max()
    )


def _check_registry(templates: object) -> typing.Mapping[str, StampTemplate]:
    """Refuse ``templates`` unless it maps names to templates, one name once."""
    if not isinstance(templates, typing.Mapping):
        raise StampError("templates must be a mapping of name to StampTemplate")
    for name, template in templates.items():
        if not isinstance(name, str) or not name.strip():
            raise StampError("a template name must be a non-empty string")
        if not isinstance(template, StampTemplate):
            raise StampError(f"template {name} is not a StampTemplate")
        if template.name != name:
            raise StampError(f"template {name} is registered under a different name")
    return templates


def detect_stamps(
    image: object,
    *,
    templates: typing.Mapping[str, StampTemplate] | None = None,
    level: float = CHROMA_LEVEL,
    close: int = CLOSE,
    min_ink: int = MIN_INK,
    min_side: int = MIN_SIDE,
) -> StampDetection:
    """Return the status this page's proposals were answered with, and the marks.

    Detection proposes and matching disposes: a proposal is reported only when
    the best template in the registry correlates with it at or above
    :data:`MATCH_LEVEL`, so a colour photograph and a patch of text are
    proposed and then declined rather than never offered.

    :param templates: the registry to match against; defaults to
        :data:`STAMP_TEMPLATES`.
    :returns: a :class:`StampDetection` in page order.  **A registry holding
        nothing answers :data:`NOT_CONFIGURED` and never :data:`NO_MATCH`**:
        nothing was compared, and an empty match list would read exactly like
        the measurement it is not.  D121.
    :raises StampError: on arguments that are not well formed.
    """
    known = _check_registry(STAMP_TEMPLATES if templates is None else templates)
    picture = to_color(image)
    candidates = find_stamps(
        picture, level=level, close=close, min_ink=min_ink, min_side=min_side
    )
    if not known:
        return StampDetection(status=NOT_CONFIGURED, proposed=len(candidates))
    matched = []
    for candidate in candidates:
        best_name, best_score = None, None
        for name, template in known.items():
            score = match_score(picture, candidate, template)
            if best_score is None or score > best_score:
                best_name, best_score = name, score
        if best_score is not None and best_score >= MATCH_LEVEL:
            matched.append(
                StampMatch(template=best_name, score=best_score, box=candidate.box)
            )
    return StampDetection(
        status=MATCHED if matched else NO_MATCH,
        matches=tuple(matched),
        proposed=len(candidates),
    )


def _authored(image: np.ndarray) -> np.ndarray:
    """Return ``image`` as a codec wrote it and read it back."""
    encoded, buffer = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), QUALITY]
    )
    if not encoded:
        raise StampError("the JPEG encoder refused the template")
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _entry_art() -> np.ndarray:
    """Draw the ``demo_entry_stamp`` mark: two rings, a bar and its lettering."""
    side, centre, ink = 140, 70, (190, 60, 40)
    art = np.full((side, side, 3), 255, np.uint8)
    cv2.circle(art, (centre, centre), centre - 6, ink, 3)
    cv2.circle(art, (centre, centre), centre - 20, ink, 2)
    cv2.line(art, (8, centre), (side - 8, centre), ink, 2)
    cv2.putText(
        art, "E N T R Y", (centre - 46, centre + 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, ink, 2, cv2.LINE_AA,
    )
    return art


def _exit_art() -> np.ndarray:
    """Draw the ``demo_exit_stamp`` mark: two rings, a star and its lettering."""
    side, centre, ink = 140, 70, (190, 60, 40)
    art = np.full((side, side, 3), 255, np.uint8)
    cv2.circle(art, (centre, centre), centre - 4, ink, 4)
    cv2.circle(art, (centre, centre), centre - 16, ink, 2)
    points = []
    for step in range(10):
        radius = centre - 26 if step % 2 == 0 else centre - 48
        angle = -np.pi / 2 + step * np.pi / 5
        points.append((int(centre + radius * np.cos(angle)), int(centre + radius * np.sin(angle))))
    for step in range(10):
        cv2.line(art, points[step], points[(step + 1) % 10], ink, 2)
    cv2.putText(
        art, "E X I T", (centre - 42, centre + 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, ink, 2, cv2.LINE_AA,
    )
    return art


#: The marks a screening may match against, by name and in registry order,
#: behind a read-only proxy so the set cannot be edited after import.  **Both
#: entries are drawn by this repository**: no authority's mark is committed,
#: so a real stamp matches none of them and that is stated rather than hidden.
STAMP_TEMPLATES: typing.Mapping[str, StampTemplate] = types.MappingProxyType(
    {
        "demo_entry_stamp": make_template("demo_entry_stamp", _authored(_entry_art())),
        "demo_exit_stamp": make_template("demo_exit_stamp", _authored(_exit_art())),
    }
)

#: The names :data:`STAMP_TEMPLATES` holds, in the order it holds them in.
TEMPLATE_NAMES = tuple(STAMP_TEMPLATES)


def _summarise(detection: StampDetection, held: int) -> str:
    """Return the clause of a stamp result that says what was compared.

    An unconfigured registry is named rather than counted: "explained 0 of 3
    against 0 templates" is arithmetic that reads clean, which is the one
    reading D121 exists to stop.
    """
    if detection.status == NOT_CONFIGURED:
        return (
            f"not_configured: this instance holds no template, so none of the "
            f"{detection.proposed} proposed regions could be compared with "
            f"anything. That is an absent capability, not a page with nothing "
            f"on it."
        )
    explained = ", ".join(
        f"{match.template} at {match.score:.2f}" for match in detection.matches
    )
    return (
        f"explained {len(detection.matches)} of them against {held} templates this "
        f"repository drew itself: "
        + (explained or "none matched, which is a measurement and not a clean page")
        + "."
    )


class StampModule(base.DeepModule):
    """Stamp matching behind the Tier 2 seam: a named mark and where it sits.

    It reads the working frame off the context it is handed and answers one
    D116 record whose regions are the boxes :func:`detect_stamps` matched.  The
    heatmap is left empty on purpose: this module knows where a mark is rather
    than how hot a pixel map went, so there is no map to draw.  ``is_stub`` is
    set because a name for a mark this repository drew is not authentication.

    The registry is a constructor argument, so an instance holding no mark
    answers ``not_configured`` in its detail rather than a zero that reads
    clean.  D121.
    """

    name = MODULE_NAME

    def __init__(
        self, templates: typing.Mapping[str, StampTemplate] | None = None
    ) -> None:
        """Hold the registry to name marks from, refusing it once, here.

        :raises StampError: on a registry :func:`_check_registry` refuses, at
            construction rather than once per document.
        """
        self.templates = STAMP_TEMPLATES if templates is None else _check_registry(templates)

    def run(self, context: "ScreeningContext") -> base.DeepResult:
        """Return this capture's stamp record.

        :returns: one :class:`~app.pipeline.tier2.base.DeepResult` whose score
            is the best match on the page and whose regions are its boxes, and
            whose detail carries ``not_configured`` when nothing was compared.
        """
        detection = detect_stamps(context.image, templates=self.templates)
        score = max((match.score for match in detection.matches), default=0.0)
        detail = (
            f"Stamp matching proposed {detection.proposed} inked regions and "
            f"{_summarise(detection, len(self.templates))} "
            "A mark this module names is a likeness, not an authentication."
        )
        return base.DeepResult(
            module=self.name,
            score=score,
            is_stub=True,
            model_version=MODEL_VERSION,
            detail=detail,
            regions=region_polygons(detection.matches),
        )
