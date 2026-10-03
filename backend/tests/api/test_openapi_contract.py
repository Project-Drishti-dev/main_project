"""11.12: every endpoint's documented response, snapshotted.

A shape change nobody planned is silent -- the endpoint keeps answering 200
and the client that read the field finds it gone.  Each operation's responses
(status code, media type, and the schema with every ``$ref`` inlined) are held
against ``openapi_contract.json`` beside this file, so an added or dropped
field fails the suite.  Rewrite that file with
``DRISHTI_UPDATE_OPENAPI_SNAPSHOT=1`` once a change is intended.
"""

import difflib
import json
import os
from pathlib import Path
from typing import Any

from app.main import app


#: The committed contract: every operation, every response it documents.
CONTRACT_PATH = Path(__file__).with_name("openapi_contract.json")

#: Set to ``"1"`` to rewrite the snapshot from the app as it is built.
UPDATE_ENV_VAR = "DRISHTI_UPDATE_OPENAPI_SNAPSHOT"

#: Prose rather than shape.  A description or an example is documentation, so
#: editing one is not a change a client can break on.
PROSE_KEYS = frozenset({"description", "example", "examples"})

#: The endpoints 11.12 names, spelled out so an added or dropped route reads
#: as itself rather than as a wall of diff.
EXPECTED_PATHS = frozenset(
    {
        "/health",
        "/ready",
        "/api/analyze",
        "/api/audit/{audit_id}/verify",
        "/api/screenings",
        "/api/screenings/{screening_id}",
        "/api/screenings/{screening_id}/decision",
        "/api/screenings/{screening_id}/progress",
        "/api/screenings/{screening_id}/progress/stream",
        "/api/screenings/{screening_id}/report",
        "/api/version",
    }
)


def _at(spec: dict[str, Any], ref: str) -> Any:
    """Follow a local JSON pointer such as ``#/components/schemas/X``.

    :param spec: the document the pointer is read from.
    :param ref: the pointer, naming a component of that document.
    :returns: the node the pointer names.
    """
    node: Any = spec
    for part in ref.removeprefix("#/").split("/"):
        node = node[part]
    return node


def _inlined(node: Any, spec: dict[str, Any], seen: frozenset[str]) -> Any:
    """Resolve every ``$ref`` to the schema it names, dropping prose keys.

    A model that reaches itself keeps its own pointer rather than the target,
    so a self-referential schema terminates instead of recursing forever.

    :param node: the fragment being walked.
    :param spec: the document holding the components.
    :param seen: the refs already expanded on the way here.
    :returns: the fragment with its refs replaced by what they name.
    """
    if isinstance(node, list):
        return [_inlined(item, spec, seen) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        if ref in seen:
            return {"$recursiveRef": ref}
        return _inlined(_at(spec, ref), spec, seen | {ref})
    return {
        key: _inlined(value, spec, seen)
        for key, value in node.items()
        if key not in PROSE_KEYS
    }


def contract() -> dict[str, Any]:
    """Every documented response of every operation, keyed path then method.

    :returns: ``{path: {method: {status_code: response}}}``, each response
        resolved, so a field buried in a model is part of the comparison.
    """
    spec = app.openapi()
    return {
        path: {
            method: {
                code: _inlined(response, spec, frozenset())
                for code, response in operation["responses"].items()
            }
            for method, operation in methods.items()
        }
        for path, methods in spec["paths"].items()
    }


def _text(value: Any) -> str:
    """Render one side of the comparison as stable, diffable JSON."""
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _difference(expected: Any, current: Any) -> str:
    """Spell out where the committed snapshot and the app have parted."""
    return "\n".join(
        difflib.unified_diff(
            _text(expected).splitlines(),
            _text(current).splitlines(),
            fromfile=f"{CONTRACT_PATH.name} as committed",
            tofile="the app as built",
            lineterm="",
        )
    )


def test_every_documented_response_matches_the_snapshot():
    """The responses the app builds are the ones the snapshot records."""
    current = contract()
    if os.environ.get(UPDATE_ENV_VAR) == "1":
        CONTRACT_PATH.write_bytes(_text(current).encode("utf-8"))
    assert CONTRACT_PATH.is_file(), (
        f"{CONTRACT_PATH.name} is missing; write it with {UPDATE_ENV_VAR}=1."
    )

    expected = json.loads(CONTRACT_PATH.read_bytes().decode("utf-8"))

    assert expected == current, _difference(expected, current)


def test_the_snapshot_covers_every_endpoint_the_api_serves():
    """The contract is the whole API, not the part someone remembered."""
    assert set(contract()) == EXPECTED_PATHS


def test_no_response_is_left_holding_a_reference():
    """Every schema is inlined, so a field inside a model is compared too.

    An unexpanded ``$ref`` would leave the file passing while the model
    behind it grew a field -- the one change this file exists to catch.
    """
    assert '"$ref"' not in json.dumps(contract())