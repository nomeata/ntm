import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ntm.models import Entry, EntryInput  # noqa: E402
from ntm.query import IndexedEntry  # noqa: E402


def make_entry(entry_id: str = "x", **kwargs) -> Entry:
    """Eintrag mit brauchbaren Vorgaben; Alter darf als 5/"Eltern" kommen."""
    data = {
        "title": "Titel",
        "description": "",
        "text": "",
        "age_from": 5,
        "age_to": 21,
        "tags": [],
        "book": "",
        "location": "",
    }
    data.update(kwargs)
    return Entry.create(entry_id, EntryInput(**data))


def indexed(*entries: Entry) -> list[IndexedEntry]:
    return [IndexedEntry.of(entry) for entry in entries]


@pytest.fixture
def entry_factory():
    return make_entry
