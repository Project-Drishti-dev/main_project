"""
Shared data structures for the Tier 0 pipeline.

Every stage (A: OCR extraction, B: checksum, C: date sanity, D: watchlist)
returns/consumes these types so the orchestrator in pipeline.py can stay
simple and uniform.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FailureReason(str, Enum):
    """Which of the four checks (or a pre-check extraction problem) failed."""

    MRZ_NOT_FOUND = "MRZ not found"
    MRZ_UNREADABLE = "MRZ unreadable"
    MRZ_CHECKSUM = "MRZ checksum"
    DATE_SANITY = "Date sanity"
    WATCHLIST_HIT = "Watchlist hit"


@dataclass
class MRZFields:
    """
    Structured content decoded from the Machine Readable Zone (ICAO 9303).

    Field names follow the spec's terminology. Dates are stored as raw
    6-digit YYMMDD strings exactly as they appear in the MRZ (parsing to
    real calendar dates with century disambiguation happens in
    date_checks.py, since that requires document-type-aware logic).
    """

    format: str  # "TD3" (passport, 2x44) or "TD1" (ID card, 3x30)
    document_type: str
    issuing_country: str
    surname: str
    given_names: str
    document_number: str
    document_number_check_digit: str
    nationality: str
    birth_date: str  # YYMMDD
    birth_date_check_digit: str
    sex: str
    expiry_date: str  # YYMMDD
    expiry_date_check_digit: str
    optional_data: str
    optional_data_check_digit: str  # may be blank depending on format
    composite_check_digit: str
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Output of Stage A: locating + OCR'ing the MRZ strip."""

    success: bool
    raw_text: Optional[str] = None
    mrz_fields: Optional[MRZFields] = None
    error: Optional[str] = None
    ocr_confidence: Optional[float] = None  # 0-100, mean tesseract word confidence


@dataclass
class CheckDigitResult:
    """One individual ICAO check-digit comparison."""

    field_name: str
    raw_data: str
    expected_digit: str
    computed_digit: str

    @property
    def passed(self) -> bool:
        return self.expected_digit == self.computed_digit


@dataclass
class CheckOutcome:
    """Generic pass/fail outcome for a single named check within a stage."""

    check_name: str
    passed: bool
    detail: str = ""


@dataclass
class TierZeroResult:
    """Final verdict returned by run_tier0()."""

    passed: bool
    failed_at: Optional[FailureReason] = None
    reason: str = ""
    elapsed_seconds: float = 0.0
    mrz_fields: Optional[MRZFields] = None
    checks_run: list[CheckOutcome] = field(default_factory=list)

    def __str__(self) -> str:
        if self.passed:
            return f"Result: PASS  ({self.elapsed_seconds*1000:.0f} ms)"
        return (
            f"Result: FAIL\n"
            f"Failed at: {self.failed_at.value}\n"
            f"Reason: {self.reason}\n"
            f"({self.elapsed_seconds*1000:.0f} ms)"
        )
