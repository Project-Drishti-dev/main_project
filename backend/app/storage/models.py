"""The declarative ``Base`` and the tables mapped against it.

Task 8.4 asks for the declarative base and the ``Screening`` row, 8.5 asks
for the ``AuditEvent`` beside it, and 8.6 for the ``LedgerEntry`` beside
that, and 16.1 for the ``TravelerCase`` beside those, so this module is all
four.  :mod:`app.storage.db` holds the engine
and the session factory and nothing else, so a migration (8.8) has one
module to import and a repository (8.10) has one module to ask for its
mapped classes.

**A row records what was measured and decides nothing.**  Every column is one
of three kinds: something the caller handed over (``document_type``,
``filename`` and the two dimensions), something a stage wrote when it
finished (``score``, ``band``, ``mode``, ``flags``, ``quality``,
``model_versions``, ``ruleset_version``, ``summary``), or one of the two
lifecycle stamps (``created_at``, ``deleted_at``).  There is no column for
an officer's decision and none for an outcome, so what was decided lives in
Part 10's events rather than in a field of a row.

**The result columns are nullable because 11.1 hands back an id before the
analysis has run.**  ``status`` is stamped ``pending`` and the rest stay
``None`` until a stage fills them, so "created, not yet analysed" is a row
this table can hold rather than a score nobody has computed.

**Only ``id``, ``created_at`` and ``status`` are written by the ORM**, each
from a default declared here: an opaque token, the UTC clock, and the
pending status.  Every other column is written by the caller that measured
it, so nothing on a row is a claim this module makes on a stage's behalf.

**The event row records one thing that happened, and it is written to be
checked afterwards rather than read for a current answer.**  Its columns are
the two ids that say which screening and which anchoring batch the event
belongs to, the ``event_type`` naming what happened, the ``actor`` naming
which station recorded it, the ``payload`` 10.3 attaches to it, the
``record_hash`` 9.17 recomputes to find out whether the row is still the row
that was written, and the creation stamp beside it.  The officer's own choice
is one of the event types (10.6) rather than a column, so a row here records
that a choice was made without this table holding a vocabulary for it.

**The ledger row is a position in a log, and the log is only ever
extended.**  It carries the five columns the abstract's Merkle batching
describes and nothing else: where the entry sits in the chain
(``sequence``), which batch of events it commits (``batch_id``), the root
over that batch (``merkle_root``), the signature over the root
(``signature``) and when it was anchored (``anchored_at``).  There is no
``id`` here, because in a ledger the position *is* the identity, and no
``screening_id``, because only hashes reach the ledger and the association
is carried one step out through the batch.  The row is refused rather than
amended: a mapper-level guard makes an update or a delete raise, and
9.12's SQLite triggers are the second and independent half of the same
claim.

**``screenings`` is the one table a query filters by, so it is the one
table with indexes.**  8.13 filters by :attr:`Screening.band` and 8.14
reads a date range out of :attr:`Screening.created_at`, and both are reads
over every row rather than over one, so each carries an index.  Neither is
unique and neither is written by this module: ``band`` is ``None`` on a
row nothing has scored and two screenings can share an instant, so a
unique index on either column would refuse rows this table can hold.  The
other three tables are read by id, which the primary key already serves.

**The two names come from :data:`NAMING_CONVENTION` and are not written
out here.**  ``ix_screenings_created_at`` and ``ix_screenings_band`` fall
out of the convention's ``ix`` entry applied to the table and the column,
so renaming the table would rename the index with it.  8.8's migration
creates them by that name and 8.8's ``downgrade`` drops them by it, and
that pair has to name the same object on both backends.

**Nothing here imports another application package.**  ``band`` and ``mode``
are columns of text rather than of a type this project defines, because
their vocabularies belong to :mod:`app.risk.bands` and to the quality gate,
and ``event_type`` is plain text because 10.1's six names are a constants
module this one is not allowed to reach across the package to read.  7.10
walks every module in ``app/`` for a band standing beside a decision, and a
table that named the three bands beside a decision would be the mapping it is
written to catch; a table that stores the band it was handed is the record
that walk exists to protect.

**Invariants**

- :data:`Base` is the service's only declarative base, and every table is
  mapped against it.
- ``screenings`` carries exactly the sixteen columns the task names, in the
  order it names them.
- ``audit_events`` carries exactly the ten columns its tasks name, in the
  order they name them: 8.5's eight, then the ``record_salt`` and
  ``batch_index`` 10.2 added, then ``created_at``.
- ``ledger_entries`` carries exactly the five columns the task names, in the
  order it names them, and ``sequence`` is its primary key.
- ``traveler_cases`` carries exactly the three columns the task names, in the
  order it names them, and all three of them are required.
- A row can be written before the analysis has produced anything: only
  ``document_type``, ``filename``, ``image_width`` and ``image_height`` are
  required, and the nine result columns and ``deleted_at`` read back
  ``None``.
- An event names its screening, its type, the station that recorded it, a
  payload and its own hash, and all five are required.  Three columns are
  optional: ``batch_id`` and ``batch_index``, because 9.16 stamps them when
  the event is anchored and an event nobody has anchored yet is one this
  table can hold; and ``record_salt``, because a column added to a table
  that already holds rows cannot be ``NOT NULL`` -- every writer is
  :func:`~app.audit.emit.emit`, which always writes one, and a row carrying
  none is one 9.17 can only answer ``unknown`` for.
- ``screening_id`` declares no foreign key, so an event outlives the row it
  names and the trail cannot be emptied by a delete on ``screenings``.
- ``screenings`` carries exactly two indexes, ``ix_screenings_created_at``
  and ``ix_screenings_band``, both non-unique, and no other table carries
  any.
- A ledger entry is never updated and never deleted: both raise
  :class:`LedgerAppendOnlyError` before any statement reaches the database,
  and only :class:`LedgerEntry` is guarded, so the other two tables are
  unaffected.
- ``created_at`` is stamped on every row and always in UTC.
- ``sequence`` is assigned by the database and is never handed over by a
  caller, so no writer can place an entry anywhere but the end.
- ``deleted_at`` is ``None`` on a row nobody has soft-deleted, and setting it
  leaves the row readable: which reads skip it is 8.15's question, not this
  table's.
- **No column type states a maximum length.**  SQLite ignores a ``VARCHAR``
  length and PostgreSQL refuses an over-long value, so a length written here
  is a limit on one backend and a decoration on the other.  The closed
  vocabularies are the constants below and the writers' business.
- No column holds image bytes, and no column is written by anything in this
  module other than the defaults declared above: ``id``, ``created_at`` and
  ``status`` on ``screenings``, ``id`` and ``created_at`` on ``audit_events``,
  ``sequence`` and ``anchored_at`` on ``ledger_entries``, and ``id`` and
  ``created_at`` on ``traveler_cases``.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, MetaData, Text, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = [
    "AUDIT_EVENT_TABLE_NAME",
    "AuditEvent",
    "Base",
    "DEFAULT_SCREENING_STATUS",
    "LEDGER_ENTRY_TABLE_NAME",
    "LedgerAppendOnlyError",
    "LedgerEntry",
    "NAMING_CONVENTION",
    "SCREENING_MODES",
    "SCREENING_STATUSES",
    "SCREENING_TABLE_NAME",
    "Screening",
    "TRAVELER_CASE_TABLE_NAME",
    "TravelerCase",
]


#: The table this task's row lives in, named the way 9.12 names
#: ``ledger_entries``: plural, lowercase, and the name the routes and the
#: migrations will use.
SCREENING_TABLE_NAME = "screenings"

#: The table the trail lives in, named the same way and the name
#: ``GET /api/audit/{id}/verify`` will read it under.
AUDIT_EVENT_TABLE_NAME = "audit_events"

#: The table the log lives in, under the name 9.12's triggers and 9.16's
#: ``append_batch`` both name explicitly.
LEDGER_ENTRY_TABLE_NAME = "ledger_entries"

#: The table a traveler's set of documents lives in, named the same way.
TRAVELER_CASE_TABLE_NAME = "traveler_cases"

#: Deterministic constraint names, so that 8.7's indexes and 8.8's migration
#: name the same object on both backends and a ``downgrade`` can find what an
#: ``upgrade`` created.  The ``ck`` entry requires a name to be given to a
#: check constraint and raises without one: an unnamed check has no stable
#: name to be dropped by.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: The three states a screening passes through, and the three 11.1's
#: immediate id, 11.2's completed result and a cascade that could not finish
#: each need.  Frozen because a set a writer could add to would let a row
#: hold a state no stage produces, which is the reason
#: :data:`app.risk.flags.WEIGHT_BANDS` is a frozenset too.
SCREENING_STATUSES = ("pending", "completed", "failed")

#: The two readings of the image quality gate makes about how a document was
#: captured, and the two :mod:`app.schemas` already answers for over HTTP.
#: A row carries one only once the gate has run, so ``mode`` is ``None``
#: until then.
SCREENING_MODES = ("photo", "scan")

#: The status a row carries until a stage writes another.  Read out of
#: :data:`SCREENING_STATUSES` rather than spelled, so the default cannot
#: become a state the vocabulary does not hold.
DEFAULT_SCREENING_STATUS = SCREENING_STATUSES[0]


def _utc_now() -> datetime:
    """The current time, in UTC, and the only clock this module reads."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """The declarative base every table in this service is mapped against."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Screening(Base):
    """One document screened once: what arrived, what was read from it, and
    when it was soft-deleted.

    :attr:`id` is an opaque token rather than a counter, and :attr:`created_at`
    is stamped in UTC when the row is first written.  :attr:`document_type`,
    :attr:`filename`, :attr:`image_width` and :attr:`image_height` are what
    the upload carried, and they are the four columns a caller cannot write
    the row without.

    :attr:`status` starts at ``pending`` and carries one of
    :data:`SCREENING_STATUSES` thereafter; it is the lifecycle of the
    screening, never an officer's action.  :attr:`score` and :attr:`band` are
    7.14's number and 7.9's reading of it as :class:`~app.risk.engine.
    RiskResult` produces them, and :attr:`ruleset_version` is the ruleset that
    produced them, so a stored score is quoted against the ruleset it was
    made under.

    :attr:`mode` is the quality gate's reading of how the document was
    captured, :attr:`quality` the gate's own result, :attr:`flags` the
    findings the cascade produced and :attr:`model_versions` the versions of
    the modules that were asked -- none of them written by this module.
    :attr:`summary` is the officer-facing narrative, and :attr:`deleted_at`
    the soft-delete stamp 8.15 sets.

    **Nothing here decides anything, and there is no column that could.** A
    row is the record of a measurement and of when it was made; the decision
    an officer takes on it is an event in Part 10's trail, beside the band
    rather than inside this table.
    """

    __tablename__ = SCREENING_TABLE_NAME

    #: An opaque token, so a screening id in a URL, an audit event or a
    #: ledger entry is not a counter a stranger can walk up.  Stored as a
    #: native ``UUID`` where the backend has one and as 32 hex characters
    #: where it does not.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    #: When the row was first written, in UTC.  Stamped by the ORM rather
    #: than asked of a caller, because 11.1 creates the row in a request that
    #: has no other use for the time.  Indexed, because 8.14 reads a date
    #: range out of this column over every row.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, index=True
    )

    #: Which kind of document the caller said this was -- a claim about the
    #: upload, checked for shape by whoever wrote the row, and never a
    #: constraint on what the cascade then reads out of the page.
    document_type: Mapped[str] = mapped_column()

    #: One of :data:`SCREENING_STATUSES`, stamped ``pending`` on insert.
    status: Mapped[str] = mapped_column(default=DEFAULT_SCREENING_STATUS)

    #: 7.14's score on the 0-100 scale, or ``None`` while no stage has
    #: produced one.
    score: Mapped[float | None]

    #: 7.9's reading of :attr:`score`, stored rather than derived again on
    #: every read so the band an officer is shown is the band that was shown.
    #: Indexed for 8.13's filter, and not unique: a band holds many rows and
    #: a row nobody has scored yet carries ``None``.
    band: Mapped[str | None] = mapped_column(index=True)

    #: The quality gate's ``photo``/``scan`` reading of the capture, or
    #: ``None`` until the gate has run.
    mode: Mapped[str | None]

    #: The name the upload arrived under.  Caller-supplied text, so it is
    #: never indexed and never leaves this table for a log or a ledger.
    filename: Mapped[str] = mapped_column()

    #: The pixel width of the uploaded image, as the quality gate read the
    #: file's header.  Two columns rather than a JSON object, so a filter
    #: or an index can name them without parsing a string.
    image_width: Mapped[int]

    #: The pixel height of the uploaded image.
    image_height: Mapped[int]

    #: The ruleset the score was produced under, or ``None`` while nothing
    #: has been scored.  Not defaulted from
    #: :data:`app.version.RULESET_VERSION`, which would claim a ruleset for a
    #: row nothing has read a document with yet.
    ruleset_version: Mapped[str | None]

    #: Module name to the version that answered for it, or ``None`` while no
    #: model has been asked.
    model_versions: Mapped[dict[str, str] | None] = mapped_column(JSON)

    #: The quality gate's own result -- its checks, its readings and its
    #: verdict -- as the gate wrote it.
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    #: The findings the cascade produced, one object per flag, in the order
    #: the rules emitted them.  The rows of a scoring run, kept beside the
    #: score they produced rather than recomputed from it.
    flags: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    #: The officer-facing narrative, or ``None`` while none has been written.
    summary: Mapped[str | None] = mapped_column(Text)

    #: When the row was soft-deleted, or ``None`` while it is live.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """One thing that happened to one screening, written once.

    A row here is not read for a current answer the way a
    :class:`Screening` row is: it is read back to find out *whether the
    record is still the record that was written*, which is what
    :attr:`record_hash` is for.  That is why nothing on this table is
    derived, defaulted or computed -- the row says what was recorded, and
    the checking is 9.17's.

    :attr:`screening_id` says which screening the event belongs to and
    :attr:`batch_id` which anchoring batch it was swept into, the second
    being ``None`` until 9.16 stamps it.  :attr:`event_type` names what
    happened, :attr:`actor` names the station that recorded it -- a
    configurable label (10.7) rather than an identity -- and
    :attr:`payload` is the detail 10.3 attaches, as a JSON object rather
    than a string, so a hash over it is taken over one canonical spelling.

    :attr:`id` is an opaque token on ``Screening``'s reasoning -- 11.1
    answers with a ``screening_id`` and an ``audit_id`` together -- and
    :attr:`created_at` is stamped in UTC by the same clock.

    **There is no foreign key from the event to the screening, and that is
    the load-bearing decision here.**  A referential constraint would make
    the trail's survival depend on a mutable table: a screening deleted
    outright would take its events with it, or block the delete, and
    9.17's answer for an event whose screening is gone should be
    ``verified`` -- the row is the row that was written -- rather than
    unanswerable.  A constraint would also be a guarantee on one backend
    only: SQLite does not enforce foreign keys unless a pragma asks it to,
    so a declared key reads as protection on PostgreSQL and as a comment
    on SQLite, which is the same "a limit on one backend and a decoration
    on the other" argument :attr:`Screening.filename` is spared by.  The
    association is real and is carried by the value, the way a batch id is
    carried on the event it was anchored with.
    """

    __tablename__ = AUDIT_EVENT_TABLE_NAME

    #: An opaque token, so an ``audit_id`` beside a ``screening_id`` in
    #: 11.1's answer is not a counter a stranger can walk up.  Stored as a
    #: native ``UUID`` where the backend has one and as 32 hex characters
    #: where it does not.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    #: Which screening this happened to.  Required, because 10.1's six
    #: event types are all about a screening and 24.8's audit view is
    #: reached by a screening id.  A plain ``Uuid`` column and no foreign
    #: key -- see the class docstring.
    screening_id: Mapped[uuid.UUID] = mapped_column()

    #: Which anchoring batch 9.16 swept this event into, or ``None`` while
    #: the event is unanchored.  ``None`` is a real state and not a zero
    #: batch: it is the answer 9.17 reports as ``unknown``, because there
    #: is no root yet to walk a proof to.
    batch_id: Mapped[uuid.UUID | None]

    #: What happened, as one of 10.1's six names.  Plain text rather than
    #: an enum, and no vocabulary held beside it, because that constants
    #: module is 10.1's and this table is not where a seventh name would be
    #: caught.  The writer (10.2) is what refuses a name outside it.
    event_type: Mapped[str] = mapped_column()

    #: Which station recorded it -- a configured label and never a person,
    #: a session or a credential (10.7).  Required, so that an event
    #: nobody recorded under cannot be written at all.
    actor: Mapped[str] = mapped_column()

    #: What the event carries, as an object rather than a string, so the
    #: hash 9.3 takes over it is over one spelling of a structure.  An
    #: event with nothing to add writes ``{}``, deliberately -- the
    #: ``None``-versus-``{}`` distinction 8.4 holds for the screening's
    #: JSON columns is the same one, and here ``{}`` is the honest "nothing
    #: beyond the type and the actor" rather than an absent value.
    #:
    #: ``none_as_null`` is what makes the required-ness real rather than
    #: declared.  Measured: with a plain ``JSON`` column, a ``None`` payload
    #: is written as the JSON literal ``null`` -- four characters of text in
    #: a ``NOT NULL`` column -- and reads back as ``None``, so the
    #: constraint is never exercised and an absent payload becomes a third
    #: spelling beside ``{}`` for 9.3 to hash.  With it, a ``None`` payload
    #: is SQL ``NULL`` and the column refuses it.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(none_as_null=True))

    #: The digest 10.2 wrote over this record, as hex.  Required, because
    #: 10.2 is the only function that creates events and it hashes before
    #: it persists, so a row with no hash is not a state this table can
    #: hold.  It is stored, not computed: nothing here recomputes it, so
    #: altering a row's payload leaves the hash beside it stale on purpose
    #: and 9.17 is what notices.
    record_hash: Mapped[str] = mapped_column()

    #: The salt 9.4 generated for this row's own record, as 32 lowercase hex
    #: -- the spelling :attr:`SaltedRecord.salt_hex` writes.  Stored beside
    #: the digest rather than derived from it, so the digest can be
    #: recomputed without the writer that took it.  Optional, because a
    #: column added to a table that already holds rows cannot be
    #: ``NOT NULL``; every writer is
    #: :func:`~app.audit.emit.emit`, and a row carrying none has no digest
    #: 9.17 can recompute, so it answers ``unknown``.
    record_salt: Mapped[str | None]

    #: Where this event sits among the events 9.16 anchored it with, counted
    #: from zero within its own batch and ``None`` while no batch has claimed
    #: it.  Written by :func:`~app.ledger.anchoring.anchor_batch`, which is
    #: what cuts the run into batches and therefore what knows the order --
    #: 9.17 used to be handed that order by its caller (``D62``), and the
    #: same events in another order do not walk to the anchored root.
    batch_index: Mapped[int | None]

    #: When the row was first written, in UTC, by the same clock and with
    #: the same SQLite-has-no-``tzinfo`` round trip as
    #: :attr:`Screening.created_at`.  Last here because the task's order is
    #: the order, and the two columns 10.2 added belong to the commitment
    #: rather than to the clock.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )


class LedgerAppendOnlyError(RuntimeError):
    """Raised when a ledger entry is amended or removed.

    The refusal belongs to the service rather than to the database, so it is
    a plain :class:`RuntimeError` and not a
    :class:`~sqlalchemy.exc.SQLAlchemyError`: 9.12's triggers refuse the
    same two operations from the other side, and a caller that cares about
    "the ledger said no" rather than about which layer said it has one type
    to catch whichever half answered.
    """


class LedgerEntry(Base):
    """One anchored batch, at one position in an append-only log.

    A ledger entry is not read for an answer and not amended: it is the
    statement that *at this point in the chain*, this root was committed
    under this signature.  Everything else in Part 9 hangs off those five
    columns -- 9.16 builds a tree and appends one entry per batch, 9.17
    walks a proof from an event's leaf up to :attr:`merkle_root`, and
    9.11's ``iter_batches`` walks the entries in :attr:`sequence` order.

    :attr:`sequence` is the primary key and is assigned by the database.
    A ledger entry's identity *is* its position, so there is no ``id``
    beside it and nothing a caller can hand over: 9.16 appends, and the
    chain decides where the append landed.  That is also why
    ``autoincrement`` is left on -- an entry cannot claim a position that
    has already been used, and cannot be inserted out of order.

    :attr:`batch_id` names the batch of events this entry commits and is
    the same ``Uuid`` value 9.16 stamps onto each of those events, so the
    two tables are joined by a value rather than by a key: the same
    reasoning :class:`AuditEvent` states for its ``screening_id``.  The
    entry carries no ``screening_id``, and that absence is the abstract's
    "only hashes reach the ledger" -- there is no column on this table an
    identity could be written into.

    :attr:`merkle_root` and :attr:`signature` are stored text rather than
    binary.  Both are hex, the spelling :attr:`AuditEvent.record_hash` is
    written in, so the whole log is text on both backends and no table in
    this module carries a binary column for anything to arrive in.

    :attr:`anchored_at` is the third lifecycle stamp this module keeps, on
    the same UTC clock as the other two, and the second column the ORM
    writes on this table.

    **An entry is only ever added.**  :attr:`sequence` moves, a root moves
    and a signature moves, and a row that has been anchored cannot be
    un-anchored, because a ledger that can be rewritten cannot prove
    anything about what it once said.  The refusal is enforced here at the
    mapper and, independently, by 9.12's SQLite triggers; the two are
    separate mechanisms on purpose, since this one is the service's own
    rule and that one is the database's.
    """

    __tablename__ = LEDGER_ENTRY_TABLE_NAME

    #: Where this entry sits in the chain, and the table's primary key.
    #: An autoincrementing integer, so the position is the database's to
    #: give and no caller can write one, reuse one, or write one out of
    #: order.  ``Integer`` rather than ``BigInteger``: at the abstract's
    #: batching rate this reaches 2^31 in longer than any deployment
    #: outlives, and a wider column would be a claim about scale nothing
    #: here measures.
    sequence: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    #: Which batch of events this entry commits, as the same ``Uuid`` value
    #: 9.16 stamps on each of the events it swept up.  Required, and with
    #: no foreign key to the events: the association is carried by the
    #: value, on :class:`AuditEvent`'s reasoning.
    batch_id: Mapped[uuid.UUID] = mapped_column()

    #: The root of the Merkle tree over that batch, as hex.  Stored, never
    #: computed: 9.6 builds it and 9.17 compares against it, and a column
    #: that recomputed would have nothing left to disagree with.
    merkle_root: Mapped[str] = mapped_column()

    #: 9.13's signature over :attr:`merkle_root`, as hex.  Text rather than
    #: ``LargeBinary`` for the reason :attr:`AuditEvent.record_hash` is
    #: text: the log is readable as text on both backends and this module
    #: holds no binary column.
    signature: Mapped[str] = mapped_column()

    #: When the batch was anchored, in UTC, by the same clock as the two
    #: other tables' stamps and with the same SQLite-has-no-``tzinfo``
    #: round trip.
    anchored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )


@event.listens_for(LedgerEntry, "before_update")
def _refuse_to_amend_a_ledger_entry(
    mapper: Any, connection: Any, target: LedgerEntry
) -> None:
    """Refuse an update to a row of :class:`LedgerEntry`.

    :param mapper: the mapper that fired.  Unused, and named because the
        event passes it.
    :param connection: the connection the flush would have used.  Unused:
        nothing is written and no statement reaches the database.
    :param target: the persistent entry the caller amended.
    :returns: nothing.
    :raises LedgerAppendOnlyError: always.

    Fires on the flush rather than on the attribute assignment, so the
    refusal lands where a caller commits rather than where it reaches for
    a field.  A commit that changes nothing emits no ``UPDATE`` and so
    raises nothing, which is the same answer the database gives: there is
    no statement to refuse.
    """
    raise LedgerAppendOnlyError(
        f"{LEDGER_ENTRY_TABLE_NAME} is append-only: entry "
        f"{target.sequence} cannot be updated"
    )


@event.listens_for(LedgerEntry, "before_delete")
def _refuse_to_remove_a_ledger_entry(
    mapper: Any, connection: Any, target: LedgerEntry
) -> None:
    """Refuse a delete of a row of :class:`LedgerEntry`.

    :param mapper: the mapper that fired.  Unused, and named because the
        event passes it.
    :param connection: the connection the flush would have used.  Unused:
        nothing is written and no statement reaches the database.
    :param target: the persistent entry the caller asked to remove.
    :returns: nothing.
    :raises LedgerAppendOnlyError: always.

    **Removing an entry is as much a rewrite as amending one**, and 9.12's
    triggers reject the two operations together, so the ORM half refuses
    them together too.  The task's verify asks only for the update, and the
    delete is here because "append-only" is the word the two halves of that
    claim have to agree on.
    """
    raise LedgerAppendOnlyError(
        f"{LEDGER_ENTRY_TABLE_NAME} is append-only: entry "
        f"{target.sequence} cannot be deleted"
    )


class TravelerCase(Base):
    """One traveler's set of documents, named by the officer who grouped them.

    :param id: an opaque token, defaulted by the ORM.
    :param created_at: a UTC stamp, defaulted by the ORM.
    :param label: what the officer called the group; required.

    Carries no match result and no verdict: those are ``crossdoc`` flags in
    Part 16's stream, so a case that agrees and a case that disagrees are the
    same three columns.
    """

    __tablename__ = TRAVELER_CASE_TABLE_NAME

    #: An opaque token, on :attr:`Screening.id`'s reasoning: a case id is
    #: named beside a screening, and neither should be a counter a stranger
    #: can walk up.  Stored as a native ``UUID`` where the backend has one and
    #: as 32 hex characters where it does not.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    #: When the case was opened, in UTC, on the same clock as the other three
    #: tables' stamps.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )

    #: What the officer called this group of documents.  Required, so that a
    #: case is always findable by name, and never a maximum length: a limit
    #: written on the column is a limit on PostgreSQL and a decoration on
    #: SQLite.  Caller-supplied text, so -- like
    #: :attr:`Screening.filename` -- it is never indexed and never leaves this
    #: table for a log or a ledger.
    label: Mapped[str] = mapped_column()
