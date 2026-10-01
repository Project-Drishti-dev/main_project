"""The watchlist seam: what Tier 0 asks a list, and what a hit may carry.

Tier 0 asks one question -- is this document or this person on a list -- and
this module is the seam it goes through, so the mock of 5.11 can answer it
now and a live stolen-document or blacklist connector can answer it later.

**A hit is a list entry, not the identity that matched it.**  ``lookup`` takes
the three identity values a document prints, and what comes back names the
entry, the kind of entry and which of the three arguments matched -- never the
value itself.  :class:`WatchlistHit` has no field a matched number, name or
date of birth could be written into, and :meth:`Watchlist.lookup` says so to
every implementer.  That is the whole point of the shape: 6.4 turns a hit into
an :class:`~app.risk.flags.EvidenceFlag`, whose ``reason`` is prose, and prose
reaches the dashboard, the log and the officer's screen.  **The record is the
last place a connector can keep a match**, so it keeps none.

**The three kinds are the three ``WATCHLIST_`` ids, one for one.**  A
blacklisted document number, a number recorded as stolen and an identity
screened here are three different findings with three different weights, and
:data:`HIT_KINDS` is where that list is written down.  Which id a kind becomes
is 6.4's question, and a kind that is not one of the three is refused here
rather than passed on as an unlabelled hit.

**A kind is matched on the argument it is about, and the record holds that
too.**  A blacklisted or stolen entry is matched on its document number and an
identity-seen entry on the name and date of birth, so
:data:`MATCHED_ON` is a second of the same claim and the pairing between the
two fields is refused when it does not hold.  A caller can therefore say
*which* question a list answered without being handed the answer.

**No argument has a default and all three are keyword-only.**  The three are
identity values, two of them are strings, and a caller who passed a name where
a document number belongs would be told *no list entry matched* rather than
failing: a false negative at a checkpoint, reported as a clean document.  So
the order carries no meaning (all three are keyword-only) and a value a
caller could not read is passed as ``None`` rather than left out, which is a
key that is not checked rather than a key that was forgotten.  **Nothing is
refused for being unreadable**, on the same grounds as ``dates``: a document
whose date of birth nobody could read has not been cleared, and the list that
is asked about the keys that were readable answers about itself.

**No argument is a date and no hit carries one.**  A connector that filtered
on "still listed today" would make a screening's outcome depend on when it
ran, which is the artefact 5.4's reference date refuses; and what a previous
outcome is worth is 7.13's calibration question rather than a list's field.

**This is an abstract base class and not a duck-typed contract**, so a
connector that forgets :meth:`Watchlist.lookup` cannot be instantiated at all
and the failure is at the wiring rather than at the first screening.
"""

import abc
import dataclasses
import datetime
import string

__all__ = [
    "BLACKLIST",
    "DOCUMENT_NUMBER",
    "ENTRY_ID_CHARACTERS",
    "HIT_KINDS",
    "IDENTITY",
    "IDENTITY_SEEN",
    "KEY_EACH_KIND_IS_FOUND_BY",
    "MATCHED_ON",
    "STOLEN_DOCUMENT",
    "Watchlist",
    "WatchlistHit",
    "WatchlistValueError",
]

#: The document number is on the blacklist.  The abstract's hard rule beside
#: a broken checksum, and the one kind that is a hard fail rather than a
#: weighted finding.
BLACKLIST = "blacklist"
#: The document number is recorded as stolen.  Heavy-weighted and not a hard
#: fail, because a stolen document is a fact about a document rather than about
#: the person holding it.
STOLEN_DOCUMENT = "stolen_document"
#: The name and date of birth are an identity already screened here.  **A
#: lookup hit and not a verdict**: what a previous outcome is worth is 7.13's
#: question, and this record carries no date it could be decayed by.
IDENTITY_SEEN = "identity_seen"

#: The three kinds of entry a hit can name, and the only three
#: :class:`WatchlistHit` accepts.  Frozen because this set is read by 6.4 and a
#: set a caller could add to would let a list answer with a kind nothing
#: downstream has a weight for.
HIT_KINDS = frozenset({BLACKLIST, STOLEN_DOCUMENT, IDENTITY_SEEN})

#: The hit came from the document number, which is how both
#: :data:`BLACKLIST` and :data:`STOLEN_DOCUMENT` entries are found.
DOCUMENT_NUMBER = "document_number"
#: The hit came from the name and date of birth together, which is how
#: :data:`IDENTITY_SEEN` entries are found.
IDENTITY = "identity"

#: The two keys a hit can have come from, and the only two
#: :class:`WatchlistHit` accepts.
MATCHED_ON = frozenset({DOCUMENT_NUMBER, IDENTITY})

#: The characters an :attr:`WatchlistHit.entry_id` may be written in.  An entry
#: id names a row in a list, so it is a token and not text: the check keeps a
#: multi-word value -- the shape every name on a document has -- out of the one
#: string field this record has.
ENTRY_ID_CHARACTERS = frozenset(string.ascii_letters + string.digits + "_-")

#: The one :attr:`WatchlistHit.matched_on` each kind is reached by, so the
#: pairing between the two fields is written down once and a caller reading
#: either one knows what the other says.
KEY_EACH_KIND_IS_FOUND_BY = {
    BLACKLIST: DOCUMENT_NUMBER,
    STOLEN_DOCUMENT: DOCUMENT_NUMBER,
    IDENTITY_SEEN: IDENTITY,
}


class WatchlistValueError(ValueError):
    """Raised when a field of a :class:`WatchlistHit` is not well formed.

    A ``ValueError``, so a caller already catching ``ValueError`` around the
    code that reads a list keeps working.

    **A message names the field that was broken and never repeats its value.**
    This is the module where a value is most likely to be identity data rather
    than a rule that was miscoded, and a name quoted back in a traceback is a
    name in a log.
    """


def _check_member(value: object, members: frozenset[str], name: str) -> str:
    """Return ``value`` if it is one of ``members``, or refuse it.

    The type is tested before the membership so an unhashable value is a
    refusal of this record's own shape rather than a ``TypeError`` from the
    lookup.
    """
    if not isinstance(value, str) or value not in members:
        raise WatchlistValueError(
            f"{name} must be one of " + ", ".join(sorted(members))
        )
    return value


def _check_entry_id(value: object) -> None:
    """Refuse ``value`` unless it is a non-empty token.

    **This is a guard and not a guarantee.**  A name is refused because the
    ones this system reads carry a separator, but a single-token name would
    pass.  What actually keeps identity data out is that
    :class:`WatchlistHit` has no field for a matched value and
    :meth:`Watchlist.lookup` tells an implementer not to invent one; the check
    here is what stops the obvious mistake at the point it is made.
    """
    if not isinstance(value, str) or not value:
        raise WatchlistValueError("entry_id must be a non-empty string")
    if not set(value) <= ENTRY_ID_CHARACTERS:
        raise WatchlistValueError("entry_id must be a token of letters, digits, '_' or '-'")


@dataclasses.dataclass(frozen=True)
class WatchlistHit:
    """One list entry the three values of a document matched.

    :attr:`kind` is one of :data:`HIT_KINDS`, :attr:`matched_on` is one of
    :data:`MATCHED_ON` and says which of the three arguments found this entry,
    and :attr:`entry_id` names the row in the list.  **None of the three is the
    value that matched**, so a hit can be counted, logged, put in a flag's
    ``reason`` and shown to an officer without carrying a document number, a
    name or a date of birth with it.

    The pairing is the invariant worth holding: :data:`BLACKLIST` and
    :data:`STOLEN_DOCUMENT` are found by :data:`DOCUMENT_NUMBER` and
    :data:`IDENTITY_SEEN` by :data:`IDENTITY`, so a hit that says one thing
    about its entry and another about its key is refused rather than passed to
    6.4.

    **Frozen, and carrying no public method**, for the reason
    :class:`~app.risk.flags.EvidenceFlag`,
    :class:`~app.pipeline.tier0.dates.ExpiryResult` and
    :class:`~app.pipeline.tier0.td3.MrzDocument` are: a method here would be a
    second answer about what matched, and it could disagree with the entry the
    record was built from.
    """

    kind: str
    entry_id: str
    matched_on: str

    def __post_init__(self) -> None:
        """Check the three fields go together, assign nothing, and return ``None``."""
        _check_member(self.kind, HIT_KINDS, "kind")
        _check_entry_id(self.entry_id)
        _check_member(self.matched_on, MATCHED_ON, "matched_on")
        if KEY_EACH_KIND_IS_FOUND_BY[self.kind] != self.matched_on:
            raise WatchlistValueError(
                f"a {self.kind} entry is found by "
                f"{KEY_EACH_KIND_IS_FOUND_BY[self.kind]}"
            )


class Watchlist(abc.ABC):
    """The one question Tier 0 asks a list, and the shape of its answer.

    :meth:`lookup` is the whole interface.  A connector is anything that
    implements it, and :class:`Watchlist` is what makes that checkable: a
    subclass that omits :meth:`lookup` cannot be instantiated, so a wiring
    mistake is a ``TypeError`` at construction rather than an ``AttributeError``
    at the first document.
    """

    @abc.abstractmethod
    def lookup(
        self,
        *,
        document_number: str | None,
        name: str | None,
        dob: datetime.date | None,
    ) -> list[WatchlistHit]:
        """Return every list entry the three values match, as
        :class:`WatchlistHit` records.

        ``document_number`` and ``name`` are the values the document printed
        and ``dob`` is the date of birth with its century already resolved by
        5.6, or ``None`` where a field could not be read.  **All three are
        keyword-only and required, and none has a default**: two of them are
        strings, so a positional call could pair a name with a document number
        and be answered with a clean miss rather than a failure, and an omitted
        key is a question nobody asked rather than a question with no answer.
        Pass ``None`` for a field the document does not give.

        ``dob`` is a resolved :class:`datetime.date` and not the six printed
        characters, so a mock and a live connector compare the same day rather
        than each resolving two digits against a reference of their own.

        **A key that is ``None`` is not checked and is not a hit**, and a
        lookup of three ``None`` values answers ``[]``: nothing was asked, so
        nothing was found, and that is not the same as a document cleared.

        **No order is promised and none should be read.**  Severity is the
        :attr:`~WatchlistHit.kind` and not the position in this list, and 6.4
        turns each hit into its own flag rather than reading the first one as
        the serious one.

        **What an implementation must not do:** write the value it matched on
        into the hit, into the entry id, or into a string of its own.  The
        three arguments are identity data, and this is the last place in the
        pipeline where a match is in hand; ``tasks.md`` bans identity data from
        logs and from the ledger, and a record that cannot hold it is what
        makes that hold for a connector nobody has written yet.

        Returns:
            A ``list`` of :class:`WatchlistHit`, one per matching entry and
            empty when nothing matched.  A return of any other shape is a
            connector's own bug: the list is what lets 6.4 emit one flag per
            entry instead of merging them.
        """
        raise NotImplementedError
