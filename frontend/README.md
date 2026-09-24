# DRISHTI frontend

## Run locally

1. From this directory, run `npm install` once to install the pinned UX4G package.
2. Open `index.html` with VS Code Live Server.

The UX4G CSS and runtime are loaded from the local `node_modules` directory, so
the page does not depend on the UX4G CDN at runtime.

The password-reset dialog and registration page are front-end prototypes only.
They do not send, verify, or persist account details or passwords.

## Test

Run `npm test` from this directory.
