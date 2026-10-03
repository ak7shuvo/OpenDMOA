"""Registers: heritage assets, incidents, early warnings, readiness checklist,
infrastructure projects, publications (generic CRUD), GIS layers, briefs, citation."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BACKEND_DIR
from ..db import get_db
from ..models import (Asset, Brief, Destination, EarlyWarning, GisLayer, Incident, InfraProject, Publication,
                      ReadinessItem, Run)
from ..services import audit, briefs as briefsvc
from ..util import new_id

router = APIRouter()

ENTITIES = {
    'assets': (Asset, {'name', 'asset_type', 'category', 'condition', 'threats', 'protection_status', 'latitude', 'longitude',
                       'gis_layer_id', 'last_assessed', 'notes', 'destination_id'}, 'AST'),
    'incidents': (Incident, {'occurred_at', 'hazard', 'severity', 'description', 'status', 'response', 'destination_id'}, 'INC'),
    'warnings': (EarlyWarning, {'hazard', 'level', 'issued_at', 'valid_until', 'message', 'source', 'active', 'destination_id'}, 'EW'),
    'readiness': (ReadinessItem, {'category', 'item', 'done', 'owner', 'destination_id'}, 'RDY'),
    'projects': (InfraProject, {'name', 'category', 'stage', 'budget_bdt_m', 'start', 'end', 'notes', 'destination_id'}, 'PRJ'),
    'publications': (Publication, {'title', 'authors', 'pub_type', 'status', 'venue', 'due', 'brief_id', 'notes'}, 'PUB'),
}
REQUIRED = {'assets': ['name', 'destination_id'], 'incidents': ['occurred_at', 'hazard', 'destination_id'],
            'warnings': ['hazard', 'issued_at', 'destination_id'], 'readiness': ['category', 'item', 'destination_id'],
            'projects': ['name', 'destination_id'], 'publications': ['title']}
CHOICES = {
    ('assets', 'condition'): {'good', 'fair', 'poor', 'critical'},
    ('assets', 'asset_type'): {'natural', 'cultural', 'mixed'},
    ('incidents', 'severity'): {'minor', 'moderate', 'major', 'critical'},
    ('incidents', 'status'): {'open', 'monitoring', 'closed'},
    ('warnings', 'level'): {'advisory', 'watch', 'warning', 'emergency'},
    ('projects', 'stage'): {'proposed', 'planned', 'building', 'done', 'stalled'},
    ('publications', 'status'): {'idea', 'draft', 'review', 'submitted', 'published'},
}


def _row(obj) -> dict:
    d = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
    return d


def _check(entity: str, data: dict, db) -> None:
    for (ent, field), allowed in CHOICES.items():
        if ent == entity and field in data and data[field] not in allowed:
            raise HTTPException(422, f'{field} must be one of {sorted(allowed)}')
    if 'destination_id' in data and data['destination_id'] and not db.get(Destination, data['destination_id']):
        raise HTTPException(422, 'unknown destination')
    if 'threats' in data and isinstance(data['threats'], str):
        data['threats'] = [t.strip() for t in data['threats'].split(',') if t.strip()]


def _make_routes(entity: str):
    model, fields, prefix = ENTITIES[entity]

    @router.get(f'/{entity}', name=f'list_{entity}')
    def list_rows(destination_id: str | None = None, db: Session = Depends(get_db)):
        q = select(model)
        if destination_id and hasattr(model, 'destination_id'):
            q = q.where(model.destination_id == destination_id)
        return [_row(r) for r in db.scalars(q)]

    @router.post(f'/{entity}', status_code=201, name=f'create_{entity}')
    def create_row(body: dict, db: Session = Depends(get_db)):
        data = {k: v for k, v in body.items() if k in fields}
        missing = [k for k in REQUIRED[entity] if not data.get(k)]
        if missing:
            raise HTTPException(422, f'missing fields: {missing}')
        _check(entity, data, db)
        obj = model(id=new_id(prefix), **data)
        db.add(obj)
        db.commit()
        audit.log(db, f'{entity}.create', obj.id)
        return _row(obj)

    @router.patch(f'/{entity}/{{row_id}}', name=f'update_{entity}')
    def update_row(row_id: str, body: dict, db: Session = Depends(get_db)):
        obj = db.get(model, row_id)
        if not obj:
            raise HTTPException(404, 'not found')
        data = {k: v for k, v in body.items() if k in fields}
        _check(entity, data, db)
        for k, v in data.items():
            setattr(obj, k, v)
        db.commit()
        return _row(obj)

    @router.delete(f'/{entity}/{{row_id}}', name=f'delete_{entity}')
    def delete_row(row_id: str, db: Session = Depends(get_db)):
        obj = db.get(model, row_id)
        if not obj:
            raise HTTPException(404, 'not found')
        db.delete(obj)
        db.commit()
        audit.log(db, f'{entity}.delete', row_id)
        return {'deleted': row_id}


for _e in ENTITIES:
    _make_routes(_e)


# ----------------------------------------------------------------------------- GIS

def _validate_geojson(gj: dict) -> dict:
    if not isinstance(gj, dict) or gj.get('type') not in ('FeatureCollection', 'Feature', 'Polygon', 'MultiPolygon', 'LineString',
                                                          'MultiLineString', 'Point', 'MultiPoint', 'GeometryCollection'):
        raise HTTPException(422, 'not a GeoJSON object (expected FeatureCollection, Feature or geometry)')
    if gj['type'] == 'Feature':
        gj = {'type': 'FeatureCollection', 'features': [gj]}
    elif gj['type'] != 'FeatureCollection':
        gj = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': gj}]}
    feats = gj.get('features') or []
    if not feats:
        raise HTTPException(422, 'GeoJSON has no features')
    if len(json.dumps(gj)) > 8_000_000:
        raise HTTPException(422, 'GeoJSON larger than 8 MB — simplify it first')

    def coords_ok(c):
        if isinstance(c, (int, float)):
            return True
        if isinstance(c, list) and len(c) >= 2 and all(isinstance(x, (int, float)) for x in c[:2]):
            return -180 <= c[0] <= 180 and -90 <= c[1] <= 90
        return isinstance(c, list) and all(coords_ok(x) for x in c)
    for f in feats:
        g = (f or {}).get('geometry') or {}
        if g.get('coordinates') is not None and not coords_ok(g['coordinates']):
            raise HTTPException(422, 'coordinates must be WGS84 longitude/latitude (EPSG:4326)')
    return gj


def _layer(l: GisLayer, full: bool = True) -> dict:
    d = {'id': l.id, 'name': l.name, 'category': l.category, 'destination_id': l.destination_id, 'source': l.source,
         'color': l.color, 'visible': l.visible, 'is_demo': l.is_demo, 'created_at': l.created_at.isoformat(),
         'features': len((l.geojson or {}).get('features', []))}
    if full:
        d['geojson'] = l.geojson
    return d


@router.get('/gis/layers')
def gis_layers(destination_id: str | None = None, full: bool = True, db: Session = Depends(get_db)):
    q = select(GisLayer)
    rows = db.scalars(q).all()
    if destination_id:
        rows = [r for r in rows if r.destination_id in (None, destination_id)]
    return [_layer(r, full) for r in rows]


@router.post('/gis/layers', status_code=201)
async def upload_layer(file: UploadFile = File(...), name: str = Form(''), destination_id: str | None = Form(None),
                       category: str = Form('custom'), color: str = Form('#D8343F'), db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        gj = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, f'invalid JSON: {exc}')
    gj = _validate_geojson(gj)
    if destination_id and not db.get(Destination, destination_id):
        raise HTTPException(422, 'unknown destination')
    layer = GisLayer(id=new_id('GIS'), name=name or (file.filename or 'layer').rsplit('.', 1)[0], category=category,
                     destination_id=destination_id or None, geojson=gj, source=f'upload: {file.filename}', color=color)
    db.add(layer)
    db.commit()
    audit.log(db, 'gis.upload', layer.id, features=len(gj['features']))
    return _layer(layer)


@router.patch('/gis/layers/{layer_id}')
def patch_layer(layer_id: str, body: dict, db: Session = Depends(get_db)):
    l = db.get(GisLayer, layer_id)
    if not l:
        raise HTTPException(404, 'layer not found')
    for k in ('name', 'visible', 'color', 'category'):
        if k in body:
            setattr(l, k, body[k])
    db.commit()
    return _layer(l)


@router.delete('/gis/layers/{layer_id}')
def delete_layer(layer_id: str, db: Session = Depends(get_db)):
    l = db.get(GisLayer, layer_id)
    if not l:
        raise HTTPException(404, 'layer not found')
    db.delete(l)
    db.commit()
    audit.log(db, 'gis.delete', layer_id)
    return {'deleted': layer_id}


@router.get('/gis/basemap')
def basemap():
    p = BACKEND_DIR / 'app' / 'seed' / 'basemap.geojson'
    return json.loads(p.read_text(encoding='utf-8'))


# ----------------------------------------------------------------------------- briefs

class BriefIn(BaseModel):
    title: str
    destination_id: str | None = None
    run_ids: list[str]
    summary: str = ''
    recommendations: list[str] = []


def _brief(b: Brief, full: bool = True) -> dict:
    d = {'id': b.id, 'title': b.title, 'destination_id': b.destination_id, 'run_ids': b.run_ids, 'summary': b.summary,
         'recommendations': b.recommendations, 'created_at': b.created_at.isoformat()}
    if full:
        d['markdown'] = b.markdown
    return d


@router.get('/briefs')
def list_briefs(db: Session = Depends(get_db)):
    return [_brief(b, False) for b in db.scalars(select(Brief).order_by(Brief.created_at.desc()))]


@router.post('/briefs', status_code=201)
def create_brief(body: BriefIn, db: Session = Depends(get_db)):
    runs = [db.get(Run, i) for i in body.run_ids]
    if not runs or any(r is None for r in runs):
        raise HTTPException(422, 'select at least one existing run')
    md = briefsvc.build_markdown(db, body.title, body.destination_id, runs, body.summary, body.recommendations)
    b = Brief(id=new_id('BRF'), title=body.title, destination_id=body.destination_id, run_ids=body.run_ids,
              summary=body.summary, recommendations=body.recommendations, markdown=md)
    db.add(b)
    db.commit()
    audit.log(db, 'brief.create', b.id, runs=len(runs))
    return _brief(b)


def _get_brief(db, brief_id: str) -> Brief:
    b = db.get(Brief, brief_id)
    if not b:
        raise HTTPException(404, 'brief not found')
    return b


@router.get('/briefs/{brief_id}')
def get_brief(brief_id: str, db: Session = Depends(get_db)):
    return _brief(_get_brief(db, brief_id))


@router.get('/briefs/{brief_id}/brief.md', response_class=PlainTextResponse)
def brief_md(brief_id: str, db: Session = Depends(get_db)):
    b = _get_brief(db, brief_id)
    return PlainTextResponse(b.markdown, media_type='text/markdown',
                             headers={'Content-Disposition': f'attachment; filename="{b.id}.md"'})


@router.get('/briefs/{brief_id}/brief.html', response_class=HTMLResponse)
def brief_html(brief_id: str, download: bool = False, db: Session = Depends(get_db)):
    b = _get_brief(db, brief_id)
    headers = {'Content-Disposition': f'attachment; filename="{b.id}.html"'} if download else {}
    return HTMLResponse(briefsvc.markdown_to_html(b.markdown, b.title), headers=headers)


@router.delete('/briefs/{brief_id}')
def delete_brief(brief_id: str, db: Session = Depends(get_db)):
    b = _get_brief(db, brief_id)
    db.delete(b)
    db.commit()
    return {'deleted': brief_id}


@router.get('/citation')
def citation():
    return briefsvc.citations()
