"""The per-record salt: fresh per record, stored beside it, never a global.

Task 9.4 asks for a per-record random salt, stored alongside the record, with
a test that two identical records get different salts and different hashes.
That test is the first one below.  The rest pin the properties the claim rests
on: where the bytes come from, how wide they are, and the fact that the salt
travels *with* its record rather than in a module global -- a global salt is
the one thing ROADMAP B3.4 rules out.
"""

from typing import Any

import pytest

from app.ledger import salts
from app.ledger.hashing import hash_record
from app.ledger.salts import SALT_BYTES, SaltedRecord, generate_salt, seal_record


#: A stand-in for the record 10.2 will seal -- text and integers only, since
#: D48 refuses a float and `screenings.score` is one.
RECORD: dict[str, Any] = {
    "actor": "station-3",
    "event_type": "flag_overridden",
    "payload": {"score": "41.7"},
}


# --- the task's claim -------------------------------------------------------


def test_two_identical_records_get_different_salts_and_different_hashes() -> None:
    """The task's own claim, and the reason a salt exists at all: without one
    per record, a reader cannot tell a repeat from a copy."""
    first = seal_record(RECORD)
    second = seal_record(RECORD)

    assert first.record == second.record == RECORD
    assert first.salt != second.salt
    assert first.digest != second.digest
    # Each is still a real digest of that record, not merely a different one.
    assert first.digest == hash_record(RECORD, first.salt)
    assert second.digest == hash_record(RECORD, second.salt)


def test_every_draw_is_a_different_salt() -> None:
    """A generator that repeated itself would pass the two-record test above
    by luck, and fail the ledger silently."""
    drawn = [generate_salt() for _ in range(256)]

    assert len(set(drawn)) == len(drawn)


# --- where the bytes come from ----------------------------------------------


def test_the_salt_comes_from_the_operating_system_csprng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`random` is not a fallback: a seeded Mersenne Twister is guessable from
    the record it is salting, and so is a fixed salt."""
    asked: list[int] = []

    def fake_token_bytes(n: int) -> bytes:
        asked.append(n)
        return b"\x01" * n

    monkeypatch.setattr(salts.secrets, "token_bytes", fake_token_bytes)

    assert generate_salt() == b"\x01" * SALT_BYTES
    assert asked == [SALT_BYTES]


def test_the_salt_is_sixteen_bytes() -> None:
    """128 bits: wider than the number of records this service will ever
    write can collide in, and a constant rather than a caller-chosen width."""
    assert len(generate_salt()) == SALT_BYTES == 16


def test_no_salt_is_held_for_a_caller_to_reuse() -> None:
    """The forbidden shape, checked mechanically: no module-level bytes at
    all, so there is no default for a writer to fall back to when it forgets."""
    held = [
        name
        for name in dir(salts)
        if isinstance(getattr(salts, name), (bytes, bytearray))
    ]

    assert held == []


# --- stored beside the record ----------------------------------------------


def test_the_record_is_stored_as_the_caller_spelled_it() -> None:
    """A writer seals and then persists the object it holds; if sealing
    rewrote it, the stored payload would not be the hashed one."""
    sealed = seal_record(RECORD)

    assert sealed.record is RECORD


def test_the_digest_is_taken_over_the_record_and_its_own_salt_only() -> None:
    """The pair is what 9.17 recomputes from, and it must be the same pair."""
    sealed = seal_record(RECORD)
    same_again = SaltedRecord(record=RECORD, salt=sealed.salt)

    assert same_again.digest == sealed.digest
    assert same_again == sealed


def test_the_stored_salt_is_immutable_bytes() -> None:
    """A `bytearray` the caller still holds could be mutated after the digest
    was taken, leaving a stored pair that no longer hashes to its own hash."""
    mutable = bytearray(b"\x9a\x1f\x4c\xd2")
    sealed = SaltedRecord(record=RECORD, salt=mutable)

    mutable[:] = b"\x00\x00\x00\x00"

    assert sealed.salt == b"\x9a\x1f\x4c\xd2"
    assert sealed.digest == hash_record(RECORD, b"\x9a\x1f\x4c\xd2")


def test_a_stored_salt_survives_a_text_column_as_hex() -> None:
    """The encoding it travels in, since `audit_events` is text: 32 lowercase
    hex, and `bytes.fromhex` reads back the salt that took the digest."""
    sealed = seal_record(RECORD)

    assert len(sealed.salt_hex) == SALT_BYTES * 2
    assert sealed.salt_hex == sealed.salt_hex.lower()
    assert all(c in "0123456789abcdef" for c in sealed.salt_hex)

    read_back = SaltedRecord(record=RECORD, salt=bytes.fromhex(sealed.salt_hex))

    assert read_back.digest == sealed.digest


# --- the refusal -----------------------------------------------------------


@pytest.mark.parametrize("salt", ["9a1f4cd2", 16, None, ["9a1f"]], ids=repr)
def test_a_salt_that_is_not_bytes_is_refused_and_its_value_is_not_shown(
    salt: Any,
) -> None:
    """The refusal names the type only, the way `_refuse` does, so a salt
    carrying anything of the record reaches no log."""
    with pytest.raises(TypeError) as caught:
        SaltedRecord(record=RECORD, salt=salt)

    assert type(salt).__name__ in str(caught.value)
    assert "9a1f4cd2" not in str(caught.value)
