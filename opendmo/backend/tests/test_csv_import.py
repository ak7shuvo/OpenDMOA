"""CSV import: detection, mapping, dry-run validation, idempotent commit."""
import pytest
from sqlalchemy import func, select

from app.models import Observation
from app.services import csv_import as ci
from app.services import datasets as dsvc


@pytest.fixture()
def ds(db):
    return dsvc.create_dataset(db, 'jaflong', 'visitor_flow', 'Gate counts')


def _validate(db, ds, text, mapping=None, **kw):
    content = text.encode(kw.pop('encoding', 'utf-8'))
    t = ci.parse_table(content, kw.pop('name', 'f.csv'))
    m = mapping or ci.suggest_mapping(t, ds.variable_defs)
    m.update(kw)
    return content, t, m, ci.validate(db, ds, t, m)


def codes(rep, level=None):
    return [i['code'] for i in rep.issues if level in (None, i['level'])]


@pytest.mark.parametrize('delim', [',', ';', '\t', '|'])
def test_delimiter_detection(delim):
    text = delim.join(['period', 'visitors', 'daily_peak']) + '\n' + delim.join(['2024-01', '100', '10']) + '\n'
    t = ci.parse_table(text.encode())
    assert t.delimiter == delim and t.columns == ['period', 'visitors', 'daily_peak'] and t.has_header


def test_encoding_bom_and_cp1252():
    assert ci.detect_encoding('﻿a,b'.encode('utf-8')) == 'utf-8-sig'
    assert ci.detect_encoding('période,visitors\n'.encode('cp1252')) == 'cp1252'
    t = ci.parse_table('﻿period,visitors\n2024-01,5\n'.encode('utf-8'))
    assert t.columns[0] == 'period'


def test_headerless_file_gets_generic_columns():
    t = ci.parse_table(b'2024-01,100\n2024-02,120\n')
    assert not t.has_header and t.columns == ['column_1', 'column_2'] and len(t.rows) == 2


def test_wide_mapping_suggestion_uses_aliases(db, ds):
    t = ci.parse_table(b'Month,Visitor Count,Hotel Occupancy,notes\n2024-01,100,50,x\n')
    m = ci.suggest_mapping(t, ds.variable_defs)
    assert m['layout'] == 'wide' and m['period_column'] == 'Month'
    assert m['columns']['Visitor Count'] == 'visitors' and m['columns']['Hotel Occupancy'] == 'occupancy_rate'
    assert m['columns']['notes'] is None


def test_long_layout_detected_and_valid(db, ds):
    text = 'period,variable,value,unit\n2024-01,visitors,100,visitors\n2024-01,occupancy_rate,55,%\n'
    _, t, m, rep = _validate(db, ds, text)
    assert m['layout'] == 'long' and rep.n_errors == 0 and len(rep.observations) == 2


def test_row_level_errors_and_warnings(db, ds):
    text = ('period,visitors,occupancy_rate,daily_peak\n'
            '2024-01,100,55,10\n'
            'not-a-date,100,55,10\n'      # period_invalid
            '2024-02,abc,140,\n'          # value_not_numeric, out_of_range, value_missing
            '2024-01,101,55,10\n'         # duplicates x3
            '2024-03,-5,10.5,7.5\n')      # out_of_range (min 0), non-integer warning
    _, t, m, rep = _validate(db, ds, text)
    errs, warns = codes(rep, 'error'), codes(rep, 'warning')
    assert 'period_invalid' in errs and 'value_not_numeric' in errs and 'out_of_range' in errs
    assert errs.count('duplicate') == 3
    assert 'value_missing' in warns and 'value_not_integer' in warns
    bad = [i for i in rep.issues if i['code'] == 'period_invalid'][0]
    assert bad['row'] == 3  # file line number


def test_unit_mismatch_and_unknown_variable(db, ds):
    text = 'period,variable,value,unit\n2024-01,occupancy_rate,55,ratio\n2024-01,mystery,1,\n'
    _, t, m, rep = _validate(db, ds, text)
    assert 'unit_mismatch' in codes(rep, 'warning') and 'variable_unknown' in codes(rep, 'error')
    _, t, m, rep = _validate(db, ds, text, create_variables=True)
    assert 'variable_new' in codes(rep, 'warning') and rep.new_variables[0]['name'] == 'mystery'


def test_outliers_flagged(db, ds):
    rows = '\n'.join(f'2024-{i:02d},{100 + i}' for i in range(1, 12)) + '\n2024-12,99999\n'
    _, t, m, rep = _validate(db, ds, 'period,visitors\n' + rows)
    assert 'outlier' in codes(rep, 'warning')
    assert [o for o in rep.observations if o['value'] == 99999][0]['quality_flag'] == 'outlier'


def test_comma_decimal_semicolon_file(db, ds):
    text = 'period;occupancy_rate\n2024-01;55,5\n'
    _, t, m, rep = _validate(db, ds, text, decimal=',')
    assert rep.observations[0]['value'] == 55.5


def test_json_paste_records(db, ds):
    content = b'{"observations":[{"period":"2024-01","variable":"visitors","value":10}]}'
    t = ci.parse_table(content, 'x.json')
    m = ci.suggest_mapping(t, ds.variable_defs)
    rep = ci.validate(db, ds, t, m)
    assert t.file_format == 'json' and m['layout'] == 'long' and rep.observations[0]['value'] == 10


def test_commit_is_idempotent(db, ds):
    text = 'period,visitors,daily_peak\n2024-01,100,10\n2024-02,120,12\n'
    content, t, m, rep = _validate(db, ds, text)
    first = ci.commit(db, ds, content, 'a.csv', t, m, rep)
    assert first['status'] == 'committed' and first['inserted'] == 4
    count = db.scalar(select(func.count(Observation.id)).where(Observation.dataset_id == ds.id))
    content, t, m, rep = _validate(db, ds, text)
    again = ci.commit(db, ds, content, 'a.csv', t, m, rep)
    assert again['status'] == 'duplicate' and again['inserted'] == 0
    assert db.scalar(select(func.count(Observation.id)).where(Observation.dataset_id == ds.id)) == count
    assert ds.provenance['last_file_hash'] == first['file_hash']
    # a different file overlapping the same cells updates instead of duplicating
    text2 = 'period,visitors,daily_peak\n2024-02,130,12\n2024-03,140,14\n'
    content, t, m, rep = _validate(db, ds, text2)
    third = ci.commit(db, ds, content, 'b.csv', t, m, rep)
    assert (third['inserted'], third['updated'], third['unchanged']) == (2, 1, 1)
    assert db.scalar(select(func.count(Observation.id)).where(Observation.dataset_id == ds.id)) == 6


def test_commit_refuses_errors_unless_skipping(db, ds):
    text = 'period,visitors\n2024-01,100\n2024-02,abc\n'
    content, t, m, rep = _validate(db, ds, text)
    with pytest.raises(ci.ImportError_):
        ci.commit(db, ds, content, 'c.csv', t, m, rep)
    res = ci.commit(db, ds, content, 'c.csv', t, m, rep, skip_invalid=True)
    assert res['inserted'] == 1 and res['skipped'] == 1


def test_archived_dataset_is_immutable(db, ds):
    ds.status = 'archived'
    db.commit()
    content, t, m, rep = _validate(db, ds, 'period,visitors\n2024-01,1\n')
    with pytest.raises(dsvc.DatasetError):
        ci.commit(db, ds, content, 'd.csv', t, m, rep)


def test_quality_score_penalises_gaps(db, ds):
    content, t, m, rep = _validate(db, ds, 'period,visitors\n2024-01,1\n2024-02,2\n2024-04,4\n')
    ci.commit(db, ds, content, 'e.csv', t, m, rep)
    q = dsvc.compute_quality(db, ds)
    assert q['n_gaps'] == 1 and q['period_gaps'] == ['2024-03']
    assert q['completeness_pct'] == 75.0 and q['level'] == 'moderate'


def test_templates_round_trip(db, ds):
    wide = ci.template_csv(ds.variable_defs, 'wide', 'monthly')
    t = ci.parse_table(wide.encode())
    m = ci.suggest_mapping(t, ds.variable_defs)
    assert m['layout'] == 'wide' and all(v for v in m['columns'].values())
    long = ci.template_csv(ds.variable_defs, 'long', 'monthly')
    assert ci.suggest_mapping(ci.parse_table(long.encode()), ds.variable_defs)['layout'] == 'long'


def test_messy_sample_file(db, ds):
    from app.seed.samples import MESSY
    t = ci.parse_table(MESSY.encode())
    m = ci.suggest_mapping(t, ds.variable_defs)
    assert t.delimiter == ';' and m['columns']['Visitor Count'] == 'visitors' and m['columns']['Hotel occupancy'] == 'occupancy_rate'
    m['columns']['Peak day'] = 'daily_peak'
    m['decimal'] = ','
    rep = ci.validate(db, ds, t, m)
    assert rep.n_errors == 1 and 'value_missing' in codes(rep, 'warning')
    jan = {o['variable']: o['value'] for o in rep.observations if o['period'] == '2025-01'}
    assert jan == {'visitors': 52340, 'daily_peak': 6120, 'occupancy_rate': 61.5}


def test_bundled_samples_are_valid(db, tmp_path):
    from app.seed.samples import write_samples
    write_samples(tmp_path)
    ds = dsvc.create_dataset(db, 'sajek', 'weather', 'Sample weather')
    t = ci.parse_table((tmp_path / 'DEMO_sajek_weather_long.csv').read_bytes())
    rep = ci.validate(db, ds, t, ci.suggest_mapping(t, ds.variable_defs))
    assert rep.n_errors == 0 and len(rep.observations) > 400
