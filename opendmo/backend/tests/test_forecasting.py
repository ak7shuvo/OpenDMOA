import math

import numpy as np
import pytest

from app.forecasting.core import ForecastError, accuracy, backtest, holt_winters, linear_trend, seasonal_naive


def test_seasonal_naive_repeats_last_season():
    res = seasonal_naive([1, 2, 3, 4, 5, 6, 7, 8], 6, 4)
    assert list(res['forecast']) == [5, 6, 7, 8, 5, 6]
    assert np.all(res['hi'] >= res['forecast'])


def test_linear_trend_exact_line():
    res = linear_trend([3, 5, 7, 9, 11], 3)
    assert np.allclose(res['forecast'], [13, 15, 17])
    assert res['fitted_params']['slope_per_period'] == pytest.approx(2)
    assert res['fitted_params']['r2'] == pytest.approx(1)


def test_holt_winters_reproduces_linear_seasonal_series():
    s = [1, -1, 2, -2]
    y = [t + s[t % 4] for t in range(16)]
    res = holt_winters(y, 8, 4, 0.3, 0.1, 0.2)
    expected = [t + s[t % 4] for t in range(16, 24)]
    assert np.allclose(res['forecast'], expected, atol=1e-9)


def test_holt_winters_grid_search_and_constant_series():
    res = holt_winters([10.0] * 24, 6, 12)
    assert np.allclose(res['forecast'], 10)
    assert set(res['fitted_params']['optimised']) == {'alpha', 'beta', 'gamma'}


def test_accuracy_known_values():
    m = accuracy([1, 2, 3], [2, 2, 2])
    assert m['mae'] == pytest.approx(2 / 3, abs=1e-6)
    assert m['rmse'] == pytest.approx(math.sqrt(2 / 3), abs=1e-6)
    assert m['mape_pct'] == pytest.approx((1 + 0 + 1 / 3) / 3 * 100, abs=1e-4)


def test_mase_uses_training_scale():
    m = accuracy([10, 12], [11, 11], train=[1, 2, 3, 4], m=1)
    assert m['mase'] == pytest.approx(1.0)


def test_backtest_holdout():
    y = [t + [1, -1, 2, -2][t % 4] for t in range(20)]
    bt = backtest('holt_winters', y, 4, 4, {'alpha': 0.5, 'beta': 0.2, 'gamma': 0.1})
    assert bt['holdout'] == 4 and bt['mae'] == pytest.approx(0, abs=1e-9)
    assert len(bt['predicted']) == 4


@pytest.mark.parametrize('fn,args', [
    (seasonal_naive, ([1, 2], 3, 4)),
    (holt_winters, ([1, 2, 3, 4, 5], 3, 4)),
    (linear_trend, ([1, 2], 3)),
])
def test_short_series_rejected(fn, args):
    with pytest.raises(ForecastError):
        fn(*args)


def test_non_finite_rejected():
    with pytest.raises(ForecastError):
        linear_trend([1, float('nan'), 3, 4], 2)
