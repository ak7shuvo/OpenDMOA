"""01 Destination Observatory — visitor flow, carrying capacity, site condition, sentiment."""
from __future__ import annotations

from .base import (CalculationError, KnownCase, Method, Output, Param, band, clamp, num, r,
                   safe_div)
from .references import AP_1992, BUTLER_1980, CIFUENTES_1992, IRTS_2008, OPENDMO, UNWTO_2004

# ------------------------------------------------------------------ Cifuentes

DEFAULT_FACTORS = [
    {'name': 'Precipitation (rainy days)', 'limiting': 120, 'total': 365, 'unit': 'days'},
    {'name': 'Erosion-prone trail length', 'limiting': 300, 'total': 2000, 'unit': 'm'},
    {'name': 'Temporary closures (maintenance)', 'limiting': 24, 'total': 365, 'unit': 'days'},
]


def _cifuentes(v: dict) -> dict:
    area = num(v, 'area_m2')
    per_visitor = num(v, 'area_per_visitor_m2')
    open_h = num(v, 'open_hours')
    visit_h = num(v, 'visit_duration_h')
    mc = num(v, 'management_capacity_pct')
    if area <= 0 or per_visitor <= 0 or open_h <= 0 or visit_h <= 0:
        raise CalculationError('area, area per visitor, opening hours and visit duration must be > 0')
    if not 0 <= mc <= 100:
        raise CalculationError('management capacity must be within 0–100 %')
    rf = open_h / visit_h                                 # rotation factor (visits / visitor-space / day)
    pcc = area / per_visitor * rf
    factors = v.get('correction_factors') or []
    cf_out = []
    product = 1.0
    for f in factors:
        try:
            lim, tot = float(f['limiting']), float(f['total'])
        except (KeyError, TypeError, ValueError) as exc:
            raise CalculationError(f'correction factor needs numeric limiting/total: {f}') from exc
        if tot <= 0 or lim < 0 or lim > tot:
            raise CalculationError(f"correction factor '{f.get('name', '?')}' requires 0 <= limiting <= total, total > 0")
        cf = lim / tot
        product *= (1 - cf)
        cf_out.append({'name': f.get('name', 'factor'), 'cf': r(cf), 'retained': r(1 - cf)})
    rcc = pcc * product
    ecc = rcc * mc / 100
    out = {'rotation_factor': r(rf), 'pcc': r(pcc, 2), 'rcc': r(rcc, 2), 'ecc': r(ecc, 2),
           'correction_product': r(product), 'correction_factors': cf_out}
    observed = v.get('observed_daily_visitors')
    if observed not in (None, ''):
        obs = float(observed)
        if ecc > 0:
            util = obs / ecc * 100
            out['utilisation_pct'] = r(util, 2)
            out['status'] = band(util, [(80, 'ok'), (100, 'watch')], 'risk')
    return out


cifuentes = Method(
    id='capacity.cifuentes', version='2.0.0', name='Tourism Carrying Capacity (Cifuentes PCC/RCC/ECC)',
    category='capacity', core='observatory',
    summary='Physical, real and effective carrying capacity of a visitor site following Cifuentes (1992). '
            'All parameters are editable and every assumption is stored with the run.',
    inputs=(
        Param('area_m2', 'Usable public area / trail length', 'm or m²', 'Area (or linear trail metres) open to visitors', default=2000, min=0),
        Param('area_per_visitor_m2', 'Space required per visitor', 'm or m²', 'Commonly 1 m of trail or 1 m² per person', default=1, min=0),
        Param('open_hours', 'Opening hours per day', 'h', 'Daily hours the site is open', default=8, min=0, max=24),
        Param('visit_duration_h', 'Average visit duration', 'h', 'Time a visitor occupies the site', default=2, min=0, max=24),
        Param('correction_factors', 'Correction factors (limiting / total magnitude)', '', 'Cf = Ml/Mt for each limiting factor', type='factors', default=DEFAULT_FACTORS),
        Param('management_capacity_pct', 'Management capacity (MC)', '%', 'Existing / optimal management capacity', default=50, min=0, max=100),
        Param('observed_daily_visitors', 'Observed peak daily visitors', 'visitors/day', 'Compared against ECC', required=False, min=0,
              source=('visitor_flow', 'daily_peak', 'max')),
    ),
    outputs=(
        Output('pcc', 'Physical carrying capacity', 'visits/day'),
        Output('rcc', 'Real carrying capacity', 'visits/day'),
        Output('ecc', 'Effective carrying capacity', 'visits/day'),
        Output('rotation_factor', 'Rotation factor Rf', 'visits/day'),
        Output('correction_product', 'Π(1 − Cf)', ''),
        Output('utilisation_pct', 'Observed / ECC', '%'),
        Output('status', 'Status band', '', 'ok < 80 % ≤ watch < 100 % ≤ risk'),
    ),
    formula='Rf  = open_hours / visit_duration_h\n'
            'PCC = (area_m2 / area_per_visitor_m2) × Rf\n'
            'Cf_i = limiting_i / total_i\n'
            'RCC = PCC × Π (1 − Cf_i)\n'
            'ECC = RCC × management_capacity_pct / 100',
    method='Cifuentes three-level method. PCC is the theoretical maximum given space and rotation; RCC applies '
           'site-specific limiting factors (weather, erosion, closures, wildlife disturbance…); ECC scales RCC by '
           'the share of management capacity actually available (staff, infrastructure, equipment). Observed peak '
           'visitors are optionally compared with ECC.',
    references=(CIFUENTES_1992, UNWTO_2004),
    limitations=('Correction factors are treated as independent (multiplicative).',
                 'Result is a daily visit ceiling for the defined area only; it does not capture social or perceptual capacity.',
                 'Management capacity is an expert estimate and should be documented with the run.'),
    known_cases=(KnownCase(
        inputs={'area_m2': 2000, 'area_per_visitor_m2': 1, 'open_hours': 8, 'visit_duration_h': 2,
                'correction_factors': [{'name': 'a', 'limiting': 40, 'total': 100}, {'name': 'b', 'limiting': 25, 'total': 100}],
                'management_capacity_pct': 50, 'observed_daily_visitors': 1980},
        expected={'rotation_factor': 4, 'pcc': 8000, 'rcc': 3600, 'ecc': 1800, 'utilisation_pct': 110, 'status': 'risk'},
        note='PCC = 2000/1×4; RCC = 8000×0.6×0.75; ECC = 3600×0.5'),),
    compute=_cifuentes,
    changelog=('2.0.0 — replaces v1 capacity.utilisation as primary capacity method; editable factors.',),
)

# ------------------------------------------------------------------ pressure & utilisation

def _utilisation(v: dict) -> dict:
    util = safe_div(num(v, 'visitors'), num(v, 'capacity'), 'capacity') * 100
    return {'utilisation_pct': r(util, 2), 'status': band(util, [(80, 'ok'), (100, 'watch')], 'risk')}


capacity_utilisation = Method(
    id='capacity.utilisation', version='1.1.0', name='Capacity Utilisation', category='capacity', core='observatory',
    summary='Share of a stated capacity (e.g. ECC × days) used by observed visitors in the same period.',
    inputs=(Param('visitors', 'Visitors in period', 'visitors', min=0, source=('visitor_flow', 'visitors', 'sum')),
            Param('capacity', 'Capacity for the same period', 'visitors', min=0)),
    outputs=(Output('utilisation_pct', 'Utilisation', '%'), Output('status', 'Status band')),
    formula='utilisation_pct = visitors / capacity × 100', method='Simple ratio; bands ok < 80 % ≤ watch < 100 % ≤ risk.',
    references=(UNWTO_2004,), compute=_utilisation, limitations=('Capacity must be expressed for the same period as visitors.',),
    known_cases=(KnownCase({'visitors': 450, 'capacity': 500}, {'utilisation_pct': 90, 'status': 'watch'}),),
)


def _pressure(v: dict) -> dict:
    vcr = safe_div(num(v, 'visitors'), num(v, 'capacity'), 'capacity')
    occ = clamp(num(v, 'occupancy_rate') / 100)
    idx = (0.6 * vcr + 0.4 * occ) * 100
    return {'pressure_index': r(idx, 2), 'visitor_capacity_ratio': r(vcr),
            'pressure_band': band(idx, [(45, 'low'), (75, 'moderate')], 'high'),
            'status': band(idx, [(45, 'ok'), (75, 'watch')], 'risk')}


pressure_index = Method(
    id='pressure.tourism_index', version='1.1.0', name='Tourism Pressure Index', category='pressure', core='observatory',
    summary='Weighted composite of visitor/capacity ratio and accommodation occupancy.',
    inputs=(Param('visitors', 'Visitors in period', 'visitors', min=0, source=('visitor_flow', 'visitors', 'sum')),
            Param('capacity', 'Capacity for the same period', 'visitors', min=0),
            Param('occupancy_rate', 'Accommodation occupancy', '%', min=0, max=100, source=('visitor_flow', 'occupancy_rate', 'mean'))),
    outputs=(Output('pressure_index', 'Pressure index', '0–100+'), Output('visitor_capacity_ratio', 'Visitor/capacity ratio'),
             Output('pressure_band', 'Band'), Output('status', 'Status')),
    formula='index = (0.6 × visitors/capacity + 0.4 × min(occupancy_rate/100, 1)) × 100',
    method='Weights 0.6/0.4 set by OpenDMO methodology v1.1; bands low < 45 ≤ moderate < 75 ≤ high. '
           'Inspired by destination life-cycle pressure concepts (Butler, 1980).',
    references=(BUTLER_1980, OPENDMO), weights={'visitor_capacity_ratio': 0.6, 'occupancy_rate': 0.4},
    limitations=('Weights are normative, not empirically estimated.', 'Unbounded above 100 when visitors exceed capacity.'),
    screening=True, compute=_pressure,
    known_cases=(KnownCase({'visitors': 500, 'capacity': 1000, 'occupancy_rate': 50},
                           {'pressure_index': 50, 'visitor_capacity_ratio': 0.5, 'pressure_band': 'moderate'}),),
)

# ------------------------------------------------------------------ ratios & growth

def _ratio(a: str, b: str, out: str, scale: float = 1.0):
    def f(v: dict) -> dict:
        return {out: r(safe_div(num(v, a), num(v, b), b) * scale, 4)}
    return f


occupancy_rate = Method(
    id='ratio.occupancy_rate', version='1.0.0', name='Accommodation Occupancy Rate', category='ratios', core='observatory',
    summary='Rooms sold as a share of rooms available.',
    inputs=(Param('rooms_sold', 'Room-nights sold', 'room-nights', min=0, source=('visitor_flow', 'rooms_sold', 'sum')),
            Param('rooms_available', 'Room-nights available', 'room-nights', min=0, source=('visitor_flow', 'rooms_available', 'sum'))),
    outputs=(Output('occupancy_rate_pct', 'Occupancy rate', '%'),),
    formula='occupancy_rate_pct = rooms_sold / rooms_available × 100', method='Standard room occupancy definition (IRTS 2008).',
    references=(IRTS_2008,), compute=_ratio('rooms_sold', 'rooms_available', 'occupancy_rate_pct', 100),
    known_cases=(KnownCase({'rooms_sold': 620, 'rooms_available': 1000}, {'occupancy_rate_pct': 62}),),
)

visitor_density = Method(
    id='ratio.visitor_density', version='1.0.0', name='Visitor Density', category='ratios', core='observatory',
    summary='Visitors per square kilometre of destination area in a period.',
    inputs=(Param('visitors', 'Visitors', 'visitors', min=0, source=('visitor_flow', 'visitors', 'sum')),
            Param('area_km2', 'Area', 'km²', min=0)),
    outputs=(Output('visitor_density_per_km2', 'Visitor density', 'visitors/km²'),),
    formula='density = visitors / area_km2', method='Intensity ratio (UNWTO 2004, tourism intensity indicators).',
    references=(UNWTO_2004,), compute=_ratio('visitors', 'area_km2', 'visitor_density_per_km2'),
    known_cases=(KnownCase({'visitors': 5000, 'area_km2': 2.5}, {'visitor_density_per_km2': 2000}),),
)

waste_per_visitor = Method(
    id='ratio.waste_per_visitor', version='1.0.0', name='Waste per Visitor', category='ratios', core='observatory',
    summary='Solid waste generated per visitor.',
    inputs=(Param('waste_kg', 'Solid waste collected', 'kg', min=0, source=('site_condition', 'waste_kg', 'sum')),
            Param('visitors', 'Visitors', 'visitors', min=0, source=('visitor_flow', 'visitors', 'sum'))),
    outputs=(Output('waste_per_visitor_kg', 'Waste per visitor', 'kg/visitor'),),
    formula='waste_per_visitor_kg = waste_kg / visitors', method='Intensity ratio (UNWTO 2004, solid-waste indicators).',
    references=(UNWTO_2004,), compute=_ratio('waste_kg', 'visitors', 'waste_per_visitor_kg'),
    known_cases=(KnownCase({'waste_kg': 300, 'visitors': 1200}, {'waste_per_visitor_kg': 0.25}),),
)


def _growth(v: dict) -> dict:
    prev = num(v, 'value_previous')
    return {'growth_rate_pct': r(safe_div(num(v, 'value_current') - prev, prev, 'value_previous') * 100, 4)}


growth_rate = Method(
    id='growth.rate', version='1.0.0', name='Growth Rate (period-over-period)', category='growth', core='observatory',
    summary='Percentage change between two observation periods.',
    inputs=(Param('value_current', 'Current value'), Param('value_previous', 'Previous value')),
    outputs=(Output('growth_rate_pct', 'Growth rate', '%'),),
    formula='growth_rate_pct = (value_current − value_previous) / value_previous × 100',
    method='Algebraic percentage change; undefined when the base is zero.', compute=_growth,
    known_cases=(KnownCase({'value_current': 110, 'value_previous': 100}, {'growth_rate_pct': 10}),),
)


def _cagr(v: dict) -> dict:
    begin, end, years = num(v, 'value_begin'), num(v, 'value_end'), num(v, 'years')
    if begin <= 0 or end < 0 or years <= 0:
        raise CalculationError('CAGR requires value_begin > 0, value_end >= 0 and years > 0')
    return {'cagr_pct': r(((end / begin) ** (1 / years) - 1) * 100, 4)}


cagr = Method(
    id='growth.cagr', version='1.0.0', name='Compound Annual Growth Rate', category='growth', core='observatory',
    summary='Geometric mean annual growth between two values n years apart.',
    inputs=(Param('value_begin', 'Begin value', min=0), Param('value_end', 'End value', min=0), Param('years', 'Years', 'years', min=0)),
    outputs=(Output('cagr_pct', 'CAGR', '%/year'),),
    formula='cagr_pct = ((value_end / value_begin)^(1/years) − 1) × 100', method='Standard CAGR definition.', compute=_cagr,
    known_cases=(KnownCase({'value_begin': 100, 'value_end': 121, 'years': 2}, {'cagr_pct': 10}),),
)

# ------------------------------------------------------------------ site condition & sentiment

def _site_condition(v: dict) -> dict:
    trail = clamp(num(v, 'trail_condition') / 100)
    litter = clamp(1 - num(v, 'litter_score') / 10)
    erosion = clamp(1 - num(v, 'erosion_score') / 10)
    idx = (0.4 * trail + 0.3 * litter + 0.3 * erosion) * 100
    return {'site_condition_index': r(idx, 2), 'status': band(idx, [(50, 'risk'), (70, 'watch')], 'ok')}


site_condition = Method(
    id='site.condition_index', version='1.0.0', name='Site Condition Index', category='site', core='observatory',
    summary='Composite of trail condition, litter and erosion field scores (higher = better).',
    inputs=(Param('trail_condition', 'Trail condition score', '0–100', min=0, max=100, source=('site_condition', 'trail_condition', 'last')),
            Param('litter_score', 'Litter severity', '0–10', min=0, max=10, source=('site_condition', 'litter_score', 'last')),
            Param('erosion_score', 'Erosion severity', '0–10', min=0, max=10, source=('site_condition', 'erosion_score', 'last'))),
    outputs=(Output('site_condition_index', 'Site condition index', '0–100'), Output('status', 'Status')),
    formula='index = (0.4 × trail/100 + 0.3 × (1 − litter/10) + 0.3 × (1 − erosion/10)) × 100',
    method='Equal-ish weighted field-survey composite; bands risk < 50 ≤ watch < 70 ≤ ok.',
    weights={'trail_condition': 0.4, 'litter': 0.3, 'erosion': 0.3}, references=(UNWTO_2004, OPENDMO), screening=True,
    limitations=('Relies on consistent field scoring protocol between surveys.',),
    compute=_site_condition,
    known_cases=(KnownCase({'trail_condition': 80, 'litter_score': 2, 'erosion_score': 4}, {'site_condition_index': 74}),),
)


def _sentiment(v: dict) -> dict:
    sup, opp = num(v, 'support_pct'), num(v, 'oppose_pct')
    if sup < 0 or opp < 0 or sup + opp > 100.0001:
        raise CalculationError('support + oppose must be between 0 and 100 %')
    net = sup - opp
    n = v.get('respondents')
    out = {'net_support': r(net, 2), 'neutral_pct': r(100 - sup - opp, 2),
           'status': band(net, [(0, 'risk'), (20, 'watch')], 'ok')}
    if n not in (None, '') and float(n) > 0:
        # 95 % margin of error for a proportion at p = 0.5 (conservative)
        out['margin_of_error_pct'] = r(1.96 * (0.25 / float(n)) ** 0.5 * 100, 2)
    return out


sentiment = Method(
    id='sentiment.net_support', version='1.0.0', name='Resident Net Support Score', category='sentiment', core='observatory',
    summary='Share of residents supporting minus share opposing tourism development, with a conservative margin of error.',
    inputs=(Param('support_pct', 'Residents supporting', '%', min=0, max=100, source=('community_sentiment', 'support_pct', 'last')),
            Param('oppose_pct', 'Residents opposing', '%', min=0, max=100, source=('community_sentiment', 'oppose_pct', 'last')),
            Param('respondents', 'Respondents (n)', 'count', required=False, min=0, source=('community_sentiment', 'respondents', 'last'))),
    outputs=(Output('net_support', 'Net support', 'pp'), Output('neutral_pct', 'Neutral', '%'),
             Output('margin_of_error_pct', '95 % margin of error', 'pp'), Output('status', 'Status')),
    formula='net_support = support_pct − oppose_pct\nMoE = 1.96 × √(0.25 / n) × 100',
    method='Resident attitude survey summary (Ap, 1992). Bands risk < 0 ≤ watch < 20 ≤ ok.',
    references=(AP_1992,), compute=_sentiment, screening=True,
    limitations=('Assumes simple random sampling for the margin of error.',),
    known_cases=(KnownCase({'support_pct': 62, 'oppose_pct': 18, 'respondents': 400},
                           {'net_support': 44, 'neutral_pct': 20, 'margin_of_error_pct': 4.9}),),
)


METHODS = [cifuentes, capacity_utilisation, pressure_index, occupancy_rate, visitor_density, waste_per_visitor,
           growth_rate, cagr, site_condition, sentiment]
