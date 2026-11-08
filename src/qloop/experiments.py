"""The experiments behind the README's numbers. `development()` uses only the development set; `heldout()` evaluates
the configs chosen there on the held-out set, once. Expert grades (qloop.meta) are read here and only here, to report
how right the platform's own numbers were."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from qloop import coverage
from qloop.app.assistant import AppConfig
from qloop.config import ROOT, Settings
from qloop.gate import compare
from qloop.guardrails import redteam
from qloop.judges import calibration
from qloop.labels import Labeler
from qloop.meta import truth
from qloop.optimize.gepa import Result, audit, optimize
from qloop.privacy import Redactor
from qloop.runner import NAIVE, TRUSTED, Run, Scorer, evaluate
from qloop.stats import paired_difference, tied_groups
from qloop.tracing import events, write
from qloop.world.tasks import Task, all_tasks, fingerprint

BASELINE = AppConfig()  # the large model with default prompts: what a team ships before it has evals
START = AppConfig(model="medium")
CHEAP_START = AppConfig(model="small")


def tasks(settings: Settings) -> tuple[list[Task], list[Task]]:
    ts = all_tasks(settings.tasks.heldout_topics)
    return [t for t in ts if t.split == "dev"], [t for t in ts if t.split == "heldout"]


def _splits(dev: list[Task], seed: int) -> tuple[list[Task], list[Task], list[Task]]:
    """train (minibatches), validation (selection), audit (expert labels): disjoint, stratified by family."""
    rng = random.Random(seed)
    train, val, aud = [], [], []
    for fam in ("research", "review", "discovery"):
        group = [t for t in dev if t.family == fam]
        rng.shuffle(group)
        a, v = len(group) // 4, len(group) * 3 // 8
        aud += group[:a]
        val += group[a : a + v]
        train += group[a + v :]
    return train, val, aud


def _dataset(dev: list[Task], held: list[Task]) -> dict:
    rows = Counter((t.split, t.family) for t in dev + held)
    return {
        "items": {f"{s}/{f}": n for (s, f), n in sorted(rows.items())},
        "jurisdictions": dict(Counter(t.jurisdiction for t in dev + held)),
        "languages": dict(Counter(t.language for t in dev + held)),
        "injected_documents": sum(t.injected for t in dev + held),
        "heldout_topics": sorted({t.topic for t in held}),
        "heldout_pin": fingerprint(held),
    }


def _landscape(run: Run) -> list[dict]:
    exp = truth.passes(run)
    cells: dict[tuple[str, str], list[tuple[bool, bool]]] = {}
    for item, t in zip(run.items, exp):
        cells.setdefault((item.task.family, item.task.jurisdiction), []).append((item.passed, t))
    measure = {
        "research": "calibrated judge for facts and overclaims, code for citations, jurisdiction and language",
        "review": "position and playbook rule against the reference, citation checked in code",
        "discovery": "field-level match, every value must stand in the document outside injected text",
    }
    out = []
    for (fam, j), pairs in sorted(cells.items()):
        n = len(pairs)
        out.append(
            {
                "family": fam,
                "jurisdiction": j,
                "n": n,
                "platform_pass": round(sum(p for p, _ in pairs) / n, 3),
                "expert_pass": round(sum(t for _, t in pairs) / n, 3),
                "measure": measure[fam],
            }
        )
    return out


def _search(name: str, result: Result, aud: dict, settings: Settings) -> dict:
    traj = []
    by_key = {c.cfg.key(): c for c in result.candidates}
    for row in result.trajectory:
        r = dict(row)
        c = by_key.get(row["key"])
        if row.get("accepted") and c is not None:
            r["expert_pass"] = round(truth.rate(c.val).estimate, 4)
        traj.append(r)
    best = result.best
    return {
        "name": name,
        "scorer": result.scorer,
        "rollouts": result.rollouts,
        "candidates": len(result.candidates),
        "start": result.candidates[0].cfg.model_dump(),
        "best": best.cfg.model_dump(),
        "best_key": best.cfg.key(),
        "fitness": {"start": round(result.candidates[0].fitness, 4), "best": round(best.fitness, 4)},
        "val_pass": {"start": round(result.candidates[0].val.pass_rate, 4), "best": round(best.val.pass_rate, 4)},
        "val_expert": {
            "start": round(truth.rate(result.candidates[0].val).estimate, 4),
            "best": round(truth.rate(best.val).estimate, 4),
        },
        "cost_per_1k": {
            "start": round(result.candidates[0].val.cost_per_1k, 4),
            "best": round(best.val.cost_per_1k, 4),
        },
        "audit": aud,
        "trajectory": traj,
    }


def _injection(all_injected: list[Task], settings: Settings) -> list[dict]:
    rows = []
    for label, cfg in (
        ("no defence", AppConfig()),
        ("documents as data (prompt)", AppConfig(documents_as_data=True)),
        ("injection guard (input filter)", AppConfig(injection_guard=True)),
        ("both", AppConfig(documents_as_data=True, injection_guard=True)),
        ("small model, no defence", AppConfig(model="small")),
        ("small model, both", AppConfig(model="small", documents_as_data=True, injection_guard=True)),
    ):
        run = evaluate(cfg, all_injected, settings, TRUSTED)
        from qloop.world import expert as E

        obeyed = [not E.grade(i.task, i.answer).criteria["no_injection"] for i in run.items]
        flagged = [not i.checks.no_injected_value for i in run.items]
        rows.append(
            {
                "defence": label,
                "n": len(run.items),
                "obeyed": sum(obeyed),
                "caught_by_output_check": sum(o and f for o, f in zip(obeyed, flagged)),
                "false_flags": sum(f and not o for o, f in zip(obeyed, flagged)),
            }
        )
    return rows


def development(settings: Settings) -> dict:
    seed = settings.run.seed
    dev, held = tasks(settings)
    train, val, aud_tasks = _splits(dev, seed)
    labeler = Labeler(settings)

    # 1. calibrate the judges on expert labels, before any of them scores anything
    samples = calibration.collect(
        dev, settings, labeler, settings.labels.calibration_items, settings.labels.double_labelled, seed
    )
    cal = calibration.calibrate(samples, settings)
    cal["spent_eur"] = round(labeler.spent_eur, 2)
    cal["labels"] = labeler.items
    labelled = {s.task.id for s in samples}

    # 2. the quality landscape of the baseline
    base = evaluate(BASELINE, dev, settings, TRUSTED)
    naive_base = evaluate(BASELINE, dev, settings, NAIVE)

    # 3. three searches: against the naive judge, against the trusted scorer, and the cheapest model only
    searches = []
    for name, start, scorer, frozen in (
        ("naive judge", START, NAIVE, frozenset()),
        ("trusted scorer", START, TRUSTED, frozenset()),
        ("small model only", CHEAP_START, TRUSTED, frozenset({"model"})),
    ):
        before = labeler.spent_eur
        res = optimize(start, train, val, scorer, settings, seed, frozen)
        aud = audit(res, start, aud_tasks, settings, labeler).as_dict()
        aud["spent_eur"] = round(labeler.spent_eur - before, 2)
        searches.append(_search(name, res, aud, settings))

    # 4. are the platform's rankings real? configs from the searches, ranked with bounds
    configs = {"baseline": BASELINE, "start": START} | {s["name"]: AppConfig(**s["best"]) for s in searches}
    runs = {k: evaluate(c, val, settings, TRUSTED) for k, c in configs.items()}
    groups = tied_groups(
        list(runs),
        {k: [float(i.passed) for i in r.items] for k, r in runs.items()},
        settings.stats.bootstrap,
        settings.stats.alpha,
    )

    mixed = evaluate(AppConfig(model="small"), [t for t in dev if t.family == "research"], settings, TRUSTED)
    return {
        "dataset": _dataset(dev, held),
        "splits": {"train": len(train), "validation": len(val), "audit": len(aud_tasks)},
        "calibration": cal,
        "coverage": coverage.clusters([t for t in dev if t.family == "research"], labelled, 8, seed),
        "baseline": {
            "config": BASELINE.model_dump(),
            "trusted": base.summary(),
            "naive_pass": round(naive_base.pass_rate, 4),
            "expert": truth.rate(base).as_dict(),
            "landscape": _landscape(base),
        },
        "searches": searches,
        "ranking": {
            "validation_items": len(val),
            "groups": groups,
            "means": {k: round(r.pass_rate, 4) for k, r in runs.items()},
            "cost_per_1k": {k: round(r.cost_per_1k, 4) for k, r in runs.items()},
        },
        "checks_vs_experts": truth.planted(mixed),
        "redteam": redteam.run(),
        "injection": _injection([t for t in dev if t.injected], settings),
        "labels": {"items": labeler.items, "spent_eur": round(labeler.spent_eur, 2)},
    }


def heldout(settings: Settings, dev_report: dict) -> dict:
    seed = settings.run.seed
    _, held = tasks(settings)
    configs = {"baseline (large, default prompts)": BASELINE, "search start (medium)": START}
    for s in dev_report["searches"]:
        configs[f"best: {s['name']}"] = AppConfig(**s["best"])
    runs = {k: evaluate(c, held, settings, TRUSTED) for k, c in configs.items()}
    base = runs["baseline (large, default prompts)"]
    base_truth = [float(x) for x in truth.passes(base)]
    kappa = next(
        (
            r["kappa"]
            for r in dev_report["calibration"]["reports"]
            if r["name"] == dev_report["calibration"]["selected"]
        ),
        None,
    )
    rows = []
    for name, run in runs.items():
        t = [float(x) for x in truth.passes(run)]
        diff = paired_difference(base_truth, t, settings.stats.bootstrap, settings.stats.alpha, seed)
        decision = compare(base, run, settings, kappa).as_dict() if run is not base else None
        expert_ok = diff.low >= -settings.gate.non_inferiority_margin
        rows.append(
            {
                "name": name,
                "config": run.config.model_dump(),
                "platform_pass": run.interval().as_dict(),
                "expert_pass": truth.rate(run).as_dict(),
                "expert_diff_vs_baseline": diff.as_dict(),
                "naive_judge_pass": round(evaluate(run.config, held, settings, NAIVE).pass_rate, 4),
                "cost_per_1k_eur": round(run.cost_per_1k, 4),
                "guardrails": {k: v.as_dict() for k, v in run.guardrail_rates().items()},
                "by_family": {f: v for f, v in run.breakdown("family").items()},
                "gate": decision,
                "gate_right": None
                if decision is None
                else (decision["verdict"] == "ship") == expert_ok
                if decision["verdict"] != "inconclusive"
                else None,
            }
        )
    redactor = Redactor(b"qloop-trace-key")
    evs = events(base, "heldout", redactor)
    trace_path = ROOT / "reports" / "traces" / "heldout-baseline.jsonl"
    write(trace_path, evs)
    raw = trace_path.read_text()
    leaked = sum(
        s in raw for s in ("@havel-software.de", "@grachten.nl", "DE02120300000000202051", "Rheinfels Pharma GmbH")
    )
    return {
        "pin": fingerprint(held),
        "items": len(held),
        "configs": rows,
        "injection": _injection([t for t in held if t.injected], settings),
        "traces": {"events": len(evs), "file": str(trace_path.relative_to(ROOT)), "raw_secrets_found": leaked},
    }


def write_json(path: Path, data: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str) + "\n")


__all__ = ["Scorer", "development", "heldout", "write_json"]
