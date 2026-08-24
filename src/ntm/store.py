"""Ablage: ein Verzeichnis, eine JSON-Datei pro Eintrag.

Alle Einträge werden im Speicher gehalten (es sind wenige tausend, jeder ein
paar Kilobyte).  Vor jedem Zugriff prüft ein billiger Verzeichnis-Scan über
Name/Größe/mtime, ob sich draußen etwas geändert hat – so kann man die Dateien
auch von Hand bearbeiten oder aus einem Backup zurückspielen.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from pathlib import Path

from . import tags as tags_mod
from .models import Entry, EntryInput
from .query import IndexedEntry

log = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford-artig, ohne i/l/o/u


def new_id() -> str:
    """Zeitlich sortierbare, kollisionsarme ID."""
    stamp = int(time.time() * 1000)
    encoded = ""
    for _ in range(10):
        stamp, remainder = divmod(stamp, len(_ALPHABET))
        encoded = _ALPHABET[remainder] + encoded
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    return encoded + suffix


def valid_id(entry_id: str) -> bool:
    return bool(ID_PATTERN.match(entry_id))


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, IndexedEntry] = {}
        self._signature: object = None
        self.refresh(force=True)

    # -- Laden ---------------------------------------------------------

    def _scan(self) -> list[tuple[str, int, int]]:
        found: list[tuple[str, int, int]] = []
        with os.scandir(self.data_dir) as it:
            for item in it:
                if not item.is_file() or not item.name.endswith(".json"):
                    continue
                info = item.stat()
                found.append((item.name, info.st_mtime_ns, info.st_size))
        found.sort()
        return found

    def refresh(self, *, force: bool = False) -> None:
        """Lädt neu, wenn sich auf der Platte etwas geändert hat."""
        signature = self._scan()
        if not force and signature == self._signature:
            return
        entries: dict[str, IndexedEntry] = {}
        for name, _, _ in signature:
            path = self.data_dir / name
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                raw.setdefault("id", path.stem)
                entry = Entry.model_validate(raw)
            except Exception:  # defekte Datei darf nicht den Rest blockieren
                log.exception("Eintrag %s konnte nicht gelesen werden", path)
                continue
            entries[entry.id] = IndexedEntry.of(entry)
        self._entries = entries
        self._signature = signature

    def _path(self, entry_id: str) -> Path:
        return self.data_dir / f"{entry_id}.json"

    # -- Lesen ---------------------------------------------------------

    def all(self) -> list[IndexedEntry]:
        self.refresh()
        return list(self._entries.values())

    def get(self, entry_id: str) -> Entry | None:
        self.refresh()
        indexed = self._entries.get(entry_id)
        return indexed.entry if indexed else None

    def tag_universe(self) -> dict[str, int]:
        return tags_mod.build_universe(
            [indexed.entry.tags for indexed in self.all()]
        )

    def books(self) -> dict[str, int]:
        """Alle verwendeten Bücher mit Häufigkeit (erste Schreibweise gewinnt)."""
        display: dict[str, str] = {}
        counts: dict[str, int] = {}
        for indexed in self.all():
            book = indexed.entry.book.strip()
            if not book:
                continue
            key = book.casefold()
            display.setdefault(key, book)
            counts[key] = counts.get(key, 0) + 1
        return {display[key]: count for key, count in counts.items()}

    # -- Schreiben -----------------------------------------------------

    def _write(self, entry: Entry) -> Entry:
        payload = entry.model_dump(mode="json")
        path = self._path(entry.id)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp, path)
        self._entries[entry.id] = IndexedEntry.of(entry)
        self._signature = self._scan()
        return entry

    def create(self, data: EntryInput) -> Entry:
        self.refresh()
        entry_id = new_id()
        while entry_id in self._entries or self._path(entry_id).exists():
            entry_id = new_id()
        return self._write(Entry.create(entry_id, data))

    def update(self, entry_id: str, data: EntryInput) -> Entry | None:
        existing = self.get(entry_id)
        if existing is None:
            return None
        return self._write(existing.updated_with(data))

    def delete(self, entry_id: str) -> bool:
        if self.get(entry_id) is None:
            return False
        self._path(entry_id).unlink(missing_ok=True)
        self._entries.pop(entry_id, None)
        self._signature = self._scan()
        return True
