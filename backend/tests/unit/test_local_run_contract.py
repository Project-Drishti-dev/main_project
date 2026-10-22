"""28.7: the documented local run path agrees with the code that serves it.

Reads the README's `## Run locally` section and holds it to the three
constants it must match: the CORS allowlist, the preview port, and the
localhost API port the served page calls.
"""

import json
import re

from app.config import BACKEND_DIR, LOCAL_CORS_ORIGINS


REPO_ROOT = BACKEND_DIR.parent
README = REPO_ROOT / "README.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"
PREVIEW_SCRIPT = REPO_ROOT / "frontend" / "scripts" / "preview.cjs"
API_CONFIG = REPO_ROOT / "frontend" / "api-config.js"

#: The heading the run path lives under. The section ends at the next one, so
#: prose elsewhere in the README cannot satisfy an assertion about it.
SECTION_HEADING = "## Run locally"

#: The two ports read from source rather than repeated here: the preview
#: server's default, and the API origin a page served from localhost calls.
PREVIEW_PORT = re.compile(r"const DEFAULT_PORT = (\d+);")
LOCAL_API_ORIGIN = re.compile(r"http://localhost:(\d+)")

#: The `CORS_ORIGINS=` line of `.env.example`, whose value is what a copy of
#: that file would put in a local shell.
EXAMPLE_CORS = re.compile(r"^CORS_ORIGINS=(.*)$", re.MULTILINE)


def _run_locally_section() -> str:
    """The README section the local run path is documented under.

    :returns: that section's markdown, or `""` when the heading is absent.
    """
    text = README.read_text(encoding="utf-8")
    start = text.find(SECTION_HEADING)
    if start < 0:
        return ""
    following = re.compile(r"^## ", re.MULTILINE).search(text, start + 1)
    return text[start : following.start() if following else len(text)]


def _port_from(pattern: re.Pattern, path) -> str:
    """The first port number `pattern` captures in `path`.

    :param pattern: a compiled pattern with one capture group.
    :param path: the file to read.
    :returns: the captured port as a string.
    :raises AssertionError: when the file does not state one port.
    """
    found = pattern.search(path.read_text(encoding="utf-8"))
    assert found is not None, f"{path.name} states no port to match the README"
    return found.group(1)


def test_the_readme_documents_a_local_run_section() -> None:
    assert _run_locally_section(), "README.md has no `## Run locally` section"


def test_every_allowed_localhost_origin_is_documented() -> None:
    section = _run_locally_section()
    undocumented = [o for o in LOCAL_CORS_ORIGINS if o not in section]
    assert not undocumented, (
        "README.md `## Run locally` omits allowed origins "
        f"{undocumented} from backend/app/config.py LOCAL_CORS_ORIGINS"
    )


def test_the_documented_api_port_is_the_one_the_frontend_calls() -> None:
    section = _run_locally_section()
    port = _port_from(LOCAL_API_ORIGIN, API_CONFIG)
    assert f"localhost:{port}" in section, (
        f"frontend/api-config.js calls localhost:{port}, which the README's "
        "`## Run locally` section does not name"
    )


def test_the_documented_serve_command_builds_and_serves() -> None:
    section = _run_locally_section()
    scripts = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]
    assert "npm run preview" in section, (
        "README.md `## Run locally` does not tell a reader to build and serve"
    )
    assert "preview" in scripts, "frontend/package.json has no preview script"
    assert scripts["preview"].endswith("preview.cjs"), (
        f"npm run preview runs {scripts['preview']!r}, which is not the "
        "preview server this README documents"
    )
    assert "buildSite" in PREVIEW_SCRIPT.read_text(encoding="utf-8"), (
        "frontend/scripts/preview.cjs never calls buildSite, so a local run "
        "could serve a stale dist"
    )


def test_the_documented_preview_port_is_the_one_the_server_binds() -> None:
    section = _run_locally_section()
    port = _port_from(PREVIEW_PORT, PREVIEW_SCRIPT)
    assert f"127.0.0.1:{port}" in section, (
        f"frontend/scripts/preview.cjs binds 127.0.0.1:{port}, which the "
        "README's `## Run locally` section does not name"
    )


def test_the_example_cors_value_is_inside_the_local_allowlist() -> None:
    shipped = EXAMPLE_CORS.search(ENV_EXAMPLE.read_text(encoding="utf-8"))
    assert shipped is not None, ".env.example declares no CORS_ORIGINS"
    origins = [o.strip().rstrip("/") for o in shipped.group(1).split(",") if o.strip()]
    assert origins, ".env.example ships CORS_ORIGINS with no origin in it"
    outside = [o for o in origins if o not in LOCAL_CORS_ORIGINS]
    assert not outside, (
        f".env.example ships CORS_ORIGINS {outside}, which a local run would "
        "not be allowed to use"
    )
