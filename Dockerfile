# Production image of the API (docs/deploy-runbook.md). Code and config only: data/ is mounted at run time.
# Build:  CTA_COMMIT=$(git rev-parse --short HEAD) docker compose --env-file .env.production -f docker-compose.prod.yml build

FROM python:3.12-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# uv reads uv.lock, so the image has exactly the versions the tests ran with (same tool as CI and the README)
RUN pip install --no-cache-dir uv==0.12.13
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
# tzdata: the API reads "today" in America/New_York (zoneinfo needs the system database)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /nonexistent --no-create-home cta
WORKDIR /app
# the project is installed in editable mode (the uv default), so the .venv points at /app/src and
# cta.settings.ROOT is /app: config/, db/ and the mounted data/ are found there
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY pyproject.toml ./
COPY config ./config
COPY db ./db
ARG CTA_COMMIT=unknown
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 CTA_API_HOST=0.0.0.0 CTA_COMMIT=$CTA_COMMIT
USER cta
EXPOSE 8000
CMD ["python", "-m", "cta.api"]
