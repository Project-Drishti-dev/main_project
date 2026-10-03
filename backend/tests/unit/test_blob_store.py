"""19.3: the evidence store -- put bytes, read them back, find them by address.

The claim is a round trip, so it is asked twice over: thirty-two documents
of every width through put and get and back byte for byte, and then again
through a second store over the same directory, because a reference that
only answers on the object that wrote it is not a reference.

The other half of the claim is what is written down.  A file named by the
SHA-256 of the plaintext, whose bytes carry neither the document nor the
master key, and which does not open once it has been moved under another
address -- the binding D156 left to this task.
"""

import base64
import binascii
import hashlib
import pathlib
import secrets

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import ENV_DEVELOPMENT
from app.storage import blob_store
from app.storage.blob_store import (
    BLOB_DIGEST_BYTES,
    BLOB_DIGEST_HEX_CHARS,
    BLOB_HEADER_BYTES,
    BLOB_NONCE_BYTES,
    BLOB_SUFFIX,
    BLOB_TAG_BYTES,
    BlobNotFound,
    BlobRef,
    BlobStoreError,
    BlobUnreadable,
    EvidenceStore,
)
from app.storage.data_key import (
    DATA_KEY_BYTES,
    DATA_KEY_NONCE_BYTES,
    DATA_KEY_TAG_BYTES,
    generate_data_key,
    wrap_data_key,
)
from app.storage.master_key import MASTER_KEY_BYTES, MasterKey

#: One master key to write under, so a case is about the store alone.
MASTER = MasterKey(
    key=bytes(range(MASTER_KEY_BYTES)), environment=ENV_DEVELOPMENT, generated=False
)

#: A document with no file header and no shape a reader has to understand:
#: the store holds bytes, and what those bytes are is the caller business.
DOCUMENT = bytes(range(256)) * 4

#: Where the wrapped key sits inside the header, beside its nonce.
_WRAPPED_KEY_END = DATA_KEY_NONCE_BYTES + DATA_KEY_BYTES + DATA_KEY_TAG_BYTES


def _store(root: pathlib.Path) -> EvidenceStore:
    """A store over root, under the one master key."""
    return EvidenceStore(root, MASTER)


def _message_of(refusal: Exception) -> str:
    """The refusal as the log would carry it."""
    return str(refusal)


def _written_by_hand(root: pathlib.Path, digest: str, payload: bytes) -> None:
    """A file at digest that opens, and is not the document digest names.

    The one thing the store itself will not write: its own put always
    seals under the digest it names, so a blob that opens to something else
    has to be assembled here out of the published parts.
    """
    associated = blob_store._associated_data(bytes.fromhex(digest))
    data_key = generate_data_key()
    wrapped = wrap_data_key(MASTER, data_key, associated)
    nonce = secrets.token_bytes(BLOB_NONCE_BYTES)
    sealed = AESGCM(data_key).encrypt(nonce, payload, associated)
    (root / (digest + BLOB_SUFFIX)).write_bytes(
        wrapped.nonce + wrapped.ciphertext + nonce + sealed
    )


def _shipped_values() -> dict[str, bytes | str]:
    """Every module-level bytes or string the module ships."""
    shipped: dict[str, bytes | str] = {}
    for name, value in vars(blob_store).items():
        if isinstance(value, (bytes, bytearray, str)):
            shipped[blob_store.__name__ + "." + name] = (
                bytes(value) if isinstance(value, bytearray) else value
            )
    return shipped


def _is_key_width(value: bytes | str) -> bool:
    """Whether value could be used as a master key, raw or encoded."""
    if isinstance(value, (bytes, bytearray)):
        return len(value) == MASTER_KEY_BYTES
    try:
        return len(base64.b64decode(value, validate=True)) == MASTER_KEY_BYTES
    except (binascii.Error, ValueError):
        return False


def test_the_widths_are_pinned() -> None:
    """32, 12, 16 and 72: AES-GCM would accept a nonce of another width."""
    assert BLOB_DIGEST_BYTES == 32
    assert BLOB_DIGEST_HEX_CHARS == 64
    assert BLOB_NONCE_BYTES == 12
    assert BLOB_TAG_BYTES == 16
    assert BLOB_HEADER_BYTES == 72


def test_a_blob_is_named_by_the_sha256_of_the_plaintext(tmp_path: pathlib.Path) -> None:
    """The name is the address, so a blob is found rather than guessed at."""
    store = _store(tmp_path)

    reference = store.put(DOCUMENT)

    assert reference.digest == hashlib.sha256(DOCUMENT).hexdigest()
    assert [p.name for p in tmp_path.iterdir()] == [
        reference.digest + BLOB_SUFFIX
    ]


def test_a_reference_records_the_size_the_blob_opens_to(tmp_path: pathlib.Path) -> None:
    """A reader knows what to expect without opening the file."""
    reference = _store(tmp_path).put(DOCUMENT)

    assert reference.size == len(DOCUMENT)


def test_what_is_written_is_not_the_plaintext(tmp_path: pathlib.Path) -> None:
    """The file is the document plus a header and a tag, and none of it is text."""
    store = _store(tmp_path)
    reference = store.put(DOCUMENT)

    stored = store.path_of(reference).read_bytes()

    assert stored != DOCUMENT
    assert DOCUMENT not in stored
    assert len(stored) == BLOB_HEADER_BYTES + len(DOCUMENT) + BLOB_TAG_BYTES


def test_the_header_is_three_parts_at_fixed_widths(tmp_path: pathlib.Path) -> None:
    """A reader slices it by offset, so it parses no format at all."""
    store = _store(tmp_path)
    reference = store.put(DOCUMENT)

    stored = store.path_of(reference).read_bytes()

    wrapped_nonce = stored[:DATA_KEY_NONCE_BYTES]
    wrapped_key = stored[DATA_KEY_NONCE_BYTES:_WRAPPED_KEY_END]
    blob_nonce = stored[_WRAPPED_KEY_END:BLOB_HEADER_BYTES]
    assert len(wrapped_nonce) == len(blob_nonce) == DATA_KEY_NONCE_BYTES
    assert len(wrapped_key) == DATA_KEY_BYTES + DATA_KEY_TAG_BYTES
    assert wrapped_nonce != blob_nonce


def test_a_blob_carries_neither_the_document_nor_the_master_key(
    tmp_path: pathlib.Path,
) -> None:
    """What is written down opens only through the key that is not in it."""
    store = _store(tmp_path)
    reference = store.put(DOCUMENT)

    stored = store.path_of(reference).read_bytes()

    assert DOCUMENT not in stored
    assert MASTER.key not in stored
    assert base64.b64encode(MASTER.key) not in stored


def test_a_blob_round_trips_byte_for_byte(tmp_path: pathlib.Path) -> None:
    """The round trip the task names, for one document."""
    store = _store(tmp_path)

    assert store.get(store.put(DOCUMENT)) == DOCUMENT


def test_thirty_two_documents_of_every_width_survive_the_trip(
    tmp_path: pathlib.Path,
) -> None:
    """Not one in thirty-two: a nonce or a tag mistake shows up here."""
    store = _store(tmp_path)

    for width in [0, 1, 15, 16, 17, 64, 1024] * 5:
        payload = secrets.token_bytes(width)
        assert store.get(store.put(payload)) == payload


def test_a_reference_answers_again_to_a_second_store(tmp_path: pathlib.Path) -> None:
    """The directory is what persists; the object that wrote it need not."""
    reference = _store(tmp_path).put(DOCUMENT)

    assert _store(tmp_path).get(reference) == DOCUMENT


def test_the_same_bytes_are_written_once(tmp_path: pathlib.Path) -> None:
    """A file is named by what it opens to, so a second write changes nothing."""
    store = _store(tmp_path)
    reference = store.put(DOCUMENT)
    before = store.path_of(reference).read_bytes()

    again = store.put(DOCUMENT)

    assert again == reference
    assert store.path_of(reference).read_bytes() == before
    assert len(list(tmp_path.iterdir())) == 1


def test_two_documents_are_two_files_and_two_references(
    tmp_path: pathlib.Path,
) -> None:
    """Different bytes address differently, so nothing overwrites anything."""
    store = _store(tmp_path)

    one = store.put(b"the first document")
    two = store.put(b"the second document")

    assert one.digest != two.digest
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [one.digest + BLOB_SUFFIX, two.digest + BLOB_SUFFIX]
    )
    assert store.get(one) == b"the first document"
    assert store.get(two) == b"the second document"


def test_the_data_key_and_the_nonce_are_drawn_not_derived(tmp_path: pathlib.Path) -> None:
    """One address written twice answers two headers and the same document."""
    one = _store(tmp_path / "one")
    two = _store(tmp_path / "two")

    first = one.put(DOCUMENT)
    second = two.put(DOCUMENT)

    assert (
        one.path_of(first).read_bytes()[:BLOB_HEADER_BYTES]
        != two.path_of(second).read_bytes()[:BLOB_HEADER_BYTES]
    )
    assert one.get(first) == two.get(second) == DOCUMENT


def test_a_blob_moved_under_another_address_does_not_open(
    tmp_path: pathlib.Path,
) -> None:
    """The digest is sealed in, so a move is caught rather than served."""
    store = _store(tmp_path)
    moved = store.put(b"the first document")
    target = store.put(b"the second document")
    store.path_of(target).write_bytes(store.path_of(moved).read_bytes())

    with pytest.raises(BlobUnreadable) as refusal:
        store.get(target)

    assert "did not open" in _message_of(refusal.value)
    assert store.get(moved) == b"the first document"


def test_a_file_that_opens_to_another_document_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """A name is a claim about the bytes, and the bytes are checked against it."""
    store = _store(tmp_path)
    other = b"a document this name does not address"
    _written_by_hand(tmp_path, hashlib.sha256(DOCUMENT).hexdigest(), other)

    with pytest.raises(BlobUnreadable) as refusal:
        store.get(BlobRef(digest=hashlib.sha256(DOCUMENT).hexdigest(), size=len(other)))

    message = _message_of(refusal.value)
    assert "SHA-256" in message
    assert other.decode("ascii") not in message


def test_altered_bytes_fail_closed_and_quote_nothing(tmp_path: pathlib.Path) -> None:
    """One flipped tag byte is a refusal, never a partial document."""
    store = _store(tmp_path)
    reference = store.put(DOCUMENT)
    path = store.path_of(reference)
    body = bytearray(path.read_bytes())
    body[-1] ^= 0xFF
    path.write_bytes(bytes(body))

    with pytest.raises(BlobUnreadable) as refusal:
        store.get(reference)

    message = _message_of(refusal.value)
    assert "did not open" in message
    assert str(len(DOCUMENT)) not in message


def test_a_file_shorter_than_the_header_is_refused(tmp_path: pathlib.Path) -> None:
    """Every part of the header is a fixed width, so a short file is not one."""
    store = _store(tmp_path)
    reference = store.put(DOCUMENT)
    store.path_of(reference).write_bytes(b"x")

    with pytest.raises(BlobUnreadable) as refusal:
        store.get(reference)

    assert "header" in _message_of(refusal.value)


def test_an_address_the_store_holds_nothing_at_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """A reference to a blob nobody wrote is a refusal, not an empty answer."""
    store = _store(tmp_path)

    with pytest.raises(BlobNotFound):
        store.get(BlobRef(digest="0" * BLOB_DIGEST_HEX_CHARS, size=10))


def test_a_reference_never_names_anything_outside_the_root(
    tmp_path: pathlib.Path,
) -> None:
    """The path is built from the digest, so it can only be the one file."""
    store = _store(tmp_path)

    path = store.path_of(store.put(DOCUMENT))

    assert path.parent == tmp_path
    assert path.suffix == BLOB_SUFFIX


def test_put_leaves_no_partial_file_beside_the_blob(tmp_path: pathlib.Path) -> None:
    """A blob is written whole or not at all, and the half is never named."""
    _store(tmp_path).put(DOCUMENT)

    names = [p.name for p in tmp_path.iterdir()]

    assert len(names) == 1
    assert not any(name.endswith(".partial") for name in names)


def test_a_bytearray_is_stored_as_it_stood(tmp_path: pathlib.Path) -> None:
    """The store copies, so a buffer the caller still holds is not the blob."""
    store = _store(tmp_path)
    buffer = bytearray(DOCUMENT)
    reference = store.put(buffer)
    buffer[:] = b"x" * len(DOCUMENT)

    assert store.get(reference) == DOCUMENT


def test_a_reference_survives_a_column(tmp_path: pathlib.Path) -> None:
    """One token a row can hold, and nothing of the document in it."""
    reference = _store(tmp_path).put(DOCUMENT)

    spelled = reference.to_wire()

    assert DOCUMENT.decode("latin-1") not in spelled
    assert BlobRef.from_wire(spelled) == reference


def test_a_reference_read_back_from_a_column_opens_the_same_blob(
    tmp_path: pathlib.Path,
) -> None:
    """The spelling is a reference, not a copy of the fields."""
    store = _store(tmp_path)
    reference = BlobRef.from_wire(store.put(DOCUMENT).to_wire())

    assert store.get(reference) == DOCUMENT


@pytest.mark.parametrize(
    "mangled",
    [
        "sha256:" + "0" * 64,
        "sha256:" + "0" * 64 + ":",
        "sha256:" + "0" * 63 + ":10",
        "sha256:" + "A" * 64 + ":10",
        "sha512:" + "0" * 64 + ":10",
        "sha256:" + "0" * 64 + ":-1",
        "sha256:" + "0" * 64 + ":01",
        "sha256:" + "0" * 64 + ":10 ",
        " sha256:" + "0" * 64 + ":10",
        "sha256:" + "0" * 64 + ":10:extra",
    ],
    ids=[
        "no-size",
        "empty-size",
        "short-digest",
        "upper-case-digest",
        "another-algorithm",
        "negative-size",
        "padded-size",
        "trailing-space",
        "leading-space",
        "an-extra-field",
    ],
)
def test_a_mangled_reference_is_refused(mangled: str) -> None:
    """One spelling or none, because guessing at one reads a blob nobody asked for."""
    with pytest.raises(BlobStoreError):
        BlobRef.from_wire(mangled)


@pytest.mark.parametrize("not_text", [b"sha256:" + b"0" * 64 + b":10", None, 10])
def test_reading_a_reference_that_is_not_text_is_refused(not_text: object) -> None:
    """The type is named and no value, since a value here is a column."""
    with pytest.raises(TypeError) as refusal:
        BlobRef.from_wire(not_text)

    assert "text" in _message_of(refusal.value)


@pytest.mark.parametrize(
    "digest",
    ["", "0" * 63, "0" * 65, "A" * 64, "g" * 64, "../../etc/passwd", " " * 64],
    ids=["empty", "short", "long", "upper-case", "not-hex", "a-path", "spaces"],
)
def test_a_reference_refuses_a_digest_that_is_not_a_digest(digest: str) -> None:
    """Checked here rather than at the filesystem, so no path is ever built."""
    with pytest.raises(ValueError) as refusal:
        BlobRef(digest=digest, size=1)

    assert str(BLOB_DIGEST_HEX_CHARS) in _message_of(refusal.value)


@pytest.mark.parametrize(
    "not_a_digest", [b"0" * 64, None, 64], ids=["raw-bytes", "none", "an-int"]
)
def test_a_reference_refuses_a_digest_that_is_not_text(not_a_digest: object) -> None:
    """Only text may address a blob, and the refusal names the type."""
    with pytest.raises(TypeError) as refusal:
        BlobRef(digest=not_a_digest, size=1)

    assert "digest" in _message_of(refusal.value)


@pytest.mark.parametrize("not_a_size", ["10", 10.0, None, True])
def test_a_reference_refuses_a_size_that_is_not_a_length(not_a_size: object) -> None:
    """Only a whole number of bytes measures a blob, and a bool is not one."""
    with pytest.raises(TypeError) as refusal:
        BlobRef(digest="0" * 64, size=not_a_size)

    assert "size" in _message_of(refusal.value)


def test_a_reference_refuses_a_negative_size() -> None:
    """Nothing is a length below zero, so the field is refused rather than kept."""
    with pytest.raises(ValueError) as refusal:
        BlobRef(digest="0" * 64, size=-1)

    assert "-1" in _message_of(refusal.value)


@pytest.mark.parametrize(
    "not_a_reference",
    [b"sha256:" + b"0" * 64 + b":10", None, "sha256:" + "0" * 64 + ":10"],
    ids=["raw-bytes", "none", "a-column-spelling"],
)
def test_reading_refuses_anything_but_a_reference(
    tmp_path: pathlib.Path, not_a_reference: object
) -> None:
    """Text out of a column is not a reference until it is read as one."""
    store = _store(tmp_path)

    with pytest.raises(TypeError) as refusal:
        store.get(not_a_reference)

    assert "BlobRef" in _message_of(refusal.value)


@pytest.mark.parametrize(
    "not_bytes", ["not bytes", list(range(8)), None, 10],
    ids=["a-string", "a-list", "none", "an-int"],
)
def test_putting_refuses_anything_but_bytes(
    tmp_path: pathlib.Path, not_bytes: object
) -> None:
    """The refusal names the type and no value, since a value here is a document."""
    store = _store(tmp_path)

    with pytest.raises(TypeError) as refusal:
        store.put(not_bytes)

    message = _message_of(refusal.value)
    assert "bytes" in message
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "not_a_master_key",
    [MASTER.key, None, MasterKey, "m" * MASTER_KEY_BYTES],
    ids=["raw-bytes", "none", "the-class", "a-string"],
)
def test_a_store_refuses_anything_but_a_master_key(
    tmp_path: pathlib.Path, not_a_master_key: object
) -> None:
    """Bytes off an attribute are not the object that checked them."""
    with pytest.raises(TypeError) as refusal:
        EvidenceStore(tmp_path, not_a_master_key)

    assert "MasterKey" in _message_of(refusal.value)


def test_the_store_creates_its_root(tmp_path: pathlib.Path) -> None:
    """A deployment that has no directory yet still gets a working store."""
    store = _store(tmp_path / "evidence" / "blobs")

    reference = store.put(DOCUMENT)

    assert (tmp_path / "evidence" / "blobs").is_dir()
    assert store.get(reference) == DOCUMENT


def test_a_root_that_is_not_a_directory_is_refused(tmp_path: pathlib.Path) -> None:
    """A store that cannot be written to would answer for a blob it never wrote."""
    (tmp_path / "evidence").write_bytes(b"not a directory")

    with pytest.raises(BlobStoreError) as refusal:
        EvidenceStore(tmp_path / "evidence", MASTER)

    assert "directory" in _message_of(refusal.value)


def test_no_module_ships_a_value_that_could_be_a_key() -> None:
    """A key constant beside the store is the failure this module exists against."""
    shipped = _shipped_values()

    assert sorted(name for name, value in shipped.items() if _is_key_width(value)) == []


def test_the_module_reads_no_environment_of_its_own() -> None:
    """The master key is handed in (D154); this module names no variable."""
    source = pathlib.Path(blob_store.__file__ or "").read_text(encoding="utf-8")

    assert "getenv" not in source
    assert "environ[" not in source
