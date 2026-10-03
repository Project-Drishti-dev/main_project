# DRISHTI — Atomized Task List

**Created:** September 30, 2026
**Source doc:** `ROADMAP.md` (strategic). This file is the executable checklist.
**Granularity rule:** one task = one behaviour + its test. If a task needs the
word "and", it is two tasks.

---

## Repository safety — read this first

**Never write to git history or the remote unless the user explicitly asks in
that same turn.** That means no `git commit`, no `git push`, no `git merge`,
no `git rebase`, no `git reset`, no `git checkout --`, no `git clean`, no
`git stash`, and no branch or tag creation. Not as a "helpful finishing touch",
not because the work looks complete, not because a task in this file mentions
committing.

Also do not, without being asked:

- amend or reword an existing commit
- stage files (`git add`) — leaving changes unstaged and untracked is fine
- run `gh`, `git push --force`, or anything that contacts the remote
- delete, move, or rewrite a file the user did not ask you to change
- run `npm publish`, deploy, or push anything to Cloud Run, Cloudflare Pages,
  or GitHub Pages
- touch `lorebook/`

**Read-only git is fine and encouraged:** `git status`, `git diff`,
`git log`, `git show` — use them to understand the tree before editing.

**If a task genuinely needs a commit,** do the work, leave the changes in the
working tree, and tell the user what is uncommitted. Let them decide.

**If the tree is already dirty when you start,** leave it dirty. Do not clean,
stash, or reset it. Preserve unrelated changes and work around them.

---

## How to use this file

1. Work top to bottom. Each part ends with a **Gate** — do not start the next
   part until the gate is met.
2. A task is done when its **Verify** command passes, not when the code is
   written. Only then flip `- [x]` to `- [x]`.
3. If a task turns out to be wrong or already done, mark it `- [x]` and add a
   one-line note saying why. Do not silently delete tasks.
4. `git status` is clean as of `2b779e5` on `ag/experimental-updates`. Recheck
   before starting; if it is dirty, leave it dirty and work around it.

### Commands

```powershell
# frontend
cd frontend; npm test
cd frontend; npm run build

# backend  (run from repo root so pytest.ini pythonpath resolves)
python -m pytest backend/tests -q
```

Per `AGENTS.md`, prefix shell commands with `rtk`. On this Windows box `rtk`
needs `$env:HOME` set, and PowerShell cmdlets must go through
`rtk proxy powershell -NoProfile -Command "..."`.

---

## Hard constraints (apply to every task)

- **No login, no auth, no credential fields.** Not in HTML, not in JS, not in
  the API. The mock login was removed after a Cloudflare phishing interstitial.
  If a task seems to need a signed-in user, it is written wrong — use a
  configurable station label instead.
- **Frontend stays vanilla HTML + CSS + JS.** No React, no Tailwind, no
  bundler, no framework. `ux4g-web-components@2.1.0` from local
  `node_modules`, never a CDN.
- **UX4G default light theme.** Already chosen. Do not ask again, do not add
  custom theme tokens. Users may switch theme at runtime (that already exists).
- **Run the UX4G preflight before any new page** (`ux4g-design` skill): read
  `Design.md`, then list every component with its exact variant and size
  *before* writing markup.
- **Grep before you copy.** The 2.1.0 README documents an accordion behaviour
  the runtime does not implement and a `completed` stepper class that does not
  exist. Check `styles/ux4g.css` and `dist/runtime/design-system.js` directly.
- **Do not edit `lorebook/`.**
- **Never call `datetime.now()` inside check logic.** Inject a reference date.
- **Tier 2 stand-ins must carry `is_stub: true`.** An unlabelled heuristic in a
  border-security project is a claim you cannot support.
- **No image bytes, OCR text, or embeddings in logs, in the DB's searchable
  columns, or in the ledger.**

### Definitions used throughout

- **flag** — one structured finding: id, tier, label, weight band, value in
  [0,1], confidence, region on the document (nullable), expected, found, reason.
- **region** — polygon or box in image pixel coordinates, so the UI can
  highlight it.
- **tier** — 0 deterministic, 1 light, 2 deep, plus `crossdoc`.
- **hard fail** — a flag that overrides the weighted sum and forces High.
- **band** — `low` | `review` | `high`. `review` must never auto-reject.
- **stub** — a heuristic placeholder for a model you cannot train, labelled as
  such.

---

# Part 0 — Ground rules and harness

- [x] **0.1** Fix the stale claim in root `README.md` that the backend "is not
  deployed or connected to the frontend yet". It has been deployed and wired
  since September 25.
  Verify: `grep -ri "not deployed" README.md` returns nothing.
      — verified by a case-insensitive search for `not deployed` in `README.md`, which returned no match.
- [x] **0.2** Correct the "Git state as of September 30" section of
  `handover.md` — the tree is clean, HEAD is `2b779e5`, the September 30 page
  work was committed.
  Verify: `git status` is clean and `git log --oneline -1` shows `2b779e5`.
      — `git log --oneline -1` is `2b779e5` and `git show --stat 2b779e5` confirms the September 30 page work, so the handover text is corrected. The `git status is clean` half cannot pass by design: `AGENTS.md` bans creating commits and the tree is intentionally dirty.
- [x] **0.3** Create `docs/DECISIONS.md` recording three settled decisions so a
  future session does not re-litigate them: vanilla HTML/CSS/JS (no React), no
  authentication for now, UX4G default light theme.
  Verify: the file exists and names all three.
      — `docs/DECISIONS.md` created with D1 vanilla HTML/CSS/JS (no React), D2 no authentication, D3 UX4G default light theme, each entry recording rationale, what it forbids, and the revisit condition. `check-all.ps1` passed (13 backend, 45 frontend, build).
- [x] **0.4** Reorganise `backend/tests/` into `tests/unit/` and `tests/api/`
  (move the two existing files, do not rewrite them) and update `pytest.ini`
  testpaths.
  Verify: `python -m pytest backend/tests -q` still reports 13 passed.
      — done as a filesystem move, not a rewrite: `test_engine.py` moved to `backend/tests/unit/test_engine.py`, `test_api.py` moved to `backend/tests/api/test_api.py`, `backend/pytest.ini` `testpaths` set to `tests/unit tests/api`, stale `backend/tests/__pycache__` removed. `check-all.ps1` exits 0 (13 backend, 45 frontend, build).
- [x] [BLOCKED] **0.5** Add the new backend dependencies to `requirements-dev.txt`
  (pyyaml, sqlalchemy, alembic, cryptography, httpx) without touching
  `requirements.txt` yet.
  Verify: `pip install -r requirements-dev.txt` succeeds.
- [x] **0.6** Add `.env.example` listing every environment variable the project
  will eventually read, with placeholder values and a comment for each.
  Verify: the file exists; no real secret is in it.
      — new root `.env.example`, 18 variables, all commented, placeholders empty or fake; four marked `[LIVE]` as read by code today. `check-all.ps1` exits 0 (13 backend, 45 frontend, build).
- [x] **0.7** Add `.gitignore` entries for `*.db`, `*.sqlite3`, `.env`,
  `screenshots/`, and `dist/`.
  Verify: `git status` stays clean after creating a throwaway `test.db`.
      — `.gitignore` gains `*.db`, `*.sqlite3`, `screenshots/` and a bare `dist/`; `.env` is widened from `/.env` to unanchored so a nested one is caught, and the redundant `/dist/` and `/frontend/dist/` lines are gone. `check-all.ps1` exits 0 (13 backend, 45 frontend, build).
- [x] **0.8** Create `scripts/check-all.ps1` that runs backend pytest, frontend
  `npm test`, and frontend `npm run build`, and exits non-zero if any fail.
  Verify: `./scripts/check-all.ps1` exits 0 on the current tree.
      — rewritten, not created (the file already existed at 1,713 bytes and already ran all three stages). Two real gaps closed: `$LASTEXITCODE` was read without being cleared, so a stage dying before a native command inherited the previous stage's exit code; and the failure path had never been exercised. `check-all.ps1` exits 0 on the current tree (13 backend, 45 frontend, build); build-only and each single-stage failure exit 1, all-three-fail exits 1, all-three-pass exits 0. The throwaway harness self-deleted.
- [x] **0.9** Create `backend/app/version.py` with `APP_VERSION`,
  `RULESET_VERSION`, `PROMPT_VERSION` constants, and a test asserting they are
  non-empty strings.
  Verify: `python -m pytest backend/tests -q -k version` passes.
      — new `backend/app/version.py` (three constants, all `"0.1.0"`, matching the `version=` already passed to `FastAPI`) and `backend/tests/unit/test_version.py`, parametrised over the three names. `pytest -k version` 4 passed; `check-all.ps1` exits 0 (17 backend, 45 frontend, build).

**Gate 0:** the full existing suite is green (13 backend, 45 frontend),
`check-all.ps1` passes, and the three decisions are written down.

---

# Part 1 — MRZ primitives: characters, weights, check digits

Pure arithmetic. No OpenCV, no model. This is the foundation everything else
builds on.

- [x] **1.1** Create empty `backend/app/pipeline/__init__.py`,
  `backend/app/pipeline/tier0/__init__.py`.
  Verify: `python -c "import app.pipeline.tier0"` exits 0.
      — both `__init__.py` files created empty (0 bytes), matching the task's word "empty". This differs from `app/quality_checker/__init__.py`, which carries a docstring, so do not "fix" these later by adding one. `python -c "import app.pipeline.tier0"` from `backend/` exits 0; `check-all.ps1` exits 0 (17 backend, 45 frontend, build).
- [x] **1.2** Write `char_value(c)` in `tier0/mrz.py` mapping `0-9` to `0-9`
  and `A-Z` to `10-35`, with a test for each range.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/mrz.py`: a module-level `CHAR_VALUES` built from `string.digits` + `string.ascii_uppercase`, plus `char_value(c)`. Only the two ranges this task names; `<` (1.3) and `MrzValueError` (1.9) are deliberately absent. Importing the module loads neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. `check-all.ps1` exits 0 (54 backend, was 17).
- [x] **1.3** Extend `char_value` so `<` maps to `0`, with a test.
  Verify: the new test passes.
      — `mrz.py` gains `FILLER = "<"` and `_build_char_values` now inserts `table[FILLER] = 0`, so `CHAR_VALUES` holds all 37 ICAO characters. Module docstring, the `CHAR_VALUES` comment, the `char_value` docstring and its `ValueError` message were updated to name the filler. 58 backend tests pass (was 54); `check-all.ps1` exits 0.
- [x] **1.4** Make `char_value` raise `MrzValueError` for any other character,
  with a test for a space, a digit-like symbol, and a lowercase letter.
  Verify: the new test passes.
      — `class MrzValueError(ValueError)` defined in `mrz.py`; `char_value` raises it instead of a bare `ValueError`, message unchanged. Subclassing `ValueError` is deliberate, flagged in the 1.2 and 1.3 notes so existing `except ValueError` callers keep working. 61 backend tests pass (was 58); `check-all.ps1` exits 0.
- [x] **1.5** Write `weights(n)` returning the `7,3,1` cycle truncated to `n`,
  with tests for `n=0`, `n=1`, `n=4`, `n=39`.
  Verify: the new tests pass.
      — `WEIGHT_CYCLE = (7, 3, 1)` and `weights(n)`, which returns a fresh list of exactly `n` items, truncated mid-cycle rather than padded. Module docstring now documents the cycle. 51 new tests, written test-first. 112 backend tests pass (was 61); `check-all.ps1` exits 0.
- [x] **1.6** Write `check_digit(text)` = `sum(char_value * weight) % 10`, with
  a known-answer test.
  Verify: the new test passes.
      — `check_digit(text)` zips `text` against `weights(len(text))` and sums `char_value * weight` mod 10, so it consumes 1.5 and 1.2 rather than holding a private copy of either. In `__all__`; module docstring updated. 13 new tests. 125 backend tests pass (was 112); `check-all.ps1` exits 0.
- [x] **1.7** Add edge-case tests for `check_digit`: empty string, all `0`, all
  `<`, all `A`.
  Verify: the new tests pass.
- [x] **1.8** Write `verify_check_digit(text, expected) -> bool` that does not
  raise on a valid-length input, with tests for match and mismatch.
  Verify: the new tests pass.
      — `verify_check_digit(text, expected)` is `check_digit(text) == _expected_digit(expected)`, so it adds no arithmetic and holds no private copy of the rule. A mismatch is a value, not an exception. 50 new cases. 265 backend tests pass (was 215); `check-all.ps1` exits 0.
- [x] **1.9** Define `MrzValueError` in `tier0/mrz.py` as the single error type
  the whole MRZ package raises, and add a test that it subclasses `ValueError`.
  Verify: the new test passes.
      — the class already existed: 1.4 introduced it when it swapped `char_value`'s raise, and 1.5/1.6/1.8 routed every other failure through it, so this task **pins** the claim rather than defining the class again. 23 new cases, the named one being `issubclass(mrz.MrzValueError, ValueError)`. 288 backend tests pass (was 265); `check-all.ps1` exits 0.

**Gate 1:** all MRZ primitive tests pass with no OpenCV import.

---

# Part 2 — TD3 passport parser

Two lines of 44 characters. Positions below are 1-indexed and must live in
named constants, not inline magic numbers.

- [x] **2.1** Create the `TD3` layout constants module (line length 44, and the
  start/end index of each field) with a test asserting the constants cover
  exactly positions 1–44 with no gap or overlap.
  Verify: the coverage test passes.
      — new `backend/app/pipeline/tier0/td3.py` (constants only: no arithmetic, no raise) and `test_td3.py`. Five names: `TD3_LINE_LENGTH` 44, `TD3_LINE_COUNT` 2, `TD3_LINE_1` (3 fields), `TD3_LINE_2` (11 fields, the four printed check digits included as fields of their own right), and the `TD3` aggregate. 313 backend tests pass (was 288); `check-all.ps1` exits 0.
- [x] **2.2** Write `validate_td3_lines(lines)` raising unless there are exactly
  2 lines of exactly 44 characters, with tests for 1 line, 3 lines, and a short
  line.
  Verify: the new tests pass.
      — `validate_td3_lines(lines)` in `td3.py`, so 2.1's module now holds the layout *and* the one gate a zone passes before any of it is read; the docstring says so. Raises `mrz.MrzValueError` and nothing else, and 1.9's package-wide scans still pass. 325 backend tests pass (was 313); `check-all.ps1` exits 0.
- [x] **2.3** Extract and validate the document code (positions 1–2): must be
  `P<` or `P`, with tests for `P<`, `P`, `V<`, and `X<`.
  Verify: the new tests pass.
      — split into two functions because the task's own four cases make the split necessary: `validate_document_code(code)` is the judgement (membership in `TD3_DOCUMENT_CODES`) and `parse_document_code(line_1)` slices positions 1–2 through `TD3_LINE_1["document_code"]` and delegates. 352 backend tests pass (was 325); `check-all.ps1` exits 0.
- [x] **2.4** Extract the issuing state (3–5) and validate it is 3 uppercase
  letters, with a test rejecting `IND`.
  Verify: the new tests pass.
      — **the task's two clauses contradict each other and this task implements the first one.** `IND` *is* three uppercase letters, so no implementation of the stated rule can reject it and the second clause is unreachable from the first; a membership rule does not rescue it either, since ISO 3166-1 alpha-3 assigns `IND` to India. 384 backend tests pass (was 352); `check-all.ps1` exits 0.
- [x] **2.5** Extract the raw name string (6–44) with a test on a known MRZ.
  Verify: the new test passes.
      — `parse_name(line_1)` in `td3.py`, and **one function rather than the reader/validator pair 2.3 and 2.4 needed**, because this field has no content rule: the standard fixes where the name sits and how wide it is, and says nothing about which characters may appear. 404 backend tests pass (was 384); `check-all.ps1` exits 0.
- [x] **2.6** Split the name on `<<` into surname and given-names, with a test
  for `ERIKSSON<<ANNA MARIA` and for a mononym with no `<<`.
  Verify: the new tests pass.
      — `split_name(name)` in `td3.py`, added to `__all__`. Takes the string `parse_name` returned rather than a line, so it is `split_*` and not `parse_*`; one function, no validator, on 2.5's reasoning. 425 backend tests pass (was 404); `check-all.ps1` exits 0. Note: on this Windows box a stray OpenCV faulthandler diagnostic makes pytest exit 1 while every test passes, so run pytest with `-p no:faulthandler`.
- [x] **2.7** Split given names on `<` into a list, dropping empty entries, with
  tests for `ANNA MARIA` and `ANNA<MARIA`.
  Verify: the new tests pass.
      — `split_given_names(given_names) -> list[str]` in `td3.py`, added to `__all__`. Takes the string `split_name` returned, so `split_*` not `parse_*`; one function, no validator, on 2.5's reasoning. 450 backend tests pass (was 425); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)
- [x] **2.8** Strip space filler and normalise to uppercase in name parsing,
  with a test using `P<UTO LIE<SOPHIE<<<<<`.
  Verify: the new test passes.
      — `normalise_names(surname, given_names) -> tuple[str, list[str]]` in `td3.py`, added to `__all__`. Takes the two halves `split_name` and `split_given_names` produced, so `normalise_*` not `parse_*`; no validator, as no content rule is left to enforce. 490 backend tests pass (was 450); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)
- [x] **2.9** Add the ICAO transliteration map (diacritics to base letters,
  `ß`→`SS`, `Ø`→`O`, `Ł`→`L`, `Đ`→`D`) and apply it to parsed names, with
  tests for `MÜLLER`→`MULLER` and `Ø`→`O`.
  Verify: the new tests pass.
      — `TRANSLITERATIONS` and `transliterate_names(surname, given_names) -> tuple[str, list[str]]` in `td3.py`, both added to `__all__`. Takes what `normalise_names` returned, so `transliterate_*`; no validator, because 2.5 already checked the field. 546 backend tests pass (was 490); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)
- [x] **2.10** Extract the passport number (line 2, 1–9) and validate it is
  non-empty, with tests for a normal number and an all-`<` number.
  Verify: the new tests pass.
      — `validate_document_number(number)` and `parse_document_number(line_2)` in `td3.py`, both added to `__all__`: the `parse_*` plus `validate_*` pair 2.3/2.4 needed and 2.5 to 2.9 did not, because the document number is the first field with a content rule of its own. The reader slices through `TD3_LINE_2`. 582 backend tests pass (was 546); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)
- [x] **2.11** Extract the nationality (11–13), validate 3 uppercase letters,
  with a test rejecting `IND`.
  Verify: the new test passes.
      — `validate_nationality(code)` and `parse_nationality(line_2)` in `td3.py`, both added to `__all__`: the 2.10 pair again, because positions 11–13 have a content rule of their own. 622 backend tests pass (was 582); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)
- [x] **2.12** Extract the date of birth (14–19), the expiry (22–27), and the
  sex marker (21) in one task, validating the sex marker against `M`, `F`, `X`,
  `<`, with tests for each accepted value and a rejection for `Z`.
  Verify: the new tests pass.
      — `validate_date_of_birth`/`parse_date_of_birth`, `validate_date_of_expiry`/`parse_date_of_expiry` and `validate_sex`/`parse_sex` in `td3.py`, plus `TD3_SEX_MARKERS`, all added to `__all__`: three fields in one task because the task says so, each the 2.10 pair. A throwaway mutation run confirms the teeth, 22 of 22 caught. 696 backend tests pass (was 622); `check-all.ps1` exits 0; `compileall` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)
- [x] **2.13** Write `parse_td3(lines) -> MrzDocument` assembling every field
  plus the raw per-field source slices, with a test on a full specimen MRZ.
  Verify: the new test passes and every field is populated.
      — **the code and all 52 of its tests were already written; this task was one failing test and the one-line change that answers it**, which is what the previous handover's Known Issues diagnosed. `MrzDocument`, `_td3_sources` and `parse_td3` were present and correct in their *values*; the failure was a *count*: the six fields with no reader of their own were sliced twice. The fix routes them out of the map `parse_td3` has already built, so a value and its source slice are now the one string read once and cannot drift apart. 772 backend tests pass; `check-all.ps1` exits 0 for the first time since 2.13 was written, unblocking the harness the previous two sessions recorded at exit 1.
- [x] **2.14** Add a negative test: a passport MRZ with a mutated character in
  the passport number still parses structurally, and the check-digit verifier
  is what reports the mismatch (parsing must not silently "fix" it).
  Verify: the new test passes.
      — **the 24 tests were already written by the session that also wrote 2.13; this task confirmed they hold and closed the marker `tasks.md` had never been flipped for.** 7 named tests plus an 18-row parametrised table at the end of `test_td3.py`, over `MUTATED_DOCUMENT_NUMBER = "L898902A<"`. **No source change.** Verified by two mutation runs: 22 of the 24 cases catch a parser that brute-forces a substitution to make the number agree with its own printed digit, and a second variant that normalises in-class substitutions too is caught by all 7 named tests. 772 backend tests pass; `check-all.ps1` exits 0; `compileall` exits 0.

**Gate 2:** a real specimen passport MRZ parses to correct name, number,
nationality, DOB, sex, and expiry.

---

# Part 3 — Check digits for TD3, then TD1 and TD2

- [x] **3.1** Build the TD3 composite input from line 2 positions 1–10, 14–20
  and 22–43, with a test asserting the assembled string is 39 characters.
  Verify: the new test passes.
      — new `TD3_COMPOSITE_FIELDS` (a tuple of the eight field *names*, not three restated spans) and `td3_composite_input(line_2)` in `td3.py`, both in `__all__`. The concatenation runs over those names and every read goes through `td3_field`, so "1–10, 14–20 and 22–43" is a *consequence* of `TD3_LINE_2` rather than a second copy of it. 780 backend tests pass (was 772); `check-all.ps1` exits 0.
- [x] **3.2** Verify the TD3 final composite check digit (position 44) against a
  specimen, with a test using a deliberately wrong final digit.
  Verify: the new test passes.
      — **this task adds no production code, and 2.2 is the reason.** A `td3_composite_verifies` was written first and 3.1's `test_this_module_computes_no_check_digit_of_its_own` failed it: that guard keeps `mrz.check_digit` and `mrz.verify_check_digit` out of `vars(td3)`, so the layout module cannot hold a digit or a verifier. 785 backend tests pass (was 780); `check-all.ps1` exits 0.
- [x] **3.3** Report a per-field check-digit result list on `MrzDocument` for
  TD3 — passport number, DOB, expiry, optional data, composite — with a test
  that a correct MRY yields all-pass and a mutated one names the failing field.
  Verify: the new test passes.
      — `MrzDocument.check_digit_results` is a `tuple` of five `mrz.CheckDigitResult` records `(field, expected, found)` plus a derived `passed` and `readable`, in printed order, populated by `parse_td3`. 812 backend tests pass (was 785); `check-all.ps1` exits 0.
- [x] **3.4** Create the TD1 layout constants (3 lines of 30) with a coverage
  test asserting positions 1–30 on each line are fully accounted for.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/td1.py` and `test_td1.py`. **A new module per format, following `td3.py` rather than `ROADMAP.md` B1.3**, which still names `mrz.py` and `test_mrz_td1.py`; the per-format split happened during Part 2, so the ROADMAP line is stale. 854 backend tests pass (was 812); `check-all.ps1` exits 0.
- [x] **3.5** Parse TD1 line 1 (document code, issuing state, document number,
  optional data) with a test on a specimen.
  Verify: the new test passes.
      — the specimen is the ICAO 9303 Part 4 sample ID card's line 1, `"I<UTOD231458907<<<<<<<<<<<<<<<"`, quoted as text and *verified* as a document: `mrz.check_digit("D23145890")` is the `7` printed at position 15, the evidence 3.4 said could not yet exist. `td1.py` gains `td1_field`, the one place a TD1 line is sliced. 941 backend tests pass (was 854); `check-all.ps1` exits 0.
- [x] **3.6** Parse TD1 line 2 (DOB, sex, expiry, nationality, optional data 2)
  with a test on the same specimen.
  Verify: the new test passes.
      — same ICAO 9303 Part 4 sample ID card, line 2, `"7408122F1204159UTO<<<<<<<<<<<6"`, with both printed digits **verified rather than trusted** the way 3.5 checked the document number: `mrz.check_digit("740812")` is the `2` at position 7 and `mrz.check_digit("120415")` is the `9` at position 13. 1037 backend tests pass (was 941); `check-all.ps1` exits 0.
- [x] **3.7** Build and verify the TD1 composite check digit over line 1
  positions 1–10 and 15–30 plus line 2 positions 1–7, 9–15 and 19–29, with a
  test on a correct specimen and one on a mutated composite.
  Verify: the new tests pass.
      — **the span in this task's own text is the standard's, and the disagreement `td1.py` carried is settled against the notes.** 3.5 wrote "line 1 6–14 and 16–29" and flagged it unchecked; 3.6 carried the flag. Implemented: line 1 1–10 and 15–30, plus line 2 1–7, 9–15 and 19–29, which is 51 characters. **The one existing value this task changed: `SPECIMEN_LINE_2` now carries `7`, not the `6` 3.6 quoted from memory.** A correct specimen yields four `True` rows and one `None`, because optional data 1 is fourteen fillers so its check-digit position prints filler rather than a digit. Spans are positions on a named line rather than field names, because line 1 1–10 stops five characters into the nine-character document number; a test asserts that one cut is the only one. Six span mutants each fail 9–13 tests. 1062 backend tests pass (was 1037); `check-all.ps1` exits 0; `compileall` exits 0.
- [x] **3.8** Create the TD2 layout constants (2 lines of 36) with a coverage
  test.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/td2.py`: `TD2_LINE_LENGTH` 36, `TD2_LINE_COUNT` 2, `TD2_LINE_1` (3 fields), `TD2_LINE_2` (11 fields) and the `TD2` aggregate over the *same dict objects*, `__all__` exactly those five names and nothing else, so no reader, no span, no arithmetic, no error type. **36 is the first line length digits and letters fill exactly**, so the synthetic line is `string.digits` + `string.ascii_uppercase` and position 36 is `Z`; every expected slice is written longhand, so a boundary one character out fails on a value. No specimen, and **no composite span, deliberately**: 3.9 and 3.10 as written describe the TD1's field distribution (between them they name no field for the holder's name), and 3.10's span is `TD1_COMPOSITE_SPANS` with the line 1 portion left in place, which on a TD2 would put the composite over the sex marker and the nationality. 1104 backend tests pass (was 1062); `check-all.ps1` exits 0.
- [x] **3.9** Parse TD2 line 1 (document code, issuing state, name) with a test
  on a specimen visa. **The field list in the task as written was a TD1's and
  is corrected here — see the note.**
  Verify: the new test passes.
      — new readers in `td2.py`: `td2_field` (the one place a TD2 line is sliced), a closed `TD2_DOCUMENT_CODES` (`{"V<", "V"}`), three `parse_*`/`validate_*` pairs (document code, issuing state, **name**, which 3.9 as written omitted) and `parse_td2_line_1`, returning all three in printed order inside a read-only mapping. 1183 backend tests pass (was 1104); `check-all.ps1` exits 0.
- [x] **3.10** Parse TD2 line 2 (document number, nationality, date of birth,
  sex, date of expiry, optional data, and all five printed check digits) and
  verify the composite over line 1 positions 6–36 plus line 2 positions
  1–10, 14–20 and 22–35. **The field list and the composite span in the task
  as written were a TD1's and are corrected here — see the note.**
  Verify: the new test passes.
      — `td2.py` gains six `parse_*`/`validate_*` pairs (document number, nationality, date of birth, sex, date of expiry, optional data), a closed `TD2_SEX_MARKERS`, `parse_td2_line_2` (eleven fields, printed order, read-only), `TD2_COMPOSITE_SPANS`, `TD2_CHECK_DIGIT_FIELDS`, `td2_composite_input` and `td2_check_digit_results`. 1327 backend tests pass (was 1183); `check-all.ps1` exits 0.
- [x] **3.11** Add the date semantics: `YYMMDD` parsing with month/day range
  validation, rejecting `993199` and `013200`, with tests.
  Verify: the new tests pass.
      — the rule is one function in `mrz.py` that all three formats delegate to: `MrzDate` (frozen; `year`, `month`, `day`, two printed year digits and **no century**), `parse_date(text) -> MrzDate | None` (six characters of `YYMMDD`; `None` if any of the six is not an ASCII digit) and `date_fault(text) -> "month" | "day" | None`. 1405 backend tests pass (was 1327); `check-all.ps1` exits 0.
- [x] **3.12** Add century inference for dates of birth (a YY implying a person
  older than ~120 years maps to the previous century) with tests at the
  boundary years.
  Verify: the new tests pass.
      — `mrz.py` gains `MAX_BIRTH_AGE = 120`, `infer_birth_year(text, reference) -> int | None` and the private `_is_a_real_day(year, month, day)`; `__all__` gains two names, thirteen in all. The answer is the **most recent year carrying the two printed digits that has already happened, was a day that year had, and is not more than 120 years ago**. 1451 backend tests pass (was 1405); `check-all.ps1` exits 0.
- [x] **3.13** Add century inference for expiry dates, which follows a different
  rule from dates of birth, with boundary tests.
  Verify: the new tests pass.
      — `mrz.py` gains `infer_expiry_year(text, reference) -> int | None` beside 3.12's `infer_birth_year`, exported in `__all__` (fourteen names in all). **The rule is the nearest year carrying the two printed digits that has not already passed**, which is 3.12's candidate pair with the sign flipped. 1503 backend tests pass (was 1451); `check-all.ps1` exits 0.
- [x] **3.14** Add `MrzDocument` as a dataclass with a `format` discriminator,
  and a `parse_mrz(lines)` dispatcher that picks TD1/TD2/TD3 from the line
  count and lengths, with a test for all three plus an unrecognised shape.
  Verify: the new tests pass.
      — `MrzDocument` (declared in `td3.py` since 3.1) is now the common currency of all three formats, carrying a `format` discriminator plus five `| None` attributes for the optional-data fields only a TD1 or TD2 prints, where `None` means "this format prints no such field" and never an empty string. **Breaking change to a published API.** 1580 backend tests pass (was 1503); `check-all.ps1` exits 0.

**Gate 3:** all three MRZ formats parse, every check digit verifies, and both
worked examples from `abstract.txt` are reproducible as tests.

---

# Part 4 — MRZ region detection (finding *where* on the document)

This is what makes "the date-of-birth field is highlighted" possible. It is
the single highest-value block after Part 1–3, because that screenshot is what
sells the product.

- [x] **4.1** Add a `deskew(image)` helper that reuses the existing skew angle
  from `m7_skew` to rotate the working image upright, with a test on a
  deliberately rotated synthetic image.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/mrz_region.py`, the file `ROADMAP.md` B1.10 names, carrying `deskew(image)`, `skew_deg(image)` and `MAX_DESKEW_DEG`. **The skew angle is measured once, by code this project already ships**: `m7_skew` gains one public function. 31 new tests. 1611 backend tests pass (was 1580); `check-all.ps1` exits 0.
- [x] **4.2** Write `to_gray(image)` and `binarize_inverted(gray)` using an
  adaptive threshold so MRZ glyphs become white on black, with tests asserting
  the output is single-channel and mostly binary.
  Verify: the new tests pass.
      — `to_gray(image)` and `binarize_inverted(gray)` in `mrz_region.py`, both public; `__all__` is five names and the source-side rule test was updated to match. 27 new tests. 1638 backend tests pass (was 1611); `check-all.ps1` exits 0.
- [x] **4.3** Extract connected components and compute per-component bbox,
  height, width and centroid, with a test on a synthetic two-line MRZ image
  asserting a plausible component count.
  Verify: the new test passes.
      — `extract_components(binary)` and the frozen record `MrzComponent` in `mrz_region.py`; `__all__` is seven names and the source-side rule test now walks the AST instead of grepping. `CONNECTIVITY = 8` is a module constant chosen by a diagonal stroke: twelve pixels read as twelve components under 4 and one under 8. **It must be passed by keyword**, because the second *positional* parameter of `connectedComponentsWithStats` is the `labels` output, so `(binary, 8)` silently gets the default. 20 new tests. 1657 backend tests pass (was 1638); `check-all.ps1` exits 0.
- [x] **4.4** Filter components to MRZ-plausible glyphs by height band and
  aspect ratio, with tests proving a large photo region and a signature blob
  are rejected.
  Verify: the new tests pass.
      — `filter_glyphs(components)` in `mrz_region.py` plus four module constants (`GLYPH_MIN_HEIGHT_PX` 8, `GLYPH_MAX_HEIGHT_PX` 24, `GLYPH_MIN_ASPECT` 0.2, `GLYPH_MAX_ASPECT` 2.5). Two bands, each rejecting one of the task's two blobs. 20 new tests. 1677 backend tests pass (was 1657); `check-all.ps1` exits 0.
- [x] **4.5** Group surviving components into lines by vertical overlap, with a
  test asserting exactly 2 groups for a 2-line synthetic MRZ.
  Verify: the new test passes.
      — `group_lines(components)` in `mrz_region.py`. **The task's test is measured against what the fixture drew, not against a bare count**, because one group holding both lines answers "2" as comfortably as two groups holding one line each. 14 new tests. 1691 backend tests pass (was 1677); `check-all.ps1` exits 0.
- [x] **4.6** Score each line group on height consistency and inter-line
  spacing consistency, and discard groups that fail, with a test where a third
  stray text line is correctly rejected.
  Verify: the new test passes.
      — `filter_lines(lines)` plus `LINE_MAX_HEIGHT_SPREAD` (1/3) and `LINE_MAX_SPACING_SPREAD` (0.25) in `mrz_region.py`; both scores are **ratios taken on the group** rather than constants, because a constant would be satisfied by one consistent group. 20 new tests. 1711 backend tests pass (was 1691); `check-all.ps1` exits 0; `compileall` exits 0. Eighteen mutants were run and all eighteen are caught; the throwaway harness under `%TEMP%` was deleted.
- [ ] [BLOCKED] **4.7** Infer the document format from line count and median glyph count
  per line (2×44, 3×30, 2×36), with a test per format.
  Verify: the new tests pass.
- [x] **4.8** Emit a polygon per detected MRZ line, with a test asserting the
  polygon encloses the drawn glyphs and has 4 points.
  Verify: the new test passes.
      — `line_polygons(lines)` in `mrz_region.py`: one four-point polygon per line group, corners read clockwise from the top left, far corner **exclusive** (the one `bbox` names), tight to the ink. 11 new tests. 1721 backend tests pass (was 1710 passed + 1 failed); `check-all.ps1` exits 0. Six mutants run, all six caught.
- [x] **4.9** Estimate residual skew *within* a line group from glyph centroids
  and rotate the group before column segmentation, with a test on a slightly
  rotated MRZ.
  Verify: the new test passes.
      — `residual_skew_deg(line)` and `deskew_line(line)` in `backend/app/pipeline/tier0/mrz_region.py`; 19 new tests, 1740 backend (was 1721), `check-all.ps1` exits 0, seven of eight mutants caught.
- [x] **4.10** Segment each line into character cells using the x-projection gap
  profile, with a test asserting the cell count matches the inferred format
  length.
  Verify: the new test passes.
      — `segment_cells(line)` in `backend/app/pipeline/tier0/mrz_region.py`: a cell is one maximal run of occupied columns, read off the union of the line's own boxes, which is measured equal to the cut's own x-projection on every capture here including ones turned to 5 degrees. 17 new tests, 1757 backend (was 1740), `check-all.ps1` exits 0, seven of seven mutants caught. **The cell count is derived, never supplied**, so comparing it against 4.7's shape is a real check; and the line segmented is the one 4.6 kept, because 4.9's turned boxes are *worse* input — measured, a page turned 5 degrees segments into 1 and 4 cells after the turn against 12 and 25 before it.
- [x] **4.11** Map a character cell index to a field offset per format, reusing
  the Part 2/3 layout constants so there is exactly one source of truth, with a
  test asserting cell 13 on TD3 line 2 maps to the passport-number check digit.
  Verify: the new test passes.
      — `cell_field(format_name, line_number, cell_index)` and `MRZ_LAYOUTS` in `backend/app/pipeline/tier0/mrz_region.py`: the layout table **is** `td1.TD1`/`td2.TD2`/`td3.TD3` (pinned by `is`), so no position is typed twice; line numbered from 1, cell indexed from 0, refusal is `None` and never a raise. 10 new tests, 1768 backend, `check-all.ps1` exits 0. **The task's two clauses contradict each other and this task implements the first:** the layout prints the passport-number check digit at position 10, so it is cell **9**, while cell 13 is position 14 — the date of birth. `test_cell_thirteen_is_the_date_of_birth_and_not_a_check_digit` pins the difference, as 2.4's `IND` test does.
- [x] **4.12** Expose `field_regions(document) -> dict[str, Polygon]` returning
  a box per extracted field, with a test asserting the DOB box covers the DOB
  characters and does not cover the expiry characters.
  Verify: the new test passes.
      — `field_regions(document, lines)` in `backend/app/pipeline/tier0/mrz_region.py`, keyed by the
  layout's own field names. **The task's signature names one argument and it cannot be one:** a parsed
  `MrzDocument` holds no pixels and a line group holds no field names, so both arrive; the format comes
  from `document.format`, which is why 4.7 is not needed. A field is the union of the boxes of the cells
  4.11 named it — no position is typed — and the polygon is 4.8's own four points from one `_box_polygon`
  both steps call, so a field box is inside its line's polygon by construction. **A field no cell names is
  absent, not `None`**: a short line (4.10's lower bound) simply has no tail fields. 11 new tests,
  1779 backend (was 1768), `check-all.ps1` exits 0, six of six mutants caught.
- [x] **4.13** Make the detector return an empty result (not an exception) when
  no MRZ is present, with a test on a blank image.
  Verify: the new test passes.
      — `detect_mrz(image)` and the frozen `MrzDetection` in `backend/app/pipeline/tier0/mrz_region.py`: one record carrying 4.7's format name, 4.6's line groups and 4.8's polygons, so a page with no MRZ answers `MrzDetection()` and never raises. 15 new tests; `check-all.ps1` exits 0 (1794 backend, was 1779), seven of seven mutants caught.
- [x] **4.14** Build a reusable synthetic MRZ image generator (fixture) that can
  render TD1/TD2/TD3 MRZs at a given size, angle, and noise level; use it for
  every test in this part.
  Verify: the fixture renders and its own round-trip test passes.
      — new `backend/tests/fixtures/mrz_images.py` (`draw_page`, `render_format`, `read_zone`, `MrzPage`, `SPECIMENS`) and `test_mrz_images.py`, 102 new tests; 1896 backend (was 1794), `check-all.ps1` exits 0. **One character per fixed cell, stamped from a 5x7 pattern table**: OpenCV's Hershey is proportional, and 4.13 measured 24 and 27 blobs on two 44-character lines, so no test on it could reach a named format. The round trip is closed rather than reopened — text → page → text → `MrzDocument` equals parsing the text, all three formats — and `field_regions` now has a known box per field to be compared against. Gap and cell size are measured, not chosen: a 1-pixel gap merges 44 glyphs into 23–26 on a page turned 4°, 2 loses one on an anticlockwise TD3, 3 is the first exact on all three; a cell not a whole multiple of 5 and 7 loses columns (8×12 reads `8` as `O`). `ZONES` in `test_mrz_region.py` now reads `SPECIMENS`, so the repository holds one specimen per format. **The second clause's migration is partial and the remainder is not a drop-in** — `upright_mrz`, `rotated_mrz`, `shadowed_mrz`, `dim_mrz`, `grainy_mrz`, `tilted_pair_mrz` and `zone_of` stand, because 4.10–4.12's negative controls need a zone of the *wrong* length and a generator that validates its shape will not draw one; each also re-measures its own claim, listed in the handover rather than done blind. Rationale as D4 in `docs/DECISIONS.md`.

**Gate 4:** for a synthetic passport image, every MRZ field has a pixel region,
and an image with no MRZ returns empty rather than raising.

---

# Part 5 — Evidence flags, date rules, watchlist

- [x] **5.1** Create `backend/app/risk/__init__.py` and an `EvidenceFlag` model
  with fields `id`, `tier`, `label`, `weight_band`, `value`, `confidence`,
  `region`, `expected`, `found`, `reason`, `source_module`.
  Verify: a test constructs one and reads every field back.
      — verified: `backend/app/risk/flags.py` (frozen dataclass) + `backend/tests/unit/test_flags.py`; 4 tests pass, 1900 backend (was 1896), `check-all.ps1` exits 0.
- [x] **5.2** Add model validation: `value` and `confidence` must be within
  [0,1], `weight_band` within the allowed set, and `region` must be a
  well-formed polygon or null — with a test per rejected case.
  Verify: the new tests pass.
      — verified: `app/risk/flags.py` gains `WEIGHT_BANDS`, `MIN_REGION_CORNERS`, `FlagValueError` and `__post_init__`; 79 new cases in `backend/tests/unit/test_flag_validation.py`, 1979 backend (was 1900), `check-all.ps1` exits 0. Decision recorded as `D6`.
- [x] **5.3** Create `backend/app/risk/flag_ids.py` with a constant for every
  flag id used anywhere in the system (`MRZ_*`, `DATE_*`, `WATCHLIST_*`,
  `OCR_*`, `LAYOUT_*`, `FACE_*`, `TAMPER_*`, `CROSSDOC_*`) and a test that the
  module exposes no duplicates.
  Verify: the new test passes.
      — verified: `backend/app/risk/flag_ids.py` (31 ids in eight families, each constant named after its id) + `backend/tests/unit/test_flag_ids.py`; 50 new cases, 2029 backend (was 1979), `check-all.ps1` exits 0. Decision recorded as `D7`.
- [x] **5.4** Implement the expiry rule — document expired relative to an
  injected reference date — with tests for expired, expiring today, and valid.
  Verify: the new tests pass.
      — verified: `backend/app/pipeline/tier0/dates.py` (`expiry_result` + `ExpiryResult`, four statuses, no flag) and `backend/tests/unit/test_dates.py`; 56 new cases, 2085 backend (was 2029), `check-all.ps1` exits 0. Decision recorded as `D8`.
- [x] **5.5** Implement the not-yet-valid rule (expiry in a past, issue date in
  the future) with tests.
  Verify: the new tests pass.
      — verified: `backend/app/pipeline/tier0/dates.py` gains `issue_result` + `IssueResult` (three statuses, no flag) and `backend/tests/unit/test_dates_issue.py`; 53 new cases, 2138 backend (was 2085), `check-all.ps1` exits 0. Decision recorded as `D9`.
- [x] **5.6** Implement the implausible-date-of-birth rule (DOB in the future,
  or implying an age over a configurable maximum) with tests at the boundary.
  Verify: the new tests pass.
      — verified: `backend/app/pipeline/tier0/dates.py` gains `dob_result` + `BirthResult` (three
statuses, no flag) and `backend/tests/unit/test_dates_dob.py`; 83 new cases, 2221 backend (was 2138),
`check-all.ps1` exits 0. Decision recorded as `D10`.
- [x] **5.7** Implement the issue-after-expiry consistency rule with a test.
  Verify: the new test passes.
      — verified: `backend/app/pipeline/tier0/dates.py` gains `consistency_result` + `ConsistencyResult` (three statuses, no flag) and `backend/tests/unit/test_dates_consistency.py`; 54 new cases, 2275 backend (was 2221), `check-all.ps1` exits 0. Decision recorded as `D11`.
- [x] **5.8** Add a `ReferenceDate` dependency so every date rule takes the
  current date as a parameter, with a test asserting no module in
  `tier0/dates.py` calls `datetime.now()`.
  Verify: the new test passes.
      — verified: `ReferenceDate = datetime.date` in `tier0/dates.py`, declared on the three rules that read a date and on all four records; `backend/tests/unit/test_reference_date.py`, 33 new cases, 2308 backend (was 2275), `check-all.ps1` exits 0. Decision recorded as `D12`.
- [x] **5.9** Create the `Watchlist` interface with
  `lookup(document_number, name, dob) -> list[WatchlistHit]`.
  Verify: a test asserts a stub implementation satisfies the interface.
      — verified: `app/risk/watchlist.py` (`WatchlistHit`, `Watchlist` ABC, three kinds); `backend/tests/unit/test_watchlist.py`, 59 new cases, 2367 backend (was 2308), `check-all.ps1` exits 0. Decision recorded as `D13`.
- [x] **5.10** Create `backend/app/seed/watchlist.json` with synthetic entries:
  stolen document numbers, a blacklist entry, and an identity already seen.
  Use obviously fake values.
  Verify: the file parses as JSON and has at least 3 entries.
      — verified: `backend/app/seed/watchlist.json` (4 synthetic entries: 2 `stolen_document`, 1 `blacklist`, 1 `identity_seen`) and `backend/app/seed/__init__.py`; every row builds a `WatchlistHit`, `check-all.ps1` exits 0 (2367 backend, 45 frontend).
- [x] **5.11** Implement `MockWatchlist` backed by that JSON, with tests: a
  number in the seed hits, an unknown number misses, and a name+DOB match hits.
  Verify: the new tests pass.
      — verified: `backend/app/seed/mock_watchlist.py` and `backend/tests/unit/test_mock_watchlist.py`, 18 new cases, 2385 backend (was 2367), `check-all.ps1` exits 0.
- [x] **5.12** Make `MockWatchlist` load the JSON once at construction, not per
  lookup, with a test counting file reads.
  Verify: the new test passes.
      — verified: the seed is read in `MockWatchlist.__init__` and never again,
      2 new read-counting cases, 2387 backend (was 2385), `check-all.ps1` exits 0.

**Gate 5:** a document with a broken DOB check digit and one with a blacklisted
number each produce the correct flag with the correct field region.

---

# Part 6 — Tier 0 runner

- [x] **6.1** Create `backend/app/pipeline/tier0/runner.py` with
  `run_tier0(image, document_type=None, reference_date=None) -> TierResult`.
  Define `TierResult` as flags, hard-failed bool, hard-fail reason, detected
  format, and detected regions.
  Verify: a test calls it on a synthetic MRZ image and gets a `TierResult`.
      — new `runner.py` (frozen `TierResult`, `run_tier0`) and `test_tier0_runner.py`,
        40 tests; 2427 backend tests (was 2387), `check-all.ps1` exits 0.
- [x] **6.2** Convert MRZ check-digit results into flags, one per failing field,
  each carrying that field's region from Part 4.
  Verify: a test with a mutated composite names the failing field and the
  region is non-null.
      — new `test_tier0_check_digits.py` (46 tests across both files): `runner.py`
      gained `_check_digit_flags` and a `parsed_document=` argument, and
      `EvidenceFlag` grew a required `field` (`D17`). 2473 backend tests (was
      2427); `check-all.ps1` exits 0.
- [x] **6.3** Convert date-rule results into flags, reusing the reference-date
  injection from 5.8.
  Verify: a test with an expired document produces `DATE_EXPIRED`.
- [x] **6.4** Convert watchlist hits into flags, treating a blacklist hit as a
  hard fail and a stolen-document hit as a heavy-weighted non-hard flag.
  Verify: tests for both severities.
      — verified: 39 new tests in `test_tier0_watchlist.py`, both severities driven off 5.11's seed; 2512 backend tests (was 2473), check-all.ps1 exits 0.
- [x] **6.5** Determine `hard_failed` — true when any hard-fail rule fired —
  and expose the reason as a human-readable string.
  Verify: a test asserting a checksum failure hard-fails and a soft flag does
  not.
      — verified: 25 new tests in `test_tier0_hard_fail.py`; a broken check digit and a stolen/identity hit in one result, showing the band is not the test; 2537 backend tests (was 2512), check-all.ps1 exits 0.
- [x] **6.6** Instrument per-stage timing on `TierResult` so a later task can
  show "Tier 0 took 0.11 s" against the abstract's sub-0.3 s target.
  Verify: a test asserts the timing keys exist and are non-negative.
    — verified: 24 new tests in `test_tier0_timing.py`; the four keys exist
    and are non-negative on every page; 2561 backend tests (was 2537).
- [x] **6.7** Reproduce worked example A from `abstract.txt` as a test: DOB
  check digit expected 4, found 7, exits as a hard fail with the DOB field
  highlighted.
  Verify: the new test passes and asserts the flag id, expected, found, and a
  non-null region.
    — verified: new `test_tier0_worked_example_a.py` (8 tests) on a drawn TD3 whose DOB comes to 4 and prints 7; 2569 backend tests, check-all.ps1 exits 0. The flag's `expected` is the printed digit, the reverse of the abstract's sentence — see HANDOVER.

**Gate 6:** `abstract.txt` worked example A is a passing test.

---

# Part 7 — Weights, risk engine, bands, history

- [x] **7.1** Write `backend/app/risk/weightsets/v1.yaml` with a weight and
  weight band for every id in `flag_ids.py`, and a test that fails if any id is
  missing.
  Verify: the completeness test passes.
      — new `backend/app/risk/weightsets/v1.yaml` (31 rows in `ALL_FLAG_IDS` order, `ruleset_version`, weights 15/30-40/55-65 in the three bands) and `test_weightset_v1.py`, 42 cases: the completeness set comparison, the reverse one, the two top-level keys, entry shape, real positive weights, every band legal and all three used, `D18`'s disjoint band ranges, no weight above 69, cascade order, the three watchlist bands read out of the runner's own table, and `ruleset_version == app.version.RULESET_VERSION`. `D21` records why a weight is points rather than a share and why nothing reaches High alone. Proven to fail: deleting one row fails 3 tests and names the id. 2611 backend tests (was 2569); `check-all.ps1` exits 0.
- [x] **7.2** Write the weightset loader exposing `ruleset_version` from the
  file, with a test that the version string is returned.
  Verify: the new test passes.
      — `weightsets` is now a package: `loader.py` returns a frozen `Weightset`
      read through `importlib.resources`, refuses rather than defaulting, and
      never caches; `test_weightset_loader.py`, 16 cases. `pyyaml` moved to
      `requirements.txt`. `D22` records the read. 2627 backend tests (was 2611);
      `check-all.ps1` exits 0.
- [x] **7.3** Make weight lookup raise on an unknown flag id, with a test — the
  system must never silently score a flag as zero.
  Verify: the new test passes.
      — verified: new `backend/app/risk/weightsets/lookup.py` (`weight_for`) raises `WeightsetError` and never zeroes; 45 cases in `test_weight_lookup.py` pass, 2672 backend tests (was 2627), `check-all.ps1` exits 0.
- [x] **7.4** Write `normalise_value(flag)` mapping a flag's value into the
  engine's 0–1 range, with tests for a normal flag, a `None` value, and a
  boolean-style flag.
  Verify: the new tests pass.
      — verified: new `backend/app/risk/values.py` (`normalise_value`) and `test_normalise_value.py`, 35 cases: the identity over the closed interval, the three named cases, and the refusals. `D24` records the reconciliation. 14 refusals proven to fail against a lenient `None -> 0.0`, boolean-as-`0`/`1`, clipped body. 2707 backend tests (was 2672); `check-all.ps1` exits 0.
- [x] **7.5** Write the weighted sum `R = Σ(wᵢ · Fᵢ)` with a test on a
  hand-computed three-flag example.
  Verify: the new test passes.
      — new `backend/app/risk/scoring.py` (`weighted_sum`) and `test_weighted_sum.py`, 26 cases: the hand-computed `30 + 10 + 11.25` over three ids at 60/40/15 with values read off the file, each term checkable alone, no normalisation, no clamp (195 over three `high` flags), an empty sequence as `0.0`, and the refusals propagated. `D25` records it. 10 refusal tests proven to fail against a lenient sum; a renormalising mutant fails 13 and a clamping one 6. 2733 backend tests (was 2707); `check-all.ps1` exits 0.
- [x] **7.6** Add hard-rule handling: any hard fail raises `R` to a configurable
  floor (default 90) regardless of the sum, with a test proving a hard fail
  cannot be outvoted by many soft flags.
  Verify: the new test passes.
- [x] **7.7** Clamp the final score to [0,100], with tests at both extremes.
  Verify: the new tests pass.
      — new `backend/app/risk/clamp.py` (`clamp_score`) and `test_score_clamp.py`, 72 cases: both extremes reached the whole way (195 → 100 off three `high` weights read off the file; a clean document and every negative score → 0), identity inside the scale, the floor surviving the clamp at 90, and the two composing in either order. `D27` records it. 10 wrong clamps proven to fail, each naming its own fault. 2889 backend tests (was 2817); `check-all.ps1` exits 0.
- [x] **7.8** Add band thresholds to config (`LOW_MAX`, `REVIEW_MAX`) with
  defaults 34 and 69, and a test asserting the defaults.
  Verify: the new test passes.
      — verified: new `app/risk/config.py` (two floats, no env var, `D28`) and `test_band_thresholds.py`, 10 cases; the three placeholder `REVIEW_MAX = 69` copies now import it. 2899 backend tests, check-all.ps1 exits 0.
- [x] **7.9** Write `to_band(score) -> "low" | "review" | "high"` and test the
  boundary values 0, 34, 35, 69, 70, 100 explicitly.
  Verify: the new tests pass.
      — verified: new `app/risk/bands.py` (`to_band`) and `test_to_band.py`, 42 cases; the six boundaries, the two
      switches at a 1e-9 either side, the 30-point row that proves a row's band and a score's band are two
      questions. 10 wrong bands proven to fail. `D29` records it. 2941 backend tests, check-all.ps1 exits 0.
- [x] **7.10** Add a test asserting there is no code path mapping the `review`
  band to an automatic reject — the band exists to protect genuine travellers.
  Verify: the new test passes.
      — new `test_review_never_rejects.py`, 17 cases: a statement-level AST walk over all of `app/` and its data files finds no `review` beside a rejection, and no rejection word anywhere in the engine; a mapping planted in a probe module fails both. 2958 backend tests (was 2941); `check-all.ps1` exits 0.
- [x] **7.11** Return a per-flag contribution breakdown (`id`, `weight`,
  `value`, `contribution`) alongside the total, with a test that the
  contributions sum to the pre-history score.
  Verify: the new test passes.
      — `scoring.py` gains frozen `Contribution`/`ScoreBreakdown` and `weighted_sum` is now `weighted_breakdown(...).total`, so the total *is* the sum of the shown rows. 29 cases; three mutants proven to fail and the source hash-restored. 2987 backend tests (was 2958); `check-all.ps1` exits 0. `D31` records it.
- [x] **7.12** Write `decay(age_days, half_life_days) -> float` for the history
  layer, with tests at 0 days, exactly one half-life, and two half-lives.
  Verify: the new tests pass.
      — new `test_history_decay.py`, 52 cases, plus `decay` and `HISTORY_HALF_LIFE_DAYS` in `history.py`. Verified: the new file passes, 3039 backend tests (was 2987), `check-all.ps1` exits 0. The three points are asserted with `==` and are exact; four planted wrong implementations each proven to fail. `D32` records it.
- [x] **7.13** Write `history_signal(prior_outcomes, reference_date, config)`
  that sums only **verified** outcomes, applies decay, and clamps to a
  configurable maximum magnitude, with tests proving an unverified outcome
  contributes nothing and one old verified pass cannot move the band.
  Verify: the new tests pass.
    — new `test_history_signal.py`, 99 cases, plus `history_signal`, `PriorOutcome`, `HistoryConfig` and `HISTORY_MAX_MAGNITUDE` in `history.py`. Verified: the new file passes, 3138 backend tests (was 3039), `check-all.ps1` exits 0. Eight planted wrong implementations each proven to fail. `D33` records it.
- [x] **7.14** Combine the history signal into the final score as a bounded
  additive term, with a test asserting the adjustment never exceeds the bound.
  Verify: the new test passes.
    — new `test_history_applied.py`, 134 cases, plus `apply_history(score, prior_outcomes, reference_date, config)` in `history.py`: the bounded term is added under 7.6's floor and 7.7's clamp and the bound stays 7.13's. Verified: the new file passes, 3272 backend tests (was 3138), `check-all.ps1` exits 0. Five planted wrong implementations each proven to fail. `D34` records it.
- [x] **7.15** Write `compute_risk(flags, weights, history=None) -> RiskResult`
  returning score, band, contributions, and ruleset version. Reproduce worked
  example B from `abstract.txt`: face similarity 0.41 against a 0.55 threshold
  routes to Tier 2 and yields a high band.
  Verify: the new test passes.
      — new `backend/app/risk/engine.py` (`compute_risk`, `RiskResult`, `ScreeningHistory`) and `test_compute_risk.py`, 61 cases: worked example B end to end, the order held by a walk over the source, seven wrong implementations proven to fail. 3333 backend tests (was 3272); `check-all.ps1` exits 0. `D35` records it.

**Gate 7:** both worked examples from the abstract are passing tests, and the
`review` band cannot auto-reject.

---

# Part 8 — Persistence

- [x] **8.1** Add `sqlalchemy` and `alembic` to `requirements.txt`, install, and
  confirm the existing suite is still green.
  Verify: `python -m pytest backend/tests -q` still reports 3333 passed (the
  `13` this line quoted was stale, from Part 0).
      — `backend/requirements.txt` gains `sqlalchemy>=2.0,<3` and
      `alembic>=1.13,<2`, and the duplicate pins are gone from
      `requirements-dev.txt` (it already pulls them in through
      `-r requirements.txt`). Installed 2.1.1 and 1.20.0. Baseline measured
      before the change was 3333 and is 3333 after;
      `check-all.ps1` exits 0.
- [x] **8.2** Create `backend/app/storage/db.py` with an engine and session
  factory defaulting to a local SQLite file, overridable by `DATABASE_URL`,
  with a test asserting the default is SQLite.
  Verify: the new test passes.
      — verified: new `app/storage/db.py` (`build_engine`, `build_session_factory`, module-level `engine`/`SessionLocal`) plus `get_database_url()` in `app/config.py`; 18 new tests pass, suite 3351 (was 3333), `check-all.ps1` exits 0; three planted mistakes each caught. `D36` records the decisions.
- [x] **8.3** Make the config accept a Postgres URL without connecting, with a
  test asserting a `postgresql://` URL is accepted and a malformed one is
  rejected.
  Verify: the new test passes.
      — verified: `SUPPORTED_DATABASE_SCHEMES` + `_validated_database_url` in `app/config.py`, new `test_database_url.py` (32 tests, incl. a `socket.socket` poison and an import walk holding that the config cannot build an engine); suite 3383 (was 3351), `check-all.ps1` exits 0; four planted mistakes each caught. `D37` records the decisions.
- [x] **8.4** Create the declarative `Base` and the `Screening` model
  (id, created_at, document_type, status, score, band, mode, filename, image
  dimensions, ruleset_version, model_versions, quality JSON, flags JSON,
  summary, deleted_at).
  Verify: a test creates and reads back a row in an in-memory DB.
      — verified: new `app/storage/models.py` (`Base` + `Screening`, 16 columns, three ORM defaults) and a `StaticPool` for in-memory URLs in `app/storage/db.py`; new `test_screening_model.py` (28 tests), suite 3411 (was 3383); eight planted mistakes each caught. `D38` records the decisions.
- [x] **8.5** Create the `AuditEvent` model (id, screening_id, batch_id,
  event_type, actor, payload JSON, record_hash, created_at).
  Verify: a test round-trips a row.
      — verified: `AuditEvent` over `audit_events` in `app/storage/models.py`
      (8 columns, no foreign key on `screening_id`, `batch_id` the one
      nullable, `payload` as `JSON(none_as_null=True)`), new
      `test_audit_event_model.py` (30 tests) round-tripping a row from a
      second session; suite 3441 (was 3411), `check-all.ps1` exits 0;
      fifteen planted mistakes each caught. `D39` records the decisions.
- [x] **8.6** Create the `LedgerEntry` model (sequence, batch_id, merkle_root,
  signature, anchored_at) and make it append-only at the ORM level.
  Verify: a test asserting an update raises.
- [x] **8.7** Add an index on `created_at` and one on `band`, with a test that
  the indexes exist in the created schema.
  Verify: the new test passes.
      — verified: `ix_screenings_created_at` and `ix_screenings_band` on
      `screenings`, named by `NAMING_CONVENTION` and non-unique; 12 new
      tests in `test_schema_indexes.py` pass, suite 3453 (was 3441); three
      planted mistakes each caught. `D40` records the decisions.
- [x] **8.8** Initialise Alembic with the SQLite URL as the default and add the
  first migration matching the models.
  Verify: `alembic upgrade head` on a fresh file succeeds.
      — verified: `backend/alembic.ini` (no `sqlalchemy.url`; `script_location` and `prepend_sys_path` both `%(here)s`), `backend/alembic/env.py` asking `app.config.get_database_url()` and building its engine through `app.storage.db.build_engine`, and the autogenerated `alembic/versions/acf710336f5f_initial_schema.py`; 16 new tests in `test_alembic_migration.py`, suite 3469 (was 3453); `alembic upgrade head` on a fresh file exits 0 both from `backend/` and from the repo root. `D41` records the decisions.
- [x] **8.9** Add a test that runs `upgrade head` then `downgrade base` then
  `upgrade head` again on a temp database.
  Verify: the new test passes.
      — verified: 5 new tests in `test_alembic_migration.py` run the round trip
      on 8.8's `tmp_path` file — the rebuilt schema is compared to the first
      upgrade's column-and-index shape, `base` is held as "only
      `alembic_version`, no revision row", the two 8.7 index names come back,
      autogenerate finds no diff against the rebuilt schema, and a row written
      before the downgrade is gone after it while the rebuilt table takes a
      row again. Suite 3474 (was 3469); `check-all.ps1` exits 0. A planted
      `downgrade` that dropped one of the three tables failed all 5.
- [x] **8.10** Write `ScreeningRepository.create(...)` and a test asserting the
  returned object has an id and a creation timestamp.
  Verify: the new test passes.
      — verified: `backend/app/storage/repository.py` with
  `ScreeningRepository(sessions)` taking its factory as an argument, and
  `create(document_type=..., filename=..., image_width=..., image_height=...)`
  writing the four upload columns only; 7 new tests in
  `test_screening_repository.py` against a `tmp_path` file migrated by
  `alembic upgrade head` rather than `create_all`; suite 3481 (was 3474);
  `check-all.ps1` exits 0. `D42` records the decisions.
 - [x] **8.11** Write `get(id)` and a test that a missing id returns `None`
  rather than raising.
  Verify: the new test passes.
      — verified: `ScreeningRepository.get(screening_id)` answering the row or
      `None` (`D43`), 6 new tests in `test_screening_repository.py` reusing
      8.10's migrated-file fixture; 3487 backend tests pass and
      `check-all.ps1` exits 0.
- [x] **8.12** Write `list(offset, limit)` with a test asserting pagination
  bounds and total count.
  Verify: the new test passes.
      — verified: `ScreeningRepository.list(offset, limit)` returning a
      `ScreeningPage` of rows, table-wide `total` and the bounds taken
      (`D44`), 12 new tests in `test_screening_repository.py`; 3499 backend
      tests pass (was 3487) and `check-all.ps1` exits 0.
- [x] **8.13** Write `list_by_band(band, offset, limit)` with a test that a
  filtered list never returns a row from another band.
  Verify: the new test passes.
      — verified: `list_by_band(band, offset, limit)` returning a
      `ScreeningPage` whose `total` counts the matched rows (`D45`), one
      shared `_page` statement with `list`, 10 new tests; 3510 backend
      tests pass and `check-all.ps1` exits 0.
- [x] **8.14** Write `list_by_date_range(start, end)` and
  `list_by_document_type(doc_type)` with a test each.
  Verify: the new tests pass.
      — verified: both reads answering a tuple of rows rather than a page
      (`D46`), an inclusive range whose open ends and UTC bounds are refused
      or converted, 22 new tests; 3532 backend tests pass and
      `check-all.ps1` exits 0.
- [x] **8.15** Write `soft_delete(id)` setting `deleted_at` and excluding
  soft-deleted rows from every read, with a test.
  Verify: the new test passes.
      — verified: `soft_delete(screening_id, *, deleted_at)` stamping one row
      once and one `_not_soft_deleted()` rule behind all five reads (`D47`),
      17 new tests; 3549 backend tests pass and `check-all.ps1` exits 0.

**Gate 8:** migrations round-trip, and the repository supports create, read,
filter, paginate, and soft delete against a temp database.

---

# Part 9 — Hashing, Merkle trees, ledger, signing, anchoring

- [x] **9.1** Write `canonical_json(obj)` producing deterministic JSON: sorted
  keys, no whitespace, explicit nulls, no floats, dates as ISO strings — with a
  test proving key order in the input does not change the output.
  — verified: 14 new tests pass, check-all.ps1 exits 0 (3563 backend, 45 frontend, build).
  Verify: the new test passes.
- [x] **9.2** Add canonical-JSON tests for unicode, nested objects, and a
  rejection of floats.
  — verified: 12 new tests (26 in the file), check-all.ps1 exits 0 (3575 backend, 45 frontend, build).
  Verify: the new tests pass.
- [x] **9.3** Write `hash_record(obj, salt)` = SHA-256 over
  `salt || canonical_json(obj)`, with a test that one changed field changes the
  hash and that the same record always hashes identically.
  — verified: 18 new tests pass (3593 backend, was 3575), check-all.ps1 exits 0 (45 frontend, build).
  Verify: the new test passes.
- [x] **9.4** Generate a per-record random salt and store it alongside the
  record, with a test asserting two identical records get different salts and
  different hashes.
  Verify: the new test passes.
      — new `backend/app/ledger/salts.py`: `generate_salt()` (16 bytes from
      `secrets.token_bytes`), `seal_record(record)` and the frozen
      `SaltedRecord(record, salt, .digest, .salt_hex)`; 13 tests in
      `test_salts.py`, headed by the task's own claim. `check-all.ps1` exits 0
      (3606 backend, was 3593; 45 frontend, build).
- [x] **9.5** Write RFC 6962-style domain-separated leaf and node hashing
  (`0x00` prefix for leaves, `0x01` for internal nodes), with known-answer
  tests.
  Verify: the new tests pass.
      — verified: 25 new tests pass (3631 backend, was 3606), check-all.ps1 exits 0 (45 frontend, build).
- [x] **9.6** Write `build_tree(leaves) -> MerkleTree` splitting at the largest
  power of two, with a test asserting the root for 3 known leaves.
  Verify: the new test passes.
      — verified: 14 new tests pass (3645 backend, was 3631), check-all.ps1 exits 0 (45 frontend, build).
- [x] **9.7** Handle the odd-count case (a lone node promoted unchanged) with a
  test on 3 and 5 leaves.
      — verified: 6 new tests pass (3651 backend, was 3645), check-all.ps1 exits 0 (45 frontend, build).
  Verify: the new tests pass.
- [x] **9.8** Handle the degenerate cases: a single leaf becomes the root, an
  empty list raises, with tests.
  Verify: the new tests pass.
      — verified: 16 new tests pass (3667 backend, was 3651), check-all.ps1 exits 0 (45 frontend, build).
- [x] **9.9** Write `proof_for(index)` returning the sibling path, and
  `verify_proof(leaf, proof, root)` returning a bool.
  Verify: a test round-trips a proof.
      — verified: 45 new tests pass (3716 backend, was 3667), check-all.ps1 exits 0 (45 frontend, build).
- [x] **9.10** Add a test that a proof verifies for *every* leaf index of a
  16-leaf tree, and that mutating any leaf fails verification.
  Verify: the new test passes.
      — verified: 3 new tests + one 16-leaf known-answer row, `test_merkle.py` 114 passed (was 110), full backend 3720 passed; two mutants planted and caught.
- [x] **9.11** Create the `Ledger` interface (`append_batch`, `read_batch`,
  `iter_batches`) and a `SqliteLedger` implementation.
  Verify: a test round-trips a batch.
      — verified: 20 new tests pass (3740 backend, was 3720), check-all.ps1 exits 0 (45 frontend, build).
- [x] **9.12** Enforce append-only with SQLite triggers that reject `UPDATE` and
  `DELETE` on `ledger_entries`, with a test proving both raise.
  Verify: the new test passes.
  — verified: 13 new tests (3753 backend, was 3740), check-all.ps1 exits 0.
- [x] **9.13** Load an Ed25519 key from an env var (generate one for dev if
  absent) and expose `sign(bytes)` and the public key, with a round-trip test.
  Verify: the new test passes.
      — verified: 41 new tests (3794 backend, was 3753), check-all.ps1 exits 0; two mutants planted and caught.
- [x] **9.14** Add a test that a signature over a tampered root fails
  verification.
  Verify: the new test passes.
      — verified: 16 new tests (57 in the file, was 41), 3810 backend (was 3794), check-all.ps1 exits 0; two mutants planted and caught.
- [x] **9.15** Write `group_into_batches(unanchored_events, size)` with a test
  asserting 100 events at batch size 25 gives 4 batches in stable order.
  Verify: the new test passes.
      — verified: new `backend/app/ledger/batching.py`, one pure
  `group_into_batches` partitioning in the caller's order by identity
  (`D61`), 23 new tests; 3833 backend (was 3810), check-all.ps1 exits 0.
- [x] **9.16** Write `anchor_batch(events)` — build the tree, append one ledger
  entry per batch, and stamp each event with its batch id.
  Verify: a test asserting 1 ledger row for 25 events and that every event
  carries the batch id.
    — verified: `app/ledger/anchoring.py` (D62), 27 new tests, 3860 backend
    (was 3833), check-all.ps1 exits 0; 9.14's tamper sweep made real (D63).
- [x] **9.17** Write `verify_event(event)` — reload the event from the database,
  recompute its hash, walk its proof, compare to the anchored root, and return
  `verified` / `altered` / `unknown`.
  Verify: a test that mutates a stored payload flips the result to `altered`.
    — verified: `app/ledger/verification.py` (D64), 30 new tests plus 13 in
    `test_merkle.py` for the shared `read_digest`; 11 mutants planted and
    caught, one survivor pinned by a recording `Ledger`.
- [x] **9.18** Add a test that a verified event produces the same hash on two
  separate calls (reproducibility).
  Verify: the new test passes.
    — verified: 3 tests in `test_ledger_verification.py` (33 in the file, was
    30), 3906 backend (was 3903); one mutant planted and caught.

**Gate 9:** an event can be independently verified against an anchored root, and
a tampered record is detected. No identity data is in the ledger.

---

# Part 10 — Audit events

- [x] **10.1** Create `backend/app/audit/__init__.py` and a constants module for
  event types (`screening_created`, `analysis_completed`, `tier_completed`,
  `decision_recorded`, `override_recorded`, `screening_deleted`), with a test
  asserting no duplicates.
  Verify: the new test passes.
      — verified: `app/audit/event_types.py` holds six `str` constants and the tuple `EVENT_TYPES` (D65); 12 tests pass, 3918 backend total, `check-all.ps1` exits 0.
- [x] **10.2** Write `emit(event_type, screening_id, payload)` that hashes,
  persists, and returns the event. This is the only function allowed to create
  audit events.
  Verify: a test emits one and reads it back.
    — verified: `app/audit/emit.py` + `record.py`, `record_salt`/`batch_index`
    columns and migration `b7d41c9e2f08`, `verify_event` widened (D66); 29 new
    tests, 3949 backend (was 3918), check-all.ps1 exits 0.
- [x] **10.3** Attach `ruleset_version` and `model_versions` to every event
  payload, with a test asserting both are present on a generic emit.
  Verify: the new test passes.
      — verified: `emit` attaches both keys on every payload, defaulting to `None` and never a constant (D67); 15 new tests, 3964 backend (was 3949).
- [x] **10.4** Emit `screening_created` and `analysis_completed` from the
  screening flow, with tests asserting both exist after one screening.
  Verify: the new tests pass.
      — verified: `app/screening.py` writes the row, emits `screening_created`, runs Tier 0 through the risk engine and emits `analysis_completed` with the row's own versions (D68); 12 new tests, 3976 backend (was 3964).
- [x] **10.5** Emit one `tier_completed` event per tier that actually ran, with
  a test asserting a hard-failed screening emits only Tier 0.
  Verify: the new test passes.
      — verified: `CASCADE` is the runner table's own keys and a hard fail breaks the loop, so a hard-failed screening emits `tier_completed` for Tier 0 alone (D69); 11 new tests, 3987 backend (was 3976).
- [x] **10.6** Emit a distinct `override_recorded` event when the officer
  contradicts the band, carrying both the system band and the officer's action.
  Verify: a test asserts the override is its own event, not a mutation of the
  automated result.
      — verified: `app/audit/decision.py` (`OFFICER_ACTIONS`, `BAND_ORDER`, `contradicts_band`, `record_override`) emits through `emit` and returns `None` when the choice agrees with the band (D70); 36 new cases, 4023 backend (was 3987), `check-all.ps1` exits 0.
- [x] **10.7** Add the `actor` field sourced from a configurable station
  identifier (env var, defaulting to a placeholder) — **not** from a login, and
  with a test asserting no credential or session token appears in the field.
  Verify: the new test passes.

**Gate 10:** the officer's human decision is in the trail next to the automated
result, and every event is independently verifiable.

---

# Part 11 — Tier 0 over HTTP, plus security

- [x] **11.1** Create `backend/app/api/__init__.py` and
  `routes_screenings.py` with `POST /api/screenings` accepting the same
  multipart shape as `/api/analyze`, returning `screening_id` and `audit_id`.
  Verify: a new API test asserts both ids are present.
      — verified: `app/api/routes_screenings.py` answers both ids, `audit_id` read from the trail as the one `analysis_completed` event (D71); 18 new cases, 4041 backend (was 4023).
- [x] **11.2** Return the full screening — score, band, flags with regions,
  contributions, ruleset version — from `GET /api/screenings/{id}`, with a test
  asserting every field is present.
  Verify: the new test passes.
      — verified: the answer is the row's own columns; contributions are rebuilt from the stored flags against the row's own ruleset and refused on a mismatch, with no verification status (D72); 13 new cases, 4054 backend (was 4041).
- [x] **11.3** Add `GET /api/screenings` with band, document-type, date-range and
  pagination parameters, with a test per filter.
  Verify: the new tests pass.
      — verified: 30 new cases (20 endpoint, 10 repository) pass; `check-all.ps1` exits 0 (4084 backend, was 4054; 45 frontend, build).
- [x] **11.4** Reuse the existing error envelope for every new endpoint, with a
  test asserting a 404 body matches the existing `{error:{code,message}}` shape.
  Verify: the new test passes.
      — verified: 20 new cases hold every refusal of the three new endpoints to one `{"error":{"code","message"}}` body, and an app-level handler answers a fault no route caught in it too (D74); 4104 backend (was 4084), check-all.ps1 exits 0.
- [x] **11.5** Add request-id middleware that stamps every request and returns
  the id in a response header, with a test.
  Verify: the new test passes.
      — verified: 30 new cases stamp all four answers, adopt a caller's id and refuse one that is not id-shaped; 4134 backend (was 4104), check-all.ps1 exits 0 (D75).
- [x] **11.6** Convert the API logging to structured JSON including the request
  id and elapsed time, with a test asserting a log line parses as JSON.
  Verify: the new test passes.
      — verified: `app/logging_config.py` (JSON formatter, ambient request id, `log_event`) and `app/api/request_logging.py` (one timed line per request), all five prose log sites converted; `LOG_LEVEL` read by `app/config.py`. 32 new cases; removing the middleware turns 11 red, dropping the id 5, pinning `elapsed_ms` to zero 1. 4166 backend tests (was 4134); `check-all.ps1` exits 0. `D76`.
- [x] **11.7** Add a test asserting no log line ever contains image bytes, an
  OCR string, or an embedding.
  -- verified: 9 new cases pass; check-all.ps1 exits 0 (4175 backend tests)
- [x] **11.8** Add per-IP rate limiting to the analysis endpoints with a
  configurable limit, and a test that the N+1th request in a window is
  rejected with the standard error envelope.
  Verify: the new test passes.
      — verified: 31 new cases; taking either guard off, refusing at N rather than N+1, keying on a forwarded-for header, or freezing the window each turns tests red; 4206 backend tests (was 4175), check-all.ps1 exits 0 (D78).
- [x] **11.9** Keep and re-verify the existing upload size and pixel caps on the
  new endpoint, with a test for each.
  Verify: the new tests pass.
        — verified: 10 new cases in `backend/tests/api/test_upload_caps_api.py` hold both caps at their edges on `POST /api/screenings`; writing either as `>=`, moving either, dropping either, or capping a side instead of the area turns tests red; 4216 backend tests (was 4206), check-all.ps1 exits 0.
- [x] **11.10** Add `GET /api/version` returning app, ruleset, model and prompt
  versions from `version.py`, with a test.
  Verify: the new test passes.
        — verified: 7 new cases in `backend/tests/api/test_version_api.py` hold each key to its own constant; swapping two, binding at import, answering a literal, spending the rate-limit budget or dropping the models turns tests red; `MODEL_VERSIONS` added to `version.py` (D79); 4224 backend tests (was 4216), check-all.ps1 exits 0.
- [x] **11.11** Split liveness (`/health`) from readiness (`/ready`, which
  checks the database and ledger), with a test that `/ready` fails when the
  database is unreachable.
  Verify: the new test passes.
        — verified: 6 new cases in `backend/tests/api/test_health_api.py`; `/health` answers 200 while the database is unopenable and `/ready` answers 503 naming the check that failed -- for an unreachable database and for a reachable one
        whose ledger table is gone; dropping the ledger check, letting the driver fault through, answering 500,
        naming the wrong check, bypassing `get_sessions` or giving `/health` a session each turns them red; `routes_health.py` holds both;
        4229 backend tests (was 4224), check-all.ps1 exits 0.
- [x] **11.12** Write the OpenAPI contract test that snapshots the response
  schemas of all endpoints, so an unplanned shape change fails the suite.
  Verify: the new test passes, and fails if you add a field without updating it.
    -- verified: 3 cases in `backend/tests/api/test_openapi_contract.py` against the committed `openapi_contract.json`; adding a field to `ImageDimensions` or dropping `/ready`'s 503 turns it red with a diff.

**Gate 11:** Tier 0 is reachable over HTTP, rate-limited, logged without
identity data, and its contract is pinned by a test.

---

# Part 12 — Tier 1: OCR and field extraction

- [x] **12.1** Create `backend/app/pipeline/tier1/__init__.py` and
  `ocr.py` with an `OcrWord` model (text, bbox, confidence) and an `OcrResult`
  model (words, mean confidence), with a test constructing both.
  Verify: the new test passes.
  — verified: the module was absent when 12.2 began and was restored with this test; test_ocr.py passes.
- [x] **12.2** Define the `OcrEngine` interface with a `read(image) -> OcrResult`
  method, and a test asserting a stub satisfies it.
  Verify: the new test passes.
  — verified: 17 tests in `backend/tests/unit/test_ocr.py` pass; check-all.ps1 exits 0.
- [x] **12.3** Implement `TesseractEngine` behind the interface, reporting
  itself unavailable rather than raising when the binary is missing.
  Verify: the availability test passes on a machine with and without Tesseract.
      — verified: 31 tests pass with neither `tesseract` nor `pytesseract` installed, and pass again with both simulated on PATH/PYTHONPATH; 5 mutations each fail a named test; `check-all.ps1` exits 0 (4280 backend, 45 frontend, build).
- [x] **12.4** Implement `EasyOcrEngine` behind the same interface with the
  same unavailable-rather-than-raising behaviour.
  Verify: the new test passes.
      — verified: 35 tests in backend/tests/unit/test_easyocr_engine.py pass; 8 mutations each fail a named test; check-all.ps1 exits 0 (4315 backend, 45 frontend, build).
- [x] **12.5** Write `select_engine(preference)` that honours an explicit
  preference, otherwise picks the first available engine, and returns `None`
  when none is available.
  Verify: tests for explicit-unavailable, first-available, and none-available.
      — verified: 41 tests in `backend/tests/unit/test_selection.py` cover the three cases, the order, non-substitution and the refusals; 9 mutations each fail a named test; `selection.py` added and D85 settled; `check-all.ps1` exits 0 (4356 backend, 45 frontend, build).
- [x] **12.6** Add a test asserting Tier 1 degrades to "ocr unavailable" and the
  screening still completes — a missing OCR engine must not fail the document.
  Verify: the new test passes.
      — verified: 22 tests in backend/tests/unit/test_tier1_runner.py over the new run_tier1; 10 mutations each fail a named test; 
unner.py + D86 added; check-all.ps1 exits 0 (4378 backend, 45 frontend, build).
- [x] **12.7** Build a synthetic document image fixture that renders known field
  labels and values (name, passport number, DOB, expiry) at a known size, for
  use by every OCR test in this part.
  Verify: the fixture renders and its own test confirms the expected text is
  present in the source description.
      — verified: 32 tests in backend/tests/unit/test_document_images.py over the new document_images fixture; 10 mutations each fail a named test; D87 settled; check-all.ps1 exits 0 (4410 backend, 45 frontend, build).

- [x] **12.8** Write `re_read_field(image, region, engine)` that crops to the
  field region, upscales, re-thresholds, and re-runs OCR on just that region.
  Verify: a test asserting a small field reads correctly after re-read.
      — `reread.py` held only a placeholder and was replaced; 22 of the 37 cases in `test_reread.py` pin the field's own `value_box`, the 3x enlargement, the Otsu re-threshold, the three-channel hand-back and thirteen refused regions.
- [x] **12.9** Write the confidence gate: below `OCR_CONFIDENCE_THRESHOLD`, re-read
  once, then try the fallback engine, and only then report low confidence.
  Verify: a test with a deliberately blurred field asserts the re-read path is
  taken.
      — the same file's other 15 cases; `gate_field` pins `>=` at the boundary, re-read once, the fallback on the *same* crop, and `low_confidence` only after both; 11 mutations across both files each fail a named test; D88 settled.
- [x] **12.10** Add the anti-false-alarm test that the abstract requires: a field
  which is merely misread must be re-read correctly and must **not** produce a
  flag.
  Verify: the new test passes — this is the most important test in Part 12.
      — 13 tests in `test_false_alarm.py`; "no flag" is pinned as the gate owing nothing plus the module holding no `app.risk` import, since 12.15 has not been written; a gate that keeps the page read fails 8 tests across the two files.
- [x] **12.11** Define the per-document-type anchor-word and regex table for
  visible-text field extraction (label text → field), starting with passport.
  Verify: a test extracting all four fields from the fixture.
      — verified: 70 tests in test_fields.py extract all four fields off the fixture page; 9 of 11 mutants of fields.py each fail a named test; check-all.ps1 exits 0 (4530 backend, 45 frontend, build).
- [x] **12.12** Add the same table for visa and for national ID, with a test each.
      — verified: 4563 backend tests, check-all.ps1 exits 0.
  Verify: the new tests pass.
- [x] **12.13** Normalise extracted values per field type — dates to ISO, names
  uppercased and transliterated, numbers stripped of spaces — with a test per
  type.
  Verify: the new tests pass.
      — verified: 62 new cases in `test_fields.py` (165 in the file, was 103) and 4625 backend tests (was 4563); 13 of 14 mutants of the three normalisers each fail a named test, the 14th being equivalent (`str(date)` is `isoformat()`); `check-all.ps1` exits 0 (4625 backend, 45 frontend, build).
- [x] **12.14** Return every extracted field with the image region it came from,
  so a later mismatch can be pointed at.
  Verify: a test asserting each field's region is non-null.
      — verified: ExtractedFields carries a required `regions`, non-null for every field a printed page carries; 26 new cases in test_fields.py (191 in the file, was 165) over all three tables; 6 of 6 mutants of the new code each fail a named test; D92 settled.
- [x] **12.15** Write `compare_to_mrz(ocr_fields, mrz_document, tolerance)` that
  emits one flag per mismatched field, each carrying the OCR field's region and
  expected/found values, with transliteration tolerance for names.
  Verify: a test altering the printed DOB yields exactly one mismatch flag.
        — verified: `mismatch.compare_to_mrz` in 52 new cases in test_mismatch.py;
4703 backend tests (was 4651); 18 of 18 mutants of the new code killed, the 2 first-sweep survivors
answered by real fixes; D93 settled.
- [x] **12.16** Add a test that a name differing only by diacritics or spacing
  does **not** produce a mismatch flag.
  — verified: 3 tests (2 net new); check-all.ps1 exits 0, 4705 backend tests.

**Gate 12:** a printed-field alteration is caught with a region, and a
low-confidence misread is re-read instead of being flagged.

---

# Part 13 — Tier 1: barcode, template, layout, face

- [x] **13.1** Define the `BarcodeDecoder` interface and implement it with
  `zxing-cpp` (or `pyzbar` if already present), reporting unavailability rather
  than raising.
  Verify: an availability test passes.
      — **this box had no barcode code at all when 13.3 asked for one**, so the tick above was written with nothing behind it; `tier1/barcode.py` and `test_barcode.py` are new here, `zxing-cpp` is declared in `requirements.txt`, and no new decision was needed because `D82`/`D83` already hold the shape. 13 tests, `check-all.ps1` exits 0 (4747 backend).
- [x] **13.2** Generate a QR containing a known payload in a test, decode it, and
  assert the payload round-trips.
  Verify: the new test passes.
      — a QR carrying the TD3 specimen is drawn by the same binding that decodes it and read back whole, whitespace and newline included; part of `test_barcode.py`'s 13 tests.
- [x] **13.3** Compare the decoded barcode payload against the printed field it
  is expected to match, and emit a flag on disagreement.
  Verify: a test with a deliberately mismatched QR passes.
      — `mismatch.compare_to_barcode` reads the payload as a TD3 zone and answers one `OCR_BARCODE_MISMATCH` per disagreeing field; 45 new tests (38 to 83), 12 of 12 mutants killed, `check-all.ps1` exits 0.
- [x] **13.4** Define a template as a reference image plus field rectangles in a
  JSON file, and write a loader that reads `backend/app/pipeline/tier1/templates/`.
  Verify: a test loads a committed template.
      -- `templates/loader.py` reads the shipped `passport_td3.json` and its own
      `passport_td3.png` as package resources and takes the frame off the image
      rather than off the file; 39 new tests, `check-all.ps1` exits 0 (4786).
- [x] **13.5** Add a test that adding a new document type requires only a new
  JSON file, with no Python change.
  Verify: the new test passes.
      -- an invented type loads through `load_template` with nothing under `app/` naming it or its fields; both tests confirmed to fail under a registry and under a name table; `check-all.ps1` exits 0 (4788).
- [x] **13.6** Implement document corner detection and corner ordering, with a
  test on a synthetic quadrilateral document.
  Verify: the new test passes.
        -- the search is `m8_coverage.find_card` called rather than copied, and its
        fitted rectangle reads as no corners; 12 new tests, `check-all.ps1` exits 0 (4800).
- [x] **13.7** Compute a homography from the detected corners to the template's
  corners and warp the document into template space, with a test on a rotated
  synthetic document.
  Verify: the new test passes and the warped result is close to the template.
      -- verified: 12 new tests in `test_align.py`, `check-all.ps1` exits 0 (4812 backend tests, was 4800); 7 of 8 mutants killed, the filter named in `D97` and deliberately unpinned.
- [x] **13.8** Store the per-document field tolerances (position, size, rotation
  allowed) in the template JSON, with a test asserting every field has one.
  Verify: the new test passes.
      -- verified: 3 new tests in `test_template_loader.py`, `check-all.ps1` exits 0 (4815 backend tests, was 4812); all three fail when the tolerances are stripped from the file.
- [x] **13.9** Score per-field position deviation in aligned space and emit a
  `LAYOUT_DEVIATION` flag with the field's region when it exceeds tolerance.
      — verified: 20 tests, `check-all.ps1` exits 0 (4835 backend); `layout.py` and `test_layout.py` are new and `D99` records the measurement, but only `photo` is measurable on the committed reference because the four text rectangles are blank paper in it.
- [x] **13.10** Add a font-style proxy metric (stroke density, glyph height
  variance) and include it in the layout score, with a test.
  Verify: the new test passes.
      — verified: 8 new tests in `test_layout.py`, `check-all.ps1` exits 0 (4843 backend tests, was 4835); `font_style`, `font_deviation` and `layout_score` are new and `D100` records the measurement; 4 of 4 mutants killed.
- [x] **13.11** Add a test that an unaligned document produces a lower layout
  score than an aligned one, so the metric is not constant.
  Verify: the new test passes.
      — verified: 2 new tests in `test_layout.py`, `check-all.ps1` exits 0 (4845 backend tests, was 4843); one capture put into template space by corners turned 4 degrees scores 0.03 where the detector's own corners score 0.92, the one measurable field 24 px off its rectangle against 2 px.
- [x] **13.12** Define the `FaceDetector` and `Embedder` interfaces, plus
  `NullEmbedder`, which returns a deterministic zero vector and reports
  `is_stub: true`.
  Verify: a test asserting the null embedder is labelled as a stub.
      — verified: 41 new tests in `test_face.py`, `check-all.ps1` exits 0 (4886 backend tests, was 4845); `face.py` is new and `D101` records the seam, 14 of 14 mutants killed.
- [x] **13.13** Implement `InsightFaceEmbedder` (or FaceNet) behind the
  interface, reporting unavailability when the model is absent.
  Verify: an availability test passes either way.
- [x] **13.14** Implement face detection and alignment (landmark-based
  similarity transform to a canonical crop) in the photo region, with a test
  on a synthetic face-like fixture.
  Verify: the new test passes.
      — verified: 26 new tests in `test_face_align.py`, `check-all.ps1` exits 0
      (4913 backend tests, was 4886); `face_align.py` is new, `D102` records the
      seam, 8 of 8 mutants killed.
- [x] **13.15** Write `match_score(embedding_a, embedding_b, threshold)` using
  cosine similarity, with tests for identical, orthogonal, and below-threshold
  inputs.
      -- verified: 44 new tests in `test_face_match.py`, `check-all.ps1` exits 0 (4957 backend tests, was 4913); `D103` records the refusal and the clamp, 6 of 6 mutants killed.
- [x] **13.16** Emit `FACE_LOW_SIMILARITY` carrying the similarity and the
  threshold, and reproduce worked example B: similarity 0.41 against a
  threshold of 0.55 routes the case to Tier 2.
  Verify: the new test passes.

**Gate 13:** a document with a moved field, a bad QR, or a low face similarity
produces the right flag with a region, and a missing model never crashes a
screening.

---

# Part 14 — Orchestrator and escalation

- [x] **14.1** Create `backend/app/pipeline/orchestrator.py` with a
  `ScreeningContext` model (screening id, document type, image, reference date,
  flags so far, stage trace, mode).
  Verify: a test constructs a context.
      — verified: 16 new tests pass and the full backend suite is 4973 passed.
- [x] **14.2** Write a stage registry mapping stage name → callable, and a test
  asserting an unknown stage name raises a clear error.
  — verified: 22 new tests pass; backend suite 4995 passed.
- [x] **14.3** Run the existing quality gate as stage 0 and merge its failed
  checks into the flag stream as `quality` tier flags.
  Verify: a test with a blurred image produces a quality flag.
      — verified: 32 new tests pass and check-all.ps1 exits 0.
- [x] **14.4** Run Tier 0 and stop immediately on a hard fail, with a test
  asserting Tier 1 and Tier 2 never ran.
  Verify: the new test passes.
      — verified: 10 new tests pass, backend suite 5074 passed.
- [x] **14.5** Run Tier 1 and compute the partial score `R1` from its flags.
  Verify: a test asserts `R1` is present in the context after Tier 1.
  — verified: 10 new tests pass, backend suite 5084 passed.
- [x] **14.6** Implement the ambiguity check: `R1` inside a configurable band
  escalates, with tests for inside, at each edge, and outside.
  Verify: the new tests pass.
      — verified: 36 new tests pass, backend suite 5120 passed.
- [x] **14.7** Implement the high-risk-profile check (document type or issuing
  state on a configurable watchlist escalates), with a test.
  Verify: the new test passes.
  — verified: 31 new tests pass, backend suite 5151 passed.
- [x] **14.8** Implement the randomised deep audit draw as
  `HMAC(server_secret, screening_id) < rate`, with a test that the same id
  always draws the same outcome and that the distribution over 10 000 ids
  matches the configured rate.
  Verify: the new test passes.
      — verified: 30 new tests pass, backend suite 5181 passed, check-all.ps1 exits 0.
- [x] **14.9** Implement the full-depth mode flag that always escalates, with a
  test.
  Verify: the new test passes.
      — verified: 23 new tests pass, backend suite 5204 passed.
- [x] **14.10** Record a stage trace (stage, started, elapsed, flags added,
  escalated?) on the context and return it in the response, with a test
  asserting the trace order is tier 0 → tier 1 → tier 2.
  Verify: the new test passes.
    — verified: 20 new tests pass, backend suite 5224 passed.
- [x] **14.11** Add a test asserting an individual module failure is recorded in
  the trace as failed and does not abort the remaining modules — one broken
  check must not lose the whole screening.
  Verify: the new test passes.
    — verified: 15 new tests pass, backend suite 5239 passed.

**Gate 11 continued:** the cascade runs end to end, and each of the four
escalation triggers is independently tested.

---

# Part 15 — Tier 2: deep analysis

Every task here ships an interface plus an honest, labelled stand-in. None may
be described as a validated detector.

- [x] **15.1** Create `backend/app/pipeline/tier2/__init__.py` and `base.py`
  with a `DeepModule` interface (`run(context) -> DeepResult`) and a registry.
  Verify: a test asserting a registry with zero modules still returns a valid
  result.
      — verified: 8 new tests in `test_tier2_base.py`; backend suite 5247 (was 5239), `check-all.ps1` exits 0.
- [x] **15.2** Define `DeepResult` (score, heatmap, regions, module name,
  `is_stub`, `model_version`, detail), with a test asserting a stub result
  carries `is_stub: true` and a non-empty `model_version`.
  Verify: the new test passes.
      — verified: 15 new tests in `test_tier2_result.py`; backend suite 5262 (was 5247), `check-all.ps1` exits 0.
- [x] **15.3** Implement ELA: re-encode the image at several JPEG qualities and
  measure per-block discrepancy, producing a normalised heatmap, with a test
  asserting a re-compressed region lights up.
  Verify: the new test passes.
      — verified: 21 new tests in `test_tier2_ela.py`; backend suite 5283 (was 5262), `check-all.ps1` exits 0.
- [x] **15.4** Implement noise-residual analysis (high-pass residual, local
  variance map) and a score, with a test asserting an edited region shows
  anomalous variance.
  Verify: the new test passes.
      — verified: 34 new tests in `test_tier2_noise_residual.py`; backend suite 5317 (was 5283), `check-all.ps1` exits 0.
- [x] **15.5** Implement copy-move detection via self-similarity matching on
  SIFT/ORB blocks, with a test asserting a duplicated region inside the document
  is localised.
  Verify: the new test passes.
      — verified: 46 new tests in `test_tier2_copy_move.py`; backend suite 5363 (was 5317), `check-all.ps1` exits 0.
- [x] **15.6** Fuse ELA, noise-residual and copy-move into one tamper score and
  one overlay mask, naming every contributing module, with a test asserting the
  contributors are listed.
  Verify: the new test passes.
- [x] **15.7** Add a test that a clean synthetic document scores near zero, so
  the tamper score is not trivially high.
  Verify: the new test passes.
- [x] **15.8** Create a stamp template registry and implement stamp detection +
  template matching, with a test.
  Verify: the new test passes.
      — verified: 49 new tests in `test_tier2_stamp.py`; backend suite 5412 (was 5363), `check-all.ps1` exits 0.
- [x] **15.9** Make a missing stamp template report `not_configured` rather than
  `clean`, with a test asserting the distinction — silence must never read as
  a pass.
  Verify: the new test passes.
      — verified: 22 new tests in `test_tier2_stamp_config.py`; backend suite 5434 (was 5412), `check-all.ps1` exits 0.
- [x] **15.10** Define the `MorphClassifier` interface and a clearly labelled

  heuristic stand-in (frequency + boundary irregularity cues at the photo
  region) with `model_version: heuristic-v0`.
  Verify: a test asserting `is_stub` and the version string.
        -- verified: 28 new tests in `test_tier2_morph.py`; backend suite 5462 (was 5434), `check-all.ps1` exits 0.
- [x] **15.11** Define the `DeepfakeClassifier` interface and a labelled
  heuristic stand-in, with the same stub test.
  Verify: the new test passes.
      — verified: 26 new tests in `test_tier2_deepfake.py`; backend suite 5488 (was 5462).
- [x] **15.12** Build a per-document feature vector (ELA stats, noise stats,
  histogram, edge density, field geometry) and fit an IsolationForest on a
  committed feature fixture, with a test asserting an out-of-distribution
  synthetic document scores above the in-distribution ones.
  Verify: the new test passes.
        -- verified: 39 new tests in `test_tier2_anomaly.py`; backend suite 5527 (was 5488), `check-all.ps1` exits 0.
- [x] **15.13** Convert each Tier 2 result into flags with heatmap-derived
  regions, so Tier 2 findings are as locatable as Tier 0's.
  Verify: a test asserting a tampered-region flag carries a non-null region.
      -- verified: 34 new tests in `test_tier2_flags.py`; backend suite 5561 (was 5527), `check-all.ps1` exits 0.
- [x] **15.14** Add a test asserting every Tier 2 flag id exists in
  `weightsets/v1.yaml` (the weightset-completeness test must not regress).
  Verify: the new test passes.
      -- verified: 3 new tests in `test_tier2_flag_weightset.py`; backend suite 5564 (was 5561), `check-all.ps1` exits 0.

**Gate 15:** a tampered document produces located tamper flags from labelled
modules, a clean document does not, and a missing template is never reported
as clean.

---

# Part 16 — Cross-document verification

- [x] **16.1** Add a `TravelerCase` model and table (id, created_at, label) and a
  migration, with a test round-triping a case.
  Verify: the new test passes.
      — verified: 9 new tests in `test_traveler_case.py` round-trip a case through both a `create_all` and an `alembic upgrade head` schema; 3 in-place mutations each fail; `check-all.ps1` exits 0 (5574 backend, 45 frontend, build).
- [x] **16.2** Add a `case_id` and `document_role` (passport / visa / ID) to
  `Screening`, with a test asserting two screenings can share a case.
  Verify: the new test passes.
- [x] **16.3** Write `normalise_name(s)` — uppercase, strip diacritics,
  transliterate, collapse whitespace — with tests for `Müller` and `MÜLLER`
  producing the same key.
  Verify: the new tests pass.
      — verified: 35 new tests in `test_crossdoc_names.py`; new `app/pipeline/crossdoc/` package, accent map delegated to Tier 0 and no digraph folded (D127); 6 in-place mutations each fail; `check-all.ps1` exits 0 (5609 backend, 45 frontend, build).
- [x] **16.4** Write `names_match(a, b, tolerance)` with transliteration,
  `Ph`/`F`, compound-surname and token-ordering tolerance, returning a
  similarity plus the differing tokens.
  Verify: tests for `Mueller`/`Müller` (match), `Muller`/`Mueller` (match),
  `Rahman`/`Rahmani` (no match).
    — verified: 50 new tests in `test_crossdoc_names_match.py`; `names_match` returns a frozen `NameMatch` (similarity, differing, tolerance) and folds UE/SS/PH only, never in the key (D128); 10 in-place mutations each fail; `check-all.ps1` exits 0 (5659 backend, 45 frontend, build).
- [x] **16.5** Write `documents_consistent(documents_in_case)` checking
  passport-number ↔ visa cross-reference, with a test that a visa referencing an
  unknown passport raises a flag.
  Verify: the new test passes.
    — verified: 64 new tests in `test_crossdoc_documents_consistent.py`; exact filler-free key with no digraph fold and no tolerance, and a case that compared nothing answers `not_configured` (D129); 12 in-place mutations each fail; `check-all.ps1` exits 0 (5723 backend, 45 frontend, build).
- [x] **16.6** Add validity-window consistency (the visa must cover the travel
  date) with a test.
  Verify: the new test passes.
    - verified: 74 new tests in `test_crossdoc_visa_validity.py`; travel date is an argument and the window is `valid_from`/`valid_until` on `CaseDocument`, closed at both ends (D130); 13 of 14 in-place mutations fail, the surviving one is `str(travel)`, which is `isoformat()` by definition; `check-all.ps1` exits 0 (5797 backend, 45 frontend, build).
- [x] **16.7** Write `face_consistent(documents_in_case)` using the Part 13
  interfaces, degrading cleanly when no embedder is available, with a test for
  both paths.
  — verified: 74 new tests pass; full backend suite 5871 passes, check-all.ps1
  exits 0; 20 mutations, 20 killed.
- [x] **16.8** Emit cross-document flags into the same `EvidenceFlag` stream with
  `tier: crossdoc`, and add a test that they aggregate into the same risk score
  as Tier 0/1/2 flags.
  Verify: the new test passes.

**Gate 16:** a case with a mismatched visa raises a located cross-document flag
and moves the score.

---

# Part 17 — Explainability

The verifier is pure code and needs no model. It is the cheapest part of the
"the model narrates and never decides" claim, so build it before the LLM client.

- [x] **17.1** Create `backend/app/explain/__init__.py` and
  `verifier.py` with `extract_numbers(text)`, and a test proving it finds
  numbers in text and ignores ordinals inside words.
  Verify: the new test passes.
  — verified: 19 new tests pass; full backend suite 5890 passes, check-all.ps1
  exits 0; 8 mutations, 8 killed. Decision recorded as `D132`.
- [x] **17.2** Add `extract_dates(text)` and `extract_field_names(text)`
  (capitalised tokens and known flag ids), with a test each.
  Verify: the new tests pass.
  — verified: 55 new tests pass; full backend suite 5945 passes, check-all.ps1
  exits 0; 12 mutations, 12 killed. Decision recorded as `D133`.
- [x] **17.3** Write `verify_summary(summary, flag_data)` returning pass/fail
  plus the offending tokens, requiring every extracted number, date and field
  name to appear in the flag data.
  Verify: the new test passes.
  — verified: 57 new tests pass; full backend suite 6002 collected, check-all.ps1 exits 0; 8 mutations, 8 killed. Decision recorded as `D134`.
- [x] **17.4** Add a negative test: a summary containing `0.98` or a flag id not
  present in the flag data is rejected.
  Verify: the new test passes.
  — verified: 41 new tests pass (98 in file); full backend suite 6043 passes, check-all.ps1 exits 0; 4 mutations, 4 killed.
- [x] **17.5** Write `template_summary(flags, band)` producing 2–3 sentences
  with one line per flag, in plain language, with a test.
  Verify: the new test passes.
  — verified: 81 new tests pass; full backend suite 6124 passes, check-all.ps1 exits 0; 16 mutations, 16 killed. Decision recorded as `D135`.
- [x] **17.6** Add a test that the template summary passes the verifier from
  17.3 — the fallback must satisfy the same contract as the model output.
  Verify: the new test passes.
  — verified: 72 new tests pass; full backend suite 6196 passes, check-all.ps1 exits 0; 6 mutations, 6 killed.
- [x] **17.7** Create the `Summarizer` interface and a self-hosted LLM client
  speaking the Ollama/llama.cpp HTTP API, with a hard timeout and no external
  fallback — when it fails it returns `None`, it does not raise.
  Verify: a test against a non-existent endpoint returns `None` within the
  timeout.
    — verified: 87 new tests pass; full backend suite 6283 passes, check-all.ps1
    exits 0; 31 mutations, 31 killed. Decision recorded as `D136`.
- [x] **17.8** Add a test asserting the client is never called when
  `LOCAL_LLM_ENABLED=false`, and that no request ever leaves the configured
  local host.
  Verify: the new test passes.
    — verified: 24 new tests pass; full backend suite 6307 passes, check-all.ps1
    exits 0; 13 mutations, 13 killed. Decision recorded as `D137`.
- [x] **17.9** Create the versioned prompt template `prompts/v1.txt` and a
  loader exposing `PROMPT_VERSION`, with a test that changing the file changes
  the reported version.
  Verify: the new test passes.
    — verified: 24 new tests pass; full backend suite 6331 passes,
    check-all.ps1 exits 0; 21 mutations, 20 killed (one prose survivor,
    untested by choice). Decision recorded as `D138`.
- [x] **17.10** Build the flag-data payload sent to the model (structured flags,
  band, contributions, no image data), with a test asserting the payload
  contains no pixel data.
  Verify: the new test passes.
    — verified: 25 new tests pass; full backend suite 6356 passes, check-all.ps1 exits 0; 21 mutations, 21 killed. Recorded as `D139`.
- [x] **17.11** Wire the reject-and-fallback path: verifier failure discards the
  model text, uses the template summary, and records `summary_source` plus
  `verification: failed` in the response.
  Verify: the new test passes.
    — verified: 70 new tests pass; full backend suite 6426 passes, check-all.ps1
    exits 0; 20 mutations, 20 killed. Recorded as `D140`.
- [x] **17.12** Add a test feeding deliberately poisoned model output and
  asserting it never reaches the response and the rejection is auditable.
  Verify: the new test passes.
    — verified: 68 new tests pass; full backend suite 6494 passes, check-all.ps1
    exits 0; 4 mutations of the reject branch, 4 killed. Recorded as `D141`.
- [x] **17.13** Add model-free per-flag reason templates so the officer always
  has a plain-language explanation, with a test asserting every flag id in
  `flag_ids.py` has a reason template.
  Verify: the new test passes.
    — verified: 262 new tests pass; full backend suite 6756 passes, check-all.ps1 exits 0; 6 mutations, 6 killed. Recorded as `D142`.

**Gate 17:** a summary can only reach the officer if every number, date and
field name in it exists in the flag data, and the model-free fallback satisfies
the same rule.

---

# Part 18 — Remaining API surface

- [x] **18.1** Add `POST /api/screenings/{id}/decision` accepting
  `allow` / `further_inspection` / `reject`, a remark, and an `override` flag,
  with a test per action value.
  Verify: the new tests pass.
    — verified: 32 new tests pass; full backend suite 6788 passes; 9 mutations, 9 killed. Recorded as `D143`.
- [x] **18.2** Reject a `reject` on a `low` band without `override: true`, with a
  test proving the rejection is a validation error, not a silent accept.
  Verify: the new test passes.
    — verified: 24 new tests pass; full backend suite 6812 passes; 8 mutations, 8 killed. Recorded as `D144`.
- [x] **18.3** Emit the `decision_recorded` and `override_recorded` audit events
  from the decision endpoint, with a test asserting both appear.
  Verify: the new test passes.
    — verified: 24 new tests pass; full backend suite 6836 passes, check-all.ps1 exits 0; 13 mutations, 13 killed. Recorded as `D145`.
- [x] **18.4** Make the decision endpoint idempotent-safe: a second decision
  changes status and emits a new event rather than overwriting, with a test.
  Verify: the new test passes.
  — verified: 21 new tests pass; full backend suite 6857 passes, check-all.ps1 exits 0; 7 mutations, 7 killed. Recorded as `D146`.
- [x] **18.5** Add `DELETE /api/screenings/{id}` doing a soft delete, with a test
  asserting the screening disappears from reads.
  Verify: the new test passes.
    — verified: 14 new tests pass; full backend suite 6871 passes, check-all.ps1 exits 0; 7 mutations, 7 killed. Recorded as `D147`.
- [x] **18.6** Add a test asserting the ledger entry and audit events survive
  the delete — deleting a screening must not erase the audit trail.
  Verify: the new test passes.
    — verified: 11 new tests pass; full backend suite 6882 passes, check-all.ps1 exits 0; 3 mutations, 3 killed. Proves the clause D147 left open; recorded as D148.
- [x] **18.7** Add `GET /api/audit/{audit_id}/verify` returning
  `verified` / `altered` / `unknown` with the batch root and proof length, and a
  plain-language explanation of what was checked.
  Verify: the new test passes.
    — verified: 21 new tests pass; full backend suite 6903 passes, check-all.ps1 exits 0; 18 mutations, 18 killed. Recorded as `D149`.
- [x] **18.8** Add a test that tampering with a stored screening payload in the
  database flips the verify endpoint to `altered`.
  Verify: the new test passes.
    — verified: 10 new tests pass; full backend suite 6913 passes, check-all.ps1 exits 0; 7 mutations, 7 killed. Closes the record-mismatch vector of `D149`.
- [x] **18.9** Add `GET /api/screenings/{id}/report` returning standalone
  printable HTML with bands, flags, reasons and the audit id, and a test
  asserting it references no external asset.
  Verify: the new test passes.
    — verified: 13 new tests pass; full backend suite 6926 passes, check-all.ps1 exits 0; 22 mutations, 22 killed. Recorded as `D150`.
- [x] **18.10** Add an SSE stream endpoint reporting per-tier and per-module
  progress, with a test asserting the event shape and a clean disconnect.
  Verify: the new test passes.
    — verified: 24 new tests pass; full backend suite 6950 passes, check-all.ps1 exits 0; 24 mutations, 23 killed, 1 equivalent. Recorded as `D151`.
- [x] **18.11** Add a polling fallback endpoint returning the same progress
  state, with a test asserting both routes report identical state.
  Verify: the new test passes.
    — verified: 13 new tests pass; full backend suite 6963 passes, check-all.ps1 exits 0; 12 mutations, 12 killed. Recorded as `D152`.
- [x] **18.12** Return the stage trace and per-stage timings on the screening
  response so the UI can show where time went, with a test.
  Verify: the new test passes.
    — verified: 17 new tests pass; full backend suite 6980 passes, check-all.ps1 exits 0; 15 mutations, 14 killed, 1 equivalent. Recorded as `D153`.

**Gate 18:** the officer can record a decision, the decision is in the audit
trail, and any event can be independently verified.

---

# Part 19 — Encrypted evidence store and retention

- [x] **19.1** Load a master key from the environment, generating a dev key when
  absent, with a test asserting a missing key never silently becomes a known
  constant in production mode.
  Verify: the new test passes.
    — verified: 43 new tests pass; full backend suite 7023 passes, check-all.ps1 exits 0; 24 mutations of D154's lines and 6 of D155's, all killed. Recorded as D154.
- [x] **19.2** Generate a per-blob data key and wrap it with the master key
  (AES-GCM), with a round-trip test.
  Verify: the new test passes.
    — verified: 33 new cases pass; full backend suite 7056 passes, check-all.ps1 exits 0; 23 mutations of the shipped lines, all killed. Recorded as D156.
- [ ] **19.3** Implement `put(bytes) -> blob_ref` writing AES-GCM ciphertext
  under a content-addressed filename, with a round-trip test.
  Verify: the new test passes.
- [ ] **19.4** Add a test asserting the stored ciphertext does not contain the
  plaintext file header.
  Verify: the new test passes.
- [ ] **19.5** Add a test asserting a wrong key fails closed with a clear error
  rather than returning garbage.
  Verify: the new test passes.
- [ ] **19.6** Wire the evidence store into the screening flow so the uploaded
  image is stored encrypted and the screening row holds only the blob reference.
  Verify: a test asserting the screening row contains no image bytes.
- [ ] **19.7** Add `RETENTION_DAYS` config per record class and a purge function,
  with a test that a purge actually deletes expired blobs.
  Verify: the new test passes.
- [ ] **19.8** Make purge idempotent and make it log what it deleted, with a test
  asserting a second purge deletes nothing and that ledger entries are never
  touched.
  Verify: the new test passes.

**Gate 19:** identity images are encrypted at rest, referenced by hash, and
retention is enforced without touching the audit trail.

---

# Part 20 — Frontend: shared plumbing

The frontend stays vanilla HTML + CSS + JS with `node --test`. No bundler, no
framework. New scripts follow the existing IIFE-per-page pattern.

Verified in `ux4g-web-components@2.1.0` while writing this list — use these,
they are real:

- **Runtime-implemented behaviours:** `data-ux4g-toggle`, `data-ux4g-tab`,
  `data-ux4g-indeterminate` (progress), `data-ux4g-select-all`.
- **CSS-only, no runtime behaviour** (you must supply the JS): `ux4g-accordion`,
  `ux4g-badge`, `ux4g-skeleton`, `ux4g-notification`, `ux4g-tag`, `ux4g-tooltip`,
  `ux4g-drawer`, `ux4g-table`, `ux4g-pagination`, `ux4g-modal`.
- **Band colours:** `ux4g-tag-{filled|outline|tonal|text}-{success|warning|error|info|neutral|primary|secondary|tertiary}` + `ux4g-tag-s`.
- **Badge:** `ux4g-badge-{dot|icon|digit}-{color}` + `ux4g-badge-{s|m|l}`.
- **Progress:** `ux4g-progress-bar`, `ux4g-progress-bar-track`,
  `ux4g-progress-bar-fill`.
- **Skeleton:** `ux4g-skeleton-{title,subtitle,main,block,circle,btn}`.

- [ ] **20.1** Create `frontend/api.js` exposing a single `request()` built on
  `fetch`, reading the base URL from `window.DRISHTI_CONFIG`, with a unit test
  asserting the base URL is read from config and defaults to same-origin.
  Verify: `npm test` passes with the new test.
- [ ] **20.2** Add a timeout to `request()` using `AbortController`, with a test
  asserting an aborted request rejects with a distinguishable error.
  Verify: the new test passes.
- [ ] **20.3** Normalise API errors into `{code, message, status}` in `api.js`,
  with a test per error shape (network failure, non-JSON body, structured error
  envelope).
  Verify: the new tests pass.
- [ ] **20.4** Move every existing `fetch` call out of `home.js` and into
  `api.js`, and add a test asserting no page script calls `fetch` directly.
  Verify: the new test passes.
- [ ] **20.5** Create `frontend/format.js` with band labels
  (`low`/`review`/`high` → display text), score formatting, and relative
  timestamps, with unit tests for each function including timezone-independent
  timestamp cases.
  Verify: the new tests pass.
- [ ] **20.6** Create `frontend/status.js` that probes `/health` on load and
  exposes `checking` / `online` / `unreachable` / `unconfigured` (no API URL
  baked into the build), with a test per state.
  Verify: the new tests pass.
- [ ] **20.7** Render the connection state in the topbar of every page, and add
  a test asserting each page contains the status element.
  Verify: the new test passes.
- [ ] **20.8** Add a test asserting the CORS-failure case shows a distinct,
  accurate message from a 5xx, a validation error, and an unconfigured build —
  the current generic "Could not connect" is misleading.
  Verify: the new test passes.

**Gate 20:** one module owns all API access, all four connection states are
distinguishable, and no page script calls `fetch`.

---

# Part 21 — Frontend: extract the duplicated shell

The sidebar/topbar/footer markup is currently duplicated across six pages. Nine
pages will make that a bug generator, so fix it before adding pages. This is
build-time injection, not client-side JS, so pages still render without
JavaScript.

Accepted tradeoff: opening a raw source `.html` file from disk will no longer
show the shell. The documented workflow becomes `npm run build` (or a preview
server), which task 21.9 covers.

- [ ] **21.1** Extract the current shell markup from `home.html` into
  `frontend/shell.html` as a template with the sidebar, topbar and footer,
  replacing page-specific bits with `{{placeholder}}` tokens.
  Verify: the file exists and the existing nav links are intact.
- [ ] **21.2** Define the placeholder tokens in one module
  (`frontend/shell-tokens.js`): page title, active-nav key, page heading.
  Verify: the module exports all three.
- [ ] **21.3** Make `build.cjs` inject the shell into every page, failing the
  build with a clear message if a page is missing a token, and add a
  `build.test.cjs` case for that failure path.
  Verify: `npm test` and `npm run build` both pass.
- [ ] **21.4** Replace the shell-duplication test in `pages.test.cjs` with an
  assertion that the shell exists once in the source and is injected at build
  time, so the test inverts rather than being deleted.
  Verify: the new test passes.
- [ ] **21.5** Add a build test asserting every page in `dist/` contains
  byte-identical shell markup.
  Verify: the new test passes.
- [ ] **21.6** Add a build test asserting each page marks exactly one nav item
  active, so the active state cannot silently disappear.
  Verify: the new test passes.
- [ ] **21.7** Verify all sidebar links still resolve to real files in `dist/`,
  with a test that fails on a dead link.
  Verify: the new test passes.
- [ ] **21.8** Add the new pages to the `staticFiles` list in `build.cjs` as you
  create them in Parts 22–24, keeping the list and the filesystem in sync via a
  test.
  Verify: the new test passes.
- [ ] **21.9** Update `frontend/README.md` to document the build-then-serve
  workflow, and add a `npm run preview` script that builds and serves `dist/`.
  Verify: `./node scripts/preview` serves the site and every page loads.

**Gate 21:** shell markup exists once, every built page carries it, and the
dead-link test guards navigation.

---

# Part 22 — Frontend: the officer screening workspace

This replaces the current upload-in-a-modal flow with a page an officer could
actually work at. Run the UX4G preflight (`ux4g-design` skill) and write down
the component list before writing markup.

- [ ] **22.1** Write the UX4G preflight note for `screening.html`: the components
  with exact variant and size, and any requirement UX4G cannot meet.
  Verify: the note exists in `docs/` before any markup is written.
- [ ] **22.2** Create `frontend/screening.html` using the shell tokens from Part
  21, with the document-type selector (UX4G radio group), the source chooser,
  and the submit action.
  Verify: `npm test` and `npm run build` pass.
- [ ] **22.3** Implement the upload path: file input, client-side type and size
  validation reusing the existing 10 MiB and JPEG/PNG/WebP rules, and a local
  preview before submission.
  Verify: tests for each rejected type, the size boundary, and an accepted file.
- [ ] **22.4** Implement real camera capture with `getUserMedia`, with a test
  asserting the consent copy is present and capture is not auto-started.
  Verify: the new test passes.
- [ ] **22.5** Handle the two failure modes explicitly: permission denied, and an
  insecure context (non-localhost HTTP), each with its own accurate message.
  Verify: tests for both branches.
- [ ] **22.6** Submit the image to `POST /api/screenings` via `api.js` and store
  the returned `screening_id`, with a test asserting the id reaches the result
  page URL.
  Verify: the new test passes.
- [ ] **22.7** Show the quality-gate result before analysis, with a "Retake"
  action and an "Analyse anyway" action that states its consequence, and a test
  asserting the file is cleared on retake.
  Verify: the new test passes.
- [ ] **22.8** Build the cascade progress panel using
  `ux4g-progress-bar`/`ux4g-progress-bar-track`/`ux4g-progress-bar-fill`, with
  one row per tier showing status and elapsed time, and a test asserting the
  markup and the per-tier update logic.
  Verify: the new test passes.
- [ ] **22.9** Implement SSE consumption with an automatic fallback to polling
  when the stream cannot connect, and a test asserting the fallback triggers.
  Verify: the new test passes.
- [ ] **22.10** Use `ux4g-skeleton-*` for the loading state on the result page
  while the screening is in progress, with a test asserting the skeleton
  elements appear and are removed.
  Verify: the new test passes.
- [ ] **22.11** Make the progress panel accessible: a live region announcing
  tier completion, and a test asserting `aria-live` and a text alternative for
  the progress bar.
  Verify: the new test passes.
- [ ] **22.12** Change the home page "Start screening" action to navigate to
  `screening.html`, and add a test asserting the navigation target.
  Verify: the new test passes.

**Gate 22:** an officer can pick a document type, upload or capture an image,
watch the cascade progress, and reach a result — all without a login.

---

# Part 23 — Frontend: the result view with located evidence

The centrepiece. A band badge, a score, a flag list, and the flagged region
highlighted on the document itself.

- [ ] **23.1** Write the UX4G preflight note for `result.html` and create the
  page skeleton with the shell tokens.
  Verify: `npm test` and `npm run build` pass.
- [ ] **23.2** Create `frontend/overlay.js` that maps normalised flag regions onto
  the displayed image, handling both a plain box and a polygon region, with unit
  tests for the coordinate mapping at three image/display size combinations.
  Verify: the new tests pass.
- [ ] **23.3** Add hit-testing so clicking a region selects its flag, and
  clicking a flag highlights its region, with a test asserting the round trip in
  both directions.
  Verify: the new test passes.
- [ ] **23.4** Render the band as a UX4G tag
  (`ux4g-tag-filled-success` / `-warning` / `-error` + `ux4g-tag-s`) and the
  score next to it, with a test asserting the correct variant per band.
  Verify: the new test passes.
- [ ] **23.5** Render the flag list grouped by tier, each row showing label,
  weight, confidence, expected, found, and the plain-language reason, with a
  test asserting all fields appear.
  Verify: the new test passes.
- [ ] **23.6** Handle a flag with no region honestly — show it in the list with a
  "not locatable on this document" note rather than silently omitting it, with
  a test.
  Verify: the new test passes.
- [ ] **23.7** Add a contribution breakdown panel (per-flag weight × value) so
  the score is explainable, with a test asserting contributions are rendered and
  sum to the displayed score.
  Verify: the new test passes.
- [ ] **23.8** Render the officer summary with its `summary_source` and
  `verification` badges, and show a plain explanation when verification failed,
  with a test per state.
  Verify: the new tests pass.
- [ ] **23.9** Add the decision form (allow / further inspection / reject), a
  remark field, and an override control that appears only when the officer
  contradicts the band, with a test asserting the control is hidden by default.
  Verify: the new test passes.
- [ ] **23.10** Submit the decision to `POST /api/screenings/{id}/decision`,
  then lock the form, with a test asserting the form cannot be resubmitted.
  Verify: the new test passes.
- [ ] **23.11** Display the ruleset version, model versions and prompt version,
  with a test asserting they are present and labelled as experimental.
  Verify: the new test passes.
- [ ] **23.12** Add an "actor" display sourced from the configurable station
  identifier, with a test asserting the frontend contains no credential or
  session input anywhere.
  Verify: the new test passes.
- [ ] **23.13** Add a link to the printable report route from Part 18, with a
  test asserting the link target.
  Verify: the new test passes.

**Gate 23:** every flag is listed with a reason, a located flag highlights on
the document, the score is explainable, and a decision can be recorded.

---

# Part 24 — Frontend: history, audit, and case views

- [ ] **24.1** Write the UX4G preflight note for the history view and rewire
  `screenings.html` from sample rows to `GET /api/screenings` via `api.js`.
  Verify: `npm test` passes and no sample row remains in the markup.
- [ ] **24.2** Keep the existing table UX (`ux4g-table ux4g-table-m
  ux4g-table-zebra-rows ux4g-table-interactive`) and the 7 columns, with a test
  asserting the class composition is unchanged.
  Verify: the new test passes.
- [ ] **24.3** Move search, filter chips, sort and pagination to the server
  parameters, keeping client-side behaviour for responsiveness, with a test per
  control.
  Verify: the new tests pass.
- [ ] **24.4** Make the band filter chips use the real band values, and add the
  existing `ux4g-filter-chip-group`/`ux4g-filter-chip-md` composition, with a
  test.
  Verify: the new test passes.
- [ ] **24.5** Wire the row "View" action to `result.html?id=…` and the "Delete"
  action to `DELETE /api/screenings/{id}` with a confirmation step, with tests
  for both.
  Verify: the new tests pass.
- [ ] **24.6** Keep the working CSV export, and fix it to export the currently
  filtered server-side rows rather than the original sample set, with a test
  asserting the exported content matches the visible rows.
  Verify: the new test passes.
- [ ] **24.7** Add loading, error and empty states using `ux4g-skeleton-*` and
  `ux4g-empty-state`, with a test per state.
  Verify: the new tests pass.
- [ ] **24.8** Write the UX4G preflight note for the audit view and create
  `audit.html` listing a screening's events from `GET /api/audit/{id}/verify`
  plus the event list, with a test.
  Verify: `npm test` and `npm run build` pass.
- [ ] **24.9** Show the Merkle verification result (`verified` / `altered` /
  `unknown`) with a plain-language explanation of what was checked, and a test
  asserting an `altered` result is visually distinct and explained.
  Verify: the new test passes.
- [ ] **24.10** Add the batch id, batch root and proof length to the audit view,
  with a test.
  Verify: the new test passes.
- [ ] **24.11** Write the UX4G preflight note for the case view and create
  `cases.html` showing a traveler's documents side by side with each document's
  band and any cross-document flags, with a test.
  Verify: `npm test` and `npm run build` pass.
- [ ] **24.12** Add a test asserting the case view degrades to a clear empty
  state when a case has only one document.
  Verify: the new test passes.

**Gate 24:** history, audit and case views are all backed by real API data with
no sample rows remaining.

---

# Part 25 — Frontend: UX4G compliance, accessibility, and browser verification

Nothing in this repository has ever been rendered in a browser. Every visual
claim so far — including in Parts 22–24 — is inferred from reading CSS. This
part is what makes any of it trustworthy.

- [ ] **25.1** For each new page, list every UX4G class used and grep
  `styles/ux4g.css` to confirm it exists, adding a test that fails on an unknown
  class.
  Verify: the new test passes.
- [ ] **25.2** For each new page, list every UX4G behaviour used and grep
  `dist/runtime/design-system.js` to confirm the runtime implements it, adding a
  test that fails when a page relies on an unimplemented behaviour.
  Verify: the new test passes.
- [ ] **25.3** Confirm the accordion in `guide.html` still needs the
  `pages.js` fallback, since the runtime ships no accordion behaviour. If the
  existing assertion that the runtime lacks accordion support starts failing,
  the package was fixed — remove the fallback and the assertion.
  Verify: `npm test` passes either way, and the outcome is recorded in
  `handover.md`.
- [ ] **25.4** Confirm the stepper workaround in `pages.css` is still needed by
  running the existing assertion. If it starts failing, the malformed selector
  upstream is fixed — delete the workaround.
  Verify: `npm test` passes and the outcome is recorded.
- [ ] **25.5** Implement a focus trap, `Escape` handling, focus restore, and
  `aria-modal` on the remaining dialogs, with tests.
  Verify: the new tests pass.
- [ ] **25.6** Check keyboard order and visible focus across all pages, and fix
  any positive `tabindex` found, with a test asserting no positive tabindex
  remains.
  Verify: the new test passes.
- [ ] **25.7** Render every page at 320, 768, 1024 and 1440 CSS pixels and fix
  overflow, clipping and unreadable text. Record the results.
  Verify: a committed screenshot set per width.
- [ ] **25.8** Render every page in both light and dark theme — the dark theme
  has shipped unrendered until now — and fix any invisible border or unreadable
  text. Record the results.
  Verify: a committed screenshot set per theme.
- [ ] **25.9** Run a contrast check on text, borders and focus rings in both
  themes, and record any failures rather than asserting there are none.
  Verify: the results are written down.
- [ ] **25.10** Check that the 112.5% and 125% text-size settings do not break
  the table, the overlay, or the decision form, and record the result including
  the known ~32 internal `px` sizes in the package.
  Verify: the results are written down.
- [ ] **25.11** Exercise the full flow in a real browser against a local backend:
  upload a synthetic image, watch the cascade, click a flag, see the region
  highlight, record a decision, and verify the audit trail.
  Verify: a committed screenshot per step and a clean console.
- [ ] **25.12** Confirm the upload request fires only after submission, and that
  `preferences.js` does not throw when `localStorage` is unavailable.
  Verify: tests plus a browser check in private-browsing mode.
- [ ] **25.13** Re-run the deployed checks: `/health`, each deployed
  `api-config.js`, and an image upload through the browser's network panel, and
  record which origins the API actually allows.
  Verify: the results are written down, and any `.tech` CORS failure is resolved
  by comparing `location.origin` against the allowlist and the active Cloud Run
  revision.

**Gate 25:** every page has been rendered in a browser in both themes at four
widths, with the console clean and the results recorded.

---

# Part 26 — Ops and CI

- [ ] **26.1** Add a multi-stage `backend/Dockerfile` with a pinned base image
  and a `.dockerignore`, with a build-and-run test that asserts `/health`
  responds from the image.
  Verify: the image builds and the endpoint responds.
- [ ] **26.2** Run the container as a non-root user, with a test asserting the
  user is not root.
  Verify: the new test passes.
- [ ] **26.3** Set the Cloud Run settings: concurrency 1, a small maximum instance
  count, and a request timeout sized for the cascade, documented in one place.
  Verify: the settings are documented and applied.
- [ ] **26.4** Keep the CORS allowlist and the frontend build variable in one
  documented list, with every entry being an origin that actually serves the
  frontend, and no `*`.
  Verify: a test asserting the config rejects `*`.
- [ ] **26.5** Add `alembic upgrade head` to the deploy step and confirm the
  SQLite path still works for a local demo, with a test.
  Verify: the new test passes.
- [ ] **26.6** Add a GitHub Actions workflow running backend pytest, frontend
  `npm test`, and `npm run build` on every push, with a test asserting the
  workflow file covers all three.
  Verify: the workflow runs green.
- [ ] **26.7** Add a build-artefact contract check to CI, so a page or script
  missing from `dist/` fails the build.
  Verify: the check fails when a file is deliberately omitted.
- [ ] **26.8** Emit per-tier latency and cascade-outcome metrics, and a
  correlation id present in every log line and on the screening record, with
  tests.
  Verify: the new tests pass.
- [ ] **26.9** Add a rate-limit quota to the public demo endpoint, plus a
  synthetic-image-only notice in the UI and the API response, with a test
  asserting the notice is present.
  Verify: the new test passes.

**Gate 26:** the app builds, tests, and deploys reproducibly, and the build
cannot silently ship a missing page.

---

# Part 27 — Validation and evaluation

`abstract.txt` states "No accuracy figures are claimed in this document." This
part is how you earn the right to change that sentence. Until it is done, keep
the sentence.

- [ ] **27.1** Build a synthetic passport generator producing a document image
  with a correct MRZ, a field manifest, and no real identity data.
  Verify: a test round-tripping generated image → parsed MRZ.
- [ ] **27.2** Extend the generator to visas and to national IDs.
  Verify: a test per document type.
- [ ] **27.3** Add tamper injection to the generator: photo replacement, text
  edit, date-of-birth change, and stamp edit, each recording the affected
  region as ground truth.
  Verify: a test asserting the manifest records a region for every injection.
- [ ] **27.4** Define the ground-truth manifest schema and a test that validates
  every generated document against it.
  Verify: the new test passes.
- [ ] **27.5** Write the evaluation harness for field-level extraction accuracy.
  Verify: it reports a number over the corpus.
- [ ] **27.6** Extend it to tamper catch rate and false-alert rate, with a test
  that both are reported separately.
  Verify: the new test passes.
- [ ] **27.7** Extend it to region overlap (IoU) between the flagged area and
  the actual edited area, with a test.
  Verify: the new test passes.
- [ ] **27.8** Build an MRZ negative corpus where every document has exactly one
  deliberately corrupted check digit, and assert a 100% catch rate.
  Verify: the harness fails if a single document is missed.
- [ ] **27.9** Add a latency benchmark reporting median and p95 per tier against
  the abstract's targets, labelled as measured versus designed.
  Verify: the benchmark produces a table with both columns.
- [ ] **27.10** Add face-evaluation scaffolding reporting FAR/FRR with
  per-demographic-group slots, wired to the Part 13 interfaces, reporting
  honestly when no model is configured.
  Verify: the scaffolding runs and says so.
- [ ] **27.11** Add morph/deepfake evaluation scaffolding following the NIST
  FATE MORPH framing, with the same honesty about stubs.
  Verify: the scaffolding runs and says so.
- [ ] **27.12** Add a results view to the app showing each measured metric with
  the dataset it came from, and a test asserting every number shown is
  accompanied by its dataset reference.
  Verify: the new test passes.

**Gate 27:** every number displayed anywhere has a dataset behind it, and
anything without one is labelled a design target.

---

# Part 28 — Docs, demo, and cleanup

- [ ] **28.1** Write `DEMO.md`: a three-minute judge walkthrough, in order, with
  the exact screen and action at each step.
  Verify: the file exists and someone else can follow it unaided.
- [ ] **28.2** List every claim in `DEMO.md` as either measured or designed, and
  make sure nothing aspirational is stated as fact.
  Verify: the list is complete.
- [ ] **28.3** Document the known limitations honestly, including the Tier 2
  stubs, the missing model weights, and the unverified-then-now-verified browser
  state.
  Verify: the file exists.
- [ ] **28.4** Update root `README.md`: project structure, what is implemented,
  what is not, and a link to `tasks.md` and `ROADMAP.md`.
  Verify: no stale claims remain.
- [ ] **28.5** Rewrite `handover.md` to match reality: the current branch and
  commit, what is deployed, what is verified, what is not, and the next
  unfinished task id from this file.
  Verify: every claim in it is either independently checked or labelled
  user-reported.
- [ ] **28.6** Document every environment variable in one place, including the
  ones from `.env.example`, and reconcile the two files.
  Verify: a test asserting the two lists match.
- [ ] **28.7** Document the local run path for both halves: backend on 8080,
  frontend built and served, and the allowed localhost origins.
  Verify: the instructions work from a clean clone.
- [ ] **28.8** Document the deploy path for both halves, including the Pages
  build variable and the Cloud Run origin list.
  Verify: the instructions are complete.
- [ ] **28.9** Rename `home.css` to `app.css` now that it is the shared shell
  stylesheet, updating the build, every page reference, and every test.
  Verify: `npm test` and `npm run build` pass.
- [ ] **28.10** Add a test asserting no page contains a password or credential
  input, protecting the decision that removed the mock login.
  Verify: the new test passes and would fail if a login form were reintroduced.
- [ ] **28.11** Delete or archive `ROADMAP.md` once `tasks.md` is complete, so
  there is one source of truth.
  Verify: the decision is recorded in `handover.md`.
- [ ] **28.12** Run the full suite and build one final time, and record the
  result in `handover.md`, along with whatever the current git state is. Do not
  commit it — report the working-tree state to the user and let them decide.
  Verify: `scripts/check-all.ps1` exits 0.

---

# Deferred — deliberately not in this list

Recorded so these are visibly parked rather than forgotten. None of them should
be started without an explicit decision.

- **Any authentication or sign-in.** No login page, no credential field, no
  session, no JWT. If it is ever built, it must be a real auth backend first,
  and the phishing-interstitial history makes this a decision for you, not an
  implementation detail. The frontend's `actor` display is a configurable
  station label, not an identity.
- **React, Tailwind, or any framework migration.** The lorebook mentions them;
  the repo is vanilla UX4G and stays that way.
- **A custom or branded UX4G theme.** The default light theme is settled.
- **Hyperledger Fabric deployment.** The `Ledger` interface and Merkle proofs
  are the demoable part; a real Fabric network is a deployment project.
- **Training or shipping real ML weights.** Every model-dependent module ships
  as an interface plus a labelled heuristic stand-in.
- **Live watchlist, stolen-document, or ePassport/NFC connectors.** Mock
  connectors now; live integrations are a later phase with real data access
  agreements.

---

# Progress convention

Check a box only when its **Verify** line passes. When you check one, add a
short note on the same line saying how you verified it, for example:

```markdown
- [x] **1.6** Write `check_digit(text)` ... Verify: the new test passes.
      — verified by `pytest -k check_digit`, 3 passed
```

That way a future session can tell what was verified by a test and what was
only written. If the user happens to commit the work, you may add the commit
hash instead — but never create that commit yourself.
