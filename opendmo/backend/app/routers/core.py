"""Health, meta, destinations, catalog/glossary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import __version__, catalog
from ..config import get_settings
from ..db import get_db, get_engine
from ..models import Dataset, Destination, Observation
from ..services import audit, csv_import, summary
from ..services.system import get_app_settings
from ..util import slugify

router = APIRouter()


@router.get('/health')
def health():
    s = get_settings()
    try:
        with get_engine().connect() as conn:
            conn.execute(text('SELECT 1'))
        db_ok = True
    except Exception as exc:  # pragma: no cover
        return {'status': 'degraded', 'detail': str(exc), 'version': __version__}
    return {'status': 'ok', 'version': __version__, 'database': s.db_engine, 'db_ok': db_ok, 'local_first': True}


@router.get('/meta')
def meta(db: Session = Depends(get_db)):
    extent = db.execute(select(func.min(Observation.period), func.max(Observation.period))).one()
    demo = db.scalar(select(func.count(Dataset.id)).where(Dataset.is_demo.is_(True)))
    total = db.scalar(select(func.count(Dataset.id)))
    return {
        'product': 'OpenDMO', 'name': 'Open Destination Management & Analytics Platform', 'version': __version__,
        'mode': 'local-first', 'network': 'offline — no telemetry, no CDN, no remote tiles; outbound only on explicit model install',
        'demo_policy': 'Synthetic seed-pack data is always badged DEMO and removable from System › Control Board.',
        'settings': get_app_settings(db), 'data_extent': {'first_period': extent[0], 'last_period': extent[1]},
        'datasets': total, 'demo_datasets': demo,
        'cores': [
            {'id': 'observatory', 'num': '01', 'name': 'Destination Observatory'},
            {'id': 'climate', 'num': '02', 'name': 'Climate & Risk'},
            {'id': 'economy', 'num': '03', 'name': 'Future & Economy'},
            {'id': 'lab', 'num': '04', 'name': 'Research & Policy Lab'},
        ],
        'information_chain': ['LOCATION', 'TIME', 'OBSERVATION', 'CHANGE', 'RISK', 'FORECAST', 'SCENARIO', 'DECISION'],
    }


# ----------------------------------------------------------------------------- destinations

class DestinationIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    region: str = ''
    country: str = 'Bangladesh'
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    area_km2: float | None = Field(default=None, ge=0)
    description: str = ''
    attributes: dict = {}
    id: str | None = None


class DestinationPatch(BaseModel):
    name: str | None = None
    region: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    area_km2: float | None = Field(default=None, ge=0)
    description: str | None = None
    attributes: dict | None = None


def dest_dict(d: Destination) -> dict:
    return {'id': d.id, 'name': d.name, 'region': d.region, 'country': d.country, 'latitude': d.latitude,
            'longitude': d.longitude, 'area_km2': d.area_km2, 'description': d.description, 'is_pilot': d.is_pilot,
            'attributes': d.attributes or {}}


@router.get('/destinations')
def list_destinations(db: Session = Depends(get_db)):
    rows = db.scalars(select(Destination).order_by(Destination.is_pilot.desc(), Destination.name)).all()
    return [dest_dict(d) for d in rows]


@router.post('/destinations', status_code=201)
def create_destination(body: DestinationIn, db: Session = Depends(get_db)):
    did = slugify(body.id or body.name, 32)
    if db.get(Destination, did):
        raise HTTPException(409, f'destination id already exists: {did}')
    d = Destination(id=did, name=body.name.strip(), region=body.region, country=body.country, latitude=body.latitude,
                    longitude=body.longitude, area_km2=body.area_km2, description=body.description,
                    attributes=body.attributes, is_pilot=False)
    db.add(d)
    db.commit()
    audit.log(db, 'destination.create', did, name=d.name)
    return dest_dict(d)


@router.get('/destinations/{dest_id}')
def get_destination(dest_id: str, db: Session = Depends(get_db)):
    d = db.get(Destination, dest_id)
    if not d:
        raise HTTPException(404, 'destination not found')
    return dest_dict(d)


@router.patch('/destinations/{dest_id}')
def patch_destination(dest_id: str, body: DestinationPatch, db: Session = Depends(get_db)):
    d = db.get(Destination, dest_id)
    if not d:
        raise HTTPException(404, 'destination not found')
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(d, k, v)
    db.commit()
    audit.log(db, 'destination.update', dest_id, fields=sorted(changes))
    return dest_dict(d)


@router.delete('/destinations/{dest_id}')
def delete_destination(dest_id: str, db: Session = Depends(get_db)):
    d = db.get(Destination, dest_id)
    if not d:
        raise HTTPException(404, 'destination not found')
    if d.is_pilot:
        raise HTTPException(409, 'pilot destinations cannot be deleted')
    if db.scalar(select(func.count(Dataset.id)).where(Dataset.destination_id == dest_id)):
        raise HTTPException(409, 'destination has datasets — delete or move them first')
    db.delete(d)
    db.commit()
    audit.log(db, 'destination.delete', dest_id)
    return {'deleted': dest_id}


@router.get('/destinations/{dest_id}/summary')
def destination_summary(dest_id: str, start: str | None = None, end: str | None = None, core: str | None = None,
                        db: Session = Depends(get_db)):
    if not db.get(Destination, dest_id):
        raise HTTPException(404, 'destination not found')
    return summary.destination_summary(db, dest_id, start, end, core)


# ----------------------------------------------------------------------------- catalog & glossary

@router.get('/catalog/kinds')
def kinds():
    return catalog.list_kinds()


@router.get('/catalog/kinds/{kind}/template.csv', response_class=PlainTextResponse)
def kind_template(kind: str, layout: str = 'wide'):
    if kind not in catalog.DATASET_KINDS:
        raise HTTPException(404, 'unknown dataset kind')
    k = catalog.DATASET_KINDS[kind]
    defs = k['variables'] or [{'name': 'my_variable', 'unit': ''}]
    body = csv_import.template_csv(defs, layout, k['frequency'])
    return PlainTextResponse(body, media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename="opendmo-template-{kind}-{layout}.csv"'})


@router.get('/catalog/indicators')
def indicators():
    return catalog.INDICATORS


@router.get('/glossary')
def glossary():
    terms = [{'term': i['label'], 'id': i['id'], 'unit': i['unit'], 'core': i['core'], 'definition': i['description'],
              'thresholds': None if i['direction'] is None else {'direction': i['direction'], 'watch': i['watch'], 'risk': i['risk']},
              'source': f"{i['kind']}.{i['variable']} ({i['aggregation']})"} for i in catalog.INDICATORS]
    for kind, k in catalog.DATASET_KINDS.items():
        for v in k['variables']:
            terms.append({'term': v['label'], 'id': f'{kind}.{v["name"]}', 'unit': v['unit'], 'core': k['core'],
                          'definition': v['description'] or f"Variable '{v['name']}' of the {k['label']} template.",
                          'thresholds': None, 'source': f'{kind} template'})
    terms += [{'term': g['term'], 'id': None, 'unit': '', 'core': 'lab', 'definition': g['definition'], 'thresholds': None,
               'source': 'concept'} for g in catalog.GLOSSARY_EXTRA]
    return sorted(terms, key=lambda t: t['term'].lower())
