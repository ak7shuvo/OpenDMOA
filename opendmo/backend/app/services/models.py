"""Model registry & runtime service.

Install flow (explicit user action only): GitHub URL -> download zipball ->
safe extraction (no path traversal, size cap) -> contract validation ->
copy into the local model store -> register (status 'disabled' until the
user enables it). requirements.txt is shown, never installed. No package
code is ever imported or executed.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import httpx
from sqlalchemy import select

from .. import __version__
from ..config import BACKEND_DIR, get_settings
from ..models import Destination, ModelPackage, Run
from ..runtime.contract import PackageError, validate_package
from ..runtime.loader import load_model
from ..util import new_id

BUNDLED_DIR = BACKEND_DIR / 'model_packages'
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_UNZIPPED = 300 * 1024 * 1024


def pkg_dict(p: ModelPackage) -> dict:
    meta = p.metadata_json or {}
    req = ''
    rp = Path(p.package_path) / 'requirements.txt'
    if rp.exists():
        req = rp.read_text(encoding='utf-8', errors='replace')[:4000]
    return {'id': p.id, 'version': p.version, 'name': p.name, 'task': p.task, 'description': p.description,
            'framework': p.framework, 'source_repo': p.source_repo, 'source_ref': p.source_ref, 'license': p.license,
            'training_data': p.training_data, 'inputs': p.input_variables, 'outputs': p.output_variables,
            'status': p.status, 'is_demo': p.is_demo, 'evaluation': meta.get('evaluation', {}),
            'requirements_txt': req, 'installed_at': p.installed_at.isoformat() if p.installed_at else None}


def _register(db, src_dir: Path, source_repo: str | None, source_ref: str | None, status: str, is_demo: bool) -> ModelPackage:
    meta = validate_package(src_dir)
    dest = get_settings().store('models') / re.sub(r'[^A-Za-z0-9._-]', '_', meta['id']) / re.sub(r'[^A-Za-z0-9._-]', '_', meta['version'])
    if dest.resolve() != src_dir.resolve():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src_dir, dest)
    pkg = db.get(ModelPackage, (meta['id'], meta['version'])) or ModelPackage(id=meta['id'], version=meta['version'])
    pkg.name, pkg.task, pkg.description = meta['name'], meta['task'], meta['description']
    pkg.framework, pkg.license = meta['framework'], meta['license']
    pkg.source_repo = source_repo or meta['source_repo']
    pkg.source_ref = source_ref or meta.get('source_ref', '')
    pkg.training_data = meta.get('training_data', '')
    pkg.input_variables, pkg.output_variables = meta['schema']['inputs'], meta['schema']['outputs']
    pkg.package_path, pkg.metadata_json, pkg.status, pkg.is_demo = str(dest), meta, status, is_demo
    db.merge(pkg)
    db.commit()
    return db.get(ModelPackage, (meta['id'], meta['version']))


def register_bundled(db) -> None:
    if not BUNDLED_DIR.is_dir():
        return
    for d in sorted(BUNDLED_DIR.iterdir()):
        if not (d / 'metadata.json').exists():
            continue
        meta = json.loads((d / 'metadata.json').read_text(encoding='utf-8'))
        if db.get(ModelPackage, (meta.get('id'), meta.get('version'))) is None:
            _register(db, d, None, None, status='enabled', is_demo='demo' in meta.get('id', ''))


def parse_github_url(url: str) -> tuple[str, str, str | None, str]:
    """Return (owner, repo, ref or None, subdir)."""
    s = url.strip().removesuffix('/').removesuffix('.git')
    s = re.sub(r'^(https?://)?(www\.)?github\.com/', '', s)
    m = re.fullmatch(r'([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:/tree/([^/]+)(?:/(.+))?)?', s)
    if not m:
        raise PackageError('expected a GitHub URL like https://github.com/owner/repo[/tree/ref/subdir] or owner/repo')
    return m.group(1), m.group(2), m.group(3), m.group(4) or ''


def _safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    total = 0
    root = target.resolve()
    for info in zf.infolist():
        total += info.file_size
        if total > MAX_UNZIPPED:
            raise PackageError('archive too large when unpacked')
        dest = (target / info.filename).resolve()
        if not str(dest).startswith(str(root)):
            raise PackageError(f'unsafe path in archive: {info.filename}')
    zf.extractall(target)


def _find_package_root(base: Path, subdir: str) -> Path:
    tops = [p for p in base.iterdir() if p.is_dir()]
    if len(tops) == 1:
        base = tops[0]
    if subdir:
        cand = (base / subdir).resolve()
        if not str(cand).startswith(str(base.resolve())) or not cand.is_dir():
            raise PackageError(f'subdirectory not found in archive: {subdir}')
        return cand
    if (base / 'metadata.json').exists():
        return base
    for depth in range(1, 3):
        for p in base.glob('/'.join(['*'] * depth) + '/metadata.json'):
            return p.parent
    raise PackageError('no metadata.json found in the repository archive')


def install_from_github(db, url: str, ref: str | None = None, client: httpx.Client | None = None) -> ModelPackage:
    owner, repo, url_ref, subdir = parse_github_url(url)
    ref = ref or url_ref or 'main'
    api = f'https://api.github.com/repos/{owner}/{repo}/zipball/{ref}'
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': f'OpenDMO/{__version__}'}
    token = get_settings().github_token
    if token:
        headers['Authorization'] = f'Bearer {token}'
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        resp = client.get(api, headers=headers)
    except httpx.HTTPError as exc:
        raise PackageError(f'download failed (offline?): {exc}') from exc
    finally:
        if own:
            client.close()
    if resp.status_code != 200:
        raise PackageError(f'GitHub download failed: HTTP {resp.status_code}')
    if len(resp.content) > MAX_ZIP_BYTES:
        raise PackageError('archive larger than 100 MB')
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                _safe_extract(zf, Path(tmp))
        except zipfile.BadZipFile as exc:
            raise PackageError('downloaded file is not a zip archive') from exc
        root = _find_package_root(Path(tmp), subdir)
        return _register(db, root, f'https://github.com/{owner}/{repo}' + (f'/tree/{ref}/{subdir}' if subdir else ''),
                         ref, status='disabled', is_demo=False)


def _validate_model_inputs(specs: list[dict], inputs: dict) -> tuple[dict, list[str]]:
    clean, errors = {}, []
    for spec in specs:
        name = spec['name']
        if inputs.get(name) in (None, ''):
            if spec.get('required', True):
                errors.append(f'missing required input: {name}')
            continue
        try:
            val = float(inputs[name])
        except (TypeError, ValueError):
            errors.append(f'{name}: not numeric ({inputs[name]!r})')
            continue
        if spec.get('min') is not None and val < spec['min']:
            errors.append(f"{name}: below minimum {spec['min']}")
        if spec.get('max') is not None and val > spec['max']:
            errors.append(f"{name}: above maximum {spec['max']}")
        clean[name] = val
    return clean, errors


def run_model(db, model_id: str, version: str | None, destination_id: str | None, inputs: dict,
              dataset_id: str | None = None, label: str = '') -> Run:
    q = select(ModelPackage).where(ModelPackage.id == model_id)
    if version:
        q = q.where(ModelPackage.version == version)
    pkg = db.scalars(q.order_by(ModelPackage.installed_at.desc())).first()
    if not pkg:
        raise PackageError('model not found')
    if pkg.status != 'enabled':
        raise PackageError('model is disabled — enable it in the Control Board or Model Lab first')
    if destination_id and not db.get(Destination, destination_id):
        raise PackageError('destination not found')
    clean, errors = _validate_model_inputs(pkg.input_variables or [], inputs)
    snapshot = {'name': pkg.name, 'framework': pkg.framework, 'source_repo': pkg.source_repo, 'source_ref': pkg.source_ref,
                'license': pkg.license, 'training_data': pkg.training_data, 'description': pkg.description,
                'formula': f'{pkg.framework} artifact {pkg.metadata_json.get("_artifact")}', 'screening': False,
                'references': [], 'evaluation': (pkg.metadata_json or {}).get('evaluation', {})}
    run = Run(id=new_id('RUN'), kind='model', method_id=f'model:{pkg.id}', method_version=pkg.version,
              destination_id=destination_id, dataset_id=dataset_id, inputs=clean, parameters={},
              software_version=__version__, method_snapshot=snapshot, label=label, is_demo=pkg.is_demo, outputs={})
    if errors:
        run.status, run.error = 'failed', '; '.join(errors)
    else:
        try:
            model = load_model(pkg.package_path, pkg.framework, pkg.metadata_json.get('_artifact', ''),
                               allow_pickle=get_settings().allow_pickle_models)
            raw = model.predict(clean)
            units = {o['name']: o.get('unit', '') for o in pkg.output_variables or []}
            run.outputs = {k: {'value': v, 'unit': units.get(k, '')} for k, v in raw.items()}
            run.status = 'success'
        except Exception as exc:
            run.status, run.error = 'failed', str(exc)
    db.add(run)
    db.commit()
    return run
