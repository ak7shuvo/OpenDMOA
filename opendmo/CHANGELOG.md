# Changelog

## 2.0.0 — 2026-10-03

Complete rebuild of OpenDMO v0.6 into a single-process, local-first research platform.

### Added
- **Single runtime**: FastAPI serves the API and the pre-built static UI; launchers for Windows, macOS and
  Linux plus `run.py` (venv creation, pinned dependencies, free port, browser).
- **Method registry** with versioned, documented, unit-tested methods: Cifuentes carrying capacity
  (PCC/RCC/ECC with editable correction factors), capacity utilisation, tourism pressure index, ratios,
  growth/CAGR, site condition index, resident net support, climate anomaly, landslide and flood
  susceptibility screens, ecosystem stress index, response-readiness score, Local Economic Leakage &
  Sustainable Tourism Impact Index (leakage, local capture, LM3), local employment, demand projection
  scenarios, sustainability screen.
- **Forecasting**: seasonal-naïve, Holt-Winters (additive) and linear trend in numpy, with prediction intervals
  and MAE/RMSE/MAPE/MASE hold-out back-tests.
- **CSV/JSON import wizard** with detection, long/wide mapping, preview, dry-run row-level validation and
  idempotent commits (file hash in provenance); CSV templates; CSV/JSON export everywhere.
- **Reproducibility**: unified append-only runs, re-run with reproduction check, run bundles, method snapshots,
  citation helper (CITATION.cff, BibTeX), auto-generated methodology, indicator glossary.
- **Registers**: heritage assets, early warnings, incidents, readiness checklist, infrastructure pipeline,
  publications; policy-brief generator (Markdown/HTML).
- **Control Board**: health, DEMO seed packs per destination, reset, backup/restore, export-all, destinations,
  method/model switches, GitHub model install, run history, audit log, settings, diagnostics.
- **UI**: Petra visual system (dark + light), JetBrains Mono bundled, command palette, KPI cells with
  status/source/confidence/timestamp, sortable/filterable data tables, SVG charts, offline schematic GIS with
  GeoJSON upload, first-run onboarding.
- Optional PostgreSQL + PostGIS via docker-compose; CI on Ubuntu/Windows/macOS, PostgreSQL job, browser gate.

### Changed
- CONTRACT.md visual system superseded (see docs/DECISIONS.md D-004); four cores, IA chain and data-integrity
  rules kept. Control Board lives under System.
- Frontend demo fixtures removed; DEMO data now lives in the database, flagged and removable.

### Security
- Model packages: data-only artifacts, executable files rejected, pickle refused by default, requirements
  never installed, safe archive extraction. CSP `default-src 'self'`; Swagger UI disabled (CDN).
