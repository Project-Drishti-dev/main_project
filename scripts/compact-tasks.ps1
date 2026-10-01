# One-shot refactor: compress completed-task notes in tasks.md to one summary
# line each. Pending tasks, headers, Gates and fenced examples stay untouched.
# ASCII-only source; {EM}/{EN} expand to em/en dash so encoding is never guessed.

$ErrorActionPreference = 'Stop'
$enc  = [System.Text.UTF8Encoding]::new($false)
$path = 'tasks.md'

# $S = summary text for a completed task id.
$S = @{}

$S['0.1'] = '{EM} verified by a case-insensitive search for `not deployed` in `README.md`, which returned no match.'

$S['0.2'] = '{EM} `git log --oneline -1` is `2b779e5` and `git show --stat 2b779e5` confirms the September 30 page work, so the handover text is corrected. The `git status is clean` half cannot pass by design: `AGENTS.md` bans creating commits and the tree is intentionally dirty.'

$S['0.3'] = '{EM} `docs/DECISIONS.md` created with D1 vanilla HTML/CSS/JS (no React), D2 no authentication, D3 UX4G default light theme, each entry recording rationale, what it forbids, and the revisit condition. `check-all.ps1` passed (13 backend, 45 frontend, build).'

$S['0.4'] = '{EM} done as a filesystem move, not a rewrite: `test_engine.py` moved to `backend/tests/unit/test_engine.py`, `test_api.py` moved to `backend/tests/api/test_api.py`, `backend/pytest.ini` `testpaths` set to `tests/unit tests/api`, stale `backend/tests/__pycache__` removed. `check-all.ps1` exits 0 (13 backend, 45 frontend, build).'

$S['0.6'] = '{EM} new root `.env.example`, 18 variables, all commented, placeholders empty or fake; four marked `[LIVE]` as read by code today. `check-all.ps1` exits 0 (13 backend, 45 frontend, build).'

$S['0.7'] = '{EM} `.gitignore` gains `*.db`, `*.sqlite3`, `screenshots/` and a bare `dist/`; `.env` is widened from `/.env` to unanchored so a nested one is caught, and the redundant `/dist/` and `/frontend/dist/` lines are gone. `check-all.ps1` exits 0 (13 backend, 45 frontend, build).'

$S['0.8'] = '{EM} rewritten, not created (the file already existed at 1,713 bytes and already ran all three stages). Two real gaps closed: `$LASTEXITCODE` was read without being cleared, so a stage dying before a native command inherited the previous stage''s exit code; and the failure path had never been exercised. `check-all.ps1` exits 0 on the current tree (13 backend, 45 frontend, build); build-only and each single-stage failure exit 1, all-three-fail exits 1, all-three-pass exits 0. The throwaway harness self-deleted.'

$S['0.9'] = '{EM} new `backend/app/version.py` (three constants, all `"0.1.0"`, matching the `version=` already passed to `FastAPI`) and `backend/tests/unit/test_version.py`, parametrised over the three names. `pytest -k version` 4 passed; `check-all.ps1` exits 0 (17 backend, 45 frontend, build).'

$S['1.1'] = '{EM} both `__init__.py` files created empty (0 bytes), matching the task''s word "empty". This differs from `app/quality_checker/__init__.py`, which carries a docstring, so do not "fix" these later by adding one. `python -c "import app.pipeline.tier0"` from `backend/` exits 0; `check-all.ps1` exits 0 (17 backend, 45 frontend, build).'

$S['1.2'] = '{EM} new `backend/app/pipeline/tier0/mrz.py`: a module-level `CHAR_VALUES` built from `string.digits` + `string.ascii_uppercase`, plus `char_value(c)`. Only the two ranges this task names; `<` (1.3) and `MrzValueError` (1.9) are deliberately absent. Importing the module loads neither `cv2` nor `numpy`, so Gate 1''s no-OpenCV rule holds. `check-all.ps1` exits 0 (54 backend, was 17).'

$S['1.3'] = '{EM} `mrz.py` gains `FILLER = "<"` and `_build_char_values` now inserts `table[FILLER] = 0`, so `CHAR_VALUES` holds all 37 ICAO characters. Module docstring, the `CHAR_VALUES` comment, the `char_value` docstring and its `ValueError` message were updated to name the filler. 58 backend tests pass (was 54); `check-all.ps1` exits 0.'

$S['1.4'] = '{EM} `class MrzValueError(ValueError)` defined in `mrz.py`; `char_value` raises it instead of a bare `ValueError`, message unchanged. Subclassing `ValueError` is deliberate, flagged in the 1.2 and 1.3 notes so existing `except ValueError` callers keep working. 61 backend tests pass (was 58); `check-all.ps1` exits 0.'

$S['1.5'] = '{EM} `WEIGHT_CYCLE = (7, 3, 1)` and `weights(n)`, which returns a fresh list of exactly `n` items, truncated mid-cycle rather than padded. Module docstring now documents the cycle. 51 new tests, written test-first. 112 backend tests pass (was 61); `check-all.ps1` exits 0.'

$S['1.6'] = '{EM} `check_digit(text)` zips `text` against `weights(len(text))` and sums `char_value * weight` mod 10, so it consumes 1.5 and 1.2 rather than holding a private copy of either. In `__all__`; module docstring updated. 13 new tests. 125 backend tests pass (was 112); `check-all.ps1` exits 0.'

$S['1.8'] = '{EM} `verify_check_digit(text, expected)` is `check_digit(text) == _expected_digit(expected)`, so it adds no arithmetic and holds no private copy of the rule. A mismatch is a value, not an exception. 50 new cases. 265 backend tests pass (was 215); `check-all.ps1` exits 0.'

$S['1.9'] = '{EM} the class already existed: 1.4 introduced it when it swapped `char_value`''s raise, and 1.5/1.6/1.8 routed every other failure through it, so this task **pins** the claim rather than defining the class again. 23 new cases, the named one being `issubclass(mrz.MrzValueError, ValueError)`. 288 backend tests pass (was 265); `check-all.ps1` exits 0.'

$S['2.1'] = '{EM} new `backend/app/pipeline/tier0/td3.py` (constants only: no arithmetic, no raise) and `test_td3.py`. Five names: `TD3_LINE_LENGTH` 44, `TD3_LINE_COUNT` 2, `TD3_LINE_1` (3 fields), `TD3_LINE_2` (11 fields, the four printed check digits included as fields of their own right), and the `TD3` aggregate. 313 backend tests pass (was 288); `check-all.ps1` exits 0.'

$S['2.2'] = '{EM} `validate_td3_lines(lines)` in `td3.py`, so 2.1''s module now holds the layout *and* the one gate a zone passes before any of it is read; the docstring says so. Raises `mrz.MrzValueError` and nothing else, and 1.9''s package-wide scans still pass. 325 backend tests pass (was 313); `check-all.ps1` exits 0.'

$S['2.3'] = '{EM} split into two functions because the task''s own four cases make the split necessary: `validate_document_code(code)` is the judgement (membership in `TD3_DOCUMENT_CODES`) and `parse_document_code(line_1)` slices positions 1{EN}2 through `TD3_LINE_1["document_code"]` and delegates. 352 backend tests pass (was 325); `check-all.ps1` exits 0.'

$S['2.4'] = '{EM} **the task''s two clauses contradict each other and this task implements the first one.** `IND` *is* three uppercase letters, so no implementation of the stated rule can reject it and the second clause is unreachable from the first; a membership rule does not rescue it either, since ISO 3166-1 alpha-3 assigns `IND` to India. 384 backend tests pass (was 352); `check-all.ps1` exits 0.'

$S['2.5'] = '{EM} `parse_name(line_1)` in `td3.py`, and **one function rather than the reader/validator pair 2.3 and 2.4 needed**, because this field has no content rule: the standard fixes where the name sits and how wide it is, and says nothing about which characters may appear. 404 backend tests pass (was 384); `check-all.ps1` exits 0.'

$S['2.6'] = '{EM} `split_name(name)` in `td3.py`, added to `__all__`. Takes the string `parse_name` returned rather than a line, so it is `split_*` and not `parse_*`; one function, no validator, on 2.5''s reasoning. 425 backend tests pass (was 404); `check-all.ps1` exits 0. Note: on this Windows box a stray OpenCV faulthandler diagnostic makes pytest exit 1 while every test passes, so run pytest with `-p no:faulthandler`.'

$S['2.7'] = '{EM} `split_given_names(given_names) -> list[str]` in `td3.py`, added to `__all__`. Takes the string `split_name` returned, so `split_*` not `parse_*`; one function, no validator, on 2.5''s reasoning. 450 backend tests pass (was 425); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)'

$S['2.8'] = '{EM} `normalise_names(surname, given_names) -> tuple[str, list[str]]` in `td3.py`, added to `__all__`. Takes the two halves `split_name` and `split_given_names` produced, so `normalise_*` not `parse_*`; no validator, as no content rule is left to enforce. 490 backend tests pass (was 450); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)'

$S['2.9'] = '{EM} `TRANSLITERATIONS` and `transliterate_names(surname, given_names) -> tuple[str, list[str]]` in `td3.py`, both added to `__all__`. Takes what `normalise_names` returned, so `transliterate_*`; no validator, because 2.5 already checked the field. 546 backend tests pass (was 490); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)'

$S['2.10'] = '{EM} `validate_document_number(number)` and `parse_document_number(line_2)` in `td3.py`, both added to `__all__`: the `parse_*` plus `validate_*` pair 2.3/2.4 needed and 2.5 to 2.9 did not, because the document number is the first field with a content rule of its own. The reader slices through `TD3_LINE_2`. 582 backend tests pass (was 546); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)'

$S['2.11'] = '{EM} `validate_nationality(code)` and `parse_nationality(line_2)` in `td3.py`, both added to `__all__`: the 2.10 pair again, because positions 11{EN}13 have a content rule of their own. 622 backend tests pass (was 582); `check-all.ps1` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)'

$S['2.12'] = '{EM} `validate_date_of_birth`/`parse_date_of_birth`, `validate_date_of_expiry`/`parse_date_of_expiry` and `validate_sex`/`parse_sex` in `td3.py`, plus `TD3_SEX_MARKERS`, all added to `__all__`: three fields in one task because the task says so, each the 2.10 pair. A throwaway mutation run confirms the teeth, 22 of 22 caught. 696 backend tests pass (was 622); `check-all.ps1` exits 0; `compileall` exits 0. (pytest needs `-p no:faulthandler`, see 2.6.)'

$S['2.13'] = '{EM} **the code and all 52 of its tests were already written; this task was one failing test and the one-line change that answers it**, which is what the previous handover''s Known Issues diagnosed. `MrzDocument`, `_td3_sources` and `parse_td3` were present and correct in their *values*; the failure was a *count*: the six fields with no reader of their own were sliced twice. The fix routes them out of the map `parse_td3` has already built, so a value and its source slice are now the one string read once and cannot drift apart. 772 backend tests pass; `check-all.ps1` exits 0 for the first time since 2.13 was written, unblocking the harness the previous two sessions recorded at exit 1.'

$S['2.14'] = '{EM} **the 24 tests were already written by the session that also wrote 2.13; this task confirmed they hold and closed the marker `tasks.md` had never been flipped for.** 7 named tests plus an 18-row parametrised table at the end of `test_td3.py`, over `MUTATED_DOCUMENT_NUMBER = "L898902A<"`. **No source change.** Verified by two mutation runs: 22 of the 24 cases catch a parser that brute-forces a substitution to make the number agree with its own printed digit, and a second variant that normalises in-class substitutions too is caught by all 7 named tests. 772 backend tests pass; `check-all.ps1` exits 0; `compileall` exits 0.'

$S['3.1'] = '{EM} new `TD3_COMPOSITE_FIELDS` (a tuple of the eight field *names*, not three restated spans) and `td3_composite_input(line_2)` in `td3.py`, both in `__all__`. The concatenation runs over those names and every read goes through `td3_field`, so "1{EN}10, 14{EN}20 and 22{EN}43" is a *consequence* of `TD3_LINE_2` rather than a second copy of it. 780 backend tests pass (was 772); `check-all.ps1` exits 0.'

$S['3.2'] = '{EM} **this task adds no production code, and 2.2 is the reason.** A `td3_composite_verifies` was written first and 3.1''s `test_this_module_computes_no_check_digit_of_its_own` failed it: that guard keeps `mrz.check_digit` and `mrz.verify_check_digit` out of `vars(td3)`, so the layout module cannot hold a digit or a verifier. 785 backend tests pass (was 780); `check-all.ps1` exits 0.'

$S['3.3'] = '{EM} `MrzDocument.check_digit_results` is a `tuple` of five `mrz.CheckDigitResult` records `(field, expected, found)` plus a derived `passed` and `readable`, in printed order, populated by `parse_td3`. 812 backend tests pass (was 785); `check-all.ps1` exits 0.'

$S['3.4'] = '{EM} new `backend/app/pipeline/tier0/td1.py` and `test_td1.py`. **A new module per format, following `td3.py` rather than `ROADMAP.md` B1.3**, which still names `mrz.py` and `test_mrz_td1.py`; the per-format split happened during Part 2, so the ROADMAP line is stale. 854 backend tests pass (was 812); `check-all.ps1` exits 0.'

$S['3.5'] = '{EM} the specimen is the ICAO 9303 Part 4 sample ID card''s line 1, `"I<UTOD231458907<<<<<<<<<<<<<<<"`, quoted as text and *verified* as a document: `mrz.check_digit("D23145890")` is the `7` printed at position 15, the evidence 3.4 said could not yet exist. `td1.py` gains `td1_field`, the one place a TD1 line is sliced. 941 backend tests pass (was 854); `check-all.ps1` exits 0.'

$S['3.6'] = '{EM} same ICAO 9303 Part 4 sample ID card, line 2, `"7408122F1204159UTO<<<<<<<<<<<6"`, with both printed digits **verified rather than trusted** the way 3.5 checked the document number: `mrz.check_digit("740812")` is the `2` at position 7 and `mrz.check_digit("120415")` is the `9` at position 13. 1037 backend tests pass (was 941); `check-all.ps1` exits 0.'

$S['3.7'] = '{EM} **the span in this task''s own text is the standard''s, and the disagreement `td1.py` carried is settled against the notes.** 3.5 wrote "line 1 6{EN}14 and 16{EN}29" and flagged it unchecked; 3.6 carried the flag. Implemented: line 1 1{EN}10 and 15{EN}30, plus line 2 1{EN}7, 9{EN}15 and 19{EN}29, which is 51 characters. **The one existing value this task changed: `SPECIMEN_LINE_2` now carries `7`, not the `6` 3.6 quoted from memory.** A correct specimen yields four `True` rows and one `None`, because optional data 1 is fourteen fillers so its check-digit position prints filler rather than a digit. Spans are positions on a named line rather than field names, because line 1 1{EN}10 stops five characters into the nine-character document number; a test asserts that one cut is the only one. Six span mutants each fail 9{EN}13 tests. 1062 backend tests pass (was 1037); `check-all.ps1` exits 0; `compileall` exits 0.'

$S['3.8'] = '{EM} new `backend/app/pipeline/tier0/td2.py`: `TD2_LINE_LENGTH` 36, `TD2_LINE_COUNT` 2, `TD2_LINE_1` (3 fields), `TD2_LINE_2` (11 fields) and the `TD2` aggregate over the *same dict objects*, `__all__` exactly those five names and nothing else, so no reader, no span, no arithmetic, no error type. **36 is the first line length digits and letters fill exactly**, so the synthetic line is `string.digits` + `string.ascii_uppercase` and position 36 is `Z`; every expected slice is written longhand, so a boundary one character out fails on a value. No specimen, and **no composite span, deliberately**: 3.9 and 3.10 as written describe the TD1''s field distribution (between them they name no field for the holder''s name), and 3.10''s span is `TD1_COMPOSITE_SPANS` with the line 1 portion left in place, which on a TD2 would put the composite over the sex marker and the nationality. 1104 backend tests pass (was 1062); `check-all.ps1` exits 0.'

$S['3.9'] = '{EM} new readers in `td2.py`: `td2_field` (the one place a TD2 line is sliced), a closed `TD2_DOCUMENT_CODES` (`{"V<", "V"}`), three `parse_*`/`validate_*` pairs (document code, issuing state, **name**, which 3.9 as written omitted) and `parse_td2_line_1`, returning all three in printed order inside a read-only mapping. 1183 backend tests pass (was 1104); `check-all.ps1` exits 0.'

$S['3.10'] = '{EM} `td2.py` gains six `parse_*`/`validate_*` pairs (document number, nationality, date of birth, sex, date of expiry, optional data), a closed `TD2_SEX_MARKERS`, `parse_td2_line_2` (eleven fields, printed order, read-only), `TD2_COMPOSITE_SPANS`, `TD2_CHECK_DIGIT_FIELDS`, `td2_composite_input` and `td2_check_digit_results`. 1327 backend tests pass (was 1183); `check-all.ps1` exits 0.'

$S['3.11'] = '{EM} the rule is one function in `mrz.py` that all three formats delegate to: `MrzDate` (frozen; `year`, `month`, `day`, two printed year digits and **no century**), `parse_date(text) -> MrzDate | None` (six characters of `YYMMDD`; `None` if any of the six is not an ASCII digit) and `date_fault(text) -> "month" | "day" | None`. 1405 backend tests pass (was 1327); `check-all.ps1` exits 0.'

$S['3.12'] = '{EM} `mrz.py` gains `MAX_BIRTH_AGE = 120`, `infer_birth_year(text, reference) -> int | None` and the private `_is_a_real_day(year, month, day)`; `__all__` gains two names, thirteen in all. The answer is the **most recent year carrying the two printed digits that has already happened, was a day that year had, and is not more than 120 years ago**. 1451 backend tests pass (was 1405); `check-all.ps1` exits 0.'

$S['3.13'] = '{EM} `mrz.py` gains `infer_expiry_year(text, reference) -> int | None` beside 3.12''s `infer_birth_year`, exported in `__all__` (fourteen names in all). **The rule is the nearest year carrying the two printed digits that has not already passed**, which is 3.12''s candidate pair with the sign flipped. 1503 backend tests pass (was 1451); `check-all.ps1` exits 0.'

$S['3.14'] = '{EM} `MrzDocument` (declared in `td3.py` since 3.1) is now the common currency of all three formats, carrying a `format` discriminator plus five `| None` attributes for the optional-data fields only a TD1 or TD2 prints, where `None` means "this format prints no such field" and never an empty string. **Breaking change to a published API.** 1580 backend tests pass (was 1503); `check-all.ps1` exits 0.'

$S['4.1'] = '{EM} new `backend/app/pipeline/tier0/mrz_region.py`, the file `ROADMAP.md` B1.10 names, carrying `deskew(image)`, `skew_deg(image)` and `MAX_DESKEW_DEG`. **The skew angle is measured once, by code this project already ships**: `m7_skew` gains one public function. 31 new tests. 1611 backend tests pass (was 1580); `check-all.ps1` exits 0.'

$S['4.2'] = '{EM} `to_gray(image)` and `binarize_inverted(gray)` in `mrz_region.py`, both public; `__all__` is five names and the source-side rule test was updated to match. 27 new tests. 1638 backend tests pass (was 1611); `check-all.ps1` exits 0.'

$S['4.3'] = '{EM} `extract_components(binary)` and the frozen record `MrzComponent` in `mrz_region.py`; `__all__` is seven names and the source-side rule test now walks the AST instead of grepping. `CONNECTIVITY = 8` is a module constant chosen by a diagonal stroke: twelve pixels read as twelve components under 4 and one under 8. **It must be passed by keyword**, because the second *positional* parameter of `connectedComponentsWithStats` is the `labels` output, so `(binary, 8)` silently gets the default. 20 new tests. 1657 backend tests pass (was 1638); `check-all.ps1` exits 0.'

$S['4.4'] = '{EM} `filter_glyphs(components)` in `mrz_region.py` plus four module constants (`GLYPH_MIN_HEIGHT_PX` 8, `GLYPH_MAX_HEIGHT_PX` 24, `GLYPH_MIN_ASPECT` 0.2, `GLYPH_MAX_ASPECT` 2.5). Two bands, each rejecting one of the task''s two blobs. 20 new tests. 1677 backend tests pass (was 1657); `check-all.ps1` exits 0.'

$S['4.5'] = '{EM} `group_lines(components)` in `mrz_region.py`. **The task''s test is measured against what the fixture drew, not against a bare count**, because one group holding both lines answers "2" as comfortably as two groups holding one line each. 14 new tests. 1691 backend tests pass (was 1677); `check-all.ps1` exits 0.'

$S['4.6'] = '{EM} `filter_lines(lines)` plus `LINE_MAX_HEIGHT_SPREAD` (1/3) and `LINE_MAX_SPACING_SPREAD` (0.25) in `mrz_region.py`; both scores are **ratios taken on the group** rather than constants, because a constant would be satisfied by one consistent group. 20 new tests. 1711 backend tests pass (was 1691); `check-all.ps1` exits 0; `compileall` exits 0. Eighteen mutants were run and all eighteen are caught; the throwaway harness under `%TEMP%` was deleted.'

$EM = [char]0x2014
$EN = [char]0x2013

# --- read + split -----------------------------------------------------------
$orig  = [System.IO.File]::ReadAllText($path, $enc)
$lines = $orig -split "`n"

$out = New-Object 'System.Collections.Generic.List[string]'
$i = 0
$inFence = $false
$rewritten = @()
$droppedNoteLines = 0
$droppedBlankLines = 0

while ($i -lt $lines.Count) {
    $line = $lines[$i]

    # fenced blocks are documentation, never task definitions
    if ($line -match '^\s*(```|~~~)') { $inFence = -not $inFence; $out.Add($line); $i++; continue }

    if ((-not $inFence) -and ($line -match '^- \[x\]')) {
        $id = [regex]::Match($line, '\*\*([\d.]+)\*\*').Groups[1].Value
        $out.Add($line); $i++

        # copy the task definition itself: continuation lines through Verify:
        $verifyIdx = -1
        while ($i -lt $lines.Count) {
            $l = $lines[$i]
            if ($l -match '^- \[') { break }
            if ($l -match '^#') { break }
            if ($l -match '^\s*Verify:') { $verifyIdx = $i; break }
            $out.Add($l); $i++
        }

        if ($verifyIdx -lt 0) { continue }   # no Verify: line, nothing to compress
        $out.Add($lines[$verifyIdx]); $i = $verifyIdx + 1

        # consume the note block that follows
        $noteLines = 0
        while ($i -lt $lines.Count) {
            $l = $lines[$i]
            if ($l -match '^- \[') { break }
            if ($l -match '^#') { break }
            if ($l -match '^\s*(```|~~~)') { break }
            if ($l.Trim() -eq '') {
                $j = $i
                while ($j -lt $lines.Count -and $lines[$j].Trim() -eq '') { $j++ }
                if ($j -lt $lines.Count -and ($lines[$j] -match '^\s') -and ($lines[$j] -notmatch '^- \[')) {
                    $droppedBlankLines += ($j - $i)
                    $i = $j
                    continue
                }
                break
            }
            if ($l -match '^\s') { $noteLines++; $i++; continue }
            break
        }

        if ($noteLines -gt 0) {
            if (-not $S.ContainsKey($id)) {
                throw "ABORT: completed task $id has $noteLines note lines but no authored summary. Nothing written."
            }
            # NB: not `$s` -- PowerShell variable names are case-insensitive,
            # so `$s` would clobber the `$S` hashtable.
            $summaryText = $S[$id].Replace('{EM}', $EM).Replace('{EN}', $EN)
            $out.Add('      ' + $summaryText)
            $rewritten += $id
            $droppedNoteLines += $noteLines
        }
        continue
    }

    $out.Add($line); $i++
}

$new = ($out -join "`n")

# --- guards: only note lines may have been removed ---------------------------
$oldHeads = @($lines | Where-Object { $_ -match '^- \[[ x]\]' })
$newHeads = @($out   | Where-Object { $_ -match '^- \[[ x]\]' })
if ($oldHeads.Count -ne $newHeads.Count) { throw "ABORT: task-header count changed $($oldHeads.Count) to $($newHeads.Count)" }
for ($k = 0; $k -lt $oldHeads.Count; $k++) {
    if ($oldHeads[$k] -ne $newHeads[$k]) { throw "ABORT: task header $k changed" }
}

$oldPend = @($lines | Where-Object { $_ -match '^- \[ \]' })
$newPend = @($out   | Where-Object { $_ -match '^- \[ \]' })
if ($oldPend.Count -ne $newPend.Count) { throw "ABORT: pending count changed $($oldPend.Count) to $($newPend.Count)" }

# Strip the 50 inserted summary lines: what remains must be an exact
# subsequence of the original, so nothing was reordered or reworded --
# only note lines deleted and one summary line added per completed task.
$summarySet = @{}
foreach ($r in $rewritten) { $summarySet[('      ' + $S[$r].Replace('{EM}', $EM).Replace('{EN}', $EN))] = $true }
$residual = @($out | Where-Object { -not $summarySet.ContainsKey($_) })
if ($residual.Count -ne ($lines.Count - $droppedNoteLines - $droppedBlankLines)) {
    throw "ABORT: residual $($residual.Count) != original $($lines.Count) minus $droppedNoteLines notes minus $droppedBlankLines blanks"
}
$a = 0
for ($b = 0; $b -lt $residual.Count; $b++) {
    while ($a -lt $lines.Count -and $lines[$a] -ne $residual[$b]) { $a++ }
    if ($a -ge $lines.Count) { throw "ABORT: line $($b) of the residual is not a subsequence of the original: '$($residual[$b])'" }
    $a++
}

[System.IO.File]::WriteAllText($path, $new, $enc)

"tasks rewritten : $($rewritten.Count) ($($rewritten -join ', '))"
"note lines gone: $droppedNoteLines"
"lines          : $($lines.Count) -> $($out.Count)"
"chars          : $($orig.Length) -> $($new.Length)"
