'use client';

import Link from 'next/link';
import { Fragment, useEffect, useState, type ReactNode } from 'react';
import { fmtDate, fmtNum, fmtPct } from '@/lib/format';
import type { Kpi, Status } from '@/lib/types';
import { Sparkline } from '../charts/Sparkline';

export function Panel({ title, sub, actions, children, tight, className = '', id }: {
  title?: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode; tight?: boolean; className?: string; id?: string;
}) {
  return (
    <section className={`panel ${className}`} id={id}>
      {(title || actions) && (
        <header className="panel-head">
          {title && <h2 className="panel-title">{title}</h2>}
          {sub && <span className="panel-sub">{sub}</span>}
          <span style={{ flex: 1 }} />
          {actions}
        </header>
      )}
      <div className={`panel-body ${tight ? 'tight' : ''}`}>{children}</div>
    </section>
  );
}

export function StatusBadge({ status, label }: { status: Status | string | null | undefined; label?: string }) {
  const s = (['ok', 'watch', 'risk'].includes(String(status)) ? status : 'none') as Status;
  return <span className={`badge ${s}`}><span className={`dot ${s}`} />{label ?? (s === 'none' ? 'n/a' : s)}</span>;
}

export function DemoBadge({ title = 'Synthetic DEMO data — not real observations' }: { title?: string }) {
  return <span className="badge demo" title={title}>DEMO</span>;
}

export function ScreeningBadge() {
  return <span className="badge screening" title="Screening indicator — not a certification or regulatory determination">Screening</span>;
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-title">{title}</span>
      {children && <span>{children}</span>}
      {action && <div className="row">{action}</div>}
    </div>
  );
}

export function NoDataState({ what = 'data' }: { what?: string }) {
  return (
    <EmptyState title={`No ${what} for this destination and time range`}>
      Import a CSV for this destination, widen the time range, or load the DEMO seed pack.
      <span className="row" style={{ marginTop: '0.4rem' }}>
        <Link className="btn primary sm" href="/import/">Import CSV</Link>
        <Link className="btn sm" href="/system/control-board/#data">Load DEMO data</Link>
      </span>
    </EmptyState>
  );
}

export function Skeleton({ h = '1rem', w = '100%', style }: { h?: string; w?: string; style?: React.CSSProperties }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} aria-hidden />;
}

export function SkeletonBlock({ lines = 4 }: { lines?: number }) {
  return (
    <div className="stack" style={{ gap: '0.45rem' }} aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <Skeleton key={i} w={`${92 - i * 9}%`} />)}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="callout red" role="alert">{error}</div>;
}

export function Tabs<T extends string>({ tabs, active, onChange }: { tabs: { id: T; label: ReactNode }[]; active: T; onChange: (t: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={active === t.id} className={`tab ${active === t.id ? 'active' : ''}`} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({ title, onClose, children, wide, footer }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; footer?: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="panel-head">
          <h2 className="panel-title">{title}</h2>
          <span style={{ flex: 1 }} />
          <button className="btn ghost sm" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="panel-body">{children}</div>
        {footer && <footer className="panel-head" style={{ borderTop: '1px solid var(--line)', borderBottom: 0, justifyContent: 'flex-end' }}>{footer}</footer>}
      </div>
    </div>
  );
}

/** Destructive action guarded by typing a confirmation word. */
export function ConfirmTyped({ word, title, body, onConfirm, onClose, busy }: {
  word: string; title: string; body: ReactNode; onConfirm: () => void; onClose: () => void; busy?: boolean;
}) {
  const [v, setV] = useState('');
  return (
    <Modal title={title} onClose={onClose} footer={<>
      <button className="btn ghost" onClick={onClose}>Cancel</button>
      <button className="btn danger" disabled={v !== word || busy} onClick={onConfirm}>{busy ? 'Working…' : title}</button>
    </>}>
      <div className="stack">
        <div className="callout red">{body}</div>
        <div className="field">
          <label htmlFor="confirm-word">Type <b>{word}</b> to confirm</label>
          <input id="confirm-word" className="input" value={v} onChange={(e) => setV(e.target.value)} autoFocus autoComplete="off" />
        </div>
      </div>
    </Modal>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: ReactNode; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function KpiCell({ k }: { k: Kpi }) {
  const conf = k.confidence ? `${k.confidence} confidence` : null;
  return (
    <div className={`kpi ${k.status}`} title={k.description}>
      <div className="kpi-label">
        <span className="truncate">{k.label}</span>
        {k.source?.is_demo && <DemoBadge />}
      </div>
      {k.empty ? (
        <div className="kpi-empty">no data in range</div>
      ) : (
        <>
          <div className="kpi-value">
            {fmtNum(k.value, k.decimals)}<span className="kpi-unit">{k.unit}</span>
          </div>
          {k.spark.length > 1 && <Sparkline values={k.spark} status={k.status} />}
          <div className="kpi-meta">
            {k.status !== 'none' && <span className={`dot ${k.status}`} aria-label={`status ${k.status}`} />}
            {k.change_pct !== null && <span title="vs previous equal window">{fmtPct(k.change_pct)}</span>}
            {conf && <span>{conf}</span>}
          </div>
          <div className="kpi-meta" title={k.source ? `${k.source.name} v${k.source.version}` : ''}>
            <span className="truncate">{k.source ? `${k.source.name} v${k.source.version}` : '—'}</span>
            <span>{k.period_label ?? ''}</span>
            <span>upd. {fmtDate(k.timestamp, false)}</span>
          </div>
        </>
      )}
    </div>
  );
}

export function KpiStrip({ kpis, loading }: { kpis: Kpi[] | undefined; loading?: boolean }) {
  if (loading && !kpis) {
    return <div className="kpi-strip">{Array.from({ length: 6 }, (_, i) => <div className="kpi" key={i}><Skeleton h="0.7rem" w="60%" /><Skeleton h="1.5rem" w="80%" /><Skeleton h="0.6rem" /></div>)}</div>;
  }
  return <div className="kpi-strip">{(kpis ?? []).map((k) => <KpiCell key={k.id} k={k} />)}</div>;
}

export function Kv({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v], i) => (<Fragment key={i}><dt>{k}</dt><dd>{v}</dd></Fragment>))}
    </dl>
  );
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button className="btn sm" onClick={async () => {
      try { await navigator.clipboard.writeText(text); } catch {
        const t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove();
      }
      setDone(true); setTimeout(() => setDone(false), 1500);
    }}>{done ? 'Copied ✓' : label}</button>
  );
}
