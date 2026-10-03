'use client';

import Link from 'next/link';
import { useState } from 'react';
import { post, put, errMsg } from '@/lib/api';
import { fmtDate, fmtNum } from '@/lib/format';
import { CORES } from '@/lib/nav';
import { useApi, useApp } from '@/lib/state';
import type { InputSource, Run } from '@/lib/types';
import { ChainBar, useSummary } from '../cores/CoreFrame';
import { GisPanel } from '../gis/GisPanel';
import { DemoBadge, KpiStrip, Panel, StatusBadge } from '../ui';

export function Overview() {
  const { meta, destination, destinationId } = useApp();
  const { data: summary, loading } = useSummary();
  const { data: runs } = useApi<Run[]>(`/runs?destination_id=${destinationId}&limit=6`);
  const onboarding = meta && !meta.settings.onboarding_complete;
  const c = summary?.counts;
  return (
    <div className="stack">
      <div className="page-head">
        <div style={{ flex: 1, minWidth: '20rem' }}>
          <div className="page-num">OVERVIEW · {destination?.region}</div>
          <h1 className="page-title">{destination?.name ?? 'OpenDMO'}</h1>
          <p className="page-lede">{destination?.description || 'Open Destination Management & Analytics Platform — local-first research workstation.'}</p>
        </div>
        <ChainBar on={['LOCATION', 'TIME']} />
      </div>
      {onboarding && <Onboarding hasData={Boolean(summary?.has_data)} />}
      {CORES.filter((x) => x.id !== 'lab').map((core) => (
        <div key={core.id}>
          <div className="row between" style={{ marginBottom: '0.35rem' }}>
            <Link href={core.route} className="label" style={{ textDecoration: 'none' }}><span style={{ color: 'var(--red-bright)' }}>{core.num}</span> {core.name.toUpperCase()} →</Link>
          </div>
          <KpiStrip kpis={summary?.kpis.filter((k) => k.core === core.id).slice(0, 6)} loading={loading} />
        </div>
      ))}
      <div className="core-layout">
        <GisPanel height={420} title="Destinations — shared spatial layer" />
        <div className="stack">
          <Panel title="Situation" actions={summary?.has_demo ? <DemoBadge /> : null}>
            <div className="result-grid">
              {[['active warnings', c?.warnings_active, c?.warnings_active ? 'risk' : 'ok'], ['open incidents', c?.incidents_open, c?.incidents_open ? 'watch' : 'ok'],
                ['readiness', c?.readiness_pct !== null && c?.readiness_pct !== undefined ? `${c.readiness_pct}%` : '—', null], ['heritage assets', c?.assets, null],
                ['pipeline projects', c?.projects, null], ['datasets', c?.datasets, null], ['mean data quality', c?.mean_quality, null], ['runs', c?.runs, null]].map(([k, v, s]) => (
                <div className="result-cell" key={String(k)}><div className="k">{k}</div><div className="v">{typeof v === 'number' ? fmtNum(v) : String(v ?? '—')} {s && <span className={`dot ${s}`} />}</div></div>
              ))}
            </div>
            <p className="tiny faint" style={{ marginTop: '0.4rem' }}>Data extent: {summary?.extent.first_period ?? '—'} → {summary?.extent.last_period ?? '—'}</p>
          </Panel>
          <Panel title="Latest runs" actions={<Link className="btn sm" href="/research-lab/#runs">All runs</Link>}>
            {!runs?.length ? <span className="small faint">No runs yet for this destination.</span> : (
              <div className="stack" style={{ gap: '0.4rem' }}>
                {runs.map((r) => (
                  <div key={r.id} className="small">
                    <div className="row between"><span>{r.method_name}</span><span className="row">{r.is_demo && <DemoBadge />}<StatusBadge status={r.status === 'success' ? 'ok' : 'risk'} label={r.status} /></span></div>
                    <div className="tiny faint truncate">{r.headline}</div>
                    <div className="tiny faint">{fmtDate(r.created_at)}</div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Onboarding({ hasData }: { hasData: boolean }) {
  const { destinations, destinationId, setDestinationId, toast, bump, reloadMeta } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const finish = async () => { try { await put('/system/settings', { onboarding_complete: true }); await reloadMeta(); } catch (e) { toast(errMsg(e), 'error'); } };
  const loadDemo = async () => {
    setBusy('demo');
    try { await post(`/system/seed-packs/${destinationId}/load`); toast('DEMO seed pack loaded — values are synthetic and badged DEMO', 'ok'); bump(); }
    catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(null); }
  };
  const firstRun = async () => {
    setBusy('run');
    try {
      const r = await post<{ inputs: Record<string, number>; sources: Record<string, InputSource> }>('/methods/capacity.cifuentes/resolve', { destination_id: destinationId });
      const ds = Array.from(new Set(Object.values(r.sources).map((s) => s.dataset_id)));
      const res = await post<Run>('/runs', { method_id: 'capacity.cifuentes', inputs: r.inputs, destination_id: destinationId, dataset_id: ds[0] ?? null, input_sources: r.sources });
      setRun(res); bump();
    } catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(null); }
  };
  const out = run?.outputs as Record<string, number | string> | undefined;
  return (
    <Panel title="Get started in three steps" actions={<button className="btn ghost sm" onClick={finish}>Skip</button>}>
      <div className="grid g3">
        <div className="stack">
          <div className="label"><span style={{ color: 'var(--red-bright)' }}>1</span> · Pick a destination</div>
          <select className="select" value={destinationId} onChange={(e) => setDestinationId(e.target.value)} aria-label="Destination">
            {destinations.map((d) => <option key={d.id} value={d.id}>{d.name} — {d.region}</option>)}
          </select>
          <span className="tiny faint">Pilots: Jaflong, Ratargul, Sajek, Bandarban. Add more in System › Control Board.</span>
        </div>
        <div className="stack">
          <div className="label"><span style={{ color: 'var(--red-bright)' }}>2</span> · Load data {hasData && <StatusBadge status="ok" label="done" />}</div>
          <div className="row">
            <button className="btn primary" onClick={loadDemo} disabled={busy !== null}>{busy === 'demo' ? 'Loading…' : 'Load DEMO data'}</button>
            <Link className="btn" href="/import/">Import your CSV</Link>
          </div>
          <span className="tiny faint">DEMO data is synthetic, always badged <DemoBadge />, and removable from the Control Board.</span>
        </div>
        <div className="stack">
          <div className="label"><span style={{ color: 'var(--red-bright)' }}>3</span> · Run your first calculation {run?.status === 'success' && <StatusBadge status="ok" label="done" />}</div>
          <div className="row">
            <button className="btn primary" onClick={firstRun} disabled={!hasData || busy !== null}>{busy === 'run' ? 'Running…' : 'Run carrying capacity'}</button>
            {run && <button className="btn" onClick={finish}>Finish</button>}
          </div>
          {run?.status === 'success' && out ? (
            <span className="small">ECC <b>{fmtNum(out.ecc as number)}</b> visits/day · utilisation {fmtNum(out.utilisation_pct as number)} % <StatusBadge status={String(out.status)} /> — <Link href="/observatory/#capacity">inspect assumptions & provenance →</Link></span>
          ) : run ? <span className="small" style={{ color: 'var(--risk)' }}>{run.error}</span> : <span className="tiny faint">Cifuentes PCC/RCC/ECC with documented default assumptions; every run is traceable.</span>}
        </div>
      </div>
    </Panel>
  );
}
