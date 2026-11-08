import { motion, useReducedMotion } from "framer-motion";
import { useId } from "react";
import { chart, color, motion as m } from "../../theme/tokens";
import { pct } from "../../shared/format";
import { useWidth } from "../../shared/charts/useWidth";
import type { Step } from "./trajectory";

const TICKS = [0.4, 0.6, 0.8, 1];

/** The search's belief about its best config against the experts' view of the same config, iteration by iteration. */
export function DivergenceChart({ steps, judgeLabel, title }: { steps: Step[]; judgeLabel: string; title: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(720);
  const reduce = useReducedMotion();
  const id = useId();
  if (steps.length < 2) return null;
  const { top, right, bottom, left } = chart.padding;
  const h = chart.height;
  const last = steps[steps.length - 1]!;
  const maxIt = last.iteration || 1;
  const lo = TICKS[0]!;
  const x = (it: number) => left + (it / maxIt) * (width - left - right - 120);
  const y = (v: number) => top + (1 - (Math.max(v, lo) - lo) / (1 - lo)) * (h - top - bottom);
  const path = (key: "judge" | "expert") =>
    steps.map((s, i) => `${i ? "L" : "M"}${x(s.iteration).toFixed(1)},${y(s[key]).toFixed(1)}`).join("");
  // keep the two end labels apart when the lines finish close together
  const ends = { judge: y(last.judge), expert: y(last.expert) };
  if (Math.abs(ends.judge - ends.expert) < 16) {
    const mid = (ends.judge + ends.expert) / 2;
    const up = last.judge >= last.expert ? "judge" : "expert";
    ends[up] = mid - 8;
    ends[up === "judge" ? "expert" : "judge"] = mid + 8;
  }
  const series = [
    { key: "judge" as const, stroke: color.judge, label: judgeLabel, dash: undefined },
    { key: "expert" as const, stroke: color.expert, label: "experts", dash: undefined },
  ];
  return (
    <figure ref={ref} className="figure">
      <svg width={width} height={h} role="img" aria-labelledby={id} className="chart">
        <title id={id}>{`${title}: ${judgeLabel} ${pct(last.judge)}, experts ${pct(last.expert)} after ${last.iteration} iterations`}</title>
        {TICKS.map((t) => (
          <g key={t}>
            <line x1={left} x2={width - right - 120} y1={y(t)} y2={y(t)} stroke={color.rule} />
            <text x={left - 8} y={y(t) + 4} textAnchor="end">
              {pct(t)}
            </text>
          </g>
        ))}
        <text x={left} y={h - 8}>
          start
        </text>
        <text x={x(maxIt)} y={h - 8} textAnchor="end">
          iteration {maxIt}
        </text>
        {series.map((s, i) => (
          <g key={s.key}>
            <motion.path
              d={path(s.key)}
              fill="none"
              stroke={s.stroke}
              strokeWidth={chart.stroke}
              strokeLinejoin="round"
              initial={reduce ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: m.draw, delay: i * 0.25, ease: m.ease }}
            />
            <motion.text
              x={x(maxIt) + 10}
              y={ends[s.key] + 5}
              className="chart__end"
              style={{ fill: s.stroke }}
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: m.draw + i * 0.25 }}
            >
              {`${s.label} ${pct(last[s.key])}`}
            </motion.text>
          </g>
        ))}
      </svg>
    </figure>
  );
}
