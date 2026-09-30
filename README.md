# DRISHTI

Hackathon prototype for screening uploaded document images.

## Project structure

- `frontend/` — static UX4G website prototype.
- `backend/` — FastAPI image-quality API for Google Cloud Run. See
  [`backend/README.md`](backend/README.md) for local setup, API contract, and
  deployment notes.
- `lorebook/` — project reference material.

The backend is deployed on Google Cloud Run and the frontend is connected to
it. The frontend sends an uploaded image to `POST /api/analyze` on the API
origin supplied at build time through `DRISHTI_API_BASE_URL`; the origin is not
checked into this repository. The static frontend is published on Cloudflare
Pages and GitHub Pages, and Cloud Run's `CORS_ORIGINS` allowlist must contain
the exact browser origins that serve it.

The checker thresholds are experimental and must not be treated as a
production identity-verification decision. The prototype is unauthenticated:
there is no login, and use synthetic images only.
