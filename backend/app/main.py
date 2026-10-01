import logging

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .analysis import analyze_uploaded_image
from .api.routes_screenings import router as screenings_router
from .config import MAX_UPLOAD_BYTES, get_cors_origins
from .errors import APIError
from .schemas import AnalysisResponse, ErrorResponse


logger = logging.getLogger(__name__)

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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(screenings_router)


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
async def handle_unexpected_error(_request, exc: Exception) -> JSONResponse:
    """Answer a fault no route caught in the same envelope as every refusal.

    The route-level handlers above are the ones that can say what went
    wrong; this one says only that it did, so the body stays the shape a
    client already parses rather than the server's plain-text 500.
    """
    logger.error("Unhandled request error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The request could not be completed.",
            }
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/analyze",
    response_model=AnalysisResponse,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze(
    image: UploadFile | None = File(default=None),
    mode: str = Form(default="auto"),
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
        logger.exception("Image analysis request failed")
        raise APIError(
            500,
            "ANALYSIS_FAILED",
            "The image could not be analyzed. Please try again.",
        ) from None
    finally:
        await image.close()
