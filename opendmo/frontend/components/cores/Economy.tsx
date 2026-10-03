'use client';

import { useApi, useApp } from '@/lib/state';
import type { Row } from '@/lib/types';
import { ForecastPanel } from '../analysis/ForecastPanel';
import { MethodRunner } from '../analysis/MethodRunner';
import { ScenarioCompare } from '../analysis/ScenarioCompare';
import { SeriesPanel } from '../analysis/SeriesPanel';
import { EntityTable } from '../registers/EntityTable';
import { Panel } from '../ui';
import { CoreFrame } from './CoreFrame';

const STAGE = { proposed: 'watch', planned: 'watch', building: 'ok', done: 'ok', stalled: 'risk' } as const;
const STAGES = ['proposed', 'planned', 'building', 'done', 'stalled'];

export function EconomyCore() {
  return (
    <CoreFrame core="economy"
      lede="Where is value created and where does it leak? Revenue signals, the Local Economic Leakage & Sustainable Tourism Impact Index, demand forecasts with back-tests, saved scenarios and the infrastructure pipeline."
      side={<PipelineSide />}
      render={(tab) => {
        switch (tab) {
          case 'leakage':
            return (<>
              <div className="callout plain small">
                <b>Leakage</b> = share of tourism revenue lost to imports and repatriated profits. <b>Local capture</b> = share spent with locally owned businesses.
                <b> LM3</b> traces three rounds of local re-spending (Sacks, 2002). The <b>STII</b> composite is a documented <b>screening indicator</b>, not a certification.
              </div>
              <SeriesPanel kind="economy" variables={['tourism_revenue_bdt', 'local_spend_bdt', 'imported_inputs_bdt']} title="Revenue, local spend and imported inputs (BDT)" />
              <MethodRunner methodId="economy.leakage_impact" title="Local Economic Leakage & Sustainable Tourism Impact Index" scenario />
              <MethodRunner methodId="economy.local_employment" />
              <MethodRunner methodId="sustainability.screen" />
            </>);
          case 'forecast':
            return <ForecastPanel />;
          case 'scenarios':
            return (<>
              <MethodRunner methodId="scenario.demand_projection" title="What-if: visitor demand projection" scenario
                intro="Base-year visitors default to the last 12 months of observed arrivals. Enter annual capacity (e.g. ECC × open days) to see when demand would exceed it." />
              <ScenarioCompare />
            </>);
          case 'infrastructure':
            return (
              <EntityTable entity="projects" title="Infrastructure pipeline" sub="proposed → planned → building → done (or stalled)"
                fields={[
                  { key: 'name', label: 'Project', required: true, wrap: true },
                  { key: 'category', label: 'Category' },
                  { key: 'stage', label: 'Stage', type: 'select', options: STAGES, status: STAGE },
                  { key: 'budget_bdt_m', label: 'Budget (BDT m)', type: 'number', num: true },
                  { key: 'start', label: 'Start', hint: 'YYYY-MM' },
                  { key: 'end', label: 'End', hint: 'YYYY-MM' },
                  { key: 'notes', label: 'Notes', type: 'textarea', inTable: false },
                ]} />
            );
          default:
            return (<>
              <SeriesPanel kind="economy" variables={['tourism_revenue_bdt']} title="Tourism revenue (BDT)" mode="bar" />
              <SeriesPanel kind="economy" variables={['avg_spend_per_visitor_bdt']} title="Average spend per visitor (BDT)" height={160} />
              <SeriesPanel kind="economy" variables={['local_employees', 'total_employees']} title="Tourism employment" height={160} />
              <MethodRunner methodId="ratio.revenue_per_visitor" intro="Revenue and visitors must cover the same period; adjust the time range or edit the inputs." />
              <MethodRunner methodId="growth.cagr" />
            </>);
        }
      }} />
  );
}

function PipelineSide() {
  const { destinationId } = useApp();
  const { data } = useApi<Row[]>(`/projects?destination_id=${destinationId}`);
  if (!data?.length) return null;
  return (
    <Panel title="Pipeline by stage">
      {STAGES.map((s) => {
        const rows = data.filter((p) => p.stage === s);
        return rows.length ? (
          <div key={s} style={{ marginBottom: '0.4rem' }}>
            <div className="label">{s} · {rows.length}</div>
            {rows.map((p) => <div key={p.id} className="small truncate" style={{ borderLeft: `2px solid var(--${STAGE[s as keyof typeof STAGE]})`, paddingLeft: '0.4rem' }}>{String(p.name)}</div>)}
          </div>
        ) : null;
      })}
    </Panel>
  );
}
