"""11.10: ``GET /api/version`` answers the four versions and spends no budget.

Every constant in :mod:`app.version` carries the same string today, so the
four are replaced by sentinels no other value carries and each key is asserted
against its own.  A route that bound a constant at import, swapped two of them
or answered a literal passes a test that only compares against the constants
it was handed.

Around that wiring sit the two claims the answer makes: that the ruleset it
names is the one a screening is scored under, and that reading the versions
costs nothing once the analysis budget is gone (``D78``).
"""

import pytest
from fastapi.testclient import TestClient

from app import version
from app.api.rate_limit import RateLimiter
from app.audit.emit import MODEL_VERSIONS_KEY, RULESET_VERSION_KEY
from app.main import app
from app.risk.weightsets.loader import load_weightset


client = TestClient(app)

#: The key each value is answered under, the constant that carries it, and a
#: sentinel no other value carries.
ANSWERED = {
    "app_version": ("APP_VERSION", "9.9.9-app"),
    "ruleset_version": ("RULESET_VERSION", "9.9.9-ruleset"),
    "model_versions": ("MODEL_VERSIONS", {"tier1_ocr": "9.9.9-model"}),
    "prompt_version": ("PROMPT_VERSION", "9.9.9-prompt"),
}


@pytest.mark.parametrize("key", sorted(ANSWERED))
def test_each_version_is_answered_under_its_own_constant(monkeypatch, key):
    """One case per key, each carrying the sentinel its own constant was given.

    :param key: the key the answer is read out of.
    """
    for _, (constant, sentinel) in ANSWERED.items():
        monkeypatch.setattr(version, constant, sentinel)

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json()[key] == ANSWERED[key][1]


def test_the_answer_holds_exactly_the_four_keys_the_trail_spells():
    """Four keys and no others, two of them spelled as the trail spells them."""
    body = client.get("/api/version").json()

    assert set(body) == set(ANSWERED)
    assert {RULESET_VERSION_KEY, MODEL_VERSIONS_KEY} <= set(body)


def test_the_ruleset_answered_is_the_one_a_screening_is_scored_under():
    """The ruleset named here is the weightset file this build ships."""
    body = client.get("/api/version").json()

    assert body["ruleset_version"] == load_weightset().ruleset_version


def test_reading_the_versions_spends_no_analysis_budget():
    """The read stays answerable once the analysis budget is spent.

    ``conftest`` hands the shipped limiter back after every test, so the small
    one put in place here outlives neither this test nor its neighbours.
    """
    app.state.rate_limiter = RateLimiter(1)

    assert client.post("/api/analyze").status_code == 422
    assert client.post("/api/analyze").status_code == 429
    assert client.get("/api/version").status_code == 200
    assert client.get("/api/version").status_code == 200