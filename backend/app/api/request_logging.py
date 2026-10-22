"""One log line per HTTP request: which handler, how it ended, how long.

The request id is read off the scope :mod:`app.api.request_id` already
filled, never the inbound header, and never re-minted -- this middleware
logs an id, it does not stamp one.

**The line names the handler, not the path.**  A path is caller-controlled
text: 11.5 refused to reflect an offered request id for exactly that
reason, and a URL would reintroduce it through the back door -- Starlette
matches ``/api/screenings/<anything>`` before FastAPI's ``uuid.UUID``
annotation ever refuses it.  A handler's dotted name is chosen by this
repository, so nothing a caller typed reaches the log.
"""

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.request_id import REQUEST_ID_STATE_KEY
from app.logging_config import bind_request_id, log_event

__all__ = ["REQUEST_LOG_EVENT", "RequestLoggingMiddleware"]


#: The message of the per-request line, and the name every reader groups by.
REQUEST_LOG_EVENT = "http_request"

#: ``ServerErrorMiddleware``'s answer, used when no ``http.response.start``
#: was seen -- a fault no route caught, or a client that hung up before the
#: response started.  A request that never started a response is reported
#: as one that failed.
_UNSTARTED_STATUS = 500

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Times every HTTP request and logs one line about it when it ends.

    :param app: the ASGI application being wrapped.
    :invariant: exactly one ``http_request`` line is logged for every ``http``
        request, whatever the outcome -- the line is written in a ``finally``,
        so a fault a route did not catch still has one.  Scopes that are not
        ``http`` pass through unlogged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = _UNSTARTED_STATUS
        state = scope.setdefault("state", {})

        async def send_recording_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        # Bound for the whole request, so a line a route or a handler logs
        # part-way through carries the same id as the line logged here.
        with bind_request_id(state.get(REQUEST_ID_STATE_KEY)):
            try:
                await self.app(scope, receive, send_recording_status)
            finally:
                log_event(
                    logger,
                    REQUEST_LOG_EVENT,
                    method=scope.get("method"),
                    handler=_handler_name(scope),
                    status=status,
                    elapsed_ms=_elapsed_ms(started),
                )


def _elapsed_ms(started: float) -> float:
    """:returns: milliseconds since :func:`time.perf_counter`, to 3 places."""
    return round((time.perf_counter() - started) * 1000, 3)


def _handler_name(scope: Scope) -> str | None:
    """The dotted name of the endpoint that answered, or ``None``.

    Starlette sets ``scope["endpoint"]`` only once a route has matched, and
    never sets a template for the path -- a probe confirms a matched scope
    carries ``endpoint`` and ``path_params`` and nothing else naming the
    route.  So the handler is what identifies the endpoint without echoing
    what the caller typed, and ``None`` says the request matched nothing.
    """
    endpoint = scope.get("endpoint")
    module = getattr(endpoint, "__module__", None)
    name = getattr(endpoint, "__qualname__", None)
    if module is None or name is None:
        return None
    return f"{module}.{name}"