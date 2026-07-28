# Single image shared by the pipeline and api services (docker-compose.yml
# selects the command per service). Multi-stage: tippecanoe is compiled from
# source in a builder stage so the final runtime image stays slim.

FROM python:3.12.7-slim-bookworm AS tippecanoe-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ca-certificates \
    libsqlite3-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch 2.63.0 https://github.com/felt/tippecanoe.git /tmp/tippecanoe \
    && make -C /tmp/tippecanoe -j"$(nproc)" \
    && make -C /tmp/tippecanoe install

FROM python:3.12.7-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 iuu_radar

COPY --from=tippecanoe-builder /usr/local/bin/tippecanoe /usr/local/bin/tippecanoe
COPY --from=tippecanoe-builder /usr/local/bin/tile-join /usr/local/bin/tile-join

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY dbt/ dbt/
COPY config/ config/
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

RUN mkdir -p /app/data /app/tiles && chown -R iuu_radar:iuu_radar /app
USER iuu_radar

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["uvicorn", "iuu_radar.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
