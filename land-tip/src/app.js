import { ZONE_CENTERS, EXACT_COORDS, BENGALURU_DATABASE } from './data/bengaluruLocations.js';

const BASE_YEAR = 2026;
const OFFSETS = [0, 1, 2, 3, 4, 5];

// Flatten all 250+ database items into searchable records
const ALL_LOCATIONS = BENGALURU_DATABASE.flatMap((sec) => {
  const zoneMeta = ZONE_CENTERS[sec.category] || ZONE_CENTERS["Central Bengaluru"];
  return sec.items.map((name) => ({
    name,
    category: sec.category,
    group: sec.group,
    coords: EXACT_COORDS[name] || zoneMeta.coords,
    hasExactCoords: Boolean(EXACT_COORDS[name]),
    basePrice: zoneMeta.basePrice,
    cagr: zoneMeta.cagr,
    metroKm: zoneMeta.metroKm,
    builtUp: zoneMeta.builtUp
  }));
});

const DIRECTORY_GROUPS = [...new Set(BENGALURU_DATABASE.map((s) => s.group))];

const CURRENT_METRO = [
  { name: 'Purple Line', color: '#0f172a', pts: [[12.9298, 77.5515], [12.9756, 77.6066], [12.9784, 77.6408], [12.9959, 77.6970], [12.9698, 77.7499]] },
  { name: 'Green Line', color: '#334155', pts: [[13.0285, 77.5409], [12.9756, 77.5713], [12.9308, 77.5838], [12.8880, 77.5600]] }
];

const FUTURE_METRO = [
  { minOffset: 1, name: 'Yellow Line (RV Rd – Electronic City)', color: '#f97316', pts: [[12.9215, 77.5805], [12.9177, 77.6233], [12.8890, 77.6380], [12.8452, 77.6602]] },
  { minOffset: 2, name: 'Blue Line (ORR – Hebbal – Airport)', color: '#ea580c', pts: [[12.9165, 77.6440], [12.9698, 77.7010], [13.0358, 77.5970], [13.1007, 77.5963]] },
  { minOffset: 3, name: 'Phase-3 West Orbital Corridor', color: '#f59e0b', pts: [[13.0358, 77.5970], [12.9900, 77.5350], [12.9308, 77.5500]] }
];

const FUTURE_CATALYSTS = [
  { yearOffset: 1, title: 'Indiranagar Multi-Modal TOD Hub', progress: 78, uplift: '+4.2%', coords: [12.9805, 77.6380] },
  { yearOffset: 1, title: 'ITPL AI & Semiconductor SEZ', progress: 82, uplift: '+7.5%', coords: [12.9845, 77.7360] },
  { yearOffset: 1, title: 'Yellow Line High-Frequency Metro', progress: 88, uplift: '+8.4%', coords: [12.8495, 77.6650] },
  { yearOffset: 2, title: 'Blue Line Airport Express Station', progress: 76, uplift: '+9.0%', coords: [13.0410, 77.5930] },
  { yearOffset: 2, title: 'HSR Sector-2 Blue Line Metro', progress: 79, uplift: '+8.1%', coords: [12.9165, 77.6440] },
  { yearOffset: 3, title: 'Bommasandra EV & DeepTech Park', progress: 74, uplift: '+7.1%', coords: [12.8320, 77.6740] },
  { yearOffset: 4, title: 'Whitefield-Hoskote Neo-Metro Spur', progress: 56, uplift: '+9.2%', coords: [12.9910, 77.7590] }
];

let state = {
  activeArea: ALL_LOCATIONS.find((l) => l.name === 'Indiranagar') || ALL_LOCATIONS[0],
  offset: 0,
  categoryFilter: 'all',
  landmarkFilter: 'all',
  activeDirGroup: DIRECTORY_GROUPS[0],
  layers: { metro: true, landmarks: true, infra: true, satellite: false },
  liveLandmarks: [],
  drawing: false,
  drawPoints: [],
  maskedArea: null,
  playing: false,
  playTimer: null
};

// Map Setup
const map = L.map('map', { zoomControl: false, doubleClickZoom: false }).setView(state.activeArea.coords, 13);
L.control.zoom({ position: 'bottomright' }).addTo(map);

const lightTileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
  attribution: 'Tiles &copy; Esri',
  maxZoom: 16
}).addTo(map);

const satTileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
  attribution: 'Imagery &copy; Esri',
  maxZoom: 17
});

const metroLayer = L.layerGroup().addTo(map);
const growthLayer = L.layerGroup().addTo(map);
const liveLandmarkLayer = L.layerGroup().addTo(map);
const infraLayer = L.layerGroup().addTo(map);
const drawPreviewLayer = L.layerGroup().addTo(map);
const maskLayer = L.layerGroup().addTo(map);

// Chart.js
const ctx = document.getElementById('analysisChart').getContext('2d');
const analysisChart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: OFFSETS.map((o) => (o === 0 ? '2026 (Now)' : `${BASE_YEAR + o}`)),
    datasets: [{
      data: [],
      borderColor: '#0f172a',
      backgroundColor: 'rgba(249, 115, 22, 0.14)',
      fill: true,
      tension: 0.34,
      borderWidth: 2.5,
      pointRadius: [],
      pointBackgroundColor: []
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (c) => ' ₹' + c.parsed.y.toLocaleString('en-IN') + ' / sq ft' } }
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 } } },
      y: { grid: { color: '#e2e8f0' }, ticks: { font: { size: 11 }, callback: (v) => '₹' + (v / 1000).toFixed(0) + 'k' } }
    }
  }
});

function calcProjected(basePrice, cagr, offset) {
  const price = Math.round((basePrice * Math.pow(1 + cagr, offset)) / 10) * 10;
  const diff = price - basePrice;
  const pct = ((diff / basePrice) * 100).toFixed(1);
  return { price, diff, pct };
}

const counterCache = {};
function animateValue(id, targetVal, prefix = '', suffix = '') {
  const el = document.getElementById(id);
  if (!el) return;
  const startVal = counterCache[id] !== undefined ? counterCache[id] : targetVal;
  counterCache[id] = targetVal;
  const t0 = performance.now();
  const dur = 260;
  function step(now) {
    const p = Math.min(1, (now - t0) / dur);
    const cur = Math.round(startVal + (targetVal - startVal) * p);
    el.textContent = prefix + cur.toLocaleString('en-IN') + suffix;
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function getTarget() {
  return state.maskedArea || state.activeArea;
}

function buildMaskTooltip(target, offset) {
  const { price, diff, pct } = calcProjected(target.basePrice, target.cagr, offset);
  const yr = offset === 0 ? 'Present (2026)' : `+${offset}Y (${BASE_YEAR + offset})`;
  return `
    <div style="font-family:'Helvetica Neue',Helvetica,Arial,sans-serif; min-width:185px; padding:2px;">
      <div style="font-size:10px; font-weight:700; color:#ea580c; text-transform:uppercase;">${target.name} · ${yr}</div>
      <div style="font-size:16px; font-weight:700; color:#0f172a; margin-top:2px;">₹${price.toLocaleString('en-IN')} / sq ft</div>
      <div style="font-size:11px; font-weight:600; color:#059669;">+₹${diff.toLocaleString('en-IN')} (+${pct}%)</div>
      <div style="font-size:10px; color:#64748b; margin-top:3px;">Click zone or <strong>(i)</strong> for Analysis View</div>
    </div>
  `;
}

// Live Overpass API Landmark Fetcher
async function fetchLiveLandmarks(lat, lng) {
  const badge = document.getElementById('sync-badge');
  badge.classList.remove('hidden');
  try {
    const query = `[out:json][timeout:10];(
      node["railway"="station"](around:2500,${lat},${lng});
      node["station"="subway"](around:2500,${lat},${lng});
      way["landuse"="industrial"](around:2000,${lat},${lng});
      node["office"](around:1800,${lat},${lng});
      node["amenity"~"hospital|university|mall"](around:1800,${lat},${lng});
    );out center 18;`;
    const res = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body: 'data=' + encodeURIComponent(query)
    });
    const data = await res.json();
    const items = (data.elements || [])
      .filter((el) => el.tags && el.tags.name)
      .slice(0, 16)
      .map((el) => {
        const c = el.center ? [el.center.lat, el.center.lon] : [el.lat, el.lon];
        let kind = 'amenity';
        if (el.tags.railway || el.tags.station) kind = 'metro';
        else if (el.tags.office || el.tags.landuse === 'industrial') kind = 'tech';
        return { name: el.tags.name, kind, coords: c };
      });
    state.liveLandmarks = items;
  } catch (err) {
    state.liveLandmarks = [];
  } finally {
    badge.classList.add('hidden');
    renderUI();
  }
}

function renderMapOverlays() {
  metroLayer.clearLayers();
  growthLayer.clearLayers();
  liveLandmarkLayer.clearLayers();
  infraLayer.clearLayers();

  if (state.layers.metro) {
    CURRENT_METRO.forEach((m) => L.polyline(m.pts, { color: m.color, weight: 3, opacity: 0.7 }).addTo(metroLayer));
    FUTURE_METRO.forEach((fm) => {
      if (state.offset >= fm.minOffset) {
        const line = L.polyline(fm.pts, { color: fm.color, weight: 3.5, opacity: 0.95, className: 'flowing-metro' }).addTo(metroLayer);
        line.bindTooltip(`New Transit Corridor: ${fm.name}`, { sticky: true });
      }
    });
  }

  const target = getTarget();
  const radius = 500 + state.offset * 145 + (target.builtUp - 60) * 14;
  L.circle(target.coords, {
    radius,
    color: '#f97316',
    weight: 1.8,
    fillColor: '#f97316',
    fillOpacity: 0.20
  }).addTo(growthLayer);

  const dotHtml = `<div class="w-4 h-4 rounded-full bg-orange-500 pulse-beacon border-2 border-white shadow-md"></div>`;
  L.marker(target.coords, { icon: L.divIcon({ html: dotHtml, iconSize: [16, 16], iconAnchor: [8, 8] }) })
    .addTo(growthLayer)
    .bindTooltip(target.name, { direction: 'top', offset: [0, -8] });

  if (state.layers.landmarks) {
    state.liveLandmarks.forEach((lm) => {
      if (state.landmarkFilter !== 'all' && lm.kind !== state.landmarkFilter) return;
      const bg = lm.kind === 'metro' ? 'bg-slate-950' : lm.kind === 'tech' ? 'bg-blue-600' : 'bg-emerald-600';
      const lbl = lm.kind === 'metro' ? 'M' : lm.kind === 'tech' ? 'T' : 'L';
      const html = `<div class="w-5 h-5 rounded-full ${bg} text-white text-[9px] font-bold flex items-center justify-center border border-white shadow spring-in">${lbl}</div>`;
      L.marker(lm.coords, { icon: L.divIcon({ html, iconSize: [20, 20], iconAnchor: [10, 10] }) })
        .addTo(liveLandmarkLayer)
        .bindTooltip(`${lm.name} (${lm.kind.toUpperCase()})`, { direction: 'top' });
    });
  }

  if (state.layers.infra && state.offset > 0) {
    FUTURE_CATALYSTS.forEach((proj) => {
      if (state.offset < proj.yearOffset) return;
      L.circle(proj.coords, {
        radius: 480,
        color: '#f97316',
        weight: 1.5,
        dashArray: '4, 4',
        fillColor: '#fb923c',
        fillOpacity: 0.28
      }).addTo(infraLayer);

      const calloutHtml = `
        <div class="glass-panel spring-in rounded-2xl p-2.5 w-[200px] pointer-events-auto">
          <div class="flex items-center justify-between">
            <span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-950 text-white tabular-nums">+${proj.yearOffset}Y (${BASE_YEAR + proj.yearOffset})</span>
            <span class="text-[11px] font-bold text-emerald-600 tabular-nums">${proj.uplift}</span>
          </div>
          <div class="text-[11px] font-bold text-slate-900 mt-1 leading-snug">${proj.title}</div>
          <div class="mt-1.5 flex items-center gap-1.5">
            <div class="flex-1 h-2 rounded-full striped-track overflow-hidden p-0.5 border border-slate-300/60">
              <div class="h-full rounded-full" style="width:${proj.progress}%; background:linear-gradient(90deg,#fdba74,#f97316);"></div>
            </div>
            <span class="text-[10px] font-bold text-slate-800 tabular-nums">${proj.progress}%</span>
          </div>
        </div>
      `;
      L.marker(proj.coords, { icon: L.divIcon({ html: calloutHtml, iconSize: [200, 74], iconAnchor: [100, 82] }) }).addTo(infraLayer);
    });
  }

  if (state.maskedArea && state.maskedArea.polygonLayer) {
    state.maskedArea.polygonLayer.setTooltipContent(buildMaskTooltip(state.maskedArea, state.offset));
  }
}

function renderUI() {
  const target = getTarget();
  const { price, diff, pct } = calcProjected(target.basePrice, target.cagr, state.offset);
  const builtNow = Math.min(97, target.builtUp + state.offset * 2);

  document.getElementById('pill-builtup').textContent = builtNow + '%';
  animateValue('pill-price', price, '₹');
  document.getElementById('pill-area-label').textContent = `${target.name} · ₹/sq ft`;
  document.getElementById('pill-horizon').textContent = state.offset === 0 ? 'Now' : `+${state.offset}Y`;
  document.getElementById('pill-delta').textContent = `+₹${diff.toLocaleString('en-IN')} (+${pct}%)`;

  document.getElementById('horizon-slider').value = state.offset;
  document.querySelectorAll('.offset-pill').forEach((btn) => {
    const active = parseInt(btn.dataset.offset, 10) === state.offset;
    btn.className = `offset-pill px-2.5 py-1 rounded-full text-[11px] font-semibold tabular-nums transition-all ${active ? 'bg-slate-950 text-white' : 'text-slate-700 hover:bg-white/80'}`;
  });

  // Separate Analysis View
  document.getElementById('analysis-title').textContent = `${target.name} · ${BASE_YEAR}–2031 Valuation Analysis`;
  document.getElementById('analysis-subtitle').textContent = `${target.category} · Bengaluru`;
  document.getElementById('an-price').textContent = `₹${price.toLocaleString('en-IN')} / sq ft`;
  document.getElementById('an-diff').textContent = `+₹${diff.toLocaleString('en-IN')} (+${pct}% vs 2026)`;
  document.getElementById('an-elasticity').textContent = '+0.48 / km';
  document.getElementById('an-metro-dist').textContent = target.metroKm + ' km';
  document.getElementById('an-landmarks-count').textContent = state.liveLandmarks.length;
  document.getElementById('an-builtup').textContent = builtNow + '%';
  document.getElementById('an-r2').textContent = 'R² = 0.81';
  document.getElementById('an-cagr-badge').textContent = `CAGR ${(target.cagr * 100).toFixed(1)}%`;

  analysisChart.data.datasets[0].data = OFFSETS.map((o) => calcProjected(target.basePrice, target.cagr, o).price);
  analysisChart.data.datasets[0].pointRadius = OFFSETS.map((o) => (o === state.offset ? 6 : 3.5));
  analysisChart.data.datasets[0].pointBackgroundColor = OFFSETS.map((o) => (o === state.offset ? '#f97316' : '#0f172a'));
  analysisChart.update('none');

  const drivers = [
    { label: 'Metro Station Proximity', pct: 38 },
    { label: 'Built-Up & Satellite Expansion', pct: 27 },
    { label: 'Commercial & Tech Hub Access', pct: 22 },
    { label: 'Road & Arterial Connectivity', pct: 13 }
  ];
  document.getElementById('an-drivers').innerHTML = drivers.map((d) => `
    <div>
      <div class="flex justify-between text-xs mb-1">
        <span class="text-slate-800 font-medium">${d.label}</span>
        <span class="text-slate-950 font-bold tabular-nums">${d.pct}%</span>
      </div>
      <div class="w-full h-2 bg-slate-200/70 rounded-full overflow-hidden">
        <div class="h-full rounded-full transition-all duration-500" style="width:${d.pct}%; background:#0f172a;"></div>
      </div>
    </div>
  `).join('');

  const lmListEl = document.getElementById('an-landmark-list');
  lmListEl.innerHTML = state.liveLandmarks.length
    ? state.liveLandmarks.map((l) => `<div class="flex justify-between p-2 rounded-xl bg-slate-100/80"><span class="font-medium text-slate-800">${l.name}</span><span class="uppercase text-[10px] font-bold text-slate-500">${l.kind}</span></div>`).join('')
    : '<div class="text-slate-500">Select or search any location to sync live nearby OSM landmarks.</div>';

  renderMapOverlays();
}

// Select Location (with live Nominatim resolution if exact coords aren't cached)
async function selectLocationItem(item) {
  state.maskedArea = null;
  document.getElementById('search-input').value = item.name;
  document.getElementById('search-dropdown').classList.add('hidden');
  document.getElementById('directory-dropup-panel').classList.add('hidden');
  closeAnalysisView();

  let targetCoords = item.coords;
  if (!item.hasExactCoords) {
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(item.name + ', Bengaluru, Karnataka, India')}`);
      const data = await res.json();
      if (data && data.length > 0) {
        targetCoords = [parseFloat(data[0].lat), parseFloat(data[0].lon)];
      }
    } catch (e) { /* keep zone center fallback */ }
  }

  state.activeArea = { ...item, coords: targetCoords };
  map.flyTo(targetCoords, 14, { duration: 0.75 });
  renderUI();
  fetchLiveLandmarks(targetCoords[0], targetCoords[1]);
}

// Search Bar Autocomplete across ALL 250+ items
const searchInput = document.getElementById('search-input');
const searchDropdown = document.getElementById('search-dropdown');

function renderSearchDropdown(list) {
  if (!list.length) {
    searchDropdown.classList.add('hidden');
    return;
  }
  searchDropdown.innerHTML = list.slice(0, 30).map((item, idx) => `
    <button type="button" data-idx="${idx}" class="w-full text-left px-4 py-2 text-xs hover:bg-white/90 flex items-center justify-between border-b border-slate-200/40 last:border-0">
      <div>
        <div class="font-bold text-slate-900">${item.name}</div>
        <div class="text-[10px] text-slate-500">${item.category}</div>
      </div>
      <span class="text-[11px] font-semibold text-slate-700 tabular-nums">₹${item.basePrice.toLocaleString('en-IN')}</span>
    </button>
  `).join('');
  searchDropdown.classList.remove('hidden');

  searchDropdown.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => selectLocationItem(list[parseInt(btn.dataset.idx, 10)]));
  });
}

function getFilteredLocations(query = '') {
  return ALL_LOCATIONS.filter((loc) => {
    const matchCat = state.categoryFilter === 'all' || loc.group === state.categoryFilter;
    const matchQ = !query || loc.name.toLowerCase().includes(query) || loc.category.toLowerCase().includes(query);
    return matchCat && matchQ;
  });
}

searchInput.addEventListener('input', () => {
  renderSearchDropdown(getFilteredLocations(searchInput.value.trim().toLowerCase()));
});
searchInput.addEventListener('focus', () => {
  renderSearchDropdown(getFilteredLocations(searchInput.value.trim().toLowerCase()));
});
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const q = searchInput.value.trim();
    const matches = getFilteredLocations(q.toLowerCase());
    if (matches.length) selectLocationItem(matches[0]);
    else if (q) selectLocationItem({ name: q, category: 'Custom Bengaluru Search', group: 'Areas', coords: [12.9716, 77.5946], hasExactCoords: false, basePrice: 12500, cagr: 0.085, metroKm: 1.2, builtUp: 78 });
  }
});
document.getElementById('search-btn').addEventListener('click', () => {
  const q = searchInput.value.trim();
  const matches = getFilteredLocations(q.toLowerCase());
  if (matches.length) selectLocationItem(matches[0]);
  else if (q) selectLocationItem({ name: q, category: 'Custom Bengaluru Search', group: 'Areas', coords: [12.9716, 77.5946], hasExactCoords: false, basePrice: 12500, cagr: 0.085, metroKm: 1.2, builtUp: 78 });
});

// Categorized Drop-Up Directory (Browse All 250+ Locations)
function renderDirectoryDropup() {
  const tabsEl = document.getElementById('dir-tabs');
  const itemsEl = document.getElementById('dir-items');
  document.getElementById('dir-count-badge').textContent = `${ALL_LOCATIONS.length} locations`;

  tabsEl.innerHTML = DIRECTORY_GROUPS.map((grp) => {
    const active = grp === state.activeDirGroup;
    return `<button type="button" data-grp="${grp}" class="px-2.5 py-1 rounded-full text-[10px] font-semibold transition-all ${active ? 'bg-slate-950 text-white' : 'bg-white/80 text-slate-700 hover:bg-white'}">${grp}</button>`;
  }).join('');

  tabsEl.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      state.activeDirGroup = btn.dataset.grp;
      renderDirectoryDropup();
    });
  });

  const groupItems = ALL_LOCATIONS.filter((l) => l.group === state.activeDirGroup);
  itemsEl.innerHTML = groupItems.map((item, idx) => `
    <button type="button" data-gidx="${idx}" class="text-left px-2.5 py-1.5 rounded-xl bg-white/80 hover:bg-slate-950 hover:text-white text-[11px] font-medium text-slate-800 transition-all truncate border border-slate-200/60">
      ${item.name}
    </button>
  `).join('');

  itemsEl.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => selectLocationItem(groupItems[parseInt(btn.dataset.gidx, 10)]));
  });
}

// Drop-Up & Modal Toggles
const dirPanel = document.getElementById('directory-dropup-panel');
const layersPanel = document.getElementById('dropup-panel');

document.getElementById('directory-dropup-btn').addEventListener('click', (e) => {
  e.stopPropagation();
  layersPanel.classList.add('hidden');
  dirPanel.classList.toggle('hidden');
  renderDirectoryDropup();
});

document.getElementById('dropup-btn').addEventListener('click', (e) => {
  e.stopPropagation();
  dirPanel.classList.add('hidden');
  layersPanel.classList.toggle('hidden');
});

document.getElementById('nav-layers-btn').addEventListener('click', (e) => {
  e.stopPropagation();
  dirPanel.classList.add('hidden');
  layersPanel.classList.toggle('hidden');
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('#search-input') && !e.target.closest('#search-dropdown')) searchDropdown.classList.add('hidden');
  if (!e.target.closest('#directory-dropup-panel') && !e.target.closest('#directory-dropup-btn')) dirPanel.classList.add('hidden');
  if (!e.target.closest('#dropup-panel') && !e.target.closest('#dropup-btn') && !e.target.closest('#nav-layers-btn')) layersPanel.classList.add('hidden');
});

// Separate Analysis View
const analysisView = document.getElementById('analysis-view');
function openAnalysisView() { analysisView.classList.remove('hidden'); analysisChart.resize(); analysisChart.update(); }
function closeAnalysisView() { analysisView.classList.add('hidden'); }

document.getElementById('pill-info-btn').addEventListener('click', openAnalysisView);
document.getElementById('nav-analysis-btn').addEventListener('click', openAnalysisView);
document.getElementById('back-to-map-btn').addEventListener('click', closeAnalysisView);
document.getElementById('nav-map-btn').addEventListener('click', closeAnalysisView);

// Filters & Layer Checkboxes
document.getElementById('filter-category').addEventListener('change', (e) => {
  state.categoryFilter = e.target.value;
  renderSearchDropdown(getFilteredLocations(searchInput.value.trim().toLowerCase()));
});
document.getElementById('filter-landmarks').addEventListener('change', (e) => {
  state.landmarkFilter = e.target.value;
  renderMapOverlays();
});
document.getElementById('chk-metro').addEventListener('change', (e) => { state.layers.metro = e.target.checked; renderMapOverlays(); });
document.getElementById('chk-landmarks').addEventListener('change', (e) => { state.layers.landmarks = e.target.checked; renderMapOverlays(); });
document.getElementById('chk-infra').addEventListener('change', (e) => { state.layers.infra = e.target.checked; renderMapOverlays(); });
document.getElementById('chk-satellite').addEventListener('change', (e) => {
  if (e.target.checked) { map.removeLayer(lightTileLayer); satTileLayer.addTo(map); }
  else { map.removeLayer(satTileLayer); lightTileLayer.addTo(map); }
});
document.getElementById('reset-blr-btn').addEventListener('click', () => {
  map.flyTo([12.9716, 77.5946], 11, { duration: 0.7 });
  layersPanel.classList.add('hidden');
});

// Polygon Masking Tool
const mapEl = document.getElementById('map');
const drawBtn = document.getElementById('draw-mask-btn');
const finishBtn = document.getElementById('finish-mask-btn');
const clearBtn = document.getElementById('clear-mask-btn');
const drawBanner = document.getElementById('draw-banner');

function startDraw() {
  closeAnalysisView();
  state.drawing = true;
  state.drawPoints = [];
  drawPreviewLayer.clearLayers();
  mapEl.classList.add('drawing-cursor');
  drawBtn.classList.add('hidden');
  finishBtn.classList.remove('hidden');
  drawBanner.classList.remove('hidden');
}

function finishDraw() {
  if (state.drawPoints.length < 3) {
    state.drawing = false;
    drawPreviewLayer.clearLayers();
    mapEl.classList.remove('drawing-cursor');
    finishBtn.classList.add('hidden');
    drawBtn.classList.remove('hidden');
    drawBanner.classList.add('hidden');
    return;
  }
  state.drawing = false;
  mapEl.classList.remove('drawing-cursor');
  finishBtn.classList.add('hidden');
  drawBtn.classList.remove('hidden');
  clearBtn.classList.remove('hidden');
  drawBanner.classList.add('hidden');
  drawPreviewLayer.clearLayers();
  maskLayer.clearLayers();

  const poly = L.polygon(state.drawPoints, { color: '#0f172a', weight: 2, fillColor: '#f97316', fillOpacity: 0.34 }).addTo(maskLayer);
  const center = poly.getBounds().getCenter();
  state.maskedArea = {
    ...state.activeArea,
    name: `Masked Zone (${state.activeArea.name})`,
    coords: [center.lat, center.lng],
    polygonLayer: poly
  };
  poly.bindTooltip(buildMaskTooltip(state.maskedArea, state.offset), { sticky: true, direction: 'top', opacity: 0.98 });
  poly.on('click', openAnalysisView);
  renderUI();
  fetchLiveLandmarks(center.lat, center.lng);
}

drawBtn.addEventListener('click', startDraw);
document.getElementById('nav-draw-btn').addEventListener('click', startDraw);
finishBtn.addEventListener('click', finishDraw);
clearBtn.addEventListener('click', () => {
  maskLayer.clearLayers();
  state.maskedArea = null;
  clearBtn.classList.add('hidden');
  renderUI();
});

map.on('click', (e) => {
  if (!state.drawing) return;
  state.drawPoints.push([e.latlng.lat, e.latlng.lng]);
  drawPreviewLayer.clearLayers();
  L.polyline(state.drawPoints, { color: '#0f172a', weight: 2, dashArray: '5, 5' }).addTo(drawPreviewLayer);
  state.drawPoints.forEach((pt) => L.circleMarker(pt, { radius: 4, color: '#0f172a', fillColor: '#f97316', fillOpacity: 1, weight: 2 }).addTo(drawPreviewLayer));
});
map.on('dblclick', () => { if (state.drawing && state.drawPoints.length >= 3) finishDraw(); });

// Slider & Play Controls
document.getElementById('horizon-slider').addEventListener('input', (e) => {
  state.offset = parseInt(e.target.value, 10);
  renderUI();
});
document.querySelectorAll('.offset-pill').forEach((btn) => {
  btn.addEventListener('click', () => {
    state.offset = parseInt(btn.dataset.offset, 10);
    renderUI();
  });
});
document.getElementById('play-btn').addEventListener('click', () => {
  if (state.playing) {
    clearInterval(state.playTimer);
    state.playing = false;
    document.getElementById('play-icon').innerHTML = '&#9654;';
    document.getElementById('play-text').textContent = 'Play +5Y';
  } else {
    state.playing = true;
    document.getElementById('play-icon').innerHTML = '&#9646;&#9646;';
    document.getElementById('play-text').textContent = 'Pause';
    state.playTimer = setInterval(() => {
      state.offset = (state.offset + 1) % OFFSETS.length;
      renderUI();
    }, 1200);
  }
});

// Initial render
renderUI();
fetchLiveLandmarks(state.activeArea.coords[0], state.activeArea.coords[1]);
