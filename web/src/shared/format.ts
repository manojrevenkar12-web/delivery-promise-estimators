export const int = (v: number) => Math.round(v).toLocaleString("en-GB");
export const one = (v: number) => v.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;
export const eur = (v: number) => `${v < 0 ? "−" : ""}€${Math.abs(Math.round(v)).toLocaleString("en-GB")}`;

/** Main designs first, then ablations in the evaluation's order. */
export const ORDER = [
  "as_found",
  "mean_models",
  "platform_rule_service",
  "platform_router_travel",
  "platform_rule_availability",
  "platform_mean",
  "platform_q50",
  "platform_q90",
  "platform_no_retrain",
  "platform_weekly_only",
  "platform_no_fallback",
  "platform",
];

export const NAME: Record<string, string> = { as_found: "As found", mean_models: "Mean models", platform: "Platform" };
