"""Tier 2 answers as flags: what each module said, and where it is.

One :class:~app.pipeline.tier2.base.DeepResult becomes one
:class:~app.risk.flags.EvidenceFlag, carrying the module score, its own
sentence and its stand-in label across unchanged.  The flag region is the
strongest place the record can name: a box the module located itself, else the
connected group of hot cells holding the map peak, else `None`.  Nothing here
decides that a result is a finding; D125 records why, and what was measured.
"""

import dataclasses
import numbers
import types
import typing

from app.pipeline.tier2 import base, copy_move, deepfake, ela, morph, noise_residual, stamp
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

__all__ = [
    "RULES",
    "RULE_BY_MODULE",
    "Rule",
    "Tier2FlagError",
    "flag_from_result",
    "flags_from_run",
    "region_from_result",
]

#: The tier every flag this module builds reports itself under.
TIER = 2


class Tier2FlagError(ValueError):
    """Raised when a result cannot be turned into a flag.

    A `ValueError`, so a caller catching one around its cascade keeps
    working, as D114 requires of everything Tier 2 raises.  A message names
    the rule broken and never repeats the value.
    """


@dataclasses.dataclass(frozen=True)
class Rule:
    """One module flag: the id it reports under, and how it is located.

    `level` is the module own constant rather than a number chosen here, so
    the line a region is drawn at cannot drift from the line the module reads
    against.  `weight_band` mirrors `weightsets/v1.yaml`.
    """

    module: str
    flag_id: str
    label: str
    weight_band: str
    level: float
    source_module: str


#: One rule per module behind the Tier 2 seam.  A module missing from this
#: table has nowhere to report and is refused, rather than answered as a module
#: that found nothing.
RULES: tuple[Rule, ...] = (
    Rule(
        module=ela.MODULE_NAME,
        flag_id=flag_ids.TAMPER_ELA_ANOMALY,
        label="Error-level analysis found a region that re-compresses unlike the page around it.",
        weight_band="review",
        level=ela.HOT_LEVEL,
        source_module="app.pipeline.tier2.ela",
    ),
    Rule(
        module=noise_residual.MODULE_NAME,
        flag_id=flag_ids.TAMPER_NOISE_RESIDUAL_ANOMALY,
        label="Noise-residual analysis found a region whose local noise the paper around it does not have.",
        weight_band="review",
        level=noise_residual.HOT_LEVEL,
        source_module="app.pipeline.tier2.noise_residual",
    ),
    Rule(
        module=copy_move.MODULE_NAME,
        flag_id=flag_ids.TAMPER_COPY_MOVE_ANOMALY,
        label="Copy-move matching found content repeated elsewhere inside this one document.",
        weight_band="review",
        level=copy_move.HOT_LEVEL,
        source_module="app.pipeline.tier2.copy_move",
    ),
    Rule(
        module=stamp.MODULE_NAME,
        flag_id=flag_ids.TAMPER_STAMP_ANOMALY,
        label="Stamp matching found a mark that disagrees with the stamp it resembles.",
        weight_band="review",
        level=stamp.MATCH_LEVEL,
        source_module="app.pipeline.tier2.stamp",
    ),
    Rule(
        module=morph.MODULE_NAME,
        flag_id=flag_ids.TAMPER_MORPH_SUSPECTED,
        label="The morph classifier scored the region it was pointed at as morphed.",
        weight_band="high",
        level=morph.SUSPECT_LEVEL,
        source_module="app.pipeline.tier2.morph",
    ),
    Rule(
        module=deepfake.MODULE_NAME,
        flag_id=flag_ids.TAMPER_DEEPFAKE_SUSPECTED,
        label="The deepfake classifier scored the region it was pointed at as synthetic.",
        weight_band="high",
        level=deepfake.SUSPECT_LEVEL,
        source_module="app.pipeline.tier2.deepfake",
    ),
)

#: The same rules under the module name a result carries, behind a read-only
#: proxy so no caller can widen the set a screening reports under.
RULE_BY_MODULE: typing.Mapping[str, Rule] = types.MappingProxyType(
    {rule.module: rule for rule in RULES}
)


def _rule(module: object, registry: typing.Mapping[str, Rule]) -> Rule:
    """Return the rule `module` reports under in `registry`, or a refusal."""
    rule = registry.get(module) if isinstance(module, str) else None
    if rule is None:
        raise Tier2FlagError("module names no Tier 2 flag rule")
    return rule


def _check_shape(shape: object) -> tuple[int, int]:
    """Refuse `shape` unless it is a frame own `(height, width)`."""
    if not isinstance(shape, tuple) or len(shape) != 2:
        raise Tier2FlagError("shape must be a (height, width) pair")
    if not all(isinstance(side, int) and not isinstance(side, bool) for side in shape):
        raise Tier2FlagError("shape must hold whole pixel counts")
    if not all(side > 0 for side in shape):
        raise Tier2FlagError("shape must hold a positive frame")
    return shape


def _check_level(level: object) -> float:
    """Refuse `level` unless it is a real number in the closed unit interval."""
    if isinstance(level, bool) or not isinstance(level, numbers.Real):
        raise Tier2FlagError("level must be a real number")
    if not 0.0 <= float(level) <= 1.0:
        raise Tier2FlagError("level must sit in [0, 1]")
    return float(level)


def _box(left: int, top: int, right: int, bottom: int) -> tuple[tuple[int, int], ...]:
    """Return one half-open box as corners clockwise from the top left.

    The order :func:~app.pipeline.tier0.mrz_region._box_polygon promises and
    in plain integers, so a highlight drawn over a Tier 2 finding is drawn the
    way one over a Tier 0 field is.
    """
    return (
        (int(left), int(top)),
        (int(right), int(top)),
        (int(right), int(bottom)),
        (int(left), int(bottom)),
    )


def _peak(heatmap: tuple[tuple[float, ...], ...]) -> tuple[float, int, int]:
    """Return the map hottest cell as `(value, row, column)`.

    A tie keeps the first cell in image order, so one map always names one
    peak and a repeated run draws the same box.
    """
    best = (0.0, 0, 0)
    for row, cells in enumerate(heatmap):
        for column, cell in enumerate(cells):
            if cell > best[0]:
                best = (cell, row, column)
    return best


def _peak_box(
    heatmap: tuple[tuple[float, ...], ...], shape: tuple[int, int], level: float
) -> tuple[tuple[int, int], ...] | None:
    """Return the box the hottest group of cells at or above `level` covers.

    The group is the four-connected run of qualifying cells holding the peak,
    so one tampered area is one box rather than one box per block, and a cold
    map answers `None` rather than a box over the frame.
    """
    rows, columns = len(heatmap), len(heatmap[0])
    peak, start_row, start_column = _peak(heatmap)
    if peak < level:
        return None
    seen = {(start_row, start_column)}
    stack = [(start_row, start_column)]
    top = bottom = start_row
    left = right = start_column
    while stack:
        row, column = stack.pop()
        top, bottom = min(top, row), max(bottom, row)
        left, right = min(left, column), max(right, column)
        for neighbour in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            if (
                0 <= neighbour[0] < rows
                and 0 <= neighbour[1] < columns
                and neighbour not in seen
                and heatmap[neighbour[0]][neighbour[1]] >= level
            ):
                seen.add(neighbour)
                stack.append(neighbour)
    height, width = shape
    return _box(
        left * width // columns,
        top * height // rows,
        (right + 1) * width // columns,
        (bottom + 1) * height // rows,
    )


def region_from_result(
    result: base.DeepResult,
    shape: tuple[int, int],
    *,
    registry: typing.Mapping[str, Rule] = RULE_BY_MODULE,
) -> tuple[tuple[int, int], ...] | None:
    """Return where `result` strongest reading is, or `None`.

    A region the module located itself wins over a box derived from its own
    heatmap, because it measured the place rather than the map; the first is
    taken, as the modules that carry both order their groups as they found
    them.  A result that is one number for the whole page carries neither and
    answers `None`, which is a finding with nowhere to point rather than a
    dropped flag.

    :param result: the record one deep module answered.
    :param shape: the frame shape module was handed, as `(height, width)`;
        the map grid is stretched across it, so a frame that is not a whole
        number of blocks still answers boxes inside its own edges.
    :param registry: the rules to report under, as :data:`RULE_BY_MODULE`
        ships them; a caller may pass its own to draw a box at a line other
        than the shipped one.
    :returns: the polygon, or `None` when the record locates nothing.
    :raises Tier2FlagError: on a result or a shape that is not one, or on a
        level outside the unit interval.
    """
    if not isinstance(result, base.DeepResult):
        raise Tier2FlagError("result must be a DeepResult")
    frame = _check_shape(shape)
    rule = _rule(result.module, registry)
    if result.regions:
        return result.regions[0]
    if not result.heatmap:
        return None
    return _peak_box(result.heatmap, frame, _check_level(rule.level))


def flag_from_result(
    result: base.DeepResult,
    *,
    shape: tuple[int, int],
    registry: typing.Mapping[str, Rule] = RULE_BY_MODULE,
) -> EvidenceFlag:
    """Return one :class:~app.risk.flags.EvidenceFlag for `result`.

    **Two numbers read the same measurement.**  A deep module answers one
    score, so `value` and `confidence` both carry it rather than one of
    them estimating a second thing nobody measured.  `expected` and
    `found` are `None` because a map has no expected half, and `reason`
    is the module own sentence, which is where its stand-in label travels:
    :class:~app.risk.flags.EvidenceFlag has no field of its own for it.

    :param result: the record one deep module answered.
    :param shape: the frame shape module was handed, as `(height, width)`.
    :param registry: the rules to report under, as :data:`RULE_BY_MODULE`
        ships them; handed to :func:`region_from_result` unchanged.
    :returns: one flag carrying `result` score and its located region.
    :raises Tier2FlagError: on a result no rule reports, or a bad `shape`.
    """
    rule = (
        _rule(result.module, registry)
        if isinstance(result, base.DeepResult)
        else None
    )
    if rule is None:
        raise Tier2FlagError("result must be a DeepResult from a named Tier 2 module")
    return EvidenceFlag(
        id=rule.flag_id,
        tier=TIER,
        label=rule.label,
        weight_band=rule.weight_band,
        value=result.score,
        confidence=result.score,
        region=region_from_result(result, shape, registry=registry),
        expected=None,
        found=None,
        reason=result.detail,
        source_module=rule.source_module,
        field=None,
    )


def flags_from_run(
    run: base.DeepRun,
    *,
    shape: tuple[int, int],
    registry: typing.Mapping[str, Rule] = RULE_BY_MODULE,
) -> tuple[EvidenceFlag, ...]:
    """Return one flag per result in `run`, in the order the run answered.

    Every result becomes a flag, including one that located nothing, and
    **whether any of them is a finding is not decided here**: D125 measures
    why a Tier 2 module own level cannot be that gate, and 15.6 fusion is
    where the question belongs.

    :param run: what :func:~app.pipeline.tier2.base.run_deep_modules answered.
    :param shape: the frame shape each module was handed, as `(height, width)`.
    :returns: one flag per result, in `run` order; an empty run answers an
        empty tuple, which is no deep module configured and not a clean page.
    :param registry: the rules to report under, as :data:`RULE_BY_MODULE`
        ships them; handed to :func:`flag_from_result` unchanged.
    :raises Tier2FlagError: on a run that is not one, or a result no rule names.
    """
    if not isinstance(run, base.DeepRun):
        raise Tier2FlagError("run must be a DeepRun")
    return tuple(
        flag_from_result(result, shape=shape, registry=registry)
        for result in run.results
    )
