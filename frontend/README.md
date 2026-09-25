# DRISHTI frontend

## Run locally

1. From `frontend/`, run `npm install` once to install the pinned UX4G package.
2. In a separate terminal, install and start the API from the repository root:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   python -m uvicorn main:app --reload --port 8080
   ```

3. Serve `frontend/` with VS Code Live Server on port `5500` (or another
   localhost origin allowed by `backend/app/config.py`), then open `index.html`.
4. On the home screen, choose **Start screening now → Upload an image**, select
   a JPEG, PNG, or WebP up to 10 MiB, then choose **Review quality checks**.
   The browser preview is local; the image is sent to
   `http://localhost:8080/api/analyze` only after submitting.

The UX4G CSS and runtime are loaded from the local `node_modules` directory, so
the page does not depend on the UX4G CDN at runtime.

The login, registration, password-reset, and home-screen flows are frontend
prototypes only. Login currently routes to the workspace regardless of the
entered values; it does not authenticate.

The home screen posts the selected image to the local quality API and displays
its nine module scores, pass/fail/N/A state, rules, reasons, and details. The
prototype checker thresholds are experimental and are not an
identity-verification decision. The API does not persist image files; use
synthetic images for local testing and avoid real identity documents.

`api-config.js` selects localhost only when the frontend itself is served from
`localhost` or `127.0.0.1`. It intentionally leaves the API URL empty on other
hosts. The production build generates `dist/api-config.js` using the
`DRISHTI_API_BASE_URL` build environment variable.

## Deploy to Cloudflare Pages

The Pages build packages the HTML, CSS, JavaScript, and pinned UX4G CSS/runtime
into `dist/`. From `frontend/`, verify the build locally with:

```powershell
$env:DRISHTI_API_BASE_URL = "https://your-cloud-run-service.run.app"
npm run build
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

The Cloud Run API and frontend login are currently unauthenticated prototypes.
CORS only restricts browser origins; it is not API authentication. Use
synthetic images, not real identity documents, until authentication and abuse
protections are in place. Camera capture and the sidebar destinations (except
logout) remain placeholders.

## Test

Run `npm test` from this directory.
