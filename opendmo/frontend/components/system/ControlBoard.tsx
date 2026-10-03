'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { href, post, put, upload, errMsg, patch, del } from '@/lib/api';
import { fmtBytes, fmtDate, fmtNum } from '@/lib/format';
import { SYSTEM_TABS } from '@/lib/nav';
import { useApi, useApp, useHashTab } from '@/lib/state';
import type { Destination, ModelPkg, Settings } from '@/lib/types';
import { RunHistory } from '../cores/LabParts';
import { DataTable } from '../ui/DataTable';
import { ConfirmTyped, CopyButton, DemoBadge, EmptyState, ErrorNote, Field, Kv, Panel, ScreeningBadge, SkeletonBlock, StatusBadge, Tabs } from '../ui';

type TabId = (typeof SYSTEM_TABS)[number]['id'];
const IDS = SYSTEM_TABS.map((t) => t.id) as TabId[];

interface SysStatus { backend: string; version: string; db_engine: string; db_path: string; db_size_bytes: number | null; data_dir: string; stores: Record<string, { path: string; bytes: number }>; counts: Record<string, number>; demo_datasets: number; static_frontend: boolean; server_time: string }
interface Pack { id: string; destination_id: string; name: string; version: string; loaded: boolean; contents: string[] }

export function ControlBoard() {
  const [tab, setTab] = useHashTab(IDS, 'overview');
  return (
    <div>
      <div className="page-head">
        <div>
          <div className="page-num">SYSTEM</div>
          <h1 className="page-title">Control Board</h1>
          <p className="page-lede">Operate everything without a terminal: health, demo data, destinations, backup & restore, methods and models, run history, audit log, settings and diagnostics. Every administrative action is written to the audit log.</p>
        </div>
      </div>
      <Tabs tabs={SYSTEM_TABS.map((t) => ({ id: t.id, label: t.name }))} active={tab} onChange={setTab} />
      {tab === 'overview' && <Overview />}
      {tab === 'data' && <DemoData />}
      {tab === 'destinations' && <Destinations />}
      {tab === 'backup' && <Backup />}
      {tab === 'registry' && <Registry />}
      {tab === 'runs' && <RunHistory allDestinations />}
      {tab === 'audit' && <Audit />}
      {tab === 'settings' && <SettingsPanel />}
      {tab === 'diagnostics' && <Diagnostics />}
    </div>
  );
}

function Overview() {
  const { data: st, error } = useApi<SysStatus>('/system/status');
  const { data: health } = useApi<{ status: string; version: string; database: string }>('/health');
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const { toast, bump } = useApp();
  if (error) return <ErrorNote error={error} />;
  if (!st) return <SkeletonBlock lines={8} />;
  const reset = async () => {
    setBusy(true);
    try { const r = await post<{ safety_backup: string }>('/system/reset', { confirm: 'RESET' }); toast(`Database reset. Safety backup: ${r.safety_backup}`, 'ok'); setConfirm(false); bump(); }
    catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <div className="grid g4">
        <Panel title="Backend"><div className="row"><StatusBadge status={health?.status === 'ok' ? 'ok' : 'risk'} label={health?.status ?? '…'} /><span className="small">v{st.version}</span></div><p className="tiny faint" style={{ marginTop: '0.4rem' }}>{fmtDate(st.server_time)}</p></Panel>
        <Panel title="Database"><div className="small">{st.db_engine}</div><div className="tiny faint" style={{ overflowWrap: 'anywhere' }}>{st.db_path}</div><div className="tiny faint">{fmtBytes(st.db_size_bytes)}</div></Panel>
        <Panel title="Data directory"><div className="tiny" style={{ overflowWrap: 'anywhere' }}>{st.data_dir}</div>{Object.entries(st.stores).map(([k, v]) => <div key={k} className="tiny faint">{k}: {fmtBytes(v.bytes)}</div>)}</Panel>
        <Panel title="Frontend"><div className="small">{st.static_frontend ? 'bundled static build' : 'dev server'}</div><div className="tiny faint">offline · no CDN · no telemetry</div></Panel>
      </div>
      <Panel title="Records">
        <div className="result-grid">{Object.entries(st.counts).map(([k, v]) => <div key={k} className="result-cell"><div className="k">{k.replace(/_/g, ' ')}</div><div className="v">{fmtNum(v)}</div></div>)}</div>
        <p className="tiny faint" style={{ marginTop: '0.4rem' }}>{st.demo_datasets} DEMO dataset(s) loaded.</p>
      </Panel>
      <Panel title="Quick actions">
        <div className="row">
          <Link className="btn primary" href="/import/">Import wizard</Link>
          <Link className="btn" href="/system/control-board/#data" onClick={() => { window.location.hash = 'data'; }}>Seed / remove demo data</Link>
          <a className="btn" href={href('/system/backup')} download>Download backup</a>
          <a className="btn" href={href('/system/export')} download>Export all data</a>
          <button className="btn danger" onClick={() => setConfirm(true)}>Reset database…</button>
        </div>
      </Panel>
      {confirm && <ConfirmTyped word="RESET" title="Reset database" busy={busy} onClose={() => setConfirm(false)} onConfirm={reset}
        body={<>Deletes <b>all</b> datasets, runs, registers, briefs and settings and recreates an empty database with the four pilot destinations. A safety backup is written to the backups folder first.</>} />}
    </div>
  );
}

function DemoData() {
  const { toast, bump } = useApp();
  const { data: packs, reload } = useApi<Pack[]>('/system/seed-packs');
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (key: string, path: string, ok: string) => {
    setBusy(key);
    try { await post(path); toast(ok, 'ok'); bump(); reload(); } catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(null); }
  };
  return (
    <div className="stack">
      <div className="callout small">Seed packs contain <b>synthetic DEMO data</b> generated deterministically for demonstration and training. Every row is flagged and badged <DemoBadge />. Removing a pack deletes its datasets, registers, GIS layers and any runs computed from it; your own data is never touched.</div>
      <Panel title="DEMO seed packs" actions={<span className="row">
        <button className="btn primary sm" disabled={!!busy} onClick={() => act('all-load', '/system/demo/load-all', 'All DEMO packs loaded')}>Seed all</button>
        <button className="btn danger sm" disabled={!!busy} onClick={() => act('all-rm', '/system/demo/remove-all', 'All DEMO data removed')}>Remove all demo data</button>
      </span>}>
        {!packs ? <SkeletonBlock /> : (
          <div className="table-wrap"><table className="data"><thead><tr><th>Pack</th><th>Version</th><th>Status</th><th>Contents</th><th /></tr></thead>
            <tbody>{packs.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td><td>{p.version}</td>
                <td><StatusBadge status={p.loaded ? 'ok' : 'none'} label={p.loaded ? 'loaded' : 'not loaded'} /></td>
                <td className="cell-wrap small muted">{p.contents.join(' · ')}</td>
                <td className="nowrap">{p.loaded
                  ? <button className="btn danger sm" disabled={!!busy} onClick={() => act(p.id, `/system/seed-packs/${p.destination_id}/remove`, `${p.name} removed`)}>{busy === p.id ? 'Removing…' : 'Remove'}</button>
                  : <button className="btn sm" disabled={!!busy} onClick={() => act(p.id, `/system/seed-packs/${p.destination_id}/load`, `${p.name} loaded`)}>{busy === p.id ? 'Loading…' : 'Load'}</button>}</td>
              </tr>))}</tbody></table></div>
        )}
      </Panel>
      <Panel title="Your own data"><div className="row"><Link className="btn primary" href="/import/">Open the CSV import wizard</Link><Link className="btn" href="/research-lab/#datasets">Dataset explorer</Link></div></Panel>
    </div>
  );
}

function Destinations() {
  const { destinations, toast, bump, setDestinationId } = useApp();
  const [form, setForm] = useState({ name: '', region: '', latitude: '', longitude: '', area_km2: '', description: '' });
  const [editing, setEditing] = useState<Destination | null>(null);
  const save = async () => {
    const body = { ...form, latitude: form.latitude ? Number(form.latitude) : null, longitude: form.longitude ? Number(form.longitude) : null, area_km2: form.area_km2 ? Number(form.area_km2) : null };
    try {
      if (editing) { await patch(`/destinations/${editing.id}`, body); toast('Destination updated', 'ok'); }
      else { const d = await post<Destination>('/destinations', body); toast(`Destination ${d.name} added`, 'ok'); setDestinationId(d.id); }
      setForm({ name: '', region: '', latitude: '', longitude: '', area_km2: '', description: '' }); setEditing(null); bump();
    } catch (e) { toast(errMsg(e), 'error'); }
  };
  const edit = (d: Destination) => { setEditing(d); setForm({ name: d.name, region: d.region, latitude: d.latitude?.toString() ?? '', longitude: d.longitude?.toString() ?? '', area_km2: d.area_km2?.toString() ?? '', description: d.description }); };
  return (
    <div className="stack">
      <Panel title={editing ? `Edit ${editing.name}` : 'Add a destination'} sub="appears in every selector, the GIS panel and the import wizard">
        <div className="stack">
          <div className="form-grid">
            {(['name', 'region', 'latitude', 'longitude', 'area_km2'] as const).map((k) => (
              <Field key={k} label={{ name: 'Name *', region: 'Region / district', latitude: 'Latitude (WGS84)', longitude: 'Longitude (WGS84)', area_km2: 'Area (km²)' }[k]} htmlFor={`d-${k}`}>
                <input id={`d-${k}`} className="input" value={form[k]} inputMode={k === 'name' || k === 'region' ? undefined : 'decimal'} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </Field>
            ))}
          </div>
          <Field label="Description" htmlFor="d-desc"><textarea id="d-desc" className="textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="row"><button className="btn primary" onClick={save} disabled={form.name.trim().length < 2}>{editing ? 'Save changes' : 'Add destination'}</button>{editing && <button className="btn ghost" onClick={() => { setEditing(null); setForm({ name: '', region: '', latitude: '', longitude: '', area_km2: '', description: '' }); }}>Cancel</button>}</div>
        </div>
      </Panel>
      <Panel title="Destinations" tight>
        <DataTable rows={destinations} rowKey={(d) => d.id} csvName="destinations"
          columns={[{ key: 'name', label: 'Name' }, { key: 'id', label: 'ID' }, { key: 'region', label: 'Region' },
            { key: 'latitude', label: 'Lat', num: true }, { key: 'longitude', label: 'Lon', num: true }, { key: 'area_km2', label: 'Area km²', num: true },
            { key: 'is_pilot', label: 'Pilot', value: (d) => (d.is_pilot ? 'pilot' : '') },
            { key: 'act', label: '', value: () => '', render: (d) => <span className="row"><button className="btn ghost sm" onClick={() => edit(d)}>Edit</button>
              {!d.is_pilot && <button className="btn ghost sm" onClick={async () => { if (!window.confirm(`Delete ${d.name}?`)) return; try { await del(`/destinations/${d.id}`); toast('Deleted', 'ok'); bump(); } catch (e) { toast(errMsg(e), 'error'); } }}>✕</button>}</span> }]} />
      </Panel>
    </div>
  );
}

function Backup() {
  const { toast, bump } = useApp();
  const { data: backups, reload } = useApi<{ name: string; bytes: number; created_at: string }[]>('/system/backups');
  const [file, setFile] = useState<File | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const restore = async () => {
    if (!file) return;
    setBusy(true);
    const form = new FormData(); form.append('file', file); form.append('confirm', 'RESTORE');
    try { const r = await upload<{ safety_backup: string }>('/system/restore', form); toast(`Restored. Safety backup of the previous state: ${r.safety_backup}`, 'ok'); setConfirm(false); setFile(null); bump(); }
    catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <div className="grid g2">
        <Panel title="Backup">
          <div className="stack">
            <p className="small muted">A single .zip containing every table (portable JSON, works across SQLite and PostgreSQL), installed model packages and archived import files. A copy is also kept in the data directory.</p>
            <div className="row"><a className="btn primary" href={href('/system/backup')} download onClick={() => setTimeout(reload, 1500)}>Download backup now</a></div>
          </div>
        </Panel>
        <Panel title="Restore">
          <div className="stack">
            <p className="small muted">Replaces all current data with the backup. The current state is backed up automatically first.</p>
            <input ref={fileRef} type="file" accept=".zip,application/zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Backup file" />
            <div className="row"><button className="btn danger" disabled={!file} onClick={() => setConfirm(true)}>Restore from file…</button></div>
          </div>
        </Panel>
      </div>
      <Panel title="Export all data" actions={<a className="btn sm" href={href('/system/export')} download>Download export (.zip)</a>}>
        <p className="small muted">Every dataset as long and wide CSV plus JSON, all runs, registers, briefs and GIS layers — for analysis in R, Python, Excel or QGIS. DEMO rows remain flagged.</p>
      </Panel>
      <Panel title="Saved backups" tight>
        <DataTable rows={backups ?? []} rowKey={(b) => b.name} empty={<EmptyState title="No backups yet" />}
          columns={[{ key: 'name', label: 'File' }, { key: 'bytes', label: 'Size', num: true, render: (b) => fmtBytes(b.bytes) }, { key: 'created_at', label: 'Created', render: (b) => fmtDate(b.created_at) }]} />
      </Panel>
      {confirm && <ConfirmTyped word="RESTORE" title="Restore backup" busy={busy} onClose={() => setConfirm(false)} onConfirm={restore}
        body={<>All current data will be replaced by <b>{file?.name}</b>. A safety backup of the current state is written first.</>} />}
    </div>
  );
}

function Registry() {
  const { toast, bump } = useApp();
  const { data: methods, reload } = useApi<{ id: string; name: string; version: string; core: string; kind: string; screening: boolean; enabled: boolean }[]>('/system/methods');
  const { data: models, reload: reloadModels } = useApi<ModelPkg[]>('/models');
  const [url, setUrl] = useState('');
  const [ref, setRef] = useState('');
  const [busy, setBusy] = useState(false);
  const toggle = async (id: string, enabled: boolean) => { try { await post(`/system/methods/${id}`, { enabled }); reload(); bump(); } catch (e) { toast(errMsg(e), 'error'); } };
  const setModel = async (m: ModelPkg, status: string) => { try { await post(`/models/${m.id}/${m.version}/status`, { status }); reloadModels(); bump(); } catch (e) { toast(errMsg(e), 'error'); } };
  const install = async () => {
    setBusy(true);
    try { const m = await post<ModelPkg>('/models/install', { url, ref: ref || null }); toast(`Installed ${m.name} v${m.version} — review it, then enable it`, 'ok'); setUrl(''); reloadModels(); bump(); }
    catch (e) { toast(errMsg(e), 'error'); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <Panel title="Calculations & forecasts" sub="disabled methods refuse new runs; past runs are kept" tight>
        <DataTable rows={methods ?? []} rowKey={(m) => m.id} csvName="methods"
          columns={[{ key: 'name', label: 'Method', render: (m) => <span className="row">{m.name}{m.screening && <ScreeningBadge />}</span> }, { key: 'id', label: 'ID' }, { key: 'version', label: 'Version' },
            { key: 'core', label: 'Core', filter: true }, { key: 'kind', label: 'Kind', filter: true },
            { key: 'enabled', label: 'Enabled', value: (m) => (m.enabled ? 'yes' : 'no'), render: (m) => <label className="checkbox"><input type="checkbox" checked={m.enabled} onChange={(e) => toggle(m.id, e.target.checked)} />{m.enabled ? 'enabled' : 'disabled'}</label> }]} />
      </Panel>
      <Panel title="Install a model package from GitHub" sub="explicit action · the only outbound network call OpenDMO makes">
        <div className="stack">
          <div className="callout small">OpenDMO downloads the repository archive, validates it against the package contract (data-only artifacts, no executable files, json-linear format; pickle refused) and registers it <b>disabled</b>. <code>requirements.txt</code> is displayed but never installed. Only install packages from sources you trust.</div>
          <div className="form-grid">
            <Field label="GitHub URL" hint="https://github.com/owner/repo or …/tree/ref/subdir" htmlFor="gh-url"><input id="gh-url" className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/owner/repo" /></Field>
            <Field label="Branch / tag (optional)" htmlFor="gh-ref"><input id="gh-ref" className="input" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="main" /></Field>
          </div>
          <div className="row"><button className="btn primary" onClick={install} disabled={!url.trim() || busy}>{busy ? 'Downloading & validating…' : 'Install model package'}</button></div>
        </div>
      </Panel>
      <Panel title="Installed models" tight>
        <DataTable rows={models ?? []} rowKey={(m) => `${m.id}@${m.version}`}
          columns={[{ key: 'name', label: 'Model', render: (m) => <span className="row">{m.name}{m.is_demo && <DemoBadge />}</span> }, { key: 'version', label: 'Version' }, { key: 'framework', label: 'Format' },
            { key: 'source_repo', label: 'Source', wrap: true }, { key: 'installed_at', label: 'Installed', render: (m) => fmtDate(m.installed_at) },
            { key: 'status', label: 'Status', render: (m) => <label className="checkbox"><input type="checkbox" checked={m.status === 'enabled'} onChange={(e) => setModel(m, e.target.checked ? 'enabled' : 'disabled')} />{m.status}</label> }]} />
      </Panel>
    </div>
  );
}

function Audit() {
  const [action, setAction] = useState('');
  const { data } = useApi<{ id: number; ts: string; action: string; target: string; detail: Record<string, unknown>; actor: string }[]>(`/system/audit${action ? `?action=${encodeURIComponent(action)}` : ''}`);
  return (
    <Panel title="Audit log" sub="administrative actions, newest first" tight actions={
      <select className="select sm" value={action} onChange={(e) => setAction(e.target.value)} aria-label="Filter by action">
        <option value="">all actions</option>{['demo', 'system', 'import', 'dataset', 'method', 'model', 'settings', 'destination', 'gis', 'brief'].map((a) => <option key={a} value={a}>{a}.*</option>)}
      </select>}>
      <DataTable rows={data ?? []} rowKey={(r) => String(r.id)} csvName="audit-log" tall empty={<EmptyState title="No audit entries" />}
        columns={[{ key: 'ts', label: 'When', render: (r) => fmtDate(r.ts) }, { key: 'action', label: 'Action', filter: true }, { key: 'target', label: 'Target', wrap: true },
          { key: 'detail', label: 'Detail', wrap: true, value: (r) => JSON.stringify(r.detail) }, { key: 'actor', label: 'Actor' }]} />
    </Panel>
  );
}

function SettingsPanel() {
  const { toast, setTheme, bump } = useApp();
  const { data } = useApi<Settings>('/system/settings');
  const [s, setS] = useState<Settings | null>(null);
  useEffect(() => { if (data) setS(data); }, [data]);
  if (!s) return <SkeletonBlock />;
  const save = async () => {
    try {
      const r = await put<{ settings: Settings; restart_required: boolean }>('/system/settings', {
        theme: s.theme, units: s.units, date_format: s.date_format, currency: s.currency, default_range_months: Number(s.default_range_months), port: Number(s.port), data_dir: s.data_dir,
      });
      setTheme(r.settings.theme);
      toast(r.restart_required ? 'Saved. Port / data directory take effect after restarting OpenDMO.' : 'Settings saved', r.restart_required ? 'warn' : 'ok');
      bump();
    } catch (e) { toast(errMsg(e), 'error'); }
  };
  return (
    <Panel title="Settings">
      <div className="stack">
        <div className="form-grid">
          <Field label="Theme" htmlFor="s-theme"><select id="s-theme" className="select" value={s.theme} onChange={(e) => setS({ ...s, theme: e.target.value as Settings['theme'] })}><option value="dark">dark (default)</option><option value="light">light (creamy)</option></select></Field>
          <Field label="Units" htmlFor="s-units"><select id="s-units" className="select" value={s.units} onChange={(e) => setS({ ...s, units: e.target.value })}><option value="metric">metric (SI)</option></select></Field>
          <Field label="Date format" htmlFor="s-df"><select id="s-df" className="select" value={s.date_format} onChange={(e) => setS({ ...s, date_format: e.target.value })}><option>YYYY-MM-DD</option><option>DD/MM/YYYY</option><option>MM/DD/YYYY</option></select></Field>
          <Field label="Currency" htmlFor="s-cur"><select id="s-cur" className="select" value={s.currency} onChange={(e) => setS({ ...s, currency: e.target.value })}><option>BDT</option><option>USD</option><option>EUR</option></select></Field>
          <Field label="Default time range (months)" htmlFor="s-range"><input id="s-range" className="input" inputMode="numeric" value={s.default_range_months} onChange={(e) => setS({ ...s, default_range_months: Number(e.target.value) || 12 })} /></Field>
          <Field label="Port (restart required)" hint={`running on ${s.effective.port}`} htmlFor="s-port"><input id="s-port" className="input" inputMode="numeric" value={s.port} onChange={(e) => setS({ ...s, port: Number(e.target.value) })} /></Field>
        </div>
        <Field label="Data directory (restart required)" hint={`currently ${s.effective.data_dir}. Move the folder contents yourself, or start empty and restore a backup.`} htmlFor="s-dir">
          <input id="s-dir" className="input" value={s.data_dir} onChange={(e) => setS({ ...s, data_dir: e.target.value })} />
        </Field>
        <div className="row"><button className="btn primary" onClick={save}>Save settings</button></div>
      </div>
    </Panel>
  );
}

function Diagnostics() {
  const { data } = useApi<Record<string, unknown> & { text: string; packages: Record<string, string | null> }>('/system/diagnostics');
  if (!data) return <SkeletonBlock lines={8} />;
  return (
    <Panel title="Diagnostics" actions={<CopyButton text={data.text} label="Copy report" />}>
      <div className="stack">
        <Kv items={[['OpenDMO', String(data.opendmo_version)], ['OS', String(data.os)], ['Python', `${data.python} (${data.python_executable})`],
          ['database', `${data.db_engine} · ${data.db_path} · ${fmtBytes(data.db_size_bytes as number)}`], ['data directory', String(data.data_dir)],
          ['disk free', `${data.disk_free_gb} GB`], ['static frontend', data.static_frontend ? 'bundled' : 'missing'], ['pickle models', data.allow_pickle_models ? 'ALLOWED (trusted sources only)' : 'refused (default)'],
          ['network policy', String(data.network_policy)]]} />
        <div className="table-wrap"><table className="data"><thead><tr><th>Package</th><th>Version</th></tr></thead><tbody>{Object.entries(data.packages).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v ?? 'not installed'}</td></tr>)}</tbody></table></div>
        <details><summary>Plain-text report</summary><pre className="formula tiny">{data.text}</pre></details>
      </div>
    </Panel>
  );
}
