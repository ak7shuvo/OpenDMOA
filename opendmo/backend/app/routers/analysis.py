"""Method registry, runs (calculations, forecasts, models), scenarios, models."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import calculations
from ..db import get_db
from ..models import ModelPackage, Run, Scenario
from ..runtime.contract import PackageError
from ..services import audit, briefs as briefsvc, datasets as dsvc, models as modelsvc, runs as runsvc
from ..util import new_id

router = APIRouter()


# ----------------------------------------------------------------------------- methods

@router.get('/methods')
def list_methods(core: str | None = None, kind: str | None = None, db: Session = Depends(get_db)):
    out = []
    for m in calculations.all_methods():
        if core and m.core != core:
            continue
        if kind and m.kind != kind:
            continue
        out.append({**m.describe(), 'enabled': runsvc.is_enabled(db, m.id)})
    return out


@router.get('/methods/{method_id}')
def get_method(method_id: str, db: Session = Depends(get_db)):
    m = calculations.get(method_id)
    if not m:
        raise HTTPException(404, 'unknown method')
    return {**m.describe(), 'enabled': runsvc.is_enabled(db, m.id), 'markdown': m.methodology_markdown()}


@router.get('/methodology.md', response_class=PlainTextResponse)
def methodology():
    return PlainTextResponse(briefsvc.methodology_markdown(), media_type='text/markdown')


class ResolveIn(BaseModel):
    destination_id: str
    start: str | None = None
    end: str | None = None


@router.post('/methods/{method_id}/resolve')
def resolve(method_id: str, body: ResolveIn, db: Session = Depends(get_db)):
    """Suggest input values from the destination's datasets (shown to the user before running)."""
    m = calculations.get(method_id)
    if not m:
        raise HTTPException(404, 'unknown method')
    res = dsvc.resolve_inputs(db, m, body.destination_id, body.start, body.end)
    dest_attrs = {}
    from ..models import Destination
    d = db.get(Destination, body.destination_id)
    if d:
        attrs = d.attributes or {}
        for p in m.inputs:
            if p.name in res['inputs']:
                continue
            if p.name == 'area_km2' and d.area_km2:
                dest_attrs[p.name] = d.area_km2
            elif p.name in attrs and isinstance(attrs[p.name], (int, float)):
                dest_attrs[p.name] = attrs[p.name]
    return {'inputs': {**dest_attrs, **res['inputs']}, 'sources': res['sources'],
            'from_destination': sorted(dest_attrs)}


# ----------------------------------------------------------------------------- runs

class RunIn(BaseModel):
    method_id: str
    inputs: dict = {}
    destination_id: str | None = None
    dataset_id: str | None = None
    label: str = ''
    input_sources: dict | None = None


class ForecastIn(BaseModel):
    method_id: str
    destination_id: str
    kind: str = 'visitor_flow'
    variable: str = 'visitors'
    dataset_id: str | None = None
    start: str | None = None
    end: str | None = None
    horizon: int = 12
    season_length: int | None = None
    holdout: int | None = None
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    label: str = ''


def _run_or_422(fn):
    try:
        return fn()
    except (runsvc.RunError, PackageError) as exc:
        raise HTTPException(422, str(exc))


@router.post('/runs', status_code=201)
def create_run(body: RunIn, db: Session = Depends(get_db)):
    run = _run_or_422(lambda: runsvc.execute(db, body.method_id, body.inputs, body.destination_id, body.dataset_id,
                                             label=body.label, input_sources=body.input_sources))
    return {**runsvc.run_dict(run), 'provenance': runsvc.provenance(run)}


@router.post('/forecasts', status_code=201)
def create_forecast(body: ForecastIn, db: Session = Depends(get_db)):
    m = calculations.get(body.method_id)
    if not m or m.kind != 'forecast':
        raise HTTPException(404, 'unknown forecast method')
    ds, series = _run_or_422(lambda: runsvc.forecast_series(db, body.destination_id, body.dataset_id, body.kind,
                                                            body.variable, body.start, body.end))
    inputs = {'series': series, 'horizon': body.horizon, 'season_length': body.season_length, 'holdout': body.holdout,
              'alpha': body.alpha, 'beta': body.beta, 'gamma': body.gamma}
    run = _run_or_422(lambda: runsvc.execute(
        db, body.method_id, {k: v for k, v in inputs.items() if v is not None}, body.destination_id, ds.id,
        parameters={'variable': body.variable, 'kind': body.kind, 'start': body.start, 'end': body.end},
        label=body.label or f'{body.variable} forecast'))
    return {**runsvc.run_dict(run), 'provenance': runsvc.provenance(run), 'history': series}


@router.get('/runs')
def list_runs(kind: str | None = None, method_id: str | None = None, destination_id: str | None = None,
              status: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    return [runsvc.run_dict(r, brief=True) | {'headline': _headline(r)}
            for r in runsvc.list_runs(db, kind, method_id, destination_id, status, min(limit, 1000))]


def _headline(r: Run) -> str:
    out = r.outputs or {}
    if r.status != 'success':
        return (r.error or 'failed')[:120]
    if r.kind == 'forecast' and out.get('forecast'):
        f = out['forecast'][0]
        mape = (out.get('backtest') or {}).get('mape_pct')
        return f"next {f['period']}: {f['value']:,.0f} · MAPE {'—' if mape is None else f'{mape:.1f}'} %"
    parts = []
    for k, v in out.items():
        if isinstance(v, (int, float)) and len(parts) < 3:
            parts.append(f'{k}={v:,.2f}')
        elif isinstance(v, dict) and 'value' in v and len(parts) < 3:
            parts.append(f"{k}={v['value']:,.2f}")
        elif isinstance(v, str) and k in ('status', 'class', 'pressure_band'):
            parts.append(f'{k}={v}')
    return ' · '.join(parts)


def _run(db, run_id: str) -> Run:
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, 'run not found')
    return r


@router.get('/runs/{run_id}')
def get_run(run_id: str, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    return {**runsvc.run_dict(r), 'provenance': runsvc.provenance(r)}


@router.post('/runs/{run_id}/rerun', status_code=201)
def rerun(run_id: str, db: Session = Depends(get_db)):
    old = _run(db, run_id)
    if old.kind == 'model':
        model_id = old.method_id.removeprefix('model:')
        new = _run_or_422(lambda: modelsvc.run_model(db, model_id, old.method_version, old.destination_id, old.inputs,
                                                     old.dataset_id, old.label))
        new.rerun_of = old.id
        db.commit()
    else:
        new = _run_or_422(lambda: runsvc.rerun(db, run_id))
    same = json.dumps(new.outputs, sort_keys=True, default=str) == json.dumps(old.outputs, sort_keys=True, default=str)
    return {**runsvc.run_dict(new), 'provenance': runsvc.provenance(new), 'reproduced': same,
            'method_version_changed': new.method_version != old.method_version}


@router.get('/runs/{run_id}/bundle.zip')
def run_bundle(run_id: str, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    return Response(runsvc.bundle(db, r), media_type='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="{"DEMO_" if r.is_demo else ""}{r.id}.zip"'})


@router.get('/runs/{run_id}/export.json')
def run_json(run_id: str, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    return Response(json.dumps({'run': runsvc.run_dict(r), 'provenance': runsvc.provenance(r)}, indent=2, default=str),
                    media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{r.id}.json"'})


@router.get('/runs/{run_id}/export.csv')
def run_csv(run_id: str, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    body = runsvc.kv_csv({'run_id': r.id, 'method': f'{r.method_id} v{r.method_version}', 'is_demo': r.is_demo,
                          'inputs': r.inputs, 'outputs': r.outputs, 'dataset': r.dataset_id, 'dataset_hash': r.dataset_hash,
                          'software_version': r.software_version, 'timestamp': r.created_at.isoformat()})
    return Response(body, media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{r.id}.csv"'})


# ----------------------------------------------------------------------------- scenarios

class ScenarioIn(BaseModel):
    name: str
    run_id: str
    notes: str = ''


def _scen_dict(db, s: Scenario) -> dict:
    r = db.get(Run, s.run_id)
    return {'id': s.id, 'name': s.name, 'notes': s.notes, 'destination_id': s.destination_id, 'run_id': s.run_id,
            'created_at': s.created_at.isoformat(), 'run': runsvc.run_dict(r) if r else None}


@router.get('/scenarios')
def list_scenarios(destination_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Scenario)
    if destination_id:
        q = q.where(Scenario.destination_id == destination_id)
    return [_scen_dict(db, s) for s in db.scalars(q.order_by(Scenario.created_at.desc()))]


@router.post('/scenarios', status_code=201)
def save_scenario(body: ScenarioIn, db: Session = Depends(get_db)):
    r = _run(db, body.run_id)
    if r.status != 'success':
        raise HTTPException(422, 'only successful runs can be saved as scenarios')
    s = Scenario(id=new_id('SCN'), destination_id=r.destination_id or '', name=body.name, notes=body.notes, run_id=r.id)
    db.add(s)
    db.commit()
    return _scen_dict(db, s)


@router.delete('/scenarios/{scn_id}')
def delete_scenario(scn_id: str, db: Session = Depends(get_db)):
    db.execute(delete(Scenario).where(Scenario.id == scn_id))
    db.commit()
    return {'deleted': scn_id}


@router.get('/scenarios/compare')
def compare(ids: str, db: Session = Depends(get_db)):
    """Side-by-side comparison: union of input and output keys across the chosen scenarios."""
    scens = [db.get(Scenario, i) for i in ids.split(',') if i]
    scens = [s for s in scens if s]
    cols = []
    in_keys, out_keys = [], []
    for s in scens:
        r = db.get(Run, s.run_id)
        if not r:
            continue
        cols.append({'scenario': s.name, 'scenario_id': s.id, 'run_id': r.id, 'method': f'{r.method_id} v{r.method_version}',
                     'is_demo': r.is_demo, 'inputs': r.inputs, 'outputs': r.outputs})
        for k, v in (r.inputs or {}).items():
            if k not in in_keys and not isinstance(v, list):
                in_keys.append(k)
        for k, v in (r.outputs or {}).items():
            if k not in out_keys and not isinstance(v, (list, dict)):
                out_keys.append(k)
    return {'columns': cols, 'input_keys': in_keys, 'output_keys': out_keys,
            'mixed_methods': len({c['method'] for c in cols}) > 1}


# ----------------------------------------------------------------------------- models

class InstallIn(BaseModel):
    url: str
    ref: str | None = None


class StatusIn(BaseModel):
    status: str


class ModelRunIn(BaseModel):
    model_id: str
    version: str | None = None
    destination_id: str | None = None
    inputs: dict
    dataset_id: str | None = None
    label: str = ''


@router.get('/models')
def list_models(db: Session = Depends(get_db)):
    return [modelsvc.pkg_dict(p) for p in db.scalars(select(ModelPackage).order_by(ModelPackage.id, ModelPackage.version))]


@router.post('/models/install', status_code=201)
def install_model(body: InstallIn, db: Session = Depends(get_db)):
    try:
        pkg = modelsvc.install_from_github(db, body.url, body.ref)
    except PackageError as exc:
        audit.log(db, 'model.install_failed', body.url, error=str(exc))
        raise HTTPException(422, str(exc))
    audit.log(db, 'model.install', f'{pkg.id}@{pkg.version}', url=body.url)
    return modelsvc.pkg_dict(pkg)


@router.post('/models/{model_id}/{version}/status')
def set_model_status(model_id: str, version: str, body: StatusIn, db: Session = Depends(get_db)):
    p = db.get(ModelPackage, (model_id, version))
    if not p:
        raise HTTPException(404, 'model not found')
    if body.status not in ('enabled', 'disabled'):
        raise HTTPException(422, 'status must be enabled or disabled')
    p.status = body.status
    db.commit()
    audit.log(db, f'model.{body.status}', f'{model_id}@{version}')
    return modelsvc.pkg_dict(p)


@router.delete('/models/{model_id}/{version}')
def delete_model(model_id: str, version: str, db: Session = Depends(get_db)):
    p = db.get(ModelPackage, (model_id, version))
    if not p:
        raise HTTPException(404, 'model not found')
    db.delete(p)
    db.commit()
    audit.log(db, 'model.delete', f'{model_id}@{version}')
    return {'deleted': f'{model_id}@{version}'}


@router.post('/models/run', status_code=201)
def run_model(body: ModelRunIn, db: Session = Depends(get_db)):
    try:
        run = modelsvc.run_model(db, body.model_id, body.version, body.destination_id, body.inputs, body.dataset_id, body.label)
    except PackageError as exc:
        raise HTTPException(422, str(exc))
    return {**runsvc.run_dict(run), 'provenance': runsvc.provenance(run)}
