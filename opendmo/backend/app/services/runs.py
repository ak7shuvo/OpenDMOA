"""Run service — execute registered methods and persist full provenance.

Every run stores: inputs, parameters, dataset id + version + content hash (and
the last import's file hash), method id + version + a snapshot of the method
definition, outputs, data quality, software version and a UTC timestamp.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

from sqlalchemy import select

from .. import __version__, calculations
from ..calculations.base import CalculationError, Method
from ..models import Dataset, Destination, MethodState, Run
from ..util import new_id
from . import datasets as dsvc


class RunError(ValueError):
    pass


def is_enabled(db, method_id: str) -> bool:
    st = db.get(MethodState, method_id)
    return True if st is None else bool(st.enabled)


def validate_inputs(m: Method, inputs: dict) -> tuple[dict, list[str]]:
    clean, errors = {}, []
    for p in m.inputs:
        raw = inputs.get(p.name)
        if raw in (None, ''):
            if p.default is not None and p.type not in ('series',):
                clean[p.name] = p.default
            elif p.required:
                errors.append(f'missing required input: {p.label} ({p.name})')
            continue
        if p.type in ('factors', 'series'):
            if not isinstance(raw, list):
                errors.append(f'{p.name} must be a list')
                continue
            clean[p.name] = raw
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            errors.append(f'{p.label}: not a number ({raw!r})')
            continue
        if p.type == 'int':
            val = int(round(val))
        if p.min is not None and val < p.min:
            errors.append(f'{p.label}: {val} is below the minimum {p.min}')
        if p.max is not None and val > p.max:
            errors.append(f'{p.label}: {val} is above the maximum {p.max}')
        clean[p.name] = val
    return clean, errors


def _dataset_context(db, dataset_id: str | None) -> dict:
    if not dataset_id:
        return {}
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise RunError(f'dataset not found: {dataset_id}')
    return {'dataset': ds, 'dataset_hash': dsvc.content_hash(db, ds.id),
            'quality': {'score': ds.quality_score, 'level': dsvc.level_for(ds.quality_score),
                        'completeness_pct': (ds.quality or {}).get('completeness_pct'),
                        'last_file_hash': (ds.provenance or {}).get('last_file_hash')}}


def execute(db, method_id: str, inputs: dict, destination_id: str | None = None, dataset_id: str | None = None,
            parameters: dict | None = None, label: str = '', rerun_of: str | None = None,
            input_sources: dict | None = None, persist: bool = True) -> Run:
    m = calculations.get(method_id)
    if not m:
        raise RunError(f'unknown method: {method_id}')
    if not is_enabled(db, method_id):
        raise RunError(f'method {method_id} is disabled in the Control Board')
    if destination_id and not db.get(Destination, destination_id):
        raise RunError(f'destination not found: {destination_id}')
    ctx = _dataset_context(db, dataset_id)
    clean, errors = validate_inputs(m, inputs)
    ds = ctx.get('dataset')
    demo = bool(ds and ds.is_demo) or any(s.get('is_demo') for s in (input_sources or {}).values())
    run = Run(id=new_id('RUN'), kind=m.kind, method_id=m.id, method_version=m.version, destination_id=destination_id,
              dataset_id=ds.id if ds else None, dataset_version=ds.version if ds else None,
              dataset_hash=ctx.get('dataset_hash'), parameters={**(parameters or {}), 'input_sources': input_sources or {}},
              inputs=clean, data_quality=ctx.get('quality', {}), software_version=__version__,
              method_snapshot={k: v for k, v in m.describe().items() if k not in ('known_cases',)},
              label=label, rerun_of=rerun_of, is_demo=demo, outputs={})
    if errors:
        run.status, run.error = 'failed', '; '.join(errors)
    else:
        try:
            run.outputs = m.compute(clean)
            run.status = 'success'
        except CalculationError as exc:
            run.status, run.error = 'failed', str(exc)
        except Exception as exc:  # pragma: no cover - recorded, never swallowed silently
            run.status, run.error = 'failed', f'{type(exc).__name__}: {exc}'
    if persist:
        db.add(run)
        db.commit()
    return run


def forecast_series(db, destination_id: str, dataset_id: str | None, kind: str, variable: str,
                    start: str | None, end: str | None) -> tuple[Dataset, list[dict]]:
    ds = db.get(Dataset, dataset_id) if dataset_id else dsvc.latest_dataset(db, destination_id, kind)
    if not ds:
        raise RunError('no dataset available for this destination — import a CSV or load the demo pack')
    s = dsvc.series(db, ds, variable, start, end)
    if not s:
        raise RunError(f"dataset {ds.id} has no values for '{variable}' in the selected range")
    return ds, [{'period': x['period'], 'value': x['value']} for x in s]


def rerun(db, run_id: str) -> Run:
    old = db.get(Run, run_id)
    if not old:
        raise RunError('run not found')
    params = dict(old.parameters or {})
    return execute(db, old.method_id, dict(old.inputs or {}), old.destination_id, old.dataset_id,
                   parameters={k: v for k, v in params.items() if k != 'input_sources'},
                   label=old.label, rerun_of=old.id, input_sources=params.get('input_sources'))


def run_dict(run: Run, brief: bool = False) -> dict:
    m = calculations.get(run.method_id)
    d = {
        'id': run.id, 'kind': run.kind, 'method_id': run.method_id, 'method_version': run.method_version,
        'method_name': (run.method_snapshot or {}).get('name') or (m.name if m else run.method_id),
        'destination_id': run.destination_id, 'dataset_id': run.dataset_id, 'dataset_version': run.dataset_version,
        'dataset_hash': run.dataset_hash, 'status': run.status, 'error': run.error, 'label': run.label,
        'is_demo': run.is_demo, 'software_version': run.software_version, 'rerun_of': run.rerun_of,
        'created_at': run.created_at.isoformat() if run.created_at else None,
        'screening': (run.method_snapshot or {}).get('screening', False),
        'current_method_version': m.version if m else None,
    }
    if not brief:
        d.update({'inputs': run.inputs, 'parameters': run.parameters, 'outputs': run.outputs,
                  'data_quality': run.data_quality, 'method': run.method_snapshot})
    return d


def provenance(run: Run) -> dict:
    snap = run.method_snapshot or {}
    return {
        'result': run.outputs, 'inputs': run.inputs, 'parameters': run.parameters,
        'method': {'id': run.method_id, 'version': run.method_version, 'name': snap.get('name'),
                   'formula': snap.get('formula'), 'screening': snap.get('screening', False),
                   'references': [r.get('citation') for r in snap.get('references', [])]},
        'data': {'dataset_id': run.dataset_id, 'dataset_version': run.dataset_version, 'dataset_hash': run.dataset_hash,
                 'input_sources': (run.parameters or {}).get('input_sources', {}), 'is_demo': run.is_demo},
        'quality': run.data_quality, 'software_version': run.software_version,
        'timestamp': run.created_at.isoformat() if run.created_at else None, 'run_id': run.id, 'status': run.status,
    }


def _flatten(prefix: str, obj, out: list[tuple[str, str]]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f'{prefix}.{k}' if prefix else str(k), v, out)
    elif isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        for i, x in enumerate(obj):
            _flatten(f'{prefix}[{i}]', x, out)
    else:
        out.append((prefix, json.dumps(obj) if isinstance(obj, (list, dict)) else '' if obj is None else str(obj)))


def kv_csv(obj: dict) -> str:
    rows: list[tuple[str, str]] = []
    _flatten('', obj, rows)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(['key', 'value'])
    w.writerows(rows)
    return buf.getvalue()


def bundle(db, run: Run) -> bytes:
    """Zip: run.json, inputs.csv, outputs.csv, methodology.md, dataset.csv (if linked), CITATION.txt."""
    m = calculations.get(run.method_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('run.json', json.dumps({'run': run_dict(run), 'provenance': provenance(run)}, indent=2, default=str))
        z.writestr('inputs.csv', kv_csv(run.inputs or {}))
        z.writestr('outputs.csv', kv_csv(run.outputs or {}))
        method_md = m.methodology_markdown() if m else f"# {run.method_id} {run.method_version}\n"
        if m and m.version != run.method_version:
            method_md = (f'> NOTE: this run used v{run.method_version}; the registry now has v{m.version}. '
                         f'The run.json method snapshot is authoritative.\n\n') + method_md
        z.writestr('methodology.md', method_md)
        if run.dataset_id and db.get(Dataset, run.dataset_id):
            from .csv_import import observations_csv
            z.writestr('dataset.csv', observations_csv(dsvc.observations(db, run.dataset_id)))
        cites = '\n\n'.join(r['bibtex'] for r in (run.method_snapshot or {}).get('references', []))
        z.writestr('CITATION.bib', cites + '\n')
        z.writestr('README.txt', (
            f'OpenDMO run bundle {run.id}\nCreated {datetime.now(timezone.utc).isoformat()}\n'
            f'Method {run.method_id} v{run.method_version} · software {run.software_version}\n'
            + ('DEMO DATA — synthetic, not for citation.\n' if run.is_demo else '')
            + 'Re-run: POST /api/runs/{id}/rerun or import run.json inputs into the same method.\n'))
    return buf.getvalue()


def list_runs(db, kind: str | None = None, method_id: str | None = None, destination_id: str | None = None,
              status: str | None = None, limit: int = 200) -> list[Run]:
    q = select(Run)
    if kind:
        q = q.where(Run.kind == kind)
    if method_id:
        q = q.where(Run.method_id == method_id)
    if destination_id:
        q = q.where(Run.destination_id == destination_id)
    if status:
        q = q.where(Run.status == status)
    return list(db.scalars(q.order_by(Run.created_at.desc()).limit(limit)))
