# IUU Fishing Radar

An open-data pipeline that detects anomalous fishing vessel behavior around
Marine Protected Areas (MPAs) and serves the results through a live interactive
map that helps enforcement analysts decide where to look.

The output is a ranked, mappable risk score per MPA and per vessel, plus
hotspot cells and a live anomaly feed. This is a prioritization aid, not a
verdict: flagged vessels are described as showing "apparent" or "potential"
patterns worth reviewing, never as proven illegality.

## Two-plane architecture

- **VPS (compute + data + serving):** runs the pipeline, stores all datasets
  (DuckDB, Parquet, PMTiles), and exposes a small FastAPI service over HTTPS.
  All data lives here and never leaves.
- **GitHub Pages (showcase only):** a thin static frontend (MapLibre GL JS,
  PMTiles protocol, vanilla JS) that fetches everything live from the VPS API
  at runtime. It holds no data of its own, only `web/config.js` pointing at
  the VPS domain.

See `CLAUDE.md` for the full architecture, data sources, API surface,
technology stack, phased roadmap, and the mandatory VPS security checklist
(section 11).

## Data sources

- **Global Fishing Watch** (4Wings fishing effort, Events API, Vessels API):
  free API, requires a token, kept only in the VPS `.env`.
- **World Database on Protected Areas (WDPA)**: MPA polygons. License forbids
  redistribution, so raw geometry never leaves the VPS or the API; only
  simplified display geometry and derived scores are served.
- Optional context: Marine Regions EEZ boundaries, Natural Earth basemaps.

## Status

Phase 0 (scaffolding) is in progress: repository layout, dependency manifest,
config schema, and stub modules for every pipeline and API component are in
place. No stage is implemented yet; each module raises `NotImplementedError`
with a pointer to the phase that fills it in. Work proceeds phase by phase per
the roadmap in `CLAUDE.md` section 14.

## Local development

```bash
make setup      # install deps with uv, install duckdb spatial extension
make test       # run pytest
make lint       # ruff check + format
make api        # run FastAPI locally (once Phase 6 lands)
make web        # serve web/ locally against a local API
```

Copy `.env.example` to `.env` and fill in `GFW_API_TOKEN` before running
ingestion. Never commit `.env`.

## Deployment

The full stack (pipeline, API, Caddy, Redis, Prometheus, Grafana, exporters)
runs via `docker-compose` on a single VPS behind Caddy, which terminates TLS
and is the only service bound to a public interface. `web/` is deployed to
GitHub Pages by `.github/workflows/deploy-pages.yml` on every push that
touches it. Full setup instructions land with Phase 8.

## Attribution

MPA data: World Database on Protected Areas (UNEP-WCMC and IUCN).
Fishing activity data: Global Fishing Watch.
