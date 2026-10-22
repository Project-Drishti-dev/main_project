"""17.10 -- `build_flag_payload`: what the model is given, and what it is not.

The payload copies a flag field by field and leaves one of the twelve behind.
The cases below pin what it carries, pin the omission, and hold the result to
the verifier that reads the same text.
"""

import dataclasses
import json

import pytest

from app.explain import payload, template, verifier
from app.risk.flags import WEIGHT_BANDS, EvidenceFlag, FlagValueError
from app.risk.scoring import Contribution

build_flag_payload = payload.build_flag_payload

#: A flag as the cascade builds it, carrying a polygon whose corners are
#: distinctive enough that finding one of them in the payload would be plain.
FLAG = {
    "id": "DATE_EXPIRED",
    "tier": 0,
    "label": "Date of expiry is in the past",
    "weight_band": "high",
    "value": 0.87,
    "confidence": 0.91,
    "region": ((4211, 3897), (4402, 3911), (4388, 4102)),
    "expected": "2024-11-02",
    "found": "2023-11-02",
    "reason": "The printed expiry is before the reference date.",
    "source_module": "app.pipeline.tier0.dates",
    "field": "date_of_expiry",
}

OTHER_FLAG = {
    "id": "FACE_MISMATCH",
    "tier": 1,
    "label": "The two faces do not match",
    "weight_band": "high",
    "value": 0.79,
    "confidence": 0.88,
    "region": None,
    "expected": None,
    "found": None,
    "reason": "The two faces disagree.",
    "source_module": "app.pipeline.tier1.face",
    "field": None,
}

#: 7.11's row beside `FLAG`: ninety points at a strength of 0.87 is 78.3.
TERM = Contribution(id="DATE_EXPIRED", weight=90.0, value=0.87, contribution=78.3)


class _Partial:
    """A finding carrying an id and nothing else, so the copy stops at `tier`."""

    id = "DATE_EXPIRED"


class _PartialTerm:
    """A contribution carrying an id and nothing else, so it stops at `weight`."""

    id = "DATE_EXPIRED"


def _flag(**overrides):
    """The flag `FLAG` describes, as an :class:`EvidenceFlag`."""
    fields = dict(FLAG)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _other_flag(**overrides):
    """The flag `OTHER_FLAG` describes, as an :class:`EvidenceFlag`."""
    fields = dict(OTHER_FLAG)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _walk(value):
    """Every value inside `value`, the containers among them included."""
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)


@pytest.mark.parametrize("band", sorted(WEIGHT_BANDS))
def test_the_payload_names_the_band_the_score_read_as(band):
    built = build_flag_payload([], band, [])
    assert built.band == band
    assert json.loads(built.to_json())["band"] == band


def test_the_only_field_left_out_of_a_flag_is_its_region():
    carried = {field.name for field in dataclasses.fields(EvidenceFlag)}
    assert set(payload.SENT_FIELDS) | {"region"} == carried


def test_a_row_carries_the_eleven_fields_in_the_declared_order():
    row = build_flag_payload([_flag()], "review", []).flags[0].as_dict()
    assert tuple(row) == payload.SENT_FIELDS


def test_a_row_carries_every_field_it_is_copied_from():
    flag = _flag()
    row = build_flag_payload([flag], "review", []).flags[0].as_dict()
    for name in payload.SENT_FIELDS:
        assert row[name] == getattr(flag, name)


def test_the_findings_arrive_in_cascade_order_and_nothing_is_dropped():
    flags = [_flag(), _other_flag()]
    built = build_flag_payload(flags, "high", ())
    assert [row.id for row in built.flags] == ["DATE_EXPIRED", "FACE_MISMATCH"]


def test_the_payload_carries_one_contribution_row_per_finding():
    other = Contribution(
        id="FACE_MISMATCH", weight=70.0, value=0.79, contribution=55.3
    )
    rows = build_flag_payload(
        [_flag(), _other_flag()], "high", [TERM, other]
    ).as_dict()["contributions"]
    assert [term["id"] for term in rows] == ["DATE_EXPIRED", "FACE_MISMATCH"]
    assert rows[0] == dataclasses.asdict(TERM)


def test_a_flag_carrying_a_polygon_sends_no_pixel_data():
    text = build_flag_payload([_flag()], "review", []).to_json()
    assert "region" not in text
    for x, y in FLAG["region"]:
        assert str(x) not in text
        assert str(y) not in text


def test_the_payload_holds_no_block_of_bytes_wherever_it_is_read():
    built = build_flag_payload([_flag()], "review", [TERM])
    for value in _walk(built.as_dict()):
        assert not isinstance(value, (bytes, bytearray, memoryview))


def test_the_payload_is_json_and_reads_back_exactly_as_it_was_built():
    built = build_flag_payload([_flag()], "review", [TERM])
    assert json.loads(built.to_json()) == built.as_dict()


def test_the_payload_is_not_the_row_a_screening_stores_unchanged():
    flag = _flag()
    sent = build_flag_payload([flag], "review", []).as_dict()["flags"][0]
    assert sent != dataclasses.asdict(flag)


def test_the_payload_prints_as_the_json_the_prompt_carries():
    built = build_flag_payload([_flag()], "review", [TERM])
    assert str(built) == built.to_json()
    opening = '{"band": "review", "flags": [{"id": "DATE_EXPIRED"'
    assert str(built).startswith(opening)


def test_a_document_with_no_findings_is_still_a_payload():
    built = build_flag_payload([], "low", [])
    assert built.as_dict() == {"band": "low", "flags": [], "contributions": []}


def test_the_findings_are_read_once_so_a_generator_is_a_legal_argument():
    built = build_flag_payload(
        (f for f in [_flag(), _other_flag()]), "high", iter([TERM])
    )
    assert [row.id for row in built.flags] == ["DATE_EXPIRED", "FACE_MISMATCH"]
    assert [term.id for term in built.contributions] == ["DATE_EXPIRED"]


def test_the_payload_is_frozen_so_what_the_model_read_cannot_be_amended():
    built = build_flag_payload([_flag()], "review", [TERM])
    with pytest.raises(dataclasses.FrozenInstanceError):
        built.band = "high"


@pytest.mark.parametrize("band", ["", "Low", "critical", 3, None, ["low"]])
def test_a_band_the_registry_does_not_know_is_refused(band):
    with pytest.raises(FlagValueError):
        build_flag_payload([], band, [])


def test_a_finding_missing_a_field_the_payload_sends_is_refused():
    with pytest.raises(FlagValueError, match="tier"):
        build_flag_payload([_Partial()], "review", [])


def test_a_contribution_missing_the_numbers_it_owes_is_refused():
    with pytest.raises(FlagValueError, match="weight"):
        build_flag_payload([], "review", [_PartialTerm()])


def test_the_template_summary_passes_the_verifier_against_this_payload():
    flags = [_flag(), _other_flag()]
    summary = template.template_summary(flags, "review")
    held = build_flag_payload(flags, "review", [TERM])
    assert verifier.verify_summary(summary, held) == (True, ())
