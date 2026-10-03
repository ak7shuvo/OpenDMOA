# OpenDMO User Guide

This guide covers the everyday workflow: choosing a destination and time range, importing data, running
methods, reading provenance, and operating the Control Board. Start OpenDMO with the launcher for your system
(see the README quick start).

## 1. The shell

- **Destination selector** (top left): every core, KPI, chart, import and run uses this destination.
  Add destinations under *System › Control Board › Destinations* (or the *+ Destination* link).
- **Time range** (12M / 24M / 36M / ALL / CUSTOM): filters every chart, KPI and "fill from data". Preset
  windows end at the latest observed period. Yearly values belong to any window they overlap.
- **DEMO badge**: shown whenever the current view uses synthetic seed-pack data.
- **Search** (**Ctrl/Cmd+K**): jump to any page, module, method, destination, or run an action.
- **Theme**: dark (default) or light creamy. **«** in the sidebar collapses it.

KPI cells show: value and unit, status flag (ok / watch / risk where thresholds are defined — see the
glossary), change vs the previous equal-length window, sparkline, source dataset and version, confidence
(from the dataset quality score), the period covered and the last update time. When both your own dataset and
a DEMO dataset exist for the same kind, **your data is used**.

## 2. Importing CSV / JSON (the main way to feed OpenDMO)

Open **Import CSV / JSON** in the sidebar.

1. **Destination & dataset** — pick an existing dataset or *Create a new dataset* from a template
   (visitor flow, site condition, sentiment, weather, hazard factors, ecosystem, economy, or *custom*).
   Download the matching CSV template (wide or long) if you are starting from scratch.
2. **Upload** — drop a `.csv`, `.tsv`, `.txt` or `.json` file (≤ 50 MB) or paste text. OpenDMO detects
   the delimiter (`,` `;` tab `|`), the encoding (UTF-8, UTF-8 with BOM, UTF-16, Windows-1252) and whether
   the first row is a header. Override any of these and *Re-detect* if needed.
3. **Map columns** — choose the layout:
   - **wide**: one row per period, one column per variable (`period,visitors,daily_peak`)
   - **long**: one row per value (`period,variable,value[,unit][,quality_flag]`)

   Pick the period column; OpenDMO accepts `2025`, `2025-Q3`, `2025-07`, `2025/7`, `07/2025`, `Jul 2025`,
   `2025-07-14`, `14/07/2025` (choose DD/MM or MM/DD) and ISO timestamps. Choose the decimal separator
   (`1,234.5` or `1.234,5`). Map each column to a variable or *ignore*; tick *Add unknown variables* to
   extend the dataset definition. The first 50 rows are previewed.
4. **Dry-run validation** — nothing is written yet. You get counts (insert / update / unchanged) and a
   row-level issue list with the file line number:

   | Check | Level | Meaning |
   |---|---|---|
   | `period_invalid` | error | the date/period cannot be parsed |
   | `value_not_numeric` | error | the cell is not a number |
   | `out_of_range` | error | outside the variable's min/max (e.g. negative visitors, occupancy > 100 %) |
   | `duplicate` | error | the same period + variable appears twice in the file (first kept) |
   | `variable_unknown` | error | not defined for this dataset (map it, or allow new variables) |
   | `value_missing` | warning | empty / `NA` cell skipped |
   | `required_missing` | warning | a required variable has no values in the file |
   | `unit_mismatch` | warning | unit column differs from the defined unit (no conversion is done) |
   | `value_not_integer` | warning | a count with decimals |
   | `outlier` | warning | modified z-score > 3.5 within the file; the value is stored with flag `outlier` |
   | `mixed_periods` | warning | e.g. months and years mixed in one file |
5. **Commit** — blocked while errors exist unless you tick *Skip invalid cells*. Choose whether existing
   values are updated or kept. The commit is **idempotent**: importing the exact same file again changes
   nothing; overlapping files update values instead of duplicating rows. The SHA-256 of the file is stored in
   the dataset provenance and the original file is archived in `data/uploads/`.

Try it with `samples/DEMO_messy_gate_counts.csv` (semicolons, `Jan 2025` dates, comma decimals and one bad value).

**Datasets** (Research & Policy Lab › Dataset Explorer) are versioned and metadata-driven. Actions: *Validate*
(recomputes the 0–100 quality score and marks it validated), *New version* (copies observations into v+1),
*Archive* (immutable), export as long/wide CSV or JSON, download a template, delete. Quality score =
completeness over the expected period grid × penalties for outliers/estimated values, minus penalties for
missing required variables and range violations (≥ 80 high, ≥ 60 moderate, else low).

## 3. Running methods

Every module has *method runners* generated from the registry. Inputs marked **⛁** were filled from your
datasets for the selected destination and time range (the hint shows the aggregation, variable, n and DEMO
status). Edit anything, then **Run calculation**. The result appears with its **provenance block**:
run id, method id + version, dataset id + version + content hash, per-input sources, data quality,
software version and timestamp. Buttons: **Re-run** (reports whether the identical result was reproduced),
**Run bundle (.zip)** (run.json, inputs.csv, outputs.csv, methodology.md, dataset.csv, CITATION.bib),
JSON, CSV, and **Save as scenario**.

- **Carrying capacity** (Observatory): edit area, space per visitor, hours, visit duration, management
  capacity and the correction-factor table. ECC is compared with peak-day visitors.
- **Forecasts** (Future & Economy › Demand Forecast): pick a dataset variable, a method and the horizon;
  *Compare all three methods* fits seasonal-naïve, Holt-Winters and linear trend and shows hold-out MAE,
  RMSE, MAPE and MASE side by side. Choose **ALL** in the time range for the longest history.
- **Scenarios**: save any successful run, then tick two or more under *Scenarios* to compare inputs and outputs.
- **Policy briefs** (Research & Policy Lab): tick runs, add your summary and recommendations, generate,
  preview, and download Markdown or print-ready HTML. DEMO-derived figures are flagged in the brief.

Run history (Lab or Control Board) lists every run, filterable by kind, method, status and destination.

## 4. Control Board (System)

| Tab | What you can do |
|---|---|
| Overview | backend & database health, engine and file path, store sizes, record counts; quick actions; **Reset database** (type `RESET`; a safety backup is written first) |
| Demo & Data | load / remove each DEMO seed pack, *Seed all*, *Remove all demo data* (your own data is never touched) |
| Destinations | add / edit destinations (name, region, WGS84 coordinates, area); pilots cannot be deleted |
| Backup & Export | download a single `.zip` backup (all tables as portable JSON + model store + archived imports); restore (type `RESTORE`; current state backed up first); export everything as CSV/JSON |
| Methods & Models | enable/disable calculations; **install a model package from a GitHub URL** (explicit action; validated, registered *disabled*); enable/disable models |
| Run History | all runs across destinations |
| Audit Log | every administrative action (imports, seeds, resets, restores, installs, toggles, settings) |
| Settings | theme, units, date format, currency, default range; **port** and **data directory** (take effect after restart; stored in `opendmo.settings.json`) |
| Diagnostics | version, OS, Python, package versions, database, disk — *Copy report* for support requests |

## 5. GIS

The GIS panel is an offline schematic (bundled outline, rivers and towns; no tiles). Click a destination to
select it; *Site* zooms to the selected destination. Upload GeoJSON (WGS84 / EPSG:4326) as a layer with
*+ GeoJSON*; toggle layers on/off. Heritage assets with coordinates appear as triangles coloured by condition.

## 6. Where your data lives

`data/opendmo.db` (SQLite), `data/models/`, `data/uploads/` (archived import files), `data/backups/`.
Nothing is sent anywhere. The only outbound request OpenDMO can make is an explicit model install from GitHub.
