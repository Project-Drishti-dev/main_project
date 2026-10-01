"""The deterministic date rules, each asked against a reference date.

One rule per question, one answer per rule, and the answer is a record rather
than a flag.  **A rule here decides nothing about a screening**: it says what a
date on a document means relative to the day it was read, and turning that into
an :class:`~app.risk.flags.EvidenceFlag` -- an id, a band, a value, a region --
is 6.3's job.  That is why this module imports nothing from ``app.risk``:
the dependency runs one way, so a rule can never be handed a weightset and
start deciding its own importance.

**The reference date is an argument on every function here and is never read
from the clock.**  A verdict that depends on when the screening ran is an
artefact rather than a finding, so a bad reference is refused loudly rather
than answered ``UNDETERMINED`` -- that answer would report a screening that
went wrong as a document nobody could read.

**The dependency itself is named: :data:`ReferenceDate`.**  The day a rule is
asked against is one declared type rather than a bare
:class:`datetime.date` repeated down the file, so 6.3 and the cascade have
one name to inject, a signature says what it is asking for, and a test can
hold that every rule asks for it and none of them defaults it.  It is an alias
and not a type of this project's own -- a second date type would make every
``isinstance`` here and every record a caller already holds answer to two
questions, and a wrapper would be a place a clock could be read from, which is
the one thing ``tasks.md`` bans.

**No module in this package may reach the calendar on its own behalf.**  The
printed six characters carry no century, and an expiry's is supplied by
:func:`~app.pipeline.tier0.mrz.infer_expiry_year` and by nothing else; every
other question about an expiry is asked of *its* answer rather than of the raw
characters.  ``D8`` in ``docs/DECISIONS.md`` records how an expired document
is recognised from a reading that deliberately never lands in the past.  **A
date of issue is the one date this module reads itself**, in the reference's
own century, and ``D9`` records why the nearest century is the only reading
under which a document that is not valid yet can be observed at all.

**A date of birth is read the other way from both, and only backwards.**  Two
printed digits repeat every hundred years, so a birth read in the reference's
own century puts nearly every living holder in the future -- and a rule that
reported that would be wrong on three quarters of the documents it sees.  So
the two centuries that bracket the reference are the only candidates, the most
recent admissible one is the answer, and ``D10`` records why the future half
of 5.6 is reachable at all: only the caller's configured maximum decides how
far back a reading may reach.

**The fourth rule reads no date of its own.**  It is handed the two records
above and compares the days they carry, because a document issued after it
expired contradicts *itself* and the day the reader happened to run is not
part of that.  So it takes no ``text`` and no ``reference``, adds no third
reading, and ``D11`` records why the half that could be read does not lend its
verdict to the half that could not.
"""

import dataclasses
import datetime

from .mrz import MAX_BIRTH_AGE, MrzValueError, infer_expiry_year, parse_date

__all__ = [
    "BIRTH_STATUSES",
    "CONSISTENCY_STATUSES",
    "CONSISTENT",
    "EXPIRED",
    "EXPIRING_TODAY",
    "EXPIRY_STATUSES",
    "IMPLAUSIBLE",
    "ISSUE_AFTER_EXPIRY",
    "ISSUE_STATUSES",
    "ISSUED",
    "NOT_YET_VALID",
    "PLAUSIBLE",
    "ReferenceDate",
    "UNDETERMINED",
    "VALID",
    "BirthResult",
    "ConsistencyResult",
    "ExpiryResult",
    "IssueResult",
    "consistency_result",
    "dob_result",
    "expiry_result",
    "issue_result",
]

#: The day a date rule is asked against: **the dependency 6.3 and the cascade
#: inject**, and the same name on every rule that reads a printed date and on
#: the record each one carries it in.  It is :class:`datetime.date` and nothing
#: more, so no rule here can be handed a clock to read instead of a day.
#:
#: **A :class:`datetime.datetime` is a legal injection** and is reduced to its
#: day by :func:`_as_day`, on
#: :func:`~app.pipeline.tier0.mrz.infer_expiry_year`'s reasoning: a caller
#: holding a timestamp is not a caller making that mistake.  Every record
#: carries the plain :class:`~datetime.date` this names, whichever of the two
#: the caller injected.
ReferenceDate = datetime.date

#: The date of expiry fell before the reference date.
EXPIRED = "expired"
#: The date of expiry is the reference date, and a document is valid *through*
#: the day it expires, so this is not :data:`EXPIRED`.
EXPIRING_TODAY = "expiring_today"
#: The date of expiry is after the reference date.
VALID = "valid"
#: The document does not tell us: the six characters are not all digits, they
#: cannot be a real day, or no century makes them one the rule can place.
#: **This is a gap and never a verdict**, in the same sense as the ``None``
#: :func:`~app.pipeline.tier0.mrz.infer_expiry_year` answers.
UNDETERMINED = "undetermined"

#: The four answers, and the only ones :class:`ExpiryResult` accepts.
EXPIRY_STATUSES = frozenset({EXPIRED, VALID, EXPIRING_TODAY, UNDETERMINED})

#: The date of issue is the reference date or earlier, so the document's
#: validity window has opened.  **A document is valid from the day it is
#: issued**, so the day of issue itself is this answer rather than a third
#: one, in the same way :data:`EXPIRING_TODAY` exists rather than folding into
#: :data:`EXPIRED`.
ISSUED = "issued"
#: The date of issue is after the reference date, so the document's validity
#: window has not opened yet.
NOT_YET_VALID = "not_yet_valid"

#: The three answers, and the only ones :class:`IssueResult` accepts.
ISSUE_STATUSES = frozenset({ISSUED, NOT_YET_VALID, UNDETERMINED})

#: The date of birth has happened and implies an age inside the configured
#: maximum.  **This is the answer a document earns by being ordinary**, which
#: is why it is a status rather than the absence of a finding: 6.3 asks what
#: the rule found, and "a holder of plausible age" is the thing it found.
PLAUSIBLE = "plausible"
#: The date of birth has not happened yet, or implies an age over the
#: configured maximum.  **Both halves are one status**, on
#: ``flag_ids.DATE_IMPLAUSIBLE_DOB``'s own grounds that 5.6 states them as one
#: rule; which half it was is readable off :attr:`BirthResult.birth` against
#: :attr:`BirthResult.reference` and needs no fourth answer.
IMPLAUSIBLE = "implausible"

#: The three answers, and the only ones :class:`BirthResult` accepts.
BIRTH_STATUSES = frozenset({PLAUSIBLE, IMPLAUSIBLE, UNDETERMINED})

#: The document's two dates run the right way round: the window opens on the
#: date of issue and closes on the date of expiry.  **A document is consistent
#: with itself**, which is the answer it earns by being ordinary and the
#: reason this is a status rather than the absence of a finding, for
#: :data:`PLAUSIBLE`'s reason.
CONSISTENT = "consistent"
#: The date of issue is after the date of expiry, so the window runs backwards
#: and the document contradicts itself.
ISSUE_AFTER_EXPIRY = "issue_after_expiry"

#: The three answers, and the only ones :class:`ConsistencyResult` accepts.
CONSISTENCY_STATUSES = frozenset({CONSISTENT, ISSUE_AFTER_EXPIRY, UNDETERMINED})


def _check_status(status: object, statuses: frozenset[str]) -> None:
    """Refuse ``status`` unless it is a string belonging to ``statuses``.

    The type is tested before the membership so that an unhashable value is a
    refusal of the rule's own shape rather than a ``TypeError`` from the
    lookup.
    """
    if not isinstance(status, str) or status not in statuses:
        raise MrzValueError(
            "status must be one of " + ", ".join(sorted(statuses))
        )


def _check_result(
    status: object,
    dated: object,
    reference: object,
    statuses: frozenset[str],
    name: str,
) -> None:
    """Refuse a result whose three fields do not go together.

    ``status`` is one of ``statuses``, ``reference`` is the day the question
    was asked on and is a date, and ``dated`` is the day the verdict is about,
    which is a date or ``None``.  ``name`` is what ``dated`` is called, so a
    refusal names the field the caller filled in.

    **A ``datetime.datetime`` passes both date tests**, which is deliberate and
    is what :func:`~app.pipeline.tier0.mrz.infer_expiry_year` already
    documents: a caller holding a timestamp is not a caller making that
    mistake.  :func:`expiry_result` and :func:`issue_result` build plain dates
    regardless, so the day they compared is the day on the record.

    The pairing is the invariant worth holding: **only an
    :data:`UNDETERMINED` result carries no date, and every other result
    carries one.**
    """
    _check_status(status, statuses)
    if not isinstance(reference, datetime.date):
        raise MrzValueError(
            f"reference must be a date, not {type(reference).__name__}"
        )
    if dated is None:
        if status != UNDETERMINED:
            raise MrzValueError(f"a {status} result carries its date")
        return
    if not isinstance(dated, datetime.date):
        raise MrzValueError(f"{name} must be a date, not {type(dated).__name__}")
    if status == UNDETERMINED:
        raise MrzValueError("an undetermined result carries no date")


@dataclasses.dataclass(frozen=True)
class ExpiryResult:
    """What a document's date of expiry means on one reference day.

    :attr:`status` is one of :data:`EXPIRY_STATUSES`, and
    :attr:`expiry` is the day the verdict is about with its century resolved:
    **for an expired document that is the day it expired on rather than the
    year it was given.**  :attr:`reference` is the day the question was asked
    against, carried rather than re-asked for, so the record says what it was
    compared with.

    :attr:`expiry` is ``None`` for exactly one status, :data:`UNDETERMINED`,
    and a value in any other shape is refused.  **Frozen and carrying no
    public method**, for the reason
    :class:`~app.pipeline.tier0.td3.MrzDocument` and
    :class:`~app.risk.flags.EvidenceFlag` are: a method here would be a second
    answer about the document, and could disagree with the status the record
    was built with.
    """

    status: str
    expiry: datetime.date | None
    reference: ReferenceDate

    def __post_init__(self) -> None:
        """Check the three fields go together, assign nothing, and return ``None``."""
        _check_result(
            self.status, self.expiry, self.reference, EXPIRY_STATUSES, "expiry"
        )


@dataclasses.dataclass(frozen=True)
class IssueResult:
    """What a document's date of issue means on one reference day.

    :attr:`status` is one of :data:`ISSUE_STATUSES`, :attr:`issue` is the day
    of issue with its century resolved -- **the day the validity window opens
    on, which is what a finding needs to put in ``found``** -- and
    :attr:`reference` is the day the question was asked against, carried for
    :class:`ExpiryResult`'s reason.

    :attr:`issue` is ``None`` for exactly one status, :data:`UNDETERMINED`,
    and a value in any other shape is refused.  **Frozen and carrying no
    public method**, for :class:`ExpiryResult`'s reason: a method would be a
    second answer about the document.
    """

    status: str
    issue: datetime.date | None
    reference: ReferenceDate

    def __post_init__(self) -> None:
        """Check the three fields go together, assign nothing, and return ``None``."""
        _check_result(
            self.status, self.issue, self.reference, ISSUE_STATUSES, "issue"
        )


@dataclasses.dataclass(frozen=True)
class BirthResult:
    """What a document's date of birth means on one reference day.

    :attr:`status` is one of :data:`BIRTH_STATUSES`, :attr:`birth` is the day
    of birth with its century resolved -- **the reading the verdict was made
    from, which is the day a finding puts in ``found``** -- and
    :attr:`reference` is the day the question was asked against, carried for
    :class:`ExpiryResult`'s reason.

    **One record carries the reading rather than an age**, because an age is a
    difference between two of the fields the record already holds and a method
    computing it would be the second answer about the document that
    :class:`ExpiryResult` is frozen to prevent.  :attr:`birth` is ``None`` for
    exactly one status, :data:`UNDETERMINED`, and a value in any other shape is
    refused; the two halves of :data:`IMPLAUSIBLE` are told apart by comparing
    :attr:`birth` with :attr:`reference` rather than by a second status.
    """

    status: str
    birth: datetime.date | None
    reference: ReferenceDate

    def __post_init__(self) -> None:
        """Check the three fields go together, assign nothing, and return ``None``."""
        _check_result(
            self.status, self.birth, self.reference, BIRTH_STATUSES, "birth"
        )


@dataclasses.dataclass(frozen=True)
class ConsistencyResult:
    """Whether a document's two dates are consistent with each other.

    :attr:`status` is one of :data:`CONSISTENCY_STATUSES`, and
    :attr:`issue` and :attr:`expiry` are the two days the comparison was made
    from, **which are the two halves a finding puts in ``expected`` and
    ``found``**.  :attr:`reference` is the day the two records being compared
    were read against, carried for :class:`ExpiryResult`'s reason -- **it is
    not an argument of its own here**, because this rule reads no date of its
    own and the day belongs to the two records it was handed.  **It is a
    :data:`ReferenceDate` like the other three**, and that is the whole of the
    difference: this rule carries the dependency off its arguments instead of
    taking it from the caller.

    **A verdict carries both days and the gap carries neither.**  One call to
    :func:`_check_result` per date is what holds that: the pairing the other
    three records have is "only an :data:`UNDETERMINED` result carries no
    date", and a date nobody could read on one side is not half a comparison.

    **Frozen and carrying no public method**, for :class:`ExpiryResult`'s
    reason: a method here would be a second answer about the document, and it
    could disagree with the one comparison the status was built from.
    """

    status: str
    issue: datetime.date | None
    expiry: datetime.date | None
    reference: ReferenceDate

    def __post_init__(self) -> None:
        """Check the four fields go together, assign nothing, and return ``None``."""
        _check_result(
            self.status, self.issue, self.reference, CONSISTENCY_STATUSES, "issue"
        )
        _check_result(
            self.status, self.expiry, self.reference, CONSISTENCY_STATUSES, "expiry"
        )


def _as_day(reference: datetime.date) -> datetime.date:
    """Return ``reference`` as a plain :class:`datetime.date`, or refuse it.

    **A bad reference raises and is never answered**, on
    :func:`~app.pipeline.tier0.mrz.infer_expiry_year`'s reasoning: a reference
    date is never a fact about a document, so a caller who has not injected
    one has made a mistake rather than handed over a document that cannot be
    read.  A timestamp is a legal reference and is reduced to its day, because
    an expiry is a day and a flag built from a time of day would say so.
    """
    if not isinstance(reference, datetime.date):
        raise MrzValueError(
            f"a reference date must be a date, not {type(reference).__name__}"
        )
    return datetime.date(reference.year, reference.month, reference.day)


def _rolled_a_century_forward(year: int, reference: datetime.date) -> bool:
    """Whether ``year`` is a century ahead of ``reference``, which means expiry.

    :func:`~app.pipeline.tier0.mrz.infer_expiry_year` reads an expiry
    *forwards*: it answers the nearest year carrying the two printed digits
    that the document has not already got past, so it never answers a year
    that is behind the reference.  Its answer is therefore always in the
    reference's own century or the one after it, and **the century it chose is
    the whole of the expiry finding**: an answer a century on means the reading
    in this century had already gone past, which is what expiry is.

    Comparing the two centuries rather than the two years is what keeps this
    from being a second rule about centuries: the year itself came from
    :func:`~app.pipeline.tier0.mrz.infer_expiry_year` and is only being asked
    which of the two it is.
    """
    return year // 100 == reference.year // 100 + 1


def _expired_on(
    parsed, year: int, reference: datetime.date
) -> ExpiryResult:
    """The result for a document whose expiry is behind the reference.

    The date is the answer a century back from the one that was read, which is
    the reading that had passed -- the day the document expired rather than
    the year the field was allowed to mean.

    **One day that cannot exist makes the whole answer undetermined rather
    than wrong.**  A 29th of February reaches the second candidate for the
    calendar instead of the reference in exactly one shape: a century that is
    not a leap century, read before that February arrived.  1900 is the shape
    it takes, and un-rolling 2000-02-29 for a reference in January 1900 would
    be a day that never was.
    """
    try:
        expiry = datetime.date(year - 100, parsed.month, parsed.day)
    except ValueError:  # a 29th of February of a year that had none
        return ExpiryResult(UNDETERMINED, None, reference)
    return ExpiryResult(EXPIRED, expiry, reference)


def expiry_result(text: str, reference: ReferenceDate) -> ExpiryResult:
    """Read the printed date of expiry in ``text`` against ``reference``.

    ``text`` is :data:`~app.pipeline.tier0.mrz.DATE_LENGTH` characters of
    ``YYMMDD`` exactly as the line printed them, and ``reference`` is a
    :data:`ReferenceDate`: the day the reading is made against.  **Both are
    arguments and neither has a default**: the answer to this question is a
    finding about a document and a finding must not depend on when the
    screening ran.

    The three verdicts and the one gap:

    * :data:`EXPIRED` -- the date of expiry fell before the reference.  It is
      read from the century
      :func:`~app.pipeline.tier0.mrz.infer_expiry_year` chose rather than
      inferred here, and it is what a document printed in 2012 and read in
      2026 needs: that reading answers 2112, and a hundred years of validity
      is not what the document says.
    * :data:`EXPIRING_TODAY` -- the date of expiry *is* the reference, and a
      document is valid through the day it expires, so this is its own answer
      and not :data:`EXPIRED` with a rounding.
    * :data:`VALID` -- the date of expiry is after the reference.
    * :data:`UNDETERMINED` -- **the document does not tell us**: the six
      characters are not all digits, they are a month or a day that cannot be
      one, or no century makes them a real day that reading puts behind the
      reference.  Nothing is refused and no date is invented.

    A date in this century that has passed is reported with the day it passed
    on, and the reading that
    :func:`~app.pipeline.tier0.mrz.infer_expiry_year` offers is kept rather
    than replaced: that function's rule has no band, so two printed digits
    always mean the nearest year ahead, and ``991231`` read in 2026 is a
    document valid until 2099.  That is 3.13's decision and not one this rule
    makes.

    Returns:
        An :class:`ExpiryResult`: a status, the day the verdict is about, and
        the reference it was made against.

    Raises:
        MrzValueError: if ``reference`` is not a
            :class:`datetime.date`, or if ``text`` is not a string of exactly
            :data:`~app.pipeline.tier0.mrz.DATE_LENGTH` characters.  **A wrong
            width is a caller's mistake rather than a fact about a document**,
            on
            :func:`~app.pipeline.tier0.mrz.parse_date`'s reasoning: the format
            validators measure a date field against their own layout table
            before it reaches here.
    """
    reference = _as_day(reference)
    parsed = parse_date(text)
    if parsed is None:
        return ExpiryResult(UNDETERMINED, None, reference)
    year = infer_expiry_year(text, reference)
    if year is None:
        return ExpiryResult(UNDETERMINED, None, reference)
    if _rolled_a_century_forward(year, reference):
        return _expired_on(parsed, year, reference)
    expiry = datetime.date(year, parsed.month, parsed.day)
    if expiry == reference:
        return ExpiryResult(EXPIRING_TODAY, expiry, reference)
    return ExpiryResult(VALID, expiry, reference)


def _day_in_this_century(parsed, reference: datetime.date) -> datetime.date | None:
    """The day ``parsed`` names in the reference's own century, or ``None``.

    **The reading is the *nearest* century carrying the two printed digits,
    and no other century is tried.**  The reported date is therefore the same
    date the verdict is about, and the two cannot disagree.

    ``None`` is the answer for a month or a day the calendar has not, and for
    the 29th of February of a year that had none -- the one question
    :class:`~app.pipeline.tier0.mrz.MrzDate` leaves open and
    :func:`~app.pipeline.tier0.mrz.date_fault` plus the year-only leap test
    between them answer.  ``datetime.date`` refuses all three in one place, so
    this is that answer reached through the constructor rather than a second
    gate copied beside it.

    **A date of birth reads two centuries, so this is its near half.**
    :func:`dob_result` asks :func:`_day_in_century` for the century behind as
    well, and :func:`issue_result` only ever wants this one: an issue date read
    a century back could never be in the future, so a second century there would
    be a reading the rule never asked for.
    """
    return _day_in_century(parsed, (reference.year // 100) * 100)


def _day_in_century(parsed, base: int) -> datetime.date | None:
    """The day ``parsed`` names in the century beginning at ``base``, or ``None``.

    ``None`` is the answer for a month or a day the calendar has not, and for
    the 29th of February of a year that had none -- the one question
    :class:`~app.pipeline.tier0.mrz.MrzDate` leaves open and
    :func:`~app.pipeline.tier0.mrz.date_fault` plus the year-only leap test
    between them answer.  ``datetime.date`` refuses all three in one place, so
    this is that answer reached through the constructor rather than a second
    gate copied beside it.

    **The two centuries a birth is read in are two calls to this**, and that is
    what keeps the century arithmetic in one place: ``000229`` is ``None`` in a
    century that had no 29th of February and a real day in one that did, and a
    rule that read the near half twice could not tell those apart.
    """
    try:
        return datetime.date(base + parsed.year, parsed.month, parsed.day)
    except ValueError:  # a month, a day or a 29th of February that never was
        return None


def issue_result(text: str, reference: ReferenceDate) -> IssueResult:
    """Read the printed date of issue in ``text`` against ``reference``.

    ``text`` is :data:`~app.pipeline.tier0.mrz.DATE_LENGTH` characters of
    ``YYMMDD`` exactly as the document printed them, and ``reference`` is a
    :data:`ReferenceDate`: the day the reading is made against.  **Both are
    arguments and neither has a default**, for :func:`expiry_result`'s
    reason: a finding must not depend on when the screening ran.

    The two verdicts and the one gap:

    * :data:`ISSUED` -- the date of issue is the reference date or earlier, so
      the validity window has opened.  A document is valid from the day it is
      issued, so the day of issue itself is this answer.
    * :data:`NOT_YET_VALID` -- the date of issue is after the reference, and
      :attr:`IssueResult.issue` is the day the window opens on.
    * :data:`UNDETERMINED` -- **the document does not tell us**: the six
      characters are not all digits, they name a month or a day no year had,
      or the reference's own century had no such day.  Nothing is refused and
      no date is invented.

    Returns:
        An :class:`IssueResult`: a status, the day of issue with its century
        resolved, and the reference it was made against.

    Raises:
        MrzValueError: if ``reference`` is not a
            :class:`datetime.date`, or if ``text`` is not a string of exactly
            :data:`~app.pipeline.tier0.mrz.DATE_LENGTH` characters, on
            :func:`expiry_result`'s reasoning for both.
    """
    reference = _as_day(reference)
    parsed = parse_date(text)
    if parsed is None:
        return IssueResult(UNDETERMINED, None, reference)
    issue = _day_in_this_century(parsed, reference)
    if issue is None:
        return IssueResult(UNDETERMINED, None, reference)
    if issue > reference:
        return IssueResult(NOT_YET_VALID, issue, reference)
    return IssueResult(ISSUED, issue, reference)


def _check_max_age(max_age: object) -> None:
    """Refuse ``max_age`` unless it is a whole number of years within the band.

    A bound the caller typed wrong -- a string, a float, a ``bool``, a year
    count past :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE` -- is a caller
    mistake, and is raised on rather than answered, for :func:`_as_day`'s
    reason: a band that is not a number of years is not a wide band, it is a
    screening that went wrong.  :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE`
    is the ceiling rather than a second opinion, so this module holds no figure
    of its own.
    """
    if isinstance(max_age, bool) or not isinstance(max_age, int):
        raise MrzValueError(
            f"a maximum age must be a number of years, not "
            f"{type(max_age).__name__}"
        )
    if not 0 <= max_age <= MAX_BIRTH_AGE:
        raise MrzValueError(
            f"a maximum age must be between 0 and {MAX_BIRTH_AGE} years"
        )


def _whole_years(birth: datetime.date, reference: datetime.date) -> int:
    """The whole years a holder of ``birth`` has lived on ``reference``.

    **Whole years, and the day a birthday falls is the day it counts**, so a
    holder born on the 30th of September 2007 is eighteen on the 29th of
    September 2026 and nineteen on the 30th.  Counting anything finer would
    make the same six characters change verdict in the middle of the day the
    birthday falls rather than on it, and an age is a thing people count in
    whole years.
    """
    years = reference.year - birth.year
    if (reference.month, reference.day) < (birth.month, birth.day):
        years -= 1
    return years


def _older_than_the_maximum(
    birth: datetime.date, reference: datetime.date, max_age: int
) -> bool:
    """Whether ``birth`` implies an age over ``max_age`` on ``reference``.

    **The maximum is inclusive** -- a holder of exactly ``max_age`` years is
    inside it -- and the two are one day apart in the reference, which is what
    makes this a line rather than a feeling.

    **A maximum of zero admits only a birth on the reference day itself.**  That
    is the band's floor rather than a special case bolted on: a band of no
    years is one day wide, and a holder born before the reference has already
    lived a day that the band has no room for.
    """
    if max_age == 0:
        return birth < reference
    return _whole_years(birth, reference) > max_age


def dob_result(
    text: str, reference: ReferenceDate, max_age: int = MAX_BIRTH_AGE
) -> BirthResult:
    """Read the printed date of birth in ``text`` against ``reference``.

    ``text`` is :data:`~app.pipeline.tier0.mrz.DATE_LENGTH` characters of
    ``YYMMDD`` exactly as the document printed them, ``reference`` is the day
    the reading is made against as a :data:`ReferenceDate`, and ``max_age`` is
    the oldest age in years the caller will admit a holder to be.  **The first
    two are arguments and neither has a default**, for
    :func:`expiry_result`'s reason; the third defaults to
    :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE` because a bound is a fact
    about the caller rather than about the day the screening ran.

    **The two verdicts the task names are one status**, on
    ``flag_ids.DATE_IMPLAUSIBLE_DOB``'s own grounds that they are one rule:
    a birth that has not happened, and a birth implying an age over the
    maximum.  Which of the two fired is readable off :attr:`BirthResult.birth`
    against :attr:`BirthResult.reference`, and it needs no fourth answer:

    * :data:`IMPLAUSIBLE` -- the birth is after the reference and has not
      happened, or it has happened and implies an age over ``max_age``.
    * :data:`PLAUSIBLE` -- the birth has happened and the holder is inside the
      band.  **This is the answer a document earns by being ordinary**, which is
      why it is a status and not the absence of a finding.
    * :data:`UNDETERMINED` -- **the document does not tell us**: the six
      characters are not all digits, no century makes them a real day, or the
      only reading left is a birth over the configured maximum.  Nothing is
      refused and no date is invented.

    **The reading is backwards, and the band is what decides how far back it
    may reach.**  Two printed digits repeat every hundred years, so the two
    centuries bracketing the reference are the only candidates and the near one
    is taken whenever it has already happened.  Where the near one has *not* --
    "99" printed in 2026 -- the century behind is read instead, and only when
    the caller's band admits a holder of that age.  **At the default neither
    branch can fire**, because a two-century reading implies an age of at most
    99 and :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE` is 120, so this rule
    agrees with :func:`~app.pipeline.tier0.mrz.infer_birth_year` about
    everything; ``D10`` records why the future half is reachable at all, and
    it is reachable only by configuring a maximum low enough to make it so.

    Returns:
        A :class:`BirthResult`: a status, the day of birth the verdict was made
        from, and the reference it was made against.

    Raises:
        MrzValueError: if ``reference`` is not a :class:`datetime.date`, or if
            ``text`` is not a string of exactly
            :data:`~app.pipeline.tier0.mrz.DATE_LENGTH` characters, on
            :func:`expiry_result`'s reasoning for both; or if ``max_age`` is
            not a whole number of years between zero and
            :data:`~app.pipeline.tier0.mrz.MAX_BIRTH_AGE`.
    """
    reference = _as_day(reference)
    _check_max_age(max_age)
    parsed = parse_date(text)
    if parsed is None:
        return BirthResult(UNDETERMINED, None, reference)
    near = _day_in_this_century(parsed, reference)
    far = _day_in_century(parsed, (reference.year // 100) * 100 - 100)
    birth = near
    if near is None or near > reference:
        # The printed digits put the birth ahead of the reference, or the near
        # century had no such day.  The century behind is the only other thing
        # two digits can mean, and the caller's band is what admits it: a
        # tightened maximum that excludes a holder of that age leaves the near
        # reading standing, and a birth that has not happened is this rule's
        # finding rather than a guess.
        if far is not None and _whole_years(far, reference) <= max_age:
            birth = far
    if birth is None:
        return BirthResult(UNDETERMINED, None, reference)
    if birth > reference or _older_than_the_maximum(birth, reference, max_age):
        return BirthResult(IMPLAUSIBLE, birth, reference)
    return BirthResult(PLAUSIBLE, birth, reference)


def _check_record(value: object, kind: type, name: str) -> None:
    """Refuse ``value`` unless it is a record of ``kind``.

    The two records this rule reads are different types on purpose, so a
    caller that handed the expiry result over where the issue result belongs
    is caught here rather than comparing a document against itself.  The
    refusal is :class:`~app.pipeline.tier0.mrz.MrzValueError` rather than a
    :class:`TypeError` because that is the one type this package raises.
    """
    if not isinstance(value, kind):
        raise MrzValueError(
            f"{name} must be a {kind.__name__}, not {type(value).__name__}"
        )


def consistency_result(issue: IssueResult, expiry: ExpiryResult) -> ConsistencyResult:
    """Compare a document's date of issue with its date of expiry.

    ``issue`` and ``expiry`` are the :class:`IssueResult` and
    :class:`ExpiryResult` that :func:`issue_result` and :func:`expiry_result`
    produced, **and they are the only arguments**.  This is the first rule in
    this module that reads no date of its own: a document issued after it
    expired contradicts itself, and the day the reader happened to run is not
    part of that.  So there is no ``reference`` to inject, no ``text`` to read
    again and no third reading to invent -- the two records hold the readings,
    and a rule that resolved its own would be a second answer about the same
    six characters.

    **This is the one rule the :data:`ReferenceDate` dependency is not an
    argument of**, and the exception is the rule itself rather than a gap in
    it: the two arguments were each read against a ``ReferenceDate``, they
    must agree on it, and the result carries it.  ``D12`` records why that is
    the injection rather than a rule exempt from one.

    The arguments are in the order the window runs -- the date of issue opens
    it, the date of expiry closes it -- and they are different types, so the
    order a caller gets wrong is told rather than compared.

    The two verdicts and the one gap:

    * :data:`ISSUE_AFTER_EXPIRY` -- the date of issue is after the date of
      expiry.  **The boundary day is not this finding**: a document issued and
      expiring on the same day has a one-day window, and
      :data:`EXPIRING_TODAY` already holds that a document is valid *through*
      the day it expires.
    * :data:`CONSISTENT` -- the date of issue is the date of expiry or
      earlier.  **A document is compared with itself and not with the
      reader**, so an expired document, and a window that has not opened, are
      both consistent when their own two dates run the right way round.
      :data:`EXPIRED` and :data:`NOT_YET_VALID` are the other two rules'
      answers about the reference day and this rule never reads them.
    * :data:`UNDETERMINED` -- **the document does not tell us**: either record
      is :data:`UNDETERMINED`, so there is no pair of days to compare.  **The
      readable half does not lend its verdict**, because "an issue date nobody
      could read" and "an issue date after the expiry" are different
      sentences, and the gap belongs to the document rather than to this
      comparison.

    Returns:
        A :class:`ConsistencyResult`: a status, the two days the comparison
        was made from, and the reference the two records were read against.

    Raises:
        MrzValueError: if either argument is not the record of the kind this
            parameter names, or if the two records were read against different
            reference days.  **Two days are two screenings rather than one
            document**, so a disagreement is a caller mistake answered on
            :func:`_as_day`'s reasoning and not a fact about a document.
    """
    _check_record(issue, IssueResult, "issue")
    _check_record(expiry, ExpiryResult, "expiry")
    reference = _as_day(issue.reference)
    if _as_day(expiry.reference) != reference:
        raise MrzValueError(
            "the two results must have been read against the same reference day"
        )
    if issue.status == UNDETERMINED or expiry.status == UNDETERMINED:
        return ConsistencyResult(UNDETERMINED, None, None, reference)
    if issue.issue > expiry.expiry:
        return ConsistencyResult(
            ISSUE_AFTER_EXPIRY, issue.issue, expiry.expiry, reference
        )
    return ConsistencyResult(CONSISTENT, issue.issue, expiry.expiry, reference)
