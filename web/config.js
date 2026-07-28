// Single point of difference between local and production frontends.
// No data is ever stored here, only the API location. Regions are discovered
// at runtime from /api/regions, so no region needs to be configured here.
window.IUU_RADAR_CONFIG = {
  API_BASE_URL: "http://localhost:8000",
};
