"""The ``/api/screenings`` resource: one upload in, one screening back out.

``POST`` is the HTTP boundary the cascade is reached through, so it does what
every boundary here does: read the upload, refuse what
:func:`app.analysis.read_uploaded_image` refuses, hand the frame to
:func:`app.screening.run_screening`, and answer with the two ids rather than
with a result.  ``GET`` on the collection is the history read, filtered and
paged by 11.3; ``GET`` on the item is one stored result, read back off the
row the create left and nothing recomputed except the terms, which the row
holds the two halves of.  Rationale in ``docs/DECISIONS.md`` D71 to D73.
"""

import dataclasses
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.analysis import read_uploaded_image
from app.api import get_sessions
from app.audit.trail import completed_event_id
from app.config import MAX_UPLOAD_BYTES
from app.errors import APIError
from app.risk.flags import FlagValueError
from app.risk.weightsets.loader import WeightsetError, load_weightset
from app.schemas import (
    ErrorResponse,
    ScreeningCreatedResponse,
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


@router.post(
    "/screenings",
    response_model=ScreeningCreatedResponse,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_screening(
    image: UploadFile | None = File(default=None),
    mode: str = Form(default="auto"),
    document_type: str = Form(default=DEFAULT_DOCUMENT_TYPE),
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
    :param sessions: the factory every write below goes through.
    :returns: ``screening_id`` and ``audit_id`` -- the row, and the one
        ``analysis_completed`` event beside it.  Nothing else: the result is
        11.2's answer, from the screening id.
    :raises APIError: 422 without an image, whatever
        :func:`app.analysis.read_uploaded_image` refuses, 422 for a blank
        document type, and 500 with a generic message for anything else.
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
        logger.exception("Screening request failed")
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
        narrative, with the per-flag terms the score was summed from.
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
        logger.exception("Screening %s could not be read back", screening_id)
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
        "contributions": [
            dataclasses.asdict(term) for term in contributions
        ],
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
