"""The evidence store: a blob written once, under its own content address.

:func:`EvidenceStore.put` takes the bytes an officer uploaded and answers a
:class:`BlobRef`; the document itself never leaves this module and no row in
this service holds it.  What is written is AES-GCM ciphertext under a data
key drawn for that blob alone (D156), and the file is named by the SHA-256
of the plaintext -- so the same document put twice is stored once, and a
blob is found by its address rather than by a name a caller chose.

**The name is the content's address, and nothing else reaches the
filesystem.**  It is 64 hex characters of a digest and the one suffix this
module writes, so no reference -- and no filename, screening id or path a
caller sends -- can name a file outside the store's root.

**A blob is self-describing.**  Every file is a fixed
:data:`BLOB_HEADER_BYTES` byte header beside the ciphertext: the nonce and
wrapped data key :mod:`app.storage.data_key` writes, then the nonce this
module drew, then the sealed document.  Each part of the header is a fixed
width, so a reader slices it by offset and parses no format at all.

**The address is sealed into the blob rather than filed beside it.**  The
digest is AES-GCM's associated data for both halves, so a blob moved under
another blob's name does not open -- nor does one whose bytes were altered.
That binding is what D156 left to this task.

**The same bytes are written once.**  A blob whose address the store already
holds is not written again and the reference answers the same either way: a
file is named by what it decrypts to, so there is nothing a second write
could change.

**A blob is never returned rather than returned wrongly.**  An address the
store holds nothing at is :class:`BlobNotFound`; a file that does not open,
or that opens to something which is not what its name addresses, is
:class:`BlobUnreadable`.  Neither quotes a byte of the document.

**Nothing here reads the environment.**  D154 loads the master key and this
module is handed one, on the reasoning that a key is not read where it is
used.
"""

import hashlib
import os
import re
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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
from app.storage.master_key import MasterKey

__all__ = [
    "BLOB_DIGEST_BYTES",
    "BLOB_DIGEST_HEX_CHARS",
    "BLOB_FORMAT_TAG",
    "BLOB_HEADER_BYTES",
    "BLOB_NONCE_BYTES",
    "BLOB_SUFFIX",
    "BLOB_TAG_BYTES",
    "BlobNotFound",
    "BlobRef",
    "BlobStoreError",
    "BlobUnreadable",
    "EvidenceStore",
]


#: How many bytes SHA-256's digest carries, and how many hex characters
#: spell it in a file name.
BLOB_DIGEST_BYTES = 32
BLOB_DIGEST_HEX_CHARS = BLOB_DIGEST_BYTES * 2

#: How many bytes the nonce drawn per blob carries: 12, the width AES-GCM is
#: specified at.  Pinned rather than a parameter, on
#: :data:`app.storage.data_key.DATA_KEY_NONCE_BYTES`' reasoning that a width
#: the primitive would also accept is a width nothing holds still.
BLOB_NONCE_BYTES = 12

#: How many bytes the tag AES-GCM appends to a blob carries: 16.
BLOB_TAG_BYTES = 16

#: How many bytes the header in front of every blob carries: the wrapped
#: key's nonce, the wrapped key itself, and this module's own nonce.  Every
#: part of it is a fixed width, so the header's length is the only thing a
#: reader has to check before slicing it.
BLOB_HEADER_BYTES = (
    DATA_KEY_NONCE_BYTES + DATA_KEY_BYTES + DATA_KEY_TAG_BYTES + BLOB_NONCE_BYTES
)

#: What every blob file's name ends in.  A blob is written beside its final
#: name under this one's absence, so a half-written file is never named like
#: a blob and cannot be read as one.
BLOB_SUFFIX = ".blob"

#: The bytes AES-GCM is handed as associated data, beside the digest itself.
#: The tag is what a later format is told apart from this one by: a blob
#: sealed under different rules must not open under these.
BLOB_FORMAT_TAG = b"drishti/evidence/v1"

#: Where each part of the header begins and ends, as offsets into a file.
#: Nothing here parses a format: every boundary is a constant.
_WRAPPED_KEY_END = DATA_KEY_NONCE_BYTES + DATA_KEY_BYTES + DATA_KEY_TAG_BYTES
_BLOB_NONCE_END = _WRAPPED_KEY_END + BLOB_NONCE_BYTES


#: What an address the store holds nothing at is told.  It names the digest
#: rather than the file, and shows no path.
_NO_SUCH_BLOB = (
    "no blob is stored at this address: the store has never written this "
    "digest, or the file has been removed since. Nothing is returned rather "
    "than returned wrongly."
)

#: What a file too short to be one of ours is told.
_MALFORMED = (
    "the stored blob is not one this module wrote: it is shorter than the "
    "header every blob carries, and every part of that header is a fixed "
    "width, so there is nothing left to read. Nothing is returned rather "
    "than returned wrongly."
)

#: What a file that does not open is told.  It names both readings, because
#: AES-GCM cannot tell them apart, and it quotes no byte of the document.
_NOT_OPENED = (
    "the stored blob did not open: the master key is not the one it was "
    "written under, or its bytes were altered or moved under another "
    "address. Nothing is returned rather than returned wrongly, and no part "
    "of the document is shown."
)

#: What a blob that opens to the wrong document is told.
_WRONG_ADDRESS = (
    "the stored blob opened but is not the document its name addresses: the "
    "SHA-256 of what came back is not the digest its name carries. Nothing "
    "is returned rather than returned wrongly, and no part of the document "
    "is shown."
)

#: What a root that cannot be a directory is told.
_NO_ROOT = (
    "the evidence store's root could not be created, or what is there is not "
    "a directory: a store that cannot be written to would answer a "
    "reference for a blob it never wrote. No path is shown."
)


class BlobStoreError(ValueError):
    """Raised when a blob cannot be written, or cannot be read back.

    A ``ValueError``, on :class:`app.storage.data_key.DataKeyError`'s
    reasoning: what is unusable is the blob, and it is refused where it is
    used rather than at the first row.
    """


class BlobNotFound(BlobStoreError):
    """Raised when the store holds nothing at the address a reference names."""


class BlobUnreadable(BlobStoreError):
    """Raised when a stored blob does not open, or is not what it is named.

    One type for the ways a file can be wrong -- a master key that is not
    the one it was written under, bytes that were altered, and a blob moved
    under another address -- because AES-GCM makes the first two one answer
    and the address binding makes the third one too.  Which of them it was
    is a question about the store rather than about the document.
    """


_DIGEST_PATTERN = re.compile(r"\A[0-9a-f]{" + str(BLOB_DIGEST_HEX_CHARS) + r"}\Z")
_WIRE_PATTERN = re.compile(
    r"\Asha256:([0-9a-f]{" + str(BLOB_DIGEST_HEX_CHARS) + r"}):(0|[1-9][0-9]*)\Z"
)


@dataclass(frozen=True, slots=True)
class BlobRef:
    """Where one blob lives: its content address and the size it opens to.

    :param digest: the SHA-256 of the plaintext, as 64 lowercase hex
        characters.  This is the file's name, so a reference is what finds a
        blob rather than a path a caller could aim somewhere.
    :param size: how many bytes the blob opens to, so a reader knows what to
        expect without reading the file.

    Carries no path and no key.  Two references to one document are the same
    value, which is what lets a document be stored once.
    """

    digest: str
    size: int

    def __post_init__(self) -> None:
        """Refuse a reference that names nothing this store could hold.

        :returns: nothing.
        :raises TypeError: when :attr:`digest` is not text or :attr:`size` is
            not a whole number, naming the type and no value.
        :raises ValueError: when :attr:`digest` is not exactly
            :data:`BLOB_DIGEST_HEX_CHARS` lowercase hex characters, or
            :attr:`size` is negative -- checked here rather than at the
            filesystem, so nothing a reference carries ever reaches a path.
        """
        if not isinstance(self.digest, str):
            raise TypeError(
                f"a blob digest is a {type(self.digest).__name__}, and only "
                f"text may address a blob"
            )
        if _DIGEST_PATTERN.match(self.digest) is None:
            raise ValueError(
                f"a blob is addressed by {BLOB_DIGEST_HEX_CHARS} lowercase "
                f"hex characters of SHA-256, and this one carries "
                f"{len(self.digest)}"
            )
        if not isinstance(self.size, int) or isinstance(self.size, bool):
            raise TypeError(
                f"a blob size is a {type(self.size).__name__}, and only a "
                f"whole number of bytes may measure a blob"
            )
        if self.size < 0:
            raise ValueError(
                f"a blob measures {self.size} bytes, which is not a length "
                f"anything can have"
            )

    def to_wire(self) -> str:
        """The reference as the one token a column may hold.

        :returns: ``sha256:<digest>:<size>``, and nothing of the document.
        """
        return f"sha256:{self.digest}:{self.size}"

    @classmethod
    def from_wire(cls, text: str) -> "BlobRef":
        """The reference ``text`` spells, or refused.

        :param text: what :meth:`to_wire` wrote, read back from a column.
        :returns: the reference it names.
        :raises BlobStoreError: when it is not that one spelling.  A
            reference that is read as anything else is not a reference, and
            guessing at it would be reading a blob nobody asked for.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"a stored blob reference is a {type(text).__name__}, and "
                f"only text may be read back as one"
            )
        matched = _WIRE_PATTERN.match(text)
        if matched is None:
            raise BlobStoreError(
                "a stored blob reference reads sha256:<"
                f"{BLOB_DIGEST_HEX_CHARS} hex characters>:<size>, and this "
                f"one could not be read as one: no value is shown"
            )
        return cls(digest=matched.group(1), size=int(matched.group(2)))


class EvidenceStore:
    """One directory of encrypted evidence blobs, and the key they open under.

    :param root: the directory the blobs live in, created if it is not
        already there.  Nothing outside it is ever read or written.
    :param master_key: what :func:`app.storage.master_key.load_master_key`
        answered.  Every blob is wrapped under it, so the store is what ties
        a directory of files to something that can open them.

    **The store keeps no index.**  A blob is found by its address, so a
    reference is a complete way to reach one and nothing has to be kept in
    step with what is on disk.
    """

    def __init__(self, root: str | Path, master_key: MasterKey) -> None:
        """Freeze the key, and make sure there is a directory to write into.

        :param root: where the blobs live.  A path a caller chose; nothing
            derived from a document ever reaches it.
        :param master_key: the key every blob is wrapped under.
        :returns: nothing.
        :raises BlobStoreError: when the root cannot be created, or what is
            there is not a directory.
        :raises TypeError: naming the type of ``master_key`` and no value.
        """
        self._master_key = _checked_master_key(master_key)
        self._root = Path(root)
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise BlobStoreError(_NO_ROOT) from None

    def put(self, plaintext: Any) -> BlobRef:
        """``plaintext`` written as an encrypted blob, addressed by its digest.

        :param plaintext: the bytes an officer uploaded.
        :returns: the :class:`BlobRef` the blob is written under, and the
            same reference when the same bytes are put again.
        :raises TypeError: naming the type of ``plaintext`` and no value,
            since a document must not reach a log.
        """
        payload = _checked_bytes(plaintext, "a blob")
        digest = hashlib.sha256(payload).digest()
        reference = BlobRef(digest=digest.hex(), size=len(payload))
        target = self._path_of(reference)
        if target.exists():
            return reference
        _written_atomically(target, self._sealed(payload, digest))
        return reference

    def get(self, reference: Any) -> bytes:
        """The document ``reference`` addresses, opened.

        :param reference: the :class:`BlobRef` :meth:`put` answered.
        :returns: the bytes that were put, byte for byte.
        :raises BlobNotFound: when this store holds nothing at that address.
        :raises BlobUnreadable: when the stored blob does not open, or opens
            to something which is not the document its name addresses.
        :raises TypeError: naming the type of ``reference`` and no value.
        """
        checked = _checked_reference(reference)
        digest = bytes.fromhex(checked.digest)
        try:
            stored = self._path_of(checked).read_bytes()
        except FileNotFoundError:
            raise BlobNotFound(_NO_SUCH_BLOB) from None
        if len(stored) < BLOB_HEADER_BYTES:
            raise BlobUnreadable(_MALFORMED)
        associated = _associated_data(digest)
        try:
            data_key = unwrap_data_key(
                self._master_key,
                WrappedDataKey(
                    nonce=stored[:DATA_KEY_NONCE_BYTES],
                    ciphertext=stored[DATA_KEY_NONCE_BYTES:_WRAPPED_KEY_END],
                ),
                associated,
            )
        except DataKeyError:
            raise BlobUnreadable(_NOT_OPENED) from None
        try:
            plaintext = AESGCM(data_key).decrypt(
                stored[_WRAPPED_KEY_END:_BLOB_NONCE_END],
                stored[_BLOB_NONCE_END:],
                associated,
            )
        except InvalidTag:
            raise BlobUnreadable(_NOT_OPENED) from None
        if hashlib.sha256(plaintext).digest() != digest:
            raise BlobUnreadable(_WRONG_ADDRESS)
        return plaintext

    def path_of(self, reference: Any) -> Path:
        """Where ``reference`` addresses, inside this store's root.

        :param reference: the :class:`BlobRef` :meth:`put` answered.
        :returns: the path the blob is written under.  Built from the digest
            and the one suffix, and :class:`BlobRef` has already refused a
            digest that is not 64 hex characters -- so no reference can name
            anything outside the root.
        :raises TypeError: naming the type of ``reference`` and no value.
        """
        return self._path_of(_checked_reference(reference))

    def _path_of(self, reference: BlobRef) -> Path:
        """The file one reference addresses.

        :param reference: a reference, already checked by its own
            ``__post_init__``.
        :returns: the path beside the digest, never a caller-supplied one.
        """
        return self._root / (reference.digest + BLOB_SUFFIX)

    def _sealed(self, payload: bytes, digest: bytes) -> bytes:
        """The bytes one blob's file carries, header first.

        :param payload: the document, already checked to be bytes.
        :param digest: its raw SHA-256, the associated data both halves are
            sealed under.
        :returns: the header beside the sealed document.  Nothing is written
            here, so a caller that fails to write leaves no file behind.
        """
        associated = _associated_data(digest)
        data_key = generate_data_key()
        nonce = secrets.token_bytes(BLOB_NONCE_BYTES)
        wrapped = wrap_data_key(self._master_key, data_key, associated)
        sealed = AESGCM(data_key).encrypt(nonce, payload, associated)
        return wrapped.nonce + wrapped.ciphertext + nonce + sealed


def _associated_data(digest: bytes) -> bytes:
    """What both halves of one blob are sealed under.

    :param digest: the blob's raw SHA-256.
    :returns: the format tag beside the digest, so a blob is bound to the
        address it was written under as well as to the rules that wrote it.
    """
    return BLOB_FORMAT_TAG + digest


def _checked_bytes(value: Any, subject: str) -> bytes:
    """``value`` copied to frozen bytes, or refused by type.

    :param subject: what this serves, named in the refusal.
    :returns: the copy, so a buffer the caller still holds cannot be what
        gets stored.
    :raises TypeError: naming the type and never the value, since every
        value this serves is a document.
    """
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(
            f"{subject} is a {type(value).__name__}, and only bytes may be "
            f"stored as evidence: no value is shown"
        )
    return bytes(value)


def _checked_reference(value: Any) -> BlobRef:
    """``value`` read as a reference, or refused by type.

    :param value: what a caller handed to :meth:`EvidenceStore.get`.
    :returns: the reference, which has already checked its own digest.
    :raises TypeError: naming the type and no value.  Text read out of a
        column is not a reference until it is read as one.
    """
    if isinstance(value, BlobRef):
        return value
    raise TypeError(
        f"a blob reference is a {type(value).__name__}, and only a BlobRef "
        f"may be read or located: no value is shown"
    )


def _checked_master_key(master_key: Any) -> MasterKey:
    """A ``MasterKey``, or the argument refused by type.

    :param master_key: what :func:`app.storage.master_key.load_master_key`
        answered.
    :returns: the key, unchanged.
    :raises TypeError: naming the type and no value, so the bytes off a
        ``MasterKey`` attribute cannot be handed here instead of the object
        that checked them.
    """
    if not isinstance(master_key, MasterKey):
        raise TypeError(
            f"a master key is a {type(master_key).__name__}, and only a "
            f"MasterKey may open a blob: no value is shown"
        )
    return master_key


def _written_atomically(target: Path, body: bytes) -> None:
    """``body`` written to ``target`` whole or not at all.

    :param target: the file the blob's address names.
    :param body: the header and the sealed document.
    :returns: nothing.
    """
    handle, temporary = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name, suffix=".partial"
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
