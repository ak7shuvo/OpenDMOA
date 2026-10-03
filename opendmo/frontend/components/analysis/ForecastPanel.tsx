'use client';

import { useState } from 'react';
import { post, errMsg } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import { useApi, useApp } from '@/lib/state';
import type { Backtest, DatasetKind, ForecastPoint, Method, Run } from '@/lib/types';
import { Legend, LineChart } from '../charts/LineChart';
import { DemoBadge, EmptyState, Field, Panel } from '../ui';
import { MethodDoc } from './MethodRunner';
import { ProvenanceBlock } from './Provenance';
import { SaveScenario } from './SaveScenario';

const METHODS = [
  { id: 'forecast.seasonal_naive', label: 'Seasonal naïve', color: 'var(--chart-3)' },
  { id: 'forecast.holt_winters', label: 'Holt-Winters', color: 'var(--chart-2)' },
  { id: 'forecast.linear_trend', label: 'Linear trend', color: 'var(--chart-5)' },
];

/** Visitor-demand forecasting with hold-out back-tests. All fitting happens in the backend. */
export function ForecastPanel() {
  const { destinationId, range, toast, bump } = useApp();
  const { data: kinds } = useApi<DatasetKind[]>('/catalog/kinds');
  const { data: methods } = useApi<Method[]>('/methods?kind=forecast');
  const [kind, setKind] = useState('visitor_flow');
  const [variable, setVariable] = useState('visitors');
  const [method, setMethod] = useState('forecast.holt_winters');
  const [horizon, setHorizon] = useState('12');
  const [season, setSeason] = useState('');
  const [holdout, setHoldout] = useState('');
  const [params, setParams] = useState({ alpha: '', beta: '', gamma: '' });
  const [runs, setRuns] = useState<Run[]>([]);
  const [busy, setBusy] = useState(false);
  const [saveFor, setSaveFor] = useState<Run | null>(null);
  const kindDef = kinds?.find((k) => k.kind === kind);

  const body = (methodId: string) => ({
    method_id: methodId, destination_id: destinationId, kind, variable, start: range.start, end: range.end,
    horizon: Number(horizon) || 12, season_length: season ? Number(season) : null, holdout: holdout ? Number(holdout) : null,
    ...(methodId === 'forecast.holt_winters' ? Object.fromEntries(Object.entries(params).map(([k, v]) => [k, v === '' ? null : Number(v)])) : {}),
  });

  const runOne = async (all: boolean) => {
    setBusy(true);
    try {
      const ids = all ? METHODS.map((m) => m.id) : [method];
      const out: Run[] = [];
      for (const id of ids) out.push(await post<Run>('/forecasts', body(id)));
      setRuns(out);
      const failed = out.filter((r) => r.status === 'failed');
      if (failed.length) toast(failed.map((r) => `${r.method_name}: ${r.error}`).join(' · '), 'error');
      bump();
    } catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); }
  };

  const ok = runs.filter((r) => r.status === 'success');
  const history = runs[0]?.history ?? [];
  const meta = (id: string) => METHODS.find((m) => m.id === id)!;
  const lastHist = history[history.length - 1]?.period;

  return (
    <div className="stack">
      <Panel title="Visitor-demand forecast" sub="seasonal-naïve · Holt-Winters · linear trend — pure numpy, back-tested">
        <div className="stack">
          <div className="form-grid">
            <Field label="Dataset type" htmlFor="fc-kind">
              <select id="fc-kind" className="select" value={kind} onChange={(e) => { setKind(e.target.value); const v = kinds?.find((k) => k.kind === e.target.value)?.variables[0]?.name; if (v) setVariable(v); }}>
                {kinds?.filter((k) => k.variables.length).map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
              </select>
            </Field>
            <Field label="Variable" htmlFor="fc-var">
              <select id="fc-var" className="select" value={variable} onChange={(e) => setVariable(e.target.value)}>
                {kindDef?.variables.map((v) => <option key={v.name} value={v.name}>{v.label}</option>)}
              </select>
            </Field>
            <Field label="Method" htmlFor="fc-method">
              <select id="fc-method" className="select" value={method} onChange={(e) => setMethod(e.target.value)}>
                {METHODS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </Field>
            <Field label="Horizon (periods)" htmlFor="fc-h"><input id="fc-h" className="input" inputMode="numeric" value={horizon} onChange={(e) => setHorizon(e.target.value)} /></Field>
            <Field label="Season length" hint="blank = infer (12 monthly, 4 quarterly)" htmlFor="fc-m"><input id="fc-m" className="input" inputMode="numeric" value={season} onChange={(e) => setSeason(e.target.value)} /></Field>
            <Field label="Back-test hold-out" hint="blank = min(horizon, n/4)" htmlFor="fc-ho"><input id="fc-ho" className="input" inputMode="numeric" value={holdout} onChange={(e) => setHoldout(e.target.value)} /></Field>
            {method === 'forecast.holt_winters' && (['alpha', 'beta', 'gamma'] as const).map((k) => (
              <Field key={k} label={`${k} (blank = optimise)`} htmlFor={`fc-${k}`}>
                <input id={`fc-${k}`} className="input" inputMode="decimal" value={params[k]} onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))} />
              </Field>
            ))}
          </div>
          <div className="row">
            <button className="btn primary" onClick={() => runOne(false)} disabled={busy}>{busy ? 'Fitting…' : 'Run forecast'}</button>
            <button className="btn" onClick={() => runOne(true)} disabled={busy}>Compare all three methods</button>
            <span className="tiny faint">Uses the observed series within {range.start ?? 'all'} → {range.end ?? 'latest'}. Choose ALL in the time range for the longest history.</span>
          </div>
        </div>
      </Panel>

      {runs.length === 0 ? (
        <EmptyState title="No forecast yet">Pick a variable and run a method. Every forecast is stored as a reproducible run with its hold-out accuracy.</EmptyState>
      ) : (
        <>
          {ok.length > 0 && (
            <Panel title="Forecast" actions={runs.some((r) => r.is_demo) ? <DemoBadge /> : null}>
              <LineChart ariaLabel="Observed series and forecasts" height={260} markX={lastHist}
                series={[
                  { id: 'obs', label: 'Observed', color: 'var(--chart-1)', points: history.map((p) => ({ x: p.period, y: p.value })) },
                  ...ok.map((r) => ({ id: r.id, label: meta(r.method_id).label, color: meta(r.method_id).color, dashed: true,
                    points: ((r.outputs?.forecast as ForecastPoint[]) ?? []).map((p) => ({ x: p.period, y: p.value })) })),
                ]}
                bands={ok.length === 1 ? [{ color: 'var(--chart-band)', points: ((ok[0].outputs?.forecast as ForecastPoint[]) ?? []).map((p) => ({ x: p.period, lo: p.lo, hi: p.hi })) }] : []} />
              <Legend items={[{ label: 'Observed', color: 'var(--chart-1)' }, ...ok.map((r) => ({ label: meta(r.method_id).label, color: meta(r.method_id).color, dashed: true })), ...(ok.length === 1 ? [{ label: '95% prediction interval', color: 'var(--chart-band)' }] : [])]} />
            </Panel>
          )}
          <Panel title="Back-test accuracy (hold-out)" tight>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Method</th><th className="num">Hold-out n</th><th className="num">MAE</th><th className="num">RMSE</th><th className="num">MAPE %</th><th className="num">MASE</th><th>Fitted parameters</th><th className="num">Next period</th><th>Run</th></tr></thead>
                <tbody>
                  {runs.map((r) => {
                    const bt = r.outputs?.backtest as Backtest | undefined;
                    const fc = (r.outputs?.forecast as ForecastPoint[] | undefined)?.[0];
                    return (
                      <tr key={r.id}>
                        <td>{r.method_name}</td>
                        {r.status === 'success' && bt ? (<>
                          <td className="num">{bt.holdout}</td><td className="num">{fmtNum(bt.mae)}</td><td className="num">{fmtNum(bt.rmse)}</td>
                          <td className="num">{fmtNum(bt.mape_pct, 1)}</td><td className="num">{fmtNum(bt.mase, 2)}</td>
                          <td className="small">{Object.entries((r.outputs?.fitted_params as Record<string, unknown>) ?? {}).filter(([k]) => k !== 'in_sample_sse').map(([k, v]) => `${k}=${Array.isArray(v) ? v.join('/') || '—' : fmtNum(v, 3)}`).join(' · ')}</td>
                          <td className="num">{fc ? `${fmtNum(fc.value)} (${fc.period})` : '—'}</td>
                        </>) : <td colSpan={7} style={{ color: 'var(--risk)' }}>{r.error}</td>}
                        <td><code className="tiny">{r.id}</code></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="tiny faint" style={{ padding: '0.5rem 0.6rem' }}>Lower is better. MASE &lt; 1 beats the in-sample naïve benchmark (Hyndman &amp; Koehler, 2006).</p>
          </Panel>
          {runs.map((r) => (
            <Panel key={r.id} title={`${r.method_name} — provenance`}>
              <ProvenanceBlock run={r} onSaveScenario={setSaveFor} />
              {methods?.find((m) => m.id === r.method_id) && <details style={{ marginTop: '0.5rem' }}><summary>Method</summary><MethodDoc m={methods.find((m) => m.id === r.method_id)!} /></details>}
            </Panel>
          ))}
        </>
      )}
      {saveFor && <SaveScenario run={saveFor} onClose={() => setSaveFor(null)} />}
    </div>
  );
}
