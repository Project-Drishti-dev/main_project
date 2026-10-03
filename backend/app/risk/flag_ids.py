"""Every flag id the system can emit, written down once and in one place.

:attr:`~app.risk.flags.EvidenceFlag.id` is a stable machine name and nothing
checks it, so the set of legal ids has to live somewhere a rule can import
rather than in the head of whoever wrote the rule.  This module is that
somewhere: the constant is named after the id it holds, so reading
``flag_ids.MRZ_DOB_CHECK_DIGIT_MISMATCH`` and reading the id a rule assigns are
the same lookup and cannot drift apart.

:data:`FLAG_IDS` is the set 7.1's weightset completeness test is written
against, and :data:`PREFIXES` is the list of the nine families those ids are
named in.  **The prefixes are the only source of truth for the families**, so a
tenth family is a change to this list rather than a string somebody typed in a
module and hoped for.  14.3 opened the ninth: the quality gate's nine checks
run as stage 0, and a check that failed is a finding of its own.

**An id names a rule, not a condition and not a field.**  The four date rules of
5.4 to 5.7 hold four ids however many ways each can fire, and one printed
check-digit failure holds one id across all three formats.  Which field a
finding is about is 6.2's question, which :attr:`EvidenceFlag` answered by
growing a ``field`` slot rather than by letting a field name reach an id
(`D17`); this list stayed at one id per printed digit, and still does.

Nothing here imports anything.  The weightset loader, the verifier and the
frontend payload all read this list, and none of them should have to import
OpenCV to learn what a flag may be called.
"""

#: The nine families, in the order the cascade runs them: the quality gate
#: first, then tier 0, tier 1, tier 2, then the cross-document rules.  Ordered
#: rather than a set because the order is the cascade, and a test reads the ids
#: back against it.
PREFIXES = (
    "QUALITY",
    "MRZ",
    "DATE",
    "WATCHLIST",
    "OCR",
    "LAYOUT",
    "FACE",
    "TAMPER",
    "CROSSDOC",
)

# --- QUALITY: the capture gate's nine checks, which run as stage 0 (14.3) ---

#: The capture is too blurred to read, against the sharpness module's own floor.
#: **A statement about the photograph rather than about the document**, and
#: weighted as one: it says this image of the page cannot be judged, never that
#: the page is forged.
QUALITY_BLUR = "QUALITY_BLUR"
#: The capture carries sensor noise above the noise module's own ceiling.
QUALITY_NOISE = "QUALITY_NOISE"
#: The capture is under- or over-exposed against the exposure module's band.
QUALITY_EXPOSURE = "QUALITY_EXPOSURE"
#: The page is lit unevenly enough that one part of it reads darker than the
#: rest, so a field's ink is judged against a background that moved.
QUALITY_UNEVEN_LIGHTING = "QUALITY_UNEVEN_LIGHTING"
#: A reflection covers enough of the card to hide what is underneath it.
QUALITY_GLARE = "QUALITY_GLARE"
#: The capture resolves fewer pixels per inch than the page is read at.
QUALITY_LOW_RESOLUTION = "QUALITY_LOW_RESOLUTION"
#: The page is photographed or scanned far off its own plane, so its lines run
#: at an angle no reading of it expects.
QUALITY_SKEW = "QUALITY_SKEW"
#: The card fills too little of the frame to be read out of what was captured.
QUALITY_LOW_COVERAGE = "QUALITY_LOW_COVERAGE"
#: An edge of the card is cut off, so part of the page is not in the frame at
#: all rather than merely hard to see.
QUALITY_CROPPED = "QUALITY_CROPPED"

# --- MRZ: the printed check digits, one id per digit the standard defines ---

#: The digits over the document number do not compute to the digit printed.
MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH = "MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH"
#: The digits over the date of birth, worked example A of the abstract.
MRZ_DOB_CHECK_DIGIT_MISMATCH = "MRZ_DOB_CHECK_DIGIT_MISMATCH"
#: The digits over the date of expiry.
MRZ_EXPIRY_CHECK_DIGIT_MISMATCH = "MRZ_EXPIRY_CHECK_DIGIT_MISMATCH"
#: The digits over the optional-data field -- TD1's optional data, TD2's
#: optional data, TD3's personal number -- which are three printed digits and
#: one rule, so they share one weight rather than holding a rule per format.
MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH = "MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH"
#: The composite digit over the spans the standard names, which is the one
#: check digit that would catch a substitution inside a single value class.
MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH = "MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH"

# --- DATE: the deterministic rules of 5.4 to 5.7, and an impossible date ---

#: The date of expiry is before the injected reference date.
DATE_EXPIRED = "DATE_EXPIRED"
#: The document's validity has not opened yet on the reference date.
DATE_NOT_YET_VALID = "DATE_NOT_YET_VALID"
#: The date of birth is in the future, or implies an age over the configured
#: maximum.  Both are the one rule 5.6 states, so both carry one id.
DATE_IMPLAUSIBLE_DOB = "DATE_IMPLAUSIBLE_DOB"
#: The issue date is later than the date of expiry.
DATE_ISSUE_AFTER_EXPIRY = "DATE_ISSUE_AFTER_EXPIRY"
#: The six printed characters cannot be a real day at all -- a month of 99, a
#: day of 32 -- which is ``mrz.date_fault`` rather than an unreadable field.
DATE_IMPOSSIBLE = "DATE_IMPOSSIBLE"

# --- WATCHLIST: the three kinds of hit the seed of 5.10 can hold ---

#: The document number is on the blacklist.  The abstract's hard rule beside a
#: broken checksum, and ROADMAP B1.8's spelling for the same thing.
WATCHLIST_HIT = "WATCHLIST_HIT"
#: The document number is recorded as stolen.  Heavy-weighted, not a hard fail.
WATCHLIST_STOLEN_DOCUMENT = "WATCHLIST_STOLEN_DOCUMENT"
#: The name and date of birth are an identity already screened here.  A lookup
#: hit and not a verdict: what a previous outcome is worth is 7.13's question.
WATCHLIST_IDENTITY_SEEN = "WATCHLIST_IDENTITY_SEEN"

# --- OCR, layout and face: what tier 1 reads off the printed page ---

#: A visible field disagrees with the MRZ field it is expected to match, with
#: transliteration tolerance for names.  One id for every field, as 12.15 and
#: ROADMAP B4.4 state it, so the field is `expected`/`found` and not the id.
OCR_MRZ_MISMATCH = "OCR_MRZ_MISMATCH"
#: A field is still below confidence after the re-read and the fallback engine
#: of 12.9.  Reached only after those, so a mere misread never lands here.
OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
#: The decoded 2D barcode payload disagrees with the printed field it is
#: expected to match.  Named under ``OCR_`` rather than given a ninth family
#: because the eight prefixes are the only source of truth, and both readings
#: are read off this image.
OCR_BARCODE_MISMATCH = "OCR_BARCODE_MISMATCH"
#: A field sits outside its template tolerance once the document is aligned,
#: counting the font-style proxy of 13.10.
LAYOUT_DEVIATION = "LAYOUT_DEVIATION"
#: The document photograph and the live capture are below the match threshold,
#: which is worked example B and an escalation to tier 2 rather than a verdict.
FACE_LOW_SIMILARITY = "FACE_LOW_SIMILARITY"
#: The two faces are the same person, as far as the comparison can tell, and
#: they disagree.
FACE_MISMATCH = "FACE_MISMATCH"

# --- TAMPER: one id per tier 2 module, all of them labelled stubs ---

#: Error-level analysis finds a block that re-compresses differently.
TAMPER_ELA_ANOMALY = "TAMPER_ELA_ANOMALY"
#: Noise-residual analysis finds local variance the paper around it does not have.
TAMPER_NOISE_RESIDUAL_ANOMALY = "TAMPER_NOISE_RESIDUAL_ANOMALY"
#: Self-similarity matching finds a region duplicated inside the document.
TAMPER_COPY_MOVE_ANOMALY = "TAMPER_COPY_MOVE_ANOMALY"
#: The three forensic modules fused into 15.6's one score and one mask.
TAMPER_FUSION_ANOMALY = "TAMPER_FUSION_ANOMALY"
#: Stamp matching against the template registry disagrees with the stamp.
TAMPER_STAMP_ANOMALY = "TAMPER_STAMP_ANOMALY"
#: The morph classifier's stand-in scores this photograph as morphed.
TAMPER_MORPH_SUSPECTED = "TAMPER_MORPH_SUSPECTED"
#: The deepfake classifier's stand-in scores this photograph as synthetic.
TAMPER_DEEPFAKE_SUSPECTED = "TAMPER_DEEPFAKE_SUSPECTED"
#: The anomaly detector places this document outside the fixture's own
#: distribution -- a forgery style the training fixture never held.
TAMPER_OUT_OF_DISTRIBUTION = "TAMPER_OUT_OF_DISTRIBUTION"

# --- CROSSDOC: one id per rule comparing two documents in one case ---

#: The same person's name differs across two documents beyond tolerance.
CROSSDOC_NAME_MISMATCH = "CROSSDOC_NAME_MISMATCH"
#: A visa references a passport number that is not in the case.
CROSSDOC_UNKNOWN_PASSPORT_REFERENCE = "CROSSDOC_UNKNOWN_PASSPORT_REFERENCE"
#: A document's validity window does not cover the travel date.
CROSSDOC_VALIDITY_WINDOW_MISMATCH = "CROSSDOC_VALIDITY_WINDOW_MISMATCH"
#: The same face does not match across two documents, or the comparison could
#: not be made and said so.
CROSSDOC_FACE_MISMATCH = "CROSSDOC_FACE_MISMATCH"

#: Every id, in :data:`PREFIXES` order.  This tuple is the list of record:
#: a new id is one constant above and one name here, and
#: ``test_flag_ids.py`` holds the two apart.
ALL_FLAG_IDS = (
    QUALITY_BLUR,
    QUALITY_NOISE,
    QUALITY_EXPOSURE,
    QUALITY_UNEVEN_LIGHTING,
    QUALITY_GLARE,
    QUALITY_LOW_RESOLUTION,
    QUALITY_SKEW,
    QUALITY_LOW_COVERAGE,
    QUALITY_CROPPED,
    MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH,
    MRZ_DOB_CHECK_DIGIT_MISMATCH,
    MRZ_EXPIRY_CHECK_DIGIT_MISMATCH,
    MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH,
    MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH,
    DATE_EXPIRED,
    DATE_NOT_YET_VALID,
    DATE_IMPLAUSIBLE_DOB,
    DATE_ISSUE_AFTER_EXPIRY,
    DATE_IMPOSSIBLE,
    WATCHLIST_HIT,
    WATCHLIST_STOLEN_DOCUMENT,
    WATCHLIST_IDENTITY_SEEN,
    OCR_MRZ_MISMATCH,
    OCR_LOW_CONFIDENCE,
    OCR_BARCODE_MISMATCH,
    LAYOUT_DEVIATION,
    FACE_LOW_SIMILARITY,
    FACE_MISMATCH,
    TAMPER_ELA_ANOMALY,
    TAMPER_NOISE_RESIDUAL_ANOMALY,
    TAMPER_COPY_MOVE_ANOMALY,
    TAMPER_FUSION_ANOMALY,
    TAMPER_STAMP_ANOMALY,
    TAMPER_MORPH_SUSPECTED,
    TAMPER_DEEPFAKE_SUSPECTED,
    TAMPER_OUT_OF_DISTRIBUTION,
    CROSSDOC_NAME_MISMATCH,
    CROSSDOC_UNKNOWN_PASSPORT_REFERENCE,
    CROSSDOC_VALIDITY_WINDOW_MISMATCH,
    CROSSDOC_FACE_MISMATCH,
)

#: Every id as a set, which is what 7.1's completeness test and 7.3's lookup
#: are written against.  Built from :data:`ALL_FLAG_IDS`, never from a second
#: literal, so the two cannot disagree about what exists.
FLAG_IDS = frozenset(ALL_FLAG_IDS)

#: Derived from the constants for the same reason: adding an id is one edit in
#: this module rather than two, and a test reads ``__all__`` back against
#: :data:`ALL_FLAG_IDS`.
__all__ = ("ALL_FLAG_IDS", "FLAG_IDS", "PREFIXES") + ALL_FLAG_IDS
