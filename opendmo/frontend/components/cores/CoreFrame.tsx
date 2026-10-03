'use client';

import type { ReactNode } from 'react';
import { qs } from '@/lib/api';
import { CHAIN, CORES } from '@/lib/nav';
import { useApi, useApp, useHashTab } from '@/lib/state';
import type { CoreId, Summary } from '@/lib/types';
import { GisPanel, type MapPoint } from '../gis/GisPanel';
import { DemoBadge, KpiStrip, Tabs } from '../ui';

export function useSummary(core?: CoreId) {
  const { destinationId, range } = useApp();
  return useApi<Summary>(destinationId ? `/destinations/${destinationId}/summary${qs({ start: range.start, end: range.end, core })}` : null);
}

export function ChainBar({ on }: { on: string[] }) {
  return <div className="chain" aria-label="Information chain">{CHAIN.map((c) => <span key={c} className={on.includes(c) ? 'on' : ''}>{c}</span>)}</div>;
}

/** Shared frame for the four cores: header, KPI strip, module tabs, GIS side panel. */
export function CoreFrame({ core, lede, render, side, points }: {
  core: CoreId; lede: ReactNode; render: (tab: string) => ReactNode; side?: ReactNode; points?: MapPoint[];
}) {
  const def = CORES.find((c) => c.id === core)!;
  const ids = def.tabs.map((t) => t.id);
  const [tab, setTab] = useHashTab(ids, ids[0]);
  const { destination } = useApp();
  const { data: summary, loading } = useSummary(core);
  return (
    <div>
      <div className="page-head">
        <div style={{ flex: 1, minWidth: '20rem' }}>
          <div className="page-num">CORE {def.num}</div>
          <h1 className="page-title">{def.name} <span className="muted" style={{ fontWeight: 400, fontSize: '1rem' }}>· {destination?.name ?? '…'}</span></h1>
          <p className="page-lede">{lede}</p>
        </div>
        <div className="stack" style={{ gap: '0.4rem', alignItems: 'flex-end' }}>
          <ChainBar on={def.chain} />
          {summary?.has_demo && <span className="row tiny faint"><DemoBadge /> includes synthetic seed-pack data</span>}
        </div>
      </div>
      {core !== 'lab' && <div style={{ marginBottom: '0.8rem' }}><KpiStrip kpis={summary?.kpis} loading={loading} /></div>}
      <Tabs tabs={def.tabs.map((t) => ({ id: t.id, label: <>{t.name}{t.roadmap && <span className="badge">roadmap</span>}</> }))} active={tab} onChange={setTab} />
      <div className={`core-layout ${core === 'lab' ? 'no-side' : ''}`}>
        <div className="stack">{render(tab)}</div>
        {core !== 'lab' && (
          <div className="stack" style={{ position: 'sticky', top: '3.6rem' }}>
            <GisPanel height={260} points={points} />
            {side}
          </div>
        )}
      </div>
    </div>
  );
}
