// IUU Fishing Radar frontend: MapLibre GL JS + PMTiles protocol + live SSE feed.
// Reads window.IUU_RADAR_CONFIG.API_BASE_URL for all data. No data is stored
// in this file or fetched from anywhere but the configured VPS API.

const { API_BASE_URL, DEFAULT_REGION } = window.IUU_RADAR_CONFIG;

const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  container: "map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [-90.5, -0.7],
  zoom: 6,
  attributionControl: true,
});

map.addControl(new maplibregl.NavigationControl(), "top-left");

function setStatus(state, label) {
  const el = document.getElementById("connection-status");
  el.className = `status status--${state}`;
  el.textContent = label;
}

async function fetchJSON(path, params = {}) {
  const url = new URL(API_BASE_URL + path);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) url.searchParams.set(key, value);
  }
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${path} failed: ${response.status}`);
  return response.json();
}

function openDetail(html) {
  const drawer = document.getElementById("detail-drawer");
  document.getElementById("detail-content").innerHTML = html;
  drawer.classList.remove("hidden");
}

document.getElementById("detail-close").addEventListener("click", () => {
  document.getElementById("detail-drawer").classList.add("hidden");
});

function reasonsHTML(reasons) {
  if (!reasons || reasons.length === 0) {
    return '<div class="reason">No specific rule flags, ranked by statistical anomaly.</div>';
  }
  return reasons.map((r) => `<div class="reason">${r}</div>`).join("");
}

async function showMpaDetail(mpaId) {
  try {
    const mpa = await fetchJSON(`/api/mpas/${mpaId}`);
    const vessels = mpa.top_vessels
      .map((v) => `<div class="reason"><strong>${v.vessel_id}</strong> — score ${v.score.toFixed(0)}</div>`)
      .join("");
    openDetail(`
      <h3>MPA ${mpa.mpa_id}</h3>
      <div class="reason">Risk score: <strong>${mpa.score.toFixed(0)}</strong></div>
      <div class="reason">Top contributing vessels</div>
      ${vessels || '<div class="reason">No flagged vessels yet.</div>'}
    `);
  } catch (err) {
    console.error(err);
  }
}

async function showVesselDetail(vesselId) {
  try {
    const vessel = await fetchJSON(`/api/vessels/${vesselId}`);
    openDetail(`
      <h3>Vessel ${vessel.vessel_id}</h3>
      <div class="reason">Risk score: <strong>${vessel.score.toFixed(0)}</strong></div>
      ${reasonsHTML(vessel.reasons)}
    `);
  } catch (err) {
    console.error(err);
  }
}

async function loadRankedMpas() {
  const list = document.getElementById("mpa-list");
  try {
    const mpas = await fetchJSON("/api/mpas", { region: DEFAULT_REGION });
    list.innerHTML = "";
    for (const mpa of mpas) {
      const li = document.createElement("li");
      li.className = "list-item";
      li.innerHTML = `
        <div class="row">
          <span>#${mpa.rank} · MPA ${mpa.mpa_id}</span>
          <span class="score">${mpa.score.toFixed(0)}</span>
        </div>
      `;
      li.addEventListener("click", () => showMpaDetail(mpa.mpa_id));
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = '<li class="list-item">Unable to reach the API.</li>';
    console.error(err);
  }
}

function prependAnomalyToFeed(anomaly) {
  const list = document.getElementById("anomaly-list");
  const li = document.createElement("li");
  li.className = "list-item item-enter";
  const reason = (anomaly.reasons && anomaly.reasons[0]) || "Flagged as anomalous.";
  li.innerHTML = `
    <div class="row">
      <span>Vessel ${anomaly.vessel_id}</span>
    </div>
    <div class="sub">${reason}</div>
  `;
  li.addEventListener("click", () => showVesselDetail(anomaly.vessel_id));
  list.prepend(li);
  while (list.children.length > 25) list.removeChild(list.lastChild);
}

function dropAnomalyMarker(anomaly) {
  if (typeof anomaly.lon !== "number" || typeof anomaly.lat !== "number") return;
  const el = document.createElement("div");
  el.className = "anomaly-marker";
  new maplibregl.Marker({ element: el })
    .setLngLat([anomaly.lon, anomaly.lat])
    .setPopup(
      new maplibregl.Popup({ offset: 12 }).setHTML(
        `<strong>Vessel ${anomaly.vessel_id}</strong><br/>${(anomaly.reasons || []).join("<br/>")}`
      )
    )
    .addTo(map);
}

async function loadInitialAnomalies() {
  try {
    const anomalies = await fetchJSON("/api/anomalies/latest", {
      region: DEFAULT_REGION,
      limit: 25,
    });
    for (const anomaly of anomalies.reverse()) {
      prependAnomalyToFeed(anomaly);
      dropAnomalyMarker(anomaly);
    }
  } catch (err) {
    console.error(err);
  }
}

function connectLiveFeed() {
  setStatus("connecting", "connecting…");
  const source = new EventSource(
    `${API_BASE_URL}/api/stream?region=${encodeURIComponent(DEFAULT_REGION)}`
  );

  source.addEventListener("anomaly", (event) => {
    setStatus("live", "live");
    const anomaly = JSON.parse(event.data);
    prependAnomalyToFeed(anomaly);
    dropAnomalyMarker(anomaly);
  });

  source.addEventListener("keep-alive", () => setStatus("live", "live"));
  source.onerror = () => setStatus("connecting", "reconnecting…");
}

map.on("load", () => {
  map.addSource("mpa", { type: "vector", url: `pmtiles://${API_BASE_URL}/tiles/mpa.pmtiles` });
  map.addLayer({
    id: "mpa-fill",
    type: "fill",
    source: "mpa",
    "source-layer": "mpa",
    paint: { "fill-color": "#38d3c0", "fill-opacity": 0.08 },
  });
  map.addLayer({
    id: "mpa-outline",
    type: "line",
    source: "mpa",
    "source-layer": "mpa",
    paint: { "line-color": "#38d3c0", "line-width": 1.5 },
  });

  map.addSource("hotspots", {
    type: "vector",
    url: `pmtiles://${API_BASE_URL}/tiles/hotspots.pmtiles`,
  });
  map.addLayer({
    id: "hotspots-fill",
    type: "fill",
    source: "hotspots",
    "source-layer": "hotspots",
    paint: {
      "fill-color": [
        "interpolate",
        ["linear"],
        ["get", "intensity"],
        0,
        "#f2b84b22",
        50,
        "#ef6a6aaa",
      ],
    },
  });

  map.on("click", "mpa-fill", (e) => {
    const props = e.features[0].properties;
    if (props.mpa_id) showMpaDetail(props.mpa_id);
  });
  map.on("mouseenter", "mpa-fill", () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", "mpa-fill", () => (map.getCanvas().style.cursor = ""));

  loadRankedMpas();
  loadInitialAnomalies();
  connectLiveFeed();
});
