"""System › Control Board API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calculations
from ..db import get_db
from ..models import AuditLog, MethodState
from ..seed import packs
from ..services import audit, runs as runsvc, system as sys_svc

router = APIRouter(prefix='/system')


@router.get('/status')
def status(db: Session = Depends(get_db)):
    return sys_svc.status(db)


@router.get('/diagnostics')
def diagnostics(db: Session = Depends(get_db)):
    return sys_svc.diagnostics(db)


# ----------------------------------------------------------------------------- demo data

@router.get('/seed-packs')
def seed_packs(db: Session = Depends(get_db)):
    return packs.pack_status(db)


@router.post('/seed-packs/{dest_id}/load')
def load_pack(dest_id: str, db: Session = Depends(get_db)):
    try:
        res = packs.load_pack(db, dest_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    audit.log(db, 'demo.load', dest_id, **{k: v for k, v in res.items() if k != 'destination_id'})
    return res


@router.post('/seed-packs/{dest_id}/remove')
def remove_pack(dest_id: str, db: Session = Depends(get_db)):
    res = packs.remove_pack(db, dest_id)
    audit.log(db, 'demo.remove', dest_id, **res['deleted'])
    return res


@router.post('/demo/load-all')
def load_all(db: Session = Depends(get_db)):
    out = [packs.load_pack(db, p['id']) for p in packs.PILOTS]
    audit.log(db, 'demo.load_all', 'all')
    return out


@router.post('/demo/remove-all')
def remove_all(db: Session = Depends(get_db)):
    out = [packs.remove_pack(db, p['id']) for p in packs.PILOTS]
    audit.log(db, 'demo.remove_all', 'all')
    return out


class ConfirmIn(BaseModel):
    confirm: str


@router.post('/reset')
def reset(body: ConfirmIn, db: Session = Depends(get_db)):
    if body.confirm != 'RESET':
        raise HTTPException(422, 'type RESET to confirm')
    backup, name = sys_svc.make_backup(db, save=True)
    sys_svc.reset_database(db)
    from ..db import SessionLocal
    fresh = SessionLocal()
    try:
        audit.log(fresh, 'system.reset', 'database', safety_backup=name)
    finally:
        fresh.close()
    return {'status': 'reset', 'safety_backup': name}


# ----------------------------------------------------------------------------- backup / restore / export

@router.get('/backup')
def backup(db: Session = Depends(get_db)):
    data, name = sys_svc.make_backup(db, save=True)
    audit.log(db, 'system.backup', name, bytes=len(data))
    return Response(data, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{name}"'})


@router.get('/backups')
def backups():
    return sys_svc.list_backups()


@router.post('/restore')
async def restore(file: UploadFile = File(...), confirm: str = Form(''), db: Session = Depends(get_db)):
    if confirm != 'RESTORE':
        raise HTTPException(422, 'type RESTORE to confirm')
    content = await file.read()
    safety, name = sys_svc.make_backup(db, save=True)
    try:
        res = sys_svc.restore_backup(db, content)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    audit.log(db, 'system.restore', file.filename or 'upload', safety_backup=name, tables=res['restored'])
    return {**res, 'safety_backup': name}


@router.get('/export')
def export(db: Session = Depends(get_db)):
    data = sys_svc.export_all(db)
    audit.log(db, 'system.export', 'all', bytes=len(data))
    return Response(data, media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="opendmo-export.zip"'})


# ----------------------------------------------------------------------------- registry switches

class EnableIn(BaseModel):
    enabled: bool


@router.get('/methods')
def methods(db: Session = Depends(get_db)):
    return [{'id': m.id, 'name': m.name, 'version': m.version, 'core': m.core, 'kind': m.kind, 'screening': m.screening,
             'enabled': runsvc.is_enabled(db, m.id)} for m in calculations.all_methods()]


@router.post('/methods/{method_id}')
def toggle_method(method_id: str, body: EnableIn, db: Session = Depends(get_db)):
    if not calculations.get(method_id):
        raise HTTPException(404, 'unknown method')
    st = db.get(MethodState, method_id) or MethodState(method_id=method_id)
    st.enabled = body.enabled
    db.merge(st)
    db.commit()
    audit.log(db, 'method.enable' if body.enabled else 'method.disable', method_id)
    return {'id': method_id, 'enabled': body.enabled}


# ----------------------------------------------------------------------------- audit & settings

@router.get('/audit')
def audit_log(action: str | None = None, limit: int = 300, db: Session = Depends(get_db)):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.like(f'{action}%'))
    rows = db.scalars(q.order_by(AuditLog.id.desc()).limit(min(limit, 2000)))
    return [{'id': r.id, 'ts': r.ts.isoformat(), 'action': r.action, 'target': r.target, 'detail': r.detail, 'actor': r.actor}
            for r in rows]


@router.get('/settings')
def get_settings_(db: Session = Depends(get_db)):
    return sys_svc.get_app_settings(db)


@router.put('/settings')
def put_settings(body: dict, db: Session = Depends(get_db)):
    try:
        res, restart = sys_svc.update_app_settings(db, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    audit.log(db, 'settings.update', ','.join(sorted(body)), restart_required=restart)
    return {'settings': res, 'restart_required': restart}
