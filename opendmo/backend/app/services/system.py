"""Control Board services: backup/restore, export-all, reset, settings, diagnostics."""
from __future__ import annotations

import io
import json
import os
import platform
import secrets
import shutil
import sys
import zipfile
from datetime import date, datetime, timezone
from importlib import metadata
from pathlib import Path

from sqlalchemy import delete, func, select

from .. import __version__
from ..config import PRODUCT_ROOT, get_settings
from ..db import Base, create_all, get_engine
from ..models import ALL_TABLES, AppSetting, Dataset, Run, UTCDateTime
from ..seed import packs
from . import csv_import, datasets as dsvc
from .models import register_bundled

BACKUP_FORMAT = 'opendmo-backup/2'
STORES = ['models', 'uploads']
LAUNCHER_FILE = PRODUCT_ROOT / 'opendmo.settings.json'

DEFAULT_SETTINGS = {
    'theme': 'dark', 'units': 'metric', 'date_format': 'YYYY-MM-DD', 'currency': 'BDT',
    'default_range_months': 12, 'onboarding_complete': False,
}


# ----------------------------------------------------------------------------- settings

def get_app_settings(db) -> dict:
    out = dict(DEFAULT_SETTINGS)
    for row in db.scalars(select(AppSetting)):
        out[row.key] = row.value
    launcher = read_launcher()
    s = get_settings()
    out['port'] = launcher.get('port', s.port)
    out['data_dir'] = launcher.get('data_dir', s.data_dir)
    out['effective'] = {'port': s.port, 'data_dir': str(s.data_path)}
    return out


def read_launcher() -> dict:
    try:
        return json.loads(LAUNCHER_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def update_app_settings(db, changes: dict) -> tuple[dict, bool]:
    restart = False
    launcher = read_launcher()
    for k, v in changes.items():
        if k in ('port', 'data_dir'):
            if k == 'port':
                v = int(v)
                if not 1024 <= v <= 65535:
                    raise ValueError('port must be within 1024–65535')
            if k == 'data_dir':
                v = str(Path(str(v)).expanduser())
            if launcher.get(k) != v:
                launcher[k] = v
                restart = True
            continue
        if k not in DEFAULT_SETTINGS:
            raise ValueError(f'unknown setting: {k}')
        row = db.get(AppSetting, k) or AppSetting(key=k)
        row.value = v
        db.merge(row)
    db.commit()
    if restart:
        LAUNCHER_FILE.write_text(json.dumps(launcher, indent=2), encoding='utf-8')
    return get_app_settings(db), restart


# ----------------------------------------------------------------------------- status & diagnostics

def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p.exists() else 0


def status(db) -> dict:
    s = get_settings()
    db_size = Path(s.db_file).stat().st_size if s.db_file and Path(s.db_file).exists() else None
    counts = {t.__tablename__: db.scalar(select(func.count()).select_from(t)) for t in ALL_TABLES}
    return {
        'backend': 'ok', 'version': __version__, 'db_engine': s.db_engine,
        'db_path': s.db_file or s.db_url.split('@')[-1], 'db_size_bytes': db_size,
        'data_dir': str(s.data_path), 'stores': {n: {'path': str(s.store(n)), 'bytes': _dir_size(s.store(n))} for n in STORES},
        'counts': counts, 'demo_datasets': db.scalar(select(func.count(Dataset.id)).where(Dataset.is_demo.is_(True))),
        'static_frontend': Path(s.static_dir, 'index.html').exists(),
        'server_time': datetime.now(timezone.utc).isoformat(),
    }


def diagnostics(db) -> dict:
    s = get_settings()
    pkgs = {}
    for name in ['fastapi', 'starlette', 'uvicorn', 'sqlalchemy', 'pydantic', 'pydantic-settings', 'python-multipart',
                 'httpx', 'numpy', 'psycopg']:
        try:
            pkgs[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pkgs[name] = None
    usage = shutil.disk_usage(s.data_path)
    st = status(db)
    report = {
        'opendmo_version': __version__, 'os': platform.platform(), 'machine': platform.machine(),
        'python': sys.version.split()[0], 'python_executable': sys.executable, 'packages': pkgs,
        'db_engine': st['db_engine'], 'db_path': st['db_path'], 'db_size_bytes': st['db_size_bytes'],
        'data_dir': st['data_dir'], 'disk_free_gb': round(usage.free / 1e9, 2), 'static_frontend': st['static_frontend'],
        'allow_pickle_models': s.allow_pickle_models, 'network_policy': 'offline; outbound only on explicit model install',
        'record_counts': st['counts'], 'generated_at': datetime.now(timezone.utc).isoformat(),
    }
    report['text'] = '\n'.join(f'{k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}'
                               for k, v in report.items())
    return report


# ----------------------------------------------------------------------------- backup / restore

def _row_dict(obj) -> dict:
    out = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.key)
        out[col.key] = v.isoformat() if isinstance(v, (datetime, date)) else v
    return out


def dump_tables(db) -> dict[str, list[dict]]:
    return {t.__tablename__: [_row_dict(o) for o in db.scalars(select(t))] for t in ALL_TABLES}


def make_backup(db, save: bool = True) -> tuple[bytes, str]:
    s = get_settings()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    name = f'opendmo-backup-{stamp}-{secrets.token_hex(2)}.zip'
    buf = io.BytesIO()
    tables = dump_tables(db)
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps({
            'format': BACKUP_FORMAT, 'opendmo_version': __version__, 'created_at': datetime.now(timezone.utc).isoformat(),
            'db_engine': s.db_engine, 'tables': {k: len(v) for k, v in tables.items()}}, indent=2))
        for tname, rows in tables.items():
            z.writestr(f'tables/{tname}.json', json.dumps(rows, default=str))
        for store in STORES:
            root = s.store(store)
            for f in root.rglob('*'):
                if f.is_file() and 'staging' not in f.relative_to(root).parts:
                    z.write(f, f'stores/{store}/{f.relative_to(root).as_posix()}')
    data = buf.getvalue()
    if save:
        (s.store('backups') / name).write_bytes(data)
    return data, name


def list_backups() -> list[dict]:
    d = get_settings().store('backups')
    return [{'name': f.name, 'bytes': f.stat().st_size,
             'created_at': datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()}
            for f in sorted(d.glob('*.zip'), reverse=True)]


def _coerce(model, row: dict) -> dict:
    cols = {c.key: c for c in model.__table__.columns}
    out = {}
    for k, v in row.items():
        if k not in cols:
            continue
        if isinstance(cols[k].type, UTCDateTime) and isinstance(v, str):
            v = datetime.fromisoformat(v)
        out[k] = v
    return out


def restore_backup(db, content: bytes) -> dict:
    try:
        z = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError('not a zip file') from exc
    with z:
        try:
            manifest = json.loads(z.read('manifest.json'))
        except KeyError as exc:
            raise ValueError('not an OpenDMO backup (manifest.json missing)') from exc
        if manifest.get('format') != BACKUP_FORMAT:
            raise ValueError(f"unsupported backup format: {manifest.get('format')}")
        tables = {}
        for t in ALL_TABLES:
            try:
                tables[t] = json.loads(z.read(f'tables/{t.__tablename__}.json'))
            except KeyError:
                tables[t] = []
        for t in reversed(ALL_TABLES):
            db.execute(delete(t))
        db.flush()
        for t in ALL_TABLES:
            for row in tables[t]:
                db.add(t(**_coerce(t, row)))
            db.flush()
        db.commit()
        s = get_settings()
        for store in STORES:
            root = s.store(store)
            for member in z.namelist():
                prefix = f'stores/{store}/'
                if member.startswith(prefix) and not member.endswith('/'):
                    target = (root / member[len(prefix):]).resolve()
                    if not str(target).startswith(str(root.resolve())):
                        raise ValueError(f'unsafe path in backup: {member}')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(member))
        # model package paths are machine-specific: re-point them into this store
        from ..models import ModelPackage
        for pkg in db.scalars(select(ModelPackage)):
            local = s.store('models') / pkg.id / pkg.version
            if local.exists():
                pkg.package_path = str(local)
        db.commit()
    return {'restored': {t.__tablename__: len(rows) for t, rows in tables.items()}, 'manifest': manifest}


def reset_database(db) -> None:
    db.close()
    eng = get_engine()
    Base.metadata.drop_all(eng)
    create_all()
    from ..db import SessionLocal
    fresh = SessionLocal()
    try:
        packs.ensure_pilots(fresh)
        register_bundled(fresh)
    finally:
        fresh.close()


def export_all(db) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        index = []
        for ds in db.scalars(select(Dataset)):
            obs = dsvc.observations(db, ds.id)
            base = f'datasets/{ds.destination_id}/{ds.id}'
            z.writestr(f'{base}.long.csv', csv_import.observations_csv(obs, 'long'))
            z.writestr(f'{base}.wide.csv', csv_import.observations_csv(obs, 'wide'))
            z.writestr(f'{base}.json', json.dumps({'dataset': dsvc.dataset_dict(db, ds), 'observations': [
                {'period': o.period, 'variable': o.variable, 'value': o.value, 'unit': o.unit, 'quality_flag': o.quality_flag}
                for o in obs]}, indent=1, default=str))
            index.append({'id': ds.id, 'is_demo': ds.is_demo, 'observations': len(obs)})
        from .runs import run_dict
        z.writestr('runs.json', json.dumps([run_dict(r) for r in db.scalars(select(Run))], indent=1, default=str))
        tables = dump_tables(db)
        for name in ('destinations', 'assets', 'incidents', 'warnings', 'readiness_items', 'infra_projects',
                     'gis_layers', 'briefs', 'publications', 'scenarios'):
            z.writestr(f'{name}.json', json.dumps(tables[name], indent=1, default=str))
        z.writestr('README.txt', f'OpenDMO {__version__} full data export, {datetime.now(timezone.utc).isoformat()}\n'
                                 'Rows with is_demo = true are synthetic DEMO data.\n')
        z.writestr('index.json', json.dumps(index, indent=1))
    return buf.getvalue()


def data_dir_info() -> dict:
    return {'data_dir': str(get_settings().data_path), 'env_override': os.environ.get('OPENDMO_DATA_DIR')}
