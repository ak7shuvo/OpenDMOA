"""Model package contract — validation only; package code is NEVER executed.

    model-package/
    ├── model/            artifact file (e.g. model.json)
    ├── metadata.json     id, name, version, task, framework, description, source_repo, license, …
    ├── schema.json       inputs[] / outputs[]: name, type, unit, min, max, required
    ├── requirements.txt  declared deps — informational, NEVER auto-installed
    └── README.md

Whitelisted frameworks: 'json-linear' (pure JSON weights). 'sklearn-joblib'
is recognised but refused unless OPENDMO_ALLOW_PICKLE_MODELS=true, because
unpickling is arbitrary code execution.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FILES = ['metadata.json', 'schema.json', 'requirements.txt', 'README.md']
ALLOWED_FRAMEWORKS = {'json-linear', 'sklearn-joblib'}
FORBIDDEN_SUFFIXES = {'.py', '.pyc', '.so', '.dll', '.exe', '.sh', '.bat', '.cmd', '.ps1', '.dylib'}


class PackageError(ValueError):
    pass


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise PackageError(f'invalid JSON in {path.name}: {exc}') from exc


def validate_package(pkg_dir: str | Path) -> dict:
    root = Path(pkg_dir)
    if not root.is_dir():
        raise PackageError(f'not a directory: {root}')
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            raise PackageError(f'missing required file: {name}')
    meta = _load_json(root / 'metadata.json')
    schema = _load_json(root / 'schema.json')
    for f in ['id', 'name', 'version', 'task', 'framework', 'description', 'source_repo', 'license']:
        if not meta.get(f):
            raise PackageError(f'metadata.json missing field: {f}')
    if meta['framework'] not in ALLOWED_FRAMEWORKS:
        raise PackageError(f"framework '{meta['framework']}' not in allowed list {sorted(ALLOWED_FRAMEWORKS)}")
    if not schema.get('inputs') or not schema.get('outputs'):
        raise PackageError('schema.json must define inputs[] and outputs[]')
    for var in schema['inputs'] + schema['outputs']:
        for f in ['name', 'type']:
            if f not in var:
                raise PackageError(f'schema variable missing {f}: {var}')
    model_dir = root / 'model'
    artifacts = sorted(p for p in model_dir.glob('*') if p.is_file()) if model_dir.is_dir() else []
    if not artifacts:
        raise PackageError('model/ directory has no artifact')
    executable = [p.name for p in model_dir.rglob('*') if p.suffix.lower() in FORBIDDEN_SUFFIXES]
    if executable:
        raise PackageError(f'model/ must contain data artifacts only; found executable files: {executable}')
    meta['_artifact'] = artifacts[0].name
    meta['schema'] = schema
    return meta
