# Serving image for the online plane: a stateless FastAPI app that reads a
# read-only serving artifact baked into the image. Run N identical replicas
# behind a load balancer to scale with users.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install only the runtime + API dependencies (no matplotlib, no dev tools).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[api]"

# Bake the precomputed serving artifact into the image. Build it first with:
#   anime-stackviz process && anime-stackviz publish
# so that data/serving/ exists in the build context.
COPY data/serving ./data/serving

# Non-root for safety; the app never writes to disk.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# Stateless: no shared writable state, so replicas scale horizontally.
CMD ["uvicorn", "anime_stackviz.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
