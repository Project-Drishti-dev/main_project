"""The question a summary is asked, read from a versioned file rather than a string.

A prompt is prose rather than logic, so it is data: ``v1.txt`` declares the
version it was written under in its own header, and no version is written down
in Python beside it (the same rule, and the same ``D21`` argument, as
:mod:`app.risk.weightsets.loader`).  This module is the one way in, so a caller
holds a :class:`Prompt` and never a path.

**The file is read as a package resource** through
:func:`importlib.resources.files` on :data:`PROMPT_PACKAGE` and never from a
path built out of ``__file__``, for ``D15``'s reason: such a path stops
resolving once the package is installed as a wheel or a zip.

**Nothing here is cached.**  A prompt retuned on disk is the one the next load
returns, and :data:`PROMPT_VERSION` is a :pep:`562` ``__getattr__`` over the
shipped file for the same reason -- a constant here would be a snapshot of a
file that is allowed to change under it.

**A file that is absent, unversioned, doubly versioned or empty is refused**
rather than answered with a default: a default prompt is a prompt nobody
recorded, and the version beside it would be a version of nothing.
"""

import dataclasses
import importlib.resources

__all__ = [
    "DEFAULT_PROMPT",
    "PROMPT_PACKAGE",
    "PROMPT_SUFFIX",
    "PROMPT_VERSION",
    "VERSION_KEY",
    "Prompt",
    "PromptError",
    "load_prompt",
]

#: The package the prompt files are read from, named rather than derived from
#: ``__file__`` so the read is a package-resource read.
PROMPT_PACKAGE = "app.explain.prompts"

#: The file the loader reads when a caller names no prompt.
DEFAULT_PROMPT = "v1"

#: The extension a prompt name is completed with.
PROMPT_SUFFIX = ".txt"

#: The header key a prompt file declares its own version under.
VERSION_KEY = "prompt_version"

#: The character opening a header line, and the one closing a key.
_COMMENT = "#"
_COLON = ":"


class PromptError(ValueError):
    """Raised when a prompt file is absent, or is not one this module can read.

    A ``ValueError`` so a caller already catching one around the code that loads
    a prompt keeps working.  A message names the file and the key, never the
    prose: prompt text is not anything printed off a document.
    """


@dataclasses.dataclass(frozen=True)
class Prompt:
    """One loaded prompt: the version its header declares, and the text to send.

    Frozen, so a caller cannot amend the text and then quote the version beside
    it: the two have to stay the pair the file was written as.
    """

    version: str
    text: str


def load_prompt(name: str = DEFAULT_PROMPT) -> Prompt:
    """The prompt named ``name``, carrying the version its own header declares.

    ``name`` is a prompt name rather than a path or a suffix, so a caller cannot
    read a file from outside :data:`PROMPT_PACKAGE`.  Raises :exc:`PromptError`
    when the file is absent, names no :data:`VERSION_KEY`, names it twice, or
    declares a version and holds no text under it.
    """
    version, text = _split(_read(name), name)
    return Prompt(version=version, text=text)


def _read(name: str) -> str:
    """The named prompt file's own text, or a refusal naming the file."""
    resource = importlib.resources.files(PROMPT_PACKAGE).joinpath(
        name + PROMPT_SUFFIX
    )
    try:
        return resource.read_text(encoding="utf-8")
    except OSError:
        raise PromptError(f"no prompt named {name!r} in {PROMPT_PACKAGE}") from None


def _split(text: str, name: str) -> tuple[str, str]:
    """The version the leading ``#`` lines declare, and the prompt below them."""
    lines = text.splitlines()
    version = None
    index = 0
    for position, line in enumerate(lines):
        if not line.startswith(_COMMENT):
            index = position
            break
        declared = _declared(line)
        if declared is None:
            continue
        if version is not None:
            raise PromptError(f"the {name!r} prompt names {VERSION_KEY} twice")
        version = declared
    else:
        index = len(lines)

    if version is None:
        raise PromptError(f"the {name!r} prompt names no {VERSION_KEY} string")
    body = "\n".join(lines[index:]).strip()
    if not body:
        raise PromptError(f"the {name!r} prompt holds no text")
    return version, body


def _declared(line: str) -> str | None:
    """The version one header line declares, or ``None`` when it declares none."""
    head, colon, value = line.partition(VERSION_KEY + _COLON)
    if not colon or head.strip(_COMMENT).strip():
        return None
    return value.strip() or None


def __getattr__(name: str) -> str:
    """``PROMPT_VERSION``: the shipped file's own version, read on every access.

    Deliberately not a module attribute, because nothing else here is cached and
    a constant would be a snapshot of a file allowed to change under it.  Any
    other name still raises the ``AttributeError`` a missing one raises.
    """
    if name != "PROMPT_VERSION":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return load_prompt(DEFAULT_PROMPT).version
