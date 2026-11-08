"""The legal sources the assistant retrieves from and every checker verifies citations against."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from qloop.config import ROOT


@dataclass(frozen=True)
class Provision:
    id: str
    jurisdiction: str  # DE, AT, NL, or EU (applies in all three)
    cite: str
    title: str
    text: str


@lru_cache(maxsize=1)
def provisions() -> dict[str, Provision]:
    raw = json.loads((ROOT / "data" / "corpus.json").read_text())
    return {p["id"]: Provision(**p) for p in raw["provisions"]}


def by_cite() -> dict[str, Provision]:
    return {p.cite: p for p in provisions().values()}


def applies_in(p: Provision, jurisdiction: str) -> bool:
    return p.jurisdiction in (jurisdiction, "EU")


_TOKEN = re.compile(r"[a-zäöüß0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "and",
    "or",
    "is",
    "for",
    "on",
    "by",
    "with",
    "be",
    "after",
    "must",
    "what",
    "how",
    "does",
    "do",
    "can",
    "which",
    "under",
    "law",
    "der",
    "die",
    "das",
    "und",
    "ein",
    "eine",
    "nach",
    "wie",
    "lange",
    "muss",
    "welche",
    "ist",
    "bei",
    "von",
    "mit",
    "zu",
    "den",
    "dem",
}

# German query words mapped to the English vocabulary of the summaries: the retriever is bilingual this far.
_DE_EN = {
    "kündigungsfrist": "notice period",
    "kündigung": "termination notice",
    "arbeitgeber": "employer",
    "arbeitnehmer": "employee",
    "beschäftigt": "employment",
    "jahre": "years",
    "verjährung": "limitation time-barred",
    "verjährt": "limitation time-barred",
    "schadensersatz": "damages",
    "verzugszinsen": "default interest",
    "zinsen": "interest",
    "datenpanne": "personal data breach",
    "aufsichtsbehörde": "supervisory authority",
    "melden": "notify",
    "e-mail": "written form electronic",
    "schriftform": "written form",
    "auskunftsersuchen": "request data subject",
    "bußgeld": "administrative fines",
    "fristlos": "without notice cause",
}


def tokens(text: str) -> list[str]:
    t = text.lower()
    for de, en in _DE_EN.items():
        if de in t:
            t += " " + en
    return [w for w in _TOKEN.findall(t) if w not in _STOP]


class BM25:
    """Plain BM25 over title and text. The jurisdiction filter is the app's choice, not the index's."""

    def __init__(self, docs: list[Provision], k1: float = 1.4, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tf = [Counter(tokens(d.title + " " + d.text)) for d in docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df: Counter[str] = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def search(self, query: str, k: int, jurisdiction: str | None = None) -> list[Provision]:
        q = tokens(query)
        scored = []
        for i, d in enumerate(self.docs):
            if jurisdiction and not applies_in(d, jurisdiction):
                continue
            s = 0.0
            for w in q:
                f = self.tf[i].get(w, 0)
                if f:
                    s += (
                        self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
                    )
            scored.append((s, d.id, d))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [d for s, _, d in scored[:k] if s > 0]


@lru_cache(maxsize=1)
def index() -> BM25:
    return BM25(list(provisions().values()))
