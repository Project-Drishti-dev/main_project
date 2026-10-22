"""One budget per address, spent by the two endpoints that analyse an image.

The key is the peer address the server reports and never a header the caller
sent -- ``X-Forwarded-For`` is the caller's own text, so a bucket keyed on it
is one the caller resets by inventing an address (``D78``).

**In memory, in one process.**  The counts are lost when the service
restarts and are not shared with the other instances a deployment runs, so
the limit a caller meets is per instance rather than per service.
"""

import time
from collections.abc import Callable

from fastapi import Request

from app.errors import APIError

__all__ = [
    "MAX_TRACKED_CLIENTS",
    "RATE_LIMIT_CODE",
    "RATE_LIMIT_MESSAGE",
    "UNKNOWN_CLIENT",
    "WINDOW_SECONDS",
    "RateLimiter",
    "client_key",
    "enforce_analysis_rate_limit",
]


#: The width of the window a count is kept for, in seconds -- one minute,
#: which is the unit :func:`app.config.get_rate_limit_per_minute` is named
#: for.  A fixed window rather than a sliding one: the count is a bucket that
#: empties, not a list of instants to expire one at a time.
WINDOW_SECONDS = 60.0

#: The most addresses counted in one window.  A caller picks its own source
#: address, so an unbounded map is a way to spend this process's memory; past
#: the ceiling the window's counts are dropped and every budget starts over,
#: which bounds the memory and costs every caller one window.
MAX_TRACKED_CLIENTS = 10_000

#: The code and the message a spent budget is refused with, spelled once so
#: the guard, the contract and the tests cannot drift apart.  The message
#: names no address: 11.5 and ``D77`` keep a caller's own text out of what
#: this service hands back as well as out of what it writes down.
RATE_LIMIT_CODE = "RATE_LIMITED"
RATE_LIMIT_MESSAGE = "Too many analyses. Wait a minute and try again."

#: The key a request is counted under when the transport reported no peer,
#: so such a request shares one budget with every other that reported none.
UNKNOWN_CLIENT = "unknown"


class RateLimiter:
    """Counts the requests made by each key within a fixed window.

    :param limit: how many requests one key may make in a window.
    :param window_seconds: the width of the window.
    :param clock: the source of the time the window is measured against.
    :param max_tracked: the most keys counted at once.
    :invariant: :meth:`count` is reached from one thread at a time --
        :func:`enforce_analysis_rate_limit` is ``async``, so the count is
        taken on the event loop -- and this holds no lock.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        max_tracked: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_tracked = max_tracked
        self._clock = clock
        self._window = 0
        self._counts: dict[str, int] = {}

    def count(self, key: str) -> int:
        """Record one request from ``key`` and report the running total.

        :param key: who the request is from, as :func:`client_key` spells it.
        :returns: how many requests ``key`` has made in the window this one
            falls in, one or more.  A budget of :attr:`limit` is therefore
            spent when the count passes it, not when it reaches it.
        """
        window = int(self._clock() // self.window_seconds)
        if window != self._window:
            # Everything counted for the window before is dropped rather
            # than aged out, so nothing is held longer than one window.  The
            # price is the fixed window's own: a caller spending the budget
            # either side of a roll gets two of it.
            self._window = window
            self._counts = {}
        if len(self._counts) >= self.max_tracked and key not in self._counts:
            self._counts = {}
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]


def client_key(request: Request) -> str:
    """The address this service saw the caller at, as the counter's key.

    :param request: the request being served.
    :returns: the peer address, or :data:`UNKNOWN_CLIENT` when the transport
        reported none.  Never a header: a forwarded-for address is the
        caller's own text, and a bucket keyed on it is one the caller can
        reset whenever it likes.
    """
    peer = request.client
    if peer is None or not peer.host:
        return UNKNOWN_CLIENT
    return peer.host


async def enforce_analysis_rate_limit(request: Request) -> None:
    """Refuse the request when the caller's address has spent its budget.

    :param request: the request being served.
    :returns: ``None``, and the request goes on to the route.
    :raises APIError: 429 in the envelope :mod:`app.main` builds (``D74``),
        for every request past the limit -- whatever the request itself was,
        and before the route reads a byte of it.
    """
    limiter: RateLimiter = request.app.state.rate_limiter
    if limiter.count(client_key(request)) > limiter.limit:
        raise APIError(429, RATE_LIMIT_CODE, RATE_LIMIT_MESSAGE)
