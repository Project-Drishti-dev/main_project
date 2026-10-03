"""18.2: the band refuses a choice the officer has not claimed as their own.

Reached through the real app over one temporary database, as 18.1's file is:
what is asserted is what a client reads rather than what a handler returns.
**The claim to hold is that this is a validation error and not a silent
accept**, so every case reads the status code, and two of them assert that the
answer shape is gone rather than merely thin.

The rule is read off :mod:`app.audit.decision` -- the bands are its
:data:`~app.audit.decision.BAND_ORDER`, the choices are its
:data:`~app.audit.decision.OFFICER_ACTIONS` -- so a fourth of either would add
a case here rather than a second list, and the band is always the stored one:
a request cannot name the band it is made against.  Nothing here asserts what a
decision reaches the trail as; 18.3 is that.
"""

import re
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.decision import (
    BAND_ORDER,
    DECISION_CURRENT,
    OFFICER_ACTIONS,
    REJECT_ENTRY,
    DecisionError,
    contradicts_band,
    override_required,
)
from app.main import app
from app.storage import db
from app.storage.models import Base, Screening
from app.storage.repository import ScreeningRepository

#: A code is the vocabulary a client branches on, so its spelling is held.
CODE = re.compile(r"[A-Z][A-Z0-9_]*")

#: The path this rule is served at, as the contract spells it.
DECISION_PATH = "/api/screenings/{screening_id}/decision"

#: The refusal this endpoint answers with when the choice contradicts the band
#: and the officer sent no flag.  Held here so a respelling fails a case.
THE_CODE = "DECISION_OVERRIDE_REQUIRED"

#: The fields a taken decision carries: none of them may survive a refusal.
#: 18.1's four, which 18.4 grew beside rather than into (D146).
THE_ANSWER_FIELDS = (
    "screening_id",
    "action",
    "remark",
    "override",
    "decision_id",
    "status",
    "supersedes",
)

#: The band the task names, and the one the adverse choice agrees with, both
#: read off the ordering rather than typed so a retune of it moves this file.
LOW = BAND_ORDER[0]
AGREEING = BAND_ORDER[-1]

#: A fourth spelling the officer does not get to make, for the vocabulary.
NOT_A_CHOICE = "escalate"

#: What the officer wrote with the choice.  A sentence is not a claim.
A_REASON = "The face does not match the live capture."


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


def _screening(sessions: sessionmaker[Session], band: str | None) -> uuid.UUID:
    """One stored screening, carrying the band the risk engine left on it."""
    with sessions() as session:
        row = Screening(
            document_type="passport",
            filename="a-name-that-must-not-travel.jpg",
            image_width=1240,
            image_height=1754,
            band=band,
        )
        session.add(row)
        session.commit()
        return row.id


def _decide(client: TestClient, screening_id: uuid.UUID, **body):
    """The decision this endpoint is given, as a request."""
    return client.post(DECISION_PATH.format(screening_id=screening_id), json=body)


def _envelope(response) -> dict:
    """Assert the one body every refusal is answered in, and hand it back."""
    assert response.status_code >= 400, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {"error"}, body
    detail = body["error"]
    assert set(detail) == {"code", "message"}, detail
    assert CODE.fullmatch(detail["code"]), detail["code"]
    assert detail["message"].strip(), detail
    return detail


# --- the refusal, and that it is one --------------------------------------


def test_the_adverse_choice_on_a_low_band_is_refused_without_the_flag(client, sessions):
    """18.2's one case: a 422 where a silent accept would have answered 200."""
    screening_id = _screening(sessions, band=LOW)

    response = _decide(client, screening_id, action=REJECT_ENTRY)

    assert response.status_code == 422, response.text
    assert _envelope(response)["code"] == THE_CODE


def test_the_refusal_carries_none_of_the_answer_a_decision_would(client, sessions):
    """A client parsing one shape cannot read a refusal as a decision taken."""
    screening_id = _screening(sessions, band=LOW)

    body = _decide(client, screening_id, action=REJECT_ENTRY).json()

    assert not set(THE_ANSWER_FIELDS) & set(body)


def test_the_flag_left_out_is_the_flag_declined(client, sessions):
    """A caller who names no flag has not claimed the choice either."""
    screening_id = _screening(sessions, band=LOW)

    left_out = _decide(client, screening_id, action=REJECT_ENTRY)
    declined = _decide(client, screening_id, action=REJECT_ENTRY, override=False)

    assert left_out.status_code == declined.status_code == 422
    assert _envelope(left_out)["code"] == _envelope(declined)["code"] == THE_CODE


def test_the_same_choice_with_the_flag_is_taken(client, sessions):
    """One field of difference, and the answer is the 200 beside the refusal.
    18.4's three fields are answered beside 18.1's four, none replaced."""
    screening_id = _screening(sessions, band=LOW)

    response = _decide(client, screening_id, action=REJECT_ENTRY, override=True)

    assert response.status_code == 200, response.text
    body = response.json()
    assert {key: body[key] for key in body if key != "decision_id"} == {
        "screening_id": str(screening_id),
        "action": REJECT_ENTRY,
        "remark": "",
        "override": True,
        "status": DECISION_CURRENT,
        "supersedes": None,
    }
    assert uuid.UUID(body["decision_id"])


def test_the_refusal_names_the_flag_the_officer_has_to_send(client, sessions):
    """A dashboard reads this to ask for the second click, so it must say it."""
    screening_id = _screening(sessions, band=LOW)

    detail = _envelope(_decide(client, screening_id, action=REJECT_ENTRY))

    assert "override" in detail["message"]


def test_a_remark_does_not_stand_in_for_the_flag(client, sessions):
    """18.1 keeps the officer sentence as written; writing one is not a claim."""
    screening_id = _screening(sessions, band=LOW)

    response = _decide(client, screening_id, action=REJECT_ENTRY, remark=A_REASON)

    assert response.status_code == 422, response.text


# --- where the rule does and does not reach -------------------------------


def test_the_band_the_choice_agrees_with_needs_no_flag(client, sessions):
    """The adverse choice on the adverse band is the agreement, not a conflict."""
    screening_id = _screening(sessions, band=AGREEING)

    response = _decide(client, screening_id, action=REJECT_ENTRY)

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("action", (OFFICER_ACTIONS[0], OFFICER_ACTIONS[1]))
def test_the_other_two_choices_are_never_held_to_the_flag(client, sessions, action):
    """A choice disagreeing the other way is the officer exercising it."""
    screening_id = _screening(sessions, band=LOW)

    response = _decide(client, screening_id, action=action)

    assert response.status_code == 200, response.text


def test_the_band_is_the_stored_one_and_not_the_requested_one(client, sessions):
    """A body naming a band does not lift, or bring, the refusal it earns."""
    low = _screening(sessions, band=LOW)
    high = _screening(sessions, band=AGREEING)

    named_high = _decide(client, low, action=REJECT_ENTRY, band=AGREEING)
    named_low = _decide(client, high, action=REJECT_ENTRY, band=LOW)

    assert named_high.status_code == 422, named_high.text
    assert named_low.status_code == 200, named_low.text


def test_a_row_nothing_scored_carries_no_band_to_go_against(client, sessions):
    """The rule asks about a band, and an unscored row has shown none."""
    screening_id = _screening(sessions, band=None)

    response = _decide(client, screening_id, action=REJECT_ENTRY)

    assert response.status_code == 200, response.text


# --- what is answered before the rule -------------------------------------


def test_a_row_that_was_deleted_is_refused_before_the_band_is_read(client, sessions):
    """The id is answered first, so 8.15's rule holds here as it does there."""
    screening_id = _screening(sessions, band=LOW)
    ScreeningRepository(sessions).soft_delete(
        screening_id, deleted_at=datetime.now(timezone.utc)
    )

    detail = _envelope(_decide(client, screening_id, action=REJECT_ENTRY))

    assert detail["code"] == "SCREENING_NOT_FOUND"


def test_a_choice_outside_the_three_is_refused_before_the_band_is_read(client, sessions):
    """18.1's vocabulary refusal, and it never depended on a band either."""
    screening_id = _screening(sessions, band=LOW)

    detail = _envelope(_decide(client, screening_id, action=NOT_A_CHOICE))

    assert detail["code"] == "INVALID_DECISION_ACTION"


# --- the rule, asked directly ---------------------------------------------


@pytest.mark.parametrize("band", BAND_ORDER)
def test_the_rule_is_the_disagreement_it_asks_about(band):
    """One direction of :func:`~app.audit.decision.contradicts_band`, so the
    two cannot drift apart."""
    assert override_required(band, REJECT_ENTRY) == contradicts_band(band, REJECT_ENTRY)


@pytest.mark.parametrize("band", BAND_ORDER)
@pytest.mark.parametrize("action", (OFFICER_ACTIONS[0], OFFICER_ACTIONS[1]))
def test_the_rule_never_holds_either_other_choice_to_the_flag(band, action):
    assert override_required(band, action) is False


def test_the_flag_is_required_on_every_band_below_the_adverse_one():
    """Read off the ordering, so this is every band but the last and no more."""
    required = [band for band in BAND_ORDER if override_required(band, REJECT_ENTRY)]

    assert required == list(BAND_ORDER[:-1])


def test_the_rule_refuses_a_name_it_cannot_read():
    """A band outside the ordering and a fourth choice are both refused."""
    with pytest.raises(DecisionError):
        override_required(LOW.upper(), REJECT_ENTRY)

    with pytest.raises(DecisionError):
        override_required(LOW, NOT_A_CHOICE)
