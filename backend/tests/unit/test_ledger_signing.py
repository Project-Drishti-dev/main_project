"""9.13: an Ed25519 key loaded from an env var, and a signature that verifies.

The task's own claim is the first test: a key configured through
``LEDGER_SIGNING_KEY`` signs, and the public key the signer exposes verifies
the signature -- rebuilt from those 32 raw bytes alone, which is the only
thing an anchoring consumer will ever hold.

The rest pin what the claim rests on, and two of them are the *uncomfortable*
halves rather than the convenient one:

- **A generated key is generated per call and cached nowhere**, so two
  callers handed no configured key hold two different keys and neither can
  verify the other's signature.  That is why the "generate one for dev" half
  of the task is a property and not a convenience, and it is checked with 256
  draws because a generator that repeated itself would pass a two-key test by
  luck.
- **A refusal quotes nothing.**  The configured value is a private key, every
  message names the variable or the type instead, and the tests hold the
  messages against the key material they were produced from.

9.14 adds the other half of the pair.  ``verify_signature`` is the service's
own check, so the claim under test is not "``cryptography`` rejects a forged
signature" but "a root that moved after it was signed is a root this service
answers ``False`` for" -- and it answers ``False`` rather than raising, since
that is the value 9.17 reports as ``altered``.  The tests sweep all
:data:`DIGEST_BYTES` positions rather than one, rebuild the root from an
altered *record* (the tamper that actually happens, which never touches the
stored root), and pin that a wrong key, a wrong width and a non-bytes
argument are three different answers.
"""

import ast
import pathlib
from typing import Any

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    generate_private_key,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key as rsa

from app import config
from app.config import LEDGER_SIGNING_KEY_ENV_VAR
from app.ledger import signing
from app.ledger.merkle import DIGEST_BYTES, build_tree, leaf_hash
from app.ledger.salts import seal_record
from app.ledger.signing import (
    PUBLIC_KEY_BYTES,
    SIGNATURE_BYTES,
    Signer,
    SigningKeyError,
    generate_signing_key_pem,
    load_signing_key,
    verify_signature,
)


SIGNING_MODULE = pathlib.Path(signing.__file__)

#: Two anchored records, in the shape 9.3 digests.  A root is what a batch
#: is anchored under, so it is what the signature is taken over.
EVENTS: tuple[dict[str, Any], ...] = (
    {"event": "screening_completed", "outcome": "cleared"},
    {"event": "screening_completed", "outcome": "flagged"},
)


@pytest.fixture(autouse=True)
def _no_configured_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test here starts from "no key configured", whatever the shell
    carries -- a developer's own ``.env`` must not decide a claim."""
    monkeypatch.delenv(LEDGER_SIGNING_KEY_ENV_VAR, raising=False)


def _verify(public_key: bytes, signature: bytes, payload: bytes) -> None:
    """Rebuild a key from the exposed bytes alone and check the signature."""
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)


def _root_over(records: Any) -> bytes:
    """The root a batch of records would be anchored under."""
    return build_tree(
        [leaf_hash(seal_record(record).digest.encode("ascii")) for record in records]
    ).root


# --- the task's claim --------------------------------------------------------


def test_a_key_loaded_from_the_env_var_signs_and_its_public_key_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task, end to end: a key in the environment, a signature out of it,
    and a verifier holding nothing but the public key that verifies it."""
    pem = generate_signing_key_pem()
    monkeypatch.setenv(LEDGER_SIGNING_KEY_ENV_VAR, pem)

    signer = load_signing_key(config.get_ledger_signing_key())
    root = b"\x11" * 32
    signature = signer.sign(root)

    assert len(signer.public_key) == PUBLIC_KEY_BYTES
    assert len(signature) == SIGNATURE_BYTES
    _verify(signer.public_key, signature, root)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"\x00", id="one-null-byte"),
        pytest.param(bytes(range(32)), id="a-32-byte-root"),
        pytest.param(b"e3b0c44298fc1c149afbf4c8996fb924", id="hex-spelling"),
        pytest.param(b"\x00" * 4096, id="four-kibibytes"),
    ],
)
def test_a_signature_round_trips_whatever_bytes_it_was_given(
    payload: bytes,
) -> None:
    """Nothing in the way: an empty message signs like any other, because the
    module adds no pre-check of its own to what the curve already accepts."""
    signer = load_signing_key(generate_signing_key_pem())

    signature = signer.sign(payload)

    _verify(signer.public_key, signature, payload)


def test_a_signature_verifies_after_the_key_is_loaded_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The round trip that matters: sign with one load, restart, verify with
    the next -- which is the only way an anchored entry is ever checked."""
    pem = generate_signing_key_pem()
    monkeypatch.setenv(LEDGER_SIGNING_KEY_ENV_VAR, pem)

    first = load_signing_key(config.get_ledger_signing_key())
    signature = first.sign(b"a-root-as-9-16-will-spell-it")

    second = load_signing_key(config.get_ledger_signing_key())

    assert second.public_key == first.public_key
    _verify(second.public_key, signature, b"a-root-as-9-16-will-spell-it")


def test_the_configured_key_is_the_key_that_signs() -> None:
    """A loader that generated a fresh key and ignored the configuration would
    pass every round trip above, because each one is self-consistent."""
    pem = generate_signing_key_pem()
    configured_key = serialization.load_pem_private_key(
        pem.encode("ascii"), password=None
    )

    signer = load_signing_key(pem)

    assert signer.public_key == configured_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


# --- the two answers' widths and shapes -------------------------------------


def test_the_answers_are_raw_bytes_of_the_widths_ed25519_defines() -> None:
    """Both answers are bytes, and a ``str`` is not one of them -- 9.16 is
    left to decide how either travels through a text column (``D57``)."""
    signer = load_signing_key(None)

    assert isinstance(signer.public_key, bytes)
    assert isinstance(signer.sign(b"x"), bytes)
    assert len(signer.public_key) == PUBLIC_KEY_BYTES == 32
    assert len(signer.sign(b"x")) == SIGNATURE_BYTES == 64


def test_the_public_key_is_the_same_bytes_every_time_it_is_asked_for() -> None:
    """9.16 reads it once per anchored batch; a value that moved between two
    reads would be two keys in one log."""
    signer = load_signing_key(generate_signing_key_pem())

    assert signer.public_key == signer.public_key


def test_signing_is_deterministic() -> None:
    """Ed25519 is a deterministic scheme: the same key over the same bytes
    gives the same signature, so an entry anchored twice is byte-identical."""
    pem = generate_signing_key_pem()
    first = load_signing_key(pem)
    second = load_signing_key(pem)

    assert first.sign(b"a-root") == first.sign(b"a-root")
    assert first.sign(b"a-root") == second.sign(b"a-root")


def test_a_bytearray_signs_exactly_as_the_bytes_it_holds() -> None:
    """A caller with a buffer is not refused -- the copy is taken on the way
    in, as ``SaltedRecord`` does, so a later mutation cannot change what was
    signed."""
    signer = load_signing_key(generate_signing_key_pem())
    buffer = bytearray(b"a-root")

    signature = signer.sign(buffer)

    assert signature == signer.sign(b"a-root")


# --- the "generate one for dev" half, which is a claim and not a convenience -


def test_each_generated_dev_key_is_a_different_key() -> None:
    """No key is cached and none is reused.  256 draws, because a generator
    that repeated itself would pass a two-key comparison by luck."""
    drawn = [load_signing_key(None).public_key for _ in range(256)]

    assert len(set(drawn)) == len(drawn)


def test_a_generated_dev_key_cannot_verify_another_generated_dev_key() -> None:
    """The honest consequence, and the reason a dev key must be persisted
    before anything is anchored: without a configured value, the signature
    that was just made is already unverifiable."""
    first = load_signing_key(None)
    second = load_signing_key(None)
    signature = first.sign(b"a-root")

    with pytest.raises(InvalidSignature):
        _verify(second.public_key, signature, b"a-root")


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param(None, id="unset"),
        pytest.param("", id="blank"),
        pytest.param("   \n\t ", id="whitespace"),
    ],
)
def test_no_configured_key_generates_rather_than_refusing(
    configured: str | None,
) -> None:
    """A blank value is what ``.env.example`` ships, so the zero-setup demo
    has to start on one -- refusal here would break local work over an unset
    optional variable."""
    signer = load_signing_key(configured)

    _verify(signer.public_key, signer.sign(b"a-root"), b"a-root")


def test_the_configuration_answers_none_for_both_an_unset_and_a_blank_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``config.py`` is where "configured or not" is decided; the ledger
    module is handed the answer and never reads an environment of its own."""
    assert config.get_ledger_signing_key() is None

    monkeypatch.setenv(LEDGER_SIGNING_KEY_ENV_VAR, "  \n")

    assert config.get_ledger_signing_key() is None


def test_the_configuration_answers_the_value_as_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not trimmed, not parsed, not re-serialised: what the operator wrote is
    what the module that knows the spelling is handed."""
    pem = generate_signing_key_pem()
    monkeypatch.setenv(LEDGER_SIGNING_KEY_ENV_VAR, pem)

    assert config.get_ledger_signing_key() == pem


# --- what a configured value may and may not be ------------------------------


def _encrypted_pem() -> str:
    """An Ed25519 private key under a passphrase, which an env var has nowhere
    to carry."""
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(b"a-passphrase"),
    ).decode("ascii")


def _public_pem() -> str:
    """The public half of a key -- no secret, and not a signing key."""
    return (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


def _rsa_pem() -> str:
    """A private key of another curve, in the one format that loads."""
    return rsa(public_exponent=65537, key_size=2048).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _ec_pem() -> str:
    """A second curve, so "not Ed25519" is not a claim about one key."""
    return generate_private_key(SECP256R1()).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _raw_seed() -> str:
    """The 32-byte private key on its own, with no PEM around it -- a
    spelling an operator reaches for first, and one that must not be
    silently accepted."""
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("not a key at all", id="prose"),
        pytest.param("-----BEGIN PRIVATE KEY-----\nnope\n", id="broken-pem"),
        pytest.param(_raw_seed(), id="a-raw-32-byte-seed-in-hex"),
        pytest.param(_public_pem(), id="a-public-key"),
        pytest.param(_encrypted_pem(), id="passphrase-protected"),
    ],
)
def test_a_value_that_is_not_an_ed25519_private_key_is_refused(
    value: str,
) -> None:
    """Every unreadable value is refused, and none of them falls back to a
    generated key -- an operator mistake must not quietly become a signature
    nobody can verify."""
    with pytest.raises(SigningKeyError):
        load_signing_key(value)


@pytest.mark.parametrize(
    ("value", "curve"),
    [
        pytest.param(_rsa_pem(), "RSA", id="rsa"),
        pytest.param(_ec_pem(), "EC", id="ec"),
    ],
)
def test_a_private_key_of_another_curve_is_refused_by_its_own_message(
    value: str,
    curve: str,
) -> None:
    """A readable key of the wrong curve is a different mistake from an
    unreadable one, and gets a different message -- both refuse."""
    with pytest.raises(SigningKeyError) as failure:
        load_signing_key(value)

    assert "not an Ed25519 one" in str(failure.value)
    assert curve not in str(failure.value)


def test_a_refusal_names_the_variable_and_never_quotes_the_value() -> None:
    """A configured key is a private key and this refusal can reach a log, so
    the message is held against carrying any of it -- including a value that
    is not even a key."""
    secret = "BEGIN PRIVATE KEY -- super-secret-marker"

    with pytest.raises(SigningKeyError) as failure:
        load_signing_key(secret)

    message = str(failure.value)
    assert LEDGER_SIGNING_KEY_ENV_VAR in message
    assert "Ed25519" in message
    assert "super-secret-marker" not in message
    assert secret not in message


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param(b"a-bytes-value", id="bytes"),
        pytest.param(2048, id="int"),
        pytest.param(["a-pem-in-a-list"], id="list"),
    ],
)
def test_a_value_that_is_not_a_string_is_refused_by_type(
    configured: object,
) -> None:
    """``None`` means "not configured"; anything else that is not text is a
    caller that read the variable wrongly, and is refused before it is
    parsed."""
    with pytest.raises(TypeError) as failure:
        load_signing_key(configured)

    assert type(configured).__name__ in str(failure.value)
    assert LEDGER_SIGNING_KEY_ENV_VAR in str(failure.value)


# --- what may be signed ------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("a-root-as-text", id="str"),
        pytest.param(1, id="int"),
        pytest.param(None, id="None"),
        pytest.param(["a", "b"], id="list"),
        pytest.param({"root": "a"}, id="dict"),
        pytest.param(memoryview(b"a-root"), id="memoryview"),
    ],
)
def test_sign_refuses_anything_that_is_not_bytes(payload: object) -> None:
    """Encoding a ``str`` here would be a second spelling of the same bytes
    (``D48``'s reasoning), and 9.16's root would then be signed without
    knowing which of the two it handed over."""
    signer = load_signing_key(generate_signing_key_pem())

    with pytest.raises(TypeError) as failure:
        signer.sign(payload)

    assert type(payload).__name__ in str(failure.value)
    assert "a-root" not in str(failure.value)


# --- 9.14: a signature over a root that was tampered with --------------------


def test_a_signature_over_a_tampered_root_fails_verification() -> None:
    """The task.  A signature covers the root and nothing else, so a root that
    moved after it was signed is a signature that does not hold -- and it
    answers ``False`` rather than raising, because "this root was altered" is
    what 9.17 has to be able to say."""
    signer = load_signing_key(generate_signing_key_pem())
    root = _root_over(EVENTS)
    signature = signer.sign(root)
    tampered = bytes((root[0] ^ 0x01,)) + root[1:]

    assert verify_signature(signer.public_key, signature, root) is True
    assert verify_signature(signer.public_key, signature, tampered) is False


def test_one_bit_flipped_anywhere_in_the_root_fails_verification() -> None:
    """All :data:`DIGEST_BYTES` positions rather than the first: a tamper that
    only the low byte's neighbour happened to catch is not a tamper that is
    caught."""
    signer = load_signing_key(generate_signing_key_pem())
    root = _root_over(EVENTS)
    signature = signer.sign(root)

    flipped = [
        verify_signature(
            signer.public_key,
            signature,
            root[:index] + bytes((root[index] ^ 0x01,)) + root[index + 1 :],
        )
        for index in range(len(root))
    ]

    assert flipped == [False] * DIGEST_BYTES


def test_a_root_rebuilt_from_an_altered_record_does_not_verify() -> None:
    """The tampering the signature is actually there for: nobody edits a
    stored root, they edit a record and let the tree be built again -- and the
    rebuild lands on a root the anchored signature does not cover."""
    signer = load_signing_key(generate_signing_key_pem())
    anchored = _root_over(EVENTS)
    signature = signer.sign(anchored)

    rebuilt = _root_over([EVENTS[0], {**EVENTS[1], "outcome": "cleared"}])

    assert rebuilt != anchored
    assert verify_signature(signer.public_key, signature, rebuilt) is False


def test_a_signature_holds_under_the_key_that_made_it_and_under_no_other() -> None:
    """Every way the pair can be wrong, which is every way a forged entry
    would be wrong: the wrong key, a bit flipped in the signature, the right
    width but not a signature, and a real signature by another key."""
    signer = load_signing_key(generate_signing_key_pem())
    other = load_signing_key(generate_signing_key_pem())
    root = _root_over(EVENTS)
    signature = signer.sign(root)

    assert verify_signature(signer.public_key, signature, root) is True
    assert verify_signature(other.public_key, signature, root) is False
    assert (
        verify_signature(
            signer.public_key, bytes((signature[0] ^ 0x01,)) + signature[1:], root
        )
        is False
    )
    assert verify_signature(signer.public_key, bytes(SIGNATURE_BYTES), root) is False
    assert verify_signature(signer.public_key, other.sign(root), root) is False


@pytest.mark.parametrize("width", [0, PUBLIC_KEY_BYTES - 1, PUBLIC_KEY_BYTES + 1])
def test_a_public_key_of_the_wrong_width_answers_false(width: int) -> None:
    """A stored column that came back short, long or empty is a signature that
    did not verify -- not an exception, so 9.17 can report it as ``altered``
    without guarding the call."""
    signer = load_signing_key(generate_signing_key_pem())
    root = _root_over(EVENTS)

    assert verify_signature(bytes(width), signer.sign(root), root) is False


@pytest.mark.parametrize("width", [0, SIGNATURE_BYTES - 1, SIGNATURE_BYTES + 1])
def test_a_signature_of_the_wrong_width_answers_false(width: int) -> None:
    """The other half of the same claim: the key can be perfectly good and the
    signature still be unreadable."""
    signer = load_signing_key(generate_signing_key_pem())
    root = _root_over(EVENTS)

    assert verify_signature(signer.public_key, bytes(width), root) is False


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        pytest.param("public_key", "a-key-as-text", id="key-as-str"),
        pytest.param("signature", 64, id="signature-as-int"),
        pytest.param("data", None, id="data-as-None"),
        pytest.param("data", ["a", "root"], id="data-as-list"),
    ],
)
def test_verify_refuses_anything_that_is_not_bytes(
    parameter: str, value: object
) -> None:
    """The same split ``sign`` draws: a wrong *type* is a caller that read a
    column wrongly and is refused, while a wrong *value* is the answer."""
    arguments: dict[str, object] = {
        "public_key": b"\x00" * PUBLIC_KEY_BYTES,
        "signature": bytes(SIGNATURE_BYTES),
        "data": b"a-root",
    }
    arguments[parameter] = value

    with pytest.raises(TypeError) as failure:
        verify_signature(**arguments)

    assert parameter in str(failure.value)
    assert type(value).__name__ in str(failure.value)
    assert "a-root" not in str(failure.value)


def test_a_bytearray_verifies_exactly_as_the_bytes_it_holds() -> None:
    """A caller holding a buffer is not refused: the copy is taken on the way
    in, as ``sign`` and ``SaltedRecord`` both do."""
    signer = load_signing_key(generate_signing_key_pem())
    root = _root_over(EVENTS)
    signature = signer.sign(root)

    assert (
        verify_signature(
            bytearray(signer.public_key), bytearray(signature), bytearray(root)
        )
        is True
    )


def test_verification_needs_no_private_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The audit path, and the reason the curve is asymmetric: the 32
    published bytes are the whole of what a verifier holds, and no ``Signer``
    has to be built to check an entry with them."""
    pem = generate_signing_key_pem()
    monkeypatch.setenv(LEDGER_SIGNING_KEY_ENV_VAR, pem)
    signer = load_signing_key(config.get_ledger_signing_key())
    root = _root_over(EVENTS)
    signature = signer.sign(root)

    assert verify_signature(signer.public_key, signature, root) is True


# --- what the module does not do ---------------------------------------------


def test_the_package_exports_exactly_its_public_names() -> None:
    """No second loading verb, no verb that exports or persists the private
    key."""
    assert set(signing.__all__) == {
        "PUBLIC_KEY_BYTES",
        "SIGNATURE_BYTES",
        "SIGNING_KEY_FORMAT",
        "Signer",
        "SigningKeyError",
        "generate_signing_key_pem",
        "load_signing_key",
        "verify_signature",
    }


def test_the_module_holds_no_key_at_module_level() -> None:
    """The "no cache" claim, checked on the source rather than trusted: a
    module-level name mentioning a key would be a key that outlives its
    caller and becomes the one every signature is made with."""
    offenders = [
        ast.dump(node)
        for node in ast.parse(SIGNING_MODULE.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and "Ed25519PrivateKey" in ast.dump(node.value)
    ]

    assert offenders == []


def test_the_module_reads_no_environment_variable() -> None:
    """``app.config`` is the only reader of the environment (``D37``), and
    this module is handed the value -- so a second ``os.getenv`` here would be
    a second spelling of a secret's source."""
    source = SIGNING_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "getenv" not in called
    assert "environ" not in called
    assert "import os" not in source


def test_a_signers_own_repr_carries_no_key_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A traceback prints ``repr``; a private key must not be in one.  The
    dataclass is built with ``repr=False`` for this reason alone."""
    pem = generate_signing_key_pem()
    monkeypatch.setenv(LEDGER_SIGNING_KEY_ENV_VAR, pem)

    signer = load_signing_key(config.get_ledger_signing_key())

    printed = repr(signer)
    assert "BEGIN" not in printed
    assert pem.strip().splitlines()[1] not in printed


def test_a_signer_cannot_be_built_around_a_key_of_another_curve() -> None:
    """The check belongs on the object as well as on the loader, so no caller
    can construct a ``Signer`` around a key the loader would have refused."""
    with pytest.raises(TypeError) as failure:
        Signer(rsa(public_exponent=65537, key_size=2048))

    assert "RSAPrivateKey" in str(failure.value)
