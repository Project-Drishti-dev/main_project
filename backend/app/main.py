import logging

from fastapi import Depends, FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .analysis import analyze_uploaded_image
from .api.request_id import REQUEST_ID_HEADER, RequestIdMiddleware, stamp_request_id
from .api.rate_limit import RateLimiter, enforce_analysis_rate_limit
from .api.request_logging import RequestLoggingMiddleware
from .api.routes_audit import router as audit_router
from .api.routes_health import router as health_router
from .api.routes_progress import router as progress_router
from .api.routes_screenings import router as screenings_router
from .api.routes_version import router as version_router
from .config import MAX_UPLOAD_BYTES, get_cors_origins, get_rate_limit_per_minute
from .errors import APIError
from .logging_config import bind_request_id, configure_logging, log_event
from .schemas import AnalysisResponse, ErrorResponse


logger = logging.getLogger(__name__)

# The one JSON handler for everything logged beneath ``app``, read from
# ``LOG_LEVEL`` at import.  Idempotent, so a session that imports this
# module many times over does not attach a handler each time.
configure_logging()

app = FastAPI(
    title="DRISHTI Image Quality API",
    description="Runs the nine DRISHTI image-quality checks on an uploaded image.",
    version="0.1.0",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", REQUEST_ID_HEADER],
    # The id is the caller's to read, and a browser cannot read a response
    # header the origin has not been told is exposed.
    expose_headers=[REQUEST_ID_HEADER],
)
# Added after the CORS middleware, so it wraps it: a preflight the CORS
# middleware answers on its own is stamped like any other answer.
app.add_middleware(RequestLoggingMiddleware)
# Added last, so it is the outermost of the three: the logging middleware
# reads the id this one stamps, rather than the inbound header, and never
# mints a second one (D76).
app.add_middleware(RequestIdMiddleware)
app.include_router(audit_router)
app.include_router(health_router)
app.include_router(progress_router)
app.include_router(screenings_router)
app.include_router(version_router)

# The one budget every analysis request spends, built from the configured
# limit at import and read per request (11.8).  It lives on the app rather
# than in a module global so a test can put a smaller one -- and a clock it
# controls -- in its place without the guard itself being swapped out.
app.state.rate_limiter = RateLimiter(get_rate_limit_per_minute())


@app.exception_handler(APIError)
async def handle_api_error(_request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    _request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "The request payload is invalid.",
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request, exc: Exception) -> JSONResponse:
    """Answer a fault no route caught in the same envelope as every refusal.

    The route-level handlers above are the ones that can say what went
    wrong; this one says only that it did, so the body stays the shape a
    client already parses rather than the server's plain-text 500.
    """
    # The binding is re-entered here rather than read off the scope directly:
    # ServerErrorMiddleware runs this handler outside every user middleware, so
    # the request-id binding the logging middleware held is already unwound by
    # the time this line is written (D76).
    with bind_request_id(request.state.request_id):
        log_event(
            logger,
            "unhandled_request_error",
            level=logging.ERROR,
            exc_info=exc,
        )
    # Starlette builds this answer outside the middleware stack, so it never
    # passes back through the request-id middleware and is stamped here from
    # the id the request already carries.
    return stamp_request_id(
        JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The request could not be completed.",
                }
            },
        ),
        request,
    )


@app.post(
    "/api/analyze",
    response_model=AnalysisResponse,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze(
    image: UploadFile | None = File(default=None),
    mode: str = Form(default="auto"),
    _within_rate_limit: None = Depends(enforce_analysis_rate_limit),
) -> dict:
    if image is None:
        raise APIError(422, "IMAGE_REQUIRED", "Choose an image to analyze.")

    try:
        contents = await image.read(MAX_UPLOAD_BYTES + 1)
        return await run_in_threadpool(
            analyze_uploaded_image,
            contents,
            image.content_type,
            mode,
        )
    except APIError:
        raise
    except Exception:
        log_event(logger, "analysis_failed", level=logging.ERROR, exc_info=True)
        raise APIError(
            500,
            "ANALYSIS_FAILED",
            "The image could not be analyzed. Please try again.",
        ) from None
    finally:
        await image.close()

