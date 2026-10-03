"""Dataset service: creation, versioning, quality scoring, series access, input resolution."""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from sqlalchemy import func, select

from .. import catalog, periods
from ..models import Dataset, Destination, Observation
from ..util import sha256_json, slugify


class DatasetError(ValueError):
    pass


# ----------------------------------------------------------------------------- serialisation

def dataset_dict(db, ds: Dataset, with_counts: bool = True) -> dict:
    d = {
        'id': ds.id, 'destination_id': ds.destination_id, 'kind': ds.kind,
        'kind_label': catalog.DATASET_KINDS.get(ds.kind, {}).get('label', ds.kind),
        'name': ds.name, 'version': ds.version, 'status': ds.status, 'frequency': ds.frequency,
        'quality_score': ds.quality_score, 'quality': ds.quality or {}, 'variable_defs': ds.variable_defs or [],
        'provenance': ds.provenance or {}, 'is_demo': ds.is_demo,
        'created_at': ds.created_at.isoformat() if ds.created_at else None,
        'updated_at': ds.updated_at.isoformat() if ds.updated_at else None,
    }
    if with_counts:
        row = db.execute(select(func.count(Observation.id), func.min(Observation.period), func.max(Observation.period))
                         .where(Observation.dataset_id == ds.id)).one()
        d.update({'observations': row[0], 'first_period': row[1], 'last_period': row[2]})
    return d


def dataset_id_for(destination_id: str, kind: str, name: str, version: int) -> str:
    return f'{slugify(destination_id, 16)}.{slugify(name, 40)}.v{version}'


def create_dataset(db, destination_id: str, kind: str, name: str, variable_defs: list[dict] | None = None,
                   frequency: str | None = None, provenance: dict | None = None, is_demo: bool = False,
                   version: int | None = None) -> Dataset:
    if not db.get(Destination, destination_id):
        raise DatasetError(f'destination not found: {destination_id}')
    if kind not in catalog.DATASET_KINDS:
        raise DatasetError(f'unknown dataset kind: {kind}')
    name = name.strip() or catalog.DATASET_KINDS[kind]['label']
    if version is None:
        last = db.scalar(select(func.max(Dataset.version)).where(
            Dataset.destination_id == destination_id, Dataset.kind == kind, Dataset.name == name))
        version = (last or 0) + 1
    ds_id = dataset_id_for(destination_id, kind, name, version)
    if db.get(Dataset, ds_id):
        raise DatasetError(f'dataset already exists: {ds_id}')
    defs = variable_defs if variable_defs is not None else catalog.kind_variables(kind)
    ds = Dataset(id=ds_id, destination_id=destination_id, kind=kind, name=name, version=version,
                 frequency=frequency or catalog.DATASET_KINDS[kind]['frequency'], variable_defs=defs,
                 provenance={'created_via': 'opendmo', 'created_at': datetime.now(timezone.utc).isoformat(),
                             **(provenance or {})},
                 is_demo=is_demo, status='draft')
    db.add(ds)
    db.commit()
    return ds


def new_version(db, ds: Dataset, copy_observations: bool = True) -> Dataset:
    nv = create_dataset(db, ds.destination_id, ds.kind, ds.name, variable_defs=list(ds.variable_defs or []),
                        frequency=ds.frequency, is_demo=ds.is_demo,
                        provenance={'derived_from': ds.id, 'derived_from_version': ds.version})
    if copy_observations:
        for o in db.scalars(select(Observation).where(Observation.dataset_id == ds.id)):
            db.add(Observation(dataset_id=nv.id, destination_id=o.destination_id, period=o.period, variable=o.variable,
                               value=o.value, unit=o.unit, quality_flag=o.quality_flag, import_id=o.import_id))
        db.commit()
        compute_quality(db, nv)
    return nv


def ensure_mutable(ds: Dataset) -> None:
    if ds.status == 'archived':
        raise DatasetError('dataset is archived (immutable) — create a new version to change it')


# ----------------------------------------------------------------------------- observations & series

def observations(db, ds_id: str, start: str | None = None, end: str | None = None,
                 variables: list[str] | None = None) -> list[Observation]:
    q = select(Observation).where(Observation.dataset_id == ds_id)
    if variables:
        q = q.where(Observation.variable.in_(variables))
    rows = db.scalars(q.order_by(Observation.period, Observation.variable)).all()
    if start or end:
        rows = [o for o in rows if periods.in_range(o.period, start, end)]
    return rows


def content_hash(db, ds_id: str) -> str:
    """Deterministic hash of the dataset's current observations (provenance fingerprint)."""
    rows = [(o.period, o.variable, o.value, o.unit, o.quality_flag) for o in observations(db, ds_id)]
    return sha256_json(rows)


def latest_dataset(db, destination_id: str, kind: str) -> Dataset | None:
    """Most relevant dataset of a kind: newest non-archived version, else newest archived."""
    rows = db.scalars(select(Dataset).where(Dataset.destination_id == destination_id, Dataset.kind == kind)
                      .order_by(Dataset.is_demo.asc(), Dataset.version.desc(), Dataset.updated_at.desc())).all()
    if not rows:
        return None
    active = [d for d in rows if d.status != 'archived']
    return (active or rows)[0]


def series(db, ds: Dataset, variable: str, start: str | None = None, end: str | None = None) -> list[dict]:
    return [{'period': o.period, 'value': o.value, 'flag': o.quality_flag}
            for o in observations(db, ds.id, start, end, [variable]) if o.value is not None]


def aggregate(values: list[float], how: str) -> float | None:
    if not values:
        return None
    if how == 'sum':
        return float(sum(values))
    if how == 'mean':
        return float(sum(values) / len(values))
    if how == 'max':
        return float(max(values))
    if how == 'min':
        return float(min(values))
    if how == 'sum12':
        return float(sum(values[-12:]))
    return float(values[-1])  # last


def resolve_inputs(db, method, destination_id: str, start: str | None, end: str | None) -> dict:
    """Fill method inputs from the destination's datasets using each Param.source binding."""
    values, sources = {}, {}
    for p in method.inputs:
        if p.type == 'series' or not p.source:
            continue
        kind, variable, agg = p.source
        ds = latest_dataset(db, destination_id, kind)
        if not ds:
            continue
        s = series(db, ds, variable, start, end)
        val = aggregate([x['value'] for x in s], agg)
        if val is None:
            continue
        values[p.name] = round(val, 6)
        sources[p.name] = {'dataset_id': ds.id, 'dataset_version': ds.version, 'variable': variable,
                           'aggregation': agg, 'periods': [s[0]['period'], s[-1]['period']], 'n': len(s),
                           'is_demo': ds.is_demo}
    return {'inputs': values, 'sources': sources}


# ----------------------------------------------------------------------------- quality

def _expected_periods(first: str, last: str, n_cap: int = 2000) -> list[str]:
    out = [first]
    while out[-1] < last and len(out) < n_cap:
        nxt = periods.next_periods(out[-1], 1)[0]
        if '+' in nxt:
            break
        out.append(nxt)
    return out


def robust_outliers(values: list[float], threshold: float = 3.5) -> set[int]:
    """Indices whose modified z-score exceeds ``threshold`` (Iglewicz & Hoaglin, 1993)."""
    if len(values) < 8:
        return set()
    med = statistics.median(values)
    mad = statistics.median([abs(x - med) for x in values])
    if mad == 0:
        return set()
    return {i for i, x in enumerate(values) if abs(0.6745 * (x - med) / mad) > threshold}


def compute_quality(db, ds: Dataset) -> dict:
    obs = observations(db, ds.id)
    defs = {d['name']: d for d in (ds.variable_defs or [])}
    flags: dict[str, int] = {}
    for o in obs:
        flags[o.quality_flag] = flags.get(o.quality_flag, 0) + 1
    observed_vars = sorted({o.variable for o in obs if o.value is not None})
    required = sorted(n for n, d in defs.items() if d.get('required'))
    missing_required = [n for n in required if n not in observed_vars]
    expected_vars = sorted(set(required) | set(observed_vars))
    period_list = sorted({o.period for o in obs})
    gaps: list[str] = []
    if period_list and periods.kind(period_list[0]) in ('month', 'quarter', 'year'):
        full = _expected_periods(period_list[0], period_list[-1])
        gaps = [p for p in full if p not in set(period_list)]
        n_periods = len(full)
    else:
        n_periods = len(period_list)
    filled = sum(1 for o in obs if o.value is not None and o.variable in expected_vars)
    expected = max(n_periods * max(len(expected_vars), 1), 1)
    completeness = min(filled / expected, 1.0) * 100 if obs else 0.0
    n = max(len(obs), 1)
    range_violations = 0
    for o in obs:
        d = defs.get(o.variable)
        if d and o.value is not None and ((d.get('min') is not None and o.value < d['min']) or
                                          (d.get('max') is not None and o.value > d['max'])):
            range_violations += 1
    score = completeness * (1 - 0.5 * flags.get('outlier', 0) / n - 0.25 * flags.get('estimated', 0) / n)
    score -= 10 * len(missing_required) + 20 * range_violations / n
    score = round(max(0.0, min(100.0, score)), 1) if obs else 0.0
    quality = {
        'observations': len(obs), 'periods': len(period_list), 'first_period': period_list[0] if period_list else None,
        'last_period': period_list[-1] if period_list else None, 'period_gaps': gaps[:50], 'n_gaps': len(gaps),
        'variables_defined': sorted(defs), 'variables_observed': observed_vars, 'missing_required': missing_required,
        'flags': flags, 'range_violations': range_violations, 'completeness_pct': round(completeness, 1),
        'quality_score': score, 'level': level_for(score), 'checked_at': datetime.now(timezone.utc).isoformat(),
    }
    ds.quality = quality
    ds.quality_score = score
    db.commit()
    return quality


def level_for(score: float | None) -> str:
    if score is None:
        return 'unknown'
    return 'high' if score >= 80 else 'moderate' if score >= 60 else 'low'
