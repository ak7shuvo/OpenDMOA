"""Visitor-demand forecasting — pure Python/numpy, no statistical packages.

Methods
-------
* seasonal naive  ŷ_{n+k} = y_{n+k−m(⌊(k−1)/m⌋+1)}
* linear trend    OLS on t = 0..n−1 with a prediction interval
* Holt-Winters    additive trend + additive seasonality; smoothing parameters
                  either fixed by the user or chosen by grid search on
                  in-sample one-step SSE.

Every forecast is accompanied by a hold-out backtest (MAE, RMSE, MAPE, MASE).
"""
from __future__ import annotations

import itertools
import math

import numpy as np

Z95 = 1.959964


class ForecastError(ValueError):
    pass


def _arr(y) -> np.ndarray:
    a = np.asarray([float(v) for v in y], dtype=float)
    if a.size == 0:
        raise ForecastError('series is empty')
    if not np.all(np.isfinite(a)):
        raise ForecastError('series contains missing or non-finite values; fill or drop them first')
    return a


# --------------------------------------------------------------------------- seasonal naive

def seasonal_naive(y, h: int, m: int) -> dict:
    a = _arr(y)
    n = a.size
    if m < 1:
        raise ForecastError('season length must be >= 1')
    if n < m:
        raise ForecastError(f'seasonal naive needs at least one full season ({m} points), got {n}')
    fc = np.array([a[n - m + (k % m)] for k in range(h)])
    resid = a[m:] - a[:-m] if n > m else np.array([0.0])
    sigma = float(np.sqrt(np.mean(resid ** 2))) if resid.size else 0.0
    width = np.array([Z95 * sigma * math.sqrt(k // m + 1) for k in range(h)])
    return {'forecast': fc, 'lo': fc - width, 'hi': fc + width, 'fitted_params': {'season_length': m}, 'sigma': sigma}


# --------------------------------------------------------------------------- linear trend

def linear_trend(y, h: int) -> dict:
    a = _arr(y)
    n = a.size
    if n < 3:
        raise ForecastError('linear trend needs at least 3 points')
    t = np.arange(n, dtype=float)
    tbar, ybar = t.mean(), a.mean()
    sxx = float(np.sum((t - tbar) ** 2))
    slope = float(np.sum((t - tbar) * (a - ybar)) / sxx)
    intercept = ybar - slope * tbar
    resid = a - (intercept + slope * t)
    sigma = float(np.sqrt(np.sum(resid ** 2) / (n - 2))) if n > 2 else 0.0
    tf = np.arange(n, n + h, dtype=float)
    fc = intercept + slope * tf
    width = Z95 * sigma * np.sqrt(1 + 1 / n + (tf - tbar) ** 2 / sxx)
    ss_tot = float(np.sum((a - ybar) ** 2))
    r2 = 1 - float(np.sum(resid ** 2)) / ss_tot if ss_tot > 0 else 1.0
    return {'forecast': fc, 'lo': fc - width, 'hi': fc + width,
            'fitted_params': {'intercept': round(intercept, 6), 'slope_per_period': round(slope, 6), 'r2': round(r2, 6)},
            'sigma': sigma}


# --------------------------------------------------------------------------- Holt-Winters (additive)

def _hw_init(a: np.ndarray, m: int):
    first, second = a[:m].mean(), a[m:2 * m].mean()
    trend = (second - first) / m
    level = first + trend * (m - 1) / 2                     # level at t = m−1
    seasonals = [a[i] - (first + trend * (i - (m - 1) / 2)) for i in range(m)]
    return level, trend, seasonals


def _hw_run(a: np.ndarray, m: int, alpha: float, beta: float, gamma: float):
    level, trend, s = _hw_init(a, m)
    s = list(s)
    sse = 0.0
    resid = []
    for t in range(m, a.size):
        season = s[t - m]
        pred = level + trend + season
        err = a[t] - pred
        sse += err * err
        resid.append(err)
        new_level = alpha * (a[t] - season) + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        s.append(gamma * (a[t] - new_level) + (1 - gamma) * season)
        level = new_level
    return level, trend, s, sse, np.asarray(resid)


GRID = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def holt_winters(y, h: int, m: int, alpha: float | None = None, beta: float | None = None,
                 gamma: float | None = None) -> dict:
    a = _arr(y)
    n = a.size
    if m < 2:
        raise ForecastError('Holt-Winters needs a season length >= 2')
    if n < 2 * m:
        raise ForecastError(f'Holt-Winters needs at least two full seasons ({2 * m} points), got {n}')
    for name, val in (('alpha', alpha), ('beta', beta), ('gamma', gamma)):
        if val is not None and not 0 <= val <= 1:
            raise ForecastError(f'{name} must be within [0, 1]')
    grid_a = (alpha,) if alpha is not None else GRID
    grid_b = (beta,) if beta is not None else GRID
    grid_g = (gamma,) if gamma is not None else GRID
    best = None
    for al, be, ga in itertools.product(grid_a, grid_b, grid_g):
        res = _hw_run(a, m, al, be, ga)
        if best is None or res[3] < best[1][3] - 1e-12:
            best = ((al, be, ga), res)
    assert best is not None
    (al, be, ga), (level, trend, s, sse, resid) = best
    fc = np.array([level + k * trend + s[n - m + ((k - 1) % m)] for k in range(1, h + 1)])
    sigma = float(np.sqrt(np.mean(resid ** 2))) if resid.size else 0.0
    # Additive HW interval: σ_h² = σ²[1 + Σ_{j<h} c_j²], c_j = α(1 + jβ) + γ(1 − α)·1{j mod m = 0}
    # (Hyndman & Athanasopoulos, 2021, §9.8 / Table 9.8, component-form parameters).
    width = []
    for k in range(1, h + 1):
        var = 1 + sum((al * (1 + j * be) + (ga * (1 - al) if j % m == 0 else 0)) ** 2 for j in range(1, k))
        width.append(Z95 * sigma * math.sqrt(var))
    width_a = np.array(width)
    optimised = [p for p, v in (('alpha', alpha), ('beta', beta), ('gamma', gamma)) if v is None]
    return {'forecast': fc, 'lo': fc - width_a, 'hi': fc + width_a,
            'fitted_params': {'alpha': al, 'beta': be, 'gamma': ga, 'season_length': m,
                              'optimised': optimised, 'in_sample_sse': round(float(sse), 6)},
            'sigma': sigma}


# --------------------------------------------------------------------------- accuracy & backtest

def accuracy(actual, predicted, train=None, m: int = 1) -> dict:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    err = a - p
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    nz = a != 0
    mape = float(np.mean(np.abs(err[nz] / a[nz])) * 100) if nz.any() else None
    mase = None
    if train is not None:
        tr = np.asarray(train, dtype=float)
        lag = m if tr.size > m else 1
        if tr.size > lag:
            scale = float(np.mean(np.abs(tr[lag:] - tr[:-lag])))
            mase = mae / scale if scale > 0 else None
    rnd = lambda x: None if x is None else round(x, 6)  # noqa: E731
    return {'mae': rnd(mae), 'rmse': rnd(rmse), 'mape_pct': rnd(mape), 'mase': rnd(mase), 'n': int(a.size)}


def run_method(method: str, y, h: int, m: int, params: dict) -> dict:
    if method == 'seasonal_naive':
        return seasonal_naive(y, h, m)
    if method == 'linear_trend':
        return linear_trend(y, h)
    if method == 'holt_winters':
        return holt_winters(y, h, m, params.get('alpha'), params.get('beta'), params.get('gamma'))
    raise ForecastError(f'unknown forecasting method: {method}')


def backtest(method: str, y, holdout: int, m: int, params: dict) -> dict:
    a = _arr(y)
    if holdout < 1 or holdout >= a.size:
        raise ForecastError('holdout must be between 1 and len(series) − 1')
    train, test = a[:-holdout], a[-holdout:]
    res = run_method(method, train, holdout, m, params)
    metrics = accuracy(test, res['forecast'], train, m)
    metrics['holdout'] = holdout
    metrics['predicted'] = [round(float(x), 4) for x in res['forecast']]
    metrics['actual'] = [round(float(x), 4) for x in test]
    return metrics
