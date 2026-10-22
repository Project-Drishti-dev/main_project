"""13.15 -- two faces, one cosine, and the three cases the task names.

Every vector here is a plain tuple of floats, because the claim is a claim
about geometry and no face model is installed on this box to measure against
(``D84``).  The three cases are exact: a vector against itself is 1.0 whatever
its length, a right angle is 0.0, and the abstract's own worked example B
supplies the below-threshold pair at 0.41 against 0.55.

**The vectors are deliberately not unit length.**  The identical pair is a
5-12-13 triangle, whose dot product with itself is 169.0 -- so a module that
reached for the dot product instead of the cosine fails on the first case
rather than passing it by luck.  The scaled copy beside it is the same claim
from the other side: a cosine cannot tell the two apart, and a dot product
tells them apart by a factor of a hundred.
"""

import dataclasses
import inspect
import math

import pytest

from app.pipeline.tier1 import face
from app.pipeline.tier1.face import (
    Embedding,
    MatchScore,
    NO_MATCH,
    NullEmbedder,
    match_score,
)

#: A vector and itself, as a 5-12-13 triangle: length 13, dot with itself 169.
IDENTICAL = Embedding(vector=(5.0, 12.0))

#: The same direction at ten times the length, for the scale-free claim.
SCALED = Embedding(vector=(50.0, 120.0))

#: Two unit vectors at a right angle.  Orthogonality is the one cosine that is
#: exactly zero rather than nearly so, so it is compared exactly below.
ALONG_X = Embedding(vector=(1.0, 0.0))
ALONG_Y = Embedding(vector=(0.0, 1.0))

#: The abstract's worked example B numbers, which 13.16 must reproduce.
BELOW = 0.41
THRESHOLD = 0.55


def unit_at(cosine):
    """A unit vector whose cosine against ``ALONG_X`` is exactly ``cosine``.

    Built rather than typed in, so the number a test asserts is the number the
    geometry produces and not a pair of floats that happens to print as it.
    """
    return Embedding(vector=(cosine, math.sqrt(1.0 - cosine * cosine)))


#: The face the abstract says was compared: 0.41 against a bar of 0.55.
BELOW_FACE = unit_at(BELOW)


def _stub():
    """The one embedding this project can always produce, and never measure."""
    return NullEmbedder().embed(object())


# --- the three cases the task names ---


def test_a_vector_compared_with_itself_is_a_perfect_match():
    """1.0 exactly, not merely near it: a dot product reads 169.0 here."""
    score = match_score(IDENTICAL, IDENTICAL, THRESHOLD)
    assert score.similarity == 1.0
    assert score.matches is True


def test_two_vectors_at_a_right_angle_score_zero():
    assert match_score(ALONG_X, ALONG_Y, THRESHOLD).similarity == 0.0


def test_a_pair_below_the_threshold_does_not_match():
    """The abstract's worked example B: a cosine of 0.41 against a bar of 0.55."""
    score = match_score(ALONG_X, BELOW_FACE, THRESHOLD)
    assert score.similarity == pytest.approx(BELOW)
    assert score.matches is False


def test_two_vectors_in_opposite_directions_score_minus_one():
    assert match_score(ALONG_X, Embedding(vector=(-1.0, 0.0)), THRESHOLD).similarity == -1.0


def test_a_right_angle_can_never_match():
    """The smallest threshold this module accepts is above zero, so 0.0 never clears one."""
    assert match_score(ALONG_X, ALONG_Y, 0.0001).matches is False


# --- the cosine, and not the dot product ---


def test_a_scaled_vector_is_the_same_direction_as_its_original():
    """A dot product would put these a hundredfold apart; the cosine cannot tell them."""
    assert match_score(IDENTICAL, SCALED, THRESHOLD).similarity == 1.0


def test_a_pair_above_the_threshold_matches():
    assert match_score(ALONG_X, unit_at(0.9), THRESHOLD).matches is True


def test_a_similarity_exactly_on_the_threshold_matches():
    """The edge is pinned here rather than left to whichever way ``>`` fell."""
    score = match_score(ALONG_X, unit_at(THRESHOLD), THRESHOLD)
    assert score.similarity == pytest.approx(THRESHOLD)
    assert score.matches is True


def test_the_score_is_the_same_either_way_round():
    left = match_score(IDENTICAL, ALONG_Y, THRESHOLD)
    right = match_score(ALONG_Y, IDENTICAL, THRESHOLD)
    assert left.similarity == right.similarity


# --- the threshold is part of the answer, not a default behind it ---


def test_the_threshold_rides_on_the_record():
    """13.16's flag carries both numbers, so the score has to hold both."""
    assert match_score(ALONG_X, BELOW_FACE, THRESHOLD).threshold == THRESHOLD


@pytest.mark.parametrize("threshold", [0.0, -0.5, -1.0])
def test_a_threshold_at_or_below_zero_is_refused(threshold):
    with pytest.raises(ValueError):
        match_score(IDENTICAL, IDENTICAL, threshold)


@pytest.mark.parametrize("threshold", [1.5, 2.0, math.inf, math.nan])
def test_a_threshold_no_cosine_can_reach_is_refused(threshold):
    """A bar above one can never be cleared, so it is a mistake and not a strictness."""
    with pytest.raises(ValueError):
        match_score(IDENTICAL, IDENTICAL, threshold)


@pytest.mark.parametrize("threshold", ["0.55", None, True, (0.55,)])
def test_a_threshold_that_is_not_a_real_number_is_refused(threshold):
    with pytest.raises(ValueError):
        match_score(IDENTICAL, IDENTICAL, threshold)


def test_the_threshold_is_required():
    """An omitted threshold would be a bar this module chose for the caller."""
    defaults = [
        parameter.default
        for parameter in inspect.signature(match_score).parameters.values()
        if parameter.default is not inspect.Parameter.empty
    ]
    assert defaults == []


def test_match_score_is_asked_for_two_embeddings_and_a_threshold():
    assert tuple(inspect.signature(match_score).parameters) == (
        "embedding_a",
        "embedding_b",
        "threshold",
    )


def test_match_score_takes_no_keyword_or_star_argument():
    kinds = {
        parameter.kind
        for parameter in inspect.signature(match_score).parameters.values()
    }
    assert kinds == {inspect.Parameter.POSITIONAL_OR_KEYWORD}


# --- a stub is refused rather than scored: D101's load-bearing claim ---


def test_a_stub_is_not_scored():
    """The cosine against a zero vector is 0 / 0, and 0 / 0 is not a score."""
    assert match_score(_stub(), IDENTICAL, THRESHOLD) is NO_MATCH


def test_a_stub_on_either_side_is_not_scored():
    assert match_score(IDENTICAL, _stub(), THRESHOLD) is NO_MATCH
    assert match_score(_stub(), _stub(), THRESHOLD) is NO_MATCH


def test_a_stub_is_refused_even_when_its_vector_looks_real():
    """The label, not the zeros, is what refuses it -- D101's own reasoning.

    ``NullEmbedder``'s vector is all zeros, which the norm check alone would
    catch, so a stub carrying a plausible vector is the case that only the
    label answers.  It would score against a real face at 1.0, and it would
    score the same for every traveller.
    """
    plausible_stub = Embedding(vector=(5.0, 12.0), is_stub=True)
    assert match_score(plausible_stub, IDENTICAL, THRESHOLD) is NO_MATCH


def test_a_refusal_is_not_a_similarity_of_zero():
    """``D99``'s rule: where nothing was measured the answer is not a clean zero."""
    assert match_score(_stub(), IDENTICAL, THRESHOLD) is not 0.0


def test_a_stub_is_refused_even_against_a_failing_threshold():
    """The argument is checked first, so a bad bar is refused either way round."""
    with pytest.raises(ValueError):
        match_score(_stub(), IDENTICAL, 0.0)


def test_a_vector_with_no_length_is_not_scored():
    """A zero vector that forgot its label still has no direction to compare."""
    assert match_score(Embedding(vector=(0.0, 0.0)), IDENTICAL, THRESHOLD) is NO_MATCH


def test_a_vector_with_no_components_is_not_scored():
    assert match_score(Embedding(vector=()), Embedding(vector=()), THRESHOLD) is NO_MATCH


# --- a wiring mistake raises rather than answering ---


def test_two_vectors_of_different_widths_are_refused():
    """Two different face models produce two different widths, and comparing them is a mistake."""
    with pytest.raises(ValueError):
        match_score(IDENTICAL, Embedding(vector=(1.0, 2.0, 3.0)), THRESHOLD)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_vector_holding_a_number_that_is_not_finite_is_refused(value):
    with pytest.raises(ValueError):
        match_score(Embedding(vector=(value, 1.0)), IDENTICAL, THRESHOLD)


@pytest.mark.parametrize("value", ["0.5", None, True, [0.5]])
def test_a_vector_holding_something_that_is_not_a_number_is_refused(value):
    with pytest.raises(ValueError):
        match_score(Embedding(vector=(value, 1.0)), IDENTICAL, THRESHOLD)


# --- the record ---


def test_a_match_score_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        MatchScore(similarity=1.0, threshold=THRESHOLD).similarity = 0.41


@pytest.mark.parametrize("field", ["similarity", "threshold"])
def test_no_field_of_a_match_score_has_a_default(field):
    assert MatchScore.__dataclass_fields__[field].default is dataclasses.MISSING


def test_matches_is_derived_rather_than_stored():
    """A stored boolean could disagree with the two numbers printed beside it."""
    assert "matches" not in {field.name for field in dataclasses.fields(MatchScore)}
    assert isinstance(MatchScore.matches, property)


def test_every_name_in_all_exists_in_the_module():
    for name in face.__all__:
        assert hasattr(face, name)
