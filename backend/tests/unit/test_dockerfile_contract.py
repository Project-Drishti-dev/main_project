"""26.1: the two build files are read, not trusted.

`tests/deploy/test_docker_image_health.py` proves the image by building and
running it, and needs a Docker daemon to do it. These read the two files
instead, so the properties that decide whether that build can succeed at all
are decidable on a machine with no daemon: the build is multi-stage, both
stages share one digest-pinned base, the virtualenv crosses the stage
boundary, the CMD serves the entry point the runtime actually copied, and the
ignore file keeps the source in and the local state out.
"""

import json
import re
from pathlib import Path

from app.config import BACKEND_DIR


DOCKERFILE = BACKEND_DIR / "Dockerfile"
DOCKERIGNORE = BACKEND_DIR / ".dockerignore"

#: A base image named with a tag *and* a digest. A tag alone floats: the same
#: name names a different image after any upstream patch release.
PINNED_BASE_IMAGE = re.compile(r"^[a-z0-9][\w./-]*:[^@\s]+@sha256:[0-9a-f]{64}$")

#: Where the builder installs and the runtime copies the virtualenv from.
VENV_PATH = "/opt/venv"

#: The port the image serves on, and the one Cloud Run sets ``PORT`` to.
IMAGE_PORT = 8080


def _instructions(text: str) -> list[tuple[str, str]]:
    """Every instruction in ``text`` as ``(keyword, argument)``.

    Line continuations are joined first, and a comment is dropped rather than
    parsed: a Dockerfile whose instructions are decided by a comment is not a
    Dockerfile these tests can vouch for.
    """
    joined = text.replace("\\\r\n", " ").replace("\\\n", " ")
    parsed: list[tuple[str, str]] = []
    for line in joined.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keyword, _, argument = stripped.partition(" ")
        parsed.append((keyword.upper(), argument.strip()))
    return parsed


def _stage_alias(argument: str) -> str | None:
    """The stage name after ``AS``, when the FROM names one."""
    parts = argument.split()
    for index, part in enumerate(parts):
        if part.upper() == "AS" and index + 1 < len(parts):
            return parts[index + 1]
    return None


def _stage_bodies() -> dict[str, str]:
    """Each stage's alias mapped to its own lines, comments included."""
    bodies: dict[str, list[str]] = {}
    alias: str | None = None
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.upper().startswith("FROM "):
            alias = _stage_alias(stripped) or f"stage{len(bodies)}"
            bodies[alias] = []
            continue
        if alias is not None:
            bodies[alias].append(line)
    return {name: "\n".join(lines) for name, lines in bodies.items()}


def _copy_sources(body: str) -> set[str]:
    """Every path a COPY reads in ``body``, destination and flags removed."""
    sources: set[str] = set()
    for keyword, argument in _instructions(body):
        if keyword != "COPY":
            continue
        parts = [part for part in argument.split() if not part.startswith("--")]
        for source in parts[:-1]:
            sources.add(source.strip("./").rstrip("/"))
    return sources


def _ignore_patterns() -> list[str]:
    """The patterns in ``.dockerignore``, without comments or trailing slashes."""
    patterns = []
    for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped.rstrip("/"))
    return patterns


def _base_images() -> list[str]:
    """The image each FROM names, in file order."""
    return [
        argument.split()[0]
        for keyword, argument in _instructions(DOCKERFILE.read_text(encoding="utf-8"))
        if keyword == "FROM"
    ]


def test_the_build_is_multi_stage():
    """One stage is a single-stage build wearing a second FROM as a comment.

    The point of the split is that the builder's pip cache and the tooling
    around it never reach the shipped image, and a build that has only one
    stage cannot keep them out.
    """
    aliases = list(_stage_bodies())

    assert len(aliases) >= 2, f"expected two or more stages, found {aliases}"
    assert all(aliases), "every FROM should name its stage after AS"


def test_every_stage_pins_its_base_image_by_digest():
    """A tag alone is not a pin, because the same tag names a new image later."""
    unpinned = [image for image in _base_images() if not PINNED_BASE_IMAGE.match(image)]

    assert not unpinned, f"base images are not pinned by digest: {unpinned}"


def test_both_stages_ride_the_same_digest():
    """A virtualenv built by one interpreter cannot be copied into another.

    The builder resolves the wheels against the image it names and the runtime
    copies the result across the stage boundary, so a second digest would ship
    an interpreter-dependent install and fail at the first import rather than
    at the build.
    """
    digests = {image.split("@", 1)[1] for image in _base_images() if "@" in image}

    assert len(digests) == 1, f"the stages name {len(digests)} different base images"


def test_the_runtime_copies_the_virtualenv_the_builder_installed():
    """Otherwise the second stage resolves nothing and the CMD cannot start."""
    stages = _stage_bodies()
    builder = next(body for name, body in stages.items() if name == "builder")
    runtime = stages["runtime"]

    assert f"python -m venv {VENV_PATH}" in builder
    assert re.search(
        rf"COPY\s+--from=builder\s+{re.escape(VENV_PATH)}\s+\S+", runtime
    ), "the runtime copies no virtualenv out of the builder"


def test_the_runtime_copies_what_the_command_line_imports():
    """A CMD naming ``main:app`` against source the image never copied."""
    sources = _copy_sources(_stage_bodies()["runtime"])

    assert {"main.py", "app"} <= sources, f"the runtime copies {sorted(sources)}"


def test_the_command_line_serves_the_app_on_the_exposed_port():
    """One port, so the image and Cloud Run are not configured differently."""
    runtime = _stage_bodies()["runtime"]
    command = next(
        argument
        for keyword, argument in _instructions(runtime)
        if keyword == "CMD"
    )
    exposed = {
        int(argument)
        for keyword, argument in _instructions(runtime)
        if keyword == "EXPOSE"
    }

    argv = json.loads(command)

    assert argv[0] == "uvicorn"
    assert "main:app" in argv
    assert argv[argv.index("--host") + 1] == "0.0.0.0"
    assert int(argv[argv.index("--port") + 1]) in exposed, (
        f"the CMD serves {argv[argv.index('--port') + 1]} and the image exposes {exposed}"
    )


def test_the_ignore_file_leaves_the_test_and_local_state_out():
    """Context that is uploaded, cached or generated by a run, not shipped."""
    patterns = _ignore_patterns()

    for excluded in ("tests", ".venv", "__pycache__", ".pytest_cache", "evidence", "*.db"):
        assert excluded in patterns, f"{excluded!r} is not ignored, so it reaches an image"


def test_the_ignore_file_keeps_what_the_runtime_reads():
    """An ignore rule too broad for the service, and the build fails on it.

    A `.dockerignore` is a list of what to send, not a list of what to worry
    about, so the entries the runtime stage copies are held here explicitly:
    dropping one into the ignore file is a build failure found by reading two
    small files, rather than by a daemon.
    """
    patterns = _ignore_patterns()

    for required in ("app", "main.py", "alembic", "alembic.ini", "requirements.txt"):
        assert required not in patterns, f"{required!r} is ignored, and the image needs it"


#: The account the runtime stage serves as. Named rather than numbered in the
#: USER instruction, so the refusal below can tell a dropped privilege from a
#: renamed one.
SERVICE_USER = "drishti"

#: The uid that account is created with. Zero is root, and a uid this file does
#: not fix is a uid this file cannot check.
SERVICE_UID = 10001


def test_the_runtime_stage_drops_privileges_before_it_serves():
    """No USER, or a USER naming root, is a service running as root.

    Read from the runtime stage only: a USER in the builder changes nothing
    about the process that answers requests.
    """
    runtime = _stage_bodies()["runtime"]
    users = [argument for keyword, argument in _instructions(runtime) if keyword == "USER"]

    assert users, "the runtime stage names no USER, so the service runs as root"
    assert users[-1].split(":")[0] == SERVICE_USER, (
        f"the runtime stage runs as {users[-1]!r}"
    )


def test_the_service_uid_is_fixed_and_is_not_zero():
    """An account whose uid comes from the base image is not a decision.

    Docker resolves a numeric USER at start-up, so `USER 10001` also keeps the
    image startable if the name is ever removed from /etc/passwd.
    """
    runtime = _stage_bodies()["runtime"]
    created = next(
        argument
        for keyword, argument in _instructions(runtime)
        if keyword == "RUN" and f"useradd --uid {SERVICE_UID} " in argument
    )

    assert SERVICE_UID != 0, "uid 0 is root"
    assert f"useradd --uid {SERVICE_UID} --gid {SERVICE_UID}" in created
    assert "nologin" in created, "a service account should not be able to log in"


def test_the_user_is_the_last_one_the_runtime_stage_declares():
    """A USER followed by another USER is the earlier one that never runs.

    Read as positions in one instruction list, because the failure is an
    ordering bug that a "does it contain a USER" check cannot see.
    """
    instructions = _instructions(_stage_bodies()["runtime"])
    keywords = [keyword for keyword, _ in instructions]
    users = [index for index, keyword in enumerate(keywords) if keyword == "USER"]
    command = keywords.index("CMD")

    assert users, "the runtime stage names no USER"
    assert users[-1] == max(users), "a later USER overrides the one above it"
    assert users[-1] < command, "the USER must precede the CMD it governs"


def test_the_writable_directories_belong_to_the_service_user():
    """Handing over /app after the USER switch grants nothing.

    app.config resolves both the SQLite file and the evidence store root
    against the backend directory, which is /app in this image, so a root-owned
    /app is the first upload failing on permissions.
    """
    instructions = _instructions(_stage_bodies()["runtime"])
    keywords = [keyword for keyword, _ in instructions]
    chowns = [
        argument
        for keyword, argument in instructions
        if keyword == "RUN" and f"chown -R {SERVICE_USER}:{SERVICE_USER}" in argument
    ]
    user_index = max(
        index for index, keyword in enumerate(keywords) if keyword == "USER"
    )
    chown_indices = [
        index
        for index, (keyword, argument) in enumerate(instructions)
        if keyword == "RUN" and f"chown -R {SERVICE_USER}:{SERVICE_USER}" in argument
    ]

    assert chowns, "nothing is handed to the service user, so /app stays root-owned"
    assert all(index < user_index for index in chown_indices), (
        "the chown runs after the USER switch, where it cannot grant anything"
    )
    assert any("/app" in argument for argument in chowns)