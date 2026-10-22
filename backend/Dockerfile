# syntax=docker/dockerfile:1
#
# The service as an image, in two stages.
#
#   builder  resolves requirements.txt into a self-contained virtualenv, so
#            pip, its cache and every build tool stay in a layer the runtime
#            never copies from.
#   runtime  carries that virtualenv and the source the service reads, runs as
#            a non-root user, and nothing else.
#
# The base image is pinned by digest, not only by tag: `3.13-slim-bookworm`
# floats across patch releases, so the digest is what makes a rebuild the same
# image. Resolved from Docker Hub on 2026-10-05. Both stages name the same
# digest, because a virtualenv built by one interpreter cannot be copied into
# an image built on another.

FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies are installed before the source is copied, so editing a module
# rebuilds this layer from cache instead of resolving every wheel again.
WORKDIR /build
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
 && python -m pip install -r requirements.txt


FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

WORKDIR /app

# The account the service runs as, with a uid and gid fixed here rather than
# inherited from the base image, so what the process is does not change when an
# upstream image does. It has no home directory and a nologin shell: the
# account serves HTTP and never logs in.
RUN groupadd --gid 10001 drishti \
 && useradd --uid 10001 --gid 10001 --no-create-home \
            --shell /usr/sbin/nologin drishti

COPY --from=builder /opt/venv /opt/venv

# What the service reads: the ASGI entry point, the package, the migration
# environment beside it, and the start command that migrates before serving.
COPY alembic.ini main.py ./
COPY docker-entrypoint.sh ./docker-entrypoint.sh
COPY alembic ./alembic
COPY app ./app

# The directories a deployment writes into, created here so their paths are the
# image's decision rather than the operator's: app.config resolves the SQLite
# file and the evidence store root against this directory, which is /app. Both
# are handed to the service user, because a root-owned /app answers the first
# upload with a permission error rather than at deploy time.
# 0755 because a Windows checkout carries no executable bit, and an
# ENTRYPOINT that cannot be executed is a container that cannot start.
RUN chmod 0755 /app/docker-entrypoint.sh \
 && mkdir -p /app/evidence \
 && chown -R drishti:drishti /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
 
RUN tesseract --version \
 && python -c "import shutil, pytesseract; print(shutil.which('tesseract')); print(pytesseract.get_tesseract_version())"
# Everything above this line runs as root to build the image; nothing below it
# does. The virtualenv stays root-owned and world-readable, so the service user
# can import from it and write only under /app.
USER drishti:drishti

# The migration runs here, in the container that will open the database and
# as the user that has to write it (D215). The CMD below is unchanged, so
# the image and the deploy step still serve one command line.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# The service listens on 8080, which is the port Cloud Run sets PORT to, so one
# CMD serves both the container and the deployment.
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
