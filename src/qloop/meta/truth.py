"""The evaluation of the platform itself: what a full expert review of every answer would say. Only the experiments
in qloop.experiments read this, to report how right the platform's own numbers, gates and alarms were."""

from __future__ import annotations

from qloop.runner import Run
from qloop.stats import Interval, wilson
from qloop.world import expert


def passes(run: Run) -> list[bool]:
    return [expert.grade(i.task, i.answer).passed for i in run.items]


def rate(run: Run) -> Interval:
    p = passes(run)
    return wilson(sum(p), len(p))


def planted(run: Run) -> dict[str, dict[str, int]]:
    """How the deterministic checks did on the failures that experts see, per failure kind."""
    out: dict[str, dict[str, int]] = {}
    for i in run.items:
        if i.task.family != "research":
            continue
        g = expert.grade(i.task, i.answer).criteria
        for name, truth_bad, flagged in (
            (
                "invented or unsupported citation",
                not g["supported"],
                not (i.checks.citation_exists and i.checks.grounded),
            ),
            ("foreign-law citation", not g["jurisdiction"], not i.checks.citation_jurisdiction),
            ("wrong language", not g["language"], not i.checks.language),
        ):
            c = out.setdefault(name, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
            c["tp" if truth_bad and flagged else "fp" if flagged else "fn" if truth_bad else "tn"] += 1
    return out
