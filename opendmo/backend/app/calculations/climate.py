"""02 Climate & Risk — anomalies, hazard susceptibility screens, ecosystem stress, readiness."""
from __future__ import annotations

from .base import CalculationError, KnownCase, Method, Output, Param, band, clamp, num, r, safe_div
from .references import AHMED_DEWAN_2017, OPENDMO, SAATY_1980, UNWTO_2004, WMO_2017

SUSCEPTIBILITY_CUTS = [(0.25, 'low'), (0.5, 'moderate'), (0.75, 'high')]


def _anomaly(v: dict) -> dict:
    value, normal = num(v, 'value'), num(v, 'normal')
    diff = value - normal
    return {'anomaly': r(diff, 4), 'anomaly_pct': r(safe_div(diff, normal, 'normal') * 100, 4)}


anomaly = Method(
    id='climate.anomaly', version='1.0.0', name='Climate Anomaly vs Normal', category='weather', core='climate',
    summary='Deviation of an observed climate value (e.g. monthly rainfall) from its climatological normal.',
    inputs=(Param('value', 'Observed value', 'mm or °C', source=('weather', 'rainfall_mm', 'sum')),
            Param('normal', 'Climatological normal for the same period', 'mm or °C')),
    outputs=(Output('anomaly', 'Absolute anomaly', 'same as input'), Output('anomaly_pct', 'Relative anomaly', '%')),
    formula='anomaly = value − normal\nanomaly_pct = (value − normal) / normal × 100',
    method='Normals should follow WMO guidance (30-year reference period, e.g. 1991–2020).',
    references=(WMO_2017,), compute=_anomaly,
    known_cases=(KnownCase({'value': 330, 'normal': 300}, {'anomaly': 30, 'anomaly_pct': 10}),),
)


def _landslide(v: dict) -> dict:
    s = clamp(num(v, 'slope_deg') / 45)
    p = clamp(num(v, 'rainfall_72h_mm') / 300)
    veg = clamp(1 - num(v, 'forest_cover_pct') / 100)
    m = clamp(num(v, 'soil_saturation_pct') / 100)
    idx = 0.35 * s + 0.30 * p + 0.15 * veg + 0.20 * m
    return {'susceptibility': r(idx), 'class': band(idx, SUSCEPTIBILITY_CUTS, 'very high'),
            'status': band(idx, [(0.4, 'ok'), (0.6, 'watch')], 'risk'),
            'factor_scores': {'slope': r(s), 'rainfall': r(p), 'vegetation_loss': r(veg), 'saturation': r(m)}}


landslide = Method(
    id='hazard.landslide_susceptibility', version='1.0.0', name='Landslide Susceptibility Screen',
    category='hazard', core='climate',
    summary='Weighted-overlay screen of slope, antecedent rainfall, vegetation loss and soil saturation.',
    inputs=(Param('slope_deg', 'Slope', '°', min=0, max=90, source=('hazard_factors', 'slope_deg', 'last')),
            Param('rainfall_72h_mm', '72-hour rainfall', 'mm', min=0, source=('hazard_factors', 'rainfall_72h_mm', 'last')),
            Param('forest_cover_pct', 'Forest / vegetation cover', '%', min=0, max=100, source=('ecosystem', 'forest_cover_pct', 'last')),
            Param('soil_saturation_pct', 'Soil saturation', '%', min=0, max=100, source=('hazard_factors', 'soil_saturation_pct', 'last'))),
    outputs=(Output('susceptibility', 'Susceptibility', '0–1'), Output('class', 'Class'), Output('status', 'Status'),
             Output('factor_scores', 'Normalised factor scores')),
    formula='S = 0.35·min(slope/45,1) + 0.30·min(rain72/300,1) + 0.15·(1 − cover/100) + 0.20·(saturation/100)\n'
            'class: low < 0.25 ≤ moderate < 0.5 ≤ high < 0.75 ≤ very high',
    method='Heuristic weighted linear combination of normalised conditioning and triggering factors, with weights in the '
           'spirit of AHP expert weighting (Saaty, 1980) and factor choice following landslide studies in Chittagong '
           '(Ahmed & Dewan, 2017).',
    references=(SAATY_1980, AHMED_DEWAN_2017, OPENDMO),
    weights={'slope': 0.35, 'rainfall_72h': 0.30, 'vegetation_loss': 0.15, 'soil_saturation': 0.20},
    limitations=('Screening only — not a substitute for a calibrated susceptibility map or geotechnical survey.',
                 'Normalisation ceilings (45°, 300 mm) are methodology constants of v1.0.',
                 'Point-based: apply per slope unit or site.'),
    screening=True, compute=_landslide,
    known_cases=(KnownCase({'slope_deg': 30, 'rainfall_72h_mm': 150, 'forest_cover_pct': 60, 'soil_saturation_pct': 80},
                           {'susceptibility': 0.6033, 'class': 'high', 'status': 'risk'}),),
)


def _flood(v: dict) -> dict:
    danger = num(v, 'danger_level_m')
    if danger <= 0:
        raise CalculationError('danger level must be > 0')
    stage = clamp(num(v, 'river_stage_m') / danger)
    p = clamp(num(v, 'rainfall_72h_mm') / 300)
    e = clamp(1 - num(v, 'elevation_m') / 100)
    d = clamp(1 - num(v, 'distance_to_river_m') / 2000)
    idx = 0.40 * stage + 0.30 * p + 0.15 * e + 0.15 * d
    return {'susceptibility': r(idx), 'class': band(idx, SUSCEPTIBILITY_CUTS, 'very high'),
            'status': band(idx, [(0.4, 'ok'), (0.6, 'watch')], 'risk'),
            'stage_to_danger_ratio': r(num(v, 'river_stage_m') / danger),
            'factor_scores': {'stage': r(stage), 'rainfall': r(p), 'low_elevation': r(e), 'proximity': r(d)}}


flood = Method(
    id='hazard.flood_susceptibility', version='1.0.0', name='Flood Susceptibility Screen', category='hazard', core='climate',
    summary='Weighted-overlay screen of river stage relative to danger level, rainfall, elevation and river proximity.',
    inputs=(Param('river_stage_m', 'River stage', 'm', min=0, source=('weather', 'river_stage_m', 'max')),
            Param('danger_level_m', 'Danger level at gauge', 'm', min=0),
            Param('rainfall_72h_mm', '72-hour rainfall', 'mm', min=0, source=('hazard_factors', 'rainfall_72h_mm', 'last')),
            Param('elevation_m', 'Site elevation', 'm a.s.l.', min=0),
            Param('distance_to_river_m', 'Distance to main channel', 'm', min=0)),
    outputs=(Output('susceptibility', 'Susceptibility', '0–1'), Output('class', 'Class'), Output('status', 'Status'),
             Output('stage_to_danger_ratio', 'Stage / danger level')),
    formula='F = 0.40·min(stage/danger,1) + 0.30·min(rain72/300,1) + 0.15·(1 − min(elev/100,1)) + 0.15·(1 − min(dist/2000,1))',
    method='Heuristic weighted overlay (AHP-style weights, Saaty 1980). Danger levels come from the national gauge network.',
    references=(SAATY_1980, OPENDMO),
    weights={'stage_ratio': 0.40, 'rainfall_72h': 0.30, 'low_elevation': 0.15, 'proximity': 0.15},
    limitations=('Screening only — not a hydrodynamic model.', 'Flash floods in hill catchments may precede gauge response.'),
    screening=True, compute=_flood,
    known_cases=(KnownCase({'river_stage_m': 9, 'danger_level_m': 10, 'rainfall_72h_mm': 150, 'elevation_m': 20,
                            'distance_to_river_m': 500}, {'susceptibility': 0.7425, 'class': 'high', 'status': 'risk'}),),
)


def _ecosystem(v: dict) -> dict:
    loss = clamp(-num(v, 'forest_cover_change_pct') / 5)
    ndvi = clamp(-num(v, 'ndvi_anomaly') / 0.2)
    water = clamp(1 - num(v, 'water_quality_index') / 100)
    press = clamp(num(v, 'utilisation_pct') / 150)
    idx = (0.30 * loss + 0.25 * ndvi + 0.25 * water + 0.20 * press) * 100
    return {'ecosystem_stress_index': r(idx, 2), 'status': band(idx, [(35, 'ok'), (60, 'watch')], 'risk'),
            'factor_scores': {'forest_loss': r(loss), 'ndvi_decline': r(ndvi), 'water_quality': r(water), 'visitor_pressure': r(press)}}


ecosystem = Method(
    id='ecosystem.stress_index', version='1.0.0', name='Ecosystem Stress Index', category='ecosystem', core='climate',
    summary='Composite of forest-cover loss, vegetation (NDVI) decline, water quality and visitor pressure.',
    inputs=(Param('forest_cover_change_pct', 'Annual forest cover change', '%', source=('ecosystem', 'forest_cover_change_pct', 'last')),
            Param('ndvi_anomaly', 'NDVI anomaly', 'Δ NDVI', min=-1, max=1, source=('ecosystem', 'ndvi_anomaly', 'last')),
            Param('water_quality_index', 'Water quality index', '0–100', min=0, max=100, source=('ecosystem', 'water_quality_index', 'last')),
            Param('utilisation_pct', 'Capacity utilisation', '%', min=0, default=80)),
    outputs=(Output('ecosystem_stress_index', 'Stress index', '0–100'), Output('status', 'Status'), Output('factor_scores', 'Factor scores')),
    formula='E = 100 × (0.30·min(−Δcover/5,1)₊ + 0.25·min(−ΔNDVI/0.2,1)₊ + 0.25·(1 − WQI/100) + 0.20·min(util/150,1))',
    method='Screening composite; bands ok < 35 ≤ watch < 60 ≤ risk. Indicator families follow UNWTO (2004).',
    references=(UNWTO_2004, OPENDMO), weights={'forest_loss': 0.30, 'ndvi_decline': 0.25, 'water_quality': 0.25, 'visitor_pressure': 0.20},
    limitations=('Normalisation ceilings (5 %/yr cover loss, 0.2 NDVI) are methodology constants of v1.0.',),
    screening=True, compute=_ecosystem,
    known_cases=(KnownCase({'forest_cover_change_pct': -2.5, 'ndvi_anomaly': -0.05, 'water_quality_index': 60, 'utilisation_pct': 75},
                           {'ecosystem_stress_index': 41.25, 'status': 'watch'}),),
)


def _readiness(v: dict) -> dict:
    done, total = num(v, 'items_done'), num(v, 'items_total')
    crit = num(v, 'critical_open')
    if total <= 0 or done < 0 or done > total:
        raise CalculationError('requires 0 <= items_done <= items_total and items_total > 0')
    pct = done / total * 100
    status = 'risk' if crit > 0 or pct < 50 else 'watch' if pct < 80 else 'ok'
    return {'readiness_pct': r(pct, 2), 'status': status}


readiness = Method(
    id='resilience.readiness', version='1.0.0', name='Response Readiness Score', category='resilience', core='climate',
    summary='Share of the response-readiness checklist completed, escalated when critical items remain open.',
    inputs=(Param('items_done', 'Items completed', 'count', min=0), Param('items_total', 'Items total', 'count', min=0),
            Param('critical_open', 'Critical items open', 'count', min=0, default=0)),
    outputs=(Output('readiness_pct', 'Readiness', '%'), Output('status', 'Status')),
    formula='readiness_pct = items_done / items_total × 100\nstatus = risk if critical_open > 0 or pct < 50; watch if pct < 80',
    method='Checklist completion ratio used in the Crisis & Disaster Resilience Command view.',
    references=(OPENDMO,), compute=_readiness, screening=True,
    limitations=('All checklist items are weighted equally.', 'Completion is self-reported; verify with drills.'),
    known_cases=(KnownCase({'items_done': 9, 'items_total': 12, 'critical_open': 0}, {'readiness_pct': 75, 'status': 'watch'}),),
)

METHODS = [anomaly, landslide, flood, ecosystem, readiness]
