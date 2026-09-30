"""The one place that knows which of the three MRZ formats it is looking at.

Three modules, three shapes: a TD1 is :data:`~app.pipeline.tier0.td1.
TD1_LINE_COUNT` lines of :data:`~app.pipeline.tier0.td1.TD1_LINE_LENGTH`
characters, a TD2 is :data:`~app.pipeline.tier0.td2.TD2_LINE_COUNT` of
:data:`~app.pipeline.tier0.td2.TD2_LINE_LENGTH`, and a TD3 is
:data:`~app.pipeline.tier0.td3.TD3_LINE_COUNT` of
:data:`~app.pipeline.tier0.td3.TD3_LINE_LENGTH`.  Each of those is stated
twice already -- once as a constant in its own module and once as a check in
that module's ``validate_*_lines`` -- and this module is the only place that
states all three **together**, which is the question a caller with a zone and
no idea what it is actually asking.

**It lives in its own module because it is the one thing that cannot live in
any of the other four.**  ``mrz.py`` must not import a format module, since
all three import it; ``td1.py`` and ``td2.py`` cannot be imported by
``td3.py`` without a cycle through this one, and :class:`~app.pipeline.
tier0.td3.MrzDocument` is the common record all three now build.  So the
dispatcher is above them, imports them, and nothing imports it but a caller.

**Nothing here parses a field.**  :func:`parse_mrz` recognises a shape and
hands the lines to the format's own parser, which slices nothing for itself
and judges fields with the readers its own module has held since Part 2.  A
fourth format is one entry in :data:`MRZ_SHAPES` and one function in
:data:`MRZ_PARSERS`; the two tables are the only things a format has to be
added to, and a test asserts they hold the same three keys so one cannot be
extended without the other.

**The record it returns carries no reference date and no inferred year, and
that is a decision rather than an omission.**  Three shapes were available
and the reasoning is on :class:`~app.pipeline.tier0.td3.MrzDocument`; the
short of it is that a year is ``int | None`` against a reference date, so
putting one on the record would freeze a reading of a date without the thing
that makes it true, and a ``reference`` attribute is the one shape that could
put ``datetime.now()`` back at the edge of the package -- which
``tasks.md`` bans inside check logic, and which 3.12 and 3.13 pinned out of
:mod:`~app.pipeline.tier0.mrz` with an AST walk.  **This module therefore
imports neither :func:`~app.pipeline.tier0.mrz.infer_birth_year` nor
:func:`~app.pipeline.tier0.mrz.infer_expiry_year`, and does not import
:mod:`datetime` at all**, and a test walks this file's AST to keep it that
way rather than trusting this paragraph.
"""

from collections.abc import Iterable

from .mrz import MrzValueError
from .td1 import (
    TD1_LINE_COUNT,
    TD1_LINE_LENGTH,
    parse_td1,
)
from .td2 import (
    TD2_LINE_COUNT,
    TD2_LINE_LENGTH,
    parse_td2,
)
from .td3 import (
    TD3_LINE_COUNT,
    TD3_LINE_LENGTH,
    MrzDocument,
    parse_td3,
)

__all__ = [
    "MRZ_PARSERS",
    "MRZ_SHAPES",
    "MrzDocument",
    "detect_mrz_format",
    "parse_mrz",
]


#: The three machine-readable zone shapes, as ``(line count, line length)``
#: keys mapped to the format's name: ``"TD1"``, ``"TD2"`` and ``"TD3"``.  The
#: widths are the constants each format's own module exports, resolved at
#: import rather than retyped, so a width corrected in one place is corrected
#: here and a fourth format is one row.
#:
#: **The keys are shapes, not contents, and that is deliberate.**  Nothing
#: here looks at a character: a zone of the right width whose document code
#: prints ``"P<"`` in three 30-character lines is a TD1 by shape, and the
#: format's own readers are what refuse the passport code.  Shape is the only
#: thing a dispatcher can decide that is not a judgement about the document,
#: and a dispatcher that also judged would be a fourth set of rules nobody
#: wrote a standard section for.
#:
#: **The three shapes are disjoint, and that is what makes the dispatch
#: unambiguous.**  Two lines of 36 and two lines of 44 differ only in the
#: width, three lines of 30 differ only in the count, and no two entries
#: share both -- so there is never a tie to break, and a test asserts the
#: three counts and widths are all different rather than trusting it.
MRZ_SHAPES: dict[tuple[int, int], str] = {
    (TD1_LINE_COUNT, TD1_LINE_LENGTH): "TD1",
    (TD2_LINE_COUNT, TD2_LINE_LENGTH): "TD2",
    (TD3_LINE_COUNT, TD3_LINE_LENGTH): "TD3",
}


#: The parser each format's name reaches, so :func:`parse_mrz` dispatches on
#: the value :data:`MRZ_SHAPES` returns rather than on an ``if`` chain that
#: would have to be edited for every format.  A test asserts the keys here and
#: in :data:`MRZ_SHAPES` are the same set, so a row added to one table and not
#: the other raises rather than dispatching to nothing.
MRZ_PARSERS = {
    "TD1": parse_td1,
    "TD2": parse_td2,
    "TD3": parse_td3,
}


def _zone_of(lines: Iterable[str]) -> tuple[str, ...]:
    """Return ``lines`` as a tuple of them, or raise if the argument is not a zone.

    The one materialisation, and the only place in this module that reads the
    lines: the dispatcher needs a line count and a width before it can name a
    format, and the format's parser needs the same lines again, so it is done
    once here and passed on.  **A single string is refused here rather than
    measured**, for
    :func:`~app.pipeline.tier0.td3.validate_td3_lines`'s reason: a string is
    a sequence of one-character lines, so iterating it would report 88 lines
    and point at the wrong mistake entirely.

    The tuple is the zone itself, so nothing read here is new information: a
    caller's own list is what every length in the next sentence is measured
    from, and the character strings this returns are never echoed -- a message
    built from it carries widths only.
    """
    if isinstance(lines, str):
        raise MrzValueError(
            "a machine-readable zone is a sequence of lines, "
            f"not one string of {len(lines)} characters"
        )
    try:
        zone = tuple(lines)
    except TypeError:
        raise MrzValueError(
            "a machine-readable zone must be a sequence of lines, "
            f"not {type(lines).__name__}"
        ) from None
    return zone


def _shape_of(zone: tuple[str, ...]) -> tuple[tuple[int, ...], int]:
    """Return the widths of ``zone`` and how many of its lines are not strings."""
    widths = tuple(len(line) for line in zone if isinstance(line, str))
    return widths, len(zone) - len(widths)


def _describe(widths: tuple[int, ...], not_strings: int) -> str:
    """Return a shape in words, for a message that must not echo the lines.

    A line's *width* is shape -- how many characters it has -- while its
    characters are the identity data the screening is about, so this names
    widths and counts and never a character.  Uniform and non-uniform zones
    read differently because they are different mistakes: three lines of 30
    is a well-formed shape this project has no parser for, while three lines
    where one is 44 is a zone that was damaged on the way in.
    """
    total = len(widths) + not_strings
    if total == 0:
        return "no lines"
    lines = "line" if total == 1 else "lines"
    if not_strings:
        return (
            f"{total} {lines} of which {not_strings} "
            f"{'is' if not_strings == 1 else 'are'} not strings"
        )
    if len(set(widths)) == 1:
        return f"{total} {lines} of {widths[0]} characters"
    return (
        f"{total} {lines} of "
        + " and ".join(str(width) for width in widths)
        + " characters"
    )


def detect_mrz_format(lines: Iterable[str]) -> str:
    """Return the format name for the zone at ``lines``, or raise.

    **The answer is the shape and nothing else.**  Three lines of 30 is
    ``"TD1"``, two of 36 is ``"TD2"``, two of 44 is ``"TD3"``, and everything
    else is refused -- including a shape that is one line short, one line
    long, or the right lines at the wrong width, all of which are documents
    this project has no parser for rather than documents that failed one.

    **A refused shape is named, because "unrecognised" on its own is not a
    diagnosis.**  The message states how many lines arrived and how wide they
    were, then the three shapes this package does recognise, so an officer
    looking at a log can tell a truncated zone from a fourth format without
    reading this function.  **The widths are shape rather than identity
    data** -- they say how many characters a line has, not what they are --
    so the message is safe to log under the same rule every other message in
    this package is.

    **A line that is not a string is refused as a shape, not as a document.**
    :func:`_shape_of` counts a non-string as ``-1``, which matches no entry,
    so ``parse_td3([None, None])`` is reported here as a zone of two
    non-strings rather than reaching a format's reader and escaping as a bare
    ``TypeError`` -- the same single-error-type rule 1.9 settled.

    Raises:
        MrzValueError: unless ``lines`` is a sequence of strings whose count
            and widths name one of :data:`MRZ_SHAPES`.
    """
    widths, not_strings = _shape_of(_zone_of(lines))
    # Uniform or nothing: a zone whose lines are different widths is a zone
    # that was damaged on the way in, and answering "TD2" because its first
    # line is 36 characters long would be a guess dressed as a reading.
    uniform = not not_strings and len(set(widths)) == 1
    format_name = MRZ_SHAPES.get((len(widths), widths[0])) if uniform else None
    if format_name is None:
        raise MrzValueError(
            f"{_describe(widths, not_strings)} does not name a "
            "machine-readable zone this project reads: "
            + ", ".join(
                f"{count} line(s) of {length} is {name}"
                for (count, length), name in sorted(MRZ_SHAPES.items())
            )
        )
    return format_name


def parse_mrz(lines: Iterable[str]) -> MrzDocument:
    """Return the whole zone at ``lines``, whatever format it turns out to be.

    The dispatch, and nothing else: :func:`detect_mrz_format` names the
    format from the line count and the widths, and the format's own parser
    does the reading.  Every field verdict therefore comes from the module
    that has held the layout and the readers for it since Part 2, and this
    function cannot disagree with them about a position.

    **This is the only layer that can guarantee each parser gets the right
    line, and 3.10 is why that is not optional.**  A TD2 line 1 parses as a
    TD2 line 2 without complaint -- its 1-9 read as a short padded number,
    its 11-13 as ``"SON"``, its 21 as an ``"M"`` -- and the arithmetic does
    not object either, because the composite skips exactly those positions.
    A caller who hands those two lines to :func:`~app.pipeline.tier0.td2.
    parse_td2_line_2` is describing a different document, and the only layer
    that knows the difference is the one choosing the parser.

    **The record says which format it is, and that is what makes one
    :class:`~app.pipeline.tier0.td3.MrzDocument` enough for three
    documents.**  A caller reads :attr:`~app.pipeline.tier0.td3.MrzDocument.
    format` first and then knows which of the per-format attributes can hold
    a value at all, rather than discovering it by finding ``None`` where a
    personal number should be.

    **The zone gate runs before the readers, and that order is the point.**
    Each format's ``validate_*_lines`` refuses a shape first, so a
    mis-measured line is reported as a wrong width rather than as a field
    reader's complaint about a document number that silently lost its tail.

    Raises:
        MrzValueError: for an unrecognised shape, from
            :func:`detect_mrz_format`; otherwise for whatever the chosen
            format's parser refuses, whose message is that reader's own.
    """
    # One materialisation, two readers: the zone is built here rather than
    # inside `detect_mrz_format`, so a generator is not measured and then
    # handed on already empty.
    zone = _zone_of(lines)
    return MRZ_PARSERS[detect_mrz_format(zone)](zone)
