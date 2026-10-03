"""Policy-brief generator (Markdown / HTML) and citation helper."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone

from .. import __version__, calculations
from ..calculations.references import ALL_REFERENCES, OPENDMO
from ..models import Destination, Run


def _fmt(v) -> str:
    if isinstance(v, float):
        return f'{v:,.2f}' if abs(v) < 1e6 else f'{v:,.0f}'
    if isinstance(v, int):
        return f'{v:,}'
    if isinstance(v, dict) and 'value' in v:
        return f"{_fmt(v['value'])} {v.get('unit', '')}".strip()
    if isinstance(v, list):
        return f'{len(v)} items'
    if isinstance(v, dict):
        return ', '.join(f'{k}={_fmt(x)}' for k, x in list(v.items())[:6])
    return str(v)


def _headline(run: Run) -> list[str]:
    out = run.outputs or {}
    if run.kind == 'forecast':
        fc = out.get('forecast') or []
        bt = out.get('backtest') or {}
        lines = []
        if fc:
            lines.append(f"Next period ({fc[0]['period']}): {_fmt(fc[0]['value'])} (95 % PI {_fmt(fc[0]['lo'])}–{_fmt(fc[0]['hi'])}); "
                         f"horizon end ({fc[-1]['period']}): {_fmt(fc[-1]['value'])}")
        if bt:
            lines.append(f"Hold-out accuracy (n={bt.get('holdout')}): MAE {_fmt(bt.get('mae'))}, RMSE {_fmt(bt.get('rmse'))}, "
                         f"MAPE {_fmt(bt.get('mape_pct'))} %")
        return lines
    return [f'{k}: {_fmt(v)}' for k, v in out.items() if k not in ('series', 'correction_factors', 'factor_scores')][:8]


def build_markdown(db, title: str, destination_id: str | None, runs: list[Run], summary: str,
                   recommendations: list[str]) -> str:
    dest = db.get(Destination, destination_id) if destination_id else None
    demo = any(r.is_demo for r in runs)
    screening = any((r.method_snapshot or {}).get('screening') for r in runs)
    now = datetime.now(timezone.utc)
    L = [f'# {title}', '']
    L.append(f"*{dest.name + ' · ' + dest.region if dest else 'Multiple destinations'} · generated {now:%Y-%m-%d %H:%M} UTC "
             f'· OpenDMO {__version__}*')
    L.append('')
    if demo:
        L += ['> **DEMO DATA** — one or more results in this brief were computed from synthetic seed-pack data. '
              'Do not cite these numbers as findings.', '']
    if screening:
        L += ['> Composite indices marked *screening* are transparent prioritisation tools, not certifications '
              'or regulatory determinations.', '']
    if summary:
        L += ['## Summary', '', summary.strip(), '']
    L += ['## Key findings', '']
    for r in runs:
        snap = r.method_snapshot or {}
        L.append(f"**{snap.get('name', r.method_id)}** (`{r.method_id}` v{r.method_version})"
                 + (' — *screening indicator*' if snap.get('screening') else '') + (' — DEMO' if r.is_demo else ''))
        L += [f'- {x}' for x in _headline(r)] + ['']
    if recommendations:
        L += ['## Recommendations', ''] + [f'{i}. {x}' for i, x in enumerate(recommendations, 1)] + ['']
    L += ['## Methods', '']
    seen = set()
    for r in runs:
        if r.method_id in seen:
            continue
        seen.add(r.method_id)
        snap = r.method_snapshot or {}
        L += [f"### {snap.get('name', r.method_id)}", '', '```', str(snap.get('formula', '')), '```', '']
        if snap.get('method'):
            L += [str(snap['method']), '']
        lim = snap.get('limitations') or []
        if lim:
            L += ['Limitations:'] + [f'- {x}' for x in lim] + ['']
    L += ['## Data & provenance', '', '| Run | Method | Dataset (version) | Data hash | Quality | Timestamp |', '|---|---|---|---|---|---|']
    for r in runs:
        q = r.data_quality or {}
        L.append(f"| `{r.id}` | {r.method_id} v{r.method_version} | {r.dataset_id or 'manual inputs'}"
                 f"{' (v' + str(r.dataset_version) + ')' if r.dataset_version else ''} | "
                 f"{(r.dataset_hash or '—')[:12]} | {q.get('score', '—')} {q.get('level', '')} | "
                 f"{r.created_at:%Y-%m-%d %H:%M} |")
    L += ['', '## References', '']
    refs = {}
    for r in runs:
        for ref in (r.method_snapshot or {}).get('references', []):
            refs[ref.get('key')] = ref.get('citation')
    refs[OPENDMO.key] = OPENDMO.citation()
    L += [f'- {c}' for c in refs.values()] + ['']
    L += ['---', f'Prepared with OpenDMO {__version__}. Every figure above can be re-run from its run id.', '']
    return '\n'.join(L)


# ----------------------------------------------------------------------------- tiny Markdown -> HTML

def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', s)
    return s


def markdown_to_html(md: str, title: str = 'OpenDMO brief') -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```'):
            j = i + 1
            block = []
            while j < len(lines) and not lines[j].startswith('```'):
                block.append(html.escape(lines[j]))
                j += 1
            out.append('<pre>' + '\n'.join(block) + '</pre>')
            i = j + 1
            continue
        if ln.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[-| ]+\|$', lines[i + 1]):
            head = [c.strip() for c in ln.strip('|').split('|')]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith('|'):
                rows.append([c.strip() for c in lines[j].strip('|').split('|')])
                j += 1
            out.append('<table><thead><tr>' + ''.join(f'<th>{_inline(h)}</th>' for h in head) + '</tr></thead><tbody>'
                       + ''.join('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in r) + '</tr>' for r in rows) + '</tbody></table>')
            i = j
            continue
        m = re.match(r'^(#{1,4}) (.*)$', ln)
        if m:
            n = len(m.group(1))
            out.append(f'<h{n}>{_inline(m.group(2))}</h{n}>')
        elif ln.startswith('> '):
            out.append(f'<blockquote>{_inline(ln[2:])}</blockquote>')
        elif re.match(r'^(- |\d+\. )', ln):
            ordered = bool(re.match(r'^\d+\. ', ln))
            items = []
            while i < len(lines) and re.match(r'^(- |\d+\. )', lines[i]):
                items.append(re.sub(r'^(- |\d+\. )', '', lines[i]))
                i += 1
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(f'<li>{_inline(x)}</li>' for x in items) + f'</{tag}>')
            continue
        elif ln.strip() == '---':
            out.append('<hr>')
        elif ln.strip():
            out.append(f'<p>{_inline(ln)}</p>')
        i += 1
    css = ('body{font-family:"JetBrains Mono",ui-monospace,monospace;max-width:860px;margin:32px auto;padding:0 16px;'
           'color:#16161A;background:#F4ECDD;line-height:1.55;font-size:14px}h1{color:#B3202A}h1,h2,h3{font-weight:600}'
           'blockquote{border-left:3px solid #B3202A;margin:12px 0;padding:6px 12px;background:#EADFCB}'
           'table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #BDB4A3;padding:4px 6px;text-align:left}'
           'pre{background:#16161A;color:#F4ECDD;padding:10px;overflow:auto;border-radius:4px}code{background:#EADFCB;padding:0 3px}'
           '@media print{body{background:#fff}}')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f'<style>{css}</style></head><body>' + '\n'.join(out) + '</body></html>')


# ----------------------------------------------------------------------------- citation

def citation_cff() -> str:
    return f"""cff-version: 1.2.0
message: "If you use OpenDMO in research, please cite it as below."
title: "OpenDMO: Open Destination Management & Analytics Platform"
version: "{__version__}"
date-released: "2026-10-03"
license: MIT
repository-code: "https://github.com/ak7shuvo/OpenDMOA"
type: software
authors:
  - name: "OpenDMO contributors"
keywords: [tourism, destination management, carrying capacity, forecasting, Bangladesh, open science]
"""


def platform_bibtex() -> str:
    return ('@software{opendmo2026,\n  author = {{OpenDMO contributors}},\n'
            '  title = {OpenDMO: Open Destination Management \\& Analytics Platform},\n'
            f'  version = {{{__version__}}},\n  year = {{2026}},\n  license = {{MIT}},\n'
            '  url = {https://github.com/ak7shuvo/OpenDMOA}\n}')


def citations() -> dict:
    methods = {}
    for m in calculations.all_methods():
        methods[m.id] = {'name': m.name, 'version': m.version, 'references': [r.key for r in m.references]}
    return {'cff': citation_cff(), 'platform_bibtex': platform_bibtex(),
            'references': [r.as_dict() for r in ALL_REFERENCES],
            'bibtex_all': '\n\n'.join([platform_bibtex()] + [r.bibtex() for r in ALL_REFERENCES]),
            'methods': methods, 'how_to_cite_run': 'Cite the platform version, the method id + version and the run id, '
                                                  'e.g. "computed with OpenDMO 2.0.0, capacity.cifuentes v2.0.0, run RUN-…".'}


def methodology_markdown() -> str:
    by_core: dict[str, list] = {}
    for m in calculations.all_methods():
        by_core.setdefault(m.core, []).append(m)
    names = {'observatory': '01 Destination Observatory', 'climate': '02 Climate & Risk', 'economy': '03 Future & Economy', 'lab': '04 Research & Policy Lab'}
    L = [f'# OpenDMO {__version__} — Methodology', '',
         '*Auto-generated from the method registry. Every method is versioned; every run stores the version it used.*', '']
    for core in ['observatory', 'climate', 'economy', 'lab']:
        if core in by_core:
            L += [f'## {names[core]}', '']
            L += [m.methodology_markdown() for m in by_core[core]]
    return '\n'.join(L)


def dumps(o) -> str:
    return json.dumps(o, indent=2, default=str)
