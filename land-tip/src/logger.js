// ─────────────────────────────────────────────────────────────
// UrbanAlpha Verbose Logger
// Every backend call, every fallback, every render decision — logged.
// Toggle via: window.LOG_LEVEL = 'ERROR' | 'WARN' | 'INFO' | 'DEBUG' | 'TRACE'
// Or silence: window.LOG_LEVEL = 'OFF'
// Ring buffer (last 500 entries) on window.LOG_HISTORY
// ─────────────────────────────────────────────────────────────

const LEVELS = { OFF: -1, ERROR: 0, WARN: 1, INFO: 2, DEBUG: 3, TRACE: 4 };

function currentLevel() {
  const raw = (typeof window !== 'undefined' && window.LOG_LEVEL) || 'TRACE';
  return LEVELS[raw] ?? LEVELS.TRACE;
}

const RING_SIZE = 500;
const ring = [];
if (typeof window !== 'undefined') window.LOG_HISTORY = ring;

function ts() {
  const d = new Date();
  const pad = (n, l = 2) => String(n).padStart(l, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

const STYLES = {
  ERROR: { css: 'background:#7f1d1d;color:#fff;padding:1px 4px;border-radius:3px', label: 'ERROR' },
  WARN:  { css: 'background:#b45309;color:#fff;padding:1px 4px;border-radius:3px', label: ' WARN' },
  INFO:  { css: 'background:#1e3a5f;color:#fff;padding:1px 4px;border-radius:3px', label: ' INFO' },
  DEBUG: { css: 'background:#374151;color:#fff;padding:1px 4px;border-radius:3px', label: 'DEBUG' },
  TRACE: { css: 'background:#166534;color:#fff;padding:1px 4px;border-radius:3px', label: 'TRACE' },
};

function pushRing(entry) {
  ring.push(entry);
  if (ring.length > RING_SIZE) ring.shift();
}

function emit(level, tag, msg, data) {
  if (LEVELS[level] > currentLevel()) return;
  const time = ts();
  const s = STYLES[level];
  const header = `%c${time} ${s.label} [${tag}]`;
  const entry = { time, level, tag, msg, data: data ?? null };

  if (data !== undefined) {
    pushRing({ ...entry, data });
    console.groupCollapsed(header, s.css, ` ${msg}`);
    console.log('  payload:', data);
    console.groupEnd();
  } else {
    pushRing(entry);
    console.log(header, s.css, ` ${msg}`);
  }
}

// Factory: each module gets its own tagged logger
export function createLogger(tag) {
  return {
    error: (msg, data) => emit('ERROR', tag, msg, data),
    warn:  (msg, data) => emit('WARN', tag, msg, data),
    info:  (msg, data) => emit('INFO', tag, msg, data),
    debug: (msg, data) => emit('DEBUG', tag, msg, data),
    trace: (msg, data) => emit('TRACE', tag, msg, data),
  };
}

// Dump ring buffer as formatted string — for bug reports / on-screen display
export function dumpLog(n = 50) {
  const slice = ring.slice(-n);
  return slice.map((e) =>
    `${e.time} ${e.level.padEnd(5)} [${e.tag}] ${e.msg}${e.data ? '\n  ↳ ' + JSON.stringify(e.data).slice(0, 300) : ''}`
  ).join('\n');
}

// Quick dump to console
if (typeof window !== 'undefined') {
  window.dumpLog = (n) => console.log(dumpLog(n));
  console.log(
    '%c[LOGGER] Verbose logger active — level: TRACE. window.dumpLog(50) to print last 50 entries.',
    'color:#166534;font-weight:bold'
  );
}
