# Tourism Demand Forecast (DEMO) — v1.0.0

> **DEMO MODEL — NOT FOR RESEARCH CONCLUSIONS.**
> The coefficients in `model/model.json` are illustrative constants. This
> package exists to exercise the full OpenDMO model-runtime workflow
> (register → schema-driven input → local run → provenance record) with
> zero trusted-code risk. Replace with a real fitted model package from an
> approved repository when one is available.

## Layout

    model/model.json      linear weights (json-linear format — data, not code)
    metadata.json         identity, provenance, licence, expected units
    schema.json           input/output variable contract (drives the UI form)
    requirements.txt      declared deps (informational; never auto-installed)

## Model

    prediction = 40 + 1.08*visitor_count + 1.6*hotel_occupancy
                 - 2.1*rainfall + 0.9*temperature + 85*holiday + 22*event_count

Prediction is clipped at zero. Expected output unit: visitors/day.
