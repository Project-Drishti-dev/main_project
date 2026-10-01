"""8.7: the two indexes on ``screenings``, read back out of a created schema.

The task's verify is "a test that the indexes exist in the created schema",
and this file is that plus the four claims the pair is worth having:

- **the created schema, not the declaration.**  An :class:`~sqlalchemy.Index`
  object sitting in ``Base.metadata`` is a claim about the mapping; an
  index a reflection reports is a claim about the database 8.8's migration
  will create.  The two can disagree, so every claim here is read with
  :func:`sqlalchemy.inspect` against a database ``create_all`` built.
- **the names are the naming convention's, not a pair written out by
  hand.**  8.8's ``downgrade`` has to drop exactly what ``upgrade``
  created, so each name is recomputed from
  :data:`app.storage.models.NAMING_CONVENTION` and compared against the one
  the database reports.
- **an index is an accelerator and not a constraint.**  ``band`` is
  ``None`` on every row no stage has scored and two screenings can share an
  instant, so ``unique=True`` on either column would refuse rows this table
  is meant to hold.
- **neither index decides anything.**  A filter on ``band`` returns the
  rows of that band and no row whose band is still ``None`` -- 8.13's
  question, and not one this task answers.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import Engine, Index, inspect, select
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable

from app.storage import db
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    LEDGER_ENTRY_TABLE_NAME,
    NAMING_CONVENTION,
    SCREENING_TABLE_NAME,
    Base,
    Screening,
)


#: The two columns 8.7 names an index on, in the task's order.  Written once
#: here so the tests can be driven from the task rather than from the model:
#: restating the model's own declarations beside them would pass on a table
#: whose indexes were both on the wrong column.
THE_INDEXED_COLUMNS = ("created_at", "band")


@pytest.fixture
def in_memory_engine() -> Iterator[Engine]:
    """One in-memory SQLite database with the schema created in it.

    Built through :func:`~app.storage.db.build_engine`, as 8.4's and 8.5's
    suites do, so the URL the service is configured with is the URL this
    suite reflects an index out of.  Disposed at the end, so a test that
    leaves a connection open cannot reach the next one.
    """
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def sessions(in_memory_engine: Engine) -> sessionmaker[Session]:
    """A session factory over :func:`in_memory_engine`, and nothing else."""
    return db.build_session_factory(in_memory_engine)


def _an_upload(**overrides: Any) -> Screening:
    """A row carrying what an upload carried, and what the caller adds."""
    fields: dict[str, Any] = {
        "document_type": "passport",
        "filename": "passport-page.jpg",
        "image_width": 1240,
        "image_height": 1754,
    }
    fields.update(overrides)
    return Screening(**fields)


def _name_the_convention_would_give(column: str) -> str:
    """The index name :data:`NAMING_CONVENTION` produces for one column."""
    return NAMING_CONVENTION["ix"] % {
        "table_name": SCREENING_TABLE_NAME,
        "column_0_N_name": column,
    }


def _the_declared_index(column: str) -> Index:
    """The :class:`~sqlalchemy.Index` this table declares over one column.

    ``Table.indexes`` is a set rather than a mapping, so it is looked up by
    name here -- and the name it is looked up under is the one the
    convention produces, which is what makes a missing index a lookup
    failure rather than an empty result.
    """
    wanted = _name_the_convention_would_give(column)
    for index in Screening.__table__.indexes:
        if index.name == wanted:
            return index
    raise AssertionError(f"{SCREENING_TABLE_NAME} declares no index {wanted}")


# --- the claim the task's verify names ------------------------------------


@pytest.mark.parametrize("column", THE_INDEXED_COLUMNS)
def test_the_created_schema_carries_an_index_on_the_column(
    column: str, in_memory_engine: Engine
) -> None:
    """The index is in the database ``create_all`` built, which is the claim
    the task's verify asks for.

    Measured through reflection rather than through ``Base.metadata``,
    because an ``Index`` object in the mapping is not yet an index in a
    schema -- and 8.8 creates the schema from the migration, not from the
    mapping.
    """
    reported = {
        index["name"]: index
        for index in inspect(in_memory_engine).get_indexes(SCREENING_TABLE_NAME)
    }

    assert _name_the_convention_would_give(column) in reported
    assert reported[_name_the_convention_would_give(column)]["column_names"] == [
        column
    ]


@pytest.mark.parametrize("column", THE_INDEXED_COLUMNS)
def test_the_index_is_a_statement_of_its_own(column: str) -> None:
    """An index is not inside ``CREATE TABLE``, so 8.8's migration needs an
    ``op.create_index`` beside its ``op.create_table``.

    Measured rather than assumed: a dialect that folded indexes into the
    table would make a migration that only creates the table complete, and
    a ``downgrade`` would find nothing to drop.  Compiled against the SQLite
    dialect this service runs on by default; the claim is about the shape of
    the DDL, and SQLite is where 8.9's round trip happens.
    """
    dialect = sqlite.dialect()
    table_ddl = str(CreateTable(Screening.__table__).compile(dialect=dialect))
    index = _the_declared_index(column)
    index_ddl = str(CreateIndex(index).compile(dialect=dialect))

    assert "CREATE INDEX" not in table_ddl
    assert index_ddl == (
        f"CREATE INDEX {_name_the_convention_would_give(column)} "
        f"ON {SCREENING_TABLE_NAME} ({column})"
    )


# --- the names 8.8's downgrade drops by -----------------------------------


@pytest.mark.parametrize("column", THE_INDEXED_COLUMNS)
def test_the_index_is_named_by_the_convention(column: str) -> None:
    """The name is the convention's, so it cannot drift from the table's and
    8.8's ``downgrade`` can drop exactly what ``upgrade`` created."""
    index = _the_declared_index(column)

    assert index.name == f"ix_{SCREENING_TABLE_NAME}_{column}"
    assert index.table is Screening.__table__


def test_the_table_declares_no_third_index() -> None:
    """Exactly the two the task names, on the one table a query filters.

    A third index here would be a claim about scale nothing measures --
    ``id`` in particular is already covered by the primary key, and
    :attr:`Screening.filename` is deliberately never indexed because it
    carries caller-supplied text.  Neither of the other two tables gets one
    either: ``audit_events`` is read by ``screening_id`` and
    ``ledger_entries`` by ``sequence``, and both are primary keys.
    """
    assert {index.name for index in Screening.__table__.indexes} == {
        _name_the_convention_would_give(column) for column in THE_INDEXED_COLUMNS
    }
    assert all(
        not Base.metadata.tables[table_name].indexes
        for table_name in (AUDIT_EVENT_TABLE_NAME, LEDGER_ENTRY_TABLE_NAME)
    )


# --- an index is not a constraint ----------------------------------------


@pytest.mark.parametrize("column", THE_INDEXED_COLUMNS)
def test_no_index_is_unique(column: str, in_memory_engine: Engine) -> None:
    """Neither index constrains a value, so the claim is held against the
    schema rather than only against a write.

    ``unique=True`` on ``band`` would refuse the second screening of a
    band -- which is the normal case -- and on ``created_at`` would refuse
    two screenings written in the same instant, which is also the normal
    case at a queue's speed.
    """
    reported = {
        index["name"]: index
        for index in inspect(in_memory_engine).get_indexes(SCREENING_TABLE_NAME)
    }

    # SQLite reflection reports ``0``/``1`` rather than ``False``/``True``,
    # so the claim is that no uniqueness was reflected, not that a
    # particular spelling of it came back.
    assert not reported[_name_the_convention_would_give(column)]["unique"]


def test_two_rows_sharing_a_band_and_an_instant_are_both_written(
    sessions: sessionmaker[Session],
) -> None:
    """The write that a unique index would refuse, written and read back.

    Both rows carry the same ``created_at`` and the same band and differ
    only in what the upload carried, so a unique index on either column
    would fail this insert rather than merely reading oddly afterwards.
    """
    instant = datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)

    with sessions() as session:
        session.add_all(
            [
                _an_upload(band="review", created_at=instant),
                _an_upload(band="review", created_at=instant),
            ]
        )
        session.commit()

    with sessions() as session:
        rows = (
            session.execute(
                select(Screening).where(Screening.band == "review")
            )
            .scalars()
            .all()
        )

    assert len(rows) == 2
    assert {row.created_at.replace(tzinfo=timezone.utc) for row in rows} == {
        instant
    }


def test_a_row_with_no_band_is_indexed_too(
    sessions: sessionmaker[Session],
) -> None:
    """A ``None`` band is a value the index holds rather than a row it
    refuses: 11.1 creates a row before anything has scored it."""
    with sessions() as session:
        session.add(_an_upload())
        session.commit()

    with sessions() as session:
        row = session.execute(select(Screening)).scalars().one()

    assert row.band is None


# --- an index decides nothing --------------------------------------------


def test_a_band_filter_returns_that_band_and_nothing_else(
    sessions: sessionmaker[Session],
) -> None:
    """The band index is a hint about how to find rows, never a rule about
    which rows exist: three bands and one unscored row in, one band out."""
    with sessions() as session:
        session.add_all(
            [
                _an_upload(band="low", filename="a.jpg"),
                _an_upload(band="review", filename="b.jpg"),
                _an_upload(band="high", filename="c.jpg"),
                _an_upload(band=None, filename="d.jpg"),
            ]
        )
        session.commit()

    with sessions() as session:
        rows = (
            session.execute(
                select(Screening).where(Screening.band == "review")
            )
            .scalars()
            .all()
        )
        unscored = (
            session.execute(select(Screening).where(Screening.band.is_(None)))
            .scalars()
            .all()
        )

    assert [row.filename for row in rows] == ["b.jpg"]
    assert [row.filename for row in unscored] == ["d.jpg"]
