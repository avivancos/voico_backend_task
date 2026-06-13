# syntax=docker/dockerfile:1

# --- builder: resolve and install dependencies into /app/.venv with uv ---
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Dependency layer (cached unless pyproject/lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Project layer.
COPY app ./app
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# --- runtime: slim image, non-root, migrate-on-start ---
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# --- test: same deps + dev group + tests, for `docker compose --profile test` ---
FROM builder AS test
ENV PATH="/app/.venv/bin:$PATH"
RUN uv sync --frozen
COPY scripts ./scripts
COPY tests ./tests
CMD ["pytest", "-q"]
