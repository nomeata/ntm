"""Die Altersachse.

Die Achse ist eine geordnete Skala von 5 bis 21 plus einem zusätzlichen,
obersten Punkt "Eltern".  21 ist als "21+" zu lesen, "Eltern" als eigener
Adressat.  Intern wird jeder Punkt als Ordinalzahl geführt (5..22), damit
Bereichsvergleiche triviale Zahlenvergleiche bleiben.

In der JSON-Datei stehen die Werte als Zahl (5..21) bzw. als String "Eltern".
"""

from __future__ import annotations

AGE_MIN = 5
AGE_MAX = 21  # als "21+" zu verstehen
PARENTS = 22  # oberster Punkt der Achse
PARENTS_LABEL = "Eltern"

_PARENTS_ALIASES = {"eltern", "parents", str(PARENTS)}


def parse_age(value: object) -> int:
    """Wandelt einen externen Alterswert in seine Ordinalzahl."""
    if isinstance(value, bool):  # bool ist ein int-Subtyp; hier nie gemeint
        raise ValueError(f"ungültiger Alterswert: {value!r}")
    if isinstance(value, int):
        ordinal = value
    elif isinstance(value, str):
        text = value.strip()
        if text.lower() in _PARENTS_ALIASES:
            return PARENTS
        text = text.rstrip("+").strip()
        try:
            ordinal = int(text)
        except ValueError:
            raise ValueError(f"ungültiger Alterswert: {value!r}") from None
    else:
        raise ValueError(f"ungültiger Alterswert: {value!r}")

    if not AGE_MIN <= ordinal <= PARENTS:
        raise ValueError(f"Alterswert außerhalb der Skala: {value!r}")
    return ordinal


def serialize_age(ordinal: int) -> int | str:
    """Externe Darstellung: Zahl oder "Eltern"."""
    return PARENTS_LABEL if ordinal >= PARENTS else ordinal


def age_label(ordinal: int) -> str:
    """Anzeigetext eines Achsenpunktes."""
    if ordinal >= PARENTS:
        return PARENTS_LABEL
    if ordinal >= AGE_MAX:
        return f"{AGE_MAX}+"
    return str(ordinal)


def range_label(age_from: int, age_to: int) -> str:
    if age_from == age_to:
        return age_label(age_from)
    return f"{age_label(age_from)}–{age_label(age_to)}"


def axis() -> list[int]:
    """Alle Punkte der Achse in aufsteigender Reihenfolge."""
    return list(range(AGE_MIN, PARENTS + 1))


def matches_age(age_from: int, age_to: int, wanted: int) -> bool:
    """Enthält der Bereich [age_from, age_to] den gesuchten Punkt?"""
    return age_from <= wanted <= age_to
