import { DayView } from "./features/day/DayView";
import { DecisionsView } from "./features/decisions/DecisionsView";
import { PromiseView } from "./features/promise/PromiseView";
import { WarehouseView } from "./features/warehouse/WarehouseView";
import { type View, go, useRoute } from "./shared/route";

const TABS: { view: View; label: string }[] = [
  { view: "promise", label: "The promise" },
  { view: "day", label: "One day" },
  { view: "decisions", label: "What to build" },
  { view: "warehouse", label: "Warehouse" },
];

export function App() {
  const view = useRoute();
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-sheet">
        <div className="mx-auto flex max-w-page flex-wrap items-end justify-between gap-4 px-6 pt-5">
          <div className="pb-4">
            <p className="text-lead font-bold text-ink">Delivery promise estimators</p>
            <p className="text-small text-muted">Stop times, travel and driver availability for a 120-minute promise, on simulated hubs</p>
          </div>
          <nav aria-label="Views" className="flex flex-wrap gap-1">
            {TABS.map((t) => (
              <button
                key={t.view}
                type="button"
                onClick={() => go(t.view)}
                aria-current={view === t.view ? "page" : undefined}
                className={`border-b-rule px-4 pb-3 pt-2 font-semibold transition-colors ${
                  view === t.view ? "border-glow text-ink" : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-page px-6 py-7">
        {view === "promise" && <PromiseView />}
        {view === "day" && <DayView />}
        {view === "decisions" && <DecisionsView />}
        {view === "warehouse" && <WarehouseView />}
      </main>
    </div>
  );
}
