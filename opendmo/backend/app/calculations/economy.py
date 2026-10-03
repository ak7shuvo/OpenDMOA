"""03 Future & Economy — revenue, leakage & local impact, scenario projections."""
from __future__ import annotations

from .base import CalculationError, KnownCase, Method, Output, Param, band, clamp, num, r, safe_div
from .references import ARCHER_FLETCHER_1996, OPENDMO, SACKS_2002, UNWTO_2004


def _leakage(v: dict) -> dict:
    rev = num(v, 'tourism_revenue')
    if rev <= 0:
        raise CalculationError('tourism revenue must be > 0')
    imported, repat = num(v, 'imported_inputs'), num(v, 'repatriated_profits')
    local, r2, r3 = num(v, 'local_spend'), num(v, 'round2_local'), num(v, 'round3_local')
    if min(imported, repat, local, r2, r3) < 0:
        raise CalculationError('monetary inputs must be >= 0')
    leakage = (imported + repat) / rev
    capture = local / rev
    lm3 = (rev + r2 + r3) / rev
    stii = 100 * (0.4 * clamp(1 - leakage) + 0.3 * clamp(capture) + 0.3 * clamp((lm3 - 1) / 2))
    return {'leakage_rate_pct': r(leakage * 100, 2), 'local_capture_pct': r(capture * 100, 2),
            'local_multiplier_lm3': r(lm3, 4), 'retained_bdt': r(rev - imported - repat, 2),
            'impact_index': r(stii, 2), 'status': band(stii, [(40, 'risk'), (60, 'watch')], 'ok')}


leakage = Method(
    id='economy.leakage_impact', version='1.0.0',
    name='Local Economic Leakage & Sustainable Tourism Impact Index', category='economy', core='economy',
    summary='Leakage rate, local capture, LM3 local multiplier and a composite Sustainable Tourism Impact Index (STII).',
    inputs=(Param('tourism_revenue', 'Tourism revenue (round 1 income)', 'BDT', min=0, source=('economy', 'tourism_revenue_bdt', 'sum')),
            Param('imported_inputs', 'Spend on imported goods & services', 'BDT', min=0, source=('economy', 'imported_inputs_bdt', 'sum')),
            Param('repatriated_profits', 'Profits leaving the destination', 'BDT', min=0, default=0, source=('economy', 'repatriated_profits_bdt', 'sum')),
            Param('local_spend', 'Spend captured by locally owned businesses', 'BDT', min=0, source=('economy', 'local_spend_bdt', 'sum')),
            Param('round2_local', 'LM3 round 2: re-spent locally by recipients', 'BDT', min=0, source=('economy', 'round2_local_bdt', 'sum')),
            Param('round3_local', 'LM3 round 3: re-spent locally again', 'BDT', min=0, source=('economy', 'round3_local_bdt', 'sum'))),
    outputs=(Output('leakage_rate_pct', 'Leakage rate', '%'), Output('local_capture_pct', 'Local capture', '%'),
             Output('local_multiplier_lm3', 'Local multiplier (LM3)', '×'), Output('retained_bdt', 'Retained revenue', 'BDT'),
             Output('impact_index', 'Sustainable Tourism Impact Index', '0–100'), Output('status', 'Status')),
    formula='leakage = (imported_inputs + repatriated_profits) / tourism_revenue\n'
            'local_capture = local_spend / tourism_revenue\n'
            'LM3 = (tourism_revenue + round2_local + round3_local) / tourism_revenue\n'
            'STII = 100 × (0.4·(1 − leakage) + 0.3·local_capture + 0.3·min((LM3 − 1)/2, 1))',
    method='Leakage follows the import-leakage concept used in tourism impact studies (Archer & Fletcher, 1996); the local '
           'multiplier uses the three-round LM3 approach (Sacks, 2002). The STII composite and its weights are an OpenDMO '
           'screening construct; bands risk < 40 ≤ watch < 60 ≤ ok.',
    references=(ARCHER_FLETCHER_1996, SACKS_2002, UNWTO_2004, OPENDMO),
    weights={'retention (1 − leakage)': 0.4, 'local_capture': 0.3, 'lm3_uplift': 0.3},
    limitations=('LM3 is a survey-based proxy, not an input–output multiplier.',
                 'Round-2/3 values require supplier and employee spending surveys.',
                 'STII is a screening indicator, not a certification.'),
    screening=True, compute=_leakage,
    known_cases=(KnownCase({'tourism_revenue': 1000, 'imported_inputs': 250, 'repatriated_profits': 50, 'local_spend': 600,
                            'round2_local': 400, 'round3_local': 200},
                           {'leakage_rate_pct': 30, 'local_capture_pct': 60, 'local_multiplier_lm3': 1.6,
                            'retained_bdt': 700, 'impact_index': 55, 'status': 'watch'}),),
)


def _rpv(v: dict) -> dict:
    return {'revenue_per_visitor_bdt': r(safe_div(num(v, 'revenue'), num(v, 'visitors'), 'visitors'), 2)}


revenue_per_visitor = Method(
    id='ratio.revenue_per_visitor', version='1.0.0', name='Revenue per Visitor', category='economy', core='economy',
    summary='Tourism revenue divided by visitors in the same period.',
    inputs=(Param('revenue', 'Tourism revenue', 'BDT', min=0, source=('economy', 'tourism_revenue_bdt', 'sum')),
            Param('visitors', 'Visitors', 'visitors', min=0, source=('visitor_flow', 'visitors', 'sum'))),
    outputs=(Output('revenue_per_visitor_bdt', 'Revenue per visitor', 'BDT/visitor'),),
    formula='revenue_per_visitor = revenue / visitors', method='Intensity ratio (UNWTO 2004).',
    references=(UNWTO_2004,), compute=_rpv,
    known_cases=(KnownCase({'revenue': 2_500_000, 'visitors': 1000}, {'revenue_per_visitor_bdt': 2500}),),
)


def _local_employment(v: dict) -> dict:
    share = safe_div(num(v, 'local_employees'), num(v, 'total_employees'), 'total_employees') * 100
    if share > 100:
        raise CalculationError('local employees cannot exceed total employees')
    return {'local_employment_pct': r(share, 2), 'status': band(share, [(50, 'risk'), (70, 'watch')], 'ok')}


local_employment = Method(
    id='economy.local_employment', version='1.0.0', name='Local Employment Share', category='economy', core='economy',
    summary='Share of tourism jobs held by residents of the destination.',
    inputs=(Param('local_employees', 'Local employees', 'persons', min=0, source=('economy', 'local_employees', 'last')),
            Param('total_employees', 'Total tourism employees', 'persons', min=0, source=('economy', 'total_employees', 'last'))),
    outputs=(Output('local_employment_pct', 'Local employment share', '%'), Output('status', 'Status')),
    formula='local_employment_pct = local_employees / total_employees × 100',
    method='UNWTO (2004) local-employment indicator; bands risk < 50 ≤ watch < 70 ≤ ok (OpenDMO).',
    references=(UNWTO_2004,), compute=_local_employment,
    known_cases=(KnownCase({'local_employees': 140, 'total_employees': 200}, {'local_employment_pct': 70, 'status': 'ok'}),),
)


def _projection(v: dict) -> dict:
    base, g, years = num(v, 'base_visitors'), num(v, 'growth_pct'), int(num(v, 'years'))
    shock, cap, y0 = num(v, 'shock_pct'), num(v, 'annual_capacity'), int(num(v, 'base_year'))
    if not 1 <= years <= 30:
        raise CalculationError('years must be 1–30')
    if base < 0 or cap <= 0:
        raise CalculationError('base visitors must be >= 0 and capacity > 0')
    series, value, exceed = [], base, None
    for i in range(1, years + 1):
        value = value * (1 + g / 100) * ((1 + shock / 100) if i == 1 else 1)
        series.append({'period': str(y0 + i), 'value': round(value, 2)})
        if exceed is None and value > cap:
            exceed = str(y0 + i)
    final_util = value / cap * 100
    return {'series': series, 'final_visitors': round(value, 2), 'final_utilisation_pct': r(final_util, 2),
            'first_year_over_capacity': exceed or 'none',
            'status': band(final_util, [(80, 'ok'), (100, 'watch')], 'risk')}


projection = Method(
    id='scenario.demand_projection', version='1.0.0', name='Visitor Demand Scenario Projection', category='scenario', core='economy',
    summary='Compound-growth projection of annual visitors with an optional one-off shock, compared with annual capacity.',
    inputs=(Param('base_visitors', 'Base-year visitors', 'visitors/yr', min=0, source=('visitor_flow', 'visitors', 'sum12')),
            Param('growth_pct', 'Annual growth', '%/yr', default=8, min=-50, max=100),
            Param('shock_pct', 'One-off shock in year 1', '%', default=0, min=-100, max=200),
            Param('years', 'Horizon', 'years', type='int', default=5, min=1, max=30),
            Param('annual_capacity', 'Annual capacity (e.g. ECC × open days)', 'visitors/yr', min=0),
            Param('base_year', 'Base year', 'year', type='int', default=2026, min=1990, max=2100)),
    outputs=(Output('series', 'Projected visitors by year', 'visitors/yr'), Output('final_visitors', 'Final-year visitors', 'visitors/yr'),
             Output('final_utilisation_pct', 'Final-year utilisation', '%'), Output('first_year_over_capacity', 'First year over capacity'),
             Output('status', 'Status')),
    formula='V_t = V_{t−1} × (1 + growth/100) × (1 + shock/100 if t = 1)\nutilisation = V_T / capacity × 100',
    method='Deterministic what-if scenario for side-by-side comparison; not a statistical forecast.',
    references=(OPENDMO,), compute=_projection,
    limitations=('Deterministic; carries no uncertainty band. Use the forecasting methods for data-driven projections.',),
    known_cases=(KnownCase({'base_visitors': 100000, 'growth_pct': 10, 'shock_pct': 0, 'years': 3, 'annual_capacity': 125000, 'base_year': 2026},
                           {'final_visitors': 133100, 'first_year_over_capacity': '2029', 'status': 'risk'}),),
)


def _sustainability(v: dict) -> dict:
    waste, rev = num(v, 'waste_per_visitor_kg'), num(v, 'revenue_per_visitor')
    waste_score = max(0.0, 100 - waste / 0.5 * 100)
    rev_score = min(rev / 5000 * 100, 100)
    idx = 0.5 * waste_score + 0.5 * rev_score
    return {'sustainability_screen': r(idx, 2), 'waste_score': r(waste_score, 2), 'revenue_score': r(rev_score, 2),
            'status': band(idx, [(40, 'risk'), (60, 'watch')], 'ok')}


sustainability = Method(
    id='sustainability.screen', version='1.0.0', name='Sustainability Screening Score', category='economy', core='economy',
    summary='Equal-weighted screen of waste intensity and revenue per visitor.',
    inputs=(Param('waste_per_visitor_kg', 'Waste per visitor', 'kg/visitor', min=0),
            Param('revenue_per_visitor', 'Revenue per visitor', 'BDT/visitor', min=0)),
    outputs=(Output('sustainability_screen', 'Screening score', '0–100'), Output('waste_score', 'Waste sub-score'),
             Output('revenue_score', 'Revenue sub-score'), Output('status', 'Status')),
    formula='0.5 × max(0, 100 − waste/0.5×100) + 0.5 × min(revenue/5000×100, 100)',
    method='Reference levels (0.5 kg, 5000 BDT per visitor) are OpenDMO methodology constants for v1.0.',
    references=(OPENDMO,), weights={'waste_score': 0.5, 'revenue_score': 0.5}, screening=True, compute=_sustainability,
    limitations=('Two indicators only; reference levels are normative constants, not empirical benchmarks.',
                 'Revenue score rewards spend, not distribution of benefits — read with the leakage index.'),
    known_cases=(KnownCase({'waste_per_visitor_kg': 0.25, 'revenue_per_visitor': 2500},
                           {'sustainability_screen': 50, 'waste_score': 50, 'revenue_score': 50}),),
)

METHODS = [leakage, revenue_per_visitor, local_employment, projection, sustainability]
