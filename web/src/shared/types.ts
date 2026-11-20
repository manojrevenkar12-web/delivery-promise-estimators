export type DesignSummary = {
  label: string;
  days: number;
  orders_per_day: number;
  late_per_day: number;
  late_ci: [number, number];
  rejected_per_day: number;
  late_share: number;
  reject_share: number;
  on_time_share: number;
  driver_hours_per_day: number;
  short_shifts_per_week: number;
  cost_per_month: number;
  cost_vs_as_found_per_month: number;
  cost_vs_as_found_ci: [number, number];
  stop_mae: number;
  stop_coverage: number;
  travel_coverage: number;
  stop_quantile: number | null;
  travel_quantile: number | null;
  retrains: number;
  promoted: number;
  drift_retrains: number;
};

export type Summary = {
  designs: Record<string, DesignSummary>;
  world: { hubs: number; seeds: number[]; days: number; orders: number };
};

export type Results = { dev: Summary; heldout: Summary | null; heldout_gate_fails: string[] | null };

export type DaySeries = { accepted: number[]; rejected: number[]; late: number[]; on_road: number[] };
export type Day = { seed: number; day: number; date: string; bin_minutes: number; series: Record<string, DaySeries> };

export type Option = {
  key: string;
  area: string;
  label: string;
  effort_weeks: number;
  value_per_month: number;
  value_ci: [number, number] | null;
  late_avoided_per_day: number | null;
  clear: boolean | null;
  value_per_effort_week: number;
};
export type Decisions = {
  options: Option[];
  sensitivity: { late_cost_eur: number; best_quantile: number; best_availability: number; late_per_day: number }[];
  selection: {
    max_reject_share: number;
    grid: { q: number; a: number; late_per_day: number; reject_share: number; cost_vs_as_found_per_month: number; ok: boolean }[];
    pick: { q: number; a: number } | null;
  };
};

export type Warehouse = {
  designs: Record<string, { metres_per_order: number; minutes_per_order: number; orders_per_cart: number; picker_hours_per_day: number; cost_per_month: number }>;
  days: number;
  hubs: number;
};
