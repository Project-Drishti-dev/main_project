"""ICAO 9303 TD3 (passport) MRZ layout: where each field sits in a line.

A TD3 machine-readable zone is two lines of exactly :data:`TD3_LINE_LENGTH`
characters each.  The two lines print *different* fields, so they get their
own tables: :data:`TD3_LINE_1` holds the document header and the name,
:data:`TD3_LINE_2` holds the identity fields and the check digits, and
:data:`TD3` is both tables keyed by line.

Positions are **1-indexed and inclusive** -- ``(1, 9)`` is the first nine
characters of the line, the way the standard prints them -- and every one of
the 44 positions of every line belongs to exactly one field.  Nothing in this
module states a position inline: :func:`td3_field` is the one place a line is
sliced, it reads the layout to do it, and every field reader from here on
calls it.  These tables plus :data:`TD3_LINE_LENGTH` are the only place in
the project where a position is stated.

The check digits are listed as fields in their own right because the MRZ
prints them inside the 44 characters: position 10 carries the document
number's check digit and so is *not* part of the document number (1-9), and
position 44 carries the composite digit, which is computed over positions
1-10, 14-20 and 22-43 and therefore skips the nationality, the date of birth
and the sex.  Computing any of those digits is
:mod:`app.pipeline.tier0.mrz`'s job; this module holds no arithmetic and so
cannot disagree with it, and it defines no error type of its own.  **3.3 is
the first thing to call that rule into question, and the answer is that the
rule is about arithmetic rather than about delegation.**  This module now
names which five fields carry a printed digit -- :data:`TD3_CHECK_DIGIT_FIELDS`
-- and hands them to :func:`~app.pipeline.tier0.mrz.check_digit_results`, which
is the one function in the package that turns characters into a verdict.  What
that call composes is layout knowledge and belongs here: which fields are
paired with which digit, and that the fifth pair's characters are the
composite rather than a printed field.  The sum, the weights and the
modulo are still :mod:`app.pipeline.tier0.mrz`'s, and
``test_this_module_computes_no_check_digit_of_its_own`` now says what that
means rather than what it meant when the arithmetic could not be reached from
here at all.

:func:`validate_td3_lines` is the gate a zone passes before any of these
positions are read: it accepts a sequence only if it is exactly
:data:`TD3_LINE_COUNT` lines of exactly :data:`TD3_LINE_LENGTH` characters,
and otherwise raises :class:`~app.pipeline.tier0.mrz.MrzValueError` -- the one
error type the MRZ package raises, so a caller writes one ``except``.  It
checks *shape* only.  The first thing a character can *say* is which kind of
document it is, and that is :func:`parse_document_code`; the next is which
state issued it, :func:`parse_issuing_state`; then the first field of line 2,
:func:`parse_document_number`, which is the first reader here that *judges*
what it extracts -- a field of nothing but filler is a number the document
did not print -- and the first whose answer has to stay exactly as printed,
because the check digit beside it is computed over the filler too; the next is
who the document is for, :func:`parse_nationality`, which judges three
uppercase letters and therefore refuses 2.4's ``IND`` question a second time;
then when the holder was born, :func:`parse_date_of_birth`, and when the
document stops working, :func:`parse_date_of_expiry`, which judge the width of
their six characters and nothing else because what a date may *print* is
3.11's question; then :func:`parse_sex`, which reads the one character between
the two dates and refuses everything outside :data:`TD3_SEX_MARKERS`; then
:func:`parse_name`, which extracts the raw name and judges nothing about
it, :func:`split_name`, which divides that name at the ``<<``, and
:func:`split_given_names`, which divides the given-names half at the single
filler into a list, and :func:`normalise_names`, which strips the filler, the
whitespace and the lower case off what those three produced, and
:func:`transliterate_names`, which turns a diacritic into the letter
underneath it in both halves.  Between the first four they clean nothing,
because each later one strips or substitutes and has to be handed the name
exactly as the one before it returned it.  A shape message carries counts and
lengths and never the line's characters, because those characters are the
identity data the screening is
about and an exception message is the most likely thing to reach a log.  A
document-code or issuing-state message does name the code it rejected, which
names a *document* and a *state* rather than a person, and stops there.
**The nationality message does not**, because a nationality is a property of
the holder rather than of the document -- the same line 2.10 drew when it kept
the document number out of its messages.

**No list of issuing-state codes ships here, and that is the decision rather
than an omission.**  :func:`validate_issuing_state` decides well-formedness --
three characters, each one of ``A``-``Z`` -- so it accepts ``IND``, and it
must: ISO 3166-1 alpha-3 assigns ``IND`` to India, so every conforming list of
issuing states, ICAO Doc 9303's included, contains it, and a parser holding a
list without it would refuse every genuine Indian passport.  Whether DRISHTI
*recognises* a state is a Tier 0 policy question whose answer is a code list
that has to be sourced rather than remembered, which is the rules engine's
business and not a field reader's.

**The nationality is the same rule and the same decision one field over,
because it is the same three letters.**  :func:`validate_nationality` demands
three uppercase letters and accepts ``IND`` for exactly the reason
:func:`validate_issuing_state` does, and no list of nationality codes ships
here either: a second list to be sourced is not a second rule to invent.  It
is also the one identity field no check digit covers -- the composite digit
spans 1-10, 14-20 and 22-43, so positions 11-13 sit in the gap between the
first two spans -- which is why a reader pointed at the wrong line returns
``"SON"`` here without anything underneath it objecting.

**The two dates are extracted, and 3.11 is the task that made them say more.**
:func:`validate_date_of_birth` and :func:`validate_date_of_expiry` demand a
string as wide as :data:`TD3_LINE_2` says and hand it back untouched, and both
now ask :func:`~app.pipeline.tier0.mrz.date_fault` whether the month and day
could be a day at all -- ``"993199"`` is refused by all three formats for the
one reason, while ``"AAAAAA"`` and ``"<<<<<<"`` are still accepted, because a
character the standard does not print in this field is a misread for the check
digit beside it to report rather than a date this module can rule on.  **The
century stays open**, which is 3.12's and 3.13's question and not this
module's: ``"000101"`` is a date here without anyone having said which
century "``00``" is.  The width is still judged, and it is 2.10's reason
restated: a line that stops before position 19 slices to a short field, and
that is a line which stopped early rather than a document carrying a
five-character date of birth.

**A date comes back exactly as printed, and the digit printed beside it is the
proof -- and also the limit of that proof.**  Position 20 is the check digit
over positions 14-19 as printed and position 28 is the check digit over 22-27,
so :func:`~app.pipeline.tier0.mrz.check_digit` on the specimen's ``"740812"``
is the ``2`` the document prints and on ``"120415"`` it is the ``9``.  **It is
also a trap rather than a licence**: the six characters one to the right of
the expiry come to the same ``9``, and so does ``"ARIA<<"`` -- the wrong line's
answer -- so the arithmetic can agree with a reader that is wrong, and the
layout is what settles it.  2.10 recorded the same trap for a trailing filler.

**The sex marker is a closed set of four, and it is closed because nothing
underneath it would object.**  ``M``, ``F``, ``X`` and ``<`` are what ICAO
9303 prints at position 21 and :data:`TD3_SEX_MARKERS` is a ``frozenset`` of
them, for :data:`TD3_DOCUMENT_CODES`'s reason.  The composite digit covers
1-10, 14-20 and 22-43, so it skips 21: the sex marker sits in the same gap
2.11's nationality does, and it is the **second** identity field with no
arithmetic under it -- a digit misread for a letter here is caught by
:func:`validate_sex` and by nothing else in the module, which is why the four
are named rather than derived from a rule such as "one uppercase letter, or
the filler", which would wave through ``N``.

**The filler is a value in this field and nowhere else in line 2.**  A
document prints ``<`` to say the sex is unspecified, which is a different
thing from a misread, so 2.10's "empty once the filler is removed" rule does
not repeat here: the filler *is* the answer.  This is what 2.11 deferred when
it declined an emptiness rule for the nationality -- there is exactly one
unspecified sex and there is no such thing as an unknown nationality, so one
of the two fields has the value and the other does not.  ``X`` is a third
thing, printed where a holder has not stated a sex, and it is accepted on the
same closed-set ground rather than being given a meaning this module cannot
source.

**The transliteration map is four letters long, and that is a decision.**
:data:`TRANSLITERATIONS` names the four characters ICAO Doc 9303's
transliteration guidance is quoted for -- ``ß``-``SS``, ``Ø``-``O``, ``Ł``-``L``
and ``Đ``-``D`` -- and every other accented letter is handled by a rule
instead: a letter that decomposes canonically into a base letter and a
combining mark *is* the base letter.  A written-out table of the two hundred
or so accented characters in the Latin ranges would be two hundred remembered
values, and this project does not quote a remembered value where a source is
what the value is -- the composite check digit is the standing example of a
value this repository declined to state for want of one.  The letters Unicode
will not decompose are therefore *not* in the map, and
:func:`transliterate_names` carries them through unchanged rather than
guessing: a name that still holds one is a name the rules engine can flag,
whereas dropping the character would change a name with nothing left behind to
show that it had.

**:func:`parse_td3` assembles the zone and judges none of it.**  Every field
reader above is called with the line the layout names for it, in the order the
document prints, and each one slices through :func:`td3_field` and hands its
slice straight to its own ``validate_*``; the assembler adds no message, wraps
no error and re-slices nothing.  Six fields have no reader of their own --
the five printed digits and the personal number, which no task in Part 2 asks
for -- and those are read through :func:`td3_field` and judged by nothing,
because verification is 2.14's, 3.2's and 3.3's question.  :class:`MrzDocument`
carries the result: every field exactly as printed, the two halves the name
field is divided into, and :attr:`MrzDocument.sources` -- the raw characters
each field occupies, read by position rather than copied out of a value.

**The composite input is assembled from field names, and that is 3.1's whole
of it.**  :func:`td3_composite_input` concatenates the eight fields in
:data:`TD3_COMPOSITE_FIELDS` -- which is what positions 1-10, 14-20 and 22-43
*are*, because the layout already says so -- and stops there: 3.2 asks whether
those 39 characters agree with the digit at position 44 and 3.3 asks which
field is at fault, so the module still computes no digit and reports no
verdict.  It judges nothing either, and the width check it does not carry is
the reason it must not become a second shape gate: :func:`validate_td3_lines`
decides whether a line is 44 characters, and a caller who skipped that gate
gets a composite input of the wrong length rather than an error.  The three
fields left out are the nationality and the sex marker -- the two identity
fields 2.11 and 2.12 recorded as sitting in the composite's gap -- and the
composite digit itself, which cannot be an input to its own arithmetic.
"""

import dataclasses
import string
import unicodedata
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from .mrz import (
    FILLER,
    CheckDigitResult,
    MrzValueError,
    check_digit_results,
    date_fault,
)

__all__ = [
    "MrzDocument",
    "TD3",
    "TD3_COMPOSITE_FIELDS",
    "TD3_CHECK_DIGIT_FIELDS",
    "TD3_DOCUMENT_CODES",
    "TD3_LINE_1",
    "TD3_LINE_2",
    "TD3_LINE_COUNT",
    "TD3_LINE_LENGTH",
    "TD3_SEX_MARKERS",
    "TRANSLITERATIONS",
    "parse_date_of_birth",
    "parse_date_of_expiry",
    "parse_document_code",
    "parse_document_number",
    "parse_issuing_state",
    "parse_nationality",
    "parse_name",
    "parse_sex",
    "parse_td3",
    "split_name",
    "split_given_names",
    "normalise_names",
    "transliterate_names",
    "td3_composite_input",
    "td3_check_digit_results",
    "td3_field",
    "validate_date_of_birth",
    "validate_date_of_expiry",
    "validate_document_code",
    "validate_document_number",
    "validate_issuing_state",
    "validate_nationality",
    "validate_sex",
    "validate_td3_lines",
]

#: Characters in one TD3 line (ICAO 9303, Part 4, "TD3 Format").
TD3_LINE_LENGTH = 44

#: Lines in a TD3 machine-readable zone.  Always 2, and never a range: a third
#: line is a different format, not a longer TD3.
TD3_LINE_COUNT = 2

#: Line 1 -- the document itself.  ``name`` runs to the end of the line, so it
#: is a 39-character name field padded with the ``<`` filler.
TD3_LINE_1: dict[str, tuple[int, int]] = {
    "document_code": (1, 2),  # "P<" for a passport; the type of document
    "issuing_state": (3, 5),  # 3-letter code of the issuing authority
    "name": (6, 44),  # surname, "<<", given names; filler-padded
}

#: Line 2 -- the holder's identity and the printed check digits.  The
#: ``personal_number`` field is what ICAO calls "optional data" (a passport may
#: use it for a personal number, and a national ID may use it for something
#: else), and the three other check-digit fields are what make a forged line
#: detectable at all.
TD3_LINE_2: dict[str, tuple[int, int]] = {
    "document_number": (1, 9),  # 9 characters, filler-padded when shorter
    "document_number_check_digit": (10, 10),
    "nationality": (11, 13),  # 3-letter code of the holder's nationality
    "date_of_birth": (14, 19),  # YYMMDD
    "date_of_birth_check_digit": (20, 20),
    "sex": (21, 21),  # M, F, X, or < where unspecified
    "date_of_expiry": (22, 27),  # YYMMDD
    "date_of_expiry_check_digit": (28, 28),
    "personal_number": (29, 42),  # 14 characters, filler-padded
    "personal_number_check_digit": (43, 43),
    "composite_check_digit": (44, 44),  # over 1-10, 14-20 and 22-43
}

#: The whole TD3 layout, keyed by line: ``TD3["line_1"]`` and
#: ``TD3["line_2"]``.  These are the *same* dict objects as
#: :data:`TD3_LINE_1` and :data:`TD3_LINE_2`, not copies, so a parser can
#: reach for either name and there is no second table to drift.
TD3: dict[str, dict[str, tuple[int, int]]] = {
    "line_1": TD3_LINE_1,
    "line_2": TD3_LINE_2,
}

#: The document codes a TD3 line 1 may carry, at positions 1-2 (ICAO 9303,
#: Part 4, "TD3 Format").  ``P<`` is what a passport prints: ``P`` for the
#: document type and ``<`` for "no variant".  A bare ``P`` is accepted
#: alongside it because that second character is filler, so a code that lost it
#: is the same document rather than a different one -- and nothing in the rest
#: of Part 2 reads position 2, so the shorter reading costs no other field.
#: The set is exact and closed: any other spelling is rejected, so accepting
#: more is a deliberate edit of this line rather than a side effect.  A
#: frozenset, so no caller can widen it at runtime.
TD3_DOCUMENT_CODES: frozenset[str] = frozenset({"P<", "P"})


def validate_td3_lines(lines: Iterable[str]) -> tuple[str, str]:
    """Return ``lines`` as the two TD3 lines, or raise unless it is a TD3 zone.

    The shape check itself: a TD3 machine-readable zone is
    :data:`TD3_LINE_COUNT` lines of :data:`TD3_LINE_LENGTH` characters, and
    this is the only place in the project that says so in a check rather than in
    a comment.  ``lines`` may be any iterable of strings -- a list or a tuple
    from the OCR step, either way -- and the two are returned in printed order
    so a parser can write ``line_1, line_2 = validate_td3_lines(lines)`` and
    never index for itself.

    What the characters *say* is not checked here: not that they are MRZ
    characters, not that the document code is a passport, and not a check
    digit.  Those are separate answers, and a shape that is right while its
    contents are wrong is still a zone worth parsing and flagging.

    Raises:
        MrzValueError: unless ``lines`` is an iterable of exactly
            :data:`TD3_LINE_COUNT` strings, each exactly
            :data:`TD3_LINE_LENGTH` characters long.  A ``MrzValueError`` is a
            ``ValueError``, so ``except ValueError`` catches it too, and it is
            the one type this raises: a ``None`` zone, a single string where two
            lines were expected, and a line that is not a string are all
            reported as this, rather than escaping as a bare ``TypeError`` a
            caller catching ``MrzValueError`` would never see.
    """
    # Checked before the iteration below: a string is a sequence of
    # one-character lines, so iterating it would report 44 lines and point at
    # the wrong mistake entirely.
    if isinstance(lines, str):
        raise MrzValueError(
            f"a TD3 machine-readable zone is {TD3_LINE_COUNT} lines, "
            f"not one string of {len(lines)} characters"
        )
    try:
        zone = tuple(lines)
    except TypeError:
        raise MrzValueError(
            "a TD3 machine-readable zone must be a sequence of lines, "
            f"not {type(lines).__name__}"
        ) from None
    if len(zone) != TD3_LINE_COUNT:
        raise MrzValueError(
            f"a TD3 machine-readable zone is {TD3_LINE_COUNT} lines, not {len(zone)}"
        )
    # 1-indexed, like every position in this module, so a message naming
    # "line 2" means the line the standard calls line 2.
    for number, line in enumerate(zone, start=1):
        if not isinstance(line, str):
            raise MrzValueError(
                f"TD3 line {number} must be a string, not {type(line).__name__}"
            )
        if len(line) != TD3_LINE_LENGTH:
            raise MrzValueError(
                f"TD3 line {number} is {len(line)} characters, "
                f"not {TD3_LINE_LENGTH}"
            )
    line_1, line_2 = zone
    return line_1, line_2


def _readable_codes() -> str:
    """The accepted document codes, sorted, for a message.

    Sorted so the message is the same string every time, which keeps a log
    greppable; never used to decide anything, only to say what was expected.
    """
    return ", ".join(repr(code) for code in sorted(TD3_DOCUMENT_CODES))


def td3_field(line: str, layout: dict[str, tuple[int, int]], name: str) -> str:
    """Return the characters ``name`` occupies in ``line``, by way of ``layout``.

    The one place in the project where a line is sliced.  Positions are
    1-indexed and inclusive, so the ``- 1`` below is the whole conversion, and
    it is written here once on purpose: it is the single most likely place for
    an off-by-one in Part 2, and a parser that sliced a line for itself would
    have eleven chances to get it wrong and no test to say so.  ``layout`` is
    one of :data:`TD3_LINE_1` or :data:`TD3_LINE_2`, so the field's width
    comes from the table rather than from the caller.

    This checks nothing about the field.  It hands back the characters the
    layout says are there, in both directions -- a field one character too
    wide and a field one too narrow are the same mistake, and only the
    judgement that follows can tell them apart.

    Raises:
        MrzValueError: if ``line`` is not a string, or ``layout`` has no field
            called ``name``.  A ``KeyError`` out of the lookup and a
            ``TypeError`` out of the slice are both the kind of built-in error
            1.9 forbids, and both are a caller mistake rather than a bad
            document, so neither reaches a ``except MrzValueError``.
    """
    if not isinstance(line, str):
        raise MrzValueError(
            f"a TD3 line must be a string, not {type(line).__name__}"
        )
    if name not in layout:
        raise MrzValueError(f"no TD3 field named {name!r}")
    start, end = layout[name]
    return line[start - 1 : end]


def validate_document_code(code: str) -> str:
    """Return ``code`` if it is a TD3 passport document code, else raise.

    The check itself, and it is a closed one: ``code`` must be one of
    :data:`TD3_DOCUMENT_CODES` -- ``P<`` or ``P``.  ``V<`` (a visa) and ``X<``
    (no document at all) are well-formed MRZ codes, not misspellings, so the
    answer is to refuse the line rather than parse a passport out of it.

    What the code says is the whole of the judgement; the filler in a rejected
    code is not normalised away first, because ``P`` on its own and ``P<`` on
    its own are both accepted and a code with anything else in it is not a
    passport whatever the whitespace is doing.

    Raises:
        MrzValueError: for any other value, including one that is not a
            string -- the membership test answers ``False`` for a non-string
            rather than raising, so this is the one failure and it is the
            package's one error type.  The message names the code it was
            given and the codes it wanted, and nothing else: two characters
            that describe a document type, never the line around them.
    """
    if code in TD3_DOCUMENT_CODES:
        return code
    raise MrzValueError(
        f"a TD3 passport document code is {_readable_codes()}, not {code!r}"
    )


def parse_document_code(line_1: str) -> str:
    """Return the document code printed in positions 1-2 of ``line_1``.

    The first field of :func:`parse_td3` to be read: the positions come from
    :data:`TD3_LINE_1` through :func:`td3_field`, so there is no ``line[0:2]``
    here and no parser downstream carrying an index of its own.  The slice is
    handed straight to :func:`validate_document_code`, so the two functions
    cannot disagree about what a passport is.

    ``line_1`` is expected to have already passed :func:`validate_td3_lines`,
    which is what guarantees :data:`TD3_LINE_LENGTH` characters; this function
    does not repeat that check, because a short line is not a document-code
    problem.  It is still total over its input: a line too short to hold a
    code slices to whatever it has, which is then not a code, and a line that
    is not a string at all is reported by :func:`td3_field` rather than left
    to raise a bare ``TypeError`` out of the slice.

    Raises:
        MrzValueError: if ``line_1`` is not a string, or the characters it
            prints at positions 1-2 are not in :data:`TD3_DOCUMENT_CODES`.
            The message carries the code and stops: the rest of the line is
            the identity data the screening is about.
    """
    return validate_document_code(td3_field(line_1, TD3_LINE_1, "document_code"))


def _is_uppercase_letter(character: str) -> bool:
    """Whether ``character`` is one of ``A``-``Z``, the MRZ letter set.

    The two obvious tests are both wrong here.  ``str.isalpha`` answers
    ``True`` for ``"Ü"``, and ``str.isupper`` answers ``True`` for ``"ÜTO"``
    and for ``"1TO"``, so a validator written from them would accept a
    diacritic carried across from the printed name and read it as a country.
    The table is :mod:`string`'s, the same source
    :data:`~app.pipeline.tier0.mrz.CHAR_VALUES` is built from.
    """
    return character in string.ascii_uppercase


def validate_issuing_state(code: str) -> str:
    """Return ``code`` if it is a well-formed TD3 issuing state, else raise.

    The whole of the rule the standard states for positions 3-5: exactly as
    wide as :data:`TD3_LINE_1` says the field is, and every one of those
    characters one of ``A``-``Z``.  The width is *read out of the table*
    rather than typed in as a 3, so the layout stays the only place a position
    is stated and the message cannot describe a width the layout does not have.

    Well-formedness is the whole of the judgement, and a code list is
    deliberately absent.  ``IND`` is three uppercase letters and is accepted;
    it has to be, because ISO 3166-1 alpha-3 assigns ``IND`` to India, so any
    conforming list of issuing states contains it and a list without it would
    refuse every genuine Indian passport.  Recognising a state is a Tier 0
    policy question, answered by a code list that has to be sourced rather
    than remembered -- the rule 1.6 applied to the composite check digit -- and
    it belongs to the rules engine, not to a field reader.

    Raises:
        MrzValueError: unless ``code`` is a string of exactly the layout's
            width whose every character is an uppercase letter, which covers
            the misreads this field actually produces: a digit read for a
            letter, a lower-case read, a filler or a space where a letter
            belongs, and a diacritic from the printed name.  A value that is
            not a string is reported as this too rather than escaping as a bare
            ``TypeError`` a caller catching ``MrzValueError`` would never see.
            The message names the state it was given, which is three characters
            naming a *state*, and stops there.
    """
    if not isinstance(code, str):
        raise MrzValueError(
            f"an issuing state must be a string, not {type(code).__name__}"
        )
    start, end = TD3_LINE_1["issuing_state"]
    width = end - start + 1
    if len(code) != width or not all(_is_uppercase_letter(letter) for letter in code):
        raise MrzValueError(
            f"a TD3 issuing state is {width} uppercase letters (A-Z), not {code!r}"
        )
    return code


def parse_issuing_state(line_1: str) -> str:
    """Return the issuing state printed in positions 3-5 of ``line_1``.

    The second field of :func:`parse_td3` to be read and the same shape as
    :func:`parse_document_code`: the positions come from
    :data:`TD3_LINE_1` through :func:`td3_field`, so there is no ``line[2:5]``
    here, and the slice is handed straight to :func:`validate_issuing_state`, so
    the reader and the judgement cannot disagree about what a well-formed
    issuing state is.

    ``line_1`` is expected to have already passed :func:`validate_td3_lines`,
    which is what guarantees :data:`TD3_LINE_LENGTH` characters; this function
    does not repeat that check, because a short line is not an issuing-state
    problem.  It is still total over its input: a line too short to hold three
    characters slices to whatever it has, which is then not three uppercase
    letters, and a line that is not a string at all is reported by
    :func:`td3_field` rather than left to raise a bare ``TypeError``.

    Raises:
        MrzValueError: if ``line_1`` is not a string, or the characters it
            prints at positions 3-5 are not a well-formed issuing state.  The
            message carries the state and stops: the name behind it is the
            identity data the screening is about.
    """
    return validate_issuing_state(td3_field(line_1, TD3_LINE_1, "issuing_state"))


def parse_name(line_1: str) -> str:
    """Return the name printed in positions 6-44 of ``line_1``, raw.

    The third field of :func:`parse_td3` and the first one that is a *person*
    rather than a document, so this is where the module's care about messages
    matters most.  It is also the first field with no rule of its own: the
    standard states where the name sits and how wide it is, and nothing about
    what the characters may be, because the names it has to carry are not a
    set anyone can enumerate.  So this function **extracts and does not
    judge**.  Nothing is split, stripped or case-folded here;
    :func:`split_name` (2.6) divides this at the ``<<``,
    :func:`split_given_names` (2.7) divides the given-names half into a list,
    and :func:`normalise_names` (2.8) strips filler and normalises case --
    each of them starting from exactly what the one before it returns.

    That is a decision, not an omission, and it cuts the way 2.4's ``IND``
    did.  A diacritic, a lower-case read or a space where a ``<`` belongs is
    an OCR misread, and refusing the document over one would leave 2.8 nothing
    to clean up and turn a flaggable field into a dropped document.  Whether a
    well-formed field is *acceptable* is a Tier 0 policy question answered by
    the rules engine, not by a field reader.

    The one thing this does check is its own width, and it needs to: every
    other reader in this module rejects a short line only as a side effect of
    checking its contents, and this one has no content rule to do it with, so
    a line cut off mid-name would slice to whatever arrived and hand back a
    short string -- and for the empty case, ``""``, which every consumer of
    this function would read as a document that printed no name.  A line
    longer than the zone is fine: the field is read by position, so surplus
    characters are not part of it.

    Raises:
        MrzValueError: if ``line_1`` is not a string (reported by
            :func:`td3_field`, so no bare ``TypeError`` escapes), or if it
            stops before the end of the name field.  The message carries the
            positions and the two lengths and **never the name**: this is the
            identity data the screening is about, it is the one field where
            2.2's rule would have been easiest to break by accident, and
            2.3's and 2.4's habit of naming the value it rejected stops at
            the name.
    """
    raw = td3_field(line_1, TD3_LINE_1, "name")
    start, end = TD3_LINE_1["name"]
    width = end - start + 1
    if len(raw) != width:
        raise MrzValueError(
            f"the TD3 name field is positions {start}-{end}, {width} characters, "
            f"but line 1 carried only {len(raw)} of them"
        )
    return raw


def split_name(name: str) -> tuple[str, str]:
    """Return ``name`` as ``(surname, given_names)``, split on the ``<<``.

    The second half of what the name field is for, and the first step in
    Part 2 that *interprets* rather than extracts.  ``<<`` is the separator
    the standard prints between the primary identifier (surname) and the
    secondary identifiers (given names).  It is the MRZ filler twice, taken
    from :data:`~app.pipeline.tier0.mrz.FILLER` rather than typed in here, so
    there is one source for the character in the project.

    The two halves come back **raw**.  ``given_names`` is one string that
    still carries the single fillers between the given names and all 19 that
    pad the field, because :func:`split_given_names` (2.7) splits it into a
    list and :func:`normalise_names` (2.8) strips filler and case -- each
    starting from exactly what this returns.  Nothing is trimmed, case-folded
    or transliterated here.

    The split is :meth:`str.partition`, which is lossless: put the two halves
    back together with the separator between them and the field is what it
    was.

    **Only the first ``<<`` splits.**  The field carries one, so a second is a
    misread -- most likely a single filler doubled -- and it stays in the
    given-names half, where :func:`split_given_names`'s ``<`` split reads it
    as the empty entry between two names and drops it.  Putting it in the
    surname would split a person's name in the wrong place, and refusing would
    drop the document over a misread.

    Two shapes have no separator to find, and both are answered rather than
    refused.

    * A **mononym** -- a field with no ``<<`` in it, which is either a holder
      with one name or a ``<<`` misread as ``<`` -- comes back whole as the
      surname with no given names.  Those two are indistinguishable here, and
      so is the alternative of treating the single name as the given names,
      which would be a guess 2.14's "parsing must not silently fix it" rules
      out.  The cost is therefore a labelled one: a mononym's given-names list
      is empty, and every consumer downstream has to live with that.
    * A **name field of nothing but filler** splits to an empty surname,
      which 2.5 said is this task's decision to make deliberately rather than
      inherit.  It is returned like any other field, on 2.4's ``IND``
      reasoning: whether a well-formed field is *acceptable* is a Tier 0
      policy question for the rules engine, and a splitter that raised here
      would turn a flaggable name into a dropped document.

    ``name`` is expected to be what :func:`parse_name` returned, and this
    function does not repeat the width check 2.5 does -- a short field is not
    a separator problem.  It is still total over its input, so nothing
    escapes as an error type the package does not raise.

    Raises:
        MrzValueError: if ``name`` is not a string.  :meth:`str.partition`
            raises ``AttributeError`` on ``None`` and ``TypeError`` on bytes,
            and a caller's ``except MrzValueError`` would miss both.  The
            message names the type it was given and **never the name**: this
            is the identity data the screening is about, and 2.5 is why that
            rule is stated here rather than assumed.
    """
    if not isinstance(name, str):
        raise MrzValueError(
            f"a TD3 name must be a string, not {type(name).__name__}"
        )


    surname, _separator, given_names = name.partition(FILLER * 2)
    return surname, given_names


def split_given_names(given_names: str) -> list[str]:
    """Return the given names as a list, split on the single filler.

    The last of the three steps the name field is read in: 2.5 extracted it,
    :func:`split_name` divided it into a surname and this, and this divides
    the secondary identifiers into the individual names a person answers to.
    So ``"ANNA<MARIA"`` comes back as ``["ANNA", "MARIA"]`` -- and
    ``"ANNA MARIA"`` comes back as ``["ANNA MARIA"]``, one name with a space
    in it rather than two.

    **The split is on the single filler and on nothing else.**  The standard
    prints one filler between the secondary identifiers and uses a space in
    the visible zone, so a space where the filler belongs is an OCR misread
    and not a separator: merging on it here would be 2.14's "parsing must not
    silently fix it", and 2.8 is the task that strips a space, so a splitter
    that did it would leave 2.8 nothing to clean up.  The character is
    :data:`~app.pipeline.tier0.mrz.FILLER`, the same source the ``<<`` came
    from, so the project has one place the filler is stated.

    **Empty entries are dropped**, and that is the second half of the task.
    Every shape the field can carry produces them: the 19 fillers that pad it,
    a leading or trailing one, and the doubled ``<<`` :func:`split_name`
    deliberately leaves behind as a misread.  Each is an empty entry between
    two separators rather than a name, and a list holding ``""`` would name a
    person who has no name.

    That rule has one case where it does real work rather than restating
    what :meth:`str.split` already does.  Splitting ``""`` on any separator
    returns ``[""]`` -- a one-element list -- and a splitter that trusted
    :meth:`str.split` alone would hand 2.13 a holder with one empty given
    name.  So the drop is written out below rather than inherited, and the
    empty list is the honest answer for both the shapes that produce no
    given names: a mononym's empty half, and a name field of nothing but
    filler.  Both are the labelled cost 2.6 recorded, and a consumer
    downstream has to live with them.

    **Nothing is cleaned.**  An entry is the characters between two fillers,
    exactly as printed: not stripped, not case-folded, not transliterated, and
    not rejected for holding a digit, a space or a diacritic.  2.8 strips
    filler and normalises case, and it has to start from exactly what this
    returns, so a splitter that cleaned an entry would leave it nothing to
    do and make its tests unfalsifiable.  That includes a whitespace-only
    entry, which is kept here -- it is not a name, but saying so is
    :func:`normalise_names`' judgement to make over the whole list, and it is
    the one this makes.

    The names come back **in the order the field printed them**, because the
    order is part of what the document says and a later comparison across
    documents (12.15) has to be able to see that the first one differs.
    The result is a :class:`list`, not a tuple and not a generator: 2.13
    iterates it, and a generator would be spent by its first consumer.

    ``given_names`` is expected to be the second half :func:`split_name`
    returned, and this function does not repeat the width check 2.5 does --
    a short value is not a separator problem, and there is no reading of it
    this could not hand on to 2.8.  It is still total over its input.

    Raises:
        MrzValueError: if ``given_names`` is not a string.  :meth:`str.split`
            raises ``AttributeError`` on ``None`` and ``TypeError`` on bytes,
            and a caller's ``except MrzValueError`` would miss both.  The
            message names the type it was given and **never the names**:
            this is still the identity data the screening is about, and 2.5 is
            why that rule is stated here rather than assumed.
    """
    if not isinstance(given_names, str):
        raise MrzValueError(
            f"TD3 given names must be a string, not {type(given_names).__name__}"
        )




    return [name for name in given_names.split(FILLER) if name]










#: not something a second caller should build on.
_WHITESPACE_REMOVED = str.maketrans("", "", string.whitespace)


def _clean_name(name: str) -> str:
    """Return ``name`` with its filler and whitespace out and its case up.

    One name at a time and one rule, so the surname and each of the given
    names cannot be cleaned differently.  The order of the three steps is the
    order the task states them in and none of them depends on another: the
    filler and the whitespace are both deletions and the case is a mapping,
    so applying them in any order gives the same string.

    :meth:`str.upper` rather than an ASCII fold is deliberate.  The MRZ
    alphabet is ``A``-``Z``, so a fold to ASCII would be *closer* to what a
    name field may contain -- and it would quietly do 2.9's job, leaving the
    transliteration map nothing to add and no reason to exist.  A diacritic
    therefore survives here, unchanged and upper-cased, and 2.9 is what turns
    it into the letter the document meant.
    """
    return name.replace(FILLER, "").translate(_WHITESPACE_REMOVED).upper()


def normalise_names(
    surname: str, given_names: Iterable[str]
) -> tuple[str, list[str]]:
    """Return the surname and given names with filler, space and case cleaned.

    The last step of the name field, and the only one that *edits* a name
    rather than dividing it.  The standard prints the name in capitals, with
    the filler carrying every gap -- there is no space in the ICAO alphabet
    at all -- so anything else in the field is a misread by the OCR engine
    that read it, and this is where the three of those come out:

    * **the filler** (:data:`~app.pipeline.tier0.mrz.FILLER`), which is
      still inside a name when a *mononym* was misread -- the ``<<`` printed
      between the primary and secondary identifiers arrived as a ``<`` and a
      space, so :func:`split_name` read the whole field as a surname with no
      given names, and the leftover filler is inside it.  :func:`split_given_names`
      cannot leave one in a given name, because it splits on exactly that
      character, so the strip is load-bearing for the surname only.
    * **the whitespace**, everywhere in the name and not only at the ends,
      because that is where the misread is: :func:`split_given_names` holds
      ``"  anna  maria  "`` as a *single* entry, and this is the function
      that has to decide what to do with it.
    * **the case**, up.  Both halves of the task, and both are removals of
      information the document never carried.

    **Nothing is invented, and that is what a misread costs.**  The line
    ``"P<UTO LIE<SOPHIE"`` -- the one this task names -- prints as
    ``"LIE<<SOPHIE"``: a surname, the ``<<``, and one given name.  It arrived
    with a space where a filler belongs, so :func:`split_name` took the
    ``<<``-misread-as-``<`` branch its docstring names and the whole field
    became a surname.  This strips the space and the filler and the answer is
    ``("LIESOPHIE", [])``: one name, no given names.  **SOPHIE is not
    recovered**, because recovering her would mean writing a ``<<`` into a
    string that does not have one, which is 2.14's "parsing must not silently
    fix it".  The cost is a labelled one -- a holder whose secondary
    identifiers were lost to a misread shows up as a holder with none, and a
    screening has to be able to say that rather than paper over it.

    The same reasoning is why the whitespace is *removed* and not replaced
    by a filler.  A space where a filler belongs is evidence that a filler
    was there, and using that evidence to put one back is the same guess with
    extra steps.  It is also why nothing here is *split*: a space is not a
    separator, :func:`split_given_names` already said so, and
    ``"ANNA MARIA"`` cleans to one name called ``"ANNAMARIA"`` rather than
    two.

    **A given name that is nothing once cleaned is dropped, and the surname
    is not.**  That is the judgement :func:`split_given_names` explicitly
    deferred -- it keeps a whitespace-only entry because "it is not a name,
    but saying so is a judgement about the whole list and it is 2.8's to make
    over it" -- and it is the same argument that function made for the empty
    entry, one step later: a list holding ``""`` names a person who has no
    name, and a consumer downstream cannot tell that from a real one.  The
    surname keeps its ``""``, because :func:`split_name` already returns one
    for a name field of nothing but filler, and a cleaner that also dropped
    it would make "no surname" indistinguishable from "not parsed" and would
    hand 2.13 a differently shaped result depending on the document.

    **Nothing is transliterated.**  ``"MÜLLER"`` comes back as ``"MÜLLER"``:
    it is already upper case and holds no filler and no space, so nothing
    here applies to it.  Turning a diacritic into its base letter is 2.9's
    job, with a map that has to be sourced, and a cleaner that reached for
    ``unicodedata`` here would leave 2.9 unfalsifiable.

    ``surname`` and ``given_names`` are expected to be what
    :func:`split_name` and :func:`split_given_names` returned, and neither the
    field's width nor the separator is re-checked here: a short name is not a
    cleaning problem, and there is no reading of a name this could not hand
    on to 2.9.  ``given_names`` may be any iterable of strings rather than
    only a list, because a caller building the list itself should not have to
    know how this one is built -- but a bare ``str`` or ``bytes`` is refused
    rather than iterated, for the reason :func:`validate_td3_lines` refuses a
    single string where two lines were expected: a string is a sequence, so
    iterating one would hand back a name per *character* and report nothing
    wrong.

    Raises:
        MrzValueError: if ``surname`` is not a string, if ``given_names`` is
            not a non-string iterable, or if any one of its entries is not a
            string.  :meth:`str.replace` raises ``AttributeError`` on
            ``None`` and ``TypeError`` on ``bytes`` and iterating a
            non-iterable raises ``TypeError`` again, and a caller's
            ``except MrzValueError`` would miss all three.  Every message
            names the *type* it was given and **never a name**: this is
            still the identity data the screening is about, and 2.5 is why
            that rule is restated here rather than assumed.
    """
    if not isinstance(surname, str):
        raise MrzValueError(
            f"a TD3 surname must be a string, not {type(surname).__name__}"
        )




    if isinstance(given_names, (str, bytes)) or not isinstance(
        given_names, Iterable
    ):
        raise MrzValueError(
            "TD3 given names must be a sequence of names, not "
            f"{type(given_names).__name__}"
        )
    names = tuple(given_names)
    for name in names:
        if not isinstance(name, str):
            raise MrzValueError(
                f"each TD3 given name must be a string, not {type(name).__name__}"
            )



    return _clean_name(surname), [name for name in map(_clean_name, names) if name]
























#: at all, and the code below reads that as one ``dict.get`` with the character
#: as its own default.  Exported, because like the layout tables it is the one
#: place a value is stated, and a rules engine that wants to flag a name it
#: could not transliterate needs to read what was attempted.
TRANSLITERATIONS: dict[str, str] = {
    "ß": "SS",
    "Ø": "O",
    "Ł": "L",
    "Đ": "D",
}



def _strip_diacritics(name: str) -> str:
    """Return ``name`` with every combining mark taken off it.

    **Canonical** decomposition (``NFD``) and not compatibility (``NFKD``),
    and that is the whole of the difference.  ``NFKD`` would also expand the
    ``DZ`` digraph to ``D`` plus ``Z``-with-caron, a full-width letter to its
    ASCII twin and a ligature to its two letters: those are rewrites of a name
    rather than the taking off of an accent, and they would be applied to a
    name that carries no accent at all.  ``NFD`` is the decomposition that
    says "this letter is written with a mark on it" and nothing more.

    A character with no decomposition is returned as it is, and a combining
    mark with no letter in front of it is the one character this removes on
    its own -- the only way a name can come out of :func:`transliterate_names`
    shorter than it went in, and the reason that function drops a given name
    it empties.
    """
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _transliterate_name(name: str) -> str:
    """Return ``name`` with every character it can be turned into an MRZ one.

    One name at a time and one rule, so the surname and each of the given
    names cannot be transliterated differently -- the same argument
    :func:`_clean_name` makes, and the reason that helper exists rather than
    the rule being written out twice.

    The two rules run in this order and neither can pre-empt the other: a
    character in :data:`TRANSLITERATIONS` does not decompose, and a combining
    mark is not a key, so the order is a readability choice.  The named
    substitutions go first because they are the part a reader can check
    against the standard, and the mechanical rule then sweeps up everything
    else.
    """
    substituted = "".join(
        TRANSLITERATIONS.get(character, character) for character in name
    )
    return _strip_diacritics(substituted)


def transliterate_names(
    surname: str, given_names: Iterable[str]
) -> tuple[str, list[str]]:
    """Return the surname and given names with each diacritic taken off.

    The last step of the name field, and the one that makes a parsed name
    readable by everything downstream of it.  The MRZ alphabet is ``A``-``Z``
    and nothing else, so a name carrying a diacritic is a name the rest of
    the pipeline cannot read: :func:`~app.pipeline.tier0.mrz.char_value`
    raises on it, which means a check-digit comparison and any later name
    comparison (12.15) either refuses it or has to special-case it.  The
    standard's answer is that the diacritic is a property of the *visible*
    zone and the machine-readable one spells the base letter, so this is
    where ``MÜLLER`` becomes ``MULLER``.

    **Two rules, and the second one is not a table.**  The first is
    :data:`TRANSLITERATIONS`, four letters long -- ``ß``, ``Ø``, ``Ł`` and
    ``Đ`` -- being the characters Unicode will not decompose.  The second is
    :func:`_strip_diacritics`, which takes the combining mark off every
    letter that decomposes into one.  Together they cover the accented Latin
    letters a name is actually written with, and they are a rule and four
    values rather than two hundred values because 1.6's rule is not to quote a
    remembered table.

    **Anything else is carried through unchanged, and that is the cost.**
    The AE and OE ligatures, thorn, eth, eng, the ``H`` with a stroke, the
    ``IJ`` ligature, the ``DZ`` digraph, and every non-Latin letter are not
    in the map and are returned exactly as they arrived.  Dropping them would
    be the worst kind of silent fix -- a name changed with nothing left behind
    to show it had changed, which is 2.14's "parsing must not silently fix it"
    in the one direction 2.14 did not anticipate.  Carrying them means such a
    name is still not in the MRZ alphabet, so :func:`char_value` still raises
    on it, and the flagging is the rules engine's job (Part 12) rather than
    this function's: Tier 0 reports what the document says, and an invented
    ``AE`` is not what it said.

    **Nothing is re-cased, re-stripped or re-split.**  The names arriving here
    are already upper case with no filler and no whitespace, and 2.7 has
    already divided them, so repeating any of that here would make those two
    tasks unfalsifiable.  ``str.upper`` is not called again -- which is also
    why :data:`TRANSLITERATIONS` is keyed by the upper-case characters only:
    :meth:`str.upper` has already turned ``ø`` into ``Ø`` and ``weiß`` into
    ``WEISS``, so the lower-case forms cannot reach this function, and the
    sharp-s entry answers a caller that skips the previous step rather than
    anything on the real path.  A name is not split on a space either:
    ``"ANNA MARIA"`` is one name, and 2.8 already said a space is not a
    separator.

    **A given name that is nothing once transliterated is dropped, and the
    surname is not**, which is :func:`normalise_names`' rule rather than a new
    one.  It is restated because this is the one step that *can* empty a name:
    a name of nothing but combining marks has no base letter to keep, and a
    list holding ``""`` is what 2.7 and 2.8 each removed on the way past.  The
    surname keeps its ``""`` for 2.8's reason -- "no surname" has to stay
    distinguishable from "not parsed".

    **A name can come out longer, and is not cut back.**  ``ß`` becomes the
    two characters ``SS``, so ``STRAßE`` is six characters where the name
    field it came from is 39 wide; that is fine, because the width is a
    property of the *field* and 2.5 already checked it.  Truncating here to
    keep the width would change a name, and a name is the one thing in this
    module that must not be invented.

    ``surname`` and ``given_names`` are expected to be what
    :func:`normalise_names` returned, and ``given_names`` may be any iterable
    of strings rather than only a list, for the reason 2.8 gives.  A bare
    ``str`` or ``bytes`` is refused rather than iterated, again for 2.8's
    reason: a string is a sequence, so iterating one would hand back a name
    per character and report nothing wrong.

    Raises:
        MrzValueError: if ``surname`` is not a string, if ``given_names`` is
            not a non-string iterable, or if any one of its entries is not a
            string.  Every message names the *type* it was given and **never
            a name**: this is still the identity data the screening is about,
            and 2.5 is why that rule is restated here rather than assumed.
    """
    if not isinstance(surname, str):
        raise MrzValueError(
            f"a TD3 surname must be a string, not {type(surname).__name__}"
        )
    if isinstance(given_names, (str, bytes)) or not isinstance(
        given_names, Iterable
    ):
        raise MrzValueError(
            "TD3 given names must be a sequence of names, not "
            f"{type(given_names).__name__}"
        )
    names = tuple(given_names)
    for name in names:
        if not isinstance(name, str):
            raise MrzValueError(
                f"each TD3 given name must be a string, not {type(name).__name__}"
            )
    transliterated = [_transliterate_name(name) for name in names]
    return _transliterate_name(surname), [
        name for name in transliterated if name
    ]


def validate_document_number(number: str) -> str:
    """Return ``number`` if a TD3 line 2 printed one, else raise.

    The first field of line 2, and the first reader in this module that
    **judges** what it extracts rather than only locating it.  The two rules
    are the ones the standard states for positions 1-9: the field is as wide
    as :data:`TD3_LINE_2` says it is, and it prints a number.  The width is
    *read out of the table* rather than typed in as a 9, for
    :func:`validate_issuing_state`'s reason -- the layout stays the only place
    a position is stated, and a message cannot describe a width the layout
    does not have.

    **"Non-empty" means non-empty once the filler is taken out, and that is
    the decision this field turned on.**  The field is nine characters wide
    whatever the number is, and a number shorter than that is padded on the
    right, so ``"L898902C<"`` is a complete number and ``"<<<<<<<<<"`` is no
    number at all -- and a plain ``if not number`` accepts both, because
    neither is an empty string.  The filler
    (:data:`~app.pipeline.tier0.mrz.FILLER`) is the *only* character the
    standard itself uses to mean "no value here", which is why it is the one
    that is removed before the emptiness is judged and why the padding
    elsewhere in the field is not treated as emptiness: ``"A<<<<<<<<"`` is a
    one-character number, not a missing one.

    The emptiness is judged **before** the width, so a field that holds nothing
    is reported as the missing number it is rather than as a line that stopped
    early.  The two are different mistakes and the first is the one the
    document made.

    **The number is returned exactly as it was printed, padding included,
    and that is load-bearing rather than untidy.**  Position 10 is the check
    digit over positions 1-9 *as printed*, and
    :func:`~app.pipeline.tier0.mrz.char_value` maps the filler to ``0`` for
    exactly this reason: the filler is a character the check digit is
    computed over, not tidying waiting to happen.  A stripped number is also
    one that no longer occupies the nine positions the layout gives it, and
    the fact that a *trailing* filler would not change the digit is a trap
    rather than a licence -- the two agree on the specimen and diverge the
    moment the filler is anywhere else.  Nothing is stripped, re-cased or
    otherwise edited either: :func:`normalise_names` cleans a *name* and
    this is not one.

    **Nothing about the characters is judged, and that is the limit of the
    task rather than an oversight.**  There is no space in the MRZ alphabet,
    so a field carrying one is a misread -- but it is not empty, and
    :func:`~app.pipeline.tier0.mrz.check_digit` is what raises on it, so the
    failure is reported rather than lost.  A validator written to also demand
    the MRZ alphabet here would be inventing a rule the task does not state,
    and would move the check to the wrong side of 2.14's "parsing must not
    silently fix it": reading a number is not verifying one, and whether a
    given number is an *acceptable* passport number is the rules engine's
    question (Part 12), as 2.4 found for a code list.

    **The message does not carry the number, where 2.3's and 2.4's do.**
    Those named a document *type* and a *state*, and neither names a person.
    A document number is the identifier the screening is about and it is
    unique to one holder's document, so this names the width it wanted and,
    for the empty field, the character that filled it -- which is the whole of
    the diagnosis -- and neither of those is the value.

    Raises:
        MrzValueError: unless ``number`` is a string of exactly the layout's
            width that prints at least one character other than the filler.
            A value that is not a string is reported as this too rather than
            escaping as a bare ``TypeError`` a caller catching
            ``MrzValueError`` would never see -- ``bytes`` being the case that
            matters, since a byte string has a length and would pass a
            validator that measured before it checked the type.
    """
    if not isinstance(number, str):
        raise MrzValueError(
            f"a TD3 document number must be a string, not {type(number).__name__}"
        )
    if not number.replace(FILLER, ""):
        start, end = TD3_LINE_2["document_number"]
        raise MrzValueError(
            f"a TD3 document number must print at least one character that is "
            f"not the filler, but positions {start}-{end} held nothing but it"
        )
    start, end = TD3_LINE_2["document_number"]
    width = end - start + 1
    if len(number) != width:
        raise MrzValueError(
            f"a TD3 document number is {width} characters (positions "
            f"{start}-{end}), not {len(number)}"
        )
    return number


def parse_document_number(line_2: str) -> str:
    """Return the document number printed in positions 1-9 of ``line_2``.

    The fourth field of :func:`parse_td3` and the same shape as
    :func:`parse_issuing_state`: the positions come from
    :data:`TD3_LINE_2` through :func:`td3_field`, so there is no ``line[:9]``
    here, and the slice is handed straight to
    :func:`validate_document_number`, so the reader and the judgement cannot
    disagree about what a document number is.

    **Line 2, and not line 1, and the cost of that is worth stating.**
    Line 1's positions 1-9 are the document code and the issuing state, so a
    reader pointed at the wrong table returns different text and cannot pass
    by accident -- but a caller that hands this function the wrong line gets
    ``"P<UTOERIK"`` rather than an error, because that is not empty and is
    nine characters long.  The only thing that disagrees is the check digit at
    position 10 of the real line 2, and 2.14 is the task that says so.

    ``line_2`` is expected to have already passed :func:`validate_td3_lines`,
    which is what guarantees :data:`TD3_LINE_LENGTH` characters; this function
    does not repeat that check, because a short line is not a
    document-number problem.  It is still total over its input, and the width
    rule is what keeps a short line honest: a line that stops before position
    9 slices to something short, which is a line that stopped early rather
    than a passport with a four-character number.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td3_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 1-9 are not a document number.
            The message carries the positions, the width and what was
            expected, and **never the number**: it is the identity data the
            screening is about.
    """
    return validate_document_number(
        td3_field(line_2, TD3_LINE_2, "document_number")
    )


def validate_nationality(code: str) -> str:
    """Return ``code`` if it is a well-formed TD3 nationality, else raise.

    The second field of line 2 and the first one the check digits never
    reach.  The whole of the rule the standard states for positions 11-13 is
    the rule :func:`validate_issuing_state` states for positions 3-5: exactly
    as wide as :data:`TD3_LINE_2` says the field is, and every one of those
    characters one of ``A``-``Z``.  The width is *read out of the table* for
    the same reason -- the layout stays the only place a position is stated,
    and a message cannot describe a width the layout does not have.

    **``IND`` is accepted, and this is 2.4's decision carried over rather than
    re-derived.**  The task asks for "3 uppercase letters" *and* for a test
    rejecting ``IND``, which cannot both hold: ``IND`` is three uppercase
    letters, and ISO 3166-1 alpha-3 assigns it to India, so every conforming
    list of nationality codes contains it.  The only implementations that
    reject it hold a list with India missing, and that parser refuses every
    genuine Indian passport.  **No list of nationality codes ships here**,
    which is the decision rather than an omission: a nationality list is a
    second list to be sourced rather than a second rule to invent, and
    recognising one is a Tier 0 policy question belonging to the rules engine
    (Part 12), not to a field reader.

    **The standard gives this field no "unspecified" value, so there is no
    emptiness rule here and the filler is not a special case.**  The sex marker
    may legitimately print a filler -- 2.12's :func:`validate_sex` accepts it
    for that reason -- where a nationality may not, because there is no such
    thing as an unknown nationality in a TD3 zone.  ``"<<<"`` is therefore a
    misread rejected on the ordinary ground -- the filler is not one of
    ``A``-``Z`` -- and *not* a missing value, which is 2.10's rule and does not
    repeat here: a document number can be short and padded, and a three-letter
    code that is short is not a code.

    **The message does not carry the code, which is where this field departs
    from 2.3's and 2.4's.**  Those named a document *code* and an issuing
    *state*, and both are properties of the document.  A nationality is a
    property of the **holder**, and 2.10 is where that reasoning started: a
    document number is unique to one holder's document and its messages carry
    the width and the filler rather than the value.  So this names the width,
    the positions and the alphabet, and never what it found.

    Nothing is edited, and here there is nothing to edit: the only value that
    passes is already three uppercase letters, so 2.8's cleaning and 2.9's
    transliteration have no work to do on it and repeating either would be
    inventing a second answer for a field that has one.

    Raises:
        MrzValueError: unless ``code`` is a string of exactly the layout's
            width whose every character is an uppercase letter, which covers
            the misreads this field actually produces: a digit read for a
            letter, a lower-case read, a filler or a space where a letter
            belongs, and a diacritic carried across from the printed name.  A
            value that is not a string is reported as this too rather than
            escaping as a bare ``TypeError`` a caller catching
            ``MrzValueError`` would never see -- ``bytes`` being the case that
            matters, since ``b"UTO".isalpha()`` is ``True``.
    """
    if not isinstance(code, str):
        raise MrzValueError(
            f"a TD3 nationality must be a string, not {type(code).__name__}"
        )
    start, end = TD3_LINE_2["nationality"]
    width = end - start + 1
    if len(code) != width or not all(_is_uppercase_letter(letter) for letter in code):
        raise MrzValueError(
            f"a TD3 nationality is {width} uppercase letters (A-Z) at positions "
            f"{start}-{end}, and those positions printed something else"
        )
    return code


def parse_nationality(line_2: str) -> str:
    """Return the nationality printed in positions 11-13 of ``line_2``.

    The second field of :func:`parse_td3` to come out of line 2 and the same
    shape as :func:`parse_document_number`: the positions come from
    :data:`TD3_LINE_2` through :func:`td3_field`, so there is no ``line[10:13]``
    here, and the slice is handed straight to :func:`validate_nationality`, so
    the reader and the judgement cannot disagree about what a well-formed
    nationality is.

    **The cost of reading the wrong line is worse here than anywhere else in
    this module, and it is worth stating rather than hiding.**  Line 1's
    positions 11-13 are the middle of the surname ``ERIKSSON``, so a reader
    pointed at the wrong table returns ``"SON"`` -- and unlike the document
    number's ``"P<UTOERIK"``, that is *not* caught by this task's rule, because
    ``"SON"`` is three uppercase letters.  :func:`validate_issuing_state` will
    not catch it either: no check digit covers positions 11-13, since the
    composite digit covers 1-10, 14-20 and 22-43 and this field sits in the
    gap between the first two spans.  It is the one identity field with no
    arithmetic of its own, which is why 2.13's caller has to pass the right
    line and why whether a nationality is *plausible* is the rules engine's
    question (Part 12) rather than a check digit's.

    A line longer than the zone is fine: the field is read by position, so
    surplus characters are not part of it.  A line that stops before position
    13 slices to something short, which is then not three uppercase letters --
    the same thing 2.10 relies on for the document number.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td3_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 11-13 are not a well-formed
            nationality.  The message carries the positions, the width and the
            alphabet, and **neither the nationality nor anything else on the
            line**: it is the identity data the screening is about.
    """
    return validate_nationality(td3_field(line_2, TD3_LINE_2, "nationality"))


def validate_date_of_birth(date: str) -> str:
    """Return ``date`` if a TD3 line 2 printed a date of birth, else raise.

    Positions 14-19, **the width read out of :data:`TD3_LINE_2` rather than
    typed in**, for :func:`validate_issuing_state`'s reason, and the month and
    day judged by :func:`~app.pipeline.tier0.mrz.date_fault` -- 3.11's rule,
    kept in :mod:`app.pipeline.tier0.mrz` so that the three formats cannot
    disagree about what a day is.  ``"993199"`` and ``"013200"`` are refused
    because their month is 31 and 32; ``"AAAAAA"`` and ``"<<<<<<"`` are still
    accepted, because a field of characters the standard does not print here is
    a misread for the check digit beside it to report rather than a date this
    function can rule on.

    What the width *is* for is 2.10's reason restated on a field that cannot be
    short by padding: a line which stops before position 19 slices to a short
    field, and that is a line that stopped early rather than a document
    carrying a five-character date of birth.

    **The date is returned exactly as printed**, which is load-bearing rather
    than untidy, and the specimen is the proof: position 20 is the check digit
    over positions 14-19 *as printed*, and
    :func:`~app.pipeline.tier0.mrz.check_digit` on ``"740812"`` is the ``2``
    the ICAO document prints there.  Trimmed, re-cased or otherwise edited, the
    answer would be to a question nobody asked -- and 3.2 verifies the digit
    against whatever comes back, so an edit would be reported as a mismatch
    rather than as the mistake it is.

    **The message does not carry the date**, for 2.10's reason: a date of
    birth is the holder's, and 2.11 is where that was carried across the line
    to a field the standard gave no "unspecified" value to.  This names the
    width it wanted and the positions it looked at, and stops.

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
            f"a TD3 date of birth must be a string, not {type(date).__name__}"
        )
    start, end = TD3_LINE_2["date_of_birth"]
    width = end - start + 1
    if len(date) != width:
        raise MrzValueError(
            f"a TD3 date of birth is {width} characters (positions "
            f"{start}-{end}), not {len(date)}"
        )
    fault = date_fault(date)
    if fault is not None:
        raise MrzValueError(
            f"a TD3 date of birth (positions {start}-{end}) has a {fault} that "
            f"no date can print"
        )
    return date


def parse_date_of_birth(line_2: str) -> str:
    """Return the date of birth printed in positions 14-19 of ``line_2``.

    The same shape as :func:`parse_nationality`: the positions come from
    :data:`TD3_LINE_2` through :func:`td3_field`, so there is no ``line[13:19]``
    here, and the slice is handed straight to :func:`validate_date_of_birth`,
    so the reader and the judgement cannot disagree about how wide a date of
    birth is.

    ``line_2`` is expected to have already passed :func:`validate_td3_lines`,
    which is what guarantees :data:`TD3_LINE_LENGTH` characters; this function
    does not repeat that check, because a short line is not a date-of-birth
    problem.  It is still total over its input, and the width rule is what
    keeps a short line honest -- which is worth saying plainly, because on a
    full-length line this reader **cannot fail**: the layout guarantees six
    characters, so what a date can get wrong is its meaning, and that is
    3.11's answer rather than this one.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td3_field`, so no bare ``TypeError`` escapes), or if the
            characters it prints at positions 14-19 are not a date of birth.
            The message carries the positions, the width and what was
            expected, and **never the date**: it is the identity data the
            screening is about.
    """
    return validate_date_of_birth(td3_field(line_2, TD3_LINE_2, "date_of_birth"))


def validate_date_of_expiry(date: str) -> str:
    """Return ``date`` if a TD3 line 2 printed a date of expiry, else raise.

    Positions 22-27, and :func:`validate_date_of_birth`'s rule unchanged: the
    width is read out of :data:`TD3_LINE_2` and the month and day are judged by
    :func:`~app.pipeline.tier0.mrz.date_fault`, which knows nothing about which
    of the two dates a field is.  3.13 gives an expiry its own century rule
    rather than the date of birth's, which is a question the range check does
    not touch.

    **The expiry is returned exactly as printed**, for the same reason the
    date of birth is: position 28 is the check digit over positions 22-27 as
    printed, and :func:`~app.pipeline.tier0.mrz.check_digit` on ``"120415"`` is
    the ``9`` the specimen prints there.  **That agreement is a trap rather
    than a licence**, and the test says so: the six characters one to the right
    of the field also come to ``9``, so the arithmetic cannot tell a correct
    reader from one that is off by one, and the layout is what settles it --
    the same trap 2.10 recorded for a trailing filler.

    The message does not carry the date, for :func:`validate_date_of_birth`'s
    reason.

    Raises:
        MrzValueError: unless ``date`` is a string of exactly the layout's
            width, including when it is not a string at all.
    """
    if not isinstance(date, str):
        raise MrzValueError(
            f"a TD3 date of expiry must be a string, not {type(date).__name__}"
        )
    start, end = TD3_LINE_2["date_of_expiry"]
    width = end - start + 1
    if len(date) != width:
        raise MrzValueError(
            f"a TD3 date of expiry is {width} characters (positions "
            f"{start}-{end}), not {len(date)}"
        )
    fault = date_fault(date)
    if fault is not None:
        raise MrzValueError(
            f"a TD3 date of expiry (positions {start}-{end}) has a {fault} that "
            f"no date can print"
        )
    return date


def parse_date_of_expiry(line_2: str) -> str:
    """Return the date of expiry printed in positions 22-27 of ``line_2``.

    The same shape as :func:`parse_date_of_birth`: the positions come from
    :data:`TD3_LINE_2` through :func:`td3_field`, and the slice is handed
    straight to :func:`validate_date_of_expiry`.

    **The cost of reading the wrong line is higher here than anywhere else in
    this module, and it is worth stating rather than hiding.**  Line 1's
    positions 22-27 are the middle of the given name ``MARIA``, so a reader
    pointed at the wrong table returns ``"ARIA<<"`` -- six characters, the
    right width, and this validator accepts it.  What usually catches it is
    arithmetic: the printed digit at position 28 is computed over positions
    22-27, and a different six characters usually give a different one.  **On
    the specimen they do not**: :func:`~app.pipeline.tier0.mrz.check_digit` on
    ``"ARIA<<"`` is ``9``, and ``9`` is what the document prints.  So this is
    the second identity field whose wrong-line read nothing underneath objects
    to, after 2.11's ``"SON"``, and 2.13's caller has to pass the right line
    rather than lean on the check digits.

    Raises:
        MrzValueError: if ``line_2`` is not a string, or if the characters it
            prints at positions 22-27 are not a date of expiry.  The message
            carries the positions, the width and what was expected, and never
            the date.
    """
    return validate_date_of_expiry(td3_field(line_2, TD3_LINE_2, "date_of_expiry"))


def _readable_sexes() -> str:
    """The accepted sex markers, sorted, for a message.

    Sorted so the message is the same string every time, which keeps a log
    greppable, for :func:`_readable_codes`'s reason.  Never used to decide
    anything -- the membership test against :data:`TD3_SEX_MARKERS` is --
    only to say what was expected.
    """
    return ", ".join(repr(marker) for marker in sorted(TD3_SEX_MARKERS))


def validate_sex(marker: str) -> str:
    """Return ``marker`` if it is a TD3 sex marker, else raise.

    The one character at position 21, and the **only** field of line 2 whose
    content rule is a closed list rather than a shape: the value must be one
    of :data:`TD3_SEX_MARKERS` -- ``M``, ``F``, ``X`` or the filler.

    **The set is closed because nothing underneath this field would object to
    a marker that is wrong.**  The composite check digit covers positions 1-10,
    14-20 and 22-43, so it skips 21, which sits in the gap between the date of
    birth's span and the date of expiry's; and no other digit covers it.  A
    digit misread for a letter here, or a letter for a digit, is therefore
    caught by this check and by nothing else in the module.  That is also why
    the four are *named* rather than derived: a rule such as "one uppercase
    letter, or the filler" would accept ``N`` and ``Q``, which no passport may
    print there.

    **The filler is a value in this field and nowhere else in line 2.**  A
    document prints ``<`` to say the sex is unspecified, which is a different
    thing from a misread, so :func:`validate_document_number`'s "empty once
    the filler is removed" rule does not repeat here -- the filler *is* the
    answer.  This is what 2.11 deferred when it declined an emptiness rule for
    the nationality: there is exactly one unspecified sex, and there is no such
    thing as an unknown nationality.  ``X`` is a third thing again -- printed
    where a holder has not stated a sex -- and is accepted on the same closed-set
    ground rather than being given a meaning this module cannot source.

    **The message names the four markers it wanted and not the one it found.**
    The set is the standard's rather than the holder's, so it is safe to print;
    a sex marker is a property of the holder, and 2.10 is where that reasoning
    started and 2.11 carried it across the line.

    Raises:
        MrzValueError: for any other value, including one that is not a string.
            The type guard comes first and is not decoration: the check below
            is a membership test, and ``[] in TD3_SEX_MARKERS`` raises a bare
            ``TypeError`` a caller catching ``MrzValueError`` would never see.
    """
    if not isinstance(marker, str):
        raise MrzValueError(
            f"a TD3 sex marker must be a string, not {type(marker).__name__}"
        )
    if marker in TD3_SEX_MARKERS:
        return marker
    start, end = TD3_LINE_2["sex"]
    raise MrzValueError(
        f"a TD3 sex marker is one of {_readable_sexes()} at position "
        f"{start}-{end}, and those positions printed something else"
    )


def parse_sex(line_2: str) -> str:
    """Return the sex marker printed at position 21 of ``line_2``.

    The same shape as every other reader here: the position comes from
    :data:`TD3_LINE_2` through :func:`td3_field`, so there is no ``line[20]``,
    and the slice is handed straight to :func:`validate_sex`, so the reader and
    the closed set cannot disagree about what a passport may print.

    **Line 1 at position 21 is the ``M`` of ``MARIA``**, which is one of the
    four markers -- so a reader handed the wrong line returns a valid marker
    rather than an error, and nothing below it will ever object.  Of the three
    fields this task adds, the sex marker is the one with no arithmetic behind
    it at all: the dates have a printed digit beside them, and this has
    neither one nor a composite covering it.

    A line longer than the zone is fine: the field is one character at
    position 21, so surplus characters are not part of it.  A line that stops
    before position 21 slices to an empty string, which is not one of the four
    -- the same thing 2.10 relies on for the document number.

    Raises:
        MrzValueError: if ``line_2`` is not a string (reported by
            :func:`td3_field`, so no bare ``TypeError`` escapes), or if the
            character it prints at position 21 is not one of
            :data:`TD3_SEX_MARKERS`.  The message names the position and the
            markers it wanted, and **neither the marker it found nor anything
            else on the line**.
    """
    return validate_sex(td3_field(line_2, TD3_LINE_2, "sex"))

#: The sex markers a TD3 line 2 may print at position 21 (ICAO 9303, Part 4,
#: "TD3 Format").  ``X`` is printed where a holder has not stated a sex, and
#: ``<`` where the field is unspecified -- two different things, and both are
#: values here rather than a misread.  The set is exact and closed for the same
#: reason :data:`TD3_DOCUMENT_CODES` is: an open one would let a caller widen
#: what a passport may print at run time.  And it has to be closed rather than
#: a rule, because nothing underneath this field would object to a marker that
#: is wrong -- see :func:`validate_sex`.  A frozenset, so no caller can widen
#: it at runtime.
TD3_SEX_MARKERS: frozenset[str] = frozenset({"M", "F", "X", FILLER})


@dataclasses.dataclass(frozen=True)
class MrzDocument:
    """One parsed machine-readable zone: every field, and the raw text of each.

    What :func:`parse_td3` returns, and the first thing in this project that
    carries a document rather than an answer about one.  The fields are
    declared in the order the two lines print, so reading the record from top
    to bottom reads the document from top to bottom.

    **Frozen, and that is the point.**  Nothing downstream of a parse has any
    business editing the nationality of the document it is screening, and a
    record that could be edited would let a "cleaned up" field look exactly
    like a read one.  :attr:`sources` is a read-only mapping for the same
    reason: it is the evidence of what the document printed.  A frozen record
    holding a mapping is compared with ``==`` rather than hashed.

    **Every field is exactly as printed, padding and filler included.**  The
    check digit beside a number is computed over the characters the document
    printed, 3.2 verifies the composite, 2.14 states that a mismatch is
    something a verifier reports, and 3.3 reports *which* field failed -- so
    the five digits are carried here as the characters at positions 10, 20,
    28, 43 and 44, never as ``int``.

    :attr:`check_digit_results` is 3.3's half of that: the five verdicts, in
    printed order, each naming the field it belongs to and carrying both
    digits.  It sits immediately after :attr:`composite_check_digit` because
    that is the last position the five cover, so reading the record top to
    bottom still reads the document top to bottom.  **A verdict and a printed
    digit are two different things and the record keeps both**: the attribute
    above is what the document printed and is evidence no caller may edit,
    while the results below are this parse's reading of whether the two agree.
    Collapsing them into one field would mean a parse that repaired a
    document's digit to make its verdict pass, which 2.14's test exists to
    fail.

    :attr:`surname` and :attr:`given_names` are the **only** derived values,
    and they are the name field read all the way through 2.5 to 2.9 --
    extracted, divided at the ``<<``, divided again at the single filler,
    cleaned of filler and whitespace and lower case, and transliterated into
    the MRZ alphabet.  Nothing else is cleaned, and in particular the dates
    are not: ``YYMMDD`` is six characters and what they may print is 3.11's
    question, so upper-casing one here would answer a question nobody asked.
    :attr:`name` keeps the field as printed, so every cleaning step stays
    reproducible from this record alone.

    :attr:`given_names` is a ``tuple`` rather than the ``list``
    :func:`split_given_names` returns, because a frozen record holding a list
    is not frozen in the part that matters.

    **3.14 makes this the common currency of all three formats, and the
    discriminator is :attr:`format`.**  ``"TD3"`` is what
    :func:`parse_td3` puts there and the field's default, so a record
    constructed by hand claims a passport unless it says otherwise; the three
    parsers all pass it explicitly, so no record this project builds takes
    the default.

    **A field a format does not print is ``None``, and never an empty string.**
    Seven attributes are the three layouts' format-specific fields -- a TD3's
    personal number and its digit, a TD1's optional data 1 and its digit, a
    TD1's optional data 2, and a TD2's optional data and its digit -- and each
    is ``None`` on a record for a format that prints no such field.  The empty
    string would be a lie twice over: it is a width no field in any layout
    has, and it is the value
    :func:`~app.pipeline.tier0.mrz.parse_date` already answers for six
    characters it could not read, so one value would mean two different
    things depending on which field it was read from.  The personal number
    pair keeps its place in TD3's printed order, because a TD3 prints it and
    a reader scanning down the record should meet it where the passport
    prints it; the five optional-data attributes sit at the end of the
    declaration instead, because no single printed order contains a TD1's
    optional data 1, its optional data 2 and a TD2's optional data, and
    putting them among the common fields would have meant choosing one
    format's document as the order all three are read in.

    **``name``, :attr:`surname` and :attr:`given_names` are ``None`` on a TD1,
    and that is a gap rather than a decision.**  A TD1 prints the holder's
    name on line 3, which is 3.7's last field to be laid out and still has no
    reader; the name is carried raw in :attr:`sources` under its own layout
    name, so nothing is lost, but the three derived attributes are ``None``
    until a later task reads line 3.

    **The record carries no reference date and no inferred year, and that is a
    decision rather than an omission.**  Three shapes were available: two
    nullable year fields beside the printed ones, a ``reference`` with the
    years as properties, or the years left to a caller.  The first would put
    two readings of one field on one record -- ``"740812"`` and ``1974`` --
    and a year is ``int | None`` against a reference the record would not
    carry, so the reading would be frozen without the thing that makes it
    true.  The second is the only design that could put ``datetime.now()``
    back at the edge of the package, which ``tasks.md`` bans inside check
    logic and which 3.12 and 3.13 pinned out of :mod:`mrz` by AST walk.  So a
    caller holding this record and a reference date asks
    :func:`~app.pipeline.tier0.mrz.infer_birth_year` or
    :func:`~app.pipeline.tier0.mrz.infer_expiry_year` about
    :attr:`date_of_birth` or :attr:`date_of_expiry` directly -- the printed
    field *is* the argument, and no plumbing is needed to get it there.
    """

    document_code: str
    issuing_state: str
    name: str
    document_number: str
    document_number_check_digit: str
    nationality: str
    date_of_birth: str
    date_of_birth_check_digit: str
    sex: str
    date_of_expiry: str
    date_of_expiry_check_digit: str
    personal_number: str | None
    personal_number_check_digit: str | None
    composite_check_digit: str
    check_digit_results: tuple[CheckDigitResult, ...]
    surname: str
    given_names: tuple[str, ...]
    sources: Mapping[str, str]
    optional_data_1: str | None = None
    optional_data_1_check_digit: str | None = None
    optional_data_2: str | None = None
    optional_data: str | None = None
    optional_data_check_digit: str | None = None
    format: str = "TD3"


def _td3_sources(zone: tuple[str, str]) -> Mapping[str, str]:
    """Return every field's raw characters, in printed order, as printed.

    The raw half of :class:`MrzDocument`, read by position out of
    :data:`TD3` through :func:`td3_field` rather than copied out of a parsed
    value -- so a record's evidence cannot be whatever a reader did to the
    text.  For all fourteen fields the two are the same string today, and that
    is worth asserting rather than assuming: it is the test that no field
    reader edits what it reads.

    Concatenating the slices in printed order rebuilds both lines exactly,
    because 2.1's coverage test gives every position to exactly one field, so
    the map is a complete record of the zone and not only of the parts of it
    someone thought to keep.

    ``sorted(TD3)`` puts the two line names in printed order, which is the
    order :func:`validate_td3_lines` returned the lines in, so pairing them
    here states no line name of its own.
    """
    sources: dict[str, str] = {}
    for line_name, line in zip(sorted(TD3), zone):
        layout = TD3[line_name]
        for name in sorted(layout, key=layout.__getitem__):
            sources[name] = td3_field(line, layout, name)
    return MappingProxyType(sources)


def parse_td3(lines: Iterable[str]) -> MrzDocument:
    """Return the whole TD3 zone at ``lines`` as a :class:`MrzDocument`.

    The assembly, and nothing else.  Every field reader from 2.3 to 2.12 is
    called with the line the layout names for it, in printed order, so the
    record cannot disagree with the readers about where a field sits or what it
    may print; this function slices no line for itself, and
    :func:`_td3_sources` -- which builds the raw map -- goes through
    :func:`td3_field` like everything else does.

    **The two lines come from :func:`validate_td3_lines` in printed order,
    and that is the only thing keeping them apart.**  2.11 and 2.12 recorded
    that line 1 answers ``"SON"`` for the nationality, ``"<<ANNA"`` for the
    date of birth, ``"M"`` for the sex marker and ``"ARIA<<"`` for the date of
    expiry -- all four pass their own validators, and the arithmetic does not
    object either, since ``"ARIA<<"`` comes to the ``9`` the specimen prints
    at position 28.  An assembler cannot validate its way out of a swap here;
    it has to hand each reader the right line.  A caller who passes the lines
    the other way round *is* caught, and only because the document code is the
    first field read: line 2's positions 1-2 are ``"L8"``, which is not a
    passport.

    **Six fields are read with no reader of their own, and are judged by
    nothing.**  They are the five printed check digits and the personal
    number, for which no task in Part 2 asks for a ``parse_*``: the digits
    because verifying one is 2.14's and 3.2's question, and the personal
    number because a passport may print anything at all there.  Each is taken
    out of the raw map rather than sliced a second time, so a field's value
    and its source slice are the one string that :func:`_td3_sources` read
    once and not two copies of it that could drift apart.  Either way it is
    handed to the record as printed, so a personal number of nothing but
    filler -- or one carrying a space the MRZ alphabet cannot print -- comes
    back exactly as the document printed it, which is 2.10's and 2.4's rule
    rather than an omission here.

    **3.3 adds a verdict to the record, and the digits stay printed.**  After
    the name assembly, :func:`td3_check_digit_results` is asked for the five
    comparisons and the answers go to :attr:`MrzDocument.check_digit_results`
    while :attr:`MrzDocument.composite_check_digit` and its four siblings stay
    the characters the line printed.  A mismatch is a result, so 2.14's mutant
    still produces a full record and a field that failed is a row in the list
    rather than an exception; the two attributes can never be the same fact
    reported twice.

    **Nothing the digits find can add an error to this function, and that is
    2.4's and 2.10's rule seen from the other side.**  A field whose characters
    are not MRZ at all, or whose printed "digit" is not a digit, is reported by
    :attr:`CheckDigitResult.passed` being ``None`` rather than by
    :func:`~app.pipeline.tier0.mrz.check_digit_results` raising -- one
    mis-OCR'd character among five is the normal condition of an OCR'd line,
    and a list that refused to be built would take the other four verdicts and
    the whole record down with it.  That also means reading the digits first
    does not change which fault a caller is told about, so a zone with both a
    malformed field and an unreadable digit is still refused by the reader that
    found the field.

    **The name field is read all the way through**, by :func:`parse_name`,
    :func:`split_name`, :func:`split_given_names`,
    :func:`normalise_names` and :func:`transliterate_names` in that order, and
    :attr:`MrzDocument.name` keeps the field as printed alongside the two
    derived halves.

    Raises:
        MrzValueError: for anything this zone can be wrong about -- a shape
            that is not two lines of :data:`TD3_LINE_LENGTH` characters, then
            whichever field reader refuses first, in printed order.  The error
            is the reader's own, unwrapped and unedited, so its message names
            the field and the width it wanted and never the identity data
            around it; this function has no message of its own, because the
            only new thing it could say is which document failed.  The five
            check digits cannot contribute one: a mismatch and an unreadable
            field are both rows in
            :attr:`MrzDocument.check_digit_results`.
    """
    line_1, line_2 = validate_td3_lines(lines)
    sources = _td3_sources((line_1, line_2))
    name = parse_name(line_1)
    surname, given_names = split_name(name)
    surname, given_names = normalise_names(surname, split_given_names(given_names))
    surname, given_names = transliterate_names(surname, given_names)
    check_digits = td3_check_digit_results(line_2, sources)
    return MrzDocument(
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
        personal_number=sources["personal_number"],
        personal_number_check_digit=sources["personal_number_check_digit"],
        composite_check_digit=sources["composite_check_digit"],
        check_digit_results=check_digits,
        surname=surname,
        given_names=tuple(given_names),
        sources=sources,
        format="TD3",
    )


#: The fields of :data:`TD3_LINE_2` the composite digit is computed over, in
#: printed order: positions 1-10, 14-20 and 22-43.  A tuple of *names* rather
#: than three spans, because the spans are already in :data:`TD3_LINE_2` -- the
#: eight fields below *are* those three ranges and nothing else, and that is a
#: test's claim to check rather than this comment's to make.  The three fields
#: left out are the nationality (11-13), the sex marker (21) and the composite
#: digit itself (44), the first two of which are the identity fields 2.11 and
#: 2.12 recorded as having no arithmetic under them.
TD3_COMPOSITE_FIELDS: tuple[str, ...] = (
    "document_number",
    "document_number_check_digit",
    "date_of_birth",
    "date_of_birth_check_digit",
    "date_of_expiry",
    "date_of_expiry_check_digit",
    "personal_number",
    "personal_number_check_digit",
)


def td3_composite_input(line_2: str) -> str:
    """Return the 39 characters ``line_2``'s composite digit is computed over.

    The assembly, and nothing beyond it.  Whether those characters agree with
    the digit printed at position 44 is 3.2's question and which field is at
    fault is 3.3's, so this concatenates and stops: the module still computes
    no digit and reports no verdict, and
    :func:`~app.pipeline.tier0.mrz.check_digit` remains the only place in the
    package where a digit comes out.  This is the same line
    :class:`MrzDocument` draws when it carries the five printed digits as the
    characters the document printed rather than as ``int``s.

    **The three spans are reached by field name, not restated as positions.**
    The concatenation is over :data:`TD3_COMPOSITE_FIELDS`, and every read
    goes through :func:`td3_field`, so "1-10, 14-20 and 22-43" is a
    consequence of :data:`TD3_LINE_2` rather than a second copy of it: a
    field that moved in the layout moves here too, and nothing in this
    function can disagree with the table.  A hand-written ``line[28:42]``
    would produce the right answer for one specimen and no other, and the
    read-count test is what says so.

    **Nothing is judged on the way through, and the width is not checked.**
    :func:`validate_td3_lines` is the one place a TD3 line's shape is decided,
    and every field reader from 2.3 onwards takes a line that has passed it
    and judges only its own field.  The composite is eight fields wide, so a
    check here would be a second shape gate and a second message; instead a
    caller who skipped the gate gets a composite input of the wrong length and
    no error, which is the price of the one gate.  3.2 therefore reads a line
    that came out of :func:`validate_td3_lines`.

    **Nothing is repaired, and the printed digits are inside the span rather
    than beside it.**  Positions 10, 20, 28 and 43 are the check digits the
    line printed, and they are part of what this returns, so a document number
    that no longer agrees with its own digit reaches the verifier as both the
    mutation and the digit that contradicts it -- 2.14's second witness, and
    the reason this function is a concatenation rather than a cleverer thing.

    Raises:
        MrzValueError: if ``line_2`` is not a string, and then only because
            :func:`td3_field` raises it on the first read.  The error is
            :func:`td3_field`'s own, unwrapped and unedited, so this function
            defines no error type and adds no message; 1.9's single-``except``
            rule still holds.
    """
    return "".join(
        td3_field(line_2, TD3_LINE_2, name) for name in TD3_COMPOSITE_FIELDS
    )


#: The five printed check digits of a TD3, each paired with the characters it
#: is computed over.  Triples of ``(label, field the characters come from,
#: field the printed digit comes from)``, in printed order -- position 10, then
#: 20, 28, 43 and 44.
#:
#: **The first element is the name a verdict is reported under, and it is the
#: field's own name for four of the five and ``"composite"`` for the fifth.**
#: The odd one out is the composite, because its characters are not printed
#: anywhere in the zone: they are the eight fields of
#: :data:`TD3_COMPOSITE_FIELDS` read out and joined, which is why its second
#: element is ``None`` rather than a name that would lie about where they came
#: from.  Everything else is a pair of real fields in
#: :data:`_td3_sources`, and a pairing that named a field the layout does not
#: have raises rather than reporting a field nobody printed.
#:
#: A list of pairs rather than two parallel lists because a pairing is the
#: whole content: which digit checks which field is a fact about the standard
#: and not something a caller should be able to transpose.  It is stated here
#: rather than derived from the layout because the layout cannot say it --
#: position 10 is adjacent to the document number and also the first character
#: of the first composite span, and only the standard says which field the
#: digit belongs to.
TD3_CHECK_DIGIT_FIELDS: tuple[tuple[str, str | None, str], ...] = (
    ("document_number", "document_number", "document_number_check_digit"),
    ("date_of_birth", "date_of_birth", "date_of_birth_check_digit"),
    ("date_of_expiry", "date_of_expiry", "date_of_expiry_check_digit"),
    ("personal_number", "personal_number", "personal_number_check_digit"),
    ("composite", None, "composite_check_digit"),
)


def td3_check_digit_results(
    line_2: str, sources: Mapping[str, str]
) -> tuple[CheckDigitResult, ...]:
    """Return the five :class:`~app.pipeline.tier0.mrz.CheckDigitResult`
    records of ``line_2``, in printed order.

    The composition, and the first call in this module into
    :mod:`app.pipeline.tier0.mrz` for anything other than an error type and the
    filler.  It pairs the five entries of :data:`TD3_CHECK_DIGIT_FIELDS` with
    the characters they are computed over and the digits they are compared
    against, and hands the lot to
    :func:`~app.pipeline.tier0.mrz.check_digit_results`, which is where the
    arithmetic lives.

    **Where a pair's characters come from is the layout's business and is
    read, not restated.**  The four field pairs are looked up in ``sources`` --
    the same map :attr:`MrzDocument.sources` holds, so a verdict is computed
    over exactly the characters the record is evidence of -- and the composite
    is :func:`td3_composite_input`, so there is one assembler rather than a
    second copy of the eight-field join that could drift from it.  The printed
    digits are read from ``sources`` too, never re-sliced from ``line_2``: a
    second read of position 44 would be a second opinion about where it is.

    ``sources`` is passed rather than rebuilt so the record's evidence and its
    verdicts are one read, and so a caller holding a line can verify it without
    assembling a map to hand over.  :func:`parse_td3` is the caller that
    matters, and it passes the map it just built.

    **This is where 3.2's verification moved to, and the two halves of it are
    still independent.**  3.2 compared :func:`td3_composite_input` against a
    longhand table of what the standard prints, so the layout and the fixture
    could not agree by agreeing with themselves.  That is a property of the
    *test*, and it is not repeated here: in production the printed digit comes
    from the same line as the characters, and the only claim this function
    makes is that the two agree.  What the specimen actually carries is 1.6's
    open question and is unaffected by where the comparison is written.

    **A field that cannot be read comes back as a row whose ``passed`` is
    ``None``, not as an exception.**  3.2's
    :func:`composite_agrees` raised for a non-digit at position 44, and that
    is right for one isolated field; over five of them it is not, because the
    composite spans 22 positions of which a single space is enough to make the
    whole thing uncomputable.  So the record loses nothing an officer needs --
    the field is named, the printed digit beside it is still reported, and the
    other four verdicts are unaffected -- where raising would have lost the
    document.

    Raises:
        ``KeyError``, and only :class:`KeyError`, if ``sources`` does not hold
            a field this pairing names.  It is deliberately not translated into
            :class:`MrzValueError`: ``sources`` is this package's own map built
            from :data:`TD3_LINE_2`, every pairing names a field of that
            layout, and a missing key is a bug in the caller rather than a
            document that is wrong -- so translating it would dress a
            programmer error up as a fact about a passport.  A document that
            is wrong raises nothing here at all; that is the row above.
    """
    composite = td3_composite_input(line_2)
    return check_digit_results(
        (
            (
                label,
                composite if field is None else sources[field],
                sources[digit_field],
            )
            for label, field, digit_field in TD3_CHECK_DIGIT_FIELDS
        )
    )
