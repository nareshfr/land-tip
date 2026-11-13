// UrbanAlpha BLI backend API client
// Backend runs via: uvicorn app.main:app --reload (port 8000)

import { createLogger } from './logger.js';
const log = createLogger('API');

export const API_BASE_URL = 'http://localhost:8000';

// Timing wrapper
async function timedFetch(label, url, opts) {
  const t0 = performance.now();
  log.info(`${label} → ${opts?.method || 'GET'} ${url}`, opts?.body ? JSON.parse(opts.body) : undefined);
  try {
    const res = await fetch(url, opts);
    const ms = Math.round(performance.now() - t0);
    log.info(`${label} ← ${res.status} ${res.statusText} (${ms}ms)`);
    if (!res.ok) {
      let body = null;
      try { body = await res.text(); } catch {}
      log.error(`${label} HTTP ${res.status} response body`, body ? body.slice(0, 500) : '(empty)');
    }
    return res;
  } catch (err) {
    const ms = Math.round(performance.now() - t0);
    log.error(`${label} network failure after ${ms}ms`, { name: err.name, message: err.message });
    throw err;
  }
}

/**
 * POST /parcel/analyze — baseline CatBoost valuation + spatial buffer analysis.
 * @param {object} params — ParcelRequest fields (location, total_sqft, bhk, ...)
 * @returns {Promise<object>} ParcelAnalysisResponse
 */
export async function analyzeParcel(params) {
  const res = await timedFetch('analyzeParcel', `${API_BASE_URL}/parcel/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!res.ok) throw new Error(`Parcel analysis failed: ${res.status}`);
  const json = await res.json();
  log.debug('analyzeParcel response', json);
  return json;
}

/**
 * POST /simulation/run — Mesa multi-agent simulation (Years 0..N).
 * @param {object} parcel — ParcelRequest fields
 * @param {object} config — SimulationConfig (years, households, developers, ...)
 * @param {boolean} scrapeFirst — run a live scrape before simulating
 * @returns {Promise<object>} SimulationRunResponse
 */
export async function runSimulation(parcel, config = {}, scrapeFirst = false) {
  const payload = { parcel, config, scrape_first: scrapeFirst };
  const res = await timedFetch('runSimulation', `${API_BASE_URL}/simulation/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
  const json = await res.json();
  log.debug('runSimulation response keys', {
    has_baseline: !!json.baseline,
    timeline_len: json.timeline?.length,
    has_future_valuation: !!json.future_valuation,
    has_summary: !!json.summary,
    run_id: json.run_id
  });
  return json;
}

/**
 * GET /simulation/{runId} — fetch a stored simulation run.
 * @param {string} runId
 * @returns {Promise<object>} SimulationFetchResponse
 */
export async function getSimulation(runId) {
  const res = await timedFetch('getSimulation', `${API_BASE_URL}/simulation/${runId}`);
  if (!res.ok) throw new Error(`Fetch simulation failed: ${res.status}`);
  return res.json();
}

/**
 * GET /infrastructure/ — list all stored infrastructure projects.
 * @returns {Promise<{count: number, projects: object[]}>}
 */
export async function listInfrastructure() {
  const res = await timedFetch('listInfrastructure', `${API_BASE_URL}/infrastructure/`);
  if (!res.ok) throw new Error(`List infrastructure failed: ${res.status}`);
  const json = await res.json();
  log.debug('listInfrastructure response', { count: json.count, projects_len: json.projects?.length });
  return json;
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
  const res = await timedFetch('scrapeLive', url, { method: 'POST' });
  if (!res.ok) throw new Error(`Scrape failed: ${res.status}`);
  return res.json();
}

/**
 * GET /health — liveness probe + baseline model status.
 * @returns {Promise<object>} { status, version, baseline_model_ready, repository }
 */
export async function checkHealth() {
  try {
    const res = await timedFetch('checkHealth', `${API_BASE_URL}/health`);
    if (!res.ok) {
      log.warn('checkHealth non-OK status, treating as offline', { status: res.status });
      return { status: 'error', baseline_model_ready: false };
    }
    const json = await res.json();
    log.info('checkHealth OK', json);
    return json;
  } catch {
    log.error('checkHealth — backend unreachable (is uvicorn running?)');
    return { status: 'error', baseline_model_ready: false };
  }
}
