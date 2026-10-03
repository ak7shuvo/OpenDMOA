"""CSV / JSON import pipeline.

detect  -> encoding, delimiter, header, columns, layout guess, first 50 rows, mapping suggestion
validate (dry run) -> normalised observations + row-level errors/warnings
commit  -> idempotent upsert; the raw file hash is stored in provenance

Supported layouts
  long : one row per (period, variable, value[, unit][, flag])
  wide : one row per period, one column per variable
"""
from __future__ import annotations

import codecs
import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .. import periods
from ..config import get_settings
from ..models import Dataset, ImportRecord, Observation
from ..util import new_id, norm_col, sha256_bytes
from . import datasets as dsvc

MAX_BYTES = 50 * 1024 * 1024
PREVIEW_ROWS = 50
MAX_ISSUES = 1000

PERIOD_NAMES = {'period', 'date', 'month', 'year', 'quarter', 'time', 'yearmonth', 'year_month', 'month_year', 'week', 'day'}
VARIABLE_NAMES = {'variable', 'indicator', 'metric', 'var', 'measure', 'series'}
VALUE_NAMES = {'value', 'val', 'amount', 'observation', 'obs'}
UNIT_NAMES = {'unit', 'units', 'uom'}
FLAG_NAMES = {'flag', 'quality_flag', 'quality', 'status'}
FLAGS = {'ok', 'estimated', 'missing', 'outlier'}
NULLS = {'', 'na', 'n/a', 'nan', 'null', 'none', '-', '--', '.'}


class ImportError_(ValueError):
    pass


@dataclass
class Table:
    columns: list[str]
    rows: list[list[str]]
    encoding: str = 'utf-8'
    delimiter: str = ','
    has_header: bool = True
    file_format: str = 'csv'
    first_line: int = 2          # file line number of rows[0]


@dataclass
class Report:
    issues: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    n_errors: int = 0
    n_warnings: int = 0
    new_variables: list[dict] = field(default_factory=list)

    def add(self, level: str, row: int | None, column: str | None, code: str, message: str):
        if level == 'error':
            self.n_errors += 1
        else:
            self.n_warnings += 1
        if len(self.issues) < MAX_ISSUES:
            self.issues.append({'level': level, 'row': row, 'column': column, 'code': code, 'message': message})


# ----------------------------------------------------------------------------- staging

def staging_dir() -> Path:
    d = get_settings().store('uploads') / 'staging'
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage(content: bytes, file_name: str) -> dict:
    if len(content) > MAX_BYTES:
        raise ImportError_(f'file too large ({len(content) / 1e6:.1f} MB > 50 MB)')
    if not content.strip():
        raise ImportError_('file is empty')
    token = sha256_bytes(content)
    d = staging_dir()
    (d / token).write_bytes(content)
    (d / f'{token}.name').write_text(file_name or 'upload.csv', encoding='utf-8')
    return {'token': token, 'file_name': file_name, 'size': len(content)}


def load_staged(token: str) -> tuple[bytes, str]:
    if not re.fullmatch(r'[0-9a-f]{64}', token or ''):
        raise ImportError_('invalid upload token')
    p = staging_dir() / token
    if not p.exists():
        raise ImportError_('upload expired — please upload the file again')
    name_p = staging_dir() / f'{token}.name'
    return p.read_bytes(), name_p.read_text(encoding='utf-8') if name_p.exists() else 'upload.csv'


# ----------------------------------------------------------------------------- decoding & parsing

def detect_encoding(b: bytes) -> str:
    if b.startswith(codecs.BOM_UTF8):
        return 'utf-8-sig'
    if b.startswith(codecs.BOM_UTF16_LE) or b.startswith(codecs.BOM_UTF16_BE):
        return 'utf-16'
    try:
        b.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        pass
    try:
        b.decode('cp1252')
        return 'cp1252'
    except UnicodeDecodeError:
        return 'latin-1'


def detect_delimiter(text: str) -> str:
    sample = '\n'.join(text.splitlines()[:30])
    try:
        return csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in [',', ';', '\t', '|']}
        best = max(counts, key=counts.get)
        return best if counts[best] else ','


def _is_number(s: str) -> bool:
    return parse_number(s) is not None


def parse_number(raw, decimal: str = '.') -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    s = str(raw).strip().replace(' ', '').replace(' ', '')
    if s.lower() in NULLS:
        return None
    if decimal == ',':
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '')
    s = s.rstrip('%')
    try:
        x = float(s)
    except ValueError:
        return None
    return x if x == x and x not in (float('inf'), float('-inf')) else None


def detect_header(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return True
    first, second = rows[0], rows[1]
    first_num = sum(_is_number(c) or periods.normalise(c) is not None for c in first)
    second_num = sum(_is_number(c) or periods.normalise(c) is not None for c in second)
    return first_num < second_num or first_num < len(first) / 2


def parse_json_content(text: str) -> Table:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportError_(f'invalid JSON: {exc.msg} (line {exc.lineno})') from exc
    records = payload.get('observations') if isinstance(payload, dict) and 'observations' in payload else payload
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list) or not records or not all(isinstance(r, dict) for r in records):
        raise ImportError_('JSON must be a list of objects or {"observations": [...]}')
    cols: list[str] = []
    for r in records:
        for k in r:
            if k not in cols:
                cols.append(k)
    rows = [['' if r.get(c) is None else str(r.get(c)) for c in cols] for r in records]
    return Table(columns=cols, rows=rows, encoding='utf-8', delimiter='', has_header=True, file_format='json', first_line=1)


def parse_table(content: bytes, file_name: str = '', encoding: str | None = None, delimiter: str | None = None,
                has_header: bool | None = None) -> Table:
    enc = encoding or detect_encoding(content)
    try:
        text = content.decode(enc)
    except (UnicodeDecodeError, LookupError) as exc:
        raise ImportError_(f'cannot decode file as {enc}: {exc}') from exc
    stripped = text.lstrip('﻿').lstrip()
    if file_name.lower().endswith('.json') or stripped.startswith(('[', '{')):
        t = parse_json_content(stripped)
        t.encoding = enc
        return t
    delim = delimiter or detect_delimiter(text)
    raw_rows = [r for r in csv.reader(io.StringIO(text.lstrip('﻿')), delimiter=delim)]
    # keep line numbers stable; drop fully empty rows but remember positions
    numbered = [(i + 1, r) for i, r in enumerate(raw_rows) if any(c.strip() for c in r)]
    if not numbered:
        raise ImportError_('no rows found')
    header = has_header if has_header is not None else detect_header([r for _, r in numbered[:3]])
    width = max(len(r) for _, r in numbered)
    if header:
        columns = [c.strip() or f'column_{i + 1}' for i, c in enumerate(numbered[0][1])]
        columns += [f'column_{i + 1}' for i in range(len(columns), width)]
        body = numbered[1:]
    else:
        columns = [f'column_{i + 1}' for i in range(width)]
        body = numbered
    seen: dict[str, int] = {}
    for i, c in enumerate(columns):          # de-duplicate header names
        if c in seen:
            seen[c] += 1
            columns[i] = f'{c}_{seen[c]}'
        else:
            seen[c] = 1
    rows = [[(r[i].strip() if i < len(r) else '') for i in range(len(columns))] for _, r in body]
    t = Table(columns=columns, rows=rows, encoding=enc, delimiter=delim, has_header=header, file_format='csv',
              first_line=body[0][0] if body else 2)
    t._lines = [n for n, _ in body]  # type: ignore[attr-defined]
    return t


def line_of(t: Table, idx: int) -> int:
    lines = getattr(t, '_lines', None)
    return lines[idx] if lines else t.first_line + idx


# ----------------------------------------------------------------------------- mapping suggestion

def _match_variable(col: str, defs: list[dict]) -> str | None:
    n = norm_col(col)
    n_nounit = re.sub(r'_(pct|percent|mm|kg|bdt|m|c|count)$', '', n)
    for d in defs:
        names = {norm_col(d['name']), norm_col(d.get('label', ''))} | {norm_col(a) for a in d.get('aliases', [])}
        if n in names or n_nounit in names:
            return d['name']
    return None


def suggest_mapping(t: Table, defs: list[dict]) -> dict:
    normed = {c: norm_col(c) for c in t.columns}
    find = lambda names: next((c for c, n in normed.items() if n in names), None)  # noqa: E731
    period_col = find(PERIOD_NAMES)
    if period_col is None:
        for i, c in enumerate(t.columns):
            sample = [r[i] for r in t.rows[:20] if r[i]]
            if sample and all(periods.normalise(x) for x in sample):
                period_col = c
                break
    var_col, val_col = find(VARIABLE_NAMES), find(VALUE_NAMES)
    if var_col and val_col:
        return {'layout': 'long', 'period_column': period_col, 'variable_column': var_col, 'value_column': val_col,
                'unit_column': find(UNIT_NAMES), 'flag_column': find(FLAG_NAMES), 'columns': {}, 'decimal': '.',
                'date_format': 'DMY'}
    cols = {}
    for c in t.columns:
        if c == period_col:
            continue
        if normed[c] in UNIT_NAMES or normed[c] in FLAG_NAMES:
            cols[c] = None
            continue
        cols[c] = _match_variable(c, defs) or (norm_col(c) if not defs else None)
    return {'layout': 'wide', 'period_column': period_col, 'variable_column': None, 'value_column': None,
            'unit_column': None, 'flag_column': None, 'columns': cols, 'decimal': '.', 'date_format': 'DMY'}


def detect(content: bytes, file_name: str, defs: list[dict], encoding: str | None = None,
           delimiter: str | None = None, has_header: bool | None = None) -> dict:
    t = parse_table(content, file_name, encoding, delimiter, has_header)
    return {
        'file_name': file_name, 'size': len(content), 'file_hash': sha256_bytes(content),
        'format': t.file_format, 'encoding': t.encoding, 'delimiter': t.delimiter, 'has_header': t.has_header,
        'columns': t.columns, 'n_rows': len(t.rows), 'preview': t.rows[:PREVIEW_ROWS],
        'suggested_mapping': suggest_mapping(t, defs),
    }


# ----------------------------------------------------------------------------- validation

def _cells(t: Table, mapping: dict, report: Report):
    """Yield (line, column, period_raw, variable, value_raw, unit, flag) cells according to mapping."""
    idx = {c: i for i, c in enumerate(t.columns)}
    pcol = mapping.get('period_column')
    if not pcol or pcol not in idx:
        raise ImportError_('choose the column that holds the period / date')
    if mapping.get('layout') == 'long':
        vcol, valcol = mapping.get('variable_column'), mapping.get('value_column')
        if vcol not in idx or valcol not in idx:
            raise ImportError_('long layout needs a variable column and a value column')
        ucol, fcol = mapping.get('unit_column'), mapping.get('flag_column')
        for i, r in enumerate(t.rows):
            yield (line_of(t, i), valcol, r[idx[pcol]], r[idx[vcol]].strip(), r[idx[valcol]],
                   r[idx[ucol]] if ucol in idx else None, r[idx[fcol]] if fcol in idx else None)
    else:
        colmap = {c: v for c, v in (mapping.get('columns') or {}).items() if v}
        unknown = [c for c in colmap if c not in idx]
        if unknown:
            raise ImportError_(f'mapped columns not in file: {unknown}')
        if not colmap:
            raise ImportError_('map at least one column to a variable')
        for i, r in enumerate(t.rows):
            for c, var in colmap.items():
                yield (line_of(t, i), c, r[idx[pcol]], var, r[idx[c]], None, None)


def validate(db, ds: Dataset, t: Table, mapping: dict) -> Report:
    report = Report()
    defs = {d['name']: d for d in (ds.variable_defs or [])}
    allow_new = ds.kind == 'custom' or bool(mapping.get('create_variables'))
    decimal = mapping.get('decimal', '.')
    date_format = mapping.get('date_format', 'DMY')
    seen: dict[tuple[str, str], int] = {}
    pending_new: dict[str, dict] = {}
    period_kinds: set[str] = set()

    for line, col, praw, var, vraw, unit, flag in _cells(t, mapping, report):
        period = periods.normalise(praw, date_format)
        if period is None:
            report.add('error', line, col, 'period_invalid',
                       f"period '{praw}' is not a recognised date/period (YYYY, YYYY-Qn, YYYY-MM, YYYY-MM-DD, Jan 2024, 01/2024…)")
            continue
        period_kinds.add(periods.kind(period) or '')
        if not var:
            report.add('error', line, col, 'variable_missing', 'variable name is empty')
            continue
        vname = norm_col(var) if var not in defs else var
        d = defs.get(vname)
        if d is None:
            matched = _match_variable(var, list(defs.values()))
            if matched:
                vname, d = matched, defs[matched]
        if d is None:
            if not allow_new:
                report.add('error', line, col, 'variable_unknown',
                           f"variable '{var}' is not defined for this dataset (enable 'add new variables' or map it)")
                continue
            if vname not in pending_new:
                pending_new[vname] = {'name': vname, 'label': var, 'unit': (unit or '').strip(), 'type': 'float',
                                      'min': None, 'max': None, 'required': False, 'description': 'added by import',
                                      'aliases': []}
                report.add('warning', line, col, 'variable_new', f"new variable '{vname}' will be added to the dataset definition")
            d = pending_new[vname]
        value = parse_number(vraw, decimal)
        if value is None:
            if str(vraw).strip().lower() in NULLS:
                report.add('warning', line, col, 'value_missing', f'{vname}: empty value skipped')
            else:
                report.add('error', line, col, 'value_not_numeric', f"{vname}: '{vraw}' is not a number")
            continue
        if d.get('type') == 'int' and abs(value - round(value)) > 1e-9:
            report.add('warning', line, col, 'value_not_integer', f'{vname}: expected a whole number, got {value}')
        if d.get('min') is not None and value < d['min']:
            report.add('error', line, col, 'out_of_range', f"{vname}: {value} is below the minimum {d['min']} {d.get('unit', '')}".strip())
            continue
        if d.get('max') is not None and value > d['max']:
            report.add('error', line, col, 'out_of_range', f"{vname}: {value} is above the maximum {d['max']} {d.get('unit', '')}".strip())
            continue
        if unit and d.get('unit') and norm_col(unit) != norm_col(d['unit']):
            report.add('warning', line, col, 'unit_mismatch', f"{vname}: unit '{unit}' differs from expected '{d['unit']}' (not converted)")
        qflag = (flag or 'ok').strip().lower() or 'ok'
        if qflag not in FLAGS:
            report.add('warning', line, col, 'flag_unknown', f"quality flag '{flag}' not recognised — stored as 'ok'")
            qflag = 'ok'
        key = (period, vname)
        if key in seen:
            report.add('error', line, col, 'duplicate', f'duplicate {vname} for {period} (first seen on line {seen[key]}) — ignored')
            continue
        seen[key] = line
        report.observations.append({'line': line, 'period': period, 'variable': vname, 'value': value,
                                    'unit': (unit or d.get('unit') or '').strip(), 'quality_flag': qflag})

    if len(period_kinds - {''}) > 1:
        report.add('warning', None, mapping.get('period_column'), 'mixed_periods',
                   f'mixed period granularity in file: {sorted(period_kinds)}')

    # required variables present?
    present = {o['variable'] for o in report.observations}
    for name, d in defs.items():
        if d.get('required') and name not in present:
            report.add('warning', None, None, 'required_missing', f"required variable '{name}' has no values in this file")

    # robust outliers per variable (combined with stored history for context)
    by_var: dict[str, list[int]] = {}
    for i, o in enumerate(report.observations):
        by_var.setdefault(o['variable'], []).append(i)
    for var, ids in by_var.items():
        vals = [report.observations[i]['value'] for i in ids]
        for j in dsvc.robust_outliers(vals):
            o = report.observations[ids[j]]
            if o['quality_flag'] == 'ok':
                o['quality_flag'] = 'outlier'
            report.add('warning', o['line'], None, 'outlier', f"{var} = {o['value']} for {o['period']} is a statistical outlier (|modified z| > 3.5) — flagged")

    # compare with what is stored
    existing = {(o.period, o.variable): o for o in db.scalars(select(Observation).where(Observation.dataset_id == ds.id))}
    for o in report.observations:
        cur = existing.get((o['period'], o['variable']))
        if cur is None:
            o['action'] = 'insert'
        elif cur.value == o['value'] and (cur.unit or '') == o['unit'] and cur.quality_flag == o['quality_flag']:
            o['action'] = 'unchanged'
        else:
            o['action'] = 'update'
            o['previous'] = cur.value
    report.new_variables = list(pending_new.values())
    return report


def summarise(t: Table, report: Report, extra: dict | None = None) -> dict:
    acts = {'insert': 0, 'update': 0, 'unchanged': 0}
    for o in report.observations:
        acts[o.get('action', 'insert')] += 1
    return {
        'rows_total': len(t.rows), 'valid_cells': len(report.observations),
        'errors': report.n_errors, 'warnings': report.n_warnings,
        'will_insert': acts['insert'], 'will_update': acts['update'], 'unchanged': acts['unchanged'],
        'new_variables': report.new_variables,
        'issues': report.issues, 'issues_truncated': report.n_errors + report.n_warnings > len(report.issues),
        'preview_observations': report.observations[:PREVIEW_ROWS],
        **(extra or {}),
    }


# ----------------------------------------------------------------------------- commit

def commit(db, ds: Dataset, content: bytes, file_name: str, t: Table, mapping: dict, report: Report,
           skip_invalid: bool = False, mode: str = 'upsert') -> dict:
    dsvc.ensure_mutable(ds)
    file_hash = sha256_bytes(content)
    prior = db.scalar(select(ImportRecord).where(ImportRecord.dataset_id == ds.id, ImportRecord.file_hash == file_hash))
    if prior:
        return {'status': 'duplicate', 'import_id': prior.id, 'file_hash': file_hash, 'inserted': 0, 'updated': 0,
                'unchanged': 0, 'message': f'this exact file was already imported on {prior.created_at:%Y-%m-%d %H:%M} — nothing changed'}
    if report.n_errors and not skip_invalid:
        raise ImportError_(f'{report.n_errors} error(s) found — fix the file or choose “skip invalid rows” to import the valid cells only')
    if not report.observations:
        raise ImportError_('no valid observations to import')

    imp_id = new_id('IMP')
    if report.new_variables:
        ds.variable_defs = list(ds.variable_defs or []) + report.new_variables
    existing = {(o.period, o.variable): o for o in db.scalars(select(Observation).where(Observation.dataset_id == ds.id))}
    inserted = updated = unchanged = 0
    for o in report.observations:
        cur = existing.get((o['period'], o['variable']))
        if cur is None:
            db.add(Observation(dataset_id=ds.id, destination_id=ds.destination_id, period=o['period'],
                               variable=o['variable'], value=o['value'], unit=o['unit'],
                               quality_flag=o['quality_flag'], import_id=imp_id))
            inserted += 1
        elif o.get('action') == 'unchanged' or mode == 'insert_only':
            unchanged += 1
        else:
            cur.value, cur.unit, cur.quality_flag, cur.import_id = o['value'], o['unit'], o['quality_flag'], imp_id
            updated += 1
    archive = get_settings().store('uploads') / f"{file_hash}{Path(file_name).suffix or '.csv'}"
    if not archive.exists():
        archive.write_bytes(content)
    rec = ImportRecord(id=imp_id, dataset_id=ds.id, file_name=file_name, file_hash=file_hash, file_format=t.file_format,
                       layout=mapping.get('layout', 'long'), encoding=t.encoding, delimiter=t.delimiter, mapping=mapping,
                       rows_total=len(t.rows), inserted=inserted, updated=updated, unchanged=unchanged,
                       skipped=report.n_errors, warnings=[i for i in report.issues if i['level'] == 'warning'][:200])
    db.add(rec)
    prov = dict(ds.provenance or {})
    prov['imports'] = (prov.get('imports') or []) + [{'import_id': imp_id, 'file_name': file_name, 'file_hash': file_hash,
                                                      'at': datetime.now(timezone.utc).isoformat(),
                                                      'inserted': inserted, 'updated': updated}]
    prov['last_file_hash'] = file_hash
    ds.provenance = prov
    if ds.status == 'validated' and (inserted or updated):
        ds.status = 'draft'
    db.commit()
    quality = dsvc.compute_quality(db, ds)
    return {'status': 'committed', 'import_id': imp_id, 'file_hash': file_hash, 'inserted': inserted, 'updated': updated,
            'unchanged': unchanged, 'skipped': report.n_errors, 'quality': quality}


# ----------------------------------------------------------------------------- templates & export

def template_csv(defs: list[dict], layout: str = 'wide', frequency: str = 'monthly') -> str:
    sample_periods = {'monthly': ['2025-01', '2025-02'], 'quarterly': ['2025-Q1', '2025-Q2'],
                      'yearly': ['2024', '2025'], 'daily': ['2025-01-01', '2025-01-02']}.get(frequency, ['2025-01', '2025-02'])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    if layout == 'long':
        w.writerow(['period', 'variable', 'value', 'unit'])
        for p in sample_periods:
            for d in defs:
                w.writerow([p, d['name'], '', d.get('unit', '')])
    else:
        w.writerow(['period'] + [d['name'] for d in defs])
        for p in sample_periods:
            w.writerow([p] + ['' for _ in defs])
    return buf.getvalue()


def observations_csv(rows: list[Observation] | list[dict], layout: str = 'long') -> str:
    recs = [r if isinstance(r, dict) else {'period': r.period, 'variable': r.variable, 'value': r.value,
                                           'unit': r.unit, 'quality_flag': r.quality_flag} for r in rows]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    if layout == 'wide':
        variables = sorted({r['variable'] for r in recs})
        by_period: dict[str, dict] = {}
        for r in recs:
            by_period.setdefault(r['period'], {})[r['variable']] = r['value']
        w.writerow(['period'] + variables)
        for p in sorted(by_period):
            w.writerow([p] + ['' if by_period[p].get(v) is None else by_period[p][v] for v in variables])
    else:
        w.writerow(['period', 'variable', 'value', 'unit', 'quality_flag'])
        for r in recs:
            w.writerow([r['period'], r['variable'], '' if r['value'] is None else r['value'], r.get('unit') or '',
                        r.get('quality_flag') or 'ok'])
    return buf.getvalue()
