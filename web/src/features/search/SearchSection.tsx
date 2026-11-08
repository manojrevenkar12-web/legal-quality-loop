import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { Search } from "../../shared/api/types";
import { changedLevers, euro, pct } from "../../shared/format";
import { motion as m } from "../../theme/tokens";
import { DivergenceChart } from "./DivergenceChart";
import { bestSoFar } from "./trajectory";

const NAMES: Record<string, { tab: string; judge: string }> = {
  "naive judge": { tab: "Scored by a cheap holistic judge", judge: "judge" },
  "trusted scorer": { tab: "Scored by the calibrated judge and checks", judge: "scorer" },
  "small model only": { tab: "Small model only", judge: "scorer" },
};

export function SearchSection({ searches }: { searches: Search[] }) {
  const [active, setActive] = useState(searches[0]?.name ?? "");
  const s = searches.find((x) => x.name === active) ?? searches[0];
  if (!s) return null;
  const meta = NAMES[s.name] ?? { tab: s.name, judge: "scorer" };
  const steps = bestSoFar(s.trajectory);
  return (
    <div>
      <div className="tabs" role="tablist" aria-label="Searches">
        {searches.map((x) => (
          <button key={x.name} role="tab" aria-selected={x.name === s.name} onClick={() => setActive(x.name)} className="tab">
            {NAMES[x.name]?.tab ?? x.name}
            {x.name === s.name && <motion.span layoutId="tab-underline" className="tab__line" transition={{ duration: m.settle, ease: m.ease }} />}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={s.name} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: m.quick }}>
          <DivergenceChart steps={steps} judgeLabel={meta.judge} title={meta.tab} />
          <div className="search-facts">
            <p className={s.audit.flagged ? "verdict verdict--block" : "verdict verdict--ok"}>
              <strong>{s.audit.flagged ? "Flagged by the expert audit." : "Confirmed by the expert audit."}</strong>{" "}
              Experts labelled {s.audit.labels} answers: pass rate {pct(s.audit.start_human_pass)} at the start,{" "}
              {pct(s.audit.final_human_pass)} for the search's best.
            </p>
            <p>
              The search changed: {changedLevers(s.start, s.best).join(", ") || "nothing"}. Cost {euro(s.cost_per_1k.start)} →{" "}
              {euro(s.cost_per_1k.best)} per 1,000 queries, {s.rollouts.toLocaleString("en")} rollouts.
            </p>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
