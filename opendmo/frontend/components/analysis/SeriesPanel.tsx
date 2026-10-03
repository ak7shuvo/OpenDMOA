'use client';

import { useState } from 'react';
import { href, qs } from '@/lib/api';
import { fmtNum } from '@/lib/format';
import { useApi, useApp } from '@/lib/state';
import type { Dataset, Series } from '@/lib/types';
import { BarChart } from '../charts/BarChart';
import { Legend, LineChart } from '../charts/LineChart';
import { DataTable } from '../ui/DataTable';
import { DemoBadge, NoDataState, Panel, SkeletonBlock } from '../ui';

const PALETTE = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)'];

/** Observed series for a dataset kind at the selected destination and time range. */
export function SeriesPanel({ kind, variables, title, mode = 'line', height = 220, lineVar, sub }: {
  kind: string; variables: string[]; title: string; mode?: 'line' | 'bar'; height?: number; lineVar?: string; sub?: string;
}) {
  const { destinationId, range } = useApp();
  const vars = [...variables, ...(lineVar ? [lineVar] : [])];
  const { data, loading } = useApi<{ dataset: Dataset | null; series: Series[] }>(
    `/series${qs({ destination_id: destinationId, kind, variables: vars.join(','), start: range.start, end: range.end })}`);
  const [table, setTable] = useState(false);
  const ds = data?.dataset;
  const hasPoints = data?.series.some((s) => s.points.length);
  const periods = Array.from(new Set((data?.series ?? []).flatMap((s) => s.points.map((p) => p.period)))).sort();
  const rows = periods.map((p) => ({ period: p, ...Object.fromEntries((data?.series ?? []).map((s) => [s.variable, s.points.find((x) => x.period === p)?.value ?? null])) }));
  const main = (data?.series ?? []).filter((s) => variables.includes(s.variable));
  const line = (data?.series ?? []).find((s) => s.variable === lineVar);

  return (
    <Panel title={title} sub={sub ?? (ds ? `${ds.name} v${ds.version}` : undefined)} actions={
      <span className="row">
        {ds?.is_demo && <DemoBadge />}
        {ds && <button className="btn sm" onClick={() => setTable((t) => !t)}>{table ? 'Chart' : 'Table'}</button>}
        {ds && <a className="btn sm" href={href(`/datasets/${ds.id}/export.csv${qs({ layout: 'wide', start: range.start, end: range.end })}`)} download>CSV</a>}
      </span>
    }>
      {loading && !data ? <SkeletonBlock /> : !hasPoints ? <NoDataState what={title.toLowerCase()} /> : table ? (
        <DataTable columns={[{ key: 'period', label: 'Period' }, ...(data?.series ?? []).map((s) => ({ key: s.variable, label: `${s.label}${s.unit ? ` (${s.unit})` : ''}`, num: true }))]}
          rows={rows} rowKey={(r) => r.period} csvName={`${destinationId}-${kind}`} />
      ) : mode === 'bar' ? (
        <>
          <BarChart ariaLabel={title} height={height} bars={periods.map((p) => ({ label: p, value: main[0]?.points.find((x) => x.period === p)?.value ?? null, color: 'var(--chart-1)' }))}
            line={line ? periods.map((p) => line.points.find((x) => x.period === p)?.value ?? null) : undefined} lineLabel={line?.label} />
          <Legend items={[{ label: `${main[0]?.label} (${main[0]?.unit})`, color: 'var(--chart-1)' }, ...(line ? [{ label: line.label, color: 'var(--chart-2)', dashed: true }] : [])]} />
        </>
      ) : (
        <>
          <LineChart ariaLabel={title} height={height} unit={main.length === 1 ? main[0].unit : ''}
            series={main.map((s, i) => ({ id: s.variable, label: s.label, color: PALETTE[i % PALETTE.length], points: s.points.map((p) => ({ x: p.period, y: p.value })) }))} />
          <Legend items={main.map((s, i) => ({ label: `${s.label}${s.unit ? ` (${s.unit})` : ''}`, color: PALETTE[i % PALETTE.length] }))} />
        </>
      )}
      {ds && !table && hasPoints && (
        <div className="tiny faint" style={{ marginTop: '0.3rem' }}>
          {periods.length} periods · {periods[0]} → {periods[periods.length - 1]} · quality {fmtNum(ds.quality_score)} / 100 · source: {ds.id}
        </div>
      )}
    </Panel>
  );
}
