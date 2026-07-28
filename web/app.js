// IUU Fishing Radar frontend: MapLibre GL JS + PMTiles protocol + live SSE feed.
// Reads window.IUU_RADAR_CONFIG.API_BASE_URL for all data. No data is stored
// in this file or fetched from anywhere but the configured VPS API.
//
// Regions are discovered from /api/regions rather than hardcoded, so every
// configured region's MPAs, hotspots, and anomalies show up on one world map,
// with a region filter in the side panel to focus on just one.

const { API_BASE_URL } = window.IUU_RADAR_CONFIG;

const ALL_REGIONS = "__all__";
const state = {
  regions: [], // [{region, name, bbox}]
  regionByKey: new Map(),
  mpas: [], // flattened across regions, each tagged with .region
  markers: [], // [{marker, region}]
  selectedRegion: ALL_REGIONS,
};

const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  container: "map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [20, 20],
  zoom: 1.5,
  attributionControl: true,
});

map.addControl(new maplibregl.NavigationControl(), "top-left");

function setStatus(statusState, label) {
  const el = document.getElementById("connection-status");
  el.className = `status status--${statusState}`;
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

function renderMpaList() {
  const list = document.getElementById("mpa-list");
  const mpas = state.mpas
    .filter((m) => state.selectedRegion === ALL_REGIONS || m.region === state.selectedRegion)
    .sort((a, b) => b.score - a.score);

  list.innerHTML = "";
  if (mpas.length === 0) {
    list.innerHTML = '<li class="list-item">No MPAs scored for this region yet.</li>';
    return;
  }
  for (const mpa of mpas) {
    const li = document.createElement("li");
    li.className = "list-item";
    li.innerHTML = `
      <div class="row">
        <span>#${mpa.rank} · MPA ${mpa.mpa_id} <span class="sub">(${mpa.region})</span></span>
        <span class="score">${mpa.score.toFixed(0)}</span>
      </div>
    `;
    li.addEventListener("click", () => showMpaDetail(mpa.mpa_id));
    list.appendChild(li);
  }
}

async function loadRankedMpas(regions) {
  try {
    const perRegion = await Promise.all(
      regions.map((r) => fetchJSON("/api/mpas", { region: r.region }).catch(() => []))
    );
    state.mpas = perRegion.flat();
    renderMpaList();
  } catch (err) {
    console.error(err);
  }
}

function prependAnomalyToFeed(anomaly) {
  const list = document.getElementById("anomaly-list");
  const li = document.createElement("li");
  li.className = "list-item item-enter";
  li.dataset.region = anomaly.region;
  if (state.selectedRegion !== ALL_REGIONS && anomaly.region !== state.selectedRegion) {
    li.style.display = "none";
  }
  const reason = (anomaly.reasons && anomaly.reasons[0]) || "Flagged as anomalous.";
  li.innerHTML = `
    <div class="row">
      <span>Vessel ${anomaly.vessel_id} <span class="sub">(${anomaly.region})</span></span>
    </div>
    <div class="sub">${reason}</div>
  `;
  li.addEventListener("click", () => showVesselDetail(anomaly.vessel_id));
  list.prepend(li);
  while (list.children.length > 60) list.removeChild(list.lastChild);
}

function dropAnomalyMarker(anomaly) {
  if (typeof anomaly.lon !== "number" || typeof anomaly.lat !== "number") return;
  const el = document.createElement("div");
  el.className = "anomaly-marker";
  if (state.selectedRegion !== ALL_REGIONS && anomaly.region !== state.selectedRegion) {
    el.style.display = "none";
  }
  const marker = new maplibregl.Marker({ element: el })
    .setLngLat([anomaly.lon, anomaly.lat])
    .setPopup(
      new maplibregl.Popup({ offset: 12 }).setHTML(
        `<strong>Vessel ${anomaly.vessel_id}</strong><br/>${(anomaly.reasons || []).join("<br/>")}`
      )
    )
    .addTo(map);
  state.markers.push({ marker, region: anomaly.region });
}

async function loadInitialAnomalies(regions) {
  try {
    const perRegion = await Promise.all(
      regions.map((r) =>
        fetchJSON("/api/anomalies/latest", { region: r.region, limit: 25 }).catch(() => [])
      )
    );
    const anomalies = perRegion.flat().sort((a, b) => (a.id ?? 0) - (b.id ?? 0));
    for (const anomaly of anomalies) {
      prependAnomalyToFeed(anomaly);
      dropAnomalyMarker(anomaly);
    }
  } catch (err) {
    console.error(err);
  }
}

function connectLiveFeed(regions) {
  setStatus("connecting", "connecting…");
  let liveCount = 0;

  for (const r of regions) {
    const source = new EventSource(
      `${API_BASE_URL}/api/stream?region=${encodeURIComponent(r.region)}`
    );

    source.addEventListener("anomaly", (event) => {
      liveCount += 1;
      setStatus("live", "live");
      const anomaly = JSON.parse(event.data);
      prependAnomalyToFeed(anomaly);
      dropAnomalyMarker(anomaly);
    });

    source.addEventListener("keep-alive", () => setStatus("live", "live"));
    source.onerror = () => {
      if (liveCount === 0) setStatus("connecting", "reconnecting…");
    };
  }
}

function addRegionLayers(region) {
  const mpaSourceId = `mpa-${region}`;
  const hotspotsSourceId = `hotspots-${region}`;

  map.addSource(mpaSourceId, {
    type: "vector",
    url: `pmtiles://${API_BASE_URL}/tiles/${region}_mpa.pmtiles`,
  });
  map.addLayer({
    id: `mpa-fill-${region}`,
    type: "fill",
    source: mpaSourceId,
    "source-layer": "mpa",
    paint: { "fill-color": "#38d3c0", "fill-opacity": 0.08 },
  });
  map.addLayer({
    id: `mpa-outline-${region}`,
    type: "line",
    source: mpaSourceId,
    "source-layer": "mpa",
    paint: { "line-color": "#38d3c0", "line-width": 1.5 },
  });

  map.addSource(hotspotsSourceId, {
    type: "vector",
    url: `pmtiles://${API_BASE_URL}/tiles/${region}_hotspots.pmtiles`,
  });
  map.addLayer({
    id: `hotspots-fill-${region}`,
    type: "fill",
    source: hotspotsSourceId,
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

  map.on("click", `mpa-fill-${region}`, (e) => {
    // The tiles carry raw WDPA attribute names (SITE_ID), not the API's mpa_id
    // alias; both refer to the same value (see dbt stg_mpa.sql).
    const props = e.features[0].properties;
    if (props.SITE_ID) showMpaDetail(String(props.SITE_ID));
  });
  map.on("mouseenter", `mpa-fill-${region}`, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", `mpa-fill-${region}`, () => (map.getCanvas().style.cursor = ""));
}

function regionLayerIds(region) {
  return [`mpa-fill-${region}`, `mpa-outline-${region}`, `hotspots-fill-${region}`];
}

function bboxUnion(regions) {
  let [minLon, minLat, maxLon, maxLat] = regions[0].bbox;
  for (const r of regions.slice(1)) {
    const [lo1, la1, lo2, la2] = r.bbox;
    minLon = Math.min(minLon, lo1);
    minLat = Math.min(minLat, la1);
    maxLon = Math.max(maxLon, lo2);
    maxLat = Math.max(maxLat, la2);
  }
  return [minLon, minLat, maxLon, maxLat];
}

function fitToBbox(bbox, opts = {}) {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  map.fitBounds(
    [
      [minLon, minLat],
      [maxLon, maxLat],
    ],
    { padding: 40, duration: 600, ...opts }
  );
}

function applyRegionFilter(selected) {
  state.selectedRegion = selected;

  for (const r of state.regions) {
    const visible = selected === ALL_REGIONS || r.region === selected;
    for (const layerId of regionLayerIds(r.region)) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    }
  }

  for (const { marker, region } of state.markers) {
    marker.getElement().style.display =
      selected === ALL_REGIONS || region === selected ? "" : "none";
  }

  for (const li of document.getElementById("anomaly-list").children) {
    li.style.display = selected === ALL_REGIONS || li.dataset.region === selected ? "" : "none";
  }

  renderMpaList();

  if (selected === ALL_REGIONS) {
    fitToBbox(bboxUnion(state.regions));
  } else {
    const region = state.regionByKey.get(selected);
    if (region) fitToBbox(region.bbox);
  }
}

function populateRegionFilter(regions) {
  const select = document.getElementById("region-filter");
  for (const r of regions) {
    const option = document.createElement("option");
    option.value = r.region;
    option.textContent = r.name;
    select.appendChild(option);
  }
  select.addEventListener("change", (e) => applyRegionFilter(e.target.value));
}

map.on("error", (e) => {
  // A missing pmtiles file for one region (e.g. its pipeline hasn't run yet)
  // should not break the rest of the map.
  console.warn("Map source error (non-fatal):", e.error?.message || e);
});

map.on("load", async () => {
  let regions;
  try {
    regions = await fetchJSON("/api/regions");
  } catch (err) {
    console.error("Unable to load /api/regions:", err);
    regions = [];
  }

  state.regions = regions;
  state.regionByKey = new Map(regions.map((r) => [r.region, r]));

  for (const r of regions) addRegionLayers(r.region);
  if (regions.length > 0) fitToBbox(bboxUnion(regions), { duration: 0 });

  populateRegionFilter(regions);
  loadRankedMpas(regions);
  loadInitialAnomalies(regions);
  connectLiveFeed(regions);
});
