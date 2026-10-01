"""Tier 0 as one call: a page in, a record of what was measured out.

This is the seam the cascade and the HTTP boundary call, and it is the first
place in the project where a whole page rather than one zone is the subject.
:func:`run_tier0` runs Part 4's
:func:`~app.pipeline.tier0.mrz_region.detect_mrz` over the frame it is handed
and reports what was measured: the format the zone has the shape of, and one
polygon per line the chain found.  **Nothing here judges a document.**

**A finding is a flag, and a flag is not decided here.**  The rules the
cascade will ask are Parts 5 and 6.2 to 6.4 -- the check digits, the date
rules, the watchlist -- and each of those produces a record that this module
turns into an :class:`~app.risk.flags.EvidenceFlag`.  The weight belongs to the
weightset and the band to the score, so nothing in this package may decide how
much a finding is worth; that is why ``flags`` is the one type imported here
and why no rule module may be handed one.  **6.2 wires the check digits and 6.4
the watchlist**, and 6.3 is what adds the date family beside them.

**The runner holds no rule of its own.**  It measures, it collects, and it
reports; a second opinion about what a page holds is the failure Part 4 has
spent four parts avoiding, and a threshold typed in here would be one that no
standard section wrote.  So the format comes from
:func:`~app.pipeline.tier0.document.detect_mrz_format` by way of 4.7 and
nowhere else, and the regions are 4.8's own polygons handed over untouched.
**The arithmetic is not repeated here either.**  6.2 asks
:attr:`~app.pipeline.tier0.td3.MrzDocument.check_digit_results` which fields
disagreed and reads neither a line nor a digit: the verdict, the two digits it
compares and the field it belongs to are all already on
:class:`~app.pipeline.tier0.mrz.CheckDigitResult`, and a module that
recomputed one would be a second place to disagree with Part 1's arithmetic.

**A list is asked, never imported.**  6.4's connector arrives as an argument
built on :class:`~app.risk.watchlist.Watchlist`, and the runner knows the
seam and nothing behind it -- not the seed, not 5.11's mock, not whatever a
live stolen-document feed will be -- so swapping one for another changes no
caller.  **A list is asked with the three values a document printed and with
nothing tidied**, and a hit is a record naming an entry rather than the value
that matched it, so a flag can be written from it without carrying a document
number, a name or a date of birth to the dashboard.  **A blacklist hit is a
hard fail and a stolen-document hit is not**, and a failed printed check
digit is one beside it.  So :attr:`TierResult.hard_failed` is 6.5's one
question about the flags rather than a thing any single rule sets: which
rules are hard fails is read off each family's own table, and the reason is
what those findings' own ``label``s say.

**No module here reaches the calendar.**  ``reference_date`` is the
:data:`~app.pipeline.tier0.dates.ReferenceDate` dependency 5.8 declared: 6.3
injects it into each date rule, and 6.4 hands it to 5.6 because a list is
asked about a date of birth as a resolved day and never as the six printed
characters.  ``None`` here means the caller injected nothing, and a rule that
needs a day refuses it rather than reading the clock for one.  **6.6 reads a
stopwatch and not a day**: :func:`_now` is :func:`time.perf_counter`, which
answers "how long since this instant" and resolves no date, so the
instrumentation does not weaken the claim 6.2's and 6.4's AST walks hold.
``document_type`` is a claim the caller brought and not a constraint on what
is measured: the zone's shape decides the format, so a caller who names a
passport in front of a TD1 still gets the TD1 the pixels have.  ``D16``
records both.

**A run says how long it took, and the figure is measured here rather than
asked of the caller.**  6.6's :attr:`TierResult.stage_timings` carries one
duration per stage under :data:`STAGE_NAMES`, so the task that shows an
officer "Tier 0 took 0.11 s" against the abstract's sub-0.3 s target reads a
number off the result instead of timing the call from outside.  **The stages
are the three things this runner does** -- Part 4's chain, 6.2's digits and
6.4's lists -- and **``total`` is a measurement rather than their sum**: it
spans the refusals as well, so it is at least every stage and rather more
than the three added together, and a caller that summed them would
under-report the one figure the abstract bounds.

**A page with no machine-readable zone on it is a value and not an
exception**, for the reason every refusal in Part 4's chain already is one:
:attr:`TierResult.detected_format` is ``None``, the regions are empty and
there is nothing for a caller to catch.
"""

import collections.abc
import dataclasses
import datetime
import numbers
import time
import types

from app.risk import flag_ids
from app.risk import watchlist as watchlist_seam
from app.risk.flags import EvidenceFlag

from . import dates, document, mrz_region
from .mrz import MrzValueError

__all__ = ["STAGE_NAMES", "TIER_NAME", "TierResult", "run_tier0"]

#: What this tier calls itself, as an audit payload spells it.  Stated here
#: rather than beside the cascade that runs it, so the name on the trail is
#: the one the code that did the work carries and a later tier names itself
#: the same way.
TIER_NAME = "tier_0"

#: The three format names a :attr:`TierResult.detected_format` may carry, read
#: out of Part 3's own table rather than written down here, so a fourth format
#: is an entry in :data:`~app.pipeline.tier0.document.MRZ_SHAPES` and not an
#: edit to this module.
_FORMAT_NAMES = frozenset(document.MRZ_SHAPES.values())

#: The keys :attr:`TierResult.stage_timings` carries: the three stages
#: :func:`run_tier0` times and the total that spans them.  **One closed
#: vocabulary, written down once**, on :mod:`app.risk.flag_ids`' own
#: reasoning -- the task that puts a duration on an officer's screen reads
#: these names rather than retyping strings beside the abstract's 0.3 s
#: target, and a stage that needs timing later joins by being named here and
#: measured in :func:`run_tier0` rather than by a second table elsewhere.
#:
#: **Every key is on every result, whatever the page and whatever was wired
#: in.**  A page handed no parse still runs the check-digit stage and the
#: watchlist stage and returns from both at once, so those two keys carry a
#: reading taken over an empty call -- a very small number, and ``0.0`` on a
#: counter too coarse to see it -- which is a different statement from a key
#: that was never written, and a missing key would leave every consumer
#: guarding a lookup before it could read a number at all.
STAGE_NAMES = frozenset({"detection", "check_digits", "watchlist", "total"})

#: What one failing printed check digit becomes as a finding: the id
#: :mod:`app.risk.flag_ids` holds for that kind of digit, the sentence an
#: officer reads, and **the layout's own name for the field the digit is
#: printed in**, which is the key 4.12 boxes it under.
#:
#: **Keyed by the label a format's ``*_CHECK_DIGIT_FIELDS`` table gives the
#: row**, not by the field the characters came from, because the composite
#: has no field of its own: ``td1.py``, ``td2.py`` and ``td3.py`` all hold
#: ``None`` there, for the reason their own note gives -- the composite's
#: characters cross a line boundary and a field boundary at once, so a name
#: for them would be lying twice.  The row is named, the field it is printed
#: in is not, and the printed digit's own box is what a highlight goes over.
#:
#: **Three labels have no field of their own and one id between them.**
#: ``optional_data_1``, ``optional_data`` and ``personal_number`` are three
#: printed digits and one rule, which is
#: :mod:`app.risk.flag_ids`' reason and not a second opinion; each still gets
#: its own layout field name, so each is boxed over its own printed digit.
#:
#: **A label missing from this table is refused rather than skipped**, so a
#: fourth format naming a new digit is a loud failure and not a finding that
#: silently never fires.  ``test_tier0_check_digits.py`` holds the table
#: against all three layouts at once.
_CHECK_DIGIT_FLAG = {
    "document_number": (
        flag_ids.MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH,
        "The document number's check digit does not match.",
        "document_number_check_digit",
    ),
    "date_of_birth": (
        flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH,
        "The date of birth's check digit does not match.",
        "date_of_birth_check_digit",
    ),
    "date_of_expiry": (
        flag_ids.MRZ_EXPIRY_CHECK_DIGIT_MISMATCH,
        "The date of expiry's check digit does not match.",
        "date_of_expiry_check_digit",
    ),
    "optional_data_1": (
        flag_ids.MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH,
        "The optional data's check digit does not match.",
        "optional_data_1_check_digit",
    ),
    "optional_data": (
        flag_ids.MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH,
        "The optional data's check digit does not match.",
        "optional_data_check_digit",
    ),
    "personal_number": (
        flag_ids.MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH,
        "The personal number's check digit does not match.",
        "personal_number_check_digit",
    ),
    "composite": (
        flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH,
        "The composite check digit does not match.",
        "composite_check_digit",
    ),
}

#: The ids this family's table calls hard fails, read out of the table rather
#: than written down beside it, for the reason
#: :data:`_WATCHLIST_HARD_FAIL_IDS` gives and with no ``if`` in the
#: comprehension.
#:
#: **Every failing printed check digit is one, and the whole table is the
#: claim** rather than a ``True`` repeated on seven rows: the abstract names a
#: broken checksum beside a blacklist match as the finding that exits straight
#: to High Risk, and it carves out no exception for a composite, for a field
#: a document leaves unused, or for a fourth format's printed digit that this
#: project has not met yet.  **A failed digit is a failed digit**, so a
#: rule that wanted one of them to be soft would have to say so against the
#: abstract rather than by omission here -- and a fourth format naming a new
#: digit joins this set by being a printed digit, which is the reading 6.2
#: already acts on when it fires on ``passed is False``.
_CHECK_DIGIT_HARD_FAIL_IDS = frozenset(
    row[0] for row in _CHECK_DIGIT_FLAG.values()
)

#: What one list hit becomes as a finding, keyed by the ``kind`` the hit
#: carries: the id :mod:`app.risk.flag_ids` holds for that kind of entry, the
#: sentence an officer reads, **the weight band naming how heavy the finding
#: is**, the layout's own name for the field it is about (``None`` where it is
#: about no one field), and whether the kind is a hard fail.
#:
#: **The severity is the kind and never the position in the connector's
#: answer.**  :meth:`~app.risk.watchlist.Watchlist.lookup` promises no order
#: and says so, so a rule that read the first hit as the serious one would be
#: reading an accident; two entries can come back in either order and both
#: findings are owed.
#:
#: **A blacklist hit is a hard fail and a stolen-document hit is not**, and
#: the two sit in the same ``high`` band rather than one above the other: a
#: document number that is blacklisted is refused and a document number
#: recorded as stolen is weighted, which is the abstract's own pair beside its
#: broken-checksum hard rule, and the band a weight is *named* in is not the
#: question.  What a flag weighs is 7.1's weightset, and 6.5 is what
#: generalises ``hard_failed`` to the other families; both are read off this
#: table rather than written down beside it, so 6.5 collects this family's
#: last value with the check digits' rather than asking one family to answer
#: for both.
#:
#: **An identity_seen hit is ``review`` and no more.**  It is a lookup and not
#: a verdict -- what a previous outcome is worth is 7.13's question -- and
#: ``review`` is the band ``tasks.md`` reserves for a case that goes to a
#: person rather than being rejected automatically.  **Its ``value`` and
#: ``confidence`` are still both ``1.0``**, because the finding is that a list
#: answered and not how much the answer is worth: the bound and the decay the
#: abstract asks for are weights, and weights are not chosen here.
#:
#: **A kind missing from this table is refused rather than skipped**, on
#: :func:`_check_digit_flag`'s reasoning: 5.9 already refuses a hit naming a
#: kind outside :data:`~app.risk.watchlist.HIT_KINDS`, and this is the second
#: place that would have to grow for a fourth kind.
_WATCHLIST_FLAG = {
    watchlist_seam.BLACKLIST: (
        flag_ids.WATCHLIST_HIT,
        "The document number is on the blacklist.",
        "high",
        "document_number",
        True,
    ),
    watchlist_seam.STOLEN_DOCUMENT: (
        flag_ids.WATCHLIST_STOLEN_DOCUMENT,
        "The document number is recorded as a stolen document.",
        "high",
        "document_number",
        False,
    ),
    watchlist_seam.IDENTITY_SEEN: (
        flag_ids.WATCHLIST_IDENTITY_SEEN,
        "This name and date of birth have been screened before.",
        "review",
        None,
        False,
    ),
}

#: The ids this family's table calls hard fails, read out of the table rather
#: than written down again, so a kind that becomes a hard fail is one edit and
#: the two lists cannot disagree.  Each row is the five values
#: :data:`_WATCHLIST_FLAG` documents, in that order.
_WATCHLIST_HARD_FAIL_IDS = frozenset(
    row[0] for row in _WATCHLIST_FLAG.values() if row[4]
)

#: Every id this module knows to be a hard fail, across the families wired
#: today, **and it is a union of the families' own tables rather than a list
#: of its own**.  A family states its severities in one place beside the
#: sentence and the field that go with them, and this is the one place that
#: asks all of them the same question, so a rule can never be a hard fail
#: here and something else beside it.
#:
#: **A family joins by adding its own table to the union and nothing else.**
#: Whether a date is a hard fail is 6.3's question to answer against the
#: abstract, and the answer is one value beside the label it belongs to
#: rather than a second list of severities to keep in step with this one.
_HARD_FAIL_IDS = _CHECK_DIGIT_HARD_FAIL_IDS | _WATCHLIST_HARD_FAIL_IDS


def _check_flags(flags: object) -> None:
    """Refuse ``flags`` unless it is a tuple of :class:`EvidenceFlag` records.

    The membership is what the engine reads, so a tuple holding anything else
    is a caller bug rather than a flag: nothing downstream would catch it and
    the weighted sum would score whatever arrived.
    """
    if not isinstance(flags, tuple) or not all(
        isinstance(flag, EvidenceFlag) for flag in flags
    ):
        raise MrzValueError("flags must be a tuple of EvidenceFlag records")


def _check_regions(regions: object) -> None:
    """Refuse ``regions`` unless it is a tuple of Part 4's polygons.

    **The container is checked and the corners are not.**  A list in a frozen
    record is a hole in the frozenness -- it can still be appended to after
    the record was handed over -- and the corners are
    :func:`~app.pipeline.tier0.mrz_region._box_polygon`'s promise, checked
    where a polygon is built into a finding.  A second check here would be a
    second opinion about boxes 4.8 has already written down.
    """
    if not isinstance(regions, tuple):
        raise MrzValueError("detected_regions must be a tuple of polygons")


def _now() -> float:
    """Return the monotonic counter's own reading, in seconds.

    **A stopwatch and not a calendar.**  :func:`time.perf_counter` answers
    "how long since this instant" and resolves no day, which is what keeps
    6.6's instrumentation from weakening this module's own claim: a rule that
    wanted a reference would have to be handed one by its caller, exactly as
    5.8's dependency says, and the difference between two readings carries no
    date for a century to be resolved against.  A wall clock would answer the
    same question and also move when the host's time is corrected, so a
    screening's reported duration would be at the mercy of an NTP step.

    **It is the one place in this module that reads a clock at all**, so the
    AST walks 6.2's and 6.4's tests hold over a module that now measures
    something, and a future stage reaching for :func:`datetime` beside it
    would be one line away from being visible.
    """
    return time.perf_counter()


def _empty_stage_timings() -> collections.abc.Mapping[str, float]:
    """Return the timings of a result nobody measured: every stage at zero.

    **Zero is the honest value and not a missing one.**  ``TierResult()`` is
    the empty result on 6.1's own reasoning -- a page with nothing on it --
    and a default-constructed record is a run nobody watched, so ``0.0`` is
    what each key carries.  **It says the record measured nothing rather than
    that the counter read zero**: a stage that really did nothing in a real
    run reports a small number, not a guaranteed ``0.0``, so the default is a
    statement about the record rather than about the clock.  Either way the
    default carries the whole vocabulary rather than an empty mapping every
    consumer would have to test for.
    """
    return types.MappingProxyType({name: 0.0 for name in STAGE_NAMES})


def _check_stage_timings(
    timings: object,
) -> collections.abc.Mapping[str, float]:
    """Refuse ``timings`` unless it maps every stage to a duration, and freeze it.

    **The read-only copy is the return value and not a courtesy.**  A frozen
    dataclass stops a field being reassigned and does nothing about a
    container, so a dict handed over here would still be the caller's to
    empty or overwrite after the record was built -- the same hole
    :func:`_check_regions` names for a list in place of a tuple.  The record
    therefore keeps a copy of its own, and
    :func:`run_tier0`'s timings dict stops being something it has to wrap.

    **The keys must be exactly :data:`STAGE_NAMES`.**  A missing key is a
    stage a consumer would have to guard against before it could read a
    number, and an unknown one is a stage this vocabulary does not have;
    both are loud here rather than a ``KeyError`` in whatever draws the
    figure, or a ``.get`` default of zero reporting an unmeasured stage as
    an instant one.

    **A value is a real, non-negative, non-boolean number of seconds.**  The
    comparison is chained, ``0 <= value``, so a ``nan`` is refused rather
    than passing a ``< 0`` test it fails in both directions.  **A ``bool`` is
    refused** where 5.2's own check would let one through as a real number:
    ``True`` is one second, which is a caller handing over a truth value
    rather than a measurement.  **A numpy float is not a rejection** -- a
    duration from a timer is a real number whichever library counted it.

    **The message names the stage and the rule and never the value**, on
    ``FlagValueError``'s reasoning: a traceback is a log line, and this is
    not the place to quote whatever arrived.
    """
    if not isinstance(timings, collections.abc.Mapping):
        raise MrzValueError(
            "stage_timings must be a mapping of stage names to seconds, not "
            f"{type(timings).__name__}"
        )
    if set(timings) != STAGE_NAMES:
        raise MrzValueError(
            "stage_timings must carry exactly these stages: "
            + ", ".join(sorted(STAGE_NAMES))
        )
    for name in sorted(STAGE_NAMES):
        value = timings[name]
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise MrzValueError(
                f"the {name} timing must be a real number of seconds, not "
                f"{type(value).__name__}"
            )
        if not 0 <= value:
            raise MrzValueError(
                f"the {name} timing must be zero or more seconds"
            )
    return types.MappingProxyType(dict(timings))


@dataclasses.dataclass(frozen=True)
class TierResult:
    """What one page's Tier 0 run measured: findings, and what was found.

    :attr:`flags` is a tuple of :class:`~app.risk.flags.EvidenceFlag` records
    in the order the rules produced them, and **it is empty rather than
    absent** for a clean document, so "nothing fired" and "nothing was asked"
    are two different statements and only the first is a pass.

    :attr:`hard_failed` and :attr:`hard_fail_reason` are the override and the
    sentence behind it, and **the pairing is the invariant worth holding**: a
    hard fail always carries a reason and a reason always belongs to a hard
    fail.  The abstract requires the reason to be recorded with the exit, so a
    result that raised a document to High and said nothing about it is refused
    here rather than shown to an officer.

    :attr:`detected_format` is one of the three names
    :data:`~app.pipeline.tier0.document.MRZ_SHAPES` holds, or ``None``, and
    ``None`` means this page holds no zone this project reads.  **It is what
    the pixels were measured as and not what the caller asked for**: the
    detected format is the shape's own answer and a caller's claim is not a
    second opinion on it.

    :attr:`detected_regions` is one polygon of whole-pixel corners per
    detected line, in the frame
    :func:`~app.pipeline.tier0.mrz_region.deskew` handed over, and it is
    :func:`~app.pipeline.tier0.mrz_region.line_polygons`' own output handed
    over untouched rather than re-measured.

    :attr:`stage_timings` is how long each stage of the run took, in
    seconds, under :data:`STAGE_NAMES`' four names, and **all four keys are
    always there**: a stage with nothing to do carries a near-zero reading
    and never an absent key, so whoever draws the figure reads a number
    rather than testing for one first.
    **It is read-only**, so a caller who handed over a plain dict cannot
    change the result afterwards -- the same frozenness
    :func:`_check_regions` insists on for a list of polygons.  **``total`` is
    the one the abstract bounds**, since its figure is for the whole of Tier
    0 and not for one stage of it; it is a measurement spanning the refusals
    and the stages rather than the sum of the three, so it is rather more
    than they come to and never less than any one of them.  **The record is
    no longer hashable, and that is the price of the mapping rather than a
    hole in it**: a read-only mapping cannot be hashed, where a tuple of
    pairs could -- and a tuple of pairs would answer ``stage_timings[0]`` as
    readily as ``stage_timings["total"]``, which is the positional reading
    this project refuses everywhere else.  Nothing in the cascade hashes a
    result, and a consumer wanting a number has to name which one.

    **Every field is defaulted, so ``TierResult()`` is the empty result** -- a
    page with nothing on it -- for the reason
    :class:`~app.pipeline.tier0.mrz_region.MrzDetection` is: one value for a
    caller to compare against rather than six containers whose emptiness it
    has to know the shape of.  **A default-constructed result was never
    timed at all**, so its four keys are all ``0.0`` rather than absent --
    which says the record measured nothing, where a stage that ran and took
    no time says how long it took.

    **Frozen and carrying no public method**, for the reason
    :class:`~app.pipeline.tier0.td3.MrzDocument` and
    :class:`~app.risk.flags.EvidenceFlag` are.  A method here would be a
    second opinion about what a screening found, and could disagree with the
    fields the record was built with.
    """

    flags: tuple[EvidenceFlag, ...] = ()
    hard_failed: bool = False
    hard_fail_reason: str | None = None
    detected_format: str | None = None
    detected_regions: tuple[tuple[tuple[int, int], ...], ...] = ()
    stage_timings: collections.abc.Mapping[str, float] = dataclasses.field(
        default_factory=_empty_stage_timings
    )

    def __post_init__(self) -> None:
        """Check the six fields, keep the timings read-only, and return ``None``."""
        if not isinstance(self.hard_failed, bool):
            raise MrzValueError(
                "hard_failed must be a bool, not "
                f"{type(self.hard_failed).__name__}"
            )
        if self.hard_fail_reason is not None and not isinstance(
            self.hard_fail_reason, str
        ):
            raise MrzValueError(
                "hard_fail_reason must be a string or None, not "
                f"{type(self.hard_fail_reason).__name__}"
            )
        if self.hard_failed != (self.hard_fail_reason is not None):
            raise MrzValueError(
                "a hard fail carries its reason and a reason belongs to a "
                "hard fail"
            )
        if self.detected_format is not None and self.detected_format not in (
            _FORMAT_NAMES
        ):
            raise MrzValueError(
                "detected_format must be None or one of "
                + ", ".join(sorted(_FORMAT_NAMES))
            )
        _check_flags(self.flags)
        _check_regions(self.detected_regions)
        # The one field the record stores rather than only checks: a frozen
        # dataclass cannot be reassigned, and a mapping handed in can still
        # be emptied by whoever kept it, so the record keeps a read-only
        # copy of its own rather than trusting the caller's.
        object.__setattr__(
            self, "stage_timings", _check_stage_timings(self.stage_timings)
        )


def _check_document_type(document_type: object) -> None:
    """Refuse ``document_type`` unless it is ``None`` or a non-empty string.

    **No vocabulary is imposed on it here, and that is the decision.**  The
    officer-facing selector (F6) names passports, visas, national IDs and
    permits, while Part 3's table names three *zone shapes*, and a tier that
    had to speak both would hold a mapping the project has no source for and
    would refuse a caller's own word for their own document.  So the shape is
    checked and the name is carried, and what a claim is compared against is
    a later task's question rather than this one's.
    """
    if document_type is not None and (
        not isinstance(document_type, str) or not document_type
    ):
        raise MrzValueError(
            "document_type must be None or a non-empty string, not "
            f"{type(document_type).__name__}"
        )


def _check_reference_date(reference_date: object) -> None:
    """Refuse ``reference_date`` unless it is ``None`` or a date.

    ``None`` is legal here because no rule in this module reads one: it is the
    caller saying they injected no day, and a date rule asked against it
    refuses on :func:`~app.pipeline.tier0.dates._as_day`'s reasoning rather
    than reading the clock for a substitute.  **A :class:`datetime.datetime`
    passes**, on the same grounds it does everywhere else: a caller holding a
    timestamp is not a caller making that mistake, and reducing it to its day
    is the rule that asks the question's business.

    A reference is refused rather than passed over on
    :func:`~app.pipeline.tier0.dates._as_day`'s grounds: a bad reference is
    never a fact about a document, so a caller who has not injected one has
    made a mistake rather than handed over a document nobody could read.
    """
    if reference_date is not None and not isinstance(
        reference_date, datetime.date
    ):
        raise MrzValueError(
            "reference_date must be None or a date, not "
            f"{type(reference_date).__name__}"
        )


def _check_digit_flag(label: str) -> tuple[str, str, str]:
    """Return ``label``'s id, sentence and printed field, or raise.

    One lookup rather than a bare subscript, on 1.9's rule: a layout naming a
    check digit this table does not hold would otherwise escape as a bare
    ``KeyError``, and 1.9 makes :class:`MrzValueError` the single error type
    this package raises.  **The label may be quoted** -- it is a field this
    code invented rather than a thing a document printed -- and nothing else
    about the row is.
    """
    try:
        return _CHECK_DIGIT_FLAG[label]
    except KeyError:
        raise MrzValueError(
            f"{label!r} is not a printed check digit this project has a flag for"
        ) from None


def _check_digit_flags(parsed_document, lines) -> tuple[EvidenceFlag, ...]:
    """Return one flag per failing printed check digit, in printed order.

    6.2's conversion, and it reads Part 4 and Parts 1 to 3 rather than
    judging anything.  The verdict and both of its digits come off
    :attr:`~app.pipeline.tier0.td3.MrzDocument.check_digit_results`, which
    :func:`~app.pipeline.tier0.mrz.check_digit_results` filled in, and the
    region comes off :func:`~app.pipeline.tier0.mrz_region.field_regions`,
    which boxes the cells
    :func:`~app.pipeline.tier0.mrz_region.cell_field` named on the lines 4.6
    kept.  **Neither half is recomputed here**, so a flag cannot disagree with
    the arithmetic or with where the ink is.

    **Only ``passed is False`` fires, and the third answer stays silent.**
    ``passed is None`` is 2.14's own case -- a field whose characters or whose
    printed digit could not be read -- and it is not evidence of a forged
    digit.  A TD1 prints filler where an unused optional data field's digit
    would be, so a third of the rows in a perfectly honest specimen are
    ``None`` and a rule that fired on them would invent a mismatch on every
    identity card this project reads.  ``passed is True`` is silence too.
    Both digits are therefore known on the firing path, which is why
    :attr:`~app.risk.flags.EvidenceFlag.expected` and
    :attr:`~app.risk.flags.EvidenceFlag.found` carry no ``"unreadable"`` case.

    **One flag per failing field, and never a merged list.**  A document whose
    composite was rebuilt has two or three failures at once, and an officer is
    owed each of them separately: the same id can appear twice in one
    screening's flag list with two different fields and two different boxes,
    and that is the honest reading rather than a deduplicated summary.

    **The weight band is ``high`` and the two numbers are both ``1.0``,
    because there is nothing here to estimate.**  The digit was computed from
    the same characters the verdict compares, so the finding is as strong and
    as sure as it can be; a soft score would imply a threshold this package
    has no source for.  **The band is a name and not a number** -- what a
    finding weighs belongs to 7.1's weightset, and whether it overrides the
    score is a different question this function does not answer.  **6.5 has
    answered it and the answer is yes**, so a failed printed check digit is a
    hard fail -- read off :data:`_CHECK_DIGIT_HARD_FAIL_IDS` beside the
    sentence it belongs to, which is why nothing here touches
    :attr:`TierResult.hard_failed`.

    **A field with no box is a flag with no region, and not a dropped flag.**
    4.12 says a field no cell names is absent from the answer, because a
    merged cut left its cells inside a neighbour's box; the finding is still
    true and 23.6 is what lists it honestly.
    """
    regions = mrz_region.field_regions(parsed_document, lines)
    flags = []
    for result in parsed_document.check_digit_results:
        if result.passed is not False:
            continue
        flag_id, sentence, printed_field = _check_digit_flag(result.field)
        flags.append(
            EvidenceFlag(
                id=flag_id,
                tier=0,
                label=sentence,
                weight_band="high",
                value=1.0,
                confidence=1.0,
                region=regions.get(printed_field),
                expected=str(result.expected),
                found=str(result.found),
                reason=f"expected {result.expected}, found {result.found}",
                source_module="app.pipeline.tier0.mrz",
                field=result.field,
            )
        )
    return tuple(flags)


def _check_watchlist(watchlist: object) -> None:
    """Refuse ``watchlist`` unless it is ``None`` or a :class:`Watchlist`.

    **The abstract base class is the check, and a duck-typed object is
    refused.**  5.9 made the seam an ABC so a connector that forgot
    ``lookup`` could not be built at all; this is the other end of the same
    guarantee, where a caller hands a screening something that merely has a
    ``lookup`` attribute.  A connector whose signature differs is caught by
    the same line, and 1.9's one-error-type rule holds.

    ``None`` is legal and is the caller saying they wired no list.  **A
    screening with no list has not been cleared by one**: the same "asked
    nothing, found nothing" that :meth:`Watchlist.lookup` itself refuses to
    read as a clean document.
    """
    if watchlist is not None and not isinstance(watchlist, watchlist_seam.Watchlist):
        raise MrzValueError(
            "watchlist must be None or a Watchlist, not "
            f"{type(watchlist).__name__}"
        )


def _check_hits(hits: object) -> None:
    """Refuse a connector's answer unless it is a list of :class:`WatchlistHit`.

    **A connector's own bug is refused here rather than half-read.**  5.9
    declares the return shape and says a return of any other shape is the
    connector's bug; ``None``, a bare hit, a tuple and a list of dictionaries
    would each otherwise become an ``AttributeError`` on the first hit's
    ``kind``, several lines into a screening, naming a line of this module
    rather than the connector that answered wrongly.
    """
    if not isinstance(hits, list) or not all(
        isinstance(hit, watchlist_seam.WatchlistHit) for hit in hits
    ):
        raise MrzValueError(
            "a watchlist's answer must be a list of WatchlistHit records"
        )


def _watchlist_row(kind: str) -> tuple[str, str, str, str | None, bool]:
    """Return ``kind``'s id, sentence, band, field and hard-fail row, or raise.

    One lookup rather than a bare subscript, for :func:`_check_digit_flag`'s
    reason: 1.9 makes :class:`MrzValueError` the single error type this
    package raises, and a kind this table lacks is a loud failure rather than
    a finding that silently never fires.
    """
    try:
        return _WATCHLIST_FLAG[kind]
    except KeyError:
        raise MrzValueError(
            f"{kind!r} is not a kind of list entry this project has a flag for"
        ) from None


def _watchlist_reason(hit: watchlist_seam.WatchlistHit) -> str:
    """Return the sentence naming which entry matched on which key.

    **Built here from the hit's own two closed vocabularies and from nothing
    else** -- :attr:`~app.risk.watchlist.WatchlistHit.kind` and
    :attr:`~app.risk.watchlist.WatchlistHit.matched_on` -- which is ``D13``'s
    requirement that the prose on a flag is written in this project rather
    than taken from a connector.  A live feed's own free text is exactly where
    identity data would ride in, and ``reason`` reaches the dashboard, the log
    and the officer's screen.

    **The entry id is deliberately not in it.**  ``entry_id`` is a guard and
    not a guarantee -- 5.9's own test admits that a one-word name passes the
    character check -- so a hit's row reference stays on the record that
    carries it and off the prose an officer reads.
    """
    return f"an entry of kind {hit.kind} matched on {hit.matched_on}"


def _lookup_keys(
    parsed_document: document.MrzDocument, reference_date: datetime.date | None
) -> dict[str, str | datetime.date | None]:
    """Return the three values a list is asked about, under the three key names.

    **A mapping rather than three arguments**, so the keys are keyword-only by
    construction and a fourth key could not be added to a call that
    :meth:`Watchlist.lookup` does not accept: 5.9 made all three keyword-only
    because a name passed where a document number belongs would be answered
    with a clean miss rather than a failure.

    **Nothing here is tidied, case-folded, stripped of filler or upper-cased.**
    The values are what the document printed, on 5.11's own ground -- a lookup
    table is not a matcher, and a runner that tidied them would be a second
    place for a list's spelling to disagree with the document's.

    **A date of birth is 5.6's reading and never the six printed characters**,
    because :meth:`Watchlist.lookup` compares a resolved
    :class:`datetime.date` and two digits have no century.  **The rule is asked
    rather than half of it called**: :func:`~app.pipeline.tier0.dates.
    dob_result` is the whole of 5.6, and the plausibility half of its answer is
    6.3's to flag rather than a reason for this module to skip a list.  So a
    document too old to be plausible is still asked about, on the day it
    prints.

    **No injected reference date means no day is asked about.**  5.6's
    century is resolved against a day this module is not allowed to read from
    the clock, so ``None`` here is a key that is not checked -- the seam's own
    answer for a value nobody could read, and not a question with a wrong
    answer.  The document number is still asked about, which is the half a
    blacklist hit comes from.
    """
    return {
        "document_number": parsed_document.document_number,
        "name": parsed_document.name,
        "dob": (
            None
            if reference_date is None
            else dates.dob_result(
                parsed_document.date_of_birth, reference_date
            ).birth
        ),
    }


def _ask_watchlist(
    watchlist: watchlist_seam.Watchlist | None,
    parsed_document: document.MrzDocument | None,
    reference_date: datetime.date | None,
) -> tuple[watchlist_seam.WatchlistHit, ...]:
    """Return the hits one list answers with, or no hits when none was asked.

    **A list is asked only when a parse was handed in.**  The three keys are
    the three values a document prints and nothing in Part 4 reads a character
    out of a cell, so with no parse every key would be ``None`` and 5.9 says a
    lookup of three ``None`` values answers ``[]`` -- a question nobody asked
    rather than a cleared document.  Spending a round trip to reach that answer
    is a live feed's latency paid for a silence, so it is not spent.

    **The connector's answer is checked before it is read**, and its errors
    are not caught: a list that is down is a list that is down, and turning
    that into an empty list of hits would report a checkpoint's outage as a
    cleared document.
    """
    if watchlist is None or parsed_document is None:
        return ()
    hits = watchlist.lookup(**_lookup_keys(parsed_document, reference_date))
    _check_hits(hits)
    return tuple(hits)


def _watchlist_flags(
    parsed_document: document.MrzDocument,
    lines,
    hits: tuple[watchlist_seam.WatchlistHit, ...],
) -> tuple[EvidenceFlag, ...]:
    """Return one flag per list hit, in the order the connector answered.

    6.4's conversion, and like 6.2's it reads a record and boxes it rather
    than judging anything: the four things a flag carries here are the table's
    row, 4.12's own box for the field the hit is about, 5.6's reading of a day
    and the hit's own two closed vocabularies.

    **One flag per entry, and never one flag for the answer.**  Two entries can
    match one document and an officer is owed both, the way 6.2 owes a separate
    flag per failing digit; and :meth:`Watchlist.lookup` promises no order, so
    the flags come back in the order the connector gave them with no
    significance read into the position.

    **The box is the field's own and is 4.12's.**  A blacklist or a stolen hit
    is found by the document number, so it is boxed over the document number's
    cells -- the abstract's "the offending field highlighted", and the same
    :func:`~app.pipeline.tier0.mrz_region.field_regions` call 6.2 makes.
    **An identity hit names no field and carries no box**, because it is about
    a name and a date of birth together and no one field is either; 23.6 is
    what lists such a finding honestly rather than dropping it.

    **``expected`` is ``None`` and ``found`` is the kind.**  The expected half
    of a watchlist comparison is the absence of this flag, which is a claim
    about the flag's own existence and has no value to print, and the found
    half is the kind the list answered with -- the only part of a hit that is
    safe to print, since it is one of three closed names.  ``entry_id`` is on
    neither, for :func:`_watchlist_reason`'s reason.

    **A list with nothing to place is a flag with no region and not a dropped
    one**, on 6.2's reasoning: 4.12 says a field no cell names is absent
    because a merged cut left its cells inside a neighbour's box, and the
    finding is still true.
    """
    if not hits:
        return ()
    regions = mrz_region.field_regions(parsed_document, lines)
    flags = []
    for hit in hits:
        flag_id, sentence, band, field_name, _hard_fail = _watchlist_row(hit.kind)
        flags.append(
            EvidenceFlag(
                id=flag_id,
                tier=0,
                label=sentence,
                weight_band=band,
                value=1.0,
                confidence=1.0,
                region=regions.get(field_name),
                expected=None,
                found=hit.kind,
                reason=_watchlist_reason(hit),
                source_module="app.risk.watchlist",
                field=field_name,
            )
        )
    return tuple(flags)


def _hard_fail_reason(flags: tuple[EvidenceFlag, ...]) -> str | None:
    """Return why this result is a hard fail, or ``None`` when nothing was.

    **The override is a property of the rule and not of the flag's weight.**
    Membership of :data:`_HARD_FAIL_IDS` is the whole test, and
    :attr:`~app.risk.flags.EvidenceFlag.weight_band` is deliberately not it:
    a stolen-document hit and a failed check digit are both ``high``, and only
    one of them overrides, so a band could not stand in for the answer even
    where it happened to agree.

    **The reason is the finding's own ``label`` and not a second string.**  A
    blacklist hit and a hard fail say the same thing, and two sentences
    describing one event is one of them able to disagree with the other on a
    later edit.  **It is therefore the flags the caller already holds** and
    not a summary of them: a reason naming a finding that is not in
    :attr:`TierResult.flags` would be an officer reading about a document
    finding the result does not carry.

    **Every hard fail is named, and the sentences are collected and sorted, so
    the answer depends on neither the family nor the order.**  A rebuilt
    composite fails two or three digits at once and an officer is owed each
    of them, and :meth:`Watchlist.lookup` promises no order at all -- so a
    hard-fail reason that read differently on two runs over the same document
    would be a reason nobody could rely on in an audit.

    **A finding that is not a hard fail is left out rather than mentioned.**
    A document on a stolen list and carrying a broken digit is one hard fail
    and not two, and naming the heavy hit beside the override would say the
    runner treats it as one.
    """
    reasons = {flag.label for flag in flags if flag.id in _HARD_FAIL_IDS}
    return "; ".join(sorted(reasons)) or None


def _check_parsed_document(parsed_document: object, detected_format) -> None:
    """Refuse ``parsed_document`` unless it is ``None`` or this page's own parse.

    **The caller's parse must be the parse of the page measured**, and the
    two are compared on format rather than trusted to agree.  4.12 reads
    :attr:`~app.pipeline.tier0.td3.MrzDocument.format` to name cells and
    :attr:`TierResult.detected_regions` is what 4.8 measured from these very
    lines, so a TD2 parse handed in front of a TD3 page would box TD2 field
    names over TD3 ink -- a highlight drawn over the wrong words, which is
    worse than no highlight because an officer reads it.  The formats are
    shape rather than identity data, so the message may name both.

    **A page with no zone refuses a parse rather than pairing one with
    nothing**, for the same reason: ``detected_format`` is ``None`` and no
    field name matches it.
    """
    if parsed_document is None:
        return
    if not isinstance(parsed_document, document.MrzDocument):
        raise MrzValueError(
            "parsed_document must be None or a parsed MrzDocument, not "
            f"{type(parsed_document).__name__}"
        )
    if parsed_document.format != detected_format:
        raise MrzValueError(
            "parsed_document is a "
            f"{parsed_document.format} and the page measured as "
            f"{detected_format}"
        )


def run_tier0(
    image,
    document_type: str | None = None,
    reference_date: datetime.date | None = None,
    parsed_document: document.MrzDocument | None = None,
    watchlist: watchlist_seam.Watchlist | None = None,
) -> TierResult:
    """Run Tier 0's measurements over ``image`` and report what they found.

    ``image`` is the working frame :func:`~app.pipeline.tier0.mrz_region.
    detect_mrz` takes -- three-channel BGR -- and the one argument this
    function cannot do without.  **A frame that is not an image is refused by
    4.1 rather than here**, on the grounds 4.1 gives: it is a caller that
    passed something that is not an image, and a second gate copying that
    judgement would be a second opinion about what an image is.

    ``document_type`` is the caller's claim about the document -- a
    non-empty string or ``None`` -- and **it does not choose a format**.
    :attr:`TierResult.detected_format` is 4.7's answer read off the zone's
    shape, so a caller who names a passport in front of a TD1 is answered
    about the TD1 the pixels hold; what a claim is compared against is a later
    task's question.

    ``reference_date`` is the :data:`~app.pipeline.tier0.dates.ReferenceDate`
    dependency, injected by whoever runs the cascade and passed on to each
    date rule rather than read from the clock here, and handed to 5.6 for 6.4
    because a list is asked about a date of birth as a resolved day.  ``None``
    means the caller injected no day, and 6.4 then asks no list about a date of
    birth rather than resolving one against a day it read for itself.

    ``parsed_document`` is the caller's own
    :class:`~app.pipeline.tier0.td3.MrzDocument` for the same page, and it is
    **how 6.2 gets its characters**: nothing in Part 4 reads a character out
    of a cell, so the runner measures a page and the caller who holds the
    parse hands it over.  ``None`` means no parse was handed in, and 6.2 then
    reports no check-digit findings -- **which is not a pass**, and is why the
    field is not defaulted to anything that could be mistaken for one.  A
    parse whose :attr:`~app.pipeline.tier0.td3.MrzDocument.format` is not the
    format the page measured is refused rather than paired, so no highlight is
    ever drawn over another format's ink.

    ``watchlist`` is the connector Tier 0 asks about this document, built on
    :class:`~app.risk.watchlist.Watchlist` and injected rather than imported:
    the runner knows the seam and nothing behind it, so 5.11's mock and a live
    feed are the same call.  **It is asked only when a parse was handed in**,
    because the three keys it takes are the three values a document prints,
    and a lookup of three ``None`` values answers nothing at all.  ``None`` is
    the caller saying no list was wired, and **no list is not a cleared
    document** any more than no parse is: the result is the measurement and
    the flags, and only a flag says anything about a document.

    A hit becomes one flag, each of the three kinds carrying the severity
    :data:`_WATCHLIST_FLAG` holds.  **A blacklist hit sets
    :attr:`TierResult.hard_failed`**, because the abstract names a blacklist
    match beside a broken checksum as the finding that exits straight to High
    Risk; a stolen-document hit is heavy-weighted and does not, because a
    stolen document is a fact about a document rather than about the person
    holding it.  **A failed printed check digit sets it too**, for the first
    of the abstract's two named findings: 6.5 reads the override off
    :data:`_HARD_FAIL_IDS`, which every family's own table feeds, so no rule
    and no family sets it and nothing is a hard fail by being assembled here.

    Returns:
        A :class:`TierResult`: the findings, the hard-fail override and its
        reason, the format the zone was measured as, and one polygon per
        detected line, plus :attr:`TierResult.stage_timings` -- the four
        durations in seconds under :data:`STAGE_NAMES`, ``total`` being the
        one the abstract's sub-0.3 s target is about.  **A page with no zone
        on it is a result and not a refusal**: the format is ``None``, the
        regions are empty and the flags are the empty tuple.  **A run that
        raises produces no result and so no timings at all**: how long a
        refusal took is not something the caller can read off anything this
        module hands back, and a record claiming otherwise would be a number
        nobody measured.

    Raises:
        MrzValueError: if ``document_type`` is neither ``None`` nor a
            non-empty string, or if ``reference_date`` is neither ``None`` nor
            a :class:`datetime.date`, or if ``parsed_document`` is neither
            ``None`` nor a parse of the format this page measured, or if
            ``watchlist`` is neither ``None`` nor a
            :class:`~app.risk.watchlist.Watchlist`, or if a connector answers
            with anything but a list of
            :class:`~app.risk.watchlist.WatchlistHit` records; and whatever the
            chain itself refuses, which is 4.1's own answer for a frame that
            is not an image.
    """
    # 6.6: the total's window opens over the refusals and not after them, so
    # the abstract's figure is for the whole call.  Each stage is then timed
    # where the cascade calls it rather than through a wrapper, which could
    # only ever time the function it was given and not this one's own order.
    started = _now()
    timings: dict[str, float] = {}
    _check_document_type(document_type)
    _check_reference_date(reference_date)
    _check_watchlist(watchlist)
    mark = _now()
    detection = mrz_region.detect_mrz(image)
    timings["detection"] = _now() - mark
    _check_parsed_document(parsed_document, detection.format)
    # Empty and not absent: a clean document, a page nobody handed a parse for
    # and a screening with no list wired all come back with no flags, and only
    # the first is a pass.  The families sit beside one another in the
    # cascade's own order -- the document's own arithmetic, then the lists it
    # is on -- and 6.3's dates go between them.
    mark = _now()
    digits = (
        ()
        if parsed_document is None
        else _check_digit_flags(parsed_document, detection.lines)
    )
    timings["check_digits"] = _now() - mark
    mark = _now()
    hits = _ask_watchlist(watchlist, parsed_document, reference_date)
    hits_flags = _watchlist_flags(parsed_document, detection.lines, hits)
    timings["watchlist"] = _now() - mark
    flags = digits + hits_flags
    # 6.5: the override is any hard-fail rule having fired and never a
    # family's own answer, so this is asked of the flags as a whole and of
    # the ids the families' tables call hard fails.  A rule that is not one
    # is left out of the sentence rather than named in it.
    hard_fail_reason = _hard_fail_reason(flags)
    timings["total"] = _now() - started
    return TierResult(
        flags=flags,
        hard_failed=hard_fail_reason is not None,
        hard_fail_reason=hard_fail_reason,
        detected_format=detection.format,
        detected_regions=detection.regions,
        stage_timings=timings,
    )
