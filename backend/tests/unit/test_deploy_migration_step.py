"""26.5: the deploy step migrates, and the SQLite demo path still works.

The static cases read `docker-entrypoint.sh` and the Dockerfile, so the claim is
decidable with no Docker daemon. The live cases run the entrypoint's own
alembic command as a subprocess, then read and write the file it migrated
through `app.storage`, which is what a local demo does.
"""

import json
import os
import pathlib
import subprocess
import sys

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select

from app import config
from app.config import BACKEND_DIR
from app.storage import db
from app.storage.models import (
    AUDIT_EVENT_TABLE_NAME,
    LEDGER_ENTRY_TABLE_NAME,
    SCREENING_TABLE_NAME,
    TRAVELER_CASE_TABLE_NAME,
    Screening,
)


ENTRYPOINT = BACKEND_DIR / "docker-entrypoint.sh"
DOCKERFILE = BACKEND_DIR / "Dockerfile"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
README = BACKEND_DIR / "README.md"

#: The entrypoint migration in the form this process runs it: the module form of
#: the same alembic CLI, so the test needs no PATH entry.
MIGRATE = [sys.executable, "-m", "alembic", "upgrade", "head"]

#: How long the migration may take before the test stops waiting for it.
MIGRATE_TIMEOUT_SECONDS = 120

#: The tables the migration creates, plus the one alembic keeps of its own.
MIGRATED_TABLES = frozenset(
    {
        SCREENING_TABLE_NAME,
        AUDIT_EVENT_TABLE_NAME,
        LEDGER_ENTRY_TABLE_NAME,
        TRAVELER_CASE_TABLE_NAME,
        "alembic_version",
    }
)

#: Where the image keeps the virtualenv, and so where the entrypoint's bare
#: `alembic` is resolved from.
VENV_BIN = "/opt/venv/bin"

#: The command line the image declares, which the entrypoint execs rather than
#: replaces.
IMAGE_COMMAND_LINE = '["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]'


def _entrypoint_commands() -> list[str]:
    """The entrypoint commands, comments and blank lines dropped."""
    return [
        line.strip()
        for line in ENTRYPOINT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _instructions() -> list[tuple[str, str]]:
    """Every Dockerfile instruction as a pair, comments dropped.

    Line continuations are joined first, so what is read here is one instruction
    rather than one line of a wrapped one.
    """
    joined = DOCKERFILE.read_text(encoding="utf-8").replace(
        chr(92) + chr(10), " "
    )
    parsed: list[tuple[str, str]] = []
    for line in joined.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keyword, _, argument = stripped.partition(" ")
        parsed.append((keyword.upper(), argument.strip()))
    return parsed


def _arguments(keyword: str) -> list[str]:
    """Every matching instruction argument, in file order."""
    return [argument for name, argument in _instructions() if name == keyword]


def _position(keyword: str) -> int:
    """Where the last matching instruction stands, or a clear failure."""
    positions = [
        index for index, (name, _) in enumerate(_instructions()) if name == keyword
    ]
    assert positions, f"the Dockerfile declares no {keyword}"
    return positions[-1]


def _head_revision() -> str:
    """The one revision `head` names, read from the scripts."""
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()


def _sqlite_url(database: pathlib.Path) -> str:
    """The URL for a file, in the posix form `app.config` uses."""
    return f"sqlite:///{database.as_posix()}"


def _stamped_revision(database: pathlib.Path) -> str:
    """The revision `alembic_version` records in the file."""
    engine = db.build_engine(_sqlite_url(database))
    try:
        with engine.connect() as connection:
            return connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
    finally:
        engine.dispose()


def _run_the_deploy_step(database: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run the entrypoint migration against a file, as a boot does.

    :param database: a SQLite path, which need not exist yet.
    :returns: the finished process, captured rather than streamed, so a failure
        is read from the result instead of from the test log.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if name != "DATABASE_URL"
    }
    environment["DATABASE_URL"] = _sqlite_url(database)
    return subprocess.run(
        MIGRATE,
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=MIGRATE_TIMEOUT_SECONDS,
    )


@pytest.fixture(scope="module")
def migrated_database(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """The file the deploy step creates, starting from nothing.

    Outside the repository, so a failed run cannot leave a `drishti.db` beside the
    code, and absent to begin with.
    """
    database = (
        tmp_path_factory.mktemp("deploy-step") / config.DEFAULT_DATABASE_FILENAME
    )
    completed = _run_the_deploy_step(database)

    assert completed.returncode == 0, completed.stderr
    return database


# --- the deploy step ---------------------------------------------------


def test_the_deploy_step_runs_the_migration() -> None:
    """The one substantive entrypoint command is `alembic upgrade head`.

    Read as a command rather than as prose: a comment naming the migration is a
    claim about the script, not about the boot.
    """
    assert "alembic upgrade head" in _entrypoint_commands()


def test_the_migration_runs_before_the_service_is_served() -> None:
    """Migrate first, then exec the command line the image declares.

    The other order serves requests against a database holding no tables, which
    is the failure this step exists to remove.
    """
    commands = _entrypoint_commands()

    assert commands.index("alembic upgrade head") < commands.index(
        'exec "$@"'
    ), commands


def test_a_failed_migration_stops_the_boot() -> None:
    """Without `set -e` the script still serves after a failed migration.

    The exit status is what says the schema is not there, so the first command
    has to be the one that reads it.
    """
    commands = _entrypoint_commands()

    assert commands[0] == "set -e"
    assert commands.index("set -e") < commands.index("alembic upgrade head")


# --- the image runs it as the service user ------------------------------


def test_the_image_runs_the_deploy_step_after_dropping_privileges() -> None:
    """The migration writes the file the service writes, as that same user.

    The uid from D215 owns /app, so an ENTRYPOINT above the USER switch would
    migrate a root-owned database the service cannot then write.
    """
    entrypoints = _arguments("ENTRYPOINT")

    assert entrypoints, "the runtime stage declares no ENTRYPOINT"
    assert json.loads(entrypoints[-1]) == ["/app/docker-entrypoint.sh"]
    assert (
        _position("USER") < _position("ENTRYPOINT") < _position("CMD")
    )


def test_the_entrypoint_wraps_the_command_rather_than_replacing_it() -> None:
    """The CMD is still uvicorn: the step precedes it, not replaces it."""
    assert _arguments("CMD")[-1] == IMAGE_COMMAND_LINE


def test_the_image_copies_the_deploy_step_and_makes_it_executable() -> None:
    """A Windows checkout carries no exec bit, so the image sets one.

    Both instructions are read from the file rather than inferred: a COPY after
    the USER switch would need the service user to write into /app, and a
    missing chmod is a container that cannot start.
    """
    positions = [
        index
        for index, (name, argument) in enumerate(_instructions())
        if name in {"COPY", "RUN"}
        and "docker-entrypoint.sh" in argument
    ]

    assert positions, "the image never copies the deploy step"
    assert any(
        "chmod 0755" in argument for argument in _arguments("RUN")
    ), _arguments("RUN")
    assert max(positions) < _position("USER")


def test_the_image_puts_alembic_on_the_path_the_entrypoint_uses() -> None:
    """A bare `alembic` resolves only from the virtualenv the image builds."""
    assert VENV_BIN in " ".join(_arguments("ENV"))


# --- the local demo ----------------------------------------------------


def test_the_local_demo_migrates_before_it_serves() -> None:
    """The documented local run creates the schema it then reads.

    Split out of the README between its own headings, so run instructions for
    something else cannot satisfy this.
    """
    readme = README.read_text(encoding="utf-8")
    local = readme.split("## Run locally", 1)[1].split(
        "## Run as a container", 1
    )[0]

    assert "alembic upgrade head" in local
    assert local.index("alembic upgrade head") < local.index(
        "uvicorn main:app"
    )


def test_a_local_demo_needs_no_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nothing configured the service opens a SQLite file, not a socket.

    Reading the default must not create the file, so this case creates none and
    leaves 8.8's guard that the repository copy is absent.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = config.get_database_url()

    assert url.startswith("sqlite:///")
    assert url.endswith("/" + config.DEFAULT_DATABASE_FILENAME)
    assert not config.DEFAULT_DATABASE_PATH.exists()


def test_the_deploy_step_migrates_a_file_that_did_not_exist(
    migrated_database: pathlib.Path,
) -> None:
    """The entrypoint command creates the file and stamps it `head`."""
    engine = db.build_engine(_sqlite_url(migrated_database))
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
    finally:
        engine.dispose()

    assert migrated_database.exists()
    assert tables == MIGRATED_TABLES
    assert _stamped_revision(migrated_database) == _head_revision()


def test_the_deploy_step_can_run_again_at_every_boot(
    migrated_database: pathlib.Path,
) -> None:
    """A second boot migration is a no-op, not a second CREATE TABLE.

    The step runs at every container start, so idempotency decides whether it
    can run at all.
    """
    completed = _run_the_deploy_step(migrated_database)

    assert completed.returncode == 0, completed.stderr
    engine = db.build_engine(_sqlite_url(migrated_database))
    try:
        assert set(inspect(engine).get_table_names()) == MIGRATED_TABLES
    finally:
        engine.dispose()
    assert _stamped_revision(migrated_database) == _head_revision()


def test_the_service_writes_to_the_schema_the_deploy_step_created(
    migrated_database: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The demo write path, against the file the deploy step migrated.

    Read back through the ORM on the URL the service resolves, so this fails if
    the migration and the service are pointed at different databases.
    """
    monkeypatch.setenv("DATABASE_URL", _sqlite_url(migrated_database))
    engine = db.build_engine(config.get_database_url())
    factory = db.build_session_factory(engine)
    try:
        with factory() as session:
            session.add(
                Screening(
                    document_type="passport",
                    filename="specimen.png",
                    image_width=640,
                    image_height=480,
                )
            )
            session.commit()
        with factory() as session:
            count = session.scalar(select(func.count()).select_from(Screening))
    finally:
        engine.dispose()

    assert count == 1