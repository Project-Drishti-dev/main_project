"""18.1: `POST /api/screenings/{id}/decision` takes the officer three choices.

Reached through the real app over one temporary database, so what is asserted
is what a client reads rather than what a handler returns: each choice is
taken with a remark and an override flag, the answer carries nothing read off
the document, and every refusal is the one envelope (D74).

The three are read off :mod:`app.audit.decision` rather than typed here, so a
fourth would add a case to this file instead of a second list.  Nothing here
asserts what a decision reaches the trail as: 18.3 is what writes it there.
"""

import re
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.decision import DECISION_CURRENT, OFFICER_ACTIONS
from app.main import app
from app.storage import db
from app.storage.models import Base
from app.storage.repository import ScreeningRepository

#: A code is the vocabulary a client branches on, so its spelling is held.
CODE = re.compile(r"[A-Z][A-Z0-9_]*")

#: An id no row carries, so a decision on it is a refusal and not a page.
MISSING = uuid.uuid4()

#: What the officer wrote with the choice: their own words, kept as written.
A_REMARK = "Checked the page against the book of issuers."

#: Every field the answer is required to carry: 18.1's four, which none of
#: the later tasks replaced, and the three 18.4 added beside them (D146).
THE_ANSWER_FIELDS = (
    "screening_id",
    "action",
    "remark",
    "override",
    "decision_id",
    "status",
    "supersedes",
)

#: The path this endpoint is served at, as the contract spells it.
DECISION_PATH = "/api/screenings/{screening_id}/decision"

#: A fourth spelling the officer does not get to make, for the refusal.
NOT_A_CHOICE = "escalate"


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


def _screening(sessions: sessionmaker[Session]) -> uuid.UUID:
    """One stored screening for a decision to be taken on."""
    return ScreeningRepository(sessions).create(
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        image_width=320,
        image_height=90,
    ).id


def _decide(client: TestClient, screening_id: uuid.UUID, **body) -> object:
    """The decision this endpoint is given, as a request."""
    return client.post(f"/api/screenings/{screening_id}/decision", json=body)


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


# --- the three choices, one case each -------------------------------------


def test_the_officer_makes_exactly_three_choices():
    """A fourth choice would be a case below rather than a second list."""
    assert len(OFFICER_ACTIONS) == 3


@pytest.mark.parametrize("action", OFFICER_ACTIONS)
def test_a_choice_is_taken_and_answered_back(client, sessions, action):
    """Each of the three: a 200 carrying the choice that was sent."""
    screening_id = _screening(sessions)

    response = _decide(
        client, screening_id, action=action, remark=A_REMARK, override=True
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == action
    assert body["screening_id"] == str(screening_id)


@pytest.mark.parametrize("action", OFFICER_ACTIONS)
def test_the_answer_is_the_four_values_the_request_named(client, sessions, action):
    """Nothing is dropped and none of 18.1's four is replaced: 18.4 grew the
    answer beside them (D143's revisit clause, taken in D146)."""
    screening_id = _screening(sessions)

    body = _decide(
        client, screening_id, action=action, remark=A_REMARK, override=True
    ).json()

    assert set(body) == set(THE_ANSWER_FIELDS)
    assert {key: body[key] for key in body if key != "decision_id"} == {
        "screening_id": str(screening_id),
        "action": action,
        "remark": A_REMARK,
        "override": True,
        "status": DECISION_CURRENT,
        "supersedes": None,
    }
    assert uuid.UUID(body["decision_id"])


def test_the_same_choice_taken_twice_is_two_answers_not_one(client, sessions):
    """Two decisions rather than one rewritten: the officer's own four values
    and the standing answer alike, with two records and the second naming the
    first (18.4, D146)."""
    screening_id = _screening(sessions)

    first = _decide(client, screening_id, action=OFFICER_ACTIONS[0])
    second = _decide(client, screening_id, action=OFFICER_ACTIONS[0])

    assert first.status_code == second.status_code == 200
    one, two = first.json(), second.json()
    assert set(one) == set(two) == set(THE_ANSWER_FIELDS)
    for key in ("screening_id", "action", "remark", "override", "status"):
        assert one[key] == two[key]
    assert one["supersedes"] is None
    assert two["supersedes"] == one["decision_id"]
    assert two["decision_id"] != one["decision_id"]


# --- the remark and the flag beside it ------------------------------------


def test_a_remark_is_kept_as_the_officer_wrote_it(client, sessions):
    """Not trimmed, not capitalised, not rewritten: it is their sentence."""
    remark = "  held for a second look at the printing  "
    screening_id = _screening(sessions)

    body = _decide(
        client, screening_id, action=OFFICER_ACTIONS[0], remark=remark
    ).json()

    assert body["remark"] == remark


def test_a_remark_may_be_left_out(client, sessions):
    """An officer who wrote nothing has not written the wrong thing."""
    screening_id = _screening(sessions)

    body = _decide(client, screening_id, action=OFFICER_ACTIONS[0]).json()

    assert body["remark"] == ""


@pytest.mark.parametrize("override", (True, False))
def test_the_override_flag_is_the_officers_own_claim(client, sessions, override):
    """It is what the caller sent, not what the band beside it implies."""
    screening_id = _screening(sessions)

    body = _decide(
        client, screening_id, action=OFFICER_ACTIONS[1], override=override
    ).json()

    assert body["override"] is override


def test_the_override_flag_is_off_when_the_caller_names_none(client, sessions):
    screening_id = _screening(sessions)

    body = _decide(client, screening_id, action=OFFICER_ACTIONS[1]).json()

    assert body["override"] is False


# --- nothing read off the document ---------------------------------------


def test_the_answer_carries_nothing_read_off_the_document(client, sessions):
    """The row holds a claim and a filename; neither belongs in this answer."""
    screening_id = _screening(sessions)

    response = _decide(client, screening_id, action=OFFICER_ACTIONS[0])

    assert "passport" not in response.text
    assert "a-name-that-must-not-travel" not in response.text
    assert "band" not in response.text


# --- what is refused ------------------------------------------------------


def test_a_screening_no_row_carries_is_refused(client, sessions):
    detail = _envelope(_decide(client, MISSING, action=OFFICER_ACTIONS[0]))

    assert detail["code"] == "SCREENING_NOT_FOUND"


def test_a_screening_that_was_deleted_is_not_decided(client, sessions):
    """8.15 reads skip a deleted row, so a decision on one is a 404 as well."""
    screening_id = _screening(sessions)
    ScreeningRepository(sessions).soft_delete(
        screening_id, deleted_at=datetime.now(timezone.utc)
    )

    detail = _envelope(_decide(client, screening_id, action=OFFICER_ACTIONS[0]))

    assert detail["code"] == "SCREENING_NOT_FOUND"


@pytest.mark.parametrize("action", (NOT_A_CHOICE, "ALLOW", "", "allow "))
def test_a_choice_outside_the_three_is_refused(client, sessions, action):
    """Casing and spacing included: the vocabulary is three exact words."""
    screening_id = _screening(sessions)

    detail = _envelope(_decide(client, screening_id, action=action))

    assert detail["code"] == "INVALID_DECISION_ACTION"


def test_the_refusal_names_the_three_choices_it_will_take(client, sessions):
    """The message is built from the constants, so it cannot fall behind them."""
    screening_id = _screening(sessions)

    detail = _envelope(_decide(client, screening_id, action=NOT_A_CHOICE))

    for choice in OFFICER_ACTIONS:
        assert choice in detail["message"]


def test_a_body_naming_no_choice_is_refused(client, sessions):
    screening_id = _screening(sessions)

    detail = _envelope(client.post(f"/api/screenings/{screening_id}/decision", json={}))

    assert detail["code"] == "INVALID_REQUEST"


def test_a_choice_that_is_not_text_is_refused(client, sessions):
    screening_id = _screening(sessions)

    detail = _envelope(_decide(client, screening_id, action=3))

    assert detail["code"] == "INVALID_REQUEST"


def test_an_id_that_is_not_a_uuid_is_refused(client):
    response = client.post("/api/screenings/not-a-uuid/decision", json={"action": "allow"})

    assert _envelope(response)["code"] == "INVALID_REQUEST"


def test_a_body_that_is_not_json_is_refused(client, sessions):
    screening_id = _screening(sessions)

    response = client.post(
        f"/api/screenings/{screening_id}/decision",
        content=b"action=allow",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert _envelope(response)["code"] == "INVALID_REQUEST"


def test_the_officer_is_asked_for_no_credential(client, sessions):
    """A decision is taken from the station, with nothing to sign in with."""
    screening_id = _screening(sessions)

    response = _decide(client, screening_id, action=OFFICER_ACTIONS[0])

    assert response.status_code == 200
    assert "password" not in response.text.lower()
    assert "authorization" not in {h.lower() for h in response.request.headers}


# --- the contract the route declares --------------------------------------


def test_the_route_declares_no_security_requirement():
    """No authentication: the contract asks for no credential and names none."""
    schema = app.openapi()

    assert "security" not in schema["paths"][DECISION_PATH]["post"]
    assert schema.get("components", {}).get("securitySchemes") is None


def test_the_route_declares_a_json_body_and_a_json_answer():
    """One request shape and one answer, so a client parses one of each."""
    schema = app.openapi()
    operation = schema["paths"][DECISION_PATH]["post"]

    request = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request["$ref"].endswith("/DecisionRequest")
    assert operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/DecisionResponse")


@pytest.mark.parametrize("status", ("404", "422", "500"))
def test_every_refusal_the_route_declares_is_the_shared_model(status):
    """The document says the same thing the body does, or says nothing."""
    schema = app.openapi()
    responses = schema["paths"][DECISION_PATH]["post"]["responses"]

    model = responses[status]["content"]["application/json"]["schema"]["$ref"]
    assert model == "#/components/schemas/ErrorResponse"


def test_the_body_needs_no_field_beyond_the_three():
    """``action`` alone is a whole request; the other two have defaults."""
    schema = app.openapi()
    name = "DecisionRequest"
    body = schema["components"]["schemas"][name]

    assert set(body["properties"]) == {"action", "remark", "override"}
    assert body["required"] == ["action"]

