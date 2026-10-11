# DRISHTI Project -- Handover

**Updated:** October 6, 2026 -- 28.6 is the last completed task. `scripts/check-all.ps1`
was re-run today and exits 0 on all four stages: backend 7841 passed / 4 skipped,
frontend 720 passed, build and the 28-artefact check clean.

## Last Completed Task

- **28.6** -- Every environment variable is listed once, in `README.md` under
  `## Environment variables`, mirrored by `.env.example`. Six cases in
  `backend/tests/unit/test_env_reference_contract.py` compare the two lists and the
  variables the code reads. Two real drifts were fixed: `DRISHTI_STATION_LABEL`
  (read by `frontend/build.cjs`, documented nowhere) and `LOCAL_LLM_ENABLED`
  (tagged `[PLAN]` while `app/explain/summarizer.py` reads it). Rationale in
  `docs/DECISIONS.md` D231.

## Git State

- **Branch `ag/updates-3`, HEAD `1c39cd28`** -- `Feat(Backend): Tier 1 and Tier 2
  implemented`, 2026-10-03 16:57 +05:30. Read from `.git/HEAD` and the branch ref;
  **no git command was run**, because `AGENTS.md` bans them.
- **Everything since that commit is uncommitted.** Parts 25-28 and the files written
  on Oct 6 exist only in the working tree. `git status` was not run; 28.12 is the
  task that records the tree state.

## What Is Deployed

From `docs/deployed-check/README.md`, written by a live run on **2026-10-05T17:15Z**.
Read from that file -- **not re-run today**.

| Origin | State |
| --- | --- |
| Cloud Run `https://main-project-888645637790.asia-south1.run.app` | `/health` 200. `/api/version` 404 -- the serving revision predates the route. |
| `https://project-drishti.pages.dev` | Reaches the API; its `api-config.js` names the Cloud Run origin, and the upload was answered 422 with a matching allow-origin. |
| `https://project-drishti.tech` | Cannot reach the API. Its `api-config.js` bakes in an empty base URL so the page issues 0 requests, and the serving revision's `CORS_ORIGINS` allowlists `http://project-drishti.tech`, not `https://`. **Both fixes are user-side deployment settings.** |
| GitHub Pages | Two `github.io` origins sit in the deployed allowlist, but nothing in this repository publishes there. Unconfirmed. |

## What Is Verified

- **`scripts/check-all.ps1` exits 0, 4 of 4 stages** (re-run today): backend
  `7841 passed, 4 skipped`; frontend `720 pass, 0 fail`; `npm run build` and
  `check-artefacts` (28 artefacts) both clean.
- **22 environment variables, listed once.** README `## Environment variables`
  carries two tables -- four frontend-build rows and eighteen backend rows -- each
  with the function that reads it, its status, and the value it ships as.
  `.env.example` carries the same 22 names in copy-pasteable form; `backend` and
  `frontend` README point at the README table rather than repeating it.
- **The contract test is held to its red state.** A variable added to
  `.env.example` alone (`DRISHTI_MUTANT_CHECK`) was reported as listed in one file
  and not the other, and green again once the file was restored.
- **The cascade is Tier 0 only.** `backend/app/screening.py:83-85` registers one
  runner, `run_tier0`, and `CASCADE` at line 90 is `tuple(_TIER_RUNNERS)`. Tier 1,
  Tier 2 and `crossdoc` are unreachable from `POST /api/screenings`.
- **`tasks.md` holds 345 boxes: 338 checked, 7 unchecked** -- `4.7`, which is
  parked, and `28.7` through `28.12`.
- **CI mirrors the local stages.** `.github/workflows/ci.yml` runs two jobs,
  `backend` and `frontend`, the latter covering test, build and the artefact check.
- **The browser evidence is committed:** `docs/viewport-shots/` (41 files),
  `docs/theme-shots/` (21), `docs/private-check/` (1), `docs/deployed-check/` (1).
- **The latest recorded decision is D231** (`docs/DECISIONS.md`).
- **No identity claim is possible from this build.** Every number is drawn only
  beside its synthetic dataset and nothing on the results page is a measurement
  about a real document.

## Known Issues / Blockers -- what is not verified

- **4.7 is `[BLOCKED]` with no blocker recorded.** It is the only unfinished task
  outside Part 28, it sits at line 377, and its box carries no note saying what
  stopped it. Either finish it or say why it is parked.
- **The upload flow has no entry point.** `frontend/dist/` holds no
  `screening.html`, and `frontend/home.test.cjs:17` pins `href="./screening.html"`.
  The full screening flow has never been driven in a browser (25.11, `[BLOCKED]`).
- **No history row has been drawn in a browser.** Without `alembic upgrade head` the
  screen reads *Could not load the history*.
- **The Results page has never been opened in a browser.** Its table is proved by
  driving `draw()` over the committed file, which is not the same thing.
- **The container image has never been built here.** `docker`, `podman`, `gcloud`
  and `gh` are all absent from PATH. 26.1 is `[BLOCKED]`; 26.2 is checked, but its
  two live cases skip for the same reason.
- **CI has never run green** -- it needs GitHub's runner, and the Oct 6 work was
  never pushed.
- **Cloud Run settings are unproven live.** `backend/cloudrun.yaml` is documented
  and statically tested; there is no `gcloud` here to read the running revision.
- **Running the API writes `backend/drishti.db`**, which
  `test_alembic_migration.py:423` and `test_traveler_case.py:257-258` assert absent.
- **The env contract compares names and statuses, not prose.** A row whose reader or
  shipped value has gone stale is outside what the test can see.
- **The sandbox rejected every sandboxed command this session** (deny-read ACL on
  exec, reparse-point error on the patch tool), so all reads and writes went through
  escalated PowerShell.

## Current State & Key Decisions

- **One list of environment variables, and a test that holds it.** The README table
  is the index, `.env.example` is the copy-pasteable mirror, and
  `test_env_reference_contract.py` fails on any difference in names, on any
  disagreement about a variable's status, or on a variable the backend or the build
  reads and neither file names (D231).
- **`DRISHTI_STATION_LABEL` and `STATION_LABEL` are different variables.** The
  first is live in the frontend build and names the station a deployed page shows;
  the second is planned for the backend audit actor (tasks 10.7 and 23.12). Neither
  reads the other.
- **The two labels are strict.** *Measured* means observed by running this build, or
  read from a committed generated file the served page loads verbatim. *Designed*
  means read from source -- true of the build, never an observation, never a
  performance result.
- **A claim points at an evidence file or is labelled designed.** The README quotes
  no number of its own.
- **Unchanged from earlier.** A rate with no denominator is `--`, never a zero;
  `evaluate` scores over four disjoint denominators; every Tier 2 module ships
  `is_stub=True`.

## Immediate Next Step

- **28.7** -- Document the local run path for both halves: backend on 8080,
  frontend built and served, and the allowed localhost origins. Every variable it
  touches is already named in the README table, and no local setup needs one.