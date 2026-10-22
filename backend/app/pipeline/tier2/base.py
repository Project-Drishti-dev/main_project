"""Tier 2's seam: the one question a deep module is asked, and the registry of them.

:class:`DeepModule` is what every deep module goes through.  ``run`` is handed
the screening's context and answers one :class:`DeepResult` -- a score, a
heatmap, the regions that make a finding locatable, and whether a real model
produced any of it.  The seam names that question and nothing else: no model,
no threshold, and no field a module may not read off the context it was handed.

**The registry is read-only and ships empty.**  :data:`DEEP_MODULES` holds no
module today, because 15.1 is the seam and the first module behind it is 15.3,
and it sits behind a mapping proxy so no caller can widen the set a screening
draws from.  An empty registry is an answer and not a refusal:
:func:`run_deep_modules` hands back a :class:`DeepRun` with nothing in it, on
D86's rule that an absent capability stays visible rather than being read as a
pass.

**A module that raises is not caught here.**  D114 isolates a broken stage
inside ``run_cascade``, one level up, and a deep module is reached through
that cascade, so catching a second time here would hide the failure from the
trace row whose whole job is to record it.  What a module is asked, and what
it answers, is the seam.  What happens when a module cannot answer is the
cascade's to decide, once.

**A result says who produced it.**  ``is_stub`` and ``model_version`` carry no
default, so a module cannot answer without naming whether a real model did the
work, and a stub's score is never evidence that a document is clean.
"""

import abc
import dataclasses
import numbers
import types
import typing

from app.risk.flags import MIN_REGION_CORNERS

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "DEEP_MODULES",
    "MODULE_NAMES",
    "DeepModule",
    "DeepResult",
    "DeepResultError",
    "DeepRun",
    "run_deep_modules",
]

#: The deep modules a screening may run, by name and in the order they run,
#: behind a read-only proxy so the set cannot be edited after import.  **It
#: holds none yet.**  An empty registry is a state the runner answers, not a
#: wiring mistake, and the first module behind it is 15.3's rather than this
#: task's.
DEEP_MODULES: typing.Mapping[str, "DeepModule"] = types.MappingProxyType({})

#: The names :data:`DEEP_MODULES` holds, in the order it holds them in.
MODULE_NAMES = tuple(DEEP_MODULES)


class DeepResultError(ValueError):
    """Raised when a field of a :class:`DeepResult` is not well formed.

    A ``ValueError``, so a caller catching one around its cascade keeps
    working.  A message names the rule broken and never repeats the value.
    """


def _check_text(value: object, field: str) -> None:
    """Refuse ``field`` unless it is a string carrying something to say."""
    if not isinstance(value, str) or not value.strip():
        raise DeepResultError(f"{field} must be a non-empty string")


def _check_unit(value: object, field: str) -> None:
    """Refuse ``field`` unless it is a real number in the closed unit interval."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise DeepResultError(f"{field} must be a real number")
    if not 0.0 <= float(value) <= 1.0:
        raise DeepResultError(f"{field} must sit in [0, 1]")


def _check_heatmap(heatmap: object) -> None:
    """Refuse ``heatmap`` unless it is rows of ``[0, 1]`` numbers of one width.

    Empty is legal and means no map was drawn.  **It is not a map of zeros**,
    since an overlay over it would claim a measurement nobody made, and a
    ragged grid is refused because no overlay draws on one.
    """
    if not isinstance(heatmap, tuple):
        raise DeepResultError("heatmap must be a tuple of rows")
    width = None
    for row in heatmap:
        if not isinstance(row, tuple):
            raise DeepResultError("a heatmap row must be a tuple of numbers")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise DeepResultError("every heatmap row must be the same width")
        for cell in row:
            _check_unit(cell, "a heatmap cell")


def _check_regions(regions: object) -> None:
    """Refuse ``regions`` unless it is a tuple of whole-pixel polygons.

    Empty is legal and means nothing was located, which is an answer rather
    than a gap.  Corners are whole pixels, as
    :attr:`~app.risk.flags.EvidenceFlag.region` holds them.
    """
    if not isinstance(regions, tuple):
        raise DeepResultError("regions must be a tuple of polygons")
    for index, region in enumerate(regions):
        if not isinstance(region, tuple) or len(region) < MIN_REGION_CORNERS:
            raise DeepResultError(
                f"region {index} must be a tuple of at least "
                f"{MIN_REGION_CORNERS} corners"
            )
        for corner in region:
            if not isinstance(corner, tuple) or len(corner) != 2:
                raise DeepResultError(f"region {index} corner must be an (x, y) pair")
            if not all(isinstance(coord, numbers.Integral) for coord in corner):
                raise DeepResultError(f"region {index} corner must hold whole pixels")


@dataclasses.dataclass(frozen=True)
class DeepResult:
    """One deep module's answer: how strongly, where, and who produced it.

    ``score`` is the module's own ``[0, 1]`` confidence and not a probability
    the document is forged; ``heatmap`` is normalised rows in image order and
    ``regions`` are whole-pixel polygons in the same frame.  **Empty means the
    module produced neither**, never that it measured zero.  ``D116`` records
    the rest, and :exc:`DeepResultError` what is refused.
    """

    #: The name of the module that answered, as it is registered.
    module: str

    #: How strongly this module believes its own finding, in ``[0, 1]``.
    score: float

    #: Whether a stand-in produced this answer rather than a real model.
    is_stub: bool

    #: What produced the answer: a model and its version, or a stand-in's.
    model_version: str

    #: The one sentence an officer reads beside the score.
    detail: str

    #: Rows of normalised ``[0, 1]`` values in image order; empty is no map.
    heatmap: tuple[tuple[float, ...], ...] = ()

    #: Whole-pixel polygons in the frame handed over; empty is nothing located.
    regions: tuple[tuple[tuple[int, int], ...], ...] = ()

    def __post_init__(self) -> None:
        _check_text(self.module, "module")
        _check_unit(self.score, "score")
        if not isinstance(self.is_stub, bool):
            raise DeepResultError("is_stub must be a bool")
        _check_text(self.model_version, "model_version")
        _check_text(self.detail, "detail")
        _check_heatmap(self.heatmap)
        _check_regions(self.regions)


class DeepModule(abc.ABC):
    """The one question Tier 2 asks a deep module, and the shape of its answer.

    A subclass that omits ``run`` cannot be instantiated, so a module wired
    wrongly fails at construction rather than on the first document.
    """

    #: The name this module is registered under, and the name its result and
    #: its flags are traced to.  Declared rather than read off the class name,
    #: so a rename is one edit here and not a search across the tier.
    name: str

    @abc.abstractmethod
    def run(self, context: "ScreeningContext") -> DeepResult:
        """Return one result describing what ``context`` carries.

        :param context: the run's record, the one ``run_cascade`` hands each
            stage; the working frame is on ``context.image``.
        :returns: one :class:`DeepResult`, which 15.2 defines as a score, a
            heatmap, regions, the module name, ``is_stub`` and a
            ``model_version``.
        """
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class DeepRun:
    """What one call over the registry answered: what ran, and what it said.

    ``ran`` names the modules that ran in registry order and ``results`` holds
    one answer each in that same order, so a caller reads a name beside its own
    row.  Both are empty when the registry is empty, which says no deep module
    was configured.  It is not a clean document, and nothing here may be read
    as one.
    """

    ran: tuple[str, ...]
    results: tuple[DeepResult, ...]


def run_deep_modules(
    context: "ScreeningContext",
    *,
    modules: typing.Mapping[str, "DeepModule"] | None = None,
) -> DeepRun:
    """Run every registered deep module over ``context`` and answer their rows.

    :param context: the run's record; a module reads it and returns its own
        answer rather than writing onto it.
    :param modules: the registry to run, in the order it holds them; defaults
        to :data:`DEEP_MODULES`.
    :returns: a :class:`DeepRun` naming the modules that ran and holding one
        answer each in that order.  A registry holding none answers an empty
        :class:`DeepRun` rather than a refusal, so an unconfigured tier is a
        visible absence and never a silent pass.
    """
    known = DEEP_MODULES if modules is None else modules
    results = tuple(module.run(context) for module in known.values())
    return DeepRun(ran=tuple(known), results=results)
