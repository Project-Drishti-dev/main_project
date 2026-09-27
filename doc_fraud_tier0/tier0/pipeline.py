"""
Stage E — the Tier 0 orchestrator.

Runs, in order:
  A. MRZ extraction (locate strip -> preprocess -> OCR -> parse)
  B. Check-digit verification
  C. Date sanity checks
  D. Watchlist lookup

Stops at the first failure and reports which check failed and why. This
is the single public entry point the rest of the fraud-detection system
(and Tier 1) calls into.
"""
from __future__ import annotations

import time
from typing import Optional

from . import checksum, date_checks, watchlist
from .models import CheckOutcome, FailureReason, TierZeroResult
from .mrz_extract import extract_mrz_text

# Tier 0's budget per the spec: must return well under this.
TIME_BUDGET_SECONDS = 0.3


def run_tier0(
    image_path: str,
    watchlist_path: Optional[str] = None,
    visual_zone_text: Optional[str] = None,
) -> TierZeroResult:
    """
    Run the full Tier 0 instant/cheap fraud gate on a document photo.

    Args:
        image_path: path to the document photo (passport/ID photo page).
        watchlist_path: path to a watchlist JSON file (see watchlist.py for
            shape). If omitted or the file doesn't exist, the watchlist
            check is skipped rather than failed — callers integrating this
            into a live system should always pass a real path.
        visual_zone_text: optional OCR text from the rest of the document
            (outside the MRZ strip), used for the DOB cross-check in Stage
            C. If not supplied, that sub-check is skipped rather than
            failed, since not every caller will have run general OCR yet.

    Returns:
        TierZeroResult — .passed is True/False; on failure, .failed_at and
        .reason explain what tripped the gate.
    """
    start = time.perf_counter()
    checks_run: list[CheckOutcome] = []

    # --- Stage A: extract & parse the MRZ ---------------------------------
    extraction = extract_mrz_text(image_path)
    if not extraction.success or extraction.mrz_fields is None:
        failed_at = (
            FailureReason.MRZ_NOT_FOUND
            if extraction.raw_text is None
            else FailureReason.MRZ_UNREADABLE
        )
        return TierZeroResult(
            passed=False,
            failed_at=failed_at,
            reason=extraction.error or "Could not extract a readable MRZ",
            elapsed_seconds=time.perf_counter() - start,
            checks_run=checks_run,
        )
    fields = extraction.mrz_fields

    # --- Stage B: ICAO check-digit verification ----------------------------
    digit_results = checksum.verify(fields)
    for r in digit_results:
        outcome = CheckOutcome(
            check_name=f"checksum:{r.field_name}",
            passed=r.passed,
            detail=(
                f"expected {r.expected_digit}, computed {r.computed_digit}"
                if not r.passed
                else "check digit matches"
            ),
        )
        checks_run.append(outcome)
        if not outcome.passed:
            field_label = r.field_name.replace("_", " ")
            return TierZeroResult(
                passed=False,
                failed_at=FailureReason.MRZ_CHECKSUM,
                reason=(
                    f"{field_label} check digit mismatch "
                    f"(expected {r.expected_digit}, computed {r.computed_digit})"
                ),
                elapsed_seconds=time.perf_counter() - start,
                mrz_fields=fields,
                checks_run=checks_run,
            )

    # --- Stage C: date sanity checks ---------------------------------------
    date_outcomes = date_checks.run_all(
        raw_birth_date=fields.birth_date,
        raw_expiry_date=fields.expiry_date,
        visual_zone_text=visual_zone_text,
    )
    for outcome in date_outcomes:
        checks_run.append(outcome)
        if not outcome.passed:
            return TierZeroResult(
                passed=False,
                failed_at=FailureReason.DATE_SANITY,
                reason=outcome.detail,
                elapsed_seconds=time.perf_counter() - start,
                mrz_fields=fields,
                checks_run=checks_run,
            )

    # --- Stage D: watchlist lookup ------------------------------------------
    watchlist_outcome = watchlist.check_watchlist(
        document_number=fields.document_number,
        watchlist_path=watchlist_path or "",
        issuing_country=fields.issuing_country,
    )
    checks_run.append(watchlist_outcome)
    if not watchlist_outcome.passed:
        return TierZeroResult(
            passed=False,
            failed_at=FailureReason.WATCHLIST_HIT,
            reason=watchlist_outcome.detail,
            elapsed_seconds=time.perf_counter() - start,
            mrz_fields=fields,
            checks_run=checks_run,
        )

    # --- All checks passed ---------------------------------------------------
    return TierZeroResult(
        passed=True,
        elapsed_seconds=time.perf_counter() - start,
        mrz_fields=fields,
        checks_run=checks_run,
    )
