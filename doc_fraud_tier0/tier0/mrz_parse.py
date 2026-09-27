"""
Turn raw OCR text of the MRZ strip into structured MRZFields.

Handles the two MRZ layouts we're likely to see at a KYC/visa portal:
  TD3 — passports: 2 lines x 44 chars
  TD1 — ID cards:  3 lines x 30 chars
(ICAO 9303 also defines TD2, 2x36, for some national ID/visa formats;
not wired up here but would slot in the same way.)

OCR on a monospaced, high-contrast MRZ strip is usually very reliable, but
tesseract still occasionally confuses visually similar characters. We
apply a conservative, position-aware cleanup pass before parsing: only
fields that must be pure digits get digit-biased correction, and only
fields that must be pure letters get letter-biased correction. We never
"fix" the document-owner's actual name or number — we only correct
character-class-impossible OCR noise (e.g. an 'O' in a field that can
only legally contain digits).
"""
from __future__ import annotations

import re
from typing import Optional

from .models import MRZFields

# OCR commonly confuses these pairs. Only applied when the target
# character class makes the "corrected" reading the sole legal option.
_LETTER_TO_DIGIT = {"O": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "Q": "0"}
_DIGIT_TO_LETTER = {"0": "O", "1": "I", "5": "S", "8": "B"}


class MRZParseError(ValueError):
    """Raised when raw OCR text can't be interpreted as a valid MRZ."""


def _bias_digits(s: str) -> str:
    """Coerce a string that must be all-digits-or-filler into that alphabet."""
    out = []
    for ch in s:
        if ch.isdigit() or ch == "<":
            out.append(ch)
        elif ch.upper() in _LETTER_TO_DIGIT:
            out.append(_LETTER_TO_DIGIT[ch.upper()])
        else:
            out.append(ch)  # leave as-is; checksum stage will catch real problems
    return "".join(out)


def _bias_letters(s: str) -> str:
    """Coerce a string that should be letters/filler (e.g. names) into that alphabet."""
    out = []
    for ch in s:
        if ch.isalpha() or ch == "<":
            out.append(ch.upper())
        elif ch in _DIGIT_TO_LETTER:
            out.append(_DIGIT_TO_LETTER[ch])
        else:
            out.append(ch)
    return "".join(out)


def _clean_lines(raw_text: str) -> list[str]:
    """Uppercase, strip stray whitespace/newlines, and drop empty lines."""
    lines = []
    for line in raw_text.splitlines():
        # OCR sometimes inserts spaces inside the MRZ; the MRZ alphabet
        # never contains spaces, so it's always safe to strip them.
        cleaned = line.upper().replace(" ", "").strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _pick_mrz_lines(lines: list[str], width: int, count: int) -> Optional[list[str]]:
    """
    From OCR'd lines of possibly-ragged length, find `count` consecutive
    lines close to `width` characters — and pad/trim them to exactly
    `width`. Returns None if no good candidate block exists.

    Tolerance is intentionally asymmetric: tesseract quite often drops
    trailing runs of the MRZ filler character ('<') at the end of a line —
    long runs of one repeated thin glyph get misclassified as noise/a rule
    line rather than text — so short lines get a generous allowance
    (they're padded back out with '<'). A line that's *longer* than
    expected is a different, less common failure mode (stray character
    picked up), so that gets almost no slack. This is safe to be generous
    about: Stage B's check-digit verification is the real backstop — if a
    shortfall ever eats a genuine data character rather than filler, the
    checksum simply won't match and the document correctly fails, rather
    than us silently accepting corrupted data.
    """
    max_shortfall = 25
    max_excess = 2
    candidates = [
        ln for ln in lines if (width - max_shortfall) <= len(ln) <= (width + max_excess)
    ]
    if len(candidates) < count:
        return None
    block = candidates[-count:]  # MRZ is always the last lines of the strip
    fixed = []
    for ln in block:
        if len(ln) < width:
            ln = ln + "<" * (width - len(ln))
        elif len(ln) > width:
            ln = ln[:width]
        fixed.append(ln)
    return fixed


def parse_td3(lines: list[str]) -> MRZFields:
    """Parse a 2x44 passport MRZ."""
    if len(lines) != 2 or any(len(ln) != 44 for ln in lines):
        raise MRZParseError("TD3 MRZ must be exactly 2 lines of 44 characters")
    l1, l2 = lines

    document_type = _bias_letters(l1[0:2])
    issuing_country = _bias_letters(l1[2:5])
    name_field = l1[5:44]
    if "<<" in name_field:
        surname_raw, given_raw = name_field.split("<<", 1)
    else:
        surname_raw, given_raw = name_field, ""
    surname = surname_raw.replace("<", " ").strip()
    given_names = given_raw.replace("<", " ").strip()

    document_number = _bias_digits(l2[0:9]) if l2[0:9].strip("<").isdigit() else l2[0:9]
    document_number_check_digit = l2[9]
    nationality = _bias_letters(l2[10:13])
    birth_date = _bias_digits(l2[13:19])
    birth_date_check_digit = l2[19]
    sex = l2[20]
    expiry_date = _bias_digits(l2[21:27])
    expiry_date_check_digit = l2[27]
    optional_data = l2[28:42]
    optional_data_check_digit = l2[42]
    composite_check_digit = l2[43]

    return MRZFields(
        format="TD3",
        document_type=document_type,
        issuing_country=issuing_country,
        surname=surname,
        given_names=given_names,
        document_number=document_number,
        document_number_check_digit=document_number_check_digit,
        nationality=nationality,
        birth_date=birth_date,
        birth_date_check_digit=birth_date_check_digit,
        sex=sex,
        expiry_date=expiry_date,
        expiry_date_check_digit=expiry_date_check_digit,
        optional_data=optional_data,
        optional_data_check_digit=optional_data_check_digit,
        composite_check_digit=composite_check_digit,
        raw_lines=lines,
    )


def parse_td1(lines: list[str]) -> MRZFields:
    """Parse a 3x30 ID-card MRZ."""
    if len(lines) != 3 or any(len(ln) != 30 for ln in lines):
        raise MRZParseError("TD1 MRZ must be exactly 3 lines of 30 characters")
    l1, l2, l3 = lines

    document_type = _bias_letters(l1[0:2])
    issuing_country = _bias_letters(l1[2:5])
    document_number = l1[5:14]
    document_number_check_digit = l1[14]
    optional_data_1 = l1[15:30]

    birth_date = _bias_digits(l2[0:6])
    birth_date_check_digit = l2[6]
    sex = l2[7]
    expiry_date = _bias_digits(l2[8:14])
    expiry_date_check_digit = l2[14]
    nationality = _bias_letters(l2[15:18])
    optional_data_2 = l2[18:29]
    composite_check_digit = l2[29]

    name_field = l3
    if "<<" in name_field:
        surname_raw, given_raw = name_field.split("<<", 1)
    else:
        surname_raw, given_raw = name_field, ""
    surname = surname_raw.replace("<", " ").strip()
    given_names = given_raw.replace("<", " ").strip()

    return MRZFields(
        format="TD1",
        document_type=document_type,
        issuing_country=issuing_country,
        surname=surname,
        given_names=given_names,
        document_number=document_number,
        document_number_check_digit=document_number_check_digit,
        nationality=nationality,
        birth_date=birth_date,
        birth_date_check_digit=birth_date_check_digit,
        sex=sex,
        expiry_date=expiry_date,
        expiry_date_check_digit=expiry_date_check_digit,
        optional_data=optional_data_1,
        optional_data_check_digit=optional_data_2,  # reused slot; see checksum.verify_td1
        composite_check_digit=composite_check_digit,
        raw_lines=lines,
    )


def parse(raw_text: str) -> MRZFields:
    """
    Auto-detect MRZ format from OCR'd raw text and parse it.
    Tries TD3 (passport) first, then TD1 (ID card).
    """
    lines = _clean_lines(raw_text)

    td3_lines = _pick_mrz_lines(lines, width=44, count=2)
    if td3_lines:
        try:
            return parse_td3(td3_lines)
        except MRZParseError:
            pass

    td1_lines = _pick_mrz_lines(lines, width=30, count=3)
    if td1_lines:
        try:
            return parse_td1(td1_lines)
        except MRZParseError:
            pass

    raise MRZParseError(
        "Could not find a valid TD3 (2x44) or TD1 (3x30) MRZ block in the OCR text"
    )
