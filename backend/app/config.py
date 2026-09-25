import os


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

LOCAL_CORS_ORIGINS = (
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5501",
    "http://127.0.0.1:5501",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")
    if configured_origins is None:
        return list(LOCAL_CORS_ORIGINS)

    origins = list(
        dict.fromkeys(
            origin.strip().rstrip("/")
            for origin in configured_origins.split(",")
            if origin.strip()
        )
    )
    if "*" in origins:
        raise ValueError("CORS_ORIGINS must list exact origins; '*' is not allowed.")
    return origins
