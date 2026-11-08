"""Sentences a legal assistant writes besides the facts: scaffolds, background padding, confident markers, and
overclaims (statements no source supports; a lawyer who relies on them is misled)."""

SCAFFOLD = {"en": "Under {cites}: {facts}.", "de": "Nach {cites}: {facts}."}

ABSTAIN = {
    "en": "The retrieved sources do not answer this question; please check the applicable provision before advising.",
    "de": "Die abgerufenen Quellen beantworten diese Frage nicht; bitte die einschlägige Vorschrift prüfen.",
}

PADDING = {
    "en": [
        "The rules aim to balance the interests of both parties and to give each of them planning certainty.",
        "In practice, firms document the relevant dates carefully so that deadlines can be shown later.",
        "It is good practice to record when and how the relevant information was received.",
        "Collective agreements or individual contracts may contain further provisions that should be checked.",
    ],
    "de": [
        "Die Regeln sollen die Interessen beider Seiten ausgleichen und Planungssicherheit schaffen.",
        "In der Praxis werden die maßgeblichen Daten sorgfältig dokumentiert, um Fristen später belegen zu können.",
        "Es empfiehlt sich festzuhalten, wann und wie die maßgeblichen Informationen eingegangen sind.",
        "Tarifverträge oder Einzelverträge können weitere Regelungen enthalten, die zu prüfen sind.",
    ],
}

CONFIDENT = {
    "en": ["Clearly,", "Without doubt,", "It is settled that"],
    "de": ["Eindeutig gilt:", "Zweifellos gilt:", "Es steht fest:"],
}

OVERCLAIMS = {
    "en": [
        "This rule applies without exception and cannot be varied by any agreement.",
        "Courts have never departed from this rule.",
        "No further facts need to be checked before relying on this.",
    ],
    "de": [
        "Diese Regel gilt ausnahmslos und kann durch keine Vereinbarung geändert werden.",
        "Die Gerichte sind von dieser Regel nie abgewichen.",
        "Vor einer Berufung darauf müssen keine weiteren Umstände geprüft werden.",
    ],
}


def all_overclaims() -> list[str]:
    return [s for v in OVERCLAIMS.values() for s in v]
