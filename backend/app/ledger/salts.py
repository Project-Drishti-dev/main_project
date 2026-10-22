"""The per-record salt: generated fresh, stored beside the record, never shared.

A salt that is reused is not a salt, so this module holds no salt to reuse:
the only way to obtain one is to generate it, and it travels with the record
it belongs to rather than sitting in a module global.
"""

import secrets
from dataclasses import dataclass
from typing import Any

from app.ledger.hashing import hash_record

__all__ = ["SALT_BYTES", "SaltedRecord", "generate_salt", "seal_record"]

#: How many random bytes one record's salt carries: 16 bytes, or 128 bits.
#: A constant rather than a parameter, because a width a caller can ask for
#: is a width a caller can ask for too small.
SALT_BYTES = 16


def generate_salt() -> bytes:
    """:data:`SALT_BYTES` random bytes, from the OS CSPRNG.

    :returns: a fresh salt.  Never the same one twice, and never derived from
        a seed, a clock or a counter -- all three are guessable from the row
        they are salting.
    """
    return secrets.token_bytes(SALT_BYTES)


@dataclass(frozen=True)
class SaltedRecord:
    """A record and the salt its digest was taken with, stored together.

    :param record: the value handed to :func:`~app.ledger.hashing.
        hash_record`, left exactly as the caller spelled it.
    :param salt: the per-record salt, as bytes.  A ``bytearray`` is copied to
        ``bytes`` on the way in, so a buffer the caller still holds cannot
        change the digest after the pair is made.
    """

    record: Any
    salt: bytes

    def __post_init__(self) -> None:
        """Refuse a salt that is not bytes, and freeze the rest.

        :returns: nothing.
        :raises TypeError: when :attr:`salt` is neither ``bytes`` nor a
            ``bytearray``, naming the type and never the value, so a salt
            carrying anything of the record reaches no log.
        """
        if not isinstance(self.salt, (bytes, bytearray)):
            raise TypeError(
                f"a stored salt is a {type(self.salt).__name__}, and only "
                f"bytes may be stored beside a record: no value is shown"
            )
        object.__setattr__(self, "salt", bytes(self.salt))

    @property
    def digest(self) -> str:
        """The record's digest, as 64 lowercase hex (``D49``)."""
        return hash_record(self.record, self.salt)

    @property
    def salt_hex(self) -> str:
        """The salt as 32 lowercase hex -- the spelling a text column takes."""
        return self.salt.hex()


def seal_record(record: Any) -> SaltedRecord:
    """``record`` paired with a salt of its own, generated here.

    :param record: the value to seal; stored as handed over, unhashed and
        unaltered, so what is persisted is what the digest was taken over.
    :returns: the pair, ready to hash or to write beside its record.
    """
    return SaltedRecord(record=record, salt=generate_salt())
