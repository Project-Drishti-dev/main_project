"""The one way this service logs: one JSON object per line.

A record carries its structured fields beside it under a single ``fields``
key rather than as ``extra`` attributes of its own, and the formatter
merges them into one flat object.  Two consequences, both wanted here:

- **Nothing is interpolated into the message.**  The message *is* the event
  name -- ``http_request``, ``unhandled_request_error`` -- so a payload
  cannot reach a log by being formatted into a string.  11.7's "no log line
  ever contains image bytes, OCR text or identity data" is far easier to
  hold when there is no free-text slot to hold it in.
- **The request id is ambient rather than passed.**  A handler, a route and
  the middleware that times the request all log without being handed the
  id: :func:`bind_request_id` puts it where the formatter finds it, so a
  line cannot disagree with the id the answer carried.

The formatter never raises.  A field whose value is not JSON-serialisable
is stringified rather than allowed to raise out of a logging call, because
a handler that throws turns one bad field into a failed request.
"""

import contextlib
import json
import logging
import sys
from collections.abc import Iterator
from contextvars import ContextVar
from datetime import datetime, timezone

from app.config import get_log_level

__all__ = [
    "ALWAYS_PRESENT_FIELDS",
    "APP_LOGGER_NAME",
    "FIELDS_KEY",
    "JsonFormatter",
    "bind_request_id",
    "configure_logging",
    "current_request_id",
    "log_event",
]


#: The logger this service logs under.  Every module's
#: ``logging.getLogger(__name__)`` resolves beneath it, so one handler
#: reaches all of them and a third-party logger configured by its own
#: package does not.
APP_LOGGER_NAME = "app"

#: Where a record's structured fields are carried.  A single key rather
#: than a spread of ``extra`` attributes: :meth:`logging.Logger.makeRecord`
#: refuses an ``extra`` key that shadows a :class:`~logging.LogRecord`
#: attribute, so the spread form collides with ``message``, ``args``,
#: ``exc_info`` and friends as soon as a field is named after one.
FIELDS_KEY = "fields"

#: The keys :class:`logging.LogRecord` puts on every record, read off a
#: throwaway one rather than spelled out -- so a future Python that adds one
#: is excluded from ``fields`` automatically.  The three formatting-time
#: additions are listed because no record carries them until a formatter
#: puts them there.
_RECORD_ATTRIBUTES = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None))
) | {"message", "asctime", "taskName"}

#: The id of the request being served, for whatever is running inside it.
#: A :class:`~contextvars.ContextVar` rather than a thread-local because a
#: route in a threadpool is a different thread and the same logical request:
#: :func:`starlette.concurrency.run_in_threadpool` copies the context, so
#: a ``logger.exception`` raised inside one carries the id without the
#: route having been handed it.
_request_id: ContextVar[str | None] = ContextVar(
    "drishti_request_id", default=None
)


def current_request_id() -> str | None:
    """:returns: the id of the request being served, or ``None`` outside one."""
    return _request_id.get()


@contextlib.contextmanager
def bind_request_id(request_id: str | None) -> Iterator[None]:
    """Make ``request_id`` the one every line logged inside the block carries.

    :param request_id: the id already stamped on the request, or ``None``
        when nothing stamped one.  ``None`` is honoured rather than
        replaced with a minted value: the id belongs to
        :mod:`app.api.request_id`, and a second spelling of it is exactly
        what this module must not add.
    :invariant: on exit the previous binding is restored, so a nested or
        concurrent request cannot see its neighbour's id.
    """
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)


def log_event(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    exc_info: object = None,
    **fields: object,
) -> None:
    """Log one event by name, with its fields beside it.

    :param message: the event name, snake_case and stable.  Not prose: it is
        the machine-readable half of the line, and the reason a caller
        cannot put a payload into the message.
    :param exc_info: the traceback to attach, as
        :func:`logging.Logger.exception` takes it -- ``True`` for the
        exception being handled, or an exception instance.
    :param fields: the record's other values, merged into the same flat
        object.  Named arguments only, so a field is always spelled and can
        never be assembled from a caller's keys.
    """
    logger.log(level, message, exc_info=exc_info, extra={FIELDS_KEY: fields})


class JsonFormatter(logging.Formatter):
    """Render one record as one JSON object on one line.

    The object is always the five keys
    :data:`ALWAYS_PRESENT_FIELDS` plus whatever the record was given, and
    an exception traceback -- never a formatted, indented, multi-line one --
    so a line stays a line and stays parseable.
    """

    def format(self, record: logging.LogRecord) -> str:
        line = {
            "timestamp": _utc_stamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": current_request_id(),
        }
        line.update(self._fields(record))
        if record.exc_info:
            # Newlines escaped by json.dumps, so a traceback cannot break
            # the one-object-per-line property the whole format rests on.
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)

    def _fields(self, record: logging.LogRecord) -> dict[str, object]:
        """:returns: the record's own fields, minus anything not one of them."""
        fields = getattr(record, FIELDS_KEY, None)
        if not isinstance(fields, dict):
            return {}
        return {
            name: value
            for name, value in fields.items()
            if name not in _RECORD_ATTRIBUTES
        }


#: The keys every line carries whatever the record was given, so a reader
#: can index them without a guard on each.
ALWAYS_PRESENT_FIELDS = ("timestamp", "level", "logger", "message", "request_id")


def configure_logging(stream=None) -> logging.Logger:
    """Attach the one JSON handler to the ``app`` logger.

    Idempotent: a second call re-reads the level and adds no second
    handler, so importing :mod:`app.main` from several places cannot make
    every line appear twice.

    :param stream: where the lines go, defaulting to stdout.  A test passes
        its own.
    :returns: the ``app`` logger it configured.
    :invariant: every record logged beneath :data:`APP_LOGGER_NAME` is
        rendered exactly once, by :class:`JsonFormatter`.  Propagation to
        the root logger is turned off for that reason -- otherwise uvicorn's
        own root handler would render the same record a second time, in
        whatever format it was configured with.
    """
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(get_log_level())
    logger.propagate = False
    if not any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout if stream is None else stream)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


def _utc_stamp(created: float) -> str:
    """:returns: ``created`` (a :meth:`time.time` epoch) as a UTC ISO 8601."""
    return datetime.fromtimestamp(created, timezone.utc).isoformat()