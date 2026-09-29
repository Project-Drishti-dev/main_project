# DRISHTI Project — Handover

**Prepared:** September 24, 2026  
**Updated:** September 30, 2026
**Workspace:** `D:\sih\main_project`  
**Frontend:** `D:\sih\main_project\frontend`

## Resume from here

The prototype now has a full multi-page interface. `home.html` (the public demo and `dist/index.html`) plus five new pages: `screenings.html`, `settings.html`, `guide.html`, `about.html`, and `profile.html`. Settings genuinely work — theme (light/dark/system) and text size are real, persisted browser preferences. The new pages are polished but mostly hold sample data, and **none of it has been through a real browser.**

The DRISHTI frontend remains available on Cloudflare Pages at `https://project-drishti.pages.dev/`, and the FastAPI quality API remains deployed on Google Cloud Run. The frontend uploads images to `POST /api/analyze`; the deployed API origin is `https://main-project-888645637790.asia-south1.run.app`. The user reports that the Cloudflare Pages site is back online after the earlier phishing false alert; the formal alert/review outcome has not been independently checked.

**Nothing from the September 30 UI work has been deployed.** Pages still serves whatever was last pushed. The five new pages, dark mode, and text size exist only in the local checkout.

### Git state as of September 30, 2026

- Branch is **`ag/experimental-updates`**, not `ag/alpha-2`. HEAD is `11fe962 Fix(Major): Fixed false flags about phishing risk, fixing prod`.
- The tree is **uncommitted**: modified `frontend/build.cjs`, `build.test.cjs`, `home.html`, `home.js`, `home.test.cjs`, `handover.md`; untracked `about.html`, `guide.html`, `pages.css`, `pages.js`, `pages.test.cjs`, `preferences.js`, `profile.html`, `screenings.html`, `settings.html`.
- No commit was made this session. Nothing under `lorebook/` was modified by this work, though the user added `abstract.txt` and `description.txt` there on September 30 for their own purposes. Recheck status before editing and do not reset or clean.

### Recent deployment and domain status

- GitHub Pages is also deployed as a fallback. It initially showed the old login page because the no-login update was on another branch; the user reports that merging the older branch fixed this. The user has a personal GitHub Pages site and a separate organization Pages site. Exact live URLs and the latest successful deployment commit were not independently inspected.
- The user reports `project-drishti.tech` is serving over HTTP while its TLS certificate is pending. The API works on `project-drishti.pages.dev` but was still reported failing on the `.tech` site.
- The last-reported Cloud Run `CORS_ORIGINS` value was `http://project-drishti.tech/,https://project-drishti.pages.dev/,https://Cosmiczen7.github.io,https://project-drishti-dev.github.io/`. The backend parser splits on commas, trims whitespace, strips trailing slashes, and rejects `*`; therefore the HTTP `.tech` origin should match if the browser origin is exactly `http://project-drishti.tech`. The failure remains unresolved: check `location.origin`, the failed request/OPTIONS `Origin` header, and the active traffic-serving Cloud Run revision. Normalize the personal Pages hostname to lowercase. Add `https://project-drishti.tech` after HTTPS is active. The organization Pages origin is `https://project-drishti-dev.github.io` if that is the actual organization hostname.
- Before updating this handover, the local checkout was clean on `ag/alpha-2` and contained no `.github/workflows` file, despite the user-reported Pages deployment. Remote refs may not include the reported merge; refresh Git and inspect the actual Actions workflow/run before changing deployment configuration.

### Deployment connection notes

- Cloudflare Pages builds the static site with `frontend/build.cjs`; the build packages the pinned UX4G assets and generates `dist/api-config.js`.
- The Pages build-time variable is `DRISHTI_API_BASE_URL`, set to the Cloud Run service origin (not the `/api/analyze` path). Rebuild/redeploy Pages after changing it.
- Cloud Run reads `CORS_ORIGINS` as a comma-separated list of exact browser origins. `backend/app/config.py` trims whitespace and trailing slashes; origins still need the right scheme and hostname, with no path. Changing the Cloud Run variable requires deploying a new revision. CORS is not API authentication.
- For the current HTTP custom domain, allow `http://project-drishti.tech`; add `https://project-drishti.tech` once its certificate is active. If the site redirects to `www`, allow that exact hostname too. Keep only the origins that actually serve the frontend.
- The generated Cloudflare `*.pages.dev` hostname is not a domain the user controls and cannot be claimed as a GitHub Pages custom domain. A purchased domain can serve different providers on distinct hostnames, but one hostname should point to one Pages host.
- The generic frontend “Could not connect” message is used when `fetch` rejects; browser CORS failures can produce it even when the API is running. `GET /health` should return `{"status":"ok"}`.
- The API is publicly callable and has no authentication or rate limiter. CORS is not API authentication; use synthetic images only.

## Current implementation

- `frontend/index.html` and `frontend/home.html`: public demo entry points with no login, registration, password-reset, or logout flow. The source root page redirects to `home.html`; the production build copies the demo page to `dist/index.html`.
- `frontend/home.html`, `home.css`, `home.js`, `api-config.js`: modular UX4G demo with an expandable icon sidebar, real navigation to the new pages, image-source modal, local image preview, and results modal wired to `POST /api/analyze`. The page labels the checker experimental and advises using synthetic images only. API URL defaults to `http://localhost:8080` only on localhost; production builds use `DRISHTI_API_BASE_URL`.
- `frontend/build.cjs`, `build.test.cjs`, `.nvmrc`: Cloudflare Pages static build, UX4G asset packaging, build-time API configuration, and build contract tests.
- `frontend/home.test.cjs` and `frontend/build.test.cjs`: Node tests for the demo interactions and the static-build contract, including exclusion of the former account-flow files.
- `frontend/README.md`: run and test instructions.
- `backend/`: FastAPI service deployed on Cloud Run with `GET /health` and `POST /api/analyze`, structured JSON results/errors, exact-origin CORS configuration, upload/media/dimension validation, and no persistent image storage. See `backend/README.md`.
- `backend/app/quality_checker/`: vendored copies of the nine quality-check modules plus an API runner. The external checker repo was left unchanged; its copied module files were verified byte-for-byte against the source on September 25, 2026.

### Secondary pages (added September 30, 2026)

All five share the same shell (sidebar, topbar, footer), `home.css`, and `pages.css`.

- `frontend/screenings.html` — previous screenings. UX4G table (`ux4g-table ux4g-table-m ux4g-table-zebra-rows ux4g-table-interactive`), 7 columns, 6 sample rows, live search, `ux4g-filter-chip-group` result filter, sortable Checked column via `aria-sort`, per-row View/Delete, `ux4g-pagination`, `ux4g-empty-state`, four summary tiles, and a working client-side CSV export.
- `frontend/settings.html` — Appearance card with working theme radios (Light/Dark/System) and text-size radios (Default/Large/Extra large), a live summary line, and a Reset-to-defaults button. A second card holds four placeholder switches that are clearly labelled as not connected to the API.
- `frontend/guide.html` — four-step stepper, a nine-item accordion explaining every check (each with a one-line summary and a "Fix" line), a "before you upload" checklist, and an accepted-formats list.
- `frontend/about.html` — prototype facts grid, how-it's-built cards, data/privacy list, known limitations, and links out.
- `frontend/profile.html` — sample profile: avatar with local-only photo preview and change/remove, editable name and email, read-only Details (Role, Organisation, Location, and so on), and a full-width Security card.
- `frontend/preferences.js` — shared theme/text-size module. Loaded **synchronously in `<head>`** on every page so there is no flash of the wrong theme. Storage key `drishti.preferences.v1`, shape `{theme, textSize}`, defaults `{theme:"light", textSize:"default"}`. Guards against `localStorage` throwing (private mode) and silently keeps preferences in memory.
- `frontend/pages.js` — shared behaviour for the secondary pages: sidebar toggle, accordion toggle, screenings search/filter/sort/delete/CSV export, settings control sync, and the profile form.
- `frontend/pages.css` — layout for the secondary pages only, loaded after `home.css`.
- `frontend/pages.test.cjs` — new test file covering preferences behaviour, shared-shell and navigation consistency across all six pages, token validity, and per-page content.

### Deliberate decisions to preserve

- **No password field anywhere.** `profile.html` has a "Change password" button, but it is `aria-disabled="true"` and explains there is no account or stored password. Mock credential collection is what drew the Cloudflare phishing interstitial, and there is still no auth backend. Do not add a real password form without genuine authentication; the user has not authorised one.
- **Profile edits are never persisted.** Name and email live in the tab only. Only theme and text size are stored, under one key.
- **Screenings data is sample data**, not a record store, and says so on the page.
- The demo is still unauthenticated and must not be described as having accounts.

The public frontend is an unauthenticated prototype and does not ask visitors for account credentials. The home screen accepts JPEG, PNG, or WebP files up to 10 MiB, previews locally, and sends the image to the configured API only when analysis is submitted. The API itself is publicly callable and does not persist uploaded image files. Checker thresholds are experimental and are not an identity-verification decision; use synthetic images for testing.

The original Python checker remains in the separate repo `D:\SIH\SIH_qualitycheck`; `main.py` is a CLI that reads local filesystem paths and can emit JSON for nine quality checks. The backend uses vendored copies under `backend/app/quality_checker/` so it can deploy independently. If the original algorithms change, intentionally resync the copies and rerun backend tests.

## UX4G and visual decisions — preserve consistency

- Keep the default UX4G **light** theme as the shipped default (`data-theme="light"`); do not add custom theme-token overrides unless the user asks for a brand theme. Users can now switch to dark or system at runtime, but that is UX4G's own token set, not a custom theme.
- The frontend uses framework-neutral HTML/CSS/JS with the pinned local npm package `ux4g-web-components@2.1.0`. UX4G supplies CSS components and a runtime usable from HTML, React, or Angular; there is no need to migrate frameworks for these screens.
- CSS and runtime load from `frontend/node_modules/ux4g-web-components/`, not a CDN. This avoids CDN/runtime styling failures. Do not switch to CDN or add a second UX4G delivery method.
- The public demo uses the default UX4G light theme and an app-specific responsive workspace layout. Do not reintroduce account/credential collection in the public demo unless genuine authentication is implemented and the user requests it.
- UX4G compositions currently used include:
  - Card: `ux4g-card ux4g-p-l`.
  - Buttons: base + variant + size, e.g. `ux4g-btn ux4g-btn-primary ux4g-btn-md`; text actions use `ux4g-btn ux4g-btn-text-primary ux4g-btn-sm`.
  - Home-screen large action: `ux4g-btn ux4g-btn-primary ux4g-btn-lg`; sidebar icon toggle: `ux4g-icon-btn ux4g-icon-btn-text-primary ux4g-icon-btn-md`.
  - Home-screen dialogs use the same modal backdrop classes; the results dialog uses `ux4g-modal-box ux4g-modal-l`.
  - Radius utility: `ux4g-radius-m`.
  - Secondary pages add: `ux4g-table*`, `ux4g-tag-{variant}-{color}`, `ux4g-search-container ux4g-search-m`, `ux4g-filter-chip-group` + `ux4g-filter-chip-md`, `ux4g-pagination ux4g-pagination-compact`, `ux4g-empty-state`, `ux4g-radio ux4g-radio-md`, `ux4g-switch ux4g-switch-md`, `ux4g-alert ux4g-alert-{info,warning}`, `ux4g-accordion*`, `ux4g-stepper*`, `ux4g-list ux4g-list-{default,warning}`, `ux4g-avatar ux4g-avatar-profile ux4g-avatar-2xl`, `ux4g-input-container ux4g-input-md ux4g-input-default` wrapping `ux4g-label-m-default` + `.ux4g-input` > `.ux4g-input-input` + `ux4g-input-helper`.
- Application-specific CSS is for the two-column/responsive page layout, CSS scan illustration, and positioning of controls; UX4G classes/tokens remain responsible for the design-system components and theme colors. Check the installed CSS for tokens/classes before adding or renaming any.

### Text size: why it is a root font-size rule

Every UX4G type token resolves to a **rem** value (`--ux4g-font-size-16: 1rem`, and `--ux4g-fs-*` aliases to those), and the package sets **no** `html { font-size }`. So `html[data-text-size="large"] { font-size: 112.5% }` and `html[data-text-size="x-large"] { font-size: 125% }` scale the entire design system without overriding a single token. **Caveat:** the package also contains ~32 internal `px` font-size literals that will not scale.

### UX4G 2.1.0 defects found on September 30, 2026

Verify against the installed package before trusting its README. Both were confirmed by reading `node_modules/ux4g-web-components`:

1. **No accordion behaviour ships.** The runtime `dist/runtime/design-system.js` contains **zero** occurrences of `ux4g-accordion` or `data-ux4g-accordion-toggle` (the word appears once, in a comment). The package README documents that attribute, and `Design.md` §10 lists Accordion among delegated behaviours, but nothing implements it. `pages.js` therefore provides `initAccordions()` keyed off the documented `data-ux4g-accordion-toggle`, so it can be deleted if UX4G ever ships it. `pages.test.cjs` asserts the runtime still lacks accordion support; if that assertion starts failing, remove the fallback.
2. **Malformed CSS selector breaks the horizontal stepper.** The stylesheet contains `.ux4g-stepper-center):not(.ux4g-stepper-left):not(.ux4g-stepper-bottom-line) .ux4g-stepper-step:not(:last-child):after` — an unbalanced parenthesis, so browsers drop the rule and the connector falls back to a vertical one. `pages.css` redraws the connector scoped to `.guide-stepper`. A test asserts the malformed selector still exists so the workaround can be deleted when it is fixed upstream.

Also note the README stepper example uses `class="ux4g-stepper-step completed"`, but `completed` is not a real class — the package uses `ux4g-stepper-completed` / `ux4g-stepper-done` and requires `ux4g-stepper-head` + `ux4g-stepper-head-icon` children. And `ux4g-accordion-bordered` is what draws a box around each item; dropping it gives the cleaner divider look.

## Run and verify

From `frontend/`:

1. Install dependencies if needed: `npm install`.
2. Open `index.html` or `home.html` with VS Code Live Server; both open the public demo. The other pages open directly: `screenings.html`, `settings.html`, `guide.html`, `about.html`, `profile.html`.
3. Tests: `rtk proxy npm test` — **45 tests passed** on September 30, 2026 (was 22).

From `backend/`, with Python 3.12 and `requirements-dev.txt` installed:

1. Start locally: `python -m uvicorn main:app --reload --port 8080`.
2. Tests: `python -m pytest -q` — **13 tests passed** on September 25, 2026. Reverified with the system Python using `python -m pytest -q -p no:faulthandler`; the project `.venv` currently does not have `pytest` installed.
3. `python -m compileall -q backend` passed from the repo root; `/health` was also verified against a running local Uvicorn server.

The global Python used for this session has `opencv-python 5.0.0.93` installed, while `backend/requirements.txt` specifies `opencv-python-headless>=4.8,<5`. The default pytest run printed Windows native access-violation diagnostics during NumPy/OpenCV import despite returning 13 passing tests; the full suite passed cleanly with `-p no:faulthandler`. Use the documented backend virtual environment before manually running the API.

`npm run build`, the 45-test frontend suite, and `git diff --check` all passed on September 30, 2026 with `DRISHTI_API_BASE_URL` set to the Cloud Run origin. The built `dist/` contains all six pages, `home.css`, `pages.css`, `home.js`, `pages.js`, `preferences.js`, `api-config.js`, and the UX4G assets; zero `node_modules` references remain in the HTML. No account-flow files or credential fields were found. The repository instruction in `AGENTS.md` says to prefix shell commands with `rtk`; `rtk proxy npm test` worked.

Shell note on this Windows setup: `rtk` refuses to run unless `$HOME` is set, and the harness strips `$` from double-quoted arguments, so `rtk git ...` needs `$env:HOME=$env:USERPROFILE; $env:CLAUDE_CONFIG_DIR="$env:USERPROFILE\.claude";` in front of it, and any PowerShell or Node one-liner containing `$` must go through a temporary script file.

## Verification still needed

**No real-browser visual/accessibility pass has ever been performed**, including for the September 30 pages. Every visual claim about the new pages, the stepper, the accordion, and dark mode is inferred from reading the CSS, not from a rendered screenshot. The 45 passing tests assert markup structure, token validity, and script logic only. Treat the UI as unverified until someone opens it.

The user reported the stepper, accordion, avatar initials, and profile inputs as visually broken on first render, which was fixed by reading the package source. Expect more visual defects to surface on the first real render.

The user reports that image analysis works from `project-drishti.pages.dev`; API connectivity from `project-drishti.tech` remains unresolved. No independent live request or browser Network trace was captured in this workspace. When browser tooling is available:

- Check the public demo at 320, 768, 1024, and 1440 CSS-pixel widths; capture screenshots and inspect console/network.
- **Open all six pages in both light and dark theme.** Check the guide stepper connector and circles, accordion expand/collapse and arrow rotation, the profile avatar initials centring, input borders/labels, and the profile grid at 320/768/1024/1440px.
- Exercise the settings page end to end: switch theme and text size, reload, confirm the choice persists and that dark mode has no unreadable text or invisible borders. Confirm the root font-size change does not break table or modal layout.
- Exercise the screenings page: search, each filter chip, the sort toggle, a row delete, clear-filters from the empty state, and CSV export.
- Confirm `preferences.js` does not throw when `localStorage` is unavailable (private browsing).
- Confirm UX4G CSS/runtime load; exercise source-selection and results modals (close button, backdrop, Escape), upload/preview, and sidebar expansion.
- Check keyboard order/focus, modal focus behavior, accessible names/live messages, contrast, image validation, and confirm the upload request occurs only after submission.
- Run the local end-to-end flow: start the backend on port 8080, serve the frontend on an allowed localhost origin (e.g. Live Server port 5500), and upload a synthetic image.
- Recheck the deployed `/health`, each Pages `/api-config.js`, and image uploads in browser DevTools. For the unresolved `.tech` CORS issue, compare `location.origin` with the active Cloud Run allowlist and inspect the `OPTIONS` preflight response.
- After TLS is active for `project-drishti.tech`, add its HTTPS origin to Cloud Run `CORS_ORIGINS` and deploy a new revision. Keep public endpoint limits small; the API currently has no authentication or rate limiter.

## Known debt

- **The sidebar shell markup is duplicated across all six pages.** Chosen deliberately for static-first rendering (no flash, no JS dependency, works without JavaScript), with a test enforcing that navigation stays identical everywhere. If pages keep multiplying, extract it.
- **`home.css` doubles as the shared shell stylesheet** despite its name; `pages.css` only holds secondary-page layout. Renaming `home.css` to something like `app.css` would be cleaner but touches the build and tests.
- Dark mode ships but has never been rendered or contrast-checked.
- Text-size scaling does not affect ~32 internal `px` font sizes in the UX4G package.

## Working-tree caution

Recheck Git status before future work and preserve unrelated existing changes; do not reset/clean the tree or modify `lorebook/` as part of frontend tasks.

## Previous implementation record: skills and sources

Skills applied or consulted while implementing the home-screen and screening prototype:

- `using-agent-skills` for workflow selection.
- `ux4g-design` and `frontend-ui-engineering` for UX4G consistency and responsive UI work.
- `incremental-implementation` and `test-driven-development` for small implementation slices and test verification.
- `security-and-hardening` for upload/input handling considerations.
- `git-workflow-and-versioning` to preserve and inspect the existing uncommitted work; no commit was made.

Skills applied or consulted for the September 30, 2026 secondary pages:

- `ux4g-design` for the mandatory preflight and the component plan. The user's earlier default-theme choice was reused rather than re-asked, as that handover records.
- Incremental, test-first slices: each new page or behaviour landed with its assertions, and the suite grew 22 → 45.
- `Design.md`, the package README, the compiled `ux4g.css`, and `design-system.js` were read directly. **The README proved unreliable** — it documents accordion attributes the runtime does not implement and a `completed` stepper class that does not exist. Grep the shipped CSS/JS before copying any example.

Sources inspected:

- The local UX4G `Design.md` contract and the pinned `ux4g-web-components@2.1.0` package README, CSS, and runtime under `frontend/node_modules/ux4g-web-components/`.
- `README.md`, `main.py`, `requirements.txt`, and the nine metric modules in `D:\SIH\SIH_QualityCheck`.
- The external UX4G online documentation path was unavailable during that implementation, so it was not used as a source.

Scope decisions/deviations to preserve:

- The frontend is deployed on Cloudflare Pages and GitHub Pages; the API is on Cloud Run. Pages builds use `DRISHTI_API_BASE_URL`; Cloud Run uses `CORS_ORIGINS` for exact browser origins. The user reports Cloudflare Pages is back online and that merging the older branch resolved the GitHub Pages login screen.
- `project-drishti.tech` is user-reported to be live over HTTP with TLS issuance pending. Its API connectivity is not yet confirmed; the last-reported allowlist and next diagnostics are recorded above.
- Camera capture and all sidebar destinations remain UI placeholders.
- The sidebar destinations are no longer placeholders; they are real pages as of September 30, 2026. Camera capture is still a placeholder.
- The former mock login, registration, and password-reset flows were removed from the public demo and Pages build after the user reported an active phishing interstitial. Do not describe the demo as authenticated.
- Browser visual/runtime verification was unavailable; the test and syntax results above are not a substitute for a browser pass.
- Dark mode and text size were added as runtime user preferences on the existing default theme. No custom theme tokens were introduced.
- The profile page deliberately ships without a password field; see the decisions section above.

## Suggested skills for the next session

- `using-agent-skills` to select the workflow.
- `ux4g-design` before any UX4G UI change; follow its preflight and use the UX4G `Design.md` contract and installed package as the source of truth.
- `frontend-ui-engineering` for responsive/accessibility/visual work.
- `incremental-implementation` and `test-driven-development` for multi-file or behavioral changes.
- `browser-testing-with-devtools` when a browser MCP is available; otherwise state the verification limitation.
- `security-and-hardening` before connecting real authentication, handling credentials, or adding a backend integration.
- `git-workflow-and-versioning` for changes and review of the existing uncommitted tree.

The user previously chose the default UX4G theme, so do not ask them to choose colors again unless they request a branded theme.

## If picking this up next

The single highest-value next step is a **browser pass** over the six pages in light and dark theme. Everything else in this handover is inferred from source, and the user already caught four visual defects that only a render would have shown. After that, the obvious product gap is that `screenings.html` still shows sample data because nothing persists a screening record.
