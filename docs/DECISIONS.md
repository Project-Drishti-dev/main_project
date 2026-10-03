# DRISHTI — Settled Decisions

**Created:** September 30, 2026
**Purpose:** Record the three decisions that are already settled so a future
session does not re-litigate them. Each one was a real fork, it was decided
deliberately, and reopening it costs time without a visible benefit.

**Status of this file:** these decisions are **closed**. Do not re-open one
because the lorebook or an earlier design note says something different. If a
decision genuinely must change, that is a new, explicit decision with a new
entry at the bottom of this file — not a silent edit to an existing one.

Related documents: `ROADMAP.md` (strategy), `tasks.md` (executable checklist),
`handover.md` (session state), `lorebook/` (domain context, not architecture).

---

## D1 — The frontend is vanilla HTML/CSS/JS; no React

**Status:** settled · **Settled by:** project maintainer

The six shipped pages (`home`, `screenings`, `settings`, `guide`, `about`,
`profile`) are plain HTML with `home.css` / `pages.css` and plain JS modules
(`home.js`, `pages.js`, `preferences.js`). There is no build-time framework
step beyond `frontend/build.cjs`, which copies files and generates
`dist/api-config.js`.

**Why**

- The lorebook mentions React + Tailwind. The repo is deliberately not that,
  and the two have diverged for the whole prototype.
- UX4G is the government design mandate for this project, and
  `ux4g-web-components@2.1.0` is explicitly framework-neutral: it supplies CSS
  components and a runtime usable from plain HTML. A framework migration buys
  nothing a judge can see.
- Six pages and 45 passing tests already exist. A rewrite costs roughly two
  days of the demo runway and adds no capability.

**What this forbids**

- No `package.json` UI framework dependency, no JSX/Vite/Next/webpack app
  shell, no component build step, no Tailwind.
- The Cloudflare Pages build stays `node frontend/build.cjs`.

**Revisit only if** the roadmap grows an interactive surface that genuinely
cannot be expressed as page-level JS — and then as a new decision, not by
quietly adding a framework.

---

## D2 — No authentication for now

**Status:** settled · **Settled by:** project maintainer

The public demo and the API are unauthenticated. There is no login,
registration, logout, password-reset, or password field anywhere in the
frontend, and the Cloud Run API has no auth and no rate limiter.

**Why**

- The prototype shipped a mock credential flow. Cloudflare's security team
  served a phishing interstitial over it, and the mock flow was removed. Mock
  credential collection is a real harm here — it misrepresents the project to
  visitors and to the host — so it is not an acceptable shortcut.
- There is no auth backend to talk to. A form that collects a password and
  discards it is worse than no form.
- A quality-checker demo needs to be openable by a judge in one click, with no
  account to create first.

**What this forbids**

- No password input, no "Change password" affordance that is not
  `aria-disabled="true"` and explicitly labelled as having no account behind
  it, and no demo copy implying the product has accounts.
- Never add a credential field that does not talk to a real authentication
  backend. The user has not authorised one.

**When this changes** — real auth is planned, backend-first. Build argon2id
hashing and JWT issuance on the server (`app/auth/*`) and only *then* add
sign-in UI, on a separate operator route, never on the public demo page. The
profile page stays an explicitly labelled sample until an API actually serves
an officer identity.

**Related but separate:** the open API needs rate limiting and a
`PUBLIC_DEMO` mode before the model-loading tiers land. That is a security
task, not an auth task, and it does not reopen D2.

---

## D3 — The UX4G default light theme ships as the default

**Status:** settled · **Settled by:** project maintainer

The application renders with UX4G's own default light theme. `preferences.js`
defaults to `{ theme: "light", textSize: "default" }` and sets
`data-theme="light"` on the root element, loaded synchronously in `<head>` on
every page so there is no flash of the wrong theme.

**Why**

- The user has already chosen the default theme. It is not to be re-asked
  unless a branded theme is explicitly requested.
- UX4G's own token set is the mandate. Inventing custom theme-token overrides
  creates a second source of truth that can drift from the design system.
- Dark and system themes remain available at runtime because they are
  UX4G's own tokens, not a custom theme. A visitor's choice persists under the
  single key `drishti.preferences.v1` and is only a preference — it does not
  change what ships.

**What this forbids**

- No custom UX4G token overrides, no rebrand palette, no hand-rolled colour
  scale, and no forked stylesheet.
- The accessibility toggle stays a text-size preference, not a theme.

**Revisit only if** the user explicitly asks for a branded theme. When a new
page is added, the `ux4g-design` preflight still applies, and the theme
question is already answered by this decision.

---

## D4 — Part 4's test MRZ is a drawn monospaced face, not rendered text

**Status:** settled · **Settled by:** 4.14's measurements

`backend/tests/fixtures/mrz_images.py` draws every synthetic MRZ page in this
repository, and it draws it one character per fixed-width cell from a 5×7
pattern table. `draw_page` takes a size, an angle, an exposure and a noise
level; `read_zone` reads the characters back out of the pixels; `render_format`
draws one of the three shapes and refuses any other.

**Why**

- `cv2.putText` in `FONT_HERSHEY_SIMPLEX` is *proportional*. Measured on one
  zone it advances 12.4 pixels on line one and 13.0 on line two, and the
  glyphs touch: two 44-character lines come out of `extract_components` as 24
  and 27 blobs. No test on that page can reach a named format, and no pitch
  read off it is the standard's, so every claim about a cell count or a
  character pitch was being made against a face the project had drawn wrong.
- Character *k* has to occupy a known box for Gate 4 to mean anything. "Every
  MRZ field has a pixel region" is only checkable if the characters' own boxes
  are known independently of the cut, and a proportional face does not give
  them.
- The gap is four pixels and the cell sizes in the sweep are whole multiples
  of 5 and 7. Both are measured, not chosen: at a gap of 1 a page turned to
  four degrees merges 44 glyphs into 23 to 26 blobs, at 2 a TD3 turned
  anticlockwise loses one, and 3 is the first gap exact on all three formats
  at both signs. A cell size that is not a multiple of the pattern loses
  columns — at 8 by 12 the 5x7 pattern reads `8` back as `O`.

**What this forbids**

- No test in Part 4 may go back to `cv2.putText` for a page whose claim is a
  cell count, a cell index, a field box or a named format.
- No second shape table and no second specimen. The generator reads
  `document.MRZ_SHAPES` and `mrz.CHAR_VALUES`, and `test_mrz_region.py`
  parses the generator's own `SPECIMENS`.
- The character reader stays in the fixture. It is a nearest-pattern match
  over the drawing's own ground truth, and it is not a claim about Part 5's
  recogniser or about anything in `app/`.

**Revisit only if** a real capture replaces the synthetic page. `ADAPTIVE_C`,
  `ADAPTIVE_BLOCK_SIZE` and the two bands in 4.4/4.6 are sized on a drawn face
  whose strokes are 255 levels below the paper by construction, and the
  sweeps behind them (the odd block sizes, the height and spacing bands) have
  to be re-run against the generator before any of those numbers is trusted.

---

## D5 — `EvidenceFlag.region` is a pixel polygon, not a field name

**Status:** settled · **Settled by:** 5.1, against the two source documents

`EvidenceFlag.region` holds the shape to draw over the image — a polygon of
integer `(x, y)` corners, or `None` — and nothing else. It does not hold the
name of the document field a finding is about.

**Why**

- Both source documents say so, and they are the ones a task is written from.
  `tasks.md`'s own definitions read "`region` — polygon or box in image pixel
  coordinates, so the UI can highlight it", and `ROADMAP.md` B2.1 reads
  "`region` (polygon or bbox, nullable)".
- Part 23 depends on it: 23.2 maps normalised flag regions onto the displayed
  image, and 23.6 lists a flag with no region rather than hiding one. A string
  field name cannot be mapped onto an image.
- 4.12 already writes the one shape. `mrz_region._box_polygon` returns a
  four-corner tuple of integer corners clockwise from the top left, so a box
  and a polygon are the same type and Part 4 hands 6.2 a value this record can
  carry unchanged.
- The field-name reading came from one sentence of the handover, which
  claimed `field_regions`' keys "are the names ... Part 5's `EvidenceFlag.region`
  already carry". That sentence is wrong against both source documents, and
  is corrected in `HANDOVER.md` rather than left to be inherited.

**What this forbids**

- `region` never takes a string, a field name, or a `{"field": ..., "box":
  ...}` pair.
- Nothing may reintroduce a second region type — a normalised box beside a
  pixel polygon, say — to reach the frontend. 23.2 normalises; the flag does
  not.

**Revisit only if** `tasks.md` or `ROADMAP.md` is amended to name a field on
the flag. 6.2 has to attach Part 4's *field* name to a finding and the
eleven fields 5.1 names have no slot for it, so that is the task where the
gap either closes or becomes a field. Do not smuggle it into `region`.

---

## D6 â€” A malformed flag is refused at construction, with its own error

**Status:** settled Â· **Settled by:** 5.2, against `tasks.md` 5.2 and the two
questions the handover left open

`EvidenceFlag` checks itself in `__post_init__`: `value` and `confidence` are
real numbers in the closed interval `[0, 1]`, `weight_band` is one of
`WEIGHT_BANDS`, and `region` is a tuple of at least `MIN_REGION_CORNERS`
corners of whole pixels or `None`. Anything else raises `FlagValueError`. None
of it is coerced, clipped, rounded or defaulted.

**Why**

- **The check is in the constructor rather than in a `validate()` method.** 5.1
  declared the eleven field types and enforced none of them, so the rules this
  task adds are new rather than a tightening. A separate validator is one a
  caller can forget, and a flag that was built wrongly is already wrong before
  anyone remembers to ask.
- **A bad value is a bug in the module that built the flag, not a document that
  is wrong.** `value = 1.4` says a rule measured something out of range.
  Clipping it would hand 7.5 a contribution of `1.0` for a finding that measured
  `1.4`, and from the score onwards nothing could tell the two apart. Loud is
  recoverable; a plausible number is not.
- **`FlagValueError`, not `mrz.MrzValueError` and not `APIError`.** 1.9 makes
  `mrz.MrzValueError` the single error type *the MRZ package* raises. A flag is
  emitted by tier 1, tier 2 and the crossdoc rules, none of which parse the MRZ,
  so reusing the tier0 error would make a face-match flag depend on the MRZ
  parser. `app.errors.APIError` is the HTTP boundary's and is not a value error.
  It subclasses `ValueError` for 1.4's reason: an existing
  `except ValueError` around the code that builds a flag keeps working. A test
  walks `flags.py`'s imports and holds them to `dataclasses` and `numbers`.
- **The range is chained, `0 <= number <= 1`, and `nan` is refused.** Two one
  -sided tests pass a `nan`, and a `nan` reaching 7.4 would poison a weighted
  sum with no error anywhere.
- **The polygon floor is three corners** because two are a segment and enclose
  no area, so a highlight drawn over them draws nothing at all. Corner values
  are `numbers.Integral`, so a numpy pixel out of a detector is not itself a
  refusal: 4.12's `_box_polygon` is where the plain-`int` promise is made, and
  re-imposing it here would push that cast into every future caller.
- **`region=None` stays legal**, and is 23.6's claim rather than this task's: a
  finding with nowhere to point is listed rather than dropped. The check is on
  the shape that is there and never a demand that something be there.

**What this forbids**

- No clamping, coercion or default of any field, and no silent drop of a flag
  with a bad one.
- **No message quotes the value it refused.** A wrong region or band is exactly
  where a field name or a line of printed text arrives, and quoting it back puts
  that text into a traceback and a log. A message names the rule and the index.
- `app.risk` must not import `app.pipeline.tier0` to reuse an error type, a band
  set or a polygon rule.
- `EvidenceFlag` gains no *public* method. `__post_init__` checks the shape the
  caller handed over and assigns nothing; a public method would be the second
  opinion about what was found that the frozen record exists to prevent.

**Revisit only if** flags are read back from storage rather than built, where
  refusing at construction is a different question from refusing on load, or if
  `tasks.md` 7.4 turns out to need a `value` that is `None` or boolean â€” its
  "boolean-style flag" case and this decision's closed interval cannot both be
  true for an `EvidenceFlag`, and that is 7.4's task to reconcile and record
  rather than a reason to soften the range here.

---

## D7 — A flag id names one rule, and the id list is the whole vocabulary

**Status:** settled · **Settled by:** 5.3, against `tasks.md` 5.3 and the four
open questions the handover left

`app/risk/flag_ids.py` holds 31 ids in eight families (`MRZ_`, `DATE_`,
`WATCHLIST_`, `OCR_`, `LAYOUT_`, `FACE_`, `TAMPER_`, `CROSSDOC_`). Every
constant is named after the id it holds, `ALL_FLAG_IDS` lists them in cascade
order by referencing those constants, and `FLAG_IDS` is the frozenset built
from that tuple. `PREFIXES` holds the eight family names.

**Why**

- **One id per rule, not per condition and not per field.** 5.6 states one
  rule with two ways to fire (a DOB in the future, an age over the maximum) and
  6.3 converts *rule results* into flags, so both carry `DATE_IMPLAUSIBLE_DOB`.
  `OCR_MRZ_MISMATCH` is one id for every mismatched field, which is what 12.15
  and ROADMAP B4.4 already state ("exactly one `OCR_MRZ_MISMATCH` flag") — and
  it happens to leave `D5`'s missing *field* slot undecided, because which field
  a finding is about stays 6.2's question rather than being smuggled into an id.
- **`MRZ_DOB_CHECK_DIGIT_MISMATCH`, not the abstract's `MRZ_DOB_CHECKDIGIT`.**
  The abstract spells its illustrative flag `MRZ_DOB_CHECKDIGIT`; the two
  completed test files and 6.7 spell it with both separators and the
  `_MISMATCH` suffix every other id in the list carries. The code's spelling
  wins and the constant matches it, so 6.7's worked example A asserts an id
  that exists rather than renaming a test.
- **The three optional-data check digits share one id.** TD1's optional data,
  TD2's optional data and TD3's personal number are three printed digits and
  one rule; three ids would mean three weights for a finding the officer sees
  as one, and 7.1's completeness test would then hold weights for ids no rule
  emits.
- **`OCR_BARCODE_MISMATCH` sits under `OCR_` rather than opening a ninth
  family.** 13.3 and ROADMAP B4.5 require a flag on a QR/print disagreement and
  name none; the eight prefixes are the only source of truth, and both sides of
  that comparison are read off this image.
- **No validation of `id` on the flag, and the module imports nothing.** 5.2
  checks three of eleven fields and says so; `id` is not one of them. A flag
  whose id is not yet in this list must stay constructible, which 6.2 needs
  while the rules are still being written. The list itself imports nothing, so
  7.1's loader, 7.3's lookup and 17.3's verifier can read it without pulling in
  OpenCV.
- **No flag id collides with a name the pipeline or the risk package already
  uses.** `MRZ_LAYOUTS`, `MRZ_SHAPES`, `MRZ_PARSERS` and `DATE_LENGTH` are one
  refactor away from being one, and a weightset keyed on a name the pipeline
  means by something else is silent. A test reads the uppercase module-level
  names of `app.pipeline.tier0` and `app.risk` statically — names, not values,
  because `MRZ_LAYOUTS` is a dict — and holds the two sets apart.

**What this forbids**

- No id outside the eight prefixes, and no ninth prefix without changing
  `PREFIXES` and the test that holds its eight names.
- No field name, date, number or module name inside an id: the id is a stable
  machine name and nothing about the document goes in it.
- No second spelling of one id — the duplicate check is the task's own
  requirement, and a misnamed constant (`MRZ_DOB` holding
  `MRZ_DOB_CHECK_DIGIT_MISMATCH`) is the same failure one step earlier.

**Revisit only if** 14.3's `quality` tier flags need ids, since that tier has
no family here and is also not one of the four `EvidenceFlag.tier` allows —
14.3's gap to record. `FACE_MISMATCH` and `FACE_LOW_SIMILARITY` are both held
because ROADMAP B4.11 names both and 13.16 emits only the second; the boundary
between "ambiguous, escalate" and "mismatch" is 13.16's to draw.

---

## D8 — An expiry rule answers with a result, and reads the century `infer_expiry_year` chose

**Status:** settled · **Settled by:** 5.4, against `tasks.md` 5.4 and the open
question of how a document is found to be expired

`app/pipeline/tier0/dates.py` holds `expiry_result(text, reference)` and the
frozen record `ExpiryResult(status, expiry, reference)`, with four statuses:
`EXPIRED`, `EXPIRING_TODAY`, `VALID`, `UNDETERMINED`.  An expired result
reports the day the document expired **on**; an undetermined one reports no
date at all.

**Why**

- **A rule produces a result and 6.3 produces the flag.** 6.3 is "convert
  date-rule results into flags", so a rule that built an `EvidenceFlag` would
  take the id, the band, the value and the region away from the tier that owns
  them.  The dependency therefore runs one way only -- `tier0` knows nothing
  about `app.risk` -- and a test walks this module's imports to hold it.  `D6`
  already forbids the other direction.
- **The century comes from `infer_expiry_year` and from nowhere else.** 3.13
  made that the only function permitted to invent one, and it deliberately
  reads an expiry *forwards*: its answer is the nearest year carrying the two
  printed digits that the document has not already got past, so **it never
  answers a date that is behind the reference**.  A rule that compared its
  answer with the reference could therefore never report expiry at all, which
  is the whole of the fork this entry records.
- **So expiry is read from *which* century that answer landed in.** The answer
  is always in the reference's century or the one after it; a century on means
  the reading in this century had already gone past, which is what expiry is.
  The date is then that answer less the century it added, so the specimen's
  `120415` reads as expired on 2012-04-15 while
  `mrz.infer_expiry_year("120415", ...)` still answers 2112.  This is asking a
  question of the answer rather than inventing a century: no arithmetic in
  this module chooses one.
- **`EXPIRING_TODAY` is its own status.** A document is valid *through* the
  day it expires -- the reason `infer_expiry_year` admits the day itself -- so
  collapsing it into `VALID` would lose the one boundary an officer reads, and
  making it `EXPIRED` would refuse a document that is still good.
- **No band, so `991231` read in 2026 is a document valid until 2099.** 3.13's
  rule has no horizon because two digits repeat every century, and adding one
  here would be an unsourced constant of exactly the kind `ADAPTIVE_C` is
  called out for. The consequence is asserted in a test so it is read rather
  than discovered.
- **One corner answers `UNDETERMINED` rather than `EXPIRED`.** A 29th of
  February can reach the second candidate for the calendar rather than for the
  reference -- `000229` read in January 1900 -- and un-rolling that gives a day
  that never was.

**What this forbids**

- No flag id, weight band, value, region or confidence on a rule result, and
  no import of `app.risk` from `tier0`.
- No default reference date, no `datetime.now()`/`today()`, and no second place
  a century is chosen. A bad reference raises `MrzValueError` rather than
  answering `UNDETERMINED`, which would report a screening that went wrong as
  a document nobody could read.
- No `None`/undetermined coerced into a verdict, and no date invented to fill
  the gap a status leaves.

**Revisit only if** 5.5 to 5.7 need a common base for the four date rules
where one record would serve, or if a sourced horizon for a plausible expiry
ever replaces the forward reading, or if 6.3 finds `ExpiryResult` cannot carry
what a `DATE_EXPIRED` flag needs.

---

## D9 — A date of issue is read in the reference's own century, and no other

**Status:** settled · **Settled by:** 5.5, against `tasks.md` 5.5 ("the
not-yet-valid rule (expiry in a past, issue date in the future)") and the
`D8` revisit clause asking whether 5.5 to 5.7 need a common base for the four
date rules

`app/pipeline/tier0/dates.py` holds `issue_result(text, reference)` and the
frozen record `IssueResult(status, issue, reference)`, with three statuses:
`ISSUED`, `NOT_YET_VALID`, `UNDETERMINED`.  A not-yet-valid result reports the
day the validity window opens on; an undetermined one reports no date at all.

**Why**

- **The task names both ends of the window and 5.4 already owns one of them.**
  "Expiry in a past" is 5.4's answer and is implemented; 5.5 is the other
  half — the window's near end.  So the rule reads a date of issue and nothing
  else, which is what keeps it from overlapping 5.7: a document whose issue
  date is unreadable and a document whose issue date is after its expiry are
  two different questions, and this one asks the first.
- **The century is the reference's own, and no second century is tried.**  The
  two readings `mrz.py` has are a birth (backwards, most recent admissible day
  before the reference) and an expiry (forwards, nearest day the document has
  not got past).  **Read backwards, a date of issue could never be in the
  future, because the candidate a century back always is** — so that reading
  could never produce this rule's finding at all.  The nearest century is the
  only reading under which "not yet valid" is observable, and it is the
  reading the verdict and the reported date are both made from, so the two
  cannot disagree.
- **It is not `infer_expiry_year`, and no `infer_issue_year` was added.**
  That function answers 2125 for `250101` read in 2026, which would flag every
  document ever issued as not yet valid — a forward reading is right for a
  date that is bounded ahead of the reader and wrong for one that is not.  A
  third century function in `mrz.py` would have to take the band `D8` refuses
  to invent, so the reading is `dates.py`'s own and the module stays the one
  place a date rule is judged.
- **There is no un-rolling.**  `D8` recovers a past expiry from a century-on
  answer, because an expiry is known to have passed and the day is evidence of
  when.  A date of issue has no such evidence: un-rolling a century-on reading
  here is precisely the move that would delete the finding, so the reading is
  reported as it was made.
- **No band, so `991231` read in 2026 is an issue date of 2099.**  Two digits
  repeat every century, exactly as they do for an expiry, so a document issued
  in a year whose two digits sit ahead of the reference's own reads a century
  on.  That is the cost of the only reading under which the rule can fire, and
  it is asserted in a test rather than hoped away.
- **One corner answers `UNDETERMINED` rather than reaching for another
  century.**  `000229` read in 2100 names a day that never was, and 2000-02-29
  is a century further back than this rule is willing to go — the same refusal
  `D8` makes for the same characters.
- **The *check* is shared and the *record* is not.**  `_check_result` takes the
  status set and the field's name, so the pairing invariant — only an
  `UNDETERMINED` result carries no date — is one piece of code rather than
  two.  The records stay separate because their statuses and their dated field
  differ, and a test holds that the two status sets share exactly one answer:
  the gap.

**What this forbids**

- No flag id, weight band, value, region or confidence on a rule result, and
  no import of `app.risk` from `tier0`.
- No default reference date, no `datetime.now()`/`today()`, and no second
  century for a date of issue.
- No `infer_issue_year` beside `infer_birth_year` and `infer_expiry_year`, and
  no `mrz.date_fault` call here: `datetime.date` refuses the impossible month,
  the impossible day and the 29th of February that never was in one place.
- No one record shared across the four date rules, and no status shared between
  two of them except `UNDETERMINED`.

**Revisit only if** 6.3 finds `IssueResult` cannot carry what a
`DATE_NOT_YET_VALID` flag needs, if a sourced horizon for a plausible date of
issue ever replaces the nearest-century reading, or if 5.6 and 5.7 make a
shared base for all four rules cheaper than the pairwise check.

---

## D10 — A date of birth is read backwards, and the caller's band decides how far back

**Status:** settled · **Settled by:** 5.6, against `tasks.md` 5.6 ("the
implausible-date-of-birth rule (DOB in the future, or implying an age over a
configurable maximum) with tests at the boundary") and the `D9` revisit clause
asking whether 5.6 to 5.7 need a common base for the four date rules

`app/pipeline/tier0/dates.py` holds `dob_result(text, reference, max_age)`
and the frozen record `BirthResult(status, birth, reference)`, with three
statuses: `PLAUSIBLE`, `IMPLAUSIBLE`, `UNDETERMINED`.  `max_age` defaults to
`mrz.MAX_BIRTH_AGE`, and that figure is imported rather than restated: the
module holds no number of its own, and a test walks the AST to hold it to that.

**Why**

- **The two halves of the task are one status.**  `flag_ids.DATE_IMPLAUSIBLE_DOB`
  names one rule and 6.3 still has to write a reason for it, because a birth
  after the reference and a birth over the maximum are different sentences.
  The record's own two dates tell them apart, so a fourth status would be a
  second answer about the document that the frozen record exists to prevent.
- **The reading is backwards and the band is what decides how far back it
  reaches.**  The two centuries bracketing the reference are the only
  candidates; the near one is taken whenever it has already happened, and the
  century behind is read on only when the caller's `max_age` admits a holder of
  that age.  A birth that has not happened is therefore *reachable as a
  finding* only when the band is tightened — which is the whole of what the
  task's "configurable" buys.
- **`mrz.infer_birth_year` cannot be built on, and that is its own rule
  working.**  It skips a candidate that has not happened and reads on, because
  a function whose job is to name a birth cannot answer with a future one.
  That discarded reading *is* this rule's finding, so the rule reads both
  centuries itself and never asks the century function for a year.
- **At the default maximum this rule can report nothing, and that is asserted
  rather than promised.**  A two-century reading implies an age of at most 99
  and `MAX_BIRTH_AGE` is 120, so the band admits every real reading and the two
  implausible answers are unreachable.  A test holds that at the default the
  rule and `infer_birth_year` agree about every character, so a disagreement
  is a signal that one of the two has been changed.
- **The age is whole years and the maximum is inclusive; a maximum of zero
  admits only a birth on the reference day.**  Whole years because an age is
  the thing people count that way, and the day a birthday falls is the day it
  counts — the same six characters change verdict on the birthday rather than
  in the middle of it.  The floor is the band's own edge: a band of no years is
  one day wide, and a holder born before the reference has already lived a day
  it has no room for.
- **`reference` has no default and `max_age` does.**  A verdict that depends
  on when the screening ran is an artefact, while a bound on plausible age is a
  fact about the caller rather than about the day.  A wrong `reference`, a
  wrong-width `text` and a `max_age` that is not a whole number of years within
  the band are all raised on rather than answered.

**What this forbids**

- No flag id, weight band, value, region or confidence on `BirthResult`, and no
  import of `app.risk` from `tier0`.
- No third century, no `infer_birth_year` call here, and no second figure
  beside `mrz.MAX_BIRTH_AGE`.
- No age, no method and no convenience field on the record: the age is a
  difference between two of the fields it already holds.

**Revisit only if** 6.3 finds `BirthResult` cannot carry what a
`DATE_IMPLAUSIBLE_DOB` flag needs, if a caller needs a maximum this project's
own figure does not bound, or if 5.7 makes a shared base for all four rules
cheaper than the pairwise check.

---

## D11 — The issue-after-expiry rule reads two records and no date of its own

**Status:** settled · **Settled by:** 5.7, against `tasks.md` 5.7 ("the
issue-after-expiry consistency rule with a test") and the `D9`/`D10` revisit
clauses asking whether a shared base for all four date rules is cheaper than
the pairwise check

`app/pipeline/tier0/dates.py` holds `consistency_result(issue, expiry)` and
the frozen record `ConsistencyResult(status, issue, expiry, reference)`, with
three statuses: `CONSISTENT`, `ISSUE_AFTER_EXPIRY`, `UNDETERMINED`.  The two
arguments are the `IssueResult` and `ExpiryResult` the other two rules
produced, in the order the validity window runs.

**Why**

- **This is the first rule that asks the document rather than the reader.**  A
  window that opens after it closes is a contradiction whatever day the
  screening ran on, so the function takes two records, `text` and `reference`
  are both absent, and the signature is the test.  There is no reading here to
  resolve and no century to choose, so the rule adds no third date of its own
  and the record's `reference` is *carried* from the two records rather than
  asked for.
- **The answer to `D9`/`D10`'s shared-base question is no.**  The first three
  rules share `_as_day`, `_check_result` and one `parse_date`; the fourth
  shares those and adds nothing, because a comparison of two resolved days
  has no text to parse.  A common base for all four would be a wrapper over
  three rules and a passthrough on the fourth, so the pairwise check stands.
- **It compares the two days, not the other two rules' verdicts.**  A document
  is compared with itself: an expired window and a window that has not opened
  are both `CONSISTENT` when their own dates run the right way round, and a
  rule that inherited `EXPIRED` or `NOT_YET_VALID` would be answering a
  different question with this id.
- **The two horizon gaps compose, and the composition is asserted.**  `991231`
  read in 2026 is an issue date of 2099 (`D9`) and `120415` is an expiry that
  expired in 2012 (`D8`), so the records a caller already holds contradict
  each other.  Re-reading the six characters here would mean inventing a third
  reading to reach the same answer.
- **The boundary day is inside.**  A document issued and expiring on the same
  day has a one-day window, and `EXPIRING_TODAY` already holds that a
  document is valid *through* the day it expires; the day after the expiry is
  the first that is a finding.
- **The gap is the gap and is never inherited from the half that could be
  read.**  "An issue date nobody could read" and "an issue date after the
  expiry" are different sentences, and only the second is this rule's finding.
  The pairing is therefore "a verdict carries both days and the gap carries
  neither", held by one `_check_result` call per date — the same helper the
  other three records use, called twice rather than duplicated.
- **Two records read against different reference days are refused.**  Two days
  are two screenings rather than one document, so the disagreement is a
  caller mistake raised on `_as_day`'s reasoning.  The two record types are
  the check that catches a caller handing them over the wrong way round, which
  would otherwise be a document compared with itself.

**What this forbids**

- No `text` and no `reference` argument on `consistency_result`, no re-read of
  the six printed characters, no `parse_date` call here, and no century
  arithmetic in this rule.
- No flag id, weight band, value, region or confidence on `ConsistencyResult`,
  and no import of `app.risk` from `tier0`.
- No status shared with the other three rules except `UNDETERMINED`, no
  method on the record, and no separate pairing checker: a second one would be
  the same invariant written twice.

**Revisit only if** 6.3 finds `ConsistencyResult` cannot carry what a
`DATE_ISSUE_AFTER_EXPIRY` flag needs for `expected` and `found`, if a caller
genuinely holds two records read on different days, or if 5.8's
`ReferenceDate` turns the reference from something a rule carries into
something every rule must be handed.

---

## D12 — The reference date is one named dependency, and the fourth rule carries it

**Status:** settled · **Settled by:** 5.8, against `tasks.md` 5.8 ("Add a
`ReferenceDate` dependency so every date rule takes the current date as a
parameter, with a test asserting no module in `tier0/dates.py` calls
`datetime.now()`") and answering `D11`'s revisit clause, which asked exactly
whether 5.8 turns the reference into something every rule must be handed

`app/pipeline/tier0/dates.py` gains one name, `ReferenceDate = datetime.date`,
declared on the `reference` parameter of `expiry_result`, `issue_result` and
`dob_result` and on the `reference` field of all four records.  It is in
`__all__`, and `backend/tests/unit/test_reference_date.py` holds it.

**Why**

- **The injection point gets a name, so there is one thing for the cascade to
  supply.**  6.3 and everything after it hand a day to every date rule; a
  bare `datetime.date` repeated down the file says nothing about that, and a
  name in one place says it once.
- **It is an alias and not a type of this project's own.**  A subclass would
  make every `isinstance` in the module and every record a caller already
  holds answer to two questions, and a wrapper would be a place a clock could
  be read from -- which is the one thing `tasks.md` bans.  `dates.py` still
  defines four classes and all four are records, which a test asserts against
  the module's own `ast`.
- **The name is pinned in the source, not only in the resolved type.**
  `ReferenceDate` *is* `datetime.date`, so a signature annotation proves
  nothing on its own; the test walks the tree and reads what the `reference`
  argument and field are written as.
- **No rule has a default that could have come from the clock.**  The only
  default anywhere in the module is `max_age`, the caller's age band, and the
  test collects every default across all four rules and compares the whole
  set.  A `date.today()` default would pass every behavioural test in the
  suite and still make a screening's answer depend on when it ran.
- **A `datetime.datetime` stays a legal injection**, reduced to its day by
  `_as_day`, so a caller holding a timestamp is not a caller making that
  mistake and every record carries the plain `date` the alias names.
- **`D11`'s revisit clause is answered: the fourth rule carries the
  dependency, and that is the injection rather than an exemption.**  It takes
  no `reference` because it reads no date of its own -- its two arguments are
  records that each hold one, they must agree on it, and the result carries
  it.  So all four rules and all four records name `ReferenceDate`; three
  rules take it as an argument and the fourth carries it off the two it was
  given.  The exception is pinned by a test of its own, so a fifth rule that
  quietly took neither would fail.
- **The clock ban now covers `dates.py` as well as `mrz.py`, by one walk.**
  `test_reference_date.py` walks both modules for `now`, `utcnow`, `today` and
  `fromtimestamp`, because `date.today()` is the same dependency as
  `datetime.now()` written more quietly.  The walk is an `ast` walk rather
  than a substring search because these docstrings name the banned call in
  order to say it is not used, and the test asserts both modules really do
  import `datetime` so the walk cannot pass vacuously.

**What this forbids**

- No call to the calendar anywhere in `tier0/dates.py`, and no default that
  is a day or anything callable, on any of the four rules.
- No subclass, wrapper, `Protocol` or clock object standing in for the
  dependency: a rule must be handed a day, never a way of finding one.
- No `reference` parameter added to `consistency_result`, and no `reference`
  argument dropped from the other three to "simplify" a call site.
- No date of the screening held as module state, cached at import, or
  threaded through a record that does not name it as a field.

**Revisit only if** 6.3 needs a timezone or an instant rather than a day (a
recorded `found` that must be quotable to the minute), if a caller genuinely
holds records read on different days rather than the mistake 5.7 refuses, or
if a fifth date rule appears whose reference is on neither the printed
characters nor the two records.

---

## D13 — A watchlist hit names a list entry, never the identity that matched it

**Status:** settled · **Settled by:** 5.9, against `tasks.md` 5.9 ("Create the
`Watchlist` interface with
`lookup(document_number, name, dob) -> list[WatchlistHit]`") and answering the
question `HANDOVER.md` raised for it,
which was what a hit may carry before 5.10 puts synthetic entries in the seed

`app/risk/watchlist.py` holds three things: `WatchlistHit`, the `Watchlist`
interface, and the vocabulary of three kinds.  It is in the `app.risk` package
rather than a new one because 6.4 turns a hit into an `EvidenceFlag` and the
three kinds are the three `WATCHLIST_` ids one for one.

**Why**

- **The record has three fields and none of them holds the value that
  matched.**  `lookup` takes identity arguments, so the connector is the last
  place in the pipeline where a match is in hand; 6.4 writes a `reason` from
  the hit, and prose reaches the dashboard, the log and the officer's screen.
  A record that cannot hold a document number, a name or a date of birth is
  what makes the `tasks.md` ban hold for a connector nobody has written yet,
  and a test pins the field set by name.
- **`entry_id` is a token and the check on it is a guard, not a guarantee.**
  Letters, digits, `_` and `-` are allowed, so a name carrying a separator is
  refused at the point it is made; `1988-04-12` and `MALHOTRA` pass, and a test
  asserts that limit rather than leaving it implied.
- **The kind and the key it was found by are held together.**  A blacklisted
  or stolen entry is found by its document number and an identity-seen entry by
  its name and date of birth, which is what `flag_ids` already says, so the
  pairing is refused when the two fields disagree and a caller can say which
  question a list answered without holding the answer.
- **The three arguments are keyword-only, required, and none has a default.**
  Two are strings: a positional call could pair a name with a document number
  and be answered with a clean miss, which at a checkpoint is a false negative
  reported as a clear document.  An omitted key is a question nobody asked, so
  a field nobody could read is passed as `None` explicitly.
- **`dob` is a resolved `datetime.date` and there is no reference date.**  A
  connector that filtered on "still listed today" would make a screening's
  outcome depend on when it ran, which is the artefact 5.4's reference date
  refuses; and 5.6 already resolves the century in one place, so six printed
  characters are not handed to a second place to resolve.
- **`Watchlist` is an `abc.ABC` and not a `Protocol`.**  A subclass that omits
  `lookup` cannot be instantiated, so a wiring mistake is a `TypeError` at
  construction rather than an `AttributeError` at the first document.
- **No order is promised and none should be read.**  Severity is the kind and
  not the position, and 6.4 turns each hit into its own flag.

**What this forbids**

- No field on `WatchlistHit` for a document number, a name, a date of birth or
  a free-text reason, and no `detail` a connector could fill with the text it
  was sent.
- No positional call to `lookup`, no default on any of its three arguments, and
  no fourth argument carrying a day.
- A kind outside `HIT_KINDS`, a `matched_on` that disagrees with its kind, and
  an `entry_id` that is not a non-empty token are refused, not coerced.
- No method on `WatchlistHit`: a second answer about what matched is the thing
  every record in this project is frozen to prevent.

**Revisit only if** 7.13's history decay needs a date on the hit, which would
then be a `ReferenceDate` on `lookup` (`D12`) rather than a day read from the
clock; if a live connector can only be asked with a country code alongside the
document number, which is a fourth key rather than a fourth field; or if 6.4
turns out to need per-entry weights that are not one per kind.

---

## D14 — The mock connector lives beside the seed and matches values as printed

**Status:** settled · **Settled by:** 5.11, against `tasks.md` 5.11 ("Implement
`MockWatchlist` backed by that JSON, with tests: a number in the seed hits, an
unknown number misses, and a name+DOB match hits") and answering the question
`HANDOVER.md` raised for it, which was which of the seed's two name shapes the
mock looks a name up in

`app/seed/mock_watchlist.py` holds `MockWatchlist`, the one `Watchlist` this
project can run against, and it reads `app/seed/watchlist.json` through
`importlib.resources.files("app.seed")`.

**Why**

- **The mock sits with its data and not in `app.risk`.**  The seed is the whole
  of it: when a live connector arrives this module and its JSON go, and the
  seam stays.  A production module importing a mock is the mistake this
  placement makes visible rather than prevents by a comment.
- **Values are compared as printed, and neither name shape wins.**  No case
  folding, no filler stripping and no tidying: a matching rule this project has
  not written down is a rule no live connector could be expected to share, and
  a mock that tidied names would be answering a question `Watchlist.lookup`
  does not ask.  5.10's row carries both shapes so the mock can try both, and
  a caller holding either spelling is answered alike rather than one of them
  being told the document is clear.
- **A `None` argument matches nothing.**  An identity entry is a name *and* a
  date of birth; a lookup of one key alone is not a question about the
  identity, so three `None`'s answer `[]` and a number is never read against an
  identity row that carries none.
- **Every row becomes a `WatchlistHit` before it is matched**, so `D13`'s field
  set and its kind/key pairing are what a seed row has to satisfy rather than a
  second set of checks this module would keep.
- **A row the mock cannot read is refused, not passed over.**  A missing or
  non-text field and a `dob` that is not a day raise `WatchlistValueError`,
  naming the key and never the value.  A row passed over is an entry the list
  cannot speak about, and an unanswered question reads as a cleared document --
  the same failure `D13` names for a hit that cannot carry what it matched.

**What this forbids**

- No case folding, filler stripping or tidying inside the mock, and no second
  spelling invented here that the seed does not carry.
- No matched document number, name or date of birth in a returned hit, in a log,
  or in a refusal message -- `D13`'s limit, held on the connector that matched.
- No skipping a row that cannot be read, and no reading the file by a path
  assembled from `__file__`.
- No clock: `dob` arrives resolved and the seed's own text names a day.

**Revisit only if** 5.12 moves the read to construction, which changes *when*
the seed is read and not what a row is matched against; if 6.4 settles that a
caller passes only the tidied shape, in which case the printed shape is still
the one tried first; or if a live connector needs a fourth key, which is `D13`'s
revisit and not this entry's.

---

## D15 — The seed is read once per connector, and the read is still `_entries`

**Status:** settled · **Settled by:** 5.12, against `tasks.md` 5.12 ("Make
`MockWatchlist` load the JSON once at construction, not per lookup, with a test
counting file reads") and answering the question D14 left for it, which was
whether the read moves to construction

`MockWatchlist.__init__` calls `app.seed.mock_watchlist._entries()` and keeps
the rows; `lookup` answers from those rows and never reopens the file.

**Why**

- **The seed does not change while a run is going.**  A read per document is
  work a screening pays for a file whose answer it is already holding, and it
  is paid again by every tier and every cascade stage that asks the list.
- **The rows are the connector's and not the module's.**  A cache held at
  module level would answer every connector in the process from the first
  one's read, so a row edited in the seed would be a row no later connector
  could find.  One read per connector is what keeps the edit visible to the
  next connector, which is the property `D14` recorded when the read was on
  every lookup.
- **The read is still behind `_entries`, and it is still the only place the
  file is opened.**  The cache sits behind that seam rather than beside it, so
  the row-to-`WatchlistHit` reading, both name shapes and the refusals stay
  where `D14` put them and a test that replaces `_entries` still replaces what
  a connector sees.
- **The count is taken at the resource, not at `_entries`.**  What 5.12 asks is
  that the seed is opened once, and a count of this module's own function
  would still read one if the read behind it were moved, cached elsewhere or
  answered from memory.  The test wraps the traversable the package hands out
  and records each `read_text`.

**What this forbids**

- No module-level cache of the seed's rows, and no reload path: nothing may
  reopen the file to answer a lookup.
- No per-connector refresh hook, because a screening that can be told to
  reread a list is a screening whose answer depends on when it was asked --
  the same ground `Watchlist.lookup` takes no day over.
- No change to what a row is matched against: exact printed values, both name
  shapes, `None` matching nothing, and `D14`'s refusals all stand.

**Revisit only if** a live connector arrives, since how *it* caches a remote
list is a question of its own and not this module's; or if a seed is ever
reloaded under a running process, which needs a stated reason for a screening
to answer from a different list than the one it started with.

---

## D16 — The runner measures; the caller's claim never becomes a constraint

**Status:** settled · **Settled by:** 6.1, against `tasks.md` 6.1's
`run_tier0(image, document_type=None, reference_date=None)`

`app/pipeline/tier0/runner.py` holds `TierResult` (five defaulted fields, frozen,
no public method) and `run_tier0`, which runs
`mrz_region.detect_mrz(image)` and reports its `format` and `regions` untouched.
`flags` is the empty tuple and `hard_failed` is `False`, because no rule is
wired to the seam yet; 6.2 to 6.5 fill them.

**Why**
- **`document_type` is a claim, and no vocabulary is imposed on it.** It is
  checked for shape only (`None` or a non-empty string). The officer-facing
  selector (`F6`) names passports, visas, national IDs and permits while
  `document.MRZ_SHAPES` names three *zone shapes*; a tier that had to speak
  both would hold a mapping the project has no source for and would refuse a
  caller's own word for their own document. A test asserts that a claim of
  `"TD1"` in front of a TD3 page still answers `TD3`.
- **The format is the shape's own answer.** `document.py` decides by shape
  alone and `mrz_region.infer_format` is the only writer, so the runner
  cannot be a second opinion about what a page holds.
- **`hard_failed` and `hard_fail_reason` are one invariant.** The abstract
  requires the reason to be recorded with the High exit, so a result that
  raised a document and said nothing is refused at construction. This is
  `dates._check_result`'s pairing seen from the other side.
- **The container fields are checked and the corners are not.** A list in a
  frozen record is a hole in the frozenness; the corners are
  `mrz_region._box_polygon`'s promise and are checked where a polygon is built
  into a flag.
- **`reference_date` is the 5.8 dependency and is never defaulted.** `None`
  means the caller injected no day, and a date rule asked against it refuses
  on `dates._as_day`'s reasoning rather than reading the clock.

**What this forbids**

- No format dispatch off `document_type`, and no claim-checked-against-shape
  flag until a task names an id in `flag_ids.py`.
- No clock read in `runner.py`, held by an AST walk in
  `test_tier0_runner.py` rather than a substring.
- No document-type vocabulary table in `tier0`; the mapping belongs at the
  HTTP boundary (`B1.12`), which is where a caller's word is translated.
- No threshold, band or weight in this module: a rule produces a record and
  the runner collects records.

**Revisit only if** a task emits a flag about a claim disagreeing with a
measurement, which needs an id this project does not have; or if a reader that
turns cells into characters exists, at which point 6.2's inputs change.

## D17 — The record names the field, because the id names the rule

**Status:** settled · **Settled by:** 6.2, against the gap `D5` and `D7` left

`EvidenceFlag` grew a twelfth field, `field: str | None`, and it is required
like the other eleven. `field` names which field of the document a finding is
about — `"date_of_birth"`, `"composite"` — or `None` for a finding that is not
about one field. `run_tier0` gained a fourth optional argument,
`parsed_document`, which is where 6.2's characters come from.

**Why**

- **`D5` and `D7` together left no third place for the name, and 6.2 is the
  task that had to answer.** `region` is a pixel polygon and cannot answer
  "which field"; `id` names one rule and 7.1's completeness test, the weightset
  loader and 7.3's lookup all read it, so `MRZ_DOB_CHECK_DIGIT_MISMATCH_COMPOSITE`
  would be a second rule wearing a field's name. `CheckDigitResult.field` already
  exists and already carries the label the three layouts declare, so the name
  had somewhere true to go and nowhere true to be invented.
- **A flag about a composite cannot name a field, and says so.** `td1.py`,
  `td2.py` and `td3.py` all hold `None` in the composite row's second column,
  because the composite's characters cross a line boundary and a field
  boundary at once. So `field` is `None` where the span has no field, the
  printed digit's own box is the region, and neither half is faked.
- **Required, and last, rather than defaulted and inserted.** A rule that has
  to answer the question cannot forget it, and appending keeps a flag built
  positionally meaning what it meant. `D6`'s "three checked, the rest not" is
  unchanged: `field` is unchecked, like the other nine.
- **The parse is handed in, not read out of the page.** Nothing in Part 4
  reads a character out of a cell, so `run_tier0` still measures and the
  caller who holds the parse passes it over. `None` reports no check-digit
  findings, which is not a pass, and a parse whose `format` is not the format
  the page measured is refused rather than paired — a highlight drawn over
  another format's ink is worse than no highlight.

**What this forbids**

- No field name spelled into an `id`, and no `region` that is anything but
  `D5`'s polygon.
- No `hard_failed` from 6.2, and no weight number: 6.5 owns the override and
  7.1's weightset owns what a finding weighs. The band is the name `high`.
- No reader. If one arrives, `run_tier0` gains an argument rather than
  growing a second opinion about what a page holds.

**Revisit only if** a flag is ever emitted about something with no field at
all — a quality-gate finding, a whole-page finding — and `None` proves to be
carrying more than one meaning.

---

## D18 — A hit's severity is its kind, and the entry never reaches the flag

**Status:** settled · **Settled by:** 6.4, on the seam 5.9 left

Each `WatchlistHit.kind` becomes one `EvidenceFlag` through a single table in
`runner.py`, keyed by the kind and holding its id, its sentence, its weight
band, the field it is about, and whether it is a hard fail. A blacklist hit is
a hard fail; a stolen-document hit is heavy and is not; an identity_seen hit
is `review` and is not. `run_tier0` gained a fifth optional argument,
`watchlist`, and the runner imports `app.risk.watchlist` and nothing behind it.

**Why**

- **A blacklist hit overrides and a stolen one does not**, which is the
  abstract's own pair: a blacklist match sits beside a broken checksum as the
  finding that exits straight to High Risk with the reason recorded, while a
  stolen document is a fact about a document rather than about the person
  holding it. `ROADMAP`'s V-phase names the same pair.
- **The severity is the kind and never the position in the answer.** `lookup`
  promises no order, so a rule that read the first hit as the serious one
  would report a document on a stolen list as blacklisted. Every hit becomes
  its own flag, in the order given, with no significance read into it.
- **The prose is written here from `kind` and `matched_on` and nothing
  else.** `D13` left this to 6.4, and a live feed's own free text is exactly
  where identity data would ride in, so `reason` is composed from two closed
  vocabularies: one of three kind names and one of two key names.
- **`entry_id` reaches the flag nowhere.** Its charset is a guard and not a
  guarantee -- 5.9's own test admits a one-word name passes it -- so the row
  reference stays on the record that carries it and off the dashboard, the log
  and the officer's screen. `expected` is `None` and `found` is the kind, since
  a clean document produces no flag at all and so has no expected string to
  print against.
- **The hard-fail reason is the finding's own `label`.** Two sentences
  describing one event is one of them able to disagree with the other, and the
  labels are collected and sorted so the reason does not depend on which list
  answered first. `source_module` is the seam rather than the connector:
  which list answered is a deployment concern, not part of the finding.
- **A document-number hit is boxed over the document number and an identity
  hit is not boxed at all**, because it is about a name and a date of birth
  together and 4.12 has no box for a pair of fields. 23.6 lists it.

**What this forbids**

- No `entry_id`, no document number, no name and no date of birth in any
  string on a watchlist flag, including `reason` and `hard_fail_reason`.
- No reading an answer's order, and no merging two entries into one finding.
- No override from any other family: a failed check digit still leaves
  `hard_failed` alone, because 6.5 is what generalises it.

**Revisit only if** 7.1's weightset gives a band a number that says `review`
and `high` are not the distance `high` sits above `review`, or if 7.13's
calibration says a previous screening is worth a hard fail.

## D19 — A list is asked with what the document printed, and nothing tidied

**Status:** settled · **Settled by:** 6.4, on `D14`'s rule and one gap it left

`run_tier0` asks a connector once per screening, with the three keys
`lookup` declares: the document number, the name and a date of birth. The
document number and the name are the fields **as the document printed them**,
untidied and unstripped of filler; the date of birth is `dates.dob_result`'s
reading against the injected reference, or `None` where no reference was
injected or no rule could read the six characters.

**Why**

- **`D14` settled the connector's half and not the caller's.** The mock is a
  lookup table that compares values as printed, so a runner that tidied them
  would be a second place for a list's spelling to disagree with the
  document's.
- **A date of birth is asked as a resolved day, never as six characters.**
  `lookup` compares a `datetime.date` and two digits have no century, so 5.6's
  rule is asked rather than `infer_birth_year` called: the plausibility half of
  that rule is 6.3's to flag, not a reason to skip a list.
- **A list is not asked without a parse.** The three keys are three values a
  document prints and nothing in Part 4 reads a character out of a cell, so
  asking with nothing would spend a live feed's round trip to reach `[]`.
- **`None` is a key that is not checked, never a hit.** A TD1 prints no name
  and is not asked about the identity list; a screening that injected no
  reference date is not asked about a date of birth and still is asked about
  the document number.

**What this forbids**

- No tidying, case folding, filler stripping or upper-casing of any value
  handed to a list, and no tidied single-string name invented here to make the
  seed's identity row reachable.
- No default connector. `None` means no list was wired, and no list is not a
  cleared document.

**The gap this leaves, on purpose:** a TD2 or TD3 prints its name field padded
to 39 characters, so the name a list is asked about is the padded field and the
seed's bare `FICTITIOUS<<JANE` row is not reachable end to end. Closing that
needs a sourced single-string spelling for a tidied name, which is a naming
decision and not 6.4's; until it exists, the identity path is exercised
through a stub rather than through the seed.

**Revisit only if** a real connector reports that it cannot match a padded
name field, which would make the tidied spelling a requirement rather than a
gap.

## D20 — A run reports its own four durations, on the record and read-only

**Status:** settled · **Settled by:** 6.6, on the "one value for a caller to
compare against" rule 6.1 set for `TierResult`

`TierResult` carries a sixth field, `stage_timings`: a read-only mapping of
`time.perf_counter` durations in seconds under `runner.STAGE_NAMES` —
`detection`, `check_digits`, `watchlist` and `total`. All four keys are on
every result including a default-constructed one, a run that raises produces
no record and so no durations, and `total` is a measurement taken over a
window opened before the first stage rather than a sum of the other three.

**Why**

- **Measured inside the run, not asked of the caller.** A caller timing the
  call from outside measures the HTTP boundary, the queue it waited in and
  the response it has not written yet, so the figure on the record and the
  figure against the abstract's sub-0.3 s target would be two numbers wearing
  one name.
- **A stopwatch is not a calendar.** `time.perf_counter` answers "how long
  since this instant" and resolves no day, so 6.6 does not weaken what
  `D12`'s named dependency and the two AST walks in 6.2's and 6.4's suites
  hold. `_now` is the only clock read in the module, and the widened walk
  pins that it is the only clock-shaped call in it at all — a wall clock would
  answer the same question and also move when the host's time is corrected.
- **The four keys are always there.** A stage with no work still ran, so it
  carries a near-zero reading where a skipped stage would have been a missing
  key, and a consumer drawing a table of stages would otherwise guard every
  lookup before it could read a number.
- **`total` spans the refusals too.** The abstract bounds the whole of Tier 0,
  so the window opens before the seam's own argument checks; summing the
  three stages instead would under-report the one figure the target is
  about, and under-reporting is the direction that lets a regression look
  like a pass.
- **The record keeps a read-only copy of its own.** A frozen dataclass stops
  a field being reassigned and does nothing about a container, so a caller's
  dict left in the field is the same hole `MrzDetection`'s tuples avoid. The
  price is that **`TierResult` is no longer hashable**, and that was taken
  deliberately: a read-only mapping cannot be hashed, and nothing in the
  cascade hashes a result.
- **A mapping and not a tuple of pairs.** The consumer names the stage it
  wants — `stage_timings["total"]` — where a sequence would answer
  `stage_timings[0]` as readily, which is the positional reading 4.11 and
  4.12 refuse and which would be the one thing a written-down vocabulary
  exists to stop.

**What this forbids**

- No clock argument, and nothing to switch the instrumentation off: a
  caller-supplied timer is the one way these numbers could be wrong with
  nothing else broken.
- No wall clock, and no `datetime` reading, beside the stopwatch.
- No threshold in this module. The abstract's 0.3 s is not enforced, judged
  or formatted here, so a slow run is a number a later task reports rather
  than a failure Tier 0 raises over.
- No duration for a run that raised, and no vocabulary outside
  `STAGE_NAMES`.

**The gap this leaves, on purpose:** "per-stage" means the three things the
runner does, not Part 4's eleven chain steps. Splitting `deskew` from
`line_polygons` would mean threading a timer through `detect_mrz` and giving
Part 4 a caller it has no reason to know about, for a figure the abstract
bounds only as a whole. **Nothing renders these numbers yet**, either: the
task that shows "Tier 0 took 0.11 s" is a later one, and this is the record
it will read.

**Revisit only if** a tier's own budget is ever set per chain step rather
than per tier, which would make `detect_mrz` the place to measure and this
record the place to summarise.

---

## D21 — A weight is points on the score, and one finding never reaches High

**Status:** settled · **Settled by:** 7.1, on `D18`'s condition that a band
carry a number `high` sits a distance above `review`

`app/risk/weightsets/v1.yaml` holds one row per id in
`app.risk.flag_ids.FLAG_IDS`: a weight in points and one of the record's own
three bands. **A weight is points on the 0–100 score and not a share of a
budget**, so one flag contributes at most its own weight and corroborating
flags may exceed 100, which is what 7.7's clamp is for. **The heaviest weight
is 65 and 7.8's `REVIEW_MAX` is 69**, so no single finding reaches High on its
own: High needs corroboration, or 7.6's hard-fail floor of 90.

**Why**

- **Corroboration, not one strong signal, is what sends a document to High.**
  The abstract names two findings that exit straight to High Risk — a broken
  checksum and a blacklist match — and leaves every other finding to be
  weighed, and this is that rule as arithmetic rather than as prose.
- **A stand-in must not reject a genuine traveller by itself.** Every module
  in Part 15 ships as an interface plus a labelled heuristic, so a morph or
  deepfake stand-in that fired on its own at a weight above the threshold would
  make a false alarm an automatic High — the failure the abstract lists under
  false alarms on genuine travellers, and the one `review` exists to prevent.
- **Points rather than shares, because the flags that fire are a minority of
  the vocabulary.** Thirty-one ids share the vocabulary and a clean document
  fires none of them, so weights that partitioned 100 between them would make
  every real finding worth three points and put the band thresholds in charge
  of the result instead of the weights.
- **Three bands in three disjoint ranges, not one scale with a name on it.**
  `low` is 15, `review` is 30–40 and `high` is 55–65, so a band an officer
  reads is never decided by a one-point difference, which is the condition
  `D18` set for this file.
- **The band is a severity class, not a promise about the score.** A `high`
  row says the finding is the most serious kind this vocabulary has; whether
  the document lands in High is 7.7 and 7.9's arithmetic over the whole flag
  set.

**What this forbids**

- No hard-fail list in the weightset. That is `runner._HARD_FAIL_IDS`, a union
  of each family's own table held beside its labels, and a second list here
  could disagree with those without either one noticing.
- No band, weight or `ruleset_version` written in Python. The file is the
  single place all three live, `ruleset_version` agrees with
  `app.version.RULESET_VERSION`, and `test_weightset_v1.py` holds both.
- No weight that reaches 70, and no id in the file that `flag_ids` does not
  have, so 7.3's lookup can neither raise on the committed file nor find a row
  no rule can reach.

**The gap this leaves, on purpose:** every number in the file is an expert-rule
figure and none is calibrated. The abstract says the initial weights come from
expert rules and are refined on labelled validation data, and Part 27 owns
that, so `v1.yaml` is the starting point rather than a measured one — and a
retune is a new versioned file, not an edit to this one.

**Revisit only if** Part 27's calibration produces weights above 69 that are
still one finding's own contribution, which would mean a single validated
detector is more reliable than corroboration and the floor belongs to move
rather than the scale.

---

## D22 — A weightset is a package resource, and nothing about it is defaulted

**Date:** 2026-10-01. **Status:** settled, task 7.2.

**Decision**

`app/risk/weightsets/` is a package and `weightsets/loader.py` is the one way
in. `load_weightset(name)` takes a *name*, reads the file through
`importlib.resources.files(WEIGHTSET_PACKAGE)`, and returns a frozen
`Weightset(ruleset_version, flags)`. A file that is absent, unreadable, is not
a mapping, names no `ruleset_version`, or holds no `flags` mapping raises
`WeightsetError` rather than answering with a default. The rows come back
frozen at both levels, and the file is read once per call with nothing cached
at module level.

**Why**

- **A weightset that is not found is an engine that scores every flag at
  zero.** That failure is silent and it is the one 7.1's completeness test
  exists to prevent, so the missing file is refused at the door rather than
  read as an empty mapping. Nothing here can default: a default version is a
  ruleset nobody wrote down, and a result would quote it.
- **A path assembled out of `__file__` stops working the moment the package is
  installed as a wheel or a zip.** `app/seed` and `D15` are the precedent for
  the same reason, and 7.1's test read by path only because the directory was
  not yet a package. The claim is held over the loader's source with an AST
  walk rather than over a run, because a checkout answers both reads
  identically and only an installed package tells them apart.
- **A name, not an address.** Completing the name with `.yaml` is what keeps a
  caller from scoring a screening against a file outside the package, which
  would be a weightset with no version and no completeness test.
- **Frozen, because a weight amended after the read is a score nobody can
  trace.** The record quotes the ruleset version beside the result, so the
  numbers it holds have to be the ones that version names.
- **Read per call, not cached.** A retune is a new versioned file, and the
  loader that only ever answers from the parse it did first is a loader whose
  process and weights disagree.
- **`pyyaml` is a production dependency.** The loader is production code, so a
  dev-only entry would have left the engine unable to start in deployment while
  the suite stayed green.

**What this forbids**

- No path, `__file__` or `pathlib` in the loader, and no default for a missing
  version, a missing file or a missing `flags`.
- No module-level cache of a parsed weightset, and no mutable rows handed back.
- No second reader of `v1.yaml` in production code; 7.1's test may keep reading
  the file directly, because its claim is about the file's contents.

**The gap this leaves, on purpose:** the loader parses and returns, and says
nothing about what a weight means. 7.3's lookup, 7.4's value mapping and 7.5's
sum are the questions asked of the rows it hands back, and the shape of a row
is still 7.1's claim against the file rather than this module's.

---

## D23 — An unweighted flag id is refused, never scored as zero

**Date:** 2026-10-01. **Status:** settled, task 7.3.

**Decision**

`app/risk/weightsets/lookup.py` holds `weight_for(weightset, flag_id) -> float`,
the one way from a flag id to the number the engine scores it with. It answers
from the `Weightset` record the caller is already holding and never opens the
package. An id the record carries no row for raises `WeightsetError`, and so do
a row that is not a mapping and a row whose `weight` is missing or is not a
finite number. The answer is always a `float`, and a read never writes: the
record stays frozen through the lookup.

**Why**

- **A missing weight scored as zero is the silent failure this project has
  spent two tasks walking towards.** `R = Σ(wᵢ·Fᵢ)` cannot tell a finding
  worth nothing from a finding nobody weighted, so the flag reaches the
  officer's list of reasons having moved no score, and a screening can be
  answered `low` on a finding the weightset never mentioned. `D22` refuses an
  absent file for the same reason at the door; this refuses the same fault one
  lookup later.
- **The refusal is `WeightsetError`, not `KeyError`.** It is a `ValueError`, so
  a caller already catching `ValueError` around the code that loads a weightset
  keeps catching it, and `WeightsetError` names a ruleset that is wrong rather
  than a caller that is buggy — which is what an id with no row is.
- **A message names the id and the ruleset version.** Both are rule names and
  nothing read off a document, so `D13`'s limit holds; a refusal nobody can
  locate is one nobody can fix.
- **The row's shape is judged here because 7.2 deliberately did not judge it.**
  `D22` passes a non-mapping row through, because the shape is 7.1's claim
  against the committed file. A weightset that is not the committed file is
  where a `band` with no `weight`, a string weight, or a boolean weight becomes
  a score, so the lookup checks what it is about to return a number from.
- **`nan` and `inf` are refused with the rest.** A `nan` weight poisons the sum,
  and every comparison against `nan` is false, so the band a `nan` score lands
  in is decided by nothing at all. A boolean is inside `[0, 1]` in Python's own
  arithmetic and is refused for the same reason `flags.py` refuses one.
- **The lookup does not check the id against `flag_ids.FLAG_IDS`.** The
  vocabulary is what a *rule may emit*; the weightset is what a *screening is
  scored against*. An id the vocabulary has and the file does not is 7.1's
  completeness test's claim about the file, and re-judging it here would give
  the same check two homes.

**What this forbids**

- No default weight, no `.get(id, 0)`, and no `try`/`except KeyError` around a
  row: every route to a number the file does not carry is refused.
- No coercion — a string is not parsed and a boolean is not read as `0`/`1`;
  the caller fixes the weightset instead.
- No second read of `v1.yaml`, and no module-level weightset the lookup loads
  for itself: `D22`'s one-way record stays the thing a caller holds.
- No mutation through the lookup, and no band returned from it. The band is the
  flag's own `weight_band` and the thresholds are 7.8's config.

**The gap this leaves, on purpose:** the lookup answers a number and nothing
about it — 7.4 maps a flag's `value` into `[0, 1]` and 7.5 is the sum that
turns two numbers into a score, so nothing here says what a weight is *for*.

## D24 — A flag's value reaches the sum through one gate, or not at all

**Date:** 2026-10-01. **Status:** settled, task 7.4.

**Decision**

`app/risk/values.py` holds `normalise_value(flag) -> float`, the one way from
a flag's `value` to the `F` of `R = Σ(wᵢ · Fᵢ)`. The answer is the value
unchanged, as a `float`, and **the map is the identity**: a flag's `value` is
already inside `[0, 1]` (`D6`), which is the range the engine sums in, so
nothing is rescaled. What the function owns is the other half of that
sentence — whether a value is a number the sum may carry at all. A record
carrying no `value`, a `value` of `None`, a boolean, and a value that is not a
real number inside `[0, 1]` all raise `FlagValueError`; nothing is clipped,
rounded, defaulted or parsed. The argument is typed `object` rather than
`EvidenceFlag`, because the refusals are for records this package does not
build.

**Why**

- **The interval is not written down here.** It is
  `flags._check_unit_interval`, the check 5.2 already put in the record's own
  constructor, so the engine's gate and the record's cannot drift apart. A
  second copy of `[0, 1]` beside the first is what 7.1 refuses for a weight.
- **`None` is refused rather than read as zero, and that is `D23`'s reason
  again.** A rule that measured nothing is silence, and `F = 0` puts "nobody
  measured this" into the sum as a real contribution of nothing — the same
  silent zero an unweighted id reaches the score as.
- **A boolean is refused, and `D6` is not changed to match.** A boolean is
  inside `[0, 1]` in Python's own arithmetic, so `EvidenceFlag(value=True)`
  still builds and 5.2's test still passes; the shape check and the engine's
  gate are two different questions. `True` scored as `1.0` would make every
  rule that fired a maximum-strength finding, and `False` scored as `0.0`
  would score "this rule did not fire" as a finding of no strength.
- **`tasks.md` 7.4's `None` case is unreachable as an `EvidenceFlag`, and `D6`
  predicted it.** `D6`'s own revisit clause named this exact disagreement and
  said it was 7.4's to reconcile rather than a reason to soften the range. The
  case is therefore written against a rule's own record before it became a
  flag, and against a flag read back from storage in Part 8, where `null` is a
  legal JSON value — which is `D6`'s stated revisit condition, answered with a
  refusal.
- **The refusal is `FlagValueError`**, the risk package's own type and a
  `ValueError`, so a caller already catching `ValueError` around the scoring
  keeps catching it. **No message quotes the value it refused**, on `D6`'s
  grounds: a value is exactly where something read off a document arrives.

**What this forbids**

- No rescaling, rounding, clipping or defaulting of any value, and no parsing
  of a string into a number.
- No boolean read as `0` or `1`, and no `None` read as `0.0`.
- No second statement of the interval in this module, and no softening of
  `flags.py` to make one of the three named cases reachable through the record.
- No weightset read here, and no flag amended by being normalised: 7.3 is the
  one way out of a weightset and this is the one way out of a value.

**The gap this leaves, on purpose:** nothing here says what a value *means*,
and nothing combines the terms — 7.5's sum is the next question, and it is
written against the one promise this module makes: every `F` reaching it is a
finite `float` inside `[0, 1]`, or the call was refused.

---

## D25 — The sum adds the terms and nothing else

**Date:** 2026-10-01. **Status:** settled, task 7.5.

**Decision**

`app/risk/scoring.py` holds `weighted_sum(flags, weightset) -> float`, the
one place the terms of `R = Σ(wᵢ · Fᵢ)` are added. It multiplies 7.3's
`weight_for` by 7.4's `normalise_value` per flag and accumulates with
`math.fsum`. It normalises nothing, clamps nothing, compares against no band
threshold, applies no hard rule, opens no file, amends no flag and drops no
finding — including a second finding carrying an id a first one already
carries. An empty sequence is `0.0`. A record carrying no `id` raises
`FlagValueError`, the sum's own addition, since the sum is the only place that
reads both fields of a term.

**Why**

- **Nothing is renormalised, and `D21` is the reason.** A weight is points on
  a 0–100 score, so three rows are summed as they stand. Dividing by the
  weights that fired would make a lone `high` finding worth less the fewer
  flags there were, which is the opposite of what corroboration is for.
- **The sum is allowed past 100 and 7.7's clamp is what an officer sees.**
  Three `high` findings at full strength is 195 points, and clamping here
  would discard the margin the band thresholds read.
- **An empty sequence is not the silent zero `D23` and `D24` refuse.** No
  finding fired, so there is no term to leave out; a document with no flags is
  a real answer a tier produces. A *measured* `0.0` is a term of nothing, which
  is a different thing from an unmeasured value and is in the sum.
- **A refusal propagates rather than becoming a term of nothing.** Skipping one
  bad flag and scoring the rest is the same fault as scoring an unweighted id
  as zero, one level up.
- **`math.fsum` for the exact sum rather than a running total.** The claim
  that order-independence is being bought is *weaker than it looks and is
  written down here*: over the committed weights and values in hundredths, no
  three-term ordering changes the result, measured exhaustively and then at
  random. What plain `sum()` does fail is the empty case, which returns an
  `int`. `fsum` is chosen because the correct answer is free, not because a
  bug was found.

**What this forbids**

- No normalisation over the flags that fired, and no division by a total.
- No clamp, no band comparison and no hard-rule floor here; 7.6, 7.7 and 7.9
  are those questions and each names its own answer.
- No dedupe by id, no sorting, and no flag dropped for carrying a value that
  scores nothing.
- No second statement of `[0, 1]`, no second reader of `v1.yaml`, and no
  softening of either gate to make a term reachable.

**The gap this leaves, on purpose:** this returns a number and nothing else.
7.6's hard-fail floor, 7.7's clamp, 7.9's band and 7.11's per-flag breakdown
are four later questions about the same number, and 7.15 is what assembles
them.

---

## D26 — The hard-fail floor is asked for, not held, and it is a floor

**Date:** 2026-10-01. **Status:** settled, task 7.6.

**Decision**

`app/risk/hard_rules.py` holds `apply_hard_rules(score, flags, hard_fail_ids,
*, floor=DEFAULT_HARD_FAIL_FLOOR) -> float`. The answer is `floor` when a rule
the caller named has fired and `floor` is above the score, and the score
itself otherwise; `floor` defaults to `90.0` and is held to
`[MIN_SCORE, MAX_SCORE]` (`0.0`–`100.0`, the two ends named here for 7.7's
clamp to read rather than retype). **The module holds no table of which rules
override** — the caller passes the ids in. `app/risk/flags.py` gained
`_flag_id(flag, purpose)`, shared with `weighted_sum`, which refuses a record
carrying no `id` and an `id` that is not a string.

**Why**

- **`app.risk` is asked rather than told, and 6.5's table is the answer it is
  asked with.** Which rules override is `runner._HARD_FAIL_IDS`, a union of
  each family's own table held beside its own labels, and the pipeline
  depends on this package's records and not the other way round. Importing it
  would make the engine depend on the tier that feeds it and would give the
  fact a second home; `test_hard_fail_floor.py` reads that table from the other
  side, the way 7.1's suite reads the watchlist bands, and holds the two
  together by test.
- **The floor is applied above the sum, never inside it.** `D25`'s module
  stays the sum its ruleset produced, and the override is one further question
  about it, so a score quoted beside its ruleset is not silently rewritten.
- **A floor and not a contribution, and not an addition.** A broken checksum
  does not add sixty points: `max(R, floor)` is the whole of it. `R + floor`
  would report 285 on a 0–100 scale for a blacklist hit with corroboration,
  and 7.7 would clamp that away and lose the margin the thresholds read.
- **The overriding flag's own `value` is not read.** A rule that fired without
  being able to quantify reports `0.0`, and 5.2 leaves `value` free precisely
  so it can. A floor weighted by the overriding finding's own strength would be
  outvoted by any pile of soft findings at all.
- **90 is above 7.8's `REVIEW_MAX` of 69 rather than on it.** The abstract
  says a hard rule *forces High Risk*, so the floor lands in High under the
  same arithmetic as any other score and `to_band` is not given a fourth case
  to special-case. It is also the only route to High that a single finding can
  take, which is `D21`'s other half: the heaviest weight in `v1.yaml` is 65.
- **The ids are consumed and never tested for truthiness**, because a generator
  is truthy whether or not it yields anything, and reading one as one would
  floor every screening a caller passed it. A bare `str` is refused for the
  same reason: `"WATCHLIST_HIT"` iterated is eleven characters matching no id,
  so the mistake would answer every screening with the sum it already had.
- **Every flag is read, including those after an override already fired.**
  Short-circuiting past a malformed record is the skip-the-bad-flag fault
  `D23` and `D25` refuse, one level up.
- **A malformed score or floor is refused rather than coerced.** A `nan`
  passes no comparison and would leave the score exactly as it was; a floor
  above the top of the scale can never be reached and one below the bottom is
  a no-op that reads as a configured override. Both are `FlagValueError`, and
  a message names the field and the type and never the value, on `D6`.

**What this forbids**

- No import of `app.pipeline`, no second hard-fail list, and no reading of
  `weight_band` as the override: a stolen-document hit is `high` and does not
  override, so a band could not stand in for the answer even where the two
  agreed.
- No summing, clamping, banding, deduplication or sorting here, and no writing
  to a flag or to the table the caller passed.
- No `max`/`min` spelling that could lower a heavier score, and no dependence
  on the overriding flag's `value`.

---

## D27 — The clamp is the last question asked of a score, and it answers rather than refuses

**Date:** 2026-10-01. **Status:** settled, task 7.7.

**Decision**

`app/risk/clamp.py` holds `clamp_score(score) -> float`. The answer is
`MAX_SCORE` above the scale, `MIN_SCORE` below it, and the score itself
otherwise, unchanged to the last bit. **Both ends are 7.6's, imported rather
than retyped** (`MIN_SCORE`, `MAX_SCORE`), and 7.6's `_score` is the one
validation of a score for the whole package, shared rather than written a
second time. **A separate module** rather than an addition to `scoring.py` or
`hard_rules.py`: 7.5's suite pins `scoring.__all__` and its import set, and
7.6's pins `hard_rules.__all__` and the *absence* of `max`/`min` there
("no `max`/`min` spelling that could lower a heavier score"). Putting a clamp
in either would have edited a completed task's claim rather than this one's.

**Why**

- **A clamp and not a rescale.** 195 points are held to 100 rather than
  divided by anything, and a score of 95 stays 95: the margin above a band
  threshold is kept everywhere the scale has room for it and lost only where
  the scale ends.
- **A score off the scale is answered, not refused.** `D23` and `D24` refuse a
  flag that cannot be scored, because there the answer would be a number
  nobody can trace back to a weightset. This is the other case: under `D21`
  corroborating findings are *how* a document reaches High, so 195 is a real
  reading that is merely larger than the scale can show, and refusing it would
  fail a document instead of reporting it. **What is refused is a score that
  is not a finite real number** — a `nan` passes no comparison, so a clamp
  written as two comparisons hands it straight back.
- **The clamp is the last step, after the floor, and the two commute**,
  because 7.6 holds a floor inside `[MIN_SCORE, MAX_SCORE]` and refuses one
  outside it. A hard fail therefore still reads `90` and not `100`: a clamp
  that reported the top of the scale would make every override
  indistinguishable from every pile of strong soft findings, which is what
  7.6's floor exists to prevent.
- **The lower bound is unreachable today and held anyway.** Every committed
  weight is positive and every value is in `[0, 1]`, so the sum is a sum of
  non-negative terms; 7.14's history term is the first thing that can move a
  score down, and a traveller with a verified history must not read below
  zero.
- **The spelling is `max(MIN_SCORE, min(total, MAX_SCORE))`** and not the
  other way round: `min(max(-0.0, 0.0), 100)` is `-0.0`, and an officer reads
  a number.

**What this forbids**

- No renormalisation, no division by the total, and no subtraction of the
  overflow.
- **No band threshold is consulted.** `MAX_SCORE` is the top of the scale and
  not 7.8's `REVIEW_MAX`; comparing against one is 7.9's question, and a clamp
  that stopped at 69 would answer two documents in the same band identically.
- No import of `app.pipeline`, and no second definition of either end of the
  scale — 7.6's suite already reads both names.
- No refusal of a score that is merely large or negative.

---

## D28 — The band thresholds are committed policy, and live in the risk package

**Date:** 2026-10-01. **Status:** settled, task 7.8.

**Decision**

`app/risk/config.py` holds `LOW_MAX = 34.0` and `REVIEW_MAX = 69.0`, and
nothing else. **The pair is committed policy rather than a deployment
setting**, so there is no environment variable for either and no entry in
`.env.example`. A retune of the pair is a change to `RULESET_VERSION` in the
same commit, the way `D22` says a change to the weights is.

**Why**

- **The abstract versions the thresholds and nothing else.** "Thresholds are
  chosen against a target false-alert rate for genuine travellers and a
  target catch rate for forged documents, and are versioned so that every
  change to policy is recorded." An environment variable is the one place a
  policy can change with nothing recording it, so it is the wrong home for
  the two numbers the abstract means to be versioned.
- **A deployment that retuned them would break `D21` silently.** The claim is
  that the heaviest weight in `v1.yaml` is 65 so that no single finding
  reaches High on its own. That claim is arithmetic over *two* numbers, and a
  `REVIEW_MAX` of 40 in one environment's `.env` makes it false there while
  every test in the repository still passes.
- **Beside the weights rather than in `app/config.py`.** The numbers a score
  is read against already live in the risk package — `MIN_SCORE` and
  `MAX_SCORE` in 7.6, `DEFAULT_HARD_FAIL_FLOOR` beside them, and the weights
  in `weightsets/v1.yaml` — and every reader of the pair is in the package
  (7.9, and 7.13's and 7.14's history bounds). `app/config.py` is the
  deployment and HTTP-boundary config: the CORS allowlist and the upload
  limits. Putting a ruleset number in it would put an `os.getenv` in the risk
  engine's import graph, and 7.13's `history_signal(..., config)` takes its
  bounds from here rather than from the environment.
- **Two floats, and a module that compares nothing.** The ends of the scale
  are floats, and 7.9's comparisons are between two numbers of one kind.
  Deciding a band is `to_band`'s question: a boundary written in both places
  is one that can disagree with itself, and `test_band_thresholds.py` holds
  this module to three statements so a second answer cannot arrive here.
- **34 and 69 are not round numbers, and both are read against the file.** A
  `low` row may never weigh more than `LOW_MAX` and no row may weigh more than
  `REVIEW_MAX`, so the two are held to `v1.yaml` by a test: 34 sits above two
  full-strength `low` findings (2 × 15) and below three, and 69 is one point
  clear of the heaviest weight in the file. The suite fails on a retune of
  either side rather than on a stale copy of the other.

**What this forbids**

- No environment variable and no `.env.example` entry for either threshold.
  `.env` is for deployment policy the operator owns — origins, retention,
  rate limits — and not for the ruleset's arithmetic.
- No second copy of either name anywhere in `app/risk`, and no comparison
  against `34` or `69` written out as a literal. Three suites carried their
  own `REVIEW_MAX = 69` while the threshold did not exist;
  `test_weightset_v1.py`, `test_hard_fail_floor.py` and `test_score_clamp.py`
  import it now, and the walk fails if one goes back to writing it out.
- No validation that raises at import, and no `assert` in the module: an
  `assert` is stripped by `-O` and a raise at import fails an import rather
  than a screening. The ordering is held by the suite.
- No use of `MAX_SCORE` as a band threshold. The top of the scale is not
  `REVIEW_MAX`, and 7.7's clamp must not stop at a band boundary.

**Revisit only if** Part 27's calibration moves the pair, which is a
`RULESET_VERSION` bump and a new `v2.yaml` rather than an edit to either
file, or if two deployments are ever given genuinely different thresholds —
which is a policy question the abstract answers by versioning, not a
configuration one.

---

## D29 — A band is decided from the score in one module, and each threshold belongs to the band below it

**Date:** 2026-10-01. **Status:** settled, task 7.9.

**Decision**

`app/risk/bands.py` holds `to_band(score) -> "low" | "review" | "high"` and
nothing else. The two thresholds are **read** from `app/risk/config.py` by
name, the score is validated by 7.6's `_score`, and the comparisons are
inclusive below: `score <= LOW_MAX` is `low`, `score <= REVIEW_MAX` is
`review`, anything above is `high`. **Nothing is clamped and nothing off the
scale is refused** — 7.7's clamp is what puts a score on the scale, and the
two questions compose rather than merge.

**Why**

- **`bands.py` rather than `config.py` or `clamp.py`.** One question, one
  module, the way 7.5, 7.6 and 7.7 are held. `D28` pins `config.py` to three
  statements and a module that compares nothing, so a comparison there would
  put a second answer in the file whose whole claim is that it holds none.
  `clamp.py`'s claim is that it edits a score and does nothing else, and 7.7's
  own suite holds that it must not stop at a band boundary.
- **Each `_MAX` is the last score of its own band, not the first of the next.**
  34 is `LOW_MAX`, so 34 is the top of `low` and 35 is the first `review`
  score. This is what the names already said, and the task's own table is
  34 → `low`, 35 → `review`, 69 → `review`, 70 → `high` because of it. So the
  three bands on the scale are `[MIN_SCORE, LOW_MAX]`, `(LOW_MAX, REVIEW_MAX]`
  and `(REVIEW_MAX, MAX_SCORE]` — each closed at its own top, which is what
  makes a boundary one score wide rather than a contested point.
- **A `nan` is refused because of arithmetic, not tidiness.** Every comparison
  against a `nan` is false, so a band written as two comparisons falls through
  both and answers `high` — the one answer a number that is not a number must
  never produce, on a document the officer is then asked to act on. A `bool`
  is refused for the neighbouring reason: `True` is `1`, and `1` is a real
  score reading `low`. Hence 7.6's `_score` is imported and shared rather than
  a second validation written beside it.
- **A row's band and a document's band are two different questions, and the
  committed file already answers them differently.** The `band` in `v1.yaml`
  is the severity class a *weight* sits in; this is the severity of a *sum*.
  Two 30-point rows are banded `review` in the file, and 30 points on a
  document reads `low`, because a clean document carrying one dating
  irregularity is a document with a question on it rather than a case for a
  second officer. The gap has a direction and `test_to_band.py` holds it: a
  row's band is never *softer* than the band its own weight reads as. Nothing
  here reads the weightset, and a band is never derived from a weight — a
  module that derived it would have to pick one of the two questions and
  would be wrong about the other.
- **`high` means corroboration or an override, and this is where that becomes
  visible.** `D21`'s claim that the heaviest weight is 65 is arithmetic; here
  it is a question asked of every row in `v1.yaml`, and the heaviest single
  finding reads `review`.

**What this forbids**

- No `34` or `69` compared in this package. `test_band_thresholds.py` already
  walks every module in `app.risk` and fails on a literal; `test_to_band.py`
  holds the other side of that walk — every comparison in `bands.py` reads a
  `Name`, and the set of names is exactly the score and the two committed
  thresholds, so a third edge cannot be added either.
- No second answer anywhere in `app.risk`. A walk over the `return` statements
  of every other module in the package fails if one of them hands back a name
  from `WEIGHT_BANDS`.
- No band name of its own. The three this module returns are held to
  `flags.WEIGHT_BANDS` by the same walk, so a fourth name, a rename, or the
  officer-facing "Low Risk" spelling would fail here rather than at a
  dashboard. 23.5 renders that spelling; this is not where it is chosen.
- No clamping, and no refusal of a score merely above or below the scale. A
  caller that skipped 7.7 has been handed the wrong number, and a refusal
  would fail a document instead of reporting it — the same trade `D23` and
  `D24` make against the other two gates.
- No import of `app.pipeline`, on `D6`'s one-way dependency: a band computed
  by asking a rule which tier it came from would be a band that moved with
  the cascade.

**Revisit only if** Part 27's calibration moves the pair, which is a
`RULESET_VERSION` bump and a new `v2.yaml` rather than an edit here; or if the
abstract's escalation rule needs a fourth band, which is a `WEIGHT_BANDS` and
`v1.yaml` change before it is a change to this module.

---

## D30 — A rejection is never derived from a band, and the walk is over the service

**Date:** 2026-10-01. **Status:** settled, task 7.10.

**Decision**

`test_review_never_rejects.py` asserts an absence over the whole of
`backend/app`, in two claims that cover each other:

1. **No statement puts the `review` band and a rejection in the same
   expression**, in Python or in a data file beside the code. A unit is a
   statement and its own subtree, because a mapping is a decision *derived*
   from a band and is therefore written where the two appear together: a
   table keyed by a band, a conditional on `to_band(score)` or on a flag's
   `weight_band`, a tuple of bands a rejection is taken from.
2. **The engine has no vocabulary for a decision at all** — no identifier
   and no string in `app/` is a rejection, so no band, score or flag can
   reach one.

**Why**

- **The walk is over the source, not over a run.** A band reaches no
  response body, no score and no officer's screen until 7.15, so a runtime
  assertion would pass for the wrong reason: there is no path left to run.
- **The second claim is what covers the first one's limit.** A path that
  builds the rejection in one function and chooses it in another puts the
  band and the word in different statements, which no statement-level walk
  can see. It is still a word in the service, and the vocabulary claim finds
  it.
- **Docstrings and comments are not code.** The parsing modules say they
  "reject" a line, a frame and a spelling repeatedly, and 17.11's
  reject-and-fallback path rejects a *summary*. A function body is therefore
  walked through, never read whole — Part 8's ledger will hold the officer's
  three choices in one module beside the band that was shown.
- **`refuse` is not a rejection word.** A gate refusing a malformed flag is
  not a refusal of a traveller, and this codebase uses that verb for
  `D23`/`D24`'s gates. The word list is `reject`, `deny`, `decline` and the
  entry/admission phrases, so a walk cannot fire on every validator sitting
  beside a band.
- **`high` is not this claim.** Whether an outcome may follow `high` is
  23.9's and Part 8's question, and the abstract gives the officer the
  decision on every case. Pinning it here would be a claim this task cannot
  source, so the band's vocabulary is the protected band only.

**What this forbids**

- No `review` beside a rejection in one statement, in code or in data. A
  policy written as configuration is still a mapping.
- No rejection word anywhere in `app/`. The first change that writes one is
  the first that must record here whether it is the officer's own choice
  being written down or a band being acted on.
- No client-side equivalent is policed here: 23.9's decision form *must*
  offer "reject", and nothing the browser renders changes a traveller's
  outcome. The server is where an outcome is decided and recorded.

**Revisit only if** Part 8's ledger records an officer's rejection in the
backend, which makes the vocabulary claim answer a question about recording
rather than deriving — and that is a decision to write down, not a test to
delete.

---

## D31 — The total is the sum of the terms it exposes, and a contribution carries no verdict

**Date:** 2026-10-01. **Status:** settled, task 7.11.

**Decision**

`app/risk/scoring.py` gains two frozen records and two entry points beside
7.5's `weighted_sum`. `Contribution` is exactly the four fields the task
names — `id`, `weight`, `value`, `contribution` — and nothing else.
`ScoreBreakdown` is a `total` and the tuple of `contributions` that add up to
it. `contributions(flags, weightset)` returns the per-flag terms,
`weighted_breakdown(flags, weightset)` returns them beside the total, and
**`weighted_sum` is now defined as `weighted_breakdown(...).total`**: the
float 7.5 promised is the `total` field of the very breakdown a caller reads
the rows from, so the number and its explanation cannot drift.

**Why**

- **One place multiplies the terms, so the two answers cannot disagree.** A
  separate total function beside a separate breakdown would be two
  implementations of `w · F` that happen to agree today. The task's claim
  holds by construction here rather than by two pieces of arithmetic being
  kept in step, which is `D22`/`D24`'s reason for a single gate applied
  twice.
- **"Pre-history" is 7.5's number, and the rows sum to exactly it.** The
  history term is 7.13's, the floor 7.6's and the clamp 7.7's; the breakdown
  is the score *before* all three, and a `total` that is the
  `math.fsum` of the shown `contribution` values is what lets a dashboard
  claim "the score is these rows added up" and be right.
- **A contribution is arithmetic and carries no band, decision or outcome.**
  7.10 holds that no band in the service may cause a rejection, and this is
  the record that sits directly beside a band on an officer's screen. A row
  that grew a `band` or a `decision` field would be the first thing to trip
  that walk, and it would put a meaning on a number whose only job is to be
  added up. What a document *means* stays 7.9's question asked of the total,
  and the officer's own decision is Part 8's.
- **The empty breakdown is a real answer.** 7.5 answers `0.0` for no flags,
  so no findings is an empty tuple summing to `0.0`, not a `None` and not a
  refusal — a clean document is a result a tier produces, and "no data" and
  "nothing fired" are different sentences to a screen.
- **A measured `0.0` is a row of nothing that is still shown.** On `D24`'s
  line, an *unmeasured* value is refused while a measured `0.0` is a real
  reading of no strength; dropping it would hide the fact that a rule fired.
- **Both records are frozen**, like `Weightset` and `TierResult`, so a caller
  cannot amend a term after the fact and leave the total disagreeing with the
  rows on screen.

**What this forbids**

- No `band`, `decision`, `outcome` or `verdict` on a contribution, and no
  rejection vocabulary in this module. The field set is pinned to the four
  the task names.
- No clamping, flooring, banding or history terming inside the breakdown: it
  is the pre-history sum, and 7.6, 7.7, 7.9 and 7.13 are four later
  questions about this number.
- No dedupe, no reorder and no dropped row: one row per finding, in arrival
  order, two findings of one id included.
- No second statement of `w · F` or of `[0, 1]`; both still come from 7.3,
  7.4 and this module's one `_term`.

**Measured, not asserted** — three wrong implementations were planted in
`scoring.py` and the new suite was run against each: a `total` that is the
clamp rather than the sum (caught), the `D21` renormalising mutant that
divides every row by the weights that fired (caught by five tests), and a
dedupe by id (caught by the new suite *and* by two of 7.5's own tests). The
source was restored and its SHA-256 verified against the pre-mutant backup.

**The claim the task names is necessary and not sufficient, and that is
written down rather than left implied.** A breakdown that renormalises every
row and then totals *those* rows is internally consistent — the rows do sum
to the total it reports — so the sum claim alone does not catch it. The
per-term claim (a row is its own `weight × value`) and the absolute
expectation of 51.25 are what catch it, which is why the headline test is
paired with them deliberately.

**The gap this leaves, on purpose:** 7.15's `compute_risk` is what assembles
this with the band, the ruleset version and the history term into the
`RiskResult` a response body carries, and 23.7 is what renders these rows to
an officer. Until 7.15 lands, no production path produces a breakdown either.

---

## D32 — The history layer's decay takes an age, and its half-life is committed policy

**Date:** 2026-10-01. **Status:** settled, task 7.12.

**Decision**

`app/risk/history.py` is a new module holding `decay(age_days,
half_life_days) -> float` and the constant `HISTORY_HALF_LIFE_DAYS = 180.0`.
The curve is `math.pow(0.5, age_days / half_life_days)`, so `decay(0, h)` is
exactly `1.0`, one half-life is exactly `0.5` and two are exactly `0.25`. Both
arguments are validated through 7.6's `_score`; a negative age and a
non-positive half-life are refused with `FlagValueError`.

**Why**

- **An age is supplied; a clock is never reached.** 7.13's
  `history_signal` takes a `reference_date` and does the subtraction, which is
  `D12`'s named dependency and the same one-way rule the watchlist seam keeps.
  A decay reading `today()` would make a screening's score depend on the day
  it ran, so a replay of a screening would not be a replay of its history
  term. `test_history_decay.py` walks this module's own source for clock
  calls and clock imports, on `test_tier0_timing.py`'s precedent.
- **A half-life is the curve, so the curve is written as a half-life.** The
  task's three points are the three the formula is pinned at, and they are
  exact in binary floating point, so the suite asserts them with `==` rather
  than a tolerance. **The third point is the discriminating one**: 4.8's claim
  is that an old outcome counts for *less*, which a linear ramp satisfies at
  every age. A ramp mutant passes at 0 and at 1 half-life and fails at 2 —
  measured, not assumed.
- **The half-life is committed, not a deployment setting**, on `D28`'s
  reason: the abstract calls the decay rate a calibration parameter, and one a
  deployment could retune would let what an old outcome is worth change with
  nothing recording it. No environment variable, no `.env.example` entry, and
  a retune is a `RULESET_VERSION` bump. **The number is a documented starting
  point and not a measurement** — no validation set exists in this repo, and
  the honest reading is the same one 7.8's thresholds get.
- **It lives in `app/risk/history.py` and not in `app/risk/config.py` beside
  the band thresholds.** `config.py` holds a *pair*, and `test_band_thresholds.py`
  pins its whole body to three assignments; the decay rate is not a band
  threshold and adding a third name there would widen a settled claim about
  a different question. The constant sits beside the function that reads it,
  which is also where a reader of the curve looks for its rate.
- **It is a weight in `[0, 1]` and nothing else.** Not a score, so never
  clamped to the 0-100 scale, never floored by 7.6, never banded by 7.9. It
  carries no band, decision or outcome field — `D30`'s walk would catch the
  first one written beside it — and `D31`'s split between what a number *is*
  and what it *means* is the same split one term further along.

**What this forbids**

- No clock, no `datetime`/`time` import and no attribute of any object but
  `math.pow`, all held by walks over the module's own source.
- No band, verdict or rejection vocabulary in the module, and no threshold
  compared against anything.
- No second statement of the half-life: the constant is the only place the
  number lives, and every claim that needs a rate reads it.
- No clamping, rounding or fixed precision. The exactness at one and two
  half-lives is the claim, so a curve that is correct to fifteen places and
  renders as `0.4999999999999999` on a dashboard fails the suite.

**Measured, not asserted** — four wrong implementations were planted and the
new suite run against each: a linear ramp (caught, 10 failures, and it passes
at one half-life), a decay reading `date.today()` (caught by all three source
walks), and a negative age answered rather than refused (caught). The source
was restored and its SHA-256 verified against the pre-mutant backup.

**The gap this leaves, on purpose:** nothing calls `decay` yet. 7.13's
`history_signal` is what sums verified outcomes through it, 7.14's is what
bounds the term, and 7.15's `compute_risk` is what puts the result in a
`RiskResult`. No screening reads a history term until all three land.

---

## D33 — The history signal is one signed sum, and its bound is the answer to "an old pass cannot move a band"

**Date:** 2026-10-01. **Status:** settled, task 7.13.

**Decision**

`app/risk/history.py` gains three names beside `decay`: the frozen
`PriorOutcome` record, the frozen `HistoryConfig` record, and
`history_signal(prior_outcomes, reference_date, config)`. The committed
`HISTORY_MAX_MAGNITUDE = 12.0` sits beside the half-life, and
`DEFAULT_HISTORY_CONFIG` is one `HistoryConfig` built from the two. A term is
`weight * decay((reference_date - outcome_date).days, half_life_days)` summed
by `math.fsum` over the **verified** outcomes and then clamped to
`+/- max_magnitude`.

**Why**

- **The weight is signed points, not a kind.** A verified pass carries a
  negative number and a verified fail a positive one, on `D21`'s own unit.
  4.8's continuity for a repeat case is then *reducing* a score rather than a
  second kind of term, one total is one sum, and the bound is symmetric for
  free. The record does not infer the sign and carries no meaning of its own.
- **The verified gate is a type, not a truthiness test.** `verified` is a
  `bool` and anything else is refused, so `verified=1` — the mutant this
  claim exists to catch — cannot stand in for an audited outcome. **A record
  is checked for shape before the gate is asked of it**, on 7.6's rule that a
  record carrying no `id` is refused rather than passed over; the age is
  computed only for a verified outcome, so an unaudited record dated after
  the reference is `0.0` rather than a refusal over a number the sum never
  uses.
- **`reference_date` is this function's subtraction and `decay` keeps
  reaching no clock.** `D12`'s named dependency, the same reference 5.8
  injects into the three date rules. `datetime` is imported for the *type*
  two ages are measured between, so 7.12's import walk is narrowed to ban
  `time`/`calendar`/`zoneinfo` and its attribute walk is scoped to `decay`'s
  own subtree, which is what keeps the claim true rather than what weakens
  it. A `datetime` is refused rather than accepted as a `date`: it is a
  subclass, and subtracting one from a `date` is a `TypeError`.
- **The bound is committed policy, on `D28`'s reason**, and it is a constant
  in this module rather than a third name in `app/risk/config.py` beside the
  band pair, for `D32`'s reason: that module holds a *pair* and its suite pins
  its whole body. **Neither calibration parameter is a measurement** — 4.8
  says both are set during validation and no validation set exists here.
  `max_magnitude` is validated into `(0, MAX_SCORE]` at construction, so a
  bound that bounds nothing is refused where it was written rather than
  answering every screening `0.0`.
- **"One old verified pass cannot move the band" is a claim about the
  bound, not about 34 and 69.** The band numbers are uncalibrated and
  unexercised end to end, so the widths are read off `app.risk.config` and
  `app.risk.hard_rules` and `HISTORY_MAX_MAGNITUDE < min(width)` is asserted
  as its own test. What makes the claim hold is `D29`: each `_MAX` is the
  *last* score of its own band, so a term that only reduces a score standing
  on one of the four edges lands back inside that band, and the bottom edge
  lands back on itself because 7.7 clamps. **A term that raises a score
  crosses two of those same edges, and a test asserts exactly that**, so the
  headline is not passing because `to_band` were being fed something
  constant.

**What this forbids**

- No unverified outcome in the sum, no clock anywhere in `history.py`, and no
  `LOW_MAX`/`REVIEW_MAX` import: this module is a magnitude on the scale and
  holds no idea where a band begins.
- No fourth field read off a record — the walk is over the `_field` call
  sites, so pulling an identity or a screening id in one `getattr` at a time
  fails.
- No band, verdict or rejection vocabulary, and no `outcome_kind`: the same
  walk 7.12 already applies now covers the signal beside the curve.

**Measured, not asserted** — eight wrong implementations were planted and the
two history suites run against each, every one caught: unverified outcomes
summed too, decay removed, clamp removed, clamped from above only, clamped by
absolute value, `reference_date` replaced by `date.today()`, `config` ignored,
and `verified` asked for truthiness. The source was restored and its SHA-256
verified against the pre-mutant backup.

**The gap this leaves, on purpose:** `history_signal` adds the term to
nothing yet. 7.14 is what adds it to a score and holds that the adjustment
never exceeds the bound, and 7.15's `compute_risk` is what puts the total,
its band and its contributions into one record an officer reads.

---

## D34 — The history term is added under the floor, and the bound is not written twice

**Date:** 2026-10-01. **Status:** settled, task 7.14.

**Decision**

`app/risk/history.py` gains `apply_history(score, prior_outcomes,
reference_date, config)`. It validates `score` with 7.6's `_score`, asks
`history_signal` for the term, and adds it. That is the whole function: two
calls, no comparison, no number of its own, and neither 7.6's floor, nor
7.7's clamp, nor 7.9's band reached from it.

**Why**

- **The order of the four questions is the design, and it is observable.**
  The abstract writes `R = Sum(w_i * F_i) + hard rules` with 4.8's signal
  added to the sum and the hard rules above it. A term applied *above* the
  floor could pull a hard fail's reading back down off it, which is not what
  an override means: 500 verified passes take worked example A's `0.0` to
  `-12.0` and the reading is still `90.0`, where the other order answers
  `78.0`. `apply_history` therefore adds and stops.
- **The bound is 7.13's and is not re-invented here.** The term arrives
  already inside `+/- config.max_magnitude`, so the adjustment is the term
  itself rounded by one addition. The headline sweep's only slack is
  `math.ulp` read off the operands — two roundings, one ulp — rather than a
  tolerance typed here, and the sweep runs seven scores by three bounds by
  four histories, every pile overflowing its bound by three orders of
  magnitude.
- **The floor and the clamp can only shrink the adjustment.** Both are
  1-Lipschitz, so the two *readings an officer compares* — taken with and
  without the term — differ by at most the term. That is what "only move the
  score by a limited amount" means at the end of the chain, and it is the
  claim five screenings (a floor swallowing the term whole, a clamp holding
  it the other way) are asked of.
- **A score off the scale is answered off the scale**, on 7.7's reason: 195
  points plus the term is a real sum waiting for the clamp to receive, and
  holding it here would make this task's answer depend on where the score
  stood.

**What this forbids**

- No second bound in this module: a walk over `apply_history`'s own subtree
  holds that it writes no number and compares nothing, and that it calls
  exactly `_score` and `history_signal`. A clamp written here would pass the
  bound headline and fail that walk — which is the planted mutant that
  answered one test and a half.
- No floor, no table of overriding ids and no band reached from here, so
  7.15's `compute_risk` is what composes the four questions.
- No second statement of `HISTORY_MAX_MAGNITUDE`: a retune moves the claim
  and the implementation together.

**Measured, not asserted** — five wrong implementations were planted and the
three history suites run against each, every one caught: the term doubled,
`abs`'d (a history layer raising a score because a traveller was confirmed
genuine), added twice, `config` ignored, and the bound clamped a second time
in this module. The last passed the headline and failed the structural walk,
which is the point of having it. The source was restored and its SHA-256
verified against the pre-mutant backup.

**The gap this leaves, on purpose:** nothing calls `apply_history` yet, so no
screening produces a band (see HANDOVER's Known Issues). 7.15's
`compute_risk` is what asks the four questions in order and puts the total, its
band, its contributions and the ruleset version into one record.

## D35 — The engine is one call that asks five questions in one order, and it is asked for the hard-fail table

**Date:** 2026-10-01. **Status:** settled, task 7.15.

**Decision**

`app/risk/engine.py` is a new module holding `compute_risk(flags, weights,
history=None, *, hard_fail_ids, floor=DEFAULT_HARD_FAIL_FLOOR) -> RiskResult`,
the frozen `RiskResult` (`score`, `band`, `contributions`, `ruleset_version`
-- the four the task names and no more) and the frozen `ScreeningHistory`
(`prior_outcomes`, `reference_date`, `config`). The composition is:

1. `weighted_breakdown` (`D31`) -- the sum and the rows it was made of;
2. `apply_history` (`D34`) -- 4.8's bounded term;
3. `apply_hard_rules` (`D26`) -- the floor, a `max`;
4. `clamp_score` (`D27`) -- the last question asked of a number;
5. `to_band` (`D29`) -- the reading an officer sees.

**The order is the decision, and it is held by a walk rather than by a
docstring.** A test reads the five calls out of `compute_risk`'s own subtree
and asserts their source order, asserts the call set is exactly those five
plus three argument checks and the record, and asserts **no binary operator
appears in the function at all** -- the engine adds, floors, clamps and bands
nothing. Any two of the five swapped answer a different question: `D34`'s
counterfactual is 500 verified passes taking a hard fail's `0.0` to `-12.0`
where the floor still reads `90.0` and the other order answers `78.0`. The
last two are worth naming separately: `to_band` bands an off-scale score
without refusing it, so swapping questions four and five changes no answer
anywhere on the scale and only the walk can see it.

**The hard-fail table is required, not defaulted.** `D26` holds that which
rules override is 6.5's answer and that the engine is asked rather than told,
and `D6`'s one-way dependency keeps `app.pipeline` out of `app.risk`, so the
ids are a required keyword-only argument. A default would be a second copy of
6.5's table somewhere it can drift, and an empty one would let a broken
checksum score 60 and read as a document with a question on it -- the opposite
of what an override means. A caller that forgot the table gets a `TypeError`
before any argument is read, which is the one refusal that cannot be caught
and answered around. **This is a deliberate departure from the task's literal
three-argument signature**, and it is the price of the decision above.

**`history` is a record and not a sequence, because an age needs the day.**
`D12`'s named dependency is a `reference_date`, and 7.13's is a sequence of
outcomes plus a config; the two cannot be told apart, so `ScreeningHistory`
holds all three, has no default for the reference and reads no clock, and
`history=None` is the only way to say "a first sighting". `None` skips 7.14's
call entirely rather than adding a term of nothing, and the two paths compare
equal because the answers are equal.

**The rows are the pre-history rows and they do not add up to the score.**
`D31` named the breakdown "pre-history" for exactly this: 4.8's term, 7.6's
floor and 7.7's clamp all sit between the rows and the number, so a document
with a history or a hard fail shows a score its rows do not add to. That is
stated on the record itself and asserted, rather than left to be discovered on
an officer's screen. A record whose rows tracked the score would be claiming
the column adds up to the band, and on a hard fail it does not.

**The version is the weightset's own, read off the record the caller passed.**
Not `app.version.RULESET_VERSION`: that is the version the service *ships*,
and a score is only comparable against the ruleset that produced it. A
weightset that is not the shipped one is therefore expressible, and a test
asserts a version the service does not ship comes back on the record.

**The findings are read once.** 7.6's floor asks its own question of the same
findings the sum was computed from, so `flags` is materialised into a tuple
once: a generator is a legal argument, and a hard fail still lifts the score.
A bare `str` or `bytes` is refused rather than iterated, on 7.6's and 7.13's
reason, and `weights` is refused as a `WeightsetError` rather than answering
the `AttributeError` 7.3's lookup would raise on a plain mapping.

**Worked example B, and the one reading it forced.** Section 3's Tier 1
finding is a face similarity of 0.41 against a 0.55 match threshold, and "R1
falls in the ambiguous band and the case is routed to Tier 2". **A threshold
rule that has fired reports its full strength**, which is how 6.2 and 6.4
write `value=1.0` for every threshold rule of their own, and 40 points is the
middle band. The competing reading -- that a finding's strength is *how far
below* the threshold it fell, `1 - 0.41` -- is measured in the suite rather
than argued about, and it is the reading the abstract's own sentence rules
out: it puts `R1` in the lowest band, which is the case the escalation rule
does not send on. **The similarity and the threshold are the flag's own
`expected` and `found`**, the two halves of the comparison the rule made, and
neither is a share of the weight. This is the same gap 5.3 recorded: the line
from "below the threshold" to `FACE_MISMATCH` is 13.16's to draw, and 7.1's
committed file already names 0.41-against-0.55 as the escalating case.

**What this forbids**

- No arithmetic, no comparison against a threshold, no second sum, no second
  floor, no hand-rolled band: the walk over `compute_risk`'s own subtree holds
  the call set and the absence of every binary operator.
- No import from `app.pipeline`, and no table of overriding ids -- the ids are
  an argument.
- No clock, no randomness, and no `reference_date` default.
- No fifth field: the record carries no decision, no outcome and no officer's
  action, which is `D30`'s claim held at the one place a band and a set of rows
  sit side by side.
- No second statement of `LOW_MAX`, `REVIEW_MAX`, `MIN_SCORE`, `MAX_SCORE` or
  the history bound; every number is read off the module that owns it.

**Measured, not asserted** -- seven wrong implementations were planted and the
suite run against each, every one caught: history applied *above* the floor
(`D34`'s own counterfactual, caught by the order walk and by the composed
end-to-end case), the band read off the pre-history total, the clamp dropped,
the hard-fail table defaulted, the contributions emptied, the findings not
materialised, and the version read from `app.version` rather than off the
weightset. The source was restored and its SHA-256 verified against the
pre-mutant backup.

**The gap this leaves, on purpose:** nothing calls `compute_risk` yet. The
band is reachable for the first time, and the thresholds it is read against
are still uncalibrated, so a band this produces is a designed reading and not
a measurement. Part 8's ledger is what puts it on an officer's screen beside
a decision, and Part 27 is what will have a number behind it.

---

## D36 — The URL is configuration, and the engine is built, never connected

**Date:** 2026-10-01. **Status:** settled, task 8.2.

**Decision**

`app/storage/db.py` is a new module holding exactly four names:
`build_engine(url=None) -> Engine`, `build_session_factory(engine)`, and the
two the service itself uses, `engine` and `SessionLocal`. The URL is
`app/config.py`'s `get_database_url()` -- `DATABASE_URL` when it is set to a
non-blank value, and `DEFAULT_DATABASE_URL` (`sqlite:///` plus the absolute
path of `backend/drishti.db`) when it is not.

**The URL is read in `app/config.py` and nowhere else, so `app/storage` never
touches the environment.** Two readers of one variable are two answers that
can disagree about what is configured, and `D28`'s note is that
`app/config.py` stays the deployment and HTTP-boundary config. `get_database_url`
is the answer 8.3 validates, and `build_engine` receives whatever it returns.

**A blank value is an unset variable, and `.env.example` is why.** That file
ships `DATABASE_URL=` with an empty value, and copying it to `.env` is the
documented first step -- so an empty string has to read as "not configured"
rather than as a URL nothing can parse. Surrounding whitespace is stripped for
the same reason.

**Two builders, not a factory that builds its own engine.** `build_session_factory`
takes the engine it is to bind to. The wiring it rules out is
`build_session_factory(url=None)`, which would leave the module-level
`SessionLocal` holding an engine no name in the module referred to, and would
hand a caller asking for a second database a second *pool* against the same
file while the engine it migrated stayed out of reach. The shape 8.9 needs is
two lines and reads as the two decisions it is:
`build_session_factory(build_engine(f"sqlite:///{path}"))`.

**The default is a file, and the file is absolute.** `:memory:` gives every
connection its own empty database, so the schema 8.8's alembic migrations
create in one process would be invisible to the service in another; a path
relative to the working directory would be a different database per launch
directory. The file sits beside the code and is covered by `.gitignore`'s
`*.db`.

**Building opens no connection, so importing the module has no side effect.**
`create_engine` parses a URL and allocates a pool; the file appears on the
first connect (asserted against a path in `tmp_path`). So a suite run leaves
no database behind, and a bad URL surfaces where a connection is wanted rather
than at the import of an unrelated module. **The module-level pair binds at
import time** -- that is what reading configuration once at start-up means --
while the builders re-read the environment on every call, so a test moves the
database without reimporting anything.

**`expire_on_commit=False`, and the reason is 8.10.** A repository method
returns the row it wrote and the caller's `with` block then closes the
session; with the default, every attribute of that returned object raises
`DetachedInstanceError` on the next read.

**What this forbids**

- No `MetaData`, no declarative `Base`, no table and no query: 8.4 owns the
  models, and a model module cannot be folded in here without that task
  saying so.
- No validation of the URL shape: 8.3 asks that question of
  `get_database_url`, not of the builder.
- No connection at import, no second engine for the default, and no
  `os.environ` read anywhere under `app/storage`.

**Measured, not asserted** -- three wrong implementations were planted and each
was caught: a `postgresql://` default (the suite fails at collection with
`ModuleNotFoundError: No module named 'psycopg'`, SQLAlchemy importing the
DBAPI to build the dialect -- which is 8.3's reason for validating the URL
before a builder is given one, and the reason no test here builds an engine
from a non-SQLite URL), a blank `DATABASE_URL` read as set (5 failures), and
`expire_on_commit` dropped (1 failure). All three were reverted.

**The gap this leaves, on purpose:** no table exists, so nothing here has been
written to or read from, and `build_engine` has never been given a URL this
environment can open a second dialect for.

## D37 — A URL is accepted by being parsed, and refused by being unusable

**Date:** 2026-10-01. **Status:** settled, task 8.3.

**Decision**

`app/config.py` gains `SUPPORTED_DATABASE_SCHEMES = ("postgresql", "sqlite")`
and a private `_validated_database_url(url)`, and `get_database_url()` now calls
it on the configured value. The answer is still the configured string -- still
`DATABASE_URL` when set, and `DEFAULT_DATABASE_URL` when unset or blank -- what
changed is that a value which is not a usable URL raises `ValueError` instead of
being handed on.

**The gate is `get_database_url`, and not `build_engine`, because `D36` made the
config the one reader of the variable.** A URL reaches `build_engine` from two
doors -- configuration, and a caller handing over a URL it chose (8.9's
temporary database). Only the first can be a deployment mistake, and only the
first is read at start-up, which is the moment a refusal is worth having.

**Validation is `sqlalchemy.engine.make_url`, and not a second opinion about
what a URL is.** `make_url` is the parser `create_engine` parses with, so
"acceptable here" and "buildable there" cannot drift apart; a `urlsplit` in this
module would be a second dialect of URL, and the two disagreeing is the bug
this gate exists to prevent. The price is that `app/config.py` imports from
SQLAlchemy for the first time -- the parser, and the exception the parser
raises, and nothing else.

**Accepting is parsing, and parsing connects to nothing.** `make_url` reads a
string and returns an object: no DBAPI is imported, no socket is opened, no host
is resolved. Measured in this environment, `create_engine` on the same
`postgresql://` URL raises `ModuleNotFoundError: No module named 'psycopg'` --
SQLAlchemy imports the DBAPI to build the dialect, having dialled nothing. So a
test that tried to prove acceptance by building an engine would be proving the
opposite, and none here does. The claim is held from both sides instead:
statically, that `app/config.py` imports no engine, session factory or dialect
anywhere in its source (an AST walk, which survives `psycopg` being installed
later); and at run time, with `socket.socket` refusing to be constructed while
the config answers.

**A scheme is the part before the `+`, so a driver suffix is not a different
backend.** `postgresql+psycopg://` is accepted and passed through whole; whether
that driver is installed is the builder's question at the DBAPI import, and
answering it there is honest in a way a URL-shape check could not be.
`postgres://` is refused, because SQLAlchemy has no dialect under that name --
it is Postgres' own older spelling, and accepting it would defer the failure to
a driver lookup that names nothing about the configuration. The refusal names
`postgresql` back to the operator.

**A PostgreSQL URL must name its database; it need not name its host.**
`postgresql:///drishti` is a real unix-socket connection and is accepted, while
`postgresql://` and `postgresql://user@host/` name a deployment that has to
have a database name and are refused. This half is policy rather than anything
the URL specification requires, and it is here because the failure it prevents
surfaces in 8.8's `alembic upgrade head`, against a file that may already hold
rows. A SQLite URL is required to be nothing beyond a URL: `sqlite://`, the
in-memory form 8.4 may want, is accepted.

**A refusal names the variable and quotes none of the value.** `AGENTS.md` says
no identity data reaches stdout or logs, and a configured database URL carries
a password, so the message names `DATABASE_URL` and the scheme -- the one
character group `make_url` will read out of an arbitrary string -- and nothing
else. A malformed URL is refused rather than falling back to
`DEFAULT_DATABASE_URL`: a misconfigured deployment coming up, empty, against a
local dev file is the worse of the two failures.

**The strip happens before the parse.** `make_url` refuses a leading space, and
a trailing newline from a docker-compose file is a value with a URL inside it;
the blank values `.env.example` ships stay an unset variable (`D36`).

**What this forbids**

- No engine, `Session`, `MetaData` or dialect in `app/config.py`, and no
  connection, host resolution or DNS lookup on any path through
  `get_database_url`.
- No re-serialisation: the answer is the operator's string, not
  `str(make_url(...))`, which normalises a Windows drive letter and would hand
  the engine a second spelling of the same file.
- No acceptance of a scheme the project does not ship, and no rewriting of one
  into another -- a refused URL is refused, not repaired.

**Measured, not asserted** -- four wrong implementations were planted and each
was caught: the gate removed entirely (15 failures), `postgresql` dropped from
the whitelist (11), the scheme refusal echoing the configured URL (1 -- the
test that the message carries no password), and acceptance that connects,
`create_engine(url).connect()` after the checks (9, including the static walk
and the socket test). All four were reverted. That last plant also left a
0-byte `backend/drishti.db` behind, which is `D36`'s "building opens no
connection" claim failing where it was forced to succeed; it was deleted.

**The gap this leaves, on purpose:** no PostgreSQL driver is installed here, so
nothing in this project has ever connected to one -- the gate is exercised, the
driver import is not. `postgresql+nosuchdriver://` is accepted here and refused
by `build_engine` at the dialect registry, which is the right division: the URL
names a backend this service ships, and whether that driver is installed is a
fact about the machine.

---

## D38 — The row records what was measured, and the in-memory URL is one database

**Date:** 2026-10-01. **Status:** settled, task 8.4.

**Decision**

`app/storage/models.py` is a new module holding `Base` (a `DeclarativeBase`
whose `MetaData` carries a naming convention) and one mapped class,
`Screening`, over the table `screenings`: sixteen columns, in the order the
task names them — `id`, `created_at`, `document_type`, `status`, `score`,
`band`, `mode`, `filename`, `image_width`, `image_height`,
`ruleset_version`, `model_versions`, `quality`, `flags`, `summary`,
`deleted_at`. `app/storage/db.py` gains one thing: `build_engine` gives an
**in-memory SQLite URL** a `StaticPool` with `check_same_thread` off, and
every other URL the pool its dialect ships.

**The models live beside the engine rather than in it.** `D36` forbade a
`MetaData`, a `Base`, a table and a query in `db.py`, on the grounds that a
model cannot be folded into the engine module without the task saying so.
This is the task saying so, and it says so by creating a module: a migration
(8.8) then has one module to import, a repository (8.10) one module to ask,
and `db.py` keeps being its builders plus the pool decision below.

**An opaque id, not a counter.** `id` is a `Uuid` primary key defaulted to
`uuid.uuid4` — `CHAR(32)` on SQLite and a native `uuid` on PostgreSQL, one
model for both. A screening id appears in a URL, in an audit event and in a
ledger entry, and a sequential integer in those places is a count a stranger
can walk up; `D13`'s opaque `entry_id` is the same argument about a token
that crosses a boundary.

**`created_at` is stamped by the ORM, in UTC, and nothing else on the row
is.** Three defaults are declared on the model — the id, `_utc_now()` and
`status="pending"` — and a test pins that a freshly written row carries values
on exactly those three beyond what the caller handed over. The clock is here
and not injected because a row's creation stamp is not check logic: it is the
record of when the write happened, and 11.1 creates the row in a request with
no other use for the time. Nothing in `app/pipeline` was touched, so the
walks that ban a clock in the MRZ parsers and the runner still hold. SQLite
hands the value back without a timezone (measured: the stored string is the
UTC wall clock and `tzinfo` is `None`), so the assertion about it is written
to hold under either spelling.

**The nine result columns are nullable because 11.1 answers before the
analysis has run.** `POST /api/screenings` returns a `screening_id` while the
cascade continues, so a row must be writable with a document type, a filename
and two pixel dimensions and nothing else. `score`, `band`, `mode`,
`ruleset_version`, `model_versions`, `quality`, `flags`, `summary` and
`deleted_at` are all `None` on such a row, and a JSON column that was never
written stays `None` rather than becoming `{}` — the distinction 23.6 shows
as a finding that cannot be located on the document rather than an omitted
one.

**Image dimensions are two integer columns, not a JSON object.** Every other
structured field on this row is JSON because it is structured; the two
dimensions are a pair of numbers an index, a filter or 8.7's migration can
name without parsing a string, and `app/schemas.ImageDimensions` is the shape
the API hands them back out in.

**`filename` is stored, and stored alone.** It is caller-supplied text and a
file name can carry a traveller's name, so this column is never indexed (8.7
indexes `created_at` and `band` only), never reaches a log or a ledger entry,
and no test writes an identity-shaped name into it. That is the whole of the
protection, and the reason the column exists at all rather than a content
address: 23.x shows the officer what they submitted.

**No column states a maximum length.** `String(32)` in SQLite is not enforced
at all, while PostgreSQL refuses an over-long value — so a length here is a
limit on one backend and a decoration on the other, and a limit nothing in
this repository can test. The two closed vocabularies are named module
constants instead: `SCREENING_STATUSES = ("pending", "completed", "failed")`
and `SCREENING_MODES = ("photo", "scan")`, with `DEFAULT_SCREENING_STATUS`
read out of the first rather than spelled beside it. The modes are held to
`app/schemas.py`'s own `Literal` by reading that annotation rather than
restating it, so the column and `/api/analyze` cannot drift apart. **Neither
vocabulary is enforced by the schema**, and that is deliberate: a column
cannot enforce it on both backends, and the writer (8.10) is where a refused
value belongs.

**Nothing in the module imports another application package.** `band` is text
rather than a type from `app.risk`, because 7.10 walks every module in `app/`
for a band standing beside a decision, and a table naming the three bands
beside a decision would be the mapping it is written to catch. A table that
stores the band it was handed is the record that walk exists to protect —
which also means the officer's own choice cannot become a column here without
failing `test_the_engine_has_no_vocabulary_for_a_decision_at_all`, since that
test refuses a rejection word anywhere in `app/`. What was decided belongs to
Part 10's events.

**The naming convention is deterministic, and the `ck` entry demands a
name.** 8.7 adds indexes and 8.8 downgrades a migration, so an object created
under one name and dropped under another is a migration that passes on an
empty database and fails on a real one.
`ck_%(table_name)s_%(constraint_name)s` means an unnamed check constraint
raises at `create_all` rather than taking a name no `DROP` can find.

**The in-memory URL gets a one-connection pool, because `sqlite://` is a URL
`D37` accepts on purpose.** SQLAlchemy answers a memory URL with a
`SingletonThreadPool`: one connection per thread, each opening its own private
database. Measured with SQLAlchemy 2.1.1, a second thread reading a row the
first had written gets `no such table: screenings`. A service running
synchronous endpoints in a thread pool is several threads, so this is not a
test detail but a way to run the whole service against a memory database and
see it empty from the second request. `StaticPool` with
`check_same_thread=False` makes that URL mean one database; every other URL
is left to its dialect, and the question is asked of the **parsed** URL with
the parser `create_engine` uses, on `D37`'s reason that two spellings of a URL
cannot disagree about which database they name. Measured spellings:
`sqlite://` parses to a `database` of `None`, `sqlite:///:memory:` to
`":memory:"`, and `sqlite:///drishti.db` to its file.

**What this forbids**

- No second declarative base, no table in `db.py`, and no import of
  `app.risk`, `app.pipeline` or `app.schemas` from `models.py`.
- No index on `filename`, on `band` or on `created_at` here: 8.7 owns the
  indexes.
- No filtering on `deleted_at` in the model, no default on any result column,
  and no column carrying an officer's decision or an outcome.
- No binary column, and no image bytes in any column.

**Measured, not asserted** — eight wrong implementations were planted and each
was caught: the `StaticPool` branch removed (2 failures — the cross-thread
read and the pool assertion), a seventeenth column added (1), the UTC stamp
replaced by a local one (1), the id default dropped (13, planted twice — once
as a missing default and once as a bare column), `quality` left without its
`JSON` type (the suite fails at collection, because no type can be inferred
for `dict[str, Any]`), the mode vocabulary widened to three names (2), and
`score` made non-nullable (14). All eight were reverted.

**The gaps this leaves, on purpose:** no migration exists yet, so nothing here
has been created by `alembic upgrade head` (8.8), and no repository has
written a row (8.10). The two vocabularies are named but not enforced, so a
row can still be written with a status no stage produces — the writer is where
that is caught. And no PostgreSQL driver is installed here, so the `Uuid`
column has only ever been a `CHAR(32)` on SQLite; the model is declared for
both backends and has run against one.

---

## D39 — The event is a row that is checked, not a row that is read for an answer, and it names its screening without pointing at it

**Date:** October 1, 2026. **Status:** settled, task 8.5.

**Decision**

`app/storage/models.py` gains `AuditEvent` over `audit_events` on the same
`Base` `D38` declared, with exactly the eight columns the task names in the
order it names them: `id`, `screening_id`, `batch_id`, `event_type`, `actor`,
`payload`, `record_hash`, `created_at`.

**A row here is checked, not read.** A `Screening` row is read for a current
answer; an event is read back to find out *whether the record is still the
record that was written*, which is what `record_hash` is for. Nothing on the
table is derived, defaulted or computed: `record_hash` is **stored, never
computed**, because a column that recomputed would hash an altered payload to
its new value and leave 9.17 with nothing to notice. The officer's own choice
is one of 10.1's event types rather than a column, so this table holds no
vocabulary for a decision — which is also what keeps
`test_the_engine_has_no_vocabulary_for_a_decision_at_all` passing over a
module that now names things that happened.

**`screening_id` is a plain `Uuid` column and no foreign key.** This is the
load-bearing choice, and 8.5's handover named it as the question 8.5 had to
answer first. Three reasons, in order of weight:

1. **A trail that a delete on `screenings` can empty is not a trail.** A key
   with `CASCADE` would take the events with the row; a key without it would
   block the delete. Neither is what an audit trail is for, and 9.17's answer
   for an event whose screening is gone should be `verified` — the row is the
   row that was written — not unanswerable.
2. **A key would be a guarantee on one backend and a comment on the other.**
   SQLite does not enforce declared foreign keys unless a pragma asks it to,
   so the constraint reads as protection on PostgreSQL and as documentation
   on SQLite. That is the same "a limit on one backend and a decoration on
   the other" argument `D38` applies to column lengths, and it is why a test
   that only deleted a screening would pass on a table that had one: the
   claim has to be held against the *declaration*
   (`column.foreign_keys == set()`, and no `REFERENCES` in the DDL).
3. **8.8's `downgrade` would have to find it.** A key is an object the
   migration has to name and drop in the right order, and the association is
   carried by the value in any case.

The association is real and is carried by the value, the way a batch id is
carried on the event it was anchored with.

**`batch_id` is the one nullable column, and `None` is a state rather than an
absence.** 9.16 stamps each event with its batch id when it is anchored, so an
unanchored event is one this table can hold, and `None` is precisely the
answer 9.17 reports as `unknown` — there is no root yet to walk a proof to.
Everything else is required: the screening, the type, the actor, the payload
and the hash. Six of the eight are asserted from the compiled DDL rather than
from the model, so a column that stopped being optional fails.

**The payload is required, and `none_as_null=True` is what makes that real
rather than declared — measured, not assumed.** With a plain `JSON` column, a
`None` payload is written as the JSON literal `null`: four characters of text
inside a `NOT NULL` column, read back as `None`, so the constraint is never
once exercised and an absent payload becomes a *third* spelling beside `{}` for
9.1's canonical JSON to hash. With `none_as_null=True` a `None` payload is SQL
`NULL` and the column refuses it. An event with nothing to add writes `{}`:
`D38`'s "`None` is not `{}`" distinction, and here `{}` is the honest "nothing
beyond the type and the actor" rather than a value nobody wrote.

**No vocabulary is held in this module, and the module's own namespace is what
holds that.** `event_type` is plain text, not an `Enum`, because 10.1's six
names are a constants module this file may not reach across the package to
read (`D38`'s "no import of another application package", now asserted over
the file with an AST walk). An `Enum` would freeze a second list beside the
first, and a 10.1 rename would silently change the schema. `actor` is
required — an event nobody recorded under is not a record — and is a
configured label (`STATION_LABEL`, 10.7) rather than an identity; **this
module never reads the environment**, since a model that read it would stamp
rows from whatever the process happened to be started with. The suite holds
the whole namespace, not just `event_type`: the only sequence-typed names in
the module are `SCREENING_MODES` and `SCREENING_STATUSES`, so a second
vocabulary added here fails rather than drifts.

**The ORM writes two columns on this table and three on the other.** `id` and
`created_at`, the same two as `Screening`, and no `status`: a row records
something that happened, so there is no pending state for it to hold, and a
status would be a lifecycle this table has no business carrying. Everything
else is what the recorder handed over.

**What this forbids**

- No `ForeignKey`, no `relationship()`, and no import of `app.version`,
  `app.audit`, `app.risk` or any other application package.
- No `Enum`, no `CheckConstraint`, and no event-type or actor vocabulary here.
- No `Computed` column, no `server_default`, and no default on any column but
  the id and the timestamp.
- No index on `screening_id`, `batch_id`, `event_type` or `created_at`: 8.7
  owns the indexes.
- No binary column, no image bytes, and no trigger: 9.12's append-only
  triggers are for `ledger_entries`, and tamper-evidence here is the hash
  rather than a constraint.

**Measured, not asserted** — fifteen wrong implementations were planted and
each was caught: a declared `ForeignKey` (3 failures), `actor` made nullable,
`batch_id` made required, a ninth column, a local clock, an event-type
constant added to this module, the id default dropped, the payload made
nullable, a `status` default copied over from `Screening`, a real `Computed`
`record_hash`, `event_type` as a real `Enum`, a real `CheckConstraint` on the
table, an import of another application package, a plain `JSON` payload
column, and `mapped_column(JSON, none_as_null=True)`. That last one does not
raise — it *warns* that no dialect is named `none`, so the constraint is
silently absent and the `IntegrityError` test demanding it fails. All fifteen
were reverted.

**The gaps this leaves, on purpose:** no index on any column (8.7), no
migration (8.8), no writer (10.2 is the only function allowed to create one),
and no `LedgerEntry` to anchor into (8.6). `event_type` and `actor` are
required but unenforced, so a row can still be written with a name or a label
no vocabulary holds — the writer is where that is caught, on `D38`'s reason.
And no PostgreSQL driver is installed here, so `Uuid` and the absent foreign
key have only ever been exercised as `CHAR(32)` and as nothing, on SQLite. The
no-foreign-key claim is a claim about what the schema *declares*, which is
exactly the thing that would bind on the other backend.

---

## D40 — The two indexes are on `screenings`, are named by the convention, and are not constraints

**Date:** October 1, 2026. **Status:** settled, task 8.7.

**Context.** 8.7 asks for "an index on `created_at` and one on `band`".
`band` exists on one table and `created_at` on two, so the task does not say
on its own where the pair belongs, and an index is the one thing in this
schema that is easy to add wrongly: the schema still works, and the mistake
only shows up as a slow query nobody attributes.

**Decision.** Both indexes are on `screenings`, declared with `index=True` on
the two columns, and neither is unique.

**Rationale.**

- **`screenings` is the only table a query filters by.** 8.13 reads
  `list_by_band` and 8.14 reads `list_by_date_range`, and both are reads
  over every row rather than over one row the primary key already finds.
  `audit_events` is read by `screening_id` and `ledger_entries` by
  `sequence`, both primary keys, so an index on `audit_events.created_at`
  would not be the index either query used — 24.8 lists one screening's
  events, and 9.17 verifies one screening's chain.
- **The names come from `NAMING_CONVENTION`, not from a hand-written pair.**
  `ix_screenings_created_at` and `ix_screenings_band` fall out of the `ix`
  entry applied to the table and the column, so renaming the table renames
  the index with it, and 8.8's `downgrade` drops by the same name its
  `upgrade` created. This is the `pk` argument the existing
  `test_the_base_names_its_constraints_deterministically` already makes.
- **Neither is unique.** `band` holds many rows and is `None` on every row
  11.1 has created before a stage scores it; `created_at` repeats whenever
  two screenings are written in the same instant. `unique=True` on either
  would refuse ordinary rows, which is what makes a schema test necessary
  rather than a row-count test.
- **Not a composite `(band, created_at)`.** The two filters are independent:
  8.13 filters by band with no date bound, and 8.14 filters by date across
  all three bands. A composite would serve the first and not the second.

**What this forbids**

- No index on `id` (the primary key is already one), on `filename` (it
  carries caller-supplied text), or on any `audit_events`/`ledger_entries`
  column.
- No `Index` object written out with a literal name in `models.py`, so a name
  cannot drift from the convention 8.8 relies on.
- No uniqueness on either index, and no claim in a test that an index makes a
  query return particular rows.

**Measured, not asserted** — `test_schema_indexes.py` reads the indexes out
of a created schema with `sqlalchemy.inspect` rather than out of
`Base.metadata`, because an `Index` in the mapping is not yet an index in a
 database, and it asserts that `CREATE TABLE` does *not* carry them: compiled
 against the SQLite dialect, the table DDL has no `CREATE INDEX` in it, so
 8.8's migration needs an `op.create_index` beside its `op.create_table` and
 a downgrade has something to drop. Three wrong implementations were planted
 and each was caught: `index=True` moved from `created_at` to `summary`
 (5 failures), a hand-written `Index("ix_screening_band", "band")` beside
 the convention (1), and `unique=True` on `band` (3, one of them an
 `IntegrityError` on the insert of two rows sharing a band and an instant).
 All three were reverted.

**The gaps this leaves, on purpose:** no index is measured against a real
 corpus — nothing here has a `screenings` table with rows in it beyond a
 test's handful, so these are the indexes two named queries would use, not
 indexes shown to speed them up. And the indexes have only ever been
 reflected on SQLite: no PostgreSQL driver is installed here, so the names
 8.8 depends on have been checked on one backend.

---

## D41 — Alembic reads the service's URL, not its own, and the migration is autogenerated

**Context.** 8.8 initialises alembic with the SQLite URL as the default and
adds the first migration matching the models 8.4 to 8.7 wrote.

**Decision.**

- **`alembic.ini` names no `sqlalchemy.url`.** `alembic/env.py` asks
  `app.config.get_database_url()` for the URL instead, which is `DATABASE_URL`
  when it is set and the absolute SQLite file in `backend/` when it is not. A
  URL in the ini would be a second spelling of the same setting, free to
  disagree with the one the service opens — and the ini's is the one that
  wins, so a deployment carrying a stale `sqlite:///...` would migrate a
  database the service never reads, with no error anywhere. This is `D37`'s
  "two spellings of a URL cannot disagree" reaching the migration tool.
- **Both paths in the ini are `%(here)s`.** `script_location` and
  `prepend_sys_path` resolve against the ini file rather than the working
  directory, so `alembic upgrade head` reaches `app` from `backend/` and from
  the repository root alike. Measured: run from the root with
  `-c backend/alembic.ini`, it migrates the default file and reports head.
- **`env.py` builds its engine through `app.storage.db.build_engine`** rather
  than alembic's `engine_from_config`, so a migration and the service share
  one place that decides what a URL means — including `D36`'s `StaticPool`
  for an in-memory SQLite URL.
- **`render_as_batch=True`** on both modes, because SQLite cannot `ALTER` most
  things and the next migration after this one will want to add a column.
- **The first migration is autogenerated, not hand-written.**
  `alembic revision --autogenerate` against `Base.metadata` means the three
  tables and their columns are the models rather than a copy of them. The two
  index calls are in it because 8.7 measured that SQLite keeps an index
  outside `CREATE TABLE`: `index=True` is a claim about the mapping, and only
  an `op.create_index` puts the index in a database.
- **One revision, not a sequence.** The revision id is alembic's generated
  hash, `down_revision` is `None`, and `downgrade` drops the two indexes before
  the three tables — so `upgrade head` then `downgrade base` returns an empty
  database, which is 8.9's round trip.

**What this forbids**

- No `sqlalchemy.url` in `alembic.ini`, and no URL literal in any version
  file.
- No relative `sqlite:///drishti.db` anywhere: it resolves against the working
  directory, so it is a different database per launch directory.
- No hand-edited column list in the first migration that the models do not
  declare.
- No second version file until a model has actually changed; amending the
  first migration after it has been applied is how two databases end up with
  different schemas.

**Measured, not asserted** — `test_alembic_migration.py` runs
`alembic upgrade head` against a `tmp_path` file and reads the schema back out
with `sqlalchemy.inspect`, then re-runs autogenerate against that database and
requires the diff to be empty; a column added to `models.py` and not to the
migration shows up as a diff. Three wrong implementations were planted and
each was caught (9 failures): `env.py` hard-coding
`sqlite:///drishti.db` instead of asking the config, the migration dropping
`ix_screenings_created_at`, and `image_height` made nullable in the migration
only. All three were reverted. The hard-coded-URL mistake additionally wrote
`drishti.db` into the repository root, which is why the suite asserts that no
`drishti.db` exists in `backend/` *or* in the working directory afterwards.

**The gaps this leaves, on purpose:** the migration has only been run on
SQLite — no PostgreSQL driver is installed here, so `D40`'s index names and
the `Uuid` column types have only been exercised on one backend, and 26.5's
deploy-time `upgrade head` is untested against a real PostgreSQL URL. Nothing
has been run in `--sql` offline mode against PostgreSQL either.

---

## D42 — A repository is handed its sessions, and `create` writes only what the upload carried

**Date:** October 1, 2026. **Status:** settled, task 8.10.

**Context.** 8.10 asks for `ScreeningRepository.create(...)` and a test that the
returned object has an id and a creation timestamp. `app/storage/db.py` already
holds a module-level `engine` / `SessionLocal` pair, so the obvious
implementation reaches for it; the task does not say whether it should.

**Decision.**

`app/storage/repository.py` takes a `sessionmaker[Session]` as a constructor
argument and opens one session per method call through it. It is required, not
defaulted, and `SessionLocal` is not the fallback.

`create` takes exactly the four columns an upload carried — `document_type`,
`filename`, `image_width`, `image_height` — and leaves `mode`,
`ruleset_version`, `model_versions`, `quality` and `flags` at their defaults.

**Rationale.** The module-level pair binds the URL at *import*, so a repository
using it is pinned to whatever `DATABASE_URL` said when the process started: a
test could not point it at a temporary file, and 8.9's round trip — which
migrates a file and reads it back — would be a claim about a database the
repository cannot write to. Taking the factory as an argument is what makes
D41's one database the same database in a request and in a test.

The five result columns are left out because 11.1 asks for an id *before* the
analysis has run. Taking them as arguments now would be a call shape written
for a caller that does not exist yet, and a score, a band or a finding must be
written by the stage that measured it — a method that could fill one in is a
method that could fill one in wrongly.

`create` validates nothing. Its caller is 11.1's route, where the upload has
already been checked by a schema, so a second set of rules here would be a
second answer to the same question that could disagree with the first. The
row's own constraints are the table's, enforced by the database.

**What this forbids**

- No repository reaching for `app.storage.db.SessionLocal`, and no `create`
  with a default argument for its sessions.
- No engine, URL, table or clock created in `app/storage/repository.py`.
- No result column ever written by a repository.
- No `session.add` without a `session.commit` in the same block, so a returned
  row is a stored row.
- No band beside a decision anywhere in the module: 7.10's walk over `app/`
  covers it, and a repository that stores what a stage measured is the split
  that walk exists to protect.

**Measured, not asserted** — `test_screening_repository.py` writes into a
`tmp_path` file migrated by `alembic upgrade head` rather than by
`create_all`, so a write against a column the migration never made fails here
rather than in a deploy. Two mistakes were planted and each was caught:
`create` returning after a `flush` instead of a `commit` (2 failures — the
returned row was in no committed transaction), and the repository binding to
`SessionLocal` in `__init__` (all 7 failures, and it wrote a `drishti.db` into
`backend/`, which was removed). All reverted. Both failures under the `flush`
mistake are the same claim seen twice — a row nobody committed is a row no
other session can find — and that is why the read back in the suite goes
through a *new* engine rather than a second session on the same one.

**The gaps this leaves, on purpose:** `create` is the only method, so the
repository is a one-method object until 8.11 to 8.15 add the reads, and
whether 8.12's `list` and 8.14's date range take a session or a factory is
undecided until they are written. `expire_on_commit=False` (D36) is a
precondition on the factory this repository is handed, stated in the module
docstring and not enforced here: a caller passing a plain `sessionmaker()`
gets a detached, unreadable row rather than an error.

## D43 — A missing row is an answer, and `get` takes the id type the column holds

**Date:** October 1, 2026. **Status:** settled, task 8.11.

**Context.** 8.11 asks for `get(id)` and a test that a missing id returns
`None` rather than raising. Two things are not settled by the task: whether
`get` raises for anything else (a malformed id, an id of the wrong type), and
whether the argument is a `uuid.UUID` or the string an HTTP path parameter
arrives as.

**Decision.** `get(screening_id: uuid.UUID) -> Screening | None` returns the
stored row, or `None` when no row carries that id, and raises nothing of its
own. It coerces no string, and it filters nothing.

**Why**

- **Absence is an ordinary outcome, not a failure.** A screening id reaches
  this table from a URL and from a queue, where "no such row" is an answer
  about the past rather than an exception. A raising `get` would push a
  `try`/`except` onto every caller and put a genuine fault — a dropped
  connection, a missing table — in the same place a stranger's stale link
  would be, which is how one becomes the other in a log at 3am.
- **The argument is the type the column holds.** `Screening.id` is a
  `uuid.UUID`; accepting `str` too would add a second spelling of an id to a
  module that has exactly one, on the same rule `D19` applied to a list being
  asked with what the document printed. Parsing a path parameter is the HTTP
  boundary's job, where 11.2's route already has a schema doing the rest.
- **`get` filters nothing today, on purpose.** 8.4's invariant is explicit
  that setting `deleted_at` leaves the row readable, so "missing" can only
  mean "never there" or "gone from the table" until 8.15 writes the
  exclusion rule and changes what every read means.

**What this forbids**

- No `NoResultFound`, no `KeyError` and no `try` inside `get`.
- No `uuid.UUID(...)` coercion, and no `str` in `get`'s signature.
- No `deleted_at` filter added by `get` before 8.15 writes one rule for
  every read.
- No `SessionLocal` and no engine: `get` opens its session from the factory
  the repository was constructed with, like `create` (`D42`).

**Measured, not asserted** — `test_screening_repository.py` reuses 8.10's
migrated-file fixture. Three mistakes were planted and each was caught: `get`
raising `KeyError` on absence (3 failures), `get` returning `None`
unconditionally (4 failures — the absence tests alone would have passed it),
and `get` binding to `db.SessionLocal` (6 failures, and it wrote a
`drishti.db` into `backend/`, which was removed). All reverted.

**The gaps this leaves, on purpose:** the read that excludes a soft-deleted
row does not exist, so 8.15 is where every read here changes at once and
where `get`'s "missing" gains a second meaning. Whether 8.12's `list` and
8.14's date range return a list plus a total, or a page object, is still
undecided until they are written.

---

## D44 — A page is rows and the total together, and the bounds that took it

**Date:** October 1, 2026. **Status:** settled, task 8.12.

**Context.** 8.12 asks for `list(offset, limit)` with a test asserting
pagination bounds and total count. Two things are not settled by the task: a
count is half of the answer, so whether the method returns a bare list plus a
separate count or one object carrying both; and what a request for a page
that does not exist is — an empty page, or a fault.

**Decision.** `list(offset: int, limit: int) -> ScreeningPage`, where
`ScreeningPage` is a frozen dataclass carrying `rows: tuple[Screening, ...]`,
`total: int`, `offset: int` and `limit: int`. `total` counts the table, not
the page. Rows come back ordered by `created_at` then `id`. An `offset` past
the last row is an empty page carrying the true total; a negative `offset`
and a `limit` below one raise `ValueError` before any statement is emitted.
No filter is applied.

**Why**

- **The count belongs beside the rows, not in a second query.** 11.3's route
  renders a paginated history and 24.3's table needs to size every page; a
  bare list would make each of them issue a second `COUNT` that could
  disagree with the rows beside it, since a row written between the two
  statements lands in one and not the other.
- **The page remembers the window it was taken with.** "Showing 21–40 of 137"
  is three numbers, and a page carrying only rows and a total would make the
  route re-derive the window from a request object it no longer holds.
- **An `offset` past the end is an answer.** D43's reasoning, unchanged: a
  caller paging to the end of a shrinking table is asking an ordinary
  question, and the answer is no rows. Raising would put a `try`/`except` on
  every paged view to catch the ordinary case.
- **Bounds that describe no page are refused rather than clamped.** A
  negative offset and a zero limit are not "near" a page; silently clamping
  them answers with a window the caller did not ask for, and a paged UI that
  quietly re-reads the same rows is harder to diagnose than a `ValueError` at
  the boundary that produced it.
- **The order is total, and it is the one the index already serves.** Two
  screenings can share a `created_at` instant, so ordering by that column
  alone is partial: a row could appear on two pages, or on none. `id` breaks
  the tie. `ix_screenings_created_at` (D40) covers the leading column.

**What this forbids**

- No `deleted_at` filter in `list` before 8.15 writes one rule for every
  read, on D43's reasoning.
- No band beside a decision, no `SessionLocal`, no engine, no clock: 7.10's
  walk and D42's injected sessions cover the read as they covered the write.
- No `LIMIT` cap in this module. The largest page a caller may ask for is
  11.3's schema's decision, and a cap written here would be a second number
  to keep in step with it.
- No `list_by_band` / `list_by_date_range` re-implementing the ordering: 8.13
  and 8.14 add a filter to this statement, not a second way to spell it.

**Measured, not asserted** — 12 new tests in
`test_screening_repository.py`, against 8.10's migrated-file fixture with the
table emptied first, because a *total* is only an absolute number against a
table the test controls. Four mistakes were planted and each was caught:
`ORDER BY` removed (1 failure), `total` measured from the returned rows
instead of the table (3), bounds clamped instead of refused (3), and `list`
bound to `db.SessionLocal` (12, and it wrote a `drishti.db` into `backend/`,
which was removed). All reverted. `check-all.ps1` exits 0 — 3499 backend,
45 frontend, build.

**The gaps this leaves, on purpose:** `list_by_band` (8.13),
`list_by_date_range` and `list_by_document_type` (8.14) are not written, and
`soft_delete` (8.15) will change what every read here returns. Whether 8.14
reuses `ScreeningPage` or answers a bare list — a date range has no natural
page window of its own — is undecided until it is written.

---

## D45 — A band filter is `list`'s page with a filter, and holds no vocabulary

**Date:** October 1, 2026. **Status:** settled, task 8.13.

**Context.** 8.13 asks for `list_by_band(band, offset, limit)` with a test
that a filtered list never returns a row from another band. D44 already
settled the shape of the answer and forbade a second spelling of the order,
but three things are not settled by the task: whether the filter is one
statement or a second copy of `list`'s, whether `total` counts the table or
the match, and what the method does with a band it does not recognise — or
with `None`, which is a state the column really holds.

**Decision.** `list_by_band(band: str | None, offset: int, limit: int) ->
ScreeningPage`, where `total` counts the rows that matched rather than the
table. The rows and the count are one statement each, both carrying the
filter, and both are written once in a private `_page(condition, offset,
limit)` that `list` also calls with `true()` — so the order, the bounds and
the refusal are written once and reached twice. `band` is compared as it was
handed, with no check against `app.risk.bands`; a name no row carries is an
empty page, and `None` filters on `band IS NULL`, the rows nothing has scored
yet. `deleted_at` is still not a filter.

**Why**

- **A filter added to `list`'s statement, not a second copy of it.** D44
  forbade the re-spelling and 8.13 is where that promise is either kept or
  broken. Two statements would put the order and the count in two places to
  keep in step, and the second copy would be the one nobody re-reads when
  `list` changes.
- **The total counts the match.** It is the number 11.3's route sizes its
  pages by: three rows read as a table of five would render a second page
  holding nothing, and a caller paging to the end of the band would never
  reach it.
- **No vocabulary here.** The band is a value a stage wrote and this module
  stores what it was handed. A repository that validated against
  `app.risk.bands` would be a second answer to a question 7.9's `band()` and
  the weightset's `weight_band` already give, would have to be edited when
  those bands are retuned, and would raise on a name a future ruleset
  introduces before 7.9 could band anything with it. 7.10's walk over
  `app/` protects against a band standing beside a decision; it does not
  protect against a table of band names, and a repository holding one is
  close to what that walk is looking for.
- **`None` is a band, not an absence of one.** 11.1 creates the row before
  any stage has run, so `band` is `None` on every screening until 7.9's
  result is written. A filter that refused `None`, or that answered the
  whole table for it, would put a second query on every route asking what
  has not been scored yet — and "nothing has scored it" is a state a queue
  is asked about daily, on D43's reasoning that absence is an answer.

**What this forbids**

- No `deleted_at` filter here; 8.15 writes that rule once for every read.
- No import of `app.risk.bands`, no `WEIGHT_BANDS` check, no `ValueError`
  for an unknown band: an empty page is the answer.
- No band beside a decision, no `SessionLocal`, no engine, no clock, and no
  second `ORDER BY`: D42 and D44 cover this read as they covered the last.

**Measured, not asserted** — 10 new tests in `test_screening_repository.py`
(11 items, one of them parametrized over two bounds), against 8.10's
migrated-file fixture with the table emptied first. Five mistakes were planted
and each was caught: the filter dropped from the row query (6 failures), the
filter dropped from the count (5), `ORDER BY` removed (2), `band=None`
answered as the whole table (1), and bounds clamped instead of refused (5).
All reverted. `check-all.ps1` exits 0 — 3510 backend, 45 frontend, build.

**The gaps this leaves, on purpose:** `list_by_date_range` and
`list_by_document_type` (8.14) are still unwritten and reuse `_page`; and
`soft_delete` (8.15) will change what this filter returns, since a
soft-deleted row is still in this table and still carries its band.

---

## D46 — A range and a kind answer rows, and a range is in UTC

**Date:** October 1, 2026. **Status:** settled, task 8.14.

**Context.** 8.14 asks for `list_by_date_range(start, end)` and
`list_by_document_type(doc_type)`, a test each. D45 settled the shape of a
filtered *page*, and neither signature takes an `offset` or a `limit`, so
whether these two reuse `ScreeningPage` is a question the task did not
answer. Four more were left open alongside it: whether a range's ends are
inclusive, what an open end is, what a bound means in a column SQLite reads
back without a `tzinfo`, and whether a kind is checked against a vocabulary.

**Decision.** Both methods answer a `tuple[Screening, ...]` and take no
bounds. They are reached through a second private statement,
`_rows(condition)`, which orders by the same `_in_read_order()` helper
`_page` uses, so there is one order in the module and there is no count to
report for a read that has no window. A range's two ends are inclusive and
either may be `None` for an open end; both ends open, an inverted range, and
a bound carrying no timezone are refused with `ValueError` before any
statement is emitted, and a bound carrying an offset is converted to UTC.
`document_type` is compared as it was handed, with no vocabulary.
`deleted_at` is still not a filter.

**Why**

- **Rows, not a page.** A `ScreeningPage` carries the window it was taken
  at. A range and a kind were given none, and a page carrying an `offset`
  and a `limit` the caller never chose is a claim about a page nobody asked
  for — the same reasoning D44 applied to a cap. 11.3 wants band,
  document-type, date-range *and* pagination parameters over one listing;
  composing those is that task's decision, to be made with its caller in
  front of it rather than inherited from here.
- **One order, one statement.** D44 forbade a second spelling of the order
  and D45 kept it inside `_page`. `_rows` is the same rule reached without
  a window, and both call `_in_read_order()`, so the `created_at` then `id`
  pair is written once for the whole module.
- **Both ends inclusive.** `created_at` is stamped to the microsecond, so an
  exclusive end silently drops the last row of whatever period was asked
  for, and the drop is indistinguishable from a document nobody screened.
- **An open end is `None`; both open is a fault.** "Everything since" and
  "everything up to" need an open end, and `None` is the honest spelling of
  one. Both ends open names no period at all, and D45's precedent is that a
  bound describing nothing is refused rather than quietly answered: an
  inverted pair is nearly always two bounds transposed, and answering it
  with nothing would render as an empty history. `list()` already answers
  "every row", so refusing does not leave the question unanswered.
- **A range is in UTC, converted rather than assumed.** The ORM stamps
  `created_at` in UTC, and SQLite's `DATETIME` drops an offset rather than
  applying it — measured, not read: a row stamped 09:00 UTC is *not* found
  by a bound written as 14:30+05:30 compared as handed. Converting makes the
  filter the instant the caller named. A *naive* bound is refused rather
  than converted, because it means one instant on SQLite (compared as UTC)
  and another on PostgreSQL (resolved against the server's zone); one
  spelling of the query must not mean two instants on two backends.
- **No vocabulary for a kind.** `document_type` is a claim the upload
  carried, not a value a stage wrote, and the closed set of kinds is
  whatever `app.schemas` accepts at the boundary that received the file. A
  repository holding that set would be a second answer to a question the
  schema already asks, and would raise on a kind a future schema introduces.
  The column is not nullable, so `None` is not a stored value either.

**What this forbids**

- No `offset`/`limit` on either read, and no `ScreeningPage` built from a
  window the caller did not choose.
- No inclusive-to-exclusive change, no silent clamping of an inverted range,
  and no accepting a naive bound.
- No `deleted_at` filter here; 8.15 writes that rule once for every read.
- No import of `app.schemas` and no set of document kinds beside a read: a
  kind no row carries is an empty answer.
- No second `ORDER BY`, no `SessionLocal`, no engine, no clock: D42 and D44
  cover these reads as they covered the last.

**Measured, not asserted** — 22 new tests in `test_screening_repository.py`
(19 functions, three of them parametrized), against 8.10's migrated-file
fixture with the table emptied first. Seven mistakes were planted and each
was caught: the range filter dropped (1 failure), the ends made exclusive
(1), the bound compared as handed (1), a naive bound accepted (1), a range
naming no range accepted (1), the kind filter dropped (1), and `ORDER BY`
removed from `_rows` (1); `_rows` bound to `db.SessionLocal` fails 22 and
writes a `drishti.db` into `backend/`, which was removed. All reverted.
`check-all.ps1` exits 0 — 3532 backend, 45 frontend, build.

**The gaps this leaves, on purpose:** `soft_delete` (8.15) is unwritten, and
it changes what *every* read here returns — a soft-deleted row is still in
this table and still carries its `created_at` and `document_type`. And
11.3 still has to decide how band, kind and range compose with one window,
which no method here answers.

---

## D47 — A soft-deleted row is answered by no read, and deleted once

**Date:** October 1, 2026. **Status:** settled, task 8.15.

**Context.** 8.15 asks for `soft_delete(id)` setting `deleted_at` and
excluding soft-deleted rows from every read, with a test. Three things the
task did not answer: which reads the rule covers — `get` was left open, and
24.5's confirm-then-delete reads the row it is about to delete; what
`soft_delete` does to a row that is already soft-deleted; and where the
instant on the column comes from, since this module reads no clock.

**Decision.** `soft_delete(screening_id: uuid.UUID, *, deleted_at: datetime)
-> Screening | None`. It stamps the column and removes nothing, commits, and
returns the stored row — or `None` when no *live* row carries that id. It
finds its row through the same `_not_soft_deleted()` every read carries, so a
second delete is answered as absence and the first stamp stands. The stamp is
keyword-only, must carry a timezone, and is converted to UTC through the
existing `_utc_bound`. The exclusion is one private helper,
`_not_soft_deleted() -> Screening.deleted_at.is_(None)`, applied in `get`,
in `_page` (both the row statement and the count) and in `_rows`, so `get`
is included and a page's `total` moves with the rows it counts.

**Why**

- **`get` is included.** D43 left "missing" meaning "never there" or "gone
  from the table" until this task; it now means "never there" or "deleted",
  which is the honest answer to a question about a screening's *present*.
  24.5's confirmation step reads the row **before** it deletes it, so the
  one read that needs it is untouched by the rule — a delete that confirmed
  its target first still finds it. A caller that genuinely needs a deleted
  row (a restore, an audit context) has no method to reach for: that is a
  decision owed, not a bypass to be taken here.
- **One helper, not five filters.** D44 and D45 forbade a second spelling of
  the order and of the count. The same reasoning covers the exclusion: the
  rule is written once, and `soft_delete` reads through it as well, so a
  delete that found a row the reads skip would be deleting something no
  read could show.
- **The count moves with the filter.** `total` is the number 11.3's route
  sizes its pages by and 24.3's table renders "showing 21–40 of"; a total
  that counted a deleted row would render a final page holding nothing the
  caller could see.
- **A page is taken over the live rows.** `offset` and `limit` apply after
  the exclusion, so deleting the oldest row does not slide the window and
  drop a live row off the end of the history.
- **A row is deleted once; the second delete is absence.** Re-stamping
  silently is the option that loses the trail — two clicks an hour apart
  would leave only the second on the row. Answering `None` rather than
  raising keeps D43's rule that absence is not a failure, and the fact that
  a row was deleted, and who deleted it, is Part 10's event rather than a
  second reading of this column.
- **The stamp is taken, not read.** `create` takes its clock from the ORM's
  defaults because the row's creation is a fact the module owns; the delete
  is a fact about a request handled elsewhere, and `tasks.md`'s reference
  date rule already keeps clocks out of logic. Injecting it keeps D42's "no
  clock in this module" true, and lets a test assert the exact instant.
- **Naive is refused, offset is converted.** D46's reasoning, applied to
  the column rather than to a bound: SQLite drops an offset instead of
  applying it, and a naive stamp is one instant on SQLite and another on
  PostgreSQL. Measured, not asserted — the same instant handed in UTC and in
  a zone 5:30 east reads back as the same row value only under conversion.

**What this forbids**

- No `get_including_deleted`, no `include_deleted=True` flag, and no read
  that skips the rule: a caller needing a deleted row gets a new decision.
- No hard `DELETE` in this module, and no clearing of any other column: the
  row is still the record 9.17 verifies and 24.9 shows.
- No `datetime.now()` in `app/storage/repository.py`, and no
  `app.storage.models._utc_now` import to borrow one.
- No re-stamping a deleted row, and no `ValueError` for a second delete.
- A second spelling of the exclusion: if another read appears, it reaches
  `_not_soft_deleted()` or `_page`/`_rows`, it does not spell the filter.

**Measured, not asserted** — 17 new tests in
`test_screening_repository.py`, against 8.10's migrated-file fixture with
the table emptied first. Six mistakes were planted and each was caught: the
filter dropped from `get` (2 failures), the filter dropped from the count
statement (2), the filter dropped from `_rows` (2), `soft_delete` finding
its row without the filter so a second delete re-stamped it (1),
`soft_delete` issuing a `DELETE` (4), and the stamp stored as handed rather
than converted (3, overlapping the delete). All reverted.
`check-all.ps1` exits 0 — 3549 backend, 45 frontend, build.

**The gaps this leaves, on purpose:** nothing reads a soft-deleted row, so
a restore, a retention sweep and an audit view that shows deleted rows each
want a method that does not exist yet. 11.3 still has to compose band, kind
and range with one window. And 9.17's verification reaches
`audit_events` rather than `screenings`, so nothing yet proves a deleted
row's *history* survived — 24.9's audit view is where that question
arrives.

---

## D48 — A canonical record is one spelling, and only dates are coerced

**Date:** October 1, 2026. **Status:** settled, task 9.1.

**Context.** 9.1 asks for `canonical_json(obj)` producing deterministic JSON —
sorted keys, no whitespace, explicit nulls, no floats, dates as ISO strings —
with a test that key order in the input does not change the output. Four of
the five named rules are refusals or coercions, and the task says nothing
about a value outside them: a `float`, a set, a `uuid.UUID`, a key that is not
text. The handover records that the refusal is the safer half, that `int` and
`bool` must both be said out loud because `bool` is a subclass of `int`, and
that `score` is a float on `screenings`, so whatever 9.3 hashes and 9.17
recomputes has to agree about it.

**Decision.** `app/ledger/canonical.py` holds `canonical_json(obj) -> str` and
`CanonicalJsonError(ValueError)`. Keys sorted by code point, separators
`(",", ":")`, `ensure_ascii=True`, `None` written as `null` and never dropped,
`bool` written as `true`/`false`, `int` written as itself, `datetime` and
`date` written as ISO strings, lists and tuples as arrays in their own order.
**Everything else is refused, and only a `datetime` is ever coerced.** An
aware `datetime` is converted to UTC before it is spelled, so one instant has
one spelling; a naive one is spelled exactly as it stands and is not read as
UTC.

**Why**

- **Refused, not stringified.** A `set` has no order to canonicalise, a
  `uuid.UUID` has two spellings (hyphenated and bare hex) and `bytes` has no
  JSON form at all, so each would need a rule this module would have to
  invent. Refusing means the record's shape is one deliberate decision in one
  place — the writer that builds it — rather than a set of coercions spread
  across callers that each guessed differently. `D23` and `D42` hold the same
  line: an unrepresentable value is refused, never quietly turned into
  something else.
- **A `uuid.UUID` is refused, so 10.2 spells ids itself.** `AuditEvent`
  carries `screening_id` as a `uuid.UUID` in Python on both backends, so a
  record built straight from a row would be refused. That is the intended
  answer: the writer decides how an id appears in a hashed record rather than
  this module picking the hyphenated form on its behalf.
- **A `float` is refused because `score` is one.** `repr()` gives the
  shortest string that round-trips, which is a property of *this* runtime
  rather than of the record — and a hash that changes under a Python upgrade
  is not tamper-evidence. `Decimal` falls with it: its exactness would need
  an exponent rule of its own. Whoever hashes a score decides its spelling
  (a string or a scaled integer) once, and 9.3 and 9.17 then agree by
  construction.
- **`bool` is a JSON boolean, not the `int` behind it.** `isinstance(True,
  int)` is true, so a `bool` reaching an `int` branch would spell `1` and a
  field changed from `1` to `true` would hash the same — a silent collision in
  the one claim Part 9 makes. The check is written before the `int` one and a
  test asserts the two spellings differ.
- **An aware datetime is converted, a naive one is not.** `D46`'s offset
  argument applies here: `14:30+05:30` and `09:00+00:00` are one instant, so
  one instant must not hash two ways. Converting loses nothing — it changes
  the spelling, not the moment. A **naive** value is a different thing: it is
  a wall-clock reading claiming no offset, and reading it as UTC would be a
  guess. It is spelled as it stands because SQLite hands a
  `DateTime(timezone=True)` column back without a `tzinfo` (measured in 8.4)
  and **9.17 recomputes a hash from exactly such a read** — refusing here
  would break verification against this project's own default backend.
  The UTC convention is enforced where a record is *written*, per `D46`.
- **Non-ASCII is escaped rather than encoded.** `ensure_ascii=True` makes
  the output pure ASCII, so the bytes 9.3 feeds to SHA-256 cannot depend on
  an encoder's error handling, and a lone surrogate cannot raise on the way
  into the hash. 9.2 pins the spelling.
- **A refusal names the path and the type, never the value.** A record's
  values are where document-derived text arrives, and `AGENTS.md` bars that
  text from logs. The message carries `$.payload.mrz_line[1]` and the type,
  which is what makes it actionable; a test asserts an MRZ line is absent
  from the message that refused it.
- **Sorting is for keys only.** An array's order is part of its value, so
  `flags` hashes in the order the cascade emitted it.

**What this forbids**

- No `default=` handler, no `float` coercion and no `str()` fallback in
  `canonical_json`: an unsupported type raises or the hash is a lie.
- No `allow_nan` escape hatch, no `Decimal` branch and no `uuid` branch.
- No second serialiser over the same records: 9.3's `hash_record` and 9.17's
  recomputation both go through this function.
- No "strip the nulls" convenience, which would make `{"a": null}` and `{}`
  hash alike.

**Measured, not asserted** — 14 new tests in `test_canonical_json.py`. Three
mistakes were planted and each was caught: `sort_keys=False` (2 failures), a
float spelled as a string (1), and `bool` folded into `int` before the
serialiser (1). All reverted. `check-all.ps1` exits 0 — 3563 backend, 45
frontend, build.

**The gaps this leaves, on purpose:** unicode and nested objects are 9.2's,
and a writer that must carry a `score`, a `Decimal` or a `uuid.UUID` in a
hashed record has to decide that spelling itself — 9.3 and 10.2 are where
that decision arrives.

---

## D49 — A record's digest is SHA-256 over `salt || canonical_json`, hex

**Date:** October 1, 2026. **Status:** settled, task 9.3.

**Context.** 9.3 asks for `hash_record(obj, salt)` = SHA-256 over
`salt || canonical_json(obj)`, with one test that a changed field changes the
hash and one that the same record always hashes identically. It leaves four
things open: what `hash_record` answers (bytes or hex), where the salt sits and
what happens at the boundary, how a `score` — a `float` on `screenings` that
`D48` refuses — gets into a hashed record, and whether an unsalted digest is
reachable.

**Decision.** `app/ledger/hashing.py` holds `hash_record(obj, salt) -> str`
and nothing else. It streams `salt` and then `canonical_json(obj).encode(
"ascii")` into one `hashlib.sha256` and answers `hexdigest()`. **Hex, lower
case, 64 characters**, because that is the spelling `audit_events.record_hash`
already stores and nothing converts it on the way to or from the column. It
calls `canonical_json` and adds no spelling of its own (`D48` forbids a second
serialiser), so a record `canonical_json` refuses raises `CanonicalJsonError`
and **no digest is returned** rather than a hash of a fallback spelling.
`salt` must be `bytes` or a `bytearray`; anything else raises `TypeError`
whose message names the type and **never the value**, matching `_refuse` and
`AGENTS.md`'s rule that nothing record-derived reaches a log. A `bytearray` is
accepted because it is hashed as the bytes it already is — accepting it is
not a second spelling of the salt.

**What this forbids**

- No default salt, no `b""` fallback and no global salt: an unsalted digest is
  only reachable by passing an empty salt deliberately, and 9.4 is what
  generates and stores the real ones.
- No length prefix, separator or domain-separation byte here. The `0x00`/`0x01`
  prefixes are 9.5's, and they belong to the Merkle leaf and node hashes, not
  to a record hash.
- No `str` salt, no `hexdigest()` of the salt folded into the result, and no
  HMAC: the task specifies a salted digest, and a second construction beside it
  is a second thing 9.17 would have to know which was used.
- No trimming, truncating or case-folding of the digest.

**Measured, not asserted** — 18 new tests in `test_hashing.py`. The task's two
claims are there — one changed field changes the digest (six ways, parametrised:
two top-level, two inside the payload, one field added, one dropped) and the
same record always hashes alike (three builds of one record, one of them with
every key inserted in reverse). Plus a **known-answer digest computed
independently of the module**, so a refactor that changes what is hashed fails
instead of agreeing with itself forever; a test that the digest is neither the
unsalted nor the salt-appended one, pinning `||` in that order with no
separator; and the two refusals. **Four mistakes were planted and each was
caught**: the salt appended after the text (3 failures), the salt dropped
entirely (3), `.upper()` on the hex (3), and the salt type check disabled (4).
All reverted, and `hashing.py` is byte-identical afterwards.

**The gaps this leaves, on purpose:** 9.4 generates and stores the salt and so
decides the column and the encoding it travels in; 9.5's domain separation and
9.17's recomputation are where a digest is compared to something else. The
`float` `score` still has no spelling here — `D48` refuses it and this function
  refuses it too, deliberately, so 10.2 spells the score as text or a scaled
  integer before it hashes rather than after.

## D50 — A salt is per record, 16 bytes from the OS CSPRNG, stored beside the record

**Date:** October 1, 2026. **Status:** settled, task 9.4.

**Context.** 9.4 asks for a per-record random salt "stored alongside the
record", with a test that two identical records get different salts and
different hashes. `D49` left two things to this task explicitly: where the
bytes come from, and "the column and the encoding it travels in". Nothing
writes an `audit_events` row yet — 10.2 is the first writer — so there is no
row here to put a salt in, and 8.5 pins `audit_events` at exactly the eight
columns its task names, which a ninth column and a migration would break.

**Decision.** `app/ledger/salts.py` holds `generate_salt() -> bytes`,
`seal_record(record) -> SaltedRecord` and the frozen `SaltedRecord` dataclass
(`record`, `salt`, `.digest`, `.salt_hex`). `generate_salt` answers
`secrets.token_bytes(SALT_BYTES)` with `SALT_BYTES = 16` — the OS CSPRNG,
never `random`, never a seed, a clock or a counter. The width is a constant
and not a parameter, because a width a caller can ask for is a width a caller
can ask for too small. **`seal_record` is the entry point**: it pairs a record
with a salt generated at that moment, so nothing can be sealed with a salt it
found lying around. A `bytearray` salt is copied to `bytes` on the way in, so
a buffer the caller still holds cannot change a digest that was already taken.
The salt travels as **32 lowercase hex** (`salt_hex`), the same spelling
`audit_events.record_hash` already uses, and `bytes.fromhex` reads it back to
the same digest.

**What this forbids**

- **No global salt, no default and no module-level bytes at all.** An unsalted
  digest is only reachable by passing an empty salt on purpose (`D49`). The
  test suite checks this mechanically rather than by reading the source: it
  walks the module's namespace and fails if any attribute is `bytes`.
- No reuse of one salt across two records, and no resealing a record with its
  own salt: the first would let two equal records hash alike, which is the one
  thing a salt exists to prevent.

**The gap this leaves, deliberately.** **The salt is not on a database row.**
It is carried by `SaltedRecord` and offered as hex, but no column stores it,
because the writer does not exist yet and adding one would break 8.5's pinned
column count and 8.8's round-tripped migration. **9.17 cannot recompute a
stored `record_hash` until whoever writes the row (10.2) persists the salt
beside it** — a `record_salt` text column plus a migration is that task's
price, and this entry is the decision it inherits.

## D51 — The tree's two hashes live in their own module, answer raw bytes, and refuse a child that is not a digest

**Date:** October 1, 2026. **Status:** settled, task 9.5.

**Context.** 9.5 asks for "RFC 6962-style domain-separated leaf and node
hashing (`0x00` prefix for leaves, `0x01` for internal nodes), with
known-answer tests". `D49` deferred exactly this: it refused to put a
domain-separation byte in a record hash and said the prefixes "belong to the
Merkle leaf and node hashes, not to a record hash". Three later tasks sit on
top of these two functions — 9.6 builds the tree, 9.7 handles the odd-count
promotion, and 9.10 verifies a proof for every leaf index — so the width of
what comes back is a decision here rather than an accident later.

**Decision.** A new module, `app/ledger/merkle.py`, holds `LEAF_PREFIX =
b"\x00"`, `NODE_PREFIX = b"\x01"`, `DIGEST_BYTES = 32`, `MerkleError
(ValueError)`, `leaf_hash(data) -> bytes` = SHA-256 over `0x00 || data`, and
`node_hash(left, right) -> bytes` = SHA-256 over `0x01 || left || right`.
Three choices inside that:

- **Its own module, not `hashing.py`.** `D49`'s `hash_record` answers 64
  lowercase hex because that is the `audit_events.record_hash` column's
  spelling, and 9.17 recomputes into it. A tree node is never stored in a
  column; it is composed in memory and fed to the next hash. So these
  functions answer **32 raw bytes** and the conversion to a stored spelling
  belongs to whoever stores a root. The apparent inconsistency with `D49` is
  the point: two domains, two return conventions, one reason each.
- **A leaf takes any length; a node's children must be exactly 32.** The
  leaf is the only place arbitrary-length data enters the tree — which is
  precisely why it is the hash that carries the prefix — so refusing a short
  leaf would forbid RFC 6962's own definition. A child is different: it is
  only ever the output of one of these two functions, so a child of any other
  width is a truncated or unhashed value. It is **refused, not padded**,
  because a padded child would produce a root that looks sound and verifies
  nothing.
- **`bytearray` is accepted** and hashed as the bytes it is, on `D49`'s
  reasoning: a caller still holding a mutable buffer is no reason to refuse a
  hash, and the digest is taken from a copy at once.

**What this forbids**

- **No hex on the way out**, and no `hexdigest()` folded back in. A node
  answer is a child of the next node; hex there is a type error waiting to
  happen.
- No unprefixed variant and no "optional prefix": `leaf_hash` and
  `node_hash` are the only two hashes above a record digest, so a caller
  cannot reach a second spelling of either.
- No padding, truncating or hashing-onward of a mis-sized child, and no
  accepting a `str` — which is what stops `record_hash`'s own hex spelling
  being hashed as text and quietly producing a tree nobody can walk.
- **No leaf over a record's payload.** A leaf commits to 9.3's digest, never
  to the record: the ledger holds hashes, and a root that commits to payloads
  would put identity data in the thing 9.13 signs.
- No ordering flexibility: `left` and `right` are the tree's, so a proof that
  swaps two siblings does not verify.

**Measured, not asserted** — 25 new tests in `test_merkle.py`. Every
known-answer vector is **computed from `hashlib` in the test and pinned as a
literal**, so a refactor that changes what is hashed fails instead of
agreeing with itself forever; the node vector is taken over two real leaves,
so it also pins that leaves compose. The separation itself is pinned in both
directions (`leaf_hash(0x01 || l || r)` and `leaf_hash(0x00 || l || r)` are
both unequal to `node_hash(l, r)`), and a leaf is shown to be built from
9.3's pinned record digest and not from the record text. **Seven mistakes
were planted and each was caught**: the leaf sharing the node's `0x01` domain,
each prefix dropped in turn, the two children concatenated in the wrong
order, the 32-byte child check removed, the raw bytes replaced by the hex
spelling, and the non-bytes refusal disabled. All reverted, and `merkle.py`
is byte-identical afterwards.

**The gaps this leaves, on purpose:** 9.6 decides what `build_tree` takes
(digests, or records it hashes itself) and how the levels are laid out; 9.7
decides the lone-node promotion, which is a tree-building question and
touches neither prefix; and nothing yet stores a root anywhere, so the
bytes-to-a-column conversion this entry defers has no caller until 9.16.

---

## D52 — `build_tree` takes record digests and applies `leaf_hash` itself, so the prefix cannot be skipped

**Date:** October 1, 2026. **Status:** settled, task 9.6.

**Context.** 9.6 asks for "`build_tree(leaves) -> MerkleTree` splitting at
the largest power of two", and `D51` left the input open: "9.6 decides what
`build_tree` takes (digests, or records it hashes itself)". The two readings
produce trees over different things, and the difference decides where
`leaf_hash` is called -- which is the one place a caller can otherwise skip
the `0x00` prefix and get a tree that composes but cannot be walked.

**Decision.** `build_tree(leaves)` takes **9.3's record digests**, as 32
raw bytes, and hashes each with `leaf_hash` **inside the builder**. It does
not take records, and it does not take already-hashed leaves.

- **Digests, not records.** `D51` forbids a leaf over a record's payload;
  taking the digest makes that unreachable rather than merely documented.
  A caller cannot put identity data in the root, because the only thing it
  can hand in is something 32 bytes wide.
- **The builder hashes, not the caller.** This is the decision the entry
  was waiting on. If `build_tree` took *leaf hashes*, the prefix would sit
  in every caller's hands -- 9.16's `anchor_batch`, a test, anything -- and
  one that forgot it would build a tree that verifies against nothing. One
  call site now, and the tree is unfalsifiable about its own leaves.
- **A leaf is refused unless it is exactly `DIGEST_BYTES`**, on 9.5's
  reasoning: the only thing ever handed in is `hash_record`'s answer, so
  any other width is a truncated or unhashed value. A `str` is refused by
  the type check, which is what stops `record_hash`'s hex spelling being
  hashed as text. An empty `leaves` raises `MerkleError` rather than
  answering a root over nothing.
- **The split is the largest power of two strictly below the leaf count**
  (RFC 6962 section 2.1), so 3 splits `2 | 1`, 5 splits `4 | 1` and 6
  splits `4 | 2`. The strictness is the whole rule: a plain halving agrees
  with it at 2 and 4 leaves and disagrees everywhere else, and a halving is
  the mistake a reader is most likely to make.

**What this forbids**

- **No second entry point** that takes pre-hashed leaves. One way in means
  one spelling of the tree, and no caller can build one `build_tree` cannot
  rebuild.
- No accepting records, `str`, or a hex digest -- the three things that
  would put a payload or a text spelling in the tree.
- No padding or truncating a leaf, on 9.5's reasoning.
- No storing the root: a tree is in memory, and 9.16 owns the column.

**Measured, not asserted** -- 14 new tests in `test_merkle.py` (39 in the
file). The root for 3 known record digests is pinned as a literal and
computed independently from `hashlib`, and so are the roots for 2, 4, 5, 6
and 7 leaves. Pinning the rule *only* against an independent reference was
not enough, because the first draft of that test recomputed the same split
expression and would have agreed with a wrong rule; the literals are now
the only statement of what the split is, and a separate test asserts the
root differs from a plain halving at 3, 5, 6 and 7 leaves so "halve the
list" cannot pass them. **Six mistakes were planted and each was caught**:
splitting by halving, an off-by-one split, skipping the leaf prefix, hashing
a lone leaf again, dropping the leaf width check, and answering an empty
tree. All reverted; `merkle.py` is byte-identical afterwards.

---

## D53 — an odd split promotes its lone node unchanged, and as the *right* child

**Date:** October 1, 2026. **Status:** settled, task 9.7.

**Context.** `D51` and `D52` both deferred this: the split rule leaves a
right subtree of one leaf at 3, 5 and 7 leaves, and something had to be said
about what the parent node does with that leaf. `_root_of` already promoted
it unchanged, but nothing pinned the claim, and "unchanged" has three
plausible wrong answers -- hash it again, pad it against itself, put it on
the other side -- and each builds a tree that verifies against nothing.

**Decision.** A lone subtree's root is handed to its parent **byte for byte,
as the right child**, and is never hashed on the way up.

- **No second hash under `0x01`.** RFC 6962 hashes pairs only; there is no
  node with one child, and manufacturing one (`node_hash(lone, lone)`) is
  the mistake this rule forbids. A lone node takes no `0x00` pass either --
  it is already a leaf hash, so `leaf_hash` over it would be the leaf domain
  run twice over one digest.
- **The unpaired node is the last leaf, on the right.** The split is
  `largest power of two | remainder`, so an odd count always leaves the *last*
  leaf alone and always on the right of its parent; at `n = 2` both children
  are lone leaves, which is the same promotion and not an exception. Putting
  the unpaired node on the left instead is a different tree, not another
  spelling of this one.
- **The promotion costs nothing.** A tree over `n` leaves runs exactly
  `n - 1` node hashes whatever `n` is, because every internal node has two
  children. That is the shape of the claim a root literal cannot reach: the
  lone leaf is a child of exactly one `node_hash` call -- the root's -- and
  the tree still spends `n - 1` hashes.

**What this forbids**

- No padding, self-pairing, or re-hashing of an unpaired node.
- No promotion onto the left side.
- No top-level exception either: a single leaf becoming the root is the same
  rule at `n = 1`, which 9.8 pins on its own.

**Measured, not asserted** -- 6 new tests in `test_merkle.py` (45 in the
file). The roots for 3 and 5 leaves are spelled out longhand -- each as
`node_hash` over the joined left half and the untouched leaf -- rather than
through the file's own split helper, so the answer cannot borrow the
builder's rule, and pinned as the literals 9.6 already pinned.
**Three mistakes were planted and each was caught**: re-hashing the lone
leaf as a leaf, padding it against itself, and promoting it as the left
child. All reverted; `merkle.py` is byte-identical afterwards.

**What this leaves:** 9.9's `proof_for(index)` carries one step for a
promoted leaf rather than two, and `verify_proof` stops on the root. Nothing
in Part 9 says yet how a proof spells that shorter path.

---

## D54 — one leaf is its own root, and a tree over no leaves does not exist

**Date:** October 1, 2026. **Status:** settled, task 9.8.

**Context.** `D52` refused an empty `leaves` and `D53` settled what happens
to a lone subtree, but `D53` said "which 9.8 pins on its own" and left both
degenerate ends unpinned: the one-leaf tree and the empty batch. Each had
code in `_root_of` and no test. A third hole sat beside them: `MerkleTree` is
public and frozen, so `MerkleTree((), b"")` was constructible by hand, and a
root over nothing could reach 9.9's proof walk from outside the builder.

**Decision.** `n = 1` is `D53`'s promotion applied one level up, and `n = 0`
is refused by the *type*, not only by the function.

- **One leaf is the root, unchanged and unhashed.** No second `0x00` pass,
  no `node_hash(leaf, leaf)`, and no passing the record digest through with
  no leaf hash at all. The tree over one record digest roots at the same
  `leaf_hash` 9.5 already pinned for that digest, which is what makes
  `n = 1` a case of the split rule rather than a rule of its own.
- **The promotion costs zero hashes.** A tree over `n` leaves runs `n - 1`
  `node_hash` calls, so at `n = 1` it runs none. Counted in a test by
  patching both hashes, because a root literal cannot make this claim.
- **No empty iterable answers a root** — `[]`, `()`, an exhausted iterator,
  `""`, `b""`, a frozenset: all of them, all with the same `MerkleError`.
  Batching a quiet window fails loudly instead of anchoring a root that
  commits to nothing.
- **The tree refuses its own degenerate shape.** `MerkleTree.__post_init__`
  raises `MerkleError` on no leaves, sharing one message constant with
  `_root_of`, so "no tree" has one spelling whichever route reaches it. A
  hand-built tree *over* leaves stays allowed and still equals the
  builder's; what is refused is the empty shape, not hand-building.

**What this forbids**

- No `MerkleTree` with an empty `leaves`, from any caller.
- No second refusal message for the same fault.
- No root formula of its own for `n = 1`.

**Measured, not asserted** -- 16 new tests in `test_merkle.py` (61 in the
file). Two mistakes were planted and each was caught: dropping the
`__post_init__` guard, which failed only the hand-built-empty test, and
padding a lone subtree against itself, which failed 22. Both reverted;
`merkle.py` is otherwise byte-identical to 9.7.

**What this leaves:** `MerkleTree` still does not check its root's width on
the hand-built path — `MerkleTree(leaves=(leaf,), root=b"short")` is accepted
— and nothing says what a proof over one leaf looks like. Both belong to
9.9, the first task to walk a root it did not build itself.

---

## D55 -- a proof is its leaf's siblings in walk order, and a verifier that raises is not a verifier

**Date:** October 1, 2026. **Status:** settled, task 9.9.

**Context.** `D53` and `D54` each deferred a question to this task. The
first: a proof over an odd count is a *shorter* path, and nothing said how
that shorter path is spelled -- a one-element proof, a `None` terminator
or a flag. The second: `MerkleTree` is public and frozen, so
`MerkleTree(leaves=(leaf,), root=b"short")` was buildable by hand and a
root that is not a digest could reach a walk. Neither is a detail: 9.17 is
the first caller to read a proof back out of storage rather than build one
in memory.

**Decision.** A proof is a tuple of frozen `ProofStep(sibling,
sibling_on_left)`, leaf-first, and `verify_proof` answers `False` for
anything it cannot use.

- **One step per internal node above the leaf, leaf-first.** A step names
  the sibling *and the side it was a child on*, so a verifier never
  re-derives the tree's shape from the index. Leaf-first is the order the
  walk runs in, so neither side of the pair owns a reversal.
- **A promoted leaf carries one step fewer, and there is no filler.**
  `D53`'s promoted leaf is a child of the root and of nothing else, so at
  three leaves its path is one step where its neighbours carry two. The
  proof is exactly that short -- not a null sibling, not a `None`
  terminator, not a full-length proof with a skip. `D54`'s lone leaf is the
  same rule at the other end: the empty proof, and a walk that never moves.
- **A sibling is the digest the tree already has, never re-hashed.** The
  walk re-applies `0x01` once per level and nothing else, so a step
  carrying `leaf_hash(sibling)` or a self-padded `node_hash` would put a
  leaf's own digest through a second domain and land on nothing.
- **A verifier answers `False`; it does not raise.** A leaf, a sibling or
  a root that is not a digest answers `False`, and so does a step that is
  not a `ProofStep`. This is the load-bearing part: 9.17 has to answer
  `altered` for a tampered row, and a `MerkleError` out of a proof read
  from a column would make that a `try`/`except` at every call site. The
  root check is not redundant for the same reason -- without it a `str`
  root reaches the final `bytes(root)` and raises there.
- **A root is a digest on the type as well as on the walk.**
  `MerkleTree.__post_init__` refuses a root that is not `DIGEST_BYTES`,
  closing the hand-built path `D54` left open. A hand-built tree *over*
  leaves is still allowed and still `==` the builder's.
- **An index is a position, not a Python index.** `proof_for(-1)` is
  refused rather than wrapped, and a `bool` is refused too, because
  `True` is an `int` and would otherwise hand back leaf 1's proof. A
  `float` that compares equal to a real index is refused for the same
  reason.

**What this forbids**

- No filler step, no `None` terminator and no skip flag for a promoted
  leaf's shorter path.
- No raised error out of `verify_proof` for a malformed leaf, sibling,
  step or root.
- A `MerkleTree` whose root is not a digest, from any caller.
- A negative, boolean or non-`int` index that resolves to a leaf.

**Measured, not asserted** -- 45 new tests in `test_merkle.py` (106 in the
file). The round trip is pinned against 9.6's and 9.7's root literals, and
the path is spelled longhand on the three-leaf tree rather than read back
through the builder. A proof of `k` steps over `n` leaves runs exactly
`n - 1 - k` node hashes -- every internal node but the `k` on the leaf's
own path -- counted with both hashes patched, over every index at six
sizes; that table is a claim a "it round-trips" test cannot make. **Eight
mistakes were planted and each was caught**: a root-first path (8
failures), a swapped side flag (7), no root-width check on a hand-built
tree (2), a step walked without being a step (4), a negative index that
wrapped (2), an accepted `bool` (1), a walk that compared against a root of
any width (2), and a leaf hashed again on the way out (6). Two survived the
first planting -- the non-bytes root and the non-`ProofStep` step -- and
both are now pinned.

**What this leaves:** a proof exists in memory and nothing stores one, so
9.16's `anchor_batch` has to put it somewhere and the spelling that travels
(hex digests, a side per step) is that task's business. `MerkleTree` still
does not check the *widths of its leaves*, so a hand-built tree over short
leaves is still accepted; `proof_for` refuses it once `_root_of` reaches a
node, and nothing walks the tree before then. And the walk re-derives every
sibling subtree from the leaf hashes rather than reading one off a stored
tree, so a proof costs `n - 1 - k` hashes -- nothing at a batch of 25
(9.15), and 9.11's `read_batch` is where a caller wanting the whole tree at
once would notice.

---

## D56 -- a proof's guarantee is a claim about every index, pinned at sixteen leaves

**Date:** October 1, 2026. **Status:** settled, task 9.10.

**Context.** `D55` settled what a proof *is* and walked one leaf back to
the root, but every negative claim it made ran on a three- or five-leaf
tree. Those are the sizes where `D53`'s promotion is visible, so they are
the right size for a structural claim and the wrong size for a claim about
the whole surface: a tree three leaves deep is two levels, and one level
can be walked correctly while another is not.

**Decision.** The sweep is the claim, and it is pinned at 16 leaves with
both halves in one place -- every index's own leaf walks its own proof to
the root, and one bit flipped in any leaf verifies against none of the
sixteen proofs.

- **Sixteen, not three or five.** The smallest count at which the tree is
  four levels deep *and* balanced, so no height is special and a path that
  is right at one level cannot hide a sibling or a side flag that is wrong
  at another. Every index is walked, and the sixteen answers are listed as
  sixteen `True` values rather than folded into `all(...)` -- a sweep over
  an empty range cannot pass.
- **A mutation is refused against *every* proof, not only its own.** All
  256 pairs, because a proof claims to commit to exactly one leaf. The
  untouched walk runs first in the same test, so the refusals cannot be an
  artefact of a root nothing could have reached.
- **The mutation is planted at the record too.** One digest is changed
  before `build_tree`, and the leaf that comes out is run against the proof
  and root cut before the change -- the shape 9.17's `altered` will meet,
  where the tampered value is a stored digest rather than a leaf.

**What this forbids**

- A spot-checked path standing in for "every leaf".
- A mutation test that tries the altered leaf only against its own proof,
  which would pass for a proof that accepted any leaf it was walked with.
- Reading the 16-leaf row of the known-answer table as a substitute for
  the split-rule test. At a power of two the split rule and a plain
  halving agree, which is why `test_the_split_is_not_a_plain_halving`
  stays on 3, 5, 6 and 7 and this task added no split assertion.

**Measured, not asserted** -- 3 new tests (114 in `test_merkle.py`, was
110) and one new known-answer row, 16 leaves at `cc6e692a...`, taken from
three derivations that use no code from `merkle.py`: level-by-level
pairing, the split rule written out in the test file, and the builder.
**Two mistakes were planted and both were caught**: a `verify_proof`
answering `True` unconditionally (the mutation sweep and the record test
fail) and a `proof_for` dropping a step (the sixteen-index sweep fails).

**What this leaves:** nothing new. The task is test-only -- `merkle.py` is
unchanged from `D55` -- so no guarantee was narrowed. `D55`'s open items
stand: nothing stores a proof or a root yet, and 9.11's `read_batch` is
still where a caller wanting the whole tree at once would want a walk
answering siblings *and* roots.

---

## D57 -- the ledger is three methods, one session source, and one spelling it does not own

**Date:** October 1, 2026. **Status:** settled, task 9.11.

**Context.** 9.6 to 9.10 built the hashes and the tree in memory; nothing
had ever put a root anywhere. `ledger_entries` already exists as a 8.6 row
with its position as the primary key, and the abstract describes a log that
several agencies write to, so 9.11 had to choose an interface rather than a
function -- and could have chosen three different shapes for it.

**Decision.** `app/ledger/store.py` holds an abstract `Ledger` and the one
`SqliteLedger`, and the choices worth recording are these four.

- **The interface is three methods and nothing else.** `append_batch`,
  `read_batch` and `iter_batches`, all three abstract, so a caller holds a
  `Ledger` and the implementation is the thing a test swaps. No `sign`, no
  `verify`, no `flush`: 9.13 owns signing and 9.17 owns verification, and a
  fourth method here would be one of those tasks' behaviour written twice.
- **The ledger is handed its sessions**, on `D42`'s reasoning -- a required
  `sessionmaker[Session]`, never the module-level `SessionLocal`, so a test
  can point it at a migrated file and a caller cannot reach the process's
  start-up configuration by accident.
- **A batch is appended once.** A second `append_batch` of a `batch_id` the
  log already carries raises `DuplicateBatchError` rather than writing a
  second entry, because two entries for one batch leave `read_batch` with
  two answers to one question and 9.17 has to pick one. This is the
  application's rule, not the schema's: nothing in the migration makes
  `batch_id` unique, so a concurrent writer can still race past the check.
- **A stored spelling is 9.16's decision.** The root and the signature are
  written and answered back **verbatim**, and nothing here validates,
  re-encodes or rejects either by its shape. `merkle.py` holds a root as 32
  raw bytes while the column is text, and pinning a spelling here would
  answer 9.16's question before it was asked -- and refuse its first
  choice if it disagreed.

**What this forbids**

- A `Ledger` that opens its own session or reads a clock.
- A root or signature "helpfully" normalised, lower-cased or length-checked
  on the way in; 9.16 owns the stored spelling.
- An `append_batch` that silently amends or replaces an entry -- the mapper
  events and 9.12's triggers own that refusal.
- A `read_batch` that raises for a batch the log does not carry. Absence is
  an answer, on `ScreeningRepository.get`'s reasoning.

**Measured, not asserted** -- 20 new tests, 3740 in the backend suite (was
3720), and `check-all.ps1` exits 0. Five mutants were planted and each was
caught: `iter_batches` with no `ORDER BY`, `append_batch` without the
duplicate check, `_as_utc` without its naive-stamp refusal, `read_batch`
answering the first row rather than the named one, and an append that
returned before committing.

**What this leaves:** the ordering of `iter_batches` cannot be shown by the
rows on this backend -- `sequence` *is* the rowid, so an unordered `SELECT`
scans in sequence order and keeps passing -- so the test checks the emitted
statement carries `ORDER BY ledger_entries.sequence` rather than trusting
the order the rows arrive in. The duplicate-batch rule is the service's
alone until a unique constraint on `batch_id` exists, which is a migration
and not this task. And nothing stores a *proof* yet: `read_batch` answers
the entry (root, signature, stamp) and 9.17 still has to read the events
back beside it, so `D55`'s note that a caller wanting the whole tree at once
would want a walk answering siblings *and* roots is now a call to 9.17
rather than to this task.

---

## D58 -- append-only is refused by the database, and the guards are installed rather than migrated

**Context.**  8.6's mapper events (`D39`) refuse an amendment and a removal
from the ORM's side, and 9.11's `Ledger` offers no verb that could make one.
9.12 adds the other half: the refusal *in the database*, so a statement the
ORM never built -- raw SQL, a script, a second service -- cannot amend or
remove an entry either.

**Decision.**

- **The guards are installed by `app/ledger/triggers.py`, not by a second
  Alembic revision.**  `D41` forbids a second version file until a model has
  changed, and a trigger is not in `Base.metadata`, so `--autogenerate` would
  never produce one and a hand-written revision would exist only to be an
  exception. The migration owns tables and columns; the ledger layer owns the
  guard on the log it writes.
- **`install_append_only_triggers(engine)` is the only verb, and it takes an
  engine rather than sessions.** A caller asks on whatever database it is
  serving, and the module builds nothing: no URL, no session, no table.
- **Installing is idempotent and never replaces.** `CREATE TRIGGER IF NOT
  EXISTS` makes a second call a no-op, so a start-up path may ask every time;
  a guard already present under the name is kept, so an install cannot
  silently weaken one.
- **Both guards are `BEFORE ... FOR EACH ROW` and `RAISE(ABORT)`.** Not
  `AFTER`, which would let the amendment reach the row first. Not
  `ROLLBACK`, which would discard the transaction a refused statement
  travelled in. Not `RAISE(IGNORE)`, which abandons the statement *silently* --
  a guard that says nothing is not a refusal.
- **The two names and the message are derived from
  `LEDGER_ENTRY_TABLE_NAME`**, and both guards carry one message: an entry is
  neither amended nor removed, which is one claim.
- **Only SQLite, and the installer says so.** `RAISE` is SQLite's own, so a
  non-SQLite engine is refused by name before any statement is sent rather
  than handed a syntax error at run time.
- **The two halves answer in their own words.** The mapper events raise
  `LedgerAppendOnlyError` (`D39`); the triggers raise SQLite's constraint
  failure, which SQLAlchemy answers as `IntegrityError`, carrying
  `APPEND_ONLY_MESSAGE`. Measured: during a refused `session.delete` the
  engine's `before_cursor_execute` records no `UPDATE` and no `DELETE`, so
  the ORM half really does stop before the database and the trigger half
  covers exactly the statements it cannot see.

**What this forbids**

- A second Alembic version file for the triggers, and a trigger added to
  `Base.metadata` to smuggle one in.
- Any function in the package that drops a guard. Nothing in the service may
  un-append an entry; a caller that wants an empty log drops the two triggers
  by name and installs them again, which is what this task's own tests do.
- An `AFTER` trigger, `RAISE(IGNORE)`, or a guard installed without
  `IF NOT EXISTS`.
- A `session.execute(update(LedgerEntry))` or a hand-written `DELETE` treated
  as the append-only guarantee. The mapper events do not see either.

**Measured, not asserted** -- 13 new tests in
`test_ledger_append_only.py`, 3753 in the backend suite (was 3740), and
`check-all.ps1` exits 0. Both refusals are issued as driver-level SQL, because
that is the only place a trigger is visible at all; the migrated-but-never-
installed file is held in the same run to show those statements *succeed*
there, and the surviving entry is checked for position, root and signature so
a half-applied refusal cannot pass. Two mutants were planted and each was
caught: the delete guard removed from the pair (5 tests fail) and `IF NOT
EXISTS` dropped (every test in the file errors on the second install). Both
were reverted.

**The gaps this leaves, on purpose:** nothing calls
`install_append_only_triggers` yet -- `app/main.py` has no database wiring at
all, so there is no start-up seam to call it from, and a migrated database is
unguarded until 9.16 or 11.1 asks. PostgreSQL has no equivalent here: the DDL
is SQLite's, and the installer refuses another dialect rather than pretending.
And one statement walks past the delete trigger: `INSERT OR REPLACE` over an
occupied `sequence` removes the row without firing it unless `PRAGMA
recursive_triggers = ON`, which is measured and pinned by a test rather than
left to be discovered; closing it would be a third `BEFORE INSERT` guard
refusing an insert that names a taken position, which this task does not ask
for. Two smaller facts, both measured: a guard fires per row, so a `DELETE`
against an empty log is allowed and changes nothing, and `Uuid` is `CHAR(32)`
hex on SQLite, so raw SQL must spell a batch id the way the column stores it.

---

## D59 -- the signing key is configured as one PEM, and a generated one is never held

**Context.**  `append_batch` takes a `signature` as text (9.11, `D57`) and
nothing in Part 9 can produce one. 9.13 supplies the key and the one verb that
signs. `.env.example` already named `LEDGER_SIGNING_KEY` and published a PEM
PKCS#8 generation command, so the spelling was decided before the code was;
what was open is what a *missing* key means and what a caller is handed.

**Decision.**

- **`app/config.py` is the only reader of `LEDGER_SIGNING_KEY`, and the ledger
  module is handed the value.**  `get_ledger_signing_key()` answers the string
  as written or `None`, on `D37`'s reasoning, and `LEDGER_SIGNING_KEY_ENV_VAR`
  lives in `config.py` so the variable's name is spelled once -- the ledger
  module imports it to name the variable in its refusals rather than holding a
  second copy of the string. A test parses the module's AST and fails if an
  `os.getenv` appears in it.
- **Unset *and* blank both mean "generate", and a blank value is what
  `.env.example` ships.**  Refusing a blank optional variable would break the
  zero-setup demo over nothing, so a dev key is generated instead.
- **The one accepted spelling is an unencrypted Ed25519 private key as PEM
  PKCS#8.**  Unencrypted because the environment variable *is* the secret
  store and there is nowhere for a passphrase to come from; PEM because that
  is what the committed example already publishes, and a raw 32-byte seed in
  hex is refused rather than quietly accepted as a second spelling.
- **A generated key is generated per call and held nowhere.**  There is no
  module-level key and no cache, on `D50`'s reasoning that a reused secret is
  not one. The consequence is a claim, not a convenience: two callers handed
  `None` in the same process hold two *different* keys, and a signature made
  by one does not verify under the other's public key. 256 draws are checked
  for distinctness, and an AST test fails on any module-level assignment
  whose value references the key class.
- **An unreadable or wrong-curve key is refused, never replaced.**  There is
  no generated fallback for a malformed value: an operator mistake that
  quietly became a signature would anchor batches under a key nobody holds.
  `SigningKeyError` is a `ValueError` (`D37`'s reasoning) and there are two
  messages, because "unreadable" and "readable but not Ed25519" are two
  mistakes with two different fixes.
- **Answers are raw bytes and the text spelling stays 9.16's business.**
  `Signer.public_key` is 32 bytes and `Signer.sign` is 64, the same answer
  `merkle.py` gives (`D51`) and the same separation from `ledger_entries`'
  text columns that `D57` records. A consumer holding only the bytes rebuilds
  the key with `Ed25519PublicKey.from_public_bytes`, which is what the
  round-trip test does rather than reaching back into the `Signer`.
- **`sign` refuses anything that is not bytes, and a `bytearray` is copied.**
  Encoding a `str` here would be a second spelling of the same payload
  (`D48`'s reasoning), so 9.16's root would be signed without anyone knowing
  which of the two it handed over.
- **No refusal quotes its input, and a `Signer`'s `repr` carries no key.**  A
  private key that reaches a message is a private key in a log, so the
  dataclass is built `repr=False` and a traceback cannot print one. Both are
  held by tests rather than by review.

**What this forbids**

- A module-level key, a cached key, or any verb in the package that writes,
  exports or persists one. `generate_signing_key_pem()` answers a value for
  the operator to keep; persisting it is their decision.
- A second env reader, a second spelling of the variable's name, or a
  generated fallback standing in for a configured key that cannot be read.
- A `verify` helper in this module. 9.14 owns "a tampered root fails"; the
  round trip here proves only that what this module signs, the exposed public
  key verifies.

**Measured, not asserted** -- 41 new tests in `test_ledger_signing.py`, 3794
in the backend suite (was 3753), and `check-all.ps1` exits 0 (45 frontend,
build). Two mutants were planted and each was caught: a generated key returned
in place of a refusal (6 tests fail) and a module-level cached dev key (3
tests fail, one of them the AST scan naming the offender). Both were reverted.

**The gaps this leaves, on purpose:** nothing signs yet -- 9.16 is the first
caller, and there is no start-up seam in `app/main.py` to hold a loaded key
(`D58` records the same gap for the triggers). A generated dev key is not
persisted by anything, so **anything anchored under one is unverifiable once
the process restarts**; that is the honest cost of the zero-setup path, and the
reason `.env.example` now says to set the variable before anchoring. And
`cryptography` is still a *dev* dependency only (`requirements-dev.txt`), so
`app.ledger.signing` will not import in a production image built from
`requirements.txt` until 26.1 promotes it -- 0.5 deliberately deferred that
and this task did not touch it.

---

## D60 -- verification is one verb that answers a bool, and needs only the public key

**Context.**  `D59` forbade a `verify` helper in `signing.py` and named 9.14 as
the task that owns "a tampered root fails".  Until now the round trip was proven
by rebuilding a key *inside the test* with
`Ed25519PublicKey.from_public_bytes`, which shows the library works rather than
that this service checks anything.  Part 9 also needs an answer 9.17 can
report: an entry whose signature no longer holds has to come back as
`altered`, not as an exception.

**Decision.**

- **`verify_signature(public_key, signature, data) -> bool` is the one
  verification verb, and it sits beside `sign`.**  Module-level rather than a
  `Signer` method: a verifier holds the 32 published bytes and never the
  private key, so making it a method would force an auditor to reconstruct the
  *signing* key to check an entry.  This replaces `D59`'s "a `verify` helper in
  this module" bullet, which deferred it to this task rather than banning it.
- **It answers `False` and never raises on anything that is the wrong
  _value_.**  On `verify_proof`'s reasoning: a signature that no longer holds is
  the answer, not an error, so no call site needs a `try`.  A public key or a
  signature of the wrong width answers `False` -- and the key-width guard is
  load-bearing, not decoration, because `from_public_bytes` *raises* `ValueError`
  on a short key.  Measured: a mutant that dropped the guard fails three tests.
- **Only a non-bytes argument is refused, by `TypeError`.**  `sign` draws the
  same line, and for the same reason: a wrong type is a caller that read a
  column wrongly, a wrong value is a tamper.  A `bytearray` is copied on the
  way in, so a later mutation cannot change the answer.
- **What a signature covers is a root and nothing else, and the root is what
  makes the tamper visible.**  Editing a *stored* root is not the threat --
  the append-only triggers refuse that (`D58`) -- the threat is editing a
  record and rebuilding the tree, so the root under test is one recomputed from
  the data (`D55`, `D57`).  The test measures that path, and sweeps all 32
  byte positions, rather than flipping a bit in a value held in memory.
- **What this still does not do:** it takes raw bytes, so reading a
  `ledger_entries` row and decoding its hex columns is still **9.16's**
  (`D57`).  Nothing calls the verb yet.

**Measured, not asserted** -- 16 new test cases in `test_ledger_signing.py`, 57
in the file (was 41).  Two mutants were planted and each was caught: an
`InvalidSignature` answered `True` (4 tests fail, the task's own test among
them) and the width guard dropped (3 fail).  Both reverted.

---

## D61 -- a batch is a consecutive slice of the caller's run, and the caller keeps the events

**Date:** October 1, 2026.  **Status:** settled, task 9.15.

**Context.**  `D54` made "no empty batch" a rule with teeth -- `build_tree`
refuses an empty leaf list so a quiet window cannot anchor a root committing
to nothing -- but nothing yet said who decides which events go together, in
what order, or whether the grouping may look inside an event.  9.16's
`anchor_batch` will sweep unanchored events into batches, root each one and
stamp every event, so the grouping is the step where an ordering mistake
would be baked into a root and then signed.

**Decision.**  `group_into_batches(unanchored_events, size)` is one pure
function in `app/ledger/batching.py`, and it partitions without judging.

- **The order is the caller's, and nothing sorts.**  Batches are
  consecutive slices of the run in the order it arrived, because the root
  commits to the order the events were written in, not to an order this
  module could invent.  Measured: a run handed over out of order comes back
  out of order, while 100 events at 25 still give four batches -- the
  count alone cannot tell a sorted grouping from a stable one.
- **A short last batch is a real batch; there is no padding and no refusal.**
  26 events at 25 are two batches holding 25 and 1.  Padding would invent an
  event and a refusal would drop the tail, which is what 9.16's "stamp every
  event" forbids.
- **Events come back by identity, in a tuple of tuples.**  9.16 stamps a row
  it holds; a copy would leave the caller's row unstamped and unanchored.  The
  answer cannot be appended to between the cut and the tree, so what 9.16
  roots is what this answered.
- **`size` is a positive `int`, checked before a single event is read.**  A
  `bool` is an `int` and would quietly cut batches of one -- `proof_for`'s
  rule, drawn again -- and a `float` comparing equal to a real size is not
  one.  Zero and negatives are `ValueError`.  Both checks precede the read, so
  a refusal cannot drain a caller's stream on its way out.
- **Any iterable is accepted and read exactly once**, because 9.16 will hand
  over what a query returns rather than a list.
- **Nothing to cut answers `()`, not one empty batch.**  The refusal
  `D54` bought stays where it was placed -- on the tree -- and a
  zero-event batch is never created to be rooted.
- **No event is inspected**, so the function is generic over its element and
  is not coupled to a column 9.16 will stamp.  "Unanchored" is the caller's
  claim about what it selected, not a check this module repeats.

**What this forbids**

- Sorting, deduplicating, dropping or padding inside the cut.
- A second, different notion of which events are unanchored.
- Reading the caller's events before the size has been accepted.
- A batch whose events are copies of the ones the caller holds.

**Measured, not asserted** -- 23 new tests in `test_ledger_batching.py`,
3833 in the backend suite (was 3810), and `check-all.ps1` exits 0 (45
frontend, build).  Four mutants were planted and each was caught: the run
sorted (4 tests fail, the task's own count test among the survivors), the
slice widened to `size + 1` (6), the `bool` guard dropped (3), and the
positive check dropped (4).  All reverted.

**What this leaves:** nothing yet chooses the run.  There is no reader for
"events with `batch_id IS NULL`" and no policy for how many events a window
holds or when a batch is anchored -- 9.16 owns all of it, as does the
question of what a caller does with `()`, which is this module's answer and
not yet an error anywhere.  Nothing reads these batches; the anchoring,
stamping and signature they exist for is 9.16's.

---

## D62 -- the anchoring commits to what the database holds, an event is anchored once, and the entry is appended before the stamp

**Date:** October 1, 2026.  **Status:** settled, task 9.16.

**Context.**  `D57` left four things open for this task by design: what a
root and a signature are spelled as when they reach `ledger_entries`' text
columns, how a batch's events reach the entry that committed them, when a
run is chosen at all, and what happens to the two steps when the second
fails.  Each is a place where a plausible-looking ordering would leave the
log saying something the rows do not support.

**Decision.**  `app/ledger/anchoring.py` holds `anchor_batch` and
`select_unanchored`, and the three decisions below are what make them one
honest operation rather than four calls in a row.

- **Text columns are lowercase hex, and the signature is over the raw
  root.**  A root is 32 raw bytes and an Ed25519 signature 64; both are
  widened with `.hex()` on the way in, which is the spelling `hash_record`
  writes and the one `verify_signature` is handed back.  Signing the *hex
  spelling* of the root would verify against nothing, so the raw bytes are
  what is signed and the hex is only what is stored.
- **The root commits to what the database holds, not to what a caller is
  carrying.**  The digests are read out of `audit_events` inside the
  anchoring call, in the batch's own order, rather than taken off the
  passed objects.  The objects are exactly what `select_unanchored`
  answered, so this costs one read and buys the guarantee that a drifted
  or hand-built row cannot produce a signed root 9.17 could never
  recompute.  The read is in a session that closes before anything is
  written, so the ledger append is not holding a read open against the
  writer that follows it.
- **An event is anchored once, and the database is what says so.**  The
  stamp is written `WHERE batch_id IS NULL`, so the condition is in the
  statement rather than in a check above it that a second writer could
  race past; a rowcount short of the batch is refused.  The read refuses
  an already-stamped row before the tree is built, so the common case
  costs no entry.
- **The entry is appended before the events are stamped.**  The stamp is a
  pointer into the log, so it must never point at an entry the log does
  not hold.  A failure between the two therefore leaves the events
  *unanchored* -- the reader will pick them up again -- rather than
  stamped toward nothing, which `D54` already reserves the word
  `unknown` for.  The price is paid in the other direction: a crash
  between the two can leave an entry nothing references, and re-anchoring
  those rows would append a *second* entry over the same digests under a
  fresh `batch_id`.

**What this forbids**

- A root built from an in-memory `record_hash` rather than the stored one.
- Signing anything other than the 32 raw root bytes.
- Stamping a row unconditionally, or stamping it before the entry exists.
- Re-anchoring a row that already carries a `batch_id`.
- A second, different notion of which events are unanchored -- the reader
  is `batch_id IS NULL`, and anchoring refuses a row that does not meet it.
- A batch that holds one event twice, which would give 9.17 two leaf
  positions for one row.

**Window policy.**  `DEFAULT_BATCH_SIZE` is 25 -- a default, not a rule,
and the size this task's verify is stated at.  `anchor_batch` anchors
*everything* it is handed, cutting into as many batches as that takes, so
100 events give four entries.  The order is `select_unanchored`'s
(`created_at`, then `id`); a caller that anchors an arbitrary iterable
instead commits to whatever order it passed.

**What this still does not do.**  **The order of a batch is stored
nowhere.**  `audit_events` carries `batch_id` but no position within it,
so 9.17 cannot rebuild the tree from the stamped rows and must be handed
the same order the batch was cut in -- which only
`select_unanchored -> anchor_batch` reproduces.  A `batch_index` column and
a migration are 9.17's or 10.2's, not this task's.

**Measured, not asserted** -- 27 new tests in `test_ledger_anchoring.py`,
3860 in the backend suite (was 3833), and `check-all.ps1` exits 0 (45
frontend, build).  Seven mutants were planted and each was caught: the
`IS NULL` condition dropped (1), the two steps swapped (1), the
already-anchored refusal dropped (1), the digest read off the object
instead of the row (4), the caller's objects left unstamped (2), the hex
spelling signed instead of the raw root (1), and the repeated-id refusal
dropped (1).  All reverted.

---

## D63 -- a tamper sweep flips a bit; it never writes a literal byte

**Date:** October 1, 2026.  **Status:** settled, task 9.16 re-verification.

**Context.**  9.14's sweep over all `DIGEST_BYTES` positions built each
tampered root by *writing* `0xff` at the index rather than flipping a bit
in what was there.  A root is a SHA-256 output over randomly salted record
digests, so it already contains a `0xff` byte in about one run in nine --
and at that position the "tampered" bytes are byte-identical to the
original.  Measured: 3 failures in 30 runs, against a predicted
`1 - (255/256)^32` of 11.9%.  `verify_signature` was right every time;
the sweep was asking it the wrong question.

**Decision.**  A tamper constructs its bytes with `^ 0x01`, on the byte
that is already there, so every position is a real change and the sweep is
deterministic.  This is not a weakening: the assertion
`flipped == [False] * DIGEST_BYTES` is untouched and is now satisfied for
the reason it claims -- a bit that moved anywhere.

**Why it could not be fixed in the code under test.**  The same file's
`test_a_signature_over_a_tampered_root_fails_verification` asserts
`verify_signature(public_key, signature, root) is True`.  On a no-op
tamper the two tests ask the identical call for opposite answers, so no
implementation of the verifier can satisfy both.  A suite that fails one
run in nine on a value it generated itself is a defective test, not a
detected defect.

---

## D64 -- three words, one recomputation, one walk, and two required keywords

**Date:** October 1, 2026. **Status:** settled, task 9.17.

**Context.**  9.17 asks for `verify_event(event)` that reloads the event,
recomputes its hash, walks its proof, compares against the anchored root, and
answers `verified` / `altered` / `unknown`, with a test that mutates a stored
payload as its verify.  Two facts that verb needs are stored nowhere: an
`audit_events` row carries no `record_salt` (`D50`, and 8.5's pinned eight
columns) and carries no position within its batch (`D62`).  So the task had to
choose between being honest about both gaps and answering as if they were
closed.

**Decision.**  A new module, `app/ledger/verification.py`, holds
`verify_event(event, *, sessions, ledger, salt, batch) -> str` and the three
module constants `VERIFIED`, `ALTERED` and `UNKNOWN` (with the closed
`VERIFICATION_STATUSES`).  The choices worth recording:

- **The answer is one word, not an object.**  The task names three states and
  `AuditEvent.batch_id`'s own docstring already reserved `unknown` for an
  event with no root to walk to, so a plain string is the whole contract; the
  constants and the closed tuple are what make it closed.
- **Two halves, and neither subsumes the other.**  A payload moved with its
  hash left stale is caught by the recomputation
  (`hash_record(payload, salt)` against `record_hash`); a payload *and* its
  hash rewritten together passes that and is caught by the walk, because the
  anchored root committed to the digest the row used to carry.  Both halves
  are tested, the second with the attacker's own salt handed over so the
  recomputation genuinely succeeds.
- **The record recomputed is the row's `payload`.**  It is the one column 10.3
  attaches and the one the task's verify mutates, and it is the only hashed
  record on the table.  10.2 is free to widen the record; whatever it hashes,
  it must hash *here* too, because two record shapes would make `verified` a
  claim about the wrong value.
- **`salt` and `batch` are required, keyword-only, and the caller supplies
  both.**  `salt` is what `D50` seals a record with and what 10.2 persists;
  `batch` is the order 9.16 cut, which no column stores.  Both gaps could have
  been defaulted to "no salt" and "the reader's order", and both defaults
  would have answered `unknown` for every event in the system -- or, worse,
  silently verified against a tree cut in an order nobody anchored.  A
  required keyword is the loud version: the two facts are the caller's to
  supply until `record_salt` and `batch_index` columns exist.
- **The proof is cut from the rows, so a rewritten digest moves the whole
  batch.**  A payload-only tamper answers `altered` for that event alone;
  changing any stored digest changes every proof in the batch, because the
  siblings are re-derived from the rows rather than read off a stored proof.
  That is the stronger of the two answers and it is what the batch really
  committed to.
- **`unknown` is the absence of a half, and never a clearance.**  No row, no
  stamp, no entry for the stamp, a root that is not a digest, no leaf position
  for this event, a payload `D48` refuses to spell (a `float` score), and a
  batch that cannot be rebuilt (a row gone, or a sibling's hash that is not a
  digest).  An unreadable *sibling* answers `unknown` rather than `altered`
  on purpose: the claim is about one event, and the broken leaf is not known
  to be this one.  `unknown` is never a clearance, only the absence of an
  answer.
- **Every compared value is read out of the rows**, never off the object the
  caller holds, on `D62`'s reasoning: a payload changed on a detached event
  verifies, and a row changed behind a pristine object does not.
- **A refusal is a caller at fault, not a state.**  `TypeError` for a value
  that is not an `AuditEvent` and for a salt that is not bytes (so `D49`'s
  refusal is not swallowed), and a new `VerifyError(ValueError)` for an event
  handed over with no id or a batch holding one event twice -- a batch that
  could not be one is not a record whose answer is unknown.
- **`read_digest` moved to `merkle.py`,** so 9.16 and 9.17 widen a column
  through one reader (`MerkleError` for prose or another width).  It is a
  change to a file two settled entries describe, and it is a narrowing
  rather than a loosening: `anchoring._digest_of` now delegates and keeps its
  own `AnchorError` messages.

**What this forbids**

- A `verify_event` that reads `record_hash`, the payload or `batch_id` off the
  passed object rather than off the row.
- A defaulted salt or a defaulted batch order.
- A `verified` answer reachable without the recomputation and the walk both
  having run.
- A second serialiser or a second hash in this module; the digest is
  `hashing.hash_record`'s and every leaf, node, proof and walk is `merkle`'s.
  A source-side test walks the AST and fails if either appears.
- An `altered` answer for a row whose own two columns are intact because a
  *sibling* could not be read; that is `unknown`.

**Measured, not asserted** -- 30 new tests in `test_ledger_verification.py`
and 13 in `test_merkle.py` (127 in the file, was 114).  **Eleven mutants
were planted and each is caught**: the recomputation dropped (2), the walk
ignoring the root (6), the leaf taken at position zero (5), the position
taken as zero (1), the unanchored check dropped (1), the absent entry treated
as found (1), the missing-row check dropped (1), an unreadable sibling
treated as a leaf (1), the repeated-id refusal dropped (1), the salt dropped
(14), and the leaf fed to the walk unhashed (8).

**The one that survived the first planting** was the unanchored check, and it
survived for a real reason: `Ledger.read_batch(None)` happens to answer
`None`, so the check and its absence agreed on every row.  Rather than delete
a check that names a real state, a recording `Ledger` now pins that the log
is never asked for a batch no row named.

**What this leaves.**  **Nothing checks the entry's signature.**  9.17 compares
the anchored root as read; `verify_signature` (9.14) exists and no caller
holds a public key outside the `Signer` that made the signature, so a
verification cannot tell a tampered root from an unsigned one.  **Nothing
calls `verify_event` yet** -- 11.1's audit view and 24.9 are where it is
reached.  **A `float` in a payload answers `unknown`,** because `D48` refuses
to spell one; 10.2 must store a score as text or a scaled integer, in this
module's record and in the writer's, together.  **A caller that lost the salt
cannot verify the row**, which is 10.2's `record_salt` column and the reason
it is not optional here.  And the order still lives with whoever anchored the
batch, which is `batch_index`.

## D65 -- the event vocabulary is six plain strings, closed as a tuple, in one constants module

**Date:** October 1, 2026. **Status:** settled, task 10.1.

**Context.**  8.5 built `AuditEvent` with `event_type` as a plain text column
and no vocabulary type beside it, on the reasoning that a table holding the
words is the thing 7.10's band walk exists to catch, and that the writer
(10.2) is what should refuse a name outside the vocabulary.  That left this
task the six names and a choice of shape.

**Decision.**  `app/audit/event_types.py` holds six module-level `str`
constants and the closed tuple `EVENT_TYPES` that gathers them;
`app/audit/__init__.py` is a docstring and nothing else.  The choices worth
recording:

- **Plain `str`, not an `Enum`.**  The column is text with no vocabulary
  type, so an enum member would make what lands in the row depend on how the
  driver binds a member rather than on the constant the code states.  The
  spelling is the thing a trail is read by.
- **A tuple, not a set or a `frozenset`.**  The task's own verify is "a test
  asserting no duplicates", and a set cannot hold one -- the check would be a
  tautology that passes by construction.  A tuple keeps the duplicate
  representable so the test says something.
- **Declaration order is trail order** -- created, analysis completed, tier
  by tier, decision, override, deleted -- so 24.8's audit view reads in that
  order without sorting.
- **One import path.**  The names live in a submodule rather than being
  re-exported from `app/audit/__init__.py`, matching `app/ledger` (1.1):
  importing the package does not silently pull the vocabulary in, and a
  module that emits an event says which module it took the name from.
- **No predicate here.**  Refusing a name outside the vocabulary is `emit`'s
  job (10.2).  An `is_event_type()` in this module would be a second place
  the vocabulary is enforced and a second place a seventh name is added.
- **One home in `app/`.**  A literal spelled anywhere else is a second
  vocabulary that can drift from this one; `AuditEvent`'s own docstring
  leans on that, being "not where a seventh name would be caught" precisely
  because this module is the vocabulary.  A test walks `app/` and fails on
  a second spelling.

**What this forbids**

- An enum, or any value that is not exactly `str`.
- A set, frozenset or dict for `EVENT_TYPES`.
- A membership function in this module.
- A literal `"screening_created"` (or any of the other five) anywhere else
  under `app/`; import the constant instead.
- A seventh name without a decision to move this one.

**Measured, not asserted** -- 12 tests in `test_audit_event_types.py`.  One
mutant planted: `SCREENING_CREATED` repeated in the tuple.  Caught, one
failure naming the offender; reverted, 12 pass.

**What this leaves.**  Nothing refuses a name yet -- 10.2's writer is where
the vocabulary becomes load-bearing, and it is also where a `record_salt`
column and a `batch_index` column land (`D64`).

---

## D66 -- one writer, one record shape, and the two columns the writer and the verifier share

**Date:** October 1, 2026. **Status:** settled, task 10.2.

**Context.**  `D65` closed the vocabulary and left the writer to enforce it.
`D64` had been explicit about what was still missing: `verify_event` hashed
the row's `payload` alone and took the salt and the batch order as required
keywords, because neither was stored.  A writer had to answer three
questions at once -- what is hashed, what is persisted, and what 9.17
recomputes -- and a disagreement between any two of those makes `verified` a
claim about a value nobody hashed.

**Decision.**

- **`app/audit/emit.py` holds `emit(event_type, screening_id, payload, *,
  sessions)`, and it is the only function that creates an audit event.**  A
  test walks `app/` and fails on any other module constructing an
  `AuditEvent`, which is the enforcement behind the task's wording rather
  than a promise in a docstring.  The name is checked against `EVENT_TYPES`
  itself -- the imported tuple, asserted to be the same object -- so there is
  no second list for a seventh name to be added to.
- **The hashed record is `{actor, event_type, payload, screening_id}`,**
  spelled once in `app/audit/record.py` and imported by both halves.
  `screening_id` goes in as `str()`, because `D48` has no UUID branch and a
  raw UUID has no canonical JSON at all.  `created_at` and `batch_id` are
  deliberately outside it: the stamp is applied by the ORM after the digest
  is taken and reads back naive on SQLite, and an event is unanchored when it
  is written, so a record carrying either would name a value the row does not
  hold.  Hashing the type and the station beside the payload is what makes a
  rewritten `event_type` answer `altered` instead of `verified`.
- **The record is hashed before the row is built.**  A `float` in a payload
  raises `CanonicalJsonError` (`D48`) and no row is written, so there is no
  event in the trail whose digest cannot be recomputed.  A score goes into a
  payload as text or a scaled integer.
- **Two columns, one migration (`b7d41c9e2f08`), both nullable.**
  `record_salt` is written by `emit` beside the digest it was taken with;
  `batch_index` is written by `anchor_batch`, which is what cuts the run into
  batches and therefore what knows the order.  A column added to a table
  that already holds rows cannot be `NOT NULL`, and a row carrying neither
  answers `unknown`, which is never a clearance.
- **`verify_event` is now `(event, *, sessions, ledger)`.**  The salt and the
  batch are read out of the row, `batch_index` giving the order the tree was
  cut in.  Two facts that were caller-supplied refusals became row
  conditions: a salt that is not readable and a position that is missing,
  duplicated or non-contiguous all answer `unknown` rather than raising.

**What this forbids**

- A second function, helper or repository method that constructs an
  `AuditEvent`.
- A second spelling of the hashed record, in the writer or the verifier.
- `created_at` or `batch_id` inside the hashed record.
- Hashing the `payload` alone, which leaves `event_type`, `actor` and
  `screening_id` rewritable under a `verified` answer.
- Handing `verify_event` a salt or a batch order.
- A `NOT NULL` claim on `record_salt` or `batch_index`.

**Measured, not asserted** -- 29 tests in `test_audit_emit.py`, 34 in
`test_ledger_verification.py` (was 33) and 29 in `test_ledger_anchoring.py`
(was 28).  The load-bearing one is
`test_an_event_written_by_the_writer_verifies_against_its_root`: a real
`emit`, a real `anchor_batch`, and `verify_event` answering `verified` with
no hand-built hash between them.

**What this leaves.**  Nothing calls `emit` yet -- 10.4 wires it into the
screening flow and 11.1 into the request.  **The station is still the
placeholder** `"station-unset"`; 10.7 replaces it with a configured one and
the actor is already inside the hashed record, so making it configurable
changes no digest shape.  **A `float` written by anything but this writer
still answers `unknown`**, and a row written before this revision carries no
salt at all.  **A batch that lost a row now answers `altered` rather than
`unknown`**, because the order stayed readable and only the leaf set moved;
the old answer was true when the order was the caller's.

---

## D67 -- every payload carries its ruleset and model versions, spelled as unknowns rather than defaulted

**Date:** October 1, 2026. **Status:** settled, task 10.3.

**Context.**  A `Screening` row carries `ruleset_version` and
`model_versions`, and neither is defaulted -- `models.py` refuses to name a
ruleset for a row nothing has read a document with.  10.2's writer, however,
stored the caller's payload and nothing else, so an event could say *that a
tier finished* without saying under which ruleset and which models, and a
reader of the trail had no way to tell which build produced a finding.

**Decision.**

- **`emit` takes `ruleset_version` and `model_versions` as keyword
  arguments, both defaulting to `None`, and attaches both keys to every
  payload** under the columns' own names (`RULESET_VERSION_KEY`,
  `MODEL_VERSIONS_KEY`, in `VERSION_KEYS`).  They are attached before the
  record is sealed, and the attached object is both what is hashed and what
  is stored, so they land inside the record for free in the writer and in
  9.17's rebuild together -- the verifier changes not at all.
- **The default is `None`, never `app.version.RULESET_VERSION`.**  This
  module does not import `app.version` at all, and a test holds that, so an
  event can never claim a ruleset nothing answered under.  Both keys are
  attached whether or not a value was handed over, so a reader never has to
  tell "unknown" from "never asked about".
- **The caller's payload is carried by reference and never amended** --
  the attachment is made to a copy, which is what keeps 10.2's "what is
  hashed is exactly what was handed over" true.
- **A payload that already carries either key is refused** (`EmitError`,
  naming the key), because one value recorded twice is two claims, and
  `None` is an answer.
- **Both values are checked in the shapes their columns hold** -- text or
  nothing, an object or nothing -- and the message names the type and never
  the value.  A `float` inside `model_versions` is still `D48`'s refusal,
  and it still arrives before the row is built.

**What this forbids**

- Reading the ruleset or the model versions off the `Screening` row inside
  the writer: `screening_id` declares no foreign key, an event outlives its
  row, and the caller that holds the row is the one that knows.
- Defaulting either value from a constant, or omitting a key that was not
  supplied.
- A second spelling of either key name.

**Measured, not asserted** -- 14 new cases in `test_audit_emit.py` (43 in
all, was 29) and one in `test_ledger_verification.py` (35 in all, was 34):
a real `emit`, a real `anchor_batch`, `verify_event` answering `verified`,
and a rewritten `ruleset_version` on the row answering `altered`.

**What this leaves.**  Nothing passes the two values yet -- 10.4 wires
`emit` into the screening flow and hands over the row's columns.  A payload
hand-built elsewhere (9.17's own fixtures, `test_ledger_anchoring.py`) still
carries neither key, and answers the same way it did.

## D68 -- the screening flow holds the row, and the two events bracket the cascade

**Date:** October 1, 2026. **Status:** settled, task 10.4.

**Context.**  D67 attached two version keys to every payload but left them
unset, because no caller had a `Screening` row to read them off.  The row is
written by `ScreeningRepository.create` before any stage has run, and the
result columns beside it are written by whoever ran the cascade -- until now,
by nobody, because 14.1's orchestrator does not exist yet.

**Decision.**

- **`backend/app/screening.py` is the flow, and it is the only caller of
  `emit`.**  One function: write the row, emit `screening_created`, run Tier 0
  through the risk engine, store the result on the row, emit
  `analysis_completed`.  10.5 to 10.7 add to this function rather than
  wrapping it, and 11.1 and 14.1 call it.
- **The first event is written before the cascade runs.**  Both version keys
  are therefore attached as the unknowns they are -- `None` is a value, not
  an omission -- and a weightset that cannot be loaded leaves the row
  `pending` with one event and no score.
- **The second event is handed the row's own columns.**  `ruleset_version`
  comes off the weightset that produced the score and `model_versions` off
  what the caller recorded, both written onto the row first and read back for
  the event: D67 forbids the writer reading the row, so the caller is the one
  that knows.
- **A score reaches a payload as whole basis points** (`score_bp`), and a
  finding as its id.  D48 refuses a `float` before a row is built, so the
  6.6 stage timings and the flags' measured values stay off the trail for
  the same reason the score is scaled rather than spelled.
- **The filename is stored on the row and reaches no event.**  `models.py`
  says caller-supplied text never leaves this table for a log or a ledger,
  and the trail is both.
- **6.5's hard-fail table is read off the runner's own union** and handed to
  7.15's required keyword.  `app.risk` may not hold it (`D6`), so the
  composition layer is where it is asked for.

**What this forbids**

- A second writer of a `Screening` result column.
- An event whose versions were not read off the row the flow holds.
- A filename, a pixel, or a `float` in an audit payload.

**Measured, not asserted** -- 12 new cases in
`test_screening_flow_audit.py`, 3976 backend tests (was 3964).

**What this leaves.**  Tier 1 and Tier 2 do not exist, so the flow runs one
tier and `model_versions` is `None` in practice until Part 12 and Part 15
have something to record.  The quality gate is not a stage here; 14.3 is
what runs it as stage 0.  `decision_recorded`, `override_recorded` and
`screening_deleted` are still unemitted.

---

## D69 -- One `tier_completed` per tier that ran, and a hard fail ends the cascade

**Date:** October 1, 2026. **Status:** settled, task 10.5.

**Context.**  D68 left the flow running one tier and emitting two events, so
the trail could say a screening existed and what it scored, but not which
tiers had run.  The abstract's cascade is three tiers deep and a hard failure
"exits directly to High Risk", so the trail has to be able to say that a
cascade stopped there rather than finished.

**Decision.**

- **The plan is a runner table, and the plan is its own keys.**
  `app/screening.py` holds `_TIER_RUNNERS`, a name to the function that runs
  that tier, and `CASCADE = tuple(_TIER_RUNNERS)`.  One structure, so the
  tiers the flow names and the tiers the trail records cannot drift apart:
  a tier that ran without being recorded has to be added as a runner rather
  than as a bare call.  Parts 12 and 15 add a name and its runner there.
- **The tier event is written inside the loop, and a hard fail breaks it.**
  `run_tier0` already answers `hard_failed`, so "the tiers that actually ran"
  is that answer and nothing else, and the last tier's result is what the
  risk engine is scored from.
- **A tier carries its own name in the payload** (`"tier": "tier_0"`), spelled
  as `TIER_NAME` beside the runner that did the work rather than beside the
  flow that ran it, so a later tier names itself the same way.
- **A tier event carries the versions that tier ran under, which for Tier 0
  is `None` for both keys.**  It is written before anything has been scored,
  and a deterministic tier runs no model; handing it the screening's
  `model_versions` would claim a model answered that did not.  D67 attaches
  both keys as `None` rather than omitting them, exactly as the
  `screening_created` event does.
- **`analysis_completed` gains `tiers_run`**, the cascade's own answer about
  itself, so a reader who meets the trail at its end can tell a cascade that
  stopped early from one that was never more than one tier deep -- and can
  check that answer against the tier events beside it.
- **The stage timings stay off the trail** and the findings go in as ids, for
  D48's reason and D68's: a payload a ledger cannot re-canonically-spell is
  refused before a row is written.

**What this forbids**

- A `tier_completed` for a tier that did not run, and a tier that ran
  without one.
- A `tier_completed` carrying another tier's model versions.
- A second place that names the tiers a screening ran.

**Measured, not asserted** -- 11 new cases in `test_tier_event_audit.py`
(two of them hold the stop with a stubbed second tier, which is the only
reading left once the real plan holds one name), and 10.4's three
event-counting tests restated.  3987 backend tests (was 3976).

**What this leaves.**  Tier 1 and Tier 2 do not exist, so the plan holds one
name and a real cascade is one tier deep.  The escalation rule that decides
whether Tier 2 runs at all is 12's, not this task's; the loop stops on a hard
fail and would stop on an escalation decision for the same reason.

---

## D70 -- An override is its own event, beside a band that names no outcome

**Date:** October 1, 2026. **Status:** settled, task 10.6.

**Context.**  The abstract has the officer "choose to allow entry, send the
traveller for further inspection, or reject entry" while the system "combines
all flags into a score R and a band", and says "officer overrides are ledgered
in the same way" so the trail "records exactly what the system showed the
officer".  D65 through D69 named `override_recorded` and wrote every other
event, so this is the first change to write a rejection into the backend --
which 7.10's own suite said would have to record here whether it was the
officer's own choice being written down or a band being acted on.  **It is the
 former.**

**Decision.**

- **The officer's three choices are declared once**, in `app/audit/decision.py`
  as `OFFICER_ACTIONS` in the abstract's own order, spelled the way 18.1's
  endpoint accepts them.  No band names any of them anywhere, and no function
  takes a band and answers with an action: 7.10's walk over `app/` is
  unchanged and still finds no statement putting a band and a rejection in
  the same breath.
- **An override is a comparison, not a translation.**  `BAND_ORDER` and
  `OFFICER_ACTIONS` are two independent orderings, and
  `contradicts_band(band, action)` is their ranks differing.  The three
  agreeing pairs are `low`/allow, `review`/further inspection and
  `high`/the adverse choice; **every other pairing is recorded, in either
  direction**, so an officer who released a document the system was more
  worried about is owed the same record as one who stopped a document the
  system was less worried about.  Where the rule errs, it errs toward
  recording.
- **`record_override` is the only writer of the event**, and it writes through
  `emit` with `sessions=` passed explicitly.  It takes the band as an
  argument rather than reading it off a row, so a band is never recomputed
  where a choice is recorded.
- **An agreeing choice answers `None` and writes nothing.**  It is not a
  refusal and not a failure, so it is a named return rather than an
  exception -- and the caller cannot both ask and emit, because the rule is
  read in one place.
- **The event is beside the automated result and never inside it.**  Nothing
  in this module writes to the screening row or to the event
  `analysis_completed` left: the payload is `system_band` and
  `officer_action` beside the two version keys, the digest is the one hashed
  over that record, and 9.17 verifies it with no change.
- **7.10's second claim is narrowed, not dropped.**  It used to hold that no
  identifier and no string in `app` was a rejection; it now holds that the
  only such spelling anywhere in the service is the declaration of the
  officer's own three choices in `audit/decision.py`, and that the walk has
  to find nothing else.

**What this forbids**

- A band that names an outcome, in a table or in a conditional.
- An override recorded by amending `analysis_completed`, or by a column on
  the screening row.
- An override payload carrying a score, a filename, a flag label or a
  `float` (`D48`).
- A second spelling of the three choices.

**Measured, not asserted** -- 36 new cases in
`test_override_event_audit.py`, including all nine band/action pairs and a
probe set held against the pairing walk, plus 7.10's vocabulary case restated
and its band-side non-vacuity test widened to reach the new module.

**What this leaves.**  Nothing calls `record_override` yet: `decision_recorded`
is 18.3's, the endpoint is 18.1's, and 18.2's validation error for a
`reject` on a `low` band without `override: true` is where this rule first
reaches a request body.  The `actor` is still the placeholder until 10.7.

---

## D71 -- The create endpoint answers with a row and the one event beside it, and the upload's checks are spelled once

**Date:** October 1, 2026. **Status:** settled, task 11.1.

**Context.**  `Screening.id` and `AuditEvent.id` were both made opaque tokens
on the ground that 11.1's answer carries them together, and 8.10's contract
already said the create row is written *before* anything has analysed
anything.  Nothing had reached HTTP: the only route was `/api/analyze`, which
runs the nine quality checks and keeps no row.  ROADMAP B8.1 also asks for the
two ids "immediately, analysis continues", which is a background job this
project has no table, worker or queue for.

**Decision.**

- **`audit_id` is the id of the one `analysis_completed` event for that
  screening**, read back out of the trail rather than recomputed, so it is
  the id of the row `emit` stored and the id 18.7 verifies.  The other two
  events are the trail's setup; the one whose payload says what the system
  answered is the one a reader is handed.
- **The upload's checks are one function.**  `app/analysis.py` gained
  `read_uploaded_image`, holding the size cap, the media types, the pixel cap
  and the mode vocabulary in the order `/api/analyze` has always refused in;
  `analyze_uploaded_image` is now that frame plus `analyze_image`.  11.1's
  endpoint therefore cannot answer a bad upload differently from `/api/analyze`,
  which is the claim 11.9 re-tests and a second copy of the caps would have
  quietly broken.
- **The route holds the seam, not the factory.**  `app/api/__init__.py` holds
  `get_sessions`, an overridable dependency returning `SessionLocal`, so a
  test points the service at a temporary database by overriding one name.
  The flow and `emit` still refuse a module-level factory (`D62`).
- **The cascade runs in a threadpool, synchronously, and the request answers
  when it has finished.**  B8.1's "analysis continues" is not implemented:
  nothing here can enqueue work, so an answer that returned before the
  cascade ran would be an answer with no `analysis_completed` behind it and
  no `audit_id` to give.  A job table and a worker are a later decision, and
  11.2's read is what a client polls in the meantime.
- **`mode` is accepted and not stored.**  It is in the shared multipart shape
  and is checked against the same vocabulary, but
  `Screening.mode` is the quality gate's own reading of the capture, which
  14.3 runs and writes; a route that filled it would be a second writer of a
  result column.
- **`document_type` is optional and defaults to `"unspecified"`.**  The row
  cannot be written without a claim, `D16` imposes no vocabulary on the words
  a caller sends, and a claim nobody made is stored as its own name rather
  than as a kind of document.  A blank claim is refused rather than stored.
- **A name is never invented.**  An upload that arrived without a filename is
  stored as the empty string, which the flow already keeps off the trail and
  out of every log.

**What this forbids**

- A second copy of the upload caps, the media types or the mode vocabulary
  anywhere in `app/`.
- A route closing over `SessionLocal`, or a flow reachable without a
  required `sessions=`.
- A `screening_id` answer with no `analysis_completed` event beside it.
- `document_type` checked against a vocabulary of document kinds.

**Measured, not asserted** -- 18 new cases in `tests/api/test_screenings_api.py`:
both ids present, each naming a row that exists, the audit id a member of that
screening's own trail, two uploads answering with two trails, the shared caps
and codes on both endpoints, the claim stored and the gate's `mode` column
left `None`, and no row written for any refusal.  `4041` backend tests pass
(was `4023`).

**What this leaves.**  `GET /api/screenings/{id}` (11.2) and the list (11.3)
are the only reads; the trail has one read seam
(`app/audit/trail.py`) that 18.7 and 24.8 grow; no reference date is
injected, so a DOB century stays unasked; and the request is not yet rate
limited, structured-logged or request-stamped (11.5 to 11.8).

---

## D72 -- The result is read off the row; its terms are rebuilt against the row's own ruleset, and the answer carries no verification status

**Date:** October 1, 2026. **Status:** settled, task 11.2.

**Context.**  ROADMAP B8.3 asks `GET /api/screenings/{id}` for "score, band,
flags with regions, summary, verification status, versions", and the
atomised task narrows it to the score, the band, the flags, the contributions
and the ruleset version.  11.1's flow stores five of those on the row and
stores **no contributions**: 8.4's suite holds `screenings` to the sixteen
columns the task names, so a seventeenth is a schema change 11.2 did not ask
for and would have to migrate.  The last session's handover assumed the row
"writes the whole result"; it does not, and a term is what is missing.

**Decision.**

- **The answer is the row's own columns, and nothing is scored again.**
  `score`, `band`, `ruleset_version`, `model_versions`, `summary`, `flags`,
  `status`, `document_type`, `created_at` and the two dimensions are all read
  and serialised, never recomputed -- the band an officer is shown is the
  band that was shown when the score was made.
- **A contribution is a pure function of two things the row does hold, so it
  is rebuilt rather than stored.**  A term is `weightset weight x stored
  value`, and `app/screening.py`'s `screening_contributions` hands the stored
  findings to the same `weighted_breakdown` that summed them the first time.
  The reader sits in the same module as the writer of the `flags` column for
  that reason: two modules holding one column's spelling is two answers to
  "what does this row hold".
- **The weightset must be the one the row names, and a mismatch is refused.**
  Recomputing against a *different* weightset would put numbers on screen
  that do not add up to the score beside them, so a `ruleset_version` that is
  not the loaded file's is a `WeightsetError` and a generic 500.  The
  known cost is recorded below rather than hidden.
- **The answer carries no verification status.**  9.17 answers `unknown` for
  any event no batch has claimed, and nothing in the service anchors an event
  outside its own tests, so a field here could only ever say `unknown` -- a
  decoration that looks like a check.  18.7 (`/api/audit/{id}/verify`) owns
  that answer and grows the trail's read seam; a client that wants it asks
  there.
- **A row nobody has scored is answered, not refused.**  11.1 hands back an id
  before the cascade runs, and 8.4 made the result columns nullable for
  exactly that reason: the answer carries `null`'s and empty lists, which is a
  state the row can hold rather than an error.
- **The route is a plain `def`.**  FastAPI runs a synchronous path operation
  in a threadpool, so the read needs no `run_in_threadpool` of its own; 11.1's
  `async def` keeps its own because it awaits the upload.
- **The `filename` is not in the answer.**  11.1 already holds the name off
  every response and 11.2 does not reopen that.

**What this forbids**

- A second scoring pass over a stored row, or a stored contribution beside a
- score it was not summed into.
- A `contributions` column on `screenings` without a migration and a decision
  that 8.4's column count is wrong.
- A 500 that names a ruleset version, a finding id or anything read off a
  document.
- A `verification` field on this endpoint.

**Measured, not asserted** -- 13 new cases in
`tests/api/test_screening_result_api.py`: every field present, the score, band,
ruleset version and flags equal to the stored row's own, a real 6.2 finding
carrying a four-corner polygon, one `weight x value` term per finding in the
same order and weighed by the version the row names, the terms summing to the
pre-history total rather than to the hard-fail floor the score sits at, a
region-less finding listed rather than dropped, a `pending` row answered, a
soft-deleted row 404, a non-uuid 422, and a ruleset mismatch refused without
echoing the version.  `check-all.ps1` exits 0: `4054` backend tests (was
`4041`), 45 frontend, build.

**What this leaves.**  A ruleset bump makes a row scored under the old file
unreadable until it is re-scored, because the weights that produced its score
are not kept; keeping the weightset *name* on the row, or keeping one weight
per finding, is a schema decision nobody has taken.  11.3's list and 11.4's
404 shape are the next reads, and no reference date is injected over HTTP, so
a DOB century stays unasked.

## D73 -- The three filters are one paged statement in the repository; a list row carries six columns and the answer carries the count

**Date:** October 1, 2026. **Status:** settled, task 11.3.

**Context.**  ROADMAP B8.2 asks `GET /api/screenings` for "band / date /
doc-type filters and pagination", done when it "matches the B3.3 repository
contract".  That contract is four reads, and three of the four take **no**
window: `list_by_band` is paged, while `list_by_date_range` and
`list_by_document_type` answer a whole tuple, so a caller wanting all three
filters could only fetch every matching row and page in Python -- a second
count, an order the repository does not own, and a table read that grows with
the history rather than with the page.

**Decision.**

- **One composed read lives in the repository, not in the route.**
  `ScreeningRepository.list_matching(band=..., document_type=...,
  start=..., end=..., offset=, limit=)` ands the conditions that were given and
  hands them to the same private `_page` the other reads use, so the order,
  the `deleted_at` rule, the bounds check and the count are written once.  A
  statement is the repository's job, and a route that built one would be a
  second spelling of every rule the module already holds.
- **A filter left `None` is not applied.**  So `band=None` is "no band
  filter" here and "the rows nothing has scored" in `list_by_band`: the two
  reads differ deliberately, each says so, and the composed one is documented
  rather than left to be guessed at.
- **Neither a band nor a kind is checked against a vocabulary.**  A name no
  row carries is an empty page, as on the reads being composed: the
  repository holds no band list, and 7.10's walk exists to keep it that way.
- **A range keeps 8.14's rules and its refusals.**  Both ends inclusive,
  either end open, converted to UTC, and a bound with no timezone or an
  inverted range refused.  The route does not re-check them: it turns the one
  `ValueError` the read raises into a 422 in the shared envelope, so the rule
  stays in one place and a caller mistake is not a 500.
- **A page is `items`, `total`, `offset`, `limit`.**  `total` counts the rows
  every given filter matched rather than the rows on the page, so 24.3's
  table needs no second request; the bounds are echoed because a caller that
  did not record its own query can still read what it was given.
- **A list row is six columns.**  `screening_id`, `status`,
  `document_type`, `created_at`, `score`, `band` -- the row's own, never
  re-scored.  The findings, the narrative and the upload's `filename` are
  11.2's answer, and a page of them would make the history read cost what the
  result read costs.
- **The page size has a default and a ceiling** (`20` and `200`), declared
  where the request is read.  The ceiling is a bound rather than a policy:
  11.8's rate limit and 26.3's instance settings decide what a read may
  really cost.

**What this forbids**

- Composing the three filters in a route, a worker or a test, or paging a
  whole-tuple read in Python to fake a window.
- A second count: a `total` read from anywhere but the statement that produced
  the rows.
- A band or document-type vocabulary added to the repository or the route to
  make a filter "valid".
- Guessing a timezone for a naive bound, at either end.
- The findings, the narrative or the upload's filename on a list row.

**Measured, not asserted** -- 20 new cases in
`tests/api/test_screening_list_api.py`: the page envelope and the six row
columns, no filename or findings anywhere in the answer, a `pending` row
listed with nulls, the band and kind filters against a table holding every
band and kind, an unknown band or kind an empty page rather than a refusal,
both ends of a range inclusive, an open end reaching the edge of the table,
all three filters over one window with each filter alone answered first, a
window no row falls inside an empty page and not the table, `limit`/`offset`
splitting the rows while `total` holds, a page taken over the matched rows, a
page past the end empty and still counting, a soft-deleted row absent from
both rows and count, a naive bound and an inverted range 422 in the shared
envelope, three refused page bounds, and the contract declaring the six
parameters and no security.  10 more in
`tests/unit/test_screening_repository.py`, against six rows written in an
order they are not read back in: all three filters with each alone answered
first, no filter answering what `list` answers, paging over the matched rows,
no vocabulary check, the delete rule with a filter applied, both refused
bounds, a refused range reading nothing, asked twice answering twice and
writing nothing, and reading only from the database its sessions name.

**What this leaves.**  A `created_at` read back from SQLite carries no offset
(`D36` records why), so the instant this answer prints cannot be fed straight
back into `created_after` -- a 422 by design, since a naive bound is two
instants on two backends.  11.2's answer has the same shape, so giving both
endpoints one UTC-labelling helper is 24.1's or 11.12's decision rather than
a second spelling here.  The rows nothing has scored carry `band = None` and
are listed by every filter except the band one, which cannot name them: an
`unscored` chip would be the vocabulary 7.10's walk exists to catch, and what
24.7's pending filter is called is 24.3's decision.  Sort is the
repository's one order (`created_at` then `id`) and is not a parameter yet;
24.3 asks for sort and owns it.

## D74 -- One error envelope for every endpoint, and a crash answers in it too

**Date:** October 1, 2026. **Status:** settled, task 11.4.

**Context.**  `/api/analyze` established the refusal body --
`{"error": {"code", "message"}}` -- and 11.1 to 11.3 answered through it, but
that was a habit three routes happened to keep.  Nothing stopped the next
route from returning a bare `HTTPException` (which FastAPI renders as
`{"detail": ...}`), a second field beside `error`, or a different message
spelling, and a client parsing one shape would have had to branch on the
endpoint.  A fourth gap sat under all three: a route's own
`except Exception` only covers faults that route raises, and the two `GET`
routes have none, so an unexpected fault on a read was answered by
Starlette's `text/plain` `Internal Server Error` -- a body no client can
parse at all.

**Decision.**

- **One body, one handler, and a test that holds every refusal to it.**
  `app.main` keeps `APIError` and `RequestValidationError` where they are, and
  `backend/tests/api/test_error_envelope_api.py` drives every refusal the
  three new endpoints can answer -- eight on the create, four on the list,
  two on the read -- through the real app and asserts `{"error"}` at the top
  level and exactly `{"code", "message"}` inside it, on every one.  The 404
  the task names is asserted against `/api/analyze`'s own body rather than
  against a literal, so "the existing envelope" means the one that is there.
- **A fault no route caught is answered in the same envelope, as a 500
  `INTERNAL_ERROR`.**  A third handler on the app covers the reads, which
  have no catch-all of their own.  It names nothing: the traceback goes to
  the log, and the body says only that the request could not be completed.
  A route that catches its own faults still answers `SCREENING_FAILED` or
  `SCREENING_UNREADABLE` and never reaches this one.
- **A code is a vocabulary, and is spelled `UPPER_SNAKE`.**  The test holds
  the pattern rather than a list, so a new code is allowed and a misspelt one
  is not.

**What this forbids**

- A second refusal body on any endpoint, including a second module that
  builds `{"error": ...}` by hand beside `app.main`.
- Raising `HTTPException` from a route for a refusal a caller can fix; the
  envelope's `code` is what a client branches on.
- Putting a fault's detail, a filename or a traceback in a refusal body.
- Letting a declared `responses=` entry on a new route name any model other
  than `ErrorResponse`, which the test now walks.

**Measured, not asserted** -- 20 new cases in
`tests/api/test_error_envelope_api.py`: the thirteen refusals above, each
driven through the real app and held to the one shape; a guard that fails if
a fourth endpoint is added with no refusal of its own here; the 404 compared
against the pre-existing endpoint's body; `SCREENING_FAILED` and
`SCREENING_UNREADABLE` in the envelope with no fault detail in either body;
the unhandled-fault 500; and two contract walks, one over every failure the
three routes declare and one asserting no second error schema exists in the
OpenAPI document.  Removing the new handler was checked to turn the last of
them red with `content-type: text/plain`.

**What this leaves.**  A *router miss* is not an endpoint refusal, so an
unknown path still answers FastAPI's `{"detail": "Not Found"}` and a wrong
method still answers `{"detail": ...}` with a 405; wrapping those would mean
overriding the framework's own handler rather than adding one of ours, and
nothing in Part 11 asks for it.  The message text is still per-refusal and
not yet pinned -- 11.12's contract snapshot is where a wording change should
start failing.  11.8's rate limit and 11.11's readiness probe will add codes
to the same vocabulary; they do not add a second envelope.

---

## How to use this file

- Read it before proposing architecture, UI, or security changes.
- Do not treat any decision here as up for debate in a routine task.
- To change one, say so explicitly, and append a new dated entry describing
  what replaced it and why. Never edit an entry in place.
- New settled decisions go at the bottom in the same format, so this file
  stays a record rather than a summary that silently drifts.

---

## D75 -- One request id, stamped by one middleware, adopted from the caller and refused when it is not id-shaped

**Date:** October 2, 2026. **Status:** settled, task 11.5.

**Decision.**

- **`app.api.request_id` owns the one header name, the one stamp and the one
  rule for an offered id.**  `X-Request-ID` is spelled once, the middleware
  in that module is the only thing that stamps a request, and
  `resolve_request_id` is the only thing that decides what a request is
  stamped with.  `app.main` imports the name and the middleware and nothing
  else spells either.
- **An id a caller offers is adopted, not replaced.**  11.6's JSON log line
  and 26.8's correlation column both want the value a caller already holds,
  which is the whole reason for reading the inbound header rather than always
  minting.  Surrounding whitespace is the header's and is trimmed; anything
  else is kept exactly as written.
- **An offered id that is not id-shaped is refused, not sanitised.**  The
  accepted shape is `[A-Za-z0-9._:-]{1,64}`.  A newline, a null, a control
  character, a space or a separator in that value would be reflected into a
  response header *and* into 11.6's log line, which is a header-injection and
  a log-forging surface that a caller controls; a value over 64 characters is
  an unbounded string in the same two places.  Such a request is stamped with
  a fresh uuid4 hex instead, so nothing the caller sent is ever echoed back.
  The colon is in the set because `traceparent` fragments and proxy-chained
  ids are spelled with one.
- **The middleware is added after the CORS middleware**, so it wraps it: a
  preflight `OPTIONS` the CORS middleware answers by itself is stamped like
  any other answer, rather than being the one answer with no id.  The header
  is in both `allow_headers` and `expose_headers`, because a browser may only
  offer an id the preflight permits and may only read one the origin is told
  is exposed.
- **The 500 for a fault no route caught is stamped by its own handler.**
  This was measured rather than assumed: Starlette wraps the user middleware
  in `ServerErrorMiddleware`, so an exception that reaches it is answered by
  the registered `Exception` handler *outside* every user middleware, and that
  response never passes back through the request-id middleware.  A throwaway
  probe confirmed it -- the same middleware stamped a 404 and left the 500
  with no header.  `handle_unexpected_error` therefore stamps its own
  response from `request.state`, which the middleware has already filled.
  This is the one place the header is set outside the middleware, and it is
  the one place that would otherwise have no id.

**What this forbids**

- A second stamp: another middleware, a dependency that writes the header, or
  a route that sets it by hand.
- Echoing a caller's id back unsanitised, however convenient -- the value is
  caller-controlled and reaches a log line.
- Reading the inbound header anywhere but `app.api.request_id`.
- A second spelling of the header name outside the module that owns it.

**Measured, not asserted** -- 30 cases in
`tests/api/test_request_id_api.py`: all four answers the app can give (a
success, an envelope refusal, a router miss, and the unhandled-fault 500),
each asserted to carry a minted id; two requests answered with two different
ids; four offered ids adopted verbatim; thirteen offered ids that are not
id-shaped each refused, with the injection-shaped ones checked to have
introduced no second header; the same rule at the seam for values no HTTP
client will put on the wire; the id read back off `request.state` by a route
on a probe app; and both CORS directions.  Removing the middleware was
checked to turn 23 of the 30 red, and removing only the 500 handler's stamp
to turn exactly that one red -- the case the middleware cannot reach.

**What this leaves.**  The id is on `request.state` and in the header, but
nothing reads it yet: 11.6's log line and 26.8's stored correlation column
are the two consumers, and until they land the id is carried and not used.
Nothing writes it to a log or a row, and `check-all.ps1` still passes with no
assertion anywhere that a log line carries one.  There is no inbound header
allow-list beyond the character set -- a deployment behind a proxy that
should not let a caller choose its own id has no setting that says so, and
trusting the edge rather than the caller is a deployment decision, not one

---

## D76 -- One JSON object per log line; the message is the event name, the request id is ambient, and the line names a handler rather than a path

**Date:** October 2, 2026. **Status:** settled, task 11.6.

**Context.**  Nothing in the service configured logging at all.  Five call
sites used `logger.exception` and `logger.error` with prose and `%s`
interpolation -- `Unhandled request error`, `Screening %s could not be read
back` -- and none of them named the request, because 11.5's id was stamped
and never used.  11.6 asks for structured JSON carrying the request id and
an elapsed time; 11.7 then has to assert that no line ever contains image
bytes, OCR text or identity data, and 26.8 wants per-tier latency and a
correlation column.  Those three tasks share one decision, so 11.6 takes
it rather than leaving the format to be re-litigated twice.

**Decision.**

- **`app.logging_config` owns the format; `app.api.request_logging` owns the
  one line per request.**  `JsonFormatter` renders one record as one object;
  `RequestLoggingMiddleware` times every `http` request and writes that
  line in a `finally`, so a fault a route did not catch still has one.
- **The message *is* the event name -- `http_request`,
  `unhandled_request_error` -- and nothing is interpolated into it.**  This
  is the decision 11.7 rests on.  A payload reaches a log by being
  formatted into a string, so removing the free-text slot removes the class
  of leak rather than promising to police it.  Structured values ride
  beside the message under a single `fields` key, and are named arguments
  only: `log_event(logger, "screening_unreadable", screening_id=str(...))`
  cannot be assembled from a caller's keys, and cannot shadow the event
  name, which the formatter drops rather than merges.
- **The request id is ambient, not passed.**  `bind_request_id` puts it in a
  `ContextVar` the formatter reads, so a handler, a route and the timing
  middleware all write the same value without any of them being handed it.
  A `ContextVar` rather than a thread-local because the sync routes run in a
  threadpool -- `run_in_threadpool` copies the context, so an exception
  raised inside one carries the id with it.
- **The line names the handler, never the path.**  A probe confirmed
  Starlette sets `scope["endpoint"]` on a match and never sets a template
  for the path.  A path is caller-controlled text: 11.5 refused to reflect
  an offered request id for exactly that reason, and a URL would reintroduce
  it through the back door, since `/api/screenings/<anything>` matches
  before `uuid.UUID` ever refuses it.  So the field is the endpoint's dotted
  name, and `null` says the request matched nothing.
- **`propagate` is off for the `app` logger.**  Otherwise uvicorn's own root
  handler renders the same record a second time, in whatever format it was
  configured with -- and the whole point is that there is one format.
  `configure_logging` is idempotent, because `app.main` is imported by every
  test session.
- **`LOG_LEVEL` is read by `app.config`,** like every other variable
  (`get_log_level`).  An unknown level name is refused rather than applied:
  `Logger.setLevel` answers an unrecognised string by doing nothing at all,
  so a typo would leave the level wherever it was while looking as though
  it had been set.

**Measured, not asserted** -- 32 cases in
`tests/api/test_json_logging_api.py`.  A line parses as JSON; it carries the
five keys every line promises, and a UTC ISO timestamp that parses back; a
success, a refusal, a router miss and a crash all produce the same shape;
an id a caller offered is the id the line carries *and* the header carries;
two requests log two ids; the elapsed time is a float that covers the
handler and not just the response; a traceback stays on one line; a field
that is not serialisable is stringified rather than raising out of a logging
call; a field named `message` is dropped rather than merged; the level
reader takes every level name, folds case, treats blank as the default and
refuses an unknown name.  Four mutants were run: removing the middleware
turned 11 red; dropping the id from the formatter turned 5 red; pinning
`elapsed_ms` to zero turned 1 red.

**What this forbids**

- Interpolating a value into a message, or a second format, or a second
  handler on the `app` logger.
- Reading the inbound header to log an id, or minting one where none was
  stamped: `bind_request_id(None)` logs `null`.
- Logging a URL, a query string, or any other caller-supplied text.
- Setting the level anywhere but `app.config`, or configuring logging from
  a module that is not the one that owns the format.

**What this leaves.**  11.7's content ban is unwritten -- the structure is
here, the assertion is not.  26.8's per-tier latency and its stored
correlation column are still owed, and a line naming a tier is the natural
place for the first.  The level is read once at import, so changing
`LOG_LEVEL` needs a restart, and there is no log *destination* setting --
lines go to stdout, which is right for Cloud Run and wrong for a file a
deployment wants to ship.  The formatter is not a structured-logging
protocol implementation: it emits no `trace_id`, spans, or resource
attributes, so a deployment adopting OpenTelemetry has nothing to map onto
and would add a second formatter beside this one.

---

## D77 -- The ban on payload content is an allow-list of field names, read from the source; not a filter on the rendered line

**Date:** October 2, 2026. **Status:** settled, task 11.7.

**Context.**  D76 left no free-text slot in a line, so the only way an image,
an OCR string or an embedding could reach one is as a *value* somebody passes
to `log_event` -- or as a message somebody rebuilds, which D76 already
forbids.  That narrows the problem to a finite and checkable one, and 11.7
asks for an assertion rather than a convention.

**Decision.**

- **The assertion is a field-name allow-list, not a filter on the rendered
  line.**  `ALLOWED_FIELDS` names the six values a call site may hand in:
  `elapsed_ms`, `handler`, `method`, `module`, `screening_id`, `status`.
  Each is vocabulary this repository chose; none is data a caller supplied
  or a document carried.  Scrubbing the line instead would mean recognising
  an embedding by its shape and an MRZ by its grammar, and would fail open
  on anything it had not been taught.
- **The allow-list is read from `backend/app` with `ast`, so it polices the
  next call site and not only the seven that exist.**  The same walk refuses a
  message that is not a string constant, and any `**fields` splat, whose
  names nothing has seen.
- **The runtime half drives the real flows; the mutation half proves it
  bites.**  A payload is logged on purpose in a permanent test, because
  without it every runtime assertion would pass against a checker that never
  matched anything.  Four deliberate leaks were injected to confirm the guards
  turn red, then reverted.
- **The caller's own text is banned alongside the document's.**  The holder's
  name sent as a filename or a document-type claim reaches the endpoint that
  stores it on the row; the log is the third place it must not go.

**This forbids.**

- Passing a payload, a caller-supplied string, or any document-derived value
  to `log_event` under any field name.
- Adding a name to `ALLOWED_FIELDS` to make a failing test pass, rather than
  renaming the call site's field to something the service owns.
- Reintroducing a message that is built rather than named.

**What this leaves.**  The ban covers values passed to `log_event`; a library
raising `ValueError(f"...{contents}")` still reaches the log through
`exc_info`, and nothing holds that today.  `ALLOWED_FIELDS` is hand-written,
so adding a legitimate field is an edit to a test.  And
`JsonFormatter._fields` drops any field whose name is a `LogRecord`
attribute -- `module` is one, so `quality_check_module_failed` is written
without the module it names.  11.7 found that and deliberately did not assert

---

## D78 -- One budget per address on the two endpoints that analyse an image, keyed on the peer address and never on a header

**Date:** October 2, 2026. **Status:** settled, task 11.8.

**Context.**  11.8 asks for per-IP rate limiting on the analysis endpoints
with a configurable limit.  This is the first thing here keyed on something a
caller controls: 11.5 and D76 refused to reflect caller-supplied text into an
answer or a log, and a rejected request is exactly where a peer address would
otherwise be echoed back.  The limit is also the first gate that has to answer
before the work, so where it sits decides what a refused request costs.

**Decision.**

- **The key is the peer address the server reports, never a header.**  A
  forwarded-for address is the caller's own text, so a bucket keyed on it is
  one the caller resets by inventing an address per request.  A deployment
  behind a proxy therefore sees one bucket for every address the proxy
  forwards for, which is a known limit of this build rather than a bug: the
  honest fix is a proxy that normalises the peer address, not a header this
  service starts believing.
- **One budget on analysis, not one per route.**  `POST /api/analyze` and
  `POST /api/screenings` spend the same per-address count, so a caller who
  alternates between them cannot buy twice the analysis for one limit.  The
  reads spend nothing: 11.8 is about what an image costs, not what reading a
  row costs.
- **The refusal is a new reason code on the envelope D74 already built.**
  `429` with `RATE_LIMITED`, raised as an `APIError` and therefore answered by
  the one handler, stamped with a request id like every other answer and
  written up by the one line per request that already exists.  No second
  envelope, and no new log event: a line naming a refusal would repeat the
  handler and status the `http_request` line already carries, and a field
  holding the address would reopen the door D77 closed.
- **The guard is a dependency declared ahead of the session factory.**  So
  every request past the limit is refused before the route reads a byte, and
  before a refused request opens a database session -- and a request that was
  going to be refused anyway still spends the budget, so a bad upload is not a
  free one.
- **The counter is a fixed window, in memory, in one process, under a
  ceiling.**  A fixed window is a bucket that empties rather than a list of
  instants to expire; the price is its own, a caller spending the budget
  either side of a roll gets two of it.  The counts are lost on restart and
  are not shared between instances, so the limit is per instance.  The map is
  capped because a caller picks its own source address, and past the cap the
  window empties: memory is bounded and every caller pays one window.
- **The limit is a configured whole number, and anything else is refused
  while the configuration is read.**  `RATE_LIMIT_PER_MINUTE`, read by
  `app/config.py` like every other tunable and at import like `LOG_LEVEL`.
  `0` and a negative number are refused along with the rest: read as "no
  limit" a zero would turn a typo into an endpoint with none, and read as a
  limit it would answer every request with a refusal.  Neither is what the
  operator wrote.
- **The count is taken on the event loop, so it holds no lock.**  The guard
  and both analysis routes are `async`, which is the invariant the class
  states and a test holds; a route made synchronous would move the count into
  a threadpool and the invariant with it.

**This forbids.**

- Keying the bucket on `X-Forwarded-For`, or on any other header the caller
  sent.
- Reading `RATE_LIMIT_PER_MINUTE` anywhere but `app/config.py`, or reading it
  as a limit of zero or less.
- Letting the address reach a refusal body or a log line, or adding a
  `log_event` field to hold it.
- A second envelope for 429, or a second event for the refusal.

**What this leaves.**  The count is per process, so a deployment running
several instances meets a per-instance limit and restarts clear it; a NAT in
front of a station means every officer behind it shares one bucket, at the
default sixty a minute.  There is no `Retry-After` header, because
`APIError` carries no headers and widening D74 is not this task.  Only the
analysis endpoints are limited, so the reads are not, and nothing here is
shared with a CDN or a WAF in front of the service.

---
## How to use this file
'@

if (-not $text.Contains($anchor)) { throw "anchor not found" }

---

## D79 -- The version endpoint answers the three constants and the model set under the spellings a result and the trail already use

**Date:** October 2, 2026. **Status:** settled, task 11.10.

**Context.**  11.10 asks for `GET /api/version` returning the app, ruleset,
model and prompt versions.  :mod:`app.version` exported three of them, and its
docstring had been promising this endpoint since before it was declared.  There
is no fourth constant, and `model_versions` is not one: it is a per-screening
object of module name to version, written on the row by
:func:`app.screening.run_screening`, handed to the trail by
:func:`app.audit.emit.emit`, and answered under the same key by 11.2's result.
So the one thing the task did not settle is whether a model version belongs on
the endpoint at all, and in what shape.

**Decision.**

- **The model version is an object, not a fourth scalar.**  A `MODEL_VERSION`
  string beside the other three would be a second, incompatible spelling of a
  fact the row, the event payload and the result endpoint already spell as
  ``model_versions``.  When a model is wired it is per module -- a deployment
  may ship more than one -- so a single string could not answer the question
  the endpoint is asked anyway.
- **`MODEL_VERSIONS` lives in `app.version` beside the three constants, and is
  empty while the cascade runs no model.**  Tier 0 answers from measurements,
  so today the honest deployment-wide answer is the empty object rather than a
  placeholder string that would claim a model exists.  Wiring a model means
  editing this constant in the same commit that wires the model, which is the
  same rule ``RULESET_VERSION`` already follows.
- **The two version keys are spelled as the trail spells them.**
  ``ruleset_version`` and ``model_versions`` are :data:`app.audit.emit`'s own
  ``RULESET_VERSION_KEY`` and ``MODEL_VERSIONS_KEY``, so a client parses one
  spelling wherever it reads a version.
- **The route reads the module per request rather than binding names at
  import.**  A constant bound into the route's globals is a second copy that
  only a restart reconciles, and it is a copy tests cannot substitute.
- **The read is free.**  No budget (``D78`` -- the reads spend nothing), no
  session, no row: it is a read of four constants, so it answers even when the
  database is unreachable and even once the analysis budget is spent.

**Consequences.**  A client can cache the answer for the life of a deployment
and show it as experimental, as the module's docstring promises.  Until a
model is wired the object is empty, which is a claim to keep true rather than
a gap: 11.2's result answers ``null`` for the same fact, because a stored row
records what answered *that screening*, and ``null`` there means no model ran

---

## D80 -- Liveness and readiness are two endpoints, and the refusal wears the error envelope

**Date:** October 2, 2026. **Status:** settled, task 11.11.

**Context.**  11.11 asks for liveness to be split from readiness, with
``/ready`` checking the database and the ledger and a test that it fails when
the database is unreachable.  `/health` was declared inline in
:mod:`app.main` beside the exception handlers, opened nothing, and answered
``{"status": "ok"}`` -- and nothing in the deployment told it apart from a
readiness answer, because there was not one.  Three things the task does not
settle: where the two routes live, what "checks the ledger" means when the
ledger is a table rather than a service, and what a not-ready answer is
spelled in.

**Decision.**

- **Two routes, and liveness touches nothing.**  ``/health`` declares no
  session dependency at all, so it cannot wait on a database however long that
  database takes to answer.  This is the whole reason for the split: a
  liveness probe that consulted the database would have a supervisor restart a
  process that is alive and well, turning a dependency outage into a crash
  loop, and the crash loop would keep the dependency down.
- **The two live in ``app/api/routes_health.py``**, beside the other routers
  and out of :mod:`app.main`, which keeps the app and the error envelope.  A
  readiness probe with two checks and a readiness body is a route, and 11.12
  will snapshot it there beside every other.
- **Readiness reaches its database through :func:`app.api.get_sessions`**, the
  same overridable seam the write routes use, on ``D42``'s reasoning: a
  module-level factory bound at import cannot be pointed at a database a test
  then makes unreachable.  So the test that matters -- an unopenable database
  answers 503 -- is written by binding a factory, not by patching a global.
- **Both checks are named, and the ledger is one of them.**  ``database`` runs
  a statement that touches no table, so it measures reachability rather than
  schema; ``ledger`` reads one row of the ledger table, so a database that
  answers while its ledger is gone is reported as not ready.  A probe running
  only the first check would have passed that deployment, which is the case
  the second exists for.  The names come from one module-level list, so the
  answer, the log line and the refusal cannot drift into three spellings.
- **The 503 wears the one error envelope** (``D74``): ``NOT_READY`` under
  ``{"error": {"code", "message"}}``, with the message naming the check that
  failed.  A bespoke readiness body would be the one refusal on the service
  that a client could not parse with the code it already has; the only thing
  an operator needs from the refusal -- *which* check broke -- rides in the
  message, where it is a phrase drawn from the module's own two names rather
  than anything a caller supplied.
- **Neither probe spends rate-limit budget** (``D78``).  A supervisor polls on
  a schedule, through whatever load balancer sits in front, and must not be
  refused with a 429 because a burst of screenings spent the budget meant for
  them.

**Consequences.**  A deployment can point a liveness probe at ``/health`` and
a readiness probe at ``/ready``, and an outage now removes an instance from
rotation without restarting it.  The cost is that ``/ready`` is a real query on
every poll, so it is bounded by the database's own answer time rather than by
a cached flag, and a database that is slow rather than down will show up as a

---

## D81 -- The response schema of every endpoint is held against one committed snapshot, with every `$ref` inlined

**Date:** October 2, 2026. **Status:** settled, task 11.12.

**Context.**  Every response on this service was held only by its own file's
exact-key cases: eleven files, each knowing one shape, none able to notice a
shape it was not written for.  A field dropped from `ScreeningResultResponse`
would have failed `test_screening_result_api.py` and nothing else; a field
added to it would have failed nothing at all, because every assertion in the
suite asks for a key by name and never for the set of keys.  A rename would
have been the same silence.  The endpoint keeps answering 200 either way,
which is what makes it a break rather than an error.

**Decision.**

- **The snapshot is the documented responses, resolved.**  The contract is
  `{path: {method: {status_code: response}}}` for all seven operations,
  straight off `app.openapi()`, so it covers what a client is handed --
  status code, media type, and schema -- rather than what the handlers
  return.  Reading the generated document rather than the routes is what
  makes one test cover all of them: the list is the app's, so a new endpoint
  cannot be forgotten and an existing one cannot be answered with a shape
  the document does not carry.
- **Every `$ref` is inlined, because a ref is a hole in the comparison.**
  The document names its models once under `components/schemas` and points at
  them from seven places, so a snapshot of the pointers would record which
  models exist and nothing about what is in them -- `dpi` could be added to
  `ImageDimensions` and the file would still match.  A model that reaches
  itself keeps its own pointer, so the walk terminates rather than recursing.
  `test_no_response_is_left_holding_a_reference` asserts the property, since
  it is the whole of what makes the rest of the file worth having.
- **Prose is dropped; structure is kept.**  `description`, `example` and
  `examples` are documentation, and a docstring edit is not a change a client
  can break on.  `title`, `required`, `const`, `default` and the rest are
  kept: a renamed model or a newly required field is a break.
- **The snapshot is a committed file beside the test,**
  `backend/tests/api/openapi_contract.json`, and the failure is a unified
  diff of the two rather than a bare inequality, so the diff says which
  field and which endpoint moved.  `DRISHTI_UPDATE_OPENAPI_SNAPSHOT=1`
  rewrites it, and the test then asserts against the file it just wrote --
  so a regeneration still cannot pass a shape nobody read.
- **Two guards around the equality.**  `EXPECTED_PATHS` names the six paths
  the task names, so an added or dropped route fails as itself instead of as
  a wall of JSON, and a snapshot committed while the app served nothing
  cannot pass.  The one test file needs neither a session nor a client: an
  OpenAPI document is built without touching the database, which is the same
  reason `test_version_api.py` takes a module-level client.

**Consequences.**  A shape change now fails the suite whether it was planned
or not, and fixing it is a deliberate act -- reading the diff and rewriting
the file -- rather than something discovered by a client.  The cost is that
adding a field is now two edits, a schema and a snapshot, and a route added
in a hurry fails CI until someone reads why.  The snapshot also cannot see a
shape the document does not declare: an `APIError` the route raises without
a matching `responses=` entry is still an undocumented refusal, which is why

---

## D82 -- Tier 1's OCR seam is one abstract `read(image) -> OcrResult`, and nothing else

**Date:** October 2, 2026. **Status:** settled, task 12.2.

**Context.**  Part 12 needs two engines (`TesseractEngine` and
`EasyOcrEngine`), a fallback chain, a confidence-gated re-read and a
crop-to-region read, and each of those is a caller written once.  ROADMAP B4.1
names the engines and B4.2 the re-read, so the risk is an interface that grows
one argument per engine: a `dpi` for Tesseract, a `language` for EasyOCR, a
`psm` for neither.  Every one of those compiles, and a caller is then left
needing to know which engine it happens to hold.

**Decision.**

- **`OcrEngine` is an `abc.ABC`, on `Watchlist`'s reasoning (`D13`).**  A
  subclass that omits `read` cannot be instantiated, so a wiring mistake is a
  `TypeError` at construction rather than an `AttributeError` at the first
  document.  `test_read_is_the_only_method_the_interface_requires` pins the
  set to one name, so 12.3's availability check becomes a concrete method on
  the engines rather than a second requirement on the interface.
- **`read` takes one positional `image` and carries no option.**  A crop for
  12.8's re-read is a frame of its own, so a re-read is `read(crop)` and not
  `read(image, region)`, and no caller can reach an argument only one engine
  understands.  **The signature is read with `inspect.signature` rather than
  called**, because a method that happens to work proves less than a signature:
  adding `dpi=300` leaves every behavioural test in the file passing and is
  caught by two of the signature tests, proved by mutation.
- **A read is words, and a word is text, a box and a confidence.**  The box is
  `(left, top, right, bottom)` in the frame handed in, which is what makes
  12.8's region crop and 12.14's "every field carries the region it came from"
  addressable from a word rather than recomputed from the page.
- **`OcrResult` keeps the words and no joined page string.**  ROADMAP B4.1's
  "text + per-word confidence" is answered by the words themselves, and a
  `text` field beside them would be a second copy of a page's identity data
  with somewhere to be logged -- the thing `WatchlistHit`'s missing fields are
  about.
- **Both records are frozen and carry no public method**, as `WatchlistHit`,
  `MrzDocument` and `EvidenceFlag` are: a method here would be a second answer
  about what a page held, and it could disagree with the words the record was
  built from.
- **A page holding no words is an empty `OcrResult` and not a refusal.**  Tier
  1 degrades (12.6), so "no engine could read this page" is a result a caller
  can carry, not an exception it has to catch on a second path.

**What this forbids**

- A second argument on `read`, a default on `image`, `*args`, `**kwargs`, and
  any engine-specific option on the interface.
- `availability` as a second abstract method before 12.3 has two engines it
  could differ between.
- A `text` field or property on `OcrResult`, and any slot an engine could
  write a whole page's characters into.

**Consequences.**  Adding a third engine is a subclass and nothing else, and
12.5's `select_engine` can hold a list of them without knowing which is which.

---

## D83 -- An engine reports its own absence through `is_available()`, and the binding is imported late

**Date:** October 2, 2026. **Status:** settled, task 12.3.

**Context.**  `pytesseract` is not a declared dependency of this project and
the `tesseract` binary is an operating-system install rather than a Python
package, so a Tesseract machine and a non-Tesseract machine are both ordinary.
The task asks the engine to report itself unavailable rather than raise, which
makes absence a *value*, and a value has to be answerable before any document
is read -- otherwise 12.5's selector chooses between engines by catching
exceptions, and 12.6's degrade is a second `except` clause instead of a
branch. The risk in answering it is that the answer gets read off whichever
machine runs the test, so the suite would pass on a station with Tesseract and
fail on one without it.

**Decision.**

- **Availability is a concrete `is_available() -> bool` on the engine, not a
  second abstract method.**  `D82` deliberately left it off the seam for want
  of two engines to differ between; `TesseractEngine.__abstractmethods__` is
  `frozenset()`, which is asserted by name.
- **Two things must both be present, and either one missing means
  unavailable.**  The `tesseract` binary alone is not availability --
  `pytesseract` is what drives it -- and the binding alone is not availability
  either, because it shells out to the binary. Both halves have their own test.
- **`read` on an unavailable engine returns `ocr.NO_WORDS` and never raises.**
  This is `D82`'s "an empty read is a result, not a refusal" read literally:
  an engine that cannot read has nothing to report about the page, and 12.6's
  degradation is the same value it returns rather than a second one.
- **`NO_WORDS` is one shared value in `ocr.py`, not a literal per engine.**
  12.3 and 12.4 both answer "nothing found", and two spellings of nothing read
  as two findings later.
- **`pytesseract` is imported on first use and the absence is cached.**
  A module-scope import would make importing this module an `ImportError` on
  every box that has not installed it, which is the exact failure the task
  asks 12.3 not to have. `lru_cache` holds the absence as firmly as the
  presence, so a box without it asks once per process rather than once per
  document.
- **Both probes are constructor-injected, and `binding=None` is a different
  answer from the `binding=IMPORT` default.**  `IMPORT` means "import it when
  asked"; `None` means "there is definitely not one". Without that distinction
  a test could only assert the *real* machine's binding, so the availability
  test would mean one thing here and another on a station with Tesseract --
  exactly the failure the task's Verify line names.
- **`lang` and the page segmentation mode are module constants, not
  environment variables.**  This is a deliberate departure from `D82`'s "reads
  it from the environment". The intent there was that no caller reaches an
  engine-specific option, and a constant serves that without making one
  document's read depend on ambient process state that no request owns or can
  see; a test changes the constant rather than the environment.
- **Tier 0's frame is BGR and pytesseract's PIL path reads the array as RGB,
  so the frame is reversed and made contiguous before it is handed over.**
  Handing a frame over as it stands swaps two channels and every box, text and
  confidence still comes back plausible, so the test reads the channels out of
  what the binding received rather than trusting the read.
- **pytesseract's output holds more than words.**  Its dict form reports one
  row per block, paragraph and line alongside the words, marks those rows at
  `conf` of -1, and a confidence it could not parse is not a word's
  confidence either. A score of `0` is a word Tesseract was unsure about and
  is kept, because judging an unsure word is 12.9's confidence gate's job.
- **The mean is over the words that were read**, so a dropped row cannot drag
  a page's confidence down without contributing a word to it.
- **`read` does not wrap a real pytesseract call in a handler.**  The probe
  answers "can this engine read at all", and a failure part-way through one
  read is a different event with its own evidence. Swallowing it would make a
  broken install look like a blank page.

**What this forbids**

- `is_available` as an abstract method, or as a property on the seam.
- `read` raising for a missing binary, a missing binding, or both.
- A module-scope `import pytesseract`, and `pytesseract` in `requirements.txt`
  on the strength of this engine alone.
- Handing the frame over in Tier 0's order, or handing the caller's own array
  over rather than a contiguous copy of it.
- An environment variable for a language, a DPI, or a segmentation mode.
- Keeping a block, paragraph or line row as if it were a word.

**Consequences.**  12.4's `EasyOcrEngine` is this shape with a different probe
and a different binding, and 12.5's `select_engine` can ask `is_available()`
with no handler wrapped around asking it. The costs are honest ones: a
Tesseract installed outside `PATH` reads as unavailable, a box that loses the
binary between the probe and the read raises out of `read` rather than
degrading, and `is_available()` asks the filesystem on every call rather than
caching a verdict, because a cached "unavailable" on a machine that has since
installed Tesseract would be worse than a cheap second `which`.

---

## D84 -- EasyOCR is probed by one question and read in Tier 0's own channel order

**Date:** October 2, 2026. **Status:** settled, task 12.4.

**Context.**  `D83` settled the shape of an absent OCR engine and predicted
that 12.4 would be "this shape with a different probe and a different
binding".  It is, with one finding that is not a matter of taste and that the
prediction did not anticipate: the two engines disagree about channel order.
pytesseract builds a PIL image, which reads the array as RGB, so 12.3 reverses
Tier 0's BGR frame before handing it over.  EasyOCR does not.  Its
`utils.reformat_input` takes a three-channel `numpy` array as `img = image`
and greys it with `cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)` -- the array is
BGR, in the order `cv2.imread` produces and the order the rest of EasyOCR's
own pipeline is written in.  A second question is what "absent" means for a
package that has no executable behind it.  EasyOCR builds a `Reader` on first
use, and that construction downloads recognition models.

**Decision.**

- **EasyOCR's frame is handed over as it arrives.**  Tier 0 works in BGR and
  EasyOCR reads BGR, so there is no reversal here, and the reversal 12.3
  performs for pytesseract must not be copied across by symmetry.  Doing so
  would swap the two channels EasyOCR greys and normalises while every box,
  text and confidence still came back plausible.  The frame is still copied and
  made C-contiguous, because "reading leaves the frame it was handed untouched"
  is a property of a read rather than of an engine.
- **Availability is one question, not two.**  Tesseract's engine takes a
  `locate` probe beside its binding because it has two halves that can each be
  missing.  EasyOCR is one Python package, so `EasyOcrEngine.__init__` takes
  only `binding` and `is_available()` is `self._easyocr() is not None`.  The
  absence of a second probe is asserted by the constructor's signature, since
  a second probe added later would make the answer half-true rather than
  wrong, which no behavioural test would notice.
- **A `Reader` that cannot be built is a broken install and raises.**  The
  probe answers "can this engine read at all", and on this engine the only
  absence knowable without doing the work of a read is the package itself.  A
  present EasyOCR whose models cannot be downloaded raises out of `read`, on
  `D83`'s reasoning: swallowing it would report a blank page on a box whose
  engine is installed and merely unreachable.  `is_available()` deliberately
  does *not* try to build a reader, because 12.5's selector calls it in order
  to choose, and choosing must not be the thing that downloads a model.
- **`easyocr` is imported on first use and the absence is cached**, exactly as
  `pytesseract` is, and it is not in `requirements.txt` on the strength of
  this engine alone.
- **A box is read as the extent of EasyOCR's four points.**  EasyOCR reports
  the corners of a quadrilateral in no fixed order, not an origin and a size,
  so `(left, top, right, bottom)` is the min/max of the points rather than
  the first two of them.
- **The reading options are module constants and are passed explicitly.**
  `detail`, `paragraph` and `output_format` are EasyOCR's defaults today, and
  spelling them out is `D83`'s rule rather than a change of behaviour: a
  change to EasyOCR's own default must not be able to move our boxes.

**What this forbids**

- Reversing the frame for EasyOCR, or generalising 12.3's reversal into a
  shared helper both engines call.
- A `locate`, a `which`, or any second probe on `EasyOcrEngine`.
- Catching a failed `Reader` construction and returning `NO_WORDS`.
- A module-scope `import easyocr`, and `easyocr` in `requirements.txt` on the
  strength of this engine alone.
- Reading a quadrilateral as its first two points, or an out-of-range
  confidence as given rather than clamped to `0.0..1.0`.

**Consequences.**  12.5's `select_engine` can ask both engines the same
question and hold either one, and 12.9's fallback engine is a different
implementation behind the same `OcrResult` rather than a second shape.  The
costs are honest ones: an EasyOCR installed but not yet able to load its
models reports itself available and then raises, and asking whether this

---

## D85 -- A preference is a choice: the selector honours it, and answers `None` rather than substituting

**Date:** October 2, 2026. **Status:** settled, task 12.5.

**Context.**  `D83` settled that an engine reports its own absence as a bool
precisely so that "12.5's selector chooses between engines by catching
exceptions" would not happen, and `D84` settled that EasyOCR's probe must not
build a reader because "12.5's selector calls it in order to choose, and
choosing must not be the thing that downloads a model".  12.5 is therefore the
first caller to hold an engine at all, and the first to hold two, and three
questions the two decisions do not answer came with it.  How a preference is
spelled: ROADMAP B4.1 names the two classes, not a preference, and a name a
caller invents per call site is a second vocabulary.  What an *unavailable*
preference answers: the task says `None` "when none is available" and does not
say what a named engine that is not installed answers.  And what a name
matching no engine does -- raise, degrade, or quietly mean "any".  The risk
common to all three is a silent substitution: an operator who asked for one
engine and got a read from another has a screening that completed and says
nothing about having been read by something else.

**Decision.**

- **`select_engine` is its own module, `app.pipeline.tier1.selection`.**
  `ocr.py` is what both engines import, so a selector holding them cannot live
  there without a cycle; the seam stays a seam and the policy that chooses
  between implementations sits beside it.  This is `D82`'s "adding a third
  engine is a subclass and nothing else" -- and a subclass, which is what a
  selector holding a list needs.
- **A preference is one of two module constants, and `None` is the only
  spelling of "no preference".**  `ENGINE_NAMES` is the whole vocabulary, so a
  rename is one edit, and an empty or wrongly-cased name is refused rather than
  read as an absent preference -- `config.py`'s rule for an unknown log level,
  where the same argument applies: a shrug would make a typo mean "whichever".
- **An unavailable preference answers `None` and is not substituted.**  A
  caller names an engine for a reason -- a script it reads better, a language,
  boxes 12.8 can crop -- and answering with a different engine would hand back a
  read nobody asked for.  `None` is what 12.6 degrades on, so an unavailable
  preference and an uninstalled engine are one state to the caller rather than
  two.  **12.9 is where a second engine is tried on purpose**, and it is
  written down there; a selector that quietly tried the other one would make
  12.9's gate unreachable and would blur which engine produced a read.
- **A name this call cannot hold raises `UnknownEngineError`, a `ValueError`.**
  Every name in `ENGINE_NAMES` has an engine behind it, so a name that matches
  none is a wiring mistake rather than an absence, and answering `None` for a
  misspelling would degrade every screening on the box with nothing to say
  which engine was asked for.  It is loud on purpose: `main.py`'s catch-all
  answers it as a 500 `INTERNAL_ERROR` envelope (`D74`), and one refused
  document is cheaper than a box silently reading with an engine nobody chose.
- **The default order is Tesseract, then EasyOCR.**  It is neither
  alphabetical nor fastest-first, and the reason is `D84`: EasyOCR builds a
  `Reader` whose models are downloaded the first time one is built, so leading
  with it would make the selector's default choice the one that costs a
  download.  `ENGINE_NAMES` is that order written down, and a test holds the
  default registry to it, so an engine added out of order is caught rather than
  quietly changing which engine reads.
- **A preference is asked about alone, and the walk stops at the first answer.**
  Naming an available engine returns it whatever the order says, and asking the
  others as well would ask questions whose answers cannot change the one
  returned; the walk asks each engine once and stops, so an engine after the one
  chosen is never probed.
- **Nothing is wrapped around asking availability.**  A probe that faults is a
  broken install and propagates: swallowing it would report a blank page on a
  box whose engine is installed and merely unreachable, which is `D83`'s
  argument against a handler around `read`, applied to the question instead.
- **The seam does not declare the question this module asks.**
  `OcrEngine.__abstractmethods__` is `frozenset({"read"})` (`D82`) and
  `is_available` is concrete on each engine (`D83`), so `select_engine` is the
  one place in Tier 1 depending on a method the abstract class does not list.
  `D83` forbids making it abstract and its tests hold both frozensets by name,
  so the gap is recorded here rather than closed here: both engines in the
  default registry are built in this module, so the gap cannot be reached by a
  caller that passes nothing.  A third caller of `is_available`, or a caller
  handing in its own registry, is what should reopen `D83`.
- **The default registry is a mapping proxy over module-level singletons.**
  Read-only because a caller must not be able to edit the set the default
  choice is made from, and singletons because EasyOCR's reader -- and the
  loaded models -- lives on the instance (`D84`): a registry or an engine
  rebuilt per document would reload them per document.
- **`engines` is keyword-only and injectable, and the tests are the reason.**
  Every case in the file is answered by stubs, so each means the same thing on
  a station with Tesseract and on one without; the two tests that touch the
  real registry hold the answer to "one of ours or none" rather than to any
  particular machine's answer, which is 12.3's machine-agnostic test again.

**What this forbids**

- Answering an unavailable preference with another engine, or walking the rest
  of the registry once a name has been given.
- Reading `""`, `"Tesseract"` or `"paddleocr"` as "no preference", or answering
  `None` for a name that matches no engine.
- A `try` around `is_available()`, or a fallback that catches instead of asking.
- Reading a page, or building an EasyOCR reader, to decide which engine to read
  with.
- A default registry that is mutable, rebuilt per call, or holds engines built
  per call.
- Adding `is_available` to the interface to close the gap above.

**Consequences.**  12.6 degrades on one `None` that now covers three causes --
nothing installed, a named engine that is not available, and a registry holding
none -- and 12.9's fallback is the only place a second engine is tried.  The
costs are honest ones: a deployment that configures EasyOCR on a box without it
gets "ocr unavailable" for every document rather than a silent Tesseract read,
which is the intended refusal but is an operator-visible one; a caller
injecting its own registry must hand in objects that answer `is_available`

---

## D86 -- A page no engine could read is a degraded result; a faulting engine is loud

**Date:** October 2, 2026. **Status:** settled, task 12.6.

**Context.**  ROADMAP B4.1 asks that "the unavailable engine degrades, it does
not crash", and 12.6's task puts it as a test: Tier 1 degrades to "ocr
unavailable" and the screening still completes.  `D85` settled what the caller
is handed when an engine is missing -- one `None` covering three causes -- and
named the case this task has to decide: an engine installed but unreachable
reports itself available and then raises at its first read.  Two questions
came with it.  What is "ocr unavailable" as a value, given that a blank page and
an unread page carry the same words?  And does a read that faults degrade too,
or raise?

**Decision.**

- **`run_tier1(image, preference, *, engines)` is Tier 1 as one call, in
  `app.pipeline.tier1.runner`**, the path ROADMAP B4.12 gives the Tier 1 runner,
  and it is the first caller of `select_engine`.  ROADMAP B4.12's partial score
  and the cascade's own entry for it are 14.5's and are not pre-empted here.
- **"ocr unavailable" is `Tier1Result(ocr=NO_WORDS, ocr_available=False)`.**
  The read is the shared empty read rather than a second spelling of nothing
  (`D83`), and `ocr_available` is what distinguishes it from a blank page an
  available engine read -- a flag read off the words would make the two
  identical, since both carry none.
- **A missing engine is answered, not raised.**  The degrade is a branch on
  `None`, not a handler, and it returns the same record shape an available
  engine does, so every consumer reads `ocr_available` and nothing has to guard
  a lookup.
- **A read that faults is not degraded; it raises.**  This is `D83`/`D84`'s
  rule applied one level up: a broken install swallowed into the degrade would
  report a blank page on a box whose engine is installed and merely
  unreachable, and the absence is the one case the selector could not have
  known about.  14.11 is where a module fault is recorded without aborting the
  rest of a screening; 12.6 is not that task and does not become it by
  catching.
- **A refusal stays a refusal.**  `UnknownEngineError` propagates out of the
  runner: degrading a misspelling would hide the wiring mistake `D85` made it
  loud for, on every document on the box.
- **A preference is still honoured, and the runner never reads a page to find
  out.**  `D85`'s non-substitution reaches the document unchanged; the one
  engine tried is the one the selector chose, and 12.9 remains the only place a
  second is tried.
- **`engines` is keyword-only and injectable, for `D85`'s reason**: every case
  in the file is answered by stubs, so a case means the same thing on a station
  with Tesseract and one without.  The single test that touches the real
  registry skips rather than assumes.
- **The result is a frozen record of two fields and carries no public method**,
  as `OcrResult` and `TierResult` are (`D82`).  **There is no reason or cause
  field**: the three causes are one state to the caller (`D85`), and a field
  distinguishing them would be a second answer about the same absence.

**What this forbids**

- A `try`/`except` around `select_engine` or `engine.read` in the runner.
- A second spelling of the empty read, a `flags` or `reason` field nobody
  writes, or a partial score `R1` here.
- Substituting an engine for an unavailable preference, or trying a second one.
- Refusing a frame that is not an image: 4.1's gate is the one answer about
  what an image is.
- Reading a page when no engine was chosen.

**Consequences.**  A document on a box with no OCR engine now gets a Tier 1
result that says so, which is the operator-visible refusal `D85` intended, and
12.8-12.16 build on one record that carries the read.  The costs: a broken

---

## D87 — Tier 1's frame is a printed page in a real font, describing the person Part 4 already prints

**Date:** October 2, 2026. **Status:** settled, task 12.7.

**Context.**  Part 12 needs a frame to read, and Part 4 already ships a
generator.  Reusing it was the obvious move and is wrong: `mrz_images` draws a
zone as one glyph per cell from a 5x7 pattern table, because what reads a zone
is 4.3's component cutting and 4.5's row grouping and a nearest-pattern match
over cells it owns.  What reads a printed field is an OCR engine, and no engine
is installed on this box -- so the fixture has to be judged on the description
it hands back, not on a read.  That put four questions.  What is drawn, when
nothing here can read it back.  How a field's region is stated, when 12.8 crops
to it and 12.14 reports it.  What the specimen says, when 12.15 compares a
printed field with an MRZ.  And which knobs belong here rather than in Part 4's.

**Decision.**

- **A second fixture, `tests/fixtures/document_images.py`, beside
  `mrz_images` rather than inside it.**  A cell table has neither an advance
  nor a baseline, so no word box and no row of a form can be measured off it;
  adding a second page type to that module would have meant one module holding
  two ways of drawing and one `cells` field meaning two things.
- **The page is Hershey Simplex through `cv2.putText` at `LINE_8`, ink on
  paper, and the paper and ink levels are `mrz_images`' own re-exported rather
  than written down twice.**  A real font is what an engine is built to read,
  and one paper/ink vocabulary means nothing downstream has to ask which face a
  frame was drawn on.  **No rotation, gain, shadow or noise knob is added
  here**: Part 4 owns those, and Tier 1 degrades a page through font scale and
  re-read, so a second place to damage a page is a second answer to how one is
  damaged.
- **The specimen is the TD3 person, and the two dates print as a passport
  prints them -- `12 AUG 1974`, not `1974-08-12`.**  12.15's clean case needs
  printed fields that agree with the MRZ, or it hands a comparator four
  mismatches on a clean document; and 12.13's normalisation needs a printed
  form that is not already ISO, or it is tested on its own output.  **The two
  fixtures stay separate frames and the test composes them**: neither fixture
  knows about the other beyond the shared person and the shared paper.
- **A field is `name`, `label`, `value` and two boxes -- a label box and a
  value box, never one union box.**  12.11 finds a value by its anchor word and
  takes what is beside it, and 12.8 crops to the region and re-reads it; a
  union box would answer a re-read with the label and the value both, and put
  the anchor text inside the field it located.  `field_of(page, name)` is the
  lookup, because a field is addressed by name everywhere in this part.
- **The value column is placed by the widest label, and nothing about a value
  moves it.**  12.15 alters one printed date and reports a mismatch against
  the region the field was printed in, so an override that reflowed the page
  would move the region it reports and turn one altered field into four.
- **A block that will not fit the page is refused rather than clipped**, on
  Part 4's reasoning: half a printed date reads back as a date that was
  misread, which is a pipeline test failing for a reason of the fixture's
  making.  **A repeated field name and an override naming no field are
  refusals too**, for the same reason in the other direction -- a field is
  addressed by its name, so a page carrying two of them, or an override that
  silently printed nothing, would leave a test asserting against a page nobody
  altered.
- **What the file pins is that the description is true of the frame**: every
  box holds ink and sits inside the page, no ink is printed outside the boxes
  the description names, and no two rows share a row of the page.  **The
  limitation is recorded rather than hidden: no test here reads the page back
  through an engine**, because neither engine is installed and the injected
  stubs of 12.3 to 12.6 answer for a page of their own.

**What this forbids**

- A page type added to `mrz_images`, or a second set of paper/ink levels.
- An ISO printed date in the specimen, or a fifth field no anchor word names.
- One union box per field, a `dict` of fields on the page, or a field addressable
  by anything but its name.
- Clipping a block that does not fit, ignoring an override that names nothing, or
  a rotation/noise/shadow knob on this fixture.

**Consequences.**  12.8 to 12.16 have a frame with a per-field region and a
known ground truth, and 12.12 adds a visa and a national ID by adding two
specimen tables rather than a second generator.  The honest cost is that **this
fixture cannot yet show that any engine reads it**: B4.1's "interface test runs
against a synthetic image" is answered by stubs until Tesseract or EasyOCR is

---

## D88 -- A field is re-read on its own box, and the gate settles it before anything is reported

**Date:** October 2, 2026. **Status:** settled, tasks 12.8, 12.9, 12.10.

**Context.**  `tasks.md` carried 12.8 and 12.9 as done with no code behind
them: `reread.py` held a one-line placeholder and nothing in the package
mentioned a re-read or a confidence threshold.  12.10 cannot be written without
both, because its claim is about what happens *after* a bad read.  Four
questions followed.  What a re-read physically does to the frame.  What the
gate is allowed to spend before it reports.  What "produces no flag" can mean
while 12.15, which is what builds flags from OCR fields, has not been written.
And what the threshold number is, given that the abstract states none.

**Decision.**

- **`re_read_field(image, region, engine)` crops to the field's own
  `value_box`, enlarges 3x, re-thresholds with Otsu, and hands the engine's
  own `OcrResult` back untouched.**  It prepares a frame and does not read,
  score or second-guess the answer, on 12.6's rule that a result is carried
  exactly as the engine reported it.  **The crop goes out as three channels**,
  because 12.2's seam promises every frame an engine is handed is BGR and
  EasyOCR is passed it untouched (`D84`) -- a single-channel image leaving this
  module would break the one engine that cannot convert for itself.  **Otsu
  rather than a fixed cut**, so the threshold is read off this crop's own two
  levels and is not a second place a page's exposure is written down.
- **`OCR_UPSCALE = 3` and `OCR_CONFIDENCE_THRESHOLD = 0.80` are module
  constants, not caller arguments**, on `D82`'s reason that a read carries no
  engine-specific option.  **The threshold is a stated default and not a
  measured figure**: the abstract names no number, says thresholds are chosen
  against a target false-alert rate and versioned, and claims no accuracy.
  Part 27 is what earns a better one.
- **`gate_field` is a branch on `mean_confidence >= OCR_CONFIDENCE_THRESHOLD`
  and this module holds no handler.**  Below the threshold it re-reads once,
  then asks a fallback engine **on the same crop**, and only then reports
  `low_confidence`.  Handing a fallback the whole page would undo the
  enlargement it is being asked for.  The comparison is `>=` at the boundary,
  so the threshold itself is not a re-read.
- **A fallback is asked on purpose, and this is the one place `D85`'s
  non-substitution does not apply.**  `D85` is about *choosing* a read: a
  preference is honoured or the run degrades, and no other engine is tried.
  Repairing a read that came back unsure is a different question, and 4.1 names
  it: "re-read **or a fallback engine** is used before any flag is raised".
- **`FieldRead.low_confidence` is the only thing down this line that owes
  anyone a finding**, and it is the gate's verdict rather than a value any
  caller may recompute -- frozen, and carrying no public method, for the reason
  `EvidenceFlag` is.  **A field the gate resolved owes nothing**, and that is
  the entire content of the abstract's promise.
- **This module holds no finding vocabulary at all**: no `app.risk` import, no
  flag built, and a test that walks its own AST to keep it that way.  Deciding
  what a page means is 12.11 to 12.16's question.  **12.10's "no flag" is
  therefore asserted as two things that can be shown now** -- the gate owes
  nothing and the value it keeps is what the page printed, so neither
  `OCR_MRZ_MISMATCH` nor `OCR_LOW_CONFIDENCE` has anything to fire on -- rather
  than as a count of emitted flags, which would have to wait for 12.15 and would
  then be a test about the comparator rather than about the re-read.
- **A re-read's word boxes are in the crop's own frame and not on the page**,
  and the record says so.  12.14 reports the field's own region, which is what
  a highlight is drawn from; the two are deliberately not interchangeable.

**What this forbids**

- A region grown, shrunk or unioned before cropping -- a box over a field *and*
  its label answers with the anchor word as well (`D87`).
- A fixed threshold, an adaptive-threshold block size that a small field cannot
  satisfy, or a caller-supplied upscale factor.
- Wrapping a read in a handler here, the way 12.6's degrade is a branch rather
  than a catch (`D86`).
- Importing `app.risk` from this module, or naming an `EvidenceFlag` here.
- A crop handed to a fallback engine, or a fallback tried before the re-read.

**Consequences.**  12.10's anti-false-alarm test now has something to assert
against, and 12.11 to 12.16 inherit a gate that has already settled what to do
with an unsure field.  The costs are honest: **no engine on this box has read
any of it** -- the stubs answer by the shape they are handed, which is what
makes the tests mean the same thing with and without Tesseract -- and **12.15
must consume the gated read rather than the page read**, or the guarantee

---

## D89 — A printed label finds its field, and a value its own pattern cannot read is still a value

**Date:** October 2, 2026. **Status:** settled, task 12.11.

**Context.**  `D87` gave Tier 1 a page with a label box and a value box per
field, and said why they are never one box, and 12.11 is the first task to
consume a read off a whole page rather than a crop.  That put four questions.
What a field is, and what extracting one answers.  What happens to a value that
does not look like the field it sits beside.  How a label is found among words
an engine returns in whatever order it likes, and how far "beside it" reaches.
And what an unreadable field answers, against what 12.15 needs to be able to
compare.

**Decision.**

- **A module, `app/pipeline/tier1/fields.py`, beside `reread.py`.**  It holds
  :class:`FieldRule` -- a field's name, the label spellings that locate it and
  the pattern its value matches -- and :data:`FIELD_TABLES`, one tuple of rules
  per document type behind a mapping proxy, with :data:`DOCUMENT_TYPES` spelled
  out beside it rather than read off its keys, as 12.5's registry does.  **One
  function, `extract_fields(read, document_type)`,** taking the
  :class:`~app.pipeline.tier1.ocr.OcrResult` :func:`~app.pipeline.tier1.runner.run_tier1`
  returns and answering a frozen :class:`ExtractedFields` carrying an entry
  for **every** field the table names.
- **A value its own pattern cannot read is answered whole.**  The pattern says
  which part of the text beside the label is the value and trims to it; where
  it matches nothing, the whole of that text is the answer.  **Dropping it
  instead would leave 12.15 with nothing to disagree with**, and a forged value
  is often malformed -- that is precisely the case the comparator exists to
  catch, and a table that discarded it would be a false-negative generator.
  Absence stays ``None`` for the one case that really is absence: a label the
  page never printed, or printed with nothing beside it.
- **Rows are rebuilt from the boxes, and the value is what lies to the right of
  the anchor on that row.**  Words are grouped by vertical overlap and sorted
  left to right, because nothing in :class:`OcrResult` promises reading order
  and one that did would be a second promise to keep.  **An anchor run may not
  bridge a gap wider than :data:`ANCHOR_ADJACENCY` times the words' own
  height** (1.0): a label is one run of words separated by a space's width,
  while the value column is a form's own gap away, so the two are told apart by
  geometry rather than by a pixel gap another page's size would move.  That
  constant and not a caller argument, on ``D88``'s reason that one read carries
  no option.
- **Labels are compared with case, spacing and edge punctuation set aside.**
  An engine's own spelling of a label is not a second label to fail on, and
  "Passport No." and "Passport  No" are the one anchor the table lists.
- **An unknown document type is a refusal, `UnknownDocumentError`.**  On 12.5's
  reasoning: every name in :data:`DOCUMENT_TYPES` has a table, so answering
  ``None`` for a misspelling would hand 12.15 four absent fields on every
  document and say nothing about which type was asked for.
- **No finding vocabulary and no log line.**  What a disagreement means is
  12.15's question, and a field nothing could read is ``None`` rather than a
  finding; the module imports neither :mod:`app.risk` nor :mod:`logging`, so a
  printed value cannot reach one from here.

**What this forbids**

- A value dropped for matching no pattern, or a field answered ``""``.
- Reading the whole row the label shares rather than what lies beside the
  anchor, and a label run that bridges two printed blocks.
- A gap in pixels rather than one relative to the words' own height.
- Trusting the order an engine returned its words in.
- An unknown document type answering ``None``, or falling back to the passport.
- A mutable table, or one a caller may add a document type to.

**Consequences.**  12.12 adds two specimen tables and two names in
:data:`DOCUMENT_TYPES`, not a second mechanism, and its tests are the anchor
round-trip this one already has.  12.13 normalises the values answered whole
above, and 12.14 reports the region each came from -- a region this module
deliberately does not carry, because a word box off a re-read is in the crop's
frame and not the page's (``D88``).  The honest cost is unchanged from ``D87``:
**no engine on this box has read any of this**, and the read the tests consume
is a stub over ground truth that walks the drawing's own glyph advances, with

---

## D90 — A document type is a table, and a number's band is a value read whole or not at all

**Date:** October 2, 2026. **Status:** settled, task 12.12.

**Context.**  `D89` settled the shape of one document type's table and left
12.12 two more: a visa and a national identity card, both named in the problem
statement's Module 1 inputs and neither in `D89`'s one table.  That put three
questions.  Whether the two new types are a second mechanism or two more rows
in the first.  Which fields each names, given the passport table holds four
and the problem statement lists six for a passport, four for a visa and none
for an ID card.  And whether a number's width is a property of the pattern or
of the document.

**Decision.**

- **Two more tables and no second mechanism.**  `VISA_FIELDS` and
  `NATIONAL_ID_FIELDS` are tuples of the same :class:`FieldRule` in the same
  :data:`FIELD_TABLES`, with `VISA` and `NATIONAL_ID` added to
  :data:`DOCUMENT_TYPES` beside `PASSPORT`.  Same `extract_fields`, same
  :class:`ExtractedFields`, same refusal for a name no table holds.  A fourth
  document type is a fourth tuple, and the tests hold each one to a page it can
  actually be read from.
- **Each new table names four fields, and the four are the passport's four
  with the number's own name.**  `name`, `date_of_birth`, `date_of_expiry` and
  the document's own number -- `visa_number`, `national_id_number`.  **Not the
  problem statement's wider list**: a visa's MRZ is a TD2 and an ID card's is a
  TD1, and 12.15 compares each printed field with the MRZ field it must agree
  with, so a field no MRZ carries has nothing to be compared against and a
  table listing one is a claim no test downstream can keep.  `D89` already
  chose the same four for a passport against a six-field list, and this holds
  that choice rather than reopening it.  Adding a field is a table edit once
  the MRZ work that can check it exists.
- **A number's band belongs to the document, and a band is bounded at both
  ends.**  An ICAO travel document's number is at most nine characters; an
  identity card's number is not bound by ICAO at all, so
  `_NATIONAL_ID_NUMBER` is its own pattern on a wider band rather than the
  passport's.  **Both word boundaries are load-bearing**: `\b[A-Z0-9]{6,9}\b`
  means a run of the same characters longer than the band matches *nothing*,
  and `D89`'s rule then answers the whole of it.  Without them a twenty-digit
  run is answered as its first nine, which is a number the document never
  printed -- the one outcome 12.15 exists to catch, manufactured by the
  comparator's own input.
- **The tests are 12.11's two, over two new pages.**  The anchor round-trip and
  the print-order hold, per table, plus each page read back whole and each
  number field named by exactly one table.  Pages are drawn by
  `document_images.draw_document` from rows the test file states: the fixture
  prints one document, and 12.12 adds two tables rather than a second specimen.

**What this forbids**

- A visa or an ID card read by a different code path, a fallback to the
  passport, or a table assembled from another's rules at run time.
- A field in a table that no MRZ for that format carries.
- One band shared by two document types whose numbers are bounded differently,
  and an unbounded band inside any band.

**Consequences.**  12.13 normalises the values these tables answer, and 12.14
reports the region each came from.  A document type with no table is still
`UnknownDocumentError` rather than four absent fields, and there are now three
names in that message instead of one.  The honest cost is `D87`'s, unchanged:
**no engine on this box has read any of this**, and all three tables are
exercised through a stub over ground truth.  A real visa or ID card page will
print labels none of these three tables lists, and the first such page is
likely to find an anchor here that is wrong -- which is what the anchor

---

## D91 — A value is normalised by the type its own rule names, and one that cannot be read is handed back whole

**Date:** October 2, 2026. **Status:** settled, task 12.13.

**Context.**  `D90` left three tables answering a printed value as it was read,
and 12.13 names the shape: dates to ISO, names uppercased and transliterated,
numbers stripped of spaces.  That put four questions.  What a normaliser keys
on.  Whether it is a step inside `extract_fields` or a separate call.  What it
does with a value no pattern could read — which by `D89` is *most* of what
it is handed.  And what happens to a value it cannot turn into the shape it
wants.

**Decision.**

- **The type is the key, and it is the field\\'s type rather than the
  document\\'s.**  `FieldRule` gains a required `value_type` naming one of
  `DATE`, `NAME`, `NUMBER`, and `NORMALISERS` maps those three to three
  functions.  A name is a name on all three tables, so keying on the document
  would make a fourth table a fourth normaliser and would put "which table is
  in play" ahead of "what does this value say".  **`value_type` is required and
  not defaulted**, so a field added to a table cannot reach 12.15 unnormalised
  by leaving it out; a name outside the three is `UnknownFieldTypeError`, on
  `D89`\\'s reason that a misspelling is a refusal and not a shrug — including
  a value type that is not a string at all, which would otherwise raise
  `TypeError` out of the membership test.
- **A separate call, not a step inside `extract_fields`.**  12.11 answers what
  the page printed, and a value no pattern could read is the one 12.15 most
  needs; folding the two together would hide a forgery in the record 12.14
  points a region at.  `normalise_value` is the primitive and `normalise_fields`
  the one walk over the document type\\'s own table — which is what makes all
  three types cost one entry rather than one per table.
- **Nothing is invented, and what cannot be read is handed back whole.**  A
  date carrying an unknown month, an impossible day, a two-digit year or a
  numeric order is carried through unchanged: each is a decision the page does
  not carry, and a 31st of February rolled into March is a forgery this project
  would have manufactured itself.  A number whose joined form misses **its own
  band** is carried through whole, on 12.11\\'s rule that a value the pattern
  cannot read is still a value.
- **The band is the only judge of a number, and the normaliser removes
  whitespace and nothing else.**  `NOT A NUMBER` beside `ID No` becomes
  `NOTANUMBER`, because `\\b[A-Z0-9]{6,14}\\b` holds it and any content rule
  beyond the band would answer the same value two ways depending on the words
  in it.  12.15 disagrees with it either way, and the disagreement is the
  finding.  A test pins that every printed character survives, in order, so the
  claim is checkable rather than asserted.
- **The month table is `calendar`\\'s, not twelve remembered values**, on 1.6\\'s
  rule, and a test holds it at exactly twelve so a locale that renamed one
  fails loudly instead of answering a date no document carries.
- **Transliteration is borrowed, not copied.**  `_normalise_name` hands the
  printed run to `tier0.td3.transliterate_names` as a surname — 2.8\\'s rule
  that a space is not a separator, so it is not split and no given names are
  invented beside it — and a test asserts `fields.py` holds neither
  `TRANSLITERATIONS` nor `unicodedata`.
- **The date pattern is grouped, not duplicated.**  `_DAY_MONTH_YEAR` gains
  three capture groups so the normaliser reads its components off the pattern
  the table matched on.  `group(0)` is unchanged, so 12.11\\'s answers are
  byte-for-byte what they were.

**What this forbids**

- A normaliser keyed on the document type, a second normalising pass inside
  `extract_fields`, and a fourth table that needs a fourth normaliser.
- Rolling a date forward, numbering an unknown month, giving a two-digit year
  a century, or reading `12/08/1974` day-first.
- Joining a number whose compacted form misses its own band, or removing a
  character the band does not admit.
- A second copy of the ICAO transliteration map, or of the combining-mark rule.

**Consequences.**  12.15 compares a shaped value against the MRZ and holds
both sides.  12.14 reports a region beside a value that is no longer the
string the page printed, so the record has to carry the printed form as well as
the shaped one — which is why `normalise_fields` returns a new record rather
than editing the one it was given.  12.16 has less to absorb, since spacing and
diacritics are both gone before it runs.  The honest cost is `D87`\\'s,
unchanged: **no engine on this box has read any of this**, so a month printed
as `AUG.` with its own full stop, or a label row where the value is the whole

---

## D92 — A field is located by the words its own value was read from, and an absent region is a claim

**Date:** October 2, 2026. **Status:** settled, task 12.14.

**Context.**  12.14 names the region a field came from, and `D89` left none in
the record, so `FieldRule` had nothing to read one out of and 12.15 had nothing
to hang a finding on.  That put four questions.  What a region — a word's box,
the page's box, or a flag's polygon.  Which words it covers when a value is
only part of a printed row.  What it says where there is no value to point at.
And what it says where a page prints one field on two rows.

**Decision.**

- **The region is the four corners of the words that field's value was read
  from**, clockwise from the top left.  That is the shape a flag's ``region``
  already carries, so 12.15 hands a finding one instead of re-expressing it,
  and it is a box 12.8's gate could crop if a later step wants that.  **Plain
  ``int``**, as ``MrzComponent`` converts to, so a region can go into a JSON
  body where a ``numpy.int32`` cannot.
- **The words are the value's own, which is what the trimming rule had already
  decided.**  ``_beside`` trimmed the match to its own extent so trailing text
  another field printed on the same row is not read as part of the value; the
  region follows that same extent, so the value and the region cannot describe
  different ink.  ``_beside`` is now ``_printed_words`` and answers the words
  as well as the text.
- **``None`` is the answer where there is no value**, on 23.6's reason: a
  finding with nowhere to point is still a finding and is listed rather than
  dropped.  A blank row, a field no anchor was printed for, and a page no
  engine could read are all ``None`` — not an empty box, and not an error.
- **``regions`` is required and not defaulted**, on ``D91``'s reason: a field
  whose region a record does not carry is a field 12.15 has nowhere to point,
  and the slot left out is the same gap.
- **Normalising moves nothing.**  ``normalise_fields`` carries the regions of
  the record it was given, and the printed value stays in the record that call
  was handed — ``D91``'s consequence, paid rather than deferred.
- **The frame is the page's, and the crop is not imported.**  12.8's re-read
  boxes are in that crop's own coordinates, so this module takes no import of
  ``reread`` and a test holds it there.
- **A field printed on two rows is the first row's, value and region together.**
  The value has always been the first row's; a region beside the second row's
  ink would point at something the record does not claim.
- **A word beside the anchor that carries no ink is not in the region.**  The
  match is found in the stripped row and the word spans are counted in the raw
  one, and the offset between them is applied rather than assumed away.

**What this forbids**

- A region covering the label, the whole row, or the page.
- A region in a crop's frame, and one invented where the page printed no value.
- A region that widens or clips a measured box.
- Leaving the slot out, so that a field can be added to a table without one.

**Consequences.**  12.15 writes ``EvidenceFlag(region=...)`` with no geometry
of its own, and 23.6's list shows a field it cannot locate rather than omitting
it.  The two halves of 12.11's answer stay on hand — ``extracted`` carries
what the page printed, ``normalise_fields`` carries what it was shaped into,
and both carry the same corners.  The honest cost is ``D87``'s, unchanged:
**no engine on this box has read any of this**, so every region here is the
stub's per-word layout over ground truth, and a real engine whose word boxes
are tighter or looser than the ink would move a region's edge with it.

---

## D93 — A printed field is compared with the zone beside it, and the two halves a finding carries

**Date:** October 2, 2026. **Status:** settled, task 12.15.

**Context.**  `D92` gave every extracted field a region, `D91` gave every value a
shape, and `D88` gave every uncertain field a re-read.  12.15 is the first thing
in Tier 1 that turns any of that into a finding, and it is the first module in
the tier to import `app.risk`.  That put six questions.  Which printed field is
compared with which MRZ field, given that a visa's number and an identity
card's are both the zone's `document_number`.  Which century a printed `1974`
and a zone's `74` are in.  What `tolerance` reaches, and what it must not.  What
a zone that does not carry a field at all means.  And what `expected` and
`found` may hold, given that they are where a disagreement is written down.

**Decision.**

- **A module, `app/pipeline/tier1/mismatch.py`, beside `fields.py` and
  `reread.py`, holding one function.**  `compare_to_mrz(ocr_fields,
  mrz_document, tolerance)` walks the document type's own field table and answers
  a tuple of `EvidenceFlag` in the table's printed order, one per field that
  disagrees.  **It takes an `ExtractedFields` and not an `OcrResult`**, which is
  how `D88`'s promise is kept: a caller hands it the record built from the
  *gated* read, and the comparator cannot be given the page read by accident.
- **The field-to-field mapping is a named table, `MRZ_FIELDS`, and a field it
  does not name is a refusal.**  The three document types name three different
  numbers and the zone calls all three `document_number`; a name is the zone's
  `surname` and `given_names` together.  **Checked before anything is
  emitted**, so a fourth table cannot produce a partial answer, and a test holds
  every field of every table against it.
- **The zone's side is shaped too, and the filler is the only edit made to it.**
  A TD3 prints its document number padded to nine places (`L898902C<`), so a
  comparison that kept the filler would disagree with every genuine passport.
  Both sides therefore go out as upper-case words with the filler set aside.
- **A date is compared on the two year digits the zone prints, and no century is
  invented.**  `1974-08-12` and `740812` agree; `1874-08-12` agrees with them
  too, because the zone carries no century to disagree with.  3.12 left the
  century open on purpose and `mrz.infer_birth_year` is what closes it — a
  comparator that guessed one would be inventing the forgery it then reports.
- **`tolerance` is a count of name *words*, required and not defaulted, and it
  reaches a name and nothing else.**  Two names are compared as the shortest run
  of word substitutions turning one into the other, so a diacritic 12.13 already
  took off and a run of spaces cost neither of them anything.  **A date and a
  number are exact or are not**: a digit is a digit, and a tolerance that bought
  a date one day out would buy a forgery one day out.
- **Two absences are not disagreements.**  A field the page printed nothing for
  is `None` and is compared with nothing, on 12.10's ground that 4.1's promise
  is about misreads; and a zone record carrying none of a field's halves — a
  TD1's name sits on line 3, which 3.7 has not read — is a capability gap, and
  flagging every identity card would be the false alarm this project exists to
  avoid.
- **A name's `expected` and `found` are counts of words, and the other two
  types carry the two values.**  `D6` and `EvidenceFlag`'s own rule are that a
  flag never carries a line of printed text so that a flag cannot become a place
  identity data is stored, and a holder's name is the one value here that is
  identity data.  So a name mismatch reads `expected="3 name words"`,
  `found="2 agree"`, `field="name"`, and a region over the printed name — an
  officer judges it off the two images, which is what the region is for.  **The
  cost is honest**: a name finding says *how far* the two disagree and never
  *which word*, where a date finding says exactly which day.
- **The region is 12.14's, handed over untouched, and this module holds no
  geometry.**  No `cv2`, no `bbox`, no corner of its own.
- **`value` and `confidence` are both 1.0, because both sides were read and
  12.9's gate already settled how sure they were.**  A structural disagreement
  between two readings of the same page is not a measurement to be hedged.
- **One id for every field.**  `flag_ids.OCR_MRZ_MISMATCH` is what `flag_ids.py`
  promised 12.15, and which field is about is `field` (`D17`), not a second id.

**What this forbids**

- A second id per field, a field name reaching an id, or a comparator holding
  its own weight.
- Comparing a printed value with a raw one, or a date that assumes a century.
- A tolerance that reaches a digit, and a default the caller never states.
- A finding for a field the page printed nothing for, or for one the zone does
  not carry.
- A holder's name in `expected`, `found`, `label` or `reason`.
- Geometry of its own, and any import of `cv2`.

**Consequences.**  12.16 has less to absorb than it would have: diacritics and
spacing are both gone before it runs, and the tests here already hold a diacritic
and a hyphenated word within tolerance.  **12.10's "no flag" can now be asserted
as a count** as well as the two structural claims `D88` settled it with.
`Tier1Result` still has no `flags` field for `R1` to be summed from — 12.15
writes the first finding and the record that carries it is still the next task.
The honest cost is `D87`'s, unchanged: **no engine on this box has read any of
this**, so every disagreement below is between two readings of a page a fixture
drew, and a real engine's misreads will reach this comparator far more often
than a forgery's will.

---

## D94 — A barcode is a second reading of the page, and it is compared with the page and not with the zone

**Date:** October 2, 2026. **Status:** settled, task 13.3.

**Context.**  `D93` settled how a printed field is compared with the machine-
readable zone beside it.  13.3 asks the same question of a second machine-
readable thing: a 2D barcode, which on an ePassport carries the very same TD3
zone in a form a phone camera can read off the same paper.  That puts four
questions.  What the payload is read *as*, when the standard says what a TD3
zone looks like but says nothing about what a QR on a border document
happens to encode.  Which printed fields it is compared against at all.  What a
payload this cannot parse means — and the answer that is easy to get wrong
here is to call it a mismatch, which would flag every genuine document whose
barcode carries something this build does not recognise.  And whether the
comparison belongs in `mismatch.py`, which is named for one.

**Decision.**

- **`compare_to_barcode(ocr_fields, payload)` sits beside `compare_to_mrz` in
  the same module, and takes the record and a string.**  Two readings of one
  page disagreeing is one subject, and the record, the region, the band, the
  `source_module` and the flag shape are all `D93`'s.  **The payload is text,
  not a `DecodedBarcode`**: the decoder's job ends at handing over the payload,
  and a comparator that took its own frame would decode a second time.
- **The payload is read as a TD3 zone, through `td3.validate_td3_lines` and
  `td3.td3_field`.**  `BARCODE_FIELDS` names the printed field and the TD3
  line-2 field each is read from, exactly as `MRZ_FIELDS` does, and the three
  document numbers map to the zone's one `document_number` for the same reason.
  **The payload's own edges are stripped before it is split into lines**,
  because a scanner hands back a trailing newline and a padded zone is read
  rather than called unreadable.
- **`name` is not in `BARCODE_FIELDS`, and that absence is the claim.**  A TD3
  payload carries no name to disagree with, so there is nothing to compare and
  nothing to say.  This is the one place the two tables differ, and a test says
  so, because a table that grew a name later would be comparing a value that is
  not in the payload.
- **A payload that is not a TD3 zone is an absence, not a disagreement.**  It
  answers `()`, and the reason is not politeness: naming what a payload we
  cannot parse disagrees with would be inventing the other half of the
  comparison and then reporting it.  **This is a known blind spot and not a
  safe default** — a forged document whose barcode carries a payload this build
  does not recognise gets no finding from this rule, and the flag for that is
  not in `flag_ids.py` yet.
- **A date and a number are exact or are not, and no tolerance parameter
  exists.**  `_agrees` is now `_exact_agrees` plus a name half: 13.3 calls the
  exact half, so the two functions cannot hold two answers to the same question.
  The century question `D93` settled is untouched — a payload printing `74` has
  no century to disagree with either.
- **`expected` is the payload's value and `found` is the printed one, and the
  region is the printed field's.**  The officer reads two values and one box,
  and the box is on the page rather than on the barcode, because the printed
  side is the one 12.14 located and the barcode's corners belong to 13.3's
  caller.
- **The band is `review`, not `high`, and that is `v1.yaml`'s own word.**
  `BARCODE_MISMATCH_BAND` exists so a test can hold the code to the weightset
  the way 12.15's is held.  **Both of this finding's readings come off one
  image, so either can be the wrong one** — which is also why `value` and
  `confidence` are 1.0 (both sides were read) while the *weight* stays low.
- **One id, `flag_ids.OCR_BARCODE_MISMATCH`, under the `OCR_` prefix** the flag
  registry already recorded for this rule rather than a ninth family.
- **The payload's own check digits are not re-verified here.**  A payload whose
  check digit is wrong is a `MRZ_*_CHECK_DIGIT_MISMATCH` finding when Tier 0
  reads the same text as a zone, not a second finding from here.

**What this forbids**

- Comparing a printed value with a payload that does not carry it, and a name
  against a TD3 payload.
- A finding for a payload this cannot parse, and a tolerance that reaches a
  digit.
- Decoding inside the comparator, and geometry of its own.
- `expected` and `found` carrying anything but the two compared values, and any
  part of line 1 — which is where the holder's name is — reaching either.

**Consequences.**  13.3 is the third reading of the page and the first that can
disagree with `D93`'s: the test that moves a field inside the payload while the
zone keeps it, and asserts 13.3 answers `()` where 12.15 answers a finding, is
what makes the pair independent rather than one a restatement of the other.
**The blind spot above is the thing to reopen first**, along with
`Tier1Result` still having no `flags` field for `R1` to be summed from — 13.3
writes the second kind of finding and the record that carries both is still
next.  Nothing here has read a real document either: the QR is drawn by the same
library that decodes it, and the printed side comes from a fixture.

---

## D95 -- A template is a reference image and a rectangle per field, and no name in it is looked up in Python

**Date:** October 2, 2026. **Status:** settled, task 13.4.

**Context.**  13.4 asks what a template *is*, and every later layout question --
13.6's corners, 13.7's homography, 13.8's tolerances, 13.9's deviation -- is
measured against whatever this settles.  There are four ways it could have been
defined wrongly.  Rectangles in absolute pixels on one capture, which locate
nothing on a page of any other size.  A reference size written into the JSON
beside the image, which is a second copy of a fact the image already carries and
can disagree with it unnoticed.  A shape validated against this project's own
document-type and field registries, which would make a new document type a
Python change -- exactly what 13.5 exists to deny.  And a loader that answers an
empty template when a file is missing, which reads as a layout with no fields on
it rather than as a fault.

**Decision.**

- **A template is one JSON file naming a document type, a reference image and a
  rectangle per field, held in a package of its own.**  `app/pipeline/tier1/
  templates/` holds `passport_td3.json` and `passport_td3.png` and is read as a
  package resource through `importlib.resources` -- `app.risk.weightsets` under
  `D15` is the precedent -- so `loader.load_template(name)` is the one way in
  and a caller holds a `Template` and never a path.
- **A rectangle is written as `x`, `y`, `width`, `height` and answered as four
  corners.**  The JSON form is what a person measures off a reference image
  with; `FieldRect.corners` answers them clockwise from the top left, the order
  `app.risk.flags.EvidenceFlag.region` already uses, so 13.9 hangs a finding on
  a template's rectangle without re-expressing it.
- **The frame is read off the reference image, not written beside it.**
  `Template.reference_size` comes from opening the image -- as a stream, so the
  read survives the package being a zip -- and a rectangle falling outside that
  frame raises.  A rectangle off the page locates nothing, and keeping it would
  hand 13.9 a position no page can occupy.
- **No name is looked up in Python.**  `document_type` is answered as the string
  the file carries and a field name is held only to being non-empty.
  `fields.DOCUMENT_TYPES` is 12.12's registry, and checking it here is precisely
  what would make a new document type a Python change; a test holds the one
  committed template's type against it instead, which puts the check on the file
  that shipped rather than on every file written after it.
- **Every key the loader reads is required, and a key it does not read is
  ignored.**  13.8 puts a per-field tolerance in these very rows, and a loader
  that refused a key it had not heard of would make that a loader change.  A
  misspelt key the loader *does* read is caught by that key's own absence.
- **Nothing is defaulted, and a file that cannot be read raises
  `TemplateError`.**  Absent JSON, unreadable JSON, a non-mapping top level, no
  document type, no reference image, a reference that is absent or is not an
  image, no fields at all, a field that is not four whole pixels (a `bool` is
  not one), a rectangle with no area or one running off the frame, a field named
  nothing: each raises, and every message names the file and the field and never
  a row's contents.
- **A key the file names twice raises.**  `json.loads` keeps the last of a
  repeated key and says nothing, so a rectangle an author wrote twice would be
  dropped without a word, and a hand-written data file is exactly where that
  happens.
- **There is no default template name**, because nothing has chosen the layout
  Tier 1 should reach for and a default would be that choice made on the
  loader's behalf.
- **The MRZ is not in a template.**  Tier 0 locates the zone by detecting it
  (`mrz_region.detect_mrz`), so a rectangle naming the zone here would be a
  second answer to a question one module already answers.
- **The committed rectangles were measured, not invented.**  They are the boxes
  `tests/fixtures/document_images.py` printed those four fields at, with four
  pixels of slack, over a 1000x700 blank page carrying that fixture's own
  labels.  `photo` is the one rectangle the four `PASSPORT_FIELDS` do not name,
  and 13.14 is what will read it.

**What this forbids**

- Declaring the reference size in the JSON, or looking a document type or a field
  name up in a Python table from inside the loader.
- Answering a template with no field, a defaulted document type, a rectangle off
  its own reference image, or a repeated key silently collapsed.
- Anchoring a layout to one capture's absolute pixels, and naming the MRZ in a
  template at all.

**Consequences.**  13.5's claim -- a new document type is a new JSON file and no
Python change -- rests on the loader holding no registry, no default and no
per-type code, which is why those three absences are the decision rather than
incidents.  **The reference image is a blank form with its labels on it**: a
layout, not a specimen, and nothing here has put a photographed document into
template space -- 13.6 and 13.7 are the first tasks that will.  One template
ships, a passport; the visa and national-ID layouts 12.12 names have none, and
13.5 is what a second one looks like.

---

## D96 -- Tier 1 asks the quality checker where the document is, and reads no pixels of its own

**Date:** October 2, 2026. **Status:** settled, task 13.6.

**Context.**  13.6 is the first of the layout tasks, and every one of 13.7
through 13.11 is measured against whatever it settles.  There are two ways it
could have been done wrongly.  **A corner detector written inside Tier 1**,
which is what the task's own wording invites, and this repository already owns
one -- `app/quality_checker/m8_coverage.find_card`, byte for byte identical in
five modules, `m4_uniformity`, `m5_glare`, `m6_ppi`, `m7_skew` and `m8_coverage`
itself, none of them tested and none of them named in any decision.  A sixth
copy would be a second answer to a question five answers already give, free to
disagree on exactly the off-axis photographs where the answer decides whether
the layout can be measured at all.  And **a detector that answers a rectangle
as though it were a quadrilateral**, which is what the one already in the tree
does when it cannot simplify an outline to four corners: it returns the
rectangle that best fits the contour, which is a guess about a page rather
than a measurement of one.

**Decision.**

- **Tier 1's corner search is `m8_coverage.find_card`, called rather than
  copied.**  `corners.detect_corners(image)` is the seam.  This follows
  `mrz_region.deskew`, which calls `m7_skew.text_skew` for the same reason;
  `m7_skew`'s copy of `find_card` being a copy is a defect this decision
  records rather than one it fixes.
- **The reuse is checkable rather than asserted.**  A test replaces
  `find_card` with a stub and is handed a string in place of an image, so the
  corners must follow the stub and Tier 1 must never have opened the frame
  itself; a second search written beside it fails that test instead of quietly
  agreeing.  A second test holds `order_corners` to the checker's own ordering
  the same way.
- **The ordering is one function, not one per caller.**  `m8_coverage._order`
  is renamed `order_card_corners` and is the sort every corner set in this
  repository goes through.  `corners.order_corners(points)` refuses anything
  that is not exactly four points rather than reshaping it into four.
- **The corners are whole pixels, clockwise from the top left, and each is the
  nearest pixel rather than the one truncated towards zero.**  That is the
  order `EvidenceFlag.region` and `FieldRect.corners` are both written in, so
  a detected corner and a template rectangle are one shape and 13.9 can hang a
  finding on either.  A corner left of the frame is exactly where truncating
  and rounding part company, so a test pins it.
- **A frame holding no document is answered `:data:`NO_CORNERS`, not raised.**
  `()` is the whole answer, on `mrz_region.detect_mrz`'s reason that a page
  which is not a document is an ordinary outcome, and on `barcode.NO_BARCODES`'
  reason that one empty value should not be spelled two ways.
- **An outline that was not a quadrilateral is `NO_CORNERS`.**  Only
  `find_card`'s own `"quad"` answer is read; its fitted-rectangle answer is a
  guess, and 13.7's homography off a guess would straighten a document nobody
  has found.

**What this forbids**

- A second corner search under `app/pipeline/`, and a second ordering sort.
- Reading `find_card`'s fitted rectangle as if it were the document's corners.
- Answering detected corners as floats, as a truncated pixel, or in an order of
  this module's own.

**Consequences.**  The synthetic specimen is a real one -- the printed page
laid at a known quadrilateral and photographed on a background below its paper
-- because the four corners have to be ground truth rather than a re-reading of
whatever the detector produced; 13.7 warps the same capture, so
`tests/fixtures/document_images.photograph` is where that page is built.

---

## D97 -- Template space is the reference frame's own four corners, and a page that is not there is answered

**Date:** October 2, 2026. **Status:** settled, task 13.7.

**Context.**  13.7 is the second of the layout tasks, and 13.8 through 13.11 are
all measured in whatever space it settles.  Three things had to be answered.
**What "template space" is.**  A template carries a reference image and a
rectangle per field, and no page outline -- the file has no key for one, and
`loader.Template` keeps no bitmap.  So the frame the rectangles were measured
on has to become the target, and inventing a second frame beside it would give
13.9 two coordinates to convert between.  **What the search is.**  13.6 settled
that the corner search is `m8_coverage.find_card`; 13.7 could call
`detect_corners` itself or take corners, and doing both would let the two
halves disagree about where the page is.  **What happens when there is no
page.**  13.6 answers `NO_CORNERS` rather than raising, and 13.7 has to answer
in the same shape or a caller has to catch one and test the other.

**Decision.**

- **Template space is the reference frame's own four corners**, `(0, 0)`
  through `(width, height)`, clockwise from the top left --
  `align.template_corners(template)`.  Not a field rectangle, and not a
  constant written beside the template: `FieldRect.corners` already measures
  against that frame, so a field read in template space is already in the
  coordinates its rectangle is written in.
- **`align.warp_to_template(image, template, corners)` takes the corners and
  detects nothing.**  `detect_corners` is the seam 13.6 settled, and the warp is
  the mechanical half of the same question.  A caller holding corners -- from a
  stub, or from a capture it has already searched -- does not pay for a second
  search, and this module cannot open a frame of its own.
- **The matrix is public.**  `align.homography` returns the 3x3 rather than
  keeping it, because a field box found in template space has to be carried
  back to capture pixels for `EvidenceFlag.region`, which is written in capture
  coordinates.
- **A capture with no page in it is answered `NO_WARP`, which is `None`.**  Not
  a raise, and not an empty frame: an image of nothing would be a picture and
  not a refusal.  13.6's reason -- a page that is not a document is an ordinary
  outcome -- is 13.7's.
- **Four points enclosing no area are refused as well.**  This is the one place
  OpenCV does not refuse for us: `cv2.getPerspectiveTransform` handed four
  collinear points returns a near-zero matrix without raising, and
  `warpPerspective` then writes whatever that matrix implies without a word.
  That is 13.6's "a fitted rectangle is a guess, not a page" applied to a
  different failure, and the guard is `cv2.contourArea(...) <= 0`.
- **A wrong corner count raises, and says how many it got.**  Not the
  `ValueError` numpy's own reshape would raise: the caller passed three points
  and should be told three.

**Consequences.**  **The test lays the committed template down rather than the
printed specimen.**  `tests/fixtures/document_images.lay` is the new seam -- it
takes a bare frame where `photograph` takes a printed page, and `photograph` is
now `lay` given a page's own frame -- so the capture under test is the one
artefact 13.9 will measure against and "close to the template" is a comparison
with that file rather than with a second drawing of it.

The page is laid down turned 7 degrees about its own centre and photographed on
a background below its paper, and the limits the test holds are a mean
difference below 8 grey levels with over 96% of the frame within 40.  **What
they reject, measured:** a capture left where it was (mean 61), one
straightened off a reversed corner order (21), one off a mirrored one (19), and
one built off corners 10 pixels off the page's own (9.3).  **What the correct
warp measures is 4.4 to 4.7** across tilts of 5, 7 and 9 degrees either way.

**Two things this task does not claim.**  **The resampling filter is named but
not pinned.**  `align.INTERPOLATION` is `cv2.INTER_LINEAR`, and a mutant
setting it to `INTER_NEAREST` still passes every test, because on a capture
this close to 1:1 both filters land inside the same limits; a future session
changing it would not be caught.  **IoU of the ink mask is deliberately not the
test's measure.**  The detector's corners are 4 to 5 pixels off the page's own
on this capture, which on thin glyphs is the difference between an IoU of 0.98
for the exact quadrilateral and 0.32 for the warp this task actually builds --
so an IoU assertion would be a test of `find_card`'s accuracy wearing a warp's

---

## D98 -- A tolerance lives in its own field's row, and the loader reads none of it yet

**Date:** October 2, 2026. **Status:** settled, task 13.8.

**Context.**  13.8 asks what a template records about where a printed field may
sit rather than where it does sit, and three things had to be answered before a
number could be written down.  **Whether a tolerance is one value per document
or one per field.**  A single document-wide figure would be a fourth key beside
`document_type`, and 13.9 hangs its finding on one field's region -- so the
allowance that decides a flag would belong to the page rather than to the field
the flag names.  **Whether it is one number or three.**  The task names
position, size and rotation, and those fail apart from one another: a field
printed in the right place at the wrong angle is a different fault from one
printed small, and a single figure wide enough for the second would excuse the
first on every field at once.  **Whether the loader reads it.**  `D95` settled
that a key the loader does not read is ignored, and wrote 13.8's tolerance into
that decision on purpose; reading it here would be a loader change 13.8 did not
ask for, and it would move the parse in front of the question 13.9 has not
answered -- what a displacement is measured against, and whether a size is a
ratio or a pixel count.

**Decision.**

- **A tolerance is written in the field's own row, as `position`, `size` and
  `rotation`.**  Per field and not per document, three numbers and not one, for
  the two reasons above.
- **Position and size are pixels of the reference frame; rotation is degrees.**
  `D97` settled that template space is that frame's own four corners, so a
  pixel in this file is a pixel 13.9 measures in, with no second conversion
  and no scale factor to agree about.
- **The committed passport's five fields carry `position: 12`, `size: 8`,
  `rotation: 2.0`.**  Position is chosen against the detector rather than by
  taste: `find_card`'s corners land 4 to 5 pixels off the page's own on the
  1000x700 reference (`D96`), and that error reaches template space as every
  field's displacement.  Twelve is more than double it, so a correctly
  photographed document does not read as displaced.
- **The loader reads none of it and `FieldRect` carries no tolerance.**
  `D95`'s decision, kept because 13.8 is a data task and 13.9 is the task that
  knows what the numbers are for.  The cost is real and is paid for below.
- **A test reads the template files by path and covers every field of every
  file that shipped**, not the passport alone, and holds each to a positive
  finite number and to a position wider than the detector's own error.  This is
  the same move `D95` makes for `document_type` against
  `fields.DOCUMENT_TYPES`: the check sits on the files, because with the loader
  reading none of these keys the files and this test are the only two places
  that can catch a field left with no tolerance on it.

**What this forbids**

- One tolerance per document, or one number standing for position, size and
  rotation together.
- A position tolerance at or below the detector's error, which would report a
  correctly photographed document as a displaced one on every field.
- Reading the tolerance into `FieldRect` before 13.9 settles what a displacement
  is measured against.

**Consequences.**  13.9 has to parse these rows, and the numbers above are that
task's to use or to argue with -- a tolerance that reads every field as
displaced is a figure to change in this file, not a threshold to lower in
Python.  Only one layout ships, so the claim rests on a single invented file,
but the test walks the directory instead of naming the passport, so a second
layout is covered the day it lands.  The five committed rows happen to agree
with one another; that is a fact about this layout and not a rule the loader
enforces, because a layout with one loose field is exactly what storing these
per field is for.

---

## D99 -- A field is measured against the ink its own reference prints, and a rectangle with none is skipped

**Date:** October 2, 2026. **Status:** settled, task 13.9.

**Context.**  `D98` left 13.8's tolerances unread, holding them for the task
that knows what a displacement is measured against.  Three questions were open.
**What "a field's position" is**, given a template rectangle is a region of a
reference image and not a measurement of anything.  **Which ink belongs to
which field** once a field has moved, since a field printed off its row lands
inside its neighbour's rectangle.  **What a field with nothing printed in its
reference rectangle means**, which on the committed passport is four fields out
of five.

**Decision.**

- **A displacement is a whole-pixel distance in template space, from a field
  rectangle's centre to the centre of that field's own ink.**  Position only:
  size and rotation fail apart from it (`D98`), so the ink's centre of mass is
  used rather than its bounding box, and a field printed larger in the right
  place scores no position deviation at all.
- **A field's ink is the blob nearest its own rectangle, not the ink inside
  it.**  A box test was measured first and is wrong in the one case this
  module exists for: a field moved 30 px right and 25 px down lands in
  `passport_number`'s rectangle and was reported as `passport_number` sitting
  +15, -20 off -- a confident finding about the wrong field.  Nearest-centre
  assignment keeps a moved field with its own ink.
- **A rectangle carrying no ink in the reference is skipped, never scored as
  zero.**  Its centre is a drawn box, and the box is not the document.  This is
  a limit of the committed data and it is large: `passport_td3.json` leaves
  `name`, `passport_number`, `date_of_birth` and `date_of_expiry` blank, so
  **only `photo` is measurable today**, and the claim rests on one field.
  Scoring them anyway was measured and rejected -- a correctly printed value
  reads 7.6 px off its own rectangle against a 12 px tolerance, which would
  flag honest documents and spend half the tolerance on the box.
- **The aligned frame's outer 8 px are not ink.**  `D96`'s detector lands 4 to
  5 px off the page's own, so a warp built on its corners samples the capture's
  background into the frame's outermost pixels; counted as ink it dragged the
  photo block's centroid 37 px sideways and the measurement was meaningless.
- **Ink is the reference's own paper less 40 levels, and the paper is the
  frame's 95th percentile.**  Taken from the reference frame rather than
  declared, so a template printed on tinted stock measures against itself.
- **A field further than 64 px from its own centre is not measured.**  Five
  times the shipped tolerance, and far enough to keep the measurement
  meaningful rather than clipped -- an anchor-sized window reported a true 50 px
  move as 30.
- **The band is `low` and the id is `LAYOUT_DEVIATION`, both already declared
  in `v1.yaml`**, which calls template deviation the classic false alarm on a
  genuine document.  13.9 did not choose either.
- **`loader.read_document` is public and `Template` carries its own `name`.**
  `D98`'s "the loader reads none of it" holds: `FieldRect` still holds no
  tolerance and the loader still interprets no tolerance key.  What changed is
  that the parsed file is now reachable, so the module that owns the number
  reads it out of the one parse rather than opening a second that could disagree.

**What this forbids**

- Scoring a field against a rectangle the reference prints nothing into, and
  reporting that as a displacement of zero.
- Assigning a field's ink by rectangle containment, which misattributes any
  field moved more than half a row from where the layout puts it.
- Counting the aligned frame's border as a field's ink.
- Changing the 12 px tolerance in Python to make a measurement fit.

**Consequences.**  `LAYOUT_DEVIATION` can be emitted for one field of the one
layout that ships, and the four text fields are unmeasured rather than
measured-clean until the committed reference prints values inside their
rectangles -- a change to `passport_td3.png`, not to this module.  A field
moved beyond 64 px is absent from the answer rather than reported as in place,
which is a gap a forgery could sit in and which 13.10 inherits.  13.11's "an
unaligned page scores worse than an aligned one" is now measurable rather than
constant: the committed page reads 2.3 px and a page shifted 39 px reads 39.

---

## D100 -- A font is two numbers read off the type a page prints, and both are measured against the reference's own

**Date:** October 2, 2026. **Status:** settled, task 13.10.

**Context.**  The abstract's tier 1 is "template alignment of layout, fonts and
text positions".  13.9 answered the last two, per field, and left the middle one.
Three questions were open.  **What a font is**, on an image, when nothing here
classifies type.  **What the number is compared against**, given `D99`'s finding
that a measurement means nothing until it is measured against what the reference
itself prints.  **How it reaches a score**, when 13.9's `LAYOUT_DEVIATION` is one
finding per field with that field's rectangle on it and a page-wide style number
has no field to hang on.

**Decision.**

- **A glyph is a mark 6 to 60 rows tall carrying at least 8 pixels of ink, and
  the type on a page is two numbers taken over the glyphs the band admits**:
  `stroke_density`, the share of those glyphs' own bounding boxes that carries
  ink, and `height_spread`, their heights' standard deviation over their mean.
  Both are ratios of positive quantities, so neither needs a page size to be
  compared against anything.
- **The photo block is excluded by the height band, not by a rule about
  pictures.**  360 rows is not a glyph at any weight, and naming the one block
  `passport_td3` happens to carry would be a rule about this layout.
- **The band is fitted to the one page that ships and is stated as such.**
  `passport_td3.png` prints glyphs 15 to 22 rows tall; 6 and 60 sit an order of
  magnitude below the tallest type and far below the smallest mark that is not
  type.  This is that layout's band and not a rule, exactly as 13.9's 64 px and
  12 px are that layout's numbers.
- **Both numbers are taken over every glyph on the page, not inside the<truncated omitted_approx_tokens="378" />eld with that field's rectangle on it, and a page-wide style
  number has no rectangle to point at.  `flag_ids.LAYOUT_DEVIATION`'s own
  comment, "counting the font-style proxy of 13.10", is read as the aggregate
  and not as a per-field value.

**What this forbids**

- Reading a font off a page against a constant stroke width or a constant glyph
  height, or against any number but the reference's own.
- Naming the photo block, or any other block, as a thing to exclude, rather than
  leaving it to the glyph band.
- Reading the proxy inside the field rectangles, where the committed reference
  prints nothing at all.
- Scoring a page whose type could not be measured as clean.

**Consequences.**  Two numbers stand in for a font.  Measured on this page: a
second face at the same size, in the same place, over the same four words
(`FONT_HERSHEY_DUPLEX` against the reference's `FONT_HERSHEY_SIMPLEX`) departs
by 39% of the density band and 240% of the spread band, so the style departure
saturates at 1.0 while the committed page's own capture costs 7% and 3%.  A face
that agreed with the reference on both numbers would be called clean, and nothing
here claims more than that.  Both tolerances are fifteen to thirty times *this*
capture's cost, so a worse capture than `test_align.py`'s narrows them.  The
committed reference is `cv2.putText` in `FONT_HERSHEY_SIMPLEX` at scale 1.0,
thickness 2, at four baselines, and a reprint in that face reproduces its style
numbers exactly -- which is what makes the test's control a control.  **In this
OpenCV build `putText` thickness saturates at 2**, so a heavier weight of the
*same* face could not be drawn as a fixture and the face had to change; that is
a property of the box, not a finding about fonts.  **`layout_score` has no
caller**: it is what 13.11 measures and what the risk engine will carry once
`Tier1Result` grows the field `R1` is summed from, which it still does not have.

---


[36] tool exec_command result: Chunk ID: e7ac32
Wall time: 0.6386 seconds
Process exited with code 0
Original token count: 8145
Output:
Warning: truncated output (original token count: 8145)
Total output lines: 230


lorebook\abstract.txt:1:1. Problem Statement and Context Border checkpoints must decide within seconds whether a traveller's documents are 
genuine, current and actually belong to the person presenting them. The threats have grown beyond crude forgery. Attackers now use forged or 
digitally altered passports and visas, expired or reused documents, impersonation with genuine documents, and facial images that are morphed or 
synthetically generated. A morphed photograph is especially difficult because it can resemble two different people, so a document can pass a face 
comparison for both of them. Current verification relies on manual inspection and several disconnected checks: a visual examination, a separate 
MRZ read, and a separate database lookup. This has four consequences: - Time and congestion. Each additional check adds seconds per traveller, and 
queues build at peak hours. - Inconsistency. Outcomes depend on the experience, fatigue and attention of the officer on duty. - No explanation. 
Where automated tools exist, they tend to return a pass or fail verdict without showing what was wrong or where. - No verifiable record. There is 
rarely a tamper-evident account of what the system showed the officer and what the officer decided, which weakens accountability in disputed 
cases. Any solution must also handle sensitive identity and biometric data, so the design cannot solve the fraud problem by creating a new privacy 

---

## D101 -- The face seam is two interfaces, and a stub that is labelled rather than silent

**Date:** October 2, 2026. **Status:** settled, task 13.12.

**Context.**  The abstract's Tier 1 ends with "face detection, alignment and
embedding, matched against a live capture", and 13.13-13.16 build the model,
the alignment, the similarity and the flag.  Three questions were open before
any of them.  **What a detector is asked**, given that 13.14 needs a place to
put a face and 13.15 needs a place to put a number.  **What an embedder is
asked to return**, given that a missing face model is an ordinary box rather
than a broken one (`D83`).  **What Tier 1 does with no face model at all**,
which is the case on every machine this project has been run on so far: the
stub that fills the gap is the one piece here that will be read on a real
screening before a real model exists.

**Decision.**

- **Two seams, not one.**  `FaceDetector.detect(image)` answers *where the
  faces are*, as a tuple of `DetectedFace`; `Embedder.embed(image)` answers
  *what one face is*, as an `Embedding` or nothing.  They are separate because
  13.14 owns the first and 13.13 owns the second, and one method doing both
  would make the crop 13.14 builds an argument only a detector understands --
  the failure `D82` was written to prevent, arriving again one tier over.
- **Both are `abc.ABC` and both declare exactly one method**, on `D82` and
  `D83`'s reasoning: a subclass that omits its method cannot be built, and
  availability stays concrete on each implementation rather than becoming a
  second abstract method nothing here can answer honestly.
- **`detect` answers `()` for a frame holding no face**, which is a
  measurement of nothing rather than a failure to measure -- `ocr.NO_WORDS`
  and `MrzDetection` already answer the same way.
- **`embed` answers `None` for a face it could not measure, and that is a
  different statement from the stub's answer.**  `D99`'s rule, held here:
  where nothing was measured the answer is `None`, never a zero that reads
  like a reading.
- **`is_stub` rides on the `Embedding`, not on the embedder.**  A caller
  holding two embeddings cannot ask which embedder produced either of them,
  so a label on the object that made them would be a question the comparison
  could not answer.  It defaults to `False`, because a vector is a
  measurement unless it says otherwise, and the record is frozen so a stub
  cannot be relabelled after the fact.
- **`NullEmbedder` returns the same zero vector for every image, and labels
  it.**  This is the load-bearing part: a zero vector has no direction, so the
  cosine 13.15 computes is `0 / 0` and undefined against it.  Refusing to
  score it is the only correct answer, and the refusal needs something to key
  on -- which is what the label is for.  A stub that returned a plausible
  random vector instead would be strictly worse: it would score, and it would
  score the same for every traveller.
- **`NULL_EMBEDDING_DIM` is 512, ArcFace's own width, and is stated as such
  rather than measured** -- no face model is installed here, so there was
  nothing to measure against.  It buys shape compatibility (a caller does not
  branch on vector length) and nothing else: since a stub is refused rather
  than scored, the length is never load-bearing for correctness.  A `dim` that
  is not a positive `int` raises rather than defaulting, on `D98`'s reasoning.
- **`DetectedFace.region` is a polygon of whole-pixel corners in the order
  `EvidenceFlag.region` uses**, so a face and a flag are drawn by one routine.
  It carries no landmarks: 13.14's alignment is a crop this record does not
  hold, and guessing a landmark order here would be a claim 13.14's
  implementation has not earned.
- **Neither record defaults.**  A defaulted `confidence` would be a face
  measured at a clean zero, which is the one answer this project's own rules
  refuse everywhere else.

**What this forbids**

- A detector or an embedder taking an argument only it understands, or an
  image argument with a default.
- An `Embedding` that can be relabelled after it is created, or whose
  `is_stub` defaults to `True`.
- A zero vector presented as a similarity, a score, or a match against
  anything.
- Reporting "no face" as `None` from `detect`, or a stub as a real vector.
- Naming a landmark order on `DetectedFace` before 13.14 builds one.

**Consequences.**  A box with no face model answers every question here and
answers none of them truthfully, which is what the label is for: 13.15's
cosine is undefined against a zero vector, so the similarity a caller would
have reported is refused rather than divided by.  **`NullEmbedder` has no
caller yet** -- nothing in Tier 1 reads it, so on a box without a model a
screening today takes the same path it took before 13.12; the stub is what
13.15-13.16 will degrade onto.  **`DetectedFace` carries no landmarks**, so
13.14 may find it needs a field this record does not have; that is a change to
add then, and the seam is one dataclass wide.  **Both interfaces are
unchecked at the call site**: `is_available` is not declared on either, so a
future selector reaches a method the abstract class does not list, which is
the same gap `selection.py` records for OCR and is what should reopen `D83`
if a third caller appears.

---

## D102 -- A face is aligned by a similarity to ArcFace's own five points, and a face that cannot be fitted is absent

**Date:** October 2, 2026. **Status:** settled, task 13.14.

**Context.**  13.14 asks for "face detection and alignment (landmark-based
similarity transform to a canonical crop) in the photo region".  Three things
were open.  **Where a detector is pointed** -- anywhere on the page would find
a face in the printed portrait *or* in a face pasted into the visa sticker, and
nothing downstream would say which.  **What "aligned" is measured against** --
`D99` has twice refused a measurement against a constant in favour of one
against a reference, and this could have gone either way.  **What happens to
landmarks that describe no face**, which is the geometry version of a detector
answering `None`.

**Decision.**

- **A detector is pointed at the template's own `photo` field**, cut out of
  the aligned frame by `photo_region`.  The rectangle is read in the space
  `align.warp_to_template` produced it in, so a face is looked for where the
  document says the face is.  A template placing no `photo` field answers
  `NO_CROP`, and so does a frame too small to hold the rectangle it names.
- **The rectangle is checked against the frame rather than sliced.**  A numpy
  slice past the edge returns a *shorter* frame, so an unclipped
  `photo_region` hands a detector a partial portrait and reports whatever it
  found there as though the whole region had been searched.  This was a real
  failure during this task, not a hypothetical one.
- **The canonical landmarks are ArcFace's own five reference points for a
  112-square**, stated rather than measured -- they are the recogniser's input
  contract (`insightface_embedder.MODEL_INPUT_SIZE` is the same 112, held to it
  by a test).  Fitting to them is what "aligned" means, the same way 13.11's
  alignment space is the reference frame's own corners.
- **The fit is a similarity, not a full affine.**  A full affine would also fit
  five points and would add a shear term no flatter photograph asked for.
  **Five points that are already a similarity determine it uniquely, so the two
  fitters agree on an undeformed face** -- which is why the test that holds
  this drags the mouth corners off the fitted pose, where a full affine puts
  0.36 of shear on a transform that should have none.  That number was measured,
  not chosen.
- **Landmarks that enclose no area -- stacked on one point, or all on one line
  -- answer `NO_CROP`, never a zero crop.**  A 112-square of black would read
  like a face measured and found empty, which is the answer `D99` refuses
  everywhere else.  OpenCV itself returns `None` for the stacked case; the
  collinear case it fits anyway with half its points marked outliers, so the
  area check is this module's and not merely a pass-through.
- **Landmarks that are not five finite `(x, y)` pairs raise**, on `D98`'s
  reasoning.  Padding or trimming them into shape would produce a transform
  that looked measured and was not.
- **`aligned_crops` drops an unalignable face and keeps the rest.**  One
  unusable face does not stop a good one being reported beside it, and a caller
  asking "what did this photo show" gets faces rather than a failure.
- **`DetectedFace` gained `landmarks`**, which `D101` forbade naming until
  13.14 built one.  The record is one dataclass wide and the alternative was a
  second return value no caller would have kept in step with the first.

**What this forbids**

- Pointing a detector at anything but the template's own `photo` field.
- Slicing a rectangle out of a frame too small to hold it.
- Fitting a full affine, or fitting no similarity at all.
- Reporting an unalignable face as a black crop, a `None` landmark, or a
  `DetectedFace` with five points that were never measured.
- Adding a default to `DetectedFace.landmarks`, on `D99` and `D101`.

**Consequences.**  **`photo_region` needs the template, so `aligned_crops` is
the only caller that has both** -- there is no face-aware path into `runner.py`
yet.  **The canonical landmarks are ArcFace's and were not measured here**; a
different recogniser would need different numbers, and only
`CANONICAL_SIZE == MODEL_INPUT_SIZE` is held to 13.13's module today.  **The
landmark order is named in `LANDMARK_ORDER` and the record's docstring, and a
test holds the two to five** -- but nothing detects a detector that returns its
five points in a different order, which is the same unanswerable gap
`selection.py` records for OCR engines.  **`InsightFaceEmbedder` still has no
test at all**, so 13.13's box is ticked on the strength of the module existing;
this task read its `MODEL_INPUT_SIZE` and verified nothing else about it.

---

## D103 -- Two faces are compared by the cosine between them, and a vector with no direction is not compared at all

**Date:** October 2, 2026. **Status:** settled, task 13.15.

**Context.**  13.12 built the seam and left one thing in it open: a stub
returns a zero vector, and `D101` recorded that the cosine against a zero
vector is `0 / 0`.  13.15 is the task that has to do something about it, and it
is the first part of this project that reads two measurements and produces a
number rather than measuring one thing.  Two questions followed.  **What a
comparison answers**, given that the abstract's flag carries both a similarity
and a threshold and neither number can be recovered from the other afterwards.
**What a caller with no face model gets**, which is this box and every box the
project has been run on so far.

**Decision.**

- **The similarity is the cosine, and both vectors are scaled to unit length
  before they are multiplied.**  A dot product of the same pair scores a
  5-12-13 vector against itself at 169.0 rather than 1.0, and it is not
  invariant to the brightness of either photograph.  The fixture is
  deliberately not unit length, so a module reaching for the dot product fails
  on the first case instead of passing it by luck.
- **The answer is a `MatchScore` carrying `similarity` and `threshold`, and
  neither field defaults.**  The threshold rides on the record rather than
  living here as a constant, because 13.16's flag carries both numbers and a
  score whose threshold is a constant the caller must remember is one place for
  the two to drift apart.  `matches` is a property rather than a stored field,
  so it cannot disagree with the two numbers printed beside it, and reaching
  the threshold counts as meeting it.
- **`threshold` is required, and must be above 0.0 and no more than 1.0.**  No
  default, on `D98`'s reasoning: it is part of the answer rather than a default
  standing behind it, and a caller scoring against a bar this module chose is
  scoring against a number it cannot see.  A cosine runs from -1.0 to 1.0, so a
  bar above one is a mistake no pair of vectors can clear -- stricter is a
  policy, unreachable is a wiring error.
- **A stub on either side, and any vector with no length, answer `NO_MATCH`
  (`None`) and never a similarity of zero.**  `D101` named the refusal and
  `D99` gives it its value: where nothing was measured the answer is `None`,
  and a clean `0.0` would read as a measurement of two faces that are merely
  unlike.  **The label and the norm are checked separately and both are
  load-bearing**: `NullEmbedder`'s vector is all zeros, which the norm alone
  would catch, and the stub carrying a *plausible* vector that `D101` calls
  strictly worse is caught by the label alone.
- **A vector holding something that is not a finite number raises**, on the
  same reasoning as 13.14's landmarks: `float("0.5")` would take a string, and
  a `nan` reaches the cosine as itself.  Two vectors of different widths raise
  too, since two face models produce two widths and comparing them is a mistake
  rather than a measurement of nothing.
- **The similarity is clamped to the cosine's own range.**  This is measured,
  not decorative: a 5-12-13 vector against itself reads 1.0000000000000002
  unclamped -- a similarity above a perfect match, which fails the exact
  assertion the identical case is written with.  `math.fsum` rounds once at the
  end, so an exact sum of rounded products can still leave the range it came
  from.

**What this forbids**

- Scaling either vector into the answer, or reporting a dot product as a
  similarity.
- Defaulting the threshold, or accepting one no cosine can reach.
- Reporting a stub, a zero vector, or a vector with no components as a
  similarity, and above all as a similarity of `0.0`.
- Padding or truncating two vectors of different widths into one comparison.
- Storing `matches` on the record beside the two numbers it derives from.

**Consequences.**  **`match_score` has no caller**, the gap 13.11's
`layout_score` and 13.14's `aligned_crops` are in: 13.16 is what turns the
score into a flag and nothing wires either into `runner.py`, so no screening
compares faces today.  **A stub degrades to `None`, so `MatchScore | None` is
the answer at every call site** -- 13.16 has to decide what a face that was
never compared reports, and a `None` that became a `0.0` flag is the failure
`D99` exists to prevent.  **Nothing here reads a face model**, so every number
is the fixture's own geometry: no threshold is claimed to be measured against
real ArcFace pairs, and none of these figures is a statement about how alike two
travellers' photographs really are.

---

## D104 -- The cascade carries one mutable context, and the depth is not called "mode"

`backend/app/pipeline/orchestrator.py` holds `ScreeningContext`: the screening
id, the caller's document claim, the working frame, the injected reference day
and the checkpoint's depth, beside the two lists the run fills in -- the flags
found so far and the stage trace.  Four decisions came out of writing it, and
three of them are refusals rather than additions.

- **The context is mutable, and that is the one thing that separates it from
  every record this project freezes.**  A stage appends a flag and a trace
  entry; a frozen context would have to be rebuilt after each one, and the
  rebuilt copy is a second record that could disagree with the one the run is
  holding.  `EvidenceFlag`, `MrzDocument` and `MatchScore` are frozen because
  they are evidence, and a context is not evidence -- it is the run's own
  working record, and nothing reads it after the screening is scored.
- **The two accumulators default to empty, per instance.**  `default_factory`
  rather than a shared `[]`, because a list as a class-level default is one
  list that every context on the box appends to.  **An empty list is a fact
  about time, not about a document**: it says no stage has run yet, which is
  exactly what is true of a context built this second, and it is not the
  answer "this document is clean", which is what a zero would read as.  This
  is `D99`'s rule -- where there is nothing to measure, the answer is `None`
  or the thing is absent -- applied to the one field where absence is the
  truth.
- **The depth field is `depth_mode`, and the two vocabularies are held
  disjoint.**  `Screening.mode` in `app/storage/models.py` is the quality
  gate's reading of how the document was captured -- `photo` or `scan` -- and
  this field is whether the checkpoint runs the ordinary cascade or the
  abstract's full-depth one.  Two questions about a screening, and `D5`'s
  reason that one cannot answer the other: a context field named `mode` would
  be written into the row's capture column by whoever stores the result, and
  both hold short lowercase words, so nothing would object.
  `test_the_depths_are_the_two_named_and_not_the_capture_modes` holds the two
  sets apart, so a third depth or a fourth capture mode cannot quietly grow
  into the other's vocabulary.
- **The depth is required and has no default.**  A context defaulting to
  `STANDARD` is a screening that silently skipped Tier 2, and the escalation
  it skipped is 14.9's rule to make loud.  This is the same argument as
  `selection.UnknownEngineError`: answering "standard" for a misspelled mode
  degrades every screening on the box with nothing to say which mode was asked
  for, so an unknown name raises `ContextValueError` instead, and the message
  names both depths so a caller can see the vocabulary without reading the
  module.

**What is checked at construction, and what is deliberately not**

- **`screening_id` must be a `uuid.UUID`, and `depth_mode` must name a mode.**
  Those are the two fields *no stage owns*, so they are checked where the
  record is built and nowhere else.  The id's type is load-bearing for 14.8:
  the randomised audit draw is `HMAC(server_secret, screening_id)`, and a
  string id would make that draw depend on how the string happened to be
  spelled.  The mode's membership is load-bearing for 14.9 in the other
  direction -- a mode nothing recognises must not read as a standard one.
- **The frame, the document claim and the reference day are not checked
  here.**  Each has an owner: 4.1 is the only gate that decides what an image
  is, and `run_tier0` already refuses a `document_type` that is neither
  `None` nor a non-empty string and a `reference_date` that is not a date.
  Copying either judgement here would be a second opinion about the same
  question, and `_check_parsed_document`'s reasoning -- a second gate that
  copies a judgement is a second opinion -- applies to a context as much as to
  a runner.  So a bad value is refused by the stage that reads it, not by the
  record that carries it.
- **`stage_trace` is a list of whatever 14.10 writes, and is typed `Any` for
  that reason.**  14.1 fixes that the context carries the stages in the order
  they ran and starts empty; the record's own shape -- stage, started, elapsed,
  flags added, escalated -- is 14.10's to write, and typing the list now would
  be a promise about a shape this task does not decide.

**What this forbids**

- Freezing the context, or handing two contexts one shared default list.
- Naming the depth `mode`, or writing a depth into the row's capture column.
- Defaulting `depth_mode` to `STANDARD`, or answering a mode nothing names.
- Re-checking the frame, the document claim or the reference day here.
- Reading a clock for the reference day, or typing the trace list to a shape
  14.10 has not written.

**Consequences.**  **Nothing reads this record yet**: 14.2 is the registry
that will drive stages against it, 14.3 is the first stage to add flags to it,
and no route constructs one yet, so a screening still reaches Tier 0 alone
through `app/screening.py`.  **`image` is typed `Any` and nothing gates it**,
so the first frame to reach a context is judged by whatever stage runs first
rather than at construction; that is the intended division, and it is worth
revisiting if a caller ever wants the refusal earlier than 14.3.

---

## D105 -- The cascade draws its stages from a read-only registry, and a name it does not hold is a refusal

`backend/app/pipeline/orchestrator.py` holds `STAGES`: the stage callables
this cascade may run, keyed by name and in cascade order.
`resolve_stage(name, stages=None)` answers the callable a name asks for, and
raises `UnknownStageError` for a name no registry holds.

- **A stage is a callable handed the context.**  One argument, no return
  value, because a stage answers by what it writes onto the context and a
  second channel out of it would be a record the run has to keep in step with
  the context itself.  **What a stage may return, and how one asks the cascade
  to stop, are 14.4's to decide**, so this task fixes only the call.
- **The registry is read-only and built once.**  A mapping proxy, on
  12.5's reasoning: a registry a caller could add to would make "the stages
  this cascade runs" a property of whoever wired it up last.
- **`STAGE_NAMES` is read off the registry rather than spelled out beside it.**
  12.5 spells `ENGINE_NAMES` out because its order is a *preference* order --
  "first available" walks it -- and that order has to exist before the engines
  do.  A stage order is the registry's own insertion order, so a second
  listing could only ever disagree with it.
- **An unknown name raises `UnknownStageError`, a `ValueError`.**  This is a
  wiring mistake and not an absence: every name the registry holds has a
  callable behind it, so answering `None` for a misspelling would run a
  screening through no stage at all and say nothing about which stage was
  asked for -- a screening that found no forgery because nothing looked.  The
  message lists the names this call does know and echoes the name asked for,
  which is a deployment's own configuration and not anything a document
  printed.  A name of the wrong type is the same refusal, on `ContextValueError`
  and `UnknownEngineError`'s reasoning.
- **The shipped registry is empty, and that is the honest reading.**  14.3
  writes the first stage callable; until then every name is unknown, and a
  name mapped to a callable that measures nothing would be a stage that ran
  and reported nothing -- the clean zero `D99` forbids.  **The tests
  therefore hand in their own registry**, so what is pinned here is the
  mapping and the refusal, not the number of stages that exist today.
- **A caller may hand in its own registry.**  The same seam `select_engine`
  offers, and what lets a test drive a two-stage cascade without the shipped
  registry having to grow a stage to be exercised.

**What this forbids**

- Registering a name whose callable measures nothing, or returning `None` for
  a name the registry does not hold.
- Editing `STAGES`, or listing the stage names a second time somewhere.
- Fixing here what a stage returns, or how a stage stops the cascade.

**Consequences.**  **Nothing dispatches through this yet**: `STAGES` is empty,
no route constructs a `ScreeningContext`, and a screening still reaches Tier 0
alone through `app/screening.py`.  **The registry cannot be checked against
the tree by a test** -- a name mapped to a callable that was deleted or
renamed imports fine -- so what holds the map honest is 14.10's trace
recording the name that actually ran.

---

## D106 -- The capture gate is stage 0, and its nine failures are `quality` tier flags

`backend/app/pipeline/quality.py` holds `run_quality`, registered in
`app.pipeline.orchestrator.STAGES` under `STAGE_NAME` = `"quality"`.  It hands
`context.image` to `app.quality_checker.engine.analyze_image` and appends one
`EvidenceFlag` per result whose `passed` is `False`.  `CHECKS` is the one
table mapping each of the gate's nine checks to the id its failure carries.

**Context.**  D105 left the shipped registry empty and named 14.3 as the task
that fills it.  Two of its gaps were recorded elsewhere and are closed here:
D7's "no ninth prefix without changing `PREFIXES` and the test that holds its
eight names", and D17's revisit on a flag emitted about something with no
field at all.

- **The stage runs the gate that already exists and changes nothing in it.**
  `analyze_image` is called on the context's own frame with its own
  `requested_mode="auto"`, because the photo-or-scan reading is
  `Screening.mode`'s only permitted writer and the context has no slot for it
  (D104).  **A second quality implementation beside this one would be five
  answers to one question**, which is the duplication D96 exists to prevent.
- **`QUALITY_` is a ninth family, and it comes first.**  Stage 0 runs before
  tier 0, so the family leads `PREFIXES`, `ALL_FLAG_IDS` and `v1.yaml`'s rows
  in that order.  Both halves of D7's condition were met: the list changed and
  `test_flag_ids.py`'s `NAMED_PREFIXES` changed with it, deliberately.
- **`tier="quality"` is the fifth name `EvidenceFlag.tier` allows.**  It is the
  one finding on record that is about the photograph rather than about the
  page, and `tier` stays unchecked, as D6 has it.
- **One id per check, keyed on the label `run_all` writes.**  A module's own
  result is keyed by its short name (`"sharpness"`) while the error path in
  `run_all` writes `module.__name__` (`"app.quality_checker.m1_sharpness"`),
  so the label is the only key both paths share.  **A label `CHECKS` does not
  hold raises `UnknownCheckError` rather than being dropped**: a tenth check
  with no tenth id is a wiring fault, and dropping the result would report a
  capture the gate could not clear as one it did.
- **Only `passed is False` reaches the stream.**  `None` is the gate's own
  answer for a check that does not apply -- glare on a flat scan, resolution
  on a page it found no text on -- which is neither a failure nor an absence
  of one.
- **`value` and `confidence` are both 1.0, as 6.2's check-digit flags are.**
  The gate measured and its own threshold decided, which is all the finding
  says.  **The measurement is not a severity on `[0, 1]`** -- a Laplacian
  variance or a median character height has no meaning there -- so it is
  carried in `found` as the number the gate printed, and `found` is `None`
  where the gate printed none.  `expected` stays `None` for all nine: the
  gate's rule is a sentence (`PASS if Laplacian variance >= 100.0`) and
  `found` is a value column, not a sentence column.
- **A module that raised is written, not dropped.**  `run_all` already reports
  such a check as `passed: False` with `reasons: ["module_error"]` and no
  score, so the flag carries that reason and no number.  **Silence would be
  the worse answer**: a broken check that vanishes leaves a capture the gate
  could not clear looking like one it did, which is the silent stub D101
  refuses.
- **`field` is `None` on all nine, and that is one meaning.**  D17's revisit
  asked whether `None` would come to carry more than one thing.  It does not:
  the check is named by `id` and measured by `source_module`, both read off
  the gate's own table, and `None` says only that the finding is about no
  field of the document.
- **Every quality row weighs 5 and is banded `low` -- one weight for nine
  checks.**  They are one gate, and nine separate uncalibrated figures would
  pretend to know which check matters most.  Three failures weigh what one
  unreadable field weighs (15) and all nine weigh 45, which reads `review`:
  a capture nothing can be read out of is a screening no officer can clear.
  `LOW_MAX`'s own rationale in `app/risk/config.py` no longer held -- it
  promised a number above *any* pile of `low` rows, and there are eleven now --
  so it was amended rather than left claiming something false.
- **`RULESET_VERSION` moves to 0.2.0.**  Nine new weighted rows is a flag and
  a weight changing (D22), and a score is only comparable against the ruleset
  that produced it.
- **One assertion elsewhere was wrong, and nine five-point rows found it.**
  `test_compute_risk.py`'s hard-fail pile expected `min(100, floor + pile)`,
  which leaves the overriding flag's own weight out of the sum and adds the
  floor as though it were a contribution.  **It agreed with the engine only by
  coincidence**: the pile's first soft id used to weigh 55, so all four sizes
  clamped to 100 and the two formulas met.  The expectation now spells the
  engine's own composition, `min(MAX, max(floor, sum))`, which is what
  `apply_hard_rules` and `clamp_score` do.

**What this forbids**

- Judging a frame anywhere but the gate, or opening a tenth quality check
  without a tenth id in `app.risk.flag_ids` and a tenth row in `v1.yaml`.
- Writing a flag for a check that passed or does not apply, and dropping one
  whose check `CHECKS` does not hold.
- Retuning the weightset's version without the bump, or the weight without the
  version.

**Consequences.**  **Nothing dispatches through the cascade yet**: no route
builds a `ScreeningContext`, so `app/screening.py` still reaches Tier 0 alone
and the gate still runs nowhere in a real screening.  `Screening.mode` is still
unwritten, because the context has no field for it and D104 reserved the name
-- whoever builds a row from a context writes it, and no route may.  **From
14.5 the first time the score is summed from a context, a blurred capture
costs five points**, which is the first way a photograph can move a score in
this system.

**Revisit only if** a tenth check is added to the gate, or if the gate's own
`MODULES` table stops being the one place its checks are listed -- which is
what `CHECKS` is keyed against and what `test_quality_stage.py` reads back.

## D107 -- A hard fail is one reason on the context, and the cascade stops where it is written

`backend/app/pipeline/tier0/stage.py` holds `run_tier0`, registered in
`app.pipeline.orchestrator.STAGES` under `STAGE_NAME` read off
`runner.TIER_NAME`.  It hands the context's frame, claim and injected day to
`app.pipeline.tier0.runner.run_tier0` and writes the result's findings onto
`context.flags` and, when the result hard failed, its reason onto
`context.hard_fail_reason`.  `orchestrator.run_cascade(context, *, stages=None)`
runs a registry in order and breaks the moment that field is no longer `None`.

**Context.**  D105 fixed a stage as a callable handed the context and
answering only by what it writes, and left the registry empty of any way to
stop.  14.4 is the first stage that can end a cascade, so it is the first to
force the question.

- **The stop is a field, not an exception and not a return value.**  D105
  leaves a stage answering by its writes, and both alternatives open a second
  channel beside them: a raised `HardFail` would make "the stage failed" and
  "the cascade stopped" one event that no caller could tell apart, and a
  returned verdict would give every stage a second answer to read.  A field
  keeps D105 whole -- the stage writes, and the cascade reads.
- **A reason *is* the hard fail.**  There is one optional field rather than a
  bool beside a sentence, so the pairing `TierResult` already refuses to let
  disagree (`hard_failed != (hard_fail_reason is not None)` raises there) is
  structural here rather than merely checked: a non-`None` reason *is* the
  stop.  Nothing on the context can say "hard failed" without saying why.
- **The cascade reads the field after a stage returns, never inside it.**  A
  stage cannot know what runs after it; only the cascade holds the order.  The
  break is therefore one line in `run_cascade` and the stage knows nothing
  about it.
- **The override is the runner's verdict, copied rather than recomputed.**  The
  stage writes `result.hard_fail_reason` because `result.hard_failed` said so.
  **Membership of the runner's `_HARD_FAIL_IDS` is the whole test there** --
  a stolen-document hit is `high` and does not override -- so deciding it again
  here would be a second answer to 6.5's question, and one free to disagree
  with the first.  `test_a_heavy_finding_that_is_not_a_hard_fail_does_not_stop_the_cascade`
  pins that a heavy flag runs the tiers on.
- **A tier a hard fail kept out is absent from the answer, not skipped in it.**
  `run_cascade` returns the names that ran.  Recording a skipped tier would
  make `tiers_run` and the tier events beside it (D68, D69) two answers to one
  question, which is the drift `_TIER_RUNNERS`/`CASCADE` in `app/screening.py`
  is built to prevent.
- **An empty registry answers `()`, where `app/screening.py` raises.**  That
  module's `CASCADE` is a module constant that lost its entries, which is a
  fault worth refusing; here `stages` is a caller's argument, so an empty one
  is a caller who asked for no stages.

**What this forbids**

- Deciding the override anywhere but the runner that raised it, or treating a
  weight band as though it were one.
- A second field beside `hard_fail_reason` that could disagree with it, and a
  stage that stops the cascade by any means but writing to the context.
- Reporting a tier as run because the cascade reached for it.

**Consequences.**  **The new cascade is still unreachable**: no route builds a
`ScreeningContext`, so `app/screening.py` runs its own `_run_cascade` and
reaches Tier 0 alone, and the two are separate code with the same job.
**A context-driven Tier 0 cannot hard fail today.**  The runner's two override
families are exactly the check digits, which need a `parsed_document`, and the
blacklist, which needs a `watchlist` -- and `ScreeningContext` has no slot for
either, so the stage asks for neither and 14.5's `R1` has nothing to stop on.
`test_the_hard_fail_stops_the_cascade` reaches the stop by standing the runner
in, and that stand-in is the honest shape of the seam until a later task gives
the context those two slots.
`test_stage_registry.py` and `test_quality_stage.py` each asserted that
`"tier_0"` was a name the shipped registry refused; 14.4 registers it, so both
now refuse `"tier_1"` -- the same claim, about a name the registry still does
not hold.

**Revisit only if** a second family grows an override of its own, which would
make `hard_fail_reason` a summary of several findings rather than the runner's
one sentence, or the context gains slots for a parse and a watchlist, which
would let a real page reach the stop without a stand-in.

## D108 -- R1 is the weighted sum of Tier 1's own findings, and the stage writes it

`backend/app/pipeline/tier1/stage.py` holds `run_tier1`, registered in
`app.pipeline.orchestrator.STAGES` under `STAGE_NAME = "tier_1"`.  It hands the
context's frame to `app.pipeline.tier1.runner.run_tier1`, extends
`context.flags` with the findings that came back, and writes
`app.risk.scoring.weighted_sum(result.flags, weightset)` to the new
`ScreeningContext.r1`.  `Tier1Result` grew the `flags` field that sum is made
from, empty by default so every construction of it that named two fields still
reads.

**Context.**  D105 made a stage answer only by what it writes, D106 gave the
cascade its first two stages and D107 its stop.  The abstract's escalation rule
turns on `R1`, so 14.5 is the first task whose output is a number rather than a
finding, and it had to choose what that number is made of.

- **`R1` is Tier 1's own flags, not the whole flag stream.**  The abstract says
  "Tier 1 produces a partial score R1" and the task says `R1` is computed
  "from its flags", so Tier 0's non-override findings -- a stolen document, an
  identity already seen, a date not yet valid -- do not move it.  They move the
  eventual `R`, which 7.5 already sums over every flag a run collected.
  `test_r1_is_the_sum_of_tier_1s_own_flags_and_not_of_the_whole_stream` pins
  this with a stage-0 quality flag already on the context, which is otherwise
  the one finding that could have been argued into the sum: **a failed quality
  check does not cost five points here, whatever the handover predicted.**
- **`None` means the tier has not run; `0.0` means it ran and found nothing.**
  7.5 holds an empty sequence to be `0.0`, a real answer rather than a missing
  one, so the field's two states are questions about *the run* and never about
  the document.
- **The sum is 7.5's `weighted_sum`, unchanged.**  Nothing is clamped, banded,
  floored or hard-ruled in the stage, so a `high` Tier 1 finding is a weight and
  never an override -- which
  `test_a_heavy_tier_1_finding_moves_the_score_and_stops_nothing` pins.  The
  ambiguity band is 14.6's question asked of this number, not this stage's.
- **The weightset is the stage's argument, defaulting to the shipped one read
  per call.**  The loader refuses to cache at module level, and a `weightset=`
  argument lets a caller or a test score against a retuned table without the
  stage holding a number of its own;
  `test_r1_is_scored_against_the_weightset_the_caller_hands_over` uses a second
  id to show the table, not the stage, decides.
- **The one finding this runner makes today is a page no engine could read.**
  D86 already answered that page with `ocr_available=False` rather than a
  refusal; 14.5 adds the `OCR_LOW_CONFIDENCE` finding beside it, which is the
  honest id -- the weightset's own comment calls that row a statement about our
  reading and not about the document.  A page an engine *did* read produces no
  flags, because the four checks that would fire -- `compare_to_mrz`,
  `compare_to_barcode`, `compare_layout`, `match_score` -- need a parsed MRZ and
  a live capture, and the context carries neither.

**What this forbids**

- Summing the context's whole flag stream into `r1`, or multiplying a term
  anywhere but `weighted_sum`.
- Reading a weight band as an override, or clamping, banding or hard-ruling
  `r1` inside the stage.
- Leaving `r1` absent once Tier 1 has run, or writing it from any other stage.

**Consequences.**  **`R1` cannot yet tell a genuine page from an untested one.**
A readable page scores `0.0` whatever it carries, because none of Tier 1's four
comparisons is wired, so 14.6's band has nothing to separate until they are.
`test_stage_registry.py` and `test_quality_stage.py` each asserted that
`"tier_1"` was a name the shipped registry refused; 14.5 registers it, so both
now refuse `"tier_2"` -- the same claim, about a name the registry still does
not hold.

**Revisit only if** the context gains slots for a parsed MRZ and a live capture,
which would let the four Tier 1 comparisons fire and give `R1` something other
than zero to separate, or if the escalation rule ever asks for the cumulative
score across the tiers rather than Tier 1's own.

## D109 -- The ambiguity band is a range closed at its own top, and an escalation is a reason

`backend/app/pipeline/escalation.py` holds `AmbiguityBand(low_max,
review_max)`, `default_band()`, `check_ambiguity(context, *, band=None)` and
the `CHECK_NAME` this trigger is named by.  `ScreeningContext` grew
`escalations: list[str]` and the derived `escalated` property.  The check
reads `context.r1`, asks the band one question, and on a yes appends a
sentence to `escalations`; on a no it writes nothing and returns `False`.

**Context.**  D108 made `R1` a number and left the band that reads it to
14.6.  The abstract's escalation rule is "R1 falls in the ambiguous band and
the case is routed to Tier 2", and its thresholds are policy that is versioned
with every change, so the band is a committed reading a caller may retune --
not a literal in the check.

- **The band is `(low_max, review_max]`: open at the bottom, closed at its
  own top.**  That is 7.9's shape for all three bands, and the reason each
  edge is named `*_max` rather than `lower`/`upper` is that the name says
  which side is open.  34 is the top of `low` and not the first `review`
  score, and 69 is the top of `review` and not the first `high` one; a
  symmetric pair of names would have left each edge's membership an accident.
  `test_the_band_is_closed_at_its_top_and_open_at_its_bottom` sweeps below,
  at each edge, just inside each edge and above, with every score read off
  `app.risk.config`.
- **The band is the check's argument, defaulting to the committed one read
  per call.**  `default_band()` reads `LOW_MAX` and `REVIEW_MAX` on every
  call rather than binding them at import, which is 14.5's `weightset`
  argument's argument: a retune of D28's pair then moves the edges with
  nothing else edited.  `test_the_band_the_caller_hands_over_is_the_one_that_decides`
  hands over a second band and shows the same `R1` escalating under one and
  not the other, so the record rather than the module decides.
- **The default band and 7.9's middle band are one answer held to each other,
  not one derived from the other.**  `to_band` answers what an officer reads
  off a finished total; this answers whether an unclamped partial score is
  routed on.  They coincide today on every score
  (`test_the_default_band_reads_the_scores_7_9_reads_as_review`), so a retune
  cannot move one and leave the other, and the check does not become
  unconfigurable in the name of consistency.
- **`None` is an absence and `0.0` is a score.**  D108 fixed the two states
  of `r1`: `None` is a tier that has not run, so there is nothing for a band
  to read and the check returns `False` without touching it, and `0.0` is a
  Tier 1 that ran and found nothing, which sits below the band and is
  likewise not an escalation.  A band whose lower edge could reach below zero
  would be the one case that made those two answers disagree, and the default
  one cannot.
- **The band is not held to `[MIN_SCORE, MAX_SCORE]`, though 7.6 holds its
  floor there.**  `R1` is an unclamped weighted sum (D108), so it can exceed
  the top of the scale; a band refused above `MAX_SCORE` would have a half no
  score could reach.  The two edges are still refused unless they are finite
  reals and the pair is a range, through 7.6's own `_score`, so a `nan` --
  which compares false against both edges and would read as a clean page --
  stops the screening rather than answering it.
- **An escalation is a sentence, and the bool is read off the sentences.**
  `escalations` holds one reason per trigger in the order they fired, and
  `escalated` is a property over it rather than a field beside it.  This is
  D107's rule that a reason *is* the signal, extended from one trigger to the
  four this part needs: a stored bool could be `True` with nothing written, or
  `False` beside a reason, and 14.7 to 14.9 would each have had to decide what
  to do with the previous one's answer.
- **It is not a stage, and `STAGES` is unchanged.**  A trigger is a decision
  on what a stage already found, where D105's stage is an analysis handed the
  context.  Registering four decisions would make `run_cascade`'s returned
  `ran` claim four tiers had run, which is the one answer 14.4 made an absence
  rather than a record for.  `STAGE_NAMES` is still
  `("quality", "tier_0", "tier_1")`.
- **It escalates and stops nothing.**  `hard_fail_reason` stays `None` and
  `r1` is not rewritten, because D107's stop is the runner's own override and
  a band is a routing decision;
  `test_an_escalation_hard_fails_nothing_and_changes_no_score` holds it.

**What this forbids**

- A second band, or a comparison against a threshold written beside
  `AmbiguityBand.contains`.
- Storing an `escalated` bool beside the reasons, or overwriting a trigger's
  reason with the next one's.
- Reading a hard fail as an ambiguity escalation, or a `heavy` Tier 1
  finding as one by weight band rather than by score.
- Putting the trigger in `STAGES`, or a band edge in the module rather than on
  the record.

**Consequences.**  **Nothing calls `check_ambiguity` yet.**  `run_cascade`
  runs three stages and never escalates, so the trigger is a function a
  caller runs against a record the cascade produced, and the wiring belongs
  with the gate that asks all four independently.  **And `R1` still cannot
  reach the band on its own**: per D108 the only score a real Tier 1 produces
  today is `0.0` or the weight of one `OCR_LOW_CONFIDENCE`, both below
  `LOW_MAX`, so every test that escalates stands in an `r1` rather than
  running the tier.  That is the honest shape of the seam until 14.7's slots
  and the four Tier 1 comparisons exist, and it is the same reason the band is
  an argument: the check is ready for a score that can land in it.

**Revisit only if** `R1` is ever asked for as a clamped number, which would
  make the scale's ends the partial score's ends too, or if a fifth trigger
  appears that must escalate *without* naming a reason, which is the case the
  reasons-are-the-signal rule could not carry.
## D110 -- A high-risk profile watches two claims, and the shipped profile names nothing

`backend/app/pipeline/escalation.py` grows `HighRiskProfile(document_types,
issuing_states)`, the two committed lists `SHIPPED_DOCUMENT_TYPES` and
`SHIPPED_ISSUING_STATES`, `default_profile()` and
`check_high_risk_profile(context, *, profile=None)`, with
`HIGH_RISK_PROFILE_CHECK_NAME` beside 14.6's `CHECK_NAME`.
`ScreeningContext` grows `issuing_state: str | None = None`.  D109's shape is
untouched: the check appends one sentence, and `escalated` is still read off
the reasons.

**Context.**  The abstract's escalation rule turns on four triggers, and 14.7
is the second: "the case matches a high-risk profile".  Nothing in this
repository says what such a profile holds, so the task's own wording -- "a
*configurable* watchlist" -- is the whole instruction, and two questions were
left open by it: what a profile watches, and what ships.

- **The profile watches claims, not identities.**  The two halves are
  `document_type` and `issuing_state`: the two things a document says about
  itself before anyone has checked it.  **This is not `app.risk.watchlist`** --
  that seam answers "is this document number or this person listed", is Tier 0's
  own hard-failing work, and carries D13's reasons; this one asks "is this kind
  of document or this state worth a second look" and is a routing decision.
  D13 still holds over it for the same reason, though: the reason names the
  watchlist entry that matched, and that entry is a document type or a
  three-letter code -- never a document number, a name or a date of birth.
- **`None` is an absence and not a hit.**  No MRZ reaches the context today, so
  `issuing_state` is `None` on every real run, and a watchlist that read `None`
  as a listed value would send every document on the moment it was consulted.
  `test_an_unclaimed_value_is_not_a_hit` holds it, and
  `test_a_claim_no_watchlist_can_be_read_against_is_refused` refuses a claim
  that is neither `None` nor a string, because a value nobody typed is a
  wiring mistake and not an absence.
- **Both ends fold to lower case and trim.**  An MRZ prints `IND` in capitals
  while a configured list is typed by hand, so comparing the raw strings would
  make a hit a matter of spelling.  `HighRiskProfile.__post_init__` folds the
  entries and `_claim` folds the claims, so exactly one spelling is compared
  and an entry cannot be listed twice in two spellings.  The reason still
  quotes the claim **as the document printed it**, because that is the string
  an officer reads back.
- **The shipped lists are both empty, and that is the decision.**  The abstract
  names the trigger and never the list.  Shipping one would put policy in this
  package that no commit recorded and no calibration chose -- what D22 forbids
  for a threshold -- and a plausible-looking list of states would be worse than
  none, because every deployment would inherit it silently.  So the profile is
  an argument, the way 14.6's band is: `default_profile()` builds it from the
  two committed constants per call, and an agency holding its own list hands it
  over.  **The test that pins the emptiness is meant to fail** the moment a
  list is filled in, because filling it in is the change that must be recorded.
- **One trigger writes one reason.**  A document whose type *and* state are
  both listed is escalated once, naming the type.  D109's rule is one sentence
  per trigger, and a second sentence would make the count a property of the
  document rather than of the trigger.
- **It escalates and stops nothing.**  `hard_fail_reason` stays `None`, `r1`
  and `flags` are untouched, and the profile's twin of 14.6's
  `test_an_escalation_hard_fails_nothing_and_changes_no_score` holds it.
- **`CHECK_NAME` stays as 14.6 named it and this one is prefixed.**  Renaming
  the first would have broken the claim its own test makes, so the four
  triggers end up as `CHECK_NAME`, `HIGH_RISK_PROFILE_CHECK_NAME`, and two more
  in the same prefixed shape.  That is the seam 14.8 and 14.9 copy rather than a
  collision they have to resolve.

**What this forbids**

- Reading an unclaimed value as a listed one, or escalating on a claim the
  profile does not list.
- Shipping a high-risk list without recording it in the same commit, or reading
  one from a file or an environment, so a deployment could retune it with
  nothing recording the change.
- Editing a profile after it is built, or matching a document type against the
  states list.
- Writing a reason that does not name the entry that matched.

**Consequences.**  **Nothing writes `issuing_state`.**  It is a claim on the
record with no producer, in the same position `r1` held before 14.5, so every
14.7 test stands a context in and the check is unreachable from a live cascade
-- which is where its wiring belongs, beside 14.6's.  **The shipped profile
escalates nothing**, so the default path never sends a case on, and a
deployment that configures no list gets the abstract's other triggers and no
more.  **`issuing_state` sits after `stage_trace`**, not beside
`document_type`, because a defaulted field cannot precede a required one and
moving it would have shifted every positional construction in the tree.

**Revisit only if** a task gives the context a parsed MRZ, which would make
`issuing_state` something the cascade writes rather than something a caller
states, or if a deployment needs the lists in a file, which would make the
loaded value part of the recorded ruleset version instead of a constant beside
the check.

## D111 -- The deep audit draw is an HMAC keyed by the server secret, and the shipped rate is zero

`backend/app/pipeline/escalation.py` grows `DeepAuditDraw(rate, secret)`, the
committed `SHIPPED_DEEP_AUDIT_RATE`, `default_draw(secret)` and
`check_deep_audit(context, *, draw)`, with `DEEP_AUDIT_CHECK_NAME` beside the
other two.  D109's shape is untouched: the check appends one sentence, and
`escalated` is still read off the reasons.

**Context.**  The abstract's escalation rule turns on four triggers, and
14.8 is the third: "if it is drawn for a random audit".  It also says why --
"A random sample of low-risk documents still receives deep analysis, so an
adversary cannot learn exactly what passes the light checks" -- which makes
the draw a security control rather than a load-shaving knob, and gives three
questions the task's own wording leaves open: where the randomness comes
from, what the draw is a function of, and what ships.

- **The randomness comes from an HMAC, not from a generator.**  The draw is
  `HMAC_SHA256(secret, screening_id)`, its leading eight bytes read
  big-endian as a fraction of `2**64`, compared against the rate.  **A
  generator would have broken the one property the trigger exists for**: a
  caller's `random` or `secrets` answers a different way each call, so the
  same case could be re-drawn by asking twice, and a re-draw is an oracle.
  `test_the_draw_is_an_hmac_and_reaches_neither_a_clock_nor_a_file` pins the
  primitive, and the module-wide scan that already held 14.6 and 14.7 now
  reads this file too.
- **The draw is a function of the secret and the id, and of nothing else.**
  Not of the clock, the case, the score, the image, or the order two checks
  ran in.  So the same id draws the same way forever -- across a process
  restart, a retry, and a second checkpoint -- which is what
  `test_the_same_screening_id_always_draws_the_same_outcome` holds.  It is
  also why a different secret changes the corpus:
  `test_a_second_secret_draws_the_same_corpus_differently` holds that.
- **The secret is required, and none is shipped.**  `check_deep_audit` takes
  `draw` as a required keyword rather than defaulting it, which is the one
  place this file breaks 14.6's and 14.7's shape.  A secret is the one
  value here that cannot be committed: a shipped one is a key every
  deployment would share, and an unkeyed HMAC is a plain hash of the id,
  which an adversary computes offline and knows the whole draw in advance.
  So there is nothing to default to and the type says so.
- **The rate is a probability, refused outside `[0, 1]`.**  A rate is not a
  score, so it does not go through `_score`'s `MIN_SCORE`/`MAX_SCORE` ends;
  it reuses `_score` to refuse a non-real or non-finite value and range-checks
  it itself.  `0.0` draws nobody and `1.0` draws everybody, both exactly,
  which `test_the_edges_of_a_rate_are_exact_and_need_no_corpus` holds
  without a sample.
- **The shipped rate is zero, and that is the decision.**  The abstract says
  a random sample still receives deep analysis and never says how large a
  sample is.  D110's argument applies unchanged: a number here would be
  policy no commit recorded and no calibration chose, and every deployment
  would inherit it silently.  So `default_draw` is the same shape as
  `default_band` and `default_profile` -- an argument, built per call from a
  committed constant -- and **the test that pins the zero is meant to fail**
  when the constant is filled in, because filling it in is a change to
  record against `RULESET_VERSION` (D22).
- **The distribution claim is statistical, and says so.**  The share drawn
  over 10 000 ids is asserted to sit within five binomial standard
  deviations of the configured rate, at two rates.  A fixed secret gives one
  fixed count, so a tighter band would only ever have fitted the number
  observed today; the binomial band is a claim about the draw, not about
  this corpus.  The edges are held exactly instead.
- **It escalates and stops nothing, and needs nothing to have run.**  It
  reads the id alone, so it fires on a context whose `r1` is `None` and whose
  claims were never made -- the one trigger of the four that a cascade can
  answer before any stage has produced anything.

**What this forbids**

- Drawing from `random`, `secrets`, the clock, or any per-call state, or
  re-drawing a case a caller asks about twice.
- Committing a secret, defaulting one, or accepting a key that is not bytes.
- Shipping a rate, or reading one from a file or an environment, so that a
  deployment could retune it with nothing recording the change.
- Writing a reason that quotes the secret or the screening id.  The reason
  names the rate, which is the policy an officer reads.
- Reusing a bare `hash(id)` in place of the keyed draw.

**Consequences.**  **The shipped draw escalates nothing**, exactly as the
shipped profile does in 14.7: a deployment that configures no rate gets the
abstract's other triggers and no more.  **A deployment must supply a secret
from outside the package**, and nothing reads one today, so the check is
unreachable from a live cascade -- where 14.6's and 14.7's wiring belongs,
beside the gate that asks all four independently.  **No `ScreeningContext`
field moved**: the draw reads the id the context already holds.

**Revisit only if** the escalation gate (14.9) needs to know whether a case
was drawn without re-running the draw, which would put the outcome on the
context, or if a deployment wants the rate in configuration rather than in
the ruleset, which would make it a settings value that the ruleset version
has to name.


## D112 -- The fourth trigger reads the depth off the context and takes no argument

The abstract lists four reasons a document proceeds to Tier 2, and this is the
fourth: the document proceeds "if the checkpoint is running in full-depth
mode".  `check_full_depth` answers that one question and nothing else.  Four
things came out of writing it, and three of them are refusals.

- **The mode is read off `context.depth_mode`, not passed in.**  The record
  already carries the depth of the checkpoint, and D104 made the field
  required so no context can assume `STANDARD`.  A `mode=` keyword would let
  a caller ask what a screening nobody is running would do, which is a
  question the gate must not be able to ask.
  `test_the_mode_is_read_off_the_context_and_is_not_a_parameter` holds the
  signature down to its one parameter.
- **`FULL_DEPTH` is imported from `app.pipeline.orchestrator`, never
  re-spelled.**  The D104 rule is that the depth vocabulary and the capture
  vocabulary are held disjoint, and a second copy of `"full_depth"` written
  here would be a second place to grow a third depth.
  `test_the_fourth_trigger_never_reads_a_capture_mode` holds the two sets
  apart where this trigger reads one of them.
- **The vocabulary is refused by the record, not again here.**
  `ScreeningContext` already refuses a `depth_mode` naming nothing known with
  a `ContextValueError`, and D104 says that check is load-bearing for this
  task in this direction: a mode nothing recognises must not read as a
  standard one.  Repeating the membership test here would be the
  `_check_parsed_document` second opinion about a question that has an owner,
  so this trigger carries no `:raises FlagValueError:` clause and is the only
  one of the four that refuses nothing at all.
- **There is no shipped constant and nothing to configure.**  14.6, 14.7 and
  14.8 each ship a value on purpose: a band with real edges, and two empty
  lists and a zero rate that name a policy nobody recorded (D110, D111).
  This trigger has no such value.  `FULL_DEPTH` is a depth the context either
  is or is not, so there is no number to fill in and no test meant to fail
  when one is.  A `default_full_depth()` would be a function returning its
  own argument, and it is deliberately absent.

**What this forbids**

- Passing a mode in, or reading one from a file, an environment or a settings
  object, so a deployment could retune the depth of a box with nothing
  recording the change.
- Writing a reason that quotes the document claim, the issuing state, the
  screening id, or anything else the traveller brought.  The reason names the
  mode, which is the only reason here.
- Treating the mode as anything but the field the context already owns:
  reading `Screening.mode`, a capture mode, or a third depth name.
- Making this trigger stop the cascade.  It escalates and nothing else, as
  `test_a_full_depth_escalation_hard_fails_nothing_and_changes_no_score` holds.

**Consequences.**  **All four of the abstract triggers now exist**, and none
is wired into `run_cascade`: each is a function a caller runs against a
record the cascade produced, and the gate that asks all four independently is
still to be written.  **This is the one trigger that escalates out of the
box** -- unlike the two empty lists of the profile and the zero rate of the
draw, a checkpoint configured at full depth escalates every screening today,
because the abstract states the behaviour of that mode rather than leaving it
to a deployment.  **No `ScreeningContext` field moved**: the mode was already
required, already checked, and already carrying the D104 vocabulary.

**Revisit only if** the gate wants the four answers at once and needs this
one reportable without asking, which would put the answer on the context
rather than on the list of reasons, or if a third depth is ever recorded,
which changes what "no other depth escalates" means and so changes
`test_the_trigger_escalates_for_full_depth_and_no_other_depth`.

---

## D113 -- One trace row per stage that ran, and the answer carries it beside the names

ackend/app/pipeline/orchestrator.py holds StageTrace(stage, started,
elapsed, flags_added, escalated), frozen, and CascadeResponse(ran, trace),
also frozen.  
un_cascade appends one row to context.stage_trace as each
stage returns, and returns a response carrying the rows beside the names it
already returned.

**Context.**  14.1 put stage_trace on the record as list[Any] and said so
openly: D104 left the list untyped because the shape was this task to write.
D105 went further and said the registry could not be checked against the tree
by a test, so what would hold that map honest is the trace recording the name
that actually ran.  Both debts land here, and eight things came out of it.

- **One row per stage that ran, appended as the stage returns.**  D107 rule
  stands unchanged: a stage a hard fail kept out is absent from the answer, so
  it is absent from the trace too.  Recording it as skipped would make the trace
  and 
an two answers to one question.
- **The row names the registry key, not the callable.**  That is the whole of
  D105 to have been for: a name mapped to a callable that was renamed imports
  fine, and the row is what says which key ran.
- **lags_added is the growth of context.flags across the one stage.**  It
  is read before the stage and after it, so it counts what that stage left
  behind and cannot absorb a finding another stage wrote.
- **escalated is read off the reasons at the moment the row is written**, and
  is never stored beside them as a second bool (D109).  A row therefore records
  when the run was escalated, so a trigger firing in a later stage does not
  rewrite the rows before it.
- **The clock is 	ime.perf_counter, and it is a keyword.**  A monotonic
  reading cannot run backwards when the wall clock is adjusted, and no wall
  clock is written beside it because the screening already carries a timestamp
  and two timestamps for one moment is one too many.  The keyword exists so a
  test can pin the arithmetic; nothing ships that retunes it.
- **stage_trace is now typed list[StageTrace].**  D104 forbade typing the
  list to a shape this task had not written, and this is the task that wrote
  it, so the reservation is discharged rather than overridden.
- **The answer keeps the names beside the rows.**  CascadeResponse.ran is
  D107 to the word; 	race is the new half beside it.  Deriving the names from
  the rows instead would have left D107 recorded answer as a second spelling of
  the trace.
- **Both records are frozen, for the reason a flag is.**  A row is a record of
  what happened, and a record that can be edited afterwards is the tidied
  version of itself.

**What this forbids**

- Recording a stage that did not run, or recording one as skipped.
- A second clock, or a wall-clock timestamp beside the elapsed seconds.
- A stage writing its own row, or the trace being anything but rows of this
  shape.
- An escalated bool stored beside the reasons, or a row carrying one written
  by anything but the cascade.
- lags_added counting findings the stage did not add.

**Consequences.**  **The trace is written and nothing reads it yet**: no route
builds a ScreeningContext, so the cascade runs only under test and D107 two
cascades still stand.  **
un_cascade returns a CascadeResponse rather than
a bare tuple of names**, so the five assertions in 	est_tier0_stage.py and
	est_tier1_stage.py that pinned the tuple now read .ran; the claim is
D107 to the word and only its spelling moved.  **A stage that raises leaves no
row**, because the row is written after the stage returns, which is the seam
14.11 closes.  **Tier 2 has no stage of its own to trace yet**: the shipped
registry reads quality, tier_0, tier_1, so
	est_the_trace_reads_tier_0_then_tier_1_then_tier_2 runs the three tiers
through a stand-in registry and 15.1 is what registers the deep analysis tier.

**Revisit only if** a stage is registered that runs beside another rather than
after it, which would make started and the order of the trace mean something
else, or the trace is to be anchored in the audit record, which would need a
canonical serialisation and a wall clock this decision does not write.


---

## D114 -- A stage that raises is traced as failed, and the cascade runs on

backend/app/pipeline/orchestrator.py runs each stage through a private
_run, which catches Exception and answers whether the stage returned.  The
row is written either way, carrying a sixth field, `failed`.

**Context.**  D113 named the seam this closes: the row was written after the
stage returned, so a stage that raised left no row and took the rest of the
cascade with it.  One broken check must not lose the whole screening.

- **The row is written whether or not the stage returned.**  A stage that
  raised did run, so it is absent from nothing: it is in `ran` and in the
  trace like any other, and `failed` is what says how it went.  Recording it
  as skipped would be D113's second answer to one question.
- **`failed` is a bool beside the other five, never a reason.**  D106 keeps
  a broken check's own words off the record so an internal detail cannot
  reach an officer, and this is that rule one tier up: the row says the
  stage failed and never carries the exception.
- **Only Exception is caught.**  A KeyboardInterrupt or SystemExit still
  stops the run, because a shutdown is not a broken check.
- **A hard fail still stops the cascade.**  Isolation and D107's one stop
  are not rivals: a stage that wrote `hard_fail_reason` and then raised is
  traced as failed and keeps the stages after it out.
- **What the stage left before it broke still counts.**  `flags_added` is
  read across the stage as before, so a finding written before the raise is
  a finding rather than a casualty of the raise.

**What this forbids**

- An exception escaping `run_cascade`, or its message reaching a row.
- A stage kept out of the trace because it raised.
- Isolation swallowing a BaseException, or overriding the hard fail.

**Consequences.**  `test_stage_trace.py` holds the isolation tests, and the
row-shape test grew from five fields to six.  **A broken shipped stage is
now quiet**, which is the trade: the run completes and the trace says which
stage failed, and nothing reads that trace yet (D113).

**Revisit only if** the trace is anchored in the audit record, where a stage
recorded as failed has to carry enough to reconstruct why, or if a stage
that raises is ever meant to stop the cascade rather than be traced.
"""

---

## D115 -- An empty Tier 2 registry is an answer, and a module is not caught twice

backend/app/pipeline/tier2/base.py holds `DeepModule`, the `DeepRun` record, and
`run_deep_modules`, which runs every module in `DEEP_MODULES` and answers a
`DeepRun` naming what ran beside what each said.  The registry ships empty.

**Context.**  D114 left Tier 2 with no stage of its own and no seam to hang one
on; 15.1 is that seam.  Its verification names the state worth settling first,
a registry holding zero modules.

- **The registry is read-only and holds none yet.**  A mapping proxy, as
  `STAGES` and `DEFAULT_ENGINES` are, so the set a screening draws from cannot
  be widened by a caller.  The first module behind it is 15.3's.
- **Zero modules is a `DeepRun` with nothing in it, not a refusal.**  D86's
  rule one tier up: an absent capability stays visible.  Raising here would
  report a wiring mistake on a box that is merely unconfigured, and the caller
  could not tell the two apart.
- **An empty run is not a clean document.**  An empty `ran` says no deep module
  was configured.  15.9 makes the same demand of a missing stamp template, and
  15.7 is what holds a clean document near zero.
- **A module that raises is not caught here.**  D114 isolates a broken stage
  inside `run_cascade`, one level up, and a deep module is reached through that
  cascade.  Catching a second time here would hide the failure from the trace
  row whose whole job is to record it.
- **`DeepResult` is forward-referenced, not defined.**  15.2 owns that record,
  and the annotations here are strings so this task does not spend it.

**What this forbids**

- `run_deep_modules` raising on an empty registry.
- A caller adding to `DEEP_MODULES`.
- An exception from a module caught twice, or its words reaching a row.
- An empty `DeepRun` being read as a pass.

**Consequences.**  `test_tier2_base.py` holds the tests, 8 of them.
**`DeepModule.run` is not the seam the cascade runs**, and Tier 2 still has no
stage in `STAGES`, so nothing calls `run_deep_modules` outside a test and the
`tier_2` trace in `test_stage_trace.py` is still a stand-in.

**Revisit only if** a module holds state that cannot be built once at import,
which is `DEFAULT_ENGINES`'s reason for module-level engines and would argue for
a factory, or if an empty run ever has to reach an officer as more than an
absence.
"""
---

## D116 -- A deep result names who produced it, and refuses to be clipped

backend/app/pipeline/tier2/base.py holds `DeepResult`, the record every
`DeepModule.run` answers with: `module`, `score`, `is_stub`, `model_version`,
`detail`, and `heatmap` and `regions`.  Its verification names the state worth
settling first, a result produced by a stand-in.

**Context.**  D115 shipped the seam and forward-referenced this record, naming
15.2 as its owner.  Every Tier 2 module from 15.3 on answers one of these, and
the tasks require that a stand-in be labelled rather than shipped as a
detector.

- **`is_stub` and `model_version` have no default.**  Every other field may
  have one; these two may not, because the failure they guard against is a
  module that forgets to label itself.  A default would make the dishonest
  answer the shorter one to write.
- **A stub's score is never evidence that a document is clean.**  A stand-in
  that answers `0.0` has measured nothing, and `is_stub` is what tells a caller
  that.  This is D86's rule one level down: an absent capability stays visible.
- **An empty `heatmap` or `regions` means the module produced neither.**  It is
  not a map of zeros and not an all-clear.  A caller that renders an overlay
  must decide what it draws over nothing.
- **`score` is the module's own confidence, not a probability of forgery**, the
  same split `EvidenceFlag.value` makes, and it is a real number in `[0, 1]`.
- **Nothing is coerced.**  A malformed field raises `DeepResultError`, a
  `ValueError`, on D6's rule: a clipped `1.4` reads stronger than the finding
  that was measured.  `True` is refused for `score` and `is_stub` alike, since
  it is a real number in Python and not a confidence.
- **`heatmap` is rows of `[0, 1]` numbers of one width, and `regions` are
  whole-pixel polygons.**  Reusing `MIN_REGION_CORNERS` and `EvidenceFlag`'s
  corner rule is what lets 15.13 hand a region straight to a flag.  A ragged
  grid is refused because no overlay draws on one.
- **Frozen, for `DeepRun`'s reason**, and a message names the rule broken and
  never repeats the value, which is where a heatmap's numbers would otherwise
  land.

**What this forbids**

- A `DeepResult` built without saying whether a model did the work.
- A stub's score being read, on its own, as a clean document.
- An empty heatmap being drawn as an all-zero map.
- Clipping a score or a heatmap cell into range instead of refusing it.

**Consequences.**  `test_tier2_result.py` holds the tests, 15 of them.
`DeepRun.results` and `DeepModule.run` are annotated with the real class now
that it exists.  Nothing constructs a `DeepResult` yet, because
`DEEP_MODULES` is still empty; the first module to do so is 15.3's.

**Revisit only if** a module needs to hand back a raw numpy array rather than
rows of numbers, which would move the map off the record and into a converter,
or if a module ever has to answer "I could not run" as distinct from "I ran and
found nothing", which today would be a `DeepResult` whose `detail` says so.
## D117 -- ELA normalises against a committed ceiling, and ships labelled

backend/app/pipeline/tier2/ela.py holds `ela_heatmap` and `ELAModule`, the first
module behind 15.1's seam and the first to build the record 15.2 froze.  It
re-encodes the working frame at JPEG qualities 75, 85 and 95, takes each
quality's per-pixel discrepancy, averages those per 8x8 block, and normalises
the block means into the heatmap it answers with.

**Context.**  D116 forward-referenced this record's owner and named 15.3 as the
first module to construct a `DeepResult`.  Nothing in the tier was calibrated
against ground truth, and a tamper map drawn over a document is the most
convincing thing this project can get wrong, so the argument below is mostly
about what the map must not claim.

- **The map is normalised against `SATURATION`, not against its own maximum.**
  A block whose mean amplified discrepancy reaches `SATURATION` (60.0, which is
  `AMPLIFY` times three gray levels) reads fully hot, and the map is clipped
  there.  Dividing by the largest block on the page would instead stretch
  whatever that page happened to be worst at across the full scale, so a clean
  capture's own noise would paint its whole surface at 1.0 -- a cell claiming
  certainty because the normalisation was fitted to it.
- **A cell is one JPEG block, and a partial block is dropped.**  `BLOCK_SIZE` is
  8, the unit the codec actually coded, and the remainder along an edge is not
  averaged over fewer pixels than its neighbours.  A ragged grid is what D116
  refuses to hold, so the seam between a cell of 64 pixels and one of 8 would
  have been invisible until a caller drew it.
- **The several qualities are averaged, not maxed.**  Ringing around an edge is
  present at every quality and is evidence of nothing, and a per-block maximum
  would promote it to a finding the moment one quality happened to ring
  hardest.  Averaging damps what every codec does and leaves the blocks that
  disagree for a reason.
- **`score` is the worst block on the map.**  One comparable scale is what 15.6's
  fusion needs; a share of hot blocks would score a large, local, obvious edit
  below a page-wide faint one, which is the wrong order for a border document.
- **ELA measures re-compression, not tampering, so it ships `is_stub: true`.**
  The qualities, the amplification and the ceiling are this repository's
  choices and nothing here is calibrated against labelled data, so
  `model_version` is `ela-v0` -- the rule's own version -- and `detail` names
  the qualities, the worst block, and the share above `HOT_LEVEL`.  D116's
  `is_stub` is true for a stand-in rather than for a method, and under-claiming
  is the safe direction of the two: the shipped weightset already calls every
  Tier 2 module a labelled stub.
- **`regions` is left empty.**  15.13 is the task that turns a heatmap into
  polygons, and a region derived here would be a second answer to that
  question.
- **A frame ELA cannot measure is refused with `ELAError`, never answered as a
  clean page.**  That is no quality at all, a quality outside `[1, 100]`
  (OpenCV clamps rather than refuses, so 500 would quietly measure 100), a
  frame too small to hold one whole block, and a frame that is not a non-empty
  8-bit array.  Rescaling a float frame silently would have been a measurement
  of a different picture, which is the one failure this map cannot detect.
- **The module is shipped and is not registered.**  `DEEP_MODULES` stays empty
  (D115), so a screening that ran Tier 2 does not claim that one of three
  modules stood behind it; 15.6 is the task that fuses them and the one that
  belongs to wiring the set.
- **Nothing about the capture reaches the record but numbers.**  The heatmap is
  a grid of floats in `[0, 1]`, an error message names the rule rather than the
  frame, and no ELA call logs (D5's rule, and the reason this map is not a
  ledger entry).

**What this forbids**

- Normalising the map by its own maximum, or clipping a ceiling that was fitted
  to the capture in hand.
- Reading a hot block as evidence of tampering rather than of re-compression.
- Answering an unmeasurable frame with an empty or all-dark map.
- Registering one module of three and letting `ran` claim the tier.

**Consequences.**  `test_tier2_ela.py` holds the tests, 21 of them, over
synthetic captures: a soft gradient page written once at quality 95, with one
region replaced by the output of a second encoder at quality 30.  The task's
own verification is the contrast between that region and a control region of
the same size on the same page, because a real capture's text rings under
every quality and an absolute reading would prove nothing.  **ELA has still
never run on a real capture**, and no route calls `run_deep_modules`.

**Revisit only if** a calibrated ELA with labelled thresholds replaces these
constants, which would let `is_stub` flip and would make the ceiling a
measured number rather than a chosen one, or if 15.13 wants block rectangles
from the module itself rather than deriving them from the heatmap.
## D118 -- Noise residual measures each block against the page's own median noise

**Context.** 15.3's ELA needs a second codec to disagree with. Noise residual
needs only the capture: a spliced or re-encoded region carries the noise of the
source it came from, so its high-pass residual has a different variance from the
blocks around it.

**Decision.**

- **The baseline is the page's own median block variance, and the departure is
  the log-ratio, so the map is relative rather than absolute.** A capture's
  absolute noise is set by its scanner, its lighting and its encoder, none of
  which this repository can calibrate, and D117's committed ceiling would be a
  second such guess. Dividing each block by the page's own median makes the one
  comparison that is available offline, and it is the comparison the evidence
  supports: a block that differs from its own neighbours is inconsistent with
  them, whatever the page's overall noise level happens to be.
- **`ANOMALY_FACTOR` is 8.0, measured rather than chosen.** Four synthetic
  captures were probed first. On an untouched grainy page written once at
  quality 95, the worst block sat 2.0x the median, which reads 0.28 on a
  factor of 8. A region blurred until its grain collapsed sat 0.05x the median,
  and a region given extra grain sat 5.7x. So 8x is four times past what a
  capture's own noise produces, and an edit in either direction saturates.
- **The departure is symmetric**, so a denoised splice reads as anomalous as a
  noisier one. Only the smoother direction was the common finding in the
  literature when this was written; nothing in these probes shows the noisier
  direction is uninformative, and refusing it would hide half of what the
  measurement sees.
- **The high-pass is a median filter, not a mean.** A document is full of edges
  and a mean high-pass answers those edges rather than the noise underneath them.
- **`VARIANCE_BLOCK` is ELA's `BLOCK_SIZE`.** The two maps then overlay cell for
  cell, which is what 15.6's fusion needs.
- **A page carrying no measurable noise is refused with `NoiseResidualError`,
  never answered as a clean page.** With every variance at zero there is nothing
  to depart from, and a ratio against zero is not a measurement. This is the
  one degenerate case the probes surfaced that a synthetic test image walks
  straight into.
- **`to_gray` is repeated rather than shared with ELA.** Sharing it would make
  this module's refusals `ELAError`, so a caller catching one could mistake a
  frame this module can measure for one it cannot.
- **The module is shipped and is not registered.** `DEEP_MODULES` stays empty
  (D115) for the reason D117 gives: 15.5 and 15.6 are still ahead, and a
  two-of-three registry would let `ran` claim the tier stood behind all of it.
- **`HOT_LEVEL` is ELA's, 0.5**, so 15.6's fusion reads both modules on one line.
- **Nothing about the capture reaches the record but numbers**, by D117's rule.

**What this forbids**

- Dividing by an absolute noise ceiling, or by the map's own maximum.
- Reading an anomalous block as evidence of tampering rather than of local
  inconsistency.
- Answering a noiseless page with an all-dark map.
- Registering two of three modules and letting `ran` claim the tier.

**Consequences.** `test_tier2_noise_residual.py` holds the tests, 34 of them,
over synthetic captures: a grainy gradient page written once at quality 95, with
one region blurred until its noise collapsed and another given grain it did not
have. The task's own verification is the contrast between the blurred region and
a control region of the same size on the same page. **Noise residual has still
never run on a real capture**, and no route calls `run_deep_modules`.

**Revisit only if** a calibrated noise model replaces these constants, which
would let `is_stub` flip, or if 15.6's fusion finds the two modules disagreeing
so often that the shared `HOT_LEVEL` has to become two.

## D119 -- Copy-move believes a translation only when enough keypoints agree on it

**Context.** 15.5 needs to say where a capture repeats itself. A document is
already full of self-similarity -- ruled lines, a letterhead, a table's repeated
rows -- so the measurement has to separate that from a region pasted from one
place to another, or it reports every page as forged.

**Decision.**

- **A translation is called a copy only when `MIN_COPIES` keypoint pairs agree
  on it.** This is the whole discriminator, and it is measured: on an untouched
  synthetic page the largest group of pairs agreeing on one translation is 3,
  while the same page with a 150x150 region pasted elsewhere reaches 121. Eight
  sits in the gap. Clustering the shifts before deciding anything is also what
  makes the answer cheap to read -- the copied page's largest group is 40x its
  own clean page's.
- **The detector is SIFT, not ORB.** Both separate a copied page from a clean
  one at these settings, but SIFT reaches it with 869 keypoints where ORB needs
  4245, and `cv2` 4.14 carries it in the main package rather than contrib.
- **`RATIO = 0.6` on the nearest match against the runner-up, with the keypoint
  itself excluded.** Self-matching returns every keypoint as its own nearest
  match at distance zero, so the diagonal is dropped before the two rivals are
  taken; a page's own nearest rival is then a genuine second place.
- **`MIN_SHIFT = 24.0` pixels is the floor on a translation.** A keypoint
  matched to its own immediate neighbourhood is the same structure twice over,
  not a second copy. Measured at 16 and 24 the result is identical, so 24 is
  taken as the safer of two equal answers.
- **`SHIFT_TOLERANCE = 16.0` bins two shifts into one translation**, absorbing a
  detector's localisation error. Measured: below this the copied page's
  agreement fragments across neighbouring bins, at it the one real translation
  separates cleanly from every spurious group.
- **`SATURATION = 4.0` agreeing pairs in a block is a fully hot cell.** In a
  copied page the most common block carries 4 pairs and the busiest carries 6;
  in the untouched page no block carries any, so the scale separates them
  completely. The ceiling is committed rather than taken from the page's own
  maximum, by D117's rule, so two captures are read on one scale.
- **`HOT_LEVEL` and `BLOCK_SIZE` are the other two modules'.** All three maps
  then overlay cell for cell and read on one line, which is what 15.6's fusion
  needs and what D117 and D118 each arranged.
- **`REGION_MERGE = 48.0` pixels groups matched keypoints into a box.** Measured:
  the two ends of a copy stay two separate boxes anywhere from 32 to 128 pixels
  of merge radius, so 48 sits inside a wide plateau rather than on its edge.
  Polygons follow `_box_polygon`'s promise -- clockwise from the top left, far
  corner exclusive, plain integers -- because that is the one writer whose
  corner order the record treats as a promise.
- **`to_gray` is repeated rather than shared.** Three modules, three error
  types, so a caller catching one cannot mistake a frame it can measure for a
  frame another cannot.
- **Translation only.** A scaled, rotated or mirrored duplicate is a different
  measurement, is not attempted here, and is not claimed.
- **A capture with too little texture to match is refused with `CopyMoveError`,
  never answered as a page with no copy in it.** With no features there is
  nothing to match against itself.
- **The module answers `regions` where ELA and noise residual leave them
  empty.** The other two read a pixel map and can only say where it went hot;
  copy-move knows which keypoints matched, so its boxes are where the copy
  actually is rather than a threshold's edge. 15.13 still owns turning a
  heatmap into flags.
- **The module is shipped and is not registered.** `DEEP_MODULES` stays empty
  (D115) for D117's reason: 15.6 is still ahead, and a three-of-three registry
  would let `ran` claim the tier stood behind all of it.
- **Nothing about the capture reaches the record but numbers and whole pixels**,
  by D117's rule.

**What this forbids**

- Calling one self-similar pair a copy-move, or dividing a map by its own
  maximum.
- Reading a repeated region as proof of tampering rather than of repetition: a
  letterhead, a repeated table row and a forged duplicate are one finding to
  this measurement, which is why `is_stub` is set and the detail says so.
- Claiming scaled, rotated or mirrored copies.
- Registering three of three modules and letting `ran` claim the tier.

**Consequences.** `test_tier2_copy_move.py` holds the tests, 46 of them, over a
synthetic textured page written once at quality 95 with one 150x150 region
pasted elsewhere and the file written again. The task's own verification is
that both ends of the copy are named as boxes, and that the rest of the page is
dark. **Copy-move has still never run on a real capture**, and no route calls
`run_deep_modules`.

**Revisit only if** a rotation- or scale-invariant matcher replaces this one,
which would widen what a translation can mean, or if 15.6's fusion finds this
module disagreeing with the other two often enough for the shared `HOT_LEVEL`
to become three.
---

## D120 -- Stamp matching resamples both sides onto one grid, and every committed template is drawn here

**Context.** 15.8 asks for a stamp template registry plus detection and template
matching. Nothing had been said about what a template *is*: a mark on a
document is ink of some colour at whatever size it was printed, so a
comparison has to survive both. It had also not been said whose stamps would be
in the registry, and committing no real mark is not a gap to be filled later by
picking one.

**Decision.**

- **Every template the registry ships is drawn by this repository**
  (`demo_entry_stamp`, `demo_exit_stamp`), and their names carry a `demo_`
  prefix that a test holds. No authority's mark is committed, so a real stamp
  matches nothing here, and the module's `detail` says so in the sentence an
  officer reads. Committing a real stamp later is the deployment's call, not
  this module's.
- **Detection proposes and matching disposes.** `find_stamps` returns every
  component of chromatic ink that is big enough, and `detect_stamps` reports
  only those a template explains. This is the whole of the realistic false
  positive: a colour photograph is *proposed* and then declined, and a detector
  that never proposed it could not find a stamp printed beside one.
- **`CHROMA_LEVEL = 55` separates ink from paper.** Measured: a grayscale page
  has a chroma of exactly 0 everywhere, a colour photograph reaches 94, and the
  stamp's ink reaches 148. Below 55 the photograph survives as a component; at
  55 it is gone and the stamp's component is unchanged, so the line is placed
  on the gap rather than on a round number.
- **`CLOSE = 15` joins one mark into one component.** A ring, a star and its
  lettering are three components before the mask is closed and one after, and a
  mark reported as three findings is not a mark.
- **`MIN_INK = 1000` and `MIN_SIDE = 40` are what a stamp is not.** A print too
  small for the grid is not offered rather than offered and refused, because a
  caller holding a match computed from a stamp smaller than the comparison is
  worse than holding none.
- **Both sides are resampled onto one `CANONICAL = 64` grid before they are
  compared**, which is what makes the printed size irrelevant. Measured on a
  mark genuinely rescaled rather than redrawn, the right template correlates at
  0.987 to 0.9997 across printed sizes from 0.6x to 1.4x, and the wrong one at
  0.636 to 0.663, so `MATCH_LEVEL = 0.75` sits in a gap roughly 0.09 wide on
  each side.
- **The resampling is what made the earlier attempts fail, and a fixture was
  the reason.** Resizing the template to the candidate and sliding it over a
  padded window were both measured first and both read a mark 10% off its
  authored size as the *other* mark. The cause was the probe, not the matcher:
  it rebuilt the mark at each size, and redrawing a mark changes its relative
  stroke widths, so no scale-normalising method could succeed. A probe can only
  tell you about the fixture you probed.
- **A template is cropped to its own ink, and `make_template` reads the raw ink
  extent rather than `ink_mask`.** This was a defect this task found by reading
  its own module back: cropping the template to the *closed* mask gave it a
  border the candidate it is compared against does not have, and the two then
  sat on the canonical grid differently -- the shipped entry mark scored 0.378
  against a page carrying that very mark, and 0.9997 once both were cropped the
  same way. `test_tier2_stamp.py` pins the crop.
- **A grayscale frame is refused with `StampError`, not answered as a page with
  no stamp on it**, by D119's rule. It carries no chromatic ink by
  construction, so an answer would be a claim about the module.
- **The module answers `regions` and leaves `heatmap` empty.** It knows where a
  mark is rather than how hot a pixel map went, so there is no map to draw.
- **`score` is the best match on the page, and `is_stub` is set.** A name for a
  mark this repository drew is not authentication; the detail says "a likeness,
  not an authentication".
- **The module is shipped and is not registered**, on D119's reason: `DEEP_MODULES`
  stays empty so `ran` cannot claim the tier stood behind all of it.
- **An empty match list is a measurement, not a clean page, and an empty
  registry is a third answer again.** `detect_stamps(..., templates={})` returns
  nothing on a page that plainly carries a mark. What that absence must be
  *reported* as is 15.9's task, and this task deliberately left it alone.

**What this forbids**

- Describing a template as an authority's mark, or a match as authentication.
- Treating a proposed candidate as a finding without a template behind it.
- Comparing a stamp at its authored size only, or sliding a resized template
  over a window, since both were measured and both misread an off-size mark.
- Registering four of four modules and letting `ran` claim the tier.

**Consequences.** `test_tier2_stamp.py` holds the tests, 49 of them, over a
synthetic text page written at quality 95 with a mark from the registry pasted
onto it and the file written again. The task's own verification is that the mark
is found and its own template is named, once per mark, and that two marks on one
page are named apart. **No real stamp has ever been recognised**, no route calls
`run_deep_modules`, and the closing kernel can bridge a mark to nearby
chromatic ink and report a box wider than the ink that produced it.

**Revisit only if** real marks are committed to the registry, which is a
deployment decision and widens what a match means, or if 15.9's `not_configured`
answer needs a seam this task's `templates` argument does not already provide.

## D121 -- An empty registry answers `not_configured`, and silence is never a pass

**Context.** 15.8 shipped stamp detection against a committed registry and
deliberately left one thing open: `detect_stamps(..., templates={})` returned
an empty match list on a page that plainly carried a mark, which is the same
answer a page with nothing on it gets. D120 called it a third answer and named
this task as the one that has to say what it is.

**Decision.**

- **`detect_stamps` answers a `StampDetection`, not a match list.** The record
  carries a `status`, the `matches`, and the `proposed` count of candidates the
  detector offered. The return type changed because the distinction cannot be
  carried any other way: two answers that both hold no match are
  indistinguishable as bare tuples, which is the whole of the defect.
- **There are three statuses and `clean` is not one of them.** `matched` says a
  template explained a proposal; `no_match` says every proposal was compared and
  none was explained; `not_configured` says the registry held nothing and
  **nothing was compared at all**. Naming the middle one `clean` would be this
  module's silence read as a verdict on the document, which D115 forbids and
  which no caller should be able to pass by mistyping a string.
- **The status is about the registry and not about the page.** A blank page
  against an empty registry is `not_configured` too, since a measurement nobody
  could make is still a measurement nobody made.
- **`proposed` carries the ink an unconfigured answer had no template for.** It
  is what stops `not_configured` from reading as a page with nothing on it, and
  it removes the module's second pass over the frame.
- **A `not_configured` answer reports no region.** D120's rule holds: nothing is
  reported without a template behind it, so an absent capability reports no
  finding rather than an unlabelled one.
- **The registry is a constructor argument on `StampModule`.** D120 set the
  revisit trigger at a seam the `templates` argument did not already provide,
  and it did, so `StampModule(templates={})` is a configured instance holding
  nothing. The registry is checked once, at construction, rather than once per
  document.
- **`DeepResult` is not widened, and `detail` carries the answer.** The frozen
  record has no status field and adding one is 15.1's seam rather than this
  task's; `detail` is the sentence D116 says is the one an officer reads beside
  the score. The score is `0.0` under every status, which is precisely why the
  wording has to carry the distinction.
- **The shipped registry is not empty and a test holds it.** Both entries are
  D120's `demo_` marks, so `StampModule()` is never unconfigured here.

**What this forbids**

- Answering an empty registry with an empty match list, or any answer in which
  an unconfigured run is indistinguishable from a measured one.
- Naming a status `clean`, or reading `no_match` as a verdict on the document.
- Reporting a region for ink that no template named.

**Consequences.** `test_tier2_stamp_config.py` holds the tests over a page
carrying the entry mark pasted at the size it was authored at, so no figure in
it came from a probe that redrew the mark. 15.8's 49 tests were updated for the
new return type rather than weakened, and the one that pinned an empty
registry's silence now reads `.matches` and points here. **The seam still has no
status field**, so a caller that ignores `detail` can go on reading a zero as a
pass; closing that is 15.1's call and not this task's.

**Revisit only if** `DeepResult` grows a status field of its own, at which
point the four modules should answer through it rather than through a sentence,
or if real marks are committed to the registry and the `demo_` prefix stops
being the honest default.

---

## D122 -- A morph classifier is an interface, its stand-in is labelled at the classifier, and both cue lines are midpoints of measured gaps

**Date:** October 2, 2026. **Status:** settled, task 15.10.

**Context.** 15.10 asks for a `MorphClassifier` interface and a clearly
labelled heuristic stand-in reading "frequency + boundary irregularity cues at
the photo region", with `model_version: heuristic-v0`. Three things were open.
**What the cues actually are**, since "frequency" and "boundary irregularity"
name properties rather than measurements. **Where the label lives**, which D116
settled for the record but not for whatever produced it. **And what the module
measures**, because "at the photo region" is a claim about a rectangle that
nothing on `ScreeningContext` carries.

**Decision.**

- **Two cues, and they move in opposite directions.** A morph is one portrait
  averaged with another, so `frequency_cue` reads the fine detail that
  averaging cancels (the share of spectral power outside `FREQUENCY_RING` of the
  centre) and `boundary_cue` reads the second outline averaging leaves behind
  (the largest silhouette's shape factor, `perimeter^2 / (4*pi*area)`). A blend
  measured 0.0258 against a clean portrait's 0.0395 on the first and 1.219
  against 1.140 on the second.
- **The score is the mean of the two, not the maximum**, on ELA's rule that a
  maximum promotes one cue to a finding the other would have contradicted. This
  is not stylistic here: **one clean portrait of fifteen measured 1.194, past
  `BOUNDARY_LEVEL`, and on its own it would have been a finding against a
  genuine traveller.** The frequency cue separated every clean portrait from
  every blend; the boundary cue did not, and it is kept because it catches what
  the frequency cue catches least.
- **Every cue is read on one canonical 64px grid.** Read on the capture as
  photographed, the frequency share is not a property of the portrait at all:
  it fell from 0.0397 at 80px to 0.0039 at 240px across four sizes of the
  *same artwork*, so any constant sat against it would describe the scanner.
  D120's answer to exactly this problem was a canonical grid and it is the same
  one, held again rather than shared on D38's rule.
- **Every line is the midpoint of a gap the probe measured, not a round number.**
  `FREQUENCY_LEVEL` 0.0345 sits between the lowest clean share observed (0.0352)
  and the highest blend (0.0338); `BOUNDARY_LEVEL` 1.162 between 1.146 and
  1.178; `SUSPECT_LEVEL` 0.221 between the worst clean portrait on 30 the probe
  had not been tuned on (0.128) and the weakest blend (0.314). Each span is the
  distance from its line to the most extreme case observed in the flagged
  direction. **`BOUNDARY_LEVEL` is the weakest of the three and did not hold on
  the held-out set**, which is why the mean is load-bearing and why the test
  pins a clean portrait sitting over that line rather than pretending it does
  not.
- **`model_version` and `is_stub` are attributes of the classifier, not of the
  module.** `MorphModule` copies them off whatever classifier it holds, so a
  trained model swapped in behind the same interface answers
  `arcface-morph-v3` and `is_stub: false` without the module's code changing.
  D116 froze the record, and this keeps the label travelling with the work
  rather than with the wrapper.
- **The module refuses a classifier that cannot say what it is,** at
  construction, on 15.9's rule that a seam checked per document is a seam
  checked too late.
- **The region is a constructor seam, and the default is named rather than
  implied.** `region_of` defaults to `whole_frame`, because nothing on
  `ScreeningContext` says where a document's portrait is. A caller holding an
  aligned frame and a template hands in `face_align.photo_region` instead. **An
  earlier draft claimed to read "the photo region" off the context and would
  have been claiming a measurement it did not make**; the record now says which
  region this instance was pointed at.
- **`boundary_cue` refuses a region with no closed outline** and `NO_FACE` names
  that answer, because a cue over a region with nothing in it is a measurement
  of the region.
- **These cues do not know what a face is, and this repository cannot fix that
  yet.** Measured on purpose: a block of body text read 0.500 and a checkerboard
  0.445, both suspect. **The limit is in the `detail` sentence**, since that is
  what an officer reads, and it is why nothing here is a pass in either
  direction.

**What this forbids**

- Reading either cue off the capture as photographed, or against any constant
  that was not measured on a synthetic pair first.
- Taking the maximum of the two cues, or letting the boundary cue alone raise a
  finding.
- A module that reports `heuristic-v0` and `is_stub` for a classifier that
  answered, or that lets a classifier in without saying what it is.
- Wording a score of 0.00 as a suspicion. D121's rule holds one level up.
- Claiming to have measured the photo region off a context that does not carry
  one.

**Consequences.** `test_tier2_morph.py` holds 28 tests, including the two the
task names and one that pins a clean portrait sitting over `BOUNDARY_LEVEL`.
The fixture **resizes the artwork it already has** rather than redrawing it, on
15.8's lesson that redrawing changes relative stroke widths and would make an
unstable method look stable for the wrong reason. **`DEEP_MODULES` is still
empty and a test pins it**, as 15.3-15.5 and 15.8-15.9 each did. **The seam
gained no status field**; the refusal raises, which is D115's rule.

**Revisit only if** a real morphing attack set replaces the synthetic pairs,
at which point all five constants are chosen lines rather than measured ones
and the suspect line in particular has never met a document that was not drawn
by this repository, or if a face detector lands, at which point the text-block
and checkerboard readings above stop being this module's problem to own.

---

## D123 -- A deepfake classifier is an interface, its one cue is a share of exactly-flat gradients, and the second candidate was rejected on its numbers

**Date:** October 2, 2026. **Status:** settled, task 15.11.

**Context.** 15.11 asks for a `DeepfakeClassifier` interface and a labelled
heuristic stand-in, "with the same stub test". D122 settled that shape for a
morph, so the interface is not open: the label belongs to the classifier, the
module copies it onto the record, and a stand-in refuses to answer otherwise.
**What the cue is, was open**, and unlike 15.10 the task named none. Four
candidates were probed and one survived, which is a thinner result than D122's
two cues and is recorded as such.

**Decision.**

- **One cue: `flat_share`, the share of adjacent-pixel gradients that are
  exactly zero.** A deepfake is a portrait no camera saw, so unlike a morph --
  two real captures averaged, and so still carrying a real sensor's grain -- it
  carries none, and a capture's own noise fills almost every gradient in. The
  cue is a **share**, on D120's principle that a share is scale-stable where an
  absolute level is not.
- **`GRADIENT_LEVEL` 0.1706 is a measured gap midpoint.** Across 840 clean
  captures and 700 reconstructions the highest clean share was 0.1482 and the
  lowest reconstructed 0.1931; the midpoint sits in a gap nothing observed
  occupies. `GRADIENT_SPAN` 0.7712 is the distance from the level to the most
  extreme reconstructed share measured, 0.9418.
- **`SUSPECT_LEVEL` is 0.0116, and it is very low.** Normalised, the
  reconstructed group spreads 0.023 to 1.000 against every clean capture's
  exact 0.000, so the midpoint of that gap is 0.0116. **A line this low is a
  false-alarm risk on anything this repository has not drawn**, which is
  exactly what D21 raises about a stand-in reaching High on its own at weight
  65. The line was not raised to a safer-sounding number the probe never
  produced; the risk is recorded instead.
- **A second cue was probed and rejected, and that is why the score is the cue
  itself.** A chroma noise-floor cue -- the share of blocks whose residual
  variance sits far below the median block, read on the two chroma channels --
  separated nothing: on the held-out set clean captures reached 0.250 while
  reconstructions fell to 0.000, and on a re-grain ladder it collapsed to 0.000
  past 2.5 while the surviving cue still fired at 6.0. Averaging it in would
  have **hidden detections rather than damping them**, which is the opposite of
  what D122's mean was for. An earlier noise-floor candidate measured on the
  luma channel inverted the same way at 0.8 of added grain.
- **`model_version` and `is_stub` are attributes of the classifier**, exactly as
  D122 settled for the morph, and `heuristic-v0` is deliberately the same string
  15.10's stand-in uses: `module` on the record is what tells the two apart.
- **A region with no power at all is refused, not scored, and `NO_SIGNAL`
  names that answer.** Blank paper reads a flat share of 1.000 -- the strongest
  possible finding -- so scoring it would report an empty region as a deepfake.
- **The region is a constructor seam defaulting to `whole_frame`**, on D122's
  reasoning that nothing on `ScreeningContext` says where a portrait is.

**What this forbids**

- Reading the cue off the capture as photographed, or against any constant that
  was not measured on a synthetic pair first.
- Shipping a second cue because a mean of two reads better than one, and
  re-probing it when it does not separate.
- A module that reports `heuristic-v0` and `is_stub` for a classifier that
  answered, or that lets a classifier in without saying what it is.
- Wording a score of 0.00 as a suspicion. D121's rule holds one level up.

**The limits, which are the substance of this decision.**

- **This cue reads flatness, not provenance, and no real deepfake has ever been
  scored against it.** A body-text block reads 0.506 and a checkerboard 0.000,
  so it points the wrong way on both non-faces. The limit is in the `detail`
  sentence, because that is what an officer reads.
- **It is a share and so far steadier across sizes, but not size-invariant.**
  Added grain survives the canonical grid less well from a small source: a 120px
  portrait re-grained past about 5.0 reads clean where a 320px one still fires
  at 6.0, and all fourteen misses in the sweep were 120px or 160px sources. The
  clean side does not move -- no clean capture at any size crossed the line.
- **The constants describe this repository's fixture and not deepfakes.** A
  real generative model produces texture, not piecewise smoothness, so this cue
  would plausibly **not fire on a real deepfake at all**. That is the honest
  reading of what was measured and it is why the module ships labelled.

**Consequences.** `test_tier2_deepfake.py` holds 26 tests, including the
verification the task names and four pinning the limits above. The fixture
**resizes the artwork it already has** rather than redrawing it, on 15.8's
lesson. **`DEEP_MODULES` is still empty and a test pins it**, as 15.3-15.5 and
15.8-15.10 each did. Six modules now exist and none is reachable from a route.

**Revisit only if** a real deepfake set arrives, at which point this cue should
be expected to fail and the suspect line becomes meaningless, or if a face
detector lands, at which point the text-block reading stops being this module's
problem to own, or if `DeepResult` grows a status field (D121), at which point
this module answers through it rather than through a sentence.
---

## D124 -- The Tier 2 common scale is a fifteen-number vector, and the outlier line is the fixture's own 95th percentile, not scikit-learn's "auto"

**Date:** October 2, 2026. **Status:** settled, task 15.12.

**Context.** Every Tier 2 module reads its own thing -- a map, a mark, two
cues, one number -- so nothing has ever put two documents on one scale, and
15.6's fusion has had no agreed scale to fuse on. 15.12 asks for a per-document
feature vector over five named families and an IsolationForest fitted on a
committed feature fixture. What the vector holds, what the score means, and
where the line sits were all open.

**Decision.**

- **Fifteen numbers in five families, in a fixed order** (`FEATURE_NAMES`):
  three from ELA pooled over all three JPEG qualities, three from noise
  residual (median block variance, its 95th percentile, their ratio in
  octaves), four from the histogram (mean, standard deviation, ink share under
  level 200, 16-bin entropy), two from edge density (Canny share at 100/200,
  mean Sobel strength), three from field geometry (share of rows and of columns
  holding a straight ink run over a quarter of the frame, and the share of rows
  carrying ink). The families are reused from `ela` and `noise_residual` rather
  than reimplemented, and their refusals are translated into `AnomalyError`.
- **One grid for every capture size.** The document is resampled to 256px on
  its long side and cropped to whole 8px blocks before any family reads it, on
  D120's rule. **A frame under 256px is refused rather than upsampled**, since
  interpolating up measures pixels the capture never held.
- **The score is a rank, not a probability.** `rank` is the share of fixture
  rows *less* anomalous than the document measured, so it is in [0, 1] and
  needs no hand-chosen constant. `raw` is the forest's own `-score_samples` and
  is kept beside it because the rank saturates at 1.0 and would hide how far
  past the fixture a document sits.
- **The fixture ships in the package** at `app/pipeline/tier2/fixtures/clean_features_v1.json`,
  120 rows from 120 clean synthetic pages this repository drew. It cannot live
  beside the tests, because the scorer that reads it is production code. **Its
  header is checked against `FEATURE_NAMES`**, so a reordered fixture is
  refused rather than fitted on: that is a silent wrong answer, not a rounding
  difference.
- **`contamination=0.05`, which is the fixture's own 95th percentile, and
  `"auto"` was measured and rejected.** `"auto"` puts the line at a raw score
  of 0.500 -- the middle of the clean band, not above it -- and called **41 of
  the 120 committed rows and 6 of 12 freshly drawn clean pages** outliers. At
  0.05 the line sits at 0.5498, which calls 6 of 120 and 1 of 12.
- **`"auto"` stays an accepted value.** It is rejected as a *default* on
  measured numbers, not removed from the seam.
- **Per-feature scaling was probed and is deliberately absent.** A forest draws
  each tree's threshold uniformly inside one feature's own range, so dividing
  every column by its spread across the fixture left the probe's clean and
  out-of-distribution scores identical to four decimal places. A normalisation
  step that does nothing was not added.
- **The scorer is labelled.** `is_stub` is `True` and `model_version` is
  `isolation-forest-v0`: a forest really was fitted, but on artwork this
  repository drew, exactly as every other Tier 2 constant. A fit on real
  captures takes a different version string, not a cleared flag.

**What this forbids**

- Reading the score as a probability that a document is forged, or the rank as
  one. It is how unlike the fixture a document is.
- Tuning the line against the documents it must catch. It is the fixture's own
  tail, and it moves when the fixture is regenerated -- which is the point.
- Refitting per document, or on anything not committed and countable.
- Refusing a fixture whose header disagrees, or accepting one quietly.

**The limits, which are the substance of this decision.**

- **Nothing here has met a real document.** The fixture is synthetic artwork,
  the same footing as `SATURATION`, `ANOMALY_FACTOR`, `MATCH_LEVEL`,
  `FREQUENCY_LEVEL`, `BOUNDARY_LEVEL`, `SUSPECT_LEVEL` and `GRADIENT_LEVEL`.
- **Added grain is the measured weakness, and it was measured on purpose.**
  Re-encoding a clean page down to quality 10 leaves it inside the clean band,
  and the odd documents hold, because ELA is part of the vector. But re-graining
  a clean page past sigma 6 pushed it above the line in one case of two, and
  sigma 12 in both. **The line was not raised to hide this**, because raising
  it is what would cost the detections. D123's lesson, hit again from the other
  side.
- **The margin is thin where it should be broad, and thin where it matters.**
  The odd documents clear the worst fresh clean page by +0.030 (an inverted
  page) to +0.104 (a halftone); the clean band itself spans 0.4258 to 0.5779,
  so the line at 0.5498 sits inside the band and one clean page in twelve
  crosses it. **A 1-in-12 false-alarm rate on a fixture drawn by the same
  repository is not a false-alarm rate on a real document.**
- **Not every odd document is measurable.** A flat colour field and a smooth
  ramp are *refused* -- there is no noise to measure a departure from -- rather
  than scored. That is D115, and it means "out of distribution" and "cannot be
  measured" are two different answers.
- **The rank saturates.** Everything past the fixture reads 1.0, which is why
  `raw` is carried beside it.
- **The scorer is behind no seam.** `DEEP_MODULES` is still empty and this task
  registered nothing: a per-document score is not a heatmap, so 15.13's
  region-carrying flag does not follow from it, and the weightsheet id question
  is 15.14's. This is the common scale 15.6 needs, not a stage of its own.

**Consequences.** `test_tier2_anomaly.py` holds 39 tests, including the
verification the task names and the limits above, and draws its clean pages
from the same `_clean_page` the committed rows were measured from.
`scikit-learn>=1.3,<2` is now a backend dependency.

**Revisit only if** real clean captures arrive, at which point the fixture is
regenerated and the line moves with it, or if 15.6 fuses on this vector, at
which point the fusion owns the scale and this module owns nothing else, or if
a document is refused rather than scored often enough to matter operationally,
at which point the refusal needs its own answer in the record.

## D125 -- A Tier 2 result becomes a flag unconditionally, and the region is the strongest place the record can name

**Date:** October 2, 2026. **Status:** settled, task 15.13.

**Context.** Tier 2 modules read five different shapes -- a map, a mark, two
cues, one number, and from D124 a fifteen-number vector -- and none of them had
been turned into anything an officer reads. 15.13 asks for each result to become
a flag with a heatmap-derived region, so a Tier 2 finding is as locatable as a
Tier 0 field's. Three things were open: where a flag's region comes from when
the record may name a place, may carry a map, or may be a single number for the
whole page; whether converting a result is also the place that decides the
result *is* a finding; and what a result that locates nothing should become.

**Decision.**

- **One `DeepResult` becomes one `EvidenceFlag`, unconditionally.** Nothing in
  the conversion decides that a result is a finding, because **a gate at the
  module's own level would fire on an ordinary clean page.** Measured on a
  clean printed page written at JPEG 95, ELA reads 1.0000 with 53.9% of its
  blocks at or above `HOT_LEVEL`, and 100% of them once grain of sigma 20 or 40
  was added. Whether two documents fuse into a verdict is 15.6's question, and
  this module only answers "what did this module say, and where".
- **The region is the strongest place the record can name, in three steps.**
  A box the module located itself wins, because it measured the place rather
  than the map; the first is taken, since the modules carrying both order their
  groups as they found them. Failing that the box is derived from the heatmap,
  and failing that the region is `None`. **A result that is one number for the
  whole page carries neither and answers `None`**, which is a finding with
  nowhere to point rather than a dropped flag.
- **The derived box is the four-connected group of cells at or above the level
  holding the map peak**, so one tampered area is one box rather than one box
  per block of it. A tie keeps the first cell in image order, so a repeated run
  draws the same highlight. A map whose peak is below the level answers `None`
  rather than a box over the frame, which would claim a measurement nobody
  made.
- **The map grid is stretched across the whole frame**, so a frame that is not a
  whole number of blocks still answers boxes inside its own edges.
- **The level a region is drawn at is each module's own constant**, read out of
  the module rather than copied into `RULES`, so a module retuning its line
  cannot leave this table answering for it. `registry` is the seam a caller
  substitutes its own rules through; `RULE_BY_MODULE` itself stays read-only.
  **A level outside the unit interval is refused**, since a line above every
  cell would report the map as carrying nothing.
- **Two numbers read the same measurement.** A module answers one score, so
  `value` and `confidence` both carry it rather than one of them estimating a
  second thing nobody measured. `expected` and `found` are `None`, because a map
  has no expected half, and `reason` is the module's own sentence, which is
  where `is_stub` and `model_version` travel: `EvidenceFlag` has no field of its
  own for either.
- **A result that locates nothing still takes its row**, on the same rule 4.12
  gave Tier 0: no box is not no finding. Flags report `tier=2` and
  `field=None`, since a Tier 2 finding is about the capture and never about one
  printed field.
- **`Tier2FlagError` is a `ValueError`**, as D114 requires of everything Tier 2
  raises, and a module with no rule is refused rather than answered as a module
  that found nothing.

**Measured and left alone.** On the capture `test_tier2_flags.py` draws, the
group of hot blocks holding the ELA peak is the two leftmost block columns of
the rewritten patch, so the box is 16px of a 48px one and sits wholly inside it.
That is the map reading honestly -- the second codec rewrote the most where the
box is -- so the test asserts containment and locality rather than a
half-overlap threshold this fixture never produced.

**Revisit only if** 15.6's fusion needs a per-module gate to keep a weak module
from reporting at all, at which point the gate belongs there and reads the
level these rules already carry, or if `EvidenceFlag` grows a field for a
module's stand-in label, at which point `reason` stops carrying it.
## D126 -- A traveler case is a named group of documents and carries no verdict

**Date:** October 2, 2026. **Status:** settled, task 16.1.

**Context.** Part 16 is cross-document verification, and its first question is
what two documents are compared *against each other* as. Nothing held that
grouping, so 16.1 asked for a `TravelerCase` model and table with three named
columns and left every choice inside them open. Two of those choices would be
expensive to reverse later: what a case's `label` may be, and whether the row
may hold the answer to the comparison its documents are about.

**Decision.**

- **`traveler_cases` carries exactly `id`, `created_at` and `label`, in that
  order, and no more.** A fourth column is a task, not an extension of this
  one. The table is generated into the schema by `be3f9e1a6e14` and is not
  editable from the first migration, on the reason 10.2 gave.
- **`label` is required.** A case is reached by an officer looking for one
  traveller's paperwork (24.11), and a nullable label makes a row that is
  reachable by no name at all. This is the same reasoning 8.4 applied to
  `document_type` and `filename`: the columns a caller cannot write a row
  without are the ones that say what the row *is*. The refusal is the
  database's rather than a check in the model, so `nullable=False` is what
  makes it real on both backends.
- **The label is caller-supplied text and is never indexed.** `Screening.filename`
  sets the precedent and the reason: a search over officer-typed text is a
  scale claim nothing in this project measures, and 24.3 moves search to
  server parameters against `screenings`, not against this table.
- **`id` is an opaque UUID and `created_at` a UTC stamp, both defaulted by the
  ORM**, on `Screening`'s reasoning rather than as a fresh decision: a case id
  is named beside a screening, and neither should be a counter a stranger can
  walk up.
- **The table carries no index and declares no foreign key.** Nothing filters
  a case yet, and `id` is the primary key. The association runs the other way
  and by value: 16.2 adds a `case_id` to `screenings`, on the same reasoning
  `AuditEvent.screening_id` states -- a screening must outlive nothing here,
  and a constraint would enforce on PostgreSQL while reading as a comment on
  SQLite, which D37's rule is about.
- **A case holds no match result, no score and no band.** 16.5 to 16.7 compare
  documents *within* a case and their answers are `tier: crossdoc` flags in
  Part 16's stream. A case that agrees and a case that disagrees are therefore
  the same three columns, exactly as a band is a measurement beside a row
  rather than a decision inside it. **If a later task needs a case-level
  verdict, it is an event in Part 10's trail, not a column here.**

**Measured, not assumed.** The three defaults this table relies on were each
broken in place and the new suite re-run: a nullable `label` fails the
required-ness test, a migration that creates the table under another name fails
three tests, and removing the `created_at` default fails five. A table that
round-trips through the ORM proves the mapping, not the migration, so the
round trip is run against both a `create_all` schema and an `alembic upgrade
head` one.

**Revisit only if** 24.11 needs to list cases without a name -- an officer
filtering by case rather than by traveller -- at which point `label` becomes
nullable and an unnamed case is `None` rather than the empty string.
## D127 -- A cross-document name key reuses Tier 0's accent map, folds no digraph, and collapses its whitespace last

**Date:** October 3, 2026. **Status:** settled, task 16.3.

**Context.** 16.3 asks for `normalise_name(s)`, and the first cross-document
comparison in the project rests on it: 16.4's `names_match` compares two keys,
and every later rule in Part 16 reads a name through this function. Four
choices inside it were open, and each of them is expensive to reverse once a
flag has been raised from it -- where the function lives, who owns the accented
letter map, what order the steps run in, and whether a digraph is folded.

**Decision.**

- **`app/pipeline/crossdoc/` is a package beside `tier0`, `tier1` and `tier2`,
  and not a fourth stage inside one.** `tasks.md` defines `crossdoc` as a peer
  of the three tiers rather than a depth within them, and it is the one tier
  whose input is a *set of documents*: a deep module takes one image and a
  cross-document rule takes a case. `crossdoc/__init__.py` is 0 bytes, on 1.1's
  reason -- `tier0`, `tier1` and `tier2` are all empty and adding a docstring
  here would make this the only one that is not.
- **The accent map is Tier 0's and this function does not hold a copy of it.**
  Casing and diacritic removal are reached through
  `td3.transliterate_names(s.upper(), ())[0]`, which is exactly what
  `tier1/fields.py::_normalise_name` already does, on the argument that the
  same accented letters remembered twice is a second place for them to be
  wrong. **The only step that is this function's own is the whitespace.**
- **The order is uppercase, then transliterate, then collapse whitespace, and
  the collapse is last on a measured reason.** Transliteration is the one step
  that can *empty a token* -- a name of nothing but combining marks has no base
  letter to keep -- so a string split before it would carry a separator for a
  token that no longer exists. Measured: a name whose last token is a lone
  combining mark keys as `'MULLER '`, with a trailing space, under
  collapse-first, and as `'MULLER'` under the shipped order. Collapsing after
  means the surviving separators are the ones between tokens that survived.
- **No digraph is folded.** `normalise_name("Mueller")` is `MUELLER` and
  `normalise_name("Müller")` is `MULLER`, and those are two keys, not one.
  `ue`, `ss` and `ph` are spellings rather than diacritics, and tolerance for
  them is 16.4's `names_match` argument, not this key's. **A key that had
  already forgiven a misspelling could not be used to decide whether to
  forgive it** -- the tolerance would be baked into the thing the tolerance is
  measured against.
- **A non-string raises `MrzValueError`, and the guard is explicit rather than
  left to Tier 0.** `s.upper()` runs first, so delegating the check to
  `transliterate_names` would never reach it: the first version of this function
  raised `AttributeError` on `None`, which is not a `ValueError` and so breaks
  the rule every other refusal in the pipeline holds to. The message names the
  *type* it was given and never the value, on 2.9's rule that this is still the
  identity data the screening is about; a test asserts a refusal holding
  `["Müller"]` does not print `Müller`.
- **`TRANSLITERATIONS`' `ß` entry is unreachable on this path, and that is
  measured.** `"ß".upper()` is `"SS"` in Python, so the sharp-s entry can never
  be the character reaching the map here -- upper-casing expands it first.
  `ø`, `Ł` and `Đ` *are* reachable, because their upper-case forms do not
  decompose. The entry stays in Tier 0's table because `transliterate_names`
  still takes names that skipped the previous step.
- **A character outside the map is carried through unchanged**, so `æ` keys as
  `Æ` and not `AE`. This is 2.9's recorded cost, restated at the seam where a
  later task would otherwise be tempted to fix it: **`normalise_name` is not
  claimed to produce MRZ-alphabet output**, and inventing an `AE` here would be
  2.14's "parsing must not silently fix it" in the one direction 2.14 did not
  anticipate.

**Measured, not assumed.** Six mutations of the shipped line were each applied
in place and the suite re-run: dropping the upper-casing, dropping the
transliteration, dropping the whitespace collapse, dropping the type guard,
reversing the first two steps, and collapsing to no separator at all. All six
fail the suite; reversing the order is caught by the `ø` case rather than by
the `ß` case, which is the reason that case is in the file. The `ß`-becomes-
`SS`, upper-case-forms-do-not-decompose and `æ`-is-carried-through facts were
each run before being written into a test rather than quoted.

**Revisit only if** 16.4's `names_match` turns out to need a fold this key
cannot supply -- a name differing only by a digraph and nothing else, which no
tolerance on tokens can express -- at which point the fold belongs in
`names_match` as a named comparison, not in the key.

---

## D128 -- A name match forgives a digraph, a compound and a token's position, and reports the tokens it forgave

**Date:** October 3, 2026. **Status:** settled, task 16.4.

**Context.** 16.3 built the key and D127 kept three digraphs out of it on the
argument that a key which had already forgiven a misspelling could not be used
to decide whether to forgive it, leaving 16.4 to hold them as named
comparisons. D127 named one revisit condition -- a name differing by a digraph
and nothing else -- and the three cases `tasks.md` verifies are exactly that:
`Mueller`/`Müller` and `Muller`/`Mueller` must match, `Rahman`/`Rahmani` must
not. Nothing in the repository could yet express a tolerance, and a caller
being told "not the same name" was given no way to learn *which token*.

**Decision.**

- **`names_match(a, b, tolerance)` returns a frozen `NameMatch` of three
  fields -- `similarity`, `differing`, `tolerance` -- and `matched` is the
  similarity read against the tolerance asked for.** The threshold is an
  argument rather than a constant inside the function, so 16.5-16.7 can pick
  their own and so the record can say which one produced it. A tuple of three
  numbers was rejected: `differing` is not a number.
- **Three digraphs are folded, and only those three D127 named:** `UE`→`U`,
  `SS`→`S`, `PH`→`F`, in one left-to-right non-overlapping pass. `AE` and `OE`
  were considered and left out -- they merge `ÆTHER` with `AETHER` and
  `Aaron` with `Eron`, and nothing in the domain asked for it. `ß` reaches the
  fold already expanded, on D127's recorded reason.
- **`differing` holds folded-token pairs, one per compared position, with `""`
  on the side that had nothing to pair**, so a caller can name the token
  rather than just the verdict. Folded, not printed: those are the tokens the
  similarity was measured on, and reporting `MUELLER` against `MULLER` as a
  difference would contradict the `similarity == 1.0` beside it.
- **Tokens are sorted, and both orders are paired greedily with the higher
  total winning.** Sorting makes token order structurally unable to reach the
  answer; the two-sided maximum is what makes `names_match(a, b)` and
  `names_match(b, a)` answer alike, which one greedy pass does not promise.
  A shorter name is padded with `""` so no token is dropped and the record can
  say it had no partner.
- **A compound edge is a token edge, not a character to delete.** `-`, `.` and
  `,` each become a space, so `Smith-Jones`, `Smith.Jones` and `SMITH JONES`
  are three spellings of two tokens. `SMITHJONES` written solid is *not* split,
  because splitting it needs a surname vocabulary this module does not have.
- **Similarity is `1 - Levenshtein / max(len)`, averaged over the compared
  positions.** Measured: `Rahman`/`Rahmani` scores exactly 6/7 = 0.857, and
  an averaged edit ratio alone would have scored the *rejected* pair higher
  than `Muller`/`Mueller` -- a suffix is one cheap edit, a digraph is two. The
  digraph fold is what puts the two cases the right way round; without it the
  tolerance would have to reject a genuine misspelling to catch a near-match.
- **`DEFAULT_TOLERANCE` is 0.95, and it refuses a single added letter.**
  Measured: 6/7 sits below it and 1.0 sits above it, so the default separates
  the two cases `tasks.md` names with nothing between them. A caller wanting
  typo tolerance must lower it, which is a risk it is then choosing.
- **A name with no token in it is refused rather than scored, and so is a
  tolerance that is not a real number in `[0, 1]`.** Nothing is coerced, on
  D116's rule -- a clipped or rounded threshold is one nobody chose. An empty
  name refused rather than answered `1.0`, because two documents that both
  failed to print a name have agreed about nothing, and D115's rule is that an
  empty result is not an all-clear. Refusals are `MrzValueError`, Tier 0's,
  so a caller catching one around its cascade keeps working.

**Measured, not assumed.** Ten mutations of the shipped lines were each applied
in place and the suite re-run: dropping the `UE`, `SS` or `PH` fold, dropping
the sort, scoring the edit ratio over the *shorter* token, pairing one order
instead of two, narrowing the compound separators to `-` alone, dropping the
tolerance range check, dropping the empty-name refusal, and emptying
`differing`. All ten fail `test_crossdoc_names_match.py`. A 14,400-permutation
sample over three-token names built from near-neighbour two-letter tokens found
the shipped answer symmetric in every case and *no* case where the similarity
itself moved with token order -- the two-sided maximum was already covering
both directions, and the sort's measured contribution is to which side an
unpaired token is reported against.

**Consequences.** `test_crossdoc_names_match.py` holds 50 tests. 16.3's
`test_the_module_exports_only_the_key` was relaxed to a membership assertion,
because this task widened the module's exports and an exact-equality pin written
for the previous task would fail on a change this one was asked to make.
`normalise_name` still folds nothing, and a test holds that: the digraph is
forgiven in the comparison and not in the key.

**Revisit only if** a comparison needs a surname vocabulary to split
`SMITHJONES`, which is a table rather than a rule and would belong to the key's
own module, or if a caller needs the similarity to be order-*sensitive* -- a
visa naming a holder's parents, say -- which would mean pairing in printed
order and giving up both the sort and the symmetry this records.

## D129 -- A cross-reference is an exact match on a filler-free key, and a flag names the rule rather than the number

**Date:** October 3, 2026. **Status:** settled, task 16.5.

**Context.** 16.5 asks for `documents_consistent(documents_in_case)` checking
the passport-number <-> visa cross-reference. D126 gave the case its grouping
and settled that it carries no verdict; D127 and D128 built the name key and
the name comparison beside it. Three things were open, and each is expensive
to reverse once a flag has been raised from it: what a *document* is when
`Screening` carries no `case_id` and no `document_role` (16.2, still
unimplemented), what the number is compared as, and what the answer is when
there is nothing to compare.

**Decision.**

- **A case document is a `CaseDocument` of this module's own, and not a
  `Screening` row.** 16.2's `case_id` and `document_role` are not implemented,
  so the alternative was a module whose input type does not exist. `role` is
  the three names 16.2 names -- `passport`, `visa`, `id` -- held as
  :data:`DOCUMENT_ROLES` so a role nobody wrote down is refused rather than
  compared as something it might be. **16.2 stays outstanding and this does
  not pre-empt it**: when the columns land, a caller builds a `CaseDocument`
  from a row rather than the module reading the row itself, so the storage
  change touches no rule in here.

- **The key is upper-cased, whitespace-dropped and filler-free, and nothing
  else.** A passport number is printed into two *fixed-width* fields of two
  different documents, and the widths need not agree, so `AB1234567` and
  `AB1234567<` are one number and must match. **No digraph is folded**, on
  D127's and D128's reason: those three folds forgive a misspelling in a
  *name*, and a number has none to forgive -- `MUELLER1` against `MULLER1` is
  two different passports and is flagged as such. **No tolerance argument
  exists**: a cross-reference is exact or it is not, which is why 16.4's
  `tolerance` does not reappear here.

- **A visa that printed no reference is not compared, and the case answers
  `not_configured`.** D115's rule is that an empty result is not an all-clear,
  so this cannot answer `consistent` -- but it cannot be a finding either,
  because a visa whose reference field was never read has not referenced an
  unknown passport. Three statuses, on D121's reasoning and with its
  consequence: **`consistent` is not reachable from a case that compared
  nothing**, and `compared` is carried on the record so an officer can tell
  "every visa resolved" from "no visa said anything" without re-reading the
  case.

- **The flag carries no passport number on any of its fields.**
  `expected` and `found` are `None`, and `label` and `reason` are one sentence
  each naming the rule. The only datum that would tell two offending visas
  apart *is* the number, which is why the two flags are identical and why the
  answer is one flag per offending visa rather than one per case: an officer
  sees how many visas failed, and the numbers stay off the dashboard, the log
  and the officer's screen.

- **`region` is `None`, and `field` is `personal_number`.** A cross-document
  finding is about two pages, so neither frame locates it and 4.12's boxes
  have no single image to draw over -- a finding with nowhere to point is
  still a finding, on the flag record's own rule. The field named is the
  layout's own name for where a TD3 visa prints the number.

- **One flag per offending visa, in the order the documents were given.** Not
  one per case: two visas naming two passports that are both absent are two
  findings an officer is owed, on 6.2 and 6.4's rule. The order is the
  caller's, so the answer does not depend on a set being ordered.

**Measured, not assumed.** Twelve mutations of the shipped lines were each
applied in place and `test_crossdoc_documents_consistent.py` re-run: inverting
the visa filter, emptying the empty-reference skip, inverting the membership
test, moving the `not_configured` branch behind `compared == 0`, dropping the
key's upper-case/filler strip, raising the band to `high`, zeroing the
comparison count, dropping the flag append, dropping the non-visa reference
refusal, and each of the three refusals in `_case_of`. **Two survived the
first pass and were answered rather than waived.** The
`and _number_key(document.document_number)` guard on the passport set was dead
-- an empty reference is skipped before the set is consulted, so a `""` key
could never be looked up -- and was deleted. The bare-string refusal survived
because it only changed *which* message came out, and a test now pins the
message rather than the exception type alone. All twelve now fail.

**Consequences.** `test_crossdoc_documents_consistent.py` holds 64 tests.
`documents_consistent` is reachable only from tests today: nothing writes a
`traveler_cases` row, and DEEP_MODULES is still empty (Gate 15).

**Revisit only if** 16.2 lands and a caller would rather the module read a
`Screening` row than be handed a `CaseDocument`, which would move the input
type and nothing else, or if a real visa MRZ turns out to print the passport
reference somewhere this project has no layout name for.

## D130 -- A validity window is two printed days on the document, the travel date is an argument, and both ends are closed

**Date:** October 3, 2026. **Status:** settled, task 16.6.

**Context.** 16.5 built `CaseDocument` and answered "does a visa name a
passport the case holds". 16.6 asks the second question -- the visa must cover
the travel date -- and three things were open before any of it could be
written: where the travel date comes from, whether the window is closed or
half-open at each end, and whether this widens `documents_consistent` or sits
beside it.

**Decision.**

- **The travel date is the second argument of `visa_validity_consistent`, never
  a field of a document.** A document that carries the day it is checked
  against can be built wrong in a way nothing catches: the same visa record
  would read differently for two journeys, and there is no reading of
  `CaseDocument` that tells you which journey it was built for. Injecting it is
  also how `app.pipeline.tier0.dates` has taken every reference day since D8,
  and how a rule that would otherwise answer on the day it happened to run is
  kept from doing so.
- **The window is `valid_from` and `valid_until` on `CaseDocument`, both dates
  or neither.** Every document prints a validity window, so no role is refused
  one; only *this rule* reads it off visas, because the task is the visa's
  coverage of a journey. A half window is refused at construction rather than
  carried as a gap: `CaseDocument` is what a caller hands over, so one end
  missing is a caller mistake and not a document that printed half a window.
- **The window is closed at both ends.** `valid_from <= travel <= valid_until`.
  A visa valid *from* a day is valid on it and one valid *until* a day is valid
  on it, which is `expiry_result`'s own position in D8 -- a document is valid
  through the day it expires -- and re-deciding it here would put two rules in
  this project disagreeing about the same boundary day.
- **`visa_validity_consistent` sits beside `documents_consistent`, in
  `crossdoc/validity.py`, and reuses its `CaseConsistency` and its `_case_of`
  gate.** One flag id per rule is this project's shape (D17), and a second
  rule inside 16.5's function would have made one function's answer depend on
  an argument the other rule needs. Widening the function instead would have
  put two unrelated refusals in one signature. The shared refusal is imported
  rather than copied, so the two rules cannot disagree about what a case is.
- **The flag carries the two days, unlike 16.5's flag carrying no number.** A
  date is not identity data: `expected` is the window as printed
  (`2026-01-01/2026-06-14`) and `found` is the travel date, both ISO 8601.
  D129 withheld the passport *number* because it is the datum that would let a
  flag be linked back to a person; two days cannot be, and an officer cannot
  act on "the visa does not cover the travel date" without them. `label` and
  `reason` still name the rule and print neither date, and no document number
  or passport reference appears on the flag at all.

**Measured, not assumed.** Fourteen mutations of the shipped lines were each
applied in place and the two crossdoc suites re-run. Thirteen fail. The
fourteenth replaced `travel.isoformat()` with `str(travel)` and survived,
because `datetime.date.__str__` *is* `isoformat` in the standard library -- the
two expressions cannot be distinguished by any input. A test now pins the
format by round-tripping both fields back through `date.fromisoformat`, which
holds whichever spelling the module uses.

**Consequences.** `test_crossdoc_visa_validity.py` holds 74 tests, and 16.5's
`test_the_module_reads_no_clock_and_no_document_image` no longer asserts the
word `datetime` is absent from `documents.py`: that assertion was a proxy for
"resolves no day", and widening the record with two printed days fails it on a
type annotation. It now asserts no call reaches `now`/`today`/`utcnow` and no
image library is imported, which is what the rule always meant. `crossdoc` is
three modules now and `__init__.py` is still 0 bytes (D127).

**Revisit only if** a journey can carry more than one date (a return leg makes
"the travel date" two days, and the rule as written would answer about the
outbound one), or if a visa form is found that prints an open-ended window --
"valid until cancelled" -- which the closed reading at both ends cannot express.

## D131 -- A face is read through a record that carries the frame beside the document, the first measurable face is the reference, and a box with no embedder answers `not_configured`

**Date:** October 3, 2026. **Status:** settled, task 16.7.

**Context.** 16.7 asked for `face_consistent(documents_in_case)` over Part 13's
interfaces, degrading cleanly where no embedder is available, and left two
things open: where a document's face is held, and whether the degrading path is
a second status or one status with a detail -- the question D121 settled for
Tier 2 but which the three cross-document statuses had never been asked.

**Decision.**

- **The face rides beside the document, in `CaseFace`, and not on it.**
  `CaseDocument` gained no image field. It is a transcription, and 16.5's suite
  holds a test asserting `documents.py` imports no image library at all; a
  sixteenth field carrying pixels would have made that guard false for the
  wrong reason rather than removing it. `CaseFace` is that document *and* the
  frame 13.14's `photo_region` cut from it, so a face case is a sequence of
  `CaseFace` and the shared record stays a record of what was printed.
- **`_case_of`'s shape refusals were lifted into `_sequence_of`** rather than
  copied. The three rules ask one question of the same first argument, so the
  answer is one function; the element refusal stays in each module because
  each module's element is a different record. 16.5 and 16.6 are untouched
  behaviourally and their suites were re-run rather than edited.
- **The first measurable face in document order is the reference, and every
  other measurable face is compared against it.** Not the passport's, not the
  first *document's*: which document is primary is the caller's to order
  rather than this rule's to guess from a role, and 16.5 already reads roles
  as data a caller wrote. Three documents yield two comparisons, not three,
  and that is the whole of what "cross-document" means here.
- **Where a photo holds several faces, the most confident one is embedded.**
  A portrait is one person, and where a detector offers more than one the
  question "whose face is this document's" is answered by the confidence the
  detector itself gave, not by the order it happened to return them in. Ties
  keep the earlier face, so the answer is deterministic.
- **`not_configured` is the whole of the degrading path -- one status, no
  detail, no fourth answer.** D121 already forbids reading silence as a
  verdict and 16.5 and 16.6 answer it as a status; adding a detail field to a
  record that already carries `status` would be two ways to say one thing.
  **An unavailable embedder is asked once, before anything is read**, so a box
  with no face model costs one call and takes no case down.
- **A detector is never asked whether it is available.** The bar was asked of
  the embedder and nobody else, because the embedder is the capability the
  comparison cannot happen without and 13.13 is the seam that answers it.
  A document that cannot be measured -- no frame, no face in it, landmarks
  that describe no face, an embedder that declines -- is skipped and is not
  counted in `compared`, so a case with fewer than two measurable faces
  answers `not_configured` and never `consistent`.
- **A pair 13.15 refuses to score is not compared.** A stub's labelled zero and
  a vector with no direction answer `NO_MATCH` rather than a similarity of
  zero, so `NullEmbedder` degrades through the same door as a missing one
  without a second check of its own.
- **The threshold is checked here as well as in 13.15.** Same predicate, so
  it can never disagree; the second check is there because a refusal raised
  from this package is an `MrzValueError` and a caller catching one around its
  cascade keeps working.
- **The flag carries the bar and the cosine, and neither face.** `expected` is
  the threshold and `found` the similarity as four-place decimals, exactly as
  13.16 prints one. `region` is `None`: two documents' faces are on two
  frames, so neither can be pointed at. D129 widened -- a face embedding is
  biometric identity data, and a flag must not become a place it is stored.

**Measured, not assumed.** Each shipped line of this module and of the lifted
`_sequence_of` was broken in place and the three cross-document suites re-run:
20 mutations, 20 killed, no survivors. The two worth naming because they are
the rule's whole content are `max` over the detected faces -- reading the
first face offered instead fails on a photograph offering two -- and the
`is_available` gate returning before anything is read, which is the only
thing separating a degraded answer from a raised one.

**Revisit only if** a case's primary document becomes something the case
knows rather than something the caller orders, at which point the reference is
that document's face and the ordering is a rule rather than a convention, or
if `DEEP_MODULES` gains an entry, which is when these flags reach a screening
record at all.

## D132 -- A number in a summary is a digit run with no word character directly beside it, kept exactly as written

**Date:** October 3, 2026. **Status:** settled, task 17.1.

**Context.** 17.1 asked for `extract_numbers(text)` and a test proving it finds
numbers in text and ignores ordinals inside words. The second half of that
sentence is the whole design question: what counts as a number in prose a model
wrote, which 17.3 then requires to have been measured.

**Decision.**

- **A number is a digit run with no word character directly beside it**, and
  one compiled pattern holds that rule rather than a list of words to exclude.
  `sha256`, `mp3`, `x86_64`, `utf8`, `ISO8601` and `1st` are words no number is
  read out of: their digits name a format, a codec or a position rather than a
  measurement. A word list was the alternative and it fails on the next unseen
  token, while adjacency is a property of the text rather than a vocabulary
  somebody maintains.
- **A decimal part is part of the token, and at most one of them.** `0.98` is
  one token and not `0` followed by `98`, because 17.3 checks a token against
  the flag data by the characters printed there, and a re-spelt number is not
  the characters that were measured. At most one, so a version string splits
  rather than reading as a single measurement.
- **The token is returned exactly as written, in order, and a repeat is kept.**
  No float conversion and no rounding, so `0.980` is not `0.98` -- that
  difference is one of the things 17.4 exists to catch. Order and repeats make
  the answer a reading of the text rather than a set of its vocabulary.
- **`app/explain/__init__.py` is a docstring and nothing else** (1.1), so
  importing the package does not pull the verifier in and a caller says which
  module it took a name from. **`verifier.py` imports `re` and nothing else**,
  which is Part 17's claim that the verifier is pure code and needs no model --
  held by a test reading the module's imports rather than asserted here, and
  the same reason D7 keeps `flag_ids` import-free for 17.3.

**Measured, not assumed.** Each shipped component was broken in place and the
new suite re-run: 8 mutations, 8 killed, no survivors. The two worth naming are
the lookbehind and the lookahead, because either alone is enough to read a
`256` out of `sha256` or a `1` out of `1st`.

**Revisit only if** a summary is found quoting something that is a number
inside a word and is expected to be checked -- a document number printed
without its separators spaced, for instance -- at which point this is a
tokeniser over document syntax rather than an adjacency test.
## D133 -- A date is one of two spellings, and a field name is a registry id or a word shaped like an identifier

**Date:** October 3, 2026. **Status:** settled, task 17.2.

**Context.** 17.2 asked for `extract_dates(text)` and `extract_field_names(text)`
as the other two questions 17.3 will ask of a summary. Neither name is defined by
the flag data, and the field-name half had a trap in it: the literal reading of
"capitalised tokens" makes 17.6 impossible, because every sentence begins with a
capital and no flag data contains the word `The`.

**Decision.**

- **A date is ISO `YYYY-MM-DD` or the slash form with a two- or four-digit
  year**, under 17.1's adjacency rule, so a date stands alone as written: an ISO
  timestamp is not read as a date, and a digit run carrying no separator is not
  one. **The parts are not validated**, so `2024-99-99` is returned as written
  rather than repaired or dropped -- an impossible date is a claim 17.3 must
  match against the data, and matching it is what fails.
- **A field name is a flag id from the registry, or a capitalised word carrying a
  second signal** -- a digit, an internal capital, or an acronym of two or more
  capitals. **A capital on its own is a sentence, not a name**, which is why the
  test reads `ALL_FLAG_IDS` rather than a written-out id, and why `A` and `I` are
  length-checked before an acronym is claimed. This is the reading of "capitalised
  token" that survives 17.6: the fallback template opens with `The`.
- **`verifier.py` now imports `app.risk.flag_ids` and `re`.** The id pattern is
  built from `ALL_FLAG_IDS` at import time, longest first, word-bounded -- so an
  id added tomorrow is found by construction and cannot be read out of a longer
  word, and the capitalised pattern excludes `_` so one id is answered once.
  Part 17's "pure code, no model" claim is unchanged, because D7 keeps
  `flag_ids` importing nothing; the 17.1 import test was widened to hold that
  rather than the older "re and nothing else".
- **Both return a tuple of tokens in the order written, repeats kept**, like
  `extract_numbers`, so all three are readings of the text rather than sets of
  its vocabulary.

**Measured, not assumed.** Twelve mutations were applied in place and the new
suite re-run; eleven were killed, and the twelfth -- dropping the lookbehind in
front of a date -- survived, which was a missing assertion rather than a missing
rule. `issued2024-11-02` is now held as carrying nothing, beside the token that
follows a space, and the mutation dies with it.

**Revisit only if** a summary is found naming a field the way the flag data
prints it -- `date_of_expiry` rather than `DATE_EXPIRED` -- at which point a
snake_case token joins the identifier shapes, and 17.3's comparison decides
whether the spelling is the matcher's problem or the model's.

## D134 -- A token passes when the text the flag data prints holds it, and a refusal names each missing token once

**Date:** October 3, 2026. **Status:** settled, task 17.3.

**Context.** 17.3 asked for `verify_summary(summary, flag_data)` returning
pass/fail plus the offending tokens. D132 and D133 settled what a token is and
that it comes back exactly as written. What was left was the comparison, and it
had three parts to settle: what the flag data is searched as, what order the
offences come back in, and whether a repeat is two offences.

**Decision.**

- **A token passes when the text `str(flag_data)` prints contains it.** A
  substring search and nothing else -- no float conversion, no rounding, no
  reading of the payload's shape -- so `0.870` is refused where the data prints
  `0.87`, and a `confidence` of `0.11` settles the `11` inside a printed date.
  **A walk over mappings and sequences was written, swept and deleted.** For
  every payload this project builds -- a list of `dataclasses.asdict` flags, a
  dict payload, an `EvidenceFlag` -- `str()` already carries every value, so the
  recursion had no observable behaviour and two of its branches survived a
  mutation sweep as dead code. What `str()` buys is the safe direction: a record
  whose printed form is ever shortened can only make this verifier refuse more,
  never accept more.
- **The offending tokens come back once each, in the order the summary writes
  them**, rather than the three questions in turn. The extractors keep repeats
  (D132) because a reading of the text must not lose one; this is a diagnosis
  rather than a reading, and one unsupported claim quoted three times is one
  defect to report. The order is by first occurrence, so a reader gets the
  summary's own sequence; where a number and the date holding it start together,
  the number is asked first and the tie resolves towards it.
- **A date the flags never printed offends the numbers written inside it too.**
  `2029-01-05` is four tokens and not one, because 17.1's adjacency rule reads
  three of them as numbers. All four are unsupported, so all four are reported.
- **The answer is a `(bool, tuple[str, ...])` pair and not a record type.** A
  frozen dataclass would need `dataclasses`, and 17.1's test reads this module's
  imports to hold Part 17's "pure code, no model" claim exactly; two values do
  not need a name of their own.
- **Nothing raises.** The summary is prose from somewhere else, so a refusal has
  to be a value the caller can act on rather than an exception it must catch.

**Measured, not assumed.** Eight mutations were applied in place and the suite
re-run: the flag data not printed, each of the three questions not asked, every
token treated as offending, the dedupe dropped, the verdict flipped, and the
sort dropped. Eight killed, none survived. The first sweep is what found the dead
recursion, and the reason it was untestable is recorded above rather than papered
over with an assertion.

**Revisit only if** the flag data stops being plain JSON-shaped data and a record
type arrives whose printed form leaves something out -- at which point the
search needs a walk, and the walk needs a case a `str()` fallback cannot kill.
## D135 -- A summary is three fixed sentences and one line per flag, and every line is the flag's own `reason`

**Date:** October 3, 2026. **Status:** settled, task 17.5.

**Context.** 17.5 asked for `template_summary(flags, band)` -- the summary an
officer reads when there is no model text. D132 to D134 settled what a token is
and what settles one, so two questions were left: what the fixed part says, and
where the per-flag wording comes from.

**Decision.**

- **The frame is exactly three sentences and does not vary with the flags.** The
  band, a headline, and a closing that says the band is what the scan read. The
  task's "2-3 sentences" is read as this frame rather than as the whole output,
  because "one line per flag" makes the total a function of the flags and a
  summary that grew a fourth sentence on a five-flag scan would say nothing an
  officer did not already have.
- **The headline is the only sentence that branches,** on whether anything was
  raised at all. **It never counts the flags.** A count needs a number word, and
  a digit in the frame is a token D132 would have to settle against flag data
  that never prints it -- the fallback would be the one summary in Part 17 that
  fails its own verifier.
- **A flag line is the flag's `id` and the flag's `reason`, and nothing else.**
  This is what makes the fallback passable by construction rather than by
  luck: every token on such a line is a substring of what the flag data prints,
  because the line is built out of the flag's own fields. 17.6 is what proves
  it against the verifier; the shape here is the reason it holds.
- **`field` is deliberately never written.** The flag data prints it snake_case
  (`date_of_expiry`) and D133's extractor does not read snake_case, so writing it
  would put an unchecked token into prose that looks checked. "Which field" is
  17.13's question, and its per-flag reason templates can answer it in plain
  words or in an id.
- **The template reads `id` and `reason` and stops.** A finding carrying nothing
  else still narrates, which is pinned by a stub exposing exactly those two, so a
  future field reaching this module is a test failure rather than a surprise in
  a summary.
- **Nothing is sorted.** The lines come in the order the cascade produced the
  flags, because that order is the one an officer has already seen.
- **A malformed input refuses loudly.** A band outside the three names, a flag
  with no `id` or no `reason`, a blank `id` and a `reason` that is not text each
  raise `FlagValueError`, on `flags.py`'s rule that a malformed field is never
  coerced into something legal. This is the last thing standing between a scan
  and an officer, so a refusal is better than half a finding narrated.

**Measured, not assumed.** Sixteen mutations were applied in place and the new
file re-run: sixteen killed, none survived, and the module was restored
byte-identical afterwards. Two of them put a number and a field name into the
frame, which is what shows the two extractor cases are load-bearing rather than
decorative.

**Revisit only if** a rule's `reason` stops being plain language -- 17.13's
per-flag templates then own the wording and this module holds only the frame --
or the band vocabulary grows a fourth name.

## D136 -- One endpoint both servers speak, one budget for the whole exchange, and a failure is an answer

**Date:** October 3, 2026. **Status:** settled, task 17.7.

**Context.** 17.7 asks for a `Summarizer` interface and a self-hosted LLM
client "speaking the Ollama/llama.cpp HTTP API, with a hard timeout and no
external fallback -- when it fails it returns `None`, it does not raise".
D132 to D135 had settled what a summary may say and who checks it, so the
naming was already settled; four things were left open, and three of them are
expensive to reverse once a response names a model and an officer reads a
sentence that came from one: **which endpoint**, **what the timeout bounds**,
**where the `None`/raise line sits**, and **what the interface carries**.

**Decision.**

- **The client speaks `POST /v1/chat/completions`, the one endpoint Ollama and
  llama.cpp's server both serve.**  Their native APIs are `/api/generate` and
  `/completion` respectively, and neither server answers the other's, so
  aiming at either native path is a client that works on one machine and not
  on the other.  The OpenAI-shaped path is the intersection, and it is
  asserted as a literal rather than read back from the constant, so a
  "harmless" rename of `GENERATE_PATH` cannot quietly move the client onto a
  path only one of the two serves.
- **The timeout is one deadline for the whole exchange, re-imposed before
  every phase and before every chunk of the body, and it is enforced on a
  socket the module owns.**  `socket.create_connection`'s timeout is per
  operation, so a server that dribbles a body a byte at a time would hold a
  client open for as many windows as it liked; and `HTTPConnection.getresponse`
  closes the socket object when the reply ends the connection, after which
  `settimeout` answers `OSError` -- so the one place the budget is re-imposed
  has to hold the socket itself, which is why the request is written and the
  response parsed on a socket this module opens and closes.
- **Every failure is `None` and nothing raises -- including a blank prompt, a
  prompt that is not text, a model that is not configured, an address that
  names no server, and a budget that is not a positive number.**  Each of
  those is refused *before the connect*, which is observable: the test stub
  records an empty request list, so a client that checked afterwards would
  fail the same test.  A malformed address or a budget of zero is the
  exception, and it is refused in `config.py` while the configuration is
  read -- a bad value is a deployment that would answer `None` to every
  document, which deserves a `ValueError` naming the variable at start-up,
  the way `DATABASE_URL` and `RATE_LIMIT_PER_MINUTE` are (D36, D78).
- **`Summarizer` is one abstract `summarize(prompt) -> str | None` and carries
  `model_name`**, so whatever wrote a summary travels with it for 17.11 to
  record, and a subclass that omits the method cannot be instantiated.

**Notes.**

- **"Within the timeout" is measured, not assumed, and the measurement is not
  the same on every host.**  A closed loopback port is refused in
  milliseconds on most, but on the host this was built on the connection is
  silently dropped, so the budget is spent before the refusal arrives
  (measured: 2.03s against a 2s budget).  Both are correct answers -- `None`
  no later than the budget -- and the case is written against the budget
  rather than against a millisecond figure.
- **A base URL may carry a path prefix**, so the same server behind a reverse
  proxy is reached under the prefix rather than dialling a path that answers
  404.  It may be a LAN address as well as loopback: `.env.example` says so,
  and refusing one would refuse the deployment the project describes.
- **The request is built as UTF-8 bytes** rather than handed to
  `http.client` as text, which encodes a body as latin-1 -- a prompt quoting a
  document field can carry any character, and a mangled one would go out
  silently.
- **Untested by choice:** whether either server is actually running.  17.7
  ships a client and a stub; `LOCAL_LLM_MODEL` is blank in `.env.example` and
  the client answers `None` to everything until an operator names a model.


## D137 -- The summariser is not called at all while `LOCAL_LLM_ENABLED` is off, and the switch has no constructor argument

17.7 shipped a client that speaks to whatever `LOCAL_LLM_BASE_URL` names, and
`.env.example` shipped a master switch nothing read.  Two things were left open
and both are expensive to reverse once an officer has read a sentence a model
wrote: **whether "off" means "do not dial" or "dial and discard"**, and
**whether a caller can turn the switch back on**.

**Decision.**

- **`LOCAL_LLM_ENABLED` gates `summarize` before anything else, and the answer
  is `None` without a connection.**  The gate is the first statement, ahead of
  `_prompt`, so a disabled client does not read the flag data it was handed --
  `None` is what a caller acts on, and every failure 17.7 lists is already
  refused before the connect, so this one is refused the same way.  It is read
  in `__init__`, not per call: a client built off is off for its whole life,
  because a per-call read would follow an operator turning it off mid-process
  and leave half the documents on the template and half not.
- **There is deliberately no constructor argument for it.**  The other three
  settings are tuning values a caller may override for a test, and a switch a
  constructor could turn back on would not be one.  `LocalLLMClient` is the only
  reader of the variable, so a deployment that has not asked for the model
  cannot be talked into calling it.
- **Unset is off, blank is off, and a value the reader does not recognise is
  off.**  Nothing here is a `ValueError`, unlike `LOCAL_LLM_BASE_URL` and
  `LOCAL_LLM_TIMEOUT_SECONDS` (D136).  Those are values a wrong spelling would
  silently change into a refusal on every document, which deserves naming at
  start-up; this one has two answers, both ordinary, and only one of them is
  safe to reach for when the value is not understood.  `false`, `0`, `no`,
  `off`, `` and whitespace are off; `true`, `1`, `yes` and `on` are on, folded
  for case and surrounding space.
- **No request ever leaves the configured local host** is pinned by wrapping
  `socket.create_connection` and recording every address the client touches on
  any path, rather than by counting requests on a stub.  17.7 already showed one
  address and one dial; what was unproven was that a *second* address could not
  appear, and a stub the client never reaches cannot show that.  The default in
  `config.py` is a different port, so a fallback to it is a second entry.

**Notes.**

- **The name is part of the contract.**  `LOCAL_LLM_ENABLED=false` is what
  `.env.example` ships, and the test reads that file rather than comparing the
  constant to itself -- a rename would otherwise move both sides together and
  leave a deployment setting a variable nothing reads.
- **No request leaves the host, but the model server is never named as
  loopback-only.**  `LOCAL_LLM_BASE_URL` may be a LAN address (D136), and the
  claim is "the host the operator configured", not "this machine".
- **17.5's template is what an officer reads while the switch is off**, which
  is why off is a complete answer and not a degraded one.
- **Untested by choice:** whether an operator who sets the switch on has a
  model that answers.  17.7 was proved against a stub on loopback, and
  17.8's cases are the same stub.

## D138 -- The prompt is a versioned file, and the version is the file's own

**Context.**

The narration question is prose rather than logic, so it belongs in a file. 17.9's
task was to create `prompts/v1.txt`, a loader, and a test that changing the file
changes the reported version -- and the interesting part is not the file but the
"reported version" half, because the repository already had a constant of that
name.

**Decision.**

- **`app/explain/prompts/v1.txt` carries its own version in its own header, and
  no version is written beside it in Python.**  The leading run of `#` lines is
  metadata; one of them declares `prompt_version`, and everything below that run
  is the prompt.  The loader is the one way in, so a caller holds a frozen
  `Prompt` and never a path -- the same rule, and the same `D21` argument, as
  `app.risk.weightsets.loader` beside `v1.yaml`.
- **`PROMPT_VERSION` is a PEP 562 module `__getattr__`, not a constant.**  This
  is the load-bearing choice.  Nothing else in the module is cached -- a prompt
  retuned on disk has to be the one the next load returns -- so a constant named
  `PROMPT_VERSION` would be a snapshot of a file explicitly allowed to change
  under it, and the task's own test ("changing the file changes the reported
  version") would not hold of it.  `app/version.py` still carries a plain
  `PROMPT_VERSION` because the version API must read one without importing
  anything; a test holds the two equal rather than letting either be the
  authority alone.
- **A file that is absent, names no version, names it twice, or declares one and
  holds no text is refused with `PromptError`, a `ValueError`.**  Never defaulted:
  a default prompt is a prompt nobody recorded, and the version beside it would
  be a version of nothing.  A key written inside a note (`# The prompt_version:
  line is below`) is a note, not a declaration.
- **The prompt is read as a package resource**, through
  `importlib.resources.files` on a named package and never from a path built out
  of `__file__`, for D15's reason.
- **The shipped template introduces no token the verifier would reject.**  The
  frame is fixed and the findings are not, so a number, a date or a field name
  written into `v1.txt` would be a token D133's extractors find no flag behind,
  and a hardcoded field name would bias the model toward a claim the flags never
  made.  The four rules are held by the terms they name rather than by their
  wording, so a reworded rule passes and a dropped rule does not.

**Notes.**

- **Untested by choice:** the exact prose of the shipped prompt.  A mutation
  sweep killed 20 of 21 shipped lines; the survivor is a reworded rule in
  `v1.txt`, which nothing can detect without pinning the prose byte for byte.  A
  test that failed on every wording change would be a change-detector rather than
  a claim, and the rules are pinned at the terms they name instead.
- **Nothing calls the loader yet.**  17.10 builds the payload this prompt will be
  sent with, and 17.11 is what assembles the two; the version is quotable from
  the day it is written because a response that reports a summary has to be able
  to say which prompt wrote it.
- **`app/explain/prompts/` is a package, not a directory of strings**, so the
  file ships inside the package under Cloud Run -- `.gcloudignore` excludes only
  `requirements-dev.txt` among the text files.

## D139 -- The payload is a list of field names, and `region` is not on it

**Context.**

17.10's task was to build the flag data a model is sent -- structured flags,
the band, the contributions -- with a test asserting the payload carries no
pixel data.  The question that task does not answer for itself is what *no pixel
data* is, given that an :class:`app.risk.flags.EvidenceFlag` already
carries a `region`: a polygon of integer pixel corners.

**Decision.**

- **The payload copies a flag by name, out of `SENT_FIELDS`, and
  `region` is not in it.**  Eleven of the twelve fields reach the model;
  the twelfth is the only field on a flag that points at pixels, and it
  describes an image the model is never shown.  **The copy is a whitelist rather
  than a deletion**, so a field added to `EvidenceFlag` later is one the
  payload cannot leak by default, and a test holds the whitelist against the
  record so the addition fails loudly rather than passing quietly.
- **The payload is JSON and prints as that same JSON.**  `to_json` is the
  text a prompt carries and `__str__` is the same text, so
  :func:`app.explain.verifier.verify_summary` holds a summary to the exact
  data the model was given.  Two renderings would be two descriptions of one
  payload, and they could disagree about what was sent.
- **A contribution row is copied onto a record of its own, and its field names
  are read off `app.risk.scoring.Contribution` rather than written beside
  it.**  A payload is therefore detached from the caller's breakdown, and a row
  cannot gain a field the payload would quietly drop.
- **No total is held.**  7.11's rows are pre-history, and the score they do
  not add up to is the officer's number; a total beside them would invite the
  model to state a score, which `prompts/v1.txt` forbids in prose and the
  flag data does not support.
- **A band the registry does not know is refused with `FlagValueError`, as
  17.5's template refuses it.**  The check is restated rather than shared:
  `app.explain` re-exports nothing and reaches into no sibling module's
  private, and widening 17.5's surface for this would couple two contracts
  with no reason to move together.  Never defaulted -- a payload that named a
  band the risk package does not have is a claim nothing else can check.
- **A record missing a field the payload sends is refused, and the message names
  the field.**  The copy reads each name in turn, so the refusal falls on the
  first field the record does not carry rather than on whichever field a
  different reader happened to reach first.

**Notes.**

- **Untested by choice:** the wording of the module and its docstrings.  A
  mutation sweep killed 21 of 21 shipped lines.  One of them puts `region`
  back into `SENT_FIELDS`, which is the rule this decision is about, so the
  task's own no-pixel-data claim is held by a test that fails on its absence
  rather than on any prose.
- **Nothing sends the payload yet.**  17.11 assembles a prompt from it, and
  17.12 feeds poisoned model output back through the same text.
- **`region` is still on the flag and still reaches the officer's screen.**
  4.12's highlight and the API response are unchanged; what D139 withholds is
  the copy handed to a model, not the finding.

## D140 -- A refused summary is discarded rather than repaired, and the record says so in two fields

**Date:** October 3, 2026. **Status:** settled, task 17.11.

**Context.**

D134 settled what the verifier answers: a `(bool, tuple[str, ...])` pair,
nothing raised, so a refusal is a value the caller acts on. 17.11 is that
caller, and the task names three things -- discard the model text, use the
template, record `summary_source` plus `verification: failed`.  What it does
not settle is the vocabulary those fields carry, and the vocabulary is what an
officer's screen, an audit and 17.12 will be written against.

**Decision.**

- **A refused summary is thrown away, not repaired.**  The template stands in
  its place whole, and **the refused text is not held on the record at all** --
  there is no field it could be read back out of.  Repairing it (stripping the
  offending sentence, keeping the rest) was the alternative and was refused: a
  summary an officer reads would then be a sentence nobody wrote, holding a
  claim the flags do not support, with the removal invisible on the screen.
- **`summary_source` says who wrote the sentence on the record, so a refusal
  records `template` beside `verification: failed`.**  The two fields answer
  two different questions and the pair is the point: the source says what was
  read, and the verdict says a model wrote something and it did not survive
  being checked.  Recording `model` beside `failed` would leave an officer
  looking at prose nobody vouched for and asking which of the two to believe.
- **There are three verdicts, not two: `passed`, `failed` and `not_checked`.**
  The shipped deployment answers `not_checked` on **every** document, because
  `LOCAL_LLM_ENABLED` ships off (D137), so a record claiming `passed` there
  would be reporting a check that never ran -- and a record claiming `failed`
  would show an officer an error on a system working exactly as configured.
  Two verdicts could only tell that lie one way or the other.
- **`model_name` names who wrote *this* summary, so it is `None` on every
  template summary** whatever a model was configured to answer with.  A
  rejected summary was written by a model that did not write the summary, and a
  record naming it beside the template would credit prose to the wrong author.
- **`unsupported` is the verifier's own diagnosis, in the summary's own
  order (D134), and empty whenever nothing was refused.**  It is the record of
  a rejection rather than the text of one, which is what makes the rejection
  auditable in 17.12 without holding the sentence that caused it.
- **`prompt_version` travels with the summary**, for D138's reason: a
  sentence quoted against the prompt that did not write it is not comparable.
  It is recorded on all three paths, because the template is also an answer to
  a prompt-naming question -- "which version would have written this".
- **The payload is built on every path, including the one with no summariser**,
  so a finding that cannot be narrated is refused the same way whether or not a
  model is configured, and so the flag data the verifier searched is the exact
  text the model was given -- one rendering, on the pass path and the reject
  path alike (D139).
- **The template is built before the model is asked.**  It is the answer to
  every failure, so building it first means a finding the template cannot
  narrate is refused before anything is sent anywhere rather than after.
- **The prompt is the loaded text, then the payload JSON, joined by one blank
  line** and nothing else.  A heading written between them would be prose no
  decision recorded, and the payload is already the one rendering D139 built.
- **Nothing here raises on model text.**  17.7's client answers `None`
  rather than raising and that is its whole failure contract; a refusal is a
  verdict the record carries, not an exception a caller has to catch.  A
  `Summarizer` wired wrongly still fails at construction (D136).

**Measured, not assumed.**  Twenty mutations were applied in place and the new
file re-run: twenty killed, none survived, no anchor skipped, and the module
was restored byte-identical afterwards.  Two of them -- the given prompt
ignored, and the payload left out of the prompt -- were **survivors on the first
sweep and killed only after a writing fault was found** (see `HANDOVER.md`): a
triple-quote written where two-character `\n\n` was meant had opened a docstring
that swallowed the last twenty tests of the file, and pytest reported the
survivors without an error.  A green run is not evidence that the file was read.

**Revisit only if** a summary ever has to be shown beside the text that was
refused -- at which point the refused text becomes a field with a retention
rule -- or if the officer-facing screen needs a verdict 23.8 cannot badge.

## D141 -- The guard on model text is exactly a token the verifier reads, and no wider

**Date:** October 3, 2026. **Status:** settled, task 17.12.

**Context.**

17.12 was to prove that deliberately poisoned model output never reaches an
officer. D134 made the verifier token-based, and D140 discards whatever it
refuses, so the guarantee holds exactly where the extractor reads something.
Feeding eight poisons settled where that line falls: six carry a readable
token and are refused whole; two carry none and are delivered.

**Decision.**

- **The guard is the token, not the intent.**  Any summary carrying a token
  the flag data never printed is discarded whole and the record reads
  `template` beside `failed` -- D140's rule read as a property, and now
  asserted on poisoned answers rather than described.
- **A refusal repeats the offending tokens in `unsupported` and nothing
  else.**  That is the audit: what was refused is readable while the prose is
  unreachable, and a record still carries six fields with no seventh to hold
  refused text in.
- **A poison carrying no readable token reaches the response, and that is
  recorded rather than papered over.**  An underscore hides a token behind a
  word character (D133), and a verdict flipped in ordinary words carries no
  token at all.  The test file names both and asserts the boundary exactly:
  the refused poisons and the readable tokens are one and the same set.
- **Which tokens a refusal names depends on the payload it was held to.**
  With no findings, `SIH-2024` is refused for `2024` as well as `SIH`,
  because nothing else printed a year; so a case covering every scan asserts
  the names are tokens the poison wrote, not one fixed set.

**Measured, not assumed.**  Sixty-eight new tests, and four mutations of the
reject branch -- deliver the refused text, name the model as the source,
record the refusal as passed, drop the diagnosis -- all four killed, with
`narration.py` restored byte-identical afterwards.

**Revisit only if** an extractor learns underscored identifiers, or a semantic
check is added beside the token one -- at which point the two unguarded
poisons become the guarantee and the boundary case is rewritten as one.

## D142 -- Every flag id has one plain-language sentence, written here and never asked for

**Date:** October 3, 2026. **Status:** settled, task 17.13.

**Context.**

17.13 asked for a per-flag reason template, so an officer always has a
plain-language explanation of a finding. A rule writes its own `reason` once, at
the moment it fires, and nothing holds it to writing one: 17.5 prints a bare
machine id when the reason is blank, and an id is not English. An id the
registry does not know is a caller bug rather than a finding, so there is
nothing to look a sentence up for.

**Decision.**

- **One sentence per id, keyed by the registry's own constant.**  `REASON_TEMPLATES`
  is written in :data:`app.risk.flag_ids.ALL_FLAG_IDS` order with `flag_ids.X` as
  the key, so an id is never retyped in this module and the completeness test has
  a second table to hold against the registry.
- **The sentences are fixed prose with no slot to fill.**  Nothing read off a
  document is written into one, so a template cannot become a place identity data
  is stored, and no number, date or field name appears in one -- which means
  `verify_summary` cannot refuse a template whatever the flag data prints.  That
  is what makes this a floor rather than a claim, and it is asserted on every
  id rather than reasoned about.
- **They are the floor beneath a rule's own `reason`, not a replacement for it.**
  17.5 still narrates each finding in the wording the rule wrote (D135), because a
  rule knows what it saw and this table does not; these sentences are what the
  officer has when no rule wrote one.
- **An id the registry does not know is refused, not invented.**  A sentence
  about a rule that does not exist is a claim nothing can be traced back to, so
  `reason_for` raises :exc:`FlagValueError`, naming the registry and never
  repeating the value.
- **The table is read-only and the package re-exports nothing**, so the sentences
  are reached from their own module like every other name in Part 17, and the
  module imports the registry and the error and nothing else -- a sentence an
  officer reads must not pull a detector in to be written.

**Measured, not assumed.**  Two hundred and sixty-two new tests, and six
mutations of the shipped lines -- the membership test inverted, the type check
shortened, each refusal removed, one entry deleted, the table made writable --
all six killed, with `reasons.py` restored byte-identical afterwards.

**Revisit only if** a rule's own `reason` ever grows a slot a document can write
into, or an officer screen needs a line above the summary rather than inside it
-- at which point the fixed sentence becomes the caption and the id is the line's
own label.

## D143 -- The decision endpoint takes the officer three choices and writes nothing yet

**Date:** October 3, 2026. **Status:** settled, task 18.1.

**Context.**

Part 10 named the officer three choices and made an override an event of its
own, but nothing had reached HTTP: there was no address a client could post a
choice to, so `record_override` had no caller outside its own test. The
band is stored and the choices stand apart from it (D70), and 8.4 holds
`screenings` to sixteen columns, none of which is a decision -- so a
choice has nowhere on the row to go and this task cannot invent one.

**Decision.**

- **One route, three values, and the vocabulary is read rather than retyped.**
  `record_decision` takes `action`, `remark` and `override`, and
  the refusal for a spelling outside the three is built from
  `OFFICER_ACTIONS` itself -- so the message cannot fall behind the
  vocabulary, and no module but `app.audit.decision` spells the adverse
  choice. That is the second half of 7.10's walk, which fails a rejection word
  found anywhere else in `app/`.
- **A choice is one of three exact words, and the other two values have
  defaults.** Casing, padding and a fourth spelling are refused rather than
  normalised, so what the trail will carry is what the officer chose; a
  remark left out is an empty remark, not a missing one.
- **The answer is the four values the request named.** No score, no band, no
  finding, and nothing the upload carried. The remark comes back as it was
  written, untrimmed, because it is the officer sentence and no service
  rewrites one.
- **A live row is what makes the address meaningful**, so a screening id no
  live row carries answers the same 404 the read beside it answers -- which
  is also what a soft-deleted row is (8.15).
- **Nothing is written this task.** 18.2 is where a band refuses a choice,
  18.3 is where the choice reaches the trail as `decision_recorded` and
  `override_recorded`, and 18.4 is where a second choice is answered
  rather than overwriting the first. A route that recorded the choice on the
  row would need a seventeenth column, which 8.4 refuses.

**Measured, not assumed.** Thirty-two new tests, and nine mutations of the
shipped lines -- the vocabulary check removed, the refusal code respelled, the
row never read, the 404 removed, the remark and the flag dropped, the
documented 422 removed, and each default flipped -- all nine killed, with both
files restored byte-identical afterwards.

**Revisit only if** 18.3 answers with the event id beside the choice, at which
point the answer grows a fifth field rather than replacing one of these four.

## D144 -- The band refuses the adverse choice unless the officer claims it

**Date:** October 3, 2026. **Status:** settled, task 18.2.

**Context.** 18.1 took a choice at a URL and wrote it nowhere, which left the
one combination the abstract cares about unguarded: the officer's own adverse
choice on a `low` band, where the record holds nothing to show that anyone
disagreed with anything. The abstract gives the officer the decision on every
case, it is the adverse outcomes a disputed case turns on, and a service that
answers 200 to an adverse choice nobody claimed is answering for the system
rather than for the officer.

**Decision.**

- **The rule is `override_required`, and it lives beside the two orderings
  it reads.** `app.audit.decision` is the only module that spells the adverse
  choice (D70, D143), so the route asks that module rather than naming an
  action itself; `ADVERSE_RANK` is read off `OFFICER_ACTIONS` rather than
  counted, and the answer is `contradicts_band` asked in one direction only --
  a band and a choice disagreeing the other way are the officer exercising their
  own choice and are held to no flag.
- **The adverse choice needs `override: true` on any band below it** --
  `low` and `review` -- **and needs none on the band that agrees with
  it**, so the flag is a claim rather than a formality, and it is the only
  choice held to one.
- **The refusal is a 422 in the shared envelope**,
  `DECISION_OVERRIDE_REQUIRED`, naming the flag to send. **It is a
  validation error rather than a recorded override**: nothing is written, so
  there is no event to write until 18.3.
- **The band is the stored one and never the requested one.** `row.band` is
  read off the row the choice was made on, a body naming a band is ignored, and
  a row nothing has scored carries no band and has therefore shown none to go
  against -- which is why 18.1's fixtures, all unscored, still answer 200.
- **The id is answered before the band.** An unknown or soft-deleted row is
  still `SCREENING_NOT_FOUND` (8.15), so the rule never reads a row the
  endpoint would not have answered about anyway.

**Measured, not assumed.** Twenty-four new cases in
`backend/tests/api/test_decision_override.py`, the backend suite at 6812, and
eight mutations of the shipped lines -- the rank read off the tuple turned into
a constant, the no-band guard dropped, the answer forced to `False`, the
choice no longer validated, the flag condition inverted, the band replaced by
`None`, the status respelled and the code respelled -- all eight killed,
with both files restored byte-identical afterwards.

**Revisit only if** 18.3 records the claim, at which point `override: true` is
what makes `override_recorded` appear and the two have to move together.

## D145 -- The choice reaches the trail as an event, and the override still follows the band rather than the flag

**Date:** October 3, 2026. **Status:** settled, task 18.3.

**Context.**

18.1 took a choice at a URL and wrote it nowhere, and 18.2 refused the one
combination the abstract cares about.  Both left the same gap: the officer's
decision existed only as a 200, so a trail carrying the system's reading of a
document carried nothing about the person who answered it -- and the
append-only ledger had no row to point at.  Part 10 had already written both
event names and one of the two writers; nothing reached them.

**Decision.**

- **The writing lives in `app.audit.decision`, not in the route.**  That module
  owns the officer's vocabulary (D70, D143) and already owns
  `record_override`, so `record_officer_decision` sits beside it and the route
  asks one module for the whole record rather than spelling an event name and
  a payload of its own.
- **Every taken choice leaves exactly one `decision_recorded`,** carrying the
  three values the officer sent and nothing else of theirs -- `officer_action`,
  `remark` and `override` -- with the remark kept exactly as written and the
  flag at the value the caller sent, `false` included.  Neither is normalised
  on the way in (18.1) or on the way into the trail.
- **The band's own reading is not repeated into the decision event.**  It is
  already on the trail as `analysis_completed`'s `band`, so copying it would
  leave two records of one measurement: the officer's event carries the
  officer, and the system's carries the system.
- **`override_recorded` still follows `contradicts_band`, not the flag.**
  10.6 defines that event as the disagreement, in both directions, and it is
  the only place that defines it -- a release of a `high` band is an override
  and needs no flag, and a flag sent on a pair that agreed records no
  override.  **This is D144's revisit clause, half taken and half declined**:
  the clause triggers on 18.3 recording the claim, and the claim *is* recorded,
  inside `decision_recorded`, so claim and event sit side by side on one
  trail without the flag becoming the rule the band was.
- **A row nothing has scored carries no band, so it has nothing to go
  against**, and the answer is one decision event and no override -- 18.2's
  guard read as a fact about the record rather than as a 422.
- **A refusal writes nothing.**  The write sits after the id, after the
  vocabulary and after the band, so all three refusals leave the trail exactly
  as they found it.
- **The choice is read before either event is written,** so a spelling this
  project cannot read raises `DecisionError` with no half-decision on the
  trail -- the ordering 10.6 already holds for the override alone.
- **The answer keeps its four values.**  D143's revisit clause triggers on an
  event id being answered beside the choice; this task did not ask for one, and
  `DecisionResponse` is the contract 18.1 pinned, so no fifth field was added.
  The events are on the trail, which is where a reader already looks.

**Measured, not assumed.** Twenty-four new cases in
`backend/tests/api/test_decision_events.py`, the backend suite at 6836, and
thirteen mutations of the shipped lines -- the name read removed, the no-band
guard dropped, each of the three payload keys respelled, the flag forced to
false, the empty override replaced by a second decision event, the decision
event renamed to the override, and on the route the stored band blanked, the
choice upper-cased, and the remark, flag, ruleset and model versions each
replaced -- all thirteen killed, both files restored byte-identical.

**Revisit only if** 18.4 moves a status on the row, at which point the row and
the trail say the same thing twice and one has to be derived from the other.

## D146 -- A second choice is answered beside the first, and where a choice stands is read off the trail

**Date:** October 3, 2026. **Status:** settled, task 18.4.

**Context.**
18.3 left the officer's choice on the trail and nothing on the row, which is
right (8.4 refuses a seventeenth column) and left one gap: a second choice sat
beside the first with nothing naming which one a reader should act on. The two
were indistinguishable, so the trail recorded that two people had answered a
document without recording which answer stood. A retry -- the ordinary reason a
second choice arrives -- was therefore indistinguishable from a reversal, and
an officer who reversed themselves left no claim that they had.

**Decision.**

- **A second choice is a second event, never an edit.** `supersedes` is written
  into the *new* `decision_recorded` and names the event it was taken over
  from. The first event's id, payload, digest and salt are what they were, and
  9.17 still rebuilds it: an event is sealed when it is written (8.5), so the
  link is the only way one choice can name another.
- **Where a choice stands is a reading, never a column.** `current` is the last
  decision the trail holds and `superseded` is every earlier one, read in
  `created_at` then `id` order -- the total order the repository already reads
  rows in, because two choices can share an instant. `recorded_decisions`
  derives it; no payload carries a standing, because a standing in a payload
  would be a claim that has to be rewritten when a later choice lands, and an
  event cannot be rewritten. 18.4 therefore *changes* the first choice's
  standing without touching a byte of the first choice.
- **`supersedes` is written only where a choice was already recorded**, so a
  screening decided once hashes exactly as 18.3 left it: the three keys of the
  officer's own, unchanged.
- **The answer grows by three and replaces nothing.** `decision_id` is the
  event written, `status` is where it stands and `supersedes` is what it took
  over from. This is D143's revisit clause, taken: it says the answer "grows a
  fifth field rather than replacing one of these four", and it grows by three
  rather than one because an id alone says neither what a choice replaced nor
  where it stands -- a client retrying a request needs both to tell a
  superseded answer from a standing one.
- **The idempotency claim is the four values and the standing, not the id.**
  The same request sent twice answers with the same choice, the same remark,
  the same flag and `current` both times, with two sealed records and the
  second naming the first. Nothing the first wrote is lost and nothing is
  rewritten, which is what a retry must not disturb.
- **18.2's guard still comes first, and 18.3's refusals still write nothing**,
  so a choice nobody may take leaves the one already taken standing.
- **The reader is beside the writer.** `current_decision` and
  `recorded_decisions` sit in `app.audit.decision` rather than in
  `app.audit.trail`, because the standing is a decision vocabulary and
  `trail.py` holds no vocabulary of its own.

**Measured, not assumed.** Twenty-one new cases in
`backend/tests/api/test_decision_supersession.py`, and seven mutations of the
shipped lines -- the link written only where there was no choice to name, the
standing read off the front of the trail rather than its back,
`DECISION_STATUSES` reordered, `current_decision` answering the first decision
rather than the last, the officer's own choice replaced by the empty value, the
answer's `decision_id` dropped, and `supersedes` answered as nothing -- all
seven killed, with both files restored byte-identical afterwards. 18.1's,
18.2's and 18.3's answer-shape cases were updated rather than deleted, and each
keeps its own claim: none of the four fields 18.1 named is replaced. 11.12's
`openapi_contract.json` was rewritten with the three added fields and nothing
else.

**Revisit only if** a screening carries more than one officer at different
stations, at which point 10.7's `actor` is what says which of them superseded
which, and the trail's order stops being the whole of the answer.

## D147 -- The delete is a stamp the repository already keeps, reached at last by a URL

**Date:** October 3, 2026. **Status:** settled, task 18.5.

**Context.**
8.15 wrote ``soft_delete`` and made every read of ``screenings`` skip a row it had
stamped, so the rule this task needs has been in place since Part 8 and has
had no caller since: nothing reached it from a URL, and 24.5's confirm-then-
delete had no endpoint to confirm against. A rule with no route is untested in
practice and unreachable in the product.

**Decision.**

- **The route is the URL that reaches 8.15's rule, and adds no rule.** No column
  is added, no read filter is written here, and no second spelling of
  "deleted" appears in ``app/api/``: the route asks ``ScreeningRepository``, which
  already carries the one filter every read shares.
- **The instant is handed in, not read here in the route's own way.**
  ``soft_delete`` takes ``deleted_at`` rather than reading a clock, so the route
  passes ``datetime.now(timezone.utc)`` -- an aware instant, which the repository
  converts, and a naive one is refused before the table is touched.
- **A second delete is absence, not a second stamp.** ``soft_delete`` finds its
  row through the same ``deleted_at IS NULL`` every read uses, so an id no row
  carries and an id already stamped are the same answer: both are 404. When a
  row was deleted is a fact about the past, and who deleted it is 10.1's event
  rather than a second reading of a column.
- **The refusal is the reads' own refusal**: 404, ``SCREENING_NOT_FOUND``, and the
  same message ``GET /api/screenings/{id}`` gives, so a client that has learned
  one read's envelope has learned this one's.
- **The answer is the id and the stamp, and nothing else.** Those two are the
  whole of what the delete did, since it removed nothing. No score, no band, no
  finding and no filename: nothing read off a document reaches an answer about
  deleting it.
- **It answers 200 with a body rather than 204.** 24.5 confirms and then
  refreshes, and every other route on this resource answers with a body, so an
  empty success would be the only such answer here.
- **CORS now allows ``DELETE``.** A route a browser may not call is not a route,
  and 24.5 calls it from a page served on another origin.
- **``screening_deleted`` is still unemitted.** 18.1 took the decision endpoint
  and wrote nothing, and 18.3 emitted the events as its own task; this follows
  the same split rather than folding a second behaviour into one task.

**What this forbids**

- A hard delete, or any statement that removes a ``screenings`` row.
- A second stamp on a row that already carries one.
- An error code of this route's own, or a body carrying anything read off the
  document.

**Measured, not asserted** -- 14 cases in
``backend/tests/api/test_screening_delete_api.py`` through the real app, 6871
backend tests (was 6857), and seven mutations of the shipped lines -- a naive
stamp, the ``None`` check dropped, a fresh uuid answered in place of the row's, each
of the two answer keys dropped, a different code in the refusal, and ``DELETE``
removed from the CORS allowlist -- all seven killed, with both files restored
byte-identical afterwards. 11.12's ``openapi_contract.json`` was rewritten with the
added operation and 94 lines gained, none removed.

**What this leaves.** The row is stamped and every read refuses it, but nothing
records *that* it was deleted: ``screening_deleted`` has been a name in the
vocabulary since 10.1 with no writer. D148 is the test that the trail survives
the delete, and no task yet emits the delete's own event.

## D148 -- A delete leaves the trail where it was, and surviving means still walking it

**Date:** October 3, 2026. **Status:** settled, task 18.6.

**Context.**
D147 shipped a delete that removes nothing and named 18.6 as the test of the
clause it left open: the ledger entry and the audit events survive it. 8.5 had
already argued that structurally, since ``AuditEvent.screening_id`` declares
no foreign key and an event therefore outlives the row it names -- but an
argument about the schema is not a guarantee about what the delete issues, and
nothing held the claim through the endpoint.

**Decision.**
- **Surviving is proved by walking the trail, not by counting it.** Every case
  anchors the screening's real events through 9.16 (root, sign, append, stamp),
  takes the delete through the real endpoint, and then asks 9.17 for each
  event's answer. The claim asserted is ``verified``, because rows that outlive
  the delete but no longer reach their root would satisfy a count and fail this.
- **Events are compared as records, not as numbers.** Each stored row's type,
  actor, payload, digest, salt, batch id and position are read back before and
  after, so a row rewritten in place fails rather than passing.
- **The delete is watched at the statement level.** One case holds every
  statement the engine issues during the request and asserts that none names
  ``audit_events`` or ``ledger_entries``: no cascade, no key and no second write
  can erase a trail that no statement touches.
- **The absence of the key is asserted off the schema** -- in the metadata and
  in the created SQLite table -- so a future migration that adds one fails a
  test rather than a production cascade.
- **The officer's choice is included**, since a recorded decision is the part of
  the trail an erase would do most damage to, and a second screening's trail is
  held beside the first so a delete is proved to take nothing else with it.
- **A run anchored after the delete is proved too**: a sweep that reaches the
  trail once the row is stamped still commits to the anchored root and still
  walks to it, so a backstop running later cannot fail on a screening no read
  can reach.

**Measured, not asserted** -- 11 cases in
``backend/tests/api/test_delete_keeps_audit_api.py`` through the real app and
the real log, 6882 backend tests (was 6871), and three mutations of
``soft_delete`` -- the delete erasing the trail, the delete purging the log, and
the delete removing the row outright -- all three killed, with the file restored
byte-identical afterwards.

**What this forbids.**
- Any statement, cascade or key that removes or amends an ``audit_events`` row
  or a ``ledger_entries`` row as a consequence of deleting a screening.
- A foreign key from ``audit_events`` to ``screenings``.
- Asserting survival by a row count rather than by the verifier's answer.

**What this leaves.** ``screening_deleted`` is still a name in the vocabulary
with no writer, so a deleted screening's trail still says nothing about the
delete itself. D147 records the split; no task claims the event.
## D149 -- A verify endpoint that names the checks it made, and only those

**Date:** October 3, 2026. **Status:** settled, task 18.7.

**Context.**
11.1 hands an officer an ``audit_id`` beside every screening, and 9.17 can say
whether the event it names is still the record the log committed to -- but
nothing carried that answer over HTTP, and what 9.17 answered with was one
word and no evidence.  A word a reader cannot check is a word they have to take
on trust, which is the opposite of what a trail is for.

**Decision.**
- **The walk is written once.** 9.17 now answers with a ``Verification``
  record: the three words, the batch reached, the root as the log spells it,
  the length of the walked proof, and the names of the checks that completed.
  ``verify_event`` is that record's ``status`` and is unchanged, and 18.7's
  route asks the record.  No second walk, and no second spelling of the three
  answers in the route or beside it.
- **Only a check that ran is named.** ``checked`` is the steps that completed,
  in walk order, so a 200 can be read for what it is: a clearance, or an answer
  that stopped before it compared anything.  ``unknown`` naming nothing at all
  is how "nothing could be compared" is reported -- which is also the answer
  for an id no row carries, and a 200 rather than a 404, since the question
  was answerable.
- **The two numbers come out of the database, not off the object.** The batch
  root is D57's verbatim column as the log holds it, and the proof length is
  the path the tree really cuts for that row's own position -- both rebuilt in
  the cases from the stored digests rather than read off the answer.
- **One sentence per check, in one table keyed by 9.17's own constants.** A
  step is never retyped and never named twice, and a step added to the walk
  without a sentence fails a test rather than reaching an officer unexplained.
- **The moved commitment is this task's vector; the moved record is 18.8's.**
  The case here rewrites a ledger entry's root, so the record still hashes and
  only the walk answers. The payload is left for 18.8 to move.
- **The read spends nothing and writes nothing.** No statement naming
  ``audit_events``, ``ledger_entries`` or ``screenings`` is issued, no analysis
  budget is spent, and this route has no error code of its own: 422 is the
  envelope's and 500 is the service's.

**Measured, not asserted** -- 21 cases in
``backend/tests/api/test_audit_verify_api.py`` through the real app and the real
log, 6903 backend tests (was 6882), and eighteen mutations of the shipped lines
-- each of the three ``checked`` appends dropped, the root and the proof length
dropped, the status and the batch root not carried over, the sentence table
bypassed, the trail read by the wrong column, the log built over another
database, the response model's vocabulary narrowed, the path parameter loosened
and ``verify_event`` answering a constant -- all eighteen killed, with every
file restored byte-identical afterwards. 11.12's ``openapi_contract.json`` was
rewritten with the added operation and 145 lines gained, none removed.

**What this forbids.**
- A second walk of the log, or a second spelling of the three answers, in the
  route or in ``app.audit.verify``.
- Naming a check that did not complete, or reporting ``verified`` for an event
  no root was walked to.
- A 404, or an error code of this route's own, for an id no row carries.
- Any value read off a document in the answer: no payload, no finding, no
  score, no filename.

**What this leaves.** The entry's signature is not checked here: this route
proves the root is the batch's own and not that the signature over it is sound,
and ``app.ledger.signing.verify_signature`` still has no caller outside its own
tests. And ``unknown`` names what ran rather than why it stopped, so a caller
that needs the reason must read the log beside it. 18.8 moves the other vector.

## D150 -- The report is one self-contained page built from the row, and the route only reads it

**Context.**
An officer has three ways to read a screening: the JSON 11.2 answers with, the
screen the frontend draws, and -- since nothing built it -- a printable
record.  A filed record is the one that has to survive the deployment it was
made on: it must open on a machine with no network, print without a
stylesheet the browser cannot fetch, and still say what was found.  Two
answers about one row would also have been a hazard, so the question is
where the page is built and what it may carry.

**Decision.**
- **One module builds the page and the route reads it.**
  ``app.reporting`` turns a row and an audit id into the document;
  ``GET /api/screenings/{id}/report`` reads the row, reads the audit id
  through ``app.audit.trail`` and answers with what it is handed.  The
  route holds no markup and the module holds no session, so neither half
  can drift from the other.
- **The page references no external asset, and a case says so against the
  spellings rather than against one example.**  The stylesheet is inline,
  there is no link, script, image, frame, object or import, and no url()
  beside it -- so a printer, an offline machine and a reader in ten years
  all see the same page.  The ban is held against a page that really does
  reference one, so a checker matching nothing cannot pass it.
- **Everything printed is read off the row.**  The band and the score are
  the columns a stage wrote rather than a fresh reading of one beside the
  other, the findings are the stored evidence rather than a re-run of the
  cascade, and the audit id is the one ``analysis_completed`` event 11.1
  answered with -- which is the id 18.7's verify endpoint takes, so a
  printed record names the record it can be checked against.
- **A value the row never received prints as a sentence.**  A row no stage
  has scored carries no score and no band, and a cascade that raised leaves
  no completed event beside it; each prints as ``NOT_RECORDED`` rather than
  as an empty cell, so a reader cannot mistake an unanswered question for an
  answer that said nothing.
- **Every value is escaped on the way out**, because a label, a reason and a
  document type are all text a rule or a caller wrote, and a report is
  printed from exactly what they wrote.
- **Nothing read off the document is printed, and neither is the upload's
  name.**  A finding prints as its id, label, tier, module, weight band, its
  two numbers and the reason its own rule wrote; no expected or found value,
  no region polygon, no image, and no filename -- caller-supplied text a
  filed record does not carry.  The reason floor in ``app.explain.reasons``
  is deliberately *not* reached: wiring it to an officer's screen is 23.8's,
  and reaching it here would have written two owners for one sentence.
- **The one HTML route names the error envelope by pointer.**  FastAPI takes
  an additional response's media type from the route's own response class,
  so the ``{"model": ErrorResponse}`` spelling the other routes use would
  document this JSON envelope as a page of HTML; 11.4's own case holds the
  pointer instead.

**Measured, not asserted** -- 13 cases in
``backend/tests/api/test_screening_report_api.py`` through the real app and
the real cascade, the full backend suite, and 22 mutations of the shipped
lines -- every fact row, every finding column, the doctype, the inline
stylesheet, the finding row's own class, the escaping, the missing-value
sentence, the audit id, the response class, the envelope's media type and
pointer, and the route's answer -- all 22 killed, with every file restored
byte-identical afterwards.  Two of them survived the first pass, because
this fixture scores value and confidence alike and a case asserting one
number appeared was answered by the other's cell; the case now reads the
two as an ordered run.  11.12's ``openapi_contract.json`` was rewritten with
the added operation.

**What this forbids.**
- A second place that builds this page, or markup written in the route.
- Any external reference on it, including a stylesheet fetched by a URL or
  a font loaded by a name.
- A score or band computed here, or a band derived from the score beside it.
- A filename, a field value read off the document, or an image on the page.
- A 200 that carries an error envelope, or an id no live row carries
  answered with a page.

**What this leaves.**  The page is a read and prints nothing an officer has
to act on: it names no officer's choice, and the decision 18.1 records
lives on the trail beside the row rather than in this document, so a filed
record shows what was found and not what was decided about it.  23.8 is
where a reason template and a decision reach a screen together.

## D151 -- Progress is what a finished run recorded, and a frame carries a name, not a value

**Date:** October 3, 2026. **Status:** settled, task 18.10.

**Context.**
An officer waiting on a screening is watching nothing: ``POST /api/screenings``
runs the cascade inline and answers with its two ids only once the run has
finished, so there is no id to open a stream on while the work is in flight.
Part 18 asks for a server-sent stream reporting per-tier and per-module
progress, and the honest reading of that against the architecture this
repository actually has is **a replay of what the run recorded**, not a live
feed.  A background-job redesign would be a different decision with a
different cost, and no task in ``tasks.md`` claims it.

**Decision.**
- **``app.progress`` owns the sequence; the route only reads and hands over.**
  A step is a unit, a state, a tier and a module; the module builds the
  frames and the JSON object on each, so 18.11's polling route can answer
  from the same model without a second spelling of either.
- **A tier is ``completed`` and a module is ``reported``, and those are not
  the same word.**  A tier completed because the trail wrote a
  ``tier_completed`` event naming it.  A module reported because a stored
  finding names it as the module that made that finding -- which is the only
  record this repository keeps of a module having run.  **A module that ran
  and found nothing therefore carries no step**, and the sequence says so by
  omission rather than by claiming the module did not run.
- **A tier is stepped once per ``tier_completed`` event, in the order the
  trail stamped them**, ordered by the event's own instant and then its id,
  because the trail keeps no position of its own.  An event whose payload
  names no tier is skipped: the payload is the record, and a record carrying
  no name names no tier.
- **A tier that only a finding names is walked after every tier the trail
  recorded**, never ordered into the middle of the cascade on a finding's
  word alone.
- **Both reads finish before the first byte is written.**  An id no live row
  carries is a 404 in the shared envelope rather than an error pushed down a
  stream a caller has already started reading, and no session is held open
  for as long as a caller reads.
- **The stream ends on one ``done`` event**, carrying the number of steps
  that preceded it.  A reader that stops there holds the whole sequence, and
  the response ends on its own rather than waiting on a caller to hang up.
- **A frame is exactly a name line, one sorted JSON object and a blank line.**
  Sorted so the same step is the same bytes on every run, and held byte for
  byte by a case because a client reading a stream with a hand-written parser
  is reading the bytes.
- **Nothing read off the document is in a frame**: no finding id, no expected
  or found value, no region, no score, no band and no filename.  A frame
  carries tier names, module names, states and counts, which are this
  repository's own words.
- **``app.screening.TIER_KEY`` is the one spelling of the payload key**, so
  the writer and the reader of that key cannot drift apart.

**The two spellings of a tier are left unreconciled, deliberately.**  The
trail names a tier ``tier_0`` and a finding names the same tier ``0``; there
is no crosswalk in this repository and inventing one here would be a mapping
D151 did not design.  A frame therefore says what the record it was read from
said, and a client sees both rather than a merge nobody checked.  A case holds
the two apart on purpose, so a later task that does join them has to change
it.

**Measured, not asserted** -- 24 cases in
``backend/tests/api/test_screening_progress_stream_api.py`` through the real
app and a real cascade, the full backend suite, and 24 mutations of the
shipped lines -- every constant as it crosses the socket, the payload key as
the trail actually stored it, the frame's exact bytes, both units and both
states, the stamped-instant order against events written the other way round,
the unknown tier reached from a nameless and from a boolean one, a damaged
JSON column, the 404, the stream ending on its own, and a caller hanging up
part way through -- 23 killed, with every file restored byte-identical
afterwards.  The twenty-fourth is an equivalent mutant: rewriting
``{TIER_KEY: name}`` as ``{"tier": name}`` is the constant's own value, and
the wire key it protects is held by its own case.  11.12's
``openapi_contract.json`` was rewritten with the added operation, whose 200
is documented as ``text/event-stream``; its error responses need no
D150-style pointer, because ``StreamingResponse`` carries no media type of
its own for FastAPI to read them off.

**What this forbids.**
- A second place that builds this sequence or spells a frame.
- ``completed`` on a module, or ``reported`` on a tier.
- A step for a module no stored finding names.
- A crosswalk between the trail's tier spelling and a finding's.
- A finding id, a field value, a score, a band or a filename in a frame.
- A session held open while a caller reads, or a 404 sent down a stream.

**What this leaves.**  A stream an officer opens shows a run that has already
finished, and a clean module leaves no trace in it.  Both are limits of what
the run records rather than of the transport: a live feed needs the cascade
off the request thread and its progress stored, which no task claims yet.
18.11's polling route answers from this same model and must report state
identical to these frames.


## D152 -- A poller and a subscriber read one state, because one read is behind both

**Date:** October 3, 2026. **Status:** settled, task 18.11.

**Context.**
18.10 shipped one route over a run's recorded progress: a server-sent stream,
one frame per step, ending on a single ``done``.  A caller that cannot hold a
connection open cannot read it -- a proxy that buffers a response, a network
that drops a long-lived one, a client with no event stream at all.  The
obvious answer is a second route, and the obvious way to build one is to walk
the trail a second time and answer with the same steps, which is how two
routes come to disagree about one run.

**Decision.**
``GET /api/screenings/{id}/progress`` answers with that same sequence as one
JSON document -- ``screening_id``, ``units`` and ``events``.  Both routes go
through :func:`build_progress`, so ``ProgressReport.frames()`` and
``ProgressReport.snapshot()`` are two transports over one walk: every step is
``ProgressEvent.payload``, and ``units`` is the count the ``done`` frame
already reports.  Neither answer is derived from the other.

**One refusal, made once.**  ``_screening_or_404`` reads the row for both
routes, so the two cannot answer one id differently -- the same 404, in the
same envelope, under the same code.

**Three keys, and no completeness flag.**  A flag saying the sequence had
finished would be a claim the stored records cannot support: screening is
synchronous, so a row read here is a run that has already ended, and nothing
in the trail tells a run still going from one that has.  A poller is answered
the whole sequence or not at all.

**Measured, not asserted** -- 13 cases in
``backend/tests/api/test_screening_progress_poll_api.py`` through the real
app and a real cascade, holding the comparison against four rows: one with
findings, one nothing ran on, one a further tier completed after it, and one
whose findings name a tier nothing else does -- beside the exact key sets,
two polls of one row answering the same bytes, the 404 the stream route also
answers, and the document carrying no finding, no value and no filename.  The
two sides are read by two different parsers, the frame reader knowing nothing
about the document, so a change to either shape cannot be read the same way
by both.  12 mutations of the shipped lines, 12 killed, every file restored
byte-identical afterwards.  11.12's ``openapi_contract.json`` was rewritten
with the added operation, whose 200 is the document's own schema.

**What this forbids.**
- A second place that walks the trail or spells a step.
- A document derived from the frames, or a frame derived from the document.
- A route reading a screening without ``_screening_or_404``.
- The two routes answering one id differently.
- A finding id, a field value, a score, a band or a filename in the document.

**What this leaves.**  Both routes answer about a run that has already
finished, as D151 recorded: a poller cannot watch a run either, only read the
one that ended.  A caller waiting for steps still to arrive is waiting for
progress nothing stores yet.


## D153 -- A stage's cost is the window the trail recorded, and the whole is read rather than summed

**Date:** October 3, 2026. **Status:** settled, task 18.12.

**Context.**
An officer's screen is built from ``GET /api/screenings/{id}``, and D151 and
D152 gave a caller the run's steps -- which tiers completed and which modules
reported. Neither route could say where the time went, and task 18.12 asks
for the stage trace and the per-stage timings on that response.

The obvious instrument already exists: ``orchestrator.StageTrace`` records
``started`` and ``elapsed`` per stage. **It is not the one that runs.**  The
shipped flow is ``app.screening._run_cascade``, and that is the other cascade
recorded as a known gap, so building this on ``run_cascade`` would trace a
cascade no screening runs.  A stopwatch in either is also gone by the time a
second reader asks: nothing outlives the request but the trail, so a timing
worth answering from has to be read back out of what the run recorded.

**Decision.**
``ScreeningResultResponse`` gains ``stage_trace``: ``total_ms`` beside
``stages``, and each stage is ``tier``, ``recorded_at`` and ``elapsed_ms``.
``build_stage_trace`` builds it in ``app.progress``, off the same
``_run_events`` walk ``build_progress`` already uses.

- **A stage is a ``tier_completed`` event.**  A stored finding is not an event
  and carries no instant, so a module has no timing and no row here -- the
  same limit D151 recorded, that a clean module leaves no trace at all.
- **A cost is a window between two recorded instants**, opening on the
  instant recorded before the stage and closing on the stage's own.  Not a
  stopwatch: the window carries the writes and the work between the two
  events, and is an upper bound on the stage rather than a measurement of it.
- **The whole is read, not summed.**  ``total_ms`` is ``analysis_completed``
  less ``screening_created``, which is more than the stages add up to, because
  the scoring and the store after the last tier are charged to no stage.
- **Only the run's own three events are read.**  A decision is written by an
  officer afterwards, so walking the trail whole would bill an officer's
  pause to a stage.
- **Whole milliseconds; ``None`` for an absence.**  A stage with nothing
  recorded before it reports ``None`` rather than zero, and a row nothing ran
  on carries no stage and a ``None`` total.  A wall clock that steps backwards
  reads as 0 ms and never as a negative cost.
- **Two reads answer the same bytes**, because the numbers come off stored
  instants rather than off a clock.

**Measured, not asserted** -- 17 cases in
``backend/tests/api/test_screening_stage_trace_api.py`` through the real app
and a real cascade: the stages against the trail's own payloads, each instant
against the trail's own column, a later stage charged from the stage before it
rather than from the start of the run, whole milliseconds that are never
negative, the parts fitting inside the whole, the whole against the run's own
first and last stamps, the trace and the stream counting the same stages, a
row nothing ran on, a stage with nothing before it, a nameless payload on both
routes at once, a later stage appearing in the next answer, an officer's
decision costing nothing, a clock stepped backwards reading zero, the exact key
sets, two reads answering one trace, and the trace carrying no finding, no
value and no upload name.  15 mutations of the shipped lines, 14 killed, the
fifteenth an equivalent one (``round(max(0, x))`` is ``max(0, round(x))``),
every file restored byte-identical afterwards.  11.12's
``openapi_contract.json`` was rewritten with the added field.

**What this forbids.**
- A stage no ``tier_completed`` event named, or a cost measured by a clock of
  this module's own.
- ``total_ms`` summed from the stages' windows.
- A decision charged to a stage, or a module given a timing.
- ``0`` standing in for a window that was never measured.
- A finding id, a field value, a score, a band or a filename in a stage.

**What this leaves.**
- The gap between the last stage's window and ``total_ms`` is the scoring and
  the store, stated rather than closed: the trail records no instant between
  ``tier_completed`` and ``analysis_completed`` to charge it to.
- A cascade that raised leaves no ``tier_completed`` event, so it has no row
  here at all.  The trail's record of what ran is the only record of what
  cost anything.
- A module's cost is nothing, and says nothing.  Timing one needs the same
  stored instants, which no task claims.
- Nothing under ``frontend/`` reads the trace, as D151 and D152 recorded for
  the two progress routes.

## D154 -- the evidence master key is loaded, generated in development, and refused in production

**The decision.** ``EVIDENCE_ENCRYPTION_KEY`` holds the AES-256 key every
evidence blob is wrapped under, as ``MASTER_KEY_BYTES`` (32) of standard
base64. :func:`app.config.get_evidence_encryption_key` is the only reader of
that variable and :func:`app.config.get_app_env` the only reader of the mode;
:func:`app.storage.master_key.load_master_key` is handed what those two
answered and answers a ``MasterKey``. **A missing key is generated in
development and refused in production, and there is no third answer and no
constant.**

- **``APP_ENV`` is a mode, not a flag** -- ``development`` or ``production``,
  folded and trimmed, unset meaning ``development``. A flag would have a third
  position; 19.1 has exactly two answers to give, and a third setting would
  only ever be a misspelling of one of them.
- **An unrecognised mode is refused, not read as development**, deliberately
  not :func:`app.config.get_local_llm_enabled``'s "off is safe" (D137). This is
  the one variable that decides whether a fallback is allowed at all, so a
  typo stops the start-up rather than choosing on the operator's behalf.
- **A generated key is generated per call and held nowhere**, on
  :mod:`app.ledger.salts``'s reasoning that a reused secret is not one: two
  callers handed ``None`` in one process hold two different keys, and a blob
  written under one cannot be read back with the other. ``MasterKey.generated``
  is the flag a caller has in order to tell a key worth persisting from one
  that is not.
- **One width, pinned at 32**, because AES-GCM is driven at AES-256 here. A
  width a caller could ask for is a width a caller could ask for too small.
- **Nothing in ``app/`` ships a fallback key.** The claim is held against the
  modules and not only against the loader: every value :mod:`app.config` and
  :mod:`app.storage.master_key` ship is swept for one that could serve as a
  key -- key-width bytes, or a string that base64-decodes to them -- and 256
  generated draws are asserted distinct. A ``DEV_KEY`` written beside the
  loader is a failure of this decision, not a style note.
- **A key that cannot be read is refused in both modes**, never replaced by a
  generated one: a store that quietly wrote under a fresh key would leave
  evidence nobody can open.
- **A refusal quotes nothing**, on ``app.ledger.signing```'s reasoning: the
  configured value is the key itself, so every message names the variable or
  the type. The one value a refusal echoes is the mode name, which is not a
  secret and is what makes it actionable.
- **The loader reads no environment.** Both arguments are required rather than
  defaulted, so a caller cannot store evidence under a key or a mode it never
  asked for.

**Measured, not asserted** -- 43 cases in
``backend/tests/unit/test_master_key.py``: a key configured through
``EVIDENCE_ENCRYPTION_KEY`` is the bytes the operator wrote in either mode;
unset, blank and whitespace are a refusal in production and a fresh key in
development; the mode is folded and trimmed by both readers and an unknown one
is refused by both; a key of the wrong width, a prose key, a hex key, a PEM
and a half-width key are all refused in development too; a ``MasterKey``
refuses a non-bytes key, the wrong width, a mode it does not know and a
non-bool ``generated``; a ``bytearray`` key is copied; ``repr`` carries no key
in any of its three spellings; nothing either module ships is key-width; and
256 generated draws are all distinct.  24 mutations of the shipped lines, 24
killed, every file restored byte-identical afterwards.

**What this forbids.**
- A fallback key, in any module, in any mode.
- Reading an unrecognised mode as ``development``.
- Replacing a malformed or wrongly sized key with a generated one.
- A ``MasterKey`` naming a mode the loader would have refused.
- Any part of the configured value in a refusal or in a ``repr``.

**What this leaves.**
- **Nothing loads a key yet.** 19.1 is the loader alone, so the production
  refusal fires the first time something asks for a key rather than at
  start-up. 19.6 is what puts the store in the screening flow, so a deployment
  running ``APP_ENV=production`` with no key keeps serving until it does.
- **A generated development key is written nowhere**, so evidence written under
  it is unreadable after a restart. That is the ledger key consequence (9.13)
  accepted rather than designed away, and it is why the key is not generated
  in production at all.
- **``APP_ENV`` unset means development**, so a deployment that forgets it is a
  development deployment: the refusal is one variable away, and no task claims
  reading that variable back out of a deployment.

## D155 -- a run's own trail is its timeline, and a stamp older than that is walked last

**Date:** October 3, 2026. **Status:** settled, task 19.1's verification.

**Context.**
18.10's case ``test_tiers_come_out_ordered_by_the_instant_they_were_stamped``
files two ``tier_completed`` events against a real cascade with instants of their
own, writes them in the opposite order to those instants, and answers ``tier_0``,
``tier_early``, ``tier_late``.  D151's ordering bullet -- the event's own instant
and then its id -- puts the cascade's own ``tier_0`` last the moment the wall
clock passes the instants that case names, so it stopped passing at 09:00 UTC
on October 3, 2026 and stayed broken.  **The answer was a claim about when the
suite ran rather than about how a trail is walked**, and only an instant before
the case's own makes ``tier_0`` the earliest row.

**Decision.**
- **A run's timeline opens at the instant its ``screening_created`` event
  carries**, which is the same instant ``app.progress._trace`` already charges
  the first stage from.  An event stamped before that instant cannot be placed
  on the run -- a clock that moved backwards, or a row a writer backdated --
  and is walked last.
- **Each group keeps D151's order**, the instant and then the id.  A run whose
  clock never moved is therefore in the order it was written in, unchanged: a
  rule about a damaged trail, not a reordering of a healthy one.
- **A run that opened with no ``screening_created`` event of its own has no
  instant to be behind**, and is left as the trail holds it, so 18.12's case
  for a stage with nothing before it still reports no window at all.
- **``app.progress._run_events`` is the one place it happens**, because both
  readers walk that one tuple -- the sequence 18.10 and 18.11 answer from and
  the windows 18.12 charges -- and neither grows a second order.
- **The window over such a stamp still reads as zero**, which is
  ``app.progress._elapsed_ms``'s existing rule (D153) and is now the order's too.

**Measured, not asserted** -- 18.10's ordering case, 18.11's case that the two
routes agree after a further tier, and 18.12's backwards-clock case, all green;
the full backend suite 7023 passed and ``scripts/check-all.ps1`` exits 0; six
mutations of the shipped lines, six killed, the file restored byte-identical.

**What this forbids.**
- Ordering a run's events by the stamped instant alone, so that a stamp older
  than the run's opening instant can lead the sequence.
- A second ordering anywhere but ``app.progress._run_events``.
- Dropping or rewriting a backdated event rather than ordering it.

**What this leaves.**
- **A backdated stamp is ordered, not corrected.**  The stage row still carries
  the instant the trail holds, which may precede the run, so the trace reports
  an instant before the run began beside a zero window.
- **The rule is the reader's and is not written back.**  A trail stamped by one
  clock and read by another is ordered by whichever clock opened it.
## D156 -- a per-blob data key is drawn per blob and wrapped under the master key

**Date:** October 3, 2026. **Status:** settled, task 19.2.

**The decision.** :mod:`app.storage.data_key` owns the envelope.
:func:`~app.storage.data_key.generate_data_key` draws ``DATA_KEY_BYTES`` (32)
from the OS CSPRNG; :func:`~app.storage.data_key.wrap_data_key` encrypts that
key under the ``MasterKey`` D154 loaded with AES-GCM, under a nonce drawn per
wrap; and :func:`~app.storage.data_key.unwrap_data_key` opens it. **A blob is
therefore readable only by a holder of the master key, and one blob's key is
worthless for any other blob.**

- **A data key is drawn per blob and held nowhere**, on
  :mod:`app.ledger.salts`' reasoning that a reused secret is not one. It is
  never derived from the master key either: a derived key would leave every
  blob recoverable from the master key alone, which is the property the wrap
  exists to prevent.
- **A nonce is drawn, not counted.** AES-GCM leaks its authentication key
  outright when one nonce repeats under one key, so the nonce comes from the
  CSPRNG on every wrap. ``DATA_KEY_NONCE_BYTES`` is 12, the width AES-GCM is
  specified at, and the library accepts any other -- so that width is pinned
  by a case rather than by the round trip.
- **The wrapped form has one width.** A ``WrappedDataKey`` is a 12-byte nonce
  beside ``DATA_KEY_BYTES + DATA_KEY_TAG_BYTES`` (48) of ciphertext, and
  :meth:`~app.storage.data_key.WrappedDataKey.__post_init__` refuses any other
  before any cryptography runs. A truncated or padded wrapped value is a
  refusal rather than a decrypt, and the length a decrypt would have produced
  is pinned at the same place.
- **A wrapped key that does not open is refused, never returned.** A wrong
  master key and an altered wrapped value are one answer from AES-GCM and one
  answer here: ``DataKeyError`` names both readings and quotes neither key,
  and it is raised ``from None`` so a traceback carries this module's message
  and not the library's.
- **Only a ``MasterKey`` may wrap or open, and only a ``WrappedDataKey`` may
  be opened.** Raw ``MasterKey.key`` bytes handed to either are a ``TypeError``
  naming the type, so the attribute is not the API and the width checks cannot
  be skipped by unwrapping the dataclass.
- **The module reads no environment.** :func:`~app.storage.master_key.load_master_key` answers the master
  key and this module is handed one, on
  D154's reasoning that a key is not read where it is used.
- **The mode is metadata.** A ``MasterKey`` carrying the same bytes under the
  other mode opens the same wrapped key: only the bytes decide.

**Measured, not asserted** -- 33 cases in
``backend/tests/unit/test_data_key.py``: sixty-four generated keys through
wrap and unwrap and back byte for byte; 256 draws all distinct and none equal
to the master key they would be wrapped under; one key wrapped twice
answering two different wrapped forms, both opening to the same key; the
wrapped form holding neither the data key nor the master key in the clear; the
widths pinned; a wrong master key, a key of the other mode's spelling and a
``MasterKey`` handed where a non-``MasterKey`` was refused; a ``bytearray``
data key and a ``bytearray`` field both copied; a ``repr`` carrying no key in
hex, base64 or ``repr``; the refusal suppressing its context; and no value
the module ships being key-width. 23 mutations of the shipped lines, 23
killed, every file restored byte-identical afterwards -- three survived the
first pass and the three cases that close them are the ``DATA_KEY_NONCE_BYTES``
pin, the ``from None`` assertion and the naming of which refusal answered a
short data key.

**What this forbids.**
- A data key derived from the master key, held in a module global, or reused
  between blobs.
- A nonce that is counted, fixed or reused under one master key.
- A wrapped form of any other width, or a wrapped value handed to AES-GCM
  before it is checked.
- Returning anything at all when the wrapped key did not open.
- ``MasterKey.key`` bytes, or any value but a ``WrappedDataKey``, as an
  argument to either half.
- Reading the environment, or loading a key, from this module.

**What this leaves.**
- **Nothing wraps a blob yet.** 19.2 is the envelope alone, so the store is
  still unwritten: 19.3 puts bytes under a data key and 19.6 puts the store in
  the screening flow.
- **The wrapped form has no spelling to persist.** ``WrappedDataKey`` is a pair
  of byte fields and nothing assembles them for storage; 19.3 or 19.6 owns
  that column or filename, and neither exists yet.
- **The wrap is bound to nothing but its nonce.** AES-GCM is called with
  ``None`` as associated data, so a wrapped key is not yet tied to the blob or
  the hash it belongs to; moving one is not detected. Binding it is a decision
  about the reference format, which 19.3 designs.
- **A wrong key and a tampered wrap are indistinguishable here**, deliberately:
  AES-GCM cannot separate them and a store that tried would be claiming a
  distinction the primitive does not make.
