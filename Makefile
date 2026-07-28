.PHONY: setup ingest dbt features score tiles pipeline api web test lint docker-up monitoring streaming

setup:
	uv sync
	uv run python -c "import duckdb; duckdb.connect().execute('INSTALL spatial; LOAD spatial;')"

ingest:
	uv run python -m iuu_radar.ingest.gfw
	uv run python -m iuu_radar.ingest.wdpa

dbt:
	cd dbt/iuu_radar && uv run dbt run && uv run dbt test

features:
	uv run python -m iuu_radar.features.build

score:
	uv run python -m iuu_radar.models.anomaly

tiles:
	uv run python -m iuu_radar.export.tiles

pipeline:
	uv run python -m iuu_radar.pipeline

api:
	uv run uvicorn iuu_radar.api.main:app --reload --host 127.0.0.1 --port 8000

web:
	cd web && python3 -m http.server 8080

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format .

docker-up:
	docker compose up --build -d

monitoring:
	docker compose up -d prometheus grafana node-exporter cadvisor

streaming:
	docker compose --profile streaming up -d
