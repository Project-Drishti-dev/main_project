# DRISHTI Project — Handover

**Prepared:** September 24, 2026  
**Updated:** September 27, 2026
**Workspace:** `D:\sih\main_project`  
**Frontend:** `D:\sih\main_project\frontend`

## Resume from here

The DRISHTI frontend is deployed on Cloudflare Pages at `https://project-drishti.pages.dev/` and the FastAPI quality API is deployed on Google Cloud Run. The frontend uploads images to `POST /api/analyze`; the deployed API origin is `https://main-project-888645637790.asia-south1.run.app`. The user reports configuring the Cloud Run CORS allowlist for the Pages origin and resolving the deployed connection issue. On September 27, 2026, the user reported an active Cloudflare phishing interstitial for `project-drishti.pages.dev`; its report says “Appeared in Intel data source.” The report has not been independently inspected from this workspace. The frontend build was changed to publish a clearly labeled, no-account demo; redeploy it and follow up with Cloudflare through the report/mitigation review flow. Inspect this handover and `git status` before making changes.

### Deployment connection notes

- Cloudflare Pages builds the static site with `frontend/build.cjs`; the build packages the pinned UX4G assets and generates `dist/api-config.js`.
- The Pages build-time variable is `DRISHTI_API_BASE_URL`, set to the Cloud Run service origin (not the `/api/analyze` path). Rebuild/redeploy Pages after changing it.
- Cloud Run reads `CORS_ORIGINS` as a comma-separated list of exact browser origins. Include the production Pages origin without a path or trailing slash; add the exact custom-domain origin when one is configured. Changing the Cloud Run variable requires deploying a new revision.
- The generic frontend “Could not connect” message is used when `fetch` rejects; browser CORS failures can produce it even when the API is running. `GET /health` should return `{"status":"ok"}`.
- The API is publicly callable and has no authentication or rate limiter. CORS is not API authentication; use synthetic images only.

## Current implementation

- `frontend/index.html` and `frontend/home.html`: public demo entry points with no login, registration, password-reset, or logout flow. The source root page redirects to `home.html`; the production build copies the demo page to `dist/index.html`.
- `frontend/home.html`, `home.css`, `home.js`, `api-config.js`: modular UX4G demo with an expandable icon sidebar, placeholder navigation options, image-source modal, local image preview, and results modal wired to `POST /api/analyze`. The page labels the checker experimental and advises using synthetic images only. API URL defaults to `http://localhost:8080` only on localhost; production builds use `DRISHTI_API_BASE_URL`.
- `frontend/build.cjs`, `build.test.cjs`, `.nvmrc`: Cloudflare Pages static build, UX4G asset packaging, build-time API configuration, and build contract tests.
- `frontend/home.test.cjs` and `frontend/build.test.cjs`: Node tests for the demo interactions and the static-build contract, including exclusion of the former account-flow files.
- `frontend/README.md`: run and test instructions.
- `backend/`: FastAPI service deployed on Cloud Run with `GET /health` and `POST /api/analyze`, structured JSON results/errors, exact-origin CORS configuration, upload/media/dimension validation, and no persistent image storage. See `backend/README.md`.
- `backend/app/quality_checker/`: vendored copies of the nine quality-check modules plus an API runner. The external checker repo was left unchanged; its copied module files were verified byte-for-byte against the source on September 25, 2026.

The public frontend is an unauthenticated prototype and does not ask visitors for account credentials. The home screen accepts JPEG, PNG, or WebP files up to 10 MiB, previews locally, and sends the image to the configured API only when analysis is submitted. The API itself is publicly callable and does not persist uploaded image files. Checker thresholds are experimental and are not an identity-verification decision; use synthetic images for testing.

The original Python checker remains in the separate repo `D:\SIH\SIH_qualitycheck`; `main.py` is a CLI that reads local filesystem paths and can emit JSON for nine quality checks. The backend uses vendored copies under `backend/app/quality_checker/` so it can deploy independently. If the original algorithms change, intentionally resync the copies and rerun backend tests.

## UX4G and visual decisions — preserve consistency

- Keep the default UX4G **light** theme (`data-theme="light"`); do not add custom theme-token overrides unless the user asks for a brand theme.
- The frontend uses framework-neutral HTML/CSS/JS with the pinned local npm package `ux4g-web-components@2.1.0`. UX4G supplies CSS components and a runtime usable from HTML, React, or Angular; there is no need to migrate frameworks for these screens.
- CSS and runtime load from `frontend/node_modules/ux4g-web-components/`, not a CDN. This avoids CDN/runtime styling failures. Do not switch to CDN or add a second UX4G delivery method.
- The public demo uses the default UX4G light theme and an app-specific responsive workspace layout. Do not reintroduce account/credential collection in the public demo unless genuine authentication is implemented and the user requests it.
- UX4G compositions currently used include:
  - Card: `ux4g-card ux4g-p-l`.
  - Buttons: base + variant + size, e.g. `ux4g-btn ux4g-btn-primary ux4g-btn-md`; text actions use `ux4g-btn ux4g-btn-text-primary ux4g-btn-sm`.
  - Home-screen large action: `ux4g-btn ux4g-btn-primary ux4g-btn-lg`; sidebar icon toggle: `ux4g-icon-btn ux4g-icon-btn-text-primary ux4g-icon-btn-md`.
  - Home-screen dialogs use the same modal backdrop classes; the results dialog uses `ux4g-modal-box ux4g-modal-l`.
  - Radius utility: `ux4g-radius-m`.
- Application-specific CSS is for the two-column/responsive page layout, CSS scan illustration, and positioning of controls; UX4G classes/tokens remain responsible for the design-system components and theme colors. Check the installed CSS for tokens/classes before adding or renaming any.

## Run and verify

From `frontend/`:

1. Install dependencies if needed: `npm install`.
2. Open `index.html` or `home.html` with VS Code Live Server; both open the public demo.
3. Tests: `rtk proxy npm test` — **22 tests passed** on September 27, 2026.

From `backend/`, with Python 3.12 and `requirements-dev.txt` installed:

1. Start locally: `python -m uvicorn main:app --reload --port 8080`.
2. Tests: `python -m pytest -q` — **13 tests passed** on September 25, 2026. Reverified with the system Python using `python -m pytest -q -p no:faulthandler`; the project `.venv` currently does not have `pytest` installed.
3. `python -m compileall -q backend` passed from the repo root; `/health` was also verified against a running local Uvicorn server.

The global Python used for this session has `opencv-python 5.0.0.93` installed, while `backend/requirements.txt` specifies `opencv-python-headless>=4.8,<5`. The default pytest run printed Windows native access-violation diagnostics during NumPy/OpenCV import despite returning 13 passing tests; the full suite passed cleanly with `-p no:faulthandler`. Use the documented backend virtual environment before manually running the API.

`npm run build`, the 22-test frontend suite, and `git diff --check` passed during the September 27 frontend update. The built `dist/` contains only the public demo, its API configuration, and UX4G assets; no account-flow files or credential fields were found. The repository instruction in `AGENTS.md` says to prefix shell commands with `rtk`; `rtk proxy npm test` worked.

## Verification still needed

No real-browser visual/accessibility pass was performed. The user reports resolving the deployed Pages-to-Cloud-Run connection after configuring CORS, but no independent live request or browser Network trace was captured in this workspace. When browser tooling is available:

- Check the public demo at 320, 768, 1024, and 1440 CSS-pixel widths; capture screenshots and inspect console/network.
- Confirm UX4G CSS/runtime load; exercise source-selection and results modals (close button, backdrop, Escape), upload/preview, and sidebar expansion.
- Check keyboard order/focus, modal focus behavior, accessible names/live messages, contrast, image validation, and confirm the upload request occurs only after submission.
- Run the local end-to-end flow: start the backend on port 8080, serve the frontend on an allowed localhost origin (e.g. Live Server port 5500), and upload a synthetic image.
- Recheck the deployed `/health`, the Pages `/api-config.js`, and an image upload in browser DevTools if the connection issue recurs.
- When a custom frontend domain is added, include that exact HTTPS origin in Cloud Run's `CORS_ORIGINS` and deploy a new revision. Keep public endpoint limits small; the API currently has no authentication or rate limiter.
- The pages currently select light theme only; dark-theme behavior is not implemented or verified.

## Working-tree caution

Recheck Git status before future work and preserve unrelated existing changes; do not reset/clean the tree or modify `lorebook/` as part of frontend tasks.

## Previous implementation record: skills and sources

Skills applied or consulted while implementing the home-screen and screening prototype:

- `using-agent-skills` for workflow selection.
- `ux4g-design` and `frontend-ui-engineering` for UX4G consistency and responsive UI work.
- `incremental-implementation` and `test-driven-development` for small implementation slices and test verification.
- `security-and-hardening` for upload/input handling considerations.
- `git-workflow-and-versioning` to preserve and inspect the existing uncommitted work; no commit was made.

Sources inspected:

- The local UX4G `Design.md` contract and the pinned `ux4g-web-components@2.1.0` package README, CSS, and runtime under `frontend/node_modules/ux4g-web-components/`.
- `README.md`, `main.py`, `requirements.txt`, and the nine metric modules in `D:\SIH\SIH_QualityCheck`.
- The external UX4G online documentation path was unavailable during that implementation, so it was not used as a source.

Scope decisions/deviations to preserve:

- The frontend is deployed on Cloudflare Pages and the API on Cloud Run. Pages uses `DRISHTI_API_BASE_URL`; Cloud Run uses `CORS_ORIGINS` for the exact Pages origin. The user reports the CORS configuration is now in place.
- Camera capture and all sidebar destinations remain UI placeholders.
- The former mock login, registration, and password-reset flows were removed from the public demo and Pages build after the user reported an active phishing interstitial. Do not describe the demo as authenticated.
- Browser visual/runtime verification was unavailable; the test and syntax results above are not a substitute for a browser pass.

## Suggested skills for the next session

- `using-agent-skills` to select the workflow.
- `ux4g-design` before any UX4G UI change; follow its preflight and use the UX4G `Design.md` contract and installed package as the source of truth.
- `frontend-ui-engineering` for responsive/accessibility/visual work.
- `incremental-implementation` and `test-driven-development` for multi-file or behavioral changes.
- `browser-testing-with-devtools` when a browser MCP is available; otherwise state the verification limitation.
- `security-and-hardening` before connecting real authentication, handling credentials, or adding a backend integration.
- `git-workflow-and-versioning` for changes and review of the existing uncommitted tree.

The user previously chose the default UX4G theme, so do not ask them to choose colors again unless they request a branded theme.
