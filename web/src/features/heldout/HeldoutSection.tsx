import type { HeldoutConfig } from "../../shared/api/types";
import { euro, pct } from "../../shared/format";
import { useWidth } from "../../shared/charts/useWidth";
import { chart, color } from "../../theme/tokens";

const LABEL_COL = 260;
const COST_COL = 96;

/** Expert pass rate with its interval, the naive judge's opinion of the same config, and the cost. */
export function HeldoutSection({ configs }: { configs: HeldoutConfig[] }) {
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const narrow = width < 640;
  const barW = Math.max(160, width - (narrow ? 0 : LABEL_COL) - COST_COL);
  const x = (v: number) => (v * barW) / 1;
  const cheapest = Math.min(...configs.map((c) => c.cost_per_1k_eur));
  return (
    <div ref={ref} className="ranked">
      <div className="ranked__legend">
        <span>
          <span className="key" style={{ background: color.expert }} /> experts, with 95% interval
        </span>
        <span>
          <span className="key key--diamond" style={{ background: color.judge }} /> the cheap holistic judge's score
        </span>
      </div>
      <ol className="ranked__list">
        {configs.map((c) => {
          const e = c.expert_pass;
          return (
            <li key={c.name} className={narrow ? "ranked__row ranked__row--narrow" : "ranked__row"}>
              <div className="ranked__name" style={narrow ? undefined : { width: LABEL_COL }}>
                {c.name.replace("best: ", "best found, ")}
              </div>
              <svg width={barW} height={chart.barHeight * 2} role="img" aria-label={`experts ${pct(e.estimate)}, judge ${pct(c.naive_judge_pass)}`}>
                <rect x={0} y={chart.barHeight / 2} width={barW} height={chart.barHeight} fill={color.paper} rx={2} />
                <rect x={0} y={chart.barHeight / 2} width={x(e.estimate)} height={chart.barHeight} fill={color.expert} rx={2} />
                <line x1={x(e.low)} x2={x(e.high)} y1={chart.barHeight} y2={chart.barHeight} stroke={color.ink} strokeWidth={1.5} />
                <rect
                  x={x(c.naive_judge_pass) - 6}
                  y={chart.barHeight - 6}
                  width={12}
                  height={12}
                  fill={color.judge}
                  transform={`rotate(45 ${x(c.naive_judge_pass)} ${chart.barHeight})`}
                />
              </svg>
              <div className="ranked__num">
                <strong>{pct(e.estimate)}</strong>
                <span className={c.cost_per_1k_eur === cheapest ? "cost cost--best" : "cost"}>{euro(c.cost_per_1k_eur)}</span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
