"""11.5: every answer carries the id its request was stamped with.

``app.api.request_id`` owns the one header name and the one middleware that
stamps a request and answers with the same value.  This file holds the four
answers the app can give -- a success, a refusal in the envelope, a router
miss, and the 500 for a fault no route caught -- plus the two rules the
stamp itself has: an id a caller offers is the one it is answered with, and
one that is not id-shaped is replaced rather than reflected.

No route reads ``request.state`` yet; 11.6's log line and 26.8's
correlation column are what reach it, so the state is asserted here against a
middleware of its own rather than through a route added for the test.
"""

import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions, routes_screenings
from app.api.request_id import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    resolve_request_id,
)
from app.main import app
from app.storage import db
from app.storage.models import Base


#: An id no row carries, so the read below reaches a refusal rather than a page.
MISSING = uuid.uuid4()

#: The two shapes a minted id takes, and neither is anything a caller sent.
MINTED = re.compile(r"[0-9a-f]{32}")

#: Ids a caller may legitimately offer -- a trace id, a W3C traceparent
#: fragment, a name from an upstream proxy -- and every one is adopted as
#: written, which is the whole point of taking it rather than minting.
ADOPTABLE = (
    "0af7651916cd43dd8448eb211c80319c",
    "req-01HQ3K7M2N9P",
    "edge_proxy.42:7f3c9a1b",
    "A" * 64,
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


@pytest.fixture
def answering_client() -> Iterator[TestClient]:
    """A client that answers a crash with its 500 body instead of re-raising."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _stamp(response) -> str:
    """Assert the answer carries an id, and hand the id back."""
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id, dict(response.headers)
    return request_id


# --- the four answers -----------------------------------------------------


def test_a_success_is_answered_with_the_id_the_request_was_stamped_with(client):
    request_id = _stamp(client.get("/health"))

    assert MINTED.fullmatch(request_id), request_id


def test_a_refusal_is_answered_with_the_id_too(client, sessions):
    """:func:`app.main.handle_api_error` builds this one, so it is a real case."""
    response = client.post("/api/screenings")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IMAGE_REQUIRED"
    assert MINTED.fullmatch(_stamp(response))


def test_a_router_miss_is_answered_with_the_id_too(client):
    """Not an envelope, but still an answer, and it still names the request."""
    response = client.get("/api/nowhere")

    assert response.status_code == 404
    assert MINTED.fullmatch(_stamp(response))


def test_a_fault_no_route_caught_is_answered_with_the_id_too(
    answering_client, sessions, monkeypatch
):
    """The one answer built outside the middleware stack, and stamped anyway."""

    def fail_read(_self, _screening_id):
        raise RuntimeError("internal implementation detail")

    monkeypatch.setattr(routes_screenings.ScreeningRepository, "get", fail_read)
    response = answering_client.get(f"/api/screenings/{MISSING}")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert MINTED.fullmatch(_stamp(response))


def test_every_answer_names_the_request_it_belongs_to(client, sessions):
    """Two requests are two ids, so the header is a correlation and not a constant."""
    first = _stamp(client.get("/health"))
    second = _stamp(client.get("/health"))

    assert first != second


# --- the id a caller offers -----------------------------------------------


@pytest.mark.parametrize("offered", ADOPTABLE)
def test_an_id_the_caller_offers_is_the_one_it_is_answered_with(client, offered):
    """:func:`app.api.request_id.resolve_request_id` -- 11.6 and 26.8 want this."""
    response = client.get("/health", headers={REQUEST_ID_HEADER: offered})

    assert _stamp(response) == offered


def test_an_offered_id_reaches_the_state_the_request_carries():
    """The value 11.6 logs and 26.8 stores, read off the scope by a route."""
    probe = FastAPI()
    probe.add_middleware(RequestIdMiddleware)

    @probe.get("/where")
    def where(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    with TestClient(probe) as probe_client:
        adopted = probe_client.get(
            "/where", headers={REQUEST_ID_HEADER: "req-01HQ3K7M2N9P"}
        )
        minted = probe_client.get("/where")

    assert adopted.json()["request_id"] == "req-01HQ3K7M2N9P"
    assert MINTED.fullmatch(minted.json()["request_id"])
    assert minted.json()["request_id"] == _stamp(minted)


# --- an offered id that is refused ----------------------------------------

#: Header values that are offered and must not be reflected back: a caller
#: controls this string, and it reaches a header and 11.6's log line.
UNSAFE = (
    "a" * 65,
    "req with spaces",
    "req\twith\ttabs",
    "req\r\nx-injected: yes",
    "req\nx-injected: yes",
    "req\x00with-nulls",
    "req/with/slashes",
    "req?with=query",
    "re<script>alert(1)</script>",
    "req,with,commas",
    "",
    "   ",
    "é-accented",
)


@pytest.mark.parametrize("offered", UNSAFE)
def test_an_offered_id_that_is_not_id_shaped_is_replaced_not_reflected(
    client, offered
):
    """A refused id is minted fresh, so nothing a caller sent is echoed back."""
    try:
        response = client.get("/health", headers={REQUEST_ID_HEADER: offered})
    except Exception:
        # A client library that refuses to send the value at all has already
        # kept it off the wire; the stamp itself is checked directly below.
        assert resolve_request_id(offered) != offered.strip() or offered.strip() == ""
        return

    request_id = _stamp(response)
    assert MINTED.fullmatch(request_id), request_id
    assert request_id != offered.strip()
    assert "x-injected" not in response.text
    assert response.headers.get("location") is None


@pytest.mark.parametrize("offered", ("a" * 65, "req\r\nx-injected: yes", ""))
def test_the_stamp_refuses_an_id_that_is_not_id_shaped(offered):
    """The same rule at the seam, for the values no client will put on the wire."""
    request_id = resolve_request_id(offered)

    assert MINTED.fullmatch(request_id), request_id
    assert request_id != offered


def test_an_offered_id_is_trimmed_before_it_is_judged():
    """Surrounding whitespace is a header's, not the caller's id."""
    assert resolve_request_id("  req-01HQ3K7M2N9P  ") == "req-01HQ3K7M2N9P"


def test_no_id_offered_is_a_minted_one():
    assert MINTED.fullmatch(resolve_request_id(None))


# --- a browser can read it ------------------------------------------------


def test_cors_exposes_the_id_so_a_browser_can_read_it(client):
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5500"},
    )

    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers["access-control-expose-headers"]
    assert _stamp(response)


def test_cors_allows_the_id_back_on_a_preflight(client):
    """A browser may only offer an id the preflight says it may send."""
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": REQUEST_ID_HEADER,
        },
    )

    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert REQUEST_ID_HEADER.lower() in allowed
    assert _stamp(response)

