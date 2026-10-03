"""Audit log for administrative actions (Control Board)."""
from __future__ import annotations

from ..models import AuditLog


def log(db, action: str, target: str = '', **detail) -> None:
    db.add(AuditLog(action=action, target=target, detail=detail))
    db.commit()
