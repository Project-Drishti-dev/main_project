"""19.1: the master key -- loaded from the environment, generated in dev,
refused in production.

The claim is that a missing key never becomes a known constant, so it is
asked three ways: the production call refuses, no module ships a key-width
value, and 256 generated draws are all distinct.  An unrecognised ``APP_ENV``
is refused rather than read as development, since that variable alone gates
the fallback.
"""

import base64
import binascii

import pytest

from app import config
from app.config import (
    APP_ENV_ENV_VAR,
    DEFAULT_APP_ENV,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    ENVIRONMENTS,
    EVIDENCE_ENCRYPTION_KEY_ENV_VAR,
)
from app.storage import master_key
from app.storage.master_key import (
    MASTER_KEY_BYTES,
    MasterKey,
    MasterKeyError,
    generate_master_key,
    load_master_key,
)

#: One key-width value to configure, to draw, and to look for.
KEY_MATERIAL = bytes(range(MASTER_KEY_BYTES))


@pytest.fixture(autouse=True)
def _no_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test here starts from nothing configured, whatever the shell has."""
    monkeypatch.delenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(APP_ENV_ENV_VAR, raising=False)


def _encoded(raw: bytes) -> str:
    """``raw`` in the spelling ``EVIDENCE_ENCRYPTION_KEY`` takes."""
    return base64.b64encode(raw).decode("ascii")


def _message_of(refusal: Exception) -> str:
    """The refusal as the log would carry it."""
    return str(refusal)


def _shipped_values() -> dict[str, bytes | str]:
    """Every module-level bytes or string the two decision modules ship."""
    shipped: dict[str, bytes | str] = {}
    for module in (config, master_key):
        for name, value in vars(module).items():
            if isinstance(value, (bytes, bytearray, str)):
                shipped[module.__name__ + "." + name] = (
                    bytes(value) if isinstance(value, bytearray) else value
                )
    return shipped


def _is_key_width(value: bytes | str) -> bool:
    """Whether ``value`` could be used as a master key, raw or encoded."""
    if isinstance(value, (bytes, bytearray)):
        return len(value) == MASTER_KEY_BYTES
    try:
        return len(base64.b64decode(value, validate=True)) == MASTER_KEY_BYTES
    except (binascii.Error, ValueError):
        return False


def test_a_key_configured_through_the_environment_is_the_key_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end-to-end claim: the variable, the reader, the loader, one key."""
    monkeypatch.setenv(APP_ENV_ENV_VAR, ENV_PRODUCTION)
    monkeypatch.setenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR, _encoded(KEY_MATERIAL))

    loaded = load_master_key(
        config.get_evidence_encryption_key(), config.get_app_env()
    )

    assert loaded.key == KEY_MATERIAL
    assert loaded.generated is False
    assert loaded.environment == ENV_PRODUCTION


@pytest.mark.parametrize("mode", ENVIRONMENTS)
def test_the_configured_key_is_exactly_the_bytes_the_operator_wrote(mode: str) -> None:
    """Whatever the mode, a configured key is used rather than replaced."""
    loaded = load_master_key(_encoded(KEY_MATERIAL), mode)

    assert loaded.key == KEY_MATERIAL
    assert loaded.generated is False
    assert loaded.environment == mode


@pytest.mark.parametrize(
    ("spelled", "expected"),
    [("  PRODUCTION  ", ENV_PRODUCTION), ("Development", ENV_DEVELOPMENT)],
)
def test_the_reader_folds_and_trims_the_mode(
    monkeypatch: pytest.MonkeyPatch, spelled: str, expected: str
) -> None:
    """A shell that adds a case or a space still names the mode it meant."""
    monkeypatch.setenv(APP_ENV_ENV_VAR, spelled)

    assert config.get_app_env() == expected


@pytest.mark.parametrize("configured", [None, "", "   "], ids=["unset", "blank", "spaces"])
def test_a_missing_key_in_production_is_refused(configured: str | None) -> None:
    """The claim itself: no key configured, production, so no key at all."""
    with pytest.raises(MasterKeyError):
        load_master_key(configured, ENV_PRODUCTION)


def test_the_production_refusal_names_the_variable_and_the_mode() -> None:
    """A refusal the operator can act on, quoting nothing it cannot show."""
    with pytest.raises(MasterKeyError) as refusal:
        load_master_key(None, ENV_PRODUCTION)

    message = _message_of(refusal.value)
    assert EVIDENCE_ENCRYPTION_KEY_ENV_VAR in message
    assert ENV_PRODUCTION in message
    assert APP_ENV_ENV_VAR in message
    assert "constant" in message


@pytest.mark.parametrize("mode", ["prod", "staging", "test", "", "   "])
def test_an_unreadable_mode_is_refused_rather_than_read_as_development(
    mode: str,
) -> None:
    """A typo in the one variable that gates the fallback cannot open it."""
    with pytest.raises(MasterKeyError) as refusal:
        load_master_key(None, mode)

    assert APP_ENV_ENV_VAR in _message_of(refusal.value)


@pytest.mark.parametrize(
    ("spelled", "expected"),
    [
        ("  PRODUCTION  ", ENV_PRODUCTION),
        ("Development", ENV_DEVELOPMENT),
    ],
)
def test_a_mode_name_is_folded_and_trimmed(spelled: str, expected: str) -> None:
    """A shell that adds a case or a space is still the mode it named."""
    if expected == ENV_PRODUCTION:
        with pytest.raises(MasterKeyError):
            load_master_key(None, spelled)
        return
    assert load_master_key(None, spelled).environment == expected


def test_the_key_is_thirty_two_bytes_because_aes_256_needs_it() -> None:
    """One width, pinned: nobody may quietly shrink the key under AES."""
    assert MASTER_KEY_BYTES == 32


def test_a_key_is_generated_when_development_has_none() -> None:
    """The zero-setup demo starts with nothing configured, and needs a key."""
    loaded = load_master_key(None, ENV_DEVELOPMENT)

    assert loaded.generated is True
    assert loaded.environment == ENV_DEVELOPMENT
    assert isinstance(loaded.key, bytes)
    assert len(loaded.key) == MASTER_KEY_BYTES


def test_a_blank_key_in_development_is_a_missing_key() -> None:
    """Blank is what ``.env.example`` ships, so it is absent, not malformed."""
    assert load_master_key("   ", ENV_DEVELOPMENT).generated is True


def test_a_generated_key_is_never_the_same_one_twice() -> None:
    """256 draws, all distinct: a constant or a seeded generator fails this."""
    drawn = [load_master_key(None, ENV_DEVELOPMENT).key for _ in range(256)]

    assert len(set(drawn)) == len(drawn)
    assert all(len(key) == MASTER_KEY_BYTES for key in drawn)


def test_generate_master_key_is_fresh_every_call() -> None:
    """The generator the loader uses is the one that never repeats."""
    assert generate_master_key() != generate_master_key()
    assert len(generate_master_key()) == MASTER_KEY_BYTES


def test_no_module_ships_a_value_that_could_serve_as_a_key() -> None:
    """A ``DEV_KEY`` beside the loader would be the failure this task names."""
    shipped = _shipped_values()
    offenders = sorted(
        name for name, value in shipped.items() if _is_key_width(value)
    )

    assert offenders == []
    drawn = {load_master_key(None, ENV_DEVELOPMENT).key for _ in range(64)}
    assert not drawn.intersection(bytes(value) for value in shipped.values() if isinstance(value, (bytes, bytearray)))


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param(KEY_MATERIAL.hex(), id="hex-not-base64"),
        pytest.param("-----BEGIN PRIVATE KEY-----", id="a-pem"),
    ],
)
def test_a_malformed_key_is_refused_in_development_too(configured: str) -> None:
    """A key that cannot be read is never replaced by a generated one."""
    with pytest.raises(MasterKeyError):
        load_master_key(configured, ENV_DEVELOPMENT)


def test_surrounding_space_is_trimmed_from_a_configured_key() -> None:
    """A shell that adds whitespace is not a malformed key."""
    padded = "  " + _encoded(KEY_MATERIAL) + chr(10)

    assert load_master_key(padded, ENV_PRODUCTION).key == KEY_MATERIAL


def test_a_refusal_quotes_no_part_of_the_value() -> None:
    """The configured value is the key itself, so it reaches no message."""
    configured = "my-key-material-written-in-prose"

    with pytest.raises(MasterKeyError) as refusal:
        load_master_key(configured, ENV_DEVELOPMENT)

    message = _message_of(refusal.value)
    assert EVIDENCE_ENCRYPTION_KEY_ENV_VAR in message
    assert configured not in message
    for start in range(len(configured) - 11):
        assert configured[start : start + 12] not in message


def test_a_master_key_refuses_a_value_that_is_not_bytes() -> None:
    """Bytes or a bytearray, and the refusal names the type and no value."""
    with pytest.raises(TypeError) as refusal:
        MasterKey(key="k" * MASTER_KEY_BYTES, environment=ENV_DEVELOPMENT, generated=False)

    message = _message_of(refusal.value)
    assert "str" in message
    assert "master key" in message


def test_a_master_key_refuses_a_key_of_the_wrong_width() -> None:
    """One width, so a key that cannot be used never reaches a caller."""
    with pytest.raises(ValueError) as refusal:
        MasterKey(key=b"k" * (MASTER_KEY_BYTES - 1), environment=ENV_DEVELOPMENT, generated=False)

    assert str(MASTER_KEY_BYTES) in _message_of(refusal.value)


def test_a_master_key_refuses_a_mode_it_does_not_know() -> None:
    """A built key cannot name a mode the loader would have refused."""
    with pytest.raises(ValueError) as refusal:
        MasterKey(key=b"k" * MASTER_KEY_BYTES, environment="staging", generated=False)

    assert ENV_DEVELOPMENT in _message_of(refusal.value)


def test_a_master_key_refuses_a_generated_flag_that_is_not_a_bool() -> None:
    """Where a key came from is a fact, not a value a caller may phrase."""
    with pytest.raises(TypeError) as refusal:
        MasterKey(key=b"k" * MASTER_KEY_BYTES, environment=ENV_DEVELOPMENT, generated="yes")

    assert "str" in _message_of(refusal.value)


def test_a_bytearray_key_is_copied_so_a_buffer_cannot_change_it() -> None:
    """The caller keeps its buffer; the key is already frozen bytes."""
    buffer = bytearray(b"k" * MASTER_KEY_BYTES)
    loaded = MasterKey(key=buffer, environment=ENV_DEVELOPMENT, generated=False)
    buffer[:] = b"x" * MASTER_KEY_BYTES

    assert loaded.key == b"k" * MASTER_KEY_BYTES


def test_repr_carries_no_key_material() -> None:
    """A traceback must not print the key in any of its three spellings."""
    loaded = load_master_key(_encoded(KEY_MATERIAL), ENV_DEVELOPMENT)

    printed = repr(loaded)
    assert KEY_MATERIAL.hex() not in printed
    assert _encoded(KEY_MATERIAL) not in printed
    assert repr(KEY_MATERIAL) not in printed

def test_the_reader_answers_none_when_unset_or_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No key configured is ``None`` and not an empty string."""
    assert config.get_evidence_encryption_key() is None

    monkeypatch.setenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR, "   ")

    assert config.get_evidence_encryption_key() is None


def test_the_reader_hands_back_the_text_as_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trimming and decoding belong to the loader, which knows what a key is."""
    monkeypatch.setenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR, "  " + _encoded(KEY_MATERIAL) + " ")

    assert config.get_evidence_encryption_key() == "  " + _encoded(KEY_MATERIAL) + " "


def test_the_default_is_one_module_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Changing the shipped default changes the answer: one spelling of it."""
    monkeypatch.setattr(config, "DEFAULT_APP_ENV", ENV_PRODUCTION)

    assert config.get_app_env() == ENV_PRODUCTION


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_the_mode_defaults_to_development_when_unset_or_blank(
    monkeypatch: pytest.MonkeyPatch, configured: str | None
) -> None:
    """The zero-setup demo starts with nothing configured."""
    if configured is not None:
        monkeypatch.setenv(APP_ENV_ENV_VAR, configured)

    assert config.get_app_env() == DEFAULT_APP_ENV == ENV_DEVELOPMENT


@pytest.mark.parametrize("spelled", ["prod", "PRODUCTION_MODE", "development mode", "0"])
def test_an_unknown_mode_is_refused_by_the_reader(
    monkeypatch: pytest.MonkeyPatch, spelled: str
) -> None:
    """The reader stops the start-up rather than choosing on the operator's behalf."""
    monkeypatch.setenv(APP_ENV_ENV_VAR, spelled)

    with pytest.raises(ValueError) as refusal:
        config.get_app_env()

    message = _message_of(refusal.value)
    assert APP_ENV_ENV_VAR in message
    for environment in ENVIRONMENTS:
        assert environment in message


def test_a_configured_key_is_answered_in_development_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whichever mode it is in, a configured key is a configured key."""
    monkeypatch.setenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR, _encoded(KEY_MATERIAL))

    assert config.get_app_env() == ENV_DEVELOPMENT
    assert load_master_key(
        config.get_evidence_encryption_key(), config.get_app_env()
    ).generated is False
