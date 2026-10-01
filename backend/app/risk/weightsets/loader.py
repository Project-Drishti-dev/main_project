"""Loading a weightset file, and handing back the version it names.

A weightset is data rather than code: ``v1.yaml`` holds a weight and a band
for every flag id, and no number, band or version is written down in Python
alongside it (``D21``).  This module is the one way in, so a caller holding a
weightset holds a :class:`Weightset` and never a path.

**The file is read as a package resource**, through
:func:`importlib.resources.files` on :data:`WEIGHTSET_PACKAGE` and never from
a path built out of ``__file__``.  :mod:`app.seed` and ``D15`` are the
precedent and the reason is the same one: a path assembled from ``__file__``
stops resolving the moment the package is installed as a wheel or a zip, and a
weightset that is not found reads as no weight at all.

**The file is read once per call and never cached at module level**, so a
weightset retuned on disk is the one the next load returns and no run holds a
parse of a file that has since changed.  The record handed back is frozen, so
a caller cannot amend a weight after the loader has read it.

**Nothing here says what a weight means.**  Parsing the file is this module's
whole job; 7.3's lookup, 7.4's value mapping and 7.5's sum are separate
questions asked of the same data.

**A file that cannot be read, or that names no version, raises rather than
answering with a default.**  An absent weightset is a deployment fault, and
the failure it causes -- a missing weight scored as zero -- is silent, so it
is refused at the door with :exc:`WeightsetError`.
"""

import dataclasses
import importlib.resources
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import yaml

__all__ = [
    "DEFAULT_WEIGHTSET",
    "FLAGS_KEY",
    "RULESET_VERSION_KEY",
    "WEIGHTSET_PACKAGE",
    "WEIGHTSET_SUFFIX",
    "Weightset",
    "WeightsetError",
    "load_weightset",
]

#: The package the weightset files are read from, named rather than derived
#: from ``__file__`` so the read is a package-resource read.
WEIGHTSET_PACKAGE = "app.risk.weightsets"

#: The file the engine loads when a caller names no weightset.
DEFAULT_WEIGHTSET = "v1"

#: The extension a weightset name is completed with.
WEIGHTSET_SUFFIX = ".yaml"

#: The two top-level keys 7.1's file owns: the version it was written under and
#: the rows, one per flag id.
RULESET_VERSION_KEY = "ruleset_version"
FLAGS_KEY = "flags"


class WeightsetError(ValueError):
    """Raised when a weightset file cannot be read, is not one, or is asked
    about an id it carries no usable weight for.

    A ``ValueError``, so a caller already catching ``ValueError`` around the
    code that loads a weightset keeps working, and so that
    :func:`app.risk.weightsets.lookup.weight_for` refuses an unweighted id
    through the same type rather than a ``KeyError``.

    **A message names the file and the key, never a row's contents.**  A
    weightset holds weights and bands rather than anything printed off a
    document, so the value is not the risk ``FlagValueError`` and
    ``WatchlistValueError`` guard against; the name is still the whole of what
    a caller needs to find the file that is wrong.
    """


@dataclasses.dataclass(frozen=True)
class Weightset:
    """One loaded weightset: the version it names and the rows it holds.

    ``ruleset_version`` is the string the file carries, unchanged, so a score
    can be quoted against the ruleset that produced it.  ``flags`` maps a flag
    id to that id's row, frozen: a caller cannot raise a weight after the fact
    and have a screening answered from a ruleset nobody recorded.

    **A row is frozen when it is a mapping and passed through otherwise.**  The
    shape of a row -- a ``weight`` and a ``band`` and nothing else -- is 7.1's
    claim, held against the file, and this loader does not re-judge it; 7.3's
    lookup is what turns a row into numbers.
    """

    ruleset_version: str
    flags: Mapping[str, Any]


def _read(name: str) -> Mapping[str, Any]:
    """The named weightset file, parsed, or a loud failure.

    Refused rather than defaulted at every step: a file that is not there, one
    that is not YAML, and one that is not a mapping are three ways an engine
    could be handed no weights at all.
    """
    resource = importlib.resources.files(WEIGHTSET_PACKAGE).joinpath(
        name + WEIGHTSET_SUFFIX
    )
    try:
        text = resource.read_text(encoding="utf-8")
    except OSError:
        raise WeightsetError(
            f"no weightset named {name!r} in {WEIGHTSET_PACKAGE}"
        ) from None

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        raise WeightsetError(
            f"the {name!r} weightset is not readable YAML"
        ) from None

    if not isinstance(document, Mapping):
        raise WeightsetError(f"the {name!r} weightset is not a mapping of keys")
    return document


def _frozen_rows(rows: Mapping[str, Any]) -> Mapping[str, Any]:
    """The rows as a read-only mapping, each mapping row read-only too."""
    return MappingProxyType(
        {
            flag_id: MappingProxyType(row) if isinstance(row, Mapping) else row
            for flag_id, row in rows.items()
        }
    )


def load_weightset(name: str = DEFAULT_WEIGHTSET) -> Weightset:
    """Return the weightset named ``name``, with the version the file carries.

    ``name`` is a weightset name rather than a path or a suffix, so a caller
    cannot read a file from outside :data:`WEIGHTSET_PACKAGE`, and the default
    is the version the engine ships with.

    Raises :exc:`WeightsetError` when the file is absent, is not readable YAML,
    is not a mapping, names no :data:`RULESET_VERSION_KEY`, or holds no
    :data:`FLAGS_KEY` mapping.
    """
    document = _read(name)

    version = document.get(RULESET_VERSION_KEY)
    if not isinstance(version, str) or not version:
        raise WeightsetError(
            f"the {name!r} weightset names no {RULESET_VERSION_KEY} string"
        )

    rows = document.get(FLAGS_KEY)
    if not isinstance(rows, Mapping):
        raise WeightsetError(
            f"the {name!r} weightset holds no {FLAGS_KEY} mapping"
        )

    return Weightset(ruleset_version=version, flags=_frozen_rows(rows))
