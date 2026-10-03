"""17.9 -- the prompt is a versioned file, and the version is the file's own.

The claim is small and exact.  The loader hands back the version the prompt's
header declares rather than one written beside it in Python; the file is read
per call rather than once at import; and a file rewritten on disk is the
version the very next read reports.  That last one is the whole task: a
"reported version" that could not move when the file moved would be a label,
and the prompt it labels is prose somebody has to be able to edit.

**The shipped file is read by path as well as through the loader**, so the
loader's answer is held against the file's own bytes rather than against
itself -- the move ``test_weightset_loader.py`` makes for ``v1.yaml``.

**The version is refused rather than defaulted** at every step: a file that is
not there, names no version, names it twice or declares one and holds no text
is a prompt nobody recorded, and a default beside it is a version of nothing.

**The shipped prompt is held to carry no number, no date and no field name.**
The frame is fixed and the findings are not, so anything the template itself
introduces is a token the verifier would find no flag behind -- a template that
hardcoded a field name would be biasing the model toward a claim the flags
never made (D133, D135).
"""

import ast
import dataclasses
from pathlib import Path

import pytest

from app import version
from app.explain.prompts import loader
from app.explain.prompts.loader import (
    DEFAULT_PROMPT,
    PROMPT_PACKAGE,
    PROMPT_SUFFIX,
    VERSION_KEY,
    Prompt,
    PromptError,
    load_prompt,
)
from app.explain.verifier import extract_dates, extract_field_names, extract_numbers

#: The file this suite is written against, read by path so the loader's answer
#: is checked against the file's own text rather than against itself.
APP_DIR = Path(__file__).resolve().parents[2] / "app"
PROMPT_DIR = APP_DIR / "explain" / "prompts"
PROMPT_PATH = PROMPT_DIR / "v1.txt"

#: The loader's own source, for the claims that are about how it reads rather
#: than about what it returns.
LOADER_PATH = Path(loader.__file__).resolve()

#: A header line carrying no key, the version line itself, and a prompt body.
NOTE = "# a note to whoever edits this file\n"
MENTION = "# The prompt_version: line is the one below.\n"
DECLARED = "# {0}: {1}\n"
BODY = "Write two sentences about the findings listed below.\n"

#: What the shipped prompt's rules forbid, and the constraint each answers to.
RULE_TERMS = ("flag ids", "risk band", "document image")

#: What opens a header line, and what closes a key: the two characters the
#: shipped file is read against here as well as by the loader.
_COMMENT = "#"
_COLON = ":"


def file_lines():
    """The shipped file's own lines, read by path."""
    return PROMPT_PATH.read_text(encoding="utf-8").splitlines()


def file_version():
    """The version string as the shipped file's own bytes hold it."""
    prefix = _COMMENT + " " + VERSION_KEY + _COLON
    for line in file_lines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise AssertionError("the shipped prompt declares no " + VERSION_KEY)


def file_text():
    """The shipped file's body: every line that is not part of its header."""
    lines = file_lines()
    while lines and lines[0].startswith(_COMMENT):
        lines.pop(0)
    return "\n".join(lines).strip()


@pytest.fixture
def in_a_directory(monkeypatch, tmp_path):
    """Point the loader's package read at ``tmp_path`` and hand it back.

    The shipped directory is the loader's own, so a test that needs a file the
    repository does not ship reads one out of a directory of its own rather
    than writing into the source tree.
    """
    monkeypatch.setattr(loader.importlib.resources, "files", lambda _package: tmp_path)
    return tmp_path


def write_prompt(directory, prompt_version, body=BODY, note=NOTE):
    """Write a prompt file declaring ``prompt_version`` and return its path."""
    path = directory / (DEFAULT_PROMPT + PROMPT_SUFFIX)
    path.write_text(
        note + DECLARED.format(VERSION_KEY, prompt_version) + body, encoding="utf-8"
    )
    return path


def test_the_loader_returns_the_version_the_prompt_file_names():
    """The claim 17.9 is named for: the version comes off the file, unchanged."""
    loaded = load_prompt()

    assert isinstance(loaded, Prompt)
    assert loaded.version == file_version()
    assert loaded.version


def test_the_prompt_comes_back_as_the_file_body_and_not_the_file_itself():
    """The header is metadata and is stripped; a hash below it is not a header."""
    loaded = load_prompt()

    assert loaded.text == file_text()
    assert loaded.text
    assert _COMMENT not in loaded.text
    assert VERSION_KEY not in loaded.text


def test_a_hash_in_the_body_is_kept_as_an_ordinary_character(in_a_directory):
    """Only the leading run of hash lines is a header, so the split is a position."""
    write_prompt(in_a_directory, "0.1.0", body=BODY + "# not a header\n")

    assert load_prompt().text.endswith("# not a header")


def test_the_prompt_version_is_the_one_the_api_reports():
    """``app.version`` moves ``PROMPT_VERSION`` with the template, and a test
    reads the file rather than comparing the constant to itself: a rename or a
    retune that moved one side and not the other is the failure here.
    """
    assert loader.PROMPT_VERSION == version.PROMPT_VERSION


def test_changing_the_file_changes_the_version_the_loader_reports(in_a_directory):
    """The task's own claim: the file is the version, not a label beside it."""
    write_prompt(in_a_directory, "0.1.0")
    assert load_prompt().version == "0.1.0"

    write_prompt(in_a_directory, "9.9.9")
    assert load_prompt().version == "9.9.9"


def test_changing_the_file_changes_the_prompt_version_reported(in_a_directory):
    """The same claim of the exported constant, which is why it is not one."""
    write_prompt(in_a_directory, "0.1.0")
    assert loader.PROMPT_VERSION == "0.1.0"

    write_prompt(in_a_directory, "9.9.9")
    assert loader.PROMPT_VERSION == "9.9.9"


def test_the_prompt_version_is_not_a_cached_module_attribute():
    """Nothing here is cached, so an assignment cannot shadow the read."""
    assert "PROMPT_VERSION" not in vars(loader)
    assert "PROMPT_VERSION" in loader.__all__


def test_an_attribute_that_is_not_the_prompt_version_still_raises():
    """A module hook over one name must not swallow the other misses."""
    with pytest.raises(AttributeError):
        loader.no_such_attribute


def test_the_default_prompt_is_the_v1_file_by_name():
    """The shipped answer is a named version rather than whatever is on disk."""
    assert DEFAULT_PROMPT == "v1"
    assert PROMPT_SUFFIX == ".txt"
    assert (PROMPT_DIR / (DEFAULT_PROMPT + PROMPT_SUFFIX)).is_file()
    assert PROMPT_PACKAGE == "app.explain.prompts"


def test_a_prompt_that_is_not_there_is_refused_rather_than_answered():
    """A missing prompt is a deployment fault, and a refusal names the file."""
    with pytest.raises(PromptError) as refusal:
        load_prompt("no-such-prompt")

    assert "no-such-prompt" in str(refusal.value)
    assert PROMPT_PACKAGE in str(refusal.value)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(BODY, id="no_header_at_all"),
        pytest.param(NOTE + BODY, id="header_names_no_version"),
        pytest.param(NOTE + DECLARED.format(VERSION_KEY, "") + BODY, id="blank_version"),
        pytest.param(NOTE + "# prompt_version2: 0.1.0\n" + BODY, id="near_miss_key"),
        pytest.param(NOTE + MENTION + BODY, id="key_written_inside_a_note"),
        pytest.param(
            NOTE + DECLARED.format(VERSION_KEY, "0.1.0") + "   \n\n",
            id="no_prompt_text",
        ),
        pytest.param(
            DECLARED.format(VERSION_KEY, "0.1.0") + DECLARED.format(VERSION_KEY, "9.9.9") + BODY,
            id="version_declared_twice",
        ),
        pytest.param("", id="empty_file"),
    ],
)
def test_a_file_the_loader_cannot_quote_a_version_from_is_refused(
    in_a_directory, text
):
    """Every way the file fails to be one prompt is refused, not defaulted."""
    (in_a_directory / (DEFAULT_PROMPT + PROMPT_SUFFIX)).write_text(
        text, encoding="utf-8"
    )

    with pytest.raises(PromptError):
        load_prompt()


def test_a_prompt_error_is_a_value_error():
    """So a caller catching one around the load keeps working (D21)."""
    assert issubclass(PromptError, ValueError)


def test_the_record_is_a_frozen_prompt_named_by_its_file():
    """The text cannot be amended and then quoted under the version beside it."""
    loaded = load_prompt()

    with pytest.raises(dataclasses.FrozenInstanceError):
        loaded.text = "something else"

    with pytest.raises(dataclasses.FrozenInstanceError):
        loaded.version = "9.9.9"


def test_the_file_is_read_again_on_every_load():
    """No module-level read, so a retuned file is the next load's answer."""
    reads = []
    real_read = loader._read

    def counting_read(name):
        reads.append(name)
        return real_read(name)

    loader._read = counting_read
    try:
        load_prompt()
        load_prompt()
    finally:
        loader._read = real_read

    assert reads == [DEFAULT_PROMPT, DEFAULT_PROMPT]


def test_the_loader_reads_a_package_resource_and_not_a_path_off_dunder_file():
    """The read survives the package being installed, or it does not happen.

    Held over the source rather than over a run, because a path off ``__file__``
    and a package-resource read return the same file from a checkout and differ
    only when the package is a wheel.
    """
    tree = ast.parse(LOADER_PATH.read_text(encoding="utf-8"))

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "pathlib" not in imported
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "__file__"
    ]
    assert [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "files"
    ]


def test_the_shipped_prompt_forbids_what_the_verifier_holds_it_to():
    """Each rule maps onto a constraint 17.5's verifier or D133 already imposes.

    Pinned as the terms the rules name rather than as their wording, so a rule
    reworded still passes and a rule dropped does not.
    """
    text = load_prompt().text.lower()

    for term in RULE_TERMS:
        assert term in text
    assert len([line for line in text.splitlines() if line.startswith("- ")]) == 4


def test_the_shipped_prompt_carries_no_number_no_date_and_no_field_name():
    """The frame is fixed and the findings are not, so the template itself must
    introduce no token the verifier would find no flag behind (D133, D135).
    """
    text = load_prompt().text

    assert extract_numbers(text) == ()
    assert extract_dates(text) == ()
    assert extract_field_names(text) == ()
