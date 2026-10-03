"""The per-blob data key: generated fresh, wrapped under the master key.

Envelope encryption, in the one shape this project needs.  A blob is
encrypted under a data key of its own, and that key is encrypted under the
master key (19.2), so a blob is readable only by a holder of the master key
and one blob's key is worthless for any other blob.

**A data key is drawn per blob and held nowhere**, on
:mod:`app.ledger.salts`' reasoning that a reused secret is not one.  It is
never derived from the master key either: a derived key would leave every
blob recoverable from the master key alone, which is the property the wrap
exists to prevent.

**A nonce is drawn per wrap rather than counted.**  AES-GCM leaks its
authentication key outright when one nonce is reused under one key, so
:func:`wrap_data_key` draws :data:`DATA_KEY_NONCE_BYTES` from the CSPRNG and
:class:`WrappedDataKey` refuses a nonce of any other width.

**A wrapped key that does not open is refused, never returned.**  A wrong
master key and an altered wrapped value are one answer from AES-GCM and one
answer here, so the message names both readings and quotes neither key.

**A wrap may be bound to something.**  :func:`wrap_data_key` and
:func:`unwrap_data_key` take what the wrap is bound to as AES-GCM's
associated data, and :mod:`app.storage.blob_store` passes the address a
blob was written under (19.3), so a wrapped key moved under another blob's
name does not open.

**Nothing here reads the environment.**  :func:`app.storage.master_key.load_master_key` answers
the master key (D154) and this module is handed one.
"""

import secrets
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.storage.master_key import MasterKey

__all__ = [
    "DATA_KEY_BYTES",
    "DATA_KEY_NONCE_BYTES",
    "DATA_KEY_TAG_BYTES",
    "DataKeyError",
    "WrappedDataKey",
    "generate_data_key",
    "unwrap_data_key",
    "wrap_data_key",
]


#: How many bytes one data key carries: 32, or AES-256, the same width as
#: :data:`~app.storage.master_key.MASTER_KEY_BYTES`.  Pinned rather than a
#: parameter, on that module's reasoning.
DATA_KEY_BYTES = 32

#: How many bytes the nonce under one wrap carries: 12, the width AES-GCM is
#: specified at.
DATA_KEY_NONCE_BYTES = 12

#: How many bytes the tag AES-GCM appends to the wrapped key carries: 16.
DATA_KEY_TAG_BYTES = 16


#: What a wrapped key that did not open is told.  It names both readings,
#: because AES-GCM cannot tell them apart, and it quotes no key material.
_NOT_OPENED = (
    "the wrapped data key did not open: the master key is not the one it was "
    "wrapped under, or the wrapped value was altered. Nothing is returned "
    "rather than returned wrongly, and no key material is shown."
)


class DataKeyError(ValueError):
    """Raised when a data key cannot be wrapped or cannot be opened.

    A ``ValueError``, on :class:`~app.storage.master_key.MasterKeyError`'s
    reasoning: what is unusable is the key, and it is refused where it is
    used rather than at the first blob.
    """


@dataclass(frozen=True, repr=False, slots=True)
class WrappedDataKey:
    """One data key under the master key, and the nonce that wrapped it.

    :param nonce: :data:`DATA_KEY_NONCE_BYTES` raw bytes, drawn per wrap.
    :param ciphertext: the data key and its :data:`DATA_KEY_TAG_BYTES` tag,
        concatenated -- what :func:`wrap_data_key` wrote and
        :func:`unwrap_data_key` reads.  ``repr=False`` keeps both out of a
        traceback.
    """

    nonce: bytes
    ciphertext: bytes

    def __post_init__(self) -> None:
        """Freeze both fields at the one width each of them may be.

        :returns: nothing.
        :raises TypeError: naming the type of a field that is not bytes.
        :raises ValueError: naming the width a field is not.
        """
        nonce = _as_bytes(self.nonce, "a wrapped key's nonce")
        ciphertext = _as_bytes(self.ciphertext, "a wrapped key's ciphertext")
        if len(nonce) != DATA_KEY_NONCE_BYTES:
            raise ValueError(
                f"a wrapped key carries a {DATA_KEY_NONCE_BYTES} byte nonce, "
                f"and this one carries {len(nonce)}"
            )
        expected = DATA_KEY_BYTES + DATA_KEY_TAG_BYTES
        if len(ciphertext) != expected:
            raise ValueError(
                f"a wrapped key carries {DATA_KEY_BYTES} bytes of key and "
                f"{DATA_KEY_TAG_BYTES} of tag, {expected} in all, and this "
                f"one carries {len(ciphertext)}"
            )
        object.__setattr__(self, "nonce", nonce)
        object.__setattr__(self, "ciphertext", ciphertext)


def generate_data_key() -> bytes:
    """:data:`DATA_KEY_BYTES` random bytes, from the OS CSPRNG.

    :returns: a fresh key.  Never the same one twice, and never derived from
        the master key, a seed, a clock or a counter.
    """
    return secrets.token_bytes(DATA_KEY_BYTES)


def wrap_data_key(
    master_key: MasterKey,
    data_key: bytes,
    associated_data: bytes | None = None,
) -> WrappedDataKey:
    """``data_key`` encrypted under ``master_key`` with AES-GCM.

    :param master_key: what :func:`app.storage.master_key.load_master_key`
        answered; its own ``__post_init__`` has refused a wrong width.
    :param data_key: :data:`DATA_KEY_BYTES` raw bytes, as
        :func:`generate_data_key` answers them.
    :param associated_data: what the wrap is bound to, or ``None`` to bind
        it to nothing.  19.3's store passes the address a blob was written
        under, so a wrapped key moved under another blob does not open.
    :returns: the wrapped form, under a nonce drawn here.
    :raises TypeError: naming the type of either argument and no value.
    :raises ValueError: when ``data_key`` is not :data:`DATA_KEY_BYTES` wide.
    """
    _checked_master_key(master_key)
    raw = _checked_data_key(data_key)
    nonce = secrets.token_bytes(DATA_KEY_NONCE_BYTES)
    return WrappedDataKey(
        nonce=nonce,
        ciphertext=AESGCM(master_key.key).encrypt(nonce, raw, associated_data),
    )


def unwrap_data_key(
    master_key: MasterKey,
    wrapped: WrappedDataKey,
    associated_data: bytes | None = None,
) -> bytes:
    """The data key ``wrapped`` carries, opened under ``master_key``.

    :param master_key: the key the wrapped form was written under.  A
        different one is refused rather than tried.
    :param wrapped: what :func:`wrap_data_key` answered.
    :param associated_data: the same value :func:`wrap_data_key` was handed,
        or ``None`` when the wrap was bound to nothing.
    :returns: :data:`DATA_KEY_BYTES` raw bytes.
    :raises DataKeyError: when the wrapped form does not open -- a wrong
        master key and an altered wrapped value are one answer from AES-GCM.
    :raises TypeError: naming the type of either argument and no value.
    """
    _checked_master_key(master_key)
    if not isinstance(wrapped, WrappedDataKey):
        raise TypeError(
            f"a wrapped data key is a {type(wrapped).__name__}, and only a "
            f"WrappedDataKey may be opened: no value is shown"
        )
    try:
        opened = AESGCM(master_key.key).decrypt(
            wrapped.nonce, wrapped.ciphertext, associated_data
        )
    except InvalidTag:
        raise DataKeyError(_NOT_OPENED) from None
    return opened


def _checked_master_key(master_key: Any) -> None:
    """:attr:`MasterKey.key` is present, or the argument is refused by type.

    :returns: nothing.
    :raises TypeError: naming the type and no value.
    """
    if not isinstance(master_key, MasterKey):
        raise TypeError(
            f"a master key is a {type(master_key).__name__}, and only a "
            f"MasterKey may wrap or open a data key: no value is shown"
        )


def _checked_data_key(data_key: Any) -> bytes:
    """:data:`DATA_KEY_BYTES` raw bytes, or refused.

    :returns: the key copied to ``bytes``, so a buffer the caller still
        holds cannot change what is wrapped.
    :raises TypeError: naming the type and no value.
    :raises ValueError: naming the width and no value.
    """
    raw = _as_bytes(data_key, "a data key")
    if len(raw) != DATA_KEY_BYTES:
        raise ValueError(
            f"a data key carries {DATA_KEY_BYTES} bytes, and this one "
            f"carries {len(raw)}"
        )
    return raw


def _as_bytes(value: Any, subject: str) -> bytes:
    """``value`` copied to frozen bytes, or refused by type.

    :returns: the copy.
    :raises TypeError: naming the type and never the value, since every
        field this serves carries key material.
    """
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(
            f"{subject} is a {type(value).__name__}, and only bytes may be "
            f"stored in a wrapped key: no value is shown"
        )
    return bytes(value)
