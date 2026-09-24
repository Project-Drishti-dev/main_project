# DRISHTI frontend

## Run locally

1. From this directory, run `npm install` once to install the pinned UX4G package.
2. Open `index.html` with VS Code Live Server.

The UX4G CSS and runtime are loaded from the local `node_modules` directory, so
the page does not depend on the UX4G CDN at runtime.

The login, registration, password-reset, and home-screen flows are frontend
prototypes only. Login currently routes to the workspace regardless of the
entered values; it does not authenticate.

The home screen can preview a selected JPEG, PNG, or WebP image in the browser.
Its quality-results dialog is illustrative only: the Python checker is not
connected, and no scores are calculated. The selected image is not uploaded or
persisted. Camera capture and the sidebar destinations (except logout) are
placeholders.

The quality checker in `D:\SIH\SIH_QualityCheck` is a Python command-line tool
that reads a local file path. Connecting it to this browser frontend will
require a backend/API to receive and validate an image, run the checker, and
return its JSON results. The backend should enforce its own size/type limits
and avoid retaining identity-document images unless explicitly required.

## Test

Run `npm test` from this directory.
