# syntax=docker/dockerfile:1
#
# Production image for the xtox FastAPI backend (backend/server.py).
# Built by .github/workflows/deploy.yaml and pushed to
# ghcr.io/celladore/xtox-api, then referenced by infra/env/prod's
# container_image var (Azure Container App, Consumption plan, scale-to-zero).
FROM python:3.12-slim

# ffmpeg is a runtime dependency of pydub. The TeX packages provide pdflatex
# and the document primitives used by the conversion API (including CoilTrace's
# print-grade quotation, invoice, and certificate templates).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        texlive-fonts-recommended \
        texlive-latex-base \
        texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

# Fail the image build rather than discovering a missing binary or package on
# the first production conversion request.
RUN printf '\\documentclass{article}\n\\usepackage[table]{xcolor}\n\\usepackage{geometry,tabularx,array,helvet}\n\\begin{document}Mill render smoke test\\end{document}\n' > /tmp/mill-smoke.tex \
    && cd /tmp \
    && pdflatex -interaction=nonstopmode -halt-on-error mill-smoke.tex >/dev/null \
    && rm -f /tmp/mill-smoke.*

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
# The API only imports AudioConverter and ImageConverter. Copying
# core/__init__.py would eagerly import the CLI/document converters and
# require their unrelated dependencies. With no __init__.py, core is a
# Python namespace package containing just the runtime modules this service
# uses.
COPY core/audio_converter.py ./core/
COPY core/image_converter.py ./core/

# backend/config.py defaults TEMP_DIR to /tmp/xtopdf and creates it at import
# time. Pre-create it so the first request doesn't race module import, and
# give the runtime user ownership for per-request conversion directories.
RUN mkdir -p /tmp/xtopdf

# Run as non-root. Azure Container Apps has no issue with a non-root
# entrypoint.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /tmp/xtopdf
USER appuser

# Fail the image build if the production ASGI module cannot be imported. This
# catches missing source packages before an image can reach Container Apps.
RUN python -c "from server import app"

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
