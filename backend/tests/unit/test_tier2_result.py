"""15.2 -- a deep result says how strongly, where, and who produced it.

The claim pinned first is the verification the task names: a stand-in result
carries ``is_stub`` true and a non-empty ``model_version``.  The rest pins the
record's honesty rules -- a stub's zero is not a clean document, an empty
heatmap is no map rather than a map of zeros, and a field that would read
stronger than it was measured is refused rather than clipped.
"""

import dataclasses
import uuid

import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base

DeepModule = base.DeepModule
DeepResult = base.DeepResult

SCREENING_ID = uuid.UUID("7c2b1d40-5e6f-4a8b-9c0d-1e2f3a4b5c6d")
BOX = ((10, 20), (60, 20), (60, 70), (10, 70))


def _stub(score=0.0):
    """A stand-in's answer: it found nothing, and it says that it is a stand-in."""
    return DeepResult(
        module="morph",
        score=score,
        is_stub=True,
        model_version="heuristic-v0",
        detail="The morph heuristic ran. It is not a detector.",
    )


def _context():
    """A context carrying what the seam hands a module and nothing else."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=object(),
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


class _Answers(DeepModule):
    """A stand-in module that answers the record it was built with."""

    def __init__(self, answer):
        self.name = type(self).__name__
        self.answer = answer

    def run(self, context):
        return self.answer


def test_a_stub_result_carries_its_label_and_a_version():
    """The task's own verification: ``is_stub`` is true and a version is named."""
    result = _stub()

    assert result.is_stub is True
    assert result.model_version == "heuristic-v0"
    assert result.model_version


def test_a_stub_that_found_nothing_still_says_it_is_a_stub():
    """A stand-in's zero is not a clean document, and the record says so."""
    result = _stub(score=0.0)

    assert result.score == 0.0
    assert result.is_stub is True


def test_the_label_fields_have_nothing_to_default_to():
    """A module cannot answer without saying whether a model did the work."""
    with pytest.raises(TypeError):
        DeepResult(module="ela", score=0.5, is_stub=True, detail="no version given")


def test_a_blank_model_version_is_refused():
    """An empty version is an unnamed answer, which is the thing being stopped."""
    for version in ("", "   "):
        with pytest.raises(base.DeepResultError):
            dataclasses.replace(_stub(), model_version=version)


def test_is_stub_must_be_a_bool_and_not_a_number():
    """A 1 in that slot would be a stand-in on one page and a model on another."""
    with pytest.raises(base.DeepResultError):
        dataclasses.replace(_stub(), is_stub=1)


def test_a_score_outside_the_unit_interval_is_refused():
    """Nothing is clipped, because a clipped 1.4 reads stronger than it was."""
    with pytest.raises(base.DeepResultError):
        _stub(score=1.4)

    with pytest.raises(base.DeepResultError):
        _stub(score=-0.1)


def test_a_score_that_is_a_bool_is_refused():
    """True is a real number in Python and is not a confidence of one."""
    with pytest.raises(base.DeepResultError):
        _stub(score=True)


def test_an_empty_heatmap_and_no_regions_is_no_measurement():
    """Empty means the module produced neither, not that it measured zero."""
    result = _stub()

    assert result.heatmap == ()
    assert result.regions == ()


def test_a_result_may_carry_a_heatmap_and_a_region():
    """Both are handed straight through, in the frame the module was given."""
    result = dataclasses.replace(
        _stub(score=0.8), heatmap=((0.0, 0.5), (0.9, 1.0)), regions=(BOX,)
    )

    assert result.heatmap[1][0] == 0.9
    assert result.regions == (BOX,)


def test_a_ragged_heatmap_is_refused():
    """No overlay draws on rows of two different widths."""
    with pytest.raises(base.DeepResultError):
        dataclasses.replace(_stub(), heatmap=((0.0, 0.5), (0.9,)))


def test_a_heatmap_cell_outside_the_unit_interval_is_refused():
    """The map is normalised, so a cell above one is a normalisation that did
    not happen and would draw over the page as certainty."""
    with pytest.raises(base.DeepResultError):
        dataclasses.replace(_stub(), heatmap=((0.0, 1.2),))


def test_a_region_must_be_a_polygon_of_whole_pixels():
    """Two corners enclose no area, and a float corner is not a pixel."""
    with pytest.raises(base.DeepResultError):
        dataclasses.replace(_stub(), regions=(((10, 20), (60, 20)),))

    with pytest.raises(base.DeepResultError):
        dataclasses.replace(_stub(), regions=(((10.5, 20.0), (60, 20), (60, 70)),))


def test_a_region_must_be_a_tuple_and_not_a_list():
    """The record is frozen, so a list inside it would still be mutable."""
    with pytest.raises(base.DeepResultError):
        dataclasses.replace(_stub(), regions=[list(BOX)])


def test_the_record_is_frozen():
    """A result a later stage rewrote would be a finding nobody measured."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        _stub().score = 0.9


def test_a_module_answers_a_record_that_names_it():
    """The seam's answer is the record, and the record says who wrote it."""
    module = _Answers(_stub())

    run = base.run_deep_modules(_context(), modules={"morph": module})

    assert isinstance(run.results[0], DeepResult)
    assert run.results[0].module == "morph"
