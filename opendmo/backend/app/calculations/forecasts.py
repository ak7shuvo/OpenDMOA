"""Forecast methods registered alongside calculations (kind = 'forecast')."""
from __future__ import annotations

from ..forecasting.core import ForecastError, backtest, run_method
from ..periods import next_periods, season_length_for
from .base import CalculationError, KnownCase, Method, Output, Param
from .references import FPP3, HOLT_2004, HYNDMAN_KOEHLER_2006, WINTERS_1960

COMMON_PARAMS = (
    Param('series', 'Observed series', '', 'Ordered list of {period, value}; resolved from a dataset variable', type='series'),
    Param('horizon', 'Forecast horizon', 'periods', type='int', default=12, min=1, max=60),
    Param('season_length', 'Season length (blank = infer from period type)', 'periods', type='int', required=False, min=1, max=366),
    Param('holdout', 'Back-test hold-out', 'periods', type='int', required=False, min=1, max=60,
          description='Defaults to min(horizon, n/4)'),
)
OUTPUTS = (
    Output('forecast', 'Forecast with 95 % interval', '', '[{period, value, lo, hi}]'),
    Output('backtest', 'Hold-out accuracy', '', 'MAE, RMSE, MAPE %, MASE'),
    Output('fitted_params', 'Fitted parameters'),
)


def _make(method_key: str):
    def compute(v: dict) -> dict:
        series = v.get('series') or []
        if not isinstance(series, list) or len(series) < 3:
            raise CalculationError('series must contain at least 3 observations')
        try:
            periods = [str(p['period']) for p in series]
            values = [float(p['value']) for p in series]
        except (KeyError, TypeError, ValueError) as exc:
            raise CalculationError('series items need numeric {period, value}') from exc
        h = int(v.get('horizon') or 12)
        m = int(v.get('season_length') or season_length_for(periods[-1]))
        params = {k: (None if v.get(k) in (None, '') else float(v[k])) for k in ('alpha', 'beta', 'gamma')}
        holdout = int(v.get('holdout') or max(1, min(h, len(values) // 4)))
        try:
            res = run_method(method_key, values, h, m, params)
            bt = backtest(method_key, values, holdout, m, params)
        except ForecastError as exc:
            raise CalculationError(str(exc)) from exc
        fut = next_periods(periods[-1], h)
        fc = [{'period': p, 'value': round(float(x), 4), 'lo': round(float(lo), 4), 'hi': round(float(hi), 4)}
              for p, x, lo, hi in zip(fut, res['forecast'], res['lo'], res['hi'])]
        return {'forecast': fc, 'backtest': bt, 'fitted_params': res['fitted_params'],
                'season_length': m, 'n_observations': len(values),
                'next_period_value': fc[0]['value'] if fc else None}
    return compute


seasonal_naive = Method(
    id='forecast.seasonal_naive', version='1.0.0', name='Seasonal Naïve Forecast', category='forecast', core='economy',
    kind='forecast', summary='Each future period repeats the value observed one season earlier. The benchmark every other model must beat.',
    inputs=COMMON_PARAMS, outputs=OUTPUTS,
    formula='ŷ_{T+h} = y_{T+h−m(k+1)},  k = ⌊(h−1)/m⌋\n95 % PI: ŷ ± 1.96·σ·√(k+1)',
    method='Benchmark method (Hyndman & Athanasopoulos, 2021, §5.2). σ estimated from seasonal differences.',
    references=(FPP3, HYNDMAN_KOEHLER_2006), compute=_make('seasonal_naive'),
    limitations=('Ignores trend; needs at least one full season.',),
    known_cases=(KnownCase({'series': [{'period': f'2024-{i:02d}', 'value': v} for i, v in enumerate([1, 2, 3, 4, 1, 2, 3, 4], 1)],
                            'horizon': 4, 'season_length': 4, 'holdout': 4},
                           {'next_period_value': 1}),),
)

linear = Method(
    id='forecast.linear_trend', version='1.0.0', name='Linear Trend Forecast', category='forecast', core='economy',
    kind='forecast', summary='Ordinary least squares straight-line trend extrapolated forward with a prediction interval.',
    inputs=COMMON_PARAMS, outputs=OUTPUTS,
    formula='y_t = a + b·t + ε,  b = Σ(t−t̄)(y−ȳ)/Σ(t−t̄)²\n95 % PI: ŷ ± 1.96·s·√(1 + 1/n + (t₀−t̄)²/Sxx)',
    method='Classical OLS trend (Hyndman & Athanasopoulos, 2021, §7). No seasonality term.',
    references=(FPP3, HYNDMAN_KOEHLER_2006), compute=_make('linear_trend'),
    limitations=('Assumes a constant linear trend; seasonality is left in the residuals.',),
    known_cases=(KnownCase({'series': [{'period': str(2020 + i), 'value': v} for i, v in enumerate([1, 2, 3, 4, 5])],
                            'horizon': 2, 'holdout': 1}, {'next_period_value': 6}),),
)

holt_winters = Method(
    id='forecast.holt_winters', version='1.0.0', name='Holt-Winters Additive Forecast', category='forecast', core='economy',
    kind='forecast', summary='Triple exponential smoothing with additive trend and seasonality; smoothing parameters fixed or grid-searched.',
    inputs=COMMON_PARAMS + (
        Param('alpha', 'α level smoothing (blank = optimise)', '', type='float', required=False, min=0, max=1),
        Param('beta', 'β trend smoothing (blank = optimise)', '', type='float', required=False, min=0, max=1),
        Param('gamma', 'γ seasonal smoothing (blank = optimise)', '', type='float', required=False, min=0, max=1)),
    outputs=OUTPUTS,
    formula='ℓ_t = α(y_t − s_{t−m}) + (1−α)(ℓ_{t−1} + b_{t−1})\n'
            'b_t = β(ℓ_t − ℓ_{t−1}) + (1−β)b_{t−1}\n'
            's_t = γ(y_t − ℓ_t) + (1−γ)s_{t−m}\n'
            'ŷ_{t+h} = ℓ_t + h·b_t + s_{t+h−m(k+1)}',
    method='Winters (1960) / Holt (2004). Initial level, trend and seasonal indices from the first two seasons '
           '(centred, detrended). Unspecified parameters are chosen from {0.05, 0.1, …, 0.9} minimising in-sample one-step SSE.',
    references=(WINTERS_1960, HOLT_2004, FPP3, HYNDMAN_KOEHLER_2006), compute=_make('holt_winters'),
    limitations=('Needs at least two full seasons.', 'Grid search is coarse (0.05–0.9).',
                 'Prediction interval uses the analytic additive-HW approximation.'),
    known_cases=(KnownCase({'series': [{'period': f'{2020 + (i // 4)}-Q{i % 4 + 1}', 'value': i + [1, -1, 2, -2][i % 4]} for i in range(12)],
                            'horizon': 4, 'season_length': 4, 'holdout': 4, 'alpha': 0.5, 'beta': 0.3, 'gamma': 0.2},
                           {'next_period_value': 13}, note='Perfect linear + seasonal series is reproduced exactly'),),
)

METHODS = [seasonal_naive, linear, holt_winters]
