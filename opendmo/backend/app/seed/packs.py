"""DEMO seed packs — deterministic synthetic data for the four pilot destinations.

Every row created here carries ``is_demo = True`` and every dataset name starts
with "DEMO ·". Values are plausible in shape (seasonality, monsoon, COVID-19
dip) but are NOT observations and must never be cited as findings.
"""
from __future__ import annotations

import zlib

import numpy as np
from sqlalchemy import delete, select

from .. import catalog
from ..models import (Asset, Dataset, Destination, EarlyWarning, GisLayer, ImportRecord, Incident, InfraProject,
                      Observation, Publication, ReadinessItem, Run, Scenario)
from ..services import datasets as dsvc

PACK_VERSION = '2.0.0'
SOURCE = f'OpenDMO synthetic seed pack v{PACK_VERSION} (DEMO — not real observations)'

PILOTS = [
    {'id': 'jaflong', 'name': 'Jaflong', 'region': 'Sylhet Division', 'latitude': 25.163, 'longitude': 92.017,
     'area_km2': 12.0, 'description': 'Riverine stone-bed landscape on the Piyain River at the Dauki border; high weekend crowding.',
     'attributes': {'gauge': 'Piyain (Jaflong)', 'danger_level_m': 12.5, 'elevation_m': 25, 'climate': 'sylhet', 'area_m2': 60000, 'area_per_visitor_m2': 4, 'open_hours': 10, 'visit_duration_h': 3, 'management_capacity_pct': 50}},
    {'id': 'ratargul', 'name': 'Ratargul Swamp Forest', 'region': 'Sylhet Division', 'latitude': 25.004, 'longitude': 91.969,
     'area_km2': 3.3, 'description': 'Freshwater swamp forest visited by boat; monsoon-season peak; boat-access controls.',
     'attributes': {'gauge': 'Goyain (Gowainghat)', 'danger_level_m': 10.8, 'elevation_m': 12, 'climate': 'sylhet', 'area_m2': 30000, 'area_per_visitor_m2': 10, 'open_hours': 9, 'visit_duration_h': 2, 'management_capacity_pct': 50}},
    {'id': 'sajek', 'name': 'Sajek Valley', 'region': 'Chittagong Hill Tracts (Rangamati)', 'latitude': 23.382, 'longitude': 92.294,
     'area_km2': 7.5, 'description': 'Ridge-top hill destination with rapid resort growth and slope instability on the access road.',
     'attributes': {'gauge': 'Kassalong (nearest)', 'danger_level_m': 9.5, 'elevation_m': 550, 'climate': 'cht', 'area_m2': 40000, 'area_per_visitor_m2': 5, 'open_hours': 12, 'visit_duration_h': 4, 'management_capacity_pct': 40}},
    {'id': 'bandarban', 'name': 'Bandarban', 'region': 'Chittagong Hill Tracts (Bandarban)', 'latitude': 22.195, 'longitude': 92.218,
     'area_km2': 45.0, 'description': 'Hill district with distributed sites (Nilgiri, Boga Lake, Nafakhum); flash-flood and landslide exposure.',
     'attributes': {'gauge': 'Sangu (Bandarban)', 'danger_level_m': 15.25, 'elevation_m': 90, 'climate': 'cht', 'area_m2': 150000, 'area_per_visitor_m2': 4, 'open_hours': 10, 'visit_duration_h': 3, 'management_capacity_pct': 50}},
]

# monthly profiles (index 0 = Jan)
RAIN_NORMAL = {
    'sylhet': [8, 25, 90, 300, 530, 820, 800, 640, 500, 210, 30, 10],
    'cht': [6, 20, 55, 140, 300, 560, 640, 520, 330, 190, 50, 10],
}
TEMP = {
    'sylhet': [18.8, 21.0, 24.6, 26.4, 27.0, 27.8, 28.3, 28.4, 27.9, 26.6, 23.4, 20.0],
    'cht': [19.6, 21.9, 25.4, 27.4, 27.9, 27.6, 27.3, 27.4, 27.5, 26.9, 24.0, 20.9],
}
PROFILE = {
    'jaflong': {'base': 52000, 'growth': 0.07, 'season': [1.5, 1.4, 1.2, 0.9, 0.7, 0.5, 0.6, 0.7, 0.8, 1.0, 1.3, 1.6], 'peak_ratio': 0.11, 'slope': 18},
    'ratargul': {'base': 18000, 'growth': 0.06, 'season': [0.4, 0.4, 0.5, 0.6, 0.8, 1.3, 1.8, 1.9, 1.6, 1.2, 0.6, 0.5], 'peak_ratio': 0.12, 'slope': 4},
    'sajek': {'base': 30000, 'growth': 0.12, 'season': [1.5, 1.3, 1.0, 0.7, 0.6, 0.5, 0.6, 0.8, 1.0, 1.3, 1.5, 1.7], 'peak_ratio': 0.09, 'slope': 31},
    'bandarban': {'base': 70000, 'growth': 0.08, 'season': [1.5, 1.3, 1.0, 0.7, 0.6, 0.4, 0.5, 0.6, 0.8, 1.2, 1.5, 1.8], 'peak_ratio': 0.08, 'slope': 27},
}
FIRST_YEAR, LAST_MONTH = 2019, (2026, 8)


def _rng(dest: str, salt: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(f'{dest}:{salt}'.encode()))


def _months():
    y, m = FIRST_YEAR, 1
    while (y, m) <= LAST_MONTH:
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def _covid(y: int, m: int) -> float:
    if y == 2020 and 4 <= m <= 8:
        return 0.08
    if (y == 2020 and m >= 9) or (y == 2021 and m <= 3):
        return 0.55
    if y == 2021 and 4 <= m <= 8:
        return 0.35
    return 1.0


def generate(dest_id: str) -> dict[str, list[dict]]:
    """Return {kind: [{period, variable, value, unit}]} for one destination."""
    prof = PROFILE[dest_id]
    meta = next(p for p in PILOTS if p['id'] == dest_id)
    clim = meta['attributes']['climate']
    rng = _rng(dest_id, 'obs')
    defs = {k: {d['name']: d for d in catalog.kind_variables(k)} for k in catalog.DATASET_KINDS}
    out: dict[str, list[dict]] = {k: [] for k in ['visitor_flow', 'site_condition', 'weather', 'hazard_factors',
                                                    'community_sentiment', 'ecosystem', 'economy']}

    def add(kind, period, var, value, decimals=2):
        out[kind].append({'period': period, 'variable': var, 'value': round(float(value), decimals),
                          'unit': defs[kind][var]['unit']})

    rooms = {'jaflong': 1400, 'ratargul': 300, 'sajek': 2600, 'bandarban': 5200}[dest_id]
    annual: dict[int, float] = {}
    for y, m in _months():
        p = f'{y}-{m:02d}'
        t = (y - FIRST_YEAR) + (m - 1) / 12
        trend = prof['base'] * (1 + prof['growth']) ** t
        eid_boost = 1.25 if (y, m) in {(2023, 4), (2023, 6), (2024, 4), (2024, 6), (2025, 3), (2025, 6), (2026, 3), (2026, 5)} else 1.0
        visitors = max(50.0, trend * prof['season'][m - 1] * _covid(y, m) * eid_boost * rng.normal(1, 0.06))
        annual[y] = annual.get(y, 0) + visitors
        peak = visitors * prof['peak_ratio'] * rng.normal(1, 0.08)
        occ = min(97, max(6, 46 * prof['season'][m - 1] ** 0.8 * _covid(y, m) * (1 + 0.02 * (y - FIRST_YEAR)) * rng.normal(1, 0.05)))
        add('visitor_flow', p, 'visitors', visitors, 0)
        add('visitor_flow', p, 'daily_peak', peak, 0)
        add('visitor_flow', p, 'domestic_share_pct', min(99.5, 96 + rng.normal(0, 1)), 1)
        add('visitor_flow', p, 'occupancy_rate', occ, 1)
        add('visitor_flow', p, 'rooms_available', rooms * 30, 0)
        add('visitor_flow', p, 'rooms_sold', rooms * 30 * occ / 100, 0)
        add('visitor_flow', p, 'avg_stay_nights', max(0.3, {'jaflong': 0.6, 'ratargul': 0.4, 'sajek': 1.7, 'bandarban': 2.1}[dest_id] + rng.normal(0, 0.1)), 2)

        load = visitors / (prof['base'] * 1.6)
        add('site_condition', p, 'trail_condition', min(100, max(20, 88 - 22 * load - 1.2 * (y - FIRST_YEAR) + rng.normal(0, 3))), 1)
        add('site_condition', p, 'litter_score', min(10, max(0, 2 + 4.5 * load + rng.normal(0, 0.6))), 1)
        add('site_condition', p, 'erosion_score', min(10, max(0, (3 if prof['slope'] > 20 else 2) + RAIN_NORMAL[clim][m - 1] / 250 + rng.normal(0, 0.5))), 1)
        add('site_condition', p, 'waste_kg', visitors * 0.32 * rng.normal(1, 0.1), 0)
        add('site_condition', p, 'facilities_score', min(100, max(10, 55 + 2 * (y - FIRST_YEAR) + rng.normal(0, 4))), 1)

        normal = RAIN_NORMAL[clim][m - 1]
        rain = max(0, normal * rng.lognormal(0, 0.28) * (1.35 if (y, m) in {(2022, 6), (2024, 8), (2026, 6)} else 1))
        add('weather', p, 'rainfall_mm', rain, 1)
        add('weather', p, 'rainfall_normal_mm', normal, 1)
        add('weather', p, 'temp_mean_c', TEMP[clim][m - 1] + 0.03 * (y - FIRST_YEAR) + rng.normal(0, 0.5), 1)
        add('weather', p, 'rain_days', min(31, max(0, round(rain / 22 + rng.normal(0, 1.2)))), 0)
        danger = meta['attributes']['danger_level_m']
        add('weather', p, 'river_stage_m', max(0.5, danger * (0.35 + 0.6 * min(1.15, rain / 820)) + rng.normal(0, 0.25)), 2)

        r72 = rain * rng.uniform(0.18, 0.34)
        add('hazard_factors', p, 'rainfall_72h_mm', r72, 1)
        add('hazard_factors', p, 'soil_saturation_pct', min(100, 25 + 70 * min(1, rain / 700) + rng.normal(0, 4)), 1)
        add('hazard_factors', p, 'slope_deg', prof['slope'] + rng.normal(0, 0.4), 1)
        lam = max(0.0, (r72 - 90) / 60) * (1.0 if prof['slope'] > 20 else 0.15)
        add('hazard_factors', p, 'landslide_events', rng.poisson(lam), 0)
        add('hazard_factors', p, 'flood_days', min(31, rng.poisson(max(0.0, (rain - 450) / 90))), 0)

    for y in range(FIRST_YEAR, 2027):
        for q in range(1, 5):
            if (y, q) > (2026, 2):
                break
            p = f'{y}-Q{q}'
            pressure = {'jaflong': 0.9, 'ratargul': 0.3, 'sajek': 1.2, 'bandarban': 0.6}[dest_id]
            support = 72 - pressure * 2.2 * (y - FIRST_YEAR) + rng.normal(0, 2.5)
            oppose = 10 + pressure * 1.6 * (y - FIRST_YEAR) + rng.normal(0, 2)
            add('community_sentiment', p, 'support_pct', min(95, max(5, support)), 1)
            add('community_sentiment', p, 'oppose_pct', min(90, max(2, oppose)), 1)
            add('community_sentiment', p, 'respondents', int(rng.integers(90, 260)), 0)
            add('community_sentiment', p, 'crowding_concern_pct', min(95, max(5, 20 + pressure * 5 * (y - FIRST_YEAR) + rng.normal(0, 3))), 1)
            add('community_sentiment', p, 'benefit_perception_pct', min(95, max(5, 48 + rng.normal(0, 4))), 1)

    cover0 = {'jaflong': 38, 'ratargul': 81, 'sajek': 54, 'bandarban': 63}[dest_id]
    loss = {'jaflong': -0.6, 'ratargul': -0.1, 'sajek': -1.9, 'bandarban': -1.4}[dest_id]
    cover = cover0
    for y in range(2015, 2026):
        change = loss + rng.normal(0, 0.35)
        cover = cover * (1 + change / 100)
        add('ecosystem', str(y), 'forest_cover_pct', cover, 2)
        add('ecosystem', str(y), 'forest_cover_change_pct', change, 2)
        ndvi = 0.35 + cover / 200 + rng.normal(0, 0.01)
        add('ecosystem', str(y), 'ndvi', ndvi, 3)
        add('ecosystem', str(y), 'ndvi_anomaly', change / 40 + rng.normal(0, 0.01), 3)
        add('ecosystem', str(y), 'water_quality_index', min(100, max(10, {'jaflong': 58, 'ratargul': 74, 'sajek': 66, 'bandarban': 61}[dest_id] - 0.8 * (y - 2015) + rng.normal(0, 2))), 1)
        add('ecosystem', str(y), 'species_count', max(5, int(cover * 1.1 + rng.normal(0, 3))), 0)

    spend = {'jaflong': 1800, 'ratargul': 1200, 'sajek': 6500, 'bandarban': 5200}[dest_id]
    leak = {'jaflong': 0.24, 'ratargul': 0.15, 'sajek': 0.46, 'bandarban': 0.33}[dest_id]
    for y in range(FIRST_YEAR, 2026):
        visitors = annual.get(y, 0)
        s = spend * (1.06 ** (y - FIRST_YEAR)) * rng.normal(1, 0.03)
        rev = visitors * s
        lk = min(0.8, max(0.05, leak + 0.01 * (y - FIRST_YEAR) * (1 if dest_id == 'sajek' else 0.2) + rng.normal(0, 0.015)))
        add('economy', str(y), 'tourism_revenue_bdt', rev, 0)
        add('economy', str(y), 'imported_inputs_bdt', rev * lk * 0.8, 0)
        add('economy', str(y), 'repatriated_profits_bdt', rev * lk * 0.2, 0)
        local = rev * (1 - lk) * rng.uniform(0.75, 0.9)
        add('economy', str(y), 'local_spend_bdt', local, 0)
        add('economy', str(y), 'round2_local_bdt', local * rng.uniform(0.35, 0.5), 0)
        add('economy', str(y), 'round3_local_bdt', local * rng.uniform(0.15, 0.25), 0)
        jobs = int(visitors / 260)
        add('economy', str(y), 'total_employees', jobs, 0)
        add('economy', str(y), 'local_employees', int(jobs * (0.82 - lk * 0.5 + rng.normal(0, 0.02))), 0)
        add('economy', str(y), 'avg_spend_per_visitor_bdt', s, 0)
    return out


# ---------------------------------------------------------------------------- entities

ASSETS = {
    'jaflong': [('Piyain River stone bed', 'natural', 'river landscape', 'poor', ['stone extraction', 'littering', 'bank erosion'], 'Ecologically Critical Area (proposed)', 25.164, 92.016),
                ('Khasi Punji (Khasia village)', 'cultural', 'indigenous settlement', 'fair', ['visitor intrusion', 'commodification'], 'community-managed', 25.158, 92.025),
                ('Dauki river view terraces', 'natural', 'viewpoint', 'fair', ['crowding', 'unregulated vending'], 'unprotected', 25.170, 92.012)],
    'ratargul': [('Swamp forest core (Barringtonia–Pongamia)', 'natural', 'freshwater swamp forest', 'good', ['boat congestion', 'siltation'], 'Special Biodiversity Conservation Area (2015)', 25.004, 91.969),
                 ('Watchtower & boat ghat', 'mixed', 'visitor facility', 'fair', ['overloading', 'waste'], 'Forest Department', 25.008, 91.965)],
    'sajek': [('Ruilui Para (Lushai village)', 'cultural', 'indigenous settlement', 'fair', ['resort encroachment', 'water scarcity'], 'community-managed', 23.382, 92.294),
              ('Konglak Para hilltop', 'mixed', 'viewpoint & settlement', 'fair', ['trail erosion', 'crowding'], 'unprotected', 23.395, 92.300),
              ('Sajek ridge forest belt', 'natural', 'hill forest', 'poor', ['clearing for construction', 'landslide'], 'unclassed state forest', 23.375, 92.290)],
    'bandarban': [('Boga Lake', 'natural', 'crater-type lake', 'good', ['waste', 'unregulated trekking'], 'unprotected', 21.980, 92.469),
                  ('Nilgiri hilltop', 'natural', 'viewpoint', 'fair', ['access-road cuts', 'crowding'], 'army-managed site', 21.913, 92.326),
                  ('Buddha Dhatu Jadi (Golden Temple)', 'cultural', 'religious site', 'good', ['visitor conduct'], 'religious trust', 22.215, 92.200),
                  ('Nafakhum falls', 'natural', 'waterfall', 'fair', ['drowning risk', 'flash floods'], 'unprotected', 21.700, 92.517)],
}

READINESS = [
    ('Early warning', 'Warning dissemination tree (SMS / loudspeaker) tested this season', True),
    ('Early warning', 'Gauge / rainfall thresholds agreed with BWDB & BMD', True),
    ('Evacuation', 'Evacuation routes signposted and cleared', False),
    ('Evacuation', 'Safe shelters identified with capacity recorded', True),
    ('Response', 'Tourist police & guide roster with phone numbers', True),
    ('Response', 'First-aid kits and trained first responders at main sites', False),
    ('Response', 'Boat / vehicle availability for rescue confirmed', False),
    ('Communication', 'Multilingual visitor advisories prepared (Bangla / English)', True),
    ('Communication', 'Hotel / resort operator contact list current', True),
    ('Recovery', 'Damage & loss assessment template ready', False),
    ('Recovery', 'Business continuity contacts for small operators', False),
    ('Coordination', 'Upazila Disaster Management Committee contact confirmed', True),
]


def _square(lat, lon, d=0.012):
    return [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]


def entities(dest_id: str) -> dict:
    meta = next(p for p in PILOTS if p['id'] == dest_id)
    lat, lon = meta['latitude'], meta['longitude']
    hill = dest_id in ('sajek', 'bandarban')
    warnings = [{'hazard': 'landslide' if hill else 'flash flood', 'level': 'watch', 'issued_at': '2026-08-21T06:00',
                 'valid_until': '2026-08-24T06:00', 'message': ('Heavy rainfall forecast; slopes along access road may fail.' if hill
                                                                 else 'Upstream rainfall in Meghalaya may raise river levels rapidly.'),
                 'source': 'DEMO — illustrative bulletin', 'active': True}]
    if dest_id == 'bandarban':
        warnings.append({'hazard': 'flash flood', 'level': 'warning', 'issued_at': '2026-08-22T09:00', 'valid_until': '2026-08-25T09:00',
                         'message': 'Sangu river rising; avoid riverside trails and Nafakhum route.', 'source': 'DEMO — illustrative bulletin', 'active': True})
    incidents = [
        {'occurred_at': '2025-07-14', 'hazard': 'landslide' if hill else 'flood', 'severity': 'moderate',
         'description': 'Access route blocked for 18 h; visitors held at checkpoint.', 'status': 'closed',
         'response': 'Road cleared by LGED; advisory issued to operators.'},
        {'occurred_at': '2026-06-28', 'hazard': 'drowning' if dest_id in ('jaflong', 'bandarban') else 'boat capsize',
         'severity': 'major', 'description': 'Visitor safety incident in fast-flowing water.', 'status': 'monitoring',
         'response': 'Signage and lifeguard pilot under review.'},
    ]
    projects = {
        'jaflong': [('Riverbank visitor walkway', 'visitor facilities', 'building', 85, '2025-11', '2026-12'),
                    ('Waste segregation & collection points', 'waste', 'planned', 12, '2026-10', '2027-03')],
        'ratargul': [('Boat ghat capacity controls & ticketing', 'access management', 'done', 6, '2024-01', '2024-09'),
                     ('Eco-interpretation centre', 'visitor facilities', 'proposed', 40, '', '')],
        'sajek': [('Slope stabilisation km 18 access road', 'access', 'building', 220, '2025-12', '2027-06'),
                  ('Rainwater harvesting for Ruilui Para', 'water', 'planned', 18, '2026-11', '2027-04'),
                  ('Resort registration & zoning plan', 'planning', 'stalled', 3, '2024-05', '')],
        'bandarban': [('Thanchi–Remakri trail safety upgrade', 'access', 'planned', 64, '2026-12', '2027-12'),
                      ('Boga Lake waste management', 'waste', 'building', 9, '2026-02', '2026-11')],
    }[dest_id]
    layers = [
        {'name': f'{meta["name"]} — site boundary (schematic)', 'category': 'boundary', 'color': '#B3202A',
         'geojson': {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': meta['name'], 'demo': True},
                                                                'geometry': {'type': 'Polygon', 'coordinates': [_square(lat, lon)]}}]}},
        {'name': f'{meta["name"]} — access route (schematic)', 'category': 'infrastructure', 'color': '#BDB4A3',
         'geojson': {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': 'access route', 'demo': True},
                                                                'geometry': {'type': 'LineString', 'coordinates': [
                                                                    [lon - 0.08, lat - 0.06], [lon - 0.03, lat - 0.025], [lon, lat]]}}]}},
    ]
    return {'warnings': warnings, 'incidents': incidents, 'projects': projects, 'layers': layers}


# ---------------------------------------------------------------------------- load / remove

def ensure_pilots(db) -> None:
    for p in PILOTS:
        if db.get(Destination, p['id']) is None:
            db.add(Destination(**{k: v for k, v in p.items()}, is_pilot=True, country='Bangladesh'))
    db.commit()


def pack_status(db) -> list[dict]:
    out = []
    for p in PILOTS:
        n = db.scalar(select(Dataset.id).where(Dataset.destination_id == p['id'], Dataset.is_demo.is_(True)).limit(1))
        out.append({'id': f'demo-{p["id"]}', 'destination_id': p['id'], 'name': f'DEMO seed pack — {p["name"]}',
                    'version': PACK_VERSION, 'loaded': n is not None,
                    'contents': ['7 datasets (visitor flow, site condition, sentiment, weather, hazard factors, ecosystem, economy)',
                                 'heritage assets', 'warnings & incidents', 'readiness checklist', 'infrastructure projects',
                                 'schematic GIS layers']})
    return out


def load_pack(db, dest_id: str) -> dict:
    if dest_id not in PROFILE:
        raise ValueError(f'no seed pack for {dest_id}')
    ensure_pilots(db)
    if any(s['loaded'] for s in pack_status(db) if s['destination_id'] == dest_id):
        return {'destination_id': dest_id, 'status': 'already-loaded'}
    data = generate(dest_id)
    n_obs = 0
    for kind, rows in data.items():
        ds = dsvc.create_dataset(db, dest_id, kind, f'DEMO · {catalog.DATASET_KINDS[kind]["label"]}', is_demo=True,
                                 provenance={'source': SOURCE, 'generator': 'app/seed/packs.py', 'pack_version': PACK_VERSION})
        for r in rows:
            db.add(Observation(dataset_id=ds.id, destination_id=dest_id, period=r['period'], variable=r['variable'],
                               value=r['value'], unit=r['unit'], quality_flag='ok', import_id='seed'))
        n_obs += len(rows)
        db.commit()
        dsvc.compute_quality(db, ds)
        ds.status = 'validated'
        db.commit()
    ent = entities(dest_id)
    for i, a in enumerate(ASSETS[dest_id]):
        db.add(Asset(id=f'demo-{dest_id}-asset-{i + 1}', destination_id=dest_id, name=a[0], asset_type=a[1], category=a[2],
                     condition=a[3], threats=a[4], protection_status=a[5], latitude=a[6], longitude=a[7],
                     last_assessed='2026-03-15', notes='DEMO record — verify on site.', is_demo=True))
    for i, w in enumerate(ent['warnings']):
        db.add(EarlyWarning(id=f'demo-{dest_id}-warn-{i + 1}', destination_id=dest_id, is_demo=True, **w))
    for i, inc in enumerate(ent['incidents']):
        db.add(Incident(id=f'demo-{dest_id}-inc-{i + 1}', destination_id=dest_id, is_demo=True, **inc))
    for i, (cat, item, done) in enumerate(READINESS):
        db.add(ReadinessItem(id=f'demo-{dest_id}-rdy-{i + 1}', destination_id=dest_id, category=cat, item=item,
                             done=done if dest_id != 'sajek' else (done and i % 3 != 0), is_demo=True))
    for i, (name, cat, stage, budget, start, end) in enumerate(ent['projects']):
        db.add(InfraProject(id=f'demo-{dest_id}-prj-{i + 1}', destination_id=dest_id, name=name, category=cat, stage=stage,
                            budget_bdt_m=budget, start=start, end=end, notes='DEMO record', is_demo=True))
    for i, layer in enumerate(ent['layers']):
        db.add(GisLayer(id=f'demo-{dest_id}-layer-{i + 1}', destination_id=dest_id, source=SOURCE, is_demo=True, **layer))
    if dest_id == 'sajek':
        db.add(Publication(id='demo-pub-1', title='Carrying capacity of Sajek Valley ridge settlements (working paper)',
                           authors='OpenDMO pilot team', pub_type='working-paper', status='draft', venue='SUST working paper series',
                           due='2026-12-15', notes='DEMO record', is_demo=True))
    if dest_id == 'jaflong':
        db.add(Publication(id='demo-pub-2', title='Policy brief: crowd management at Jaflong zero point', authors='OpenDMO pilot team',
                           pub_type='policy-brief', status='review', venue='Sylhet DMO roundtable', due='2026-11-01',
                           notes='DEMO record', is_demo=True))
    db.commit()
    return {'destination_id': dest_id, 'status': 'loaded', 'datasets': len(data), 'observations': n_obs}


def remove_pack(db, dest_id: str) -> dict:
    ds_ids = list(db.scalars(select(Dataset.id).where(Dataset.destination_id == dest_id, Dataset.is_demo.is_(True))))
    counts = {'datasets': len(ds_ids)}
    if ds_ids:
        counts['observations'] = db.execute(delete(Observation).where(Observation.dataset_id.in_(ds_ids))).rowcount
        db.execute(delete(ImportRecord).where(ImportRecord.dataset_id.in_(ds_ids)))
    run_ids = list(db.scalars(select(Run.id).where(Run.destination_id == dest_id, Run.is_demo.is_(True))))
    if run_ids:
        db.execute(delete(Scenario).where(Scenario.run_id.in_(run_ids)))
        counts['runs'] = db.execute(delete(Run).where(Run.id.in_(run_ids))).rowcount
    if ds_ids:
        db.execute(delete(Dataset).where(Dataset.id.in_(ds_ids)))
    for model in (Asset, EarlyWarning, Incident, ReadinessItem, InfraProject, GisLayer):
        counts[model.__tablename__] = db.execute(delete(model).where(model.destination_id == dest_id, model.is_demo.is_(True))).rowcount
    if dest_id == 'sajek':
        db.execute(delete(Publication).where(Publication.id == 'demo-pub-1'))
    if dest_id == 'jaflong':
        db.execute(delete(Publication).where(Publication.id == 'demo-pub-2'))
    db.commit()
    return {'destination_id': dest_id, 'status': 'removed', 'deleted': counts}

