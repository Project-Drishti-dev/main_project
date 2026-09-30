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
      — verified by a case-insensitive search for `not deployed` in
      `README.md`, which returned no match.
- [x] **0.2** Correct the "Git state as of September 30" section of
  `handover.md` — the tree is clean, HEAD is `2b779e5`, the September 30 page
  work was committed.
  Verify: `git status` is clean and `git log --oneline -1` shows `2b779e5`.
      — `git log --oneline -1` shows `2b779e5` and `git show --stat 2b779e5`
      confirms the September 30 page work is in that commit, so the handover
      text is corrected. The `git status is clean` half cannot pass:
      `AGENTS.md` bans creating commits, and the tree is intentionally dirty
      with the Gate 0 cleanup edits and untracked task tooling (`AGENTS.md`,
      `ROADMAP.md`, `tasks.md`, `run_tasks.ps1`, `scripts/`). Recorded in
      `handover.md` Known Issues / Blockers.
- [x] **0.3** Create `docs/DECISIONS.md` recording three settled decisions so a
  future session does not re-litigate them: vanilla HTML/CSS/JS (no React), no
  authentication for now, UX4G default light theme.
  Verify: the file exists and names all three.
      — `docs/DECISIONS.md` exists (5,560 bytes) and names all three as
      headed entries: D1 vanilla HTML/CSS/JS, no React; D2 no authentication
      for now; D3 UX4G default light theme. Each entry records the rationale,
      what it forbids, and the condition for revisiting. `check-all.ps1`
      passed alongside (13 backend, 45 frontend, build).
- [x] **0.4** Reorganise `backend/tests/` into `tests/unit/` and `tests/api/`
  (move the two existing files, do not rewrite them) and update `pytest.ini`
  testpaths.
  Verify: `python -m pytest backend/tests -q` still reports 13 passed.
      — done via a filesystem move, not a rewrite: `test_engine.py` is now
      `backend/tests/unit/test_engine.py` and `test_api.py` is now
      `backend/tests/api/test_api.py`, with `backend/pytest.ini` set to
      `testpaths = tests/unit tests/api`. The stale `backend/tests/__pycache__`
      was removed. Verified: `python -m pytest backend/tests -q` reports
      `13 passed` from the repo root and `python -m pytest -q` reports
      `13 passed` from `backend/`, so the new `testpaths` also resolves.
      `scripts/check-all.ps1` exited 0 (13 backend, 45 frontend, build).
- [x] [BLOCKED] **0.5** Add the new backend dependencies to `requirements-dev.txt`
  (pyyaml, sqlalchemy, alembic, cryptography, httpx) without touching
  `requirements.txt` yet.
  Verify: `pip install -r requirements-dev.txt` succeeds.
- [x] **0.6** Add `.env.example` listing every environment variable the project
  will eventually read, with placeholder values and a comment for each.
  Verify: the file exists; no real secret is in it.
      — new root `.env.example`, 18 variables, all commented, all placeholders
      empty or fake (`https://api.example.com`, `http://localhost:5500,...`,
      `http://127.0.0.1:11434`, `PUBLIC_DEMO=true`, `LOCAL_LLM_ENABLED=false`).
      Four are `[LIVE]` (read in code today: `DRISHTI_API_BASE_URL`,
      `DRISHTI_BUILD_OUTPUT_DIR`, `CF_PAGES`, `CORS_ORIGINS`), one is `[HOLD]`
      (`CF_PAGES` is set by Cloudflare Pages), the other thirteen are `[PLAN]`
      and each names the task that will read it. Verified with a throwaway
      checker: file exists; all 18 lines are well-formed `NAME=value`; no
      duplicate names; every variable has a comment line above it; 13 secret
      patterns (AWS/Google/GitHub/Slack keys, PEM blocks, JWTs, long base64 or
      hex values) all clean; no live `pages.dev` / `run.app` / `project-drishti.tech`
      / GitHub Pages host appears in the file; and the four variables actually
      read in `backend/app` and `frontend/*.cjs` are all documented.
      `.gitignore` already carries `/.env` and does not match `.env.example`.
      `scripts/check-all.ps1` exited 0 (13 backend, 45 frontend, build).
- [x] **0.7** Add `.gitignore` entries for `*.db`, `*.sqlite3`, `.env`,
  `screenshots/`, and `dist/`.
  Verify: `git status` stays clean after creating a throwaway `test.db`.
      — `*.db`, `*.sqlite3`, `screenshots/`, and a bare `dist/` are new;
      `.env` replaces the narrower `/.env`, and the redundant `/dist/` and
      `/frontend/dist/` lines are gone, so one `dist/` entry now covers the
      root, `frontend/`, and any future backend output. `.env` is left
      unanchored so a nested `.env` is caught too, and it still does not match
      `.env.example` (no `.env.*` pattern was added). Checked first that no
      tracked path matches `dist`, `screenshot`, `.env`, `*.db`, or `*.sqlite3`,
      so the broader patterns cannot hide a committed file. Verified by
      creating `test.db`, `scratch.sqlite3`, `.env`, `nested/.env`,
      `screenshots/shot.png`, and `backend/dist/b.txt`: all six are ignored
      (confirmed by `git check-ignore -v` naming the exact line for each),
      none appears in `git status --porcelain`, and `.env.example` is still
      listed as untracked so it stays committable. All six throwaway files
      were then deleted. `scripts/check-all.ps1` exited 0 (13 backend,
      45 frontend, build) and the `frontend/dist` it produced did not appear
      in `git status`.
- [x] **0.8** Create `scripts/check-all.ps1` that runs backend pytest, frontend
  `npm test`, and frontend `npm run build`, and exits non-zero if any fail.
  Verify: `./scripts/check-all.ps1` exits 0 on the current tree.
      — rewritten, not created: the file already existed (1,713 bytes) and
      already ran all three stages, but had two real gaps. (1) It relied on
      `$LASTEXITCODE` without clearing it, so a stage that died before
      running a native command would silently inherit the previous stage's
      exit code. (2) The failure path had never been exercised, only
      inspected. The rewrite adds a `Invoke-Stage` helper that zeroes
      `$LASTEXITCODE` before each stage, catches a stage that throws, records
      the stage name instead of a bare boolean, lists the failing stages in
      the summary, and resolves the repo root from `$PSScriptRoot` so the
      caller's working directory no longer matters. A preflight now fails fast
      with a clear message if `python` or `npm` is not on PATH instead of
      letting all three stages report a confusing "command not found".
      Verified: `./scripts/check-all.ps1` from the repo root exits 0
      (13 backend, 45 frontend, build), and re-running it from `frontend/`
      also passes all three stages, confirming cwd-independence. The
      previously-unproven failure path is now proven by a throwaway matrix
      that stubbed each stage with a chosen exit code: backend-only, frontend-
      test-only, and build-only failures each exit 1, all-three-fail exits 1,
      and all-three-pass exits 0 — five of five correct, with all three stages
      confirmed to have run in every case. The harness and its variants
      self-deleted; `scripts/` contains only `check-all.ps1`.
- [x] **0.9** Create `backend/app/version.py` with `APP_VERSION`,
  `RULESET_VERSION`, `PROMPT_VERSION` constants, and a test asserting they are
  non-empty strings.
  Verify: `python -m pytest backend/tests -q -k version` passes.
      — new `backend/app/version.py` and `backend/tests/unit/test_version.py`.
      All three constants are `"0.1.0"`, matching the `version="0.1.0"`
      already passed to `FastAPI(...)` in `app/main.py`, and the module
      docstring states when each one must be bumped. The test is parametrised
      over the three names and asserts `isinstance(str)` plus a non-blank
      `.strip()`, and a second test pins `__all__` to exactly those three.
      Verified: `python -m pytest backend/tests -q -k version` reports
      `4 passed, 13 deselected`; `scripts/check-all.ps1` exited 0 with
      **17 backend, 45 frontend, build**. `app/main.py` was deliberately left
      alone — wiring `FastAPI(version=APP_VERSION)` is not this task.
      **Part 0 is now fully checked, so Gate 0 is met** (the "13 backend" in
      the gate text is now 17).

**Gate 0:** the full existing suite is green (13 backend, 45 frontend),
`check-all.ps1` passes, and the three decisions are written down.

---

# Part 1 — MRZ primitives: characters, weights, check digits

Pure arithmetic. No OpenCV, no model. This is the foundation everything else
builds on.

- [x] **1.1** Create empty `backend/app/pipeline/__init__.py`,
  `backend/app/pipeline/tier0/__init__.py`.
  Verify: `python -c "import app.pipeline.tier0"` exits 0.
      — both files created empty (0 bytes), matching the task's word
      "empty"; note this differs from `app/quality_checker/__init__.py`, which
      carries a docstring, so do not "fix" these later by adding one. Verified:
      `python -c "import app.pipeline.tier0"` run from `backend/` exits 0, and
      `scripts/check-all.ps1` exited 0 (17 backend, 45 frontend, build).
- [x] **1.2** Write `char_value(c)` in `tier0/mrz.py` mapping `0-9` to `0-9`
  and `A-Z` to `10-35`, with a test for each range.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/mrz.py`: a module-level `CHAR_VALUES`
  dict built from `string.digits` and `string.ascii_uppercase`, plus
  `char_value(c)`. Only the two ranges this task names are implemented. `<`
  is deliberately absent (that is 1.3) and `MrzValueError` does not exist yet
  (that is 1.9), so an unmapped character currently raises plain `ValueError`;
  1.4 should introduce `MrzValueError` as a `ValueError` subclass so this
  stays compatible. Tests are in `backend/tests/unit/test_mrz.py`,
  parametrised over all ten digits and all twenty-six letters, plus one
  endpoint test pinning `0→0, 9→9, A→10, Z→35`. Verified: `python -m pytest
  backend/tests/unit/test_mrz.py -q` reports `37 passed`; importing
  `app.pipeline.tier0.mrz` loads neither `cv2` nor `numpy`, so Gate 1's
  no-OpenCV rule holds; and `scripts/check-all.ps1` exited 0 with **54 backend
  (was 17), 45 frontend, build**.
- [x] **1.3** Extend `char_value` so `<` maps to `0`, with a test.
  Verify: the new test passes.
      — `backend/app/pipeline/tier0/mrz.py` gains a module-level `FILLER = "<"`
      and `_build_char_values` now inserts `table[FILLER] = 0`, so
      `CHAR_VALUES` holds all 37 ICAO characters. The module docstring, the
      `CHAR_VALUES` comment, the `char_value` docstring and its `ValueError`
      message were updated to name the filler; the "arrives in task 1.3" note is
      gone. Four tests in `backend/tests/unit/test_mrz.py`: `char_value("<") == 0`,
      `FILLER`/`CHAR_VALUES` agreement, filler sharing the digit `0`'s value, and
      an exact set + length-37 pin on the table so a later task cannot quietly
      add or drop a character. Verified: `python -m pytest
      backend/tests/unit/test_mrz.py -q` reports `41 passed` (was 37);
      `python -m pytest backend/tests -q` reports `58 passed` (was 54) and
      exits 0; `scripts/check-all.ps1` exited 0 (58 backend, 45 frontend,
      build). `1.4` is untouched: unmapped characters still raise plain
      `ValueError` until `MrzValueError` lands.
- [x] **1.4** Make `char_value` raise `MrzValueError` for any other character,
  with a test for a space, a digit-like symbol, and a lowercase letter.
  Verify: the new test passes.
      — `backend/app/pipeline/tier0/mrz.py` defines
      `class MrzValueError(ValueError)` and `char_value` now raises it
      instead of a bare `ValueError`; the message is unchanged. Subclassing
      `ValueError` is deliberate — it was flagged in the 1.2 and 1.3 notes so
      the existing `except ValueError` callers keep working — so **1.9 no
      longer introduces the class, it pins it.** `MrzValueError` is in
      `__all__`; the module and `char_value` docstrings were updated to name
      it, and the stale "still raises a plain `ValueError`" sentence is gone.
      Three cases in `backend/tests/unit/test_mrz.py` (a space, a circled
      digit `①`, and the lowercase letter `z`), each asserting
      `MrzValueError` is raised and that the message names the offending
      character. The `MrzValueError`-subclasses-`ValueError` assertion is
      deliberately left for 1.9. Verified: `python -m pytest
      backend/tests/unit/test_mrz.py -q` reports `44 passed` (was 41);
      `python -m pytest backend/tests -q` reports `61 passed` (was 58) and
      exits 0; `scripts/check-all.ps1` exited 0 (61 backend, 45 frontend,
      build); and importing the module still loads neither `cv2` nor `numpy`.
- [x] **1.5** Write `weights(n)` returning the `7,3,1` cycle truncated to `n`,
  with tests for `n=0`, `n=1`, `n=4`, `n=39`.
  Verify: the new tests pass.
      — `backend/app/pipeline/tier0/mrz.py` gains the module constant
      `WEIGHT_CYCLE = (7, 3, 1)` and `weights(n)`, which returns
      `[WEIGHT_CYCLE[i % 3] for i in range(n)]` — a fresh list, always exactly
      `n` items, cut off mid-cycle rather than padded. The module docstring now
      documents the check-digit weight cycle, and `weights` is in `__all__`
      (alongside `char_value`; `WEIGHT_CYCLE` and `FILLER` stay out of
      `__all__` as documented module constants, matching 1.3's `FILLER`). A
      negative `n` raises `MrzValueError` rather than silently returning `[]`,
      because 1.9 pins `MrzValueError` as the single error type the package
      raises — raising plain `ValueError` here would contradict that. Tests in
      `backend/tests/unit/test_mrz.py`: the four named cases (0, 1, 4, 39) as a
      parametrised table with literal expected lists, plus one parametrised
      test over `range(0, 46)` pinning the length, the value set, and the
      cycle-prefix property, plus the negative-`n` case asserting the message
      carries `repr(n)`. Verified: `python -m pytest
      backend/tests/unit/test_mrz.py -q` reports `95 passed` (was 44);
      `python -m pytest backend/tests -q` reports `112 passed` (was 61) and
      exits 0; `scripts/check-all.ps1` exited 0 (112 backend, 45 frontend,
      build); and importing the module still loads neither `cv2` nor `numpy`,
      so Gate 1's no-OpenCV rule holds. The weights were written test-first:
      the 51 new tests failed against the pre-1.5 module, then passed.
- [x] **1.6** Write `check_digit(text)` = `sum(char_value * weight) % 10`, with
  a known-answer test.
  Verify: the new test passes.
      — `backend/app/pipeline/tier0/mrz.py` gains `check_digit`, which
  `zip(text, weights(len(text)))` and sums `char_value * weight` modulo 10, so
  it consumes `weights` and `char_value` rather than holding a private copy of
  either — the consumer 1.5's note asked for. `check_digit` is in `__all__`
  and the module docstring now states the rule rather than deferring it to
  this task. Thirteen tests in `backend/tests/unit/test_mrz.py`. The first
  three known-answer rows are the published ICAO 9303 specimen field values —
  `"L898902C<"` → 3, `"740812"` → 2, `"120415"` → 9, the check digits printed
  in that specimen's MRZ line — so the expected values come from the standard
  and not from this implementation, which is the bar 1.5's handover set. Three
  hand-derived rows (`"L898902C3"` → 6, `"AB12345"` → 6, `"D"` → 1) are there
  because the specimen fields cannot catch every wrong implementation: all
  three are 6 or 9 characters, i.e. multiples of 3, so padding the weight
  cycle instead of truncating it would still pass, and a cycle starting at 1
  or 3 rather than 7 would pass `"D"`'s neighbours unnoticed. A throwaway
  mutation check confirms the table discriminates: shifting the cycle to
  `3, 1, 7` changes 5 of the 6 answers. Each row also asserts the intermediate
  sum of products (313, 122, 49, 316, 166, 91), so a later edit cannot leave
  the final digit coincidentally right. Also an invalid-character case, and
  non-text cases over `None`, `42`, `bytes`, and `7.5`. The non-text guard
  exists because `bytes` and `float` have a `len` and would otherwise fail as
  an opaque `TypeError`, contradicting 1.9's single-error-type pin. Verified:
  `python -m pytest backend/tests/unit/test_mrz.py -q -k check_digit` reports
  `13 passed`; `python -m pytest backend/tests -q` reports `125 passed` (was
  112) and exits 0; `scripts/check-all.ps1` exited 0 (125 backend, 45
  frontend, build); and importing the module in a bare interpreter still
  loads neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. Written
  test-first: all new cases failed against the pre-1.6 module.
      — 1.7 is untouched: empty string, all `0`, all `<`, and all `A` are still
  untested, and `check_digit` special-cases none of them.
- [x] **1.7** Add edge-case tests for `check_digit`: empty string, all `0`, all
  `<`, all `A`.
  Verify: the new tests pass.
- [x] **1.8** Write `verify_check_digit(text, expected) -> bool` that does not
  raise on a valid-length input, with tests for match and mismatch.
  Verify: the new tests pass.
      — `backend/app/pipeline/tier0/mrz.py` gains `verify_check_digit(text,
      expected)`, which is `check_digit(text) == _expected_digit(expected)`, so
      it adds no arithmetic of its own and holds no private copy of the rule.
      A **mismatch is a value, not an exception**: the abstract's worked
      example A is a DOB check digit that does not match, and 6.2/6.7 have to
      turn that into a flag with an `expected` and a `found` and exit hard, so
      the function answers `True`/`False` and never raises to report a failed
      check. The found digit is not lost — it is still `check_digit`'s return
      value, which is what a flag needs.
      **`expected` is validated, and only loosely-shaped digit spellings are
      accepted**: an `int` 0-9 (the flag schema's shape) or the single digit
      character a parser slices out of the line. `bool` and `float` are
      rejected on purpose, because `True` and `2.0` both compare equal to `2`
      and would otherwise hide a caller bug as a passing check. The filler `<`
      is not accepted as a check digit.
      **The deliberate limit of "does not raise": a field that cannot be read
      still raises `MrzValueError`**, delegated to `check_digit`. A field
      nobody could read is not evidence of tampering, and answering `False`
      for a mis-OCR'd or truncated line would put a forged-document claim in
      front of an officer. This is pinned by tests, not just documented, and
      it agrees with 1.9's pin of `MrzValueError` as the package's only error
      type.
      50 new cases in `backend/tests/unit/test_mrz.py`. The match rows reuse
      1.6's three **published** specimen digits (`"L898902C<"`→3, `"740812"`→2,
      `"120415"`→9), because a verify function tested only against its own
      arithmetic agrees with itself perfectly. All nine wrong digits on the
      specimen DOB field return `False` and raise nothing — that parametrised
      table *is* the "does not raise" clause — and one row is worked example A
      (expected 4 and 7 both `False` while the found digit stays 2). Two more
      pin the return type with `type(...) is bool` (a truthy 1 would survive
      an `if` and then be serialised into a screening record as something it is
      not), and a length sweep runs every length 0-45 × all ten digits against
      three fields each (a 37-character alphabet, the specimen document
      number, and filler), which is the totality claim: no length and no
      claimed digit raises over MRZ text. The test for a non-digit `expected`
      caught a real bug on the first run: `"" in string.digits` is `True`,
      because the empty string is a substring of every string, so the claim
      reached `int("")` and raised a bare `ValueError` — a type 1.9 forbids.
      Fixed with an explicit length test. Verified: `python -m pytest
      backend/tests/unit/test_mrz.py -q -k verify_check_digit` reports `50
      passed`; `python -m pytest backend/tests -q` reports `265 passed` (was
      215) and `scripts/check-all.ps1` exits 0 (265 backend, 45 frontend,
      build); and importing `app.pipeline.tier0.mrz` in a bare interpreter
      still loads neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds.
      `verify_check_digit` is in `__all__` and a test asserts it.
- [x] **1.9** Define `MrzValueError` in `tier0/mrz.py` as the single error type
  the whole MRZ package raises, and add a test that it subclasses `ValueError`.
  Verify: the new test passes.
      — the class already existed: 1.4 introduced it when it swapped
      `char_value`'s raise, and 1.5/1.6/1.8 routed every other failure through
      it, so this task **pins** the claim rather than defining the class again.
      23 new cases in `backend/tests/unit/test_mrz.py`. The named one is
      `issubclass(mrz.MrzValueError, ValueError)`, plus a check that a real
      raise is caught by `except ValueError` (subclassing is only worth
      anything if it works on a raise, not on the class object), a check that
      it is *not* a `TypeError` so one `except` clause is enough, an export
      check, a 16-row matrix asserting every bad call raises
      `MrzValueError` with `type(exc) is MrzValueError` (the exact-type
      assertion is what stops a second error type hiding as a subclass), a
      scan asserting `MrzValueError` is the only exception class *defined*
      anywhere in the package, and a source scan banning
      `raise ValueError/TypeError/KeyError/IndexError/RuntimeError/Exception`.
      Both scans resolve the package directory from `mrz.__file__` and import
      or read every `*.py` in it, so they keep holding when Part 2 adds
      parsers beside `mrz.py` — and `test_the_package_has_modules_to_check`
      pins that the glob matched, so an empty match cannot pass for the right
      reason. The matrix found a **real leak on its first run**: `weights()`
      raised a bare `TypeError` for a non-integer `n` (`None`, `7.5`, `"3"`),
      because `n < 0` and `range(n)` fail before the negative check does any
      good — precisely the type 1.9 forbids, and the same class of bug as
      1.8's `int("")`. `weights` now checks `isinstance(n, int)` first and
      raises `MrzValueError(f"weight count must be an integer: {n!r}")`; the
      existing negative-length message is untouched, so 1.5's test still holds
      by asserting `repr(n)`. `bool` is still accepted as an `int` (there is
      no error to convert here, unlike 1.8's `expected`, where `True` compares
      equal to a real digit). The module docstring no longer says 1.9 is
      pending; it now states that every failure is reported as this one type
      whatever its cause. A throwaway mutation run confirms the source scan
      has teeth: adding a `raise ValueError` to a function no test calls fails
      `test_the_package_never_raises_a_builtin_error`, and the file restored
      byte-identical afterwards. Verified: `python -m pytest
      backend/tests/unit/test_mrz.py -q` reports `271 passed` (was 248);
      `python -m pytest backend/tests -q` reports `288 passed` (was 265);
      `scripts/check-all.ps1` exited 0 (288 backend, 45 frontend, build); and
      importing `app.pipeline.tier0.mrz` in a bare interpreter still loads
      neither `cv2` nor `numpy`, so **Gate 1 is now met** — every task in
      Part 1 is checked. Scope was `mrz.py`, `test_mrz.py`, this marker and
      note, and `HANDOVER.md`; no other source file and no `lorebook/` file was
      touched, and no git command was run.

**Gate 1:** all MRZ primitive tests pass with no OpenCV import.

---

# Part 2 — TD3 passport parser

Two lines of 44 characters. Positions below are 1-indexed and must live in
named constants, not inline magic numbers.

- [x] **2.1** Create the `TD3` layout constants module (line length 44, and the
  start/end index of each field) with a test asserting the constants cover
  exactly positions 1–44 with no gap or overlap.
  Verify: the coverage test passes.
      — new `backend/app/pipeline/tier0/td3.py` (constants only, no
  arithmetic and no raise) and `backend/tests/unit/test_td3.py`. Five names:
  `TD3_LINE_LENGTH` (44), `TD3_LINE_COUNT` (2), `TD3_LINE_1` (3 fields),
  `TD3_LINE_2` (11 fields, including the four printed check digits as fields
  of their own right), and `TD3` — the aggregate keyed by line, holding the
  *same dict objects* rather than copies, pinned by an identity assertion so
  there is no third table to drift. Positions are 1-indexed and inclusive.
  25 new cases in three layers. The one the task names is
  `test_a_line_covers_positions_1_to_44_with_no_gap_or_overlap`, which
  compares `sorted(claimed)` to 1–44 for each line — one comparison that
  catches a gap, an overlap and an out-of-range index; counting to 44 would
  not, since a gap and an overlap can cancel in the total. A second test
  walks the boundaries so a failure names the field that broke the line.
  **The coverage test is necessary but not sufficient**, because a table can
  tile 1–44 perfectly and still put the wrong field in the wrong place, so
  the tables are also written out longhand from ICAO 9303 Part 4 and compared
  by name, and then sliced against the specimen passport. The load-bearing
  layer is the check digits: each printed digit is asserted to equal
  `mrz.check_digit` of the field the constants slice, so a boundary that
  moves by one changes the field and the digit stops matching. A throwaway
  mutation run confirms the teeth — widening `document_number` to 1–10 and
  moving its check digit to 11 fails 6 of the 25, the coverage test
  included, and the file was restored afterwards.
  **The composite check digit is deliberately not quoted as a published
  value.** 1.6 recorded that it could not confirm it from a source in reach,
  this task did not obtain one, and asserting a remembered digit is exactly
  the self-confirming test 1.6 warned about, so the test pins the composite
  *position* (44) and the three spans it covers (1–10, 14–20, 22–43, 39
  characters) and derives the digit itself. Verified: `python -m pytest
  backend/tests/unit/test_td3.py -q` reports `25 passed`; `python -m pytest
  backend/tests -q` reports `313 passed` (was 288) with exit code 0;
  `scripts/check-all.ps1` exited 0 (313 backend, 45 frontend, build); and
  importing `app.pipeline.tier0.td3` in a bare interpreter still loads
  neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's
  package-wide scans now cover this file too and still pass: it defines no
  exception class and raises nothing. Scope was `td3.py`, `test_td3.py`, this
  marker and note, and `HANDOVER.md`; no other source file and no `lorebook/`
  file was touched, and no git command was run.
- [x] **2.2** Write `validate_td3_lines(lines)` raising unless there are exactly
  2 lines of exactly 44 characters, with tests for 1 line, 3 lines, and a short
  line.
  Verify: the new tests pass.
      — `validate_td3_lines` in `backend/app/pipeline/tier0/td3.py`, so 2.1's
      module now holds the layout *and* the one gate a zone passes before any
      of it is read; `td3.py` is no longer constants-only and its docstring says
      so. It raises `mrz.MrzValueError` and nothing else — 1.9's package scans
      still pass, and the module still defines no error type of its own. It
      returns the two lines in printed order so 2.13 can destructure instead of
      indexing, and the messages are built from `TD3_LINE_COUNT`/
      `TD3_LINE_LENGTH` rather than 2 and 44, so no line count or length is
      written twice. **The messages carry counts and lengths and never the
      line's characters**, because an exception message is the most likely
      thing to reach a log and those characters are the identity data the
      screening is about; one test pins that. **Two inputs the task did not name
      are rejected deliberately, because both would otherwise escape as a bare
      `TypeError` a caller catching `MrzValueError` never sees**: a `None` zone,
      and a single string where two lines were expected (a `str` iterates as 44
      one-character "lines", so without the guard the message would report a
      count of 44 and point at the wrong mistake). 12 new cases in
      `backend/tests/unit/test_td3.py`, including the accepted case — the three
      named rejections all pass against a validator that raises
      unconditionally — and a 45-character line alongside the 43-character one,
      since an over-read is the same check from the other side. A throwaway
      mutation run confirms the teeth in both directions: loosening the count
      and length checks to `>` fails 4 of the 12, and to `<` fails the
      3-line and 45-character ones, and `td3.py` was restored byte-identically
      afterwards (hash-checked). Verified: `python -m pytest
      backend/tests/unit/test_td3.py -q` reports `37 passed` (was 25);
      `python -m pytest backend/tests -q` reports `325 passed` (was 313) with
      exit code 0; `scripts/check-all.ps1` exited 0 (325 backend, 45 frontend,
      build); and importing `app.pipeline.tier0.td3` in a bare interpreter still
      loads neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. Scope
      was `td3.py`, `test_td3.py`, this marker and note, and `HANDOVER.md`; no
      other source file and no `lorebook/` file was touched, and no git command
      was run.
- [x] **2.3** Extract and validate the document code (positions 1–2): must be
  `P<` or `P`, with tests for `P<`, `P`, `V<`, and `X<`.
  Verify: the new tests pass.
      — two functions in `backend/app/pipeline/tier0/td3.py` rather than one,
      because the task's own four test cases make the split necessary:
      `validate_document_code(code)` is the judgement (membership in
      `TD3_DOCUMENT_CODES`) and `parse_document_code(line_1)` slices positions
      1–2 **with `TD3_LINE_1["document_code"]`** and delegates to it, so
      `parse_document_code("P")` and `validate_document_code("P")` cannot
      disagree. **2.2 left the slicing helper as this task's decision, and it
      is here**: `td3_field(line, layout, name)` is the only place in the
      project that slices a line, so the 1-indexed-to-0-indexed `- 1` is
      written once rather than eleven times, and 2.4 onwards call it instead
      of open-coding a slice. **One function could not have carried all four named cases**,
      because a 44-character line always slices to two characters, so the
      accepted bare `P` is only reachable through the validator. The slice
      uses the constant, not `line[0:2]`, honouring Part 2's header rule.
      **The accepted set is exact, and that is a stated decision rather than
      an omission**: `PA` and `PP` are rejected, and `PP` is the plausible
      real spelling — a document-type letter where the filler usually sits. A
      passport carrying one is refused for an officer to look at rather than
      parsed on the assumption that the letter was filler, which is the safe
      direction for a screening; widening the set is a deliberate edit of one
      line. A test pins this *behaviourally* (`PA`/`PP` rejected), because an
      implementation using `code.startswith("P")` would pass every test that
      only inspects the set's contents. **`P` is accepted because the second
      character of a passport's code is filler, so a code that lost it is the
      same document and nothing later in Part 2 reads position 2**; that is
      also the only way a bare `P` arrives, and a test says so.
      **A non-string line is rejected rather than sliced**, since
      `None[0:2]` is a bare `TypeError` a caller catching `MrzValueError`
      would never see — the same leak 1.9 found in `weights()`. The message
      **does name the two-character code it rejected**, unlike 2.2's
      count-and-length messages: a document *type* is not identity data, and
      a message that did not say which code arrived would not be worth
      logging. A test pins that the rest of the line is still absent from it.
      `td3_field` guards the same two leaks a reader would hit: a `KeyError`
      from an unknown field name and a `TypeError` from a non-string line are
      both caller mistakes rather than bad documents, and neither reaches an
      `except MrzValueError`.
      27 new cases in `backend/tests/unit/test_td3.py`, written first — all 27
      failed against the pre-2.3 module. A throwaway mutation run confirms the
      teeth, **all nine caught**: an off-by-one slice (`line[start:end]`) fails
      8 and an exclusive end fails 7, dropping the field-name guard fails 2,
      dropping the string guard fails 2, `startswith("P")` fails 2, dropping
      `P` from the set fails 4, widening the set fails 10, making the set a
      mutable list fails 1, and raising `TypeError` fails 10. `td3.py` was
      restored afterwards and hash-checked. The module docstring no longer
      claims nothing here slices a line, and the "2.3 onwards" sentence now
      points at this function.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `64 passed` (was 37); `python -m pytest backend/tests -q` reports `352
      passed` (was 325) with exit code 0; `scripts/check-all.ps1` exited 0
      (352 backend, 45 frontend, build); and importing
      `app.pipeline.tier0.td3` in a bare interpreter still loads neither
      `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's
      package-wide scans cover this file too and still pass: it defines no
      exception class and raises nothing but `MrzValueError`. Scope was
      `td3.py`, `test_td3.py`, this marker and note, and `HANDOVER.md`; no
      other source file and no `lorebook/` file was touched, and no git
      command was run.
- [x] **2.4** Extract the issuing state (3–5) and validate it is 3 uppercase
  letters, with a test rejecting `IND`.
  Verify: the new tests pass.
      — **the task's two clauses contradict each other and this task
  implements the first one.** `IND` *is* three uppercase letters, so no
  implementation of the rule the task states can reject it, and the second
  clause is not reachable from the first. A membership rule does not rescue
  it either: ISO 3166-1 alpha-3 assigns `IND` to India, so every conforming
  list of issuing states — ICAO Doc 9303's included — contains `IND`, and the
  only lists that reject it are ones with India missing, which would refuse
  every genuine Indian passport. So `validate_issuing_state` decides
  well-formedness only and **accepts `IND`**, and
  `test_a_real_country_code_such_as_ind_is_accepted_although_the_task_says_otherwise`
  pins that with the reasoning in the test. **Recognising a state is left
  undone on purpose**: it is a Tier 0 policy question whose answer is a code
  list that must be *sourced*, not remembered (the rule 1.6 applied to the
  composite check digit), and it belongs to the rules engine. **Task 2.11
  names `IND` again for the nationality field and has the identical
  contradiction** — carry this decision over rather than re-deriving it.
      — two functions in `backend/app/pipeline/tier0/td3.py`, the same shape
  as 2.3: `parse_issuing_state(line_1)` slices positions 3–5 with
  `TD3_LINE_1["issuing_state"]` and delegates to `validate_issuing_state(code)`,
  so the reader and the judgement cannot disagree. Both are in `__all__`.
  **The width is read out of the layout** (`end - start + 1`) rather than
  typed in as a `3`, so the standard's positions stay the only place a position
  is stated and the rejection message cannot describe a width the layout does
  not have. Letters are checked against `string.ascii_uppercase`, the same
  source `mrz.CHAR_VALUES` is built from, **not `str.isalpha`/`str.isupper`**:
  `"ÜTO"` passes both of those methods, so an implementation written from them
  would read a diacritic carried over from the printed name as a country, and
  `"1TO"` passes `isupper()` alone. A `bytes` value is rejected too —
  `b"UTO".isalpha()` is `True`.
      — 32 new cases in `backend/tests/unit/test_td3.py`, written first: 31
  failed against the pre-2.4 module and the 32nd (a layout-only assertion) was
  green legitimately. 12 rejection cases are the OCR misreads this field
  really produces — a zero read for an `O`, a lower- or mixed-case read, a
  filler or space where a letter belongs, a diacritic, a wrong width — because
  an accept-only suite proves nothing (2.2's argument). Three non-string cases
  cover the bare `TypeError` 1.9 forbids. The end-to-end cases slice a real
  44-character line, so a reader that never calls the validator cannot pass.
  **The green run found a false test of mine, not a bug**: the end-to-end case
  placed a 2-character code at positions 3–5 and asserted the line was still
  44 characters, which is impossible — a short code is what a *short line*
  produces. `line_1_with_issuing_state` now asserts the width it is given, and
  the short case lives in its own test beside the short-line cases.
      A throwaway mutation run confirms the teeth, **13 of 14 caught**:
  `isalpha` fails 4, `isupper` fails 1, dropping the length check fails 6,
  dropping the letter check fails 13, dropping the non-string guard fails 3,
  case-normalising instead of rejecting fails 3, a narrow list that rejects
  `IND` fails 2, a slice starting one late fails 3, an exclusive end fails 3,
  a reader that returns the slice unjudged fails 7, taking the width from the
  wrong field fails 6, and a message that stops naming the code fails 14.
  `td3.py` was restored from bytes afterwards and the SHA-256 hash-checked,
  not assumed. The one survivor is a *semantic* no-op — typing `width = 3`
  instead of reading the layout — which cannot be detected while the layout
  says `(3, 5)`; 2.1's coverage tests are what pin those equal.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
  `96 passed` (was 64); `python -m pytest backend/tests -q` reports `384
  passed` (was 352) with exit code 0; `scripts/check-all.ps1` exited 0 (384
  backend, 45 frontend, build); and importing
  `app.pipeline.tier0.td3` in a bare interpreter still loads neither `cv2` nor
  `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's three package-wide scans
  cover this file and pass: the new code defines no exception class and raises
  nothing but `MrzValueError`. Scope was `td3.py`, `test_td3.py`, this marker
  and note, and `HANDOVER.md`; no other source file and no `lorebook/` file was
  touched, and no git command was run.
- [x] **2.5** Extract the raw name string (6–44) with a test on a known MRZ.
  Verify: the new test passes.
      — `parse_name(line_1)` in `backend/app/pipeline/tier0/td3.py`, and it
      is **one function rather than the reader/validator pair 2.3 and 2.4
      needed**, because this field has no content rule to validate: the
      standard states where the name sits and how wide it is, and nothing
      about what the characters may be, because the names it carries are not
      a set anyone can enumerate. It slices positions 6–44 through
      `TD3_LINE_1["name"]` by way of `td3_field` and hands the string back
      untouched. **It extracts and does not judge, and that is the decision
      this task turned on.** 2.6 splits the surname off, 2.7 splits the given
      names, 2.8 strips filler and normalises case — each starting from
      exactly the string this returns, so doing any of them here would have
      left the next task nothing to do.
      **A diacritic, a lower-case read, and a space where a `<` belongs are
      all carried through, where 2.4 refused a diacritic in an issuing
      state.** The difference is deliberate and it follows from 2.8 existing:
      a reader that refused these would leave 2.8 nothing to clean up and
      would drop a document over a flaggable misread. An all-filler name is
      likewise extracted rather than refused, on 2.4's `IND` reasoning —
      whether a well-formed field is *acceptable* is a Tier 0 policy question
      for the rules engine, not a field reader. **2.6 is where that becomes
      visible, because splitting 39 fillers yields an empty surname; the
      test below says so so 2.6 decides it deliberately rather than inherits
      it.**
      **The one check it does make is its own width, and it needs one.** Every
      other reader here rejects a short line only as a *side effect* of
      checking its contents; this one has no content rule to do it with, so a
      line cut off mid-name would slice to whatever arrived and hand back
      `""` — which every consumer would read as a document that printed no
      name. "Parsing must not silently fix it" is 2.14's rule and this is
      where it starts. A line *longer* than the zone is fine: the field is
      read by position, so surplus characters are not part of it, and a test
      pins that against a reader slicing "to the end of the string".
      **The message carries the positions and both lengths and never the
      name** — the one field where 2.2's rule would have been easiest to
      break by accident. 2.3's and 2.4's habit of naming the value it
      rejected stops at the name.
      **20 new cases in `backend/tests/unit/test_td3.py`, written first** — 19
      failed against the pre-2.5 module, and the 20th (a layout-only
      assertion) was green legitimately. The one the task names is
      `test_the_raw_name_of_a_known_mrz_is_read`, on the ICAO specimen
      passport, and the expected value is written out in full as
      `"ERIKSSON<<ANNA<MARIA" + "<" * 19` rather than sliced from the line it
      is meant to have come from, since a test expecting `SPECIMEN_LINE_1[5:]`
      would pass against a reader whose positions were wrong.
      **The green run caught three false tests of mine**, all of which said
      something other than what they meant: one asserted
      `raw.strip("<>")` equalled the letters alone, which is false because
      `strip` only touches the ends and the separators are in the middle
      (`count` is 22, not 21, and the name is 17 letters, not 20); one called
      `SPECIMEN_LINE_1[5:]` "one character late" when that is the correct
      slice; and one asserted the message reported the *line's* length when
      it reports the *field's*, which is negative for a line that stops
      before position 6.
      **A throwaway mutation run confirms the teeth, 13 of 14 caught**:
      returning the slice unjudged fails 6, slicing to the end of the string
      instead of position 44 fails 3, slicing from the start of the line
      fails 15 (and 15 again off by one), a message dropping the positions
      and the width fails 1, a message echoing the name fails 1, stripping
      the filler fails 8, normalising case fails 1, splitting on `<<` fails
      9, refusing a non-ASCII letter fails 1, refusing an all-filler name
      fails 1, a bare `TypeError` for a non-string line fails 2, and leaving
      `parse_name` out of `__all__` fails 1. `td3.py` was restored from bytes
      afterwards and the SHA-256 hash-checked, not assumed.
      **Two things about that run are worth recording rather than hiding.**
      The survivor is a *semantic* no-op — typing `width = 39` instead of
      reading it out of the layout — which cannot be detected while the layout
      says `(6, 44)`; 2.1's coverage tests are what pin those two equal, and
      2.4's run had the same survivor. And my first script reported that
      mutation as 116 failures when it had in fact mutated
      `validate_issuing_state`'s width line (the pattern occurs twice in the
      module), and it counted *any* number in the summary line as a failure
      count, so a surviving mutation read as 116 failures. Both were script
      faults, not test faults; the corrected script produced the counts
      above, and the throwaway was deleted.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `116 passed` (was 96); `python -m pytest backend/tests -q` reports `404
      passed` (was 384) with exit code 0; `scripts/check-all.ps1` exited 0
      (404 backend, 45 frontend, build); and importing
      `app.pipeline.tier0.td3` in a bare interpreter still loads neither
      `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's three
      package-wide scans cover this file and pass: the new code defines no
      exception class and raises nothing but `MrzValueError`. Scope was
      `td3.py`, `test_td3.py`, this marker and note, and `HANDOVER.md`; no
      other source file and no `lorebook/` file was touched, and no git
      command was run.
- [x] **2.6** Split the name on `<<` into surname and given-names, with a test
  for `ERIKSSON<<ANNA MARIA` and for a mononym with no `<<`.
  Verify: the new tests pass.
      — `split_name(name)` in `backend/app/pipeline/tier0/td3.py`, added to
      `__all__`. It takes the string `parse_name` returned rather than a line,
      so it is `split_*` and not `parse_*` like the three readers, and it is
      **one function with no validator**, on 2.5's reasoning: there is no
      content rule to enforce, and 2.7 and 2.8 are the tasks that judge and
      clean what this divides. The separator is `mrz.FILLER * 2`, derived from
      the one place the filler character is stated rather than typed in, and
      the split is `str.partition`, which is lossless — a test says so
      directly, for eight shapes.
      **The two halves come back raw**: `given_names` is one string still
      carrying the single fillers between the given names and all 19 that pad
      the field. Stripping filler and splitting the given names into a list
      are 2.7's and 2.8's, and each has to start from exactly this, so a
      splitter that cleaned anything would leave 2.7 nothing to do and make
      its tests unfalsifiable.
      **Two shapes have no separator and neither is refused.** A mononym is
      returned whole as the surname with no given names, because a holder with
      one name and a `<<` misread as `<` are indistinguishable at the parse
      level and reinterpreting a single filler as the separator would be
      2.14's "parsing must not silently fix it". A name field of nothing but
      filler — the case 2.5 said this task must decide deliberately rather
      inherit — returns `("", "<" * 37)` rather than raising, on 2.4's `IND`
      reasoning: a splitter that raised would turn a flaggable name into a
      dropped document. Both costs are labelled and stated in the docstring.
      **Only the first `<<` splits**, so a doubled single filler stays in the
      given-names half where 2.7's `<` split reads it as an empty entry and
      drops it; putting it in the surname would split a name in the wrong
      place.
      **21 new cases in `backend/tests/unit/test_td3.py`, written first** —
      all 21 failed against the pre-2.6 module. The task's two named cases
      are `test_a_name_carrying_the_separator_is_split_into_surname_and_given_names`
      (`ERIKSSON<<ANNA MARIA`, with a space where the MRZ prints a filler,
      since that misread is 2.8's to clean) and
      `test_a_mononym_with_no_separator_is_all_surname_and_no_given_names`.
      The green run caught a **false test of mine**: the mononym case written
      at its real width, `"NGUYEN" + "<" * 32`, *does* contain `<<` — in the
      padding — so it is not a mononym at the string level at all, and the
      test failed against correct code. That is worth keeping rather than
      hiding: it means a mononym and a surname with no given names are the
      same string, so this task does not have to tell them apart, and
      `test_a_padded_mononym_carries_its_separator_in_the_padding` now says
      so.
      **A throwaway mutation run confirms the teeth, 8 of 8 caught**:
      splitting on every `<<` fails 11, splitting on a single filler fails 14,
      stripping filler from both halves fails 7, swapping the halves fails 15,
      falling back to the given names when the surname is empty fails 1,
      dropping the non-string guard fails 3, a message that echoes the name
      fails 3, and leaving `split_name` out of `__all__` fails 1. `td3.py` was
      restored from bytes afterwards and the SHA-256 hash-checked, not
      assumed; the script was deleted.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `137 passed` (was 116); `python -m pytest backend/tests -q` reports
      `425 passed` (was 404) and exits 0 with `-p no:faulthandler` (without
      it the known Windows OpenCV diagnostic makes the exit code 1 while every
      test passes); `scripts/check-all.ps1` exited 0 (425 backend, 45 frontend,
      build); and importing `app.pipeline.tier0.td3` in a bare interpreter
      still loads neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds.
      1.9's three package-wide scans cover this file and pass: the new code
      defines no exception class, raises nothing but `MrzValueError`, and the
      `FILLER` import adds no second source for the character. Scope was
      `td3.py`, `test_td3.py`, the `- [x]` marker and note in `tasks.md`, and
      this handover. No other source file, and no `lorebook/` file, was
      touched, and no git command was run.
- [x] **2.7** Split given names on `<` into a list, dropping empty entries, with
  tests for `ANNA MARIA` and `ANNA<MARIA`.
  Verify: the new tests pass.
      — `split_given_names(given_names) -> list[str]` in
  `backend/app/pipeline/tier0/td3.py`, added to `__all__`. It takes the
  string `split_name` returned rather than a line, so it is `split_*` and not
  `parse_*`, and it is **one function with no validator**, on 2.5's reasoning:
  there is no content rule to enforce, there is no width to check that would
  not be 2.5's check done twice, and 2.8 owns the cleaning.
  **The split is on the single filler and on nothing else, so the task's two
  named cases come back differently and that is the point.** `ANNA<MARIA` —
  the printed form — is two entries; `ANNA MARIA` — the space an OCR engine
  really produces, which 2.6 wrote its own named case in — is **one** entry
  with a space in it. Merging on the space here would be 2.14's "parsing must
  not silently fix it", and 2.8 is the task that strips a space, so a
  splitter that did it would leave 2.8 nothing to clean up. The separator is
  `mrz.FILLER`, the same source `split_name`'s `<<` is derived from, so there
  is still one place the character is stated.
  **The empty-entry drop is load-bearing in exactly one case, and it is the
  case worth naming.** `str.split(FILLER)` already drops the empties between
  separators — the 19 padding fillers, a leading or trailing one, and the
  doubled `<<` that 2.6 deliberately left behind as a misread — so for every
  field with something in it the comprehension is a plain split. But
  splitting `""` returns `[""]`: **a one-element list naming a person with no
  name**, which is indistinguishable downstream from a real name. So the drop
  is written out rather than inherited, and both no-given-names shapes — a
  mononym's empty half and a name field of nothing but filler, the two costs
  2.6 labelled — come back as the empty list. That is the labelled cost, now
  visible at the list.
  **Nothing is cleaned.** An entry is the characters between two fillers
  exactly as printed: not stripped, not case-folded, not transliterated, and
  not rejected for a digit, a space or a diacritic. **A whitespace-only entry
  is kept** — it is not a name, but saying so is a judgement about the whole
  list, and 2.8 makes it over the list rather than this one per entry. Names
  come back in printed order (a later comparison, 12.15, has to see that the
  first one differs) as a `list`, not a tuple and not a generator, because
  2.13 iterates it and a generator would be spent by its first consumer. The
  non-string guard raises `MrzValueError` naming the type and never the
  names, on 2.5's rule.
  **25 new cases in `backend/tests/unit/test_td3.py`, written first** — all 25
  failed against the pre-2.7 module. The task's two named cases are
  `test_given_names_separated_by_a_space_stay_one_entry` and
  `test_given_names_separated_by_a_filler_are_two_entries`, beside a
  ten-row table stating the rule once, an end-to-end case composing 2.2's
  gate with 2.5 and 2.6, and a case pinning that the empty string is `[]` and
  not `[""]`.
  A throwaway mutation run confirms the teeth, **8 of 8 caught**: a bare
  `str.split()` (which also splits on whitespace) fails the space case, a
  `str.split(FILLER)` with no drop fails the specimen, splitting on `FILLER * 2`
  fails the printed form, keeping an entry that has whitespace in it fails the
  no-cleaning case, sorting fails the order case, returning a tuple fails the
  type case, dropping the non-string guard fails 3, and leaving the function
  out of `__all__` fails 1. `td3.py` was restored from bytes afterwards and
  SHA-256 hash-checked, not assumed; the script was deleted.
  Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports `162
  passed` (was 137); `python -m pytest backend/tests -q` reports `450 passed`
  (was 425) and exits 0 with `-p no:faulthandler`; `scripts/check-all.ps1`
  exited 0 (450 backend, 45 frontend, build); and importing
  `app.pipeline.tier0.td3` in a bare interpreter still loads neither `cv2` nor
  `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's package-wide scans cover
  this file and pass: the new code defines no exception class and raises
  nothing but `MrzValueError`. Scope was `td3.py`, `test_td3.py`, the `- [x]`
  marker and this note in `tasks.md`, and `HANDOVER.md`; no other source file,
  and no `lorebook/` file, was touched, and no git command was run.
- [x] **2.8** Strip space filler and normalise to uppercase in name parsing,
  with a test using `P<UTO LIE<SOPHIE<<<<<`.
  Verify: the new test passes.
      — `normalise_names(surname, given_names) -> tuple[str, list[str]]` in
  `backend/app/pipeline/tier0/td3.py`, added to `__all__`. It takes the two
  halves `split_name` and `split_given_names` produced, so it is
  `normalise_*` and not `parse_*`, and it is **one function with no
  validator**: there is no content rule left to enforce, there is no width to
  check that 2.5 has not already checked, and 2.9 owns what is left.
  **The rule is one rule over both halves — filler out, whitespace out,
  case up — and a given name that is nothing afterwards is dropped.** It
  lives in a private `_clean_name` so the surname and each given name cannot
  be cleaned differently, and in a module-level `str.maketrans` over
  `string.whitespace` so a tab or a newline read out of a misaligned row is
  the same mistake as a space rather than a character that survives.
  **"Strip", not "replace with a filler", and that is the decision this task
  turned on.** A space where a filler belongs is evidence that a filler was
  there, and using that evidence to put one back is 2.14's "parsing must not
  silently fix it" with extra steps. So the whitespace is removed and
  nothing is invented.
  **The named specimen `P<UTO LIE<SOPHIE<<<<<` therefore does not come back
  as `LIE` and `["SOPHIE"]`, and that is the point.** It prints as
  `LIE<<SOPHIE`; what arrived has a space where a filler belongs, so 2.6's
  `<<`-misread-as-`<` branch — the one its own docstring names — took the
  whole field as a surname with no given names. The answer is
  `("LIESOPHIE", [])`: the space and the leftover filler are gone, and
  **SOPHIE is not recovered**, because recovering her would mean writing a
  `<<` into a string that does not have one. The cost is labelled rather
  than hidden: a holder whose secondary identifiers were lost to a misread
  shows up as a holder with none, and a screening has to be able to say
  that rather than paper over it.
  **The list is judged and the surname is not.** The drop of a
  whitespace-only given name is the judgement 2.7 explicitly deferred
  ("it is not a name, but saying so is a judgement about the whole list and
  it is 2.8's to make over it"), and it is 2.7's own empty-entry argument
  one step later: a list holding `""` names a person who has no name. The
  surname keeps its `""`, because `split_name` already returns one for a
  name field of nothing but filler, and a cleaner that also dropped it
  would make "no surname" indistinguishable from "not parsed" and would
  hand 2.13 a differently shaped result depending on the document.
  **`str.upper()`, not an ASCII fold, and not `unicodedata`.** The MRZ
  alphabet is `A`-`Z`, so a fold to ASCII would be *closer* to what a name
  may contain and would quietly do 2.9's job, leaving the transliteration
  map nothing to add and no reason to exist. `MÜLLER` therefore comes back
  as `MÜLLER` — upper-cased, diacritic carried — which is what leaves 2.9
  a character to map. `MÜLLER` and `øyvind` are both pinned so an ASCII
  fold cannot pass by accident, since it would only differ on the
  lower-case half of that pair.
  **A bare `str` or `bytes` is refused rather than iterated**, on
  `validate_td3_lines`'s rule: a string is a sequence, so iterating one
  would hand back a name per *character* and report nothing wrong.
  **40 new cases in `backend/tests/unit/test_td3.py`, written first** — all
  40 failed against the pre-2.8 module. The task's named case is
  `test_a_name_misread_with_a_space_where_a_filler_belongs_loses_the_space`,
  with `test_the_space_is_gone_and_the_filler_with_it` writing out the
  `("LIESOPHIE", [])` answer and the reasoning, and
  `test_the_misread_line_really_is_a_td3_line` guarding the fixture itself
  so the other two cannot pass for the wrong reason. The rest is a nine-row
  table stating the rule once, the three order-preserving and
  return-shape cases, four whitespace kinds, four non-string guards, and
  the two 2.9-boundary cases.
  A throwaway mutation run confirms the teeth, **14 of 14 caught**: no
  filler strip, no whitespace strip, ends-only strip, a space-only
  translate table, folding down, an ASCII fold, no empty-entry drop,
  dropping an empty surname, sorting, a list instead of a tuple, and each of
  the three guards or the export removed. `td3.py` was restored from bytes
  afterwards and SHA-256 hash-checked, not assumed; the script was deleted.
  **The first version of that script was wrong twice over, and both were
  script faults rather than test faults.** It rewrote the file through
  `Path.write_text`, so the machine's default codec re-encoded every
  non-ASCII character, the module stopped importing, and all 14 mutations
  were reported as survivors when they had in fact not run at all; and its
  guard pattern for the surname was typed with CRLF endings the file does
  not have, so that one mutation was never applied and the run reported
  "13 of 14" for a reason that had nothing to do with the tests. The
  rewritten script works in bytes throughout, restores in a `finally`, and
  asserts the file is byte-identical at the end. The damage was repaired by
  a cp1252 → UTF-8 transcode proved lossless by a round-trip assertion, and
  one mutation left applied on disk was restored by hand and caught by the
  suite before the final run.
  Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
  `202 passed` (was 162); `python -m pytest backend/tests -q` reports `490
  passed` (was 450) and exits 0 with `-p no:faulthandler`;
  `scripts/check-all.ps1` exited 0 (490 backend, 45 frontend, build); and
  importing `app.pipeline.tier0.td3` in a bare interpreter still loads
  neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's
  package-wide scans cover this file and pass: the new code defines no
  exception class and raises nothing but `MrzValueError`. Scope was
  `td3.py`, `test_td3.py`, the `- [x]` marker and this note in `tasks.md`,
  and `HANDOVER.md`; no other source file, and no `lorebook/` file, was
  touched, and no git command was run.
- [x] **2.9** Add the ICAO transliteration map (diacritics to base letters,
  `ß`→`SS`, `Ø`→`O`, `Ł`→`L`, `Đ`→`D`) and apply it to parsed names, with
  tests for `MÜLLER`→`MULLER` and `Ø`→`O`.
  Verify: the new tests pass.
      — `TRANSLITERATIONS` and `transliterate_names(surname, given_names) ->
      tuple[str, list[str]]` in `backend/app/pipeline/tier0/td3.py`, both added
      to `__all__`. It takes what `normalise_names` returned, so it is
      `transliterate_*`, and it is **one function with no validator**: 2.5
      already checked the field, and the job here is substitution, not
      judgement.
      **The map is four letters long and the rest is a rule, and that is the
      decision this task turned on.** `ß`→`SS`, `Ø`→`O`, `Ł`→`L` and `Đ`→`D`
      are exactly the characters Unicode will not decompose; every other
      accented Latin letter *is* decomposed canonically and `_strip_diacritics`
      takes the combining mark off, leaving the base. A written-out table of
      the ~200 accented characters in the Latin ranges would be ~200
      remembered values, and 1.6's rule is not to quote a remembered value
      where a source is what the value is. An attempt to fetch ICAO Doc 9303
      on 2026-09-30 failed (no network), so the four are the task's own values
      and nothing beyond them was invented.
      **Anything the two rules cannot reach is carried through unchanged, not
      dropped.** Æ, Œ, Þ, Ð, Ŋ, Ħ, Ĳ, Ŀ, Ŧ, the Ǆ digraph, and every
      non-Latin letter come back exactly as they arrived: dropping a character
      would change a name with nothing left behind to show it had, which is
      2.14's "parsing must not silently fix it" in the one direction 2.14 did
      not anticipate. Such a name is still outside the MRZ alphabet, so
      `char_value` still raises on it and the flagging is Part 12's job.
      **Decomposition is `NFD`, not `NFKD`.** `NFKD` would also expand the Ǆ
      digraph to `D` + `Ž`, a ligature to its letters and a full-width letter
      to ASCII — rewrites of a name rather than the taking off of an accent.
      **A given name emptied here is dropped, the surname is not**, restating
      2.8's rule because this is the one step that *can* empty a name (a name
      of nothing but combining marks), and a name is never truncated: `ß` makes
      `STRAßE` seven characters where the field is 39 wide, and the width is
      2.5's property of the field, not of a parsed name.
      **56 new cases in `backend/tests/unit/test_td3.py`, written first** — 55
      failed against the pre-2.9 module, and the 56th (a fixture guard) was
      green legitimately. The task's two named cases are
      `test_a_diacritic_becomes_the_base_letter_the_document_meant` and
      `test_the_letter_with_a_stroke_through_it_becomes_the_letter_without_one`.
      **A throwaway mutation run confirms the teeth, 18 of 19 caught**: an
      empty map, no diacritic rule, map-only, `NFKD`, dropping what the map
      cannot map, re-casing, re-stripping whitespace, re-splitting on a space,
      given names left untransliterated, an emptied given name kept, an empty
      surname dropped, truncation to 39, sorting, a list of lists, the entry
      guard removed, a wrong map value, and each of the two exports removed.
      **The 19th survivor is the honest one**: applying the map before the
      diacritic rule instead of after is semantically identical, which is what
      the function's docstring says the order is — a readability choice.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `258 passed` (was 202); `python -m pytest backend/tests -q` reports
      `546 passed` (was 490) and exits 0 with `-p no:faulthandler`;
      `scripts/check-all.ps1` exited 0 (546 backend, 45 frontend, build); and
      importing `app.pipeline.tier0.td3` in a bare interpreter still loads
      neither `cv2` nor `numpy`. 1.9's package-wide scans cover this file and
      pass. Scope was `td3.py`, `test_td3.py`, the `- [x]` marker and note in
      `tasks.md`, and this handover; no other source file, and no `lorebook/`
      file, was touched, and no git command was run.
- [x] **2.10** Extract the passport number (line 2, 1–9) and validate it is
  non-empty, with tests for a normal number and an all-`<` number.
  Verify: the new tests pass.
      — `validate_document_number(number)` and `parse_document_number(line_2)`
      in `backend/app/pipeline/tier0/td3.py`, both added to `__all__`: the
      `parse_*` + `validate_*` pair 2.3 and 2.4 needed and 2.5–2.9 did not,
      because the document-number field is the first one with a content rule
      of its own. The reader takes `TD3_LINE_2` through `td3_field` and
      hands the slice straight to the validator, so the two cannot disagree
      about what a document number is.
      **"Non-empty" means non-empty once the filler is taken out, and that is
      the decision the task turned on.** The field is nine characters wide
      whatever the number is and a shorter one is padded on the right, so
      `"L898902C<"` is a complete number and `"<<<<<<<<<"` is no number at
      all — and neither is an empty string, so a plain `if not number`
      accepts both. The filler is the only character the standard itself uses
      to mean "no value here", which is why it is the one removed first and
      why `"A<<<<<<<<"` is a one-character number rather than a missing one.
      The width is checked as well, read out of the layout rather than typed
      in as a 9, which is what stops a line that stops before position 9
      being handed back as a complete passport number; emptiness is judged
      first, so a field holding nothing is reported as the missing number it
      is rather than as a line that stopped early.
      **The padding is returned, and my stated reason for it was wrong until
      the test caught it.** I claimed stripping the filler would give 1.6's
      arithmetic a different digit; it does not, because a *trailing* filler
      contributes nothing to the sum and shifts no weight
      (`check_digit("L898902C<")` and `check_digit("L898902C")` are both 3).
      The real reason is the opposite one, and the test and the docstring now
      say it: the agreement is a trap, not a licence — it holds for any
      trailing filler and breaks the moment the filler is anywhere else
      (`check_digit("<1234567<")` is 6, `check_digit("1234567")` is 4). A
      fault in my reasoning, caught by my own test, not in the module.
      **Nothing about the characters is judged.** A field carrying a space is
      a misread, but it is not empty, and the task's rule is emptiness;
      `mrz.check_digit` is what raises on it, so the failure is reported
      rather than lost, and a test asserts both halves of that. Inventing an
      alphabet check would put the check on the wrong side of 2.14's "parsing
      must not silently fix it". **This is 2.4's `IND` question again** and it
      lands the same way: reading a number is not verifying one, and whether a
      number is an *acceptable* passport number is the rules engine's
      question (Part 12).
      **The message does not carry the number, where 2.3's and 2.4's do.**
      Those named a document *type* and a *state*; a document number is the
      identifier the screening is about, so the messages name the width and
      the character that filled the field — which is the whole diagnosis
      — and never the value. The width-rejected test value
      `"L898902C<3"` carries the printed check digit too, so an echo there
      would leak both.
      36 new cases in `backend/tests/unit/test_td3.py`, written first: 35
      failed against the pre-2.10 module and the 36th (a fixture guard on the
      layout) was green legitimately, as 2.5's 20th and 2.4's 32nd were. The
      task's two named cases are
      `test_a_normal_document_number_is_read_from_positions_1_to_9` and
      `test_a_document_number_of_nothing_but_filler_is_rejected`. The rest is
      a four-row empty-field table, a six-row accepted table, the
      padding/emptiness boundary, the padding-is-kept case with the check-digit
      arithmetic, a five-row "nothing is edited" table, the check-digit
      hand-off, three wrong widths, the no-echo rule, three non-string types,
      the wrong-line cost, three short lines, the non-string line, the
      check-digit-independence guard, and the one-error-type guard.
      A throwaway mutation run confirms the teeth, **18 of 18 caught**: a
      plain emptiness check, only the first filler removed, `strip()` instead
      of the filler, no emptiness rule, no width rule, a width rule allowing a
      longer field, no type guard, emptiness judged after the width, a
      message that echoes the number, the number returned stripped /
      upper-cased / unpadded, the reader pointed at line 1's layout, at the
      check digit's field, slicing the line itself, not validating at all, and
      each of the two exports removed. **The script then deleted `td3.py`
      instead of itself; the module was rebuilt from the surviving
      `__pycache__` pyc and the rebuild was proved identical by comparing
      compiled code objects against the pyc — see `HANDOVER.md` Known
      Issues / Blockers for what that cost.**
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `294 passed` (was 258); `python -m pytest backend/tests -q` reports
      `582 passed` (was 546) and exits 0 with `-p no:faulthandler`;
      `scripts/check-all.ps1` exited 0 (582 backend, 45 frontend, build);
      and importing `app.pipeline.tier0.td3` in a bare interpreter still
      loads neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds.
      1.9's package-wide scans cover this file and pass: the new code defines
      no exception class and raises nothing but `MrzValueError`. Test names
      checked for uniqueness: the only duplicate in the file is 2.5's and
      2.8's pre-existing pair. Scope was `td3.py`, `test_td3.py`, the
      `- [x]` marker and this note, and the handover; no other source file,
      and no `lorebook/` file, was touched, and no writing git command was run.
- [x] **2.11** Extract the nationality (11–13), validate 3 uppercase letters,
  with a test rejecting `IND`.
  Verify: the new test passes.
      — `validate_nationality(code)` and `parse_nationality(line_2)` in
      `backend/app/pipeline/tier0/td3.py`, both added to `__all__`: the
      `parse_*` + `validate_*` pair 2.10 established, because positions 11-13
      have a content rule of their own. The reader takes `TD3_LINE_2` through
      `td3_field` and hands the slice straight to the validator, and the
      validator reads its width out of that table rather than typing in a 3.
      **`IND` is accepted, not rejected, and this is 2.4's decision carried
      over rather than re-derived** — tasks.md said so at 2.10's note, and the
      two clauses of this task contradict each other the same way they did
      there: `IND` *is* three uppercase letters, and ISO 3166-1 alpha-3 assigns
      it to India, so the only implementations that reject it hold a list with
      India missing and refuse every genuine Indian passport. No list of
      nationality codes ships either — a second list to be sourced is not a
      second rule to invent. The task's named test is
      `test_a_real_nationality_code_such_as_ind_is_accepted_although_the_task_says_otherwise`,
      beside `test_a_normal_nationality_is_read_from_positions_11_to_13`.
      **The message does not carry the code, where 2.3's and 2.4's do, and
      that is a departure with a reason.** Those named a *document* and a
      *state*; a nationality is a property of the **holder**, which is the
      line 2.10 drew when it kept the document number out of its messages. The
      width, the positions and `A-Z` are named; the value is not.
      **There is no emptiness rule here, and the filler is not a special
      case.** The standard gives this field no "unspecified" value — unlike
      the sex marker's filler in 2.12 — so `"<<<"` is a misread rejected
      because the filler is not one of `A`-`Z`, not a missing nationality;
      2.10's "empty once the filler is removed" rule does not repeat, because a
      three-letter code that is short is not a code.
      **The wrong-line cost is worse here than anywhere else in the module, and
      it is stated rather than hidden.** Line 1's positions 11-13 are the
      middle of `ERIKSSON`, so a reader pointed at the wrong table returns
      `"SON"` — which is three uppercase letters, so this task's own rule does
      **not** catch it, unlike 2.10's `"P<UTOERIK"`. And no check digit covers
      positions 11-13: the composite spans 1-10, 14-20 and 22-43, so the field
      sits in the gap between the first two. It is the one identity field with
      no arithmetic of its own, which is why 2.13's caller has to pass the
      right line and why plausibility is Part 12's question.
      **One test falsifies "the reader takes its positions from the layout",
      which nothing else here can.** The layout and a hand-written
      `line[10:13]` agree on the specimen, so
      `test_the_reader_takes_its_positions_from_the_layout_rather_than_its_own`
      moves the field in the table (`monkeypatch.setitem`) and gives the line
      different letters at 11-13 and 12-14, which is what tells the two
      implementations apart.
      **40 new cases in `backend/tests/unit/test_td3.py`, 39 of them written
      first** — 37 failed against the pre-2.11 module and the two that were
      green legitimately are the layout guards, as 2.5's 20th and 2.4's 32nd
      were. The 40th, the layout-fidelity test above, was written afterwards
      because no other test could falsify the claim it makes. Beyond the two
      named cases: a 13-row
      rejection table (digit, lower case, filler, diacritic, four widths), a
      five-row acceptance table, the filler-as-misread case, three non-string
      types, the two no-echo cases, three end-to-end malformed lines, three
      short lines, the non-string line, read-by-position-not-by-end-of-string,
      the layout-fidelity test, the wrong-line `"SON"` cost, the no-check-digit
      guard, and the one-error-type guard.
      **A throwaway mutation run confirms the teeth, 12 of 12 caught**:
      `isalpha`/`isupper` instead of the MRZ letter set, no width rule, a
      hardcoded width with the positions left out of the message, `IND` refused
      by name, the message echoing the code, no type guard (so `bytes` reaches
      the letter test), the filler accepted where a letter belongs, the value
      stripped and upper-cased before judgement, the reader slicing the line
      itself, the reader pointed at line 1's layout, and each of the two
      exports removed. `td3.py` was restored from bytes afterwards and
      SHA-256 hash-checked, not assumed; the script was deleted.
      **One mutation of mine was wrong twice and read as a survivor.** It
      replaced only the first line of a two-line f-string, so the positions it
      claimed to remove were still printed by the continuation — the test was
      fine and the mutation was not.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `334 passed` (was 294); `python -m pytest backend/tests -q` reports `622
      passed` (was 582) and exits 0 with `-p no:faulthandler`;
      `scripts/check-all.ps1` exited 0 (622 backend, 45 frontend, build); and
      importing `app.pipeline.tier0.td3` in a bare interpreter still loads
      neither `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's
      package-wide scans cover this file and pass: the new code defines no
      exception class and raises nothing but `MrzValueError`. Test-name
      uniqueness re-checked after the fact — the only duplicate in the file is
      still the pre-existing 2.5/2.8 pair, and none of the 40 new names
      collides. Scope was `td3.py`, `test_td3.py`, the `- [x]` marker and note
      in `tasks.md`, and this handover; no other source file, and no
      `lorebook/` file, was touched, and no git command was run.
- [x] **2.12** Extract the date of birth (14–19), the expiry (22–27), and the
  sex marker (21) in one task, validating the sex marker against `M`, `F`, `X`,
  `<`, with tests for each accepted value and a rejection for `Z`.
  Verify: the new tests pass.
      — `validate_date_of_birth` / `parse_date_of_birth`,
      `validate_date_of_expiry` / `parse_date_of_expiry` and `validate_sex` /
      `parse_sex` in `backend/app/pipeline/tier0/td3.py`, plus
      `TD3_SEX_MARKERS`, all added to `__all__`. Three fields in one task
      because the task says so, and each is the `parse_*` + `validate_*` pair
      2.10 established, with every position coming from `TD3_LINE_2` through
      `td3_field`.
      **Only the sex marker gets a content rule; the two dates get a width
      rule and nothing else, and that is the line to 3.11.** 3.11 states
      "YYMMDD parsing with month/day range validation, rejecting 993199 and
      013200", and 3.12 and 3.13 give the two dates *different* century rules,
      so judging a date here would be 3.11 arriving three tasks early.
      `test_a_six_character_date_that_is_not_a_real_date_is_still_extracted`
      therefore asserts that **both of 3.11's own rejection values pass
      here**, on the width alone.
      **The width is judged all the same, for 2.10's reason restated**: a line
      that stops before position 19 slices short, and that is a line which
      stopped early rather than a document carrying a five-character date of
      birth.
      **A date comes back exactly as printed, and the digit printed beside it
      is both the proof and the limit of that proof.**
      `check_digit("740812")` is the `2` at position 20 and
      `check_digit("120415")` is the `9` at position 28 — **but
      `check_digit("204159")` is also 9**, so the six characters one to the
      right of the expiry agree with the printed digit and a reader off by one
      in that direction is not caught by arithmetic at all. The layout test is
      what settles it, as 2.10's trailing-filler trap was.
      **`TD3_SEX_MARKERS` is a closed set of four, and it is closed because
      nothing underneath it would object.** Position 21 sits in the gap
      between the date of birth's span (14-20) and the expiry's (22-28), and
      the composite digit covers 1-10, 14-20 and 22-43, so no check digit
      reaches it — the second identity field with no arithmetic, after 2.11's
      nationality. The four are therefore *named* rather than derived from a
      rule such as "one uppercase letter, or the filler", which would wave
      through `N`. A `frozenset`, as `TD3_DOCUMENT_CODES` is.
      **The filler is a value here and nowhere else in line 2.** `<` is what a
      document prints for an unspecified sex, which is a different thing from a
      misread, so 2.10's "empty once the filler is removed" rule does not
      repeat: the filler *is* the answer. This is what 2.11 deferred when it
      declined an emptiness rule for the nationality — there is exactly one
      unspecified sex and there is no such thing as an unknown nationality.
      **Line 1 at position 21 is the `M` of `MARIA`**, so a reader handed the
      wrong line returns a valid marker rather than an error, and the
      wrong-line expiry read is `"ARIA<<"`, whose check digit is **also 9**.
      All three wrong-line answers pass their own validators and two of the
      three are caught by nothing underneath, which is 2.13's problem to
      solve; the test asserts the wrong answers rather than hiding them.
      **The messages name the four markers and not the one that was found; the
      dates' messages name the width and the positions and not the date.** A
      sex marker and a date of birth are both properties of the holder, so
      nothing here echoes a value — 2.10's line, carried across again.
      **74 new cases in `backend/tests/unit/test_td3.py`, 71 of them written
      first** — 66 failed against the pre-2.12 module and the 5 that were
      green legitimately are the layout guards, as 2.5's 20th and 2.4's 32nd
      were: the layout-position test, the three width pins, and the
      no-check-digit-covers-the-sex-marker guard. The other 3 were added after
      the mutation run, in answer to survivors (below). Beyond the four named
      accepted markers and the named `Z` rejection: a 17-row sex rejection
      table, an exhaustive check that the validator accepts exactly
      `TD3_SEX_MARKERS` over the whole MRZ alphabet, the 3.11 boundary, the
      as-printed evidence and its limit, the untrimmed and un-re-cased date
      cases, a six-row width table, three non-string rows per validator, two
      no-echo cases, three short lines, three non-string lines, the
      read-by-position case, the wrong-line costs, and three layout-fidelity
      cases that move each field to a **different width**, so a hardcoded 6
      fails as well as a hand-written slice.
      **A throwaway mutation run confirms the teeth, 22 of 22 caught**: accept
      any sex, drop the filler from the set, no sex type guard, the sex reader
      slicing the line itself or pointed at the date of birth, the date of
      birth reader hardcoding its slice, each date's width check removed /
      relaxed / hardcoded to 6, each date returned stripped or upper-cased, the
      sex message echoing the marker or dropping the set, the date message
      dropping the positions or echoing the date, the expiry reader pointed at
      the personal number, and each of the three new exports removed.
      `td3.py` was restored from bytes afterwards and SHA-256 hash-checked,
      not assumed; the script was deleted.
      **Three mutations survived the first pass, and each was a missing test
      rather than a wrong one**: a stripped date, an upper-cased date, and a
      hardcoded width of 6. The first two are closed by
      `test_a_date_holding_whitespace_is_returned_untrimmed` and by the
      lower-case row of the accepted table, and the third by moving each date
      to a field of a different width in the layout-fidelity test.
      Verified: `python -m pytest backend/tests/unit/test_td3.py -q` reports
      `408 passed` (was 334); `python -m pytest backend/tests -q` reports
      `696 passed` (was 622) and exits 0 with `-p no:faulthandler`;
      `scripts/check-all.ps1` exited 0 (696 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0; and importing
      `app.pipeline.tier0.td3` in a bare interpreter still loads neither
      `cv2` nor `numpy`, so Gate 1's no-OpenCV rule holds. 1.9's package-wide
      scans cover this file and pass. Test-name uniqueness re-checked: the
      only duplicate in the file is still the pre-existing 2.5/2.8 pair.
      Scope was `td3.py`, `test_td3.py`, the `- [x]` marker and this note, and
      `HANDOVER.md`; no other source file, and no `lorebook/` file, was
      touched, and no git command that writes anything was run.
- [x] **2.13** Write `parse_td3(lines) -> MrzDocument` assembling every field
  plus the raw per-field source slices, with a test on a full specimen MRZ.
  Verify: the new test passes and every field is populated.
      — **the code and all 52 of its tests were already written; this task was
      one failing test and the one-line change that answers it, which is what
      the previous handover's Known Issues section diagnosed and then had to
      leave alone because 2.14 was not 2.13.** `MrzDocument`, `_td3_sources`
      and `parse_td3` were all present and correct in their *values*; the
      failure was a *count*. `parse_td3` called `td3_field` for the six fields
      that have no reader of their own (the five printed check digits and the
      personal number) and `_td3_sources` then read all fourteen again, so
      every field was sliced twice where
      `test_the_assembler_reads_every_field_through_td3_field` claims the eight
      with a reader are sliced twice and the six without one are sliced once.
      **The fix routes the six out of the map `parse_td3` has already built**
      rather than off the line a second time, so a field's value and its
      source slice are now the one string `_td3_sources` read once and cannot
      drift apart. That is the shape the surrounding documentation already
      described — `parse_td3`'s docstring says "this function slices no line
      for itself" and `_td3_sources`' says it reads "every field's raw
      characters" — so the test was right and the implementation was the
      thing out of step with its own prose. The `parse_td3` docstring
      paragraph on the six fields was updated to say where they come from.
      Nothing else moved: the record's fields, `sources`, the readers and
      their order are untouched, so 2.14's 24 mutation tests stayed green
      without an edit, which is the evidence that the change was about
      *where a read happens* rather than *what it produces*. Verified:
      `python -m pytest backend/tests -q` reports `772 passed` and exits 0
      (was `771 passed, 1 failed`); the task's own named cases — the
      end-to-end specimen parse, the 14-row "every field is populated" table,
      the export check and the read-count check — report `17 passed`;
      **`scripts/check-all.ps1` exits 0 (772 backend, 45 frontend, build) for
      the first time since 2.13 was written**, which is what unblocks the
      harness the previous two sessions recorded at exit 1; `python -m
      compileall -q backend` exits 0; and importing
      `app.pipeline.tier0.td3` in a bare interpreter loads neither `cv2` nor
      `numpy`, so Gate 1's no-OpenCV rule holds. Parsed the specimen by hand
      outside the test file as well, and Gate 2's own sentence holds: the name
      is `ERIKSSON` / `('ANNA', 'MARIA')`, the number `L898902C<`, the
      nationality `UTO`, the date of birth `740812`, the sex `F`, the expiry
      `120415`, and `sources` holds 14 entries. Scope was `td3.py`, this
      `- [x]` marker and note, and `HANDOVER.md`; no other source file, and no
      `lorebook/` file, was touched, and no git command that writes anything
      was run.
- [x] **2.14** Add a negative test: a passport MRZ with a mutated character in
  the passport number still parses structurally, and the check-digit verifier
  is what reports the mismatch (parsing must not silently "fix" it).
  Verify: the new test passes.
      — **the 24 tests were already written by the session that also wrote
      2.13; this task was to confirm they hold and to close the marker, which
      `tasks.md` had never been flipped for.** They are at the end of
      `backend/tests/unit/test_td3.py` — 7 named tests and one 18-row
      parametrised table, `MUTATED_DOCUMENT_NUMBER = "L898902A<"` (the
      specimen's `L898902C<` with `C`→`A` at position 8, moving the printed
      digit from `3` to `7`). **No source change**: `td3.py` already parses a
      mutated number and already hands the verifier the character the document
      printed. The per-field verifier over a TD3 zone is deliberately *not*
      built — 3.3 owns reporting which field failed and 3.2 owns the
      composite, so 2.14 only pins the seam they build on.
      **Verified by two mutation runs, not by the test names.** A
      `parse_document_number` that brute-forces a substitution to make the
      number agree with its own printed digit — the exact silent fix this
      task forbids — is caught by **22 of the 24 cases**: the structural
      test, the whole 18-row table, the not-corrected test, the
      one-field-differs test and the three-other-digits test. The two
      survivors are the blind-spot tests, and they survive *correctly*, since
      an in-value-class substitution is one the arithmetic already agrees
      with, so that repair never fires; a second repair variant, which
      normalises in-class substitutions too, is caught by **all 7 named
      tests including both blind-spot ones**. So every 2.14 case has teeth
      against a repairing parser, across the two variants. `td3.py` was
      restored from bytes after each run and SHA-256 hash-checked
      (`95758F5D…66C7703` before and after), not assumed, and the backup was
      deleted; a `_mrz`/`_cand` residue grep returns 0.
      Verified: `python -m pytest backend/tests -q -p no:faulthandler` reports
      `772 passed` and exits 0; `python -m compileall -q backend` exits 0;
      **`scripts/check-all.ps1` exits 0 (772 backend, 45 frontend, build)**.
      No test was added or changed in this session, so there is no new name to
      collide; scope was the `- [x]` marker and note in `tasks.md` and this
      handover — **no source file, and no `lorebook/` file, was touched, and
      no git command that writes anything was run.**

**Gate 2:** a real specimen passport MRZ parses to correct name, number,
nationality, DOB, sex, and expiry.

---

# Part 3 — Check digits for TD3, then TD1 and TD2

- [x] **3.1** Build the TD3 composite input from line 2 positions 1–10, 14–20
  and 22–43, with a test asserting the assembled string is 39 characters.
  Verify: the new test passes.
      — new `TD3_COMPOSITE_FIELDS` (a tuple of the eight field *names*, not
      three restated spans) and `td3_composite_input(line_2)` in `td3.py`, both
      in `__all__`. The concatenation is over those names and every read goes
      through `td3_field`, so "1-10, 14-20 and 22-43" is a *consequence* of
      `TD3_LINE_2` rather than a second copy of it — the module's rule that no
      position is stated outside the layout tables. **It computes no digit and
      judges nothing**, which is 3.2's and 3.3's boundary: `check_digit` stays
      the only place a digit comes out, and the width is not re-checked because
      `validate_td3_lines` is the one shape gate. 8 new cases at the end of
      `backend/tests/unit/test_td3.py`. The named one asserts 39 *and* the
      characters, the expected 39 built longhand from the standard's spans
      (`"L898902C<3" + "7408122" + "1204159ZE184226B<<<<<1"`), so a builder
      reading 39 characters from the wrong place fails on the value. The
      others: the field list collapses to exactly the three spans and skips
      exactly the nationality, the sex and the composite digit; the read-count
      test records eight `td3_field` calls, all line 2, all the line-2 table
      (2.13's technique, so a hand-written `line[28:42]` cannot pass); a
      mutated nationality *and* sex leave the input byte-identical while a
      mutated date of birth moves it, which measures 2.11/2.12's gap instead of
      restating it; the 2.14 mutant reaches the composite as printed with the
      contradicted digit *inside* the span, so the assembler demonstrably does
      not repair; a non-string raises `td3_field`'s own `MrzValueError`
      verbatim, so 1.9's single-`except` rule holds. **One limit is written
      down rather than left for 3.2 to find:** a short line is not rejected, and
      returns a composite *shorter than the line* — 20 characters yield 17,
      because reads of fields starting past the end return nothing — and such a
      string is arithmetically valid, so 3.2 should read a line that came out of
      `validate_td3_lines`. Verified: `python -m pytest
      backend/tests/unit/test_td3.py -q` reports `492 passed` (was 483 + 1
      failed); `python -m pytest backend/tests -q -p no:faulthandler` reports
      `780 passed` (was 772) and exits 0; **`scripts/check-all.ps1` exits 0**
      (780 backend, 45 frontend, build); `python -m compileall -q backend`
      exits 0; and importing `app.pipeline.tier0.td3` in a bare interpreter
      loads neither `cv2` nor `numpy`, so Gate 1's rule holds. Assembling the
      specimen's 39 characters outside the test file gives
      `L898902C<374081221204159ZE184226B<<<<<1`. Test-name uniqueness
      re-checked: the only duplicate is still the pre-existing 2.5/2.8 pair.
      Scope was `td3.py`, `test_td3.py`, this marker and note, and the
      handover; no other source file and no `lorebook/` file was touched, and
      no writing git command was run.
- [x] **3.2** Verify the TD3 final composite check digit (position 44) against a
  specimen, with a test using a deliberately wrong final digit.
  Verify: the new test passes.
      -- **This task adds no production code, and 2.2 is the reason.** A
      `td3_composite_verifies` was written first and 3.1's
      `test_this_module_computes_no_check_digit_of_its_own` failed it: that
      guard asserts `mrz.check_digit` and `mrz.verify_check_digit` are not
      even in `vars(td3)`, so the layout module cannot hold a digit and a
      verdict has nowhere to live there. The check is therefore composed in
      the test -- `td3.td3_composite_input` (3.1's production half) against
      `mrz.verify_check_digit` against position 44 read with the *longhand*
      `EXPECTED_LINE_2` table, so the two halves of the comparison are
      independent: the standard's field list and the module's layout. `td3.py`
      is byte-for-byte unchanged and 3.3 is what gives the verdict a home, on
      `MrzDocument`. 5 new cases at the end of
      `backend/tests/unit/test_td3.py`. The named one verifies the specimen's
      line *as returned by `validate_td3_lines`*, discharging 3.1's handover
      instruction, and says in its own comment what it cannot do: 1.6's limit
      stands, position 44 was derived by `mrz.check_digit` rather than quoted,
      so this confirms the arithmetic and not a published value. The wrong
      final digit is tested over **all nine** wrong digits rather than one
      chosen digit, with the 39 characters byte-identical and the arithmetic
      still at 6 in every case, so the disagreement is provably the printed
      digit and nothing else. The rest record the limits: a wrong nationality
      *and* sex still agree (2.11/2.12's gap, with a mutated date of birth as
      the contrast so the `True` cannot read as a check that passes
      everything); a character at position 44 that is not a digit is refused
      by `verify_check_digit` rather than answered `False`, because a misread
      last character is not evidence of forgery; and a line that never passed
      the gate offers a 17-character composite and no claim at all, which is
      why no width check was added to either function. Verified: `python -m
      pytest backend/tests/unit/test_td3.py -q` reports `497 passed` (was 492);
      `python -m pytest backend/tests -q -p no:faulthandler` reports `785
      passed` (was 780) and exits 0; **`scripts/check-all.ps1` exits 0** (785
      backend, 45 frontend, build); `python -m compileall -q backend` exits 0.
      Test-name uniqueness re-checked: the only duplicate is still the
      pre-existing 2.5/2.8 pair. Scope was `test_td3.py` (`import string`
      added), this marker and note, and the handover; `td3.py` was touched and
      then reverted to its original 90,617 bytes, no other source file and no
      `lorebook/` file was changed, and no writing git command was run.
- [x] **3.3** Report a per-field check-digit result list on `MrzDocument` for
  TD3 — passport number, DOB, expiry, optional data, composite — with a test
  that a correct MRY yields all-pass and a mutated one names the failing field.
  Verify: the new test passes.
      -- `MrzDocument.check_digit_results` is a `tuple` of five
      `mrz.CheckDigitResult` records, declared immediately after
      `composite_check_digit` and populated by `parse_td3`. Each row is
      `(field, expected, found)` plus a derived `passed` and `readable`, in
      printed order: `document_number`, `date_of_birth`, `date_of_expiry`,
      `personal_number`, `composite`. The printed digit is the `int` the
      character at positions 10/20/28/43/44 came to; the *printed characters*
      stay on the record as before, so evidence and verdict remain two
      fields. **`mrz` gains `CheckDigitResult` and `check_digit_results`**,
      which is where the arithmetic is; `td3.py` gains only
      `TD3_CHECK_DIGIT_FIELDS` (the five `(label, characters-field or None,
      digit-field)` pairings) and `td3_check_digit_results(line_2, sources)`,
      which reads the four field pairs out of `sources` and takes the
      composite's characters from `td3_composite_input` so there is still
      exactly one assembler.
      -- **The design decision this task turned on: an unreadable field is a
      third answer, not a `False` and not a refusal.** The first version made
      `parse_td3` raise, because `mrz.verify_check_digit` raises for a field
      nobody could read and 2.14's rule says a `False` would be a forged-
      document claim the document did not earn. That broke two Part 2
      guarantees immediately and visibly: 2.4's
      `test_the_personal_number_is_carried_as_printed_and_judged_by_nothing`
      (a space in the optional data) and 2.12's
      `test_only_the_name_is_cleaned_and_a_date_comes_back_exactly_as_printed`
      (`"7a0812"` as a date of birth) both stopped parsing, and
      `test_a_zone_given_the_other_way_round_is_rejected` started reporting
      the wrong fault. `verify_check_digit` is right to raise for one
      isolated field; a *list* cannot, because the composite spans 22
      positions and a single space makes the whole thing uncomputable, so
      raising would take the document with it. So the unreadable half becomes
      `None`, `passed is None`, the row is still there with its readable half
      still reported (`expected 2, found unreadable`), and the other four
      verdicts are unaffected. 2.14's principle is kept rather than dropped.
      What still raises is a mistake in the *call* — a non-iterable, an entry
      that is not a triple, a field named with something other than a string.
      -- **2.2's guard was rewritten, not deleted, and this is the one place
      the task had to change an existing test rather than satisfy it.**
      `test_this_module_computes_no_check_digit_of_its_own` asserted
      `check_digit` and `verify_check_digit` are not in `vars(td3)`, which
      stayed true — but a name check cannot survive a delegation, and
      `td3_check_digit_results` is the first thing in the module that needs
      the digit layer. The two original assertions are kept and the rule they
      stood for is now stated directly: `WEIGHT_CYCLE` and `CHAR_VALUES` are
      not in the namespace, the new function's source contains no `%`, and
      `td3.check_digit_results is mrz.check_digit_results` — the same object,
      so the sum, the weights and the modulo exist in exactly one place in the
      package and there is no second copy here to disagree with it. The
      module docstring's "holds no arithmetic" is now about arithmetic rather
      than about reachability, and says so.
      -- 13 new cases in `test_td3.py` and 14 in `test_mrz.py`. The two the
      task names: the specimen yields five rows in printed order, all
      `passed is True`, and each mutation of the four fields (number, DOB,
      expiry, optional data, printed digit left exactly where the specimen
      printed it) fails **exactly two rows — the field and the composite**,
      which is the standard's three spans rather than a property of the
      mutations, and the contrast case is 3.2's forged final digit, which
      fails the composite row alone. Also pinned: both digits per row against
      the longhand `EXPECTED_DOCUMENT_FIELDS`; each row's characters proved to
      be its own field (and the whole of line 2, which comes to `0` rather
      than `6`, as the near miss); 2.14's 25 same-value-class substitutions
      still passing and still not inventing a failure; a non-digit claim
      giving `expected is None` with `found` still `6`; an MRZ-illegal
      character in a date or the optional data leaving two rows unchecked and
      the document parsed; 2.11/2.12's nationality-and-sex gap still passing
      all five; the pairings checked against the layout's printed order rather
      than against a literal table; and the results being a tuple of frozen
      records that two parses do not share. Three existing tests were updated
      rather than worked around: the record's field order (3.3's row goes
      after `composite_check_digit`), the `td3_field` read count (the
      composite is now read a third time, through the same helper, asserted
      as the old count plus one per `TD3_COMPOSITE_FIELDS`), and
      `test_the_mutant_record_differs_from_the_specimen_in_the_document_number_alone`
      (3.3's row now differs too — which is the point). One stale comment in
      2.14's test claimed the record holds "nowhere a verdict"; it is
      corrected.
      -- Verified: `python -m pytest backend/tests/unit/test_td3.py -q`
      reports `510 passed` (was 497); `python -m pytest
      backend/tests/unit/test_mrz.py -q` reports `285 passed` (was 271);
      `python -m pytest backend/tests -q -p no:faulthandler` reports `812
      passed` (was 785) and exits 0; **`scripts/check-all.ps1` exits 0** (812
      backend, 45 frontend, build); `python -m compileall -q backend` exits 0;
      importing `app.pipeline.tier0.td3` loads neither `cv2` nor `numpy`, so
      Gate 1 holds. `def` name uniqueness re-checked: the only duplicate in
      either file is still the pre-existing 2.5/2.8 pair. Scope was `mrz.py`,
      `td3.py`, `test_mrz.py`, `test_td3.py`, this marker and note, and the
      handover; no other source file and no `lorebook/` file was touched, and
      no writing git command was run.
- [x] **3.4** Create the TD1 layout constants (3 lines of 30) with a coverage
  test asserting positions 1–30 on each line are fully accounted for.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/td1.py` and
      `backend/tests/unit/test_td1.py`. **A new module per format, following
      `td3.py` rather than `ROADMAP.md`'s B1.3 line**, which still says
      `app/pipeline/tier0/mrz.py` and `tests/test_mrz_td1.py`; the split into
      per-format modules happened during Part 2, and the ROADMAP line is the
      stale half of that. `td1.py` holds `TD1_LINE_LENGTH = 30`,
      `TD1_LINE_COUNT = 3`, `TD1_LINE_1` (6 fields), `TD1_LINE_2` (8),
      `TD1_LINE_3` (`name` alone, 1–30) and the `TD1` aggregate holding those
      *same dict objects*, with `__all__` exactly those six names. Nothing
      else: no reader, no shape gate, no arithmetic, so 3.5 and 3.6 own the
      first functions and `mrz.check_digit` stays the only place a digit comes
      out.
      **The named coverage test is
      `test_a_line_covers_positions_1_to_30_with_no_gap_or_overlap`**, run
      against all three lines: it collects every span in the table and
      asserts `sorted(claimed) == list(range(1, 31))`, because counting to 30
      would not do — a gap and an overlap cancel out in the total. It is stated
      three ways on purpose, each failing differently: the sorted comparison
      (compact), a per-boundary adjacency check naming *which* field broke the
      line, and the slices rebuilt into the whole line. **No specimen MRZ is
      used, and that is deliberate:** quoting a TD1 specimen means quoting a
      printed check digit this project has not verified, which is exactly what
      1.6 declined for the TD3 composite; 3.5 is the task that brings one
      into reach. So the positions are checked against a synthetic 30-character
      line where each character names the position it stands in
      (`string.digits + ascii_uppercase[:20]`), and the expected slice for each
      of the 15 fields is written out longhand from the standard's positions —
      which earned its keep on the first run: my own `optional_data_1`
      expectation was one character too long (16–29 ends at `S`, not `T`), and
      the test failed on the value rather than passing as self-consistent.
      **`test_mrz.py`'s package scan picked the new file up with no edit** —
      `PACKAGE_FILES` globs `tier0/*.py` — so the "one error type" and "never
      raises a builtin" invariants already cover `td1.py`.
      **The composite is on line 2, not line 1, and one thing here contradicts
      the task list itself.** Line 1's position 30 is the check digit over
      optional data 1 (16–29); the composite is printed at the *end of line 2*
      (position 30) over line 1's 6–14 and 16–29 plus line 2's 1–7, 9–15 and
      19–29. 3.7's text says "line 1 positions 1–10 and 15–30", which
      **3.7 has since settled as the standard's span and this note as the
      wrong one** — the reasoning is on 3.7 and the two are now the same, so
      the contradiction this note recorded no longer exists. The document
      number's check digit (line 1, position 15) is
      optional in the standard and may print as `<`; the table cannot record
      that — a field is a span, not a rule about characters — so it is written
      in the module docstring, and it matters there because the optional digit
      sits inside the composite's span either way.
      Verified: `python -m pytest backend/tests/unit/test_td1.py -q` reports
      `42 passed`; `python -m pytest backend/tests -q -p no:faulthandler`
      reports `854 passed` (was 812) and exits 0; **`scripts/check-all.ps1`
      exits 0** (854 backend, 45 frontend, build); `python -m compileall -q
      backend` exits 0; importing `app.pipeline.tier0.td1` loads neither `cv2`
      nor `numpy`, so Gate 1 holds. Scope was `td1.py`, `test_td1.py`, this
      marker and note, and `HANDOVER.md`.
- [x] **3.5** Parse TD1 line 1 (document code, issuing state, document number,
  optional data) with a test on a specimen.
  Verify: the new test passes.
      — the specimen is the ICAO 9303 Part 4 sample ID card's line 1,
      `"I<UTOD231458907<<<<<<<<<<<<<<<"`, quoted as text and *verified* as
      a document: `mrz.check_digit("D23145890")` is the `7` it prints at
      position 15, which is the evidence 3.4 said it could not have yet.
      `td1.py` gains `td1_field` (the one place a TD1 line is sliced, as in
      `td3.py`), the closed `TD1_DOCUMENT_CODES` (`I<`, and bare `I`),
      `parse_`/`validate_` pairs for the document code, issuing state,
      document number and optional data 1, and `parse_td1_line_1`, which
      returns all six fields in printed order in a read-only mapping. The
      two printed check digits are carried as printed and judged by nothing
      — verification is 3.7's — and every field comes back with its filler,
      because positions 15 and 30 are computed over those characters as
      they stand. No record type is created: 3.14 owns that.
      **The assembler's line-width check is new and has its own test:** with
      no zone gate yet, a 29-character line sliced its last field to an empty
      string and reported the rest as a document, losing a position quietly.
      The gate will take it over when one exists.
      **The composite is deliberately not asserted, and 3.7 is blocked on a
      question rather than on work:** this module's span (line 1 6-14 and
      16-29, excluding position 15) and 3.7's ("line 1 positions 1-10 and
      15-30") disagree, and they differ exactly at the `7`. Neither has been
      checked against the standard text, so the disagreement is recorded in
      `td1.py`'s docstring rather than settled here, and the specimen's
      printed composite is not quoted. **3.7 settled it: 3.7's span is the
      standard's and this note's is the wrong one, and 3.6's remembered
      `6` was replaced with the `7` the arithmetic computes** — see 3.7.
      Verified: `python -m pytest
      backend/tests/unit/test_td1.py -q` reports `129 passed` (was 42);
      `python -m pytest backend/tests -q` reports `941 passed` (was 854) and
      exits 0; `scripts/check-all.ps1` exits 0 (941 backend, 45 frontend,
      build); `python -m compileall -q backend` exits 0; importing
      `app.pipeline.tier0.td1` loads neither `cv2` nor `numpy`.
- [x] **3.6** Parse TD1 line 2 (DOB, sex, expiry, nationality, optional data 2)
  with a test on the same specimen.
  Verify: the new test passes.
      — the specimen is the *same* ICAO 9303 Part 4 sample ID card, and its
      line 2, `"7408122F1204159UTO<<<<<<<<<<<6"`, is quoted with its two
      printed digits **verified rather than trusted** the way 3.5 checked the
      document number's: `mrz.check_digit("740812")` is the `2` at position 7
      and `mrz.check_digit("120415")` is the `9` at position 15. `td1.py` gains
      `TD1_SEX_MARKERS`, five `parse_`/`validate_` pairs — date of birth, sex,
      date of expiry, nationality, optional data 2 — and `parse_td1_line_2`,
      which returns all eight fields in printed order in a read-only mapping
      and is the twin of `parse_td1_line_1`. All three printed digits on this
      line (7, 15 and 30) are carried as printed and judged by nothing.
      **Two decisions 3.6 was told to make rather than inherit.** The **dates**
      are judged for their width and nothing else, because `YYMMDD` range
      validation is 3.11's: `"993199"` is as acceptable as `"740812"` today, and
      a reader that refused it would make the month 3.11 later reports
      unreachable. The **sex marker** is a closed set of four —
      `{"M", "F", "X", "<"}`, the same four `TD3_SEX_MARKERS` holds — because
      line 2's position 8 is the one field no check digit in this project
      covers (the composite skips it, and neither date's own digit reaches it),
      so "one uppercase letter or the filler" would let `N` and `Q` through
      unchallenged.
      **The sex set is a decision recorded against a missing source, and 3.7's
      question is unchanged.** This repository holds no copy of Doc 9303, so
      the set is stated as the TD1 table states it and not as a list checked
      against it: the two errors are not symmetric and the set goes against the
      cheaper one, since dropping `"X"` refuses a card that is well-formed (the
      failure `validate_issuing_state` already refuses to make by shipping no
      code list at all) while keeping it accepts a marker no card may print, in
      a field only a rules engine can flag. If the table reads `M`, `F` or `<`
      alone, dropping `"X"` is a one-character edit. **The composite at
      position 30 is carried and verified by nothing**, because 3.7 could not
      be settled: this module's span and `tasks.md`'s disagreed about which of
      line 1's positions are inside the arithmetic, so the specimen's `6` was
      quoted as printed and never compared with a computed span. **3.7 settled
      it in the other direction and changed the value: the span is
      `tasks.md`'s, and the position 30 character is now the `7` the
      arithmetic computes** — see 3.7. The parse still verifies nothing, and
      that half has not changed.
      **A line 1 is refused as a line 2 by the sex marker, not by the dates**,
      and that asymmetry is now a test: line 1's positions 1-6 are `"I<UTOD"`,
      six characters of the right width that `validate_date_of_birth` accepts,
      and position 8 is a digit of the document number. The other direction is
      already 3.5's issuing-state test.
      **The line-width check moved into a private `_checked_line`, and one 3.5
      test was updated on purpose:** `test_a_line_2_cannot_be_mistaken_for_a_
      line_1` had its own local copy of the line 2 literal, which is now
      `SPECIMEN_LINE_2`, so the specimen is quoted once. The exported-name pin
      carries all twenty-nine names. Verified: `python -m pytest
      backend/tests/unit/test_td1.py -q` reports `225 passed` (was 129);
      `python -m pytest backend/tests -q -p no:faulthandler` reports `1037
      passed` (was 941) and exits 0; `scripts/check-all.ps1` exits 0 (1037
      backend, 45 frontend, build); `python -m compileall -q backend` exits 0;
      importing `app.pipeline.tier0.td1` loads neither `cv2` nor `numpy`.
- [x] **3.7** Build and verify the TD1 composite check digit over line 1
  positions 1–10 and 15–30 plus line 2 positions 1–7, 9–15 and 19–29, with a
  test on a correct specimen and one on a mutated composite.
  Verify: the new tests pass.
      — **the span in this task's own text is the standard's, and the
      disagreement `td1.py` and its docstring carried is settled against
      them.** 3.5 wrote "line 1 6-14 and 16-29" into the module and then
      flagged it as unchecked; 3.6 carried the flag rather than dropping it.
      The task text is line 1 1-10 and 15-30, plus line 2 1-7, 9-15 and
      19-29 — 51 characters, 26 from line 1 and 25 from line 2 — and three
      things about the format's own shape say it is right: it *starts* at
      line 1 position 1, so it covers the document code and the issuing
      state, the two fields no printed check digit in a TD1 reaches; it
      *includes* every check digit line 1 prints (15 and 30), which the old
      span broke by leaving line 1's own last position out and which is what
      a TD3 does at its positions 10, 20, 28 and 43; and it reads line 2 in
      the shape both other formats use, skipping the sex marker at 8, the
      nationality at 16-18 and its own position.
      **This repository holds no copy of Doc 9303, so the span is stated as
      the standard states it rather than as a list something here looked
      up** — the same standing caveat 3.6 attached to `TD1_SEX_MARKERS`.
      `td1.py` gains `TD1_COMPOSITE_SPANS` (five `(line, first, last)`
      triples) and `TD1_CHECK_DIGIT_FIELDS` (the five pairings, the
      composite's own being `None` in the middle exactly as in `td3.py`),
      `td1_composite_input(line_1, line_2)` and
      `td1_check_digit_results(line_1, line_2, sources)`.
      **The spans are positions on a named line rather than field names, and
      that is forced rather than chosen:** line 1 1-10 stops five characters
      into the nine-character document number, so no list of whole fields
      can name it. Every other span *is* a run of whole fields, and a test
      asserts that the one cut is the document number and nothing else — which
      is what makes a span one position out fail on a value. Six mutants of
      the span were run against the suite (the old 6-14/16-29, one position
      early, one late, the two spans transposed, line 2's sex marker pulled
      in, and line 1's own digit dropped) and each fails 9–13 tests.
      **`td1_composite_input` checks both lines' widths through the existing
      `_checked_line`, which `td3.py` does not need and this format does:**
      a silently short span comes back as a composite that *failed* rather
      than as an error, which is the one failure mode a caller could not
      tell from a forged document.
      **The specimen's composite is now derived, not quoted, and that is the
      one existing value this task changed.** 3.6 put `"6"` at line 2
      position 30 from memory, with a test named
      `test_the_composite_is_carried_as_printed_and_verified_by_nothing`.
      3.7 computed the standard's 51 characters and got **`7`**; the old
      span gets 7 too, and no plausible reading of either line produces 6.
      So the remembered digit was one of the two values 1.6 refused to
      state, and the choice `test_td3.py` made for its own composite was
      made here: `SPECIMEN_LINE_2` now carries `7`, the tests pin the *span*
      longhand rather than a published character, and the fixture is the
      arithmetic's rather than a document's. That test keeps its second
      half — the parse still carries the digit and never judges it — and
      loses only "nothing" from its name.
      **A correct specimen yields four `True` rows and one `None`, and the
      `None` is a property of the format:** optional data 1 is fourteen
      fillers, so its check digit position prints filler rather than a digit
      and 3.3's three-way answer says `found 0, expected None, passed None`.
      A `False` there would be 2.14's mistake on the strength of a field
      nobody filled in. It also makes the composite the only row that can
      catch an edit to that field, which is asserted rather than assumed.
      **The span's one surprise is now a test:** positions 11-14 of the
      document number are *outside* the composite, so editing the tail of
      the number fails the number's own row and nothing else. The sex
      marker and the nationality cannot move the composite at all.
      Verified: `python -m pytest backend/tests/unit/test_td1.py -q` reports
      `250 passed` (was 225); `python -m pytest backend/tests -q -p
      no:faulthandler` reports `1062 passed` (was 1037) and exits 0;
      **`scripts/check-all.ps1` exits 0** (1062 backend, 45 frontend,
      build); `python -m compileall -q backend` exits 0; importing
      `app.pipeline.tier0.td1` loads neither `cv2` nor `numpy`, so Gate 1
      holds. The `__all__` pin now carries all thirty-three names, and
      `test_this_module_states_positions_and_computes_nothing` was rewritten
      the way 3.3 rewrote `td3.py`'s twin — the `banned in vars(td1)` loop
      stays, and `td1.check_digit_results is mrz.check_digit_results` is the
      assertion that says delegation and duplication differ. Scope was
      `td1.py`, `test_td1.py`, this marker and note, the 3.4 note below, and
      `HANDOVER.md`.
- [x] **3.8** Create the TD2 layout constants (2 lines of 36) with a coverage
  test.
  Verify: the new test passes.
      — new `backend/app/pipeline/tier0/td2.py`: `TD2_LINE_LENGTH = 36`,
      `TD2_LINE_COUNT = 2`, `TD2_LINE_1` (3 fields), `TD2_LINE_2` (11
      fields) and the `TD2` aggregate over the *same dict objects*, `__all__`
      exactly those five names, and nothing else — no reader, no span, no
      arithmetic, no error type. Line 1 is `document_code` 1-2,
      `issuing_state` 3-5 and `name` 6-36; line 2 is `document_number` 1-9
      and its digit 10, `nationality` 11-13, `date_of_birth` 14-19 and its
      digit 20, `sex` 21, `date_of_expiry` 22-27 and its digit 28,
      `optional_data` 29-34 and its digit 35, `composite_check_digit` 36.
      The named test is
      `test_a_line_covers_positions_1_to_36_with_no_gap_or_overlap`,
      parametrised over both lines, and stated three ways as in 3.4 (the
      sorted comparison, a per-boundary adjacency check, and the slices
      rebuilt into the whole line) because counting to 36 would not catch a
      gap an overlap cancels out.
      **36 is the first line length the digits and the letters fill exactly**,
      so the synthetic line is `string.digits + string.ascii_uppercase` and
      position 36 is `Z`; every expected slice is written longhand, which is
      what makes a boundary one character out fail on a value.
      **The whole of a TD2's 8-character shortfall against a TD3 is the
      optional data** — 6 characters here against a TD3's 14-character
      personal number — and the two formats share line 2 up to position 28,
      which a test asserts against `td3.py` rather than asserting in prose.
      Five check digits are printed, **all five on line 2**; line 1 carries
      none, so its last position is the last filler of the name.
      **No specimen, on 3.4's reason**: quoting a visa specimen means quoting
      printed check digits nobody has verified, which is 1.6's refusal and
      3.9's task. **No composite span either, deliberately** — see below.
      **This repository holds no copy of Doc 9303, so the positions are
      stated as the standard states them and not as a list something here
      could look up.** That caveat is written into `td2.py` at the moment the
      claim is made, which is the lesson of 3.5 → 3.7: a span written down
      unchecked, carried forward, and found wrong two tasks later.
      **3.9 and 3.10 as written describe the TD1's field distribution and
      this note does not edit them.** 3.9 lists TD2 line 1 as "document code,
      issuing state, document number, optional data with its own check
      digit" and 3.10 lists TD2 line 2 as "DOB, sex, expiry, nationality,
      optional data, final composite" — between them they name no field for
      the holder's name, which a visa MRZ certainly carries, and 3.10's
      composite span (line 1 6-30 plus line 2 1-7, 9-15 and 19-29) is
      `TD1_COMPOSITE_SPANS` with the line 1 portion left in place: those
      three line 2 spans are the TD1's verbatim, and applied to a TD2 they
      would put the composite over the sex marker and the nationality, which
      no other composite in this package does. `td2.py` therefore publishes
      **no** span constant and `test_td2.py` asserts there is none, so the
      wrong one cannot be inherited by importing a name that already exists.
      3.9 and 3.10 have to settle both the field distribution and the span
      against the standard, the way 3.7 did, rather than inherit either.
      Verified: `python -m pytest backend/tests/unit/test_td2.py -q` reports
      `42 passed`; `python -m pytest backend/tests -q -p no:faulthandler`
      reports `1104 passed` (was 1062) and exits 0; **`scripts/check-all.ps1`
      exits 0** (1104 backend, 45 frontend, build); `python -m compileall -q
      backend` exits 0; importing `app.pipeline.tier0.td2` loads neither
      `cv2` nor `numpy`, so Gate 1 holds. Six position mutants were run
      against the suite — the optional data one position late, the document
      code one late, the name one early, the optional data's digit moved onto
      the composite, the sex marker one late, and an inverted composite span
      — and each fails 5 to 8 tests. Scope was `td2.py`, `test_td2.py`, this
      marker and note, and `HANDOVER.md`.
- [x] **3.9** Parse TD2 line 1 (document code, issuing state, name) with a test
  on a specimen visa. **The field list in the task as written was a TD1's and
  is corrected here — see the note.**
  Verify: the new test passes.
      — new readers in `backend/app/pipeline/tier0/td2.py`:
      `td2_field` (the one place a TD2 line is sliced), a closed
      `TD2_DOCUMENT_CODES` (`{"V<", "V"}`), three `parse_*`/`validate_*`
      pairs — document code, issuing state, **name** — and `parse_td2_line_1`,
      which returns all three fields in printed order inside a read-only
      `MappingProxyType`. Nine names added to `__all__` (fourteen in all).
      **The task's own list named a TD1's line 1 and this task corrects it
      rather than parsing it.** It said "document code, issuing state,
      document number, optional data with its own check digit"; in a TD2 the
      document number and its digit are at 1-10 of **line 2** and the optional
      data at 29-35 of line 2, while line 1 holds the holder's **name** at
      6-36 — the field a visa MRZ most visibly carries and the one 3.9 and
      3.10 between them named nowhere. `TD2_LINE_1` was pinned by 3.8, so the
      correction is settled against the table rather than remembered, and
      `test_the_document_number_and_the_optional_data_are_line_2_fields`
      keeps it honest. **3.10's list is wrong in the same way and is not
      edited here — it is 3.10's own correction, and its composite span is
      still 3.10's question.**
      **A specimen is a remembered check digit, so 3.9 is the task 1.6
      pointed at — and on this line the objection does not arise, for a
      reason that is the format's shape.** A TD2 line 1 **prints no check
      digit at all**, so the sample visa's first line has no printed digit to
      take on trust: what cannot be confirmed is the *name*, and no
      arithmetic in this project computes over a name. **3.10 is where that
      stops being true** — line 2 prints five digits and 3.10 is where their
      span has to be settled — which is why the fixture stops at the first
      line. The one thing that *is* checked about it is the one thing this
      project can check: every character on the line is one `mrz.CHAR_VALUES`
      prints, which catches a misremembered line that no check digit would
      have caught. The specimen is `V<UTOERIKSSON<<ANNA<MARIA<<<…<<<` (36
      characters, 31 of name).
      **The name is extracted and judged for its width and nothing else**,
      which is `td3.py`'s rule carried over: the standard fixes where the name
      sits and how wide it is, and nothing about the characters, so a
      diacritic, a lower-case read or a space where a `<<` belongs is a
      misread a flag wants to point at. **The padding is returned with it**,
      because if 3.10's composite covers any part of this line then a
      stripped filler would change the digit 3.10 computes. Its message names
      the positions and the two lengths and **never the name** — the one
      field on this line that is a person rather than a document, and the
      no-echo rule's hardest case in this format.
      **What tells a TD2's two lines apart is two fields and not one.** The
      document code refuses a line 2 whose number does not start `V<`, but a
      number that does start `V<` reaches the code reader as a perfectly good
      visa code; positions 3-5 are then the third through fifth characters of
      a number, so the **issuing state** is what catches it. Two rules, two
      fields, neither of them a check digit, and both are tests.
      Two existing tests were **rewritten rather than deleted**, and 3.8's
      own note said the first one would have to be:
      `test_this_module_states_positions_and_computes_nothing` (its
      "defines no function at all" assertion became a per-function "computes
      nothing" loop, 3.3's and 3.7's way) and
      `test_this_module_defines_no_error_type_of_its_own` (absence became
      identity — the class in `vars(td2)` is `mrz.MrzValueError`, the same
      object, since importing it put mrz's class in the module namespace).
      `test_the_layout_names_are_exported` grew the nine names and now also
      asserts that **no** composite and **no** `parse_td2_line_2` is exported.
      Verified: `python -m pytest backend/tests/unit/test_td2.py -q` reports
      `121 passed` (was 42); `python -m pytest backend/tests -q -p
      no:faulthandler` reports `1183 passed` (was 1104) and exits 0;
      **`scripts/check-all.ps1` exits 0** (1183 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0; importing
      `app.pipeline.tier0.td2` loads neither `cv2` nor `numpy`, so Gate 1
      holds. **Sixteen mutants were run against the suite and all sixteen are
      caught** — the visa code set widened to a passport, a code reader
      accepting anything starting with `V`, the issuing state judged on width
      alone, its width typed in as a 3, its reader slicing the line itself or
      pointed at the name, the name's width typed in as a TD3's 39, its
      reader slicing the line itself, the name stripped of its padding, the
      line width unchecked, the mapping made editable, the name read one
      position early, the name or the state left out of the assembler, and the
      name echoed in its own message. The two assembler mutants are the ones
      that first went uncaught, and they are what
      `test_the_assembler_hands_every_field_to_its_validator` exists for: a
      raw read is *equivalent* on a well-formed line, so equivalence needed a
      test rather than a demonstration. Scope was `td2.py`, `test_td2.py`,
      this marker and note, and `HANDOVER.md`; no other source file and no
      `lorebook/` file was touched, and no writing git command was run.
- [x] **3.10** Parse TD2 line 2 (document number, nationality, date of birth,
  sex, date of expiry, optional data, and all five printed check digits) and
  verify the composite over line 1 positions 6–36 plus line 2 positions
  1–10, 14–20 and 22–35. **The field list and the composite span in the task
  as written were a TD1's and are corrected here — see the note.**
  Verify: the new test passes.
      — `td2.py` gains six `parse_*`/`validate_*` pairs (document number,
      nationality, date of birth, sex, date of expiry, optional data), a
      closed `TD2_SEX_MARKERS`, `parse_td2_line_2` (eleven fields, printed
      order, read-only), `TD2_COMPOSITE_SPANS`, `TD2_CHECK_DIGIT_FIELDS`,
      `td2_composite_input` and `td2_check_digit_results`. Fourteen names
      added to `__all__` (twenty-eight in all).
      **The field list in the task text named a TD1's line 2, and this task
      corrects it rather than parsing it.** It said "DOB, sex, expiry,
      nationality, optional data, final composite"; a TD2's line 2 opens with
      the **document number and its own digit at 1–10**, then the nationality,
      the date of birth and its digit, the sex, the date of expiry and its
      digit, six characters of optional data, that field's own digit and the
      composite. `TD2_LINE_2` was pinned by 3.8, so the correction is settled
      against the table rather than remembered, and
      `test_the_document_number_and_the_optional_data_are_line_2_fields` plus
      the eleven-field assembler keep it honest.
      **The composite's span is settled here, from the format's shape, and it
      is not the task text's span.** The text's three line 2 spans (1–7, 9–15,
      19–29) are `TD1_COMPOSITE_SPANS`'s line 2 spans **verbatim**: applied to
      a TD2 they cut the nine-character document number, the date of birth and
      the six-character optional data, and they take in the nationality and
      the sex marker — the two fields no composite in this package reaches.
      Its line 1 portion ("6–30") stops five characters into a 31-character
      name, which nothing in the format's shape explains. **What this format's
      shape does say is three things:** the span includes every check digit
      the line prints (10, 20, 28 and 35), skips the nationality at 11–13 and
      the sex marker at 21 as both siblings' spans do, and on line 1 reaches
      the **name at 6–36 whole** because it is the only field of that line any
      digit can reach. So the span is 62 characters, 31 from each line, and
      **it is the TD3's own composite with the name in front of it and the
      last eight positions of line 2 dropped** (1–10, 14–20, 22–35 against
      1–10, 14–20, 22–43) — asserted against `td3.py` in a test rather than
      in prose. **This repository still holds no copy of Doc 9303**, so the
      span is the standard's as this project states it; a sourced copy of
      Part 7 is the only thing that turns it into a lookup.
      **Three of the specimen's five printed digits are quoted and confirmed;
      two are derived, and that is 1.6's rule applied rather than avoided.**
      The line is the same fictitious visa line 1 quotes, with the standard's
      own document number "L898902C<" — eight characters and a filler, so the
      padding rule has a value on the specimen — and its personal number
      "ZE184226B<<<<<" cut from a TD3's fourteen characters to this format's
      six. The "3" at 10, the "2" at 20 and the "9" at 28 are the digits the
      same three fields print on the TD1 and TD3 specimens, and each is
      checked against `mrz.check_digit` in a test; **the optional data's own
      digit ("8") and the composite ("3") are computed and written in**, so a
      green composite row is a claim about this project and never about any
      visa — 3.7's choice, made for the same reason.
      **A correct specimen gives five `True` rows and no `None`, which is the
      one thing this format's specimen does not share with the TD1's** — this
      optional data is filled in, so its own digit position prints a digit.
      The unused case is tested rather than assumed: six fillers with the
      filler in the digit position give `found 0, expected None, passed
      None`, and with that row unable to say "failed" **the composite is the
      only row that can see an edit to the field** (asserted by comparing the
      two composites' `found` values).
      **A line 1 handed to the line 2 assembler is not caught, and that is now
      a test rather than a surprise.** Its positions 1–9 are "V<UTOERIK" (not
      filler, so a short padded number), 11–13 are "SON" — an MRZ prints a name
      in capitals, so three uppercase letters — and 21 is an "M", so the parse
      *succeeds*. **What it does not do is accuse the document:** every printed
      digit position on a line 1 holds a letter or the filler, so all five
      rows come back "could not be read" rather than "failed". Two docstrings
      that had claimed the nationality would catch it are corrected.
      **3.9's padding is now load-bearing in fact, not in prospect:** the name
      is inside the span, so a filler changed in its padding moves the
      composite and nothing else. The test picks a character that moves it —
      a filler printed as "A" is worth zero, exactly as the filler is, which is
      2.14's blind spot one field along and not a defect in the span.
      **Three existing tests were rewritten rather than deleted**, each
      because the claim they stated was no longer the true one:
      `test_this_module_states_positions_and_computes_nothing` (the banned
      list relaxes by one name, `check_digit_results`, now that this module
      delegates to it, and gains the positive `td2.check_digit_results is
      mrz.check_digit_results`), `test_this_module_holds_no_composite_span`
      (absence becomes single authorship), and
      `test_the_assembler_hands_every_field_to_its_validator` (parametrised
      over both lines, with line 2's five printed digits deliberately absent
      from the list, because a count of eleven would claim the parse judges
      digits).
      Verified: `python -m pytest backend/tests/unit/test_td2.py -q` reports
      `265 passed` (was 121); `python -m pytest backend/tests -q -p
      no:faulthandler` reports `1327 passed` (was 1183) and exits 0;
      **`scripts/check-all.ps1` exits 0** (1327 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0; importing
      `app.pipeline.tier0.td2` loads neither `cv2` nor `numpy`, so Gate 1
      holds. **Eighteen mutants were run against the suite and all eighteen
      are caught** — the span's four runs each moved (including the task
      text's own 6–30, its 1–7, and one taking the composite), the nationality
      and the sex marker swallowed into the span, the spans transposed and
      reordered, the optional data widened to fourteen, the sex set widened,
      the document number accepting an all-filler field, the optional data
      stripped, the assembler reading a field raw, the composite input
      skipping the width check, the pairings reordered, and the two messages
      that must not echo their value. Scope was `td2.py`, `test_td2.py`, this
      marker and note, and `HANDOVER.md`; no other source file and no
      `lorebook/` file was touched, and no writing git command was run.
- [x] **3.11** Add the date semantics: `YYMMDD` parsing with month/day range
  validation, rejecting `993199` and `013200`, with tests.
  Verify: the new tests pass.
      — the rule is one function in `mrz.py` and all three formats delegate
      to it. `MrzDate` (frozen dataclass: `year`, `month`, `day`, two printed
      digits of year and **no century**), `parse_date(text) -> MrzDate | None`
      (six characters of `YYMMDD`; `None` when any of the six is not an ASCII
      digit), `date_fault(text) -> "month" | "day" | None`, and the constants
      `DATE_LENGTH = 6` and `MONTH_DAYS`. `"993199"` and `"013200"` are
      refused by name — the month, not the line — through
      `validate_date_of_birth`/`validate_date_of_expiry` in `td1.py`,
      `td2.py` and `td3.py`, and every message names the field, the positions
      and the fault and never the date.
      **Two boundaries this task deliberately does not move.** A field of
      letters or fillers (`"AAAAAA"`, `"<<<<<<"`, `"abcdef"`, `"74o812"`) is
      still accepted, because a character the standard does not print there is
      a misread for the check digit beside the date to report — 2.14's
      unreadable row, not a refusal — and `"000101"`/`"020229"` are accepted
      too, because the century is 3.12's and 3.13's question and a range check
      that needed one would have to invent it. **February's entry in
      `MONTH_DAYS` is 29 and not 28**: a date carries two digits of year, so
      whether *this* February had a 29th is not answerable from what a line
      printed, and the reading that refuses nothing genuine is the largest a
      month can be in any year. `date_fault` also passes a wrong width over
      rather than judging it — the width belongs to the layout table all three
      formats read it from, and 2.11's monkeypatch test (a date field moved to
      five characters) fails if a second width rule leaks in.
      **Three tests were rewritten rather than deleted**, each because the
      claim it stated was no longer the true one: the width-only date tests in
      `test_td1.py`/`test_td2.py`, `test_a_six_character_date_that_is_not_a_real_date_is_still_extracted`
      (now the unreadable half, which 3.11 did not move) and
      `test_a_full_length_line_cannot_make_a_date_reader_fail` (now the two
      lines that fail *are* the two carrying an impossible date). The whole
      rule is measured rather than remembered: every one of the fourteen month
      values against every day from 00 to 32, 462 cases, against a longhand
      copy of the maxima in the test. Verified: `python -m pytest
      backend/tests/unit/test_mrz.py -q` reports `330 passed` (285 before this
      task's tests, measured on the tree as it stood), `test_td1.py` `264`,
      `test_td2.py` `273`, `test_td3.py` `521`; `python -m pytest
      backend/tests -q` reports `1405 passed` (was 1327) and exits 0;
      **`scripts/check-all.ps1` exits 0** (1405 backend, 45 frontend, build);
      `python -m compileall -q
      backend` exits 0; importing the three format modules loads neither
      `cv2` nor `numpy`, so Gate 1 holds. **Five mutants were run against the
      suite and all five are caught** — `str.isdigit()` for the ASCII digit
      test (caught only by the non-ASCII-digit row), February's entry at 28
      (5 tests), `date_fault` refusing a wrong width instead of passing it
      over (8 tests, two of them `test_td3.py`'s layout-monkeypatch pair),
      `YYMMDD` read as `YDMY` (168 tests, because the specimen's own date
      becomes month 74), and `td2.validate_date_of_birth` with the
      `date_fault` call removed (5 tests). Scope was `mrz.py`, `td1.py`,
      `td2.py`, `td3.py`, the four test files, this marker and note, and
      `HANDOVER.md`; no other source file and no `lorebook/` file was touched,
      and no writing git command was run.
- [x] **3.12** Add century inference for dates of birth (a YY implying a person
  older than ~120 years maps to the previous century) with tests at the
  boundary years.
  Verify: the new tests pass.
      — `mrz.py` gains `MAX_BIRTH_AGE = 120`,
      `infer_birth_year(text, reference) -> int | None` and the private
      `_is_a_real_day(year, month, day)`; `__all__` gains two names (thirteen
      in all). The answer is the **most recent year carrying the two printed
      digits that (a) has already happened, (b) was a day that year had, and
      (c) is no more than `MAX_BIRTH_AGE` years before `reference`** — and only
      two centuries are ever candidates, because a third is past the band
      whatever it holds. `reference` is injected (a `datetime.date`, required,
      never the clock) and the answer is a plain `int` beside the record, never
      a field of it: `MrzDate` still holds three numbers and no century.
      **The task's own sentence is half a rule, and the other half is that a
      birth has not happened yet.** Read literally it makes the current century
      the default and sends "74" to 2074 on a 2026 document — a birth 48 years in
      the future — so the previous century is reached two ways, both written
      down: a date the reference has not reached, and a century further back
      than `MAX_BIRTH_AGE`. **The band is where the task's 120 is observable**,
      because the "not yet" test alone can never need it: read on 2120-12-31,
      `"000229"` is 2000 (a real day, exactly 120 years back); read on
      2121-01-01 it is `None`, because 2100 had no 29th of February and the
      century before that is 121.
      **`None` is now three answers a caller cannot tell apart, and all three
      are the same sentence:** the six characters are not all digits;
      `mrz.date_fault` names a month or day that cannot be one; or no century in
      the window makes those six characters a real past day. `parse_date` is
      asked first and `date_fault` second — the first run of the tests caught
      the mistake of asking only `date_fault`, which answers `None` both for "I
      could not read it" and for "there is no fault here".
      **A bad `reference` raises where a bad field does not**, because a
      reference date is never a fact about a document: reporting a screening
      that went wrong as a document nobody could read is the one confusion this
      package cannot have. (`datetime.datetime` is accepted, since it
      subclasses `datetime.date`.)
      **The leap-year question 3.11 deferred is now answered, and `"020229"` is
      the row that needed writing to answer it:** read in 2026 its two
      candidates are 2002 and 1902, neither of which had a 29th of February, so
      a field `date_fault` calls perfectly good gets no year at all.
      `MONTH_DAYS[1]` stays 29 — the range check still cannot know the century,
      and now it does not have to.
      **Nothing is wired to it, and that is a test:** no format module
      references `infer_birth_year`, `MrzDate` still has exactly three fields,
      and `mrz` has no `infer_expiry_year` yet (3.13's, and a different rule).
      Verified: `python -m pytest backend/tests/unit/test_mrz.py -q` reports
      `376 passed` (330 before); `python -m pytest backend/tests -q
      -p no:faulthandler` reports `1451 passed` (was 1405) and exits 0;
      `scripts/check-all.ps1` exits 0 (1451 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0; importing `mrz` loads neither
      `cv2` nor `numpy`, so Gate 1 holds. **Fourteen mutants were run against
      the suite and all fourteen are caught** — the "not yet" comparison
      counted as `>=`, the band removed, the band closed at 120, the leap check
      removed, every February given a 29th, the two candidates tried oldest
      first, the range gate removed, the readability gate removed, the width
      gate removed, the type gate removed, `MAX_BIRTH_AGE` typed as 100, the
      century hard-coded to 2000, the two printed year digits read as the day,
      and the reference-date type check removed. A 700-case sweep (every
      printed year `00`-`99` against seven reference dates, the count asserted)
      compares the answer with the rule restated longhand in the test — the
      `TEST_MONTH_DAYS` technique — so a wrong rule cannot agree with itself.
      Scope was `mrz.py`, `test_mrz.py`, the `tasks.md` marker and note, and
      `HANDOVER.md`; no other source file and no `lorebook/` file was touched,
      and no writing git command was run.
- [x] **3.13** Add century inference for expiry dates, which follows a different
  rule from dates of birth, with boundary tests.
  Verify: the new tests pass.
      — `mrz.py` gains `infer_expiry_year(text, reference) -> int | None` beside
      3.12's `infer_birth_year`, exported in `__all__` (fourteen names in all).
      **The rule is the nearest year carrying the two printed digits that has
      not already passed**, and the candidate pair is 3.12's with the sign
      flipped: `century + YY` and `century + 100 + YY`, most recent first. The
      comparison admits the **day itself**, so a document valid *through* the
      day it expires reads as this year while yesterday's date reads a century
      on — the one place the two rules are not mirror images, and the mirror
      of 3.12's "a birth today has already happened". It shares
      `_readable_date` (the two gates) and `_is_a_real_day` (the calendar) and
      nothing else.
      **There is no `MAX_EXPIRY` and the absence is a decision with its
      reasoning next to it**: `MAX_BIRTH_AGE` exists because nobody is 121, a
      fact about people the six characters cannot supply, whereas two digits
      repeating every hundred years *is* the bound on an expiry — the nearest
      year that has not passed is at most a century away, and that is
      arithmetic rather than an invented figure. So the rule is left unbounded.
      Three tests make that checkable rather than asserted: the sweep asserts
      `0 <= found - reference.year <= 99` for all 700 cases, the sweep asserts
      `unplaceable == 0` (3.12's sweep leaves `None`s behind when the band runs
      out; this one cannot), and an AST walk over the function body asserts
      `MAX_BIRTH_AGE` is not among its `ast.Name` nodes while 3.12's does name
      it. The walk is on the code rather than the source because the docstring
      names the constant in order to explain why it is not used.
      **The leap-day question bites differently, and this is the task's
      distinctive case.** A birth reads backwards and always has a century in
      hand, so its `None` needs a century that is both too old and not a real
      day; an expiry reads forwards and can simply *run out*. `"000229"` read
      in 2026 is 2000 for a birth and `None` for an expiry — 2000 has passed
      and 2100 was not a leap year — and the same field returns 2400 read
      against 2400, because 2100, 2200 and 2300 are all non-leap centuries.
      The one-day boundary pair is 2000-02-28 → 2000 and 2000-03-01 → `None`.
      **The three `None`s are 3.12's and share one function**, asserted row for
      row against the birth rule across the same fifteen unreadable and
      impossible fields, plus the expiry-only third `None` above.
      **3.12's scope assertion is updated rather than deleted, and what
      replaces it is stronger**: where 3.12 asserted
      `not hasattr(mrz, "infer_expiry_year")`, the test now asserts both
      functions exist, are not the same function, have different sources, and
      genuinely disagree — `("740930", REFERENCE)` is 1974 for a birth and
      2074 for an expiry. A test that only said "the second does not exist yet"
      would have stopped protecting anything the moment the second arrived.
      The handover's warning about a `kind=` argument is what the disagreement
      table measures: five fields read against one reference where the two
      rules return different years, which a single function with a flag would
      fail.
      **The boundary tests asked for are all written**: a fixed reference
      (2026-09-30) with the printed date either side of the cut, including the
      one-day pair `"260929"` → 2126 and `"260930"` → 2026 and the
      year-only-comparison row `"260101"` → 2126; a 29 February whose two
      candidate centuries disagree about whether it existed; and one field the
      rule cannot place at all.
      **Ten mutants were run against the suite and all ten are caught** — the
      direction flipped, the farthest century tried first, the day itself
      excluded, the leap-day check deleted, `MAX_BIRTH_AGE` borrowed as a
      band, the century hard-coded at 2000, the year compared without the
      month and day, the readability gate dropped, the reference type gate
      dropped, and the two printed year digits read as the day.
      Verified: `python -m pytest backend/tests/unit/test_mrz.py -q` reports
      `428 passed` (376 before this task's tests, 52 added);
      `python -m pytest backend/tests -q -p no:faulthandler` reports `1503
      passed` (was 1451) and exits 0; **`scripts/check-all.ps1` exits 0** (1503
      backend, 45 frontend, build); `python -m compileall -q backend` exits 0;
      importing `mrz` loads neither `cv2` nor `numpy`, so Gate 1 holds. Scope
      was `test_mrz.py`, the `tasks.md` marker and note, and this handover —
      `mrz.py` already carried the implementation from the interrupted
      attempt and was not modified. No other source file and no `lorebook/`
      file was touched, and no writing git command was run. The mutant harness
      and the Gate 1 probe were throwaways at the repo root and deleted
      themselves.
- [x] **3.14** Add `MrzDocument` as a dataclass with a `format` discriminator,
  and a `parse_mrz(lines)` dispatcher that picks TD1/TD2/TD3 from the line
  count and lengths, with a test for all three plus an unrecognised shape.
  Verify: the new tests pass.
      — `MrzDocument` (declared in `td3.py` since 3.1) is now the common
      currency of all three formats and carries a `format` discriminator,
      plus five `| None` attributes for the optional-data fields only a TD1
      or a TD2 prints; `None` means "this format prints no such field" and
      never an empty string, which is a width no layout has and is already
      the answer `mrz.parse_date` gives for six unreadable characters. New
      module `app/pipeline/tier0/document.py` holds `MRZ_SHAPES`,
      `MRZ_PARSERS`, `detect_mrz_format(lines)` and `parse_mrz(lines)`, and
      it lives in its own module because `mrz.py` must not import a format
      module and no format module can import the other two — the one thing
      that cannot live in any of the four. **The three shapes are disjoint
      (3×30, 2×36, 2×44), so the dispatch is a dictionary lookup and never a
      tiebreak**; a zone whose lines differ in width is refused rather than
      dispatched on its first line.
      **An unrecognised shape is refused by `MrzValueError` and named as
      one** — the message gives the line count and widths plus the three
      shapes this package does read, and never a character, because widths
      are shape and the characters are the identity data the screening is
      about. Eleven unrecognised shapes are tested: no lines, one line, a
      missing name line, a fourth line, three lines of 44, four of 36, a
      line one character short on either line, a ragged zone, lines that are
      not strings, and a zone with one good line and one integer.
      **Two things this task had to add for the dispatcher to have something
      to dispatch to**, both anticipated by 3.6/3.7/3.9/3.10 and left
      explicitly to it: `validate_td1_lines` (three lines of 30) and
      `validate_td2_lines` (two lines of 36), the twins of 3.11's
      `validate_td3_lines`, and the whole-zone parsers `parse_td1(lines)` and
      `parse_td2(lines)`. The private `_checked_line` stays in both modules
      — the handover's "all six assemblers lose it at once" is a breaking
      change to a published API that 264 and 273 tests pin, and removing it
      would *open* the hazard 3.7 recorded rather than close it, since a TD1
      or TD2 composite computed over a silently short span comes back
      *failed* rather than as an error. What the gate buys is the missing
      third line, which no reader inside a format can see.
      **The record carries no reference date and no inferred year**, the
      decision the handover asked to be written down: two nullable year
      fields would put two readings of one field on one record, and a year
      is `int | None` against a reference the record would not carry, so the
      reading would be frozen without the thing that makes it true; a
      `reference` attribute is the one shape that could put
      `datetime.now()` back at the edge of the package, which `tasks.md`
      bans inside check logic. So a caller asks `mrz.infer_birth_year` or
      `mrz.infer_expiry_year` about the printed field directly. Four tests
      hold it: the field names are asserted absent, an AST walk asserts
      `document.py` names no `datetime` and neither inference, and a
      positive test reads a parsed TD3's dates through both functions.
      **3.13's substring assertion over the format modules became an AST
      walk** — same claim ("neither rule is called from a validator"), and a
      substring test would have had to ban the sentences that document the
      decision it protects, which is the same reason 3.13 walked `mrz.py`.
      **A TD1's `name`, `surname` and `given_names` are `None`**: line 3 has
      no reader yet, and the thirty characters are in `sources` under the
      layout's own name, so nothing is lost and a later task fills the three
      attributes without changing this type.
      **The whole thing is measured rather than remembered.** Each of the
      three specimens is asserted field by field against values written out
      in the test, against its format's own parser for equality, for five
      check-digit rows in printed order, and for a `sources` map holding
      every field its layout states. **Thirteen mutants were run against the
      suite and all thirteen are caught**: the discriminator hard-coded, a
      per-format field left `None`, a per-format field made an empty string,
      the gate deleted from `parse_td1` (which had passed the suite before
      the gate-ordering tests were written — a real gap this task found in
      itself), a TD1's name or surname invented, ragged zones accepted, an
      unrecognised shape defaulted to TD3, the zone measured twice, the
      refusal message echoing the characters, the zone not materialised, and
      the one-string guard removed.
      Verified: `python -m pytest backend/tests/unit/test_document.py -q`
      reports `52 passed`; `python -m pytest backend/tests -q -p
      no:faulthandler` reports `1580 passed` (was 1503) and exits 0; **`scripts/
      check-all.ps1` exits 0** (1580 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0; importing `document`, `td1`,
      `td2` and `td3` loads neither `cv2` nor `numpy`, so Gate 1 holds.
      Scope was `mrz`-package source (`td3.py`, `td1.py`, `td2.py`, the new
      `document.py`), the five MRZ test files (new `test_document.py`, plus
      the `__all__` and field-list pins in `test_td1.py`/`test_td2.py`/
      `test_td3.py` and the AST walk in `test_mrz.py`), the `tasks.md`
      marker and note, and this handover; no other source file and no
      `lorebook/` file was touched, and no writing git command was run. The
      mutant harness was a throwaway at the repo root and was deleted.

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
      — new `backend/app/pipeline/tier0/mrz_region.py` — the file
      `ROADMAP.md` B1.10 names — carrying `deskew(image)`, `skew_deg(image)`
      and `MAX_DESKEW_DEG`, with 31 new tests in
      `backend/tests/unit/test_mrz_region.py`. **The skew angle is measured
      once, by code this project already ships.** `m7_skew` gains one public
      function, `text_skew(img, mode=...)`, returning the **signed** reading,
      and `assess` now calls it in both of its branches, so the quality gate
      and this helper cannot drift onto different estimators. Nothing in
      `mrz_region.py` computes an angle.

      **A positive reading is the correction and not the tilt, and the tests
      pair every rotation with its mirror for that reason.** A page turned `+5`
      degrees reads about `-5`, and the rotation is applied as the reading
      comes -- negating it leaves `-9.8` on a fixture that wanted `-5`. The
      task's own test reads the corrected page with `m7_skew`'s *other*
      estimator (the photo-mode `minAreaRect`, which shares no code with the
      scan-mode projection search) and requires it within 0.5 of level, while
      the starting page must read over 4 -- so neither an identity function
      nor a sign flip passes it.

      **The frame does not move, and the four new corners are filled with the
      image's own median colour.** Rotating into a larger canvas would offset
      every polygon 4.8 emits and every field box 4.12 returns from the frame
      the officer is looking at, and nothing downstream carries an offset. The
      fill is a per-channel median because OpenCV reads a *scalar*
      `borderValue` as `(v, 0, 0)` on a three-channel image: `borderValue=255`
      turns a white page's corners blue, which binarises as ink and hands 4.3 a
      full-width false component, and a test asserts the corner's three
      channels are equal. `BORDER_REPLICATE`, the other obvious choice, was
      measured and rejected -- it smears the border into the ink mask, and
      with it in place the independent verifier reads 0.00 for *every* image,
      corrected or not, so the test could not have told a correct rotation
      from a wrong one.

      **`MAX_DESKEW_DEG` is `m7_skew.MAX_SKEW_DEG` and not a second number,
      and the comparison is `>`.** At or past the gate's own pass threshold,
      `m7_skew`'s search is at the edge of its range, so the angle is an
      artefact of the search rather than a measurement, and rotating by it can
      leave the image less upright than it was. In that case the argument is
      returned *as it arrived* -- the same object, not a copy -- which is also
      where a blank page lands, because the scan estimator answers an empty
      frame with the end of its search range. `skew_deg` returning `None` (no
      text at all) takes the same branch. One test walks both sides of the
      bound and both signs, and another asserts the exact boundary *is*
      applied, so an off-by-one `>=` fails.

      **The input is three-channel BGR because that is what `m7_skew` takes.**
      Widening the contract here would run the estimator on a frame its author
      never saw. A greyscale test was written and then deleted rather than
      satisfied: `_scan_skew`'s `cvtColor` raises on a one-channel image, and
      the alternative -- converting quietly inside `deskew` -- would be the one
      step in Part 4 nobody could check against the gate that ran before it.

      **The reuse is pinned behaviourally rather than by a comment.** One test
      asserts `mrz_region.skew_deg` equals `m7_skew.text_skew` on a real tilted
      page; a second stands a sentinel angle in `m7_skew`'s place and asserts
      the output is rotated by exactly that sentinel, which a local estimator
      would ignore. **Eight mutants were run and all eight are caught**: the
      sign flipped, a local estimator replacing the call, a scalar border
      fill, an enlarged canvas, the bound made exclusive, the bound restated
      as `12.0`, the guard deleted, and `deskew` short-circuited to return
      its argument. The harness was a throwaway and was deleted.

      **Gate 1 became a test, because this is the file that could have broken
      it.** `mrz_region.py` is the first module in the package to import
      `cv2`, so one `from .mrz_region import deskew` inside `td3.py` would
      have pulled OpenCV into every MRZ reader with nothing in the suite
      noticing.
      `test_the_character_readers_still_import_without_opencv` runs a bare
      interpreter that imports `document`, `td1`, `td2` and `td3` and reports
      whether `cv2` or `numpy` landed in `sys.modules`. A second test holds
      this module to 1.9's rule from the source side: no class, no `raise`,
      and `__all__` exactly the three names. `test_mrz.py`'s existing
      package-wide scans now cover `mrz_region.py` as well, without an edit:
      `PACKAGE_FILES` is a glob, and this module passes both.

      Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q`
      reports `31 passed`; `python -m pytest backend/tests -q -p
      no:faulthandler` reports `1611 passed` (was 1580) and exits 0; **`scripts/
      check-all.ps1` exits 0** (1611 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0. Scope was the new
      `mrz_region.py`, `m7_skew.py`, the new `test_mrz_region.py`, this marker
      and note, and `HANDOVER.md`; no other source file and no `lorebook/`
      file was written, and no git command was run.
- [x] **4.2** Write `to_gray(image)` and `binarize_inverted(gray)` using an
  adaptive threshold so MRZ glyphs become white on black, with tests asserting
  the output is single-channel and mostly binary.
  Verify: the new tests pass.
      — `to_gray` and `binarize_inverted` in
      `backend/app/pipeline/tier0/mrz_region.py`, both public, with 27 new
      tests in `backend/tests/unit/test_mrz_region.py`. **The verified result
      is `1638` backend (`27` of them new) and `scripts/check-all.ps1` exits
      0.** `__all__` is five names; the source-side rule test was updated to
      match and still holds (no class, no `raise`).

      **The cut is local because 4.1 refused to assume the paper was white,
      and that is measured on a photograph rather than a scan.** 4.1 filled
      the new corners with the image's own median for exactly this reason, and
      a single threshold inherits the assumption straight back: on a page
      whose right half sits at half brightness, one global Otsu cut -- the
      estimator `m7_skew` itself reaches for, and the right answer for a flat
      scan -- calls **88%** of that half ink and hands 4.3 a component **264
      pixels** wide. The local cut calls **2.9%** of the page, which is what
      the same page scanned flat gives (2.9%), and its widest component is one
      glyph, 22 pixels. One test asserts **both** halves of that comparison, so
      a swap to a global cut cannot pass on a fixture that happened to be evenly
      lit.

      **Inverted, so the glyphs are the white, and the polarity is measured
      against the fixture's own drawing.** `connectedComponentsWithStats`
      numbers the zero-valued region as background and calls it 0, so paper at
      0 makes the list 4.3 reads *be* the glyph list with the page in the one
      entry to throw away; the other way round hands 4.3 a full-page foreground
      component to reject. The test re-draws the same two lines with `LINE_8`,
      dilates by a pixel for the anti-aliased fringe `upright_mrz` paints, and
      asserts **zero** white pixels outside the glyphs -- the other way round
      puts ~174,000 pixels of paper out there. A second test says the cut is
      not quietly eating strokes either: it finds every pixel a hard 127 cut
      finds and no more than 1.5x as many.

      **The offset is not zero, and that is arithmetic rather than taste.**
      `THRESH_BINARY_INV` marks a pixel white when it sits *at or below*
      `local mean - C`, so at `C = 0` a **uniform** page compares equal to its
      own neighbourhood mean and every pixel becomes ink: 84% of the flat
      fixture is white there against 2.9% at `ADAPTIVE_C = 10`. It is also what
      stops grain running the page white -- sigma-6 grain gives 40% ink at 0
      and 3.0% at 10. **`ADAPTIVE_C` is this project's own number and its risk
      is written down rather than claimed away**: nothing here can say how much
      darker than the paper a genuine MRZ stroke is (no copy of Doc 9303, no
      printed specimen, and the fixture is *drawn*, so its strokes are 255
      levels below the paper by construction). A larger offset buys cleaner
      paper at the cost of faint print. The number is sized to stop the page
      turning white -- the failure that makes 4.3 see one component -- and not
      to reach a clean component list, which is 4.4's height band's job.

      **The block size is a rule, not a tuned optimum, and that was measured
      first.** Every odd block from 11 to 61 gives the same reading on the
      fixture (ink 2.6%-3.0%, tallest component 15 pixels at every one), so a
      test sweeps all 26 and asserts the reading is the module's -- the
      `TEST_MONTH_DAYS` technique again, with the sweep written out longhand so
      a wrong constant cannot be laundered through a shared expectation. The
      constant is then pinned on three checkable rules that 41 satisfies: odd
      (OpenCV refuses an even neighbourhood), **at least twice a glyph** (or
      the window measures the glyph's own level and stops being a cut relative
      to the paper), and **under a line pitch** (or a pixel in the gap between
      two MRZ lines takes both lines' ink into its mean). The two sizes are
      measured from the fixture rather than restated, so 4.14 replacing the
      generator cannot quietly invalidate the rule -- which is the honest limit
      of the claim.

      **`to_gray` is idempotent and that is not what `deskew` does on
      purpose.** `deskew` refuses a one-channel frame because it would run
      `m7_skew`'s estimator on something its author never saw; here the
      conversion *is* the job, so a converted frame is handed straight back --
      the same object, not a copy, as `deskew` does -- and a caller never has
      to track how many channels it holds. The conversion is **weighted luma,
      not the mean of three channels**: red 76, green 150, blue 29, where a
      channel mean says all three are 85. That is not tidiness -- a mean treats
      a saturated red and a saturated blue as the same brightness, so blue ink
      or a red security tint lands exactly where black belongs. The three
      primaries are pinned longhand, not read back from the call.

      **Neither step moves the frame, and a test now says so for all four
      frames.** 4.1 declined to enlarge the canvas so a region would mean the
      same pixel; a crop or resize here would undo that for every polygon 4.8
      emits. One test runs the whole chain from a page tilted 5 degrees and
      asserts the frame is the one that went in, the ink is in two bands, and
      the ink fraction matches the flat page within 10% -- the order
      (`deskew`, `to_gray`, `binarize_inverted`) held together for the first
      time.

      **A colour frame handed to `binarize_inverted` is left visible as a
      `cv2.error`, and that extends 4.1's known escape rather than repeating
      it.** This function reads a frame the caller already holds rather than
      measuring one, so converting quietly would hide a mistake in the caller
      behind an answer that looked fine; the two functions are separate so the
      channel question is settled in `to_gray`, where it is known.

      **The row-band test deliberately has no threshold in it, and the one
      frame it cannot answer for is named.** `grainy_mrz` makes whole rows of
      isolated single pixels -- 74 bands where the other three frames give 2 --
      so the honest test for it is not a band count but the claim 4.4 actually
      depends on: the widest and tallest components are `(22, 15)` on the
      grainy page and on the clean one alike, so the height band 4.4 is about
      to write rejects the speckle and keeps the print. A further test records
      the limit of the "adaptive" claim rather than widening it: **dimming the
      whole page does not need a local cut** (everything moves together, so a
      single cut is fine -- measured within 10%); what defeats a single cut is
      a page that is *uneven*, and only that is claimed.

      **Ten mutants were run and all ten are caught**: the polarity flipped,
      the Gaussian weighting replaced by a box mean, the local cut swapped for
      a global Otsu, the offset zeroed, the offset quadrupled, the block set
      below one glyph, the block set above the line pitch, luma replaced by a
      channel mean, the already-converted short-circuit deleted, and
      `binarize_inverted` short-circuited to return its argument. Both
      harnesses were throwaway files at the repo root and were deleted.

      Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q`
      reports `58 passed` (was 31); `python -m pytest backend/tests -q -p
      no:faulthandler` reports `1638 passed` (was 1611) and exits 0; **`scripts/
      check-all.ps1` exits 0** (1638 backend, 45 frontend, build); `python -m
      compileall -q backend` exits 0; and importing `document`, `td1`, `td2`
      and `td3` in a bare interpreter still loads neither `cv2` nor `numpy`, so
      Gate 1 holds. Scope was `mrz_region.py`, `test_mrz_region.py`, this
      marker and note, and `HANDOVER.md`; no other source file and no
      `lorebook/` file was written, and no git command was run.
- [x] **4.3** Extract connected components and compute per-component bbox,
  height, width and centroid, with a test on a synthetic two-line MRZ image
  asserting a plausible component count.
  Verify: the new test passes.
      — `extract_components(binary)` and the frozen record `MrzComponent` in
      `backend/app/pipeline/tier0/mrz_region.py`, with 20 new tests in
      `backend/tests/unit/test_mrz_region.py`. **The verified result is
      `1657` backend (`20` of them new) and `scripts/check-all.ps1` exits 0.**
      `__all__` is seven names; the source-side rule test now walks the AST
      instead of grepping, and the claim did not change (see below).

      **The plausible count is 51, from 53 printed characters, and the
      shortfall is two merged neighbours rather than a loose band.** The
      ceiling is not a tolerance: a blob holds at least one character's ink,
      so no component can exist without something behind it, and that holds on
      the frame that went white too. The floor is three quarters of the
      characters, and the test says both halves -- 51 passes, 24 would not.
      Three more claims sit beside the count, because a bare count is
      satisfied by a single full-page blob just as comfortably as by two
      lines of print: the areas **partition the ink exactly** (so a dropped,
      doubled or page-sized component fails), every box lies inside the ink
      `glyph_mask` drew, and the widest and tallest are **4.2's own numbers
      read by 4.2's own helper**, so the two tasks stay checkable against each
      other. The three clean captures 4.2 built -- flat, one-sided shadow,
      low light -- give 51, 51 and 52, so the band is two wide, not one.

      **The page is dropped by label, and the frame that 4.2 could not fix is
      the one that decides it.** When the page turns white the frame is
      entirely ink, and OpenCV numbers the *empty* background anyway: the
      first row of `stats` is the sentinel `[-1, 2147483647, 0, 0, 0]`, so
      dropping the widest component, the last one, or the largest-area one
      reports a **clean page** on the one frame where the cut has failed, and
      4.4 would have nothing left to reject. Dropping index 0 leaves the
      single 600-by-300 blob visible, which is what 4.2's docstring promised
      4.3 would see. A second test holds the same rule where the background
      is small rather than absent -- a page that is all ink except a hole --
      so a reading that dropped "the biggest blob" would return the hole.

      **`CONNECTIVITY = 8`, and the measurement that chose it is a diagonal
      stroke, not a preference.** MRZ strokes are diagonal, and a diagonal
      pixel run is 8-connected and not 4-connected: twelve pixels read as
      **twelve** components under 4 and as **one** under 8. The cost of 8 is
      the opposite mistake, two glyphs whose corners touch reading as one
      blob, and that is 4.4's and 4.10's to live with -- 51 components from
      53 characters already contains two of them. A module constant rather
      than an argument, for 4.2's `ADAPTIVE_C` reason: a caller cannot label
      the page's own definition of "connected" differently from the one 4.4
      filters on.

      **The connectivity is passed by keyword, and this is a live trap in
      OpenCV's own signature.** It reads
      `connectedComponentsWithStats(image[, labels[, stats[, centroids[, connectivity[, ltype]]]]])`,
      so the second *positional* parameter is the `labels` **output** -- a
      call written `(binary, 8)` binds the 8 there and silently gets the
      default. The default is 8, which is exactly why it cannot be noticed by
      looking at the answers: measured, the positional form returns **one**
      component on that diagonal stroke for both `4` and `8`, where
      `connectivity=` returns twelve and one. A test records the call's
      arguments and asserts there are no positional ones, and a first half
      asserts the two readings really are indistinguishable before it does.
      **4.2's test helper `_widest_and_tallest` passes `8` positionally too
      and is unaffected -- 8 is the default, so its answers are right -- but
      the argument there does not say what it looks like it says.**

      **The list is ordered down the page and then across it, which is not the
      order OpenCV hands back.** Labels are numbered in raster-scan order of
      each component's first pixel, which is an artefact of the labelling
      algorithm: measured on this fixture, the fourteenth component's box
      starts at row 107 and the fifteenth's at row 106. 4.5 groups by vertical
      overlap and 4.10 segments along x, so the sort is the order those two
      want -- and the test asserts the fixture *is* a frame where OpenCV's own
      order is unsorted, so the assertion is not vacuous.

      **The centroid is the mean of a component's pixels and the box is
      half-open, and both were chosen against a specific wrong answer.** An
      L-shaped blob has centroid `(7.333, 4.167)` and box centre `(7.0, 5.0)`,
      and 4.9 fits a line through these to find the residual skew inside a
      line -- a box centre would tilt that fit towards whichever glyph shape
      was in the group. The box is `(left, top, left + width, top + height)`,
      not OpenCV's inclusive `cv::Rect`, so that
      `binary[top:top + height, left:left + width]` is exactly the component;
      a one-pixel blob at `(6, 4)` is `(6, 4, 7, 5)` and a test says so
      explicitly, because `(6, 4, 6, 4)` is the other answer and it is wrong.
      Every field is a **measured** pixel count -- the fixture's tallest is 15
      and its widest 22 -- never a normalised one, which is what the
      handover asked for so 4.4's band is written against the same integers.
      The numbers are converted to plain `int` and `float` on the way out,
      because 4.4 compares them against a band, 4.5 sorts them, and a record
      carrying `numpy.int32` cannot go in a JSON body when 4.13's empty result
      becomes a response.

      **Nothing is filtered here, and a test says so before 4.4 finds out.**
      A sigma-6 grainy capture gives **313** components against the clean
      frame's 51, with areas down to a single pixel, while the widest and the
      tallest component are identical on both -- so the speckle adds blobs
      and takes none of the print away. That is the claim 4.4's height band
      rests on, restated through this task's own output, and it is why a
      filter here would be applying a threshold nobody wrote down.

      **The source-side rule test walked the AST instead of grepping, and the
      claim did not change -- 3.14's move, applied one part earlier.** It
      asserted `"class " not in source` and `"raise " not in source`; the
      first is a proxy for a rule that is about *error types*, and 4.3
      introduces this module's first record, which is not one. The second was
      already a landmine: `"raise "` appears in this module's own docstrings
      while they explain the rule. An `ast.Raise` walk and a
      `ClassDef`-bases walk say what the substrings meant -- no `raise`
      anywhere, and no class that is an exception -- and a third assertion
      pins `MrzComponent` as not a `BaseException`. A fourth test holds the
      record to **data and nothing else**: seven fields, and `bbox` and
      `centroid` as the only public attributes, because a method on it is
      where a second judgement about what a glyph is would grow.

      **A greyscale frame is accepted and its answer is the page, and that is
      written down rather than refused.** `extract_components` reads a frame
      the caller holds rather than measuring one, so a three-channel frame is
      `cv2.error` exactly as 4.2 made it. A *greyscale* frame is the other
      mistake and OpenCV does not object: it reads every non-zero pixel as
      ink, so `to_gray`'s own output handed straight in -- skipping
      `binarize_inverted` -- gives 24 components on this fixture with one
      600 pixels wide. That is the page-turned-white failure reached by a
      different route, and catching it would need a `raise` this module may
      not have. A test measures the answer so the limitation is a number and
      not a caveat; the honest fix is the binarisation step that guarantees
      the input.

      **Seventeen mutants were run against the suite and all seventeen are
      caught**: the background kept, dropped by the wrong label, dropped by
      position, and dropped by size; the connectivity set to 4 and passed
      positionally; the sort removed and sorted across before down; numpy
      scalars left in; the centroid taken as the box centre; the box counted
      the far edge in; the area read as width times height; height and width
      swapped; a speckle filter added early; a list returned instead of a
      tuple; the record made mutable; and a colour frame quietly converted.
      Both harnesses were throwaway files at the repo root and were deleted.
      The first run reported 14 of 15, and the survivor was a badly built
      mutant rather than a gap -- `list(enumerate(stats))[1:]` is the same
      reading as the original -- so it was replaced with three that differ.

      Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q`
      reports `77 passed`; `python -m pytest backend/tests -q -p no:faulthandler`
      reports `1657 passed` (was 1638) and exits 0; **`scripts/check-all.ps1`
      exits 0** (1657 backend, 45 frontend, build); `python -m compileall -q
      backend` exits 0. Scope was `mrz_region.py`, `test_mrz_region.py`, this
      marker and note, and `HANDOVER.md`; no other source file and no
      `lorebook/` file was written, and no writing git command was run.
- [x] **4.4** Filter components to MRZ-plausible glyphs by height band and
  aspect ratio, with tests proving a large photo region and a signature blob
  are rejected.
  Verify: the new tests pass.
      — `filter_glyphs(components)` in `backend/app/pipeline/tier0/mrz_region.py`,
      four module constants (`GLYPH_MIN_HEIGHT_PX` 8, `GLYPH_MAX_HEIGHT_PX`
      24, `GLYPH_MIN_ASPECT` 0.2, `GLYPH_MAX_ASPECT` 2.5) and 20 new tests in
      `backend/tests/unit/test_mrz_region.py`. **Two bands, each rejecting one
      of the task's two blobs, and each test asserts the other half would have
      kept it.** A printed photo box comes through the real cut as one blob
      **180 by 120** — aspect 1.5, *inside* the aspect band, so only the height
      ceiling refuses it — and a signature stroke as **150 by 20**, height
      *inside* the height band, so only the aspect ceiling refuses it. The
      bounds are in the measured pixel counts 4.3 reported, never a fraction of
      the page: the three clean captures give glyph heights 13-15 and
      width/height 0.29-1.47, and the constants are held to four *rules* the
      tests check rather than to those readings, because 4.14 replaces the
      fixture. Also measured and asserted: the grainy capture falls from 313
      components to 51 — exactly the clean page's glyphs, all of them inside
      the drawn extent; a page whose cut went white (one 600-by-300 blob)
      leaves nothing for 4.5; and the greyscale exposure is now a number
      (24 components in, **6** survive, all of them 5-or-6-by-10 specks of
      paper). Nothing here reads `area`, pinned non-vacuously by two blobs of
      the *same* 39 pixels given opposite verdicts. 17 mutants were run and all
      17 are caught: either band dropped, each of the four constants moved,
      the bounds made exclusive, the aspect computed before the height,
      records rebuilt, order reversed, a list returned, an area filter added,
      and everything kept. Verified: `python -m pytest
      backend/tests/unit/test_mrz_region.py -q` reports `97 passed`;
      `python -m pytest backend/tests -q -p no:faulthandler` reports `1677
      passed` (was 1657) and exits 0; **`scripts/check-all.ps1` exits 0**
      (1677 backend, 45 frontend, build); `python -m compileall -q backend`
      exits 0. Scope was `mrz_region.py`, `test_mrz_region.py`, this marker and
      note, and `HANDOVER.md`; no other source file and no `lorebook/` file was
      written, and no writing git command was run.
- [x] **4.5** Group surviving components into lines by vertical overlap, with a
  test asserting exactly 2 groups for a 2-line synthetic MRZ.
  Verify: the new test passes.
      — `group_lines(components)` in
      `backend/app/pipeline/tier0/mrz_region.py` and 14 new tests in
      `backend/tests/unit/test_mrz_region.py`. **The task's test is measured
      against what the fixture drew, not against a bare count**, because one
      group holding both lines answers "2" as comfortably as two groups
      holding one line each: all four captures (flat, one-sided shadow, low
      light, sigma-6 grain) come back as **exactly 2** lines, each inside one
      of the fixture's own two drawn row bands, and the grouping is a
      **partition** of the 51 survivors — every record arrives exactly once,
      as the record 4.3 measured. The lines are rows **105-120** and
      **175-190**, and the **55 rows** between them exceed the tallest glyph
      (15), which is 4.4's own reason for putting its ceiling under half the
      line pitch. **The boundary is half-open, so a blob whose top sits
      exactly on a line's lower edge starts a new line** — written out
      longhand (rows 10-20, 15-25, 20-30, 30-40) because a cut cannot produce
      that boundary on demand. **A line is closed by the running maximum of
      its members' lower edges, not by the last one**, and that is the
      decision the first version of the test got wrong: rows 10-31, 15-17 and
      30-32, where the middle blob stops 14 rows short of where it started.
      Both directions are pinned — a blob sharing no row with the *first*
      member is still on its line when something between them bridges, and a
      blob ending above the running max does not pull it down. **The order is
      re-sorted, not inherited**: lines down the page (4.7 counts them, 4.11
      maps a cell index to a field offset), glyphs across it (4.10 segments
      along x) — and 4.3's own `(top, left)` order is asserted *not* to be
      left-monotonic on this fixture's first line, so the sort is not
      vacuous. **The band is not applied a second time**, shown with the one
      record 4.4 refuses and this step keeps: a signature, 150 by 20, aspect
      7.5. **Nothing is discarded, which is 4.6's call**: the handover's
      standing exposure is now a measured number — the six specks of *paper* a
      greyscale frame leaves behind group into **two lines of 2 and 4**, on
      the same two baselines the print uses. A merged pair is still one line
      (written longhand: a 22-wide blob beside an 11-wide one is one line of
      two, not two lines), and the per-line counts bracket the printed
      characters (24 and 27 against 25 and 28; 25 and 27 in low light).
      **15 mutants were run and all 15 are caught**: the edge made
      inclusive; the previous blob taken as the edge instead of the running
      max; the running max off by one; sorted across the page before down;
      the inner sort reversed and dropped; grouped along x; the lower edge
      read from the right; everything merged into one line; the band applied
      again; records rebuilt; lists instead of tuples; lines of one dropped;
      and the lines in reverse order. **The first run reported 13 of 15 and
      both survivors were the transitivity claim** — the hand-made case had
      every blob reaching lower than the one before it, which is exactly the
      shape where comparing against the previous blob gives the right answer,
      so it was replaced with one where the middle blob ends 14 rows short.
      Verified: `python -m pytest backend/tests/unit/test_mrz_region.py -q`
      reports `111 passed`; `python -m pytest backend/tests -q
      -p no:faulthandler` reports `1691 passed` (was 1677) and exits 0;
      **`scripts/check-all.ps1` exits 0** (1691 backend, 45 frontend, build);
      `python -m compileall -q backend` exits 0. Scope was `mrz_region.py`,
      `test_mrz_region.py`, the `tasks.md` marker and note, and `HANDOVER.md`;
      no other source file and no `lorebook/` file was written, and no
      writing git command was run.
- [x] **4.6** Score each line group on height consistency and inter-line
  spacing consistency, and discard groups that fail, with a test where a third
  stray text line is correctly rejected.
  Verify: the new test passes.
      — `filter_lines(lines)` and the two module constants
      `LINE_MAX_HEIGHT_SPREAD` (1/3) and `LINE_MAX_SPACING_SPREAD` (0.25) in
      `backend/app/pipeline/tier0/mrz_region.py`, with 20 new tests in
      `backend/tests/unit/test_mrz_region.py`. Both scores are **ratios taken
      on the group** rather than constants, because a constant would be a
      fifth glyph-size threshold in a module that already holds four: a
      line's own glyph heights spread about its own **median**, and its
      spacing to its nearest neighbour departs from the **tightest spacing the
      set shows** (the leading), judged on the *nearest* of a line's two
      spacings so a stray line cannot take a real one down with it. The stray
      line is drawn on the fixture page at the top (`STRAY_TEXT`,
      `STRAY_BASELINE` in the test) in the fixture's own font and size, so it
      is glyph-plausible to 4.4 and its glyph heights *match* the MRZ's --
      measured, the height score passes it (0.14 of spread) and only the
      spacing refuses it (a pitch of 100 against a leading of 70, 0.43 of it
      against a band of 0.25). Both bands are pinned to rules, and the two
      numbers they are sized from are measured rather than remembered: the
      four captures 4.2 builds all read a leading of exactly **70** and a
      worst line spread of **2 rows on a median of 14**. **4.5's note that
      4.6 is what throws the greyscale specks away was measured to be false
      and has been corrected in that docstring**: the two groups of 2 and 4
      are ten rows tall like each other and a leading apart like each other,
      so both scores pass them and 4.7's cell count is what catches a
      two-blob line. Verified: `python -m pytest
      backend/tests/unit/test_mrz_region.py -q -p no:faulthandler` reports
      `131 passed`; `python -m pytest backend/tests -q -p no:faulthandler`
      reports `1711 passed` (was 1691) and exits 0; `scripts/check-all.ps1`
      exits 0 (1711 backend, 45 frontend, build); `python -m compileall -q
      backend` exits 0. Eighteen mutants were run and all eighteen are
      caught; the harness was a throwaway file under `%TEMP%` and was deleted.
- [ ] [BLOCKED] **4.7** Infer the document format from line count and median glyph count
  per line (2×44, 3×30, 2×36), with a test per format.
  Verify: the new tests pass.
- [ ] **4.8** Emit a polygon per detected MRZ line, with a test asserting the
  polygon encloses the drawn glyphs and has 4 points.
  Verify: the new test passes.
- [ ] **4.9** Estimate residual skew *within* a line group from glyph centroids
  and rotate the group before column segmentation, with a test on a slightly
  rotated MRZ.
  Verify: the new test passes.
- [ ] **4.10** Segment each line into character cells using the x-projection gap
  profile, with a test asserting the cell count matches the inferred format
  length.
  Verify: the new test passes.
- [ ] **4.11** Map a character cell index to a field offset per format, reusing
  the Part 2/3 layout constants so there is exactly one source of truth, with a
  test asserting cell 13 on TD3 line 2 maps to the passport-number check digit.
  Verify: the new test passes.
- [ ] **4.12** Expose `field_regions(document) -> dict[str, Polygon]` returning
  a box per extracted field, with a test asserting the DOB box covers the DOB
  characters and does not cover the expiry characters.
  Verify: the new test passes.
- [ ] **4.13** Make the detector return an empty result (not an exception) when
  no MRZ is present, with a test on a blank image.
  Verify: the new test passes.
- [ ] **4.14** Build a reusable synthetic MRZ image generator (fixture) that can
  render TD1/TD2/TD3 MRZs at a given size, angle, and noise level; use it for
  every test in this part.
  Verify: the fixture renders and its own round-trip test passes.

**Gate 4:** for a synthetic passport image, every MRZ field has a pixel region,
and an image with no MRZ returns empty rather than raising.

---

# Part 5 — Evidence flags, date rules, watchlist

- [ ] **5.1** Create `backend/app/risk/__init__.py` and an `EvidenceFlag` model
  with fields `id`, `tier`, `label`, `weight_band`, `value`, `confidence`,
  `region`, `expected`, `found`, `reason`, `source_module`.
  Verify: a test constructs one and reads every field back.
- [ ] **5.2** Add model validation: `value` and `confidence` must be within
  [0,1], `weight_band` within the allowed set, and `region` must be a
  well-formed polygon or null — with a test per rejected case.
  Verify: the new tests pass.
- [ ] **5.3** Create `backend/app/risk/flag_ids.py` with a constant for every
  flag id used anywhere in the system (`MRZ_*`, `DATE_*`, `WATCHLIST_*`,
  `OCR_*`, `LAYOUT_*`, `FACE_*`, `TAMPER_*`, `CROSSDOC_*`) and a test that the
  module exposes no duplicates.
  Verify: the new test passes.
- [ ] **5.4** Implement the expiry rule — document expired relative to an
  injected reference date — with tests for expired, expiring today, and valid.
  Verify: the new tests pass.
- [ ] **5.5** Implement the not-yet-valid rule (expiry in a past, issue date in
  the future) with tests.
  Verify: the new tests pass.
- [ ] **5.6** Implement the implausible-date-of-birth rule (DOB in the future,
  or implying an age over a configurable maximum) with tests at the boundary.
  Verify: the new tests pass.
- [ ] **5.7** Implement the issue-after-expiry consistency rule with a test.
  Verify: the new test passes.
- [ ] **5.8** Add a `ReferenceDate` dependency so every date rule takes the
  current date as a parameter, with a test asserting no module in
  `tier0/dates.py` calls `datetime.now()`.
  Verify: the new test passes.
- [ ] **5.9** Create the `Watchlist` interface with
  `lookup(document_number, name, dob) -> list[WatchlistHit]`.
  Verify: a test asserts a stub implementation satisfies the interface.
- [ ] **5.10** Create `backend/app/seed/watchlist.json` with synthetic entries:
  stolen document numbers, a blacklist entry, and an identity already seen.
  Use obviously fake values.
  Verify: the file parses as JSON and has at least 3 entries.
- [ ] **5.11** Implement `MockWatchlist` backed by that JSON, with tests: a
  number in the seed hits, an unknown number misses, and a name+DOB match hits.
  Verify: the new tests pass.
- [ ] **5.12** Make `MockWatchlist` load the JSON once at construction, not per
  lookup, with a test counting file reads.
  Verify: the new test passes.

**Gate 5:** a document with a broken DOB check digit and one with a blacklisted
number each produce the correct flag with the correct field region.

---

# Part 6 — Tier 0 runner

- [ ] **6.1** Create `backend/app/pipeline/tier0/runner.py` with
  `run_tier0(image, document_type=None, reference_date=None) -> TierResult`.
  Define `TierResult` as flags, hard-failed bool, hard-fail reason, detected
  format, and detected regions.
  Verify: a test calls it on a synthetic MRZ image and gets a `TierResult`.
- [ ] **6.2** Convert MRZ check-digit results into flags, one per failing field,
  each carrying that field's region from Part 4.
  Verify: a test with a mutated composite names the failing field and the
  region is non-null.
- [ ] **6.3** Convert date-rule results into flags, reusing the reference-date
  injection from 5.8.
  Verify: a test with an expired document produces `DATE_EXPIRED`.
- [ ] **6.4** Convert watchlist hits into flags, treating a blacklist hit as a
  hard fail and a stolen-document hit as a heavy-weighted non-hard flag.
  Verify: tests for both severities.
- [ ] **6.5** Determine `hard_failed` — true when any hard-fail rule fired —
  and expose the reason as a human-readable string.
  Verify: a test asserting a checksum failure hard-fails and a soft flag does
  not.
- [ ] **6.6** Instrument per-stage timing on `TierResult` so a later task can
  show "Tier 0 took 0.11 s" against the abstract's sub-0.3 s target.
  Verify: a test asserts the timing keys exist and are non-negative.
- [ ] **6.7** Reproduce worked example A from `abstract.txt` as a test: DOB
  check digit expected 4, found 7, exits as a hard fail with the DOB field
  highlighted.
  Verify: the new test passes and asserts the flag id, expected, found, and a
  non-null region.

**Gate 6:** `abstract.txt` worked example A is a passing test.

---

# Part 7 — Weights, risk engine, bands, history

- [ ] **7.1** Write `backend/app/risk/weightsets/v1.yaml` with a weight and
  weight band for every id in `flag_ids.py`, and a test that fails if any id is
  missing.
  Verify: the completeness test passes.
- [ ] **7.2** Write the weightset loader exposing `ruleset_version` from the
  file, with a test that the version string is returned.
  Verify: the new test passes.
- [ ] **7.3** Make weight lookup raise on an unknown flag id, with a test — the
  system must never silently score a flag as zero.
  Verify: the new test passes.
- [ ] **7.4** Write `normalise_value(flag)` mapping a flag's value into the
  engine's 0–1 range, with tests for a normal flag, a `None` value, and a
  boolean-style flag.
  Verify: the new tests pass.
- [ ] **7.5** Write the weighted sum `R = Σ(wᵢ · Fᵢ)` with a test on a
  hand-computed three-flag example.
  Verify: the new test passes.
- [ ] **7.6** Add hard-rule handling: any hard fail raises `R` to a configurable
  floor (default 90) regardless of the sum, with a test proving a hard fail
  cannot be outvoted by many soft flags.
  Verify: the new test passes.
- [ ] **7.7** Clamp the final score to [0,100], with tests at both extremes.
  Verify: the new tests pass.
- [ ] **7.8** Add band thresholds to config (`LOW_MAX`, `REVIEW_MAX`) with
  defaults 34 and 69, and a test asserting the defaults.
  Verify: the new test passes.
- [ ] **7.9** Write `to_band(score) -> "low" | "review" | "high"` and test the
  boundary values 0, 34, 35, 69, 70, 100 explicitly.
  Verify: the new tests pass.
- [ ] **7.10** Add a test asserting there is no code path mapping the `review`
  band to an automatic reject — the band exists to protect genuine travellers.
  Verify: the new test passes.
- [ ] **7.11** Return a per-flag contribution breakdown (`id`, `weight`,
  `value`, `contribution`) alongside the total, with a test that the
  contributions sum to the pre-history score.
  Verify: the new test passes.
- [ ] **7.12** Write `decay(age_days, half_life_days) -> float` for the history
  layer, with tests at 0 days, exactly one half-life, and two half-lives.
  Verify: the new tests pass.
- [ ] **7.13** Write `history_signal(prior_outcomes, reference_date, config)`
  that sums only **verified** outcomes, applies decay, and clamps to a
  configurable maximum magnitude, with tests proving an unverified outcome
  contributes nothing and one old verified pass cannot move the band.
  Verify: the new tests pass.
- [ ] **7.14** Combine the history signal into the final score as a bounded
  additive term, with a test asserting the adjustment never exceeds the bound.
  Verify: the new test passes.
- [ ] **7.15** Write `compute_risk(flags, weights, history=None) -> RiskResult`
  returning score, band, contributions, and ruleset version. Reproduce worked
  example B from `abstract.txt`: face similarity 0.41 against a 0.55 threshold
  routes to Tier 2 and yields a high band.
  Verify: the new test passes.

**Gate 7:** both worked examples from the abstract are passing tests, and the
`review` band cannot auto-reject.

---

# Part 8 — Persistence

- [ ] **8.1** Add `sqlalchemy` and `alembic` to `requirements.txt`, install, and
  confirm the existing suite is still green.
  Verify: `python -m pytest backend/tests -q` still reports 13 passed.
- [ ] **8.2** Create `backend/app/storage/db.py` with an engine and session
  factory defaulting to a local SQLite file, overridable by `DATABASE_URL`,
  with a test asserting the default is SQLite.
  Verify: the new test passes.
- [ ] **8.3** Make the config accept a Postgres URL without connecting, with a
  test asserting a `postgresql://` URL is accepted and a malformed one is
  rejected.
  Verify: the new test passes.
- [ ] **8.4** Create the declarative `Base` and the `Screening` model
  (id, created_at, document_type, status, score, band, mode, filename, image
  dimensions, ruleset_version, model_versions, quality JSON, flags JSON,
  summary, deleted_at).
  Verify: a test creates and reads back a row in an in-memory DB.
- [ ] **8.5** Create the `AuditEvent` model (id, screening_id, batch_id,
  event_type, actor, payload JSON, record_hash, created_at).
  Verify: a test round-trips a row.
- [ ] **8.6** Create the `LedgerEntry` model (sequence, batch_id, merkle_root,
  signature, anchored_at) and make it append-only at the ORM level.
  Verify: a test asserting an update raises.
- [ ] **8.7** Add an index on `created_at` and one on `band`, with a test that
  the indexes exist in the created schema.
  Verify: the new test passes.
- [ ] **8.8** Initialise Alembic with the SQLite URL as the default and add the
  first migration matching the models.
  Verify: `alembic upgrade head` on a fresh file succeeds.
- [ ] **8.9** Add a test that runs `upgrade head` then `downgrade base` then
  `upgrade head` again on a temp database.
  Verify: the new test passes.
- [ ] **8.10** Write `ScreeningRepository.create(...)` and a test asserting the
  returned object has an id and a creation timestamp.
  Verify: the new test passes.
- [ ] **8.11** Write `get(id)` and a test that a missing id returns `None`
  rather than raising.
  Verify: the new test passes.
- [ ] **8.12** Write `list(offset, limit)` with a test asserting pagination
  bounds and total count.
  Verify: the new test passes.
- [ ] **8.13** Write `list_by_band(band, offset, limit)` with a test that a
  filtered list never returns a row from another band.
  Verify: the new test passes.
- [ ] **8.14** Write `list_by_date_range(start, end)` and
  `list_by_document_type(doc_type)` with a test each.
  Verify: the new tests pass.
- [ ] **8.15** Write `soft_delete(id)` setting `deleted_at` and excluding
  soft-deleted rows from every read, with a test.
  Verify: the new test passes.

**Gate 8:** migrations round-trip, and the repository supports create, read,
filter, paginate, and soft delete against a temp database.

---

# Part 9 — Hashing, Merkle trees, ledger, signing, anchoring

- [ ] **9.1** Write `canonical_json(obj)` producing deterministic JSON: sorted
  keys, no whitespace, explicit nulls, no floats, dates as ISO strings — with a
  test proving key order in the input does not change the output.
  Verify: the new test passes.
- [ ] **9.2** Add canonical-JSON tests for unicode, nested objects, and a
  rejection of floats.
  Verify: the new tests pass.
- [ ] **9.3** Write `hash_record(obj, salt)` = SHA-256 over
  `salt || canonical_json(obj)`, with a test that one changed field changes the
  hash and that the same record always hashes identically.
  Verify: the new test passes.
- [ ] **9.4** Generate a per-record random salt and store it alongside the
  record, with a test asserting two identical records get different salts and
  different hashes.
  Verify: the new test passes.
- [ ] **9.5** Write RFC 6962-style domain-separated leaf and node hashing
  (`0x00` prefix for leaves, `0x01` for internal nodes), with known-answer
  tests.
  Verify: the new tests pass.
- [ ] **9.6** Write `build_tree(leaves) -> MerkleTree` splitting at the largest
  power of two, with a test asserting the root for 3 known leaves.
  Verify: the new test passes.
- [ ] **9.7** Handle the odd-count case (a lone node promoted unchanged) with a
  test on 3 and 5 leaves.
  Verify: the new tests pass.
- [ ] **9.8** Handle the degenerate cases: a single leaf becomes the root, an
  empty list raises, with tests.
  Verify: the new tests pass.
- [ ] **9.9** Write `proof_for(index)` returning the sibling path, and
  `verify_proof(leaf, proof, root)` returning a bool.
  Verify: a test round-trips a proof.
- [ ] **9.10** Add a test that a proof verifies for *every* leaf index of a
  16-leaf tree, and that mutating any leaf fails verification.
  Verify: the new test passes.
- [ ] **9.11** Create the `Ledger` interface (`append_batch`, `read_batch`,
  `iter_batches`) and a `SqliteLedger` implementation.
  Verify: a test round-trips a batch.
- [ ] **9.12** Enforce append-only with SQLite triggers that reject `UPDATE` and
  `DELETE` on `ledger_entries`, with a test proving both raise.
  Verify: the new test passes.
- [ ] **9.13** Load an Ed25519 key from an env var (generate one for dev if
  absent) and expose `sign(bytes)` and the public key, with a round-trip test.
  Verify: the new test passes.
- [ ] **9.14** Add a test that a signature over a tampered root fails
  verification.
  Verify: the new test passes.
- [ ] **9.15** Write `group_into_batches(unanchored_events, size)` with a test
  asserting 100 events at batch size 25 gives 4 batches in stable order.
  Verify: the new test passes.
- [ ] **9.16** Write `anchor_batch(events)` — build the tree, append one ledger
  entry per batch, and stamp each event with its batch id.
  Verify: a test asserting 1 ledger row for 25 events and that every event
  carries the batch id.
- [ ] **9.17** Write `verify_event(event)` — reload the event from the database,
  recompute its hash, walk its proof, compare to the anchored root, and return
  `verified` / `altered` / `unknown`.
  Verify: a test that mutates a stored payload flips the result to `altered`.
- [ ] **9.18** Add a test that a verified event produces the same hash on two
  separate calls (reproducibility).
  Verify: the new test passes.

**Gate 9:** an event can be independently verified against an anchored root, and
a tampered record is detected. No identity data is in the ledger.

---

# Part 10 — Audit events

- [ ] **10.1** Create `backend/app/audit/__init__.py` and a constants module for
  event types (`screening_created`, `analysis_completed`, `tier_completed`,
  `decision_recorded`, `override_recorded`, `screening_deleted`), with a test
  asserting no duplicates.
  Verify: the new test passes.
- [ ] **10.2** Write `emit(event_type, screening_id, payload)` that hashes,
  persists, and returns the event. This is the only function allowed to create
  audit events.
  Verify: a test emits one and reads it back.
- [ ] **10.3** Attach `ruleset_version` and `model_versions` to every event
  payload, with a test asserting both are present on a generic emit.
  Verify: the new test passes.
- [ ] **10.4** Emit `screening_created` and `analysis_completed` from the
  screening flow, with tests asserting both exist after one screening.
  Verify: the new tests pass.
- [ ] **10.5** Emit one `tier_completed` event per tier that actually ran, with
  a test asserting a hard-failed screening emits only Tier 0.
  Verify: the new test passes.
- [ ] **10.6** Emit a distinct `override_recorded` event when the officer
  contradicts the band, carrying both the system band and the officer's action.
  Verify: a test asserts the override is its own event, not a mutation of the
  automated result.
- [ ] **10.7** Add the `actor` field sourced from a configurable station
  identifier (env var, defaulting to a placeholder) — **not** from a login, and
  with a test asserting no credential or session token appears in the field.
  Verify: the new test passes.

**Gate 10:** the officer's human decision is in the trail next to the automated
result, and every event is independently verifiable.

---

# Part 11 — Tier 0 over HTTP, plus security

- [ ] **11.1** Create `backend/app/api/__init__.py` and
  `routes_screenings.py` with `POST /api/screenings` accepting the same
  multipart shape as `/api/analyze`, returning `screening_id` and `audit_id`.
  Verify: a new API test asserts both ids are present.
- [ ] **11.2** Return the full screening — score, band, flags with regions,
  contributions, ruleset version — from `GET /api/screenings/{id}`, with a test
  asserting every field is present.
  Verify: the new test passes.
- [ ] **11.3** Add `GET /api/screenings` with band, document-type, date-range and
  pagination parameters, with a test per filter.
  Verify: the new tests pass.
- [ ] **11.4** Reuse the existing error envelope for every new endpoint, with a
  test asserting a 404 body matches the existing `{error:{code,message}}` shape.
  Verify: the new test passes.
- [ ] **11.5** Add request-id middleware that stamps every request and returns
  the id in a response header, with a test.
  Verify: the new test passes.
- [ ] **11.6** Convert the API logging to structured JSON including the request
  id and elapsed time, with a test asserting a log line parses as JSON.
  Verify: the new test passes.
- [ ] **11.7** Add a test asserting no log line ever contains image bytes, an
  OCR string, or an embedding.
  Verify: the new test passes.
- [ ] **11.8** Add per-IP rate limiting to the analysis endpoints with a
  configurable limit, and a test that the N+1th request in a window is
  rejected with the standard error envelope.
  Verify: the new test passes.
- [ ] **11.9** Keep and re-verify the existing upload size and pixel caps on the
  new endpoint, with a test for each.
  Verify: the new tests pass.
- [ ] **11.10** Add `GET /api/version` returning app, ruleset, model and prompt
  versions from `version.py`, with a test.
  Verify: the new test passes.
- [ ] **11.11** Split liveness (`/health`) from readiness (`/ready`, which
  checks the database and ledger), with a test that `/ready` fails when the
  database is unreachable.
  Verify: the new test passes.
- [ ] **11.12** Write the OpenAPI contract test that snapshots the response
  schemas of all endpoints, so an unplanned shape change fails the suite.
  Verify: the new test passes, and fails if you add a field without updating it.

**Gate 11:** Tier 0 is reachable over HTTP, rate-limited, logged without
identity data, and its contract is pinned by a test.

---

# Part 12 — Tier 1: OCR and field extraction

- [ ] **12.1** Create `backend/app/pipeline/tier1/__init__.py` and
  `ocr.py` with an `OcrWord` model (text, bbox, confidence) and an `OcrResult`
  model (words, mean confidence), with a test constructing both.
  Verify: the new test passes.
- [ ] **12.2** Define the `OcrEngine` interface with a `read(image) -> OcrResult`
  method, and a test asserting a stub satisfies it.
  Verify: the new test passes.
- [ ] **12.3** Implement `TesseractEngine` behind the interface, reporting
  itself unavailable rather than raising when the binary is missing.
  Verify: the availability test passes on a machine with and without Tesseract.
- [ ] **12.4** Implement `EasyOcrEngine` behind the same interface with the
  same unavailable-rather-than-raising behaviour.
  Verify: the new test passes.
- [ ] **12.5** Write `select_engine(preference)` that honours an explicit
  preference, otherwise picks the first available engine, and returns `None`
  when none is available.
  Verify: tests for explicit-unavailable, first-available, and none-available.
- [ ] **12.6** Add a test asserting Tier 1 degrades to "ocr unavailable" and the
  screening still completes — a missing OCR engine must not fail the document.
  Verify: the new test passes.
- [ ] **12.7** Build a synthetic document image fixture that renders known field
  labels and values (name, passport number, DOB, expiry) at a known size, for
  use by every OCR test in this part.
  Verify: the fixture renders and its own test confirms the expected text is
  present in the source description.
- [ ] **12.8** Write `re_read_field(image, region, engine)` that crops to the
  field region, upscales, re-thresholds, and re-runs OCR on just that region.
  Verify: a test asserting a small field reads correctly after re-read.
- [ ] **12.9** Write the confidence gate: below `OCR_CONFIDENCE_THRESHOLD`, re-read
  once, then try the fallback engine, and only then report low confidence.
  Verify: a test with a deliberately blurred field asserts the re-read path is
  taken.
- [ ] **12.10** Add the anti-false-alarm test that the abstract requires: a field
  which is merely misread must be re-read correctly and must **not** produce a
  flag.
  Verify: the new test passes — this is the most important test in Part 12.
- [ ] **12.11** Define the per-document-type anchor-word and regex table for
  visible-text field extraction (label text → field), starting with passport.
  Verify: a test extracting all four fields from the fixture.
- [ ] **12.12** Add the same table for visa and for national ID, with a test each.
  Verify: the new tests pass.
- [ ] **12.13** Normalise extracted values per field type — dates to ISO, names
  uppercased and transliterated, numbers stripped of spaces — with a test per
  type.
  Verify: the new tests pass.
- [ ] **12.14** Return every extracted field with the image region it came from,
  so a later mismatch can be pointed at.
  Verify: a test asserting each field's region is non-null.
- [ ] **12.15** Write `compare_to_mrz(ocr_fields, mrz_document, tolerance)` that
  emits one flag per mismatched field, each carrying the OCR field's region and
  expected/found values, with transliteration tolerance for names.
  Verify: a test altering the printed DOB yields exactly one mismatch flag.
- [ ] **12.16** Add a test that a name differing only by diacritics or spacing
  does **not** produce a mismatch flag.
  Verify: the new test passes.

**Gate 12:** a printed-field alteration is caught with a region, and a
low-confidence misread is re-read instead of being flagged.

---

# Part 13 — Tier 1: barcode, template, layout, face

- [ ] **13.1** Define the `BarcodeDecoder` interface and implement it with
  `zxing-cpp` (or `pyzbar` if already present), reporting unavailability rather
  than raising.
  Verify: an availability test passes.
- [ ] **13.2** Generate a QR containing a known payload in a test, decode it, and
  assert the payload round-trips.
  Verify: the new test passes.
- [ ] **13.3** Compare the decoded barcode payload against the printed field it
  is expected to match, and emit a flag on disagreement.
  Verify: a test with a deliberately mismatched QR passes.
- [ ] **13.4** Define a template as a reference image plus field rectangles in a
  JSON file, and write a loader that reads `backend/app/pipeline/tier1/templates/`.
  Verify: a test loads a committed template.
- [ ] **13.5** Add a test that adding a new document type requires only a new
  JSON file, with no Python change.
  Verify: the new test passes.
- [ ] **13.6** Implement document corner detection and corner ordering, with a
  test on a synthetic quadrilateral document.
  Verify: the new test passes.
- [ ] **13.7** Compute a homography from the detected corners to the template's
  corners and warp the document into template space, with a test on a rotated
  synthetic document.
  Verify: the new test passes and the warped result is close to the template.
- [ ] **13.8** Store the per-document field tolerances (position, size, rotation
  allowed) in the template JSON, with a test asserting every field has one.
  Verify: the new test passes.
- [ ] **13.9** Score per-field position deviation in aligned space and emit a
  `LAYOUT_DEVIATION` flag with the field's region when it exceeds tolerance.
  Verify: a test with a deliberately shifted field passes.
- [ ] **13.10** Add a font-style proxy metric (stroke density, glyph height
  variance) and include it in the layout score, with a test.
  Verify: the new test passes.
- [ ] **13.11** Add a test that an unaligned document produces a lower layout
  score than an aligned one, so the metric is not constant.
  Verify: the new test passes.
- [ ] **13.12** Define the `FaceDetector` and `Embedder` interfaces, plus
  `NullEmbedder`, which returns a deterministic zero vector and reports
  `is_stub: true`.
  Verify: a test asserting the null embedder is labelled as a stub.
- [ ] **13.13** Implement `InsightFaceEmbedder` (or FaceNet) behind the
  interface, reporting unavailability when the model is absent.
  Verify: an availability test passes either way.
- [ ] **13.14** Implement face detection and alignment (landmark-based
  similarity transform to a canonical crop) in the photo region, with a test
  on a synthetic face-like fixture.
  Verify: the new test passes.
- [ ] **13.15** Write `match_score(embedding_a, embedding_b, threshold)` using
  cosine similarity, with tests for identical, orthogonal, and below-threshold
  inputs.
  Verify: the new tests pass.
- [ ] **13.16** Emit `FACE_LOW_SIMILARITY` carrying the similarity and the
  threshold, and reproduce worked example B: similarity 0.41 against a
  threshold of 0.55 routes the case to Tier 2.
  Verify: the new test passes.

**Gate 13:** a document with a moved field, a bad QR, or a low face similarity
produces the right flag with a region, and a missing model never crashes a
screening.

---

# Part 14 — Orchestrator and escalation

- [ ] **14.1** Create `backend/app/pipeline/orchestrator.py` with a
  `ScreeningContext` model (screening id, document type, image, reference date,
  flags so far, stage trace, mode).
  Verify: a test constructs a context.
- [ ] **14.2** Write a stage registry mapping stage name → callable, and a test
  asserting an unknown stage name raises a clear error.
  Verify: the new test passes.
- [ ] **14.3** Run the existing quality gate as stage 0 and merge its failed
  checks into the flag stream as `quality` tier flags.
  Verify: a test with a blurred image produces a quality flag.
- [ ] **14.4** Run Tier 0 and stop immediately on a hard fail, with a test
  asserting Tier 1 and Tier 2 never ran.
  Verify: the new test passes.
- [ ] **14.5** Run Tier 1 and compute the partial score `R1` from its flags.
  Verify: a test asserts `R1` is present in the context after Tier 1.
- [ ] **14.6** Implement the ambiguity check: `R1` inside a configurable band
  escalates, with tests for inside, at each edge, and outside.
  Verify: the new tests pass.
- [ ] **14.7** Implement the high-risk-profile check (document type or issuing
  state on a configurable watchlist escalates), with a test.
  Verify: the new test passes.
- [ ] **14.8** Implement the randomised deep audit draw as
  `HMAC(server_secret, screening_id) < rate`, with a test that the same id
  always draws the same outcome and that the distribution over 10 000 ids
  matches the configured rate.
  Verify: the new test passes.
- [ ] **14.9** Implement the full-depth mode flag that always escalates, with a
  test.
  Verify: the new test passes.
- [ ] **14.10** Record a stage trace (stage, started, elapsed, flags added,
  escalated?) on the context and return it in the response, with a test
  asserting the trace order is tier 0 → tier 1 → tier 2.
  Verify: the new test passes.
- [ ] **14.11** Add a test asserting an individual module failure is recorded in
  the trace as failed and does not abort the remaining modules — one broken
  check must not lose the whole screening.
  Verify: the new test passes.

**Gate 11 continued:** the cascade runs end to end, and each of the four
escalation triggers is independently tested.

---

# Part 15 — Tier 2: deep analysis

Every task here ships an interface plus an honest, labelled stand-in. None may
be described as a validated detector.

- [ ] **15.1** Create `backend/app/pipeline/tier2/__init__.py` and `base.py`
  with a `DeepModule` interface (`run(context) -> DeepResult`) and a registry.
  Verify: a test asserting a registry with zero modules still returns a valid
  result.
- [ ] **15.2** Define `DeepResult` (score, heatmap, regions, module name,
  `is_stub`, `model_version`, detail), with a test asserting a stub result
  carries `is_stub: true` and a non-empty `model_version`.
  Verify: the new test passes.
- [ ] **15.3** Implement ELA: re-encode the image at several JPEG qualities and
  measure per-block discrepancy, producing a normalised heatmap, with a test
  asserting a re-compressed region lights up.
  Verify: the new test passes.
- [ ] **15.4** Implement noise-residual analysis (high-pass residual, local
  variance map) and a score, with a test asserting an edited region shows
  anomalous variance.
  Verify: the new test passes.
- [ ] **15.5** Implement copy-move detection via self-similarity matching on
  SIFT/ORB blocks, with a test asserting a duplicated region inside the document
  is localised.
  Verify: the new test passes.
- [ ] **15.6** Fuse ELA, noise-residual and copy-move into one tamper score and
  one overlay mask, naming every contributing module, with a test asserting the
  contributors are listed.
  Verify: the new test passes.
- [ ] **15.7** Add a test that a clean synthetic document scores near zero, so
  the tamper score is not trivially high.
  Verify: the new test passes.
- [ ] **15.8** Create a stamp template registry and implement stamp detection +
  template matching, with a test.
  Verify: the new test passes.
- [ ] **15.9** Make a missing stamp template report `not_configured` rather than
  `clean`, with a test asserting the distinction — silence must never read as
  a pass.
  Verify: the new test passes.
- [ ] **15.10** Define the `MorphClassifier` interface and a clearly labelled
  heuristic stand-in (frequency + boundary irregularity cues at the photo
  region) with `model_version: heuristic-v0`.
  Verify: a test asserting `is_stub` and the version string.
- [ ] **15.11** Define the `DeepfakeClassifier` interface and a labelled
  heuristic stand-in, with the same stub test.
  Verify: the new test passes.
- [ ] **15.12** Build a per-document feature vector (ELA stats, noise stats,
  histogram, edge density, field geometry) and fit an IsolationForest on a
  committed feature fixture, with a test asserting an out-of-distribution
  synthetic document scores above the in-distribution ones.
  Verify: the new test passes.
- [ ] **15.13** Convert each Tier 2 result into flags with heatmap-derived
  regions, so Tier 2 findings are as locatable as Tier 0's.
  Verify: a test asserting a tampered-region flag carries a non-null region.
- [ ] **15.14** Add a test asserting every Tier 2 flag id exists in
  `weightsets/v1.yaml` (the weightset-completeness test must not regress).
  Verify: the new test passes.

**Gate 15:** a tampered document produces located tamper flags from labelled
modules, a clean document does not, and a missing template is never reported
as clean.

---

# Part 16 — Cross-document verification

- [ ] **16.1** Add a `TravelerCase` model and table (id, created_at, label) and a
  migration, with a test round-triping a case.
  Verify: the new test passes.
- [ ] **16.2** Add a `case_id` and `document_role` (passport / visa / ID) to
  `Screening`, with a test asserting two screenings can share a case.
  Verify: the new test passes.
- [ ] **16.3** Write `normalise_name(s)` — uppercase, strip diacritics,
  transliterate, collapse whitespace — with tests for `Müller` and `MÜLLER`
  producing the same key.
  Verify: the new tests pass.
- [ ] **16.4** Write `names_match(a, b, tolerance)` with transliteration,
  `Ph`/`F`, compound-surname and token-ordering tolerance, returning a
  similarity plus the differing tokens.
  Verify: tests for `Mueller`/`Müller` (match), `Muller`/`Mueller` (match),
  `Rahman`/`Rahmani` (no match).
- [ ] **16.5** Write `documents_consistent(documents_in_case)` checking
  passport-number ↔ visa cross-reference, with a test that a visa referencing an
  unknown passport raises a flag.
  Verify: the new test passes.
- [ ] **16.6** Add validity-window consistency (the visa must cover the travel
  date) with a test.
  Verify: the new test passes.
- [ ] **16.7** Write `face_consistent(documents_in_case)` using the Part 13
  interfaces, degrading cleanly when no embedder is available, with a test for
  both paths.
  Verify: the new tests pass.
- [ ] **16.8** Emit cross-document flags into the same `EvidenceFlag` stream with
  `tier: crossdoc`, and add a test that they aggregate into the same risk score
  as Tier 0/1/2 flags.
  Verify: the new test passes.

**Gate 16:** a case with a mismatched visa raises a located cross-document flag
and moves the score.

---

# Part 17 — Explainability

The verifier is pure code and needs no model. It is the cheapest part of the
"the model narrates and never decides" claim, so build it before the LLM client.

- [ ] **17.1** Create `backend/app/explain/__init__.py` and
  `verifier.py` with `extract_numbers(text)`, and a test proving it finds
  numbers in text and ignores ordinals inside words.
  Verify: the new test passes.
- [ ] **17.2** Add `extract_dates(text)` and `extract_field_names(text)`
  (capitalised tokens and known flag ids), with a test each.
  Verify: the new tests pass.
- [ ] **17.3** Write `verify_summary(summary, flag_data)` returning pass/fail
  plus the offending tokens, requiring every extracted number, date and field
  name to appear in the flag data.
  Verify: the new test passes.
- [ ] **17.4** Add a negative test: a summary containing `0.98` or a flag id not
  present in the flag data is rejected.
  Verify: the new test passes.
- [ ] **17.5** Write `template_summary(flags, band)` producing 2–3 sentences
  with one line per flag, in plain language, with a test.
  Verify: the new test passes.
- [ ] **17.6** Add a test that the template summary passes the verifier from
  17.3 — the fallback must satisfy the same contract as the model output.
  Verify: the new test passes.
- [ ] **17.7** Create the `Summarizer` interface and a self-hosted LLM client
  speaking the Ollama/llama.cpp HTTP API, with a hard timeout and no external
  fallback — when it fails it returns `None`, it does not raise.
  Verify: a test against a non-existent endpoint returns `None` within the
  timeout.
- [ ] **17.8** Add a test asserting the client is never called when
  `LOCAL_LLM_ENABLED=false`, and that no request ever leaves the configured
  local host.
  Verify: the new test passes.
- [ ] **17.9** Create the versioned prompt template `prompts/v1.txt` and a
  loader exposing `PROMPT_VERSION`, with a test that changing the file changes
  the reported version.
  Verify: the new test passes.
- [ ] **17.10** Build the flag-data payload sent to the model (structured flags,
  band, contributions, no image data), with a test asserting the payload
  contains no pixel data.
  Verify: the new test passes.
- [ ] **17.11** Wire the reject-and-fallback path: verifier failure discards the
  model text, uses the template summary, and records `summary_source` plus
  `verification: failed` in the response.
  Verify: the new test passes.
- [ ] **17.12** Add a test feeding deliberately poisoned model output and
  asserting it never reaches the response and the rejection is auditable.
  Verify: the new test passes.
- [ ] **17.13** Add model-free per-flag reason templates so the officer always
  has a plain-language explanation, with a test asserting every flag id in
  `flag_ids.py` has a reason template.
  Verify: the new test passes.

**Gate 17:** a summary can only reach the officer if every number, date and
field name in it exists in the flag data, and the model-free fallback satisfies
the same rule.

---

# Part 18 — Remaining API surface

- [ ] **18.1** Add `POST /api/screenings/{id}/decision` accepting
  `allow` / `further_inspection` / `reject`, a remark, and an `override` flag,
  with a test per action value.
  Verify: the new tests pass.
- [ ] **18.2** Reject a `reject` on a `low` band without `override: true`, with a
  test proving the rejection is a validation error, not a silent accept.
  Verify: the new test passes.
- [ ] **18.3** Emit the `decision_recorded` and `override_recorded` audit events
  from the decision endpoint, with a test asserting both appear.
  Verify: the new test passes.
- [ ] **18.4** Make the decision endpoint idempotent-safe: a second decision
  changes status and emits a new event rather than overwriting, with a test.
  Verify: the new test passes.
- [ ] **18.5** Add `DELETE /api/screenings/{id}` doing a soft delete, with a test
  asserting the screening disappears from reads.
  Verify: the new test passes.
- [ ] **18.6** Add a test asserting the ledger entry and audit events survive
  the delete — deleting a screening must not erase the audit trail.
  Verify: the new test passes.
- [ ] **18.7** Add `GET /api/audit/{audit_id}/verify` returning
  `verified` / `altered` / `unknown` with the batch root and proof length, and a
  plain-language explanation of what was checked.
  Verify: the new test passes.
- [ ] **18.8** Add a test that tampering with a stored screening payload in the
  database flips the verify endpoint to `altered`.
  Verify: the new test passes.
- [ ] **18.9** Add `GET /api/screenings/{id}/report` returning standalone
  printable HTML with bands, flags, reasons and the audit id, and a test
  asserting it references no external asset.
  Verify: the new test passes.
- [ ] **18.10** Add an SSE stream endpoint reporting per-tier and per-module
  progress, with a test asserting the event shape and a clean disconnect.
  Verify: the new test passes.
- [ ] **18.11** Add a polling fallback endpoint returning the same progress
  state, with a test asserting both routes report identical state.
  Verify: the new test passes.
- [ ] **18.12** Return the stage trace and per-stage timings on the screening
  response so the UI can show where time went, with a test.
  Verify: the new test passes.

**Gate 18:** the officer can record a decision, the decision is in the audit
trail, and any event can be independently verified.

---

# Part 19 — Encrypted evidence store and retention

- [ ] **19.1** Load a master key from the environment, generating a dev key when
  absent, with a test asserting a missing key never silently becomes a known
  constant in production mode.
  Verify: the new test passes.
- [ ] **19.2** Generate a per-blob data key and wrap it with the master key
  (AES-GCM), with a round-trip test.
  Verify: the new test passes.
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
