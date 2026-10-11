#!/bin/sh
# The deploy step: migrate, then serve.
#
# lembic upgrade head runs here, in the container that will open the
# database, rather than as a Cloud Build step. A build step migrates a
# database inside the build; the service reads the file in its own
# container, so the two would be different databases and the one being
# served would still hold no schema. Cloud Run has no init container, so
# the start command is the only place both can be one filesystem.
#
# It runs as the service user (D215's uid 10001) and writes the SQLite
# file app.config resolves, which is /app/drishti.db in this image. The
# Dockerfile chmods this file, because a Windows checkout carries no
# executable bit and an entrypoint without one cannot be run.
set -e

alembic upgrade head

exec "$@"
