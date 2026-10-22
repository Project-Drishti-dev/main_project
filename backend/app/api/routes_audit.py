"""``GET /api/audit/{audit_id}/verify``: whether one record still stands.

18.7's read, and the only route the ``/api/audit`` resource holds so far.  The
answer is 9.17's three words beside the root the walk reached, the length of
the path it walked and one plain sentence per check that completed, so a caller
reading a 200 can tell a clearance from an answer that stopped before it
compared anything.  Nothing read off the document is in it: no payload, no
finding, no score.  Rationale in ``docs/DECISIONS.md`` D149.
"""

import dataclasses
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_ledger, get_sessions
from app.audit.verify import verify_audit_event
from app.ledger.store import Ledger
from app.schemas import AuditVerificationResponse, ErrorResponse

__all__ = ["router"]

router = APIRouter(prefix="/api", tags=["audit"])


@router.get(
    "/audit/{audit_id}/verify",
    response_model=AuditVerificationResponse,
    responses={
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def verify_audit_record(
    audit_id: uuid.UUID,
    sessions: sessionmaker[Session] = Depends(get_sessions),
    ledger: Ledger = Depends(get_ledger),
) -> dict[str, Any]:
    """Answer whether one stored event is still the record the log holds.

    Synchronous, so FastAPI reaches it in a threadpool: the walk reads the row
    and the log through sessions, which do not belong on the event loop.

    :param audit_id: the event id ``POST /api/screenings`` answered with.
    :param sessions: the factory the row is read through.
    :param ledger: the log the anchored root is read back from, reached
        through :func:`app.api.get_ledger` so both are the same database.
    :returns: 9.17's three words, the batch the walk reached, the root it
        read, the length of the proof it walked, and one sentence per check
        that completed.
    :raises APIError: none of this route's own -- 9.17 answers a string or
        nothing, so an id no row carries is 200 and ``unknown`` rather than a
        404, since the question was answerable.  422 covers an id that is not
        a UUID, which the envelope answers before this runs, and 500 is the
        service's own handler for a fault no route caught.  Nothing internal is
        echoed back.
    """
    return dataclasses.asdict(
        verify_audit_event(audit_id, sessions=sessions, ledger=ledger)
    )
