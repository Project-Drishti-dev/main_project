"""19.2: the per-blob data key -- generated fresh, wrapped under the master key.

The claim is a round trip, so it is asked four ways: sixty-four generated
keys through the whole trip and back byte for byte, one key wrapped twice
answering two different wrapped forms, the wrapped form carrying neither the
data key nor the master key in the clear, and a wrapped key refused under a
master key that did not wrap it.
"""

import base64
import binascii
import pathlib

import pytest

from app.config import ENV_DEVELOPMENT, ENV_PRODUCTION
from app.storage import data_key
from app.storage.data_key import (
    DATA_KEY_BYTES,
    DATA_KEY_NONCE_BYTES,
    DATA_KEY_TAG_BYTES,
    DataKeyError,
    WrappedDataKey,
    generate_data_key,
    unwrap_data_key,
    wrap_data_key,
)
from app.storage.master_key import MASTER_KEY_BYTES, MasterKey

#: One master key to wrap under, so a case is about the data key alone.
MASTER = MasterKey(
    key=bytes(range(MASTER_KEY_BYTES)), environment=ENV_DEVELOPMENT, generated=False
)

#: Another master key, equal in every way but in its bytes.
OTHER_MASTER = MasterKey(
    key=bytes(MASTER_KEY_BYTES),
    environment=ENV_DEVELOPMENT,
    generated=False,
)


def _message_of(refusal: Exception) -> str:
    """The refusal as the log would carry it."""
    return str(refusal)


def _shipped_values() -> dict[str, bytes | str]:
    """Every module-level bytes or string the module ships."""
    shipped: dict[str, bytes | str] = {}
    for name, value in vars(data_key).items():
        if isinstance(value, (bytes, bytearray, str)):
            shipped[data_key.__name__ + "." + name] = (
                bytes(value) if isinstance(value, bytearray) else value
            )
    return shipped


def _is_key_width(value: bytes | str) -> bool:
    """Whether ``value`` could be used as a data key, raw or encoded."""
    if isinstance(value, (bytes, bytearray)):
        return len(value) == DATA_KEY_BYTES
    try:
        return len(base64.b64decode(value, validate=True)) == DATA_KEY_BYTES
    except (binascii.Error, ValueError):
        return False


def test_a_data_key_is_thirty_two_bytes_because_aes_256_needs_it() -> None:
    """One width, pinned, and the same width the master key carries."""
    assert DATA_KEY_BYTES == MASTER_KEY_BYTES == 32


def test_the_nonce_and_tag_are_the_widths_aes_gcm_specifies() -> None:
    """12 and 16: a nonce of any other width still round-trips, so pin both."""
    assert DATA_KEY_NONCE_BYTES == 12
    assert DATA_KEY_TAG_BYTES == 16


def test_a_generated_data_key_is_thirty_two_bytes() -> None:
    """The generator the wrapper is handed answers exactly one width."""
    drawn = generate_data_key()

    assert isinstance(drawn, bytes)
    assert len(drawn) == DATA_KEY_BYTES


def test_a_generated_data_key_is_never_the_same_one_twice() -> None:
    """256 draws, all distinct: a constant or a seeded generator fails this."""
    drawn = [generate_data_key() for _ in range(256)]

    assert len(set(drawn)) == len(drawn)


def test_a_data_key_is_not_the_master_key_it_is_wrapped_under() -> None:
    """A derived key would leave every blob recoverable from the master."""
    drawn = [generate_data_key() for _ in range(64)]

    assert MASTER.key not in drawn


def test_a_wrapped_data_key_opens_back_to_the_key_it_wrapped() -> None:
    """The round trip the task names, for one key."""
    original = generate_data_key()

    wrapped = wrap_data_key(MASTER, original)

    assert unwrap_data_key(MASTER, wrapped) == original


def test_sixty_four_keys_survive_the_whole_trip() -> None:
    """Not one key in sixty-four: a nonce or a tag mistake shows up here."""
    for _ in range(64):
        original = generate_data_key()

        assert unwrap_data_key(MASTER, wrap_data_key(MASTER, original)) == original


def test_a_wrapped_key_is_the_data_key_and_its_tag_and_nothing_else() -> None:
    """The wrapped form carries one key and one tag, at the pinned widths."""
    wrapped = wrap_data_key(MASTER, generate_data_key())

    assert len(wrapped.nonce) == DATA_KEY_NONCE_BYTES
    assert len(wrapped.ciphertext) == DATA_KEY_BYTES + DATA_KEY_TAG_BYTES


def test_two_wraps_of_one_key_answer_two_different_wrapped_forms() -> None:
    """A nonce reused under one key leaks that key outright, so it is drawn."""
    original = generate_data_key()

    first = wrap_data_key(MASTER, original)
    second = wrap_data_key(MASTER, original)

    assert first.ciphertext != second.ciphertext
    assert first.nonce != second.nonce
    assert unwrap_data_key(MASTER, first) == unwrap_data_key(MASTER, second) == original


def test_a_wrapped_form_holds_neither_key_in_the_clear() -> None:
    """What is written down opens only through the master key."""
    original = generate_data_key()

    wrapped = wrap_data_key(MASTER, original)

    assert original not in wrapped.ciphertext
    assert MASTER.key not in wrapped.ciphertext


def test_opening_under_another_master_key_is_refused() -> None:
    """The wrong master key fails closed: a refusal, never wrong bytes."""
    wrapped = wrap_data_key(MASTER, generate_data_key())

    with pytest.raises(DataKeyError):
        unwrap_data_key(OTHER_MASTER, wrapped)


def test_the_mode_is_metadata_and_does_not_change_the_key() -> None:
    """The same bytes under the other mode still open it: only bytes decide."""
    same_bytes_other_mode = MasterKey(
        key=MASTER.key, environment=ENV_PRODUCTION, generated=False
    )
    original = generate_data_key()
    wrapped = wrap_data_key(MASTER, original)

    assert unwrap_data_key(same_bytes_other_mode, wrapped) == original


def test_a_refusal_names_both_readings_and_quotes_no_key() -> None:
    """AES-GCM cannot tell a wrong key from an altered value, so both are said."""
    wrapped = wrap_data_key(MASTER, generate_data_key())

    with pytest.raises(DataKeyError) as refusal:
        unwrap_data_key(OTHER_MASTER, wrapped)

    message = _message_of(refusal.value)
    assert "master key" in message
    assert "altered" in message
    assert refusal.value.__suppress_context__ is True
    assert OTHER_MASTER.key.hex() not in message
    assert wrapped.ciphertext.hex() not in message


def test_repr_carries_no_key_material() -> None:
    """A traceback must not print the data key or the wrapped form."""
    original = generate_data_key()

    printed = repr(wrap_data_key(MASTER, original))

    assert original.hex() not in printed
    assert repr(original) not in printed
    assert base64.b64encode(original).decode("ascii") not in printed
    assert base64.b64encode(original).decode("ascii") not in printed


def test_a_wrapped_key_refuses_a_nonce_of_the_wrong_width() -> None:
    """One width per field, so a malformed wrapped form never reaches AES."""
    with pytest.raises(ValueError) as refusal:
        WrappedDataKey(
            nonce=bytes(DATA_KEY_NONCE_BYTES - 1),
            ciphertext=bytes(DATA_KEY_BYTES + DATA_KEY_TAG_BYTES),
        )

    assert str(DATA_KEY_NONCE_BYTES) in _message_of(refusal.value)


@pytest.mark.parametrize("short_by", [1, DATA_KEY_TAG_BYTES])
def test_a_wrapped_key_refuses_a_ciphertext_of_the_wrong_width(short_by: int) -> None:
    """A truncated or padded wrapped form is refused before any crypto runs."""
    width = DATA_KEY_BYTES + DATA_KEY_TAG_BYTES

    with pytest.raises(ValueError) as refusal:
        WrappedDataKey(
            nonce=bytes(DATA_KEY_NONCE_BYTES), ciphertext=bytes(width - short_by)
        )

    assert str(width) in _message_of(refusal.value)


@pytest.mark.parametrize("field", ["nonce", "ciphertext"])
def test_a_wrapped_key_refuses_a_field_that_is_not_bytes(field: str) -> None:
    """Bytes or a bytearray, and the refusal names the type and no value."""
    fields = {
        "nonce": bytes(DATA_KEY_NONCE_BYTES),
        "ciphertext": bytes(DATA_KEY_BYTES + DATA_KEY_TAG_BYTES),
    }
    fields[field] = "k" * len(fields[field])

    with pytest.raises(TypeError) as refusal:
        WrappedDataKey(**fields)

    assert "str" in _message_of(refusal.value)


def test_a_wrapped_key_copies_a_bytearray_so_a_buffer_cannot_change_it() -> None:
    """The caller keeps its buffer; the wrapped form is already frozen."""
    nonce = bytearray(bytes(DATA_KEY_NONCE_BYTES))
    ciphertext = bytearray(bytes(DATA_KEY_BYTES + DATA_KEY_TAG_BYTES))

    wrapped = WrappedDataKey(nonce=nonce, ciphertext=ciphertext)
    nonce[:] = b"x" * DATA_KEY_NONCE_BYTES
    ciphertext[:] = b"x" * (DATA_KEY_BYTES + DATA_KEY_TAG_BYTES)

    assert wrapped.nonce == bytes(DATA_KEY_NONCE_BYTES)
    assert wrapped.ciphertext == bytes(DATA_KEY_BYTES + DATA_KEY_TAG_BYTES)


def test_a_bytearray_data_key_is_wrapped_as_it_stood() -> None:
    """The wrapper copies, so a buffer the caller still holds is not wrapped."""
    buffer = bytearray(generate_data_key())
    expected = bytes(buffer)

    wrapped = wrap_data_key(MASTER, buffer)
    buffer[:] = b"x" * DATA_KEY_BYTES

    assert unwrap_data_key(MASTER, wrapped) == expected


@pytest.mark.parametrize("short_by", [1, 2])
def test_wrapping_refuses_a_data_key_of_the_wrong_width(short_by: int) -> None:
    """A data key that is not a data key is refused before any crypto runs."""
    with pytest.raises(ValueError) as refusal:
        wrap_data_key(MASTER, bytes(DATA_KEY_BYTES - short_by))

    message = _message_of(refusal.value)
    assert "data key" in message
    assert str(DATA_KEY_BYTES) in message


@pytest.mark.parametrize("not_bytes", ["k" * DATA_KEY_BYTES, list(range(DATA_KEY_BYTES))])
def test_wrapping_refuses_a_data_key_that_is_not_bytes(not_bytes: object) -> None:
    """The refusal names the type and no value, since a data key is a secret."""
    with pytest.raises(TypeError) as refusal:
        wrap_data_key(MASTER, not_bytes)

    assert "data key" in _message_of(refusal.value)


@pytest.mark.parametrize(
    "not_a_master_key",
    [MASTER.key, None, MasterKey, "m" * MASTER_KEY_BYTES],
    ids=["raw-bytes", "none", "the-class", "a-string"],
)
def test_wrapping_and_opening_refuse_anything_but_a_master_key(
    not_a_master_key: object,
) -> None:
    """Only a MasterKey may wrap or open: bytes off an attribute are not one."""
    original = generate_data_key()
    wrapped = wrap_data_key(MASTER, original)

    with pytest.raises(TypeError) as refusal:
        wrap_data_key(not_a_master_key, original)
    assert "MasterKey" in _message_of(refusal.value)

    with pytest.raises(TypeError) as refusal:
        unwrap_data_key(not_a_master_key, wrapped)
    assert "MasterKey" in _message_of(refusal.value)


@pytest.mark.parametrize(
    "not_a_wrapped_key",
    [b"n" * (DATA_KEY_NONCE_BYTES + DATA_KEY_BYTES + DATA_KEY_TAG_BYTES), None],
    ids=["raw-bytes", "none"],
)
def test_opening_refuses_anything_but_a_wrapped_key(not_a_wrapped_key: object) -> None:
    """Bytes off a file are not a WrappedDataKey until they are read as one."""
    with pytest.raises(TypeError) as refusal:
        unwrap_data_key(MASTER, not_a_wrapped_key)

    assert "WrappedDataKey" in _message_of(refusal.value)


def test_no_module_ships_a_value_that_could_serve_as_a_data_key() -> None:
    """A data key constant beside the wrapper is the failure this task names."""
    shipped = _shipped_values()

    assert sorted(name for name, value in shipped.items() if _is_key_width(value)) == []


def test_the_module_reads_no_environment_of_its_own() -> None:
    """The master key is handed in (D154); this module names no variable."""
    source = pathlib.Path(data_key.__file__ or "").read_text(encoding="utf-8")

    assert "getenv" not in source
    assert "environ[" not in source
    assert not hasattr(data_key, "os")
