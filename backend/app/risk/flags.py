"""One structured finding: the record every rule in this project answers with.

Nothing here decides anything.  A rule produces a flag and says nothing about
what it means; the weight it carries comes from a versioned weightset and the
band the score lands in is a later question again.  Keeping the three apart is
what lets a ruleset change without re-running a scan, and lets a score be
recomputed from flags that were recorded under an older one.

The shape of a flag is checked where one is built rather than assumed on the
way in: :attr:`~app.risk.flags.EvidenceFlag.value` and
:attr:`~app.risk.flags.EvidenceFlag.confidence` are real numbers in the closed
unit interval, :attr:`~app.risk.flags.EvidenceFlag.weight_band` is one of
:data:`WEIGHT_BANDS`, and :attr:`~app.risk.flags.EvidenceFlag.region` is a
polygon of whole-pixel corners or ``None``.  A malformed field raises
:exc:`FlagValueError` and is never coerced or clipped into something legal;
``D6`` in ``docs/DECISIONS.md`` records why, and what each check deliberately
does not decide.
"""

import dataclasses
import numbers

__all__ = ["EvidenceFlag", "FlagValueError", "MIN_REGION_CORNERS", "WEIGHT_BANDS"]

#: The bands a flag's weight may sit in: ``low``, ``review`` and ``high``, the
#: three ``tasks.md`` names.  Frozen because Part 7's weightset is read against
#: it, and a set a caller could add to would let a weightset validate itself.
WEIGHT_BANDS = frozenset({"low", "review", "high"})

#: Three corners is the floor for a polygon: two are a segment and enclose no
#: area, so a highlight drawn over them draws nothing at all.
MIN_REGION_CORNERS = 3


class FlagValueError(ValueError):
    """Raised when a field of an :class:`EvidenceFlag` is not well formed.

    The risk package's own error type, and a ``ValueError`` so a caller already
    catching ``ValueError`` around the code that builds a flag keeps working.

    **A message names the rule that was broken and never repeats the value.**
    A malformed field is precisely where a line of printed text would arrive --
    a field name handed over as a region, an OCR string handed over as a band --
    and quoting it back would put that text into a traceback and a log.
    """


def _flag_id(flag: object, purpose: str) -> str:
    """The id ``flag`` carries, or a refusal naming the field it lacks.

    **One reader of ``id`` for the whole package**, because two modules need
    this question and :data:`app.risk.flag_ids.FLAG_IDS` does not check it
    (`D6`): 7.5's sum needs the id to look a weight up and 7.6's floor needs
    it to ask whether the rule overrides.  ``purpose`` is the half-sentence
    naming what the caller was about to do with the id, so a message says
    which of the two asked rather than only what was missing.

    **A raw ``AttributeError`` is not the answer.** A caller already catching
    :exc:`FlagValueError` around the code that scores a screening would not
    catch it, and a record that reached either question carrying no id is a
    caller bug rather than a finding.

    **An ``id`` that is not a string is refused too**, on
    :func:`_check_weight_band`'s reason: both questions are membership tests
    against a vocabulary of machine names, and an id of the wrong type is a
    record that cannot answer either.  ``D6`` checks neither at construction,
    because a rule whose id is not yet listed still has to be constructible
    while the rules are being written.
    """
    try:
        flag_id = flag.id
    except AttributeError:
        raise FlagValueError(
            f"a flag must carry an 'id' {purpose}"
        ) from None
    if not isinstance(flag_id, str):
        raise FlagValueError(
            f"id must be a string, not {type(flag_id).__name__}, {purpose}"
        )
    return flag_id


def _check_unit_interval(field: str, number: object) -> None:
    """Refuse ``number`` unless it is a real number inside the closed unit interval.

    **The comparison is chained**, ``0 <= number <= 1``, rather than a pair of
    ``<`` and ``>`` tests, so ``nan`` is refused instead of passing both halves
    of a comparison it fails in both directions.
    """
    if not isinstance(number, numbers.Real):
        raise FlagValueError(
            f"{field} must be a real number, not {type(number).__name__}"
        )
    if not 0 <= number <= 1:
        raise FlagValueError(f"{field} must lie in [0, 1]")


def _check_weight_band(band: object) -> None:
    """Refuse ``band`` unless it is one of :data:`WEIGHT_BANDS`.

    The type is tested before the membership because membership on an
    unhashable value raises ``TypeError``, and a flag that was built wrongly is
    refused with one error type.
    """
    if not isinstance(band, str) or band not in WEIGHT_BANDS:
        raise FlagValueError(
            "weight_band must be one of " + ", ".join(sorted(WEIGHT_BANDS))
        )


def _check_region(region: object) -> None:
    """Refuse ``region`` unless it is ``None`` or a polygon of whole-pixel corners.

    Each corner is a pair of integers of any integer type, so a numpy pixel out
    of a detector is not itself a rejection.  **Three things are deliberately
    not checked**: whether the corners enclose any area, whether they cross one
    another, and whether they run clockwise.  Those are properties of a
    highlight being drawn well rather than of a finding being well formed, and
    4.12's ``_box_polygon`` is the one writer whose corner order is a promise.
    """
    if region is None:
        return
    if not isinstance(region, tuple) or len(region) < MIN_REGION_CORNERS:
        raise FlagValueError(
            "region must be None or a tuple of at least "
            f"{MIN_REGION_CORNERS} corners"
        )
    for index, corner in enumerate(region):
        if not isinstance(corner, tuple) or len(corner) != 2:
            raise FlagValueError(f"region corner {index} must be an (x, y) pair")
        if not all(isinstance(coord, numbers.Integral) for coord in corner):
            raise FlagValueError(f"region corner {index} must hold whole pixels")


@dataclasses.dataclass(frozen=True)
class EvidenceFlag:
    """One finding, with everything an officer needs to judge it.

    **Two numbers, not one, and both on the same scale.**
    :attr:`value` is how strongly the finding itself speaks and
    :attr:`confidence` is how sure the module is of it.  They are separate
    fields because a certain weak signal and an unsure strong one are
    different rows, and a single column would have to average them into a
    number that means neither.  Neither is the document's risk score, and
    neither is a probability that the document is forged.

    :attr:`region` is a polygon of integer ``(x, y)`` pixel corners in the
    frame the module was handed, clockwise from the top left, or ``None`` when
    the finding cannot be located on this image.  **A box is the four-corner
    case of the same shape**, so one type covers both a whole field and a
    single line, and a highlight drawn over either is drawn the same way.
    ``None`` is a claim and not a gap: a finding with nowhere to point is
    still a finding, and it is listed rather than dropped.

    :attr:`expected` and :attr:`found` are the two halves of the comparison
    the finding made, and either may be ``None`` -- an unreadable field yields
    "expected 2, found unreadable", which says more than a refusal.  Both are
    short values: a digit, a date, a field name.  A flag never carries a line
    of printed text, so a flag cannot become a place identity data is stored.

    :attr:`tier` is ``0``, ``1``, ``2`` or ``"crossdoc"``, and
    :attr:`source_module`` is the module that produced the finding, so any
    claim can be traced to the code that made it.  :attr:`weight_band` names
    the band this flag's weight sits in; the number itself belongs to the
    weightset and is deliberately not held here.

    :attr:`field` names which field of the document the finding is about --
    ``"date_of_birth"``, ``"composite"`` -- or ``None`` for a finding that is
    not about one field.  **It is a name this code invented and never a value
    the document printed**, on the same grounds as every other message in
    this package, and it is last of the twelve, so a rule building a flag
    positionally cannot shift a meaning.  **It is required like the other
    eleven**, because a rule that has to answer "which field is this about"
    is a rule that cannot forget the question, and a finding about no one
    field says so with ``None`` rather than by leaving the slot out.
    :attr:`region` is
    where that field is on the image and :attr:`field` is what it is called,
    which are two questions and ``D5``'s reason the first cannot answer the
    second.  ``D17`` records why the name lives here rather than inside
    :attr:`id`.

    **Three fields are checked as the flag is built, and the other nine are
    not.**  :attr:`value` and :attr:`confidence` are real numbers in
    ``[0, 1]``, :attr:`weight_band` is one of :data:`WEIGHT_BANDS`, and
    :attr:`region` is a polygon of at least :data:`MIN_REGION_CORNERS` corners
    of whole pixels, or ``None``.  Anything else raises :exc:`FlagValueError`
    and nothing is coerced: a clipped ``1.4`` would be a finding that reads
    stronger than the one that was measured.

    **Frozen, for the reason
    :class:`~app.pipeline.tier0.td3.MrzDocument` and
    :class:`~app.pipeline.tier0.mrz.CheckDigitResult` are.**  A flag is
    evidence, and a record that could be edited would let a finding be
    tidied into a cleaner one that looks exactly like a read one.  It carries
    no *public* method for the same reason those records do not: a method on it
    would be a second opinion about what was found.  :meth:`__post_init__` is a
    check on the shape the caller handed over rather than an opinion, and it
    assigns nothing.
    """

    id: str
    tier: int | str
    label: str
    weight_band: str
    value: float
    confidence: float
    region: tuple[tuple[int, int], ...] | None
    expected: str | None
    found: str | None
    reason: str
    source_module: str
    field: str | None

    def __post_init__(self) -> None:
        """Check the three shape rules, assign nothing, and return ``None``."""
        _check_unit_interval("value", self.value)
        _check_unit_interval("confidence", self.confidence)
        _check_weight_band(self.weight_band)
        _check_region(self.region)
