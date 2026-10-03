"""11.8: the counter's arithmetic, and the reader that sets what it counts.

Two halves answering two questions.  :class:`RateLimiter` is asked whether
its count puts the refusal on the N+1th request and on no other; the reader
in :mod:`app.config` is asked whether the limit is the operator's to set, and
what a value that is not a count of requests does before any limiter sees it.
"""

from types import SimpleNamespace

import pytest

from app.api.rate_limit import (
    MAX_TRACKED_CLIENTS,
    UNKNOWN_CLIENT,
    WINDOW_SECONDS,
    RateLimiter,
    client_key,
)
from app.config import (
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_ENV_VAR,
    get_rate_limit_per_minute,
)


class Clock:
    """A clock a test moves by hand, so a window rolls without a wait."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _peer(host: str | None) -> SimpleNamespace:
    """The part of a request :func:`client_key` reads, and nothing else."""
    return SimpleNamespace(
        client=None if host is None else SimpleNamespace(host=host)
    )


# --- the counter -----------------------------------------------------------


def test_the_count_is_one_more_with_every_request_from_one_key():
    limiter = RateLimiter(3, clock=Clock())

    assert [limiter.count("198.51.100.7") for _ in range(5)] == [1, 2, 3, 4, 5]


def test_another_key_counts_from_one_again():
    """Per address, so exhausting one leaves the other untouched."""
    limiter = RateLimiter(3, clock=Clock())
    limiter.count("198.51.100.7")
    limiter.count("198.51.100.7")

    assert limiter.count("198.51.100.8") == 1


def test_the_count_survives_the_window_and_starts_again_at_the_roll():
    clock = Clock()
    limiter = RateLimiter(3, clock=clock)
    limiter.count("198.51.100.7")

    clock.advance(WINDOW_SECONDS - 1)
    assert limiter.count("198.51.100.7") == 2

    clock.advance(1)
    assert limiter.count("198.51.100.7") == 1


def test_the_map_does_not_grow_past_what_the_limiter_was_given():
    """A caller picks its own source address, so the map needs a ceiling.

    Past the ceiling the window empties: memory is bounded, and the cost is
    that every caller -- including the ones that were counting -- starts the
    next request from one again.
    """
    limiter = RateLimiter(3, clock=Clock(), max_tracked=2)
    limiter.count("198.51.100.7")
    limiter.count("198.51.100.8")

    assert limiter.count("198.51.100.9") == 1
    assert limiter.count("198.51.100.8") == 1


def test_the_ceiling_a_limiter_is_built_with_is_the_one_that_was_named():
    assert RateLimiter(3).max_tracked == MAX_TRACKED_CLIENTS


# --- the key ---------------------------------------------------------------


def test_the_key_is_the_address_the_server_reported():
    assert client_key(_peer("198.51.100.7")) == "198.51.100.7"


@pytest.mark.parametrize(
    "peer",
    [_peer(None), _peer("")],
    ids=["no peer reported", "no host in the peer"],
)
def test_a_transport_that_reports_no_address_shares_one_key(peer):
    assert client_key(peer) == UNKNOWN_CLIENT


# --- the limit the operator sets -------------------------------------------


def test_the_limit_is_the_default_when_the_variable_is_unset(monkeypatch):
    monkeypatch.delenv(RATE_LIMIT_ENV_VAR, raising=False)

    assert get_rate_limit_per_minute() == DEFAULT_RATE_LIMIT_PER_MINUTE


def test_a_blank_variable_is_the_default(monkeypatch):
    monkeypatch.setenv(RATE_LIMIT_ENV_VAR, "   ")

    assert get_rate_limit_per_minute() == DEFAULT_RATE_LIMIT_PER_MINUTE


@pytest.mark.parametrize("configured", ["1", " 5 ", "60", "600"])
def test_the_limit_is_the_count_the_variable_says(monkeypatch, configured):
    monkeypatch.setenv(RATE_LIMIT_ENV_VAR, configured)

    assert get_rate_limit_per_minute() == int(configured)


@pytest.mark.parametrize(
    "configured",
    ["ten", "3.5", "5/min", "0", "-1"],
    ids=["a word", "a decimal", "a rate with a unit", "zero", "negative"],
)
def test_a_value_that_is_not_a_count_of_requests_is_refused(
    monkeypatch, configured
):
    """Refused while the configuration is read, not as a silent no-op.

    ``0`` is the one that matters: read as "no limit" it would turn a typo
    into an endpoint with none, and read as a limit it would answer every
    request with a refusal.  Neither is what the operator wrote.
    """
    monkeypatch.setenv(RATE_LIMIT_ENV_VAR, configured)

    with pytest.raises(ValueError, match=RATE_LIMIT_ENV_VAR):
        get_rate_limit_per_minute()
