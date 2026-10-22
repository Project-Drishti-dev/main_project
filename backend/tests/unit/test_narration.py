"""17.11 -- the reject-and-fallback path: a refused summary is discarded.

The verifier answers a verdict, and this is what acts on it: model text that
fails is thrown away rather than repaired, 17.5's template stands in its
place, and the record names which of the two wrote the sentence and that
verification failed.  The cases below pin the discard, the two fields beside it,
and the promise that no text a model wrote survives in a record that refused it.
"""

import dataclasses
import json

import pytest

from app.explain import narration, payload, summarizer, template, verifier
from app.explain.prompts.loader import Prompt, load_prompt
from app.risk.flags import WEIGHT_BANDS, EvidenceFlag, FlagValueError
from app.risk.scoring import Contribution

narrate = narration.narrate
verify_summary = verifier.verify_summary

#: Two flags as `screening.py` stores them, and 7.11's row beside the first.
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

TERM = Contribution(id="DATE_EXPIRED", weight=90.0, value=0.87, contribution=78.3)

#: A model summary whose every token the payload prints, so 17.3 passes it.
SUPPORTED = "The DATE_EXPIRED finding and the FACE_MISMATCH finding are on file."

#: A second supported summary, this one quoting a number the payload prints.
SUPPORTED_VALUE = "The DATE_EXPIRED value was read as 0.87 beside the reference."

#: One refused summary per token kind 17.3 reads, and the tokens the refusal has
#: to name for it.  0.42 is the smallest token genuinely absent from this
#: payload, which 17.3 records: every other digit occurs inside a printed date.
REFUSED = (
    ("The scan read a 0.42 score on this document.", "number"),
    ("The printed expiry is 2029-01-05, so the document is stale.", "date"),
    ("The scan found a GHOST entry beside the DATE_EXPIRED finding.", "field-name"),
)

#: The same three refusals, with the offending tokens spelled out.  A date the
#: flags never printed offends the numbers inside it as well (D134), so that row
#: names four tokens rather than one.
REFUSED_TOKENS = {
    "number": ("0.42",),
    "date": ("2029", "2029-01-05", "01", "05"),
    "field-name": ("GHOST",),
}


class _Stub(summarizer.Summarizer):
    """A summariser answering one fixed text and recording every prompt it is given."""

    def __init__(self, text, model_name="stub-model"):
        self.model_name = model_name
        self.prompts = []
        self._text = text

    def summarize(self, prompt):
        """The stub's own text, however it was asked for it."""
        self.prompts.append(prompt)
        return self._text


def _without(name):
    """A finding carrying every field :data:`FLAG` holds but ``name``.

    Built out of :data:`FLAG` rather than written out beside it, so a partial
    record cannot quietly gain the field it is meant to be missing.
    """
    fields = {field: value for field, value in FLAG.items() if field != name}
    return type("Partial", (), fields)()


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


FLAGS = (_flag(), _other_flag())

#: Every band over no findings, one finding and two, so no case is a special one.
CASES = tuple(
    (flags, band)
    for flags in ((), (_flag(),), FLAGS)
    for band in sorted(WEIGHT_BANDS)
)


def _held(flags, band, contributions=()):
    """The flag data the verifier is handed, built exactly as 17.11 builds it."""
    return payload.build_flag_payload(flags, band, contributions)


def _refused(text, flags=FLAGS, band="review"):
    """The record a summariser writing ``text`` produced."""
    return narrate(flags, band, [TERM], _Stub(text))


# --- the refusal -------------------------------------------------------------


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refused_summary_is_not_the_text_the_model_wrote(text, ids):
    assert _refused(text).summary != text


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refused_summary_is_the_template_summary_instead(text, ids):
    assert _refused(text).summary == template.template_summary(FLAGS, "review")


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refused_summary_names_the_template_as_its_source(text, ids):
    assert _refused(text).summary_source == narration.TEMPLATE
    assert _refused(text).summary_source in narration.SUMMARY_SOURCES


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refused_summary_is_recorded_as_verification_failed(text, ids):
    assert _refused(text).verification == narration.FAILED
    assert _refused(text).verification == "failed"


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refusal_names_every_token_it_was_for(text, ids):
    assert set(_refused(text).unsupported) == set(REFUSED_TOKENS[ids])


@pytest.mark.parametrize("text,ids", REFUSED)
def test_no_part_of_a_refused_summary_survives_in_the_record(text, ids):
    record = _refused(text)
    assert text not in json.dumps(record.as_dict())
    for token in REFUSED_TOKENS[ids]:
        assert token not in record.summary


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refused_summary_names_no_model_because_no_model_wrote_it(text, ids):
    assert _refused(text).model_name is None


@pytest.mark.parametrize("text,ids", REFUSED)
def test_a_refused_summary_is_one_the_verifier_would_have_passed(text, ids):
    record = _refused(text)
    assert verify_summary(record.summary, _held(FLAGS, "review", [TERM])) == (True, ())


def test_a_refusal_names_only_the_tokens_the_payload_never_printed():
    record = _refused("The scan read a 0.42 score.")
    assert record.unsupported == ("0.42",)


def test_a_refusal_is_never_recorded_beside_the_model_summary():
    record = _refused("The scan read a 0.42 score.")
    assert record.summary_source == narration.TEMPLATE
    assert record.verification != narration.PASSED
    assert record.model_name is None


# --- the acceptance ----------------------------------------------------------


def test_a_summary_the_verifier_passes_is_the_one_the_record_carries():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED))
    assert record.summary == SUPPORTED


def test_a_passed_summary_names_the_model_as_its_source():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED))
    assert record.summary_source == narration.MODEL
    assert record.verification == narration.PASSED


def test_a_passed_summary_names_the_model_that_wrote_it():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED))
    assert record.model_name == "stub-model"


def test_a_passed_summary_refused_nothing():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED))
    assert record.unsupported == ()


def test_a_model_naming_nothing_names_nothing_beside_the_summary():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED, model_name=None))
    assert record.summary == SUPPORTED
    assert record.model_name is None


def test_a_summary_is_held_to_the_flag_data_the_model_was_given():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED_VALUE))
    assert record.verification == narration.PASSED
    assert record.summary == SUPPORTED_VALUE


# --- nothing was written to check --------------------------------------------


def test_a_summariser_that_answers_none_reads_as_the_template():
    record = narrate(FLAGS, "review", [TERM], _Stub(None))
    assert record.summary == template.template_summary(FLAGS, "review")
    assert record.summary_source == narration.TEMPLATE


def test_nothing_is_recorded_as_checked_when_no_model_wrote_anything():
    record = narrate(FLAGS, "review", [TERM], _Stub(None))
    assert record.verification == narration.NOT_CHECKED
    assert record.unsupported == ()
    assert record.model_name is None


def test_no_summariser_reads_the_way_a_summariser_answering_none_does():
    without = narrate(FLAGS, "review", [TERM], None)
    answered = narrate(FLAGS, "review", [TERM], _Stub(None))
    assert without == answered


@pytest.mark.parametrize(
    "stub",
    [None, _Stub(None), _Stub("The scan read a 0.42 score.")],
    ids=["no-summariser", "answered-none", "refused"],
)
def test_the_text_an_officer_reads_is_the_template_whoever_was_asked(stub):
    assert narrate(FLAGS, "review", [TERM], stub).summary == template.template_summary(
        FLAGS, "review"
    )


@pytest.mark.parametrize(
    "stub",
    [None, _Stub(None), _Stub(SUPPORTED), _Stub("The scan read a 0.42 score.")],
    ids=["no-summariser", "answered-none", "passed", "refused"],
)
def test_every_answer_names_a_verdict_out_of_the_three_declared(stub):
    record = narrate(FLAGS, "review", [TERM], stub)
    assert record.verification in narration.VERIFICATION_STATUSES
    assert record.summary_source in narration.SUMMARY_SOURCES


# --- what the model was asked ------------------------------------------------


def test_the_summariser_is_asked_exactly_once():
    stub = _Stub(SUPPORTED)
    narrate(FLAGS, "review", [TERM], stub)
    assert len(stub.prompts) == 1


def test_the_prompt_is_the_loaded_prompt_above_the_payload():
    stub = _Stub(SUPPORTED)
    narrate(FLAGS, "review", [TERM], stub)
    asked = load_prompt().text + "\n\n" + _held(FLAGS, "review", [TERM]).to_json()
    assert stub.prompts == [asked]


def test_the_flag_data_the_verifier_searched_is_the_text_the_model_read():
    stub = _Stub(SUPPORTED)
    narrate(FLAGS, "review", [TERM], stub)
    assert _held(FLAGS, "review", [TERM]).to_json() in stub.prompts[0]


def test_the_prompt_carries_no_pixel_data():
    stub = _Stub(SUPPORTED)
    narrate(FLAGS, "review", [TERM], stub)
    for x, y in FLAG["region"]:
        assert str(x) not in stub.prompts[0]
        assert str(y) not in stub.prompts[0]


def test_the_prompt_version_recorded_is_the_one_that_was_asked_with():
    given = Prompt(version="9.9.9", text="Say one sentence about the findings.")
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED), given)
    assert record.prompt_version == "9.9.9"


def test_the_shipped_prompt_version_is_recorded_on_every_path():
    assert narrate(FLAGS, "review", [TERM]).prompt_version == load_prompt().version
    assert _refused(SUPPORTED).prompt_version == load_prompt().version


# --- refusals and the record's own shape ----------------------------------


@pytest.mark.parametrize("flags,band", CASES)
def test_every_scan_reaches_an_officer_even_when_the_model_is_refused(flags, band):
    refused = "The scan read a 0.42 score."
    record = narrate(flags, band, [], _Stub(refused))
    assert record.summary == template.template_summary(flags, band)
    assert record.verification == narration.FAILED
    assert verify_summary(record.summary, _held(flags, band)) == (True, ())


@pytest.mark.parametrize("band", sorted(WEIGHT_BANDS))
def test_every_band_records_a_refusal_the_same_way(band):
    record = narrate(FLAGS, band, [TERM], _Stub("The scan read a 0.42 score."))
    assert (record.summary_source, record.verification) == (
        narration.TEMPLATE,
        narration.FAILED,
    )


@pytest.mark.parametrize("band", ["", "Low", "critical", 3, None, ["low"]])
def test_a_band_the_registry_does_not_know_is_refused(band):
    with pytest.raises(FlagValueError):
        narrate(FLAGS, band, [TERM], _Stub(SUPPORTED))


def test_a_finding_missing_a_field_the_payload_sends_is_refused_with_no_summariser():
    with pytest.raises(FlagValueError, match="tier"):
        narrate([_without("tier")], "review", [])


def test_a_finding_the_template_cannot_narrate_is_refused_before_the_model_is_asked():
    stub = _Stub(SUPPORTED)
    with pytest.raises(FlagValueError, match="reason"):
        narrate([_without("reason")], "review", [TERM], stub)
    assert stub.prompts == []


def test_the_record_is_frozen_so_what_an_officer_read_cannot_be_amended():
    record = narrate(FLAGS, "review", [TERM])
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.summary = "something else"


def test_the_record_reads_back_as_a_response_body():
    record = narrate(FLAGS, "review", [TERM], _Stub(SUPPORTED))
    body = json.loads(json.dumps(record.as_dict()))
    assert set(body) == {field.name for field in dataclasses.fields(record)}
    assert body["summary"] == SUPPORTED
    assert body["summary_source"] == narration.MODEL
    assert body["verification"] == narration.PASSED
    assert body["unsupported"] == []
