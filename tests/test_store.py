"""Ablage auf der Platte."""

import json

from ntm import ages
from ntm.models import EntryInput
from ntm.store import Store


def make_input(**kwargs) -> EntryInput:
    data = {"title": "Titel", "age_from": 5, "age_to": 21}
    data.update(kwargs)
    return EntryInput(**data)


def test_anlegen_schreibt_eine_datei_pro_eintrag(tmp_path):
    store = Store(tmp_path)
    entry = store.create(make_input(title="Kasus-Memory", tags=["Sprache/Grammatik"]))
    path = tmp_path / f"{entry.id}.json"
    assert path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["title"] == "Kasus-Memory"
    assert raw["schema_version"] == 1
    assert raw["age_from"] == 5


def test_eltern_steht_lesbar_in_der_json(tmp_path):
    store = Store(tmp_path)
    entry = store.create(make_input(age_from="Eltern", age_to="Eltern"))
    raw = json.loads((tmp_path / f"{entry.id}.json").read_text(encoding="utf-8"))
    assert raw["age_from"] == "Eltern"
    assert store.get(entry.id).age_from == ages.PARENTS


def test_aendern_behaelt_id_und_anlagedatum(tmp_path):
    store = Store(tmp_path)
    entry = store.create(make_input(title="Alt"))
    changed = store.update(entry.id, make_input(title="Neu"))
    assert changed.id == entry.id
    assert changed.created == entry.created
    assert changed.title == "Neu"
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_loeschen(tmp_path):
    store = Store(tmp_path)
    entry = store.create(make_input())
    assert store.delete(entry.id) is True
    assert store.get(entry.id) is None
    assert store.delete(entry.id) is False
    assert list(tmp_path.glob("*.json")) == []


def test_neues_verzeichnis_wird_angelegt(tmp_path):
    store = Store(tmp_path / "tief" / "drin")
    assert store.data_dir.is_dir()
    assert store.all() == []


def test_aenderungen_von_hand_werden_bemerkt(tmp_path):
    store = Store(tmp_path)
    entry = store.create(make_input(title="Alt"))
    path = tmp_path / f"{entry.id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["title"] = "Von Hand geändert"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert store.get(entry.id).title == "Von Hand geändert"


def test_fremde_datei_ohne_id_nutzt_den_dateinamen(tmp_path):
    (tmp_path / "handgemacht.json").write_text(
        json.dumps({"title": "Handgemacht", "age_from": 5, "age_to": 21}),
        encoding="utf-8",
    )
    store = Store(tmp_path)
    assert store.get("handgemacht").title == "Handgemacht"


def test_kaputte_datei_blockiert_den_rest_nicht(tmp_path):
    (tmp_path / "kaputt.json").write_text("{ das ist kein JSON", encoding="utf-8")
    store = Store(tmp_path)
    entry = store.create(make_input(title="Heil"))
    assert [indexed.entry.title for indexed in store.all()] == ["Heil"]
    assert store.get(entry.id) is not None


def test_stammdaten_sammeln_tags_und_buecher(tmp_path):
    store = Store(tmp_path)
    store.create(make_input(tags=["Sprache/Grammatik"], book="Sprachförderung konkret"))
    store.create(make_input(tags=["Sprache/Wortschatz"], book="Sprachförderung konkret"))
    store.create(make_input(tags=["Motorik"], book="digital"))
    universe = store.tag_universe()
    assert universe["Sprache"] == 2
    assert universe["Motorik"] == 1
    assert store.books() == {"Sprachförderung konkret": 2, "digital": 1}


def test_ids_sind_zeitlich_sortierbar(tmp_path):
    store = Store(tmp_path)
    ids = [store.create(make_input()).id for _ in range(5)]
    stamps = [entry_id[:10] for entry_id in ids]  # Zeitanteil, danach Zufall
    assert stamps == sorted(stamps)
    assert len(set(ids)) == 5


def test_migration_weist_altbestand_der_ersten_nutzerin_zu(tmp_path):
    from ntm.store import migrate_legacy

    old = Store(tmp_path)
    old.create(make_input(title="Alt 1"))
    old.create(make_input(title="Alt 2"))
    (tmp_path / ".secret").write_text("bleibt liegen\n")

    assert migrate_legacy(tmp_path, "anna@example.org") == 2
    assert list(tmp_path.glob("*.json")) == []
    assert (tmp_path / ".secret").exists()
    moved = Store(tmp_path / "anna@example.org")
    assert {item.entry.title for item in moved.all()} == {"Alt 1", "Alt 2"}

    # Ein zweiter Lauf fasst nichts mehr an, auch wenn wieder Dateien auftauchen.
    Store(tmp_path).create(make_input(title="Streuner"))
    assert migrate_legacy(tmp_path, "anna@example.org") == 0


def test_migration_ohne_altbestand_tut_nichts(tmp_path):
    from ntm.store import migrate_legacy

    assert migrate_legacy(tmp_path, "anna@example.org") == 0
    assert not (tmp_path / "anna@example.org").exists()
