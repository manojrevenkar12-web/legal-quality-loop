"""Runs one app config over a set of tasks and scores every answer the way the platform does: a judge chosen by
calibration plus the deterministic checks. Nothing here reads expert grades."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from qloop.app.assistant import AppConfig, answer
from qloop.config import Settings
from qloop.guardrails import checks as C
from qloop.judges.llm_judge import JudgeResult, judge
from qloop.stats import Interval, wilson
from qloop.world.tasks import Task


@dataclass(frozen=True)
class Scorer:
    """How a run is scored: which judge, which rubric, and whether the deterministic checks count."""

    judge: str = "large"
    rubric: str = "v2"
    checks: bool = True

    @property
    def name(self) -> str:
        return f"judge-{self.judge}/{self.rubric}" + ("+checks" if self.checks else "")


TRUSTED = Scorer("large", "v2", True)
NAIVE = Scorer("small", "v1", False)


@dataclass
class Item:
    task: Task
    answer: str
    retrieved: list[str]
    cost_eur: float
    tokens_in: int
    tokens_out: int
    judged: JudgeResult
    checks: C.Checks
    passed: bool
    feedback: list[str]
    steps: list[dict] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def row(self) -> dict:
        return {
            "task": self.task.id,
            "family": self.task.family,
            "topic": self.task.topic,
            "jurisdiction": self.task.jurisdiction,
            "language": self.task.language,
            "split": self.task.split,
            "answer": self.answer,
            "cost_eur": round(self.cost_eur, 6),
            "passed": self.passed,
            "judge": {
                "name": self.judged.judge,
                "rubric": self.judged.rubric,
                "passed": self.judged.passed,
                "score": round(self.judged.score, 3),
                "criteria": self.judged.criteria,
            },
            "checks": asdict(self.checks),
            "feedback": self.feedback,
        }


def checks_for(task: Task, text: str) -> C.Checks:
    if task.family == "research":
        return C.research(text, task.jurisdiction, task.language)
    if task.family == "review":
        return C.review(text, bool(task.reference.citations))
    return C.discovery(text, task.documents[0].text)


def score(
    task: Task, out_text: str, retrieved: list[str], scorer: Scorer, settings: Settings
) -> tuple[JudgeResult, C.Checks, bool, list[str]]:
    j = judge(task, out_text, retrieved, scorer.judge, scorer.rubric, settings)
    ch = checks_for(task, out_text)
    if task.family == "research" and scorer.rubric == "v2":
        # the judge decides the facts and overclaims; citations, jurisdiction and language are checked by code
        judged_ok = j.criteria["correct"] and j.criteria["no_overclaim"]
    else:
        judged_ok = j.passed
    ok = judged_ok and (ch.passed if scorer.checks else True)
    feedback = list(j.rationale) + ([f"check failed: {f}" for f in ch.failures()] if scorer.checks else [])
    return j, ch, ok, feedback


def run_item(task: Task, cfg: AppConfig, scorer: Scorer, settings: Settings, seed: int) -> Item:
    out = answer(task, cfg, settings, seed)
    j, ch, ok, fb = score(task, out.text, out.retrieved, scorer, settings)
    return Item(
        task,
        out.text,
        out.retrieved,
        out.cost_eur,
        out.tokens_in,
        out.tokens_out,
        j,
        ch,
        ok,
        fb,
        out.steps,
        out.removed_from_documents,
    )


@dataclass
class Run:
    config: AppConfig
    scorer: Scorer
    items: list[Item]

    @property
    def pass_rate(self) -> float:
        return sum(i.passed for i in self.items) / max(1, len(self.items))

    def interval(self, alpha: float = 0.05) -> Interval:
        return wilson(sum(i.passed for i in self.items), len(self.items), alpha)

    @property
    def cost_per_1k(self) -> float:
        return 1000 * sum(i.cost_eur for i in self.items) / max(1, len(self.items))

    def guardrail_rates(self) -> dict[str, Interval]:
        injected = [i for i in self.items if i.task.injected]
        research = [i for i in self.items if i.task.family == "research"]
        inj_fail = sum(1 for i in injected if not i.checks.no_injected_value)
        unground = sum(1 for i in research if not (i.checks.citation_exists and i.checks.grounded))
        juris = sum(1 for i in research if not i.checks.citation_jurisdiction)
        lang = sum(1 for i in research if not i.checks.language)
        return {
            "injection_success": wilson(inj_fail, len(injected)),
            "ungrounded_citation": wilson(unground, len(research)),
            "jurisdiction_leak": wilson(juris, len(research)),
            "language_leak": wilson(lang, len(research)),
        }

    def breakdown(self, key: str) -> dict[str, dict]:
        groups: dict[str, list[Item]] = defaultdict(list)
        for i in self.items:
            groups[getattr(i.task, key)].append(i)
        return {
            k: {"n": len(v), **wilson(sum(x.passed for x in v), len(v)).as_dict()} for k, v in sorted(groups.items())
        }

    def summary(self) -> dict:
        return {
            "config": self.config.model_dump(),
            "config_key": self.config.key(),
            "scorer": self.scorer.name,
            "items": len(self.items),
            "pass": self.interval().as_dict(),
            "cost_per_1k_queries_eur": round(self.cost_per_1k, 3),
            "guardrails": {k: v.as_dict() for k, v in self.guardrail_rates().items()},
            "by_family": self.breakdown("family"),
            "by_jurisdiction": self.breakdown("jurisdiction"),
        }


def evaluate(
    cfg: AppConfig, tasks: list[Task], settings: Settings, scorer: Scorer = TRUSTED, seed: int | None = None
) -> Run:
    seed = settings.run.seed if seed is None else seed
    return Run(cfg, scorer, [run_item(t, cfg, scorer, settings, seed) for t in tasks])
