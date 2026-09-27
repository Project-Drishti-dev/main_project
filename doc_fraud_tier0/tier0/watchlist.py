"""
Stage D — check the document number against a watchlist of documents
already known to be stolen, lost, or previously flagged as fraudulent.

For Tier 0's "must run under 0.3 seconds" budget, this has to be an O(1)
lookup, not a linear scan or a network round trip. We load the watchlist
into an in-memory dict once and cache it (keyed by file path + mtime) so
repeated calls to run_tier0() in the same process don't re-read the file
from disk every time.

Expected watchlist.json shape:
{
  "entries": [
    {"document_number": "L898902C3", "issuing_country": "UTO", "reason": "Reported stolen"},
    {"document_number": "AB1234567", "reason": "Previously flagged as fraudulent"}
  ]
}
`issuing_country` is optional — omit it to flag a document number across
all issuing countries (useful for globally-unique number spaces), or
include it to scope the match and avoid collisions between countries that
reuse number formats.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from .models import CheckOutcome

_cache: dict[str, tuple[float, dict]] = {}


@dataclass
class WatchlistHit:
    document_number: str
    issuing_country: Optional[str]
    reason: str


def _normalize(document_number: str) -> str:
    # MRZ document numbers pad with '<'; normalize so lookups match
    # regardless of whether the caller passes the padded or unpadded form.
    return document_number.strip().rstrip("<").upper()


def _load_index(watchlist_path: str) -> dict:
    """
    Build (or fetch from cache) an index of the watchlist:
      { document_number: [ {issuing_country, reason}, ... ] }
    Cache is invalidated automatically if the file's mtime changes.
    """
    mtime = os.path.getmtime(watchlist_path)
    cached = _cache.get(watchlist_path)
    if cached and cached[0] == mtime:
        return cached[1]

    with open(watchlist_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    index: dict[str, list[dict]] = {}
    for entry in raw.get("entries", []):
        doc_num = _normalize(entry["document_number"])
        index.setdefault(doc_num, []).append(
            {
                "issuing_country": entry.get("issuing_country"),
                "reason": entry.get("reason", "Flagged on watchlist"),
            }
        )

    _cache[watchlist_path] = (mtime, index)
    return index


def lookup(
    document_number: str, watchlist_path: str, issuing_country: Optional[str] = None
) -> Optional[WatchlistHit]:
    """
    Return a WatchlistHit if this document number is flagged, else None.
    If the watchlist entry specifies an issuing_country, it must match the
    document's issuing_country to count as a hit (avoids false positives
    from number-format collisions across countries).
    """
    index = _load_index(watchlist_path)
    candidates = index.get(_normalize(document_number))
    if not candidates:
        return None

    for entry in candidates:
        entry_country = entry["issuing_country"]
        if entry_country is None or entry_country == issuing_country:
            return WatchlistHit(
                document_number=document_number,
                issuing_country=entry_country,
                reason=entry["reason"],
            )
    return None


def check_watchlist(
    document_number: str, watchlist_path: str, issuing_country: Optional[str] = None
) -> CheckOutcome:
    """Wrap lookup() as a CheckOutcome for uniform pipeline handling."""
    if not watchlist_path or not os.path.exists(watchlist_path):
        return CheckOutcome(
            check_name="watchlist",
            passed=True,
            detail=f"Watchlist file not found at '{watchlist_path}'; check skipped",
        )

    hit = lookup(document_number, watchlist_path, issuing_country)
    if hit is None:
        return CheckOutcome(
            check_name="watchlist", passed=True, detail="No watchlist match"
        )
    return CheckOutcome(
        check_name="watchlist",
        passed=False,
        detail=f"Document number matches watchlist entry: {hit.reason}",
    )
