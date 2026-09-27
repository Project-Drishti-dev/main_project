import json

from tier0.models import FailureReason
from tier0.pipeline import run_tier0, TIME_BUDGET_SECONDS


def test_pipeline_passes_on_valid_unexpired_document(valid_unexpired_passport_image):
    result = run_tier0(valid_unexpired_passport_image)
    assert result.passed is True, result
    assert result.failed_at is None
    assert result.mrz_fields.document_number == "X12345678"


def test_pipeline_fails_on_checksum_for_expired_icao_example(icao_example_passport_image):
    # The canonical ICAO example document expired in 2012, so Stage C
    # (date sanity) should catch it -- checksums all pass first, though.
    result = run_tier0(icao_example_passport_image)
    assert result.passed is False
    assert result.failed_at == FailureReason.DATE_SANITY
    assert "expired" in result.reason.lower()


def test_pipeline_fails_on_watchlist_hit(valid_unexpired_passport_image, tmp_path):
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(
        json.dumps({"entries": [{"document_number": "X12345678", "reason": "Reported stolen"}]})
    )
    result = run_tier0(valid_unexpired_passport_image, watchlist_path=str(watchlist_path))
    assert result.passed is False
    assert result.failed_at == FailureReason.WATCHLIST_HIT
    assert "stolen" in result.reason.lower()


def test_pipeline_missing_image_fails_fast():
    result = run_tier0("/nonexistent/image.png")
    assert result.passed is False
    assert result.failed_at == FailureReason.MRZ_NOT_FOUND


def test_pipeline_str_representation_on_pass(valid_unexpired_passport_image):
    result = run_tier0(valid_unexpired_passport_image)
    assert "PASS" in str(result)


def test_pipeline_str_representation_on_fail(icao_example_passport_image):
    result = run_tier0(icao_example_passport_image)
    s = str(result)
    assert "FAIL" in s
    assert "Failed at:" in s
    assert "Reason:" in s


def test_pipeline_runs_fast_enough(valid_unexpired_passport_image):
    """
    Not a hard perf assertion (CI machines vary, and this environment's OCR
    call is the dominant cost) -- but this documents Tier 0's budget and
    flags wildly regressive changes.
    """
    result = run_tier0(valid_unexpired_passport_image)
    # Generous multiple of the spec's 0.3s budget so this doesn't flake in
    # a slow/shared CI environment, while still catching real blowups.
    assert result.elapsed_seconds < TIME_BUDGET_SECONDS * 10
