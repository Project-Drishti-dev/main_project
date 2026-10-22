"""26.6, 26.7: CI runs the stages `scripts/check-all.ps1` runs.

The workflow is parsed and the assertions are about run commands and working
directories, so a stage named only in a comment cannot satisfy them. Nothing
here proves a run happened; it proves what a run would do.
"""

import json
import pathlib

import yaml

from app.config import BACKEND_DIR


REPO_ROOT = BACKEND_DIR.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
FRONTEND_DIR = REPO_ROOT / "frontend"

#: The commands, as the runner receives them. The backend one is check-all's
#: own, from the repository root, so the two gates cannot drift apart.
BACKEND_COMMAND = "python -m pytest backend/tests -q"
FRONTEND_TEST_COMMAND = "npm test"
FRONTEND_BUILD_COMMAND = "npm run build"
#: 26.7. The check that reads what the build wrote, and the npm script it
#: names, so a rename cannot leave CI running a command that no longer exists.
ARTEFACT_COMMAND = "npm run check-artefacts"
ARTEFACT_SCRIPT = "node scripts/check-artefacts.cjs"
PACKAGE_JSON = FRONTEND_DIR / "package.json"
CHECK_ALL = REPO_ROOT / "scripts" / "check-all.ps1"


def _workflow() -> dict:
    """The parsed workflow."""
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers() -> dict:
    """The trigger block, under either spelling of `on` PyYAML may leave."""
    workflow = _workflow()
    for key in ("on", True):
        if key in workflow:
            return workflow[key] or {}
    raise AssertionError(f"{WORKFLOW.name} declares no trigger block")


def _steps() -> list[tuple[str, str, dict]]:
    """Every step as (job, working directory, step), across all jobs."""
    steps: list[tuple[str, str, dict]] = []
    for name, job in _workflow()["jobs"].items():
        defaults = job.get("defaults") or {}
        working_directory = (defaults.get("run") or {}).get(
            "working-directory", ""
        )
        for step in job.get("steps") or []:
            steps.append((name, working_directory, step))
    return steps


def _commands() -> list[str]:
    """Every run block, whitespace-normalised, so a wrapped command is one."""
    return [
        " ".join(step["run"].split())
        for _, _, step in _steps()
        if "run" in step
    ]


def _runs_in(directory: pathlib.Path, command: str) -> bool:
    """Whether some step runs `command` from the directory named.

    :param directory: the directory the command has to run in.
    :param command: the run block, whitespace-normalised.
    :returns: whether a step's working-directory resolves to `directory`, so
        both `frontend` and an absolute path count and a step run from
        elsewhere does not.
    """
    return any(
        " ".join(step["run"].split()) == command
        and (REPO_ROOT / working_directory).resolve() == directory.resolve()
        for _, working_directory, step in _steps()
        if "run" in step
    )


def test_every_push_runs_the_workflow() -> None:
    """The trigger is `push`, unfiltered.

    A branch filter lets pushes to any other branch through unbuilt, which is
    exactly the drift this workflow exists to catch.
    """
    triggers = _triggers()

    assert "push" in triggers, triggers
    assert triggers["push"] in (None, {}), triggers["push"]


def test_the_backend_suite_runs_the_command_check_all_runs() -> None:
    """Backend pytest, by check-all's own command rather than a paraphrase."""
    assert BACKEND_COMMAND in _commands()


def test_the_backend_dependencies_are_installed_before_the_suite_runs() -> None:
    """requirements-dev.txt first: a suite that cannot import app cannot pass."""
    commands = _commands()
    install = "pip install -r backend/requirements-dev.txt"

    assert install in commands
    assert commands.index(install) < commands.index(BACKEND_COMMAND)


def test_the_frontend_tests_run_from_the_frontend_directory() -> None:
    """`npm test`, from the directory holding package.json.

    The same command run from the repository root is npm's help text rather
    than the suite, so the directory is part of the claim.
    """
    assert _runs_in(FRONTEND_DIR, FRONTEND_TEST_COMMAND)


def test_the_frontend_build_runs_from_the_frontend_directory() -> None:
    """`npm run build`, from that same directory and after the tests."""
    commands = _commands()

    assert _runs_in(FRONTEND_DIR, FRONTEND_BUILD_COMMAND)
    assert commands.index(FRONTEND_TEST_COMMAND) < commands.index(
        FRONTEND_BUILD_COMMAND
    )


def test_the_frontend_dependencies_are_installed_from_the_lockfile() -> None:
    """`npm ci`, or the runner has no node_modules to test or build with."""
    assert _runs_in(FRONTEND_DIR, "npm ci")


def test_every_job_starts_by_checking_out_the_repository() -> None:
    """Without a checkout a job runs against an empty workspace."""
    jobs = _workflow()["jobs"]

    assert jobs, "the workflow declares no job"
    for name, job in jobs.items():
        actions = [step.get("uses", "") for step in job.get("steps") or []]

        assert any(
            action.startswith("actions/checkout@") for action in actions
        ), f"the {name} job never checks the repository out"

def test_the_built_artefacts_are_checked_after_the_build() -> None:
    """`npm run check-artefacts`, from `frontend/` and after `npm run build`.

    Read before the build there is no directory to check, so the order is part
    of the claim: a check that ran first would pass on nothing and be green
    about every artefact the build went on to leave out.
    """
    commands = _commands()

    assert _runs_in(FRONTEND_DIR, ARTEFACT_COMMAND)
    assert commands.index(FRONTEND_BUILD_COMMAND) < commands.index(
        ARTEFACT_COMMAND
    )


def test_the_artefact_command_is_a_script_that_exists() -> None:
    """The workflow names an npm script, so package.json has to carry it.

    A step naming a script that was renamed or removed fails on the runner as
    an npm usage error, which reads as a broken workflow rather than as the
    artefact contract quietly not running.
    """
    scripts = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]

    assert ARTEFACT_COMMAND.split("run ", 1)[1] in scripts
    assert scripts[ARTEFACT_COMMAND.split("run ", 1)[1]] == ARTEFACT_SCRIPT


def test_check_all_runs_the_artefact_command_ci_runs() -> None:
    """The local gate runs the same command.

    CI is check-all's own gate (D218), so a fourth stage only in the workflow
    would leave `./scripts/check-all.ps1` reporting three green stages for a
    build whose artefacts nobody had looked at.
    """
    assert ARTEFACT_COMMAND in CHECK_ALL.read_text(encoding="utf-8")
