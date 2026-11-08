"""Failure analysis on a run: which failure reasons cluster where, as a pandas table, so a deep-dive starts from
the biggest lever instead of the first trace."""

from __future__ import annotations

import pandas as pd

from qloop.runner import Run


def frame(run: Run) -> pd.DataFrame:
    rows = []
    for i in run.items:
        reasons = i.feedback or ["passed"]
        for r in reasons:
            rows.append(
                {
                    "task": i.task.id,
                    "family": i.task.family,
                    "topic": i.task.topic,
                    "jurisdiction": i.task.jurisdiction,
                    "language": i.task.language,
                    "passed": i.passed,
                    "reason": r.split(":")[0] if r.startswith(("misses", "check failed")) and ":" in r else r,
                    "cost_eur": i.cost_eur,
                }
            )
    return pd.DataFrame(rows)


def failure_table(run: Run, by: str = "jurisdiction") -> pd.DataFrame:
    """Share of failed items carrying each reason, per group, most frequent reason first."""
    df = frame(run)
    failed = df[~df["passed"]]
    if failed.empty:
        return pd.DataFrame()
    counts = failed.groupby([by, "reason"])["task"].nunique().unstack(fill_value=0)
    totals = df.groupby(by)["task"].nunique()
    table = counts.div(totals, axis=0).round(3)
    return table[table.sum().sort_values(ascending=False).index]
