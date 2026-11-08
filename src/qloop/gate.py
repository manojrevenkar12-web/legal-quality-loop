"""The release gate: a candidate config ships only if it is not worse than the baseline beyond the margin (lower
bound of the paired difference), its guardrail failure rates stay under their caps (upper bound), it fits the cost
budget, and the judge scoring it has passed calibration. When the bounds are too wide to decide, the gate says how
many more items would."""

from __future__ import annotations

from dataclasses import dataclass, field

from qloop.config import Settings
from qloop.runner import Run
from qloop.stats import items_needed, mcnemar, paired_difference


@dataclass
class Decision:
    verdict: str  # ship, block, inconclusive
    reasons: list[str] = field(default_factory=list)
    quality_diff: dict = field(default_factory=dict)
    p_value: float = 1.0
    items_for_decision: int = 0

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "reasons": self.reasons, "quality_diff": self.quality_diff,
                "p_value": round(self.p_value, 4), "items_for_decision": self.items_for_decision}


def compare(base: Run, cand: Run, settings: Settings, judge_kappa: float | None = None) -> Decision:
    g, st = settings.gate, settings.stats
    by_id = {i.task.id: i for i in base.items}
    pairs = [(by_id[i.task.id].passed, i.passed) for i in cand.items if i.task.id in by_id]
    a, b = [float(x) for x, _ in pairs], [float(y) for _, y in pairs]
    diff = paired_difference(a, b, st.bootstrap, st.alpha, seed=settings.run.seed)
    reasons: list[str] = []
    blocked = False
    if judge_kappa is not None and judge_kappa < settings.calibration.min_kappa:
        reasons.append(f"the scoring judge agrees with experts at kappa {judge_kappa:.2f}, below {settings.calibration.min_kappa}")
        blocked = True
    rates = cand.guardrail_rates()
    if rates["injection_success"].high > g.max_injection_success and rates["injection_success"].estimate > 0:
        reasons.append(f"injection success up to {rates['injection_success'].high:.1%} (cap {g.max_injection_success:.0%})")
        blocked = True
    if rates["ungrounded_citation"].estimate > g.max_ungrounded_citation:
        reasons.append(f"ungrounded citations {rates['ungrounded_citation'].estimate:.1%} (cap {g.max_ungrounded_citation:.0%})")
        blocked = True
    if cand.cost_per_1k > g.max_cost_per_1k_queries_eur:
        reasons.append(f"cost €{cand.cost_per_1k:.2f} per 1,000 queries (budget €{g.max_cost_per_1k_queries_eur:.2f})")
        blocked = True
    p = mcnemar([x > 0 for x in a], [y > 0 for y in b])
    if diff.low < -g.non_inferiority_margin:
        if diff.high < -g.non_inferiority_margin:
            reasons.append(f"quality worse by {-diff.estimate:.1%} (bound {diff.low:+.1%})")
            verdict = "block"
        else:
            base_rate = sum(a) / max(1, len(a))
            need = items_needed(base_rate, g.non_inferiority_margin, st.alpha)
            reasons.append(f"quality change {diff.estimate:+.1%}, bounds {diff.low:+.1%} to {diff.high:+.1%} cross the margin")
            return Decision("block" if blocked else "inconclusive", reasons, diff.as_dict(), p, need)
    else:
        verdict = "ship"
        reasons.append(f"quality {diff.estimate:+.1%} (lower bound {diff.low:+.1%}, margin -{g.non_inferiority_margin:.0%})")
    return Decision("block" if blocked else verdict, reasons, diff.as_dict(), p)
