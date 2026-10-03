"""The evidence store master key: loaded from the environment, never a constant.

``EVIDENCE_ENCRYPTION_KEY`` holds the AES-256 key every evidence blob is
wrapped under (19.1). :func:`app.config.get_evidence_encryption_key` is the
only reader of that variable and :func:`app.config.get_app_env` the only
reader of the mode; this module reads no environment of its own and is handed
what those two answered.

**A missing key is generated in development and refused in production**, and
those are the only two answers. The zero-setup demo starts with nothing
configured and needs a key to run at all, while a deployment that has lost
its key must stop rather than write evidence under something every
deployment missing one shares. There is no third answer, and in particular
**no constant**: a key this repository could name is a key nobody has to
steal.

**A generated key is generated per call and held nowhere**, on
:mod:`app.ledger.salts`'s reasoning that a reused secret is not one. Two
callers handed ``None`` in the same process hold two different keys, so a
blob written under one cannot be read back with the other; persisting the
key is the operator job, and in development losing it loses the blobs.

**An unreadable mode is not read as development.** The mode is folded and
matched against the two names :mod:`app.config` publishes, and anything else
is refused -- because this is the one variable that decides whether a
fallback is allowed at all, and a typo in it must not be what turns the
fallback on.

**A refusal quotes nothing.** The configured value is the master key itself,
so every message here names the variable or the type and shows no part of the
value.

**Nothing here encrypts.** 19.2 wraps a data key with this key and 19.3
stores a blob under it; this module only answers what the wrapping uses.
"""

import base64
import binascii
import secrets
from dataclasses import dataclass

from app.config import (
    APP_ENV_ENV_VAR,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    ENVIRONMENTS,
    EVIDENCE_ENCRYPTION_KEY_ENV_VAR,
)

__all__ = [
    "MASTER_KEY_BYTES",
    "MasterKey",
    "MasterKeyError",
    "generate_master_key",
    "load_master_key",
]


#: How many bytes one master key carries: 32, or AES-256.  A constant rather
#: than a parameter, because a width a caller can ask for is a width a caller
#: can ask for too small, and because 19.2 wraps data keys with AES-GCM,
#: which this project drives at 256 bits.
MASTER_KEY_BYTES = 32


#: What a production service with no key is told.  It names the variable and
#: the mode, it says plainly that no key is invented, and it quotes nothing:
#: the master key is the one value in this module that must never reach a log.
_NO_KEY_IN_PRODUCTION = (
    f"{EVIDENCE_ENCRYPTION_KEY_ENV_VAR} is not set, and this service is in "
    f"{ENV_PRODUCTION} mode, so no master key is generated and none is taken "
    f"from a constant: evidence written under a key this repository names "
    f"would be readable by anyone holding it. Set "
    f"{EVIDENCE_ENCRYPTION_KEY_ENV_VAR}, or run with "
    f"{APP_ENV_ENV_VAR}={ENV_DEVELOPMENT} for local work. No value is shown: "
    f"the master key must not reach a log."
)

#: What a value that is not a master key is told.  One message covers a string
#: that is not base64 at all, one that is base64 of some other width, and one
#: carrying characters the standard alphabet does not have.
_UNREADABLE = (
    f"{EVIDENCE_ENCRYPTION_KEY_ENV_VAR} must hold {MASTER_KEY_BYTES} bytes of "
    f"key as standard base64, and could not be read as one. No value is "
    f"shown: the master key must not reach a log."
)


class MasterKeyError(ValueError):
    """Raised when the master key cannot be used, or may not be made.

    A ``ValueError``, on :func:`app.ledger.signing.load_signing_key`'s
    reasoning: what is unusable is the configuration, and it is refused where
    it is read rather than at the first blob.
    """


@dataclass(frozen=True, repr=False, slots=True)
class MasterKey:
    """One master key, and the two facts about it a caller needs to know.

    :param key: :data:`MASTER_KEY_BYTES` raw bytes.  ``repr=False`` keeps
        them out of the object's own ``repr`` -- this is a value that must not
        be printed by a traceback.
    :param environment: the mode it was loaded in, one of
        :data:`app.config.ENVIRONMENTS`, so a caller can see which of the
        two answers it was given without holding the value that produced it.
    :param generated: whether the key was generated here rather than
        configured.  A generated key is never written down, so this is the
        flag 19.1's callers have in order to tell a key worth persisting
        from one that is not.
    """

    key: bytes
    environment: str
    generated: bool

    def __post_init__(self) -> None:
        """Refuse a key that is not master-key shaped, and freeze both.

        :returns: nothing.
        :raises TypeError: when :attr:`key` is neither ``bytes`` nor a
            ``bytearray``, or :attr:`generated` is not a ``bool``, naming the
            type and never the value.
        :raises ValueError: when the key is not :data:`MASTER_KEY_BYTES`
            wide, or the mode is not one of the two names
            :mod:`app.config` publishes -- so a ``MasterKey`` cannot be built
            in a mode :func:`load_master_key` would have refused.
        """
        if not isinstance(self.key, (bytes, bytearray)):
            raise TypeError(
                f"a master key is a {type(self.key).__name__}, and only bytes "
                f"may be one: no value is shown"
            )
        object.__setattr__(self, "key", bytes(self.key))
        if len(self.key) != MASTER_KEY_BYTES:
            raise ValueError(
                f"a master key carries {MASTER_KEY_BYTES} bytes, and this one "
                f"carries {len(self.key)}"
            )
        if self.environment not in ENVIRONMENTS:
            raise ValueError(
                f"a master key records the mode it was loaded in, and "
                f"{ENV_DEVELOPMENT!r} and {ENV_PRODUCTION!r} are the only two"
            )
        if not isinstance(self.generated, bool):
            raise TypeError(
                f"generated is a {type(self.generated).__name__}, and only a "
                f"bool may say where a key came from"
            )


def generate_master_key() -> bytes:
    """:data:`MASTER_KEY_BYTES` random bytes, from the OS CSPRNG.

    :returns: a fresh key.  Never the same one twice, and never derived from
        a seed, a clock or a counter -- all three are guessable by anyone who
        has seen one blob written under the key.
    """
    return secrets.token_bytes(MASTER_KEY_BYTES)


def load_master_key(configured: str | None, environment: str) -> MasterKey:
    """The master key for this process: the configured one, or a generated one.

    :param configured: what :func:`app.config.get_evidence_encryption_key`
        answered, as written.  ``None`` -- unset, or blank, which is what
        ``.env.example`` ships -- means no key was configured.
    :param environment: what :func:`app.config.get_app_env` answered.
    :returns: a :class:`MasterKey`.  Two calls handed ``None`` in development
        hold two different keys; see the module docstring.
    :raises MasterKeyError: when the mode is not one of the two published
        names, or when production has no key configured.  Neither generates
        one, and neither falls back to a constant.
    :raises TypeError: when an argument is not the type its parameter names,
        naming the type and no value.
    """
    mode = _read_environment(environment)
    if configured is None or (isinstance(configured, str) and not configured.strip()):
        if mode == ENV_PRODUCTION:
            raise MasterKeyError(_NO_KEY_IN_PRODUCTION)
        return MasterKey(key=generate_master_key(), environment=mode, generated=True)
    if not isinstance(configured, str):
        raise TypeError(
            f"{EVIDENCE_ENCRYPTION_KEY_ENV_VAR} is a "
            f"{type(configured).__name__}, and only a string or None may be "
            f"loaded as a master key: no value is shown"
        )
    return MasterKey(
        key=_decoded_master_key(configured.strip()),
        environment=mode,
        generated=False,
    )


def _read_environment(environment: str) -> str:
    """``environment`` folded to one of the two published mode names.

    :returns: the name, as :func:`app.config.get_app_env` spells it.
    :raises TypeError: naming the type of ``environment`` and no value.
    :raises MasterKeyError: when it names neither mode.  An unknown mode is
        refused rather than read as development, which is what keeps a
        misspelled :data:`~app.config.APP_ENV_ENV_VAR` from being the thing
        that turns the fallback on.
    """
    if not isinstance(environment, str):
        raise TypeError(
            f"the mode is a {type(environment).__name__}, and only one of the "
            f"two published mode names may be loaded with a master key: no "
            f"value is shown"
        )
    mode = environment.strip().lower()
    if mode not in ENVIRONMENTS:
        raise MasterKeyError(
            f"{APP_ENV_ENV_VAR} was read as {environment!r}, which is not one "
            f"of {', '.join(ENVIRONMENTS)}, so no master key is generated: an "
            f"unrecognised mode is refused rather than read as "
            f"{ENV_DEVELOPMENT}"
        )
    return mode


def _decoded_master_key(encoded: str) -> bytes:
    """``encoded`` as raw key bytes, or refused.

    :param encoded: the configured value, trimmed.
    :returns: :data:`MASTER_KEY_BYTES` raw bytes.
    :raises MasterKeyError: when it is not standard base64, or decodes to
        some other width.  Nothing is generated as a fallback: a key that
        cannot be read is an operator mistake, and a store that quietly wrote
        under a fresh one would leave evidence nobody can open.
    """
    try:
        key = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        # binascii.Error is what a character outside the standard alphabet
        # and a missing pad raise, and both are subclasses of ValueError, so
        # the pair catches the non-ASCII string as well: all of them are one
        # operator mistake, which is that the value is not a key.
        raise MasterKeyError(_UNREADABLE) from None
    if len(key) != MASTER_KEY_BYTES:
        raise MasterKeyError(_UNREADABLE)
    return key
