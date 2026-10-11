"""19.7: a retention window per record class, and a purge that deletes.

The claim is that a purge removes a document: an expired blob is gone from
disk and its reference answers :class:`~app.storage.blob_store.BlobNotFound`
rather than opening, a blob still inside the window is untouched, and a file
in the root that is not named like a blob survives however old it is.

**The window is the configuration, and the configuration refuses.**  A class
this service does not retain, a window that is not a whole number of days, a
window of zero, the same class named twice -- and a window set for the audit
trail, the one promise a purge cannot keep -- are each refused by name
rather than read as something else.

**Nothing here is a claim about the clock.**  Every case passes the instant
the window is measured from and stamps the files it wrote, so what is
asserted is the comparison and not the hour the suite ran in.

**A sweep is idempotent and it says what it removed** (19.8).  Run twice over
one store, the second answers nothing deleted and the first answer is
unchanged; a blob another sweep took between the listing and here is not
named a second time; one line per sweep carries the window enforced and every
digest it removed, with the event name as the message and nothing formatted
into it; and a sweep beside a migrated ledger leaves every ledger entry
exactly as it was, ten years old or not.
"""

import inspect
import io
import json
import logging
import os
import pathlib
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.config import (
    DEFAULT_RETENTION_DAYS,
    ENV_DEVELOPMENT,
    NEVER_PURGED_RECORD_CLASSES,
    PURGEABLE_RECORD_CLASSES,
    RECORD_CLASS_AUDIT_EVENTS,
    RECORD_CLASS_EVIDENCE,
    RECORD_CLASS_LEDGER_ENTRIES,
    RECORD_CLASSES,
    RETENTION_DAYS_ENV_VAR,
    get_retention_days,
)
from app.ledger.store import SqliteLedger
from app.logging_config import APP_LOGGER_NAME, JsonFormatter
from app.storage import db, retention
from app.storage.blob_store import (
    BLOB_DIGEST_HEX_CHARS,
    BLOB_SUFFIX,
    BlobNotFound,
    BlobRef,
    EvidenceStore,
)
from app.storage.master_key import MASTER_KEY_BYTES, MasterKey
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    LEDGER_ENTRY_TABLE_NAME,
    SCREENING_TABLE_NAME,
    LedgerEntry,
)
from app.storage.retention import (
    PURGE_LOG_EVENT,
    PurgeResult,
    purge_expired_evidence,
)

#: One master key to write under, so a case is about retention and not about
#: encryption.
MASTER = MasterKey(
    key=bytes(range(MASTER_KEY_BYTES)), environment=ENV_DEVELOPMENT, generated=False
)

#: The instant every window is measured from.  A case that named the real
#: clock would be a claim about the hour the suite happened to run in.
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)

#: How long a window most cases enforce, in whole days.
WINDOW = 30

#: The alembic configuration this service migrates with, derived from this
#: file for the reason `test_ledger_store.py` gives.
ALEMBIC_INI = pathlib.Path(__file__).resolve().parents[2] / "alembic.ini"

#: A root and a signature in the spellings the ledger stores verbatim, so the
#: entries below are shaped like the ones 9.16 writes.
A_ROOT = "7c9f" * 16
A_SIGNATURE = "3f" * 64

#: Every column the ledger entry declares, so a column added later is also a
#: column the snapshot in `_ledger_rows` reads.
LEDGER_ENTRY_COLUMNS = tuple(LedgerEntry.__table__.columns)


def _store(root: pathlib.Path) -> EvidenceStore:
    """A store over root, under the one master key."""
    return EvidenceStore(root, MASTER)


def _written_at(
    store: EvidenceStore, document: bytes, *, older_than: timedelta
) -> BlobRef:
    """`document` put into `store` and its file stamped `older_than` back.

    :param store: the store to write into.
    :param document: the bytes to store; what they are is a case business.
    :param older_than: how far before :data:`NOW` the file last write is put.
    :returns: the reference the document is stored under.
    """
    reference = store.put(document)
    stamp = (NOW - older_than).timestamp()
    os.utime(store.path_of(reference), (stamp, stamp))
    return reference


def test_a_purge_deletes_a_blob_past_its_window(tmp_path: pathlib.Path) -> None:
    """The claim this task makes: the file is gone, and the store says so."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))
    fresh = _written_at(store, b"a document inside its window", older_than=timedelta(days=1))

    result = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert result == PurgeResult(deleted=(expired.digest,), kept=1)
    assert not store.path_of(expired).exists()
    with pytest.raises(BlobNotFound):
        store.get(expired)
    assert store.path_of(fresh).exists()
    assert store.get(fresh) == b"a document inside its window"


def test_a_blob_exactly_at_its_window_is_kept_and_one_second_past_it_is_not(
    tmp_path: pathlib.Path,
) -> None:
    """The window is a boundary and not a moment, so both sides are pinned."""
    store = _store(tmp_path / "evidence")
    at = _written_at(store, b"written at the window", older_than=timedelta(days=WINDOW))
    past = _written_at(
        store, b"written a second past the window", older_than=timedelta(days=WINDOW, seconds=1)
    )

    result = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert result.deleted == (past.digest,)
    assert store.path_of(at).exists()
    assert store.get(at) == b"written at the window"


def test_a_purge_leaves_every_file_that_is_not_named_like_a_blob(
    tmp_path: pathlib.Path,
) -> None:
    """A window names documents, so nothing beside the blobs is reachable."""
    root = tmp_path / "evidence"
    store = _store(root)
    reference = _written_at(store, b"one document inside its window", older_than=timedelta(days=1))
    partial = root / (reference.digest + BLOB_SUFFIX + "3f9.partial")
    partial.write_bytes(b"half a blob")
    (root / "README").write_text("not a blob", encoding="utf-8")
    unescaped = root / ("e" * BLOB_DIGEST_HEX_CHARS + "Xblob")
    unescaped.write_bytes(b"a name that is not the suffix")
    backup = root / (reference.digest + BLOB_SUFFIX + ".bak")
    backup.write_bytes(b"a backup of a blob")
    nested = root / "nested"
    nested.mkdir()
    restore = root / ("d" * BLOB_DIGEST_HEX_CHARS + BLOB_SUFFIX)
    restore.mkdir()
    (nested / ("a" * BLOB_DIGEST_HEX_CHARS + BLOB_SUFFIX)).write_bytes(b"not reached")
    old = (NOW - timedelta(days=3650)).timestamp()
    beside = nested / ("a" * BLOB_DIGEST_HEX_CHARS + BLOB_SUFFIX)
    for path in (partial, root / "README", beside, restore, unescaped, backup):
        os.utime(path, (old, old))

    result = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert result == PurgeResult(deleted=(), kept=1)
    assert store.path_of(reference).exists()
    assert partial.exists()
    assert (root / "README").exists()
    assert beside.exists()
    assert restore.is_dir()
    assert unescaped.exists()
    assert backup.exists()


def test_a_purge_reports_a_digest_and_no_path(tmp_path: pathlib.Path) -> None:
    """What is reported is what a document is named by, and nothing of it."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))

    result = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert list(result.deleted) == [expired.digest]
    for digest in result.deleted:
        assert len(digest) == BLOB_DIGEST_HEX_CHARS
        assert all(character in "0123456789abcdef" for character in digest)
        assert os.sep not in digest
        assert BLOB_SUFFIX not in digest


def test_a_purge_reads_its_window_from_the_configured_evidence_class(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment is read in one module, so the purge asks for it."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "evidence=2")
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"three days old", older_than=timedelta(days=3))
    fresh = _written_at(store, b"one day old", older_than=timedelta(days=1))

    result = purge_expired_evidence(store, now=NOW)

    assert result.deleted == (expired.digest,)
    assert store.path_of(fresh).exists()


def test_a_purge_of_an_empty_store_answers_nothing_deleted(
    tmp_path: pathlib.Path,
) -> None:
    """There is nothing to expire, and the answer says so rather than failing."""
    store = _store(tmp_path / "evidence")

    assert purge_expired_evidence(store, retention_days=WINDOW, now=NOW) == PurgeResult(
        deleted=(), kept=0
    )


def test_the_window_is_the_default_for_every_class_when_nothing_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset and blank are both what `.env.example` ships."""
    monkeypatch.delenv(RETENTION_DAYS_ENV_VAR, raising=False)
    assert get_retention_days() == DEFAULT_RETENTION_DAYS

    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "   ")
    assert get_retention_days() == DEFAULT_RETENTION_DAYS


def test_one_configured_class_changes_nothing_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A class the operator names is answered, and the rest keep the default."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "evidence=30")
    windows = get_retention_days()

    assert windows[RECORD_CLASS_EVIDENCE] == 30
    assert windows[RECORD_CLASS_AUDIT_EVENTS] is None
    assert windows[RECORD_CLASS_LEDGER_ENTRIES] is None


def test_a_window_is_read_whatever_the_spacing_around_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spacing is trimmed rather than refused, and a blank pair is ignored."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "  evidence = 45 , , ")

    assert get_retention_days()[RECORD_CLASS_EVIDENCE] == 45


def test_a_retention_setting_that_is_not_class_equals_days_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A value with no class in it names no window, so it is refused."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "evidence30")

    with pytest.raises(ValueError) as failure:
        get_retention_days()

    assert RETENTION_DAYS_ENV_VAR in str(failure.value)
    assert "class=days" in str(failure.value)


def test_an_unknown_record_class_is_refused_and_the_names_are_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A class this service does not retain must not expire anything."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "screens=30")

    with pytest.raises(ValueError) as failure:
        get_retention_days()

    message = str(failure.value)
    assert "screens" in message
    for record_class in RECORD_CLASSES:
        assert record_class in message


def test_the_same_record_class_named_twice_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two windows for one class would be read as whichever was written last."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, "evidence=30,evidence=60")

    with pytest.raises(ValueError) as failure:
        get_retention_days()

    assert RETENTION_DAYS_ENV_VAR in str(failure.value)


@pytest.mark.parametrize("written", ["soon", "30.5", "", "thirty"])
def test_a_window_that_is_not_a_whole_number_of_days_is_refused(
    monkeypatch: pytest.MonkeyPatch, written: str
) -> None:
    """A window nobody can measure a document against is refused by name."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, f"evidence={written}")

    with pytest.raises(ValueError) as failure:
        get_retention_days()

    assert RECORD_CLASS_EVIDENCE in str(failure.value)


@pytest.mark.parametrize("written", ["0", "-1"])
def test_a_window_below_one_day_is_refused(
    monkeypatch: pytest.MonkeyPatch, written: str
) -> None:
    """Zero expires a document the moment it is stored, which is not a window."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, f"evidence={written}")

    with pytest.raises(ValueError) as failure:
        get_retention_days()

    assert RETENTION_DAYS_ENV_VAR in str(failure.value)


@pytest.mark.parametrize(
    "record_class", [RECORD_CLASS_AUDIT_EVENTS, RECORD_CLASS_LEDGER_ENTRIES]
)
def test_a_window_for_the_audit_trail_is_refused(
    monkeypatch: pytest.MonkeyPatch, record_class: str
) -> None:
    """A window no purge could keep is a promise, so it is refused not read."""
    monkeypatch.setenv(RETENTION_DAYS_ENV_VAR, f"{record_class}=1")

    with pytest.raises(ValueError) as failure:
        get_retention_days()

    assert record_class in str(failure.value)


def test_the_classes_are_the_purgeable_ones_and_the_never_ones() -> None:
    """The evidence class is a whole number of days, and the audit trail is not."""
    assert RECORD_CLASSES == PURGEABLE_RECORD_CLASSES + NEVER_PURGED_RECORD_CLASSES
    assert PURGEABLE_RECORD_CLASSES == (RECORD_CLASS_EVIDENCE,)
    window = DEFAULT_RETENTION_DAYS[RECORD_CLASS_EVIDENCE]
    assert isinstance(window, int) and window >= 1
    for record_class in NEVER_PURGED_RECORD_CLASSES:
        assert DEFAULT_RETENTION_DAYS[record_class] is None


def test_the_answer_is_a_fresh_mapping_on_every_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing a caller does to the answer is what the next call reads."""
    monkeypatch.delenv(RETENTION_DAYS_ENV_VAR, raising=False)
    first = get_retention_days()
    first[RECORD_CLASS_EVIDENCE] = 999

    assert get_retention_days()[RECORD_CLASS_EVIDENCE] != 999
    assert DEFAULT_RETENTION_DAYS[RECORD_CLASS_EVIDENCE] != 999


def test_a_purge_result_that_is_not_the_shape_a_purge_answers_is_refused() -> None:
    """The answer is a value other modules read, so it refuses being faked."""
    with pytest.raises(TypeError) as failure:
        PurgeResult(deleted=["a"], kept=0)
    assert "tuple of digests" in str(failure.value)

    with pytest.raises(TypeError) as failure:
        PurgeResult(deleted=(), kept=True)
    assert "whole number of blobs" in str(failure.value)


def test_the_store_to_purge_is_refused_by_type(tmp_path: pathlib.Path) -> None:
    """A directory is not a store, and a sweep of one would be a guess."""
    with pytest.raises(TypeError) as failure:
        purge_expired_evidence(tmp_path, retention_days=WINDOW, now=NOW)

    assert "EvidenceStore" in str(failure.value)


@pytest.mark.parametrize("window", [True, 30.5, "30"])
def test_a_window_the_caller_passes_is_refused_by_type(
    tmp_path: pathlib.Path, window: object
) -> None:
    """`bool` is an `int`, and True is not one day.

    `None` is not in this list: it is what a purge reads the configured
    window out of, so it is the default rather than a refusal.
    """
    store = _store(tmp_path / "evidence")

    with pytest.raises(TypeError) as failure:
        purge_expired_evidence(store, retention_days=window, now=NOW)

    assert "retention window" in str(failure.value)


def test_a_window_below_one_day_is_refused_by_the_purge(tmp_path: pathlib.Path) -> None:
    """The refusal belongs in the module that would act on the window too."""
    store = _store(tmp_path / "evidence")

    with pytest.raises(ValueError) as failure:
        purge_expired_evidence(store, retention_days=0, now=NOW)

    assert "0 days" in str(failure.value)


def test_an_instant_without_a_timezone_is_refused(tmp_path: pathlib.Path) -> None:
    """A naive instant cannot be compared with the UTC stamp of a file."""
    store = _store(tmp_path / "evidence")

    with pytest.raises(ValueError) as failure:
        purge_expired_evidence(store, retention_days=WINDOW, now=datetime(2026, 10, 3))

    assert "timezone" in str(failure.value)


def test_an_instant_that_is_not_a_datetime_is_refused(tmp_path: pathlib.Path) -> None:
    """A number is not an instant, whatever it counts."""
    store = _store(tmp_path / "evidence")

    with pytest.raises(TypeError) as failure:
        purge_expired_evidence(store, retention_days=WINDOW, now=NOW.timestamp())

    assert "datetime" in str(failure.value)


def test_a_purge_measures_from_the_clock_when_no_instant_is_passed(
    tmp_path: pathlib.Path,
) -> None:
    """The default is the UTC clock, and a window of one day still expires."""
    store = _store(tmp_path / "evidence")
    old = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    reference = store.put(b"written two days ago")
    os.utime(store.path_of(reference), (old, old))

    result = purge_expired_evidence(store, retention_days=1)

    assert result.deleted == (reference.digest,)
@pytest.fixture
def logged() -> Iterator[Callable[[], list[dict]]]:
    """Drain every line the `app` logger wrote, parsed as JSON."""

    def drain() -> list[dict]:
        return [
            json.loads(line)
            for line in stream.getvalue().splitlines()
            if line.strip()
        ]

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(APP_LOGGER_NAME)
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield drain
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


def _url_for(database: pathlib.Path) -> str:
    """The URL naming `database`, in the spelling 9.11 uses."""
    return f"sqlite:///{database.as_posix()}"


def _appended(database: pathlib.Path, anchored_at: datetime, count: int) -> tuple[LedgerEntry, ...]:
    """`count` ledger entries appended over `database`, all stamped long ago."""

    def append(ledger: SqliteLedger, index: int) -> LedgerEntry:
        return ledger.append_batch(
            batch_id=uuid.uuid4(),
            merkle_root=A_ROOT,
            signature=A_SIGNATURE,
            anchored_at=anchored_at + timedelta(seconds=index),
        )

    engine = db.build_engine(_url_for(database))
    try:
        ledger = SqliteLedger(db.build_session_factory(engine))
        return tuple(append(ledger, index) for index in range(count))
    finally:
        engine.dispose()


def _ledger_rows(database: pathlib.Path) -> tuple[tuple[object, ...], ...]:
    """Every column of every ledger entry, in the order the log holds them."""
    engine = db.build_engine(_url_for(database))
    try:
        sessions = db.build_session_factory(engine)
        with sessions() as session:
            entries = session.execute(
                select(LedgerEntry).order_by(LedgerEntry.sequence)
            ).scalars()
            return tuple(
                tuple(getattr(entry, column.name) for column in LEDGER_ENTRY_COLUMNS)
                for entry in entries
            )
    finally:
        engine.dispose()


def _purge_lines(logged: Callable[[], list[dict]]) -> list[dict]:
    """The lines of this file`s own event, and nothing else the suite logged."""
    return [line for line in logged() if line["message"] == PURGE_LOG_EVENT]


def test_a_second_purge_over_one_store_deletes_nothing(tmp_path: pathlib.Path) -> None:
    """The claim 19.8 makes: a repeated sweep answers not what the first did."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))
    fresh = _written_at(store, b"a document inside its window", older_than=timedelta(days=1))

    first = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)
    second = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)
    third = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert first == PurgeResult(deleted=(expired.digest,), kept=1)
    assert second == third == PurgeResult(deleted=(), kept=1)
    assert not set(first.deleted) & set(second.deleted)
    assert not store.path_of(expired).exists()
    assert store.get(fresh) == b"a document inside its window"


def test_a_purge_of_a_store_holding_nothing_expired_answers_the_same_twice(
    tmp_path: pathlib.Path,
) -> None:
    """A sweep with nothing to remove is already the answer a second sweep gives."""
    store = _store(tmp_path / "evidence")

    assert purge_expired_evidence(store, retention_days=WINDOW, now=NOW) == (
        purge_expired_evidence(store, retention_days=WINDOW, now=NOW)
    )


def test_a_blob_another_sweep_took_is_not_named_a_second_time(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A digest is reported for the run that removed the file, and no other."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))
    taken = store.path_of(expired)
    taken.unlink()
    monkeypatch.setattr(EvidenceStore, "blob_paths", lambda self: (taken,))

    result = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert result == PurgeResult(deleted=(), kept=0)


def test_a_blob_that_vanishes_between_its_stamp_and_the_unlink_is_not_a_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sweep beside another sweep reads a file that is gone by the unlink."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))
    taken = store.path_of(expired)

    class _Vanishing(type(taken)):
        """A blob path stamped twice: gone before the sweep unlinks it.

        The lookup behind `is_file() is the first stamp; the sweep`s own is
        the second, and the file goes between the two.
        """

        def __init__(self, other: pathlib.Path) -> None:
            super().__init__(other)
            self.stamps = 0

        def stat(self, *, follow_symlinks: bool = True):
            self.stamps += 1
            stamp = super().stat(follow_symlinks=follow_symlinks)
            if self.stamps > 1:
                self.unlink()
            return stamp

    monkeypatch.setattr(EvidenceStore, "blob_paths", lambda self: (_Vanishing(taken),))

    result = purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    assert result == PurgeResult(deleted=(expired.digest,), kept=0)
    assert not taken.exists()


def test_the_event_name_is_the_one_a_log_query_reads() -> None:
    """A rename changes what a saved query finds, so the spelling is pinned."""
    assert PURGE_LOG_EVENT == "evidence_purge"


def test_a_purge_logs_the_window_and_every_digest_it_removed(
    tmp_path: pathlib.Path, logged: Callable[[], list[dict]]
) -> None:
    """The log is what says what went, so it is asked in full."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))
    fresh = _written_at(store, b"a document inside its window", older_than=timedelta(days=1))

    purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    lines = _purge_lines(logged)
    assert len(lines) == 1
    (line,) = lines
    assert line["level"] == "INFO"
    assert line["logger"] == retention.__name__
    assert line["retention_days"] == WINDOW
    assert line["deleted"] == [expired.digest]
    assert line["deleted_count"] == 1
    assert line["kept"] == 1
    assert expired.digest not in line["message"]


def test_a_second_purge_logs_a_sweep_that_removed_nothing(
    tmp_path: pathlib.Path, logged: Callable[[], list[dict]]
) -> None:
    """Both sweeps are on the record, and the second names no digest."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))

    purge_expired_evidence(store, retention_days=WINDOW, now=NOW)
    purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    first, second = _purge_lines(logged)
    assert first["deleted"] == [expired.digest]
    assert second["deleted"] == []
    assert second["deleted_count"] == 0
    assert second["kept"] == 0
    assert expired.digest not in json.dumps(second)


def test_a_purge_line_carries_no_document_in_it(
    tmp_path: pathlib.Path, logged: Callable[[], list[dict]]
) -> None:
    """The message is the event name, so nothing a sweep removed is in a line."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))

    purge_expired_evidence(store, retention_days=WINDOW, now=NOW)

    lines = logged()
    assert lines, "a sweep that deleted a document logged nothing at all"
    for line in lines:
        assert "an expired document" not in json.dumps(line)


def test_a_purge_never_touches_a_ledger_entry(tmp_path: pathlib.Path) -> None:
    """The window is a day; the entries are ten years old and stay as they are."""
    store = _store(tmp_path / "evidence")
    expired = _written_at(store, b"an expired document", older_than=timedelta(days=31))
    database = tmp_path / "ledger.db"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", _url_for(database))
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
    appended = _appended(database, NOW - timedelta(days=3650), 3)
    before = _ledger_rows(database)

    first = purge_expired_evidence(store, retention_days=1, now=NOW)
    second = purge_expired_evidence(store, retention_days=1, now=NOW)

    assert first == PurgeResult(deleted=(expired.digest,), kept=0)
    assert second == PurgeResult(deleted=(), kept=0)
    assert len(before) == len(appended) == 3
    assert min(NOW - entry.anchored_at for entry in appended) > timedelta(days=365)
    assert before == _ledger_rows(database)


def test_a_purge_takes_no_session_and_names_no_table() -> None:
    """A module that cannot reach a row cannot remove one, or amend one."""
    source = inspect.getsource(retention)

    assert "sqlalchemy" not in source
    assert "Session" not in source
    for table in (LEDGER_ENTRY_TABLE_NAME, AUDIT_EVENT_TABLE_NAME, SCREENING_TABLE_NAME):
        assert table not in source