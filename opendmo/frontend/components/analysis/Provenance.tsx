'use client';

import { useState } from 'react';
import { href, post, errMsg } from '@/lib/api';
import { fmtDate, fmtNum, humanKey, shortHash } from '@/lib/format';
import { useApp } from '@/lib/state';
import type { Run } from '@/lib/types';
import { LineChart } from '../charts/LineChart';
import { HBar } from '../charts/BarChart';
import { DemoBadge, Kv, ScreeningBadge, StatusBadge } from '../ui';

type Out = { name: string; label: string; unit: string };

function isStatusKey(k: string) { return k === 'status'; }

/** Generic display of a run's outputs. Values are rendered exactly as the backend computed them. */
export function ResultView({ outputs, spec }: { outputs: Record<string, unknown>; spec?: Out[] }) {
  const labels = Object.fromEntries((spec ?? []).map((o) => [o.name, o]));
  const scalars = Object.entries(outputs).filter(([, v]) => v === null || ['number', 'string', 'boolean'].includes(typeof v) || (typeof v === 'object' && v !== null && 'value' in (v as object)));
  const complex = Object.entries(outputs).filter(([k]) => !scalars.some(([s]) => s === k));
  return (
    <div className="stack">
      <div className="result-grid">
        {scalars.map(([k, v]) => {
          const o = labels[k];
          const val = typeof v === 'object' && v !== null && 'value' in (v as object) ? (v as { value: unknown; unit?: string }) : null;
          return (
            <div className="result-cell" key={k}>
              <div className="k" title={o?.label ?? k}>{o?.label ?? humanKey(k)}</div>
              <div className="v">
                {isStatusKey(k) ? <StatusBadge status={String(v)} /> : val ? <>{fmtNum(val.value)} <span className="kpi-unit">{val.unit}</span></> : <>{fmtNum(v)} <span className="kpi-unit">{o?.unit}</span></>}
              </div>
            </div>
          );
        })}
      </div>
      {complex.map(([k, v]) => <ComplexOutput key={k} name={labels[k]?.label ?? humanKey(k)} value={v} />)}
    </div>
  );
}

function ComplexOutput({ name, value }: { name: string; value: unknown }) {
  if (Array.isArray(value) && value.length && typeof value[0] === 'object' && value[0] && 'period' in value[0] && 'value' in value[0]) {
    const pts = value as { period: string; value: number }[];
    return (
      <div>
        <div className="label">{name}</div>
        <LineChart ariaLabel={name} height={150} series={[{ id: 's', label: name, color: 'var(--chart-2)', points: pts.map((p) => ({ x: p.period, y: p.value })) }]} />
      </div>
    );
  }
  if (Array.isArray(value) && value.length && typeof value[0] === 'object') {
    const keys = Object.keys(value[0] as object);
    return (
      <div>
        <div className="label">{name}</div>
        <div className="table-wrap"><table className="data"><thead><tr>{keys.map((k) => <th key={k}>{humanKey(k)}</th>)}</tr></thead>
          <tbody>{(value as Record<string, unknown>[]).map((r, i) => <tr key={i}>{keys.map((k) => <td key={k}>{fmtNum(r[k])}</td>)}</tr>)}</tbody></table></div>
      </div>
    );
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.every(([, v]) => typeof v === 'number' && v >= 0 && v <= 1)) {
      return <div><div className="label">{name} (0–1)</div>{entries.map(([k, v]) => <HBar key={k} label={humanKey(k)} value={v as number} max={1} right={fmtNum(v as number, 3)} />)}</div>;
    }
    return <div><div className="label">{name}</div><Kv items={entries.map(([k, v]) => [humanKey(k), typeof v === 'object' ? JSON.stringify(v) : fmtNum(v)])} /></div>;
  }
  return null;
}

/** Full traceability block: data, variables, method+version, parameters, software, timestamp, quality. */
export function ProvenanceBlock({ run, onRerun, onSaveScenario }: { run: Run; onRerun?: (r: Run) => void; onSaveScenario?: (r: Run) => void }) {
  const { toast, bump } = useApp();
  const [busy, setBusy] = useState(false);
  const p = run.provenance;
  const sources = p?.data.input_sources ?? {};
  const rerun = async () => {
    setBusy(true);
    try {
      const r = await post<Run>(`/runs/${run.id}/rerun`);
      toast(r.reproduced ? `Re-run ${r.id}: identical result reproduced` : `Re-run ${r.id}: result differs${r.method_version_changed ? ' (method version changed)' : ''}`, r.reproduced ? 'ok' : 'warn');
      onRerun?.(r);
      bump();
    } catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); }
  };
  return (
    <div className="stack" style={{ gap: '0.5rem' }}>
      <div className="row between">
        <span className="row">
          <span className="label">PROVENANCE</span>
          {run.is_demo && <DemoBadge />}
          {run.screening && <ScreeningBadge />}
          <StatusBadge status={run.status === 'success' ? 'ok' : 'risk'} label={run.status} />
        </span>
        <span className="row">
          {onSaveScenario && run.status === 'success' && <button className="btn sm" onClick={() => onSaveScenario(run)}>Save as scenario</button>}
          <button className="btn sm" onClick={rerun} disabled={busy}>{busy ? 'Re-running…' : 'Re-run'}</button>
          <a className="btn sm" href={href(`/runs/${run.id}/bundle.zip`)} download>Run bundle (.zip)</a>
          <a className="btn sm" href={href(`/runs/${run.id}/export.json`)} download>JSON</a>
          <a className="btn sm" href={href(`/runs/${run.id}/export.csv`)} download>CSV</a>
        </span>
      </div>
      <Kv items={[
        ['run', <code key="r">{run.id}</code>],
        ['method', `${run.method_name} — ${run.method_id} v${run.method_version}`],
        ['data', run.dataset_id ? `${run.dataset_id} (v${run.dataset_version}) · hash ${shortHash(run.dataset_hash)}` : Object.keys(sources).length ? 'resolved from datasets (below)' : 'manual inputs'],
        ...Object.entries(sources).map(([k, s]): [string, string] => [`  ↳ ${k}`, `${s.aggregation}(${s.variable}) over ${s.periods.join(' → ')} · n=${s.n} · ${s.dataset_id} v${s.dataset_version}${s.is_demo ? ' · DEMO' : ''}`]),
        ['quality', p?.quality?.score !== undefined && p?.quality?.score !== null ? `${fmtNum(p.quality.score)} / 100 (${p.quality.level})` : '—'],
        ['software', `OpenDMO ${run.software_version}`],
        ['timestamp', fmtDate(run.created_at)],
        ...(run.rerun_of ? [['re-run of', run.rerun_of] as [string, string]] : []),
        ...(run.error ? [['error', <span key="e" style={{ color: 'var(--risk)' }}>{run.error}</span>] as [string, React.ReactNode]] : []),
      ]} />
      <details>
        <summary>Exact inputs & parameters</summary>
        <pre className="formula">{JSON.stringify({ inputs: run.inputs, parameters: run.parameters }, null, 2)}</pre>
      </details>
    </div>
  );
}
