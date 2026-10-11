"""28.6: the two files listing environment variables name the same ones.

Both are read as lists of (name, status) pairs and compared both ways, and the
code that reads the environment is read too, so a variable configured in
`app/config.py` or `frontend/build.cjs` and documented in neither file fails.
"""

import re

from app.config import BACKEND_DIR


REPO_ROOT = BACKEND_DIR.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
README = REPO_ROOT / "README.md"
CONFIG_MODULE = BACKEND_DIR / "app" / "config.py"
BUILD_SCRIPT = REPO_ROOT / "frontend" / "build.cjs"

#: The heading the README's tables live under. The list ends at the next one,
#: so a table elsewhere in the file cannot be read as part of it.
SECTION_HEADING = "## Environment variables"

#: The three statuses, as each file spells them.
STATUSES = ("live", "planned", "held")

#: A declaration in `.env.example`: the name and its shipped value, which may be
#: empty, so the trailing `=` is what matches.
_DECLARATION = re.compile(r"^([A-Z][A-Z0-9_]*)=")

#: A status comment. The legend near the top of the file indents its tags, so
#: `^# ` is what separates a tag from an example of one. The tag is mapped to
#: the word the README's status cell uses, because the two files spell the same
#: three statuses differently.
_TAG = re.compile(r"^# \[(LIVE|PLAN|HOLD)\]")
_TAGS = {"LIVE": "live", "PLAN": "planned", "HOLD": "held"}

#: The name cell of one README table row.
_ROW = re.compile(r"^`([A-Z][A-Z0-9_]*)`$")


def _example_entries() -> list[tuple[str, str]]:
    """Every (name, status) `.env.example` declares, in file order.

    :returns: one pair per `NAME=` line, the status being the tag comment above
        it. A declaration with no tag above it is an assertion failure.
    """
    entries: list[tuple[str, str]] = []
    status: str | None = None
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        declaration = _DECLARATION.match(line)
        if declaration:
            name = declaration.group(1)
            assert status is not None, f"{name} is declared with no tag above it"
            entries.append((name, _TAGS[status]))
            continue
        tag = _TAG.match(line)
        if tag:
            status = tag.group(1)
    return entries


def _documented_entries() -> list[tuple[str, str]]:
    """Every (name, status) the README's section declares.

    :returns: one pair per table row naming a variable, the status being the
        third cell. Rows naming nothing variable -- the header and the
        separator -- match no name and are skipped.
    """
    text = README.read_text(encoding="utf-8")
    assert SECTION_HEADING in text, f"{README.name} has no {SECTION_HEADING} section"
    entries: list[tuple[str, str]] = []
    for line in text.split(SECTION_HEADING, 1)[1].splitlines():
        if line.startswith("## "):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        name = _ROW.match(cells[0])
        if name:
            assert len(cells) > 2, f"{name.group(1)} has no status cell"
            entries.append((name.group(1), cells[2].lower()))
    return entries


def _variables_the_backend_reads() -> set[str]:
    """Names `app/config.py` reads: constants, plus the two read inline."""
    source = CONFIG_MODULE.read_text(encoding="utf-8")
    return set(
        re.findall(r'\w+_ENV_VAR = "([A-Z][A-Z0-9_]*)"', source)
    ) | set(re.findall(r'os\.getenv\("([A-Z][A-Z0-9_]*)"\)', source))


def _variables_the_build_reads() -> set[str]:
    """Names `frontend/build.cjs` reads, directly or through a constant."""
    source = BUILD_SCRIPT.read_text(encoding="utf-8")
    return set(
        re.findall(r"process\.env\.([A-Z][A-Z0-9_]+)", source)
    ) | set(re.findall(r'\w+_ENV_VAR = "([A-Z][A-Z0-9_]*)"', source))


def test_both_files_declare_at_least_one_variable() -> None:
    """Two empty lists would match each other and pass every comparison."""
    assert _example_entries(), f"{ENV_EXAMPLE.name} declares no variable"
    assert _documented_entries(), f"{README.name} documents no variable"


def test_the_two_lists_name_the_same_variables() -> None:
    """Set equality, not containment, in both directions.

    A variable only `.env.example` knows is one an operator copies and a
    maintainer cannot find; one only the README knows is the reverse.
    """
    in_example = {name for name, _ in _example_entries()}
    in_readme = {name for name, _ in _documented_entries()}

    assert in_example - in_readme == set(), (
        f"{sorted(in_example - in_readme)} are in {ENV_EXAMPLE.name} and not in "
        f"{README.name}"
    )
    assert in_readme - in_example == set(), (
        f"{sorted(in_readme - in_example)} are in {README.name} and not in "
        f"{ENV_EXAMPLE.name}"
    )


def test_neither_file_names_a_variable_twice() -> None:
    """A repeat is invisible to a set comparison, and reads as two settings."""
    for label, entries in (
        (ENV_EXAMPLE.name, _example_entries()),
        (README.name, _documented_entries()),
    ):
        names = [name for name, _ in entries]
        repeated = sorted({name for name in names if names.count(name) > 1})

        assert not repeated, f"{label} lists {repeated} more than once"


def test_a_variable_has_the_same_status_in_both_files() -> None:
    """A variable promoted from planned to live in the code is drift in one
    file or the other until both are changed, so the statuses are compared."""
    in_example = dict(_example_entries())
    in_readme = dict(_documented_entries())
    shared = in_example.keys() & in_readme.keys()

    disagreeing = {
        name: f"{README.name} says {in_readme[name]}, {ENV_EXAMPLE.name} says {in_example[name]}"
        for name in shared
        if in_readme[name] != in_example[name]
    }

    assert not disagreeing, disagreeing


def test_every_status_is_one_of_the_three_words() -> None:
    """A fourth spelling would compare equal in one file and read as nothing
    in the other."""
    for label, entries in (
        (ENV_EXAMPLE.name, _example_entries()),
        (README.name, _documented_entries()),
    ):
        used = {status for _, status in entries}

        assert used <= set(STATUSES), f"{label} uses {sorted(used - set(STATUSES))}"


def test_every_variable_the_code_reads_is_documented() -> None:
    """The lists are only complete if they cover what is read.

    Reads the source rather than a hand-written list, so a variable added to
    the backend or the build without being documented fails here.
    """
    read = _variables_the_backend_reads() | _variables_the_build_reads()
    listed = {name for name, _ in _documented_entries()}

    assert read - listed == set(), (
        f"{sorted(read - listed)} are read by {CONFIG_MODULE.name} or "
        f"{BUILD_SCRIPT.name} and documented in neither file"
    )