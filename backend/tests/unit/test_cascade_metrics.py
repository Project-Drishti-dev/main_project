"""26.8: what one cascade cost, and how it ended, as two log lines.

The task's verify is "the new tests pass", so what is held here is each half
of what the task asks for: **one latency line per tier the cascade ran**, and
**one outcome line naming how the whole of it ended** -- a closed vocabulary,
written even for a cascade that raised, because a run nobody can measure is
the run an operator most needs to find.

- **the count is held with a plan of two.**  The shipped plan holds one name,
  so "one line per tier" would be true for want of a second tier rather than
  because anything is measured twice.  The stubbed second tier raises if it is
  reached, so nothing but the measurement can be what stops it.
- **a latency is a measurement, not a constant.**  One stub sleeps, and its
  line has to show the sleep -- a field that is always the same number would
  satisfy every other assertion in this file.
- **the three outcomes are reached, not enumerated.**  Completed, hard-failed
  and raised are each produced by a plan that produces it, so a fourth way to
  end cannot be added without a case here.
- **the raised case still raises.**  The metric is written from a
  ``finally``; swallowing the fault to log it would be a second, worse
  behaviour.
- **one answer about the cascade, not two.**  The outcome line's tier names
  are held against the ``analysis_completed`` payload's, so the metric cannot
  come to disagree with the trail about what ran.
"""

import io
import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import metrics, screening
from app.audit.event_types import ANALYSIS_COMPLETED
from app.logging_config import APP_LOGGER_NAME, JsonFormatter, bind_request_id
from app.pipeline.tier0 import runner
from app.storage import db
from app.storage.models import AuditEvent, Base
from app.storage.repository import ScreeningRepository
from tests.fixtures import mrz_images

#: A page with no machine-readable zone on it: Tier 0 measures it, finds
#: nothing, and the cascade completes -- the shortest path to a measurement.
BLANK = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))

#: The id a caller offered and the flow adopted, so a row can be shown to
#: carry the offered value rather than one minted here.
OFFERED = "req-01HQ3K7M2N9P"

#: How long the slow stub spends, in seconds: long enough that the reading
#: cannot be the clock's own noise.
SLOW_SECONDS = 0.05

#: The sentence a stubbed hard fail answers with.  6.5's reason is one of the
#: findings' own labels, so a stand-in for one has to look like one.
HARD_FAIL = "The composite check digit does not match."


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema in it, and a factory."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield db.build_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture
def logged() -> Iterator[Callable[[], list[dict]]]:
    """Drain every line the ``app`` logger has written, parsed as JSON."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield lambda: [
            json.loads(line)
            for line in stream.getvalue().splitlines()
            if line.strip()
        ]
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


class Reached(Exception):
    """A fault a stubbed tier raises."""


def _screening(sessions: sessionmaker[Session], **overrides: Any):
    """One screening of a page with no MRZ zone, and the row it left."""
    arguments: dict[str, Any] = {
        "sessions": sessions,
        "image": BLANK.image,
        "document_type": "passport",
        "filename": "a-name-that-must-not-travel.jpg",
    }
    arguments.update(overrides)
    return screening.run_screening(**arguments)


def _clean(*_args: Any, **_kwargs: Any) -> runner.TierResult:
    """A stand-in tier answering with the empty result and nothing else."""
    return runner.TierResult()


def _hard_failed(*_args: Any, **_kwargs: Any) -> runner.TierResult:
    """A stand-in tier that stops the cascade, on :data:`HARD_FAIL`."""
    return runner.TierResult(hard_failed=True, hard_fail_reason=HARD_FAIL)


def _never(*_args: Any, **_kwargs: Any) -> runner.TierResult:
    """A stand-in tier that refuses to be reached after a hard fail."""
    raise AssertionError("a hard-failed cascade reached a second tier")


def _plan(monkeypatch: pytest.MonkeyPatch, *runners: Any) -> None:
    """Put ``runners`` in as the whole plan, Tier 0 first, then stand-ins.

    ``app.screening`` reads :data:`~app.screening.CASCADE` and its runner
    table at call time, which is what lets a plan of two stand in for the
    shipped plan of one.
    """
    names = (runner.TIER_NAME,) + tuple(f"tier_{n}" for n in range(1, len(runners)))
    monkeypatch.setattr(screening, "CASCADE", names)
    monkeypatch.setattr(screening, "_TIER_RUNNERS", dict(zip(names, runners)))


def _lines(logged: Callable[[], list[dict]], event: str) -> list[dict]:
    """Every line of one event, in the order it was written."""
    return [line for line in logged() if line["message"] == event]


def _stored(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> Any:
    """The committed row, read back over a fresh session."""
    row = ScreeningRepository(sessions).get(screening_id)
    assert row is not None, "the flow returned a row it did not store"
    return row


def _completed(sessions: sessionmaker[Session], screening_id: uuid.UUID) -> dict:
    """The one ``analysis_completed`` payload this screening wrote."""
    with sessions() as session:
        payloads = list(
            session.scalars(
                select(AuditEvent.payload).where(
                    AuditEvent.screening_id == screening_id,
                    AuditEvent.event_type == ANALYSIS_COMPLETED,
                )
            )
        )
    assert len(payloads) == 1, f"expected one payload, got {len(payloads)}"
    return payloads[0]


# --- one line per tier ----------------------------------------------------


def test_each_tier_the_cascade_ran_writes_one_latency_line(
    sessions, logged, monkeypatch
):
    """The headline: the count is the plan's, not an accident of one tier."""
    _plan(monkeypatch, runner.run_tier0, _clean)

    row = _screening(sessions)

    lines = _lines(logged, metrics.TIER_LATENCY_EVENT)
    assert [line["tier"] for line in lines] == list(screening.CASCADE)
    assert [line["screening_id"] for line in lines] == [str(row.id)] * 2


def test_a_latency_line_reports_that_tier_s_own_answer(
    sessions, logged, monkeypatch
):
    """Each line carries its own tier's stop, not the cascade's last one."""
    _plan(monkeypatch, _clean, _hard_failed)

    _screening(sessions)

    first, second = _lines(logged, metrics.TIER_LATENCY_EVENT)
    assert (first["hard_failed"], second["hard_failed"]) == (False, True)
    assert [first["flags_found"], second["flags_found"]] == [0, 0]


def test_the_latency_is_a_measurement_rather_than_a_constant(
    sessions, logged, monkeypatch
):
    """One tier sleeps, so its line has to show it -- a fixed field cannot."""

    def slow(*_args: Any, **_kwargs: Any) -> runner.TierResult:
        time.sleep(SLOW_SECONDS)
        return runner.TierResult()

    _plan(monkeypatch, _clean, slow)

    _screening(sessions)

    fast, slow_line = _lines(logged, metrics.TIER_LATENCY_EVENT)
    assert fast["elapsed_ms"] >= 0.0
    assert slow_line["elapsed_ms"] >= SLOW_SECONDS * 1000


def test_a_tier_a_hard_fail_kept_out_is_never_measured(
    sessions, logged, monkeypatch
):
    """A tier that did not run costs nothing, and is not reported as if it did."""
    _plan(monkeypatch, _hard_failed, _never)

    _screening(sessions)

    assert [line["tier"] for line in _lines(logged, metrics.TIER_LATENCY_EVENT)] == [
        runner.TIER_NAME
    ]


# --- one line per cascade, from a closed vocabulary -----------------------


def test_one_outcome_line_is_written_and_names_a_known_outcome(sessions, logged):
    """Exactly one per cascade, and a name a reader can group by."""
    _screening(sessions)

    lines = _lines(logged, metrics.CASCADE_OUTCOME_EVENT)

    assert len(lines) == 1
    assert lines[0]["outcome"] in metrics.CASCADE_OUTCOMES


def test_a_cascade_nothing_stopped_ended_completed(sessions, logged):
    """The ordinary answer, reached by a plan that runs to its end."""
    _screening(sessions)

    line = _lines(logged, metrics.CASCADE_OUTCOME_EVENT)[0]

    assert line["outcome"] == metrics.OUTCOME_COMPLETED
    assert line["tiers_run"] == list(screening.CASCADE)
    assert line["flags_found"] == 0
    assert line["elapsed_ms"] >= 0.0


def test_a_hard_fail_ended_the_cascade_and_that_is_the_outcome(
    sessions, logged, monkeypatch
):
    """The stop is the hard fail, and the outcome names it."""
    _plan(monkeypatch, _hard_failed, _never)

    _screening(sessions)

    line = _lines(logged, metrics.CASCADE_OUTCOME_EVENT)[0]
    assert line["outcome"] == metrics.OUTCOME_HARD_FAILED
    # The tiers that ran, and no skipped ones: the trail's own answer.
    assert line["tiers_run"] == [runner.TIER_NAME]


def test_a_cascade_that_raised_is_measured_and_still_raises(
    sessions, logged, monkeypatch
):
    """The outcome the other two cannot describe, and the fault is not hidden."""

    def raising(*_args: Any, **_kwargs: Any) -> runner.TierResult:
        raise Reached

    _plan(monkeypatch, raising, _clean)

    with pytest.raises(Reached):
        _screening(sessions)

    line = _lines(logged, metrics.CASCADE_OUTCOME_EVENT)[0]
    assert line["outcome"] == metrics.OUTCOME_FAILED
    # A tier that raised returned no result, so it has no latency to report
    # and no name to add: what ran is what returned.
    assert _lines(logged, metrics.TIER_LATENCY_EVENT) == []
    assert line["tiers_run"] == []


def test_the_outcome_line_and_the_trail_name_the_same_tiers(
    sessions, logged, monkeypatch
):
    """One answer about the cascade, not two that could come to disagree."""
    _plan(monkeypatch, runner.run_tier0, _clean)

    row = _screening(sessions)

    assert _lines(logged, metrics.CASCADE_OUTCOME_EVENT)[0]["tiers_run"] == list(
        _completed(sessions, row.id)[screening.TIERS_RUN_KEY]
    )


# --- the correlation id, on the record ------------------------------------


def test_the_row_carries_the_correlation_id_of_the_request_that_asked(
    sessions, logged
):
    """The join between a row found in the database and its own log lines."""
    with bind_request_id(OFFERED):
        row = _screening(sessions)

    assert _stored(sessions, row.id).request_id == OFFERED
    assert {line["request_id"] for line in logged()} == {OFFERED}


def test_a_screening_run_outside_a_request_carries_no_correlation_id(sessions):
    """``None`` is the honest absence: no id was bound, rather than a blank."""
    row = _screening(sessions)

    assert _stored(sessions, row.id).request_id is None