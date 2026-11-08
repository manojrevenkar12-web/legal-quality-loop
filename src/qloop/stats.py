"""The statistics the platform reports instead of single numbers: bounds, paired differences, and whether a ranking
survives the noise."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    def contains(self, x: float) -> bool:
        return self.low <= x <= self.high

    def as_dict(self) -> dict[str, float]:
        return {"estimate": round(self.estimate, 4), "low": round(self.low, 4), "high": round(self.high, 4)}


def wilson(successes: int, n: int, alpha: float = 0.05) -> Interval:
    """Wilson score interval for a proportion: honest at small n and near 0 or 1, where the normal one is not."""
    if n == 0:
        return Interval(0.0, 0.0, 1.0)
    z = _z(alpha)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half))


def _z(alpha: float) -> float:
    from scipy.stats import norm

    return float(norm.ppf(1 - alpha / 2))


def bootstrap_mean(x: Sequence[float], n_boot: int, alpha: float, seed: int = 0) -> Interval:
    a = np.asarray(x, dtype=float)
    if len(a) == 0:
        return Interval(0.0, 0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = a[rng.integers(0, len(a), (n_boot, len(a)))].mean(axis=1)
    return Interval(float(a.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def paired_difference(a: Sequence[float], b: Sequence[float], n_boot: int, alpha: float, seed: int = 0) -> Interval:
    """Bootstrap interval of mean(b - a) over the same items: what a candidate b changes against a baseline a."""
    d = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    return bootstrap_mean(d, n_boot, alpha, seed)


def mcnemar(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Exact two-sided McNemar p-value for paired pass/fail outcomes."""
    from scipy.stats import binomtest

    b_only = sum(1 for x, y in zip(a, b) if not x and y)
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    n = a_only + b_only
    if n == 0:
        return 1.0
    return float(binomtest(min(a_only, b_only), n, 0.5).pvalue)


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm-adjusted p-values: many comparisons, one error rate."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    m = len(pvalues)
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvalues[i])
        adjusted[i] = min(1.0, running)
    return adjusted


def cohen_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def items_needed(p: float, delta: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Items per arm to tell pass rate p from p + delta (normal approximation): when a result is inconclusive,
    how much more data would settle it."""
    from scipy.stats import norm

    if delta <= 0:
        return 0
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    q = p + delta
    var = p * (1 - p) + q * (1 - q)
    return int(math.ceil((za + zb) ** 2 * var / delta**2))


def tied_groups(names: list[str], scores: dict[str, list[float]], n_boot: int, alpha: float) -> list[list[str]]:
    """Ranks configs by mean and merges neighbours whose paired difference interval contains zero: the ranking a
    reader may trust."""
    ranked = sorted(names, key=lambda n: -float(np.mean(scores[n])))
    groups: list[list[str]] = []
    for name in ranked:
        if groups and paired_difference(scores[groups[-1][0]], scores[name], n_boot, alpha).contains(0.0):
            groups[-1].append(name)
        else:
            groups.append([name])
    return groups
