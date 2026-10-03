#!/usr/bin/env python3
"""Build the OpenDMO release ZIP.

    python scripts/build_release.py                 # build frontend, bundle, write release/opendmo-v2.0.zip
    python scripts/build_release.py --skip-frontend # reuse frontend/out
    python scripts/build_release.py --frontend-only # build frontend and copy it into backend/app/static

Steps: npm ci + next build (static export) -> copy frontend/out to backend/app/static ->
regenerate sample CSVs -> assemble a deterministic ZIP (fixed timestamps, sorted entries,
executable bits for the macOS/Linux launchers) -> write a SHA-256 checksum.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / 'frontend'
BACKEND = ROOT / 'backend'
STATIC = BACKEND / 'app' / 'static'
VERSION = '2.0'
PREFIX = f'opendmo-v{VERSION}'
FIXED_DATE = (2026, 10, 3, 0, 0, 0)

INCLUDE = [
    'run.py', 'start-windows.bat', 'start-mac.command', 'start-linux.sh', 'README.md', 'LICENSE', 'CITATION.cff',
    'CHANGELOG.md', 'CONTRACT.md', 'docker-compose.yml', 'docs', 'samples', 'database', 'backend',
]
EXCLUDE_PARTS = {'__pycache__', '.pytest_cache', 'data', 'node_modules', '.venv'}
EXCLUDE_SUFFIX = {'.pyc', '.db', '.db-wal', '.db-shm'}
EXECUTABLE = {'run.py', 'start-mac.command', 'start-linux.sh'}


def sh(cmd: list[str], cwd: Path) -> None:
    print('$', ' '.join(cmd), flush=True)
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'}
    if subprocess.call(cmd, cwd=cwd, env=env, shell=os.name == 'nt') != 0:
        sys.exit(f'command failed: {" ".join(cmd)}')


def build_frontend() -> None:
    if not (FRONTEND / 'node_modules').is_dir():
        sh(['npm', 'ci', '--no-audit', '--no-fund'], FRONTEND)
    sh(['npm', 'run', 'build'], FRONTEND)


def copy_static() -> None:
    out = FRONTEND / 'out'
    if not (out / 'index.html').exists():
        sys.exit('frontend/out is missing — run without --skip-frontend')
    if STATIC.exists():
        shutil.rmtree(STATIC)
    shutil.copytree(out, STATIC)
    print(f'copied static frontend -> {STATIC.relative_to(ROOT)}')


def files_to_zip() -> list[Path]:
    out = []
    for item in INCLUDE:
        p = ROOT / item
        if not p.exists():
            sys.exit(f'missing release input: {item}')
        candidates = [p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file())
        for f in candidates:
            rel = f.relative_to(ROOT)
            if EXCLUDE_PARTS & set(rel.parts) or f.suffix in EXCLUDE_SUFFIX:
                continue
            out.append(f)
    return sorted(out)


def write_zip(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files_to_zip():
            rel = f.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f'{PREFIX}/{rel}', date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if f.name in EXECUTABLE else 0o644
            info.external_attr = (0o100000 | mode) << 16
            data = f.read_bytes()
            if f.suffix in {'.sh', '.command'}:
                data = data.replace(b'\r\n', b'\n')
            z.writestr(info, data)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
    print(f'wrote {target} ({target.stat().st_size / 1e6:.2f} MB) sha256 {digest[:16]}…')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-frontend', action='store_true')
    ap.add_argument('--frontend-only', action='store_true')
    ap.add_argument('--out', default=str(ROOT / 'release' / f'{PREFIX}.zip'))
    a = ap.parse_args()
    if not a.skip_frontend:
        build_frontend()
    copy_static()
    if a.frontend_only:
        return
    sys.path.insert(0, str(BACKEND))
    from app.seed.samples import write_samples  # noqa: E402
    write_samples(ROOT / 'samples')
    write_zip(Path(a.out))


if __name__ == '__main__':
    main()
