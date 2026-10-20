# DRISHTI image-quality API

This Python API accepts an image, runs the nine quality checks and the available
single-image tier checks, and returns a JSON report for the website. The
in-memory analysis route is designed to deploy independently from the static
frontend to Google Cloud Run.

## Layout

- `app/main.py` — FastAPI routes, CORS, and HTTP error handling.
- `app/analysis.py` — upload validation and in-memory image decoding.
- `app/quality_checker/` — the nine checker modules and API-facing runner.
- `tests/unit/` and `tests/api/` — checker unit tests and API contract tests.
- `tests/deploy/` — the build-and-run check for the container image.
- `main.py` and `Procfile` — Cloud Run buildpack entry points.
- `Dockerfile` and `.dockerignore` — the container build and its build context.

The checker modules in `app/quality_checker/` are a vendored copy of
`D:\SIH\SIH_qualitycheck`. The original checker directory is not modified.
If its algorithms change, copy the intended updates here and rerun these tests
before deploying so the API does not silently use stale checks.

## API

### `GET /health`

Returns `{"status":"ok"}`.

### `POST /api/analyze`

Send `multipart/form-data` with:

- `image`: JPEG, PNG, or WebP image, at most 10 MiB and 20 million pixels.
- `mode`: optional `auto`, `photo`, or `scan`; defaults to `auto`.

Successful response:

```json
{
  "mode": "photo",
  "image": { "width": 1600, "height": 1000 },
  "trim_box": null,
  "overall_pass": false,
  "modules": [
    {
      "module": "sharpness",
      "label": "Sharpness",
      "score": 123.4,
      "unit": "Laplacian variance (higher = sharper)",
      "passed": true,
      "rule": "PASS if ...",
      "reasons": [],
      "details": { "tenengrad": 456.7 },
      "mode": "photo"
    }
  ]
}
```

The response contains all nine module results, plus `tier_checks` summaries for
Tier 0 MRZ-format detection, Tier 1 Tesseract status, and seven Tier 2 modules.
Tier 2 results include `is_stub` and `model_version`; their values are
experimental signals, not authenticity probabilities. Tier 1 may return
`recognized_text` in the non-persistent Overview response. The response also
carries a `tier_notice` explaining that
the Tier 2 modules are prototypes. Internal outline arrays are omitted. Errors
use the same shape:

```json
{
  "error": {
    "code": "INVALID_IMAGE",
    "message": "The uploaded file is empty or is not a supported image."
  }
}
```

`POST /api/analyze` does not persist uploaded images to storage or a database.
Multipart parsing may use framework-managed temporary spooling, which is closed
at the end of the request. `POST /api/screenings` is a separate persisted route;
its database-backed cascade currently runs Tier 0 only. The checks and
thresholds are experimental and are not a production identity-verification
decision.

## Run locally

From this directory, using Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn main:app --reload --port 8080
```

The API will be available at `http://localhost:8080`; interactive API docs are
at `/docs`. In another terminal, run:

```powershell
python -m pytest -q
```

The demo keeps its data in `drishti.db` beside this directory unless `DATABASE_URL`
names another database, so `alembic upgrade head` is what creates the schema
the service then reads. Running it again at every start is safe: a second run
finds the database already at `head` and changes nothing.

By default, CORS allows exactly the six origins in `LOCAL_CORS_ORIGINS`,
`app/config.py`: `localhost` and `127.0.0.1` on ports 5500, 5501 and 5173.
That covers this project's preview server, VS Code Live Server and Vite, so a
local run needs no value at all. Setting `CORS_ORIGINS` *replaces* those six
rather than adding to them, so for a deployed site set it to a comma-separated
list of exact origins, for example `https://your-project.pages.dev`. Do not use
`*`. Nothing in this service reads a `.env` file -- set the variable in the
shell.

Both halves at once, and the table of allowed origins per port, are in the root
[README](../README.md#run-locally).

Every variable this service reads is one table in the root
[README](../README.md#environment-variables) -- reader, status, and the value
it ships as. [`.env.example`](../.env.example) is the same list in
copy-pasteable form, and a test fails if the two disagree.

## Run as a container

`Dockerfile` builds the service into an image and `.dockerignore` keeps the
build context down to what the service reads. From this directory:

```powershell
docker build -t drishti-backend .
docker run --rm -p 8080:8080 drishti-backend
```

The image serves on port 8080, so `GET /health` answers `{"status":"ok"}`
without touching a database. The base image is pinned by digest, so a rebuild
is the same image; to move it, resolve a new digest and change both stages:

```powershell
docker buildx imagetools inspect python:3.13-slim-bookworm
```

The container runs as drishti, a fixed uid 10001 with no login shell, and
/app is chowned to it before the USER switch (26.2).

`docker-entrypoint.sh` is the image ENTRYPOINT: it runs `alembic upgrade head`
and then serves, as that same uid, so a fresh container migrates the SQLite
file it is about to be asked to open. A failed migration stops the boot
rather than serving an unmigrated database.

`python -m pytest tests/deploy -q` builds the image, runs it, and asserts
`/health` answers from inside it. It needs a Docker daemon and skips, with the
reason, where there is none, so a green suite on its own is not evidence the
image works.
## Deploy to Cloud Run

`cloudrun.yaml` holds the service settings, and `cloudbuild.yaml` builds the
image it deploys. Both are applied from this directory:

```powershell
gcloud builds submit --config cloudbuild.yaml
gcloud run services replace cloudrun.yaml --allow-unauthenticated
```

The image migrates itself at start-up, in the container that will open the
database, which is the only place the migration and the service can be one
filesystem. A step in `cloudbuild.yaml` running the migration instead would
migrate a database inside the build, and the revision would still be serving
an empty one.

The three settings this task fixes, and why each is what it is, are documented
in `cloudrun.yaml` itself rather than restated here:

| Setting | Value | Why |
| --- | --- | --- |
| `maxInstanceRequestConcurrency` | `1` | One request at a time per instance. The rate-limit budget (D78) and the Merkle batching window are counted per process, so a second concurrent request would not share them. |
| `scaling.maxInstanceCount` | `2` | A small ceiling on purpose: an unauthenticated public endpoint on a shared project is a cost and abuse bound. `minInstanceCount` is `0`, so an idle demo costs nothing. |
| `timeout` | `600s` | Sized for the cascade: the tier targets plus the summariser's 30 s budget, with room for a cold start and a slow Tier 2 on a shared CPU instance. Below Cloud Run's 60-minute maximum, so a hung request cannot hold the single concurrency slot for an hour. |

`gcloud run services replace` applies the file as written. `gcloud run deploy
--source .` is deliberately not used, because a source deploy writes its own
revision template and would overwrite these settings on the next deploy.

Set `CORS_ORIGINS` on the same command, or as an `env` entry in
`cloudrun.yaml`. `tests/unit/test_cloudrun_config_contract.py` reads the file
and fails if a setting is dropped, left to a platform default, or set below what
the cascade needs.

The public unauthenticated endpoint is intentional for the unauthenticated
prototype browser flow. CORS only controls browser access; it does not stop
direct API requests. Use synthetic images for the public prototype, and do not
treat this endpoint as a secure document-processing service.
After deployment, configure the website to call the service's `/api/analyze`
endpoint and add the website's production origin (and later its custom-domain
origin) to `CORS_ORIGINS`.

Triggering cloud deployment.
