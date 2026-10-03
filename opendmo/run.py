#!/usr/bin/env python3
"""OpenDMO launcher — the only thing an end user runs.

    python run.py                 # first run: creates .venv, installs pinned deps, starts, opens browser
    python run.py --no-browser    # server only
    python run.py --port 8123     # preferred port (the next free one is used if busy)
    python run.py --install-only  # prepare .venv and exit
    python run.py --smoke         # start, check /api/health, stop (used by CI)

Standard library only until the virtual environment exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

MIN_PY = (3, 11)
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'backend'
VENV = ROOT / '.venv'
REQS = BACKEND / 'requirements.txt'
STAMP = VENV / '.opendmo-requirements.sha256'
SETTINGS = ROOT / 'opendmo.settings.json'


def say(msg: str) -> None:
    print(f'[OpenDMO] {msg}', flush=True)


def fail(msg: str, code: int = 1) -> None:
    print(f'\n[OpenDMO] ERROR: {msg}\n', file=sys.stderr, flush=True)
    sys.exit(code)


def venv_python() -> Path:
    return VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def in_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def ensure_venv() -> None:
    py = venv_python()
    if not py.exists():
        say(f'First run: creating a private Python environment in {VENV} …')
        import venv
        try:
            venv.EnvBuilder(with_pip=True, clear=True).create(VENV)
        except Exception as exc:  # noqa: BLE001
            fail(f'could not create the virtual environment ({exc}).\n'
                 '  Linux: install the venv module, e.g. "sudo apt install python3-venv", then retry.')
    digest = hashlib.sha256(REQS.read_bytes()).hexdigest()
    if STAMP.exists() and STAMP.read_text().strip() == digest:
        return
    say('Installing pinned dependencies (one time, ~1 minute) …')
    wheels = ROOT / 'wheels'
    cmd = [str(py), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(REQS)]
    if wheels.is_dir():
        cmd[4:4] = ['--no-index', '--find-links', str(wheels)]
        say('Using bundled wheels (offline install).')
    if subprocess.call(cmd) != 0:
        fail('dependency installation failed. Check your internet connection (needed once) '
             'or place wheels in a "wheels" folder next to run.py, then run again.')
    STAMP.write_text(digest)


def free_port(preferred: int, host: str) -> int:
    for port in list(range(preferred, preferred + 30)) + [0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return s.getsockname()[1]
            except OSError:
                continue
    fail('no free TCP port found')
    return 0


LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never route localhost via a proxy


def wait_health(url: str, timeout: float = 60) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with LOCAL.open(f'{url}/api/health', timeout=2) as r:
                if json.loads(r.read()).get('status') == 'ok':
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    return False


def serve(args) -> None:
    launcher = {}
    if SETTINGS.exists():
        try:
            launcher = json.loads(SETTINGS.read_text(encoding='utf-8'))
        except ValueError:
            say('opendmo.settings.json is not valid JSON — ignoring it')
    data_dir = args.data_dir or os.environ.get('OPENDMO_DATA_DIR') or launcher.get('data_dir')
    if data_dir:
        os.environ['OPENDMO_DATA_DIR'] = str(Path(data_dir).expanduser())
    port = free_port(args.port or int(launcher.get('port', 8000)), args.host)
    os.environ['OPENDMO_PORT'] = str(port)
    url = f'http://{"127.0.0.1" if args.host in ("0.0.0.0", "127.0.0.1") else args.host}:{port}'
    sys.path.insert(0, str(BACKEND))
    import uvicorn  # noqa: E402  (available inside the venv)

    config = uvicorn.Config('app.main:app', host=args.host, port=port, log_level='warning')
    server = uvicorn.Server(config)

    def announce():
        if not wait_health(url):
            say('server did not become healthy within 60 s — see messages above')
            return
        say(f'OpenDMO is running at {url}   (press Ctrl+C to stop)')
        say(f'Data directory: {os.environ.get("OPENDMO_DATA_DIR") or ROOT / "data"}')
        if args.smoke:
            say('smoke test passed')
            server.should_exit = True
        elif not args.no_browser:
            webbrowser.open(url)

    threading.Thread(target=announce, daemon=True).start()
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    say('stopped.')


def main() -> None:
    if sys.version_info < MIN_PY:
        fail(f'OpenDMO needs Python {MIN_PY[0]}.{MIN_PY[1]} or newer; this is {sys.version.split()[0]}.\n'
             '  Download it from https://www.python.org/downloads/ and run the launcher again.')
    p = argparse.ArgumentParser(description='Start OpenDMO')
    p.add_argument('--port', type=int, default=None)
    p.add_argument('--host', default='127.0.0.1', help='use 0.0.0.0 only on a trusted network')
    p.add_argument('--data-dir', default=None)
    p.add_argument('--no-browser', action='store_true')
    p.add_argument('--install-only', action='store_true')
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--no-venv', action='store_true', help='use the current interpreter (developers / CI)')
    args = p.parse_args()
    if not BACKEND.is_dir():
        fail(f'backend folder not found next to run.py ({BACKEND}). Re-extract the release ZIP.')
    if not args.no_venv and not in_venv():
        ensure_venv()
        if args.install_only:
            say('environment ready.')
            return
        argv = [str(venv_python()), str(Path(__file__).resolve()), *sys.argv[1:]]
        if os.name != 'nt':
            os.execv(argv[0], argv)  # replace this process so Ctrl+C / kill reach the server directly
        sys.exit(subprocess.call(argv))
    if args.install_only:
        return
    serve(args)


if __name__ == '__main__':
    main()
