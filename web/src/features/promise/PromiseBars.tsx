/** Every order of a design, as one bar: delivered within the promise, delivered late, turned away. */
import { motion } from "framer-motion";
import { NAME, pct } from "../../shared/format";
import type { DesignSummary } from "../../shared/types";
import { motionTokens } from "../../theme/motion";

const SEGMENTS = [
  { key: "on", label: "Within 120 minutes", cls: "bg-onTime text-sheet" },
  { key: "late", label: "Late", cls: "bg-late text-sheet" },
  { key: "away", label: "Turned away", cls: "bg-away text-ink" },
] as const;

function shares(d: DesignSummary) {
  const accepted = 1 - d.reject_share;
  return { on: d.on_time_share, late: accepted - d.on_time_share, away: d.reject_share };
}

export function PromiseBars({ rows }: { rows: [string, DesignSummary][] }) {
  return (
    <figure className="flex flex-col gap-4">
      <ul className="flex flex-col gap-4">
        {rows.map(([name, d], i) => {
          const s = shares(d);
          return (
            <li key={name} className="grid grid-cols-[9rem_1fr] items-center gap-4">
              <span className={`font-semibold ${name === "platform" ? "text-ink" : "text-copy"}`}>{NAME[name] ?? d.label}</span>
              <div className="flex h-bar overflow-hidden rounded-soft bg-line" role="img" aria-label={`${NAME[name] ?? d.label}: ${pct(s.on)} within 120 minutes, ${pct(s.late)} late, ${pct(s.away)} turned away`}>
                {SEGMENTS.map((seg, k) => (
                  <motion.div
                    key={seg.key}
                    className={`flex items-center overflow-hidden whitespace-nowrap px-2 text-small font-semibold ${seg.cls} ${k ? "border-l-rule border-sheet" : ""}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${s[seg.key] * 100}%` }}
                    transition={{ duration: motionTokens.fill, delay: i * motionTokens.stagger, ease: motionTokens.ease }}
                  >
                    {s[seg.key] > 0.06 ? pct(s[seg.key]) : ""}
                  </motion.div>
                ))}
              </div>
            </li>
          );
        })}
      </ul>
      <figcaption className="flex flex-wrap gap-5 pl-[10rem] text-small text-muted">
        {SEGMENTS.map((seg) => (
          <span key={seg.key} className="inline-flex items-center gap-2">
            <span className={`inline-block h-swatch w-swatch rounded-soft ${seg.cls.split(" ")[0]}`} aria-hidden />
            {seg.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
