"""17.5 -- `template_summary`: the fallback written with no model at all.

The frame is fixed, so the cases below pin its shape; a flag line is the flag's
own ``reason``, so they pin too that no wording is invented in this module.
"""

import dataclasses

import pytest

from app import explain
from app.explain import template, verifier
from app.risk import flag_ids
from app.risk.flags import WEIGHT_BANDS, EvidenceFlag, FlagValueError

template_summary = template.template_summary

#: Two flags as the pipeline already builds them, so the per-flag lines have
#: something to be in order against and something to differ in.
FLAG = {
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


def _flag(**overrides):
    """The flag :data:`FLAG` describes, as an :class:`EvidenceFlag`."""
    fields = dict(FLAG)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _other_flag(**overrides):
    """The flag :data:`OTHER_FLAG` describes, as an :class:`EvidenceFlag`."""
    fields = dict(OTHER_FLAG)
    fields.update(overrides)
    return EvidenceFlag(**fields)


def _frame(summary):
    """The summary's own sentences, with the per-flag lines taken out."""
    return [line for line in summary.splitlines() if not line.startswith("- ")]


def _lines(summary):
    """The summary's one line per flag."""
    return [line for line in summary.splitlines() if line.startswith("- ")]


@pytest.mark.parametrize("band", sorted(WEIGHT_BANDS))
def test_the_first_sentence_names_the_band_the_score_read_as(band):
    assert template_summary([], band).startswith(
        "This document reads as {0} risk.".format(band)
    )


@pytest.mark.parametrize("count", [0, 1, 2, 5])
def test_the_summary_is_three_sentences_whatever_number_of_flags_it_holds(count):
    frame = _frame(template_summary([_flag()] * count, "review"))
    assert len(frame) == 3
    assert all(line.endswith(".") for line in frame)


def test_each_flag_is_narrated_on_one_line_with_its_own_reason():
    summary = template_summary([_flag(), _other_flag()], "high")
    assert _lines(summary) == [
        "- DATE_EXPIRED: The printed expiry is before the reference date.",
        "- FACE_MISMATCH: The two faces disagree.",
    ]


def test_the_lines_follow_the_cascade_and_not_the_alphabet():
    summary = template_summary([_other_flag(), _flag()], "low")
    assert _lines(summary)[0].startswith("- FACE_MISMATCH")


def test_the_wording_is_the_rules_own_and_not_the_templates():
    loud = _lines(template_summary([_flag(reason="Nothing looked wrong.")], "low"))
    assert loud == ["- DATE_EXPIRED: Nothing looked wrong."]


def test_a_scan_that_raised_nothing_still_reads_as_three_sentences():
    summary = template_summary([], "low")
    assert _lines(summary) == []
    assert _frame(summary)[1] == "No check in the scan raised a finding."


def test_a_flag_with_no_reason_is_still_listed_by_its_id():
    summary = template_summary([_flag(reason="")], "low")
    assert _lines(summary) == ["- DATE_EXPIRED"]
    assert len(_frame(summary)) == 3


def test_a_flag_raised_twice_is_listed_once_per_flag():
    summary = template_summary([_flag(), _flag()], "low")
    assert _lines(summary) == [
        "- DATE_EXPIRED: The printed expiry is before the reference date.",
        "- DATE_EXPIRED: The printed expiry is before the reference date.",
    ]


@pytest.mark.parametrize("band", sorted(WEIGHT_BANDS))
@pytest.mark.parametrize("flags", [[], ["two"]])
def test_the_frame_writes_no_number_a_verifier_would_have_to_settle(band, flags):
    narrated = [_flag(), _other_flag()] if flags else []
    frame = "\n".join(_frame(template_summary(narrated, band)))
    assert verifier.extract_numbers(frame) == ()


@pytest.mark.parametrize("band", sorted(WEIGHT_BANDS))
@pytest.mark.parametrize("flags", [[], ["two"]])
def test_the_frame_writes_no_field_name_either(band, flags):
    narrated = [_flag(), _other_flag()] if flags else []
    frame = "\n".join(_frame(template_summary(narrated, band)))
    assert verifier.extract_field_names(frame) == ()


def test_the_summary_never_writes_the_flag_datas_own_field_name():
    assert "date_of_expiry" not in template_summary([_flag()], "low")


def test_the_template_reads_the_id_and_the_reason_and_nothing_else():
    class _IdAndReasonOnly:
        """A finding carrying only what a summary line may be built from."""

        def __init__(self, flag_id, reason):
            self.id = flag_id
            self.reason = reason

    summary = template_summary([_IdAndReasonOnly("DATE_EXPIRED", "It expired.")], "low")
    assert _lines(summary) == ["- DATE_EXPIRED: It expired."]


@pytest.mark.parametrize("band", ["Low", "HIGH", "medium", "", " low", None, 1, ["low"]])
def test_a_band_outside_the_three_is_refused(band):
    with pytest.raises(FlagValueError):
        template_summary([], band)


@pytest.mark.parametrize("missing", ["id", "reason"])
def test_a_flag_missing_what_a_line_is_built_from_is_refused(missing):
    fields = dataclasses.asdict(_flag())
    del fields[missing]
    with pytest.raises(FlagValueError):
        template_summary([type("Bare", (), fields)()], "low")


def test_a_flag_with_a_blank_id_is_refused():
    with pytest.raises(FlagValueError):
        template_summary([_flag(id="   ")], "low")


def test_a_reason_that_is_not_text_is_refused():
    with pytest.raises(FlagValueError):
        template_summary([_flag(reason=object())], "low")


def test_the_summary_is_one_string_with_no_trailing_blank_line():
    summary = template_summary([_flag()], "low")
    assert isinstance(summary, str)
    assert summary == summary.rstrip()


@pytest.mark.parametrize("flag_id", flag_ids.ALL_FLAG_IDS)
def test_every_id_in_the_registry_is_narrated_on_its_own_line(flag_id):
    summary = template_summary([_flag(id=flag_id)], "review")
    assert _lines(summary) == [
        "- " + flag_id + ": The printed expiry is before the reference date."
    ]


def test_the_package_re_exports_nothing_so_the_template_is_reached_from_its_module():
    assert not hasattr(explain, "template_summary")
