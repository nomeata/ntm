"""Suchen und Filtern – die Kernlogik.

Ein Eintrag ist ein Treffer, wenn er *alle* Bedingungen erfüllt:

* jedes Token der Volltextsuche kommt in Titel, Beschreibung oder Fließtext vor,
* jedes Filter-Schlagwort passt (Unter-Tags eingeschlossen),
* der gesuchte Punkt der Altersachse liegt im Bereich des Eintrags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from . import ages, tags as tags_mod, text
from .models import Entry

WEIGHT_TITLE = 3
WEIGHT_DESCRIPTION = 2
WEIGHT_TEXT = 1


@dataclass(frozen=True)
class IndexedEntry:
    """Eintrag samt vorberechneter Textfaltungen."""

    entry: Entry
    title: text.Folded
    description: text.Folded
    body: text.Folded

    @classmethod
    def of(cls, entry: Entry) -> IndexedEntry:
        return cls(
            entry=entry,
            title=text.fold(entry.title),
            description=text.fold(entry.description),
            body=text.fold(entry.text),
        )


@dataclass
class SearchQuery:
    q: str = ""
    tags: list[str] = field(default_factory=list)
    age: int | None = None

    @property
    def tokens(self) -> list[str]:
        return text.tokenize(self.q)


def score(indexed: IndexedEntry, tokens: list[str]) -> int | None:
    """Relevanz eines Eintrags, ``None`` wenn nicht alle Tokens vorkommen."""
    total = 0
    for token in tokens:
        best = 0
        if text.contains(indexed.title, token):
            best = WEIGHT_TITLE
        elif text.contains(indexed.description, token):
            best = WEIGHT_DESCRIPTION
        elif text.contains(indexed.body, token):
            best = WEIGHT_TEXT
        if best == 0:
            return None
        total += best
    return total


def matches_filters(entry: Entry, query: SearchQuery) -> bool:
    if query.age is not None and not ages.matches_age(
        entry.age_from, entry.age_to, query.age
    ):
        return False
    return tags_mod.matches_all_filters(entry.tags, query.tags)


def search(entries: Iterable[IndexedEntry], query: SearchQuery) -> list[Entry]:
    """Gefilterte, sortierte Trefferliste."""
    tokens = query.tokens
    hits: list[tuple[int, str, Entry]] = []
    for indexed in entries:
        if not matches_filters(indexed.entry, query):
            continue
        relevance = score(indexed, tokens)
        if relevance is None:
            continue
        hits.append((relevance, indexed.entry.title.casefold(), indexed.entry))
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    return [entry for _, _, entry in hits]
