FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
COPY uv.lock .

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]