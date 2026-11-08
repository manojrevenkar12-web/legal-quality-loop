"""Loads config/qloop.toml into typed settings. Unknown or missing keys fail, so a typo cannot silently fall back."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Run(Strict):
    seed: int


class Tasks(Strict):
    heldout_topics: list[str]


class ModelTier(Strict):
    price_in: float
    price_out: float
    wrong_value: float
    omit_point: float
    invent_when_missing: float
    follow_wrong_jurisdiction: float
    wrong_language: float
    follow_injection: float
    misread_number_words: float
    overclaim_when_assertive: float


class Levers(Strict):
    quote_then_answer_error: float
    quote_then_answer_tokens: float
    self_check_error: float
    self_check_invent: float
    self_check_language: float
    self_check_cost: float
    cite_only_retrieved_invent: float
    answer_in_question_language: float
    documents_as_data_injection: float
    detailed_tokens: float


class JudgeTier(Strict):
    price_in: float
    price_out: float
    notices_overclaim: float
    length_bonus_chars: int


class Labels(Strict):
    cost_per_item_eur: float
    calibration_items: int
    audit_items: int
    double_labelled: int
    annotator_flip: float


class Stats(Strict):
    bootstrap: int
    alpha: float


class Calibration(Strict):
    min_kappa: float


class Gate(Strict):
    non_inferiority_margin: float
    max_injection_success: float
    max_ungrounded_citation: float
    max_cost_per_1k_queries_eur: float


class Optimizer(Strict):
    iterations: int
    minibatch: int
    children_per_iteration: int
    cost_weight: float
    goodhart_gap: float


class Settings(Strict):
    run: Run
    tasks: Tasks
    models: dict[str, ModelTier]
    levers: Levers
    judges: dict[str, JudgeTier]
    labels: Labels
    stats: Stats
    calibration: Calibration
    gate: Gate
    optimizer: Optimizer


def load(path: Path | None = None) -> Settings:
    path = path or ROOT / "config" / "qloop.toml"
    with open(path, "rb") as f:
        return Settings.model_validate(tomllib.load(f))
