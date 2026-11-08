// Mirrors reports/results.json, written by qloop.report.

export interface Bound {
  estimate: number;
  low: number;
  high: number;
}

export interface JudgeReport {
  name: string;
  judge: string;
  rubric: string;
  with_checks: boolean;
  agreement: number;
  kappa: number;
  judge_pass: number;
  human_pass: number;
  false_pass: number;
  false_fail: number;
  long_bias: number;
  n: number;
}

export interface TrajectoryRow {
  iteration: number;
  key: string;
  accepted: boolean;
  change: Record<string, unknown>;
  fitness?: number;
  pass?: number;
  expert_pass?: number;
  cost_per_1k?: number;
}

export interface Audit {
  start_human_pass: number;
  final_human_pass: number;
  human_diff: Bound;
  fitness_gain: number;
  flagged: boolean;
  reason: string;
  labels: number;
}

export interface Search {
  name: string;
  scorer: string;
  rollouts: number;
  start: Record<string, unknown>;
  best: Record<string, unknown>;
  fitness: { start: number; best: number };
  val_pass: { start: number; best: number };
  val_expert: { start: number; best: number };
  cost_per_1k: { start: number; best: number };
  audit: Audit;
  trajectory: TrajectoryRow[];
}

export interface Gate {
  verdict: "ship" | "block" | "inconclusive";
  reasons: string[];
}

export interface HeldoutConfig {
  name: string;
  config: Record<string, unknown>;
  platform_pass: Bound;
  expert_pass: Bound;
  expert_diff_vs_baseline: Bound;
  naive_judge_pass: number;
  cost_per_1k_eur: number;
  gate: Gate | null;
  gate_right: boolean | null;
}

export interface InjectionRow {
  defence: string;
  n: number;
  obeyed: number;
  caught_by_output_check: number;
}

export interface RedTeamPart {
  attacks: number;
  caught: number;
  missed: string[];
  benign: number;
  false_positives: string[];
}

export interface LandscapeCell {
  family: string;
  jurisdiction: string;
  n: number;
  platform_pass: number;
  expert_pass: number;
  measure: string;
}

export interface Results {
  generated_at: string;
  heldout_runs: number;
  development: {
    calibration: { reports: JudgeReport[]; selected: string | null; humans: { kappa: number; n: number }; n: number; spent_eur: number; min_kappa: number };
    searches: Search[];
    baseline: { landscape: LandscapeCell[] };
    redteam: { development: RedTeamPart; heldout: RedTeamPart };
    labels: { items: number; spent_eur: number };
  };
  heldout: null | {
    pin: string;
    items: number;
    configs: HeldoutConfig[];
    injection: InjectionRow[];
    traces: { events: number; raw_secrets_found: number };
  };
}
