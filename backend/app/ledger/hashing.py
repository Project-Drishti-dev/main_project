"""The digest a stored record is checked against.

One record, one spelling, one salt: SHA-256 over ``salt || canonical_json``.
"""

import hashlib
from typing import Any

from app.ledger.canonical import canonical_json

__all__ = ["hash_record"]


def hash_record(obj: Any, salt: bytes) -> str:
    """SHA-256 over ``salt || canonical_json(obj)``, as 64 lowercase hex.

    ``obj`` is spelled only by ``canonical_json``, so the digest depends on
    the value rather than on how the caller built it; ``salt`` is the
    per-record bytes 9.4 stores and 9.17 reads back.  A non-bytes salt raises
    ``TypeError`` naming the type alone, and a record with no canonical
    spelling raises ``CanonicalJsonError`` -- neither returns a digest.
    """
    if not isinstance(salt, (bytes, bytearray)):
        raise TypeError(
            f"salt is a {type(salt).__name__}, and only bytes may be hashed "
            f"in front of a record: no value is shown"
        )
    digest = hashlib.sha256()
    digest.update(salt)
    # ensure_ascii made this pure ASCII, so the encode cannot fail (D48).
    digest.update(canonical_json(obj).encode("ascii"))
    return digest.hexdigest()
