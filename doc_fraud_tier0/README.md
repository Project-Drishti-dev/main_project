# Tier 0 — Instant Document Sanity Gate

The first, cheapest stage of a 3-tier document fraud detection system.
Given a photo of an ID document (passport or ID card), it decides in
under ~0.3s whether the document is obviously fine or obviously wrong,
before anything slower (face matching, deepfake detection) even runs.

```
Result: PASS
```
or
```
Result: FAIL
Failed at: MRZ checksum
Reason: Date of birth check digit mismatch (expected 4, computed 7)
```

## What it checks

Runs four checks in order, **stopping at the first failure**:

| # | Stage | What it catches |
|---|-------|------------------|
| A | Extract the MRZ | Can't even find/read the machine-readable zone |
| B | ICAO 9303 check digits | Tampered document number, birth date, expiry date, or optional data |
| C | Date sanity | Birth date in the future, expired document, DOB mismatch vs. the rest of the document |
| D | Watchlist | Document number matches a known stolen/lost/fraudulent record |

Stage B is the highest-signal, lowest-cost check here: the MRZ encodes
check digits — the deterministic output of a public formula applied to
each field. If a field was edited without recomputing its check digit,
the math won't add up. That's essentially free proof of tampering.

## Quick start

```bash
pip install -r requirements.txt
# tesseract itself is a system package, not a pip package:
#   apt-get install tesseract-ocr   (Debian/Ubuntu)
#   brew install tesseract          (macOS)

python -m tier0 sample_data/sample_valid_passport.png
python -m tier0 sample_data/sample_expired_passport.png
python -m tier0 sample_data/sample_tampered_dob.png
python -m tier0 sample_data/sample_valid_passport.png --watchlist sample_data/watchlist.json
python -m tier0 sample_data/sample_expired_passport.png --json
```

`sample_tampered_dob.png` reproduces the exact scenario from the spec: a
birth date edited without recomputing its check digit —

```
Result: FAIL
Failed at: MRZ checksum
Reason: birth date check digit mismatch (expected 2, computed 1)
```

As a library:

```python
from tier0 import run_tier0

result = run_tier0("document.jpg", watchlist_path="watchlist.json")

if result.passed:
    send_to_tier1(document)
else:
    reject(reason=result.reason, failed_at=result.failed_at)
```

## Project layout

```
tier0/
  models.py        Shared result/data types used across every stage
  checksum.py       Stage B — ICAO 9303 check-digit algorithm
  mrz_parse.py       TD3 (passport, 2x44) & TD1 (ID card, 3x30) MRZ text -> structured fields
  mrz_extract.py     Stage A — image -> MRZ strip -> OCR -> parsed fields
  date_checks.py    Stage C — future birthdate / expiry / DOB cross-check
  watchlist.py       Stage D — cached O(1) watchlist lookup
  pipeline.py         Stage E — orchestrates A->B->C->D, fail-fast
  __main__.py         CLI (`python -m tier0 ...`)
tests/                pytest suite, incl. synthetic MRZ image generation for
                      real end-to-end OCR testing (no external test images needed)
sample_data/          Example images + watchlist.json for the quick start above
```

## The ICAO 9303 check-digit algorithm (`checksum.py`)

Each character maps to a value (`0-9` -> itself, `A-Z` -> `10-35`, filler
`<` -> `0`), weights `7, 3, 1` cycle across the string, and the check
digit is `(sum of value*weight) mod 10`. TD3 passports carry this for the
document number, birth date, expiry date, optional data, and a
"composite" digit computed over all of them concatenated together — so a
single edited field breaks two independent checks at once (its own digit,
and the composite). The implementation is verified in
`tests/test_checksum.py` against the official worked example from ICAO
Doc 9303.

## Watchlist format (`watchlist.py`)

```json
{
  "entries": [
    {"document_number": "L898902C3", "issuing_country": "UTO", "reason": "Reported stolen"},
    {"document_number": "AB1234567", "reason": "Previously flagged as fraudulent"}
  ]
}
```
`issuing_country` is optional; omit it to flag a document number across
all countries, or include it to avoid collisions between countries that
reuse number formats. Lookups are O(1) against an in-memory index that's
cached per file path and automatically invalidated when the file's mtime
changes — repeated calls in the same process don't re-read from disk.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

The test suite renders synthetic MRZ document images on the fly (see
`tests/conftest.py`) and runs them through the *real* OCR pipeline, so
the tests exercise the actual image -> text -> fields -> checksum path,
not just the math in isolation.

## Known limitations / things to tune before production

- **OCR is best-effort by design.** Stage A doesn't try to be perfect —
  Stage B's check-digit math is the actual correctness backstop. A
  misread digit in a checksummed field correctly produces a FAIL (a
  false rejection you'd want to re-photograph/retry), which is the safe
  failure direction for a fraud gate; it never produces a false PASS from
  garbled data, since a wrong digit essentially never happens to satisfy
  the checksum by chance. In testing, generic tesseract occasionally
  misreads a digit when it sits immediately after a long unbroken run of
  the repeated `<` filler character — a known quirk of general-purpose
  OCR models on this kind of highly repetitive input. A production
  deployment would likely swap in an OCR-B-trained model (or a
  purpose-built MRZ OCR library) for meaningfully better accuracy than
  stock tesseract.
- **MRZ location heuristic** (`mrz_extract._locate_mrz_band`) assumes the
  strip is in the bottom ~45% of the image and uses row-darkness density
  to isolate it. It's been tuned against synthetic photo-page layouts,
  not a large real-world dataset — expect to retune the density threshold
  and crop margins against real scans/photos.
- **DOB visual-zone cross-check** (`date_checks.check_dob_matches_visual_zone`)
  is intentionally best-effort: it only fires if the caller supplies OCR
  text from the rest of the document, and only fails on a confident
  mismatch (no date found at all -> skipped, not failed), since printed
  layouts vary enormously across issuers.
- **TD2 format** (2x36, used by some national ID/visa documents) isn't
  wired up yet — only TD3 (passport) and TD1 (ID card). It would slot in
  the same way as TD1 in `mrz_parse.py` / `checksum.py`.
- **Time budget**: the 0.3s target is dominated by the OCR call. If that
  ever becomes the bottleneck in practice, the biggest lever is swapping
  tesseract for a faster/smaller MRZ-specific OCR model rather than
  further optimizing the OpenCV preprocessing.
