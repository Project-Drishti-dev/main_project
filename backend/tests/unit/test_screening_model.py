"""8.4: the declarative ``Base``, the ``Screening`` row, and one in-memory
database they can be read back out of.

The task's verify is "a test creates and reads back a row in an in-memory DB",
and this file is that plus the four claims the row is worth having:

- **the read back is a second session, not the one that wrote.** A row held
  by an open session proves nothing was serialised; the read is a fresh
  session against the same database, which is what a repository method
  (8.10) and a request handler do.
- **one in-memory database is one database.** The default pool for
  ``sqlite://`` is a per-thread one, so a second thread would find an empty
  database rather than the row -- which is asserted here by reading it from
  a thread, and is what ``build_engine``'s ``StaticPool`` answers.
- **the row is the sixteen columns the task names, in that order, and no
  others.** The claim is held against the table's own column list rather
  than against the model class, so a column added for a field nobody named
  -- an officer's decision, an outcome -- fails here.
- **a row exists before the analysis does.** 11.1 hands back an id
  immediately, so the nine result columns and ``deleted_at`` are ``None`` on
  a row that has only been uploaded, and only ``document_type``,
  ``filename`` and the two dimensions are required.
"""

import pathlib
import threading
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, get_args, get_type_hints

import pytest
from sqlalchemy import LargeBinary, Uuid, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.schema import CreateTable

from app.schemas import AnalysisResponse, ModuleResult
from app.storage import db
from app.storage.models import (
    DEFAULT_SCREENING_STATUS,
    NAMING_CONVENTION,
    SCREENING_MODES,
    SCREENING_STATUSES,
    SCREENING_TABLE_NAME,
    TRAVELER_CASE_TABLE_NAME,
    Base,
    Screening,
)


#: The columns 8.4 names, in the order it names them.  Held as one tuple so
#: the table's own column list is checked against a list written once here:
#: restating the model's fields beside the model's fields would pass on a
#: table that had grown one.
THE_TASK_S_COLUMNS = (
    "id",
    "created_at",
    "document_type",
    "status",
    "score",
    "band",
    "mode",
    "filename",
    "image_width",
    "image_height",
    "ruleset_version",
    "model_versions",
    "quality",
    "flags",
    "summary",
    "deleted_at",
)

#: The columns a caller cannot write a row without: what the upload carried.
REQUIRED_ON_INSERT = (
    "document_type",
    "filename",
    "image_width",
    "image_height",
)

#: The columns the cascade fills in, and the two lifecycle stamps.  All of
#: them ``None`` on a row nothing has analysed yet.
FILLED_BY_A_STAGE = (
    "score",
    "band",
    "mode",
    "ruleset_version",
    "model_versions",
    "quality",
    "flags",
    "summary",
    "deleted_at",
)

#: The three ORMs-written defaults, named so the "nothing else is written"
#: claim below has a list to be checked against.
DEFAULTED_COLUMNS = ("id", "created_at", "status")


@pytest.fixture
def in_memory_engine() -> Iterator[Engine]:
    """One in-memory SQLite database with the schema created in it.

    Built through :func:`~app.storage.db.build_engine` rather than through
    ``create_engine``, so the URL the service is configured with is the URL
    this suite exercises.  Disposed at the end, so a test that leaves a
    connection open cannot reach the next one.
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
    """A row carrying what an upload carried, and nothing a stage has read."""
    fields: dict[str, Any] = {
        "document_type": "passport",
        "filename": "passport-page.jpg",
        "image_width": 1240,
        "image_height": 1754,
    }
    fields.update(overrides)
    return Screening(**fields)


# --- the row, written and read back --------------------------------------


def test_a_row_written_to_an_in_memory_database_is_read_back(
    sessions: sessionmaker[Session],
) -> None:
    """8.4's verify, and the read is a second session on purpose.

    The first session is closed before the second one opens, so nothing here
    can be answered out of the identity map of the session that wrote the
    row: the value came back through the database or it did not come back.
    """
    with sessions() as session:
        session.add(_an_upload())
        session.commit()

    with sessions() as session:
        rows = session.execute(select(Screening)).scalars().all()

    assert len(rows) == 1
    assert rows[0].document_type == "passport"
    assert rows[0].filename == "passport-page.jpg"
    assert (rows[0].image_width, rows[0].image_height) == (1240, 1754)


def test_a_row_survives_the_session_that_wrote_it_closing(
    sessions: sessionmaker[Session],
) -> None:
    """``expire_on_commit=False`` (``D36``) is what makes the object readable
    after the block a repository method writes it in has closed."""
    with sessions() as session:
        written = _an_upload()
        session.add(written)
        session.commit()

    assert written.id is not None
    assert written.created_at is not None
    assert written.status == DEFAULT_SCREENING_STATUS


def test_a_written_row_can_be_fetched_by_its_own_id(
    sessions: sessionmaker[Session],
) -> None:
    """11.2 reads one screening by id, so the primary key is what it will
    read it with."""
    with sessions() as session:
        written = _an_upload()
        other = _an_upload(document_type="visa", filename="visa.png")
        session.add_all((written, other))
        session.commit()

    with sessions() as session:
        found = session.get(Screening, written.id)

    assert found is not None
    assert found.id == written.id
    assert found.document_type == "passport"


# --- the in-memory database is one database ------------------------------


def test_an_in_memory_url_is_given_a_one_connection_pool() -> None:
    """``D37`` accepts ``sqlite://``, and the dialect's own answer for it is
    a pool per thread -- each thread a separate empty database."""
    assert isinstance(db.build_engine("sqlite://").pool, StaticPool)
    assert isinstance(db.build_engine("sqlite:///:memory:").pool, StaticPool)


def test_a_row_written_on_one_thread_is_readable_on_another(
    in_memory_engine: Engine,
) -> None:
    """The claim the pool exists for, measured rather than described.

    With SQLAlchemy's default pool for a memory URL, this read finds
    ``no such table: screenings``, because the second thread opened its own
    connection to its own empty database.
    """
    factory = db.build_session_factory(in_memory_engine)
    with factory() as session:
        session.add(_an_upload())
        session.commit()

    found: list[int] = []

    def read_it() -> None:
        with factory() as session:
            found.append(
                len(session.execute(select(Screening)).scalars().all())
            )

    reader = threading.Thread(target=read_it)
    reader.start()
    reader.join()

    assert found == [1]


def test_a_file_url_keeps_the_pool_its_dialect_ships(
    tmp_path: pathlib.Path,
) -> None:
    """The decision is about in-memory URLs only, so a file is untouched."""
    engine = db.build_engine(f"sqlite:///{(tmp_path / 'pooled.db').as_posix()}")
    try:
        assert not isinstance(engine.pool, StaticPool)
        assert isinstance(engine.pool, QueuePool)
    finally:
        engine.dispose()


def test_a_non_sqlite_url_is_never_given_the_in_memory_pool() -> None:
    """A URL with no driver installed still parses, which is ``D37``'s claim
    and the reason the question is asked of the parsed URL."""
    assert db._is_in_memory_sqlite("postgresql://user@host/drishti") is False
    assert db._is_in_memory_sqlite("postgresql:///drishti") is False


# --- the columns, and only the columns -----------------------------------


def test_the_table_carries_exactly_the_columns_the_task_names() -> None:
    assert tuple(Screening.__table__.columns.keys()) == THE_TASK_S_COLUMNS


def test_the_table_is_named_for_the_table_the_task_and_routes_use() -> None:
    """8.5 added ``audit_events`` beside this one, on the same base, and the
    claim is now that the schema holds exactly the tables the tasks name --
    8.6 added ``ledger_entries`` and 16.1 added ``traveler_cases``, and the
    claim is unchanged by either.  It is a claim about *no* fifth table, so a
    table added without a task fails here rather than arriving quietly."""
    assert SCREENING_TABLE_NAME == "screenings"
    assert list(Base.metadata.tables) == [
        SCREENING_TABLE_NAME,
        "audit_events",
        "ledger_entries",
        TRAVELER_CASE_TABLE_NAME,
    ]
    assert Screening.__table__.metadata is Base.metadata


def test_only_the_columns_the_task_names_are_required(
    in_memory_engine: Engine,
) -> None:
    """The schema says so, read off the DDL rather than off the model, so a
    column that stopped being optional fails here."""
    ddl = str(
        CreateTable(Screening.__table__).compile(dialect=in_memory_engine.dialect)
    )

    required = {
        line.split()[0]
        for line in ddl.splitlines()
        if "NOT NULL" in line
    }

    assert required == set(REQUIRED_ON_INSERT) | set(DEFAULTED_COLUMNS)


def test_no_column_holds_image_bytes() -> None:
    """``AGENTS.md``'s "no image bytes in the database": the schema has no
    binary column for them to arrive in."""
    assert not any(
        isinstance(column.type, LargeBinary)
        for column in Screening.__table__.columns
    )


# --- a row exists before the analysis does -------------------------------


def test_a_row_that_nothing_has_analysed_reads_back_empty_results(
    sessions: sessionmaker[Session],
) -> None:
    """11.1 creates the row and answers with its id, so the fields a stage
    would write are absent rather than zeroed or invented."""
    with sessions() as session:
        session.add(_an_upload())
        session.commit()

    with sessions() as session:
        row = session.execute(select(Screening)).scalar_one()

    assert {name: getattr(row, name) for name in FILLED_BY_A_STAGE} == dict.fromkeys(
        FILLED_BY_A_STAGE
    )


def test_the_only_columns_the_orm_writes_are_its_three_defaults(
    sessions: sessionmaker[Session],
) -> None:
    """Every other value on a fresh row is one the caller handed over, so
    nothing on the row is a claim this module makes for a stage."""
    with sessions() as session:
        row = _an_upload()
        session.add(row)
        session.commit()
        stamped = {name: getattr(row, name) for name in THE_TASK_S_COLUMNS}

    expected: dict[str, Any] = dict.fromkeys(FILLED_BY_A_STAGE)
    expected.update(
        {
            "document_type": "passport",
            "filename": "passport-page.jpg",
            "image_width": 1240,
            "image_height": 1754,
            "status": DEFAULT_SCREENING_STATUS,
        }
    )
    for name in ("id", "created_at"):
        assert stamped[name] is not None
        expected[name] = stamped[name]

    assert stamped == expected


# --- the three defaults --------------------------------------------------


def test_a_new_row_is_stamped_with_an_opaque_id(
    sessions: sessionmaker[Session],
) -> None:
    """Not a counter: an id in a URL or an audit event should not be a number
    a stranger can walk up.  Stored as a native ``UUID`` where the backend has
    one and as hex where it does not."""
    column = Screening.__table__.columns["id"]

    assert isinstance(column.type, Uuid)
    assert column.primary_key

    with sessions() as session:
        first, second = _an_upload(), _an_upload()
        session.add_all((first, second))
        session.commit()

        assert isinstance(first.id, uuid.UUID)
        assert first.id is not None
        assert first.id != second.id


def test_a_row_nobody_has_written_carries_no_id_and_no_timestamp() -> None:
    """Construction is not persistence: the three defaults are the ORM's and
    belong to the flush."""
    row = Screening()

    assert row.id is None
    assert row.created_at is None


def test_a_caller_may_choose_the_id(
    sessions: sessionmaker[Session],
) -> None:
    """11.1 answers with a screening id, and 9.x's events reference one, so a
    row can be written with an id the caller already holds."""
    chosen = uuid.uuid4()

    with sessions() as session:
        session.add(_an_upload(id=chosen))
        session.commit()

        assert session.get(Screening, chosen) is not None


def test_a_new_row_is_stamped_pending_and_can_be_written_another_state(
    sessions: sessionmaker[Session],
) -> None:
    """``status`` is a lifecycle, and the default is read out of the
    vocabulary rather than spelled beside it."""
    assert DEFAULT_SCREENING_STATUS in SCREENING_STATUSES

    with sessions() as session:
        fresh = _an_upload()
        finished = _an_upload(status=SCREENING_STATUSES[1])
        session.add_all((fresh, finished))
        session.commit()

    with sessions() as session:
        statuses = set(session.execute(select(Screening.status)).scalars())

    assert statuses == {DEFAULT_SCREENING_STATUS, SCREENING_STATUSES[1]}


def test_the_status_vocabulary_has_no_duplicates() -> None:
    """Part 10's 10.1 test is over event types; this is the same question of
    the one other closed vocabulary this table has."""
    assert len(SCREENING_STATUSES) == len(set(SCREENING_STATUSES))
    assert all(status.islower() for status in SCREENING_STATUSES)


def test_a_new_row_is_stamped_with_the_time_in_utc(
    sessions: sessionmaker[Session],
) -> None:
    """Stamped by the ORM and stamped in UTC, so two stations' rows are
    comparable without each of them converting first.

    **SQLite gives the value back without a timezone** -- measured here, the
    stored string is the UTC wall clock and ``tzinfo`` is ``None`` -- while a
    backend with a real timestamp type would hand back an aware value.  The
    assertion is written so it holds under either spelling, and it holds on
    the object before the round trip as well as after it.
    """
    with sessions() as session:
        row = _an_upload()
        session.add(row)
        session.commit()
        stamped = row.created_at

    assert stamped.tzinfo is timezone.utc

    with sessions() as session:
        read_back = session.execute(select(Screening)).scalar_one().created_at

    assert read_back.replace(tzinfo=timezone.utc) == stamped


# --- the modes, and the one the API already answers with -----------------


@pytest.mark.parametrize("response", [ModuleResult, AnalysisResponse])
def test_the_mode_vocabulary_is_the_one_the_api_answers_with(
    response: type,
) -> None:
    """Read off the API's own annotation rather than restated here, so the
    column and ``/api/analyze`` cannot drift apart."""
    assert get_args(get_type_hints(response)["mode"]) == SCREENING_MODES


def test_a_mode_is_written_by_the_quality_gate_and_read_back(
    sessions: sessionmaker[Session],
) -> None:
    """``mode`` is one of the two, and it is absent until the gate has run."""
    with sessions() as session:
        row = _an_upload(mode=SCREENING_MODES[1])
        session.add(row)
        session.commit()

    with sessions() as session:
        assert session.execute(select(Screening.mode)).scalar_one() == "scan"


# --- the JSON columns ----------------------------------------------------


def test_the_json_columns_carry_nested_values_through_and_back(
    sessions: sessionmaker[Session],
) -> None:
    """Findings, the gate's result and the module versions are structures
    rather than strings, so the round trip has to keep the nesting, the
    ``None`` inside it and the empty list.
    """
    flags = [
        {
            "id": "MRZ_CHECK_DIGIT_MISMATCH",
            "tier": 0,
            "label": "Check digit mismatch",
            "weight": 40.0,
            "value": 1.0,
            "confidence": 0.98,
            "region": [[10, 20], [30, 20], [30, 28], [10, 28]],
            "expected": None,
            "found": "7",
            "reason": "The printed digit does not match the line it is on.",
        }
    ]
    quality = {
        "mode": "photo",
        "overall_pass": True,
        "modules": [{"module": "m1_sharpness", "passed": True, "reasons": []}],
        "trim_box": None,
    }
    model_versions = {"tier1_ocr": "heuristic-v0", "tier2_face": "not-configured"}

    with sessions() as session:
        session.add(
            _an_upload(
                flags=flags,
                quality=quality,
                model_versions=model_versions,
                ruleset_version="1.0.0",
                score=40.0,
                band="review",
                summary="One dating irregularity needs a second look.",
            )
        )
        session.commit()

    with sessions() as session:
        row = session.execute(select(Screening)).scalar_one()

    assert row.flags == flags
    assert row.quality == quality
    assert row.model_versions == model_versions
    assert row.ruleset_version == "1.0.0"
    assert row.score == 40.0
    assert row.band == "review"
    assert row.summary == "One dating irregularity needs a second look."


def test_a_json_column_that_was_never_written_is_null_not_an_empty_object(
    sessions: sessionmaker[Session],
) -> None:
    """The distinction 23.6 is about on the front end: "nothing was found"
    and "nothing was recorded" must not both read as ``{}``."""
    with sessions() as session:
        session.add(_an_upload())
        session.commit()

    with sessions() as session:
        row = session.execute(select(Screening)).scalar_one()

    assert row.flags is None
    assert row.quality is None
    assert row.model_versions is None


# --- the soft-delete stamp -----------------------------------------------


def test_the_soft_delete_stamp_is_empty_until_something_sets_it(
    sessions: sessionmaker[Session],
) -> None:
    assert Screening().deleted_at is None


def test_setting_the_soft_delete_stamp_leaves_the_row_readable(
    sessions: sessionmaker[Session],
) -> None:
    """Which reads skip a soft-deleted row is 8.15's question.  The table
    itself stores the stamp and stores nothing else, so the row is still
    there -- a soft delete is not a delete, and the ledger entry beside it
    has to keep verifying either way.
    """
    deleted_at = datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
    with sessions() as session:
        row = _an_upload()
        row.deleted_at = deleted_at
        session.add(row)
        session.commit()

    with sessions() as session:
        read_back = session.execute(select(Screening)).scalar_one()

    assert read_back.deleted_at.replace(tzinfo=timezone.utc) == deleted_at


# --- the base every table shares -----------------------------------------


def test_every_table_in_the_service_is_mapped_against_one_base() -> None:
    """8.5's ``AuditEvent`` and 8.6's ``LedgerEntry`` are mapped against this
    one base, which is what lets 8.8's migration see the whole schema."""
    assert {table.metadata for table in Base.metadata.tables.values()} == {
        Base.metadata
    }
    assert issubclass(Screening, Base)


def test_the_base_names_its_constraints_deterministically() -> None:
    """8.7 adds indexes and 8.8 downgrades a migration, so the names those
    objects are created under have to be the same on both backends."""
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    named = {
        constraint.name
        for constraint in Screening.__table__.constraints
        if constraint.name
    }

    assert f"pk_{SCREENING_TABLE_NAME}" in named
