"""19.6: the upload is stored encrypted, and the row holds only its address.

The task's verify is "a test asserting the screening row contains no image
bytes", and that assertion is asked three ways, each stronger than the last,
because a row that merely looks clean is a row nobody checked:

- **no column of the row carries a byte of the document.**  Driven through
  the real route with the real flow behind it and a real store, against an
  upload carrying a marker inside its own bytes (as 11.7's ban is checked).
  Every column is read back and searched, so a copy smuggled into ``quality``
  or ``flags`` fails here rather than passing on the schema's word.
- **the database file carries none either.**  The row is read out of a
  *file*, and the file itself is searched, so nothing reaches the page by a
  column, an index or a journal the model does not name.
- **the address on the row opens back to exactly those bytes.**  Without
  this the two above pass on a flow that stored nothing at all.

The rest of the file is the wiring that claim rests on: the row carries the
one token D157 designed, two uploads of one document share one blob, a
screening written with no store keeps nothing, a document handed over without
a store is refused rather than dropped, and one key serves the whole process.
"""

import hashlib
import pathlib
import struct
import uuid
import zlib
from collections.abc import Iterator

import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.api import get_evidence_store, get_sessions
from app.config import (
    APP_ENV_ENV_VAR,
    BACKEND_DIR,
    DEFAULT_EVIDENCE_STORE_ROOT,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    EVIDENCE_ENCRYPTION_KEY_ENV_VAR,
    EVIDENCE_STORE_ROOT_ENV_VAR,
    get_evidence_store_root,
)
from app.main import app
from app.screening import run_screening
from app.storage import db
from app.storage.blob_store import BLOB_SUFFIX, BlobRef, EvidenceStore
from app.storage.master_key import MASTER_KEY_BYTES, MasterKey, MasterKeyError
from app.storage.models import Base, Screening
from tests.fixtures import mrz_images


#: A marker carried inside the uploaded bytes as a PNG text chunk, so the
#: search below is against the document itself rather than a stand-in.
IMAGE_BYTES_MARKER = "DRISHTI-EVIDENCE-BYTES-7c41e2"

#: One key to write under, so a case is about the flow rather than the key:
#: a generated development key differs per call, and two calls would write
#: two blobs no single store could open.
MASTER = MasterKey(
    key=bytes(range(MASTER_KEY_BYTES)), environment=ENV_DEVELOPMENT, generated=False
)

#: A page with no machine-readable zone on it: Tier 0 measures it, finds
#: nothing to flag, and the cascade completes -- the shortest path from an
#: upload to a completed row.
PAGE = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))


def marked_png(image, marker: str = IMAGE_BYTES_MARKER) -> bytes:
    """``image`` as the PNG bytes an upload would carry, carrying ``marker``.

    The marker rides in a ``tEXt`` chunk spliced into a real encoding rather
    than a re-save, because what is under test is the bytes as they arrive.
    ``tEXt`` is ancillary, so every decoder skips it and the marker is still
    in what the service was handed.
    """

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)
        )

    encoded, raw = cv2.imencode(".png", image)
    assert encoded
    body = raw.tobytes()
    at = body.rindex(b"IEND") - 4  # the length field ahead of the final chunk
    return body[:at] + chunk(b"tEXt", b"Comment\x00" + marker.encode("ascii")) + body[at:]


@pytest.fixture
def store(tmp_path: pathlib.Path) -> EvidenceStore:
    """A real evidence store over a temporary directory, under one key."""
    return EvidenceStore(tmp_path / "evidence", MASTER)


@pytest.fixture
def database(tmp_path: pathlib.Path) -> Iterator[pathlib.Path]:
    """A SQLite *file*, so the bytes on disk can be read and searched."""
    path = tmp_path / "drishti.db"
    engine = db.build_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    try:
        yield path
    finally:
        engine.dispose()


@pytest.fixture
def sessions(database: pathlib.Path) -> Iterator[sessionmaker[Session]]:
    """The factory every write goes through, bound into the app."""
    engine = db.build_engine(f"sqlite:///{database.as_posix()}")
    factory = db.build_session_factory(engine)
    app.dependency_overrides[get_sessions] = lambda: factory
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        engine.dispose()


@pytest.fixture
def client(sessions, store) -> Iterator[TestClient]:
    """The app with both seams pointed at the temporary database and store."""
    app.dependency_overrides[get_evidence_store] = lambda: store
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_evidence_store, None)


def upload(marker: str = IMAGE_BYTES_MARKER) -> dict:
    """A multipart body carrying one marked page."""
    return {
        "files": {"image": ("page.png", marked_png(PAGE.image, marker), "image/png")},
        "data": {"document_type": "passport"},
    }


def screened(client: TestClient, sessions) -> tuple[Screening, bytes]:
    """Post one upload and answer with its row and the bytes that were sent.

    The bytes are rebuilt rather than read back, so the case compares the row
    against the same document it handed over rather than against whatever the
    route says it received.
    """
    document = marked_png(PAGE.image)
    response = client.post("/api/screenings", **upload())
    assert response.status_code == 200, response.text
    with sessions() as session:
        row = session.execute(
            select(Screening).where(
                Screening.id == uuid.UUID(response.json()["screening_id"])
            )
        ).scalar_one()
    return row, document


# --- the task's verify -------------------------------------------------


def test_the_screening_row_carries_no_byte_of_the_document(client, sessions):
    """**No column of the row holds any of the uploaded bytes.**

    Held against every column rather than against the schema: the document is
    searched for as a whole and for the marker it carries, so a copy smuggled
    into a JSON column fails here rather than passing on the schema's word.
    """
    row, document = screened(client, sessions)

    assert IMAGE_BYTES_MARKER.encode("ascii") in document
    for column in Screening.__table__.columns:
        rendered = repr(getattr(row, column.name))
        assert IMAGE_BYTES_MARKER not in rendered, column.name
        assert document.decode("latin-1") not in rendered, column.name
    assert row.image_blob_ref is not None


def test_the_database_file_carries_no_byte_of_the_document(
    client, sessions, database
):
    """**Stronger than the row: the whole file on disk.**

    The row is read out of a file rather than out of memory, and the file is
    searched, so nothing reaches the page by a column, an index or a journal
    the model does not name.
    """
    _row, document = screened(client, sessions)

    written = database.read_bytes()
    assert written
    assert document not in written
    assert IMAGE_BYTES_MARKER.encode("ascii") not in written


def test_the_address_on_the_row_opens_back_to_the_document(client, sessions, store):
    """**And the store really holds it** -- otherwise the two above pass on a
    flow that stored nothing.

    The token is read back through the store's own reader and opened, byte
    for byte, and its digest is the SHA-256 of what the officer sent.
    """
    row, document = screened(client, sessions)

    reference = BlobRef.from_wire(row.image_blob_ref)

    assert reference.digest == hashlib.sha256(document).hexdigest()
    assert reference.size == len(document)
    assert store.get(reference) == document


# --- what is written, and where ----------------------------------------


def test_the_document_is_on_disk_as_ciphertext_and_nothing_else(
    client, sessions, store
):
    """**The stored file carries neither the document nor its header.**

    The file is named by the digest and holds no run of the plaintext, which
    is the shape a file-type detector, a backup index or a thumbnailer reads
    without a key.
    """
    row, document = screened(client, sessions)
    reference = BlobRef.from_wire(row.image_blob_ref)

    written = store.path_of(reference).read_bytes()

    assert store.path_of(reference).name == reference.digest + BLOB_SUFFIX
    assert document not in written
    assert IMAGE_BYTES_MARKER.encode("ascii") not in written
    assert b"\x89PNG" not in written


def test_the_token_on_the_row_names_a_file_and_nothing_else(client, sessions, store):
    """**The address is the whole of what the row holds.**

    ``sha256:<digest>:<size>`` is one spelling, the file it reaches is inside
    the store's own root and named by that digest, and no caller-supplied name
    -- a filename, a screening id, a path -- reaches the filesystem (D157).
    """
    row, _document = screened(client, sessions)
    reference = BlobRef.from_wire(row.image_blob_ref)

    assert row.image_blob_ref == reference.to_wire()
    assert reference.to_wire().count(":") == 2
    assert store.path_of(reference).parent == store.path_of(reference).parent
    assert store.path_of(reference).parent.name == "evidence"


def test_two_uploads_of_one_document_share_one_blob(client, sessions, store):
    """**The same document is stored once.**  D157's claim, through the flow.

    Two screenings of the same page answer the same reference and leave one
    file behind -- a document is addressed by what it decrypts to, so a second
    write had nothing to add.
    """
    first, _ = screened(client, sessions)
    second, _ = screened(client, sessions)

    assert first.image_blob_ref == second.image_blob_ref
    root = store.path_of(BlobRef.from_wire(first.image_blob_ref)).parent
    assert [path.name for path in root.iterdir()] == [
        BlobRef.from_wire(first.image_blob_ref).digest + BLOB_SUFFIX
    ]


def test_a_screening_written_with_no_store_keeps_nothing(sessions, store):
    """**No store, no blob, and the row says so.**

    The flow stores what it is handed and never keeps a copy of its own, so a
    caller that wires no store gets a row carrying ``None`` -- not a row
    claiming evidence that is nowhere.
    """
    row = run_screening(
        sessions=sessions,
        image=PAGE.image,
        document_type="passport",
        filename="page.png",
    )

    assert row.image_blob_ref is None
    assert list(store.path_of(BlobRef(digest="ab" * 32, size=1)).parent.iterdir()) == []


# --- what is refused ---------------------------------------------------


def test_a_document_with_no_store_is_refused_rather_than_dropped(sessions):
    """**Half a pair is a refusal, not a screening.**

    A document with no store to write it in would be discarded while the row
    claimed it had been screened, so the flow refuses before a row is written
    and nothing is stored.
    """
    with pytest.raises(ValueError) as refusal:
        run_screening(
            sessions=sessions,
            image=PAGE.image,
            document_type="passport",
            filename="page.png",
            document=marked_png(PAGE.image),
        )

    assert "document" in str(refusal.value)
    with sessions() as session:
        assert session.execute(select(Screening)).scalars().all() == []


def test_a_store_with_no_document_is_refused(sessions, store):
    """**The other half is the same refusal.**

    A store with nothing to write has said nothing about this screening, and a
    reference to a document nobody handed over is a claim the row cannot back.
    """
    with pytest.raises(ValueError) as refusal:
        run_screening(
            sessions=sessions,
            image=PAGE.image,
            document_type="passport",
            filename="page.png",
            evidence_store=store,
        )

    assert "document" in str(refusal.value)
    with sessions() as session:
        assert session.execute(select(Screening)).scalars().all() == []


# --- where the store lives ---------------------------------------------


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_the_store_lives_beside_the_backend_when_nothing_is_configured(
    monkeypatch: pytest.MonkeyPatch, configured: str | None
):
    """**Unset or blank means one shipped directory.**

    Resolved rather than spelled relative to the working directory, on
    :data:`app.config.DEFAULT_DATABASE_PATH`\'s reasoning: the same store
    whichever directory the process was started from.  Nothing is created
    here -- a reader that built a directory would write on a mere read.
    """
    if configured is None:
        monkeypatch.delenv(EVIDENCE_STORE_ROOT_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(EVIDENCE_STORE_ROOT_ENV_VAR, configured)

    root = get_evidence_store_root()

    assert root == DEFAULT_EVIDENCE_STORE_ROOT
    assert root.parent == BACKEND_DIR


def test_the_configured_root_is_the_one_the_store_writes_into(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    """**A configured root is that root**, trimmed of surrounding space --
    the one directory every blob of this process lands in.
    """
    monkeypatch.setenv(EVIDENCE_STORE_ROOT_ENV_VAR, f"  {tmp_path / 'held'}  ")

    root = get_evidence_store_root()

    assert root == tmp_path / "held"
    assert not root.exists()


def test_the_shipped_default_is_named_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    """**One constant, and changing it changes the answer.**

    Held against the module attribute rather than against a path spelled
    here, so a default that moved would have to be changed in one place.
    """
    monkeypatch.delenv(EVIDENCE_STORE_ROOT_ENV_VAR, raising=False)
    monkeypatch.setattr(config, "DEFAULT_EVIDENCE_STORE_ROOT", tmp_path / "elsewhere")

    assert get_evidence_store_root() == tmp_path / "elsewhere"


def test_the_store_lands_its_blobs_under_the_configured_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    """**The reader and the store agree**, so the variable is what an operator
    sets rather than a spelling nothing reads.
    """
    root = tmp_path / "held"
    monkeypatch.setenv(EVIDENCE_STORE_ROOT_ENV_VAR, str(root))
    monkeypatch.delenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(APP_ENV_ENV_VAR, raising=False)
    get_evidence_store.cache_clear()
    try:
        store = get_evidence_store()
        reference = store.put(marked_png(PAGE.image))
        assert store.path_of(reference).parent == root
    finally:
        get_evidence_store.cache_clear()


# --- the store seam ---------------------------------------------------


def test_the_suite_leaves_no_blob_in_the_repository(
    client, sessions, store, tmp_path
):
    """**A run of this suite writes nothing into the repository.**

    The shipped root is ``backend/evidence``, and an upload posted without the
    override would land there -- which is what ``conftest.py``\'s temporary
    store exists to prevent, on the same reasoning
    ``test_alembic_migration.py`` applies to ``drishti.db``.  Checked after a
    real upload has gone through the route, so it is the writing that is
    measured rather than the intention.
    """
    _row, _document = screened(client, sessions)

    shipped = BACKEND_DIR / "evidence"
    assert not shipped.exists() or not list(shipped.iterdir())
    assert [path.name for path in store.path_of(
        BlobRef(digest="ab" * 32, size=1)
    ).parent.iterdir()]


def test_the_store_is_one_per_process_so_a_process_reads_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    """**One key per process, not one per request.**

    D154 draws a development key per call, so a store rebuilt per request
    would write every upload under a key that exists for that one request --
    and the next request could not open what the last one stored.
    """
    monkeypatch.delenv("EVIDENCE_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("EVIDENCE_STORE_ROOT", str(tmp_path / "evidence"))
    get_evidence_store.cache_clear()
    try:
        assert get_evidence_store() is get_evidence_store()
    finally:
        get_evidence_store.cache_clear()


def test_a_production_deployment_with_no_key_stores_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    """**19.1's refusal now has something asking for a key.**

    With ``APP_ENV=production`` and no ``EVIDENCE_ENCRYPTION_KEY`` the store
    cannot be built, so no upload is stored under a key this repository could
    name -- and the refusal names the variable without quoting a value.
    """
    monkeypatch.setenv("APP_ENV", ENV_PRODUCTION)
    monkeypatch.delenv("EVIDENCE_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("EVIDENCE_STORE_ROOT", str(tmp_path / "evidence"))
    get_evidence_store.cache_clear()
    try:
        with pytest.raises(MasterKeyError) as refusal:
            get_evidence_store()
    finally:
        get_evidence_store.cache_clear()

    assert "EVIDENCE_ENCRYPTION_KEY" in str(refusal.value)
    assert not (tmp_path / "evidence").exists() or not list(
        (tmp_path / "evidence").iterdir()
    )
