"""The two routes that answer what one screening's run recorded.

``.../progress/stream`` is 18.10: one server-sent event per step, ending on a
single ``done`` rather than waiting for a caller to hang up.
``.../progress`` is 18.11: the same sequence as one JSON object, for a caller
that cannot hold a connection open -- a proxy that buffers a response, or a
client with no event stream at all.

**Both are transports over one read.**  A screening is screened synchronously,
so neither watches a run in flight; both answer what the finished run left
behind, and both go through :func:`build_progress`, so there is one place that
builds the sequence and one spelling of a step.  The document carries the
frames' own objects under the same keys in the same order, and its units is
what the done frame reports -- which is the whole of what 18.11 asserts, and
is asserted by comparing the two answers rather than by either one alone.

:mod:`app.progress` owns the sequence and the wire spelling; this module reads
the row, refuses an id no live row carries, and hands the answer over.
Rationale in ``docs/DECISIONS.md`` D151, D152.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.errors import APIError
from app.progress import build_progress
from app.schemas import ErrorResponse, ScreeningProgressResponse
from app.storage.models import Screening
from app.storage.repository import ScreeningRepository

__all__ = ["router"]

router = APIRouter(prefix="/api", tags=["progress"])


def _screening_or_404(
    screening_id: uuid.UUID, sessions: sessionmaker[Session]
) -> Screening:
    """The screening both routes answer about, or the refusal they share.

    :param screening_id: the id ``POST /api/screenings`` answered with.
    :param sessions: the factory the row is read through.
    :returns: the live row.
    :raises APIError: 404 for an id no live row carries -- 11.2's own answer
        for the same id on the same repository read, held here so the two
        routes make one refusal rather than each holding its own.
    """
    row = ScreeningRepository(sessions).get(screening_id)
    if row is None:
        raise APIError(
            404,
            "SCREENING_NOT_FOUND",
            "That screening could not be found.",
        )
    return row


@router.get(
    "/screenings/{screening_id}/progress/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "The stream, as text/event-stream.  Each frame is one named"
                " event carrying one JSON object; the endpoint's docstring is"
                " where the five keys of a progress event are written down,"
                " since a frame is not a document a schema can hold.  The"
                " same sequence is one JSON object at .../progress."
            ),
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def stream_screening_progress(
    screening_id: uuid.UUID,
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> StreamingResponse:
    """Stream one screening's recorded progress, one server-sent event a step.

    Synchronous, so FastAPI reaches it in a threadpool: the row and the trail
    beside it are read through sessions, which do not belong on the event
    loop.  **Both reads finish before the first byte is written**, so an id no
    live row carries is a 404 in the shared envelope rather than an error
    pushed down a stream a caller has already started reading -- and the
    frames themselves only format what was read, so no session is held open
    for as long as the caller reads.

    :param screening_id: the id ``POST /api/screenings`` answered with.
    :param sessions: the factory both of the reads above go through.
    :returns: ``text/event-stream`` -- one ``progress`` event per recorded
        tier and per module that reported, then exactly one ``done``.  No
        frame carries anything read off the document: no finding, no value,
        no score and no filename.
    :raises APIError: 404 for an id no live row carries, which is 11.2's own
        answer for the same id on the same repository read.  422 is the
        envelope's and 500 is the service's.
    """
    row = _screening_or_404(screening_id, sessions)
    report = build_progress(row, sessions=sessions)
    return StreamingResponse(report.frames(), media_type="text/event-stream")


@router.get(
    "/screenings/{screening_id}/progress",
    response_model=ScreeningProgressResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def get_screening_progress(
    screening_id: uuid.UUID,
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """One screening's recorded progress, as the whole sequence at once.

    The answer for a caller that cannot read a stream, and it is the sequence
    the stream carries: the same five keys per step, in the same order, and
    the step count under the name the done frame reports it as.  Nothing here
    is read back off the frames, so the two routes cannot be made to disagree
    by one of them changing.

    **There is no completeness flag and that is deliberate.**  Screening is
    synchronous, so a row read here is a run that has already finished and
    every step it will ever have is in this answer; a flag saying so would
    be a claim the stored records cannot support.  A caller polling for a run
    still in flight is waiting for something no task in this repository
    stores yet (D151).

    :param screening_id: the id ``POST /api/screenings`` answered with.
    :param sessions: the factory the row and the trail are read through.
    :returns: the document -- ``screening_id``, ``units`` and
        ``events``.  A row no stage has run on carries an empty
        ``events`` and a ``units`` of zero, which is the done frame on its own.
    :raises APIError: 404 for an id no live row carries, the stream route's
        own refusal.  422 is the envelope's and 500 is the service's.
    """
    row = _screening_or_404(screening_id, sessions)
    return build_progress(row, sessions=sessions).snapshot()
