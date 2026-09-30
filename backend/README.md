# DRISHTI image-quality API

This Python API accepts an image, runs the nine quality checks, and returns a
JSON report for the website. It is designed to deploy independently from the
static frontend to Google Cloud Run.

## Layout

- `app/main.py` — FastAPI routes, CORS, and HTTP error handling.
- `app/analysis.py` — upload validation and in-memory image decoding.
- `app/quality_checker/` — the nine checker modules and API-facing runner.
- `tests/unit/` and `tests/api/` — checker unit tests and API contract tests.
- `main.py` and `Procfile` — Cloud Run buildpack entry points.

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

The response contains all nine module results, including `rule`, `reasons`,
and `details`. Internal outline arrays are intentionally omitted. Errors use
the same shape:

```json
{
  "error": {
    "code": "INVALID_IMAGE",
    "message": "The uploaded file is empty or is not a supported image."
  }
}
```

The API does not persist uploaded images to storage or a database. Multipart
parsing may use framework-managed temporary spooling, which is closed at the
end of the request. The checker thresholds are still experimental; results
are suitable for a prototype, not as a production identity-verification
decision.

## Run locally

From this directory, using Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn main:app --reload --port 8080
```

The API will be available at `http://localhost:8080`; interactive API docs are
at `/docs`. In another terminal, run:

```powershell
python -m pytest -q
```

By default, CORS allows the common localhost Live Server and Vite origins.
For a deployed site, set `CORS_ORIGINS` to a comma-separated list of exact
origins, for example `https://your-project.pages.dev`. Do not use `*`.

## Deploy to Cloud Run

From this directory, deploy the source with the Google Cloud CLI:

```powershell
gcloud run deploy drishti-quality-api `
  --source . `
  --region asia-south1 `
  --allow-unauthenticated `
  --set-env-vars "CORS_ORIGINS=https://your-project.pages.dev"
```

The public unauthenticated endpoint is intentional for the unauthenticated
prototype browser flow. Before exposing it, set a small maximum instance
count, one request per instance at a time, and a request timeout appropriate
for image analysis in Cloud Run settings. CORS only controls browser access;
it does not stop direct API requests. Use synthetic images for the public
prototype, and do not treat this endpoint as a secure document-processing
service.

After deployment, configure the website to call the service's `/api/analyze`
endpoint and add the website's production origin (and later its custom-domain
origin) to `CORS_ORIGINS`.
