"""
Tier 0 — instant document sanity gate.

Public API:
    from tier0 import run_tier0
    result = run_tier0("path/to/document.jpg", watchlist_path="watchlist.json")
"""
from .pipeline import run_tier0
from .models import TierZeroResult, CheckOutcome, FailureReason

__all__ = ["run_tier0", "TierZeroResult", "CheckOutcome", "FailureReason"]
