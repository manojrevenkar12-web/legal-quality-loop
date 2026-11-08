import { MotionConfig } from "framer-motion";
import { fetchJSON } from "../shared/api/client";
import type { Results } from "../shared/api/types";
import { useResource } from "../shared/hooks/useResource";
import { Empty, ErrorState, Section, Skeleton } from "../shared/ui/States";
import { euro, pct } from "../shared/format";
import { SearchSection } from "../features/search/SearchSection";
import { HeldoutSection } from "../features/heldout/HeldoutSection";
import { CalibrationSection } from "../features/calibration/CalibrationSection";
import { GateSection } from "../features/gate/GateSection";
import { GuardrailSection } from "../features/guardrails/GuardrailSection";
import { LandscapeSection } from "../features/landscape/LandscapeSection";

const URL = import.meta.env.VITE_RESULTS_URL ?? "/results.json";

export function App() {
  const res = useResource((s) => fetchJSON<Results>(URL, s), URL);
  return (
    <MotionConfig reducedMotion="user">
      <main className="page">
        <p className="kicker-line">legal-quality-loop: evaluation results for a legal AI assistant</p>
        {res.state === "loading" && <Skeleton />}
        {res.state === "error" && <ErrorState error={res.error} onRetry={res.retry} />}
        {res.state === "ready" && <Report r={res.data} />}
      </main>
    </MotionConfig>
  );
}

function Report({ r }: { r: Results }) {
  const dev = r.development;
  const held = r.heldout;
  const naive = held?.configs.find((c) => c.name.startsWith("best: naive"));
  const base = held?.configs.find((c) => c.name.startsWith("baseline"));
  const small = held?.configs.find((c) => c.name.startsWith("best: small"));
  return (
    <>
      <header className="hero">
        <h1>An optimizer learned to please the judge. The experts' audit caught it before release.</h1>
        {naive && base ? (
          <p className="hero__lead">
            Searching against a cheap holistic judge, the assistant learned to sound confident. On held-out legal tasks that judge
            scores the result {pct(naive.naive_judge_pass)}, above the baseline's {pct(base.naive_judge_pass)}. Experts pass{" "}
            {pct(naive.expert_pass.estimate)} of its answers against the baseline's {pct(base.expert_pass.estimate)}.
          </p>
        ) : (
          <p className="hero__lead">The held-out set has not run yet; the development results follow.</p>
        )}
      </header>

      <Section id="searches" title="What each search believed, and what experts saw" lead="The search's best configuration after each iteration, as its own scorer rates it and as experts grade the same answers.">
        <SearchSection searches={dev.searches} />
      </Section>

      <Section
        id="heldout"
        title="Held-out legal tasks, run once"
        lead={
          held && small && base
            ? `Limitation periods, default interest, GDPR fines, payment terms and a new contract layout, never used for tuning. The small model, configured by the search, costs ${euro(small.cost_per_1k_eur)} per 1,000 queries against ${euro(base.cost_per_1k_eur)}.`
            : undefined
        }
      >
        {held ? <HeldoutSection configs={held.configs} /> : <Empty title="Not run yet">Run qloop heldout once, then qloop report.</Empty>}
      </Section>

      <Section
        id="judges"
        title="Judges earn trust against experts first"
        lead={`${dev.calibration.n} answers from five configurations, labelled by experts (€${dev.calibration.spent_eur.toLocaleString("en")} of their time). Only a judge above the line may score a search or a release.`}
      >
        <CalibrationSection reports={dev.calibration.reports} selected={dev.calibration.selected} humans={dev.calibration.humans.kappa} minKappa={dev.calibration.min_kappa} />
      </Section>

      <Section id="gate" title="Release gate on the held-out candidates" lead="Each candidate against the baseline: lower bound of the quality change, guardrail caps, cost budget.">
        {held ? <GateSection configs={held.configs} /> : <Empty title="No gate decisions yet" />}
      </Section>

      <Section id="guardrails" title="Prompt injection from ingested contracts">
        {held ? <GuardrailSection injection={held.injection} redteam={dev.redteam} /> : <Empty title="No held-out injection results yet" />}
      </Section>

      <Section id="landscape" title="The baseline across tasks and jurisdictions" lead="Development set. The platform's pass rate first, experts' below it.">
        <LandscapeSection cells={dev.baseline.landscape} />
      </Section>

      <footer className="footer">
        Generated {new Date(r.generated_at).toLocaleString("en-GB")} from reports/results.json. Held-out set run {r.heldout_runs} time
        {r.heldout_runs === 1 ? "" : "s"}
        {held ? `, pin ${held.pin.slice(0, 12)}` : ""}. Expert labels used: {dev.labels.items}.
      </footer>
    </>
  );
}
