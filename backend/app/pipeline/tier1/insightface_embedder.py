"""InsightFace behind the face seam: one face's vector, or an honest absence.

The ``insightface`` package is imported on first use rather than at module
scope, so importing this module on a box that has never installed it costs
nothing and fails nothing, and a missing package answers
:meth:`InsightFaceEmbedder.is_available` and ``None`` from ``embed`` rather
than raising.

**Availability is one question -- the package -- and the model is not
probed.**  Loading the model is what fetches it, and ``D84`` already refused
to let a probe pay a download.  A box holding the package but not the weights
therefore reports itself available and raises on the first ``embed``; that is
a broken install and not an absence, and ``D83``'s reason for not swallowing
one is why it is loud.

**The crop is resized, not aligned.**  ``get_feat`` reads a fixed-width frame
and fails on any other, so the crop is converted here the way 12.3 converts
one for pytesseract.  Turning landmarks into that crop is 13.14's; nothing
here moves a pixel of position.
"""

from functools import lru_cache

import cv2
import numpy

from app.pipeline.tier1.face import Embedder, Embedding

__all__ = [
    "IMPORT",
    "INSIGHTFACE_MODEL",
    "INSIGHTFACE_PROVIDERS",
    "MODEL_INPUT_SIZE",
    "InsightFaceEmbedder",
]

#: Constructor default meaning "import insightface when asked".  Passing
#: ``binding=None`` instead says the package is definitely absent, which is a
#: different answer and the one a test needs to be the same on every machine.
IMPORT = object()

#: The recognition model ``model_zoo`` loads, and the ONNX runtime provider it
#: runs on.  The name is spelled out rather than inherited from insightface's
#: own default so a change there cannot silently move which faces we score.
#: CPU-only because this project has never run on a GPU and a provider that is
#: present on some machines and not others would make the same box answer
#: differently depending on what was installed alongside it.
INSIGHTFACE_MODEL = "w600k_r50.onnx"
INSIGHTFACE_PROVIDERS = ("CPUExecutionProvider",)

#: The square the recogniser reads, which is the crop's own width and height.
MODEL_INPUT_SIZE = 112


@lru_cache(maxsize=1)
def _import_insightface():
    """Return insightface's ``model_zoo``, or ``None`` where it is not installed.

    The absence is cached as firmly as the presence: a box without the package
    asks once per process rather than once per document.
    """
    try:
        from insightface import model_zoo
    except ImportError:
        return None
    return model_zoo


def _as_model_input(image):
    """The crop in the square, contiguous shape the recogniser reads.

    Tier 0 works in BGR and ArcFace was trained on it, so the frame is handed
    over in the order it arrives -- the reversal 12.3 performs for pytesseract
    would swap two channels and every vector would still look plausible.
    """
    resized = cv2.resize(image, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
    return numpy.ascontiguousarray(resized)


class InsightFaceEmbedder(Embedder):
    """ArcFace's vector for one face crop, or ``None`` where there is no model.

    ``binding`` stands in for insightface's ``model_zoo``, so a test can answer
    either way on a machine that has never installed the package.  The
    recogniser is held on the instance, because it carries the loaded session
    and building one per document would re-load it per document.
    """

    def __init__(self, *, binding=IMPORT):
        self._binding = binding
        self._recogniser = None

    def _model_zoo(self):
        """The package to read through: the one handed in, or insightface."""
        if self._binding is not IMPORT:
            return self._binding
        return _import_insightface()

    def _recogniser_for(self, binding):
        """The recogniser to read through, built once and then kept."""
        if self._recogniser is None:
            self._recogniser = binding.get_model(
                INSIGHTFACE_MODEL, providers=INSIGHTFACE_PROVIDERS
            )
        return self._recogniser

    def is_available(self) -> bool:
        """Whether an embedding could run: the ``insightface`` package imports.

        One question, because InsightFace is a package and not a package plus
        an executable to find, so the answer cannot be half-true.  The model
        is not loaded to answer it -- loading is what downloads, and a probe
        that downloads is the cost ``D84`` refused.
        """
        return self._model_zoo() is not None

    def embed(self, image) -> Embedding | None:
        """Return the model's own vector for ``image``, or ``None`` when absent.

        A missing InsightFace is not an error here: the embed degrades to
        ``None``, which is ``D101``'s answer for a face nothing measured.  A
        model that cannot be loaded is not degraded and raises, being a broken
        install rather than an absence.
        """
        binding = self._model_zoo()
        if binding is None:
            return None
        recogniser = self._recogniser_for(binding)
        feats = recogniser.get_feat(_as_model_input(image))
        return Embedding(vector=tuple(float(value) for value in feats))
