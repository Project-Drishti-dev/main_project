"""Loading a document template: a reference image and a rectangle per field.

A template is data rather than code: ``passport_td3.json`` names a reference
image and a rectangle for every field the layout carries, and no coordinate is
written down in Python beside it.  This module is the one way in, so a caller
holding a template holds a :class:`Template` and never a path -- the same rule
:mod:`app.risk.weightsets.loader` works under for a weightset.

**The file is read as a package resource**, through
:func:`importlib.resources.files` on :data:`TEMPLATES_PACKAGE` and never from a
path built out of ``__file__``, on ``app.risk.weightsets.loader``'s reason: a
path assembled from ``__file__`` stops resolving the moment the package is
installed as a wheel or a zip, and a template that is not found reads as a
layout with no fields on it.

**A rectangle is written as a corner and a size, and answered as four corners.**
The file carries ``x``, ``y``, ``width`` and ``height`` because that is what a
person measures off the reference image with, and
:attr:`FieldRect.corners` answers them in the clockwise-from-the-top-left order
``app.risk.flags.EvidenceFlag.region`` is written in, so 13.9 hangs a finding on
a template's rectangle without re-expressing it.

**The frame is read off the reference image, not written beside it.**  A
rectangle is a claim about a position on *that* image, so a second copy of the
size in the JSON could disagree with the file it describes and nothing would
notice -- and a rectangle falling outside the image raises rather than being
kept, because a rectangle off the page locates nothing.

**Every key this module reads is required, and a key it does not read is
ignored.**  13.8 puts a per-field tolerance in the very same rows, and a loader
that refused a key it had not heard of would make that a loader change; a
misspelt key this module *does* read is caught by that key's own absence.
:func:`read_document` hands the parsed file back whole, so the module that owns
13.8's tolerance reads it out of the one parse rather than opening a second.

**No name is looked up in Python.**  ``document_type`` is answered as the
string the file carries and a field name is held only to being non-empty,
because a registry checked here is exactly what would make a new document type
a Python change -- the opposite of what 13.5 is for.  A test holds the
committed template's type against
:data:`app.pipeline.tier1.fields.DOCUMENT_TYPES` instead, which puts the check
on the one file that shipped rather than on every file written after it.

**A key the file names twice raises.**  :func:`json.loads` keeps the last of a
repeated key and says nothing, so a rectangle an author wrote twice would be
dropped without a word, and a hand-written data file is exactly where that
happens.

**Nothing here is defaulted, and nothing here is a finding.**  A file that
cannot be read, or that is missing a key, raises :exc:`TemplateError` rather
than answering with an empty template.  Where a printed field sits against the
reference is 13.6--13.9's question, and what a displacement means is 13.9's
flag.
"""

import dataclasses
import importlib.resources
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from PIL import Image, UnidentifiedImageError

__all__ = [
    "DOCUMENT_TYPE_KEY",
    "FIELDS_KEY",
    "FieldRect",
    "REFERENCE_IMAGE_KEY",
    "TEMPLATES_PACKAGE",
    "TEMPLATE_SUFFIX",
    "Template",
    "TemplateError",
    "load_template",
    "read_document",
]

#: The package the template files are read from, named rather than derived from
#: ``__file__`` so the read is a package-resource read.
TEMPLATES_PACKAGE = "app.pipeline.tier1.templates"

#: The extension a template name is completed with.
TEMPLATE_SUFFIX = ".json"

#: The three top-level keys 13.4's file owns: what the layout is for, the image
#: its rectangles were measured on, and the rectangles themselves.
DOCUMENT_TYPE_KEY = "document_type"
REFERENCE_IMAGE_KEY = "reference_image"
FIELDS_KEY = "fields"

#: The four keys one field's rectangle is written with, every one a whole pixel.
_RECT_KEYS = ("x", "y", "width", "height")


class TemplateError(ValueError):
    """Raised when a template file cannot be read, is not one, or describes a
    rectangle this cannot use.

    A ``ValueError``, so a caller already catching ``ValueError`` around the
    code that loads a template keeps working.

    **A message names the file and the field, never a row's contents.**  A
    template holds names and coordinates rather than anything printed off a
    document, so the value is not the risk ``FlagValueError`` guards against;
    the name and the key are still the whole of what a caller needs to find the
    file that is wrong.
    """


@dataclasses.dataclass(frozen=True)
class FieldRect:
    """One field's rectangle in the reference image's own pixels.

    ``x`` and ``y`` are the top-left corner and ``width`` and ``height`` the
    size below and right of it, both whole pixels and both as the file carries
    them.  Frozen, on the reason
    :class:`app.risk.weightsets.loader.Weightset` is.
    """

    x: int
    y: int
    width: int
    height: int

    @property
    def corners(self) -> tuple[tuple[int, int], ...]:
        """The rectangle's four corners, clockwise from the top left."""
        return (
            (self.x, self.y),
            (self.x + self.width, self.y),
            (self.x + self.width, self.y + self.height),
            (self.x, self.y + self.height),
        )


@dataclasses.dataclass(frozen=True)
class Template:
    """One loaded template: its type, its reference frame, and its rectangles.

    ``name`` is the template's own name, the one :func:`load_template` was asked
    for, so a caller holding a template can reach its own file without carrying
    a second handle to it.  ``document_type`` is the string the file names,
    unchanged and unchecked, on
    the module docstring's reason that a registry looked up here would make a
    new document type a Python change.  ``reference_image`` is the file's name
    and not its pixels: the image is opened to learn the frame and no bitmap is
    kept, so a template is a record of coordinates rather than a copy of an
    image.  ``reference_size`` is ``(width, height)`` in pixels, read off the
    image itself.  ``fields`` maps a field name to its rectangle, frozen so a
    caller cannot move a field after the loader read it.
    """

    name: str
    document_type: str
    reference_image: str
    reference_size: tuple[int, int]
    fields: Mapping[str, FieldRect]


def _repeating_key(name: str):
    """An object hook that refuses a key the ``name``'s file carries twice.

    Bound to the template's name so the message names the file as well as the
    key, which is all a caller needs to find the row that was written twice.
    """

    def hook(pairs):
        row = {}
        for key, value in pairs:
            if key in row:
                raise TemplateError(
                    f"the {name!r} template names {key!r} twice"
                )
            row[key] = value
        return row

    return hook


def read_document(name: str) -> Mapping[str, Any]:
    """The named template file, parsed, or a loud failure.

    Refused rather than defaulted at every step: a file that is not there, one
    that is not JSON, and one that is not a mapping are three ways a caller
    could be handed a layout with no fields on it.

    **Public so that 13.9 can read a key this module ignores.**  What a
    tolerance *means* is not the loader's to decide, and ``D98`` keeps it out of
    :class:`FieldRect`; handing the file back is what lets the module that owns
    the number read it without a parse of its own to disagree with this one.
    """
    resource = importlib.resources.files(TEMPLATES_PACKAGE).joinpath(
        name + TEMPLATE_SUFFIX
    )
    try:
        text = resource.read_text(encoding="utf-8")
    except OSError:
        raise TemplateError(
            f"no template named {name!r} in {TEMPLATES_PACKAGE}"
        ) from None

    try:
        document = json.loads(text, object_pairs_hook=_repeating_key(name))
    except json.JSONDecodeError:
        raise TemplateError(
            f"the {name!r} template is not readable JSON"
        ) from None

    if not isinstance(document, Mapping):
        raise TemplateError(f"the {name!r} template is not a mapping of keys")
    return document


def _reference_size(image_name: str) -> tuple[int, int]:
    """The named image's own ``(width, height)``, or a loud failure.

    A template's rectangles are positions on one image, so the frame they were
    measured in is read rather than declared.  The image is opened as a stream
    rather than by path, because a package resource stops being a path the
    moment the package is a zip.
    """
    resource = importlib.resources.files(TEMPLATES_PACKAGE).joinpath(image_name)
    try:
        with resource.open("rb") as stream:
            with Image.open(stream) as image:
                return image.size
    except UnidentifiedImageError:
        raise TemplateError(
            f"the {image_name!r} reference is not an image this can open"
        ) from None
    except FileNotFoundError:
        raise TemplateError(
            f"the {image_name!r} reference image is not in {TEMPLATES_PACKAGE}"
        ) from None
    except OSError:
        raise TemplateError(f"the {image_name!r} reference cannot be read") from None


def _whole_pixel(value: Any) -> bool:
    """Whether ``value`` is a whole pixel, which a ``bool`` is not.

    ``isinstance(True, int)`` holds, so a rectangle carrying ``true`` would
    otherwise be read as one pixel wide rather than refused.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _rect(field: str, row: Any, size: tuple[int, int]) -> FieldRect:
    """One field's rectangle as the file writes it, or a loud failure.

    Every way the four keys can be unreadable raises, and each message names the
    field and the key rather than the row.  The rectangle is also held to the
    reference frame it claims to sit on: a rectangle that runs off the image
    locates nothing, and keeping it would hand 13.9 a position to compare
    against that no page can ever occupy.
    """
    if not field:
        raise TemplateError(f"a field of the template is named {field!r}")
    if not isinstance(row, Mapping):
        raise TemplateError(f"the {field!r} field is not a rectangle of four keys")

    whole = {}
    for key in _RECT_KEYS:
        value = row.get(key)
        if not _whole_pixel(value):
            raise TemplateError(
                f"the {field!r} field has no whole-pixel {key!r}"
            )
        whole[key] = value

    if whole["width"] <= 0 or whole["height"] <= 0:
        raise TemplateError(f"the {field!r} field has no area to be read from")

    width, height = size
    right = whole["x"] + whole["width"]
    bottom = whole["y"] + whole["height"]
    if whole["x"] < 0 or whole["y"] < 0 or right > width or bottom > height:
        raise TemplateError(
            f"the {field!r} field falls outside the reference image"
        )

    return FieldRect(**whole)


def load_template(name: str) -> Template:
    """Return the template named ``name``: its type, its frame and its fields.

    ``name`` is a template name rather than a path or a suffix, so a caller
    cannot read a file from outside :data:`TEMPLATES_PACKAGE`.  **There is no
    default**, because nothing has chosen the layout Tier 1 should reach for and
    a default would be that choice made on the loader's behalf.

    Raises :exc:`TemplateError` when the file is absent, is not readable JSON,
    is not a mapping, names no :data:`DOCUMENT_TYPE_KEY` or
    :data:`REFERENCE_IMAGE_KEY` string, names a reference image that is absent
    or unreadable, holds no :data:`FIELDS_KEY` mapping of at least one
    rectangle, or carries a field whose rectangle is unreadable or falls outside
    the reference.
    """
    document = read_document(name)

    document_type = document.get(DOCUMENT_TYPE_KEY)
    if not isinstance(document_type, str) or not document_type:
        raise TemplateError(
            f"the {name!r} template names no {DOCUMENT_TYPE_KEY} string"
        )

    image_name = document.get(REFERENCE_IMAGE_KEY)
    if not isinstance(image_name, str) or not image_name:
        raise TemplateError(
            f"the {name!r} template names no {REFERENCE_IMAGE_KEY} string"
        )
    size = _reference_size(image_name)

    rows = document.get(FIELDS_KEY)
    if not isinstance(rows, Mapping):
        raise TemplateError(f"the {name!r} template holds no {FIELDS_KEY} mapping")
    if not rows:
        raise TemplateError(f"the {name!r} template names no field at all")

    return Template(
        name=name,
        document_type=document_type,
        reference_image=image_name,
        reference_size=size,
        fields=MappingProxyType(
            {field: _rect(field, row, size) for field, row in rows.items()}
        ),
    )
