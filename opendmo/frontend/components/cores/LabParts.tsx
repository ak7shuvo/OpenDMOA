'use client';

import Link from 'next/link';
import { useState } from 'react';
import { del, href, post, qs, errMsg } from '@/lib/api';
import { fmtDate, fmtNum, shortHash } from '@/lib/format';
import { methodRoute } from '@/lib/nav';
import { useApi, useApp } from '@/lib/state';
import type { Dataset, Method, ModelPkg, Observation, Run } from '@/lib/types';
import { LineChart } from '../charts/LineChart';
import { MethodDoc } from '../analysis/MethodRunner';
import { ProvenanceBlock, ResultView } from '../analysis/Provenance';
import { DataTable } from '../ui/DataTable';
import { CopyButton, DemoBadge, EmptyState, ErrorNote, Field, Kv, Panel, ScreeningBadge, SkeletonBlock, StatusBadge } from '../ui';

const QSTATUS = (l?: string) => (l === 'high' ? 'ok' : l === 'moderate' ? 'watch' : l === 'low' ? 'risk' : 'none');

/* ------------------------------------------------------------------ datasets */

export function DatasetExplorer() {
  const { destinationId } = useApp();
  const [scope, setScope] = useState<'dest' | 'all'>('dest');
  const { data, loading } = useApi<Dataset[]>(`/datasets${qs({ destination_id: scope === 'dest' ? destinationId : undefined })}`);
  const [sel, setSel] = useState<string | null>(null);
  return (
    <div className="stack">
      <Panel title="Dataset explorer" sub="versioned · metadata-driven · quality-scored" tight actions={
        <span className="row">
          <div className="btn-group"><button className={`btn sm ${scope === 'dest' ? 'on' : ''}`} onClick={() => setScope('dest')}>This destination</button><button className={`btn sm ${scope === 'all' ? 'on' : ''}`} onClick={() => setScope('all')}>All</button></div>
          <Link className="btn primary sm" href="/import/">+ Import CSV</Link>
        </span>
      }>
        {loading && !data ? <div className="panel-body"><SkeletonBlock /></div> : (
          <DataTable rows={data ?? []} rowKey={(d) => d.id} onRowClick={(d) => setSel(d.id)} selectedKey={sel} csvName="datasets"
            empty={<EmptyState title="No datasets yet" action={<><Link className="btn primary sm" href="/import/">Import CSV</Link><Link className="btn sm" href="/system/control-board/#data">Load DEMO data</Link></>}>Create one from the import wizard or load a DEMO seed pack.</EmptyState>}
            columns={[
              { key: 'name', label: 'Dataset', render: (d) => <span className="row">{d.name}{d.is_demo && <DemoBadge />}</span> },
              { key: 'destination_id', label: 'Destination', filter: true },
              { key: 'kind_label', label: 'Type', filter: true },
              { key: 'version', label: 'Ver.', num: true },
              { key: 'status', label: 'Status', filter: true, render: (d) => <StatusBadge status={d.status === 'validated' ? 'ok' : d.status === 'archived' ? 'none' : 'watch'} label={d.status} /> },
              { key: 'observations', label: 'Obs.', num: true },
              { key: 'first_period', label: 'From' }, { key: 'last_period', label: 'To' },
              { key: 'quality_score', label: 'Quality', num: true, render: (d) => <StatusBadge status={QSTATUS(d.quality?.level)} label={`${fmtNum(d.quality_score)}`} /> },
              { key: 'updated_at', label: 'Updated', value: (d) => d.updated_at, render: (d) => fmtDate(d.updated_at) },
            ]} />
        )}
      </Panel>
      {sel && <DatasetDetail id={sel} onClose={() => setSel(null)} />}
    </div>
  );
}

function DatasetDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { toast, bump } = useApp();
  const { data: ds, error } = useApi<Dataset>(`/datasets/${id}`);
  const { data: obs } = useApi<Observation[]>(`/datasets/${id}/observations`);
  const [variable, setVariable] = useState<string>('');
  const act = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok, 'ok'); bump(); } catch (e) { toast(errMsg(e), 'error'); } };
  if (error) return <ErrorNote error={error} />;
  if (!ds) return <Panel title="Loading…"><SkeletonBlock /></Panel>;
  const q = ds.quality ?? {};
  const v = variable || ds.variable_defs[0]?.name || (obs?.[0]?.variable ?? '');
  const pts = (obs ?? []).filter((o) => o.variable === v && o.value !== null).map((o) => ({ x: o.period, y: o.value }));
  return (
    <Panel title={ds.name} sub={`${ds.id} · v${ds.version}`} actions={
      <span className="row">
        {ds.is_demo && <DemoBadge />}
        <button className="btn sm" onClick={() => act(() => post(`/datasets/${id}/validate`), 'Validated — quality recomputed')} disabled={ds.status === 'archived'}>Validate</button>
        <button className="btn sm" onClick={() => act(() => post(`/datasets/${id}/version`), 'New version created')}>New version</button>
        <button className="btn sm" onClick={() => act(() => post(`/datasets/${id}/archive`), 'Archived (immutable)')} disabled={ds.status === 'archived'}>Archive</button>
        <Link className="btn sm" href={`/import/?dataset=${encodeURIComponent(id)}`}>Import into…</Link>
        <a className="btn sm" href={href(`/datasets/${id}/export.csv?layout=long`)} download>CSV long</a>
        <a className="btn sm" href={href(`/datasets/${id}/export.csv?layout=wide`)} download>CSV wide</a>
        <a className="btn sm" href={href(`/datasets/${id}/export.json`)} download>JSON</a>
        <a className="btn sm" href={href(`/datasets/${id}/template.csv`)} download>Template</a>
        <button className="btn danger sm" onClick={() => { if (window.confirm(`Delete dataset ${id} and all its observations? Runs keep their recorded inputs.`)) void act(() => del(`/datasets/${id}`).then(onClose), 'Dataset deleted'); }}>Delete</button>
        <button className="btn ghost sm" onClick={onClose} aria-label="Close">✕</button>
      </span>
    }>
      <div className="grid g2">
        <div className="stack">
          <Kv items={[
            ['status', <StatusBadge key="s" status={ds.status === 'validated' ? 'ok' : ds.status === 'archived' ? 'none' : 'watch'} label={ds.status} />],
            ['quality', <span key="q"><StatusBadge status={QSTATUS(q.level)} label={`${fmtNum(q.quality_score)} / 100 ${q.level ?? ''}`} /></span>],
            ['completeness', `${fmtNum(q.completeness_pct)} %`], ['periods', `${q.periods ?? 0} (${q.first_period ?? '—'} → ${q.last_period ?? '—'})`],
            ['gaps', q.n_gaps ? `${q.n_gaps}: ${(q.period_gaps ?? []).slice(0, 6).join(', ')}${(q.n_gaps ?? 0) > 6 ? '…' : ''}` : 'none'],
            ['flags', Object.entries(q.flags ?? {}).map(([k, n]) => `${k} ${n}`).join(' · ') || '—'],
            ['missing required', (q.missing_required ?? []).join(', ') || 'none'],
            ['range violations', String(q.range_violations ?? 0)],
            ['frequency', ds.frequency], ['source', String(ds.provenance.source ?? ds.provenance.created_via ?? '—')],
            ['last file hash', shortHash(ds.provenance.last_file_hash as string | undefined)],
            ['versions', (ds.versions ?? []).map((x) => `v${x.version} ${x.status}`).join(' · ')],
          ]} />
          <div>
            <div className="label">Imports</div>
            {!ds.imports?.length ? <span className="tiny faint">No file imports{ds.is_demo ? ' (generated by the seed pack)' : ''}.</span> : (
              <div className="table-wrap" style={{ maxHeight: '12rem' }}><table className="data"><thead><tr><th>When</th><th>File</th><th>Hash</th><th className="num">+</th><th className="num">Δ</th><th className="num">skip</th></tr></thead>
                <tbody>{ds.imports.map((i) => <tr key={i.id}><td>{fmtDate(i.created_at)}</td><td>{i.file_name}</td><td><code>{shortHash(i.file_hash)}</code></td><td className="num">{i.inserted}</td><td className="num">{i.updated}</td><td className="num">{i.skipped}</td></tr>)}</tbody></table></div>
            )}
          </div>
        </div>
        <div className="stack">
          <div className="row"><span className="label">Variable</span>
            <select className="select sm" value={v} onChange={(e) => setVariable(e.target.value)}>{ds.variable_defs.map((d) => <option key={d.name} value={d.name}>{d.label} ({d.unit})</option>)}</select>
          </div>
          {pts.length ? <LineChart ariaLabel={`${v} series`} height={180} series={[{ id: v, label: v, color: 'var(--chart-2)', points: pts }]} /> : <span className="tiny faint">No values for this variable.</span>}
          <div className="table-wrap" style={{ maxHeight: '14rem' }}>
            <table className="data"><thead><tr><th>Variable</th><th>Unit</th><th>Type</th><th className="num">Min</th><th className="num">Max</th><th>Req.</th></tr></thead>
              <tbody>{ds.variable_defs.map((d) => <tr key={d.name}><td title={d.description}>{d.label} <span className="faint tiny">{d.name}</span></td><td>{d.unit}</td><td>{d.type}</td><td className="num">{fmtNum(d.min)}</td><td className="num">{fmtNum(d.max)}</td><td>{d.required ? 'yes' : ''}</td></tr>)}</tbody></table>
          </div>
        </div>
      </div>
      <details style={{ marginTop: '0.6rem' }}>
        <summary>Observations ({obs?.length ?? 0})</summary>
        <DataTable rows={(obs ?? []).map((o, i) => ({ ...o, _k: `${o.period}-${o.variable}-${i}` }))} rowKey={(o) => o._k} csvName={id}
          columns={[{ key: 'period', label: 'Period' }, { key: 'variable', label: 'Variable', filter: true }, { key: 'value', label: 'Value', num: true }, { key: 'unit', label: 'Unit' }, { key: 'quality_flag', label: 'Flag', filter: true }]} />
      </details>
    </Panel>
  );
}

/* ------------------------------------------------------------------ methodology */

export function MethodologyRegistry() {
  const { data: methods } = useApi<Method[]>('/methods');
  const [sel, setSel] = useState<string | null>(null);
  const m = methods?.find((x) => x.id === sel) ?? null;
  return (
    <div className="stack">
      <Panel title="Methodology registry" sub="every calculation is registered, versioned, documented and unit-tested" tight
        actions={<a className="btn sm" href={href('/methodology.md')} download="opendmo-methodology.md">Download methodology.md</a>}>
        <DataTable rows={methods ?? []} rowKey={(x) => x.id} onRowClick={(x) => setSel(x.id)} selectedKey={sel} csvName="methods"
          columns={[
            { key: 'name', label: 'Method', render: (x) => <span className="row">{x.name}{x.screening && <ScreeningBadge />}</span> },
            { key: 'id', label: 'ID' }, { key: 'version', label: 'Version' }, { key: 'core', label: 'Core', filter: true },
            { key: 'kind', label: 'Kind', filter: true }, { key: 'category', label: 'Category', filter: true },
            { key: 'enabled', label: 'Enabled', value: (x) => (x.enabled ? 'yes' : 'no') },
            { key: 'refs', label: 'References', value: (x) => x.references.length },
          ]} />
      </Panel>
      {m && (
        <Panel title={m.name} sub={`${m.id} v${m.version}`} actions={<span className="row">{m.screening && <ScreeningBadge />}<Link className="btn primary sm" href={methodRoute(m.id)}>Open & run</Link><button className="btn ghost sm" onClick={() => setSel(null)}>✕</button></span>}>
          <div className="stack">
            <p className="small">{m.summary}</p>
            {m.screening && <div className="callout small">{m.label}.</div>}
            <MethodDoc m={m} />
            <div className="table-wrap"><table className="data"><thead><tr><th>Input</th><th>Unit</th><th>Range</th><th>Default</th><th>Data binding</th></tr></thead>
              <tbody>{m.inputs.map((p) => <tr key={p.name}><td title={p.description}>{p.label} <span className="tiny faint">{p.name}</span></td><td>{p.unit}</td><td>{p.min ?? ''} – {p.max ?? ''}</td><td>{typeof p.default === 'object' && p.default !== null ? 'table' : fmtNum(p.default)}</td><td className="small">{p.source ? `${p.source.aggregation}(${p.source.kind}.${p.source.variable})` : ''}</td></tr>)}</tbody></table></div>
            <div className="table-wrap"><table className="data"><thead><tr><th>Output</th><th>Unit</th><th>Description</th></tr></thead>
              <tbody>{m.outputs.map((o) => <tr key={o.name}><td>{o.label} <span className="tiny faint">{o.name}</span></td><td>{o.unit}</td><td className="cell-wrap">{o.description}</td></tr>)}</tbody></table></div>
            <div><div className="label">Verification cases (enforced by unit tests)</div>
              {m.known_cases.map((k, i) => <pre key={i} className="formula tiny">{JSON.stringify(k.inputs)}{'\n'}→ {JSON.stringify(k.expected)}{k.note ? `\n# ${k.note}` : ''}</pre>)}</div>
            <div><div className="label">BibTeX</div>
              <pre className="formula tiny">{m.references.map((r) => r.bibtex).join('\n\n') || '—'}</pre>
              {m.references.length > 0 && <CopyButton text={m.references.map((r) => r.bibtex).join('\n\n')} label="Copy BibTeX" />}</div>
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ model lab */

export function ModelLab() {
  const { destinationId, toast, bump } = useApp();
  const { data: models } = useApi<ModelPkg[]>('/models');
  const [sel, setSel] = useState<string | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [run, setRun] = useState<Run | null>(null);
  const m = models?.find((x) => `${x.id}@${x.version}` === sel) ?? null;
  const execute = async () => {
    if (!m) return;
    try {
      const r = await post<Run>('/models/run', { model_id: m.id, version: m.version, destination_id: destinationId,
        inputs: Object.fromEntries(Object.entries(inputs).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)])) });
      setRun(r); bump();
      if (r.status === 'failed') toast(`Model run failed: ${r.error}`, 'error');
    } catch (e) { toast(errMsg(e), 'error'); }
  };
  return (
    <div className="stack">
      <div className="callout plain small">Model packages follow a safe contract: artifacts are <b>data</b> (json-linear weights). Pickle artifacts are refused by default, package code is never executed and <code>requirements.txt</code> is never auto-installed. Install new packages from a GitHub URL in <Link href="/system/control-board/#registry">System › Control Board › Methods & Models</Link>.</div>
      <Panel title="Installed model packages" tight>
        <DataTable rows={models ?? []} rowKey={(x) => `${x.id}@${x.version}`} onRowClick={(x) => { setSel(`${x.id}@${x.version}`); setInputs({}); setRun(null); }} selectedKey={sel}
          empty={<EmptyState title="No models installed" />}
          columns={[
            { key: 'name', label: 'Model', render: (x) => <span className="row">{x.name}{x.is_demo && <DemoBadge />}</span> },
            { key: 'version', label: 'Version' }, { key: 'task', label: 'Task' }, { key: 'framework', label: 'Format' },
            { key: 'status', label: 'Status', render: (x) => <StatusBadge status={x.status === 'enabled' ? 'ok' : 'none'} label={x.status} /> },
            { key: 'source_repo', label: 'Source', wrap: true }, { key: 'license', label: 'License' },
          ]} />
      </Panel>
      {m && (
        <Panel title={m.name} sub={`${m.id} v${m.version}`} actions={m.is_demo ? <DemoBadge /> : null}>
          <div className="stack">
            <p className="small muted">{m.description}</p>
            <Kv items={[['training data', m.training_data || '—'], ['evaluation', JSON.stringify(m.evaluation)], ['requirements.txt (not installed)', <pre key="r" className="formula tiny">{m.requirements_txt || '—'}</pre>]]} />
            <div className="form-grid">
              {m.inputs.map((p) => (
                <Field key={p.name} label={`${p.label ?? p.name}${p.required === false ? ' (optional)' : ''}`} hint={`${p.unit ?? ''} ${p.min !== undefined || p.max !== undefined ? `[${p.min ?? '−∞'} … ${p.max ?? '∞'}]` : ''}`} htmlFor={`mi-${p.name}`}>
                  <input id={`mi-${p.name}`} className="input" inputMode="decimal" value={inputs[p.name] ?? ''} onChange={(e) => setInputs((s) => ({ ...s, [p.name]: e.target.value }))} />
                </Field>
              ))}
            </div>
            <div className="row"><button className="btn primary" onClick={execute} disabled={m.status !== 'enabled'}>Run model locally</button>{m.status !== 'enabled' && <span className="small faint">Enable this model in the Control Board first.</span>}</div>
            {run && (<div className="stack" style={{ borderTop: '1px solid var(--line)', paddingTop: '0.7rem' }}>
              {run.status === 'success' ? <ResultView outputs={run.outputs ?? {}} /> : <ErrorNote error={run.error} />}
              <ProvenanceBlock run={run} onRerun={setRun} />
            </div>)}
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ run history */

export function RunHistory({ allDestinations = false }: { allDestinations?: boolean }) {
  const { destinationId } = useApp();
  const [scope, setScope] = useState<'dest' | 'all'>(allDestinations ? 'all' : 'dest');
  const { data: runs, loading } = useApi<Run[]>(`/runs${qs({ destination_id: scope === 'dest' ? destinationId : undefined, limit: 500 })}`);
  const [sel, setSel] = useState<string | null>(null);
  return (
    <div className="stack">
      <Panel title="Run history" sub="append-only provenance records" tight actions={
        <div className="btn-group"><button className={`btn sm ${scope === 'dest' ? 'on' : ''}`} onClick={() => setScope('dest')}>This destination</button><button className={`btn sm ${scope === 'all' ? 'on' : ''}`} onClick={() => setScope('all')}>All</button></div>
      }>
        {loading && !runs ? <div className="panel-body"><SkeletonBlock /></div> : (
          <DataTable rows={runs ?? []} rowKey={(r) => r.id} onRowClick={(r) => setSel(r.id)} selectedKey={sel} csvName="runs" tall
            empty={<EmptyState title="No runs yet">Run any calculation, forecast or model — each run is recorded here with its inputs and provenance.</EmptyState>}
            columns={[
              { key: 'created_at', label: 'When', render: (r) => fmtDate(r.created_at) },
              { key: 'kind', label: 'Kind', filter: true },
              { key: 'method_name', label: 'Method', render: (r) => <span className="row">{r.method_name}{r.is_demo && <DemoBadge />}{r.screening && <ScreeningBadge />}</span> },
              { key: 'method_version', label: 'Ver.' },
              { key: 'destination_id', label: 'Destination', filter: true },
              { key: 'status', label: 'Status', filter: true, render: (r) => <StatusBadge status={r.status === 'success' ? 'ok' : 'risk'} label={r.status} /> },
              { key: 'headline', label: 'Result', wrap: true },
              { key: 'dataset_id', label: 'Dataset', hidden: true },
              { key: 'id', label: 'Run id', hidden: true },
            ]} />
        )}
      </Panel>
      {sel && <RunDetail id={sel} onClose={() => setSel(null)} />}
    </div>
  );
}

export function RunDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { data: run, setData } = useApi<Run>(`/runs/${id}`);
  if (!run) return <Panel title="Loading run…"><SkeletonBlock /></Panel>;
  return (
    <Panel title={run.method_name} sub={run.id} actions={<button className="btn ghost sm" onClick={onClose} aria-label="Close">✕</button>}>
      <div className="stack">
        {run.status === 'success' ? <ResultView outputs={run.outputs ?? {}} /> : <ErrorNote error={run.error} />}
        <ProvenanceBlock run={run} onRerun={(r) => setData(r)} />
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ briefs */

export function BriefBuilder() {
  const { destinationId, destination, toast, bump } = useApp();
  const { data: runs } = useApi<Run[]>(`/runs${qs({ destination_id: destinationId, status: 'success', limit: 200 })}`);
  const { data: briefs } = useApi<{ id: string; title: string; created_at: string; run_ids: string[]; destination_id: string }[]>('/briefs');
  const [sel, setSel] = useState<string[]>([]);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [recs, setRecs] = useState('');
  const [view, setView] = useState<string | null>(null);
  const create = async () => {
    try {
      const b = await post<{ id: string }>('/briefs', { title: title || `${destination?.name ?? destinationId} — policy brief`, destination_id: destinationId, run_ids: sel, summary,
        recommendations: recs.split('\n').map((s) => s.trim()).filter(Boolean) });
      toast('Brief generated', 'ok'); setView(b.id); setSel([]); bump();
    } catch (e) { toast(errMsg(e), 'error'); }
  };
  return (
    <div className="stack">
      <Panel title="Policy-brief generator" sub="Markdown / HTML from selected runs — every figure carries its run id">
        <div className="grid g2">
          <div className="stack">
            <Field label="Title" htmlFor="b-title"><input id="b-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={`${destination?.name ?? ''} — policy brief`} /></Field>
            <Field label="Summary (your interpretation)" htmlFor="b-sum"><textarea id="b-sum" className="textarea" value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
            <Field label="Recommendations (one per line)" htmlFor="b-recs"><textarea id="b-recs" className="textarea" value={recs} onChange={(e) => setRecs(e.target.value)} /></Field>
            <div className="row"><button className="btn primary" onClick={create} disabled={!sel.length}>Generate brief ({sel.length} run{sel.length === 1 ? '' : 's'})</button></div>
          </div>
          <div className="stack">
            <span className="label">Select runs ({destination?.name})</span>
            {!runs?.length ? <EmptyState title="No successful runs yet">Run calculations in the cores first, then assemble them into a brief.</EmptyState> : (
              <div className="table-wrap" style={{ maxHeight: '20rem' }}>
                <table className="data"><tbody>{runs.map((r) => (
                  <tr key={r.id} className={sel.includes(r.id) ? 'selected' : ''}>
                    <td><input type="checkbox" checked={sel.includes(r.id)} onChange={() => setSel((s) => (s.includes(r.id) ? s.filter((x) => x !== r.id) : [...s, r.id]))} aria-label={`Include ${r.id}`} /></td>
                    <td className="small">{r.method_name}{r.is_demo && <> <DemoBadge /></>}<div className="tiny faint">{r.headline}</div></td>
                    <td className="tiny faint">{fmtDate(r.created_at)}</td>
                  </tr>))}</tbody></table>
              </div>
            )}
          </div>
        </div>
      </Panel>
      <Panel title="Briefs" tight>
        <DataTable rows={briefs ?? []} rowKey={(b) => b.id} onRowClick={(b) => setView(b.id)} selectedKey={view}
          empty={<EmptyState title="No briefs yet" />}
          columns={[{ key: 'title', label: 'Title' }, { key: 'destination_id', label: 'Destination' }, { key: 'runs', label: 'Runs', value: (b) => b.run_ids.length, num: true },
            { key: 'created_at', label: 'Created', render: (b) => fmtDate(b.created_at) },
            { key: 'dl', label: '', value: () => '', render: (b) => <span className="row"><a className="btn sm" href={href(`/briefs/${b.id}/brief.md`)} download onClick={(e) => e.stopPropagation()}>.md</a><a className="btn sm" href={href(`/briefs/${b.id}/brief.html?download=true`)} download onClick={(e) => e.stopPropagation()}>.html</a></span> }]} />
      </Panel>
      {view && (
        <Panel title="Preview" actions={<span className="row"><a className="btn sm" href={href(`/briefs/${view}/brief.html`)} target="_blank" rel="noreferrer">Open / print</a><button className="btn ghost sm" onClick={() => setView(null)}>✕</button></span>}>
          <iframe className="iframe-brief" title="Brief preview" src={href(`/briefs/${view}/brief.html`)} />
        </Panel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ glossary & citation */

export function GlossaryCitation() {
  const { data: terms } = useApi<{ term: string; id: string | null; unit: string; core: string; definition: string; source: string; thresholds: { direction: string; watch: number; risk: number } | null }[]>('/glossary');
  const { data: cit } = useApi<{ cff: string; platform_bibtex: string; bibtex_all: string; how_to_cite_run: string }>('/citation');
  return (
    <div className="stack">
      <Panel title="Indicator glossary" tight>
        <DataTable rows={(terms ?? []).map((t, i) => ({ ...t, _k: `${t.term}-${i}` }))} rowKey={(t) => t._k} csvName="glossary" tall
          columns={[{ key: 'term', label: 'Term' }, { key: 'unit', label: 'Unit' }, { key: 'core', label: 'Core', filter: true },
            { key: 'definition', label: 'Definition', wrap: true },
            { key: 'thresholds', label: 'Status thresholds', value: (t) => (t.thresholds ? `${t.thresholds.direction === 'up_bad' ? 'higher = worse' : 'higher = better'}; watch ${t.thresholds.watch}, risk ${t.thresholds.risk}` : '') },
            { key: 'source', label: 'Source', hidden: true }]} />
      </Panel>
      <div className="grid g2">
        <Panel title="Cite the platform" actions={cit ? <CopyButton text={cit.platform_bibtex} label="Copy BibTeX" /> : null}>
          <pre className="formula tiny">{cit?.platform_bibtex}</pre>
          <p className="small muted" style={{ marginTop: '0.5rem' }}>{cit?.how_to_cite_run}</p>
        </Panel>
        <Panel title="CITATION.cff" actions={cit ? <CopyButton text={cit.cff} /> : null}><pre className="formula tiny">{cit?.cff}</pre></Panel>
      </div>
      <Panel title="All method references (BibTeX)" actions={cit ? <CopyButton text={cit.bibtex_all} label="Copy all" /> : null}>
        <pre className="formula tiny" style={{ maxHeight: '24rem', overflow: 'auto' }}>{cit?.bibtex_all}</pre>
      </Panel>
    </div>
  );
}

export function VrArRoadmap() {
  return (
    <Panel title="VR / AR field visualisation" actions={<span className="badge">roadmap — not functional</span>}>
      <div className="stack small">
        <div className="callout">This is a labelled <b>roadmap placeholder</b>. OpenDMO v2.0 contains no VR/AR functionality and makes no network connections for it.</div>
        <p className="muted">Planned scope (not scheduled): offline 360° site imagery linked to heritage assets; AR overlays of carrying-capacity zones for field staff; immersive briefings of scenario outcomes for community consultation. Contributions welcome — see the README roadmap.</p>
      </div>
    </Panel>
  );
}
