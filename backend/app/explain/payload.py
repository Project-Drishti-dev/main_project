"""The flag data a model is given: findings, band and terms, and no pixels.

Eleven of the twelve fields on an :class:`app.risk.flags.EvidenceFlag` are
copied into a record that prints as the JSON a prompt carries, so what the
model reads and what the verifier searches are one rendering (`D139`).
`region` is the twelfth, and it is the only field that points at pixels:
it describes an image the model is never shown.
"""

import dataclasses
import json
from collections.abc import Iterable

from app.risk.flags import WEIGHT_BANDS, FlagValueError
from app.risk.scoring import Contribution

__all__ = ["FlagPayload", "FlagRow", "SENT_FIELDS", "build_flag_payload"]

#: The eleven fields of a flag that reach the model, in payload order.
#: `region` is absent from this line, and that absence is D139's rule.
SENT_FIELDS = (
    "id",
    "tier",
    "label",
    "weight_band",
    "value",
    "confidence",
    "expected",
    "found",
    "reason",
    "source_module",
    "field",
)

#: A contribution row's own field names, read off the record rather than
#: written out here, so a row cannot gain a field the payload would drop.
TERM_FIELDS = tuple(field.name for field in dataclasses.fields(Contribution))


@dataclasses.dataclass(frozen=True)
class FlagRow:
    """One finding as the model is shown it: the eleven sent fields.

    `region` is not a field of this row, so a flag carrying a polygon
    contributes no coordinate to anything that leaves the process.
    """

    id: str
    tier: int | str
    label: str
    weight_band: str
    value: float
    confidence: float
    expected: str | None
    found: str | None
    reason: str
    source_module: str
    field: str | None

    def as_dict(self) -> dict[str, object]:
        """The row as a JSON mapping, its keys in :data:`SENT_FIELDS` order."""
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class FlagPayload:
    """The band, the findings and the terms, as one frozen record.

    No total is held here: 7.11's rows are pre-history, and the score they
    do not add up to is the officer's number rather than the model's to
    be given.
    """

    band: str
    flags: tuple[FlagRow, ...]
    contributions: tuple[Contribution, ...]

    def as_dict(self) -> dict[str, object]:
        """The payload as a JSON mapping of band, flags and contributions."""
        return {
            "band": self.band,
            "flags": [row.as_dict() for row in self.flags],
            "contributions": [dataclasses.asdict(t) for t in self.contributions],
        }

    def to_json(self) -> str:
        """The one text a prompt carries and 17.3's verifier searches."""
        return json.dumps(self.as_dict(), ensure_ascii=False)

    def __str__(self) -> str:
        """:meth:`to_json`, so a summary can be held to the payload it was given."""
        return self.to_json()


def build_flag_payload(
    flags: Iterable[object],
    band: object,
    contributions: Iterable[object],
) -> FlagPayload:
    """The findings, the band and the terms as one payload for the model.

    `flags` are the findings in cascade order and `contributions` are
    7.11's rows beside them; both are read once and either may be empty.
    Raises :exc:`app.risk.flags.FlagValueError` on a band or a record it
    cannot read.
    """
    return FlagPayload(
        band=_band(band),
        flags=tuple(_row(flag) for flag in flags),
        contributions=tuple(_term(term) for term in contributions),
    )


def _band(band: object) -> str:
    """`band` if it is one of :data:`app.risk.flags.WEIGHT_BANDS`, else a refusal."""
    if not isinstance(band, str) or band not in WEIGHT_BANDS:
        raise FlagValueError("band must be one of " + ", ".join(sorted(WEIGHT_BANDS)))
    return band


def _row(flag: object) -> FlagRow:
    """The eleven sent fields of `flag`, read by name and copied onto a row."""
    return FlagRow(**{name: _field(flag, name, "flag") for name in SENT_FIELDS})


def _term(term: object) -> Contribution:
    """One contribution row copied onto a record of its own, detached from its source."""
    return Contribution(
        **{name: _field(term, name, "contribution") for name in TERM_FIELDS}
    )


def _field(record: object, name: str, noun: str) -> object:
    """The field `record` carries as `name`, or a refusal naming what it lacked."""
    try:
        return getattr(record, name)
    except AttributeError:
        raise FlagValueError(
            "a {0} must carry a {1!r} to reach the model".format(noun, name)
        ) from None
