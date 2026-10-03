# OpenDMO v2.0 — Open Destination Management & Analytics Platform

OpenDMO is an open-source, **local-first** research workstation for destination management organisations (DMOs),
university researchers and policymakers. Install it from a ZIP, load a CSV, run a documented method and get a
fully traceable, exportable result. Pilot context: Bangladesh tourism — **Jaflong**, **Ratargul Swamp Forest**
(Sylhet), **Sajek Valley** and **Bandarban** (Chittagong Hill Tracts).

- **Easy first:** one launcher, no configuration, guided 3-step onboarding, CSV import wizard.
- **Powerful second:** versioned method registry (Cifuentes carrying capacity, leakage/LM3/STII, hazard
  screens, Holt-Winters forecasting with back-tests…), reproducible runs, run bundles, policy briefs, citations.
- **Honest:** DEMO data is always badged; composite indices are labelled *screening indicators*; every number
  shows its data, method, version, timestamp and data quality.
- **Offline:** no CDN, no telemetry, no external fonts or map tiles. Data stays on your machine.

---

## 5-minute quick start

You need **Python 3.11 or newer**. Nothing else (no Node.js, no database server).

1. Download `release/opendmo-v2.0.zip` and extract it anywhere (e.g. your Documents folder).
2. Start OpenDMO:

| System | Do this |
|---|---|
| **Windows 10/11** | Double-click `start-windows.bat`. If Python is missing, the window tells you where to get it (tick *Add python.exe to PATH* during setup). |
| **macOS** | Double-click `start-mac.command`. The first time, right-click › *Open* to allow it. If Python is missing: install it from python.org or `brew install python@3.12`. |
| **Linux** | Run `./start-linux.sh` in a terminal (Debian/Ubuntu may need `sudo apt install python3-venv`). |
| **Any** | `python run.py` (or `python3 run.py`) from the extracted folder. |

3. The first start creates a private environment (`.venv`) and installs pinned dependencies — about a minute,
   internet needed **once**. Later starts take a few seconds and work fully offline.
   (For air-gapped machines put wheels in a `wheels/` folder next to `run.py`; they are used automatically.)
4. Your browser opens at `http://127.0.0.1:8000` (the next free port is used if 8000 is busy).
5. Follow **Get started in three steps**: pick a destination → *Load DEMO data* or *Import your CSV* →
   *Run carrying capacity*. Done — open *Observatory › Carrying Capacity* to inspect the assumptions and provenance.

Stop OpenDMO with **Ctrl+C** in the launcher window (or close it). Your data lives in the `data/` folder
(SQLite database, model store, archived imports, backups) — back it up from *System › Control Board › Backup*.

Launcher options: `python run.py --port 8123 --no-browser --data-dir D:\research\opendmo-data`.

## What is inside

Information chain: **LOCATION › TIME › OBSERVATION › CHANGE › RISK › FORECAST › SCENARIO › DECISION**.
The destination and time-range selectors at the top are shared by every page.

| Core | Modules |
|---|---|
| **01 Destination Observatory** | Visitor flow & crowding · **Carrying Capacity Engine** (Cifuentes PCC/RCC/ECC, editable factors) · Site condition · Community sentiment · Cultural & natural **heritage asset registry** |
| **02 Climate & Risk** | Weather & hydrology · Flood & landslide susceptibility screens · Ecosystem stress · **Crisis & Disaster Resilience Command** (early warnings, incident log, readiness checklist) |
| **03 Future & Economy** | Revenue signals · **Local Economic Leakage & Sustainable Tourism Impact Index** (leakage, local capture, LM3) · Demand forecasting (seasonal-naïve, Holt-Winters, linear trend; MAE/RMSE/MAPE/MASE back-tests) · Saved scenarios side-by-side · Infrastructure pipeline |
| **04 Research & Policy Lab** | Dataset explorer · Methodology registry · Model lab · Run history · Policy-brief generator (Markdown/HTML) · Publication queue · Glossary & citation · VR/AR (roadmap placeholder only) |
| **System › Control Board** | Health, DB engine & path · seed/remove DEMO data · reset (typed confirmation) · backup/restore (.zip) · export all · destinations · enable/disable methods & models · install a model from GitHub · run history · audit log · settings · diagnostics |

Also: CSV/JSON **import wizard** (auto-detects delimiter/encoding/header, long and wide layouts, column mapping,
50-row preview, dry-run with row-level errors and warnings, idempotent commit), downloadable CSV templates,
CSV/JSON export everywhere, offline schematic GIS with GeoJSON upload, command palette (**Ctrl/Cmd+K**),
dark (default) and light creamy themes.

## Mock vs real-ready — a plain statement

| Part | Status |
|---|---|
| Calculations, forecasts, validation, provenance, import, backup/restore, briefs | **Real.** Production code paths with unit tests and known-value verification cases. They compute on whatever data you load. |
| DEMO seed packs (all four destinations) | **Synthetic.** Deterministically generated, plausible in shape (seasonality, monsoon, COVID-19 dip) but **not observations**. Always badged DEMO; removable per pack. Never cite them. |
| Destination coordinates, gauges, danger levels, capacity defaults | **Indicative.** Approximate public values used as editable defaults; verify before research use. |
| Bundled model `demo-tourism-demand` | **Demo.** Illustrative coefficients, no training data; exists to exercise the safe model runtime. |
| GIS basemap | **Schematic.** Hand-simplified outline for orientation; not survey-grade, not an official boundary. |
| Composite indices (pressure, STII, hazard screens, ecosystem stress, readiness, site condition, sentiment) | **Screening indicators** with documented formulas and weights — not certifications or regulatory determinations. |
| Live data feeds (BMD weather, BWDB gauges, satellite imagery, booking systems) | **Not connected.** OpenDMO never implies live connectivity. Import exports from those systems as CSV. |
| VR/AR | **Roadmap placeholder only.** No functionality. |

A real deployment additionally needs: real observation datasets and survey protocols, locally validated
thresholds and weights, calibrated hazard maps, data-sharing agreements, and — for multi-user servers —
authentication and TLS (OpenDMO is a single-user local application; it binds to 127.0.0.1 by default).

## For developers

```bash
# backend (Python 3.11+)
cd backend && python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest                                                 # 117 tests (calculations, import, provenance, API)
uvicorn app.main:app --reload --port 8000

# frontend (Node 22) — talks to the backend on :8000 via .env.development
cd frontend && npm ci && npm run dev                              # http://localhost:3000
npm run typecheck && npm run lint && npm run build

# release
python scripts/build_release.py        # builds the UI, bundles it into the backend, writes release/opendmo-v2.0.zip
python scripts/smoke_test.py           # boots via run.py, checks /api/health and the UI
node scripts/ui_check.mjs http://127.0.0.1:8000   # browser gate (needs Playwright + Chromium)
python -m app.docs_gen                 # regenerate docs/CALCULATIONS.md, docs/API.md, CITATION.cff (from backend/)
```

Optional PostgreSQL + PostGIS: `docker compose up -d db`, `pip install -r backend/requirements-postgres.txt`,
then start with `OPENDMO_DATABASE_URL=postgresql+psycopg://opendmo:opendmo@localhost:5432/opendmo`.
The full test suite also runs against PostgreSQL (`OPENDMO_TEST_DATABASE_URL=… pytest`).

Layout: `backend/` (FastAPI, SQLAlchemy, numpy; serves the built UI from `backend/app/static`), `frontend/`
(Next.js static export — interface only), `docs/`, `samples/` (DEMO CSVs), `database/schema.sql`,
`scripts/`, launchers, `release/`.

## Documentation

[USER-GUIDE](docs/USER-GUIDE.md) (CSV import, Control Board, cores) · [CALCULATIONS](docs/CALCULATIONS.md) (generated from the registry)
· [API](docs/API.md) (generated from the routes) · [MODELS](docs/MODELS.md) · [DECISIONS](docs/DECISIONS.md)
· [CONTRACT](CONTRACT.md) · [CHANGELOG](CHANGELOG.md) · [CITATION.cff](CITATION.cff)

## Known limitations

- PostgreSQL is supported and tested; the PostGIS `gis_features` view in `database/schema.sql` is provided but
  GIS layers are stored as GeoJSON, and spatial queries are not used by the app itself.
- The map is a schematic SVG (no tiles by design). Large GeoJSON layers (> 8 MB) must be simplified first.
- Unit handling is validation-only: mismatched units produce warnings; no automatic conversion.
- Holt-Winters parameters are optimised on a coarse grid (0.05–0.9); multiplicative seasonality is not offered.
- Single-user, local application: no authentication, no concurrent multi-user editing.
- Model packages support the `json-linear` format only (pickle refused by default by design).
- The macOS and Windows launchers are covered by CI on GitHub-hosted runners; they could not be exercised
  interactively during development (Linux was).

## Licence and citation

MIT licence — see [LICENSE](LICENSE). If you use OpenDMO in research, cite it via [CITATION.cff](CITATION.cff)
and cite each method's references (copy BibTeX from *Research & Policy Lab › Glossary & Citation*).
