"""``ScreeningRepository``: the one way in to the ``screenings`` table.

8.10 asks for ``create(...)``, 8.11 to 8.14 for the reads beside it, 8.15
for the delete and 11.3 for the one read that composes them, so
this module is that object and nothing else.  It builds no engine, opens no
engine of its own, and declares no table: :mod:`app.storage.db` owns the
engine and the session factory, and :mod:`app.storage.models` owns the row.
What lives here is the handful of statements a caller would otherwise write
the same way in a route, a worker and a test.

**The repository is handed its sessions, and that is the whole decision
here.**  :data:`app.storage.db.SessionLocal` is bound to whatever
``DATABASE_URL`` said when the module was first imported, so a repository
that reached for it would be pinned to the process's start-up configuration:
a test could not point it at a temporary file, and 8.9's round trip -- which
migrates a file and then reads it back -- would be a claim about a database
the repository cannot write to.  Taking the factory as an argument is what
makes the one database D41 speaks about, the migrated one and the served
one, the same database in a request and in a test.

**A returned row is a stored row, and that is what the commit is for.**  The
row is added and committed inside one ``with`` block, so a write that fails
raises out of :meth:`~ScreeningRepository.create` with nothing returned and
nothing half-written; a repository that returned the instance before the
commit would hand a caller an object that no query would ever find.

**The returned row is readable after the block closes, because
:func:`app.storage.db.build_session_factory` sets ``expire_on_commit`` to
``False`` (``D36``).**  The session opens one, writes, commits and closes
inside the call, so the instance the caller holds is detached by the time it
is returned; with the default every attribute of it would raise
``DetachedInstanceError`` on the next read.  This is a precondition on the
factory rather than a rule enforced here, and it is stated because a caller
handing a plain ``sessionmaker()`` gets a detached, unreadable row rather
than an error.

**``create`` writes the four columns an upload carried and nothing else.**
``mode``, ``ruleset_version``, ``model_versions``, ``quality`` and ``flags``
are the columns a stage fills in once it has run, and 11.1 asks this method
for an id *before* the analysis has happened; taking them as arguments now
would be a call shape written for a caller that does not exist yet.  The
three ORM defaults -- ``id``, ``created_at`` and ``status`` -- are the
model's, and this module sets none of them.

**Nothing here validates the four arguments.**  A caller reaches
:meth:`~ScreeningRepository.create` from 11.1's route, where the upload has
already been checked by a schema, so a second set of rules here would be a
second answer to the same question and could disagree with the first.  The
row's own constraints are the table's, and they are enforced by the
database, not by this method.

**Absence is an answer and never a raise.**  :meth:`ScreeningRepository.get`
returns ``None`` for an id no row carries, because a screening id reaches
this table from a URL and from a queue where "no such row" is an ordinary
outcome rather than a failure; a method that raised would push a
``try``/``except`` onto every caller and hide a genuine fault in the same
place.  It takes a :class:`uuid.UUID`, the type the primary key column
holds, and coerces nothing: a string id is parsed once at the HTTP boundary
that received it, which is the same rule ``D19`` applied to a list being
asked with what the document printed.

**A page is rows and the total together, and a page past the end is empty.**
:meth:`ScreeningRepository.list` returns a :class:`ScreeningPage` rather than
a bare list, because a count is half of every answer 11.3's route and 24.3's
table need and a bare list would make the caller issue a second query for it.
It carries the bounds it was given beside the rows they selected, so a caller
does not have to remember what it asked for.  An ``offset`` beyond the last
row is an empty page carrying the true total, on :meth:`get`'s reasoning that
a question with no rows left is an answer rather than a fault; a *negative*
``offset`` and a ``limit`` below one are refused instead, because those
describe no page at all and silently clamping them would answer with a page
the caller did not ask for.

**A page has one order, and it is the one the index already serves.**  Rows
come back by ``created_at`` then ``id``, which is a total order rather than a
partial one: two screenings can share an instant, and a partial order would
let a row appear on two pages or on none.  :meth:`list_by_band` is a filter
added to :meth:`list`'s statement rather than a second way to spell it, so
the order, the bounds and the total are written once and reached twice.

**A band is a value a stage wrote, and this module neither knows the
vocabulary nor refuses one.**  ``band`` is compared as it was handed, with no
check against :mod:`app.risk.bands`: the filter answers what is stored, so a
name this project has not used yet is an empty page rather than a fault, and
a vocabulary held here would be the second one 7.10's walk exists to catch.
``band`` is nullable and 11.1 creates a row before any stage has run, so
:meth:`list_by_band` accepts ``None`` and answers the rows nothing has scored.

**A range answers rows, not a page, and a page is what a window is for.**
:meth:`list_by_date_range` and :meth:`list_by_document_type` take no
``offset`` or ``limit`` and answer a tuple: neither was given a window, and a
:class:`ScreeningPage` carrying bounds the caller never chose would be a claim
about a page nobody asked for.  Both are reached through
:meth:`ScreeningRepository._rows`, which holds the same order as
:meth:`_page`, so a caller composing these reads with the paged ones gets one
order rather than two.

**A range's two ends are inclusive, and either one may be open.**
``created_at`` is stamped to the microsecond, so an exclusive end would
silently drop the last row of whatever period was asked for, and the drop
would look like a row that was never screened.  ``None`` means that end is
open, which is how "everything since" and "everything up to" are asked; both
ends open name no range at all and are refused, on :meth:`list`'s reasoning
that a bound describing nothing is a caller mistake rather than an empty
answer, with :meth:`list` already the way to ask for every row.

**A range is in UTC, and this module says so rather than assuming it.**  The
ORM stamps ``created_at`` in UTC and SQLite reads it back with no ``tzinfo``,
so a bound is converted to UTC before it is bound rather than compared as it
was handed: SQLite's ``DATETIME`` drops the offset instead of applying it,
which would turn a range given in local time into a range given in UTC.  A
bound with no timezone at all is refused instead, because against PostgreSQL's
``timestamptz`` the same comparison would be resolved against the server's
zone -- one spelling of the query meaning two instants on two backends.

**Three filters over one window are one statement, and it is written here.**
:meth:`ScreeningRepository.list_matching` adds an optional band, an optional
kind and an optional range to one :meth:`_page` call, because the reads above
are each a whole statement and a caller composing them itself would page in
Python and count a second time.  A filter left ``None`` is not applied, which
is why ``band=None`` is "no band filter" there and "the rows nothing has
scored" in :meth:`list_by_band` -- two reads differing on purpose, each
saying so.  Its refusals are :meth:`list`'s and :func:`_created_at_within`'s
rather than a third set, so one rule stays in one place.

**``document_type`` is compared as it was handed, for
:meth:`list_by_band`'s reasons.**  It is a claim the upload carried rather
than a value a stage wrote, the table does not allow it to be null, and no
vabulary is held here: a kind no row carries is an empty answer, and the
closed set of kinds is whatever :mod:`app.schemas` accepts at the boundary
that received the upload.

**A soft-deleted row is not an answer any read gives, and that rule is
written once.**  :meth:`ScreeningRepository.soft_delete` stamps
``deleted_at`` and removes nothing, so the row is still in this table and
still carries its band, its ``created_at`` and its ``document_type``.  Every
read therefore carries ``deleted_at IS NULL``, in the private
:func:`_not_soft_deleted` that :meth:`get`, :meth:`_page` and :meth:`_rows`
all reach, so a page's ``total`` counts the rows that read can see rather
than the rows the table holds.  :meth:`get` is included: a question about a
screening's *present* has one answer whether the row was never written or
was deleted, and 24.5's confirm-then-delete reads the row **before** it
deletes it, so the one read that needs it is untouched by this rule.  A
caller that genuinely needs a deleted row -- a restore, an audit context --
has no method here to reach for, and is owed a decision rather than a
bypass.

**A row is deleted once, and the second delete is absence.**
:func:`_not_soft_deleted` is also what :meth:`soft_delete` finds its row
through, so an already-deleted row is not found, answers ``None`` and keeps
the stamp it was given.  Re-stamping silently would be the one that loses
the trail: when it was deleted is a fact about the past, and who deleted it
is Part 10's event rather than a second reading of this column.

**The delete takes the instant rather than reading a clock.**  The stamp is
when the request was handled, which the route knows and this module does not;
it is keyword-only, must carry a timezone, and is converted to UTC on
:func:`_utc_bound`'s reasoning, so one spelling of the column cannot mean
two instants on two backends.

**Invariants**

- Every session this repository opens comes from the factory it was
  constructed with, and that factory is the only database it can reach.
- A method that returns a row has committed it; a method that raises has
  written nothing.
- No engine, URL, session, table or clock is created or read here, and no
  result column is ever written by this module.
- A read returns the stored row or ``None``, and never raises on absence.
- No read answers a soft-deleted row: ``get``, ``list``, ``list_by_band``,
  ``list_by_date_range`` and ``list_by_document_type`` all skip one, and a
  page's ``total`` counts the rows those reads can reach.
- ``soft_delete`` stamps one row once, leaves it in the table, and answers
  ``None`` for an id no *live* row carries.
- A page returns at most ``limit`` rows, reports the number of rows that
  matched rather than the number in the page, and orders them by
  ``created_at`` then ``id``.
- A read given no bounds answers a tuple of rows in that same order, and a
  date range refuses bounds that name no range at all: both ends open, an
  inverted range, or a bound with no timezone.
- A page from :meth:`list_matching` carries every filter that was given, its
  ``total`` counts the rows all of them matched, a filter left ``None`` is
  not applied, and the page is taken over those matched rows.
- Nothing here holds a band beside a decision: a repository stores what a
  stage measured, which is the split 7.10's walk over ``app/`` exists to
  protect.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import ColumnElement, and_, func, select, true
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import Screening

__all__ = ["ScreeningPage", "ScreeningRepository"]


@dataclass(frozen=True)
class ScreeningPage:
    """One page of ``screenings`` rows, and the total they were drawn from.

    :param rows: the rows this page holds, detached and readable, in
        ``created_at`` then ``id`` order.
    :param total: how many rows the table holds, not how many this page does.
    :param offset: the offset the page was taken at.
    :param limit: the page size the page was taken with.
    """

    rows: tuple[Screening, ...]
    total: int
    offset: int
    limit: int

    def __len__(self) -> int:
        """The number of rows on this page, which is not :attr:`total`."""
        return len(self.rows)


def _require_page_bounds(offset: int, limit: int) -> None:
    """Refuse bounds that describe no page.

    :param offset: rows to skip; must not be negative.
    :param limit: rows per page; must be at least one.
    :returns: nothing.
    :raises ValueError: when either bound is out of range.  Nothing is
        queried, so nothing is read and nothing is written.
    """
    if offset < 0:
        raise ValueError(f"offset cannot be negative, got {offset}")
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")


def _in_read_order() -> tuple[ColumnElement[Any], ...]:
    """The one order every read of ``screenings`` answers in.

    ``created_at`` then ``id``, which is a total order rather than a partial
    one: two screenings can share an instant, and a partial order would let a
    row appear on two pages or on none.

    :returns: the ordering clauses, for ``order_by``.
    """
    return (Screening.created_at, Screening.id)


def _not_soft_deleted() -> ColumnElement[bool]:
    """Build the filter every read of ``screenings`` applies.

    :returns: ``deleted_at IS NULL`` -- the one spelling of "not deleted",
        reached by ``get``, ``_page``, ``_rows`` and ``soft_delete``, so a
        read that skipped it and a delete that found through it could not
        disagree about which rows are live.
    """
    return Screening.deleted_at.is_(None)


def _utc_bound(name: str, moment: datetime) -> datetime:
    """Return ``moment`` as a UTC instant, refusing a bound with no zone.

    :param name: the argument's name, for the message.
    :param moment: the instant the caller handed over.
    :returns: ``moment`` converted to UTC, so a bound carrying an offset
        reaches the database as the instant it names rather than as the wall
        time it was written at.
    :raises ValueError: when ``moment`` carries no timezone.  Nothing is
        queried, so nothing is read and nothing is written.
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(
            f"{name} must carry a timezone, got naive {moment.isoformat()}"
        )
    return moment.astimezone(timezone.utc)


def _created_at_within(
    start: datetime | None, end: datetime | None
) -> ColumnElement[bool]:
    """Build the filter :meth:`ScreeningRepository.list_by_date_range` applies.

    :param start: the inclusive first instant, or ``None`` for an open one.
    :param end: the inclusive last instant, or ``None`` for an open one.
    :returns: the condition, carrying one end only where that end is open.
    :raises ValueError: when both ends are open, or when the range is
        inverted.  Nothing is queried, so nothing is read and nothing is
        written.
    """
    if start is None:
        if end is None:
            raise ValueError(
                "a date range needs at least one of start or end; "
                "list() is the way to ask for every row"
            )
        return Screening.created_at <= _utc_bound("end", end)
    if end is None:
        return Screening.created_at >= _utc_bound("start", start)
    first = _utc_bound("start", start)
    last = _utc_bound("end", end)
    if first > last:
        raise ValueError(
            f"start cannot be after end, got {first.isoformat()} "
            f"after {last.isoformat()}"
        )
    return and_(Screening.created_at >= first, Screening.created_at <= last)


class ScreeningRepository:
    """Reads and writes ``screenings`` rows through sessions the caller owns.

    :param sessions: the factory every session this repository opens is bound
        to, as returned by :func:`app.storage.db.build_session_factory`.
        Required, and not defaulted to the module-level
        :data:`app.storage.db.SessionLocal`: see the module docstring.
    """

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(
        self,
        *,
        document_type: str,
        filename: str,
        image_width: int,
        image_height: int,
    ) -> Screening:
        """Write the row an upload carried, and return it once it is stored.

        :param document_type: which kind of document the caller said this was.
        :param filename: the name the upload arrived under.
        :param image_width: the pixel width of the uploaded image.
        :param image_height: the pixel height of the uploaded image.
        :returns: the committed row, carrying the ``id``, ``created_at`` and
            ``status`` its ORM defaults stamped and no result at all.
        :raises ~sqlalchemy.exc.IntegrityError: when the row cannot be stored.
            Nothing is returned and nothing is written.
        """
        row = Screening(
            document_type=document_type,
            filename=filename,
            image_width=image_width,
            image_height=image_height,
        )
        with self._sessions() as session:
            session.add(row)
            session.commit()
        return row

    def soft_delete(
        self, screening_id: uuid.UUID, *, deleted_at: datetime
    ) -> Screening | None:
        """Stamp ``deleted_at`` on a live row, and leave the row in place.

        :param screening_id: the :class:`uuid.UUID` the primary key column
            holds.  Not coerced from a string, on :meth:`get`'s reasoning.
        :param deleted_at: when the row was deleted.  Keyword-only, must
            carry a timezone, and is converted to UTC.  Taken rather than
            read from a clock: see the module docstring.
        :returns: the committed row carrying the stamp, detached and
            readable, or ``None`` when no *live* row carries that id -- an id
            no row carries and a row already soft-deleted are the same
            answer, and the second delete leaves the first stamp standing.
        :raises ValueError: when ``deleted_at`` carries no timezone.  Nothing
            is queried, so the table is neither read nor written.
        """
        stamp = _utc_bound("deleted_at", deleted_at)
        with self._sessions() as session:
            row = session.execute(
                select(Screening).where(
                    Screening.id == screening_id, _not_soft_deleted()
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            row.deleted_at = stamp
            session.commit()
        return row

    def get(self, screening_id: uuid.UUID) -> Screening | None:
        """Return the row ``screening_id`` names, or ``None`` if none does.

        :param screening_id: the :class:`uuid.UUID` the primary key column
            holds.  Not coerced from a string: see the module docstring.
        :returns: the stored row, detached and readable once this call's
            session has closed, or ``None`` when no row carries that id or
            the row that does has been soft-deleted.
        """
        with self._sessions() as session:
            return session.execute(
                select(Screening).where(
                    Screening.id == screening_id, _not_soft_deleted()
                )
            ).scalar_one_or_none()

    def list(self, offset: int, limit: int) -> ScreeningPage:
        """Return one page of rows, and the number of rows there are.

        :param offset: how many rows to skip.  Past the last row is an empty
            page, not an error; negative is refused.
        :param limit: how many rows the page holds.  A page may hold fewer
            than this; ``limit`` below one is refused.
        :returns: a :class:`ScreeningPage` whose ``rows`` are detached and
            readable, ordered by ``created_at`` then ``id``, and whose
            ``total`` counts the rows rather than the page.  No filter is
            applied besides the ``deleted_at`` rule every read carries.
        :raises ValueError: when a bound describes no page.  Nothing is
            queried, so the table is neither read nor written.
        """
        return self._page(true(), offset, limit)

    def list_by_band(
        self, band: str | None, offset: int, limit: int
    ) -> ScreeningPage:
        """Return one page of the rows carrying ``band``, and their number.

        :param band: the band to filter on, as a stage stored it, or ``None``
            for the rows nothing has scored yet.  Not checked against
            :mod:`app.risk.bands`: a name no row carries is an empty page.
        :param offset: how many of the matched rows to skip.
        :param limit: how many of the matched rows the page holds.
        :returns: a :class:`ScreeningPage` on :meth:`list`'s terms, with a
            ``total`` that counts the rows that matched rather than the
            table.  Carries the ``deleted_at`` rule every read carries.
        :raises ValueError: when a bound describes no page.  Nothing is
            queried, so the table is neither read nor written.
        """
        condition = (
            Screening.band.is_(None) if band is None else Screening.band == band
        )
        return self._page(condition, offset, limit)

    def list_by_date_range(
        self, start: datetime | None, end: datetime | None
    ) -> tuple[Screening, ...]:
        """Return the rows stamped inside the range, and only those.

        :param start: the inclusive first instant in UTC, or ``None`` for a
            range open at the beginning.  A bound in another offset is
            converted; one with no timezone is refused.
        :param end: the inclusive last instant in UTC, or ``None`` for a
            range open at the end.
        :returns: the matching rows, detached and readable, in
            ``created_at`` then ``id`` order.  No window of their own: see
            the module docstring.  Carries the ``deleted_at`` rule every read
            carries.
        :raises ValueError: when the range names no range -- both ends open,
            inverted, or a bound with no timezone.  Nothing is queried, so
            the table is neither read nor written.
        """
        return self._rows(_created_at_within(start, end))

    def list_by_document_type(self, doc_type: str) -> tuple[Screening, ...]:
        """Return the rows whose upload claimed this kind of document.

        :param doc_type: the kind to filter on, as the upload carried it.
            Not checked against a vocabulary, on :meth:`list_by_band`'s
            reasoning: a kind no row carries is an empty answer.
        :returns: the matching rows, detached and readable, in
            ``created_at`` then ``id`` order.  No window of their own, and no
            filter besides the ``deleted_at`` rule every read carries.
        """
        return self._rows(Screening.document_type == doc_type)

    def list_matching(
        self,
        *,
        band: str | None = None,
        document_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int,
        limit: int,
    ) -> ScreeningPage:
        """Take one page of the rows every filter that was given matches.

        :param band: the band to filter on, or ``None`` for no band filter
            at all -- unlike :meth:`list_by_band`, where ``None`` is the rows
            nothing has scored.  Not checked against a vocabulary.
        :param document_type: the kind to filter on, or ``None`` for none.
            Not checked against a vocabulary either.
        :param start: the inclusive first instant, or ``None`` to leave the
            beginning of the range open.
        :param end: the inclusive last instant, or ``None`` to leave the end
            open.  Both ``None`` is no date filter rather than a fault.
        :param offset: how many of the matched rows to skip.
        :param limit: how many of the matched rows the page holds.
        :returns: a :class:`ScreeningPage` on :meth:`list`'s terms, whose
            ``total`` counts the rows every given filter matched.  With no
            filter given it answers what :meth:`list` answers.  Carries the
            ``deleted_at`` rule every read carries.
        :raises ValueError: when a bound describes no page, or the range
            names no range -- inverted, or a bound with no timezone.  Nothing
            is queried, so the table is neither read nor written.
        """
        conditions: list[ColumnElement[bool]] = [true()]
        if band is not None:
            conditions.append(Screening.band == band)
        if document_type is not None:
            conditions.append(Screening.document_type == document_type)
        if start is not None or end is not None:
            conditions.append(_created_at_within(start, end))
        return self._page(and_(*conditions), offset, limit)

    def _page(
        self, condition: ColumnElement[bool], offset: int, limit: int
    ) -> ScreeningPage:
        """Take one page of the rows matching ``condition``.

        :param condition: the filter the rows and the count both apply.
        :param offset: how many matched rows to skip.
        :param limit: how many matched rows the page holds.
        :returns: a :class:`ScreeningPage` ordered by ``created_at`` then
            ``id``, holding at most ``limit`` rows and a ``total`` counting
            the matched rows.  Both statements also carry
            :func:`_not_soft_deleted`, so the count moves with the rows: a
            total that counted a deleted row would page 11.3's route past
            rows it will never show.
        :raises ValueError: when a bound describes no page, before any
            statement is emitted.
        """
        _require_page_bounds(offset, limit)
        live = and_(condition, _not_soft_deleted())
        with self._sessions() as session:
            rows = tuple(
                session.execute(
                    select(Screening)
                    .where(live)
                    .order_by(*_in_read_order())
                    .offset(offset)
                    .limit(limit)
                ).scalars()
            )
            total = session.execute(
                select(func.count())
                .select_from(Screening)
                .where(live)
            ).scalar_one()
        return ScreeningPage(rows=rows, total=total, offset=offset, limit=limit)

    def _rows(self, condition: ColumnElement[bool]) -> tuple[Screening, ...]:
        """Read every row matching ``condition``, with no window on it.

        :param condition: the filter the rows apply.
        :returns: the matching rows, detached and readable, in
            ``created_at`` then ``id`` order.  Every match rather than a
            window of them, so the count is ``len()`` of what comes back.
            :func:`_not_soft_deleted` is applied here as it is in
            :meth:`_page`.
        """
        with self._sessions() as session:
            return tuple(
                session.execute(
                    select(Screening)
                    .where(and_(condition, _not_soft_deleted()))
                    .order_by(*_in_read_order())
                ).scalars()
            )
