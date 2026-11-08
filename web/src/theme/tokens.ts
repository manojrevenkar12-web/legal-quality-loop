// The visual system. CSS reads these as custom properties (applyTokens); charts read them directly.

export const color = {
  paper: "#F1F3EF",
  panel: "#FFFFFF",
  ink: "#16211B",
  muted: "#5C6A62",
  faint: "#94A199",
  rule: "#D3DAD4",
  expert: "#1E5B44", // what experts say: the truth the platform is measured against
  expertWash: "#DCEAE2",
  judge: "#B7791F", // what a judge says
  judgeWash: "#F6EAD3",
  block: "#A8322A",
  blockWash: "#F5DEDA",
} as const;

export const font = {
  ui: '"Instrument Sans", "Segoe UI", system-ui, sans-serif',
} as const;

export const size = { small: 13, body: 15, lead: 19, title: 24, display: 40 } as const;
export const space = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 32, 7: 48, 8: 72 } as const;
export const radius = { control: 4, panel: 8 } as const;
export const layout = { contentMax: 1120, measure: 68, breakpoint: 760 } as const;

export const chart = {
  height: 280,
  padding: { top: 16, right: 24, bottom: 32, left: 44 },
  stroke: 2.25,
  barHeight: 14,
  dot: 3.5,
} as const;

export const motion = {
  quick: 0.18,
  settle: 0.35,
  draw: 1.1,
  ease: [0.22, 1, 0.36, 1] as [number, number, number, number],
} as const;

export const net = { timeoutMs: 8000 } as const;

function kebab(s: string) {
  return s.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
}

export function applyTokens(root: HTMLElement = document.documentElement) {
  for (const [k, v] of Object.entries(color)) root.style.setProperty(`--c-${kebab(k)}`, v);
  root.style.setProperty("--f-ui", font.ui);
  for (const [k, v] of Object.entries(size)) root.style.setProperty(`--s-${k}`, `${v}px`);
  for (const [k, v] of Object.entries(space)) root.style.setProperty(`--sp-${k}`, `${v}px`);
  for (const [k, v] of Object.entries(radius)) root.style.setProperty(`--r-${k}`, `${v}px`);
  root.style.setProperty("--content-max", `${layout.contentMax}px`);
  root.style.setProperty("--measure", `${layout.measure}ch`);
}
