'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { downloadText, toCsv } from '@/lib/csv';
import { fmtNum } from '@/lib/format';

export interface Column<R> {
  key: string;
  label: string;
  num?: boolean;
  render?: (row: R) => ReactNode;
  value?: (row: R) => unknown;     // sort / filter / CSV value (defaults to row[key])
  hidden?: boolean;
  filter?: boolean;                // show a select filter for distinct values
  wrap?: boolean;
}

interface Props<R> {
  columns: Column<R>[];
  rows: R[];
  rowKey: (r: R) => string;
  onRowClick?: (r: R) => void;
  selectedKey?: string | null;
  csvName?: string;
  tools?: ReactNode;
  empty?: ReactNode;
  tall?: boolean;
  searchable?: boolean;
  initialSort?: { key: string; dir: 'asc' | 'desc' };
}

export function DataTable<R extends object>({ columns, rows, rowKey, onRowClick, selectedKey, csvName, tools, empty, tall, searchable = true, initialSort }: Props<R>) {
  const [q, setQ] = useState('');
  const [sort, setSort] = useState(initialSort ?? null);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set(columns.filter((c) => c.hidden).map((c) => c.key)));
  const [filters, setFilters] = useState<Record<string, string>>({});
  const val = (c: Column<R>, r: R) => (c.value ? c.value(r) : (r as Record<string, unknown>)[c.key]);
  const visible = columns.filter((c) => !hidden.has(c.key));

  const options = useMemo(() => {
    const o: Record<string, string[]> = {};
    for (const c of columns.filter((x) => x.filter)) {
      o[c.key] = Array.from(new Set(rows.map((r) => String(val(c, r) ?? '')))).filter(Boolean).sort();
    }
    return o;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, columns]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = rows.filter((r) => Object.entries(filters).every(([k, v]) => {
      if (!v) return true;
      const c = columns.find((x) => x.key === k);
      return c ? String(val(c, r) ?? '') === v : true;
    }));
    if (needle) out = out.filter((r) => columns.some((c) => String(val(c, r) ?? '').toLowerCase().includes(needle)));
    if (sort) {
      const c = columns.find((x) => x.key === sort.key);
      if (c) {
        out = [...out].sort((a, b) => {
          const va = val(c, a), vb = val(c, b);
          const cmp = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va ?? '').localeCompare(String(vb ?? ''), undefined, { numeric: true });
          return sort.dir === 'asc' ? cmp : -cmp;
        });
      }
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, q, sort, filters, columns]);

  const exportCsv = () => {
    const cols = visible.map((c) => ({ key: c.key, label: c.label }));
    const data = shown.map((r) => Object.fromEntries(visible.map((c) => [c.key, val(c, r)])));
    downloadText(`${csvName ?? 'opendmo-table'}.csv`, toCsv(cols, data));
  };

  return (
    <div>
      <div className="table-tools">
        {searchable && <input className="input sm" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search table" style={{ width: '12rem' }} />}
        {columns.filter((c) => c.filter).map((c) => (
          <select key={c.key} className="select sm" value={filters[c.key] ?? ''} aria-label={`Filter ${c.label}`}
            onChange={(e) => setFilters((f) => ({ ...f, [c.key]: e.target.value }))}>
            <option value="">{c.label}: all</option>
            {options[c.key]?.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
        {tools}
        <span style={{ flex: 1 }} />
        <span className="tiny faint">{shown.length} / {rows.length} rows</span>
        <details style={{ position: 'relative' }}>
          <summary className="btn sm" style={{ listStyle: 'none' }}>Columns</summary>
          <div className="panel" style={{ position: 'absolute', right: 0, zIndex: 10, padding: '0.5rem', minWidth: '12rem' }}>
            {columns.map((c) => (
              <label key={c.key} className="checkbox" style={{ display: 'flex' }}>
                <input type="checkbox" checked={!hidden.has(c.key)} onChange={() => setHidden((h) => {
                  const n = new Set(h); if (n.has(c.key)) n.delete(c.key); else n.add(c.key); return n;
                })} />{c.label}
              </label>
            ))}
          </div>
        </details>
        <button className="btn sm" onClick={exportCsv} disabled={!shown.length}>CSV</button>
      </div>
      {rows.length === 0 && empty ? <div style={{ padding: '0.8rem' }}>{empty}</div> : (
        <div className={`table-wrap ${tall ? 'tall' : ''}`}>
          <table className="data">
            <thead>
              <tr>
                {visible.map((c) => (
                  <th key={c.key} className={`sortable ${c.num ? 'num' : ''}`} aria-sort={sort?.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    onClick={() => setSort((s) => (s?.key === c.key ? { key: c.key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key: c.key, dir: 'asc' }))}>
                    {c.label}{sort?.key === c.key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const k = rowKey(r);
                return (
                  <tr key={k} className={`${onRowClick ? 'clickable' : ''} ${selectedKey === k ? 'selected' : ''}`} onClick={onRowClick ? () => onRowClick(r) : undefined}>
                    {visible.map((c) => {
                      const raw = val(c, r);
                      return (
                        <td key={c.key} className={`${c.num ? 'num' : ''} ${c.wrap ? 'cell-wrap' : 'nowrap'}`}>
                          {c.render ? c.render(r) : c.num ? fmtNum(raw) : raw === null || raw === undefined ? '—' : String(raw)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
