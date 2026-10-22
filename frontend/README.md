# DRISHTI frontend

## Run locally

1. From `frontend/`, run `npm ci` once to install the pinned UX4G package.
   The lockfile is committed, so this is the reproducible form; `npm install`
   works too.
2. In a separate terminal, install and start the API from the repository root:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   python -m uvicorn main:app --reload --port 8080
   ```

3. Build the site, then serve it. From `frontend/`:

   ```powershell
   npm run preview
   ```

   That builds `frontend/dist/` and serves it at `http://127.0.0.1:5500/`.
   See **Build, then serve** below for the whole workflow.

4. `dist/index.html` links to `home.html`. **Start screening** opens the
   Overview upload modal. Submitting an image calls
   `http://localhost:8080/api/analyze`, which returns nine image-quality
   results plus Tier 0 MRZ-format detection, Tier 1 OCR status, and seven Tier 2
   prototype signals.

The UX4G CSS and runtime are loaded from the local `node_modules` directory, so
the page does not depend on the UX4G CDN at runtime.

The home screen displays the nine image-quality results and tier checks in a
separate section. Tier 1 uses Tesseract when installed and never returns OCR
text. All seven Tier 2 checks are labelled prototype stubs; their scores are
not an authenticity verdict and are not combined into the quality pass/fail
result. `POST /api/analyze` does not persist image files. Use synthetic images
for local testing and avoid real identity documents.

The public demo has no login, registration, password-reset, or logout flow.
It does not authenticate users or make identity-verification decisions.

`api-config.js` selects localhost only when the frontend itself is served from
`localhost` or `127.0.0.1`. It intentionally leaves the API URL empty on other
hosts. The production build generates `dist/api-config.js` using the
`DRISHTI_API_BASE_URL` build environment variable.

The full list of variables this build reads is one table in the root
[README](../README.md#environment-variables) -- reader, status, and the value
it ships as. [`.env.example`](../.env.example) is the same list in
copy-pasteable form, and a test fails if the two disagree.

## Build, then serve

A source `.html` file under `frontend/` is a fragment: the build fills it into
`frontend/shell.html` and writes a finished page into `frontend/dist/`. Opening
a fragment from disk shows its `{{token}}` placeholders rather than a page, so
the workflow is build first, then serve what the build wrote.

| Command | What it does |
| --- | --- |
| `npm run build` | Writes `frontend/dist/` and stops. |
| `npm run check-artefacts` | Reads `frontend/dist/` and fails, naming every page, script or asset the build owes that is missing or empty. |
| `npm run preview` | Builds `frontend/dist/`, then serves it. |
| `npm run shots` | Renders every page at 320, 768, 1024 and 1440 CSS pixels into `docs/viewport-shots/`. |
| `npm test` | Runs the frontend suite. |

`npm run shots` runs `scripts/viewport-shots.cjs`. It builds, serves, drives a
headless Chromium over the DevTools protocol, and writes one full-page PNG per
page per width under `docs/viewport-shots/<width>/`. The same run measures each
render for sideways overflow, clipped text and text below 10px, and writes
`docs/viewport-shots/README.md` with a verdict per page and width; it exits
non-zero when any page has a finding. Set `DRISHTI_BROWSER` to choose the
browser executable.
`npm run preview` runs `scripts/preview.cjs`. It builds before it serves, so a
preview cannot publish a stale `dist/` beside the sources, and it serves exactly
the directory the build wrote.

The server answers `http://127.0.0.1:5500/`, which opens `dist/index.html` --
the public demo -- and every page the build wrote by its own name:
`home.html`, `screenings.html`, `settings.html`, `guide.html`, `about.html` and
`profile.html`. It prints the port and that page list when it starts. Set
`DRISHTI_PREVIEW_PORT` to use another port; `0` asks the operating system for a
free one. The server binds loopback only, answers a path climbing out of `dist/`
with `403`, and a name the build does not write with `404`.

To serve a build without rebuilding it -- to look at what a Cloudflare Pages
deploy would publish -- run `npm run build` and open `frontend/dist/` with VS
Code Live Server or any other static file server, on port `5500` or another
localhost origin allowed by `backend/app/config.py`.

Either route leaves the API base URL alone. Served from `localhost` or
`127.0.0.1`, the generated `api-config.js` points at `http://localhost:8080`
whatever `DRISHTI_API_BASE_URL` holds, so a local preview reaches a local API
with nothing set; `DRISHTI_API_BASE_URL` names the origin for every other
host, as described under **Deploy to Cloudflare Pages**.

## Deploy to Cloudflare Pages

The Pages build packages the HTML, CSS, JavaScript, and pinned UX4G CSS/runtime
into `dist/`. From `frontend/`, verify the build locally with:

```powershell
$env:DRISHTI_API_BASE_URL = "https://your-cloud-run-service.run.app"
npm run build
npm run check-artefacts
npm test
```

Create a Cloudflare Pages project using the Git integration and configure:

- **Root directory:** `frontend`
- **Build command:** `npm run build`
- **Build output directory:** `dist`
- **Framework preset:** None
- **Production environment variable:** `DRISHTI_API_BASE_URL`, set to the
  Cloud Run service origin (HTTPS only; no `/api/analyze` path).

The API origin is public browser configuration, not a secret. If the variable
is omitted, the build warns and the hosted analysis feature stays unconfigured.
Preview builds can omit it unless you also want those preview sites to call the
API.

After the first Pages deploy, copy its exact `https://<project>.pages.dev`
origin into the Cloud Run service's `CORS_ORIGINS` environment variable. Do not
include a path or trailing slash. If adding a custom domain later, add that
exact HTTPS origin to `CORS_ORIGINS` too, then deploy the updated Cloud Run
revision.

The Cloud Run API is publicly callable and unauthenticated. CORS only restricts
browser origins; it is not API authentication. Use synthetic images, not real
identity documents, until authentication and abuse protections are in place.
Camera capture and the sidebar destinations remain placeholders.

## Test

Run `npm test` from this directory.
