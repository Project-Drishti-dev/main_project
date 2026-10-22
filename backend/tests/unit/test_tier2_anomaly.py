"""15.12 -- one feature vector per document, and a forest fitted on a committed fixture.

The claim pinned first is the verification the task names: a synthetic document
from outside the clean family reads *higher* than the clean pages it is compared
against, on both the rank and the forest's own raw score.  The rest holds that
the scorer says it is a stand-in, that the fixture it fits on is the one in the
package and cannot be silently reordered, and that the line it reads is the
fixture's own 95th percentile rather than scikit-learn's ``"auto"``, which was
measured and called 41 of 120 clean rows -- D124.

**The limits are pinned as carefully as the claim.**  Nothing here has met a
real document; the fixture is artwork this repository drew.  ``"auto"`` is kept
as an accepted value and rejected as a default, with its numbers.  Added grain
is the measured weakness: re-encoding a clean page down to quality 10 leaves it
in the clean band, while re-graining it past sigma 6 pushes it above the line,
and both are measured here rather than asserted in prose only.  Every figure
came from the shipped functions, and the fixture is drawn by the same
``_clean_page`` the committed rows were measured from.
"""

import dataclasses
import json

import cv2
import numpy as np
import pytest

from app.pipeline.tier2 import anomaly

#: The clean pages the fixture was drawn from, and the seeds the test draws
#: fresh ones at.  Different seeds, same generator: the fixture's rows and the
#: pages compared against them are drawn from one family on purpose.
FIXTURE_SIZE = 120
FRESH_SEEDS = tuple(range(1000, 1012))


def _head(side=180, dx=0):
    """Return one synthetic portrait at ``side`` pixels square, in colour."""
    image = np.full((side, side, 3), 205, np.uint8)
    image[:, :] = (205, 190, 165)
    cv2.ellipse(image, (side // 2 + dx, side // 2), (52, 66), 0, 0, 360, (150, 165, 175), -1)
    cv2.circle(image, (side // 2 + dx - 20, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.circle(image, (side // 2 + dx + 20, side // 2 - 20), 9, (45, 45, 45), -1)
    cv2.ellipse(image, (side // 2 + dx, side // 2 + 40), (26, 10), 0, 0, 180, (60, 65, 70), 2)
    return image


def _clean_page(seed=0, size=(900, 700), density=18, quality=85, noise=1.4, photo=True, tint=(236, 236, 236)):
    """Return one clean synthetic form: body text, printed rules, a portrait box.

    This is the generator the committed fixture's rows were measured from, so
    the pages this test draws are the same family the forest was fitted on.
    """
    rng = np.random.default_rng(seed)
    width, height = size
    page = np.full((height, width, 3), 0, np.uint8)
    page[:, :] = (tint[2], tint[1], tint[0])
    for row in range(40, int(height * 0.78), density):
        for column in range(40, int(width * 0.62), 18):
            if rng.random() < 0.12:
                continue
            cv2.line(page, (column, row), (column + 12, row), (70, 70, 70), 2, cv2.LINE_AA)
    for row in range(int(height * 0.82), int(height * 0.88), 24):
        cv2.line(page, (50, row), (int(width * 0.6), row), (90, 90, 90), 1, cv2.LINE_AA)
    cv2.rectangle(page, (int(width * 0.68), 60), (int(width * 0.94), int(height * 0.45)), (60, 60, 60), 2)
    if photo:
        photo_image = _head(180, int(rng.integers(-8, 9)))
        x, y = int(width * 0.70), 70
        page[y : y + 180, x : x + 180] = photo_image
    lit = rng.poisson(np.clip(page.astype(np.float64), 0, None))
    noisy = np.clip(lit + rng.normal(0, noise, page.shape), 0, 255).astype(np.uint8)
    encoded = cv2.imencode(".jpg", noisy, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert encoded[0], "the test's own JPEG encoder refused its page"
    return cv2.imdecode(encoded[1], cv2.IMREAD_COLOR)


def _jpeg(page, quality):
    """Return ``page`` through a JPEG round trip at ``quality``."""
    encoded = cv2.imencode(".jpg", page, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert encoded[0], "the test's own JPEG encoder refused its page"
    return cv2.imdecode(encoded[1], cv2.IMREAD_COLOR)


def _regrain(page, sigma, seed=1):
    """Return ``page`` with ``sigma`` of uniform grain added back."""
    added = np.random.default_rng(seed).normal(0, sigma, page.shape)
    return np.clip(page.astype(np.float64) + added, 0, 255).astype(np.uint8)


def _noise_field(seed=7):
    """Return a frame of shot noise, which is not a document at all."""
    return np.clip(np.random.default_rng(seed).normal(128, 60, (700, 900, 3)), 0, 255).astype(np.uint8)


def _halftone():
    """Return a 1px checkerboard, the hardest edge pattern there is."""
    grid = (np.indices((700, 900)).sum(axis=0) % 2 * 255).astype(np.uint8)
    return np.repeat(grid[:, :, None], 3, axis=2)


def _collage(seed=7):
    """Return a tiled sheet of noise blocks, a page-like arrangement of none."""
    rng = np.random.default_rng(seed)
    out = np.zeros((720, 960, 3), np.uint8)
    for index in range(24):
        tile = np.clip(rng.normal(90, 40, (120, 160, 3)), 0, 255).astype(np.uint8)
        row, column = divmod(index, 6)
        out[row * 120 : row * 120 + 120, column * 160 : column * 160 + 160] = tile
    return out


def _inverted(seed=7):
    """Return a clean page with its tones reversed, which no camera produces."""
    return 255 - _clean_page(seed=seed, photo=False)


#: Four documents outside the clean family, and the score field above them.
OUT_OF_DISTRIBUTION = {
    "noise field": _noise_field,
    "halftone": _halftone,
    "collage": _collage,
    "inverted page": _inverted,
}

SCORER = anomaly.AnomalyScorer()
CLEAN = [
    _clean_page(seed=seed, size=((900, 700), (1000, 1200))[seed % 2], density=18, quality=85, noise=1.4)
    for seed in FRESH_SEEDS
]
CLEAN_VERDICTS = [SCORER.verdict(page) for page in CLEAN]
CLEAN_SCORES = [verdict.score for verdict in CLEAN_VERDICTS]
CLEAN_RAW = [verdict.raw for verdict in CLEAN_VERDICTS]


# --- the task's own verification -----------------------------------------


def test_an_out_of_distribution_document_scores_above_the_in_distribution_ones():
    """The task's own verification: every odd document outranks every clean page.

    Asserted on the rank *and* on the forest's raw score, because the rank
    saturates at 1.0 and would hide how far past the fixture a document sits.
    """
    for name, draw in OUT_OF_DISTRIBUTION.items():
        verdict = SCORER.verdict(draw())
        assert all(verdict.score > score for score in CLEAN_SCORES), name
        assert all(verdict.raw > raw for raw in CLEAN_RAW), name


def test_the_odd_documents_are_the_ones_the_forest_calls_outliers():
    """The same ordering read through the forest's own line, not the rank."""
    flags = {name: SCORER.verdict(draw()).outlier for name, draw in OUT_OF_DISTRIBUTION.items()}

    assert all(flags.values()), flags
    assert sum(1 for verdict in CLEAN_VERDICTS if verdict.outlier) < len(flags)


def test_a_document_past_the_whole_fixture_ranks_one():
    """A rank is a share of the fixture, so it tops out at 1.0 and no further."""
    assert SCORER.verdict(_noise_field()).score == 1.0
    assert SCORER.verdict(_noise_field(seed=11)).score == 1.0


# --- the scorer says what produced it ------------------------------------


def test_the_scorer_says_a_stand_in_produced_it():
    """A forest really was fitted, but on artwork this repository drew."""
    assert SCORER.is_stub is True
    assert SCORER.model_version == "isolation-forest-v0"
    assert anomaly.MODEL_VERSION == "isolation-forest-v0"


def test_the_line_is_the_fixtures_own_ninety_fifth_percentile():
    """``"auto"`` was measured and rejected: it sits in the middle of the band."""
    assert anomaly.CONTAMINATION == 0.05

    raw = np.asarray([SCORER.raw_score(anomaly.FeatureVector(*row)) for row in SCORER.rows])

    assert -SCORER.forest.offset_ == pytest.approx(float(np.percentile(raw, 95)), abs=1e-9)


def test_two_scorers_built_from_one_fixture_answer_the_same_number():
    """The fit is seeded, so a repeated fit is a repeated answer."""
    again = anomaly.AnomalyScorer()
    features = anomaly.feature_vector(_clean_page(seed=1000))

    assert again.rows == SCORER.rows
    assert again.raw_score(features) == SCORER.raw_score(features)
    assert again.rank(features) == SCORER.rank(features)


# --- the fixture is the one in the package -------------------------------


def test_the_forest_is_fitted_on_the_committed_fixture():
    """The rows it holds are the file the module ships, all of them."""
    rows = anomaly.load_fixture()

    assert len(rows) == FIXTURE_SIZE
    assert SCORER.rows == rows
    assert all(len(row) == len(anomaly.FEATURE_NAMES) for row in rows)


def test_the_fixtures_header_names_this_vectors_features():
    """A reordered fixture would be a silent wrong answer, so it is refused."""
    payload = json.loads(anomaly.FIXTURE_PATH.read_text(encoding="utf-8"))

    assert tuple(payload["features"]) == anomaly.FEATURE_NAMES
    assert payload["count"] == FIXTURE_SIZE


def test_every_family_the_task_names_is_in_the_vector():
    """ELA, noise, histogram, edge density and field geometry, all five."""
    names = anomaly.FEATURE_NAMES

    assert any(name.startswith("ela_") for name in names)
    assert any(name.startswith("noise_") for name in names)
    assert any(name.startswith("hist_") for name in names)
    assert any(name.startswith("edge_") for name in names)
    assert any(name.startswith(("rule_", "row_")) for name in names)
    assert len(set(names)) == len(names) == 15


# --- the vector reads a page the way it is drawn -------------------------


def test_a_drawn_page_reads_more_ink_than_a_blank_one():
    """The histogram and edge families separate a form from the paper behind it."""
    drawn = anomaly.feature_vector(_clean_page(seed=3))
    blank = anomaly.feature_vector(_regrain(np.full((700, 900, 3), 236, np.uint8), 1.5, seed=9))

    assert drawn.ink_share > blank.ink_share
    assert drawn.hist_mean < blank.hist_mean
    assert drawn.edge_density > blank.edge_density
    assert drawn.row_fill > blank.row_fill


def test_the_printed_fields_are_read_as_geometry():
    """A form's rules and box are straight runs of ink, and the family says so."""
    drawn = anomaly.feature_vector(_clean_page(seed=3))
    blank = anomaly.feature_vector(_regrain(np.full((700, 900, 3), 236, np.uint8), 1.5, seed=9))

    assert drawn.rule_rows > 0.0
    assert drawn.rule_cols > 0.0
    assert blank.rule_rows == 0.0
    assert blank.rule_cols == 0.0


def test_every_feature_is_a_finite_number_and_the_vector_will_not_move():
    """A forest cannot be shown a NaN, and cannot be shown a changed vector."""
    features = anomaly.feature_vector(_clean_page(seed=3))
    array = features.as_array()

    assert array.shape == (len(anomaly.FEATURE_NAMES),)
    assert np.isfinite(array).all()
    with pytest.raises(dataclasses.FrozenInstanceError):
        features.ela_mean = 0.0  # frozen: a fitted forest keeps what it was given


def test_one_grid_is_read_for_every_capture_size():
    """D120's rule on this measurement: a page drawn at two sizes, one grid."""
    wide = anomaly.canonical(_clean_page(seed=4, size=(900, 700)))
    tall = anomaly.canonical(_clean_page(seed=4, size=(700, 900)))

    assert max(wide.shape) == anomaly.CANONICAL
    assert max(tall.shape) == anomaly.CANONICAL
    assert min(wide.shape) % 8 == 0 and min(tall.shape) % 8 == 0


# --- the measured limits, pinned -----------------------------------------


def test_re_encoding_a_clean_page_down_to_quality_ten_leaves_it_in_the_clean_band():
    """An attacker re-encodes rather than redraws, and the vector barely moves."""
    page = _clean_page(seed=3)
    re_encoded = SCORER.verdict(_jpeg(page, 10))
    oddest = min(SCORER.verdict(draw()).raw for draw in OUT_OF_DISTRIBUTION.values())

    assert re_encoded.raw < oddest
    assert re_encoded.score < 1.0, "a re-encoded clean page did not stay inside the fixture"


def test_added_grain_is_the_measured_weakness():
    """Re-grained past sigma 6, a clean page crosses the line.  Recorded, not tuned.

    D123's lesson applied to this module: a cue tested only on the two classes
    it separates ships looking better than it is.  The line was not raised to
    hide this, because raising it is what would have cost the detections.
    """
    page = _clean_page(seed=3)

    assert not SCORER.verdict(_regrain(page, 2.0, seed=1)).outlier
    assert SCORER.verdict(_regrain(page, 12.0, seed=3)).outlier


def test_a_document_with_no_noise_is_refused_rather_than_scored():
    """A flat frame would read as the most average document there is."""
    with pytest.raises(anomaly.AnomalyError):
        anomaly.feature_vector(np.full((700, 900, 3), 128, np.uint8))


def test_a_document_smaller_than_the_grid_is_refused_rather_than_upsampled():
    """Interpolating up would measure pixels the capture never held."""
    with pytest.raises(anomaly.AnomalyError):
        anomaly.feature_vector(cv2.resize(_clean_page(seed=5), (64, 48), interpolation=cv2.INTER_AREA))


@pytest.mark.parametrize(
    "frame",
    [
        pytest.param(_clean_page(seed=6).astype(np.float64), id="float dtype"),
        pytest.param(_clean_page(seed=6)[:, :, :2].copy(), id="two channels"),
        pytest.param(np.zeros((0, 10, 3), np.uint8), id="empty"),
        pytest.param("a page", id="not an array"),
    ],
)
def test_a_frame_that_is_not_a_capture_is_refused(frame):
    """Whatever the reason, it is an :class:`AnomalyError` and a ``ValueError``."""
    with pytest.raises(anomaly.AnomalyError) as caught:
        anomaly.feature_vector(frame)

    assert isinstance(caught.value, ValueError)


# --- a malformed fixture or scorer is refused ----------------------------


def _write(tmp_path, payload):
    """Write ``payload`` as a fixture file and return its path."""
    path = tmp_path / "features.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


GOOD_ROW = [1.0] * len(anomaly.FEATURE_NAMES)
HEADER = list(anomaly.FEATURE_NAMES)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"features": list(reversed(HEADER)), "rows": [GOOD_ROW, GOOD_ROW]}, id="reordered"),
        pytest.param({"features": HEADER, "rows": [[1.0] * 14, GOOD_ROW]}, id="short row"),
        pytest.param({"features": HEADER, "rows": []}, id="no rows"),
        pytest.param({"features": HEADER, "rows": [[float("nan")] + [1.0] * 14, GOOD_ROW]}, id="not finite"),
        pytest.param({"features": HEADER, "rows": [["ela"] + [1.0] * 14, GOOD_ROW]}, id="not a number"),
        pytest.param([GOOD_ROW, GOOD_ROW], id="not an object"),
    ],
)
def test_a_fixture_that_is_not_this_vectors_fixture_is_refused(tmp_path, payload):
    """Each of these would be fitted on silently, so each is refused."""
    with pytest.raises(anomaly.AnomalyError):
        anomaly.load_fixture(_write(tmp_path, payload))


def test_a_fixture_that_is_not_there_is_refused(tmp_path):
    """A missing file is a refusal, not an empty forest fitted on nothing."""
    with pytest.raises(anomaly.AnomalyError):
        anomaly.load_fixture(tmp_path / "absent.json")


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"rows": [GOOD_ROW]}, id="one row"),
        pytest.param({"n_estimators": 0}, id="no trees"),
        pytest.param({"n_estimators": True}, id="trees is not a count"),
        pytest.param({"random_state": -1}, id="negative seed"),
        pytest.param({"contamination": "lots"}, id="contamination is not a share"),
    ],
)
def test_a_scorer_cannot_be_wired_wrongly(kwargs):
    """Wired wrongly fails at construction, not on the first document."""
    with pytest.raises(anomaly.AnomalyError):
        anomaly.AnomalyScorer(**kwargs)


def test_a_scorer_is_refused_anything_that_is_not_a_vector():
    """A row of numbers is not a vector, and a vector is not a row."""
    scorer = anomaly.AnomalyScorer()

    for call in (scorer.raw_score, scorer.rank, scorer.outlier):
        with pytest.raises(anomaly.AnomalyError):
            call([1.0] * len(anomaly.FEATURE_NAMES))


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"score": 1.5, "raw": 0.5, "outlier": False}, id="score above one"),
        pytest.param({"score": -0.1, "raw": 0.5, "outlier": False}, id="score below zero"),
        pytest.param({"score": 0.5, "raw": float("nan"), "outlier": False}, id="raw not finite"),
        pytest.param({"score": 0.5, "raw": 0.5, "outlier": "yes"}, id="flag is not a bool"),
    ],
)
def test_a_verdict_that_disagrees_with_itself_is_refused(kwargs):
    """The record validates what it carries, so a caller cannot read half of one."""
    fields = {"features": anomaly.feature_vector(_clean_page(seed=7)), **kwargs}

    with pytest.raises(anomaly.AnomalyError):
        anomaly.AnomalyVerdict(**fields)


def test_a_feature_vector_holding_a_bad_number_is_refused():
    """The vector is checked when it is built, not when a forest is shown it."""
    values = {name: 1.0 for name in anomaly.FEATURE_NAMES}

    assert anomaly.FeatureVector(**values).ink_share == 1.0
    with pytest.raises(anomaly.AnomalyError):
        anomaly.FeatureVector(**{**values, "hist_entropy": float("inf")})
    with pytest.raises(anomaly.AnomalyError):
        anomaly.FeatureVector(**{**values, "edge_density": "0.2"})
