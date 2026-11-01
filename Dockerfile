FROM ghcr.io/astral-sh/uv:0.10.11 AS uv
FROM python:3.12.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH FEAST_USAGE=False
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev && useradd --uid 10001 --user-group --create-home income \
    && mkdir /work && chown 10001:10001 /work
WORKDIR /work
USER income
CMD ["python", "-m", "income_lab.model"]
