"""Datasets, observations, CSV/JSON import wizard and exports."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import catalog, periods
from ..db import get_db
from ..models import Dataset, ImportRecord, Observation
from ..services import audit, csv_import
from ..services import datasets as dsvc

router = APIRouter()


def _ds(db, ds_id: str) -> Dataset:
    ds = db.get(Dataset, ds_id)
    if not ds:
        raise HTTPException(404, f'dataset not found: {ds_id}')
    return ds


class DatasetIn(BaseModel):
    destination_id: str
    kind: str = 'custom'
    name: str = ''
    frequency: str | None = None
    variable_defs: list[dict] | None = None
    description: str = ''


class DatasetPatch(BaseModel):
    name: str | None = None
    variable_defs: list[dict] | None = None
    frequency: str | None = None
    description: str | None = None


@router.get('/datasets')
def list_datasets(destination_id: str | None = None, kind: str | None = None, include_archived: bool = True,
                  db: Session = Depends(get_db)):
    q = select(Dataset)
    if destination_id:
        q = q.where(Dataset.destination_id == destination_id)
    if kind:
        q = q.where(Dataset.kind == kind)
    if not include_archived:
        q = q.where(Dataset.status != 'archived')
    rows = db.scalars(q.order_by(Dataset.destination_id, Dataset.kind, Dataset.name, Dataset.version.desc())).all()
    return [dsvc.dataset_dict(db, d) for d in rows]


@router.post('/datasets', status_code=201)
def create_dataset(body: DatasetIn, db: Session = Depends(get_db)):
    defs = body.variable_defs
    if defs is not None:
        for d in defs:
            if not d.get('name'):
                raise HTTPException(422, 'every variable needs a name')
            d.setdefault('label', d['name'])
            d.setdefault('unit', '')
            d.setdefault('type', 'float')
            d.setdefault('required', False)
            d.setdefault('aliases', [])
    try:
        ds = dsvc.create_dataset(db, body.destination_id, body.kind, body.name, defs, body.frequency,
                                 provenance={'description': body.description} if body.description else None)
    except dsvc.DatasetError as exc:
        raise HTTPException(422, str(exc))
    audit.log(db, 'dataset.create', ds.id, kind=ds.kind)
    return dsvc.dataset_dict(db, ds)


@router.get('/datasets/{ds_id}')
def get_dataset(ds_id: str, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    d = dsvc.dataset_dict(db, ds)
    d['imports'] = [{'id': i.id, 'file_name': i.file_name, 'file_hash': i.file_hash, 'layout': i.layout,
                     'inserted': i.inserted, 'updated': i.updated, 'unchanged': i.unchanged, 'skipped': i.skipped,
                     'created_at': i.created_at.isoformat()}
                    for i in db.scalars(select(ImportRecord).where(ImportRecord.dataset_id == ds_id).order_by(ImportRecord.created_at.desc()))]
    d['versions'] = [{'id': v.id, 'version': v.version, 'status': v.status} for v in db.scalars(
        select(Dataset).where(Dataset.destination_id == ds.destination_id, Dataset.kind == ds.kind, Dataset.name == ds.name)
        .order_by(Dataset.version))]
    return d


@router.patch('/datasets/{ds_id}')
def patch_dataset(ds_id: str, body: DatasetPatch, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    try:
        dsvc.ensure_mutable(ds)
    except dsvc.DatasetError as exc:
        raise HTTPException(409, str(exc))
    ch = body.model_dump(exclude_unset=True)
    if 'name' in ch and ch['name']:
        ds.name = ch['name']
    if 'variable_defs' in ch and ch['variable_defs'] is not None:
        ds.variable_defs = ch['variable_defs']
    if ch.get('frequency'):
        ds.frequency = ch['frequency']
    if 'description' in ch:
        ds.provenance = {**(ds.provenance or {}), 'description': ch['description']}
    db.commit()
    dsvc.compute_quality(db, ds)
    return dsvc.dataset_dict(db, ds)


@router.post('/datasets/{ds_id}/validate')
def validate_dataset(ds_id: str, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    q = dsvc.compute_quality(db, ds)
    if ds.status != 'archived':
        ds.status = 'validated'
        db.commit()
    audit.log(db, 'dataset.validate', ds_id, score=q['quality_score'])
    return {'status': ds.status, 'quality': q}


@router.get('/datasets/{ds_id}/quality')
def dataset_quality(ds_id: str, db: Session = Depends(get_db)):
    return dsvc.compute_quality(db, _ds(db, ds_id))


@router.post('/datasets/{ds_id}/archive')
def archive_dataset(ds_id: str, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    ds.status = 'archived'
    db.commit()
    audit.log(db, 'dataset.archive', ds_id)
    return dsvc.dataset_dict(db, ds)


@router.post('/datasets/{ds_id}/version', status_code=201)
def new_version(ds_id: str, copy: bool = True, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    nv = dsvc.new_version(db, ds, copy)
    audit.log(db, 'dataset.new_version', nv.id, derived_from=ds_id)
    return dsvc.dataset_dict(db, nv)


@router.delete('/datasets/{ds_id}')
def delete_dataset(ds_id: str, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    db.execute(delete(Observation).where(Observation.dataset_id == ds_id))
    db.execute(delete(ImportRecord).where(ImportRecord.dataset_id == ds_id))
    db.delete(ds)
    db.commit()
    audit.log(db, 'dataset.delete', ds_id, was_demo=ds.is_demo)
    return {'deleted': ds_id}


@router.get('/datasets/{ds_id}/observations')
def get_observations(ds_id: str, start: str | None = None, end: str | None = None, variable: str | None = None,
                     db: Session = Depends(get_db)):
    _ds(db, ds_id)
    rows = dsvc.observations(db, ds_id, start, end, [variable] if variable else None)
    return [{'period': o.period, 'variable': o.variable, 'value': o.value, 'unit': o.unit, 'quality_flag': o.quality_flag}
            for o in rows]


class ObsIn(BaseModel):
    period: str
    variable: str
    value: float | None
    unit: str | None = None
    quality_flag: str = 'ok'


class ObsBatch(BaseModel):
    observations: list[ObsIn] = Field(min_length=1)


@router.post('/datasets/{ds_id}/observations', status_code=201)
def add_observations(ds_id: str, body: ObsBatch, db: Session = Depends(get_db)):
    """Manual entry: same validation as the CSV pipeline (long layout)."""
    ds = _ds(db, ds_id)
    try:
        dsvc.ensure_mutable(ds)
    except dsvc.DatasetError as exc:
        raise HTTPException(409, str(exc))
    rows = [[o.period, o.variable, '' if o.value is None else str(o.value), o.unit or '', o.quality_flag] for o in body.observations]
    t = csv_import.Table(columns=['period', 'variable', 'value', 'unit', 'flag'], rows=rows, file_format='manual', first_line=1)
    mapping = {'layout': 'long', 'period_column': 'period', 'variable_column': 'variable', 'value_column': 'value',
               'unit_column': 'unit', 'flag_column': 'flag'}
    rep = csv_import.validate(db, ds, t, mapping)
    if rep.n_errors:
        return JSONResponse(status_code=422, content={'detail': 'validation failed', 'issues': rep.issues})
    content = json.dumps([o.model_dump() for o in body.observations], sort_keys=True).encode()
    res = csv_import.commit(db, ds, content, 'manual-entry.json', t, mapping, rep)
    return res


@router.get('/datasets/{ds_id}/series')
def get_series(ds_id: str, variables: str, start: str | None = None, end: str | None = None, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    defs = {d['name']: d for d in ds.variable_defs or []}
    out = []
    for v in [x for x in variables.split(',') if x]:
        out.append({'variable': v, 'label': defs.get(v, {}).get('label', v), 'unit': defs.get(v, {}).get('unit', ''),
                    'points': dsvc.series(db, ds, v, start, end)})
    return {'dataset_id': ds.id, 'is_demo': ds.is_demo, 'series': out}


@router.get('/series')
def series_by_kind(destination_id: str, kind: str, variables: str, start: str | None = None, end: str | None = None,
                   db: Session = Depends(get_db)):
    ds = dsvc.latest_dataset(db, destination_id, kind)
    if not ds:
        return {'dataset': None, 'series': []}
    defs = {d['name']: d for d in ds.variable_defs or []}
    out = [{'variable': v, 'label': defs.get(v, {}).get('label', v), 'unit': defs.get(v, {}).get('unit', ''),
            'points': dsvc.series(db, ds, v, start, end)} for v in variables.split(',') if v]
    return {'dataset': dsvc.dataset_dict(db, ds, with_counts=False), 'series': out}


@router.get('/datasets/{ds_id}/export.csv')
def export_csv(ds_id: str, layout: str = 'long', start: str | None = None, end: str | None = None,
               db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    body = csv_import.observations_csv(dsvc.observations(db, ds_id, start, end), layout)
    prefix = 'DEMO_' if ds.is_demo else ''
    return Response(body, media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{prefix}{ds.id}.{layout}.csv"'})


@router.get('/datasets/{ds_id}/export.json')
def export_json(ds_id: str, db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    obs = dsvc.observations(db, ds_id)
    body = {'dataset': dsvc.dataset_dict(db, ds), 'observations': [
        {'period': o.period, 'variable': o.variable, 'value': o.value, 'unit': o.unit, 'quality_flag': o.quality_flag} for o in obs]}
    return Response(json.dumps(body, indent=1, default=str), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="{"DEMO_" if ds.is_demo else ""}{ds.id}.json"'})


@router.get('/datasets/{ds_id}/template.csv', response_class=PlainTextResponse)
def dataset_template(ds_id: str, layout: str = 'wide', db: Session = Depends(get_db)):
    ds = _ds(db, ds_id)
    defs = ds.variable_defs or catalog.kind_variables(ds.kind) or [{'name': 'my_variable', 'unit': ''}]
    return Response(csv_import.template_csv(defs, layout, ds.frequency), media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="template-{ds.id}-{layout}.csv"'})


# ----------------------------------------------------------------------------- import wizard

class DetectIn(BaseModel):
    token: str
    dataset_id: str | None = None
    kind: str | None = None
    encoding: str | None = None
    delimiter: str | None = None
    has_header: bool | None = None


class PasteIn(BaseModel):
    content: str = Field(min_length=1)
    file_name: str = 'pasted.json'
    dataset_id: str | None = None
    kind: str | None = None


class MappingIn(BaseModel):
    token: str
    dataset_id: str
    mapping: dict
    encoding: str | None = None
    delimiter: str | None = None
    has_header: bool | None = None
    skip_invalid: bool = False
    mode: str = 'upsert'


def _defs_for(db, dataset_id: str | None, kind: str | None) -> list[dict]:
    if dataset_id:
        ds = db.get(Dataset, dataset_id)
        if ds:
            return ds.variable_defs or []
    return catalog.kind_variables(kind or 'custom')


def _wrap(fn):
    try:
        return fn()
    except (csv_import.ImportError_, dsvc.DatasetError) as exc:
        raise HTTPException(422, str(exc))


@router.post('/imports/upload')
async def upload(file: UploadFile = File(...), dataset_id: str | None = Form(None), kind: str | None = Form(None),
                 db: Session = Depends(get_db)):
    content = await file.read()
    staged = _wrap(lambda: csv_import.stage(content, file.filename or 'upload.csv'))
    det = _wrap(lambda: csv_import.detect(content, staged['file_name'], _defs_for(db, dataset_id, kind)))
    return {**staged, **det}


@router.post('/imports/paste')
def paste(body: PasteIn, db: Session = Depends(get_db)):
    content = body.content.encode('utf-8')
    staged = _wrap(lambda: csv_import.stage(content, body.file_name))
    det = _wrap(lambda: csv_import.detect(content, body.file_name, _defs_for(db, body.dataset_id, body.kind)))
    return {**staged, **det}


@router.post('/imports/detect')
def detect(body: DetectIn, db: Session = Depends(get_db)):
    content, name = _wrap(lambda: csv_import.load_staged(body.token))
    det = _wrap(lambda: csv_import.detect(content, name, _defs_for(db, body.dataset_id, body.kind), body.encoding,
                                          body.delimiter, body.has_header))
    return {'token': body.token, **det}


def _prepare(db, body: MappingIn):
    ds = _ds(db, body.dataset_id)
    content, name = _wrap(lambda: csv_import.load_staged(body.token))
    t = _wrap(lambda: csv_import.parse_table(content, name, body.encoding, body.delimiter, body.has_header))
    rep = _wrap(lambda: csv_import.validate(db, ds, t, body.mapping))
    return ds, content, name, t, rep


@router.post('/imports/validate')
def validate_import(body: MappingIn, db: Session = Depends(get_db)):
    ds, content, name, t, rep = _prepare(db, body)
    from ..util import sha256_bytes
    prior = db.scalar(select(ImportRecord).where(ImportRecord.dataset_id == ds.id, ImportRecord.file_hash == sha256_bytes(content)))
    return csv_import.summarise(t, rep, {'dataset_id': ds.id, 'file_name': name, 'archived': ds.status == 'archived',
                                         'already_imported': prior.id if prior else None})


@router.post('/imports/commit', status_code=201)
def commit_import(body: MappingIn, db: Session = Depends(get_db)):
    ds, content, name, t, rep = _prepare(db, body)
    res = _wrap(lambda: csv_import.commit(db, ds, content, name, t, body.mapping, rep, body.skip_invalid, body.mode))
    if res['status'] == 'committed':
        audit.log(db, 'import.commit', ds.id, file=name, file_hash=res['file_hash'], inserted=res['inserted'],
                  updated=res['updated'], skipped=res['skipped'])
    return res


@router.get('/periods/normalise')
def normalise_period(value: str, date_format: str = 'DMY'):
    p = periods.normalise(value, date_format)
    return {'input': value, 'period': p, 'kind': periods.kind(p) if p else None}
