import { useResource } from "../../shared/api";
import { eur, int, one, pct } from "../../shared/format";
import type { Results } from "../../shared/types";
import { EmptyState, ErrorState, Skeleton, Tone } from "../../shared/ui/states";
import { DesignTable } from "./DesignTable";
import { PromiseBars } from "./PromiseBars";

export function PromiseView() {
  const r = useResource<Results>("/api/results");
  if (r.loading) return <Skeleton label="Loading results" rows={8} />;
  if (r.error) return <ErrorState error={r.error} retry={r.retry} what="the results" />;
  const s = r.data!.dev;
  const p = s.designs.platform;
  const a = s.designs.as_found;
  if (!p || !a) return <EmptyState title="No results yet">Run <code>python -m dpe.eval.cli evaluate</code>.</EmptyState>;
  const rows = (["as_found", "mean_models", "platform"] as const).filter((n) => s.designs[n]).map((n) => [n, s.designs[n]!] as [string, typeof p]);
  const ho = r.data!.heldout;
  const fails = r.data!.heldout_gate_fails;
  return (
    <div className="flex flex-col gap-7">
      <section className="flex max-w-hero flex-col gap-4">
        <h1 className="text-hero font-bold tracking-tight">
          Of every 1,000 orders, the platform delivers {int(p.on_time_share * 1000)} within the promise. The hub as found delivers {int(a.on_time_share * 1000)}.
        </h1>
        <p className="max-w-prose text-lead text-copy">
          Late deliveries fall from {one(a.late_per_day)} to {one(p.late_per_day)} a day per hub. More orders are turned away when a hub is full ({pct(a.reject_share)} to {pct(p.reject_share)}),
          because the planner stops accepting what it cannot deliver on time. Net of driver hours the change is {eur(p.cost_vs_as_found_per_month)} a month per hub.
        </p>
      </section>
      <section aria-labelledby="bars" className="flex flex-col gap-3">
        <h2 id="bars" className="text-lead font-semibold">Where every order ended up, development hubs</h2>
        <PromiseBars rows={rows} />
        <p className="text-small text-muted">
          {s.world.hubs} simulated hubs, {s.world.days} open days, {int(s.world.orders)} orders; every design meets the same orders, streets and absences.
        </p>
      </section>
      <section aria-labelledby="heldout" className="flex flex-col gap-3">
        <h2 id="heldout" className="text-lead font-semibold">Held-out hubs, run once</h2>
        {ho && fails ? (
          <div className="flex flex-col gap-2">
            <p className="flex flex-wrap items-center gap-3">
              {fails.length === 0 ? <Tone tone="good">Gate passed</Tone> : <Tone tone="bad">Gate not passed</Tone>}
              <span className="text-muted">{fails.length ? `Missed on: ${fails.join("; ")}.` : "Every limit in config/gate.yaml was met."}</span>
            </p>
            <PromiseBars rows={(["as_found", "platform"] as const).filter((n) => ho.designs[n]).map((n) => [n, ho.designs[n]!] as [string, typeof p])} />
          </div>
        ) : (
          <EmptyState title="Not run yet">The held-out hubs are run once, with <code>python -m dpe.eval.cli heldout</code>.</EmptyState>
        )}
      </section>
      <section aria-labelledby="designs" className="flex flex-col gap-3">
        <h2 id="designs" className="text-lead font-semibold">Every design on the same hubs</h2>
        <p className="max-w-prose text-muted">Each grey row is the platform with one piece taken out; its gap to the platform is what that piece is worth.</p>
        <DesignTable s={s} caption="Development hubs" />
      </section>
    </div>
  );
}
