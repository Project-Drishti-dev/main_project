"""ICAO 9303 TD1 (ID card) MRZ layout: where each field sits in a line.

A TD1 machine-readable zone is three lines of exactly :data:`TD1_LINE_LENGTH`
characters each, and unlike a TD3 the three lines do different jobs: line 1
is the document header and the first optional data field, line 2 holds the
holder's identity fields and every printed check digit including the
composite, and line 3 is nothing but the name.  So each line gets its own
table -- :data:`TD1_LINE_1`, :data:`TD1_LINE_2`, :data:`TD1_LINE_3` -- and
:data:`TD1` is all three keyed by line.

Positions are **1-indexed and inclusive** -- ``(1, 9)`` is the first nine
characters of the line, the way the standard prints them -- and every one of
the 30 positions of every line belongs to exactly one field.  These tables
plus :data:`TD1_LINE_LENGTH` are the only place in this module where a
position is stated.

**The tables arrived first and the readers came second, in that order on
purpose.**  Task 3.4 wrote this module as a table and nothing else, 3.5 added
line 1's reader -- :func:`parse_td1_line_1` and the four field readers
underneath it -- and 3.6 added line 2's five readers and
:func:`parse_td1_line_2` on top of those, each written against a table that
was already pinned.  A reader written first would have had the layout derived
from the code it parsed, and a boundary that was a character out would have
been right about the code and wrong about the standard.  The printed digits
are still listed as fields in
their own right, because the MRZ prints them inside the 30 characters --
position 15 of line 1 is the document number's check digit and so is *not*
part of the document number (6-14) -- and a table that left those positions
out could not account for them.  Computing any of the digits is
:mod:`app.pipeline.tier0.mrz`'s job, so this module holds no arithmetic, and
it defines no error type of its own.

**The composite digit belongs to line 2 and not to line 1, which is the one
thing about a TD1 that is easy to get backwards.**  Line 1 ends with the
check digit over optional data 1, printed at position 30.  The composite is
printed at the end of *line 2*, position 30, and is computed over characters
on both of the first two lines.  That is why no field here spans two lines --
every position has exactly one owner on its own line -- and why verifying the
composite is the first task in this format that has to read two lines to
answer a question about one digit.

The document number's check digit is **optional** in the standard, which may
print as the ``<`` filler rather than a digit.  The table cannot record that,
because a field is a span of positions and not a rule about what a character
may be, so whether a printed ``<`` there means "no digit was printed" or "a
digit was misread" is a reader's question.  It is also inside the composite's
span either way, which is what lets the span in the next paragraph be
indifferent to the answer.

**The composite's span is :data:`TD1_COMPOSITE_SPANS`, and 3.7 settled a
disagreement this module used to carry.**  The task list's 3.7 states it as
line 1 positions 1-10 and 15-30 plus line 2 positions 1-7, 9-15 and 19-29:
51 characters, of which line 1 supplies 26 and line 2 supplies 25.  That is
the standard's, and the earlier claim in this docstring -- line 1 6-14 and
16-29, with the document number's own digit at 15 excluded -- **was not**.
3.5 wrote that span down and then flagged it as unchecked; 3.6 carried the
flag forward rather than dropping it; and neither had the standard open.

Three things make the standard's span checkable here, and two of them are
about this format's own shape rather than about a document.  It **starts at
line 1 position 1**, so it covers the document code and the issuing state --
the two fields no printed check digit in this format reaches.  And it
**includes every check digit line 1 prints**, positions 15 and 30, which is
the rule the old span broke: the composite of a TD3 covers that format's check
digits at 10, 20, 28 and 43, and ``tasks.md`` 3.10 states the same for a TD2,
so a composite that dropped the digit printed beside it would be the odd one
out in this package rather than a variant of it.  The third is about line 2,
and it reads the way the other two formats read: the date of birth and its own
digit, then the expiry and its own digit, then the optional data -- skipping
the sex marker at 8, the nationality at 16-18, and the composite's own
position.  That is the same set the TD3 composite skips, and it is why
:data:`TD1_SEX_MARKERS` is the one closed set in this format that no
arithmetic here will ever test.

**This repository holds no copy of Doc 9303, so the span is stated as the
standard states it rather than as a list something here could look up.**  The
three points above are the argument, and the argument is about the format's
shape rather than a quotation; a sourced copy of Part 4 is the only thing
that would make it a lookup.  It is stated as *positions on a named line*
rather than as field names, which departs from ``td3.py``'s
:data:`~app.pipeline.tier0.td3.TD3_COMPOSITE_FIELDS` and is not a stylistic
choice: line 1 positions 1-10 cuts five characters into the nine-character
document number, so no list of whole field names can name it.  Every other
span in the composite is a run of whole fields, and the test that says so is
what keeps a span one position out from passing as self-consistent.

**Every field is read through :func:`td1_field`, which is the one place a TD1
line is sliced.**  The readers below are the same shape as ``td3.py``'s: a
``parse_*`` that takes the line and a ``validate_*`` that judges what came
out of it, so a reader and its judgement cannot disagree.  Each width is read
out of the table above rather than typed in, each message names a *document*
or a *state* and never the characters of the line, and every field comes back
exactly as printed -- padding included -- because position 15 and position 30
are check digits computed over those characters as they stand.  The one
exception is :func:`td1_composite_input`, which slices by position because
the standard's span cuts across field boundaries, and it is the only function
here that does.

**Five printed digits are read by the assemblers and judged by nothing, which
is 2.4's rule; 3.7 is the question, and 3.7 is what answers it.**  Line 1
carries two of them (positions 15 and 30) and line 2 three (7, 15 and 30);
:func:`parse_td1_line_1` returns all six fields of line 1 and
:func:`parse_td1_line_2` all eight of line 2, keyed by name, in printed order.
The fields the standard constrains are read through their own validators, and
the digits are read through the layout and carried as the characters the
document printed.  **The parsers still judge none of them, and that is
deliberate and unchanged:** a parse reports what the document printed, and
whether those characters agree with the fields beside them is
:func:`td1_check_digit_results`'s question, which a caller asks for
separately.  So the two halves of this format's evidence stay two halves --
the map says what was there, the verdicts say whether it adds up -- and a
caller cannot "repair" a printed digit to make a verdict pass.

**That list is five rows rather than one, and four of them are not the
composite.**  :data:`TD1_CHECK_DIGIT_FIELDS` pairs the document number, the
first optional data field, the two dates and the composite with the five
digits printed beside them, in printed order, exactly as
``td3.py``'s :data:`~app.pipeline.tier0.td3.TD3_CHECK_DIGIT_FIELDS` does.
3.5 and 3.6 deferred all five to this task, and this task answers all five
rather than leaving four of the format's printed digits unjudged: an officer
reading a TD1 is owed the same "which field disagreed" the TD3 gives.  **A
specimen therefore does not yield five passing rows, and that is a property of
the format rather than of the fixture.**  An unused optional data field
prints filler in its own check digit's place, so that row's ``passed`` is
``None`` -- not ``False``.  2.14's rule is the reason: there is no digit there
to disagree with anything, and calling that a failure would put a forged-digit
claim in front of an officer on the strength of a field nobody filled in.

**Line 2's two dates come back exactly as printed, and 3.11 is what they are
judged against.**  The month and day go to
:func:`~app.pipeline.tier0.mrz.date_fault`, which lives in
:mod:`app.pipeline.tier0.mrz` precisely so that a TD1, a TD2 and a TD3 cannot
disagree about what a day is: ``"993199"`` is refused by all three and by
exactly one of them at a time, and ``"AAAAAA"`` is accepted by all three,
because a character the standard does not print in this field is a misread for
the check digit beside it to report rather than a date this module can rule
on.  **The century is not touched.**  ``"000101"`` and ``"991231"`` are dates
here and so are ``"000229"`` and ``"020229"`` -- whether a particular February
had a 29th, and whether ``"00"`` means 1900 or 2000, are 3.12's and 3.13's
questions and this module answers neither.  A digit inside a date is not
tidied either, for the reason the document number is not: position 7 is the
check digit over positions 1-6 *as printed*.

**The sex marker is a closed set of four characters, and that is a decision
3.6 makes rather than inherits.**  :data:`TD1_SEX_MARKERS` holds ``M``, ``F``,
``X`` and the filler -- the same four
:data:`~app.pipeline.tier0.td3.TD3_SEX_MARKERS` holds, and for the same
reason: the composite digit skips position 8 and neither date's own digit
covers it, so **this membership test is the only judgement any arithmetic in
this project will ever make about the character.**  **The source is the TD1
format table in the same part of the standard these layout tables come from,
and this repository holds no copy of the document**, so the set is stated as
that table states it rather than as a list this project could check.  The two
errors are not symmetric and the set goes against the cheaper one: dropping
``"X"`` refuses a card that is well-formed, which is the same failure as a
nationality list with one country missing and the one
:func:`validate_issuing_state` refuses to make; keeping ``"X"`` accepts a
marker no card may print, in a field nothing else checks, which a rules
engine (Part 12) can flag and a reader cannot.  If the table in fact reads
``M``, ``F`` or ``<`` alone, dropping ``"X"`` is a one-character edit and
nothing else in this module moves.
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
from .td3 import MrzDocument

__all__ = [
    "TD1",
    "TD1_CHECK_DIGIT_FIELDS",
    "TD1_COMPOSITE_SPANS",
    "TD1_DOCUMENT_CODES",
    "TD1_LINE_1",
    "TD1_LINE_2",
    "TD1_LINE_3",
    "TD1_LINE_COUNT",
    "TD1_LINE_LENGTH",
    "TD1_SEX_MARKERS",
    "parse_td1",
    "parse_date_of_birth",
    "parse_date_of_expiry",
    "parse_document_code",
    "parse_document_number",
    "parse_issuing_state",
    "parse_nationality",
    "parse_optional_data_1",
    "parse_optional_data_2",
    "parse_sex",
    "td1_check_digit_results",
    "td1_composite_input",
    "parse_td1_line_1",
    "parse_td1_line_2",
    "td1_field",
    "validate_date_of_birth",
    "validate_date_of_expiry",
    "validate_document_code",
    "validate_document_number",
    "validate_issuing_state",
    "validate_nationality",
    "validate_optional_data_1",
    "validate_optional_data_2",
    "validate_sex",
    "validate_td1_lines",
]

#: Characters in one TD1 line (ICAO 9303, Part 4, "TD1 Format").
TD1_LINE_LENGTH = 30

#: Lines in a TD1 machine-readable zone.  Always 3, and never a range: the name
#: on line 3 is what makes a TD1 three lines where a TD3 is two.
TD1_LINE_COUNT = 3

#: Line 1 -- the document itself and its first optional data field.  ICAO
#: numbers the two optional data fields 1 and 2 because both lines may carry
#: one; line 1's is 14 characters wide, filler-padded when unused.
TD1_LINE_1: dict[str, tuple[int, int]] = {
    "document_code": (1, 2),  # "I<" for an identity card; the type of document
    "issuing_state": (3, 5),  # 3-letter code of the issuing authority
    "document_number": (6, 14),  # 9 characters, filler-padded when shorter
    "document_number_check_digit": (15, 15),  # optional; may print as filler
    "optional_data_1": (16, 29),  # 14 characters, filler-padded
    "optional_data_1_check_digit": (30, 30),  # over optional_data_1 only
}

#: Line 2 -- the holder's identity and every printed check digit, the
#: composite among them.  Both dates carry their own digit, and the sex marker
#: and the nationality are the two fields no check digit covers: the composite
#: skips position 8 and positions 16-18.
TD1_LINE_2: dict[str, tuple[int, int]] = {
    "date_of_birth": (1, 6),  # YYMMDD
    "date_of_birth_check_digit": (7, 7),
    "sex": (8, 8),  # M, F, or < where unspecified
    "date_of_expiry": (9, 14),  # YYMMDD
    "date_of_expiry_check_digit": (15, 15),
    "nationality": (16, 18),  # 3-letter code of the holder's nationality
    "optional_data_2": (19, 29),  # 11 characters, filler-padded
    "composite_check_digit": (30, 30),  # over TD1_COMPOSITE_SPANS: line 1
    # 1-10 and 15-30, line 2 1-7, 9-15 and 19-29 -- the only field in this
    # module whose characters are not all on the line it is printed in
}

#: Line 3 -- the holder's name and nothing else, in the same shape as a TD3
#: line 1's name field: surname, "<<", given names, filler-padded to the end
#: of the line.
TD1_LINE_3: dict[str, tuple[int, int]] = {
    "name": (1, 30),
}

#: The whole TD1 layout, keyed by line: ``TD1["line_1"]``, ``TD1["line_2"]``
#: and ``TD1["line_3"]``.  These are the *same* dict objects as
#: :data:`TD1_LINE_1`, :data:`TD1_LINE_2` and :data:`TD1_LINE_3`, not copies,
#: so a parser can reach for either name and there is no second table to
#: drift.
TD1: dict[str, dict[str, tuple[int, int]]] = {
    "line_1": TD1_LINE_1,
    "line_2": TD1_LINE_2,
    "line_3": TD1_LINE_3,
}

#: The document codes a TD1 line 1 may carry, at positions 1-2 (ICAO 9303,
#: Part 4, "TD1 Format").  ``I<`` is what an identity card prints: ``I`` for
#: the document type and ``<`` for "no variant".  A bare ``I`` is accepted
#: alongside it for ``td3.py``'s reason -- the second character is filler, so a
#: code that lost it is the same document rather than a different one -- and
#: because the filler maps to ``0`` in the check-digit arithmetic, dropping it
#: cannot change any digit computed over this line.  The set is exact and
#: closed: ``P<`` and ``V<`` are well-formed MRZ codes belonging to other
#: formats, so a zone that prints one is refused rather than read as an ID
#: card.  A frozenset, so no caller can widen it at runtime.
TD1_DOCUMENT_CODES: frozenset[str] = frozenset({"I<", "I"})

#: The sex markers a TD1 line 2 may print at position 8 (ICAO 9303, Part 4,
#: "TD1 Format"): ``M``, ``F``, ``X`` and the filler.  ``X`` is printed where
#: a holder has not stated a sex and ``<`` where the field is unspecified --
#: two different things, and both are values here rather than a misread.  The
#: set is closed and named rather than a rule such as "one uppercase letter, or
#: the filler", which would accept ``N`` and ``Q`` on the one field of line 2
#: that no check digit in this project covers: the composite skips position 8
#: and neither date's own digit reaches it.  A frozenset, so no caller can
#: widen what a card may print at run time.  **The module docstring says where
#: this set comes from and what the cost of being wrong about it is**; the
#: short of it is that this repository holds no copy of the standard, so the
#: set is the table's and not a list checked against it.
TD1_SEX_MARKERS: frozenset[str] = frozenset({"M", "F", "X", FILLER})

#: The 51 characters the composite check digit printed at line 2 position 30
#: is computed over, as ``(line, first position, last position)`` triples in
#: the order the standard concatenates them: line 1 positions 1-10 and 15-30,
#: then line 2 positions 1-7, 9-15 and 19-29.  Line 1 supplies 26 characters
#: and line 2 supplies 25, and a TD1 composite is the only digit in this
#: package computed over characters from two different lines.
#:
#: **Positions on a named line rather than field names, and that is forced
#: rather than chosen.**  ``td3.py`` can name its 39 characters as eight whole
#: fields, because every one of the TD3's spans happens to end on a field
#: boundary.  Here line 1 positions 1-10 stops five characters into the
#: nine-character document number, so no list of field names is equal to this
#: span and naming fields here would be a different -- and a wrong -- claim.
#: The other four spans *are* runs of whole fields, which is the one thing
#: about the layout and this table that can be checked, and the test that
#: checks it is what keeps a span one position out from being self-consistent
#: rather than correct.
#:
#: **It is stated here rather than derived from the layout above, for the
#: reason :data:`~app.pipeline.tier0.td3.TD3_CHECK_DIGIT_FIELDS` is:** the
#: tables say where a field sits, and only the standard says which of those
#: positions a given digit is computed over.  Position 10 of line 1, for
#: instance, is the fifth character of the document number *and* the tenth
#: character of the composite, and nothing in the layout distinguishes them.
#: The gaps are as much a part of the claim as the spans: 11-14 of line 1 and
#: 8 and 16-18 of line 2 are outside it, and those excluded fields are the
#: document number's tail, the sex marker and the nationality.
TD1_COMPOSITE_SPANS: tuple[tuple[str, int, int], ...] = (
    ("line_1", 1, 10),
    ("line_1", 15, 30),
    ("line_2", 1, 7),
    ("line_2", 9, 15),
    ("line_2", 19, 29),
)

#: The five printed check digits of a TD1, each paired with the characters it
#: is computed over.  Triples of ``(label, field the characters come from,
#: field the printed digit comes from)``, in printed order -- line 1 positions
#: 15 and 30, then line 2 positions 7, 15 and 30.
#:
#: **The same shape as
#: :data:`~app.pipeline.tier0.td3.TD3_CHECK_DIGIT_FIELDS`, and for the same
#: reason, down to the ``None``:** the composite's second element is ``None``
#: because its characters are not printed as one field anywhere.  They are
#: :data:`TD1_COMPOSITE_SPANS` read out and joined, and they cross a field
#: boundary as well as a line boundary, so a name that said where they came
#: from would be lying twice.  Everything else is a pair of real fields, and a
#: pairing that named a field the layout does not have raises rather than
#: reporting a field nobody printed.
TD1_CHECK_DIGIT_FIELDS: tuple[tuple[str, str | None, str], ...] = (
    ("document_number", "document_number", "document_number_check_digit"),
    ("optional_data_1", "optional_data_1", "optional_data_1_check_digit"),
    ("date_of_birth", "date_of_birth", "date_of_birth_check_digit"),
    ("date_of_expiry", "date_of_expiry", "date_of_expiry_check_digit"),
    ("composite", None, "composite_check_digit"),
)


def validate_td1_lines(lines: Iterable[str]) -> tuple[str, str, str]:
    """Return ``lines`` as the three TD1 lines, or raise unless it is a TD1 zone.

    The TD1 twin of
    :func:`~app.pipeline.tier0.td3.validate_td3_lines`, and 3.14 is what
    brought it: a TD1 machine-readable zone is :data:`TD1_LINE_COUNT` lines
    of :data:`TD1_LINE_LENGTH` characters, and this is where that shape is
    said in a check rather than in a comment.  ``lines`` may be any iterable
    of strings and the three are returned in printed order, so a caller never
    indexes for itself.

    **This gate covers all three lines, and a TD1 needs it more than a TD3
    does.**  A TD1's third line is the holder's name and nothing else, so a
    zone that arrives two lines long is a different document rather than a
    truncated one, and 3.10 showed that no reader inside a format can catch
    that: a line 1 parses as a line 2 without complaint.  It is also the
    only place that can see a *missing* line, since nothing else in this
    module is ever handed one.

    What the characters *say* is not checked here: not that they are MRZ
    characters, not that the document code is an identity card, and not a
    check digit.  A shape that is right while its contents are wrong is
    still a zone worth parsing and flagging.

    Raises:
        MrzValueError: unless ``lines`` is an iterable of exactly
            :data:`TD1_LINE_COUNT` strings, each exactly
            :data:`TD1_LINE_LENGTH` characters long.  A ``MrzValueError`` is
            a ``ValueError``, so ``except ValueError`` catches it too, and
            it is the one type this raises: a ``None`` zone, a single string
            where three lines were expected, and a line that is not a string
            are all reported as this, rather than escaping as a bare
            ``TypeError`` a caller catching ``MrzValueError`` would never
            see.  **The messages carry the shape and never the characters**,
            because the lines are the identity data the screening is about.
    """
    # Checked before the iteration below: a string is a sequence of
    # one-character lines, so iterating it would report 30 lines and point at
    # the wrong mistake entirely.
    if isinstance(lines, str):
        raise MrzValueError(
            f"a TD1 machine-readable zone is {TD1_LINE_COUNT} lines, "
            f"not one string of {len(lines)} characters"
        )
    try:
        zone = tuple(lines)
    except TypeError:
        raise MrzValueError(
            "a TD1 machine-readable zone must be a sequence of lines, "
            f"not {type(lines).__name__}"
        ) from None
    if len(zone) != TD1_LINE_COUNT:
        raise MrzValueError(
            f"a TD1 machine-readable zone is {TD1_LINE_COUNT} lines, "
            f"not {len(zone)}"
        )
    # 1-indexed, like every position in this module, so a message naming
    # "line 3" means the line the standard calls line 3.
    for number, line in enumerate(zone, start=1):
        if not isinstance(line, str):
            raise MrzValueError(
                f"TD1 line {number} must be a string, not {type(line).__name__}"
            )
        if len(line) != TD1_LINE_LENGTH:
            raise MrzValueError(
                f"TD1 line {number} is {len(line)} characters, "
                f"not {TD1_LINE_LENGTH}"
            )
    line_1, line_2, line_3 = zone
    return line_1, line_2, line_3


def _checked_line(line: str, number: int) -> str:
    """Return ``line`` if it is a TD1 line of 30 characters, else raise.

    The width check the two assemblers share, held in one place because the
    message *is* the diagnosis and there is no reason for it to be written
    twice.  It exists at all only because there is no zone gate yet: without
    it a 29-character line reads as a document whose last field sliced to an
    empty string, which is a report of what the document printed that has
    quietly lost a position.  When :func:`~app.pipeline.tier0.td3.
    validate_td3_lines`'s twin arrives -- three lines of 30, the whole zone --
    this check moves into it and the two assemblers lose it.

    The type check comes first and is not decoration: :func:`len` raises a
    bare ``TypeError`` on ``None``, and ``bytes`` *has* a length, so a
    validator that measured before it checked the type would measure an
    argument the package's error type never mentions.

    Raises:
        MrzValueError: if ``line`` is not a string, or is not
            :data:`TD1_LINE_LENGTH` characters.  The message names the line
            number and the length it was given, and **never the characters**:
            the line is the identity data the screening is about.
    """
    if not isinstance(line, str):
        raise MrzValueError(f"a TD1 line must be a string, not {type(line).__name__}")
    if len(line) != TD1_LINE_LENGTH:
        raise MrzValueError(
            f"TD1 line {number} is {len(line)} characters, not {TD1_LINE_LENGTH}"
        )
    return line


def td1_field(line: str, layout: dict[str, tuple[int, int]], name: str) -> str:
    """Return the characters ``name`` occupies in ``line``, by way of ``layout``.

    The one place in the project where a TD1 line is sliced, and the TD1
    counterpart of ``td3.py``'s function of the same name.  Positions are
    1-indexed and inclusive, so the ``- 1`` below is the whole conversion.
    ``layout`` is one of :data:`TD1_LINE_1`, :data:`TD1_LINE_2` or
    :data:`TD1_LINE_3`, so the field's width comes from the table rather than
    from the caller.

    This checks nothing about the field and nothing about the line's width.  It
    hands back the characters the layout says are there, in both directions --
    a field one character too wide and one too narrow are the same mistake,
    and only the judgement that follows can tell them apart.

    Raises:
        MrzValueError: if ``line`` is not a string, or ``layout`` has no field
            called ``name``.  A ``KeyError`` out of the lookup and a
            ``TypeError`` out of the slice are both the kind of built-in error
            1.9 forbids, and both are a caller mistake rather than a bad
            document, so neither reaches a ``except MrzValueError``.
    """
    if not isinstance(line, str):
        raise MrzValueError(f"a TD1 line must be a string, not {type(line).__name__}")
    if name not in layout:
        raise MrzValueError(f"no TD1 field named {name!r}")
    start, end = layout[name]
    return line[start - 1 : end]


def _readable_codes() -> str:
    """The accepted document codes, sorted, for a message.

    Sorted so the message is the same string every time, which keeps a log
    greppable; never used to decide anything, only to say what was expected.
    """
    return ", ".join(repr(code) for code in sorted(TD1_DOCUMENT_CODES))


def validate_document_code(code: str) -> str:
    """Return ``code`` if it is a TD1 identity card document code, else raise.

    The same closed check ``td3.py`` makes over a different set, and closed
    for the same reason: ``P<`` (a passport) and ``V<`` (a visa) are
    well-formed MRZ codes, not misspellings, so the answer is to refuse the
    zone rather than read an ID card out of a document that is not one.

    Raises:
        MrzValueError: for any other value, including one that is not a
            string -- the membership test answers ``False`` for a non-string
            rather than raising, so this is the one failure and it is the
            package's one error type.  The message names the code it was given
            and the codes it wanted, and nothing else: two characters that
            describe a document type, never the line around them.
    """
    if code in TD1_DOCUMENT_CODES:
        return code
    raise MrzValueError(
        f"a TD1 identity card document code is {_readable_codes()}, not {code!r}"
    )


def parse_document_code(line: str) -> str:
    """Return the document code printed in positions 1-2 of ``line``.

    The first field :func:`parse_td1_line_1` reads, and the first thing a TD1
    character can *say*: this line is a TD1 at all, and it is a card rather
    than a passport.  The positions come from :data:`TD1_LINE_1` through
    :func:`td1_field`, so there is no ``line[0:2]`` here, and the slice is
    handed straight to :func:`validate_document_code` so the reader and the
    judgement cannot disagree about what an ID card is.

    ``line`` is expected to be the 30 characters :data:`TD1_LINE_1` describes,
    which :func:`parse_td1_line_1` checks before calling this; the width is not
    repeated here, because a line that is too short is a shape problem and not
    a document-code problem.  It is still total over its input: a line too
    short to hold a code slices to whatever it has, which is then not a code,
    and a line that is not a string is reported by :func:`td1_field` rather
    than left to raise a bare ``TypeError``.

    Raises:
        MrzValueError: if ``line`` is not a string, or the characters it
            prints at positions 1-2 are not in :data:`TD1_DOCUMENT_CODES`.
            The message carries the code and stops: the rest of the line is
            the identity data the screening is about.
    """
    return validate_document_code(td1_field(line, TD1_LINE_1, "document_code"))


def _is_uppercase_letter(character: str) -> bool:
    """Whether ``character`` is one of ``A``-``Z``, the MRZ letter set.

    Spelled out rather than taken from :data:`string.ascii_uppercase` so the
    rule reads as the standard states it -- three characters, each one an
    uppercase letter -- rather than as a range that happens to end at the
    right place.
    """
    return len(character) == 1 and "A" <= character <= "Z"


def validate_issuing_state(code: str) -> str:
    """Return ``code`` if it is a well-formed TD1 issuing state, else raise.

    The whole of the rule the standard states for positions 3-5: exactly as
    wide as :data:`TD1_LINE_1` says the field is, and every one of those
    characters one of ``A``-``Z``.  The width is *read out of the table*
    rather than typed in as a 3, so the layout stays the only place a position
    is stated and the message cannot describe a width the layout does not have.

    Well-formedness is the whole of the judgement, and a code list is
    deliberately absent, for ``td3.py``'s reason: ``IND`` is three uppercase
    letters and is accepted, because ISO 3166-1 alpha-3 assigns ``IND`` to
    India, so any conforming list of issuing states contains it and a list
    without one would refuse every genuine Indian ID card.  Recognising a
    state is a Tier 0 policy question, answered by a code list that has to be
    sourced rather than remembered, and it belongs to the rules engine.

    Raises:
        MrzValueError: unless ``code`` is a string of exactly the layout's
            width whose every character is an uppercase letter, which covers
            the misreads this field actually produces: a digit read for a
            letter, a lower-case read, a filler or a space where a letter
            belongs, and a diacritic from a printed name.  A value that is
            not a string is reported as this too rather than escaping as a
            bare ``TypeError``.  The message names the state it was given,
            which is three characters naming a *state*, and stops there.
    """
    if not isinstance(code, str):
        raise MrzValueError(
            f"an issuing state must be a string, not {type(code).__name__}"
        )
    start, end = TD1_LINE_1["issuing_state"]
    width = end - start + 1
    if len(code) != width or not all(_is_uppercase_letter(letter) for letter in code):
        raise MrzValueError(
            f"a TD1 issuing state is {width} uppercase letters (A-Z), not {code!r}"
        )
    return code


def parse_issuing_state(line: str) -> str:
    """Return the issuing state printed in positions 3-5 of ``line``.

    The second field :func:`parse_td1_line_1` reads and the same shape as
    :func:`parse_document_code`: the positions come from :data:`TD1_LINE_1`
    through :func:`td1_field`, so there is no ``line[2:5]`` here, and the
    slice is handed straight to :func:`validate_issuing_state`.

    **Line 1 of a TD1 carries the document code, the issuing state *and* the
    document number, where a TD3 splits them across two lines -- and that is
    why a wrong line cannot be read as this one by accident.**  Line 2's
    positions 3-5 are ``"081"``: not three uppercase letters, so it is
    refused.  The document number is the weaker of the three, and
    :func:`parse_document_number` says so.

    Raises:
        MrzValueError: if ``line`` is not a string, or the characters it
            prints at positions 3-5 are not a well-formed issuing state.  The
            message carries the state and stops.
    """
    return validate_issuing_state(td1_field(line, TD1_LINE_1, "issuing_state"))


def validate_document_number(number: str) -> str:
    """Return ``number`` if a TD1 line 1 printed one, else raise.

    The same rule ``td3.py`` applies to the same nine positions, and the same
    two reasons for it.  The width is read out of :data:`TD1_LINE_1` rather
    than typed in as a 9, so the layout stays the only place a position is
    stated.  **"Non-empty" means non-empty once the filler is taken out**: the
    field is nine characters wide whatever the number is and a shorter number
    is padded on the right, so ``"D23145890"`` is a complete number,
    ``"D23145<<<"`` is a complete shorter one, and ``"<<<<<<<<<"`` is no
    number at all -- a plain ``if not number`` would accept all three.  The
    emptiness is judged *before* the width, so a field that holds nothing is
    reported as the missing number it is rather than as a line that stopped
    early.

    **The number is returned exactly as printed, padding included, and that is
    load-bearing rather than untidy.**  Position 15 is the check digit over
    positions 6-14 *as printed*, and the filler
    (:data:`~app.pipeline.tier0.mrz.FILLER`) is a character that digit is
    computed over, not tidying waiting to happen.  A stripped number no longer
    occupies the nine positions the layout gives it, and the fact that a
    *trailing* filler would not change the digit is a trap rather than a
    licence -- the two agree on a right-padded number and diverge the moment
    the filler is anywhere else.  Nothing is stripped, re-cased or otherwise
    edited.

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
            f"a TD1 document number must be a string, not {type(number).__name__}"
        )
    start, end = TD1_LINE_1["document_number"]
    if not number.replace(FILLER, ""):
        raise MrzValueError(
            f"a TD1 document number must print at least one character that is "
            f"not the filler, but positions {start}-{end} held nothing but it"
        )
    width = end - start + 1
    if len(number) != width:
        raise MrzValueError(
            f"a TD1 document number is {width} characters (positions "
            f"{start}-{end}), not {len(number)}"
        )
    return number


def parse_document_number(line: str) -> str:
    """Return the document number printed in positions 6-14 of ``line``.

    The third field :func:`parse_td1_line_1` reads, and the same shape as the
    two before it: the positions come from :data:`TD1_LINE_1` through
    :func:`td1_field`, so there is no ``line[5:14]`` here, and the slice is
    handed straight to :func:`validate_document_number`.

    **Line 1, and the cost of that is worth stating, because a TD1 puts all
    three of these fields on one line where a TD3 splits them.**  Nothing else
    in the package reads a TD1 line 1, so there is no second opinion about
    where this field sits; the only thing that disagrees is the check digit
    printed at position 15, and 3.7 is the task that says so.  What *is*
    caught today is the line being the wrong one: :func:`parse_issuing_state`
    refuses a line 2 at position 3, so an assembler handed the lines the
    other way round never reaches this reader with them.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td1_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 6-14 are not a document number.
            The message carries the positions, the width and what was
            expected, and **never the number**.
    """
    return validate_document_number(td1_field(line, TD1_LINE_1, "document_number"))


def validate_optional_data_1(data: str) -> str:
    """Return ``data`` as a TD1 line 1 printed optional data 1, else raise.

    **The width is the whole of the judgement, and everything else is
    deliberately left unjudged.**  Optional data 1 is whatever the issuing
    authority chose to put in fourteen characters: unused on most cards,
    which is why the specimen's field is nothing but the filler, and used for
    a national use of the authority's own on others.  A rule saying "filler
    only means unused" would be inventing a meaning the standard does not
    state, so this judges nothing beyond being a string exactly as wide as
    :data:`TD1_LINE_1` says -- the same rule 2.4 applied to a TD3's personal
    number, for the same reason.

    **It is returned with its filler, and that is load-bearing twice over.**
    Position 30 is the check digit computed over positions 16-29 *as printed*,
    so stripping the field would change the digit 3.7 computes; and an unused
    field is a *value* rather than an absence, the way the filler in the sex
    marker is, so "all filler" comes back as fourteen fillers rather than as
    an empty string a caller would have to guess the meaning of.

    **A character the MRZ alphabet cannot print comes back untouched** -- a
    space or a lower-case letter is a misread, and
    :func:`~app.pipeline.tier0.mrz.check_digit` is what raises on it in 3.7.
    A reader that refused the field here would lose the printed characters a
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
            f"TD1 optional data 1 must be a string, not {type(data).__name__}"
        )
    start, end = TD1_LINE_1["optional_data_1"]
    width = end - start + 1
    if len(data) != width:
        raise MrzValueError(
            f"TD1 optional data 1 is {width} characters (positions "
            f"{start}-{end}), not {len(data)}"
        )
    return data


def parse_optional_data_1(line: str) -> str:
    """Return the optional data 1 printed in positions 16-29 of ``line``.

    The fourth field :func:`parse_td1_line_1` reads, and the same shape as
    the three before it: the positions come from :data:`TD1_LINE_1` through
    :func:`td1_field`, so there is no ``line[15:29]`` here, and the slice is
    handed straight to :func:`validate_optional_data_1`, which is where the
    width is judged and where the decision to judge nothing else is written
    down.

    Raises:
        MrzValueError: if ``line`` is not a string (reported by
            :func:`td1_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 16-29 are not the field's
            width.  The message names the width and never the characters.
    """
    return validate_optional_data_1(td1_field(line, TD1_LINE_1, "optional_data_1"))


def parse_td1_line_1(line: str) -> Mapping[str, str]:
    """Return line 1 of a TD1 zone as its six fields, keyed by name.

    The assembly, and nothing else: it slices no line for itself, judges
    nothing of its own beyond the line's width, and every field is read
    through the reader or :func:`td1_field` that owns it.

    **The keys are in printed order**, which is the order the standard prints
    them and therefore the order a caller reading the mapping top to bottom
    sees the document.  Reading a mapping preserves insertion order, so the
    returned object is built in that order rather than sorted afterwards.

    **The two check digits are read and judged by nothing, and that is 3.7's
    question.**  Positions 15 and 30 are the only fields here with no
    ``validate_*`` of their own: a printed digit is a character, not a value
    to check, and whether it agrees with the field beside it is verification
    rather than parsing.  Each is taken out of the line through
    :func:`td1_field` like everything else, so the map is a complete record
    of the 30 characters -- concatenating its values in printed order
    rebuilds the line -- rather than only of the parts someone thought to
    keep.  Both come back as the characters the document printed, so a
    position 15 that holds the filler rather than a digit is carried as the
    filler, which the standard permits and which 3.4's docstring already
    called a reader's question.

    **The returned mapping is read-only, for ``MrzDocument.sources``'s
    reason:** this is the evidence of what the document printed, and a caller
    that could edit it would be able to make a cleaned-up field look like a
    read one.

    **No record type is created here, and that is 3.14's to decide.**  The
    TD3 parse returns a frozen dataclass; a TD1 record is the same type with
    a ``format`` discriminator, and inventing a second shape now would mean
    3.14 has to merge two.  A mapping keyed by the layout's own field names is
    the shape that survives that merge, and 3.6 adds line 2's fields to their
    own mapping rather than to this one.

    **The line's width is checked by :func:`_checked_line`, because there is
    no zone gate yet.**  A TD1 line is :data:`TD1_LINE_LENGTH` characters or
    the layout's last field slices to nothing: a 29-character line reads as a
    document number and an optional data 1, with the optional data 1 digit
    coming back as an empty string, and a map that reports what the document
    printed while having lost a position.  When the zone gate arrives -- three
    lines of 30, as :func:`~app.pipeline.tier0.td3.validate_td3_lines` is for
    a TD3 -- that check moves into it, and both assemblers lose it at once
    rather than one of them being left behind.

    Raises:
        MrzValueError: for a line that is not a string, a line that is not
            :data:`TD1_LINE_LENGTH` characters, then whichever field reader
            refuses first, in printed order.  The error is the reader's own,
            unwrapped and unedited, so its message names the field and the
            width it wanted and never the characters around it.
    """
    line = _checked_line(line, 1)
    return MappingProxyType(
        {
            "document_code": parse_document_code(line),
            "issuing_state": parse_issuing_state(line),
            "document_number": parse_document_number(line),
            "document_number_check_digit": td1_field(
                line, TD1_LINE_1, "document_number_check_digit"
            ),
            "optional_data_1": parse_optional_data_1(line),
            "optional_data_1_check_digit": td1_field(
                line, TD1_LINE_1, "optional_data_1_check_digit"
            ),
        }
    )


def validate_date_of_birth(date: str) -> str:
    """Return ``date`` if a TD1 line 2 printed a date of birth, else raise.

    Positions 1-6, **the width read out of :data:`TD1_LINE_2` rather than typed
    in**, for :func:`validate_issuing_state`'s reason, and the month and day
    judged by :func:`~app.pipeline.tier0.mrz.date_fault` -- 3.11's rule, kept
    in :mod:`app.pipeline.tier0.mrz` so the three formats cannot disagree about
    what a day is.  ``"993199"`` is refused because its month is 31, and
    ``"AAAAAA"`` is not, because a field of characters the standard does not
    print here is a misread for the check digit beside it to report rather than
    a date this function can rule on.

    The width is *read out of* :data:`TD1_LINE_2` rather than typed in as a 6,
    for :func:`validate_issuing_state`'s reason: the layout stays the only
    place a position is stated, and a message cannot describe a width the
    layout does not have.  What the width is for is the document number's
    reason restated on a field that cannot be short by padding -- a line which
    stopped before position 6 slices to a short field, and that is a line that
    stopped early rather than a document carrying a five-character date of
    birth.

    **The date is returned exactly as printed, which is load-bearing rather
    than untidy.**  Position 7 is the check digit over positions 1-6 *as
    printed*, and the specimen is the proof: :func:`~app.pipeline.tier0.mrz.
    check_digit` on ``"740812"`` is the ``2`` the ICAO document prints there.
    A space, a diacritic or a stray filler is carried rather than tidied, so
    3.7's arithmetic sees the characters the document printed -- and
    :func:`~app.pipeline.tier0.mrz.check_digit` is what raises on the ones
    outside the MRZ alphabet, which is a finding rather than a lost document.

    **The message does not carry the date**, for the holder's reason: a date
    of birth is a property of the holder, not of the document, and
    ``td3.py``'s nationality is where that rule was carried across from the
    document's own identifiers to one of the holder's.  This names the width it
    wanted and the positions it looked at, and stops.

    Raises:
        MrzValueError: unless ``date`` is a string of exactly the layout's
            width.  A value that is not a string is reported as this too,
            rather than escaping as a bare ``TypeError`` a caller catching
            ``MrzValueError`` would never see -- ``bytes`` being the case that
            matters, since it has a length and would pass a validator that
            measured before it checked the type.
    """
    if not isinstance(date, str):
        raise MrzValueError(
            f"a TD1 date of birth must be a string, not {type(date).__name__}"
        )
    start, end = TD1_LINE_2["date_of_birth"]
    width = end - start + 1
    if len(date) != width:
        raise MrzValueError(
            f"a TD1 date of birth is {width} characters (positions "
            f"{start}-{end}), not {len(date)}"
        )
    fault = date_fault(date)
    if fault is not None:
        raise MrzValueError(
            f"a TD1 date of birth (positions {start}-{end}) has a {fault} that "
            f"no date can print"
        )
    return date


def parse_date_of_birth(line_2: str) -> str:
    """Return the date of birth printed in positions 1-6 of ``line_2``.

    The first field :func:`parse_td1_line_2` reads, and the same shape as
    every reader on line 1: the positions come from :data:`TD1_LINE_2` through
    :func:`td1_field`, so there is no ``line[0:6]`` here, and the slice is
    handed straight to :func:`validate_date_of_birth`, so the reader and the
    judgement cannot disagree about how wide a date of birth is.

    **This reader cannot tell a line 1 from a line 2, and the reason is worth
    stating rather than leaving to be discovered.**  Line 1's positions 1-6
    are ``"I<UTOD"`` -- six characters, the right width, nothing this
    validator objects to, because what a date may print is 3.11's question and
    a width is all this answers.  :func:`parse_sex` is what catches a line 1
    handed to this assembler, since position 8 of a line 1 is a digit of the
    document number.  That is a fact about *this* line rather than a general
    one, so the caller still has to pass the right line rather than lean on
    the widths.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td1_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 1-6 are not a date of birth's
            width.  The message carries the positions, the width and what was
            expected, and **never the date**.
    """
    return validate_date_of_birth(td1_field(line_2, TD1_LINE_2, "date_of_birth"))


def _readable_sexes() -> str:
    """The accepted sex markers, sorted, for a message.

    Sorted so the message is the same string every time, which keeps a log
    greppable, for :func:`_readable_codes`'s reason.  Never used to decide
    anything -- the membership test against :data:`TD1_SEX_MARKERS` is -- only
    to say what was expected.
    """
    return ", ".join(repr(marker) for marker in sorted(TD1_SEX_MARKERS))


def validate_sex(marker: str) -> str:
    """Return ``marker`` if it is a TD1 sex marker, else raise.

    The one character at position 8, and the **only** field of line 2 whose
    content rule is a closed list rather than a shape: the value must be one
    of :data:`TD1_SEX_MARKERS` -- ``M``, ``F``, ``X`` or the filler.  The
    set and where it comes from are :data:`TD1_SEX_MARKERS`' to say and this
    repeats only the part that is a judgement rather than a fact about the
    field: **it is closed because nothing underneath this field would object
    to a marker that is wrong.**  The composite digit skips position 8 -- it
    covers line 2's 1-7, 9-15 and 19-29 -- and no other digit covers it
    either, so a digit misread for a letter, or a letter for a digit, is caught
    by this membership test and by nothing else in the package.  That is also
    why the four are *named* rather than derived: a rule such as "one
    uppercase letter, or the filler" would accept ``N`` and ``Q``, which no
    card may print there.

    **The filler is a value in this field, and so is ``X``.**  A document
    prints ``<`` where the sex is unspecified and ``X`` where a holder has not
    stated one; both are different from a misread, so
    :func:`validate_document_number`'s "empty once the filler is removed" rule
    does not repeat here -- for one character there is nothing to strip, and
    the filler *is* the answer.

    **The message names the four markers it wanted and not the one it found.**
    The set is the standard's rather than the holder's, so it is safe to
    print; a sex marker is a property of the holder, and this is the second
    field on this line to say so.

    Raises:
        MrzValueError: for any other value, including one that is not a
            string.  The type guard comes first and is not decoration: the
            check below is a membership test, and ``[] in TD1_SEX_MARKERS``
            raises a bare ``TypeError`` a caller catching ``MrzValueError``
            would never see.
    """
    if not isinstance(marker, str):
        raise MrzValueError(
            f"a TD1 sex marker must be a string, not {type(marker).__name__}"
        )
    if marker in TD1_SEX_MARKERS:
        return marker
    start, end = TD1_LINE_2["sex"]
    raise MrzValueError(
        f"a TD1 sex marker is one of {_readable_sexes()} at position "
        f"{start}-{end}, and those positions printed something else"
    )


def parse_sex(line_2: str) -> str:
    """Return the sex marker printed at position 8 of ``line_2``.

    The same shape as every other reader here: the position comes from
    :data:`TD1_LINE_2` through :func:`td1_field`, so there is no ``line[7]``,
    and the slice is handed straight to :func:`validate_sex`, so the reader and
    the closed set cannot disagree about what a card may print.

    **This is the reader that catches a zone handed over the wrong way round,
    and that is a property of line 2 rather than a general one.**  A line 1's
    position 8 is a digit of the document number -- ``"3"`` in the specimen --
    and no digit there is a sex marker, so :func:`parse_td1_line_2` refuses a
    line 1 two fields before the date of expiry and three before the
    nationality.  The other direction does not lean on this function:
    :func:`parse_issuing_state` refuses a line 2 at position 3.

    A line longer than the zone is fine: the field is one character at
    position 8, so surplus characters are not part of it.  A line that stops
    before position 8 slices to an empty string, which is not one of the four.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td1_field`, so no bare ``TypeError`` escapes), or if the
            character it prints at position 8 is not one of
            :data:`TD1_SEX_MARKERS`.  The message names the position and the
            markers it wanted, and **neither the marker it found nor anything
            else on the line**.
    """
    return validate_sex(td1_field(line_2, TD1_LINE_2, "sex"))


def validate_date_of_expiry(date: str) -> str:
    """Return ``date`` if a TD1 line 2 printed a date of expiry, else raise.

    Positions 9-14, and :func:`validate_date_of_birth`'s rule unchanged: the
    width is read out of :data:`TD1_LINE_2` and the month and day are judged
    by :func:`~app.pipeline.tier0.mrz.date_fault`, which does not know which of
    the two dates it is looking at.  ``"993199"`` is refused here for exactly
    the reason it is refused in the date of birth, and 3.13's century rule for
    an expiry is a question that check does not touch.

    **The expiry is returned exactly as printed**, for the reason the date of
    birth is: position 15 is the check digit over positions 9-14 as printed,
    and :func:`~app.pipeline.tier0.mrz.check_digit` on ``"120415"`` is the
    ``9`` the specimen prints there.  Nothing is trimmed, and the two are
    different documents to the arithmetic the moment they differ.

    The message does not carry the date, for :func:`validate_date_of_birth`'s
    reason.

    Raises:
        MrzValueError: unless ``date`` is a string of exactly the layout's
            width, including when it is not a string at all.
    """
    if not isinstance(date, str):
        raise MrzValueError(
            f"a TD1 date of expiry must be a string, not {type(date).__name__}"
        )
    start, end = TD1_LINE_2["date_of_expiry"]
    width = end - start + 1
    if len(date) != width:
        raise MrzValueError(
            f"a TD1 date of expiry is {width} characters (positions "
            f"{start}-{end}), not {len(date)}"
        )
    fault = date_fault(date)
    if fault is not None:
        raise MrzValueError(
            f"a TD1 date of expiry (positions {start}-{end}) has a {fault} that "
            f"no date can print"
        )
    return date


def parse_date_of_expiry(line_2: str) -> str:
    """Return the date of expiry printed in positions 9-14 of ``line_2``.

    The same shape as :func:`parse_date_of_birth`: the positions come from
    :data:`TD1_LINE_2` through :func:`td1_field`, so there is no ``line[8:14]``
    here, and the slice is handed straight to
    :func:`validate_date_of_expiry`, so the reader and the judgement cannot
    disagree about how wide a date of expiry is.

    **A line 1 read as a line 2 gets six digits here and this validator
    accepts them**, where ``td3.py``'s twin of this reader has a field that
    comes back as the tail of a given name.  Line 1's positions 9-14 are six
    characters of a document number, and the width rule has no opinion about
    what a date may print.  What catches a line 1 in
    :func:`parse_td1_line_2` is :func:`parse_sex` two fields earlier, so the
    honest statement is that this reader is safe only when handed the right
    line -- which is 3.7's caller to guarantee, not this one's.

    Raises:
        MrzValueError: if ``line_2`` is not a string, or if the characters it
            prints at positions 9-14 are not a date of expiry's width.  The
            message carries the positions, the width and what was expected,
            and never the date.
    """
    return validate_date_of_expiry(td1_field(line_2, TD1_LINE_2, "date_of_expiry"))


def validate_nationality(code: str) -> str:
    """Return ``code`` if it is a well-formed TD1 nationality, else raise.

    Positions 16-18, and the whole of the rule the standard states for them is
    the rule :func:`validate_issuing_state` states for a state's three
    characters: exactly as wide as :data:`TD1_LINE_2` says the field is, and
    every one of those characters one of ``A``-``Z``.  The width is read out
    of the table for the same reason it is everywhere else here.

    **``IND`` is accepted, and that is ``td3.py``'s decision carried over
    rather than re-derived.**  "Three uppercase letters" and "reject
    ``IND``" cannot both hold: ISO 3166-1 alpha-3 assigns ``IND`` to India, so
    every conforming list of nationality codes contains it, and a list without
    one refuses every genuine Indian ID card.  **No list of nationality codes
    ships here**, which is the decision rather than an omission -- a second
    list is a second thing to be sourced rather than a second rule to invent,
    and recognising a nationality is a Tier 0 policy question belonging to the
    rules engine (Part 12).

    **The standard gives this field no "unspecified" value, so there is no
    emptiness rule here and the filler is not a special case.**  The sex
    marker may legitimately print the filler, where a nationality may not,
    because there is no such thing as an unknown nationality in a TD1 zone.
    ``"<<<"`` is therefore a misread rejected on the ordinary ground -- the
    filler is not one of ``A``-``Z`` -- and *not* a missing value, which is
    :func:`validate_document_number`'s rule and does not repeat here: a
    document number can be short and padded, and a three-letter code that is
    short is not a code.

    **The message does not carry the code, where the issuing state's message
    does carry a state.**  Both codes are the same shape, and the
    difference is whose property each is: a document *state* describes the
    document, a nationality describes the **holder**.  This names the
    positions, the width and the alphabet, and never what it found.

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
            f"a TD1 nationality must be a string, not {type(code).__name__}"
        )
    start, end = TD1_LINE_2["nationality"]
    width = end - start + 1
    if len(code) != width or not all(_is_uppercase_letter(letter) for letter in code):
        raise MrzValueError(
            f"a TD1 nationality is {width} uppercase letters (A-Z) at positions "
            f"{start}-{end}, and those positions printed something else"
        )
    return code


def parse_nationality(line_2: str) -> str:
    """Return the nationality printed in positions 16-18 of ``line_2``.

    The same shape as :func:`parse_date_of_expiry`: the positions come from
    :data:`TD1_LINE_2` through :func:`td1_field`, so there is no
    ``line[15:18]`` here, and the slice is handed straight to
    :func:`validate_nationality`, so the reader and the judgement cannot
    disagree about what a well-formed nationality is.

    **Two of the three wrong-line reads on this line are caught and one is
    not, and the one that is not is the identity field no digit covers.**
    Handed a line 1 this returns ``"<<<"``, which
    :func:`validate_nationality` refuses -- though the refusal comes from
    :func:`parse_sex` two fields earlier in the assembler, before this reader
    is reached.  Handed a line 3 it returns three uppercase letters out of the
    holder's name, and **nothing in this module would ever object to them**:
    the composite skips positions 16-18 on line 2, exactly as it skips the
    sex marker at 8.  So this is the second field in this format whose
    plausibility is the rules engine's question rather than a check digit's,
    and 3.7's caller has to pass the right line.

    A line longer than the zone is fine: the field is read by position, so
    surplus characters are not part of it.  A line that stops before position
    18 slices to something short, which is then not three uppercase letters.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td1_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 16-18 are not a well-formed
            nationality.  The message carries the positions, the width and the
            alphabet, and **neither the nationality nor anything else on the
            line**: it is the identity data the screening is about.
    """
    return validate_nationality(td1_field(line_2, TD1_LINE_2, "nationality"))


def validate_optional_data_2(data: str) -> str:
    """Return ``data`` as a TD1 line 2 printed optional data 2, else raise.

    **The width is the whole of the judgement, and everything else is
    deliberately left unjudged**, for :func:`validate_optional_data_1`'s
    reason applied to the second of the two fields: optional data 2 is
    whatever the issuing authority chose to put in eleven characters, and a
    rule saying "filler only means unused" would be inventing a meaning the
    standard does not state.  So this judges nothing beyond being a string
    exactly as wide as :data:`TD1_LINE_2` says.

    **It is returned with its filler, which is load-bearing twice over.**  The
    composite digit printed at position 30 is computed over positions 19-29
    *as they stand*, so stripping the field would change the digit 3.7
    computes; and an unused field is a *value* rather than an absence, the way
    the filler in the sex marker is, so the specimen's eleven fillers come
    back as eleven fillers rather than as an empty string a caller would have
    to guess the meaning of.

    **A character the MRZ alphabet cannot print comes back untouched** -- a
    space or a lower-case letter is a misread, and
    :func:`~app.pipeline.tier0.mrz.check_digit` is what raises on it in 3.7.
    A reader that refused the field here would lose the printed characters a
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
            f"TD1 optional data 2 must be a string, not {type(data).__name__}"
        )
    start, end = TD1_LINE_2["optional_data_2"]
    width = end - start + 1
    if len(data) != width:
        raise MrzValueError(
            f"TD1 optional data 2 is {width} characters (positions "
            f"{start}-{end}), not {len(data)}"
        )
    return data


def parse_optional_data_2(line_2: str) -> str:
    """Return the optional data 2 printed in positions 19-29 of ``line_2``.

    The last field :func:`parse_td1_line_2` judges, and the same shape as
    :func:`parse_optional_data_1`: the positions come from :data:`TD1_LINE_2`
    through :func:`td1_field`, so there is no ``line[18:29]`` here, and the
    slice is handed straight to :func:`validate_optional_data_2`, which is
    where the width is judged and where the decision to judge nothing else is
    written down.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td1_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 19-29 are not the field's
            width.  The message names the width and never the characters.
    """
    return validate_optional_data_2(td1_field(line_2, TD1_LINE_2, "optional_data_2"))


def parse_td1_line_2(line: str) -> Mapping[str, str]:
    """Return line 2 of a TD1 zone as its eight fields, keyed by name.

    The twin of :func:`parse_td1_line_1`, and nothing more than it: it slices
    no line for itself, judges nothing of its own beyond the line's width, and
    every field is read through the reader or :func:`td1_field` that owns it.

    **The keys are in printed order**, for :func:`parse_td1_line_1`'s reason,
    and the returned object is built in that order rather than sorted
    afterwards, so a caller reading the mapping top to bottom reads the
    holder: when they were born, their sex, when the card stops working, what
    they are, and what the issuing authority had to say about them.

    **The three printed digits are read and judged by nothing, and that is
    3.7's question.**  Positions 7, 15 and 30 are the only fields here with no
    ``validate_*`` of their own: a printed digit is a character, not a value
    to check, and whether it agrees with the field beside it is verification
    rather than parsing.  Each is taken out of the line through
    :func:`td1_field` like everything else, so the map is a complete record of
    the 30 characters -- concatenating its values in printed order rebuilds
    the line -- rather than only of the parts someone thought to keep.
    **The composite at position 30 is the one that could not be checked even
    if this module wanted to**: it is computed over characters on both of the
    first two lines, and which of line 1's positions are inside it is the
    conflict the module docstring records and 3.7 has to settle against the
    standard.

    **The returned mapping is read-only, for the same reason as line 1's:**
    this is the evidence of what the document printed, and a caller that could
    edit it would be able to make a cleaned-up field look like a read one.

    **No record type is created here, and that is still 3.14's to decide.**  A
    TD1 record is the TD3 record with a ``format`` discriminator, so a second
    shape now would mean 3.14 has to merge two.  Line 2's fields go in their
    own mapping, keyed by the layout's own field names, which is the shape
    that survives that merge.

    **The line's width is checked by :func:`_checked_line`, for
    :func:`parse_td1_line_1`'s reason:** the zone gate that will cover all
    three lines takes this over rather than three lines each repeating it.

    Raises:
        MrzValueError: for a line that is not a string, a line that is not
            :data:`TD1_LINE_LENGTH` characters, then whichever field reader
            refuses first, in printed order.  The error is the reader's own,
            unwrapped and unedited, so its message names the field and the
            width it wanted and never the characters around it.
    """
    line = _checked_line(line, 2)
    return MappingProxyType(
        {
            "date_of_birth": parse_date_of_birth(line),
            "date_of_birth_check_digit": td1_field(
                line, TD1_LINE_2, "date_of_birth_check_digit"
            ),
            "sex": parse_sex(line),
            "date_of_expiry": parse_date_of_expiry(line),
            "date_of_expiry_check_digit": td1_field(
                line, TD1_LINE_2, "date_of_expiry_check_digit"
            ),
            "nationality": parse_nationality(line),
            "optional_data_2": parse_optional_data_2(line),
            "composite_check_digit": td1_field(
                line, TD1_LINE_2, "composite_check_digit"
            ),
        }
    )


def td1_composite_input(line_1: str, line_2: str) -> str:
    """Return the 51 characters the composite digit printed on line 2 is
    computed over.

    The assembly, and nothing beyond it.  Whether those characters agree with
    the digit at line 2 position 30 is
    :func:`td1_check_digit_results`'s question, so this concatenates and
    stops: :func:`~app.pipeline.tier0.mrz.check_digit` remains the only place
    in this package where a digit comes out.  This is the same line
    :func:`~app.pipeline.tier0.td3.td3_composite_input` draws when it carries
    the printed digit as the characters the document printed rather than as an
    ``int``.

    **This is the one function here that slices by position, and the module
    docstring says why it has to.**  Every other read goes through
    :func:`td1_field` and therefore names a field, which is what stops a
    layout change and a reader from drifting apart.  The composite's first
    span, line 1 positions 1-10, ends five characters into the nine-character
    document number, so there is no field name to give it: the positions in
    :data:`TD1_COMPOSITE_SPANS` *are* the claim, and the test that pins them
    against the layout is what keeps the one boundary-crossing span honest.
    A hand-written ``line_1[0:10]`` would produce the right answer for one
    specimen and no other.

    **Both lines are checked for width, through :func:`_checked_line`, which
    is a change from ``td3.py`` and the right way round here.**  ``td3.py`` can
    leave the width to :func:`~app.pipeline.tier0.td3.validate_td3_lines`
    because every read it makes is a field read, and a caller who skipped the
    gate got a short field.  A caller who skipped TD1's gate would instead get
    a *silently short composite*: dropping a character anywhere in these 51
    positions changes the digit without changing anything else, so a wrong
    span would come back as a composite that failed and no error.  Checking
    both lines here costs nothing twice, because :func:`parse_td1_line_1` and
    :func:`parse_td1_line_2` are the callers that have already made, and it
    moves to the zone gate in one place when that arrives rather than being
    left behind on the one function with two lines to check.

    **Nothing is judged on the way through and nothing is repaired.**  The
    printed digits at line 1 position 15 and line 2 positions 7 and 15 are
    *inside* the span rather than beside it, so a document number that no
    longer agrees with its own digit reaches the verifier as both the mutation
    and the digit that contradicts it.  Filler is not tidied either, for the
    same reason the field readers leave padding alone: a stripped ``<`` would
    change the digit this function exists to let someone check.

    Returns:
        A ``str`` of exactly 51 characters: line 1's 26, then line 2's 25, in
        the order :data:`TD1_COMPOSITE_SPANS` states.

    Raises:
        MrzValueError: if either argument is not a string or is not
            :data:`TD1_LINE_LENGTH` characters, from :func:`_checked_line`
            unchanged -- line 1 first, so a caller who passed both wrong is
            told about the first one rather than both.
    """
    lines = {"line_1": _checked_line(line_1, 1), "line_2": _checked_line(line_2, 2)}
    return "".join(
        lines[line_name][start - 1 : end]
        for line_name, start, end in TD1_COMPOSITE_SPANS
    )


def td1_check_digit_results(
    line_1: str, line_2: str, sources: Mapping[str, str]
) -> tuple[CheckDigitResult, ...]:
    """Return the five :class:`~app.pipeline.tier0.mrz.CheckDigitResult`
    records of a TD1 zone, in printed order.

    The composition, and this format's first call into
    :mod:`app.pipeline.tier0.mrz` for anything other than an error type, the
    filler and the digit layer.  It pairs the five entries of
    :data:`TD1_CHECK_DIGIT_FIELDS` with the characters each is computed over
    and the digit it is compared against, and hands the lot to
    :func:`~app.pipeline.tier0.mrz.check_digit_results`, which is where the
    arithmetic lives.

    **Both lines and one map, and the reason is that the span needs the lines
    while the per-field rows need the evidence.**  The four single-field rows
    read their characters out of ``sources``, which is the map
    :func:`parse_td1_line_1` and :func:`parse_td1_line_2` build, so a verdict
    is computed over exactly the characters the parse is evidence of rather
    than over a second read of a line that could disagree.  The composite
    cannot: line 1 positions 1-10 stops inside the document number, so
    :func:`td1_composite_input` is the only honest way to get those 51
    characters.  ``sources`` is passed rather than rebuilt for the reason
    :func:`~app.pipeline.tier0.td3.td3_check_digit_results` passes it, and
    3.14 is the caller that will hand over the merged map its record holds.

    **The printed digits are read from ``sources`` too, never re-sliced from a
    line:** a second read of position 30 would be a second opinion about
    where it is, and 3.3's test that a document cannot "repair" its own
    printed digit would stop holding the moment two readers existed.

    **A field that cannot be read comes back as a row whose ``passed`` is
    ``None``, not as an exception, for 3.3's reason and more sharply here.**
    2.4's rule is that a check digit this project did not verify is carried as
    printed, and the same character may be filler on one card and a digit on
    another, so a TD1 that raised would raise on the ordinary condition of an
    unused optional data field.  Nothing an officer needs is lost: the field is
    named, the half that could be read is still reported -- ``found 0,
    expected unreadable`` for a filler where the arithmetic still comes to
    zero -- and the other four rows are unaffected.

    Raises:
        ``KeyError``, and only :class:`KeyError`, if ``sources`` does not hold
            a field this pairing names.  Deliberately not translated into
            :class:`MrzValueError`, for
            :func:`~app.pipeline.tier0.td3.td3_check_digit_results`'s reason:
            the field names come from this module's own layouts, a missing one
            is a bug in the caller rather than a document that is wrong, and
            dressing it up as the latter would put a ``MrzValueError`` in a log
            describing nothing about any card.  Also :class:`MrzValueError`
            from :func:`td1_composite_input` for a line of the wrong width.
            A document that is *wrong* raises nothing here at all; that is the
            row above.
    """
    composite = td1_composite_input(line_1, line_2)
    return check_digit_results(
        (
            (
                label,
                composite if field is None else sources[field],
                sources[digit_field],
            )
            for label, field, digit_field in TD1_CHECK_DIGIT_FIELDS
        )
    )


def _td1_sources(zone: tuple[str, str, str]) -> Mapping[str, str]:
    """Return every field's raw characters across ``zone``, in printed order.

    The raw half of :class:`~app.pipeline.tier0.td3.MrzDocument` for a TD1,
    and the TD1 twin of
    :func:`~app.pipeline.tier0.td3._td3_sources`.  It is the two line
    assemblers' own maps plus line 3's name, merged by a chained update
    rather than re-sliced: a second read of a position would be a second
    opinion about where it sits, and the two maps are already the evidence
    the readers read through :func:`td1_field`.

    **Line 3 is here and nowhere else.**  Nothing in this module reads the
    name yet, so the map carries the thirty characters as printed and the
    record's :attr:`~app.pipeline.tier0.td3.MrzDocument.surname` and
    :attr:`~app.pipeline.tier0.td3.MrzDocument.given_names` stay ``None``
    until a later task does.  The key is the layout's own ``"name"``, so the
    field is reachable by the name :data:`TD1_LINE_3` gives it and a caller
    does not have to know it is currently unread.

    :func:`parse_td1_line_1` and :func:`parse_td1_line_2` are called rather
    than their results being passed in, so this cannot disagree with the
    readers about a value; the cost is that the field readers run twice per
    parse, which on two 30-character lines is arithmetic this package is not
    short of.
    """
    sources: dict[str, str] = dict(parse_td1_line_1(zone[0]))
    sources.update(parse_td1_line_2(zone[1]))
    sources["name"] = td1_field(zone[2], TD1_LINE_3, "name")
    return MappingProxyType(sources)


def parse_td1(lines: Iterable[str]) -> MrzDocument:
    """Return the whole TD1 zone at ``lines`` as a
    :class:`~app.pipeline.tier0.td3.MrzDocument` with ``format`` ``"TD1"``.

    The assembly, and nothing else.  Every field reader from 3.3 to 3.7 is
    called with the line the layout names for it, through
    :func:`parse_td1_line_1`, :func:`parse_td1_line_2` and
    :func:`_td1_sources`, so the record cannot disagree with the readers
    about where a field sits or what it may print; this function slices no
    line for itself.

    **The record is the TD3 record, not a second shape.**  3.6, 3.7 and 3.9
    each left the decision here rather than inventing a TD1 type that 3.14
    would then have to merge, and this is the merge: one
    :class:`~app.pipeline.tier0.td3.MrzDocument` for all three formats, told
    apart by :attr:`~app.pipeline.tier0.td3.MrzDocument.format` and by which
    of the per-format fields are ``None``.  **The seven attributes a TD1 does
    not fill are ``None`` and not empty strings** -- a TD3's personal number
    and its digit, and a TD2's optional data and its digit -- and the name
    attributes are ``None`` too, because line 3 still has no reader.

    **The record carries no reference date and no inferred year, for
    :class:`~app.pipeline.tier0.td3.MrzDocument`'s reason.**  A caller who
    wants the century behind :attr:`~app.pipeline.tier0.td3.MrzDocument.
    date_of_birth` asks
    :func:`~app.pipeline.tier0.mrz.infer_birth_year` with the printed field
    and a date it injects; this function has no second reading of a date to
    offer and no way to know which reference the caller means.

    Raises:
        MrzValueError: for anything this zone can be wrong about -- a shape
            :func:`validate_td1_lines` refuses, then whichever field reader
            refuses first, in printed order.  The error is the reader's own,
            unwrapped and unedited, so its message names the field and the
            width it wanted and never the identity data around it.  The five
            check digits cannot contribute one: a mismatch and an unreadable
            digit are both rows in
            :attr:`~app.pipeline.tier0.td3.MrzDocument.check_digit_results`.
    """
    line_1, line_2, line_3 = validate_td1_lines(lines)
    sources = _td1_sources((line_1, line_2, line_3))
    return MrzDocument(
        format="TD1",
        document_code=parse_document_code(line_1),
        issuing_state=parse_issuing_state(line_1),
        name=None,
        document_number=parse_document_number(line_1),
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
        check_digit_results=td1_check_digit_results(line_1, line_2, sources),
        surname=None,
        given_names=None,
        sources=sources,
        optional_data_1=parse_optional_data_1(line_1),
        optional_data_1_check_digit=sources["optional_data_1_check_digit"],
        optional_data_2=parse_optional_data_2(line_2),
        optional_data=None,
        optional_data_check_digit=None,
    )
