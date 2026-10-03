'use client';

import { useState } from 'react';
import { patch, post, del, errMsg } from '@/lib/api';
import { fmtDate } from '@/lib/format';
import { useApi, useApp } from '@/lib/state';
import type { Row } from '@/lib/types';
import { MethodRunner } from '../analysis/MethodRunner';
import { SeriesPanel } from '../analysis/SeriesPanel';
import { EntityTable } from '../registers/EntityTable';
import { DemoBadge, EmptyState, Panel, StatusBadge } from '../ui';
import { CoreFrame, useSummary } from './CoreFrame';

const LEVEL = { advisory: 'ok', watch: 'watch', warning: 'risk', emergency: 'risk' } as const;
const SEVERITY = { minor: 'ok', moderate: 'watch', major: 'risk', critical: 'risk' } as const;

export function ClimateCore() {
  const { destinationId, destination } = useApp();
  const { data: warnings } = useApi<Row[]>(`/warnings?destination_id=${destinationId}`);
  const active = (warnings ?? []).filter((w) => w.active);
  const points = destination?.latitude != null && active.length ? [{ id: 'w', name: `${active.length} active warning(s)`, lat: destination.latitude + 0.05, lon: destination.longitude! + 0.05, status: 'risk', kind: 'warning' }] : [];
  return (
    <CoreFrame core="climate" points={points}
      lede="What is changing and what is at risk? Weather and hydrology observations, flood and landslide susceptibility screens, ecosystem stress and the crisis & disaster resilience command view."
      side={<WarningSide warnings={active} />}
      render={(tab) => {
        switch (tab) {
          case 'hazards':
            return (<>
              <div className="callout plain small">Susceptibility screens are transparent weighted overlays for prioritising field checks. They are <b>screening indicators</b>, not hazard maps or geotechnical assessments.</div>
              <SeriesPanel kind="hazard_factors" variables={['rainfall_72h_mm']} title="Maximum 72-hour rainfall" mode="bar" />
              <SeriesPanel kind="hazard_factors" variables={['landslide_events', 'flood_days']} title="Landslide events & days above danger level" height={160} />
              <MethodRunner methodId="hazard.landslide_susceptibility" scenario />
              <MethodRunner methodId="hazard.flood_susceptibility" scenario />
            </>);
          case 'ecosystem':
            return (<>
              <SeriesPanel kind="ecosystem" variables={['forest_cover_pct', 'water_quality_index']} title="Forest cover (%) & water quality index" />
              <SeriesPanel kind="ecosystem" variables={['ndvi', 'ndvi_anomaly']} title="Vegetation greenness (NDVI)" height={160} />
              <MethodRunner methodId="ecosystem.stress_index" />
            </>);
          case 'resilience':
            return <Resilience />;
          default:
            return (<>
              <SeriesPanel kind="weather" variables={['rainfall_mm']} lineVar="rainfall_normal_mm" title="Monthly rainfall vs normal (mm)" mode="bar" />
              <SeriesPanel kind="weather" variables={['temp_mean_c']} title="Mean temperature (°C)" height={160} />
              <SeriesPanel kind="weather" variables={['river_stage_m']} title="River stage — monthly maximum (m)" height={160} />
              <MethodRunner methodId="climate.anomaly" intro="Defaults to rainfall in the selected range vs the sum of the monthly normals." />
            </>);
        }
      }} />
  );
}

function WarningSide({ warnings }: { warnings: Row[] }) {
  return (
    <Panel title="Early warnings" sub={`${warnings.length} active`}>
      {!warnings.length ? <span className="small faint">No active warnings recorded for this destination.</span> : (
        <div className="stack" style={{ gap: '0.5rem' }}>
          {warnings.map((w) => (
            <div key={w.id} className="small" style={{ borderLeft: `2px solid var(--${LEVEL[String(w.level) as keyof typeof LEVEL]})`, paddingLeft: '0.5rem' }}>
              <div className="row between"><b>{String(w.hazard)}</b><span className="row"><StatusBadge status={LEVEL[String(w.level) as keyof typeof LEVEL]} label={String(w.level)} />{Boolean(w.is_demo) && <DemoBadge />}</span></div>
              <div className="muted">{String(w.message)}</div>
              <div className="tiny faint">{String(w.issued_at)} → {String(w.valid_until || 'open')} · {String(w.source)}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function Resilience() {
  const { destinationId, toast, bump } = useApp();
  const { data: items } = useApi<Row[]>(`/readiness?destination_id=${destinationId}`);
  const { data: summary } = useSummary('climate');
  const [newItem, setNewItem] = useState({ category: 'Response', item: '' });
  const toggle = async (r: Row) => { try { await patch(`/readiness/${r.id}`, { done: !r.done }); bump(); } catch (e) { toast(errMsg(e), 'error'); } };
  const add = async () => {
    if (!newItem.item.trim()) return;
    try { await post('/readiness', { ...newItem, destination_id: destinationId }); setNewItem({ ...newItem, item: '' }); bump(); } catch (e) { toast(errMsg(e), 'error'); }
  };
  const groups = Array.from(new Set((items ?? []).map((i) => String(i.category))));
  const done = (items ?? []).filter((i) => i.done).length;
  const crit = (items ?? []).filter((i) => !i.done && /early warning|evacuation/i.test(String(i.category))).length;
  return (
    <>
      <div className="grid g3">
        <div className="panel panel-body"><div className="label">Active warnings</div><div className="kpi-value">{summary?.counts.warnings_active ?? '—'}</div></div>
        <div className="panel panel-body"><div className="label">Open incidents</div><div className="kpi-value">{summary?.counts.incidents_open ?? '—'}</div></div>
        <div className="panel panel-body"><div className="label">Checklist complete</div><div className="kpi-value">{summary?.counts.readiness_pct ?? '—'}<span className="kpi-unit">%</span></div></div>
      </div>
      <EntityTable entity="warnings" title="Early warnings" sub="advisory · watch · warning · emergency"
        fields={[
          { key: 'hazard', label: 'Hazard', required: true },
          { key: 'level', label: 'Level', type: 'select', options: ['advisory', 'watch', 'warning', 'emergency'], status: LEVEL },
          { key: 'issued_at', label: 'Issued', type: 'datetime', required: true },
          { key: 'valid_until', label: 'Valid until', type: 'datetime' },
          { key: 'message', label: 'Message', type: 'textarea', wrap: true },
          { key: 'source', label: 'Source' },
          { key: 'active', label: 'Active', type: 'bool' },
        ]} />
      <EntityTable entity="incidents" title="Incident log"
        fields={[
          { key: 'occurred_at', label: 'Date', type: 'date', required: true },
          { key: 'hazard', label: 'Hazard / type', required: true },
          { key: 'severity', label: 'Severity', type: 'select', options: ['minor', 'moderate', 'major', 'critical'], status: SEVERITY },
          { key: 'status', label: 'Status', type: 'select', options: ['open', 'monitoring', 'closed'] },
          { key: 'description', label: 'Description', type: 'textarea', wrap: true },
          { key: 'response', label: 'Response', type: 'textarea', wrap: true },
        ]} />
      <Panel title="Response-readiness checklist" sub={`${done} / ${items?.length ?? 0} done`}>
        {!items?.length ? <EmptyState title="No checklist yet">Add items below, or load the DEMO pack for a 12-item template.</EmptyState> : groups.map((g) => (
          <div key={g} style={{ marginBottom: '0.6rem' }}>
            <div className="label">{g}</div>
            <ul className="checklist">
              {items.filter((i) => String(i.category) === g).map((i) => (
                <li key={i.id}>
                  <input type="checkbox" checked={Boolean(i.done)} onChange={() => toggle(i)} aria-label={String(i.item)} />
                  <span style={{ flex: 1, textDecoration: i.done ? 'line-through' : undefined, color: i.done ? 'var(--faint)' : undefined }}>{String(i.item)}</span>
                  {Boolean(i.is_demo) && <DemoBadge />}
                  <span className="tiny faint">{fmtDate(String(i.updated_at), false)}</span>
                  <button className="btn ghost sm" onClick={async () => { await del(`/readiness/${i.id}`); bump(); }} aria-label="Remove item">✕</button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="row" style={{ marginTop: '0.4rem' }}>
          <select className="select sm" value={newItem.category} onChange={(e) => setNewItem({ ...newItem, category: e.target.value })} aria-label="Category">
            {['Early warning', 'Evacuation', 'Response', 'Communication', 'Recovery', 'Coordination'].map((c) => <option key={c}>{c}</option>)}
          </select>
          <input className="input sm" style={{ flex: 1, minWidth: '14rem' }} placeholder="New checklist item…" value={newItem.item} onChange={(e) => setNewItem({ ...newItem, item: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && add()} />
          <button className="btn sm" onClick={add}>Add</button>
        </div>
      </Panel>
      <MethodRunner methodId="resilience.readiness" title="Record readiness score (with provenance)"
        intro="Counts are taken from the checklist above; open Early-warning / Evacuation items are treated as critical."
        inputOverrides={{ items_done: done, items_total: items?.length || 1, critical_open: crit }} />
    </>
  );
}
