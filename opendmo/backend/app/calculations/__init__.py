"""Method registry — the single source of truth for every calculation and forecast."""
from __future__ import annotations

from . import climate, economy, forecasts, observatory
from .base import CalculationError, Method

REGISTRY: dict[str, Method] = {}
for _m in [*observatory.METHODS, *climate.METHODS, *economy.METHODS, *forecasts.METHODS]:
    if _m.id in REGISTRY:
        raise RuntimeError(f'duplicate method id {_m.id}')
    REGISTRY[_m.id] = _m


def get(method_id: str) -> Method | None:
    return REGISTRY.get(method_id)


def all_methods() -> list[Method]:
    return list(REGISTRY.values())


__all__ = ['REGISTRY', 'Method', 'CalculationError', 'get', 'all_methods']
