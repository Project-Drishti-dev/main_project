"""10.4: the screening flow writes the row, and the events beside it.

The task's verify is "tests asserting both exist after one screening", so
that is the first test here, and 10.5's ``tier_completed`` is in the count
with the other two.  The rest is what makes the trail honest:

- **nothing is written that names a score the engine has not produced.**  A
  weightset that cannot be loaded raises with the row still ``pending`` and
  no ``analysis_completed`` beside it, which is the ordering claim stated
  without a comparison of two timestamps that could tie.
- **the two events say different things about the versions.**  The first
  carries both keys as the unknowns they are, and the second carries the
  row's own ``ruleset_version`` and ``model_versions`` -- read off the row,
  never a constant, which is what ``D67`` asks the caller for.
- **the score reaches a payload as a scaled integer.**  A ``float`` is
  refused before a row is written (``D48``), so a payload that cannot be
  hashed cannot be stored and this flow would raise rather than record.
- **nothing about the upload leaves the row.**  The filename is written on
  the row and reaches neither event, and no payload carries a ``float``.
- **the hard-fail table is handed to the engine.**  A broken printed check
  digit lifts the score to the floor and the band to ``high``, which no
  score without 6.5's ids would reach.
- **two screenings do not share a trail.**  Each row's events are its own,
  so a flow that reused an id between them fails here.
- **``emit`` is the only writer.**  This module names no ``AuditEvent`` and
  adds nothing to a session itself.
"""

import ast
import datetime
import pathlib
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import screening
from app.audit.emit import MODEL_VERSIONS_KEY, RULESET_VERSION_KEY
from app.audit.event_types import (
    ANALYSIS_COMPLETED,
    SCREENING_CREATED,
    TIER_COMPLETED,
)
from app.pipeline.tier0 import document
from app.risk.hard_rules import DEFAULT_HARD_FAIL_FLOOR
from app.risk.weightsets.loader import WeightsetError, load_weightset
from app.storage import db
from app.storage.models import AuditEvent, Base, Screening
from tests.fixtures import mrz_images

flow_module = pathlib.Path(screening.__file__)

#: The day 5.8's own suite measures against; no rule here reads a clock.
REFERENCE = datetime.date(2026, 9, 30)

#: A page with no machine-readable zone on it: the empty result, and the
#: shortest path from an upload to a completed row.
BLANK = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema in it, and a factory
    over it -- the same shape :mod:`app.audit.emit`'s own suite writes to."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield db.build_session_factory(engine)
    finally:
        engine.dispose()


def _screening(sessions: sessionmaker[Session], **overrides: Any):
    """One screening of a page with no MRZ zone, and the row it left."""
    arguments = {
        "sessions": sessions,
        "image": BLANK.image,
        "document_type": "passport",
        "filename": "a-name-that-must-not-travel.jpg",
    }
    arguments.update(overrides)
    return screening.run_screening(**arguments)


def _trail(
    sessions: sessionmaker[Session], screening_id: uuid.UUID
) -> list[AuditEvent]:
    """The events one screening wrote, read back over a fresh session."""
    with sessions() as session:
        return list(
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.screening_id == screening_id)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
            .scalars()
            .all()
        )


def _one_of(events: list[AuditEvent], event_type: str) -> AuditEvent:
    """The single event of that name, failing loudly on zero or two."""
    found = [event for event in events if event.event_type == event_type]
    assert len(found) == 1, f"expected one {event_type}, got {len(found)}"
    return found[0]


def _leaves(value: Any) -> Any:
    """Every leaf of a payload, so a ``float`` can be looked for anywhere."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item)
    else:
        yield value


def _broken_digit_page():
    """A drawn TD3 whose printed composite digit is wrong, and its parse
    read back off the pixels rather than off this file."""
    zone = list(mrz_images.SPECIMENS["TD3"])
    printed = zone[1][43]
    zone[1] = zone[1][:43] + ("0" if printed != "0" else "1") + zone[1][44:]
    page = mrz_images.render_format("TD3", lines=tuple(zone))
    return page, document.parse_mrz(mrz_images.read_zone(page))


# --- the task's claim ------------------------------------------------------


def test_one_screening_writes_both_events(sessions: sessionmaker[Session]):
    """The verify: after one screening the trail holds both names."""
    row = _screening(sessions)

    events = _trail(sessions, row.id)
    assert len(events) == 3
    assert sorted(event.event_type for event in events) == sorted(
        [SCREENING_CREATED, TIER_COMPLETED, ANALYSIS_COMPLETED]
    )


def test_no_event_names_a_score_the_engine_never_produced(
    sessions: sessionmaker[Session],
):
    """A weightset that cannot be loaded stops the flow before the score."""
    with pytest.raises(WeightsetError):
        _screening(sessions, weightset="no-such-weightset")

    with sessions() as session:
        rows = session.execute(select(Screening)).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        events = session.execute(
            select(AuditEvent).where(AuditEvent.screening_id == row.id)
        ).scalars().all()

    assert sorted(event.event_type for event in events) == sorted(
        [SCREENING_CREATED, TIER_COMPLETED]
    )
    assert row.status == "pending"
    assert row.score is None and row.ruleset_version is None


# --- what each of the two says --------------------------------------------


def test_the_created_event_carries_both_version_keys_as_unknowns(
    sessions: sessionmaker[Session],
):
    """Nothing has scored yet, so both keys are present and ``None``."""
    row = _screening(sessions)

    payload = _one_of(_trail(sessions, row.id), SCREENING_CREATED).payload
    assert payload[RULESET_VERSION_KEY] is None
    assert payload[MODEL_VERSIONS_KEY] is None


def test_the_created_event_records_what_the_upload_carried(
    sessions: sessionmaker[Session],
):
    """The kind, and the two size columns -- read off the row, not retyped."""
    row = _screening(sessions)

    payload = _one_of(_trail(sessions, row.id), SCREENING_CREATED).payload
    height, width = BLANK.image.shape[:2]
    assert payload["document_type"] == row.document_type == "passport"
    assert payload["image_width"] == row.image_width == int(width)
    assert payload["image_height"] == row.image_height == int(height)


def test_the_completed_event_hands_over_the_row_s_own_ruleset(
    sessions: sessionmaker[Session],
):
    """The version is the weightset's, and it is the row's column."""
    row = _screening(sessions)

    payload = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload
    assert row.ruleset_version == load_weightset().ruleset_version
    assert payload[RULESET_VERSION_KEY] == row.ruleset_version


def test_the_completed_event_hands_over_the_row_s_own_model_versions(
    sessions: sessionmaker[Session],
):
    """What the cascade recorded on the row is what the event carries."""
    row = _screening(sessions, model_versions={"tier2": "0.1.0"})

    payload = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload
    assert row.model_versions == {"tier2": "0.1.0"}
    assert payload[MODEL_VERSIONS_KEY] == row.model_versions


def test_no_model_answered_and_the_key_is_still_there(
    sessions: sessionmaker[Session],
):
    """``None`` is an answer, so the key is written rather than omitted."""
    row = _screening(sessions)

    payload = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload
    assert row.model_versions is None
    assert MODEL_VERSIONS_KEY in payload
    assert payload[MODEL_VERSIONS_KEY] is None


# --- the payload is spellable at all ---------------------------------------


def test_the_completed_payload_carries_the_score_as_a_scaled_integer(
    sessions: sessionmaker[Session],
):
    """A ``float`` in a payload is refused before a row is written."""
    row = _screening(sessions)

    payload = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload
    assert payload[screening.SCORE_BP_KEY] == round(row.score * 100)
    assert isinstance(payload[screening.SCORE_BP_KEY], int)
    assert not any(isinstance(leaf, float) for leaf in _leaves(payload))


def test_the_completed_payload_names_the_findings_and_the_hard_fail(
    sessions: sessionmaker[Session],
):
    """A broken printed digit is a finding, and 6.5 lifts the score."""
    page, parsed = _broken_digit_page()
    row = _screening(
        sessions,
        image=page.image,
        parsed_document=parsed,
        reference_date=REFERENCE,
    )

    payload = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload
    assert payload["flag_ids"] == ["MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH"]
    assert payload["hard_failed"] is True
    assert payload["hard_fail_reason"]
    assert row.score == DEFAULT_HARD_FAIL_FLOOR
    assert payload["band"] == row.band == "high"
    assert payload["detected_format"] == "TD3"


def test_nothing_about_the_upload_leaves_the_row(
    sessions: sessionmaker[Session],
):
    """The filename is stored on the row and carried into no event."""
    row = _screening(sessions)

    assert row.filename == "a-name-that-must-not-travel.jpg"
    for event in _trail(sessions, row.id):
        assert "filename" not in event.payload
        assert row.filename not in repr(event.payload)


def test_two_screenings_do_not_share_a_trail(
    sessions: sessionmaker[Session],
):
    """Each row's events are its own, so an id reused between them fails."""
    first = _screening(sessions)
    second = _screening(sessions)

    assert first.id != second.id
    assert {event.event_type for event in _trail(sessions, first.id)} == {
        SCREENING_CREATED,
        TIER_COMPLETED,
        ANALYSIS_COMPLETED,
    }
    assert {event.event_type for event in _trail(sessions, second.id)} == {
        SCREENING_CREATED,
        TIER_COMPLETED,
        ANALYSIS_COMPLETED,
    }


# --- the writer is still the only writer -----------------------------------


def test_the_flow_writes_no_event_of_its_own():
    """``emit`` is the only thing that builds an ``AuditEvent``."""
    tree = ast.parse(flow_module.read_text(encoding="utf-8"))
    built = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    } | {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    assert "AuditEvent" not in built
    assert "add" not in built
