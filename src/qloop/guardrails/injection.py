"""Prompt injection from ingested documents: find the segments that talk to the assistant instead of the reader.

Contracts are full of the word "instructions" ("the Supplier shall follow the Customer's written instructions"), so
the detector looks for the combination that injections need: an override verb aimed at prior instructions, or a
message addressed to an AI system, in English, German or Dutch, after removing zero-width characters and folding
look-alike letters.
"""

from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")
HOMOGLYPHS = str.maketrans({"а": "a", "е": "e", "о": "o", "і": "i", "р": "p", "с": "c",
                            "1": "1", "ı": "i"})

OVERRIDE = re.compile(
    r"\b(ignore|disregard|forget|override|ignoriere|ignorieren|vergiss|missachte|negeer|vergeet)\b[^.]{0,60}?"
    r"\b(instructions?|prompts?|rules|anweisungen|vorgaben|instructies|regels)\b"
    r"|\b(previous|prior|earlier|above|bisherigen|vorherigen|eerdere)\s+(instructions?|anweisungen|instructies)\b[^.]{0,40}"
    r"(outdated|void|cancelled|no longer|ungültig|vervallen)", re.I)
ADDRESSED = re.compile(
    r"(note|message|hinweis|nachricht|opmerking|bericht)\s+(to|for|an|für|voor)\s+(the\s+|den\s+|de\s+)?"
    r"(ai|ki|llm|language model|assistant|assistent|sprachmodell)"
    r"|^\s*(system|assistant)\s*:|\[\[\s*(system|assistant)\s*:", re.I | re.M)
EXFIL = re.compile(r"\b(copy|repeat|include|send|kopiere|stuur)\b[^.]{0,40}\b(iban|password|api key|passwort|wachtwoord)", re.I)

SEGMENT = re.compile(r"\[\[.*?\]\]|[^.!?\n]+[.!?]?", re.S)


def normalise(text: str) -> str:
    text = ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text))
    return text.translate(HOMOGLYPHS)


def is_injection(segment: str) -> bool:
    s = normalise(segment)
    return bool(OVERRIDE.search(s) or ADDRESSED.search(s) or EXFIL.search(s))


def segments(text: str) -> list[str]:
    return [m.group(0) for m in SEGMENT.finditer(text) if m.group(0).strip()]


def scan_documents(text: str) -> tuple[str, list[str]]:
    """The document without its injected segments, and the segments removed."""
    keep, removed = [], []
    for seg in segments(text):
        (removed if is_injection(seg) else keep).append(seg)
    return "".join(keep), [r.strip() for r in removed]
