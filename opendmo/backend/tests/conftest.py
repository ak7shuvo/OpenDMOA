import os
import tempfile
from pathlib import Path

import pytest

# Isolate every test session in a temporary data directory BEFORE the app is imported.
_SESSION_DIR = tempfile.mkdtemp(prefix='opendmo-test-')
os.environ['OPENDMO_DATA_DIR'] = _SESSION_DIR


def _fresh(tmp: Path):
    from app.config import reset_settings_cache
    from app.db import reset_engine
    os.environ['OPENDMO_DATA_DIR'] = str(tmp)
    reset_settings_cache()
    reset_engine()


@pytest.fixture()
def db(tmp_path):
    _fresh(tmp_path)
    from app.main import bootstrap
    from app.db import SessionLocal
    bootstrap()
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    _fresh(tmp_path)
    import app.services.system as sysmod
    monkeypatch.setattr(sysmod, 'LAUNCHER_FILE', tmp_path / 'opendmo.settings.json')
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def demo_client(client):
    assert client.post('/api/system/seed-packs/jaflong/load').status_code == 200
    return client
