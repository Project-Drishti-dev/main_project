"""``GET /api/version``: the versions this deployment answers with.

Four values, read off :mod:`app.version` per request rather than bound at
import, so the endpoint cannot answer with a version the module has moved
past.  The read spends no rate-limit budget (D78) and opens no session.
"""

from typing import Any

from fastapi import APIRouter

from app import version
from app.schemas import VersionResponse

__all__ = ["router"]

router = APIRouter(prefix="/api", tags=["version"])


@router.get("/version", response_model=VersionResponse)
async def read_version() -> dict[str, Any]:
    """Answer what :mod:`app.version` holds, and nothing else."""
    return {
        "app_version": version.APP_VERSION,
        "ruleset_version": version.RULESET_VERSION,
        "model_versions": dict(version.MODEL_VERSIONS),
        "prompt_version": version.PROMPT_VERSION,
    }