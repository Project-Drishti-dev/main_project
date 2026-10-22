"""17.6 -- the template summary passes the verifier: the fallback keeps 17.3's contract.

The model summary and the no-model fallback are held to one rule: every token a
summary carries is printed in the flag data.  These cases pin both directions, so
the pass cannot come from a verifier that answers everything yes.
"""

import dataclasses

import pytest

from app.explain import template, verifier
from app.risk import flag_ids
from app.risk.flags import WEIGHT_BANDS, EvidenceFlag

template_summary = template.template_summary
verify_summary = verifier.verify_summary

#: Two flags as `screening.py` stores them -- `dataclasses.asdict` of the
#: dataclass -- so the payload below is what a caller hands over unchanged.
FLAG_DATA = {
    "id": "DATE_EXPIRED",
    "tier": 0,
    "label": "Date of expiry is in the past",
    "weight_band": "high",
    "value": 0.87,
    "confidence": 0.91,
    "region": None,
    "expected": "2024-11-02",
    "found": "2023-11-02",
    "reason": "The printed expiry is before the reference date.",
    "source_module": "app.pipeline.tier0.dates",
    "field": "date_of_expiry",
}

OTHER_FLAG_DATA = {
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


def _flag(**overrides):
    """The flag :data:`FLAG_DATA` describes, as an :class:`EvidenceFlag`."""
    fields = dict(FLAG_DATA)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _other_flag(**overrides):
    """The flag :data:`OTHER_FLAG_DATA` describes, as an :class:`EvidenceFlag`."""
    fields = dict(OTHER_FLAG_DATA)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _stored(flags):
    """The payload a screening record holds for ``flags``, as it is stored."""
    return [dataclasses.asdict(flag) for flag in flags]


#: Two findings as the cascade hands them over: the dataclass is what a summary
#: is narrated from, and :func:`_stored` is what the verifier is handed.
FLAGS = (_flag(), _other_flag())

#: Every band over no flags, one flag and two, so no case is a special one.
CASES = tuple(
    (flags, band)
    for flags in ((), (_flag(),), FLAGS)
    for band in sorted(WEIGHT_BANDS)
)


@pytest.mark.parametrize("flags,band", CASES)
def test_the_fallback_passes_the_verifier_against_the_flags_it_narrates(flags, band):
    summary = template_summary(flags, band)
    assert verify_summary(summary, _stored(flags)) == (True, ())


@pytest.mark.parametrize("flags,band", CASES)
def test_the_answer_is_the_pair_the_model_output_is_held_to(flags, band):
    answer = verify_summary(template_summary(flags, band), _stored(flags))
    assert isinstance(answer, tuple) and len(answer) == 2
    assert isinstance(answer[0], bool)
    assert isinstance(answer[1], tuple)
    assert all(isinstance(token, str) for token in answer[1])


@pytest.mark.parametrize("flag", FLAGS)
def test_the_fallback_puts_the_flags_own_id_into_the_verifiers_hands(flag):
    summary = template_summary([flag], "low")
    assert verifier.extract_field_names(summary) == (flag.id,)


@pytest.mark.parametrize("flag", FLAGS)
def test_every_token_the_fallback_carries_is_printed_in_the_flag_data(flag):
    summary = template_summary([flag], "high")
    carried = (
        verifier.extract_numbers(summary)
        + verifier.extract_dates(summary)
        + verifier.extract_field_names(summary)
    )
    assert carried
    assert all(token in str(_stored([flag])) for token in carried)


def test_a_reason_carrying_its_own_numbers_and_dates_passes_on_the_flags_own_text():
    flag = _flag(reason="The expiry 2029-01-05 was read beside the value 0.42.")
    summary = template_summary([flag], "low")
    assert verifier.extract_dates(summary) == ("2029-01-05",)
    assert verifier.extract_numbers(summary) == ("2029", "01", "05", "0.42")
    assert verify_summary(summary, _stored([flag])) == (True, ())


@pytest.mark.parametrize("flags", [(_flag(),), FLAGS])
def test_the_same_summary_is_refused_against_data_carrying_none_of_those_flags(flags):
    summary = template_summary(flags, "high")
    passed, offending = verify_summary(summary, [])
    assert passed is False
    assert offending == tuple(flag.id for flag in flags)


@pytest.mark.parametrize("missing", FLAGS)
def test_each_line_is_settled_by_its_own_flags_data_and_by_no_other(missing):
    flags = [flag for flag in FLAGS if flag is not missing]
    passed, offending = verify_summary(
        template_summary(FLAGS, "high"), _stored(flags)
    )
    assert passed is False
    assert offending == (missing.id,)


def test_a_flag_with_no_reason_is_still_settled_against_its_own_data():
    flag = _flag(reason="")
    summary = template_summary([flag], "low")
    assert verify_summary(summary, _stored([flag])) == (True, ())
    assert verify_summary(summary, []) == (False, ("DATE_EXPIRED",))


@pytest.mark.parametrize("band", sorted(WEIGHT_BANDS))
def test_the_fallback_passes_against_the_nested_payload_a_screening_record_holds(band):
    flags = [_flag(), _other_flag()]
    payload = {"band": band, "flags": _stored(flags)}
    assert verify_summary(template_summary(flags, band), payload) == (True, ())


def test_the_fallback_passes_whether_the_flags_were_converted_first_or_not():
    flags = [_flag(), _other_flag()]
    summary = template_summary(flags, "review")
    assert verify_summary(summary, flags) == verify_summary(summary, _stored(flags))
    assert verify_summary(summary, flags) == (True, ())


@pytest.mark.parametrize("flag_id", flag_ids.ALL_FLAG_IDS)
def test_the_fallback_passes_for_every_flag_id_the_registry_knows(flag_id):
    flag = _flag(id=flag_id)
    summary = template_summary([flag], "review")
    assert verify_summary(summary, _stored([flag])) == (True, ())
