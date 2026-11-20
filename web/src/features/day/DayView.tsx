import { motion } from "framer-motion";
import { useState } from "react";
import { useResource } from "../../shared/api";
import { NAME, int } from "../../shared/format";
import type { Day, DaySeries } from "../../shared/types";
import { EmptyState, ErrorState, Skeleton } from "../../shared/ui/states";
import { chart, color } from "../../theme/tokens";
import { motionTokens } from "../../theme/motion";

type Metric = keyof DaySeries;
const METRICS: { key: Metric; label: string }[] = [
  { key: "late", label: "Late deliveries" },
  { key: "rejected", label: "Orders turned away" },
  { key: "on_road", label: "Vans on the road" },
];
const LINE: Record<string, string> = { as_found: color.asFound, mean_models: color.mean, platform: color.platform };
const FIRST = 7 * 4;
const LAST = 23 * 4;

const clock = (bin: number, size: number) => {
  const m = bin * size;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};

export function DayView() {
  const r = useResource<Day>("/api/day");
  const [metric, setMetric] = useState<Metric>("late");
  const [hover, setHover] = useState<number | null>(null);
  if (r.loading) return <Skeleton label="Loading the day" rows={8} />;
  if (r.error) return <ErrorState error={r.error} retry={r.retry} what="the day" />;
  const d = r.data!;
  const names = Object.keys(d.series).filter((n) => d.series[n]?.late?.length);
  if (!names.length) return <EmptyState title="No day recorded">Run <code>python -m dpe.eval.cli evaluate</code> to record one.</EmptyState>;
  const { width: W, height: H, left: L, right: R, top: T, bottom: B } = chart;
  const values = (n: string) => d.series[n]![metric].slice(FIRST, LAST);
  const top = Math.max(1, ...names.flatMap(values)) * 1.1;
  const len = LAST - FIRST;
  const x = (i: number) => L + ((W - L - R) * i) / (len - 1);
  const y = (v: number) => T + (H - T - B) * (1 - v / top);
  const ends = names
    .map((n) => ({ n, y: y(values(n)[len - 1] ?? 0) + 4 }))
    .sort((a, b) => a.y - b.y)
    .map((e, i, arr) => ({ ...e, y: i ? Math.max(e.y, arr[i - 1]!.y + 14) : e.y }));
  const totals = Object.fromEntries(names.map((n) => [n, d.series[n]![metric].reduce((s, v) => s + v, 0)]));
  return (
    <div className="flex flex-col gap-5">
      <div className="flex max-w-hero flex-col gap-2">
        <h1 className="text-title font-bold">One day, minute by minute</h1>
        <p className="text-muted">
          Hub {d.seed}, {d.date}: the first open day after road works start in three zones, in 15-minute steps. The hub as found plans on the map router and
          rules of thumb; the platform's travel model has already started to learn the new streets.
        </p>
      </div>
      <div role="group" aria-label="Metric" className="flex flex-wrap gap-2">
        {METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            aria-pressed={metric === m.key}
            onClick={() => setMetric(m.key)}
            className={`rounded-pill border px-3 py-1 text-small font-semibold transition-colors ${
              metric === m.key ? "border-ink bg-ink text-sheet" : "border-line bg-sheet text-copy hover:border-ink"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <figure className="flex flex-col gap-2 rounded-soft border border-line bg-sheet p-4">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label={`${METRICS.find((m) => m.key === metric)!.label} through the day for ${names.map((n) => NAME[n] ?? n).join(", ")}`}
          onMouseLeave={() => setHover(null)}
          onMouseMove={(e) => {
            const box = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - box.left) / box.width) * W;
            const i = Math.round(((px - L) / (W - L - R)) * (len - 1));
            setHover(i >= 0 && i < len ? i : null);
          }}
        >
          {Array.from({ length: 5 }, (_, k) => (top / 1.1) * (k / 4)).map((v) => (
            <g key={v}>
              <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={color.line} />
              <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill={color.muted}>{int(v)}</text>
            </g>
          ))}
          {Array.from({ length: 6 }, (_, k) => k * 12).map((i) => (
            <text key={i} x={x(i)} y={H - 12} textAnchor="middle" fontSize="11" fill={color.muted}>{clock(FIRST + i, d.bin_minutes)}</text>
          ))}
          {names.map((n) => (
            <motion.path
              key={`${n}-${metric}`}
              d={values(n).map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("")}
              fill="none"
              stroke={LINE[n] ?? color.ablation}
              strokeWidth={2}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: motionTokens.draw, ease: motionTokens.ease }}
            />
          ))}
          {ends.map((e) => (
            <text key={e.n} x={W - R + 8} y={e.y} fontSize="12" fill={color.ink}>{NAME[e.n] ?? e.n}</text>
          ))}
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke={color.ink} strokeDasharray="3 3" />
              {names.map((n) => (
                <circle key={n} cx={x(hover)} cy={y(values(n)[hover] ?? 0)} r={4} fill={LINE[n] ?? color.ablation} stroke={color.sheet} strokeWidth={2} />
              ))}
            </g>
          )}
        </svg>
        <figcaption className="flex flex-wrap items-center gap-5 text-small text-muted" aria-live="polite">
          <span className="font-semibold text-ink">{hover === null ? "Whole day" : clock(FIRST + hover, d.bin_minutes)}</span>
          {names.map((n) => (
            <span key={n} className="inline-flex items-center gap-2">
              <span className="inline-block h-swatch w-swatch rounded-soft" style={{ background: LINE[n] }} aria-hidden />
              {NAME[n] ?? n}: {hover === null ? int(totals[n] ?? 0) : int(values(n)[hover] ?? 0)}
            </span>
          ))}
        </figcaption>
      </figure>
    </div>
  );
}
