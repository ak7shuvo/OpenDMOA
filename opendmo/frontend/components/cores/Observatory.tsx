'use client';

import { MethodRunner } from '../analysis/MethodRunner';
import { SeriesPanel } from '../analysis/SeriesPanel';
import { EntityTable } from '../registers/EntityTable';
import { useApi, useApp } from '@/lib/state';
import type { Row } from '@/lib/types';
import { CoreFrame } from './CoreFrame';
import { StatusBadge } from '../ui';

const CONDITION = { good: 'ok', fair: 'watch', poor: 'risk', critical: 'risk' } as const;

export function ObservatoryCore() {
  const { destinationId } = useApp();
  const { data: assets } = useApi<Row[]>(`/assets?destination_id=${destinationId}`);
  const points = (assets ?? []).filter((a) => a.latitude != null && a.longitude != null).map((a) => ({
    id: a.id, name: String(a.name), lat: Number(a.latitude), lon: Number(a.longitude), kind: String(a.asset_type),
    status: CONDITION[String(a.condition) as keyof typeof CONDITION],
  }));
  return (
    <CoreFrame core="observatory" points={points}
      lede="Where are visitors, how crowded are sites, what is their condition and how do residents feel? Observed data, carrying capacity and the heritage asset registry for the selected destination."
      side={<AssetSide assets={assets ?? []} />}
      render={(tab) => {
        switch (tab) {
          case 'capacity':
            return (<>
              <div className="callout plain small">
                Cifuentes (1992) carrying capacity. Every parameter is an explicit, editable assumption and is stored with the run.
                Peak-day visitors are filled from the destination’s visitor-flow data for the selected range. Save variants as scenarios to compare management options.
              </div>
              <MethodRunner methodId="capacity.cifuentes" title="Destination Carrying Capacity Engine" scenario />
              <MethodRunner methodId="capacity.utilisation" title="Capacity utilisation for a period" />
            </>);
          case 'site':
            return (<>
              <SeriesPanel kind="site_condition" variables={['trail_condition', 'facilities_score']} title="Site condition scores" />
              <SeriesPanel kind="site_condition" variables={['litter_score', 'erosion_score']} title="Litter & erosion severity (0–10)" height={170} />
              <MethodRunner methodId="site.condition_index" />
              <MethodRunner methodId="ratio.waste_per_visitor" />
            </>);
          case 'sentiment':
            return (<>
              <SeriesPanel kind="community_sentiment" variables={['support_pct', 'oppose_pct', 'crowding_concern_pct', 'benefit_perception_pct']} title="Resident attitude survey (%)" />
              <MethodRunner methodId="sentiment.net_support" />
            </>);
          case 'heritage':
            return (
              <EntityTable entity="assets" title="Cultural & natural heritage asset registry" sub="condition · threats · protection status · GIS link"
                emptyText="Record heritage assets with their condition, threats and protection status. Assets with coordinates appear on the GIS panel."
                fields={[
                  { key: 'name', label: 'Asset', required: true },
                  { key: 'asset_type', label: 'Type', type: 'select', options: ['natural', 'cultural', 'mixed'] },
                  { key: 'category', label: 'Category' },
                  { key: 'condition', label: 'Condition', type: 'select', options: ['good', 'fair', 'poor', 'critical'], status: CONDITION },
                  { key: 'threats', label: 'Threats', type: 'list', wrap: true },
                  { key: 'protection_status', label: 'Protection status', wrap: true },
                  { key: 'latitude', label: 'Lat', type: 'number', num: true },
                  { key: 'longitude', label: 'Lon', type: 'number', num: true },
                  { key: 'last_assessed', label: 'Last assessed', type: 'date' },
                  { key: 'gis_layer_id', label: 'GIS layer id', inTable: false },
                  { key: 'notes', label: 'Notes', type: 'textarea', inTable: false },
                ]} />
            );
          default:
            return (<>
              <SeriesPanel kind="visitor_flow" variables={['visitors']} title="Visitor arrivals" mode="bar" />
              <SeriesPanel kind="visitor_flow" variables={['daily_peak']} title="Peak-day crowding" height={170} />
              <SeriesPanel kind="visitor_flow" variables={['occupancy_rate', 'domestic_share_pct']} title="Accommodation occupancy & domestic share (%)" height={170} />
              <MethodRunner methodId="pressure.tourism_index" intro="Capacity is entered for the same period as visitors (e.g. annual ECC × open days)." />
              <MethodRunner methodId="ratio.occupancy_rate" />
              <MethodRunner methodId="ratio.visitor_density" />
            </>);
        }
      }} />
  );
}

function AssetSide({ assets }: { assets: Row[] }) {
  if (!assets.length) return null;
  return (
    <div className="panel">
      <div className="panel-head"><span className="panel-title">Assets on map</span></div>
      <div className="panel-body stack" style={{ gap: '0.3rem' }}>
        {assets.slice(0, 8).map((a) => (
          <div key={a.id} className="row between small">
            <span className="truncate" style={{ maxWidth: '14rem' }}>{String(a.name)}</span>
            <StatusBadge status={CONDITION[String(a.condition) as keyof typeof CONDITION]} label={String(a.condition)} />
          </div>
        ))}
      </div>
    </div>
  );
}
