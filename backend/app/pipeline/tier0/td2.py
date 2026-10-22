"""ICAO 9303 TD2 (visa) MRZ layout: where each field sits in a line.

A TD2 machine-readable zone is two lines of exactly :data:`TD2_LINE_LENGTH`
characters each.  The format is the one that sits between the other two: it
has a TD3's *shape* -- line 1 is the document header followed by the holder's
name, line 2 is the identity fields and every printed check digit -- and 36
characters per line where a TD3 has 44.  So the two lines get their own
tables, :data:`TD2_LINE_1` and :data:`TD2_LINE_2`, and :data:`TD2` is both of
them keyed by line, over the *same* dict objects rather than copies.

Positions are **1-indexed and inclusive** -- ``(1, 9)`` is the first nine
characters of the line, the way the standard prints them -- and every one of
the 36 positions of every line belongs to exactly one field.  These tables plus
:data:`TD2_LINE_LENGTH` are the only place in this module where a position is
stated.

**What a TD2 gives up to reach 36 is the optional data, and the whole
difference between this line 2 and a TD3's is the tail after position 28.**
The first 28 positions are the same fields in the same order as a TD3's --
document number and its check digit, nationality, date of birth and its check
digit, sex, date of expiry and its check digit -- and a TD3 then spends 16
positions on a personal number, its check digit and the composite where this
format spends 8 on an optional data field, its own check digit and the
composite.  So the optional data here is **6 characters wide, not 14**, and it
is the one field in this format whose width a reader is most likely to get
wrong by carrying a TD3's number over.

**Five check digits are printed in a TD2 and all five are on line 2, which is
worth stating because a TD1 prints five across two lines and a TD3 prints
five on one.**  They are the document number's digit at 10, the date of
birth's at 20, the date of expiry's at 28, the optional data's at 35 and the
composite at 36.  They are listed here as fields in their own right because
the MRZ prints them inside the 36 characters: position 10 is not part of the
document number (1-9), and a table that left those five positions unclaimed
could not account for the line.  **Line 1 carries no check digit at all** --
its last position is the last filler of the name -- so a reader pointed at the
wrong line here gets a name, and nothing underneath it objects.

**The sex marker at 21 and the nationality at 11-13 are the two fields no
field's own check digit reaches, and the composite is the one digit in this
format whose span is a claim about the standard rather than a consequence of
the layout.**  Every other field with a digit printed beside it is covered by
that digit by construction, because a field's digit sits in the position
straight after the field.  :data:`TD2_COMPOSITE_SPANS` is where 3.10 settled
that claim, and the two paragraphs after this one say how.

**The composite's span is :data:`TD2_COMPOSITE_SPANS`, and 3.10 settled a
disagreement this module used to carry the way 3.7 settled one in
``td1.py``:** the task list states the span as line 1 positions 6-30 plus
line 2 positions 1-7, 9-15 and 19-29, and **those three line 2 spans are
:data:`~app.pipeline.tier0.td1.TD1_COMPOSITE_SPANS`'s line 2 spans copied
verbatim.**  They are not this format's, and the reason is arithmetic rather
than a doubt: applied to a TD2's line 2 they cut the nine-character document
number at position 7, take in the nationality and the sex marker, split the
date of birth across two of the three spans, and stop one character into a
six-character optional data field.  Those are the positions that make a
*TD1's* line 2 whole -- a TD1's line 2 really does hold a date of birth at
1-6, a sex marker at 8 and an optional data field at 19-29 -- and they are
positions nothing could have meant here.

**Three things about this format's own shape say what the span is, and none
of the three is a quotation.**  It **includes every check digit the line
prints** -- positions 10, 20, 28 and 35, the composite at 36 being the fifth
-- which is the rule a TD1's span follows at 15 and 30 of its line 1 and 7
and 15 of its line 2, and the rule a TD3's follows at 10, 20, 28 and 43.  It
**skips the nationality at 11-13 and the sex marker at 21**, which is the
same pair of fields a TD3's span skips at those very positions and the pair a
TD1's skips at 8 and 16-18.  And on line 1 it **reaches the name at 6-36
whole**, because the name is the only field of that line any digit can reach:
line 1 prints none, so the document code and the issuing state are as
unprotected here as they are everywhere else, and 3.9's
:func:`validate_name` is what hands the arithmetic the filler padding it is
computed over.

**So the span is 62 characters, 31 from line 1 and 31 from line 2, and it is
the TD3's own composite with the name in front of it and the last eight
positions of line 2 dropped** -- ``1-10``, ``14-20`` and ``22-35`` here
against ``1-10``, ``14-20`` and ``22-43`` there.  **The task text's line 1
portion is not adopted either**, for the reason 3.7 gave for a cut inside a
field: nothing in the format's shape stops that span five characters into a
31-character name, and a span here is either a run of whole fields or the
positions the standard forces.  **This repository holds no copy of Doc 9303**,
so this is the standard's span as this project states it rather than a list
something here could look up, and a sourced copy of Part 7 is the only thing
that would turn it into one.

**This repository holds no copy of Doc 9303, so these positions are stated as
the standard states them rather than as a list something here could look
up.**  That caveat is the same one ``td1.py`` and ``test_td3.py`` carry, and
it is written down at the moment the claim is made rather than discovered
later: 3.5 wrote a composite span into a docstring, 3.6 carried it forward,
and 3.7 found it wrong and had to take it back.  A layout table is the one
place in this package that cannot be checked by anything underneath it, so it
is the place the caveat belongs.

**The synthetic line is still how the positions are checked, and 3.9 adds a
printed specimen on top of it rather than replacing it.**  Thirty-six distinct
characters, each one naming the position it stands in, catches a slice that
lands a character early or late on a line that is otherwise meaningless; a
*printed* line catches a table that is right about a meaningless line and
wrong about a document.  They fail differently, so both stay.

**A specimen visa is quoted, and 1.6's rule is honoured by deriving the digits
rather than by leaving line 2 unquoted.**  Line 1 prints no check digit at
all, so 3.9 had nothing there to take on trust; **line 2 prints five, so 3.10
confirms three of them against the characters beside them -- the same
arithmetic 3.5 and 3.6 used on a TD1 -- and derives the other two.**  The
optional data's own digit and the composite are computed by
:mod:`app.pipeline.tier0.mrz` and written into the fixture, which makes a
green composite row a claim about this project and never about any visa,
exactly as 1.6 recorded for a TD3's composite.

**Both lines are read, and the arithmetic is nowhere.**  :func:`td2_field` is
the one place a TD2 line is sliced, :data:`TD2_DOCUMENT_CODES` and
:data:`TD2_SEX_MARKERS` are this format's two closed sets, and every field of
both lines is read by a ``parse_*``/``validate_*`` pair underneath
:func:`parse_td2_line_1` and :func:`parse_td2_line_2`.  Every width is read
out of the tables above rather than typed in, every message names a
*document* or a *state* and never a person, and every field comes back
exactly as printed.  The arithmetic stays in
:mod:`app.pipeline.tier0.mrz`, so this module holds no sum, no weights and
no modulo, and it defines no error type of its own.  The two dates are the one
place this format is no longer a width check: 3.11's rule is
:func:`~app.pipeline.tier0.mrz.date_fault`, called from here and from its two
siblings so that a visa, an ID card and a passport are refused for the same
month for the same reason, and the century it leaves open is 3.12's and
3.13's.

**The five printed digits are read by the parsers and judged by nothing, and
that is 2.4's rule kept rather than relaxed.**  The fields the standard
constrains go through their own validators; the digits are taken out of the
line through :func:`td2_field` and carried as the characters the document
printed, so a parse reports what was there and
:func:`td2_check_digit_results` is asked separately whether it adds up.  The
two halves stay two halves, because a caller that could "repair" a printed
digit to make its own verdict pass is the failure 2.14 exists to prevent.

**The name is extracted and not judged, which is ``td3.py``'s rule and not a
new one.**  The standard says where the name sits and how wide it is, and
nothing about the characters, because the names it has to carry are not a set
anyone can enumerate -- so a diacritic, a lower-case read or a space where a
``<`` belongs is an OCR misread to be reported by a flag, not a reason to
drop the document.  :func:`validate_name` therefore judges the field's **width
and nothing else**, and the filler is returned with it: 3.10's composite
covers this field whole, so the padding this function returns is inside its
arithmetic, and a stripped ``<`` would change a digit.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from .mrz import (
    FILLER,
    CheckDigitResult,
    MrzValueError,
    check_digit_results,
    date_fault,
)
from .td3 import (
    MrzDocument,
    normalise_names,
    split_given_names,
    split_name,
    transliterate_names,
)

__all__ = [
    "TD2",
    "TD2_CHECK_DIGIT_FIELDS",
    "TD2_COMPOSITE_SPANS",
    "TD2_DOCUMENT_CODES",
    "TD2_LINE_1",
    "TD2_LINE_2",
    "TD2_LINE_COUNT",
    "TD2_LINE_LENGTH",
    "TD2_SEX_MARKERS",
    "parse_td2",
    "parse_date_of_birth",
    "parse_date_of_expiry",
    "parse_document_code",
    "parse_document_number",
    "parse_issuing_state",
    "parse_name",
    "parse_nationality",
    "parse_optional_data",
    "parse_sex",
    "td2_check_digit_results",
    "td2_composite_input",
    "parse_td2_line_1",
    "parse_td2_line_2",
    "td2_field",
    "validate_date_of_birth",
    "validate_date_of_expiry",
    "validate_document_code",
    "validate_document_number",
    "validate_issuing_state",
    "validate_name",
    "validate_nationality",
    "validate_optional_data",
    "validate_sex",
    "validate_td2_lines",
]

#: Characters in one TD2 line (ICAO 9303, Part 7, "TD2 Format").  36, and not
#: a TD3's 44: the whole of the difference is the optional data field, which is
#: 6 characters here rather than 14.
TD2_LINE_LENGTH = 36

#: Lines in a TD2 machine-readable zone.  Always 2, the same as a TD3 and half
#: a TD1: the name shares line 1 with the document header, which is what makes
#: a visa one line shorter in each direction rather than three lines.
TD2_LINE_COUNT = 2

#: Line 1 -- the document itself and the holder's name, and nothing else.  A
#: TD2 line 1 carries no check digit: its last position is the last filler of
#: the name, which is why the name field runs to the end of the line.
TD2_LINE_1: dict[str, tuple[int, int]] = {
    "document_code": (1, 2),  # "V<" for a visa; the type of document
    "issuing_state": (3, 5),  # 3-letter code of the issuing authority
    "name": (6, 36),  # 31 characters, surname "<<" given names, filler-padded
}

#: Line 2 -- the document number, the holder's identity and all five printed
#: check digits, the composite among them.  Positions 1-28 are the same
#: fields, in the same order, at the same positions as a TD3's line 2; the
#: tail differs, and it is where this format is 8 characters shorter.
TD2_LINE_2: dict[str, tuple[int, int]] = {
    "document_number": (1, 9),  # 9 characters, filler-padded when shorter
    "document_number_check_digit": (10, 10),  # over document_number only
    "nationality": (11, 13),  # 3-letter code of the holder's nationality
    "date_of_birth": (14, 19),  # YYMMDD
    "date_of_birth_check_digit": (20, 20),
    "sex": (21, 21),  # M, F, or < where unspecified
    "date_of_expiry": (22, 27),  # YYMMDD
    "date_of_expiry_check_digit": (28, 28),
    "optional_data": (29, 34),  # 6 characters -- a TD3's personal number is
    # 14, and carrying that number over is the mistake this table exists to
    # prevent
    "optional_data_check_digit": (35, 35),  # over optional_data only
    "composite_check_digit": (36, 36),  # the last position of the last line;
    # which positions it is computed over is 3.10's question, not this table's
}

#: The whole TD2 layout, keyed by line: ``TD2["line_1"]`` and
#: ``TD2["line_2"]``.  These are the *same* dict objects as
#: :data:`TD2_LINE_1` and :data:`TD2_LINE_2`, not copies, so a parser can reach
#: for either name and there is no second table to drift.
TD2: dict[str, dict[str, tuple[int, int]]] = {
    "line_1": TD2_LINE_1,
    "line_2": TD2_LINE_2,
}

#: The document codes a TD2 line 1 may carry, at positions 1-2 (ICAO 9303,
#: Part 7, "TD2 Format").  ``V<`` is what a visa prints: ``V`` for the
#: document type and ``<`` for "no variant".  A bare ``V`` is accepted
#: alongside it for ``td1.py``'s and ``td3.py``'s reason -- the second
#: character is filler, so a code that lost it is the same document rather
#: than a different one -- and the filler's value of zero means dropping it
#: cannot change any digit computed over this line, which
#: ``test_td2.py`` checks with ``mrz``'s own arithmetic rather than asserting.
#: The set is exact and closed: ``P<`` (a passport) and ``I<`` (an identity
#: card) are well-formed MRZ codes belonging to other formats, so a zone that
#: prints one is refused rather than read as a visa.  A frozenset, so no
#: caller can widen it at runtime.
TD2_DOCUMENT_CODES: frozenset[str] = frozenset({"V<", "V"})

#: The sex markers a TD2 line 2 may print at position 21 (ICAO 9303, Part 7,
#: "TD2 Format"): ``M``, ``F``, ``X`` and the filler.  The same four
#: characters :data:`~app.pipeline.tier0.td1.TD1_SEX_MARKERS` and
#: :data:`~app.pipeline.tier0.td3.TD3_SEX_MARKERS` hold, and for the same
#: reason: **the composite skips position 21 and no other digit in this format
#: reaches it**, so this membership test is the only judgement any arithmetic
#: in this project will ever make about the character.  A rule as loose as "one
#: uppercase letter, or the filler" would wave ``N`` and ``Q`` through on
#: precisely the field nothing else checks.  The two errors are not symmetric
#: and the set goes against the cheaper one: dropping ``"X"`` refuses a visa
#: that is well-formed, which is the same failure as a nationality list with
#: one country missing and the one :func:`validate_nationality` refuses to
#: make; keeping ``"X"`` accepts a marker no visa may print, in a field a
#: rules engine (Part 12) can flag and a reader cannot.  **This repository
#: holds no copy of the standard**, so the set is the format table's as this
#: project states it and not a list checked against it -- a frozenset, so no
#: caller can widen what a visa may print at run time.
TD2_SEX_MARKERS: frozenset[str] = frozenset({"M", "F", "X", FILLER})

#: The 62 characters the composite check digit printed at line 2 position 36
#: is computed over, as ``(line, first position, last position)`` triples in
#: the order the standard concatenates them: the whole of line 1's name at
#: 6-36, then line 2's 1-10, 14-20 and 22-35.  Line 1 supplies 31 characters
#: and line 2 supplies 31, and a TD2 composite is -- like a TD1's -- the only
#: digit in this package computed over characters from two different lines.
#
#: **Positions on a named line rather than field names, and here that is a
#: choice rather than a necessity.**  ``td3.py`` can name its 39 characters
#: as eight whole fields; so can this, because every span above is a run of
#: whole fields -- the name, the document number with its digit, the date of
#: birth with its digit, and the date of expiry, the optional data and their
#: two digits as one run.  It is stated as positions because the module
#: docstring's argument is *about* those positions, and because a name-only
#: table could not show that the nationality at 11-13 and the sex marker at 21
#: are the two fields it skips.
#
#: **It is stated here rather than derived from the layout, for
#: :data:`~app.pipeline.tier0.td3.TD3_CHECK_DIGIT_FIELDS`'s reason:** the
#: tables say where a field sits, and only the standard says which of those
#: positions a given digit is computed over.  Position 10 of line 2, for
#: instance, is the document number's tenth character *and* the tenth character
#: of the composite, and nothing in the layout distinguishes them.  The gaps
#: are as much a part of the claim as the spans: the document code, the
#: issuing state, the nationality and the sex marker are outside it, and so is
#: the composite's own position.
TD2_COMPOSITE_SPANS: tuple[tuple[str, int, int], ...] = (
    ("line_1", 6, 36),
    ("line_2", 1, 10),
    ("line_2", 14, 20),
    ("line_2", 22, 35),
)

#: The five printed check digits of a TD2, each paired with the characters it
#: is computed over.  Triples of ``(label, field the characters come from,
#: field the printed digit comes from)``, in printed order -- all five are on
#: line 2, at 10, 20, 28, 35 and 36.  **The same shape as
#: :data:`~app.pipeline.tier0.td3.TD3_CHECK_DIGIT_FIELDS`, down to the
#: ``None``:** the composite's second element is ``None`` because its
#: characters are not printed as one field anywhere.  They are
#: :data:`TD2_COMPOSITE_SPANS` read out and joined, and they cross a line
#: boundary as well as a field boundary, so a name that said where they came
#: from would be lying twice.  Everything else is a pair of real fields, and a
#: pairing that named a field the layout does not have raises rather than
#: reporting a field nobody printed.
TD2_CHECK_DIGIT_FIELDS: tuple[tuple[str, str | None, str], ...] = (
    ("document_number", "document_number", "document_number_check_digit"),
    ("date_of_birth", "date_of_birth", "date_of_birth_check_digit"),
    ("date_of_expiry", "date_of_expiry", "date_of_expiry_check_digit"),
    ("optional_data", "optional_data", "optional_data_check_digit"),
    ("composite", None, "composite_check_digit"),
)

def validate_td2_lines(lines: Iterable[str]) -> tuple[str, str]:
    """Return ``lines`` as the two TD2 lines, or raise unless it is a TD2 zone.

    The TD2 twin of
    :func:`~app.pipeline.tier0.td3.validate_td3_lines`, and 3.14 is what
    brought it: a TD2 machine-readable zone is :data:`TD2_LINE_COUNT` lines
    of :data:`TD2_LINE_LENGTH` characters, and this is where that shape is
    said in a check rather than in a comment.  ``lines`` may be any iterable
    of strings and the two are returned in printed order, so a caller never
    indexes for itself.

    **The two lines are the same count as a TD3's and a different width, and
    that is the whole reason this gate is worth having.**  3.10 showed a
    TD2 line 1 parses as a TD2 line 2 without complaint -- its 1-9 read as a
    short padded number, its 11-13 as ``"SON"``, its 21 as an ``"M"`` -- and
    :func:`~app.pipeline.tier0.mrz.check_digit` does not object either.  Only
    a layer that knows a TD2 is 36 characters wide and not 44 can tell those
    two mistakes apart, and this is it.

    What the characters *say* is not checked here: not that they are MRZ
    characters, not that the document code is a visa, and not a check digit.
    A shape that is right while its contents are wrong is still a zone worth
    parsing and flagging.

    Raises:
        MrzValueError: unless ``lines`` is an iterable of exactly
            :data:`TD2_LINE_COUNT` strings, each exactly
            :data:`TD2_LINE_LENGTH` characters long.  A ``MrzValueError`` is
            a ``ValueError``, so ``except ValueError`` catches it too, and
            it is the one type this raises: a ``None`` zone, a single string
            where two lines were expected, and a line that is not a string
            are all reported as this, rather than escaping as a bare
            ``TypeError`` a caller catching ``MrzValueError`` would never
            see.  **The messages carry the shape and never the characters**,
            because the lines are the identity data the screening is about.
    """
    # Checked before the iteration below: a string is a sequence of
    # one-character lines, so iterating it would report 36 lines and point at
    # the wrong mistake entirely.
    if isinstance(lines, str):
        raise MrzValueError(
            f"a TD2 machine-readable zone is {TD2_LINE_COUNT} lines, "
            f"not one string of {len(lines)} characters"
        )
    try:
        zone = tuple(lines)
    except TypeError:
        raise MrzValueError(
            "a TD2 machine-readable zone must be a sequence of lines, "
            f"not {type(lines).__name__}"
        ) from None
    if len(zone) != TD2_LINE_COUNT:
        raise MrzValueError(
            f"a TD2 machine-readable zone is {TD2_LINE_COUNT} lines, "
            f"not {len(zone)}"
        )
    # 1-indexed, like every position in this module, so a message naming
    # "line 2" means the line the standard calls line 2.
    for number, line in enumerate(zone, start=1):
        if not isinstance(line, str):
            raise MrzValueError(
                f"TD2 line {number} must be a string, not {type(line).__name__}"
            )
        if len(line) != TD2_LINE_LENGTH:
            raise MrzValueError(
                f"TD2 line {number} is {len(line)} characters, "
                f"not {TD2_LINE_LENGTH}"
            )
    line_1, line_2 = zone
    return line_1, line_2


def _checked_line(line: str, number: int) -> str:
    """Return ``line`` if it is a TD2 line of 36 characters, else raise.

    The width check :func:`parse_td2_line_1` holds, and it is the TD2 twin of
    ``td1.py``'s: the message *is* the diagnosis and there is no reason for
    it to be written twice.  It exists at all only because there is no zone
    gate yet -- one that will cover the whole zone the way
    :func:`~app.pipeline.tier0.td3.validate_td3_lines` covers a TD3's -- and
    until that arrives a 35-character line 1 reads as a visa whose name sliced
    to thirty characters, which is a report of what the document printed that
    has quietly lost a position.  When the gate takes this over, the
    assembler loses it.

    The type check comes first and is not decoration: :func:`len` raises a
    bare ``TypeError`` on ``None``, and ``bytes`` *has* a length, so a check
    that measured before it tested the type would measure an argument the
    package's error type never mentions.

    Raises:
        MrzValueError: if ``line`` is not a string, or is not
            :data:`TD2_LINE_LENGTH` characters.  The message names the line
            number and the length it was given, and **never the characters**:
            the line is the identity data the screening is about.
    """
    if not isinstance(line, str):
        raise MrzValueError(f"a TD2 line must be a string, not {type(line).__name__}")
    if len(line) != TD2_LINE_LENGTH:
        raise MrzValueError(
            f"TD2 line {number} is {len(line)} characters, not {TD2_LINE_LENGTH}"
        )
    return line


def td2_field(line: str, layout: dict[str, tuple[int, int]], name: str) -> str:
    """Return the characters ``name`` occupies in ``line``, by way of ``layout``.

    The one place in this module where a TD2 line is sliced, and the third of
    the per-format twins of ``td3.py``'s function of the same name.  Positions
    are 1-indexed and inclusive, so the ``- 1`` below is the whole
    conversion.  ``layout`` is :data:`TD2_LINE_1` or :data:`TD2_LINE_2`, so
    the field's width comes from the table rather than from the caller, and a
    reader written as a hand-written ``line[0:2]`` would be a second source
    of positions that the table could not contradict.

    This checks nothing about the field and nothing about the line's width.
    It hands back the characters the layout says are there, in both
    directions -- a field one character too wide and one too narrow are the
    same mistake, and only the judgement that follows can tell them apart.

    Raises:
        MrzValueError: if ``line`` is not a string, or ``layout`` has no
            field called ``name``.  A ``KeyError`` out of the lookup and a
            ``TypeError`` out of the slice are both the kind of built-in
            error 1.9 forbids, and both are a caller mistake rather than a
            bad document.
    """
    if not isinstance(line, str):
        raise MrzValueError(f"a TD2 line must be a string, not {type(line).__name__}")
    if name not in layout:
        raise MrzValueError(f"no TD2 field named {name!r}")
    start, end = layout[name]
    return line[start - 1 : end]


def _readable_codes() -> str:
    """The accepted document codes, sorted, for a message.

    Sorted so the message is the same string every time, which keeps a log
    greppable; never used to decide anything, only to say what was expected.
    """
    return ", ".join(repr(code) for code in sorted(TD2_DOCUMENT_CODES))


def _readable_markers() -> str:
    """The accepted sex markers, sorted, for a message.

    The twin of :func:`_readable_codes` and never used to decide anything:
    the decision is the membership test in :func:`validate_sex`, and this
    only says what was expected, in the same sorted order every time so a log
    stays greppable.
    """
    return ", ".join(repr(marker) for marker in sorted(TD2_SEX_MARKERS))


def validate_document_code(code: str) -> str:
    """Return ``code`` if it is a TD2 visa document code, else raise.

    The same closed check ``td1.py`` and ``td3.py`` make over a different
    set, and closed for the same reason: ``P<`` (a passport, two lines of 44)
    and ``I<`` (an identity card, three lines of 30) are well-formed MRZ
    codes, not misspellings, so the answer is to refuse the zone rather than
    read a visa out of a document that is not one.

    **The message names the code it was given, which is the one place this
    format's no-echo rule does not reach, and the cost of that is worth
    stating rather than leaving to be discovered.**  ``td1.py``'s exception
    is that two characters in the document-code position describe a
    *document*, and that is exactly what they describe here -- unless the
    caller handed over the wrong line, in which case the same two characters
    are the first two of a holder's document number.  The echo stays
    because the caller has the whole line in hand already (it handed it
    over), the message is what tells an operator the zone was read as the
    wrong format, and the alternative -- a message naming only what was
    expected -- costs the diagnosis to protect two characters from a log
    line that would have held forty-four of them.

    Raises:
        MrzValueError: for any other value, including one that is not a
            string -- the membership test answers ``False`` for a non-string
            rather than raising, so this is the one failure and it is the
            package's one error type.
    """
    if code in TD2_DOCUMENT_CODES:
        return code
    raise MrzValueError(
        f"a TD2 visa document code is {_readable_codes()}, not {code!r}"
    )


def parse_document_code(line: str) -> str:
    """Return the document code printed in positions 1-2 of ``line``.

    The first field :func:`parse_td2_line_1` reads, and the first thing a TD2
    character can *say*: this line is a TD2 at all, and it is a visa rather
    than a passport or a card.  The positions come from :data:`TD2_LINE_1`
    through :func:`td2_field`, so there is no ``line[0:2]`` here, and the
    slice is handed straight to :func:`validate_document_code` so the reader
    and the judgement cannot disagree about what a visa is.

    ``line`` is expected to be the 36 characters :data:`TD2_LINE_1` describes,
    which :func:`parse_td2_line_1` checks before calling this; the width is
    not repeated here, because a line that is too short is a shape problem
    and not a document-code problem.  It is still total over its input: a
    line too short to hold a code slices to whatever it has, which is then
    not a code, and a line that is not a string is reported by
    :func:`td2_field` rather than left to raise a bare ``TypeError``.

    **This field is also the only thing standing between line 1 and line 2,
    and it does not stand between them alone.**  A TD2's line 2 begins with
    the document number, so a number whose first two characters are ``V<``
    is a line 1 as far as this reader is concerned; the issuing state three
    positions later is what catches it, and
    ``test_a_number_beginning_with_the_visa_code_is_caught_by_the_state_instead``
    says so in its own name.  Two fields, two different rules, and neither
    of them a check digit -- because this line prints none.

    Raises:
        MrzValueError: if ``line`` is not a string, or the characters it
            prints at positions 1-2 are not in :data:`TD2_DOCUMENT_CODES`.
    """
    return validate_document_code(td2_field(line, TD2_LINE_1, "document_code"))


def _is_uppercase_letter(character: str) -> bool:
    """Whether ``character`` is one of ``A``-``Z``, the MRZ letter set.

    Spelled out rather than taken from :data:`string.ascii_uppercase` so the
    rule reads as the standard states it -- three characters, each one an
    uppercase letter -- rather than as a range that happens to end at the
    right place.  A private copy, as in ``td1.py`` and ``td3.py``: the
    formats are separate modules whose rules are allowed to differ, and a
    shared helper would make a change to one of them a change to all three.
    """
    return len(character) == 1 and "A" <= character <= "Z"


def validate_issuing_state(code: str) -> str:
    """Return ``code`` if it is a well-formed TD2 issuing state, else raise.

    The whole of the rule the standard states for positions 3-5: exactly as
    wide as :data:`TD2_LINE_1` says the field is, and every one of those
    characters one of ``A``-``Z``.  The width is *read out of the table*
    rather than typed in as a 3, so the layout stays the only place a
    position is stated and the message cannot describe a width the layout
    does not have.

    Well-formedness is the whole of the judgement, and a code list is
    deliberately absent, for ``td1.py``'s reason: ``IND`` is three uppercase
    letters and is accepted, because ISO 3166-1 alpha-3 assigns ``IND`` to
    India, so any conforming list of issuing states contains it and a list
    without one would refuse every genuine Indian visa.  Recognising a
    state is a Tier 0 policy question, answered by a code list that has to be
    sourced rather than remembered, and it belongs to the rules engine.

    The message carries the state, which names a *state* and not a holder,
    and the no-echo rule stops where ``td1.py``'s does.

    Raises:
        MrzValueError: unless ``code`` is a string of exactly the layout's
            width whose every character is an uppercase letter, which covers
            the misreads this field actually produces: a digit read for a
            letter, a lower-case read, a filler or a space where a letter
            belongs, and a diacritic carried across from the printed name.  A
            value that is not a string is reported as this too rather than
            escaping as a bare ``TypeError``.
    """
    if not isinstance(code, str):
        raise MrzValueError(
            f"an issuing state must be a string, not {type(code).__name__}"
        )
    start, end = TD2_LINE_1["issuing_state"]
    width = end - start + 1
    if len(code) != width or not all(_is_uppercase_letter(letter) for letter in code):
        raise MrzValueError(
            f"a TD2 issuing state is {width} uppercase letters (A-Z) at positions "
            f"{start}-{end}, not {code!r}"
        )
    return code


def parse_issuing_state(line: str) -> str:
    """Return the issuing state printed in positions 3-5 of ``line``.

    The second field :func:`parse_td2_line_1` reads and the same shape as
    :func:`parse_document_code`: the positions come from
    :data:`TD2_LINE_1` through :func:`td2_field`, so there is no
    ``line[2:5]`` here, and the slice is handed straight to
    :func:`validate_issuing_state`.

    **On a TD2 this field is also the second half of what tells the two
    lines apart**, where a TD1's line 1 reaches a document number and does
    not need the help: positions 3-5 of a TD2 line 2 are the third through
    fifth characters of a document number, so a number that happens to
    start ``V<`` and then digits is refused here rather than being read as a
    state.

    Raises:
        MrzValueError: if ``line`` is not a string, or the characters it
            prints at positions 3-5 are not a well-formed issuing state.
    """
    return validate_issuing_state(td2_field(line, TD2_LINE_1, "issuing_state"))


def validate_name(name: str) -> str:
    """Return ``name`` if it is a TD2 line 1 printed one, else raise.

    **The width is the whole of the judgement, and that is
    :func:`~app.pipeline.tier0.td3.parse_name`'s rule rather than a new
    one.**  The standard says where the name sits and how wide it is, and
    nothing about the characters, because the names it has to carry are not
    a set anyone can enumerate.  A diacritic, a lower-case read or a space
    where a ``<`` belongs is an OCR misread: refusing the document over one
    would leave nothing for a flag to point at and turn a readable name into
    a dropped visa.  So this returns whatever the line printed, padding
    included.

    **The padding is load-bearing, and this is the one place in the format
    where it can be shown to be.**  A TD3's name runs to position 44 and a
    TD2's to position 36, so a TD2's name is 31 characters where a TD3's is
    39 -- and 3.10 settled that the composite's first span is this field
    whole, at 6-36.  A stripped filler here would change the digit
    :func:`td2_composite_input` assembles, which is why nothing here tidies
    the field and why an all-filler name is a *value* a visa may print rather
    than an absence to be tidied away.

    The width is read out of :data:`TD2_LINE_1` rather than typed in, for
    every width's reason.

    Raises:
        MrzValueError: unless ``name`` is a string of exactly the layout's
            width.  The message carries the positions and the two lengths and
            **never the name**: this is the identity data the screening is
            about, it is the one field on this line where 2.2's rule would
            have been easiest to break by accident, and the sibling formats'
            habit of naming the value they rejected stops at the name.
    """
    if not isinstance(name, str):
        raise MrzValueError(f"a TD2 name must be a string, not {type(name).__name__}")
    start, end = TD2_LINE_1["name"]
    width = end - start + 1
    if len(name) != width:
        raise MrzValueError(
            f"a TD2 name field is positions {start}-{end}, {width} characters, "
            f"not {len(name)}"
        )
    return name


def parse_name(line: str) -> str:
    """Return the name printed in positions 6-36 of ``line``, raw.

    The third field :func:`parse_td2_line_1` reads and the first one that is
    a *person* rather than a document, which is why the module's care about
    messages matters most here.  Same shape as the other two readers -- the
    positions come from :data:`TD2_LINE_1` through :func:`td2_field`, so
    there is no ``line[5:36]`` in this module, and the slice is handed
    straight to :func:`validate_name`, which is where the width is judged
    and where the decision to judge nothing else is written down.

    Nothing is split, stripped or case-folded: a surname and given names are
    a later task's question, and this line's whole name is one field either
    way.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if it
            stops before the end of the name field.  The message carries the
            positions and the two lengths and never the name.
    """
    return validate_name(td2_field(line, TD2_LINE_1, "name"))


def parse_td2_line_1(line: str) -> Mapping[str, str]:
    """Return line 1 of a TD2 zone as its three fields, keyed by name.

    The TD2 twin of ``td1.py``'s :func:`~app.pipeline.tier0.td1.
    parse_td1_line_1`, and nothing more than it: it slices no line for
    itself, judges nothing of its own beyond the line's width, and every
    field is read through the reader or :func:`td2_field` that owns it.

    **The keys are in printed order**, for ``td1.py``'s reason, and the
    returned object is built in that order rather than sorted afterwards, so
    a caller reading the mapping top to bottom reads the document and then
    the person it belongs to.  Three fields rather than six is the whole of
    a TD2 line 1: **this line prints no check digit**, so there is no
    printed digit here for a caller to mistake for a value this module
    judged, and 3.10's five are all on line 2.

    **The task list's 3.9 named this line's fields as the document code,
    the issuing state, the document number and the optional data with its own
    check digit, and that list is a TD1's.**  The document number and its
    digit are at 1-10 of *line 2* in this format, and a TD2's line 1 holds
    the holder's **name** at 6-36 instead -- the field a visa MRZ most
    visibly carries and the one the task text named nowhere between 3.9 and
    3.10.  The list is settled here against the table above, which 3.8
    pinned, and the task text has been corrected to match; ``td2.py`` reads
    the standard's line rather than the task's.

    **The returned mapping is read-only, for ``td1.py``'s reason:** this is
    the evidence of what the document printed, and a caller that could edit
    it would be able to make a cleaned-up field look like a read one.

    **No record type is created here, and that is still 3.14's to decide.**
    A TD2 record is the TD3 record with a ``format`` discriminator, so a
    second shape now would mean 3.14 has to merge two.  Line 1's fields go
    in their own mapping, keyed by the layout's own field names, which is
    the shape that survives that merge.

    **The line's width is checked by :func:`_checked_line`**, for
    ``td1.py``'s reason: the zone gate that will cover both lines takes this
    over rather than two lines each repeating it.

    Raises:
        MrzValueError: for a line that is not a string, a line that is not
            :data:`TD2_LINE_LENGTH` characters, then whichever field reader
            refuses first, in printed order.  The error is the reader's own,
            unwrapped and unedited, so its message names the field and the
            width it wanted and never the characters around it.
    """
    line = _checked_line(line, 1)
    return MappingProxyType(
        {
            "document_code": parse_document_code(line),
            "issuing_state": parse_issuing_state(line),
            "name": parse_name(line),
        }
    )


def validate_document_number(number: str) -> str:
    """Return ``number`` if a TD2 line 2 printed one, else raise.

    The same rule ``td1.py`` and ``td3.py`` apply to the same nine positions,
    and the same two reasons for it.  The width is read out of
    :data:`TD2_LINE_2` rather than typed in as a 9, so the layout stays the
    only place a position is stated.  **"Non-empty" means non-empty once the
    filler is taken out**: the field is nine characters wide whatever the
    number is and a shorter number is padded on the right, so ``"L898902C3"``
    is a complete number, ``"L8989<<<"`` is a complete shorter one, and
    ``"<<<<<<<<<"`` is no number at all -- a plain ``if not number`` would
    accept all three.  The emptiness is judged *before* the width, so a field
    that holds nothing is reported as the missing number it is rather than as
    a line that stopped early.

    **The number is returned exactly as printed, padding included, and that is
    load-bearing twice over.**  Position 10 is the check digit over positions
    1-9 *as printed*, and the filler
    (:data:`~app.pipeline.tier0.mrz.FILLER`) is a character that digit is
    computed over, not tidying waiting to happen.  And positions 1-9 are
    inside :data:`TD2_COMPOSITE_SPANS`, so a stripped number would change the
    composite as well.

    **Nothing about the characters is judged, and that is the limit of the
    task rather than an oversight.**  A field carrying a space is a misread --
    there is no space in the MRZ alphabet -- but it is not empty, and
    :func:`~app.pipeline.tier0.mrz.check_digit` is what raises on it, so the
    failure is reported rather than lost.  Reading a number is not verifying
    one.

    **The message does not carry the number**, where the document-code and
    issuing-state messages do carry theirs.  A document number is the
    identifier the screening is about and it is unique to one holder's
    document, so this names the width it wanted and, for the empty field, the
    character that filled it -- which is the whole of the diagnosis -- and
    neither of those is the value.

    Raises:
        MrzValueError: unless ``number`` is a string of exactly the layout's
            width that prints at least one character other than the filler.
            A value that is not a string is reported as this too rather than
            escaping as a bare ``TypeError`` -- ``bytes`` being the case that
            matters, since a byte string has a length and would pass a
            validator that measured before it checked the type.
    """
    if not isinstance(number, str):
        raise MrzValueError(
            f"a TD2 document number must be a string, not {type(number).__name__}"
        )
    start, end = TD2_LINE_2["document_number"]
    if not number.replace(FILLER, ""):
        raise MrzValueError(
            f"a TD2 document number must print at least one character that is "
            f"not the filler, but positions {start}-{end} held nothing but it"
        )
    width = end - start + 1
    if len(number) != width:
        raise MrzValueError(
            f"a TD2 document number is {width} characters (positions "
            f"{start}-{end}), not {len(number)}"
        )
    return number


def parse_document_number(line: str) -> str:
    """Return the document number printed in positions 1-9 of ``line``.

    The first field :func:`parse_td2_line_2` reads and the first thing on
    this line that says what the document *is* rather than who it is about.
    Same shape as every other reader here: the positions come from
    :data:`TD2_LINE_2` through :func:`td2_field`, so there is no
    ``line[0:9]`` in this module, and the slice is handed straight to
    :func:`validate_document_number` so the reader and the judgement cannot
    disagree.

    **This is the field that tells a TD2's two lines apart, and it is the
    mirror image of what 3.9 said about the document code.**  Line 1 opens
    with a code this reader would refuse unless the number began ``V<``; line
    2 opens with a number, and a document number is filler-padded and may be
    as short as an authority likes.  **Neither side of that test catches a
    mislaid line, and saying so here is cheaper than leaving it to be
    discovered:** a line 1's first nine characters are a code, a state and
    the first four characters of a name, none of them filler, so they read as
    a short padded number and this reader accepts them.  What tells a TD2's
    two lines apart is 3.9's pair -- the document code and the issuing state
    -- and both of those are on line 1.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 1-9 are not a document number.
            The message carries the positions, the width and what was
            expected, and **never the number**.
    """
    return validate_document_number(td2_field(line, TD2_LINE_2, "document_number"))


def validate_nationality(code: str) -> str:
    """Return ``code`` if it is a well-formed TD2 nationality, else raise.

    Positions 11-13, and the whole of the rule the standard states for them
    is the rule :func:`validate_issuing_state` states for a state's three
    characters: exactly as wide as :data:`TD2_LINE_2` says the field is, and
    every one of those characters one of ``A``-``Z``.  The width is read out
    of the table for the same reason it is everywhere else here.

    **``IND`` is accepted, and that is ``td1.py``'s and ``td3.py``'s decision
    carried over rather than re-derived.**  "Three uppercase letters" and
    "reject ``IND``" cannot both hold: ISO 3166-1 alpha-3 assigns ``IND`` to
    India, so every conforming list of nationality codes contains it, and a
    list without one refuses every genuine Indian visa.  **No list of
    nationality codes ships here**, which is the decision rather than an
    omission -- a second list is a second thing to be sourced rather than a
    second rule to invent, and recognising a nationality is a Tier 0 policy
    question belonging to the rules engine (Part 12).

    **The standard gives this field no "unspecified" value, so the filler is
    not a special case**, for ``td1.py``'s reason: there is no such thing as
    an unknown nationality in a TD2 zone, so ``"<<<"`` is a misread rejected
    on the ordinary ground and *not* a missing value, which is
    :func:`validate_document_number`'s rule and does not repeat here.

    **The message does not carry the code, where the issuing state's message
    does carry a state.**  Both codes are the same shape, and the difference
    is whose property each is: a document *state* describes the document, a
    nationality describes the **holder**.  This names the positions, the width
    and the alphabet, and never what it found.

    Raises:
        MrzValueError: unless ``code`` is a string of exactly the layout's
            width whose every character is an uppercase letter, which covers
            the misreads this field actually produces: a digit read for a
            letter, a lower-case read, the filler or a space where a letter
            belongs, and a diacritic carried across from the printed name.  A
            value that is not a string is reported as this too rather than
            escaping as a bare ``TypeError``.
    """
    if not isinstance(code, str):
        raise MrzValueError(
            f"a TD2 nationality must be a string, not {type(code).__name__}"
        )
    start, end = TD2_LINE_2["nationality"]
    width = end - start + 1
    if len(code) != width or not all(_is_uppercase_letter(letter) for letter in code):
        raise MrzValueError(
            f"a TD2 nationality is {width} uppercase letters (A-Z) at positions "
            f"{start}-{end}, and those positions printed something else"
        )
    return code


def parse_nationality(line: str) -> str:
    """Return the nationality printed in positions 11-13 of ``line``.

    The second field :func:`parse_td2_line_2` reads, and the same shape as
    :func:`parse_document_number`: the positions come from
    :data:`TD2_LINE_2` through :func:`td2_field`, and the slice is handed
    straight to :func:`validate_nationality`.

    **Handed a line 1, this returns three characters of the holder's *name*,
    and accepts them -- the one field of this assembler where a wrong line is
    not merely uncaught but unanswerable.**  An MRZ prints a name in capitals,
    so the "``SON``" at positions 11-13 of a line 1 is three uppercase letters
    and this has nothing to object to; it is ``td1.py``'s
    :func:`~app.pipeline.tier0.td1.parse_nationality` situation one format
    along, and the answer there is the answer here.  The honest statement is
    that this assembler is safe only when handed the right line, which is
    3.14's caller to guarantee, and that **no digit here would object
    either**: :data:`TD2_COMPOSITE_SPANS` skips positions 11-13 and 21, so a
    nationality that changed on a genuine visa is the rules engine's finding
    (Part 12) and never a check digit's.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 11-13 are not a well-formed
            nationality.  The message carries the positions, the width and the
            alphabet, and **neither the nationality nor anything else on the
            line**.
    """
    return validate_nationality(td2_field(line, TD2_LINE_2, "nationality"))


def validate_date_of_birth(date: str) -> str:
    """Return ``date`` if a TD2 line 2 printed a date of birth, else raise.

    Positions 14-19, **the width read out of :data:`TD2_LINE_2` rather than
    typed in**, for :func:`validate_issuing_state`'s reason, and the month and
    day judged by :func:`~app.pipeline.tier0.mrz.date_fault` -- 3.11's rule,
    kept in :mod:`app.pipeline.tier0.mrz` so the three formats cannot disagree
    about what a day is.  ``"993199"`` and ``"013200"`` are refused, and they
    are refused *by name* rather than reported as an unreadable line, which is
    the distinction 3.11 exists to draw: a month of 31 is a reading this
    project can contradict, where a letter in the field is a reading only the
    check digit beside it can contradict.  ``"AAAAAA"`` and ``"<<<<<<"`` are
    still accepted, for that reason.

    The width is *read out of* :data:`TD2_LINE_2` rather than typed in as a
    6, for :func:`validate_issuing_state`'s reason.  What the width is for is
    :func:`validate_document_number`'s reason restated on a field that cannot
    be short by padding -- a line that stopped before position 19 slices to a
    short field, and that is a line that stopped early rather than a document
    carrying a five-character date of birth.

    **The date is returned exactly as printed, which is load-bearing rather
    than untidy.**  Position 20 is the check digit over positions 14-19 *as
    printed*, and the specimen is the proof:
    :func:`~app.pipeline.tier0.mrz.check_digit` on ``"740812"`` is the ``2``
    the specimen prints there.  A space, a diacritic or a stray filler is
    carried rather than tidied, so 3.10's arithmetic sees the characters the
    document printed -- and :func:`~app.pipeline.tier0.mrz.check_digit` is
    what raises on the ones outside the MRZ alphabet, which is a finding
    rather than a lost document.

    **The message does not carry the date**, for the holder's reason: a date
    of birth is a property of the holder, not of the document.  This names the
    width it wanted and the positions it looked at, and stops.

    Raises:
        MrzValueError: unless ``date`` is a string of exactly the layout's
            width.  A value that is not a string is reported as this too,
            rather than escaping as a bare ``TypeError`` a caller catching
            ``MrzValueError`` would never see.
    """
    if not isinstance(date, str):
        raise MrzValueError(
            f"a TD2 date of birth must be a string, not {type(date).__name__}"
        )
    start, end = TD2_LINE_2["date_of_birth"]
    width = end - start + 1
    if len(date) != width:
        raise MrzValueError(
            f"a TD2 date of birth is {width} characters (positions "
            f"{start}-{end}), not {len(date)}"
        )
    fault = date_fault(date)
    if fault is not None:
        raise MrzValueError(
            f"a TD2 date of birth (positions {start}-{end}) has a {fault} that "
            f"no date can print"
        )
    return date


def parse_date_of_birth(line: str) -> str:
    """Return the date of birth printed in positions 14-19 of ``line``.

    The third field :func:`parse_td2_line_2` reads, and the same shape as the
    two before it: the positions come from :data:`TD2_LINE_2` through
    :func:`td2_field`, so there is no ``line[13:19]`` here, and the slice is
    handed straight to :func:`validate_date_of_birth`.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 14-19 are not a date of
            birth's width.  The message carries the positions and the two
            lengths and never the date.
    """
    return validate_date_of_birth(td2_field(line, TD2_LINE_2, "date_of_birth"))


def validate_sex(marker: str) -> str:
    """Return ``marker`` if a TD2 line 2 printed a sex marker, else raise.

    **The closed set is a decision this format makes rather than inherits,
    and it is the same decision ``td1.py`` and ``td3.py`` make over the same
    four characters.**  A rule as loose as "one uppercase letter, or the
    filler" would accept ``N`` and ``Q`` on the one field of line 2 that no
    check digit in this project reaches: :data:`TD2_COMPOSITE_SPANS` skips
    position 21, and neither date's own digit covers it.  So
    :data:`TD2_SEX_MARKERS` is the whole of the judgement this format makes
    about that character, and a wrong answer here is the only wrong answer a
    forgery could produce without any digit noticing.

    **The set is stated from a standard this repository does not hold**, and
    the cost of being wrong is written down at the constant rather than left
    to be discovered: dropping ``"X"`` refuses a visa that is well-formed,
    which is the same failure as a nationality list with one country missing;
    keeping it accepts a marker no visa may print, in a field only a rules
    engine (Part 12) can flag.  The set goes against the cheaper error, and
    if a sourced copy of Part 7 shows the field reading ``M``, ``F`` or ``<``
    alone, dropping ``"X"`` is a one-character edit and nothing else in this
    module moves.

    **The message names the set and never the marker**, for
    :func:`validate_nationality`'s reason: a sex marker is a property of the
    holder, and the set is a list this code invented rather than a thing any
    visa printed.

    Raises:
        MrzValueError: for anything not in :data:`TD2_SEX_MARKERS`, including
            a non-string -- the membership test answers ``False`` for a
            non-string rather than raising, so this is the one failure and it
            is the package's one error type.
    """
    if marker in TD2_SEX_MARKERS:
        return marker
    raise MrzValueError(
        f"a TD2 sex marker is one of {_readable_markers()}, and positions "
        f"{TD2_LINE_2['sex'][0]} printed something else"
    )


def parse_sex(line: str) -> str:
    """Return the sex marker printed in position 21 of ``line``.

    The fourth field :func:`parse_td2_line_2` reads and the only one this
    format reads by membership rather than by width, for
    :func:`validate_sex`'s reason: nothing else here can check it.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if the
            character it prints at position 21 is not a marker a visa may
            print.  The message names the set and never the marker.
    """
    return validate_sex(td2_field(line, TD2_LINE_2, "sex"))


def validate_date_of_expiry(date: str) -> str:
    """Return ``date`` if a TD2 line 2 printed a date of expiry, else raise.

    Positions 22-27, and :func:`validate_date_of_birth`'s rule for the
    second of the two dates: the width read out of :data:`TD2_LINE_2` rather
    than typed in as a 6, so a message cannot describe a width the layout does
    not have, and the month and day judged by
    :func:`~app.pipeline.tier0.mrz.date_fault`, which does not know which of
    the two dates it is looking at.  3.13's century rule for an expiry is a
    question that check does not touch.

    **The date is returned exactly as printed**, for the same reason the date
    of birth is: position 28 is the check digit over positions 22-27 *as
    printed*, and the specimen is the proof --
    :func:`~app.pipeline.tier0.mrz.check_digit` on ``"120415"`` is the ``9``
    the specimen prints there.

    **The message does not carry the date**, and it says less than the date of
    birth's does on purpose: a date of expiry is a property of the *document*
    rather than the holder, but it still dates the holder's presence in a
    country, and nothing in this module's messages is read by a wider audience
    than an operator who already holds the document.

    Raises:
        MrzValueError: unless ``date`` is a string of exactly the layout's
            width, including a non-string, reported as this rather than
            escaping as a bare ``TypeError``.
    """
    if not isinstance(date, str):
        raise MrzValueError(
            f"a TD2 date of expiry must be a string, not {type(date).__name__}"
        )
    start, end = TD2_LINE_2["date_of_expiry"]
    width = end - start + 1
    if len(date) != width:
        raise MrzValueError(
            f"a TD2 date of expiry is {width} characters (positions "
            f"{start}-{end}), not {len(date)}"
        )
    fault = date_fault(date)
    if fault is not None:
        raise MrzValueError(
            f"a TD2 date of expiry (positions {start}-{end}) has a {fault} that "
            f"no date can print"
        )
    return date


def parse_date_of_expiry(line: str) -> str:
    """Return the date of expiry printed in positions 22-27 of ``line``.

    The fifth field :func:`parse_td2_line_2` reads, and the same shape as
    every other reader here: the positions come from :data:`TD2_LINE_2`
    through :func:`td2_field`, so there is no ``line[21:27]`` here, and the
    slice is handed straight to :func:`validate_date_of_expiry`.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 22-27 are not a date of
            expiry's width.  The message carries the positions and the two
            lengths and never the date.
    """
    return validate_date_of_expiry(td2_field(line, TD2_LINE_2, "date_of_expiry"))


def validate_optional_data(data: str) -> str:
    """Return ``data`` as a TD2 line 2 printed optional data, else raise.

    Positions 29-34, and **the width is the whole of the judgement, and
    everything else is deliberately left unjudged**, for
    :func:`validate_document_number`'s reason and ``td1.py``'s: optional data
    is whatever the issuing authority chose to put in six characters, and a
    rule saying "filler only means unused" would be inventing a meaning the
    standard does not state.  So this judges nothing beyond being a string
    exactly as wide as :data:`TD2_LINE_2` says.

    **Six characters is the number a reader is most likely to get wrong in
    this format**, because a TD3's personal number is 14 and this field is
    where a TD3 spends the 8 positions a TD2 does not have.  The width is
    read out of the table rather than typed in as a 6 precisely so that a
    carried-over 14 would have to be typed here to survive, and
    ``test_td2.py`` asserts the number against the sibling table as well.

    **It is returned with its filler, and that is load-bearing twice over.**
    Position 35 is the check digit computed over positions 29-34 *as
    printed*, so stripping the field would change that digit; and positions
    29-34 are inside :data:`TD2_COMPOSITE_SPANS`, so it would change the
    composite as well.  An unused field is a *value* rather than an absence,
    the way the filler in the sex marker is, so six fillers come back as six
    fillers rather than as an empty string a caller would have to guess the
    meaning of.

    **A character the MRZ alphabet cannot print comes back untouched** -- a
    space or a lower-case letter is a misread, and
    :func:`~app.pipeline.tier0.mrz.check_digit` is what raises on it.  A
    reader that refused the field here would lose the printed characters a
    flag needs to point at.

    Raises:
        MrzValueError: unless ``data`` is a string of exactly the layout's
            width, including a non-string, which is reported as this rather
            than escaping as a bare ``TypeError``.  The message names the
            positions and the width and **never the characters**, which are
            data the issuing authority wrote about the holder.
    """
    if not isinstance(data, str):
        raise MrzValueError(
            f"TD2 optional data must be a string, not {type(data).__name__}"
        )
    start, end = TD2_LINE_2["optional_data"]
    width = end - start + 1
    if len(data) != width:
        raise MrzValueError(
            f"TD2 optional data is {width} characters (positions "
            f"{start}-{end}), not {len(data)}"
        )
    return data


def parse_optional_data(line: str) -> str:
    """Return the optional data printed in positions 29-34 of ``line``.

    The sixth and last field :func:`parse_td2_line_2` judges, and the same
    shape as every other reader here: the positions come from
    :data:`TD2_LINE_2` through :func:`td2_field`, so there is no
    ``line[28:34]`` here, and the slice is handed straight to
    :func:`validate_optional_data`, which is where the width is judged and
    where the decision to judge nothing else is written down.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td2_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 29-34 are not the field's
            width.  The message names the width and never the characters.
    """
    return validate_optional_data(td2_field(line, TD2_LINE_2, "optional_data"))


def parse_td2_line_2(line: str) -> Mapping[str, str]:
    """Return line 2 of a TD2 zone as its eleven fields, keyed by name.

    The twin of :func:`parse_td2_line_1`, and nothing more than it: it
    slices no line for itself, judges nothing of its own beyond the line's
    width, and every field is read through the reader or :func:`td2_field`
    that owns it.

    **The keys are in printed order**, for :func:`parse_td2_line_1`'s reason,
    and the returned object is built in that order rather than sorted
    afterwards, so a caller reading the mapping top to bottom reads the
    document and then the person it belongs to: what the document is, which
    country issued it, when the holder was born, what the document's own
    digits say about all three, when it stops working, and what the
    issuing authority had to add.  Eleven fields rather than three is the
    whole of a TD2 line 2, and **five of them are printed check digits** --
    the most a line carries in this package.

    **The task list's 3.10 named this line's fields as "DOB, sex, expiry,
    nationality, optional data, final composite", and that list is a TD1's.**
    It is not this line's order and it is not its fields: the document number
    and its own digit come *first* at 1-10, then the nationality, the date of
    birth and its digit, the sex marker, the date of expiry and its digit,
    six characters of optional data, that field's digit, and the composite.
    The list is settled here against the table above, which 3.8 pinned, and
    the task text has been corrected to match; ``test_td2.py`` says which
    line each of the disputed fields is on.

    **The five printed digits are read and judged by nothing, and that is
    2.4's rule.**  Positions 10, 20, 28, 35 and 36 are the only fields here
    with no ``validate_*`` of their own: a printed digit is a character, not
    a value to check, and whether it agrees with the field beside it is
    verification rather than parsing.  Each is taken out of the line through
    :func:`td2_field` like everything else, so the map is a complete record
    of the 36 characters -- concatenating its values in printed order
    rebuilds the line -- rather than only of the parts someone thought to
    keep.  **The composite at position 36 is the one that could not be
    checked even if this module wanted to**: it is computed over characters
    on both lines, and :func:`td2_composite_input` is the only honest way to
    get them.

    **The returned mapping is read-only, for :func:`parse_td2_line_1`'s
    reason:** this is the evidence of what the document printed, and a caller
    that could edit it would be able to make a cleaned-up field look like a
    read one.

    **No record type is created here, and that is still 3.14's to decide.**
    A TD2 record is the TD3 record with a ``format`` discriminator, so a
    second shape now would mean 3.14 has to merge two.  Line 2's fields go in
    their own mapping, keyed by the layout's own field names, which is the
    shape that survives that merge.

    **The line's width is checked by :func:`_checked_line`**, for
    :func:`parse_td2_line_1`'s reason: the zone gate that will cover both
    lines takes this over rather than two lines each repeating it.

    Raises:
        MrzValueError: for a line that is not a string, a line that is not
            :data:`TD2_LINE_LENGTH` characters, then whichever field reader
            refuses first, in printed order.  The error is the reader's own,
            unwrapped and unedited, so its message names the field and the
            width it wanted and never the characters around it.
    """
    line = _checked_line(line, 2)
    return MappingProxyType(
        {
            "document_number": parse_document_number(line),
            "document_number_check_digit": td2_field(
                line, TD2_LINE_2, "document_number_check_digit"
            ),
            "nationality": parse_nationality(line),
            "date_of_birth": parse_date_of_birth(line),
            "date_of_birth_check_digit": td2_field(
                line, TD2_LINE_2, "date_of_birth_check_digit"
            ),
            "sex": parse_sex(line),
            "date_of_expiry": parse_date_of_expiry(line),
            "date_of_expiry_check_digit": td2_field(
                line, TD2_LINE_2, "date_of_expiry_check_digit"
            ),
            "optional_data": parse_optional_data(line),
            "optional_data_check_digit": td2_field(
                line, TD2_LINE_2, "optional_data_check_digit"
            ),
            "composite_check_digit": td2_field(
                line, TD2_LINE_2, "composite_check_digit"
            ),
        }
    )


def td2_composite_input(line_1: str, line_2: str) -> str:
    """Return the 62 characters the composite digit printed on line 2 is
    computed over.

    The assembly, and nothing beyond it.  Whether those characters agree with
    the digit at line 2 position 36 is :func:`td2_check_digit_results`'s
    question, so this concatenates and stops:
    :func:`~app.pipeline.tier0.mrz.check_digit` remains the only place in
    this package where a digit comes out.

    **Both lines are read, and this is the first function in the format to
    have to.**  A TD2's name is on line 1 and every printed digit is on line
    2, so no single line holds the composite's characters: 31 come from one
    line and 31 from the other, and a caller who passed only the line that
    *prints* the digit would be computing a different number over a third of
    the evidence.

    **Both lines are checked for width, through :func:`_checked_line`, and
    that is a change from ``td3.py`` and the right way round here.**
    ``td3.py`` can leave the width to
    :func:`~app.pipeline.tier0.td3.validate_td3_lines` because every read it
    makes is a field read, and a caller who skipped the gate got a short
    *field*.  A caller who skipped this format's gate would instead get a
    *silently short composite*: dropping a character anywhere in these 62
    positions changes the digit without changing anything else, so a wrong
    width would come back as a composite that failed and no error -- the one
    failure mode a caller could not tell from a forged document.  Checking
    both lines costs nothing twice, because :func:`parse_td2_line_1` and
    :func:`parse_td2_line_2` are the callers that have already made, and it
    moves to the zone gate in one place when that arrives.

    **Nothing is judged on the way through and nothing is repaired.**  The
    printed digits at 10, 20, 28 and 35 are *inside* the span rather than
    beside it, so a document number that no longer agrees with its own digit
    reaches the verifier as both the mutation and the digit that contradicts
    it.  Filler is not tidied either, for the reason the field readers leave
    padding alone: a stripped ``<`` would change the digit this function
    exists to let someone check.

    Returns:
        A ``str`` of exactly 62 characters: line 1's 31, then line 2's 31, in
        the order :data:`TD2_COMPOSITE_SPANS` states.

    Raises:
        MrzValueError: if either argument is not a string or is not
            :data:`TD2_LINE_LENGTH` characters, from :func:`_checked_line`
            unchanged -- line 1 first, so a caller who passed both wrong is
            told about the first one rather than both.
    """
    lines = {"line_1": _checked_line(line_1, 1), "line_2": _checked_line(line_2, 2)}
    return "".join(
        lines[line_name][start - 1 : end]
        for line_name, start, end in TD2_COMPOSITE_SPANS
    )


def td2_check_digit_results(
    line_1: str, line_2: str, sources: Mapping[str, str]
) -> tuple[CheckDigitResult, ...]:
    """Return the five :class:`~app.pipeline.tier0.mrz.CheckDigitResult`
    records of a TD2 zone, in printed order.

    The composition, and this format's first call into
    :mod:`app.pipeline.tier0.mrz` for anything other than an error type and
    the filler.  It pairs the five entries of :data:`TD2_CHECK_DIGIT_FIELDS`
    with the characters each is computed over and the digit it is compared
    against, and hands the lot to
    :func:`~app.pipeline.tier0.mrz.check_digit_results`, which is where the
    arithmetic lives.  ``td2.py`` may delegate here and may not reimplement:
    the sum, the weights and the modulo are mrz's, and
    ``test_td2.py`` asserts the two functions are the same object.

    **Both lines and one map, and the reason is the same as
    ``td1.py``'s.**  The four single-field rows read their characters out of
    ``sources``, which is the map :func:`parse_td2_line_1` and
    :func:`parse_td2_line_2` build, so a verdict is computed over exactly
    the characters the parse is evidence of rather than over a second read of
    a line that could disagree.  The composite cannot: its first span is the
    name, and its spans are positions rather than field names, so
    :func:`td2_composite_input` is the only honest way to get those 62
    characters.  ``sources`` is passed rather than rebuilt for the reason
    :func:`~app.pipeline.tier0.td3.td3_check_digit_results` passes it, and
    3.14 is the caller that will hand over the merged map its record holds.

    **The printed digits are read from ``sources`` too, never re-sliced from
    a line:** a second read of position 36 would be a second opinion about
    where it is, and 3.3's test that a document cannot "repair" its own
    printed digit would stop holding the moment two readers existed.

    **A field that cannot be read comes back as a row whose ``passed`` is
    ``None``, not as an exception, for 3.3's reason.**  2.4's rule is that a
    check digit this project did not verify is carried as printed, and the
    same character may be filler on one visa and a digit on another -- the
    optional data's digit position at 35 prints whatever the authority put
    there, and an unused field may print the filler -- so a TD2 that raised
    would raise on the ordinary condition of an unused field.  Nothing an
    officer needs is lost: the field is named, the half that could be read is
    still reported, and the other four rows are unaffected.

    Raises:
        ``KeyError``, and only :class:`KeyError`, if ``sources`` does not
            hold a field this pairing names.  Deliberately not translated
            into :class:`MrzValueError`, for
            :func:`~app.pipeline.tier0.td3.td3_check_digit_results`'s
            reason: the field names come from this module's own layout, a
            missing one is a bug in the caller rather than a document that is
            wrong, and dressing it up as the latter would put a
            ``MrzValueError`` in a log describing nothing about any visa.
            Also :class:`MrzValueError` from :func:`td2_composite_input` for
            a line of the wrong width.  A document that is *wrong* raises
            nothing here at all; that is the row above.
    """
    composite = td2_composite_input(line_1, line_2)
    return check_digit_results(
        (
            (
                label,
                composite if field is None else sources[field],
                sources[digit_field],
            )
            for label, field, digit_field in TD2_CHECK_DIGIT_FIELDS
        )
    )


def _td2_sources(zone: tuple[str, str]) -> Mapping[str, str]:
    """Return every field's raw characters across ``zone``, in printed order.

    The raw half of :class:`~app.pipeline.tier0.td3.MrzDocument` for a TD2,
    and the TD2 twin of
    :func:`~app.pipeline.tier0.td3._td3_sources`.  The two line assemblers'
    own maps, merged by a chained update rather than re-sliced: a second read
    of a position would be a second opinion about where it sits, and the two
    maps are already the evidence the readers read through
    :func:`td2_field`.

    A TD2 zone is complete at two lines -- its name is on line 1, which 3.9
    read for the composite's span and 3.10 for its own -- so unlike a TD1
    there is no field here that nothing reads.
    """
    sources: dict[str, str] = dict(parse_td2_line_1(zone[0]))
    sources.update(parse_td2_line_2(zone[1]))
    return MappingProxyType(sources)


def parse_td2(lines: Iterable[str]) -> MrzDocument:
    """Return the whole TD2 zone at ``lines`` as a
    :class:`~app.pipeline.tier0.td3.MrzDocument` with ``format`` ``"TD2"``.

    The assembly, and nothing else.  Every field reader from 3.8 to 3.10 is
    called with the line the layout names for it, through
    :func:`parse_td2_line_1`, :func:`parse_td2_line_2` and
    :func:`_td2_sources`, so the record cannot disagree with the readers
    about where a field sits or what it may print; this function slices no
    line for itself.

    **The record is the TD3 record, not a second shape**, for
    :func:`~app.pipeline.tier0.td1.parse_td1`'s reason: 3.9 and 3.10 left
    the decision here rather than inventing a TD2 type that 3.14 would then
    have to merge, and this is the merge.  **The seven attributes a TD2 does
    not fill are ``None`` and not empty strings** -- a TD3's personal number
    and its digit, and a TD1's optional data 1, its digit and its optional
    data 2.

    **The name is read all the way through, exactly as a TD3's is**, because
    a TD2 prints the same field in the same MRZ shape -- surname, ``<<``,
    given names, filler-padded to the end of the line -- and
    :func:`~app.pipeline.tier0.td3.split_name`,
    :func:`~app.pipeline.tier0.td3.split_given_names`,
    :func:`~app.pipeline.tier0.td3.normalise_names` and
    :func:`~app.pipeline.tier0.td3.transliterate_names` read the characters
    rather than a position, so they are imported from :mod:`~app.pipeline.
    tier0.td3` rather than reimplemented.  **The name field itself is read by
    this module's own** :func:`parse_name`, because a TD2 name is 31
    characters at positions 6-36 and a TD3's is 39 at 1-39; the shared
    pipeline starts after that, where the two are the same string.

    **The record carries no reference date and no inferred year, for
    :class:`~app.pipeline.tier0.td3.MrzDocument`'s reason.**  A caller who
    wants the century behind
    :attr:`~app.pipeline.tier0.td3.MrzDocument.date_of_birth` asks
    :func:`~app.pipeline.tier0.mrz.infer_birth_year` with the printed field
    and a date it injects.

    Raises:
        MrzValueError: for anything this zone can be wrong about -- a shape
            :func:`validate_td2_lines` refuses, then whichever field reader
            refuses first, in printed order.  The error is the reader's own,
            unwrapped and unedited, so its message names the field and the
            width it wanted and never the identity data around it.  The five
            check digits cannot contribute one: a mismatch and an unreadable
            digit are both rows in
            :attr:`~app.pipeline.tier0.td3.MrzDocument.check_digit_results`.
    """
    line_1, line_2 = validate_td2_lines(lines)
    sources = _td2_sources((line_1, line_2))
    name = parse_name(line_1)
    surname, given_names = split_name(name)
    surname, given_names = normalise_names(surname, split_given_names(given_names))
    surname, given_names = transliterate_names(surname, given_names)
    return MrzDocument(
        format="TD2",
        document_code=parse_document_code(line_1),
        issuing_state=parse_issuing_state(line_1),
        name=name,
        document_number=parse_document_number(line_2),
        document_number_check_digit=sources["document_number_check_digit"],
        nationality=parse_nationality(line_2),
        date_of_birth=parse_date_of_birth(line_2),
        date_of_birth_check_digit=sources["date_of_birth_check_digit"],
        sex=parse_sex(line_2),
        date_of_expiry=parse_date_of_expiry(line_2),
        date_of_expiry_check_digit=sources["date_of_expiry_check_digit"],
        personal_number=None,
        personal_number_check_digit=None,
        composite_check_digit=sources["composite_check_digit"],
        check_digit_results=td2_check_digit_results(line_1, line_2, sources),
        surname=surname,
        given_names=tuple(given_names),
        sources=sources,
        optional_data_1=None,
        optional_data_1_check_digit=None,
        optional_data_2=None,
        optional_data=parse_optional_data(line_2),
        optional_data_check_digit=sources["optional_data_check_digit"],
    )
