import { ORDER, eur, one, pct } from "../../shared/format";
import type { Summary } from "../../shared/types";

export function DesignTable({ s, caption }: { s: Summary; caption: string }) {
  const rows = ORDER.filter((n) => s.designs[n]);
  const max = Math.max(...rows.map((n) => Math.abs(s.designs[n]!.cost_vs_as_found_per_month)), 1);
  return (
    <div className="overflow-x-auto rounded-soft border border-line bg-sheet">
      <table className="w-full min-w-table text-left">
        <caption className="sr-only">{caption}</caption>
        <thead className="text-small text-muted">
          <tr className="border-b border-line">
            <th scope="col" className="px-4 py-3 font-semibold">Design</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Late per day</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Turned away</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Driver hours</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Stop error (min)</th>
            <th scope="col" className="px-4 py-3 font-semibold">Cost a month against as found</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((n) => {
            const d = s.designs[n]!;
            const c = d.cost_vs_as_found_per_month;
            const strong = n === "platform";
            return (
              <tr key={n} className={`border-b border-line last:border-0 ${strong ? "bg-ground font-semibold text-ink" : ""}`}>
                <th scope="row" className="px-4 py-3 font-normal">
                  <span className={strong ? "font-semibold" : ""}>{d.label.split(":")[0]}</span>
                </th>
                <td className="px-4 py-3 text-right">{one(d.late_per_day)}</td>
                <td className="px-4 py-3 text-right">{pct(d.reject_share)}</td>
                <td className="px-4 py-3 text-right">{Math.round(d.driver_hours_per_day)}</td>
                <td className="px-4 py-3 text-right">{d.stop_mae.toFixed(2)}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="relative h-2 w-track rounded-pill bg-line" aria-hidden>
                      <div
                        className={`absolute top-0 h-2 rounded-pill ${c < 0 ? "bg-good" : "bg-bad"}`}
                        style={c < 0 ? { right: "50%", width: `${(-c / max) * 50}%` } : { left: "50%", width: `${(c / max) * 50}%` }}
                      />
                    </div>
                    <span>{n === "as_found" ? "–" : eur(c)}</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
