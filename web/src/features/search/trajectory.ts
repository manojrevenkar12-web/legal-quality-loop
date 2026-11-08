import type { TrajectoryRow } from "../../shared/api/types";

export interface Step {
  iteration: number;
  judge: number; // what the search's own scorer says about its current best
  expert: number; // what experts say about the same config
  change: string[];
}

/** The search's best-so-far candidate after each iteration: what it believed, and what experts saw. */
export function bestSoFar(rows: TrajectoryRow[]): Step[] {
  const last = Math.max(0, ...rows.map((r) => r.iteration));
  let best: TrajectoryRow | undefined;
  const steps: Step[] = [];
  for (let it = 0; it <= last; it++) {
    const changes: string[] = [];
    for (const r of rows) {
      if (r.iteration !== it || !r.accepted || r.fitness == null) continue;
      if (!best || r.fitness > (best.fitness ?? -Infinity)) {
        best = r;
        changes.push(...Object.entries(r.change).map(([k, v]) => `${k}: ${String(v)}`));
      }
    }
    if (best && best.pass != null && best.expert_pass != null) {
      steps.push({ iteration: it, judge: best.pass, expert: best.expert_pass, change: changes });
    }
  }
  return steps;
}
