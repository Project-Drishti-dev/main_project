"""11.2: ``GET /api/screenings/{id}`` answers with the whole stored screening.

The endpoint is reached through the real app with the real flow behind it and
one temporary database under it, so what is asserted is the answer a client
reads rather than a route's return value: every field the task names is
present, the score, the band and the ruleset version are the stored row's own
columns rather than numbers recomputed beside them, a finding carries the
polygon the officer's screen highlights, and the contributions are one
``weight x value`` term per finding in the same order.

**The evidence under the endpoint is a real cascade's.**  A page with no
machine-readable zone produces no findings, so a blank upload alone could
only prove that empty lists are answered.  A drawn TD3 whose printed
composite digit is wrong is screened through
:func:`app.screening.run_screening` with its own parse, which is how a rule
gets its characters, and 6.2 then boxes the failing digit on the page -- so
the flags and the terms are asserted on findings that really fired and
really carry a region.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.main import app
from app.pipeline.tier0 import document
from app.risk.hard_rules import DEFAULT_HARD_FAIL_FLOOR
from app.risk.weightsets.loader import load_weightset
from app.screening import run_screening
from app.storage import db
from app.storage.models import Base, Screening
from app.storage.repository import ScreeningRepository
from tests.fixtures import mrz_images


#: Every field 11.2's answer is required to carry.  Written out once and read
#: back against the response body, so a field dropped from the contract fails
#: here rather than being noticed by a screen that renders nothing.
THE_ANSWER_FIELDS = (
    "screening_id",
    "status",
    "document_type",
    "created_at",
    "image",
    "score",
    "band",
    "ruleset_version",
    "model_versions",
    "summary",
    "flags",
    "contributions",
    "stage_trace",
)

#: The twelve a stored finding carries, as 5.2's own record holds them.
THE_FLAG_FIELDS = (
    "id",
    "tier",
    "label",
    "weight_band",
    "value",
    "confidence",
    "region",
    "expected",
    "found",
    "reason",
    "source_module",
    "field",
)


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema, and a factory over it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        factory = db.build_session_factory(engine)
        app.dependency_overrides[get_sessions] = lambda: factory
        yield factory
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _broken_digit_screening(sessions: sessionmaker[Session]) -> Screening:
    """One screening of a TD3 whose printed composite digit is wrong.

    The page is parsed back off its own pixels rather than handed over as
    text, and the parse is what 6.2 reads its characters from, so the
    finding is the rule's own rather than a fixture's.
    """
    zone = list(mrz_images.SPECIMENS["TD3"])
    printed = zone[1][43]
    zone[1] = zone[1][:43] + ("0" if printed != "0" else "1") + zone[1][44:]
    page = mrz_images.render_format("TD3", lines=tuple(zone))
    return run_screening(
        sessions=sessions,
        image=page.image,
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        parsed_document=document.parse_mrz(mrz_images.read_zone(page)),
    )


def _read(client: TestClient, row: Screening) -> dict:
    """The answer 11.2's endpoint gives for ``row``."""
    response = client.get(f"/api/screenings/{row.id}")
    assert response.status_code == 200
    return response.json()


# --- every field the answer must carry ------------------------------------


def test_every_field_the_task_names_is_present(client, sessions):
    """The task's own verify: score, band, flags, contributions, version."""
    row = _broken_digit_screening(sessions)

    body = _read(client, row)

    assert set(body) == set(THE_ANSWER_FIELDS)
    assert body["screening_id"] == str(row.id)
    assert body["status"] == "completed"
    assert body["document_type"] == "passport"
    assert body["image"] == {
        "width": row.image_width,
        "height": row.image_height,
    }
    assert body["created_at"] is not None
    assert isinstance(body["score"], (int, float))
    assert isinstance(body["band"], str)
    assert body["ruleset_version"] == row.ruleset_version
    assert body["flags"]
    assert body["contributions"]
    assert "summary" in body
    assert "model_versions" in body


def test_the_answer_is_the_row_s_own_columns_and_not_a_second_reading(
    client, sessions
):
    """The score beside the officer is the score that was stored, not a new one."""
    row = _broken_digit_screening(sessions)

    body = _read(client, row)

    with sessions() as session:
        stored = session.execute(
            select(Screening).where(Screening.id == row.id)
        ).scalar_one()
    assert body["score"] == stored.score
    assert body["band"] == stored.band
    assert body["ruleset_version"] == stored.ruleset_version
    assert body["flags"] == stored.flags


def test_nothing_about_the_upload_reaches_the_answer(client, sessions):
    """The name the upload arrived under is on the row and on no answer."""
    row = _broken_digit_screening(sessions)

    body = _read(client, row)

    assert "a-name-that-must-not-travel" not in str(body)


# --- the flags, with the region a highlight is drawn over -----------------


def test_every_flag_carries_the_twelve_fields_and_a_locatable_region(
    client, sessions
):
    row = _broken_digit_screening(sessions)

    flags = _read(client, row)["flags"]

    for flag in flags:
        assert set(flag) == set(THE_FLAG_FIELDS)
        assert flag["id"] and flag["label"] and flag["reason"]
        assert 0.0 <= flag["value"] <= 1.0
        assert 0.0 <= flag["confidence"] <= 1.0
        assert flag["region"] is not None
        assert len(flag["region"]) >= 3
        for corner in flag["region"]:
            assert len(corner) == 2
            assert all(isinstance(pixel, int) for pixel in corner)


def test_a_finding_with_nowhere_to_point_is_listed_rather_than_dropped(
    client, sessions
):
    """``None`` is a claim about the page, and 23.6 is what reads it.

    Tier 0 boxes every finding it makes over a printed field, so a page that
    cannot be located is one this fixture cannot draw.  The stored column is
    cleared instead, which is the state a rule with nothing to point at would
    leave, and the read is asked whether it drops such a finding.
    """
    row = _broken_digit_screening(sessions)
    with sessions() as session:
        stored = session.merge(row)
        stored.flags = [
            {**finding, "region": None} for finding in (row.flags or [])
        ]
        session.commit()
    body = _read(client, row)

    assert [flag["region"] for flag in body["flags"]] == [None] * len(body["flags"])
    assert [flag["id"] for flag in body["flags"]] == [
        term["id"] for term in body["contributions"]
    ]


# --- the contributions, and what they add up to ---------------------------


def test_the_contributions_are_one_weight_times_value_term_per_finding(
    client, sessions
):
    row = _broken_digit_screening(sessions)

    body = _read(client, row)
    contributions = body["contributions"]

    assert [term["id"] for term in contributions] == [
        flag["id"] for flag in body["flags"]
    ]
    for term, flag in zip(contributions, body["flags"], strict=True):
        assert set(term) == {"id", "weight", "value", "contribution"}
        assert term["value"] == flag["value"]
        assert term["contribution"] == term["weight"] * term["value"]


def test_the_terms_are_weighed_by_the_ruleset_the_row_names(client, sessions):
    """A weight is the weightset's, so the version beside it is the file's."""
    row = _broken_digit_screening(sessions)
    weightset = load_weightset()

    body = _read(client, row)

    assert body["ruleset_version"] == weightset.ruleset_version
    for term in body["contributions"]:
        assert term["weight"] == weightset.flags[term["id"]]["weight"]


def test_the_terms_are_the_pre_history_total_and_not_the_score(client, sessions):
    """4.8's term, 6.5's floor and 7.7's clamp all sit between the two."""
    row = _broken_digit_screening(sessions)

    body = _read(client, row)
    total = sum(term["contribution"] for term in body["contributions"])

    assert total < body["score"]
    assert body["score"] == DEFAULT_HARD_FAIL_FLOOR


# --- a row nobody scored, and an id no row carries ------------------------


def test_a_screening_nobody_scored_is_answered_rather_than_refused(
    client, sessions
):
    """11.1 hands back an id before the cascade runs, and 11.2 reads it."""
    created = ScreeningRepository(sessions).create(
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        image_width=320,
        image_height=90,
    )

    body = _read(client, created)

    assert body["status"] == "pending"
    assert body["score"] is None
    assert body["band"] is None
    assert body["ruleset_version"] is None
    assert body["flags"] == []
    assert body["contributions"] == []


def test_an_id_no_row_carries_is_a_404_in_the_shared_envelope(client, sessions):
    """11.4 is what holds this body to the shape every other refusal uses."""
    response = client.get(f"/api/screenings/{uuid.uuid4()}")

    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "SCREENING_NOT_FOUND"


def test_an_id_that_is_not_one_is_refused_before_the_table_is_read(
    client, sessions
):
    """A string that is not a uuid is 11.4's question, and the envelope's."""
    response = client.get("/api/screenings/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_a_deleted_screening_is_absent_rather_than_readable(client, sessions):
    """8.15's rule reaches this read through ``ScreeningRepository.get``."""
    row = _broken_digit_screening(sessions)
    ScreeningRepository(sessions).soft_delete(
        row.id, deleted_at=datetime.now(timezone.utc)
    )

    response = client.get(f"/api/screenings/{row.id}")

    assert response.status_code == 404


def test_a_row_scored_under_a_ruleset_the_package_no_longer_ships_is_refused(
    client, sessions
):
    """Terms weighed by the wrong file would not add up to the score beside
    them, so the read is refused rather than answered with a mismatch."""
    row = _broken_digit_screening(sessions)
    with sessions() as session:
        stored = session.merge(row)
        stored.ruleset_version = "a-ruleset-this-deployment-does-not-ship"
        session.commit()

    response = client.get(f"/api/screenings/{row.id}")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "SCREENING_UNREADABLE",
            "message": "This result could not be read. Please try again later.",
        }
    }
    assert "a-ruleset-this-deployment-does-not-ship" not in response.text
