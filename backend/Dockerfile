# syntax=docker/dockerfile:1
#
# Production image for the xtox FastAPI backend (backend/server.py).
# Built by .github/workflows/deploy.yaml and pushed to
# ghcr.io/celladore/xtox-api, then referenced by infra/env/prod's
# container_image var (Azure Container App, Consumption plan, scale-to-zero).
FROM python:3.12-slim

# ffmpeg is a runtime dependency of pydub (backend/services/audio_service.py),
# used to normalize uploaded audio before it's forwarded to sluice's
# transcription endpoint. requirements.txt only pulls the Python binding —
# the actual ffmpeg binary has to come from the OS package.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copied and installed before the rest of the source so `docker build` can
# cache this layer across app-code-only changes.
COPY backend/requirements.txt .
# This file also carries dev/lint tooling (pytest, black, isort, flake8,
# mypy) — kept as one file so `make dev-install` and this image can never
# drift apart, at the cost of a larger image. Split into a
# requirements-prod.txt if that tradeoff stops being worth it.
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# backend/config.py defaults TEMP_DIR and DOC_STORAGE_DIR to /tmp paths and
# creates them at import time — pre-create so the first request doesn't race
# module import, and so a read-only-root-filesystem policy change fails loudly
# here instead of at request time.
RUN mkdir -p /tmp/xtopdf /tmp/document_storage

# Run as non-root. Azure Container Apps has no issue with a non-root
# entrypoint, and /tmp is world-writable by default so no chown is needed.
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000

# GET /api/ (backend/routers/status.py) is a static, dependency-free 200 —
# the best available liveness signal. It does not check the Mongo
# connection; there is no DB-backed readiness endpoint yet.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/', timeout=3).status == 200 else 1)"

# server.py's `if __name__ == "__main__"` block sets reload=True (a dev-only
# autoreload file-watcher) — invoke uvicorn directly instead for prod, with
# no --reload.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
