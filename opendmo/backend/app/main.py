"""OpenDMO v2 — single-process runtime.

FastAPI serves the JSON API under /api and the pre-built static frontend
(Next.js `output: 'export'`) from app/static. End users need only Python.

    python run.py                          # launcher (venv, deps, free port, browser)
    uvicorn app.main:app --port 8000       # developers
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings
from .db import SessionLocal, create_all
from .routers import analysis, core, data, registry, system
from .runtime.contract import PackageError
from .seed import packs
from .services.csv_import import ImportError_
from .services.datasets import DatasetError
from .services.models import register_bundled
from .services.runs import RunError

log = logging.getLogger('opendmo')


def bootstrap() -> None:
    """Idempotent: schema, pilot destinations, bundled (DEMO) model package."""
    create_all()
    db = SessionLocal()
    try:
        packs.ensure_pilots(db)
        register_bundled(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    yield


app = FastAPI(
    title='OpenDMO API', version=__version__, lifespan=lifespan,
    description='Open Destination Management & Analytics Platform — local-first research API. '
                'All data stays on this machine unless you export it.',
    docs_url=None, redoc_url=None, openapi_url='/api/openapi.json',
)

app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(',') if o.strip()],
                   allow_methods=['*'], allow_headers=['*'])


@app.middleware('http')
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    # Local-first: the UI may only talk to this origin; no remote scripts, fonts, tiles or telemetry.
    resp.headers.setdefault('Content-Security-Policy',
                            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('Referrer-Policy', 'no-referrer')
    return resp


for exc_type in (DatasetError, ImportError_, RunError, PackageError):
    @app.exception_handler(exc_type)
    async def _domain_error(request: Request, exc: Exception):  # noqa: ANN001
        return JSONResponse(status_code=422, content={'detail': str(exc)})


for r in (core.router, data.router, analysis.router, registry.router, system.router):
    app.include_router(r, prefix='/api')


@app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], include_in_schema=False)
async def api_not_found(path: str):
    return JSONResponse(status_code=404, content={'detail': f'unknown API route: /api/{path}'})


static_dir = Path(get_settings().static_dir)
if (static_dir / 'index.html').exists():
    app.mount('/', StaticFiles(directory=static_dir, html=True), name='frontend')
else:
    @app.get('/', include_in_schema=False)
    async def no_frontend():
        return HTMLResponse('<!doctype html><meta charset="utf-8"><title>OpenDMO API</title>'
                            '<body style="font-family:monospace;background:#0E0E10;color:#F4ECDD;padding:32px">'
                            f'<h1 style="color:#D8343F">OpenDMO {__version__} — API running</h1>'
                            '<p>The built frontend was not found in backend/app/static.</p>'
                            '<p>Developers: <code>python scripts/build_release.py --frontend-only</code> or run '
                            '<code>npm run dev</code> in frontend/. OpenAPI schema: <a style="color:#F4ECDD" href="/api/openapi.json">/api/openapi.json</a></p>')
