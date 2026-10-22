"""8.5: the ``AuditEvent`` row, and one in-memory database it round-trips
through.

The task's verify is "a test round-trips a row", and this file is that plus
the four claims the row is worth having:

- **the read back is a second session, not the one that wrote.** A row held
  by an open session proves nothing was serialised; the read is a fresh
  session against the same database, which is what 9.17's verification and
  24.8's audit view do.
- **the row is exactly the columns its tasks name, in that order, and no
  others** -- 8.5's eight, then the ``record_salt`` and ``batch_index``
  10.2 added, then ``created_at``.  Still no column for a decision, which
  10.6 records as an event type instead.
- **``screening_id`` names a screening without pointing at it.** No foreign
  key is declared, and the claim is held against the column's own
  ``foreign_keys`` set as well as against a delete, because SQLite does not
  enforce a declared key without a pragma: a test that only deleted a
  screening would pass on a table that had one.
- **an unanchored event is a state this table can hold.** ``batch_id`` and
  ``batch_index`` are nullable because 9.16 writes them later than the event,
  ``record_salt`` is nullable because a column added to a table that already
  holds rows cannot be ``NOT NULL``, and a required JSON payload is an object
  rather than an absent value.
"""

import ast
import pathlib
import uuid
from collections.abc import Iterator
from datetime import timezone
from typing import Any

import pytest
from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    LargeBinary,
    String,
    Uuid,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateTable

from app.storage import db, models
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    SCREENING_MODES,
    SCREENING_STATUSES,
    AuditEvent,
    Base,
    Screening,
)


#: The columns the table carries: 8.5's eight in the order it named them,
#: then the two 10.2 added, then the stamp.  Held as one tuple so the
#: table's own column list is checked against a list written once here:
#: restating the model's fields beside the model's fields would pass on a
#: table that had grown one.
THE_TABLE_S_COLUMNS = (
    "id",
    "screening_id",
    "batch_id",
    "event_type",
    "actor",
    "payload",
    "record_hash",
    "record_salt",
    "batch_index",
    "created_at",
)

#: The seven a caller cannot write the row without.  ``batch_id`` and
#: ``batch_index`` are written when the event is anchored, and
#: ``record_salt`` by 10.2's writer rather than by the caller.
REQUIRED_ON_INSERT = (
    "id",
    "screening_id",
    "event_type",
    "actor",
    "payload",
    "record_hash",
    "created_at",
)

#: The three the DDL leaves optional: the two 9.16 stamps and the salt
#: 10.2's writer always writes.
OPTIONAL_COLUMNS = ("batch_id", "record_salt", "batch_index")

#: The two columns the ORM writes itself, named so the "nothing else is
#: written" claim below has a list to be checked against.  ``Screening``'s
#: third default (``status``) has no counterpart here: a row records
#: something that happened, so there is no pending state for it to hold.
DEFAULTED_COLUMNS = ("id", "created_at")

#: A digest as 9.3 would hand it back -- 64 hex characters -- and one
#: differing from it in a single character, which is all 9.17 needs to see
#: to call a row altered.
A_RECORD_HASH = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
ANOTHER_RECORD_HASH = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a09"


@pytest.fixture
def in_memory_engine() -> Iterator[Engine]:
    """One in-memory SQLite database with the schema created in it.

    Built through :func:`~app.storage.db.build_engine`, as 8.4's suite does,
    so the URL the service is configured with is the URL this suite
    exercises -- and so the in-memory URL means one database
    (``D38``'s ``StaticPool``).  Disposed at the end, so a test that leaves
    a connection open cannot reach the next one.
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


def _an_event(**overrides: Any) -> AuditEvent:
    """A row carrying what a recorder handed over, and nothing more."""
    fields: dict[str, Any] = {
        "screening_id": uuid.uuid4(),
        "event_type": "screening_created",
        "actor": "station-unset",
        "payload": {"document_type": "passport"},
        "record_hash": A_RECORD_HASH,
    }
    fields.update(overrides)
    return AuditEvent(**fields)


# --- the row, written and read back --------------------------------------


def test_a_row_written_to_an_in_memory_database_is_read_back(
    sessions: sessionmaker[Session],
) -> None:
    """8.5's verify, and the read is a second session on purpose.

    The first session is closed before the second one opens, so nothing here
    can be answered out of the identity map of the session that wrote the
    row: the value came back through the database or it did not come back.
    """
    screening_id = uuid.uuid4()

    with sessions() as session:
        session.add(_an_event(screening_id=screening_id))
        session.commit()

    with sessions() as session:
        rows = session.execute(select(AuditEvent)).scalars().all()

    assert len(rows) == 1
    assert rows[0].screening_id == screening_id
    assert rows[0].event_type == "screening_created"
    assert rows[0].actor == "station-unset"
    assert rows[0].payload == {"document_type": "passport"}
    assert rows[0].record_hash == A_RECORD_HASH


def test_a_row_survives_the_session_that_wrote_it_closing(
    sessions: sessionmaker[Session],
) -> None:
    """``expire_on_commit=False`` (``D36``) is what makes the object readable
    after the block 10.2's ``emit`` writes it in has closed."""
    with sessions() as session:
        written = _an_event()
        session.add(written)
        session.commit()

    assert written.id is not None
    assert written.created_at is not None


def test_a_written_row_can_be_fetched_by_its_own_id(
    sessions: sessionmaker[Session],
) -> None:
    """11.1 answers with a ``screening_id`` and an ``audit_id`` together, so
    the primary key is what the trail will be read with."""
    with sessions() as session:
        first, second = _an_event(), _an_event(event_type="tier_completed")
        session.add_all((first, second))
        session.commit()

    with sessions() as session:
        found = session.get(AuditEvent, first.id)

    assert found is not None
    assert found.id == first.id
    assert found.event_type == "screening_created"


# --- the columns, and only the columns -----------------------------------


def test_the_table_carries_exactly_the_columns_the_task_names() -> None:
    assert tuple(AuditEvent.__table__.columns.keys()) == THE_TABLE_S_COLUMNS


def test_the_table_is_named_for_the_table_the_task_and_routes_use() -> None:
    assert AUDIT_EVENT_TABLE_NAME == "audit_events"
    assert AuditEvent.__table__.metadata is Base.metadata
    assert AuditEvent.__table__ is Base.metadata.tables[AUDIT_EVENT_TABLE_NAME]
    assert issubclass(AuditEvent, Base)


def test_only_the_anchoring_columns_and_the_salt_are_optional(
    in_memory_engine: Engine,
) -> None:
    """The schema says so, read off the DDL rather than off the model, so a
    column that stopped being optional fails here.  The three exceptions are
    the two 9.16 stamps when the event is anchored and the salt 10.2's writer
    puts beside the digest."""
    ddl = str(
        CreateTable(AuditEvent.__table__).compile(dialect=in_memory_engine.dialect)
    )

    required = {line.split()[0] for line in ddl.splitlines() if "NOT NULL" in line}
    every_column = set(AuditEvent.__table__.columns.keys())

    assert required == set(REQUIRED_ON_INSERT)
    assert every_column - required == set(OPTIONAL_COLUMNS)


def test_no_column_holds_image_bytes() -> None:
    """``AGENTS.md``'s "no image bytes in the database": the schema has no
    binary column for them to arrive in, on this table or the other."""
    for table in Base.metadata.tables.values():
        assert not any(
            isinstance(column.type, LargeBinary) for column in table.columns
        )


def test_the_table_constrains_nothing_the_writers_own() -> None:
    """The primary key is the only constraint.  10.1's six event types and
    10.7's station label are closed vocabularies, and a column cannot
    enforce one on both backends -- 8.4's reason, held again here."""
    kinds = {type(constraint) for constraint in AuditEvent.__table__.constraints}

    assert not any(
        issubclass(kind, (CheckConstraint, ForeignKeyConstraint)) for kind in kinds
    )


# --- the screening this happened to, named but not pointed at ------------


def test_the_screening_column_is_a_uuid_named_as_a_value() -> None:
    """Same type as ``Screening.id``, so 11.1's ``screening_id`` and 24.8's
    lookup are the same value rather than two spellings of it."""
    column = AuditEvent.__table__.columns["screening_id"]

    assert isinstance(column.type, Uuid)
    assert not column.nullable
    assert column.type is Screening.__table__.columns["id"].type


def test_the_screening_column_declares_no_foreign_key(
    in_memory_engine: Engine,
) -> None:
    """The claim held against the schema, not only against a delete.

    A delete test passes on either answer: SQLite does not enforce a
    declared key unless a pragma asks it to, so a table *with* a foreign
    key would still let the row go.  The declaration is what would bind
    PostgreSQL, so the declaration is what is asserted.
    """
    column = AuditEvent.__table__.columns["screening_id"]
    ddl = str(
        CreateTable(AuditEvent.__table__).compile(dialect=in_memory_engine.dialect)
    )

    assert column.foreign_keys == set()
    assert "REFERENCES" not in ddl


def test_an_event_outlives_the_screening_row_it_names(
    sessions: sessionmaker[Session],
) -> None:
    """A trail a delete on ``screenings`` could empty is not a trail.  8.15
    soft-deletes rather than deletes, but the screening row is also the
    record an officer reads, and 9.17's answer for an event whose screening
    is gone should be ``verified`` rather than unanswerable."""
    with sessions() as session:
        screening = Screening(
            document_type="passport",
            filename="passport-page.jpg",
            image_width=1240,
            image_height=1754,
        )
        session.add(screening)
        session.commit()
        event = _an_event(screening_id=screening.id)
        session.add(event)
        session.commit()

        session.delete(screening)
        session.commit()

    with sessions() as session:
        assert session.get(Screening, event.screening_id) is None
        read_back = session.get(AuditEvent, event.id)

    assert read_back is not None
    assert read_back.record_hash == A_RECORD_HASH


def test_an_event_is_written_against_a_screening_id_the_caller_already_holds(
    sessions: sessionmaker[Session],
) -> None:
    """11.1 has the id before the cascade runs, so the event naming it is
    written with a value rather than reached through a relationship."""
    chosen = uuid.uuid4()

    with sessions() as session:
        session.add(_an_event(screening_id=chosen))
        session.commit()

    with sessions() as session:
        assert session.get(AuditEvent, chosen) is None
        stored = session.execute(select(AuditEvent)).scalar_one()

    assert stored.screening_id == chosen


# --- the batch, absent until 9.16 stamps it ------------------------------


def test_an_unanchored_event_carries_no_batch(
    sessions: sessionmaker[Session],
) -> None:
    """``None`` rather than a zero batch or an empty string: it is the state
    9.17 reports as ``unknown``, because there is no root yet to walk a
    proof to."""
    with sessions() as session:
        session.add(_an_event())
        session.commit()

    with sessions() as session:
        assert session.execute(select(AuditEvent.batch_id)).scalar_one() is None


def test_a_batch_id_stamped_by_anchoring_reads_back_as_a_uuid(
    sessions: sessionmaker[Session],
) -> None:
    """9.16 stamps each event with its batch id, and 9.12's ledger entry
    carries the same value -- so it reads back as the type it was written
    as, not as the 32 hex characters SQLite stores."""
    batch_id = uuid.uuid4()

    with sessions() as session:
        session.add(_an_event(batch_id=batch_id))
        session.commit()

    with sessions() as session:
        stamped = session.execute(select(AuditEvent)).scalar_one().batch_id

    assert isinstance(stamped, uuid.UUID)
    assert stamped == batch_id


# --- what happened, and who recorded it ----------------------------------


def test_the_event_type_is_plain_text_and_not_an_enum() -> None:
    """10.1's constants module is the vocabulary and this table is not it:
    an ``Enum`` here would freeze a second list of names beside the first,
    and the writer (10.2) is where a name outside it is refused."""
    column = AuditEvent.__table__.columns["event_type"]

    assert isinstance(column.type, String)
    assert not isinstance(column.type, Enum)
    assert not column.nullable


def test_no_event_type_vocabulary_is_claimed_in_this_module() -> None:
    """The six names are 10.1's, and a second list beside them could disagree
    with the first.  Held against the module's own namespace, so a
    vocabulary added here fails rather than drifting."""
    vocabularies = {
        name: value
        for name, value in vars(models).items()
        if not name.startswith("__")
        and isinstance(value, (tuple, list, frozenset, set))
    }

    assert set(vocabularies) == {"SCREENING_MODES", "SCREENING_STATUSES"}
    assert set(vocabularies.values()) == {SCREENING_MODES, SCREENING_STATUSES}


@pytest.mark.parametrize("actor", ["station-unset", "KIOSK-02", "Station Alpha"])
def test_a_station_label_is_written_and_read_back(
    sessions: sessionmaker[Session], actor: str
) -> None:
    """10.7's field is a configured label and not an identity, so the three
    spellings that matter are a placeholder, a machine name and a room."""
    with sessions() as session:
        session.add(_an_event(actor=actor))
        session.commit()

    with sessions() as session:
        assert session.execute(select(AuditEvent.actor)).scalar_one() == actor


def test_this_module_never_reads_the_station_label() -> None:
    """The label is configuration and 10.7 is the one reader of it.  A model
    that read the environment would stamp a row from whatever the process
    happened to be started with."""
    source = pathlib.Path(models.__file__).read_text(encoding="utf-8")
    reads = {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"getenv", "environ"}
    }

    assert reads == set()


# --- the payload ---------------------------------------------------------


def test_the_payload_carries_nested_values_through_and_back(
    sessions: sessionmaker[Session],
) -> None:
    """The payload is a structure rather than a string, so 9.3's hash is
    taken over one spelling of it -- which only holds if the nesting, the
    ``None`` inside it, the empty list and the non-ASCII text all survive
    the round trip unchanged."""
    payload = {
        "document_type": "passport",
        "tiers": [{"tier": 0, "elapsed_ms": 41, "flag_ids": []}],
        "band_shown": None,
        "operator_note": "Réglage vérifié",
        "flags": [],
    }

    with sessions() as session:
        session.add(_an_event(payload=payload))
        session.commit()

    with sessions() as session:
        assert session.execute(select(AuditEvent.payload)).scalar_one() == payload


def test_an_event_with_nothing_to_add_writes_an_empty_object(
    sessions: sessionmaker[Session],
) -> None:
    """``{}`` is a decision -- "nothing beyond the type and the actor" --
    where ``None`` is 8.4's "never written".  On this table ``None`` is not
    an available answer, and the test holds that it is refused.

    **The refusal is the reason the column is declared
    ``none_as_null=True``, and it is measured rather than assumed**: with a
    plain ``JSON`` column a ``None`` payload is written as the four
    characters ``null`` inside a ``NOT NULL`` column and reads back as
    ``None``, so the constraint would never be exercised and an absent
    payload would be a third spelling for 9.3 to hash beside ``{}``.
    """
    with sessions() as session:
        session.add(_an_event(payload={}))
        session.commit()

    with sessions() as session:
        assert session.execute(select(AuditEvent.payload)).scalar_one() == {}

    with pytest.raises(IntegrityError):
        with sessions() as session:
            session.add(_an_event(payload=None))
            session.commit()


# --- the hash ------------------------------------------------------------


def test_the_record_hash_is_stored_and_not_computed(
    sessions: sessionmaker[Session],
) -> None:
    """A stored digest, not a generated one.  If the column recomputed, a
    payload altered behind the table's back would hash to the new value and
    9.17 would have nothing to notice."""
    column = AuditEvent.__table__.columns["record_hash"]

    assert isinstance(column.type, String)
    assert not column.nullable
    assert column.computed is None

    with sessions() as session:
        session.add(_an_event())
        session.add(
            _an_event(
                event_type="analysis_completed", record_hash=ANOTHER_RECORD_HASH
            )
        )
        session.commit()

    with sessions() as session:
        assert set(session.execute(select(AuditEvent.record_hash)).scalars()) == {
            A_RECORD_HASH,
            ANOTHER_RECORD_HASH,
        }


def test_the_orm_writes_only_the_id_and_the_timestamp(
    sessions: sessionmaker[Session],
) -> None:
    """Everything else on a fresh row is what the recorder handed over, so
    nothing on an event is a claim this module makes on 10.2's behalf."""
    defaulted = {
        name
        for name, column in AuditEvent.__table__.columns.items()
        if column.default is not None or column.server_default is not None
    }
    assert defaulted == set(DEFAULTED_COLUMNS)

    with sessions() as session:
        session.add(_an_event())
        session.commit()
        row = session.execute(select(AuditEvent)).scalar_one()
        written = {name: getattr(row, name) for name in THE_TABLE_S_COLUMNS}

    assert written["batch_id"] is None
    for name in DEFAULTED_COLUMNS:
        assert written[name] is not None
    assert written["event_type"] == "screening_created"
    assert written["actor"] == "station-unset"
    assert written["payload"] == {"document_type": "passport"}
    assert written["record_hash"] == A_RECORD_HASH
    assert written["screening_id"] is not None


def test_a_new_row_is_stamped_with_an_opaque_id(
    sessions: sessionmaker[Session],
) -> None:
    """Not a counter, and not the screening's own id: 11.1 answers with the
    two side by side, so one being a walkable number would leak the other.
    Stored as a native ``UUID`` where the backend has one and as hex where
    it does not."""
    column = AuditEvent.__table__.columns["id"]

    assert isinstance(column.type, Uuid)
    assert column.primary_key

    with sessions() as session:
        first, second = _an_event(), _an_event()
        session.add_all((first, second))
        session.commit()

        assert isinstance(first.id, uuid.UUID)
        assert first.id != second.id
        assert first.id != first.screening_id


def test_a_row_nobody_has_written_carries_no_id_and_no_timestamp() -> None:
    """Construction is not persistence: the two defaults are the ORM's and
    belong to the flush."""
    row = AuditEvent()

    assert row.id is None
    assert row.created_at is None


def test_a_new_row_is_stamped_with_the_time_in_utc(
    sessions: sessionmaker[Session],
) -> None:
    """Stamped by the ORM and stamped in UTC, so two stations' trails are
    comparable without each of them converting first.

    **SQLite gives the value back without a timezone** -- measured in 8.4's
    suite, the stored string is the UTC wall clock and ``tzinfo`` is ``None``
    -- while a backend with a real timestamp type would hand back an aware
    value, so the assertion holds under either spelling.
    """
    with sessions() as session:
        row = _an_event()
        session.add(row)
        session.commit()
        stamped = row.created_at

    assert stamped.tzinfo is timezone.utc

    with sessions() as session:
        read_back = session.execute(select(AuditEvent)).scalar_one().created_at

    assert read_back.replace(tzinfo=timezone.utc) == stamped


# --- a trail is a list of events, not one row ----------------------------


def test_the_events_of_one_screening_read_back_together(
    sessions: sessionmaker[Session],
) -> None:
    """24.8's audit view is reached by a screening id, so a screening's
    events are readable together -- and another screening's are not among
    them, which is the whole reason the column exists."""
    mine, theirs = uuid.uuid4(), uuid.uuid4()

    with sessions() as session:
        session.add_all(
            [
                _an_event(screening_id=mine, event_type="screening_created"),
                _an_event(screening_id=mine, event_type="tier_completed"),
                _an_event(screening_id=theirs, event_type="screening_deleted"),
            ]
        )
        session.commit()

    with sessions() as session:
        rows = (
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.screening_id == mine)
                .order_by(AuditEvent.created_at)
            )
            .scalars()
            .all()
        )

    assert [row.event_type for row in rows] == [
        "screening_created",
        "tier_completed",
    ]
    assert all(row.screening_id == mine for row in rows)


# --- the base both tables share ------------------------------------------


def test_the_base_names_this_table_constraints_deterministically() -> None:
    """8.7 indexes and 8.8 downgrades a migration, so the names those
    objects are created under have to be the same on both backends."""
    named = {
        constraint.name
        for constraint in AuditEvent.__table__.constraints
        if constraint.name
    }

    assert named == {f"pk_{AUDIT_EVENT_TABLE_NAME}"}
    assert Base.metadata.naming_convention == models.NAMING_CONVENTION


def test_no_model_imports_another_application_package() -> None:
    """8.4's claim, still true of the second table in the module: 7.10's
    walk, 8.8's migration and 8.10's repository all reach this file."""
    source = pathlib.Path(models.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert [name for name in imported if name.startswith("app")] == []
