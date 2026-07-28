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

Phases 0 through 8 are implemented: ingestion, DuckDB/dbt storage and
transforms, spatial/feature engineering, rule-based flags and anomaly scoring,
pmtiles export, the FastAPI + SSE serving layer, the MapLibre frontend
showcase, and Docker/Caddy deployment. The stack is deployed and reachable on
the project VPS (see Deployment below). Remaining work: Phase 9
(Prometheus/Grafana dashboards content), and Phase 12 (final security review).
Work proceeds phase by phase per the roadmap in `CLAUDE.md` section 14.

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
runs via `docker-compose` on a single VPS. Only Caddy publishes ports to the
host; every other service (api, redis, prometheus, grafana, node-exporter,
cadvisor) is reachable only over the internal Docker network. `web/` is
deployed to GitHub Pages by `.github/workflows/deploy-pages.yml` on every push
that touches it.

### Current VPS setup (shared box, pre-domain)

This project's VPS is a pre-existing, actively used server hosting other
unrelated apps (not a dedicated single-purpose box), so the deployment adapts
CLAUDE.md's defaults instead of applying them blindly:

- **Firewall:** UFW is enabled with a default-deny inbound policy. Every port
  already in use by other apps on the box was explicitly allowed alongside
  22 (SSH), 80/443 (the box's existing nginx), and this project's Caddy ports.
- **Caddy ports:** the box's nginx already owns host ports 80/443, so Caddy is
  temporarily bound to host ports 8090 (HTTP) and 8443 (HTTPS) via
  `CADDY_HTTP_PORT` / `CADDY_HTTPS_PORT` in `.env`. Once a domain is pointed at
  this VPS and 80/443 are free (or an nginx vhost is added to proxy to Caddy),
  switch these back to 80/443.
- **TLS:** no domain is configured yet, so `API_DOMAIN` is set to `:80` in
  `.env`, which tells Caddy to serve plain HTTP without attempting automatic
  HTTPS. Once a domain's DNS A record points at the VPS, set `API_DOMAIN` to
  that domain and Caddy will automatically obtain a Let's Encrypt certificate.
  Until then, the GitHub Pages frontend (served over HTTPS) cannot call this
  API directly due to browser mixed-content blocking; use a local API for
  frontend development in the meantime.
- **SSH:** a dedicated non-root sudo user was created for this project's
  administration, with fail2ban and unattended security updates enabled.
  `PermitRootLogin` and `PasswordAuthentication` were intentionally left
  unchanged (still enabled) at the operator's request, since other workflows
  on this shared box depend on root SSH access. This is a deliberate deviation
  from CLAUDE.md section 11.2 and should be revisited if the box is ever moved
  to dedicated, single-purpose use.
- **Secrets:** `GFW_API_TOKEN`, `REDIS_PASSWORD`, and `GRAFANA_ADMIN_PASSWORD`
  are set from randomly generated values in the VPS's `.env` (`chmod 600`,
  gitignored), never committed.

### Bringing the stack up

```bash
# On the VPS, from the repo root:
docker compose up -d api caddy redis prometheus grafana node-exporter cadvisor
# Pipeline is not part of `up`; invoke it on a schedule instead:
docker compose run --rm pipeline
```

## Attribution

MPA data: World Database on Protected Areas (UNEP-WCMC and IUCN).
Fishing activity data: Global Fishing Watch.
