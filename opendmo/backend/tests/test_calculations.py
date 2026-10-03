"""Every registered method must reproduce its documented known-value cases."""
import json
import math

import pytest

from app import calculations
from app.calculations.base import CalculationError
from app.services.runs import validate_inputs

CASES = [(m.id, i, k) for m in calculations.all_methods() for i, k in enumerate(m.known_cases)]


def _close(a, b, tol):
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        return isinstance(a, (int, float)) and math.isclose(a, b, rel_tol=1e-4, abs_tol=max(tol, 1e-3))
    return a == b


@pytest.mark.parametrize('method_id,idx,case', CASES, ids=[f'{c[0]}#{c[1]}' for c in CASES])
def test_known_cases(method_id, idx, case):
    m = calculations.get(method_id)
    out = m.compute(case.inputs)
    for key, expected in case.expected.items():
        assert _close(out.get(key), expected, case.tol), f'{method_id}.{key}: {out.get(key)} != {expected}'


def test_every_method_documented():
    for m in calculations.all_methods():
        d = m.describe()
        assert m.id and m.version.count('.') == 2
        assert m.formula and m.method and m.summary
        assert m.inputs and m.outputs
        assert m.known_cases, f'{m.id} has no verification case'
        assert m.core in ('observatory', 'climate', 'economy', 'lab')
        json.dumps(d)  # serialisable
        if m.screening:
            assert m.limitations, f'screening index {m.id} must declare limitations'
            assert 'not a certification' in d['label']
        assert '### ' in m.methodology_markdown()


def test_registry_ids_unique_and_complete():
    ids = [m.id for m in calculations.all_methods()]
    assert len(ids) == len(set(ids))
    for required in ['capacity.cifuentes', 'economy.leakage_impact', 'forecast.seasonal_naive', 'forecast.holt_winters',
                     'forecast.linear_trend', 'hazard.landslide_susceptibility', 'hazard.flood_susceptibility']:
        assert required in ids


def test_cifuentes_without_factors_and_observed():
    m = calculations.get('capacity.cifuentes')
    out = m.compute({'area_m2': 1000, 'area_per_visitor_m2': 2, 'open_hours': 6, 'visit_duration_h': 3,
                     'correction_factors': [], 'management_capacity_pct': 100})
    assert out['pcc'] == 1000 and out['rcc'] == 1000 and out['ecc'] == 1000
    assert 'utilisation_pct' not in out


@pytest.mark.parametrize('inputs,msg', [
    ({'area_m2': 0, 'area_per_visitor_m2': 1, 'open_hours': 8, 'visit_duration_h': 2, 'management_capacity_pct': 50}, '> 0'),
    ({'area_m2': 10, 'area_per_visitor_m2': 1, 'open_hours': 8, 'visit_duration_h': 2, 'management_capacity_pct': 150}, '0–100'),
    ({'area_m2': 10, 'area_per_visitor_m2': 1, 'open_hours': 8, 'visit_duration_h': 2, 'management_capacity_pct': 50,
      'correction_factors': [{'name': 'x', 'limiting': 5, 'total': 2}]}, 'limiting'),
])
def test_cifuentes_rejects_invalid(inputs, msg):
    with pytest.raises(CalculationError, match=msg):
        calculations.get('capacity.cifuentes').compute(inputs)


@pytest.mark.parametrize('method_id,inputs', [
    ('growth.rate', {'value_current': 5, 'value_previous': 0}),
    ('ratio.occupancy_rate', {'rooms_sold': 5, 'rooms_available': 0}),
    ('economy.leakage_impact', {'tourism_revenue': 0, 'imported_inputs': 0, 'repatriated_profits': 0, 'local_spend': 0,
                                'round2_local': 0, 'round3_local': 0}),
    ('growth.cagr', {'value_begin': 0, 'value_end': 5, 'years': 2}),
    ('sentiment.net_support', {'support_pct': 80, 'oppose_pct': 40}),
])
def test_undefined_results_raise(method_id, inputs):
    with pytest.raises(CalculationError):
        calculations.get(method_id).compute(inputs)


def test_leakage_index_bounds():
    m = calculations.get('economy.leakage_impact')
    best = m.compute({'tourism_revenue': 100, 'imported_inputs': 0, 'repatriated_profits': 0, 'local_spend': 100,
                      'round2_local': 100, 'round3_local': 100})
    worst = m.compute({'tourism_revenue': 100, 'imported_inputs': 100, 'repatriated_profits': 0, 'local_spend': 0,
                       'round2_local': 0, 'round3_local': 0})
    assert best['impact_index'] == 100 and best['status'] == 'ok'
    assert worst['impact_index'] == 0 and worst['status'] == 'risk'


def test_input_validation_ranges_and_defaults():
    m = calculations.get('capacity.cifuentes')
    clean, errors = validate_inputs(m, {'area_m2': 100, 'management_capacity_pct': 120})
    assert any('above the maximum' in e for e in errors)
    assert clean['open_hours'] == 8  # default applied
    _, errors = validate_inputs(calculations.get('growth.rate'), {'value_current': 'abc'})
    assert any('not a number' in e for e in errors) and any('missing required' in e for e in errors)


def test_projection_series_length():
    out = calculations.get('scenario.demand_projection').compute(
        {'base_visitors': 1000, 'growth_pct': 0, 'shock_pct': -50, 'years': 4, 'annual_capacity': 2000, 'base_year': 2026})
    assert [p['value'] for p in out['series']] == [500, 500, 500, 500]
    assert out['first_year_over_capacity'] == 'none' and out['status'] == 'ok'
