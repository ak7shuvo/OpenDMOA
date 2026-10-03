'use client';

import Link from 'next/link';
import { useApp, type RangePreset } from '@/lib/state';
import { DemoBadge } from '../ui';
import { useApi } from '@/lib/state';
import type { Summary } from '@/lib/types';

const PRESETS: { id: RangePreset; label: string }[] = [
  { id: '12m', label: '12M' }, { id: '24m', label: '24M' }, { id: '36m', label: '36M' }, { id: 'all', label: 'ALL' }, { id: 'custom', label: 'CUSTOM' },
];

export function TopBar() {
  const { destinations, destinationId, setDestinationId, range, setRange, applyPreset, theme, setTheme, setPaletteOpen, backendOk } = useApp();
  const { data: summary } = useApi<Summary>(destinationId ? `/destinations/${destinationId}/summary?core=lab` : null);
  return (
    <header className="topbar">
      <label className="sr-only" htmlFor="dest-select">Destination</label>
      <select id="dest-select" className="select" value={destinationId} onChange={(e) => setDestinationId(e.target.value)} style={{ minWidth: '13rem' }}>
        {destinations.map((d) => <option key={d.id} value={d.id}>{d.name}{d.is_pilot ? '' : ' ·'}</option>)}
      </select>
      <Link className="btn ghost sm" href="/system/control-board/#destinations" title="Add a destination">+ Destination</Link>
      <div className="btn-group" role="group" aria-label="Time range">
        {PRESETS.map((p) => (
          <button key={p.id} className={`btn sm ${range.preset === p.id ? 'on' : ''}`} onClick={() => applyPreset(p.id)}>{p.label}</button>
        ))}
      </div>
      {range.preset === 'custom' && (
        <span className="row">
          <input className="input sm" type="month" aria-label="From" value={range.start ?? ''} onChange={(e) => setRange({ ...range, start: e.target.value || null })} />
          <span className="faint">→</span>
          <input className="input sm" type="month" aria-label="To" value={range.end ?? ''} onChange={(e) => setRange({ ...range, end: e.target.value || null })} />
        </span>
      )}
      <span className="tiny faint">{range.start ?? 'start'} → {range.end ?? 'latest'}</span>
      {summary?.has_demo && <DemoBadge title="This destination currently includes synthetic DEMO datasets" />}
      <span className="spacer" />
      <button className="btn sm" onClick={() => setPaletteOpen(true)} aria-label="Open command palette">Search <span className="kbd">Ctrl K</span></button>
      <button className="btn sm" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">{theme === 'dark' ? '☾ Dark' : '☀ Light'}</button>
      <span className="statusbar" title={backendOk ? 'Local backend reachable' : 'Backend unreachable'}>
        <span className={`dot ${backendOk === null ? '' : backendOk ? 'ok' : 'risk'}`} />{backendOk === false ? 'offline' : 'local'}
      </span>
    </header>
  );
}
