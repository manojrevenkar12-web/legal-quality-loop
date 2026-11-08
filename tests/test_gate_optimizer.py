import random

from qloop.app.assistant import AppConfig
from qloop.gate import compare
from qloop.labels import Labeler
from qloop.optimize.gepa import audit, mutate, optimize, reflect
from qloop.runner import NAIVE, TRUSTED, evaluate

DEFENDED = AppConfig(documents_as_data=True, injection_guard=True, jurisdiction_filter=True, cite_only_retrieved=True)


def test_gate_ships_an_equal_config_and_blocks_a_worse_one(dev, settings):
    base = evaluate(DEFENDED, dev, settings)
    assert compare(base, evaluate(DEFENDED, dev, settings), settings).verdict == "ship"
    worse = compare(base, evaluate(AppConfig(model="small", tone="assertive"), dev, settings), settings)
    assert worse.verdict == "block" and worse.quality_diff["high"] < 0


def test_gate_blocks_an_uncalibrated_judge_and_injections(dev, settings):
    base = evaluate(DEFENDED, dev, settings)
    d = compare(base, evaluate(DEFENDED, dev, settings), settings, judge_kappa=0.3)
    assert d.verdict == "block" and "kappa" in d.reasons[0]
    small = compare(base, evaluate(AppConfig(model="small"), dev, settings), settings)
    assert any("injection" in r for r in small.reasons)


def test_mutation_respects_frozen_levers():
    cfg = AppConfig(model="small")
    assert mutate(cfg, {"model": "up"}).model == "medium"
    assert mutate(cfg, {"model": "up", "tone": "assertive"}, frozenset({"model"})) == AppConfig(
        model="small", tone="assertive"
    )
    assert mutate(AppConfig(retrieval_k=8), {"retrieval_k": 2}).retrieval_k == 8


def test_reflection_acts_on_the_feedback():
    rng = random.Random(0)
    props = reflect(
        ["cites the law of another jurisdiction"] * 5 + ["answer is not in the language of the question"], [], rng, 2
    )
    assert {"jurisdiction_filter": True} in props


def test_trusted_search_improves_and_survives_the_audit(dev, settings):
    rng = random.Random(1)
    pool = dev[:]
    rng.shuffle(pool)
    train, val, aud = pool[:60], pool[60:120], pool[120:170]
    start = AppConfig(model="medium")
    trusted = optimize(start, train, val, TRUSTED, settings, 3)
    assert trusted.best.fitness > trusted.candidates[0].fitness
    assert not audit(trusted, start, aud, settings, Labeler(settings)).flagged


def test_naive_search_is_flagged(dev, settings):
    rng = random.Random(1)
    pool = dev[:]
    rng.shuffle(pool)
    train, val, aud = pool[:60], pool[60:120], pool[120:170]
    start = AppConfig(model="medium")
    naive = optimize(start, train, val, NAIVE, settings, 3)
    a = audit(naive, start, aud, settings, Labeler(settings))
    assert a.flagged and a.labels == 2 * len(aud)
