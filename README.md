# DRISHTI

A hackathon prototype whose Overview upload returns nine image-quality checks
plus separate Tier 0 MRZ-format, Tier 1 OCR-status and Tier 2 prototype signals.
It does not verify identity or decide document authenticity. A separate
screening-record API stores encrypted evidence and currently runs Tier 0 only.

Nothing here is an identity-verification decision, and no page in this
repository asks for a login.

## Start here

| File | What it is |
| --- | --- |
| [`DEMO.md`](DEMO.md) | The three-minute judge walkthrough, plus a 34-row ledger marking each claim Measured or Designed. |
| [`LIMITATIONS.md`](LIMITATIONS.md) | What this build does not do, under those same two labels. Read it before believing a number. |
| [`tasks.md`](tasks.md) | The executable checklist this project is driven from -- one behaviour and its test per task. An unchecked box is unfinished work. |
| [`ROADMAP.md`](ROADMAP.md) | The strategic plan the checklist was derived from. |
| [`HANDOVER.md`](HANDOVER.md) | Session state: last completed task, live invariants, blockers, next task. |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Why the build is the way it is, one numbered decision per heading. |
| [`AGENTS.md`](AGENTS.md) | The rules an agent works under in this repository. |

## Project structure

- `frontend/` — the website. Sources are HTML/CSS/JS fragments plus the shared
  `shell.html`; `npm run build` fills them in and writes ten pages into
  `frontend/dist/`. UX4G components come from the pinned
  `ux4g-web-components@2.1.0`, loaded out of `node_modules` and never from a
  CDN. See [`frontend/README.md`](frontend/README.md).
- `backend/` — the FastAPI service: the nine-check quality gate, in-memory
  tier summaries for Overview uploads, a separate screening-record cascade,
  the SQLite store, and Alembic migrations. See [`backend/README.md`](backend/README.md) for the API
  contract, the local run path and the Cloud Run settings.
- `docs/` — `DECISIONS.md`, the UX4G preflight record, and the browser
  evidence: `viewport-shots/`, `theme-shots/`, `private-check/` and
  `deployed-check/`, each written by its own `npm run` script, each written so
  that a finding fails the run rather than only being recorded.
- `scripts/` — `check-all.ps1`, the local verification script, and the
  task-file helpers beside it. `run_tasks.ps1` at the root is the autonomous
  loop that walks `tasks.md`.
- `.env.example` — every environment variable the project reads, each tagged
  live, planned, or deliberately held empty.
- `lorebook/` — the problem statement and abstract this project was built from.
  Reference material; nothing in the build reads it at runtime.
- `.github/workflows/ci.yml` — the same checks as `check-all.ps1`, as two jobs.

## What is implemented

- **The Overview upload.** `POST /api/analyze` returns the nine quality modules
  and safe Tier 0/1/2 summaries. It does not persist the image or return OCR
  text. Tier 1 uses Tesseract when installed; Tier 2 outputs carry `is_stub`.
- **Screening records.** `POST /api/screenings`, the list and detail routes, a
  report, an operator decision, progress polling and an SSE progress stream,
  plus an audit re-verification route. Records live in SQLite, and `alembic
  upgrade head` creates the schema the service reads.
- **Persistent screening records.** `POST /api/screenings` stores encrypted
  evidence and currently runs only the Tier 0 MRZ-format check.
- **Ten built pages** — home, screenings, result, cases, results, audit,
  profile, settings, guide, about — each filled from the shared shell, in light
  and dark themes, checked at 320, 768, 1024 and 1440 CSS pixels.
- **Re-runnable verification.** `./scripts/check-all.ps1` runs four stages; the
  browser-evidence scripts exit non-zero on a finding.

## What is not implemented

[`LIMITATIONS.md`](LIMITATIONS.md) is the full list, with evidence per item.
The short version:

- **Tier 1 field extraction is not wired.** The Overview reports whether its
  local Tesseract OCR check ran and displays recognized text for prototype
  inspection, but it does not validate extracted fields.
- **Tier 2 checks are all labelled stand-ins** (`is_stub=True`). No trained
  model weights or validation data ship, so their scores are exploratory
  signals, not authenticity findings.
- **Cross-document checks are not wired.** The upload flow has no case grouping
  API or way to submit multiple related documents.
- **No authentication, by decision** (`docs/DECISIONS.md` D2). No login, no
  session, and no credential field. The public API is unauthenticated and
  rate-limited.
- **The full record-and-audit upload flow is separate from the Overview demo.**
  The home modal uses `/api/analyze`; it does not create a stored screening row.
- **The history needs its migration.** Without `alembic upgrade head` the
  screenings screen reads *Could not load the history*, so no history row has
  been drawn in a browser either.
- **The container image has never been built here** — there is no container
  runtime on this machine (26.1 and 26.2, `[BLOCKED]`) — and CI has never run
  green, because this checkout is never pushed.
- **One deployed origin cannot reach the API.** See below.

## Run locally

Two halves, two terminals, nothing configured. The steps below were run
against a clean copy of this tree on 2026-10-06 -- no `.venv`, no
`node_modules`, no `dist/` -- and none of them needs an environment variable
set.

### 1 -- Backend, on 8080

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn main:app --reload --port 8080
```

`GET http://localhost:8080/health` then answers `{"status":"ok"}`, and
`http://localhost:8080/docs` is the interactive API contract.
`alembic upgrade head` creates `backend/drishti.db`, the SQLite file the
service reads; it is safe at every start, because a second run finds the
database already at `head`. Verified on CPython 3.12.10.
`backend/.python-version` pins 3.13 for the Cloud Buildpack image, which is a
different thing from the interpreter you run locally.

### 2 -- Frontend, built then served, on 5500

From `frontend/`:

```powershell
npm ci
npm run preview
```

`frontend/package-lock.json` is committed, so `npm ci` installs the pinned
`ux4g-web-components@2.1.0` reproducibly; `npm install` works too. `npm run
preview` builds `frontend/dist/` and *then* serves it, so a preview can never
publish a stale `dist/` beside the sources. It answers
`http://127.0.0.1:5500/`, which opens `dist/index.html`, and prints the eleven
pages it wrote. `npm run build` followed by any static file server is the
equivalent, and `npm run check-artefacts` reads the result and fails, naming
any of the 28 artefacts that is missing or empty. See
[`frontend/README.md`](frontend/README.md).

### The two halves find each other with nothing set

The build writes `dist/api-config.js`, which points the page at
`http://localhost:8080` whenever the page's own hostname is `localhost` or
`127.0.0.1`, and writes an empty API URL on every other host.
`DRISHTI_API_BASE_URL` names the API for a deployed site only; a local run
leaves it alone.

### Allowed origins

The browser enforces CORS, so the origin that *serves the page* has to be on
the backend's allowlist. With `CORS_ORIGINS` unset, the service allows exactly
the six origins in `LOCAL_CORS_ORIGINS`, `backend/app/config.py`:

| Port | Origins | |
| --- | --- | --- |
| 5500 | `http://localhost:5500`, `http://127.0.0.1:5500` | this project's preview server, and VS Code Live Server's default |
| 5501 | `http://localhost:5501`, `http://127.0.0.1:5501` | Live Server once 5500 is taken |
| 5173 | `http://localhost:5173`, `http://127.0.0.1:5173` | Vite's default, if a page is ever served by one |


Every other origin is answered without an `access-control-allow-origin`
header, which the browser treats as a refusal -- including
`http://localhost:8080`, the API's own origin. Setting `CORS_ORIGINS`
*replaces* those six rather than adding to them, and
[`.env.example`](.env.example) ships a value naming 5500 on both hosts, which
is all a local run needs.

### What a local run does and does not show

- **It shows both halves talking.** A synthetic PNG posted to
  `POST http://localhost:8080/api/analyze` with the preview page's origin
  answers `200` with all nine quality modules and the tier summaries, and echoes
  `access-control-allow-origin: http://127.0.0.1:5500`.
- **It does not create a stored screening record.** The Overview modal uses
  `/api/analyze`, which returns in-memory results and no screening id or audit
  row. The separate `/api/screenings` endpoint stores encrypted evidence and
  currently runs Tier 0 only.
- **No `.env` file is read.** Nothing in the backend loads one, so copying
  `.env.example` to `.env` changes nothing. Set a variable in the shell --
  `$env:CORS_ORIGINS = "http://localhost:5500"` -- to use one.

## Deployment

The backend is a Google Cloud Run service. The frontend is a static build
published by Cloudflare Pages, whose API origin is baked in at build time from
`DRISHTI_API_BASE_URL` — public browser configuration, not a secret, and not
checked into this repository. The Cloud Run `CORS_ORIGINS` allowlist must hold
the exact browser origin that serves the site, with no path and no trailing
slash.

What is actually verified, recorded on 2026-10-05 in
[`docs/deployed-check/README.md`](docs/deployed-check/README.md):

| Origin | State |
| --- | --- |
| `https://project-drishti.pages.dev` | Reaches the API. Its deployed `api-config.js` names the Cloud Run origin. |
| `https://project-drishti.tech` | Cannot reach the API: its `api-config.js` bakes in no base URL, and `https://project-drishti.tech` is absent from the serving revision's `CORS_ORIGINS`. Both fixes are deployment settings, not code. |
| GitHub Pages | Two `github.io` origins are in the deployed CORS allowlist, but nothing in this repository publishes to GitHub Pages — there is no workflow for it — so a build served there is unconfirmed. |

The revision serving traffic also predates `GET /api/version`, which answers
404 there while the route exists in this source.

## Environment variables

Every variable the project reads is listed here once. [`.env.example`](.env.example)
is the same list in copy-pasteable form, with the full rules for each value, and
`backend/tests/unit/test_env_reference_contract.py` fails if the two ever name a
different set of variables or give one of them a different status.

There is no authentication in this project (`docs/DECISIONS.md`, D2), so no
variable below holds a user credential. The three marked secret are server-side
keys injected by the platform, never a browser value and never a committed one.

Status: **live** is read by code in this repository now, **planned** is named in
[`tasks.md`](tasks.md) and not read yet, **held** is deliberately empty and must
be left unset.

### Frontend build -- read by `frontend/build.cjs` during `npm run build`

| Variable | Reader | Status | Ships as |
| --- | --- | --- | --- |
| `DRISHTI_API_BASE_URL` | `getApiBaseUrl`, baked into `dist/api-config.js` | live | `https://api.example.com`, a placeholder |
| `DRISHTI_BUILD_OUTPUT_DIR` | `buildOutputDirectory` | live | empty, meaning `frontend/dist` |
| `DRISHTI_STATION_LABEL` | `getStationLabel`, written beside it into `dist/api-config.js` | live | empty, meaning `station-unset` |
| `CF_PAGES` | `getApiBaseUrl`, only to warn about an unset API base URL | held | empty -- Cloudflare Pages sets it |

### Backend -- read by `backend/app/config.py`

| Variable | Reader | Status | Ships as |
| --- | --- | --- | --- |
| `CORS_ORIGINS` | `get_cors_origins` | live | `http://localhost:5500,http://127.0.0.1:5500` |
| `LOG_LEVEL` | `get_log_level` | live | empty, meaning `INFO` |
| `APP_ENV` | `get_app_env` | live | empty, meaning `development` |
| `DATABASE_URL` | `get_database_url` | live | empty, meaning SQLite at `backend/drishti.db` |
| `LEDGER_SIGNING_KEY` | `get_ledger_signing_key`, secret | live | empty, meaning a fresh key per call |
| `EVIDENCE_ENCRYPTION_KEY` | `get_evidence_encryption_key`, secret | live | empty: generated in development, refused in production |
| `EVIDENCE_STORE_ROOT` | `get_evidence_store_root` | live | empty, meaning `backend/evidence` |
| `RETENTION_DAYS` | `get_retention_days` | live | empty, meaning evidence is kept 90 days |
| `RATE_LIMIT_PER_MINUTE` | `get_rate_limit_per_minute` | live | empty, meaning 60 |
| `LOCAL_LLM_ENABLED` | `get_local_llm_enabled` | live | `false` |
| `LOCAL_LLM_BASE_URL` | `get_local_llm_base_url` | live | `http://127.0.0.1:11434` |
| `LOCAL_LLM_MODEL` | `get_local_llm_model` | live | empty, meaning no model is asked |
| `LOCAL_LLM_TIMEOUT_SECONDS` | `get_local_llm_timeout_seconds` | live | empty, meaning 30 |
| `STATION_LABEL` | the backend audit actor, tasks 10.7 and 23.12 -- not the frontend build's `DRISHTI_STATION_LABEL` | planned | empty |
| `PUBLIC_DEMO` | the public-demo gate, DECISIONS.md D7 | planned | `true` |
| `OCR_CONFIDENCE_THRESHOLD` | the Tier 1 re-read gate, task 12.9 | planned | empty |
| `AUDIT_DRAW_SECRET` | the deep-audit HMAC key, task 14.8, secret | planned | empty |
| `DEEP_AUDIT_RATE` | the deep-audit draw probability, task 14.8 | planned | empty |

`DRISHTI_STATION_LABEL` and `STATION_LABEL` are two different variables and
neither reads the other: the first names the station this build was deployed
as, the second is the audit actor a future backend task will record.

No local setup needs any of them. Every backend row ships empty or at a
local-development default, so a clean checkout runs with nothing configured. The
values that matter are the ones a deployment sets, which are covered under
**Deployment** and in the two half-READMEs.
## Continuous integration

Every push and pull request runs
[`.github/workflows/ci.yml`](.github/workflows/ci.yml), which performs the same
four checks as [`scripts/check-all.ps1`](scripts/check-all.ps1) — the backend
pytest suite, the frontend tests, the frontend build, and the built-artefact
check — as two jobs, because the halves need different runtimes. The workflow is
itself asserted by `backend/tests/unit/test_ci_workflow_contract.py`, so a stage
dropped from it fails the suite instead of going quietly unbuilt.

The last local run, on 2026-10-06, exited 0 on all four stages: 7835 backend
cases passed and 4 skipped, and 720 frontend cases passed.

## Standing cautions

- The thresholds are experimental and have never been calibrated against a real
  document set. Nothing this build reports is a measurement about a real
  identity document.
- Every published number describes this repository's own generated, synthetic
  corpus.
- The prototype is unauthenticated. Use synthetic images only, and do not send
  real identity documents to the deployed endpoint.
