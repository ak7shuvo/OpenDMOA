# Model packages — contract, safety, installation, provenance

OpenDMO can run externally developed models **without executing their code**. A model package is data plus
metadata; the runtime only loads whitelisted artifact formats.

## Package contract

```
model-package/
├── model/              exactly the artifact(s), e.g. model.json — no executable files allowed
├── metadata.json       id, name, version, task, framework, description, source_repo, license
│                       (+ optional: source_ref, training_data, expected_units, evaluation, author)
├── schema.json         inputs[] / outputs[]: name, type, label, unit, min, max, required
├── requirements.txt    declared dependencies — informational, NEVER installed
└── README.md
```

Validation (`backend/app/runtime/contract.py`) rejects a package if a required file or field is missing, the
framework is not whitelisted, `schema.json` lacks inputs/outputs, `model/` is empty, or `model/` contains files
with executable suffixes (`.py .pyc .so .dll .exe .sh .bat .cmd .ps1 .dylib`).

## Formats

| Framework | Status | Notes |
|---|---|---|
| `json-linear` | **enabled** | `{"bias": b, "coefficients": {"x": c, …}, "clip_negative": true, "output": "prediction"}` → `y = b + Σ cᵢxᵢ` |
| `sklearn-joblib` | **refused by default** | unpickling executes arbitrary code. Only with `OPENDMO_ALLOW_PICKLE_MODELS=true` for fully trusted sources, and `joblib` must be installed manually. |

## Installing from GitHub (explicit user action only)

*System › Control Board › Methods & Models › Install a model package from GitHub*. Accepted forms:
`https://github.com/owner/repo`, `owner/repo`, `https://github.com/owner/repo/tree/<ref>/<subdir>`, plus an
optional branch/tag. OpenDMO downloads the repository zipball (the **only** outbound request it ever makes;
`OPENDMO_GITHUB_TOKEN` optionally raises rate limits), extracts it with path-traversal and size checks
(≤ 100 MB download, ≤ 300 MB unpacked), finds the package root (`metadata.json`), validates it, copies it into
`data/models/<id>/<version>/` and registers it **disabled**. Review the metadata, training data, evaluation and
`requirements.txt` in the Model Lab, then enable it. Every install (and failed install) is audit-logged.

## Running and provenance

Inputs are validated against `schema.json` (required, numeric, min/max). Each execution writes an append-only
run (`kind = model`, `method_id = model:<id>`, `method_version = <package version>`) with the exact inputs,
outputs with units, source repository and ref, licence, training-data statement and evaluation metadata.
Re-run and run bundles work exactly as for calculations.

## Bundled demo model

`backend/model_packages/demo-tourism-demand-v1` — **DEMO**, illustrative coefficients, no training data. It
exists to exercise register → schema-driven input → local run → provenance end to end. Never cite its outputs.
