# DRISHTI

Hackathon prototype for screening uploaded document images.

## Project structure

- `frontend/` — static UX4G website prototype.
- `backend/` — FastAPI image-quality API for Google Cloud Run. See
  [`backend/README.md`](backend/README.md) for local setup, API contract, and
  deployment notes.
- `lorebook/` — project reference material.

The backend is implemented but is not deployed or connected to the frontend
yet. The checker thresholds are experimental and must not be treated as a
production identity-verification decision.
