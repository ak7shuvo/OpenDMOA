"""Small shared helpers."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_json(obj) -> str:
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=str).encode())


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return s[:max_len].strip('-') or 'item'


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def norm_col(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', str(name).strip().lower()).strip('_')
