"""The passport entry point onto 27.2's generator, kept for 27.1's callers.

:func:`generate` draws a passport data page, a correct TD3 MRZ and the field
manifest 27.1 pinned.  **The drawing is not here**: it is
:mod:`tests.fixtures.document_corpus`, which 27.2 extended to draw a visa and a
national ID as well, and this module is the name those two document types do
not have.  Every value, pool and reader below is that module's own, re-exported
rather than restated, so there is one passport generator and one set of pools.
"""

from tests.fixtures import document_corpus, document_images

__all__ = [
    "BIRTH_YEARS",
    "DEFAULT_SEED",
    "DOCUMENT_NUMBER_DIGITS",
    "DOCUMENT_NUMBER_PREFIX",
    "DOCUMENT_TYPE",
    "EXPIRY_YEARS",
    "FORM",
    "GIVEN_NAMES",
    "ISSUING_STATES",
    "MrzField",
    "NATIONALITIES",
    "ROW_GAP",
    "SEXES",
    "SURNAMES",
    "SyntheticPassport",
    "generate",
    "mrz_field",
    "printed_field",
    "read_mrz",
]

#: What this entry point draws, and the MRZ format a passport carries.
DOCUMENT_TYPE = "passport"
FORM = document_corpus.DOCUMENT_TYPES[DOCUMENT_TYPE]

BIRTH_YEARS = document_corpus.BIRTH_YEARS
DEFAULT_SEED = document_corpus.DEFAULT_SEED
DOCUMENT_NUMBER_DIGITS = document_corpus.DOCUMENT_NUMBER_DIGITS
DOCUMENT_NUMBER_PREFIX = document_corpus.DOCUMENT_NUMBER_PREFIX
EXPIRY_YEARS = document_corpus.EXPIRY_YEARS
GIVEN_NAMES = document_corpus.GIVEN_NAMES
ISSUING_STATES = document_corpus.ISSUING_STATES
NATIONALITIES = document_corpus.NATIONALITIES
ROW_GAP = document_corpus.ROW_GAP
SEXES = document_corpus.SEXES
SURNAMES = document_corpus.SURNAMES
MrzField = document_corpus.MrzField
SyntheticPassport = document_corpus.SyntheticDocument
mrz_field = document_corpus.mrz_field
printed_field = document_corpus.printed_field
read_mrz = document_corpus.read_mrz


def generate(seed=DEFAULT_SEED, size=document_images.PAGE_SIZE):
    """Draw one synthetic passport and return it with its field manifest.

    ``seed`` picks the document and the same seed always draws the same one;
    ``size`` is the ``(width, height)`` asked for, and the page grows when the
    printed block and the MRZ strip do not both fit it, so nothing is clipped.

    Raises:
        ValueError: if the printed rows do not fit ``size``, which
            :func:`~tests.fixtures.document_images.draw_document` refuses.
    """
    return document_corpus.generate(seed, document_type=DOCUMENT_TYPE, size=size)
