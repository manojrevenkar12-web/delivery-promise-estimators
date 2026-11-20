import { useResource } from "../../shared/api";
import { eur, one, pct } from "../../shared/format";
import type { Decisions } from "../../shared/types";
import { EmptyState, ErrorState, Skeleton, Tone } from "../../shared/ui/states";

export function DecisionsView() {
  const r = useResource<Decisions>("/api/decisions");
  if (r.loading) return <Skeleton label="Loading the options" rows={8} />;
  if (r.error) return <ErrorState error={r.error} retry={r.retry} what="the options" />;
  const { options, sensitivity, selection } = r.data!;
  if (!options.length) return <EmptyState title="No options yet">Run <code>python -m dpe.eval.cli evaluate</code>.</EmptyState>;
  const max = Math.max(...options.map((o) => Math.abs(o.value_per_month)), 1);
  return (
    <div className="flex flex-col gap-7">
      <div className="flex max-w-hero flex-col gap-2">
        <h1 className="text-title font-bold">What to build first</h1>
        <p className="text-muted">
          Ranked by value per week of work. Value is each piece's saving against the full platform without it, paired on the same hub-days; effort is the
          team's own estimate, stated in <code>config/options.yaml</code>. This is the page for the management update.
        </p>
      </div>
      <ol className="flex flex-col divide-y divide-line rounded-soft border border-line bg-sheet">
        {options.map((o, i) => (
          <li key={o.key} className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 px-4 py-3 md:grid-cols-[2rem_1fr_14rem_8rem]">
            <span className="text-lead font-bold text-muted">{i + 1}</span>
            <div className="flex flex-col">
              <span className="font-semibold text-ink">{o.label}</span>
              <span className="text-small text-muted">
                {o.area} · {o.effort_weeks} {o.effort_weeks === 1 ? "week" : "weeks"}
                {o.late_avoided_per_day !== null ? ` · ${one(o.late_avoided_per_day)} late deliveries avoided a day` : ""}
              </span>
            </div>
            <div className="hidden items-center gap-3 md:flex" aria-hidden>
              <div className="relative h-2 w-full rounded-pill bg-line">
                <div className={`absolute left-0 top-0 h-2 rounded-pill ${o.value_per_month >= 0 ? "bg-platform" : "bg-bad"}`} style={{ width: `${(Math.abs(o.value_per_month) / max) * 100}%` }} />
              </div>
            </div>
            <div className="flex flex-col items-end">
              <span className="font-semibold text-ink">{eur(o.value_per_month)}</span>
              {o.clear === null ? (
                <span className="text-small text-muted">a month</span>
              ) : o.clear ? (
                <Tone tone={o.value_per_month >= 0 ? "good" : "bad"}>clear of zero</Tone>
              ) : (
                <span className="text-small text-muted">within noise</span>
              )}
            </div>
          </li>
        ))}
      </ol>
      <section aria-labelledby="grid" className="flex flex-col gap-3">
        <h2 id="grid" className="text-lead font-semibold">Which percentiles the planner gets</h2>
        <p className="max-w-prose text-muted">
          Every pair was replayed on the development hubs. Higher stop and travel percentiles mean fewer late deliveries and more orders turned away;
          a lower percentile of shows means more drivers asked. The pick is the cheapest pair that turns away at most {pct(selection.max_reject_share, 0)} of orders.
        </p>
        <div className="overflow-x-auto rounded-soft border border-line bg-sheet">
          <table className="w-full text-left">
            <caption className="sr-only">Percentile pairs replayed on the development hubs</caption>
            <thead className="text-small text-muted">
              <tr className="border-b border-line">
                <th scope="col" className="px-4 py-3 font-semibold">Stops and travel</th>
                <th scope="col" className="px-4 py-3 font-semibold">Shows</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Late per day</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Turned away</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Cost a month against as found</th>
              </tr>
            </thead>
            <tbody>
              {selection.grid.map((g) => {
                const pick = selection.pick && g.q === selection.pick.q && g.a === selection.pick.a;
                return (
                  <tr key={`${g.q}-${g.a}`} className={`border-b border-line last:border-0 ${pick ? "bg-ground font-semibold text-ink" : g.ok ? "" : "text-muted"}`}>
                    <td className="px-4 py-2">{Math.round(g.q * 100)}th</td>
                    <td className="px-4 py-2">{Math.round(g.a * 100)}th</td>
                    <td className="px-4 py-2 text-right">{one(g.late_per_day)}</td>
                    <td className="px-4 py-2 text-right">{pct(g.reject_share)}{g.ok ? "" : " (over)"}</td>
                    <td className="px-4 py-2 text-right">{eur(g.cost_vs_as_found_per_month)}{pick ? " · served" : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <h3 className="pt-3 font-semibold">If a late delivery is worth more</h3>
        <ul className="flex flex-wrap gap-3">
          {sensitivity.map((s) => (
            <li key={s.late_cost_eur} className="rounded-soft border border-line bg-sheet px-4 py-3">
              <span className="block text-small text-muted">Late delivery at €{s.late_cost_eur}</span>
              <span className="font-semibold text-ink">
                {Math.round(s.best_quantile * 100)}th / {Math.round(s.best_availability * 100)}th
              </span>
              <span className="block text-small text-muted">{one(s.late_per_day)} late a day</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
