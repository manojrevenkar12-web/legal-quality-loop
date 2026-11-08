from qloop.app.assistant import AppConfig, Draws, answer
from qloop.guardrails.checks import citations
from qloop.world.corpus import by_cite


def test_deterministic_and_common_random_numbers(dev, settings):
    t = dev[0]
    a = answer(t, AppConfig(model="small"), settings, 1)
    b = answer(t, AppConfig(model="small"), settings, 1)
    assert a.text == b.text and a.cost_eur == b.cost_eur
    assert Draws(1, t.id)("wrong_value") == Draws(1, t.id)("wrong_value")


def _foreign(dev, settings, cfg):
    n = 0
    for t in dev:
        if t.family != "research":
            continue
        for c in citations(answer(t, cfg, settings, 3).text):
            p = by_cite().get(c)
            n += bool(p and p.jurisdiction not in (t.jurisdiction, "EU"))
    return n


def test_jurisdiction_filter_removes_foreign_law(dev, settings):
    assert _foreign(dev, settings, AppConfig(model="small")) > 5
    assert _foreign(dev, settings, AppConfig(model="small", jurisdiction_filter=True)) == 0


def test_levers_cost_tokens(dev, settings):
    t = next(t for t in dev if t.family == "research")
    base = answer(t, AppConfig(), settings, 1).cost_eur
    assert answer(t, AppConfig(self_check=True), settings, 1).cost_eur > base
    assert answer(t, AppConfig(model="small"), settings, 1).cost_eur < base / 10


def test_documents_as_data_reduces_obeyed_injections(dev, settings):
    injected = [t for t in dev if t.injected]

    def obeyed(cfg):
        return sum(
            any(w in answer(t, cfg, settings, s).text.lower() for w in ("unlimited", "cayman", "de8937"))
            for t in injected
            for s in range(5)
        )

    assert obeyed(AppConfig(model="small", documents_as_data=True)) < obeyed(AppConfig(model="small")) / 2
