"""
Stage C — basic sanity checks on the dates in the MRZ.

These catch the "wait, that can't be right" cases a human would spot
instantly: a birth date in the future, an already-expired document, or a
birth date that doesn't match what's printed elsewhere on the document.

None of this requires understanding whether the document is a skillful
forgery — it's just arithmetic and string comparison, which is exactly
why it belongs in the instant/cheap Tier 0 gate.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .models import CheckOutcome

_YYMMDD_RE = re.compile(r"^\d{6}$")


class DateParseError(ValueError):
    pass


def _split_yymmdd(raw: str) -> tuple[int, int, int]:
    if not _YYMMDD_RE.match(raw):
        raise DateParseError(f"'{raw}' is not a 6-digit YYMMDD date")
    yy = int(raw[0:2])
    mm = int(raw[2:4])
    dd = int(raw[4:6])
    return yy, mm, dd


def resolve_birth_date(raw_yymmdd: str, today: Optional[date] = None) -> date:
    """
    Resolve an MRZ birth-date's 2-digit year into a full calendar date.

    ICAO MRZ dates are always YY, never YYYY, so the century has to be
    inferred. A birth date can't be in the future and people don't live
    past ~120, so: try interpreting YY as 19xx and as 20xx, keep whichever
    candidate is not in the future and yields a plausible age; if both
    qualify, prefer the more recent one (20xx) since that's the common case.
    """
    today = today or date.today()
    yy, mm, dd = _split_yymmdd(raw_yymmdd)

    candidates = []
    for century in (2000, 1900):
        try:
            d = date(century + yy, mm, dd)
        except ValueError:
            continue  # invalid calendar date (e.g. Feb 30) under this century guess
        age_days = (today - d).days
        if age_days < 0:
            continue  # would be a future birth date under this guess
        age_years = age_days / 365.25
        if age_years > 120:
            continue  # implausibly old
        candidates.append(d)

    if not candidates:
        # Neither century guess produced a sane date — let the caller's
        # "birth date in the future / impossible" check report this as a
        # hard failure rather than silently picking something.
        raise DateParseError(
            f"Birth date '{raw_yymmdd}' has no plausible calendar interpretation "
            f"(not in the future, age <= 120 years)"
        )

    # Prefer the most recent (youngest) plausible candidate — the common case.
    return max(candidates)


def resolve_expiry_date(raw_yymmdd: str) -> date:
    """
    Resolve an MRZ expiry date's 2-digit year. Travel/ID documents using
    the MRZ format postdate 1980, so 20xx is the only sane interpretation
    for the vast majority of real-world documents (including long-expired
    ones, which is fine — expiry is checked separately against today).
    """
    yy, mm, dd = _split_yymmdd(raw_yymmdd)
    return date(2000 + yy, mm, dd)


def check_birth_date_not_future(raw_birth_date: str, today: Optional[date] = None) -> CheckOutcome:
    """FAIL if the birth date can't correspond to a real person alive today."""
    today = today or date.today()
    try:
        resolve_birth_date(raw_birth_date, today=today)
    except DateParseError as e:
        return CheckOutcome(
            check_name="birth_date_plausible", passed=False, detail=str(e)
        )
    return CheckOutcome(
        check_name="birth_date_plausible", passed=True, detail="Birth date is a plausible past date"
    )


def check_not_expired(raw_expiry_date: str, today: Optional[date] = None) -> CheckOutcome:
    """FAIL if the document's expiry date is in the past."""
    today = today or date.today()
    try:
        expiry = resolve_expiry_date(raw_expiry_date)
    except (DateParseError, ValueError) as e:
        return CheckOutcome(check_name="not_expired", passed=False, detail=f"Invalid expiry date: {e}")

    if expiry < today:
        return CheckOutcome(
            check_name="not_expired",
            passed=False,
            detail=f"Document expired on {expiry.isoformat()}",
        )
    return CheckOutcome(
        check_name="not_expired", passed=True, detail=f"Valid until {expiry.isoformat()}"
    )


# Common printed date formats seen in the visual (human-readable) zone of
# ID documents, e.g. "DOB: 15 JAN 1990", "01/15/1990", "1990-01-15".
_VISUAL_DATE_PATTERNS = [
    re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"),  # DD/MM/YYYY or MM/DD/YYYY
    re.compile(r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})"),  # YYYY-MM-DD
    re.compile(
        r"(\d{1,2})\s*"
        r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\w*\s*"
        r"(\d{4})",
        re.IGNORECASE,
    ),  # 15 JAN 1990
]
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _extract_candidate_dates(visual_text: str) -> list[date]:
    found: list[date] = []
    for pattern in _VISUAL_DATE_PATTERNS:
        for m in pattern.finditer(visual_text):
            groups = m.groups()
            try:
                if len(groups) == 3 and groups[1].isalpha():
                    dd, mon, yyyy = groups
                    found.append(date(int(yyyy), _MONTHS[mon.upper()[:3]], int(dd)))
                elif len(groups) == 3 and len(groups[0]) == 4:
                    yyyy, mm, dd = groups
                    found.append(date(int(yyyy), int(mm), int(dd)))
                else:
                    a, b, yyyy = groups
                    # Ambiguous DD/MM vs MM/DD — accept either that parses validly;
                    # we're cross-checking against a known MRZ date, not guessing blind.
                    for d1, d2 in ((a, b), (b, a)):
                        try:
                            found.append(date(int(yyyy), int(d2), int(d1)))
                        except ValueError:
                            pass
            except (ValueError, KeyError):
                continue
    return found


def check_dob_matches_visual_zone(
    raw_mrz_birth_date: str, visual_zone_text: Optional[str]
) -> CheckOutcome:
    """
    Cross-check the MRZ birth date against a date printed elsewhere on the
    document (the human-readable "visual inspection zone"), if that text
    was supplied by the caller (e.g. from a general OCR pass over the rest
    of the document photo, outside the MRZ strip).

    This is best-effort: document layouts vary a lot, so if no
    corroborating date is found at all we treat that as "not checkable"
    rather than a failure — we only FAIL on an actual, confident mismatch.
    """
    if not visual_zone_text or not visual_zone_text.strip():
        return CheckOutcome(
            check_name="dob_matches_visual_zone",
            passed=True,
            detail="No visual-zone text supplied; cross-check skipped",
        )

    try:
        mrz_date = resolve_birth_date(raw_mrz_birth_date)
    except DateParseError as e:
        return CheckOutcome(
            check_name="dob_matches_visual_zone", passed=False, detail=str(e)
        )

    candidates = _extract_candidate_dates(visual_zone_text)
    if not candidates:
        return CheckOutcome(
            check_name="dob_matches_visual_zone",
            passed=True,
            detail="No date found in visual zone text; cross-check skipped",
        )

    if mrz_date in candidates:
        return CheckOutcome(
            check_name="dob_matches_visual_zone",
            passed=True,
            detail=f"Visual zone date matches MRZ birth date {mrz_date.isoformat()}",
        )

    return CheckOutcome(
        check_name="dob_matches_visual_zone",
        passed=False,
        detail=(
            f"MRZ birth date {mrz_date.isoformat()} does not match any date found "
            f"printed elsewhere on the document ({[d.isoformat() for d in candidates]})"
        ),
    )


def run_all(
    raw_birth_date: str,
    raw_expiry_date: str,
    visual_zone_text: Optional[str] = None,
    today: Optional[date] = None,
) -> list[CheckOutcome]:
    """Run every Stage C date check, in order."""
    return [
        check_birth_date_not_future(raw_birth_date, today=today),
        check_not_expired(raw_expiry_date, today=today),
        check_dob_matches_visual_zone(raw_birth_date, visual_zone_text),
    ]
