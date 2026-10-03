'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { post, errMsg } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import { useApi, useApp } from '@/lib/state';
import type { InputSource, Method, Param, Run } from '@/lib/types';
import { DemoBadge, ErrorNote, Panel, ScreeningBadge, SkeletonBlock } from '../ui';
import { ProvenanceBlock, ResultView } from './Provenance';
import { SaveScenario } from './SaveScenario';

type Factor = { name: string; limiting: number | string; total: number | string; unit?: string };
type Values = Record<string, string | Factor[]>;

function initialValues(m: Method): Values {
  const v: Values = {};
  for (const p of m.inputs) {
    if (p.type === 'series') continue;
    if (p.type === 'factors') v[p.name] = ((p.default as Factor[]) ?? []).map((f) => ({ ...f }));
    else v[p.name] = p.default === null || p.default === undefined ? '' : String(p.default);
  }
  return v;
}

function FactorEditor({ value, onChange }: { value: Factor[]; onChange: (f: Factor[]) => void }) {
  const set = (i: number, k: keyof Factor, v: string) => onChange(value.map((f, j) => (j === i ? { ...f, [k]: v } : f)));
  return (
    <div className="table-wrap" style={{ maxHeight: 'none' }}>
      <table className="data">
        <thead><tr><th>Limiting factor</th><th className="num">Limiting magnitude (Ml)</th><th className="num">Total magnitude (Mt)</th><th>Unit</th><th /></tr></thead>
        <tbody>
          {value.map((f, i) => (
            <tr key={i}>
              <td><input className="input sm" style={{ width: '100%' }} value={f.name} onChange={(e) => set(i, 'name', e.target.value)} aria-label="Factor name" /></td>
              <td className="num"><input className="input sm" style={{ width: '7rem' }} inputMode="decimal" value={String(f.limiting)} onChange={(e) => set(i, 'limiting', e.target.value)} aria-label="Limiting magnitude" /></td>
              <td className="num"><input className="input sm" style={{ width: '7rem' }} inputMode="decimal" value={String(f.total)} onChange={(e) => set(i, 'total', e.target.value)} aria-label="Total magnitude" /></td>
              <td><input className="input sm" style={{ width: '5rem' }} value={f.unit ?? ''} onChange={(e) => set(i, 'unit', e.target.value)} aria-label="Unit" /></td>
              <td><button className="btn ghost sm" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label="Remove factor">✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="btn sm" style={{ margin: '0.4rem' }} onClick={() => onChange([...value, { name: 'New factor', limiting: 0, total: 365, unit: 'days' }])}>+ Add factor</button>
    </div>
  );
}

export function MethodDoc({ m }: { m: Method }) {
  return (
    <div className="stack" style={{ gap: '0.5rem' }}>
      <pre className="formula">{m.formula}</pre>
      <p className="small muted">{m.method}</p>
      {Object.keys(m.weights).length > 0 && <p className="small"><span className="faint">Weights:</span> {Object.entries(m.weights).map(([k, v]) => `${k} ${v}`).join(' · ')}</p>}
      {m.limitations.length > 0 && <ul className="small muted" style={{ margin: 0, paddingLeft: '1.1rem' }}>{m.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
      {m.references.length > 0 && <div className="tiny faint">{m.references.map((r) => <div key={r.key}>{r.citation}</div>)}</div>}
    </div>
  );
}

/** Schema-driven runner for any registered calculation. The backend validates, computes and records provenance. */
export function MethodRunner({ methodId, title, intro, onResult, scenario = false, children, inputOverrides }: {
  methodId: string; title?: string; intro?: ReactNode; onResult?: (r: Run) => void; scenario?: boolean; children?: ReactNode;
  inputOverrides?: Record<string, string | number>;
}) {
  const { destinationId, range, toast, bump } = useApp();
  const { data: m, error } = useApi<Method>(`/methods/${methodId}`);
  const [values, setValues] = useState<Values>({});
  const [sources, setSources] = useState<Record<string, InputSource>>({});
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveFor, setSaveFor] = useState<Run | null>(null);

  const resolve = async (base?: Values) => {
    if (!m) return;
    try {
      const r = await post<{ inputs: Record<string, number>; sources: Record<string, InputSource> }>(`/methods/${m.id}/resolve`, { destination_id: destinationId, start: range.start, end: range.end });
      const next: Values = { ...(base ?? values) };
      for (const [k, v] of Object.entries(r.inputs)) next[k] = String(v);
      for (const [k, v] of Object.entries(inputOverrides ?? {})) next[k] = String(v);
      setValues(next);
      setSources(r.sources);
    } catch (e) { toast(errMsg(e), 'error'); }
  };

  useEffect(() => {
    if (!m) return;
    const init = initialValues(m);
    setRun(null);
    void resolve(init);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m, destinationId, range.start, range.end, JSON.stringify(inputOverrides ?? {})]);

  const params = useMemo(() => (m?.inputs ?? []).filter((p) => p.type !== 'series'), [m]);

  const execute = async () => {
    if (!m) return;
    setBusy(true);
    const inputs: Record<string, unknown> = {};
    for (const p of params) {
      const v = values[p.name];
      if (p.type === 'factors') inputs[p.name] = (v as Factor[]).map((f) => ({ name: f.name, limiting: Number(f.limiting), total: Number(f.total), unit: f.unit }));
      else if (v !== '' && v !== undefined) inputs[p.name] = Number(v);
    }
    const usedSources = Object.fromEntries(Object.entries(sources).filter(([k]) => String(values[k]) === String(inputs[k])));
    const dsIds = Array.from(new Set(Object.values(usedSources).map((s) => s.dataset_id)));
    try {
      const r = await post<Run>('/runs', { method_id: m.id, inputs, destination_id: destinationId, dataset_id: dsIds.length === 1 ? dsIds[0] : null, input_sources: usedSources });
      setRun(r);
      onResult?.(r);
      bump();
      if (r.status === 'failed') toast(`Run failed: ${r.error}`, 'error');
    } catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); }
  };

  if (error) return <ErrorNote error={error} />;
  if (!m) return <Panel title={title ?? 'Loading method…'}><SkeletonBlock /></Panel>;
  const anyDemo = Object.values(sources).some((s) => s.is_demo);

  return (
    <Panel title={title ?? m.name} sub={`${m.id} v${m.version}`} actions={<span className="row">{m.screening && <ScreeningBadge />}{anyDemo && <DemoBadge />}{!m.enabled && <span className="badge risk">disabled</span>}</span>}>
      <div className="stack">
        {intro && <div className="small muted">{intro}</div>}
        {m.screening && <div className="callout plain small">{m.label}. {m.summary}</div>}
        <div className="form-grid">
          {params.filter((p) => p.type !== 'factors').map((p) => <ParamInput key={p.name} p={p} value={String(values[p.name] ?? '')} source={sources[p.name]}
            onChange={(v) => setValues((s) => ({ ...s, [p.name]: v }))} />)}
        </div>
        {params.filter((p) => p.type === 'factors').map((p) => (
          <div key={p.name} className="stack" style={{ gap: '0.3rem' }}>
            <span className="label">{p.label} — Cf = Ml / Mt; RCC multiplies Π(1 − Cf)</span>
            <FactorEditor value={(values[p.name] as Factor[]) ?? []} onChange={(f) => setValues((s) => ({ ...s, [p.name]: f }))} />
          </div>
        ))}
        <div className="row">
          <button className="btn primary" onClick={execute} disabled={busy || !m.enabled}>{busy ? 'Running…' : 'Run calculation'}</button>
          <button className="btn" onClick={() => resolve()} title="Fill inputs from this destination's datasets for the selected time range">Fill from data</button>
          <button className="btn ghost" onClick={() => { setValues(initialValues(m)); setSources({}); }}>Reset to defaults</button>
          <span className="tiny faint">Inputs marked ⛁ came from datasets for {range.start ?? 'all'} → {range.end ?? 'latest'}; edit any value before running.</span>
        </div>
        {children}
        {run && (
          <div className="stack" style={{ borderTop: '1px solid var(--line)', paddingTop: '0.7rem' }}>
            {run.status === 'success' ? <ResultView outputs={run.outputs ?? {}} spec={m.outputs} /> : <ErrorNote error={run.error} />}
            <ProvenanceBlock run={run} onRerun={setRun} onSaveScenario={scenario ? setSaveFor : undefined} />
          </div>
        )}
        <details>
          <summary>Method, assumptions & references</summary>
          <MethodDoc m={m} />
        </details>
      </div>
      {saveFor && <SaveScenario run={saveFor} onClose={() => setSaveFor(null)} />}
    </Panel>
  );
}

function ParamInput({ p, value, source, onChange }: { p: Param; value: string; source?: InputSource; onChange: (v: string) => void }) {
  const id = `in-${p.name}`;
  const rng = p.min !== null || p.max !== null ? `[${p.min ?? '−∞'} … ${p.max ?? '∞'}]` : '';
  return (
    <div className="field">
      <label htmlFor={id} title={p.description}>{source ? '⛁ ' : ''}{p.label}{p.required ? '' : ' (optional)'}</label>
      <input id={id} className="input" inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} placeholder={p.default !== null && p.default !== undefined ? String(p.default) : ''} />
      <span className="hint">{p.unit} {rng}{source ? ` · ${source.aggregation} of ${source.variable}, n=${source.n}${source.is_demo ? ' · DEMO' : ''}` : ''}{!source && p.source ? ' · no data found' : ''}</span>
    </div>
  );
}

export function fmtInputs(i: Record<string, unknown>) {
  return Object.entries(i).filter(([, v]) => !Array.isArray(v)).map(([k, v]) => `${k}=${fmtNum(v)}`).join(', ');
}
