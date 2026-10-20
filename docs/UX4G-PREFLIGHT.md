# UX4G preflight notes

One file, one section per new page. Written **before** the markup it governs,
because `AGENTS.md` and the `ux4g-design` skill both require the component
list to exist first, and because a list written after the markup is a
description of what was built rather than a decision about what to build.

Every class, data attribute and variant named below was read out of the
installed stylesheet
(`frontend/node_modules/ux4g-web-components/styles/ux4g.css`, package
`ux4g-web-components@2.1.0`), not recalled.

---

## Part 22 - `frontend/screening.html`

### Delivery method and theme

- **Delivery:** npm `ux4g-web-components@2.1.0`, already installed and already
  wired by `frontend/shell.html` (`styles/ux4g.css` +
  `dist/runtime/design-system.js`). CDN delivery is not mixed in.
- **Theme:** the **default UX4G light theme**, no root token override block.
  This is D3's settled answer, not a fresh choice - D3 records the
  maintainer's decision, forbids re-asking it, and states that when a new page
  is added the theme question is already answered. Dark and system remain
  available at runtime through `preferences.js` because they are UX4G's own
  tokens, not a custom theme.
- **Buttons carry no `!important`.** As of v2.0.1 button dimensions sit in a
  zero-specificity `:where()` wrapper, so no component-selector override is
  needed anywhere on this page.

### Components, variants and sizes

Base class first, then variant, then size, on every line.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Radio group | `.ux4g-radio` + `.ux4g-radio-header`, `.ux4g-radio-control`, `.ux4g-radio-input`, `.ux4g-radiomark`, `.ux4g-radio-content`, `.ux4g-radio-label`, `.ux4g-radio-description` | `.ux4g-radio-desc-helper` / `-warning` / `-error`; group-level `.ux4g-radio-error` | `.ux4g-radio-md` | Document-type selector (22.2). `md` matches every radio already on the site. |
| Button | `.ux4g-btn` | `.ux4g-btn-primary` | `.ux4g-btn-md` | "Screen document" (submit). |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-primary` | `.ux4g-btn-md` | "Choose a file", "Use camera", "Retake", "Analyse anyway". |
| Button | `.ux4g-btn` | `.ux4g-btn-text-neutral` | `.ux4g-btn-md` | "Cancel". |
| Button | `.ux4g-btn` | `.ux4g-btn-text-primary` | `.ux4g-btn-sm` | "Change image" inside the progress panel. |
| Upload | `.ux4g-upload`, `.ux4g-upload-panel`, `.ux4g-upload-content`, `.ux4g-upload-icon-wrap`, `.ux4g-upload-icon`, `.ux4g-upload-titleblock`, `.ux4g-upload-heading`, `.ux4g-upload-hint`, `.ux4g-upload-btn`, `.ux4g-upload-file-list`, `.ux4g-upload-file-item`, `.ux4g-upload-file-row`, `.ux4g-upload-file-leading`, `.ux4g-upload-file-icon`, `.ux4g-upload-file-copy`, `.ux4g-upload-file-name`, `.ux4g-upload-file-description`, `.ux4g-upload-file-statusbox`, `.ux4g-upload-file-status`, `.ux4g-upload-file-remove`, `.ux4g-upload-file-retry`, `.ux4g-upload-error-msg`, `.ux4g-upload-actions`, `.ux4g-upload-more` | one state at a time on the panel: `.ux4g-upload-state-default` / `-selecting` / `-scanning` / `-uploaded` / `-error`; `.ux4g-upload-file-item-error` on a rejected row | **none ships** - see G3 | Chosen file, local preview, and the rejected-type message (22.3, 22.7). |
| Card | `.ux4g-card` + `.ux4g-card-body` | `.ux4g-card-outline` or `.ux4g-card-solid` (they share one border rule and differ in background) | none ships | One bounded surface per step: type, source, camera, progress. No existing page names either modifier, so 22.2 follows the existing pages and names neither until it has seen the rendered result. |
| Progress bar | `[data-ux-progress-bar]` root, `.ux4g-progress-bar-track` + `.ux4g-progress-bar-fill` | `[data-ux-shape=rounded]`; `[data-ux-label-placement=inside]` (20px track, label inside the fill) | **none ships** - track is 8px by default, see G3 | Whole-cascade progress (22.8). Fill width is driven by `--ux4g-progress-value`, 0-100. |
| Tag | `.ux4g-tag` | `.ux4g-tag-filled-success` / `-warning` / `-error` / `-info` / `-neutral` / `-primary`, or the `-outline-` / `-text-` families | `.ux4g-tag-s` (the only size in the sheet) | Per-tier status beside each progress row (22.8). |
| Alert | `.ux4g-alert` + `.ux4g-alert-icon`, `.ux4g-alert-content`, `.ux4g-alert-title`, `.ux4g-alert-message`, `.ux4g-alert-actions`, `.ux4g-alert-footer`, `.ux4g-alert-close` | `.ux4g-alert-info`, `.ux4g-alert-warning`, `.ux4g-alert-error`, `.ux4g-alert-success` | none ships | Permission denied and insecure context (22.5, `.ux4g-alert-error`); quality-gate verdict (22.7, `-warning` / `-success`). |
| Skeleton | `.ux4g-skeleton-block`, `.ux4g-skeleton-title`, `.ux4g-skeleton-subtitle`, `.ux4g-skeleton-circle`, `.ux4g-skeleton-btn`, `.ux4g-skeleton-main` | none | none | Loading state while the screening runs (22.10). |
| Spinner | `.ux4g-spinner` | - | `.ux4g-spinner-md` | While the chosen file is read and the submit request is in flight. Inside the upload panel the component's own `.ux4g-upload-spinner` is used instead. |
| Empty state | `.ux4g-empty-state`, `.ux4g-empty-state-content`, `.ux4g-empty-state-icon` | none | none | The "no image chosen yet" state. Design.md 13 forbids a bespoke empty illustration. |

### Amendment for 22.10 -- the skeleton ships seven shapes, not six

The Skeleton row above lists six names and leaves out
`ux4g-skeleton-sidebar-card`, which the installed stylesheet does ship:
`grep -o '\.ux4g-skeleton[a-z-]*'` over
`node_modules/ux4g-web-components/styles/ux4g.css` returns all seven and no
others, and `frontend/result-skeleton.js` holds the same seven against that
grep in `result-skeleton.test.cjs`. A page may use any of the seven; a shape
carrying an eighth `ux4g-skeleton-*` class is a typo or an invented component,
and the binding refuses it by name rather than drawing it as a grey block.

Two further names the row did not cover, both settled by 22.10:

- **The shapes are the page's own markup.** The binding switches the
  container and every shape below it and draws none of them itself, so 23.1
  decides what a screening looks like and this note adds no class.
- **The state is switched with `hidden`, not with a class.** UX4G ships no
  loading/loaded variant for the skeleton, so there is nothing to swap, and a
  page cannot drift into a third state by adding a class of its own.
### Amendment for 22.4 -- the shutter, and one primary per page

The button table above names "Screen document" as the only
`.ux4g-btn-primary` on the page and lists "Use camera" and "Cancel", but it
never named the **shutter** the capture path needs: without one there is no
control that draws a frame. 22.4 adds it as
`.ux4g-btn` + `.ux4g-btn-outline-primary` + `.ux4g-btn-md`, labelled
"Take photo", inside the camera card beside "Cancel". It is deliberately
**outline** rather than primary: a page carries one primary action, and on the
screening page that is "Screen document". 22.4 adds no new component class,
no new size and no custom CSS beyond the video's own aspect box (G1).

Two further names the table above did not cover, both settled by 22.4:

- **The consent line** is a plain paragraph inside the camera card, carrying
  `camera.js`'s own `CONSENT` string. It is not a UX4G component -- there is
  no alert variant for standing copy an officer reads once -- so the copy has
  one home in the module and the markup holds the container, which is the
  arrangement D167 already settled for sentences.
- **The capture surface** is a native `<video>` plus a hidden `<canvas>`, per
  G1. Neither is styled by UX4G; the canvas carries no class and is not in the
  table because it is never seen.

`.ux4g-alert-narrow` exists in the sheet and is **not** used: it is a fixed
`padding-inline: 25%`, which is not a safe width for a two-sentence refusal at
320px.

### What UX4G cannot meet

Each of these is a real gap, named here rather than discovered mid-markup.
Custom CSS stays minimal and justified, per rule 5.

- **G1 - There is no camera-capture component.** `grep -i camera` over the
  shipped stylesheet returns nothing, and Design.md 12 marks Biometric Capture
  absent on Web (it exists on Flutter only). 22.4 and 22.5 therefore use a
  native `<video>` driven by `getUserMedia` inside a `.ux4g-card`, with
  `.ux4g-alert-error` as the container for both refusal sentences. No custom CSS
  is needed beyond the video's own aspect box.
- **G2 - The progress bar and the skeleton ship no ARIA.** The component is
  classes and data attributes only: no `role="progressbar"`, no
  `aria-valuenow` / `aria-valuemin` / `aria-valuemax`, no `aria-valuetext`, no
  live region, and no `aria-busy` or `aria-hidden` on the skeleton shapes. 22.11
  writes all of these by hand onto the same elements. The live region itself is
  a bare `role="status" aria-live="polite"` div - no component claims it.
- **G3 - Five of these components have no size modifier at all.** Upload,
  Card, Progress bar, Alert and Skeleton each ship exactly one size. The page
  therefore offers no compact variant and 22.3/22.7 must not invent
  `ux4g-upload-sm`. Density comes from the documented spacing and gap
  utilities the shell already uses (`ux4g-gap-row-*`, `ux4g-padding-*`), never
  from a new size class.
- **G4 - There is no dropzone.** `grep -i dropzone` returns nothing.
  `.ux4g-upload` is a button plus a file list, not a drop target, and
  `home.html`'s current `.upload-dropzone` is bespoke CSS in `home.css`. No
  Part 22 task asks for drag-and-drop, so the page ships the button path and
  the bespoke dropzone is **not** carried over. If a later task wants it, that
  is new custom CSS and needs its own decision here first.
- **G5 - `.ux4g-upload` is CSS-only.** The shipped runtime's behaviours are
  Dropdown, Collapse/Accordion, Offcanvas, Tooltip, Popover, Toast, Carousel,
  Tabs and Scrollspy - nothing for upload. So the native
  `<input type="file" accept="image/jpeg,image/png,image/webp">` carries the
  constraint, and every behaviour in 22.3-22.11 (type and size validation,
  preview, capture, retake, SSE, polling fallback) is ours.
- **G6 - `document_type` has no server-side vocabulary.** `POST /api/screenings`
  takes `document_type` as a free non-blank form string defaulting to
  `"unspecified"`; nothing in `app/` enumerates the values. The radio group is
  therefore a **claim the officer makes**, and its labels must read that way
  ("Passport", "Visa", "National ID", "Not sure") rather than as a closed set
  the server validates. Widening or renaming the list is a backend decision.
- **G7 - `mode` is the one field with a real server vocabulary.**
  `ALLOWED_MODES = {"auto", "photo", "scan"}` is refused server-side, so camera
  capture sends `photo` and a file upload sends `auto`. This is noted because
  the asymmetry with G6 is easy to miss and would otherwise be decided in
  markup.

### Open item for 22.2 - not a UX4G question

`screening.html` has no nav key of its own. `frontend/shell-tokens.js` carries
exactly six (`home`, `screenings`, `profile`, `settings`, `guide`, `about`), and
D168 refuses an `activeNavKey` outside that table. 22.2 must either mark the
page `activeNavKey: "screenings"` - which lights the *Previous screenings*
link, a different page - or Part 21 grows a seventh key. That is a shell
decision, recorded here rather than invented in markup.

### Confirmation owed before 22.2

This note settles the component list. 22.2 writes markup, so it needs the
maintainer's explicit confirmation that D3's default theme still stands (no
custom colours). Nothing above changes with the answer except a `:root`
override block, which is added only if the answer is a branded theme.

### Amendment for 22.11 -- G2 closed, and the ARIA written by hand

G2 is now written rather than merely recorded. Each module writes the
attributes G2 found missing onto the elements it already builds, and adds no
class, no size and no CSS:

- **Progress bar** (`progress-panel.js`): `role="progressbar"`,
  `aria-label`, `aria-valuemin="0"`, `aria-valuemax="100"`,
  `aria-valuenow` (absent while indeterminate) and `aria-valuetext`, which is
  the same string as the visible `[data-ux-progress-label]` text. The bar is
  indeterminate until the done frame carries the run's own step count (D151).
- **Live region**: a bare `role="status" aria-live="polite"` div the panel
  builds beside the bar. No component claims it, per G2.
- **Skeleton** (`result-skeleton.js`): `aria-busy` on the container, written
  with `hidden` by the same call, and `aria-hidden="true"` on every shape.
- **Alert** (`quality-gate.js`): `role="status" aria-live="polite"` written
  at binding, so the region is listening before the first verdict lands.

The label placement the Progress bar row above names is `outside`, not the
`inside` the row lists: the bar starts empty, and a label inside a 0%-wide
fill is a label nobody can read. `outside` ships in the sheet alongside
`inside`, and `progress-panel.test.cjs` holds the row's own reading.

---

## Part 23 - `frontend/result.html`

### Delivery method and theme

- **Delivery:** npm `ux4g-web-components@2.1.0`, already installed and already
  wired by `frontend/shell.html` (`styles/ux4g.css` +
  `dist/runtime/design-system.js`). The page ships no stylesheet and no script
  of its own -- it is a fragment the build fills -- so no CDN path is mixed in.
- **Theme:** the **default UX4G light theme**, no root token override block.
  The answer is D3's and `tasks.md`'s hard constraints record it as already
  chosen ("Do not ask again, do not add custom theme tokens"), so the skill's
  step 3 was answered from the repository rather than re-asked, and a default
  answer adds no `:root` block. Dark and system stay available at runtime
  through `preferences.js`, which are UX4G's own tokens and not a custom theme.
- **The page loads no script.** `overlays` and `pageScripts` are empty, so
  `result-skeleton.js` is still loaded by no page and `staticFiles` still does
  not copy it; D173's two-way asset check is unchanged. The shapes below are
  markup with no reader yet, which is the debt 22.10 already recorded.

### Components, variants and sizes

Base class first, then variant, then size. Rows marked *later* are the plan
for 23.2 onward and are **not** in the 23.1 markup, which is the shell, a page
header, the loading container and the result surface.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Skeleton | `.ux4g-skeleton-title`, `.ux4g-skeleton-subtitle`, `.ux4g-skeleton-main`, `.ux4g-skeleton-sidebar-card` | none | none ships | The loading container `#result-loading`, one shape per region of the page: the band and score line, the summary line, the document, the flag list. Read by `result-skeleton.js`, switched with `hidden`. |
| Layout utility | `.ux4g-d-flex`, `.ux4g-flex-column`, `.ux4g-gap-y-l` | n/a | `gap-y-l` | The loading container's own stacking. No custom CSS. |
| Tag | `.ux4g-tag` | `.ux4g-tag-filled-success` / `-warning` / `-error` | `.ux4g-tag-s` (the only size in the sheet) | The band badge (23.4) and the `summary_source` / `verification` badges (23.8). Fixed by the task text, so the choice is not open here. |
| Card | `.ux4g-card` + `.ux4g-card-body` | `.ux4g-card-outline` or `.ux4g-card-solid` (same border rule, different background) | none ships | One bounded surface each: contributions (23.7), summary (23.8), decision form (23.9), versions (23.11). As on Part 22, no existing page names either modifier and this page names neither until it has seen the rendered result. |
| Image | `.ux4g-img`; container `.ux4g-img-overlay` + `.ux4g-img-rounded` | `.ux4g-img-fluid` is not used -- `.ux4g-img` already sets `max-width: 100%` | none ships | The screened document (23.2). `.ux4g-img-overlay` is what makes the region overlay possible: it is the only rule in the sheet that gives an image container `position: relative` and `overflow: hidden`. |
| List | `.ux4g-list` + `.ux4g-list-item`, `.ux4g-list-item-row`, `.ux4g-list-item-start`, `.ux4g-list-item-end` | `.ux4g-list-default` / `-success` / `-warning` / `-error` | `.ux4g-list-m` | The flag list grouped by tier (23.5), one row per flag. |
| Divider | `.ux4g-divider-horizontal` | `.ux4g-divider-horizontal-text` when the tier name sits in the rule | none ships | Between tier groups in the flag list (23.5). |
| Empty state | `.ux4g-empty-state`, `.ux4g-empty-state-content`, `.ux4g-empty-state-icon` | none | none | A screening that returned no flags at all (23.5). Design.md 13 forbids a bespoke empty illustration. |
| Radio group | `.ux4g-radio` + `.ux4g-radio-header`, `.ux4g-radio-control`, `.ux4g-radio-input`, `.ux4g-radiomark`, `.ux4g-radio-content`, `.ux4g-radio-label`, `.ux4g-radio-description` | `.ux4g-radio-desc-helper`; group-level `.ux4g-radio-error` | `.ux4g-radio-md` | The decision: allow / further inspection / reject (23.9). `md` matches every radio already on the site. |
| Textarea | `.ux4g-textarea-container` + `.ux4g-textarea-default`, `.ux4g-textarea-input`, `.ux4g-textarea-helper` | `.ux4g-textarea-error` / `-warning` / `-success` on the container | `.ux4g-textarea-md` | The officer's remark (23.9). `md` matches the inputs on `profile.html`. |
| Switch | `.ux4g-switch` + `.ux4g-switch-input`, `.ux4g-switch-control`, `.ux4g-switch-track`, `.ux4g-switch-thumb`, `.ux4g-switch-content`, `.ux4g-switch-label`, `.ux4g-switch-description` | `.ux4g-switch-desc-helper` | `.ux4g-switch-md` | The override control that appears only when the officer contradicts the band (23.9). A switch and not a checkbox because the override is a standing state, not a tick in a list. |
| Alert | `.ux4g-alert` + `.ux4g-alert-icon`, `.ux4g-alert-content`, `.ux4g-alert-title`, `.ux4g-alert-message` | `.ux4g-alert-warning`, `.ux4g-alert-error`, `.ux4g-alert-info`, `.ux4g-alert-success` | none ships | A failed verification on the summary (23.8); a result that could not be read at all. **23.10 draws the base and one state variant and nothing else** -- the composition the 2.1.0 README documents (`<div class="ux4g-alert ux4g-alert-info">Message</div>`) -- for the decision form's one live line: `-error` for a refusal, `-success` for the record. No icon and no title, because neither adds a word to a one-sentence line. |
| Button | `.ux4g-btn` | `.ux4g-btn-primary` | `.ux4g-btn-md` | "Record decision" (23.10) -- the one primary action on the page. |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-primary` | `.ux4g-btn-md` | "Printable report" (23.13). |
| Button | `.ux4g-btn` | `.ux4g-btn-text-neutral` | `.ux4g-btn-md` | "Previous screenings", leaving the page. |

### What UX4G cannot meet

The G series continues from Part 22. G8 and G9 are new; neither was visible
until the markup was planned, which is what this note is for.

- **G8 - The skeleton only styles itself inside a form-submission layout.**
  All seven `.ux4g-skeleton-*` rules in the installed stylesheet are scoped
  `.ux4g-application-submission .ux4g-skeleton-*`: of the 44 occurrences of
  that scope class, 43 are descendant selectors and the 44th is its own only
  rule, `.ux4g-application-submission.ux4g-relative { min-height: 52.75rem }`.
  Nothing in the class styles a page that is not a form submission. A shape
  outside that scope has no height, no width and no grey, so `result-skeleton.js`
  switching it switches nothing an officer can see. Two ways out, and the first
  is rejected: wrapping the result page in `.ux4g-application-submission`
  would be a false claim in the markup (this page files a decision, it does not
  submit an application) and would drag `min-height: 52.75rem` with it; the
  second is one documented rule in `pages.css` giving the shapes their size and
  `var(--ux4g-bg-neutral-subtle)` outside the scope. **23.1 adds no CSS**: the
  loading container ships `hidden`, so nothing is drawn yet, and the rule is
  owed to the task that binds the skeleton. Until then the four shapes in the
  table above are correct markup that cannot render, which is recorded here
  rather than left to be discovered.
- **G9 - Nothing draws a flagged region.** `.ux4g-img-overlay-top` and
  `-bottom` are text bars over a scrim (`background: var(--ux4g-bg-overlay)`),
  not per-region markers, and there is no polygon, box or highlight component in
  the sheet. 23.2 and 23.3 therefore position their own overlay inside
  `.ux4g-img-overlay`, which is what supplies `position: relative` and
  `overflow: hidden`. The rule that colours and outlines a selected region is
  custom CSS and must be documented in this file when it is written; it is not
  written here.
- **G9, as 23.2 answered it.** The overlay positions one element per region
  inside `.ux4g-img-overlay` and writes `position`, `left`, `top`, `width`,
  `height` and `clip-path` inline. Each carries `.result-region` and
  `data-result-region` naming its flag, which is the one class and attribute
  the sheet has no answer for (D185) and the seam 23.3 reads. A plain box
  region writes no `clip-path`, because its corners are already its own
  bounding box; a polygon writes `polygon()` percentages inside that box, so
  one element carries position and shape together. **23.2 still adds no CSS**:
  nothing colours, outlines, hovers or focuses a region yet, and no page
  loads the module, so the same debt G8 records for the skeleton is owed here
  to the task that binds the overlay -- 23.3 for behaviour, and a documented
  `pages.css` rule for the paint.
- **Part 22's G3 wording was wrong about the utility spellings.** It names
  `ux4g-gap-row-*` and `ux4g-padding-*` as the utilities the shell uses. Neither
  is a class in 2.1.0: `grep` over the sheet returns 0 of each, because those
  are *token* names (`--ux4g-gap-row-xs`, `--ux4g-padding-m`) and the utilities
  built from them are spelled `ux4g-gap-*`, `ux4g-gap-y-*`, `ux4g-p-*` and
  `ux4g-m-*`. 23.1 uses `ux4g-gap-y-l`, which the sheet ships. The G3 claim
  about density still holds -- no component invents a size -- but the spelling
  does not.

### The nav key, settled for 23.1

Part 22 recorded this as an open item for `screening.html` and it applies here
unchanged: `shell-tokens.js` carries exactly six nav keys and D168 refuses an
`activeNavKey` outside them, so a page with no section of its own has two
choices and cannot have a third. **23.1 marks `activeNavKey: "screenings"`.**
A result page is a detail view of one screening, `result.html?id=<id>` is
reached from a screening, and "Previous screenings" is the only nav section a
result belongs under. The cost, stated rather than hidden: the shell puts
`aria-current="page"` on a link to a *different* page, so the sidebar claims
the officer is somewhere they are not. Growing a seventh key is a Part 21
change, not a page's, and is not made here.

### Confirmation owed before 23.2

This note settles the component list and the nav key. 23.2 writes the overlay
markup. The theme answer above was read from D3 and `tasks.md` rather than
re-asked, because `tasks.md`'s hard constraints forbid re-asking it; if the
maintainer wants a branded theme instead, the only thing that changes is a
`:root` override block, added once at the application root.

- **G9 and G2, as 23.3 answered them.** 23.2 made a region the right shape on
  screen and 23.3 makes it a control: every region naming a flag carries
  `role="button"`, `tabindex="0"` and `aria-pressed`, written by the same draw
  that writes `data-result-region`, and Enter or Space chooses the flag exactly
  as a click does. None of it comes from the sheet, because the sheet ships
  no control laid over an image, and the one class it adds is
  `.result-region-selected`, the project vocabulary beside the one 23.2 wrote.
  **23.3 adds no CSS**, so a selected region is announced to a screen reader
  and painted to nobody:
  the `pages.css` rule that G9 says must be documented here when it is written
  is still owed to the task that binds the overlay to the page, and the same
  debt G8 records for the skeleton is now owed twice. A region naming no flag
  gets none of the ARIA, because a control that cannot say which flag it points
  at is a control that lies.

- **The tag row, as 23.4 answered it.** `result-band.js` draws one line: a
  `<span>` carrying `.ux4g-tag` + `.ux4g-tag-s` + the band's variant
  (`.ux4g-tag-filled-success` / `-warning` / `-error`) with the band's label as
  its text, and beside it a `<span>` holding `.ux4g-sr-only` "Score: " and
  `format.js`'s `formatScore` output. The row itself is a `<div>` with
  `.ux4g-d-flex` + `.ux4g-gap-s`, so "the score next to it" is a layout
  utility and not custom CSS. The two classes of the project's own,
  `.result-band` and `.result-band-score`, are hooks for the documented
  `pages.css` rule G9 already owes -- the sheet ships no class for a badge row
  or for a number beside one -- and **23.4 adds no CSS and loads no script**, so
  the module is out of `staticFiles` and named by no page, with
  `result-band.test.cjs` holding both directions of D173. `.ux4g-sr-only` is the
  sheet's own answer for the word a bare number lacks; no ARIA was written by
  hand, so G2 has nothing owed here. The band is never recomputed from the
  score: `app/risk/bands.py`'s thresholds own that, and the module only paints
  the band it is handed.

- **The flag list, as 23.5 answered it.** `result-flags.js` draws, per tier, an
  `<h3>` carrying `.ux4g-divider-horizontal` + `.ux4g-divider-horizontal-text`
  with the tier name in a `.ux4g-divider-label` span, and a `<ul>` of
  `.ux4g-list` + `.ux4g-list-default` + `.ux4g-list-m` -- the same three
  classes `about.html` already uses. Each row is a
  `<li class="ux4g-list-item result-flag-row">` holding a
  `.ux4g-list-item-row` **+ `.ux4g-list-item-row-fixed`** row: the row class on
  its own is the sheet's clickable row (`cursor:pointer` and a hover
  background), and no row is a control yet. `.ux4g-list-item-start` carries the
  label, the reason and the expected/found pair stacked with `.ux4g-d-flex` +
  `.ux4g-flex-column` + `.ux4g-gap-y-2xs`; `.ux4g-list-item-end` carries the
  weight band and the confidence. Three classes beyond the list row above are
  named because the sheet needs them: `.ux4g-divider-label` (the `-text` divider
  has no other way to sit its text over the line),
  `.ux4g-list-item-row-fixed` and `.ux4g-text-neutral-secondary` for the
  trailing fields. A case greps the installed stylesheet for every class the
  module writes, so a spelling 2.1.0 does not ship reds the suite. The empty
  state is `.ux4g-empty-state` with a `.ux4g-empty-state-content` child and no
  icon, as this note planned, and carries `app/reporting.py`'s own
  `NO_FINDINGS` sentence. **23.5 adds no CSS and loads no script**, so the
  module is out of `staticFiles` and named by no page, with
  `result-flags.test.cjs` holding both directions of D173. The tier name is a
  heading rather than a bare `<div>` because the sheet ships the `-text` variant
  and no example of its use, so the one thing this note cannot settle -- how the
  heading sits at the height the sheet gives the divider -- stays a browser
  question until a page renders it.
---

## Part 24 - `frontend/screenings.html`

### Delivery method and theme

- **Delivery:** npm `ux4g-web-components@2.1.0`, already installed and already
  wired by `frontend/shell.html`. No CDN path is mixed in.
- **Theme:** the **default UX4G light theme**, no root token override block.
  The answer is D3's and `tasks.md`'s hard constraints forbid re-asking it
  ("Do not ask again, do not add custom theme tokens"), so the skill's step 3
  is answered from the repository rather than re-put to the maintainer.
  **24.1 adds no markup beyond deleting sample rows**, so this is recorded
  rather than exercised.
- **No `!important` on buttons**, per the v2.0.1 `:where()` note; no page in
  Part 24 overrides a button.

### The component list, as 24.1 answers it

The page already existed with its table, chips, search and pagination in
place. 24.1 changes one thing: **where the rows come from**. The class
composition below is therefore mostly unchanged, and 24.2 is the task that
holds it still.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Table | `.ux4g-table` + `.ux4g-table-m`, `.ux4g-table-zebra-rows`, `.ux4g-table-interactive` | none | `ux4g-table-m` | The history table. **Unchanged by 24.1**; 24.2 holds the composition with a test. |
| Cell text | `.ux4g-table-cell-text` | none | n/a | The screening id cell, so the id and its status read as one value. |
| Tag | `.ux4g-tag` | `.ux4g-tag-filled-success` / `-warning` / `-error`, and `-neutral` for a row nothing has scored | `.ux4g-tag-s` | The Result cell, one tag per row. `screenings-list.js` writes these; they are no longer in the markup. |
| Search | `.ux4g-search-container` + `.ux4g-search-input` | none | `.ux4g-search-m` | The toolbar's id/document search. |
| Filter chip | **none ships** -- the sheet has no `.ux4g-filter-chip` base rule | `.ux4g-filter-chip-md` on each chip, `.ux4g-filter-chip-group` on the container, `.active` on the pressed one | `md` | All / Low Risk / Review / High Risk, one per band `app/risk/bands.py` bands in. **24.4 rewrote the vocabulary**; 24.1 left the sample chips in place and mapped a row onto them. |
| Button | `.ux4g-btn` | `.ux4g-btn-primary` | `.ux4g-btn-md` | "New screening" -- the one primary action on the page. |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-primary` | `.ux4g-btn-md` | "Export", "Clear filters", "Run a new screening". |
| Button | `.ux4g-btn` | `.ux4g-btn-text-primary` | `.ux4g-btn-sm` | The "Checked" sort control in the header, and the per-row View/Delete. |
| Empty state | `.ux4g-empty-state` + `.ux4g-empty-state-content`, `.ux4g-empty-state-icon` | none | none | Shown when the answer carries no rows. Design.md 13 forbids a bespoke illustration. |
| Pagination | `.ux4g-pagination` + `.ux4g-pagination-prev`, `-next` | `.ux4g-pagination-compact` | compact | **24.3 makes this server-driven**; 24.1 leaves the markup as found. |
| Card | `.ux4g-card` + `.ux4g-card-body` | none named | none ships | The stat tiles and the table panel. |

### The one real decision in 24.1 -- `screenings-list.js` owns the rows

Six sample `<tr>`s and a "Sample data." alert are deleted from the markup and
replaced by `frontend/screenings-list.js`, which reads
`GET /api/screenings` through `api.js` and draws the tbody.

- **The markup is a container, not a record.** `<tbody id="screenings-body">`
  ships empty, and `screenings-list.test.cjs` holds both directions of that:
  zero `<tr data-result=` in the page, and one script tag naming the module.
- **The module refuses a payload it cannot read, by name.** A row missing a
  `screening_id`, a status outside `SCREENING_STATUSES`, an unparseable
  `created_at`, a score outside 0-100 or a band outside the three
  `app/risk/bands.py` bands in, is refused (`bad_item`, `bad_timestamp`,
  `bad_score`, `bad_band`) **before** anything is drawn, so a bad row leaves
  the table as it stood rather than half replaced.
- **Two columns are named absent rather than filled.** The list route returns
  six fields (`screening_id`, `status`, `document_type`, `created_at`,
  `score`, `band`) and **no `mode`**, so the Mode column reads
  `Not recorded` on every row. This is the 23.10 rule and not 23.11's: an
  absent field is the honest answer a stored row carries. The id cell's
  `<small>` carries `status` instead of the sample rows' invented "Photo" /
  "Scan" claim.
- **An unscored row gets a neutral tag, not a verdict.** `band` is `None`
  until the gate has run, so those rows draw `.ux4g-tag-filled-neutral`
  reading `Not scored`. 23.10's rule again: a page that passed nothing is not
  a Low Risk document.
- **`format.js` is loaded for the first time.** The score and the band label
  come from it rather than being spelled twice. This is why `build.cjs`'s
  `staticFiles` gains `format.js` and `screenings-list.js`, and why
  `result-band.test.cjs`'s "format.js must not be copied yet" line became
  false and was corrected rather than worked around.
- **The request is `api.js`'s, not `fetch`.** One base URL, one error
  envelope, one timeout, as D194 left it.

### What UX4G cannot meet

The G series continues. G10 and G11 are new.

- **G10 - the list route cannot answer the three stat tiles.** Only `total`
  comes back from `GET /api/screenings`; there is no passed count, no
  attention count and no average, and computing them from one page of at most
  200 rows would be a number about the page, not about the history. **24.1
  binds `data-stat="total"` to the answer and deletes the other three tiles**
  rather than leave `96` / `75%` / `78` on a page now reading a live route.
  Restoring them is a backend summary, not a page fix.
- **G11 - there is no loading or error state, and 24.1 does not invent one.**
  The sheet ships no loading variant for the table and no error state for a
  failed read. `load()` therefore **stores** a failure on `error()` rather
  than throwing an unhandled rejection, and the table is simply empty until
  something is drawn. **24.7 owns the loading, error and empty treatment**
  with `ux4g-skeleton-*` and `ux4g-alert-*`; the debt is recorded here so it
  is not rediscovered.
- **`.ux4g-tag-filled-neutral` is used for one case the sheet does not
  document.** The three band tags are read out of `result-band.js`, which
  took them from the sheet; the neutral variant exists in 2.1.0 (one
  occurrence) and is what an unscored row needs, since no band tag is honest
  for it. A case greps the installed sheet for every class the module writes.
- **The chip vocabulary, as 24.4 answered it.** `data-filter` now carries the
  engin's own values -- `all`, `low`, `review`, `high` -- and
  `screenings-list.js` writes that same value onto each row's `data-result`, so
  the chip a row answers to is the band it was banded in. `not-scored` is the
  value a row nothing scored is filed under, and **no chip carries it**:
  the engine has no band for an unscored document, so a filter over that
  set would be a vocabulary of this page's own. The chip labels are
  `format.js's, and `screenings-list.test.cjs` holds each chip's text against
  the `bandLabel()` of its own `data-filter`.

### Amendment for 24.5 -- the row actions, and the confirmation they go through

The 24.1 component list gave the seventh column "the per-row View/Delete" as
one row of buttons. 24.5 splits that row in two, because the two actions are
not the same kind of thing, and it adds one component the page did not have.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Link as button | `a.ux4g-btn` | `.ux4g-btn-text-primary` | `.ux4g-btn-sm` | The per-row **View**. An anchor, not a button: it navigates to `result.html?id=` and needs nothing from JavaScript. The page already used `a.ux4g-btn ux4g-btn-primary ux4g-btn-md` for "New screening", so the shape is the one this page already ships. |
| Button | `.ux4g-btn` | `.ux4g-btn-text-primary` | `.ux4g-btn-sm` | The per-row **Delete**. A button, because it changes something a server holds and goes through a confirmation first. |
| Modal | `.ux4g-modal-backdrop` | backdrop: `.ux4g-modal-backdrop-50`, `.ux4g-modal-backdrop-blur`; box `.ux4g-modal-box` | `.ux4g-modal-s` | The delete confirmation, in the ``overlays`` slot. Shown by adding `is-open`, which is how `home.html` shows its two. |
| Modal header | `.ux4g-modal-header` + `.ux4g-modal-header-title` | none | none | The question the confirmation asks, wired to the dialog by `aria-labelledby`. |
| Modal body | `.ux4g-modal-body` | none | none | The sentence that names the row, with `aria-describedby` pointing at it. |
| Modal action bar | `.ux4g-modal-actions` | none | none | **Not `.ux4g-modal-footer`.** The package README documents that name and `styles/ux4g.css` does not carry it; the sheet ships `.ux4g-modal-actions` and nothing else. This is the README-versus-runtime trap Design.md warns about, and a case fails if the documented name is used. |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-neutral` (Cancel), `.ux4g-btn-danger` (Delete) | `.ux4g-btn-md` | The two controls in the action bar. Danger is the destructive one and there is exactly one of it. |

Three further notes the amendment owes:

- **No focus trap, no `Escape`, no focus restore.** The dialog follows the
  two `home.html` already ships, which have neither. 25.5 is the task that
  brings all three to the remaining dialogs.
- **The outcome is a `role="status"` paragraph, not an `ux4g-alert-*`.**
  A refusal the service wrote is shown in its own words. 24.7 owns the error
  treatment and the alert component.
- **A redraw fires `drishti:screenings-changed` on `document`.**
  `pages.js` owns the band filter and hides rows by setting `hidden`;
  the module owns the rows and replaces them. Neither can reach into the other,
  so the redraw is announced and the filter is re-applied. Nothing in UX4G
  provides this: it is two project modules agreeing on one event name, held by
  a case in each file.
### Amendment for 24.7 -- the loading, error and empty states

The 24.1 list said "Empty state: shown when the answer carries no rows" and
G11 recorded that no loading or error state existed. 24.7 adds two regions to
the page and one switch to the module. The theme answer above is unchanged:
the **default UX4G light theme**, no root token override block, and no button
in this amendment carries one.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Skeleton | `ux4g-skeleton-block` (x5), on `ux4g-card-body` | **none ships** -- the sheet has no loading variant and no size modifier | none | `#screenings-loading`, one shape per row the table is about to hold. `aria-busy` on the container, `aria-hidden="true"` on every shape (G2). |
| Alert | `ux4g-alert` + `ux4g-alert-content` + `ux4g-alert-title` + `ux4g-alert-message` + `ux4g-alert-actions` | `.ux4g-alert-error` | none | `#screenings-error`, `role="alert"`: a read that failed. The module writes `error.message` into the message paragraph, so the alert says what the service said. |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-primary` | `.ux4g-btn-md` | `#screenings-retry`, inside the alert's own action bar: the alert's way back to a read. |
| Empty state | `.ux4g-empty-state` | none | none | `#screenings-empty`, unchanged since 24.1. It is now switched with the two states above rather than only with the row count. |

Notes the amendment owes:

- **The three states are exclusive, and one switch says so.**
  `screenings-list.js`'s `showState()` writes the table, the skeleton, the
  alert and the empty panel together, so the page cannot show a skeleton and
  an empty state at once; `bad_state` refuses a state the page does not have.
  24.1 hid the scroll and the empty panel separately and had nowhere to put a
  failed read, which read as an empty history rather than a failed one.
- **`aria-busy` and `hidden` are written by the same call,** so what a screen
  reader is told and what an officer can see cannot disagree (G2: the
  skeleton ships no ARIA). The count line, which is already a
  `role="status"`, carries `LOADING_MESSAGE` while the read is in flight and
  is cleared when it fails -- the sample "Showing 6 of 6 screenings" cannot
  survive as a lie.
- **`role="alert"` on the alert, not `role="note"`.** The page's four static
  notes use `role="note"`; this one arrives after a read, and 23.10's rule is
  that a late fact is announced.
- **What UX4G cannot meet.** **G8 is now owed twice:** all seven
  `ux4g-skeleton-*` rules are scoped `.ux4g-application-submission`, which this
  page does not carry, so the five blocks draw nothing until that rule lands
  -- the same debt `result.html` carries. **G12:** the empty panel keeps the
  project's own `.empty-panel__icon` SVG and its own heading rather than the
  sheet's `.ux4g-empty-state-content` and `.ux4g-empty-state-icon`, which is
  the composition 23.5's `result-flags.js` draws and which Design.md 13's ban
  on a bespoke illustration points at. 24.7 leaves the 24.1 markup alone
  rather than re-cutting a panel nobody has seen rendered.
- **Unverified in a browser.** Skeleton block heights, the alert's action bar
  inside `.ux4g-card-body`, dark-theme contrast and the retry button's focus
  ring are all open questions; the states are proved against the stub DOM.
---

## Part 24 - `frontend/audit.html`

### Delivery method and theme

- **Delivery:** npm `ux4g-web-components@2.1.0`, already installed and already
  wired by `frontend/shell.html`. No CDN path is mixed in.
- **Theme:** the **default UX4G light theme**, no root token override block.
  The answer is D3's and `tasks.md`'s hard constraints forbid re-asking it
  ("Do not ask again, do not add custom theme tokens"), so the skill's step 3 is
  answered from the repository rather than re-put to the maintainer, exactly as
  Parts 22, 23 and the first half of 24 did.
- **No `!important` on buttons**, per the v2.0.1 `:where()` note. 24.8 adds no
  CSS of its own, so no button in this section carries one.

### The nav key, settled for 24.8

`shell-tokens.js` carries exactly six nav keys and D168 refuses an
`activeNavKey` outside them, so a page with no section of its own has two
choices and cannot have a third. **24.8 marks `activeNavKey: "screenings"`,** on
D184's reasoning: an audit trail is a detail view of one screening's record,
and "Previous screenings" is the only nav section it belongs under. The cost
is stated rather than hidden, and it is the cost D184 already recorded for
`result.html` -- the shell puts `aria-current="page"` on a link to a different
page. Growing a seventh key is a Part 21 change, not a page's.

### Components, variants and sizes

Base class first, then variant, then size. The page is a fragment the build
fills; `overlays` and `pageScripts` are the only slots it uses, and
`pageScripts` carries one script tag.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Table | `.ux4g-table` + `.ux4g-table-m`, `.ux4g-table-responsive` | none | `ux4g-table-m` | The event list, `#audit-events`. **The responsive wrapper, not the history page's `-zebra-rows` / `-interactive`:** an audit trail is read top to bottom and is never clicked, and zebra striping is the history table's affordance rather than an audit one. 24.8 adds no second table. |
| Cell text | `.ux4g-table-cell-text` | none | n/a | The event id cell, written by `audit.js`, so the id reads as one value. |
| Skeleton | `ux4g-skeleton-block` (x3), on `ux4g-card-body` | **none ships** -- the sheet has no loading variant and no size modifier | none | `#audit-loading`, one shape per event the list is about to hold. `aria-busy` on the container, `aria-hidden="true"` on every shape (G2). |
| Alert | `.ux4g-alert` + `.ux4g-alert-content` + `.ux4g-alert-title` + `.ux4g-alert-message` + `.ux4g-alert-actions` | `.ux4g-alert-error` | none ships | `#audit-error`, `role="alert"`: a read that failed. `audit.js` writes the failure's own message into the message paragraph. The composition is 24.7's, unchanged. |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-primary` | `.ux4g-btn-md` | `#audit-retry`, inside the alert's own action bar, and the link out of the empty panel. |
| Empty state | `.ux4g-empty-state` + `.ux4g-empty-state-content` | none | none | `#audit-empty`: the page opened with no audit id. **The sheet's own composition and no icon**, so G12 -- which `screenings.html` still carries against this note's own advice -- is not repeated here. |
| Layout utility | `.ux4g-d-flex`, `.ux4g-gap-y-l` | n/a | `gap-y-l` | The page's own stacking of its header, panel and states. No custom CSS. |
| Card | `.ux4g-card` + `.ux4g-card-body` | none named | none ships | The event panel. As on Parts 22-24, no existing page names `-outline` or `-solid`, and this page names neither until it has seen the rendered result. |

### What UX4G cannot meet

G13 is new and it is the reason this note exists.

- **G13 - no route lists a screening's audit events.** The `/api/audit`
  resource holds exactly one read, `GET /api/audit/{audit_id}/verify`
  (`app/api/routes_audit.py`), and it answers about **one** stored event:
  `AuditVerificationResponse` carries `audit_id`, `status`, `batch_id`,
  `batch_root`, `proof_length` and `checked`. It carries no event type, no
  actor, no timestamp and no ruleset or model version, and nothing else in the
  service exposes a trail: `app/audit/trail.py` holds `completed_event_id` and
  `event_by_id` and no list, and no `/api/screenings*` response carries an audit
  id or an event stream. **The roadmap's F18 columns -- type, actor,
  timestamp, ruleset/model version, batch id -- are therefore five columns a
  route this service does not have would carry.** 24.8 refuses to invent them.

  What 24.8 builds instead: **the event list is one row per audit id the page
  was opened with**, and the query string carries those ids. `audit.js` reads
  `id` whole, so `audit.html?id=<uuid>` is one row today and a screening's whole
  trail is one link away the moment a trail route lands, with no change to the
  table. Each row carries the two things the answer holds that 24.9 and 24.10
  do not own: **Event** (the `audit_id`) and **Checks run** (how many of the
  walk's checks completed).

  Two columns is a thin table, and that is the honest reading of the route
  rather than a layout to dress up. 24.9 adds the status tag and the sentences
  the walk completed; 24.10 adds the batch id, the batch root and the proof
  length. Both are columns this note has already reserved.

- **G8 is now owed a third time.** All seven `ux4g-skeleton-*` rules are scoped
  `.ux4g-application-submission`, which this page does not carry, so the three
  blocks draw nothing until the documented `pages.css` rule lands -- the same
  debt `result.html` and `screenings.html` carry.
- **G2, unchanged:** the skeleton and the alert ship no ARIA, so the container's
  `aria-busy` and every shape's `aria-hidden`, and the alert's `role="alert"`,
  are written by the same call that switches them, as 24.7 already does.

### Considered and rejected: the timeline

The sheet ships `.ux4g-timeline`, `.ux4g-timeline-step`, `.ux4g-timeline-head`,
`.ux4g-timeline-head-icon`, `.ux4g-timeline-head-text` and
`.ux4g-timeline-content` (Design.md's "Journey Timeline", available on Web),
and a trail of events is the shape it is drawn for. **24.8 does not use it**,
for one reason read out of the installed stylesheet rather than recalled: the
connector line is the step's `:after` pseudo-element and the head icon rule
(`.ux4g-timeline-head-icon`) sets only `align-items`, `border-radius`,
`display`, `font-size`, `font-weight`, `height`, `justify-content` and
`width` -- **no background and no colour**. A timeline on this page would
therefore need a background utility the timeline itself does not name, and a
timeline's row is a single cell wide, which cannot hold an id and a count
beside each other. The table is both the honest fit for the data this route
carries and the one that needs no class the sheet does not ship. Nothing is
owed here; a trail with one field per step would reopen it.

### Amendment for 24.9 -- the result tag, and the sentences the walk completed

G13 above reserved two columns for this task: "24.9 adds the status tag and the
sentences the walk completed." The theme answer above is unchanged -- the
**default UX4G light theme**, no root token override block -- and 24.9 adds no
CSS and no `!important`.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Tag | `.ux4g-tag` | `.ux4g-tag-filled-success` (verified), `.ux4g-tag-filled-error` (altered), `.ux4g-tag-filled-neutral` (unknown) | `.ux4g-tag-s` (the only size in the sheet) | The **Result** cell of every audit row, written by `audit.js`. All three variants are the same three `screenings-list.js` and `result-band.js` already use, plus `-neutral`, which G11's note already recorded as shipped in 2.1.0. |
| List | **none -- a bare `<ul>`/`<li>`** | n/a | n/a | The **What was checked** cell: one `<li>` per completed check. See the gap below. |

Four further notes the amendment owes:

- **`altered` is the only answer that takes the error tag.** It is the only one
  of the three that is a refusal; `verified` is a clearance and `unknown` is a
  question the walk could not answer, so it gets the neutral tag rather than a
  band of its own. This is 24.1's "an unscored row gets a neutral tag, not a
  verdict" rule applied to the audit's own three words.
- **The tag's colour is never the only carrier.** The tag reads the word --
  `Verified` / `Altered` / `Unknown` -- from `STATUS_LABELS`, and each row also
  carries `data-verification` with the status the walk answered. A reader in
  print, a screen reader, and an officer with a colour-blind eye all get the
  answer from the word. D200's "the export reads the visible rows" reasoning
  does not apply here; this is D3's contrast rule in the form the audit view
  needs it.
- **No custom CSS is added, and none is needed.** The tag composition is
  23.4's and 24.1's, verbatim and in the same order -- base, variant, size.
- **`NO_CHECKS_LABEL` is the module's own sentence**, "No check completed.",
  held in `audit.js` beside the tag tables rather than in the markup, because
  `audit.js` writes the tbody. It is 23.10's rule: an absent check is said,
  not counted, and a cell that stands empty reads as a fault rather than as an
  answer.

### What UX4G cannot meet, for 24.9

- **G14 - the sheet has no list inside a table cell.** `.ux4g-list` and its
  variants are card-body compositions: they carry their own padding, border and
  divider, which inside a `<td>` would draw a box inside the table's own box.
  **24.9 therefore draws a bare `<ul>`/`<li>` and gives it no class at all.**
  The browser's own list styling is the correct one here, and no
  `ux4g-list-*` class is claimed, so nothing has to be overridden to undo it.
  A future task that wants these sentences styled differently reopens this.

### Unverified in a browser

The three states, the three-column table at 320px, the tag in each of its three
variants against the result page's own tags, dark-theme contrast and the
empty-panel link are all open questions. Nothing of Part 24 has been seen in a
browser; this page is proved against the stub DOM.

## Part 24 - `frontend/cases.html`

### Delivery method and theme

- **Delivery:** npm `ux4g-web-components@2.1.0`, already installed and already
  wired by `frontend/shell.html`. No CDN path is mixed in.
- **Theme:** the **default UX4G light theme**, no root token override block.
  The answer is D3's and `tasks.md`'s hard constraints forbid re-asking it
  ("Do not ask again, do not add custom theme tokens"), so the skill's step 3 is
  answered from the repository rather than re-put to the maintainer, exactly as
  Parts 22, 23 and the two earlier halves of 24 did.
- **No `!important`, and no CSS at all.** 24.11 adds no stylesheet block and no
  rule to `pages.css`; the only tokens it touches are the ones the sheet
  already defines. See "No custom CSS" below.

### The nav key, settled for 24.11

**`activeNavKey: "screenings"`,** on 24.8's reasoning and D184's: a case is a
detail view of stored screenings, and "Previous screenings" is the only nav
section it belongs under. The cost is the same one D184 recorded -- the shell
puts `aria-current="page"` on a link to a different page. Growing a seventh key
is a Part 21 change, not a page's.

### Components, variants and sizes

Base class first, then variant, then size. The page is a fragment the build
fills; `overlays` and `pageScripts` are the only slots it uses, and
`pageScripts` carries one script tag.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Card | `.ux4g-card` + `.ux4g-card-body` | none named | none ships | The panel (`table-panel ux4g-card`, as `audit.html` has it) and **one card per document**, written by `cases.js`. No existing page names `-outline` or `-solid`, and this page names neither until it has seen the rendered result. |
| Grid | `.ux4g-grid` + `.ux4g-grid-cols-1` + `.ux4g-md-grid-cols-2` + `.ux4g-xl-grid-cols-3` + `.ux4g-gap-m` | none -- the base ships no variant | the two responsive column counts are the "size" | `#case-documents`, the row of documents side by side. Breakpoints read out of the installed sheet, not recalled: `md` at **768px**, `xl` at **1200px**. |
| Tag | `.ux4g-tag` + `.ux4g-tag-s` | `.ux4g-tag-filled-success` (low), `.ux4g-tag-filled-warning` (review), `.ux4g-tag-filled-error` (high), `.ux4g-tag-filled-neutral` (unscored) | `.ux4g-tag-s` -- the only size in the sheet | The band on each card. **The same four variants `screenings-list.js`, `result-band.js` and `audit.js` already use**, in the same base-variant-size order; `cases.test.cjs` pins all four against `result-band.js` so a rename upstream reds this file. |
| Skeleton | `ux4g-skeleton-block` (x3), on `ux4g-card-body` | **none ships** | none | `#case-loading`, one shape per document about to be drawn. `aria-busy` on the container, `aria-hidden="true"` on every shape (G2). |
| Alert | `.ux4g-alert` + `-content` + `-title` + `-message` + `-actions` | `.ux4g-alert-error` | none ships | `#case-error`, `role="alert"`. `cases.js` writes the failure's own message into the message paragraph. 24.7's composition, unchanged. |
| Button | `.ux4g-btn` | `.ux4g-btn-outline-primary` | `.ux4g-btn-md` | `#case-retry`, inside the alert's own action bar, and the link out of the empty panel. |
| Empty state | `.ux4g-empty-state` + `.ux4g-empty-state-content` | none | none | `#case-empty`: the page opened with no document named. **The sheet's own composition and no icon**, so G12 -- which `screenings.html` still carries against this note's own advice -- is not repeated. |
| Flex row | `.ux4g-d-flex` + `.ux4g-gap-s` | n/a | `gap-s` | The band and its score on one line, as `result-band.js` draws it. |
| Grid, stacked | `.ux4g-grid` + `.ux4g-gap-y-s` | n/a | `gap-y-s` | The four blocks inside one card: type, id, band, cross-document flags. |
| Screen-reader only | `.ux4g-sr-only` | n/a | n/a | The words `Score: ` and `Screening id: `, so a bare number and a bare UUID are not read as fragments. |
| Layout utility | `.ux4g-gap-y-l` | n/a | `gap-y-l` | Nothing on this page beyond what the table above lists; the panel reuses `pages.css`'s own `.page-header` and `.table-toolbar` as every other page does. |

### No custom CSS, and why that is a finding rather than an omission

Design.md 13 forbids a bespoke atom where a UX4G component exists, and
`tasks.md` forbids unnecessary custom CSS. **The side-by-side layout is
therefore UX4G's own grid, not a `.case-grid` written in `pages.css`:**
`ux4g-grid` sets `display: grid`, and the two responsive column counts carry
the documents from one column to two at 768px and three at 1200px. The one
thing the sheet does not provide is a gap between grid children -- `.ux4g-grid`
sets only `display` -- so `ux4g-gap-m` is named on the grid itself, which is
what that class is for. 24.11 adds no `<style>` block and no rule, and
`cases.test.cjs` asserts both (`!pageHtml.includes("<style")`, and no
`class="case-` anywhere on the page).

### What UX4G cannot meet

- **G15 is new, and it is why this note exists: no route groups a traveler's
  documents into a case.** There is no case entity, no traveller entity, and no
  relation between two screenings anywhere in the service. `GET /api/screenings`
  pages the rows by band, document type and date; `GET /api/screenings/{id}`
  answers about **one** row and carries `screening_id`, `status`,
  `document_type`, `created_at`, `image`, `score`, `band`, `ruleset_version`,
  `model_versions`, `summary`, `flags`, `stage_trace` and `contributions`.
  Nothing anywhere groups two of them, and nothing names a traveler. **A
  "traveler's documents side by side" is therefore a grouping this service
  cannot produce, and 24.11 refuses to invent a traveler.**

  What 24.11 builds instead, on 24.8's pattern: **a case is the set of
  screening ids the page was opened with.** `cases.js` reads `id` whole, so
  `cases.html?id=<uuid>&id=<uuid>` is two documents side by side today, and a
  real case route is one link away the moment a case entity lands, with no
  change to the card. Every card is read from a route that exists.

- **The cross-document flags are per screening, not per case, and that is the
  second half of G15.** `app/risk/flag_ids.py` names four cross-document rules
  (`CROSSDOC_NAME_MISMATCH`, `CROSSDOC_UNKNOWN_PASSPORT_REFERENCE`,
  `CROSSDOC_VALIDITY_WINDOW_MISMATCH`, `CROSSDOC_FACE_MISMATCH`), and
  `app/risk/flags.py` spells the tier `"crossdoc"`. **But no route reports a
  cross-document finding across two screenings**: `flags` is a column on the
  screening row, so a `crossdoc` flag reaches this page only if some tier wrote
  it onto that one row. 24.11 draws the `crossdoc` flags the answer carries and
  draws nothing else -- a flag of any other tier is scoped to one document,
  belongs on `result.html`, and a test asserts it never reaches a card. **If
  the cross-document engine is not writing these onto screening rows today,
  this view's second column is empty, and that is the service's answer rather
  than a fault in the page.** 24.11 does not claim the rules ran.

- **G14 is owed a second time.** `.ux4g-list` and its variants are card-body
  compositions carrying their own padding, border and divider. **The
  cross-document list is therefore a bare `<ul>`/`<li>` with no class**, as
  24.9's explanation cell already is.

- **G8 is now owed a fourth time.** All seven `ux4g-skeleton-*` rules are scoped
  `.ux4g-application-submission`, which this page does not carry, so the three
  blocks draw nothing until that documented `pages.css` rule lands -- the same
  debt `result.html`, `screenings.html` and `audit.html` carry.

- **G2, unchanged:** the skeleton and the alert ship no ARIA, so the container's
  `aria-busy`, every shape's `aria-hidden` and the alert's `role="alert"` are
  written by the same call that switches them, as 24.7 already does.

### Considered and rejected: a table of documents

A table was the obvious first shape -- `audit.html` and `screenings.html` are
both tables -- and it is the wrong one here. **Documents side by side is a
comparison read across, and a table read across is a table whose cells are
compared by eye down a column of a phone.** At 320px a three-column comparison
becomes one column of the same, which is the history page with the row
stripped. The grid also answers the second requirement better: a card holds a
band, a score and a *list* of flags, where the audit table needed G14's bare
`<ul>` inside a `<td>` and this page gets the same bare list with no box drawn
around it. 24.11 takes the grid; a future task that wants a sortable,
comparable column of bands reopens it and owes `ux4g-table-responsive`.

### Considered and rejected: linking a card to `result.html`

Each card shows the screening id, and `result.html?id=` is one link away. **24.11
does not draw that link**, for one reason: `result.html` reads nothing from its
query string today (the handover's G10), so the link would land on a skeleton
nothing fills. A link that goes nowhere is worse than an id an officer can read
aloud. The moment `result.html` is wired, this is a one-line change and belongs
to the task that wires it.

### What is deliberately not here

**The one-document case.** A traveler whose set holds a single document is
24.12's task, and 24.11 does not pre-empt it: `#case-empty` says only that no
document was *named*, which is a different answer from a case that named one
document and has nothing to compare it against. The two are kept apart on
purpose, because collapsing them would make the second unreadable.

### Unverified in a browser

Nothing of Part 24 has been seen in a browser. The grid at 320, 768 and 1200px,
the four tag variants beside the result page's own tags, dark-theme contrast,
the bare list's spacing inside a card, and the heading order (`h1` page, `h2`
panel, `h3` per document, `h4` per card's flags) are all open questions. This
page is proved against the stub DOM.
---

## Part 27 - `frontend/results.html`

### Delivery method and theme

- **Delivery:** npm `ux4g-web-components@2.1.0`, already installed and already
  wired by `frontend/shell.html` (`styles/ux4g.css` +
  `dist/runtime/design-system.js`). CDN delivery is not mixed in.
- **Theme:** the **default UX4G light theme**, no root token override block.
  D3 settles this and forbids re-asking it -- "The user has already chosen the
  default theme. It is not to be re-asked unless a branded theme is explicitly
  requested" -- and states that "when a new page is added, the theme question is
  already answered by this decision." A new page does not reopen it. Dark and
  system remain available at runtime through `preferences.js`, as on every
  other page.
- **Buttons carry no `!important`.** No button ships on this page; the rule is
  recorded so a later edit adding one does not reach for it.

### Components, variants and sizes

Base class first, then variant, then size, on every line.

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Table | `.ux4g-table` | `.ux4g-table-responsive` | `.ux4g-table-m` | The metric rows (27.12). The composition is `audit.html`'s, read out of that page rather than recalled. |
| Tag | `.ux4g-tag` | `.ux4g-tag-filled-success` / `-warning` / `-neutral` / `-info` | `.ux4g-tag-s` | One per row: the source, which is `measured`, `stub`, `designed` or `not measured`. |
| Card | `.ux4g-card` + `.ux4g-card-body` | none, as `audit.html` | none ships | The one bounded surface the table sits in. |
| Empty state | `.ux4g-empty-state`, `.ux4g-empty-state-content` | none | none | A metrics file holding no metric at all. Design.md 13 forbids a bespoke illustration, and none is drawn. |

Grep out of the installed `ux4g.css` confirms each name and no others:
`ux4g-tag-filled-{error,info,neutral,primary,success,warning}` and `ux4g-tag-s`;
`ux4g-empty-state{,-content,-icon}`; `ux4g-card{,-body,...}`; and
`ux4g-table{,-m,-responsive}`.

**No loading state and no error state.** `results-metrics.js` is a `<script>`
the page loads, not a route it reads, so there is no request in flight to
describe and no failure the service can word. The empty state is the whole of
the no-data answer, which is a different thing from `audit.html`'s three.

### The value and the dataset are one row, and a row is not drawn without both

Gate 27 asks that every number displayed anywhere has a dataset behind it.
`results.js` refuses to draw the value of a metric whose dataset reference is
absent, and says so in the row rather than dropping the row: a number with no
dataset is the one thing the page exists to refuse, and hiding it would leave
the reader unable to tell a refusal from a page that did not load.

**A design target is not a measurement and is not given a dataset.** The
abstract's latency windows are shown in the same table, tagged `designed` and
carrying the abstract as their reference rather than a corpus. That is Gate 27's
own second clause, and it is why the table has a source column at all.

### Where the numbers come from, and why the page reads a file rather than a route

The metrics are read by four harnesses under `backend/tests/fixtures/`, and D221
records that `app` imports no test module anywhere in this repository -- the one
edge this codebase has never had. A route that answered these numbers would
mean `app` importing `tests.fixtures`, which D221's revisit condition names as
the moment to decide, not the moment to do it quietly.

So the harnesses are read **at build-authoring time**, not at request time:
`tests/fixtures/results_view.py` assembles the rows and renders
`frontend/results-metrics.js`, which is committed and loaded by the page.
`tests/unit/test_results_view.py` holds the committed file against a fresh
render, so the page cannot drift from the harnesses that wrote it.

**Measured durations are deliberately not in the file.** Tier 0's median and
p95 are read on the machine that ran the benchmark, so committing them would
make the artifact machine-specific and force a rewrite of the committed file on
every regeneration -- and the freshness test would have to exempt them, which is
where a stale number would hide. The latency rows therefore carry the
abstract's designed targets only, tagged `designed`, and Tier 0's measurement
stays where it was measured: in `latency_benchmark.py`'s own table.

### Considered and rejected: reading the harnesses through the API

A `GET /api/results` route is the obvious shape and the wrong one here. It
would put the test fixtures inside the shipped application's import graph for
the sake of four numbers that do not change between requests, and it would make
the numbers depend on a service being up -- a results page that fails to load
is exactly the page that must not be able to hide a measurement.

### Considered and rejected: hand-writing the rows into `results.js`

Copying the harnesses' printed tables into the page would be a second copy of
every number, free to drift from the first, and nothing would notice. The page
reads a generated file so there is exactly one owner of each number, which is
the same rule that put `flags.py` beside `cases.test.cjs` rather than a list of
tier names inside it.

### What is deliberately not here

**The corpus behind each metric is a row, not a link.** No metric links to the
fixture that produced it: the dataset is named in words in the row beside the
number, and a link out of a static page to a Python module would be a link to
nothing a reader can open.

### Unverified in a browser

Nothing of Part 27 has been seen in a browser. The four columns at 320, 768 and
1200px under `.ux4g-table-responsive`, the four tag variants beside the audit
page's own tags, dark-theme contrast of the dataset column, and the heading
order (`h1` page, `h2` panel) are all open questions. This page is proved
against the stub DOM, as the others are.

---

## Part 29 — `frontend/home.html` tier results in the existing modal

### Delivery method and theme

- **Delivery:** the existing local npm `ux4g-web-components@2.1.0` package.
- **Theme:** the settled default light theme from D3; no token overrides.

### Components, variants and sizes

| Component | Classes | Variant | Size | Where |
|---|---|---|---|---|
| Modal | `.ux4g-modal-backdrop`, `.ux4g-modal-box` | backdrop `-50` and `-blur` | `ux4g-modal-l` | Existing result modal; unchanged. |
| Alert | `.ux4g-alert` + `.ux4g-alert-content`, `.ux4g-alert-title`, `.ux4g-alert-message` | `.ux4g-alert-warning` | none ships | Notice above the Tier 2 prototype results. |
| List | `.ux4g-list` + `.ux4g-list-item` | `.ux4g-list-default` | none ships | Semantic list of tier checks. |
| Card | `.ux4g-card` + `.ux4g-card-body`, `.ux4g-card-title`, `.ux4g-card-sub-title` | none named | none ships | One result per Tier 0, Tier 1 or Tier 2 check. |
| Layout utility | `.ux4g-d-flex`, `.ux4g-flex-column`, `.ux4g-gap-y-m` | n/a | `gap-y-m` | The warning and check list stack. |

No custom CSS is needed: the existing modal scrolls, and the UX4G list,
card and spacing utilities provide the new result layout.

### Amendment for prototype OCR text

- **Delivery:** existing local npm `ux4g-web-components@2.1.0`.
- **Theme:** default light theme; no token overrides.
- **Components:** no new component. The transcript is a plain text paragraph
  inside the existing Tier 1 Card (`.ux4g-card` and `.ux4g-card-body`, with no
  variant or size); the existing result Modal and default List remain unchanged.
- **Safety:** render OCR output through `textContent`; no custom CSS or HTML
  interpretation is needed.
