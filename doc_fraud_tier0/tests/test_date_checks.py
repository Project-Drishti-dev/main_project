from datetime import date

import pytest

from tier0.date_checks import (
    resolve_birth_date,
    resolve_expiry_date,
    check_birth_date_not_future,
    check_not_expired,
    check_dob_matches_visual_zone,
    DateParseError,
)

TODAY = date(2026, 9, 27)


def test_resolve_birth_date_recent_person():
    # YY=05 with today=2026 -> should resolve to 2005, not 1905 (which
    # would make the person implausibly old at the time this test was written).
    d = resolve_birth_date("050615", today=TODAY)
    assert d == date(2005, 6, 15)


def test_resolve_birth_date_older_person():
    # YY=45 -> only 1945 is plausible (2045 would be in the future).
    d = resolve_birth_date("450101", today=TODAY)
    assert d == date(1945, 1, 1)


def test_resolve_birth_date_no_plausible_century_raises():
    # A birth "date" that's in the future under every century guess close
    # to today, and implausibly old under the rest -- shouldn't happen with
    # real people, but must not silently produce a wrong answer.
    with pytest.raises(DateParseError):
        resolve_birth_date("999999", today=TODAY)  # invalid month/day anyway


def test_resolve_expiry_date():
    assert resolve_expiry_date("300101") == date(2030, 1, 1)


def test_check_birth_date_not_future_passes_for_real_date():
    outcome = check_birth_date_not_future("900101", today=TODAY)
    assert outcome.passed is True


def test_check_not_expired_fails_for_past_date():
    outcome = check_not_expired("200101", today=TODAY)  # 2020-01-01, in the past
    assert outcome.passed is False
    assert "expired" in outcome.detail.lower()


def test_check_not_expired_passes_for_future_date():
    outcome = check_not_expired("300101", today=TODAY)  # 2030-01-01
    assert outcome.passed is True


def test_dob_visual_zone_match():
    outcome = check_dob_matches_visual_zone("900101", "Date of Birth: 01 JAN 1990")
    assert outcome.passed is True


def test_dob_visual_zone_mismatch():
    outcome = check_dob_matches_visual_zone("900101", "Date of Birth: 02 FEB 1991")
    assert outcome.passed is False


def test_dob_visual_zone_skipped_when_no_text_supplied():
    outcome = check_dob_matches_visual_zone("900101", None)
    assert outcome.passed is True
    assert "skipped" in outcome.detail.lower()


def test_dob_visual_zone_skipped_when_no_date_found():
    outcome = check_dob_matches_visual_zone("900101", "Name: JOHN SMITH, Nationality: USA")
    assert outcome.passed is True
    assert "skipped" in outcome.detail.lower()
