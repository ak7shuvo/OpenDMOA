#!/usr/bin/env python3
"""Boot smoke test: start the server via run.py, hit /api/health and the static UI, stop.

    python scripts/smoke_test.py            # uses run.py (creates .venv on first run)
    python scripts/smoke_test.py --no-venv  # current interpreter (deps already installed)
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(url: str):
    with LOCAL.open(url, timeout=5) as r:
        return r.status, r.headers.get('content-type', ''), r.read()


def main() -> int:
    port = free_port()
    data = tempfile.mkdtemp(prefix='opendmo-smoke-')
    cmd = [sys.executable, str(ROOT / 'run.py'), '--no-browser', '--port', str(port), '--data-dir', data, *sys.argv[1:]]
    proc = subprocess.Popen(cmd, cwd=ROOT, env={**os.environ, 'PYTHONUNBUFFERED': '1'})
    base = f'http://127.0.0.1:{port}'
    try:
        deadline = time.time() + 300
        while time.time() < deadline:
            if proc.poll() is not None:
                print(f'server exited early with code {proc.returncode}')
                return 1
            try:
                status, _, body = get(f'{base}/api/health')
                if status == 200 and json.loads(body)['status'] == 'ok':
                    break
            except Exception:
                time.sleep(1)
        else:
            print('timed out waiting for /api/health')
            return 1
        print('health:', body.decode())
        checks = [('/api/meta', 'application/json'), ('/api/destinations', 'application/json'), ('/api/methods', 'application/json')]
        static = (ROOT / 'backend' / 'app' / 'static' / 'index.html').exists()
        if static:
            checks += [('/', 'text/html'), ('/observatory/', 'text/html'), ('/system/control-board/', 'text/html')]
        for path, ctype in checks:
            status, got, body = get(base + path)
            assert status == 200 and got.startswith(ctype), f'{path}: {status} {got}'
            if ctype == 'text/html':
                assert b'OpenDMO' in body, f'{path}: page does not look like OpenDMO'
            print(f'ok {path}')
        req = urllib.request.Request(f'{base}/api/system/seed-packs/jaflong/load', method='POST')
        with LOCAL.open(req, timeout=30) as r:
            assert json.loads(r.read())['status'] == 'loaded'
        print('ok seed pack load')
        print('SMOKE TEST PASSED' + ('' if static else ' (API only — static frontend not built)'))
        return 0
    finally:
        if os.name == 'nt':  # run.py spawns the venv interpreter as a child on Windows
            subprocess.call(['taskkill', '/T', '/F', '/PID', str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    sys.exit(main())
