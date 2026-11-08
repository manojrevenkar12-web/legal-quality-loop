"""The legal facts an answer must state, how they are written in English and German, and how to read them back.

A Point is canonical ("3 month", "end_of_month", "9 pp base"). `realise` writes it the way a model might: in either
language, with digits or words. `extract` reads every point it can find in a text, whatever the language or style;
experts read like this. Judges in qloop.judges read less robustly, on purpose: that is what calibration measures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EN_NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
          "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
DE_NUM = ["null", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf",
          "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn", "zwanzig"]

UNITS = {
    "month": {"en": ("month", "months"), "de": ("Monat", "Monate")},
    "week": {"en": ("week", "weeks"), "de": ("Woche", "Wochen")},
    "year": {"en": ("year", "years"), "de": ("Jahr", "Jahre")},
    "hour": {"en": ("hour", "hours"), "de": ("Stunde", "Stunden")},
    "day": {"en": ("day", "days"), "de": ("Tag", "Tage")},
}

ANCHORS = {
    "end_of_month": {"en": "to the end of a calendar month", "de": "zum Ende eines Kalendermonats"},
    "end_of_quarter": {"en": "to the end of a calendar quarter", "de": "zum Ende eines Kalendervierteljahres"},
    "last_day_of_month": {"en": "ending on the last day of a month", "de": "zum letzten Tag eines Monats"},
    "end_of_year_knowledge": {"en": "running from the end of the year in which the claim arose and the creditor learned of it",
                              "de": "ab dem Schluss des Jahres, in dem der Anspruch entstand und der Gläubiger davon erfuhr"},
    "from_knowledge": {"en": "running from when the injured party learned of the damage and the liable person",
                       "de": "ab Kenntnis von Schaden und Schädiger"},
    "without_undue_delay": {"en": "without undue delay", "de": "unverzüglich"},
    "extendable_two_months": {"en": "extendable by two further months", "de": "um weitere zwei Monate verlängerbar"},
    "written_form": {"en": "termination requires written form", "de": "die Kündigung bedarf der Schriftform"},
    "no_email": {"en": "an email does not suffice", "de": "eine E-Mail genügt nicht"},
    "more_than_ten": {"en": "the business must regularly employ more than ten employees", "de": "der Betrieb muss regelmäßig mehr als zehn Arbeitnehmer beschäftigen"},
    "higher_of": {"en": "whichever is higher", "de": "je nachdem, welcher Betrag höher ist"},
}

RATE_BASES = {
    "base": {"en": "above the base rate", "de": "über dem Basiszinssatz"},
    "ecb": {"en": "above the ECB reference rate", "de": "über dem Referenzzinssatz der EZB"},
}


@dataclass(frozen=True)
class Point:
    """A canonical legal fact: kind is duration, anchor, rate or money."""

    kind: str
    value: str  # "3 month", "end_of_month", "9 base", "20m_or_4pct"

    def __str__(self) -> str:
        return f"{self.kind}:{self.value}"


def duration(n: int, unit: str) -> Point:
    return Point("duration", f"{n} {unit}")


def anchor(name: str) -> Point:
    assert name in ANCHORS, name
    return Point("anchor", name)


def rate(pp: float, base: str) -> Point:
    return Point("rate", f"{pp:g} {base}")


FINE = Point("money", "20m_or_4pct")


def num_word(n: int, lang: str) -> str:
    table = EN_NUM if lang == "en" else DE_NUM
    if 0 <= n < len(table):
        return table[n]
    return str(n)


def realise(p: Point, lang: str, words: bool) -> str:
    """Writes a point as a model would. `words` spells small numbers out."""
    if p.kind == "duration":
        n, unit = p.value.split()
        n = int(n)
        sing, plur = UNITS[unit][lang]
        noun = sing if n == 1 else plur
        num = num_word(n, lang) if words else str(n)
        if lang == "de" and words and n == 1:
            num = "einen" if unit in ("month",) else "eine" if unit in ("week", "hour") else "ein"
        return f"{num} {noun}"
    if p.kind == "anchor":
        return ANCHORS[p.value][lang]
    if p.kind == "rate":
        pp, base = p.value.split()
        pp_f = float(pp)
        if pp_f.is_integer():
            num = num_word(int(pp_f), lang) if words else str(int(pp_f))
        else:
            num = pp.replace(".", ",") if lang == "de" else pp
        unit = "percentage points" if lang == "en" else "Prozentpunkte"
        return f"{num} {unit} {RATE_BASES[base][lang]}"
    if p.kind == "money":
        if lang == "en":
            return "up to 20 million euros or " + ("four" if words else "4") + " percent of worldwide annual turnover, whichever is higher"
        return "bis zu 20 Millionen Euro oder " + ("vier" if words else "4") + " Prozent des weltweiten Jahresumsatzes, je nachdem, welcher Betrag höher ist"
    raise ValueError(p)


_UNIT_RE = {
    "month": r"(?:months?|monate?n?|monats)",
    "week": r"(?:weeks?|wochen?)",
    "year": r"(?:years?|jahre?n?|jahres)",
    "hour": r"(?:hours?|stunden?)",
    "day": r"(?:days?|tage?n?)",
}


def _number_map() -> dict[str, int]:
    m: dict[str, int] = {}
    for i, w in enumerate(EN_NUM):
        m[w] = i
    for i, w in enumerate(DE_NUM):
        m[w.lower()] = i
    m.update({"einen": 1, "eine": 1, "einem": 1, "an": 1, "a": 1})
    return m


NUMBERS = _number_map()
_NUM_TOKEN = r"(\d+(?:[.,]\d+)?|" + "|".join(sorted((re.escape(k) for k in NUMBERS), key=len, reverse=True)) + r")"


def _to_number(tok: str) -> float | None:
    tok = tok.lower()
    if tok in NUMBERS:
        return float(NUMBERS[tok])
    try:
        return float(tok.replace(",", "."))
    except ValueError:
        return None


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace(" ", " "))


def extract(text: str) -> set[Point]:
    """Every point stated in the text, in English or German, with digits or words."""
    t = normalise(text)
    found: set[Point] = set()
    for unit, ure in _UNIT_RE.items():
        for m in re.finditer(r"\b" + _NUM_TOKEN + r"\s+" + ure + r"\b", t):
            n = _to_number(m.group(1))
            if n is not None and n.is_integer():
                found.add(duration(int(n), unit))
    for base, forms in RATE_BASES.items():
        pattern = r"\b" + _NUM_TOKEN + r"\s+(?:percentage points|prozentpunkte)\s+" + "(?:" + "|".join(
            re.escape(normalise(f)) for f in forms.values()) + ")"
        for m in re.finditer(pattern, t):
            n = _to_number(m.group(1))
            if n is not None:
                found.add(rate(n, base))
    for name, forms in ANCHORS.items():
        if any(normalise(f) in t for f in forms.values()):
            found.add(anchor(name))
    if re.search(r"20 (?:million|millionen) euro", t) and re.search(r"\b(?:4|four|vier) (?:percent|prozent)", t):
        found.add(FINE)
    return found


_DE_WORDS = {"der", "die", "das", "und", "ist", "nicht", "eine", "einen", "beträgt", "nach", "zum", "des", "mit", "für"}
_EN_WORDS = {"the", "and", "is", "not", "a", "an", "after", "to", "of", "with", "for", "must", "period"}


def language(text: str) -> str:
    """'de' or 'en' by function words: enough to tell a German answer from an English one."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in _DE_WORDS for w in words)
    en = sum(w in _EN_WORDS for w in words)
    return "de" if de > en else "en"
