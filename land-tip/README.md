# UrbanAlpha — Bengaluru GeoAI Property & Infrastructure Intelligence

## Project Structure
- `index.html` — Full-screen Swiss-editorial glassmorphic map + separate Analysis view
- `src/styles/main.css` — Helvetica Neue typography, frosted/smoked glassmorphism, and keyframe animations
- `src/data/bengaluruLocations.js` — Complete 10-category Bengaluru database (250+ areas, tech parks, metro stations, malls, lakes, universities, roads)
- `src/app.js` — Leaflet map, Nominatim geocoding, Overpass live landmark sync, custom polygon masking, 5-year forecast slider, and Chart.js causality view

## How to Run in VS Code
1. Open this folder in **VS Code**.
2. Because `index.html` uses ES modules (`<script type="module">`), serve it with a local dev server:
   - **Option A:** Install the **Live Server** VS Code extension and click **Go Live** on `index.html`.
   - **Option B:** Run `npx serve .` or `python3 -m http.server 5173` in the VS Code terminal and open `http://localhost:5173`.
3. To connect your **FastAPI** backend later, replace the `calcProjected` / `fetchOverpassLandmarks` calls in `src/app.js` with `fetch("http://localhost:8000/api/...")`.
