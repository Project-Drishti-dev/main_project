"""26.1: the image builds, runs, and answers ``/health`` from inside it.

`tests/unit/test_dockerfile_contract.py` reads the Dockerfile; only this file
proves the image. It builds `backend/` the way a deployment would, runs the
container, and asks the published port for ``/health``. Nothing else is
asserted -- the point is that the pinned base, the copied virtualenv and the
CMD line up into a process that answers at all.

It needs a Docker daemon, so it skips, with the reason, where there is none,
rather than reporting a pass nobody earned. Only ``/health`` is read, so no
image bytes, OCR text or identity data can reach the output.
"""

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator

import pytest

from app.config import BACKEND_DIR


#: Tagged per run so two runs never share an image, and so the image this
#: run answers from is provably the one this run built.
IMAGE_TAG = f"drishti-backend-healthcheck:{uuid.uuid4().hex[:12]}"

#: The port the image serves on, which the contract tests read out of it too.
IMAGE_PORT = 8080

#: A first build resolves every wheel from PyPI, so this is minutes, not
#: seconds; a warm cache is far quicker.
BUILD_TIMEOUT_SECONDS = 1800

#: How long the container may take to import the stack and answer.
STARTUP_TIMEOUT_SECONDS = 120


def _docker() -> str:
    """The docker CLI, or a skip: without it there is no image to ask."""
    found = shutil.which("docker")
    if not found:
        pytest.skip("docker is not on PATH, so no image can be built on this machine")
    return found


def _run(docker: str, *arguments: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    """One docker command, with its output captured rather than printed."""
    return subprocess.run(
        [docker, *arguments], capture_output=True, text=True, timeout=timeout
    )


def _tail(output: str, lines: int = 40) -> str:
    """The last ``lines`` of a command's output, for a failure message."""
    return "\n".join(output.splitlines()[-lines:])


@pytest.fixture(scope="module")
def docker_daemon() -> Iterator[str]:
    """A Docker CLI that can actually reach a daemon.

    A CLI on PATH is not a daemon: an installed client against a stopped or
    unreachable server fails every command with a permission or connection
    error, and reporting that as a broken image would be reading the machine
    as the Dockerfile.
    """
    docker = _docker()
    reachable = _run(docker, "info", timeout=120)
    if reachable.returncode != 0:
        pytest.skip(f"no reachable Docker daemon here: {_tail(reachable.stderr, 3)}")
    yield docker


@pytest.fixture(scope="module")
def built_image(docker_daemon: str) -> Iterator[str]:
    """Build `backend/` into an image, and remove it when the run is over."""
    completed = _run(
        docker_daemon, "build", "-t", IMAGE_TAG, str(BACKEND_DIR),
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        pytest.fail(f"the image did not build:\n{_tail(completed.stderr)}")

    try:
        yield IMAGE_TAG
    finally:
        _run(docker_daemon, "image", "rm", "-f", IMAGE_TAG)


@pytest.fixture(scope="module")
def running_container(built_image: str, docker_daemon: str) -> Iterator[str]:
    """Run the built image, publishing 8080 on a port the host picks."""
    started = _run(
        docker_daemon, "run", "--detach", "-p", f"127.0.0.1::{IMAGE_PORT}", built_image
    )
    if started.returncode != 0:
        pytest.fail(f"the image did not start:\n{_tail(started.stderr)}")

    container = started.stdout.strip()
    try:
        yield container
    finally:
        _run(docker_daemon, "rm", "--force", container)


def _published_port(docker_daemon: str, container: str) -> int:
    """The host port the container's 8080 is published on."""
    published = _run(docker_daemon, "port", container, f"{IMAGE_PORT}/tcp")
    if published.returncode != 0:
        pytest.fail(f"the container published no port:\n{_tail(published.stderr)}")
    return int(published.stdout.splitlines()[0].rsplit(":", 1)[1])


def _await_health(port: int) -> dict[str, object]:
    """``GET /health`` once it answers, or fail saying it never did.

    Polling rather than sleeping a fixed time: the container is answering as
    soon as the stack is imported, and how long that takes depends on the
    machine rather than on the image.
    """
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    url = f"http://127.0.0.1:{port}/health"
    last_error = "no request was made"

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return json.loads(response.read())
        except (urllib.error.URLError, OSError, ValueError) as error:
            last_error = f"{type(error).__name__}: {error}"
        time.sleep(1)

    pytest.fail(f"/health did not answer within {STARTUP_TIMEOUT_SECONDS}s: {last_error}")


def test_the_container_runs_the_image_this_run_built(running_container, built_image):
    """The answer below is only evidence if the container is this image.

    A container left over from an earlier run on the same name would answer
    /health perfectly and prove nothing about the Dockerfile.
    """
    inspected = _run(
        _docker(), "inspect", "--format", "{{.Config.Image}}", running_container
    )

    assert inspected.stdout.strip() == built_image


def test_health_answers_from_the_running_image(running_container, docker_daemon):
    """The task's assertion: the endpoint responds from inside the image.

    ``/health`` is the one route that opens no session and reads no row, so
    this answers whether the image starts and serves -- not whether its schema
    is migrated, which is a separate task.
    """
    port = _published_port(docker_daemon, running_container)

    assert _await_health(port) == {"status": "ok"}


def test_the_image_config_declares_a_non_root_user(built_image, docker_daemon):
    """The USER the image config carries is what a plain `docker run` gets.

    Read from the config rather than from a running container, so it answers
    even when an operator overrides the user at run time -- which is exactly
    the case where the file's own instruction is the thing being trusted.
    """
    inspected = _run(
        docker_daemon, "inspect", "--format", "{{.Config.User}}", built_image
    )
    if inspected.returncode != 0:
        pytest.fail(f"the image config was not readable:\n{_tail(inspected.stderr)}")

    declared = inspected.stdout.strip()

    assert declared, "the image config names no user, so the service runs as root"
    assert declared.split(":")[0] not in ("root", "0"), (
        f"the image config names {declared!r} as its user"
    )


def test_the_running_container_reports_a_non_zero_uid(running_container, docker_daemon):
    """The task's assertion, asked of the process rather than of the file.

    `id -u` inside the container is what the kernel says the user is, so it
    catches a USER the image carries and then drops -- an entrypoint that
    re-raises, or a base image whose default is restored -- which no amount of
    reading the Dockerfile can.
    """
    inside = _run(docker_daemon, "exec", running_container, "id", "-u", timeout=60)
    if inside.returncode != 0:
        pytest.fail(f"the container's uid was not readable:\n{_tail(inside.stderr)}")

    reported = inside.stdout.strip()

    assert reported.isdigit(), f"uid {reported!r} is not a number"
    assert int(reported) != 0, "the service is running as uid 0 (root)"