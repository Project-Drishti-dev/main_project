"""10.5: one ``tier_completed`` per tier that ran, and none for one that did not.

The task's verify is "a test asserting a hard-failed screening emits only
Tier 0", so that is the first test here.  The rest is what keeps the count an
answer rather than an accident of there being one tier today:

- **the plan is the runner table.**  :data:`app.screening.CASCADE` is that
  table's own keys, so a tier the flow names and a tier the trail records
  cannot drift apart, and a tier that ran without being recorded would have
  to be added as a runner rather than as a bare call.
- **a hard fail ends the cascade, and that is held with a plan of two.**  The
  real plan holds one name, which makes "only Tier 0" true for want of a
  second tier rather than because anything stopped.  The stubbed second tier
  raises if it is reached, so the stop is the only reading left.
- **the tier event is written before anything is scored**, stated with a
  weightset that cannot be loaded rather than by comparing two timestamps
  that could tie.
- **a tier event carries the versions that tier ran under**, which for a
  deterministic tier is ``None`` for both keys: handing it the screening's
  model versions would claim a model answered that did not.
"""

import datetime
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
from app.pipeline.tier0 import document, runner
from app.risk.weightsets.loader import WeightsetError
from app.storage import db
from app.storage.models import AuditEvent, Base, Screening
from tests.fixtures import mrz_images

#: The day 5.8's own suite measures against; no rule here reads a clock.
REFERENCE = datetime.date(2026, 9, 30)

#: A page with no machine-readable zone on it: nothing fires, and nothing
#: stops the cascade either.
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


def _of_type(events: list[AuditEvent], event_type: str) -> list[AuditEvent]:
    """Every event of that name, so a count can be asserted on its own."""
    return [event for event in events if event.event_type == event_type]


def _one_of(events: list[AuditEvent], event_type: str) -> AuditEvent:
    """The single event of that name, failing loudly on zero or two."""
    found = _of_type(events, event_type)
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


def _hard_failed(sessions: sessionmaker[Session]):
    """One screening of a page with a broken printed digit: 6.5's exit."""
    page, parsed = _broken_digit_page()
    row = _screening(
        sessions, image=page.image, parsed_document=parsed, reference_date=REFERENCE
    )
    return row, _trail(sessions, row.id)


# --- the task's claim ------------------------------------------------------


def test_a_hard_failed_screening_emits_only_tier_0(
    sessions: sessionmaker[Session],
):
    """The verify: one hard fail, one tier event, and it names Tier 0."""
    row, events = _hard_failed(sessions)

    tiers = _of_type(events, TIER_COMPLETED)
    assert len(tiers) == 1
    assert tiers[0].payload["tier"] == runner.TIER_NAME == "tier_0"
    assert _one_of(events, ANALYSIS_COMPLETED).payload[
        screening.TIERS_RUN_KEY
    ] == [runner.TIER_NAME]
    assert row.band == "high"


def test_a_clean_screening_records_its_tier_too(
    sessions: sessionmaker[Session],
):
    """The event says a tier ran, not that a tier failed."""
    row = _screening(sessions)

    tiers = _of_type(_trail(sessions, row.id), TIER_COMPLETED)
    assert len(tiers) == 1
    assert tiers[0].payload["tier"] == runner.TIER_NAME
    assert tiers[0].payload["hard_failed"] is False
    assert tiers[0].payload["flag_ids"] == []


def test_a_hard_fail_ends_the_cascade(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
):
    """With a second tier in the plan, the hard fail is what stops it."""
    page, parsed = _broken_digit_page()

    def never_runs(*args: Any, **kwargs: Any):
        raise AssertionError("a hard-failed cascade reached a second tier")

    monkeypatch.setattr(screening, "CASCADE", (runner.TIER_NAME, "tier_1"))
    monkeypatch.setattr(
        screening,
        "_TIER_RUNNERS",
        {runner.TIER_NAME: runner.run_tier0, "tier_1": never_runs},
    )
    row = _screening(
        sessions, image=page.image, parsed_document=parsed, reference_date=REFERENCE
    )

    events = _trail(sessions, row.id)
    assert [event.payload["tier"] for event in _of_type(events, TIER_COMPLETED)] == [
        runner.TIER_NAME
    ]


def test_a_cascade_without_a_hard_fail_reaches_the_next_tier(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
):
    """The stop is the hard fail, and not the shape of the plan."""
    class Reached(LookupError):
        """What a reached second tier raises, so arriving is loud."""

    def second_tier(*args: Any, **kwargs: Any):
        raise Reached("the second tier of this plan was reached")

    monkeypatch.setattr(screening, "CASCADE", (runner.TIER_NAME, "tier_1"))
    monkeypatch.setattr(
        screening,
        "_TIER_RUNNERS",
        {runner.TIER_NAME: runner.run_tier0, "tier_1": second_tier},
    )
    with pytest.raises(Reached):
        _screening(sessions)



# --- the plan and the trail are one thing ----------------------------------


def test_the_plan_is_the_runner_table_its_own_keys():
    """A tier the plan names has a runner, and a runner is in the plan."""
    assert screening.CASCADE == tuple(screening._TIER_RUNNERS)
    assert runner.TIER_NAME in screening.CASCADE
    assert all(
        callable(screening._TIER_RUNNERS[name]) for name in screening.CASCADE
    )


def test_the_tier_event_is_written_before_anything_is_scored(
    sessions: sessionmaker[Session],
):
    """A weightset that cannot be loaded stops the flow after the cascade."""
    with pytest.raises(WeightsetError):
        _screening(sessions, weightset="no-such-weightset")

    with sessions() as session:
        rows = session.execute(select(Screening)).scalars().all()
        events = session.execute(
            select(AuditEvent).where(AuditEvent.screening_id == rows[0].id)
        ).scalars().all()

    assert sorted(event.event_type for event in events) == sorted(
        [SCREENING_CREATED, TIER_COMPLETED]
    )
    assert rows[0].status == "pending"
    assert rows[0].score is None


def test_the_completed_event_names_the_tiers_the_trail_recorded(
    sessions: sessionmaker[Session],
):
    """The cascade's own answer about itself matches the events beside it."""
    row, events = _hard_failed(sessions)

    named = [event.payload["tier"] for event in _of_type(events, TIER_COMPLETED)]
    assert _one_of(events, ANALYSIS_COMPLETED).payload[screening.TIERS_RUN_KEY] == named


def test_two_screenings_do_not_share_a_tier_trail(
    sessions: sessionmaker[Session],
):
    """Each row's tier events are its own, so an id reused fails here."""
    first = _screening(sessions)
    second = _screening(sessions)

    first_tiers = _of_type(_trail(sessions, first.id), TIER_COMPLETED)
    second_tiers = _of_type(_trail(sessions, second.id), TIER_COMPLETED)
    assert first.id != second.id
    assert [event.id for event in first_tiers] != [event.id for event in second_tiers]
    assert [event.screening_id for event in first_tiers] == [first.id]
    assert [event.screening_id for event in second_tiers] == [second.id]


# --- what a tier event says ------------------------------------------------


def test_the_tier_event_carries_what_that_tier_found(
    sessions: sessionmaker[Session],
):
    """The findings go in as ids, and 6.5's reason is on the event."""
    _, events = _hard_failed(sessions)

    payload = _one_of(events, TIER_COMPLETED).payload
    assert payload["flag_ids"] == ["MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH"]
    assert payload["hard_failed"] is True
    assert payload["hard_fail_reason"]
    assert payload["detected_format"] == "TD3"
    assert not any(isinstance(leaf, float) for leaf in _leaves(payload))
    assert "stage_timings" not in payload


def test_a_tier_event_carries_no_version_of_its_own(
    sessions: sessionmaker[Session],
):
    """A deterministic tier ran no model and was scored by nothing yet."""
    row = _screening(sessions, model_versions={"tier2": "0.1.0"})

    payload = _one_of(_trail(sessions, row.id), TIER_COMPLETED).payload
    assert payload[MODEL_VERSIONS_KEY] is None
    assert payload[RULESET_VERSION_KEY] is None
    completed = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload
    assert completed[MODEL_VERSIONS_KEY] == row.model_versions
    assert completed[RULESET_VERSION_KEY] == row.ruleset_version


def test_nothing_about_the_upload_reaches_a_tier_event(
    sessions: sessionmaker[Session],
):
    """The filename is on the row and in no payload, as 10.4 settled it."""
    row = _screening(sessions)

    assert row.filename == "a-name-that-must-not-travel.jpg"
    for event in _of_type(_trail(sessions, row.id), TIER_COMPLETED):
        assert "filename" not in event.payload
        assert row.filename not in repr(event.payload)
