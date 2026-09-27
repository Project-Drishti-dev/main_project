"""
Exercises the real image -> OCR -> parse pipeline (Stage A) against
synthetic document photos, including a noisy/skewed variant to check the
preprocessing (deskew, denoise, binarize) actually helps.
"""
from tier0.mrz_extract import extract_mrz_text


def test_extract_from_clean_synthetic_passport(icao_example_passport_image):
    result = extract_mrz_text(icao_example_passport_image)
    assert result.success is True
    assert result.mrz_fields is not None
    assert result.mrz_fields.document_number == "L898902C3"
    assert result.mrz_fields.surname == "ERIKSSON"


def test_extract_from_noisy_skewed_passport(icao_example_passport_image_noisy_skewed):
    result = extract_mrz_text(icao_example_passport_image_noisy_skewed)
    # OCR on noisy/skewed input is inherently less certain than the clean
    # case, but the preprocessing pipeline (deskew + denoise + binarize)
    # should still get a parseable MRZ out of a phone-photo-level distortion.
    assert result.success is True
    assert result.mrz_fields is not None
    assert result.mrz_fields.document_number == "L898902C3"


def test_extract_missing_file_reports_error():
    result = extract_mrz_text("/nonexistent/path/to/image.png")
    assert result.success is False
    assert result.error is not None
