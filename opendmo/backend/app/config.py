"""Central configuration — local-first, zero-config defaults.

Resolution order for every setting: environment variable (OPENDMO_*) >
built-in default. The data directory holds the SQLite database, model store,
upload archive and backups. It defaults to ``<product root>/data`` so a
release ZIP is fully self-contained.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PRODUCT_ROOT = BACKEND_DIR.parent
STATIC_DIR = Path(__file__).resolve().parent / 'static'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='OPENDMO_', env_file='.env', extra='ignore')

    data_dir: str = str(PRODUCT_ROOT / 'data')
    database_url: str = ''            # empty -> sqlite file inside data_dir
    host: str = '127.0.0.1'
    port: int = 8000
    allow_pickle_models: bool = False
    github_token: str | None = None
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    static_dir: str = str(STATIC_DIR)

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_path / 'opendmo.db').as_posix()}"

    @property
    def db_engine(self) -> str:
        return 'postgresql' if self.db_url.startswith('postgresql') else 'sqlite'

    @property
    def db_file(self) -> str | None:
        if self.db_engine == 'sqlite':
            return self.db_url.removeprefix('sqlite:///')
        return None

    def store(self, name: str) -> Path:
        p = self.data_path / name
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()


def env_flag(name: str) -> bool:
    return os.environ.get(name, '').lower() in {'1', 'true', 'yes'}
