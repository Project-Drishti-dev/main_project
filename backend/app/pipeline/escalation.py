"""14.6 -- the ambiguity check: ``R1`` inside a configurable band escalates.

:func:`check_ambiguity` asks :class:`AmbiguityBand` one question of
``ScreeningContext.r1``.  Inside the band it appends a reason to
``context.escalations``; outside it, or before Tier 1 has run, it writes
nothing and returns ``False``.  The band defaults to :func:`default_band`,
read from the committed thresholds per call; D109 holds why the band is
closed at its own top, and why an escalation is a reason and not a bool.

:func:`check_high_risk_profile` asks :class:`HighRiskProfile` whether the
claimed document type or the claimed issuing state is on one of its two
watchlists, and on a yes appends its own sentence beside the first.  A claim
nobody made is an absence rather than a hit, and the shipped profile names
nothing; D110 holds why both.

:func:`check_deep_audit` asks :class:`DeepAuditDraw` whether this run's id
draws a random audit, by ``HMAC(server_secret, screening_id) < rate``.  The
draw is a function of the secret and the id and of nothing else, so a case
cannot be re-drawn by asking twice; no secret is shipped, and the shipped
rate is zero.  D111 holds why both.

:func:`check_full_depth` asks ``context.depth_mode`` whether the checkpoint
is running the abstract full-depth cascade, and on a yes appends its own
sentence.  It takes nothing but the context, so there is nothing to
configure and nothing to read from disk; D112 holds why.
"""

import dataclasses
import hashlib
import hmac
import typing
import uuid

from app.pipeline.orchestrator import FULL_DEPTH
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import FlagValueError
from app.risk.hard_rules import _score

if typing.TYPE_CHECKING:
    from app.pipeline.orchestrator import ScreeningContext

__all__ = [
    "CHECK_NAME",
    "DEEP_AUDIT_CHECK_NAME",
    "FULL_DEPTH_CHECK_NAME",
    "HIGH_RISK_PROFILE_CHECK_NAME",
    "SHIPPED_DEEP_AUDIT_RATE",
    "SHIPPED_DOCUMENT_TYPES",
    "SHIPPED_ISSUING_STATES",
    "AmbiguityBand",
    "DeepAuditDraw",
    "HighRiskProfile",
    "check_ambiguity",
    "check_deep_audit",
    "check_full_depth",
    "check_high_risk_profile",
    "default_band",
    "default_draw",
    "default_profile",
]

#: The name 14.6's trigger is known by, **left as it was named** when it
#: was the only one so that its test keeps the claim it was written against.
CHECK_NAME = "ambiguity"

#: The name 14.7's trigger is known by.  **Prefixed, as every trigger after
#: the first is**, so 14.8 and 14.9 add theirs beside it and none collides.
HIGH_RISK_PROFILE_CHECK_NAME = "high_risk_profile"

#: The document types on the shipped profile.  **Empty, deliberately**: the
#: abstract names the trigger but never the list, so a list shipped here
#: would be policy this repository never recorded (D22).  An agency fills
#: it in, and filling it in is a change to record.
SHIPPED_DOCUMENT_TYPES: frozenset[str] = frozenset()

#: The issuing states on the shipped profile, on the same terms as the types
#: above: nothing is listed until a deployment records what it lists.
SHIPPED_ISSUING_STATES: frozenset[str] = frozenset()

#: The name 14.8's trigger is known by, prefixed as 14.7's is.
DEEP_AUDIT_CHECK_NAME = "deep_audit"

#: The share of screenings the shipped draw escalates.  **Zero, deliberately**:
#: the abstract says a random sample of low-risk documents still receives deep
#: analysis and never says how large a sample, so any number here would be
#: policy this repository never recorded (D111, on D110's and D22's grounds).
SHIPPED_DEEP_AUDIT_RATE = 0.0

#: The name 14.9 trigger is known by, prefixed as 14.7 and 14.8 are.
FULL_DEPTH_CHECK_NAME = "full_depth"


@dataclasses.dataclass(frozen=True)
class AmbiguityBand:
    """One range of ``R1`` that escalates: above ``low_max``, up to ``review_max``.

    :param low_max: the top of the band below, which is **not** ambiguous.
    :param review_max: the top of this band, which **is** ambiguous.
    :raises FlagValueError: when an edge is not a finite real number, or the
        pair is not a range.
    """

    low_max: float
    review_max: float

    def __post_init__(self) -> None:
        """Refuse a bad edge and a pair that could not be read as a range."""
        low = _score("low_max", self.low_max)
        high = _score("review_max", self.review_max)
        if low >= high:
            raise FlagValueError(
                "an ambiguity band is a range: low_max must be below "
                "review_max, and got "
                f"{low:g} and {high:g}"
            )

    def contains(self, r1: object) -> bool:
        """Whether ``r1`` falls inside the band, both edges read as 7.9 reads.

        :param r1: the finished partial score to read.
        :returns: ``True`` when ``low_max < r1 <= review_max``.
        :raises FlagValueError: when ``r1`` is not a finite real number.
        """
        return self.low_max < _score("r1", r1) <= self.review_max


def default_band() -> AmbiguityBand:
    """The committed ambiguity band, read per call rather than frozen here."""
    return AmbiguityBand(LOW_MAX, REVIEW_MAX)


def check_ambiguity(
    context: "ScreeningContext", *, band: AmbiguityBand | None = None
) -> bool:
    """Escalate ``context`` when its ``R1`` is inside ``band``.

    :param context: the run's record; ``escalations`` is the only field that
        grows, and nothing on it is hard failed or stopped.
    :param band: the band to read; defaults to :func:`default_band`.
    :returns: whether this call escalated.
    :raises FlagValueError: when ``band`` is not an :class:`AmbiguityBand`, or
        ``context.r1`` is not a finite real number.
    """
    if band is None:
        band = default_band()
    elif not isinstance(band, AmbiguityBand):
        raise FlagValueError(
            f"band must be an AmbiguityBand, not {type(band).__name__}"
        )
    if context.r1 is None:
        return False
    if not band.contains(context.r1):
        return False
    context.escalations.append(
        f"R1 of {context.r1:g} falls in the ambiguous band "
        f"({band.low_max:g}, {band.review_max:g}]."
    )
    return True

def _entry(field: str, entry: object) -> str:
    """One watchlist entry, folded to the spelling a claim is folded to.

    :param field: the list's own name, for the refusal's message.
    :param entry: one value a caller listed.
    :returns: ``entry`` trimmed and lower-cased.
    :raises FlagValueError: when ``entry`` is not a non-empty string.
    """
    if not isinstance(entry, str):
        raise FlagValueError(
            f"a {field} entry must be a string, not {type(entry).__name__}"
        )
    if not entry.strip():
        raise FlagValueError(f"a {field} entry must not be empty")
    return entry.strip().lower()


def _claim(field: str, value: object) -> str | None:
    """The claim to compare against a watchlist, folded the same way.

    :param field: the context field's name, for the refusal's message.
    :param value: what the document claims, or ``None`` for no claim at all.
    :returns: ``value`` trimmed and lower-cased, or ``None``.
    :raises FlagValueError: when ``value`` is neither ``None`` nor a string.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise FlagValueError(
            f"{field} must be a string or None, not {type(value).__name__}"
        )
    return value.strip().lower()


@dataclasses.dataclass(frozen=True)
class HighRiskProfile:
    """Two watchlists of claim values: document types, and issuing states.

    :param document_types: the document types that escalate on their own.
    :param issuing_states: the issuing-state codes that escalate on their own.
    :raises FlagValueError: when an entry is not a non-empty string.
    """

    document_types: frozenset[str] = frozenset()
    issuing_states: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Fold both lists to one spelling, so a comparison needs no guessing."""
        for field, entries in (
            ("document_types", self.document_types),
            ("issuing_states", self.issuing_states),
        ):
            object.__setattr__(
                self,
                field,
                frozenset(_entry(field, entry) for entry in entries),
            )

    def matches(self, document_type: object, issuing_state: object) -> bool:
        """Whether either claim is on the watchlist of its own half.

        :param document_type: the claimed type, or ``None`` for no claim.
        :param issuing_state: the claimed issuing state, or ``None``.
        :returns: ``True`` when either is listed.
        :raises FlagValueError: when a claim is neither ``None`` nor a string.
        """
        return (
            _claim("document_type", document_type) in self.document_types
            or _claim("issuing_state", issuing_state) in self.issuing_states
        )


def default_profile() -> HighRiskProfile:
    """The shipped profile, built from the committed lists per call."""
    return HighRiskProfile(SHIPPED_DOCUMENT_TYPES, SHIPPED_ISSUING_STATES)


def check_high_risk_profile(
    context: "ScreeningContext", *, profile: HighRiskProfile | None = None
) -> bool:
    """Escalate ``context`` when its type or issuing state is on ``profile``.

    :param context: the run's record; ``escalations`` is the only field that
        grows, and nothing on it is hard failed or stopped.
    :param profile: the watchlist to read; defaults to :func:`default_profile`.
    :returns: whether this call escalated.
    :raises FlagValueError: when ``profile`` is not a
        :class:`HighRiskProfile`, or a claim is neither ``None`` nor a string.
    """
    if profile is None:
        profile = default_profile()
    elif not isinstance(profile, HighRiskProfile):
        raise FlagValueError(
            f"profile must be a HighRiskProfile, not {type(profile).__name__}"
        )
    document_type = _claim("document_type", context.document_type)
    issuing_state = _claim("issuing_state", context.issuing_state)
    if document_type in profile.document_types:
        reason = (
            f"The document type {context.document_type.strip()!r} is on "
            "the high-risk profile watchlist."
        )
    elif issuing_state in profile.issuing_states:
        reason = (
            f"The issuing state {context.issuing_state.strip()!r} is on "
            "the high-risk profile watchlist."
        )
    else:
        return False
    context.escalations.append(reason)
    return True


def _secret(field: str, value: object) -> bytes:
    """The server secret as bytes, or a refusal naming the field.

    :param field: the field's own name, for the refusal's message.
    :param value: the secret a deployment configured.
    :returns: ``value`` as non-empty bytes.
    :raises FlagValueError: when it is not non-empty bytes.
    """
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise FlagValueError(
            f"{field} must be bytes, not {type(value).__name__}"
        )
    if not value:
        raise FlagValueError(f"{field} must not be empty")
    return bytes(value)


#: The bytes of a digest that carry the draw, and the range they span.
#: **Eight of the thirty-two**: they are already one part in ``2**64``, which
#: no rate a deployment configures can tell from a wider read.
_DRAW_BYTES = 8
_DRAW_SPAN = float(1 << (8 * _DRAW_BYTES))


def _unit(digest: bytes) -> float:
    """A digest read as a number in ``[0, 1)``, big-endian off the front.

    :param digest: an HMAC digest, or its leading bytes.
    :returns: the first :data:`_DRAW_BYTES` bytes as a fraction of their span.
    """
    return int.from_bytes(digest[:_DRAW_BYTES], "big") / _DRAW_SPAN


@dataclasses.dataclass(frozen=True)
class DeepAuditDraw:
    """One draw: the share to escalate, and the secret it is keyed by.

    :param rate: the share of screenings escalated, as a probability.
    :param secret: the server secret, as non-empty bytes.
    :raises FlagValueError: when the rate is not a probability in ``[0, 1]``,
        or the secret is not non-empty bytes.
    """

    rate: float
    secret: bytes

    def __post_init__(self) -> None:
        """Refuse a rate that is not a probability; fold both to one value."""
        rate = _score("rate", self.rate)
        if not 0.0 <= rate <= 1.0:
            raise FlagValueError(
                "a deep audit rate is a probability in [0, 1], and got "
                f"{rate:g}"
            )
        object.__setattr__(self, "rate", rate)
        object.__setattr__(self, "secret", _secret("secret", self.secret))

    def draws(self, screening_id: object) -> bool:
        """Whether this draw escalates ``screening_id``.

        :param screening_id: the run's id, which the context already holds as
            a :class:`uuid.UUID`.
        :returns: ``True`` when ``HMAC(secret, screening_id) < rate``.
        :raises FlagValueError: when the id is not a :class:`uuid.UUID`.
        """
        if not isinstance(screening_id, uuid.UUID):
            raise FlagValueError(
                "screening_id must be a uuid.UUID, not "
                f"{type(screening_id).__name__}"
            )
        message = str(screening_id).encode("ascii")
        mac = hmac.new(self.secret, message, hashlib.sha256)
        return _unit(mac.digest()) < self.rate


def default_draw(secret: bytes) -> DeepAuditDraw:
    """The shipped draw: the committed rate, keyed by the caller's secret.

    :param secret: the deployment's server secret, as non-empty bytes.
    :returns: a fresh draw, built per call from :data:`SHIPPED_DEEP_AUDIT_RATE`.
    :raises FlagValueError: when the secret is not non-empty bytes.
    """
    return DeepAuditDraw(SHIPPED_DEEP_AUDIT_RATE, secret)


def check_deep_audit(context: "ScreeningContext", *, draw: DeepAuditDraw) -> bool:
    """Escalate ``context`` when its id draws the random deep audit.

    :param context: the run's record; only ``escalations`` grows.
    :param draw: the draw to read.  **Required**: it is keyed by a secret no
        deployment ships, so there is nothing here to default to.
    :returns: whether this call escalated.
    :raises FlagValueError: when ``draw`` is not a :class:`DeepAuditDraw`.
    """
    if not isinstance(draw, DeepAuditDraw):
        raise FlagValueError(
            f"draw must be a DeepAuditDraw, not {type(draw).__name__}"
        )
    if not draw.draws(context.screening_id):
        return False
    context.escalations.append(
        f"Drawn for a random deep audit at a rate of {draw.rate:g}."
    )
    return True


def check_full_depth(context: "ScreeningContext") -> bool:
    """Escalate ``context`` when the checkpoint is running at full depth.

    :param context: the record for this run; only ``escalations`` grows.
    :returns: whether this call escalated, which is the whole answer here:
        full depth escalates every screening and no other depth any.
    """
    if context.depth_mode != FULL_DEPTH:
        return False
    context.escalations.append(
        "The checkpoint is running in full-depth mode."
    )
    return True
