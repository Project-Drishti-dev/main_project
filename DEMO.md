# DEMO.md — the three-minute judge walkthrough

Follow the steps in order. Each one names the screen you should be looking at
and the single action to take. There is no sign-in, no account and no password
anywhere in this build, and no step needs a real identity document.

Total speaking time: about three minutes, after the one-time start-up in step 0.

---

## Step 0 — Start both halves (once, about 3 minutes)

**Terminal 1 — the analysis API, on port 8080.** From the repository root:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn main:app --port 8080
```

**Terminal 2 — the site, on port 5500:**

```powershell
cd frontend
npm install
npm run preview
```

`npm run preview` builds `frontend/dist/` and then serves it, so nothing stale
can be on screen.

**Open** <http://127.0.0.1:5500/>. The root URL redirects to the Overview
screen.

**Before you start, check the top bar.** If it reads
**Connected to the quality service**, both halves are up. If it does not, the
API is not running or is not on port 8080.

`alembic upgrade head` creates the local SQLite schema that the history screen
in step 4 reads. Without it, that screen shows *Could not load the history*
instead of rows.

---

## Step 1 — Overview: what the product is (0:00 – 0:20)

**Screen:** Overview.

**Action:** read the headline, *Public image-quality demo*, then the three
summary cards: *Nine signals, one clearer view*, *Sent only when you submit*,
and the banner *Experimental image-quality checks only — not identity
verification*.

**Say:** one image in, nine quality signals out, so a person retakes a bad
photo instead of submitting it. This screens image quality; it does not decide
who a document belongs to.

---

## Step 2 — Guide: the nine checks (0:20 – 0:55)

**Screen:** Guide.

**Action:** click **Guide** in the left sidebar.

**Then:** read **01 Sharpness**, which is already open. It gives the cause —
*Is the text crisp, or does it look soft?* — and a **Fix** line, *Rest your
phone or scanner on a surface, or hold steady.* Click **02 Noise** to open and
close the next one.

**Say:** nine checks, numbered 01 to 09, each with a cause and a fix, plus the
five capture rules under *Before you upload*.

---

## Step 3 — Results: every number beside its dataset (0:55 – 1:35)

**Screen:** Results.

**Action:** click **Results** in the left sidebar.

**Then:** read the first rows aloud. **Field extraction accuracy — 645/645 —
Measured — Synthetic document corpus.** **Tamper catch rate — 0/36 —
Measured.** **False-alert rate — 0/9 — Measured.** Now point at **Region
overlap (mean IoU)**, which shows `--` and the tag **Not measured**.

**Say:** this is the page I would put in front of a reviewer. No number is
shown without the dataset it was read over, and a rate with no denominator
prints `--` instead of a zero. The test suite drives the table's draw function
over the committed data file and fails if a bare number ever appears.

**If asked:** those figures describe this repository's own synthetic corpus.
They are not measurements on real identity documents.

---

## Step 4 — Previous screenings: the record (1:35 – 2:00)

**Screen:** Previous screenings.

**Action:** click **Previous screenings** in the left sidebar. Type `TD3` into
**Search screenings**; the list filters as you type.

**Say:** the run history — each row's id, document, time, score and result
band, searchable by id and filterable by risk band. Two things I will not
oversell: the **Mode** column reads *Not recorded* on every row, and the
product's own About page calls this history sample data rather than a real
record store.

**If the screen reads *Could not load the history*:** the schema from step 0 is
missing. Stop, run `alembic upgrade head` in `backend/`, restart the API and
reload.

---

## Step 5 — Settings: dark theme, live (2:00 – 2:20)

**Screen:** Settings.

**Action:** click **Settings** in the left sidebar. Under **Theme**, click the
**Dark** radio button. The entire interface restyles immediately.

**Say:** light and dark come from the same token set, and the choice is stored
in this browser only — there is no account behind it.

**Action:** click **Light** to go back before the next step.

---

## Step 6 — About: what this build does not do (2:20 – 2:45)

**Screen:** About.

**Action:** click **About** in the left sidebar, then scroll to **Known
limitations**.

**Say:** camera capture is a placeholder, the screening history is not
persisted between visits, the analysis endpoint is unauthenticated and unrated
so it should only be used with synthetic images, and the thresholds have not
been calibrated against a real document set.

---

## Step 7 — Close (2:45 – 3:00)

**Screen:** Overview.

**Action:** click **Overview** in the left sidebar.

**Say:** image-quality screening in the browser, nine signals, every published
number carrying its dataset, and the parts that are not finished labelled as
not finished.

---

## Known defect on this build — the "Try the demo" button 404s

The Overview screen's primary call to action, **Try the demo**, points at
`./screening.html`. The build does not write that file, so the button lands on
a 404 and the image-upload overlay cannot be opened from the page. Steps 1 to 7
do not touch it, so the walkthrough above runs without it.

**The fix, if you want the upload flow in the demo.** Give `#start-screening` a
click handler that calls the `showSourceChooser()` already defined in
`frontend/home.js`, and remove the `href="./screening.html"` that
`frontend/home.test.cjs` currently pins (the `START_HREF` constant and the
assertion at line 315).

**To try the upload flow by hand once it is wired**, draw a synthetic document
from the repository's own corpus. Never use a real identity document:

```powershell
cd backend
python -c "import cv2; from tests.fixtures import document_corpus as c; cv2.imwrite('sample.png', c.generate().image)"
```

Then on the Overview screen: **Try the demo** → **Upload an image** → **Browse
files** → choose `sample.png` → **Review quality checks**. The panel is built to
list all nine checks with a score, a unit, a pass / fail / **N/A** state, the
rule and the reasons. That is what the render path writes; nobody has watched
it render, because on this build the button that opens it 404s.

**Glare** and **Card coverage** return **N/A** when the request resolves to scan
mode, with the reason *not applicable to flat scans / digital documents*. The
page sends `mode=auto` and the service decides, so whether a drawn synthetic
page lands on `scan` is the classifier's call and has not been observed here.

---

## Claim ledger — every claim above, and what backs it

Two labels, used strictly:

- **Measured** — observed by running this build, or read from a committed
  generated data file that the served page loads verbatim.
- **Designed** — read from source. True as a statement about how the build is
  made; not an observation, and never a performance result.

Navigation instructions ("click **Guide** in the left sidebar") and the reviewer's opinion in step 3 are not claims and carry no label. Everything else that asserts something about this build does.

Every aspirational sentence was rewritten before this list was written. Two did
not survive in any form and are listed as **Removed** or **Rewritten** below,
with what replaced them.

### Front matter

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C1 | No sign-in, no account, no password anywhere in this build. | Designed | about.html:138 states it; no `type="password"` control exists in any source page; pages.js:344 refuses a password change. |
| C2 | No step needs a real identity document. | Designed | The Overview banner says use synthetic images; the corpus is drawn, not photographed. |
| C3 | About three minutes of speaking. | Designed | An estimate. No timer was run over the script. |

### Step 0 — start-up

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C4 | `alembic upgrade head` then `uvicorn main:app --port 8080` brings the API up. | Measured | 28.1 ran it; `/health` and `POST /api/analyze` both answered. |
| C5 | `npm run preview` builds `frontend/dist/` and then serves it, so nothing stale can be on screen. | Measured | preview.cjs calls `buildSite()` before it serves; 28.1 served eleven built pages. |
| C6 | The root URL redirects to the Overview screen. | Measured | 28.1 saw it; index.html redirects to `./home.html` twice over. |
| C7 | *Connected to the quality service* means both halves are up; anything else means the API is down or off port 8080. | Measured | 28.1 saw the label. api-config.js forces `http://localhost:8080` on 127.0.0.1, so the fourth state cannot appear at that URL. |
| C8 | Without the migration, step 4 reads *Could not load the history*. | Measured | 28.1 saw it; `GET /api/screenings` answered 500. |

### Step 1 — Overview

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C9 | The headline, the three cards and the banner read as quoted. | Measured | 28.1 read them; every string matches home.html. |
| C10 | One image in, nine quality signals out. | Measured | 28.1: `POST /api/analyze` returned all nine modules. |
| C11 | This screens image quality; it does not decide who a document belongs to. | Designed | home.html:11 states the boundary, and all nine modules are image-quality checks. |
| C12 | "so a person retakes a bad photo instead of submitting it". | Designed | The product's purpose, not an observed outcome. |

### Steps 2 and 3 — Guide and Results

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C13 | Nine checks, numbered 01 to 09, each with a cause and a Fix line. | Measured | 28.1 read 01 Sharpness; guide.html carries nine accordion bodies. |
| C14 | 01 Sharpness is already open; 02 Noise opens and closes. | Measured | 28.1 drove both; `#check-sharpness` ships with class `show`. |
| C15 | Five capture rules under *Before you upload*. | Measured | 28.1 counted them; guide.html:358-376 lists five. |
| C16 | 645/645, 0/36 and 0/9, each tagged Measured; Region overlap shows `--` / Not measured. | Measured | 28.1 read these rows. They are the committed `results-metrics.js` the page loads. |
| C17 | No number appears without its dataset, and a rate with no denominator prints `--`. | Designed, enforced | results.test.cjs asserts `checkMetric` throws `ResultsError ... names no dataset` for a metric with an empty dataset. |
| C18 | Those figures describe this repository's synthetic corpus, not real identity documents. | Measured | The dataset's own `detail` string says so, and document_manifest.py is the ground truth. |

### Step 4 — Previous screenings

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C19 | *Search screenings* is there and filters as you type. | Measured control, designed behaviour | 28.1 saw the labelled box. pages.js:171 binds `input` to the redraw, but no row existed here to filter. |
| C20 | Rows carry a score and a result band, and filter by risk band. | Designed | drawRow writes score and result cells; screenings.html carries low, review and high chips. No row has been drawn on this machine. |
| C21 | "every screening run on this station, with its score, result and mode". | Removed | The Mode column is written *Not recorded* on every row (screenings-list.js:320), and about.html:145 calls the history sample data, not a record store. The Say line now says both. |
| C22 | The bands are Low, Review and High. | Designed | screenings.html chips; result-band.js names the same three. |

### Steps 5 to 7 — Settings, About, close

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C23 | The Dark radio restyles the interface immediately. | Measured | 28.1 clicked it; preferences.js persists, then applies, setting `data-theme`. |
| C24 | Light and dark come from the same token set. | Designed | pages.css and home.css override `--ux4g-*` tokens under `html[data-theme="dark"]` rather than restyling by hand. |
| C25 | The choice is stored in this browser only; there is no account behind it. | Measured | 28.1 saw `drishti.preferences.v1` written and the page repaint; about.html:138. |
| C26 | About → Known limitations lists the four items as quoted. | Measured | 28.1; about.html:154-184 matches them verbatim. |
| C27 | Camera capture is a placeholder. | Designed | The About page says so; nothing wires camera.js to a capture path. |
| C28 | Nine signals, every published number carrying its dataset, unfinished parts labelled as unfinished. | Measured | 28.1; results-metrics.js and the limitations list. |

### The known defect and the upload flow

| # | Claim | Label | What backs it |
|---|-------|-------|---------------|
| C29 | *Try the demo* points at `./screening.html`, the build never writes it, so it 404s. | Measured | 28.1 landed on the 404; the build's page list has no screening.html. |
| C30 | The upload overlay has no other entry point. | Measured | 28.1; nothing in the built pages opens `#screening-modal`. |
| C31 | The fix is a handler calling `showSourceChooser()` plus dropping the pinned href. | Designed | A proposal, not a change. `showSourceChooser` is home.js:464; home.test.cjs:17 pins `START_HREF` and :315 pins the href in the markup. |
| C32 | The one-line corpus command draws a synthetic page. | Designed | `generate()` returns a SyntheticDocument carrying `.image`. The command has not been run here. |
| C33 | The panel lists nine checks with score, unit, state, rule and reasons. | Designed | What the render path writes. Nobody has watched it render, because the button that opens it 404s. |
| C34 | *Glare* and *Card coverage* return **N/A** on a flat page. | Rewritten | m5_glare.py:76-78 and m8_coverage.py:56-58 return N/A when `mode == "scan"`. The page sends `auto` and the service resolves it, so the resolved mode decides it, not the page's appearance, and it has not been observed. The paragraph now says that. |

## The bar this file holds to

A number appears here only with the corpus it was read over. A behaviour is
stated as done only if it was seen on screen. Everything else is labelled
designed, and a designed claim never borrows the grammar of a measured one.