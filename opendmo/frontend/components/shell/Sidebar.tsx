'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { CORES, SYSTEM_TABS } from '@/lib/nav';
import { useApp } from '@/lib/state';

function Mark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="5" fill="var(--red)" />
      <path d="M8 22 L13 10 L17 18 L20 13 L24 22 Z" fill="#F4ECDD" />
      <circle cx="22" cy="9" r="2" fill="#F4ECDD" />
    </svg>
  );
}

const Icon = ({ d }: { d: string }) => (
  <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.3"><path d={d} /></svg>
);

export function Sidebar() {
  const path = usePathname() || '/';
  const { sidebarCollapsed, setSidebarCollapsed, meta } = useApp();
  const goTab = (route: string, tab: string) => (e: React.MouseEvent) => {
    if (path === route || path === route.replace(/\/$/, '')) { e.preventDefault(); window.location.hash = tab; }
  };
  const isOn = (route: string) => path === route || path === route.replace(/\/$/, '');
  return (
    <aside className="sidebar" aria-label="Main navigation">
      <Link href="/" className="brand">
        <Mark />
        <span className="brand-text">
          <div className="brand-name">OpenDMO</div>
          <div className="brand-sub">Destination analytics</div>
        </span>
      </Link>
      <nav className="nav">
        <Link href="/" className={`nav-link ${path === '/' ? 'active' : ''}`} title="Overview">
          <span className="nav-icon"><Icon d="M2 8 L8 2 L14 8 M4 7 V14 H12 V7" /></span><span className="nav-label">Overview</span>
        </Link>
        <div className="nav-section">Cores</div>
        {CORES.map((c) => (
          <div key={c.id}>
            <Link href={c.route} className={`nav-link ${isOn(c.route) ? 'active' : ''}`} title={c.name}>
              <span className="nav-num">{c.num}</span><span className="nav-label">{c.name}</span>
            </Link>
            {isOn(c.route) && c.tabs.map((t) => (
              <Link key={t.id} href={`${c.route}#${t.id}`} className="nav-sub" onClick={goTab(c.route, t.id)}>
                {t.name}
              </Link>
            ))}
          </div>
        ))}
        <div className="nav-section">Data</div>
        <Link href="/import/" className={`nav-link ${isOn('/import/') ? 'active' : ''}`} title="Import CSV">
          <span className="nav-icon"><Icon d="M8 2 V10 M4.5 6.5 L8 10 L11.5 6.5 M3 13 H13" /></span><span className="nav-label">Import CSV / JSON</span>
        </Link>
        <div className="nav-section">System</div>
        <Link href="/system/control-board/" className={`nav-link ${isOn('/system/control-board/') ? 'active' : ''}`} title="Control Board">
          <span className="nav-icon"><Icon d="M3 4 H13 M3 8 H13 M3 12 H13 M6 2.5 V5.5 M10 6.5 V9.5 M5 10.5 V13.5" /></span><span className="nav-label">Control Board</span>
        </Link>
        {isOn('/system/control-board/') && SYSTEM_TABS.map((t) => (
          <Link key={t.id} href={`/system/control-board/#${t.id}`} className="nav-sub" onClick={goTab('/system/control-board/', t.id)}>{t.name}</Link>
        ))}
      </nav>
      <div className="sidebar-foot">
        <button className="btn ghost sm" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {sidebarCollapsed ? '»' : '«'}
        </button>
        <span className="sidebar-foot-text">v{meta?.version ?? '…'} · local-first</span>
      </div>
    </aside>
  );
}
