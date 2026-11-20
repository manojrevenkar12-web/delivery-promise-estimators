import { motion } from "framer-motion";
import { useResource } from "../../shared/api";
import { eur, one } from "../../shared/format";
import type { Warehouse } from "../../shared/types";
import { EmptyState, ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/motion";

const LABEL: Record<string, string> = {
  as_found: "As found: first come first served, S-shape, slots as they are",
  platform_fcfs: "Platform, first come first served",
  platform_s_shape: "Platform, S-shape routes",
  platform_return: "Platform, return routes",
  platform_no_reslot: "Platform, slots as they are",
  platform: "Platform: savings batching, 2-opt routes, busiest SKUs near pack-out",
};

export function WarehouseView() {
  const r = useResource<Warehouse>("/api/warehouse");
  if (r.loading) return <Skeleton label="Loading the warehouse" rows={6} />;
  if (r.error) return <ErrorState error={r.error} retry={r.retry} what="the warehouse" />;
  const w = r.data!;
  const names = Object.keys(w.designs);
  if (!names.length) return <EmptyState title="No picking results yet">Run <code>python -m dpe.eval.cli evaluate</code>.</EmptyState>;
  const max = Math.max(...names.map((n) => w.designs[n]!.metres_per_order));
  const a = w.designs.as_found!;
  const p = w.designs.platform!;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex max-w-hero flex-col gap-2">
        <h1 className="text-title font-bold">Picking: {one(a.metres_per_order)} m an order down to {one(p.metres_per_order)} m</h1>
        <p className="text-muted">
          The same order lines on {w.days} days across {w.hubs} hubs, picked in 10-minute waves onto carts of 12 crates. Picker time falls from{" "}
          {a.minutes_per_order.toFixed(2)} to {p.minutes_per_order.toFixed(2)} minutes an order, worth {eur(a.cost_per_month - p.cost_per_month)} a month per hub
          in picker hours.
        </p>
      </div>
      <ul className="flex flex-col gap-3 rounded-soft border border-line bg-sheet p-5">
        {names.map((n) => {
          const d = w.designs[n]!;
          return (
            <li key={n} className="grid grid-cols-1 gap-1 md:grid-cols-[22rem_1fr_6rem] md:items-center md:gap-4">
              <span className={n === "platform" ? "font-semibold text-ink" : "text-copy"}>{LABEL[n] ?? n}</span>
              <div className="h-3 rounded-pill bg-line" aria-hidden>
                <motion.div
                  className={`h-3 rounded-pill ${n === "platform" ? "bg-platform" : n === "as_found" ? "bg-asFound" : "bg-ablation"}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${(d.metres_per_order / max) * 100}%` }}
                  transition={{ duration: motionTokens.fill, ease: motionTokens.ease }}
                />
              </div>
              <span className="text-right font-semibold">{one(d.metres_per_order)} m</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
