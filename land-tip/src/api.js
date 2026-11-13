// UrbanAlpha BLI backend API client
// Backend runs via: uvicorn app.main:app --reload (port 8000)

export const API_BASE_URL = 'http://localhost:8000';

/**
 * POST /parcel/analyze — baseline CatBoost valuation + spatial buffer analysis.
 * @param {object} params — ParcelRequest fields (location, total_sqft, bhk, ...)
 * @returns {Promise<object>} ParcelAnalysisResponse
 */
export async function analyzeParcel(params) {
  const res = await fetch(`${API_BASE_URL}/parcel/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!res.ok) throw new Error(`Parcel analysis failed: ${res.status}`);
  return res.json();
}

/**
 * POST /simulation/run — Mesa multi-agent simulation (Years 0..N).
 * @param {object} parcel — ParcelRequest fields
 * @param {object} config — SimulationConfig (years, households, developers, ...)
 * @param {boolean} scrapeFirst — run a live scrape before simulating
 * @returns {Promise<object>} SimulationRunResponse
 */
export async function runSimulation(parcel, config = {}, scrapeFirst = false) {
  const res = await fetch(`${API_BASE_URL}/simulation/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parcel, config, scrape_first: scrapeFirst })
  });
  if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
  return res.json();
}

/**
 * GET /simulation/{runId} — fetch a stored simulation run.
 * @param {string} runId
 * @returns {Promise<object>} SimulationFetchResponse
 */
export async function getSimulation(runId) {
  const res = await fetch(`${API_BASE_URL}/simulation/${runId}`);
  if (!res.ok) throw new Error(`Fetch simulation failed: ${res.status}`);
  return res.json();
}

/**
 * GET /infrastructure/ — list all stored infrastructure projects.
 * @returns {Promise<{count: number, projects: object[]}>}
 */
export async function listInfrastructure() {
  const res = await fetch(`${API_BASE_URL}/infrastructure/`);
  if (!res.ok) throw new Error(`List infrastructure failed: ${res.status}`);
  return res.json();
}

/**
 * POST /infrastructure/scrape-live — trigger the scraping cluster.
 * @param {string[]|null} sources — optional source filters
 * @returns {Promise<object>} ScrapeResponse
 */
export async function scrapeLive(sources = null) {
  const url = sources && sources.length
    ? `${API_BASE_URL}/infrastructure/scrape-live?${sources.map(s => `sources=${encodeURIComponent(s)}`).join('&')}`
    : `${API_BASE_URL}/infrastructure/scrape-live`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) throw new Error(`Scrape failed: ${res.status}`);
  return res.json();
}

/**
 * GET /health — liveness probe + baseline model status.
 * @returns {Promise<object>} { status, version, baseline_model_ready, repository }
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) return { status: 'error', baseline_model_ready: false };
    return res.json();
  } catch {
    return { status: 'error', baseline_model_ready: false };
  }
}
