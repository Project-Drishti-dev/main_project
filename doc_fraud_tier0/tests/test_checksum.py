"""
Tests for tier0.checksum against the canonical ICAO Doc 9303 worked example
(Part 4, "Machine Readable Passports"), plus tamper-detection cases.
"""
import pytest

from tier0.checksum import compute_check_digit, char_value, verify_td3
from tier0.mrz_parse import parse

# The official ICAO 9303 worked example.
ICAO_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
ICAO_LINE2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def test_char_value_digits():
    assert char_value("0") == 0
    assert char_value("9") == 9


def test_char_value_letters():
    assert char_value("A") == 10
    assert char_value("Z") == 35


def test_char_value_filler():
    assert char_value("<") == 0


def test_char_value_rejects_garbage():
    with pytest.raises(ValueError):
        char_value("!")


@pytest.mark.parametrize(
    "data,expected",
    [
        ("L898902C3", "6"),        # document number
        ("740812", "2"),           # birth date
        ("120415", "9"),           # expiry date
        ("ZE184226B<<<<<", "1"),   # optional data
    ],
)
def test_compute_check_digit_matches_icao_worked_example(data, expected):
    assert compute_check_digit(data) == expected


def test_composite_check_digit_matches_icao_worked_example():
    composite_input = "L898902C3" + "6" + "740812" + "2" + "120415" + "9" + "ZE184226B<<<<<" + "1"
    assert compute_check_digit(composite_input) == "0"


def test_verify_td3_all_pass_on_genuine_mrz():
    fields = parse(ICAO_LINE1 + "\n" + ICAO_LINE2)
    results = verify_td3(fields)
    assert len(results) == 5  # doc number, birth, expiry, optional data, composite
    assert all(r.passed for r in results)


def test_verify_td3_catches_tampered_birth_date():
    """
    Simulate exactly the fraud scenario in the spec: someone edits the
    birth date but doesn't recompute the check digit that sits right next
    to it in the MRZ.
    """
    # Original: ...7408122F... (740812 is the date, '2' is its check digit)
    # Tamper the date to 740811 (one day off) without touching the check digit.
    tampered_line2 = ICAO_LINE2.replace("7408122", "7408112")
    fields = parse(ICAO_LINE1 + "\n" + tampered_line2)
    results = verify_td3(fields)
    by_name = {r.field_name: r for r in results}

    assert by_name["birth_date"].passed is False
    assert by_name["birth_date"].expected_digit == "2"
    assert by_name["birth_date"].computed_digit != "2"
    # Composite digit is computed over the birth date too, so it should
    # also now disagree -- a single edit breaks two independent checks.
    assert by_name["composite"].passed is False


def test_verify_td3_catches_tampered_document_number():
    tampered_line2 = "L898902C46" + ICAO_LINE2[10:]  # change C3 -> C4, keep old check digit
    fields = parse(ICAO_LINE1 + "\n" + tampered_line2)
    results = verify_td3(fields)
    by_name = {r.field_name: r for r in results}
    assert by_name["document_number"].passed is False
