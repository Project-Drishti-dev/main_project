"""The ``/api/screenings`` resource: one upload in, one screening back out.

``POST`` is the HTTP boundary the cascade is reached through, so it does what
every boundary here does: read the upload, refuse what
:func:`app.analysis.read_uploaded_image` refuses, hand the frame to
:func:`app.screening.run_screening`, and answer with the two ids rather than
with a result.  ``GET`` on the collection is the history read, filtered and
paged by 11.3; ``GET`` on the item is one stored result, read back off the
row the create left and nothing recomputed except the terms, which the row
holds the two halves of.  Rationale in ``docs/DECISIONS.md`` D71 to D73.

``POST /api/screenings/{id}/decision`` is 18.1: the choice an officer makes,
taken at a URL and refused in the same envelope, and since 18.2 the band it was
shown beside refuses a choice the officer has not claimed as their own.  Since 18.3 a taken choice reaches the trail as an event of
its own, with the override beside it, and since 18.4 a second choice is
answered rather than overwriting the first -- it is a new event naming the one
it took over from, and the answer reports the record and where it stands.

``DELETE /api/screenings/{id}`` is 18.5: the delete 24.5's confirmation takes,
which stamps 8.15's column and removes nothing.  The repository already refuses
a deleted row to every read, so this route is the URL that reaches that rule --
and the answer names the id and the stamp, because those two are the whole of
what it did.  Rationale in ``docs/DECISIONS.md`` D147.

``GET /api/screenings/{id}/report`` is 18.9: the same row as one printable
page, carrying the band, the findings, the reason each rule wrote and the
audit id, and referencing nothing a printer has to fetch.  The page itself
is app.reporting; this route reads the row and the audit id beside it and
answers with the document.  Rationale in ``docs/DECISIONS.md`` D150.

"""

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.analysis import read_uploaded_image
from app.api import get_sessions
from app.api.rate_limit import enforce_analysis_rate_limit
from app.audit.decision import (
    DECISION_CURRENT,
    OFFICER_ACTIONS,
    SUPERSEDES_KEY,
    override_required,
    record_officer_decision,
)
from app.audit.trail import completed_event_id
from app.config import MAX_UPLOAD_BYTES
from app.errors import APIError
from app.logging_config import log_event
from app.progress import build_stage_trace
from app.reporting import render_report
from app.risk.flags import FlagValueError
from app.risk.weightsets.loader import WeightsetError, load_weightset
from app.schemas import (
    DecisionRequest,
    DecisionResponse,
    ErrorResponse,
    ScreeningCreatedResponse,
    ScreeningDeletedResponse,
    ScreeningListResponse,
    ScreeningResultResponse,
)
from app.screening import run_screening, screening_contributions
from app.storage.repository import ScreeningRepository

__all__ = [
    "DEFAULT_DOCUMENT_TYPE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "router",
]

logger = logging.getLogger(__name__)

#: What a row carries when the caller sent no claim of its own.  Text, not
#: ``None`` -- the column is required -- and a statement about the upload
#: rather than a kind of document, so it imposes no vocabulary on the words a
#: caller does send (``D16``).
DEFAULT_DOCUMENT_TYPE = "unspecified"

#: Rows a list answer holds when the caller names no page size, and the most
#: it will hold when it does.  The ceiling is a bound rather than a policy:
#: 11.8's rate limit and 26.3's instance settings are the ones that decide how
#: much a read may cost, and a page nobody may bound is neither.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200

router = APIRouter(prefix="/api", tags=["screenings"])

#: How the report route names the shared error envelope in its own document.
#: The one route here that answers HTML cannot use the model spelling the
#: others use: FastAPI takes an additional response's media type from the
#: route's own response class, which would document this JSON envelope as a
#: page of HTML.  The pointer is what the envelope is, and the case below is
#: what holds it (D150).
ERROR_ENVELOPE_RESPONSE = {
    "description": "The shared error envelope, in JSON.",
    "content": {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
        }
    },
}

@router.post(
    "/screenings",
    response_model=ScreeningCreatedResponse,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_screening(
    image: UploadFile | None = File(default=None),
    mode: str = Form(default="auto"),
    document_type: str = Form(default=DEFAULT_DOCUMENT_TYPE),
    _within_rate_limit: None = Depends(enforce_analysis_rate_limit),
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """Screen one upload and answer with the row and the event beside it.

    :param image: the uploaded frame, in the same multipart shape
        ``/api/analyze`` accepts.
    :param mode: the caller's capture claim, accepted for that shared shape
        and checked against the same vocabulary.  **Not stored**:
        :attr:`app.storage.models.Screening.mode` is the quality gate's own
        reading, which 14.3 runs and writes.
    :param document_type: the caller's claim about the document, stored on
        the row and handed to the tiers as a claim.  Blank is refused rather
        than stored, so a row always carries the words a caller sent.
    :param _within_rate_limit: 11.8's guard, ahead of the session factory
        so a refused request never opens one.
    :param sessions: the factory every write below goes through.
    :returns: ``screening_id`` and ``audit_id`` -- the row, and the one
        ``analysis_completed`` event beside it.  Nothing else: the result is
        11.2's answer, from the screening id.
    :raises APIError: 422 without an image, whatever
        :func:`app.analysis.read_uploaded_image` refuses, 422 for a blank
        document type, 429 once the caller's address has spent its budget,
        and 500 with a generic message for anything else.
    """
    if image is None:
        raise APIError(422, "IMAGE_REQUIRED", "Choose an image to screen.")
    if not document_type.strip():
        raise APIError(
            422,
            "INVALID_DOCUMENT_TYPE",
            "Name the kind of document, or leave it unset.",
        )

    try:
        contents = await image.read(MAX_UPLOAD_BYTES + 1)
        frame = read_uploaded_image(contents, image.content_type, mode)
        return await run_in_threadpool(
            _screen,
            sessions,
            frame,
            document_type.strip(),
            image.filename or "",
        )
    except APIError:
        raise
    except Exception:
        log_event(logger, "screening_failed", level=logging.ERROR, exc_info=True)
        raise APIError(
            500,
            "SCREENING_FAILED",
            "The document could not be screened. Please try again.",
        ) from None
    finally:
        await image.close()


@router.get(
    "/screenings",
    response_model=ScreeningListResponse,
    responses={422: {"model": ErrorResponse}},
)
def list_screenings(
    band: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """Answer with one page of the screenings every given filter matches.

    Synchronous, so FastAPI reaches it in a threadpool: the page is read
    through a session, which does not belong on the event loop.

    :param band: the band to filter on, as a stage stored it.  Omitted
        filters for no band at all, and neither this nor ``document_type``
        is checked against a vocabulary: a name no row carries is an empty
        page.  The rows nothing has scored are not addressable here, since
        their band is ``None`` rather than a name.
    :param document_type: the kind of document to filter on, as the upload
        claimed it.
    :param created_after: the inclusive first instant of the range, or
        omitted to leave the beginning open.
    :param created_before: the inclusive last instant, or omitted to leave
        the end open.
    :param offset: how many of the matched rows to skip.
    :param limit: how many of the matched rows to hold, between one and
        :data:`MAX_PAGE_SIZE`.
    :param sessions: the factory the page is read through.
    :returns: ``items`` -- one row per screening, carrying six of the stored
        columns -- beside the ``total`` that matched and the ``offset`` and
        ``limit`` the page was taken with.
    :raises APIError: 422 for a range the storage layer refuses -- a bound
        carrying no offset, or ends the wrong way round -- and 422 for a
        bound describing no page, which ``ge``/``le`` answer before any
        query is emitted.  Nothing read off a document is echoed back.
    """
    try:
        page = ScreeningRepository(sessions).list_matching(
            band=band,
            document_type=document_type,
            start=created_after,
            end=created_before,
            offset=offset,
            limit=limit,
        )
    except ValueError:
        raise APIError(
            422,
            "INVALID_DATE_RANGE",
            "Give the range as instants carrying a UTC offset, earliest "
            "first.",
        ) from None

    return {
        "items": [
            {
                "screening_id": row.id,
                "status": row.status,
                "document_type": row.document_type,
                "created_at": row.created_at,
                "score": row.score,
                "band": row.band,
            }
            for row in page.rows
        ],
        "total": page.total,
        "offset": page.offset,
        "limit": page.limit,
    }


@router.get(
    "/screenings/{screening_id}",
    response_model=ScreeningResultResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def read_screening(
    screening_id: uuid.UUID,
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """Answer with the whole stored screening, read off its own row.

    Synchronous, so FastAPI reaches it in a threadpool: the row is read
    through a session and the weightset off the package's files, and
    neither belongs on the event loop.

    :param screening_id: the id ``POST /api/screenings`` answered with.
    :param sessions: the factory the row is read through.
    :returns: the row's own score, band, ruleset version, findings and
        narrative, with the per-flag terms the score was summed from and
        the stage trace naming what each stage cost (18.12).
    :raises APIError: 404 for an id no live row carries, and 500 with a
        generic message for a row whose terms cannot be rebuilt -- a
        weightset that is not the one the row was scored under, or a stored
        finding that is not one.  Nothing internal is echoed back.
    """
    row = ScreeningRepository(sessions).get(screening_id)
    if row is None:
        raise APIError(
            404,
            "SCREENING_NOT_FOUND",
            "That screening could not be found.",
        )

    try:
        contributions = screening_contributions(row, load_weightset())
    except (FlagValueError, WeightsetError):
        log_event(
            logger,
            "screening_unreadable",
            level=logging.ERROR,
            exc_info=True,
            screening_id=str(screening_id),
        )
        raise APIError(
            500,
            "SCREENING_UNREADABLE",
            "This result could not be read. Please try again later.",
        ) from None

    return {
        "screening_id": row.id,
        "status": row.status,
        "document_type": row.document_type,
        "created_at": row.created_at,
        "image": {"width": row.image_width, "height": row.image_height},
        "score": row.score,
        "band": row.band,
        "ruleset_version": row.ruleset_version,
        "model_versions": row.model_versions,
        "summary": row.summary,
        "flags": [flag for flag in (row.flags or [])],
        "stage_trace": build_stage_trace(row, sessions=sessions).document(),
        "contributions": [
            dataclasses.asdict(term) for term in contributions
        ],
    }


@router.get(
    "/screenings/{screening_id}/report",
    response_class=HTMLResponse,
    responses={
        404: ERROR_ENVELOPE_RESPONSE,
        422: ERROR_ENVELOPE_RESPONSE,
    },
)
def read_screening_report(
    screening_id: uuid.UUID,
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> HTMLResponse:
    """Answer with the printable report for one screening, as one page.

    Synchronous, so FastAPI reaches it in a threadpool: the row and the
    trail beside it are read through sessions, which do not belong on the
    event loop.

    :param screening_id: the id ``POST /api/screenings`` answered with.
    :param sessions: the factory both of the reads below go through.
    :returns: one complete HTML document referencing no external asset --
        app.reporting builds the page, and this route reads the row and
        the audit id it is handed (18.9, D150).
    :raises APIError: 404 for an id no live row carries, which is 11.2's
        own answer for the same id on the same repository read.  422 is
        the envelope's and 500 is the service's; nothing read off the
        document is echoed into either.
    """
    row = ScreeningRepository(sessions).get(screening_id)
    if row is None:
        raise APIError(
            404,
            "SCREENING_NOT_FOUND",
            "That screening could not be found.",
        )
    return HTMLResponse(
        render_report(
            row, audit_id=completed_event_id(row.id, sessions=sessions)
        )
    )


@router.delete(
    "/screenings/{screening_id}",
    response_model=ScreeningDeletedResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def delete_screening(
    screening_id: uuid.UUID,
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """Stamp one live screening deleted, and answer with the stamp.

    Synchronous, so FastAPI reaches it in a threadpool: the row is written
    through a session, which does not belong on the event loop.

    :param screening_id: the id ``POST /api/screenings`` answered with.
    :param sessions: the factory the row is written through.
    :returns: the id, and the instant it was stamped -- the whole of what
        this did, since 8.15 removed nothing.  Nothing read off the document
        is here: no score, no band and no finding.
    :raises APIError: 404 for an id no *live* row carries.  An id no row
        carries and one already deleted are the same answer, so a second
        delete is a 404 rather than a second stamp (D147).
    """
    row = ScreeningRepository(sessions).soft_delete(
        screening_id, deleted_at=datetime.now(timezone.utc)
    )
    if row is None:
        raise APIError(
            404,
            "SCREENING_NOT_FOUND",
            "That screening could not be found.",
        )

    return {"screening_id": row.id, "deleted_at": row.deleted_at}


@router.post(
    "/screenings/{screening_id}/decision",
    response_model=DecisionResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def record_decision(
    screening_id: uuid.UUID,
    decision: DecisionRequest,
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> dict[str, Any]:
    """Take the choice an officer made, and answer with what was taken.

    Synchronous, so FastAPI reaches it in a threadpool: the row is read
    through a session, and a session does not belong on the event loop.

    :param screening_id: the row the choice was made on.
    :param decision: the choice, the remark and the override flag.
    :param sessions: the factory the row is read through, and the factory the
        choice is written through.
    :returns: the four values the request named, and nothing read off the
        document -- no score, no band and no finding.  **The choice reaches
        the trail first**, through the module that owns the override rather
        than through a second spelling of it here (18.3, D145), and the
        answer then names the record it was written to, where that record
        stands, and the choice it took over from -- three fields beside 18.1's
        four, none of which replaces one (18.4, D146).
    :raises APIError: 422 for a choice outside the officer's own three, which
        are read off the constants rather than spelled here (D70), 422 again
        when the adverse choice contradicts the band the row was scored at and
        the officer did not claim it (18.2, D144), and 404 for an id no live
        row carries.
    """
    if decision.action not in OFFICER_ACTIONS:
        raise APIError(
            422,
            "INVALID_DECISION_ACTION",
            "Choose one of " + ", ".join(OFFICER_ACTIONS) + ".",
        )
    row = ScreeningRepository(sessions).get(screening_id)
    if row is None:
        raise APIError(
            404,
            "SCREENING_NOT_FOUND",
            "That screening could not be found.",
        )
    if not decision.override and override_required(row.band, decision.action):
        raise APIError(
            422,
            "DECISION_OVERRIDE_REQUIRED",
            "This choice goes against the band on this screening. Send override "
            "true to record it as your own.",
        )
    recorded, _ = record_officer_decision(
        row.id,
        system_band=row.band,
        officer_action=decision.action,
        remark=decision.remark,
        override=decision.override,
        sessions=sessions,
        ruleset_version=row.ruleset_version,
        model_versions=row.model_versions,
    )
    return {
        "screening_id": row.id,
        "action": decision.action,
        "remark": decision.remark,
        "override": decision.override,
        "decision_id": recorded.id,
        "status": DECISION_CURRENT,
        "supersedes": recorded.payload.get(SUPERSEDES_KEY),
    }


def _screen(
    sessions: sessionmaker[Session],
    frame: Any,
    document_type: str,
    filename: str,
) -> dict[str, uuid.UUID]:
    """Run the cascade over one frame and answer the two ids it left.

    Synchronous, so the caller reaches it through ``run_in_threadpool``:
    the flow holds sessions and measures pixels, neither of which belongs on
    the event loop.  The audit id is read back out of the trail rather than
    recomputed, so it is the id of the row ``emit`` stored.

    :returns: ``screening_id`` and ``audit_id``.
    :raises RuntimeError: when a completed screening left no
        ``analysis_completed`` event, which is a fault in the flow rather
        than a request the caller can fix.
    """
    row = run_screening(
        sessions=sessions,
        image=frame,
        document_type=document_type,
        filename=filename,
    )
    audit_id = completed_event_id(row.id, sessions=sessions)
    if audit_id is None:
        raise RuntimeError(
            "a screening that completed wrote no analysis_completed event, "
            "so there is no audit_id to answer with"
        )
    return {"screening_id": row.id, "audit_id": audit_id}
