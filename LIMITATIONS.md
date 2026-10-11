# LIMITATIONS.md — what this build does not do

`DEMO.md` is the walkthrough; this file is the other half. Everything here is a
statement the build cannot currently support, written down so nobody has to
discover it in a demo.

The labels are the same two `DEMO.md` uses, with the same strictness:

- **Measured** — observed by running this build, or read from a committed
  generated file the served page loads verbatim.
- **Designed** — read from source. True as a statement about how the build is
  made; not an observation, and never a performance result.

Where a limitation was **fixed**, it says so and names the task that fixed it.
Nothing here is aspirational, and nothing here is phrased as a plan.

---

## 1. The cascade runs Tier 0 and nothing else

`backend/app/screening.py:83` maps one name — `runner.TIER_NAME` — to one
runner, `runner.run_tier0`, and `CASCADE` at line 90 is `tuple(_TIER_RUNNERS)`.
So a screening submitted today runs the deterministic MRZ parser and stops.

**Designed.** Tier 1's OCR engines and Tier 2's seven modules, and the
`crossdoc` package, all exist, all have tests, and none of them is reachable
from `POST /api/screenings`.

This is the single largest gap in the project. A flag from Tier 2 cannot appear
in a real screening record today, because nothing calls the module that would
raise it. The per-tier latency metrics added in 26.8 therefore report one tier,
not three.

## 2. Every Tier 2 module is a labelled stand-in

Seven modules ship in `backend/app/pipeline/tier2/`. All seven answer
`is_stub=True`. That flag is not decoration: `base.py` validates it as a `bool`
on every result, and `flags.py` carries `weight_band` beside it.

| Module | `model_version` | What it actually does |
| --- | --- | --- |
| `anomaly.py` | `isolation-forest-v0` | A real `IsolationForest`, fitted on a committed fixture of synthetic pages this repository drew. |
| `copy_move.py` | `copy-move-v0` | Block-matching for duplicated regions. |
| `deepfake.py` | `heuristic-v0` | One cue. No model. |
| `ela.py` | `ela-v0` | Error-level analysis. Not calibrated against ground truth. |
| `morph.py` | `heuristic-v0` | Two cues. No model. |
| `noise_residual.py` | `noise-residual-v0` | Printed-noise signature. |
| `stamp.py` | `stamp-v0` | Reads a stamp as a pixel statistic, so there is no region map to draw. |

**Measured, by reading the source.** Each module's own module docstring says
which of these is true, and `anomaly.py` is the clearest example: a forest was
really fitted, and the module still answers `is_stub`, because *the fixture is
synthetic artwork this repository drew*.

## 3. No model weights ship, and none can be trained here

Nothing in this repository trains or loads a trained weightset for face
matching, morph detection or deepfake detection. `tasks.md` parks this
deliberately under **Deferred**: *"Every model-dependent module ships as an
interface plus a labelled heuristic stand-in."*

- `deepfake.py` and `morph.py` are `heuristic-v0` — a cue and two cues. There
  is no weight file to swap.
- The interfaces exist and are tested, so a real classifier drops in behind
  them. That is the seam, not the implementation.
- `tests/fixtures/face_evaluation.py` (27.10) and
  `tests/fixtures/morph_evaluation.py` (27.11) report FAR/FRR and morph rates
  honestly when nothing is configured: the default run prints empty `--` slots
  and names all three missing inputs. A stand-in's rate is labelled `stub`, and
  an ensemble carrying one is labelled `stub` too.

**Designed.** No FAR or FRR figure has been measured, and none is shown
anywhere in the app.

## 4. Every published number describes this repository's own synthetic corpus

The Results page shows 645/645 field accuracy, 0/36 tamper catch and 0/9 false
alerts, each tagged **Measured** with **Synthetic document corpus** beside it
(D221, D230). That is exactly what those words mean:

- **Measured, on drawn pages.** `document_manifest.py` is the ground truth and
  the corpus is generated, not photographed. No figure here is a measurement
  about a real identity document.
- **The tamper catch rate is 0/36 and that is a real finding, not a bug to be
  hidden.** 27.3 guarantees no injection touches the MRZ, and the default
  detector reads the zone and nothing else. Region overlap and localisation
  print `--` / **Not measured** because nothing was caught to overlap.
- **Thresholds are uncalibrated.** The About page has said so since the start:
  *"Thresholds have not been calibrated against a real document set."*

The tier latency table (27.9) carries the designed targets from `abstract.txt`
and, for Tiers 1 and 2, no measured column at all.

## 5. Browser state — what has been seen, and what still has not

Before Part 25, **no page in this repository had ever been rendered in a
browser.** That has changed, and this is the honest account of how far.

**Verified in a real browser (Measured):**

| What | Where it is recorded |
| --- | --- |
| 10 pages at 320, 768, 1024 and 1440 CSS px, headless Chromium | `docs/viewport-shots/` (25.7) |
| The same 10 pages in light and dark theme | `docs/theme-shots/` (25.8) |
| The seven demo steps, driven in order against a live local pair | `DEMO.md` (28.1) |
| No upload request before the submit click, `localStorage` raising `SecurityError` under private browsing | `docs/private-check/` (25.12) |
| `/health`, each deployed `api-config.js`, an upload through the network panel | `docs/deployed-check/` (25.13) |

**Still unverified:**

- **The full screening flow has never been driven end to end.** 25.11 is
  `[BLOCKED]`: `screening.html` is never written by the build, so the Overview
  screen's **Try the demo** CTA links to a 404 and the upload overlay has no
  other entry point. Nobody has watched the nine-check panel render. The fix is
  a click handler on `#start-screening` calling the `showSourceChooser()`
  already in `frontend/home.js`, plus dropping the `href="./screening.html"`
  that `home.test.cjs:17` (as `START_HREF`) and `:335` pin.
- **No history row has ever been drawn in a browser.** Without
  `alembic upgrade head` the screen reads *Could not load the history*. That is
  why `DEMO.md` labels the search box a measured control with designed
  behaviour, and drops the claim that the history showed a score, result and
  mode (C19, C21).
- **The Results page has never been opened in a browser.** Its table is proved
  by driving `draw()` over the committed file in `results.test.cjs` and
  `test_results_view.py`, which is not the same thing.
- **No real device.** Every render above is headless Chromium at CSS
  breakpoints. No phone, no touch target, no assistive technology, no browser
  other than the one bundled.
- **The `.tech` deployment cannot reach the API.** Its `api-config.js` bakes in
  an empty base URL so the page issues zero requests, and its
  `location.origin` is `https://` while the serving Cloud Run revision
  allowlists `http://project-drishti.tech`. Both need fixing on the user's side:
  `DRISHTI_API_BASE_URL` on the Pages build, and `https://project-drishti.tech`
  in `CORS_ORIGINS`. Until then the live check reaches the API from 1 of 3
  probed origins.

## 6. Ops gaps that are recorded, not fixed

- **No authentication, by decision.** `docs/DECISIONS.md` D2. There is no
  login, no session and no credential field. The frontend's `actor` is a
  configurable station label, not an identity.
- **The analysis endpoint is unauthenticated and unrated.** 26.9 — the
  rate-limit quota and the synthetic-image notice — is still unchecked, so the
  notice in the About page is the only guard. Use synthetic images only.
- **The container image has never been built.** 26.1 and 26.2 are `[BLOCKED]`
  on this machine: no container runtime on the Windows PATH. The static
  contract tests pass; `/health` from the image is unproven.
- **CI has never run green.** 26.6's workflow and its 7 contract cases pass
  locally. The run itself needs GitHub's runner, and this checkout is never
  pushed.
- **The screening history is not persisted between visits**, per the About
  page, and the local API writes `backend/drishti.db`, which three tests treat
  as a stray file.

## 7. What would change each label

| Limitation | What would lift it |
| --- | --- |
| Tier 0 only in the cascade | Register Tier 1 and Tier 2 runners in `_TIER_RUNNERS`. |
| Tier 2 stubs | A fit on real captures, replacing the synthetic fixture behind `AnomalyScorer`; a real classifier behind the `DeepfakeClassifier` and `MorphClassifier` interfaces. |
| No weights | Out of scope for this repo by the Deferred list. Needs a training pipeline and a data access agreement. |
| Synthetic-corpus numbers | A corpus of real documents with a lawful basis for holding it, and thresholds calibrated against it. |
| Unverified browser flow | Wire the upload CTA, then drive 25.11's steps for real. |
| `.tech` cannot reach the API | Set the Pages build variable and the Cloud Run origin list. |

## Where the rules behind this live

`docs/DECISIONS.md` holds the reasoning (D118, D119, D121, D124, D221, D225,
D228, D229, D230 among them). `DEMO.md` holds the claim ledger. The About page
holds the four-item version a user sees in the product, which is a subset of
this file and not a replacement for it.

`tasks.md` records which of these are `[BLOCKED]` and why. Nothing in this file
is a task in disguise, and nothing in it is fixed in passing.