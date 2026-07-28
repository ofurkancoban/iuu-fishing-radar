# CLAUDE.md

Project context and working instructions for Claude Code.
Read this file fully before starting any task. Follow the conventions and the
phased roadmap. Do not skip ahead: each phase produces artifacts the next phase
depends on.

---

## 1. Project overview

**Name:** IUU Fishing Radar (working title, repo: `iuu-fishing-radar`)

**One line:** An open-data pipeline that detects anomalous fishing vessel
behavior around Marine Protected Areas (MPAs) and serves the results through a
live interactive map that helps enforcement analysts decide where to look.

**Problem framing:** Illegal, Unreported and Unregulated (IUU) fishing is hard
to catch because vessels can fish inside protected zones and switch off their
AIS transponders to go dark. This project combines three open signals to surface
suspicious activity and rank it so a human reviewer can prioritize
investigation:

1. Where vessels fish (AIS apparent fishing effort).
2. When vessels go dark (AIS disabling / gap events) near sensitive boundaries.
3. Which boundaries matter (Marine Protected Area polygons).

**Decision output (the point of the project):** a ranked, mappable risk score
per MPA and per vessel, plus hotspot cells and a live anomaly feed, so the answer
to "where should a patrol or audit go first?" is concrete and visual.

**Audience:** this is a portfolio project. Code quality, reproducibility, a
clean architecture and an impressive live visualization matter as much as the
analysis itself.

---

## 2. Deployment model (read this first, it drives everything)

There are two planes and they have very different jobs.

- **VPS = compute plane AND data plane AND serving plane.** All heavy data lives
  here and never leaves. The VPS runs the pipeline, stores the datasets
  (DuckDB, Parquet, tiles), and exposes a small API that the frontend queries.
- **GitHub Pages = showcase only.** It hosts a thin static frontend (HTML, JS,
  CSS, one config file). It holds no data. Every dataset, tile, and anomaly it
  displays is fetched live from the VPS API at runtime.

Consequences that MUST be respected:
- Never commit large data files, tiles, or raw datasets to the repo. The repo
  holds code and the thin frontend only.
- The frontend reads a single `API_BASE_URL` (in `web/config.js`) pointing at
  the VPS domain. That is the only thing that differs between local and
  production.
- Because GitHub Pages is served over HTTPS, the VPS API MUST also be served
  over HTTPS on a real domain or subdomain. A browser page loaded over HTTPS
  cannot call an `http://` endpoint (mixed content is blocked). Use Caddy for
  automatic TLS. This is not optional.
- Exposing a public API turns the VPS into an attack surface. VPS security is a
  cross-cutting requirement, not an afterthought. Section 11 lists the mandatory
  hardening, and every phase that adds network exposure, a secret, or a new
  service MUST apply the relevant hardening before it is considered done.

---

## 3. Goals and non-goals

### Goals
- A fully reproducible pipeline runnable from a single command on a fresh VPS.
- A modular architecture where each stage is independently testable.
- A live interactive web map (the showcase) that reads from the VPS API and
  updates as new anomalies are detected.
- Demonstrate breadth across modern data engineering, ML, and serving tooling
  (see section 6) without gluing unrelated tools together for show. Every tool
  must earn its place.
- Config-driven region selection so the same pipeline runs for any EEZ or set of
  MPAs by editing one YAML file.

### Non-goals
- No claim that flagged vessels are actually guilty. The output is a
  prioritization aid, not a verdict. All UI copy and README text must frame it as
  "apparent" / "potential" / "worth reviewing", never as proven illegality.
- No true real-time upstream data. Global Fishing Watch data lags from hours to a
  few days, so "live" means the map reflects the latest pipeline state and
  streams updates to connected clients as new results are produced, not that the
  ocean is watched second by second. Be honest about this in the README.
- No paid data sources. Everything must come from free, open data.
- No data hosted on GitHub Pages. Pages is a static shell only.

---

## 4. Data sources

All sources are open and free. Access details:

### 4.1 Global Fishing Watch (GFW) APIs (primary)
- Access via the official Python client `gfw-api-python-client`.
- Requires a free API token. The token lives in the `.env` file on the VPS only.
  Never commit it. Never print it in logs.
- Data used:
  - **4Wings API:** AIS apparent fishing effort rasters, gridded by location and
    time.
  - **Events API:** fishing events, encounters (potential transshipment),
    loitering, port visits, and AIS disabling (gap) events. The gap events are
    the most important novel signal for this project.
  - **Vessels API:** vessel identity, flag, registry info, used for identity
    anomaly features (missing registry data, flag inconsistencies).
- Respect rate limits. Pull region by region and cache raw responses to disk so
  reruns do not re-hit the API.

### 4.2 World Database on Protected Areas (WDPA)
- Marine Protected Area polygons.
- Download from protectedplanet.net (shapefile / geodatabase) or read via the
  Google Earth Engine catalog asset `WCMC/WDPA/current/polygons`.
- **License constraint (important):** WDPA data may NOT be redistributed. Since
  all data stays on the VPS and is never committed, this is naturally satisfied.
  Still, the API must not expose raw WDPA geometry for bulk download. Serve only
  simplified display geometry and derived scores, and show a WDPA attribution
  line in the web UI footer and README.

### 4.3 Optional context layers (only if time allows)
- EEZ boundaries (Marine Regions, marineregions.org) for regional filtering.
- Country / coastline base layers from Natural Earth (public domain).

---

## 5. Architecture

Data flows left to right on the VPS, then the frontend pulls from the API over
HTTPS. Big data never crosses the boundary; only query results and tiles do.

```
                            VPS (single machine)
  +------------------------------------------------------------------+
  |                                                                  |
  |  COMPUTE / PIPELINE                                              |
  |  [Ingest] GFW client + WDPA loader  -> data/raw (parquet/gjson)  |
  |     v                                                            |
  |  [Storage] DuckDB (spatial ext) + Parquet  raw->staging->marts   |
  |     v                                                            |
  |  [Transform] dbt-duckdb SQL models, spatial joins vs MPA zones   |
  |     v                                                            |
  |  [Features] GeoPandas, Shapely, H3 aggregation                  |
  |     v                                                            |
  |  [ML] PyOD / scikit-learn anomaly scoring + rules.py flags       |
  |     v                                                            |
  |  writes results into DuckDB result tables + generates PMTiles    |
  |  on new anomalies: publish notice to pub/sub                     |
  |     |                                                            |
  |     |  Prefect flow orchestrates all of the above (cron)         |
  |     v                                                            |
  |  SERVING                                                         |
  |  [FastAPI]  /api/... reads DuckDB result tables                  |
  |             /api/stream  SSE, pushes new anomalies live          |
  |  [Tiles]    hotspot + MPA PMTiles served as static files         |
  |     ^                                                            |
  |  [Caddy]  reverse proxy, automatic HTTPS, CORS, range requests   |
  +------------------------------------------------------------------+
                         ^   HTTPS (api.yourdomain)
                         |   fetch + SSE, live
                         |
              GitHub Pages (showcase only)
  +------------------------------------------------------------------+
  |  Static shell: MapLibre GL JS + PMTiles protocol + vanilla JS    |
  |  web/config.js -> API_BASE_URL points at the VPS                 |
  |  Layers: MPA risk outlines, hotspot heat, live anomaly markers   |
  |  No data stored here. Everything fetched from the VPS at runtime. |
  +------------------------------------------------------------------+
```

### Serving layer responsibilities
- **FastAPI** reads from the DuckDB result tables and serves compact JSON. It
  never streams raw datasets. Endpoints are paginated and bounded (bbox, limits).
- **Tiles:** hotspot cells and simplified MPA outlines are exported to a
  `.pmtiles` file on the VPS and served as a static file through Caddy. MapLibre
  reads it client side via the pmtiles protocol using HTTP range requests, so no
  dynamic tile server is required. (Optional upgrade: `martin` for live dynamic
  tiles if range-served PMTiles becomes limiting.)
- **Live feed:** a Server-Sent Events endpoint (`/api/stream`) pushes newly
  flagged anomalies to connected browsers so markers appear on the map without a
  reload. Default backing is a lightweight pub/sub (Redis) that the pipeline
  publishes to when scoring finds new anomalies. If Redis is not wanted, fall
  back to a DB-cursor SSE that polls the result table for rows newer than the
  last sent id. Prefer Redis for clean decoupling between the pipeline process
  and the API process.

### Payload discipline (browser side)
Even though data lives on the VPS, the browser must receive small responses:
- Aggregate to H3 cells before serving hotspots.
- Serve dense geometry as PMTiles, not GeoJSON.
- Paginate vessel and anomaly lists, support `min_score` and `bbox` filters.
- Simplify MPA polygons for display before tiling.

### Cross-origin and transport (must configure)
- FastAPI `CORSMiddleware` allows the exact GitHub Pages origin
  (for example `https://ofurkancoban.github.io`). Do not use a wildcard in
  production.
- Caddy terminates TLS and reverse-proxies `/api/*` to FastAPI and serves the
  `.pmtiles` static files, enabling range requests.
- SSE must not be buffered by the proxy. Configure Caddy to flush the
  `/api/stream` route so events reach the client immediately.

### Runtime: everything in Docker
Every service runs in a container, orchestrated by `docker-compose` on the single
VPS. Nothing runs directly on the host except Docker itself, the firewall, and
SSH. The compose stack is the single source of truth for what runs on the VPS.

### Observability stack (recommended, part of the default build)
A monitoring stack runs alongside the app so the VPS is observable and abuse is
visible:
- **Prometheus** scrapes metrics from the API (via a FastAPI instrumentator),
  the host (`node-exporter`), and the containers (`cAdvisor`). The pipeline
  exposes custom metrics (anomalies detected per run, rows processed, run
  duration, failures).
- **Grafana** provides dashboards over Prometheus: operational (API latency,
  request rate, rate-limit hits, CPU, memory, disk, container health, pipeline
  run status) and analytical (anomalies over time, top MPAs by risk). This also
  satisfies the security monitoring requirement in section 11.
- Grafana and Prometheus are internal only. They are never exposed to the public
  internet without authentication (see section 11).

### Optional event streaming (opt-in, off by default)
The default live feed uses Redis pub/sub, which is the right size for this
low-volume batch pipeline. If the goal is to demonstrate an event-driven,
Kafka-style architecture, enable the streaming profile: the pipeline publishes
anomaly events to a **Redpanda** topic (Kafka-API compatible, single binary,
light enough for one VPS), and the SSE endpoint consumes that topic instead of
Redis. This is a deliberate showcase, not a necessity: Kafka-grade infrastructure
is overkill for the actual data volume here, so it lives behind a compose profile
and a config flag, and the honest tradeoff is documented in the README.

---

## 6. Technology stack

Each tool maps to a specific job. Do not add tools outside this list without a
clear reason, and do not use a listed tool outside its role.

| Layer | Tool | Role |
|-------|------|------|
| Package / env | `uv` | Fast dependency and virtualenv management |
| Lint / format | `ruff` | Linting and formatting |
| Ingestion | `gfw-api-python-client`, `httpx` | Pull GFW data |
| Storage | DuckDB + `spatial` extension, Parquet | Analytical store, spatial SQL |
| Transformation | `dbt-duckdb` | SQL staging and mart models, tested and documented |
| Geospatial (Python) | GeoPandas, Shapely, `h3` | Buffers, spatial ops, hex aggregation |
| ML | `pyod`, scikit-learn | Unsupervised anomaly detection |
| Rules | plain Python | Deterministic red-flag logic |
| Tiling | `tippecanoe`, PMTiles | Generate vector tiles served from the VPS |
| Serving API | FastAPI, `uvicorn` | JSON endpoints + SSE live feed |
| Pub/sub (live) | Redis (optional) | Decouple pipeline from API for SSE |
| Orchestration | Prefect | Flow definition, scheduling, retries |
| Reverse proxy / TLS | Caddy | Automatic HTTPS, CORS, static tiles, SSE flush |
| Frontend | MapLibre GL JS, PMTiles protocol, vanilla JS | Static live map |
| Containerization | Docker, docker-compose | Reproducible VPS runtime, all services |
| Metrics | Prometheus, `node-exporter`, cAdvisor | Scrape API, host, and container metrics |
| Dashboards | Grafana | Operational and analytical dashboards |
| Streaming (optional) | Redpanda (Kafka API) | Opt-in event-driven live feed showcase |
| K8s (optional) | k3s | Opt-in alternative deployment target for portfolio |
| CI/CD | GitHub Actions | Deploy `web/` to GitHub Pages |

### Infrastructure and tooling policy (encodes the "if needed" judgment)
This project runs on ONE VPS with batch, low-volume data. Choose infrastructure
to match that reality, not to collect buzzwords. A portfolio is stronger when it
shows judgment about when NOT to use heavy tooling.
- **Default runtime is docker-compose on a single node.** This is the correct
  tool for one VPS. It is the primary, always-built path.
- **Grafana and Prometheus are in the default build.** They earn their place:
  real observability and security monitoring for a public-facing service.
- **Kafka-style streaming is opt-in only.** The data volume does not justify a
  distributed log. If enabled for showcase reasons, use Redpanda behind a compose
  profile, and state plainly in the README that it is a demonstration, not a
  requirement.
- **Kubernetes is opt-in only and never the default.** Full K8s on a single node
  is an anti-pattern. If a K8s deliverable is wanted, provide k3s manifests as a
  clearly labeled alternative in a late optional phase, and keep docker-compose as
  the source of truth. Do not build this unless explicitly requested.
- Do not add any other heavy infrastructure without a stated, honest reason tied
  to a real need in this project.

### Portfolio rationale (for the README, not for behavior)
The stack tells one story: a modern lakehouse-lite pipeline (DuckDB + dbt +
Parquet) feeding an unsupervised ML layer, orchestrated with Prefect, and served
through a FastAPI + Caddy backend that powers a live, serverless-frontend map
(MapLibre + PMTiles + SSE). This demonstrates data engineering, geospatial
analysis, ML, backend serving, and frontend delivery in a single coherent
project.

---

## 7. Repository structure

Create and maintain this layout. Keep `data/`, tiles, and secrets out of git.

```
iuu-fishing-radar/
├── CLAUDE.md
├── README.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── caddy/
│   └── Caddyfile              # TLS, reverse proxy, CORS, SSE flush, tiles
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml     # scrape configs: api, node-exporter, cadvisor
│   └── grafana/
│       ├── provisioning/      # datasources + dashboard providers
│       └── dashboards/        # json dashboards (operational + analytical)
├── k8s/                       # optional, only if k3s deliverable is requested
│   └── README.md              # kept empty/stub unless explicitly built
├── config/
│   └── regions.yml            # region + MPA + date-range definitions
├── data/                      # gitignored (lives on the VPS only)
│   ├── raw/
│   ├── interim/
│   └── processed/
├── tiles/                     # gitignored, generated pmtiles served by VPS
├── src/
│   └── iuu_radar/
│       ├── __init__.py
│       ├── config.py          # loads regions.yml + env
│       ├── ingest/
│       │   ├── gfw.py
│       │   └── wdpa.py
│       ├── spatial/
│       │   ├── mpa.py         # load, buffer, proximity zones
│       │   └── indexing.py    # H3 assignment + aggregation
│       ├── features/
│       │   └── build.py
│       ├── models/
│       │   ├── anomaly.py     # PyOD / IsolationForest scoring
│       │   └── rules.py       # deterministic flags + reason strings
│       ├── export/
│       │   ├── results.py     # write result tables to DuckDB
│       │   └── tiles.py       # build pmtiles via tippecanoe
│       ├── api/
│       │   ├── main.py        # FastAPI app, CORS, router mounts
│       │   ├── deps.py        # DuckDB connection, settings
│       │   ├── routers/
│       │   │   ├── mpas.py
│       │   │   ├── hotspots.py
│       │   │   ├── vessels.py
│       │   │   └── anomalies.py
│       │   └── stream.py      # SSE endpoint + pub/sub subscriber
│       ├── events/
│       │   └── bus.py         # publish/subscribe wrapper (Redis or DB cursor)
│       └── pipeline.py        # Prefect flow: ingest -> score -> export -> notify
├── dbt/
│   └── iuu_radar/
│       ├── dbt_project.yml
│       ├── profiles.yml       # duckdb profile
│       └── models/
│           ├── staging/       # stg_gfw_events, stg_mpa, ...
│           └── marts/         # mart_events_mpa, mart_vessel_features, ...
├── notebooks/                 # EDA only, never part of the pipeline
├── web/                       # deployed to GitHub Pages, showcase only
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── config.js              # API_BASE_URL only, no data
├── tests/
│   ├── test_spatial.py
│   ├── test_features.py
│   ├── test_rules.py
│   └── test_api.py
└── .github/
    └── workflows/
        ├── ci.yml
        └── deploy-pages.yml
```

---

## 8. API surface

Design the FastAPI endpoints as bounded, paginated reads. All responses are
compact JSON except tiles which are static PMTiles served by Caddy.

- `GET /api/health` : liveness and last pipeline run timestamp.
- `GET /api/regions` : configured regions.
- `GET /api/mpas?region=` : MPA list with risk score and rank (small GeoJSON or
  JSON, simplified geometry).
- `GET /api/mpas/{mpa_id}` : one MPA detail plus its top contributing vessels.
- `GET /api/hotspots?region=&bbox=` : H3 hotspot cells with intensity (bounded by
  bbox). For dense display prefer the PMTiles layer over this endpoint.
- `GET /api/vessels?region=&min_score=&limit=&offset=` : ranked flagged vessels
  with score and reason strings, paginated.
- `GET /api/vessels/{vessel_id}` : vessel detail, features, and flags.
- `GET /api/anomalies/latest?region=&limit=` : most recent flagged anomalies, for
  the initial state of the live feed.
- `GET /api/stream?region=` : Server-Sent Events. Emits each new anomaly as it is
  detected so the map can drop a marker live. Sends periodic keep-alive comments.

Tiles (served by Caddy as static files, read client side via pmtiles protocol):
- `/tiles/hotspots.pmtiles`
- `/tiles/mpa.pmtiles`

Rules for the API:
- Never return raw datasets or unbounded queries.
- Every list endpoint has a hard max `limit`.
- Filter by `region` everywhere; the pipeline supports multiple regions.
- Do not expose the GFW token or any secret through any endpoint.

---

## 9. Analytical approach

### Core question
Around Marine Protected Areas, which vessels and which locations show behavior
patterns consistent with potential IUU fishing, ranked by how unusual they are?

### Proximity zones
For each event, assign an MPA relationship using MPA polygons plus buffers:
- `inside`: event geometry inside an MPA polygon.
- `edge`: within a configurable buffer (default 10 km) of an MPA boundary.
- `outside`: elsewhere in the region.

Do the spatial join in DuckDB spatial where possible (ST_ functions), fall back
to GeoPandas only for operations DuckDB cannot do cleanly.

### Feature engineering (per vessel and per H3 cell)
Build features such as:
- Fishing effort hours inside vs edge vs outside MPAs.
- Count and total duration of AIS gap (disabling) events near MPA boundaries.
- Gap events that start near an MPA and end near the same MPA (dark then
  reappear), the strongest single red flag.
- Encounter / loitering counts inside protected zones.
- Speed and course-change profiles consistent with active fishing.
- Identity anomalies: missing registry entry, flag not matching operating
  region.

### Models
Combine two complementary layers, then merge into one score:
1. **Unsupervised anomaly detection** (`models/anomaly.py`): fit an ensemble
   (start with Isolation Forest via PyOD, optionally add ECOD or LOF) on the
   per-vessel feature matrix. Output a continuous anomaly score, normalized to
   0-100. Unsupervised because there is no reliable ground-truth label set.
2. **Rule-based flags** (`models/rules.py`): deterministic, explainable flags,
   for example "fishing effort inside a no-take MPA" or "AIS gap begins within
   5 km of an MPA boundary". Each flag is a named boolean with a short human
   readable reason string, so the UI can explain WHY something is flagged.

Final risk score = normalized anomaly score adjusted by rule hits, kept
interpretable. Always carry the reason strings through to the result tables so
the map and the live feed can show them.

### Result tables (what the API reads)
The pipeline writes tidy result tables into DuckDB:
- `result_mpa_scores` : mpa_id, region, score, rank, geometry_simplified.
- `result_hotspots` : h3_cell, region, intensity.
- `result_vessels` : vessel_id, region, score, flags, reasons, last_seen.
- `result_anomalies` : monotonic id, region, vessel_id, lon, lat, ts, reasons.
  The `result_anomalies` id is the cursor the SSE feed uses.

---

## 10. Deployment strategy

### VPS (compute + data + serving)
- Everything runs in Docker via `docker-compose`. Core services:
  - `pipeline` : runs the Prefect flow, triggered by cron.
  - `api` : FastAPI + uvicorn, reads DuckDB, serves JSON and SSE, exposes
    `/metrics` for Prometheus.
  - `caddy` : TLS termination, reverse proxy, serves static PMTiles.
  - `redis` : pub/sub for the live feed (default).
  - `prometheus` : scrapes api, node-exporter, cadvisor.
  - `grafana` : dashboards over Prometheus.
  - `node-exporter` : host metrics.
  - `cadvisor` : container metrics.
- Optional services behind compose profiles (not started by default):
  - `redpanda` : Kafka-API event log, enabled with the `streaming` profile when
    demonstrating event-driven architecture instead of Redis.
- Container and network rules (see section 11): only `caddy` publishes ports to
  the host (80/443). Every other service is reachable only on the internal Docker
  network. `prometheus`, `grafana`, `node-exporter`, and `cadvisor` are never
  published to the public internet.
- DuckDB file and Parquet live on a mounted volume on the VPS. They are the
  single source of truth and never leave the machine.
- The pipeline, when scoring finds new anomalies, writes them to
  `result_anomalies` and publishes a notice on the bus (Redis, or Redpanda under
  the streaming profile), which the SSE endpoint relays to connected browsers.
- Requires a domain or subdomain pointed at the VPS (for example
  `api.yourdomain.tld`) so Caddy can issue a TLS certificate. Document the DNS A
  record step in the README.
- Optional k3s deployment: only if explicitly requested. If built, k3s manifests
  in `k8s/` mirror the compose services. docker-compose stays the source of
  truth; do not let the two definitions drift.

### GitHub Pages (showcase)
- `deploy-pages.yml` publishes the `web/` directory to GitHub Pages on push to
  `main` when `web/**` changes. No data, no build secrets.
- `web/config.js` sets `API_BASE_URL` to the VPS HTTPS domain.

### Separation of secrets
- GFW token, Redis password, any VPS credentials: only in the VPS `.env`,
  gitignored.
- GitHub Actions needs no data secrets; it only copies the static shell.

---

## 11. VPS security requirements

The VPS hosts the data and a public API, so it must be hardened. Treat these as
mandatory. Apply each item at the phase where the relevant service or exposure is
introduced, and never move a phase to done while leaving its security items open.
Do not print, commit, or expose any secret while implementing these.

### 11.1 Network and firewall
- Only three inbound ports are public: 22 (SSH), 80 and 443 (Caddy). Deny all
  other inbound traffic with UFW or nftables. Set default inbound policy to deny,
  outbound to allow.
- Only Caddy binds to public interfaces. Every internal service (uvicorn/FastAPI,
  Redis, Prefect, Prometheus, Grafana, node-exporter, cAdvisor, Redpanda) binds
  to `127.0.0.1` or the internal Docker network, never to `0.0.0.0` on the public
  interface. In docker-compose, do not publish internal service ports to the
  host; expose them only to Caddy over the internal network.
- Redis, if used, must have a strong password, must bind to the internal network
  only, and must never be reachable from the public internet. Verify this
  explicitly. The same rule applies to Redpanda if the streaming profile is used.
- Monitoring UIs are sensitive: Prometheus, Grafana, node-exporter, and cAdvisor
  must not be exposed to the public internet. Reach them over an SSH tunnel, or
  put them behind Caddy on an internal-only path with authentication. If Grafana
  is exposed at all, change the default admin password immediately and set it from
  the VPS `.env`. cAdvisor and node-exporter are never public.

### 11.2 SSH hardening
- Key-based authentication only. Disable password authentication and disable root
  login in `sshd_config`.
- Run `fail2ban` (or equivalent) to throttle brute-force attempts on SSH.
- Optionally move SSH off port 22 and update the firewall rule accordingly.
- Use a dedicated non-root sudo user for administration.

### 11.3 TLS and proxy
- Caddy provides automatic HTTPS via Let's Encrypt. Enable HSTS and let Caddy use
  modern TLS defaults.
- Do not serve any plaintext HTTP content other than the automatic redirect to
  HTTPS.
- Configure Caddy to strip server version headers and to disable directory
  listing on the tiles path.

### 11.4 API hardening
- Rate limit the API per client IP (at Caddy or in FastAPI). Set sane request
  timeouts and a maximum request body size.
- Validate and bound every input: `bbox` area, `limit`, `offset`, `region` must
  be checked against allowed ranges so a caller cannot trigger an expensive or
  unbounded query. Reject anything out of range with a 4xx.
- CORS is restricted to the exact GitHub Pages origin from config. Never use a
  wildcard origin in production.
- In production, never return stack traces or internal error details to clients.
  Log them server side and return a generic error to the caller.
- The API process opens DuckDB read-only. It must not be able to write to the
  pipeline result tables. Separate the write path (pipeline) from the read path
  (API).
- No endpoint ever returns a secret, a raw dataset, or an unbounded dump.

### 11.5 Secrets management
- All secrets live in the VPS `.env`, which is gitignored and set to `chmod 600`.
  Secrets are never committed, never baked into Docker images, and never logged.
- Pass secrets to containers via env files or Docker secrets, not via image
  layers or build args.
- If the VPS needs to pull code, use a read-only deploy key scoped to this repo.
- Rotate the GFW token and any Redis password if they are ever exposed.

### 11.6 Docker hardening
- Containers run as a non-root user. Set an explicit `USER` in the Dockerfile.
- Pin base image versions (no bare `:latest` in production).
- Keep images minimal (slim base, no build tools in the runtime image).
- Mount the data volume read-only into the API container. Only the pipeline
  container gets write access to the data volume.
- Never mount the Docker socket into a container.
- Add a `healthcheck` to the api and caddy services.

### 11.7 System hygiene and monitoring
- Enable unattended security updates for the OS (for example
  `unattended-upgrades`). Keep the base OS patched.
- Install only the packages the project needs.
- Enable Caddy access logs and monitor them for abuse patterns.
- Monitor disk usage: the datasets grow over time, and a full disk breaks both
  the pipeline and the API. Add a simple alert or cron check.
- Keep a periodic backup of the DuckDB result file so a failure or compromise is
  recoverable. Store backups off the public path.

### 11.8 Application dependencies
- Pin dependency versions via `uv.lock`.
- Do not disable TLS verification in any HTTP client.
- Review third-party libraries before adding them; prefer well-maintained ones.

---

## 12. Coding conventions

These are firm. Follow them in every file you create or edit.

- **Language:** all code, comments, docstrings, variable names, commit messages,
  and in-repo documentation are written in English.
- **No em-dashes:** never use the long dash character in any generated text,
  code comment, README, or UI copy. Use commas, colons, parentheses, or separate
  sentences instead.
- **Commit authorship:** never add Claude, Anthropic, or any AI assistant as a
  co-author, contributor, or trailer in commits, PRs, or documentation. Commit
  messages describe the change only. Do not add "Co-authored-by" lines or
  "Generated with" lines.
- **Style:** format and lint with `ruff`. Type-hint public functions. Prefer
  small pure functions that are easy to test.
- **Config over hardcoding:** region, date ranges, buffer distances, H3
  resolution, MPA selection, API limits, and the allowed CORS origin all come
  from config (`config/regions.yml` and env). No magic numbers buried in code.
- **Reproducibility:** cache raw API responses to `data/raw/` so reruns are
  deterministic and do not re-hit rate-limited APIs.
- **Logging:** use structured logging. Never log the API token, Redis password,
  or full raw responses containing credentials.
- **Docstrings:** every module starts with a one line purpose comment. Every
  public function has a short docstring stating inputs, outputs, and side
  effects.
- **Tests:** spatial logic, feature construction, rules, and API endpoints must
  have unit tests with small synthetic fixtures. Tests must not require network
  access; mock the GFW client and use an in-memory DuckDB.

---

## 13. Environment and commands

### Environment
- Python managed by `uv`.
- `.env.example` lists required variables (`GFW_API_TOKEN`, `API_BASE_URL`,
  `CORS_ORIGIN`, `REDIS_URL` optional, `REDIS_PASSWORD` optional, `API_DOMAIN`,
  `RATE_LIMIT`, region default) with placeholder values. The real `.env` is
  gitignored, `chmod 600`, and lives on the VPS only.

### Makefile targets (create these)
- `make setup`       install deps with uv, install duckdb spatial extension
- `make ingest`      pull GFW + WDPA for the configured region
- `make dbt`         run dbt models and tests
- `make features`    build feature matrix
- `make score`       run anomaly detection + rules, write result tables
- `make tiles`       build hotspot + mpa pmtiles into tiles/
- `make pipeline`    run the full Prefect flow end to end
- `make api`         run FastAPI locally with uvicorn
- `make web`         serve web/ locally, pointed at a local API
- `make test`        run pytest
- `make lint`        run ruff check and format
- `make docker-up`   build and start the full VPS stack (all core services)
- `make monitoring`  start prometheus + grafana + exporters (part of the stack)
- `make streaming`   start the stack with the optional redpanda profile

Keep targets thin: they call into `src/iuu_radar` or the Prefect flow, they do
not contain business logic.

---

## 14. Roadmap (phased)

Work phase by phase. Do not start a phase until the previous one runs and is
committed. After each phase, update the README with what now works.

### Phase 0: Scaffolding
- Create the repo structure, `pyproject.toml`, `.gitignore` (ignore `data/`,
  `tiles/`, `.env`), `.env.example`, `Makefile`, `ruff` config, stub modules,
  and a stub Prefect flow.
- Set up `config/regions.yml` with one small default region for fast iteration.
- Add a minimal README describing the project and the two-plane model.

### Phase 1: Ingestion
- Implement `ingest/gfw.py`: authenticate, pull events (fishing, gaps,
  encounters, loitering) and fishing effort, cache raw responses to `data/raw/`.
- Implement `ingest/wdpa.py`: download / load MPA polygons into `data/raw/`.
- Load raw data into DuckDB raw tables. Sanity check counts in a notebook.

### Phase 2: Storage and transformation
- Enable the DuckDB spatial extension.
- Build dbt staging models (clean, typed, renamed).
- Build dbt mart models: `mart_events_mpa` (events tagged with proximity zone)
  and the base for vessel aggregation. Add dbt tests.

### Phase 3: Spatial and features
- Implement MPA buffers and proximity zones in `spatial/mpa.py`.
- Implement H3 assignment and aggregation in `spatial/indexing.py`.
- Implement `features/build.py` producing per-vessel and per-cell matrices.
  Unit test with synthetic geometry.

### Phase 4: Modeling
- Implement `models/rules.py` with named, explainable flags and reason strings.
- Implement `models/anomaly.py` with PyOD (Isolation Forest first), normalized.
- Merge into a final risk score. Verify synthetic suspicious cases rank high.
- Write result tables via `export/results.py` (including `result_anomalies` with
  a monotonic id cursor).

### Phase 5: Tiles
- Implement `export/tiles.py` to build `hotspots.pmtiles` and `mpa.pmtiles` via
  tippecanoe into `tiles/`. Simplify geometry, keep files small.

### Phase 6: Serving API
- Build the FastAPI app: routers for mpas, hotspots, vessels, anomalies.
- Configure CORS to the exact GitHub Pages origin from env.
- Implement `events/bus.py` (Redis pub/sub with a DB-cursor fallback).
- Implement `stream.py`: SSE endpoint that emits new anomalies and keep-alives.
- Security (section 11.4): add per-IP rate limiting, request timeouts and body
  size limit, strict input validation on bbox/limit/offset/region, generic error
  responses with no stack traces, and a read-only DuckDB connection for the API.
- Add `test_api.py` using an in-memory DuckDB and a fake bus, including tests that
  out-of-range inputs are rejected.

### Phase 7: Frontend (the showcase)
- Build the static map in `web/`: MapLibre GL JS, register the pmtiles protocol,
  load `mpa.pmtiles` and `hotspots.pmtiles` from the VPS, fetch scores and
  vessels from the API.
- Open an SSE connection to `/api/stream` and drop live markers as anomalies
  arrive, with a subtle animation and a running "latest anomalies" side panel.
- Interactions: click an MPA to see rank and top vessels, click a vessel to see
  score and reason strings. Include a clear disclaimer and WDPA + GFW attribution
  in the footer.
- Apply intentional, clean visual design. Read the frontend-design guidance if
  available and avoid a default template look.

### Phase 8: Reverse proxy, orchestration, deployment
- Write `caddy/Caddyfile`: HTTPS for the API domain, reverse proxy `/api/*` to
  FastAPI, serve `/tiles/*.pmtiles` as static files with range support, disable
  buffering on `/api/stream`.
- Wire all pipeline stages into the Prefect flow with retries on ingest.
- Write `Dockerfile` and `docker-compose.yml` for the core stack (pipeline, api,
  caddy, redis). Only caddy publishes host ports; everything else is internal.
- Set up cron to run the flow. On new anomalies the flow publishes to the bus.
- Write `deploy-pages.yml` to publish `web/` on push.
- Harden the VPS (section 11): configure the firewall (allow only 22, 80, 443),
  bind internal services to the internal network only, run containers as
  non-root, mount the data volume read-only into the api container, set the
  Redis password, apply SSH hardening and fail2ban, enable unattended security
  updates, and turn on Caddy access logs. Do not consider deployment done until
  these are in place.
- Document VPS setup, DNS A record, the hardening checklist, and the full deploy
  process in the README.

### Phase 9: Observability
- Add an api `/metrics` endpoint via a FastAPI Prometheus instrumentator.
- Expose custom pipeline metrics (anomalies per run, rows processed, run
  duration, failures).
- Add `prometheus`, `grafana`, `node-exporter`, and `cadvisor` to the compose
  stack, all on the internal network only, none published to the public internet.
- Provision Grafana datasource and dashboards from `monitoring/grafana/` (an
  operational dashboard and an analytical dashboard).
- Security (section 11): Grafana admin password from env, monitoring UIs reached
  via SSH tunnel or an authenticated internal Caddy path only.

### Phase 10 (optional, only if requested): event streaming
- Add a `redpanda` service behind the `streaming` compose profile.
- Make the pipeline publish anomaly events to a Kafka topic and have the SSE
  endpoint consume that topic when the profile is active, selectable by a config
  flag, with Redis as the default fallback.
- Document in the README that this is a demonstration of event-driven design and
  is not required by the data volume.

### Phase 11 (optional, only if requested): k3s deployment
- Provide k3s manifests in `k8s/` mirroring the compose services.
- Keep docker-compose as the source of truth. Do not build this unless the user
  explicitly asks for a Kubernetes deliverable.

### Phase 12: Security review
- Verify the firewall exposes only 22, 80, 443 and that Redis, the API, and all
  monitoring services are not reachable from the public internet.
- Confirm no secrets are in the repo or in any image, `.env` is `chmod 600`, and
  the API returns no stack traces and no unbounded responses.
- Run a final review against the section 11 checklist and record the result in
  the README.

---

## 15. Definition of done

- `make docker-up` brings up the full stack on a fresh VPS; `make pipeline`
  populates the result tables and tiles from raw config.
- The GitHub Pages map loads, reads live from the VPS over HTTPS, shows ranked
  MPAs, hotspots, and flagged vessels, streams new anomalies onto the map via
  SSE, and explains flags in plain language with a visible disclaimer.
- No large data or tiles are committed to the repo; the frontend holds only code
  and `config.js`.
- The full stack runs in Docker via docker-compose, including the observability
  services (Prometheus, Grafana, exporters), with Grafana showing at least one
  operational and one analytical dashboard, and no monitoring UI exposed publicly.
- The VPS API is HTTPS, CORS is restricted to the Pages origin, and no secret is
  exposed by any endpoint.
- The VPS is hardened per section 11: firewall limited to 22/80/443, internal
  services not publicly bound, Redis password set, SSH key-only with fail2ban,
  containers non-root, data volume read-only for the api, rate limiting on the
  API, unattended security updates enabled, and the section 11 checklist passes.
- Tests pass, ruff is clean, no secrets in the repo, no raw WDPA served for bulk
  download.
- README explains the problem, the two-plane architecture, the stack, how to run
  it locally, and how to deploy, with GFW and WDPA attribution.
- Commits are clean and contain no AI co-author or generated-with trailers.
