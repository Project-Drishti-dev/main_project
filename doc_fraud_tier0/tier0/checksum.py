"""
Stage B — ICAO 9303 check-digit verification.

This is the cheapest, highest-signal fraud check we have: the MRZ embeds a
check digit for several fields (document number, birth date, expiry date,
optional data) plus one "composite" check digit over all of them combined.
Each is the deterministic result of a public formula. If a field was
altered without recomputing its check digit, the math won't line up —
that mismatch is treated as strong evidence of tampering.

Reference: ICAO Doc 9303, Part 3, Section 4.9 (Check Digit).
"""
from __future__ import annotations

from .models import MRZFields, CheckDigitResult

# Per ICAO 9303: weights cycle 7, 3, 1 across the data string.
_WEIGHTS = (7, 3, 1)


def char_value(ch: str) -> int:
    """
    Map a single MRZ character to its numeric value per ICAO 9303:
      '0'-'9' -> 0-9
      'A'-'Z' -> 10-35
      '<' (filler) -> 0
    """
    if ch == "<":
        return 0
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    raise ValueError(f"Character {ch!r} is not valid in an MRZ check-digit field")


def compute_check_digit(data: str) -> str:
    """
    Compute the single ICAO 9303 check digit for a data string.

    Applies weights 7,3,1 cyclically to each character's numeric value,
    sums the products, and returns (sum mod 10) as a single digit string.
    """
    total = 0
    for i, ch in enumerate(data):
        total += char_value(ch) * _WEIGHTS[i % 3]
    return str(total % 10)


def verify_field(field_name: str, raw_data: str, expected_digit: str) -> CheckDigitResult:
    """Compute the check digit for one field and compare it to the one printed in the MRZ."""
    computed = compute_check_digit(raw_data)
    return CheckDigitResult(
        field_name=field_name,
        raw_data=raw_data,
        expected_digit=expected_digit,
        computed_digit=computed,
    )


def verify_td3(fields: MRZFields) -> list[CheckDigitResult]:
    """
    Run every ICAO check-digit test defined for the TD3 (passport, 2-line
    44-char) format: document number, birth date, expiry date, optional
    data (if present), and the composite digit over all of them.
    """
    results = [
        verify_field(
            "document_number",
            fields.document_number,
            fields.document_number_check_digit,
        ),
        verify_field(
            "birth_date",
            fields.birth_date,
            fields.birth_date_check_digit,
        ),
        verify_field(
            "expiry_date",
            fields.expiry_date,
            fields.expiry_date_check_digit,
        ),
    ]

    # Optional data (personal number) only carries a meaningful check digit
    # when the field isn't just filler. Some issuers leave it blank/'<'.
    if fields.optional_data.strip("<"):
        results.append(
            verify_field(
                "optional_data",
                fields.optional_data,
                fields.optional_data_check_digit,
            )
        )

    # Composite check digit: computed over doc_number+cd, birth_date+cd,
    # expiry_date+cd, optional_data+cd concatenated together.
    composite_input = (
        fields.document_number
        + fields.document_number_check_digit
        + fields.birth_date
        + fields.birth_date_check_digit
        + fields.expiry_date
        + fields.expiry_date_check_digit
        + fields.optional_data
        + fields.optional_data_check_digit
    )
    results.append(
        verify_field("composite", composite_input, fields.composite_check_digit)
    )

    return results


def verify_td1(fields: MRZFields) -> list[CheckDigitResult]:
    """
    Run the ICAO check-digit tests for the TD1 (ID card, 3-line 30-char)
    format. TD1's composite digit covers a different, format-specific span
    than TD3's.
    """
    results = [
        verify_field(
            "document_number",
            fields.document_number,
            fields.document_number_check_digit,
        ),
        verify_field(
            "birth_date",
            fields.birth_date,
            fields.birth_date_check_digit,
        ),
        verify_field(
            "expiry_date",
            fields.expiry_date,
            fields.expiry_date_check_digit,
        ),
    ]

    # TD1 composite digit is computed over: line 1 positions 6-30 (doc number
    # + its check digit + optional data 1), plus line 2 positions 1-7 (birth
    # date + check digit), 9-15 (expiry date + check digit), and 19-29
    # (optional data 2). We reconstruct that span from our parsed fields.
    composite_input = (
        fields.document_number
        + fields.document_number_check_digit
        + fields.optional_data  # optional data block 1 (from line 1)
        + fields.birth_date
        + fields.birth_date_check_digit
        + fields.expiry_date
        + fields.expiry_date_check_digit
        + fields.optional_data_check_digit  # optional data block 2 (from line 2), reused field
    )
    results.append(
        verify_field("composite", composite_input, fields.composite_check_digit)
    )
    return results


def verify(fields: MRZFields) -> list[CheckDigitResult]:
    """Dispatch to the correct verification routine for the document's MRZ format."""
    if fields.format == "TD3":
        return verify_td3(fields)
    if fields.format == "TD1":
        return verify_td1(fields)
    raise ValueError(f"Unsupported MRZ format: {fields.format}")
