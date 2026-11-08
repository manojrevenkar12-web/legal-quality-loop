import type { HeldoutConfig } from "../../shared/api/types";
import { signedPct } from "../../shared/format";

export function GateSection({ configs }: { configs: HeldoutConfig[] }) {
  const decided = configs.filter((c) => c.gate);
  return (
    <ul className="gate">
      {decided.map((c) => {
        const d = c.expert_diff_vs_baseline;
        return (
          <li key={c.name} className="gate__row">
            <span className={`verdict-chip verdict-chip--${c.gate!.verdict}`}>{c.gate!.verdict}</span>
            <div>
              <p className="gate__name">{c.name.replace("best: ", "best found, ")}</p>
              <p className="gate__reasons">{c.gate!.reasons.join("; ")}.</p>
              <p className="gate__truth">
                Experts: {signedPct(d.estimate)} against the baseline ({signedPct(d.low)} to {signedPct(d.high)}).{" "}
                {c.gate_right === true ? "The gate was right." : c.gate_right === false ? "The gate was wrong." : "Not scored."}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
