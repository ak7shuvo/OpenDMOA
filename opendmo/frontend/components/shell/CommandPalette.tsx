'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { post, errMsg } from '@/lib/api';
import { CORES, SYSTEM_TABS, methodRoute } from '@/lib/nav';
import { useApi, useApp } from '@/lib/state';
import type { Method } from '@/lib/types';

interface Cmd { id: string; label: string; hint: string; run: () => void | Promise<void> }

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen, destinations, setDestinationId, destinationId, theme, setTheme, toast, bump } = useApp();
  const router = useRouter();
  const [q, setQ] = useState('');
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: methods } = useApi<Method[]>(paletteOpen ? '/methods' : null);

  const go = (href: string) => {
    setPaletteOpen(false);
    const [path, hash] = href.split('#');
    if (window.location.pathname === path && hash) window.location.hash = hash;
    else router.push(href);
  };

  const cmds = useMemo<Cmd[]>(() => {
    const out: Cmd[] = [
      { id: 'home', label: 'Overview', hint: 'page', run: () => go('/') },
      { id: 'import', label: 'Import CSV / JSON', hint: 'data', run: () => go('/import/') },
    ];
    for (const c of CORES) {
      out.push({ id: c.id, label: `${c.num} ${c.name}`, hint: 'core', run: () => go(c.route) });
      for (const t of c.tabs) out.push({ id: `${c.id}-${t.id}`, label: `${c.name} › ${t.name}`, hint: 'module', run: () => go(`${c.route}#${t.id}`) });
    }
    for (const t of SYSTEM_TABS) out.push({ id: `sys-${t.id}`, label: `Control Board › ${t.name}`, hint: 'system', run: () => go(`/system/control-board/#${t.id}`) });
    for (const d of destinations) out.push({ id: `dest-${d.id}`, label: `Switch destination: ${d.name}`, hint: d.region, run: () => { setDestinationId(d.id); setPaletteOpen(false); } });
    out.push({ id: 'theme', label: `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`, hint: 'action', run: () => { setTheme(theme === 'dark' ? 'light' : 'dark'); setPaletteOpen(false); } });
    out.push({ id: 'demo', label: 'Load DEMO seed pack for current destination', hint: 'action', run: async () => {
      setPaletteOpen(false);
      try { await post(`/system/seed-packs/${destinationId}/load`); toast('DEMO seed pack loaded', 'ok'); bump(); } catch (e) { toast(errMsg(e), 'error'); }
    } });
    for (const m of methods ?? []) out.push({ id: `m-${m.id}`, label: `Method: ${m.name}`, hint: `${m.id} v${m.version}`, run: () => go(methodRoute(m.id)) });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [destinations, methods, theme, destinationId]);

  const shown = useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return cmds.slice(0, 40);
    return cmds.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(n)).slice(0, 60);
  }, [cmds, q]);

  useEffect(() => { if (paletteOpen) { setQ(''); setIdx(0); setTimeout(() => inputRef.current?.focus(), 0); } }, [paletteOpen]);
  useEffect(() => setIdx(0), [q]);
  if (!paletteOpen) return null;

  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && setPaletteOpen(false)}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Command palette">
        <input ref={inputRef} className="palette-input" placeholder="Go to a page, method, destination or action…" value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setIdx((i) => Math.min(shown.length - 1, i + 1)); }
            if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
            if (e.key === 'Enter' && shown[idx]) { e.preventDefault(); void shown[idx].run(); }
          }} aria-label="Command" />
        <div className="palette-list" role="listbox">
          {shown.map((c, i) => (
            <div key={c.id} role="option" aria-selected={i === idx} className={`palette-item ${i === idx ? 'active' : ''}`}
              onMouseEnter={() => setIdx(i)} onClick={() => void c.run()}>
              <span>{c.label}</span><span className="faint">{c.hint}</span>
            </div>
          ))}
          {!shown.length && <div className="palette-item faint">No matches</div>}
        </div>
      </div>
    </div>
  );
}
