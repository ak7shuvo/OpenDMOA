'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { get, errMsg } from './api';
import type { Destination, Meta } from './types';

export type RangePreset = '12m' | '24m' | '36m' | 'all' | 'custom';
export interface TimeRange { preset: RangePreset; start: string | null; end: string | null }
export type Toast = { id: number; kind: 'ok' | 'error' | 'warn' | 'info'; text: string };

interface AppState {
  meta: Meta | null;
  backendOk: boolean | null;
  destinations: Destination[];
  destinationId: string;
  destination: Destination | null;
  setDestinationId: (id: string) => void;
  range: TimeRange;
  setRange: (r: TimeRange) => void;
  applyPreset: (p: RangePreset) => void;
  theme: 'dark' | 'light';
  setTheme: (t: 'dark' | 'light') => void;
  dataVersion: number;
  bump: () => void;
  reloadMeta: () => Promise<void>;
  toast: (text: string, kind?: Toast['kind']) => void;
  toasts: Toast[];
  dismiss: (id: number) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;
}

const Ctx = createContext<AppState | null>(null);

const store = {
  get(k: string): string | null { try { return window.localStorage.getItem(`opendmo.${k}`); } catch { return null; } },
  set(k: string, v: string) { try { window.localStorage.setItem(`opendmo.${k}`, v); } catch { /* storage unavailable */ } },
};

function monthOf(p: string | null | undefined): string {
  if (p && /^\d{4}-\d{2}/.test(p)) return p.slice(0, 7);
  if (p && /^\d{4}-Q[1-4]$/.test(p)) return `${p.slice(0, 4)}-${String(Number(p.slice(-1)) * 3).padStart(2, '0')}`;
  if (p && /^\d{4}$/.test(p)) return `${p}-12`;
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** Calendar arithmetic for the range selector (UI navigation, not analysis). */
export function presetRange(p: RangePreset, anchor: string | null | undefined): TimeRange {
  if (p === 'all' || p === 'custom') return { preset: p, start: null, end: null };
  const months = { '12m': 12, '24m': 24, '36m': 36 }[p];
  const end = monthOf(anchor);
  const [y, m] = end.split('-').map(Number);
  const idx = y * 12 + (m - 1) - (months - 1);
  const start = `${Math.floor(idx / 12)}-${String((idx % 12) + 1).padStart(2, '0')}`;
  return { preset: p, start, end };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [destinationId, setDestinationIdRaw] = useState('jaflong');
  const [range, setRangeRaw] = useState<TimeRange>({ preset: '12m', start: null, end: null });
  const [theme, setThemeRaw] = useState<'dark' | 'light'>('dark');
  const [dataVersion, setDataVersion] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sidebarCollapsed, setCollapsedRaw] = useState(false);
  const toastId = useRef(0);
  const rangeInit = useRef(false);

  const toast = useCallback((text: string, kind: Toast['kind'] = 'info') => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-4), { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === 'error' ? 9000 : 5000);
  }, []);
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const reloadMeta = useCallback(async () => {
    try {
      const [m, d] = await Promise.all([get<Meta>('/meta'), get<Destination[]>('/destinations')]);
      setMeta(m);
      setDestinations(d);
      setBackendOk(true);
      if (!rangeInit.current) {
        rangeInit.current = true;
        const saved = store.get('range');
        const parsed = saved ? (JSON.parse(saved) as TimeRange) : null;
        if (parsed && parsed.preset === 'custom') setRangeRaw(parsed);
        else setRangeRaw(presetRange(parsed?.preset ?? '12m', m.data_extent.last_period));
      }
    } catch (e) {
      setBackendOk(false);
      toast(`Backend unreachable: ${errMsg(e)}`, 'error');
    }
  }, [toast]);

  useEffect(() => {
    const t = (store.get('theme') as 'dark' | 'light' | null) ?? 'dark';
    setThemeRaw(t);
    document.documentElement.dataset.theme = t;
    const d = store.get('destination');
    if (d) setDestinationIdRaw(d);
    setCollapsedRaw(store.get('sidebar') === 'collapsed');
    void reloadMeta();
  }, [reloadMeta]);

  useEffect(() => {
    if (destinations.length && !destinations.some((d) => d.id === destinationId)) setDestinationIdRaw(destinations[0].id);
  }, [destinations, destinationId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen((v) => !v); }
      if (e.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const value = useMemo<AppState>(() => ({
    meta, backendOk, destinations, destinationId,
    destination: destinations.find((d) => d.id === destinationId) ?? null,
    setDestinationId: (id) => { setDestinationIdRaw(id); store.set('destination', id); },
    range,
    setRange: (r) => { setRangeRaw(r); store.set('range', JSON.stringify(r)); },
    applyPreset: (p) => {
      const r = p === 'custom' ? { ...range, preset: 'custom' as const } : presetRange(p, meta?.data_extent.last_period);
      setRangeRaw(r); store.set('range', JSON.stringify(r));
    },
    theme,
    setTheme: (t) => { setThemeRaw(t); store.set('theme', t); document.documentElement.dataset.theme = t; },
    dataVersion, bump: () => { setDataVersion((v) => v + 1); void reloadMeta(); },
    reloadMeta, toast, toasts, dismiss, paletteOpen, setPaletteOpen,
    sidebarCollapsed, setSidebarCollapsed: (v) => { setCollapsedRaw(v); store.set('sidebar', v ? 'collapsed' : 'open'); },
  }), [meta, backendOk, destinations, destinationId, range, theme, dataVersion, reloadMeta, toast, toasts, dismiss, paletteOpen, sidebarCollapsed]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppProvider');
  return v;
}

/** Fetch JSON from the API; refetches when the path or the global data version changes. */
export function useApi<T>(path: string | null) {
  const { dataVersion } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) { setData(null); return; }
    let alive = true;
    setLoading(true);
    get<T>(path)
      .then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(errMsg(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [path, dataVersion, tick]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}

/** Hash-addressed tab state (shareable links, works with static export). */
export function useHashTab<T extends string>(tabs: readonly T[], fallback: T): [T, (t: T) => void] {
  const [tab, setTabRaw] = useState<T>(fallback);
  useEffect(() => {
    const read = () => {
      const h = window.location.hash.replace('#', '') as T;
      setTabRaw(tabs.includes(h) ? h : fallback);
    };
    read();
    window.addEventListener('hashchange', read);
    return () => window.removeEventListener('hashchange', read);
  }, [tabs, fallback]);
  return [tab, (t: T) => { window.history.replaceState(null, '', `#${t}`); setTabRaw(t); }];
}
