"""``GET /health`` and ``GET /ready``: the two questions a supervisor asks.

Liveness is whether this process answers at all; readiness is whether it can
serve -- the database reachable, the ledger readable.  Splitting them is what
lets an outage take an instance out of rotation without a supervisor
restarting a process that is perfectly alive.

``/health`` opens no session and reads no row, so it answers whatever else is
broken.  ``/ready`` goes through the same overridable session dependency the
write routes do, so a test points it at a database it then makes unreachable.
"""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.errors import APIError
from app.logging_config import log_event
from app.schemas import ErrorResponse, HealthResponse, ReadinessResponse
from app.storage.models import LedgerEntry


logger = logging.getLogger(__name__)

__all__ = ["router"]


def _database_answers(sessions: sessionmaker[Session]) -> None:
    """Prove the database is reachable, with a statement that touches no table.

    :param sessions: the factory the session is opened from.
    :raises Exception: whatever the driver raises when it cannot connect.
    """
    with sessions() as session:
        session.execute(text("SELECT 1"))


def _ledger_reads(sessions: sessionmaker[Session]) -> None:
    """Prove the ledger is readable: the first entry, or the absence of any.

    :param sessions: the factory the session is opened from.
    :raises Exception: whatever SQLAlchemy raises when the table is not there.
    """
    with sessions() as session:
        session.execute(select(LedgerEntry.batch_id).limit(1))


#: What a ready process has proved, in the order it proved it.  The route
#: runs each and names the one that failed, so the answer, the log line and
#: the refusal all read the same list rather than three copies of it.
CHECKS: tuple[tuple[str, Callable[[sessionmaker[Session]], None]], ...] = (
    ("database", _database_answers),
    ("ledger", _ledger_reads),
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Answer that the process is up, without asking it to do anything."""
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ErrorResponse}},
)
def ready(
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """Answer that the process can serve, or refuse in the one error envelope.

    Synchronous, so FastAPI reaches it in a threadpool: a session does not
    belong on the event loop, and this is the endpoint a load balancer calls
    precisely when the process is already under strain.

    :param sessions: the factory both checks open theirs from.
    :returns: ``status`` and the ``checks`` that were run.
    :raises ~app.errors.APIError: 503, naming the first check that failed.
    """
    for name, check in CHECKS:
        try:
            check(sessions)
        except Exception:
            log_event(
                logger,
                "readiness_check_failed",
                level=logging.WARNING,
                exc_info=True,
            )
            raise APIError(
                503,
                "NOT_READY",
                f"The service is not ready: {name} is unreachable.",
            ) from None
    return {"status": "ready", "checks": [name for name, _ in CHECKS]}