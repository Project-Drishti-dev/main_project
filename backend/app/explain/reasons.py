"""One plain-language sentence per flag id, written here and never asked for.

Every id in `app.risk.flag_ids.FLAG_IDS` has a sentence here, so a finding is
never read as a bare machine name and never waits on a model that may not exist
(`D142`).  The sentences are fixed prose: no value read off a document is written
into one, so a template cannot become a place identity data is stored, and no
number, date or field name appears in one, so
`app.explain.verifier.verify_summary` can never refuse a template whatever the
flag data prints.

**These are the floor beneath a rule's own `reason`, not a replacement for it**
(D135): a rule that wrote a specific reason says more than a sentence written
once per id, and this module is what an officer still has when no rule wrote one.
"""

from types import MappingProxyType

from app.risk import flag_ids
from app.risk.flags import FlagValueError

__all__ = ["REASON_TEMPLATES", "reason_for"]

#: One sentence per flag id, in :data:`app.risk.flag_ids.ALL_FLAG_IDS` order and
#: keyed by the registry's own constant, so an id is never retyped here and no id
#: is spelled twice.  Read-only, because the table is the record.
REASON_TEMPLATES = MappingProxyType(
    {
        flag_ids.QUALITY_BLUR: (
            "The photograph is too blurred to read, so nothing on the page could"
            " be checked from it."
        ),
        flag_ids.QUALITY_NOISE: (
            "The photograph carries heavy camera noise, which makes the fine print"
            " on the page harder to read."
        ),
        flag_ids.QUALITY_EXPOSURE: (
            "The photograph is under- or over-exposed, so part of the page is lost"
            " in shadow or washed out."
        ),
        flag_ids.QUALITY_UNEVEN_LIGHTING: (
            "The page is lit unevenly, so one part of it reads darker than the"
            " rest."
        ),
        flag_ids.QUALITY_GLARE: (
            "A reflection covers part of the card and hides what is underneath it."
        ),
        flag_ids.QUALITY_LOW_RESOLUTION: (
            "The photograph resolves too little detail to read the print at the"
            " size it was meant to be read."
        ),
        flag_ids.QUALITY_SKEW: (
            "The page was captured off its own plane, so its lines run at an angle"
            " no reading of it expects."
        ),
        flag_ids.QUALITY_LOW_COVERAGE: (
            "The card fills too little of the frame to be read out of what was"
            " captured."
        ),
        flag_ids.QUALITY_CROPPED: (
            "An edge of the card is cut off, so part of the page is not in the"
            " frame at all."
        ),
        flag_ids.MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH: (
            "The check digits printed over the document number do not match the"
            " number printed beneath them."
        ),
        flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH: (
            "The check digits printed over the date of birth do not match that"
            " date."
        ),
        flag_ids.MRZ_EXPIRY_CHECK_DIGIT_MISMATCH: (
            "The check digits printed over the date of expiry do not match that"
            " date."
        ),
        flag_ids.MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH: (
            "The check digits printed over the optional data do not match the"
            " optional data."
        ),
        flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH: (
            "The single check digit printed over the whole machine-readable zone"
            " does not match what that zone spells out."
        ),
        flag_ids.DATE_EXPIRED: (
            "The printed date of expiry falls before the date the scan compared it"
            " against."
        ),
        flag_ids.DATE_NOT_YET_VALID: (
            "The printed validity of the document has not opened yet on the date"
            " the scan compared it against."
        ),
        flag_ids.DATE_IMPLAUSIBLE_DOB: (
            "The printed date of birth is in the future, or implies an age no"
            " living person could have reached."
        ),
        flag_ids.DATE_ISSUE_AFTER_EXPIRY: (
            "The printed date of issue falls after the printed date of expiry."
        ),
        flag_ids.DATE_IMPOSSIBLE: (
            "The printed date cannot exist, so the field was not read as a real"
            " date."
        ),
        flag_ids.WATCHLIST_HIT: (
            "The document number appears on the blacklist this deployment checks"
            " against."
        ),
        flag_ids.WATCHLIST_STOLEN_DOCUMENT: (
            "The document number is recorded as stolen."
        ),
        flag_ids.WATCHLIST_IDENTITY_SEEN: (
            "The same name and date of birth were screened here before."
        ),
        flag_ids.OCR_MRZ_MISMATCH: (
            "A field read off the printed page disagrees with the same field in"
            " the machine-readable zone."
        ),
        flag_ids.OCR_LOW_CONFIDENCE: (
            "A field is still read with low confidence after a second look, so"
            " what it says may be wrong."
        ),
        flag_ids.OCR_BARCODE_MISMATCH: (
            "The barcode payload disagrees with the field printed beside it."
        ),
        flag_ids.LAYOUT_DEVIATION: (
            "A field sits outside the place the document template puts it."
        ),
        flag_ids.FACE_LOW_SIMILARITY: (
            "The photograph and the live capture are not similar enough for the"
            " match to be read as the same person."
        ),
        flag_ids.FACE_MISMATCH: (
            "The photograph and the live capture are the same person as far as the"
            " comparison can tell, and they disagree."
        ),
        flag_ids.TAMPER_ELA_ANOMALY: (
            "Error-level analysis found a block of the image that recompresses"
            " differently from the rest of it."
        ),
        flag_ids.TAMPER_NOISE_RESIDUAL_ANOMALY: (
            "Noise-residual analysis found local variation that the paper around"
            " it does not have."
        ),
        flag_ids.TAMPER_COPY_MOVE_ANOMALY: (
            "Self-similarity matching found a region of the page duplicated"
            " somewhere else on it."
        ),
        flag_ids.TAMPER_FUSION_ANOMALY: (
            "The three forensic modules together scored this page outside the"
            " range they agree on."
        ),
        flag_ids.TAMPER_STAMP_ANOMALY: (
            "A stamp on the page disagrees with the stamp templates this"
            " deployment holds."
        ),
        flag_ids.TAMPER_MORPH_SUSPECTED: (
            "The morph classifier scored this photograph as a face that has been"
            " altered."
        ),
        flag_ids.TAMPER_DEEPFAKE_SUSPECTED: (
            "The synthetic-image classifier scored this photograph as generated"
            " rather than photographed."
        ),
        flag_ids.TAMPER_OUT_OF_DISTRIBUTION: (
            "This page looks unlike every forgery style the anomaly detector was"
            " trained on."
        ),
        flag_ids.CROSSDOC_NAME_MISMATCH: (
            "The same person's name is written differently across two documents in"
            " this case."
        ),
        flag_ids.CROSSDOC_UNKNOWN_PASSPORT_REFERENCE: (
            "A visa in this case refers to a passport number that is not among the"
            " documents in the case."
        ),
        flag_ids.CROSSDOC_VALIDITY_WINDOW_MISMATCH: (
            "A document's validity window does not cover the travel date written"
            " on the other document."
        ),
        flag_ids.CROSSDOC_FACE_MISMATCH: (
            "The same face does not match across two documents in this case, or"
            " the comparison could not be made and said so."
        ),
    }
)


def reason_for(flag: object) -> str:
    """The plain-language sentence ``flag``'s id always has, with no model in it.

    :param flag: anything carrying an ``id``.  Only that one attribute is read,
        so a finding cannot put its own values into the sentence.
    :returns: the template held for that id in :data:`REASON_TEMPLATES`.
    :raises FlagValueError: when the id is missing, is not text, or is not one
        the registry knows.
    """
    flag_id = _id_of(flag)
    return REASON_TEMPLATES[flag_id]


def _id_of(flag: object) -> str:
    """The id ``flag`` carries, if the table holds a sentence for it.

    **A refusal names the rule and never repeats the value**, on the same
    grounds as every other message in this package: an id arriving here is
    caller-supplied, and a traceback is a place printed text ends up.
    """
    try:
        flag_id = flag.id
    except AttributeError:
        raise FlagValueError("a flag must carry an 'id' to be explained") from None
    if not isinstance(flag_id, str) or flag_id not in REASON_TEMPLATES:
        raise FlagValueError(
            "an id must be text and one of the flag ids in app.risk.flag_ids to be"
            " explained"
        )
    return flag_id
