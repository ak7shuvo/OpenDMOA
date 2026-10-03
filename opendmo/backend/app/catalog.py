"""Metadata catalog: dataset templates (variable_defs) and the indicator glossary.

Datasets are metadata-driven: a template supplies default ``variable_defs``
(name, label, unit, type, min, max, required, aliases). Import validation,
CSV templates, entry forms and the glossary are all generated from here.
"""
from __future__ import annotations

from copy import deepcopy


def v(name, label, unit='', type='float', min=None, max=None, required=False, description='', aliases=()):
    return {'name': name, 'label': label, 'unit': unit, 'type': type, 'min': min, 'max': max,
            'required': required, 'description': description, 'aliases': list(aliases)}


DATASET_KINDS: dict[str, dict] = {
    'visitor_flow': {
        'label': 'Visitor flow & crowding', 'core': 'observatory', 'frequency': 'monthly',
        'description': 'Monthly visitor counts, peak-day crowding and accommodation occupancy.',
        'variables': [
            v('visitors', 'Visitors', 'visitors', 'int', 0, None, True, 'Total visits in the period', ('visitor_count', 'arrivals', 'tourists')),
            v('daily_peak', 'Peak-day visitors', 'visitors/day', 'int', 0, None, False, 'Highest single-day count in the period', ('peak', 'peak_day')),
            v('domestic_share_pct', 'Domestic share', '%', 'float', 0, 100, False, 'Share of domestic visitors'),
            v('occupancy_rate', 'Accommodation occupancy', '%', 'float', 0, 100, False, 'Room occupancy', ('occupancy', 'hotel_occupancy')),
            v('rooms_available', 'Room-nights available', 'room-nights', 'int', 0),
            v('rooms_sold', 'Room-nights sold', 'room-nights', 'int', 0),
            v('avg_stay_nights', 'Average length of stay', 'nights', 'float', 0, 60),
        ],
    },
    'site_condition': {
        'label': 'Site condition survey', 'core': 'observatory', 'frequency': 'monthly',
        'description': 'Field condition scores and waste collected.',
        'variables': [
            v('trail_condition', 'Trail condition', '0–100', 'float', 0, 100, True, 'Protocol score, 100 = excellent'),
            v('litter_score', 'Litter severity', '0–10', 'float', 0, 10, False, '0 = none, 10 = severe'),
            v('erosion_score', 'Erosion severity', '0–10', 'float', 0, 10, False, '0 = none, 10 = severe'),
            v('waste_kg', 'Solid waste collected', 'kg', 'float', 0, None, False, '', ('waste',)),
            v('facilities_score', 'Visitor facilities', '0–100', 'float', 0, 100),
        ],
    },
    'community_sentiment': {
        'label': 'Community sentiment survey', 'core': 'observatory', 'frequency': 'quarterly',
        'description': 'Resident attitude survey summaries.',
        'variables': [
            v('support_pct', 'Residents supporting tourism', '%', 'float', 0, 100, True),
            v('oppose_pct', 'Residents opposing', '%', 'float', 0, 100, True),
            v('respondents', 'Respondents', 'count', 'int', 0, None, False, 'Sample size n', ('n', 'sample_size')),
            v('crowding_concern_pct', 'Concerned about crowding', '%', 'float', 0, 100),
            v('benefit_perception_pct', 'Perceive personal benefit', '%', 'float', 0, 100),
        ],
    },
    'weather': {
        'label': 'Weather & hydrology observations', 'core': 'climate', 'frequency': 'monthly',
        'description': 'Station rainfall, temperature and river stage.',
        'variables': [
            v('rainfall_mm', 'Rainfall', 'mm', 'float', 0, 5000, True, 'Monthly total', ('rain', 'precip', 'precipitation')),
            v('rainfall_normal_mm', 'Rainfall normal', 'mm', 'float', 0, 5000, False, '1991–2020 normal for the month'),
            v('temp_mean_c', 'Mean temperature', '°C', 'float', -10, 50, False, '', ('temperature', 'temp')),
            v('rain_days', 'Rain days', 'days', 'int', 0, 31),
            v('river_stage_m', 'River stage (max)', 'm', 'float', 0, 60, False, 'Maximum gauge reading'),
        ],
    },
    'hazard_factors': {
        'label': 'Hazard conditioning factors', 'core': 'climate', 'frequency': 'monthly',
        'description': 'Inputs to flood & landslide susceptibility screens and event counts.',
        'variables': [
            v('rainfall_72h_mm', 'Max 72-hour rainfall', 'mm', 'float', 0, 2000, True),
            v('soil_saturation_pct', 'Soil saturation', '%', 'float', 0, 100),
            v('slope_deg', 'Representative slope', '°', 'float', 0, 90),
            v('landslide_events', 'Landslide events', 'count', 'int', 0),
            v('flood_days', 'Days above danger level', 'days', 'int', 0, 31),
        ],
    },
    'ecosystem': {
        'label': 'Ecosystem indicators', 'core': 'climate', 'frequency': 'yearly',
        'description': 'Land cover, vegetation greenness and water quality.',
        'variables': [
            v('forest_cover_pct', 'Forest cover', '%', 'float', 0, 100, True),
            v('forest_cover_change_pct', 'Forest cover change', '%/yr', 'float', -100, 100),
            v('ndvi', 'Mean NDVI', '', 'float', -1, 1),
            v('ndvi_anomaly', 'NDVI anomaly', 'Δ', 'float', -1, 1),
            v('water_quality_index', 'Water quality index', '0–100', 'float', 0, 100),
            v('species_count', 'Indicator species recorded', 'count', 'int', 0),
        ],
    },
    'economy': {
        'label': 'Tourism economy & leakage', 'core': 'economy', 'frequency': 'yearly',
        'description': 'Revenue, leakage and local multiplier survey inputs; employment.',
        'variables': [
            v('tourism_revenue_bdt', 'Tourism revenue', 'BDT', 'float', 0, None, True, '', ('revenue',)),
            v('imported_inputs_bdt', 'Imported inputs', 'BDT', 'float', 0),
            v('repatriated_profits_bdt', 'Repatriated profits', 'BDT', 'float', 0),
            v('local_spend_bdt', 'Locally captured spend', 'BDT', 'float', 0),
            v('round2_local_bdt', 'LM3 round 2', 'BDT', 'float', 0),
            v('round3_local_bdt', 'LM3 round 3', 'BDT', 'float', 0),
            v('local_employees', 'Local tourism employees', 'persons', 'int', 0),
            v('total_employees', 'Total tourism employees', 'persons', 'int', 0),
            v('avg_spend_per_visitor_bdt', 'Average spend per visitor', 'BDT', 'float', 0),
        ],
    },
    'custom': {
        'label': 'Custom dataset', 'core': 'lab', 'frequency': 'monthly',
        'description': 'Any variables — definitions are created from the CSV columns you map.',
        'variables': [],
    },
}


def kind_variables(kind: str) -> list[dict]:
    return deepcopy(DATASET_KINDS.get(kind, DATASET_KINDS['custom'])['variables'])


def list_kinds() -> list[dict]:
    return [{'kind': k, **{x: y for x, y in d.items() if x != 'variables'}, 'variables': deepcopy(d['variables'])}
            for k, d in DATASET_KINDS.items()]


# ---------------------------------------------------------------------------- indicators
# status direction: 'up_bad' — higher is worse; 'up_good' — higher is better.

def ind(id, label, core, kind, variable, agg, unit, description, direction=None, watch=None, risk=None, decimals=0):
    return {'id': id, 'label': label, 'core': core, 'kind': kind, 'variable': variable, 'aggregation': agg,
            'unit': unit, 'description': description, 'direction': direction, 'watch': watch, 'risk': risk,
            'decimals': decimals}


INDICATORS: list[dict] = [
    ind('visitors', 'Visitors', 'observatory', 'visitor_flow', 'visitors', 'sum', 'visitors', 'Total visits in the selected time range.', decimals=0),
    ind('daily_peak', 'Peak-day visitors', 'observatory', 'visitor_flow', 'daily_peak', 'max', 'visitors/day',
        'Highest single-day visitor count; compare with effective carrying capacity (ECC).'),
    ind('occupancy', 'Accommodation occupancy', 'observatory', 'visitor_flow', 'occupancy_rate', 'mean', '%',
        'Mean room occupancy.', 'up_bad', 75, 90, 1),
    ind('trail_condition', 'Trail condition', 'observatory', 'site_condition', 'trail_condition', 'last', '0–100',
        'Latest field condition score (100 = excellent).', 'up_good', 70, 50, 0),
    ind('support', 'Resident support', 'observatory', 'community_sentiment', 'support_pct', 'last', '%',
        'Share of residents supporting tourism (latest survey).', 'up_good', 55, 40, 0),
    ind('waste', 'Waste collected', 'observatory', 'site_condition', 'waste_kg', 'sum', 'kg', 'Solid waste collected at sites.'),

    ind('rainfall', 'Rainfall', 'climate', 'weather', 'rainfall_mm', 'sum', 'mm', 'Total rainfall in the selected range.'),
    ind('rain_anomaly', 'Rainfall anomaly', 'climate', 'weather', 'rainfall_anomaly_pct', 'derived', '%',
        'Total rainfall vs the sum of monthly normals in range (WMO normal method).', 'up_bad', 15, 30, 1),
    ind('river_stage', 'River stage (max)', 'climate', 'weather', 'river_stage_m', 'max', 'm', 'Highest gauge reading in range.', decimals=2),
    ind('rain72', 'Max 72-h rainfall', 'climate', 'hazard_factors', 'rainfall_72h_mm', 'max', 'mm',
        'Antecedent rainfall trigger for landslides.', 'up_bad', 100, 200, 0),
    ind('forest_cover', 'Forest cover', 'climate', 'ecosystem', 'forest_cover_pct', 'last', '%', 'Latest forest cover estimate.', 'up_good', 50, 35, 1),
    ind('water_quality', 'Water quality index', 'climate', 'ecosystem', 'water_quality_index', 'last', '0–100',
        'Latest water quality index.', 'up_good', 60, 40, 0),

    ind('revenue', 'Tourism revenue', 'economy', 'economy', 'tourism_revenue_bdt', 'sum', 'BDT', 'Tourism revenue in range.'),
    ind('leakage', 'Leakage rate', 'economy', 'economy', 'leakage_pct', 'derived', '%',
        '(imported inputs + repatriated profits) / revenue, latest year.', 'up_bad', 30, 45, 1),
    ind('local_capture', 'Local capture', 'economy', 'economy', 'local_capture_pct', 'derived', '%',
        'Locally captured spend / revenue, latest year.', 'up_good', 50, 35, 1),
    ind('local_jobs', 'Local employment share', 'economy', 'economy', 'local_employment_pct', 'derived', '%',
        'Local / total tourism employees, latest year.', 'up_good', 70, 50, 1),
    ind('spend', 'Spend per visitor', 'economy', 'economy', 'avg_spend_per_visitor_bdt', 'last', 'BDT', 'Average spend per visitor.'),
    ind('visitors_growth', 'Visitor growth (YoY)', 'economy', 'visitor_flow', 'visitors_yoy_pct', 'derived', '%',
        'Visitors in range vs the same span one year earlier.', decimals=1),
]

INDICATOR_BY_ID = {i['id']: i for i in INDICATORS}

GLOSSARY_EXTRA = [
    {'term': 'PCC / RCC / ECC', 'definition': 'Physical, real and effective carrying capacity (Cifuentes, 1992): the theoretical, factor-corrected and management-adjusted daily visit ceilings for a site.'},
    {'term': 'Correction factor (Cf)', 'definition': 'Share of a magnitude that limits visitation, Cf = limiting / total (e.g. rainy days / 365).'},
    {'term': 'Leakage rate', 'definition': 'Share of tourism revenue that leaves the destination through imports and repatriated profits.'},
    {'term': 'LM3', 'definition': 'Local Multiplier 3: (round-1 + round-2 + round-3 local spending) / round-1 income (Sacks, 2002).'},
    {'term': 'Screening indicator', 'definition': 'A transparent, documented composite used for prioritisation. Not a certification, accreditation or regulatory determination.'},
    {'term': 'MAE / RMSE / MAPE / MASE', 'definition': 'Forecast accuracy on a hold-out sample: mean absolute error, root-mean-square error, mean absolute percentage error, mean absolute scaled error (Hyndman & Koehler, 2006).'},
    {'term': 'Data quality score', 'definition': '0–100 score from completeness, range violations, outliers and estimated values. ≥ 80 high, ≥ 60 moderate, otherwise low.'},
    {'term': 'DEMO', 'definition': 'Synthetic seed-pack data generated for demonstration. Never cite DEMO values as findings.'},
    {'term': 'Provenance', 'definition': 'The full record of a result: data (dataset id, version, file hash), method (id, version), parameters, software version and timestamp.'},
]
