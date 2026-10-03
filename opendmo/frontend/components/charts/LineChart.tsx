'use client';

import { useState } from 'react';
import { fmtCompact, fmtNum } from '@/lib/format';
import { useWidth } from './useWidth';

export interface LineSeries { id: string; label: string; color: string; points: { x: string; y: number | null }[]; dashed?: boolean }
export interface Band { color: string; points: { x: string; lo: number; hi: number }[] }
export interface RefLine { y: number; label: string; color: string }

/** Multi-series line chart over a categorical (period) x-axis with optional uncertainty bands. */
export function LineChart({ series, bands = [], refs = [], height = 200, unit = '', ariaLabel, markX }: {
  series: LineSeries[]; bands?: Band[]; refs?: RefLine[]; height?: number; unit?: string; ariaLabel: string; markX?: string;
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const xs = Array.from(new Set([...series.flatMap((s) => s.points.map((p) => p.x)), ...bands.flatMap((b) => b.points.map((p) => p.x))])).sort();
  const ys = [
    ...series.flatMap((s) => s.points.map((p) => p.y).filter((y): y is number => y !== null && Number.isFinite(y))),
    ...bands.flatMap((b) => b.points.flatMap((p) => [p.lo, p.hi])), ...refs.map((r) => r.y),
  ];
  if (!xs.length || !ys.length) return <div ref={ref} style={{ height }} className="chart" />;
  const pad = { l: 46, r: 10, t: 12, b: 20 };
  let lo = Math.min(...ys), hi = Math.max(...ys);
  if (lo === hi) { lo -= 1; hi += 1; }
  const span = hi - lo;
  lo -= span * 0.06; hi += span * 0.06;
  if (Math.min(...ys) >= 0 && lo < 0) lo = 0;
  const iw = Math.max(10, w - pad.l - pad.r);
  const ih = height - pad.t - pad.b;
  const xi = new Map(xs.map((x, i) => [x, i]));
  const X = (x: string) => pad.l + (xs.length === 1 ? iw / 2 : ((xi.get(x) ?? 0) / (xs.length - 1)) * iw);
  const Y = (y: number) => pad.t + ih - ((y - lo) / (hi - lo)) * ih;
  const ticks = [lo, lo + (hi - lo) / 2, hi];
  const nx = Math.max(2, Math.min(xs.length, Math.floor(iw / 70)));
  const xticks = Array.from(new Set(Array.from({ length: nx }, (_, i) => Math.round((i * (xs.length - 1)) / (nx - 1)))));
  const pathOf = (pts: { x: string; y: number | null }[]) => {
    let d = '';
    let pen = false;
    for (const p of pts) {
      if (p.y === null || !Number.isFinite(p.y)) { pen = false; continue; }
      d += `${pen ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - r.left) / r.width;
    setHover(Math.max(0, Math.min(xs.length - 1, Math.round(rel * (xs.length - 1)))));
  };
  const hx = hover !== null ? xs[hover] : null;
  return (
    <div ref={ref} className="chart" style={{ height }} role="img" aria-label={ariaLabel}>
      {w > 0 && (
        <svg width={w} height={height}>
          {ticks.map((t, i) => (
            <g key={i}>
              <line className="chart-grid" x1={pad.l} x2={w - pad.r} y1={Y(t)} y2={Y(t)} />
              <text className="chart-axis" x={pad.l - 5} y={Y(t) + 3} textAnchor="end">{fmtCompact(t)}</text>
            </g>
          ))}
          {xticks.map((i, j) => (
            <text key={i} className="chart-axis" x={X(xs[i])} y={height - 5} textAnchor={j === 0 ? 'start' : j === xticks.length - 1 ? 'end' : 'middle'}>{xs[i]}</text>
          ))}
          {unit && <text className="chart-axis" x={pad.l} y={pad.t - 3}>{unit}</text>}
          {markX && xi.has(markX) && <line x1={X(markX)} x2={X(markX)} y1={pad.t} y2={pad.t + ih} stroke="var(--line-strong)" strokeDasharray="3 3" />}
          {bands.map((b, i) => {
            const top = b.points.map((p, j) => `${j ? 'L' : 'M'}${X(p.x)},${Y(p.hi)}`).join(' ');
            const bot = [...b.points].reverse().map((p) => `L${X(p.x)},${Y(p.lo)}`).join(' ');
            return <path key={i} d={`${top} ${bot} Z`} fill={b.color} stroke="none" />;
          })}
          {refs.map((r, i) => (
            <g key={i}>
              <line x1={pad.l} x2={w - pad.r} y1={Y(r.y)} y2={Y(r.y)} stroke={r.color} strokeDasharray="4 3" />
              <text className="chart-axis" x={w - pad.r - 2} y={Y(r.y) - 3} textAnchor="end" style={{ fill: r.color }}>{r.label}</text>
            </g>
          ))}
          {series.map((s) => (
            <path key={s.id} d={pathOf(s.points)} fill="none" stroke={s.color} strokeWidth={1.6} strokeDasharray={s.dashed ? '5 3' : undefined} />
          ))}
          {hx !== null && (
            <g>
              <line x1={X(hx)} x2={X(hx)} y1={pad.t} y2={pad.t + ih} stroke="var(--cream-dim)" opacity={0.5} />
              {series.map((s) => {
                const p = s.points.find((q) => q.x === hx);
                return p && p.y !== null ? <circle key={s.id} cx={X(hx)} cy={Y(p.y)} r={3} fill={s.color} stroke="var(--panel)" /> : null;
              })}
            </g>
          )}
          <rect x={pad.l} y={pad.t} width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
        </svg>
      )}
      {hx !== null && w > 0 && (
        <div className="chart-tip" style={{ left: Math.min(X(hx) + 10, w - 170), top: 4 }}>
          <div className="faint">{hx}</div>
          {series.map((s) => {
            const p = s.points.find((q) => q.x === hx);
            return p && p.y !== null ? <div key={s.id}><span style={{ color: s.color }}>■</span> {s.label}: {fmtNum(p.y)}</div> : null;
          })}
          {bands.map((b, i) => {
            const p = b.points.find((q) => q.x === hx);
            return p ? <div key={i} className="faint">95% PI {fmtNum(p.lo)} – {fmtNum(p.hi)}</div> : null;
          })}
        </div>
      )}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.label}><i style={{ background: i.dashed ? `repeating-linear-gradient(90deg, ${i.color} 0 4px, transparent 4px 7px)` : i.color }} />{i.label}</span>
      ))}
    </div>
  );
}
