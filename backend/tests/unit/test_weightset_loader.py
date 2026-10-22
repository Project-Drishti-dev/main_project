"""The weightset loader hands back the version the file names, read as data.

Task 7.2 is a loader, and the claim it exists to hold is small and exact: a
caller asking for a weightset gets the ``ruleset_version`` string out of that
file, and nothing else decides what it is.  7.1 held the *file* -- a row for
every id, three bands in three ranges, the version equal to
``app.version.RULESET_VERSION`` -- and this file holds the way the engine
reaches that file at all.

**Three claims carry the rest, and each is a way the loader could quietly do
the wrong thing instead.**  The file is read as a package resource rather than
off ``__file__``, so the read survives the package being installed.  A file
that is absent, unreadable, or names no version raises rather than answering
with a default, because a default version is a weightset nobody recorded and
every flag scored against a ruleset that was never written down.  And the rows
come back frozen, because a weight amended after the loader read it is a score
no longer comparable against the version it quotes.

**The file is read per call and not cached**, which is what lets a retuned
weightset be the one the next load returns; a module-level parse would make the
process that loaded it first the only one that ever sees the change.
"""

import ast
from pathlib import Path

import pytest
import yaml

from app import version
from app.risk.weightsets import loader
from app.risk.weightsets.loader import (
    DEFAULT_WEIGHTSET,
    WEIGHTSET_PACKAGE,
    Weightset,
    WeightsetError,
    load_weightset,
)

#: The file this suite is written against, read by path so the loader's answer
#: is checked against the file's own text rather than against itself.
WEIGHTSET_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "risk" / "weightsets" / "v1.yaml"
)

#: The loader's own source, for the claims that are about how it reads rather
#: than about what it returns.
LOADER_PATH = Path(loader.__file__).resolve()


def file_version():
    """The version string as the file's own bytes hold it."""
    return yaml.safe_load(WEIGHTSET_PATH.read_text(encoding="utf-8"))[
        "ruleset_version"
    ]


def test_the_loader_returns_the_ruleset_version_the_file_names():
    """The claim 7.2 is named for: the version comes off the file, unchanged."""
    loaded = load_weightset()

    assert loaded.ruleset_version == file_version()
    assert isinstance(loaded.ruleset_version, str)
    assert loaded.ruleset_version


def test_the_version_the_loader_returns_is_the_one_the_api_reports():
    """A score is only comparable against the ruleset that produced it.

    ``app.version`` moves ``RULESET_VERSION`` whenever a weight changes, so
    the string the loader hands back and that constant are one fact: a
    disagreement is a weight retuned without the version moving, which is
    exactly the change the abstract requires to be recorded.
    """
    assert load_weightset().ruleset_version == version.RULESET_VERSION


def test_the_default_weightset_is_the_v1_file_by_name():
    """A name, not a path and not a suffix.

    The default and the explicit request have to be the same file, and both
    have to be a *name* -- a caller that could hand the loader any path would
    be able to score a screening against a file that was never versioned.
    """
    assert DEFAULT_WEIGHTSET == "v1"
    assert load_weightset("v1") == load_weightset()


def test_a_weightset_that_is_not_there_raises_rather_than_answers():
    """A missing file is a deployment fault, and a zero weight is not the fix."""
    with pytest.raises(WeightsetError, match="v2"):
        load_weightset("v2")


@pytest.mark.parametrize(
    "document",
    [
        pytest.param({}, id="empty"),
        pytest.param({"flags": {}}, id="no_version_key"),
        pytest.param({"ruleset_version": ""}, id="empty_version"),
        pytest.param({"ruleset_version": 1}, id="version_is_not_text"),
        pytest.param(
            {"ruleset_version": "0.1.0"}, id="no_flags_mapping"
        ),
        pytest.param(
            {"ruleset_version": "0.1.0", "flags": []}, id="flags_is_not_a_mapping"
        ),
    ],
)
def test_a_file_the_loader_cannot_quote_a_version_from_is_refused(
    monkeypatch, document
):
    """Nothing is defaulted, so every one of these raises rather than loads.

    The shapes are handed straight to the loader rather than written to disk,
    because what is under test is what the loader does with what it read -- a
    temporary file would only prove that :mod:`yaml` agrees.
    """
    monkeypatch.setattr(loader, "_read", lambda _name: document)

    with pytest.raises(WeightsetError):
        load_weightset()


def test_a_file_that_is_not_readable_yaml_is_refused(monkeypatch):
    """Unparseable text is a refused file, not an empty weightset."""
    monkeypatch.setattr(
        loader.importlib.resources,
        "files",
        lambda _package: _Text("ruleset_version: [unclosed\n"),
    )

    with pytest.raises(WeightsetError, match="YAML"):
        load_weightset()


def test_a_file_that_is_not_a_mapping_is_refused(monkeypatch):
    """A document with no keys in it is not a weightset."""
    monkeypatch.setattr(
        loader.importlib.resources,
        "files",
        lambda _package: _Text("- a row\n- another\n"),
    )

    with pytest.raises(WeightsetError, match="mapping"):
        load_weightset()


def test_the_rows_come_back_frozen():
    """A weight amended after the read is a score nobody can trace.

    Both levels are held: the outer mapping and the row inside it, since a
    band retuned in place would be the quieter of the two.
    """
    loaded = load_weightset()

    with pytest.raises(TypeError):
        loaded.flags["MRZ_DOB_CHECK_DIGIT_MISMATCH"] = {"weight": 1, "band": "low"}
    with pytest.raises(TypeError):
        loaded.flags["MRZ_DOB_CHECK_DIGIT_MISMATCH"]["weight"] = 1


def test_the_file_is_read_again_on_every_load():
    """No module-level parse, so a retuned file is the next load's answer.

    Counted through :func:`_read` rather than by editing the file, so the claim
    is that the loader has no cached parse and not that this process happens to
    hold an old one.
    """
    reads = []
    real_read = loader._read

    def counting_read(name):
        reads.append(name)
        return real_read(name)

    loader._read = counting_read
    try:
        load_weightset()
        load_weightset()
    finally:
        loader._read = real_read

    assert reads == [DEFAULT_WEIGHTSET, DEFAULT_WEIGHTSET]


def test_the_loader_reads_a_package_resource_and_not_a_path_off_dunder_file():
    """The read survives the package being installed, or it does not happen.

    Held over the source rather than over a run, because a path off ``__file__``
    and a package-resource read return the same file from a checkout and
    differ only when the package is a wheel.  Three things are banned: the
    ``pathlib`` import, any use of ``__file__``, and a call to
    :func:`importlib.resources.files` that is not there.
    """
    tree = ast.parse(LOADER_PATH.read_text(encoding="utf-8"))

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    reads_the_package = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "files"
    ]

    assert not any(name.startswith("pathlib") for name in imported)
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "__file__"
    ]
    assert len(reads_the_package) == 1
    assert isinstance(reads_the_package[0].args[0], ast.Name)
    assert reads_the_package[0].args[0].id == "WEIGHTSET_PACKAGE"
    assert WEIGHTSET_PACKAGE == "app.risk.weightsets"


class _Text:
    """The one method of a resource the loader calls, returning fixed text.

    A stand-in for what :func:`importlib.resources.files` hands back, so a
    refusal can be tested against text no file has to be written for.
    """

    def __init__(self, text: str) -> None:
        self._text = text

    def joinpath(self, _name: str) -> "_Text":
        return self

    def read_text(self, *, encoding: str) -> str:
        assert encoding == "utf-8"
        return self._text


def test_the_loaded_record_is_a_frozen_weightset_named_by_its_file():
    """The return value is the loader's own type, not a bare mapping.

    A caller that has to know whether it got a record or a dict is a caller
    that 7.3's lookup will have to answer for, and the answer belongs in one
    place: the type this module returns.
    """
    loaded = load_weightset()

    assert isinstance(loaded, Weightset)
    with pytest.raises(AttributeError):
        loaded.ruleset_version = "9.9.9"
