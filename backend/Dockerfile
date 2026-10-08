FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"
WORKDIR /app
RUN useradd --uid 10001 --create-home app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn documind.main:app --host 0.0.0.0 --port 8000"]
