"""The ledger's signing key: one Ed25519 key, loaded, and never echoed.

``LEDGER_SIGNING_KEY`` holds an unencrypted Ed25519 private key as PEM
PKCS#8 -- the spelling ``.env.example`` already publishes.
:func:`app.config.get_ledger_signing_key` is the only reader of that
variable; this module reads no environment of its own and is handed either
the configured PEM or ``None``, and ``None`` -- unset, or the blank value
``.env.example`` ships -- means a fresh key is generated so the zero-setup
demo runs with no configuration at all.

**A generated key is generated per call and held nowhere.**  There is no
module-level key and no cache, on :mod:`app.ledger.salts`'s reasoning that a
reused secret is not one.  The consequence is a claim rather than a
convenience: two callers handed ``None`` in the same process hold two
*different* keys, and a signature made by one does not verify under the
other's public key.  Persisting the key is the operator's job, and
:func:`generate_signing_key_pem` is what they persist.

**An answer is raw bytes, and the text spelling is 9.16's business.**
:attr:`Signer.public_key` is 32 raw bytes and :meth:`Signer.sign` is 64 --
the same answer :mod:`app.ledger.merkle` gives (``D51``), and the same
separation from ``ledger_entries``' text columns that ``D57`` records.  A
consumer holding only the bytes rebuilds the key with
``Ed25519PublicKey.from_public_bytes``; :func:`verify_signature` is where
that lives now, rather than in each consumer.

**Verifying is a verb here too, and it needs only the public key.**
:func:`verify_signature` answers a ``bool``, ``False`` where
:func:`app.ledger.merkle.verify_proof` answers ``False``, because a stored
signature that no longer holds is the answer 9.17 reports rather than an
exception to catch.  A key or signature of the wrong width answers
``False``; only a non-bytes argument is refused by type.  Nothing here
signs, so an auditor holding the 32 published bytes checks an entry
without holding anything secret.

**Ed25519 is deterministic**, so one key over one payload gives one
signature: an entry anchored twice is byte-identical rather than merely
equivalent.  That is a property of the curve, not a nonce scheme added here.

**Nothing here reads or writes a file, and no refusal quotes its input.**  A
private key that reaches a message is a private key in a log, so every
message in this module names the variable or the type and shows no value.
"""

from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import LEDGER_SIGNING_KEY_ENV_VAR

__all__ = [
    "PUBLIC_KEY_BYTES",
    "SIGNATURE_BYTES",
    "SIGNING_KEY_FORMAT",
    "Signer",
    "SigningKeyError",
    "generate_signing_key_pem",
    "load_signing_key",
    "verify_signature",
]


#: Ed25519's public key width: 32 raw bytes, and the width of what
#: :attr:`Signer.public_key` answers.
PUBLIC_KEY_BYTES = 32

#: Ed25519's signature width: 64 raw bytes, and the width of what
#: :meth:`Signer.sign` answers.
SIGNATURE_BYTES = 64

#: The one spelling a configured key may be written in, named so an operator
#: reading a refusal knows what to paste.  Unencrypted, because the
#: environment variable *is* the secret store and there is nowhere for a
#: passphrase to come from.
SIGNING_KEY_FORMAT = "an unencrypted Ed25519 private key as PEM PKCS#8"


class SigningKeyError(ValueError):
    """Raised when a configured key is not an Ed25519 private key.

    A ``ValueError``, on :func:`app.config.get_database_url`'s reasoning
    (``D37``): the configuration is what is unusable, and it is refused where
    it is read rather than at the first signature, where the operator is no
    longer watching.
    """


#: What an unreadable value is told, naming the variable and the format and
#: quoting nothing.  One message covers a string that is not PEM at all, a
#: *public* key, and a passphrase-protected one.
_UNREADABLE = (
    f"{LEDGER_SIGNING_KEY_ENV_VAR} must hold {SIGNING_KEY_FORMAT}, the "
    f"spelling .env.example publishes, and could not be read as one. "
    f"No value is shown: a private key must not reach a log."
)

#: What a readable private key of the wrong curve is told, for the same
#: reason.  A second message because the two failures are two different
#: operator mistakes and the fix for one is not the fix for the other.
_NOT_ED25519 = (
    f"{LEDGER_SIGNING_KEY_ENV_VAR} holds a private key, but not an Ed25519 "
    f"one, and this project signs ledger roots with Ed25519 alone. "
    f"No value is shown: a private key must not reach a log."
)


@dataclass(frozen=True, repr=False, slots=True)
class Signer:
    """One Ed25519 key, and the two things the ledger asks of it.

    :param key: the loaded private key.  Nothing else is kept, and
        ``repr=False`` keeps the key out of the object's own ``repr`` -- this
        is a value that must not be printed by a traceback.
    :raises TypeError: when ``key`` is not an ``Ed25519PrivateKey``, naming
        the type and no value, so a key of another curve cannot sign as
        though it were this one.
    """

    key: Ed25519PrivateKey

    def __post_init__(self) -> None:
        if not isinstance(self.key, Ed25519PrivateKey):
            raise TypeError(
                f"a signing key is an Ed25519PrivateKey, and this one is a "
                f"{type(self.key).__name__}: no value is shown"
            )

    @property
    def public_key(self) -> bytes:
        """:data:`PUBLIC_KEY_BYTES` raw bytes -- what verifies a signature."""
        public = self.key.public_key()
        return public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(self, data: bytes) -> bytes:
        """:data:`SIGNATURE_BYTES` raw bytes over ``data``.

        :param data: the bytes to sign -- 9.16's spelling of a Merkle root.
            A ``bytearray`` is copied on the way in; anything that is not
            bytes is refused rather than encoded.
        :returns: the signature, as raw bytes.
        :raises TypeError: naming the type of ``data`` and no value, since
            what went unsigned may be a payload.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(
                f"what is signed is a {type(data).__name__}, and only bytes "
                f"may be signed -- encode it first, so one payload has one "
                f"spelling. No value is shown"
            )
        return self.key.sign(bytes(data))


def generate_signing_key_pem() -> str:
    """A fresh Ed25519 private key, as the PEM this module loads.

    :returns: unencrypted PEM PKCS#8, the value
        :data:`~app.config.LEDGER_SIGNING_KEY_ENV_VAR` takes.  Never the same
        one twice, and never written anywhere by this module: persisting it
        is the operator's decision, and the ``.env.example`` entry is where
        it goes.
    """
    return _as_pem(Ed25519PrivateKey.generate())


def load_signing_key(configured: str | None) -> Signer:
    """The signer for this process: the configured key, or a generated one.

    :param configured: what :func:`app.config.get_ledger_signing_key`
        answered, as written.  ``None`` -- unset, or blank -- means no key
        was configured and one is generated here.  It is a required argument
        rather than a default, so a caller cannot sign with a key it never
        asked for.
    :returns: a :class:`Signer`.  Two calls handed ``None`` hold two
        different keys; see the module docstring.
    :raises TypeError: when ``configured`` is neither ``str`` nor ``None``.
    :raises SigningKeyError: when a configured value is not an unencrypted
        Ed25519 private key in PEM PKCS#8, naming the variable and never
        quoting it.  Nothing is generated as a fallback -- a key that cannot
        be read is an operator mistake, and anchoring under a key nobody
        holds would produce entries that are unverifiable from then on.
    """
    if configured is None:
        return Signer(Ed25519PrivateKey.generate())
    if not isinstance(configured, str):
        raise TypeError(
            f"{LEDGER_SIGNING_KEY_ENV_VAR} is a "
            f"{type(configured).__name__}, and only a string or None may be "
            f"loaded as a signing key: no value is shown"
        )
    pem = configured.strip()
    if not pem:
        return Signer(Ed25519PrivateKey.generate())

    try:
        loaded = serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None
        )
    except (UnsupportedAlgorithm, TypeError, ValueError) as error:
        # cryptography raises ValueError for a string that is not a PEM
        # private key at all, TypeError for one that is encrypted (no
        # password was given, and an env var has nowhere to carry one), and
        # UnsupportedAlgorithm for a key whose curve this build cannot read.
        # All three are one operator mistake: the value is not a key.
        raise SigningKeyError(_UNREADABLE) from error
    if not isinstance(loaded, Ed25519PrivateKey):
        raise SigningKeyError(_NOT_ED25519)
    return Signer(loaded)


def verify_signature(public_key: bytes, signature: bytes, data: bytes) -> bool:
    """Whether ``signature`` over ``data`` holds under ``public_key``.

    A verifier, not a second signer: it answers a ``bool`` rather than
    raising, on :func:`app.ledger.merkle.verify_proof`'s reasoning -- a
    stored signature that no longer matches is what 9.17 reports as
    ``altered``, not an exception to catch at every call site.

    :param public_key: :data:`PUBLIC_KEY_BYTES` raw bytes, as
        :attr:`Signer.public_key` answers them.
    :param signature: :data:`SIGNATURE_BYTES` raw bytes, as
        :meth:`Signer.sign` answers them.
    :param data: the bytes that were signed -- 9.16's Merkle root.
    :returns: whether the signature holds.  A key or signature of the wrong
        width, and a signature over different bytes, all answer ``False``:
        none of them can be the pair this log wrote.
    :raises TypeError: when an argument is not bytes, naming the parameter
        and the type and no value, on :meth:`Signer.sign`'s split between a
        wrong type and a wrong value.
    """
    for parameter, value in (
        ("public_key", public_key),
        ("signature", signature),
        ("data", data),
    ):
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(
                f"{parameter} is a {type(value).__name__}, and only bytes may "
                f"be verified -- one payload has one spelling. "
                f"No value is shown"
            )
    if (
        len(public_key) != PUBLIC_KEY_BYTES
        or len(signature) != SIGNATURE_BYTES
    ):
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes(public_key)).verify(
            bytes(signature), bytes(data)
        )
    except InvalidSignature:
        return False
    return True


def _as_pem(key: Ed25519PrivateKey) -> str:
    """``key`` as unencrypted PEM PKCS#8, the one configured spelling."""
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
