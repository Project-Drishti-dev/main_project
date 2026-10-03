"""Which engine Tier 1 reads with: a preference, an order, or neither.

:func:`select_engine` is the one thing that holds a list of engines, and it
holds it without knowing which is which -- it asks each whether it is
available and answers the first that says yes, or the one a caller named.  The
names a preference may be spelled in are :data:`ENGINE_NAMES`, and each has an
engine behind it in :data:`DEFAULT_ENGINES`.

**Absence is a value here, so the selector branches rather than catches.**
Every ``is_available()`` answers a bool (``D83``, ``D84``), and nothing is
wrapped around asking the question: a probe that raises is a broken install
and is not this module's to swallow, which would report a blank page on a box
whose engine is only unreachable.

**A preference that is not available answers ``None`` and is not
substituted.**  A caller names an engine for a reason -- a script it reads
better, a language, boxes 12.8 can crop -- so answering it with another engine
would hand back a read nobody asked for, under a name the caller did not
choose.  ``None`` is what 12.6 degrades on, which makes an unavailable
preference and an uninstalled engine one state to the caller rather than two.
12.9 is where a *second* engine is tried on purpose, and it is written down
there.

**The order is Tesseract, then EasyOCR, and the order is a decision.**  It is
neither alphabetical nor fastest-first: EasyOCR builds a ``Reader`` whose
models are downloaded the first time one is built (``D84``), so leading with
it would make this module's default choice the one that costs a download.
:data:`ENGINE_NAMES` is that order written down and a test holds the registry
to it, so an engine added out of order is caught rather than quietly changing
which engine reads.

**The seam does not declare the question this module asks.**
:func:`~app.pipeline.tier1.ocr.OcrEngine` requires ``read`` and nothing else
(``D82``), and ``is_available`` is concrete on each engine rather than
abstract (``D83``), so the call below is the one place in Tier 1 depending on
a method the abstract class does not list.  Both engines here are built in this
module, so the gap cannot be reached by a caller who passes nothing; the cost
is recorded rather than paid silently, and a third caller of
``is_available`` is what should reopen ``D83``.

**The registry is read-only and built once.**  :data:`DEFAULT_ENGINES` is a
mapping proxy, so no caller can add a third engine to the set the default
choice is made from, and its engines are module-level objects because
EasyOCR's reader -- and the models it holds -- lives on the instance
(``D84``): a registry rebuilt per call would reload them per document.
"""

from collections.abc import Mapping
from types import MappingProxyType

from app.pipeline.tier1.easyocr_engine import EasyOcrEngine
from app.pipeline.tier1.ocr import OcrEngine
from app.pipeline.tier1.tesseract_engine import TesseractEngine

__all__ = [
    "DEFAULT_ENGINES",
    "EASYOCR",
    "EASYOCR_ENGINE",
    "ENGINE_NAMES",
    "TESSERACT",
    "TESSERACT_ENGINE",
    "UnknownEngineError",
    "select_engine",
]

#: The spelling of a preference naming each engine.  Two constants rather than
#: strings written at call sites, so a caller spells ``EASYOCR`` and a rename
#: is one edit rather than a search.
TESSERACT = "tesseract"
EASYOCR = "easyocr"

#: The order "first available" walks, and the whole set of names a preference
#: may be spelled in.  Spelled out beside the registry rather than read off its
#: keys so the order is one value a test can hold that registry against.
ENGINE_NAMES = (TESSERACT, EASYOCR)

#: The one engine of each kind this process reads with.  Module-level because
#: EasyOCR keeps its reader -- and the loaded models -- on the instance, so an
#: engine built per document would reload them per document.
TESSERACT_ENGINE = TesseractEngine()
EASYOCR_ENGINE = EasyOcrEngine()

#: The registry :func:`select_engine` reads by default, in
#: :data:`ENGINE_NAMES` order and behind a mapping proxy so the default
#: choice cannot be edited by a caller.
DEFAULT_ENGINES: Mapping[str, OcrEngine] = MappingProxyType({
    TESSERACT: TESSERACT_ENGINE,
    EASYOCR: EASYOCR_ENGINE,
})


class UnknownEngineError(ValueError):
    """Raised when a preference names an engine this selector cannot hold.

    A ``ValueError``, so a caller already catching one around its choice keeps
    working.  This is a wiring mistake and not an absence: every name in
    :data:`ENGINE_NAMES` has an engine behind it, and answering ``None`` for
    a misspelling would degrade every screening on the box with nothing to say
    which engine was asked for.  It is loud on purpose -- ``main.py``'s
    catch-all answers it as a 500 ``INTERNAL_ERROR`` envelope (``D74``), and
    one refused document is cheaper than a box that silently reads with an
    engine nobody chose.
    """


def select_engine(
    preference: str | None = None,
    *,
    engines: Mapping[str, OcrEngine] | None = None,
) -> OcrEngine | None:
    """Return the engine to read with: the one named, or the first available.

    :param preference: one of :data:`ENGINE_NAMES`, spelled exactly, or
        ``None`` -- the one spelling of "no preference", and the reason an
        empty or wrongly-cased name is a refusal rather than a shrug.
    :param engines: the registry to choose from, in the order "first
        available" walks it.  Defaults to :data:`DEFAULT_ENGINES`.
    :returns: the engine to read with, or ``None`` when none is available.
        One answer covers three causes: no engine installed, a preference
        naming an engine that is not available, and a registry holding none.
    :raises UnknownEngineError: when ``preference`` is not a string, or names
        no engine in ``engines``.

    **A preference is asked about alone.**  Naming an engine that is available
    answers it whatever the order says, and asking the rest as well would ask
    questions whose answers cannot change the one returned.
    """
    known = DEFAULT_ENGINES if engines is None else engines

    if preference is not None:
        engine = _engine_named(preference, known)
        return engine if engine.is_available() else None

    for engine in known.values():
        if engine.is_available():
            return engine
    return None


def _engine_named(preference: object, known: Mapping[str, OcrEngine]) -> OcrEngine:
    """The engine ``preference`` names, refusing a name this call cannot hold.

    :param preference: the caller's preference, of any type.
    :param known: the registry the choice is being made from.
    :returns: the engine ``known`` holds under that name.
    :raises UnknownEngineError: when ``preference`` is not a string or names
        no engine in ``known``.  The message lists the names this call does
        know and echoes the preference: that value is a deployment's
        configuration and not anything a document printed.
    """
    if isinstance(preference, str) and preference in known:
        return known[preference]
    raise UnknownEngineError(
        f"preference must be one of {', '.join(known)} or None; "
        f"{preference!r} is not one."
    )