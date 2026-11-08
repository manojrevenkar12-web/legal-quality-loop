"""Human labels: experts grading answers, with the occasional slip, at a cost per item.

This is the platform's only legitimate contact with expert judgment, and it is budgeted: every label is counted and
priced, so the dashboard can say what a calibration or an audit cost.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from qloop.config import Settings
from qloop.world import expert
from qloop.world.tasks import Task


@dataclass
class Labeler:
    settings: Settings
    spent_eur: float = 0.0
    items: int = 0
    log: list[dict] = field(default_factory=list)

    def label(self, task: Task, answer: str, annotator: str = "a1", purpose: str = "") -> dict[str, bool]:
        g = expert.grade(task, answer).criteria
        flip = self.settings.labels.annotator_flip
        out = {}
        for k, v in g.items():
            h = hashlib.sha256(f"{annotator}|{task.id}|{answer}|{k}".encode()).digest()
            out[k] = (not v) if int.from_bytes(h[:8], "big") / 2**64 < flip else v
        self.spent_eur += self.settings.labels.cost_per_item_eur
        self.items += 1
        self.log.append({"task": task.id, "annotator": annotator, "purpose": purpose})
        return out


def passed(criteria: dict[str, bool]) -> bool:
    return all(criteria.values())
