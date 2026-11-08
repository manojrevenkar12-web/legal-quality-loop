"""Judge calibration: before a judge's grades decide anything, measure how often it agrees with experts, where it is
biased, and whether that agreement is close to how often two experts agree with each other.

The answers to calibrate on come from several app configs, so the judge sees the variety of answers it will grade in
production (long and short, confident and hedged, digits and words), not only one model's style.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from qloop.app.assistant import AppConfig, answer
from qloop.config import Settings
from qloop.judges.llm_judge import judge
from qloop.labels import Labeler, passed
from qloop.runner import checks_for
from qloop.stats import Interval, cohen_kappa, wilson
from qloop.world.tasks import Task

CALIBRATION_CONFIGS = [
    AppConfig(),
    AppConfig(model="small"),
    AppConfig(model="medium", tone="assertive", verbosity="detailed"),
    AppConfig(model="small", number_style="words", tone="assertive"),
    AppConfig(model="medium", jurisdiction_filter=True, cite_only_retrieved=True, quote_then_answer=True),
]

JUDGES = [("small", "v1"), ("small", "v2"), ("large", "v1"), ("large", "v2")]


@dataclass
class Sample:
    task: Task
    answer: str
    retrieved: list[str]
    human: dict[str, bool]
    second: dict[str, bool] | None = None


def collect(tasks: list[Task], settings: Settings, labeler: Labeler, n: int, n_double: int, seed: int) -> list[Sample]:
    """Draws n (task, answer) pairs across configs and has experts label them; n_double get a second expert."""
    rng = random.Random(seed)
    research = [t for t in tasks if t.family == "research"]
    picks = [(rng.choice(research), CALIBRATION_CONFIGS[i % len(CALIBRATION_CONFIGS)]) for i in range(n)]
    out = []
    for k, (t, cfg) in enumerate(picks):
        o = answer(t, cfg, settings, seed + k)
        human = labeler.label(t, o.text, "a1", "calibration")
        second = labeler.label(t, o.text, "a2", "calibration") if k < n_double else None
        out.append(Sample(t, o.text, o.retrieved, human, second))
    return out


@dataclass
class Report:
    judge: str
    rubric: str
    with_checks: bool
    agreement: float
    kappa: float
    judge_pass: float
    human_pass: float
    false_pass: int  # judge passed what experts failed: the dangerous direction
    false_fail: int
    long_bias: float  # (judge - human) pass rate on long answers minus the same on short ones
    criteria_kappa: dict[str, float]
    cost_eur: float
    n: int

    @property
    def name(self) -> str:
        return f"judge-{self.judge}/{self.rubric}" + ("+checks" if self.with_checks else "")

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "judge": self.judge,
            "rubric": self.rubric,
            "with_checks": self.with_checks,
            "agreement": round(self.agreement, 3),
            "kappa": round(self.kappa, 3),
            "judge_pass": round(self.judge_pass, 3),
            "human_pass": round(self.human_pass, 3),
            "false_pass": self.false_pass,
            "false_fail": self.false_fail,
            "long_bias": round(self.long_bias, 3),
            "criteria_kappa": {k: round(v, 3) for k, v in self.criteria_kappa.items()},
            "cost_eur": round(self.cost_eur, 4),
            "n": self.n,
        }


def evaluate_judge(samples: list[Sample], tier: str, rubric: str, with_checks: bool, settings: Settings) -> Report:
    jp, hp, long_d, short_d = [], [], [], []
    crit: dict[str, tuple[list[bool], list[bool]]] = {}
    cost = 0.0
    for s in samples:
        j = judge(s.task, s.answer, s.retrieved, tier, rubric, settings)
        cost += j.cost_eur
        if rubric == "v2":
            ok = j.criteria["correct"] and j.criteria["no_overclaim"]
            if with_checks:
                ok = ok and checks_for(s.task, s.answer).passed
            else:
                ok = j.passed
        else:
            ok = j.passed and (checks_for(s.task, s.answer).passed if with_checks else True)
        h = passed(s.human)
        jp.append(ok)
        hp.append(h)
        (long_d if len(s.answer) > 400 else short_d).append(int(ok) - int(h))
        for k, v in j.criteria.items():
            if k in s.human:
                crit.setdefault(k, ([], []))
                crit[k][0].append(v)
                crit[k][1].append(s.human[k])
    n = len(samples)
    mean = lambda x: sum(x) / len(x) if x else 0.0
    return Report(
        tier,
        rubric,
        with_checks,
        sum(a == b for a, b in zip(jp, hp)) / n,
        cohen_kappa(jp, hp),
        mean(jp),
        mean(hp),
        sum(1 for a, b in zip(jp, hp) if a and not b),
        sum(1 for a, b in zip(jp, hp) if b and not a),
        mean(long_d) - mean(short_d),
        {k: cohen_kappa(a, b) for k, (a, b) in crit.items()},
        cost,
        n,
    )


def human_agreement(samples: list[Sample]) -> dict:
    pairs = [(passed(s.human), passed(s.second)) for s in samples if s.second is not None]
    a, b = [x for x, _ in pairs], [y for _, y in pairs]
    return {
        "n": len(pairs),
        "agreement": round(sum(x == y for x, y in pairs) / max(1, len(pairs)), 3),
        "kappa": round(cohen_kappa(a, b), 3),
    }


def calibrate(samples: list[Sample], settings: Settings) -> dict:
    reports = [
        evaluate_judge(samples, t, r, chk, settings)
        for t, r in JUDGES
        for chk in ((False, True) if r == "v2" else (False,))
    ]
    trusted = [r for r in reports if r.kappa >= settings.calibration.min_kappa]
    best = max(trusted, key=lambda r: (round(r.kappa, 3), r.with_checks, -r.cost_eur)) if trusted else None
    human_rate: Interval = wilson(sum(passed(s.human) for s in samples), len(samples))
    return {
        "reports": [r.as_dict() for r in reports],
        "selected": best.name if best else None,
        "min_kappa": settings.calibration.min_kappa,
        "humans": human_agreement(samples),
        "human_pass": human_rate.as_dict(),
        "n": len(samples),
    }
