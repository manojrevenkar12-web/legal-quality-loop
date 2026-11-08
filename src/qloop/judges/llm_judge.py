"""LLM-as-judge, simulated with the failure modes real judges have.

A judge reads the question, the answer, the sources the assistant retrieved and the Legal Engineers' reference, and
grades against a versioned rubric:

- rubric v1 is holistic: "rate the answer 1-5 against the reference"; pass at 4.
- rubric v2 is criterion by criterion: right facts, a citation from the provided sources that supports them, the
  question's jurisdiction, the question's language, no statement the sources do not support.

The small judge reads like a cheap model: it looks for the reference's own wording, so "3 months" does not match
"three months", it rewards long and confident answers, and it rarely notices an overclaim. The large judge reads
facts in any style, checks which country a citation belongs to, and notices most overclaims. Neither reads anything
an expert has not written into the dataset; how often they agree with experts is measured in calibration.py.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from qloop.config import Settings
from qloop.guardrails.checks import citations
from qloop.lang import extract, language, normalise, realise
from qloop.world.corpus import by_cite, provisions
from qloop.world.phrases import CONFIDENT
from qloop.world.tasks import Task

LAW_COUNTRY = {
    "BGB": "DE",
    "KSchG": "DE",
    "HGB": "DE",
    "AngG": "AT",
    "ABGB": "AT",
    "UGB": "AT",
    "BW": "NL",
    "GDPR": "EU",
}


@dataclass(frozen=True)
class JudgeResult:
    judge: str
    rubric: str
    passed: bool
    score: float
    criteria: dict[str, bool]
    rationale: list[str] = field(default_factory=list)
    cost_eur: float = 0.0


def _u(*parts: str) -> float:
    h = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def _points_matched(task: Task, answer: str, tier: str) -> tuple[int, list[str]]:
    gold = list(task.reference.points)
    missed: list[str] = []
    if tier == "small":
        text = normalise(answer)
        for p in gold:
            surface = normalise(realise(p, task.language, words=True))
            if surface not in text:
                missed.append(surface)
    else:
        stated = extract(answer)
        missed = [realise(p, task.language, True) for p in gold if p not in stated]
    return len(gold) - len(missed), missed


def _cost(settings: Settings, tier: str, task: Task, answer: str) -> float:
    t = settings.judges[tier]
    tin = (len(task.prompt) + len(answer) + len(task.reference.text) + 1200) // 4
    return (tin * t.price_in + 60 * t.price_out) / 1000


def judge(task: Task, answer: str, retrieved: list[str], tier: str, rubric: str, settings: Settings) -> JudgeResult:
    name = f"judge-{tier}"
    cost = _cost(settings, tier, task, answer)
    if task.family == "review":
        m = re.search(r"position:\s*(acceptable|fallback|unacceptable)", answer.lower())
        ok = bool(m) and m.group(1) == task.reference.label and task.reference.rule in answer
        return JudgeResult(
            name,
            rubric,
            ok,
            5.0 if ok else 1.0,
            {"correct": ok},
            [] if ok else ["position or rule differs from the reference"],
            cost,
        )
    if task.family == "discovery":
        low = answer.lower()
        ok = all(re.search(rf"{k}:\s*{re.escape(v.lower())}\s*$", low, re.MULTILINE) for k, v in task.reference.fields)
        return JudgeResult(
            name,
            rubric,
            ok,
            5.0 if ok else 1.0,
            {"correct": ok},
            [] if ok else ["extracted fields differ from the reference"],
            cost,
        )
    cfg = settings.judges[tier]
    matched, missed = _points_matched(task, answer, tier)
    total = len(task.reference.points)
    long_or_confident = len(answer) > cfg.length_bonus_chars or any(
        c in answer for c in CONFIDENT["en"] + CONFIDENT["de"]
    )
    rationale = [f"misses: {m}" for m in missed]
    if rubric == "v1":
        score = 1 + 4 * matched / total
        if long_or_confident and tier == "small":
            score += 1.5
            rationale.append("bonus: thorough and confident explanation")
        elif tier == "small" and score < 5:
            rationale.append("terse: a fuller, more decisive explanation would score higher")
        score = min(5.0, score)
        return JudgeResult(name, rubric, score >= 4, score, {"overall": score >= 4}, rationale, cost)
    cited = citations(answer)
    sources = {provisions()[i].cite for i in retrieved}
    ref_cites = {provisions()[c].cite for c in task.reference.citations}
    abstained = "do not answer this question" in answer or "beantworten diese Frage nicht" in answer
    supported = bool(cited) and all(c in sources for c in cited)
    if tier == "large":
        supported = supported and bool(set(cited) & ref_cites)
    if tier == "large":
        countries = {LAW_COUNTRY.get(c.split()[-1], "?") for c in cited}
        jurisdiction = countries <= {task.jurisdiction, "EU"}
    else:
        jurisdiction = True
    lang_ok = language(answer) == task.language
    overclaim_present = _has_overclaim(answer)
    noticed = overclaim_present and _u(name, task.id, answer) < cfg.notices_overclaim
    criteria = {
        "correct": matched == total and not abstained,
        "supported": supported,
        "jurisdiction": jurisdiction,
        "language": lang_ok,
        "no_overclaim": not noticed,
    }
    if not supported:
        rationale.append("citation not among the provided sources" if cited else "no citation")
    if not jurisdiction:
        rationale.append("cites the law of another jurisdiction")
    if not lang_ok:
        rationale.append("answer is not in the language of the question")
    if noticed:
        rationale.append("states something the sources do not support")
    score = 1 + 4 * sum(criteria.values()) / len(criteria)
    return JudgeResult(name, rubric, all(criteria.values()), score, criteria, rationale, cost)


def _has_overclaim(answer: str) -> bool:
    from qloop.world.phrases import all_overclaims

    return any(o in answer for o in all_overclaims())


def known_citation(c: str) -> bool:
    return c in by_cite()
