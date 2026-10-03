'use client';

import { fmtCompact, fmtNum } from '@/lib/format';
import { useWidth } from './useWidth';

export interface Bar { label: string; value: number | null; color?: string; note?: string }

/** Categorical bars with an optional dashed reference line per category (e.g. climatological normal). */
export function BarChart({ bars, line, lineLabel, height = 180, ariaLabel, refY, refLabel }: {
  bars: Bar[]; line?: (number | null)[]; lineLabel?: string; height?: number; ariaLabel: string; refY?: number; refLabel?: string;
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const pad = { l: 46, r: 8, t: 12, b: 20 };
  const vals = [...bars.map((b) => b.value ?? 0), ...(line ?? []).map((v) => v ?? 0), refY ?? 0];
  const hi = Math.max(1, ...vals) * 1.08;
  const iw = Math.max(10, w - pad.l - pad.r);
  const ih = height - pad.t - pad.b;
  const bw = iw / Math.max(1, bars.length);
  const Y = (v: number) => pad.t + ih - (v / hi) * ih;
  const every = Math.max(1, Math.ceil(bars.length / Math.max(1, Math.floor(iw / 48))));
  return (
    <div ref={ref} className="chart" style={{ height }} role="img" aria-label={ariaLabel}>
      {w > 0 && (
        <svg width={w} height={height}>
          {[0, hi / 2, hi].map((t, i) => (
            <g key={i}>
              <line className="chart-grid" x1={pad.l} x2={w - pad.r} y1={Y(t)} y2={Y(t)} />
              <text className="chart-axis" x={pad.l - 5} y={Y(t) + 3} textAnchor="end">{fmtCompact(t)}</text>
            </g>
          ))}
          {bars.map((b, i) => {
            const x = pad.l + i * bw + bw * 0.15;
            const bwi = Math.max(1, bw * 0.7);
            return (
              <g key={`${b.label}-${i}`}>
                {b.value === null ? (
                  <rect x={x} y={pad.t} width={bwi} height={ih} fill="none" stroke="var(--line)" strokeDasharray="2 2" />
                ) : (
                  <rect x={x} y={Y(b.value)} width={bwi} height={Math.max(0, pad.t + ih - Y(b.value))} fill={b.color ?? 'var(--chart-1)'} opacity={0.85}>
                    <title>{`${b.label}: ${fmtNum(b.value)}${b.note ? ` · ${b.note}` : ''}`}</title>
                  </rect>
                )}
                {i % every === 0 && <text className="chart-axis" x={x + bwi / 2} y={height - 5} textAnchor="middle">{b.label}</text>}
              </g>
            );
          })}
          {line && (
            <path d={line.map((v, i) => (v === null ? '' : `${i && line[i - 1] !== null ? 'L' : 'M'}${(pad.l + i * bw + bw / 2).toFixed(1)},${Y(v).toFixed(1)}`)).join(' ')}
              fill="none" stroke="var(--chart-2)" strokeWidth={1.4} strokeDasharray="4 3"><title>{lineLabel}</title></path>
          )}
          {refY !== undefined && (
            <g>
              <line x1={pad.l} x2={w - pad.r} y1={Y(refY)} y2={Y(refY)} stroke="var(--risk)" strokeDasharray="4 3" />
              <text className="chart-axis" x={w - pad.r - 2} y={Y(refY) - 3} textAnchor="end" style={{ fill: 'var(--risk)' }}>{refLabel}</text>
            </g>
          )}
        </svg>
      )}
    </div>
  );
}

/** Horizontal score bar (0–max). */
export function HBar({ label, value, max = 100, status, right }: { label: string; value: number | null; max?: number; status?: string; right?: string }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(8rem, 40%) 1fr 5rem', gap: '0.5rem', alignItems: 'center', fontSize: '0.78rem', padding: '0.2rem 0' }}>
      <span className="truncate muted">{label}</span>
      <div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%`, background: status ? `var(--${status})` : undefined }} /></div>
      <span className="right">{right ?? fmtNum(value)}</span>
    </div>
  );
}
