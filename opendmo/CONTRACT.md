# OpenDMO — Product & Design Contract (v2.0)

**OpenDMO** — *Open Destination Management & Analytics Platform*

Source of truth for what OpenDMO is and what must not drift. v2.0 supersedes the v0.6 contract
(`baseline/opendmo-local/frontend/CONTRACT.md`). **Changed in v2:** §5 visual system (replaced by the Petra
system, see docs/DECISIONS.md D-004) and §3/§7 scope (four cores extended; Control Board added under System).
§2 information architecture and §6 data-integrity rules are carried over unchanged in intent.

## 1. What this is

An open-source, local-first research workstation for DMOs, university researchers and policymakers working on
tourism, climate and local economies — piloted in Bangladesh (Sylhet and the Chittagong Hill Tracts).
Easy first, powerful second. It is **not** a marketing site, a generic SaaS admin panel, or a live
real-time system.

## 2. Information architecture (fixed)

```
LOCATION → TIME → OBSERVATION → CHANGE → RISK → FORECAST → SCENARIO → DECISION
```

Every module moves the user along this chain. The destination and time-range selectors are global and stay
synced on every page. GIS is the shared spatial layer — not a core.

## 3. The four cores (fixed set, fixed order — no fifth core)

| # | Core | Modules |
|---|---|---|
| 01 | **Destination Observatory** | Visitor Flow & Crowd Intelligence · Destination Carrying Capacity Engine (Cifuentes PCC/RCC/ECC) · Site Condition · Community Sentiment · Cultural & Natural Heritage Asset Registry |
| 02 | **Climate & Risk** | Weather Observations · Flood & Landslide Susceptibility · Ecosystem Stress · Crisis & Disaster Resilience Command |
| 03 | **Future & Economy** | Revenue Signals · Local Economic Leakage & Sustainable Tourism Impact Index · Visitor-Demand Forecasting · Scenario Comparison · Infrastructure Pipeline |
| 04 | **Research & Policy Lab** | Dataset Explorer · Methodology Registry · Model Lab · Run History · Policy Briefs · Publication Queue · Glossary & Citation · VR/AR (roadmap placeholder only) |

**System › Control Board** operates the installation (data, backup, registry, audit, settings, diagnostics).
It is part of System, never a core. The CSV import wizard is a Data tool shared by all cores.

## 4. Destinations

Pilots (cannot be deleted): **Jaflong**, **Ratargul Swamp Forest**, **Sajek Valley**, **Bandarban**.
Adding destinations is a GUI action (Control Board › Destinations).

## 5. Visual system — Petra (supersedes v0.6 §5)

| Token | Dark (default) | Light (creamy) | Use |
|---|---|---|---|
| `--black` | `#0E0E10` | `#F4ECDD` | app background |
| `--panel` | `#16161A` | `#FBF6EC` | panels |
| `--panel-alt` | `#1D1D22` | `#EFE5D3` | hover / header surfaces |
| `--cream` | `#F4ECDD` | `#16161A` | primary text |
| `--cream-dim` | `#BDB4A3` | `#4A453D` | secondary text |
| `--red` | `#B3202A` | `#B3202A` | brand, primary actions, selection |
| `--red-bright` | `#D8343F` | `#9E1B24` | active states, focus |
| `--ok` / `--watch` / `--risk` | `#6DBE8C` / `#E3A94F` / `#F2555A` | `#2D7A4C` / `#9A630A` / `#C0282F` | status flags only |

**Type:** JetBrains Mono everywhere, bundled locally (no external fonts), tabular numerals.
**Rules:** hairline 1 px borders; radius 4–6 px; no heavy shadows, no neon, no glow, no decorative gradients;
dense but calm; status is conveyed by flags, not decoration. Works from 1280 px to 4K: collapsible sidebar,
tables scroll in their own container, no horizontal page scroll.

## 6. Data integrity (non-negotiable, carried over)

- DEMO / synthetic data is always badged **DEMO** and never presented as observations.
- Composite indices are labelled **screening indicators** — not certifications or regulatory determinations.
- Every result is traceable: data (dataset id, version, hash), variables, formula/model and version,
  parameters, software version, timestamp and data quality.
- Never claim or imply a live connection; timestamps describe the data, not "now".
- The backend owns all logic; no equation lives in a React component.
- Local-first and offline: no CDN, no telemetry, no remote tiles, fonts or scripts at runtime.

## 7. Done means

All quality gates in the README pass; each core's modules are distinct and functional; every calculation is
registered, versioned, documented and unit-tested; the release ZIP runs on Windows, macOS and Linux with only
Python 3.11+.

## 8. Change control

Any request conflicting with this contract (a fifth core, removing DEMO labels, remote tiles, logic in the
frontend…) must be flagged explicitly and recorded in docs/DECISIONS.md before being implemented.
