"""One spelling of a JSON value, so one value always hashes to one digest.

Keys sorted, no whitespace, nulls written rather than dropped, no floats, and
dates as ISO strings.  Anything else is refused rather than stringified.
"""

import json
from datetime import date, datetime, timezone
from typing import Any, NoReturn

__all__ = ["CanonicalJsonError", "canonical_json"]


class CanonicalJsonError(ValueError):
    """Raised when a value has no canonical spelling.

    A ``ValueError``, so a caller already catching one around 9.3's hash
    keeps catching it.
    """


def _refuse(value: object, path: str) -> NoReturn:
    """Raise the refusal for ``value``, naming ``path`` and its type only."""
    raise CanonicalJsonError(
        f"{path} is a {type(value).__name__}, which canonical JSON cannot "
        f"spell: no value is shown"
    )


def _iso(value: datetime) -> str:
    """``value`` as ISO 8601, an aware one converted to UTC first."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: Any, path: str) -> Any:
    """``value`` in a form :func:`json.dumps` spells identically every time."""
    if value is None or isinstance(value, bool) or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise CanonicalJsonError(
            f"{path} is a float, and a float's shortest spelling is this "
            f"runtime's decision rather than a canonical one"
        )
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return _canonical_object(value, path)
    if isinstance(value, (list, tuple)):
        return [
            _canonical(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    return _refuse(value, path)


def _canonical_object(obj: dict[Any, Any], path: str) -> dict[str, Any]:
    """``obj`` with every key checked and every value canonicalised."""
    canonical: dict[str, Any] = {}
    for key, value in obj.items():
        if not isinstance(key, str):
            raise CanonicalJsonError(
                f"{path} carries a {type(key).__name__} key, and a JSON "
                f"object is keyed by text"
            )
        canonical[key] = _canonical(value, f"{path}.{key}")
    return canonical


def canonical_json(obj: Any) -> str:
    """``obj`` as the one JSON text every spelling of it agrees on.

    :param obj: the value to spell: objects and arrays of them, with text,
        ``bool``, ``int``, ``None``, :class:`~datetime.datetime` and
        :class:`~datetime.date` leaves.  Anything else is refused.
    :returns: the JSON text -- keys sorted by code point, no whitespace, every
        ``None`` written as ``null``, no floats, dates as ISO strings and
        every non-ASCII character escaped.  Equal values spell equally, in
        any process and whatever order their keys arrived in.
    :raises CanonicalJsonError: when a float, a key that is not text, or an
        unsupported type is reached.  Nothing is coerced.
    """
    return json.dumps(
        _canonical(obj, "$"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
