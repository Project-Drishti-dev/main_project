"""ICAO 9303 machine-readable-zone (MRZ) primitives.

Pure arithmetic on characters: no OpenCV, no model, no numpy. Everything in
Part 1 of ``tasks.md`` builds on this module.

The MRZ character value table (ICAO 9303, Part 4, "Character Mapping") is
defined as:

* ``0``-``9`` map to ``0``-``9``
* ``A``-``Z`` map to ``10``-``35``
* ``<`` (filler) maps to ``0``
* any other character is a hard error

Any other character raises :class:`MrzValueError`, the single error type this
module raises, which subclasses ``ValueError`` so existing ``except
ValueError`` handling keeps working.  Every failure is reported as this one
type whatever its cause -- a character outside the table, a field of the
wrong type, an impossible length, a claimed check digit that is not a digit
-- so a caller writes one ``except MrzValueError`` and has seen them all.

The check-digit weight cycle (ICAO 9303, Part 4, "Check Digit") is ``7, 3, 1``,
repeated from the start of a field and truncated to that field's length.
:func:`weights` returns that prefix, and :func:`check_digit` applies it:
``sum(char_value * weight) % 10``.  :func:`verify_check_digit` compares a
field's digit against the one printed in the MRZ and answers with a bool,
because a mismatch is a finding to report rather than an error to raise.

:func:`check_digit_results` is that comparison kept rather than spent: it
answers a whole document's worth of fields at once, in the order the caller
lists them, as a tuple of :class:`CheckDigitResult` records carrying the
field's name and both halves of the arithmetic.  It is what a document record
hands a rules engine, so that a caller can ask *which* field disagreed without
recomputing any of them, and the layout module stays free of arithmetic.

A date is the other thing every format here prints the same way, and
:func:`parse_date` reads it: six characters as ``YYMMDD``, returned as a frozen
:class:`MrzDate` of three numbers, or ``None`` when the six characters are not
all digits.  **It judges no range** -- :func:`date_fault` names the component
that cannot be a day (``"month"`` or ``"day"``), so the three format modules
can put their own positions in the message without each of them keeping its
own copy of the rule.  **The reading implies no century, and a separate function
answers for one.**  :class:`MrzDate` carries the two printed digits and nothing
else, because what century they belong to is not a property of the six
characters: it is a property of *when* the document is read, and of *which* of
the two dates a document prints the field is.  So there are two functions that
add one, and **they are deliberately not one function with a flag**: a birth is
read backwards from the reference and an expiry forwards, so the two disagree
about which side of the reference a candidate must be on *and* about whether a
candidate too far away may be admitted -- only a birth needs a figure for that
(a fact about people, :data:`MAX_BIRTH_AGE`), because two digits repeating
every hundred years is already the bound on an expiry.  A single function would
have to take a direction *and* a band that the expiry half would never use.  So
:func:`infer_birth_year` and :func:`infer_expiry_year` are separate, each named
for the one date it answers for, and each takes the reference date as an
argument rather than reading the clock.
"""

import calendar
import dataclasses
import datetime
import string
from collections.abc import Iterable

__all__ = [
    "CHAR_VALUES",
    "MAX_BIRTH_AGE",
    "CheckDigitResult",
    "MrzDate",
    "MrzValueError",
    "char_value",
    "check_digit",
    "check_digit_results",
    "date_fault",
    "infer_birth_year",
    "infer_expiry_year",
    "parse_date",
    "verify_check_digit",
    "weights",
]

#: The MRZ filler character (ICAO 9303, Part 4).
FILLER = "<"

#: The check-digit weight cycle (ICAO 9303, Part 4, "Check Digit"): ``7`` for
#: the first character of a field, ``3`` for the second, ``1`` for the third,
#: then over again.  Use :func:`weights` to get the first ``n`` of them.
WEIGHT_CYCLE = (7, 3, 1)

#: The width of a date in every format this package reads, in characters: two
#: of year, two of month, two of day.  The three layout modules read their own
#: width out of their own tables and never import this; it is here so that a
#: caller holding six characters has one number to ask about.
DATE_LENGTH = 6

#: The most days each month of the Gregorian calendar can have, January first.
#:
#: **February is 29 and not 28, which is the one judgement in this tuple and it
#: is written down here rather than left for a reader to assume.**  A date
#: carries two digits of year and no century, so whether *this* February had a
#: 29th is not answerable from what a line printed -- it needs the century the
#: line does not carry.  The reading that refuses nothing genuine is the most a
#: month can be in *any* year, so February's entry is 29: "``020229``" is
#: accepted and "``020230``" is not.  Flattening every month to 31 would accept
#: more nonsense and refuse nothing.  The leap-year question itself is
#: :func:`infer_birth_year`'s, and it is answerable there precisely *because*
#: this reading refused to invent a century: once the century is known, a 29th
#: of February either is a day in that year or is not, and no tuple of maxima
#: has to guess which.
MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

#: The oldest age, in years, that :func:`infer_birth_year` will read a date of
#: birth as implying.  **A date of birth is a person's, and nobody this
#: package can picture is 121**, so a two-digit year whose only century left to
#: try is further back than this gets no century at all: the answer is
#: ``None``, the same third answer an unreadable date gets, because "this
#: document does not tell us" is the honest report either way.
#:
#: **The figure is a decision rather than a fact about documents** -- the
#: oldest verified human age is well past it -- and it is a named constant
#: rather than a literal so that a later task disagreeing with it has one place
#: to disagree in, and because :func:`infer_expiry_year` has no counterpart to
#: it at all: an expiry is bounded by the century repeating underneath it, not
#: by a figure anybody had to invent.
MAX_BIRTH_AGE = 120


class MrzValueError(ValueError):
    """Raised when a character, field, or line is not valid ICAO 9303 MRZ.

    The single error type the whole MRZ package raises.  It subclasses
    ``ValueError`` so callers that already catch ``ValueError`` around
    ``char_value`` (or anything built on it) keep working unchanged.
    """


def _build_char_values() -> dict[str, int]:
    """Build the character value table from the three MRZ character classes."""
    table: dict[str, int] = {}
    for value, char in enumerate(string.digits):
        table[char] = value
    for value, char in enumerate(string.ascii_uppercase, start=10):
        table[char] = value
    table[FILLER] = 0
    return table


#: MRZ character value table.  ``CHAR_VALUES["A"] == 10``, ``CHAR_VALUES["Z"] == 35``,
#: ``CHAR_VALUES["<"] == 0``.
CHAR_VALUES: dict[str, int] = _build_char_values()


def char_value(c: str) -> int:
    """Return the ICAO 9303 numeric value of the MRZ character ``c``.

    ``0``-``9`` return ``0``-``9``, ``A``-``Z`` return ``10``-``35``, and the
    filler ``<`` returns ``0`` (it is numeric, not alphabetic).

    Raises:
        MrzValueError: if ``c`` is not one of those 37 characters.  A
            ``MrzValueError`` is a ``ValueError``, so ``except ValueError``
            still catches it.
    """
    try:
        return CHAR_VALUES[c]
    except (KeyError, TypeError):
        raise MrzValueError(
            f"not an MRZ character: {c!r} "
            "(expected 0-9, A-Z, or '<' filler)"
        ) from None


def weights(n: int) -> list[int]:
    """Return ``n`` weights: the ``7, 3, 1`` cycle repeated, then truncated.

    ``weights(0)`` is ``[]`` and ``weights(4)`` is ``[7, 3, 1, 7]``.  A partial
    cycle is cut off rather than padded or scaled, so the result always holds
    exactly ``n`` items and every item is a whole weight from the cycle.

    Raises:
        MrzValueError: if ``n`` is not an ``int``, or if it is negative.  A
            field cannot have a non-integer or negative length, and quietly
            returning ``[]`` would hide that mistake from the caller instead
            of failing at the arithmetic.  The type is checked before the
            comparison because ``n < 0`` on a ``str`` or ``None`` would raise
            a bare ``TypeError``, and this package raises one error type.
    """
    if not isinstance(n, int):
        raise MrzValueError(f"weight count must be an integer: {n!r}")
    if n < 0:
        raise MrzValueError(f"weight count must not be negative: {n!r}")
    return [WEIGHT_CYCLE[i % len(WEIGHT_CYCLE)] for i in range(n)]


def check_digit(text: str) -> int:
    """Return the ICAO 9303 check digit for the MRZ field ``text``.

    ``sum(char_value * weight) % 10``, where the weights come from
    :func:`weights` and therefore restart at the first character of *this*
    field -- a check digit is always computed over one field, never over a
    whole line.

    The values come from :func:`char_value`, so the field is validated as it
    is summed: a single character outside the table fails the whole check
    rather than being skipped and quietly changing the digit.

    Raises:
        MrzValueError: if ``text`` is not a sequence of characters, or if any
            character in it is not one of the 37 MRZ characters (delegated to
            :func:`char_value`, so the message names the offending character).
    """
    try:
        field_weights = weights(len(text))
    except TypeError:
        raise MrzValueError(
            f"check-digit field must be a sequence of characters: {text!r}"
        ) from None
    return sum(char_value(char) * weight for char, weight in zip(text, field_weights)) % 10


def _expected_digit(expected: int | str) -> int:
    """Normalise the check digit a caller claims, to an ``int`` in ``0``-``9``."""
    # A parser has the printed check digit as a single character of the line,
    # and the flag schema wants it as an int, so both spellings are accepted --
    # but only a decimal digit.  bool and float are excluded on purpose: both
    # compare equal to 2, so letting them through would hide a bug in the
    # caller that parsed the digit rather than naming it here.
    if isinstance(expected, int) and not isinstance(expected, bool) and 0 <= expected <= 9:
        return expected
    # The length test is not redundant: "" is a substring of every string, so
    # the membership test alone would let an empty claim through to int("").
    if isinstance(expected, str) and len(expected) == 1 and expected in string.digits:
        return int(expected)
    raise MrzValueError(f"expected check digit must be a digit 0-9: {expected!r}")


def verify_check_digit(text: str, expected: int | str) -> bool:
    """Return whether ``text``'s check digit matches the one claimed for it.

    ``expected`` is the digit the MRZ claims, as an ``int`` ``0``-``9`` (the
    shape the flag schema uses: ``expected 4, found 7``) or as the single
    character printed in the line, which is what a parser has to hand.

    A mismatch is a *result*, not an error, so this answers ``True`` or
    ``False`` for every field it can read and never raises to report a failed
    check.  The found digit is not lost: it is still
    :func:`check_digit`'s return value, which is what a flag needs to carry
    both halves.

    Raises:
        MrzValueError: if ``expected`` is not a digit, or if ``text`` cannot be
            read as an MRZ field (delegated to :func:`check_digit`).  An
            unreadable field raises on purpose rather than answering ``False``:
            a field nobody could read is not evidence of tampering, and a
            ``False`` here would put a forged-document claim in front of an
            officer for a mis-OCR'd or truncated line.
    """
    return check_digit(text) == _expected_digit(expected)


@dataclasses.dataclass(frozen=True)
class CheckDigitResult:
    """One field's check-digit verdict, or the fact that it could not be made.

    The record :func:`verify_check_digit` returns as a bare ``bool``, kept as
    the thing a flag needs instead: a finding carries ``expected`` and
    ``found`` as well as whether they agree, and a rules engine that is handed
    only the ``bool`` has to run the arithmetic a second time to fill the other
    two in.  Here they are already done.

    **The field is named, and that is what makes a list of these worth
    having.**  Five verdicts with no field attached cannot answer "which field
    failed", and that question is the one a screening asks.

    **Either digit may be ``None``, and :attr:`passed` is then ``None`` rather
    than ``False`` -- a third answer, not a softened second one.**  ``found``
    is ``None`` when the field's characters are not MRZ at all, and
    ``expected`` is ``None`` when what the line printed is not a digit.  The
    other digit is still reported, because a flag still wants it:
    ``expected 2, found unreadable`` says more than a refusal.  A ``False``
    here would be 2.14's mistake repeated at the wrong level -- a mis-OCR'd
    character is not evidence of a forged digit, and calling it a failure
    would put a tampering claim in front of an officer that the document did
    not earn.  So a caller asking "did this document pass" gets three answers
    and has to handle the third, which is the point.

    :attr:`passed` and :attr:`readable` are properties rather than stored
    fields, so neither can be held disagreeing with the two digits it is
    derived from.

    **Frozen, hashable, and holding no identity data.**  The characters the
    digit was computed over are not kept: they are already in the record that
    was parsed, and a result that travelled on its own would be one more place
    a passport number sat.  ``field`` is a field *name* -- ``"date_of_birth"``
    -- and never a value, for the same reason the error messages in
    :mod:`app.pipeline.tier0.td3` name the field they rejected and not what it
    printed.
    """

    field: str
    expected: int | None
    found: int | None

    @property
    def readable(self) -> bool:
        """Whether both halves of the comparison were available."""
        return self.expected is not None and self.found is not None

    @property
    def passed(self) -> bool | None:
        """``True`` or ``False``, or ``None`` when the field could not be read.

        The three-way answer is deliberate and 2.14's rule rather than a
        convenience: a field nobody could read is not a field that failed.
        """
        if not self.readable:
            return None
        return self.expected == self.found


def _named_check_digit_field(
    entry: tuple[str, str, int | str],
) -> tuple[str, str, int | str]:
    """Return ``entry`` as a ``(name, text, printed digit)`` triple, or raise.

    :func:`check_digit_results` takes a list of these, and a caller who builds
    one from a layout table will eventually pass a pair rather than a triple or
    name a field with a position.  Unpacking that raises a bare ``TypeError``
    or ``ValueError``, and 1.9's rule is that this package raises one error
    type, so it is caught here and re-raised as a :class:`MrzValueError`.

    **The message carries no part of the entry.**  The second element is the
    document's own characters, and an exception message is the most likely
    thing in this project to reach a log, so the shape is described and the
    value is not echoed -- the same rule 2.10 and 2.13 set for the field
    readers.  The *name* may be, because a name is a field this code invented
    rather than a thing the document printed.

    Raises:
        MrzValueError: if ``entry`` is not a three-element sequence, or if its
            first element is not a string.
    """
    try:
        name, text, printed = entry
    except (TypeError, ValueError):
        raise MrzValueError(
            "each check-digit field must be a (name, text, printed digit) triple"
        ) from None
    if not isinstance(name, str):
        raise MrzValueError(f"check-digit field name must be a string: {name!r}")
    return name, text, printed


def _checked_digit_result(
    field: str, text: str, printed: int | str
) -> CheckDigitResult:
    """Return the verdict for one field, recording what could not be read.

    The two halves are attempted independently and either may come back
    ``None``, so a field whose characters are unreadable still reports the
    digit the document printed beside them and a field whose printed digit is
    not a digit still reports the one its characters come to.

    **The refusals of :func:`check_digit` and :func:`_expected_digit` are
    caught here and nowhere else.**  :func:`verify_check_digit` lets both
    through, and this is the one place in the package that does not: a list
    reports an unreadable field rather than refusing to be built, and the
    result is where the refusal went.  Nothing is discarded -- the character
    that could not be read is still named in the error that was caught, it
    simply does not become a verdict, and the caller is told which field it
    belongs to.
    """
    try:
        found = check_digit(text)
    except MrzValueError:
        found = None
    try:
        expected = _expected_digit(printed)
    except MrzValueError:
        expected = None
    return CheckDigitResult(field, expected, found)


def check_digit_results(
    fields: Iterable[tuple[str, str, int | str]],
) -> tuple[CheckDigitResult, ...]:
    """Return one :class:`CheckDigitResult` per field, in the order given.

    ``fields`` is an iterable of ``(name, text, printed digit)`` triples, where
    ``printed digit`` is the claim to test -- an ``int`` ``0``-``9`` or the
    single character a parser read out of the line, exactly as
    :func:`verify_check_digit` takes it.  The caller owns the pairing: this
    function knows how to compare one field with one claim and has no opinion
    about which fields a document format prints or in what order.

    **This is :func:`verify_check_digit` over a list rather than a new
    comparison.**  Each entry is answered by :func:`check_digit` against
    :func:`_expected_digit`, so a field that passes here passes there, and the
    two cannot drift.  The difference is only that the answer is kept: the
    ``found`` digit :func:`verify_check_digit` computes and throws away is
    exactly the half a finding has to carry, so computing the list once serves
    both the verdict and the evidence.

    **A field that cannot be read is reported as not checked rather than
    refused, and this is the one place this function parts company with
    :func:`verify_check_digit`.**  That function raises for an unreadable
    field, and rightly: a caller who has already isolated one suspect field
    should hear about it rather than get a ``False``.  A *list* cannot do
    that, because one garbled character among five is the normal condition of
    an OCR'd line rather than an event, and a list that raised would take the
    other four verdicts down with it.  So the unreadable half becomes ``None``
    in the result and :attr:`CheckDigitResult.passed` is ``None`` -- 2.14's
    principle, kept, rather than dropped because it was inconvenient here.

    **What still raises is a mistake in the call, not a fact about the
    document.**  An entry that is not a triple, or a field named with
    something other than a string, is a caller who built the list wrong and
    would otherwise get a silently shorter answer; ``fields`` not being
    iterable at all is the same.  Those are :class:`MrzValueError` like
    everything else this package raises, and their messages carry no part of
    the entry.

    Returns:
        A ``tuple``, never a ``list``: a frozen record holding a list is not
        frozen in the part that matters, which is the rule
        :class:`~app.pipeline.tier0.td3.MrzDocument` follows for the same
        reason.  Empty for empty input, because a format that prints no check
        digits is not an error here -- it is a format with none.  Exactly one
        result per entry, always, and in the order given: a caller that asked
        about five fields gets five rows back whatever became of them.

    Raises:
        MrzValueError: if ``fields`` is not iterable, if an entry is not a
            three-element sequence, or if an entry names its field with
            something other than a string (all from
            :func:`_named_check_digit_field`).  **Not** for a field that
            cannot be read or a printed digit that is not one -- see above.
    """
    try:
        entries = list(fields)
    except TypeError:
        raise MrzValueError(
            f"check-digit fields must be a sequence of triples: {fields!r}"
        ) from None
    return tuple(
        _checked_digit_result(*_named_check_digit_field(entry)) for entry in entries
    )


# --- dates: the one field every format prints the same way ----------------


@dataclasses.dataclass(frozen=True)
class MrzDate:
    """The three numbers a ``YYMMDD`` date prints, and nothing else.

    **Two digits of year are two digits of year, not a year.**  :attr:`year`
    is what the two characters said, as an ``int`` in ``0``-``99``, so
    ``MrzDate(0, 1, 1)`` is the first of January printed by a document whose
    century nobody has read yet.  Turning "``00``" into "``1900``" or "``2000``"
    is a separate question with two different answers for the two dates a
    document prints, and a record that had already made the guess could not be
    asked it.  :func:`infer_birth_year` is where that question is asked, and
    its answer comes back as a plain ``int`` beside the record rather than
    inside it -- which is what lets the same six characters be read twice, once
    per date, from one record.

    Frozen and hashable, like :class:`CheckDigitResult` and for the same
    reason.  **Unlike it, this record is identity data**: three numbers that
    may be a holder's date of birth, which is why it is built from a field a
    caller already holds rather than carried inside an exception message --
    :class:`CheckDigitResult` deliberately keeps the characters it was
    computed over out of itself, and every reader in the three format modules
    names the *component* of a date it refused rather than the date.

    ``str()`` renders the six characters back, zero-padded, and round-trips:
    the record holds the same digits the line printed, so nothing here tidies,
    re-cases or re-orders anything.
    """

    year: int
    month: int
    day: int

    def __str__(self) -> str:
        """The six characters the record was read from."""
        return f"{self.year:02d}{self.month:02d}{self.day:02d}"


def parse_date(text: str) -> MrzDate | None:
    """Return the date ``text`` prints, or ``None`` if it does not print one.

    ``text`` is :data:`DATE_LENGTH` characters exactly as they stand in the
    line: two of year, then two of month, then two of day.  ``YYMMDD`` is the
    shape every format in this package prints a date in, which is why the
    reading lives here rather than in any one of the three layout modules.

    **``None`` is the answer for six characters that are not all digits, and
    it is the whole of this function's judgement.**  A filler, a letter, a
    space, a diacritic and a non-ASCII digit are all ``None``, because a
    character the standard does not print in this field is a *misread*, and
    the check digit printed beside the date is what reports a misread --
    :func:`check_digit` raises on the ones outside the MRZ alphabet and
    :func:`check_digit_results` reports the row as unreadable rather than as
    failed.  Refusing here instead would throw that finding away and report an
    ordinary OCR slip as a document that could not be read, which is the
    mistake 2.14's third answer exists to prevent.

    **No range is judged here.**  Whether month 31 or day 32 is a day is
    :func:`date_fault`'s question, and keeping the two apart is what lets a
    caller answer "this line could not be read" differently from "this line
    carries a month no calendar has".

    **No century is invented, and none is implied by :attr:`MrzDate.year`.**
    What century two digits imply is a question with a different answer for a
    date of birth and for an expiry, so this stops at the two characters and
    :func:`infer_birth_year` is asked separately.

    Raises:
        MrzValueError: if ``text`` is not a string, or is not exactly
            :data:`DATE_LENGTH` characters wide.  **Both are a caller's
            mistake rather than a fact about a document**: the three format
            validators measure the field against their own layout table before
            they delegate here, so neither can reach this function from a line
            that stopped early.
    """
    if not isinstance(text, str):
        raise MrzValueError(
            f"a date must be a string, not {type(text).__name__}"
        )
    if len(text) != DATE_LENGTH:
        raise MrzValueError(
            f"a date is {DATE_LENGTH} characters (YYMMDD), not {len(text)}"
        )
    # `str.isdigit()` is deliberately not the test: it answers True for the
    # superscripts and the non-ASCII digits Python considers decimal, and
    # int() accepts those, so "74٠812" would parse as a date.  A date is six
    # characters out of the MRZ's own alphabet, and this is the half of it
    # that is digits.
    if not all(character in string.digits for character in text):
        return None
    return MrzDate(int(text[0:2]), int(text[2:4]), int(text[4:6]))


def date_fault(text: str) -> str | None:
    """Name the part of ``text`` that cannot be a day, or ``None`` if it can.

    ``"month"``, ``"day"`` or ``None``.  **The answer is a component name and
    never a value**, for the reason every message in this package names a
    field and not what the field printed: the month a document carries is two
    digits of a holder's date, and an exception message is the most likely
    thing in this project to reach a log.  A caller puts its own field name
    and its own positions around the name it gets back.

    **A field that is not :data:`DATE_LENGTH` wide has no fault to report,
    and this is deliberate rather than an oversight.**  How wide a date is
    belongs to the layout table, which is where all three format validators
    read their own width from and the reason they read it rather than type in
    a 6; a reader that carried a second width rule of its own could disagree
    with the table and answer about a field the table has not declared yet.
    :func:`parse_date` is the stricter of the two -- it raises, because a
    caller holding five characters has made a mistake and should hear about
    it -- and this is the one place a wrong width is passed over, because the
    three formats have already judged it and judged it the right way.

    **The month is judged before the day, so a date that is wrong in both
    reports the month.**  Printed order is the order the six characters are
    read in, and a month that does not exist makes the day beside it
    meaningless to judge on its own terms anyway.

    **The year is never judged, because two digits cannot be out of range.**
    Every pair of digits in ``00``-``99`` is a year somebody was born in or a
    document was valid for; which of the two centuries it belongs to is a
    different question and this is not it -- :func:`infer_birth_year` is, and
    it is a different question for the two dates a document prints.

    **Characters this function does not read are not faults.**  A date of
    letters or fillers is ``None`` rather than ``"month"``, for
    :func:`parse_date`'s reason: it is not a date that cannot exist, it is a
    date nobody could read, and the check digit printed beside it is what says
    so.

    Returns ``None`` for anything it cannot read as six digits, including a
    non-string: a field nobody could read is not a field carrying an
    impossible month, which is 2.14's distinction at one level up.
    """
    if not isinstance(text, str) or len(text) != DATE_LENGTH:
        return None
    date = parse_date(text)
    if date is None:
        return None
    if not 1 <= date.month <= 12:
        return "month"
    if not 1 <= date.day <= MONTH_DAYS[date.month - 1]:
        return "day"
    return None


def _is_a_real_day(year: int, month: int, day: int) -> bool:
    """Whether ``month``/``day`` is a day of ``year``, the 29th of February included.

    :data:`MONTH_DAYS` cannot ask this, because its February is 29 in every
    century -- 29 days is what refuses nothing genuine, not what every year
    had.  This is the half that needs the year, and it is the only calendar
    rule in this module: everything else is a maximum somebody could read off
    a calendar, and a 29th of February is a year-by-year fact.
    """
    if month == 2 and day == 29:
        return calendar.isleap(year)
    return True


def _readable_date(text: str) -> MrzDate | None:
    """The date ``text`` prints, if one can be placed in a century at all.

    **The two gates 3.11 wrote, asked once here rather than once per rule.**
    :func:`parse_date` goes first because it is the reader and answers ``None``
    for six characters that are not all digits; :func:`date_fault` goes second
    because it *also* answers ``None`` for a field it could not read, and a
    non-``None`` answer means there is no real date to put in any century.
    Asking only the second is the mistake 3.12's first test run caught: a field
    of six letters answers ``None`` there both for "I could not read it" and
    for "there is no fault here", and the caller cannot tell the two apart.

    **A width this package has not declared is answered ``None`` and not
    raised**, for 2.11's reason: the three format validators measure a date
    field against their own layout table, and a rule here that measured it a
    second time could refuse a field the table has deliberately moved.

    Both century rules reach this through one call, so a field both of them
    answer ``None`` for is a field neither could place -- there is no copy of
    the gate to drift, and a caller comparing the two functions is comparing
    their *directions*, which is the part that is genuinely different.
    """
    if not isinstance(text, str) or len(text) != DATE_LENGTH:
        return None
    date = parse_date(text)
    if date is None or date_fault(text) is not None:
        return None
    return date


def infer_birth_year(text: str, reference: datetime.date) -> int | None:
    """Return the four-digit year a date of birth's two digits mean, or ``None``.

    ``text`` is :data:`DATE_LENGTH` characters of ``YYMMDD`` exactly as the
    line printed them, and ``reference`` is the date the reading is made
    against.  **The reference date is an argument and is never read from the
    clock**: an inferred date of birth that differs depending on when the
    screening ran is not a finding, it is an artefact, and `tasks.md` bans
    ``datetime.now()`` inside check logic for the same reason.  Every caller
    and every test passes its own.

    **The rule is the most recent century that works, and only two centuries
    are worth trying.**  ``"00"`` in 2026 is 2000 or 1900, never 1800, because
    a holder is not 126: :data:`MAX_BIRTH_AGE` is what makes the candidate set
    two long.  Each candidate is read in full -- year, month and day -- and
    admitted only if all three hold:

    * **it has already happened.**  A birth date after the reference is a
      misread or a forgery, and the century before it is the only other thing
      two digits can mean.  The comparison is on the whole date, so a document
      printed today and read on the 30th is a birth *today*, while one printed
      for the 1st of October read on the 30th of September is 100 years back.
    * **it is a day that year had.**  This is the leap-year question 3.11
      deferred by putting 29 into February's maximum, and it is answerable
      here only because the century was left open until now.  ``"000229"``
      read in 2026 is 2000-02-29, a real day; the same six characters read in
      2126 would be 2100-02-29, which never was.
    * **it is no more than :data:`MAX_BIRTH_AGE` years before the reference.**
      A 120-year-old is admitted on the day; a 121-year-old is not, and the
      two are one day apart in the reference, which is what makes this a line
      rather than a feeling.

    **The most recent admissible candidate is the answer**, and the first is
    tried first precisely so that the older one is a fallback rather than a
    preference.

    **``None`` is the answer in three different cases, and all three are the
    same sentence said three ways: this document does not tell us.**  The six
    characters are not all digits (a misread, which is the check digit
    printed beside the field's job to report, not this function's);
    :func:`date_fault` names a month or a day that cannot be one, so there is
    no real date to place in a century at all; or no century in the
    :data:`MAX_BIRTH_AGE` window makes those six characters a real past day.
    **A guess is worse than a gap here**: an officer reading a year this
    project invented has no way to know it was invented, whereas a
    missing one is visible.

    **This is a date of birth's rule and only a date of birth's rule.**  An
    expiry is read the other way -- forwards, to the nearest year that has not
    passed -- and :func:`infer_expiry_year` gives that its own function rather
    than a flag on this one, so the two cannot drift: they differ in which
    side of the reference a candidate must be on, and in that only this one
    needs a band at all.  Neither is wired into the three format validators,
    which judge range only.

    Returns:
        A four-digit ``int`` year, not a :class:`~datetime.date` and not an
        :class:`MrzDate`: the century is the part that was missing, the caller
        may want the rest of the date for itself, and returning the year keeps
        this function's one judgement out of a record the readers build.

    Raises:
        MrzValueError: if ``reference`` is not a :class:`datetime.date`.  **A
            bad reference raises where a bad date field does not**, because a
            reference date is never a fact about a document: passing a string
            is a caller who has not injected a date, and answering ``None``
            would report a screening that went wrong as a document that could
            not be read.  (``datetime.datetime`` is a ``datetime.date``, so a
            caller holding a timestamp is not a caller making that mistake.)
    """
    if not isinstance(reference, datetime.date):
        raise MrzValueError(
            f"a reference date must be a date, not {type(reference).__name__}"
        )
    date = _readable_date(text)
    if date is None:
        return None
    century = (reference.year // 100) * 100
    # Most recent first, and only these two: a third century back is beyond
    # MAX_BIRTH_AGE whatever it holds, so it is not a candidate to weigh.
    for year in (century + date.year, century - 100 + date.year):
        if (year, date.month, date.day) > (
            reference.year,
            reference.month,
            reference.day,
        ):
            continue  # a birth has not happened yet
        if not _is_a_real_day(year, date.month, date.day):
            continue  # the 29th of February in a year that had none
        if reference.year - year > MAX_BIRTH_AGE:
            continue  # older than a holder can plausibly be
        return year
    return None


def infer_expiry_year(text: str, reference: datetime.date) -> int | None:
    """Return the four-digit year a date of expiry's two digits mean, or ``None``.

    ``text`` is :data:`DATE_LENGTH` characters of ``YYMMDD`` exactly as the
    line printed them, and ``reference`` is the date the reading is made
    against.  **The reference is injected for the reason
    :func:`infer_birth_year` takes one**: a year that depends on when the
    screening ran is an artefact rather than a finding, so this never reads
    the clock, and a caller who has not injected a date is told rather than
    answered.

    **The rule is the nearest year carrying the two printed digits that the
    document has not already got past, and that was a day that year had.**  It
    is three clauses and the first one is the whole difference from a birth:

    * **it has not already passed.**  Read *forwards*, not backwards -- a
      passport printed in 2012 and read in 2026 has expired, and the only
      other thing "``12``" can mean is 2112.  **The comparison admits the day
      itself, and that is the one place the two dates' rules are not mirror
      images**: a document is valid *through* the day it expires, so a
      passport expiring today is read as this year, while a birth today has
      already happened and is read the same way.  The next day, the same six
      characters mean a century on.
    * **it is a day that year had.**  The same leap-year question
      :func:`infer_birth_year` answers, through the same
      :func:`_is_a_real_day`, and it bites *differently* here: a century that
      is not a leap century is one this rule can run out of.  ``"000229"`` read
      in 2026 is ``None`` -- 2000 has passed and 2100 had no 29th of February
      -- while the same field read in 1999 is 2000.
    * **and there is no band, because there is nothing to bound.**  This is the
      rule's sharpest difference from a birth and it is not an oversight:
      :data:`MAX_BIRTH_AGE` exists because nobody is 121, which is a fact
      about people that the six characters cannot supply.  An expiry has no
      such fact, because **two digits repeat every hundred years, so the
      nearest year that has not passed is at most a century away** -- and that
      is arithmetic, not a decision.  The second candidate is only ever
      reached when the printed year is not ahead of the reference's own, which
      is what puts the answer inside the hundred years between them.  A
      third century would be a century further than the answer can ever be.

    **``None`` is the same three answers :func:`infer_birth_year` gives, and
    the third is the one worth reading closely:** these six characters are not
    all digits; :func:`date_fault` names a month or a day that cannot be one;
    or neither of the two candidate centuries makes them a real day that has
    not passed.  The gates are one function, so a field this answers ``None``
    for is a field a birth answers ``None`` for as well -- what differs between
    the two is only which century each one lands on.

    **The answer is a plain ``int`` beside the record, never a field of it**, for
    :func:`infer_birth_year`'s reason: :class:`MrzDate` still holds three
    numbers and no century, so the same six characters can be read twice from
    one record -- once per date -- and neither reading is baked into it.

    Returns:
        A four-digit ``int`` year, not a :class:`~datetime.date` and not a
        :class:`MrzDate`, for :func:`infer_birth_year`'s reason.

    Raises:
        MrzValueError: if ``reference`` is not a :class:`datetime.date`, on
            :func:`infer_birth_year`'s reasoning and with the same message: a
            reference date is never a fact about a document, and answering
            ``None`` to a caller who has not injected one would report a
            screening that went wrong as a document nobody could read.
            (``datetime.datetime`` is a ``datetime.date``, so a timestamp is
            not that mistake.)
    """
    if not isinstance(reference, datetime.date):
        raise MrzValueError(
            f"a reference date must be a date, not {type(reference).__name__}"
        )
    date = _readable_date(text)
    if date is None:
        return None
    century = (reference.year // 100) * 100
    # The *other* two candidates to a birth's, and the sign is the whole
    # difference: a birth reads back a century, an expiry reads forward one.
    for year in (century + date.year, century + 100 + date.year):
        if (year, date.month, date.day) < (
            reference.year,
            reference.month,
            reference.day,
        ):
            continue  # the document had already expired on that day
        if not _is_a_real_day(year, date.month, date.day):
            continue  # the 29th of February in a year that had none
        return year
    return None
