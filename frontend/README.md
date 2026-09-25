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
hosts; set `apiBaseUrl` to the deployed API origin when configuring a hosted
frontend. This is a public, unauthenticated prototype API, not a secure
document-processing service. Camera capture and the sidebar destinations
(except logout) remain placeholders.

## Test

Run `npm test` from this directory.
