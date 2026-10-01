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
  identity, so three `None`s answer `[]` and a number is never read against an
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
  exactly that reason: the answer carries `null`s and empty lists, which is a
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
