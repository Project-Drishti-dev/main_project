"""The id every request is stamped with, and the header it is answered in.

One middleware, one header name and one spelling of what an offered id has
to look like -- so the log line 11.6 writes and the row 26.8 correlates are
the same value the caller was handed.
"""

import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


__all__ = [
    "ACCEPTED_REQUEST_ID",
    "REQUEST_ID_HEADER",
    "REQUEST_ID_STATE_KEY",
    "RequestIdMiddleware",
    "resolve_request_id",
    "stamp_request_id",
]

#: The one name the id travels under, inbound and out.  Spelled once so the
#: middleware, the CORS expose list and the tests cannot drift apart.
REQUEST_ID_HEADER = "X-Request-ID"

#: The scope state key the id is left on, which is where a route, a log
#: record or a stored row reaches the same value the caller was handed.
REQUEST_ID_STATE_KEY = "request_id"

#: What an offered id has to look like to be adopted rather than replaced:
#: the characters a correlation id is spelled with, and a length bound -- so
#: no caller can put a newline, a control character or a megabyte into a
#: header and a log line this service then reflects.  A colon is in the set
#: because traceparent fragments and proxy-chained ids are spelled with one;
#: space, the separators and anything non-ASCII are not, since a log line or
#: a header read on a delimiter is where those are unsafe.
ACCEPTED_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,64}")


def resolve_request_id(offered: str | None) -> str:
    """The id to stamp a request with, given the id its caller offered.

    :param offered: the inbound header's text, or ``None`` when none was
        offered.
    :returns: ``offered`` when it is spelled like an id, else a fresh uuid4
        hex.  An offered id is the caller's to correlate with, so it is kept
        rather than replaced; one that is not id-shaped is refused, because
        whatever it carried would be reflected into a header and into a log.
    """
    if offered is None:
        return uuid.uuid4().hex
    candidate = offered.strip()
    if ACCEPTED_REQUEST_ID.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Stamps every HTTP request with an id and answers with the same one.

    :param app: the ASGI application being wrapped.
    :invariant: every ``http`` request leaves the scope carrying
        ``state["request_id"]`` and is answered with that value in
        :data:`REQUEST_ID_HEADER`.  Scopes that are not ``http`` -- startup,
        shutdown, a websocket -- pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(_offered_id(scope))
        scope.setdefault("state", {})[REQUEST_ID_STATE_KEY] = request_id

        async def send_with_request_id(message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def stamp_request_id(response: Response, request: Request) -> Response:
    """Put the id ``request`` was stamped with onto ``response``.

    :returns: ``response``, stamped.  For the one answer the middleware
        cannot reach: a fault no route caught is answered by Starlette's
        server-error handler, which sits outside the middleware stack, so
        that response never passes back through it.
    """
    response.headers[REQUEST_ID_HEADER] = request.state.request_id
    return response


def _offered_id(scope: Scope) -> str | None:
    """:returns: the inbound id header's text, or ``None`` when not sent."""
    return Headers(scope=scope).get(REQUEST_ID_HEADER)

