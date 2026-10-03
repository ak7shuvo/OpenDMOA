'use client';

import { useState, type ReactNode } from 'react';
import { del, patch, post, errMsg, qs } from '@/lib/api';
import { useApi, useApp } from '@/lib/state';
import type { Row } from '@/lib/types';
import { DataTable, type Column } from '../ui/DataTable';
import { DemoBadge, EmptyState, ErrorNote, Field, Modal, Panel, SkeletonBlock, StatusBadge } from '../ui';

export interface FieldSpec {
  key: string; label: string; type?: 'text' | 'select' | 'number' | 'bool' | 'date' | 'datetime' | 'list' | 'textarea';
  options?: string[]; required?: boolean; inTable?: boolean; status?: Record<string, 'ok' | 'watch' | 'risk'>; num?: boolean; wrap?: boolean; hint?: string;
}

/** Generic register (assets, incidents, warnings, projects, publications…) with add / edit / delete. */
export function EntityTable({ entity, title, fields, scoped = true, sub, actions, onRows, emptyText }: {
  entity: string; title: string; fields: FieldSpec[]; scoped?: boolean; sub?: string; actions?: ReactNode;
  onRows?: (rows: Row[]) => ReactNode; emptyText?: string;
}) {
  const { destinationId, toast, bump } = useApp();
  const { data, error, loading } = useApi<Row[]>(`/${entity}${qs(scoped ? { destination_id: destinationId } : {})}`);
  const [editing, setEditing] = useState<Row | 'new' | null>(null);

  const remove = async (r: Row) => {
    if (!window.confirm(`Delete “${String(r.name ?? r.title ?? r.item ?? r.id)}”? This is recorded in the audit log.`)) return;
    try { await del(`/${entity}/${r.id}`); toast('Deleted', 'ok'); bump(); } catch (e) { toast(errMsg(e), 'error'); }
  };
  const toggleBool = async (r: Row, key: string) => {
    try { await patch(`/${entity}/${r.id}`, { [key]: !r[key] }); bump(); } catch (e) { toast(errMsg(e), 'error'); }
  };

  const columns: Column<Row>[] = [
    ...fields.filter((f) => f.inTable !== false).map((f): Column<Row> => ({
      key: f.key, label: f.label, num: f.num, wrap: f.wrap, filter: f.type === 'select',
      value: (r) => (Array.isArray(r[f.key]) ? (r[f.key] as string[]).join(', ') : r[f.key]),
      render: f.type === 'bool' ? (r) => <input type="checkbox" checked={Boolean(r[f.key])} onChange={() => toggleBool(r, f.key)} aria-label={f.label} />
        : f.status ? (r) => <StatusBadge status={f.status![String(r[f.key])] ?? 'none'} label={String(r[f.key] ?? '—')} />
        : undefined,
    })),
    { key: '_demo', label: 'Source', value: (r) => (r.is_demo ? 'DEMO' : 'user'), render: (r) => (r.is_demo ? <DemoBadge /> : <span className="faint tiny">user</span>) },
    { key: '_act', label: '', value: () => '', render: (r) => (
      <span className="row" style={{ flexWrap: 'nowrap' }}>
        <button className="btn ghost sm" onClick={(e) => { e.stopPropagation(); setEditing(r); }}>Edit</button>
        <button className="btn ghost sm" onClick={(e) => { e.stopPropagation(); void remove(r); }} aria-label="Delete">✕</button>
      </span>
    ) },
  ];

  return (
    <Panel title={title} sub={sub} tight actions={<span className="row">{actions}<button className="btn primary sm" onClick={() => setEditing('new')}>+ Add</button></span>}>
      <ErrorNote error={error} />
      {loading && !data ? <div className="panel-body"><SkeletonBlock /></div> : (
        <>
          {onRows && data && <div style={{ padding: '0.6rem 0.8rem', borderBottom: '1px solid var(--line)' }}>{onRows(data)}</div>}
          <DataTable columns={columns} rows={data ?? []} rowKey={(r) => r.id} csvName={`${entity}-${destinationId}`}
            empty={<EmptyState title={`No ${title.toLowerCase()} yet`} action={<button className="btn primary sm" onClick={() => setEditing('new')}>+ Add the first one</button>}>{emptyText}</EmptyState>} />
        </>
      )}
      {editing && <EntityForm entity={entity} fields={fields} row={editing === 'new' ? null : editing} scoped={scoped} onClose={() => setEditing(null)} />}
    </Panel>
  );
}

function EntityForm({ entity, fields, row, scoped, onClose }: { entity: string; fields: FieldSpec[]; row: Row | null; scoped: boolean; onClose: () => void }) {
  const { destinationId, toast, bump } = useApp();
  const [v, setV] = useState<Record<string, unknown>>(() => Object.fromEntries(fields.map((f) => [f.key,
    row ? (Array.isArray(row[f.key]) ? (row[f.key] as string[]).join(', ') : row[f.key] ?? '') : f.type === 'bool' ? false : f.options?.[0] ?? ''])));
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    const body: Record<string, unknown> = {};
    for (const f of fields) {
      let x = v[f.key];
      if (f.type === 'number') x = x === '' || x === null ? null : Number(x);
      if (f.type === 'list') x = String(x ?? '').split(',').map((s) => s.trim()).filter(Boolean);
      body[f.key] = x;
    }
    if (scoped && !row) body.destination_id = destinationId;
    try {
      if (row) await patch(`/${entity}/${row.id}`, body); else await post(`/${entity}`, body);
      toast(row ? 'Saved' : 'Added', 'ok');
      bump();
      onClose();
    } catch (e) { setErr(errMsg(e)); }
  };
  return (
    <Modal title={row ? 'Edit record' : 'Add record'} onClose={onClose} footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save}>Save</button></>}>
      <div className="stack">
        <ErrorNote error={err} />
        <div className="form-grid">
          {fields.map((f) => {
            const id = `f-${f.key}`;
            const val = v[f.key];
            const set = (x: unknown) => setV((s) => ({ ...s, [f.key]: x }));
            let input: ReactNode;
            if (f.type === 'select') input = <select id={id} className="select" value={String(val ?? '')} onChange={(e) => set(e.target.value)}>{f.options?.map((o) => <option key={o}>{o}</option>)}</select>;
            else if (f.type === 'bool') input = <label className="checkbox"><input id={id} type="checkbox" checked={Boolean(val)} onChange={(e) => set(e.target.checked)} />yes</label>;
            else if (f.type === 'textarea') input = <textarea id={id} className="textarea" value={String(val ?? '')} onChange={(e) => set(e.target.value)} />;
            else input = <input id={id} className="input" type={f.type === 'date' ? 'date' : f.type === 'datetime' ? 'datetime-local' : 'text'} inputMode={f.type === 'number' ? 'decimal' : undefined} value={String(val ?? '')} onChange={(e) => set(e.target.value)} />;
            return <div key={f.key} style={f.type === 'textarea' ? { gridColumn: '1 / -1' } : undefined}><Field label={`${f.label}${f.required ? ' *' : ''}`} hint={f.hint ?? (f.type === 'list' ? 'comma-separated' : undefined)} htmlFor={id}>{input}</Field></div>;
          })}
        </div>
      </div>
    </Modal>
  );
}
