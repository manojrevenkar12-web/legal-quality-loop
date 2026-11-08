import type { JudgeReport } from "../../shared/api/types";
import { pct } from "../../shared/format";

export function CalibrationSection({ reports, selected, humans, minKappa }: { reports: JudgeReport[]; selected: string | null; humans: number; minKappa: number }) {
  const scale = (k: number) => `${Math.max(0, k) * 100}%`;
  return (
    <div className="kappa">
      <div className="kappa__axis" aria-hidden="true">
        <span style={{ left: scale(minKappa) }} className="kappa__mark">
          trust from κ {minKappa.toFixed(2)}
        </span>
        <span style={{ left: scale(humans) }} className="kappa__mark kappa__mark--humans">
          two experts κ {humans.toFixed(2)}
        </span>
      </div>
      <ul className="kappa__list">
        {reports.map((r) => (
          <li key={r.name} className={r.name === selected ? "kappa__row kappa__row--selected" : "kappa__row"}>
            <span className="kappa__name">
              {r.name}
              {r.name === selected && <span className="chip">selected</span>}
            </span>
            <span className="kappa__track">
              <span className="kappa__bar" style={{ width: scale(r.kappa) }} />
              <span className="kappa__line" style={{ left: scale(minKappa) }} />
              <span className="kappa__line kappa__line--humans" style={{ left: scale(humans) }} />
            </span>
            <span className="kappa__value">κ {r.kappa.toFixed(2)}</span>
            <span className="kappa__note">
              passed {r.false_pass} answers experts failed; passes {pct(r.judge_pass)} vs experts {pct(r.human_pass)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
