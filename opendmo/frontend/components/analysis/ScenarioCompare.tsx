'use client';

import { useState } from 'react';
import { del, errMsg } from '@/lib/api';
import { fmtDate, fmtNum, humanKey } from '@/lib/format';
import { useApi, useApp } from '@/lib/state';
import type { Scenario } from '@/lib/types';
import { DemoBadge, EmptyState, Panel, StatusBadge } from '../ui';

interface Compare { columns: { scenario: string; scenario_id: string; run_id: string; method: string; is_demo: boolean; inputs: Record<string, unknown>; outputs: Record<string, unknown> }[]; input_keys: string[]; output_keys: string[]; mixed_methods: boolean }

/** Saved scenarios side by side. Values are exactly those recorded in each run. */
export function ScenarioCompare() {
  const { destinationId, toast, bump } = useApp();
  const { data: scenarios } = useApi<Scenario[]>(`/scenarios?destination_id=${destinationId}`);
  const [sel, setSel] = useState<string[]>([]);
  const { data: cmp } = useApi<Compare>(sel.length ? `/scenarios/compare?ids=${sel.join(',')}` : null);
  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const cell = (v: unknown) => (v === undefined ? <span className="faint">—</span> : typeof v === 'string' && ['ok', 'watch', 'risk'].includes(v) ? <StatusBadge status={v} /> : fmtNum(v));
  return (
    <Panel title="Saved scenarios — side-by-side" sub="select two or more">
      {!scenarios?.length ? (
        <EmptyState title="No saved scenarios">Run a calculation or forecast and choose “Save as scenario”. Saved scenarios keep a link to their immutable run.</EmptyState>
      ) : (
        <div className="stack">
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th /><th>Scenario</th><th>Method</th><th>Notes</th><th>Saved</th><th /></tr></thead>
              <tbody>
                {scenarios.map((s) => (
                  <tr key={s.id} className={sel.includes(s.id) ? 'selected' : ''}>
                    <td><input type="checkbox" checked={sel.includes(s.id)} onChange={() => toggle(s.id)} aria-label={`Select ${s.name}`} /></td>
                    <td>{s.name} {s.run?.is_demo && <DemoBadge />}</td>
                    <td className="small">{s.run ? `${s.run.method_id} v${s.run.method_version}` : 'run missing'}</td>
                    <td className="small cell-wrap">{s.notes}</td>
                    <td className="small">{fmtDate(s.created_at)}</td>
                    <td><button className="btn ghost sm" onClick={async () => { try { await del(`/scenarios/${s.id}`); setSel((x) => x.filter((i) => i !== s.id)); bump(); } catch (e) { toast(errMsg(e), 'error'); } }} aria-label="Delete scenario">✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {cmp && cmp.columns.length > 0 && (
            <>
              {cmp.mixed_methods && <div className="callout small">These scenarios use different methods; only shared keys are directly comparable.</div>}
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>Variable</th>{cmp.columns.map((c) => <th key={c.scenario_id} className="num">{c.scenario}</th>)}</tr></thead>
                  <tbody>
                    <tr><td colSpan={cmp.columns.length + 1} className="label">Outputs</td></tr>
                    {cmp.output_keys.map((k) => <tr key={`o-${k}`}><td>{humanKey(k)}</td>{cmp.columns.map((c) => <td key={c.scenario_id} className="num">{cell(c.outputs[k])}</td>)}</tr>)}
                    <tr><td colSpan={cmp.columns.length + 1} className="label">Inputs / assumptions</td></tr>
                    {cmp.input_keys.map((k) => <tr key={`i-${k}`}><td>{humanKey(k)}</td>{cmp.columns.map((c) => <td key={c.scenario_id} className="num">{cell(c.inputs[k])}</td>)}</tr>)}
                    <tr><td className="faint">run</td>{cmp.columns.map((c) => <td key={c.scenario_id} className="num tiny faint">{c.run_id}</td>)}</tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </Panel>
  );
}
