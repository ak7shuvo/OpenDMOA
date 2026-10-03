'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { href, post, qs, upload, errMsg } from '@/lib/api';
import { fmtBytes, fmtNum, shortHash } from '@/lib/format';
import { useApi, useApp } from '@/lib/state';
import type { CommitResult, Dataset, DatasetKind, Detection, Mapping, ValidationReport } from '@/lib/types';
import { DataTable } from '../ui/DataTable';
import { DemoBadge, ErrorNote, Field, Panel, StatusBadge } from '../ui';

const STEPS = ['Destination & dataset', 'Upload', 'Map columns', 'Dry-run validation', 'Commit'];

export function ImportWizard() {
  const { destinationId, setDestinationId, destinations, toast, bump } = useApp();
  const [step, setStep] = useState(0);
  const { data: datasets } = useApi<Dataset[]>(`/datasets${qs({ destination_id: destinationId, include_archived: false })}`);
  const { data: kinds } = useApi<DatasetKind[]>('/catalog/kinds');
  const [datasetId, setDatasetId] = useState<string>('');
  const [creating, setCreating] = useState(false);
  const [newKind, setNewKind] = useState('visitor_flow');
  const [newName, setNewName] = useState('');
  const [det, setDet] = useState<Detection | null>(null);
  const [opts, setOpts] = useState<{ encoding: string; delimiter: string; has_header: string }>({ encoding: '', delimiter: '', has_header: '' });
  const [mapping, setMapping] = useState<Mapping | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [result, setResult] = useState<CommitResult | null>(null);
  const [skipInvalid, setSkipInvalid] = useState(false);
  const [mode, setMode] = useState<'upsert' | 'insert_only'>('upsert');
  const [paste, setPaste] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [issueFilter, setIssueFilter] = useState<'all' | 'error' | 'warning'>('all');

  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get('dataset');
    if (p) { setDatasetId(p); const dest = p.split('.')[0]; if (dest && destinations.some((d) => d.id === dest)) setDestinationId(dest); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [destinations.length]);

  const ds = datasets?.find((d) => d.id === datasetId) ?? null;
  const vars = ds?.variable_defs ?? [];
  const allowNew = ds?.kind === 'custom' || Boolean(mapping?.create_variables);

  const wrap = async (fn: () => Promise<void>) => { setBusy(true); setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); } };

  const createDataset = () => wrap(async () => {
    const d = await post<Dataset>('/datasets', { destination_id: destinationId, kind: newKind, name: newName || kinds?.find((k) => k.kind === newKind)?.label });
    toast(`Dataset ${d.id} created`, 'ok');
    bump();
    setDatasetId(d.id); setCreating(false); setStep(1);
  });

  const acceptDetection = (d: Detection) => { setDet(d); setMapping({ ...d.suggested_mapping, create_variables: false }); setReport(null); setResult(null); };
  const onFile = (f: File | undefined) => f && wrap(async () => {
    const form = new FormData(); form.append('file', f); form.append('dataset_id', datasetId);
    acceptDetection(await upload<Detection>('/imports/upload', form));
    setOpts({ encoding: '', delimiter: '', has_header: '' });
  });
  const onPaste = () => wrap(async () => {
    const isJson = /^\s*[[{]/.test(paste);
    acceptDetection(await post<Detection>('/imports/paste', { content: paste, file_name: isJson ? 'pasted.json' : 'pasted.csv', dataset_id: datasetId }));
  });
  const redetect = () => det && wrap(async () => {
    acceptDetection(await post<Detection>('/imports/detect', { token: det.token, dataset_id: datasetId, encoding: opts.encoding || null,
      delimiter: opts.delimiter === '\\t' ? '\t' : opts.delimiter || null, has_header: opts.has_header === '' ? null : opts.has_header === 'yes' }));
  });
  const payload = () => ({ token: det!.token, dataset_id: datasetId, mapping, encoding: opts.encoding || null,
    delimiter: opts.delimiter === '\\t' ? '\t' : opts.delimiter || null, has_header: opts.has_header === '' ? null : opts.has_header === 'yes' });
  const validate = () => wrap(async () => { setReport(await post<ValidationReport>('/imports/validate', payload())); setStep(3); });
  const commit = () => wrap(async () => {
    const r = await post<CommitResult>('/imports/commit', { ...payload(), skip_invalid: skipInvalid, mode });
    setResult(r); setStep(4); bump();
    toast(r.status === 'duplicate' ? 'This file was already imported — nothing changed' : `Imported: ${r.inserted} new, ${r.updated} updated`, r.status === 'duplicate' ? 'warn' : 'ok');
  });

  const issues = useMemo(() => (report?.issues ?? []).filter((i) => issueFilter === 'all' || i.level === issueFilter).map((i, k) => ({ ...i, _k: k })), [report, issueFilter]);

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="page-num">DATA</div>
          <h1 className="page-title">Import CSV / JSON</h1>
          <p className="page-lede">The primary way to feed OpenDMO. Detection, column mapping and a full dry-run happen before anything is written. Re-importing the same file never duplicates rows; the file hash is stored in provenance.</p>
        </div>
      </div>
      <div className="steps" role="list">
        {STEPS.map((s, i) => (
          <div key={s} role="listitem" className={`step ${i === step ? 'active' : i < step ? 'done' : ''}`}><b>STEP {i + 1}</b>{s}</div>
        ))}
      </div>
      <ErrorNote error={err} />

      {step === 0 && (
        <Panel title="1 · Choose destination and dataset">
          <div className="stack">
            <div className="form-grid">
              <Field label="Destination" htmlFor="w-dest">
                <select id="w-dest" className="select" value={destinationId} onChange={(e) => { setDestinationId(e.target.value); setDatasetId(''); }}>
                  {destinations.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
              <Field label="Existing dataset" htmlFor="w-ds" hint="archived datasets are immutable and not listed">
                <select id="w-ds" className="select" value={datasetId} onChange={(e) => { setDatasetId(e.target.value); setCreating(false); }}>
                  <option value="">— choose —</option>
                  {datasets?.map((d) => <option key={d.id} value={d.id}>{d.is_demo ? '[DEMO] ' : ''}{d.name} v{d.version} · {d.kind_label}</option>)}
                </select>
              </Field>
            </div>
            <div className="row"><button className="btn" onClick={() => { setCreating(true); setDatasetId(''); }}>+ Create a new dataset</button></div>
            {creating && (
              <div className="panel panel-body stack">
                <div className="form-grid">
                  <Field label="Dataset type (template)" htmlFor="w-kind">
                    <select id="w-kind" className="select" value={newKind} onChange={(e) => setNewKind(e.target.value)}>
                      {kinds?.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
                    </select>
                  </Field>
                  <Field label="Name" htmlFor="w-name" hint="e.g. Gate counts 2024 (Tourist Police)"><input id="w-name" className="input" value={newName} onChange={(e) => setNewName(e.target.value)} /></Field>
                </div>
                <p className="small muted">{kinds?.find((k) => k.kind === newKind)?.description} Variables: {kinds?.find((k) => k.kind === newKind)?.variables.map((v) => v.name).join(', ') || 'defined from your CSV columns'}.</p>
                <div className="row">
                  <button className="btn primary" onClick={createDataset} disabled={busy}>Create dataset</button>
                  <a className="btn" href={href(`/catalog/kinds/${newKind}/template.csv?layout=wide`)} download>Template (wide)</a>
                  <a className="btn" href={href(`/catalog/kinds/${newKind}/template.csv?layout=long`)} download>Template (long)</a>
                </div>
              </div>
            )}
            {ds && (
              <div className="callout plain small">
                <div className="row">{ds.name} v{ds.version} {ds.is_demo && <DemoBadge />} · {ds.observations} observations · quality {fmtNum(ds.quality_score)}</div>
                <div className="faint">Variables: {vars.map((v) => `${v.name} (${v.unit || '—'})`).join(', ') || 'none yet — they will be created from your columns'}</div>
                {ds.is_demo && <div style={{ color: 'var(--watch)' }}>Importing into a DEMO dataset mixes real and synthetic values — consider creating a new dataset instead.</div>}
              </div>
            )}
            <div className="row">
              <button className="btn primary" disabled={!datasetId} onClick={() => setStep(1)}>Next: upload</button>
              {ds && <a className="btn" href={href(`/datasets/${ds.id}/template.csv?layout=wide`)} download>Download template for this dataset</a>}
            </div>
          </div>
        </Panel>
      )}

      {step === 1 && (
        <Panel title="2 · Upload a file or paste data" sub={ds ? `into ${ds.id}` : ''}>
          <div className="stack">
            <label className={`dropzone ${over ? 'over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]); }}>
              <input type="file" accept=".csv,.tsv,.txt,.json,text/csv,application/json" hidden onChange={(e) => onFile(e.target.files?.[0])} />
              <div><b>Drop a CSV / TSV / JSON file here</b> or click to choose</div>
              <div className="tiny faint">Delimiter (, ; tab |), encoding (UTF-8, UTF-8-BOM, UTF-16, Windows-1252) and header row are detected automatically · max 50 MB</div>
            </label>
            <details>
              <summary>…or paste CSV / JSON text</summary>
              <textarea className="textarea" style={{ minHeight: '8rem' }} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder={'period,visitors,daily_peak\n2025-01,52000,6100\n\n[{"period":"2025-01","variable":"visitors","value":52000}]'} />
              <button className="btn" style={{ marginTop: '0.4rem' }} onClick={onPaste} disabled={!paste.trim() || busy}>Use pasted data</button>
            </details>
            {det && (
              <>
                <div className="grid g4">
                  <div className="panel panel-body"><div className="label">File</div><div className="small truncate">{det.file_name}</div><div className="tiny faint">{fmtBytes(det.size)} · {shortHash(det.file_hash)}</div></div>
                  <div className="panel panel-body"><div className="label">Format</div><div className="small">{det.format} · {det.encoding}</div><div className="tiny faint">delimiter {det.delimiter === '\t' ? 'TAB' : det.delimiter ? `“${det.delimiter}”` : 'n/a'}</div></div>
                  <div className="panel panel-body"><div className="label">Rows × columns</div><div className="small">{det.n_rows} × {det.columns.length}</div><div className="tiny faint">header: {det.has_header ? 'yes' : 'no'}</div></div>
                  <div className="panel panel-body"><div className="label">Layout guess</div><div className="small">{det.suggested_mapping.layout === 'long' ? 'long (period, variable, value)' : 'wide (one column per variable)'}</div></div>
                </div>
                {det.format === 'csv' && (
                  <div className="row">
                    <span className="label">Override:</span>
                    <select className="select sm" value={opts.delimiter} onChange={(e) => setOpts({ ...opts, delimiter: e.target.value })} aria-label="Delimiter"><option value="">delimiter: auto</option><option value=",">,</option><option value=";">;</option><option value="\t">TAB</option><option value="|">|</option></select>
                    <select className="select sm" value={opts.encoding} onChange={(e) => setOpts({ ...opts, encoding: e.target.value })} aria-label="Encoding"><option value="">encoding: auto</option><option value="utf-8">utf-8</option><option value="utf-8-sig">utf-8-sig</option><option value="utf-16">utf-16</option><option value="cp1252">cp1252</option><option value="latin-1">latin-1</option></select>
                    <select className="select sm" value={opts.has_header} onChange={(e) => setOpts({ ...opts, has_header: e.target.value })} aria-label="Header row"><option value="">header: auto</option><option value="yes">has header</option><option value="no">no header</option></select>
                    <button className="btn sm" onClick={redetect}>Re-detect</button>
                  </div>
                )}
              </>
            )}
            <div className="row">
              <button className="btn ghost" onClick={() => setStep(0)}>Back</button>
              <button className="btn primary" disabled={!det} onClick={() => setStep(2)}>Next: map columns</button>
            </div>
          </div>
        </Panel>
      )}

      {step === 2 && det && mapping && (
        <Panel title="3 · Map columns" sub={`${det.columns.length} columns · preview of first ${det.preview.length} rows`}>
          <div className="stack">
            <div className="form-grid">
              <Field label="Layout" htmlFor="m-layout">
                <select id="m-layout" className="select" value={mapping.layout} onChange={(e) => setMapping({ ...mapping, layout: e.target.value as Mapping['layout'] })}>
                  <option value="wide">wide — one column per variable</option><option value="long">long — period, variable, value[, unit]</option>
                </select>
              </Field>
              <ColSelect label="Period / date column" value={mapping.period_column} columns={det.columns} onChange={(v) => setMapping({ ...mapping, period_column: v })} />
              <Field label="Day/month order for dates like 03/04/2025" htmlFor="m-df">
                <select id="m-df" className="select" value={mapping.date_format} onChange={(e) => setMapping({ ...mapping, date_format: e.target.value })}><option value="DMY">DD/MM/YYYY</option><option value="MDY">MM/DD/YYYY</option></select>
              </Field>
              <Field label="Decimal separator" htmlFor="m-dec">
                <select id="m-dec" className="select" value={mapping.decimal} onChange={(e) => setMapping({ ...mapping, decimal: e.target.value })}><option value=".">. (1,234.5)</option><option value=",">, (1.234,5)</option></select>
              </Field>
              {mapping.layout === 'long' && (<>
                <ColSelect label="Variable column" value={mapping.variable_column} columns={det.columns} onChange={(v) => setMapping({ ...mapping, variable_column: v })} />
                <ColSelect label="Value column" value={mapping.value_column} columns={det.columns} onChange={(v) => setMapping({ ...mapping, value_column: v })} />
                <ColSelect label="Unit column (optional)" value={mapping.unit_column} columns={det.columns} optional onChange={(v) => setMapping({ ...mapping, unit_column: v })} />
                <ColSelect label="Quality-flag column (optional)" value={mapping.flag_column} columns={det.columns} optional onChange={(v) => setMapping({ ...mapping, flag_column: v })} />
              </>)}
            </div>
            {ds?.kind !== 'custom' && (
              <label className="checkbox"><input type="checkbox" checked={Boolean(mapping.create_variables)} onChange={(e) => setMapping({ ...mapping, create_variables: e.target.checked })} />Add unknown variables to this dataset’s definition</label>
            )}
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>{det.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                  {mapping.layout === 'wide' && (
                    <tr>{det.columns.map((c) => (
                      <th key={c} style={{ top: '1.9rem', textTransform: 'none' }}>
                        {c === mapping.period_column ? <span className="badge red">period</span> : (
                          <select className="select sm" value={mapping.columns[c] ?? ''} aria-label={`Map ${c}`}
                            onChange={(e) => setMapping({ ...mapping, columns: { ...mapping.columns, [c]: e.target.value || null } })}>
                            <option value="">ignore</option>
                            {vars.map((v) => <option key={v.name} value={v.name}>{v.name} ({v.unit || '—'})</option>)}
                            {allowNew && !vars.some((v) => v.name === c) && <option value={c.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')}>new: {c}</option>}
                          </select>
                        )}
                      </th>
                    ))}</tr>
                  )}
                </thead>
                <tbody>{det.preview.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="nowrap">{c}</td>)}</tr>)}</tbody>
              </table>
            </div>
            <div className="row">
              <button className="btn ghost" onClick={() => setStep(1)}>Back</button>
              <button className="btn primary" onClick={validate} disabled={busy}>{busy ? 'Validating…' : 'Run dry-run validation'}</button>
            </div>
          </div>
        </Panel>
      )}

      {step === 3 && report && (
        <div className="stack">
          <Panel title="4 · Dry-run validation" sub="nothing has been written yet">
            <div className="stack">
              <div className="result-grid">
                {[['rows in file', report.rows_total], ['valid values', report.valid_cells], ['errors', report.errors], ['warnings', report.warnings],
                  ['will insert', report.will_insert], ['will update', report.will_update], ['unchanged', report.unchanged]].map(([k, v]) => (
                  <div key={String(k)} className="result-cell"><div className="k">{k}</div><div className="v" style={{ color: k === 'errors' && Number(v) ? 'var(--risk)' : k === 'warnings' && Number(v) ? 'var(--watch)' : undefined }}>{fmtNum(v as number)}</div></div>
                ))}
              </div>
              {report.already_imported && <div className="callout">This exact file was already imported ({report.already_imported}). Committing again will not change anything.</div>}
              {report.new_variables.length > 0 && <div className="callout plain small">New variables will be added: {report.new_variables.map((v) => v.name).join(', ')}</div>}
              {report.errors > 0 && <div className="callout red small">{report.errors} cell(s) have errors and cannot be imported. Fix the file, adjust the mapping, or tick “skip invalid” to import the valid cells only.</div>}
            </div>
          </Panel>
          <Panel title="Row-level issues" tight actions={
            <div className="btn-group">{(['all', 'error', 'warning'] as const).map((f) => <button key={f} className={`btn sm ${issueFilter === f ? 'on' : ''}`} onClick={() => setIssueFilter(f)}>{f}</button>)}</div>
          }>
            <DataTable rows={issues} rowKey={(i) => String(i._k)} csvName="import-issues" initialSort={{ key: 'row', dir: 'asc' }}
              empty={<div className="callout ok">No issues — every value passed type, range, duplicate, missing and unit checks.</div>}
              columns={[
                { key: 'level', label: 'Level', render: (i) => <StatusBadge status={i.level === 'error' ? 'risk' : 'watch'} label={i.level} /> },
                { key: 'row', label: 'Line', num: true }, { key: 'column', label: 'Column' }, { key: 'code', label: 'Check', filter: true },
                { key: 'message', label: 'Message', wrap: true },
              ]} />
            {report.issues_truncated && <p className="tiny faint" style={{ padding: '0.4rem 0.6rem' }}>Only the first 1000 issues are listed.</p>}
          </Panel>
          <Panel title="Normalised preview" sub="first 50 values as they will be stored" tight>
            <DataTable rows={report.preview_observations.map((o, i) => ({ ...o, _k: i }))} rowKey={(o) => String(o._k)} searchable={false}
              columns={[{ key: 'line', label: 'Line', num: true }, { key: 'period', label: 'Period' }, { key: 'variable', label: 'Variable' },
                { key: 'value', label: 'Value', num: true }, { key: 'unit', label: 'Unit' }, { key: 'quality_flag', label: 'Flag' },
                { key: 'action', label: 'Action', render: (o) => <StatusBadge status={o.action === 'insert' ? 'ok' : o.action === 'update' ? 'watch' : 'none'} label={o.action} /> },
                { key: 'previous', label: 'Previous', num: true }]} />
          </Panel>
          <Panel title="Commit">
            <div className="row">
              <label className="checkbox"><input type="checkbox" checked={skipInvalid} onChange={(e) => setSkipInvalid(e.target.checked)} disabled={!report.errors} />Skip invalid cells ({report.errors})</label>
              <select className="select sm" value={mode} onChange={(e) => setMode(e.target.value as typeof mode)} aria-label="Existing values">
                <option value="upsert">update existing values</option><option value="insert_only">keep existing values (insert new only)</option>
              </select>
              <span style={{ flex: 1 }} />
              <button className="btn ghost" onClick={() => setStep(2)}>Back to mapping</button>
              <button className="btn primary" onClick={commit} disabled={busy || (report.errors > 0 && !skipInvalid) || report.archived}>{busy ? 'Importing…' : 'Commit import'}</button>
            </div>
          </Panel>
        </div>
      )}

      {step === 4 && result && (
        <Panel title="5 · Import complete">
          <div className="stack">
            <div className={`callout ${result.status === 'duplicate' ? '' : 'ok'}`}>{result.status === 'duplicate' ? result.message : `Committed import ${result.import_id}: ${result.inserted} inserted, ${result.updated} updated, ${result.unchanged} unchanged, ${result.skipped ?? 0} skipped.`}</div>
            {result.quality && <p className="small">Dataset quality now {fmtNum(result.quality.quality_score)} / 100 ({result.quality.level}) · completeness {fmtNum(result.quality.completeness_pct)} % · {result.quality.n_gaps} gap(s).</p>}
            <p className="tiny faint">File hash {result.file_hash} stored in the dataset provenance.</p>
            <div className="row">
              <Link className="btn primary" href="/research-lab/#datasets">Open in Dataset Explorer</Link>
              <Link className="btn" href="/observatory/">Go to the cores</Link>
              <button className="btn ghost" onClick={() => { setDet(null); setReport(null); setResult(null); setPaste(''); setStep(1); }}>Import another file</button>
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}

function ColSelect({ label, value, columns, onChange, optional }: { label: string; value: string | null; columns: string[]; onChange: (v: string | null) => void; optional?: boolean }) {
  const id = `col-${label.replace(/\W+/g, '-')}`;
  return (
    <Field label={label} htmlFor={id}>
      <select id={id} className="select" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">{optional ? '— none —' : '— choose —'}</option>
        {columns.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
    </Field>
  );
}
