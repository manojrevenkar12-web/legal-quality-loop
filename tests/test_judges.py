from qloop.judges.llm_judge import judge


def _task(dev, topic="notice_period", lang="en", jur="DE"):
    return next(t for t in dev if t.topic == topic and t.language == lang and t.jurisdiction == jur)


def test_small_judge_reads_only_the_reference_wording(dev, settings):
    t = _task(dev)
    from qloop.lang import realise

    digits = "Under § 622 BGB: " + "; ".join(realise(p, "en", False) for p in t.reference.points) + "."
    assert not judge(t, digits, ["DE-BGB-622"], "small", "v2", settings).criteria["correct"]
    assert judge(t, digits, ["DE-BGB-622"], "large", "v2", settings).criteria["correct"]


def test_small_judge_rewards_confidence(dev, settings):
    t = _task(dev)
    plain = "Under § 622 BGB: one month."
    confident = "Clearly, " + plain + " " + "x" * 600
    assert judge(t, confident, [], "small", "v1", settings).score > judge(t, plain, [], "small", "v1", settings).score


def test_large_judge_checks_the_country_of_a_citation(dev, settings):
    t = _task(dev)
    from qloop.lang import realise

    facts = "; ".join(realise(p, "en", True) for p in t.reference.points)
    r = judge(t, f"Under art. 7:672 BW: {facts}.", ["NL-BW-7-672"], "large", "v2", settings)
    assert not r.criteria["jurisdiction"] and "another jurisdiction" in " ".join(r.rationale)
