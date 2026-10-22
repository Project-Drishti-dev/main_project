"""The summary written when there is no model text: fixed frame, one line per flag.

Every line is a flag's own ``id`` and ``reason``, so the fallback cannot invent a
claim the flags do not carry and does not need a model to exist (``D135``).
"""

from app.risk.flags import WEIGHT_BANDS, FlagValueError

__all__ = ["template_summary"]

#: The frame, written so that no number and no field name can appear in it --
#: 17.5's contract with ``D133``'s two extractors.
_BAND = "This document reads as {0} risk."
_HEADLINE_WITH_FLAGS = (
    "Each finding the scan raised is on its own line below, in the wording"
    " the rule wrote."
)
_HEADLINE_WITHOUT_FLAGS = "No check in the scan raised a finding."
_CLOSING = "The band is what the scan read, not a decision about the document."

#: What a flag line looks like, and the mark an officer and a test both split on.
_BULLET = "- "


def template_summary(flags: object, band: object) -> str:
    """The model-free summary: three sentences of frame, then one line per flag.

    ``flags`` are the findings in cascade order, each carrying ``id`` and
    ``reason``; ``band`` is one of :data:`~app.risk.flags.WEIGHT_BANDS`.  Raises
    :exc:`~app.risk.flags.FlagValueError` on a band or a flag it cannot read.
    """
    lines = [_BAND.format(_band(band))]
    narrated = tuple(flags)
    if not narrated:
        lines.append(_HEADLINE_WITHOUT_FLAGS)
    else:
        lines.append(_HEADLINE_WITH_FLAGS)
        lines.extend(_flag_line(flag) for flag in narrated)
    lines.append(_CLOSING)
    return "\n".join(lines)


def _band(band: object) -> str:
    """``band`` if it is one of :data:`~app.risk.flags.WEIGHT_BANDS`, else a refusal."""
    if not isinstance(band, str) or band not in WEIGHT_BANDS:
        raise FlagValueError("band must be one of " + ", ".join(sorted(WEIGHT_BANDS)))
    return band


def _flag_line(flag: object) -> str:
    """The one line ``flag`` is narrated on: its id, with its own reason beside it."""
    flag_id = _text(flag, "id")
    reason = _text(flag, "reason", optional=True)
    return _BULLET + (flag_id + ": " + reason if reason else flag_id)


def _text(flag: object, name: str, optional: bool = False) -> str:
    """The attribute ``flag`` carries as text, or a refusal naming what it lacked."""
    try:
        value = getattr(flag, name)
    except AttributeError:
        raise FlagValueError(
            "a flag must carry a {0!r} to be narrated".format(name)
        ) from None
    if not isinstance(value, str):
        raise FlagValueError(
            "a flag's {0} must be text, not {1}".format(name, type(value).__name__)
        )
    if not value.strip() and not optional:
        raise FlagValueError("a flag's {0} must not be blank".format(name))
    return value
