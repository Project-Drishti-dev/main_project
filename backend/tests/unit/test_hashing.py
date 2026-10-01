"""The digest a stored record is checked against: SHA-256 over salt + text.

Task 9.3 asks for ``hash_record(obj, salt)`` and two claims: one changed
field changes the hash, and the same record always hashes identically.  Both
are pinned here, plus a known answer so 9.17's recomputation is anchored to
something measured rather than to whatever the code happens to print.
"""

import hashlib
from typing import Any, Callable

import pytest

from app.ledger.canonical import CanonicalJsonError
from app.ledger.hashing import hash_record


#: A stand-in for the per-record salt 9.4 generates and 9.17 reads back.
SALT = b"\x9a\x1f\x4c\xd2"

RECORD: dict[str, Any] = {
    "actor": "station-3",
    "event_type": "flag_overridden",
    "payload": {"flags": [{"id": "DATE_MISMATCH", "value": 0}], "score": "41.7"},
}

#: The one spelling 9.3 hashes -- pinned here so the known answer below is
#: checkable by eye rather than only by running the function.
RECORD_TEXT = (
    '{"actor":"station-3","event_type":"flag_overridden","payload":'
    '{"flags":[{"id":"DATE_MISMATCH","value":0}],"score":"41.7"}}'
)


def _with_payload(**overrides: Any) -> Callable[[], dict[str, Any]]:
    """A builder for ``RECORD`` with one field inside its payload changed."""
    return lambda: {
        **RECORD,
        "payload": {**RECORD["payload"], **overrides},
    }


#: Each entry changes exactly one field of ``RECORD`` -- two at the top level,
#: two inside the payload, one added and one dropped.
CHANGES: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("actor", lambda: {**RECORD, "actor": "station-9"}),
    ("event_type", lambda: {**RECORD, "event_type": "flag_accepted"}),
    ("payload.score", _with_payload(score="41.8")),
    ("payload.flags[0].value", _with_payload(flags=[{"id": "DATE_MISMATCH", "value": 1}])),
    ("a field added", lambda: {**RECORD, "batch_id": "6f1c9a20-0000-4000-8000-000000000000"}),
    ("a field dropped", lambda: {k: v for k, v in RECORD.items() if k != "actor"}),
]


# --- the task's two claims --------------------------------------------------


def test_the_same_record_always_hashes_identically() -> None:
    """The claim 9.17 rests on: recomputing a hash months later must answer
    the same digest, or every stored record reads as altered."""
    first = hash_record(RECORD, SALT)

    assert hash_record(RECORD, SALT) == first
    assert hash_record({**RECORD}, SALT) == first
    assert hash_record(
        {
            "payload": {"score": "41.7", "flags": [{"value": 0, "id": "DATE_MISMATCH"}]},
            "event_type": "flag_overridden",
            "actor": "station-3",
        },
        SALT,
    ) == first


@pytest.mark.parametrize(
    "build_changed",
    [change for _, change in CHANGES],
    ids=[label for label, _ in CHANGES],
)
def test_one_changed_field_changes_the_hash(build_changed: Callable[[], dict[str, Any]]) -> None:
    """The other half of the task: a digest that cannot notice a changed
    field is not evidence of anything."""
    assert hash_record(build_changed(), SALT) != hash_record(RECORD, SALT)


# --- the digest itself ------------------------------------------------------


def test_a_record_hashes_to_a_known_digest() -> None:
    """Pinned independently of the module, so a refactor that changes what
    is hashed fails here rather than agreeing with itself forever."""
    expected = hashlib.sha256(SALT + RECORD_TEXT.encode("ascii")).hexdigest()

    assert expected == (
        "94219251f9602f5bdc4a324ff4695f71306f83bb69a42d7669816ed57094f7c7"
    )
    assert hash_record(RECORD, SALT) == expected


def test_the_digest_is_64_lowercase_hex_characters() -> None:
    """``AuditEvent.record_hash`` is a text column, so the return value is
    the stored spelling and nothing converts it."""
    digest = hash_record(RECORD, SALT)

    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(character in "0123456789abcdef" for character in digest)


def test_the_salt_is_hashed_in_front_of_the_record_and_nothing_else() -> None:
    """``salt || canonical_json(obj)``, in that order, with no separator --
    so an unsalted digest and a salt-appended one are both wrong."""
    unsalted = hashlib.sha256(RECORD_TEXT.encode("ascii")).hexdigest()
    appended = hashlib.sha256(RECORD_TEXT.encode("ascii") + SALT).hexdigest()

    assert hash_record(RECORD, SALT) not in (unsalted, appended)
    assert hash_record(RECORD, b"") == unsalted


def test_one_record_under_two_salts_is_two_digests() -> None:
    """What the salt is for: 9.4 gives two identical records different
    digests, so a reader cannot tell a repeat from a copy."""
    assert hash_record(RECORD, SALT) != hash_record(RECORD, SALT + b"\x00")


def test_a_bytearray_salt_is_accepted() -> None:
    """A caller holding a mutable buffer is not a reason to refuse a
    digest; it is hashed as the bytes it is."""
    assert hash_record(RECORD, bytearray(SALT)) == hash_record(RECORD, SALT)


# --- the refusals -----------------------------------------------------------


def test_a_record_with_no_canonical_spelling_is_refused_and_no_digest_returned() -> None:
    """``score`` is a float on ``screenings`` (D48), and a writer that
    spelled it would produce a digest this function cannot reproduce."""
    with pytest.raises(CanonicalJsonError):
        hash_record({**RECORD, "payload": {"score": 41.7}}, SALT)


@pytest.mark.parametrize("salt", ["not-bytes", 42, None, ["9a1f"]], ids=repr)
def test_a_salt_that_is_not_bytes_is_refused_and_its_value_is_not_shown(salt: Any) -> None:
    """The refusal names the type only, the way ``_refuse`` does, so a salt
    carrying anything of the record reaches no log."""
    with pytest.raises(TypeError) as caught:
        hash_record(RECORD, salt)

    assert type(salt).__name__ in str(caught.value)
    assert "not-bytes" not in str(caught.value)


def test_hashing_leaves_the_record_the_caller_will_persist_unchanged() -> None:
    """A writer hashes and then writes the object it holds; if hashing
    rewrote it, the stored payload would not be the hashed one."""
    before = {
        "actor": "station-9",
        "payload": {"flags": [{"id": "MRZ_CHECK_DIGIT", "value": 1}]},
    }

    hash_record(before, SALT)

    assert before == {
        "actor": "station-9",
        "payload": {"flags": [{"id": "MRZ_CHECK_DIGIT", "value": 1}]},
    }
