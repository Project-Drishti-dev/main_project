# DRISHTI Project -- Handover

**Updated:** October 3, 2026 -- after task 19.2.  Backend suite: 7056 passes,
check-all.ps1 exits 0, 33 new from this task.

**Workspace:** D:\sih\main_project -- **Frontend:** D:\sih\main_project\frontend

## Working on this tree

- **`@BT@` is not a placeholder this repository writes.**  17.12 left fourteen
  of them in `docs/DECISIONS.md` and `tasks.md` where backticks were meant and
  nothing failed, because the suite never reads the decision log.  17.13
  replaced them; grep for `@BT@` after any write that carries markdown.
- **Sandboxed exec cannot start a process** ("apply deny-read ACLs") and
  **apply_patch refuses this tree** ("path contains a reparse point").  Every
  read, edit and test run goes through escalated PowerShell.  Approve the
  escalation prompt once and the session reuses it.
- **Write a multi-line edit as a Python script in `$env:TEMP`, not as a
  PowerShell replacement.**  On 19.2 four anchored PowerShell edits were
  written and three needed repair: a `$new` built as `'a' + [char]10 +
  'b'` landed one line and left the old one behind, and a `\"` inside a
  single-quoted here-string arrived as a plain `"` -- **the shell eats the
  backslash in an escaped quote**, the same class of loss as the backtick
  below.  A patch script asserts `text.count(old) == 1`, names the label
  it missed and writes bytes, and three of the four repairs were one line
  each once the script existed.
- **A survivor is a claim nothing pins, and the library may be the only
  thing pinning it.**  19.2's sweep left `DATA_KEY_NONCE_BYTES = 11`
  alive: AES-GCM accepts any nonce width, so the round trip still held
  and every case that read the constant agreed with it.  Its sibling
  `DATA_KEY_TAG_BYTES = 8` died for the opposite reason -- the primitive's
  real tag is 16 bytes, so the library refused.  **A constant the standard
  does not enforce needs a case that spells the number**, and a constant
  it does enforce looks pinned when it is only coupled.
- **Two refusals can answer one wrong input.**  A data key of the wrong
  width is caught by `_checked_data_key` and again by the wrapped form's
  own width check, and both messages print `32`, so asserting the number
  passed against either.  **Name which refusal answered** -- the case now
  asserts `"data key" in message`, which only the first prints.
- **A replacement built with an embedded CRLF can silently lose the half
  after it.** 18.7 built both of `main.py`'s edits as `@(...)` array pairs
  whose replacement held `[string][char]13 + [char]10`, and `String.Replace`
  wrote only the text before the CRLF -- `routes_health` and
  `app.include_router(health_router)` were deleted from a file that still
  parsed.  Build the join with `[string]::Concat([char]13, [char]10)`, insert
  one line at a time, and read the file back rather than trusting the anchor
  count.
- **Line endings are mixed here, so a here-string anchor can be written
  against the wrong one and report "anchor missing" with no error.**
  `backend/app/api/routes_screenings.py` is CRLF;
  `backend/app/audit/decision.py`, `backend/tests/api/*.py`, `tasks.md`,
  `docs/DECISIONS.md` and this file are LF.  Count CR against LF on read,
  build the anchor for the file actually being edited, and count them again
  after the write.  18.2 lost two rounds to it.
- **Writing a whole file is one WriteAllText, not a patcher.**
  `[System.IO.File]::WriteAllText(path, $c + [char]10, (New-Object
  System.Text.UTF8Encoding($false)))` with `$c` a single-quoted here-string
  writes it LF-only with no BOM.  The here-string holds apostrophes and
  backticks; the only thing it cannot hold is a line beginning `''`.  A
  here-string also drops its final newline, hence the `+ [char]10`.
- **Three quotes written where two were meant swallow the rest of the file.**
  Writing `"""` into a line that should hold `"""""` opens a
  docstring at the first `"` and every later function becomes part of its
  body.  **Nothing complains**: `ast.parse` succeeds and pytest collects only
  what came before the swallow, so the run is green over half a file.  Count
  the functions (`python -c "import ast,pathlib; m=ast.parse(...); ..."`) and
  compare with `pytest --collect-only -q` before believing a count, and treat a
  mutation "survivor" as a possible writing fault before treating it as an
  untested line -- two survivors on 17.11 were this and nothing else.
- **One here-string per assignment, each closed by an `''` at the start of
  its own line.**  Starting `$b = ''` before the first block's `''` swallows the
  second block into the first: the run reports success and lands a truncated
  file.  It cost a `__init__.py` with no closing `"""` on 17.1.  Read back the
  last lines of each file written before running anything on it.
- **Editing an existing file is ReadAllText, one anchored Replace,
  WriteAllText**, all in one block: assert `$t.IndexOf($old) -ge 0` and that it
  equals `LastIndexOf($old)` before replacing, or a stale anchor writes
  twice.  Write both halves as here-strings -- the repo is full of markdown
  backticks, which a double-quoted PowerShell string eats.  **A `Replace` built
  from `"` + `` `r`n `` + `"` injects CRLF into an LF file; check the count
  afterwards** and `.Replace("`r`n", "`n")` if it changed.
- **A single-quoted PowerShell string does NOT expand `` `n ``.**  It keeps the
  backtick and the letter, so a multi-line anchor written as
  `''...:`n...''` silently fails to match and a mutation is skipped as "anchor
  absent".  Use a here-string for any anchor spanning a line break.  **The same
  trap has an inverse: a Python anchor for a literal backslash-n needs
  ```n` in the Python source**, or the anchor holds two real newlines and
  matches nothing (mutant 20 on 17.11 was skipped that way).
- **Read the file's real bytes before trusting an anchor typed from an earlier
  read.**  On 17.7 an import line spelled `sqlalchemy.exc` in the file and
  `sqlalchemy.exceptions` on screen, and the mismatch was silent until
  `IndexOf` answered -1.  When an anchor is reported missing twice, dump
  `(Get-Content $p -TotalCount 7) -join ''|''` and compare rather than retyping.
- **`tasks.md` indents a task body by TWO spaces**, not four, and the 16.5
  arrow is `<->` (U+2194) rather than the `<->` the reader sees.  A hand-typed
  anchor missed on both.  **A task's `Verify:` line is `  Verify: the new test
  passes.` with two leading spaces, and a four-space anchor is simply not
  found** -- `IndexOf` answers -1 with no error.  17.5 lost a round to exactly
  this.  When an anchor is reported missing, re-read the exact lines rather than
  retyping them.
- **An anchor built in a double-quoted PowerShell string needs `"` escaped as
  `` `" ``, and a here-string built for the same file will not match it.**
  Two 16.6 edits failed on exactly that.  For a small anchor with no newline,
  a single-quoted PowerShell string holding `"` literally is the reliable form
  -- and on 17.11 a search string holding `"` matched 0 times against a file
  whose quotes were real, which cost a round for the same reason.
- **Do not build a Python line by substituting PowerShell variables into a
  placeholder.**  On 17.7 `${...}` inside an `f"..."` here-string landed in
  the file as `${LOCAL_LLM_TIMEOUT_ENV_VAR}` and broke the parse.  Write the
  Python line as it should read.
- **pytest needs `-p no:faulthandler`.**  The full backend run is `2.5 minutes and
  `check-all.ps1` ends with `ALL CHECKS PASSED SUCCESSFULLY - 3 of 3
  stages`; pass `yield_time_ms` and poll rather than assuming either finished.
  Truncating its output with `Select-Object -Last 30` drops the pytest count, so
  redirect the whole run to `$env:TEMP` and `Select-String` the count out of it
  -- and beware `Select-Object -First`, which stops the upstream pipeline early.
- **`scripts/verify-compact.ps1` and `scripts/verify-handover.ps1` are dead.**
  Do not run them.
- **Run the mutation sweep before ticking a task.**  Apply each shipped line's
  removal in place, re-run the suite, revert from a string held in memory.  A
  line that survives is either untested or dead, and the two need different
  answers.
- **A sweep is a throwaway script in `$env:TEMP`, never a repo file.**  Hold
  `ORIGINAL = TARGET.read_bytes()`, apply
  `ORIGINAL.decode("utf-8").replace(old, new, 1)` per mutant, `subprocess.run`
  pytest per mutant, restore in a `finally`, then assert
  `TARGET.read_bytes() == ORIGINAL` at the end.  Assert the anchor count is 1
  before each apply so a stale anchor is reported rather than counted as killed.
- **In a sweep, hold the bytes, not the text.**  `path.write_text()` on Windows
  turns the whole file CRLF, so a restore checked with `read_text()` compares a
  rewritten file and the sweep quietly lands a diff.  Use `read_bytes()` /
  `write_bytes()`.
- **Measured on this host: a connection to a closed loopback port is silently
  dropped, not refused.**  `socket.create_connection` to a released port times
  out (2.03s against a 2s budget) instead of answering `WSAECONNREFUSED`, so a
  case asserting a refused connection comes back "within the budget" rather
  than "immediately" -- and a stub that dials the wrong port in a test costs the
  whole budget rather than a millisecond.
- **`ThreadingHTTPServer` teardown is `poll_interval` wide.**  `shutdown()`
  waits up to the default 0.5s per stub, which was 10s of the 29s the 17.7
  file first took; `serve_forever(poll_interval=0.05)` took it to 8s.
- **A placeholder that can pair with the next character loses one of them.**
  On 18.12 a here-string written with \docs/DECISIONS.md\ arrived as
  ``docs``DECISIONS.md`` -- the pair was read as an escaped slash, and the
  placeholder's own character went with it, so the anchor simply missed with
  no error.  **Use a character that pairs with nothing**: 18.12 wrote `` for a
  double backtick and ` for a single one, and probed ``IndexOf`` on the built
  anchor before editing anything.
- **A sweep anchor written with a bare newline finds nothing in a CRLF file**,
  so that mutant is reported SKIP and never run at all -- 18.12 skipped
  `routes_screenings.py` that way and re-ran it with the CRLF built from
  `Concat([char]13, [char]10)`.  A sweep reaches every file its edit touched,
  and SKIP is not killed.
- **A sweep must restore after EVERY mutant, not once in a `finally`.**  A
  mutant that rewrites the line the *next* mutant anchors on leaves that
  anchor at count 0, so four of thirteen were reported SKIP on 17.8 and one
  real survivor was never tested.  Decode `originals[path]` fresh per mutant,
  write it back immediately after the subprocess, and keep the `finally` as
  a safety net.  **SKIP is not killed** -- count it as untested.
- **`$decision.TrimStart("`n")` silently joins two markdown sections.**  On
  17.8 it ran `...operator names a model.## D137 --` onto one line, and
  `Select-String '^## D137'` then found nothing while the file was still valid.
  A here-string opened by a newline already ends with one: use `$block`
  directly, or `.TrimStart("`r`n")` only when you know the caller adds one.
  **Read the bytes at the seam before moving on.**
- **One doubled RST pair in one file collapsed and nine hundred did not.** A
  probe that reads "backticks survive a here-string" is wrong: on 18.7 one
  literal arrived as a single backtick while every other pair in the same
  write was intact, and the file still parsed. After each write, mask every
  double-backtick literal and every single-backtick role reference with a
  regex and report the lone backticks left -- the throwaway `check_ticks.py`
  in TEMP does this and names the line rather than the prose.
- **The shell eats a raw backtick and collapses a doubled apostrophe.**  Write
  file content with the placeholders \, ' and " and substitute
  [string]([char]96), [string]([char]39) and [string]([char]34) afterwards; a
  here-string meant to carry Python quoting lands three backticks in the file
  and a SyntaxError.  When the text itself has to carry one of those
  characters, spell it as a second placeholder and substitute that too.
- **A Replace against a char does not bind.**  $c.Replace("\\", [char]96)
  picks the (Char, Char) overload and throws, so bind $tick =
  [string]([char]96) first and pass the strings.  A doubled apostrophe written
  in a command arrives as one, which is right for prose and wrong for the three
  that open a Python string.
- **A backslash-n written in a here-string is two characters**, which is what a
  Python anchor wants: the sweep anchors matched real line breaks that way.  A
  PowerShell newline has to be built as [char]10.
- **A backtick placeholder stands for a backtick and nothing else.**  Spelling an
  apostrophe as the same placeholder (`D133`s extractor) matched 0 times against
  a file whose apostrophe was real, and cost two rounds on 17.12.  Normalise the
  file you are editing on read -- replace every backtick with the placeholder, do
  the edit, substitute on write -- and leave apostrophes alone.
- **One character, two spellings.**  ``docs/DECISIONS.md`` and every
  Python source write RST *double* backticks where `tasks.md` and this
  file write *single* ones, so an anchor typed with the wrong count is missing
  rather than wrong and `IndexOf` answers -1 with no error.  18.3 lost
  one round to each, in that order.
- **A refused token is on the record by design.**  `unsupported` repeats every
  token a refusal was for, so a test asserting that no token of a poisoned
  answer survives *in the response body* fails against the design rather than
  a bug -- assert against `record.summary` instead.  17.12 lost a run to it.
- **A refusal names what the payload left out, so the set moves with the
  payload.**  The same poison names `2024` as well as `SIH` over an empty flag
  set, because nothing else printed a year; a case covering every scan asserts
  the names are tokens the poison wrote, not one fixed set.
- **Read a shipped design before asserting against it.**  17.12 asserted a
  stronger rule than D140 records, and the suite was right to refuse it twice.
- **A placeholder has to be substituted in the anchor too, not only in the
  file.**  18.5 built an anchor holding the placeholder and compared it against
  text carrying real backticks, so `IndexOf` answered -1 and the failure read
  as a stale anchor rather than as a typo.  Substitute into `$old` and `$new`
  in the same block.
- **A multi-line anchor into a CRLF file needs ``\r\n`` written into it**, and a
  sweep that reports SKIP is reporting a missed mutant, not a surviving one.
  18.5's first pass skipped two of seven this way -- the only multi-line
  anchors were the ones the shell had written with a bare newline.
- **A ``\`` placeholder next to a real backtick came out as four.**  Writing
  ``\``\`` for a pair of RST backticks put four in the file (harmless in a
  docstring, wrong everywhere else); `[regex]::Replace(c, tick + '{2,}', tick
  + tick)` collapses every run to the two this repository writes in
  `docs/DECISIONS.md`.
- **A placeholder token expands to exactly one character.**  18.11 wrote a
  doubled RST literal as one token pair and got a single backtick on each
  side, in a file whose prose is doubled throughout: `ast.parse` accepted it,
  pytest accepted it, and only a lone-backtick regex caught it.  A doubled
  literal needs a token that expands to *two*, and the doubling has to be
  spelled per file rather than assumed from a neighbouring write.
- **Type the apostrophe.**  A possessive written with a backtick token
  arrives as a doubled backtick instead of a quote, and the line reads
  as damage rather than as a typo.  A single apostrophe inside a
  here-string is safe; only a line that *begins* with one closes it.
- **`@( @($a,$b), @($c,$d) )` is not two pairs.**  Given a single argument
  PowerShell wraps instead of splitting, so `$pair[0]` arrives as an array
  holding both strings, the anchor coerces to one long value, `IndexOf`
  answers -1, and the error names the wrong thing entirely.  Use
  `[pscustomobject]@{ Old = ...; New = ... }` and the count check still runs.
- **A `response_model` drops an undeclared key silently**, so a case
  asserting the document holds three keys passes against a producer that
  emitted a fourth: the schema filtered it before the case saw it.  What
  catches that is the comparison against the other route's answer, which
  nothing filtered.

- **A line beginning with an apostrophe placeholder lands, but at column
  zero**: on 19.1 the ``'s`` of a possessive came through intact and
  unindented, so a docstring read as if the sentence were on the floor. Read
  the written file back, and never start a line with a placeholder a
  following character can pair with.
- **`@( @($a,$b), @($c,$d) )` is not two pairs** -- already recorded for 16.6
  and it cost a round again on 19.1, where one pair applied and the next was
  checked against a stale `$t`. **Do several edits as several explicit
  `$old`/`$new` blocks**, never a loop over an array of pairs.
- **A blanket `.Replace` over a whole markdown file turns one mistake into
  five**: replacing ``` `s ``` with ``` `'s ``` on 19.1 reached five places
  in `docs/DECISIONS.md`. It happened to be harmless -- it only inserts an
  apostrophe a typo was missing -- but scope a replace to the block you wrote
  and grep the file after.
- **`workdir=backend` doubles a relative edit path** into
  ``backend/backend/tests/...``, and the edit then silently does nothing.
  Keep every edit path rooted at the repository root, whichever directory the
  command runs in.


- **A case that names instants of its own is a claim about the wall clock.**
  18.10's `EARLY`/`LATE` are fixed at 09:00 and 09:05 UTC on October 3, 2026,
  so the moment the suite ran past them the assertion described the hour rather
  than the reader. Three attempts read that as a defect in the case; the root
  cause was in `app/` after all, and the fix was a reader that orders a run's
  timeline -- never a case rewritten to match the clock.

## Resume from here

### Last Completed Task

**19.2** -- `app.storage.data_key`: a per-blob data key drawn fresh and
wrapped under the master key with AES-GCM, and opened back by
`unwrap_data_key` (D156).
- **The round trip is the task, and it is asked sixty-four times**: a
  generated key that is wrapped and opened is the same bytes, and 256
  draws are all distinct and none equal to the master key they sit under.
- **The nonce is drawn, not counted.** `DATA_KEY_NONCE_BYTES` is 12 and is
  **pinned by a case rather than by behaviour**, because AES-GCM accepts
  any other width -- that mutant survived the first sweep.
- **A wrapped key that does not open is refused, not returned.**
  `DataKeyError` names the wrong key and the altered value, which AES-GCM
  cannot separate, and is raised `from None` so the traceback carries this
  module's message and not the library's.
- **The wrapped form has one width** -- 12 beside 48 -- and is checked
  before any cryptography runs, so a truncated value is a refusal and
  never a decrypt.
- **Two refusals can answer one wrong input.** A short data key is caught
  by its own width check and again by the wrapped form's, so the case
  names which refusal answered instead of asserting a number both print.
- **7056 backend tests pass and `check-all.ps1` exits 0**; 23 mutations of
  D156's lines, all 23 killed, every file restored byte-identical.

### Current State & Key Decisions

- **A blob is encrypted under a key of its own, and that key under the
  master key** (D156): `generate_data_key` draws `DATA_KEY_BYTES` (32) per
  blob, `wrap_data_key` seals it with AES-GCM under a nonce drawn per wrap,
  and `unwrap_data_key` opens it. A data key is never derived from the
  master key and held nowhere, on `app.ledger.salts`' reasoning.
- **The wrapped form has one width and one owner**: a 12-byte nonce beside
  48 bytes of ciphertext, `repr=False`, refused before any cryptography
  runs if either is another width, and reachable only through a
  `WrappedDataKey` -- `MasterKey.key` bytes handed to either half are a
  `TypeError`, so the attribute is not the API.
- **A wrapped key that does not open is refused rather than returned**
  (D156): `DataKeyError` is a `ValueError`, names the wrong key and the
  altered value as the two readings AES-GCM cannot separate, quotes
  neither key, and suppresses the library's context.

- **The evidence master key is loaded, generated, or refused, and never a
  constant** (D154): `app.config.get_app_env` is the only reader of `APP_ENV`
  (`development`/`production`, folded, trimmed, unset meaning development)
  and `get_evidence_encryption_key` the only reader of
  `EVIDENCE_ENCRYPTION_KEY`, so `load_master_key(configured, environment)` is
  handed what those two answered. A missing or blank key is generated per call
  in development and refused in production; an unreadable mode is refused
  rather than read as development; a malformed or wrongly sized key is refused
  in both modes; and every refusal names the variable without quoting any of
  the value.
- **`MasterKey` is 32 bytes, frozen, `repr=False`, and carries the mode and
  whether it was generated** -- so a caller can tell a key worth persisting
  from one that is not, and a traceback cannot print the key in any of its
  three spellings. One width, pinned at 32, because AES-GCM is driven at
  AES-256 here.
- **Nothing stores a blob yet and nothing loads a key in the flow.** D156's
  wrap is the envelope alone, the production refusal still fires the first
  time something asks for a key rather than at start-up, and 19.3 is what
  puts bytes under a data key with 19.6 putting the store in the flow.
- **A stage's cost is a window the trail recorded** (D153): the answer
  carries `stage_trace` -- `total_ms` beside `stages`, each stage `tier`,
  `recorded_at`, `elapsed_ms` -- and `app.progress.build_stage_trace` builds
  it off the same `_run_events` walk `build_progress` uses, so the trace and
  the two progress routes cannot count the trail differently.
- **Progress is a read, and `app.progress` owns its sequence** (D151): a tier
  is `completed` because the trail wrote a `tier_completed` event naming it,
  and a module is `reported` because a stored finding names it -- so a module
  that ran and found nothing carries no step, and the stream never claims it
  did not run.  A frame is a name line, one sorted object and a blank line,
  and carries nothing read off the document.
- **Both reads finish before the first byte is written**, so a 404 arrives as
  the shared envelope rather than as an error pushed down a stream a caller
  has already started reading, and no session is held open while it reads.
- **A tier's two spellings are left unreconciled** (D151): the trail names
  `tier_0` and a finding names `0`, and the stream reports what each record
  said rather than merging them on a crosswalk D151 did not design.
- **`app.screening.TIER_KEY` is the one spelling of the payload key** a
  `tier_completed` event names its tier under, so the writer and the reader of
  that key cannot drift apart.


- **A report is a read, and `app.reporting` owns its markup** (D150): the
  page references no external asset, prints every stored value escaped, and
  carries the band, the findings with their own reasons and the audit id --
  and neither a filename nor a value read off the document.  The reason
  floor in `app.explain.reasons` is deliberately not reached; 23.8 is where
  that and a decision reach a screen together.
- **The report route is the only one that spells its error envelope as an
  OpenAPI pointer** rather than as the model, because FastAPI takes an
  additional response's media type from the route's response class; 11.4's
  own case holds the pointer.
- **A verify answer names the checks that ran, and only those** (D149):
  `GET /api/audit/{audit_id}/verify` answers `verified` / `altered` /
  `unknown` with the batch it reached, the root as the log spells it, the
  length of the walked proof, and one plain sentence per check that
  completed.  An event no batch has claimed, and an id no row carries, both
  answer `unknown` with nothing named -- and an id no row carries is a 200,
  not a 404, because the question was answerable.
- **The one walk is 9.17's** and `verify_event` is its `status`; the route
  asks the record rather than walking again, and the sentences live in one
  table keyed by that module's own check constants (D149).

- **The signature over the anchored root is not checked** by anything in the
  service: 18.7 proves the root is the batch own and 18.8 that a moved
  payload is caught, not that the signature over either is sound.

- **Both halves of a tampered trail are now walked** (D149): 18.7 moved a
  ledger entry root, so the record still hashed and only the proof answered,
  and 18.8 moves a stored payload, so the record disagrees and the proof is
  never walked at all.

- **A delete is a stamp every read already refuses**, and it removes nothing
  (D147): `DELETE /api/screenings/{id}` answers 200 with the id and the instant
  it stamped, 404 for an id no *live* row carries, and the item read, the list
  read and every filter answer 404 or an empty page for a row that was stamped.
  A second delete is that same 404 rather than a second stamp, and the trail is
  untouched — which 18.6 now holds by walking every event back to its
  anchored root rather than by counting rows.

- **A decision is taken at a URL, refused in the same envelope, and written to
  the trail; nothing moves on the row** (D143, D144, D145).  A second choice
  is answered beside the first: a new event naming what it took over from,
  with where either stands read off the trail's order rather than stored
  anywhere (D146).

- **`OFFICER_ACTIONS` is the only spelling of the officer's three
  choices in `app/`**, and `app.audit.decision` now owns the
  rule, both the events and the writing of them, so the route asks that one
  module (D70, D143, D145).

- **A row carrying no band is asked nothing and overrides nothing**, which is
  why 18.1's unscored fixtures answer 200 and record a choice alone (D144,
  D145).

- **A refusal writes nothing**, and an unreadable choice is refused by the
  writer before either event, so the trail never carries half a decision
  (D144, D145).

- **The guard on model text is a token rather than an intent** (D141), so the
  guarantee that poisoned output never reaches a response is asserted on six
  poisons and stops where the extractor stops -- two carrying no readable
  token are delivered, and the test file names them.

- **A refusal repeats the offending tokens in `unsupported` and nothing
  else** (D141): `unsupported` is the record of a rejection, not the
  text of one (D140).

- **The narration path is seven modules**: `verifier`,
  `template`, `payload`, `summarizer`,
  `prompts.loader`, `prompts/v1.txt` and `narration` --
  `explain` re-exports nothing, so a caller says which module it took a
  name from, and both a prompt and the data it is sent are values rather than
  strings (D138, D139, D140).

- **`narrate` is the only caller of the loader, the payload builder and
  the summariser**, and the prompt it sends is the loaded text, then the
  payload JSON, joined by one blank line (D140).

- **A summary reaches an officer only as a `Narration`**, and its
  `summary` is either model text the verifier passed or 17.5's template
  -- there is no third source and no partial repair (D140).

- **The payload is a whitelist of field names and `region` is the field
  left out of it**, so nothing about a pixel reaches a model, and 17.11 is the
  first thing that actually sends it (D139, D140).

- **A verdict is a `(bool, tuple[str, ...])` pair and never an
  exception** (D134), and `verifier.py` still imports `re` and
  `app.risk.flag_ids` and nothing else -- which is how Part 17's "no
  model" claim is held.

- **`Summarizer` is one abstract `summarize(prompt) -> str | None`
  carrying `model_name`**, and 17.11 is what names that model on a record
  whose summary the model wrote; a subclass wired wrongly fails at construction
  (D136).

- **`None` is the whole failure contract of the client** -- absent
  model, blank prompt, address naming no server, refused connection, late
  body, non-200, payload carrying no text -- and the client has no second
  address to try.

- **A malformed base URL or a budget below one second is refused in
  `config.py` instead**, naming the variable at start-up, like
  `DATABASE_URL` and `RATE_LIMIT_PER_MINUTE` (D36, D78).

- **`LOCAL_LLM_MODEL` blank is the shipped state and is not a
  refusal**: no model named is a client answering `None` to everything.

- **A switch value this reader does not understand is off, not a
  `ValueError`** -- both answers are ordinary and only one is safe to
  guess at, where a malformed address is a refusal because it silently
  disables the client anyway (D36, D78, D137).

- **`LOCAL_LLM_ENABLED` gates the whole narration path and defaults to
  off** (D137), read once in `LocalLLMClient.__init__`; while it is off
  `summarize` answers `None` without dialling, and 17.5's
  template is the summary.

- **The fallback summary is a fixed three-sentence frame plus one line per
  flag, and every line is the flag's own `reason`** (D135).

- **`app/explain/reasons.py` holds one fixed sentence per flag id**,
  read by `reason_for` and keyed by the registry's own constant; no slot
  is filled from the finding, so the floor cannot quote a document and cannot
  be refused (D142).

- **Those sentences are a floor beneath a rule's own `reason`, not a
  replacement for it** -- 17.5 still narrates each finding in the wording the
  rule wrote, and the table is what an officer has when a rule wrote none.

- **A summary is built from `EvidenceFlag` objects and verified against
  the payload it was sent** -- same flag data, two shapes, and the narration
  side refuses the mapping.

- **`crossdoc` has four modules** on a 0-byte `__init__.py`
  (D127), and **`explain` has seven**, beside `risk`,
  `audit` and `quality_checker`.

- **A case holds no verdict, no score and no band** (D126); a result becomes a
  flag unconditionally and never a dropped one (D125).

- **`hard_fail_reason` is still the one stop** (D107, D113) and
  **escalated is still derived, never stored** (D109); the four triggers are
  still not wired into `run_cascade`.



- **A run's timeline opens at the instant its own `screening_created` event
  carries** (D155), so an event stamped before it -- a clock that moved
  backwards, or a row a writer backdated -- is walked last, and each group
  keeps D151's instant-then-id order; a run whose clock never moved is in the
  order it was written in, and a run that opened with no event of its own is
  left as the trail holds it.

### Known Issues / Blockers
- **Nothing loads a master key**, as D154 records: 19.1 is the loader and 19.2
  the envelope, so a deployment running `APP_ENV=production` with no key
  keeps serving until 19.6 puts the store in the screening flow.
- **A wrapped data key has no spelling to persist.** `WrappedDataKey` is a
  pair of byte fields and nothing assembles them for a column or a filename,
  so the wrapped form is unreachable on disk until 19.3 or 19.6 does (D156).
- **The wrap is bound to nothing but its nonce.** AES-GCM is called with
  `None` as associated data, so a wrapped key is not tied to its blob or its
  hash and moving one is not detected; that belongs with the reference
  format 19.3 designs (D156).

- **The stream shows a run that has already finished.**  `POST` screens
  inline and answers with its ids only once the cascade is done, so nothing
  observes a run in flight; a live feed needs the cascade off the request
  thread and its progress stored, and no task in `tasks.md` claims that.
- **A module that ran and found nothing leaves no step** (D151): a stored
  finding is the only record a module has, so a clean module is absent from
  the stream rather than reported as clean.
- **The two spellings of a tier are never joined** (D151): the stream
  reports `tier_0` and `0` side by side, so a client joins them itself.
- **The gap between the last stage's window and `total_ms` is the scoring
  and the store** (D153): the trail records no instant between
  `tier_completed` and `analysis_completed`, so it can be stated and not
  charged to a stage.
- **A cascade that raised has no row in the stage trace** (D153): a tier
  that never returned wrote no `tier_completed`, so the trace cannot say what
  it cost.
- **Nothing in the frontend opens either progress route.**  Both are served
  and tested; no page under `frontend/` connects to the stream or polls the
  document, so an officer reaches both by typing the URL (D151, D152).

- **Nothing in the frontend opens the report.**  The endpoint is served and
  tested, and no page under `frontend/` links to it, so a page an officer
  files is reached by typing the URL.
- **`unknown` names what ran, not why it stopped.**  A caller that needs the
  reason must read the log beside the answer; no error code or reason field
  distinguishes "no batch" from "no entry" from "no root" (D149).

- **`screening_deleted` is a name with no writer.**  10.1 reserved it, nothing
  emits it, and no task in `tasks.md` claims it -- so a deleted screening leaves
  a stamped row beside its original trail with nothing anywhere saying the
  delete happened.  18.5 deliberately did not fold the event in (18.1/18.3's
  split), which leaves the event itself unassigned rather than done.

- **Nothing reads a reason template yet.**  `reason_for` has no caller
  outside its own test, so an officer-facing screen still narrates a finding
  only in the rule's own words, and a rule that wrote no reason is a bare id
  on screen.  23.8 is where that wiring is, as it is for the narration.

- **Nothing writes a `Narration` anywhere yet.**
  `Screening.summary` still has no writer in `app/`,
  `ScreeningResultResponse` still carries no `summary_source` or
  `verification`, and `app/api/routes_screenings.py` reads a
  column nothing fills.  The narration is built by tests and by nothing else;
  23.8 and Part 11's wiring are what put it on a screen.

- **16.2 is ticked and was never implemented.**  `Screening` carries
  no `case_id` and no `document_role`, and 16.3 through 16.7
  were built around that.  It is a second migration rather than an amendment
  to `be3f9e1a6e14`.

- **16.8 is ticked and only partly shipped.**  `tier: "crossdoc"` and
  one score-aggregation case exist, but no test names the task and this file
  was never updated for it.

- **The fusion still does not exist**, so no Tier 2 or crossdoc flag reaches a
  screening record.  15.6 and 15.7 remain ticked with nothing behind them.

- **`DEEP_MODULES` is still empty**, so Gate 15 is unmet and nothing
  writes a `traveler_cases` row; all four document rules are reachable
  only from tests.

- **No local model server has ever answered.**  17.7 and 17.8 are proved
  against a stub on loopback; `LOCAL_LLM_MODEL` is blank,
  `LOCAL_LLM_ENABLED` ships false, and nothing in the repository has
  talked to a real Ollama.  So every record the shipped configuration
  produces is `not_checked`.

- **`ELA` locates the left 16px of a 48px rewritten patch**, and
  nothing widens it.  Recorded rather than tuned.

- **`SUSPECT_LEVEL` at 0.0116 is a false-alarm risk** off a fixture
  this repository drew (D123).

- **A broken shipped stage is still quiet**, and there are still two cascades
  (`orchestrator.run_cascade` and
  `app/screening.py::_run_cascade`).

- **D133's extractor still cannot read a snake_case field name.**  17.6 closed
  the gap for the fallback, which never writes `field` (D135), and 17.11
  discards whatever the verifier refuses -- but **17.12 exercised the gap and
  left it open**: an underscored claim reaches the response with
  `verification: passed` beside it, and so does a verdict flipped in
  ordinary words, which carries no token at all.  Both are named in the new
  file (D141) rather than left out of it.

- **The comparison is a substring search, so it is generous**, and a one-digit
  number cannot be used to test the fallback: every digit from 0 to 9 occurs
  inside a printed date or value, so `0.42` is the smallest token
  genuinely absent.  Recorded rather than tightened.

- **The shipped prompt's exact prose is untested by choice**, and the one
  sweep survivor is that: a reworded rule in `v1.txt` passes every test
  (D138).

- **``docs/DECISIONS.md`` D75-D103 still end mid-sentence**; D104-D145
  are whole.

- **`tasks.md` has a typo at 16.1** -- "round-tripping" -- left as
  found.

### Immediate Next Step

**19.3** -- `put(bytes) -> blob_ref` writing AES-GCM ciphertext under a
content-addressed filename, with a round-trip test.
