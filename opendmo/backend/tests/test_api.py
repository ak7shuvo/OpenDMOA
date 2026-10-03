"""API + provenance + Control Board integration tests."""
import io
import json
import zipfile

import httpx
import pytest


def test_health_meta_and_headers(client):
    r = client.get('/api/health')
    assert r.status_code == 200 and r.json()['status'] == 'ok' and r.json()['version'] == '2.0.0'
    assert "default-src 'self'" in r.headers['content-security-policy']
    meta = client.get('/api/meta').json()
    assert len(meta['cores']) == 4 and meta['information_chain'][0] == 'LOCATION'
    assert client.get('/api/does-not-exist').status_code == 404
    assert client.get('/api/does-not-exist').json()['detail'].startswith('unknown API route')


def test_pilots_and_add_destination(client):
    ids = [d['id'] for d in client.get('/api/destinations').json()]
    assert {'jaflong', 'ratargul', 'sajek', 'bandarban'} <= set(ids)
    r = client.post('/api/destinations', json={'name': 'Lalakhal', 'region': 'Sylhet', 'latitude': 25.1, 'longitude': 92.2})
    assert r.status_code == 201 and r.json()['id'] == 'lalakhal'
    assert client.post('/api/destinations', json={'name': 'Lalakhal'}).status_code == 409
    assert client.delete('/api/destinations/jaflong').status_code == 409
    assert client.delete('/api/destinations/lalakhal').status_code == 200


def _wizard(client, ds_id, text, name='visits.csv', **opts):
    up = client.post('/api/imports/upload', files={'file': (name, text.encode(), 'text/csv')}, data={'dataset_id': ds_id})
    assert up.status_code == 200, up.text
    body = up.json()
    payload = {'token': body['token'], 'dataset_id': ds_id, 'mapping': body['suggested_mapping'], **opts}
    return body, payload


def test_import_wizard_end_to_end(client):
    ds = client.post('/api/datasets', json={'destination_id': 'sajek', 'kind': 'visitor_flow', 'name': 'Gate survey'}).json()
    text = 'Month;Visitors;Occupancy\n2024-01;1000;55\n2024-02;1100;60\n2024-03;oops;61\n'
    det, payload = _wizard(client, ds['id'], text)
    assert det['delimiter'] == ';' and det['columns'] == ['Month', 'Visitors', 'Occupancy'] and len(det['preview']) == 3
    assert det['suggested_mapping']['columns'] == {'Visitors': 'visitors', 'Occupancy': 'occupancy_rate'}
    val = client.post('/api/imports/validate', json=payload).json()
    assert val['errors'] == 1 and val['will_insert'] == 5 and val['issues'][0]['row'] == 4
    assert client.post('/api/imports/commit', json=payload).status_code == 422          # errors block commit
    res = client.post('/api/imports/commit', json={**payload, 'skip_invalid': True})
    assert res.status_code == 201 and res.json()['inserted'] == 5
    again = client.post('/api/imports/commit', json={**payload, 'skip_invalid': True}).json()
    assert again['status'] == 'duplicate'
    detail = client.get(f"/api/datasets/{ds['id']}").json()
    assert detail['observations'] == 5 and len(detail['imports']) == 1
    assert detail['provenance']['imports'][0]['file_hash'] == res.json()['file_hash']
    csv_out = client.get(f"/api/datasets/{ds['id']}/export.csv?layout=wide").text
    assert csv_out.splitlines()[0] == 'period,occupancy_rate,visitors'
    js = client.get(f"/api/datasets/{ds['id']}/export.json").json()
    assert len(js['observations']) == 5


def test_paste_json_and_custom_dataset(client):
    ds = client.post('/api/datasets', json={'destination_id': 'ratargul', 'kind': 'custom', 'name': 'Boat counts'}).json()
    content = json.dumps([{'period': '2024-01', 'boats': 12}, {'period': '2024-02', 'boats': 15}])
    p = client.post('/api/imports/paste', json={'content': content, 'dataset_id': ds['id']}).json()
    payload = {'token': p['token'], 'dataset_id': ds['id'], 'mapping': p['suggested_mapping']}
    assert p['suggested_mapping']['columns'] == {'boats': 'boats'}
    res = client.post('/api/imports/commit', json=payload).json()
    assert res['inserted'] == 2
    assert [v['name'] for v in client.get(f"/api/datasets/{ds['id']}").json()['variable_defs']] == ['boats']


def test_templates_download(client):
    r = client.get('/api/catalog/kinds/visitor_flow/template.csv?layout=long')
    assert r.status_code == 200 and r.text.startswith('period,variable,value,unit')
    assert 'attachment' in r.headers['content-disposition']


def test_dataset_versioning_and_archive(client):
    ds = client.post('/api/datasets', json={'destination_id': 'jaflong', 'kind': 'weather', 'name': 'Station A'}).json()
    client.post(f"/api/datasets/{ds['id']}/observations", json={'observations': [{'period': '2024-01', 'variable': 'rainfall_mm', 'value': 10}]})
    assert client.post(f"/api/datasets/{ds['id']}/archive").json()['status'] == 'archived'
    r = client.post(f"/api/datasets/{ds['id']}/observations", json={'observations': [{'period': '2024-02', 'variable': 'rainfall_mm', 'value': 11}]})
    assert r.status_code == 409
    v2 = client.post(f"/api/datasets/{ds['id']}/version").json()
    assert v2['version'] == 2 and v2['observations'] == 1 and v2['provenance']['derived_from'] == ds['id']
    bad = client.post(f"/api/datasets/{v2['id']}/observations", json={'observations': [{'period': '2024-02', 'variable': 'rainfall_mm', 'value': -5}]})
    assert bad.status_code == 422 and bad.json()['issues'][0]['code'] == 'out_of_range'


def test_run_provenance_rerun_bundle(demo_client):
    c = demo_client
    res = c.post('/api/methods/capacity.cifuentes/resolve', json={'destination_id': 'jaflong', 'start': '2025-09', 'end': '2026-08'}).json()
    assert res['inputs']['area_m2'] == 60000 and 'observed_daily_visitors' in res['sources']
    ds = c.get('/api/datasets?destination_id=jaflong&kind=visitor_flow').json()[0]
    run = c.post('/api/runs', json={'method_id': 'capacity.cifuentes', 'inputs': res['inputs'], 'destination_id': 'jaflong',
                                    'dataset_id': ds['id'], 'input_sources': res['sources']}).json()
    assert run['status'] == 'success' and run['is_demo'] is True
    prov = run['provenance']
    assert prov['method']['id'] == 'capacity.cifuentes' and prov['method']['version'] == '2.0.0'
    assert prov['data']['dataset_id'] == ds['id'] and len(prov['data']['dataset_hash']) == 64
    assert prov['software_version'] == '2.0.0' and prov['timestamp'].endswith('+00:00')
    assert prov['quality']['level'] == 'high'
    rr = c.post(f"/api/runs/{run['id']}/rerun").json()
    assert rr['reproduced'] is True and rr['rerun_of'] == run['id']
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/runs/{run['id']}/bundle.zip").content))
    assert {'run.json', 'inputs.csv', 'outputs.csv', 'methodology.md', 'dataset.csv', 'CITATION.bib', 'README.txt'} <= set(z.namelist())
    assert 'Cifuentes' in z.read('methodology.md').decode() and 'DEMO' in z.read('README.txt').decode()
    assert c.get(f"/api/runs/{run['id']}/export.csv").text.startswith('key,value')
    assert any(r['id'] == run['id'] for r in c.get('/api/runs?method_id=capacity.cifuentes').json())


def test_failed_run_is_recorded(client):
    r = client.post('/api/runs', json={'method_id': 'growth.rate', 'inputs': {'value_current': 1, 'value_previous': 0}})
    assert r.status_code == 201 and r.json()['status'] == 'failed' and 'zero' in r.json()['error']
    assert client.post('/api/runs', json={'method_id': 'nope', 'inputs': {}}).status_code == 422


def test_forecasts_and_scenarios(demo_client):
    c = demo_client
    runs = []
    for mid in ['forecast.seasonal_naive', 'forecast.holt_winters', 'forecast.linear_trend']:
        f = c.post('/api/forecasts', json={'method_id': mid, 'destination_id': 'jaflong', 'horizon': 6, 'end': '2026-08'}).json()
        assert f['status'] == 'success', f
        out = f['outputs']
        assert len(out['forecast']) == 6 and out['forecast'][0]['period'] == '2026-09'
        assert {'mae', 'rmse', 'mape_pct'} <= set(out['backtest'])
        runs.append(f['id'])
    s1 = c.post('/api/scenarios', json={'name': 'HW', 'run_id': runs[1]}).json()
    p = c.post('/api/runs', json={'method_id': 'scenario.demand_projection', 'destination_id': 'jaflong', 'inputs': {
        'base_visitors': 900000, 'growth_pct': 8, 'years': 5, 'annual_capacity': 1500000}}).json()
    s2 = c.post('/api/scenarios', json={'name': 'Growth 8%', 'run_id': p['id']}).json()
    cmp = c.get(f"/api/scenarios/compare?ids={s1['id']},{s2['id']}").json()
    assert len(cmp['columns']) == 2 and cmp['mixed_methods'] is True
    assert 'final_visitors' in cmp['output_keys']


def test_disable_method_blocks_runs(client):
    assert client.post('/api/system/methods/growth.rate', json={'enabled': False}).json()['enabled'] is False
    r = client.post('/api/runs', json={'method_id': 'growth.rate', 'inputs': {'value_current': 2, 'value_previous': 1}})
    assert r.status_code == 422 and 'disabled' in r.json()['detail']
    client.post('/api/system/methods/growth.rate', json={'enabled': True})
    audit = client.get('/api/system/audit').json()
    assert [a['action'] for a in audit][:2] == ['method.enable', 'method.disable']


def test_summary_kpis(demo_client):
    s = demo_client.get('/api/destinations/jaflong/summary?start=2025-09&end=2026-08').json()
    k = {x['id']: x for x in s['kpis']}
    assert k['visitors']['value'] > 0 and k['visitors']['source']['is_demo'] is True
    assert k['forest_cover']['value'] is not None  # annual data overlaps the window
    assert k['leakage']['status'] in ('ok', 'watch', 'risk')
    assert s['has_demo'] and s['counts']['warnings_active'] >= 1


def test_seed_pack_load_remove(client):
    assert client.post('/api/system/seed-packs/sajek/load').json()['status'] == 'loaded'
    assert client.post('/api/system/seed-packs/sajek/load').json()['status'] == 'already-loaded'
    assert any(p['loaded'] for p in client.get('/api/system/seed-packs').json() if p['destination_id'] == 'sajek')
    res = client.post('/api/system/seed-packs/sajek/remove').json()
    assert res['deleted']['datasets'] == 7
    assert client.get('/api/datasets?destination_id=sajek').json() == []


def test_backup_reset_restore_roundtrip(demo_client):
    c = demo_client
    n = len(c.get('/api/datasets').json())
    backup = c.get('/api/system/backup')
    assert backup.status_code == 200 and backup.headers['content-type'] == 'application/zip'
    assert c.post('/api/system/reset', json={'confirm': 'nope'}).status_code == 422
    r = c.post('/api/system/reset', json={'confirm': 'RESET'}).json()
    assert r['status'] == 'reset' and r['safety_backup'].endswith('.zip')
    assert c.get('/api/datasets').json() == []
    assert len(c.get('/api/destinations').json()) == 4
    bad = c.post('/api/system/restore', files={'file': ('b.zip', backup.content, 'application/zip')}, data={'confirm': 'x'})
    assert bad.status_code == 422
    ok = c.post('/api/system/restore', files={'file': ('b.zip', backup.content, 'application/zip')}, data={'confirm': 'RESTORE'})
    assert ok.status_code == 200, ok.text
    assert len(c.get('/api/datasets').json()) == n
    assert len(c.get('/api/system/backups').json()) >= 2
    assert c.post('/api/system/restore', files={'file': ('x.zip', b'not a zip', 'application/zip')}, data={'confirm': 'RESTORE'}).status_code == 422


def test_export_all(demo_client):
    z = zipfile.ZipFile(io.BytesIO(demo_client.get('/api/system/export').content))
    names = z.namelist()
    assert 'runs.json' in names and any(n.endswith('.wide.csv') for n in names) and 'assets.json' in names


def test_registers_crud(client):
    r = client.post('/api/assets', json={'destination_id': 'jaflong', 'name': 'Old bridge', 'asset_type': 'cultural',
                                         'condition': 'poor', 'threats': 'flooding, vandalism'})
    assert r.status_code == 201 and r.json()['threats'] == ['flooding', 'vandalism']
    assert client.post('/api/assets', json={'destination_id': 'jaflong', 'name': 'x', 'condition': 'bad'}).status_code == 422
    aid = r.json()['id']
    assert client.patch(f'/api/assets/{aid}', json={'condition': 'critical'}).json()['condition'] == 'critical'
    w = client.post('/api/warnings', json={'destination_id': 'sajek', 'hazard': 'landslide', 'level': 'warning', 'issued_at': '2026-09-01T06:00'})
    assert w.status_code == 201
    assert client.delete(f'/api/assets/{aid}').status_code == 200
    pub = client.post('/api/publications', json={'title': 'Paper', 'status': 'idea'})
    assert pub.status_code == 201


def test_gis_upload_validation(client):
    gj = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Point', 'coordinates': [92.0, 25.1]}}]}
    r = client.post('/api/gis/layers', files={'file': ('pts.geojson', json.dumps(gj).encode(), 'application/geo+json')},
                    data={'destination_id': 'jaflong'})
    assert r.status_code == 201 and r.json()['features'] == 1
    bad = {'type': 'Point', 'coordinates': [500000, 2700000]}   # projected metres, not WGS84
    r = client.post('/api/gis/layers', files={'file': ('bad.geojson', json.dumps(bad).encode(), 'application/json')})
    assert r.status_code == 422 and 'WGS84' in r.json()['detail']
    assert client.get('/api/gis/basemap').json()['type'] == 'FeatureCollection'


def test_briefs_markdown_html(demo_client):
    c = demo_client
    run = c.post('/api/runs', json={'method_id': 'economy.leakage_impact', 'destination_id': 'jaflong', 'inputs': {
        'tourism_revenue': 1000, 'imported_inputs': 250, 'repatriated_profits': 50, 'local_spend': 600,
        'round2_local': 400, 'round3_local': 200}}).json()
    b = c.post('/api/briefs', json={'title': 'Leakage brief', 'destination_id': 'jaflong', 'run_ids': [run['id']],
                                    'summary': 'Test summary', 'recommendations': ['Buy local']}).json()
    assert '# Leakage brief' in b['markdown'] and 'screening' in b['markdown'] and 'Sacks' in b['markdown']
    html = c.get(f"/api/briefs/{b['id']}/brief.html").text
    assert '<h1>Leakage brief</h1>' in html and '<table>' in html and 'http' not in html.split('<body>')[0]
    assert c.get(f"/api/briefs/{b['id']}/brief.md").status_code == 200


def test_methods_methodology_citation_glossary(client):
    ms = client.get('/api/methods?core=economy').json()
    assert all(m['core'] == 'economy' for m in ms) and any(m['kind'] == 'forecast' for m in ms)
    md = client.get('/api/methodology.md').text
    assert md.startswith('# OpenDMO 2.0.0') and 'Cifuentes' in md
    cit = client.get('/api/citation').json()
    assert cit['cff'].startswith('cff-version') and '@software{opendmo2026' in cit['bibtex_all']
    terms = client.get('/api/glossary').json()
    assert any(t['term'] == 'Screening indicator' for t in terms)


def test_settings_and_diagnostics(client):
    r = client.put('/api/system/settings', json={'theme': 'light', 'date_format': 'DD/MM/YYYY'}).json()
    assert r['settings']['theme'] == 'light' and r['restart_required'] is False
    r = client.put('/api/system/settings', json={'port': 8123}).json()
    assert r['restart_required'] is True and r['settings']['port'] == 8123
    assert client.put('/api/system/settings', json={'nonsense': 1}).status_code == 422
    d = client.get('/api/system/diagnostics').json()
    assert d['opendmo_version'] == '2.0.0' and d['packages']['fastapi'] and 'python' in d['text']
    st = client.get('/api/system/status').json()
    from tests.conftest import PG_URL
    if PG_URL:
        assert st['db_engine'] == 'postgresql' and 'password' not in st['db_path']
    else:
        assert st['db_engine'] == 'sqlite' and st['db_path'].endswith('opendmo.db')


# ----------------------------------------------------------------------------- model runtime

def test_bundled_demo_model_runs(client):
    models = client.get('/api/models').json()
    demo = [m for m in models if m['id'] == 'demo-tourism-demand'][0]
    assert demo['is_demo'] and demo['status'] == 'enabled' and 'NOT' in demo['description']
    inputs = {'visitor_count': 100, 'hotel_occupancy': 50, 'rainfall': 10, 'temperature': 25, 'holiday': 1, 'event_count': 2}
    r = client.post('/api/models/run', json={'model_id': 'demo-tourism-demand', 'inputs': inputs, 'destination_id': 'jaflong'}).json()
    # 40 + 108 + 80 - 21 + 22.5 + 85 + 44
    assert r['status'] == 'success' and r['outputs']['prediction']['value'] == pytest.approx(358.5)
    assert r['is_demo'] is True
    rr = client.post(f"/api/runs/{r['id']}/rerun").json()
    assert rr['reproduced'] is True
    client.post('/api/models/demo-tourism-demand/1.0.0/status', json={'status': 'disabled'})
    assert client.post('/api/models/run', json={'model_id': 'demo-tourism-demand', 'inputs': inputs}).status_code == 422


def _pkg_zip(framework='json-linear', extra=None, root='repo-main'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(f'{root}/metadata.json', json.dumps({'id': 'gh-model', 'name': 'GH', 'version': '0.1.0', 'task': 'regression',
                                                         'framework': framework, 'description': 'd', 'source_repo': 'x', 'license': 'MIT'}))
        z.writestr(f'{root}/schema.json', json.dumps({'inputs': [{'name': 'x', 'type': 'float'}], 'outputs': [{'name': 'prediction', 'type': 'float'}]}))
        z.writestr(f'{root}/requirements.txt', 'numpy\n')
        z.writestr(f'{root}/README.md', '# m')
        z.writestr(f'{root}/model/model.json', json.dumps({'bias': 1, 'coefficients': {'x': 2}}))
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


def _mock_client(payload):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=payload)))


def test_install_from_github_mocked(db):
    from app.services import models as ms
    pkg = ms.install_from_github(db, 'https://github.com/example/models', client=_mock_client(_pkg_zip()))
    assert pkg.id == 'gh-model' and pkg.status == 'disabled'  # never auto-enabled
    assert pkg.source_repo == 'https://github.com/example/models'
    assert ms.pkg_dict(pkg)['requirements_txt'] == 'numpy\n'  # shown, never installed


def test_install_rejects_traversal_and_executables(db):
    from app.services import models as ms
    from app.runtime.contract import PackageError
    with pytest.raises(PackageError, match='unsafe path'):
        ms.install_from_github(db, 'example/models', client=_mock_client(_pkg_zip(extra={'../evil.txt': 'x'})))
    with pytest.raises(PackageError, match='executable'):
        ms.install_from_github(db, 'example/models', client=_mock_client(_pkg_zip(extra={'repo-main/model/run.py': 'import os'})))


def test_pickle_refused_by_default(db):
    from app.services import models as ms
    from app.runtime.contract import PackageError
    pkg = ms.install_from_github(db, 'example/models', client=_mock_client(_pkg_zip('sklearn-joblib')))
    pkg.status = 'enabled'
    db.commit()
    run = ms.run_model(db, pkg.id, pkg.version, None, {'x': 1})
    assert run.status == 'failed' and 'refused by default' in run.error


@pytest.mark.parametrize('url,ok', [('https://github.com/a/b', True), ('a/b', True), ('https://github.com/a/b/tree/v1/pkgs/m', True),
                                    ('https://example.com/a/b', False), ('justname', False)])
def test_parse_github_url(url, ok):
    from app.services.models import parse_github_url
    from app.runtime.contract import PackageError
    if ok:
        assert parse_github_url(url)[:2] == ('a', 'b')
    else:
        with pytest.raises(PackageError):
            parse_github_url(url)
