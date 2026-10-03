'use client';

import { useMemo, useRef, useState } from 'react';
import { patch, upload, errMsg } from '@/lib/api';
import { useApi, useApp } from '@/lib/state';
import type { GeoJSON, GisLayer } from '@/lib/types';
import { DemoBadge, Panel } from '../ui';

export interface MapPoint { id: string; name: string; lat: number; lon: number; status?: string; kind?: string }

type Geom = { type: string; coordinates: unknown };
type Pos = [number, number];

/** Offline schematic map: bundled GeoJSON basemap + local layers, equirectangular projection. Never loads remote tiles. */
export function GisPanel({ points = [], title = 'GIS — shared spatial layer', height = 300, compact }: {
  points?: MapPoint[]; title?: string; height?: number; compact?: boolean;
}) {
  const { destinations, destinationId, setDestinationId, destination, toast, bump } = useApp();
  const { data: basemap } = useApi<GeoJSON>('/gis/basemap');
  const { data: layers, setData: setLayers } = useApi<GisLayer[]>(`/gis/layers?destination_id=${destinationId}`);
  const [zoom, setZoom] = useState<'region' | 'site'>('region');
  const [cursor, setCursor] = useState<Pos | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const bbox = useMemo(() => {
    if (zoom === 'site' && destination?.latitude != null && destination.longitude != null) {
      const d = 0.18;
      return { minLon: destination.longitude - d, maxLon: destination.longitude + d, minLat: destination.latitude - d, maxLat: destination.latitude + d };
    }
    const lats = destinations.map((d) => d.latitude).filter((x): x is number => x != null);
    const lons = destinations.map((d) => d.longitude).filter((x): x is number => x != null);
    return {
      minLon: Math.min(90.2, ...lons) - 0.3, maxLon: Math.max(92.8, ...lons) + 0.3,
      minLat: Math.min(21.3, ...lats) - 0.3, maxLat: Math.max(25.4, ...lats) + 0.3,
    };
  }, [zoom, destination, destinations]);

  const W = 1000;
  const kx = Math.cos((((bbox.minLat + bbox.maxLat) / 2) * Math.PI) / 180);
  const H = Math.round((W * (bbox.maxLat - bbox.minLat)) / ((bbox.maxLon - bbox.minLon) * kx));
  const P = (lon: number, lat: number): Pos => [((lon - bbox.minLon) / (bbox.maxLon - bbox.minLon)) * W, ((bbox.maxLat - lat) / (bbox.maxLat - bbox.minLat)) * H];
  const ring = (r: Pos[]) => r.map((c, i) => `${i ? 'L' : 'M'}${P(c[0], c[1]).map((v) => v.toFixed(1)).join(',')}`).join(' ');
  const pathFor = (g: Geom): string => {
    const c = g.coordinates as never;
    switch (g.type) {
      case 'Polygon': return (c as Pos[][]).map((r) => `${ring(r)} Z`).join(' ');
      case 'MultiPolygon': return (c as Pos[][][]).flatMap((p) => p.map((r) => `${ring(r)} Z`)).join(' ');
      case 'LineString': return ring(c as Pos[]);
      case 'MultiLineString': return (c as Pos[][]).map(ring).join(' ');
      default: return '';
    }
  };
  const pointsOf = (g: Geom): Pos[] => (g.type === 'Point' ? [g.coordinates as Pos] : g.type === 'MultiPoint' ? (g.coordinates as Pos[]) : []);
  const sw = 1000 / 600;

  const toggle = async (l: GisLayer) => {
    setLayers((ls) => ls?.map((x) => (x.id === l.id ? { ...x, visible: !x.visible } : x)) ?? null);
    try { await patch(`/gis/layers/${l.id}`, { visible: !l.visible }); } catch (e) { toast(errMsg(e), 'error'); }
  };
  const onUpload = async (f: File | undefined) => {
    if (!f) return;
    const form = new FormData();
    form.append('file', f);
    form.append('destination_id', destinationId);
    try { await upload('/gis/layers', form); toast(`Layer “${f.name}” added`, 'ok'); bump(); } catch (e) { toast(errMsg(e), 'error'); }
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <Panel title={title} tight actions={
      <div className="btn-group">
        <button className={`btn sm ${zoom === 'region' ? 'on' : ''}`} onClick={() => setZoom('region')}>Region</button>
        <button className={`btn sm ${zoom === 'site' ? 'on' : ''}`} onClick={() => setZoom('site')} disabled={destination?.latitude == null}>Site</button>
      </div>
    }>
      <div className="map" style={{ height }}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Schematic map of destinations"
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const scale = Math.min(r.width / W, r.height / H);
            const ox = (r.width - W * scale) / 2, oy = (r.height - H * scale) / 2;
            const x = (e.clientX - r.left - ox) / scale, y = (e.clientY - r.top - oy) / scale;
            setCursor([bbox.minLon + (x / W) * (bbox.maxLon - bbox.minLon), bbox.maxLat - (y / H) * (bbox.maxLat - bbox.minLat)]);
          }} onMouseLeave={() => setCursor(null)}>
          <rect width={W} height={H} fill="var(--map-water)" opacity={0.25} />
          {basemap?.features.filter((f) => f.properties.kind === 'outline' && f.geometry).map((f, i) => (
            <path key={`o${i}`} d={pathFor(f.geometry as Geom)} fill="var(--map-land)" stroke="var(--line-strong)" strokeWidth={sw} />
          ))}
          {basemap?.features.filter((f) => f.properties.kind === 'river' && f.geometry).map((f, i) => (
            <path key={`r${i}`} d={pathFor(f.geometry as Geom)} fill="none" stroke="var(--map-water)" strokeWidth={sw * 2.2} opacity={0.9} />
          ))}
          {!compact && basemap?.features.filter((f) => f.properties.kind === 'city' && f.geometry).map((f, i) => {
            const [x, y] = P(...(f.geometry!.coordinates as Pos));
            return <g key={`c${i}`}><rect x={x - 3} y={y - 3} width={6} height={6} fill="var(--faint)" /><text x={x + 7} y={y + 4} fontSize={14} fill="var(--faint)">{String(f.properties.name)}</text></g>;
          })}
          {layers?.filter((l) => l.visible && l.geojson).map((l) => (
            <g key={l.id}>
              {l.geojson!.features.filter((f) => f.geometry).map((f, i) => {
                const g = f.geometry as Geom;
                const isArea = g.type.includes('Polygon');
                const d = pathFor(g);
                return (
                  <g key={i}>
                    {d && <path d={d} fill={isArea ? l.color || 'var(--red)' : 'none'} fillOpacity={isArea ? 0.18 : 0} stroke={l.color || 'var(--red)'} strokeWidth={sw * 1.6} strokeDasharray={l.is_demo ? '6 4' : undefined} />}
                    {pointsOf(g).map((p, j) => { const [x, y] = P(p[0], p[1]); return <circle key={j} cx={x} cy={y} r={5} fill={l.color || 'var(--red)'} />; })}
                  </g>
                );
              })}
            </g>
          ))}
          {points.map((p) => {
            const [x, y] = P(p.lon, p.lat);
            const c = p.status ? `var(--${p.status})` : 'var(--cream-dim)';
            return <g key={p.id}><path d={`M${x},${y - 8} L${x + 7},${y + 5} L${x - 7},${y + 5} Z`} fill={c} stroke="var(--panel)" strokeWidth={1.5}><title>{p.name}{p.kind ? ` · ${p.kind}` : ''}{p.status ? ` · ${p.status}` : ''}</title></path></g>;
          })}
          {destinations.filter((d) => d.latitude != null && d.longitude != null).map((d) => {
            const [x, y] = P(d.longitude!, d.latitude!);
            const sel = d.id === destinationId;
            return (
              <g key={d.id} style={{ cursor: 'pointer' }} onClick={() => setDestinationId(d.id)}>
                {sel && <circle cx={x} cy={y} r={16} fill="none" stroke="var(--red-bright)" strokeWidth={2} />}
                <circle cx={x} cy={y} r={sel ? 8 : 6} fill={sel ? 'var(--red-bright)' : 'var(--cream)'} stroke="var(--panel)" strokeWidth={2} />
                <text x={x + 12} y={y + 5} fontSize={sel ? 17 : 14} fontWeight={sel ? 700 : 400} fill={sel ? 'var(--cream)' : 'var(--cream-dim)'}>{d.name}</text>
                <title>{`${d.name} — ${d.region}`}</title>
              </g>
            );
          })}
        </svg>
        <span className="map-note">SCHEMATIC · not survey-grade · offline</span>
        <span className="map-coord">{cursor ? `${cursor[1].toFixed(3)}°N ${cursor[0].toFixed(3)}°E` : destination?.latitude != null ? `${destination.latitude.toFixed(3)}°N ${destination.longitude?.toFixed(3)}°E` : '—'}</span>
      </div>
      {!compact && (
        <div className="layer-list">
          <div className="row between"><span className="label">Layers</span>
            <span className="row">
              <input ref={fileRef} type="file" accept=".geojson,.json,application/geo+json,application/json" hidden onChange={(e) => onUpload(e.target.files?.[0])} />
              <button className="btn sm" onClick={() => fileRef.current?.click()} title="Upload a WGS84 GeoJSON file as a local layer">+ GeoJSON</button>
            </span>
          </div>
          {!layers?.length && <span className="tiny faint">No layers for this destination. Upload GeoJSON (EPSG:4326) or load the DEMO pack.</span>}
          {layers?.map((l) => (
            <label key={l.id} className="checkbox small">
              <input type="checkbox" checked={l.visible} onChange={() => toggle(l)} />
              <i style={{ width: 10, height: 10, background: l.color || 'var(--red)', display: 'inline-block' }} />
              <span className="truncate" style={{ maxWidth: '15rem' }}>{l.name}</span>{l.is_demo && <DemoBadge />}
            </label>
          ))}
        </div>
      )}
    </Panel>
  );
}
