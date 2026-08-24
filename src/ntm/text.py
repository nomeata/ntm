"""Textnormalisierung für Suche und Typeahead.

Zwei Faltungen laufen parallel, damit sowohl "Marchen" als auch "Maerchen"
den Eintrag "Märchen" finden:

* ``plain``    – Diakritika werden entfernt (ä → a)
* ``expanded`` – deutsche Umlaute werden ausgeschrieben (ä → ae, ß → ss)

Ein Suchbegriff passt, wenn *eine* seiner Faltungen in der gleichnamigen
Faltung des Textes vorkommt.
"""

from __future__ import annotations

import unicodedata

_EXPANSIONS = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "ae",
    "Ö": "oe",
    "Ü": "ue",
    "ß": "ss",
}

# (plain, expanded)
Folded = tuple[str, str]


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def fold(text: str) -> Folded:
    """Beide Faltungen eines Textes."""
    lowered = text.casefold()
    plain = _strip_diacritics(lowered)
    expanded = _strip_diacritics(
        "".join(_EXPANSIONS.get(ch, ch) for ch in text).casefold()
    )
    return plain, expanded


def contains(haystack: Folded, needle: str) -> bool:
    """Kommt ``needle`` (roh) im gefalteten ``haystack`` vor?"""
    plain, expanded = fold(needle)
    if not plain and not expanded:
        return True
    return plain in haystack[0] or expanded in haystack[1]


def tokenize(query: str) -> list[str]:
    """Zerlegt eine Suchanfrage in Tokens (UND-verknüpft).

    Anführungszeichen halten mehrere Wörter zusammen.
    """
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for ch in query:
        if quote:
            if ch == quote:
                quote = None
            else:
                current.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return [token for token in tokens if token]
