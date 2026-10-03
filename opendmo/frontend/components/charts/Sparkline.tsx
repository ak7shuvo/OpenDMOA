import type { Status } from '@/lib/types';

/** Tiny trend line. Pixel mapping only. */
export function Sparkline({ values, status = 'none' }: { values: number[]; status?: Status }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = 100 / (values.length - 1);
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(2)},${(18 - ((v - min) / span) * 16 + 1).toFixed(2)}`).join(' ');
  const color = status === 'none' ? 'var(--cream-dim)' : `var(--${status})`;
  return (
    <svg className="kpi-spark" viewBox="0 0 100 20" preserveAspectRatio="none" aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.3} vectorEffect="non-scaling-stroke" opacity={0.9} />
    </svg>
  );
}
