'use client';

import type { ReactNode } from 'react';
import { AppProvider, useApp } from '@/lib/state';
import { CommandPalette } from './CommandPalette';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

function Toasts() {
  const { toasts, dismiss } = useApp();
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} role={t.kind === 'error' ? 'alert' : 'status'}>
          <span style={{ flex: 1 }}>{t.text}</span>
          <button className="btn ghost sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">✕</button>
        </div>
      ))}
    </div>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const { sidebarCollapsed, backendOk } = useApp();
  return (
    <div className={`shell ${sidebarCollapsed ? 'collapsed' : ''}`}>
      <Sidebar />
      <div className="main">
        <TopBar />
        <main className="content">
          {backendOk === false && (
            <div className="callout red" style={{ marginBottom: '0.8rem' }}>
              The local OpenDMO backend is not reachable. Start it with <b>start-windows.bat</b>, <b>start-mac.command</b> or <b>start-linux.sh</b> (or <code>python run.py</code>) and reload.
            </div>
          )}
          {children}
        </main>
      </div>
      <CommandPalette />
      <Toasts />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return <AppProvider><Frame>{children}</Frame></AppProvider>;
}
