"""Schlagworte und ihre Hierarchie.

Ein Schlagwort ist ein Pfad aus Segmenten, getrennt durch "/", z. B.
``Sprache/Grammatik/Kasus``.  Die Hierarchie steckt ausschließlich im Namen –
es gibt keine separate Tag-Entität.  Gespeichert wird stets der volle Pfad,
damit ein späterer Umbau (Umbenennen/Verschieben) ein reines Präfix-Rewrite
über alle Einträge ist.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import text

SEPARATOR = "/"


def split_tag(tag: str) -> list[str]:
    """Segmente eines Pfades, leere Segmente entfallen."""
    return [
        " ".join(segment.split())
        for segment in tag.split(SEPARATOR)
        if segment.strip()
    ]


def normalize_tag(tag: str) -> str:
    """Kanonische Schreibweise: getrimmte Segmente, einfache Trenner."""
    return SEPARATOR.join(split_tag(tag))


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalisiert eine Liste, entfernt Leeres und Dubletten (Reihenfolge bleibt)."""
    result: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = normalize_tag(tag)
        if not normalized:
            continue
        key = tag_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def tag_key(tag: str) -> str:
    """Vergleichsschlüssel: Groß-/Kleinschreibung ist unerheblich."""
    return SEPARATOR.join(segment.casefold() for segment in split_tag(tag))


def ancestors(tag: str, *, include_self: bool = True) -> list[str]:
    """Alle Präfixe eines Pfades, von der Wurzel abwärts."""
    segments = split_tag(tag)
    if not include_self:
        segments = segments[:-1]
    return [SEPARATOR.join(segments[: i + 1]) for i in range(len(segments))]


def is_descendant(tag: str, ancestor: str) -> bool:
    """Ist ``tag`` gleich ``ancestor`` oder liegt es darunter?"""
    tag_segments = tag_key(tag).split(SEPARATOR) if tag_key(tag) else []
    anc_segments = tag_key(ancestor).split(SEPARATOR) if tag_key(ancestor) else []
    if not anc_segments:
        return False
    return tag_segments[: len(anc_segments)] == anc_segments


def matches_filter(entry_tags: list[str], wanted: str) -> bool:
    """Ein Filter-Tag schließt seine Unter-Tags mit ein."""
    return any(is_descendant(tag, wanted) for tag in entry_tags)


def matches_all_filters(entry_tags: list[str], wanted: list[str]) -> bool:
    return all(matches_filter(entry_tags, filter_tag) for filter_tag in wanted)


@dataclass(frozen=True)
class TagSuggestion:
    tag: str
    count: int


def build_universe(entry_tags: list[list[str]]) -> dict[str, int]:
    """Alle vergebenen Tags *inklusive* ihrer Oberbegriffe mit Trefferzahl.

    Gezählt wird pro Eintrag: ein Eintrag mit ``A/B`` und ``A/C`` zählt für
    ``A`` nur einmal.  Als Anzeigeform gewinnt die erste gesehene Schreibweise.
    """
    display: dict[str, str] = {}
    counts: dict[str, int] = {}
    for tags in entry_tags:
        seen: set[str] = set()
        for tag in tags:
            for prefix in ancestors(tag):
                key = tag_key(prefix)
                display.setdefault(key, prefix)
                if key not in seen:
                    seen.add(key)
                    counts[key] = counts.get(key, 0) + 1
    return {display[key]: count for key, count in counts.items()}


def _score(tag: str, query: str) -> int | None:
    """Je höher, desto besser; ``None`` heißt: kein Treffer.

    Enthält die Anfrage einen "/", wird gegen den ganzen Pfad geprüft,
    sonst gegen die einzelnen Segmente.
    """
    query = query.strip()
    if not query:
        return 0
    if SEPARATOR in query:
        folded_path = text.fold(tag)
        needle = SEPARATOR.join(split_tag(query))
        if not text.contains(folded_path, needle):
            return None
        return 40 if text.fold(tag)[0].startswith(text.fold(needle)[0]) else 20

    best: int | None = None
    segments = split_tag(tag)
    for index, segment in enumerate(segments):
        folded = text.fold(segment)
        needle_plain, needle_expanded = text.fold(query)
        if folded[0] == needle_plain or folded[1] == needle_expanded:
            score = 100
        elif folded[0].startswith(needle_plain) or folded[1].startswith(needle_expanded):
            score = 60
        elif needle_plain in folded[0] or needle_expanded in folded[1]:
            score = 30
        else:
            continue
        # Treffer im letzten Segment sind meist gemeint, Treffer weiter vorne
        # liefern dafür kürzere, allgemeinere Pfade.
        if index == len(segments) - 1:
            score += 5
        if best is None or score > best:
            best = score
    return best


def suggest(
    universe: dict[str, int], query: str, *, limit: int = 12
) -> list[TagSuggestion]:
    """Typeahead über alle bekannten Tags, auch auf Teilsegmenten."""
    scored: list[tuple[int, int, int, str]] = []
    for tag, count in universe.items():
        score = _score(tag, query)
        if score is None:
            continue
        # Sortierung: Score, dann Häufigkeit, dann kurze Pfade, dann Alphabet.
        scored.append((-score, -count, len(split_tag(tag)), tag))
    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3].casefold()))
    return [
        TagSuggestion(tag=tag, count=universe[tag]) for _, _, _, tag in scored[:limit]
    ]
