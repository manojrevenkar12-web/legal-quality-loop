"""A GEPA-style optimizer over the app's levers, and the audit that catches it when it optimizes the judge instead of
the answers.

GEPA (reflective prompt evolution) keeps a pool of candidates, picks a parent from the Pareto front of per-task
scores, runs it on a minibatch, reads the feedback the scorer wrote for each answer, and proposes children that act
on it. Here the reflection step is a fixed table from feedback to lever changes, standing in for the reflection
model, so runs are reproducible; the feedback it reads is whatever the chosen scorer wrote, which is the point:

- against a naive judge (small model, holistic rubric) the feedback praises "thorough and confident" answers and
  asks for the reference's wording, so the search learns to be confident, long and to spell numbers out;
- against the trusted scorer (a calibrated judge plus checks) the feedback names invented citations, foreign law,
  the wrong language and injected instructions, so the search learns the levers that fix those.

The audit is the platform's defence: experts label a fixed sample of the start and the final candidate's answers. If
the fitness rose but the experts' pass rate did not rise with it, the run is flagged before anyone ships it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from qloop.app.assistant import AppConfig
from qloop.config import Settings
from qloop.labels import Labeler, passed
from qloop.runner import Run, Scorer, evaluate
from qloop.stats import paired_difference
from qloop.world.tasks import Task

MODELS = ["small", "medium", "large"]

REFLECTIONS: list[tuple[str, list[dict]]] = [
    ("citation not among the provided sources", [{"cite_only_retrieved": True}, {"retrieval_k": 2}, {"self_check": True}]),
    ("no citation", [{"retrieval_k": 2}, {"jurisdiction_filter": True}]),
    ("another jurisdiction", [{"jurisdiction_filter": True}]),
    ("citation_jurisdiction", [{"jurisdiction_filter": True}]),
    ("language", [{"answer_in_question_language": True}]),
    ("misses:", [{"quote_then_answer": True}, {"number_style": "words"}, {"self_check": True}, {"model": "up"}]),
    ("bonus: thorough and confident", [{"tone": "assertive"}, {"verbosity": "detailed"}]),
    ("fuller, more decisive", [{"tone": "assertive"}, {"verbosity": "detailed"}]),
    ("states something the sources do not support", [{"tone": "neutral"}]),
    ("check failed: grounded", [{"quote_then_answer": True}, {"cite_only_retrieved": True}]),
    ("check failed: citation_exists", [{"cite_only_retrieved": True}, {"self_check": True}]),
    ("check failed: has_citation", [{"retrieval_k": 2}]),
    ("check failed: fields_grounded", [{"injection_guard": True}, {"documents_as_data": True}]),
    ("check failed: no_secret", [{"injection_guard": True}, {"documents_as_data": True}]),
    ("extracted fields differ", [{"documents_as_data": True}, {"injection_guard": True}]),
    ("position or rule differs", [{"quote_then_answer": True}, {"self_check": True}]),
]
CHEAPER = [{"model": "down"}, {"verbosity": "concise"}, {"self_check": False}, {"retrieval_k": -1}]


def mutate(cfg: AppConfig, change: dict, frozen: frozenset[str] = frozenset()) -> AppConfig:
    d = cfg.model_dump()
    for k, v in change.items():
        if k in frozen:
            continue
        if k == "model":
            i = MODELS.index(d["model"]) + (1 if v == "up" else -1)
            d["model"] = MODELS[max(0, min(2, i))]
        elif k == "retrieval_k":
            d["retrieval_k"] = max(2, min(8, d["retrieval_k"] + v))
        else:
            d[k] = v
    return AppConfig(**d)


def reflect(feedback: list[str], rewarded: list[str], rng: random.Random, n: int) -> list[dict]:
    """Proposals, most-cited problem first; what the scorer rewarded counts as a reason too."""
    counts: dict[int, int] = {}
    for text in feedback + rewarded:
        for i, (pattern, _) in enumerate(REFLECTIONS):
            if pattern in text:
                counts[i] = counts.get(i, 0) + 1
    ranked = sorted(counts, key=lambda i: -counts[i])
    proposals: list[dict] = []
    for i in ranked:
        options = REFLECTIONS[i][1]
        proposals.append(options[rng.randrange(len(options))])
        if len(proposals) == n:
            break
    while len(proposals) < n:
        proposals.append(CHEAPER[rng.randrange(len(CHEAPER))])
    if len(proposals) >= 2 and rng.random() < 0.5:  # a merged child, as GEPA's merge step does
        proposals[-1] = {**proposals[0], **proposals[1]}
    return proposals


@dataclass
class Candidate:
    cfg: AppConfig
    parent: str | None
    change: dict
    val: Run
    fitness: float
    iteration: int


@dataclass
class Result:
    scorer: str
    candidates: list[Candidate]
    best: Candidate
    rollouts: int
    trajectory: list[dict] = field(default_factory=list)


def fitness(run: Run, settings: Settings) -> float:
    return run.pass_rate - settings.optimizer.cost_weight * run.cost_per_1k


def optimize(start: AppConfig, train: list[Task], val: list[Task], scorer: Scorer, settings: Settings, seed: int,
             frozen: frozenset[str] = frozenset()) -> Result:
    """Searches from `start`; levers named in `frozen` stay as they are (for example the model, to find the best
    configuration of a cheaper one)."""
    opt = settings.optimizer
    rng = random.Random(seed)
    first = evaluate(start, val, settings, scorer)
    pool = [Candidate(start, None, {}, first, fitness(first, settings), 0)]
    rollouts = len(val)
    trajectory = [{"iteration": 0, "key": start.key(), "fitness": round(pool[0].fitness, 4), "accepted": True,
                   "change": {}, "pass": round(first.pass_rate, 4), "cost_per_1k": round(first.cost_per_1k, 3)}]
    seen = {start.key()}
    for it in range(1, opt.iterations + 1):
        parent = _pareto_pick(pool, rng)
        batch = rng.sample(train, min(opt.minibatch, len(train)))
        p_run = evaluate(parent.cfg, batch, settings, scorer)
        rollouts += len(batch)
        failures = [f for i in p_run.items if not i.passed for f in i.feedback]
        rewarded = [f for i in p_run.items if i.passed for f in i.feedback if f.startswith("bonus")]
        for change in reflect(failures, rewarded, rng, opt.children_per_iteration):
            child = mutate(parent.cfg, change, frozen)
            if child.key() in seen:
                continue
            seen.add(child.key())
            c_run = evaluate(child, batch, settings, scorer)
            rollouts += len(batch)
            accepted = fitness(c_run, settings) >= fitness(p_run, settings)
            row = {"iteration": it, "key": child.key(), "parent": parent.cfg.key(), "change": change, "accepted": accepted}
            if accepted:
                v = evaluate(child, val, settings, scorer)
                rollouts += len(val)
                cand = Candidate(child, parent.cfg.key(), change, v, fitness(v, settings), it)
                pool.append(cand)
                row.update({"fitness": round(cand.fitness, 4), "pass": round(v.pass_rate, 4),
                            "cost_per_1k": round(v.cost_per_1k, 3)})
            trajectory.append(row)
    best = max(pool, key=lambda c: (c.fitness, -c.val.cost_per_1k))
    return Result(scorer.name, pool, best, rollouts, trajectory)


def _pareto_pick(pool: list[Candidate], rng: random.Random) -> Candidate:
    """A parent from the candidates that are best on at least one validation task, weighted by how many they win."""
    n = len(pool[0].val.items)
    wins = [0] * len(pool)
    for k in range(n):
        top = max(c.val.items[k].passed for c in pool)
        if not top:
            continue
        for i, c in enumerate(pool):
            if c.val.items[k].passed:
                wins[i] += 1
    if not any(wins):
        return rng.choice(pool)
    return rng.choices(pool, weights=[w + 1e-9 for w in wins])[0]


@dataclass
class Audit:
    start_pass: float
    final_pass: float
    human_diff: dict
    fitness_gain: float
    flagged: bool
    reason: str
    labels: int
    spent_eur: float

    def as_dict(self) -> dict:
        return {"start_human_pass": round(self.start_pass, 3), "final_human_pass": round(self.final_pass, 3),
                "human_diff": self.human_diff, "fitness_gain": round(self.fitness_gain, 4), "flagged": self.flagged,
                "reason": self.reason, "labels": self.labels, "spent_eur": round(self.spent_eur, 2)}


def audit(result: Result, start: AppConfig, audit_tasks: list[Task], settings: Settings, labeler: Labeler) -> Audit:
    """Experts label the start and the final candidate's answers on the same audit tasks."""
    before = labeler.items, labeler.spent_eur
    s_run = evaluate(start, audit_tasks, settings, Scorer(result.best.val.scorer.judge, result.best.val.scorer.rubric,
                                                           result.best.val.scorer.checks))
    f_run = evaluate(result.best.cfg, audit_tasks, settings, result.best.val.scorer)
    s_h = [float(passed(labeler.label(i.task, i.answer, "a1", "audit"))) for i in s_run.items]
    f_h = [float(passed(labeler.label(i.task, i.answer, "a1", "audit"))) for i in f_run.items]
    diff = paired_difference(s_h, f_h, settings.stats.bootstrap, settings.stats.alpha, seed=settings.run.seed)
    gain = result.best.fitness - result.candidates[0].fitness
    human_gain = diff.estimate
    flagged = gain - human_gain > settings.optimizer.goodhart_gap or diff.high < 0
    if diff.high < 0:
        reason = f"experts' pass rate fell {-human_gain:.0%} (bound {diff.high:+.0%}) while fitness rose {gain:+.0%}"
    elif flagged:
        reason = f"fitness rose {gain:+.0%}, experts' pass rate only {human_gain:+.0%}: the optimizer is fitting the judge"
    else:
        reason = f"experts confirm the gain: {human_gain:+.0%} (bounds {diff.low:+.0%} to {diff.high:+.0%})"
    return Audit(sum(s_h) / len(s_h), sum(f_h) / len(f_h), diff.as_dict(), gain, flagged, reason,
                 labeler.items - before[0], labeler.spent_eur - before[1])
