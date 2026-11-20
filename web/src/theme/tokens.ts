/**
 * Tokens for the estimators dashboard. A pale sage ground and deep green-black ink, like a dispatch board at
 * dawn; one amber for focus and the active tab. Series follow the evaluation and were checked for colour-blind
 * separation: blue the platform, orange the hub as found, teal the mean models, grey the ablations. Red is a
 * late delivery and nothing else. Every colour, size and duration comes from here.
 */
export const color = {
  ground: "#F2F4F1",
  sheet: "#FFFFFF",
  ink: "#14211D",
  copy: "#2C3833",
  muted: "#56625C",
  line: "#D5DCD7",
  glow: "#8A5300",
  focus: "#8A5300",
  good: "#14653F",
  goodWash: "#DCEFE3",
  bad: "#B42318",
  badWash: "#FBE4E1",
  onTime: "#2F4F44",
  late: "#B42318",
  away: "#A3A9A6",
  platform: "#1D4ED8",
  asFound: "#C2410C",
  mean: "#00897B",
  ablation: "#A3A9A6",
} as const;

export const font = {
  ui: ["Schibsted Grotesk Variable", "Schibsted Grotesk", "system-ui", "sans-serif"],
} as const;

/** 1.25 ratio from a 15px base. [size, line-height] */
export const type = {
  small: ["0.8125rem", "1.4"],
  body: ["0.9375rem", "1.55"],
  lead: ["1.1875rem", "1.4"],
  title: ["1.875rem", "1.15"],
  hero: ["2.75rem", "1.05"],
} as const;

export const space = { 0: "0", 1: "0.25rem", 2: "0.5rem", 3: "0.75rem", 4: "1rem", 5: "1.5rem", 6: "2rem", 7: "3rem", 8: "4rem" } as const;
export const radius = { none: "0", soft: "6px", pill: "999px" } as const;
export const measure = { prose: "68ch", page: "76rem", hero: "56rem", table: "60rem" } as const;
export const line = { hair: "1px", rule: "2px" } as const;
export const size = { swatch: "0.625rem", bar: "2.25rem", barTrack: "9rem", chart: "22rem" } as const;
export const chart = { width: 960, height: 340, left: 52, right: 120, top: 20, bottom: 36 } as const;
