"""10.2: ``emit`` -- check the name, seal the record, store the row.

The task's verify is "a test emits one and reads it back", and that is the
first test here.  The rest is what makes it the only writer:

- **the vocabulary is enforced here.**  A name outside 10.1's six is refused
  before a row exists, and the tuple :mod:`emit` checks against *is* the one
  module holds, so there is no second list to drift.
- **what is hashed is what is stored.**  The digest is taken over
  :func:`~app.audit.record.event_record` with the salt stored beside it, so
  9.17 recomputes the same value out of the row rather than being told it.
- **a payload that cannot be spelled is never stored.**  ``D48`` refuses a
  ``float``, and the refusal comes before the row is built, so there is no
  event in the trail whose digest nobody could ever recompute.
- **every payload carries its versions.**  The ruleset and the model
  versions are attached here, whether or not the caller knew them, and they
  are attached before the record is sealed -- so they are inside the digest
  and 9.17 rebuilds them without a change.
- **no value reaches a message.**  A refusal names the type it was handed and
  nothing else, so an identity in a payload cannot end up in a log.
- **one writer in ``app/``.**  A walk over the package fails on any other
  module constructing an ``AuditEvent``, which is the enforcement behind
  "this is the only function allowed to create audit events".
"""

import ast
import inspect
import pathlib
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.audit import emit as emit_module
from app.audit import event_types
from app.audit.emit import (
    MODEL_VERSIONS_KEY,
    PLACEHOLDER_ACTOR,
    RULESET_VERSION_KEY,
    VERSION_KEYS,
    EmitError,
    emit,
)
from app.audit.event_types import EVENT_TYPES
from app.audit.record import event_record
from app.ledger.canonical import CanonicalJsonError
from app.ledger.hashing import hash_record
from app.storage import db
from app.storage.models import AuditEvent, Base


#: A payload 9.3 can spell: text, ints and objects, and no ``float`` (``D48``).
A_PAYLOAD = {"band": "high", "flags": ["MATCH"], "score_bp": 7250}

#: What 10.3 attaches when the caller stated no version: both keys, spelled
#: as unknowns rather than omitted.
NO_VERSIONS = {RULESET_VERSION_KEY: None, MODEL_VERSIONS_KEY: None}


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema in it, built the way
    the service builds one (``D38``), and a factory over it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield db.build_session_factory(engine)
    finally:
        engine.dispose()


def _rows(sessions: sessionmaker[Session]) -> int:
    """How many events the table holds, counted by the database."""
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(AuditEvent)) or 0


def _stored(
    sessions: sessionmaker[Session], event_id: uuid.UUID
) -> AuditEvent | None:
    """One row, read back over a session that did not write it."""
    with sessions() as session:
        return session.get(AuditEvent, event_id)


# --- the task's claim ------------------------------------------------------


def test_an_emitted_event_is_read_back_by_another_session(
    sessions: sessionmaker[Session],
) -> None:
    """The task's verify, read back over a session that did not write it: a
    row held by an open session proves nothing was serialised."""
    screening_id = uuid.uuid4()

    emitted = emit(
        event_types.SCREENING_CREATED, screening_id, A_PAYLOAD, sessions=sessions
    )

    stored = _stored(sessions, emitted.id)
    assert stored is not None, "the event did not reach the database"
    assert stored.id == emitted.id
    assert stored.screening_id == screening_id
    assert stored.event_type == event_types.SCREENING_CREATED
    assert stored.actor == PLACEHOLDER_ACTOR
    assert stored.payload == {**A_PAYLOAD, **NO_VERSIONS}
    assert stored.created_at is not None
    assert _rows(sessions) == 1


def test_the_returned_row_is_readable_once_the_session_has_closed(
    sessions: sessionmaker[Session],
) -> None:
    """``emit`` hands back the row it stored rather than a row it is still
    holding, which is what ``expire_on_commit=False`` on the factory buys."""
    emitted = emit(
        event_types.SCREENING_CREATED, uuid.uuid4(), A_PAYLOAD, sessions=sessions
    )

    assert emitted.id is not None, "a row with no id was never written"
    assert emitted.record_hash and emitted.record_salt
    assert emitted.batch_id is None
    assert emitted.batch_index is None


def test_the_stored_digest_is_the_one_the_stored_salt_was_taken_under(
    sessions: sessionmaker[Session],
) -> None:
    """9.17 recomputes out of the row, so the row has to carry everything the
    recomputation needs: the four fields of the record and the salt."""
    emitted = emit(
        event_types.ANALYSIS_COMPLETED,
        uuid.uuid4(),
        A_PAYLOAD,
        sessions=sessions,
    )

    stored = _stored(sessions, emitted.id)
    assert stored is not None
    recomputed = hash_record(
        event_record(
            stored.event_type, stored.screening_id, stored.actor, stored.payload
        ),
        bytes.fromhex(stored.record_salt),
    )

    assert stored.record_hash == recomputed
    assert len(bytes.fromhex(stored.record_salt)) == 16


def test_two_events_with_one_payload_are_sealed_under_different_salts(
    sessions: sessionmaker[Session],
) -> None:
    """``D50``: a salt that is reused is not a salt, so the same payload twice
    is two digests and two rows."""
    first = emit(
        event_types.SCREENING_CREATED,
        uuid.uuid4(),
        A_PAYLOAD,
        sessions=sessions,
    )
    second = emit(
        event_types.SCREENING_CREATED,
        uuid.uuid4(),
        A_PAYLOAD,
        sessions=sessions,
    )

    assert first.payload == second.payload
    assert first.record_salt != second.record_salt
    assert first.record_hash != second.record_hash
    assert _rows(sessions) == 2


def test_an_event_with_nothing_to_add_writes_an_empty_object(
    sessions: sessionmaker[Session],
) -> None:
    """8.5's ``{}`` rather than an absent value, and it still hashes.  What is
    stored is that empty object plus the two version keys, so a payload with
    nothing to add is still an object a reader can ask about."""
    emitted = emit(
        event_types.SCREENING_CREATED, uuid.uuid4(), {}, sessions=sessions
    )

    stored = _stored(sessions, emitted.id)
    assert stored is not None
    assert stored.payload == NO_VERSIONS
    assert stored.record_hash == hash_record(
        event_record(
            stored.event_type, stored.screening_id, stored.actor, stored.payload
        ),
        bytes.fromhex(stored.record_salt),
    )


@pytest.mark.parametrize("event_type", list(EVENT_TYPES))
def test_every_name_in_the_vocabulary_is_accepted(
    sessions: sessionmaker[Session], event_type: str
) -> None:
    """The closed tuple is what the writer checks, so every one of the six is
    a name this row can carry."""
    emitted = emit(event_type, uuid.uuid4(), A_PAYLOAD, sessions=sessions)

    stored = _stored(sessions, emitted.id)
    assert stored is not None
    assert stored.event_type == event_type


# --- the refusals ----------------------------------------------------------


def test_a_name_outside_the_vocabulary_is_refused_and_nothing_is_written(
    sessions: sessionmaker[Session],
) -> None:
    """10.1 left this to the writer: a seventh name is refused before a row
    exists, and the message names the name -- which is a constant in the
    source, never anything a screening carried."""
    with pytest.raises(EmitError) as refused:
        emit("screening_created_v2", uuid.uuid4(), A_PAYLOAD, sessions=sessions)

    assert "screening_created_v2" in str(refused.value)
    assert _rows(sessions) == 0


@pytest.mark.parametrize("event_type", [None, 7, ["screening_deleted"]])
def test_a_value_that_is_not_a_name_is_refused(
    sessions: sessionmaker[Session], event_type: Any
) -> None:
    """Membership is checked before anything else, so a value that is not
    text at all is refused as a name rather than written."""
    with pytest.raises(EmitError):
        emit(event_type, uuid.uuid4(), A_PAYLOAD, sessions=sessions)

    assert _rows(sessions) == 0


def test_a_payload_the_serialiser_refuses_is_never_stored(
    sessions: sessionmaker[Session],
) -> None:
    """``D48`` bars a ``float`` from a hashed record, so a score handed over
    as one has no digest: the refusal comes before the row is built rather
    than after it is written (a score goes in as text or a scaled integer)."""
    with pytest.raises(CanonicalJsonError):
        emit(
            event_types.ANALYSIS_COMPLETED,
            uuid.uuid4(),
            {"score": 72.5},
            sessions=sessions,
        )

    assert _rows(sessions) == 0


@pytest.mark.parametrize("payload", [[], "banded", None, 3])
def test_a_payload_that_is_not_an_object_is_refused(
    sessions: sessionmaker[Session], payload: Any
) -> None:
    """The column is a JSON object and 8.5 spells the empty one as ``{}``, so
    a bare value has no spelling here."""
    with pytest.raises(TypeError):
        emit(
            event_types.SCREENING_CREATED,
            uuid.uuid4(),
            payload,
            sessions=sessions,
        )

    assert _rows(sessions) == 0


def test_a_refusal_names_the_type_and_never_the_value(
    sessions: sessionmaker[Session],
) -> None:
    """``AGENTS.md``'s no identity data in a log: a payload carrying a name is
    refused by its type alone, and that type is all the message holds."""
    payload = ["surname", "a name that is not printed"]

    with pytest.raises(TypeError) as refused:
        emit(
            event_types.SCREENING_CREATED,
            uuid.uuid4(),
            payload,
            sessions=sessions,
        )

    message = str(refused.value)
    assert "list" in message
    assert "surname" not in message
    assert "not printed" not in message


@pytest.mark.parametrize("screening_id", ["a screening", 7, None])
def test_a_screening_that_is_not_a_uuid_is_refused(
    sessions: sessionmaker[Session], screening_id: Any
) -> None:
    """The trail carries the value rather than pointing at a row, so it has to
    be the one type both writers and readers spell the same way."""
    with pytest.raises(TypeError):
        emit(
            event_types.SCREENING_CREATED,
            screening_id,
            A_PAYLOAD,
            sessions=sessions,
        )

    assert _rows(sessions) == 0


def test_the_name_is_refused_before_the_screening_or_the_payload(
    sessions: sessionmaker[Session],
) -> None:
    """Order matters for the message a developer sees: a name that is wrong is
    the first thing said, whatever else was also wrong."""
    with pytest.raises(EmitError):
        emit(
            "not_a_name",
            "not a uuid either",
            "not an object",
            sessions=sessions,
        )

    assert _rows(sessions) == 0


# --- 10.3: the two versions, on every payload ------------------------------


def test_a_generic_emit_carries_both_versions(
    sessions: sessionmaker[Session],
) -> None:
    """The task's verify, on the plainest call there is: an ordinary emit
    that says nothing about versions, and both keys are on the payload.  A
    reader never has to tell "unknown" from "never asked about"."""
    emitted = emit(
        event_types.SCREENING_CREATED, uuid.uuid4(), A_PAYLOAD, sessions=sessions
    )

    stored = _stored(sessions, emitted.id)
    assert stored is not None
    assert set(stored.payload) == set(A_PAYLOAD) | set(VERSION_KEYS)
    assert stored.payload[RULESET_VERSION_KEY] is None
    assert stored.payload[MODEL_VERSIONS_KEY] is None


def test_the_versions_handed_over_are_the_ones_recorded(
    sessions: sessionmaker[Session],
) -> None:
    """What the screening row carries is what the event says, under the
    column's own names, beside the caller's payload rather than instead of
    it."""
    versions = {"tier1.mrz": "1.0.0", "tier2.forgery": "stub-1"}

    emitted = emit(
        event_types.ANALYSIS_COMPLETED,
        uuid.uuid4(),
        A_PAYLOAD,
        sessions=sessions,
        ruleset_version="0.1.0",
        model_versions=versions,
    )

    stored = _stored(sessions, emitted.id)
    assert stored is not None
    assert stored.payload == {
        **A_PAYLOAD,
        RULESET_VERSION_KEY: "0.1.0",
        MODEL_VERSIONS_KEY: versions,
    }


def test_the_callers_payload_is_not_amended(
    sessions: sessionmaker[Session],
) -> None:
    """10.2 carried the payload by reference so the writer sealed exactly
    what it was handed; attaching to a copy is what keeps that true."""
    payload = dict(A_PAYLOAD)

    emit(
        event_types.SCREENING_CREATED,
        uuid.uuid4(),
        payload,
        sessions=sessions,
        ruleset_version="0.1.0",
    )

    assert payload == A_PAYLOAD


def test_an_attached_version_is_inside_the_digest(
    sessions: sessionmaker[Session],
) -> None:
    """The versions are hashed, not filed beside the row: rewriting one in
    the database leaves a digest nobody recomputes, which is what 9.17
    answers ``altered`` on."""
    emitted = emit(
        event_types.SCREENING_CREATED,
        uuid.uuid4(),
        A_PAYLOAD,
        sessions=sessions,
        ruleset_version="0.1.0",
    )
    stored = _stored(sessions, emitted.id)
    assert stored is not None
    salt = bytes.fromhex(stored.record_salt)

    assert stored.record_hash == hash_record(
        event_record(
            stored.event_type, stored.screening_id, stored.actor, stored.payload
        ),
        salt,
    )

    with sessions() as session:
        session.execute(
            update(AuditEvent)
            .where(AuditEvent.id == emitted.id)
            .values(
                payload={**stored.payload, RULESET_VERSION_KEY: "9.9.9"}
            )
        )
        session.commit()

    tampered = _stored(sessions, emitted.id)
    assert tampered is not None
    assert tampered.record_hash != hash_record(
        event_record(
            tampered.event_type,
            tampered.screening_id,
            tampered.actor,
            tampered.payload,
        ),
        bytes.fromhex(tampered.record_salt),
    )


@pytest.mark.parametrize("key", list(VERSION_KEYS))
def test_a_payload_that_already_carries_a_version_key_is_refused(
    sessions: sessionmaker[Session], key: str
) -> None:
    """One value is recorded once: a payload that writes one of the keys
    itself would leave the trail saying two things, so it is refused before
    a row exists."""
    with pytest.raises(EmitError) as refused:
        emit(
            event_types.SCREENING_CREATED,
            uuid.uuid4(),
            {key: "0.1.0"},
            sessions=sessions,
            ruleset_version="0.1.0",
        )

    assert key in str(refused.value)
    assert _rows(sessions) == 0


@pytest.mark.parametrize("ruleset_version", [7, ["0.1.0"], {"v": 1}])
def test_a_ruleset_version_that_is_not_text_is_refused(
    sessions: sessionmaker[Session], ruleset_version: Any
) -> None:
    """The column is text or nothing, so a version handed over as anything
    else has no spelling here."""
    with pytest.raises(TypeError):
        emit(
            event_types.SCREENING_CREATED,
            uuid.uuid4(),
            A_PAYLOAD,
            sessions=sessions,
            ruleset_version=ruleset_version,
        )

    assert _rows(sessions) == 0


@pytest.mark.parametrize("model_versions", [["tier1", "1.0.0"], "1.0.0", 3])
def test_model_versions_that_are_not_an_object_are_refused(
    sessions: sessionmaker[Session], model_versions: Any
) -> None:
    """``model_versions`` is module name to version, the object the column
    holds, so a list of two strings is not a spelling of it."""
    with pytest.raises(TypeError):
        emit(
            event_types.SCREENING_CREATED,
            uuid.uuid4(),
            A_PAYLOAD,
            sessions=sessions,
            model_versions=model_versions,
        )

    assert _rows(sessions) == 0


def test_a_float_inside_model_versions_is_refused_and_nothing_is_written(
    sessions: sessionmaker[Session],
) -> None:
    """``D48`` bars a ``float`` from a hashed record, so a version written
    as one has no digest.  The refusal still comes before the row is built,
    which is the half 10.2 added the attachment to."""
    with pytest.raises(CanonicalJsonError):
        emit(
            event_types.SCREENING_CREATED,
            uuid.uuid4(),
            A_PAYLOAD,
            sessions=sessions,
            model_versions={"tier2.forgery": 0.5},
        )

    assert _rows(sessions) == 0


# --- the claims the task's wording rests on -------------------------------


def test_this_is_the_only_writer_of_an_audit_event_in_the_package() -> None:
    """The task's "the only function allowed to create audit events", held
    against ``app/`` rather than against a promise: any other module
    constructing an ``AuditEvent`` is a second writer."""
    package = pathlib.Path(emit_module.__file__).parent.parent

    offenders = []
    for module in sorted(package.rglob("*.py")):
        if module == pathlib.Path(emit_module.__file__):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "AuditEvent"
            ):
                offenders.append(module.name)

    assert offenders == []


def test_the_writer_checks_the_one_vocabulary_not_its_own_list() -> None:
    """The tuple 10.1 closed *is* the tuple this module checks, so a seventh
    name cannot be added by editing a second list."""
    assert emit_module.EVENT_TYPES is EVENT_TYPES


def test_the_dependencies_are_keyword_only_and_sessions_is_the_only_required_one() -> None:
    """``sessions`` is a keyword and is required: the factory is the seam, so
    no module-level session is reachable from here.  The two versions are
    keywords too and both default to ``None``, which is the honest unknown
    rather than a constant nothing answered under."""
    signature = inspect.signature(emit)

    assert list(signature.parameters) == [
        "event_type",
        "screening_id",
        "payload",
        "sessions",
        "ruleset_version",
        "model_versions",
    ]
    for name in ("sessions", "ruleset_version", "model_versions"):
        assert signature.parameters[name].kind.name == "KEYWORD_ONLY"
    assert (
        signature.parameters["sessions"].default is inspect.Parameter.empty
    )
    assert signature.parameters["ruleset_version"].default is None
    assert signature.parameters["model_versions"].default is None


def test_the_writer_never_reaches_for_a_version_constant() -> None:
    """``models.py`` is careful that a row nothing has scored carries no
    ruleset; an event is held to the same bar, so this module cannot read
    :data:`app.version.RULESET_VERSION` and default to it."""
    source = ast.parse(
        pathlib.Path(emit_module.__file__).read_text(encoding="utf-8")
    )
    imported = {
        (node.module or "") for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom)
    }

    assert "app.version" not in imported


def test_the_writer_reaches_for_no_module_level_session_factory() -> None:
    """9.16's claim, held here too: nothing in this module is bound to the
    session factory :mod:`app.storage.db` builds at import time."""
    source = ast.parse(
        pathlib.Path(emit_module.__file__).read_text(encoding="utf-8")
    )
    imported = {
        (node.module or "") for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom)
    }
    named = {node.id for node in ast.walk(source) if isinstance(node, ast.Name)}

    assert "app.storage.db" not in imported
    assert not {"SessionLocal", "engine"} & named
