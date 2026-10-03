"""Database layer — SQLite by default (zero config), PostgreSQL+PostGIS optional.

The engine is created lazily so tests and the Control Board (reset/restore)
can rebuild it against a different data directory.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_Session: sessionmaker | None = None


def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute('PRAGMA foreign_keys=ON')
    cur.execute('PRAGMA journal_mode=WAL')
    cur.close()


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        url = get_settings().db_url
        kwargs: dict = {'future': True}
        if url.startswith('sqlite'):
            kwargs['connect_args'] = {'check_same_thread': False}
        _engine = create_engine(url, **kwargs)
        if url.startswith('sqlite'):
            event.listen(_engine, 'connect', _sqlite_pragmas)
        _Session = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def SessionLocal() -> Session:
    get_engine()
    assert _Session is not None
    return _Session()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    from . import models  # noqa: F401  (register mappers)
    Base.metadata.create_all(get_engine())
