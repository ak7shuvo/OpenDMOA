"""Destination summary — KPI cells per core, computed entirely in the backend.

Each KPI carries: value, unit, status flag (ok|watch|risk|none), change vs the
previous equal-length window, sparkline values, source dataset (+DEMO flag),
confidence (from the dataset quality score) and a timestamp.
"""
from __future__ import annotations

from sqlalchemy import func, select

from .. import catalog, periods
from ..models import (Asset, Dataset, EarlyWarning, Incident, InfraProject, Observation, ReadinessItem, Run)
from . import datasets as dsvc


def _status(ind: dict, value: float | None) -> str:
    if value is None or ind.get('direction') is None:
        return 'none'
    w, r = ind['watch'], ind['risk']
    if ind['direction'] == 'up_bad':
        return 'risk' if value >= r else 'watch' if value >= w else 'ok'
    return 'risk' if value <= r else 'watch' if value <= w else 'ok'


def _shift_year(p: str, years: int = -1) -> str:
    k = periods.kind(p)
    if k in ('month', 'quarter', 'day'):
        return f'{int(p[:4]) + years}{p[4:]}'
    if k == 'year':
        return str(int(p) + years)
    return p


def _window(start: str | None, end: str | None, all_periods: list[str]) -> list[str]:
    return [p for p in all_periods if periods.in_range(p, start, end)]


def _per_period(db, ds: Dataset, variables: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for o in dsvc.observations(db, ds.id, variables=variables):
        if o.value is not None:
            out.setdefault(o.period, {})[o.variable] = o.value
    return out


DERIVED = {
    'rainfall_anomaly_pct': (['rainfall_mm', 'rainfall_normal_mm'], 'window_ratio'),
    'leakage_pct': (['imported_inputs_bdt', 'repatriated_profits_bdt', 'tourism_revenue_bdt'], 'latest'),
    'local_capture_pct': (['local_spend_bdt', 'tourism_revenue_bdt'], 'latest'),
    'local_employment_pct': (['local_employees', 'total_employees'], 'latest'),
    'visitors_yoy_pct': (['visitors'], 'yoy'),
}


def _derived_point(var: str, row: dict) -> float | None:
    try:
        if var == 'leakage_pct':
            return (row['imported_inputs_bdt'] + row.get('repatriated_profits_bdt', 0)) / row['tourism_revenue_bdt'] * 100
        if var == 'local_capture_pct':
            return row['local_spend_bdt'] / row['tourism_revenue_bdt'] * 100
        if var == 'local_employment_pct':
            return row['local_employees'] / row['total_employees'] * 100
        if var == 'rainfall_anomaly_pct':
            return (row['rainfall_mm'] - row['rainfall_normal_mm']) / row['rainfall_normal_mm'] * 100
    except (KeyError, ZeroDivisionError, TypeError):
        return None
    return None


def kpi(db, ind: dict, destination_id: str, start: str | None, end: str | None) -> dict:
    cell = {k: ind[k] for k in ('id', 'label', 'core', 'unit', 'description', 'decimals')}
    cell.update({'value': None, 'status': 'none', 'change_pct': None, 'spark': [], 'source': None,
                 'confidence': None, 'timestamp': None, 'period_label': None, 'empty': True})
    ds = dsvc.latest_dataset(db, destination_id, ind['kind'])
    if not ds:
        return cell
    variable = ind['variable']
    agg = ind['aggregation']
    needs = DERIVED[variable][0] if agg == 'derived' else [variable]
    table = _per_period(db, ds, needs)
    all_p = sorted(table)
    win = _window(start, end, all_p)
    value = prev = None
    spark: list[float] = []
    if agg != 'derived':
        vals = [table[p][variable] for p in win if variable in table[p]]
        value = dsvc.aggregate(vals, agg)
        spark = vals[-24:]
        if win:
            n = len(win)
            before = [p for p in all_p if p < win[0]][-n:]
            pv = [table[p][variable] for p in before if variable in table[p]]
            if agg == 'last':
                earlier = [table[p][variable] for p in all_p if p < win[-1] and variable in table[p]]
                prev = earlier[-1] if earlier else None
            elif len(pv) == n:
                prev = dsvc.aggregate(pv, agg)
    else:
        mode = DERIVED[variable][1]
        if mode == 'latest':
            pts = [(p, _derived_point(variable, table[p])) for p in win]
            pts = [(p, v) for p, v in pts if v is not None]
            spark = [v for _, v in pts][-24:]
            if pts:
                value = pts[-1][1]
                prev = pts[-2][1] if len(pts) > 1 else None
                win = [p for p, _ in pts]
        elif mode == 'window_ratio':
            rows = [table[p] for p in win if 'rainfall_mm' in table[p] and 'rainfall_normal_mm' in table[p]]
            tot, norm = sum(r['rainfall_mm'] for r in rows), sum(r['rainfall_normal_mm'] for r in rows)
            value = (tot - norm) / norm * 100 if norm else None
            spark = [v for v in (_derived_point(variable, table[p]) for p in win) if v is not None][-24:]
        elif mode == 'yoy':
            cur = [table[p]['visitors'] for p in win if 'visitors' in table[p]]
            base = [table[_shift_year(p)]['visitors'] for p in win if _shift_year(p) in table and 'visitors' in table[_shift_year(p)]]
            if cur and len(base) == len(cur) and sum(base):
                value = (sum(cur) - sum(base)) / sum(base) * 100
            spark = [((table[p]['visitors'] - table[_shift_year(p)]['visitors']) / table[_shift_year(p)]['visitors'] * 100)
                     for p in win if _shift_year(p) in table and table[_shift_year(p)].get('visitors')][-24:]
    if value is None:
        return cell | {'source': _src(ds)}
    change = (value - prev) / abs(prev) * 100 if prev not in (None, 0) else None
    cell.update({
        'value': round(value, 4), 'status': _status(ind, value), 'change_pct': None if change is None else round(change, 2),
        'spark': [round(x, 4) for x in spark], 'source': _src(ds), 'empty': False,
        'confidence': dsvc.level_for(ds.quality_score),
        'timestamp': ds.updated_at.isoformat() if ds.updated_at else None,
        'period_label': f'{win[0]} → {win[-1]}' if win else None,
    })
    return cell


def _src(ds: Dataset) -> dict:
    return {'dataset_id': ds.id, 'name': ds.name, 'version': ds.version, 'is_demo': ds.is_demo,
            'quality_score': ds.quality_score}


def destination_summary(db, destination_id: str, start: str | None, end: str | None, core: str | None = None) -> dict:
    inds = [i for i in catalog.INDICATORS if core in (None, i['core'])]
    kpis = [kpi(db, i, destination_id, start, end) for i in inds]
    warnings = db.scalar(select(func.count(EarlyWarning.id)).where(EarlyWarning.destination_id == destination_id, EarlyWarning.active.is_(True)))
    incidents = db.scalar(select(func.count(Incident.id)).where(Incident.destination_id == destination_id, Incident.status != 'closed'))
    ready_total = db.scalar(select(func.count(ReadinessItem.id)).where(ReadinessItem.destination_id == destination_id)) or 0
    ready_done = db.scalar(select(func.count(ReadinessItem.id)).where(ReadinessItem.destination_id == destination_id, ReadinessItem.done.is_(True))) or 0
    datasets = db.scalars(select(Dataset).where(Dataset.destination_id == destination_id)).all()
    demo_any = any(d.is_demo for d in datasets)
    extent = db.execute(select(func.min(Observation.period), func.max(Observation.period))
                        .where(Observation.destination_id == destination_id)).one()
    return {
        'destination_id': destination_id, 'start': start, 'end': end, 'kpis': kpis,
        'counts': {
            'datasets': len(datasets), 'demo_datasets': sum(d.is_demo for d in datasets),
            'warnings_active': warnings or 0, 'incidents_open': incidents or 0,
            'readiness_pct': round(ready_done / ready_total * 100, 1) if ready_total else None,
            'assets': db.scalar(select(func.count(Asset.id)).where(Asset.destination_id == destination_id)) or 0,
            'projects': db.scalar(select(func.count(InfraProject.id)).where(InfraProject.destination_id == destination_id)) or 0,
            'runs': db.scalar(select(func.count(Run.id)).where(Run.destination_id == destination_id)) or 0,
            'mean_quality': round(sum(d.quality_score or 0 for d in datasets) / len(datasets), 1) if datasets else None,
        },
        'has_demo': demo_any, 'has_data': bool(datasets),
        'extent': {'first_period': extent[0], 'last_period': extent[1]},
    }
