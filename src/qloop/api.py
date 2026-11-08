"""Self-service evaluation over HTTP: an AI Engineer posts a config and gets the scored run, compares a candidate with
a baseline through the gate, or reads the calibration and the experiment results the dashboard shows."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from qloop.app.assistant import AppConfig
from qloop.config import ROOT, Settings, load
from qloop.gate import compare
from qloop.runner import TRUSTED, Run, Scorer, evaluate
from qloop.world.tasks import Task, all_tasks

FAMILIES = ("research", "review", "discovery")


class EvalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: AppConfig = Field(default_factory=AppConfig)
    families: list[str] = Field(default_factory=lambda: list(FAMILIES))
    split: str = "dev"
    judge: str = "large"
    rubric: str = "v2"
    checks: bool = True
    include_items: bool = False


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline: AppConfig
    candidate: AppConfig
    families: list[str] = Field(default_factory=lambda: list(FAMILIES))


def create_app(settings: Settings | None = None, reports: Path | None = None) -> FastAPI:
    settings = settings or load()
    reports = reports or ROOT / "reports"
    app = FastAPI(title="legal-quality-loop", version="1.0.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["*"]
    )

    @lru_cache(maxsize=1)
    def tasks() -> list[Task]:
        return all_tasks(settings.tasks.heldout_topics)

    def select(families: list[str], split: str) -> list[Task]:
        if split == "heldout":
            raise HTTPException(403, "the held-out set runs once, through `qloop heldout`, not on request")
        if split != "dev":
            raise HTTPException(422, "split must be dev")
        bad = set(families) - set(FAMILIES)
        if bad:
            raise HTTPException(422, f"unknown families: {sorted(bad)}")
        return [t for t in tasks() if t.split == split and t.family in families]

    def judge_kappa(scorer: Scorer) -> float | None:
        path = reports / "development.json"
        if not path.exists():
            return None
        cal = json.loads(path.read_text())["calibration"]
        return next((r["kappa"] for r in cal["reports"] if r["name"] == scorer.name), None)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/evaluate")
    def run_eval(req: EvalRequest) -> dict:
        scorer = Scorer(req.judge, req.rubric, req.checks)
        run: Run = evaluate(req.config, select(req.families, req.split), settings, scorer)
        out = run.summary()
        kappa = judge_kappa(scorer)
        out["judge_kappa"] = kappa
        out["judge_trusted"] = kappa is not None and kappa >= settings.calibration.min_kappa
        if req.include_items:
            out["items"] = [i.row() for i in run.items]
        return out

    @app.post("/compare")
    def run_compare(req: CompareRequest) -> dict:
        ts = select(req.families, "dev")
        base, cand = evaluate(req.baseline, ts, settings, TRUSTED), evaluate(req.candidate, ts, settings, TRUSTED)
        return {
            "baseline": base.summary(),
            "candidate": cand.summary(),
            "decision": compare(base, cand, settings, judge_kappa(TRUSTED)).as_dict(),
        }

    @app.get("/results")
    def results(part: str = Query("all", pattern="^(all|development|heldout)$")) -> dict:
        path = reports / "results.json"
        if not path.exists():
            raise HTTPException(404, "no results yet: run `qloop develop` and `qloop report`")
        data = json.loads(path.read_text())
        return data if part == "all" else data.get(part, {})

    @app.get("/calibration")
    def calibration() -> dict:
        path = reports / "development.json"
        if not path.exists():
            raise HTTPException(404, "not calibrated yet: run `qloop develop`")
        return json.loads(path.read_text())["calibration"]

    return app
