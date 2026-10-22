"""8.10 to 8.15: ``ScreeningRepository.create``, ``get``, the four reads and
``soft_delete``, then 11.3's one read that composes the three filters.

The task's verify is "a test asserting the returned object has an id and a
creation timestamp", so that assertion is the first test here, bracketed by
clock reads taken either side of the call so a repository that stamped its
own constant would fail it.  8.11's verify -- a missing id answers ``None``
rather than raising -- is the second block.  8.12's verify -- a test
asserting pagination bounds and total count -- is the third, and it is the
one block that empties the table first, because a total is only an absolute
number against a table whose contents this test controls.  The tests around
them are the claims all four rest on:

- **the row is in the database, not merely on the return value.**  The read
  back is a *new* engine over the same file, so nothing can be answered out
  of the session that wrote the row or out of an identity map.
- **the repository writes into the schema 8.8 migrated.**  The fixture below
  runs ``alembic upgrade head`` on a temporary file rather than calling
  ``create_all``, because a repository is the first thing in this project to
  write a row, and a write against a table the migration never made would
  otherwise pass here and fail in a deploy.
- **the returned row survives the session that wrote it.**  ``create`` opens,
  writes, commits and closes inside the call, so the instance the caller
  holds is detached on return; ``expire_on_commit=False`` (``D36``) is the
  only reason reading it does not raise.
- **a row that cannot be committed is neither returned nor left behind.**
  ``create`` returning before the commit would hand a caller an object no
  query would ever find.
- **the repository writes only to the database its sessions name.**  Held
  against two migrated databases at once, because a repository that reached
  for :data:`app.storage.db.SessionLocal` would satisfy every test above it
  and be pinned to the process's start-up configuration.
- **a page is bounded, counted and ordered.**  8.12's total is the count of
  the table rather than of the page, so a page of one row out of five says
  five; the order is checked against a stamp the test chose rather than one
  it waited for, so a ``list`` with no ``ORDER BY`` fails rather than
  happening to agree with insertion order.
- **a filtered page excludes every other band.**  8.13's verify, held
  against a table holding every band so a filter that answered nothing, or
  everything, fails rather than passing on an empty match; and the count is
  the number of rows that *matched*, which is the number 11.3's route sizes
  its pages by.
- **a range and a kind exclude every row beside them.**  8.14's two
  verifies, held against rows stamped either side of the range and rows of
  another kind, so a filter that answered everything or nothing fails.  The
  claims those two rests on are separate ones: both ends are inclusive, an
  open end reaches the edge of the table, a range in another timezone is the
  instant it names rather than the wall time it was written at, and a range
  that names no range is refused rather than answered empty.
- **a soft-deleted row is answered by no read, and is still in the table.**
  8.15's verify, held against each read in turn rather than against ``list``
  alone, because the rule is written in one private helper five statements
  reach and a read that missed it would go unnoticed.  The claims that rest
  on it are separate ones: the row is stamped rather than removed, so it is
  still there for the audit view; the total moves with the rows it counts,
  or 11.3's route pages past rows it will never show; the page is taken over
  the live rows, so a deleted one does not shift the window; ``get`` answers
  the row *before* it is deleted, which is the read 24.5 confirms on; a row
  is deleted once, and a second delete leaves the first stamp standing; the
  stamp is the instant the caller named rather than the wall time it was
  written at; and a naive stamp is refused with the row untouched.
- **the three filters are one statement and one count.**  11.3 needs a band
  *and* a kind *and* a range over one window, which the four reads above
  cannot give: each is a whole statement, so composing them in a caller
  would page in Python and count a second time.  The composed read is held
  against a table carrying every band, every kind and stamps on both sides
  of every range, and the rows are written in an order that is not the order
  they are read back in, so a read with no ``ORDER BY`` fails rather than
  agreeing with insertion by accident.
"""

import pathlib
import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.storage import db
from app.storage.models import DEFAULT_SCREENING_STATUS, Screening
from app.storage.repository import ScreeningPage, ScreeningRepository


#: The alembic configuration this service migrates with, derived from this
#: file for the reason ``test_alembic_migration.py`` gives: the suite runs
#: from the repository root, so a path spelled relative to the working
#: directory would be a second answer to "where is alembic.ini".
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"

#: What an upload carried, and the whole of what ``create`` is given.  A
#: mapping rather than four module-level names so one test can hand a single
#: column a value the table refuses without repeating the other three.
AN_UPLOAD: dict[str, Any] = {
    "document_type": "passport",
    "filename": "passport-page.jpg",
    "image_width": 1240,
    "image_height": 1754,
}

#: The columns ``create`` is given, beside the three the ORM stamps.  A
#: column of the row that is not in this set is one ``create`` must leave
#: empty, and it is read off the model below rather than listed twice.
WRITTEN_BY_CREATE = frozenset(AN_UPLOAD) | frozenset(
    {"id", "created_at", "status"}
)

#: Every column the model declares, so "a column added later is also a column
#: ``create`` must leave empty" needs no edit here.
ALL_COLUMNS = frozenset(column.name for column in Screening.__table__.columns)


class _Databases(NamedTuple):
    """Two migrated SQLite files, for the claim about who owns the session."""

    primary: pathlib.Path
    other: pathlib.Path


def _url_for(database: pathlib.Path) -> str:
    """The URL naming ``database``, in the spelling 8.8's fixture uses."""
    return f"sqlite:///{database.as_posix()}"


def _migrate(databases: tuple[pathlib.Path, ...]) -> None:
    """Run ``upgrade head`` against each of ``databases``, in turn.

    ``DATABASE_URL`` is set for the command and restored afterwards, because
    :mod:`alembic.env` asks :func:`app.config.get_database_url` for the
    answer rather than taking a URL of its own.
    """
    for database in databases:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", _url_for(database))
            command.upgrade(Config(str(ALEMBIC_INI)), "head")
        assert database.exists()


@pytest.fixture(scope="module")
def migrated_databases(tmp_path_factory: pytest.TempPathFactory) -> _Databases:
    """Two ``tmp_path`` files migrated to head, and nothing else in them.

    Module-scoped so the migration runs twice for the file rather than once
    per test, and ``tmp_path_factory`` rather than ``tmp_path`` for the same
    reason.  ``tmp_path_factory`` is outside the repository, so a failed run
    cannot leave a ``drishti.db`` beside the code.
    """
    directory = tmp_path_factory.mktemp("screening-repository")
    databases = _Databases(
        directory / "primary.db", directory / "other.db"
    )
    _migrate(tuple(databases))
    return databases


@pytest.fixture
def sessions(migrated_databases: _Databases) -> sessionmaker[Session]:
    """A session factory over the migrated file, built the service's way."""
    return db.build_session_factory(
        db.build_engine(_url_for(migrated_databases.primary))
    )


@pytest.fixture
def repository(sessions: sessionmaker[Session]) -> ScreeningRepository:
    """The repository under test, over the sessions the test handed it."""
    return ScreeningRepository(sessions)


@pytest.fixture
def clean_repository(sessions: sessionmaker[Session]) -> ScreeningRepository:
    """The same repository, over a table emptied before the test ran.

    The migrated file is module-scoped, so it carries every row an earlier
    test wrote.  A *total* is the number a page is measured against, and a
    total taken against a table this test did not empty could only be a
    delta -- so the row delete happens here, once, and every count below it
    is an absolute number.  It is a separate fixture rather than an
    autouse one so 8.10's and 8.11's delta claims are left as they are.
    """
    with sessions() as session:
        session.execute(delete(Screening))
        session.commit()
    return ScreeningRepository(sessions)


def _empty_table(sessions: sessionmaker[Session]) -> None:
    """Delete every row, for a test that needs the table bare mid-run."""
    with sessions() as session:
        session.execute(delete(Screening))
        session.commit()


def _fresh_sessions(database: pathlib.Path) -> sessionmaker[Session]:
    """A second factory, over a *new* engine on the same file.

    A new engine is the point: it holds its own connection, so a row found
    through it was serialised rather than still sitting in the identity map
    of the session that wrote it.
    """
    return db.build_session_factory(db.build_engine(_url_for(database)))


def _stored_row_count(database: pathlib.Path) -> int:
    """How many rows the migrated file holds, read over a fresh engine."""
    with _fresh_sessions(database)() as session:
        return session.execute(
            select(func.count()).select_from(Screening)
        ).scalar_one()


# --- the task's assertion, and what it rests on -----------------------------


def test_the_row_create_returns_carries_an_id_and_a_creation_timestamp(
    repository: ScreeningRepository,
) -> None:
    """8.10's verify: the returned object has an id and a creation stamp.

    The clock is read either side of the call, so the timestamp is shown to
    be the moment the row was written rather than a value that happens to be
    present.  The id is checked as a :class:`uuid.UUID` rather than merely
    for truthiness, because an empty string would pass the weaker test and
    is not the opaque token :attr:`Screening.id` is documented to be.
    """
    before = datetime.now(timezone.utc)
    row = repository.create(**AN_UPLOAD)
    after = datetime.now(timezone.utc)

    assert isinstance(row.id, uuid.UUID)
    assert row.created_at is not None
    assert before <= row.created_at <= after


def test_the_row_is_in_the_database_when_create_returns(
    repository: ScreeningRepository, migrated_databases: _Databases
) -> None:
    """The returned row is a stored row: the commit is what makes it one."""
    row = repository.create(**AN_UPLOAD)

    with _fresh_sessions(migrated_databases.primary)() as session:
        found = session.get(Screening, row.id)

    assert found is not None
    assert (found.document_type, found.filename) == (
        "passport",
        "passport-page.jpg",
    )
    assert (found.image_width, found.image_height) == (1240, 1754)
    assert found.status == DEFAULT_SCREENING_STATUS


def test_the_returned_row_is_readable_once_its_session_is_closed(
    repository: ScreeningRepository,
) -> None:
    """``expire_on_commit=False`` (``D36``), measured by reading every column.

    ``create`` opens, writes, commits and closes inside the call, so the
    instance handed back is detached.  Reading one attribute of it is enough
    to fail if the factory ever expires on commit, and *every* column is read
    because a column added later must not become a new way for this to raise.
    """
    row = repository.create(**AN_UPLOAD)

    read = {name: getattr(row, name) for name in sorted(ALL_COLUMNS)}

    assert read["id"] is not None
    assert read["created_at"] is not None
    assert read["status"] == DEFAULT_SCREENING_STATUS


def test_a_created_row_carries_the_upload_and_none_of_the_result(
    repository: ScreeningRepository,
) -> None:
    """11.1 asks for an id before the analysis has run, so nothing is filled.

    The empty columns are read off the model rather than listed here, so a
    column added to ``Screening`` later is covered by this test without it
    being edited -- and ``create`` is given no way to fill one in, which is
    the claim: a score, a band and a finding are written by the stages that
    measured them, never by the method that created the row.
    """
    row = repository.create(**AN_UPLOAD)

    written = {name for name in ALL_COLUMNS - WRITTEN_BY_CREATE
               if getattr(row, name) is not None}

    assert written == set()


def test_two_rows_created_at_the_same_time_get_two_different_ids(
    repository: ScreeningRepository,
) -> None:
    """The id is per row, not a value the repository holds and reuses."""
    first = repository.create(**AN_UPLOAD)
    second = repository.create(**AN_UPLOAD)

    assert first.id != second.id


def test_a_row_that_cannot_be_stored_is_neither_returned_nor_left_behind(
    repository: ScreeningRepository, migrated_databases: _Databases
) -> None:
    """A failed commit raises out of ``create`` and writes nothing.

    ``filename`` is the required column being handed the value the table
    refuses, so the refusal is the database's and not an argument check this
    module would have had to grow.  The count is a delta rather than an
    absolute because the migrated file is module-scoped and earlier tests
    have written to it.
    """
    before = _stored_row_count(migrated_databases.primary)

    with pytest.raises(IntegrityError):
        repository.create(**{**AN_UPLOAD, "filename": None})

    assert _stored_row_count(migrated_databases.primary) == before


def test_a_repository_writes_only_to_the_database_its_sessions_name(
    sessions: sessionmaker[Session], migrated_databases: _Databases
) -> None:
    """The repository owns no database of its own -- ``D42``.

    Two repositories, two migrated files, and each row is found only through
    the sessions that repository was handed.  A repository reaching for
    :data:`app.storage.db.SessionLocal` would put both rows in a third
    database and the second half of this test would fail, which is the whole
    point: the module-level pair is bound at import and cannot be aimed at a
    file.
    """
    other_sessions = _fresh_sessions(migrated_databases.other)
    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(other_sessions)

    written_by_mine = mine.create(**AN_UPLOAD)
    written_by_theirs = theirs.create(**{**AN_UPLOAD, "document_type": "visa"})

    with sessions() as session:
        assert session.get(Screening, written_by_mine.id) is not None
        assert session.get(Screening, written_by_theirs.id) is None

    with other_sessions() as session:
        assert session.get(Screening, written_by_theirs.id) is not None
        assert session.get(Screening, written_by_mine.id) is None


# --- 8.11: the read beside create -------------------------------------------


def test_get_answers_the_row_the_id_names(
    repository: ScreeningRepository,
) -> None:
    """The round trip 8.11's "missing" claim needs something to be missing from.

    The row is written and read through the same repository, so a ``get``
    that answered ``None`` for everything would fail here rather than
    quietly passing the absence test below.
    """
    written = repository.create(**AN_UPLOAD)

    found = repository.get(written.id)

    assert found is not None
    assert found.id == written.id
    assert (found.document_type, found.filename) == (
        "passport",
        "passport-page.jpg",
    )
    assert (found.image_width, found.image_height) == (1240, 1754)
    assert found.status == DEFAULT_SCREENING_STATUS


def test_get_answers_none_for_an_id_no_row_carries(
    repository: ScreeningRepository,
) -> None:
    """8.11's verify: a missing id answers ``None`` rather than raising.

    ``uuid.uuid4()`` is fresh, so no row in this module's database has ever
    carried it; the assertion reaching at all is the test, since a ``get``
    that raised ``NoResultFound`` would fail on the line above it.
    """
    assert repository.get(uuid.uuid4()) is None


def test_get_answers_none_for_a_row_that_has_been_removed(
    repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """Absence is read rather than remembered: a row that was there is not.

    The delete goes through a session directly because this is a *hard*
    delete, which is not what ``soft_delete`` does: the claim is about a row
    that is gone from the table, so a ``get`` answering from anything the
    caller already held would still return the row it wrote a moment ago.
    """
    written = repository.create(**AN_UPLOAD)
    with sessions() as session:
        session.delete(session.get(Screening, written.id))
        session.commit()

    assert repository.get(written.id) is None


def test_the_row_get_returns_is_readable_once_its_session_is_closed(
    repository: ScreeningRepository,
) -> None:
    """``get`` hands back a detached row, read in every column to prove it.

    ``get`` opens, reads and closes inside the call, so the instance it
    returns is detached.  Every column is read because a column added later
    must not become a new way for this to raise.
    """
    written = repository.create(**AN_UPLOAD)

    found = repository.get(written.id)

    read = {name: getattr(found, name) for name in sorted(ALL_COLUMNS)}
    assert read["id"] == written.id
    assert read["created_at"] is not None
    assert read["status"] == DEFAULT_SCREENING_STATUS


def test_get_reads_the_same_row_twice_and_writes_nothing(
    repository: ScreeningRepository, migrated_databases: _Databases
) -> None:
    """A read is a read: asked twice it answers twice, and adds no row.

    The count is read over a fresh engine, so a ``get`` that inserted a row
    on its way past would be caught rather than being answered out of its
    own uncommitted transaction.
    """
    written = repository.create(**AN_UPLOAD)
    after_create = _stored_row_count(migrated_databases.primary)

    first = repository.get(written.id)
    second = repository.get(written.id)

    assert first is not None
    assert second is not None
    assert (first.id, second.id) == (written.id, written.id)
    assert _stored_row_count(migrated_databases.primary) == after_create


def test_get_reads_only_from_the_database_its_sessions_name(
    sessions: sessionmaker[Session], migrated_databases: _Databases
) -> None:
    """``D42`` holds for the read too, not only for the write.

    Two repositories over two migrated files: the row the second one wrote
    is invisible to the first, so a ``get`` reaching for
    :data:`app.storage.db.SessionLocal` would answer it -- and a ``get`` that
    asked its caller's session rather than its own would answer it too.
    """
    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(_fresh_sessions(migrated_databases.other))
    written_by_theirs = theirs.create(**AN_UPLOAD)

    assert mine.get(written_by_theirs.id) is None
    assert theirs.get(written_by_theirs.id) is not None


# --- 8.12: the page beside the two reads ------------------------------------

#: How many rows the pagination tests put in the table.  Five is the smallest
#: number that leaves a page short of a full one and a final page that is,
#: so a bound that ignored ``limit`` cannot pass by being asked for exactly
#: the number of rows present.
ROWS_ON_TEST = 5


def _write_rows(
    repository: ScreeningRepository, count: int = ROWS_ON_TEST
) -> list[Screening]:
    """Write ``count`` rows through ``create``, and return them in order.

    Each carries a distinct ``filename`` so a page can be checked against the
    rows that were written rather than against their positions, and the list
    is in creation order because ``create`` stamps ``created_at`` itself and
    each call is a separate commit.
    """
    return [
        repository.create(
            **{**AN_UPLOAD, "filename": f"passport-page-{index}.jpg"}
        )
        for index in range(count)
    ]


def test_list_answers_the_rows_the_bounds_name(
    clean_repository: ScreeningRepository,
) -> None:
    """8.12's verify: the page holds the rows ``offset`` and ``limit`` name.

    Five rows are written and the middle two are asked for, so a ``list`` that
    ignored either bound -- returning the first two, all five, or the last two
    -- fails here rather than on a page that happened to be full.
    """
    written = _write_rows(clean_repository)

    page = clean_repository.list(offset=1, limit=2)

    assert [row.id for row in page.rows] == [written[1].id, written[2].id]


def test_list_reports_the_number_of_rows_there_are_not_the_number_it_returned(
    clean_repository: ScreeningRepository,
) -> None:
    """The total is the table's count, so a caller can size every page.

    A ``total`` measured from the returned rows would answer 2 here, which is
    the one number 11.3's route and 24.3's pagination cannot work from: a
    table of five read as a table of two would render one page and hide four
    rows.
    """
    _write_rows(clean_repository)

    page = clean_repository.list(offset=0, limit=2)

    assert len(page.rows) == 2
    assert page.total == ROWS_ON_TEST


def test_a_page_past_the_last_row_is_empty_and_still_counts(
    clean_repository: ScreeningRepository,
) -> None:
    """An ``offset`` beyond the end is an answer, not a fault.

    Asked twice, once a page short of the end and once well past it, because
    the two halves of this claim are separate: a bound that is simply larger
    than the table must not raise, and it must not lower the count either --
    the table did not change.
    """
    _write_rows(clean_repository)

    last_full = clean_repository.list(offset=3, limit=2)
    past_end = clean_repository.list(offset=ROWS_ON_TEST, limit=10)

    assert len(last_full.rows) == 2
    assert last_full.total == ROWS_ON_TEST
    assert past_end.rows == ()
    assert past_end.total == ROWS_ON_TEST


def test_paging_by_two_visits_every_row_once(
    clean_repository: ScreeningRepository,
) -> None:
    """Consecutive pages tile the table: no row twice, no row skipped.

    This is the claim a single page cannot make.  An ``OFFSET`` with no
    ``ORDER BY`` would be stable enough on one file and unstable on another,
    and would still pass a test that only ever read one page.
    """
    written = _write_rows(clean_repository)

    paged = [
        row
        for offset in (0, 2, 4)
        for row in clean_repository.list(offset=offset, limit=2).rows
    ]

    assert [row.id for row in paged] == [row.id for row in written]


def test_list_orders_by_when_the_row_was_created(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The order is ``created_at``, not the order the rows went in.

    The three rows are written newest, oldest, middle -- through a session
    directly, because ``create`` stamps the clock itself and 8.14 owns the
    question of choosing a stamp.  A ``list`` with no ``ORDER BY`` would
    answer in rowid order and return these three exactly as written.
    """
    stamps = [
        datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc),
    ]
    with sessions() as session:
        for index, stamp in enumerate(stamps):
            session.add(
                Screening(
                    document_type="passport",
                    filename=f"passport-page-{index}.jpg",
                    image_width=1240,
                    image_height=1754,
                    created_at=stamp,
                )
            )
        session.commit()

    page = clean_repository.list(offset=0, limit=len(stamps))

    assert [row.filename for row in page.rows] == [
        "passport-page-1.jpg",
        "passport-page-2.jpg",
        "passport-page-0.jpg",
    ]


@pytest.mark.parametrize(
    ("offset", "limit"),
    [
        pytest.param(-1, 10, id="negative-offset"),
        pytest.param(0, 0, id="no-rows-per-page"),
        pytest.param(0, -5, id="negative-limit"),
    ],
)
def test_list_refuses_bounds_that_describe_no_page(
    clean_repository: ScreeningRepository,
    offset: int,
    limit: int,
) -> None:
    """A bound that selects nothing is refused, and reads nothing on the way.

    Clamping either one to a nearby value would answer with a page nobody
    asked for, and answering quietly is how a caller ends up paging over the
    same rows twice.  The count is read after the refusal so a ``list`` that
    queried before it checked is caught: a refused call reads nothing.
    """
    _write_rows(clean_repository)

    with pytest.raises(ValueError):
        clean_repository.list(offset=offset, limit=limit)

    assert clean_repository.list(offset=0, limit=ROWS_ON_TEST).total == (
        ROWS_ON_TEST
    )


def test_list_answers_an_empty_page_for_an_empty_table(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """No rows and a total of zero is a page, not a failure to find one.

    A ``total`` read as ``None`` here -- or an empty page refused as "nothing
    found" -- would make a first-ever request to 11.3's route an error
    instead of the empty history 24.7 is written to render.
    """
    _empty_table(sessions)

    page = clean_repository.list(offset=0, limit=10)

    assert page.rows == ()
    assert page.total == 0
    assert len(page) == 0


def test_the_rows_list_returns_are_readable_once_its_session_is_closed(
    clean_repository: ScreeningRepository,
) -> None:
    """A page hands back detached rows, read in every column to prove it.

    The same ``expire_on_commit=False`` (``D36``) precondition 8.10's and
    8.11's rows rest on, and read for a page rather than for one row because
    a page is the case 11.3 hands to a response model attribute by attribute.
    Every column is read so a column added later is not a new way to raise.
    """
    _write_rows(clean_repository)

    page = clean_repository.list(offset=0, limit=ROWS_ON_TEST)

    read = [
        {name: getattr(row, name) for name in sorted(ALL_COLUMNS)}
        for row in page.rows
    ]
    assert len(read) == ROWS_ON_TEST
    assert all(row["id"] is not None for row in read)
    assert all(row["created_at"] is not None for row in read)
    assert all(row["status"] == DEFAULT_SCREENING_STATUS for row in read)


def test_list_reads_the_same_page_twice_and_writes_nothing(
    clean_repository: ScreeningRepository,
    migrated_databases: _Databases,
) -> None:
    """A list is a read: asked twice it answers twice, and adds no row.

    The count is read over a *fresh* engine afterwards, so a ``list`` that
    inserted a row on the way past could not be answered out of its own
    uncommitted transaction.
    """
    written = _write_rows(clean_repository)

    first = clean_repository.list(offset=1, limit=2)
    second = clean_repository.list(offset=1, limit=2)

    assert [row.id for row in first.rows] == [row.id for row in second.rows]
    assert [row.id for row in first.rows] == [written[1].id, written[2].id]
    with _fresh_sessions(migrated_databases.primary)() as fresh:
        assert fresh.execute(
            select(func.count()).select_from(Screening)
        ).scalar_one() == ROWS_ON_TEST


def test_a_page_carries_the_bounds_it_was_taken_with(
    clean_repository: ScreeningRepository,
) -> None:
    """The page remembers its own bounds, so a caller need not.

    11.3 renders "showing 21-40 of 137" from these three values; a page that
    carried only rows and a total would make the route re-derive the window
    from a request it no longer holds.
    """
    _write_rows(clean_repository)

    page = clean_repository.list(offset=2, limit=3)

    assert (page.offset, page.limit, page.total) == (2, 3, ROWS_ON_TEST)
    assert isinstance(page, ScreeningPage)
    assert len(page) == 3


# --- 8.13: the same page, filtered by the band a stage wrote ----------------

#: The three band names as ``app.risk.bands`` spells them.  Written out here
#: rather than imported: the repository holds no vocabulary, and a test that
#: imported one would not notice if it grew a second.
BANDS = ("low", "review", "high")

#: The instant the banded rows are stamped from, so a test chooses the order
#: rather than waits for it -- ``create`` takes no band and stamps its own
#: clock, so these rows are written through a session directly.
FIRST_STAMP = datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc)


def _write_banded_rows(
    sessions: sessionmaker[Session],
    bands: Sequence[str | None],
    stamps: Sequence[datetime] | None = None,
) -> list[Screening]:
    """Write one row per entry of ``bands``, and return them in write order.

    :param sessions: the factory the rows are written through.
    :param bands: the band each row carries; ``None`` writes the row nothing
        has scored.
    :param stamps: the ``created_at`` each row is stamped with, defaulting to
        one minute after the previous row.
    :returns: the rows, in the order they were written rather than the order
        they will be read back in.
    """
    with sessions() as session:
        rows = [
            Screening(
                document_type="passport",
                filename=f"passport-page-{index}.jpg",
                image_width=1240,
                image_height=1754,
                band=band,
                created_at=(
                    FIRST_STAMP + timedelta(minutes=index)
                    if stamps is None
                    else stamps[index]
                ),
            )
            for index, band in enumerate(bands)
        ]
        session.add_all(rows)
        session.commit()
    return rows


def test_list_by_date_range_answers_only_the_rows_stamped_inside_the_range(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """8.14's verify: no row stamped outside the range is on the answer.

    Four rows sit either side of the window and the whole table is counted
    first, so the filter cannot pass by matching nothing: a range that
    answered the whole table, or an empty tuple, fails below.
    """
    written = _write_typed_rows(
        sessions,
        ("passport", "passport", "passport", "passport"),
        _march((6, 9, 12, 15)),
    )
    assert clean_repository.list(offset=0, limit=10).total == 4

    found = clean_repository.list_by_date_range(
        start=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
        end=datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc),
    )

    assert [row.id for row in found] == [written[1].id, written[2].id]


def test_list_by_date_range_includes_both_of_its_ends(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A row stamped exactly on either end is inside the range.

    The window is drawn to land on two stamps and nothing else, so a range
    with an exclusive end drops both rows and answers nothing -- a loss that
    reads as a row nobody ever screened.
    """
    written = _write_typed_rows(
        sessions, ("passport", "passport", "passport"), _march((6, 9, 12))
    )

    found = clean_repository.list_by_date_range(
        start=datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert [row.id for row in found] == [written[1].id, written[2].id]


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        pytest.param(
            None,
            datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            (0, 1, 2),
            id="open-at-the-beginning",
        ),
        pytest.param(
            datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
            None,
            (1, 2, 3),
            id="open-at-the-end",
        ),
    ],
)
def test_list_by_date_range_with_an_open_end_reaches_the_edge_of_the_table(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    start: datetime | None,
    end: datetime | None,
    expected: tuple[int, ...],
) -> None:
    """``None`` is an open end, not a bound of zero.

    A row before the first stamp and one after the last sit in the table
    throughout, so a missing end that filtered as the other one does drops a
    row rather than reaching the edge of the table.
    """
    written = _write_typed_rows(
        sessions, ("passport",) * 4, _march((6, 9, 12, 15))
    )

    found = clean_repository.list_by_date_range(start=start, end=end)

    assert [row.id for row in found] == [
        written[index].id for index in expected
    ]


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(None, None, id="both-ends-open"),
        pytest.param(
            datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
            id="inverted",
        ),
    ],
)
def test_list_by_date_range_refuses_a_range_that_describes_no_range(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    start: datetime | None,
    end: datetime | None,
) -> None:
    """A range with no range in it is a fault, refused before anything is read.

    An inverted pair is almost always two bounds transposed, and an answer of
    nothing would render as an empty history rather than as a mistake.  The
    table is asked for afterwards: a refused call reads nothing.
    """
    _write_typed_rows(sessions, ("passport",) * 3, _march((9, 12, 15)))

    with pytest.raises(ValueError):
        clean_repository.list_by_date_range(start=start, end=end)

    assert len(
        clean_repository.list_by_date_range(
            start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), end=None
        )
    ) == 3


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(
            datetime(2026, 3, 1, 9, 0),
            datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            id="naive-start",
        ),
        pytest.param(
            datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 1, 12, 0),
            id="naive-end",
        ),
    ],
)
def test_list_by_date_range_refuses_a_bound_that_carries_no_timezone(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    start: datetime,
    end: datetime,
) -> None:
    """``created_at`` is UTC, so a bound with no zone is an ambiguous instant.

    SQLite would compare a naive bound as though it were UTC and answer
    confidently; against a ``timestamptz`` the same query is resolved against
    the server's zone instead.  Refusing it is what makes one query mean one
    instant on both backends.  The table is asked for afterwards.
    """
    _write_typed_rows(sessions, ("passport",) * 2, _march((9, 12)))

    with pytest.raises(ValueError):
        clean_repository.list_by_date_range(start=start, end=end)

    assert len(
        clean_repository.list_by_date_range(
            start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), end=None
        )
    ) == 2


def test_list_by_date_range_reads_a_bound_in_another_zone_as_its_instant(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A range handed in local time is the instant it names, not its wall time.

    The row is stamped 09:00 UTC and the range is asked for 14:30 east, which
    is the same instant.  SQLite's ``DATETIME`` drops an offset rather than
    applying it, so a bound compared as it was written would look for 14:30
    and answer nothing.
    """
    written = _write_typed_rows(
        sessions, ("passport", "passport"), _march((9, 14))
    )

    found = clean_repository.list_by_date_range(
        start=datetime(2026, 3, 1, 14, 30, tzinfo=EAST_ISH),
        end=datetime(2026, 3, 1, 14, 30, tzinfo=EAST_ISH),
    )

    assert [row.id for row in found] == [written[0].id]


def test_list_by_date_range_orders_by_when_the_row_was_created(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The order is the one read order every other read here uses.

    The rows go in newest, oldest, middle, so a range with no ``ORDER BY``
    answers them exactly as they were written.
    """
    _write_typed_rows(sessions, ("passport",) * 4, _march((15, 6, 12, 9)))

    found = clean_repository.list_by_date_range(
        start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), end=None
    )

    assert [row.filename for row in found] == [
        "passport-1.jpg",
        "passport-3.jpg",
        "passport-2.jpg",
        "passport-0.jpg",
    ]


def test_list_by_date_range_answers_no_rows_when_there_are_none_to_answer_with(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """An empty table and a period nothing was screened in are both empty.

    A first-ever request to 11.3's route asks for a period and gets no rows,
    which is an answer rather than a failure to find any.
    """
    _empty_table(sessions)
    assert (
        clean_repository.list_by_date_range(
            start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), end=None
        )
        == ()
    )

    _write_typed_rows(sessions, ("passport",), _march((9,)))
    assert (
        clean_repository.list_by_date_range(
            start=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc), end=None
        )
        == ()
    )


def test_the_rows_list_by_date_range_returns_are_readable_once_they_are_closed(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A filtered read hands back detached rows, read in every column.

    The same ``expire_on_commit=False`` (``D36``) precondition as every other
    read here, read for the tuple rather than the page 8.12 covers.  Every
    column is read so a column added later is not a new way to raise.
    """
    _write_typed_rows(sessions, ("passport",) * 2, _march((9, 12)))

    found = clean_repository.list_by_date_range(
        start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), end=None
    )

    read = [
        {name: getattr(row, name) for name in sorted(ALL_COLUMNS)}
        for row in found
    ]
    assert len(read) == 2
    assert all(row["created_at"] is not None for row in read)
    assert all(row["status"] == DEFAULT_SCREENING_STATUS for row in read)


def test_list_by_date_range_reads_the_same_rows_twice_and_writes_nothing(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    migrated_databases: _Databases,
) -> None:
    """A filtered read is a read: asked twice it answers twice.

    The count is read over a *fresh* engine afterwards, so a filter that
    inserted a row on its way past could not be answered out of its own
    uncommitted transaction.
    """
    _write_typed_rows(sessions, ("passport",) * 2, _march((9, 12)))
    window = {
        "start": datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        "end": None,
    }

    first = clean_repository.list_by_date_range(**window)
    second = clean_repository.list_by_date_range(**window)

    assert [row.id for row in first] == [row.id for row in second]
    assert _stored_row_count(migrated_databases.primary) == 2


def test_list_by_date_range_reads_only_from_the_database_its_sessions_name(
    sessions: sessionmaker[Session], migrated_databases: _Databases
) -> None:
    """``D42`` holds for the range read, and the range is a real one.

    A row in the *other* migrated file falls inside the range asked for, so a
    repository reaching for :data:`app.storage.db.SessionLocal`, or asking
    its caller's session rather than its own, would answer it.  Both files
    are emptied first, since earlier tests in this module write to each.
    """
    other_sessions = _fresh_sessions(migrated_databases.other)
    _empty_table(sessions)
    _empty_table(other_sessions)
    written_here = _write_typed_rows(sessions, ("passport",), _march((9,)))
    written_there = _write_typed_rows(
        other_sessions, ("passport", "passport"), _march((9, 12))
    )
    window = {
        "start": datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        "end": None,
    }

    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(other_sessions)

    assert [row.id for row in mine.list_by_date_range(**window)] == [
        written_here[0].id
    ]
    assert [row.id for row in theirs.list_by_date_range(**window)] == [
        row.id for row in written_there
    ]


def test_list_by_document_type_never_answers_a_row_of_another_kind(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """8.14's verify: every row on the answer carries the kind asked for.

    Two kinds are written and the whole table is counted first, so the filter
    cannot pass by matching nothing: one that answered the whole table, or
    an empty tuple, fails below.
    """
    written = _write_typed_rows(
        sessions, ("passport", "visa", "passport"), _march((9, 12, 15))
    )
    assert clean_repository.list(offset=0, limit=10).total == 3

    found = clean_repository.list_by_document_type("passport")

    assert {row.document_type for row in found} == {"passport"}
    assert [row.id for row in found] == [written[0].id, written[2].id]


def test_list_by_document_type_filters_on_that_column_and_no_other(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The filter is the kind alone, whatever else the row has been given.

    The three rows carry every band and every status between them, including
    the unscored ``pending`` row 11.1 creates, so a filter that also narrowed
    on a result column would answer a subset of its own kind.
    """
    with sessions() as session:
        session.add_all(
            [
                Screening(
                    document_type="passport",
                    filename=f"passport-{index}.jpg",
                    image_width=1240,
                    image_height=1754,
                    band=band,
                    status=status,
                    created_at=stamp,
                )
                for index, (band, status, stamp) in enumerate(
                    zip(
                        (None, "high", "low"),
                        ("pending", "completed", "failed"),
                        _march((9, 12, 15)),
                    )
                )
            ]
        )
        session.commit()

    found = clean_repository.list_by_document_type("passport")

    assert len(found) == 3
    assert {row.band for row in found} == {None, "high", "low"}


def test_list_by_document_type_does_not_check_the_kind_against_a_vocabulary(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A kind this project has never used is an empty answer, not a fault.

    The kind is a claim the upload carried, so the filter answers what is
    stored and holds no vocabulary of its own: a repository that validated
    it would raise, and would have to be edited whenever that closed set
    moved.  The assertion reaching at all is the test.
    """
    _write_typed_rows(sessions, ("passport",), _march((9,)))

    assert clean_repository.list_by_document_type("travel-authorisation") == ()


def test_list_by_document_type_orders_by_when_the_row_was_created(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The order is the one read order every other read here uses.

    Two kinds go in newest, oldest, middle, so a filtered query with no
    ``ORDER BY`` answers them exactly as they were written.
    """
    _write_typed_rows(
        sessions, ("passport", "visa", "passport"), _march((15, 6, 12))
    )

    found = clean_repository.list_by_document_type("passport")

    assert [row.filename for row in found] == [
        "passport-2.jpg",
        "passport-0.jpg",
    ]


def test_the_rows_list_by_document_type_returns_are_readable_once_they_are_closed(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A filtered read hands back detached rows, read in every column.

    The same ``expire_on_commit=False`` (``D36``) precondition as every other
    read here.  Every column is read so a column added later is not a new way
    to raise.
    """
    _write_typed_rows(sessions, ("passport", "visa"), _march((9, 12)))

    found = clean_repository.list_by_document_type("passport")

    read = [
        {name: getattr(row, name) for name in sorted(ALL_COLUMNS)}
        for row in found
    ]
    assert len(read) == 1
    assert read[0]["document_type"] == "passport"
    assert read[0]["created_at"] is not None


def test_list_by_document_type_reads_the_same_rows_twice_and_writes_nothing(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    migrated_databases: _Databases,
) -> None:
    """A filtered read is a read: asked twice it answers twice.

    The count is read over a *fresh* engine afterwards, so a filter that
    inserted a row on its way past could not be answered out of its own
    uncommitted transaction.
    """
    _write_typed_rows(
        sessions, ("passport", "passport", "visa"), _march((9, 12, 15))
    )

    first = clean_repository.list_by_document_type("passport")
    second = clean_repository.list_by_document_type("passport")

    assert [row.id for row in first] == [row.id for row in second]
    assert _stored_row_count(migrated_databases.primary) == 3


def test_list_by_document_type_reads_only_from_the_database_its_sessions_name(
    sessions: sessionmaker[Session], migrated_databases: _Databases
) -> None:
    """``D42`` holds for the kind read, and the filter is a real one.

    A row in the *other* migrated file carries the kind asked for, so a
    repository reaching for :data:`app.storage.db.SessionLocal`, or asking
    its caller's session rather than its own, would answer it.  Both files
    are emptied first, since earlier tests in this module write to each.
    """
    other_sessions = _fresh_sessions(migrated_databases.other)
    _empty_table(sessions)
    _empty_table(other_sessions)
    written_here = _write_typed_rows(sessions, ("passport",), _march((9,)))
    written_there = _write_typed_rows(
        other_sessions, ("passport", "visa"), _march((9, 12))
    )

    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(other_sessions)

    assert [row.id for row in mine.list_by_document_type("passport")] == [
        written_here[0].id
    ]
    assert [row.id for row in theirs.list_by_document_type("passport")] == [
        written_there[0].id
    ]


def test_the_reads_given_no_window_answer_rows_and_not_a_page(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """Neither read grew bounds, so neither answers a page.

    A range and a kind are sets, and a :class:`ScreeningPage` built from a
    window nobody chose would carry an ``offset`` and a ``limit`` that mean
    nothing.  A caller that needs a window is 11.3's decision to make with
    its own caller in front of it.
    """
    _write_typed_rows(sessions, ("passport",), _march((9,)))
    window = {
        "start": datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        "end": None,
    }

    for found in (
        clean_repository.list_by_date_range(**window),
        clean_repository.list_by_document_type("passport"),
    ):
        assert isinstance(found, tuple)
        assert not hasattr(found, "total")
        assert len(found) == 1


def test_list_by_band_never_answers_a_row_from_another_band(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """8.13's verify: every row on the page carries the band asked for.

    All three bands are written and ``list`` answers all six rows first, so
    the filter cannot pass by matching nothing: a filter that returned the
    whole table, or an empty page, both fail the two assertions below.  The
    page is asked for at ``limit`` well above the match count, so a filter
    that leaked one row from elsewhere would land on this page too.
    """
    written = _write_banded_rows(sessions, ["low", "review", "high", "review"])

    assert clean_repository.list(offset=0, limit=10).total == 4
    page = clean_repository.list_by_band("review", offset=0, limit=10)

    assert {row.band for row in page.rows} == {"review"}
    assert [row.id for row in page.rows] == [
        written[1].id,
        written[3].id,
    ]


def test_list_by_band_reports_the_number_of_rows_that_matched(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The total counts the band asked for, not the table and not the page.

    A ``total`` measured without the filter would answer four here, which is
    the one number 11.3's route cannot page from: three rows read as a table
    of four would render a second page holding nothing.
    """
    _write_banded_rows(sessions, ["low", "review", "high", "review", "low"])

    page = clean_repository.list_by_band("low", offset=0, limit=1)

    assert len(page.rows) == 1
    assert page.total == 2
    assert clean_repository.list(offset=0, limit=10).total == 5


def test_list_by_band_pages_within_the_matched_rows(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """``offset`` and ``limit`` count matched rows, so pages tile the band.

    Four ``review`` rows sit among four others, so an offset applied to the
    table rather than to the band would slide the window and drop or repeat a
    row.  Consecutive pages are the claim a single page cannot make.
    """
    written = _write_banded_rows(
        sessions, ["review", "low", "review", "high", "review", "low", "review"]
    )

    paged = [
        row
        for offset in (0, 2)
        for row in clean_repository.list_by_band(
            "review", offset=offset, limit=2
        ).rows
    ]

    assert [row.id for row in paged] == [
        written[index].id for index in (0, 2, 4, 6)
    ]


def test_list_by_band_orders_by_when_the_row_was_created(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The order is ``list``'s: by ``created_at``, not by write order.

    The same four rows are written newest, oldest, middle, second-newest, so
    a filtered query with no ``ORDER BY`` answers them in exactly the order
    they went in.  ``list``'s own ordering test cannot make this claim: its
    rows are all in one band, and a filter that were missing there too would
    be caught only here.
    """
    _write_banded_rows(
        sessions,
        ["review"] * 4,
        stamps=[
            datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 1, 18, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 1, 15, 0, tzinfo=timezone.utc),
        ],
    )

    page = clean_repository.list_by_band("review", offset=0, limit=10)

    assert [row.filename for row in page.rows] == [
        "passport-page-1.jpg",
        "passport-page-0.jpg",
        "passport-page-3.jpg",
        "passport-page-2.jpg",
    ]


def test_list_by_band_answers_the_rows_nothing_has_scored_yet(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """``None`` asks for the unscored rows, which are rows like any other.

    11.1 creates the row before any stage has run, so ``band`` is ``None``
    on every screening until 7.9's result is written.  A filter that refused
    ``None``, or that answered the whole table for it, would put a second
    query on every route asking what has not been scored.
    """
    written = _write_banded_rows(sessions, [None, "low", None, "review"])

    page = clean_repository.list_by_band(None, offset=0, limit=10)

    assert {row.band for row in page.rows} == {None}
    assert [row.id for row in page.rows] == [written[0].id, written[2].id]
    assert page.total == 2


def test_list_by_band_does_not_check_the_band_against_the_risk_vocabulary(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A name this project has never used is an empty page, not a fault.

    The band is a value a stage wrote, so the filter answers what is stored
    and holds no vocabulary of its own: a repository that validated against
    :mod:`app.risk.bands` would raise instead, and would have to be edited
    every time those bands moved.  The assertion reaching at all is the test.
    """
    _write_banded_rows(sessions, ["low", "review", "high"])

    page = clean_repository.list_by_band("medium", offset=0, limit=10)

    assert page.rows == ()
    assert page.total == 0


@pytest.mark.parametrize(
    ("offset", "limit"),
    [
        pytest.param(-1, 10, id="negative-offset"),
        pytest.param(0, 0, id="no-rows-per-page"),
    ],
)
def test_list_by_band_refuses_bounds_that_describe_no_page(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    offset: int,
    limit: int,
) -> None:
    """The bounds are ``list``'s bounds, refused the same way.

    The table is asked for afterwards, so a filter that queried before it
    checked is caught: a refused call reads nothing, whichever statement
    would have been emitted.
    """
    _write_banded_rows(sessions, ["low", "review"])

    with pytest.raises(ValueError):
        clean_repository.list_by_band("review", offset=offset, limit=limit)

    assert clean_repository.list_by_band(
        "review", offset=0, limit=10
    ).total == 1


def test_the_rows_list_by_band_returns_are_readable_once_its_session_is_closed(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A filtered page hands back detached rows, read in every column.

    The same ``expire_on_commit=False`` (``D36``) precondition as every other
    read here.  Every column is read so a column added later is not a new way
    for this to raise.
    """
    _write_banded_rows(sessions, ["review", "low", "review"])

    page = clean_repository.list_by_band("review", offset=0, limit=10)

    read = [
        {name: getattr(row, name) for name in sorted(ALL_COLUMNS)}
        for row in page.rows
    ]
    assert len(read) == 2
    assert all(row["band"] == "review" for row in read)
    assert all(row["id"] is not None for row in read)
    assert all(row["created_at"] is not None for row in read)


def test_list_by_band_reads_the_same_page_twice_and_writes_nothing(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    migrated_databases: _Databases,
) -> None:
    """A filtered list is a read: asked twice it answers twice.

    The count is read over a *fresh* engine afterwards, so a filter that
    inserted a row on its way past could not be answered out of its own
    uncommitted transaction.
    """
    _write_banded_rows(sessions, ["review", "low", "review"])

    first = clean_repository.list_by_band("review", offset=0, limit=10)
    second = clean_repository.list_by_band("review", offset=0, limit=10)

    assert [row.id for row in first.rows] == [row.id for row in second.rows]
    assert _stored_row_count(migrated_databases.primary) == 3


def test_list_by_band_reads_only_from_the_database_its_sessions_name(
    sessions: sessionmaker[Session], migrated_databases: _Databases
) -> None:
    """``D42`` holds for the filtered read, and the filter is a real one.

    A row in the *other* migrated file carries the band asked for, so a
    repository that reached for :data:`app.storage.db.SessionLocal`, or that
    asked its caller's session rather than its own, would answer it.  The
    local rows prove the second half: the filter excludes everything beside
    them in the database it *does* read.  Both files are emptied first,
    since earlier tests in this module write to each of them and a count is
    only an absolute number against a table this test controls.
    """
    other_sessions = _fresh_sessions(migrated_databases.other)
    _empty_table(sessions)
    _empty_table(other_sessions)
    written_here = _write_banded_rows(sessions, ["review", "low"])
    written_there = _write_banded_rows(other_sessions, ["review"])

    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(other_sessions)

    page = mine.list_by_band("review", offset=0, limit=10)

    assert [row.id for row in page.rows] == [written_here[0].id]
    assert written_there[0].id not in [row.id for row in page.rows]
    assert theirs.list_by_band(
        "review", offset=0, limit=10
    ).total == 1


# --- 8.14: the two reads that were given no window --------------------------

#: The zone the timezone test asks in: 5:30 east, so a bound handed in local
#: time names an instant two hours before the wall time it is written as.
EAST_ISH = timezone(timedelta(hours=5, minutes=30))


def _march(hours: Sequence[int]) -> list[datetime]:
    """``created_at`` stamps on 1 March 2026, one per hour of ``hours``.

    A stamp the test chose rather than one it waited for, because ``create``
    stamps the clock itself and takes no timestamp.
    """
    return [
        datetime(2026, 3, 1, hour, 0, tzinfo=timezone.utc) for hour in hours
    ]


def _write_typed_rows(
    sessions: sessionmaker[Session],
    types: Sequence[str],
    stamps: Sequence[datetime],
) -> list[Screening]:
    """Write one row per entry of ``types``, stamped with ``stamps``.

    :param sessions: the factory the rows are written through.
    :param types: the ``document_type`` each row carries.
    :param stamps: the ``created_at`` each row is stamped with.
    :returns: the rows, in the order they were written rather than the order
        they will be read back in.
    """
    with sessions() as session:
        rows = [
            Screening(
                document_type=doc_type,
                filename=f"{doc_type}-{index}.jpg",
                image_width=1240,
                image_height=1754,
                created_at=stamp,
            )
            for index, (doc_type, stamp) in enumerate(zip(types, stamps))
        ]
        session.add_all(rows)
        session.commit()
    return rows


# --- 8.15: the delete, and the one rule every read carries ------------------

#: The instant ``soft_delete`` is handed, chosen by the test rather than
#: waited for: the repository reads no clock, so the stamp is the caller's.
DELETED_AT = datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)

#: A second instant, for the claim that a row is deleted once.
LATER_STAMP = datetime(2026, 10, 2, 11, 0, tzinfo=timezone.utc)


def _stored(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> Any:
    """Read one row back directly, soft-deleted or not.

    Every claim about what a delete *kept* needs a read that does not go
    through the rule under test, so this asks the table rather than ``get``.
    """
    with sessions() as session:
        return session.get(Screening, screening_id)


def _as_utc(moment: datetime) -> datetime:
    """``moment`` as SQLite hands it back, for comparison with a stored one.

    SQLite's ``DATETIME`` drops the offset rather than applying it, so a
    stamp read back carries no ``tzinfo`` and names the instant it was stored
    as only once it is labelled UTC.
    """
    return moment.replace(tzinfo=timezone.utc)


def test_soft_delete_stamps_the_row_it_names_and_returns_it(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """8.15's verify: the row carries ``deleted_at`` once the call returns.

    Read back over a session rather than off the return value, so a method
    that stamped the instance it was holding without committing would fail
    here instead of answering a row no other session can find.
    """
    written = clean_repository.create(**AN_UPLOAD)

    returned = clean_repository.soft_delete(written.id, deleted_at=DELETED_AT)

    assert returned is not None
    assert returned.id == written.id
    assert _as_utc(_stored(sessions, written.id).deleted_at) == DELETED_AT


def test_soft_delete_stamps_the_row_and_leaves_it_in_the_table(
    clean_repository: ScreeningRepository,
    migrated_databases: _Databases,
) -> None:
    """Nothing is removed: the row is still there for the audit view.

    Counted over a fresh engine, so a delete that issued a ``DELETE`` -- or
    one that rolled back and left no row behind at all -- fails here.
    """
    written = _write_rows(clean_repository, 3)
    before = _stored_row_count(migrated_databases.primary)

    clean_repository.soft_delete(written[1].id, deleted_at=DELETED_AT)

    assert _stored_row_count(migrated_databases.primary) == before == 3


def test_soft_delete_writes_the_stamp_and_nothing_else(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A deleted row is still a record: its upload and its band stand.

    Every column but the one the method may write is compared, so a delete
    that also cleared the row -- and left the audit view and 9.17's
    verification nothing to check -- fails rather than passing.
    """
    [written] = _write_banded_rows(sessions, ["review"])
    before = {
        name: getattr(_stored(sessions, written.id), name)
        for name in sorted(ALL_COLUMNS)
    }
    before.pop("deleted_at")

    clean_repository.soft_delete(written.id, deleted_at=DELETED_AT)

    stored = _stored(sessions, written.id)
    after = {name: getattr(stored, name) for name in sorted(ALL_COLUMNS)}
    after.pop("deleted_at")
    assert after == before


def test_get_answers_none_for_a_row_that_has_been_soft_deleted(
    clean_repository: ScreeningRepository,
) -> None:
    """``get`` is a read like the others, so it carries the same rule.

    ``None`` is the one answer to "is there a screening with this id now",
    whether the row was never written or was deleted, and a caller cannot
    tell the two apart because the table does not offer a way to.
    """
    written = clean_repository.create(**AN_UPLOAD)

    clean_repository.soft_delete(written.id, deleted_at=DELETED_AT)

    assert clean_repository.get(written.id) is None


def test_get_answers_the_row_a_delete_is_about_to_be_asked_about(
    clean_repository: ScreeningRepository,
) -> None:
    """24.5 confirms the row it is about to delete, and this rule spares it.

    The read happens *before* the delete, so the one caller that needs a row
    the delete is aimed at is not the caller this rule was written against.
    """
    written = clean_repository.create(**AN_UPLOAD)

    confirmed = clean_repository.get(written.id)
    clean_repository.soft_delete(written.id, deleted_at=DELETED_AT)

    assert confirmed is not None
    assert confirmed.id == written.id
    assert clean_repository.get(written.id) is None


def test_list_never_answers_a_soft_deleted_row(
    clean_repository: ScreeningRepository,
) -> None:
    """The whole table on one page, with the deleted row missing from it.

    Five rows are written and one deleted, so a filter that answered the
    whole table fails and one that answered nothing fails too -- the four
    live rows are named individually.
    """
    written = _write_rows(clean_repository, ROWS_ON_TEST)

    clean_repository.soft_delete(written[2].id, deleted_at=DELETED_AT)
    page = clean_repository.list(offset=0, limit=ROWS_ON_TEST)

    assert [row.id for row in page.rows] == [
        written[0].id,
        written[1].id,
        written[3].id,
        written[4].id,
    ]


def test_a_total_counts_the_rows_the_read_can_reach_and_not_the_table(
    clean_repository: ScreeningRepository,
) -> None:
    """The count moves with the filter, or 11.3's route pages past nothing.

    Two rows are deleted from five, so a total measured over the table would
    render a second page holding one row nobody can see.
    """
    written = _write_rows(clean_repository, ROWS_ON_TEST)

    clean_repository.soft_delete(written[0].id, deleted_at=DELETED_AT)
    clean_repository.soft_delete(written[4].id, deleted_at=DELETED_AT)
    page = clean_repository.list(offset=0, limit=ROWS_ON_TEST)

    assert page.total == 3
    assert len(page.rows) == page.total


def test_a_page_is_taken_over_the_live_rows_so_a_deleted_one_does_not_shift_it(
    clean_repository: ScreeningRepository,
) -> None:
    """``offset`` counts rows the read can reach, or the window slides.

    The first row is deleted, so an offset applied to the table rather than
    to the live rows would start the page one row late and drop the first
    live row off the end of the history.
    """
    written = _write_rows(clean_repository, ROWS_ON_TEST)

    clean_repository.soft_delete(written[0].id, deleted_at=DELETED_AT)
    page = clean_repository.list(offset=0, limit=2)

    assert [row.id for row in page.rows] == [written[1].id, written[2].id]


def test_list_by_band_never_answers_a_soft_deleted_row(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The band a row carried before the delete does not keep it on a page.

    The deleted row's band is asked for on its own, so an empty page with a
    total of one would fail; the band holding two live rows is asked for too,
    so a filter that answered nothing fails as well.
    """
    written = _write_banded_rows(sessions, ["low", "high", "low"])

    clean_repository.soft_delete(written[1].id, deleted_at=DELETED_AT)
    deleted_band = clean_repository.list_by_band("high", offset=0, limit=10)
    live_band = clean_repository.list_by_band("low", offset=0, limit=10)

    assert deleted_band.rows == ()
    assert deleted_band.total == 0
    assert [row.id for row in live_band.rows] == [written[0].id, written[2].id]
    assert live_band.total == 2


def test_list_by_date_range_never_answers_a_soft_deleted_row(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A row stamped inside the range is inside it however it was deleted.

    The range covers every row written and only the middle one is deleted, so
    the answer is both narrower than the range and wider than nothing.
    """
    stamps = _march([0, 1, 2, 3])
    written = _write_typed_rows(sessions, ["passport"] * 4, stamps)

    clean_repository.soft_delete(written[1].id, deleted_at=DELETED_AT)
    inside = clean_repository.list_by_date_range(stamps[0], stamps[3])

    assert [row.id for row in inside] == [
        written[0].id,
        written[2].id,
        written[3].id,
    ]


def test_list_by_document_type_never_answers_a_soft_deleted_row(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The kind an upload claimed does not keep a deleted row on the answer.

    Two rows of the kind are written and one deleted, and a row of another
    kind is written beside them, so a filter that answered everything, or
    nothing, fails against either.
    """
    stamps = _march([0, 1, 2])
    written = _write_typed_rows(
        sessions, ["passport", "passport", "visa"], stamps
    )

    clean_repository.soft_delete(written[0].id, deleted_at=DELETED_AT)

    assert [
        row.id for row in clean_repository.list_by_document_type("passport")
    ] == [written[1].id]
    assert [
        row.id for row in clean_repository.list_by_document_type("visa")
    ] == [written[2].id]


def test_soft_delete_answers_none_for_an_id_no_row_carries(
    clean_repository: ScreeningRepository,
) -> None:
    """Absence is an answer here too, and the live row beside it is untouched.

    An id no row carries is a stranger's stale link.  A second row is written
    and still readable afterwards, so a delete that committed an empty
    transaction over the whole table would fail.
    """
    written = clean_repository.create(**AN_UPLOAD)

    assert clean_repository.soft_delete(uuid.uuid4(), deleted_at=DELETED_AT) is None
    assert clean_repository.get(written.id) is not None


def test_a_row_is_deleted_once_and_a_second_delete_keeps_the_first_stamp(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """The second delete answers absence rather than re-stamping the row.

    Re-stamping silently would be the one that loses the trail: when it was
    deleted is a fact about the past, and two clicks an hour apart would
    leave only the second one on the row.
    """
    written = clean_repository.create(**AN_UPLOAD)
    clean_repository.soft_delete(written.id, deleted_at=DELETED_AT)

    second = clean_repository.soft_delete(written.id, deleted_at=LATER_STAMP)

    assert second is None
    assert _as_utc(_stored(sessions, written.id).deleted_at) == DELETED_AT


def test_soft_delete_refuses_a_stamp_that_carries_no_timezone(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A naive stamp is one instant on SQLite and another on PostgreSQL.

    ``D46``'s reasoning, applied to the column rather than to a bound: the
    refusal happens before any statement, so the row is still live and still
    readable afterwards.
    """
    written = clean_repository.create(**AN_UPLOAD)

    with pytest.raises(ValueError):
        clean_repository.soft_delete(
            written.id, deleted_at=DELETED_AT.replace(tzinfo=None)
        )

    assert _stored(sessions, written.id).deleted_at is None
    assert clean_repository.get(written.id) is not None


def test_soft_delete_stores_the_instant_the_stamp_names_not_the_wall_time(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A stamp written in another zone is the instant it names.

    The same instant is handed in two spellings -- as UTC, and as the local
    time of a zone five and a half hours east -- so a delete that stored the
    value as written would come back five and a half hours out, on the same
    reasoning 8.14 measured for a date-range bound.
    """
    written = clean_repository.create(**AN_UPLOAD)

    clean_repository.soft_delete(
        written.id, deleted_at=DELETED_AT.astimezone(EAST_ISH)
    )

    stored = _stored(sessions, written.id).deleted_at
    assert _as_utc(stored) == DELETED_AT
    assert stored != DELETED_AT.astimezone(EAST_ISH).replace(tzinfo=None)


def test_the_row_soft_delete_returns_is_readable_once_its_session_is_closed(
    clean_repository: ScreeningRepository,
) -> None:
    """``expire_on_commit=False`` (``D36``), measured by reading every column.

    ``soft_delete`` opens, writes, commits and closes inside the call, so
    the instance it returns is detached.  Every column is read because a
    column added later must not become a new way for this to raise.
    """
    written = clean_repository.create(**AN_UPLOAD)

    returned = clean_repository.soft_delete(written.id, deleted_at=DELETED_AT)

    read = {name: getattr(returned, name) for name in sorted(ALL_COLUMNS)}
    assert read["id"] == written.id
    assert read["created_at"] is not None
    assert read["status"] == DEFAULT_SCREENING_STATUS
    assert _as_utc(read["deleted_at"]) == DELETED_AT


def test_soft_delete_writes_only_to_the_database_its_sessions_name(
    sessions: sessionmaker[Session],
    migrated_databases: _Databases,
) -> None:
    """``D42`` holds for the delete too: it cannot reach the other file.

    A repository handed the second factory is asked to delete a row that
    lives in the first, so a delete reaching for
    :data:`app.storage.db.SessionLocal` -- or for its caller's session --
    would stamp a row it was never asked about.
    """
    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(_fresh_sessions(migrated_databases.other))
    written_by_me = mine.create(**AN_UPLOAD)

    assert theirs.soft_delete(written_by_me.id, deleted_at=DELETED_AT) is None
    assert _stored(sessions, written_by_me.id).deleted_at is None


# --- 11.3: one page, three filters, one count -------------------------------

#: Six rows as ``(kind, band, hour)``, in the order they are *written* -- which
#: is not the order they are read back in, so a read with no ``ORDER BY``
#: fails rather than agreeing with insertion by accident.  Every band and
#: every kind is here, so a filter answering all six, or none, fails.
MIXED_WRITES = (
    ("national-id", "review", 3),
    ("passport", "low", 0),
    ("visa", "high", 5),
    ("national-id", None, 4),
    ("passport", "review", 1),
    ("visa", "low", 2),
)


def _write_mixed_rows(sessions: sessionmaker[Session]) -> list[Screening]:
    """Write :data:`MIXED_WRITES`, stamped an hour apart, in write order.

    :returns: the rows in the order they were written, so a test asserting
        the read order has to say which order it means.
    """
    with sessions() as session:
        rows = [
            Screening(
                document_type=kind,
                filename=f"{kind}-{hour}.jpg",
                image_width=1240,
                image_height=1754,
                band=band,
                created_at=_march([hour])[0],
            )
            for kind, band, hour in MIXED_WRITES
        ]
        session.add_all(rows)
        session.commit()
    return rows


def _by_hour(rows: Sequence[Screening]) -> list[int]:
    """The hour of each row's ``created_at``, for a read-order assertion."""
    return [row.created_at.hour for row in rows]


def test_list_matching_answers_the_rows_every_given_filter_matches(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """11.3's own claim: one filter at a time matches more than all three.

    Each filter alone is answered first, so a composed read that ignored one
    of them answers the table and fails, and one that answered nothing fails
    rather than passing an assertion of emptiness.
    """
    written = _write_mixed_rows(sessions)
    by_hour = {row.created_at.hour: row for row in written}
    window = {"start": _march([1])[0], "end": _march([4])[0]}

    band_only = clean_repository.list_matching(band="low", offset=0, limit=10)
    kind_only = clean_repository.list_matching(
        document_type="visa", offset=0, limit=10
    )
    window_only = clean_repository.list_matching(**window, offset=0, limit=10)
    all_three = clean_repository.list_matching(
        band="low", document_type="visa", **window, offset=0, limit=10
    )

    assert (_by_hour(band_only.rows), band_only.total) == ([0, 2], 2)
    assert (_by_hour(kind_only.rows), kind_only.total) == ([2, 5], 2)
    assert (_by_hour(window_only.rows), window_only.total) == ([1, 2, 3, 4], 4)
    assert (_by_hour(all_three.rows), all_three.total) == ([2], 1)
    assert all_three.rows[0].id == by_hour[2].id


def test_list_matching_given_no_filter_answers_what_list_answers(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A filter left ``None`` is not applied, so the window is the whole table.

    Both are asked for and compared row for row, so a composed read reaching
    for a condition ``list`` does not apply -- or dropping the order while
    composing -- fails here rather than at the route.
    """
    _write_mixed_rows(sessions)

    composed = clean_repository.list_matching(offset=0, limit=10)
    plain = clean_repository.list(offset=0, limit=10)

    assert [row.id for row in composed.rows] == [row.id for row in plain.rows]
    assert composed.total == plain.total
    assert _by_hour(composed.rows) == [0, 1, 2, 3, 4, 5]


def test_list_matching_pages_over_the_matched_rows(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A window taken over the table would shift the page under a filter."""
    _write_mixed_rows(sessions)

    first = clean_repository.list_matching(band="low", offset=0, limit=1)
    second = clean_repository.list_matching(band="low", offset=1, limit=1)
    past = clean_repository.list_matching(band="low", offset=2, limit=1)

    assert (_by_hour(first.rows), first.total) == ([0], 2)
    assert (_by_hour(second.rows), second.total) == ([2], 2)
    assert (past.rows, past.total, len(past)) == ((), 2, 0)
    assert (past.offset, past.limit) == (2, 1)


def test_list_matching_does_not_check_a_band_or_a_kind_against_a_vocabulary(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """A name no row carries is an empty page, as on the reads it composes."""
    _write_mixed_rows(sessions)

    for page in (
        clean_repository.list_matching(
            band="a-band-this-service-has-never-written", offset=0, limit=10
        ),
        clean_repository.list_matching(
            document_type="travel-permit", offset=0, limit=10
        ),
    ):
        assert (page.rows, page.total) == ((), 0)


def test_list_matching_never_answers_a_soft_deleted_row_and_does_not_count_it(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """8.15's rule again, this time with the other filters applied as well."""
    written = _write_mixed_rows(sessions)
    deleted = next(row for row in written if row.created_at.hour == 3)
    clean_repository.soft_delete(deleted.id, deleted_at=DELETED_AT)

    page = clean_repository.list_matching(band="review", offset=0, limit=10)

    assert _by_hour(page.rows) == [1]
    assert page.total == 1
    assert clean_repository.list_matching(offset=0, limit=10).total == 5


@pytest.mark.parametrize(
    ("offset", "limit"),
    [
        pytest.param(-1, 10, id="negative-offset"),
        pytest.param(0, 0, id="no-rows-per-page"),
    ],
)
def test_list_matching_refuses_bounds_that_describe_no_page(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    offset: int,
    limit: int,
) -> None:
    """A refused call reads nothing, on :meth:`list`'s reasoning."""
    _write_mixed_rows(sessions)

    with pytest.raises(ValueError):
        clean_repository.list_matching(offset=offset, limit=limit)

    assert clean_repository.list_matching(offset=0, limit=10).total == len(
        MIXED_WRITES
    )


def test_list_matching_refuses_a_range_that_names_no_range(
    clean_repository: ScreeningRepository, sessions: sessionmaker[Session]
) -> None:
    """An inverted range and a naive bound, as 8.14's read refuses them.

    Both ends open is not in this list: leaving both out is how a caller asks
    for no date filter at all, which is the whole table rather than a fault.
    """
    _write_mixed_rows(sessions)
    hours = _march(range(6))

    with pytest.raises(ValueError):
        clean_repository.list_matching(
            start=hours[4], end=hours[1], offset=0, limit=10
        )
    with pytest.raises(ValueError):
        clean_repository.list_matching(
            start=hours[1].replace(tzinfo=None), offset=0, limit=10
        )

    assert clean_repository.list_matching(offset=0, limit=10).total == len(
        MIXED_WRITES
    )


def test_list_matching_reads_the_same_page_twice_and_writes_nothing(
    clean_repository: ScreeningRepository,
    sessions: sessionmaker[Session],
    migrated_databases: _Databases,
) -> None:
    """A composed read is a read: asked twice it answers twice, and adds no row."""
    _write_mixed_rows(sessions)
    window = {"band": "low", "document_type": "visa"}

    first = clean_repository.list_matching(**window, offset=0, limit=10)
    second = clean_repository.list_matching(**window, offset=0, limit=10)

    assert [row.id for row in first.rows] == [row.id for row in second.rows]
    with _fresh_sessions(migrated_databases.primary)() as fresh:
        assert fresh.execute(
            select(func.count()).select_from(Screening)
        ).scalar_one() == len(MIXED_WRITES)


def test_list_matching_reads_only_from_the_database_its_sessions_name(
    sessions: sessionmaker[Session],
    migrated_databases: _Databases,
) -> None:
    """``D42`` holds for the composed read: it cannot reach the other file.

    Each file is given a kind of its own, so the two answers are about the
    rows the other repository wrote rather than about whatever an earlier
    test left behind in either file.
    """
    mine = ScreeningRepository(sessions)
    theirs = ScreeningRepository(_fresh_sessions(migrated_databases.other))
    with sessions() as session:
        _write_one_row(session, "only-here")
    with _fresh_sessions(migrated_databases.other)() as other:
        _write_one_row(other, "only-there")

    assert mine.list_matching(
        document_type="only-here", offset=0, limit=10
    ).total == 1
    assert mine.list_matching(
        document_type="only-there", offset=0, limit=10
    ).total == 0
    assert theirs.list_matching(
        document_type="only-there", offset=0, limit=10
    ).total == 1
    assert theirs.list_matching(
        document_type="only-here", offset=0, limit=10
    ).total == 0


def _write_one_row(session: Session, document_type: str) -> None:
    """Write one row of ``document_type`` through ``session``, and commit."""
    session.add(
        Screening(
            document_type=document_type,
            filename=f"{document_type}.jpg",
            image_width=1240,
            image_height=1754,
            created_at=_march([0])[0],
        )
    )
    session.commit()
